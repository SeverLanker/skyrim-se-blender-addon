# SPDX-License-Identifier: MIT
"""Skeleton preset operators (Vanilla / XPMSE / Custom)."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.types import Operator

from ..adapters.base import ImportRequest
from ..adapters.registry import get as get_adapter
from ..utils import deps
from ..utils.paths import (
    SKELETON_PATH_HINTS,
    resolve_skeleton_candidate,
)


def _props(context):
    return context.scene.skyrim_se_loader


def _set_status(context, message: str):
    _props(context).last_status = message


class SKYRIMSE_OT_apply_skeleton_preset(Operator):
    bl_idname = "skyrimse.apply_skeleton_preset"
    bl_label = "应用为默认并导入"
    bl_description = (
        "按 Vanilla/XPMSE/自定义 + 性别解析 skeleton.hkx，"
        "写入侧栏路径与偏好默认骨骼，并尝试用 PyNifly 导入"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        prefs = deps.get_addon_prefs(context)
        path = resolve_skeleton_candidate(
            preset=props.skeleton_preset,
            gender=props.skeleton_gender,
            prefs=prefs,
            data_root=(prefs.data_root if prefs else "") or "",
        )
        if not path:
            hints = "；".join(SKELETON_PATH_HINTS)
            msg = (
                "无法解析骨骼路径。请在偏好填写 Vanilla/XPMSE 的 male/female HKX，"
                f"或设置 Data 目录。提示：{hints}"
            )
            _set_status(context, msg)
            self.report({"ERROR"}, msg[:255])
            return {"CANCELLED"}

        props.skeleton_hkx = path
        if prefs is not None:
            prefs.default_skeleton_hkx = path

        if not Path(path).is_file():
            msg = (
                f"已设为默认路径，但文件尚不存在：{path}。"
                "请确认已安装 XPMSE loose files 或已从 BA2 解出对应骨骼。"
            )
            _set_status(context, msg)
            self.report({"WARNING"}, msg[:255])
            return {"CANCELLED"}

        ad = get_adapter(props.game_id) or get_adapter("skyrim_se")
        result = ad.import_asset(
            context,
            ImportRequest("skeleton", path, {}),
        )
        if result.ok:
            arms = [o for o in result.objects if o.type == "ARMATURE"]
            if arms:
                props.target_armature = arms[-1]
            arms = [o for o in context.scene.objects if o.type == "ARMATURE"]
            if arms and props.target_armature is None:
                props.target_armature = arms[-1]
            label = {
                "VANILLA": "Vanilla",
                "XPMSE": "XPMSE",
                "CUSTOM": "自定义",
            }.get(props.skeleton_preset, props.skeleton_preset)
            note = (
                f"已应用 {label}/{props.skeleton_gender} 并导入：{Path(path).name}。"
                "多数 SE 动画在 XPMSE 上可用；目标缺骨时导入/Retarget 会跳过。"
            )
            _set_status(context, note)
            self.report({"INFO"}, note[:255])
            return {"FINISHED"}

        _set_status(context, result.message)
        self.report({"ERROR"}, result.message[:255])
        return {"CANCELLED"}


class SKYRIMSE_OT_fill_skeleton_from_preset(Operator):
    bl_idname = "skyrimse.fill_skeleton_from_preset"
    bl_label = "仅填入路径"
    bl_description = "按预设+性别填写侧栏骨骼路径，不导入"

    def execute(self, context):
        props = _props(context)
        prefs = deps.get_addon_prefs(context)
        path = resolve_skeleton_candidate(
            preset=props.skeleton_preset,
            gender=props.skeleton_gender,
            prefs=prefs,
            data_root=(prefs.data_root if prefs else "") or "",
        )
        if not path:
            msg = "无法解析路径。请在偏好配置 Vanilla/XPMSE HKX 或 Data 目录。"
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}
        props.skeleton_hkx = path
        exists = Path(path).is_file()
        msg = f"已填入：{path}" + ("" if exists else "（文件尚不存在）")
        _set_status(context, msg)
        self.report({"INFO"} if exists else {"WARNING"}, msg[:255])
        return {"FINISHED"}


CLASSES = (
    SKYRIMSE_OT_apply_skeleton_preset,
    SKYRIMSE_OT_fill_skeleton_from_preset,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
