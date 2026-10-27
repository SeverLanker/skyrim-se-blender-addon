# SPDX-License-Identifier: MIT
"""Find plugins.txt / loadorder.txt (MO2 profile or vanilla) and build plugin path lists."""

from __future__ import annotations

import os
from pathlib import Path

BASE_MASTERS = ("Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm")
PLUGIN_EXT = (".esm", ".esp", ".esl")


def default_appdata_dir() -> str:
    la = os.environ.get("LOCALAPPDATA", "")
    return str(Path(la) / "Skyrim Special Edition") if la else ""


def _read_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def parse_plugins_txt(path) -> list[str]:
    """Active plugins in order. SSE format: '*Name.esp' = active; lines without '*' are inactive."""
    lines = _read_lines(Path(path))
    has_star = any(ln.startswith("*") for ln in lines)
    out = []
    for ln in lines:
        if has_star:
            if ln.startswith("*"):
                out.append(ln[1:].strip())
        else:
            out.append(ln)
    return out


def parse_manual_list(text: str) -> list[str]:
    out = []
    for part in (text or "").replace(";", "\n").replace(",", "\n").splitlines():
        part = part.strip().lstrip("*").strip()
        if part:
            out.append(part)
    return out


def implicit_masters(data_dir: str | None) -> list[str]:
    out = list(BASE_MASTERS)
    if data_dir:
        ccc = Path(data_dir).parent / "Skyrim.ccc"
        out += _read_lines(ccc)
    return out


def build_order(profile_dir: str = "", data_dir: str = "", manual: str = "") -> tuple[list[str], str]:
    """Return (ordered plugin names, source description)."""
    if manual.strip():
        names = parse_manual_list(manual)
        src = "手动列表"
    else:
        names, src = [], ""
        cands = [Path(profile_dir)] if profile_dir else []
        if default_appdata_dir():
            cands.append(Path(default_appdata_dir()))
        for d in cands:
            lo, pt = d / "loadorder.txt", d / "plugins.txt"
            if pt.is_file():
                active = parse_plugins_txt(pt)
                if lo.is_file():
                    act = {a.lower() for a in active}
                    order = [n for n in _read_lines(lo) if n.lower() in act or n in BASE_MASTERS]
                    tail = [a for a in active if a.lower() not in {o.lower() for o in order}]
                    names = order + tail
                    src = f"{lo} + {pt.name}"
                else:
                    names = active
                    src = str(pt)
                break
    # Implicit masters first (dedupe, keep first position)
    final, seen = [], set()
    for n in implicit_masters(data_dir) + names:
        if n.lower() not in seen:
            seen.add(n.lower())
            final.append(n)
    return final, src or "仅隐式主文件"


def find_plugin_files(names, search_dirs) -> tuple[list[str], list[str]]:
    """Resolve plugin names to files. search_dirs: highest priority first. Returns (paths, missing)."""
    index: dict[str, str] = {}
    for d in reversed([Path(x) for x in search_dirs if x]):
        if not d.is_dir():
            continue
        try:
            for f in d.iterdir():
                if f.suffix.lower() in PLUGIN_EXT:
                    index[f.name.lower()] = str(f)  # higher priority dirs overwrite
        except OSError:
            continue
    found, missing = [], []
    for n in names:
        p = index.get(n.lower())
        (found.append(p) if p else missing.append(n))
    return found, missing


def mo2_roots(profile_dir: str) -> tuple[list[str], str]:
    """From an MO2 profile dir return (mod roots highest-priority first incl. overwrite, instance dir).

    MO2 modlist.txt: first line = highest priority; '+' enabled, '-' disabled.
    Layout: <instance>/profiles/<name>/modlist.txt, <instance>/mods/<mod>, <instance>/overwrite.
    """
    if not profile_dir:
        return [], ""
    prof = Path(profile_dir)
    inst = prof.parent.parent
    roots = [str(inst / "overwrite")]
    for ln in _read_lines(prof / "modlist.txt"):
        if ln.startswith("+") and not ln.endswith("_separator"):
            roots.append(str(inst / "mods" / ln[1:].strip()))
    return roots, str(inst)
