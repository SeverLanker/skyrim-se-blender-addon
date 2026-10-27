# SPDX-License-Identifier: MIT
"""View3D sidebar panels (v0.7 layout).

Tree (parents registered before children):
  SKYRIMSE_PT_main            Skyrim SE Loader  — compact status bar
    SKYRIMSE_PT_character     角色
      SKYRIMSE_PT_npc         NPC / 种族外观（快速加载）
      SKYRIMSE_PT_mesh        手动部件
      SKYRIMSE_PT_skin        皮肤贴图           (closed)
      SKYRIMSE_PT_chargen     捏脸 / CharGen      (closed)
      SKYRIMSE_PT_bodyslide   BodySlide 身形      (closed)
    SKYRIMSE_PT_skeleton      骨架
    SKYRIMSE_PT_anim          动作
      SKYRIMSE_PT_anim_transfer 导入 / 中转
      SKYRIMSE_PT_preview     预览
      SKYRIMSE_PT_retarget    Retarget           (closed)
    SKYRIMSE_PT_tools         工具               (closed)
      SKYRIMSE_PT_unpack      BSArch 解包
      SKYRIMSE_PT_help        说明               (closed)
"""

from __future__ import annotations

import os

import bpy
from bpy.types import Operator, Panel

from ..adapters.registry import get as get_adapter
from ..utils import deps

ADDON_MODULE = __package__.rsplit(".", 1)[0] if __package__ else "skyrim_se_loader"


# ----------------------------------------------------------------- helpers
def _ok(cond):
    return "CHECKMARK" if cond else "ERROR"


def _exists(path):
    try:
        return bool(path) and os.path.exists(bpy.path.abspath(path))
    except Exception:  # noqa: BLE001
        return False


def data_dir(context):
    """Scene override (npc_game_data) first, then preferences.data_root."""
    props = context.scene.skyrim_se_loader
    prefs = deps.get_addon_prefs(context)
    p = getattr(props, "npc_game_data", "") or (getattr(prefs, "data_root", "") if prefs else "")
    return p


def _wrap(col, text, width=44, icon_first="NONE", alert=False):
    for line in (text or "").splitlines():
        miss = line.startswith("[缺失]") or line.startswith("读取失败") or line.startswith("未找到")
        sub = col.row()
        sub.alert = alert or miss
        for i in range(0, max(len(line), 1), width):
            sub.label(text=line[i : i + width], icon=("ERROR" if miss else icon_first) if i == 0 else "NONE")
            sub = col.row()
            sub.alert = alert or miss


def _big(layout, op, scale=1.5, enabled=True, reason="", **kw):
    col = layout.column()
    col.scale_y = scale
    col.enabled = enabled
    col.operator(op, **kw)
    if not enabled and reason:
        r = layout.row()
        r.alert = True
        r.label(text=reason, icon="INFO")


class SKYRIMSE_OT_open_prefs(Operator):
    bl_idname = "skyrimse.open_prefs"
    bl_label = "打开插件偏好设置"
    bl_description = "在偏好设置中定位本插件（路径都在这里配置）"

    def execute(self, context):
        try:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
            bpy.ops.preferences.addon_show(module=ADDON_MODULE)
        except Exception as exc:  # noqa: BLE001
            self.report({"WARNING"}, f"请手动打开 编辑 > 偏好设置 > 插件：{exc}")
        return {"FINISHED"}


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Skyrim SE"


# ----------------------------------------------------------------- root
class SKYRIMSE_PT_main(_Base, Panel):
    bl_label = "Skyrim SE Loader"
    bl_idname = "SKYRIMSE_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        prefs = deps.get_addon_prefs(context)
        st = deps.pynifly_status()
        bs = deps.bsarch_status(prefs)
        bd = deps.bodyslide_status(prefs)
        dd = data_dir(context)
        dd_ok = _exists(dd)
        arm = props.target_armature

        box = layout.box()
        grid = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        grid.label(text="PyNifly", icon=_ok(st.available))
        grid.label(text="BSArch", icon=_ok(bs.available))
        grid.label(text="BodySlide", icon=_ok(bd.available))
        grid.label(text="Data 目录", icon=_ok(dd_ok))
        row = box.row()
        row.label(text=f"骨架：{arm.name}" if arm else "骨架：未选择", icon="OUTLINER_OB_ARMATURE" if arm else "ERROR")
        if not st.available:
            box.label(text=st.message[:60], icon="INFO")
        row = box.row(align=True)
        row.operator("skyrimse.refresh_deps", text="刷新", icon="FILE_REFRESH")
        if not (bs.available and bd.available and dd_ok):
            row.operator("skyrimse.open_prefs", text="设置路径", icon="PREFERENCES")
        else:
            row.operator("skyrimse.open_prefs", text="", icon="PREFERENCES")
        if not st.available:
            row = box.row(align=True)
            row.operator("skyrimse.show_missing_help", text="PyNifly 说明", icon="HELP")
            row.operator("wm.url_open", text="下载", icon="URL").url = (
                "https://github.com/BadDogSkyrim/PyNifly/releases"
            )
        layout.prop(props, "game_id", text="游戏")
        if props.last_status:
            r = layout.row()
            r.label(text=props.last_status[:70], icon="INFO")


# ----------------------------------------------------------------- 角色
class SKYRIMSE_PT_character(_Base, Panel):
    bl_label = "角色"
    bl_idname = "SKYRIMSE_PT_character"
    bl_parent_id = "SKYRIMSE_PT_main"

    def draw_header(self, context):
        self.layout.label(icon="USER")

    def draw(self, context):
        self.layout.prop(context.scene.skyrim_se_loader, "target_armature", text="目标骨架")


class SKYRIMSE_PT_npc(_Base, Panel):
    bl_label = "NPC / 种族外观"
    bl_idname = "SKYRIMSE_PT_npc"
    bl_parent_id = "SKYRIMSE_PT_character"

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        dd = data_dir(context)
        if not _exists(dd) and not props.npc_mo2_profile and not props.npc_manual_plugins:
            r = layout.row(align=True)
            r.alert = True
            r.label(text="未设置游戏 Data 目录", icon="ERROR")
            r.operator("skyrimse.open_prefs", text="", icon="PREFERENCES")
        row = layout.row(align=True)
        row.operator("skyrimse.npc_index", text="读取插件", icon="FILE_REFRESH")
        row.prop(props, "npc_show_sources", text="", icon="FILE_FOLDER")
        if props.npc_show_sources:
            b = layout.box()
            b.label(text="本场景覆盖（留空用偏好）", icon="FILE_FOLDER")
            b.prop(props, "npc_game_data")
            b.prop(props, "npc_mo2_profile")
            b.prop(props, "npc_manual_plugins")
            b.prop(props, "npc_extract_archives")
        if props.npc_index_report:
            first = props.npc_index_report.splitlines()[-1]
            r = layout.row()
            r.alert = "失败" in props.npc_index_report or "未找到" in props.npc_index_report
            r.label(text=first[:60], icon="ERROR" if r.alert else "INFO")

        row = layout.row(align=True)
        row.prop(props, "npc_search", text="", icon="VIEWZOOM")
        row.operator("skyrimse.npc_search", text="搜索")
        layout.template_list("SKYRIMSE_UL_npcs", "", props, "npc_results", props, "npc_results_index", rows=6)
        has = 0 <= props.npc_results_index < len(props.npc_results)
        _big(layout, "skyrimse.npc_load", 1.6, enabled=has,
             reason="先读取插件并选中一个 NPC", text="加载此 NPC", icon="IMPORT")
        if props.npc_report:
            missing = sum(1 for l in props.npc_report.splitlines() if l.startswith("[缺失]"))
            hdr = layout.row()
            hdr.alert = missing > 0
            hdr.prop(props, "npc_show_report", emboss=False,
                     icon="DOWNARROW_HLT" if props.npc_show_report else "RIGHTARROW",
                     text=f"加载报告（缺失 {missing}）" if missing else "加载报告")
            if props.npc_show_report:
                _wrap(layout.box().column(align=True), props.npc_report, 48)


_PARTS = (
    ("身体", "body_nif", "skyrimse.import_body", "MESH_DATA"),
    ("手", "hands_nif", "skyrimse.import_hands", "MESH_DATA"),
    ("脚", "feet_nif", "skyrimse.import_feet", "MESH_DATA"),
    ("头", "head_nif", "skyrimse.import_head", "USER"),
    ("头发", "hair_nif", "skyrimse.import_hair", "CURVES_DATA"),
    ("眉毛", "brows_nif", "skyrimse.import_brows", "CURVES_DATA"),
    ("眼睛", "eyes_nif", "skyrimse.import_eyes", "HIDE_OFF"),
)


class SKYRIMSE_PT_mesh(_Base, Panel):
    bl_label = "手动部件"
    bl_idname = "SKYRIMSE_PT_mesh"
    bl_parent_id = "SKYRIMSE_PT_character"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        col = layout.column(align=True)
        filled = 0
        for label, attr, op, icon in _PARTS:
            val = getattr(props, attr)
            filled += bool(val)
            row = col.row(align=True)
            row.label(text="", icon="CHECKBOX_HLT" if val else "CHECKBOX_DEHLT")
            sp = row.split(factor=0.2, align=True)
            sp.label(text=label, icon=icon)
            r2 = sp.row(align=True)
            r2.prop(props, attr, text="")
            sub = r2.row(align=True)
            sub.enabled = bool(val)
            sub.operator(op, text="", icon="IMPORT")
        layout.operator("skyrimse.bodyslide_fill_hands_feet", text="从 BodySlide 构建目录填入手脚", icon="FILE_FOLDER")

        b = layout.box()
        b.label(text=f"附加部件（{len(props.extra_parts)}）", icon="ADD")
        row = b.row()
        row.template_list("SKYRIMSE_UL_extra_parts", "", props, "extra_parts", props, "extra_parts_index", rows=2)
        c = row.column(align=True)
        c.operator("skyrimse.extra_part_add", icon="ADD", text="")
        c.operator("skyrimse.extra_part_remove", icon="REMOVE", text="")
        b.operator("skyrimse.import_extra_parts", text="只导入附加部件", icon="IMPORT")

        row = layout.row(align=True)
        row.prop(props, "import_tris")
        row.prop(props, "import_collisions")
        _big(layout, "skyrimse.import_all_parts", 1.6, enabled=filled > 0 or len(props.extra_parts) > 0,
             reason="至少填一个部件路径", text=f"一键导入已填部件（{filled}）", icon="IMPORT")


class SKYRIMSE_PT_skin(_Base, Panel):
    bl_label = "皮肤贴图"
    bl_idname = "SKYRIMSE_PT_skin"
    bl_parent_id = "SKYRIMSE_PT_character"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        layout.prop(props, "skin_dds")
        layout.prop(props, "texture_slot")
        sel = any(o.type == "MESH" for o in context.selected_objects)
        _big(layout, "skyrimse.import_skin", 1.3, enabled=sel and bool(props.skin_dds),
             reason="先选中 Mesh 并选择 DDS", icon="TEXTURE")


class SKYRIMSE_PT_chargen(_Base, Panel):
    bl_label = "捏脸 / CharGen"
    bl_idname = "SKYRIMSE_PT_chargen"
    bl_parent_id = "SKYRIMSE_PT_character"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        b = layout.box()
        b.label(text="头雕包（SKSE/Plugins/CharGen）", icon="USER")
        b.prop(props, "chargen_nif")
        row = b.row(align=True)
        row.prop(props, "chargen_face_dds")
        row.operator("skyrimse.guess_chargen_dds", text="", icon="VIEWZOOM")
        _big(b, "skyrimse.import_chargen_pack", 1.4, enabled=bool(props.chargen_nif),
             reason="选择 CharGen 头 NIF", icon="IMPORT")

        b = layout.box()
        b.label(text="RaceMenu .jslot（摘要 / 近似）", icon="TEXT")
        b.prop(props, "chargen_jslot")
        r = b.row()
        r.enabled = bool(props.chargen_jslot)
        r.operator("skyrimse.parse_jslot", icon="FILE_TEXT")
        if props.chargen_jslot_report:
            _wrap(b.box().column(align=True), props.chargen_jslot_report, 42)
        b.prop(props, "chargen_apply_face_custom")
        b.prop(props, "chargen_shapekey_json")
        c = b.column(align=True)
        c.operator("skyrimse.export_jslot_shapekeys", icon="EXPORT")
        c.operator("skyrimse.apply_jslot_shapekeys", icon="SHAPEKEY_DATA")
        layout.label(text="jslot 不能还原 sculpt/tint；以头 NIF+DDS 为准", icon="INFO")


class SKYRIMSE_PT_bodyslide(_Base, Panel):
    bl_label = "BodySlide 身形"
    bl_idname = "SKYRIMSE_PT_bodyslide"
    bl_parent_id = "SKYRIMSE_PT_character"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        bd = deps.bodyslide_status(deps.get_addon_prefs(context))
        if not bd.available:
            r = layout.row(align=True)
            r.alert = True
            r.label(text="BodySlide 未配置", icon="ERROR")
            r.operator("skyrimse.bodyslide_help", text="", icon="HELP")
            r.operator("skyrimse.open_prefs", text="", icon="PREFERENCES")

        b = layout.box()
        row = b.row(align=True)
        row.prop(props, "bodyslide_preset_enum", text="预设")
        row.operator("skyrimse.bodyslide_refresh_presets", text="", icon="FILE_REFRESH")
        b.prop(props, "bodyslide_preset_xml")
        b.prop(props, "bodyslide_preset_name")
        b.prop(props, "bodyslide_group")
        b.prop(props, "bodyslide_outfit")
        b.prop(props, "bodyslide_output_dir")
        b.prop(props, "bodyslide_trimorphs")
        _big(b, "skyrimse.bodyslide_build", 1.4, enabled=bd.available,
             reason="需要在偏好里设置 BodySlide.exe", icon="MOD_BUILD")

        b = layout.box()
        row = b.row(align=True)
        row.prop(props, "bodyslide_built_nif")
        row.operator("skyrimse.bodyslide_pick_newest_nif", text="", icon="TIME")
        b.operator("skyrimse.bodyslide_import_built_nif", icon="IMPORT")
        b.operator("skyrimse.bodyslide_fill_hands_feet", text="填入手脚到「手动部件」", icon="FILE_FOLDER")

        b = layout.box()
        b.prop(props, "bodyslide_shapekey_size")
        b.operator("skyrimse.bodyslide_apply_shapekeys", icon="SHAPEKEY_DATA")
        row = b.row(align=True)
        row.prop(props, "bodyslide_tri_path", text="TRI")
        row.operator("skyrimse.bodyslide_import_tri", text="", icon="IMPORT")
        if props.bodyslide_report:
            _wrap(layout.box().column(align=True), props.bodyslide_report, 42)


# ----------------------------------------------------------------- 骨架
class SKYRIMSE_PT_skeleton(_Base, Panel):
    bl_label = "骨架"
    bl_idname = "SKYRIMSE_PT_skeleton"
    bl_parent_id = "SKYRIMSE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="ARMATURE_DATA")

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        row = layout.row(align=True)
        row.prop(props, "skeleton_preset", text="")
        row.prop(props, "skeleton_gender", text="")
        _big(layout, "skyrimse.apply_skeleton_preset", 1.4, icon="IMPORT")
        layout.operator("skyrimse.fill_skeleton_from_preset", icon="FILE_FOLDER")
        row = layout.row(align=True)
        row.prop(props, "skeleton_hkx")
        row.operator("skyrimse.fill_default_skeleton", text="", icon="DOWNARROW_HLT")
        r = layout.row()
        r.enabled = bool(props.skeleton_hkx)
        r.operator("skyrimse.import_skeleton", text="仅导入当前路径 HKX", icon="ARMATURE_DATA")
        layout.prop(props, "target_armature")
        layout.label(text="主流 MOD 用 XPMSE；缺骨的通道会被跳过", icon="INFO")


# ----------------------------------------------------------------- 动作
class SKYRIMSE_PT_anim(_Base, Panel):
    bl_label = "动作"
    bl_idname = "SKYRIMSE_PT_anim"
    bl_parent_id = "SKYRIMSE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="ACTION")

    def draw(self, context):
        self.layout.prop(context.scene.skyrim_se_loader, "target_armature", text="目标骨架")


class SKYRIMSE_PT_anim_transfer(_Base, Panel):
    bl_label = "导入 / 中转"
    bl_idname = "SKYRIMSE_PT_anim_transfer"
    bl_parent_id = "SKYRIMSE_PT_anim"

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        layout.prop(props, "anim_source")
        row = layout.row(align=True)
        row.prop(props, "anim_transfer_format", expand=True)
        layout.prop(props, "anim_transfer_output_dir")
        layout.prop(props, "keep_transfer_temp")
        ok = bool(props.anim_source) and props.target_armature is not None
        _big(layout, "skyrimse.anim_transfer", 1.5, enabled=ok,
             reason="需要动作文件和目标骨架", icon="IMPORT")
        col = layout.column(align=True)
        col.operator("skyrimse.import_transfer_file", icon="FILE_FOLDER")
        col.operator("skyrimse.export_transfer_only", icon="EXPORT")
        layout.prop(props, "show_advanced_native_hkx")
        if props.show_advanced_native_hkx:
            adv = layout.box()
            adv.label(text="高级：原生 HKX→Action（非默认）", icon="ERROR")
            adv.prop(props, "animation_hkx")
            adv.operator("skyrimse.import_animation", icon="ACTION")


class SKYRIMSE_PT_preview(_Base, Panel):
    bl_label = "预览"
    bl_idname = "SKYRIMSE_PT_preview"
    bl_parent_id = "SKYRIMSE_PT_anim"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.scale_y = 1.3
        row.operator("skyrimse.setup_preview", icon="PLAY")
        row.operator("skyrimse.list_actions", icon="ACTION")


class SKYRIMSE_PT_retarget(_Base, Panel):
    bl_label = "Retarget"
    bl_idname = "SKYRIMSE_PT_retarget"
    bl_parent_id = "SKYRIMSE_PT_anim"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        layout.prop(props, "retarget_source")
        layout.prop(props, "retarget_target")
        layout.prop(props, "retarget_action")
        layout.prop(props, "retarget_new_action_name")
        layout.prop(props, "retarget_mode")
        layout.prop(props, "retarget_channels")
        row = layout.row(align=True)
        row.prop(props, "retarget_overwrite")
        row.prop(props, "retarget_copy_root_motion")
        if props.retarget_mode == "CUSTOM":
            box = layout.box()
            box.label(text="自定义映射表", icon="BONE_DATA")
            row = box.row()
            row.template_list("SKYRIMSE_UL_bone_map", "", props, "retarget_bone_map",
                              props, "retarget_bone_map_index", rows=5)
            col = row.column(align=True)
            col.operator("skyrimse.retarget_add_map_row", icon="ADD", text="")
            col.operator("skyrimse.retarget_remove_map_row", icon="REMOVE", text="")
            row = box.row(align=True)
            row.operator("skyrimse.retarget_guess_map", icon="SHADERFX")
            row.operator("skyrimse.retarget_clear_map", icon="X")
            box.prop(props, "retarget_map_json")
            row = box.row(align=True)
            row.operator("skyrimse.retarget_import_map", icon="IMPORT")
            row.operator("skyrimse.retarget_export_map", icon="EXPORT")
        ok = props.retarget_source is not None and props.retarget_target is not None
        _big(layout, "skyrimse.retarget_execute", 1.5, enabled=ok,
             reason="选择源和目标骨架", icon="PLAY")
        if props.retarget_report:
            _wrap(layout.box().column(align=True), props.retarget_report, 42)


# ----------------------------------------------------------------- 工具
class SKYRIMSE_PT_tools(_Base, Panel):
    bl_label = "工具"
    bl_idname = "SKYRIMSE_PT_tools"
    bl_parent_id = "SKYRIMSE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="PREFERENCES")

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator("skyrimse.open_prefs", icon="PREFERENCES")
        row.operator("skyrimse.refresh_deps", text="", icon="FILE_REFRESH")


class SKYRIMSE_PT_unpack(_Base, Panel):
    bl_label = "BSArch 解包"
    bl_idname = "SKYRIMSE_PT_unpack"
    bl_parent_id = "SKYRIMSE_PT_tools"

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        bs = deps.bsarch_status(deps.get_addon_prefs(context))
        if not bs.available:
            r = layout.row(align=True)
            r.alert = True
            r.label(text="BSArch 未配置", icon="ERROR")
            r.operator("skyrimse.bsarch_help", text="", icon="HELP")
            r.operator("skyrimse.open_prefs", text="", icon="PREFERENCES")
        layout.prop(props, "archive_path")
        layout.prop(props, "unpack_output_dir")
        _big(layout, "skyrimse.unpack_archive", 1.3,
             enabled=bs.available and bool(props.archive_path),
             reason="需要 BSArch 和档案路径", icon="PACKAGE")
        row = layout.row(align=True)
        row.operator("skyrimse.open_bsarch_url", text="BSArch", icon="URL")
        row.operator("skyrimse.open_bae_url", text="BAE GUI", icon="URL")


class SKYRIMSE_PT_help(_Base, Panel):
    bl_label = "说明"
    bl_idname = "SKYRIMSE_PT_help"
    bl_parent_id = "SKYRIMSE_PT_tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.skyrim_se_loader
        col = layout.column(align=True)
        ad = get_adapter(props.game_id)
        for step in (ad.recommended_workflow() if ad else []):
            _wrap(col, step, 42)
        col.separator()
        for t in (
            "NPC 外观以 FaceGen NIF 为准，不是运行时捏脸",
            ".jslot 是 RaceMenu 预设，不是 ECE CME_save",
            "动作：HKX → PyNifly → FBX/glTF → 目标骨架",
            "场景建议 30 FPS；空格播放",
        ):
            col.label(text=t, icon="INFO")
        if ad:
            for chunk in ad.retarget_notes().split("。"):
                if chunk.strip():
                    col.label(text=chunk.strip() + "。")


# Parents strictly before children.
CLASSES = (
    SKYRIMSE_OT_open_prefs,
    SKYRIMSE_PT_main,
    SKYRIMSE_PT_character,
    SKYRIMSE_PT_npc,
    SKYRIMSE_PT_mesh,
    SKYRIMSE_PT_skin,
    SKYRIMSE_PT_chargen,
    SKYRIMSE_PT_bodyslide,
    SKYRIMSE_PT_skeleton,
    SKYRIMSE_PT_anim,
    SKYRIMSE_PT_anim_transfer,
    SKYRIMSE_PT_preview,
    SKYRIMSE_PT_retarget,
    SKYRIMSE_PT_tools,
    SKYRIMSE_PT_unpack,
    SKYRIMSE_PT_help,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
