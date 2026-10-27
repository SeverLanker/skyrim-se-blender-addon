# SPDX-License-Identifier: MIT
"""Scene-level properties for the sidebar UI."""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup, Scene

from .adapters.registry import adapter_items


def _armature_poll(_self, obj):
    return obj is not None and obj.type == "ARMATURE"




def _on_bodyslide_preset_enum_update(self, context):
    ident = getattr(self, "bodyslide_preset_enum", "NONE")
    if not ident or ident == "NONE":
        return
    try:
        from .utils import bodyslide as _bs
        from .utils import deps as _deps

        prefs = _deps.get_addon_prefs(context)
        names = _bs.list_preset_names(prefs=prefs)
        for i, (pname, xml_path) in enumerate(names[:200]):
            cand = f"P{i}_{pname}"[:60]
            if cand == ident or f"P{i}" == ident:
                self.bodyslide_preset_name = pname
                self.bodyslide_preset_xml = xml_path
                return
    except Exception:
        return


def _bodyslide_preset_enum_items(self, context):
    """Dynamic enum: presets discovered under BodySlide SliderPresets."""
    items = [("NONE", "（手动填写 / 浏览 XML）", "不从目录选择")]
    try:
        from .utils import bodyslide as _bs
        from .utils import deps as _deps

        prefs = _deps.get_addon_prefs(context)
        names = _bs.list_preset_names(prefs=prefs)
        # Blender enums must be unique identifiers
        seen = set()
        for i, (pname, xml_path) in enumerate(names[:200]):
            ident = f"P{i}_{pname}"[:60]
            if ident in seen:
                ident = f"P{i}"
            seen.add(ident)
            items.append((ident, pname, xml_path))
    except Exception:
        pass
    return items






class SkyrimSEExtraPartItem(PropertyGroup):
    """Optional extra accessory NIF (mouth, beard, etc.)."""

    filepath: StringProperty(
        name="额外 NIF",
        description="嘴巴/胡须/其它附加部件 NIF 路径",
        subtype="FILE_PATH",
        default="",
    )
    label: StringProperty(
        name="备注",
        description="可选备注（如 mouth / beard）",
        default="",
    )


class SkyrimSEBoneMapItem(PropertyGroup):
    """One source_bone → target_bone row for custom retarget."""

    source_bone: StringProperty(
        name="源骨骼",
        description="源 Armature 上的骨名",
        default="",
    )
    target_bone: StringProperty(
        name="目标骨骼",
        description="目标 Armature 上的骨名",
        default="",
    )


class SkyrimSENpcItem(PropertyGroup):
    key: StringProperty(name="Key")  # plugin_lower|LOCALID
    edid: StringProperty(name="EditorID")
    full: StringProperty(name="名字")
    plugin: StringProperty(name="生效插件")
    race: StringProperty(name="种族", default="")  # v0.7


class SkyrimSELoaderSceneProps(PropertyGroup):
    game_id: EnumProperty(
        name="游戏适配器",
        description="当前使用的 GameAdapter（首版仅 Skyrim SE，后续可扩展）",
        items=adapter_items,
    )

    last_status: StringProperty(
        name="状态",
        description="最近一次操作的结果说明",
        default="就绪",
    )

    # --- Step 1: unpack ---
    archive_path: StringProperty(
        name="BA2 / BSA 档案",
        description="要解包的 .ba2 或 .bsa（SE 常用 .ba2）",
        subtype="FILE_PATH",
        default="",
    )

    unpack_output_dir: StringProperty(
        name="解包输出目录",
        description="BSArch unpack 的目标文件夹；建议指向你的工作 Data 根",
        subtype="DIR_PATH",
        default="",
    )

    # --- Mesh / head / skin ---
    body_nif: StringProperty(
        name="身体/服装 NIF",
        subtype="FILE_PATH",
        default="",
    )

    head_nif: StringProperty(
        name="头雕 NIF",
        subtype="FILE_PATH",
        default="",
    )

    # --- Body parts (v0.5) ---
    hands_nif: StringProperty(
        name="手 NIF",
        description="例如 femalehands_1.nif / malehands_1.nif（BodySlide 构建输出）",
        subtype="FILE_PATH",
        default="",
    )

    feet_nif: StringProperty(
        name="脚 NIF",
        description="例如 femalefeet_1.nif / malefeet_1.nif",
        subtype="FILE_PATH",
        default="",
    )

    hair_nif: StringProperty(
        name="头发 NIF",
        description="头发网格（独立发型 MOD 或从头雕拆出）",
        subtype="FILE_PATH",
        default="",
    )

    brows_nif: StringProperty(
        name="眉毛 NIF",
        description="眉毛网格（如 femalebrows）",
        subtype="FILE_PATH",
        default="",
    )

    eyes_nif: StringProperty(
        name="眼睛 NIF",
        description="可选：独立眼睛网格",
        subtype="FILE_PATH",
        default="",
    )

    extra_parts: CollectionProperty(type=SkyrimSEExtraPartItem)

    extra_parts_index: IntProperty(name="额外部件行", default=0)

    # --- RaceMenu / ECE CharGen (v0.5) ---
    chargen_nif: StringProperty(
        name="CharGen 头雕 NIF",
        description=(
            "RaceMenu / ECE 导出的头雕，通常在 SKSE/Plugins/CharGen/*.nif；"
            "常含头+发+眉+眼+嘴"
        ),
        subtype="FILE_PATH",
        default="",
    )

    chargen_face_dds: StringProperty(
        name="面部 DDS",
        description="CharGen 导出的面部 tint/细节图；可留空则尝试与 NIF 同名 .dds",
        subtype="FILE_PATH",
        default="",
    )

    chargen_jslot: StringProperty(
        name="RaceMenu 预设 .jslot",
        description="仅解析只读信息；不能在 Blender 完整还原滑条——请以导出 NIF+DDS 为准",
        subtype="FILE_PATH",
        default="",
    )

    chargen_jslot_report: StringProperty(
        name="jslot 摘要",
        description="最近一次解析 RaceMenu .jslot 的只读摘要",
        default="",
    )

    chargen_shapekey_json: StringProperty(
        name="Shape Key 映射 JSON",
        description="从 jslot 导出的名称→值映射（可再套到同名 Shape Keys；近似）",
        subtype="FILE_PATH",
        default="",
    )

    chargen_apply_face_custom: BoolProperty(
        name="含 morphs.custom 面部滑条",
        description="导出/应用 Shape Key 时一并包含 RaceMenu morphs.custom（常无同名键）",
        default=False,
    )


    skin_dds: StringProperty(
        name="皮肤 DDS",
        subtype="FILE_PATH",
        default="",
    )

    skeleton_hkx: StringProperty(
        name="骨骼 HKX",
        subtype="FILE_PATH",
        default="",
    )


    # --- Skeleton preset (v0.4) ---
    skeleton_preset: EnumProperty(
        name="骨架预设",
        description=(
            "Vanilla=原版；XPMSE=XP32 Maximum Skeleton SE（主流 MOD 骨架）；"
            "自定义=使用下方/偏好路径"
        ),
        items=(
            ("VANILLA", "Vanilla 原版", "原版 BSA/解包树中的 skeleton(.hkx)"),
            ("XPMSE", "XPMSE (XP32)", "主流 MOD 骨骼；请指向 XPMSE loose files"),
            ("CUSTOM", "自定义", "手动路径 / 偏好「默认骨骼」"),
        ),
        default="XPMSE",
    )

    skeleton_gender: EnumProperty(
        name="性别",
        description="选择 male skeleton.hkx 或 female skeleton_female.hkx",
        items=(
            ("female", "女 skeleton_female", "character assets female/skeleton_female.hkx"),
            ("male", "男 skeleton", "character assets/skeleton.hkx"),
        ),
        default="female",
    )


    texture_slot: EnumProperty(
        name="贴图槽位",
        description="将 DDS 赋到选中物体材质的哪个槽",
        items=(
            ("BASE_COLOR", "Base Color / Diffuse", "Principled BSDF Base Color"),
            ("NORMAL", "Normal", "法线贴图（非 Color）"),
            ("ROUGHNESS", "Roughness / Specular 近似", "Roughness 输入"),
        ),
        default="BASE_COLOR",
    )

    import_collisions: BoolProperty(
        name="导入碰撞",
        default=False,
    )

    import_tris: BoolProperty(
        name="自动导入同名 TRI",
        description="头雕表情/chargen morph（若 PyNifly 找到同名 .tri）",
        default=True,
    )

    # --- Animation transfer (default) ---
    anim_source: StringProperty(
        name="动作源文件",
        description=(
            "默认：.hkx（经中转）；也可直接选已转换的 .fbx / .glb / .gltf"
        ),
        subtype="FILE_PATH",
        default="",
    )

    anim_transfer_format: EnumProperty(
        name="中转格式",
        description="覆盖偏好中的默认中转格式；SCENE=使用偏好",
        items=(
            ("SCENE", "使用偏好设置", "跟随插件偏好里的中转格式"),
            ("FBX", "FBX", "导出/导入 FBX"),
            ("GLTF", "glTF / GLB", "导出/导入 glTF（默认写 .glb）"),
        ),
        default="SCENE",
    )

    anim_transfer_output_dir: StringProperty(
        name="中转输出目录",
        description="留空则用偏好；再空则用源文件同目录",
        subtype="DIR_PATH",
        default="",
    )

    target_armature: PointerProperty(
        name="目标 Armature",
        description="中转导入后要把 Action 套到的骨骼（通常是已导入的 skeleton）",
        type=bpy.types.Object,
        poll=_armature_poll,
    )

    keep_transfer_temp: BoolProperty(
        name="保留中转临时骨骼",
        description="半自动管线里由 HKX 导入产生的临时 Armature；默认删除以免污染场景",
        default=False,
    )

    # --- Advanced: native HKX ---
    animation_hkx: StringProperty(
        name="动作 HKX（原生高级）",
        description="高级：不经 FBX/GLTF，直接用 PyNifly 导入为 Action",
        subtype="FILE_PATH",
        default="",
    )

    show_advanced_native_hkx: BoolProperty(
        name="显示原生 HKX 导入（高级）",
        description="默认工作流强调 FBX/GLTF 中转；勾选后显示直接导入 HKX",
        default=False,
    )

    show_workflow_help: BoolProperty(
        name="显示工作流说明",
        default=True,
    )



    # --- BodySlide (v0.4) ---
    bodyslide_preset_xml: StringProperty(
        name="预设 XML",
        description="SliderPresets 下的 .xml，或任意 BodySlide 预设文件",
        subtype="FILE_PATH",
        default="",
    )

    bodyslide_preset_name: StringProperty(
        name="预设名",
        description=(
            "BodySlide 预设显示名（--preset）；也可填 file.xml?PresetName。"
            "若已选 XML，可留空表示用文件内第一个预设"
        ),
        default="",
    )

    bodyslide_group: StringProperty(
        name="构建 Group",
        description='传给 --groupbuild，可逗号分隔多个，例如 "CBBE" 或 "CBBE,CBBE Vanilla Outfits"',
        default="CBBE",
    )

    bodyslide_outfit: StringProperty(
        name="构建项目/服装名",
        description=(
            "可选：传给 --build（单个或 ;/, 分隔）。"
            "与 Group 可同时填；至少填一项"
        ),
        default="",
    )

    bodyslide_output_dir: StringProperty(
        name="构建输出目录",
        description="--targetdir；留空则用 BodySlide 配置的游戏 Data 路径",
        subtype="DIR_PATH",
        default="",
    )

    bodyslide_trimorphs: BoolProperty(
        name="输出 TRI morphs (--trimorphs)",
        description="构建时输出 TRI，便于在 Blender 用形态键预览身形",
        default=True,
    )

    bodyslide_built_nif: StringProperty(
        name="构建结果 NIF",
        description="构建后要导入的 NIF（可从输出目录挑选）",
        subtype="FILE_PATH",
        default="",
    )

    bodyslide_tri_path: StringProperty(
        name="BodySlide TRI",
        description="单独导入的 .tri（PyNifly import_scene.pyniflytri）",
        subtype="FILE_PATH",
        default="",
    )

    bodyslide_shapekey_size: EnumProperty(
        name="Shape Key 用体重",
        description="预设里同一滑条常有 small/big；预览时优先用哪一档（值÷100 → Shape Key）",
        items=(
            ("big", "Big（高体重）", "使用 size=big 的滑条值"),
            ("small", "Small（低体重）", "使用 size=small 的滑条值"),
        ),
        default="big",
    )

    bodyslide_report: StringProperty(
        name="BodySlide 报告",
        default="",
    )

    bodyslide_preset_enum: EnumProperty(
        name="从目录选预设",
        description="扫描 BodySlide 数据目录 SliderPresets；选后写入预设名/XML",
        items=_bodyslide_preset_enum_items,
        update=_on_bodyslide_preset_enum_update,
    )


    # --- Retarget (v0.3) ---
    retarget_source: PointerProperty(
        name="源 Armature",
        description="带动作的源骨骼",
        type=bpy.types.Object,
        poll=_armature_poll,
    )

    retarget_target: PointerProperty(
        name="目标 Armature",
        description="要把动作套上去的目标骨骼",
        type=bpy.types.Object,
        poll=_armature_poll,
    )

    retarget_action: StringProperty(
        name="源 Action",
        description="留空则用源 Armature 当前 Action；否则填 Action 名称",
        default="",
    )

    retarget_mode: EnumProperty(
        name="映射模式",
        description="同名骨骼自动匹配，或使用自定义映射表",
        items=(
            ("NAME", "同名骨骼", "源与目标骨名一致时直接匹配（含大小写不敏感）"),
            ("CUSTOM", "自定义映射", "使用下方映射表 / JSON"),
        ),
        default="NAME",
    )

    retarget_channels: EnumProperty(
        name="通道",
        description="烘焙哪些变换通道",
        items=(
            ("ROT", "仅旋转", "只写入 rotation_quaternion"),
            ("LOC_ROT", "旋转 + 位置", "写入 location 与 rotation_quaternion"),
        ),
        default="LOC_ROT",
    )

    retarget_overwrite: BoolProperty(
        name="覆盖同名 Action",
        description="若目标 Action 名已存在则先删除再写入",
        default=False,
    )

    retarget_copy_root_motion: BoolProperty(
        name="复制根位移",
        description="关闭时跳过目标根骨的 location 关键帧",
        default=True,
    )

    retarget_new_action_name: StringProperty(
        name="新 Action 名",
        description="留空则自动生成「原Action_on_目标名」",
        default="",
    )

    retarget_bone_map: CollectionProperty(type=SkyrimSEBoneMapItem)

    retarget_bone_map_index: IntProperty(name="映射行", default=0)

    retarget_map_json: StringProperty(
        name="映射 JSON",
        description="导入/导出骨名映射表的文件路径",
        subtype="FILE_PATH",
        default="",
    )

    # ---- v0.6 NPC / race appearance
    npc_mo2_profile: StringProperty(
        name="MO2 Profile 目录",
        description="例如 <MO2 实例>/profiles/Default（含 plugins.txt / loadorder.txt / modlist.txt）。"
        "留空则读 %LOCALAPPDATA%\\Skyrim Special Edition",
        subtype="DIR_PATH", default="",
    )
    npc_game_data: StringProperty(
        name="游戏 Data 目录",
        description="Skyrim Special Edition/Data；留空用偏好里的 Data 目录",
        subtype="DIR_PATH", default="",
    )
    npc_manual_plugins: StringProperty(
        name="手动插件列表",
        description="可选：逗号/分号分隔，按加载顺序；填写后忽略 plugins.txt",
        default="",
    )
    npc_extract_archives: BoolProperty(
        name="从 BSA/BA2 按需解出",
        description="散文件找不到时，用 BSArch 解包对应插件的档案到缓存目录（首次较慢）",
        default=True,
    )
    npc_search: StringProperty(name="搜索", description="EditorID / 名字 / FormID（十六进制）", default="")
    npc_results: CollectionProperty(type=SkyrimSENpcItem)
    npc_results_index: IntProperty(default=0)
    npc_index_report: StringProperty(default="")
    npc_report: StringProperty(default="")
    # v0.7 UI toggles (new names only; old properties untouched)
    npc_show_sources: BoolProperty(name="数据源覆盖", description="显示本场景的 Data / MO2 / 插件列表覆盖项（留空则用偏好设置）", default=False)
    npc_show_report: BoolProperty(name="显示加载报告", default=True)

    retarget_report: StringProperty(
        name="Retarget 报告",
        description="最近一次 Retarget 的匹配/跳过统计",
        default="",
    )



CLASSES = (SkyrimSEExtraPartItem, SkyrimSENpcItem, SkyrimSEBoneMapItem, SkyrimSELoaderSceneProps,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    Scene.skyrim_se_loader = PointerProperty(type=SkyrimSELoaderSceneProps)


def unregister():
    if hasattr(Scene, "skyrim_se_loader"):
        del Scene.skyrim_se_loader
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
