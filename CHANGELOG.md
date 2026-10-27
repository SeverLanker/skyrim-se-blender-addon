# Changelog

## 0.7.0 — 2026-10-26

- **界面重构**：父面板 + 子面板，顺序为 状态 → 角色（NPC / 手动部件 / 皮肤 / CharGen / BodySlide）→ 骨架 → 动作（导入中转 / 预览 / Retarget）→ 工具（BSArch / 说明）；去掉编号；不常用分组 DEFAULT_CLOSED
- 顶部紧凑状态栏（图标显示通过/失败、当前目标骨架），新增 `skyrimse.open_prefs` 直达插件偏好
- 偏好设置顶部加路径状态；面板内不再重复路径输入框（NPC 的场景覆盖收进可展开区域）
- NPC 列表显示名字 / EditorID / 插件 / 种族（`SkyrimSENpcItem.race`，新字段）；大号「加载此 NPC」；报告可折叠，缺失项 alert 标红
- 手动部件一行一个，已填/未填图标，「一键导入」放大并显示已填数量
- 主操作按钮 scale_y 放大；条件不满足时 enabled=False 并显示原因
- 兼容：所有旧属性名与面板 bl_idname 保留；新增属性仅 `npc_show_sources`、`npc_show_report`、`race`
- 测试：`tests/test_ui_static.py`（图标白名单、所有操作符可达、父先于子注册、无编号标签、旧属性名存在）


## 0.6.1 — 2026-10-26

- 合入用户本机 localfix-npc-20261026（以其为准）：`importers/dds_textures.py`、`operators/npc_ops.py`、`ui/panels.py`、`utils/bsarch.py`、`utils/esp.py`、`utils/npc_appearance.py`，新增 `LOCAL_FIXES.md`
- 修复：继承 armor race、精确/运行时 FormID 搜索、Blender 图标、保留着色器图 + 模型空间法线、MO2/档案贴图查找、FaceTint 分组近似、自动复用身体骨架、必需部件报告、BSA 目录过滤
- 更正：Lydia 的 NPC BaseID 是 `000A2C8E`（`000A2C94` 是放置引用）；测试同步
- 需配套 PyNifly `io_scene_nifly-29.1.0-localfix-20261026-Windows.zip`
- 仍有限制：FaceTint 柔光近似、头部偏暗、眼睛/头发显示差异、STRINGS 本地化名未接入、手掌比例未调、BSA 整包解压

## 0.6.0 — 2026-10-26

- **NPC/种族外观**（侧栏「3c」）：读 esm/esp/esl（纯 Python TES4：NPC_/RACE/HDPT/ARMO/ARMA/TXST，zlib 压缩、master 解析、ESL 12 位 FormID）
- 加载顺序：MO2 profile 或 `%LOCALAPPDATA%\Skyrim Special Edition` 的 plugins.txt / loadorder.txt，或手动列表；最后覆盖生效（替换 mod）
- 外观：FaceGen 头（按原始定义插件 + 本地 FormID）+ FaceTint；种族/NPC 皮肤 → 身体/手/脚 ARMA + TXST；无 FaceGen 时回退 HDPT 并提示黑脸风险；`Use Traits` 模板跟随
- 文件查找：MO2 overwrite/mods → Data → BSArch 按需解档（缓存）
- 报告每个部件来源；列出缺失部件
- FaceTint 以 Multiply 乘到头部材质（近似）
- 测试：`tests/test_esp.py`（合成 esp：压缩、master、覆盖、ESL、模板、加载顺序、档案回退）

## 0.5.1 — 2026-10-26

- **Loader**：`apply_jslot_shapekeys` 先扩展 `slider_min` / `slider_max`，再赋 `kb.value`，避免 RaceMenu 负值/超范围被 Blender 钳到 0 或 1（如 -0.3→0、1.25→1）
- 文档：CharGen 头雕请搭配本机修补版 **PyNifly** `io_scene_nifly-29.1.0-localfix-20261026-Windows.zip`（FaceGen 导入保留目标身体骨架姿态，按 skin bind 对齐）；该补丁属外部 PyNifly，**不**打进本插件 zip
- 证据：`evidence/localfix-20261026/`（用户修补报告、patches、verification；可选对照包）
- 已知未修（摘自本机报告）：赋皮肤 DDS 遇组材质会重建丢失连线；`_msn` 模型空间法线；手部大小；完整 RaceMenu/ECE 捏脸还原


## 0.5.0 — 2026-10-25

- **部件槽位**（侧栏「3. 模型 / 头雕」）：手 / 脚 / 头发 / 眉毛 / 眼睛 NIF；可增删「附加部件」列表；「一键导入已填部件」
- **捏脸 / CharGen**（「3b」）：导入 RaceMenu/ECE 导出头雕 NIF + 面部 DDS；猜测同名 DDS
- **RaceMenu .jslot**：解析只读摘要（weight、hairColor、headTexture、headParts、bodyMorphs XPMSE/非 XPMSE、tintInfo、sculpt host）；明确 **不是 ECE CME_save**
- 可选：从 bodyMorphs（± morphs.custom）导出 JSON / 按名称套到 Shape Keys（近似，≠ 完整捏脸）
- BodySlide：「从构建目录填入手脚路径」（femalehands_1 / femalefeet_1 等）
- 样本：`evidence/chargen-sample/`（NIF/DDS/jslot；不进安装 zip）
- 测试：`tests/test_jslot.py`


## 0.4.1 — 2026-10-25

- 合入本机已验证的 BodySlide / 骨架**局部修复**（相对 0.4.0 仅改 3 个文件）：
  - `operators/skeleton_ops.py`：导入 HKX 成功后，优先把侧栏「目标骨骼」设为本次导入的 Armature
  - `utils/bodyslide.py`：Shape Key 应用时去掉 PyNifly TRI 的 `>` 前缀匹配；滑条百分比按 `/100` 写入且**不钳制**到 0–1（可超出常规范围）；同步扩展 `slider_min` / `slider_max`
  - `operators/bodyslide_ops.py`：无匹配形态键时返回 `CANCELLED`（不再因「有物体」而误报成功）
- **验收摘要**（详见 [`evidence/bodyslide-full-build-acceptance.md`](evidence/bodyslide-full-build-acceptance.md)）：
  - 通用 **CBBE 3BA** 项目：插件调 BodySlide 构建 → 导入 NIF/TRI → 绑定 **XP32** → 原生 HKX / FBX / GLB 动作通过
  - 行走 35 帧：FBX 最大顶点差约 0.00036、GLB 约 0.00021（游戏单位）；手腕/脚踝接缝无明显脱开
  - 样本：`evidence/BodySlide-Newbie-generated-NIF-TRI.zip`
  - **范围**：通用 3BA 已通；预设原先指向的 **TeraElin 专用身体项目未找到，故未验证**

## 0.4.0 — 2026-10-25


- **骨架预设**：偏好可分别配置 Vanilla / XPMSE 的 male / female `skeleton.hkx`；侧栏「2. 骨骼」下拉选 Vanilla / XPMSE / 自定义 + 性别，「应用为默认并导入」
- 文档说明：主流 MOD 动画多针对 **XPMSE（XP32）**；勿只用原版 BSA 内骨骼；缺骨时导入/Retarget 跳过
- **BodySlide 集成**：
  - 偏好：`BodySlide.exe` + 数据目录（SliderSets / SliderPresets / ShapeData）
  - 侧栏「7. BodySlide 身形」：扫描预设、CLI 构建（`--groupbuild` / `--build` / `--targetdir` / `--preset` / `--trimorphs`）、导入构建 NIF、导入 TRI、按预设 XML 写 Shape Keys（百分比÷100，近似预览 ≠ 完整 OSD）
  - `utils/bodyslide.py`：标准库解析 SliderPresets XML + 调用官方 CLI
- Retarget 区块改为「8.」；保留 BSArch / FBX·glTF 中转 / Retarget
- 测试：`tests/test_bodyslide_xml.py`

## 0.3.0 — 2026-10-25

- **真正实现 Retarget**：将源 Action 逐帧烘焙到目标 Armature 局部空间（复用 v0.2.1 FBX 中转的姿势烘焙思路，兼容 Blender 5.2 Action slot）
- 模式 A：同名骨骼映射（精确 + 忽略大小写）；过滤目标不存在的骨骼
- 模式 B：自定义映射表（侧栏列表 + JSON 导入/导出）；「按名称猜测」「清空」
- 可选：仅旋转 / 旋转+位置；是否覆盖同名 Action；是否复制根位移
- 侧栏新增「7. 动作替换 / Retarget」区块（源/目标/Action/模式/执行/结果报告）
- 回归脚本：`tests/test_retarget_bake.py`（`blender -b -P`；无 Blender 时跳过）
- 保留解包 / 导入 / FBX·glTF 中转工作流

## 0.2.1 — 2026-10-25

- 修复动态枚举非法默认导致注册失败
- 依赖检测改为查算子注册信息（避免 `hasattr` 假阳性）
- 适配 Blender 5.2 Action slot / layer / channelbag
- NIF 导入前激活目标骨骼，头身共用骨架
- FBX/GLB 中转：烘焙姿势到目标局部空间、时间范围、真实末端骨骼、只导出当前动作；与原生 HKX 网格偏差极小
- 已在 Blender 5.2.0 LTS + PyNifly 29.1.0 + 真实 Skyrim SE 资源验证（见 `evidence/blender52-fix-report.md`）
- 版本号 bump 至 0.2.1；安装包仍为 `skyrim_se_loader.zip`

## 0.2.0

- 侧栏工作流：BSArch 解包、骨骼 / NIF / DDS、动作预览
- 动作默认走 FBX/glTF 半自动中转；原生 HKX 直导收进高级选项
- 模块化 `GameAdapter`；Retarget 仅预留接口
