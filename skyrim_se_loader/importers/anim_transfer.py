# SPDX-License-Identifier: MIT
"""
Animation transfer pipeline: HKX → FBX/glTF → Action on target armature.

Research (2026): There is no widely used free standalone CLI that converts
Skyrim SE 64-bit HKX directly to FBX/glTF. Practical path:

  1) Optional external converter if the user configured one in preferences
  2) Semi-automatic (default):
       PyNifly import HKX onto an armature
       → Blender export_scene.fbx / export_scene.gltf
       → import onto / copy Action to the user target armature

Native PyNifly HKX→Action remains available as an advanced option elsewhere.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from math import ceil, floor
from pathlib import Path
from typing import Optional

import bpy

from ..adapters.base import ImportResult
from ..utils import deps
from ..utils.paths import ensure_dir, ensure_file, expand_path
from . import pynifly_bridge


TRANSFER_EXTS = {".fbx", ".glb", ".gltf"}
HKX_EXTS = {".hkx"}


def resolve_transfer_format(context, scene_override: str = "SCENE") -> str:
    if scene_override and scene_override != "SCENE":
        return scene_override.upper()
    prefs = deps.get_addon_prefs(context)
    if prefs and prefs.anim_transfer_format:
        return prefs.anim_transfer_format.upper()
    return "FBX"


def resolve_output_dir(context, scene_dir: str, source: Path) -> Path:
    if scene_dir:
        return ensure_dir(scene_dir, create=True)
    prefs = deps.get_addon_prefs(context)
    if prefs and prefs.anim_transfer_output_dir:
        return ensure_dir(prefs.anim_transfer_output_dir, create=True)
    return source.parent


def intermediate_path(out_dir: Path, source: Path, fmt: str) -> Path:
    stem = source.stem
    if fmt == "FBX":
        return out_dir / f"{stem}_transfer.fbx"
    return out_dir / f"{stem}_transfer.glb"


def _deselect_all():
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)


def _activate(obj):
    _deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _find_armature(name: str | None = None) -> Optional[bpy.types.Object]:
    if name and name in bpy.data.objects:
        obj = bpy.data.objects[name]
        if obj.type == "ARMATURE":
            return obj
    active = bpy.context.view_layer.objects.active
    if active and active.type == "ARMATURE":
        return active
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
    return None


def _action_of(arm: bpy.types.Object) -> Optional[bpy.types.Action]:
    if arm.animation_data and arm.animation_data.action:
        return arm.animation_data.action
    return None


def _curve_collections(action, slot=None):
    if hasattr(action, "fcurves"):
        yield action.fcurves
        return
    for layer in action.layers:
        for strip in layer.strips:
            if strip.type == "KEYFRAME":
                for bag in strip.channelbags:
                    if slot is None or bag.slot_handle == slot.handle:
                        yield bag.fcurves


def copy_action_by_bone_name(
    source_action: bpy.types.Action,
    target_arm: bpy.types.Object,
    new_name: str = "",
    source_slot=None,
) -> bpy.types.Action:
    """Copy F-Curves whose data_path references bones that exist on target."""
    name = new_name or f"{source_action.name}_on_{target_arm.name}"
    new_action = source_action.copy()
    new_action.name = name

    copied_slot = None
    if not hasattr(new_action, "fcurves"):
        slots = list(source_action.slots)
        if source_slot is None and len(slots) == 1:
            source_slot = slots[0]
        if source_slot is None:
            bpy.data.actions.remove(new_action)
            raise ValueError("动作有多个或没有 Slot，无法确定要复制的骨骼动画")
        slot_index = next(i for i, slot in enumerate(slots) if slot == source_slot)
        copied_slot = new_action.slots[slot_index]

    bone_names = {b.name for b in target_arm.data.bones}
    # Drop fcurves for bones that do not exist on the target armature.
    for curves in _curve_collections(new_action, copied_slot):
        for fc in list(curves):
            m = re.match(r'pose\.bones\["([^"]+)"\]', fc.data_path)
            if m is not None and m.group(1) not in bone_names:
                curves.remove(fc)

    if target_arm.animation_data is None:
        target_arm.animation_data_create()
    target_arm.animation_data.action = new_action
    if copied_slot is not None:
        target_arm.animation_data.action_slot = copied_slot
    return new_action


def run_external_converter(
    context,
    source: Path,
    output: Path,
    fmt: str,
) -> ImportResult:
    prefs = deps.get_addon_prefs(context)
    if not prefs or not prefs.external_hkx_converter:
        return ImportResult(False, "未配置外部转换器", backend="external")

    exe = expand_path(prefs.external_hkx_converter)
    if not Path(exe).is_file():
        return ImportResult(
            False,
            f"外部转换器不存在：{exe}",
            backend="external",
        )

    template = prefs.external_hkx_converter_args or '"{input}" "{output}"'
    filled = (
        template.replace("{input}", str(source))
        .replace("{output}", str(output))
        .replace("{format}", fmt.lower())
    )
    try:
        args = shlex.split(filled, posix=os_name_posix())
    except ValueError as exc:
        return ImportResult(False, f"参数模板无效：{exc}", backend="external")

    cmd = [exe, *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        return ImportResult(False, f"外部转换器启动失败：{exc}", backend="external")

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return ImportResult(
            False,
            f"外部转换器失败（code={proc.returncode}）：{err[:300]}",
            backend="external",
        )
    if not output.is_file():
        return ImportResult(
            False,
            f"外部转换器退出 0，但未找到输出文件：{output}",
            backend="external",
        )
    return ImportResult(
        True,
        f"外部转换完成：{output.name}",
        backend="external",
    )


def os_name_posix() -> bool:
    import os

    return os.name != "nt"


def export_armature_animation(
    arm: bpy.types.Object,
    filepath: Path,
    fmt: str,
) -> ImportResult:
    _activate(arm)
    fmt = fmt.upper()
    scene = bpy.context.scene
    original_range = (scene.frame_start, scene.frame_end, scene.frame_current)
    action = _action_of(arm)
    if action is not None:
        scene.frame_start = floor(action.frame_range[0])
        scene.frame_end = ceil(action.frame_range[1])
    try:
        if fmt == "FBX":
            if not deps.operator_exists(bpy.ops.export_scene, "fbx"):
                return ImportResult(
                    False,
                    "未找到 export_scene.fbx。请在偏好设置启用 FBX 格式插件。",
                    backend="fbx",
                )
            kwargs = {
                "filepath": str(filepath),
                "use_selection": True,
                "object_types": {"ARMATURE"},
                "bake_anim": True,
                "add_leaf_bones": False,
                "bake_anim_use_nla_strips": False,
                "bake_anim_use_all_actions": False,
                "bake_anim_simplify_factor": 0.0,
            }
            try:
                result = bpy.ops.export_scene.fbx(**kwargs)
            except TypeError:
                result = bpy.ops.export_scene.fbx(
                    filepath=str(filepath),
                    use_selection=True,
                )
        else:
            if not deps.operator_exists(bpy.ops.export_scene, "gltf"):
                return ImportResult(
                    False,
                    "未找到 export_scene.gltf。请启用 glTF 2.0 格式插件。",
                    backend="gltf",
                )
            kwargs = {
                "filepath": str(filepath),
                "export_format": "GLB",
                "use_selection": True,
                "export_animations": True,
                "export_skins": True,
            }
            properties = bpy.ops.export_scene.gltf.get_rna_type().properties
            if "export_animation_mode" in properties:
                kwargs["export_animation_mode"] = "ACTIVE_ACTIONS"
            else:
                kwargs["export_nla_strips"] = False
            try:
                result = bpy.ops.export_scene.gltf(**kwargs)
            except TypeError:
                result = bpy.ops.export_scene.gltf(filepath=str(filepath))
    except Exception as exc:  # noqa: BLE001
        return ImportResult(False, f"导出中转文件失败：{exc}", backend=fmt.lower())
    finally:
        scene.frame_start, scene.frame_end = original_range[:2]
        scene.frame_set(original_range[2])

    if "CANCELLED" in result:
        return ImportResult(False, f"导出 {fmt} 被取消", backend=fmt.lower())
    if not filepath.is_file():
        return ImportResult(
            False,
            f"导出声称成功但文件不存在：{filepath}",
            backend=fmt.lower(),
        )
    return ImportResult(True, f"已导出中转文件：{filepath.name}", backend=fmt.lower())


def import_transfer_file(filepath: Path, fmt: str) -> ImportResult:
    before_obj = set(bpy.data.objects)
    before_act = set(bpy.data.actions)
    fmt = fmt.upper()
    try:
        if fmt == "FBX" or filepath.suffix.lower() == ".fbx":
            if not deps.operator_exists(bpy.ops.import_scene, "fbx"):
                return ImportResult(False, "未找到 import_scene.fbx", backend="fbx")
            try:
                result = bpy.ops.import_scene.fbx(
                    filepath=str(filepath),
                    automatic_bone_orientation=False,
                    ignore_leaf_bones=False,
                    anim_offset=0.0,
                )
            except TypeError:
                result = bpy.ops.import_scene.fbx(filepath=str(filepath))
            backend = "fbx"
        else:
            if not deps.operator_exists(bpy.ops.import_scene, "gltf"):
                return ImportResult(False, "未找到 import_scene.gltf", backend="gltf")
            result = bpy.ops.import_scene.gltf(filepath=str(filepath))
            backend = "gltf"
    except Exception as exc:  # noqa: BLE001
        return ImportResult(False, f"导入中转文件失败：{exc}", backend=fmt.lower())

    if "CANCELLED" in result:
        return ImportResult(False, "导入中转文件被取消", backend=backend)

    new_objs = [o for o in bpy.data.objects if o not in before_obj]
    new_acts = [a for a in bpy.data.actions if a not in before_act]
    arms = [o for o in new_objs if o.type == "ARMATURE"]
    msg = (
        f"已导入 {filepath.name}（新物体 {len(new_objs)}，"
        f"Armature {len(arms)}，新 Action {len(new_acts)}）"
    )
    return ImportResult(True, msg, objects=new_objs, backend=backend)


def _delete_objects(objects):
    for obj in list(objects):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass


def transfer_animation(
    context,
    source_path: str,
    *,
    fmt_override: str = "SCENE",
    output_dir: str = "",
    target_armature: Optional[bpy.types.Object] = None,
    skeleton_hkx: str = "",
    keep_temp: bool = False,
) -> ImportResult:
    """
    Default workflow entry:
      - If source is FBX/GLTF: import and optionally copy Action to target
      - If source is HKX: external converter OR PyNifly→export→import→copy
    """
    try:
        source = ensure_file(
            source_path,
            tuple(HKX_EXTS | TRANSFER_EXTS),
        )
    except (FileNotFoundError, ValueError) as exc:
        return ImportResult(False, str(exc), backend="transfer")

    fmt = resolve_transfer_format(context, fmt_override)
    prefs = deps.get_addon_prefs(context)
    if prefs and prefs.set_scene_fps_30:
        context.scene.render.fps = 30

    target = target_armature or _find_armature(
        target_armature.name if target_armature else None
    )
    # Pointer may be passed explicitly; also accept scene prop resolved by caller.
    if target_armature is not None:
        target = target_armature

    suffix = source.suffix.lower()

    # --- Already an intermediate file ---
    if suffix in TRANSFER_EXTS:
        inferred = "FBX" if suffix == ".fbx" else "GLTF"
        result = import_transfer_file(source, inferred)
        if not result.ok:
            return result
        applied = _apply_to_target(result, target, source.stem)
        return ImportResult(
            applied.ok,
            f"{result.message}；{applied.message}",
            objects=result.objects,
            backend="transfer",
        )

    # --- HKX path ---
    out_dir = resolve_output_dir(context, output_dir, source)
    inter = intermediate_path(out_dir, source, fmt)

    # Optional external CLI
    if prefs and prefs.external_hkx_converter:
        ext = run_external_converter(context, source, inter, fmt)
        if not ext.ok:
            return ImportResult(
                False,
                ext.message
                + "。也可清空「外部转换器」以改用半自动（PyNifly→导出中转）。",
                backend="external",
            )
        result = import_transfer_file(inter, fmt)
        if not result.ok:
            return result
        applied = _apply_to_target(result, target, source.stem)
        return ImportResult(
            applied.ok,
            f"外部转换 + 导入完成。{applied.message} 中转文件：{inter}",
            objects=result.objects,
            backend="transfer",
        )

    # Semi-automatic: need PyNifly HKX
    if not deps.operator_exists(bpy.ops.import_scene, "pynifly_hkx"):
        return ImportResult(
            False,
            "半自动中转需要 PyNifly 的 import_scene.pynifly_hkx。"
            "请安装 https://github.com/BadDogSkyrim/PyNifly/releases"
            "（Windows；动画建议 Blender 4.4+），"
            "或提供已转换的 FBX/GLTF，或配置可用的外部转换器。",
            backend="missing",
        )

    # Ensure we have a working armature (prefer user target / existing skeleton)
    work_arm = target

    if work_arm is None:
        # Import skeleton first if provided
        if skeleton_hkx:
            sk = pynifly_bridge.import_hkx(context, skeleton_hkx, {})
            if not sk.ok:
                return ImportResult(
                    False,
                    f"中转前导入骨骼失败：{sk.message}",
                    backend="transfer",
                )
            work_arm = _find_armature()
        else:
            return ImportResult(
                False,
                "请指定「目标 Armature」，或先导入 skeleton.hkx，"
                "或在骨骼路径中填写 skeleton.hkx。",
                backend="transfer",
            )

    _activate(work_arm)
    before_actions = set(bpy.data.actions)

    anim_result = pynifly_bridge.import_hkx(
        context,
        str(source),
        {"reference_skel": skeleton_hkx} if skeleton_hkx else {},
    )
    if not anim_result.ok:
        return ImportResult(
            False,
            f"PyNifly 导入动作 HKX 失败：{anim_result.message}",
            backend="transfer",
        )

    # Re-find armature in case import created a new one
    work_arm = _find_armature(work_arm.name) or _find_armature()
    if work_arm is None:
        return ImportResult(False, "导入 HKX 后找不到 Armature", backend="transfer")

    action = _action_of(work_arm)
    if action is None:
        new_acts = [a for a in bpy.data.actions if a not in before_actions]
        if new_acts:
            if work_arm.animation_data is None:
                work_arm.animation_data_create()
            work_arm.animation_data.action = new_acts[-1]
            action = new_acts[-1]
    if action is None:
        return ImportResult(
            False,
            "HKX 已导入但没有产生 Action。请确认选中的是带动画的 HKX，"
            "且 Blender ≥ 4.4、PyNifly 版本支持动画。",
            backend="transfer",
        )

    export_res = export_armature_animation(work_arm, inter, fmt)
    if not export_res.ok:
        return export_res

    # Import intermediate into scene (creates a clean transfer armature/action)
    import_res = import_transfer_file(inter, fmt)
    if not import_res.ok:
        return import_res

    applied = _apply_to_target(import_res, target or work_arm, source.stem)
    if not applied.ok:
        return applied

    # Cleanup: remove newly imported duplicate armature if we copied onto target,
    # and optional temp from skeleton-only import — conservative: only extras
    # from the transfer re-import when target already existed.
    if target is not None and not keep_temp:
        for obj in list(import_res.objects):
            if obj.type == "ARMATURE" and obj != target and obj.name != target.name:
                _delete_objects([obj])

    msg = (
        f"中转完成（{fmt}）：{source.name} → {inter.name}。"
        f"{applied.message}"
        " 可在时间轴预览；原生 HKX 直导见「高级」面板。"
    )
    return ImportResult(True, msg, objects=[target or work_arm], backend="transfer")


def _bake_fbx_to_target(source, target, name):
    """FBX may change rest transforms; bake matching bones in armature space."""
    scene = bpy.context.scene
    action = source.animation_data.action
    start, end = floor(action.frame_range[0]), ceil(action.frame_range[1])
    matched = [bone for bone in target.pose.bones if bone.name in source.pose.bones]
    if not matched:
        raise ValueError("FBX 与目标骨骼没有匹配的骨名")
    copied = bpy.data.actions.new(name)
    target.animation_data_create()
    target.animation_data.action = copied
    original_frame = scene.frame_current
    try:
        for frame in range(start, end + 1):
            scene.frame_set(frame)
            transform = target.matrix_world.inverted() @ source.matrix_world
            matrices = {
                bone.name: transform @ source.pose.bones[bone.name].matrix
                for bone in matched
            }
            for bone in matched:
                parent = bone.parent
                parent_options = {}
                if parent is not None:
                    parent_options = {
                        "parent_matrix": matrices.get(parent.name, parent.matrix),
                        "parent_matrix_local": parent.bone.matrix_local,
                    }
                bone.rotation_mode = "QUATERNION"
                bone.matrix_basis = bone.bone.convert_local_to_pose(
                    matrices[bone.name], bone.bone.matrix_local,
                    invert=True, **parent_options,
                )
                for channel in ("location", "rotation_quaternion", "scale"):
                    bone.keyframe_insert(data_path=channel, frame=frame, group=bone.name)
    finally:
        scene.frame_set(original_frame)
    return copied


def _apply_to_target(
    import_result: ImportResult,
    target: Optional[bpy.types.Object],
    stem: str,
) -> ImportResult:
    if target is None:
        arms = [o for o in import_result.objects if o.type == "ARMATURE"]
        if arms:
            return ImportResult(
                True,
                f"已使用导入的 Armature「{arms[0].name}」（未指定目标）",
                backend="transfer",
            )
        return ImportResult(
            True,
            "已导入中转文件（未找到 Armature，也未指定目标）",
            backend="transfer",
        )

    # Prefer action from newly imported armature
    src_arm = None
    for obj in import_result.objects:
        if obj.type == "ARMATURE" and obj != target:
            src_arm = obj
            break
    if src_arm is None:
        for obj in import_result.objects:
            if obj.type == "ARMATURE":
                src_arm = obj
                break

    action = _action_of(src_arm) if src_arm else None
    if action is None and bpy.data.actions:
        # Fallback: newest action
        action = bpy.data.actions[-1]

    if action is None:
        return ImportResult(
            False,
            "中转文件没有可用 Action",
            backend="transfer",
        )

    if src_arm is target or (src_arm and src_arm.name == target.name):
        if target.animation_data is None:
            target.animation_data_create()
        target.animation_data.action = action
        return ImportResult(
            True,
            f"Action「{action.name}」已在目标「{target.name}」上",
            backend="transfer",
        )

    source_slot = getattr(src_arm.animation_data, "action_slot", None) if src_arm else None
    if import_result.backend == "fbx" and src_arm is not None:
        new_action = _bake_fbx_to_target(src_arm, target, f"{stem}_transfer")
    else:
        new_action = copy_action_by_bone_name(
            action, target, new_name=f"{stem}_transfer", source_slot=source_slot
        )
        if src_arm is not None:
            for bone in target.pose.bones:
                source_bone = src_arm.pose.bones.get(bone.name)
                if source_bone is not None:
                    bone.rotation_mode = source_bone.rotation_mode
    matched = sum(
        1
        for curves in _curve_collections(
            new_action, getattr(target.animation_data, "action_slot", None)
        )
        for fc in curves
        if fc.data_path.startswith("pose.bones[")
    )
    return ImportResult(
        True,
        f"已将 Action 套到「{target.name}」→「{new_action.name}」"
        f"（保留骨名匹配曲线，约 {matched} 条 FCurve）",
        backend="transfer",
    )
