# Skills Flow 总览

这份文档汇总仓库内各个 skill 的用途、触发方式、核心流程、依赖文件与典型产出。

目标不是替代各自的 `SKILL.md`，而是提供一个“先看全局、再钻细节”的入口。

## 文档约定

- `主流程` 只回答“分几步做”
- `主流程使用的文件` 只回答“会读写哪些文件”
- 如果要让流程真正可执行，仅有 `Phase 名称` 不够，还应继续补：
  - 这一阶段实际动作
  - 关键判断条件
  - 直接调用的脚本或命令
  - 阶段完成后的产物
- 因此下面的 skill 中，凡是适合命令化的，我都补了 `Phase 执行动作 / 命令`；不适合直接 shell 化的，则写成“操作动作 + 读取/写入目标”。

## 1. `story`

- 作用：网文工具箱总入口，负责把用户需求路由到更具体的 skill。
- 触发：`story`、`网文`、`我想写小说`、`帮我写书`、`写网文`
- 主流程：
  1. 识别用户意图
  2. 按路由表匹配到写作 / 拆文 / 扫榜 / 去 AI 味 / 封面 / 部署等 skill
  3. 结合项目状态决定是否可直接进入下游 skill
- 依赖：
  - `skills/story/SKILL.md`
- 主流程使用的文件：
  - 读取：`skills/story/SKILL.md`
  - 读取：项目目录状态文件，如 `.active-book`、`追踪/上下文.md`、`大纲/`、`正文/`（按路由需要）
  - 下游转交：对应 skill 的 `SKILL.md`
- 产出：
  - 不直接产出内容
  - 负责把请求交给下游 skill

## 2. `story-setup`

- 作用：给小说项目部署 Codex 写作基础设施。
- 触发：`story-setup`、`准备写书`、`帮我搭一下环境`、`配置写作项目`
- 主流程：
  1. Phase 1：检测项目状态
  2. Phase 2：部署基础设施
  3. Phase 3：验证安装
  4. 若存在旧部署，根据 `.story-deployed`、`agents_version` 走升级或重部署逻辑
- Phase 执行动作 / 命令：
  - Phase 1：检查目标目录中是否已有 `.story-deployed`、`.codex/`、`CLAUDE.md`
  - Phase 1：读取 `.story-deployed` 判断是否首次部署或升级部署
  - Phase 2：把模板写入项目目录，对已有文件按合并策略处理
  - Phase 2：典型入口命令：`bash scripts/install-codex-project.sh <项目目录>`
  - Phase 3：检查 `.codex/agents/`、`.codex/hooks/`、`.codex/rules/`、`.codex/config.toml` 是否齐全
  - Phase 3：必要时执行 hooks 做烟测，如 `bash .codex/hooks/session-start.sh`
- 依赖：
  - `skills/story-setup/SKILL.md`
  - 模板目录：`skills/story-setup/references/templates/`
- 主流程使用的文件：
  - 读取：`skills/story-setup/SKILL.md`
  - 读取：`skills/story-setup/references/templates/CLAUDE.md.tmpl`
  - 读取：`skills/story-setup/references/templates/subagents/*.md`
  - 读取：`skills/story-setup/references/templates/hooks/*`
  - 读取：`skills/story-setup/references/templates/rules/*`
  - 读取：项目中的 `.story-deployed`、`CLAUDE.md`、`.codex/config.toml`
  - 写入：项目根目录 `CLAUDE.md`
  - 写入：`.codex/config.toml`
  - 写入：`.codex/agents/*.md`
  - 写入：`.codex/hooks/*`
  - 写入：`.codex/rules/*`
  - 写入：`.story-deployed`
- 典型产出：
  - 项目根目录 `CLAUDE.md`
  - `.codex/config.toml`
  - `.codex/agents/*.md`
  - `.codex/hooks/*`
  - `.codex/rules/*`
  - `.story-deployed`

## 3. `story-long-write`

- 作用：长篇网文从开书到日更到回炉的主写作 skill。
- 触发：`story-long-write`、`写长篇`、`帮我开书`、`写大纲`、`日更`、`续写`、`继续写`、`修改第X章`、`回炉`、`重写第X章`
- 场景分流：
  - 开书：完整执行 Phase 1→2→3→4→5
  - 日更续写：加载 `references/workflow-daily.md`
  - 大修：加载 `references/workflow-revision.md`
- 主流程：
  1. Phase 1：确认选题方向
  2. Phase 2：核心设定
  3. Phase 3：大纲搭建
  4. Phase 4：正文写作辅助
  5. Phase 5：持续迭代与质量控制
- Phase 执行动作 / 命令：
  - Phase 1：读取用户需求、对标信息、项目已有设定，确定题材与目标平台
  - Phase 2：生成或补齐核心设定文件，如 `设定/关系.md`、`设定/题材定位.md`
  - Phase 3：生成或补齐 `大纲/大纲.md`、`卷纲_*.md`、`细纲_第XXX章.md`
  - Phase 4：读取当前章细纲与追踪文件，生成或修改 `正文/第XXX章_*.md`
  - Phase 5：回写 `追踪/上下文.md`、`追踪/伏笔.md`、`追踪/时间线.md`
  - 日更续写时，不是固定 shell 命令，而是优先按 `references/workflow-daily.md` 的步骤读取和回写项目文件
  - 大修时，优先按 `references/workflow-revision.md` 重审细纲、正文、追踪再落稿
- 可选子代理：
  - `story-architect`
  - `character-designer`
  - 其他项目内已部署的写作子代理
- 依赖：
  - `skills/story-long-write/SKILL.md`
  - `skills/story-long-write/references/workflow-daily.md`
  - `skills/story-long-write/references/workflow-revision.md`
  - `skills/story-long-write/references/artifact-protocols.md`
  - `skills/story-long-write/references/opening-design.md`
  - 其余 `references/*.md` 为写作方法库
- 主流程使用的文件：
  - 读取：`skills/story-long-write/SKILL.md`
  - 读取：`skills/story-long-write/references/workflow-daily.md`
  - 读取：`skills/story-long-write/references/workflow-revision.md`
  - 读取：`skills/story-long-write/references/artifact-protocols.md`
  - 读取：`skills/story-long-write/references/opening-design.md`
  - 读取：其余相关方法库，如 `outline-*.md`、`hooks-*.md`、`writing-craft.md`、`quality-checklist.md`
  - 读取：项目中的 `.active-book`
  - 读取：书目录下 `设定/`、`大纲/`、`正文/`、`追踪/`
  - 重点读取：`大纲/细纲_第XXX章.md`、`追踪/上下文.md`、`追踪/伏笔.md`、`追踪/时间线.md`
  - 写入：`设定/关系.md`
  - 写入：`设定/题材定位.md`
  - 写入：`大纲/大纲.md`
  - 写入：`大纲/卷纲_第X卷.md`
  - 写入：`大纲/细纲_第XXX章.md`
  - 写入：`正文/第XXX章_章名.md`
  - 写入：`追踪/伏笔.md`
  - 写入：`追踪/时间线.md`
  - 写入：`追踪/上下文.md`
- 典型产出：
  - `设定/关系.md`
  - `设定/题材定位.md`
  - `大纲/大纲.md`
  - `大纲/卷纲_第X卷.md`
  - `大纲/细纲_第XXX章.md`
  - `正文/第XXX章_章名.md`
  - `追踪/伏笔.md`
  - `追踪/时间线.md`
  - `追踪/上下文.md`

## 4. `story-short-write`

- 作用：短篇网文写作，偏情绪、反转、节奏密度。
- 触发：`story-short-write`、`写短篇`、`帮我写一篇短篇`、`写个盐言故事`
- 主流程：
  1. Phase 1：确定情绪目标
  2. Phase 2：构思核心框架
  3. Phase 3：逐场景写作
  4. 按 `writing-workflow.md` 完成小节大纲、反转验证、伏笔回查
- Phase 执行动作 / 命令：
  - Phase 1：确定短篇要打的核心情绪，如爽、虐、甜、反转、悬疑
  - Phase 2：按 `writing-workflow.md` 生成核心框架、小节规划、角色关系
  - Phase 3：按段推进正文，每批写 2-3 节并回查字数与节奏
  - 这类 skill 通常不是跑 shell 命令，而是按模板文件驱动写作
- 可选子代理：
  - `story-architect`
  - `character-designer`
  - `narrative-writer`
- 依赖：
  - `skills/story-short-write/SKILL.md`
  - `skills/story-short-write/references/writing-workflow.md`
  - 其余 `references/*.md` 为短篇方法库
- 主流程使用的文件：
  - 读取：`skills/story-short-write/SKILL.md`
  - 读取：`skills/story-short-write/references/writing-workflow.md`
  - 读取：短篇方法库，如 `hooks-*.md`、`reversal-toolkit.md`、`writing-craft.md`
  - 读取：项目中的短篇大纲、设定、人物文件
  - 写入：短篇正文文件
  - 写入：小节大纲或过程性结构文件（如项目中启用）
- 典型产出：
  - 短篇正文
  - 小节大纲
  - 反转与伏笔检查结果

## 5. `story-long-analyze`

- 作用：拆解长篇网文，支持快速模式与深度模式。
- 触发：`story-long-analyze`、`长篇拆文`、`帮我拆这本书`、`分析黄金三章`
- 模式分流：
  - 快速模式：默认，做黄金三章 + 整体结构 + 报告
  - 深度模式：用户明确要求完整拆解，或提供原文路径
- 主流程：
  - 快速模式：
    1. Phase 1：确认拆解对象 + 路由
    2. Phase 2：黄金三章逐章拆解
    3. Phase 3：整体结构拆解
    4. Phase 4：输出拆文报告
  - 深度模式：
    1. Phase 2B：进入深度拆解管道
    2. 原文备份
    3. 分块拆解、质量门控、恢复机制
    4. 汇总结构化结果
- Phase 执行动作 / 命令：
  - Phase 1：确认输入是书名、文本、章节目录还是已有项目
  - 快速 Phase 2-4：按 `output-templates.md` 模板直接输出结构分析
  - 深度模式：先备份原文，再分块读取章节做结构化拆解
  - 深度模式通常是“读取文件 -> 按模板分析 -> 写回结果”，不依赖固定单一 shell 命令
- 依赖：
  - `skills/story-long-analyze/SKILL.md`
  - `skills/story-long-analyze/references/output-templates.md`
  - `skills/story-long-analyze/references/material-decomposition.md`
  - `skills/story-long-analyze/references/deconstruction-notes.md`
- 主流程使用的文件：
  - 读取：`skills/story-long-analyze/SKILL.md`
  - 读取：`skills/story-long-analyze/references/output-templates.md`
  - 读取：`skills/story-long-analyze/references/material-decomposition.md`
  - 读取：`skills/story-long-analyze/references/deconstruction-notes.md`
  - 读取：用户提供的小说原文、章节文件或书籍目录
  - 深度模式写入：拆解目录、阶段性分析文件、拆文报告
  - 快速模式写入：`拆文报告.md` 或对话内报告
- 典型产出：
  - 快速拆文报告
  - 深度拆解目录与结构化章节分析

## 6. `story-short-analyze`

- 作用：拆解短篇网文，重点看结构、情绪曲线、反转和首尾。
- 触发：`story-short-analyze`、`短篇拆文`、`帮我拆这个短篇`、`分析这篇故事`
- 主流程：
  1. Phase 1：确认拆解对象 + 题材路由
  2. Phase 2：全篇结构拆解
  3. Phase 2.5：人设速写
  4. Phase 3：情绪曲线分析
  5. Phase 4：反转设计分析
  6. Phase 5：开头与结尾分析
  7. Phase 6：输出拆文报告
- Phase 执行动作 / 命令：
  - Phase 1：确认题材与目标读者
  - Phase 2-6：按 `output-templates.md` 顺序完成结构、情绪、反转、首尾分析
  - 主要是模板驱动分析，不依赖固定脚本命令
- 依赖：
  - `skills/story-short-analyze/SKILL.md`
  - `skills/story-short-analyze/references/output-templates.md`
  - 其余 `references/*.md` 为短篇分析方法库
- 主流程使用的文件：
  - 读取：`skills/story-short-analyze/SKILL.md`
  - 读取：`skills/story-short-analyze/references/output-templates.md`
  - 读取：其余短篇分析方法库，如 `hooks-*.md`、`genre-*.md`、`quality-checklist.md`
  - 读取：用户提供的短篇原文或章节文件
  - 写入：短篇拆文报告
- 典型产出：
  - 短篇拆文报告
  - 结构、情绪、反转、首尾分析

## 7. `story-long-scan`

- 作用：扫长篇平台榜单，提炼题材热度、平台偏好与市场机会。
- 触发：`story-long-scan`、`长篇扫榜`、`长篇什么火`、`起点排行`
- 主流程：
  1. Phase 1：确认平台和方向
  2. Phase 1.5：确定数据来源
  3. 采集质量检查
  4. Phase 2：数据分析
  5. 输出平台趋势与选题洞察
- Phase 执行动作 / 命令：
  - Phase 1：确认要扫的平台，如起点、番茄、晋江、七猫、刺猬猫
  - Phase 1.5：判断走公开榜单、页面抓取还是登录态抓取
  - Phase 1.5：典型脚本命令示例：`node skills/story-long-scan/scripts/fanqie-rank-scraper.js`
  - Phase 1.5：典型脚本命令示例：`node skills/story-long-scan/scripts/qidian-rank-scraper.js`
  - Phase 1.5：如需浏览器登录态，先走 `browser-cdp` 或 `cdp-utils.js`
  - Phase 2：读取采集结果，按 `scan-output-format.md` 聚合成趋势分析
- 依赖：
  - `skills/story-long-scan/SKILL.md`
  - `skills/story-long-scan/scripts/*.js`
  - `skills/story-long-scan/references/genre-trends.md`
  - `skills/story-long-scan/references/reader-profiling.md`
  - `skills/story-long-scan/references/publishing-guide.md`
  - `skills/story-long-scan/references/scan-output-format.md`
- 主流程使用的文件：
  - 读取：`skills/story-long-scan/SKILL.md`
  - 读取：`skills/story-long-scan/references/scan-output-format.md`
  - 读取：`skills/story-long-scan/references/genre-trends.md`
  - 读取：`skills/story-long-scan/references/reader-profiling.md`
  - 读取：`skills/story-long-scan/references/publishing-guide.md`
  - 调用脚本：`skills/story-long-scan/scripts/qidian-rank-scraper.js`
  - 调用脚本：`skills/story-long-scan/scripts/fanqie-rank-scraper.js`
  - 调用脚本：`skills/story-long-scan/scripts/jjwxc-rank-scraper.js`
  - 调用脚本：`skills/story-long-scan/scripts/qimao-rank-scraper.js`
  - 调用脚本：`skills/story-long-scan/scripts/ciweimao-rank-scraper.js`
  - 调用脚本：`skills/story-long-scan/scripts/cdp-utils.js`
  - 写入：采集结果文件、扫榜报告、缓存数据（按执行方式）
- 典型产出：
  - 榜单采集结果
  - 平台趋势分析
  - 热门题材与读者偏好结论

## 8. `story-short-scan`

- 作用：扫短篇平台榜单，抓情绪热点、题材风口与平台差异。
- 触发：`story-short-scan`、`短篇扫榜`、`短篇什么火`、`知乎故事排行`
- 主流程：
  1. Phase 1：确认平台和方向
  2. Phase 1.5：确定数据来源
  3. Phase 2：数据分析
  4. Phase 3：输出扫榜报告
  5. Phase 4：选题建议
- Phase 执行动作 / 命令：
  - Phase 1：确认平台，如知乎盐言、点众、黑岩等
  - Phase 1.5：根据平台决定是否需要登录态
  - Phase 1.5：典型脚本命令示例：`node skills/story-short-scan/scripts/dz-browse-scraper.js`
  - Phase 1.5：典型脚本命令示例：`node skills/story-short-scan/scripts/heiyan-booklist-scraper.js`
  - Phase 2-4：读取采集数据，输出市场概况、热度排行、选题建议
- 依赖：
  - `skills/story-short-scan/SKILL.md`
  - `skills/story-short-scan/scripts/*.js`
  - `skills/story-short-scan/references/real-market-data.md`
- 主流程使用的文件：
  - 读取：`skills/story-short-scan/SKILL.md`
  - 读取：`skills/story-short-scan/references/real-market-data.md`
  - 调用脚本：`skills/story-short-scan/scripts/dz-browse-scraper.js`
  - 调用脚本：`skills/story-short-scan/scripts/heiyan-booklist-scraper.js`
  - 调用脚本：`skills/story-short-scan/scripts/cdp-utils.js`
  - 写入：短篇榜单采集结果、扫榜报告
- 典型产出：
  - 平台扫榜报告
  - 情绪热度排行
  - 值得写的方向与风口预警

## 9. `story-deslop`

- 作用：去除网文中的 AI 味，回到更自然、更像真人写作的表达。
- 触发：`story-deslop`、`去AI味`、`去味`、`deslop`、`这篇太AI了`
- 主流程：
  1. Phase 1：AI 味扫描
  2. Phase 2：诊断与分级
  3. Phase 3：逐项清除
  4. 必要时调用子代理执行改写
- Phase 执行动作 / 命令：
  - Phase 1：读取正文，扫描套话、空洞抒情、模板化递进、口水解释
  - Phase 2：按轻 / 中 / 重度 AI 味分级
  - Phase 3：逐段改写并回写正文
  - 该 skill 以文本改写为主，不依赖固定 shell 命令
- 可选子代理：
  - `narrative-writer`
- 依赖：
  - `skills/story-deslop/SKILL.md`
  - `skills/story-deslop/references/anti-ai-writing.md`
  - `skills/story-deslop/references/banned-words.md`
- 主流程使用的文件：
  - 读取：`skills/story-deslop/SKILL.md`
  - 读取：`skills/story-deslop/references/anti-ai-writing.md`
  - 读取：`skills/story-deslop/references/banned-words.md`
  - 读取：待去味的正文文件
  - 写入：改写后的正文文件，或输出去味版本
- 典型产出：
  - AI 味检测报告
  - 清洗后的正文版本

## 10. `story-review`

- 作用：多视角并行审查，适合正文、细纲、设定、卷纲的综合评审。
- 触发：`story-review`、`审查`、`审查一下`、`帮我审一下`
- 模式：
  - `full`：完整多代理对抗式审查
  - `lean`：精简版审查
- 主流程（`full`）：
  1. Phase 1：收集待审查内容
  2. Phase 1.5：可选 `story-explorer` 预查询
  3. Phase 2：并行 spawn 4 个子代理
  4. Phase 3：综合裁决
  5. Phase 4：输出报告
- Phase 执行动作 / 命令：
  - Phase 1：读取正文、细纲、卷纲、设定、追踪文件
  - Phase 1.5：必要时先让 `story-explorer` 查询上下文
  - Phase 2：按不同视角并行拉起子代理做评审
  - Phase 3：汇总冲突意见，给出主裁决
  - Phase 4：按 `quality-rubric.md` 输出正式审查报告
- 依赖：
  - `skills/story-review/SKILL.md`
  - `skills/story-review/references/quality-rubric.md`
  - `skills/story-review/references/banned-words.md`
- 主流程使用的文件：
  - 读取：`skills/story-review/SKILL.md`
  - 读取：`skills/story-review/references/quality-rubric.md`
  - 读取：`skills/story-review/references/banned-words.md`
  - 读取：待审查正文、细纲、设定、卷纲、追踪文件
  - 写入：审查报告或评审结论
- 典型产出：
  - `Verdict Summary`
  - 综合评定
  - 发现的问题
  - 修改建议

## 11. `story-import`

- 作用：把已写小说反向整理为本项目的标准目录结构。
- 触发：`story-import`、`导入小说`、`反向解析`、`导入`、`把我的书导进来`
- 主流程：
  1. Phase 1：确认导入源
  2. Phase 2：深度分析
  3. Phase 3：结构迁移
  4. 迁移人物、设定、大纲、正文与追踪信息
- Phase 执行动作 / 命令：
  - Phase 1：确认输入是单文件、章节目录还是旧项目
  - Phase 2：抽取人物、设定、章节结构、时间线
  - Phase 3：按 `structure-mapping.md` 写入标准目录结构
  - 这是文件迁移型 skill，核心是“读旧结构 -> 写新结构”
- 依赖：
  - `skills/story-import/SKILL.md`
  - `skills/story-import/references/structure-mapping.md`
- 主流程使用的文件：
  - 读取：`skills/story-import/SKILL.md`
  - 读取：`skills/story-import/references/structure-mapping.md`
  - 读取：用户提供的原始小说文本、章节目录、旧项目结构
  - 写入：标准化后的 `设定/`、`大纲/`、`正文/`、`追踪/`
- 典型产出：
  - 标准化后的书籍目录
  - 角色、设定、关系、大纲、正文、追踪文件

## 12. `story-cover`

- 作用：根据书名、作者名、题材方向生成网文封面。
- 触发：`story-cover`、`封面`、`帮我做个封面`、`生成封面图`、`做个小说封面`、`封面设计`
- 主流程：
  1. 检查 API 配置
  2. 选择封面风格与构图
  3. 组装提示词
  4. 调用图像生成接口
  5. 必要时做参数兼容回退
- Phase 执行动作 / 命令：
  - Phase 1：检查图像接口配置与环境变量
  - Phase 2：根据题材和平台定位选择风格
  - Phase 3：组装标题、作者名、主体画面提示词
  - Phase 4：调用图像生成接口输出图片
  - 若渠道不兼容参数，按 skill 中回退逻辑重试
- 依赖：
  - `skills/story-cover/SKILL.md`
  - `skills/story-cover/references/cover-styles.md`
- 主流程使用的文件：
  - 读取：`skills/story-cover/SKILL.md`
  - 读取：`skills/story-cover/references/cover-styles.md`
  - 读取：书名、作者名、题材信息，必要时读取项目设定文件
  - 写入：封面图片文件，或生成结果链接/说明
- 典型产出：
  - 封面图片
  - 风格说明或备选方案

## 13. `browser-cdp`

- 作用：通过 Chrome DevTools Protocol 复用浏览器登录态与页面会话。
- 触发：浏览器自动化、CDP、浏览器操作、Chrome CDP、复用登录态、提取 token
- 主流程：
  1. 启动 CDP Chrome 环境
  2. 打开页面 / 复用会话
  3. 执行常用浏览器操作
  4. 从 localStorage 或 cookie 提取信息
  5. 必要时排查常见问题
- Phase 执行动作 / 命令：
  - Phase 1：典型命令：`node skills/browser-cdp/scripts/setup-cdp-chrome.js`
  - Phase 2：连接本机 Chrome 的调试端口，复用已有登录态
  - Phase 3：执行页面打开、点击、抓取、评估脚本等操作
  - Phase 4：从 localStorage、cookie、页面变量中提取 token 或状态
- 依赖：
  - `skills/browser-cdp/SKILL.md`
  - `skills/browser-cdp/scripts/setup-cdp-chrome.js`
- 主流程使用的文件：
  - 读取：`skills/browser-cdp/SKILL.md`
  - 调用脚本：`skills/browser-cdp/scripts/setup-cdp-chrome.js`
  - 读取 / 使用：本机 Chrome 用户数据目录、CDP 端口信息
  - 输出：浏览器会话信息、页面数据、提取到的 token
- 典型产出：
  - 已连接的 CDP Chrome 会话
  - 登录态、token、页面数据

## 14. `story-agent-dispatch`

- 作用：Codex 侧子代理调度器，把上游 skill 的子代理请求转发到 `.codex/agents/`。
- 触发：通常不直接面向终端用户，而是作为内部调度 skill 使用
- 主流程：
  1. 读取上游传入的子代理调用请求
  2. 校验格式
  3. 映射到 `.codex/agents/` 对应代理
  4. 返回标准化结果
- Phase 执行动作 / 命令：
  - Phase 1：接收上游 skill 传入的调度参数
  - Phase 2：校验子代理名、输入格式、目标路径
  - Phase 3：映射到 `.codex/agents/*.md`
  - Phase 4：输出规范化调度结果
- 依赖：
  - `skills/story-agent-dispatch/SKILL.md`
- 主流程使用的文件：
  - 读取：`skills/story-agent-dispatch/SKILL.md`
  - 读取：上游 skill 传入的调度请求
  - 读取：项目目录下 `.codex/agents/*.md`
  - 输出：标准化的子代理调度结果
- 典型产出：
  - 标准化的子代理调度结果

## 15. 使用建议

- 如果你只是想“知道应该用哪个技能”，先看 `story`
- 如果你要“搭环境”，看 `story-setup`
- 如果你要“写长篇”，看 `story-long-write`
- 如果你要“写短篇”，看 `story-short-write`
- 如果你要“拆书”，看 `story-long-analyze` 或 `story-short-analyze`
- 如果你要“扫市场”，看 `story-long-scan` 或 `story-short-scan`
- 如果你要“做质量修正”，看 `story-deslop` 或 `story-review`
- 如果你要“导入旧稿”，看 `story-import`
- 如果你要“做封面”，看 `story-cover`
- 如果你要“浏览器复用登录态”，看 `browser-cdp`

## 16. 维护约定

- 本文档是索引，不替代各 skill 的 `SKILL.md`
- 若某个 skill 的 Phase、依赖文件或产出结构有变，必须同步更新本文档
- 若新增 skill，应在本文档补一节，并说明：
  - 作用
  - 触发方式
  - 主流程
  - 依赖
  - 产出
