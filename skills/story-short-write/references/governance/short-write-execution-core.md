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

skill 或拆书来源发生变化后，先执行 `migration-report` 再执行 `sync-sources`。迁移报告只读分类：未变化且 SHA 一致的条目可保留；源文本变化的条目必须人工重绑 canonical、来源契约和目标证据；缺路径、旧机器路径、旧 SHA 仍为 passed 或 canonical 关系断裂的条目属于阻断项。不得通过批量替换路径、编号或状态恢复通过态。

进入最低输入判断前，必须先通过：

```bash
python3 "$SKILL_ROOT/scripts/validate_writing_rule_gate.py" validate \
  --receipt "项目目录/写作资产/写作规则读取回执.json" \
  --stage draft \
  --output "项目目录/正文.md"

python3 "$SKILL_ROOT/scripts/validate_source_read_gate.py" validate \
  --receipt "项目目录/写作资产/拆文读取回执.json" \
  --output "项目目录/设定.md" \
  --output "项目目录/小节大纲.md" \
  --output "项目目录/正文.md"
```

`writing_rule_gate` 必须覆盖当前工作区的格式规则、`anti-ai-writing.md` 和 `narrator-voice.md`。任一规则文件变化后旧回执失效，禁止用旧对话上下文或旧摘要代替。校验时只把当前阶段目标作为 `--output`；后续阶段重读可以晚于已验收的上游产物，但绝不能晚于本阶段目标。

回执必须覆盖每本选中的主体 / 辅助拆文的完整资产。只读 `profile_source.md`、profile、设定或大纲不算通过。缺资产直接回 `story-short-analyze` 全量重拆，不做兼容回退。

详细口径见：

- [writing-rule-reading-gate.md](writing-rule-reading-gate.md)
- [source-reading-gate.md](source-reading-gate.md)

## 执行介质纪律

- 正式流程里的回执、合同、台账和审计文件，优先由 skill 官方脚本创建骨架、绑定 SHA、执行合并和校验。
- 当前模型补写人工语义字段时，优先直接 `apply_patch` 修改已初始化文件；这类修改应局限在明确需要的人类判断字段，不要整份重写。
- 临时 Python、shell 循环或 here-doc 只能用于只读诊断、候选定位、统计、或把当前模型已逐字段确认的非语义结果做确定性序列化；不得把它们当成正式回执的默认生成器。
- 禁止用临时 Python 批量生成或覆写 `manual_judgment / comparison / target_evidence / source_contract_reviews / parity_status / keep-revise` 等需要当前模型逐项裁决的字段。
- 若同类文件反复需要大批量结构化回填，应补官方脚本或侧车合并入口，而不是在流程中持续追加一次性 here-doc Python。

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
19. 对大纲执行 `outline_performance_contract`：主体全部 BID 内逐句提取全部有效情节拍和实际情绪变化拍，逐拍绑定细纲原句并按原顺序一一映射；少拍、并拍、压缩、实际作用或重复次数不一致、任一拍降烈度时先重写细纲
20. 仿写 / 融合任务先初始化文字颗粒度 v2.4 合同，完成连续片段逐句语义标注、逐特征原句证据、成文活性资产和人物性格颗粒；为核心人物建立不可互换母版，再执行 `bind-outline` 并逐节完成连续句链、句间关系正反例、对白三联包、活性计划和人物计划，通过 `validate-prewrite`，由第一本主体原文独占正文声线
21. 绑定主体拆文的 `全文情绪颗粒总账.json` 后初始化情绪颗粒度合同，把总账全部实际情绪拍按原序逐节唯一分配并绑定细纲和独占证据；各节并集必须与总账全集同序相等。同时从细纲表演回执领取全部目标情节拍并逐节唯一归属，通过 `validate-prewrite`
22. 通过 `validate_write_release_gate.py draft --writing-receipt "项目目录/写作资产/写作规则读取回执.json" --source-receipt "项目目录/写作资产/拆文读取回执.json" --ledger "项目目录/写作资产/规则执行台账.json" --sequence-receipt "项目目录/写作资产/顺序契约回执.json" --opening-contract "项目目录/写作资产/开头承重契约回执_大纲.json" --outline-contract "项目目录/写作资产/细纲表演验收回执.json" --prose-contract "项目目录/写作资产/全文文字颗粒度契约回执.json" --emotional-contract "项目目录/写作资产/全文情绪颗粒度契约回执.json" --primary-source-original "拆文库/主体书/原文/主体书.txt" --source-emotion-ledger "拆文库/主体书/写作资产/全文情绪颗粒总账.json" --profile "profiles/项目名.project.profile.json"`；随后创建逐节字数预算并初始化 `逐节正文进度.json`，正文此时必须不存在或为空。该脚本三个阶段均不接收 `--output`。
23. 为第 1 节写完整场面计划并运行 `start-section`，再固定按“只读本节两类写前合同和人物计划 -> 在独立暂存稿一次写完并完整通读本节 -> 初始化确定性延后回执 -> 预检当前暂存稿、写前合同和场面领取 SHA/ID -> `commit-section` 原子写入正文并输出 `section_passed` -> 才能 `start-section` 下一节”推进。默认不再逐节重复填写人工侧车；发现未兑现、错脸、摘要化或偏离时先重写正文，必要时显式退回差量/全量侧车。当前节未通过时禁止创建未来标题，已通过旧节禁止修改；首稿不执行去 AI 味
24. 全部小节逐节通过后运行 `finalize`；只有输出 `final_ready` 才能绑定最终 SHA。随后必须基于最终正文一次性完整填写文字颗粒度与情绪颗粒度全文终审，并分别通过 `validate-draft`；逐节延后回执不能替代这两道最终人工合同。情节终审必须读取每个 P 拍的来源七项语义快照与目标七项语义，分别核对动作、控制权、信息变化和现实后果；只见 P 编号和一条正文引句不得判过
25. 只再运行统一字数统计；知乎 / 盐言稿另运行平台格式校验
26. 立即向用户交付初稿并停靠，明确报告正文路径、字数、格式和“尚未执行深审、去味与回炉”；禁止自动运行后续步骤
27. 只有用户明确回复“继续深审”“继续完整流程”或同义指令后，才补正文节点证据并通过 `validate_sequence_contract.py validate --receipt "项目目录/写作资产/顺序契约回执.json" --setting "项目目录/设定.md" --outline "项目目录/小节大纲.md" --draft "项目目录/正文.md"`
28. 对正文前 `20 / 60 / 80 / 120` 字再次执行 `opening_contract_gate`
29. 首轮按 skill canonical 规则和主体拆书资产做正文定向回修，并逐项留下正文证据
30. 规则资产复核完成后直接跑正式全量审计并回填脚本产物；不再强制执行 `validate_pre_window_revision_gate.py` 或人工模型分段
33. 若属于仿写 / 融合 / 同桥任务，先对主体原文跑同一套轻审计和全量审计，再运行 `compare_source_baseline_audit.py` 生成基线对照
34. 全文人工判断剩余问题；仿写任务必须把问题标成 `source_like / craft_tradeoff / draft_extra_ai_shell`

### 推荐合并执行批次

上面的默认闭环是治理顺序，不等于必须把每一步拆成单独回合。默认推荐按以下 4 个批次连续执行；批次内可以顺手完成多个相邻门禁，但不得跨批次偷跑下游产物：

1. `读取批次`
   - 初始化并回填 `写作规则读取回执`
   - 校验 `writing_rule_gate`
   - 初始化并回填 `拆文读取回执`
   - 校验 `source_read_gate`
   - 如两份回执时序和字段都通过，再进入下一批
2. `纲前放行批次`
   - 初始化 `规则执行台账`
   - 导出模型分类批次并完成 canonical 归并/分类
   - 读取 `profile_source.md` 与 `book.profile.json / project.profile.json`
   - 写设定并通过 `设定顺序契约`
   - 写大纲并通过 `完整顺序契约`
   - 通过 `开头承重契约`
   - 通过 `细纲表演验收`
   - 若卡在 `细纲表演验收`，推荐先在同一批次内按 `global_review -> 源情绪账本 bid_ids 边界 -> 桥级非逐拍裁决 -> 桥级逐拍/逐情绪 -> 逐场语义资产 -> 节级场面/scene_units -> 逐拍语义映射 -> SF` 的顺序修，不要直接跳去文字合同或情绪合同
   - 桥级修复默认走一套连续官方入口：`manage_outline_bridge_review.py sync-source-emotions -> export-template/apply-template -> export-beat-template/apply-beat-template -> manage_outline_section_review.py export-template/apply-template -> rebind-outline -> validate_outline_performance_contract.py validate -> seal-review`
   - 如这些闸门都过，再进入正文前合同批次
3. `正文前合同批次`
   - 初始化并绑定 `全文文字颗粒度合同`
   - 初始化并绑定 `全文情绪颗粒度合同`
   - 两份合同都通过各自 `validate-prewrite`
   - 如两份合同都过，再进入正文开写前最终放行批次
4. `正文开写前最终放行批次`
   - 运行 `validate_outline_performance_contract.py validate`
   - 运行 `batch_draft_prewrite.py validate`
   - 运行 `validate_write_release_gate.py draft`
   - 或直接运行 `batch_prewrite_release.py validate`
   - 只有这一批全部通过，才创建逐节正文状态机并开始正式正文

硬口径：

- 可合并的是“连续执行批次”，不是把多个治理对象合并成一张回执。
- `细纲表演验收回执.json` 是节级场面真源；`逐节计划`、写作包和正文状态只保存 ID、领取序列与 SHA，正文前入口按引用回解，不再复制整块 `scene_units`。侧车只保存人工可编辑字段，应用时局部合并。
- 同一批次内可以顺手连续修桥级与节级阻断，但前提仍是先修来源账本边界，再修桥级，再修节级场面与 `scene_units`，再修逐拍语义映射与 SF；不要让下游合同替上游桥级试错。
- `读取门禁`、`顺序契约`、`开头契约`、`细纲表演验收`、`文字颗粒度合同`、`情绪颗粒度合同`、`规则执行台账` 仍是独立硬闸，不能因为批处理而删字段、跳校验或用一份总说明替代。
- 若某批次中途有一项未 `passed`，应停在当前批次内修正，不得先写下游产物再回补上游。
- 若当前批次卡在 `细纲表演验收`，先把阻断折成 `bridge_emotion_boundary -> bridge_mapping_missing -> section_scene_units_missing` 三类施工单，再按顺序处理；不要把桥级边界、桥级逐拍、节级空壳和下游合同噪音混成一张无序待办。
- 若细纲在修桥过程中发生变化，先运行 `manage_outline_bridge_review.py rebind-outline` 重绑 `outline.sha256` 并把顶层验收态重置为 `pending`；全部字段补齐且真实校验通过后，再运行 `seal-review` 落盘 `reviewed_by_current_model=true / gate_status=passed`。不要把这两个顶层状态继续当作手工遗留项。
35. 只把 `draft_extra_ai_shell` 写进回修任务单；`source_like / craft_tradeoff` 可保留，但必须写明原文基线和情节功能
36. 回修；设定、大纲或正文 SHA 变化后，对应顺序契约、正式审计和原文基线对照全部失效
37. 回到第 29 步，重新做规则/资产复核和正式重审
38. 无正文变化后，绑定最终写作产物；递归重绑规则台账中所有目标产物证据和 `source_contract_reviews`，再通过 `rule_execution_gate`
39. 重新校验正文 `opening_contract_gate`、细纲 `outline_performance_contract` 和完整顺序契约
40. 生成人工语义复核回执并人工复扫全文
41. 通过 `post_write_human_review_gate`
42. 高风险任务再过第二闸门

关键原则：

- 规则只用于约束，不替代正文生成
- 主体导语资产明确规定“为什么顺序不能乱”时，必须提升为独立硬闸，不能合并成宽泛的“开头抓人”后丢失窗口和先后关系
- 细纲表演验收不能由顺序契约、开头契约或规则台账替代；它专门检查主体原文每个 BID 内全部情节拍与情绪拍是否逐拍迁移。最低拍数不是抽样配额，原文实际多少拍就必须迁移多少拍；未通过时禁止写正文
- 用户要求“借颗粒度、自造情节”时，细纲表演验收使用 `source_mode: granularity_only`：不强迫主体 BID 全集迁移，但必须用 `granularity_transfer_contract` 覆盖全部目标小节，并逐场证明事件拍密度、信息延迟、控制权变化与原文同级，同时列明拒绝复制的表层元素
- 设定、细纲、正文之间的主桥顺序也必须提升为独立硬闸；规则执行台账只证明规则执行记录完整，不证明产物顺序一致
- profile、事实边界、样本分级、作者 DNA、桥段施工、高敏识别、同桥过检和禁写清单即使合并，也必须逐来源回填 `source_contract_reviews`
- 最终设定、大纲或正文 SHA 变化后，规则台账不能只更新 artifacts；所有 canonical 合并规则、成员来源、`text_evidence`、`structural_claim_reviews`、`source_contract_reviews.target_evidence` 和 `scope_reviews` 都必须递归重绑到当前产物真实原句
- 普通素材候选可以不选；主体治理资产及顺序、后果、外部秩序、公开场后果不能用“未调用、保留原稿”跳过
- 文件级关键契约也必须逐来源复核；规则级文件父节点由子规则自动派生，不能手填假完成
- 设定/大纲 canonical 同时覆盖多个目标时，每个目标都要有 `structural_claim_reviews` 原句证据，不能跨范围代证
- 读取回执不能代替执行台账；执行一项标记一项，不能最后统一补“已使用”
- 写作放行必须独立运行 `validate_write_release_gate.py`；任一前置门禁不是 `passed` 时禁止生成或修改当前阶段产物，不能先写后补
- 设定内部顺序必须在大纲写作前单独过闸；完整顺序契约不能事后替代设定阶段校验
- 正文初稿落盘并通过字数/平台格式基础检查后必须停靠；此时只能宣称“初稿完成”，不能宣称“完整流程完成”
- 用户明确选择继续深审后，最终完成判定必须同时包含规则台账、正式全量审计和写后人工语义复核；部分通过不得宣称完整流程完成
- 正文完成判定中的字数必须统一运行 `count_words.py`；统计规则为去掉 `#` 开头 Markdown 标题行后，计算所有非空白字符。回执和审计里记录的字符数/字数不得使用估算或其他脚本口径
- 窗口诊断不是首轮通用规则执行器。默认直接进入正式全量审计和全文人工复核；只有用户明确要求定位局部风险时，才导出可选窗口任务
- 规则资产检查未完成时，禁止进入正式全量审计；窗口前回修和人工分段不再是默认硬闸
- 全文人工判断必须记录病因、证据和处理决策；脚本风险标签不能直接写成“必须修改”
- 全文人工判断必须填写 `procedural_stiffness_review`，覆盖 `流程日志感 / 证据清单感 / 三连状态回执 / 手续推进过顺 / 一句完成多任务 / 人物反应被流程替代 / 现场阻力不足 / 分镜或施工稿`，并在写后人工复核回执中给出原句、原因、优先级和改法；不再要求逐窗汇总
- 正式人工复核必须逐节点确认主桥顺序和正文证据；窗口切分本身不是顺序契约，也不属于默认完成条件
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
python3 "$SKILL_ROOT/scripts/count_words.py" "项目目录/正文.md"
python3 "$SKILL_ROOT/scripts/count_words.py" --json "项目目录/正文.md"
```

### 1. 生成并校验写作规则读取回执

```bash
python3 "$SKILL_ROOT/scripts/validate_writing_rule_gate.py" init \
  --project "{项目名}" \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json"

python3 "$SKILL_ROOT/scripts/validate_writing_rule_gate.py" validate \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --stage draft \
  --output "{项目目录}/正文.md"
```

设定和大纲阶段分别使用 `--stage setting --output 设定.md` 与 `--stage outline --output 小节大纲.md`。不要在后续阶段重复传入旧的上游产物。

### 官方批处理入口

以下命令块是本 skill 的批处理权威来源。新增、删减或改参时，优先更新这里；`SKILL.md` 只保留总口径与少量高频入口，`writing-workflow.md` 只保留贴近阶段执行的示例。

当前已提供：

1. `batch-read-gates`
   - 包含：新项目总入口 + 项目骨架 bootstrap + 外层 shell 模板导出 + 规则读取回执 init/validate + 拆文读取回执 init/validate + 读取批次 prepare/status/next-step/run-cycle/finalize/export/apply
   - 目标：把两道读取门禁收成一个连续批次
   - 边界：只能初始化骨架、转发路径、切分文件正文、绑定 SHA、做时序/完整性校验与确定性合并；不得生成人工证据词和读取结论
   - 口径：高层命令优先，`bootstrap-project` 只建标准目录和项目骨架索引，不提前创建设定/大纲/正文；全新项目既可传入不存在的目标路径，也可传入“已按目录硬闸创建、但尚未初始化任何文件”的空目录；目录里已有正式文件或历史内容时仍按占用阻断。人工阶段默认走 `export-review-plan -> preflight-review-plan -> apply-review-plan --consume -> preflight-manifest -> finalize-batches --consume`；紧凑计划不嵌入源文件全文。`finalize-batches` 先在内存中合并并通过两道最终门禁，再原子写回和消费，失败时不得留下半消费状态。`export-batches / apply-batch / apply-manifest` 仅用于单批排障或中途续跑

```bash
python3 "$SKILL_ROOT/scripts/batch_read_gates.py" bootstrap-project \
  --project "{项目名}" \
  --project-dir "{工作区}/{项目名}" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --batch-size 20 \
  --print-paths-json

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" start-new-project-read-gates \
  --project "{项目名}" \
  --project-dir "{工作区}/{项目名}" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --stage outline \
  --stage-output "{工作区}/{项目名}/小节大纲.md" \
  --output "{工作区}/{项目名}/设定.md" \
  --output "{工作区}/{项目名}/小节大纲.md" \
  --output "{工作区}/{项目名}/正文.md" \
  --batch-size 20

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" prepare-batches \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --output-dir "{项目目录}/写作资产/读取批次" \
  --batch-size 20

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" export-review-plan \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --output "{项目目录}/写作资产/读取批次/人工读取计划.json"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" preflight-review-plan \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --input "{项目目录}/写作资产/读取批次/人工读取计划.json"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" apply-review-plan \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --input "{项目目录}/写作资产/读取批次/人工读取计划.json" \
  --consume

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" preflight-manifest \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" finalize-batches \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --consume \
  --stage outline \
  --stage-output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" status \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" next-step \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --stage outline \
  --stage-output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" run-read-gates-cycle \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --stage outline \
  --stage-output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" emit-shell-template \
  --project "{项目名}" \
  --project-dir "{工作区}/{项目名}" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --stage outline \
  --stage-output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md" \
  --batch-size 20

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" init \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" validate \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --stage outline \
  --stage-output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" export-batches \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --output-dir "{项目目录}/写作资产/读取批次" \
  --batch-size 20

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" apply-batch \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --input "{项目目录}/写作资产/读取批次/batch-001.json" \
  --consume

python3 "$SKILL_ROOT/scripts/batch_read_gates.py" apply-manifest \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --consume
```

2. `batch-outline-release`
   - 包含：规则执行台账 init/export、设定顺序契约 init、完整顺序契约 init、开头契约 init、细纲表演验收 init
   - 目标：把“纲前放行批次”的骨架创建与失效重绑收成一轮
   - 边界：只能创建回执和绑定 SHA；不得代填顺序节点、开头判断、逐拍映射或情绪同级判断
   - 规则分类：导出的 `规则模型分类批次.json` 默认只是紧凑索引；用 `read-model-review-batch` 按批从台账即时展开完整案例，不再提前复制整份规则案例库
   - 高层命令：现已支持按项目目录自动推导正式路径；高层总入口优先，`init` 仅用于排障或手动重绑

```bash
python3 "$SKILL_ROOT/scripts/batch_outline_release.py" status \
  --project "{项目名}" \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/batch_outline_release.py" next-step \
  --project "{项目名}" \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/batch_outline_release.py" emit-shell-template \
  --project "{项目名}" \
  --project-dir "{项目目录}"

python3 "$SKILL_ROOT/scripts/batch_outline_release.py" start-outline-release \
  --project "{项目名}" \
  --project-dir "{项目目录}" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --export-model-review-output "{项目目录}/写作资产/规则模型分类批次.json" \
  --export-model-plan-output "{项目目录}/写作资产/规则模型归并计划.json"
```

```bash
python3 "$SKILL_ROOT/scripts/batch_outline_release.py" init \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --setting "{项目目录}/设定.md" \
  --outline "{项目目录}/小节大纲.md" \
  --setting-sequence-receipt "{项目目录}/写作资产/设定顺序契约回执.json" \
  --sequence-receipt "{项目目录}/写作资产/顺序契约回执.json" \
  --opening-source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --opening-receipt "{项目目录}/写作资产/开头承重契约回执_大纲.json" \
  --outline-receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-original "拆文库/{辅助书}/原文/{辅助书}.txt" \
  --export-model-review-output "{项目目录}/写作资产/规则模型分类批次.json" \
  --export-model-plan-output "{项目目录}/写作资产/规则模型归并计划.json"
```

3. `batch-draft-prewrite`
   - 包含：文字颗粒度 bind-outline/apply-section-plan/validate-prewrite + 情绪颗粒度 assemble-section-plan/validate-prewrite
   - 目标：把正文前两份大合同的路径一致性、绑定、缺资产阻断与预检收成一轮
   - 边界：只能检查 `source-original / 子流程索引 / source-emotion-ledger / outline SHA` 一致性并执行官方校验；不得生成落笔包、对白包、逐拍合同或任何人工裁决字段

```bash
python3 "$SKILL_ROOT/scripts/batch_draft_prewrite.py" prepare \
  --project "{项目名}" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --outline "{项目目录}/小节大纲.md" \
  --prose-receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --emotional-receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json"

python3 "$SKILL_ROOT/scripts/batch_draft_prewrite.py" validate \
  --prose-receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --emotional-receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --outline "{项目目录}/小节大纲.md"
```

4. `batch-prewrite-release`
   - 包含：`validate_outline_performance_contract.py validate` + `batch_draft_prewrite.py validate` + `validate_write_release_gate.py draft`
   - 目标：把“人工回填完成后到正文开写前”的最后三道散门禁收成一轮
   - 边界：只能做串联校验和统一摘要；不得重写细纲表演回执、两份合同或放行闸中的人工字段
   - 复用：前两步已经按绝对路径与当前 SHA 成功验证的细纲、文字、情绪合同直接传给最终放行闸，避免同一进程内重复全量校验；绑定不一致时自动回退重验

```bash
python3 "$SKILL_ROOT/scripts/batch_prewrite_release.py" validate \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --sequence-receipt "{项目目录}/写作资产/顺序契约回执.json" \
  --opening-contract "{项目目录}/写作资产/开头承重契约回执_大纲.json" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --outline "{项目目录}/小节大纲.md" \
  --prose-contract "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --emotional-contract "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --primary-source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --profile "profiles/{项目名}.project.profile.json"
```

5. `batch-prewrite-release prepare-validate`
   - 包含：`batch_draft_prewrite.py prepare` + `validate_outline_performance_contract.py validate` + `batch_draft_prewrite.py validate` + `validate_write_release_gate.py draft`
   - 目标：把“正文前合同批次 + 正文开写前最终放行批次”直接收成一个总入口
   - 边界：只能调用官方 prepare/validate 与放行闸，不得自动生成任何 `manual_judgment / target_evidence / parity_status / section_contracts`

```bash
python3 "$SKILL_ROOT/scripts/batch_prewrite_release.py" prepare-validate \
  --project "{项目名}" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --outline "{项目目录}/小节大纲.md" \
  --prose-receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --emotional-receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --sequence-receipt "{项目目录}/写作资产/顺序契约回执.json" \
  --opening-contract "{项目目录}/写作资产/开头承重契约回执_大纲.json" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --profile "profiles/{项目名}.project.profile.json"
```

6. `batch-prewrite-blockers`
   - 包含：`validate_outline_performance_contract.py validate` + `batch_draft_prewrite.py validate`，并可选吸收 `validate_write_release_gate.py draft`
   - 目标：把正文前重复报出的桥级、节级、SF、细节卡、文字合同、情绪合同阻断去重后折成一份施工单
   - 边界：只读取现有校验结果并归类，不修改任何正式回执，也不生成人工语义字段

```bash
python3 "$SKILL_ROOT/scripts/batch_prewrite_blockers.py" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --outline "{项目目录}/小节大纲.md" \
  --prose-receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --emotional-receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json"
```

统一禁止：

- 不得把 batch 入口做成“批量写满正式回执”的黑箱。
- 不得用 batch 入口自动填 `manual_judgment / comparison / target_evidence / source_contract_reviews / parity_status / keep-revise`。
- 需要当前模型逐字段判断的内容，只能由当前模型补写，再交给官方校验器验证。

### 桥级原文情绪序列同步

当当前项目卡在 `bridge_emotion_boundary`，且问题是 `source_emotion_sequence` 为空、错桥、漏桥或混入桥外拍时，优先使用官方同步入口把原文情绪真源回填回正式回执；不要在大 JSON 内手工搜索多个同名字段并直接粘贴长数组。

固定命令：

```bash
python3 "$SKILL_ROOT/scripts/manage_outline_bridge_review.py" sync-source-emotions \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json"
```

作用边界：

- 只同步 `outside_bridge_plot_parity.source_emotion_sequence` 与 `outline_bridge_flow_parity[*].source_emotion_sequence`
- 数据真源固定是各桥 `source_path` 同书目录下的 `写作资产/全文情绪颗粒总账.json`
- `outside_bridge_plot_parity` 只消费 `bid_ids=[]` 的桥外拍
- `outline_bridge_flow_parity[*]` 只消费与该条 `source_bridge_id` 完全匹配的 `bid_ids`
- 不生成也不修改 `target_emotion_sequence`
- 不放宽任何桥级或节级校验，只负责把原文边界真源精确落回正式回执

如果同步后仍报 `bridge_emotion_boundary`，先查：

1. `source_path` 是否真实指向对应原文
2. 同书 `全文情绪颗粒总账.json` 是否与当前拆文资产口径一致
3. `source_bridge_id` 是否与桥段施工卡、总账 `bid_ids` 使用相同桥 ID

不要先在正式回执里挪拍硬凑，更不要让 `target_emotion_sequence` 反向替原文边界试错。

### `batch-prewrite-blockers` 聚焦使用顺序

`batch-prewrite-blockers` 的默认职责是去重，不是替执行器决定施工先后。当前推荐读取顺序如下：

1. 先只消费 `bridge_emotion_boundary`
   - 关注：`全文情绪颗粒总账.json` 的真实 `bid_ids`、桥外 `bid_ids=[]` 误塞、桥段施工卡与总账边界口径冲突。
   - 口径：桥级情绪边界的唯一真源始终是 `全文情绪颗粒总账.json`；桥段施工卡只用于解释承重件、顺序和桥为什么成立。
2. 再消费 `bridge_mapping_missing`
   - 关注：`target_plot_beats / plot_beat_mapping / source_emotion_sequence / target_emotion_sequence` 的缺失、改序、并拍、漏拍。
   - 口径：桥级逐拍逐情绪没有补齐前，不要让节级 `scene_units` 或两份下游合同代替桥级试错。
3. 最后消费 `section_scene_units_missing`
   - 关注：各节 `scene_units`、逐节场面验收承载位和节级空 scaffold。
   - 口径：节级场面承载必须建立在桥边界和桥级映射已稳定的前提上。

若当前脚本版本尚未自动吐出上述分类，执行器也必须先手工把同轮阻断折成这三类再施工；禁止按报错自然顺序东补一块、西补一块，导致桥级边界反复污染节级证据。

### 2. 生成并校验拆文读取回执

```bash
python3 "$SKILL_ROOT/scripts/validate_source_read_gate.py" init \
  --project "{项目名}" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --receipt "{项目目录}/写作资产/拆文读取回执.json"

# 目标回执已存在时，init 自动归档旧文件并原子生成新回执。
# 调用方不要手工移动、删除或用 --force 绕过归档。

python3 "$SKILL_ROOT/scripts/validate_source_read_gate.py" validate \
  --receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"
```

### 3. 初始化、绑定并校验规则执行台账

```bash
python3 "$SKILL_ROOT/scripts/validate_rule_execution_ledger.py" init \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --ledger "{项目目录}/写作资产/规则执行台账.json"

python3 "$SKILL_ROOT/scripts/validate_rule_execution_ledger.py" validate-prewrite \
  --ledger "{项目目录}/写作资产/规则执行台账.json"

python3 "$SKILL_ROOT/scripts/validate_rule_execution_ledger.py" preflight-final-rebind \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --artifact "设定={项目目录}/设定.md" \
  --artifact "大纲={项目目录}/小节大纲.md" \
  --artifact "正文={项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/validate_rule_execution_ledger.py" bind-artifacts \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --artifact "设定={项目目录}/设定.md" \
  --artifact "大纲={项目目录}/小节大纲.md" \
  --artifact "正文={项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/validate_rule_execution_ledger.py" validate \
  --ledger "{项目目录}/写作资产/规则执行台账.json"
```

逐项字段、规则展开范围和脚本/人工分工见 [rule-execution-ledger.md](rule-execution-ledger.md)。

### 4. 生成并校验开头承重契约

大纲和正文各自生成回执，由当前模型逐项人工回填：

```bash
python3 "$SKILL_ROOT/scripts/validate_opening_contract.py" init \
  --project "{项目名}" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md" \
  --artifact-kind draft \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json"

python3 "$SKILL_ROOT/scripts/validate_opening_contract.py" validate \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md"
```

只要任务说明先于关系钩子、主体三拍功能顺序被打乱，或题面未在前 `80 / 120` 字兑现，就返回 blocked。详见 [opening-contract-gate.md](opening-contract-gate.md)。

### 5. 建立并校验全文文字颗粒度合同

完整初始化、写前和初稿停靠前命令见 [prose-granularity-contract.md](prose-granularity-contract.md)。固定入口为：

人物性格颗粒度作为本合同 v2.4 的内置层执行，详细字段与裁决见 [character-personality-granularity.md](character-personality-granularity.md)。只有活句而没有不可互换人物证据时，下面两道验证必须阻断。

```bash
python3 "$SKILL_ROOT/scripts/validate_prose_granularity_contract.py" bind-outline \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --outline "{项目目录}/小节大纲.md"

python3 "$SKILL_ROOT/scripts/validate_prose_granularity_contract.py" validate-prewrite \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --outline "{项目目录}/小节大纲.md"

python3 "$SKILL_ROOT/scripts/validate_prose_granularity_contract.py" bind-draft \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --draft "{项目目录}/正文.md" \
  --section-progress "{项目目录}/写作资产/逐节正文进度.json"

python3 "$SKILL_ROOT/scripts/validate_prose_granularity_contract.py" preflight-manual-sidecar \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --sidecar "{项目目录}/写作资产/文字颗粒度人工侧车.json" \
  --draft "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/validate_prose_granularity_contract.py" validate-draft \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --draft "{项目目录}/正文.md" \
  --section-progress "{项目目录}/写作资产/逐节正文进度.json"
```

### 6. 生成并校验写后人工语义复核回执

全新正文：

```bash
python3 "$SKILL_ROOT/scripts/validate_post_write_human_review_gate.py" init \
  --project "{项目名}" \
  --text "{项目目录}/正文.md" \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json"
```

局部或专项回炉：

```bash
python3 "$SKILL_ROOT/scripts/validate_post_write_human_review_gate.py" init \
  --project "{项目名}" \
  --text "{项目目录}/正文.md" \
  --base-text "{母稿目录}/正文.md" \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json"
```

人工回填后：

```bash
python3 "$SKILL_ROOT/scripts/validate_post_write_human_review_gate.py" validate \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json" \
  --text "{项目目录}/正文.md"
```

### 5. 生成单书 profile

```bash
python3 "$SKILL_ROOT/scripts/generate_story_profile.py" \
  --source "拆文库/{书名}" \
  --name "{书名}" \
  --output "拆文库/{书名}/book.profile.json"
```

### 6. 生成融合 profile

```bash
python3 "$SKILL_ROOT/scripts/generate_story_profile.py" \
  --merge-profile "拆文库/{书名1}/book.profile.json" \
  --merge-profile "拆文库/{书名2}/book.profile.json" \
  --name "{项目名}" \
  --output "profiles/{项目名}.project.profile.json"
```

硬闸：任一单书 profile 缺少 `precheck_overrides` 时停止融合，重新全量拆书后再生成单书和融合 profile。

### 7. 跑全量审计（默认不切窗）

默认流程跳过窗口前回修和人工模型分段，直接执行正式全量审计；下方窗口命令仅在用户明确要求窗口诊断时使用。

窗口前先初始化并回填规则/资产定向回修回执：

```bash
python3 "$SKILL_ROOT/scripts/validate_pre_window_revision_gate.py" init \
  --project "{项目名}" \
  --text "正文.md" \
  --receipt "写作资产/窗口前规则资产回修回执.json"
```

回填后必须通过：

```bash
python3 "$SKILL_ROOT/scripts/validate_pre_window_revision_gate.py" validate \
  --receipt "写作资产/窗口前规则资产回修回执.json" \
  --text "正文.md"
```

通过后再导出人工模型分段任务：

```bash
python3 "$SKILL_ROOT/scripts/run_full_ai_audit.py" \
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
python3 "$SKILL_ROOT/scripts/run_full_ai_audit.py" \
  正文.md \
  --profile profiles/{项目名}.project.profile.json \
  --audit-rulebook "$SKILL_ROOT/references/governance/audit-rulebook.json" \
  --pre-window-revision-receipt 写作资产/窗口前规则资产回修回执.json \
  --sequence-receipt 写作资产/顺序契约回执.json \
  --model-segmentation-receipt 写作资产/人工模型分段回执.json
```

默认流程不再要求人工窗口边界、窗口归属或逐窗 `procedural_stiffness_review`。正式审计与写后人工语义复核覆盖全文，并以真实原句判断节奏、对白、流程硬化和顺序；窗口分段仅作为用户明确要求时的可选诊断。

### 8. 生成回修任务单

```bash
python3 "$SKILL_ROOT/scripts/auto_revise_ai_flavor.py" \
  正文.md \
  --profile profiles/{项目名}.project.profile.json \
  --output-dir auto_revise_runs
```

已识别的高风险桥段如果没有进入前排桥段任务，任务单生成直接阻断。已绑定 profile 时，`bridge_rules / scene_assets / style_assets / story_guardrails` 缺失也直接阻断并要求重建拆书/profile。短段偏多、局部频率和统计波动仍只作诊断预警，不得据此机械改文。

### 9. 跑单轮闭环

```bash
python3 "$SKILL_ROOT/scripts/run_revision_cycle.py" 当前短篇目录
```

### 10. 做题材首次校准

```bash
python3 "$SKILL_ROOT/scripts/compare_with_external_block_audit.py" \
  "项目目录" \
  --audit-dir "项目目录/写作资产/正式审计" \
  --output "项目目录/写作资产/外部分块审计对齐.csv" \
  --summary-output "项目目录/写作资产/外部分块审计对齐摘要.json" \
  --internal-standard-output "项目目录/写作资产/内部审计标准.json"
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

完整流程停机前还必须运行：

```bash
python3 "$SKILL_ROOT/scripts/validate_short_write_completion.py" mark-complete \
  --state "{项目目录}/写作资产/短篇全流程状态.json"
```

完成态的必需检查包含 `write_release_gate / prose_granularity_contract / emotional_granularity_contract / platform_format_gate`。这些检查与规则、来源、顺序、开头、台账、正式审计和写后人工复核必须同时通过；窗口前回修和人工分段不属于默认必需检查。状态仍为 `active` 或缺任一检查时，不得对外宣称完整流程完成。

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
