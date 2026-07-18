# staged-execution-index

这份索引只做一件事：让 `story-short-analyze` 按阶段加载规则，同时在阶段内大批量连续落盘。

## 读取规则

正式拆书时，固定按下面顺序读取：

1. `SKILL.md`
2. 本文件
3. 当前阶段对应文档
4. 当前阶段确实需要的模板 / 样例
5. `session-manual-execution-protocol.md`

不要一次性加载：

- 全部阶段文档
- 全部 few-shot 样例
- 全部失败类型说明
- 整份 `output-templates.md`；先检索目标文件标题，只读取命中区段

## 阶段映射

### Stage 0：入口与抽样

读取：

- `stage-00-intake-and-sampling.md`
- `references/examples/INDEX.md`
- `session-manual-execution-protocol.md`

必须补 1-2 套样例，并先落 `_sample_comparison.md`；没有对照记录不得进入 Stage 1。

### Stage 1：事实底座与第一波并发

读取：

- `stage-01-main-report-batch.md`
- `output-templates.md`

主线程先处理：

- `事实与推断台账.md`
- `_analysis_brief.md`

随后按 `_parallel_plan.json.foundation_lanes` 并发处理：

- `拆文报告.md`
- `情节节点.md`
- `写作手法.md`
- `本书动态信号字典.json`
- `原文资产候选池.md`

汇合后更新样本复核与 `_meta.json`，再运行 foundation 预检。

### Stage 2：字典、候选池、16 张表

读取：

- `stage-02-ledger-and-tables-batch.md`
- `dynamic-signal-dictionary.md`
- `source-asset-coverage-ledger.md`

foundation 预检通过后，Stage 2 与 Stage 3 合并成 3 次粗粒度并发派发。12000 字以内使用“主线程 + 3 个复用子 agent”：`agent-core` 承担结构动作表+高敏资产，`agent-craft` 承担对白关系表+常规资产，`agent-discovery` 从发现索引续到细节库。第二波不重读第一波资源，只追加 `delta_reads`；禁止每条 lane 重新 spawn。

### Stage 3：细节库与写作资产

读取：

- `stage-03-detail-assets-batch.md`

### Stage 4：profile 与收口

读取：

- `stage-04-profile-and-finalize-batch.md`
- `output-contract.md`
- `quality-checklist.md`

## 关键原则

- 主 skill 只管总控，不再承载全部细则
- 当前批次只看当前阶段文档，减少上下文焦虑
- 第一波并发主报告、节点/手法、字典/候选池；第二波并发 16 表、细节库和两类写作资产
- 并发只用于 `_parallel_plan.json` 中写入路径互不重叠的 lane；事实台账、分析契约与最终收口始终串行
- 子 agent 只用于正式内容产出 lane；读取、grep、validator、厚度统计、BID 贯通等确定性步骤优先回主线程工具流
- lane 是文件所有权单元，不是 agent 会话单元；同一 executor 跨两波复用，不得按 lane 重启
- 第一波必须先过 foundation 预检，避免错误扩散到 30 多个下游文件
- 同一波 lane 固定共享上下文顺序，不为不同 worker 重排稳定前缀
- 原文和样本只完整读取一次；后续通过台账、节点、候选池和精确原文切片复核
- 批量输出失败时只二分责任批次，二分仍截断才回退双文件模式
- few-shot 只在能明确防当前失败时加载
- few-shot 必须留下具体读取文件、正反例锚点和主报告后复核证据
- finalize 只验证，不补写任何 Markdown
- 快速模式不得以压缩单文件内容换速度；主报告和现有厚度门槛仍优先
- `intake / foundation / assets / finalize` 必须写入 `_timing.json`，提速结论以实测耗时为准
