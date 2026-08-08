---
name: story-setup
description: |
  网文写作工具集基础设施部署。将 `.codex/agents`、hooks、rules、项目级 scripts、`CLAUDE.md` 等宿主基础设施部署到用户项目目录；仅在已存在真实书籍目录时，再补齐 `写作执行铁律.md`、`追踪/上下文.md` 等书内文件。
  触发方式：提到 `/story-setup`、`story-setup`，或直接说「准备写书」「帮我搭一下环境」「配置写作项目」
---

# story-setup：网文写作工具集基础设施部署

当前部署版本：`1.6.0`。

你是写作基础设施部署器。将网文写作工具集的全套基础设施（`.codex/agents`、hooks、rules、项目级 scripts、`CLAUDE.md`）部署到用户项目目录；若项目内已经存在真实书籍目录，再继续部署 `写作执行铁律.md`、`追踪/上下文.md` 等书内文件。

**本分支是 Codex 专用分支。默认只部署 `.codex/*`，不再维护 `.claude/*` 双栈。**

**执行铁律：不覆盖用户已有配置，合并而非替换。**

---

## Phase 1：检测项目状态

1. 检查当前目录是否已部署过（存在 `.story-deployed`）
   - 如果已存在 → 明确提示已部署，并让用户确认是否重新部署
2. 检查是否有书名目录（包含 `追踪/`、`正文/`、`正文.md`、`设定/`、`设定.md`、`大纲/` 等书籍结构的候选目录）
   - 先校验候选目录 basename：不得是 `新书-题材-日期`、骨架名、暂定名或内部任务代号；书内 `设定.md`、`小节大纲.md`、`正文.md` 已声明书名时，目录 basename 必须与其逐字一致
   - 通过 → 识别为“书籍模式”，显示当前项目信息
   - 不通过 → 只列为疑似书目录并阻断书内文件部署；先确认正式书名、重命名目录并同步内部路径，不得把工作代号写入模板或 `.active-book`
   - 无 → 识别为“宿主模式”；此时只部署宿主基础设施，不创建任何 `正文/设定/大纲/追踪/对标/` 目录，不创建 `.active-book`
3. 检查当前宿主配置文件：
   - 检查 `.codex/config.toml`
   - 存在 → 读取现有配置，后续合并或覆盖
   - 不存在 → 后续创建新文件
4. 检查 `.active-book` 文件是否存在
   - 存在且目标位于项目根内、目录存在并通过正式书名目录校验 → 显示当前活跃书目
   - 指向工作代号、不存在目录或项目根外路径 → 视为无效，不得让 hooks 采用
   - 不存在 → 跳过

## Phase 2：部署基础设施

确认部署位置后，依次执行：

### 2.1 部署 CLAUDE.md
- 读取 `skills/story-setup/references/templates/CLAUDE.md.tmpl`
- 替换占位符（见下方「模板占位符」段）
- 写入项目根目录 `CLAUDE.md`（如已存在，按「CLAUDE.md 合并策略」处理）
- 模板落盘统一由 `scripts/install-codex-project.sh` 执行；模板文件自带 `<!-- managed-by: story-setup -->` 标记，后续重部署只覆盖受管文件，不强盖用户手写文件
- 新版模板必须包含“正文落盘后四连收尾”和“compact/续写前追踪主表核对”要求，避免只同步 `上下文.md` 而漏掉 `时间线.md`、`角色状态.md`、`伏笔.md`、`情报台账.md`
- 当处于“宿主模式”时，`CLAUDE.md` 的文件结构段必须保留 `<书名>/...` 占位说明，不得把 `正文/设定/大纲/追踪/对标/` 直接写成项目根已存在目录

### 2.2 部署公共执行铁律
- 读取 `skills/story-setup/references/templates/写作执行铁律.md.tmpl`
- 若项目内存在明确书名目录，则写入对应小说目录
- 若不存在明确书名目录，跳过本步骤；不得在项目根目录预写 `写作执行铁律.md`
- 如果已存在且带 `<!-- managed-by: story-setup -->`，允许重部署覆盖；如果是不带标记的用户手写文件，默认跳过，不覆盖
- 新版铁律必须包含“`scene_lint.py -> 写后验收 -> 追踪同步 -> 反读追踪` 四连收尾”与“正文章节号前推但追踪主表未同步时直接按 `F5` 截停”

### 2.3 部署宿主环境文件

- 从 `references/templates/` 复制模板到目标项目
- Codex 项目级安装脚本为 `scripts/install-codex-project.sh`
- 生成 `.codex/config.toml`
- 生成 `.codex/agents/`、`.codex/hooks/`、`.codex/rules/`
- 生成 `.codex/skills/story-setup/references/agent-references/`
- `agent-references/` 必须包含新一轮参考边界卡：`reference-boundary-and-sources-split.md`、`chapter-prewrite-card-enforcement.md`、`reference-chapter-comparison-protocol.md`，避免部署后正文写作仍缺“可借层/禁借层/参考对比”口径
- `agent-references/` 还必须包含短篇资料包副本：`material-packs-setting-plot.md`、`material-packs-expression.md`、`material-packs-character.md`，避免短篇写作和拆文部署后缺“情节融合 / 口气模板 / 人物功能位”材料库
- `agent-references/` 还必须包含短篇治理与审计副本：`short-write-execution-core.md`、`no-external-block-audit-self-check.md`、`high-sensitivity-block-audit-rewrite-playbook.md`、`gate-pass-checklist.md`、`audit-rulebook-coverage.md`、`story-profile-schema.md`、`profile-source-template.md`、`internal-toolchain-map.md`，以及 `audit-rulebook.json`、`precheck_rewrite_gate.config.json`、`通用高风险词类词典.json`、`虚词模板词典.json`，避免部署后短篇高敏回修仍缺正式规则包
- 生成项目级 `scripts/`，复制 `references/templates/scripts/*` 全套模板脚本。部署包必须覆盖 `story-long-write/scripts/`、`story-short-write/scripts/`、`story-short-analyze/scripts/` 中全部正式 `.py/.js`，不得只维护一份容易过期的手写文件名枚举
- 正式书名确定后，创建书内文件前必须运行 `validate_project_directory_name.py --project-dir <目录> --title <正式书名>`；结构探测只能找候选目录，不能替代正式书名确认
- 修改任一上游脚本、治理文档、agent reference、hook、rule 或 agent 后，必须运行 `python3 skills/story-setup/scripts/validate_bundle.py`；出现缺文件、旧副本或死链接时不得发布
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
- 若 `追踪/上下文.md` 已存在且带 `<!-- managed-by: story-setup -->`，允许重部署覆盖；若为用户手写文件，默认跳过

### 2.6 宿主配置处理
- 如不存在 `.codex/config.toml`，创建最小必需配置
- 如已存在，仅补齐最小必需项，不覆盖用户自定义配置

### 2.7 创建部署标记

- 创建 `.story-deployed` 文件（sentinel file）
- 写入以下字段：
  ```
  deployed_at: <date -u +"%Y-%m-%dT%H:%M:%SZ">
  agents_version: 19
  setup_skill_version: 1.6.0
  target_cli: codex
  resolver_strategy: project-local-skill-reference
  references_dir: .codex/skills/story-setup/references/agent-references
  ```
- 此文件供 session-start.sh 和写作 skill 检测部署状态，避免重复提示
- 仅当目录通过正式书名校验时，才允许创建或更新 `.active-book`；只有一个有效书目录时写入项目内相对路径，多书时只采用已通过校验的用户选择
- 如果 `.story-deployed` 已存在但无 `agents_version` 或版本 < 19，提示用户重新运行 `story-setup`。v19 增加正式书名目录硬闸、统一安装器与 hooks 的书目发现条件、补齐长篇写作/短篇写作/短篇拆文正式脚本与治理文档，并加入部署包完整性校验；更早版本沿用各自既有升级说明

## Phase 3：验证安装

1. 验证宿主环境文件：
   - 检查 `.codex/config.toml`、`.codex/hooks/`、`.codex/rules/`、`.codex/agents/`
   - 运行 `python3 skills/story-setup/scripts/validate_bundle.py`，检查全部正式 scripts、hooks、rules、agents、基础模板、治理资料、上游版本和 Markdown 内部链接
   - 安装后逐项比较 `references/templates/scripts/` 与项目 `scripts/`、`references/agent-references/` 与项目 `.codex/skills/story-setup/references/agent-references/`，不得只抽查旧版最小清单
2. 若为书籍模式，再额外验证书内文件：
   - 检查 `{书名}/写作执行铁律.md`
   - 检查 `{书名}/追踪/上下文.md`
3. 验证部署标记：
   - 检查 `.story-deployed` 是否存在且包含时间戳
4. 输出安装报告：
   - 列出所有已部署的文件
   - 列出需要注意的事项（如已有配置已合并）
   - 提示用户可以开始使用 `/story-long-write`、`story-long-write`、`/story-short-write` 或 `story-short-write`

---

## 模板占位符

| 占位符 | 替换规则 | 示例 |
|--------|----------|------|
| `{项目名}` | 宿主项目名称；用户未指定时可用宿主根目录名 | 小说工作区 |
| `{书名}` | 已确认的小说正式书名；必须与书目录 basename 一致，不得回退为宿主目录名或工作代号 | 他把我的旧录像送给白月光后，我离婚了 |
| `{目标平台}` | 目标发布平台 | 起点、番茄、晋江、知乎盐言 |
| `{作者名}` | 用户笔名或昵称 | 未指定时用「作者」 |

替换时去掉花括号。如果用户未指定项目名，`{项目名}` 可用当前宿主目录名。没有已确认正式书名时，保留 `{书名}` 占位符并跳过所有书内模板；不得用 `{项目名}`、当前目录名或疑似书目录名补成 `{书名}`。

## CLAUDE.md 合并策略

用户已有 CLAUDE.md 时，按 section 合并：
1. 读取用户现有 CLAUDE.md，按 `##` 标题切分为 section map
2. 读取模板 CLAUDE.md.tmpl，同样切分
3. 模板实际拥有的标准 section（如 Skill 路由表、文件结构、协作规则、Compact 后恢复上下文）**覆盖**用户同名 section
4. 用户独有的 section（自定义内容）**保留**不动
5. 只按完整二级标题精确匹配；标题不同的用户 section 一律保留，不做模糊覆盖

## `.codex/config.toml` 处理策略

1. 如果不存在 `.codex/config.toml`，由安装脚本直接创建
2. 如果已存在，优先保留用户已有配置
3. 如缺少 `project_doc_fallback_filenames` 或 `project_doc_max_bytes`，按最小必需配置补齐
4. `project_doc_fallback_filenames` 仅允许宿主项目文档回退文件，默认补齐为 `["CLAUDE.md", "AGENTS.md"]`；不得把 `写作执行铁律.md` 这类流程约束文件写入 fallback 列表
5. 不覆盖用户自定义的其他 Codex 配置

## 重新部署

- `.story-deployed` 不存在 → 全新安装，Phase 2 全部执行
- `.story-deployed` 存在且 `agents_version: 19` → 提示已部署，并确认是否重新部署
- `.story-deployed` 存在但 `agents_version` < 19 → 提示需要更新，重新执行 Phase 2 覆盖子代理/hooks/rules/scripts/references，模板文件按受管标记覆盖，用户手写文件默认保留，`.codex/config.toml` 走保守补齐策略

---

## 参考资料

| 文件 | 用途 |
|------|------|
| references/templates/CLAUDE.md.tmpl | 项目根 CLAUDE.md 模板 |
| references/templates/写作执行铁律.md.tmpl | 书籍目录内公共执行铁律模板（仅书籍模式部署） |
| references/templates/hooks/ | 生命周期与写作门禁 hook 脚本及公共函数库 |
| references/templates/hooks/lib/ | hook 依赖的公共 shell 函数 |
| references/templates/scripts/ | 长篇写作、短篇写作、短篇拆文的完整项目级脚本部署副本；具体清单由 `scripts/validate_bundle.py` 对上游自动核对 |
| references/templates/rules/ | 4 条 path-scoped 规则模板 |
| references/templates/subagents/ | 7 个代理模板目录；部署时复制到 `.codex/agents/`（story-architect, character-designer, narrative-writer, consistency-checker, story-researcher, story-explorer, chapter-extractor） |
| references/agent-references/ | 子代理自带参考资料副本；模板统一引用本目录，避免跨 skill 引用失效 |
| references/agent-references/material-packs-setting-plot.md | 短篇情节/设定/冲突/融合写法资料包副本，供起盘、补冲突、做融合写作时调用 |
| references/agent-references/material-packs-expression.md | 短篇表达/口气/开头句/虐点表达资料包副本，供角色口气设计与正文修辞调用 |
| references/agent-references/material-packs-character.md | 短篇人物功能位/关系重组/接住者与对照组资料包副本，供人物与关系设计调用 |
| references/agent-references/short-write-execution-core.md | 短篇 profile 闭环、审计优先级、逐条引用正文句子的自检口径副本 |
| references/agent-references/no-external-block-audit-self-check.md | 无外部分块审计时的块级自检副本，要求每个判断贴正文原句 |
| references/agent-references/high-sensitivity-block-audit-rewrite-playbook.md | 短篇高敏桥段第二闸门与回修停机口径副本 |
| references/agent-references/story-profile-schema.md | `book.profile.json / project.profile.json / story_guardrails` 结构合同副本 |
| references/agent-references/audit-rulebook.json | 短篇正式审计规则簿副本，供项目内审计脚本直接读取 |
| references/templates/上下文.md.tmpl | 写作上下文模板（仅书籍模式部署） |
| scripts/validate_bundle.py | 校验部署包文件齐全、上游版本同步和内部链接完整性 |
