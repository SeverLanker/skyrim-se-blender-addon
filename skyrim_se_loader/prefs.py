# SPDX-License-Identifier: MIT
"""Addon preferences."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import AddonPreferences


class SkyrimSELoaderPreferences(AddonPreferences):
    bl_idname = __package__

    data_root: StringProperty(
        name="Skyrim SE Data 目录",
        description=(
            "已解压的 Data 根目录（含 meshes/、textures/）。"
            "可用侧栏「解包 BA2/BSA」经 BSArch 解出后写入此处。"
        ),
        subtype="DIR_PATH",
        default="",
    )

    default_skeleton_hkx: StringProperty(
        name="默认骨骼 HKX",
        description=(
            "人物骨骼 HKX 路径。官方通常为 "
            "meshes/actors/character/character assets/skeleton.hkx"
        ),
        subtype="FILE_PATH",
        default="",
    )

    bsarch_exe: StringProperty(
        name="BSArch 可执行文件",
        description=(
            "BSArch.exe 完整路径（xEdit 团队的命令行 BSA/BA2 工具）。"
            "下载：https://www.nexusmods.com/newvegas/mods/64745"
        ),
        subtype="FILE_PATH",
        default="",
    )

    bsarch_multithread: BoolProperty(
        name="BSArch 多线程解包",
        description="传给 BSArch 的 -mt:yes|no（官方默认 yes）",
        default=True,
    )

    set_data_root_after_unpack: BoolProperty(
        name="解包后写入 Data 目录偏好",
        description="解包成功后，把输出目录写入上方「Skyrim SE Data 目录」",
        default=True,
    )

    anim_transfer_format: EnumProperty(
        name="动作中转格式",
        description=(
            "默认动作工作流：HKX 经 PyNifly 导入后导出为 FBX/GLTF，"
            "再导入到目标骨骼。无通用免费 HKX→FBX 外部 CLI。"
        ),
        items=(
            ("FBX", "FBX", "Blender 内置 FBX 导入/导出（兼容面广）"),
            ("GLTF", "glTF / GLB", "Blender 内置 glTF 2.0 导入/导出"),
        ),
        default="FBX",
    )

    anim_transfer_output_dir: StringProperty(
        name="中转文件输出目录",
        description="半自动管线导出 FBX/GLTF 的默认目录（可被场景属性覆盖）",
        subtype="DIR_PATH",
        default="",
    )

    external_hkx_converter: StringProperty(
        name="外部 HKX 转换器（可选）",
        description=(
            "可选：自定义 CLI，把 .hkx 转成 .fbx/.gltf。"
            "占位符：{input} {output} {format}。"
            "留空则使用半自动：PyNifly 导入 → Blender 导出中转。"
            "社区暂无稳定的通用免费 SE HKX→FBX CLI。"
        ),
        subtype="FILE_PATH",
        default="",
    )

    external_hkx_converter_args: StringProperty(
        name="外部转换器参数模板",
        description="例如: \"{input}\" \"{output}\" ；需含 {input} 与 {output}",
        default='"{input}" "{output}"',
    )


    # --- Skeleton presets (Vanilla / XPMSE) ---
    vanilla_skeleton_male: StringProperty(
        name="Vanilla 男 skeleton.hkx",
        description=(
            "原版男性骨骼。常见相对路径："
            "meshes/actors/character/character assets/skeleton.hkx"
        ),
        subtype="FILE_PATH",
        default="",
    )

    vanilla_skeleton_female: StringProperty(
        name="Vanilla 女 skeleton_female.hkx",
        description=(
            "原版女性骨骼。常见相对路径："
            "meshes/actors/character/character assets female/skeleton_female.hkx"
        ),
        subtype="FILE_PATH",
        default="",
    )

    xpmse_skeleton_male: StringProperty(
        name="XPMSE 男 skeleton.hkx",
        description=(
            "XPMSE/XP32 男性骨骼 loose file（通常覆盖原版同路径；"
            "请指向 Mod Organizer 覆盖或已安装的 XPMSE 文件，不要只用 BSA 原版）"
        ),
        subtype="FILE_PATH",
        default="",
    )

    xpmse_skeleton_female: StringProperty(
        name="XPMSE 女 skeleton_female.hkx",
        description=(
            "XPMSE/XP32 女性骨骼 loose file。"
            "主流 MOD 动画多针对 XPMSE；缺骨时 Retarget/导入会跳过。"
        ),
        subtype="FILE_PATH",
        default="",
    )

    # --- BodySlide ---
    bodyslide_exe: StringProperty(
        name="BodySlide 可执行文件",
        description=(
            "BodySlide x64.exe 或 BodySlide.exe 完整路径。"
            "Nexus：https://www.nexusmods.com/skyrimspecialedition/mods/201"
        ),
        subtype="FILE_PATH",
        default="",
    )

    bodyslide_data_dir: StringProperty(
        name="BodySlide 数据目录",
        description=(
            "含 SliderSets / SliderPresets / ShapeData 的目录"
            "（通常为 …/CalienteTools/BodySlide）"
        ),
        subtype="DIR_PATH",
        default="",
    )

    prefer_blender_orientation: BoolProperty(
        name="使用 Blender 坐标系",
        description="调用 PyNifly 时传入 blender_xf（旋转/缩放以匹配 Blender）",
        default=False,
    )

    rename_bones: BoolProperty(
        name="Blender 友好骨骼名",
        description="调用 PyNifly 时开启 rename_bones（.L / .R）；骨骼与动作导入须一致",
        default=True,
    )

    set_scene_fps_30: BoolProperty(
        name="导入动作时设为 30 FPS",
        description="Bethesda 动画标准帧率；导入动作前写入场景输出帧率",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        import os

        def _st(path):
            return "CHECKMARK" if path and os.path.exists(bpy.path.abspath(path)) else "ERROR"

        box = layout.box()
        box.label(text="路径状态（侧栏只在缺失时提示）", icon="INFO")
        g = box.grid_flow(columns=2, even_columns=True, align=True)
        g.label(text="Data 目录", icon=_st(self.data_root))
        g.label(text="BSArch", icon=_st(self.bsarch_exe))
        g.label(text="BodySlide", icon=_st(self.bodyslide_exe))
        g.label(text="BodySlide 数据", icon=_st(self.bodyslide_data_dir))
        box.label(text="NPC 面板里的 Data / MO2 覆盖仍按场景保存，留空用这里的 Data 目录")

        layout.label(text="资源路径", icon="FILE_FOLDER")
        layout.prop(self, "data_root")
        layout.prop(self, "default_skeleton_hkx")

        layout.separator()
        layout.label(text="骨架预设路径（Vanilla / XPMSE）", icon="ARMATURE_DATA")
        layout.prop(self, "vanilla_skeleton_male")
        layout.prop(self, "vanilla_skeleton_female")
        layout.prop(self, "xpmse_skeleton_male")
        layout.prop(self, "xpmse_skeleton_female")
        col = layout.column()
        col.label(text="提示：XPMSE 安装后通常覆盖原版同相对路径；")
        col.label(text="请分别指向原版解包树与 XPMSE loose files。")

        layout.separator()
        layout.label(text="BSArch 解包", icon="FILE_ARCHIVE")
        layout.prop(self, "bsarch_exe")
        layout.prop(self, "bsarch_multithread")
        layout.prop(self, "set_data_root_after_unpack")
        row = layout.row(align=True)
        row.operator(
            "wm.url_open",
            text="下载 BSArch",
            icon="URL",
        ).url = "https://www.nexusmods.com/newvegas/mods/64745"
        row.operator(
            "wm.url_open",
            text="BAE（GUI 备选）",
            icon="URL",
        ).url = "https://www.nexusmods.com/skyrimspecialedition/mods/974"

        layout.separator()
        layout.label(text="BodySlide 身形", icon="MOD_MESHDEFORM")
        layout.prop(self, "bodyslide_exe")
        layout.prop(self, "bodyslide_data_dir")
        row = layout.row(align=True)
        row.operator(
            "wm.url_open",
            text="BodySlide Nexus",
            icon="URL",
        ).url = "https://www.nexusmods.com/skyrimspecialedition/mods/201"
        row.operator(
            "wm.url_open",
            text="CLI 文档",
            icon="URL",
        ).url = "https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Command‐line-arguments"

        layout.separator()
        layout.label(text="动作中转（默认工作流）", icon="ACTION")
        layout.prop(self, "anim_transfer_format")
        layout.prop(self, "anim_transfer_output_dir")
        layout.prop(self, "external_hkx_converter")
        layout.prop(self, "external_hkx_converter_args")

        layout.separator()
        layout.label(text="PyNifly 桥接选项", icon="LINKED")
        layout.prop(self, "prefer_blender_orientation")
        layout.prop(self, "rename_bones")
        layout.prop(self, "set_scene_fps_30")

        layout.separator()
        layout.label(text="强依赖：PyNifly（仅 Windows）", icon="INFO")
        layout.operator(
            "wm.url_open",
            text="打开 PyNifly Releases",
            icon="URL",
        ).url = "https://github.com/BadDogSkyrim/PyNifly/releases"


CLASSES = (SkyrimSELoaderPreferences,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
