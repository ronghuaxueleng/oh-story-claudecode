# 全文文字颗粒度合同

本合同只处理成文语言，不处理剧情桥段。`场面颗粒度` 与 `文字颗粒度` 必须分开：

- 场面颗粒度回答谁先动、物件如何换主、情绪怎样升级。
- 文字颗粒度回答原文怎样选词、组句、断段、接话、插嘴和保留有效毛边。

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

## 全文覆盖

正文写作时逐节维护 `section_reviews`，每个数字小节必须：

- 引用至少 2 条本节目标原句。
- 引用至少 2 条主体原文声线锚。
- 复核全部七个文字维度。
- 明确 `source_voice_preserved=true`。
- 明确 `functional_alignment_used_as_prose_proof=false`。
- 明确 `extra_ai_shell=false`。
- 写出原文与目标稿的具体句面对照，不能只写“已检查”。

不同小节不得复用完全相同的 `source_anchors` 组合，也不得复用完全相同的 `comparison`。逐节复核必须使用与该节实际场面相符的主体声线锚，不能用两条万能原句给全书批量盖章。

除逐节七维复核外，`source_subflow_reviews` 必须覆盖主体 `子流程索引.jsonl` 的全部 `SF-*`。每个 SF 的六类局部颗粒都要分别填写：

- `target_sections`：实际消费该颗粒的正文数字小节。
- `dimension_transfers.{field}.target_quotes`：绑定小节中的真实正文原句。
- `dimension_transfers.{field}.source_evidence`：必须与该 SF 字段在主体索引中的全部证据完全一致，不得只挑最容易迁移的一条。
- `dimension_transfers.{field}.evidence_mappings`：每条主体证据必须单独绑定目标正文原句和句面对照，映射数量与顺序必须和主体字段证据一致。
- `dimension_transfers.{field}.comparison`：说明目标句面如何消费该局部颗粒，而非只对齐剧情功能。
- `dimension_transfers.{field}.surface_copy_rejected=true`：确认没有复制原人物、职业、原句或完整事件壳。

任一 SF、任一局部颗粒或任一已抽取原文证据没有正文对照，`validate-draft` 必须失败。全局七维都出现过，不等于主体原文颗粒已经全量消费。

语义回填还必须满足：

- `target_section_rationale` 逐 SF 说明为什么由这些正文小节消费，禁止按 `SF-01 -> 第1节` 机械顺排。
- `semantic_review_method=current_model_manual`，且 `automation_used_for_semantic_judgment=false`。
- 同一组目标句跨多个颗粒字段复用时，每个字段分别填写 `cross_dimension_reuse_justification`，说明该句在本字段承担的不同语言作用；复用理由不得同文复制。
- 六类字段的 `comparison` 与逐证据 `evidence_mappings[].comparison` 必须具体到句面作用。仅替换 SF 编号、字段名或章节号的文本按模板重复处理并阻断。
- 不同 SF 的目标小节理由和人工裁决不得使用同一模板。

脚本只能初始化骨架、校验 SHA/完整性，或把当前模型已经逐字段明确写出的数据确定性序列化到回执。禁止用循环从章节首尾自动抽两句，再批量生成 `status / comparison / manual_judgment / target_section_rationale` 等语义裁决。验证器输出 `passed` 仍不替代当前模型逐项判断。

正文全部写完后，只允许运行本合同的 `validate-draft`、字数统计和平台格式校验，然后立即执行初稿停靠。该窄门禁属于首写质量控制，不代表已进入 AI 深审、滑窗审计或正文回炉。

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
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" validate-prewrite \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt"
```

正文初稿落盘后，先绑定最终 SHA 并自动生成全部小节复核骨架：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" bind-draft \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --draft "{项目目录}/正文.md"
```

当前模型逐节回填后运行：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_prose_granularity_contract.py" validate-draft \
  --receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --draft "{项目目录}/正文.md"
```

任一命令未输出 `passed` 都必须回到当前步骤修正，不得运行 `--help` 探路，也不得降级成 warning。
