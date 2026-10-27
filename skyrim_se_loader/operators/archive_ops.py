# SPDX-License-Identifier: MIT
"""BSArch unpack operators."""

from __future__ import annotations

import bpy
from bpy.types import Operator

from ..utils import deps
from ..utils.bsarch import (
    BAE_DOWNLOAD,
    BSARCH_DOWNLOAD,
    missing_bsarch_help,
    unpack_archive,
)


def _props(context):
    return context.scene.skyrim_se_loader


def _set_status(context, message: str):
    _props(context).last_status = message


class SKYRIMSE_OT_unpack_archive(Operator):
    bl_idname = "skyrimse.unpack_archive"
    bl_label = "用 BSArch 解包"
    bl_description = (
        "调用 BSArch.exe unpack <档案> <输出目录> [-mt:yes|no]。"
        "需在偏好中配置 BSArch 路径。"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = _props(context)
        prefs = deps.get_addon_prefs(context)
        result = unpack_archive(
            props.archive_path,
            props.unpack_output_dir,
            prefs=prefs,
        )
        _set_status(context, result.message)
        if not result.ok:
            self.report({"ERROR"}, result.message[:255])
            print(result.message)
            if result.command:
                print("[BSArch cmd]", " ".join(result.command))
            return {"CANCELLED"}

        # Optionally write Data root preference
        if prefs and prefs.set_data_root_after_unpack and props.unpack_output_dir:
            prefs.data_root = props.unpack_output_dir
            _set_status(
                context,
                result.message + "；已写入偏好「Data 目录」。",
            )

        self.report({"INFO"}, _props(context).last_status[:255])
        if result.command:
            print("[BSArch cmd]", " ".join(result.command))
        return {"FINISHED"}


class SKYRIMSE_OT_bsarch_help(Operator):
    bl_idname = "skyrimse.bsarch_help"
    bl_label = "BSArch 配置说明"

    def execute(self, context):
        text = missing_bsarch_help()
        print(text)
        _set_status(context, "已在系统控制台打印 BSArch 配置说明")
        self.report({"INFO"}, "见对话框 / 控制台")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        for line in missing_bsarch_help().splitlines():
            self.layout.label(text=line)


class SKYRIMSE_OT_open_bsarch_url(Operator):
    bl_idname = "skyrimse.open_bsarch_url"
    bl_label = "打开 BSArch 下载页"

    def execute(self, context):
        bpy.ops.wm.url_open(url=BSARCH_DOWNLOAD)
        return {"FINISHED"}


class SKYRIMSE_OT_open_bae_url(Operator):
    bl_idname = "skyrimse.open_bae_url"
    bl_label = "打开 BAE 下载页"

    def execute(self, context):
        bpy.ops.wm.url_open(url=BAE_DOWNLOAD)
        return {"FINISHED"}


CLASSES = (
    SKYRIMSE_OT_unpack_archive,
    SKYRIMSE_OT_bsarch_help,
    SKYRIMSE_OT_open_bsarch_url,
    SKYRIMSE_OT_open_bae_url,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
