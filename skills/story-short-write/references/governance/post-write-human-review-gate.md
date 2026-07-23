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
| 分段、短句和显式清单模式 | 是否把全文写成分镜清单或规则施工稿 |

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
9. `full_text_storyboard_construction_list_review`：全文是否存在“一句一个动作 / 一句一个证据 / 一句一个反应”的分镜清单，或“规则 A 执行、证据 B 展示、边界 C 落地”的施工稿。
10. `source_granularity_preservation`：正文是否保持选中原文或拆书情节的场面颗粒度，不能把公开清算、复核、直播、会议、签字、调查等高价值场写成结果播报链。
11. `section_four_axis_review`：逐小节同时复查原文颗粒度、强情绪追妻承诺、流程/证据顺滑度、人物交流与冲突载体，不允许只用“开头成品感”“尾部说明句”等单一标签代替。
12. `full_text_legacy_rescan`：不能只审本轮 diff，必须复扫母稿遗留问题。

每项必须引用当前正文原句，填写语义判断和 `keep / revise / delete` 动作。

其中 `full_text_storyboard_construction_list_review` 必须额外填写：

- `scan_scope`：必须为 `full_text`
- `remaining_storyboard_or_construction_list`：必须为 `false`
- `symptoms_checked`：至少覆盖三类症状，包括 `一句一个动作 / 一句一个证据 / 一句一个反应 / 规则施工`
- `allowed_in_story_artifacts`：只记录情节内真实出现的清单、报告、日志、合同、群公告、流程单等文本；每条必须引用正文原句并说明情节功能

如果这类清单感出现在叙述正文、关系场、冲突场、追妻低位、揭示或结尾里，不能标例外，必须先回修为连续现场叙述。

其中 `source_granularity_preservation` 必须额外填写：

- `scan_scope`：必须为 `full_text`
- `remaining_result_broadcast_chain`：必须为 `false`
- `remaining_granularity_shrinkage`：必须为 `false`
- `source_scenes_checked`：逐场列出所有承重场，尤其是公开清算、复核、直播、会议、签字、声明、调查、追妻低位和尾声入口

`source_scenes_checked` 每项必须填写：

- `target_scene`：目标正文场景名
- `target_quote`：当前正文原句
- `source_granularity`：选中原文或拆书情节自己的颗粒度，不得只写“同级”
- `target_granularity`：目标正文实际颗粒度
- `scene_resistance`：现场阻力，例如抢话、卡顿、手续被拦、物件不顺、人物错答
- `control_right_change`：动作、物件、空间、身份或外部秩序如何换主
- `information_delay`：信息如何分次漏出，不能一口气把证据、责任和结论全报完
- `external_order_or_bystander_pressure`：旁观者、制度、平台、复核人、主持人、门口、话筒、证物袋等如何改变现场
- `result_broadcast_chain_judgment`：明确反证没有写成 `证据出现 -> 众人发问 -> 责任人承认 -> 主角总结/离场`
- `decision`：只能是 `keep` 才能放行；若为 `revise/delete`，先改正文再重建回执

如果某场只能概括为“真相公开了、现场混乱了、责任人承认了、主角不需要他发声了”，说明该场没有通过原文颗粒度保持检查。

其中 `section_four_axis_review` 必须额外填写：

- `scan_scope`：必须为 `all_sections`
- `all_sections_reviewed`：必须为 `true`
- `section_reviews`：每个正文小节必须有一条记录，正文有 10 节就必须有 10 条

`section_reviews` 每项必须填写：

- `section_id`：正文小节编号
- `section_role`：本节功能，例如 `opening / midpoint / public_reckoning / aftermath / ending`
- `representative_quote`：当前正文原句
- `source_granularity_preservation`：原文/拆书颗粒度是否缩水，必须给判断和证据
- `genre_promise_alignment`：追妻、婚恋清算、强情绪关系文的题材承诺是否仍成立
- `process_evidence_smoothness`：流程、证据、权限、复核、签字、声明是否太顺太像案卷
- `interaction_exchange_and_conflict_carrier`：人物是否真实接招，现场争夺的权力/物件/空间/身份是否发生变化
- `revision_scope_decision`：`keep / sentence_hotspot / paragraph_cluster / full_scene / coarse_block / global_structure`
- `decision`：只能是 `keep` 才能通过；若为 `revise`，必须先改正文再重建回执

开头节必须额外在判断中覆盖：承重顺序、关系锚、起事速度、物件是否全服务主线、对白是否太快对题、作者是否提前盖章。

尾声节必须额外在判断中覆盖：追妻低位是否持续、女主边界是否行动化、结尾是否落在完成动作上、是否误开复合入口、男主是否只剩功能性补偿。

其中宏观检查必须结合 `run_full_ai_audit.py` 的
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

全新正文没有母稿时，不传 `--base-text`，但全部全文人工检查仍必须完成。不得用抽样审查代替全文复扫。

## 最终校验

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_post_write_human_review_gate.py" validate \
  --receipt "{项目目录}/写作资产/写后人工语义复核回执.json" \
  --text "{项目目录}/正文.md" \
  --sequence-receipt "{项目目录}/写作资产/顺序契约回执.json"
```

只有在人工语义回执和完整顺序契约都通过，并输出 `post_write_human_review_gate: passed` 后，才能结束当前写作或回炉任务。

正文 SHA、母稿 SHA 或改写行发生变化后，旧回执立即失效。脚本只校验人工回执是否完整、证据是否真实、是否对应最终正文，不替人工填写语义结论。
