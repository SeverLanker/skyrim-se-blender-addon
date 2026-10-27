# SPDX-License-Identifier: MIT
"""Retarget operators — bake Action from one Armature onto another."""

from __future__ import annotations

import bpy
from bpy.types import Operator, UIList

from ..retarget.api import (
    RetargetRequest,
    execute_retarget,
    export_mapping_json,
    guess_bone_map,
    import_mapping_json,
    mapping_from_collection,
)


def _set_status(context, message: str):
    props = context.scene.skyrim_se_loader
    props.last_status = message
    props.retarget_report = message


def _fill_collection(collection, mapping: dict[str, str]):
    collection.clear()
    for src, dst in sorted(mapping.items(), key=lambda kv: kv[0].casefold()):
        item = collection.add()
        item.source_bone = src
        item.target_bone = dst


class SKYRIMSE_UL_bone_map(UIList):
    bl_idname = "SKYRIMSE_UL_bone_map"

    def draw_item(
        self,
        _context,
        layout,
        _data,
        item,
        _icon,
        _active_data,
        _active_propname,
        _index,
    ):
        row = layout.row(align=True)
        row.prop(item, "source_bone", text="", emboss=False)
        row.label(text="→")
        row.prop(item, "target_bone", text="", emboss=False)


class SKYRIMSE_OT_retarget_execute(Operator):
    bl_idname = "skyrimse.retarget_execute"
    bl_label = "执行 Retarget"
    bl_description = (
        "将源 Action 按同名或自定义映射烘焙到目标 Armature 的局部空间"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        source = props.retarget_source
        target = props.retarget_target

        if source is None or source.type != "ARMATURE":
            msg = "请指定源 Armature"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        if target is None or target.type != "ARMATURE":
            msg = "请指定目标 Armature"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        bone_map = {}
        if props.retarget_mode == "CUSTOM":
            bone_map = mapping_from_collection(props.retarget_bone_map)

        req = RetargetRequest(
            source_armature=source.name,
            target_armature=target.name,
            action_name=(props.retarget_action or "").strip(),
            bone_map=bone_map,
            mode=props.retarget_mode,
            channels=props.retarget_channels,
            overwrite=props.retarget_overwrite,
            new_action_name=(props.retarget_new_action_name or "").strip(),
            copy_root_motion=props.retarget_copy_root_motion,
        )
        result = execute_retarget(req)
        _set_status(context, result.message)
        if not result.ok:
            self.report({"ERROR"}, result.message)
            return {"CANCELLED"}

        # Keep transfer target pointer in sync when useful.
        if props.target_armature is None:
            props.target_armature = target

        self.report({"INFO"}, result.message)
        return {"FINISHED"}


class SKYRIMSE_OT_retarget_guess_map(Operator):
    bl_idname = "skyrimse.retarget_guess_map"
    bl_label = "按名称猜测映射"
    bl_description = "用源/目标骨名（精确 + 忽略大小写）填充映射表"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        source = props.retarget_source
        target = props.retarget_target
        if source is None or target is None:
            msg = "请先指定源与目标 Armature"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        mapping = guess_bone_map(source, target)
        _fill_collection(props.retarget_bone_map, mapping)
        props.retarget_bone_map_index = 0
        msg = f"已猜测映射 {len(mapping)} 条（源 {len(source.data.bones)} / 目标 {len(target.data.bones)}）"
        _set_status(context, msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class SKYRIMSE_OT_retarget_clear_map(Operator):
    bl_idname = "skyrimse.retarget_clear_map"
    bl_label = "清空映射"
    bl_description = "清空自定义骨名映射表"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        props.retarget_bone_map.clear()
        props.retarget_bone_map_index = 0
        msg = "映射表已清空"
        _set_status(context, msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class SKYRIMSE_OT_retarget_add_map_row(Operator):
    bl_idname = "skyrimse.retarget_add_map_row"
    bl_label = "添加映射行"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        props.retarget_bone_map.add()
        props.retarget_bone_map_index = len(props.retarget_bone_map) - 1
        return {"FINISHED"}


class SKYRIMSE_OT_retarget_remove_map_row(Operator):
    bl_idname = "skyrimse.retarget_remove_map_row"
    bl_label = "删除映射行"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        idx = props.retarget_bone_map_index
        if 0 <= idx < len(props.retarget_bone_map):
            props.retarget_bone_map.remove(idx)
            props.retarget_bone_map_index = max(0, idx - 1)
        return {"FINISHED"}


class SKYRIMSE_OT_retarget_export_map(Operator):
    bl_idname = "skyrimse.retarget_export_map"
    bl_label = "导出映射 JSON"
    bl_description = "把当前映射表写到「映射 JSON」路径"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        path = (props.retarget_map_json or "").strip()
        if not path:
            msg = "请先填写映射 JSON 路径"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        mapping = mapping_from_collection(props.retarget_bone_map)
        if not mapping and props.retarget_source and props.retarget_target:
            mapping = guess_bone_map(props.retarget_source, props.retarget_target)
        try:
            out = export_mapping_json(mapping, path)
        except Exception as exc:  # noqa: BLE001
            msg = f"导出失败：{exc}"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        msg = f"已导出映射 {len(mapping)} 条 → {out}"
        _set_status(context, msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class SKYRIMSE_OT_retarget_import_map(Operator):
    bl_idname = "skyrimse.retarget_import_map"
    bl_label = "导入映射 JSON"
    bl_description = "从「映射 JSON」路径读入映射表"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        path = (props.retarget_map_json or "").strip()
        if not path:
            msg = "请先填写映射 JSON 路径"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        try:
            mapping = import_mapping_json(path)
        except Exception as exc:  # noqa: BLE001
            msg = f"导入失败：{exc}"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _fill_collection(props.retarget_bone_map, mapping)
        props.retarget_mode = "CUSTOM"
        props.retarget_bone_map_index = 0
        msg = f"已导入映射 {len(mapping)} 条"
        _set_status(context, msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


# Back-compat alias name (old stub id) → run real execute if props filled,
# otherwise try Active/selected convention.
class SKYRIMSE_OT_retarget_stub(Operator):
    bl_idname = "skyrimse.retarget_stub"
    bl_label = "Retarget（兼容入口）"
    bl_description = "兼容旧按钮；优先用侧栏源/目标，否则 Active=源、加选=目标"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.skyrim_se_loader
        if props.retarget_source is None:
            src = context.view_layer.objects.active
            if src and src.type == "ARMATURE":
                props.retarget_source = src
        if props.retarget_target is None:
            src = props.retarget_source
            for obj in context.selected_objects:
                if obj.type == "ARMATURE" and obj != src:
                    props.retarget_target = obj
                    break
        return bpy.ops.skyrimse.retarget_execute()


CLASSES = (
    SKYRIMSE_UL_bone_map,
    SKYRIMSE_OT_retarget_execute,
    SKYRIMSE_OT_retarget_guess_map,
    SKYRIMSE_OT_retarget_clear_map,
    SKYRIMSE_OT_retarget_add_map_row,
    SKYRIMSE_OT_retarget_remove_map_row,
    SKYRIMSE_OT_retarget_export_map,
    SKYRIMSE_OT_retarget_import_map,
    SKYRIMSE_OT_retarget_stub,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
