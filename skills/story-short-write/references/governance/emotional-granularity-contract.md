# 全文情绪颗粒度合同

本合同解决“桥段和句法都像原文，正文仍然白、平、没情感”的问题。它只检查首稿是否消费主体原文的情绪生成机制，不执行去 AI 味。

## 写前合同

正文放行前初始化 `写作资产/全文情绪颗粒度契约回执.json`。每个数字小节必须绑定一段主体原文真实连续片段，并逐拍填写：

1. `entry`：人物带着什么期待、惯性或误判进入。
2. `pain`：具体动作、称呼、物件或站位如何刺痛。
3. `hope_or_resistance`：人物是否仍有希望、争夺或反抗。
4. `reversal`：对手怎样再次选错或把希望反刀。
5. `peak`：失控动作或同级强度动作在哪里兑现。
6. `afterpain`：场末余痛怎样留下，不用主题句盖章。

每拍都写 `触发 / 关系位置变化 / 读者体感 / 1-10 烈度 / 原文或细纲证据`。目标稿逐拍烈度不得低于主体原文，不能只比较整节均分。

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

- 六拍真实正文引句与源/目标烈度。
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
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" bind-outline \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --outline "{项目目录}/小节大纲.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" validate-prewrite \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --outline "{项目目录}/小节大纲.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" bind-draft \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --draft "{项目目录}/正文.md"
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_emotional_granularity_contract.py" validate-draft \
  --receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --draft "{项目目录}/正文.md"
```

任一命令未输出 `passed`，不得开始正文或宣称初稿完成。
