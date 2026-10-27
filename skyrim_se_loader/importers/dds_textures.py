# SPDX-License-Identifier: MIT
"""Apply DDS (or other image) textures to selected mesh materials."""

from __future__ import annotations

from pathlib import Path

import bpy

from ..adapters.base import ImportResult
from ..utils.paths import ensure_file


def _ensure_principled(mat: bpy.types.Material):
    mat.use_nodes = True
    nt = mat.node_tree
    for node in nt.nodes:
        if node.type == "GROUP" and node.node_tree and node.node_tree.name.startswith("SkyrimShader:"):
            return nt, node
    for node in nt.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return nt, node
    if any(n.type == "OUTPUT_MATERIAL" and n.inputs["Surface"].is_linked for n in nt.nodes):
        raise ValueError(f"{mat.name} 使用不支持的自定义着色器，已保留原材质")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return nt, bsdf


def _load_image(filepath: str, non_color=False) -> bpy.types.Image:
    path = str(Path(filepath))
    # Reuse if already loaded
    space = "Non-Color" if non_color else "sRGB"
    for img in bpy.data.images:
        if bpy.path.abspath(img.filepath) == bpy.path.abspath(path) and img.colorspace_settings.name == space:
            return img
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = space
    return img


def apply_to_material(mat, filepath, slot="BASE_COLOR"):
    """Update a supported shader input without replacing the shader graph."""
    nt, shader = _ensure_principled(mat)
    grouped = shader.type == "GROUP"
    names = {"BASE_COLOR": ("Diffuse", "Base Color"), "NORMAL": ("Normal", "Normal"),
             "ROUGHNESS": ("Glossiness", "Roughness"), "SUBSURFACE": ("Subsurface", "Subsurface Weight"),
             "SPECULAR": ("Specular", "Specular IOR Level")}
    if slot not in names:
        raise ValueError(f"不支持的贴图槽位：{slot}")
    inp = shader.inputs.get(names[slot][0 if grouped else 1])
    if inp is None:
        raise ValueError(f"{mat.name} 没有 {slot} 输入")
    image = _load_image(str(filepath), slot in {"NORMAL", "ROUGHNESS", "SPECULAR"})
    tag = "SSE_" + slot
    tex = next((n for n in nt.nodes if n.get("sse_slot") == slot and n.type == "TEX_IMAGE"), None)
    if tex is None and inp.links and inp.links[0].from_node.type == "TEX_IMAGE":
        tex = inp.links[0].from_node
    tex = tex or nt.nodes.new("ShaderNodeTexImage")
    tex["sse_slot"] = slot
    tex.image, tex.label = image, Path(filepath).name
    uv = next((n for n in nt.nodes if n.name == "UV_Converter"), None)
    uv_socket = (uv.outputs.get("Vector") or uv.outputs.get("UV")) if uv else None
    if uv_socket is not None and not tex.inputs["Vector"].is_linked:
        nt.links.new(uv_socket, tex.inputs["Vector"])
    color = tex.outputs["Color"]
    def node(suffix, kind):
        return nt.nodes.get(tag + suffix) or nt.nodes.new(kind)
    if slot == "NORMAL":
        msn = "_msn" in Path(filepath).stem.lower()
        if grouped:
            if "MSN" in shader.inputs:
                shader.inputs["MSN"].default_value = msn
        else:
            normal = node("Normal", "ShaderNodeNormalMap"); normal.name = tag + "Normal"
            normal.space = "OBJECT" if msn else "TANGENT"
            if msn:
                sep = node("Split", "ShaderNodeSeparateColor"); sep.name = tag + "Split"
                comb = node("Join", "ShaderNodeCombineColor"); comb.name = tag + "Join"
                nt.links.new(color, sep.inputs[0])
                for src, dst in ((0, 0), (2, 1), (1, 2)):
                    nt.links.new(sep.outputs[src], comb.inputs[dst])
                color = comb.outputs[0]
            nt.links.new(color, normal.inputs["Color"])
            color = normal.outputs["Normal"]
    elif slot == "ROUGHNESS" and grouped:
        invert = node("Gloss", "ShaderNodeMapRange"); invert.name = tag + "Gloss"
        invert.inputs["To Min"].default_value = 200
        invert.inputs["To Max"].default_value = 0
        nt.links.new(color, invert.inputs["Value"])
        color = invert.outputs[0]
    nt.links.new(color, inp)
    return tex


def apply_dds_to_selection(
    context,
    filepath: str,
    slot: str = "BASE_COLOR",
) -> ImportResult:
    try:
        path = ensure_file(filepath, (".dds", ".png", ".tga", ".jpg", ".jpeg", ".tif", ".tiff"))
    except (FileNotFoundError, ValueError) as exc:
        return ImportResult(False, str(exc), backend="blender-image")

    meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
    if not meshes:
        # Fall back to active mesh
        obj = context.view_layer.objects.active
        if obj and obj.type == "MESH":
            meshes = [obj]
    if not meshes:
        return ImportResult(
            False,
            "请先选中至少一个 Mesh，再赋皮肤贴图。",
            backend="blender-image",
        )

    try:
        _load_image(str(path), slot in {"NORMAL", "ROUGHNESS", "SPECULAR"})
    except Exception as exc:  # noqa: BLE001
        return ImportResult(False, f"加载贴图失败: {exc}", backend="blender-image")

    touched = 0
    errors = []
    for obj in meshes:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        if not obj.data.materials:
            mat = bpy.data.materials.new(name=f"{obj.name}_Skin")
            obj.data.materials.append(mat)
        for slot_idx, mat in enumerate(obj.data.materials):
            if mat is None:
                mat = bpy.data.materials.new(name=f"{obj.name}_Mat{slot_idx}")
                obj.data.materials[slot_idx] = mat
            if mat.users > 1:
                mat = mat.copy()
                obj.data.materials[slot_idx] = mat
            try:
                apply_to_material(mat, path, slot)
                touched += 1
            except (ValueError, OSError, RuntimeError) as exc:
                errors.append(str(exc))

    return ImportResult(
        not errors,
        f"已将 {path.name} 赋到 {len(meshes)} 个网格（槽位 {slot}，材质更新 {touched}）。"
        + ("；" + "；".join(errors) if errors else ""),
        objects=meshes,
        backend="blender-image",
    )
