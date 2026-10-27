# Skyrim SE Asset Loader（Blender 插件 v0.7.1）

在 Blender 中以较便捷方式加载《上古卷轴 5》Special Edition（含 AE）人物相关资源：

- 用 **BSArch** 解包 `.ba2` / `.bsa`
- 身体 / 手 / 脚 / 头发 / 眉毛 / 眼睛 / 头雕与附加部件（`.nif`，可附带 `.tri`）
- **RaceMenu / ECE CharGen**：导出头雕包 + 面部 DDS；RaceMenu `.jslot` 只读摘要与可选 Shape Key 近似
- 皮肤贴图（`.dds` 等）
- **骨架预设**：Vanilla / **XPMSE（XP32）** / 自定义（主流 MOD 请用 XPMSE）
- **BodySlide**：CLI 构建、填入手脚路径、导入 NIF/TRI、预设→Shape Keys
- **动作默认走 FBX / glTF 中转**；**Retarget**；多游戏 `GameAdapter` 预留

> **重要：** NIF / HKX 解析**不内嵌**，强依赖 [PyNifly](https://github.com/BadDogSkyrim/PyNifly)（**仅 Windows**）。

**兼容性：** Blender **4.0+**；动作 / 中转建议 **4.4+**；**5.2 已实测**（见下方验证说明）。

**验证：**
- v0.2.1 导入/中转：Blender **5.2.0 LTS** + PyNifly **29.1.0**（[`evidence/blender52-fix-report.md`](evidence/blender52-fix-report.md)）
- **v0.4.1** BodySlide 完整构建：通用 **CBBE 3BA** → 插件调 BodySlide → 导入 → **XP32** 绑定 → 原生/FBX/GLB 动作通过；接缝与误差见 [`evidence/bodyslide-full-build-acceptance.md`](evidence/bodyslide-full-build-acceptance.md)。**TeraElin 专用身体项目未找到，故未验证。**
- v0.3+ Retarget / BodySlide XML 有脚本：`tests/test_retarget_bake.py`、`tests/test_bodyslide_xml.py`

---


---


## v0.7.1 手部姿态保留

向已有 **XP32 / 目标骨架** 导入手等 NIF 部件时，不再被 PyNifly 改写已有手指/手掌/前臂姿态（修复求值后手形异常变大）。改动在 `importers/pynifly_bridge.py`：导入前快照 `matrix_basis`，结束后恢复；详见 [`CHANGELOG.md`](CHANGELOG.md) 与 [`skyrim_se_loader/HAND_FIX_1027.md`](skyrim_se_loader/HAND_FIX_1027.md)。

**用法边界：** 只保护新导入。旧场景若姿态已被覆盖，请撤销或打开导入前存档，用未损坏骨架重新导入；不要只删除手模型再导。

## v0.7.0 新界面结构

侧栏按工作流分组，去掉了「3b」「3c」等编号；不常用的分组默认折叠。路径统一在 **编辑 > 偏好设置 > 插件 > Skyrim SE Asset Loader** 里配置，侧栏只在缺失时提示并给出「设置路径」按钮。不可用的主按钮会变灰并在下方说明原因。

```
Skyrim SE Loader        状态栏：PyNifly / BSArch / BodySlide / Data ✓✗ + 当前骨架 + [设置路径]
├─ 角色                 目标骨架
│  ├─ NPC / 种族外观     读取插件 → 搜索 → 列表（名字/EditorID/插件/种族）→ [加载此 NPC]；报告可折叠，缺失标红
│  ├─ 手动部件（折叠）   一行一个部件 ☑/☐ + 导入；[一键导入已填部件]
│  ├─ 皮肤贴图（折叠）
│  ├─ 捏脸 / CharGen（折叠）
│  └─ BodySlide 身形（折叠）
├─ 骨架（折叠）          预设 + 性别 → [应用骨架预设]
├─ 动作（折叠）
│  ├─ 导入 / 中转        [导入动作]
│  ├─ 预览
│  └─ Retarget（折叠）
└─ 工具（折叠）
   ├─ BSArch 解包
   └─ 说明（折叠）
```

## v0.6.1 本机 NPC localfix 合入（用户验证：Windows + Blender 5.2 + 真实资源）

修复项（来自 localfix-npc-20261026，详见 [`evidence/localfix-npc-20261026/`](evidence/localfix-npc-20261026/)）：
- 继承 armor race 的种族皮肤解析
- 精确 / 运行时 FormID 搜索
- 面板改用 Blender 内置图标
- 保留着色器节点图，支持模型空间法线（`_msn`）
- MO2 / 档案内贴图查找
- FaceTint 分组近似叠加
- 自动复用已有身体骨架
- 必需部件缺失报告；BSA 目录按需过滤

例：原版 Lydia：EditorID `HousecarlWhiterun`，**NPC BaseID `000A2C8E`**（`000A2C94` 是她在世界里的放置引用 REFR，不是 NPC）→ FaceGen `meshes/actors/character/FaceGenData/FaceGeom/Skyrim.esm/000A2C8E.nif`。

**需配套 PyNifly localfix**：`io_scene_nifly-29.1.0-localfix-20261026-Windows.zip`（不打进本 zip；先装它再装 Loader）。

限制：FaceTint 是柔光近似，头部整体偏暗；眼睛、头发显示与游戏有差异；STRINGS 本地化名字未接入（显示编号，用 EditorID 搜）；BSA 仍是整包解压（首次慢，有缓存）；已损坏的旧场景不会自动修复，请从干净存档重新导入。部件导入改写已有手指姿态的问题见 **v0.7.1**。

## v0.6.0 NPC / 种族外观（esp + FaceGen）

侧栏「3c. NPC/种族外观」：按 NPC 打开随从 mod、mod 种族角色、原版角色替换 mod 后的外观。

**为什么以前只看到 femalehead.nif**：那是种族基础头（HDPT），游戏里 NPC 的脸来自 CK 预生成的 **FaceGen**：
`meshes/actors/character/FaceGenData/FaceGeom/<定义该 NPC 的插件>/<8 位本地 FormID>.nif`，
肤色/妆容在 `textures/.../FaceGenData/FaceTint/<插件>/<id>.dds`。这与 RaceMenu 无关；FaceGen 与 esp 不匹配时游戏里就是黑脸。

用法：
1. 填「游戏 Data 目录」；用 MO2 时再填 profile 目录（读 plugins.txt / loadorder.txt / modlist.txt，散文件优先级 overwrite > 上层 mod > Data）。也可手动列插件
2. 「读取插件 / 建立索引」→ 搜索 EditorID / 名字 / FormID → 选中 →「加载此 NPC」
3. 报告列出每个部件来自哪个插件/文件，[缺失] 列出找不到的；无 FaceGen 时会提示并回退到 HDPT 头部件

细节：纯 Python TES4 读取器（zlib 压缩记录、MAST→全局 FormID、ESL/light 12 位 ID）；同一记录最后加载者生效，但 FaceGen 路径用**原始定义插件**；`Use Traits` 模板沿 TPLT 跟随（模板是等级列表时报告无法静态确定）；种族 WNAM（或 NPC WNAM）→ ARMA 身体/手/脚（按性别 MOD2/MOD3，种族+额外种族匹配）→ TXST；有 FaceGen 时头发/眉毛/眼睛用 FaceGen NIF 自带形状。散文件找不到时用 BSArch 把同名插件档案 + `Skyrim - *.bsa` 解到 `%LOCALAPPDATA%/skyrim_se_loader_cache/archives`（整包解，首次慢，有缓存）。FaceTint 以 Multiply 节点乘到头部 Base Color（近似）。

限制：不做 RaceMenu 运行时捏脸/叠加层；本地化插件名字显示为 `<lstring id>`；FaceTint 为近似；FaceGen 头需搭配目标骨架（推荐 PyNifly localfix）。

## v0.5.1 jslot 范围 + 配套 PyNifly 说明

合入本机 localfix-20261026 的 **Loader** 修复（用户验证：Blender 5.2.0 LTS）：

- **jslot → Shape Keys**：先扩大滑条范围再写值，负值与 >1 的 morph 不再被钳制（详见 [`evidence/localfix-20261026/`](evidence/localfix-20261026/)）
- **CharGen 头雕**：导入前请先选好身体正在用的目标骨架。头雕改写身体骨架 / 姿态的问题在 **外部 PyNifly** 修补版中处理——请额外安装 `io_scene_nifly-29.1.0-localfix-20261026-Windows.zip`（**不**包含在本仓库的 `skyrim_se_loader.zip` 内）。安装顺序：先 PyNifly 修补包，再本 Loader；启用后重启 Blender。已变形的旧场景请撤销或打开导入前存档再重新导入。
- **仍未修复**：赋皮肤 DDS 对组材质会重建材质丢连线；完整捏脸/妆容还原（手部因部件导入被改写姿态 → 已在 **v0.7.1** 修复；`_msn`/FaceTint 等见 0.6.1）

---

## v0.5.0 部件槽位 + RaceMenu / CharGen

### 模型部件（侧栏 3）

在身体/头雕之外增加独立路径与导入按钮：

- 手 / 脚（可与 BodySlide「从构建目录填入手脚路径」联动）
- 头发 / 眉毛 / 眼睛
- 附加部件列表（嘴、须等）+「导入额外部件」
- **一键导入已填部件**（按顺序导入并激活 `target_armature`）

### 捏脸 / CharGen（侧栏 3b）

1. 选择 RaceMenu 或 ECE **导出的头雕 NIF**（常见 `SKSE/Plugins/CharGen/*.nif`）与面部 DDS  
2. **导入 CharGen 头雕包**：PyNifly 导入 → 绑目标骨骼 → 面部 DDS 赋到疑似头部 Mesh  
3. **RaceMenu `.jslot`**：解析摘要（weight、hairColor、headTexture、headParts、bodyMorphs 中非 XPMSE 数量、tint 层数等）  
4. 可选：导出 bodyMorphs→Shape Key JSON，或按**同名**写入当前 Mesh（近似）

**重要限制**

- `.jslot` 是 **RaceMenu** 预设，**不是** ECE `CME_save`；ECE 请先导出头 NIF  
- **不能**在 Blender 完整还原 jslot 滑条 / sculpt / tint 合成；外观以导出 NIF+DDS 为准  
- jslot→Shape Keys：v0.5.1 起负值/超范围会先扩滑条再赋值；仍只是同名键近似  
- CharGen 头雕请搭配修补版 PyNifly（见上节），否则导入可能改写身体骨架姿态  
- 游戏内发色常靠 tint 遮罩与顶点色，Blender 预览多为近似  
- 赋皮肤 DDS、`_msn`、手大小等仍有已知缺口（见 v0.5.1）  

样本与说明：[`evidence/chargen-sample/NOTES.md`](evidence/chargen-sample/NOTES.md)（不进入安装 zip）。

## 产品决策（v0.2）

1. **接受强依赖 PyNifly（Windows）**，继续完善侧栏工作流  
2. **动作必须走 FBX 或 glTF 中转**（默认与文档强调此路径；原生 HKX→Action 仅作高级可选项）  
3. **调用 BSArch CLI 解包 BA2/BSA**

---

## v0.4.1 局部修复 + BodySlide 验收合入

相对 0.4.0，本版**只合入**本机已验证的 BodySlide / 骨架局部修复（3 个文件），不改其他工作流逻辑：

| 文件 | 修复要点 |
| --- | --- |
| `operators/skeleton_ops.py` | 导入骨架后自动选中本次导入的 Armature 为「目标骨骼」 |
| `utils/bodyslide.py` | 匹配 PyNifly TRI 的 `>` 前缀形态键；滑条不钳制到 0–100%；写入时扩展 slider 范围 |
| `operators/bodyslide_ops.py` | 无匹配 Shape Key 时取消操作 |

**验收结论（摘要）：** 补入 CBBE / 3BA 项目后，通用 3BA 流程打通：插件调用真实 BodySlide 按预设构建身体/手/脚高低体重 NIF+TRI → 导入 Blender → 绑定 XP32 → 原生及 FBX/GLB 中转行走动作通过。逐帧与接缝数据、Newbie 生成物见 [`evidence/bodyslide-full-build-acceptance.md`](evidence/bodyslide-full-build-acceptance.md) 与 [`evidence/BodySlide-Newbie-generated-NIF-TRI.zip`](evidence/BodySlide-Newbie-generated-NIF-TRI.zip)。

**范围边界：** 通用 **CBBE 3BA** 已通；包内**未找到** `[TeraElin2] CBBE 3BBB Body Amazing` 等 TeraElin 专用身体项目，**不能**声称已构建 TeraElin 专用身形。

---

## v0.4.0 骨架切换 + BodySlide

### 骨架（Vanilla / XPMSE）

现在主流人物 MOD / 动画基本基于 **XPMSE（XP32 Maximum Skeleton Special Extended）**，不是原版 BSA 里的 `skeleton.hkx`。

1. 偏好分别填写 Vanilla / XPMSE 的男、女 HKX（可空；也可只填 Data 目录让插件按相对路径猜）  
2. 侧栏 **2. 骨骼**：下拉 **Vanilla / XPMSE / 自定义** + 性别 → **应用为默认并导入**  
3. 流程仍是：先导 HKX 骨架，再导身体/头雕 NIF  

常见相对路径：

- 男：`meshes/actors/character/character assets/skeleton.hkx`
- 女：`meshes/actors/character/character assets female/skeleton_female.hkx`

XPMSE 安装后通常**覆盖**上述同路径；请把偏好里的 XPMSE 项指向 Mod Organizer 覆盖或已安装的 loose files，不要只用原版 BSA 内骨骼。

**动作兼容：** 多数 SE 动画在 XPMSE 上可播放；目标骨架缺骨时，导入与 Retarget 会跳过对应通道（不会自动补骨）。

### BodySlide

完整形态求解由 **BodySlide** 完成（`.osp` + ShapeData `.nif` / `.osd`）。本插件：

1. 配置 `BodySlide x64.exe` 与数据目录（含 `SliderSets` / `SliderPresets` / `ShapeData`）  
2. 侧栏调用官方 CLI 构建，再用现有 **PyNifly** 导入输出 NIF  
3. 可选导入 BodySlide **TRI**（`import_scene.pyniflytri`）  
4. 若网格已有同名 Shape Keys，可读 `SliderPresets/*.xml`，把滑条百分比 ÷100 写到形态键做**近似预览**

**限制：** Shape Key 预设预览 **不等于** 完整 OSD 构建；无 TRI / 无同名键时请先 BodySlide build（建议勾选 `--trimorphs`）或导入 TRI。

#### BodySlide CLI（真实参数）

来源：[官方 Wiki · Command-line arguments](https://github.com/ousnius/BodySlide-and-Outfit-Studio/wiki/Command‐line-arguments)

```text
BodySlide [--groupbuild <groups>] [--build <outfits>] [--targetdir <path>]
          [--preset <name|file>] [--trimorphs] [--preview <files>]
```

示例：

```text
BodySlide --groupbuild "CBBE,CBBE Vanilla Outfits" --targetdir "C:\Output" --preset "CBBE Curvy" --trimorphs
```

下载：[BodySlide and Outfit Studio (SE)](https://www.nexusmods.com/skyrimspecialedition/mods/201)

---

## v0.3.0 Retarget

侧栏 **8. 动作替换 / Retarget**：

1. 指定 **源 Armature**（已有 Action）与 **目标 Armature**
2. 可选填写源 Action 名（留空=源当前 Action）、新 Action 名
3. 映射模式：
   - **同名骨骼**：精确匹配 + 忽略大小写
   - **自定义映射**：列表编辑，或 JSON `{ "源骨": "目标骨" }` 导入/导出；可「按名称猜测」
4. 通道：仅旋转 / 旋转+位置；可选覆盖同名 Action、复制根位移
5. **执行 Retarget** → 逐帧把源姿势烘焙到目标骨 `matrix_basis`（与 FBX 中转烘焙同思路），状态栏报告匹配/跳过骨数

**不是**完整人体自动 IK 重定向；骨架层级差很大时请手改映射表。跨完全不同游戏骨架的高级 auto-retarget 仍属后续。

---

## v0.2.1 修复

相对 0.2.0，本版主要修复在 Blender 5.2 上的注册与中转问题（细节与复测数据见证据报告）：

- 修复动态枚举非法默认导致插件注册失败  
- 依赖检测改为查询算子注册信息，避免 `hasattr(bpy.ops…)` 假阳性  
- 适配 Blender 5.2 的 Action slot / layer / channelbag  
- NIF 导入前激活目标骨骼，使头雕与身体共用同一骨架  
- FBX / GLB 中转：将姿势烘焙到目标局部空间、正确时间范围、保留真实末端骨骼、只导出当前动作；与原生 HKX 相比网格偏差极小  

---

## 调研结论（动作中转）

| 问题 | 结论 |
|------|------|
| 有没有通用免费的「SE HKX → FBX/glTF」独立 CLI？ | **目前没有**被广泛使用、文档齐全的稳定免费工具 |
| 现实可用路径 | **半自动**：PyNifly 导入 HKX → Blender `export_scene.fbx` / `export_scene.gltf` → 再导入并套到目标 Armature |
| 可选 | 偏好里可填「外部 HKX 转换器」+ 参数模板 `{input}` `{output}` `{format}`；留空则走半自动 |
| 原生 HKX→Action | PyNifly 支持，本插件放在「高级」折叠区，**不是默认** |

PyNifly 官方骨骼/动画说明见：  
https://github.com/BadDogSkyrim/PyNifly/blob/main/ANIMATIONS.md

---

## BSArch 解包（真实参数）

来源：[TES5Edit `BSArch.dpr` 帮助文本](https://github.com/TES5Edit/TES5Edit/blob/master/BSArch.dpr)

```text
BSArch.exe unpack <档案> [输出目录] [-mt:yes|no]
```

- 省略输出目录时，解到档案所在目录旁  
- `-mt:yes|no`：多线程，官方默认 yes  
- **不要**把 pack 专用参数（`-sse`、`-z`、`-f:` 等）用在 unpack 上  

下载：

| 工具 | 用途 | URL |
|------|------|-----|
| **BSArch** | CLI 解包/打包（本插件调用） | https://www.nexusmods.com/newvegas/mods/64745 |
| **BAE** | GUI 解包备选 | https://www.nexusmods.com/skyrimspecialedition/mods/974 |
| **BSA Browser** | GUI 浏览/解包 | https://www.nexusmods.com/skyrimspecialedition/mods/1756 |
| 源码（xEdit） | BSArch 与 xEdit 同源 | https://github.com/TES5Edit/TES5Edit |

---

## 安装

### 1. PyNifly（必需，Windows）

1. [PyNifly Releases](https://github.com/BadDogSkyrim/PyNifly/releases) 下载 `io_scene_nifly-*.zip`  
2. Blender → Edit → Preferences → Add-ons → Install… → 启用 **Import-Export: NIF format (PyNifly)**  
3. 确认 File → Import 出现 Nif / HKX / Tri  
4. 网格：Blender **4.0+**；**HKX 动画官方建议 4.4+**；本插件 **5.2 已实测**  
5. 勿用 Microsoft Store 版 Blender  

### 2. BSArch（解包推荐）

1. 从 https://www.nexusmods.com/newvegas/mods/64745 下载  
2. 插件偏好 → **BSArch 可执行文件** → 指向 `BSArch.exe`  

### 3. 本插件

安装包：仓库根目录的 **`skyrim_se_loader.zip`**（或自行打包）：

```bash
cd skyrim-se-blender-addon
zip -r skyrim_se_loader.zip skyrim_se_loader
```

Blender Add-ons → Install `skyrim_se_loader.zip` → 启用 **Skyrim SE Asset Loader**。

### 4. 偏好设置建议

- Skyrim SE Data 目录（解压后的工作根）  
- Vanilla / XPMSE 男、女 `skeleton.hkx`（及可选「默认骨骼」）  
- BSArch.exe  
- BodySlide.exe + BodySlide 数据目录（`…/CalienteTools/BodySlide`）  
- 动作中转格式：**FBX** 或 **glTF**  
- 中转文件输出目录  

---

## 使用步骤（侧栏 N → Skyrim SE）

1. **解包 BA2/BSA** — 选档案与输出目录 →「用 BSArch 解包」（可选写入 Data 偏好）  
2. **骨骼** — 选 **XPMSE**（推荐）或 Vanilla + 性别 →「应用为默认并导入」；设「目标 Armature」  
3. **模型 / 头雕** — 导入身体与头雕 NIF（可自动 TRI）  
4. **皮肤** — 选中 Mesh，赋 DDS  
5. **动作（FBX/glTF 中转）** — HKX → 中转 → 套到目标；高级可原生 HKX  
6. **预览** —「准备动作预览」→ 30 FPS → 空格播放  
7. **BodySlide（可选）** — 选预设 / Group →「用 BodySlide 构建」→ 导入结果 NIF；或导入 TRI 后「应用预设到 Shape Keys」  
8. **Retarget（可选）** — 源/目标 Armature → 同名或自定义映射 →「执行 Retarget」  

依赖检测：PyNifly、BSArch、BodySlide、FBX/glTF。

---

## 架构（v0.4）

```text
skyrim_se_loader/
  prefs.py                 # Data / Vanilla·XPMSE / BSArch / BodySlide / 中转
  properties.py            # 侧栏场景属性
  utils/deps.py            # PyNifly / BSArch / BodySlide 检测
  utils/bsarch.py          # BSArch unpack
  utils/bodyslide.py       # SliderPresets XML + BodySlide CLI
  utils/paths.py           # 骨架预设相对路径
  operators/skeleton_ops.py
  operators/bodyslide_ops.py
  importers/anim_transfer.py
  retarget/api.py
  …
```

---

## 已知限制 / 仍缺

- 非 Windows：PyNifly 不可用 → NIF/HKX 与半自动中转不可用（仍可导入已有 FBX/glTF，若 Blender 内置插件启用）  
- 不内嵌 nifly / Havok / BSArch 二进制  
- 无通用免费外部 HKX→FBX CLI；外部转换器需自备  
- DDS：部分格式需外部转 PNG  
- Retarget 为同名 + 映射表烘焙；**无**自动人体 IK / 跨游戏姿态对齐  
- BodySlide Shape Key 预览 ≠ 完整 OSD；无同名 TRI 形态键时需先 build / 导 TRI  
- 不内嵌 BodySlide / 不解析 `.osd` 求解器  
- 不替代 Creation Kit / Nemesis / FNIS / BodySlide GUI  
- 5.2 实测范围主要为原版人体样本；第三方骨架 / MOD 未全面覆盖（见证据报告）  

---

## 许可

MIT（本仓库插件代码）。PyNifly、BSArch、游戏资源遵循各自许可与 EULA；请勿分发 Bethesda 资产。
