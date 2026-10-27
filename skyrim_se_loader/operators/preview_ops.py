# SPDX-License-Identifier: MIT
"""Animation preview helpers."""

from __future__ import annotations

import bpy
from bpy.types import Operator


def _set_status(context, message: str):
    context.scene.skyrim_se_loader.last_status = message


class SKYRIMSE_OT_setup_preview(Operator):
    bl_idname = "skyrimse.setup_preview"
    bl_label = "准备动作预览"
    bl_description = "将场景设为 30 FPS，选中 Armature，范围对齐当前 Action"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        props = scene.skyrim_se_loader
        scene.render.fps = 30

        arm = props.target_armature
        if arm is None:
            arm = context.view_layer.objects.active
        if arm is None or arm.type != "ARMATURE":
            arms = [o for o in scene.objects if o.type == "ARMATURE"]
            if not arms:
                msg = "场景中没有 Armature。请先完成步骤 2（导入骨骼）。"
                _set_status(context, msg)
                self.report({"ERROR"}, msg)
                return {"CANCELLED"}
            arm = arms[0]
        context.view_layer.objects.active = arm
        arm.select_set(True)

        action = None
        if arm.animation_data and arm.animation_data.action:
            action = arm.animation_data.action
        elif bpy.data.actions:
            action = bpy.data.actions[-1]
            if arm.animation_data is None:
                arm.animation_data_create()
            arm.animation_data.action = action

        if action is None:
            msg = (
                "没有可预览的 Action。"
                "请先用步骤 5「动作中转导入（FBX/glTF）」导入动作。"
            )
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}

        try:
            frame_start = int(action.frame_range[0])
            frame_end = int(action.frame_range[1])
        except Exception:
            frame_start, frame_end = 1, 30

        scene.frame_start = max(1, frame_start)
        scene.frame_end = max(scene.frame_start, frame_end)
        scene.frame_current = scene.frame_start

        if context.mode != "POSE":
            try:
                bpy.ops.object.mode_set(mode="POSE")
            except Exception:
                pass

        msg = (
            f"预览就绪：Action「{action.name}」"
            f" 帧 {scene.frame_start}-{scene.frame_end} @ {scene.render.fps}fps。"
            "按空格播放。"
        )
        _set_status(context, msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class SKYRIMSE_OT_list_actions(Operator):
    bl_idname = "skyrimse.list_actions"
    bl_label = "列出已导入 Action"
    bl_description = "在状态栏与控制台列出场景中的动作"

    def execute(self, context):
        names = [a.name for a in bpy.data.actions]
        if not names:
            msg = "尚无 Action — 请先做步骤 5 动作中转"
        else:
            msg = "Actions: " + ", ".join(names)
        _set_status(context, msg)
        print(msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


CLASSES = (
    SKYRIMSE_OT_setup_preview,
    SKYRIMSE_OT_list_actions,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
