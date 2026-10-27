# SPDX-License-Identifier: MIT
"""Skyrim Special Edition adapter — bridges to PyNifly + Blender DDS."""

from __future__ import annotations

import bpy

from .base import GameAdapter, ImportRequest, ImportResult
from ..importers import dds_textures, pynifly_bridge
from ..utils import deps


class SkyrimSEAdapter(GameAdapter):
    id = "skyrim_se"
    label = "Skyrim SE"
    description = "《上古卷轴5》Special Edition / AE（NIF + DDS + HKX）"

    mesh_extensions = (".nif",)
    anim_extensions = (".hkx", ".fbx", ".glb", ".gltf")
    texture_extensions = (".dds", ".png", ".tga")
    morph_extensions = (".tri",)

    def capabilities(self) -> dict[str, bool]:
        st = deps.pynifly_status()
        has_nif = deps.operator_exists(bpy.ops.import_scene, "pynifly")
        has_hkx = deps.operator_exists(bpy.ops.import_scene, "pynifly_hkx")
        return {
            "mesh": has_nif,
            "animation": has_hkx,
            "animation_transfer": True,
            "texture": True,
            "morph": has_nif,
            "retarget": True,
            "bsarch": deps.bsarch_status().available,
            "bodyslide": deps.bodyslide_status().available,
            "backend_ready": st.available,
        }

    def import_asset(self, context, request: ImportRequest) -> ImportResult:
        kind = request.kind
        if kind in ("body", "head", "mesh"):
            return pynifly_bridge.import_nif(context, request.filepath, request.options)
        if kind == "skeleton":
            return pynifly_bridge.import_hkx(context, request.filepath, request.options)
        if kind == "animation":
            return pynifly_bridge.import_hkx(context, request.filepath, request.options)
        if kind == "tri":
            return pynifly_bridge.import_tri(context, request.filepath, request.options)
        if kind == "skin":
            return dds_textures.apply_dds_to_selection(
                context,
                request.filepath,
                slot=request.options.get("texture_slot", "BASE_COLOR"),
            )
        return ImportResult(False, f"未知导入类型: {kind}")

    def recommended_workflow(self) -> list[str]:
        return [
            "1. 偏好：Data、Vanilla/XPMSE 骨骼路径、BSArch、BodySlide.exe、中转格式",
            "2. 解包：BSArch unpack 解出 Meshes/Textures BA2",
            "3. 启用 PyNifly（Windows；动画建议 4.4+；5.2 已测）",
            "4. 骨架：侧栏选 XPMSE（主流）或 Vanilla →「应用为默认并导入」",
            "5. 身形（可选）：BodySlide CLI 构建 → 导入身体；可「填入手脚路径」",
            "6. 部件：身体/手/脚/头/发/眉/眼 + 一键导入；或捏脸 CharGen 头雕包",
            "7. RaceMenu/ECE：导出头 NIF+面部 DDS；.jslot 仅只读参考，不还原滑条",
            "8. 赋 DDS 皮肤；动作 HKX→FBX/glTF 中转；预览 30fps",
            "9. Retarget（可选）：同名或映射表烘焙到另一套骨骼",
        ]

    def retarget_notes(self) -> str:
        return (
            "v0.3：同名骨骼或自定义 JSON 映射，将源姿势烘焙到目标局部空间。"
            "不是完整人体 IK 自动重定向；骨层级差很大时请手改映射表"
        )
