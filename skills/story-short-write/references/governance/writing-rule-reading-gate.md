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

## 标准流程

正常写作固定使用统一工具箱，不直接编辑正式回执：

```bash
SKILL_ROOT="{系统注入的 story-short-write SKILL.md 所在目录}"
TOOLBOX="$SKILL_ROOT/scripts/story_short_write_project_toolbox.py"

python3 "$TOOLBOX" --project "{项目目录}" export-rule-review
```

命令只输出任务文件路径和 SHA，不把完整规则再次打印进模型上下文。禁止直接打开总文件 `写作资产/规则语义输入.json`。改为循环执行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" rule-review-next
```

`rule-review-next` 每次只打印一个完整规则文件包。当前模型完整读取该唯一规则文件，按包内 `result_template` 填写 `写作资产/当前规则语义回执.json`，再执行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" apply-rule-review-item \
  --packet-sha "{当前包 packet_sha256}"
```

重复到 `rule-review-next` 显示清单归零后，必须立刻连续执行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" apply-rule-review
python3 "$TOOLBOX" --project "{项目目录}" validate-prewrite-reads
```

`apply-rule-review-item` 校验当前必须处理的规则文件、包 SHA、任务 SHA、正式回执 SHA、证据词和非空结论；通过后才原子追加到 `规则语义进度.json`。重复到 `rule-review-next` 显示清单归零，再运行 `apply-rule-review`。`apply-rule-review` 会把累计进度汇总成正式 `规则语义输出.json`，并再次校验输入任务 SHA、正式回执 SHA、三份必读规则的文件集合、当前文件 SHA、精确证据词和非空结论；全部通过后才原子替换正式回执。证据词拼写错误、规则文件变化、缺项、跳项或总进度未完成时，正式回执保持不变。`apply-rule-review` 不是自然停点；规则总验收一旦通过，当前链路必须继续推进到 `validate-prewrite-reads`，不得停在“规则回执已通过”的成功提示上。

禁止搜索其他项目的 `规则语义输出.json`、`规则语义进度.json` 或 `写作规则读取回执.json` 猜字段；唯一字段模板已经包含在当前 `rule-review-next` 输出的 `result_template`。

下面的单脚本命令只用于开发诊断：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_writing_rule_gate.py" validate \
  --receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --output "{项目目录}/设定.md" \
  --output "{项目目录}/小节大纲.md" \
  --output "{项目目录}/正文.md"
```

只有输出 `writing_rule_gate: passed` 才能起盘、写大纲或写正文。正文回炉前必须再次读取并校验当前回执；规则文件变化时禁止沿用旧结论。
