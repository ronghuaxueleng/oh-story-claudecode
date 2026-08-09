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
- 直接把全文情绪拍复制成情节拍，用一套 ID 和内容伪造双轨覆盖
- 情节拍库由回执填写者临时生成，没有绑定拆文阶段独立落盘的全文情节微拍总账
- 新稿情绪烈度低于原文，却用“控制权已经换主”冒充同级仿写
- 连续小节复制同一套场面颗粒度或人工判断，批量制造假通过回执
- 连续小节复制同一套原文情绪拍、触发和证据，只换目标桥段名称
- 只迁移主体原文部分 SF，或只挑每个 SF 中最显眼的一两类颗粒
- 用同一条目标细纲原句批量声称已经迁移全部局部颗粒，却不填写各字段迁移方法

## 强情绪仿写四硬闸

追妻、婚恋清算、白月光、替身、背叛等强情绪关系稿，正文前必须同时通过：

1. `relationship_legibility`：不用职业知识也能说清人物关系、偏心方向和具体伤害。
2. `emotion_intensity`：逐节填写 1-10 分烈度、具体羞辱/刺痛、情绪翻面和相对上一节的升级；强情绪稿不得低于 7。
3. `professional_shell_translation`：删除术语后冲突仍成立，且先让读者读懂关系伤害，再用职业动作把伤害做实。
4. `source_emotion_parity`：绑定选中原文真实片段，逐拍对齐原文与目标稿的情绪流程；每拍必须包含触发、关系位置变化、读者感受、烈度和证据。目标拍数、拍序、反刀拍、峰值拍不得变化，任何一拍的目标烈度不得低于原文。

“和原文一样”指情绪功能、顺序、反刀时机、峰值位置、场末余痛和读者体感烈度对齐，不复制原句、人物、职业或完整情节壳。不能用“整节总分相同”掩盖中间某一拍被削弱。

## 执行时机

设定与细纲完成后，且在任何正文首写、全文重写或正文大回炉前，必须先初始化并人工回填：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_outline_performance_contract.py" init \
  --project "{项目名}" \
  --outline "{项目目录}/小节大纲.md" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-original "拆文库/{辅助书一}/原文/{辅助书一}.txt" \
  --source-original "拆文库/{辅助书二}/原文/{辅助书二}.txt" \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json"
```

当前模型完整读取选中原文及细纲后，逐节回填，再运行：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_outline_performance_contract.py" validate \
  --outline "{项目目录}/小节大纲.md" \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json"
```

输出不是 `outline_performance_contract: passed` 时，禁止写正文。细纲或任一选中原文 SHA 变化后，旧回执立即失效。

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

先绑定 `写作资产/全文情节微拍总账.json`。该总账必须由拆文阶段从 L1 到 EOF 独立扫描生成，不得从情绪总账、BID 情绪子集或细纲验收回执反推。每拍至少包含：

- 独立 `P-*` ID，不得使用 `E-*`。
- `actor / action / object_or_receiver / pressure_or_trigger`。
- `control_change / information_change / consequence`。
- `source_range / source_evidence / bid_ids`；每拍最多归属一个 BID，桥外使用 `[]`。

总账须完整收录原文所有有效情节微拍，包括桥外 `bid_ids=[]` 的导语、过场、现实后果或尾声动作。情节拍与情绪拍可以引用同一原文句，但它们必须分别说清“外部事实怎样变”和“关系/读者体感怎样变”，不得整套同 ID、同序、等量复制。

第一张是 `source_bridge_flow_inventory`，用于列出主体原文 BID / 关键子桥段全集。它不得临时抽拍：每个 BID 的 `source_plot_beats` 必须与全文情节微拍总账中含该 `bid_id` 的原序子序列完全一致。每个桥段必须写清：

1. `source_path` 与 `source_sha256`：绑定原文文件。
2. `bridge_id` 与 `bridge_name`：例如 `BID-01 公开掉位与网络补台反杀`。
3. `source_required_sequence`：按情节拍逐项列出原文内不能打乱的全部动作顺序，数量与实际情节拍相等。
4. `source_must_keep_actions`：迁移时必须保留的全部动作、物件、空间、身份或权力变化，不设抽样数量。
5. `source_scene_granularity`：原文场面颗粒度，不是功能概括。
6. `source_plot_beats`：逐句提取桥段内全部有效情节拍。每拍填写 `beat_id / action / actor / pressure_or_trigger / control_change / information_change / consequence / evidence`，不得只摘高潮或主动作。
7. `source_plot_beat_completion_review`：当前模型确认动作换手、信息释放、短暂希望、选择、反刀和现实后果均已入账。
8. `source_end_state_change`：桥段结束时人物关系、现实位置或信息边界如何变化。
9. `cannot_merge_or_drop_reason`：为什么不能被合并成一句功能说明或删掉。

`source_required_sequence` 的项目数必须与 `source_plot_beats` 相等。不得设定最低拍数或推荐拍数；当前模型必须逐句读到桥段结束，原文实际存在多少有效拍，就登记多少拍。

`bid_ids=[]` 的桥外情节拍不得丢失。它们必须进入 `outside_bridge_plot_parity`，按全文原序一对一绑定目标拍、目标小节和细纲原句。若总账没有桥外情节拍，该表可为空；只要有一拍，就不得塞入首尾 BID 或省略。

桥段全集不能由回执填写者自行定义：

- `init` 会从每本选中原文对应的 `写作资产/桥段施工卡.md` 自动提取 `available_bridge_ids` 并绑定该文件 SHA。
- 第一本选中原文固定为 `primary`，`required_bridge_ids` 必须与施工卡全部 BID 完全一致，不能手工删减。
- 后续选中原文固定为 `auxiliary`，必须在 `selected_bridge_ids` 中显式列出本稿采用的子 BID。
- 每条库存通过 `source_path` 继承来源的 `primary / auxiliary` 角色，`bridge_id` 可带书名前缀，但必须保留可识别的 `BID-*`。
- 主体 `required_bridge_ids` 或辅助 `selected_bridge_ids` 任一未进入库存及对齐表，正文硬阻断。

第二张是 `outline_bridge_flow_parity`，用于证明每个原文桥段已经落进细纲。每个原文 `bridge_id` 都必须有且只有一条对齐记录，并填写：

1. `source_path / source_sha256`：绑定该桥段实际来自哪本选中原文。
2. `source_plot_beats / target_plot_beats`：分别列出全部原文情节拍和目标情节拍，字段与库存一致；原文拍必须原样继承库存。
   - `target_plot_beats` 必须已经是目标人物在目标场面中的真实动作拍。目标 `actor` 至少一名必须真实出现在该拍 `action/evidence`；不得把原文 `action` 加前缀、换标题或补一句“新稿以某物承接”后继续使用。
3. `plot_beat_mapping`：按原顺序一一填写 `source_beat_id / target_beat_id / status / adaptation_note`。状态只能是 `matched/adapted`，两拍不得指向同一目标拍。
4. `plot_granularity_parity_judgment`：人工说明为什么没有漏拍、并拍、压缩、弱化或用复合句吞拍。
5. `source_emotion_sequence / target_emotion_sequence`：逐拍填写 `role / trigger / relationship_position_change / reader_effect / intensity / evidence`。
   - 目标情绪拍保留原文 `beat_id / role / intensity` 与反刀、峰值位置；`trigger / relationship_position_change / evidence` 必须改写为目标世界。字段与原文完全相同，说明仍是原文分析而不是目标表演。
   - 每个 BID 的原文情绪拍集合必须与同书 `全文情绪颗粒总账.json` 的 `bid_ids` 完全一致。`bid_ids=[]` 的桥外拍不得塞入任一 BID，只能由全书分节情绪合同另行消费。
6. `source_reversal_beat / target_reversal_beat`：原文真实存在反刀时填写实际拍序并保持同位；原文没有则双方填 `0`，不得补造。
7. `source_peak_beat / target_peak_beat`：原文真实存在明确峰值时填写实际拍序并保持同位；原文没有则双方填 `0`，不得补造。
8. `reader_experience_parity / emotion_parity_judgment`：当前模型说明为什么目标桥段给读者的羞辱、刺痛、希望落空或反噬体感与原文同级。
9. `target_outline_sections / target_outline_evidence`：绑定目标小节及至少两条当前细纲原句。
10. `parity_status / adaptation_reason / missing_or_weakened_risk / manual_judgment`：状态只能是 `matched/adapted`，并说明替换边界、缩水风险和人工结论。

以下情况直接失败，必须先回细纲重构，禁止写正文：

- 原文某个 BID 没有进入 `outline_bridge_flow_parity`。
- 原文任一有效情节拍缺失、被合并、被压缩、顺序变化，或两个原文拍映射到同一个目标拍。
- 目标情节拍仍包含原文动作句面、原文专名或原文事件说明，只是在前面加“新稿承接/迁移/改写”。
- 目标情节拍的施事者没有出现在目标 `action/evidence`，只有泛化功能说明。
- `source_plot_beats` 与库存不一致，或多个情节拍复用同一句证据。
- `source_plot_beats` 不是全文情节微拍总账的真实 BID 子序列，或桥外情节拍未进入 `outside_bridge_plot_parity`。
- 情节拍 ID 与全文情绪拍 ID 重叠，或情节 `action` 只是情绪 `content / role / trigger` 换名。
- 原文 BID 虽已进入对齐表，但没有逐拍迁移情绪，或只给一个整桥烈度总分。
- 当前模型先套固定情绪角色表而没有逐句盘点原文实际变化；原文任一实际情绪拍被目标稿漏掉或合并；多个情绪拍复用同一句证据。
- 目标桥段改变原文反刀拍、峰值拍，或任一拍烈度低于原文。
- 目标情绪拍的触发、关系位移和证据仍与原文相同，或桥内拍集合不符合总账 `bid_ids` 的真实边界。
- 只对齐最虐的少数桥段，其余主体 BID 仍只写功能和动作。
- 主体桥段施工卡中的任一 BID 没有进入库存，或辅助显式选中的任一 BID 没有进入库存。
- `parity_status` 是 `missing / weakened / merged_unclear / only_function_mapped / pending`。
- 只写“迁移公开掉位 / 补救失败 / 公开反噬”，但没有细纲原句证明动作顺序、控制权变化和场末状态。
- 目标细纲把两个以上承重 BID 合并成一场，并且说不清哪个动作链、信息延迟和状态变化分别承担原文功能。
- 只证明新故事内部顺序合理，没有证明原文桥段流程如何迁移。

## 主体 SF 六类颗粒全量覆盖

主体原文的 `写作资产/子流程索引.jsonl` 是全量清单，不是抽样素材池。`init` 必须绑定该文件 SHA，并把全部 `SF-*` 写入 `source_subflow_granularity_coverage`。每个 SF 必须逐项覆盖：

1. `narrative_voice_and_attitude`：叙述者在这一局部场面的态度如何变化。
2. `sentence_relation_and_rhythm`：长短句、承接、加速和骤停如何组织。
3. `paragraph_breath_and_cut_points`：段落在哪里换气、断开和留白。
4. `dialogue_misfire_or_avoidance`：谁错答、回避、重复或把问题拽向别处。
5. `action_perception_emotion_weave`：动作、感知和情绪如何在同一链条里互相触发。
6. `narrator_interjection_and_roughness`：现场插嘴、口语棱角和有效毛边如何保留。

每个字段必须有 `target_outline_evidence / transfer_method / surface_copy_rejected=true`。每个 SF 还必须绑定目标小节，填写 `matched/adapted`、迁移边界和人工判断。缺任一 SF 或任一字段即失败；不能用 BID 已覆盖、七维全局基线已填写、情绪拍已对齐来替代。

## 逐节必填

每个真实小节都必须单独填写：

1. `irreversible_action`：本场唯一不可逆动作，不允许由多个并列结果代替。
2. `controlling_object`：本场唯一主控物件或空间控制点，必须服务人物争夺。
3. `source_function_mechanism`：绑定拆书资料中的功能机制，说明本节迁移的是公开掉位、私域换主、不可替代物爆体、高成本补救后再选错、行动验收、公开反噬、私人尾声等哪类功能；必须填写拆书资产路径、资产规则和本节采用理由。
4. `original_scene_granularity`：绑定选中原文具体桥段，写清原文场面颗粒度：谁先施压、谁抢/挡/松手、哪个物件或空间改归属、哪句台词逼出动作、旁观者或外部秩序如何改变现场。不能只写“参考原文节奏”。
5. `source_mechanism`：绑定一段选中原文，说明只迁移的表演机制，以及不复制人物、职业、原句和完整桥壳的改写边界。
6. `information_delay`：入场已知、本场只漏出什么、必须压到后场的事实分别是什么。
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

## 全局必填

`global_review` 必须明确：

- 已完整阅读所有选中原文的表演机制，而非只读拆书摘要；
- 已同时读取拆书资料的功能机制和原文对应桥段的场面颗粒度，不能只做功能映射；
- 已在正文前完成原文 BID / 关键子桥段流程全集；
- 已逐句盘清每个 BID 内全部有效情节拍，没有按预设数量抽样；
- 已在正文前逐桥验收细纲对原文主情节和子情节流程的迁移；
- 已在正文前逐项复核全部原文拍与目标拍的一对一映射；
- 已在正文前确认人物关系对陌生读者直接可懂；
- 已完成职业外壳白话翻译，不让术语承担情绪；
- 已逐节核对原文情绪流程、反刀时机和同级烈度；
- 已盘清原文全部实际情绪拍和同类重复次数，没有用预设角色表冒充完整情绪库存；
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
