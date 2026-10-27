# SPDX-License-Identifier: MIT
"""Fallback messaging when native backends are unavailable."""

from __future__ import annotations

MISSING_PYNIFLY = """\
本插件不内嵌 NIF/HKX 解析库，强依赖 PyNifly（仅 Windows）。

必需：
  • PyNifly（BadDogSkyrim）— https://github.com/BadDogSkyrim/PyNifly/releases
  • Blender 4.0+（网格）；HKX 动画官方建议 4.4+
  • 勿用 Microsoft Store 版 Blender

动作默认工作流（本版强调）：
  • HKX →（PyNifly 导入）→ 导出 FBX 或 glTF → 再导入/套到目标骨骼
  • 也可直接使用已有 FBX/GLB/GLTF
  • 社区暂无稳定的通用免费「SE HKX→FBX」外部 CLI
  • 「原生 HKX→Action」仅作高级可选项

解包 BA2/BSA：
  • BSArch CLI（推荐，本插件可调用）：
    https://www.nexusmods.com/newvegas/mods/64745
    命令：BSArch.exe unpack <档案> [输出目录] [-mt:yes|no]
  • BAE GUI：https://www.nexusmods.com/skyrimspecialedition/mods/974
  • BSA Browser：https://www.nexusmods.com/skyrimspecialedition/mods/1756
"""
