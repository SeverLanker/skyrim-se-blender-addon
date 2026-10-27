# SPDX-License-Identifier: MIT
"""Resolve an NPC_ record into concrete mesh / texture files — no bpy.

FaceGen paths follow the Creation Kit convention:
  meshes\\actors\\character\\FaceGenData\\FaceGeom\\<OriginPlugin>\\<00XXXXXX>.nif
  textures\\actors\\character\\FaceGenData\\FaceTint\\<OriginPlugin>\\<00XXXXXX>.dds
where OriginPlugin is the plugin that *first defines* the NPC (not the overriding one).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .esp import SLOT_BODY, SLOT_FEET, SLOT_HANDS, PluginSet, fmt_key

FACEGEOM = "meshes/actors/character/FaceGenData/FaceGeom"
FACETINT = "textures/actors/character/FaceGenData/FaceTint"


@dataclass
class Part:
    role: str  # head_facegen | head_part:<type> | body | hands | feet
    rel_path: str  # Data-relative path (meshes/... or textures/...)
    source: str  # which record / plugin determined it
    file: str = ""  # resolved absolute file ("" = missing)
    file_from: str = ""  # loose root / archive name
    textures: dict = field(default_factory=dict)  # TX00.. -> rel path
    texture_files: dict = field(default_factory=dict)


@dataclass
class Appearance:
    npc_label: str
    female: bool
    race_label: str
    origin_plugin: str
    winning_plugin: str
    traits_from: str
    parts: list = field(default_factory=list)
    facetint: Part | None = None
    face_textures: dict = field(default_factory=dict)  # from FTST / head HDPT TXST
    has_facegen: bool = False
    notes: list = field(default_factory=list)

    def report(self) -> str:
        L = [
            f"NPC：{self.npc_label}  ({'女' if self.female else '男'})",
            f"种族：{self.race_label}",
            f"定义插件：{self.origin_plugin}；生效覆盖：{self.winning_plugin}",
        ]
        if self.traits_from:
            L.append(f"外观来自模板：{self.traits_from}")
        miss = []
        for p in self.parts + ([self.facetint] if self.facetint else []):
            if self.has_facegen and p.role.startswith("head_part:"):
                L.append(f"[备用/未使用] {p.role}: {p.rel_path}（{p.source}）")
                continue
            if p.file:
                L.append(f"[OK] {p.role}: {p.rel_path} ← {p.file_from}（{p.source}）")
            else:
                miss.append(p)
        for p in miss:
            L.append(f"[缺失] {p.role}: {p.rel_path}（{p.source}）")
        for n in self.notes:
            L.append("· " + n)
        return "\n".join(L)

    @property
    def missing(self):
        return [p for p in self.parts + ([self.facetint] if self.facetint else [])
                if not p.file and not (self.has_facegen and p.role.startswith("head_part:"))]


def _norm(rel: str, prefix: str) -> str:
    r = (rel or "").replace("\\", "/").lstrip("/")
    if not r:
        return ""
    if not r.lower().startswith(prefix + "/"):
        r = f"{prefix}/{r}"
    return r


def _txst_textures(ps: PluginSet, key) -> dict:
    t = ps.get(key, "TXST")
    if not t:
        return {}
    return {k: _norm(v, "textures") for k, v in t.fields.get("textures", {}).items() if v}


def facegen_paths(origin_plugin: str, local_id: int) -> tuple[str, str]:
    hid = f"{local_id & 0xFFFFFF:08X}"
    return f"{FACEGEOM}/{origin_plugin}/{hid}.nif", f"{FACETINT}/{origin_plugin}/{hid}.dds"


def _follow_traits(ps: PluginSet, npc, max_depth: int = 16):
    """Follow TPLT while 'Use Traits' set. Returns (record supplying traits, chain note)."""
    cur, chain = npc, []
    for _ in range(max_depth):
        if not (cur.fields.get("template_flags", 0) & 0x0001):
            break
        tk = cur.fields.get("template")
        nxt = ps.get(tk)
        if nxt is None:
            chain.append(f"模板 {fmt_key(tk)} 未在已加载插件中找到")
            break
        if nxt.sig != "NPC_":
            chain.append(f"模板 {nxt.edid or fmt_key(tk)} 是 {nxt.sig}（等级列表，游戏运行时随机），无法静态确定")
            break
        cur = nxt
    return cur, chain


def _armor_races(ps: PluginSet, race_key):
    """Include inherited Armor Race keys without accepting unrelated races."""
    chain = set()
    while race_key and race_key not in chain:
        chain.add(race_key)
        race = ps.get(race_key, "RACE")
        race_key = race.fields.get("armor_race") if race else None
    return chain


def _missing_skin_parts(reason):
    return [Part(role, "", f"未解析：{reason}") for role in ("body", "hands", "feet")]


def _armor_parts(ps: PluginSet, armo_key, race_key, female: bool, source_label: str):
    armo = ps.get(armo_key, "ARMO")
    out = []
    if not armo:
        reason = f"皮肤 ARMO {fmt_key(armo_key)} 未找到"
        return _missing_skin_parts(reason), [reason]
    picked = {}
    priorities = {}
    allowed_races = _armor_races(ps, race_key)
    for ak in armo.fields.get("addons", []):
        arma = ps.get(ak, "ARMA")
        if not arma:
            continue
        races = [arma.fields.get("race")] + arma.fields.get("extra_races", [])
        if allowed_races and not allowed_races.intersection(races):
            continue
        slots = arma.fields.get("slots", 0)
        priority = arma.fields.get("priority_f" if female else "priority_m", 0)
        for role, bit in (("body", SLOT_BODY), ("hands", SLOT_HANDS), ("feet", SLOT_FEET)):
            if slots & bit and (role not in picked or priority > priorities[role]):
                model = arma.fields.get("model_f" if female else "model_m") or arma.fields.get("model_m", "")
                tex_key = arma.fields.get("skin_tex_f" if female else "skin_tex_m")
                if model:
                    priorities[role] = priority
                    picked[role] = Part(
                        role=role,
                        rel_path=_norm(model, "meshes"),
                        source=f"{source_label} → {armo.edid} → ARMA {arma.edid} [{arma.plugin}]",
                        textures=_txst_textures(ps, tex_key),
                    )
    notes = []
    for role in ("body", "hands", "feet"):
        if role in picked:
            out.append(picked[role])
        else:
            reason = f"皮肤 {armo.edid} 没有适用于该种族的 {role} ARMA"
            notes.append(reason)
            out.append(Part(role, "", f"未解析：{reason}"))
    return out, notes


def resolve(ps: PluginSet, npc_key) -> Appearance:
    npc = ps.get(npc_key, "NPC_")
    if npc is None:
        raise KeyError(f"NPC {fmt_key(npc_key)} 不存在")
    traits, chain = _follow_traits(ps, npc)
    f = traits.fields
    female = bool(f.get("female", npc.fields.get("female", False)))
    race = ps.get(f.get("race"), "RACE")
    origin = ps.origin_name(traits.key)
    app = Appearance(
        npc_label=f"{npc.edid} \"{npc.full}\" [{fmt_key(npc.key)}]",
        female=female,
        race_label=f"{race.edid} [{race.plugin}]" if race else f"未找到 {fmt_key(f.get('race'))}",
        origin_plugin=ps.origin_name(npc.key),
        winning_plugin=npc.plugin,
        traits_from=(f"{traits.edid} [{fmt_key(traits.key)}]" if traits is not npc else ""),
    )
    app.notes += chain

    geom, tint = facegen_paths(origin, traits.key[1])
    app.parts.append(Part("head_facegen", geom, f"FaceGen（定义插件 {origin}）"))
    app.facetint = Part("facetint", tint, f"FaceTint（定义插件 {origin}）")

    # Head parts: NPC PNAM + race defaults (only for types the NPC does not override)
    hp_keys = list(f.get("head_parts", []))
    npc_types = set()
    hdpts = []
    for k in hp_keys:
        h = ps.get(k, "HDPT")
        if h:
            hdpts.append(h)
            npc_types.add(h.fields.get("type"))
        else:
            app.notes.append(f"头部件 {fmt_key(k)} 未找到")
    if race:
        for k in race.fields.get("head_parts_f" if female else "head_parts_m", []):
            h = ps.get(k, "HDPT")
            if h and h.fields.get("type") not in npc_types:
                hdpts.append(h)
    seen = set()
    stack = list(hdpts)
    while stack:
        h = stack.pop(0)
        if h.key in seen:
            continue
        seen.add(h.key)
        for ek in h.fields.get("extra_parts", []):
            e = ps.get(ek, "HDPT")
            if e:
                stack.append(e)
        if h.fields.get("model"):
            tex = _txst_textures(ps, h.fields.get("texture_set"))
            app.parts.append(Part(
                f"head_part:{h.fields.get('type', '?')}",
                _norm(h.fields["model"], "meshes"),
                f"HDPT {h.edid} [{h.plugin}]",
                textures=tex,
            ))
            if h.fields.get("type") == "face" and tex and not app.face_textures:
                app.face_textures = tex
    if f.get("face_texture"):
        ft = _txst_textures(ps, f.get("face_texture"))
        if ft:
            app.face_textures = ft
            app.notes.append("面部贴图取自 NPC FTST")

    skin_key = f.get("skin") or (race.fields.get("skin") if race else None)
    label = "NPC WNAM" if f.get("skin") else "种族 WNAM"
    if skin_key:
        parts, notes = _armor_parts(ps, skin_key, race.key if race else None, female, label)
        app.parts += parts
        app.notes += notes
    else:
        app.notes.append("没有皮肤 ARMO（NPC/种族 WNAM 均为空）")
        app.parts += _missing_skin_parts("NPC/种族 WNAM 均为空")
    return app


class FileLocator:
    """Find Data-relative files in loose roots (highest priority first), then archives.

    ``extract`` is an optional callable(archive_path) -> extracted_root or "" used
    to unpack BSA/BA2 on demand (cached by caller).
    """

    def __init__(self, roots, archives=(), extract=None):
        self.roots = [Path(r) for r in roots if r]
        self.archives = list(archives)
        self.extract = extract
        self._extracted: dict[str, Path] = {}
        self._tried: set[str] = set()

    @staticmethod
    def _ci(root: Path, rel: str) -> Path | None:
        p = root / rel
        if p.is_file():
            return p
        # case-insensitive walk (Linux tests / odd casing)
        cur = root
        for seg in rel.split("/"):
            if not cur.is_dir():
                return None
            low = seg.lower()
            nxt = None
            try:
                for c in cur.iterdir():
                    if c.name.lower() == low:
                        nxt = c
                        break
            except OSError:
                return None
            if nxt is None:
                return None
            cur = nxt
        return cur if cur.is_file() else None

    def find(self, rel: str) -> tuple[str, str]:
        if not rel:
            return "", ""
        for r in self.roots:
            p = self._ci(r, rel)
            if p:
                return str(p), f"散文件 {r}"
        if self.extract:
            for a in self.archives:
                if a in self._extracted:
                    p = self._ci(self._extracted[a], rel)
                    if p:
                        return str(p), f"档案 {Path(a).name}"
                    continue
                if a in self._tried:
                    continue
                contains = getattr(self.extract, "contains", None)
                if contains is not None and not contains(a, rel):
                    continue
                self._tried.add(a)
                out = self.extract(a)
                if out:
                    self._extracted[a] = Path(out)
                    p = self._ci(Path(out), rel)
                    if p:
                        return str(p), f"档案 {Path(a).name}"
        return "", ""

    def fill(self, app: Appearance):
        if app.parts:
            app.parts[0].file, app.parts[0].file_from = self.find(app.parts[0].rel_path)
        app.has_facegen = bool(app.parts and app.parts[0].file)
        for p in app.parts + ([app.facetint] if app.facetint else []):
            if app.has_facegen and p.role.startswith("head_part:"):
                continue
            p.file, p.file_from = self.find(p.rel_path)
            for k, rel in p.textures.items():
                fp, _ = self.find(rel)
                if fp:
                    p.texture_files[k] = fp
        if not app.has_facegen:
            app.notes.insert(0, "未找到 FaceGen 头 NIF：已回退到 HDPT 种族/头部件。"
                                "外观可能不匹配；需核对游戏中的记录与资源，必要时重新生成 FaceGen。")
        fts = {}
        for k, rel in app.face_textures.items():
            fp, _ = self.find(rel)
            if fp:
                fts[k] = fp
        app.face_textures = {**app.face_textures, **{f"{k}_file": v for k, v in fts.items()}}
        return app


def archive_candidates(plugin_names, dirs) -> list[str]:
    """BSA/BA2 named after plugins (later plugins first), then vanilla 'Skyrim - *'."""
    out = []
    dirs = [Path(d) for d in dirs if d and Path(d).is_dir()]
    for name in reversed(list(plugin_names)):
        stem = Path(name).stem.lower()
        for d in dirs:
            try:
                for f in d.iterdir():
                    n = f.name.lower()
                    if f.suffix.lower() in (".bsa", ".ba2") and (n.startswith(stem + ".") or n.startswith(stem + " - ")):
                        out.append(str(f))
            except OSError:
                pass
    for d in dirs:
        try:
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in (".bsa", ".ba2") and f.name.lower().startswith("skyrim - ") and str(f) not in out:
                    out.append(str(f))
        except OSError:
            pass
    return out
