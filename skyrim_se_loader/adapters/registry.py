# SPDX-License-Identifier: MIT
"""Adapter registry."""

from __future__ import annotations

from typing import Dict, Optional

from .base import GameAdapter
from .skyrim_se import SkyrimSEAdapter

_REGISTRY: Dict[str, GameAdapter] = {}


def bootstrap() -> None:
    clear()
    register(SkyrimSEAdapter())


def register(adapter: GameAdapter) -> None:
    _REGISTRY[adapter.id] = adapter


def clear() -> None:
    _REGISTRY.clear()


def get(adapter_id: str) -> Optional[GameAdapter]:
    return _REGISTRY.get(adapter_id)


def all_adapters() -> list[GameAdapter]:
    return list(_REGISTRY.values())


def adapter_items(self, context):
    """EnumProperty items callback — signature required by Blender."""
    items = []
    for ad in _REGISTRY.values():
        items.append((ad.id, ad.label, ad.description))
    if not items:
        items.append(("skyrim_se", "Skyrim SE", "默认"))
    return items
