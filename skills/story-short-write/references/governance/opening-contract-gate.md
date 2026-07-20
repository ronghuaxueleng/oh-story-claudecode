# 开头承重契约硬闸

普通“开头抓人”规则不能替代主体拆书资产给出的功能顺序。本闸门专门阻断：

- 先铺任务、职业流程或背景，再迟到地交代关系炸点
- 第一节最终有冲突，但前 `20 / 60 / 80 / 120` 字没有兑现题面
- 只证明“开头有事”，没有证明主体导语的功能顺序被保留
- 回炉时以“本轮不改开头”为由保护一个从未过闸的旧开头

## 固定执行

主体来源必须使用其 `可直接仿写_导语拆解表.md`。当前模型人工提取：

1. 至少三拍功能顺序
2. 禁止抢跑或禁止换序规则
3. 至少两条可迁移要求
4. 主体资产真实原句证据
5. 当前目标前 `20 / 60 / 80 / 120` 字逐项裁决

不得硬编码主体书中的人物、职业、动作或物件，只继承功能顺序。

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

当前模型回填后运行 `validate`。以下六项必须全部为 `true`：

- `relationship_anchor_in_first_20_60`
- `relationship_conflict_or_abnormal_position_in_first_60`
- `premise_paid_off_in_first_80_120`
- `reader_question_established`
- `task_exposition_does_not_precede_hook`
- `source_sequence_preserved_at_function_level`

任一项失败都必须修改大纲或开头，不得降级为 warning，不得用“第一节后面会交代”放行。

主体导语资产 SHA 或目标文本 SHA 变化后，旧回执立即失效。局部回炉也必须先校验旧开头回执；未通过时不能声明“本轮只改中后段”。
