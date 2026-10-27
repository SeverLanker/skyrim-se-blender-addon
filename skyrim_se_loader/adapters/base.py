# SPDX-License-Identifier: MIT
"""GameAdapter interface for multi-game extensibility."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class ImportRequest:
    kind: str  # body | head | skin | skeleton | animation | tri
    filepath: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    ok: bool
    message: str
    objects: Sequence[Any] = field(default_factory=list)
    backend: str = ""


class GameAdapter(ABC):
    """Contract every game backend must implement."""

    id: str = "base"
    label: str = "Base"
    description: str = ""

    mesh_extensions: tuple[str, ...] = (".nif",)
    anim_extensions: tuple[str, ...] = (".hkx",)
    texture_extensions: tuple[str, ...] = (".dds",)
    morph_extensions: tuple[str, ...] = (".tri",)

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        """Return feature flags: mesh, animation, texture, morph, retarget."""

    @abstractmethod
    def import_asset(self, context, request: ImportRequest) -> ImportResult:
        ...

    def recommended_workflow(self) -> list[str]:
        return [
            "1. 从 BSA/BA2 解出 meshes / textures",
            "2. 导入骨骼",
            "3. 导入身体与头雕网格",
            "4. 赋皮肤贴图",
            "5. 导入动作并预览",
        ]

    def retarget_notes(self) -> str:
        return "支持同名或映射表烘焙；细节由具体 GameAdapter 说明。"
