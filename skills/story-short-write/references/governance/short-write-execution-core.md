# 短篇写作执行骨架

这份文件只回答 9 件事：

1. 写作规则怎么证明读的是当前版本
2. 拆文资料怎么证明实际读过
3. 写前最少要准备什么
4. `profile` 闭环怎么跑
5. 审计和回修按什么优先级走
6. 高风险任务为什么要额外挂第二闸门
7. 常用脚本入口和产物怎么看
8. 自动预扫和人工语义复核怎么分工
9. skill 规则和拆书规则怎么逐项执行并留证

---

## 一、最低输入

进入最低输入判断前，必须先通过：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" validate \
  --receipt "项目目录/写作资产/写作规则读取回执.json" \
  --output "项目目录/设定.md" \
  --output "项目目录/小节大纲.md" \
  --output "项目目录/正文.md"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" validate \
  --receipt "项目目录/写作资产/拆文读取回执.json" \
  --output "项目目录/设定.md" \
  --output "项目目录/小节大纲.md" \
  --output "项目目录/正文.md"
```

`writing_rule_gate` 必须覆盖当前工作区的格式规则、`anti-ai-writing.md` 和 `narrator-voice.md`。任一规则文件变化后旧回执失效，禁止用旧对话上下文或旧摘要代替。

回执必须覆盖每本选中的主体 / 辅助拆文的完整资产。只读 `profile_source.md`、profile、设定或大纲不算通过。缺资产直接回 `story-short-analyze` 全量重拆，不做兼容回退。

详细口径见：

- [writing-rule-reading-gate.md](writing-rule-reading-gate.md)
- [source-reading-gate.md](source-reading-gate.md)

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

1. 生成规则读取清单并逐文件回填
2. 通过 `writing_rule_gate`
3. 生成拆文逐文件读取清单
4. 逐文件读取并回填读取回执
5. 通过 `source_read_gate`
6. 初始化 `规则执行台账.json`
7. 导出模型复核批次，由当前写作模型逐族阅读 `cases` 并归纳 `canonical_rule_text`
8. 模型确认规则角色、修复目标、`script / human / hybrid`、适用性、目标阶段和目标场景，并先合并近义规则
9. 读取 `profile_source.md`
10. 读取 `book.profile.json / project.profile.json`
11. 判断 `讲法型 / 桥段链型 / 混合型`
12. 起盘和细纲，同时逐项标记规则
13. 正文，同时逐项标记规则
14. 跑内部审计并回填脚本产物
15. 生成回修任务单
16. 回修
17. 重审
18. 绑定最终写作产物并通过 `rule_execution_gate`
19. 生成人工语义复核回执并人工复扫全文
20. 通过 `post_write_human_review_gate`
21. 高风险任务再过第二闸门

关键原则：

- 规则只用于约束，不替代正文生成
- 读取回执不能代替执行台账；执行一项标记一项，不能最后统一补“已使用”
- 台账不是正文修改清单；流程、设定、大纲、正文、审计、拆书候选和禁用规则必须分流
- 完全重复规则族自动合并，近义规则族由模型归一；canonical 执行一次并保留全部来源和族内变体
- 脚本只执行可计算规则，人物、叙述、认知和生活性规则必须人工逐项裁决
- 只有失败的适用正文约束才能进入正文修改单，拆书候选未采用不算漏用
- 桥段链问题先回细纲，不先磨字句
- 审计层切块只决定先修哪块，不决定正文怎么排版
- 自检必须逐条引用正文句子，不准只写“已处理”“已优化”
- 自动审计只负责显式模式和量化风险，不能替代作者代判、叙述站位、多余解释和人物动机的人工判断
- 局部或专项回炉必须绑定母稿，逐条复核所有新增/改写句，同时复扫母稿旧句
- 高敏桥改写前先确认 3 件事：重大证据前隔着什么现实后果、尾声入口给谁、几位核心人物是不是不同脸
- 一轮回修如果把正文修得更像“安全成熟块 / 会过闸稿”，即使命中下降，也不算通过
- 正文变好不是“解释更全、主题更明、人物更会说人话”，而是现场更成立、后果更落地、人物更分脸

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
- 为了过审计把人物改得更懂事、更会认错、更会总结
- 把“局部句子更顺”误判成“整块更像真人成文”

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
- 自动结果中的“作者站位过高 0”只代表脚本没有命中显式模式，不代表人工语义复核通过

人工语义层固定再查：

1. 作者是否替人物归纳动机、认知或胜负
2. 第一人称评价是现场态度还是借人物点题
3. 动作已经表达后是否又补解释
4. 判断是否有当前场景可观察依据
5. 对白是否句句正答、过度高效
6. 是否只审本轮 diff，漏掉母稿旧问题

---

## 六、常用脚本入口

### 1. 生成并校验写作规则读取回执

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" init \
  --project "{项目名}" \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" validate \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"
```

### 2. 生成并校验拆文读取回执

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" init \
  --project "{项目名}" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --receipt "{项目目录}/写作资产/拆文读取回执.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" validate \
  --receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"
```

### 3. 初始化、绑定并校验规则执行台账

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" init \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --ledger "{项目目录}/写作资产/规则执行台账.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" bind-artifacts \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --artifact "设定={项目目录}/设定.md" \
  --artifact "大纲={项目目录}/小节大纲.md" \
  --artifact "正文={项目目录}/正文.md"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" validate \
  --ledger "{项目目录}/写作资产/规则执行台账.json"
```

逐项字段、规则展开范围和脚本/人工分工见 [rule-execution-ledger.md](rule-execution-ledger.md)。

### 4. 生成并校验写后人工语义复核回执

全新正文：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_post_write_human_review_gate.py" init \
  --project "{项目名}" \
  --text "{项目目录}/正文.md" \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json"
```

局部或专项回炉：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_post_write_human_review_gate.py" init \
  --project "{项目名}" \
  --text "{项目目录}/正文.md" \
  --base-text "{母稿目录}/正文.md" \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json"
```

人工回填后：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_post_write_human_review_gate.py" validate \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json" \
  --text "{项目目录}/正文.md"
```

### 5. 生成单书 profile

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --source "拆文库/{书名}" \
  --name "{书名}" \
  --output "拆文库/{书名}/book.profile.json"
```

### 6. 生成融合 profile

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --merge-profile "拆文库/{书名1}/book.profile.json" \
  --merge-profile "拆文库/{书名2}/book.profile.json" \
  --name "{项目名}" \
  --output "profiles/{项目名}.project.profile.json"
```

硬闸：任一单书 profile 缺少 `precheck_overrides` 时停止融合，重新全量拆书后再生成单书和融合 profile。

### 7. 跑全量审计

先导出人工模型分段任务：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_full_ai_audit.py" \
  正文.md \
  --export-model-segmentation-task 写作资产/人工模型分段回执.json
```

当前执行 skill 的模型必须完整读取 `正文.md`，从回执
`paragraph_anchors.start_char` 中选择 3-6 个边界，并用
`apply_patch` 回填：

- `status=completed`
- `boundaries`
- `boundary_evidence`
- `manual_judgment`

禁止调用 Anthropic/OpenAI 等外部 API，也禁止调用 Claude CLI。完成后再跑正式审计：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_full_ai_audit.py" \
  正文.md \
  --profile profiles/{项目名}.project.profile.json \
  --audit-rulebook "$CODEX_HOME/skills/story-short-write/references/governance/audit-rulebook.json" \
  --model-segmentation-receipt 写作资产/人工模型分段回执.json
```

回执必须绑定当前正文路径、SHA 和字符数，边界必须严格对齐段落起点。正文修改后必须重新导出并人工执行，不能沿用旧边界。未传回执时只运行算法滑窗预扫，不得把 `boundary_source=algorithmic` 写成模型已复核。

### 8. 生成回修任务单

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/auto_revise_ai_flavor.py" \
  正文.md \
  --profile profiles/{项目名}.project.profile.json \
  --output-dir auto_revise_runs
```

### 9. 跑单轮闭环

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_revision_cycle.py" 当前短篇目录
```

### 10. 做题材首次校准

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
- `规则执行台账.json` 已逐项完成并绑定最终设定、大纲、正文 SHA
- `写后人工语义复核回执.json` 已绑定最终正文 SHA 并通过校验
- 局部或专项回炉已逐条复核全部新增/改写句，且完成全文旧问题复扫
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
- 规则执行台账已通过，最终正文修改没有让规则证据或 SHA 过期
- 人工语义复核回执已经通过，正文最后一次修改没有让回执过期

---

## 九、自动与人工的边界

自动脚本负责：

- 格式、段长、频率、固定词句、显式模式、SHA 和回执完整性
- 生成风险块、热点、任务单和改写行清单

人工负责：

- 作者是否替人物想明白
- 叙述者是否在现场插嘴，还是作者借人物总结
- 是否解释了读者已经看懂的内容
- 评价是否有当前场景依据
- 对白和配角是否只服务主线

详细字段和失败条件见 [post-write-human-review-gate.md](post-write-human-review-gate.md)。
