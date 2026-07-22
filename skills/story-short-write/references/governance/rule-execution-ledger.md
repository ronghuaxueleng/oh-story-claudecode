# 规则执行台账硬闸

读取回执只证明文件被读过，不能证明规则已经用于设定、大纲、正文和写后复核。本硬闸负责建立：

`来源文件 -> 规则族 -> 族内变体 -> 模型语义分类 -> 适用性 -> 执行证据 -> 结果`

## 规则族，不是行级膨胀

- Markdown 按真实小节形成规则卡；同类小节合并后只保留一条 `canonical_rule_text`，清单、表格行和例子保存在 `cases`。
- `audit-rulebook.json` 按 section 形成规则族。
- 每个拆书承重资产文件形成一个规则族；四本拆书中的同名资产族自动合并来源。
- 普通拆书文件按相对路径形成文件资产族；四本书的同名细节库或报告只做一次用途判断，但保留四份来源。
- 导航、说明、例子和 profile 数据不能各自膨胀成一条强制执行规则。
- 合并后仍必须阅读全部 `cases`，不能因为数量下降而漏掉案例差异。

## 关键来源契约不能被合并降级

以下资产含“必须保留、顺序不能乱、换序即失效、判假、禁写、事实边界”等阻断信息：

- `book.profile.json`
- `事实与推断台账.md`
- `写作资产/样本分级与可学层.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/桥段施工卡.md`
- `写作资产/高敏桥段识别.md`
- `写作资产/同桥段过检规则.md`
- `写作资产/仿写约束_禁写清单.md`
- `写作资产/公开场_关键硬牌_后果.md`
- `可直接仿写_顺序事件表.md`
- `可直接仿写_后果链表.md`
- `可直接仿写_外部秩序表.md`

这些资产可以合并进 canonical，但不能只留一条宽泛结论。canonical 必须在 `source_contract_reviews` 中逐个覆盖其 `source_refs`：

```json
{
  "source_path": "/absolute/path/to/asset.md",
  "source_sha256": "...",
  "disposition": "applied",
  "source_quote": "为什么这个顺序不能乱：……",
  "judgment": "本稿采用哪一层、禁止哪一层。",
  "target_evidence": [
    {
      "artifact": "大纲",
      "quote": "当前大纲原句",
      "judgment": "该句如何兑现来源契约。"
    }
  ],
  "scope_reviews": [],
  "non_dependency_reason": ""
}
```

- `applied`：必须提供当前设定/大纲/正文原句证据。
- `prohibition_checked`：必须提供全文范围复核。
- `not_selected`：必须解释当前结构为何不依赖该契约，不能只写“本轮未调用、保留原稿”。
- 主体的 profile、事实边界、样本分级、作者 DNA、桥段施工、高敏识别、同桥过检、禁写清单、平台提醒、顺序事件、后果链、外部秩序和公开场后果不得标 `not_selected`。
- 文件级关键资产也执行同一套 `source_contract_reviews`，不能因为没有展开子规则而绕过契约复核。
- 规则级资产父节点由子规则自动派生。`refresh-summary / apply-plan / apply-model-groups` 会同步 `applicability / status / outcome / result`；手填结果与子规则不一致时直接阻断。

## 最终产物变更后必须递归重绑证据

设定、大纲或正文任一文件重新绑定后，旧台账不能只改 `artifacts.sha256`，也不能只改一条代表规则。必须递归检查并重绑：

- `skill_rules / source_assets / asset_rules` 里的所有规则卡。
- canonical 规则和所有由 canonical 合并出来的成员来源。
- `text_evidence / structural_claim_reviews / source_contract_reviews.target_evidence / scope_reviews` 中的每一条目标产物证据。
- 每条带关键来源 `source_refs` 的规则都必须按当前实际 `source_refs` 重建 `source_contract_reviews`。

硬失败口径：

- `quote` 不存在于当前设定、大纲或正文。
- `target_evidence` 还引用旧正文句子、旧大纲句子或旧设定句子。
- `source_contract_reviews` 缺少当前 `source_refs` 中的关键来源。
- `source_contract_reviews` 残留上一轮无关来源。
- 用一条公共 target evidence 代替逐来源契约判断。
- 把源文件证据写进 `target_evidence`，或把目标产物证据写进 `source_quote`。
- 台账 `validate` 未 passed 时，用“人工已看过”“整体已执行”口头替代。

正确顺序：

1. 运行 `bind-artifacts` 绑定最终设定、大纲、正文。
2. 递归重建全部目标产物证据和 `source_contract_reviews`。
3. 运行 `refresh-summary`，再人工确认汇总。
4. 运行 `validate`。
5. 只有输出 `rule_execution_gate: passed` 才能进入写后人工语义复核或宣称流程闭环。

## 结构结论必须逐目标举证

`setting_constraint / outline_constraint` 的 `target_scene` 如果写了多个目标，例如：

`开头、反转揭示、正式后果及追妻后效应`

则 `structural_claim_reviews` 必须分别覆盖 `开头 / 反转揭示 / 正式后果 / 追妻后效应`，每项都引用当前设定或大纲原句。只证明其中两项却把整张 canonical 判为 passed，直接阻断。

## 先分类，再执行

台账中的规则不等于正文修改项。每条规则必须先确认 `rule_role`：

| 规则角色 | 作用 | 失败时修复目标 |
|---|---|---|
| `workflow_gate` | 读取、回执、顺序、SHA、运行门禁 | `workflow`，不改正文 |
| `format_check` | 格式、标点、字数、固定排版 | `audit` 或 `draft` |
| `setting_constraint` | 人设、关系、事实边界 | `setting` |
| `outline_constraint` | 桥段链、场序、信息释放 | `outline` |
| `draft_constraint` | 叙述、对白、节奏、现场表达 | `draft` |
| `audit_check` | 检测、定位、复核方法 | `audit`，本身不直接改正文 |
| `source_candidate` | 拆书里的可选人物偏手、桥段、句式和生活细节 | 选中后落到 `setting / outline / draft`；未选中标 `not_applicable` |
| `source_prohibition` | 禁写、禁搬、污染和相似风险 | `audit`；命中后再定位修复 |

只有同时满足以下四项的规则，才能进入正文修改单：

`rule_role=draft_constraint + applicability=applicable + outcome=failed + requires_text_change=true`

流程、设定、大纲和审计问题必须修到各自目标，不得借“执行全部规则”之名全部塞进正文。拆书候选不是每项都要写进正文；禁用规则未命中时只需全文范围复核，不得反向新增内容。

## 规则合并

初始化会自动合并完全相同的规则族标签，并把全部来源保存在 canonical 规则的 `source_refs`、把全部具体条目保存在 `cases`。模型继续归纳统一的 `canonical_rule_text`。重复项标记为：

`applicability=merged + outcome=not_applicable + merged_into={canonical_rule_id}`

语义近似但标签不同的规则由当前写作模型通过 `apply-plan` 指定 `merged_into`。canonical 必须存在、不能再指向其他规则、必须完成并通过；合并环直接阻断。合并只减少重复执行，不删除来源追踪。

## 两层清点

1. 每个 skill 核心规则和每个主体/辅助拆书文件都必须进入台账。
2. 16 张 `可直接仿写_*.md`、作者 DNA、禁写清单、同桥规则、桥段施工卡、高敏桥段、动态字典和 profile 必须形成规则族，并保留全部族内变体。
3. 其他报告和细节库至少逐文件判断 `applicable / rejected / not_applicable`；实际用于当前稿时必须提供写作产物证据。
4. 额外挂载的题材或专项规则文件必须通过 `--skill-rule-file` 加入台账，不能只在聊天里声称使用。

## 脚本与人工分工

| 执行方式 | 适用内容 | 通过条件 |
|---|---|---|
| `script` | SHA、格式、字数、频率、禁词、固定模式、字段和文件完整性 | 存在真实脚本产物、产物 SHA 和结果摘要 |
| `human` | 人物偏手、失控说话、注意力漂移、认知局限、作者代判、对白生活性 | 有人工判断，并引用设定/大纲/正文原句 |
| `hybrid` | 长窗节奏、对白效率、桥段相似度、profile 覆盖 | 脚本定位和人工裁决两侧证据都齐全 |

初始化给出的角色和 `execution_mode` 都只是脚本建议。最终分类必须写入：

`classification_confirmed=true + classification_method=model_semantic_review + classification_notes`

自动完全重复项允许使用 `classification_method=exact_duplicate`。其他条目仍是 `script_suggestion` 时，最终校验必须阻断。

## 初始化

必须先通过 `writing_rule_gate` 和 `source_read_gate`：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" init \
  --project "{项目名}" \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --ledger "{项目目录}/写作资产/规则执行台账.json"
```

如本次加载了额外题材规则或专项规则，逐个追加：

```bash
--skill-rule-file "/absolute/path/to/extra-rule.md"
```

初始化完成后，先逐项确认规则角色、修复目标、适用性、执行方式、目标阶段和目标场景，再写设定、大纲或正文。可合并项先归一，避免同义规则重复执行；不得写完后统一伪造执行记录。

先导出模型复核批次：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" export-model-review \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --output "{项目目录}/写作资产/规则模型分类批次.json" \
  --batch-size 30
```

当前写作模型必须逐批阅读 `cases`，把同一规则的多个案例压成一张规则卡，并生成可审计 `apply-plan`。不得写脚本把建议分类批量改成 `model_semantic_review`。

模型归并计划使用：

```json
{
  "groups": [
    {
      "canonical_id": "SKILL-...",
      "canonical_rule_text": "统一后的可执行规则",
      "member_ids": ["SKILL-...", "SKILL-..."],
      "rule_role": "draft_constraint",
      "remediation_target": "draft",
      "execution_mode": "human",
      "classification_notes": "这些条目执行动作相同，只是案例和来源不同。",
      "applicability": "applicable",
      "status": "completed",
      "outcome": "passed",
      "decision_reason": "本规则适用于当前正文，已由当前模型人工核对并完成。",
      "target_stage": "draft",
      "result": "正文已满足该规则。",
      "human_judgment": "人工判断正文已落实该规则，未发现待改项。",
      "text_evidence": [
        {
          "artifact": "正文",
          "quote": "必须引用当前最终正文中真实存在的原句",
          "judgment": "说明这句如何证明规则已执行"
        }
      ]
    }
  ]
}
```

应用后，canonical 规则卡保留全部 `cases/source_refs`，其他成员自动标记 `merged`：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" apply-model-groups \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --plan "{项目目录}/写作资产/规则模型归并计划.json"
```

`apply-model-groups` 不只是归并工具，也是 canonical 规则裁决入口。每个 group 必须同时完成：

- `applicability`：只能是 `applicable / rejected / not_applicable`，不得留空或写 `merged`。
- `status`：必须是 `completed`，归并计划不得留下 `pending`。
- `outcome`：适用规则必须是 `passed / failed`；跳过规则必须是 `not_applicable`。
- `decision_reason`：必须写具体裁决原因。
- 适用规则必须补 `target_stage`、`result`，并按 `execution_mode` 补 `script_artifacts`、`text_evidence` 或 `human_scope_reviews`。
- 带关键 `source_refs` 的 canonical 必须补 `source_contract_reviews`；不能只靠成员被合并来绕过来源契约。

## 执行与标记

- `applicable`：必须真正执行并标记 `status: completed`。
- `rejected / not_applicable`：必须写具体 `decision_reason`，不能用“本次不需要”敷衍。
- 关键来源契约还要逐来源填写 `source_contract_reviews`，不能用 canonical 的一条公共证据替代。
- `merged`：只由 canonical 规则统一执行，重复项不得再生成一份正文修改任务。
- `script`：填写 `script_artifacts` 的路径、SHA 和结果摘要。
- `human`：填写 `human_judgment`，并在 `text_evidence` 中引用当前写作产物原句及逐项判断。
- `hybrid`：同时满足脚本和人工要求。
- 承重资产的文件级状态和其中每条展开规则都必须完成。

正文或大纲发生变化后，重新绑定最终产物；原句证据消失时台账会阻断。阻断后不能机械把所有旧证据替换成同一句正文开头，必须按规则实际目标重绑到设定、大纲、正文或人工复核证据；否则虽然可能消除“原句不存在”，但仍属于伪执行。

逐项状态更新后刷新汇总：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" refresh-summary \
  --ledger "{项目目录}/写作资产/规则执行台账.json"
```

刷新会把 `gate_status` 重置为 `pending`。人工核对汇总无误后再改为 `passed`，不能手填与逐项状态不一致的数量。

## 绑定最终产物

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" bind-artifacts \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --artifact "设定={项目目录}/设定.md" \
  --artifact "大纲={项目目录}/小节大纲.md" \
  --artifact "正文={项目目录}/正文.md"
```

## 最终校验

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/validate_rule_execution_ledger.py" validate \
  --ledger "{项目目录}/写作资产/规则执行台账.json"
```

只有输出 `rule_execution_gate: passed` 才能进入最终人工语义复核。缺台账、缺规则、缺拆书文件、源文件 SHA 变化、正文证据消失、分类未确认、修复目标错位、canonical 无效或执行类型证据不完整，全部直接阻断，不做兼容回退。
