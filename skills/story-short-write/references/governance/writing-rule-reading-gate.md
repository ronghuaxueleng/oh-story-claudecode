# 写作规则强制读取闸门

这道闸门防止执行器只读主 `SKILL.md` 或下层工作流摘要，却漏掉正式写作前的必读规则。

## 必读文件

- `references/workflow/format-and-structure.md`
- `references/anti-ai-writing.md`
- `references/craft/narrator-voice.md`

三份文件一律读取当前工作区版本。文件内容或 SHA 变化后，旧回执立即失效，必须重新读取。

## 回执要求

每个文件必须填写：

- `status: read`
- 至少一个确实存在于当前规则文件的 `evidence_terms`
- 至少一条 `takeaways`
- 至少一个 `used_for`

回执还必须满足：

- `gate_status: passed`
- `confirmed_before_outline: true`
- `confirmed_before_draft: true`
- 回执时间早于当前即将生成的阶段目标：`setting -> 设定.md`、`outline -> 小节大纲.md`、`draft -> 正文.md`

规则更新后允许在后续阶段重新读取。比如设定和大纲已经验收、正文尚未生成时，新的读取回执可以晚于旧设定和旧大纲，但必须早于 `正文.md`。旧设定和旧大纲继续由各自阶段门禁、SHA 绑定与顺序契约负责，不能在正文阶段把它们再次作为 `--output` 传入。这样既不把合法重读误判为事后补票，也不允许正文生成后补回执。

## 标准命令

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" init \
  --project "{项目名}" \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" validate \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --stage draft \
  --output "{项目目录}/正文.md"
```

设定和大纲阶段把 `--stage` 及 `--output` 分别换成 `setting / 设定.md`、`outline / 小节大纲.md`。`--output` 只接收当前阶段目标；尚未生成也必须传预定路径。只有输出 `writing_rule_gate: passed` 才能起盘、写大纲或写正文。正文回炉前必须再次读取并校验当前回执；规则文件变化时禁止沿用旧结论。

## 官方批次中段

为了避免执行时用零散 `cat` 或临时文件直接读取规则正文，读取中段统一走 `batch_read_gates.py`。高层命令优先：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" prepare-batches \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --source-dir "拆文库/{主体书}" \
  --source-dir "拆文库/{辅助书}" \
  --output-dir "{项目目录}/写作资产/读取批次" \
  --batch-size 20
```

- 导出的 `batch-*.json` 会内嵌当前规则文件全文、源文件 SHA 和回执绑定关系，供当前模型逐批填写 `evidence_terms / takeaways / used_for`。
- 当前模型开始填写时把 `status` 改成 `in_progress` 并写入 `review_started_at`；全部人工字段完成后再改成 `status=reviewed`，补 `reviewed_at`，并把 `reviewed_by_current_model` 设为 `true`，同时保持 `semantic_fields_generated_by_script=false`。
- 脚本只负责切分正文、绑定 SHA 和确定性合并；不得自动把 `status` 标成 `read`，也不得自动生成任何语义判断。

需要先看哪些批次还没做完时，运行：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" status \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json"
```

输出会包含状态计数，以及按批次顺序排列的 `batch_id | status | entry_count | first_entry_id | last_entry_id` 简表。

填写完单个批次后执行：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" apply-batch \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --input "{项目目录}/写作资产/读取批次/batch-001.json" \
  --consume
```

`apply-batch` 会校验批次文件绑定的回执 SHA、源文件 SHA 和证据词真实存在，再把当前批次的人工字段合并回正式回执；`--consume` 成功后会把已应用的批次侧车压缩成消费回执。所有批次应用完后，再运行正式 `validate`。

若当前批次已全部填写完，推荐直接按清单顺序一次合并并校验：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" finalize-batches \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json" \
  --consume \
  --stage outline \
  --stage-output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"
```

它会先检查 `manifest.json` 下是否仍有未完成批次；只要任一批次还没切到 `status=reviewed`，或缺少 `reviewed_by_current_model=true` / `reviewed_at`，就直接阻断，不允许先合并前半段。全部完成后，它才按 `manifest.json` 中的批次顺序逐个执行 `apply-batch`、逐个压缩批次侧车，并在末尾接上正式 `validate`。底层 `export-batches / apply-batch / apply-manifest` 仍保留给单批排障或中途续跑。
