# 开头承重契约硬闸

普通“开头抓人”规则不能替代主体拆书资产给出的功能顺序。本闸门专门阻断：

- 先铺任务、职业流程或背景，再迟到地交代关系炸点
- 第一节最终有冲突，但前 `20 / 60 / 80 / 120` 字没有兑现题面
- 只证明“开头有事”，没有证明主体导语的功能顺序被保留
- 回炉时以“本轮不改开头”为由保护一个从未过闸的旧开头
- 只看导语拆解表或 profile，不读取选中拆文的真实原文开口
- 为了压缩开头，把正文改成一句一个动作、一句一个证据、一句一个反应的分镜清单
- 把开头写成“规则 A 已执行、证据 B 已展示、边界 C 已落地”的施工验收单

## 固定执行

主体来源必须使用其 `可直接仿写_导语拆解表.md`，并同步读取所有选中主体 / 辅助拆文的 `原文/` 开头样本。当前模型人工提取：

1. 至少三拍功能顺序
2. 禁止抢跑或禁止换序规则
3. 至少两条可迁移要求
4. 主体资产真实原句证据
5. 当前目标前 `20 / 60 / 80 / 120` 字逐项裁决
6. 原文真实开口样本、共性和目标开头应用方式
7. 开头叙述流复核：是否仍像分镜清单或规则施工单

不得硬编码主体书中的人物、职业、动作或物件，只继承功能顺序。

## 原文开口对照

凡正文首写或开头回炉，都必须填写 `original_opening_comparison`：

- `all_selected_sources_reviewed` 必须为 `true`
- `samples[]` 必须记录每个开口样本的 `path / sha256 / opening_quote / opening_pattern`
- `opening_quote` 必须来自对应原文前 `1000` 字
- `common_patterns` 至少两条，说明参考原文如何起手
- `target_opening_application` 至少两条，说明目标开头如何承接这些起手共性
- 正文开头回炉时，`exposition_removed_or_deferred` 必须记录被删掉或后移的说明、背景、流程内容

只写“已参考原文”“开头更快了”不算完成。

## 去分镜 / 去施工单

压缩开头后必须填写 `opening_flow_review`：

- `storyboard_or_construction_list` 必须为 `false`
- `symptoms_checked` 必须覆盖至少两类症状，包括 `一句一个动作 / 一句一个证据 / 一句一个反应 / 规则施工`
- `narrative_flow_evidence` 至少两条，证明人物动作、现场噪音、物件证据和关系反应已经揉进连续叙述气口
- 正文开头回炉时，`revision_method` 至少两条，说明如何把清单式分镜改成现场叙述

反例：

```text
我要求停演。
他恢复旧版本。
程雾叫他。
值守员看我。
我提交撤签。
```

这类写法虽然短，但像分镜条，不算合格开口。

合格方向：

```text
后台吵得像要炸开，宣传在耳机里催倒计时，程雾还吊在三米高的试位上。
我让值守员按停演预案，他的手刚挨到报警键，周既明就从我身后伸过来，把那只手按回了控制台。
```

动作、噪音、人物站位和权力争夺在同一口气里发生，才算叙述流。

## 两次过闸

写大纲后先对 `小节大纲.md` 过一次：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" init \
  --project "{项目名}" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/小节大纲.md" \
  --artifact-kind outline \
  --receipt "{项目目录}/写作资产/开头承重契约回执_大纲.json"
```

正文首写或开头回炉后，再对 `正文.md` 过一次：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_opening_contract.py" init \
  --project "{项目名}" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md" \
  --artifact-kind draft \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json"
```

当前模型回填后运行 `validate`。以下八项必须全部为 `true`：

- `relationship_anchor_in_first_20_60`
- `relationship_conflict_or_abnormal_position_in_first_60`
- `premise_paid_off_in_first_80_120`
- `reader_question_established`
- `task_exposition_does_not_precede_hook`
- `source_sequence_preserved_at_function_level`
- `original_opening_samples_compared_before_revision`
- `opening_not_storyboard_or_construction_list`

任一项失败都必须修改大纲或开头，不得降级为 warning，不得用“第一节后面会交代”放行。

主体导语资产 SHA 或目标文本 SHA 变化后，旧回执立即失效。局部回炉也必须先校验旧开头回执；未通过时不能声明“本轮只改中后段”。
