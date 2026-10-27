# SPDX-License-Identifier: MIT
"""BodySlide CLI + SliderPresets XML helpers.

CLI flags from the official wiki:
  https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Command‐line-arguments

  BodySlide [--groupbuild <groups>] [--build <outfits>] [--targetdir <path>]
            [--preset <name|file>] [--trimorphs] [--preview <files>]

Preset XML (SliderPresets/*.xml):
  <SliderPresets>
    <Preset name="..." set="...">
      <Group name="CBBE"/>
      <SetSlider name="Breasts" size="big" value="75"/>
      <SetSlider name="Breasts" size="small" value="50"/>
    </Preset>
  </SliderPresets>
"""

from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .deps import get_addon_prefs
from .paths import expand_path


BODYSIDE_WIKI_CLI = (
    "https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Command‐line-arguments"
)
BODYSIDE_NEXUS = "https://www.nexusmods.com/skyrimspecialedition/mods/201"


@dataclass(frozen=True)
class SliderValue:
    name: str
    size: str  # "big" | "small" | ""
    value: float  # BodySlide percent; presets can exceed the usual 0–100 range.


@dataclass
class BodySlidePreset:
    name: str
    set_name: str = ""
    groups: list[str] = field(default_factory=list)
    sliders: list[SliderValue] = field(default_factory=list)
    source_file: str = ""

    def slider_map_for_shapekeys(
        self, *, prefer_size: str = "big"
    ) -> dict[str, float]:
        """Collapse SetSlider rows to percentage/100 values for Blender shape keys.

        Prefer ``prefer_size`` (default big = high weight). If only the other
        size exists, use that. Values are BodySlide percentages / 100.
        """
        by_name: dict[str, dict[str, float]] = {}
        for s in self.sliders:
            bucket = by_name.setdefault(s.name, {})
            key = (s.size or "big").lower()
            bucket[key] = float(s.value)
        out: dict[str, float] = {}
        prefer = (prefer_size or "big").lower()
        other = "small" if prefer == "big" else "big"
        for name, sizes in by_name.items():
            raw = sizes.get(prefer)
            if raw is None:
                raw = sizes.get(other)
            if raw is None and sizes:
                raw = next(iter(sizes.values()))
            if raw is None:
                continue
            out[name] = float(raw) / 100.0
        return out


@dataclass
class BodySlideResult:
    ok: bool
    message: str
    command: list[str] | None = None
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    nif_candidates: list[str] = field(default_factory=list)


def missing_bodyslide_help() -> str:
    return (
        "未找到 BodySlide 可执行文件。\n"
        "1. 安装 BodySlide and Outfit Studio（SE）：\n"
        f"   {BODYSIDE_NEXUS}\n"
        "2. 在插件偏好 →「BodySlide 可执行文件」填入 BodySlide x64.exe "
        "（新版也可能叫 BodySlide.exe）。\n"
        "3. 「BodySlide 数据目录」指向含 SliderSets / SliderPresets / ShapeData "
        "的 CalienteTools/BodySlide 目录。\n"
        "CLI 文档：\n"
        f"   {BODYSIDE_WIKI_CLI}\n"
        "示例：\n"
        '  BodySlide --groupbuild "CBBE" --targetdir "C:\\Out" '
        '--preset "CBBE Curvy" --trimorphs'
    )


def resolve_bodyslide_exe(prefs=None) -> str:
    prefs = prefs if prefs is not None else get_addon_prefs()
    if prefs and getattr(prefs, "bodyslide_exe", ""):
        raw = prefs.bodyslide_exe
        try:
            import bpy

            path = bpy.path.abspath(raw)
        except Exception:
            path = os.path.expanduser(raw)
        if path and Path(path).is_file():
            return path
    for name in (
        "BodySlide x64.exe",
        "BodySlide.exe",
        "BodySlideX64.exe",
        "BodySlide",
    ):
        from shutil import which

        found = which(name)
        if found:
            return found
    return ""


def resolve_bodyslide_data_dir(prefs=None) -> str:
    prefs = prefs if prefs is not None else get_addon_prefs()
    if prefs and getattr(prefs, "bodyslide_data_dir", ""):
        return expand_path(prefs.bodyslide_data_dir)
    exe = resolve_bodyslide_exe(prefs)
    if exe:
        # Typical layout: .../CalienteTools/BodySlide/BodySlide x64.exe
        parent = Path(exe).resolve().parent
        if (parent / "SliderPresets").is_dir() or (parent / "SliderSets").is_dir():
            return str(parent)
    return ""


def slider_presets_dir(data_dir: str | None = None, prefs=None) -> Path | None:
    root = data_dir or resolve_bodyslide_data_dir(prefs)
    if not root:
        return None
    p = Path(expand_path(root)) / "SliderPresets"
    return p if p.is_dir() else None


def list_preset_xml_files(data_dir: str | None = None, prefs=None) -> list[Path]:
    folder = slider_presets_dir(data_dir, prefs)
    if folder is None:
        return []
    return sorted(folder.glob("*.xml"), key=lambda p: p.name.lower())


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_preset_xml(
    filepath: str | Path, *, preset_name: str | None = None
) -> list[BodySlidePreset]:
    """Parse a SliderPresets XML file into BodySlidePreset objects."""
    path = Path(expand_path(str(filepath)))
    if not path.is_file():
        raise FileNotFoundError(f"预设 XML 不存在：{path}")
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValueError(f"无法解析 BodySlide 预设 XML：{exc}") from exc

    root = tree.getroot()
    presets: list[BodySlidePreset] = []
    nodes: Iterable[ET.Element]
    if _local(root.tag) == "Preset":
        nodes = (root,)
    else:
        nodes = [c for c in root if _local(c.tag) == "Preset"]

    for node in nodes:
        name = node.attrib.get("name") or path.stem
        if preset_name and name != preset_name:
            continue
        groups = [
            c.attrib.get("name", "")
            for c in node
            if _local(c.tag) == "Group" and c.attrib.get("name")
        ]
        sliders: list[SliderValue] = []
        for c in node:
            if _local(c.tag) != "SetSlider":
                continue
            sname = c.attrib.get("name") or ""
            if not sname:
                continue
            raw = c.attrib.get("value", "0")
            try:
                val = float(raw)
            except ValueError:
                continue
            sliders.append(
                SliderValue(
                    name=sname,
                    size=(c.attrib.get("size") or "").lower(),
                    value=val,
                )
            )
        presets.append(
            BodySlidePreset(
                name=name,
                set_name=node.attrib.get("set") or "",
                groups=groups,
                sliders=sliders,
                source_file=str(path),
            )
        )
    return presets


def list_preset_names(data_dir: str | None = None, prefs=None) -> list[tuple[str, str]]:
    """Return [(preset_name, xml_path), ...] from SliderPresets."""
    out: list[tuple[str, str]] = []
    for xml_path in list_preset_xml_files(data_dir, prefs):
        try:
            for preset in parse_preset_xml(xml_path):
                out.append((preset.name, str(xml_path)))
        except (OSError, ValueError, ET.ParseError):
            continue
    out.sort(key=lambda t: t[0].lower())
    return out


def find_preset(
    name_or_path: str,
    *,
    data_dir: str | None = None,
    prefs=None,
) -> BodySlidePreset | None:
    """Resolve by XML path, ``file.xml?PresetName``, or installed preset name."""
    raw = (name_or_path or "").strip()
    if not raw:
        return None

    preset_filter: str | None = None
    path_part = raw
    if "?" in raw and not raw.lower().endswith(".xml"):
        # file.xml?Name  OR  we still allow Name-only below
        pass
    if ".xml" in raw.lower():
        if "?" in raw:
            path_part, preset_filter = raw.split("?", 1)
            preset_filter = preset_filter.strip() or None
        else:
            path_part = raw
        path = Path(expand_path(path_part))
        if path.is_file():
            presets = parse_preset_xml(path, preset_name=preset_filter)
            return presets[0] if presets else None

    # Search by preset name across SliderPresets
    for pname, xml_path in list_preset_names(data_dir, prefs):
        if pname == raw:
            presets = parse_preset_xml(xml_path, preset_name=pname)
            return presets[0] if presets else None
    # Case-insensitive fallback
    lower = raw.lower()
    for pname, xml_path in list_preset_names(data_dir, prefs):
        if pname.lower() == lower:
            presets = parse_preset_xml(xml_path, preset_name=pname)
            return presets[0] if presets else None
    return None


def build_cli_command(
    exe: str,
    *,
    groups: str = "",
    outfits: str = "",
    target_dir: str = "",
    preset: str = "",
    trimorphs: bool = False,
) -> list[str]:
    """Build argv matching official BodySlide CLI."""
    cmd = [exe]
    groups = (groups or "").strip()
    outfits = (outfits or "").strip()
    if groups:
        cmd.extend(["--groupbuild", groups])
    if outfits:
        cmd.extend(["--build", outfits])
    if target_dir:
        # Wiki: path separator appended automatically if missing; still pass as-is.
        cmd.extend(["--targetdir", target_dir])
    if preset:
        cmd.extend(["--preset", preset])
    if trimorphs:
        cmd.append("--trimorphs")
    return cmd


def run_bodyslide_build(
    *,
    groups: str = "",
    outfits: str = "",
    target_dir: str = "",
    preset: str = "",
    trimorphs: bool = False,
    prefs=None,
    timeout: int = 1800,
) -> BodySlideResult:
    prefs = prefs if prefs is not None else get_addon_prefs()
    exe = resolve_bodyslide_exe(prefs)
    if not exe or not Path(exe).is_file():
        return BodySlideResult(False, missing_bodyslide_help())

    if not (groups or "").strip() and not (outfits or "").strip():
        return BodySlideResult(
            False,
            "请填写要构建的 Group（--groupbuild）或项目/服装名（--build）。"
            "例如 Group：CBBE ；项目：CBBE Body。",
        )

    dest = expand_path(target_dir) if target_dir else ""
    if dest:
        try:
            Path(dest).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return BodySlideResult(False, f"无法创建输出目录：{exc}")

    cmd = build_cli_command(
        str(Path(exe)),
        groups=groups,
        outfits=outfits,
        target_dir=dest,
        preset=(preset or "").strip(),
        trimorphs=bool(trimorphs),
    )

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # BodySlide reads SliderSets from its install / game data; cwd = data dir helps.
    cwd = resolve_bodyslide_data_dir(prefs) or str(Path(exe).parent)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
            cwd=cwd if cwd and Path(cwd).is_dir() else None,
        )
    except FileNotFoundError:
        return BodySlideResult(False, missing_bodyslide_help(), command=cmd)
    except subprocess.TimeoutExpired:
        return BodySlideResult(
            False,
            f"BodySlide 构建超时（>{timeout}s）。可在外部终端手动运行："
            f" {' '.join(cmd)}",
            command=cmd,
        )
    except OSError as exc:
        return BodySlideResult(False, f"无法启动 BodySlide：{exc}", command=cmd)

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        detail = stderr or stdout or f"exit={proc.returncode}"
        return BodySlideResult(
            False,
            f"BodySlide 构建失败：{detail}",
            command=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    nifs: list[str] = []
    if dest:
        nifs = [
            str(p)
            for p in sorted(
                Path(dest).rglob("*.nif"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:40]
        ]

    msg = "BodySlide 构建完成"
    if dest:
        msg += f" → {dest}"
    if nifs:
        msg += f"（发现 {len(nifs)} 个 NIF，最近：{Path(nifs[0]).name}）"
    elif dest:
        msg += "（输出目录暂未扫到 .nif：请确认 Group/项目名，或到 BodySlide 里核对输出路径）"
    return BodySlideResult(
        True,
        msg,
        command=cmd,
        returncode=0,
        stdout=stdout,
        stderr=stderr,
        nif_candidates=nifs,
    )


def apply_preset_to_mesh_shapekeys(
    obj,
    preset: BodySlidePreset,
    *,
    prefer_size: str = "big",
    create_missing: bool = False,
) -> tuple[list[str], list[str], str]:
    """Apply preset slider values to matching shape keys on a Mesh object.

    Returns (matched, unmatched, message). Does **not** create missing keys
    unless create_missing (always False for BodySlide — morphs must come from TRI).
    """
    if obj is None or getattr(obj, "type", None) != "MESH":
        return [], [], "请选中一个 Mesh 物体（已导入的身体，且带 BodySlide TRI 形态键）。"

    keys = getattr(obj.data, "shape_keys", None)
    if keys is None or not getattr(keys, "key_blocks", None):
        return (
            [],
            [],
            "当前 Mesh 没有 Shape Keys。请先用 BodySlide 构建并勾选 --trimorphs，"
            "或「导入 BodySlide TRI」，再应用预设。这不是完整 OSD 求解。",
        )

    blocks = keys.key_blocks
    # Map lowercase / exact names → key block
    by_exact = {kb.name: kb for kb in blocks}
    by_lower = {kb.name.lower(): kb for kb in blocks}
    # PyNifly prefixes BodySlide TRIP morph names with ">".
    for kb in blocks:
        plain = kb.name.removeprefix(">")
        by_exact.setdefault(plain, kb)
        by_lower.setdefault(plain.lower(), kb)

    desired = preset.slider_map_for_shapekeys(prefer_size=prefer_size)
    matched: list[str] = []
    unmatched: list[str] = []

    for sname, value in desired.items():
        kb = by_exact.get(sname) or by_lower.get(sname.lower())
        if kb is None:
            unmatched.append(sname)
            continue
        if kb.name == "Basis":
            continue
        kb.slider_min = min(kb.slider_min, value)
        kb.slider_max = max(kb.slider_max, value)
        kb.value = float(value)
        matched.append(f"{kb.name}={value:.2f}")

    msg = (
        f"预设「{preset.name}」：匹配 {len(matched)} 个 Shape Key，"
        f"未匹配 {len(unmatched)} 个。"
    )
    if unmatched and not matched:
        msg += " 名称对不上时，确认 TRI 来自同一 BodySlide 身体（如 CBBE）。"
    elif unmatched:
        preview = ", ".join(unmatched[:8])
        if len(unmatched) > 8:
            preview += "…"
        msg += f" 未匹配：{preview}"
    if create_missing:
        msg += "（未创建缺失键）"
    return matched, unmatched, msg


def find_recent_nifs(directory: str, limit: int = 20) -> list[str]:
    root = Path(expand_path(directory)) if directory else None
    if root is None or not root.is_dir():
        return []
    return [
        str(p)
        for p in sorted(root.rglob("*.nif"), key=lambda p: p.stat().st_mtime, reverse=True)[
            :limit
        ]
    ]


# Common BodySlide / CBBE / 3BA hand & foot mesh basenames (prefer _1 = high weight).
_HAND_FOOT_CANDIDATES = (
    ("hands", (
        "femalehands_1.nif",
        "femalehands_0.nif",
        "malehands_1.nif",
        "malehands_0.nif",
        "hands_1.nif",
        "hands_0.nif",
    )),
    ("feet", (
        "femalefeet_1.nif",
        "femalefeet_0.nif",
        "malefeet_1.nif",
        "malefeet_0.nif",
        "feet_1.nif",
        "feet_0.nif",
    )),
)


def find_hands_feet_nifs(root: str | Path | None, *, prefer_female: bool = True) -> dict[str, str]:
    """Search build output / Data-like tree for hands & feet NIFs.

    Returns ``{"hands": path, "feet": path}`` for any found. Prefers ``*_1.nif``
    (high weight) and female names when ``prefer_female``.
    """
    out: dict[str, str] = {}
    if not root:
        return out
    base = Path(expand_path(str(root)))
    if not base.is_dir():
        return out

    # Flatten candidate order with gender preference
    for kind, names in _HAND_FOOT_CANDIDATES:
        ordered = list(names)
        if prefer_female:
            ordered = [n for n in ordered if n.startswith("female")] + [
                n for n in ordered if not n.startswith("female")
            ]
        else:
            ordered = [n for n in ordered if n.startswith("male")] + [
                n for n in ordered if not n.startswith("male")
            ]
        found = None
        for name in ordered:
            # Exact basename match anywhere under root (depth-limited walk)
            matches = list(base.rglob(name))
            if matches:
                # Prefer under meshes/
                matches.sort(
                    key=lambda p: (
                        0 if "meshes" in p.parts else 1,
                        -p.stat().st_mtime,
                    )
                )
                found = str(matches[0])
                break
        if found:
            out[kind] = found
    return out

