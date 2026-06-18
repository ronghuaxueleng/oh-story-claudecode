# 质量检查这一步

> 这一页主要说第 5 阶段到底查什么、什么时候叫子代理、查完还要补哪些同步。

---

## 一、先看什么

质量检查最少看两个面：

1. 情绪落点
- 本章是否真的写到了细纲承诺的那股情绪
- 爽点、压迫、翻盘、危险是否真的落地
- 本章是不是还贴着 `设定/爽点怎么落.md` 里定好的这一段爽法在写
- 有没有把主爽法偷换成更保守、更慢、更虚的写法

2. 技术质量
- 事实一致性
- 角色 / 伏笔 / 时间线连续性
- 格式与禁用词
- AI 味与说明腔

通用清单先过一遍：
- `references/quality-checklist.md`
- `references/banned-words.md`
- `references/anti-ai-writing.md`
- `references/story-type-and-payoff-model.md`

---

## 二、先后顺序

一般按这个顺序走：

1. 先做章级自检
2. 再做连续性检查
3. 再做 AI 味 / 文字质量检查
4. 最后同步追踪

中间只要哪一步直接撞上 `F2-F5`，就别硬往后跳，更别急着说这一轮已经做完。

---

## 三、什么时候叫子代理

### 1. `consistency-checker`

若项目已部署 `.codex/agents/consistency-checker.md`，可调用：

```text
subagent: consistency-checker
prompt:
项目目录：{dir}
检查范围：{本次写作的章节}
检查类型：事实冲突+伏笔断线+角色属性不一致
```

如果用不了，就主线程按 `references/quality-checklist.md` 自己把一致性查掉。

### 2. `narrative-writer`

若项目已部署 `.codex/agents/narrative-writer.md`，可调用：

```text
subagent: narrative-writer
prompt:
项目目录：{dir}
任务描述：审查+去AI味
检查范围：{本次写作的章节}
```

如果用不了，就主线程自己查文字质量和 AI 味。

---

## 四、查完以后别漏同步

检查完以后，最少把下面几项再对一遍：

- `追踪/伏笔.md` 的过期 / 已收回状态是否更新
- `追踪/时间线.md` 的疑点是否更新
- 若本次涉及角色状态变化，`追踪/角色状态.md` 是否同步
- 若本次涉及情报兑现，`追踪/情报记录.md` 是否同步

这些还没同步完，这一批就先别写成完成。
