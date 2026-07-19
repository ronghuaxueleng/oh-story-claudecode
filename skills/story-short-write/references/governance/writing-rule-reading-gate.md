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
- 回执时间早于 `设定.md`、`小节大纲.md` 和 `正文.md`

## 标准命令

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" init \
  --project "{项目名}" \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json"

python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" validate \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"
```

只有输出 `writing_rule_gate: passed` 才能起盘、写大纲或写正文。正文回炉前必须再次读取并校验当前回执；规则文件变化时禁止沿用旧结论。
