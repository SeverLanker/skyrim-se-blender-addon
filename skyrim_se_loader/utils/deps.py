# SPDX-License-Identifier: MIT
"""Detect optional backends (PyNifly, BSArch, etc.)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import bpy


@dataclass(frozen=True)
class BackendStatus:
    available: bool
    message: str
    detail: str = ""
    extras: dict = field(default_factory=dict)


def addon_enabled(module_name: str) -> bool:
    return module_name in bpy.context.preferences.addons


def find_pynifly_module() -> Optional[str]:
    """Return the enabled addon module name that exposes PyNifly operators."""
    candidates = (
        "io_scene_nifly",
        "pynifly",
        "PyNifly",
    )
    for name in candidates:
        if addon_enabled(name):
            return name
    if operator_exists(bpy.ops.import_scene, "pynifly"):
        return "io_scene_nifly"
    return None


def operator_exists(namespace, name: str) -> bool:
    """bpy.ops creates wrappers even for operators that are not registered."""
    try:
        getattr(namespace, name).get_rna_type()
    except (AttributeError, KeyError, RuntimeError):
        return False
    return True


def pynifly_operator_map() -> dict[str, bool]:
    """Check documented PyNifly operator IDs (from BadDogSkyrim/PyNifly)."""
    return {
        "import_scene.pynifly": operator_exists(bpy.ops.import_scene, "pynifly"),
        "import_scene.pynifly_hkx": operator_exists(bpy.ops.import_scene, "pynifly_hkx"),
        "import_scene.pyniflytri": operator_exists(bpy.ops.import_scene, "pyniflytri"),
        "export_scene.pynifly": operator_exists(bpy.ops.export_scene, "pynifly"),
        "export_scene.pynifly_hkx": operator_exists(bpy.ops.export_scene, "pynifly_hkx"),
    }


def blender_version_tuple() -> tuple[int, int, int]:
    v = bpy.app.version
    return (int(v[0]), int(v[1]), int(v[2]) if len(v) > 2 else 0)


def pynifly_status() -> BackendStatus:
    mod = find_pynifly_module()
    ops = pynifly_operator_map()
    has_nif = ops["import_scene.pynifly"]
    has_hkx = ops["import_scene.pynifly_hkx"]
    has_tri = ops["import_scene.pyniflytri"]
    ver = blender_version_tuple()
    platform_ok = sys.platform.startswith("win")

    missing = [k for k, ok in ops.items() if not ok and k.startswith("import_")]
    detail_parts = [
        f"module={mod or '—'}",
        f"Blender={ver[0]}.{ver[1]}.{ver[2]}",
        f"platform={sys.platform}",
        "ops: " + ", ".join(f"{'✓' if v else '✗'}{k.split('.')[-1]}" for k, v in ops.items()),
    ]
    if not platform_ok:
        detail_parts.append("警告：PyNifly 官方仅支持 Windows（nifly DLL）")
    if has_hkx and ver < (4, 4, 0):
        detail_parts.append("提示：官方建议 Blender 4.4+ 做 HKX 动画")

    extras = {
        "module": mod,
        "operators": ops,
        "blender": ver,
        "windows": platform_ok,
    }

    if has_nif and has_hkx:
        msg = "PyNifly 已就绪（NIF + HKX"
        if has_tri:
            msg += " + TRI"
        msg += "）"
        if not platform_ok:
            msg += " — 非 Windows，实际导入可能失败"
        elif ver < (4, 4, 0):
            msg += " — 建议升级到 4.4+ 做动画"
        return BackendStatus(True, msg, " | ".join(detail_parts), extras)

    if has_nif and not has_hkx:
        return BackendStatus(
            True,
            "PyNifly 已检测到，但缺少 HKX 算子：请升级到支持动画的版本（Blender 建议 4.4+）",
            " | ".join(detail_parts),
            extras,
        )

    if mod and not has_nif:
        return BackendStatus(
            False,
            f"已启用插件 {mod}，但未找到 import_scene.pynifly",
            "请确认安装的是 BadDogSkyrim/PyNifly 发行包："
            "https://github.com/BadDogSkyrim/PyNifly/releases",
            extras,
        )

    return BackendStatus(
        False,
        "未检测到 PyNifly — 请安装后启用「Import-Export: NIF format (PyNifly)」",
        "下载：https://github.com/BadDogSkyrim/PyNifly/releases （仅 Windows；"
        "勿用 Microsoft Store 版 Blender）",
        extras,
    )


def resolve_bsarch_path(prefs=None) -> str:
    prefs = prefs if prefs is not None else get_addon_prefs()
    if prefs and prefs.bsarch_exe:
        raw = prefs.bsarch_exe
        try:
            path = bpy.path.abspath(raw)
        except Exception:
            path = os.path.expanduser(raw)
        return path
    # Common fallbacks on PATH / cwd
    for name in ("BSArch.exe", "bsarch.exe", "BSArch", "bsarch"):
        which = _which(name)
        if which:
            return which
    return ""


def _which(name: str) -> str:
    from shutil import which

    found = which(name)
    return found or ""


def bsarch_status(prefs=None) -> BackendStatus:
    path = resolve_bsarch_path(prefs)
    if not path:
        return BackendStatus(
            False,
            "未配置 BSArch.exe",
            "在插件偏好中填写路径。下载："
            "https://www.nexusmods.com/newvegas/mods/64745"
            " ；GUI 备选 BAE："
            "https://www.nexusmods.com/skyrimspecialedition/mods/974",
            {"path": ""},
        )
    p = Path(path)
    if not p.is_file():
        return BackendStatus(
            False,
            f"BSArch 路径无效：{path}",
            "请指向 BSArch.exe。来源：https://www.nexusmods.com/newvegas/mods/64745",
            {"path": path},
        )
    return BackendStatus(
        True,
        f"BSArch 已配置：{p.name}",
        str(p),
        {"path": str(p)},
    )



def resolve_bodyslide_path(prefs=None) -> str:
    from . import bodyslide as _bs

    return _bs.resolve_bodyslide_exe(prefs)


def bodyslide_status(prefs=None) -> BackendStatus:
    from . import bodyslide as _bs

    path = _bs.resolve_bodyslide_exe(prefs)
    data = _bs.resolve_bodyslide_data_dir(prefs)
    if not path:
        return BackendStatus(
            False,
            "未配置 BodySlide.exe",
            "在插件偏好中填写 BodySlide x64.exe。"
            "下载：https://www.nexusmods.com/skyrimspecialedition/mods/201 ；"
            "CLI：https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Command‐line-arguments",
            {"path": "", "data_dir": data or ""},
        )
    p = Path(path)
    if not p.is_file():
        return BackendStatus(
            False,
            f"BodySlide 路径无效：{path}",
            "请指向 BodySlide x64.exe / BodySlide.exe。",
            {"path": path, "data_dir": data or ""},
        )
    detail = str(p)
    if data:
        detail += f" | data={data}"
    else:
        detail += " | 未配置数据目录（SliderPresets 列表可能为空）"
    return BackendStatus(
        True,
        f"BodySlide 已配置：{p.name}",
        detail,
        {"path": str(p), "data_dir": data or ""},
    )


def transfer_export_ops_status(fmt: str) -> BackendStatus:
    fmt = (fmt or "FBX").upper()
    if fmt == "FBX":
        ok = operator_exists(bpy.ops.export_scene, "fbx") and operator_exists(
            bpy.ops.import_scene, "fbx"
        )
        label = "FBX"
    else:
        ok = operator_exists(bpy.ops.export_scene, "gltf") and operator_exists(
            bpy.ops.import_scene, "gltf"
        )
        label = "glTF"
    if ok:
        return BackendStatus(True, f"Blender 内置 {label} 导入/导出可用", "")
    return BackendStatus(
        False,
        f"缺少 Blender {label} 导入/导出算子（请确认官方 Add-ons 已启用）",
        "",
    )


def get_addon_prefs(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__.rsplit(".", 1)[0])
    if addon is None:
        root = __package__.split(".")[0]
        addon = context.preferences.addons.get(root)
    return addon.preferences if addon else None


def full_dependency_report(context=None) -> str:
    prefs = get_addon_prefs(context)
    lines = []
    py = pynifly_status()
    lines.append(f"[PyNifly] {'OK' if py.available else '缺'} {py.message}")
    if py.detail:
        lines.append(f"  {py.detail}")
    bs = bsarch_status(prefs)
    lines.append(f"[BSArch] {'OK' if bs.available else '缺'} {bs.message}")
    if bs.detail:
        lines.append(f"  {bs.detail}")
    bd = bodyslide_status(prefs)
    lines.append(f"[BodySlide] {'OK' if bd.available else '缺'} {bd.message}")
    if bd.detail:
        lines.append(f"  {bd.detail}")
    fmt = "FBX"
    if prefs:
        fmt = prefs.anim_transfer_format or "FBX"
    tr = transfer_export_ops_status(fmt)
    lines.append(f"[中转 {fmt}] {'OK' if tr.available else '缺'} {tr.message}")
    return "\n".join(lines)
