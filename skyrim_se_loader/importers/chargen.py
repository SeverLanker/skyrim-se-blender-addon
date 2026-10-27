# SPDX-License-Identifier: MIT
"""CharGen / RaceMenu / ECE head package helpers (NIF + facial DDS)."""

from __future__ import annotations

from pathlib import Path

import bpy

from ..adapters.base import ImportResult
from . import dds_textures, pynifly_bridge

# Mesh name fragments that usually belong to the exported face tint target.
_HEAD_NAME_HINTS = (
    "head",
    "face",
    "chargen",
    "facegen",
    "bsfacegen",
    "femalehead",
    "malehead",
)


def guess_face_dds_beside_nif(nif_path: str) -> str:
    """Prefer same-stem .dds next to the CharGen NIF."""
    if not nif_path:
        return ""
    p = Path(nif_path).expanduser()
    if not p.is_file():
        return ""
    for cand in (p.with_suffix(".dds"), p.with_suffix(".DDS")):
        if cand.is_file():
            return str(cand)
    # RaceMenu often writes Head_….nif + matching Head_….dds in CharGen folder
    stem = p.stem
    parent = p.parent
    for f in parent.glob(f"{stem}*.dds"):
        return str(f)
    for f in parent.glob(f"{stem}*.DDS"):
        return str(f)
    return ""


def _mesh_looks_like_head(obj: bpy.types.Object) -> bool:
    name = (obj.name or "").casefold()
    return any(h in name for h in _HEAD_NAME_HINTS)


def select_head_like_meshes(objects: list) -> list:
    meshes = [o for o in objects if getattr(o, "type", None) == "MESH"]
    heads = [o for o in meshes if _mesh_looks_like_head(o)]
    return heads if heads else meshes


def apply_face_dds_to_objects(
    context,
    objects: list,
    dds_path: str,
    *,
    slot: str = "BASE_COLOR",
) -> ImportResult:
    """Assign facial tint DDS onto head-like meshes among ``objects``."""
    targets = select_head_like_meshes(objects)
    if not targets:
        return ImportResult(
            False,
            "CharGen 包已导入，但场景中没有可赋贴图的 Mesh。",
            backend="chargen",
        )
    # Select targets so apply_dds_to_selection sees them
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in context.selected_objects:
        obj.select_set(False)
    for obj in targets:
        obj.select_set(True)
    context.view_layer.objects.active = targets[0]
    result = dds_textures.apply_dds_to_selection(context, dds_path, slot=slot)
    if result.ok:
        note = (
            f"{result.message} "
            f"（CharGen 面部 tint 近似：游戏内发色/眉色常靠 tint 遮罩与顶点色，"
            f"Blender 预览可能只接近，不完全等于游戏内合成。）"
        )
        return ImportResult(True, note, objects=result.objects, backend="chargen")
    return result


def import_chargen_package(
    context,
    nif_path: str,
    dds_path: str = "",
    *,
    import_tris: bool = True,
    texture_slot: str = "BASE_COLOR",
) -> ImportResult:
    """Import CharGen/RaceMenu/ECE head NIF, optionally apply face DDS."""
    nif_result = pynifly_bridge.import_nif(
        context,
        nif_path,
        {"import_collisions": False, "import_tris": import_tris},
    )
    if not nif_result.ok:
        return nif_result

    face = (dds_path or "").strip() or guess_face_dds_beside_nif(nif_path)
    if not face:
        return ImportResult(
            True,
            nif_result.message
            + "；未指定/未找到配套面部 DDS（可填 CharGen 同名 .dds）。"
            " ECE CME_save 槽位不能在 Blender 直接读，需先导出头 NIF。",
            objects=nif_result.objects,
            backend="chargen",
        )

    tex = apply_face_dds_to_objects(
        context,
        nif_result.objects or [],
        face,
        slot=texture_slot,
    )
    if not tex.ok:
        return ImportResult(
            True,
            nif_result.message + f"；面部 DDS 未赋上：{tex.message}",
            objects=nif_result.objects,
            backend="chargen",
        )
    return ImportResult(
        True,
        nif_result.message + "；" + tex.message,
        objects=list(nif_result.objects or []) + list(tex.objects or []),
        backend="chargen",
    )
