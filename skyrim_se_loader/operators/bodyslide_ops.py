# SPDX-License-Identifier: MIT
"""BodySlide build / preset / TRI operators."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.types import Operator

from ..adapters.base import ImportRequest
from ..adapters.registry import get as get_adapter
from ..importers import pynifly_bridge
from ..utils import bodyslide, deps


def _props(context):
    return context.scene.skyrim_se_loader


def _set_status(context, message: str):
    props = _props(context)
    props.last_status = message
    props.bodyslide_report = message


def _resolve_preset(context):
    props = _props(context)
    prefs = deps.get_addon_prefs(context)
    # Prefer explicit XML (+ optional name), then name-only search
    key = ""
    xml = (props.bodyslide_preset_xml or "").strip()
    name = (props.bodyslide_preset_name or "").strip()
    if xml and name:
        key = f"{xml}?{name}"
    elif xml:
        key = xml
    elif name:
        key = name
    if not key:
        return None, "请选择/填写 BodySlide 预设名或预设 XML。"
    preset = bodyslide.find_preset(key, prefs=prefs)
    if preset is None:
        return None, f"找不到预设：{key}。请确认 BodySlide 数据目录下有 SliderPresets。"
    return preset, ""


class SKYRIMSE_OT_bodyslide_refresh_presets(Operator):
    bl_idname = "skyrimse.bodyslide_refresh_presets"
    bl_label = "刷新预设列表"
    bl_description = "重新扫描 BodySlide 数据目录下的 SliderPresets/*.xml"

    def execute(self, context):
        prefs = deps.get_addon_prefs(context)
        names = bodyslide.list_preset_names(prefs=prefs)
        folder = bodyslide.slider_presets_dir(prefs=prefs)
        msg = (
            f"已扫描到 {len(names)} 个预设"
            + (f"（{folder}）" if folder else "（未配置数据目录）")
        )
        _set_status(context, msg)
        self.report({"INFO"}, msg[:255])
        return {"FINISHED"}


class SKYRIMSE_OT_bodyslide_build(Operator):
    bl_idname = "skyrimse.bodyslide_build"
    bl_label = "用 BodySlide 构建"
    bl_description = (
        "调用 BodySlide CLI："
        "--groupbuild / --build / --targetdir / --preset / --trimorphs"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = _props(context)
        prefs = deps.get_addon_prefs(context)
        preset_arg = (props.bodyslide_preset_name or "").strip()
        xml = (props.bodyslide_preset_xml or "").strip()
        # Official CLI accepts preset name or XML path (optionally path?name)
        if xml and preset_arg:
            if xml.lower().endswith(".xml"):
                preset_arg = f"{xml}?{preset_arg}"
        elif xml and not preset_arg:
            preset_arg = xml

        result = bodyslide.run_bodyslide_build(
            groups=props.bodyslide_group,
            outfits=props.bodyslide_outfit,
            target_dir=props.bodyslide_output_dir,
            preset=preset_arg,
            trimorphs=props.bodyslide_trimorphs,
            prefs=prefs,
        )
        if result.command:
            print("[BodySlide cmd]", " ".join(result.command))
        _set_status(context, result.message)
        if not result.ok:
            self.report({"ERROR"}, result.message[:255])
            return {"CANCELLED"}

        if result.nif_candidates and not props.bodyslide_built_nif:
            props.bodyslide_built_nif = result.nif_candidates[0]
        self.report({"INFO"}, result.message[:255])
        return {"FINISHED"}


class SKYRIMSE_OT_bodyslide_import_built_nif(Operator):
    bl_idname = "skyrimse.bodyslide_import_built_nif"
    bl_label = "导入构建结果 NIF"
    bl_description = "用现有 PyNifly 桥接导入「构建结果 NIF」路径"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        path = (props.bodyslide_built_nif or "").strip()
        if not path:
            # Try newest under output dir
            cands = bodyslide.find_recent_nifs(props.bodyslide_output_dir)
            if cands:
                path = cands[0]
                props.bodyslide_built_nif = path
        if not path:
            msg = "请填写构建结果 NIF，或先成功构建到输出目录。"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        ad = get_adapter(props.game_id) or get_adapter("skyrim_se")
        result = ad.import_asset(
            context,
            ImportRequest(
                "body",
                path,
                {
                    "import_collisions": props.import_collisions,
                    "import_tris": props.import_tris,
                },
            ),
        )
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message[:255])
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_bodyslide_apply_shapekeys(Operator):
    bl_idname = "skyrimse.bodyslide_apply_shapekeys"
    bl_label = "对当前 Mesh 应用预设到 Shape Keys"
    bl_description = (
        "解析预设 XML，按滑条名匹配 Shape Keys（值÷100）。"
        "近似预览，不等于完整 OSD 构建"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        preset, err = _resolve_preset(context)
        if preset is None:
            _set_status(context, err)
            self.report({"ERROR"}, err[:255])
            return {"CANCELLED"}

        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            # Prefer selected mesh
            meshes = [o for o in context.selected_objects if o.type == "MESH"]
            obj = meshes[0] if meshes else None
        props = _props(context)
        matched, unmatched, msg = bodyslide.apply_preset_to_mesh_shapekeys(
            obj,
            preset,
            prefer_size=props.bodyslide_shapekey_size,
        )
        _set_status(context, msg)
        level = {"INFO"} if matched else {"WARNING"}
        self.report(level, msg[:255])
        print("[BodySlide ShapeKeys]", msg)
        if unmatched:
            print("  unmatched:", ", ".join(unmatched[:40]))
        return {"FINISHED"} if matched else {"CANCELLED"}


class SKYRIMSE_OT_bodyslide_import_tri(Operator):
    bl_idname = "skyrimse.bodyslide_import_tri"
    bl_label = "导入 BodySlide TRI"
    bl_description = "调用 PyNifly import_scene.pyniflytri 导入形态键"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        path = (props.bodyslide_tri_path or "").strip()
        if not path:
            msg = "请选择 .tri 文件。"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        result = pynifly_bridge.import_tri(context, path, {})
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message[:255])
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_bodyslide_pick_newest_nif(Operator):
    bl_idname = "skyrimse.bodyslide_pick_newest_nif"
    bl_label = "选用输出目录最新 NIF"
    bl_description = "在构建输出目录中选最近修改的 .nif 填入「构建结果 NIF」"

    def execute(self, context):
        props = _props(context)
        cands = bodyslide.find_recent_nifs(props.bodyslide_output_dir, limit=1)
        if not cands:
            msg = "输出目录下未找到 .nif。请先构建或检查 --targetdir。"
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}
        props.bodyslide_built_nif = cands[0]
        msg = f"已选用：{cands[0]}"
        _set_status(context, msg)
        self.report({"INFO"}, msg[:255])
        return {"FINISHED"}




class SKYRIMSE_OT_bodyslide_fill_hands_feet(Operator):
    bl_idname = "skyrimse.bodyslide_fill_hands_feet"
    bl_label = "从构建目录填入手脚路径"
    bl_description = (
        "在 BodySlide 构建输出目录中查找 femalehands_1 / femalefeet_1 等常见 NIF，"
        "填入侧栏「手/脚」路径（不强制）"
    )

    def execute(self, context):
        props = _props(context)
        root = (props.bodyslide_output_dir or "").strip()
        if not root:
            msg = "请先填写 BodySlide「构建输出目录」。"
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}
        prefer_female = props.skeleton_gender == "female"
        found = bodyslide.find_hands_feet_nifs(root, prefer_female=prefer_female)
        if not found:
            msg = (
                f"在 {root} 下未找到 hands/feet 常见 NIF"
                "（femalehands_1.nif / femalefeet_1.nif 等）。"
            )
            _set_status(context, msg)
            self.report({"WARNING"}, msg[:255])
            return {"CANCELLED"}
        parts = []
        if "hands" in found:
            props.hands_nif = found["hands"]
            parts.append("手")
        if "feet" in found:
            props.feet_nif = found["feet"]
            parts.append("脚")
        msg = "已填入：" + "、".join(parts) + " → " + "；".join(
            f"{k}={v}" for k, v in found.items()
        )
        _set_status(context, msg)
        self.report({"INFO"}, msg[:255])
        return {"FINISHED"}


class SKYRIMSE_OT_bodyslide_help(Operator):
    bl_idname = "skyrimse.bodyslide_help"
    bl_label = "BodySlide 说明"

    def execute(self, context):
        text = bodyslide.missing_bodyslide_help()
        print(text)
        _set_status(context, "已在系统控制台打印 BodySlide 说明")
        self.report({"INFO"}, "见对话框 / 控制台")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        for line in bodyslide.missing_bodyslide_help().splitlines():
            self.layout.label(text=line)


CLASSES = (
    SKYRIMSE_OT_bodyslide_refresh_presets,
    SKYRIMSE_OT_bodyslide_build,
    SKYRIMSE_OT_bodyslide_import_built_nif,
    SKYRIMSE_OT_bodyslide_apply_shapekeys,
    SKYRIMSE_OT_bodyslide_import_tri,
    SKYRIMSE_OT_bodyslide_pick_newest_nif,
    SKYRIMSE_OT_bodyslide_fill_hands_feet,
    SKYRIMSE_OT_bodyslide_help,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
