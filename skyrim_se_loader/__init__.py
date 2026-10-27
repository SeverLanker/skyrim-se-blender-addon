# SPDX-License-Identifier: MIT
"""Skyrim SE Asset Loader — Blender addon hub for NIF / DDS / HKX workflows."""

bl_info = {
    "name": "Skyrim SE Asset Loader",
    "author": "Sever Lanker / Grok Bot",
    "version": (0, 7, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Skyrim SE",
    "description": (
        "便捷加载《上古卷轴5》SE 人物模型、手脚头发、头雕/CharGen、皮肤与动作；"
        "桥接 PyNifly；BSArch；XPMSE；BodySlide；RaceMenu/ECE 头雕包；按 NPC 读 esp+FaceGen；动作中转与 Retarget。"
    ),
    "warning": "NIF/HKX 依赖 PyNifly（Windows；动画建议 Blender 4.4+）",
    "doc_url": "",
    "category": "Import-Export",
}

from . import prefs, properties
from .operators import (
    anim_transfer_ops,
    archive_ops,
    bodyslide_ops,
    import_ops,
    npc_ops,
    preview_ops,
    retarget_ops,
    skeleton_ops,
)
from .ui import panels
from .adapters import registry as adapter_registry

_MODULES = (
    prefs,
    properties,
    import_ops,
    npc_ops,
    archive_ops,
    skeleton_ops,
    bodyslide_ops,
    anim_transfer_ops,
    preview_ops,
    retarget_ops,
    panels,
)


_registered_modules = []


def register():
    adapter_registry.bootstrap()
    try:
        for mod in _MODULES:
            mod.register()
            _registered_modules.append(mod)
    except Exception:
        unregister()
        raise


def unregister():
    while _registered_modules:
        mod = _registered_modules.pop()
        mod.unregister()
    adapter_registry.clear()


if __name__ == "__main__":
    register()
