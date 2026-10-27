# 调研笔记（摘要）

调研时间参考：2026-10。以公开仓库与文档为准，不编造 API / CLI flags。

## 格式

- **NIF（SE）**：BSTriShape / BSDynamicTriShape 等  
- **HKX（SE）**：Havok hk_2010，**64-bit**；LE 为 32-bit  
- **TRI**：表情 / chargen morph → Shape Keys（经 PyNifly）  
- **DDS**：皮肤等  
- **BA2**：SE/AE 资源包（LE 多为 BSA）  

## 工具

| 工具 | 角色 | 备注 |
|------|------|------|
| PyNifly | NIF + 原生 HKX | Windows；动画建议 Blender 4.4+ |
| Blender FBX / glTF | 动作中转 | 本版默认路径的中间格式 |
| BSArch | BSA/BA2 CLI | unpack 参数见下 |
| BAE / BSA Browser | GUI 解包 | 不由本插件调用 |

## BSArch unpack（已核对源码帮助）

```text
BSArch.exe unpack <archive> [destination-folder] [-mt:yes|no]
```

来源：https://github.com/TES5Edit/TES5Edit/blob/master/BSArch.dpr  
发行页：https://www.nexusmods.com/newvegas/mods/64745  

## 动作：HKX → FBX/glTF

- PyNifly 可原生 HKX↔Action（ANIMATIONS.md），但产品决策要求**默认中转**  
- 社区常见「先导入 Blender 再导出 FBX」用于 Cascadeur 等外部工具  
- **未发现**文档齐全、广泛使用的免费「SE 64-bit HKX → FBX」独立 CLI  
- 本插件实现：可选外部 CLI（用户自配）+ 默认半自动（PyNifly → export FBX/glTF → import → 骨名匹配套 Action）  

## PyNifly 算子（已核对）

```text
import_scene.pynifly
import_scene.pynifly_hkx
import_scene.pyniflytri
export_scene.pynifly
export_scene.pynifly_hkx
```

## 骨架命名

- 游戏侧：`NPC Root`、`NPC L Hand` 等  
- PyNifly `rename_bones`：可改为 `NPC Hand.L`  
- 骨骼与动作导入选项必须一致  
