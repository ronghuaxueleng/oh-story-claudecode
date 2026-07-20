# 写后人工语义复核硬闸

自动脚本只能做可计算的预扫，不能代替对正文语义、人物知识范围和叙述站位的人工判断。

进入本硬闸前，`规则执行台账.json` 必须已经绑定最终设定、大纲和正文，并通过 `rule_execution_gate`。本回执负责全文语义复扫，不代替前一阶段对 skill 规则和拆书规则的逐项执行证明。

## 分工边界

| 自动脚本适合检查 | 必须人工判断 |
|---|---|
| 文件 SHA、格式、段长、重复频率、固定词句、显式模式、审计分数 | 作者是否替人物归纳动机 |
| 引号、章节数、禁用词、规则包命中、改写行清单 | 评价句是现场态度还是作者总结 |
| 回执字段、证据原句是否存在、正文修改后回执是否过期 | 是否重复解释读者已经看懂的信息 |
| 可量化的句长、对白比例、热点和风险块 | 动作是否已经足够，新增判断是否卸力 |
| 任务单和审计产物是否生成 | 对白是否太会推进、配角是否只服务主线 |

自动报告中的“零命中”只能表示脚本没有抓到显式模式，不得写成“人工语义检查已通过”。

## 强制人工检查项

正文写完或回炉后，必须逐项人工复核：

1. `author_motive_substitution`：是否替人物总结动机、胜负或认知。
2. `narrator_voice_boundary`：第一人称评价是现场态度，还是作者借人物点题。
3. `narrator_voice_distribution`：叙述者气口是否只集中在少数短段，长区间仍然匀速。
4. `redundant_explanation`：动作、物件或对话已经表达清楚后，是否又补解释。
5. `observable_scene_basis`：判断是否有当前场景中可观察的依据。
6. `dialogue_efficiency`：局部对白是否句句正答、过度服务推进。
7. `long_window_dialogue_efficiency`：按长窗看，对话是否连续高效推进，缺打断、错位和生活闲枝。
8. `cross_block_rhythm_contrast`：各长窗的句长、情绪密度和用力程度是否过于一致。
9. `full_text_legacy_rescan`：不能只审本轮 diff，必须复扫母稿遗留问题。

每项必须引用当前正文原句，填写语义判断和 `keep / revise / delete` 动作。

其中后三项宏观检查必须结合 `run_full_ai_audit.py` 的
`rhythm_distribution_audit` 查看全文长窗，不得只凭新增句清单放行。

## 局部与专项回炉

局部回炉、叙述者声音专项、去 AI 定点修改必须传入母稿：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_post_write_human_review_gate.py" init \
  --project "{项目名}" \
  --text "{项目目录}/正文.md" \
  --base-text "{母稿目录}/正文.md" \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json"
```

脚本会按句子语义切分，忽略标题、空行和纯断行变化，列出母稿与当前正文之间所有新增、改写句。每一句都必须人工填写：

- `scene_observable_basis`
- `narrator_or_author`
- `redundant_explanation`
- `substitutes_character_motive`
- `decision`
- `reason`

如果判断为 `revise` 或 `delete`，先改正文，再重新生成回执；当前正文里仍存在待修改句时不得放行。

## 全新正文

全新正文没有母稿时，不传 `--base-text`，但九项全文人工检查仍必须完成。不得用抽样审查代替全文复扫。

## 最终校验

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_post_write_human_review_gate.py" validate \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json" \
  --text "{项目目录}/正文.md" \
  --sequence-receipt "{项目目录}/写作资产/顺序契约回执.json"
```

只有在人工语义回执和完整顺序契约都通过，并输出 `post_write_human_review_gate: passed` 后，才能结束当前写作或回炉任务。

正文 SHA、母稿 SHA 或改写行发生变化后，旧回执立即失效。脚本只校验人工回执是否完整、证据是否真实、是否对应最终正文，不替人工填写语义结论。
