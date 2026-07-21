---
name: story-short-write
description: |
  短篇网文写作。辅助短篇小说创作，从起盘、搭骨架到正文和回炉，重点抓冲突、情绪、高潮和值得付费的后果。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」
metadata:
  version: 1.7.0
---

# story-short-write：短篇网文写作

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
- `validate_post_write_human_review_gate.py`
- `generate_story_profile.py`
- `run_full_ai_audit.py`
- `validate_pre_window_revision_gate.py`
- `audit_novel_ai_flavor.py`
- `auto_revise_ai_flavor.py`
- `run_revision_cycle.py`
- `precheck_rewrite_gate.py`
- `validate_gate_receipts.py`
- `compare_with_external_block_audit.py`

工具链地图和规则接入说明见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
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
10. 写大纲和正文前必须通过 `validate_source_read_gate.py`；只读设定、大纲、`profile_source.md` 或 profile 都不算读过拆文资料。
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
29. skill 核心规则和拆书资产先由脚本按小节/资产文件压成规则卡；当前写作模型必须阅读全部 `cases`，归纳一条 `canonical_rule_text`，再区分 `workflow / format / setting / outline / draft / audit / source candidate / source prohibition`；关键词建议不能直接确认分类。
30. 所有拆书文件必须逐文件判断，16 表及承重资产按同类型规则族执行；拆书候选未选中应标 `not_applicable`，禁用规则未命中用全文复核证明，不能把表格每行都膨胀成强制正文规则。
31. 写作过程中执行一项标记一项；最终正文绑定后必须通过 `validate_rule_execution_ledger.py`，不得写完后批量伪造“已使用”记录。
32. 完全重复规则初始化时自动合并，语义近似规则人工归入 canonical；只有失败的适用 `draft_constraint` 可以设置 `requires_text_change: true` 并进入正文修改单。
33. 写后长窗审计必须先导出人工模型分段任务，由当前执行 skill 的模型完整读取正文并回填分段回执；禁止脚本调用外部 API、Claude CLI 或其他模型。正文 SHA 变化后旧分段回执立即失效；无回执的算法滑窗只能算预扫。
34. 主体拆书的 `可直接仿写_导语拆解表.md` 必须单独生成开头承重契约；大纲和正文各过一次。前 `20 / 60 / 80 / 120` 字的关系锚、异常站位、题面兑现、读者问题、说明抢跑和功能顺序任一失败都直接阻断，不能并入普通规则卡后降级为 warning。
35. profile、事实台账、样本分级、作者 DNA、桥段施工、高敏识别、同桥过检、禁写清单、顺序/后果/外部秩序表即使并入 canonical，也必须逐来源填写 `source_contract_reviews`；主体治理资产不得标 `not_selected`。规则级文件父节点由子规则自动汇总，手填状态与子规则不一致时阻断。
36. `setting_constraint / outline_constraint` 如果在 `target_scene` 同时宣称多个目标通过，必须逐目标填写 `structural_claim_reviews`；开头、反转、后果等任一目标没有对应产物原句时，不得整体判过。
37. 警告必须按语义分级：已识别的高风险桥段未进入前排回修任务、强制资产缺失、承重顺序错乱属于硬失败；统计波动、短段偏多和局部频率异常只作诊断，不得反向驱动机械改文。
38. **设定—大纲—正文顺序必须单独过顺序契约硬闸**：设定内部、设定与大纲、正文与 canonical sequence 任一冲突都阻断；“已读设定”“台账 passed”或“开头契约 passed”不能替代顺序契约。
39. **写作放行是单独的硬闸，不得绕过或事后补票**：生成设定、大纲或正文前，必须运行 `validate_write_release_gate.py`。设定写完、开始写大纲前必须先通过 `validate_sequence_contract.py validate-setting`；大纲阶段必须传入通过的设定内部顺序回执；正文阶段必须传入通过的完整顺序契约回执。任一前置门禁不是 `passed`，立即停止当前阶段。
40. **未通过写作放行闸时，禁止创建或修改目标产物**：不能因为“先写一版再修”“先生成正文测试流程”或“台账只是记录问题”而继续；必须先修门禁、回执、来源契约或台账，再重新运行放行闸。
41. **完整流程不是部分检查相加**：只通过人工复核门、预检、AI 味脚本或算法长窗中的一部分，不得宣称流程完成；必须同时满足写前放行、顺序契约、规则台账、开头契约、正文人工复核和正式长窗审计。
42. **算法窗口永远不能代替人工窗口**：未完成当前模型人工分段回执时，`run_full_ai_audit.py` 只能作为算法预扫；回执为 `pending`、缺失或正文 SHA 不一致时，禁止结束写作任务。
43. **正文完成条件必须全部满足**：人工模型分段回执为 `completed`、正文 SHA/字符数/边界一致、正式全量审计绑定并通过完整顺序契约、每个窗口完成顺序节点结构复核、正式全量审计使用该回执、`rhythm_distribution_audit` 已逐窗人工复核、`validate_post_write_human_review_gate.py` 和 `validate_rule_execution_ledger.py` 均输出 `passed`。缺任何一项，只能报告“未完成”。
44. **人工窗口前必须先做通用规则/拆书资产定向回修**：正文初稿或上一轮正文完成后，先按当前 skill canonical 规则和主体拆书资产执行一轮正文回修，并通过 `validate_pre_window_revision_gate.py`；未通过时不得导出人工分段任务，也不得把窗口检测当作当前轮正式审计。
45. **窗口检测只负责定位剩余问题**：窗口风险标签、对白比例、气口和重复统计只能作为定位证据；每窗必须由当前模型人工判断具体病因和“保留/局部回修/整块回炉”，并逐节点核对顺序契约；不能把脚本标签直接等同于正文缺陷。
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
57. **追妻题三项句段级检查为强制项**：`female_softening_externalized` 检查女主的一秒松动是否由动作、停顿或外部细节折射；`no_emotional_after_summary` 检查情绪破绽后是否又补作者总结；`repair_failure_fact_based` 检查补救失败是否落在再次选择和具体事实上。缺任一项，写后人工复核不得通过。
58. **题材公式专项回执同时绑定最终正文和公式来源**：正文 SHA 或题材公式来源 SHA 任一变化，旧回执立即失效；必须在最后一次正文修改后重新逐条复核。不能因为本轮只改一句，就沿用上一轮“已检查”的题材结论。
59. **写后必须执行局部生硬候选扫描，但脚本不得代判**：运行 `audit_local_stiffness.py` 定位 `直白心理 / 情绪后总结 / 结果汇报链 / 论点型对白 / 机械章尾钩子 / 克制解释过度 / 高价值场景摘要化`。脚本命中只算候选；当前模型必须完整读取上下文，逐项判断 `保留 / 回修 / 删除`。
60. **人工复核必须做全文反例扫描，不能只找一条合格证据**：`direct_psychology_externalization`、`post_emotion_summary_residue`、`result_reporting_chain`、`thesis_dialogue_concreteness`、`chapter_end_hook_naturalness`、`restraint_overexplained`、`high_value_scene_summary_compression` 七项必须进入 `human_checks`。每项应证明全文剩余候选均已裁决；只引用一处合格句、未处理同类反例，视为未执行。
61. **通过状态不得包含待改证据**：任何人工检查证据的 `action` 只要是 `revise / delete`，该项就不能标记 `passed`；必须先修改正文、重建绑定最终 SHA 的回执，再重新检查。禁止把“已发现问题”冒充“已通过检查”。
62. **克制不能由连续否定句自证**：同一小段连续出现三次以上 `我没有 / 我不知道 / 我没问 / 这件事我后来也没`，必须进入 `restraint_overexplained`；优先删除解释，让前面的物件和动作自己承担克制。不能为了表现冷静，把“不做什么”逐项讲给读者。
63. **高价值桥段禁止被转述摘要吞掉**：追妻低位、公开掉位、揭示、决裂、求回等承重场景若出现 `他先说……又说……` 一类复合转述，必须进入 `high_value_scene_summary_compression`；当前模型要判断是否恢复为现场对白、动作和停顿。普通过场可保留转述，承重场景默认现场化。

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

1. 对每本选中的主体 / 辅助拆文运行 `validate_source_read_gate.py init`
2. 实际逐文件读取回执列出的全部拆文资产
3. 回填证据词、读取结论和写作用途
4. 运行 `validate_source_read_gate.py validate`，显式传入设定、大纲和正文路径做时序检查

只有输出 `source_read_gate: passed` 才能继续。以下情况一律阻断：

- 只读项目内二手摘要、设定或大纲
- 只读 `profile_source.md`
- 只读 `book.profile.json / project.profile.json`
- 拆文目录缺主报告、16 表、8 库、写作资产或动态字典
- 正文写完后再补读取回执

缺资产必须重新执行 `story-short-analyze` 全量拆书，不做兼容回退。完整命令和回执字段见：

- [references/governance/source-reading-gate.md](references/governance/source-reading-gate.md)

### 规则执行硬闸

`writing_rule_gate` 和 `source_read_gate` 通过后、写设定或大纲前，必须：

1. 运行 `validate_rule_execution_ledger.py init`
2. 运行 `export-model-review`，由当前写作模型逐族阅读全部 `cases`，写出统一 `canonical_rule_text`
3. 模型用 `apply-model-groups` 把执行动作相同的条目压成“一条规则 + 多案例”，并确认规则角色、修复目标和适用性
4. 确认由 `script / human / hybrid` 哪一类执行，并填写目标阶段和目标场景
5. 写作过程中执行一项标记一项，并持续补脚本产物或人工原句证据
6. 最终绑定设定、大纲、正文 SHA，再运行 `validate_rule_execution_ledger.py validate`

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
  --profile profiles/{项目名}.project.profile.json
```

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

大纲写完后，必须重新初始化完整顺序契约，人工核对设定与大纲的 canonical 顺序后，才允许写正文；正文节点和 `offset` 必须在正文生成后补齐并重新校验。不得把“设定顺序回执已通过”当成正文顺序已通过。

固定分工：

- 脚本：SHA、格式、字数、频率、禁词、固定模式、字段与文件完整性
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

必须由当前模型读取主体 `可直接仿写_导语拆解表.md` 和目标前 `120` 字，逐项填写原句证据。任一检查失败就改大纲或开头；不允许用“第一节最终有冲突”“本轮只改中后段”或规则台账已通过替代本闸门。

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
15. 通过正文写作放行闸，再写正文并逐项更新台账
16. 补正文顺序节点证据并重新通过完整顺序契约
17. 对正文执行开头承重契约硬闸
18. 按通用规则和拆书资产定向回修
19. 通过窗口前回修闸，再做人工模型切窗和正式审计
20. 生成回修任务单
21. 定点回炉；正文 SHA 变化后重过顺序、开头、窗口前回修和人工切窗
22. 重新审计
23. 绑定最终写作产物并通过 `rule_execution_gate`
24. 全文人工语义复扫并通过 `post_write_human_review_gate`
25. 高风险任务再过第二闸门

这部分展开口径见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/integration/story-profile-schema.md](references/integration/story-profile-schema.md)
- [references/integration/profile-source-template.md](references/integration/profile-source-template.md)

### 回修优先级

回修顺序固定为：

1. 题面是否成立
2. 主桥和后果链是否成立
3. 开头和高潮是否过闸
4. `global_risk_shape` 是整篇、粗块还是局部热点
5. 人物关系和情绪是否在走
6. 最后才修句子

禁止：

- 只因全文均分下降就停
- 只因轻审计命中变少就停
- 跳过桥段承重件和顺序，直接润句

### 脚本入口

常用入口只保留下面 8 个：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_source_read_gate.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" ...
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
- 正文分段服从阅读节奏，不服从审计切块
- 不允许把正文写成“一句一段”的碎句施工稿
- 也不允许把多个动作、信息、对白回合糊成一整块墙文
- 自检记录必须写到独立文件，不能污染正文

---

## 核心方法

### 3 个硬闸

#### 开头硬闸

通用最低要求是前 60 到 100 字至少完成 `关系定位 / 冲突起事 / 后果预期` 中的两项；存在主体拆书时，还必须通过开头承重契约，主体资产明确规定的顺序不得用通用最低要求覆盖。

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

起盘和正文默认先挂：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/workflow/format-and-structure.md](references/workflow/format-and-structure.md)
- [references/anti-ai-writing.md](references/anti-ai-writing.md)
- [references/craft/narrator-voice.md](references/craft/narrator-voice.md)
- [references/craft/material-packs-setting-plot.md](references/craft/material-packs-setting-plot.md)
- [references/craft/opening-and-hook-library.md](references/craft/opening-and-hook-library.md)
- [references/craft/emotion-and-outcome-library.md](references/craft/emotion-and-outcome-library.md)
- [references/craft/character-voice-library.md](references/craft/character-voice-library.md)

写对白、修台词、去生硬人话时，额外挂：

- [references/craft/humanize-and-dialogue.md](references/craft/humanize-and-dialogue.md)
- [references/craft/dialogue-blade-library.md](references/craft/dialogue-blade-library.md)

做仿写 / 融合 / 高敏同桥时，额外挂：

- [references/craft/direct-imitation-assets.md](references/craft/direct-imitation-assets.md)
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

正文硬口径：

- 先写动作、物件归属、秩序变化，再写判断
- 对白必须带角色口气，不准所有人同脸
- 情绪要落在身体反应、动作选择、说话方式上
- 长短句交错，别整页等长短句密排
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

同时重新校验正文开头承重契约；正文或主体导语资产 SHA 变化后旧回执无效：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" validate \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md"
```

再生成局部生硬候选报告：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/audit_local_stiffness.py" \
  --text "{项目目录}/正文.md" \
  --output "{项目目录}/写作资产/局部生硬候选报告.json"
```

报告中的 `script` 项可由脚本定位，`mixed` 项只能由当前模型结合上下文裁决。无命中不等于通过，仍须人工复扫 `直白心理 / 情绪后总结 / 结果汇报链 / 论点型对白 / 机械章尾 / 克制解释过度 / 高价值场景摘要化` 七类问题。

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

追妻题至少包含 `female_softening_externalized`、`no_emotional_after_summary`、`repair_failure_fact_based`。任一证据仍应 `revise / delete` 时，先改正文，再重新初始化和复核回执。

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
