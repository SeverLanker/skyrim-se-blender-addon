# SPDX-License-Identifier: MIT
"""Minimal pure-Python TES4 (Skyrim SE) plugin reader — no bpy.

Reads only the record types needed for NPC appearance:
NPC_, RACE, HDPT, ARMO, ARMA, TXST. Records with the compressed flag are
zlib-inflated. FormIDs are resolved to global keys ``(plugin_lower, local_id)``
via the plugin's MAST list; ESL / light-flagged plugins use 12-bit local IDs.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

WANTED = (b"NPC_", b"RACE", b"HDPT", b"ARMO", b"ARMA", b"TXST")

FLAG_MASTER = 0x1
FLAG_LOCALIZED = 0x80
FLAG_LIGHT = 0x200
FLAG_COMPRESSED = 0x00040000

ACBS_FEMALE = 0x1
TPL_USE_TRAITS = 0x0001

HDPT_TYPES = {0: "misc", 1: "face", 2: "eyes", 3: "hair", 4: "facial_hair", 5: "scar", 6: "eyebrows"}

# BOD2 / BODT biped slot bits
SLOT_HEAD = 1 << 1  # 31 hair, 30 head = bit0; keep for reference
SLOT_BODY = 1 << 2  # 32
SLOT_HANDS = 1 << 3  # 33
SLOT_FEET = 1 << 7  # 37

FormKey = tuple  # (plugin_lower: str, local_id: int)


class EspError(Exception):
    pass


def fmt_key(key) -> str:
    if not key:
        return "-"
    return f"{key[0]}|{key[1]:08X}"


@dataclass
class Record:
    sig: str
    key: FormKey
    plugin: str  # plugin file name that contains this (possibly overriding) record
    origin: str  # plugin that originally defines the form
    raw_formid: int
    edid: str = ""
    full: str = ""
    fields: dict = field(default_factory=dict)


@dataclass
class Plugin:
    name: str
    path: str
    masters: list = field(default_factory=list)
    is_master: bool = False
    is_light: bool = False
    localized: bool = False
    records: dict = field(default_factory=dict)  # key -> Record

    def resolve(self, formid: int) -> FormKey | None:
        """Map a file-local FormID to a global (plugin_lower, local_id) key."""
        if formid == 0:
            return None
        idx = (formid >> 24) & 0xFF
        if idx < len(self.masters):
            # Masters' own lightness is unknown here; 24-bit local ID is correct for
            # full masters, and for ESL masters the upper bits are 0 anyway.
            return (self.masters[idx].lower(), formid & 0xFFFFFF)
        # self-reference (idx == len(masters), or anything beyond — treat as self)
        local = formid & (0xFFF if self.is_light else 0xFFFFFF)
        return (self.name.lower(), local)


# ---------------------------------------------------------------- low level

def _iter_subrecords(data: bytes):
    pos = 0
    n = len(data)
    big = None
    while pos + 6 <= n:
        sig = data[pos : pos + 4]
        size = struct.unpack_from("<H", data, pos + 4)[0]
        pos += 6
        if big is not None:
            size = big
            big = None
        if sig == b"XXXX":
            big = struct.unpack_from("<I", data, pos)[0]
            pos += size
            continue
        yield sig.decode("ascii", "replace"), data[pos : pos + size]
        pos += size


def _zstr(b: bytes) -> str:
    b = b.split(b"\0", 1)[0]
    for enc in ("utf-8", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1")


def _u32(b: bytes, off: int = 0) -> int:
    return struct.unpack_from("<I", b, off)[0] if len(b) >= off + 4 else 0


def _parse_header(path: Path, buf: bytes) -> Plugin:
    if buf[:4] != b"TES4":
        raise EspError(f"{path.name}: 不是 TES4 插件（缺 TES4 头）")
    size, flags = struct.unpack_from("<II", buf, 4)
    data = buf[24 : 24 + size]
    p = Plugin(name=path.name, path=str(path))
    p.is_master = bool(flags & FLAG_MASTER) or path.suffix.lower() in (".esm", ".esl")
    p.is_light = bool(flags & FLAG_LIGHT) or path.suffix.lower() == ".esl"
    p.localized = bool(flags & FLAG_LOCALIZED)
    for sig, d in _iter_subrecords(data):
        if sig == "MAST":
            p.masters.append(_zstr(d))
    return p


def _decode_record(sig: bytes, flags: int, data: bytes) -> bytes:
    if flags & FLAG_COMPRESSED:
        if len(data) < 4:
            raise EspError("压缩记录长度异常")
        try:
            return zlib.decompress(data[4:])
        except zlib.error as exc:
            raise EspError(f"zlib 解压失败（{sig!r}）：{exc}") from exc
    return data


def _parse_fields(plugin: Plugin, sig: str, data: bytes, rec: Record):
    f = rec.fields
    R = plugin.resolve
    if sig == "NPC_":
        f.setdefault("head_parts", [])
        for s, d in _iter_subrecords(data):
            if s == "EDID":
                rec.edid = _zstr(d)
            elif s == "FULL":
                rec.full = f"<lstring {_u32(d):08X}>" if plugin.localized and len(d) == 4 else _zstr(d)
            elif s == "ACBS" and len(d) >= 20:
                flags = _u32(d)
                f["female"] = bool(flags & ACBS_FEMALE)
                f["template_flags"] = struct.unpack_from("<H", d, 18)[0]
            elif s == "RNAM":
                f["race"] = R(_u32(d))
            elif s == "PNAM":
                k = R(_u32(d))
                if k:
                    f["head_parts"].append(k)
            elif s == "WNAM":
                f["skin"] = R(_u32(d))
            elif s == "HCLF":
                f["hair_color"] = R(_u32(d))
            elif s == "FTST":
                f["face_texture"] = R(_u32(d))
            elif s == "TPLT":
                f["template"] = R(_u32(d))
    elif sig == "RACE":
        sex = None  # None until MNAM/FNAM seen
        f.update({"head_parts_m": [], "head_parts_f": [], "skeleton_m": "", "skeleton_f": "",
                  "body_m": "", "body_f": ""})
        in_head = False
        for s, d in _iter_subrecords(data):
            if s == "EDID":
                rec.edid = _zstr(d)
            elif s == "FULL":
                rec.full = f"<lstring {_u32(d):08X}>" if plugin.localized and len(d) == 4 else _zstr(d)
            elif s == "WNAM":
                f["skin"] = R(_u32(d))
            elif s == "RNAM":
                f["armor_race"] = R(_u32(d))
            elif s == "NAM0":
                in_head = True
            elif s == "NAM1":
                in_head = False
            elif s == "MNAM":
                sex = "m"
            elif s == "FNAM":
                sex = "f"
            elif s == "ANAM" and sex and not in_head:
                f[f"skeleton_{sex}"] = _zstr(d)
            elif s == "MODL" and sex and not in_head and not f[f"body_{sex}"]:
                f[f"body_{sex}"] = _zstr(d)
            elif s == "HEAD" and sex and in_head:
                k = R(_u32(d))
                if k:
                    f[f"head_parts_{sex}"].append(k)
    elif sig == "HDPT":
        f["extra_parts"] = []
        for s, d in _iter_subrecords(data):
            if s == "EDID":
                rec.edid = _zstr(d)
            elif s == "MODL":
                f["model"] = _zstr(d)
            elif s == "PNAM":
                f["type"] = HDPT_TYPES.get(_u32(d), str(_u32(d)))
            elif s == "HNAM":
                k = R(_u32(d))
                if k:
                    f["extra_parts"].append(k)
            elif s == "TNAM":
                f["texture_set"] = R(_u32(d))
    elif sig == "ARMO":
        f["addons"] = []
        for s, d in _iter_subrecords(data):
            if s == "EDID":
                rec.edid = _zstr(d)
            elif s == "MODL" and len(d) == 4:
                k = R(_u32(d))
                if k:
                    f["addons"].append(k)
            elif s == "RNAM":
                f["race"] = R(_u32(d))
            elif s in ("BOD2", "BODT"):
                f["slots"] = _u32(d)
    elif sig == "ARMA":
        f["extra_races"] = []
        for s, d in _iter_subrecords(data):
            if s == "EDID":
                rec.edid = _zstr(d)
            elif s == "RNAM":
                f["race"] = R(_u32(d))
            elif s == "DNAM" and len(d) >= 2:
                f["priority_m"], f["priority_f"] = d[0], d[1]
            elif s == "MODL" and len(d) == 4:
                k = R(_u32(d))
                if k:
                    f["extra_races"].append(k)
            elif s == "MOD2":
                f["model_m"] = _zstr(d)
            elif s == "MOD3":
                f["model_f"] = _zstr(d)
            elif s == "NAM0":
                f["skin_tex_m"] = R(_u32(d))
            elif s == "NAM1":
                f["skin_tex_f"] = R(_u32(d))
            elif s in ("BOD2", "BODT"):
                f["slots"] = _u32(d)
    elif sig == "TXST":
        f["textures"] = {}
        for s, d in _iter_subrecords(data):
            if s == "EDID":
                rec.edid = _zstr(d)
            elif s.startswith("TX0") and len(s) == 4:
                f["textures"][s] = _zstr(d)


def _walk(plugin: Plugin, buf: bytes, start: int, end: int, wanted: tuple):
    pos = start
    while pos + 24 <= end:
        sig = buf[pos : pos + 4]
        if sig == b"GRUP":
            gsize = struct.unpack_from("<I", buf, pos + 4)[0]
            label = buf[pos + 8 : pos + 12]
            gtype = struct.unpack_from("<i", buf, pos + 12)[0]
            if gsize < 24:
                raise EspError(f"{plugin.name}: GRUP 尺寸异常 @ {pos}")
            if gtype != 0 or label in wanted:
                _walk(plugin, buf, pos + 24, min(pos + gsize, end), wanted)
            pos += gsize
            continue
        size, flags, formid = struct.unpack_from("<III", buf, pos + 4)
        body = buf[pos + 24 : pos + 24 + size]
        pos += 24 + size
        if sig not in wanted:
            continue
        data = _decode_record(sig, flags, body)
        key = plugin.resolve(formid)
        if key is None:
            continue
        s = sig.decode("ascii")
        rec = Record(sig=s, key=key, plugin=plugin.name, origin=key[0], raw_formid=formid)
        _parse_fields(plugin, s, data, rec)
        plugin.records[key] = rec


def read_plugin(path, wanted: tuple = WANTED) -> Plugin:
    path = Path(path)
    buf = path.read_bytes()
    plugin = _parse_header(path, buf)
    hsize = struct.unpack_from("<I", buf, 4)[0]
    _walk(plugin, buf, 24 + hsize, len(buf), tuple(wanted))
    return plugin


# ---------------------------------------------------------------- load order

class PluginSet:
    """Merged view of several plugins in load order; last override wins."""

    def __init__(self):
        self.plugins: list[Plugin] = []
        self.records: dict = {}  # key -> winning Record
        self.history: dict = {}  # key -> [plugin names defining/overriding]
        self.errors: list[str] = []
        self.origin_names: dict = {}  # lower -> real-cased plugin name
        self._runtime_bases = None

    def add(self, plugin: Plugin):
        self._runtime_bases = None
        self.plugins.append(plugin)
        self.origin_names[plugin.name.lower()] = plugin.name
        for m in plugin.masters:
            self.origin_names.setdefault(m.lower(), m)
        for key, rec in plugin.records.items():
            self.records[key] = rec
            self.history.setdefault(key, []).append(plugin.name)

    def get(self, key, sig: str | None = None):
        if not key:
            return None
        r = self.records.get(tuple(key))
        if r is not None and sig and r.sig != sig:
            return None
        return r

    def origin_name(self, key) -> str:
        return self.origin_names.get(key[0], key[0])

    def runtime_formid(self, key):
        """Map an origin/local key using this loaded full/light plugin order."""
        if self._runtime_bases is None:
            bases, full, light = {}, 0, 0
            for plugin in self.plugins:
                if plugin.is_light:
                    if light < 0x1000:
                        bases[plugin.name.lower()] = (0xFE000000 | light << 12, 0xFFF)
                    light += 1
                else:
                    if full < 0xFE:
                        bases[plugin.name.lower()] = (full << 24, 0xFFFFFF)
                    full += 1
            self._runtime_bases = bases
        base = self._runtime_bases.get(key[0]) if key else None
        if base is None or key[1] > base[1]:
            return None
        return base[0] | key[1]

    def search(self, query: str, sig: str = "NPC_", limit: int = 200):
        q = (query or "").strip().casefold()
        hexq = q.removeprefix("0x")
        number = (int(hexq, 16) if 0 < len(hexq) <= 8
                  and all(c in "0123456789abcdef" for c in hexq) else None)
        out = []
        for key, r in self.records.items():
            if r.sig != sig:
                continue
            names = (r.edid.casefold(), r.full.casefold())
            ids = (key[1], r.raw_formid, self.runtime_formid(key))
            if q:
                if not (any(q in h for h in names)
                        or any(hexq in f"{v:08x}" for v in ids if v is not None)):
                    continue
            exact = bool(q) and (q in names or number is not None and number in ids)
            out.append((0 if exact else 1, r))
        out.sort(key=lambda item: (item[0], item[1].edid.casefold(), item[1].key))
        return [r for _, r in out[:max(0, limit)]]


def load_plugins(paths, wanted: tuple = WANTED, progress=None) -> PluginSet:
    ps = PluginSet()
    for p in paths:
        try:
            ps.add(read_plugin(p, wanted))
        except (OSError, EspError, struct.error) as exc:
            ps.errors.append(f"{Path(p).name}: {exc}")
        if progress:
            progress(p)
    return ps
