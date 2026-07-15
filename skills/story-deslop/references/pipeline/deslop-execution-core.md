# 去AI味执行骨架

这份文件只回答 6 件事：

1. 去味到底在处理什么
2. 自然文本和 AI 味文本怎么对照
3. 分级流程怎么走
4. Gate A-F 分别处理什么
5. 第二闸门怎么跑才算完成
6. 什么情况下应该停手或转回写作侧

---

## 一、去味处理的对象

AI 味的核心问题通常不是语法错误，而是：

- 太圆滑
- 太工整
- 太会解释
- 太像交付好的成品块

去味目标不是“修成更漂亮的文本”，而是：

- 保留剧情功能
- 降低模板感
- 降低统一后处理感
- 恢复动作、停顿、口气差和现场感

---

## 二、自然文本对照

自然文本更常见的是：

- 段落长短不齐
- 对话不总是完整表达
- 情绪落在动作和反应上
- 比喻更生活化
- 省略和跳跃更多
- 结尾更常停在动作或场景上

高风险 AI 味文本更常见的是：

- 段落整齐匀称
- 对话太完整、太清楚
- 情绪直接告诉
- 排比和套路句密度高
- 结尾总想总结和升华

---

## 三、分级流程

固定顺序：

1. `Phase 1`：扫描并标记问题
2. `Phase 2`：按客观指标分级
3. `Phase 3`：按 Gate A-F 清除
4. `Phase 4`：输出结果并判断是否收敛

分级只允许：

- `轻度`
- `中度`
- `重度`

默认策略：

- `轻度`：Gate A + B
- `中度`：Gate A + B + C + D
- `重度`：完整 6 Gate + 重点段回修

综合判定优先看客观指标，不允许主观上调，只允许带理由地下调 1 档。

---

## 四、Gate A-F 职责

### Gate A：禁用词替换

处理：

- 高频 AI 词
- 书面腔词
- 直接告诉式表达

原则：

- 用展示替代告诉
- 不只是换另一个形容词
- `.deslop-whitelist` 命中时跳过该次计数

### Gate B：句式去套路

处理：

- “不是A，而是B”
- “……，带着……”
- 声音描写模板
- 万能比喻
- 对话标签密度过高
- 文言腔判断词

目标：

- 把句壳从模板句拉回自然句

### Gate C：心理描写外化

处理：

- 直接情绪陈述
- 重复拆写同一瞬间
- 同义、近义、含义重复

目标：

- 用动作、反应、身体状态替代心理总结

### Gate D：节奏打碎

处理：

- 连续排比
- 段落过匀
- 长句扎堆
- 节拍过整齐

目标：

- 打散成品感

### Gate E：对话去腔调

处理：

- 对话过于完整
- 信息推进过高功能
- 每个人都像同一个人讲话

目标：

- 恢复口语感、打断、找补、答非所问和动作插话

### Gate F：结尾去升华

处理：

- 总结句
- 升华句
- 点题句
- “这一刻 / 他知道 / 她终于明白” 类收束

目标：

- 用动作、物件、场景收口

---

## 五、保护规则

保护优先级：

`剧情功能 / 伏笔 / 钩子 / 角色特征 / 关键信息` > `Gate A-F`

因此：

- 不得整段删除正文
- 不为压味删除承重信息
- 删除会伤到连贯性时，改成降 AI 重写
- 不确定的内容标 `[需复核]`，不强行处理

删除比例上限按等级控制：

- 轻度：`<=15%`
- 中度：`<=25%`
- 重度：`<=35%`

---

## 六、第二闸门

共通场景和跨 skill 边界见：

- `../../story/references/high-risk-rewrite-governance.md`

当前去味侧命中高风险时，不能只做 Gate A-F，还必须走：

1. `受限重写防错协议`
2. `失败即重写判定`

第二闸门只审当前高风险段，不审整篇。

命中硬失败项时：

- 当前段作废
- 直接重写
- 不继续润句

---

## 七、脚本与产物

标准入口：

```bash
python3 "$CODEX_HOME/skills/story-deslop/scripts/run_rewrite_gate_cycle.py" 待去味正文.md
```

要求 gate 必须通过时：

```bash
python3 "$CODEX_HOME/skills/story-deslop/scripts/run_rewrite_gate_cycle.py" \
  待去味正文.md \
  --require-gates-passed
```

默认产物包括：

- `audit/*.json / .md`
- `gate/*-重写预检.json / .md`
- `gate/*.rewrite_gate_task.md`
- `gate/*.failure_gate_task.md`
- `gate/*.rewrite_gate_receipt.json`
- `gate/*.failure_gate_receipt.json`
- `cycle_summary.json`
- `gate_validation.md`
- `STATUS.txt`

日常优先看：

- `gate_validation.md`
- `cycle_summary.json`
- `STATUS.txt`

---

## 八、第二闸门完成标准

共通完成态判断见：

- `../../story/references/high-risk-rewrite-governance.md`

当前去味侧以下 4 条必须同时满足，才算当前轮真正完成：

1. 两份 `receipt.json` 已回填
2. `validate_gate_receipts.py --require-executed --require-complete` 通过
3. `gate_stage = gate_passed`
4. `gate_overall_status = passed`

只生成了 `task.md` 但 `receipt.json` 仍是 `pending`，不算完成。

`precheck` 全清零但 `STATUS.txt` 还没到 `gate_passed`，也不算完成。

---

## 九、停机口径

通用停机口径见：

- `../../story/references/high-risk-rewrite-governance.md`

当前去味侧额外再加一条：

- 如果问题本质是结构、桥段、顺序，转回 `story-short-write` 或 `story-short-analyze`
