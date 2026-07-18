# Stage 0：入口与抽样

本阶段只负责四件事：

1. 确认原文真的读完
2. 确认这本书最容易被拆坏的点
3. 确认 few-shot 只选 1-2 本
4. 落盘可验证的 `_sample_comparison.md`

## 必做清单

- 读取 `_source_manifest.json`
- 读取 `_source_reading_plan.md`
- 按 Chunk 读完原文直到 EOF
- 记录最后事件、最后关系状态、尾部锚点
- 判断当前文本更像：
  - `讲法型`
  - `桥段链型`
  - `混合型`
- 判断四层 grade：
  - `structure_grade`
  - `performance_grade`
  - `sentence_grade`
  - `terminal_consequence_grade`

## 输出口径

没跑检测时，一律写：

- `未测`
- `未知`
- `人工判断：...`

不要把人工判断伪装成脚本实测。

## 抽样规则

先读 `references/examples/INDEX.md`，再按失败类型选：

- 《幼薇》：防“题面翻转缺失 / 中段桥压没 / 细节库缩水”
- 《扫黄扫到了我老公》：防“中段只剩吵架 / 私域桥不实 / 证据链清算压平”
- 《归月学生》：防“长期剥夺链变背景 / 掉马和回门只剩标签”

硬规则：

- 样例上限 2 本
- 不把原文、正例、反例全塞进同一主上下文
- 每本必须实际读取 `README.md`、相关原文段和 `正反例对照.md`
- 只允许使用 `references/examples/`，禁止拿 bak、上一本文档、旧 profile 或其他拆书目录替代
- 只说明“本次拿样例防什么失败”不够，必须写出正例锚点、反例锚点和本书对应风险

## 固定产物

读完当前原文并完成选样后，先写 `_sample_comparison.md`：

```md
# Few-Shot 对照记录

## 样本一
- 样本名：
- 选择原因：
- 已读文件：
  - references/examples/.../README.md
  - references/examples/.../原文.txt
  - references/examples/.../正反例对照.md
- 正例锚点：
- 反例锚点：
- 本书对应风险：
- 将影响的正式文件：

## 主报告后复核
- 对照裁决：未滑入反例 / 需要回炉
- 证据：
- 实际回写文件：
```

`_sample_comparison.md` 是过程审计，不是分析内容。它完成后，第一个内容产物仍必须是 `事实与推断台账.md`。

## 通过条件

下面任一没做完，都不能进入主报告微批：

- 原文未读到最后一行
- 最后有效事件不清楚
- few-shot 还没做减载选择
- `_sample_comparison.md` 未落盘或只有样本名，没有具体文件和正反例锚点
- 还在拿整套样例全文当总提示词
- 使用了 bak、上一本文档、旧 profile 或其他拆书目录当样本
