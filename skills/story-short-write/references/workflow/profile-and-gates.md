# Profile 与门禁闭环

> 本文件承接读取、台账、顺序、开头、细纲、正文前合同和停靠链的完整口径。进入正式项目流程时必须完整读取。

## 目录

- [profile 闭环](#profile-闭环)
- [写作规则读取硬闸](#写作规则读取硬闸)
- [拆文读取硬闸](#拆文读取硬闸)
- [规则执行硬闸](#规则执行硬闸)
- [优先工具化的合并点](#优先工具化的合并点)
- [开头承重契约硬闸](#开头承重契约硬闸)
- [全文文字颗粒度硬闸](#全文文字颗粒度硬闸)
- [正文前总放行固定前置顺序](#正文前总放行固定前置顺序)
- [全文情绪颗粒度硬闸](#全文情绪颗粒度硬闸)
- [默认闭环与初稿停靠](#默认闭环)

## profile 闭环

### 写作规则读取硬闸

写 `设定.md`、`小节大纲.md` 或 `正文.md` 前，必须先：

1. 运行 `validate_writing_rule_gate.py init`
2. 实际读取当前工作区的 `format-and-structure.md`、`anti-ai-writing.md`、`craft/narrator-voice.md`
3. 逐文件回填真实证据词、读取结论和写作用途
4. 运行 `validate_writing_rule_gate.py validate --stage {setting|outline|draft}`，只把当前即将生成的目标作为 `--output`

只有输出 `writing_rule_gate: passed` 才能继续。规则文件内容或 SHA 变化后，旧回执立即失效；不得用历史上下文、旧摘要或旧审计结果代替当前文件。

完整命令和回执字段见：

- [references/governance/writing-rule-reading-gate.md](../governance/writing-rule-reading-gate.md)

### 拆文读取硬闸

写 `设定.md`、`小节大纲.md` 或 `正文.md` 前，必须先：

1. 对每本选中的主体 / 辅助拆文运行 `validate_source_read_gate.py init`；目标回执已存在时由脚本自动归档旧文件并原子生成新回执，禁止调用方手工删除或搬移旧回执
2. 实际逐文件读取回执列出的全部拆文资产
3. 回填证据词、读取结论和写作用途
4. 运行 `validate_source_read_gate.py validate`，显式传入设定、大纲和正文路径做时序检查

只有输出 `source_read_gate: passed` 才能继续。以下情况一律阻断：

- 只读项目内二手摘要、设定或大纲
- 只读 `profile_source.md`
- 只读 `book.profile.json / project.profile.json`
- 拆文目录缺主报告、16 表、8 库、写作资产或动态字典
- 正文写完后再补读取回执

缺资产必须重新执行 `story-short-analyze` 全量拆书，不做兼容回退。完整命令和回执字段见：

- [references/governance/source-reading-gate.md](../governance/source-reading-gate.md)

### 规则执行硬闸

`writing_rule_gate` 和 `source_read_gate` 通过后、写设定或大纲前，必须：

1. 运行 `validate_rule_execution_ledger.py init`
2. 运行 `export-model-review` 生成只含规则索引与计数的紧凑清单，再按批运行 `read-model-review-batch` 从绑定台账即时读取完整 `cases/source_refs`；当前写作模型逐族阅读后写出统一 `canonical_rule_text`
3. 运行 `export-model-group-plan` 生成 v2 紧凑人工计划骨架；模型只填写 `member_ids / canonical_rule_text / taxonomy_decision / classification_notes / applicability / decision_reason`，适用规则再填 `target_stage / target_scene`
3a. 若 skill 已提供公共 `规则模型归并 preset`，先按 `source_path_suffix + 单规则文本指纹` 执行官方预填；固定命名的职责资产允许走 `asset_family`。preset 只允许回写 `canonical_rule_text / taxonomy_decision / taxonomy / classification_notes`，严禁复制 `applicability / decision_reason / target_stage / target_scene`。无匹配、规则文本变化或公共字段冲突的组保留待人工复核
4. `taxonomy_decision=accept_suggestions` 才允许确定性复用台账已有分类；`override` 必须显式补三项 taxonomy。`status/outcome/确认标记` 由 `decision_stage=prewrite` 与明确选择展开，不再人工重复填写
5. 模型用 `apply-model-groups --source-review ... --consume` 应用归并计划。任一 canonical 尚未完成写前分类与执行计划时，禁止写设定、大纲或正文；成功后分类批次与归并计划只保留消费回执
6. 写作过程中执行一项标记一项，并持续补脚本产物或人工原句证据
7. 最终绑定设定、大纲、正文 SHA，再运行 `validate_rule_execution_ledger.py validate`

进入任一写作阶段前，还必须运行写作放行闸：

最小口径：

- `setting` 阶段至少校验：`写作规则读取回执.json`、`拆文读取回执.json`、`规则执行台账.json`
- `outline` 阶段额外校验：`设定顺序契约回执.json`
- `draft` 阶段额外校验：完整顺序契约、开头承重契约、细纲表演验收、文字合同、情绪合同、主体原文路径、情绪总账路径、`project.profile.json`

输出不是 `write_release_gate: passed` 时，当前模型必须停止，不能生成或修改目标产物。

各阶段完整命令模板见 [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)。

设定产出后、开始写大纲前，必须先建立并人工回填设定内部顺序契约：

固定流程只有两步：先 `init-setting` 建骨架，再由当前模型人工回填 `canonical_sequence / manual_judgment / 设定原句 offset / 冲突取舍` 后执行 `validate-setting`。

只有输出 `setting_sequence_contract_gate: passed`，才能为大纲运行写作放行：

大纲写完后，必须重新初始化完整顺序契约，人工核对设定与大纲的 canonical 顺序后，才允许写正文；正文节点和 `offset` 必须在正文生成后补齐并重新校验。不得把“设定顺序回执已通过”当成正文顺序已通过。

大纲通过完整顺序契约和开头承重契约后，还必须通过细纲表演验收。该闸门逐节检查原文机制是否真正落成场戏设计，且细纲与选中原文任一 SHA 变化都必须重新验收：

固定流程：先 `validate_outline_performance_contract.py init` 绑定大纲与选中原文 SHA，再由当前模型人工回填后执行 `validate`。主体与辅助原文参数必须显式传入，不得靠旧回执猜路径。

输出不是 `outline_performance_contract: passed` 时，禁止写正文；完整口径见 [细纲表演验收硬闸](../governance/outline-performance-contract-gate.md)。

固定分工：

- 脚本：SHA、格式、字数、频率、禁词、固定模式、字段与文件完整性；所有正文/回执/审计中的字数统一由 `count_words.py` 计算
- 人工：人物偏手、失控说话、注意力漂移、认知局限、作者代判、对白生活性
- 混合：长窗节奏、对白效率、桥段相似度、profile 覆盖

固定修复边界：

- 流程门禁失败只修读取、回执、顺序或执行记录
- 设定约束失败修 `设定.md`
- 大纲约束失败修 `小节大纲.md`
- 审计规则只负责定位和裁决
- 拆书候选按需选用，禁用规则只查污染
- 只有失败的适用正文约束进入正文修改单

普通动作、物件、对白和生活细节在自由创作中可作为候选按需选用；`full_bridge` 仿写中，主体 `原文细节库` 八类卡固定进入细节全集合同，逐卡迁移，不得标为候选未选。以下关键来源契约也不允许被“候选可跳过”口径吞掉：

- `book.profile.json`
- `事实与推断台账.md`
- `写作资产/样本分级与可学层.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/桥段施工卡.md`
- `写作资产/高敏桥段识别.md`
- `写作资产/同桥段过检规则.md`
- `写作资产/仿写约束_禁写清单.md`
- `可直接仿写_顺序事件表.md`
- `可直接仿写_后果链表.md`
- `可直接仿写_外部秩序表.md`

这些文件无论按规则级展开还是保留为文件级资产，被合并后 canonical 都必须对每个 `source_ref` 分别记录 `applied / not_selected / prohibition_checked`、源文件原句、人工判断和目标证据。主体的顺序、后果、外部秩序和公开场后果资产也不能标 `not_selected`。

规则级资产父节点不要求人工再填一遍。运行 `refresh-summary`、`apply-plan` 或 `apply-model-groups` 时，脚本按子规则自动派生父节点的 `applicability / status / outcome / result`；父子状态不一致时直接阻断。

设定/大纲规则若覆盖多个目标场景，还必须把 `target_scene` 中的每一项分别写入 `structural_claim_reviews`。不能用“后果链成立”的证据同时证明开头、反转和追妻线均已通过。

额外挂载的题材规则或专项规则必须通过 `--skill-rule-file` 加进同一台账。完整字段和命令见：

- [references/governance/rule-execution-ledger.md](../governance/rule-execution-ledger.md)

### 优先工具化的合并点

下面这些环节允许做成官方 batch 入口，减少执行时的零散动作；但 batch 只负责“同类步骤连续完成”，不负责替当前模型生成语义裁决：

1. `读取批次入口`
   - 顺序串起 `validate_writing_rule_gate.py init/validate` 与 `validate_source_read_gate.py init/validate`
   - 允许一次创建两份读取骨架、一次校验两道读取门禁
   - 不允许自动生成 `evidence_terms / takeaways / used_for`
2. `纲前放行批次入口`
   - 顺序串起 `规则执行台账初始化 -> 设定顺序契约 init -> 完整顺序契约 init -> 开头契约 init -> 细纲表演验收 init`
   - 只负责创建骨架、绑定当前 SHA、刷新失效态
   - 现已支持按项目目录自动推导正式路径，并提供 `status / next-step / emit-shell-template / start-outline-release` 高层总入口
   - 不允许自动生成 `canonical_sequence / manual_judgment / target_evidence / plot_beat_mapping / source_emotion_parity`
3. `正文前合同批次入口`
   - 顺序串起 `文字颗粒度 bind-outline/apply-section-plan/validate-prewrite` 与 `情绪颗粒度 assemble-section-plan/validate-prewrite`
   - 允许统一检查主体原文路径、情绪总账路径、细纲 SHA 是否一致
   - 不允许自动生成 `continuous_source_chain_packets / relation_micro_examples / dialogue_voice_packets / section_contracts` 等人工语义字段
   - 进入该批次前的固定硬前置顺序必须是：`profile 已存在 -> 项目写作配置已绑定 primary 路径 -> 逐拍语义映射已初始化并准备人工补写 -> 书级文字资产/细节卡计划/情绪人工计划按各自正式入口落盘`
   - 若 `全文文字颗粒度契约回执.json / 全文情绪颗粒度契约回执.json` 仍是官方 `pending` 空骨架，只能判定为“脚手架态”，继续走 `apply-source-assets / apply-detail-plan / apply-section-plan / assemble-section-plan`；不得把它误判成坏数据后直接硬补正式大 JSON

硬口径：

- batch 入口只能做骨架初始化、参数转发、SHA 绑定、失效检测、确定性合并和统一校验摘要。
- 任何 `manual_judgment / comparison / target_evidence / source_contract_reviews / parity_status / keep-revise` 仍必须由当前模型逐项填写。
- 如果某一类回执反复需要 here-doc Python 才能勉强推进，优先补官方 batch 或侧车脚本，不再默认接受现场临时拼装。

当前已提供：

- `batch_read_gates.py`：覆盖“读取批次入口”，负责新项目总入口 `start-new-project-read-gates`、项目骨架 `bootstrap-project`、外层 `emit-shell-template`、两道读取门禁的 init/validate 编排，以及读取批次的 `prepare-batches/status/show-batch/next-step/run-read-gates-cycle/finalize-batches/export-batches/apply-batch/apply-manifest` 中段；高层命令优先，底层命令只用于排障或单批重试。`bootstrap-project` 只建标准目录和 `项目骨架索引.json`，不提前创建设定/大纲/正文；在新项目场景下，它既接受“不存在的目标路径”，也接受“已按目录硬闸创建、但尚未初始化任何文件的空目录”；目录里一旦已有正式文件或历史内容，仍按占用阻断。`show-batch` 是官方只读排障入口，用来查看单个 `batch-*.json` 的条目列表、相对路径和文件开头预览，替代流程中临时写 Python / `jq` 查批次内容。`export-batches` 重导出时会按 `gate + relative_path (+ source_root)` 从正式回执自动回填已经人工完成的 `evidence_terms / takeaways / used_for`；某一批全部条目都已在正式回执中补齐时，会直接恢复为 `reviewed`，避免 `apply-batch --consume` 后续跑时把已完成批次刷回空白。可选 `--print-paths-json` 输出机器可消费路径 JSON；`emit-shell-template` 可直接吐出完整外层 shell；`start-new-project-read-gates` 可把新项目初始化和读取门禁续跑接成一条正式命令；批次显式走 `pending -> in_progress -> reviewed -> consumed`，`status` 可只读汇总整份清单进度并输出批次简表，`next-step` 可直接给出下一条正式命令，`run-read-gates-cycle` 可按当前状态自动继续执行；脚本只切分正文、绑定 SHA、校验和合并，不代填 `evidence_terms / takeaways / used_for`。

读取批次状态必须显式传入两份正式回执和清单，完整命令固定为：

```bash
python3 "$SKILL_ROOT/scripts/batch_read_gates.py" status \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --manifest "{项目目录}/写作资产/读取批次/manifest.json"
```

- `batch_outline_release.py`：覆盖“纲前放行批次”中的骨架初始化，负责规则执行台账 init、顺序契约 init、开头契约 init、细纲表演验收 init，以及可选的规则模型复核批次导出。现已支持按项目目录自动推导正式路径；高层命令优先，推荐先看 `status / next-step`，直接执行时用 `start-outline-release`，外层封装可用 `emit-shell-template`。
- `export-model-review` 默认只导出绑定台账 SHA 的紧凑批次索引，不再复制全部 `cases/source_refs`；逐批语义复核使用 `read-model-review-batch` 即时展开，只有旧流程兼容时才允许 `--expanded`。
- `batch_rule_model_review.py`：覆盖规则模型复核中段，负责 `export-model-review -> export-model-group-plan -> 人工归并计划判断 -> apply-model-groups --consume -> validate-prewrite` 的高层总入口。现已支持按项目目录自动推导 `规则执行台账.json / 规则模型分类批次.json / 规则模型归并计划.json`，并提供 `prepare-model-review / status / inspect-all-model-review-batches / inspect-model-review-batch / next-step / run-model-review-cycle / emit-shell-template`。默认运行 `inspect-all-model-review-batches`，一次展开清单中的全部批次，生成 `写作资产/规则模型复核展开/batch-NNN.json` 和 `全部批次索引.json`；只有明确回查某一批时才使用 `inspect-model-review-batch --batch N`。两者都只整理完整 `cases/source_refs`、紧凑索引和缺项统计，不代做 `canonical / applicability / decision_reason` 等语义裁决。
- `validate_rule_execution_ledger.py apply-model-group-presets`：按公共 `references/integration/rule-model-group-presets.json` 中记录的 `source_path_suffix + rule_text_sha256` 单规则指纹，自动把稳定公共字段预填回 `规则模型归并计划.json`；固定命名职责资产可走 `asset_family`。它不会复制项目适用性、理由或目标场景，已有人工字段冲突时只报告、不覆盖。
- `validate_rule_execution_ledger.py export-model-group-preset-candidates / merge-model-group-preset-candidates`：前者从已人工裁决计划导出 v2 公共候选并拒绝无效 taxonomy，后者只晋级显式 `--source-prefix` 范围并保留旧库中的固定资产职责，替代手工 `jq` 拼公共 preset。
- `batch_draft_prewrite.py`：覆盖“正文前合同批次入口”，负责文字/情绪两份合同的 prepare/validate 编排，并统一阻断缺失的主体原文、子流程索引、情绪总账、细纲或侧车计划。
- `batch_prewrite_release.py`：覆盖“正文开写前最终放行批次”，并提供更高层的 `prepare-validate` 总入口。它可顺序执行正文前合同批次 prepare、细纲表演验收 validate、正文前合同批次 validate 和 `validate_write_release_gate.py draft`，统一收口正文开写前的机械校验摘要；仍不代填任何人工裁决字段。
- `batch_prewrite_release.py` 在同一进程内复用已经按绝对路径和当前 SHA 成功校验的细纲、文字、情绪合同，避免最终放行闸再次全量解析同三份合同；任一路径或 SHA 不匹配即自动回退完整重验，独立调用 `validate_write_release_gate.py` 仍执行全量校验。
- `init_project_writing_assets.py`：只负责初始化项目级空骨架 `项目写作配置.json / 逐拍语义映射.json / 逐场语义映射.json`，不负责生成人工语义；初始化后必须立即补齐 `项目写作配置.primary.{name,profile_path,original_path,emotion_ledger_path,plot_ledger_path}` 等确定性绑定，再进入正文前合同阶段。不得带着空白 primary 配置继续跑正文前总放行。
- 任一 `deterministic / repair / receipt / sidecar` 类辅助脚本若要进入 skill 正式工具链，只能做 `schema 初始化 / SHA 绑定 / 路径同步 / 当前模型已写明字段的确定性序列化`。禁止硬编码题材词、物件词、场景名、人物称呼、桥段名、书名、节号范围或正则词尾来替当前模型做语义判断；开放语义类别只能靠通用结构规则与正式人工字段承接，不能再加项目特化黑白名单。
- `repair_outline_receipt_deterministic.py` 已永久停用并 fail-closed。它不得重建或重绑 `target_plot_beats / target_emotion_sequence / evidence`，不得写入 `adapted / passed / reviewed_by_current_model`；语义损坏只能从正式真源重新导出窄侧车，由当前模型逐拍复核后通过 `apply-* --consume` 回写。
- 书级文字资产文件一旦改动，正式文字合同中的文件绑定立即失效：`成文活性层资产.md` 或 `人物性格颗粒资产.md` 任何一处改字后，必须同步刷新 `全文文字颗粒度契约回执.json` 内对应层的 `asset_file.path/sha256` 与被引用的书级字段；旧 SHA 下继续 `validate-prewrite` 一律按过期合同处理。已经 `--consume` 的 `书级文字资产侧车.json` 只剩消费回执意义，不得再当可编辑真源续改。
- `manage_outline_bridge_review.py sync-source-emotions`：按 `source_bridge_id + source_path` 从主体 `全文情绪颗粒总账.json` 精确同步 `outside_bridge_plot_parity / outline_bridge_flow_parity[*].source_emotion_sequence`，只消费原文真源，不生成 `target_emotion_sequence`。
- `manage_outline_bridge_review.py export-template/apply-template`：只导出/合并桥级非逐拍人工字段。
- `manage_outline_bridge_review.py export-beat-template/apply-beat-template`：只导出/合并桥级逐拍人工字段 `target_plot_beats / plot_beat_mapping / target_emotion_sequence / 反刀位 / 峰值位`，避免直接手改大 JSON。
- `export-beat-template` 产出的桥级逐拍侧车带当前正式回执 `receipt_sha256`。只要之后执行过 `rebind-outline` 或正式回执被其他官方入口改写，就先刷新侧车 SHA 或重导侧车，再 `apply-beat-template`；不要拿旧侧车直接试合并。当前推荐链路是 `apply-beat-template --refresh-sidecar {下一节/下一桥侧车}`，把后续窄侧车绑定一起刷新掉。
- `manage_outline_bridge_review.py rebind-outline/seal-review`：前者在细纲改动后重绑 `outline.sha256` 并把 `reviewed_by_current_model / gate_status` 重置为待验收；后者会调用正式 `validate_outline_performance_contract.py` 真实校验，通过后才把顶层通过态落盘。
- `batch_outline_review_cycle.py`：覆盖细纲表演验收人工回填链，负责 `sync-source-emotions -> 导出桥级/逐拍/节级侧车 -> 判断人工阶段是否补完 -> apply+consume 三份侧车 -> rebind-outline -> seal-review` 的高层总入口。现已支持按项目目录自动推导 `细纲表演验收回执.json / 小节大纲.md / 桥级回填侧车.json / 桥级逐拍回填侧车.json / 节级回填侧车.json`，并提供 `prepare-outline-review / status / next-step / export-next-compact / run-outline-review-cycle / emit-shell-template`。
- 细纲表演验收人工回填的默认推进顺序改为：优先 `prepare-next-fill-pair` 一次导出当前桥级逐拍和当前节级两份窄侧车，人工补完后立刻 `apply-fill-pair --next-bridge-output ... --next-section-output ...` 串行回写并自动导出下一组；只有脚本入口缺失时，才退回 `export-next-compact + apply-* --refresh-sidecar`。`status / next-step` 退回到阶段切换、封口前总检查或真实异常排障时才使用，不再作为每补一条后的常规动作。
- `batch_section_review_cycle.py`：覆盖逐节正文确定性提交链，负责 `prepare-section-review -> preflight-section-review -> commit-section -> status` 的高层总入口。默认不创建、不等待、不消费人工侧车，只按项目目录自动推导并绑定 `逐节正文进度.json / 当前节暂存/第N节.md / 逐节验收/第N节.json / 当前节写作包/第N节.json`；仍提供 `prepare-section-review / preflight-section-review / status / next-step / run-section-review-cycle / emit-shell-template`。
- 逐节写后默认使用 `deferred_full_contract_review`。当前模型仍须在落盘前完整通读本节并立即重写任何未兑现、错脸、摘要化或偏离项，但不再把同一批逐句、对白、E/P、SF、细节卡、场景和人物判断重复抄进逐节侧车。逐节回执只证明当前暂存稿、状态机、写前文字合同、写前情绪合同和完整场面领取的 SHA/ID 一致；全部独特人工语义统一在最终两份全文 `bind-draft/validate-draft` 中基于最终正文一次填写并完整校验。
- `delta_manual_review` 和旧全量 `manual_items` 仅作为偏差回退模式保留。当前节若不能确认忠实执行写前包，先修改正文；确需保留偏差说明或专项逐节证据时，显式导出侧车并完整通过对应预检，禁止把默认延后模式当作跳过最终终审的理由。
- `commit-section` 展开的完整 E/P 合同只允许作为临时校验视图；`status / validated_at / review_sha256 / text_sha256 / char_count` 必须写回 `state.sections[]` 的真实条目。每次输出 `section_passed` 后立即运行一次 `status`，必须同时看到当前节 `passed`、正确字数和下一节游标；任一不一致都按半提交阻断，禁止启动下一节。
- 若正文已包含与暂存稿逐字一致的当前节，正式回执已 `passed` 且完成侧车合并与机械归一化，但状态条目仍为 `writing`，只允许运行官方 `recover-half-commit`。禁止手改状态 JSON、重复追加正文、重做已通过人工侧车或误用 `discard-writing-section`。
- `batch_full_draft_review.py`：覆盖全文收口链，负责 `sections_passed -> finalize -> bind-draft(文字/情绪) -> 判断全文合同是否已补到可校验状态 -> validate-draft(文字/情绪) -> count_words / 可选知乎格式校验` 的高层总入口。现已支持按项目目录自动推导 `逐节正文进度.json / 正文.md / 全文文字颗粒度契约回执.json / 全文情绪颗粒度契约回执.json`，并优先从两份全文合同自动反推 `主体原文 / 全文情绪颗粒总账`，提供 `bind-full-draft-contracts / status / next-step / validate-full-draft / run-full-draft-cycle / emit-shell-template`。
- `batch_formal_audit.py`：覆盖正式审计链，负责 `run_full_ai_audit.py` 的默认全量审计启动、`正式审计/*.full_audit.json` 新鲜度检查，以及可选的题材首次校准 `compare_with_external_block_audit.py` 串联。现已支持按项目目录自动推导 `正文.md / 写作资产/正式审计 / 外部分块审计对齐摘要.json / 内部审计标准.json / 外部分块审计对齐.csv`，并提供 `status / next-step / run-audit-cycle / emit-shell-template`。
- `batch_postdraft_release.py`：覆盖停靠后的深审尾链，负责 `初始化正文开头契约/写后人工复核/completion 状态 -> 判断正文开头契约是否已补完 -> 自动接管正式审计链 -> 规则执行台账 preflight-final-rebind + bind-artifacts + validate -> 判断写后人工复核是否已补完 -> mark-complete` 的高层总入口。现已支持按项目目录自动推导 `规则执行台账.json / 顺序契约回执.json / 开头承重契约回执_正文.json / 写后人工语义复核回执.json / 短篇全流程状态.json`，并优先从 `拆文读取回执.json` 反推主体 `可直接仿写_导语拆解表.md`，提供 `prepare-postdraft-release / status / next-step / run-postdraft-release-cycle / emit-shell-template`。
- 桥级、节级、书级文字、逐节文字、逐节情绪和主体细节卡侧车在成功 `apply-*` 时统一追加 `--consume`；人工内容已完整进入正式真源后，不再长期保留第二份大 JSON。

批处理命令的完整清单只维护在：

- [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md) 的“官方批处理入口”
- [references/workflow/writing-workflow.md](writing-workflow.md) 的“正文前总放行示例”

这里仅保留最容易被遗漏的最终放行入口，避免同一组命令在主 skill 与参考文档重复漂移：

```bash
python3 "$SKILL_ROOT/scripts/batch_prewrite_release.py" validate \
  --writing-receipt "{项目目录}/写作资产/写作规则读取回执.json" \
  --source-receipt "{项目目录}/写作资产/拆文读取回执.json" \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --sequence-receipt "{项目目录}/写作资产/顺序契约回执.json" \
  --opening-contract "{项目目录}/写作资产/开头承重契约回执_大纲.json" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --outline "{项目目录}/小节大纲.md" \
  --prose-contract "{项目目录}/写作资产/全文文字颗粒度契约回执.json" \
  --emotional-contract "{项目目录}/写作资产/全文情绪颗粒度契约回执.json" \
  --primary-source-original "拆文库/{主体书}/原文/{主体书}.txt" \
  --source-emotion-ledger "拆文库/{主体书}/写作资产/全文情绪颗粒总账.json" \
  --profile "profiles/{项目名}.project.profile.json"
```

### 开头承重契约硬闸

主体拆书导语资产中的“功能顺序”和“为什么不能换序”不允许只作为普通 `outline_constraint` 留在台账中。写完大纲后、正文首写或开头回炉后，分别运行：

```bash
python3 "$SKILL_ROOT/scripts/validate_opening_contract.py" init \
  --project "{项目名}" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md" \
  --artifact-kind draft \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json"

python3 "$SKILL_ROOT/scripts/validate_opening_contract.py" validate \
  --receipt "{项目目录}/写作资产/开头承重契约回执_正文.json" \
  --source "拆文库/{主体书}/可直接仿写_导语拆解表.md" \
  --target "{项目目录}/正文.md"
```

主体导语资产或目标文本 SHA 变化、旧回执因此失效时，必须对同一路径重新执行上述 `init` 并追加 `--force`。`--force` 只允许用于重建已失效的同项目、同 `artifact-kind` 回执；重建后全部人工字段回到待审状态，必须重新读取来源开口与目标前 120 字并逐项回填，禁止只替换 SHA 或沿用旧 `passed`。

必须由当前模型读取主体 `可直接仿写_导语拆解表.md`、所有选中主体/辅助拆文的 `原文/` 开头样本和目标前 `120` 字，逐项填写原句证据。任一检查失败就改大纲或开头；不允许用“第一节最终有冲突”“本轮只改中后段”“已读 profile”或规则台账已通过替代本闸门。开头回炉后还必须人工确认不是分镜清单或规则施工单。

完整字段与命令见：

- [references/governance/opening-contract-gate.md](../governance/opening-contract-gate.md)

### 全文文字颗粒度硬闸

仿写、融合和原文声线参照任务在写正文前必须建立独立合同。该合同不问桥段做了什么，只问主体原文怎样说、目标稿是否仍按同类句间关系说话。主体原文独占声线权，辅助来源不得混入。

初始化、写前校准、逐节复核和初稿停靠前验证的完整命令见：

- [references/governance/prose-granularity-contract.md](../governance/prose-granularity-contract.md)

`validate-prewrite` 未通过不得写正文；它必须验证逐句全标注和与最终细纲一一对应的逐节落笔包。写正文时每节先读包、后落笔并完整通读，逐节只做确定性提交；全部小节结束后再统一回填最终正文映射。`validate-draft` 未覆盖每一个数字小节及其真实正文证据，不得报告“正文初稿已完成”。本门禁属于首写质量控制，不等同于用户尚未授权的深审。

文字颗粒度合同还必须绑定独立的成文活性层。写前资产、逐节 `liveliness_plan` 和写中 `liveliness_review` 任一缺失，或仍存在作者总结盖过人物现场，均不得以七维声线、52 项特征或脚本统计已通过为由放行。

### 正文前总放行固定前置顺序

`batch_prewrite_release.py prepare-validate` 不是正文前人工工作的起点，而是人工资产已经齐全后的总收口。进入它之前，固定顺序必须是：

1. `profiles/{项目名}.project.profile.json` 已存在；缺失时先生成，禁止拿“稍后再补 profile”继续撞总放行。
2. `写作资产/项目写作配置.json` 已存在且 `primary` 的 `name / profile_path / original_path / emotion_ledger_path / plot_ledger_path` 都已绑定真实主体路径；空白 primary 配置视为未初始化完成。
3. `写作资产/逐拍语义映射.json` 已初始化；细纲封口后优先补它，再补正文前合同。若 `细纲表演验收回执.json` 里已有正式 `target_emotion_sequence / target_plot_beats`，默认先跑 `sync-from-outline-contract` 回收已通过细纲的现成裁决，再人工补缺。未完成逐拍语义映射时，不得先扑到书级文字合同或情绪合同大 JSON 里试错。
4. 文字合同先走 `apply-source-assets` 补书级文字资产；随后先闭合书级层里的 `ultra_fine_source_baseline.source_passages`，至少完成 `5` 组 `80` 字以上连续主体原文逐句标注，覆盖至少 `4` 类场景。`source_passages` 未补齐前，不得开始正式逐节落笔包。
5. 书级层通过后，再走 `apply-detail-plan` 补主体细节卡写前映射，最后才走 `apply-section-plan` 补逐节落笔包。
6. 情绪合同先准备逐节人工计划，再走 `assemble-section-plan`，由已批准细纲合同和逐拍语义映射确定性装配正式情绪合同。
7. 只有以上资产都已进入正式真源后，才允许执行 `batch_draft_prewrite.py validate` 或 `batch_prewrite_release.py prepare-validate`。

机械阻断与人工阻断必须分开判断：

- `profile 不存在 / 项目写作配置 primary 为空 / 逐拍语义映射文件缺失` 属于前置资产缺失，先补资产。
- 两份全文合同仍是 `pending` 且大面积空字段，默认判定为“脚手架态”，说明还没走完正式 `apply-*`/`assemble-*` 链，不得直接编辑正式合同本体冒充推进。
- 只有正式入口已消费完侧车、字段本应成立却校验失败时，才算“坏数据态”，再回到对应真源资产或上游合同修。

正文前合同人工回填一旦开始，默认工作模式必须切成 `单链资产回填`：

1. 固定顺序只有 `逐拍语义映射 -> 书级文字资产闭合链 -> 主体细节卡写前映射 -> 逐节落笔包链 -> 情绪逐节人工计划 -> assemble-section-plan -> validate`。其中书级文字资产闭合链内部顺序固定为 `apply-source-assets -> source_passages 五组连续原文逐句标注 -> 书级层复核`；逐节落笔包链从 `apply-detail-plan` 之后才开始。
2. 同一时刻只允许推进这条链上的当前节点；补当前节点前，不得先把 `batch_draft_prewrite.py validate`、`batch_prewrite_release.py prepare-validate`、重复 `status / next-step`、项目内临时修补脚本、here-doc 诊断或多轮 `rg/sed` 巡检当成默认前置动作。
3. `validate` 只在当前节点的正式真源已经落盘后执行一次，用来确认下一堵墙；未补任何新人工字段却连续重跑同一验证，视为无效耗时。
4. 需要继续下一类资产时，以上一个正式回执为唯一真源重新导出或重建侧车；不得拿旧侧车、旧统计结果或旧临时脚本输出继续推下一步。
5. 书级文字资产仍存在 blocked 项时，不得提前进入 `apply-section-plan`；逐节落笔包链只能在书级层和细节卡计划都已进入正式真源后启动，避免书级层与 14 节落笔包同时半成品并行。
6. 逐节落笔包链默认按 `2` 节一批推进：`补 N/N+1 -> 批内四项自检 -> apply-section-plan --consume -> validate-prewrite 一次`。不要在补 `N` 节后立刻消费、再补 `N+1` 节、再消费。
7. 若 `validate-prewrite` 只剩当前已消费批次里的少量局部字段错误，直接把正式真源当唯一修点小范围回写并复校；不要为了这种局部错重建整份逐节侧车或再跑额外探路命令。

硬口径：

- 不得把 `prepare-validate` 当成“自动帮你初始化并顺手生成人工语义”的入口。
- 不得为了省一步，跳过 `逐拍语义映射 -> 书级文字资产/细节卡计划/情绪人工计划` 的固定顺序。
- 不得把官方空骨架误判成“已有正式合同，只差随手补两句”。
- 不得在正文前合同阶段先跑一串探索性脚本再开始补第一条人工字段；第一次人工落笔前只允许做当前节点所必需的那一条官方 `init/export/apply/assemble`。

### 全文情绪颗粒度硬闸

强情绪稿和所有主体原文仿写稿必须另建情绪合同。该合同不统计情绪词，而是逐节核对原文的情绪锯齿、即时主观声音、对手压力、旧伤触发和峰值动作是否在目标稿中同级兑现。完整字段与命令见：

- [references/governance/emotional-granularity-contract.md](../governance/emotional-granularity-contract.md)

`validate-prewrite` 未通过不得写正文，`validate-draft` 未覆盖所有数字小节不得停靠。合同必须固定首稿未执行去 AI 味；它属于生成合同，不属于成稿审计。

### 必备输入

默认至少需要：

- `写作资产/profile_source.md`
- `book.profile.json`

如果上游是仿写 / 融合 / 高敏同桥，再额外要求：

- `写作资产/样本分级与可学层.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/仿写约束_禁写清单.md`
- `写作资产/同桥段过检规则.md`

如果做融合稿，还必须有：

- 多本 `book.profile.json`
- 合成后的 `project.profile.json`

缺资产时的固定动作：

- 缺拆书资产：回 `story-short-analyze`
- 缺 `profile_source.md`：先补 `profile_source.md`
- 缺 `book.profile.json`：先生成 `book.profile.json`
- 融合稿缺 `project.profile.json`：先合成融合包

### 默认闭环

默认顺序固定是：

前置隔离：如果用户要求全新开书，先声明 `allowed_read_roots`和 `forbidden_legacy_roots`，将所有搜索与读取限定在用户指定样本、对应拆文库、skill 自身资源和本轮新目录；禁止查看任何旧项目内容或用旧项目作模板。

0. 如果任务是“全面重写已有短篇目录”，先完整备份当前目录，再把旧 `设定.md`、`小节大纲.md`、`正文.md` 移入 `写作资产/旧稿归档-{时间}/`；目标产物路径必须恢复为未生成状态后，才能初始化读取回执。禁止在旧三件套仍占用目标路径时强行回填回执，否则会被事后补填闸误判或绕闸。
1. 生成写作规则读取回执
2. 读取当前版三份必读规则并通过 `writing_rule_gate`
3. 生成拆文逐文件读取清单
4. 逐文件读取全部拆文资产并回填回执
5. 通过 `source_read_gate`
6. 初始化规则执行台账，逐项确认脚本 / 人工 / 混合分工和适用性
7. 读取 `profile_source.md`
8. 读取 `book.profile.json / project.profile.json`
9. 判断 `讲法型 / 桥段链型 / 混合型`
10. 写设定，同时逐项更新台账
11. 建立并通过设定内部顺序契约
12. 通过大纲写作放行闸，再写细纲
13. 建立并通过设定—大纲完整顺序契约
14. 对大纲执行开头承重契约硬闸
15. 对大纲执行细纲表演验收硬闸；主流程仿写必须先绑定独立的 `全文情节微拍总账.json`，再在回执中完成 `source_bridge_flow_inventory` 和 `outline_bridge_flow_parity`
16. 分别确认原文全部 `P-*` 情节微拍与全部 `E-*` 情绪拍已按原序逐拍迁移；两轨不得互相代替，缺失、弱化、并拍或只做功能映射时先重写细纲
17. 建立并通过全文文字颗粒度合同。硬口径只有三条：主体原文独占声线；最终细纲已绑定；逐节写前包与 `validate-prewrite` 已通过。52 项特征、连续句链、对白三联包、活性层和人物颗粒的完整字段统一见 [references/governance/prose-granularity-contract.md](../governance/prose-granularity-contract.md)。
18. 建立并通过全文情绪颗粒度合同。主体 `全文情绪颗粒总账.json` 必须按原序全集绑定，全部 `E-*` 逐拍唯一分配到数字小节，且各节并集与总账完全同序相等后才允许 `validate-prewrite passed`。逐拍语义、同级烈度、独占证据和 `P-*` 并轨要求统一见 [references/governance/emotional-granularity-contract.md](../governance/emotional-granularity-contract.md)。
19. 通过正文写作放行闸并初始化逐节状态机。必须先有逐节字数预算、`逐节正文进度.json` 和本节场面计划，正文只允许在独立暂存稿中一次完成当前节，通过 `commit-section` 后才原子写入 `正文.md`。未通过前不得创建下一节，不执行去 AI 味；实质问题必须整场或整节重写，禁止追加补丁。状态机与逐节回执硬口径统一见 [references/governance/section-progress-gate.md](../governance/section-progress-gate.md)。

执行时允许按批次连续收口，不要求把上述每一步拆成独立对话轮次。主 skill 只保留步号映射；批次内具体命令与串联顺序统一见 [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)：

- `读取批次`：对应 `1-5`
- `纲前放行批次`：对应 `6-16`
- `正文前合同批次`：对应 `17-18`
- `正文开写前最终放行批次`：对应 `19` 开写前的最终机械放行
- `正文前总放行批次`：`batch_prewrite_release.py prepare-validate`，用于把正文前合同 prepare、合同 validate 和最终放行闸并成一个总入口

硬口径：允许合并的是执行批次，不是治理对象本身。任一独立门禁未 `passed`，都只能停在当前批次内修正，不能先写下游产物再回补。
20. 全部小节逐节通过后运行进度闸 `finalize`；只有输出 `final_ready` 才绑定最终正文 SHA，将已验证的逐节回执合并到全文文字/情绪合同并运行 `validate-draft`；再运行 `count_words.py`，知乎 / 盐言正文另运行纯数字分节格式校验
21. **立即停靠并把正文交给用户预览**；禁止自动继续顺序重绑、正文开头契约、正式审计、去味、回炉、最终台账或完整人工语义复核
22. 只有用户看过初稿并明确回复“继续深审”“继续完整流程”或同义指令后，才补正文顺序节点证据并重新通过完整顺序契约
23. 对正文执行开头承重契约硬闸
24. 按通用规则和拆书资产定向回修
25. 完成正文规则资产复核后，直接做正式审计和全文人工语义复核；不再强制执行窗口切分
26. 生成包含全文人工病灶汇总的回修任务单
27. 定点回炉；正文 SHA 变化后重过平台格式、顺序、开头、正式审计和全文人工复核
28. 重新审计
29. 绑定最终写作产物并通过 `rule_execution_gate`
30. 全文人工语义复扫并通过 `post_write_human_review_gate`
31. 高风险任务再过第二闸门

### 正文初稿停靠硬闸

正文初稿全部写入 `正文.md` 后必须结束当前轮，不得把用户最初提出的“完整流程”“整套写完”解释为授权连续进入深审。停靠前只允许：

- 绑定并验证逐节维护的 `全文文字颗粒度契约回执.json`；该动作只裁决主体原文声线是否覆盖全文，不得顺带运行 AI 审计或开启新一轮回炉。
- 绑定并验证逐节维护的 `全文情绪颗粒度契约回执.json`；该动作只裁决主体原文情绪是否同级兑现，不得顺带清洗直接心理或运行去味。
- 运行 `count_words.py`，报告统一番茄口径字数。
- 平台为知乎 / 盐言时运行 `validate_zhihu_section_format.py`。
- 确认正文文件可读取；不得借基础检查之名修改、润色或回炉正文。

停靠回复硬要求：

- 必须明确区分“正文初稿已完成”和“完整流程已完成”不是一回事。
- 必须报告 `正文.md` 路径、`count_words.py` 结果、平台格式状态，以及“已停靠、尚未执行深审与回炉”。
- 必须把下一步限制为：`继续深审`、`修改指定小节/情节后重新停靠`、或 `只做去 AI 味`。
- 用户未明确选择下一步时必须停止；不得把等待用户预览视为流程阻断，也不得自行替用户选择深审。

停靠回复模板和后续链路展开见 [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)。

### 用户点名的单节原型测试

用户在全文写前合同尚未全部通过时明确要求“先写第一节/某一节测试成文效果”，允许生成一次非正式单节原型，但不得把它伪装成正文放行或逐节通过：

- 准入条件：目标小节自身的细纲场面、E/P/SF、主体细节卡写前映射、情绪合同和文字落笔包都已通过；缺任一项仍禁止生成。
- 落点限制：只写入 `写作资产/单节原型测试/第N节.md`；不得创建或修改 `正文.md`、`逐节正文进度.json`、正式逐节回执，也不得运行 `commit-section`。
- 身份限制：必须同步写 `原型状态.json` 绑定当前 SHA，并明确 `canonical_draft=false`、`reusable_as_committed_section=false`。
- 质量限制：写后仍按本节 E/P/SF/细节卡逐项人工核对；任一项弱化或缺失就直接重写，不能用“测试稿”降低颗粒标准。
- 复用限制：原型只能供用户判断声线、情绪和现场效果；用户确认继续后，仍须完成全文写前合同、正文放行和状态机初始化，再从空暂存稿正式重写该节；禁止复制原型后补回执。
- 数量限制：原型未通过时不得生成下一节；一次只允许存在一个当前原型。

这部分展开口径见：

- [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)
- [references/integration/story-profile-schema.md](../integration/story-profile-schema.md)
- [references/integration/profile-source-template.md](../integration/profile-source-template.md)

### 回修优先级

主 skill 只保留裁决骨架，不再重复展开全部回修说明。固定顺序：

1. 成文真实感
2. 题面 / 题材承诺 / 主卖点
3. 主桥和后果链
4. 冲突载体与人物交流
5. 灵动感和现场毛边
6. 流程硬化 / 分镜施工稿
7. `global_risk_shape`
8. 句壳、短段节奏和显性候选词

回修前必须声明：

- `primary_revision_rule`
- `protected_rules`
- `risk_of_rule_collision`

回修后必须人工复核：

- 主修规则是否真的改善
- 保护规则是否被破坏
- 若新修改打坏旧规则，本轮不得标 `passed`
- 报告必须列出 `主修规则 / 保护规则 / 冲突裁决 / 保留或二次修复理由`

绝对禁止：

- 跳过桥段承重件和顺序，直接润句
- 用低优先级规则机械覆盖高优先级规则
- 为去流程硬化删掉冲突载体、人物交流或追妻情绪
- 为补交流/补冲突堆动作，反把正文修成分镜清单或规则施工稿
- 只因均分下降或轻审计命中变少就停

完整优先级解释、字段示例和冲突裁决口径见 [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)。

### 脚本入口

主 skill 不再重复铺开所有脚本的完整参数模板。按职责查权威命令源：

- 读取门禁、规则台账、开头契约、全文放行总链路：
  [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)
- 文字颗粒度合同：
  [references/governance/prose-granularity-contract.md](../governance/prose-granularity-contract.md)
- 情绪颗粒度合同：
  [references/governance/emotional-granularity-contract.md](../governance/emotional-granularity-contract.md)
- 逐节状态机：
  [references/governance/section-progress-gate.md](../governance/section-progress-gate.md)

#### 颗粒度合同显式参数硬口径

- `validate_prose_granularity_contract.py validate-prewrite` 即使回执内已经绑定主体原文，命令行仍必须显式传入 `--source-original`。
- `validate_emotional_granularity_contract.py assemble-section-plan / validate-prewrite / validate-draft` 即使回执内已经绑定主体原文和情绪总账，命令行仍必须显式传入 `--source-original` 与 `--source-emotion-ledger`。
- 这些参数属于“本次校验输入”，不是可由回执自动补全的省略项。不得以“回执已绑定”为理由删参；缺任一显式参数按命令不完整处理，回到固定模板修正，禁止自行脑补为脚本可推断。

#### 逐节状态机固定模板

以下是保留在主 skill 的高频状态机模板，因为它们最容易被误用为 `--help` 试参：

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
# 默认生成 deferred_full_contract_review，不创建人工侧车。当前模型通读后若发现偏差，先重写正文；
# 只有专项排障或必须记录偏差时，才显式追加 --sidecar-output 并走 delta/full 人工侧车。
python3 "$SKILL_ROOT/scripts/batch_section_review_cycle.py" preflight-section-review \
  --project "{小说书名}" \
  --project-dir "{项目目录}" \
  --section N
# 预检必须输出 preflight_passed 才允许提交；默认检查当前暂存稿、状态、写前两份合同和场面 E/P 领取的 SHA/ID 一致性。
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
# 状态机参数固定：status / finalize / sync-pending-contracts 使用 --state；start-section / commit-section / reopen-section / discard-writing-section 使用 --state + --section。start-section 用 --context-output 同步生成紧凑写作包；init_section_review.py 默认创建 deferred_full_contract_review 确定性回执；commit-section 不传 --sidecar，校验当前暂存稿与写前合同绑定后原子提交。逐句/E/P/SF/细节卡与人物语义继续以写前正式合同为生成真源，并在全文 `bind-draft/validate-draft` 一次性收口。只有偏差节才显式追加 --sidecar-output / --sidecar，进入 delta 或旧全量侧车。脚本不能生成新的 comparison / manual_judgment / semantic_parity_status / 人物归属 / keep-revise。上述命令直接替换 N 和真实路径执行；禁止先运行主脚本或任一子命令的 --help，也禁止读取 argparse 源码探参；禁止再用 jq、临时 Python或项目脚本装配逐节正式回执。参数错误应回到本段固定模板修正，不得用 help 试错。
```

细纲表演验收回执变化后，统一刷新全部小节计划，禁止逐节重复调用：

```bash
python3 "$SKILL_ROOT/scripts/create_section_plan.py" \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --section all \
  --output-dir "{项目目录}/写作资产/当前节计划" \
  --beat-mapping "{项目目录}/写作资产/逐拍语义映射.json"
```

正文收口、正式审计和回炉的完整命令见：

- [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)

题材首次校准才用：

```bash
python3 "$SKILL_ROOT/scripts/compare_with_external_block_audit.py" \
  "{项目目录}" \
  --audit-dir "{项目目录}/写作资产/正式审计" \
  --output "{项目目录}/写作资产/外部分块审计对齐.csv" \
  --summary-output "{项目目录}/写作资产/外部分块审计对齐摘要.json" \
  --internal-standard-output "{项目目录}/写作资产/内部审计标准.json"
```

详细调用、产物、停机口径见：

- [references/governance/short-write-execution-core.md](../governance/short-write-execution-core.md)

---
