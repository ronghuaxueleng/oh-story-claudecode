---
name: story-setup
version: 1.4.2
description: |
  网文写作工具集基础设施部署。将 `.codex/agents`、hooks、rules、项目级 scripts、`CLAUDE.md` 等宿主基础设施部署到用户项目目录；仅在已存在真实书籍目录时，再补齐 `写作执行铁律.md`、`追踪/上下文.md` 等书内文件。
  触发方式：提到 `/story-setup`、`story-setup`，或直接说「准备写书」「帮我搭一下环境」「配置写作项目」
---

# story-setup：网文写作工具集基础设施部署

你是写作基础设施部署器。将网文写作工具集的全套基础设施（`.codex/agents`、hooks、rules、项目级 scripts、`CLAUDE.md`）部署到用户项目目录；若项目内已经存在真实书籍目录，再继续部署 `写作执行铁律.md`、`追踪/上下文.md` 等书内文件。

**本分支是 Codex 专用分支。默认只部署 `.codex/*`，不再维护 `.claude/*` 双栈。**

**执行铁律：不覆盖用户已有配置，合并而非替换。**

---

## Phase 1：检测项目状态

1. 检查当前目录是否已部署过（存在 `.story-deployed`）
   - 如果已存在 → 明确提示已部署，并让用户确认是否重新部署
2. 检查是否有书名目录（包含 `追踪/` 子目录的目录，或同时包含 `正文/设定/大纲/追踪/` 的真实书目录）
   - 有 → 识别为“书籍模式”，显示当前项目信息
   - 无 → 识别为“宿主模式”；此时只部署宿主基础设施，不创建任何 `正文/设定/大纲/追踪/对标/` 目录，不创建 `.active-book`
3. 检查当前宿主配置文件：
   - 检查 `.codex/config.toml`
   - 存在 → 读取现有配置，后续合并或覆盖
   - 不存在 → 后续创建新文件
4. 检查 `.active-book` 文件是否存在
   - 存在 → 显示当前活跃书目
   - 不存在 → 跳过

## Phase 2：部署基础设施

确认部署位置后，依次执行：

### 2.1 部署 CLAUDE.md
- 读取 `skills/story-setup/references/templates/CLAUDE.md.tmpl`
- 替换占位符（见下方「模板占位符」段）
- 写入项目根目录 `CLAUDE.md`（如已存在，按「CLAUDE.md 合并策略」处理）
- 新版模板必须包含“正文落盘后四连收尾”和“compact/续写前追踪主表核对”要求，避免只同步 `上下文.md` 而漏掉 `时间线.md`、`角色状态.md`、`伏笔.md`、`情报台账.md`
- 当处于“宿主模式”时，`CLAUDE.md` 的文件结构段必须保留 `<书名>/...` 占位说明，不得把 `正文/设定/大纲/追踪/对标/` 直接写成项目根已存在目录

### 2.2 部署公共执行铁律
- 读取 `skills/story-setup/references/templates/写作执行铁律.md.tmpl`
- 若项目内存在明确书名目录，则写入对应小说目录
- 若不存在明确书名目录，跳过本步骤；不得在项目根目录预写 `写作执行铁律.md`
- 如果已存在，按“合并而非替换”处理：保留用户自定义附加条款，但必须覆盖/保留硬闸、读前顺序、冲突优先级
- 新版铁律必须包含“`scene_lint.py -> 写后验收 -> 追踪同步 -> 反读追踪` 四连收尾”与“正文章节号前推但追踪主表未同步时直接按 `F5` 截停”

### 2.3 部署宿主环境文件

- 从 `references/templates/` 复制模板到目标项目
- Codex 项目级安装脚本为 `scripts/install-codex-project.sh`
- 生成 `.codex/config.toml`
- 生成 `.codex/agents/`、`.codex/hooks/`、`.codex/rules/`
- 生成 `.codex/skills/story-setup/references/agent-references/`
- `agent-references/` 必须包含新一轮参考边界卡：`reference-boundary-and-sources-split.md`、`chapter-prewrite-card-enforcement.md`、`reference-chapter-comparison-protocol.md`，避免部署后正文写作仍缺“可借层/禁借层/参考对比”口径
- 生成项目级 `scripts/`，并复制 `references/templates/scripts/*.py` 全套模板脚本；当前最小应包含 `scene_lint.py`、`draft_purity_guard.py`、`template_exhaustion_lint.py`、`scene_narrowness_lint.py`、`script_version_check.py`、`validate_tracking_state.py`、`verdict_conflict_lint.py`、`chapter_hook_repeat_lint.py`、`detect_key_character_promotion.py`、`character_agency_lint.py`、`story_review_regression.py`
- 确保 `.codex/hooks/` 下脚本有执行权限（chmod +x）
- 确保项目 `scripts/*.py` 也有执行权限（chmod +x）
- 同时复制 `.codex/hooks/lib/` 公共脚本
- 新版 hooks 必须在 session start、pre-compact、post-compact 时提示或摘要 `追踪/时间线.md`、`追踪/角色状态.md`、`追踪/伏笔.md`，涉及情报流时还要覆盖 `追踪/情报台账.md`

### 2.4 子代理兼容性处理
- 子代理 frontmatter 以当前项目的 Codex 兼容形式为准；如果目标运行环境不支持某些扩展字段，应优先保留最小必需字段后再部署，不要回退到 `.claude/*` 双栈。
- 部署到项目后，子代理内引用的参考资料必须统一走 `story-setup/references/agent-references/*.md` 这一套自带副本，禁止跨 skill 直接引用其他 `story-*/references/*.md`。
- 若全局安装路径不同，优先使用项目内 `skills/` 或 `.codex/skills/` 作为规范路径前缀，其次才依赖宿主的 skill 搜索能力；不要假定固定绝对路径。

### 2.5 部署 Session State 模板
- 读取 `skills/story-setup/references/templates/上下文.md.tmpl`
- 如有书名目录，复制到 `{书名}/追踪/` 下
- 如无书名目录，跳过；不得为冷启动宿主项目预建 `追踪/` 或 `上下文.md`

### 2.6 宿主配置处理
- 如不存在 `.codex/config.toml`，创建最小必需配置
- 如已存在，仅补齐最小必需项，不覆盖用户自定义配置

### 2.7 创建部署标记

- 创建 `.story-deployed` 文件（sentinel file）
- 写入以下字段：
  ```
  deployed_at: <date -u +"%Y-%m-%dT%H:%M:%SZ">
  agents_version: 15
  setup_skill_version: 1.4.2
  target_cli: codex
  resolver_strategy: project-local-skill-reference
  references_dir: .codex/skills/story-setup/references/agent-references
  ```
- 此文件供 session-start.sh 和写作 skill 检测部署状态，避免重复提示
- 仅当存在真实书籍目录时，才允许创建或更新 `.active-book`
- 如果 `.story-deployed` 已存在但无 `agents_version` 或版本 < 15，提示用户重新运行 `story-setup` 以更新子代理/hooks/rules/scripts（v15 补齐参考边界卡、单章写前卡、参考章节对比协议到 agent-references，并把参考原文使用边界下沉到部署后的子代理；v14 补齐新版根模板、兼容层 rules 模板、项目级完整脚本链；v13 补齐项目级 `story_review_regression.py` 并串联正文/追踪回归链；v12 补齐项目级 `validate_tracking_state.py` 与 `detect_key_character_promotion.py`；v11 补齐追踪同步四连收尾、compact/续写前追踪主表核对、hook 级追踪提醒；v10 补齐项目级 `scene_lint.py` 与 `draft_purity_guard.py`；v9 补齐 references bundle 与 sentinel 字段并增强 hook 根路径检测；v8 修复子代理读取参考资料路径；v7 修复日更续写 continuation 与伏笔 hook 误报；v6 统一短篇主会话/子代理正文格式；v5 更新 `narrative-writer` 场景写法、段落密度规则和跨平台字数统计）

## Phase 3：验证安装

1. 验证宿主环境文件：
   - 检查 `.codex/config.toml`、`.codex/hooks/`、`.codex/rules/`、`.codex/agents/`
   - 检查 `scripts/scene_lint.py`、`scripts/draft_purity_guard.py`、`scripts/template_exhaustion_lint.py`、`scripts/scene_narrowness_lint.py`、`scripts/script_version_check.py`、`scripts/validate_tracking_state.py`、`scripts/verdict_conflict_lint.py`、`scripts/chapter_hook_repeat_lint.py`、`scripts/detect_key_character_promotion.py`、`scripts/character_agency_lint.py`、`scripts/story_review_regression.py`
2. 若为书籍模式，再额外验证书内文件：
   - 检查 `{书名}/写作执行铁律.md`
   - 检查 `{书名}/追踪/上下文.md`
4. 验证部署标记：
   - 检查 `.story-deployed` 是否存在且包含时间戳
5. 输出安装报告：
   - 列出所有已部署的文件
   - 列出需要注意的事项（如已有配置已合并）
   - 提示用户可以开始使用 `/story-long-write`、`story-long-write`、`/story-short-write` 或 `story-short-write`

---

## 模板占位符

| 占位符 | 替换规则 | 示例 |
|--------|----------|------|
| `{项目名}` | 用户项目名称或目录名 | 《剑来》、《暗卫》 |
| `{书名}` | 书名目录名（与目录一致） | 与 `{项目名}` 相同，或用户自定义 |
| `{目标平台}` | 目标发布平台 | 起点、番茄、晋江、知乎盐言 |
| `{作者名}` | 用户笔名或昵称 | 未指定时用「作者」 |

替换时去掉花括号。如果用户未指定项目名，用当前目录名。未指定的占位符保留原样不替换。

## CLAUDE.md 合并策略

用户已有 CLAUDE.md 时，按 section 合并：
1. 读取用户现有 CLAUDE.md，按 `##` 标题切分为 section map
2. 读取模板 CLAUDE.md.tmpl，同样切分
3. 模板中的标准 section（Skill 路由表、文件结构、协作规则、Context Recovery、语言）**覆盖**用户同名 section
4. 用户独有的 section（自定义内容）**保留**不动
5. 未知冲突时明确列出差异，并让用户选择保留哪个版本

## `.codex/config.toml` 处理策略

1. 如果不存在 `.codex/config.toml`，由安装脚本直接创建
2. 如果已存在，优先保留用户已有配置
3. 如缺少 `project_doc_fallback_filenames` 或 `project_doc_max_bytes`，按最小必需配置补齐
4. `project_doc_fallback_filenames` 仅允许宿主项目文档回退文件，默认补齐为 `["CLAUDE.md", "AGENTS.md"]`；不得把 `写作执行铁律.md` 这类流程约束文件写入 fallback 列表
5. 不覆盖用户自定义的其他 Codex 配置

## 重新部署

- `.story-deployed` 不存在 → 全新安装，Phase 2 全部执行
- `.story-deployed` 存在且 `agents_version: 15` → 提示已部署，并确认是否重新部署
- `.story-deployed` 存在但 `agents_version` < 15 → 提示需要更新，重新执行 Phase 2 覆盖子代理/hooks/rules/scripts，`CLAUDE.md` 走合并策略，`.codex/config.toml` 走保守补齐策略

---

## 参考资料

| 文件 | 用途 |
|------|------|
| references/templates/CLAUDE.md.tmpl | 项目根 CLAUDE.md 模板 |
| references/templates/写作执行铁律.md.tmpl | 书籍目录内公共执行铁律模板（仅书籍模式部署） |
| references/templates/hooks/ | 6 个 hook 脚本模板 |
| references/templates/hooks/lib/ | hook 依赖的公共 shell 函数 |
| references/templates/scripts/ | 项目级正文/追踪/回归质检脚本模板（包含 `scene_lint.py`、`draft_purity_guard.py`、`template_exhaustion_lint.py`、`scene_narrowness_lint.py`、`script_version_check.py`、`validate_tracking_state.py`、`verdict_conflict_lint.py`、`chapter_hook_repeat_lint.py`、`detect_key_character_promotion.py`、`character_agency_lint.py`、`story_review_regression.py`） |
| references/templates/rules/ | 4 条 path-scoped 规则模板 |
| references/templates/subagents/ | 7 个代理模板目录；部署时复制到 `.codex/agents/`（story-architect, character-designer, narrative-writer, consistency-checker, story-researcher, story-explorer, chapter-extractor） |
| references/agent-references/ | 子代理自带参考资料副本；模板统一引用本目录，避免跨 skill 引用失效 |
| references/templates/上下文.md.tmpl | 写作上下文模板（仅书籍模式部署） |
