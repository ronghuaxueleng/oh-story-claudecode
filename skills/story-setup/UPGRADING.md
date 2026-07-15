# 升级指南

## 升级策略

| 策略 | 适用场景 | 风险 |
|------|----------|------|
| 覆盖部署 | 全新项目或无需保留自定义 | 低 |
| 合并部署 | 有自定义内容需保留 | 中 |
| 手动更新 | 只改特定文件 | 低 |

推荐：使用 `story-setup` 重新部署，自动走合并策略。

## 文件分类

### 可安全覆盖

这些文件由 story-setup 管理，不含用户自定义内容：
- `.codex/hooks/` — 所有 hook 脚本
- `.codex/agents/` — 所有子代理定义
- `.codex/rules/` — 所有 path-scoped 规则
- `scripts/install-codex-project.sh` — 项目级基础设施安装/刷新脚本
- `scripts/scene_lint.py` — 正文场面质检脚本
- `scripts/draft_purity_guard.py` — 正文纯净度守门脚本
- `scripts/validate_tracking_state.py` — 追踪状态与章组总表校验脚本
- `scripts/detect_key_character_promotion.py` — 关键角色晋升与缺卡检测脚本
- `scripts/template_exhaustion_lint.py` — 模板榨干与模板术语回流质检脚本
- `scripts/scene_narrowness_lint.py` — 中段会议化 / 作者代判句 / 过程写窄质检脚本
- `scripts/script_version_check.py` — 项目脚本版本与双层目录路径校验脚本
- `scripts/verdict_conflict_lint.py` — 并入口径冲突校验脚本
- `scripts/chapter_hook_repeat_lint.py` — 连续章章尾撞型校验脚本
- `scripts/character_agency_lint.py` — 人物能动性与软肋角色回针校验脚本
- `scripts/story_review_regression.py` — 统一回归汇总脚本

### 需合并（不覆盖）

这些文件可能含用户自定义内容：
- `CLAUDE.md` — 按 section 合并，用户独有 section 保留
- `.codex/config.toml` — 仅补齐本工具必需项，用户其他配置保留

### 不碰

这些文件完全由用户管理：
- `{书名}/追踪/上下文.md` — 用户写作上下文
- `{书名}/追踪/伏笔.md` — 用户伏笔追踪
- `.active-book` — 用户活跃书目

## 版本检测

`.story-deployed` 文件记录部署版本：
- 无此文件 → 未部署，需全新安装
- `agents_version: 1` → 旧版，需重新部署以获取新子代理
- `agents_version: 2` → 旧版，需重新部署以获取 story-explorer 子代理
- `agents_version: 3` → 旧版，需重新部署以获取 story-explorer 子代理
- `agents_version: 4` → 旧版，需重新部署以获取 chapter-extractor 子代理
- `agents_version: 5` → 旧版，需重新部署以统一短篇主会话/子代理正文格式
- `agents_version: 6` → 旧版，需重新部署以获取日更续写与伏笔 hook 修复
- `agents_version: 7` → 旧版，需重新部署以获取子代理参考文件路径修复
- `agents_version: 8` → 旧版，需重新部署以补齐 references bundle、sentinel 字段与根路径感知 hook
- `agents_version: 9` → 旧版，需重新部署以补齐项目级正文质检脚本
- `agents_version: 10` → 旧版，需重新部署以获取追踪同步硬闸、compact/续写追踪主表核对与 hook 提示补强
- `agents_version: 11` → 旧版，需重新部署以补齐项目级追踪校验脚本
- `agents_version: 12` → 旧版，需重新部署以补齐统一回归脚本
- `agents_version: 13` → 旧版，需重新部署以补齐新版根模板、兼容层 rules 模板与完整项目脚本链
- `agents_version: 14` → 旧版，需重新部署以补齐参考边界卡、单章写前卡与参考章节对比协议到项目内 agent-references
- `agents_version: 15` → 旧版，需重新部署以补齐短篇资料包副本到项目内 agent-references
- `agents_version: 16` → 旧版，需重新部署以补齐托管模板落盘与受管文件保护
- `agents_version: 17` → 旧版，需重新部署以补齐短篇 profile / 审计 / 回修脚本链与治理副本
- `agents_version: 18` → 当前版本

## 版本变更

### v2

- 4 个创作型子代理 + 1 个研究型子代理（story-architect, character-designer, narrative-writer, consistency-checker, story-researcher）
- 子代理引用 skill references 写作理论
- Hook 脚本优化（减少 context 输出）
- 4 条 path-scoped 规则

### v3

- 新增 story-explorer 只读查询子代理（角色/伏笔/设定/进度查询，日更上下文快速加载）
- 6 个子代理总计（story-architect, character-designer, narrative-writer, consistency-checker, story-researcher, story-explorer）
- story-explorer 被 story-long-write、story-review、story 路由集成调用

### v4

- 新增 chapter-extractor 章节提取子代理
- 7 个子代理总计（story-architect, character-designer, narrative-writer, consistency-checker, story-researcher, story-explorer, chapter-extractor）

### v5

- 更新 narrative-writer 场景写法：使用“三维度织入”并按镜头断段控制段落密度
- 字数统计改为 Python 字符统计优先，`wc -m` 仅作 macOS/Linux 备选，提升 Windows + DeepSeek/Codex 兼容性
- 已部署项目重新运行 `story-setup` 后获取新版子代理定义
- 已部署项目重新运行 `story-setup` 后获取新版子代理定义

### v6

- 统一 `narrative-writer` 子代理与主会话的短篇正文格式：固定写入 `正文.md`、小节标记统一、段落无空行、对话半角双引号
- 短篇写作不再由 `narrative-writer` 创建长篇 `追踪/上下文.md`

### v7

- 修复长篇 `story-long-write` 日更批量续写中的 continuation 规则：同一批次内“继续/续写/日更”保持在 daily workflow，不直接跳到正文续写
- 修复 `detect-story-gaps.sh` 对伏笔表头和正常开放伏笔（`未埋`/`已埋`）的误报；SessionStart 只提示 `已过期` 或异常状态
- 已部署项目需重新运行 `story-setup`，以覆盖 `.codex/hooks/`、`.codex/agents/`、`.codex/rules/` 并获得新版 hook 行为

### v8

- 修复 story-review 及部署后的 reviewer 子代理在项目根目录下读取参考文件时，只找裸文件名（如 `quality-checklist.md`）导致找不到 skill references 的问题
- 子代理模板新增参考文件路径规则：优先从 `.codex/skills/` 或 `skills/` 拼接解析 `story-setup/references/agent-references/*.md` 规范路径，避免依赖当前工作目录且不跨 skill 引用 references
- 已部署项目需重新运行 `story-setup`，以覆盖 `.codex/agents/` 并获得新版参考文件路径规则

### v9

- `install-codex-project.sh` 现在会同步部署 `.codex/skills/story-setup/references/agent-references/`
- `.story-deployed` 新增 `target_cli`、`resolver_strategy`、`references_dir` 字段，session-start 可据此检查部署完整性
- `session-start.sh` 改为统一使用项目根解析与 sentinel 检查，能从嵌套目录稳定定位书目、拆文库和 references bundle
- `detect-story-gaps.sh` 改为统一使用 `discover_all_books`，并彻底中文化提示文案

### v10

- `story-setup` 现在会同步部署项目级 `scripts/scene_lint.py` 与 `scripts/draft_purity_guard.py`，避免写作/审查首次运行时再临时补脚本
- 已部署项目需重新运行 `story-setup`，以补齐 `scripts/` 下的正文质检脚本并让版本标记升级到 `agents_version: 10`

### v11

- `CLAUDE.md` 模板新增长篇正文收尾硬闸：单章正文落盘后必须完成 `scene_lint.py -> 写后验收 -> 追踪同步 -> 反读追踪`
- `写作执行铁律` 模板新增追踪同步 `F5` 截停规则：若 `正文/` 最大章节号已前推，但 `追踪/上下文.md`、`时间线.md`、`角色状态.md`、`伏笔.md`、情报流所需的 `情报台账.md` 未同步，默认当前章未收口
- `session-start.sh`、`pre-compact.sh`、`post-compact.sh` 模板新增追踪主表提示与摘要，不再只盯 `上下文.md`
- 已部署项目需重新运行 `story-setup`，以覆盖 `CLAUDE.md` 模板合并结果、小说目录内 `写作执行铁律.md` 以及 `.codex/hooks/`，并让版本标记升级到 `agents_version: 11`

### v12

- `story-setup` 现在会同步部署项目级 `scripts/validate_tracking_state.py` 与 `scripts/detect_key_character_promotion.py`
- 已部署项目需重新运行 `story-setup`，以补齐 `scripts/` 下的追踪校验脚本并让版本标记升级到 `agents_version: 12`

### v13

- `story-setup` 现在会同步部署项目级 `scripts/story_review_regression.py`
- 统一回归脚本会串联 `scene_lint.py`、`validate_tracking_state.py`、`detect_key_character_promotion.py` 的结果，并落盘 `测试/story-review_回归脚本汇总.md` 与 `.json`
- `validate_tracking_state.py` 现已修复两处兼容性问题：
  - 章组总表校验不再要求文件名必须与“最近章节范围”精确相等；只要总表章节区间覆盖最近连续章节范围，即判为有效
  - Markdown 表格分隔线现在支持 `:` 对齐写法，不再把 `|---|---:|...|` 误判成 `追踪/情报台账.md` 的数据行
- 已部署项目需重新运行 `story-setup`，以补齐统一回归脚本并让版本标记升级到 `agents_version: 13`

### v14

- `CLAUDE.md` 与 `写作执行铁律` 模板升级到新版冷启动协议：
  - 主准入链改为 `短执行核 + 写前闸门 + 新脚本门禁`
  - 新链路彻底移除独立首稿读取产物，不再生成额外首稿读取记录文件
  - 写后固定顺序补齐到 `template_exhaustion_lint.py`、`scene_narrowness_lint.py`、`script_version_check.py`、`validate_tracking_state.py`、`verdict_conflict_lint.py`、连续章钩子与人物专项脚本
  - 新增 `H1-A` 纯测试记录态与双层目录执行口径
- `.codex/rules` 模板降为兼容层，不再把旧“60 字硬限 / 第二章固定示例 / 泛化格式死规矩”重新注回项目
- `references/templates/scripts/` 现已补齐完整项目脚本链：
  - `template_exhaustion_lint.py`
  - `scene_narrowness_lint.py`
  - `script_version_check.py`
  - `verdict_conflict_lint.py`
  - `chapter_hook_repeat_lint.py`
  - `character_agency_lint.py`
- 已部署项目需重新运行 `story-setup`，以覆盖根模板、rules 模板、完整脚本链，并让版本标记升级到 `agents_version: 14`

### v15

- `story-setup` 现在会把三张新规则卡一起部署到项目内 `.codex/skills/story-setup/references/agent-references/`：
  - `reference-boundary-and-sources-split.md`
  - `chapter-prewrite-card-enforcement.md`
  - `reference-chapter-comparison-protocol.md`
- `narrative-writer` 子代理模板新增对应入口，使用参考书/TXT 情节库写作时，会先按项目内参考边界卡收口，不再只靠主 skill 口头约束
- 已部署项目需重新运行 `story-setup`，以补齐项目内 references bundle 并让版本标记升级到 `agents_version: 15`

### v16

- `story-setup` 现在会把短篇资料包副本一起部署到项目内 `agent-references/`：
  - `material-packs-setting-plot.md`
  - `material-packs-expression.md`
  - `material-packs-character.md`
- `story-architect` 子代理模板补齐短篇起盘入口，部署后的项目可以直接读到人物功能位、关系重组、表达资料包
- 已部署项目需重新运行 `story-setup`，以补齐项目内短篇资料包并让版本标记升级到 `agents_version: 16`

### v17

- `install-codex-project.sh` 正式接管 `CLAUDE.md`、`写作执行铁律.md`、`追踪/上下文.md` 的模板落盘
- 受管模板统一使用 `<!-- managed-by: story-setup -->` 标记；重部署只覆盖受管文件，默认保留用户手写文件
- 已部署项目需重新运行 `story-setup`，以获取托管模板落盘和受管文件保护，并让版本标记升级到 `agents_version: 17`

### v18 (当前)

- `story-setup` 现在会同步部署短篇 profile / 审计 / 回修脚本链到项目 `scripts/`：
  - `generate_story_profile.py`
  - `run_full_ai_audit.py`
  - `auto_revise_ai_flavor.py`
  - `run_revision_cycle.py`
  - `precheck_rewrite_gate.py`
  - `validate_gate_receipts.py`
  - `compare_with_external_block_audit.py`
  - `audit_ai_flavor.py`
  - `audit_novel_ai_flavor.py`
  - `apply_humanizer.py`
  - `normalize-punctuation.js`
- `story-setup` 现在会同步部署短篇治理副本到项目 `.codex/skills/story-setup/references/agent-references/`：
  - `short-write-execution-core.md`
  - `no-external-block-audit-self-check.md`
  - `high-sensitivity-block-audit-rewrite-playbook.md`
  - `gate-pass-checklist.md`
  - `audit-rulebook-coverage.md`
  - `story-profile-schema.md`
  - `profile-source-template.md`
  - `internal-toolchain-map.md`
  - `audit-rulebook.json`
  - `precheck_rewrite_gate.config.json`
  - `通用高风险词类词典.json`
  - `虚词模板词典.json`
- 部署后的 `narrative-writer` 和 `story-architect` 子代理已可直接读取短篇 profile 闭环、高敏桥护栏和“逐条引用正文句子”自检口径
- 已部署项目需重新运行 `story-setup`，以补齐短篇脚本链与治理副本，并让版本标记升级到 `agents_version: 18`
