# staged-execution-index

这份索引只做一件事：把 `story-short-analyze` 从“主 skill 一次吞完”改成“按阶段加载”。

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

## 阶段映射

### Stage 0：入口与抽样

读取：

- `stage-00-intake-and-sampling.md`
- `references/examples/INDEX.md`
- `session-manual-execution-protocol.md`

必须补 1-2 套样例，并先落 `_sample_comparison.md`；没有对照记录不得进入 Stage 1。

### Stage 1：主报告微批

读取：

- `stage-01-main-report-batch.md`
- `output-templates.md`

只处理：

- `事实与推断台账.md`
- `拆文报告.md`
- `情节节点.md`
- `写作手法.md + _meta.json`

### Stage 2：字典、候选池、16 张表

读取：

- `stage-02-ledger-and-tables-batch.md`
- `dynamic-signal-dictionary.md`
- `source-asset-coverage-ledger.md`

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
- 当前微批只看当前阶段文档，减少上下文焦虑
- few-shot 只在能明确防当前失败时加载
- few-shot 必须留下具体读取文件、正反例锚点和主报告后复核证据
- finalize 只验证，不补写任何 Markdown
- 同一轮里不要同时追求“全文件铺满”和“主报告加厚”；优先主报告
