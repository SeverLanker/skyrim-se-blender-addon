# SPDX-License-Identifier: MIT
"""Animation retarget: bake source Action onto another Armature (v0.3)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import ceil, floor
from pathlib import Path
from typing import Optional

import bpy
from mathutils import Matrix


@dataclass
class RetargetRequest:
    source_armature: str
    target_armature: str
    action_name: str = ""
    bone_map: dict[str, str] = field(default_factory=dict)
    mode: str = "NAME"  # NAME | CUSTOM
    channels: str = "LOC_ROT"  # ROT | LOC_ROT
    overwrite: bool = False
    new_action_name: str = ""
    copy_root_motion: bool = True


@dataclass
class RetargetResult:
    ok: bool
    message: str
    action_name: str = ""
    matched: int = 0
    skipped_source: int = 0
    skipped_target: int = 0
    frames: int = 0
    implemented: bool = True


@dataclass
class RetargetPlan:
    """Kept for callers that still ask for a plan summary."""

    summary: str
    steps: list[str] = field(default_factory=list)
    implemented: bool = True


def plan_retarget(request: RetargetRequest) -> RetargetPlan:
    steps = [
        "校验源/目标 Armature 与 Action",
        "按同名或自定义映射表建立骨对",
        "逐帧将源姿势烘焙到目标骨骼局部空间（matrix_basis）",
        "按通道写入旋转 / 位置关键帧并绑定到目标",
    ]
    summary = (
        f"Retarget {request.source_armature} → {request.target_armature}"
        f"（Action={request.action_name or '当前'}，模式={request.mode}）"
    )
    return RetargetPlan(summary=summary, steps=steps, implemented=True)


def guess_bone_map(
    source_arm: bpy.types.Object,
    target_arm: bpy.types.Object,
) -> dict[str, str]:
    """Exact name first, then case-insensitive."""
    target_names = {b.name: b.name for b in target_arm.data.bones}
    target_fold = {n.casefold(): n for n in target_names}
    mapping: dict[str, str] = {}
    for bone in source_arm.data.bones:
        if bone.name in target_names:
            mapping[bone.name] = bone.name
        elif bone.name.casefold() in target_fold:
            mapping[bone.name] = target_fold[bone.name.casefold()]
    return mapping


def mapping_from_collection(collection) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in collection:
        src = (item.source_bone or "").strip()
        dst = (item.target_bone or "").strip()
        if src and dst:
            out[src] = dst
    return out


def export_mapping_json(mapping: dict[str, str], filepath: str | Path) -> Path:
    path = Path(filepath).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def import_mapping_json(filepath: str | Path) -> dict[str, str]:
    path = Path(filepath).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"映射文件不存在：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("映射 JSON 必须是对象：{源骨名: 目标骨名}")
    out: dict[str, str] = {}
    for key, value in data.items():
        src = str(key).strip()
        dst = str(value).strip()
        if src and dst:
            out[src] = dst
    return out


def _action_of(arm: bpy.types.Object) -> Optional[bpy.types.Action]:
    if arm.animation_data and arm.animation_data.action:
        return arm.animation_data.action
    return None


def _resolve_action(
    source_arm: bpy.types.Object,
    action_name: str,
) -> tuple[bpy.types.Action, object]:
    """Return (action, source_slot_or_None)."""
    slot = None
    if action_name:
        action = bpy.data.actions.get(action_name)
        if action is None:
            raise ValueError(f"找不到 Action「{action_name}」")
    else:
        action = _action_of(source_arm)
        if action is None:
            raise ValueError(f"源 Armature「{source_arm.name}」没有当前 Action")
        slot = getattr(source_arm.animation_data, "action_slot", None)
    return action, slot


def _ensure_anim_data(arm: bpy.types.Object):
    if arm.animation_data is None:
        arm.animation_data_create()
    return arm.animation_data


def _bind_action(arm: bpy.types.Object, action: bpy.types.Action, slot=None):
    ad = _ensure_anim_data(arm)
    ad.action = action
    if slot is not None and hasattr(ad, "action_slot"):
        try:
            ad.action_slot = slot
        except Exception:
            pass


def _unique_action_name(base: str, overwrite: bool) -> str:
    if overwrite:
        existing = bpy.data.actions.get(base)
        if existing is not None:
            bpy.data.actions.remove(existing)
        return base
    name = base
    if name not in bpy.data.actions:
        return name
    i = 1
    while f"{base}.{i:03d}" in bpy.data.actions:
        i += 1
    return f"{base}.{i:03d}"


def _root_bone_names(arm: bpy.types.Object) -> set[str]:
    roots = set()
    for bone in arm.data.bones:
        if bone.parent is None:
            roots.add(bone.name)
    # Common Skyrim / generic roots
    for name in ("NPC Root [Root]", "NPC", "Root", "root", "Armature"):
        if name in arm.data.bones:
            roots.add(name)
    return roots


def bake_pose_to_target(
    source_arm: bpy.types.Object,
    target_arm: bpy.types.Object,
    action: bpy.types.Action,
    bone_map: dict[str, str],
    *,
    channels: str = "LOC_ROT",
    new_name: str = "",
    overwrite: bool = False,
    source_slot=None,
    copy_root_motion: bool = True,
) -> RetargetResult:
    """
    Evaluate source Action frame-by-frame and bake matched bones into the
    target armature's local space (matrix_basis), same idea as FBX transfer bake.
    """
    if source_arm.type != "ARMATURE" or target_arm.type != "ARMATURE":
        return RetargetResult(False, "源与目标都必须是 Armature")
    if source_arm == target_arm:
        return RetargetResult(False, "源与目标不能是同一个 Armature")

    src_bones = source_arm.pose.bones
    tgt_bones = target_arm.pose.bones

    pairs: list[tuple[str, str]] = []
    skipped_source = 0
    for src_name, tgt_name in bone_map.items():
        if src_name not in src_bones:
            skipped_source += 1
            continue
        if tgt_name not in tgt_bones:
            skipped_source += 1
            continue
        pairs.append((src_name, tgt_name))

    target_used = {t for _, t in pairs}
    skipped_target = sum(1 for b in tgt_bones if b.name not in target_used)

    if not pairs:
        return RetargetResult(
            False,
            "没有可匹配的骨骼。请用同名模式，或先「按名称猜测映射」/导入 JSON。",
            matched=0,
            skipped_source=skipped_source,
            skipped_target=skipped_target,
        )

    # Temporarily bind action on source so frame_set evaluates it.
    prev_action = _action_of(source_arm)
    prev_slot = (
        getattr(source_arm.animation_data, "action_slot", None)
        if source_arm.animation_data
        else None
    )
    _bind_action(source_arm, action, source_slot)

    base_name = new_name or f"{action.name}_on_{target_arm.name}"
    action_name = _unique_action_name(base_name, overwrite=overwrite)
    new_action = bpy.data.actions.new(action_name)
    _bind_action(target_arm, new_action)

    channels = (channels or "LOC_ROT").upper()
    use_loc = channels in {"LOC_ROT", "LOC", "ALL"}
    use_rot = channels in {"ROT", "LOC_ROT", "ALL"}
    root_names = _root_bone_names(target_arm) if not copy_root_motion else set()

    start = floor(action.frame_range[0])
    end = ceil(action.frame_range[1])
    if end < start:
        start, end = 1, 1

    scene = bpy.context.scene
    original_frame = scene.frame_current
    frames_written = 0

    try:
        for frame in range(start, end + 1):
            scene.frame_set(frame)
            # Map source pose into target's armature space.
            world_to_target = target_arm.matrix_world.inverted() @ source_arm.matrix_world
            armature_space: dict[str, Matrix] = {}
            for src_name, tgt_name in pairs:
                armature_space[tgt_name] = (
                    world_to_target @ src_bones[src_name].matrix
                )

            for src_name, tgt_name in pairs:
                bone = tgt_bones[tgt_name]
                parent = bone.parent
                parent_options = {}
                if parent is not None:
                    parent_options = {
                        "parent_matrix": armature_space.get(
                            parent.name, parent.matrix
                        ),
                        "parent_matrix_local": parent.bone.matrix_local,
                    }
                bone.rotation_mode = "QUATERNION"
                bone.matrix_basis = bone.bone.convert_local_to_pose(
                    armature_space[tgt_name],
                    bone.bone.matrix_local,
                    invert=True,
                    **parent_options,
                )

                if use_rot:
                    bone.keyframe_insert(
                        data_path="rotation_quaternion",
                        frame=frame,
                        group=bone.name,
                    )
                if use_loc:
                    if bone.name in root_names and not copy_root_motion:
                        pass
                    else:
                        bone.keyframe_insert(
                            data_path="location",
                            frame=frame,
                            group=bone.name,
                        )
            frames_written += 1
    except Exception as exc:  # noqa: BLE001
        # Restore source binding; leave partial target action for inspection.
        try:
            if prev_action is not None:
                _bind_action(source_arm, prev_action, prev_slot)
        except Exception:
            pass
        return RetargetResult(
            False,
            f"烘焙失败：{exc}",
            action_name=action_name,
            matched=len(pairs),
            skipped_source=skipped_source,
            skipped_target=skipped_target,
        )
    finally:
        scene.frame_set(original_frame)
        try:
            if prev_action is not None:
                _bind_action(source_arm, prev_action, prev_slot)
            elif source_arm.animation_data:
                # Keep the requested action if there was no previous one.
                _bind_action(source_arm, action, source_slot)
        except Exception:
            pass

    # Ensure target still has the new action (and its slot if 5.2 created one).
    _bind_action(target_arm, new_action)
    if hasattr(target_arm.animation_data, "action_slot"):
        # Prefer the slot that received keyframes when multiple exist.
        try:
            slots = list(getattr(new_action, "slots", []) or [])
            if len(slots) == 1:
                target_arm.animation_data.action_slot = slots[0]
        except Exception:
            pass

    msg = (
        f"Retarget 完成：「{action.name}」→「{target_arm.name}」Action「{action_name}」。"
        f"匹配 {len(pairs)} 骨，跳过源映射 {skipped_source}，"
        f"目标未映射 {skipped_target}，帧 {frames_written}（{channels}）。"
    )
    return RetargetResult(
        True,
        msg,
        action_name=action_name,
        matched=len(pairs),
        skipped_source=skipped_source,
        skipped_target=skipped_target,
        frames=frames_written,
    )


def execute_retarget(request: RetargetRequest) -> RetargetResult:
    """High-level entry used by operators."""
    source = bpy.data.objects.get(request.source_armature)
    target = bpy.data.objects.get(request.target_armature)
    if source is None or source.type != "ARMATURE":
        return RetargetResult(
            False, f"找不到源 Armature「{request.source_armature}」"
        )
    if target is None or target.type != "ARMATURE":
        return RetargetResult(
            False, f"找不到目标 Armature「{request.target_armature}」"
        )

    try:
        action, slot = _resolve_action(source, request.action_name)
    except ValueError as exc:
        return RetargetResult(False, str(exc))

    mode = (request.mode or "NAME").upper()
    if mode == "CUSTOM":
        bone_map = dict(request.bone_map)
        if not bone_map:
            return RetargetResult(
                False,
                "自定义模式需要映射表。请「按名称猜测」或导入 JSON。",
            )
    else:
        bone_map = guess_bone_map(source, target)
        if not bone_map:
            return RetargetResult(
                False,
                "同名模式下没有匹配骨骼。请改用自定义映射。",
            )

    return bake_pose_to_target(
        source,
        target,
        action,
        bone_map,
        channels=request.channels,
        new_name=request.new_action_name,
        overwrite=request.overwrite,
        source_slot=slot,
        copy_root_motion=request.copy_root_motion,
    )
