# 短篇写作执行骨架

这份文件只回答 5 件事：

1. 写前最少要准备什么
2. `profile` 闭环怎么跑
3. 审计和回修按什么优先级走
4. 高风险任务为什么要额外挂第二闸门
5. 常用脚本入口和产物怎么看

---

## 一、最低输入

普通短篇最低需要：

- `写作资产/profile_source.md`
- `book.profile.json`

仿写 / 融合 / 高敏同桥最低还要补：

- `写作资产/样本分级与可学层.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/仿写约束_禁写清单.md`
- `写作资产/同桥段过检规则.md`
- `写作资产/高敏桥段识别.md` 里对应桥的 `现实后果隔层 / 尾声入口 / 同桥不同脸`

融合稿还要补：

- 多本 `book.profile.json`
- `project.profile.json`

缺失处理：

- 缺拆书资产：回 `story-short-analyze`
- 缺 `profile_source.md`：先补模板
- 缺 `book.profile.json`：先生成单书 profile
- 缺 `project.profile.json`：先合成融合包

---

## 二、默认闭环

固定顺序：

1. 读取拆书资产
2. 读取 `profile_source.md`
3. 读取 `book.profile.json / project.profile.json`
4. 判断 `讲法型 / 桥段链型 / 混合型`
5. 起盘
6. 细纲
7. 正文
8. 跑内部审计
9. 生成回修任务单
10. 回修
11. 重审
12. 高风险任务再过第二闸门

关键原则：

- 规则只用于约束，不替代正文生成
- 桥段链问题先回细纲，不先磨字句
- 审计层切块只决定先修哪块，不决定正文怎么排版
- 自检必须逐条引用正文句子，不准只写“已处理”“已优化”
- 高敏桥改写前先确认 3 件事：重大证据前隔着什么现实后果、尾声入口给谁、几位核心人物是不是不同脸

---

## 三、回修优先级

默认顺序：

1. 题面是否还成立
2. 主桥起手和顺序是否成立
3. 重大证据前隔开的到底是现实后果还是纯时间空档
4. 后果链是否过顺、过满、过成熟
5. 尾声入口有没有被次线抢走
6. 开头与高潮是否过闸
7. 人物口气、权限、动作、节拍是不是又写回同一张脸
8. `global_risk_shape` 是整篇、粗块还是局部热点
9. 人物口气、关系漏出、情绪落点是否在走
10. 最后才处理句壳和短段节奏

禁止：

- 只看全文平均分
- 只看轻审计命中数
- 只看句子不看块级完整推进风险
- 为了压味把现场改成概述和总结

---

## 四、高风险任务为什么要挂第二闸门

共通场景和完成态判断见：

- `../../story/references/high-risk-rewrite-governance.md`
- `../../story/references/short-high-risk/reference-index.md`

当前写作侧必须额外挂：

- `high-sensitivity-block-audit-rewrite-playbook.md`
- `../../story/references/high-risk-gates/reference-index.md`

第二闸门在写作侧的作用不是继续给建议，而是做硬裁决：

- 当前高风险段有没有被写成完整成品块
- 有没有高功能对白
- 有没有提前关系判断和主题句
- 有没有“一刀完成太多任务”
- 有没有把后果写成成熟清算说明
- 有没有只隔时间不隔现实后果
- 有没有把尾声入口错让给次线
- 有没有把几位核心人物写回同一张脸

命中硬失败项时，当前段直接作废，回到该段重写，不继续润句。

维护边界：

- 共享高敏判断正文，统一维护在共享索引
- 这份文件只维护写作闭环、脚本入口、回修优先级和停机口径

---

## 五、审计时至少并行看哪些层

默认至少并行看 7 组结果：

1. `light_audit`
2. `heavy_audit`
3. `bridge_audit`
4. `style_assets_audit`
5. `rulebook_audit`
6. `shape_audit`
7. `sample_grading_guard`

硬口径：

- `最高块风险分` 优先级高于 `整体风险分`
- `shape_audit` 决定先修整篇、粗块还是局部
- `bridge_audit` 决定是否要回细纲换链
- `sample_grading_guard` 决定这轮能不能学句法、只能学骨架，还是只能看反面规则
- `rulebook_audit` 里如果命中 `现实后果隔层 / 尾声入口 / 人物同脸`，优先级高于句面润色
- `model_rewrite_task.md` 和自检记录都必须引用正文原句作证，不接受空口保证

---

## 六、常用脚本入口

### 1. 生成单书 profile

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --source "拆文库/{书名}" \
  --name "{书名}" \
  --output "拆文库/{书名}/book.profile.json"
```

### 2. 生成融合 profile

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --merge-profile "拆文库/{书名1}/book.profile.json" \
  --merge-profile "拆文库/{书名2}/book.profile.json" \
  --name "{项目名}" \
  --output "profiles/{项目名}.project.profile.json"
```

### 3. 跑全量审计

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_full_ai_audit.py" \
  正文.md \
  --profile profiles/{项目名}.project.profile.json \
  --audit-rulebook "$CODEX_HOME/skills/story-short-write/references/governance/audit-rulebook.json"
```

### 4. 生成回修任务单

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/auto_revise_ai_flavor.py" \
  正文.md \
  --profile profiles/{项目名}.project.profile.json \
  --output-dir auto_revise_runs
```

### 5. 跑单轮闭环

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_revision_cycle.py" 当前短篇目录
```

### 6. 做题材首次校准

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/compare_with_external_block_audit.py" ...
```

这个只在题材校准时使用，不是每轮都跑。

---

## 七、如何看回炉产物

日常优先看：

- `full_audit.md`
- `revision_plan.md`
- `model_rewrite_task.md`
- `cycle_summary.json`
- `STATUS.txt`

至少确认：

- `global_risk_shape` 已写出
- `task_validation.bridge_alignment_ok = true`
- `task_validation.short_paragraph_priority_ok = true`
- 自检记录已经逐条引用正文句子
- 当前轮如果改的是高敏桥，已额外核对 `现实后果隔层 / 尾声入口 / 人物不同脸`

如果当前轮挂了第二闸门，还要确认：

- `rewrite_gate_receipt.json` 已回填并校验通过
- `failure_gate_receipt.json` 已回填并校验通过
- 汇总状态已经更新为 `gate_passed`

只填了回执但汇总还没更新，不算这轮闭环结束。

---

## 八、停机口径

通用停机口径见：

- `../../story/references/high-risk-rewrite-governance.md`

写作侧额外再加两条：

- 主桥承重件已对齐
- 前排高风险块已下降
- 高敏桥没有回弹成标准承载方式
- 自检记录不是空口保证，而是逐条拿正文举证
