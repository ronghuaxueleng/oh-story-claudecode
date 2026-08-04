---
name: story-short-write-rule-catalog
description: |
  短篇网文写作。辅助短篇小说创作，从起盘、搭骨架到正文和回炉，重点抓冲突、情绪、高潮和值得付费的后果。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」
metadata:
  version: 1.9.0
---

# story-short-write：完整强制规则目录

你是短篇网文写作执行器。从起盘到成稿，把一篇短篇真正写出来。

主文件只保留四件事：

1. skill 定位
2. 主流程入口
3. 强制闸门
4. 调用哪些 `references/` 和 `scripts/`

细则不再在主文件里重复展开。

---

## 定位与边界

本 skill 负责：

- 起盘
- 换链
- 细纲
- 正文
- 分块回炉

不负责：

- 把拆书工作混进写作主流程
- 把整篇去味流程混成写作默认动作
- 把通用脚本说明手册塞进正文入口

固定边界见：

- [references/governance/skill-boundaries.md](references/governance/skill-boundaries.md)

硬口径：

- `story-short-write`：起盘、换链、写正文、定点回炉
- `story-short-analyze`：拆书、样本分级、高敏桥识别
- `story-deslop`：已成稿去味、局部高风险段第二闸门

---

## 工具链

本 skill 默认走 `profile` 驱动流程，不接受“只看题材概括 / 只看拆文摘要 / 只靠提示词临场发挥”直接开正文。

内置脚本位于 `story-short-write/scripts/`：

- `validate_writing_rule_gate.py`
- `validate_source_read_gate.py`
- `validate_rule_execution_ledger.py`
- `validate_write_release_gate.py`
- `validate_sequence_contract.py`
- `validate_outline_performance_contract.py`
- `validate_draft_capacity_contract.py`
- `validate_first_draft_entry.py`
- `validate_section_draft_execution.py`
- `build_section_source_bundle.py`
- `validate_post_write_human_review_gate.py`
- `validate_zhihu_section_format.py`
- `count_words.py`
- `generate_story_profile.py`
- `run_full_ai_audit.py`
- `validate_pre_window_revision_gate.py`
- `audit_novel_ai_flavor.py`
- `auto_revise_ai_flavor.py`
- `run_revision_cycle.py`
- `precheck_rewrite_gate.py`
- `validate_gate_receipts.py`
- `compare_with_external_block_audit.py`
- `compare_source_baseline_audit.py`

工具链地图和规则接入说明见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/governance/source-baseline-imitation-audit.md](references/governance/source-baseline-imitation-audit.md)
- [references/integration/internal-toolchain-map.md](references/integration/internal-toolchain-map.md)
- [references/integration/myconfig-rule-integration.md](references/integration/myconfig-rule-integration.md)
- [references/integration/rule-onboarding-checklist.md](references/integration/rule-onboarding-checklist.md)

高风险回修必须额外挂载：

- [../story/references/short-high-risk/reference-index.md](../story/references/short-high-risk/reference-index.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [references/governance/global-humanity-audit.md](references/governance/global-humanity-audit.md)
- [../story/references/high-risk-gates/reference-index.md](../story/references/high-risk-gates/reference-index.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

---

## 执行规则

总优先级：

1. `成文像真人` 高于 `看起来稳妥`
2. `关系 / 后果 / 桥段顺序成立` 高于 `句面变顺`
3. `人物不同脸` 高于 `所有句子都像会过审的标准人话`
4. `能直接给读者读` 高于 `像已经过完很多闸门的安全稿`

硬口径：

- 不允许把正文越修越像“过闸稿 / 安全施工稿 / 成熟模板块”
- 如果一轮修改同时带来“命中下降”和“活人感下降”，视为失败，不算优化
- “更像会过审”不等于“更像能发表”；正文首先要像人在现场里活着，不像规则先替人物说完了

1. 先定平台，再定故事口气。
2. 先判这题是 `讲法型 / 桥段链型 / 混合型`，再决定写法。
3. 短篇默认从“事情马上要爆”的位置切入，不从长篇式铺垫开写。
4. 主角不能只受压，必须持续有动作。
5. 爽点不是骂赢，是位置变化、后果变化和关系变化。
6. 开头三句定起事，高潮定值钱，结尾定余味。
7. 写前必须有规则包：单书读 `book.profile.json`，融合稿读 `project.profile.json`。
8. 规则包来自拆书产物，不来自 skill 内硬编码题材默认值。
9. 写设定、大纲或正文前必须通过 `validate_writing_rule_gate.py`；`format-and-structure.md`、当前版 `anti-ai-writing.md`、`craft/narrator-voice.md` 任一未读都阻断。
10. 写大纲和正文前必须通过 `validate_source_read_gate.py`；`source_asset_coverage` 的 SHA 只负责追溯，不得冒充模型已读。仿写任务必须用 `--writing-mode direct_imitation` 读取由 `story-short-analyze` finalize 预先生成的无损语义编译包：完整原文仅存一份，主体全量 BID/SF 及其事实/因果/情绪/表演/文风字段、辅助已选 SF 的全部字段均为包内真实内容。写作阶段禁止生成或刷新该包；缺失/过期必须阻断并返回拆书 finalize。
11. 桥段链高敏时，先回细纲换链，不许直接磨句子。
12. 写前写后都要审计，不能只看送检结果倒推补丁。
13. 审计分段只服务定位风险，不反向指导正文排版。
14. 一场只做一件大事，一段只保留一个主任务。
15. 插叙只补一个原因，不补整份说明书。
16. 对话优先写试探、回避、失手，不优先写结论。
17. 每三场里至少一场不直接推进主冲突，要给生活层缓冲。
18. 外部分块高分时，优先判“块级完整推进风险”，不先判词句漂不漂亮。
19. “显性命中清零”不等于安全，只要整块仍然太整齐、太明白、太像成品，就继续回块级问题。
20. 新沉淀出的成功经验必须回写规则层，不能只停在聊天里。
21. 自检必须逐条引用正文句子，不准空口保证“已经处理”。
22. 高敏桥回修时，固定补看 `现实后果隔层 / 尾声入口 / 人物不同脸`，这三项没过，不算收口。
23. 不允许把“说明更完整、判断更清楚、台词更会总结”误当成正文变好。
24. 任何一轮回修，如果把人物写得更懂事、更会解释、更会给主题句，先怀疑是在变假。
25. 自动审计只能叫“脚本预扫”；作者代判、叙述者/作者边界、多余解释、现场依据和对白过度高效必须人工逐句判断。
26. 正文写完或回炉后必须通过 `validate_post_write_human_review_gate.py`；局部或专项回炉必须绑定母稿并逐条复核全部新增/改写句。
27. 写后必须查看 `rhythm_distribution_audit`；叙述者气口分布、跨长窗节奏落差和长窗对白效率任一未人工复核，不得放行。
28. 通过两份读取门禁后，必须在写设定、大纲或正文前初始化 `规则执行台账.json`；缺台账直接阻断，不做兼容回退。
29. skill 核心规则和编译包中选中的拆书资产先由脚本按小节/资产文件压成规则卡；当前写作模型必须阅读全部案例，归纳一条 `canonical_rule_text`，再区分 `workflow / format / setting / outline / draft / audit / source candidate / source prohibition`。`export-model-review` 把重复案例和来源收口到顶层 `case_registry / source_ref_registry`，规则项用 ID 引用；这只去重存储，不得少读任何案例或来源。写设定、大纲或正文前必须通过 `validate-prewrite`，确认适用性、执行方式、目标阶段/场景与裁决理由；关键词建议不能直接确认分类。
30. 所有拆书文件必须逐文件判断，16 表及承重资产按同类型规则族执行；拆书候选未选中应标 `not_applicable`，禁用规则未命中用全文复核证明，不能把表格每行都膨胀成强制正文规则。
31. 写作过程中执行一项标记一项；最终正文绑定后必须通过 `validate_rule_execution_ledger.py`，不得写完后批量伪造“已使用”记录。skill 或来源更新时先运行 `sync-sources`：只有案例文本确实变化的规则卡允许被重置，未变化卡必须保留已有分类与证据。
32. 完全重复规则初始化时自动合并，语义近似规则人工归入 canonical；只有失败的适用 `draft_constraint` 可以设置 `requires_text_change: true` 并进入正文修改单。
33. 写后长窗审计必须先导出人工模型分段任务，由当前执行 skill 的模型完整读取正文并回填分段回执；禁止脚本调用外部 API、Claude CLI 或其他模型。正文 SHA 变化后旧分段回执立即失效；无回执的算法滑窗只能算预扫。
34. 主体拆书的 `可直接仿写_导语拆解表.md` 必须单独生成开头承重契约；大纲和正文各过一次。前 `20 / 60 / 80 / 120` 字的关系锚、异常站位、题面兑现、读者问题、说明抢跑、功能顺序、原文真实开口对照和去分镜/去施工单任一失败都直接阻断，不能并入普通规则卡后降级为 warning。
35. profile、事实台账、样本分级、作者 DNA、桥段施工、高敏识别、同桥过检、禁写清单、顺序/后果/外部秩序表即使并入 canonical，也必须逐来源填写 `source_contract_reviews`；主体治理资产不得标 `not_selected`。规则级文件父节点由子规则自动汇总，手填状态与子规则不一致时阻断。**最终产物一旦重新绑定，台账证据必须递归重绑**：`skill_rules / source_assets / asset_rules` 中所有 `text_evidence / structural_claim_reviews / source_contract_reviews.target_evidence / scope_reviews` 都必须引用当前设定、大纲、正文中真实存在的原句；canonical 合并规则不能只改代表项，必须按每条规则实际 `source_refs` 重建 `source_contract_reviews`，旧正文证据、旧 SHA、缺来源、残留无关来源或“公共证据代替逐来源契约”一律阻断。`validate_rule_execution_ledger.py validate` 未输出 `passed` 时，不得进入完成态，也不得用人工口头说明替代。
36. `setting_constraint / outline_constraint` 如果在 `target_scene` 同时宣称多个目标通过，必须逐目标填写 `structural_claim_reviews`；开头、反转、后果等任一目标没有对应产物原句时，不得整体判过。
37. 警告必须按语义分级：已识别的高风险桥段未进入前排回修任务、强制资产缺失、承重顺序错乱属于硬失败；统计波动、短段偏多和局部频率异常只作诊断，不得反向驱动机械改文。
38. **设定—大纲—正文顺序必须单独过顺序契约硬闸**：设定内部、设定与大纲、正文与 canonical sequence 任一冲突都阻断；“已读设定”“台账 passed”或“开头契约 passed”不能替代顺序契约。
39. **写作放行是单独的硬闸，不得绕过或事后补票**：生成设定、大纲或正文前，必须运行 `validate_write_release_gate.py`。设定写完、开始写大纲前必须先通过 `validate_sequence_contract.py validate-setting`；大纲阶段必须传入通过的设定内部顺序回执；正文阶段必须传入通过的完整顺序契约回执。任一前置门禁不是 `passed`，立即停止当前阶段。
40. **未通过写作放行闸时，禁止创建或修改目标产物**：不能因为“先写一版再修”“先生成正文测试流程”或“台账只是记录问题”而继续；必须先修门禁、回执、来源契约或台账，再重新运行放行闸。
41. **完整流程不是部分检查相加**：只通过人工复核门、预检、AI 味脚本或算法长窗中的一部分，不得宣称流程完成；必须同时满足写前放行、顺序契约、规则台账、开头契约、正文人工复核和正式长窗审计。
42. **算法窗口永远不能代替人工窗口**：未完成当前模型人工分段回执时，`run_full_ai_audit.py` 只能作为算法预扫；回执为 `pending`、缺失或正文 SHA 不一致时，禁止结束写作任务。
43. **正文完成条件必须全部满足**：人工模型分段回执为 `completed`、正文 SHA/字符数/边界一致、正式全量审计绑定并通过完整顺序契约、每个窗口完成顺序节点结构复核、正式全量审计使用该回执、`rhythm_distribution_audit` 已逐窗人工复核、平台格式校验通过、`validate_post_write_human_review_gate.py` 和 `validate_rule_execution_ledger.py` 均输出 `passed`。缺任何一项，只能报告“未完成”。其中正文字符数必须统一使用 `count_words.py` 的番茄口径：去掉 `#` 开头 Markdown 标题行后，统计所有非空白字符；禁止用估算、编辑器统计或其他临时脚本替代。
44. **人工窗口前必须先做通用规则/拆书资产定向回修**：正文初稿或上一轮正文完成后，先按当前 skill canonical 规则和主体拆书资产执行一轮正文回修，并通过 `validate_pre_window_revision_gate.py`；未通过时不得导出人工分段任务，也不得把窗口检测当作当前轮正式审计。
45. **窗口检测只负责定位剩余问题**：窗口风险标签、对白比例、气口和重复统计只能作为定位证据；每窗必须由当前模型人工判断具体病因和“保留/局部回修/整块回炉”，并逐节点核对顺序契约；不能把脚本标签直接等同于正文缺陷。人工窗口还必须逐窗填写 `procedural_stiffness_review`，把 `流程日志感 / 证据清单感 / 三连状态回执 / 手续推进过顺 / 一句完成多任务 / 人物反应被流程替代 / 现场阻力不足 / 分镜或施工稿` 汇总成正式审计和施工单里的可改问题；只给 AIGC 分数、不列具体原句和改法，视为人工窗口未完成。
46. **窗口前回修后必须重新绑定正文**：正文 SHA、字符数或任何正文句子变化都会使窗口前回修回执和人工分段回执同时失效；必须先重新执行窗口前规则/资产回修，再重新导出并人工切窗。
47. **全局成文形状必须单独审查**：局部窗口通过不能替代全文检查；必须检查章节弧线同构、章尾收束重复、主角连续正确、专业细节功能性和全文对白模式变化。
48. **四项全局审查缺一不可**：`global_structure_and_chapter_endings`、`protagonist_irregularity_and_agency`、`technical_detail_function`、`dialogue_pattern_variation` 必须进入写后人工复核回执；缺项、空证据或未裁决都阻断。
49. **已有规则不是建议**：凡是 skill、`anti-ai-writing.md`、`narrator-voice.md` 或拆书资产已声明为人工/混合检查项，必须在回执逐项标记 `passed` 或 `revise`；不能因为脚本没有命中就视为已执行。
50. **全局人工审查必须解释放行理由**：如果审计预扫命中章节收束重复、专业细节密集或对白模式重复，人工回执必须给出正文原句和保留/回修理由；不得只写“已检查”。
51. **拆书全局结论必须被写作阶段逐项消费**：存在主体拆书时，必须分别读取 `拆文报告.md`、`写作手法.md` 和 `写作资产/样本分级与可学层.md` 中的全局成文形状审计，并在规则执行台账中逐项处理 `全局结构形状`、`章尾收束模式`、`主角不规则性`、`专业细节功能性`、`全文对白模式`。只记录“已读”不算执行；每项必须判定为 `applied / not_selected / prohibition_checked`，并绑定设定、大纲、正文或人工审计证据。
52. **拆书反面结论不得直接机械改正文**：写作阶段必须先区分正向 DNA、反面规则、题材限制和本稿不适用；没有 `draft_constraint + applicable + failed + requires_text_change=true`，不得为了“人味”强行添加失控、闲枝、术语删减或答非所问。
53. **题材壳 / 主卖点 / 核心情绪必须先锁死再写**：设定阶段必须明确 `题材壳`、`主卖点`、`核心情绪`、`付费期待`、`禁止漂移方向` 五项；若是 `追妻 / 婚恋清算 / 强情绪关系文`，禁止把成文主体写成 `职业流程文 / 冷处理撤离文 / 现实切割说明文`。五项缺任一，阻断大纲和正文。
54. **题材承诺和卖点兑现必须单独过人工硬闸**：写后人工复核回执必须新增 `premise_genre_promise_alignment` 与 `core_selling_point_payoff` 两项，分别核对“题面 / 设定 / 大纲承诺的文类体感有没有跑偏”与“全文是否持续提供对应的高价值读点、掉位后果和关系回弹”。只用开头契约、顺序契约、窗口检测或 AI 味结果代替这两项，直接失败。
55. **强情绪追妻题的男主姿态必须验收**：若设定把关系线归为 `追妻`、`婚恋清算` 或近似题材，正文必须出现可观察的 `失位后持续后果 + 低位补救失败/狼狈求回 + 女主明确边界动作`；若男主只剩功能性修补、理性解释或秩序恢复，视为题材漂移，不得放行。
56. **选中的题材公式必须逐条生成专项复核，不得只读不验**：写前从实际采用的题材公式中抽出本稿适用规则；写后在 `genre_formula_review.rules` 中逐条填写 `id / rule / status / evidence`。每条证据必须引用最终正文原句并给出人工判断，不能用“结构成立”“整体已执行”代替。
57. **追妻题句段级检查为强制项**：`female_softening_externalized` 检查女主的一秒松动是否由动作、停顿或外部细节折射；该证据必须紧邻男主实际承担的关系代价或有效补救，职业文件、普通工作动作或无关停顿不能冒充情感松动。`no_emotional_after_summary` 检查情绪破绽后是否又补作者总结；`repair_failure_fact_based` 检查补救失败是否落在再次选择和具体事实上。缺任一项，写后人工复核不得通过。
58. **题材公式专项回执同时绑定最终正文和公式来源**：正文 SHA 或题材公式来源 SHA 任一变化，旧回执立即失效；必须在最后一次正文修改后重新逐条复核。不能因为本轮只改一句，就沿用上一轮“已检查”的题材结论。
59. **写后必须执行局部生硬候选扫描，但脚本不得代判**：运行 `audit_local_stiffness.py` 定位 `直白心理 / 情绪后总结 / 结果汇报链 / 论点型对白 / 机械章尾钩子 / 克制解释过度 / 高价值场景摘要化`。脚本命中只算候选；当前模型必须完整读取上下文，逐项判断 `保留 / 回修 / 删除`。
60. **人工复核必须做全文反例扫描，不能只找一条合格证据**：`direct_psychology_externalization`、`post_emotion_summary_residue`、`result_reporting_chain`、`thesis_dialogue_concreteness`、`chapter_end_hook_naturalness`、`restraint_overexplained`、`high_value_scene_summary_compression`、`full_text_storyboard_construction_list_review` 八项必须进入 `human_checks`。每项应证明全文剩余候选均已裁决；只引用一处合格句、未处理同类反例，视为未执行。
61. **通过状态不得包含待改证据**：任何人工检查证据的 `action` 只要是 `revise / delete`，该项就不能标记 `passed`；必须先修改正文、重建绑定最终 SHA 的回执，再重新检查。禁止把“已发现问题”冒充“已通过检查”。
62. **克制不能由连续否定句自证**：同一小段连续出现三次以上 `我没有 / 我不知道 / 我没问 / 这件事我后来也没`，必须进入 `restraint_overexplained`；优先删除解释，让前面的物件和动作自己承担克制。不能为了表现冷静，把“不做什么”逐项讲给读者。
63. **高价值桥段禁止被转述摘要吞掉**：追妻低位、公开掉位、揭示、决裂、求回等承重场景若出现 `他先说……又说……` 一类复合转述，必须进入 `high_value_scene_summary_compression`；当前模型要判断是否恢复为现场对白、动作和停顿。普通过场可保留转述，承重场景默认现场化。
64. **知乎 / 盐言正文禁止书名和章节名**：平台为知乎或盐言时，`正文.md` 只能使用独占一行的连续纯数字 `1.`、`2.`、`3.`；文件开头不得保留 `# 书名`。`## 第1节 标题`、`## 1. 标题`、`###1.`、`第一章 标题`、`1. 标题`、`1、标题` 均直接阻断。大纲可以有小节名，但写正文时不得继承；每节关闭、正文首次完成及每次回修后必须运行 `validate_zhihu_section_format.py`。
65. **追妻题不可逆去留决定必须验时机**：若卖点包含“她本来可能留下，但男主连续选择亲手关门”，接受新岗位、签署不可撤回协议、永久迁离等动作不得在关键重复伤害发生前完成。写后必须执行 `irreversible_exit_timing`，引用决定前后的正文证据；若题型从开头就承诺女主立即退出、悬念只在后果，则必须明确记录该例外，不能默认套用拖延决定。
66. **一秒松动必须验触发对象，结尾必须验完成感**：追妻专项新增 `female_softening_trigger_relevance`，确认松动由婚姻、共同生活、公开失位或男主真实代价触发，而非相邻职业道具；全文人工复核新增 `ending_action_completion`，确认结尾落在已完成的动作、关系后果或明确选择上。禁止用“任务刚出现新信号”式机械中断冒充余韵，也禁止为收束追加主题总结。
67. **强冲突载体必须由当前模型逐场人工验收**：这里的“冲突”不是“双方意见不一致”，而是争夺某种现实权力、位置或后果，例如 `制止权 / 签字权 / 解释权 / 入场权 / 物件处置权 / 花钱决定权 / 谁先被救 / 谁先被信`。固定词、动作词和统计只能导出候选，不能直接判定“有肢体冲突”或“冲突只靠对白”。正式人工分段回执必须填写 `conflict_carrier_review`，逐场判断 `dialogue / body / object / space / identity / rhythm` 如何改变动作、站位、物件控制权、身份或后果；并明确回答“这场到底在抢什么权”。若一场戏只能总结为“他们吵了一架 / 有分歧 / 情绪很重”，但答不出被争夺的现实控制权，视为冲突未立住。强情绪追妻稿若长期只靠克制问答，直接阻断。直接扇打、掐脖、踢踹等行为会改变角色可追性，必须人工裁决为不可洗白并同步题材与结局，或先修改正文；禁止把直接暴力自动包装成爱、吃醋或追妻张力。
68. **人物交流必须由当前模型逐场人工验收**：这里的“交流”不是“人物开口说话”或“补了眼神动作词”，而是 `一方施压 -> 另一方被迫接招 -> 现场发生可见变化`。视线、肢体、物件、空间、节奏、身份等固定词只用于导出候选，不得直接判定“有交流”或“没有交流”，也不得据此自动加风险分、挂失败标签或机械补写。正式人工分段回执必须填写 `interaction_exchange_review`，覆盖所有承重对话场，并证明一方施加的压力实际改变了另一方的 `动作 / 站位 / 物件控制权 / 回答范围 / 身份 / 后果 / 现场秩序` 至少一项。孤立台词、答题对白和作者解释不能冒充人物交流；只补“他盯着我”“她顿了一下”“他缓缓开口”也不算修复。任一承重场 `real_exchange=false`、`change_visible=false` 或 `author_substitution=true`，必须先回正文修改，不能结束流程。
69. **灵动感和规则证据感必须由当前模型全文人工验收**：新增写后人工复核项 `rule_evidence_stiffness_and_liveliness`。模型必须逐场判断正文是否把 `门槛 / 黄线 / 钥匙 / 确认框 / 工具箱 / 证据袋 / 麦克风` 等冲突载体写成“规则检查证据”，而不是人物自然反应。合格标准不是多加动作词，而是人物有临场偏差、错答、回避、手忙脚乱、生活毛边或不完全服务主题的小动作；这些毛边仍需服务人物真实，不得变成随机废话。若承重场读起来像“规则 A 已执行、证据 B 已展示、边界 C 已落地”的施工说明，必须回正文改成现场化人物反应；脚本、固定词和物件数量不得代判通过。
70. **开头回炉必须对照原文真实开口，且不得改成分镜/施工单**：凡用户指出开头啰嗦、说明抢跑、成品感高、像剧本分镜或像规则施工稿，必须读取所有选中主体/辅助拆文的 `原文/` 开头样本，不得只看导语拆解表、profile 或规则摘要。回修后开头不能是一句一个动作、一句一个证据、一句一个反应的清单，也不能像“规则 A 执行、证据 B 展示、边界 C 落地”的验收单；必须把人物动作、现场噪音、物件证据和关系反应揉进连续叙述气口。`validate_opening_contract.py` 中 `original_opening_samples_compared_before_revision` 与 `opening_not_storyboard_or_construction_list` 必须为 `true`，并填写 `original_opening_comparison` 和 `opening_flow_review`；缺字段、空证据或只写“已检查”均阻断。
71. **分镜清单 / 规则施工稿是全文禁区，不只限开头**：新增写后人工复核项 `full_text_storyboard_construction_list_review`。当前模型必须全文扫描是否存在“一句一个动作 / 一句一个证据 / 一句一个反应”的镜头清单，或“规则 A 执行、证据 B 展示、边界 C 落地”的验收施工稿。若出现在叙述正文、关系场、冲突场、追妻低位、揭示或结尾中，必须回修为连续现场叙述；不得因为格式短、节奏快或脚本未命中而放行。唯一例外是正文情节内真实出现的清单、报告、日志、合同、群公告、流程单等文本本身；例外必须在 `allowed_in_story_artifacts` 中逐条引用原文并说明其情节功能，不能把作者写法问题伪装成“角色正在看文件”。
72. **回修前必须先判问题粒度，禁止把大块病当小句病补丁化处理**：每轮改正文前必须先给出 `revision_scope_decision`，至少判断问题是 `global_structure / coarse_block / full_scene / paragraph_cluster / sentence_hotspot / format_only` 哪一类。凡命中 `成文真实感、题材承诺、主桥顺序、场戏功能、人物偏手、人物交流、冲突载体、流程硬化、分镜施工稿、追妻低位、开头成品感` 等场面级或结构级问题，默认按整场/大段回炉处理，必须重写该场的动作链、交流链、物件控制权和气口，不得只补一两句动作词或替换词。只有当人工证据证明问题只剩 `重复词、冒号模板、单句直白心理、格式、错别字、局部标点、单个术语残留` 时，才允许小改。若连续两轮正式审计仍命中同一 P0/P1，必须升级回修幅度：`sentence_hotspot -> paragraph_cluster -> full_scene/coarse_block`，不能继续在原位置小补丁。
73. **细纲表演验收是正文前独立硬闸**：仿写、融合和强情绪关系稿写完细纲后，必须用 `validate_outline_performance_contract.py` 绑定细纲与所有选中原文 SHA，并由当前模型逐节人工验收 `唯一不可逆动作 / 主控物件 / 拆书功能机制 / 原文场面颗粒度 / 原文表演机制及迁移边界 / 信息延迟 / 人物偏手与错答 / 交流变化链 / 冲突载体 / 禁写项 / 细纲原句证据`。只通过规则台账、顺序契约或开头契约不算细纲合格；任一节仍是多节点排队、证据清单、对白答题或分镜施工稿，必须先回细纲整场重构，禁止写正文。
74. **“完全参照原文”必须落实为表演机制对照，不得降级成桥段参考**：当前模型必须完整参照选中原文的结构、场景推进、信息延迟、物件/动作控制权、关系压力与场末信息边界，并在细纲表演验收中逐节说明迁移机制；不得复制原人物、职业、原句和完整情节壳。只写“参考《某书》”或只套题材、人设、反转位置，视为未执行。
75. **验收字段不得污染写作细纲**：`唯一不可逆动作 / 主控物件 / 信息延迟 / 交流变化链 / 禁写项` 等字段只能填写在 `细纲表演验收回执.json`，不能把 `小节大纲.md` 写成一节一张字段表。用于生成正文的细纲必须是连续的表演型场面，按 `人物如何入场 -> 压力如何出现 -> 谁先偏手或错答 -> 动作/物件/站位如何换主 -> 哪个信息仍不说 -> 场末留下什么余波` 详细展开。若细纲直接呈现为“目标、机制、载体、禁写、证据”的规则清单，即使回执字段齐全也必须回炉，不得写正文。
76. **细纲必须双轨参照，不得只做功能映射**：写细纲时，每节必须先从拆书资料确认 `功能机制`，再回到选中原文对应桥段确认 `场面颗粒度`。功能机制回答“这一节迁移公开掉位、私域换主、不可替代物爆体、高成本补救后再选错、行动验收、公开反噬、私人尾声中的哪一种”；场面颗粒度回答“原文里谁先动、谁抢/挡/松手、哪个物件或空间改归属、哪句台词逼出动作、旁观者或外部秩序如何改变现场”。只引用拆书报告、profile、同桥过检摘要或规则卡，不回看原文具体段落，视为未执行；只写“机制已迁移”但答不出原文场面颗粒，细纲表演验收必须失败。
77. **原文桥段流程对齐必须在细纲阶段完成，不得拖到正文后审计**：主流程仿写、融合仿写、同桥仿写或用户要求“完全参照原文”时，写正文前必须先建立 `source_bridge_flow_inventory`，列出主体原文全部 BID/关键子桥段、必保动作顺序、物件/空间/身份换主、场末状态变化和不可合并/不可删理由；再建立 `outline_bridge_flow_parity`，逐桥绑定到目标细纲小节和细纲原句证据。每个原文 BID 必须是 `matched` 或有明确迁移边界的 `adapted`；`missing / weakened / merged_unclear / only_function_mapped` 一律阻断正文。禁止用“正文写完再看像不像原文”“后期审计再补桥段”替代细纲阶段流程设计。
78. **细纲不是只写本书顺序，还要证明原书顺序如何迁移**：顺序契约只能证明设定、大纲、正文内部不自相矛盾；它不能证明《幼薇》这类原书的子情节流程已被完整迁移。细纲验收必须额外回答：原文每个 BID 的 `先发生什么 -> 谁施压 -> 谁失手/被迫接招 -> 哪个现实权力换主 -> 哪个信息延迟 -> 场末状态如何变` 在新稿中对应哪一节、哪几句、是否缩水。若答不出来，必须先重写细纲，不得进入正文。
78.1. **换链必须先过表层距离硬闸**：`direct_imitation` 只迁移因果、信息延迟、控制权、情绪过程和文风运行方式；不得把来源地点、关键物件、金额/伤病触发、职业流程和连续动作链整体搬入后只改人物名。设定必须逐 `SF-*` 写 `换链差异矩阵`，每单元包含 `来源表层件 / 保留机制 / 新稿实现 / 更换维度 / 用户锁定复用 / 禁止回流`；新稿实现至少四拍，更换至少四类实质维度。进入细纲前由工具箱机械校验矩阵覆盖、回流和目标链长度；缺项、两个以上来源表层件回流或仅改名式改写，一律阻断。`setting-context` 阶段不得展示原文句子预览，避免模型把原场景当细纲模板。
79. **主体 BID 全集不能由回执填写者自行缩减**：`validate_outline_performance_contract.py init` 必须从每本原文同目录拆书资产中的 `写作资产/桥段施工卡.md` 自动提取 BID。第一本选中原文固定为 `primary`，其 `required_bridge_ids` 必须等于桥段施工卡全部 BID，库存和细纲对齐缺任一条都阻断；后续原文固定为 `auxiliary`，必须显式填写本稿实际选用的 `selected_bridge_ids`，所选子桥同样必须进入库存和细纲对齐。禁止通过不填写某条主体 BID、缩短 required 列表或只写“参考功能”绕过主情节迁移。
80. **正文放行不得信任规则台账自报 passed**：`validate_write_release_gate.py` 在台账 `gate_status=passed` 时仍必须重新调用 `validate_rule_execution_ledger.py` 的真实验证逻辑。skill 规则源、拆书资产、设定、细纲或已绑定正文任一 SHA 变化，旧证据原句失效，或执行汇总不一致，都必须阻断正文；禁止出现“台账单独验证失败但正文放行通过”。
81. **强情绪稿必须先过关系可懂性硬闸**：追妻、婚恋清算、白月光、替身、背叛等关系稿，细纲每节必须用不含职业术语的一句话写清 `谁和谁是什么关系 / 谁偏向谁 / 谁因此失去什么`。陌生读者需要先理解 `联排 / 吊台 / 联锁 / 权限 / 版本` 才能感到受伤，直接阻断正文。
82. **职业外壳只能承担后果，不能承担情绪**：细纲每节必须填写 `professional_shell_translation`，证明删除专业名词后，关系冲突仍成立；叙事顺序必须是 `关系伤害先被读懂 -> 职业动作把伤害做实 -> 现实后果落地`。只写“恢复版本、撤销权限、提交复核”而无法翻译成丈夫如何偏心、羞辱或放弃妻子，视为题材漂移。
83. **仿写必须迁移原文情绪流程与同级烈度**：完全参照、融合仿写或同桥仿写时，不仅迁移 BID、动作和物件，还必须逐节绑定原文真实片段，列出原文与目标稿的 `情绪进入点 -> 受辱/刺痛 -> 短暂希望或反抗 -> 反刀 -> 场末余痛`。每一拍都要写清 `具体触发 / 关系位置变化 / 读者感受 / 1-10 烈度 / 原文或细纲证据`；目标拍数、拍序、反刀拍和峰值拍必须与原文一致，强情绪稿任何一拍的目标烈度都不得低于原文。只保留功能、只保证总分、把公开抛弃降成职业分歧，直接阻断。
84. **细纲表演回执禁止模板化假通过**：连续三节及以上复用相同 `original_scene_granularity`、相同人工判断或泛化的“先施压、再接招、控制权换主”视为未真正对照原文。必须逐节写明具体原文场面、具体情绪伤害、目标等价表演和为何达到同级读者体感；验证器必须自动拦截重复模板。
85. **原文情绪不得只抽样迁移**：主体原文每个必选 BID、辅助原文每个已选 BID 都必须在 `outline_bridge_flow_parity` 中同时完成桥段流程和情绪流程对齐；逐桥记录原文/目标情绪拍、反刀拍、峰值拍、场末余痛和读者体感裁决。只挑一两个“最虐片段”对齐、其余桥段仍按功能节点平推，视为情绪资产未全量消费，禁止写正文。
86. **仿写审计必须先建立原文基线**：同桥仿写、主干仿写、融合仿写或用户要求“按原文颗粒度/流程写”时，正式判断新稿 AI 风险前必须先对主体原文运行同一套轻审计和全量审计，并用 `compare_source_baseline_audit.py` 生成原文基线对照。不得只报新稿分数，也不得把原文自身同样存在的短句、高密对白、强钩子直接判为新稿失败。
87. **仿写不追求比原文更干净**：如果原文轻审计或重审计本身为中风险，目标稿的中风险不能自动触发全文回炉；必须先判断命中是否属于原文有效爆款形状，还是新稿额外产生的流程日志、证据清单、作者总结、对白答题和安全施工稿。回修只处理 `draft_extra_ai_shell`，不得为了清零脚本命中削弱原文事件颗粒度、情绪烈度和场面短促感。
88. **原文颗粒度高于审计清零**：仿写稿完成条件是主体 BID 全集、情绪拍序、信息延迟、物件/空间/身份换主与原文同级成立，再清掉基础语句类 AI 痕迹。若一轮修改让轻审计更干净，但把公开掉位、最后期待、旧物侵占、公开反噬、现实结清等原文颗粒写弱，视为失败。
89. **基线差值必须按规则 ID 人工裁决**：`compare_source_baseline_audit.py` 的总分差只能诊断，不得单独输出正文回炉结论；必须同时查看 `heavy_rule_comparison.shared_baseline_rules` 与 `draft_extra_rules`。原文和新稿共同命中的重审计规则属于基线噪声，不得因总分差机械降分；只对新增轻审计类型或新增重审计规则按整场/段落簇检查“人物有没有偏手、对白有没有真实接招、冲突载体有没有换主、手续有没有阻力”。只有确认是新稿新增机械壳，才进入正文回修。
90. **审计回执必须区分保留项和返修项**：正式审计或回炉计划中必须把问题标为 `source_like / craft_tradeoff / draft_extra_ai_shell` 之一。`source_like` 和 `craft_tradeoff` 可以保留但要说明情节功能；`draft_extra_ai_shell` 才能进修改单。禁止把所有脚本命中统一写成“AI 味待删”。
91. **只迁移颗粒度必须使用独立模式**：用户明确要求“借原文颗粒度、自造情节”时，细纲表演验收必须使用 `source_mode: granularity_only`。该模式不要求迁移主体 BID 身份或完整桥段流程，但仍须逐节绑定原文真实场面，迁移同级事件拍密度、信息延迟、动作/物件/空间控制权变化和情绪烈度，并在 `granularity_transfer_contract` 中列出目标原创场景及明确拒绝的原文人物、职业、物件、关系和结局表层元素。禁止为了通过旧的逐桥对齐闸，把原创实验偷写成换皮复刻。
92. **正文首写必须消费逐节生成契约，不得只看事件细纲开写**：细纲表演回执的每一节必须新增 `first_draft_generation_contract`，绑定一段真实原文表演片段，写清人物入场情绪、非自主身体反应、记忆/联想/注意力漂移、矛盾冲动、说错/回避和场末余痛；同时规划哪些动作、感知和反应属于同一连续瞬间。缺失时正文放行直接阻断，禁止先写正文再补回执。
93. **第一稿直接按原文表演颗粒度成场，不得把情绪流程压成功能节点**：写每节正文前必须重新读取该节绑定的原文片段和生成契约。原文若用多拍完成“看见 -> 误认/期待 -> 身体失控 -> 旧事反噬 -> 错答/迁怒 -> 选择 -> 余痛”，目标稿必须保留同级心理流动和现场摩擦；不能只留下“看见 -> 判断 -> 决定”。迁移表演密度，不复制原句、人物、职业、物件和完整桥壳。
94. **句间关系必须在首写时成立，禁止事后批量注入虚词**：相邻句先明确时间承接、因果、转折、让步、条件、递进或心理反冲，再用符合叙述者口气的虚词、语序、重复、停顿或省略表达。连续主谓短句若读不出关系，必须当场重写成连续气口；但不得机械撒入“然而/于是/与此同时”，也不得用固定连词数量验收。
95. **人物情感不能缩成动作标签库**：`脸白 / 眼红 / 喉结动 / 指节发紧 / 我看着他 / 我没回答`只能是情绪过程中的一个局部，不得独立替代情绪。强情绪承重场首写必须出现人物对当下的具体注意、非自主反应、带偏见的理解或自我欺骗、说话失手及动作后余波中的若干项，组合由人物和原文片段决定，禁止每场套同一模板。
96. **逐节首写、逐节停检，不能等全文完成后统一润色**：每写完一节、开始下一节前，当前模型必须对照该节 `first_draft_generation_contract` 检查：是否出现电报式动作/证据/反应分段，是否缺失原文同级情感颗粒，是否只剩事件交付，是否把连接关系压没。任一成立，当前节立即整场重写；这属于正文生成步骤，不是写后去味流程。
97. **强情绪节必须消费多处原文表演证据**：不能用同一句原文摘录覆盖整节全部情绪拍。`source_emotion_sequence` 至少要引用两处承担不同功能的真实原文细节，`first_draft_generation_contract.source_performance_evidence` 也要逐条绑定真实原文；并写出目标正文的情感落点计划，证明迁移的是注意、误认、身体反应、矛盾冲动、说话失手和余痛组成的过程，不是“这一节要虐”的功能概括。
98. **相邻小节复用原文摘录必须说明不同读法**：同一原文场面确实需要跨节迁移时，后一个小节必须填写 `source_excerpt_reuse_reason`，说清本节读取的是哪一层不同情感功能。没有理由，或只是重复“参考原文颗粒度”，细纲表演验收直接失败。
99. **正文写完先做基础审计，完成后立即停靠交首稿**：全文落笔后只允许立即检查并基础回修四类硬伤：`句间关系与虚词 / 段落气口与电报文 / 人物情感过程与动作标签化 / 人物口气与明显剧情断裂`。仿写稿必须先建立母稿与对应原文切片双基线，再修改正文。通过 `first_draft_basic_review` 后必须把状态标为 `draft_preview`，第一时间向用户交付首稿并停下，不能自动继续人工分窗、原文全量审计基线、正式审计、最终台账重绑或 30 项人工语义复核。
100. **深度审计必须由用户明确放行**：只有用户看过首稿并明确要求继续审计、回炉或完成全流程后，才能记录 `deep_review_user_confirmed=true`，再进入窗口前定向回修、原文基线、人工分窗、正式审计和最终完成链。不得把用户最初的“写一本/写正文”解释为对写后深审的预授权。
101. **已有项目正文回炉默认走增量快速通道**：项目已有设定、大纲、正文和 profile，且来源文件与既有契约 SHA 未变化时，只读取当前正文、设定、大纲、profile 与本轮涉及小节绑定的原文片段；把规则同步、增量台账、顺序和契约验证合并成一次准备闸，同一 SHA 的等价检查只跑一次。逐节回炉前先固定母稿并绑定对应原文切片，逐节回炉并就地停检后，全文只做一次四项首稿基础审计，立即交稿。不得重复展开全部拆文资产、重建未变化库存、重分类未变化规则或自动进入深审；来源或结构变化时才恢复完整流程。
102. **知乎阅读排版与电报文是两个独立维度**：知乎盐言阅读版的相邻自然段、对话轮次和小节标记之间保留且只保留一个空行。是否电报文只根据连续瞬间是否被机械拆成动作、证据、反应和结论判断，禁止以取消空行来防电报文，也禁止用存在空行证明正文碎裂。
103. **知乎正文首写必须完成语义断段，不能把“换行后加空行”冒充平台排版**：每一节首写时就要按阅读拍判断段界。一个自然段通常承载一组紧密相关的叙述、感知或心理推进；当说话轮次、注意对象、情绪阶段、现实压力或控制权发生变化时，应在变化处另起一段。对白原则上按轮次独立，必要的引语动作与对白可以作为相邻配对段。不得把包含多次注意力切换的长行整体保留后只在行间加空行，也不得反向切成“一句动作一段”的电报文。`validate_zhihu_section_format.py` 通过只证明节号与空行表层合格，不能替代当前模型逐节检查语义段界。
104. **仿写正文任何写后修改都必须重新实读对应原文切片**：基础审计回修、已有正文快速回炉、窗口前定向回修和正式审计后的再次回修，全部以“本轮修改前母稿 + 待改区块对应原文精确切片”为双基线。未记录原文路径/SHA/至少两条真实证据、母稿与改后原句、颗粒保留判断时，禁止修改或放行。不得把原文短断、留白、错答、即时插嘴、动作后不解释和场末骤断整理成更完整、更规整、更会总结的句段；完整字段和失败条件统一见 `source-baseline-imitation-audit.md`。
105. **原文颗粒度必须包含场景因果颗粒，不只包含动作表演**：写细纲前必须从 `book.profile.json.causal_precondition_assets` 和对应原文切片读取人物到场原因、入场前知情边界、关键物件生命周期、制度约束、明显替代方案阻断及离场因果。每节在 `scene_logic_contract` 中完成原文到目标场的逐项迁移；只写动作顺序、站位和余波而答不出“为什么这些人此时在这里、为什么能做这件事”，直接阻断正文。
106. **跨节关键事实必须先建状态链**：`story_fact_state_ledger` 必须覆盖怀孕确认、死亡认定、婚姻/亲子身份、证据取得、关键物件生成与持有等承重事实，逐次记录 `from_state -> trigger -> to_state` 和所在小节。状态迁移必须首尾相接，禁止在“待确认”阶段提前使用“已确认”物件或结论，也禁止人物提前知道后场信息。
107. **外部制度不得替人物硬造冲突**：涉及医疗、法律、金融、行政流程时，`external_rule_dependency` 必须写明制度领域、可靠依据并由当前模型核实。无法核实的规定不得作为唯一因果，例如虚构“某栏不能为空/必须由某人签字”强迫角色做事；应改成角色主动选择、已有授权或现场可验证的现实条件，再保留其人物责任。
108. **首稿容量与文风颗粒必须在落笔前锁定**：正文放行前必须初始化并通过 `首写容量契约回执.json`。短篇目标必须在 `9000-13000` 字，细纲必须有 8-15 节；每节至少预算 800 字，并逐节写清场面完成条件、起手或翻刀、情绪升级、场末变化和来源机制。每节还必须绑定原文真实切片，分别填写 `source_style_granularity`（叙述者嘴型、句间关系、段落气口、对白错答/回避、动作与感知如何织成连续瞬间）与 `first_draft_style_plan`（本节如何迁移上述成文机制且替换原人物、原句、职业和物件）。不得把“只借事件流程、先写短稿、之后扩写”当作首稿流程；正文低于目标的 85% 时，`first_draft_basic_review` 不得通过，必须回到细纲重建后整篇首写。
109. **仿写是全量颗粒迁移，不是桥名或功能抽样**：任务被判为 `同桥仿写 / 主干仿写 / 融合仿写 / 完全参照原文` 时，主体原文的全部 `BID`、全部 `SF-*`、每条的进场状态、完整动作/反应顺序、场景因果前提、信息延迟、物件/空间/身份控制权变化、情绪拍、场末状态、人物偏手、错答/回避和原文真实文风颗粒，必须先进入 `source_bridge_flow_inventory`。主体来源禁止选择性省略、合并为功能名，或只迁移“最虐/最爽”的几段；任一 `BID` 或 `SF-*` 未被逐条裁决为 `matched / adapted`，正文放行直接失败。
110. **选中的辅助子流程必须整条消费**：辅助来源一旦在 `selected_subflow_ids` 中选中某个 `SF-*`，必须完整读取并迁移该 `SF-*` 的进场状态、连续顺序、场面颗粒、场景因果、信息延迟、控制权变化、情绪顺序、场末状态和原文文风颗粒。禁止从选中 SF 里只摘一个动作、一个物件、一个反转或一句口气；若只需要零件，不得选中该 SF，也不得把零件伪装成“辅助仿写”。
111. **文风颗粒和事件颗粒同级验收**：逐桥/逐 SF 的 `outline_bridge_flow_parity` 除桥段流程和情绪流程外，必须新增 `source_style_granularity_parity`。每项至少记录：`source_excerpt_paths / source_excerpt_sha256 / narrative_voice_and_attitude / sentence_relation_and_rhythm / paragraph_breath_and_cut_points / dialogue_misfire_or_avoidance / action-perception-emotion_weave / target_style_plan / target_outline_evidence / parity_status / manual_judgment`。原文切片必须真实逐段读取；只引用 profile、拆文报告、风格摘要或一句“保持原文颗粒度”，均视为未执行。
112. **首写逐节重读、逐节停检**：仿写正文每一节落笔前，当前模型必须重新读取该节绑定的主体原文切片和全部选中辅助 SF 对应切片；写完该节、进入下一节前，必须同时检查事件流程、情绪拍和文风颗粒是否与绑定原文同级。任何一项被压成“发生 -> 判断 -> 决定”、解释段、动作标签清单或统一 AI 句长，立即在当前节整场重写；禁止写完整篇后用扩写、润色或去味补回原文颗粒。
113. **逐 SF 文风颗粒必须在拆书 finalize 前固化**：`仿写无损编译包.json` 中每个 SF 必须包含 `source_style_granularity`，逐项覆盖叙述者态度、句间关系与节奏、段落气口与切点、对白错答/回避、动作感知情绪织法、即时插嘴与粗粝度；每项至少绑定两条位于该 SF 精确行段内的原文证据。写作读取门禁只能继承这些上游锁定字段，禁止临场用“贴脸叙述、长短句结合”等通用五条回填。
114. **仿写首稿必须从唯一入口开写，禁止人工直写绕闸**：正文落笔前必须先运行 `validate_first_draft_entry.py init`，它会实时复验 `write_release_gate draft`、初始化 `逐节首写执行回执.json`，并拒绝任何已含正文内容或数字小节的目标文件。没有 `首稿入口回执.json`，不得创建或填写 `正文.md`，也不得把人工直接写出的正文补登记为合格首稿。
115. **仿写首稿必须使用逐节执行回执**：正文不存在数字小节时由首稿入口初始化 `逐节首写执行回执.json`；每节严格执行 `open-section -> 只写当前节 -> close-section`。正文提前出现未放行节号、上一节未关闭、来源切片未绑定或四项停检未通过时立即阻断。仿写模式的 `first_draft_basic_review init` 必须同时绑定已通过的 `首稿入口回执.json` 与正文 SHA 一致的逐节执行回执，禁止批量写完后倒填。
116. **首写生成契约不得跨节套模板**：三节及以上复用相同的矛盾冲动、注意漂移、说话失手、连续瞬间分组、断段理由、句间计划、虚词策略、情绪禁例或落点计划，视为未逐节读取原文，细纲表演闸必须失败。只替换物件名、目标权力名或节号仍算同一模板。
117. **没有逐节证据链，不得声称“已按原文颗粒度首写”**：仿写任务只有同时满足以下条件，才允许在项目内或对外声称“正文首稿已经按原文颗粒度完成”：`拆文读取回执 passed（direct_imitation）`、`细纲表演验收回执 passed`、`首写容量契约回执 passed`、`首稿入口回执 passed`、`逐节首写执行回执 passed`，且每节都绑定主体原文切片与全部选中辅助 SF 切片。缺任一项，必须明确定性为“未按 skill 完整颗粒链执行的草稿/测试稿”，禁止用“已经参考原文颗粒度”或“效果上等同”代替。
118. **仿写正文必须先编译逐节原文颗粒包**：通过 `outline_performance_contract` 后、正文放行前，必须先运行 `build_section_source_bundle.py`，把每节 `source_slice_bindings / source_performance_excerpt / emotion_process / scene_logic_contract / source_emotion_parity / sentence_relation_plan` 编译成 `逐节原文颗粒包.json`。正文放行、首稿入口和 `open-section` 都只认这个颗粒包；没有颗粒包或颗粒包 SHA 失效时，不得开任何一节。
119. **默认融合仿写，原创必须显式降级**：新书初始化读取回执默认 `direct_imitation`，即主体全量 SF 加辅助已选 SF 的融合仿写；用户提出“仿写、同桥、主干参照、融合参照、完全参照原文、按原文颗粒度/文风颗粒度写”时不得改为 `standard`。只有用户明确要求完全原创且不迁移原文桥段或文风颗粒，才可显式传入 `--writing-mode standard`。旧回执缺少 `writing_mode`，或将上述任务标为 `standard`，均不得写设定、大纲或正文。
120. **细纲必须逐拍闭合节内因果，不得只验小节之间**：每节 `scene_logic_contract` 必须先写唯一 `scene_entry_state / scene_exit_state`，再用 `beat_dependency_chain` 逐拍列出人物、动作、前态、真实触发、动作前知情、空间/物件权限、后态、下一拍原因和细纲原句。第一拍必须承接入场状态，后一拍 `from_state` 必须等于前一拍 `to_state`，末拍必须落到离场状态。正文需要的掀帘、开门、拿到文件、看见腕带、走到另一地点等动作不能只存在于回执，必须在细纲原句中出现；缺任一中间动作直接阻断正文。
121. **人物知情和高风险巧合必须在细纲内显式审查**：每节至少建立一条 `knowledge_state_chain`，把承重事实的初态、逐拍获知过程、互斥状态和终态首尾接起。另须逐项裁决 `character_convergence / critical_information_delay / critical_interruption / spatial_or_object_access`：适用时必须有事前铺垫、因果解释和细纲证据；不适用时必须写具体理由。禁止让人物近距离争执很久后才看见显眼证据，禁止用身体不适、电话或第三人连续精准打断关键回答，禁止人物或物件无权限出现。
122. **相邻小节必须完成状态交接**：`section_handoff_chain` 必须覆盖每一对相邻小节，并与前节 `scene_exit_state`、后节 `scene_entry_state` 精确相等；同时交代时间经过、触发动作、人物状态、知情边界、物件持有、地点移动和未决问题。后节不能靠新巧合重启剧情，也不能把前节未取得的证据、未建立的知情或未完成的移动当成既成事实。
123. **辅助 SF 必须按拆文回执整条逐步迁移**：融合仿写初始化 `细纲表演验收回执.json` 时必须传 `--source-receipt 写作资产/拆文读取回执.json` 并绑定其 SHA。`auxiliary_subflow_flow_parity` 必须对每个已选辅助 `SF-*` 原样继承 `entry_state / required_sequence / knowledge_boundaries / object_lifecycle / exit_cause / end_state`，再按原顺序逐步映射到目标细纲，不得删步、并步或只摘事件结果。禁止用“读者新获知”“上一节已公开的信息”“已有明确持有人”“均连续”等验收套话冒充真实因果；1.4 及更早回执必须重新初始化和人工回填。
124. **完整逐节颗粒包不得降级成摘要输入**：`build_section_source_bundle.py` 必须把每个绑定行段的完整 `source_excerpt`、完整 `section_contract` 和完整 `first_draft_generation_contract` 原样编译进逐节包。`模型语义输入.json`、单个 `primary_range`、第一条 binding、五拍摘要或一段文风概括均不得替代正文输入；任一完整切片被截断或完整合同缺失时，颗粒包校验必须失败。
125. **统一工具箱只合并机械动作，不合并语义阅读**：完整流程优先使用 `story_short_write_project_toolbox.py` 的固定命令，禁止在执行中反复用 `--help` 探参数，也禁止临时生成项目专用 scaffold、回填脚本或 data 文件。工具箱可以缓存同一内容指纹下的规则/来源/台账机械复验，可以合并正文放行与首稿入口的重复校验，但不得缓存模型的本书语义判断，不得跳过逐节原文重读。
126. **逐节推进必须先展示下一节完整包，再显式开节**：第一节先 `show-section`，完整读取后把当前 `packet_sha256` 传给 `open-section`。后续使用 `advance-section` 关闭当前节并打印下一节完整原文切片与合同；下一节保持未打开，当前模型读完后再传回该 SHA 开节。禁止把“关闭当前节、未展示原文、直接打开下一节”合并成一个黑箱命令。
127. **基础回修后的 SHA 只允许有证据地机械重绑**：完成“首稿基础审计母稿 + 对应原文切片 + 改后正文”三基线记录后，才可运行 `finalize-basic-review`。该命令只能在 `revision_blocks`、原文证据、母稿证据、改后证据和人工判断全部通过后更新逐节回执与基础审计回执 SHA；禁止无证据静默重绑，也禁止重新初始化覆盖母稿。
128. **新书初始化必须原子执行**：完整流程固定先运行 `story_short_write_project_toolbox.py init-book`。该命令必须先在内存完成全部来源包校验、辅助 SF 合法性校验和融合 profile 构建，全部成功后才落写作规则回执、拆文读取回执和项目 profile。禁止把多个初始化脚本用换行、`;` 或 `&&` 临时拼接；任一门禁失败时不得留下后置 profile 或半套项目。
129. **辅助候选先查轻量总索引，入选后才读完整包**：辅助书筛选固定先运行工具箱 `candidate-subflows`，只读取 `资料库/子流程总索引.jsonl` 的紧凑候选字段。命令内部只机械核对来源索引 SHA 和无损包可用性，不把完整包内容打印进模型上下文；只输出 `source_status=ready` 的候选，缺路径、索引变化或包过期的候选会被过滤并给出简短原因，同时继续从后续候选补足请求数量。禁止在候选阶段批量展开多本 `book.profile.json`、无损编译包、拆文报告或原文；确定辅助书和 `SF-*` 后，`init-book` 再全量校验入选来源，模型随后读取回执列出的完整内容。
130. **禁止把其他已写项目当作流程模板**：新书不得读取其他书籍项目的 `任务锁定.md / 短篇全流程状态.json / 写作规则读取回执 / 拆文读取回执 / 规则台账 / 设定 / 大纲 / 正文 / 项目专用脚本` 来推导当前项目格式、参数或内容。流程合同只能来自当前 skill、固定 references、固定 scripts 和本次选中的拆文来源；其他项目只允许在用户明确要求对比时读取。
131. **持久化路径必须按文件系统身份判断**：coverage、编译包和来源回执中的绝对路径可能因宿主大小写、挂载点拼写或符号链接不同而变化。校验器必须优先用文件系统 identity 判断是否为同一目录，再校验相对文件清单和 SHA；禁止仅凭绝对路径字符串不同判定资产过期或触发重拆。
132. **长任务必须使用可持续轮询的执行会话**：预计超过 10 秒的拆文升级、finalize 或批量审计，在 Codex 宿主中固定使用持久 `exec_command` session/PTY，并通过对应轮询接口读取进度和最终退出码。禁止用裸 `command &` 后立即把临时 PID 当作可靠后台任务；若宿主不支持持久会话，必须使用能保留日志、状态文件和退出码的托管方式，并在继续主流程前确认任务真实完成。
133. **候选筛选是独立轻量阶段，禁止提前挂载重资料**：宿主已注入完整 skill 内容时视为已读，不得再次 `cat SKILL.md`。运行候选命令前只允许读取项目规范文件和工具箱固定命令段；禁止读取写作 craft、治理长文、完整 profile、无损编译包、原文、全部 learnings 或其他项目目录。不得用 `rg --files`、`find`、递归 `ls` 或同类命令枚举旧书项目；候选命令与其参数查证存在依赖关系时必须串行，禁止一边读源码一边并行猜参数。
134. **候选命令只有一个固定入口，候选失败不得自动拆书**：优先使用 `candidate-subflows --index "资料库/子流程总索引.jsonl" --query "关键词..." --exclude-source "{主体书}"`。单次最多返回 12 条，默认 8 条；禁止用 Python、`cat`、`jq` 或其他命令打印全部索引，禁止同时发起多组宽泛查询。首轮结果不足时只允许再补一次收窄查询，仍不足则由主体承担，不强塞辅助，也不得自行调用或切换到 `story-short-analyze`、`--upgrade-existing` 或任何拆书流程。用户只说“其他书籍为辅”不构成自动拆书授权；只有用户明确要求“没有合格辅助就停止写作并先补拆”时，才停止当前写作流程并报告缺口，等待用户单独启动拆书。
135. **SF 编号不是完整消费证据**：直接仿写读取回执中的每个主体 SF 和每个已选辅助 SF 都必须保留正式 `selected_subflow_contracts`，其中完整记录原文范围、事件/因果/情绪/控制权/六类文风颗粒和真实原文证据。只把 `SF-01` 等编号追加到文件级 `evidence_terms`、只写“已完整读取”或宣称“只取若干承重机制”，读取门禁必须阻断。
136. **来源读取固定走正式回执和项目侧颗粒包**：`init-book` 后固定运行工具箱 `validate-prewrite-reads`，机械复验正式 `拆文读取回执.json` 与 `仿写无损编译包.json`；随后运行 `prepare-setting` 生成并校验项目侧 `主体原文完整颗粒包.json`。禁止直接编辑 `拆文读取回执.json`，禁止用 `jq` 展开整包、手工定位 JSON 行号或大补丁批量回填。正文前的主体消费只认正式回执、项目侧主体颗粒包和后续逐节颗粒包；任一来源失配时不得继续。
137. **直接仿写首写前隔离通用句库**：`direct_imitation` 模式在来源读取门禁通过前，只允许读取三份写作硬闸规则、`direct-imitation-assets.md`、正式 `拆文读取回执.json` 和项目侧颗粒包。`opening-and-hook-library.md`、`emotion-and-outcome-library.md`、`character-voice-library.md`、`dialogue-blade-library.md`、`material-packs-*` 中的示例句、功能句和通用题材句不得进入首写提示词；只有完全原创任务或写后诊断确认原文资产缺少对应维度时，才按需读取规则说明，且不得复制示例句。
138. **辅助 SF 文风证据必须有维度区分**：六类 `source_style_granularity` 合计至少覆盖四条不同原文证据；同一证据组不得同时冒充四个及以上文风维度。辅助包达不到该厚度时，`init-book` 必须阻断并返回 `story-short-analyze finalize`，不得因为主体资料完整就带病放行。
139. **规范发现和写前读取校验只用固定命令**：当前工作区规范固定运行工具箱 `workspace-rules --root "{工作区}"`，只检查根目录的 `CLAUDE.md / CLAUDE.local.md / AGENTS.md`，禁止递归 `find ..`，也禁止用 `rg --files`、递归 `ls` 或其他目录枚举替代。规则和来源回执统一运行 `validate-prewrite-reads`，禁止在流程中使用 `--help`、`rg argparse` 或试错调用猜参数。
140. **全新项目目录必须由工具箱原子分配**：运行 `allocate-project --root "{工作区}" --name "{新书名}"`，同名目录存在时由脚本分配安全后缀并输出完整 `next_command`。禁止通过根目录 `ls/find/rg` 枚举旧项目，禁止根据目录存在或历史时间戳断言“正在并发写入”，禁止未经用户确认把项目迁移到工作区外。
141. **正文前禁止退回旧语义任务文件**：`模型语义输入.json`、`模型语义输出.json` 只能作为旧项目诊断痕迹存在，不得作为默认流程的正文输入，也不得默认打印到模型上下文。当前模型在正文前只读取正式 `拆文读取回执.json`、项目侧 `主体原文完整颗粒包.json` 和 `逐节原文颗粒包.json`。
142. **固定规则回执必须走独立语义任务和原子应用**：初始化后运行 `export-rule-review`，再循环执行 `rule-review-next -> 当前规则语义回执.json -> apply-rule-review-item`，每次只读取一个完整规则文件包；全部完成后才运行 `apply-rule-review` 汇总正式结果。禁止直接展开 `规则语义输入.json` 总任务，也禁止直接编辑 `写作规则读取回执.json`；证据词、任务 SHA、包 SHA、回执 SHA、规则集合、文件 SHA、顺序或完成度任一不符时正式回执保持不变。
143. **主 Skill 只保留入口和闸门，完整规则目录由台账机械加载**：`SKILL.md` 不再重复注入全部规则正文；`validate_rule_execution_ledger.py` 必须把本文件作为核心规则源纳入 SHA、规则族提取、预分类和最终校验。迁移只改变加载阶段，不得删除、压缩或降低任何规则。
144. **候选输出必须直接衔接目录分配和初始化**：候选命令传入 `project-root / project-name / primary-source-dir` 后必须输出 `next_allocate_command`；目录分配命令携带来源参数并输出完整 `next_command`。执行模型不得再次读取三份治理文档搜索 `init-book` 参数。
145. **工具路径必须绑定当前注入 Skill 的真实目录**：从系统注入的 `story-short-write` `SKILL.md` 路径取得父目录并设置 `SKILL_ROOT`，工具箱固定为 `$SKILL_ROOT/scripts/story_short_write_project_toolbox.py`。禁止先试 `$CODEX_HOME/skills/story-short-write`，禁止搜索其他 Skill 副本；路径不存在时只报告当前注入路径的真实错误。
146. **旧项目隔离覆盖完整流程且设定放行使用固定入口**：候选、规则读取、来源读取、台账、设定、大纲、正文和审计阶段均不得递归搜索工作区中的旧回执、旧台账、旧语义输出或旧写作产物作为模板。两份读取门禁通过后固定运行工具箱 `prepare-setting`；默认 compiled 无损包的文件级占位由脚本预分类并直接进入设定放行，不得再手写单条模型归并计划。完整写作流程不得委派给子代理，当前模型必须连续消费来源并完成设定、细纲和逐节正文。

---

## 高敏任务路由

当前任务如果属于以下任一类，必须走高敏流程：

- `同桥仿写`
- `原情节实验`
- `对标重写`
- `外部分块审计长期卡高`
- `改很多轮后越来越像施工稿`

强制流程：

1. 先判任务类型，不把高敏仿写当普通自由创作。
2. 如果已有多版稿，先选母稿，不从最新安全稿继续补丁。
3. 改前写母稿保护卡。
4. 写活稿时只挂最少限制，不让规则接管正文生成。
5. 写后先做命名式滑窗审计，再判唯一主炸点。
6. 一轮只拆一个活结，不顺手整段回炉。

这部分完整规则和自检项，统一见：

- [../story/references/short-high-risk/reference-index.md](../story/references/short-high-risk/reference-index.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

---

## profile 闭环

### 写作规则读取硬闸

写 `设定.md`、`小节大纲.md` 或 `正文.md` 前，必须先：

1. 运行 `validate_writing_rule_gate.py init`
2. 实际读取当前工作区的 `format-and-structure.md`、`anti-ai-writing.md`、`craft/narrator-voice.md`
3. 逐文件回填真实证据词、读取结论和写作用途
4. 运行 `validate_writing_rule_gate.py validate`，显式传入设定、大纲和正文路径

只有输出 `writing_rule_gate: passed` 才能继续。规则文件内容或 SHA 变化后，旧回执立即失效；不得用历史上下文、旧摘要或旧审计结果代替当前文件。

完整命令和回执字段见：

- [references/governance/writing-rule-reading-gate.md](references/governance/writing-rule-reading-gate.md)

### 拆文读取硬闸

写 `设定.md`、`小节大纲.md` 或 `正文.md` 前，必须先：

1. 先用工具箱 `candidate-subflows` 从轻量总索引筛选辅助 `SF-*`；禁止展开全部候选书完整资料
2. 将主体拆文放在第一个 `--source-dir`，辅助拆文依次追加，运行工具箱 `init-book`（默认 `--inventory-mode compiled`、`--writing-mode direct_imitation`）
3. 确认每本 `book.profile.json` 的 `source_asset_coverage` 已对全部正式资产和完整原文逐文件绑定 SHA，再实际读取回执列出的关键编译包
4. 运行工具箱 `validate-prewrite-reads`，一次校验规则读取、来源读取和设定/大纲/正文时序
5. 运行工具箱 `prepare-setting`，生成并校验项目侧 `主体原文完整颗粒包.json`
6. 后续细纲和正文只消费正式 `拆文读取回执.json`、项目侧主体颗粒包和逐节颗粒包

只有输出 `source_read_gate: passed` 才能继续。以下情况一律阻断：

- 只读项目内二手摘要、设定或大纲
- 只读 `profile_source.md`
- 只读 `book.profile.json / project.profile.json`
- `source_asset_coverage` 缺失、漏文件或任一正式资产 SHA 变化
- 主体编译包缺完整原文、BID/SF 或关键事实/因果/情绪资产
- 辅助来源未选 `SF-*`，或所选 SF 不在子流程索引中
- 正文写完后再补读取回执

缺资产必须重新执行 `story-short-analyze` 全量拆书，不做兼容回退。完整命令和回执字段见：

- [references/governance/source-reading-gate.md](references/governance/source-reading-gate.md)

### 规则执行硬闸

`writing_rule_gate` 和 `source_read_gate` 通过后、写设定或大纲前，必须：

1. 运行 `validate_rule_execution_ledger.py init`
2. 初始化时按当前 Skill 文件 SHA 自动预分类固定 Skill 规则，只固定规则角色、执行方式和阶段；预分类不得包含任何书籍项目的适用性、正文证据或参考项目结论
3. 运行 `export-model-review`；该任务只导出本书来源资产，由当前写作模型按 `case_ids / source_ref_ids` 解引用顶层注册表，逐族阅读本书全部来源，写出统一 `canonical_rule_text`
4. 模型用 `apply-model-groups` 只处理本书来源条目，并完成 canonical 规则裁决；不得重新展开 168 条固定 Skill 规则，也不得借用其他项目的规则分组
5. 确认由 `script / human / hybrid` 哪一类执行，并填写目标阶段和目标场景
6. 写作过程中执行一项标记一项，并持续补脚本产物或人工原句证据
7. 最终绑定设定、大纲、正文 SHA，再运行 `validate_rule_execution_ledger.py validate`

进入任一写作阶段前，还必须运行写作放行闸：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_write_release_gate.py" \
  setting \
  --writing-receipt 写作资产/写作规则读取回执.json \
  --source-receipt 写作资产/拆文读取回执.json \
  --ledger 写作资产/规则执行台账.json
```

正文阶段必须额外传入：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_write_release_gate.py" \
  draft \
  --writing-receipt 写作资产/写作规则读取回执.json \
  --source-receipt 写作资产/拆文读取回执.json \
  --ledger 写作资产/规则执行台账.json \
  --sequence-receipt 写作资产/顺序契约回执.json \
  --opening-contract 写作资产/开头承重契约回执.json \
  --outline-contract 写作资产/细纲表演验收回执.json \
  --draft-capacity-contract 写作资产/首写容量契约回执.json \
  --profile profiles/{项目名}.project.profile.json
```

`draft` 命令是正文前联合放行入口：它必须在同一次运行中实时复验写作规则、拆文读取、规则台账、完整顺序、开头契约和细纲表演契约。同一 SHA 下不必在命令外再分别重跑这些子门禁；联合入口的任一实时复验失败都必须整体阻断。

输出不是 `write_release_gate: passed` 时，当前模型必须停止，不能生成或修改目标产物。

设定产出后、开始写大纲前，必须先建立并人工回填设定内部顺序契约：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_sequence_contract.py" init-setting \
  --project "{项目名}" \
  --setting "设定.md" \
  --receipt "写作资产/设定顺序契约回执.json"

# 当前执行模型人工回填 canonical_sequence、设定原句 offset、
# 设定内部冲突取舍和 manual_judgment 后再运行：
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_sequence_contract.py" validate-setting \
  --receipt "写作资产/设定顺序契约回执.json" \
  --setting "设定.md"
```

只有输出 `setting_sequence_contract_gate: passed`，才能为大纲运行写作放行：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_write_release_gate.py" \
  outline \
  --writing-receipt "写作资产/写作规则读取回执.json" \
  --source-receipt "写作资产/拆文读取回执.json" \
  --ledger "写作资产/规则执行台账.json" \
  --setting-sequence-receipt "写作资产/设定顺序契约回执.json"
```

大纲写完后，用 `validate_sequence_contract.py extend-outline --setting-receipt ... --setting ... --outline ... --receipt ...` 把已通过的设定节点和证据增量继承到完整顺序契约；只新填大纲证据和设定/大纲冲突裁决，通过 `validate` 后才允许写正文。正文完成后用 `extend-draft --receipt ... --draft ...` 绑定正文，只新填正文节点和 `offset` 再校验。增量继承不代表跳过验收：上一层 SHA 或通过状态变化时必须阻断。

大纲通过完整顺序契约和开头承重契约后，还必须通过细纲表演验收。该闸门逐节检查原文机制是否真正落成场戏设计，且细纲与选中原文任一 SHA 变化都必须重新验收：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_outline_performance_contract.py" init \
  --project "{项目名}" \
  --outline "{项目目录}/小节大纲.md" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-original "拆文库/{辅助书}/原文/{辅助书}.txt" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json"

# 当前模型人工回填后：
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_outline_performance_contract.py" validate \
  --outline "{项目目录}/小节大纲.md" \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json"
```

输出不是 `outline_performance_contract: passed` 时，禁止写正文；完整口径见 [细纲表演验收硬闸](references/governance/outline-performance-contract-gate.md)。

固定分工：

- 脚本：SHA、格式、字数、频率、禁词、固定模式、字段与文件完整性；所有正文/回执/审计中的字数统一由 `count_words.py` 计算
- 人工：人物偏手、失控说话、注意力漂移、认知局限、作者代判、对白生活性
- 混合：长窗节奏、对白效率、桥段相似度、profile 覆盖

固定修复边界：

- 流程门禁失败只修读取、回执、顺序或执行记录
- 设定约束失败修 `设定.md`
- 大纲约束失败修 `小节大纲.md`
- 审计规则只负责定位和裁决
- 拆书候选按需选用，禁用规则只查污染
- 只有失败的适用正文约束进入正文修改单

普通动作、物件、对白和生活细节仍可作为候选按需选用；以下关键来源契约不允许被“候选可跳过”口径吞掉：

- `book.profile.json`
- `事实与推断台账.md`
- `写作资产/样本分级与可学层.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/桥段施工卡.md`
- `写作资产/高敏桥段识别.md`
- `写作资产/同桥段过检规则.md`
- `写作资产/仿写约束_禁写清单.md`
- `可直接仿写_顺序事件表.md`
- `可直接仿写_后果链表.md`
- `可直接仿写_外部秩序表.md`

这些文件无论按规则级展开还是保留为文件级资产，被合并后 canonical 都必须对每个 `source_ref` 分别记录 `applied / not_selected / prohibition_checked`、源文件原句、人工判断和目标证据。主体的顺序、后果、外部秩序和公开场后果资产也不能标 `not_selected`。

规则级资产父节点不要求人工再填一遍。运行 `refresh-summary`、`apply-plan` 或 `apply-model-groups` 时，脚本按子规则自动派生父节点的 `applicability / status / outcome / result`；父子状态不一致时直接阻断。

设定/大纲规则若覆盖多个目标场景，还必须把 `target_scene` 中的每一项分别写入 `structural_claim_reviews`。不能用“后果链成立”的证据同时证明开头、反转和追妻线均已通过。

额外挂载的题材规则或专项规则必须通过 `--skill-rule-file` 加进同一台账。完整字段和命令见：

- [references/governance/rule-execution-ledger.md](references/governance/rule-execution-ledger.md)

### 开头承重契约硬闸

主体拆书导语资产中的“功能顺序”和“为什么不能换序”不允许只作为普通 `outline_constraint` 留在台账中。写完大纲后、正文首写或开头回炉后，分别运行：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" init ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" validate ...
```

必须由当前模型读取主体 `可直接仿写_导语拆解表.md`、所有选中主体/辅助拆文的 `原文/` 开头样本和目标前 `120` 字，逐项填写原句证据。任一检查失败就改大纲或开头；不允许用“第一节最终有冲突”“本轮只改中后段”“已读 profile”或规则台账已通过替代本闸门。开头回炉后还必须人工确认不是分镜清单或规则施工单。

完整字段与命令见：

- [references/governance/opening-contract-gate.md](references/governance/opening-contract-gate.md)

### 必备输入

默认至少需要：

- `写作资产/profile_source.md`
- `book.profile.json`

如果上游是仿写 / 融合 / 高敏同桥，再额外要求：

- `写作资产/样本分级与可学层.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/仿写约束_禁写清单.md`
- `写作资产/同桥段过检规则.md`

如果做融合稿，还必须有：

- 多本 `book.profile.json`
- 合成后的 `project.profile.json`

缺资产时的固定动作：

- 缺拆书资产：回 `story-short-analyze`
- 缺 `profile_source.md`：先补 `profile_source.md`
- 缺 `book.profile.json`：先生成 `book.profile.json`
- 融合稿缺 `project.profile.json`：先合成融合包

### 默认闭环

默认顺序固定是：

如果命中“已有项目正文回炉快速通道”，先按规则 101 合并完成准备与基础审计，不重复执行下列完整初始化链；快速通道失效时才从第 0 步进入完整闭环。

0. 如果任务是“全面重写已有短篇目录”，先完整备份当前目录，再把旧 `设定.md`、`小节大纲.md`、`正文.md` 移入 `写作资产/旧稿归档-{时间}/`；目标产物路径必须恢复为未生成状态后，才能初始化读取回执。禁止在旧三件套仍占用目标路径时强行回填回执，否则会被事后补填闸误判或绕闸。
1. 生成写作规则读取回执
2. 读取当前版三份必读规则并通过 `writing_rule_gate`
3. 生成拆文逐文件读取清单
4. 逐文件读取全部拆文资产并回填回执
5. 通过 `source_read_gate`
6. 初始化规则执行台账，逐项确认脚本 / 人工 / 混合分工和适用性
7. 读取 `profile_source.md`
8. 读取 `book.profile.json / project.profile.json`
9. 判断 `讲法型 / 桥段链型 / 混合型`
10. 写设定，同时逐项更新台账
11. 建立并通过设定内部顺序契约
12. 通过大纲写作放行闸，再写细纲
13. 建立并通过设定—大纲完整顺序契约
14. 对大纲执行开头承重契约硬闸
15. 对大纲执行细纲表演验收硬闸；主流程仿写必须先在回执中完成 `source_bridge_flow_inventory` 和 `outline_bridge_flow_parity`
16. 逐项确认原文 BID/关键子桥段在细纲中均为 `matched/adapted`，缺失、弱化或只做功能映射时先重写细纲
17. 运行统一工具箱 `start-draft`，只做一次正文联合放行并初始化首稿入口；第一节 `show-section -> open-section`，后续每节 `advance-section -> 阅读完整包 -> open-section`，只写当前节并逐节停检
18. 正文写完立即做句、段、人物情感、人物口气与明显剧情断裂的基础审计；必要时只做一次基础回修
19. 通过 `first_draft_basic_review`，标记 `draft_preview`，第一时间交首稿并停靠等用户确认
20. 用户明确确认继续深审后，才补正文顺序节点证据、重过开头与平台格式，并按通用规则和拆书资产定向回修
21. 通过窗口前回修闸，再做原文基线、人工模型切窗、逐窗复核和正式审计
22. 生成包含人工窗口病灶汇总的回修任务单
23. 定点回炉；正文 SHA 变化后重过平台格式、顺序、开头、窗口前回修和人工切窗
24. 重新审计
25. 绑定最终写作产物并通过 `rule_execution_gate`
26. 全文人工语义复扫并通过 `post_write_human_review_gate`
27. 高风险任务再过第二闸门

这部分展开口径见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/integration/story-profile-schema.md](references/integration/story-profile-schema.md)
- [references/integration/profile-source-template.md](references/integration/profile-source-template.md)

### 回修优先级

回修顺序固定为，不得把后面规则反向覆盖前面规则：

1. 成文真实感：任何规则都不能把正文修成规则施工稿、验收单、提示词执行结果。
2. 题面 / 题材承诺 / 主卖点：追妻、婚恋清算、强情绪关系文不得被修成职业流程文或冷处理说明文。
3. 主桥和后果链：顺序、代价、失位、求回、女主边界必须先成立。
4. 冲突载体：每场先确认在争夺什么现实权力、位置或后果，再修句面。
5. 人物交流：一方施压后，另一方的动作、站位、物件控制权、回答范围、身份或后果必须发生可见变化。
6. 灵动感和现场毛边：补冲突、补交流、补证据时必须保留临场偏差、错答、回避、手忙脚乱或生活毛边，不能变随机废话。
7. 流程硬化 / 分镜施工稿：这是负向校验，不是删内容指令；应把白板、钥匙、确认框、回执等冲突载体写进人物反应和现场阻力里。
8. `global_risk_shape` 是整篇、粗块还是局部热点。
9. 最后才处理句壳、短段节奏和显性候选词。

每轮回修前必须声明：

- `primary_revision_rule`：本轮主修规则，例如 `procedural_stiffness_review`、`interaction_exchange_review`。
- `protected_rules`：本轮不得破坏的旧规则，至少覆盖题材承诺、冲突载体、人物交流、灵动感、全文分镜/施工稿。
- `risk_of_rule_collision`：说明本轮可能把哪些旧修改修坏。

每轮回修后必须人工复核：

- 主修规则是否真的改善。
- 保护规则是否被破坏。
- 如果新修改让旧规则失败，本轮不能标 passed；必须先回滚冲突句，或做二次修复并重新复核。
- 报告中必须列出 `主修规则 / 保护规则 / 冲突裁决 / 保留或二次修复理由`，不能只写“已检查”。

禁止：

- 只因全文均分下降就停
- 只因轻审计命中变少就停
- 跳过桥段承重件和顺序，直接润句
- 用一个规则的检测结果机械覆盖另一个更高优先级规则
- 为了去流程硬化删掉冲突载体、人物交流或追妻情绪
- 为了补交流/补冲突堆动作，导致全文变成分镜清单或规则施工稿

### 脚本入口

常用入口只保留下面 10 个：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_zhihu_section_format.py" --text "{项目目录}/正文.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/count_words.py" "{项目目录}/正文.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_full_ai_audit.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/auto_revise_ai_flavor.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_revision_cycle.py" 当前短篇目录
```

题材首次校准才用：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/compare_with_external_block_audit.py" ...
```

详细调用、产物、停机口径见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)

---

## 格式规范

格式细则统一见：

- [references/workflow/format-and-structure.md](references/workflow/format-and-structure.md)

主文件只保留硬口径：

- 工作稿正文只放在 `正文.md`
- 投稿版和工作稿必须分离
- 知乎 / 盐言正文只用 `1.`、`2.` 纯数字分节；大纲小节名不得带入正文
- 正文分段服从阅读节奏，不服从审计切块
- 不允许把正文写成“一句一段”的碎句施工稿
- 也不允许把多个动作、信息、对白回合糊成一整块墙文
- 自检记录必须写到独立文件，不能污染正文

---

## 核心方法

### 3 个硬闸

#### 开头硬闸

通用最低要求是前 60 到 100 字至少完成 `关系定位 / 冲突起事 / 后果预期` 中的两项；存在主体拆书时，还必须通过开头承重契约，主体资产明确规定的顺序不得用通用最低要求覆盖。开头不是越短越好，压缩后若变成“一行一个镜头 / 一行一个证据 / 一行一个反应”的分镜稿，仍视为失败，必须改成连续现场叙述。

#### 高潮硬闸

高潮至少做到下面 3 条里的 2 条：

- 放出前文一直压着的东西
- 炸在最该公开的场面
- 炸完后让前文意义变狠

#### 回炉硬闸

回炉时必须先看：

1. 题面
2. 骨架
3. 开头与高潮
4. 风险形状
5. 情绪和关系
6. 句子

高风险任务还要再加：

7. `受限重写防错协议`
8. `失败即重写判定`

### 最短自检顺序

时间紧时，至少扫这 5 条：

1. 开头第一屏有没有起事
2. 中段有没有持续变坏或持续掉位
3. 高潮是不是炸在最该公开的地方
4. 人物一开口能不能分出来
5. 结尾是不是留下后果，而不是只做总结

这 5 条里有 2 条答不上来，不做精修，先回结构层。

### 默认挂载包

所有模式默认先挂：

- [references/workflow/format-and-structure.md](references/workflow/format-and-structure.md)
- [references/anti-ai-writing.md](references/anti-ai-writing.md)
- [references/craft/narrator-voice.md](references/craft/narrator-voice.md)

完全原创或无来源资产任务，再按需挂：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/material-packs-setting-plot.md](references/craft/material-packs-setting-plot.md)
- [references/craft/opening-and-hook-library.md](references/craft/opening-and-hook-library.md)
- [references/craft/emotion-and-outcome-library.md](references/craft/emotion-and-outcome-library.md)
- [references/craft/character-voice-library.md](references/craft/character-voice-library.md)

写后诊断确认对白或台词存在问题时，才额外挂：

- [references/craft/humanize-and-dialogue.md](references/craft/humanize-and-dialogue.md)
- [references/craft/dialogue-blade-library.md](references/craft/dialogue-blade-library.md)

做仿写 / 融合 / 高敏同桥时，来源回执通过前只额外挂：

- [references/craft/direct-imitation-assets.md](references/craft/direct-imitation-assets.md)

高敏回修手册只在细纲或写后审计确认高敏时读取，不进入首写提示词：

- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)

---

## 写作流程

### Phase 1：起盘

先定：

1. 平台
2. 主卖点
3. 故事怎么走
4. 最显眼的矛盾
5. 中段再加的那层事
6. 高潮场合
7. 结尾落点

如果用户只有模糊想法，不直接开梗概，先补：

- 读者最想看的后果
- 主情绪
- 爽点类型
- 关系重组方式
- 题材壳
- 禁止漂移方向

起盘完成后，必须在设定里明确落盘以下五项，后续每轮回修不得偷换：

- `题材壳`
- `主卖点`
- `核心情绪`
- `付费期待`
- `禁止漂移方向`

起盘、题面、导语、平台适配的详细方法见：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/opening-and-hook-library.md](references/craft/opening-and-hook-library.md)

### Phase 2：细纲

先写 `小节大纲.md`，再碰正文。

细纲阶段必须完成：

- 每场主任务
- 主桥顺序
- 承重物件
- 情绪升级点
- 钩子
- 伏笔回查
- 每节同时绑定拆书资料里的功能机制和原文对应桥段的场面颗粒度
- 从 `causal_precondition_assets` 和原文对应位置逐节迁移到场原因、知情边界、物件生命周期、制度约束、替代方案阻断与离场因果
- 建立跨节 `story_fact_state_ledger`，先消除关键事实的不兼容状态，再允许写正文
- 每节写成连续表演型场面，不把验收回执字段复制进细纲正文

如果是仿写 / 融合，先读基础资产，再写新纲。最低准入和读取顺序见：

- [references/craft/direct-imitation-assets.md](references/craft/direct-imitation-assets.md)

大纲与结构物件的详细模板见：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/writing-craft.md](references/craft/writing-craft.md)

### Phase 3：正文

正文按场景写，不按说明文写。

每场落笔前先回答：

1. 这一场主情绪是什么
2. 这一场主任务是什么
3. 谁在压谁
4. 这一场结尾要留下什么后果或问号
5. 原文对应场面里，人物情绪经过了哪些可见和不可见的中间拍
6. 本场哪些动作、感知、反应属于同一连续瞬间，不能拆成电报式短段
7. 相邻句靠什么关系连起来：时间、因果、转折、让步、递进，还是人物心理反冲

正文硬口径：

- 先写动作、物件归属、秩序变化，再写判断
- 对白必须带角色口气，不准所有人同脸
- 情绪要落在身体反应、动作选择、说话方式上
- 情绪还要有过程：注意偏移、非自主反应、记忆反噬、自我欺骗、错答和余痛不能全被压掉
- 长短句随人物呼吸和现场压力变化；同一动作链、视线链、情绪反应链优先写成连续段落
- 不设“一句一段”比例，不按单段字数机械切段；断段必须来自注意对象、权力位置、说话人或时间状态真实变化
- 先建立句间关系，再自然使用虚词或语序承接；禁止全是裸露的“主语 + 动作”短句，也禁止事后批量补连词
- 允许人物失手、岔开、找补、说半句
- 不要把“去味”写成“全改成概述和转述”
- 不要为了显得稳，把所有高风险位置都改成解释更全、逻辑更直、主题更明白的安全块
- 不要把“句子更工整”误当成“场面更成立”；一场先看谁压谁、谁失手、谁掉位，再看句面
- 如果一段改完更像“总结他为什么难过 / 她为什么后悔 / 他们关系到底是什么”，默认在变假

写作阶段详细口径见：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/humanize-and-dialogue.md](references/craft/humanize-and-dialogue.md)
- [references/craft/character-voice-library.md](references/craft/character-voice-library.md)

### Phase 4：审计与回炉

先内部审计，再决定改什么。

内部审计只负责脚本预扫和风险定位，不得凭“零命中”直接宣布作者站位、人物动机或叙述者声音已经通过。

至少同时看：

- `light_audit`
- `heavy_audit`
- `bridge_audit`
- `style_assets_audit`
- `rulebook_audit`
- `shape_audit`
- `sample_grading_guard`

高风险回修时，必须再过：

1. `受限重写防错协议`
2. `失败即重写判定`

正文最终修改完成后，先绑定最终产物并通过规则执行硬闸：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" validate \
  --ledger "{项目目录}/写作资产/规则执行台账.json"
```

最终绑定后必须人工核对台账是否仍含旧产物证据：

- 全文搜索台账里的 `quote` 是否仍指向旧正文、旧设定或旧大纲句子。
- 递归检查 canonical 规则及其合并成员，不能只改顶层 `asset_rules` 或一条代表规则。
- 对每条带关键来源 `source_refs` 的规则，按实际 `source_refs` 重建 `source_contract_reviews`；不得保留上一轮无关来源，也不得缺少主体 / 辅助来源。
- `source_contract_reviews.target_evidence` 必须引用当前最终产物原句；源文件证据用 `source_quote`，目标产物证据用 `target_evidence`，两者不能混填。
- 发现旧 SHA 或旧句子时，当前轮只能报告“规则台账未闭环”，禁止宣称流程完成。

同时重新校验正文开头承重契约；正文或主体导语资产 SHA 变化后旧回执无效：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" validate \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md"
```

知乎 / 盐言正文还必须通过纯数字分节格式硬闸；每次回修后都要重跑：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_zhihu_section_format.py" \
  --text "{项目目录}/正文.md"
```

再生成局部生硬候选报告：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/audit_local_stiffness.py" \
  --text "{项目目录}/正文.md" \
  --output "{项目目录}/写作资产/局部生硬候选报告.json"
```

报告中的 `script` 项可由脚本定位，`mixed` 项只能由当前模型结合上下文裁决。无命中不等于通过，仍须人工复扫 `直白心理 / 情绪后总结 / 结果汇报链 / 论点型对白 / 机械章尾 / 克制解释过度 / 高价值场景摘要化 / 全文分镜清单或规则施工稿` 八类问题。

再过人工语义硬闸：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_post_write_human_review_gate.py" validate \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json" \
  --text "{项目目录}/正文.md" \
  --sequence-receipt "{项目目录}/写作资产/顺序契约回执.json"
```

人工回填 `写后人工语义复核回执.json` 时，除通用 `human_checks` 外必须完成 `genre_formula_review`：

- `selected_genre`：当前实际采用的题材公式
- `source_files`：公式文件绝对路径与 SHA256
- `rules`：本稿适用规则逐项证据
- `conclusion`：题材公式是否全部落实到最终正文

追妻题至少包含 `female_softening_externalized`、`female_softening_trigger_relevance`、`irreversible_exit_timing`、`no_emotional_after_summary`、`repair_failure_fact_based`。任一证据仍应 `revise / delete` 时，先改正文，再重新初始化和复核回执。

局部或专项回炉初始化回执时必须传 `--base-text`。完整字段和自动/人工分工见：

- [references/governance/rule-execution-ledger.md](references/governance/rule-execution-ledger.md)
- [references/governance/post-write-human-review-gate.md](references/governance/post-write-human-review-gate.md)

审计和回炉细则见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [references/governance/global-humanity-audit.md](references/governance/global-humanity-audit.md)
- [references/governance/no-external-block-audit-self-check.md](references/governance/no-external-block-audit-self-check.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

判失败时额外补看：

- 这一版是不是更像“会过闸门的成熟块”，但不像“事情被逼到这一步”
- 这一版是不是把人物写得更会解释、更会认错、更会总结
- 这一版是不是把后果写成了说明，而不是继续留在动作、场面、身体感和秩序变化里

---

## 流程衔接

| 时机 | 跳转到 | 命令 |
|---|---|---|
| 有参考小说要拆 | `story-short-analyze` | `/story-short-analyze` |
| 成稿去味 | `story-deslop` | `/story-deslop` |
| 需要市场方向 | `story-short-scan` | `/story-short-scan` |
| 设定明显更适合长篇 | `story-long-write` | `/story-long-write` |

---

## 参考资料

主流程常用：

- [references/workflow/reference-index.md](references/workflow/reference-index.md)
- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/workflow/format-and-structure.md](references/workflow/format-and-structure.md)
- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/governance/rule-execution-ledger.md](references/governance/rule-execution-ledger.md)
- [references/governance/skill-boundaries.md](references/governance/skill-boundaries.md)
- [../story/references/reference-layer-map.md](../story/references/reference-layer-map.md)

起盘与结构：

- [references/craft/material-packs-setting-plot.md](references/craft/material-packs-setting-plot.md)
- [references/craft/short-story-material-bank.md](references/craft/short-story-material-bank.md)
- [references/craft/opening-and-hook-library.md](references/craft/opening-and-hook-library.md)
- [references/craft/writing-craft.md](references/craft/writing-craft.md)
- [references/craft/reversal-toolkit.md](references/craft/reversal-toolkit.md)

情绪与人物：

- [references/craft/emotion-and-outcome-library.md](references/craft/emotion-and-outcome-library.md)
- [references/craft/character-voice-library.md](references/craft/character-voice-library.md)
- [references/craft/material-packs-character.md](references/craft/material-packs-character.md)
- [references/craft/humanize-and-dialogue.md](references/craft/humanize-and-dialogue.md)
- [references/craft/dialogue-blade-library.md](references/craft/dialogue-blade-library.md)

仿写与高敏回修：

- [references/craft/direct-imitation-assets.md](references/craft/direct-imitation-assets.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [references/governance/no-external-block-audit-self-check.md](references/governance/no-external-block-audit-self-check.md)
- [../story/references/high-risk-gates/reference-index.md](../story/references/high-risk-gates/reference-index.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

脚本与规则：

- [references/integration/internal-toolchain-map.md](references/integration/internal-toolchain-map.md)
- [references/integration/myconfig-rule-integration.md](references/integration/myconfig-rule-integration.md)
- [references/integration/story-profile-schema.md](references/integration/story-profile-schema.md)
- [references/governance/audit-rulebook-coverage.md](references/governance/audit-rulebook-coverage.md)

---

## 语言

- 跟随用户语言回复
- 中文回复遵循《中文文案排版指北》
