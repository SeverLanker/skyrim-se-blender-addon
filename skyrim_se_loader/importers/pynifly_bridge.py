# SPDX-License-Identifier: MIT
"""Thin wrapper around PyNifly operators. Does not re-implement NIF/HKX parsing."""

from __future__ import annotations

from typing import Any

import bpy

from ..adapters.base import ImportResult
from ..utils import deps
from ..utils.paths import ensure_file


# Documented operator IDs from BadDogSkyrim/PyNifly (io_scene_nifly):
#   import_scene.pynifly      — NIF
#   import_scene.pynifly_hkx  — HKX skeleton or animation
#   import_scene.pyniflytri   — TRI morphs
#   export_scene.pynifly / export_scene.pynifly_hkx


def _prefs_bridge_options(context) -> dict[str, Any]:
    prefs = deps.get_addon_prefs(context)
    opts: dict[str, Any] = {}
    if prefs:
        opts["blender_xf"] = bool(prefs.prefer_blender_orientation)
        opts["rename_bones"] = bool(prefs.rename_bones)
    else:
        opts["blender_xf"] = False
        opts["rename_bones"] = True
    return opts


def import_nif(context, filepath: str, options: dict | None = None) -> ImportResult:
    status = deps.pynifly_status()
    if not deps.operator_exists(bpy.ops.import_scene, "pynifly"):
        return ImportResult(
            False,
            "无法导入 NIF：未安装/未启用 PyNifly。"
            "请从 https://github.com/BadDogSkyrim/PyNifly/releases 安装（Windows）。",
            backend="missing",
        )

    try:
        path = ensure_file(filepath, (".nif",))
    except (FileNotFoundError, ValueError) as exc:
        return ImportResult(False, str(exc), backend="pynifly")

    opts = _prefs_bridge_options(context)
    if options:
        opts.update(options)

    kwargs = {
        "filepath": str(path),
        "blender_xf": opts.get("blender_xf", False),
        "rename_bones": opts.get("rename_bones", True),
        "import_collisions": bool(opts.get("import_collisions", False)),
        "import_tris": bool(opts.get("import_tris", True)),
    }

    before = set(bpy.data.objects)
    props = getattr(context.scene, "skyrim_se_loader", None)
    target = props.target_armature if props else None
    # NIF parts carry their own bone poses. Loading a part must not pose an
    # existing character (notably XP32 fingers); HKX handles animation import.
    target_pose = ({bone.name: bone.matrix_basis.copy()
                    for bone in target.pose.bones} if target is not None else {})
    if target is not None:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in context.selected_objects:
            obj.select_set(False)
        target.select_set(True)
        context.view_layer.objects.active = target
    try:
        # Keyword names match ImportNIF properties in PyNifly import_nif.py
        result = bpy.ops.import_scene.pynifly(**kwargs)
    except TypeError:
        # Older PyNifly may use different property names — fall back to filepath only.
        try:
            result = bpy.ops.import_scene.pynifly(filepath=str(path))
        except Exception as exc:  # noqa: BLE001
            return ImportResult(False, f"PyNifly NIF 导入失败: {exc}", backend="pynifly")
    except Exception as exc:  # noqa: BLE001
        return ImportResult(False, f"PyNifly NIF 导入失败: {exc}", backend="pynifly")
    finally:
        for name, basis in target_pose.items():
            bone = target.pose.bones.get(name)
            if bone is not None:
                bone.matrix_basis = basis
        if target_pose:
            context.view_layer.update()

    if "FINISHED" not in result and "CANCELLED" not in result:
        # Some Blender versions return set; treat unknown as soft success if objects appeared
        pass
    if "CANCELLED" in result:
        return ImportResult(False, "PyNifly 取消了 NIF 导入", backend="pynifly")

    created = [obj for obj in bpy.data.objects if obj not in before]
    return ImportResult(
        True,
        f"已通过 PyNifly 导入 NIF：{path.name}（新物体 {len(created)}）",
        objects=created,
        backend="pynifly",
    )


def import_hkx(context, filepath: str, options: dict | None = None) -> ImportResult:
    if not deps.operator_exists(bpy.ops.import_scene, "pynifly_hkx"):
        return ImportResult(
            False,
            "无法导入 HKX：当前 PyNifly 未注册 import_scene.pynifly_hkx。"
            "请升级 PyNifly，并使用 Blender 4.4+。"
            "默认动作工作流也可：若你已有 FBX/glTF 中转文件，请在侧栏步骤 5 直接导入。"
            "下载：https://github.com/BadDogSkyrim/PyNifly/releases",
            backend="missing",
        )

    try:
        path = ensure_file(filepath, (".hkx",))
    except (FileNotFoundError, ValueError) as exc:
        return ImportResult(False, str(exc), backend="pynifly")

    prefs = deps.get_addon_prefs(context)
    if prefs and prefs.set_scene_fps_30:
        context.scene.render.fps = 30

    opts = _prefs_bridge_options(context)
    if options:
        opts.update(options)

    kwargs = {
        "filepath": str(path),
        "blender_xf": opts.get("blender_xf", False),
        "rename_bones": opts.get("rename_bones", True),
    }
    ref = opts.get("reference_skel") or ""
    if ref:
        kwargs["reference_skel"] = ref

    before_actions = set(bpy.data.actions)
    before_objects = set(bpy.data.objects)
    try:
        result = bpy.ops.import_scene.pynifly_hkx(**kwargs)
    except TypeError:
        try:
            result = bpy.ops.import_scene.pynifly_hkx(filepath=str(path))
        except Exception as exc:  # noqa: BLE001
            return ImportResult(False, f"PyNifly HKX 导入失败: {exc}", backend="pynifly")
    except Exception as exc:  # noqa: BLE001
        return ImportResult(False, f"PyNifly HKX 导入失败: {exc}", backend="pynifly")

    if "CANCELLED" in result:
        return ImportResult(False, "PyNifly 取消了 HKX 导入", backend="pynifly")

    new_actions = [a for a in bpy.data.actions if a not in before_actions]
    new_objects = [o for o in bpy.data.objects if o not in before_objects]
    extra = ""
    if new_actions:
        extra = f"；新 Action: {', '.join(a.name for a in new_actions)}"
    return ImportResult(
        True,
        f"已通过 PyNifly 导入 HKX：{path.name}（新物体 {len(new_objects)}{extra}）",
        objects=new_objects,
        backend="pynifly",
    )


def import_tri(context, filepath: str, options: dict | None = None) -> ImportResult:
    if not deps.operator_exists(bpy.ops.import_scene, "pyniflytri"):
        return ImportResult(
            False,
            "无法导入 TRI：未找到 import_scene.pyniflytri。请安装/启用完整版 PyNifly。",
            backend="missing",
        )
    try:
        path = ensure_file(filepath, (".tri",))
    except (FileNotFoundError, ValueError) as exc:
        return ImportResult(False, str(exc), backend="pynifly")

    try:
        result = bpy.ops.import_scene.pyniflytri(filepath=str(path))
    except Exception as exc:  # noqa: BLE001
        return ImportResult(False, f"PyNifly TRI 导入失败: {exc}", backend="pynifly")

    if "CANCELLED" in result:
        return ImportResult(False, "PyNifly 取消了 TRI 导入", backend="pynifly")
    return ImportResult(True, f"已通过 PyNifly 导入 TRI：{path.name}", backend="pynifly")
