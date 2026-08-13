# 逐节正文进度硬闸

本闸把“逐节写、逐节验、逐节回填”落实成状态机。正文放行后必须先初始化本闸；没有 `逐节正文进度.json`，禁止创建 `正文.md`。

## 状态机

固定顺序：

`先写场面计划 -> start-section N -> 在独立暂存稿中一次写完第 N 节 -> 填第 N 节回执 -> commit-section N -> 原子写入正文 -> start-section N+1`

`正文.md` 只是已通过小节的成稿，不是试写区。当前节在 `写作资产/当前节暂存/第N节.md` 一次成形；只有 `commit-section` 可以把它追加到正文。

硬限制：

- `start-section N` 前，正文只能存在已经通过的 `1..N-1` 节。
- `start-section N` 必须传入本节场面计划。计划必须把全部 E/P 拍同序聚合到 `1-3` 个完整场面，并为每场分配字数、进场压力、三步交流链、转折动作、可见后果和余波。
- 场面计划必须来自已通过的 `细纲表演验收回执.json` 的同节 `scene_units`，并绑定该回执 SHA。正文阶段只能领取上游已决定的场面容量，不得临时把事件压缩成概括。
- 场面计划的字数之和必须在本节预算内，且不得将承重场面分配为少于 `240` 字的梗概槽。装不下时必须先拆节或回写细纲，不得进入正文。
- 写第 N 节时禁止出现 `N+1.` 或任何未来小节标题。
- 暂存稿必须先完成全节字数、场面和语义验收，再原子写入正文。禁止先把短稿写进正文，再追加对白、背景、动作或情绪凑字数。
- 第 N 节验收时，已通过的旧节文本 SHA 必须保持不变。
- 第 N 节必须满足预先分配的字数区间、`5-9` 条正向首写约束、完整场面表演、文字逐句映射、完整 E/P 拍和真实引句。“ID 出现 / 事件被提到 / 有一句引句”均不等于事件成立。
- 初始化前，主体全部 `SF-*` 必须以非模板化人工理由分配到一个或多个目标数字小节；不得留空，也不得按编号平均轮转。
- 第 N 节验收必须完整覆盖写前包中的连续原文链、正反例、对白包、句间关系、逐句特征、活性、人物、全部直接对白和分配到本节的全部 SF 六维。至少四条句子映射只是不再单独成立的底线，不能冒充完整文字合同。
- `full_bridge` 还必须在初始化前把主体八类细节卡逐卡分配到目标小节；第 N 节提交时逐卡绑定当前节证据。细节卡仍为 `pending`、未分配或未进入逐节回执时，本节不得通过。
- 每个 SF 除六维文字颗粒外，必须按 `required_sequence` 原顺序逐步填写当前节引句、可见变化和人工裁决。一个相似动作或一条总括引句不能覆盖多步完整链。
- 回执中的 `current_model_manual` 和 `automation_used=false` 只是声明，不是机器可证明的事实。发现项目脚本、循环字典或模板批量生成语义字段时，必须判整节合同无效；禁止以验证器只检查非空为由继续使用。
- `status`、`start-section`、`commit-section`、`sync-pending-contracts` 和 `finalize` 均不得信任旧状态名，必须先核对当前正文逐节 SHA；`final_ready` 额外核对全文 SHA。正文被状态机外修改后直接阻断。
- E/P 不只核对 ID：E 拍必须核对来源 `role / intensity` 和目标 `trigger / relationship_position_change / reader_effect`；P 拍必须核对动作等价、外部变化和关系后果。
- 每个承重场面必须引用不同的 `进场压力 / 至少三步施压与接招 / 转折动作 / 可见后果 / 场末余波` 原句。一句概括不得重复充当这些字段。
- E/P 逐拍裁决大量复用同一组套话时直接失败；不得用通用脚本生成“已迁移、已换主、已产生后果”等语义回执。
- 回执有待改项时不能写 `passed`；先只修当前节，再重新验收。
- `commit-section N` 未输出 `section_passed`，禁止将当前节写入正文或开始下一节。
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

先用 `init_section_review.py` 从当前进度状态与文字合同初始化 `pending` 空骨架，再由当前模型完整读取本节正文逐字段人工回填。初始化器只复制 E/P/SF ID 与主体来源证据，禁止自动挑选目标引句、轮转证据、生成语义判断或填写 `passed`；不得用项目专属脚本重新实现同一结构。

```json
{
  "section_id": "1",
  "first_draft_mode": "single_pass_scene_realization",
  "complete_before_target_write": true,
  "substantive_append_or_expansion_after_target_write": false,
  "positive_generation_constraints": ["5-9 条本节正向约束"],
  "reviewed_current_section_only": true,
  "semantic_review_method": "current_model_manual",
  "automation_used_for_semantic_judgment": false,
  "prose_review": {
    "status": "passed",
    "sentence_mappings": [
      {"quote": "当前节真实原句", "source_anchor": "主体原文锚", "judgment": "句面迁移判断"}
    ]
  },
  "emotion_review": {
    "status": "passed",
    "emotion_beat_ids": ["E-001"],
    "plot_beat_ids": ["P-001"],
    "beat_reviews": [
      {"beat_id": "E-001", "quote": "当前节真实原句", "judgment": "烈度与关系位移判断"}
    ]
  },
  "scene_realization_reviews": [
    {
      "scene_id": "S1-01",
      "emotion_beat_ids": ["E-001"],
      "plot_beat_ids": ["P-001"],
      "status": "passed",
      "summary_only": false,
      "scene_complete": true,
      "entry_pressure_quote": "当前节进场压力原句",
      "interaction_exchange_quotes": ["施压原句", "接招原句", "二次变化原句"],
      "turning_action_quote": "转折动作原句",
      "visible_consequence_quote": "现实后果原句",
      "aftershock_quote": "场末余波原句",
      "reader_emotion_progression": "读者情绪如何逐步变化",
      "why_not_summary": "为什么这是一场完整戏而非事件概括",
      "manual_judgment": "当前模型对进场、交流、转折、后果和余波的具体裁决"
    }
  ],
  "issues_fixed": [],
  "final_status": "passed"
}
```

实际回执仍须包含文字合同和情绪合同要求的完整逐节字段；此处只展示进度闸会先行检查的公共最小字段。所有 `quote` 必须属于当前节，不能用其他节或细纲原句代替。

## 命令

以下命令是固定公开接口。直接替换 `N` 和真实路径执行；禁止先运行 `validate_section_progress.py --help`、任一子命令 `--help`，也禁止读取参数解析源码或旧项目命令反推参数。参数速记：`status / finalize / sync-pending-contracts` 只接受 `--state`；`start-section / commit-section / reopen-section / discard-writing-section` 均接受 `--state --section`，其中 `start-section` 还要 `--plan`，`commit-section` 还要 `--staged --review`。需要逐节回执时，先运行 `init_section_review.py --state ... --section N --output ...`，再人工回填并提交。

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
  --plan "{项目目录}/写作资产/当前节计划/第N节.json"

python3 "$SKILL_ROOT/scripts/init_section_review.py" \
  --state "{项目目录}/写作资产/逐节正文进度.json" \
  --section N \
  --output "{项目目录}/写作资产/逐节验收/第N节.json"

python3 "$SKILL_ROOT/scripts/validate_section_progress.py" commit-section \
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

`final_ready` 后才执行全文 `bind-draft`。绑定生成全文复核骨架后，按已验证的逐节回执逐节合并到两份合同，再运行各自的 `validate-draft`。全文绑定只汇总最终 SHA，不能代替随写验收。
