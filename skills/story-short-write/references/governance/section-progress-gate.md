# 逐节正文进度硬闸

本闸把“逐节写、逐节确定性提交、全文统一人工终审”落实成状态机。正文放行后必须先初始化本闸；没有 `逐节正文进度.json`，禁止创建 `正文.md`。

## 状态机

固定顺序：

`先写场面计划 -> start-section N（同步生成紧凑写作包） -> 当前模型在独立暂存稿中一次写完并完整通读第 N 节 -> init review（默认生成确定性延后回执） -> preflight-section-review -> commit-section N -> 原子写入正文 -> start-section N+1`

`正文.md` 只是已通过小节的成稿，不是试写区。当前节在 `写作资产/当前节暂存/第N节.md` 一次成形；只有 `commit-section` 可以把它追加到正文。

硬限制：

- `start-section N` 前，正文只能存在已经通过的 `1..N-1` 节。
- `start-section N` 必须传入本节场面计划。计划必须把全部 E/P 拍同序聚合到 `1-3` 个完整场面，并为每场分配字数、进场压力、三步交流链、转折动作、可见后果和余波。
- 场面计划必须来自已通过的 `细纲表演验收回执.json` 的同节 `scene_units`，但默认只保存 `scene_unit_refs` 和该回执 SHA；正文阶段由官方入口回解完整场面。正文阶段只能领取上游已决定的场面容量，不得临时把事件压缩成概括或在计划中复制一份可变场面。
- 场面计划的字数之和必须在本节预算内，且不得将承重场面分配为少于 `240` 字的梗概槽。装不下时必须先拆节或回写细纲，不得进入正文。
- 写第 N 节时禁止出现 `N+1.` 或任何未来小节标题。
- 暂存稿必须先完成全节字数和写前合同一致性检查，再原子写入正文。当前模型通读时发现语义偏差必须先重写；禁止先把短稿写进正文，再追加对白、背景、动作或情绪凑字数。
- 第 N 节验收时，已通过的旧节文本 SHA 必须保持不变。
- 第 N 节必须满足预先分配的字数区间、写前正向首写约束、完整场面表演和完整 E/P 拍领取。“ID 出现 / 事件被提到 / 有一句引句”均不等于事件成立；当前模型发现正文只点到 ID 而未形成现场时必须先重写，不得借确定性提交放行。
- 初始化前，主体全部 `SF-*` 必须以非模板化人工理由分配到一个或多个目标数字小节；不得留空，也不得按编号平均轮转。
- 写前包必须完整覆盖连续原文链、正反例、对白包、句间关系、逐句特征、活性、人物、全部直接对白和分配到本节的全部 SF 六维。逐节提交不再重复抄写这些人工字段；全部小节通过后，最终文字合同必须基于完整正文一次性逐节复核并通过 `validate-draft`。
- `full_bridge` 还必须在初始化前把主体八类细节卡逐卡分配到目标小节；未分配或写前合同仍为 `pending` 时不得开写。正文证据统一在最终文字合同逐卡绑定，一个相似动作或一条总括引句不能覆盖多步完整链。
- 回执中的 `current_model_manual` 和 `automation_used=false` 只是声明，不是机器可证明的事实。发现项目脚本、循环字典或模板批量生成语义字段时，必须判整节合同无效；禁止以验证器只检查非空为由继续使用。
- `start-section --context-output` 同步生成紧凑写作包。紧凑只删除全文合同中已存在的目标空壳、状态字段和重复静态副本；完整 E/P 拍、SF 六维全部来源证据、required_sequence 和主体细节卡原文仍保留在真源合同，并通过 ID、路径与 SHA 绑定进入本节。
- `逐节正文进度.json` 只保存每节 E/P ID、SF/细节卡 ID、预算和状态；完整 E/P 合同由 `commit-section` 按绑定的全文情绪合同回解。旧状态文件仍可读取其中的完整合同，但新初始化不得再写入重复合同正文。
- `init_section_review.py` 默认生成 `deferred_full_contract_review`：只绑定状态、暂存稿、两份写前合同、场面与 E/P 领取，不创建人工侧车。`preflight-section-review` 只读校验这些 SHA/ID，`commit-section` 不传 `--sidecar`。
- 逐节延后模式减少的是重复落盘，不减少最终人工终审。全部小节通过后，文字与情绪两份全文合同仍须逐节覆盖全部来源证据、细节卡、直接对白、人物不可互换性、E/P/SF 等价判断和 `keep-revise`，任一缺失都必须被最终 `validate-draft` 阻断。
- 当前模型通读发现任一 E/P/SF/细节卡未兑现、对白错脸、场景摘要化或偏离写前包时，禁止使用默认延后回执直接提交。先重写正文；确需记录偏差时，显式使用 `--sidecar-output` 导出 `delta_manual_review` 或旧全量侧车，并在提交时传 `--sidecar`。
- 禁止使用 `jq`、临时 Python、here-doc 或项目专属脚本拼装正式逐节回执或最终全文人工合同。默认回执、偏差侧车和最终合同统一走官方入口；正文或绑定变化后旧回执立即失效。
- `status`、`start-section`、`commit-section`、`sync-pending-contracts` 和 `finalize` 均不得信任旧状态名，必须先核对当前正文逐节 SHA；`final_ready` 额外核对全文 SHA。正文被状态机外修改后直接阻断。
- E/P 最终终审不只核对 ID：E 拍必须核对来源 `role / intensity` 和目标 `trigger / relationship_position_change / reader_effect`；P 拍必须核对动作等价、外部变化和关系后果。
- 回执有待改项时不能写 `passed`；先只修当前节，再重新验收。
- `commit-section N` 未输出 `section_passed`，禁止将当前节写入正文或开始下一节。
- `section_passed` 输出后必须立即运行一次 `status`。当前节必须显示 `passed (实际字数 chars)`，且 `current_section` 必须进入下一节；只更新正文或顶层游标、节条目仍为 `writing` 的情况属于半提交，禁止继续。
- 半提交只允许通过 `recover-half-commit` 恢复。该入口要求正文当前节与暂存稿逐字一致、正式回执绑定完整、旧节 SHA 未变化；人工侧车模式还须检查侧车 SHA 与机械归一化记录。任一条件不符就阻断。
- 最后一个已通过小节若发现合同不完整，且后续小节全部仍为 `pending`，运行 `reopen-section N` 废除旧正文 SHA 与旧回执后重写；其他历史小节禁止回开。
- 尚未落字的小节若因全量拍义复核需要调整 E/P/SF 分配，运行 `sync-pending-contracts`；命令必须证明所有已通过小节的 E/P/SF 与正文 SHA 完全不变，并拒绝同步任何已经落字的当前节。
- 旧流程已误将当前节写入正文时，只能运行 `discard-writing-section`。它必须将错误节完整归档、从正文移除并回到 `pending`；禁止直接截断、继续补写或伪装为已通过。
- 全部小节通过后必须运行 `finalize`；未输出 `final_ready`，禁止执行两份全文 `bind-draft`。

## 字数预算

正文前创建 `写作资产/逐节字数预算.json`：

```json
{
  "total_min_chars": 10000,
  "total_max_chars": 13000,
  "sections": [
    {"section_id": "1", "min_chars": 850, "max_chars": 1100},
    {"section_id": "2", "min_chars": 850, "max_chars": 1100}
  ]
}
```

必须覆盖全部连续数字小节。各节最小值之和不得低于全文最小值，各节最大值之和不得高于全文最大值。尾声可短，但必须在写前就由其他承重节分配足预算，不能全文写完后再发现总量不足并分散扩写。字数是场面容量的结果，不是写后添充目标。

写前 `target_chars` 和各场 `allocated_chars` 仍必须落在原始预算内。逐节实际成稿与 `finalize` 全文验收统一允许原始预算上下浮动 `20%`，并对低于有效下限不超过 `100` 字的自然短差免补：实际下限为 `max(0, ceil(min_chars * 0.80) - 100)`，实际上限为 `floor(max_chars * 1.20)`，边界值计为通过。例如原预算 `2650-2900`，实际允许 `2020-3480`。该宽限只处理自然场面容量短差，不授权先写短稿再补说明、对白、背景或情绪凑字数；若场面完整性失败，仍须重组细纲或整场重写。上限不享受额外宽限。

## 写前场面计划

`start-section` 使用的计划至少包含：

```json
{
  "section_id": "4",
  "mode": "single_pass_scene_realization",
  "target_chars": 1000,
  "outline_performance_receipt_sha256": "细纲表演验收回执的当前 SHA",
  "append_or_expand_after_target_write_forbidden": true,
  "scene_units": [
    {
      "scene_id": "S4-01",
      "emotion_beat_ids": ["E-019", "E-020"],
      "plot_beat_ids": ["P-023", "P-024"],
      "allocated_chars": 1000,
      "full_scene_required": true,
      "summary_only": false,
      "entry_pressure": "女主第三次输入旧爱生日后暗房门打开",
      "interaction_chain": ["女主追问翻找对象", "旧爱拿男主许可挡回", "女主伸手抢回相册"],
      "turning_action": "遮光袋被扯断并见白光",
      "visible_consequence": "未冲洗底片曝光失效",
      "aftershock": "男主先检查旧爱的手",
      "reader_emotion_path": "入侵不安经抢回希望翻成无法恢复的愤怒"
    }
  ]
}
```

这不是把正文拆成验收清单，而是在落笔前确认“这一节容不容得下一场完整戏”。计划不合格时改细纲或字数分配，不得靠正文压缩事件。

## 逐节回执

每节写入独立文件 `写作资产/逐节验收/第N节.json`。最低骨架：

默认用 `init_section_review.py` 从当前进度、暂存稿和两份写前合同生成 `deferred_full_contract_review` 回执。当前模型完整通读本节；无偏差时不填写人工侧车，直接预检并提交。逐节回执只承担确定性绑定，不声称语义已经终审通过；语义终审统一延后到最终两份全文合同。

```json
{
  "section_id": "1",
  "first_draft_mode": "single_pass_scene_realization",
  "complete_before_target_write": true,
  "substantive_append_or_expansion_after_target_write": false,
  "review_scaffold": {
    "review_mode": "deferred_full_contract_review",
    "staged_sha256": "当前暂存稿 SHA",
    "deferred_semantic_review": {
      "prewrite_contracts_remain_source_of_truth": true,
      "per_section_manual_sidecar_required": false,
      "fallback_on_detected_deviation": "delta_or_full_manual_sidecar"
    }
  },
  "emotion_review": {
    "status": "pending",
    "emotion_beat_ids": ["E-001"],
    "plot_beat_ids": ["P-001"],
    "emotion_beat_reviews": [],
    "plot_beat_reviews": []
  },
  "scene_realization_reviews": [
    {
      "scene_id": "S1-01",
      "emotion_beat_ids": ["E-001"],
      "plot_beat_ids": ["P-001"],
      "status": "pending",
      "summary_only": false,
      "scene_complete": null
    }
  ],
  "final_status": "deferred_to_final_contracts"
}
```

实际回执可保留旧人工骨架以兼容偏差回退，但默认提交不要求补写。最终两份全文合同仍须完整填写真实正文证据，不能用延后回执代替。

默认优先走高层总入口 `batch_section_review_cycle.py`。它把“逐节确定性回执 -> 预检 -> 提交”收束成固定公开入口，并按项目目录自动推导 `逐节正文进度.json / 当前节暂存/第N节.md / 逐节验收/第N节.json / 当前节写作包/第N节.json`：

```bash
python3 "$SKILL_ROOT/scripts/batch_section_review_cycle.py" prepare-section-review \
  --project "{项目名}" \
  --project-dir "{项目目录}" \
  --section N

python3 "$SKILL_ROOT/scripts/batch_section_review_cycle.py" preflight-section-review \
  --project "{项目名}" \
  --project-dir "{项目目录}" \
  --section N

python3 "$SKILL_ROOT/scripts/batch_section_review_cycle.py" status \
  --project "{项目名}" \
  --project-dir "{项目目录}" \
  --section N

python3 "$SKILL_ROOT/scripts/batch_section_review_cycle.py" next-step \
  --project "{项目名}" \
  --project-dir "{项目目录}" \
  --section N

python3 "$SKILL_ROOT/scripts/batch_section_review_cycle.py" run-section-review-cycle \
  --project "{项目名}" \
  --project-dir "{项目目录}" \
  --section N

python3 "$SKILL_ROOT/scripts/batch_section_review_cycle.py" emit-shell-template \
  --project "{项目名}" \
  --project-dir "{项目目录}" \
  --section N
```

`prepare-section-review` 默认只创建确定性延后回执；`status / next-step` 不再等待人工回填；`run-section-review-cycle` 预检通过后直接代跑底层 `commit-section`。偏差模式仍可显式使用人工侧车，脚本不代填任何语义裁决。

## 命令

以下命令是固定公开接口。直接替换 `N` 和真实路径执行；禁止先运行 `validate_section_progress.py --help`、任一子命令 `--help`，也禁止读取参数解析源码或旧项目命令反推参数。参数速记：`status / finalize / sync-pending-contracts` 只接受 `--state`；`start-section / commit-section / reopen-section / discard-writing-section` 均接受 `--state --section`，其中 `start-section` 还要 `--plan`，`commit-section` 还要 `--staged --review`。默认逐节回执固定走 `init -> preflight -> commit-section`。

```bash
python3 "$SKILL_ROOT/scripts/validate_section_progress.py" init \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --outline "{项目目录}/小节大纲.md" \
  --draft "{项目目录}/正文.md" \
  --prose-receipt "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --emotion-receipt "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --budget "{项目目录}/写作资产/逐节字数预算.json"

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" status \
  --state "{项目目录}/写作资产/逐节正文进度.json"

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" start-section \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --section N \
  --plan "{项目目录}/写作资产/当前节计划/第N节.json" \
  --context-output "{项目目录}/写作资产/当前节写作包/第N节.json"

python3 "$SKILL_ROOT/scripts/init_section_review.py" \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --section N \
  --staged "{项目目录}/写作资产/当前节暂存/第N节.md" \
  --output "{项目目录}/写作资产/逐节验收/第N节.json"

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" commit-section \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --section N \
  --staged "{项目目录}/写作资产/当前节暂存/第N节.md" \
  --review "{项目目录}/写作资产/逐节验收/第N节.json"

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" recover-half-commit \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --section N \
  --staged "{项目目录}/写作资产/当前节暂存/第N节.md" \
  --review "{项目目录}/写作资产/逐节验收/第N节.json"

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" reopen-section \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --section N

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" sync-pending-contracts \
  --state "{项目目录}/写作资产/逐节正文进度.json"

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" discard-writing-section \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --section N

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" finalize \
  --state "{项目目录}/写作资产/逐节正文进度.json"
```

`final_ready` 后才执行全文 `bind-draft`。绑定生成全文复核骨架后，当前模型必须基于最终正文逐节填写两份合同，再运行各自的 `validate-draft`。全文终审是默认延后模式的必需收口，不得因逐节状态已 passed 而跳过。
