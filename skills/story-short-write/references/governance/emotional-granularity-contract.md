# 全文情绪颗粒度合同

`full_bridge` 只接受 `story-short-analyze.full-text-emotion-ledger.v2`。来源总账除逐行 `coverage_segments` 外，必须含 `source_emotion_candidate_audit`：原文每次期待对象、受伤对象、关系位置、行动冲动或读者预期变化，都要么唯一绑定独立 E 拍，要么绑定同一不可拆情绪链并给出具体理由。当前写作模型还必须回看目标桥段原文抽查候选；总账自报完整、拍数对齐或合同通过，都不能证明源文情绪颗粒没有先在拆文阶段缩水。

本合同解决“桥段和句法都像原文，正文仍然白、平、没情感”的问题。它只检查首稿是否消费主体原文的情绪生成机制，不执行去 AI 味。

## 写前合同

正文放行前必须先绑定主体拆文的 `写作资产/全文情绪颗粒总账.json`，再初始化目标项目的 `写作资产/全文情绪颗粒度契约回执.json`。全文总账必须由拆文阶段从 L1 到 EOF 逐行建立，先于 BID 归纳，并包含导语、暖场、过场、回忆、现实后果、尾声以及 `bid_ids=[]` 的非 BID 情绪拍。写作阶段不得重新按 BID 筛拍，也不得用节选片段冒充全文全集。

初始化只创建空列表，不得预生成固定角色格。每个数字小节从全文总账领取一段连续 `beat_id` 子序列；所有小节的 `source_emotion_beats` 合并后，必须与总账 `beats` 全集完全同序相等。总账有几拍，目标就必须承接几拍，同类或重复情绪仍各自保留。

同一主体桥跨越多个目标数字节时，细纲合同可以在桥内各节保留同一份桥级允许集合，但正式情绪装配不得把该集合复制给每一节。装配器必须先以桥级 `source_emotion_sequence` 限定合法 E 拍，再按 `逐拍语义映射.target_outline_region` 将每拍唯一分流到对应数字节；跨节重复领取、整桥复制或区域不匹配均阻断。

每个来源拍填写稳定 `beat_id / role / content / trigger / relationship_position_change / reader_effect / intensity / narrative_function / bid_ids / source_evidence`，并与全文总账逐字段相等。`role` 描述该拍在这段原文里的实际作用，不从预设目录挑选；写作合同不得重新概括、改写或美化来源拍。

目标细纲沿用原文全部 `beat_id / role / intensity`、实际角色和原顺序，并逐拍填写 `target_outline_region / target_story_adaptation / trigger / relationship_position_change / reader_effect / outline_evidence`，以及 `hurt_object / expectation_before / expectation_after / action_impulse_before / action_impulse_after / equivalence_reason`。后六项必须由当前模型针对目标现场人工裁决：明确谁受伤、这一拍前后还在期待什么、人物下一步想做什么，以及如何由动作而非烈度数字完成迁移。按数组下标、`enumerate`、第 N 句或统一模板批量填充，均视为未迁移。原文有几拍，目标就必须有几拍；相近或重复情绪仍各自保留，不能合并。原文真实存在反刀或峰值时记录实际拍序，不存在则双方记 `0`，不得为了通过合同补造情绪。

原文导语拍的 `target_outline_region` 固定为 `opening`，证据必须位于目标 `## 导语`；原文尾声拍固定为 `epilogue`，证据必须位于目标 `## 尾声`。其余拍进入领取它的 `section:N`，数字节标题可写 `## N.` 或 `## N. 标题`。不得把桥外首尾拍塞进第一节或最后一节凑齐 ID。

目标稿逐拍烈度必须与主体原文精确相等，不能只比较整节均分，也不能把低烈度铺垫统一抬高成峰值。全书不同拍不得复用同一句原文、细纲或正文证据；去除标点后不足六字的细纲词组不能充当独占证据。

每节必须填写 `turning_point_selection_review`，点名反刀和峰值对应的实际 `E-*` ID，并以期待、关系位置或行动冲动的转折为依据。禁止用最高烈度、章末位置或角色名自动猜测反刀/峰值。原文一拍只能对应一个目标拍；不得拆分一拍虚增目标拍，也不得合并多拍。

`target_evidence_coverage_review` 必须实际包含本拍目标 `trigger` 和 `relationship_position_change`，并确认独占证据覆盖触发、动作和关系后果的完整链。泛化的“已检查 / 已覆盖”不算人工判定；证据只覆盖原拍一半动作时，必须先回写细纲。来源片段或证据跨行时，验证前统一把 `CRLF / CR / LF` 规范化为 `LF`；字面内容仍必须与原文一致。

辅助书只供应情节或现实后果时，在细纲表演契约使用 `emotion_transfer_policy: plot_mechanism_only`：其已选 BID 仍必须建立完整 P 拍库和等数目标映射，但不迁移辅助书 E 拍、反刀、峰值或正文声线。主体原文必须使用 `primary_full_emotion`，不得借该模式缩减情绪全集。

验证器通过只证明字段、顺序、区域、烈度和证据约束成立，不证明目标情绪在语义上真的发生。当前模型必须逐拍人工判断：现实触发是否出现，受伤对象是否一致迁移，关系位置是否改变，行动冲动和读者预期是否按原轮廓变化。`hurt_object` 必须在独占证据中真实出现；前后期待和行动冲动必须发生可解释变化；`I9-I10` 必须说明同级不可逆损失、关系掉位或读者预期翻转。合同写得完整而细纲现场没有兑现，仍须判失败并回写细纲。

### 逐拍语义映射资产

细纲验收前必须先落盘 `写作资产/逐拍语义映射.json`，按 `E-*` 与 `P-*` 分列保存每一拍的目标字段。标准起盘顺序是先运行 `validate_semantic_beat_mapping.py export-template`，按主体 E/P 总账全集和已通过细纲导出完整真源骨架，只把确定性绑定、来源字段和区域归属写入正式文件；若当前 `细纲表演验收回执.json` 已有正式 `target_emotion_sequence / target_plot_beats`，默认再运行 `validate_semantic_beat_mapping.py sync-from-outline-contract`，把这些已通过细纲的现成裁决同步回映射真源，减少二次抄写；随后再由当前模型逐拍补全剩余人工语义字段，最后运行 `validate_semantic_beat_mapping.py validate`。装配器只能读取并校验该文件后序列化回执，不能从来源数组、节序号或证据池位置推导目标语义。映射资产缺拍、重复证据、施事者不在证据中，或把施工说明当现场事实时，禁止生成正式合同。

`sync-from-outline-contract` 只是“正式真源回收”入口，不是自动放行入口。它只能同步已通过细纲回执里现成的拍级裁决，不能替代当前模型补齐 `hurt_object / expectation_before / expectation_after / action_impulse_before / action_impulse_after / actor_evidence / adaptation_equivalence` 等仍未闭合的人工字段；同步后仍必须跑正式 `validate`，未通过前不得进入正文前合同装配。尤其是 `opening / epilogue` 拍，如果细纲回执里还没有完整目标证据与人工字段，同步不会替你补完，必须单独人工闭合。

`sync-from-outline-contract` 还会按目标证据在 `小节大纲.md` 中的真实位置重算 `target_outline_region`，并在 P 拍上尽量把细纲回执里的局部 fragment 回收到所在完整 bullet，方便当前模型定位原句。但这一步只负责“回收与定位”，不负责“独占与闭合”：若完整 bullet 仍被多个相邻拍复用，或仍截不出稳定 `actor_evidence`，必须停在细纲层扩细拍，或由当前模型逐拍重选独占证据；禁止在未改真源、未改细纲、未补人工字段的情况下反复空跑同步和校验。同一组报错复现时，默认直接判“细纲承载不足”或“该拍仍未人工闭合”，而不是继续磨脚本。

进入 `逐拍语义映射` 人工收口时，推荐固定顺序是：先补 `opening / epilogue` 的空壳 E 拍，再处理当前最前面连续报错的 `P-*`。若前一组错误尚未闭合，不得提前装配书级情绪合同或跳去后面桥节试错。

如果为了消除上述报错而回修了 `小节大纲.md`，后续必须按固定重建链重走：先重绑 `细纲表演验收回执.json` 的细纲 SHA 和验收态，再重导或重同步 `写作资产/逐拍语义映射.json`，最后单独执行正式 `validate`。不得只改细纲文本后继续沿用旧的细纲回执、旧侧车或旧映射通过态。

`小节大纲.md` 的区域识别依赖纯标题行。允许的节标题形态只有 `## 导语`、`## N.` 或 `## N. 标题`、`## 尾声`；标题行后必须先空一行，再进入 `- ` bullet。若把首条 bullet、说明句或作者注释吞进标题匹配块，下游 `target_outline_region` 与证据区域校验会被污染，按细纲格式错误处理。

本合同同时承担最终正文情节拍兑现，但不负责生成情节拍库。情节拍库只能来自拆文阶段独立落盘的 `写作资产/全文情节微拍总账.json`，并经细纲表演验收逐拍改写为目标情节拍。每节写前从已通过的 `细纲表演验收回执.json` 领取归属本节的全部目标情节拍，写入 `required_plot_beats`；正文放行门禁将全书这些 `P-*` 与细纲回执的目标拍全集按顺序比对。写后在 `plot_beat_reviews` 中逐拍绑定独占正文引句和现实后果。任一细纲拍未领取、重复领取、改序或正文无证据，均阻断。

`P-*` 验收不得退化成编号覆盖。逐拍语义映射必须原样携带来源总账的施事者、动作对象、触发压力、动作、控制权变化、信息变化和现实后果，并分别填写目标等价判断。上述来源快照、目标语义和人工判等必须完整进入 `required_plot_beats`。最终 `plot_beat_reviews` 对每拍至少填写 `source_beat_id / expected_semantics / target_quotes / action_realization_judgment / control_change_realization_judgment / information_change_realization_judgment / consequence_judgment / parity_status`；`parity_status` 只接受 `matched/adapted_equal`。编号存在但语义串拍、后果缩水、并拍或摘要化时必须回正文，不能通过改回执放行。

情绪 `E-*` 与情节 `P-*` 是两条独立序列。数量相等不自动判错，但整套 ID 相同、情节动作仅复述情绪作用，或回执填写者未能指向独立情节总账时，按混轨伪覆盖直接阻断。

每节另须计划：

- 即时主观判断。
- 不体面念头或情绪破绽。
- 身体或物件动作。
- 旧伤触发；不适用时说明原因。
- 对手持续施压。
- 失控动作或不改变角色伦理的同级替代动作。

E/P 拍是场面内的运动颗粒，不是可以逐句打勾的事件标签。写前必须把本节全部拍同序组织成 `1-3` 个完整场面；每场必须有进场压力、人物想护住的对象、至少三步施压与接招、转折动作、可见后果和情绪余波。只写“某人来了 / 某人拿走了 / 我很难过 / 关系因此变了”，即使 ID、顺序和引句都齐全，也按“事件概括化”失败。

当前模型必须在小节提交前回答：读者是在哪一个可感的动作前抱有什么期待，这个动作如何改变了人物的身体、站位、物件或回答范围，以及后一拍如何在前一拍留下的疼痛上继续。答不出来时不得靠补一句心理或拉长旁白修复，必须重写整个场面。

## 首稿政策

回执必须固定：

- `mode=source_dominant_first_draft`
- `primary_source_prose_dominant=true`
- `anti_ai_cleanup_applied_during_first_draft=false`
- `ai_audit_applied_during_first_draft=false`
- `source_like_direct_emotion_preserved=true`
- `auxiliary_prose_voice_allowed=false`
- `surface_copy_rejected=true`

明显 GPT 壳只能按“主体原文声线偏移”修正，不能触发整篇清洗。

## 写中与写后回填

固定按“读本节合同 -> 在独立暂存稿中一次写完本节 -> 提交前立即回填本节 -> `commit-section` 写入正文 -> 下一节”执行。每节正文复核至少包含：

每节回填必须先落到 `写作资产/逐节验收/第N节.json` 的 `emotion_review`，并通过 [逐节正文进度硬闸](section-progress-gate.md) 的 `commit-section N`。本节 E/P 拍不全、顺序不对、事件只有概括或真实引句不在当前节时，禁止写入正文和开始下一节。

- 全部实际情绪拍的真实正文引句与源/目标烈度，`beat_id`、数量和顺序必须与写前合同一致。
- 全部 `required_plot_beats` 的真实正文引句与现实后果，数量和顺序必须与细纲情节拍全集一致。
- 每个 `required_plot_beats` 必须同时保留来源七项语义快照、目标七项语义和五项人工等价判断；每个 `plot_beat_reviews` 必须分别证明动作、换权、信息变化与现实后果已经落入正文。
- 即时主观判断引句。
- 不体面念头或情绪破绽引句。
- 身体/物件动作引句。
- 对手施压引句。
- 失控或同级替代动作引句。
- 旧伤触发证据或不适用理由。
- `target_not_lower_intensity=true`。
- `anti_ai_cleanup_applied_during_first_draft=false`。

不能用“这一节情绪很强”代替逐拍证据，也不能用付款、邮件、权限撤销等程序动作冒充情绪峰值。

## 命令

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" init \
  --project "{项目名}" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" bind-outline \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --outline "{项目目录}/小节大纲.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" export-plan-template \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --output "{项目目录}/写作资产/情绪颗粒逐节人工计划.json" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --beat-mapping "{项目目录}/写作资产/逐拍语义映射.json" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" apply-section-plan \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --plan "{项目目录}/写作资产/情绪颗粒逐节写前侧车.json" \
  --consume
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" assemble-section-plan \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --plan "{项目目录}/写作资产/情绪颗粒逐节人工计划.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --beat-mapping "{项目目录}/写作资产/逐拍语义映射.json" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --consume
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" validate-prewrite \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --outline "{项目目录}/小节大纲.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" bind-draft \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --draft "{项目目录}/正文.md" \
  --section-progress "{项目目录}/写作资产/逐节正文进度.json"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" validate-draft \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --draft "{项目目录}/正文.md" \
  --section-progress "{项目目录}/写作资产/逐节正文进度.json"
```

`--source-original` 与 `--source-emotion-ledger` 都属于强制显式输入。即使合同回执已经绑定主体原文和情绪总账，执行 `assemble-section-plan / validate-prewrite / validate-draft` 时也不得省略；脚本要校验的是“本次命令输入 + 回执绑定 + 当前文件”三方一致，而不是只信回执。

`export-plan-template` 是情绪逐节人工计划的官方导出入口。它会从正式情绪合同、逐拍语义映射和细纲表演回执中 deterministic 地导出待补骨架，并附带 `editor_hints`：`field_fill_order`、当前节 `emotion_beats / plot_beats` 短预览、来源反刀/峰值编号，以及细纲摘录统计。它只负责查料与定位，不得自动填写 `manual_judgment / turning_point_selection_review / source_emotion_beat_completion_review / plot_beat_completion_review` 或六个计划字段。

人工阶段默认优先导出“窄切片计划”，不要直接打开整份大计划：优先运行 `export-plan-template --next-pending`，只导出当前正式情绪合同里第一条 `status!=passed` 的待补节；明确要回补指定节时，再用 `export-plan-template --section-id N` 只导出该节。只有需要全量巡检、统一复核多节顺序或排查来源异常时，才导出整份计划。

若当前条计划已经补完，还要立刻接着补下一条，优先在本次 `assemble-section-plan --consume` 上追加 `--refresh-next-output {下一条计划路径}`。脚本会先写回当前正式情绪合同，再基于最新正式回执自动导出下一条待补节；如果已经没有 pending 节，则不会再导出新计划。默认不要手工再跑一次 `export-plan-template --next-pending`。

人工计划里的 `status` 是导出骨架字段，不是人工语义字段。`assemble-section-plan` 只有在当前节全部必填人工字段、E/P 显式 ID、反刀/峰值和上游绑定均通过后，才确定性把正式合同中的当前节状态写为 `passed`；执行器不得额外手改模板状态，也不得让模板初始的 `pending` 覆盖已完成装配结果。

情绪逐节人工计划默认固定顺序是：`export-plan-template -> 人工补当前节计划字段与裁决说明 -> assemble-section-plan --consume -> validate-prewrite`。进入这条链后，不再把临时脚本用于反查 `E/P` 对应、桥外 opening/epilogue 归属、峰值、反刀或场面统计；这类定位信息应直接消费官方 `editor_hints`。

`apply-section-plan` 只负责把当前模型已人工完成的 `section_contracts` 原样合并进已绑定细纲的合同。侧车可按原序只提交当前完成的小节，未提交小节保持 pending；侧车必须绑定当前细纲 SHA，并声明未使用脚本生成语义。入口不抽情绪拍、不选择原文证据、不推导目标拍，也不自动写入 `passed`；九节的全集、顺序、烈度和区域证据仍由全书 `validate-prewrite` 强制校验。标准流程追加 `--consume`，成功后仅保留消费回执；正式情绪合同继续保存全部逐拍人工颗粒。

情绪计划侧车与正式 `全文情绪颗粒度契约回执.json` 也受严格串行约束：同一路径上的 `export-plan-template / assemble-section-plan / apply-section-plan / validate-prewrite` 必须按 `export -> assemble|apply -> validate` 单独顺序执行。禁止并行触碰同一正式回执或同一计划文件，禁止在旧计划文件已失效时继续补写。

`bind-draft` 必须位于逐节进度闸 `final_ready` 之后。它会绑定最终全文 SHA 并重建骨架；当前模型随后必须直接基于最终正文逐节填写情绪引句、触发、关系位移、读者效应与等价裁决。默认延后逐节回执只提供确定性绑定，不能被当成已验证语义直接合并；脚本也不得批量生成情绪引句或裁决。

任一命令未输出 `passed`，不得开始正文或宣称初稿完成。
