# SPDX-License-Identifier: MIT
"""Path helpers."""

from __future__ import annotations

import os
from pathlib import Path


def expand_path(path: str) -> str:
    if not path:
        return ""
    return os.path.abspath(bpy_path_resolve(path))


def bpy_path_resolve(path: str) -> str:
    # Avoid importing bpy at module import time for unit-testability.
    try:
        import bpy

        return bpy.path.abspath(path)
    except Exception:
        return os.path.expanduser(path)


def ensure_file(path: str, extensions: tuple[str, ...] | None = None) -> Path:
    resolved = expand_path(path)
    if not resolved:
        raise FileNotFoundError("路径为空。请在侧栏选择文件。")
    p = Path(resolved)
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在：{p}\n请确认已从 BA2 解出，或路径无误。")
    if extensions:
        exts = tuple(e.lower() for e in extensions)
        if p.suffix.lower() not in exts:
            raise ValueError(f"期望扩展名 {exts}，实际为 {p.suffix}")
    return p


def ensure_dir(path: str, create: bool = True) -> Path:
    resolved = expand_path(path)
    if not resolved:
        raise FileNotFoundError("目录路径为空")
    p = Path(resolved)
    if create:
        p.mkdir(parents=True, exist_ok=True)
    if not p.is_dir():
        raise NotADirectoryError(f"不是目录：{p}")
    return p


def suggest_skeleton_under_data(data_root: str) -> str:
    if not data_root:
        return ""
    root = Path(expand_path(data_root))
    candidate = (
        root
        / "meshes"
        / "actors"
        / "character"
        / "character assets"
        / "skeleton.hkx"
    )
    return str(candidate) if candidate.is_file() else ""


# --- Skeleton presets (Vanilla / XPMSE) ---

# Relative paths under a Skyrim SE Data root. XPMSE normally *overwrites*
# these same game paths when installed as a mod; keep separate prefs so users
# can point Vanilla at an unpacked BSA tree and XPMSE at a Mod Organizer
# overwrite / mod folder.
VANILLA_SKELETON_REL = {
    "male": "meshes/actors/character/character assets/skeleton.hkx",
    "female": "meshes/actors/character/character assets female/skeleton_female.hkx",
}

# XPMSE (XP32 Maximum Skeleton Special Extended) ships replacement HKX at the
# same relative locations as vanilla when deployed to Data.
XPMSE_SKELETON_REL = {
    "male": "meshes/actors/character/character assets/skeleton.hkx",
    "female": "meshes/actors/character/character assets female/skeleton_female.hkx",
}

SKELETON_PATH_HINTS = (
    "Vanilla 男: meshes/actors/character/character assets/skeleton.hkx",
    "Vanilla 女: meshes/actors/character/character assets female/skeleton_female.hkx",
    "XPMSE：安装后通常覆盖上述同路径；请指向 Mod 的 loose files，勿只用原版 BSA 内骨骼。",
)


def join_data_rel(data_root: str, rel: str) -> str:
    if not data_root or not rel:
        return ""
    root = Path(expand_path(data_root))
    return str(root / Path(rel.replace("\\", "/")))


def resolve_skeleton_candidate(
    *,
    preset: str,
    gender: str,
    prefs=None,
    data_root: str = "",
) -> str:
    """Pick a skeleton.hkx path from prefs / Data root for Vanilla or XPMSE.

    ``preset``: VANILLA | XPMSE | CUSTOM
    ``gender``: male | female
    """
    preset = (preset or "VANILLA").upper()
    gender = (gender or "female").lower()
    if gender not in ("male", "female"):
        gender = "female"

    if prefs is not None:
        if preset == "VANILLA":
            key = (
                "vanilla_skeleton_male"
                if gender == "male"
                else "vanilla_skeleton_female"
            )
            configured = getattr(prefs, key, "") or ""
            if configured:
                return expand_path(configured)
        elif preset == "XPMSE":
            key = (
                "xpmse_skeleton_male"
                if gender == "male"
                else "xpmse_skeleton_female"
            )
            configured = getattr(prefs, key, "") or ""
            if configured:
                return expand_path(configured)
        elif preset == "CUSTOM":
            configured = getattr(prefs, "default_skeleton_hkx", "") or ""
            if configured:
                return expand_path(configured)

    root = data_root
    if not root and prefs is not None:
        root = getattr(prefs, "data_root", "") or ""
    rel_map = XPMSE_SKELETON_REL if preset == "XPMSE" else VANILLA_SKELETON_REL
    cand = join_data_rel(root, rel_map[gender])
    if cand and Path(cand).is_file():
        return cand
    # Fall back to classic male vanilla path helper
    if root:
        found = suggest_skeleton_under_data(root)
        if found:
            return found
    return cand  # may be non-existent path for UI fill
