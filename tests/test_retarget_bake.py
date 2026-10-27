# SPDX-License-Identifier: MIT
"""
Synthetic retarget regression for Skyrim SE Loader.

Run:
  blender -b -P tests/test_retarget_bake.py

Without Blender on PATH the script prints a skip message and exits 0.
When executed inside Blender it builds two simple armatures, bakes, and asserts.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


def _find_blender() -> str | None:
    import os
    import shutil

    for name in ("blender", "blender4", "blender5"):
        found = shutil.which(name)
        if found:
            return found
    # Common install hints (non-fatal)
    for candidate in (
        "/usr/bin/blender",
        "/snap/bin/blender",
        r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


def _running_inside_blender() -> bool:
    try:
        import bpy  # noqa: F401

        return True
    except ImportError:
        return False


def _addon_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_addon_on_path():
    root = str(_addon_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def build_scene(bpy):
    # Clean mesh/armature objects
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    def make_armature(name: str, bone_names: list[str]):
        arm_data = bpy.data.armatures.new(f"{name}_data")
        arm_obj = bpy.data.objects.new(name, arm_data)
        bpy.context.collection.objects.link(arm_obj)
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="EDIT")
        parent = None
        z = 0.0
        for bname in bone_names:
            eb = arm_data.edit_bones.new(bname)
            eb.head = (0.0, 0.0, z)
            eb.tail = (0.0, 0.0, z + 0.5)
            if parent is not None:
                eb.parent = parent
            parent = eb
            z += 0.5
        bpy.ops.object.mode_set(mode="OBJECT")
        return arm_obj

    bones = ["Root", "Spine", "Head"]
    source = make_armature("SrcArm", bones)
    target = make_armature("TgtArm", bones)

    # Animate source: rotate Spine over frames 1..10
    if source.animation_data is None:
        source.animation_data_create()
    action = bpy.data.actions.new("SrcWave")
    source.animation_data.action = action

    bpy.context.view_layer.objects.active = source
    bpy.ops.object.mode_set(mode="POSE")
    spine = source.pose.bones["Spine"]
    spine.rotation_mode = "QUATERNION"
    for frame, angle in ((1, 0.0), (5, math.radians(40)), (10, 0.0)):
        bpy.context.scene.frame_set(frame)
        spine.rotation_quaternion = (
            math.cos(angle / 2),
            0.0,
            math.sin(angle / 2),
            0.0,
        )
        spine.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene.frame_set(1)
    return source, target, action


def run_assertions(bpy, source, target, result):
    assert result.ok, result.message
    assert result.matched >= 3, result.message
    assert result.frames >= 2, result.message
    assert target.animation_data and target.animation_data.action

    new_action = target.animation_data.action
    # Evaluate mid frame — Spine should have non-identity rotation
    bpy.context.scene.frame_set(5)
    bpy.context.view_layer.update()
    tgt_spine = target.pose.bones["Spine"]
    # quaternion w near cos(20°) when angle=40° — just check not identity
    qw, qx, qy, qz = tgt_spine.rotation_quaternion
    nonzero = abs(qx) + abs(qy) + abs(qz)
    assert nonzero > 1e-4, (
        f"目标 Spine 在第 5 帧旋转仍接近单位四元数: {(qw, qx, qy, qz)}"
    )

    # Custom map path: rename target bone and retarget with map
    # (already validated name mode; also call guess_bone_map)
    from skyrim_se_loader.retarget.api import guess_bone_map

    mapping = guess_bone_map(source, target)
    assert mapping.get("Spine") == "Spine"
    print("OK", result.message)
    print("Action", new_action.name, "matched", result.matched, "frames", result.frames)


def main_inside_blender():
    import bpy

    _ensure_addon_on_path()
    from skyrim_se_loader.retarget.api import RetargetRequest, execute_retarget

    source, target, action = build_scene(bpy)
    req = RetargetRequest(
        source_armature=source.name,
        target_armature=target.name,
        action_name=action.name,
        mode="NAME",
        channels="LOC_ROT",
        overwrite=True,
        new_action_name="TgtWave",
    )
    result = execute_retarget(req)
    run_assertions(bpy, source, target, result)

    # Mode B: custom map with one renamed conceptual pair (same names still)
    req2 = RetargetRequest(
        source_armature=source.name,
        target_armature=target.name,
        action_name=action.name,
        mode="CUSTOM",
        bone_map={"Root": "Root", "Spine": "Spine", "Head": "Head"},
        channels="ROT",
        overwrite=True,
        new_action_name="TgtWaveCustom",
    )
    result2 = execute_retarget(req2)
    assert result2.ok, result2.message
    assert result2.matched == 3
    print("OK custom", result2.message)


def main():
    if _running_inside_blender():
        main_inside_blender()
        return 0

    blender = _find_blender()
    if blender is None:
        print(
            "SKIP: 本环境未找到 blender 可执行文件。"
            "请在已安装 Blender 的机器上运行：\n"
            "  blender -b -P tests/test_retarget_bake.py"
        )
        return 0

    import subprocess

    script = str(Path(__file__).resolve())
    proc = subprocess.run([blender, "-b", "-P", script], check=False)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
