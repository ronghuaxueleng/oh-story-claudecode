# 全文文字颗粒度合同

本合同只处理成文语言，不处理剧情桥段。`场面颗粒度` 与 `文字颗粒度` 必须分开：

- 场面颗粒度回答谁先动、物件如何换主、情绪怎样升级。
- 文字颗粒度回答原文怎样选词、组句、断段、接话、插嘴和保留有效毛边。

本合同按 [主体原文主导首稿](source-dominant-first-draft.md) 执行。首稿不运行去 AI 味；所谓 `extra_ai_shell` 只指目标稿新增且明显偏离主体原文的句面壳，不能用来删除主体原文式直接情绪、粗粝判断和失控气口。

## 长句与自然换气

段落气口同时检查句内节点和段间换气。一个句子若连续承载多个独立动作、证据、后果或视线转移，应在自然信息落点拆句或断段；尤其要逐句检查 `物件出现 -> 回忆/旧画面 -> 当下处置`、`证据出现 -> 人物反应 -> 现实后果`、`人物动作 -> 旁观者反应 -> 秩序变化` 三类多拍结构。同一身体动作链、感官链、话轮链可保留长句，但要在人工复核中说明连续性。禁止把“连续现场”误读成一行塞满，也禁止为消除长句改成“一句一个动作”的分镜清单。

## 主体声线独占

- 第一本选中原文固定为唯一 `primary_prose_source`。
- 辅助原文可以供应事件、桥段、物件和情绪机制，不得混入正文声线。
- 融合仿写也只能有一个文字声线主体；用户未指定时沿用第一本主体原文。
- 功能相同、情绪同级或桥段对齐，不能证明文字颗粒度对齐。

## 写前基线

正文放行前初始化 `写作资产/全文文字颗粒度契约回执.json`，由当前模型人工填写：

1. 至少 5 组四十字以上的主体原文连续片段，覆盖开口、日常叙述、高压冲突、对白和收口等至少 4 类场景。
2. 七个维度：句子运动、词语口语度、叙述者声音、段落气口、对白衔接、情绪落字、有效毛边。
3. 每个维度至少 2 条主体原文证据，同时写清迁移规则和必须拒绝的 GPT 默认壳。
4. 至少 3 条“明显不像主体原文”的句面反例。
5. 至少 3 组“主体连续原文 + 原创试写 + 人工句面对照”校准样本。

不得把原文拆成几个漂亮金句充当连续气口，不得用“冲突更快、信息更密、钩子更强”替代句面判断。

上述七维合同是书级声线摘要，不是最细执行单位。v2.5 回执还必须完成 [ultra-fine-prose-granularity.md](ultra-fine-prose-granularity.md) 的 52 项特征库、5 组 80 字以上连续片段逐句全标注和分布解释。连续片段中的每一句都必须进入 `sentence_annotations`，不得抽样。52 项是方法库存，不是出现次数配额；每个实际标注的特征都必须用 `feature_evidence` 绑定当前源句内证据，禁止按序号轮转或强制每项出现一次。

统计与句法特征完整仍不能证明正文有生命力。写前还必须按 [prose-liveliness-layer.md](prose-liveliness-layer.md) 建立 `prose_liveliness_layer`：从主体原文全文提取七类成文活性资产，每类至少 3 条，并落盘 `写作资产/成文活性层资产.md`。辅助书不得供应这层文字。

活句仍不能证明人物有性格。写前还必须按 [character-personality-granularity.md](character-personality-granularity.md) 建立 `character_personality_layer`：从主体原文提取七类人物偏手，为至少主角与一名核心关系人建立不可互换母版，并把逐节人物计划写入 `section_generation_plans[].character_plan`。

细纲定稿后、正文放行前必须先执行 `bind-outline`。当前模型随后逐节填写 `section_generation_plans`。生成主驱动固定为连续原文句链，不是规则标签：

- `generation_driver=continuous_source_chain`。
- `single_sentence_features_secondary=true`，52 项标签和单句机制只作辅助核对。
- `continuous_source_chain_packets` 至少两组；每组 `source_excerpt` 必须是主体原文中连续出现的 `60` 字以上、至少三句，并完整保留 `source_sentence_chain` 原顺序。
- 每组必须分别写清 `chain_motion / target_scene_use / target_sentence_relation / explanation_to_omit`，说明原文如何从异常、追问、错答、插嘴或动作变化连续推进，以及目标场景应在哪一步停住、不补哪类解释。
- `contrastive_examples` 至少两组。正例必须直接绑定本节连续原文句链；反例必须是一句或一小段完整可读、且不属于主体原文的错误成文，不能只写“禁止总结”“不要 AI 味”等规则名。
- 每组正反例必须说明 `positive_effect / negative_failure / rewrite_instruction`，让落笔模型同时看见“怎样写成立”和“怎样写会僵”。
- `relation_micro_examples` 至少两组。每组必须直接展开主体原文中一处相邻句或分句关系，说明它是顺承、转折、因果、补充、反证、回声还是突断，关系由连接词显式标出还是由语序和动作隐式推出，并给出当前人物场景的自然正例与完整错误反例。只写“控制虚词节奏”或列出 `才、还、却` 三个字，不算模型看到了可执行示范。
- 关系正例必须保留真正需要的口头连接；例如“嘴上说让、手上仍占”在当前句面需要显式撞开时，应给出“手却还压着”的正例和“手还压着”的硬并列反例。若主体原文同类位置靠相邻动作自然反证，则必须把 `target_marking_mode` 标成 `implicit`，禁止机械加词。
- `dialogue_voice_packets` 至少两组。每组必须同时提供：`60` 字以上连续主体原文、按原序展开的至少两轮 `source_dialogue_turns`、明确的 `target_character`、至少三轮且 `60` 字以上的当前人物 `target_rehearsal`、以及完整 `negative_example`。
- 每组对白三联包必须写清 `turn_motion / target_scene_use / oral_texture_transfer / relationship_leverage / functional_compression_to_avoid / negative_failure / rewrite_instruction`。目标试演不是最终台词模板，而是写前口条校准；正式正文不得逐字照搬原文或试演。
- 只写“事务口气、短问、答非所问、对白要自然”不算对白示范。称呼、找补、口头连接、关系里的旧习惯和具体请求被压掉，只剩席位说明、任务分配或情节调度时，按 `功能句压缩` 阻断。
- 单一话轮若同时完成三类任务，也进入 `dialogue_grounding_review`：先替第三人说明理由或风险，再给当前人物分配位置或任务，最后承诺稍后找回、解释或补偿。人工裁决必须逐项列出话轮功能；不得仅以“符合人物高效、台词信息明确”放行。修复应让具体压力、动作打断、迟疑找补或关系请求进入话轮，而不是机械拆成三句同样高效的剧情指令。
- 正式写本节时必须把上述连续正文与完整错句展开到当前上下文；只传路径、ID、摘要或字段名，按未消费处理。

在此基础上，每个细纲小节还须至少绑定 3 个源文逐句机制，并完成段落计划、句群窗口计划和表层复刻拒绝。缺一节即阻断 `validate-prewrite`。

每节还必须在 `liveliness_plan` 中至少绑定 4 条活性资产、覆盖至少 3 类，写清动作词、身体感知、对白毛边、物件承情、叙述插嘴和反总结切点。活性资产用于迁移机制，不是要求把原词逐个塞进正文。

## 全文覆盖

每次绑定正文后先填写 `rewrite_scope_review`。`first_draft`、`full_rewrite`、`partial_revision` 三种模式必须如实选择。用户明确要求“完全检查并重写 / 全文重写 / 删除正文重写”时只能选择 `full_rewrite`：重写前后各完整通读一次，`rewritten_section_ids` 按顺序覆盖全部数字小节，`unchanged_section_ids=[]`。局部规则复扫、候选清零或仅修改已指出句子不算全文重写。

同时填写 `manual_review_provenance`。人工语义字段必须由当前模型逐字段判断并绑定当前正文 SHA。`automation_artifacts_used` 使用受控类别：`candidate_localization / sha_binding / schema_initialization / deterministic_serialization` 可记录为非语义辅助；`semantic_field_generation / automatic_quote_selection / automatic_character_ownership / automatic_keep_revise` 属于自动语义生成并直接阻断，未知自由文本也不得混入。项目脚本不得自动选第 N 句、轮转人物/源锚并生成语义裁决。任何自动生成过的 `comparison / manual_judgment / parity_judgment / evidence ownership / keep-revise` 都必须清空后人工重做，不能通过修改来源声明洗成“人工回执”。

人工侧车数据写回正式合同前，必须先运行 `preflight-manual-sidecar`。侧车至少绑定当前正文 `draft_sha256`，并使用与正式回执一致的 `section_reviews / source_subflow_reviews / character_arc_reviews` 局部结构。预检只检查逐字引句是否仍在指定小节、跨节绑定是否真实、SHA 是否过期及 comparison 是否模板复用；它不得挑句、改句或生成裁决。

正文写作时逐节维护 `section_reviews`，每个数字小节必须：

- 引用至少 2 条本节目标原句。
- 引用至少 2 条主体原文声线锚。
- 复核全部七个文字维度。
- 明确 `source_voice_preserved=true`。
- 明确 `functional_alignment_used_as_prose_proof=false`。
- 明确 `extra_ai_shell=false`。
- 写出原文与目标稿的具体句面对照，不能只写“已检查”。
- 在落笔前读取本节 `section_generation_plans`，并在写完本节后立即填写 `generation_plan_consumed=true`。
- 在 `continuous_chain_reviews` 中逐组引用写前连续句链和本节实际生成的连续目标句，说明句间推进如何迁移，并确认 `post_action_explanation_removed=true` 与 `contract_used_during_writing=true`。
- 在 `dialogue_voice_reviews` 中逐组绑定写前对白三联包，引用至少两轮正文真实直接对白，并确认 `oral_texture_preserved=true`、`functional_compression_avoided=true`、`rehearsal_used_as_voice_calibration=true`、`rehearsal_copied_verbatim=false`。
- 在 `relation_micro_reviews` 中逐组绑定写前句间关系包，引用正文真实原句，记录实际关系类型、显隐方式和目标连接词；显式关系词必须真实出现在引句里，隐式关系不得伪填连接词。
- 填写 `sentence_relation_review`，逐条裁决硬并列候选并人工通读全节。`reviewed_full_section=true` 只能由当前模型在逐句检查后填写，`mechanical_marker_insertion_used` 必须为 `false`，未处理残留必须为空。
- 回填最多取实际句数、至少取 4 条的 `sentence_mappings`；不足 4 句时覆盖全部句子。
- 每条映射绑定已标注源文句、至少 2 个属于该源锚真实标注的超细特征，并逐项说明句法虚词、句间关系、指代聚焦、话语语用、情绪段落作用和允许偏移。
- 每条映射必须原样填写当前目标句内的 `target_surface_evidence`、当前源锚句内的 `source_surface_evidence`，并在 `language_mechanism_match` 中同时引用两者。说明前一句却绑定后一句、合法特征跨源锚挪用，均直接失败。
- 去标点后不超过 6 字的句子必须填写 `minimal_function_sentence_review`。它必须绑定主体原文平行颗粒，说明真实关系变化与人物偏手或身体具体性；仅以“短句急刹、增强节奏、形成留白”为由不得判 `keep`。
- 逐节还必须接受动作对象与连续性扫描：无宾语的“先按住了 / 抓住了 / 拦住了”等及物动作必须补出执行者、具体对象和可见后果；正文仍命中候选时无条件失败，必须先回正文改写并重新扫描为 0，同时在回执中记录 `revise` 根因。相邻句重复“站起来 / 转身 / 按住”等动作必须说明不同执行者、对象或二次动作的变化；候选没有人工裁决，或 `revise` 未清零，`validate-draft` 直接失败。
- 每条映射明确 `contract_used_during_writing=true` 与 `surface_copy_rejected=true`。
- 立即填写 `liveliness_review`，至少绑定 3 条实际消费资产和 3 条目标活句，并确认 `author_summary_override=false`、`stiffness_patterns_remaining=[]`。
- 立即填写 `character_vitality_review`，逐个计划人物证明性格颗粒、认知局限和不可互换性；角色仍只负责递信息、挨骂或触发反刀时不得通过。
- 在 `character_vitality_review.dialogue_grounding_review` 中逐条裁决脚本定位的“具体问题—抽象答复”候选；候选必须绑定前置具体压力、人物母版机制和 `keep / revise` 结论，存在 `revise` 时先改正文再重新绑定。
- 同一复述话轮若只剩 `我问 + 话题名词`，如“我问座牌 / 我问钱 / 我问钥匙”，必须进入 `dialogue_grounding_review`。人工复核要说明原问题究竟在问去向、归属、处置人还是原因；疑问内容仍未回到句面时只能判 `revise`。常规“问路 / 问价 / 问诊”和已补焦点的“我问的是……”不属于该候选。

不同小节不得复用完全相同的 `source_anchors` 组合，也不得复用完全相同的 `comparison`。逐节复核必须使用与该节实际场面相符的主体声线锚，不能用两条万能原句给全书批量盖章。

除逐节七维复核外，`source_subflow_reviews` 必须覆盖主体 `子流程索引.jsonl` 的全部 `SF-*`。每个 SF 的六类局部颗粒都要分别填写：

- `target_sections`：实际消费该颗粒的正文数字小节。
- `dimension_transfers.{field}.target_quotes`：绑定小节中的真实正文原句。
- `dimension_transfers.{field}.source_evidence`：必须与该 SF 字段在主体索引中的全部证据完全一致，不得只挑最容易迁移的一条。
- `dimension_transfers.{field}.evidence_mappings`：每条主体证据必须单独绑定目标正文原句和句面对照，映射数量与顺序必须和主体字段证据一致。
- `dimension_transfers.{field}.comparison`：说明目标句面如何消费该局部颗粒，而非只对齐剧情功能。
- `dimension_transfers.{field}.surface_copy_rejected=true`：确认没有复制原人物、职业、原句或完整事件壳。

任一 SF、任一局部颗粒或任一已抽取原文证据没有正文对照，`validate-draft` 必须失败。全局七维都出现过，不等于主体原文颗粒已经全量消费。

主体存在 `原文细节库/*.md` 时，八类细节卡同样是全集合同，不是候选池。`full_bridge` 必须把每张卡写入 `source_detail_card_reviews`：

- 写前逐卡填写 `target_sections / target_adaptation / distinct_function_to_preserve / overlap_binding_ids / overlap_is_not_omission`，并将 `planning_status` 置为 `passed`。
- 写后逐卡绑定真实 `target_quotes`，填写具体句面对照和人工裁决，再将 `status` 置为 `passed`。
- 一张细节卡可以与 E/P/SF 描述同一段原文，但重叠不等于已消费。必须单独说明该卡独有的动作、对白、关系、旧伤、情绪、场景、场面或翻车功能怎样保留。
- 禁止把八类卡简单相加成互不重叠的剧情事件数，也禁止为了凑卡重复桥段；允许同一目标场面承接多卡，但每卡必须有自己的功能裁决和正文证据。
- 写前映射先由当前模型逐卡写入独立 JSON，再通过通用 `apply-detail-plan` 入口校验并原样合并。该入口不得生成语义；项目专属脚本批量填计划或直接把卡置为 `passed` 均无效。

任一细节卡缺计划、缺正文证据、标为未选或只写“已由 E/P/SF 覆盖”，`validate-prewrite / validate-draft` 必须失败。

语义回填还必须满足：

- `target_section_rationale` 逐 SF 说明为什么由这些正文小节消费，禁止按 `SF-01 -> 第1节` 机械顺排。
- `semantic_review_method=current_model_manual`，且 `automation_used_for_semantic_judgment=false`。
- 同一组目标句跨多个颗粒字段复用时，每个字段分别填写 `cross_dimension_reuse_justification`，说明该句在本字段承担的不同语言作用；复用理由不得同文复制。
- 六类字段的 `comparison` 与逐证据 `evidence_mappings[].comparison` 必须具体到句面作用。仅替换 SF 编号、字段名或章节号的文本按模板重复处理并阻断。
- 不同 SF 的目标小节理由和人工裁决不得使用同一模板。

脚本只能初始化骨架、校验 SHA/完整性，或把当前模型已经逐字段明确写出的数据确定性序列化到回执。禁止用循环从章节首尾或“第 N 句”自动抽句、轮转源锚、自动分配人物证据，再批量生成 `status / comparison / manual_judgment / target_section_rationale / evidence ownership` 等语义裁决。逐节必须声明 `semantic_review_method=current_model_manual` 与 `automation_used_for_semantic_judgment=false`。验证器输出 `passed` 仍不替代当前模型逐项判断。

固定执行顺序是“展开本节连续原文正例、原文对白三联包与完整错误反例 -> 读取人物、活性和情绪计划 -> 写本节 -> 立即回填连续句链、对白三联包消费与逐句映射 -> 下一节”。禁止先写完整篇正文，再批量生成 `generation_plan_consumed`、`continuous_chain_reviews`、`dialogue_voice_reviews`、`sentence_mappings` 或人工裁决。正文全部写完后，只允许运行本合同的 `validate-draft`、字数统计和平台格式校验，然后立即执行初稿停靠。该窄门禁属于首写质量控制，不代表已进入 AI 深审、滑窗审计或正文回炉。

强情绪稿还必须并行通过 [全文情绪颗粒度合同](emotional-granularity-contract.md)。文字颗粒度通过只能证明句面机制被消费，不能证明原文的情绪锯齿、直接判断和峰值动作没有被降级。

全文还必须逐核心人物填写 `character_arc_reviews`。零散口头刺、同一冷句模板或单场鲜活不能替代稳定偏手、变化破口和私域语言的全文证据。

动作连续性复核还必须扫描 `空转舞台动作` 候选。`持物 + 站直 / 起身 / 转身 / 抬头 / 低头` 若作为独立句只完成姿态复位，而没有去向、受阻对象、物件归属变化、回应对象或可见后果，必须逐条填写 `bare_stage_direction_reviews`，说明持有物、姿态动作、方向或压力、现场变化及人工裁决。候选定位不是机械禁词：已有明确去向、即时阻力、物件后果或话轮控制权变化时可以保留；裁决为 `revise` 时必须回正文修改并重新绑定，不能只替换姿态同义词。

动作连续性还必须人工核对 `状态首次出现时间线`。对身体、衣物、物件和空间的可追溯状态，逐项确认 `触发动作 -> 首次可见 -> 持续或加重`；不得在致伤、浸湿、碰撞、撕裂或污染发生前先写出血迹、伤口、湿痕、裂口等结果，再让后文补原因。检查需跨相邻小节延续，且按开放因果类别判断，不建立封闭状态词表。旧伤、场外事件或延迟揭因只有在首次出现处已有可理解的来源锚时才能保留。

`explanatory_inference_review` 还必须覆盖 `便利巧合式调度` 候选。叙述句以 `却/但/可 + 正好/刚好/恰好 + 第三方叫、让、催、喊、通知或示意` 在关键一拍改变人物位置、打断回应或免除主动选择时，必须检查现场压力是否早已成立、第三方的具体话语是否落地、人物是否作出可见选择。只删巧合副词而保留同一调度摘要不算修复。该扫描不是“正好”禁词表；日常吻合、充分前因或人物主动利用机会可以人工判 `keep`，但必须写明原文连续句链依据。

`dialogue_grounding_review` 还必须扫描 `告示牌式工作人员对白`。`女士/先生/家属/乘客/观众 + 区域 + 先别/不要/不能 + 动作` 若只完成剧情拦截，必须人工核对身份判断、限制理由、替代去向和 `先` 的时间承诺是否真实成立。只加礼貌词不算补足人物口语；消防、安保、急救等即时止险短令可以结合现场压力判 `keep`，普通秩序维护仍缺具体口头承接时应判 `revise`。

`explanatory_inference_review` 还必须扫描 `视距越权 / 顺序视线调度` 候选。当前人物处在后排、门外或人群中时，不得把遮挡下的眼睛颜色、眼眶状态等精确特写当作已知事实；`停顿 + 先看甲 + 再找乙` 也必须落回手势、话音断点、遮挡变化和身体转向。候选只作语义提醒，近距离观察或具有明确关系后果的视线顺序可以人工判 `keep`，但需写出视距和触发证据。

`explanatory_inference_review` 还必须扫描 `空泛即时回应`。`几乎立刻/马上/很快/当即 + 应/答/回` 的独立叙述句若没有对象、原话、动作重叠或可见后果，不能靠速度副词证明人物偏向。必须回到当前视点可感知的同步动作与真实回应；紧急现场确实听不清内容时可以人工判 `keep`，但要有声音、身体或空间后果作为依据。

`explanatory_inference_review` 还必须扫描 `默认状态计时器`。`还 + 当前场景必然维持的姿态，已经/就 + 下一动作` 若前半句没有变化、阻力或反常坚持，不得作为同步感证据。通话、驾驶、站立等场景应改落电话断线、忙音、屏幕变化、手部位移或其他实际后果。人工判 `keep` 时必须证明该姿态本应结束却仍被人物维持；普通默认状态不能靠节奏功能放行。

`explanatory_inference_review` 还必须扫描 `抽象事件预判 / 同义动作复播`。检查单位不是孤立单句，而是相邻句组成的同一事件：前句若只用近义谓语重复事件并先下“突然、干脆、仓促、彻底、意外”等抽象评价，后句才给出时间、动作对象和现实结果，必须先做删除测试。删除前句后事实、情绪与因果均不损失时，判 `revise`，把具体证据提前；不得把“退出项目，离开得很突然”改成另一组近义词继续复播。评价来自人物即时视角、与随后证据构成反差或直接改变下一动作时可以判 `keep`，但须引用连续句链和可见后果。这里列举的词只用于说明常见高置信形态，人工检查按事件同指、信息增量与句间功能开放覆盖其他事件和评价。

对白人工复核不能由自动候选列表或抽样三联包代替。每节必须在 `dialogue_grounding_review` 写明 `candidate_zero_is_not_pass=true`，并逐组回填 `dialogue_voice_reviews`：说话者与现场角色、具体压力/对象、换成另一角色后的不可复用测试、以当前对白为中心前后 3-5 句重读窗口和 `keep/revise`。此外，`full_dialogue_reviews` 必须按正文顺序逐字覆盖本节全部 `「……」`，重复台词按出现次数保留；每条填写 `speaker_and_scene_role / context_window / utterance_goal / adjacency_or_reply_fit / time_state_fit / object_and_result_complete / participant_role_direction / character_specificity / verdict / manual_judgment`。其中 `participant_role_direction` 必须说明谁执行、谁承受、谁接收及主动/被动方向，不能让“谁拍谁”被压成含混的“给谁拍”。`context_window` 必须是正文中包含该句的连续窗口。少一条、顺序不一致、引句过期或任一字段空泛均失败；`reviewed_all_character_dialogue=true` 只作最终确认，不再具有独立放行效力。这样才能拦住“人已到场仍问路上堵不堵”“只说打了两遍却不落接收者和未接结果”这类没有进入抽样包的台词。

逐句复核还必须检查 `证据标签式答复`：前一话轮用“我以为不要了 / 没人用 / 可以拿”等推断替越界找理由时，后一话轮不能只报静态物件状态，再让读者自行完成反驳。`adjacency_or_reply_fit` 必须具体写出被反驳的推断和句面中的否定、反问、动作或逼答关系；“事实具体、对象明确、推动下一句”不足以放行。争议物按开放语义类别判断，不使用封闭名词表；普通报状态或紧急告警可结合现场人工保留。

相邻专业对白还必须检查 `专业对白造句感`：不得连续复用同一主题意象包装操作风险、概率和结果，更不得因拟人比喻造成施事、受事或结果对象错乱。逐句卡除人物特异性外，还要在承接判断中说明前一句比喻是否已经完成作用、后一句是否回到可理解的事实。角色粗口、行业词和单处俗比可以保留，但“连续呼应得漂亮”不能作为放行理由。

叙述中的人物转述还必须检查 `借人物之口主题总结`。出现“她说 / 他说 / 某人劝我”时，不能只因有明确说话者就放行；必须核对转述的现实目的、未知事实、要求动作或现场后果。工整价值判断若只替当前段落解释“为何不原谅、为何离开、为何不能弄丢自己”，而没有改变信息或行动，必须改回具体转述或删除。

逐句对白还必须检查 `程序标签式关系控诉`。人物面对具体事实追问时，不能用“审我 / 定罪 / 问责”等流程概括替代接招；`adjacency_or_reply_fit` 必须写明上一轮具体问了什么、当前人物故意漏答什么、又怎样借装弱或旧关系转移压力。真实程序场景除外，日常关系争执不得仅凭“体现被压迫 / 有关系杠杆”放行。

第三人去向短问还必须检查 `知情对象与转向触发`。`adjacency_or_reply_fit` 要写明当前话轮因哪个具体线索、动作或前话转向第三人，`participant_role_direction` 要说明被问者为何可能掌握第三人的位置。被问者未与第三人同场、没有收到消息或掌握行程时，“她在哪儿 / 他去哪儿了”即使语法完整、情绪急迫，也不得判 `keep`；应改问真实知情者，或改成拨号、查消息、赶回原地等可观察动作并写出结果。不得用“忽然想起 / 这才意识到”补作者说明绕过本项。

身份反问还必须检查 `身份制造知情义务`。`character_specificity` 不能只写“用丈夫/母亲/负责人身份施压”，还要在 `time_state_fit` 或 `participant_role_direction` 中引用对方实际接触该信息的机会。关系身份不会自动提供医院地址、密码、临时行程或被他人隐瞒的安排；“你是她丈夫，问我她去哪家医院？”若找不到此前告知或共同确认，必须改成对方本可追问却放弃的具体事实，如手术日期。共享日程、明确通知或人物亲自确认过的事项可以保留，但必须绑定连续事实链。

资格门槛还必须检查 `资格抽象盖章`。对白出现“让人肯认 / 得有人点头 / 还要看资格”等抽象说法时，`object_and_result_complete` 必须补出拒绝者、授权者、具体动作和被挡后果；没有这些就不能以“关系刺痛成立”判 `keep`。修复必须优先调用前文已发生的登记、签字、改名或门禁事实，例如“她在家属那一栏写的是我，护士凭什么告诉你？”；不得为了让句子具体而新增正文没有发生的出示证件或授权流程。

外部压力还必须检查 `外部后果受事者偷换`。`time_state_fit` 与 `participant_role_direction` 必须同时说明谁被骂、因为什么、该压力何时出现；全篇存在评论或围堵，不代表任意角色都已承受同一后果。前文评论只骂苏念乔插足，后文“晚照就不会继续被人骂”必须判 `revise`。修复应删掉未落地后果，回到现场真实动作，不得补写新舆论支线替旧台词找依据。

项目处置对白还必须检查 `项目处置单式对白`。同一话轮承担停项目、限制素材、分配违约责任等两项以上处置时，`adjacency_or_reply_fit` 必须证明现场角色在事项之间有真实接招；若只是“停掉 / 封存 / 找我”连续播报，即使属于同一项目也不能凭功能同类判 `keep`。应先让一项决定改变持卡人、摄影师或合同方的动作，再补下一话轮；拆句不能只加句号，必须新增可见承接。

交付短令还必须检查 `交付对象与接收者脱落`。证据、文件、素材、钱款等正在换手时，`object_and_result_complete` 与 `participant_role_direction` 必须指出具体物件、当前持有者、接收者和禁止后的控制权；“这段不能交”不能只凭前文出现警察、眼前出现存储卡就自动放行。若物件和接收者没有在紧邻话轮同时明确，应改成“这张卡不能给警察”等人物会说的完整短令。

进入关系空间的移动词还必须检查 `关系目的地脱落`。`带回来 / 领回来 / 又回来了` 若承担第三人进入婚房、家庭、公司或旧关系的后果，`object_and_result_complete` 必须写明目的地，不能只说方向副词“回来”。相邻下一话轮若重复补出同一“带回家”动作，应重新分配信息：前一句落目的地，后一句删重复并推进钱、物件或身份后果。

叙述短断还必须检查 `无主语知情增量总结`。出现“越说，知道的越多 / 越解释，事情越清楚”等句子时，必须回答谁知道、具体新增哪项事实、该事实是否尚未由前后文呈现；任一答不出即删除。不得用人物刚说出的具体口供和后文警方取证反向证明这类总结有依据，也不得换一个同义金句继续保留作者归纳。

维护或护理对白还必须检查 `维护说明书式对白`。若同一话轮包含来源转述、专业术语定位和操作禁令，`context_window` 必须先出现指向可见物件的动作，`object_and_result_complete` 必须写明触发变化、处理对象和去向。不能以“三句都服务保存要求”放行“湿度卡在这里 / 别自己换盒”一类说明书句面；应改成指卡后说变色便把盒子拿回店里等可执行口语。

对白之后还必须检查 `通用语塞占位符`。若具体追问后出现张嘴、嘴唇动、没接上或长久不语，而紧邻下一拍已经通过物件换主、继续追问、离场、签字等现实动作证明回答失败，必须删除重复反应，不得把“人物无话可说”再次写成分镜标签。`context_window` 应直接绑定造成语塞的问句和随后发生的现实变化；需要保留沉默时，人工裁决必须说明具体身体原因、实际残句或沉默改变的现场结果。该项按开放语义扫描，不用封闭短语表代替全文判断。

事实连续性还必须检查 `失效对象重复处分`。人物提出放弃、交付或不再使用某项对象时，`time_state_fit` 不能只写“承诺面向未来”，而要向前核对对象是否已出售、转让、注销、换锁、销毁或失权，以及说话者此刻是否仍有处分权。对象已失效却再次被“留给”别人，即使下一句准备揭穿，也必须先改正文；反刀只能来自双方认知时间差和可见凭证，不能靠前一句制造事实错误。`object_and_result_complete` 还要检查同一话轮是否把放弃对象、交付凭证和未来保证重复播报为处置声明。本项按开放语义类别覆盖所有控制对象，不建立封闭名词列表。

关系收口还必须检查 `抽象认知盖章`。当人物在事实对账、制度动作、失效物件或离场之后宣告“终于知道 / 真的明白 / 现在懂了”，不能仅以“前文已经托住知道内容”判 `keep`；必须说明认知对象是否在句面或紧邻话轮明确、这句迫使谁做了什么，以及删除后是否已有更具体后果完整承重。三项任一答不上来即删除，并把情绪破绽证据改绑到真实身体或物件动作，不得换写同义认错金句。普通认知答复、人物撒谎敷衍或争取具体行动的宣告可以保留，但连续窗口必须出现对方接招和可见变化。

`dialogue_grounding_review` 还必须扫描 `关系转移受益对象缺失`。当位置、座位、名额、房间、钱款、卡、钥匙、座牌、录像等争夺物与 `为什么/凭什么 + 让、给、留、交、递、腾、挪` 同时出现时，必须核对接收者是否落在话面。若本场真正争的是第三人拿走了谁的东西，“我的位置为什么要让”必须改成“我的位置为什么要让给她”或符合人物口气的明确说法。普通“让开”、接收者已出现，或只争移动而不争归属时可以结合上下文判 `keep`。

上述对象名只作例子，不构成封闭词表。争夺物、呼语身份、遮挡物、默认姿态对象和持物动作均使用“常见高置信模式 + 开放结构兜底”；例如工位、监护权、旧怀表、采访线、方向盘、车窗不在旧名单里也必须进入候选。自动扫描只负责提高召回率，当前模型仍须结合前后文判断是否真的缺接收者、越权观察、默认状态计时或告示牌式调度。

来源书动态信号字典中的 `核心物件 / 证据载体` 优先于通用物件白名单。只要动态词已由来源原文验证，profile 生成器不得再因固定后缀名单不含该物件而删除；通用名单只作为缺少动态字典时的保守回退。

## 完整命令

初始化：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" init \
  --project "{项目名}" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json"
```

当前模型完成写前基线与校准样本后：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" bind-outline \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --outline "{项目目录}/小节大纲.md"
```

当前模型逐节完成落笔包后：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" apply-section-plan \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --plan "{项目目录}/写作资产/文字颗粒逐节写前侧车.json"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" validate-prewrite \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --outline "{项目目录}/小节大纲.md"
```

`--source-original` 是强制显式输入，不得因回执已经绑定主体原文而省略。该脚本校验的是“当前命令输入 + 回执绑定 + 当前细纲”三方一致；主体路径只写在回执里、不在命令行再次传入，按命令不完整处理，不属于可容错省参。

`apply-section-plan` 只把当前模型已经逐节写完的 `section_generation_plans` 原样合并进当前合同。侧车可按原序只提交当前已人工完成的小节，未提交小节保持 pending；侧车必须绑定当前细纲 SHA，并声明 `reviewed_by_current_model=true`、`semantic_fields_generated_by_script=false`。入口不得生成句链、正反例、人物计划、语义判断或通过状态；九节仍须全部完成后才能通过全书 `validate-prewrite`。

正文放行后，先由当前模型按原文桥段与目标场面语义完成独立写前字段 `section_sf_assignments[]`，每项写明 `subflow_id / target_sections / target_section_rationale`；它必须与主体 SF 全集同序相等。任一 SF 留空或任一目标小节没有 SF 时禁止初始化。`source_subflow_reviews` 保留为提交前六维真实证据，不得在正文前伪填目标引句。再按 [逐节正文进度硬闸](section-progress-gate.md) 初始化字数预算和当前小节状态。每节只在暂存稿一次写完，立即将本合同要求的完整 `section_review` 写入 `写作资产/逐节验收/第N节.json` 的 `prose_review`，并通过 `commit-section N`。该命令必须实际校验完整场面表演、连续原文链、对白包、句间关系、逐句特征、活性、人物、全部对白及本节全部 SF 六维，不能只检查四条映射。本节未通过时禁止写入正文或创建下一节。

全部小节逐节通过且进度闸输出 `final_ready` 后，才绑定最终 SHA 并自动生成全部小节复核骨架：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" bind-draft \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --draft "{项目目录}/正文.md" \
  --section-progress "{项目目录}/写作资产/逐节正文进度.json"
```

当前模型将已逐节验证的独立回执按小节合并到全文骨架后运行：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" preflight-manual-sidecar \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --sidecar "{项目目录}/写作资产/文字颗粒度人工侧车.json" \
  --draft "{项目目录}/正文.md"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" validate-draft \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --draft "{项目目录}/正文.md" \
  --section-progress "{项目目录}/写作资产/逐节正文进度.json"
```

逐节独立回执是首写必须产物，不再属于可选侧车。全文人工侧车仍只在分批合并时创建；没有需要时不得伪造空文件过闸。只要存在全文侧车，就必须在每次合并前重跑预检。`validate-draft` 的 `passed_sections` 必须等于 `draft_sections`；两者不等即使总状态异常显示 passed，也按验证器缺陷处理并停止交付。任一命令未输出 `passed` 都必须回到当前步骤修正，不得运行 `--help` 探路，也不得降级成 warning。
