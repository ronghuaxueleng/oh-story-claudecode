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
- 按来源数组下标、连续节范围或固定角色模板自动配对目标 E/P 拍；即使拍数、烈度和证据数量齐全，也属于语义错位
- 没有独立的 `写作资产/逐拍语义映射.json`，或装配器仍能在映射缺失时自行生成 `target_emotion_sequence / target_plot_beats`

## 强情绪仿写四硬闸

追妻、婚恋清算、白月光、替身、背叛等强情绪关系稿，正文前必须同时通过：

1. `relationship_legibility`：不用职业知识也能说清人物关系、偏心方向和具体伤害。
2. `emotion_intensity`：逐节填写 1-10 分烈度、具体羞辱/刺痛、情绪翻面和相对上一节的升级；强情绪稿不得低于 7。
3. `professional_shell_translation`：删除术语后冲突仍成立，且先让读者读懂关系伤害，再用职业动作把伤害做实。
4. `source_emotion_parity`：绑定选中原文真实片段，逐拍对齐原文与目标稿的情绪流程；每拍必须包含触发、关系位置变化、读者感受、烈度和证据。目标拍数、拍序、反刀拍、峰值拍不得变化，任何一拍的目标烈度不得低于原文。

“和原文一样”指情绪功能、顺序、反刀时机、峰值位置、场末余痛和读者体感烈度对齐，不复制原句、人物、职业或完整情节壳。不能用“整节总分相同”掩盖中间某一拍被削弱。

### 承重桥细拍承载预检

桥级逐拍回填前，必须先做人肉承载力预检。凡是某个数字节要承接主体 `BID-*`，当前节细纲必须先写成“可承载逐拍的细拍场”，再允许补 `target_plot_beats / plot_beat_mapping / target_emotion_sequence`。

最低口径不是“已经有主事件、子事件、场面单元”，而是至少满足：

- 当前节已经把桥内关键换手、物件争夺、错答/改口、见血或失手、旁观纠偏、半句信息、撤权与场末余波拆成连续 `细拍拆分`。
- 这些 `细拍拆分` 足以为桥内全部目标 `P-* / E-*` 提供独占证据，避免连续多拍复用同一句 `evidence`。
- 关键目标拍已经有真实可贴的 `actor_evidence` 与 `hurt_object` 落点，不必靠回执层临时抽象兜底。

若桥级校验报出连续的 `evidence 与前拍重复`、`actor_evidence 必须逐字来自本拍 evidence`、`hurt_object 必须在证据中出现` 这类错误，默认先判为“细纲承载不足”。此时必须先扩写 `小节大纲.md` 的细拍场，再回填桥级逐拍；禁止留在正式回执里硬凑语义补丁。

桥级逐拍人工回填前，当前模型还必须做一次最小人工预检，至少逐桥确认：

- 相邻 `target_emotion_sequence[*].evidence` 不得复用同一句细纲证据；若原文连续两拍极近，目标细纲也必须拆出两条可独占的目标证据。
- 相邻 `target_plot_beats[*].evidence` 不得复用同一句细纲证据；若连续两拍只能共用一句，默认判细纲承载不足，先扩细拍再回填。
- 每拍 `actor_evidence` 必须逐字来自该拍 `evidence`，且能直接证明当前填写的目标施事者；不能用后果句、总结句或旁观评价句冒充施事者证据。
- 若绑定细纲原句里施事者只写成“她 / 他 / 对方 / 那人”等代词，而桥级回填想把 `actor` 明确写成实名，默认先判“细纲施事者证据不足”。此时必须先回 `小节大纲.md` 把对应 `细拍拆分` 改成带实名或可唯一识别身份的原句，再回填桥级字段；禁止仅在正式回执里把 `actor / actor_evidence` 从代词硬改成实名。

逐拍实际填写时，不允许“先凭语义写一遍，再等校验器抖错”。当前模型必须按拍执行固定口令式核对：

1. 先圈定本拍唯一 `evidence`，确认它逐字存在于当前绑定细纲原句中。
2. 再从这句 `evidence` 里原样截取 `actor_evidence`；截不出来就停，先改细纲，不准继续填本拍。
3. 再写 `actor`，并确认 `actor_evidence -> actor` 的指向无需猜测；若只能靠上下文脑补，仍判不通过。
4. 最后再写 `action / object_or_receiver / hurt_object / consequence` 等解释字段；这些字段只能解释已被证据承载的事实，不能反过来替证据补施事者。

只要第 1-3 步任一步不成立，本拍不得进入正式回执。禁止整桥先批量写完 `actor / action`，再回头统一补 `actor_evidence`；这类写法默认高概率制造代词漂移、错施事者和证据不命中。

### 成批施事者贴证错误的来源与一次过禁令

同一桥一次出现多条 `actor_evidence` 错误，通常不是多个独立语义难题，而是回填方法已经失控。以下写法会成批制造错误，全部禁止：

- 分轮填写：第一轮只写 `actor / action`，第二轮再统一补 `actor_evidence`，导致证据与施事者脱节。
- 把受事者代词当成施事者证据：证据写“陆沉舟护住她”，却把“她”填成陆沉舟的 `actor_evidence`。
- 跨拍批量替换：看到多条报错后，在大 JSON 中把若干相同的“她”统一替换成某个人名，没有逐拍重读 `actor / evidence / action`。
- 只改一个字段：修改了 `actor` 或 `action`，却没有同步复核本拍 `evidence / actor_evidence / object_or_receiver`；或者修改细纲实名后，只更新情节拍，没有同步更新引用同句的情绪拍。

桥级 P 拍必须以单拍原子单元完成。每写完一拍，当场锁定并人工复述以下四元组：

`谁做(actor) -> 原句哪几个字证明(actor_evidence) -> 对谁/什么做(object_or_receiver) -> 完整原句(evidence)`

四元组未能逐字闭合时，本拍不得保存到侧车或正式回执。`actor_evidence` 不得跨拍批量生成、批量替换或统一修复；即使连续多拍施事者相同，也必须逐拍从各自证据原句中重新截取。校验器只负责最后确认，不得承担首次发现这类基础贴证错误的职责。

### 逐拍映射先于装配

细纲验收前必须建立 `写作资产/逐拍语义映射.json`。每个情绪拍至少填写 `source_beat_id / target_beat_id / target_outline_region / hurt_object / expectation_before / expectation_after / action_impulse_before / action_impulse_after / equivalence_reason / evidence`；每个情节拍至少填写 `source_beat_id / target_beat_id / actor / actor_evidence / object_or_receiver / pressure_or_trigger / action / control_change / information_change / consequence / adaptation_equivalence / evidence`。这些字段是人工语义裁决结果，不得由装配脚本按编号、位置或统一句式生成。装配器只允许做确定性序列化，并必须在运行前检查映射文件覆盖主体全集、证据独占和目标人物真实出现。

主体 E 拍除了源 ID 同序，还必须按目标正文区域同序消费：`导语 / opening -> 第1节 / section:1 -> ... -> 尾声 / epilogue` 只能向后推进，不能把较早 E 拍放到后节后又回到前节。每拍 `evidence` 必须真实位于声明的 `target_outline_region`；全文存在同句不能替代区域归属。该闸只拦跨节倒序和虚假章节绑定，不按拍号平均分节，也不允许借此删拍、并拍或改烈度。

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

若当前主要卡在桥级非逐拍人工字段，不想直接手改大 JSON，可先导出侧车骨架：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_bridge_review.py" export-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --output "{项目目录}/写作资产/桥级回填侧车.json"
```

当前模型在侧车里只补 `target_outline_sections / target_outline_evidence / plot_granularity_parity_judgment / emotion_parity_judgment / reader_experience_parity / parity_status / adaptation_reason / missing_or_weakened_risk / manual_judgment` 后，再确定性合并回正式回执：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_bridge_review.py" apply-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --input "{项目目录}/写作资产/桥级回填侧车.json"
```

该侧车只允许合并桥级非逐拍字段，不会替你生成 `target_plot_beats / plot_beat_mapping / source_emotion_sequence / target_emotion_sequence`，也不会放宽任何校验。

若当前主要卡在桥级逐拍字段，不想直接手改大 JSON，可先导出逐拍侧车骨架：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_bridge_review.py" export-beat-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --output "{项目目录}/写作资产/桥级逐拍侧车.json"
```

当前模型在侧车里只补：

- `target_plot_beats`
- `plot_beat_mapping`
- `target_emotion_sequence`
- `source_reversal_beat / target_reversal_beat`
- `source_peak_beat / target_peak_beat`

再确定性合并回正式回执：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_bridge_review.py" apply-beat-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --input "{项目目录}/写作资产/桥级逐拍侧车.json"
```

该侧车同样不会生成任何语义字段，也不会放宽桥级逐拍校验；它只负责让当前模型已写好的逐拍裁决安全回填。

如果在 `export-beat-template` 之后执行过 `rebind-outline`、正式回执被其他官方入口改写，或正式回执 SHA 发生变化，旧逐拍侧车立即失效。此时必须二选一：

1. 重新执行 `export-beat-template`，得到绑定当前 `receipt_sha256` 的新侧车后再继续修改。
2. 只对侧车顶层 `receipt_sha256` 做与当前正式回执完全一致的确定性刷新；刷新前后不得顺手改动任何人工语义字段。

禁止在 `receipt_sha256` 已失效的旧侧车上继续直接 `apply-beat-template` 试错。

若当前主要卡在节级场面验收字段，不想直接手改大 JSON，可先导出节级侧车骨架：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_section_review.py" export-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --output "{项目目录}/写作资产/节级回填侧车.json"
```

当前模型在侧车里按节补 `irreversible_action / controlling_object / source_function_mechanism / original_scene_granularity / source_mechanism / information_delay / character_missteps / interaction_exchange / conflict_carrier / relationship_legibility / emotion_intensity / professional_shell_translation / source_emotion_parity / forbidden_items / outline_evidence / scene_units / manual_judgment` 后，再确定性合并回正式回执：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_section_review.py" apply-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --input "{项目目录}/写作资产/节级回填侧车.json"
```

该侧车同样不会生成任何语义字段，只负责让当前模型已写好的节级人工裁决安全回填回正式回执。

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

`full_bridge` 只接受 `story-short-analyze.full-text-plot-ledger.v2`。v2 必须包含从 L1 到 EOF 连续覆盖的 `coverage_segments`、按原文顺序登记的 `source_plot_candidate_audit`，以及正向动作扫描与反向后果扫描的人工复核。当前写作模型还必须回到目标桥段原文抽查候选，不能把来源总账的自报完整性当事实。若原文中一次独立施压、接招、换权、信息新增、旁观秩序变化、文案发布、评论转向或现实后果在候选审计中找不到，来源总账即失效，必须退回拆文重建；不得继续装配细纲合同。

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
   - 每个 BID 的原文情绪拍集合必须与同书 `全文情绪颗粒总账.json` 的 `bid_ids` 完全一致。`全文情绪颗粒总账.json` 是桥级情绪边界的唯一真源；`桥段施工卡.md` 只负责说明承重件、顺序和为什么成立，不得反向覆盖总账边界。`bid_ids=[]` 的桥外拍不得塞入任一 BID，只能由全书分节情绪合同另行消费。
6. `source_reversal_beat / target_reversal_beat`：原文真实存在反刀时填写实际拍序并保持同位；原文没有则双方填 `0`，不得补造。
7. `source_peak_beat / target_peak_beat`：原文真实存在明确峰值时填写实际拍序并保持同位；原文没有则双方填 `0`，不得补造。
8. `reader_experience_parity / emotion_parity_judgment`：当前模型说明为什么目标桥段给读者的羞辱、刺痛、希望落空或反噬体感与原文同级。
9. `target_outline_sections / target_outline_evidence`：绑定目标小节及至少两条当前细纲原句。
   - `target_outline_evidence` 必须逐条精确命中当前 `小节大纲.md` 中真实存在的原始 bullet 文本，包含原有项目符号、标点、引号、箭头链和花括号标签；不得改写成“第X节主事件：...”后再回填。
   - 同一条证据来自 `- 主事件 / - 子事件 / - 场面单元` 哪一行，回执里就必须原样填写哪一行；只保留摘要内容、补自定义前缀、删掉句末标点或改动引号，校验一律按未命中处理。
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
- 为了凑齐首尾桥段，手工把 `bid_ids=[]` 的导语、过场、回忆、现实后果或尾声情绪拍塞进任一 BID。
- 桥段施工卡里登记的“情绪拍区间/桥内全集”与 `全文情绪颗粒总账.json` 不一致，却仍拿施工卡旧口径裁决回执正确性。
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

每个字段必须有 `target_outline_evidence / source_evidence_mappings / transfer_method / surface_copy_rejected=true`。`source_evidence_mappings` 必须与该字段的 `source_evidence` 全集同序一一对应；每条分别填写目标细纲原句、机制迁移判断和 `independently_realized=true`。即使两条源证据同属一个宽字段，只要分别承担捏疼、盯视、松手、抱走、错答、换气或即时插嘴等不同机制，就不得用同一句目标证据笼统包办。每个 SF 还必须绑定目标小节，填写 `matched/adapted`、迁移边界和人工判断。缺任一 SF、任一字段或任一源证据映射即失败；不能用 BID 已覆盖、七维全局基线已填写、情绪拍已对齐来替代。

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

## 推荐回填顺序

为减少“字段全空导致的假噪音”和来回返工，`full_bridge` 模式下推荐按以下顺序回填并校验：

1. 先补 `global_review`，把已读、已判边界和“细纲不是流程清单”的顶层确认项一次性写明。
2. 再核对主体 `全文情绪颗粒总账.json` 的 `bid_ids` 边界，确认桥外 `bid_ids=[]` 与各 BID 子序列真实成立；这里如果报错，先修来源账本或来源理解，不要先在回执里挪拍硬凑。
3. 再补 `outside_bridge_plot_parity` 与 `outline_bridge_flow_parity` 的非逐拍人工裁决层：`target_outline_sections / target_outline_evidence / parity_status / adaptation_reason / manual_judgment`。
4. 在桥边界稳定后，先检查承接该桥的数字节是否已经写成可承载逐拍的细拍场；若细拍密度不足、独占证据不足或关键动作仍只存在于摘要句，先扩细纲，不得直接补桥级逐拍字段。
5. 细拍承载通过后，再补 `target_plot_beats / plot_beat_mapping / source_emotion_sequence / target_emotion_sequence`。
6. 桥级逐拍通过后，再补逐节 `sections[*]` 场面验收与 `scene_units`，让每节先拥有真实的 E/P 承载位。
7. 节级场面验收通过后，再补 `写作资产/逐拍语义映射.json`，并运行固定的 `validate_semantic_beat_mapping.py validate` 命令。
7. 最后再补 `source_subflow_granularity_coverage` 与下游文字/情绪合同。

这只是推荐施工顺序，不是放宽条件。任何一层未 `passed`，都不得跳到正文。

当 `小节大纲.md` 在桥级或节级回填过程中发生变化时，先不要继续手工改顶层状态；使用官方重绑入口把旧 SHA 和旧通过态一次清干净：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_bridge_review.py" rebind-outline \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --outline "{项目目录}/小节大纲.md"
```

该命令会重写 `outline.path / outline.sha256`，并把 `reviewed_by_current_model=false`、`gate_status=pending`、`blocking_failures=[]` 一次重置。禁止保留旧 SHA 继续补桥内字段。

全部人工字段补齐、正式校验应通过时，再执行官方封口入口：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/manage_outline_bridge_review.py" seal-review \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --outline "{项目目录}/小节大纲.md"
```

`seal-review` 会先调用正式 `validate_outline_performance_contract.py`；只有真实无阻断时，才把 `reviewed_by_current_model=true` 和 `gate_status=passed` 落盘。禁止手工盲改顶层通过态。

## 聚焦阻断读取

当 `outline_performance_contract` 仍处于大面积 `blocked` 时，先把阻断按以下三类聚焦读取并排序，不要一上来平铺所有下游噪音：

1. `bridge_emotion_boundary`
   - 只看 `bridge 内拍集合不符合总账 bid_ids`、桥外拍误塞 BID、来源总账与桥段施工卡口径冲突。
   - 这类问题没清掉前，不进入桥级逐拍或节级 `scene_units` 细修。
2. `bridge_mapping_missing`
   - 只看 `target_plot_beats / plot_beat_mapping / source_emotion_sequence / target_emotion_sequence` 缺失、漏拍、并拍、改序。
   - 这类问题清掉前，不让节级合同或下游文字/情绪合同替桥级试错。
3. `section_scene_units_missing`
   - 只看各节 `scene_units`、逐节场面验收与节级承载位空壳。
   - 这类问题应放在桥边界和桥级逐拍之后修，避免节级证据先被错误桥边界带偏。

若当前脚本输出尚未自动分组，执行器也必须先人工把同轮阻断折叠成以上三类，再决定施工顺序；不要把所有报错按出现顺序混修。

## 推荐合并修复批次

桥级与节级阻断允许按一个连续修复批次执行，但不得跨过真实依赖顺序。推荐固定编排为：

1. `sync-source-emotions`
2. `batch_prewrite_blockers` 读取聚焦顺序
3. `export-template/apply-template` 补桥级非逐拍裁决
4. `export-beat-template/apply-beat-template` 补桥级逐拍裁决
5. `export-template/apply-template`（节级）补 `sections[*] / scene_units`
6. `rebind-outline`
7. `validate_outline_performance_contract.py validate`
8. `seal-review`

这里的“合并”只指连续执行批次，不指把桥级、节级和顶层状态揉成一张回执手工乱改。桥级边界未稳时，不得先补 `scene_units`；顶层 `passed` 未经正式校验，不得提前封口。

## 双轨参照判定

每节必须同时回答两类问题：

- `拆书功能机制`：这一节在结构上承担什么功能，来自哪份拆书资产，为什么适用于当前故事。
- `原文场面颗粒度`：原文对应桥段不是“发生了什么功能”，而是“现场如何发生”：动作顺序、身体/物件/空间控制权、错答、旁观者、打断和场末余波。

以下情况直接失败：

- 只写“迁移主体原书的高成本补救机制”，但没有说明原文里如何通过具体动作、阻力、打断和离场完成补救失败。
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

### 逐场语义资产

`scene_units` 不得由装配器从每场首尾两条证据自动生成。每场必须先由当前模型落盘人工逐场语义资产，至少包含具体人物、进场压力、三步施压与接招、转折动作、可见后果、余波和读者情绪路径，再由装配器原样消费。

以下表达只算占位模板，不能通过：`一方用……施压`、`另一方用错答或抢物被迫接招`、`现场以……出现可见换权`。三步链必须能回答谁对谁做了什么、对方如何接招、哪一动作改变了现场结果。逐场资产未 `approved`、缺场或仍含泛化链时，先回修资产和细纲表演合同，不得在正文场面计划中临时补齐。

### 通用执行器与项目资产边界

新项目在目录命名和读取门禁通过后，可初始化空资产：

```bash
python3 "$SKILL_ROOT/scripts/init_project_writing_assets.py" \
  --project-dir "{项目目录}" \
  --project-name "{项目名}"
```

该命令只复制 `assets/` 中的项目配置、逐拍和逐场空模板，三份资产均不得覆盖已有文件。逐拍/逐场初始状态必须为 `pending`，由当前模型逐项填写后才能改为 `approved`。

项目 profile 来源策略由通用脚本消费 `项目写作配置.json`：

```bash
python3 "$SKILL_ROOT/scripts/apply_project_profile_policy.py" \
  --config "{项目目录}/写作资产/项目写作配置.json"
```

逐节计划必须直接复制已通过的上游 `scene_units`：

```bash
python3 "$SKILL_ROOT/scripts/create_section_plan.py" \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --beat-mapping "{项目目录}/写作资产/逐拍语义映射.json" \
  --section N \
  --output "{项目目录}/写作资产/当前节计划/第N节.json"
```

场面合同使用目标 `TE-*` 时，计划生成器必须从已批准的逐拍语义映射按显式 ID 查回主体 `E-*`，并同时保留 `target_emotion_beat_ids` 供追溯。禁止按数组位置、编号尾数或字符串替换猜配；缺映射、重复映射或映射未批准均阻断。

书名、主体/辅助来源、选中 BID 和路径属于项目配置；E/P 拍、场面链和情绪等价理由属于项目人工语义资产。通用脚本不得硬编码这些单书信息，项目也不得长期保留复制自某本书的几百行装配脚本作为下一本书模板。
