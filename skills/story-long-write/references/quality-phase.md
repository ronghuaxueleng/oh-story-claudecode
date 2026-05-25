# 质量检查阶段

> 本文件负责 Phase 5 的执行口径：检查什么、何时调用子代理、检查后同步什么。

---

## 一、检查目标

质量检查至少覆盖两个维度：

1. 情绪交付
- 本章是否交付了细纲承诺的目标情绪
- 爽点、压迫、翻盘、危险是否真的落地
- 本章是否仍然符合 `设定/爽点模型说明书.md` 约定的当前阶段爽法
- 有没有把主爽法偷换成更保守、更慢、更虚的写法

2. 技术质量
- 事实一致性
- 角色 / 伏笔 / 时间线连续性
- 格式与禁用词
- AI 味与说明腔

通用清单统一读取：
- `references/quality-checklist.md`
- `references/banned-words.md`
- `references/anti-ai-writing.md`
- `references/story-type-and-payoff-model.md`

---

## 二、执行顺序

建议顺序：

1. 先做章级自检
2. 再做连续性检查
3. 再做 AI 味 / 文字质量检查
4. 最后同步追踪

若任一步直接命中 `F2-F5`，不得跳后续步骤硬判完成。

---

## 三、子代理调用

### 1. `consistency-checker`

若项目已部署 `.codex/agents/consistency-checker.md`，可调用：

```text
subagent: consistency-checker
prompt:
项目目录：{dir}
检查范围：{本次写作的章节}
检查类型：事实冲突+伏笔断线+角色属性不一致
```

如不可用，由主线程按 `references/quality-checklist.md` 执行一致性检查。

### 2. `narrative-writer`

若项目已部署 `.codex/agents/narrative-writer.md`，可调用：

```text
subagent: narrative-writer
prompt:
项目目录：{dir}
任务描述：审查+去AI味
检查范围：{本次写作的章节}
```

如不可用，由主线程直接执行文字质量与 AI 味审查。

---

## 四、检查后同步

检查结束后，至少确认：

- `追踪/伏笔.md` 的过期 / 已回收状态是否更新
- `追踪/时间线.md` 的疑点是否更新
- 若本次涉及角色状态变化，`追踪/角色状态.md` 是否同步
- 若本次涉及情报兑现，`追踪/情报台账.md` 是否同步

未同步完成，不得把本批次标记为完成。
