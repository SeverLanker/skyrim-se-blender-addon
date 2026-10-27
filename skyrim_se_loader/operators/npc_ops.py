# SPDX-License-Identifier: MIT
"""v0.6 — load an NPC (follower / mod race / vanilla replacer) by reading plugins + FaceGen."""

from __future__ import annotations

import os
import hashlib
import json
import tempfile
from pathlib import Path

import bpy
from bpy.types import Operator, UIList

from ..importers import chargen as chargen_imp
from ..importers import dds_textures, pynifly_bridge
from ..utils import bsarch, deps, esp, loadorder, npc_appearance
from ..utils.paths import expand_path

_CACHE = {"sig": None, "ps": None, "roots": [], "archives": []}


def _props(context):
    return context.scene.skyrim_se_loader


def _data_dir(context) -> str:
    props = _props(context)
    d = expand_path(props.npc_game_data)
    if not d:
        prefs = deps.get_addon_prefs(context)
        d = expand_path(prefs.data_root) if prefs and prefs.data_root else ""
    return d


def _roots(context):
    props = _props(context)
    prof = expand_path(props.npc_mo2_profile)
    mo2, _ = loadorder.mo2_roots(prof) if prof else ([], "")
    data = _data_dir(context)
    return [r for r in mo2 + ([data] if data else []) if r]


def _cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    p = Path(base) / "skyrim_se_loader_cache" / "archives"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _extractor(context):
    prefs = deps.get_addon_prefs(context)
    catalogs = {}

    def cache_key(archive):
        p = Path(archive).resolve()
        stat = p.stat()
        identity = f"{os.path.normcase(str(p))}|{stat.st_size}|{stat.st_mtime_ns}"
        return p.stem + "-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]

    def contains(archive, rel):
        if archive not in catalogs:
            index = _cache_dir() / (cache_key(archive) + ".files.json")
            try:
                catalogs[archive] = set(json.loads(index.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                paths = bsarch.list_archive(archive, prefs=prefs)
                catalogs[archive] = paths
                if paths is not None:
                    try:
                        index.write_text(json.dumps(sorted(paths)), encoding="utf-8")
                    except OSError:
                        pass
        paths = catalogs[archive]
        return paths is None or rel.replace("\\", "/").lstrip("/").casefold() in paths

    def extract(archive: str) -> str:
        out = _cache_dir() / cache_key(archive)
        marker = out / ".unpacked"
        if marker.is_file():
            return str(out)
        res = bsarch.unpack_archive(archive, str(out), prefs=prefs)
        if res.ok:
            marker.write_text("ok", encoding="utf-8")
            return str(out)
        print(f"[skyrim_se_loader] {res.message}")
        return ""

    extract.contains = contains
    return extract


class SKYRIMSE_UL_npcs(UIList):
    bl_idname = "SKYRIMSE_UL_npcs"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        if self.layout_type in {"GRID"}:
            layout.label(text=item.full or item.edid or "-", icon="USER")
            return
        row = layout.row(align=True)
        row.label(text=item.full or "-", icon="USER")
        row.label(text=item.edid or "-")
        row.label(text=item.plugin)
        row.label(text=getattr(item, "race", "") or "-")


class SKYRIMSE_OT_npc_index(Operator):
    bl_idname = "skyrimse.npc_index"
    bl_label = "读取插件 / 建立索引"
    bl_description = "按加载顺序读取 esm/esp/esl 中的 NPC_/RACE/HDPT/ARMO/ARMA/TXST；后加载覆盖前者"

    def execute(self, context):
        props = _props(context)
        roots = _roots(context)
        names, src = loadorder.build_order(
            expand_path(props.npc_mo2_profile), _data_dir(context), props.npc_manual_plugins
        )
        files, missing = loadorder.find_plugin_files(names, roots)
        if not files:
            msg = "没有找到任何插件文件。请填写游戏 Data 目录或 MO2 profile。"
            props.npc_index_report = msg
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        wm = context.window_manager
        wm.progress_begin(0, len(files))
        n = [0]

        def prog(_p):
            n[0] += 1
            wm.progress_update(n[0])

        ps = esp.load_plugins(files, progress=prog)
        wm.progress_end()
        _CACHE.update(ps=ps, roots=roots, archives=npc_appearance.archive_candidates(names, roots))
        cnt = sum(1 for r in ps.records.values() if r.sig == "NPC_")
        lines = [f"加载顺序来源：{src}", f"已读 {len(ps.plugins)} 个插件，NPC {cnt} 个"]
        if missing:
            lines.append("未找到插件文件：" + ", ".join(missing[:12]) + (" …" if len(missing) > 12 else ""))
        lines += ["读取失败：" + e for e in ps.errors[:8]]
        props.npc_index_report = "\n".join(lines)
        bpy.ops.skyrimse.npc_search()
        self.report({"INFO"}, lines[1])
        return {"FINISHED"}


class SKYRIMSE_OT_npc_search(Operator):
    bl_idname = "skyrimse.npc_search"
    bl_label = "搜索 NPC"

    def execute(self, context):
        props = _props(context)
        ps = _CACHE.get("ps")
        props.npc_results.clear()
        if ps is None:
            self.report({"WARNING"}, "请先「读取插件」")
            return {"CANCELLED"}
        for r in ps.search(props.npc_search, limit=300):
            it = props.npc_results.add()
            it.key = esp.fmt_key(r.key)
            it.edid, it.full, it.plugin = r.edid, r.full, r.plugin
            try:
                race = ps.get(r.fields.get("race"), "RACE")
                it.race = race.edid if race else ""
            except Exception:  # noqa: BLE001
                it.race = ""
        props.npc_results_index = 0
        return {"FINISHED"}


def _new_meshes(result):
    return [o for o in (result.objects or []) if getattr(o, "type", None) == "MESH"]


def _apply_tex(context, objs, path, slot):
    if not objs or not path:
        return None
    for o in context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    context.view_layer.objects.active = objs[0]
    return dds_textures.apply_dds_to_selection(context, path, slot=slot)


def multiply_facetint(objs, tint_path: str) -> str:
    """Approximate FaceGen's base² + 2*tint*base*(1-base) with soft light.

    The legacy function name is retained for callers; this is not multiplication.
    Separate detail maps and the game's lighting are not reproduced here.
    """
    try:
        img = bpy.data.images.load(tint_path, check_existing=True)
    except Exception as exc:  # noqa: BLE001
        return f"FaceTint 加载失败（{exc}），未叠加"
    done = 0
    for obj in objs:
        for mat in getattr(obj.data, "materials", []) or []:
            if mat is None:
                continue
            mat.use_nodes = True
            nt = mat.node_tree
            try:
                nt, shader = dds_textures._ensure_principled(mat)
            except ValueError:
                continue
            inp = shader.inputs.get("Diffuse" if shader.type == "GROUP" else "Base Color")
            if inp is None:
                continue
            if inp.links and inp.links[0].from_node.get("sse_facetint"):
                continue
            src = inp.links[0].from_socket if inp.links else None
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image, tex.label = img, "FaceTint"
            tex.location = (-650, -150)
            uv = next((n for n in nt.nodes if n.name == "UV_Converter"), None)
            uv_socket = (uv.outputs.get("Vector") or uv.outputs.get("UV")) if uv else None
            if uv_socket is not None:
                nt.links.new(uv_socket, tex.inputs["Vector"])
            try:
                mix = nt.nodes.new("ShaderNodeMix")
                mix.data_type, mix.blend_type = "RGBA", "SOFT_LIGHT"
                mix.inputs[0].default_value = 1.0
                a, b, out = mix.inputs[6], mix.inputs[7], mix.outputs[2]
            except Exception:  # noqa: BLE001 — older node API
                mix = nt.nodes.new("ShaderNodeMixRGB")
                mix.blend_type = "SOFT_LIGHT"
                mix.inputs[0].default_value = 1.0
                a, b, out = mix.inputs[1], mix.inputs[2], mix.outputs[0]
            mix.label = "FaceTint Soft Light"
            mix["sse_facetint"] = True
            mix.location = (-250, 150)
            if src is not None:
                nt.links.new(src, a)
            else:
                a.default_value = tuple(inp.default_value)
            nt.links.new(tex.outputs["Color"], b)
            nt.links.new(out, inp)
            done += 1
    if not done:
        return "FaceTint：没有可用的材质输入或已经叠加，未重复修改"
    return f"FaceTint 已柔光合成到 {done} 个头部材质（近似：未完整还原游戏细节贴图和光照）"


def _restore_nif_textures(meshes, locator, log):
    """Resolve NIF texture paths across MO2 roots and archives before tinting."""
    seen = set()
    for obj in meshes:
        for mat in obj.data.materials:
            if mat is None or mat in seen:
                continue
            seen.add(mat)
            for key, slot in (("Diffuse", "BASE_COLOR"), ("Normal", "NORMAL"),
                              ("SoftLighting", "SUBSURFACE"), ("Specular", "SPECULAR")):
                rel = mat.get("BSShaderTextureSet_" + key, "")
                if not rel:
                    continue
                path, _ = locator.find(rel.replace("\\", "/"))
                if not path:
                    log.append(f"[缺失贴图] {obj.name} {key}: {rel}")
                    continue
                try:
                    dds_textures.apply_to_material(mat, path, slot)
                except (ValueError, OSError, RuntimeError) as exc:
                    log.append(f"[贴图] {obj.name} {key}: {exc}")


class SKYRIMSE_OT_npc_load(Operator):
    bl_idname = "skyrimse.npc_load"
    bl_label = "加载此 NPC"
    bl_description = "解析外观（FaceGen 头 + 种族皮肤身体/手/脚），经 PyNifly 导入并赋 DDS"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = _props(context)
        ps = _CACHE.get("ps")
        if ps is None or not props.npc_results:
            self.report({"ERROR"}, "请先读取插件并选中一个 NPC")
            return {"CANCELLED"}
        item = props.npc_results[props.npc_results_index]
        plug, hid = item.key.split("|")
        try:
            app = npc_appearance.resolve(ps, (plug, int(hid, 16)))
        except KeyError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        loc = npc_appearance.FileLocator(
            _CACHE["roots"], _CACHE["archives"],
            extract=_extractor(context) if props.npc_extract_archives else None,
        )
        loc.fill(app)

        log = []
        head_objs = []
        facegen = app.parts[0]
        to_import = [p for p in app.parts if p.role in ("body", "hands", "feet")]
        if app.has_facegen:
            to_import.append(facegen)
        else:
            to_import = [p for p in app.parts if p.role.startswith("head_part:")] + to_import
        if not deps.operator_exists(bpy.ops.import_scene, "pynifly"):
            props.npc_report = app.report() + "\n· 未安装/启用 PyNifly，仅输出解析报告"
            self.report({"WARNING"}, "PyNifly 未启用，只生成了报告")
            return {"FINISHED"}
        failures, loaded = 0, 0
        for part in to_import:
            if not part.file:
                continue
            res = pynifly_bridge.import_nif(context, part.file, {"import_collisions": False, "import_tris": props.import_tris})
            if not res.ok:
                failures += 1
                log.append(f"[导入失败] {part.role}: {res.message}")
                continue
            meshes = _new_meshes(res)
            if not meshes:
                failures += 1
                log.append(f"[导入失败] {part.role}: 未生成网格")
                continue
            loaded += 1
            if props.target_armature is None:
                rigs = [o for o in res.objects or [] if o.type == "ARMATURE"]
                if len(rigs) == 1:
                    props.target_armature = rigs[0]
                    log.append(f"自动复用身体骨架：{rigs[0].name}")
            _restore_nif_textures(meshes, loc, log)
            for o in meshes:
                o["skyrim_se_part"] = part.role
                o["skyrim_se_source"] = f"{part.file_from} :: {part.rel_path}"
            if part.role in ("head_facegen", "head_part:face"):
                head_objs += chargen_imp.select_head_like_meshes(meshes)
            for k, slot in (("TX00", "BASE_COLOR"), ("TX01", "NORMAL"),
                            ("TX02", "SUBSURFACE"), ("TX07", "SPECULAR")):
                if part.texture_files.get(k):
                    r = _apply_tex(context, meshes, part.texture_files[k], slot)
                    if r and not r.ok:
                        log.append(f"[贴图] {part.role} {k}: {r.message}")
        for key, slot in (("TX00", "BASE_COLOR"), ("TX01", "NORMAL"),
                          ("TX02", "SUBSURFACE"), ("TX07", "SPECULAR")):
            face_texture = app.face_textures.get(key + "_file")
            if head_objs and face_texture:
                r = _apply_tex(context, head_objs, face_texture, slot)
                if r and not r.ok:
                    log.append(f"[贴图] 面部 {key}: {r.message}")
        if head_objs and app.facetint and app.facetint.file:
            log.append(multiply_facetint(head_objs, app.facetint.file))
        elif app.facetint and not app.facetint.file:
            log.append("未找到 FaceTint DDS：肤色/妆容不叠加（近似）")
        props.npc_report = app.report() + ("\n" + "\n".join(log) if log else "")
        n_miss = len(app.missing)
        msg = f"已加载 {item.edid}（{loaded} 个部件）；缺失部件 {n_miss}；导入失败 {failures}" + ("；无 FaceGen（外观可能不匹配）" if not app.has_facegen else "")
        props.last_status = msg
        self.report({"WARNING"} if n_miss or failures or not app.has_facegen else {"INFO"}, msg)
        return {"FINISHED"} if loaded else {"CANCELLED"}


CLASSES = (SKYRIMSE_UL_npcs, SKYRIMSE_OT_npc_index, SKYRIMSE_OT_npc_search, SKYRIMSE_OT_npc_load)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
