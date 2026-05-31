---
name: story-setup
version: 1.0.0
description: |
  网文写作工具集基础设施部署。将 `.codex/agents`、hooks、rules、CLAUDE.md 等基础设施部署到用户项目目录。
  触发方式：提到 `/story-setup`、`story-setup`，或直接说「准备写书」「帮我搭一下环境」「配置写作项目」
---

# story-setup：网文写作工具集基础设施部署

你是写作基础设施部署器。将网文写作工具集的全套基础设施（`.codex/agents`、hooks、rules、CLAUDE.md）部署到用户项目目录。

**本分支是 Codex 专用分支。默认只部署 `.codex/*`，不再维护 `.claude/*` 双栈。**

**执行铁律：不覆盖用户已有配置，合并而非替换。**

---

## Phase 1：检测项目状态

1. 检查当前目录是否已部署过（存在 `.story-deployed`）
   - 如果已存在 → 明确提示已部署，并让用户确认是否重新部署
2. 检查是否有书名目录（包含 `追踪/` 子目录的目录，或用户自定义结构）
   - 有 → 识别为长篇项目，显示当前项目信息
   - 无 → 识别为新项目或短篇项目
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

### 2.2 部署公共执行铁律
- 读取 `skills/story-setup/references/templates/写作执行铁律.md.tmpl`
- 若项目内存在明确书名目录，则写入对应小说目录；否则写入项目根目录 `写作执行铁律.md`
- 如果已存在，按“合并而非替换”处理：保留用户自定义附加条款，但必须覆盖/保留硬闸、读前顺序、冲突优先级

### 2.3 部署宿主环境文件

- 从 `references/templates/` 复制模板到目标项目
- Codex 项目级安装脚本为 `scripts/install-codex-project.sh`
- 生成 `.codex/config.toml`
- 生成 `.codex/agents/`、`.codex/hooks/`、`.codex/rules/`
- 生成 `.codex/skills/story-setup/references/agent-references/`
- 确保 `.codex/hooks/` 下脚本有执行权限（chmod +x）
- 同时复制 `.codex/hooks/lib/` 公共脚本

### 2.4 子代理兼容性处理
- 子代理 frontmatter 以当前项目的 Codex 兼容形式为准；如果目标运行环境不支持某些扩展字段，应优先保留最小必需字段后再部署，不要回退到 `.claude/*` 双栈。
- 部署到项目后，子代理内引用的参考资料必须统一走 `story-setup/references/agent-references/*.md` 这一套自带副本，禁止跨 skill 直接引用其他 `story-*/references/*.md`。
- 若全局安装路径不同，优先使用项目内 `skills/` 或 `.codex/skills/` 作为规范路径前缀，其次才依赖宿主的 skill 搜索能力；不要假定固定绝对路径。

### 2.5 部署 Session State 模板
- 读取 `skills/story-setup/references/templates/上下文.md.tmpl`
- 如有书名目录，复制到 `{书名}/追踪/` 下

### 2.6 宿主配置处理
- 如不存在 `.codex/config.toml`，创建最小必需配置
- 如已存在，仅补齐最小必需项，不覆盖用户自定义配置

### 2.7 创建部署标记

- 创建 `.story-deployed` 文件（sentinel file）
- 写入以下字段：
  ```
  deployed_at: <date -u +"%Y-%m-%dT%H:%M:%SZ">
  agents_version: 9
  setup_skill_version: 1.0.0
  target_cli: codex
  resolver_strategy: project-local-skill-reference
  references_dir: .codex/skills/story-setup/references/agent-references
  ```
- 此文件供 session-start.sh 和写作 skill 检测部署状态，避免重复提示
- 如果 `.story-deployed` 已存在但无 `agents_version` 或版本 < 9，提示用户重新运行 `story-setup` 以更新子代理/hooks/rules（v9 补齐 references bundle 与 sentinel 字段并增强 hook 根路径检测；v8 修复子代理读取参考资料路径；v7 修复日更续写 continuation 与伏笔 hook 误报；v6 统一短篇主会话/子代理正文格式；v5 更新 `narrative-writer` 场景写法、段落密度规则和跨平台字数统计）

## Phase 3：验证安装

1. 验证宿主环境文件：
   - 检查 `.codex/config.toml`、`.codex/hooks/`、`.codex/rules/`、`.codex/agents/`
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
4. 不覆盖用户自定义的其他 Codex 配置

## 重新部署

- `.story-deployed` 不存在 → 全新安装，Phase 2 全部执行
- `.story-deployed` 存在且 `agents_version: 9` → 提示已部署，并确认是否重新部署
- `.story-deployed` 存在但 `agents_version` < 9 → 提示需要更新，重新执行 Phase 2 覆盖子代理/hooks/rules，`CLAUDE.md` 走合并策略，`.codex/config.toml` 走保守补齐策略

---

## 参考资料

| 文件 | 用途 |
|------|------|
| references/templates/CLAUDE.md.tmpl | 项目根 CLAUDE.md 模板 |
| references/templates/写作执行铁律.md.tmpl | 项目根公共执行铁律模板 |
| references/templates/hooks/ | 6 个 hook 脚本模板 |
| references/templates/hooks/lib/ | hook 依赖的公共 shell 函数 |
| references/templates/rules/ | 4 条 path-scoped 规则模板 |
| references/templates/subagents/ | 7 个代理模板目录；部署时复制到 `.codex/agents/`（story-architect, character-designer, narrative-writer, consistency-checker, story-researcher, story-explorer, chapter-extractor） |
| references/agent-references/ | 子代理自带参考资料副本；模板统一引用本目录，避免跨 skill 引用失效 |
| references/templates/上下文.md.tmpl | 写作上下文模板 |
