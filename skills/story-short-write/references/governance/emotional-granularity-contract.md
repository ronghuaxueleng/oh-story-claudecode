# 全文情绪颗粒度合同

本合同解决“桥段和句法都像原文，正文仍然白、平、没情感”的问题。它只检查首稿是否消费主体原文的情绪生成机制，不执行去 AI 味。

## 写前合同

正文放行前必须先绑定主体拆文的 `写作资产/全文情绪颗粒总账.json`，再初始化目标项目的 `写作资产/全文情绪颗粒度契约回执.json`。全文总账必须由拆文阶段从 L1 到 EOF 逐行建立，先于 BID 归纳，并包含导语、暖场、过场、回忆、现实后果、尾声以及 `bid_ids=[]` 的非 BID 情绪拍。写作阶段不得重新按 BID 筛拍，也不得用节选片段冒充全文全集。

初始化只创建空列表，不得预生成固定角色格。每个数字小节从全文总账领取一段连续 `beat_id` 子序列；所有小节的 `source_emotion_beats` 合并后，必须与总账 `beats` 全集完全同序相等。总账有几拍，目标就必须承接几拍，同类或重复情绪仍各自保留。

每个来源拍填写稳定 `beat_id / role / content / trigger / relationship_position_change / reader_effect / intensity / narrative_function / bid_ids / source_evidence`，并与全文总账逐字段相等。`role` 描述该拍在这段原文里的实际作用，不从预设目录挑选；写作合同不得重新概括、改写或美化来源拍。

目标细纲沿用原文全部 `beat_id / role / intensity`、实际角色和原顺序，并填写 `target_outline_region / target_story_adaptation / trigger / relationship_position_change / reader_effect / outline_evidence`。目标三个语义字段与迁移说明必须具体写成新书人物、动作、关系和读者预期，不能照抄来源分析。原文有几拍，目标就必须有几拍；相近或重复情绪仍各自保留，不能合并。原文真实存在反刀或峰值时记录实际拍序，不存在则双方记 `0`，不得为了通过合同补造情绪。

原文导语拍的 `target_outline_region` 固定为 `opening`，证据必须位于目标 `## 导语`；原文尾声拍固定为 `epilogue`，证据必须位于目标 `## 尾声`。其余拍进入领取它的 `section:N`，数字节标题可写 `## N.` 或 `## N. 标题`。不得把桥外首尾拍塞进第一节或最后一节凑齐 ID。

目标稿逐拍烈度必须与主体原文精确相等，不能只比较整节均分，也不能把低烈度铺垫统一抬高成峰值。全书不同拍不得复用同一句原文、细纲或正文证据；去除标点后不足六字的细纲词组不能充当独占证据。

每节必须填写 `turning_point_selection_review`，点名反刀和峰值对应的实际 `E-*` ID，并以期待、关系位置或行动冲动的转折为依据。禁止用最高烈度、章末位置或角色名自动猜测反刀/峰值。原文一拍只能对应一个目标拍；不得拆分一拍虚增目标拍，也不得合并多拍。

`target_evidence_coverage_review` 必须实际包含本拍目标 `trigger` 和 `relationship_position_change`，并确认独占证据覆盖触发、动作和关系后果的完整链。泛化的“已检查 / 已覆盖”不算人工判定；证据只覆盖原拍一半动作时，必须先回写细纲。来源片段或证据跨行时，验证前统一把 `CRLF / CR / LF` 规范化为 `LF`；字面内容仍必须与原文一致。

辅助书只供应情节或现实后果时，在细纲表演契约使用 `emotion_transfer_policy: plot_mechanism_only`：其已选 BID 仍必须建立完整 P 拍库和等数目标映射，但不迁移辅助书 E 拍、反刀、峰值或正文声线。主体原文必须使用 `primary_full_emotion`，不得借该模式缩减情绪全集。

验证器通过只证明字段、顺序、区域、烈度和证据约束成立，不证明目标情绪在语义上真的发生。当前模型必须逐拍人工判断：现实触发是否出现，受伤对象是否一致迁移，关系位置是否改变，行动冲动和读者预期是否按原轮廓变化。合同写得完整而细纲现场没有兑现，仍须判失败并回写细纲。

本合同同时承担最终正文情节拍兑现，但不负责生成情节拍库。情节拍库只能来自拆文阶段独立落盘的 `写作资产/全文情节微拍总账.json`，并经细纲表演验收逐拍改写为目标情节拍。每节写前从已通过的 `细纲表演验收回执.json` 领取归属本节的全部目标情节拍，写入 `required_plot_beats`；正文放行门禁将全书这些 `P-*` 与细纲回执的目标拍全集按顺序比对。写后在 `plot_beat_reviews` 中逐拍绑定独占正文引句和现实后果。任一细纲拍未领取、重复领取、改序或正文无证据，均阻断。

情绪 `E-*` 与情节 `P-*` 是两条独立序列。数量相等不自动判错，但整套 ID 相同、情节动作仅复述情绪作用，或回执填写者未能指向独立情节总账时，按混轨伪覆盖直接阻断。

每节另须计划：

- 即时主观判断。
- 不体面念头或情绪破绽。
- 身体或物件动作。
- 旧伤触发；不适用时说明原因。
- 对手持续施压。
- 失控动作或不改变角色伦理的同级替代动作。

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

固定按“读本节合同 -> 写本节 -> 立即回填本节 -> 下一节”执行。每节正文复核至少包含：

- 全部实际情绪拍的真实正文引句与源/目标烈度，`beat_id`、数量和顺序必须与写前合同一致。
- 全部 `required_plot_beats` 的真实正文引句与现实后果，数量和顺序必须与细纲情节拍全集一致。
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
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" validate-prewrite \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --outline "{项目目录}/小节大纲.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" bind-draft \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --draft "{项目目录}/正文.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" validate-draft \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --draft "{项目目录}/正文.md"
```

任一命令未输出 `passed`，不得开始正文或宣称初稿完成。
