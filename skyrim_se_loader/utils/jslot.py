# SPDX-License-Identifier: MIT
"""RaceMenu .jslot preset reader — display / approximate Shape Key export only.

These files are **RaceMenu** JSON presets (not ECE CME_save). Typical top-level
keys: actor, bodyMorphs, faceTextures, headParts, morphs, tintInfo, version.

Blender cannot faithfully rebuild a RaceMenu face from jslot alone (sculpt /
tint / headPart FormIDs need the game). Use exported CharGen head NIF + facial
DDS for visuals; optionally try name-matched Shape Keys from bodyMorphs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# RaceMenu / engine head-part type ids (extended beyond vanilla 0–6).
_HEAD_PART_TYPE_NAMES = {
    0: "Misc/Head?",
    1: "Face/Head",
    2: "Eyes",
    3: "Hair",
    4: "FacialHair",
    5: "Scar",
    6: "Eyebrows",
    7: "Head?",
    8: "HeadExt",
    9: "HairExt",
    10: "EyesExt",
    11: "FacialHairExt",
    12: "ScarExt",
    13: "EyebrowsExt",
    14: "Mouth/Other",
    15: "Extra",
}


@dataclass
class JslotInfo:
    path: str = ""
    ok: bool = False
    error: str = ""
    format_hint: str = "RaceMenu .jslot"
    preset_name: str = ""
    version_fmt: str = ""
    weight: str = ""
    hair_color: str = ""
    head_texture: str = ""
    head_parts: list[str] = field(default_factory=list)
    body_morph_total: int = 0
    body_morph_xpmse: int = 0
    body_morph_non_xpmse: int = 0
    body_morph_sample: list[str] = field(default_factory=list)
    face_morph_custom: int = 0
    tint_count: int = 0
    face_texture_count: int = 0
    sculpt_hosts: list[str] = field(default_factory=list)
    top_keys: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    # name → float for Shape Key attempts (bodyMorphs non-XPMSE + optional custom face morphs)
    shapekey_candidates: dict[str, float] = field(default_factory=dict)


def _is_xpmse_name(name: str) -> bool:
    n = (name or "").casefold()
    return n.startswith("xpmse") or "xpmse" in n


def _body_morph_value(entry: dict) -> float | None:
    """RaceMenu bodyMorphs: {name, keys:[{key, value}, ...]} — take first numeric value."""
    keys = entry.get("keys")
    if isinstance(keys, list):
        for item in keys:
            if isinstance(item, dict) and "value" in item:
                try:
                    return float(item["value"])
                except (TypeError, ValueError):
                    continue
    if "value" in entry:
        try:
            return float(entry["value"])
        except (TypeError, ValueError):
            return None
    return None


def _format_hair_color(raw: Any) -> str:
    if raw is None:
        return ""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return str(raw)
    # ARGB uint32 style
    return f"0x{n & 0xFFFFFFFF:08X} ({n})"


def _head_part_label(item: dict) -> str:
    typ = item.get("type")
    try:
        typ_i = int(typ)
        typ_s = _HEAD_PART_TYPE_NAMES.get(typ_i, f"type{typ_i}")
    except (TypeError, ValueError):
        typ_s = str(typ)
    ident = item.get("formIdentifier") or item.get("editorId") or item.get("name")
    if not ident and item.get("formId") is not None:
        ident = f"formId={item.get('formId')}"
    return f"{typ_s}:{ident}"


def extract_shapekey_map(
    data: dict,
    *,
    include_face_custom: bool = True,
    include_xpmse: bool = False,
) -> dict[str, float]:
    """Build name→value map from bodyMorphs (+ optional morphs.custom).

    Values are as stored in jslot (often already ~-1..1 for bodyMorphs;
    face custom morphs may be outside 0–1). Caller should treat as approximate.
    """
    out: dict[str, float] = {}
    bm = data.get("bodyMorphs")
    if isinstance(bm, list):
        for entry in bm:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            if not include_xpmse and _is_xpmse_name(name):
                continue
            val = _body_morph_value(entry)
            if val is None:
                continue
            out[name] = val
    elif isinstance(bm, dict):
        for name, raw in bm.items():
            if not include_xpmse and _is_xpmse_name(str(name)):
                continue
            if isinstance(raw, (int, float)):
                out[str(name)] = float(raw)
            elif isinstance(raw, dict):
                val = _body_morph_value(raw)
                if val is not None:
                    out[str(name)] = val

    if include_face_custom:
        morphs = data.get("morphs")
        if isinstance(morphs, dict):
            custom = morphs.get("custom")
            if isinstance(custom, list):
                for entry in custom:
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get("name") or "").strip()
                    if not name:
                        continue
                    try:
                        out[name] = float(entry.get("value", 0.0))
                    except (TypeError, ValueError):
                        continue
    return out


def parse_jslot(filepath: str | Path) -> JslotInfo:
    info = JslotInfo(path=str(filepath or ""))
    if not filepath:
        info.error = "未选择 .jslot 文件"
        return info
    path = Path(str(filepath)).expanduser()
    if not path.is_file():
        info.error = f"找不到文件：{path}"
        return info
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        info.error = f"不是合法 JSON（RaceMenu .jslot）：{exc}"
        return info
    except OSError as exc:
        info.error = f"读取失败：{exc}"
        return info

    if not isinstance(data, dict):
        info.error = "jslot 根节点不是对象"
        return info

    info.ok = True
    info.format_hint = "RaceMenu .jslot（非 ECE CME_save）"
    info.top_keys = sorted(str(k) for k in data.keys())
    info.preset_name = path.stem

    ver = data.get("version")
    if isinstance(ver, dict):
        info.version_fmt = str(ver.get("formatVersion", ""))
    elif ver is not None:
        info.version_fmt = str(ver)

    actor = data.get("actor") if isinstance(data.get("actor"), dict) else {}
    info.weight = str(actor.get("weight", "")) if actor else ""
    info.hair_color = _format_hair_color(actor.get("hairColor")) if actor else ""
    info.head_texture = str(actor.get("headTexture") or "") if actor else ""

    hp = data.get("headParts")
    if isinstance(hp, list):
        for item in hp:
            if isinstance(item, dict):
                info.head_parts.append(_head_part_label(item))
            else:
                info.head_parts.append(str(item))

    bm = data.get("bodyMorphs")
    if isinstance(bm, list):
        info.body_morph_total = len(bm)
        xpmse_n = 0
        non_names: list[str] = []
        for entry in bm:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "")
            if _is_xpmse_name(name):
                xpmse_n += 1
            else:
                non_names.append(name)
        info.body_morph_xpmse = xpmse_n
        info.body_morph_non_xpmse = len(non_names)
        info.body_morph_sample = non_names[:12]
    elif isinstance(bm, dict):
        info.body_morph_total = len(bm)
        non = [k for k in bm if not _is_xpmse_name(str(k))]
        info.body_morph_xpmse = info.body_morph_total - len(non)
        info.body_morph_non_xpmse = len(non)
        info.body_morph_sample = [str(k) for k in non[:12]]

    morphs = data.get("morphs")
    if isinstance(morphs, dict):
        custom = morphs.get("custom")
        if isinstance(custom, list):
            info.face_morph_custom = len(custom)
        sculpt = morphs.get("sculpt")
        if isinstance(sculpt, list):
            for s in sculpt:
                if isinstance(s, dict) and s.get("host"):
                    info.sculpt_hosts.append(str(s["host"]))

    tint = data.get("tintInfo")
    if isinstance(tint, list):
        info.tint_count = len(tint)
    elif isinstance(tint, dict):
        info.tint_count = len(tint)

    ft = data.get("faceTextures")
    if isinstance(ft, list):
        info.face_texture_count = len(ft)
    elif isinstance(ft, dict):
        info.face_texture_count = len(ft)

    info.shapekey_candidates = extract_shapekey_map(data)

    lines = [
        f"格式: {info.format_hint}",
        f"文件: {path.name}"
        + (f"  formatVersion={info.version_fmt}" if info.version_fmt else ""),
        f"weight: {info.weight or '（无）'}",
        f"hairColor: {info.hair_color or '（无）'}",
        f"headTexture: {info.head_texture or '（无）'}",
        f"headParts: {len(info.head_parts)} 项"
        + (
            " — " + "; ".join(info.head_parts[:5])
            + ("…" if len(info.head_parts) > 5 else "")
            if info.head_parts
            else ""
        ),
        (
            f"bodyMorphs: 共 {info.body_morph_total}（XPMSE {info.body_morph_xpmse} / "
            f"非 XPMSE {info.body_morph_non_xpmse}）"
        ),
    ]
    if info.body_morph_sample:
        lines.append("非 XPMSE 样例: " + ", ".join(info.body_morph_sample[:8]))
    lines.append(f"face morphs.custom: {info.face_morph_custom}")
    lines.append(
        f"tintInfo 层数: {info.tint_count}；faceTextures: {info.face_texture_count}"
    )
    if info.sculpt_hosts:
        lines.append("sculpt TRI host: " + "; ".join(info.sculpt_hosts[:3]))
    lines.append(
        "限制: 不能在 Blender 完整还原 RaceMenu 捏脸；"
        "请用导出的头雕 NIF + 面部 DDS。ECE 请导出头 NIF，不要用 CME_save。"
    )
    lines.append(
        f"可尝试 Shape Key 映射条目: {len(info.shapekey_candidates)}"
        "（名称匹配时近似；≠ 游戏内完整合成）"
    )
    info.summary_lines = lines
    return info


def format_jslot_status(info: JslotInfo) -> str:
    if not info.ok:
        return info.error or "jslot 解析失败"
    return (
        f"RaceMenu jslot | weight={info.weight} | hair={info.hair_color or '-'} | "
        f"HP={len(info.head_parts)} | bodyMorph非XPMSE={info.body_morph_non_xpmse} | "
        f"tint={info.tint_count}"
    )


def export_shapekey_map_json(info: JslotInfo, out_path: str | Path) -> str:
    """Write shapekey candidate map to JSON; return absolute path string."""
    path = Path(str(out_path)).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": info.path,
        "note": (
            "Approximate RaceMenu bodyMorphs/custom → Shape Key name map. "
            "Only apply when mesh has matching shape key names. "
            "Does NOT restore full in-game face/tint/sculpt."
        ),
        "values": info.shapekey_candidates,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.resolve())
