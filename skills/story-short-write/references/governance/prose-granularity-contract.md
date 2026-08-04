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
