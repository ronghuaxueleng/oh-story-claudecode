# 细纲表演验收硬闸

细纲不是“主任务 + 子事件 + 物件 + 章尾”的施工清单。对于仿写、融合和强情绪关系短篇，它必须先把原文的现场表演机制翻译成新故事的场戏设计，才能进入正文。

`小节大纲.md` 与验收回执必须分层：

- `小节大纲.md`：连续的表演型场面，详细写人物入场、偏手、错答、动作打断、站位换主、信息压后和场末余波，可直接用于生成正文。
- `细纲表演验收回执.json`：把连续场面反向归纳成结构化字段，仅用于核验和阻断。

严禁为了方便回填回执，先把细纲本身写成 `唯一动作 / 主控物件 / 信息延迟 / 交流链 / 禁写项` 的字段表。字段齐全但没有连续场面，仍然判失败。

本闸门专门阻断：

- 只参照题材、人设或桥段骨架，没有参照原文如何让人物在场内互相逼迫
- 只从拆书资料抽出功能机制，没有回到原文确认桥段的场面颗粒度
- 只把原文 BID 当作“功能节点”借用，没有在细纲阶段逐桥证明原文主情节和子情节流程已经迁移
- 写完正文后才发现原书公开掉位、私域换主、旧物爆体、补救失败、选择测试、公开反噬等承重桥段缺失或缩水
- 一场预先塞入多份材料、多个程序节点、多个物件和多个结论，正文只能逐项报到
- 证据、财务、手续、权限在同一场连续上桌，缺少信息延迟和人物阻力
- 对白只是高效问答，压力没有改变动作、站位、物件控制权、回答范围、身份或后果
- 用“冲突强烈”“信息已铺”“人物有交流”这种概括代替可执行的场戏设计
- 细纲已经像分镜条、证据排队表或规则施工稿，却在正文阶段才靠润句补救
- 人物关系必须靠职业术语才能看懂，读者不知道谁是妻子、丈夫、旧爱以及谁被放弃
- 只迁移原文桥段功能，没有迁移原文的受辱、希望、反刀和余痛顺序
- 新稿情绪烈度低于原文，却用“控制权已经换主”冒充同级仿写
- 连续小节复制同一套场面颗粒度或人工判断，批量制造假通过回执
- 连续小节复制同一套原文情绪拍、触发和证据，只换目标桥段名称
- 人物到场没有原因、入场前知情越界、关键物件在生成前被使用，或本场不能因果触发下一场
- 小节内部从听见直接跳到看见、从争执直接跳到取得证据，缺少掀开遮挡、移动、索取、交付等必要动作
- 人物近距离在场很久才发现显眼信息，或用身体不适、电话、第三人连续精准打断关键回答
- 相邻小节没有交代时间、地点、人物、知情、物件持有和未决问题的状态交接
- 辅助来源只摘取一个结果或反转硬插主体骨架，没有迁移已选 SF 的完整前态、步骤、知情、物件和出口状态
- 虚构医疗、法律、金融、行政规定替人物制造不得不做的动作
- 同一关键事实跨节同时处于“待确认”和“已确认”等不兼容状态

## 强情绪仿写五硬闸

追妻、婚恋清算、白月光、替身、背叛等强情绪关系稿，正文前必须同时通过：

1. `relationship_legibility`：不用职业知识也能说清人物关系、偏心方向和具体伤害。
2. `emotion_intensity`：逐节填写 1-10 分烈度、具体羞辱/刺痛、情绪翻面和相对上一节的升级；强情绪稿不得低于 7。
3. `professional_shell_translation`：删除术语后冲突仍成立，且先让读者读懂关系伤害，再用职业动作把伤害做实。
4. `source_emotion_parity`：绑定选中原文真实片段，逐拍对齐原文与目标稿的情绪流程；每拍必须包含触发、关系位置变化、读者感受、烈度和证据。目标拍数、拍序、反刀拍、峰值拍不得变化，任何一拍的目标烈度不得低于原文。
5. `first_draft_generation_contract`：每节在动笔前绑定一段真实原文表演片段，预先写出情感中间拍、连续瞬间分组、真实断段理由、句间关系和虚词策略。它是正文生成输入，不是写后审计表。
6. `scene_logic_contract`：每节绑定原文场景因果资产和真实证据，迁移到场原因、知情边界、物件生命周期、制度约束、替代方案阻断与离场因果。

“和原文一样”指情绪功能、顺序、反刀时机、峰值位置、场末余痛和读者体感烈度对齐，不复制原句、人物、职业或完整情节壳。不能用“整节总分相同”掩盖中间某一拍被削弱。

`required_sequence` 是零容缺合同，不是抽样指标。主体与已选辅助 `SF-*` 的每一拍都必须在目标细纲和正文中有独立落点；禁止容许漏一拍或漏两拍，禁止把相邻承重拍合并成一个结果句。逐拍验收必须判断“前态 -> 触发 -> 动作选择 -> 可见结果 -> 下一拍原因”，不能用关键词、状态标签或同一处证据重复认领多拍。任何一拍缺失都必须阻断当前节关闭并回写正文。

`required_sequence` 必须全量进入逐节展示、细纲映射和正文关闭校验，不得只展示前四拍。`source_emotion_parity.manual_judgment` 与 `adaptation_boundary` 必须由当前模型给出已完成判断；保留“机械预填 / 待确认 / 待复核”等占位话时不得通过。

正文自动开节后由工具箱生成 schema v2.1 的 `写作资产/当前节逐拍消费回填.json`。每条固定绑定 `subflow_id / beat_index / source_beat`，当前模型只补：

- `evidence`：固定五项数组，依次填写本拍前态、可见触发、动作选择、可见结果和推动下一拍的原因；
- `performance_equivalence`：说明心理过程、身体动作、注意顺位或情绪刺痛为何没有降级成标签。

`status` 由工具校验全部证据后自动判定，禁止要求模型重复手填。

五类证据必须分别引用当前正文中不少于 6 个非空白字符的真实片段，并按前态 -> 触发 -> 动作 -> 结果 -> 下一拍原因出现；不得跨组件或跨拍复用。`advance-section` 必须校验 schema、颗粒包 SHA、拍数、拍号、原拍文本、五组件正文证据、组件顺序和跨拍动作顺序。任何一项失败都留在当前节回写，不允许以总覆盖率、宽泛功能句或口头 `passed` 代替。

## 执行时机

设定与细纲完成后，且在任何正文首写、全文重写或正文大回炉前，必须先初始化并人工回填：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_outline_performance_contract.py" init \
  --project "{项目名}" \
  --outline "{项目目录}/小节大纲.md" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-original "拆文库/{辅助书一}/原文/{辅助书一}.txt" \
  --source-original "拆文库/{辅助书二}/原文/{辅助书二}.txt" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --primary-source-bundle "{项目目录}/写作资产/主体原文完整颗粒包.json" \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json"
```

`--primary-source-bundle` 是主体原文完整颗粒硬绑定入口。它必须由 `prepare-setting` 先生成并通过校验，且内容来自主体来源 `仿写无损编译包.json + 拆文读取回执.json` 的当前项目落地副本。细纲初始化后，回执中的 `primary_subflow_semantic_inventory` 必须与该包逐条一致；后续每节 `source_slice_bindings / source_performance_excerpt / source_performance_evidence / style_fields_consumed` 都要能回溯到这份主体包里的明确 `SF-*`，不能只写“像原文颗粒”的人工总结。

当前模型完整读取选中原文、主体原文完整颗粒包及细纲后，逐节回填结构验收和首写生成契约。修闸阶段先用工具箱做快速预检，禁止每改一小块就直接全量跑正式校验：

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only sections
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only handoff
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only bridges
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only first-draft
```

局部预检通过后，再运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-validate
```

`outline-validate` 会先执行快速预检；预检未过时直接阻断并跳过正式全量 `validate_outline_performance_contract.py validate`。输出不是 `outline_performance_contract: passed` 时，禁止写正文。细纲、任一选中原文、主体原文完整颗粒包或拆文读取回执 SHA 变化后，旧回执立即失效。1.4 及更早回执不具备节内逐拍链、跨节交接链和辅助 SF 全流程对齐，必须重新 `init` 并由当前模型人工回填。进入某一节正文前，必须重新读取该节 `source_performance_excerpt` 和完整生成契约；不得只凭对话上下文、`模型语义输出.json` 概括结论或压缩后的细纲开写。

`outline-precheck` 或 `outline-validate` 一旦失败，工具箱会自动刷新 `当前细纲修闸包.json + 当前细纲修闸回填.json`。失败后禁止继续用 `cat / sed / jq` 逐层探测整张回执，也禁止为了“摸字段”去读旧项目同名文件。唯一允许的修闸闭环是：编辑当前回填模板 -> `outline-repair-apply --packet-sha ...` -> 立刻重跑刚才被阻断的命令。

修闸回填必须是最小字段 delta。`sections` 只输出当前失败小节及报错字段，写回时递归合并，不得整节替换已经通过的嵌套字段；`section_handoff_chain` 只输出报错中的相邻节对。包内 `eligible_outline_evidence` 是从当前 `小节大纲.md` 有界摘出的可用原句，所有 `outline_evidence / target_outline_evidence` 必须从中逐字复制，同义改写不算命中。

### 颗粒度原创模式

用户明确要求“使用一本原文的颗粒度，但自行创造情节”时，初始化命令增加：

```bash
--source-mode granularity_only
```

该模式不要求复制主体原文 BID 身份，也不要求 `source_bridge_flow_inventory` 与 `outline_bridge_flow_parity` 覆盖原书全部桥段。它改为强制填写 `granularity_transfer_contract`，且必须覆盖目标细纲全部小节：

- `source_scene / source_evidence`：绑定原文真实场面，不得只写拆文摘要。
- `source_granularity`：说明原文一场内有多少有效动作拍、控制权如何换主、信息在哪里压后。
- `target_scene / target_outline_sections / target_outline_evidence`：绑定原创场景和当前细纲原句。
- `transferred_beat_density`：说明迁移的事件拍密度，不复制原事件身份。
- `transferred_information_delay`：说明哪些事实只漏一角、哪些压到后场。
- `transferred_control_right_changes`：说明动作、物件、空间、身份或外部秩序如何换主。
- `rejected_surface_elements`：至少三项，明确拒绝原人物、职业、核心物件、完整关系壳、原句或结局入口。
- `manual_judgment`：解释为什么这是颗粒度迁移而不是换皮复刻。

逐节 `original_scene_granularity`、`source_mechanism`、`source_emotion_parity`、关系可懂性和强情绪烈度仍是硬闸。也就是说，该模式只解除“原书发生什么必须照搬”，不解除“原书如何把一场写实写满”的参照责任。

## 原文桥段流程对齐

主流程仿写、融合仿写、同桥仿写，或用户明确要求“完全参照原文”时，正文前必须先完成两张人工表。它们属于细纲硬闸，不是写后审计项。

第一张是 `source_bridge_flow_inventory`，用于列出主体原文 BID / 关键子桥段全集。每个桥段必须写清：

1. `source_path` 与 `source_sha256`：绑定原文文件。
2. `bridge_id` 与 `bridge_name`：例如 `BID-01 公开掉位与网络补台反杀`。
3. `source_required_sequence`：原文内不能打乱的动作顺序，至少两步。
4. `source_must_keep_actions`：迁移时必须保留的动作、物件、空间、身份或权力变化，至少两条。
5. `source_scene_granularity`：原文场面颗粒度，不是功能概括。
6. `source_end_state_change`：桥段结束时人物关系、现实位置或信息边界如何变化。
7. `cannot_merge_or_drop_reason`：为什么不能被合并成一句功能说明或删掉。

桥段全集不能由回执填写者自行定义：

- `init` 会从每本选中原文对应的 `写作资产/桥段施工卡.md` 自动提取 `available_bridge_ids` 并绑定该文件 SHA。
- 第一本选中原文固定为 `primary`，`required_bridge_ids` 必须与施工卡全部 BID 完全一致，不能手工删减。
- 后续选中原文固定为 `auxiliary`。如果写作读取门禁选择的是完整 `SF-*`，不得在这里被迫扩成父 `BID-*`；只有本稿确实采用完整辅助 BID 时，才在 `selected_bridge_ids` 中显式列出并进入桥段库存。
- 每条库存通过 `source_path` 继承来源的 `primary / auxiliary` 角色，`bridge_id` 可带书名前缀，但必须保留可识别的 `BID-*`。
- 主体 `required_bridge_ids` 或辅助 `selected_bridge_ids` 任一未进入库存及对齐表，正文硬阻断。

第二张是 `outline_bridge_flow_parity`，用于证明每个原文桥段已经落进细纲。每个原文 `bridge_id` 都必须有且只有一条对齐记录，并填写：

1. `source_path / source_sha256`：绑定该桥段实际来自哪本选中原文。
2. `source_emotion_sequence / target_emotion_sequence`：逐拍填写 `role / trigger / relationship_position_change / reader_effect / intensity / evidence`。
3. `source_reversal_beat / target_reversal_beat`：反刀发生在第几拍，必须同位。
4. `source_peak_beat / target_peak_beat`：最高烈度发生在第几拍，必须同位。
5. `reader_experience_parity / emotion_parity_judgment`：当前模型说明为什么目标桥段给读者的羞辱、刺痛、希望落空或反噬体感与原文同级。
6. `target_outline_sections`：对应到目标细纲哪些小节。
7. `target_outline_evidence`：至少两条当前细纲原句，证明不是回执空话。
8. `parity_status`：只能是 `matched` 或 `adapted`。`adapted` 必须说明题材替换边界，但仍保留原文流程功能和场面压力。
9. `missing_or_weakened_risk`：人工说明最容易缩水的位置以及细纲如何避免。
10. `manual_judgment`：当前模型判断为什么这不是“只做功能映射”。

以下情况直接失败，必须先回细纲重构，禁止写正文：

- 原文某个 BID 没有进入 `outline_bridge_flow_parity`。
- 原文 BID 虽已进入对齐表，但没有逐拍迁移情绪，或只给一个整桥烈度总分。
- 目标桥段改变原文反刀拍、峰值拍，或任一拍烈度低于原文。
- 只对齐最虐的少数桥段，其余主体 BID 仍只写功能和动作。
- 主体桥段施工卡中的任一 BID 没有进入库存，或辅助显式选中的任一 BID 没有进入库存。
- `parity_status` 是 `missing / weakened / merged_unclear / only_function_mapped / pending`。
- 只写“迁移公开掉位 / 补救失败 / 公开反噬”，但没有细纲原句证明动作顺序、控制权变化和场末状态。
- 目标细纲把两个以上承重 BID 合并成一场，并且说不清哪个动作链、信息延迟和状态变化分别承担原文功能。
- 只证明新故事内部顺序合理，没有证明原文桥段流程如何迁移。

## 逐节必填

每个真实小节都必须单独填写：

1. `irreversible_action`：本场唯一不可逆动作，不允许由多个并列结果代替。
2. `controlling_object`：本场唯一主控物件或空间控制点，必须服务人物争夺。
3. `source_function_mechanism`：绑定拆书资料中的功能机制，说明本节迁移的是公开掉位、私域换主、不可替代物爆体、高成本补救后再选错、行动验收、公开反噬、私人尾声等哪类功能；必须填写拆书资产路径、资产规则和本节采用理由。
4. `original_scene_granularity`：绑定选中原文具体桥段，写清原文场面颗粒度：谁先施压、谁抢/挡/松手、哪个物件或空间改归属、哪句台词逼出动作、旁观者或外部秩序如何改变现场。不能只写“参考原文节奏”。
5. `scene_logic_contract`：绑定原文的 `causal_asset_id`、原文路径/SHA 和至少两条真实证据；逐项填写目标人物为何同场、各自入场前知道什么、关键物件何时生成/持有/使用、明显替代方案为何不可用、本场如何触发下一场。还必须用 `scene_entry_state / scene_exit_state / beat_dependency_chain` 逐拍闭合前态、触发、知情、空间或物件权限、后态和下一拍原因。等值合同是：首拍 `from_state == scene_entry_state`，每拍 `to_state == 下一拍 from_state`，末拍 `to_state == scene_exit_state`；`knowledge_state_chain` 从 `initial_state` 起逐次要求前一迁移 `to_state == 后一迁移 from_state`，且末次 `to_state == final_state`。用知情链记录承重事实如何被谁在第几拍获知；逐项裁决人物汇合、关键信息延迟、精准打断和空间/物件权限四类风险。`external_rule_dependency` 涉及医疗/法律/金融/行政时必须有可靠依据；无法核实时不得借制度硬推，改由角色主动选择承担责任。
6. `source_mechanism`：绑定一段选中原文，说明只迁移的表演机制，以及不复制人物、职业、原句和完整桥壳的改写边界。
7. `information_delay`：入场已知、本场只漏出什么、必须压到后场的事实分别是什么。
7. `character_missteps`：至少两条。写清谁先躲、谁先抓、谁错答、谁把什么当作可以补救，不写抽象性格标签。
8. `interaction_exchange`：一方施压、另一方被迫接招、现场出现何种可见变化。
9. `conflict_carrier`：本场争夺的现实权力、承载它的物件/空间/身份，以及争夺后的实际后果。
10. `forbidden_items`：至少两条。本场不能提前上桌的材料、结论、程序报账或关系判词。
11. `outline_evidence`：至少两条当前细纲原句，证明上述设计真的已写入细纲而非回执空话。
12. `manual_judgment`：人工说明本场为何不是清单式推进。
13. `relationship_legibility`：用白话写清关系角色和本场关系伤害，并确认陌生读者无需领域知识即可理解。
14. `emotion_intensity`：填写烈度、具体刺痛、情绪翻面及相对前场升级；强情绪稿低于 7 分不得放行。
15. `professional_shell_translation`：用一句白话翻译职业冲突，并证明去掉术语后感情冲突仍成立。
16. `source_emotion_parity`：引用真实原文片段，逐拍列出原文与目标情绪流程。每拍都必须填写 `role / trigger / relationship_position_change / reader_effect / intensity / evidence`；另填两边反刀拍、峰值拍、场末余痛等价、读者体感等价、人工判断及迁移边界。
17. `first_draft_generation_contract`：必须在首写前填完，不得从正文反向补写。字段必须包含：
   - `source_slice_bindings`：逐一绑定本节使用的主体/辅助原文路径、SHA、精确行段、至少两条行段内证据和六类已消费文风字段；
   - `source_performance_excerpt`：任一选中原文中真实存在的表演片段。
   - `emotion_process`：逐项写明入场情绪、非自主身体反应、记忆/联想/注意漂移、矛盾冲动、说错/回避和场末余痛。本场若无回忆，要写明由何种现场注意漂移代替，不得留空。
   - `continuous_moment_groups`：至少两组，写明哪些动作、感知和反应属于同一瞬间，不能拆成电报式短段。
   - `paragraph_break_reasons`：至少两条，只能是注意对象、说话人、时间状态或现实权力真正变化。
   - `sentence_relation_plan`：至少三条，写明关键相邻句的时间、因果、转折、让步、递进或心理反冲，不指定固定连词。
   - `function_word_strategy / telegraphic_risk / emotion_shorthand_to_avoid`：写明符合叙述者口气的虚词、本场最可能的电报文病灶，以及至少两个不能代替情感过程的动作标签。
   - `no_fixed_short_sentence_ratio`：必须为 `true`，明确不设固定短句率、单句成段率或段长上限。
   - `manual_judgment`：说明该节如何在第一稿就保留原文同级情感颗粒和连续气口。

## 跨节事实状态链

`story_fact_state_ledger` 至少覆盖一条承重事实。每条写 `fact_id / initial_state / incompatible_states / transitions`；每次迁移写 `from_state / to_state / section_id / trigger_evidence`。验证器检查迁移首尾相接、小节不倒退、触发证据真实存在于细纲。怀孕、死亡、亲子或婚姻身份、证据取得、关键物件生成等事实一旦参与冲突，就必须入账。

`section_handoff_chain` 必须覆盖每一对相邻小节。每条交接写清 `elapsed_time / from_exit_state / to_entry_state / handoff_trigger / character_state_continuity / knowledge_continuity / object_continuity / location_continuity / unresolved_threads / outline_evidence / manual_judgment`。前后状态必须与相邻两节的 `scene_exit_state / scene_entry_state` 精确一致，禁止后节凭空换地点、换持有人、增加知情或制造新巧合。

融合仿写还必须填写 `auxiliary_subflow_flow_parity`。该表从绑定的 `拆文读取回执.json` 继承每个已选辅助 SF 的完整 `entry_state / required_sequence / knowledge_boundaries / object_lifecycle / exit_cause / end_state`，然后逐步写 `sequence_mappings`。步骤数量和顺序必须原样保留，每一步均需目标动作、所在小节、前置条件、触发、状态变化和细纲证据；只摘事件结果或删并步骤直接失败。

## 全局必填

`global_review` 必须明确：

- 已完整阅读所有选中原文的表演机制，而非只读拆书摘要；
- 已同时读取拆书资料的功能机制和原文对应桥段的场面颗粒度，不能只做功能映射；
- 已在正文前核对场景因果颗粒和跨节事实状态链，确认人物到场、知情、物件、制度与离场原因连续；
- 已逐节核对所有事件拍的前态、触发、权限和后态首尾相接；
- 已完成全部相邻小节的人物、知情、物件、地点和未决问题交接；
- 融合仿写已逐个验收辅助 SF 的完整步骤、知情边界、物件生命周期和出口状态；
- 已在正文前完成原文 BID / 关键子桥段流程全集；
- 已在正文前逐桥验收细纲对原文主情节和子情节流程的迁移；
- 已在正文前确认人物关系对陌生读者直接可懂；
- 已完成职业外壳白话翻译，不让术语承担情绪；
- 已逐节核对原文情绪流程、反刀时机和同级烈度；
- 已在正文前逐节完成首写生成契约，不从正文反向补回执；
- 已确认同一动作链、感知链和情绪反应链保持连续，断段有真实理由；
- 已在首写前建立句间关系和虚词策略，不用事后批量补连词伪造流畅；
- 迁移边界：完整参照结构、信息延迟、场内压力、物件/动作/关系推进机制，不复制原人物、职业、原句或完整情节壳；
- 细纲不是流程清单、证据排队表或分镜施工稿；
- 本书的场景分工如何避免同场结算全部问题。

## 双轨参照判定

每节必须同时回答两类问题：

- `拆书功能机制`：这一节在结构上承担什么功能，来自哪份拆书资产，为什么适用于当前故事。
- `原文场面颗粒度`：原文对应桥段不是“发生了什么功能”，而是“现场如何发生”：动作顺序、身体/物件/空间控制权、错答、旁观者、打断和场末余波。

以下情况直接失败：

- 只写“迁移《幼薇》高成本补救机制”，但没有说明原文里如何通过整夜翻找、找到残缺物、电话打断和离场完成补救失败。
- 只写“迁移行动验收”，但没有说明原文里如何用近身动作、可执行条件、第三人施压和再次站队完成判卷。
- 只写“迁移公开反噬”，但没有说明原文里公开场如何由对手欲望主动搭起、外部秩序如何接管、主角为什么不需要上台讲解。
- 细纲把功能机制翻成 `补钱 / 补日志 / 交钥匙 / 修物件` 等并列任务，没有原文级别的身体动作、错答、阻力和现场摩擦。

## 正文放行

正文放行命令必须同时携带本回执：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_write_release_gate.py" \
  draft \
  --writing-receipt 写作资产/写作规则读取回执.json \
  --source-receipt 写作资产/拆文读取回执.json \
  --ledger 写作资产/规则执行台账.json \
  --sequence-receipt 写作资产/顺序契约回执.json \
  --opening-contract 写作资产/开头承重契约回执_大纲.json \
  --outline-contract 写作资产/细纲表演验收回执.json \
  --profile profiles/{项目名}.project.profile.json
```

开头契约只验前屏功能顺序；顺序契约只验设定、细纲和正文的桥段先后；规则台账只验规则执行记录。三者均不能替代本闸门。本闸门专门验证“细纲能否写出活场面”。
