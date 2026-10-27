# SPDX-License-Identifier: MIT
"""Import operators wired to the active GameAdapter."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.types import Operator, UIList

from ..adapters.base import ImportRequest
from ..adapters.registry import get as get_adapter
from ..importers import chargen as chargen_imp
from ..importers.fallback import MISSING_PYNIFLY
from ..utils import deps, jslot
from ..utils.paths import suggest_skeleton_under_data


def _props(context):
    return context.scene.skyrim_se_loader


def _set_status(context, message: str):
    _props(context).last_status = message


def _adapter(context):
    ad = get_adapter(_props(context).game_id)
    if ad is None:
        ad = get_adapter("skyrim_se")
    return ad


def _import_nif_kind(context, kind: str, filepath: str, *, collisions: bool | None = None):
    props = _props(context)
    path = (filepath or "").strip()
    if not path:
        return None, f"请先填写 {kind} 的 NIF 路径。"
    use_col = props.import_collisions if collisions is None else collisions
    ad = _adapter(context)
    result = ad.import_asset(
        context,
        ImportRequest(
            kind if kind in ("body", "head", "mesh") else "mesh",
            path,
            {
                "import_collisions": bool(use_col),
                "import_tris": props.import_tris,
            },
        ),
    )
    return result, result.message


class SKYRIMSE_UL_extra_parts(UIList):
    bl_idname = "SKYRIMSE_UL_extra_parts"

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
        row.prop(item, "filepath", text="", emboss=False)
        row.prop(item, "label", text="", emboss=True)


class SKYRIMSE_OT_refresh_deps(Operator):
    bl_idname = "skyrimse.refresh_deps"
    bl_label = "检测依赖"
    bl_description = "检测 PyNifly、BSArch、BodySlide、FBX/glTF 中转是否可用"

    def execute(self, context):
        report = deps.full_dependency_report(context)
        print(report)
        prefs = deps.get_addon_prefs(context)
        py = deps.pynifly_status()
        bs = deps.bsarch_status(prefs)
        bd = deps.bodyslide_status(prefs)
        msg = f"{py.message} ｜ {bs.message} ｜ {bd.message}"
        _set_status(context, msg)
        level = {"INFO"} if py.available else {"WARNING"}
        self.report(level, msg[:255])
        return {"FINISHED"}


class SKYRIMSE_OT_fill_default_skeleton(Operator):
    bl_idname = "skyrimse.fill_default_skeleton"
    bl_label = "填入默认骨骼路径"
    bl_description = "根据插件偏好中的 Data 目录或默认骨骼路径填写"

    def execute(self, context):
        props = _props(context)
        prefs = deps.get_addon_prefs(context)
        path = ""
        if prefs:
            path = prefs.default_skeleton_hkx or suggest_skeleton_under_data(
                prefs.data_root
            )
        if not path:
            _set_status(
                context,
                "未配置 Data / 默认骨骼路径。请先解包 BA2，或在偏好里填写。",
            )
            self.report({"WARNING"}, _props(context).last_status)
            return {"CANCELLED"}
        props.skeleton_hkx = path
        _set_status(context, f"已填入: {path}")
        return {"FINISHED"}


class SKYRIMSE_OT_import_body(Operator):
    bl_idname = "skyrimse.import_body"
    bl_label = "导入身体/服装 NIF"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        result, msg = _import_nif_kind(context, "body", props.body_nif)
        if result is None:
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_head(Operator):
    bl_idname = "skyrimse.import_head"
    bl_label = "导入头雕 NIF"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        result, msg = _import_nif_kind(
            context, "head", props.head_nif, collisions=False
        )
        if result is None:
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_hands(Operator):
    bl_idname = "skyrimse.import_hands"
    bl_label = "导入手 NIF"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        result, msg = _import_nif_kind(context, "hands", props.hands_nif)
        if result is None:
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_feet(Operator):
    bl_idname = "skyrimse.import_feet"
    bl_label = "导入脚 NIF"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        result, msg = _import_nif_kind(context, "feet", props.feet_nif)
        if result is None:
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_hair(Operator):
    bl_idname = "skyrimse.import_hair"
    bl_label = "导入头发 NIF"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        result, msg = _import_nif_kind(
            context, "hair", props.hair_nif, collisions=False
        )
        if result is None:
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_brows(Operator):
    bl_idname = "skyrimse.import_brows"
    bl_label = "导入眉毛 NIF"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        result, msg = _import_nif_kind(
            context, "brows", props.brows_nif, collisions=False
        )
        if result is None:
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_eyes(Operator):
    bl_idname = "skyrimse.import_eyes"
    bl_label = "导入眼睛 NIF"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        result, msg = _import_nif_kind(
            context, "eyes", props.eyes_nif, collisions=False
        )
        if result is None:
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_extra_part_add(Operator):
    bl_idname = "skyrimse.extra_part_add"
    bl_label = "添加额外部件"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        props.extra_parts.add()
        props.extra_parts_index = len(props.extra_parts) - 1
        return {"FINISHED"}


class SKYRIMSE_OT_extra_part_remove(Operator):
    bl_idname = "skyrimse.extra_part_remove"
    bl_label = "移除额外部件"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        idx = props.extra_parts_index
        if 0 <= idx < len(props.extra_parts):
            props.extra_parts.remove(idx)
            props.extra_parts_index = min(idx, max(0, len(props.extra_parts) - 1))
        return {"FINISHED"}


class SKYRIMSE_OT_import_extra_parts(Operator):
    bl_idname = "skyrimse.import_extra_parts"
    bl_label = "导入额外部件"
    bl_description = "导入列表中所有已填路径的额外 NIF（嘴/须等）"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        paths = [
            (item.filepath or "").strip()
            for item in props.extra_parts
            if (item.filepath or "").strip()
        ]
        if not paths:
            msg = "额外部件列表为空，请先添加路径。"
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}
        ok_n = 0
        messages = []
        for path in paths:
            result, msg = _import_nif_kind(context, "mesh", path, collisions=False)
            if result is None or not result.ok:
                messages.append(msg if result is None else result.message)
            else:
                ok_n += 1
                messages.append(result.message)
        summary = f"额外部件：成功 {ok_n}/{len(paths)}。" + "；".join(messages[:3])
        _set_status(context, summary)
        self.report({"INFO"} if ok_n else {"ERROR"}, summary[:255])
        return {"FINISHED"} if ok_n else {"CANCELLED"}


class SKYRIMSE_OT_import_all_parts(Operator):
    bl_idname = "skyrimse.import_all_parts"
    bl_label = "一键导入已填部件"
    bl_description = (
        "按顺序导入：身体 → 手 → 脚 → 头雕 → 头发 → 眉毛 → 眼睛 → 额外部件；"
        "绑到同一 target_armature（导入前会激活目标骨骼）"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        sequence = [
            ("身体", props.body_nif, True),
            ("手", props.hands_nif, True),
            ("脚", props.feet_nif, True),
            ("头雕", props.head_nif, False),
            ("头发", props.hair_nif, False),
            ("眉毛", props.brows_nif, False),
            ("眼睛", props.eyes_nif, False),
        ]
        for item in props.extra_parts:
            p = (item.filepath or "").strip()
            if p:
                label = (item.label or "额外").strip() or "额外"
                sequence.append((label, p, False))

        filled = [(n, p, c) for n, p, c in sequence if (p or "").strip()]
        if not filled:
            msg = "没有已填的部件路径。请至少填写身体/头雕等之一。"
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}

        ok_n = 0
        fail = []
        for name, path, use_col in filled:
            result, msg = _import_nif_kind(
                context, "mesh", path, collisions=use_col
            )
            if result is not None and result.ok:
                ok_n += 1
            else:
                fail.append(f"{name}:{msg if result is None else result.message}")

        summary = f"一键导入：成功 {ok_n}/{len(filled)}"
        if fail:
            summary += "；失败：" + "；".join(fail[:4])
        _set_status(context, summary)
        level = {"INFO"} if ok_n == len(filled) else (
            {"WARNING"} if ok_n else {"ERROR"}
        )
        self.report(level, summary[:255])
        return {"FINISHED"} if ok_n else {"CANCELLED"}


class SKYRIMSE_OT_import_skin(Operator):
    bl_idname = "skyrimse.import_skin"
    bl_label = "赋皮肤 DDS"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        ad = _adapter(context)
        result = ad.import_asset(
            context,
            ImportRequest(
                "skin",
                props.skin_dds,
                {"texture_slot": props.texture_slot},
            ),
        )
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_skeleton(Operator):
    bl_idname = "skyrimse.import_skeleton"
    bl_label = "导入骨骼 HKX"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        ad = _adapter(context)
        result = ad.import_asset(
            context,
            ImportRequest("skeleton", props.skeleton_hkx, {}),
        )
        if result.ok:
            arms = [o for o in context.scene.objects if o.type == "ARMATURE"]
            if arms and props.target_armature is None:
                props.target_armature = arms[-1]
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message)
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_import_animation(Operator):
    """Advanced: native HKX → Action (not the default transfer path)."""

    bl_idname = "skyrimse.import_animation"
    bl_label = "原生导入动作 HKX（高级）"
    bl_description = (
        "高级：直接用 PyNifly 把 HKX 导入为 Action。"
        "默认请用「动作中转导入（FBX/glTF）」。"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        path = props.animation_hkx or props.anim_source
        obj = context.view_layer.objects.active
        if props.target_armature is not None:
            context.view_layer.objects.active = props.target_armature
            props.target_armature.select_set(True)
            obj = props.target_armature
        if obj is None or obj.type != "ARMATURE":
            arms = [o for o in context.scene.objects if o.type == "ARMATURE"]
            if arms:
                context.view_layer.objects.active = arms[0]
                arms[0].select_set(True)
            else:
                msg = "请先导入并选中 Armature（建议先导入 skeleton.hkx）"
                _set_status(context, msg)
                self.report({"ERROR"}, msg)
                return {"CANCELLED"}

        ad = _adapter(context)
        result = ad.import_asset(
            context,
            ImportRequest(
                "animation",
                path,
                {"reference_skel": props.skeleton_hkx},
            ),
        )
        note = result.message
        if result.ok:
            note += "（高级原生路径；默认推荐 FBX/glTF 中转）"
        _set_status(context, note)
        self.report({"INFO"} if result.ok else {"ERROR"}, note[:255])
        return {"FINISHED"} if result.ok else {"CANCELLED"}


class SKYRIMSE_OT_parse_jslot(Operator):
    bl_idname = "skyrimse.parse_jslot"
    bl_label = "解析 RaceMenu .jslot（只读）"
    bl_description = (
        "解析预设为只读摘要。不能在 Blender 完整还原 jslot 滑条；"
        "请以 RaceMenu/ECE 导出的头雕 NIF + 面部 DDS 为准"
    )

    def execute(self, context):
        props = _props(context)
        info = jslot.parse_jslot(props.chargen_jslot)
        if not info.ok:
            props.chargen_jslot_report = info.error
            _set_status(context, info.error)
            self.report({"ERROR"}, info.error[:255])
            return {"CANCELLED"}
        report = "\n".join(info.summary_lines)
        props.chargen_jslot_report = report
        status = jslot.format_jslot_status(info)
        _set_status(context, status)
        print("[jslot]", report)
        self.report({"INFO"}, status[:255])
        return {"FINISHED"}


class SKYRIMSE_OT_guess_chargen_dds(Operator):
    bl_idname = "skyrimse.guess_chargen_dds"
    bl_label = "猜测同名面部 DDS"
    bl_description = "在 CharGen NIF 同目录查找同名/同 stem 的 .dds"

    def execute(self, context):
        props = _props(context)
        found = chargen_imp.guess_face_dds_beside_nif(props.chargen_nif)
        if not found:
            msg = "未找到与 CharGen NIF 配套的 .dds"
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}
        props.chargen_face_dds = found
        msg = f"已填入面部 DDS：{found}"
        _set_status(context, msg)
        self.report({"INFO"}, msg[:255])
        return {"FINISHED"}


class SKYRIMSE_OT_import_chargen_pack(Operator):
    bl_idname = "skyrimse.import_chargen_pack"
    bl_label = "导入 CharGen 头雕包"
    bl_description = (
        "用 PyNifly 导入 RaceMenu/ECE 导出的头雕 NIF，"
        "尽量绑 target_armature，并把面部 DDS 赋到疑似头部的 Mesh。"
        "ECE CME_save 槽位需先导出为头 NIF"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        nif = (props.chargen_nif or "").strip()
        if not nif:
            msg = "请选择 CharGen 头雕 NIF（常见于 SKSE/Plugins/CharGen/）。"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        result = chargen_imp.import_chargen_package(
            context,
            nif,
            props.chargen_face_dds,
            import_tris=props.import_tris,
            texture_slot=props.texture_slot,
        )
        _set_status(context, result.message)
        self.report({"INFO"} if result.ok else {"ERROR"}, result.message[:255])
        return {"FINISHED"} if result.ok else {"CANCELLED"}



class SKYRIMSE_OT_export_jslot_shapekeys(Operator):
    bl_idname = "skyrimse.export_jslot_shapekeys"
    bl_label = "导出 jslot→Shape Key 映射 JSON"
    bl_description = (
        "把 RaceMenu bodyMorphs（默认去掉 XPMSE）写成名称→值 JSON。"
        "仅当网格有同名 Shape Key 时可近似套用；不能还原游戏内完整捏脸"
    )

    def execute(self, context):
        props = _props(context)
        info = jslot.parse_jslot(props.chargen_jslot)
        if not info.ok:
            props.chargen_jslot_report = info.error
            _set_status(context, info.error)
            self.report({"ERROR"}, info.error[:255])
            return {"CANCELLED"}
        # Rebuild candidates with face-custom flag
        try:
            raw = Path(props.chargen_jslot).expanduser().read_text(encoding="utf-8")
            import json as _json
            data = _json.loads(raw)
            info.shapekey_candidates = jslot.extract_shapekey_map(
                data, include_face_custom=bool(props.chargen_apply_face_custom)
            )
        except Exception:
            pass
        out = (props.chargen_shapekey_json or "").strip()
        if not out:
            src = Path(props.chargen_jslot).expanduser()
            out = str(src.with_suffix(".shapekeys.json"))
            props.chargen_shapekey_json = out
        try:
            written = jslot.export_shapekey_map_json(info, out)
        except OSError as exc:
            msg = f"写出失败：{exc}"
            _set_status(context, msg)
            self.report({"ERROR"}, msg[:255])
            return {"CANCELLED"}
        props.chargen_jslot_report = "\n".join(info.summary_lines)
        msg = (
            f"已导出 {len(info.shapekey_candidates)} 条映射 → {written}。"
            "套用时仅名称匹配；近似 ≠ 完整捏脸。"
        )
        _set_status(context, msg)
        self.report({"INFO"}, msg[:255])
        return {"FINISHED"}


class SKYRIMSE_OT_apply_jslot_shapekeys(Operator):
    bl_idname = "skyrimse.apply_jslot_shapekeys"
    bl_label = "尝试 jslot 映射到当前 Shape Keys"
    bl_description = (
        "按名称把 RaceMenu bodyMorphs 值写到选中/活动 Mesh 的 Shape Keys。"
        "近似预览；无同名键则跳过。不能还原 tint/sculpt/头部件"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        info = jslot.parse_jslot(props.chargen_jslot)
        if not info.ok:
            _set_status(context, info.error)
            self.report({"ERROR"}, info.error[:255])
            return {"CANCELLED"}
        try:
            import json as _json
            data = _json.loads(
                Path(props.chargen_jslot).expanduser().read_text(encoding="utf-8")
            )
            mapping = jslot.extract_shapekey_map(
                data, include_face_custom=bool(props.chargen_apply_face_custom)
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"读取 jslot 失败：{exc}"
            _set_status(context, msg)
            self.report({"ERROR"}, msg[:255])
            return {"CANCELLED"}

        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            meshes = [o for o in context.selected_objects if o.type == "MESH"]
            obj = meshes[0] if meshes else None
        if obj is None or obj.type != "MESH":
            msg = "请先选中带 Shape Keys 的 Mesh。"
            _set_status(context, msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        if not obj.data.shape_keys or not obj.data.shape_keys.key_blocks:
            msg = f"{obj.name} 没有 Shape Keys。"
            _set_status(context, msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}

        # Build lookup ignoring optional PyNifly '>' prefix
        blocks = obj.data.shape_keys.key_blocks
        by_name = {}
        for kb in blocks:
            if kb.name == "Basis":
                continue
            by_name[kb.name] = kb
            if ">" in kb.name:
                by_name[kb.name.split(">", 1)[-1]] = kb
            by_name[kb.name.casefold()] = kb

        matched = 0
        unmatched = []
        for name, val in mapping.items():
            kb = by_name.get(name) or by_name.get(name.casefold())
            if kb is None:
                unmatched.append(name)
                continue
            try:
                # RaceMenu body morphs often already in ~-1..1; face custom may be larger
                # Expand slider range BEFORE assigning value (Blender clamps value to min/max)
                if float(val) > kb.slider_max:
                    kb.slider_max = float(val)
                if float(val) < kb.slider_min:
                    kb.slider_min = float(val)
                kb.value = float(val)
                matched += 1
            except Exception:
                unmatched.append(name)

        props.chargen_jslot_report = "\n".join(info.summary_lines)
        msg = (
            f"jslot→Shape Keys：匹配 {matched}/{len(mapping)}（{obj.name}）。"
            "近似预览，≠ 游戏内完整捏脸/妆容。"
        )
        if unmatched:
            msg += f" 未匹配 {len(unmatched)}（如 {', '.join(unmatched[:5])}）"
        _set_status(context, msg)
        print("[jslot shapekeys]", msg)
        level = {"INFO"} if matched else {"WARNING"}
        self.report(level, msg[:255])
        return {"FINISHED"} if matched else {"CANCELLED"}


class SKYRIMSE_OT_show_missing_help(Operator):
    bl_idname = "skyrimse.show_missing_help"
    bl_label = "依赖说明"

    def execute(self, context):
        self.report({"INFO"}, "详见侧栏与 README")
        print(MISSING_PYNIFLY)
        print(deps.full_dependency_report(context))
        _set_status(context, "已在系统控制台打印依赖说明")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        for line in MISSING_PYNIFLY.strip().splitlines():
            self.layout.label(text=line)


CLASSES = (
    SKYRIMSE_UL_extra_parts,
    SKYRIMSE_OT_refresh_deps,
    SKYRIMSE_OT_fill_default_skeleton,
    SKYRIMSE_OT_import_body,
    SKYRIMSE_OT_import_head,
    SKYRIMSE_OT_import_hands,
    SKYRIMSE_OT_import_feet,
    SKYRIMSE_OT_import_hair,
    SKYRIMSE_OT_import_brows,
    SKYRIMSE_OT_import_eyes,
    SKYRIMSE_OT_extra_part_add,
    SKYRIMSE_OT_extra_part_remove,
    SKYRIMSE_OT_import_extra_parts,
    SKYRIMSE_OT_import_all_parts,
    SKYRIMSE_OT_import_skin,
    SKYRIMSE_OT_import_skeleton,
    SKYRIMSE_OT_import_animation,
    SKYRIMSE_OT_parse_jslot,
    SKYRIMSE_OT_guess_chargen_dds,
    SKYRIMSE_OT_import_chargen_pack,
    SKYRIMSE_OT_export_jslot_shapekeys,
    SKYRIMSE_OT_apply_jslot_shapekeys,
    SKYRIMSE_OT_show_missing_help,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
