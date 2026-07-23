# 短篇写作执行骨架

这份文件只回答 12 件事：

1. 写作规则怎么证明读的是当前版本
2. 拆文资料怎么证明实际读过
3. 写前最少要准备什么
4. `profile` 闭环怎么跑
5. 审计和回修按什么优先级走
6. 高风险任务为什么要额外挂第二闸门
7. 常用脚本入口和产物怎么看
8. 自动预扫和人工语义复核怎么分工
9. skill 规则和拆书规则怎么逐项执行并留证
10. 主体拆书的开头功能顺序怎么做成阻断式契约
11. 细纲如何先通过原文表演机制验收，才允许写正文
12. 仿写审计如何先建立原文基线，避免把爆款原文形状误判成新稿失败

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
- 主体原文轻审计和全量审计结果，落盘到项目 `写作资产/原文对照审计/`
- `compare_source_baseline_audit.py` 生成的原文基线对照报告

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
13. 设定完成后，用 `validate_sequence_contract.py init-setting` 建立设定内部顺序契约
14. 当前模型人工回填设定 canonical 顺序、原句 `offset`、冲突取舍和总判断，并通过 `validate_sequence_contract.py validate-setting`
15. 用已通过的设定顺序回执运行 `validate_write_release_gate.py outline`，再写大纲
16. 大纲完成后，用 `validate_sequence_contract.py init` 建立完整设定—大纲—正文契约
17. 当前模型人工核对设定/大纲顺序、冲突和两层原句 `offset`，通过完整契约校验
18. 用主体 `可直接仿写_导语拆解表.md` 对大纲执行 `opening_contract_gate`
19. 对大纲执行 `outline_performance_contract`：逐节验证原文表演机制、信息延迟、人物偏手、交流变化链、冲突载体、禁写项和细纲原句证据
20. 通过 `validate_write_release_gate.py draft --sequence-receipt ... --outline-contract ...`，再写正文
21. 补正文节点证据并通过 `validate_sequence_contract.py validate --draft ...`
22. 对正文前 `20 / 60 / 80 / 120` 字再次执行 `opening_contract_gate`
23. 首轮按 skill canonical 规则和主体拆书资产做正文定向回修，并逐项留下正文证据
24. 通过 `validate_pre_window_revision_gate.py`
25. 导出人工模型分段任务，由当前模型完整读取回修后的正文，并结合完整顺序契约逐节点人工切窗
26. 跑正式全量审计并回填脚本产物
27. 若属于仿写 / 融合 / 同桥任务，先对主体原文跑同一套轻审计和全量审计，再运行 `compare_source_baseline_audit.py` 生成基线对照
28. 逐窗人工判断剩余问题；仿写任务必须把问题标成 `source_like / craft_tradeoff / draft_extra_ai_shell`
29. 只把 `draft_extra_ai_shell` 写进回修任务单；`source_like / craft_tradeoff` 可保留，但必须写明原文基线和情节功能
30. 回修；设定、大纲或正文 SHA 变化后，对应顺序契约、窗口前回修回执、人工分段回执、正式审计和原文基线对照全部失效
31. 回到第 23 步，重新做规则/资产定向回修，再重新切窗和重审
32. 无正文变化后，绑定最终写作产物；递归重绑规则台账中所有目标产物证据和 `source_contract_reviews`，再通过 `rule_execution_gate`
33. 重新校验正文 `opening_contract_gate`、细纲 `outline_performance_contract` 和完整顺序契约
34. 生成人工语义复核回执并人工复扫全文
35. 通过 `post_write_human_review_gate`
36. 高风险任务再过第二闸门

关键原则：

- 规则只用于约束，不替代正文生成
- 主体导语资产明确规定“为什么顺序不能乱”时，必须提升为独立硬闸，不能合并成宽泛的“开头抓人”后丢失窗口和先后关系
- 细纲表演验收不能由顺序契约、开头契约或规则台账替代；它专门检查细纲能否把原文的场内表演机制写成可执行的新场戏，未通过时禁止写正文
- 设定、细纲、正文之间的主桥顺序也必须提升为独立硬闸；规则执行台账只证明规则执行记录完整，不证明产物顺序一致
- profile、事实边界、样本分级、作者 DNA、桥段施工、高敏识别、同桥过检和禁写清单即使合并，也必须逐来源回填 `source_contract_reviews`
- 最终设定、大纲或正文 SHA 变化后，规则台账不能只更新 artifacts；所有 canonical 合并规则、成员来源、`text_evidence`、`structural_claim_reviews`、`source_contract_reviews.target_evidence` 和 `scope_reviews` 都必须递归重绑到当前产物真实原句
- 普通素材候选可以不选；主体治理资产及顺序、后果、外部秩序、公开场后果不能用“未调用、保留原稿”跳过
- 文件级关键契约也必须逐来源复核；规则级文件父节点由子规则自动派生，不能手填假完成
- 设定/大纲 canonical 同时覆盖多个目标时，每个目标都要有 `structural_claim_reviews` 原句证据，不能跨范围代证
- 读取回执不能代替执行台账；执行一项标记一项，不能最后统一补“已使用”
- 写作放行必须独立运行 `validate_write_release_gate.py`；任一前置门禁不是 `passed` 时禁止生成或修改当前阶段产物，不能先写后补
- 设定内部顺序必须在大纲写作前单独过闸；完整顺序契约不能事后替代设定阶段校验
- 正文完成判定必须同时包含规则台账、人工模型分段回执、正式长窗审计和写后人工语义复核；部分通过不得宣称完整流程完成
- 正文完成判定中的字数必须统一运行 `count_words.py`；统计规则为去掉 `#` 开头 Markdown 标题行后，计算所有非空白字符。回执、人工分段和审计里记录的字符数/字数不得使用估算或其他脚本口径
- 人工窗口不是首轮通用规则执行器。正文首稿完成后，必须先按 skill 规则和主体拆书资产定向回修，再导出人工窗口任务；窗口只负责定位剩余问题
- `validate_pre_window_revision_gate.py` 未通过时，禁止导出人工模型分段任务或运行带人工分段回执的正式全量审计
- 窗口人工判断必须记录每窗的病因、证据和处理决策；脚本风险标签不能直接写成“必须修改”
- 窗口人工判断必须填写 `procedural_stiffness_review`，逐窗输出 `流程日志感 / 证据清单感 / 三连状态回执 / 手续推进过顺 / 一句完成多任务 / 人物反应被流程替代 / 现场阻力不足 / 分镜或施工稿` 的原句、原因、优先级和改法，并汇总进 `full_audit.md` 与 `revision_plan.md`；没有汇总输出不算正式人工窗口审计闭环
- 窗口人工判断还必须逐节点确认主桥顺序、节点窗口归属和跨窗风险；窗口切分本身不是顺序契约，缺少该复核不得宣称窗口审计完成
- 台账不是正文修改清单；流程、设定、大纲、正文、审计、拆书候选和禁用规则必须分流
- 台账证据不是可复用模板；旧正文证据、旧 SHA、缺来源、残留无关来源或公共证据替代逐来源契约，均视为规则台账未闭环
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
- 仿写正文变好不是“比原文更干净”，而是原文的事件颗粒度、情绪拍序、信息延迟、场面短促感和控制权变化没有缩水，同时清掉新稿额外冒出的语句类 AI 壳
- 原文基线报告必须作为正式审计解释的一部分；原文自身存在的中风险、短句密度、高密对白和强钩子，不得未经人工裁决直接转成新稿修改单

---

## 三、回修优先级

默认顺序，不得把低位规则反向覆盖高位规则：

1. 成文真实感是否还成立：不能像规则施工稿、验收单、提示词执行结果。
2. 仿写任务的原文事件颗粒度和情绪拍序是否保持：不得为了降分削弱主体 BID、反刀拍、峰值拍和场末余痛。
3. 题面 / 题材承诺 / 主卖点是否还成立：追妻、婚恋清算、强情绪关系文不得被修成职业流程文。
4. 主桥起手和顺序是否成立。
5. 重大证据前隔开的到底是现实后果还是纯时间空档。
6. 后果链是否过顺、过满、过成熟。
7. 尾声入口有没有被次线抢走。
8. 开头与高潮是否过闸。
9. 冲突载体是否成立：每场到底在争夺什么现实权力、位置或后果。
10. 人物交流是否成立：一方施压后，另一方是否出现动作、站位、物件控制权、回答范围、身份或后果的可见变化。
11. 灵动感是否成立：现场毛边是否服务人物真实，而不是随机动作词。
12. 流程硬化 / 分镜施工稿是否被消化：白板、钥匙、确认框、回执等应进入人物反应和现场阻力，不能变成清单。
13. 人物口气、权限、动作、节拍是不是又写回同一张脸。
14. `global_risk_shape` 是整篇、粗块还是局部热点。
15. 人物口气、关系漏出、情绪落点是否在走。
16. 最后才处理句壳和短段节奏；仿写任务只清理相对原文新增的语句类 AI 壳，不清理原文有效形状。

### 回修粒度硬闸

每轮正文回修前，必须先输出并执行 `revision_scope_decision`。

可选粒度只能是：

- `global_structure`：整篇题材承诺、主桥顺序、结局归属或全局成文形状有问题。
- `coarse_block`：连续 1000 字以上的大块语言形状、流程硬化、证据清单感或场面功能同构有问题。
- `full_scene`：一整场戏的冲突载体、人物交流、动作链、物件控制权或追妻低位没有立住。
- `paragraph_cluster`：相邻数段存在同一病灶，但场戏骨架成立。
- `sentence_hotspot`：单句/少数句的直白心理、冒号模板、术语残留、重复词或标点问题。
- `format_only`：只涉及知乎/盐言小节格式、错别字、空行、文件路径等非正文叙事问题。

硬口径：

- 命中 `global_structure / coarse_block / full_scene` 时，必须按整篇重构、粗块回炉或整场重写处理；不允许用“补一个眼神、加一句动作、换几个词”冒充完成。
- 命中 `人物偏手 / 人物交流 / 冲突载体 / 流程硬化 / 分镜施工稿 / 开头成品感 / 追妻低位` 时，默认至少是 `full_scene`，除非能引用正文证明只剩单句残留。
- 连续两轮正式审计仍命中同一 P0/P1 时，必须自动升级回修粒度：`sentence_hotspot -> paragraph_cluster -> full_scene -> coarse_block`。
- `sentence_hotspot` 小改只允许用于重复词、冒号模板、单个术语、错别字、局部标点、单句解释过满；不得用于修补场戏功能、人物关系或题材承诺。
- 回修后人工复核必须说明：本轮是否按判定粒度执行；如果小改，为什么没有触发大段/整场回炉。

### 规则互斥保护

任何正文回修都必须先写本轮规则保护卡：

```json
{
  "primary_revision_rule": "本轮主修规则",
  "revision_scope_decision": {
    "scope": "global_structure | coarse_block | full_scene | paragraph_cluster | sentence_hotspot | format_only",
    "reason": "为什么是这个粒度",
    "rewrite_range": "要整篇、整块、整场、段群还是单句",
    "why_not_smaller_patch": "如果不是小改，说明为什么小补丁无效；如果是小改，说明为什么没有触发大改"
  },
  "protected_rules": [
    "premise_genre_promise_alignment",
    "core_selling_point_payoff",
    "conflict_carrier_review",
    "interaction_exchange_review",
    "rule_evidence_stiffness_and_liveliness",
    "full_text_storyboard_construction_list_review"
  ],
  "risk_of_rule_collision": "本轮可能把哪些旧修改修坏",
  "rollback_or_second_pass_plan": "若保护规则失败，回滚哪些句子或如何二次修复"
}
```

回修后必须逐项裁决：

- `primary_rule_result`：主修规则是否改善，必须引用正文原句。
- `protected_rule_results`：每条保护规则是否仍成立，必须引用正文原句或说明无影响。
- `collision_found`：是否出现“用 A 规则修完，又被 B 规则修坏”的情况。
- `resolution`：`keep / second_pass_fixed / rollback_required` 三选一。

硬口径：

- `procedural_stiffness_review` 只能负责消化流程硬化，不能直接删掉冲突载体、人物交流或追妻情绪。
- `interaction_exchange_review` 和 `conflict_carrier_review` 不能靠堆视线、手部动作、物件动作过关；若补完后像分镜清单，必须二次修复。
- `full_text_storyboard_construction_list_review` 是全篇保护闸，不只限开头；它不能否定情节内真实清单、报告、日志、合同、群公告，但必须要求说明其情节功能。
- 脚本预扫和固定词命中只能定位候选，不能覆盖当前模型的人工规则冲突裁决。

禁止：

- 只看全文平均分
- 只看轻审计命中数
- 只看句子不看块级完整推进风险
- 为了压味把现场改成概述和总结
- 为了过审计把人物改得更懂事、更会认错、更会总结
- 把“局部句子更顺”误判成“整块更像真人成文”
- 用一个规则的检测结果机械覆盖另一个更高优先级规则
- 为了去流程硬化删掉冲突载体、人物交流或追妻情绪
- 为了补交流/补冲突堆动作，导致全文变成分镜清单或规则施工稿

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

统一字数统计：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/count_words.py" "项目目录/正文.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/count_words.py" --json "项目目录/正文.md"
```

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

### 4. 生成并校验开头承重契约

大纲和正文各自生成回执，由当前模型逐项人工回填：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" init \
  --project "{项目名}" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md" \
  --artifact-kind draft \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" validate \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md"
```

只要任务说明先于关系钩子、主体三拍功能顺序被打乱，或题面未在前 `80 / 120` 字兑现，就返回 blocked。详见 [opening-contract-gate.md](opening-contract-gate.md)。

### 5. 生成并校验写后人工语义复核回执

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

窗口前先初始化并回填规则/资产定向回修回执：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_pre_window_revision_gate.py" init \
  --project "{项目名}" \
  --text "正文.md" \
  --receipt "写作资产/窗口前规则资产回修回执.json"
```

回填后必须通过：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_pre_window_revision_gate.py" validate \
  --receipt "写作资产/窗口前规则资产回修回执.json" \
  --text "正文.md"
```

通过后再导出人工模型分段任务：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_full_ai_audit.py" \
  正文.md \
  --pre-window-revision-receipt 写作资产/窗口前规则资产回修回执.json \
  --sequence-receipt 写作资产/顺序契约回执.json \
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
  --pre-window-revision-receipt 写作资产/窗口前规则资产回修回执.json \
  --sequence-receipt 写作资产/顺序契约回执.json \
  --model-segmentation-receipt 写作资产/人工模型分段回执.json
```

正式人工窗口除了校验边界、SHA 和字符数，还必须逐个回填顺序契约节点的窗口归属、正文证据、`order_status` 和人工判断，并逐窗完成 `procedural_stiffness_review`。任何 `out_of_order / missing / ambiguous` 都阻断；任何疑似 AI 窗口缺少具体病灶或 `none_found` 反证，也阻断。正文修改后必须重新执行窗口前规则/资产定向回修，再重新导出并人工执行，不能沿用旧边界。未传人工分段回执或顺序契约时只运行算法预扫，不得把 `boundary_source=algorithmic` 写成模型已复核。

### 8. 生成回修任务单

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/auto_revise_ai_flavor.py" \
  正文.md \
  --profile profiles/{项目名}.project.profile.json \
  --output-dir auto_revise_runs
```

已识别的高风险桥段如果没有进入前排桥段任务，任务单生成直接阻断。已绑定 profile 时，`bridge_rules / scene_assets / style_assets / story_guardrails` 缺失也直接阻断并要求重建拆书/profile。短段偏多、局部频率和统计波动仍只作诊断预警，不得据此机械改文。

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
