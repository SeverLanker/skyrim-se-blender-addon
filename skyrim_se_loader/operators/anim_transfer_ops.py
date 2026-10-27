# SPDX-License-Identifier: MIT
"""FBX / glTF animation transfer operators (default anim workflow)."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.types import Operator

from ..importers import anim_transfer
from ..utils import deps
from ..utils.paths import ensure_dir


def _props(context):
    return context.scene.skyrim_se_loader


def _set_status(context, message: str):
    _props(context).last_status = message


def _resolve_out_dir(context) -> Path | None:
    props = _props(context)
    if props.anim_transfer_output_dir:
        return ensure_dir(props.anim_transfer_output_dir, create=True)
    prefs = deps.get_addon_prefs(context)
    if prefs and prefs.anim_transfer_output_dir:
        return ensure_dir(prefs.anim_transfer_output_dir, create=True)
    return None


class SKYRIMSE_OT_anim_transfer(Operator):
    bl_idname = "skyrimse.anim_transfer"
    bl_label = "动作中转导入（FBX/glTF）"
    bl_description = (
        "默认工作流：HKX 经 PyNifly 导入后导出 FBX/glTF，再套到目标骨骼；"
        "若源已是 FBX/GLB/GLTF 则直接导入。社区暂无通用免费 HKX→FBX CLI。"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        target = props.target_armature
        if target is None:
            active = context.view_layer.objects.active
            if active and active.type == "ARMATURE":
                target = active

        result = anim_transfer.transfer_animation(
            context,
            props.anim_source,
            fmt_override=props.anim_transfer_format,
            output_dir=props.anim_transfer_output_dir,
            target_armature=target,
            skeleton_hkx=props.skeleton_hkx,
            keep_temp=props.keep_transfer_temp,
        )
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message[:255])
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_export_transfer_only(Operator):
    bl_idname = "skyrimse.export_transfer_only"
    bl_label = "仅导出当前动作为中转文件"
    bl_description = "把当前选中 Armature 的 Action 导出为 FBX 或 glTF（不经 HKX）"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        arm = props.target_armature or context.view_layer.objects.active
        if arm is None or arm.type != "ARMATURE":
            msg = "请选中或指定带 Action 的目标 Armature"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        action = arm.animation_data.action if arm.animation_data else None
        if action is None:
            msg = "当前 Armature 没有 Action，请先导入动作"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        out_dir = _resolve_out_dir(context)
        if out_dir is None:
            msg = "请在侧栏或插件偏好填写「中转输出目录」"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        fmt = anim_transfer.resolve_transfer_format(
            context, props.anim_transfer_format
        )
        stem = Path(props.anim_source).stem if props.anim_source else action.name
        inter = anim_transfer.intermediate_path(out_dir, Path(stem), fmt)
        result = anim_transfer.export_armature_animation(arm, inter, fmt)
        if result.ok:
            _set_status(context, f"{result.message} → {inter}")
        else:
            _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message[:255])
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_transfer_file(Operator):
    bl_idname = "skyrimse.import_transfer_file"
    bl_label = "导入已有 FBX/glTF 动作"
    bl_description = "源文件已是中转格式时：导入并套到目标 Armature"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        if not props.anim_source:
            msg = "请选择 .fbx / .glb / .gltf 文件"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        result = anim_transfer.transfer_animation(
            context,
            props.anim_source,
            fmt_override=props.anim_transfer_format,
            output_dir=props.anim_transfer_output_dir,
            target_armature=props.target_armature,
            skeleton_hkx=props.skeleton_hkx,
            keep_temp=props.keep_transfer_temp,
        )
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message[:255])
        return {"FINISHED"} if result.ok else {"CANCELLED"}


CLASSES = (
    SKYRIMSE_OT_anim_transfer,
    SKYRIMSE_OT_export_transfer_only,
    SKYRIMSE_OT_import_transfer_file,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
