---
name: story-short-write
description: |
  短篇网文写作。辅助短篇小说创作，从全新起盘、来源筛选、设定、细纲到逐节正文首写、基础审计和定点回炉。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」「继续写」「重写第X节」
---

# story-short-write

执行短篇网文完整写作流程。优先保证原文事件、因果、情绪、表演和文风颗粒真正进入首写，不用事后润色补救写前缺失。

当前流程版本：`1.14.3`。

## 边界

- 本 Skill 负责起盘、换链、设定、细纲、正文、基础审计和定点回炉。
- 拆书、补齐无损编译包或升级来源资产必须转 `story-short-analyze`，不得在写作流程中自动执行。
- 已成稿的独立去味任务转 `story-deslop`；首写不能先写安全稿再依赖去味恢复颗粒。
- 禁止读取其他已写项目作为流程模板。流程只来自本 Skill、固定 references、固定 scripts 和本次选中的拆文来源。

边界细则见 [skill-boundaries.md](references/governance/skill-boundaries.md)。

## 上下文纪律

- 宿主已经注入本 `SKILL.md` 全文时，禁止再次 `cat`、`sed` 或分段重读本文件。
- 候选完成前只运行 `workspace-rules` 和 `candidate-subflows`；禁止主动加载其他 Skill、`.learnings`、旧 Session、旧项目文件或任何 references。
- `workspace-rules` 已负责返回当前工作区必须遵守的规范路径和摘要；禁止随后再次批量读取 `CLAUDE.md / AGENTS.md`。
- 每个阶段只读取“阶段资料”中当前阶段明确指定的一份 reference。禁止初始化后并行 `cat` 多份 references，禁止为了熟悉流程预读后续阶段资料。
- `规则语义输入.json` 已携带固定规则原文；读取它时禁止再打开 `format-and-structure.md`、`anti-ai-writing.md` 或 `narrator-voice.md`。
- 任一工具输出出现 `truncated`、省略标记或超过输出上限，都视为未读取；必须改用工具箱有界包入口，禁止凭摘要声明“完整读过”。
- 修 `细纲表演验收回执.json`、`顺序契约回执.json`、`首写容量契约回执.json` 或 `开头承重契约回执.json` 时，只能依据当前项目文件、当前脚本报错、当前脚本 `result_template` 与当前阶段 reference。禁止用 `rg`/`find` 扫工作区里其他书的同名回执、设定、大纲、正文或脚手架文件当字段模板。

## 唯一准备入口

设置：

```bash
SKILL_ROOT="{系统注入的 story-short-write SKILL.md 所在目录}"
TOOLBOX="$SKILL_ROOT/scripts/story_short_write_project_toolbox.py"
```

必须使用本次 Skill 元数据给出的真实 `SKILL.md` 路径推导 `SKILL_ROOT`。禁止先尝试 `$CODEX_HOME/skills/story-short-write`，禁止用 `find`、`rg --files` 或目录枚举搜索另一份 Skill 或工具箱。

全新开书按以下顺序执行，不使用 `--help`、`rg argparse`、递归 `ls/find` 或旧项目回执发现参数：

1. 运行工作区规范入口：

```bash
python3 "$TOOLBOX" workspace-rules --root "{工作区}"
```

2. 只查一次轻量候选索引：

```bash
python3 "$TOOLBOX" candidate-subflows \
  --index "{工作区}/资料库/子流程总索引.jsonl" \
  --query "{题材与桥段关键词}" \
  --exclude-source "{主体书名}" \
  --project-root "{工作区}" \
  --project-name "{新书名}" \
  --primary-source-dir "{工作区}/拆文库/{主体书名}"
```

用户明确要求“其他书籍为辅”“融合多本”或同义要求时，候选命令必须追加：

```bash
  --require-auxiliary --auxiliary-source-count 2
```

此时工具箱必须直接把不同辅助书及其完整 `SF-*` 绑定进 `next_allocate_command`；候选不足会硬失败，禁止降级为仅主体。用户没有要求辅助来源时，候选不足才允许主体独立承担，不自动拆书。

3. 候选可用时只选择完整 `SF-*`，不得抽零件冒充辅助仿写。
4. 直接执行候选输出的 `next_allocate_command` 分配安全新目录，不得手工删除其中的辅助 `--source-dir / --select-subflow`。不得根据目录存在或旧时间戳猜测“正在并发写入”；路径异常只能报告已验证事实。
5. 运行 `allocate-project` 输出的 `next_command` 原子初始化。初始化失败不得留下半套 profile 或回执。

正常起盘不得预读 references。只有工具箱返回无法理解的失败码时，才读取与该失败码直接对应的一份治理文档。

## 写前读取

### 固定规则

初始化后运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" export-rule-review
```

不得直接编辑 `写作规则读取回执.json`。完整字段见 [writing-rule-reading-gate.md](references/governance/writing-rule-reading-gate.md)。

`init-book` 会按当前 Skill 文件 SHA 机械载入三份固定写作规则及维护过的摘要，直接生成 `review_mode=builtin_sha_bound` 的已通过回执。新书禁止再循环执行 `rule-review-next -> apply-rule-review-item` 复述固定规则；这些命令只供旧版 pending 项目迁移或规则摘要过期时诊断。初始化后直接运行 `validate-prewrite-reads`，随后进入 `prepare-setting -> setting-context`。任一规则文件或内置证据词变化时机械阻断，必须先更新 Skill 摘要，不能让写书模型临场重复消化整套固定文档。

### 原文与拆书资产

直接仿写、融合仿写或用户要求原文颗粒度时运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" validate-prewrite-reads
python3 "$TOOLBOX" --project "{项目目录}" prepare-setting
python3 "$TOOLBOX" --project "{项目目录}" setting-context
```

`prepare-setting` 通过后，设定阶段只允许读取 `setting-context` 输出的有界摘要，再运行工具箱给出的 `stage-reference --stage setting`。禁止直接 `cat/wc/awk/sed` 阶段 Markdown，禁止重复运行 `prepare-setting`，禁止 `rg --files` / `find` 枚举项目目录，禁止整包读取 `profiles/{项目名}.project.profile.json` 或 `写作资产/主体原文完整颗粒包.json`；如需字段，必须走 `setting-context`。

设定阶段的 `setting-context` 不展示 `source_excerpt` 或原文预览，只提供来源功能合同。设定必须逐个覆盖主体全部 `SF-*` 与已选辅助 `SF-*`，写入 `## 换链差异矩阵`：每个单元固定填写 `来源表层件 / 保留机制 / 新稿实现 / 更换维度 / 用户锁定复用 / 禁止回流`。`新稿实现` 必须使用 Unicode `→`；`更换维度` 只能逐字使用工具箱给出的允许标签；`禁止回流` 必须逐字重列除用户锁定项之外的每个 `来源表层件`。`direct_imitation` 只迁移因果前提、信息延迟、控制权变化、情绪过程和文风运行方式，不得保留原地点、原物件、原金额、原职业流程或原场景连续动作后只改人名；除用户明确锁定的题面件外，至少更换四类实质维度。矩阵缺项、目标链少于四拍或两个以上来源表层件回流，工具箱必须阻断进入细纲。

设定最多分两次补丁落盘；细纲固定分三批落盘：第 1-4 节、第 5-8 节、第 9 节至末节及全书状态链。禁止先发送“现在写入”后在单次超大补丁前静默生成数分钟。设定落盘后立即运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" stage-reference --stage outline
```

该命令会先机械校验换链差异矩阵；门禁未通过时不返回细纲阶段资料，禁止靠口头解释绕过。

细纲中的小节一级标题必须独占一行且严格写成 `## 第N节`，标题另起一行写 `### 标题：...`；禁止写成 `## 第N节：标题` 或 `## 第N节 标题`。细纲三批全部落盘后立即运行 `prepare-draft-gates`，不得停在大纲文件生成提示上。

设定写完并通过设定内部顺序契约、大纲写完后，正文首写前必须运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" prepare-draft-gates
```

该命令只负责机械初始化四张正文前契约骨架：

- `开头承重契约回执.json`：绑定 `小节大纲.md` 的首段开口，不允许等 `正文.md` 先写出来再补
- `细纲表演验收回执.json`
- `顺序契约回执.json`
- `首写容量契约回执.json`

初始化后，必须由当前模型把四张回执补到 `gate_status=passed`，再继续 `start-draft`。禁止先落 `正文.md` 再回头补闸。

补 `细纲表演验收回执.json` 时，禁止每改一小块就直接全量跑正式校验。工具箱默认把同一错误组中最多 6 个连续小节放进一个有界修闸包；当前模型应一次补完包内全部小节，再用工具箱快速预检当前批次：

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only sections
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only handoff
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only bridges
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only first-draft
```

`outline-precheck` 只读 `小节大纲.md + 细纲表演验收回执.json`，用于快速发现空字段、证据句不命中、交接状态不一致和跨节模板复用。修闸包会从当前细纲的 `场景入口状态 / 场景出口状态` 机械预填节内状态；小节写回时会同步更新相邻交接的 `from_exit_state / to_entry_state`。禁止手工改写这四个可机械派生字段；只需人工处理不可逆动作、人物偏手、因果拍链、知情变化和情绪等强判断。只有当前批次预检通过后，才运行正式全量：

`opening-precheck / sequence-precheck / draft-capacity-precheck` 本身会在失败时生成当前修闸包和回填模板；对应写回命令只能是 `opening-apply / sequence-apply / draft-capacity-apply`。不存在 `opening-repair-next / sequence-repair-next / draft-capacity-repair-next`。细纲才使用 `outline-repair-next / outline-repair-apply`。

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-validate
```

`outline-validate` 会先跑快速预检；预检有错时直接阻断并跳过正式全量校验。只有预检通过，才补跑一次 `validate_outline_performance_contract.py validate` 作为最终放行。

如果 `outline-precheck` 或 `outline-validate` 失败，工具箱会自动刷新当前最优先的修闸包与局部回填模板；失败后禁止继续用 `cat / sed / jq` 逐层探测整张回执、禁止手搓整张大补丁、禁止写项目专用临时脚本。固定动作只有：

1. 只编辑 `写作资产/当前细纲修闸回填.json`
2. 直接重跑 `start-draft`
3. 仍被阻断时，只处理工具箱这次重新打印出来的当前修闸包，不得回头扫旧项目

如需手动重新刷新当前包，再运行固定修闸入口，而不是手搓整张回执或临时写项目脚本：

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-repair-next
```

该命令会把当前最优先的错误分组导出到：

- `写作资产/当前细纲修闸包.json`
- `写作资产/当前细纲修闸回填.json`

当前模型只编辑 `当前细纲修闸回填.json` 这一份局部模板。若模板同时含 2-3 节，必须在同一次回填中全部完成，不得只留第一节或拆回逐节串行。填完后默认直接重跑：

```bash
python3 "$TOOLBOX" --project "{项目目录}" start-draft
```

`start-draft` 会先自动吸收已完成且已更新的 `opening/sequence/draft-capacity/outline` 修闸回填，再继续 preflight、颗粒包和正文放行。只有需要隔离单张修闸回执调试时，才单独运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-repair-apply \
  --packet-sha "{outline-repair-next 输出的 packet_sha256}"
```

工具箱会原子写回正式 `细纲表演验收回执.json`。写回后仍应立刻重跑 `start-draft`，不要停在单张回执成功提示上。禁止在修闸阶段手写项目专用临时脚本、临时 `/tmp/*.json` 依赖或整张回执大补丁。

局部回填是字段级 delta：只能包含当前批次最多 6 个同错误组失败小节、失败字段或失败交接，不得复制整本 `sections` 或全部交接链。`outline_evidence` 必须从修闸包的 `eligible_outline_evidence` 逐字复制，不得同义改写。节内状态链采用精确相等合同：首拍 `from_state == scene_entry_state`，每拍 `to_state == 下一拍 from_state`，末拍 `to_state == scene_exit_state`；知情链同样要求 `initial_state -> transitions` 逐项首尾精确相等，最后一次 `to_state == final_state`。交接包中的两端状态由工具箱自动同步；人工只补 `handoff_trigger`、人物/知情/物件连续、未解线头、证据和语义判断。

修闸过程中如果脚本提示某个字段缺失，只允许回到以下来源补齐：

- 当前项目的 `小节大纲.md`
- 当前项目的四张正文前契约
- 当前脚本校验器报错与 `create_receipt/init` 生成的字段结构
- 当前阶段唯一允许读取的治理文档

禁止为了“看字段长什么样”去打开其他项目的 `细纲表演验收回执.json`、`规则执行台账.json`、`设定.md`、`小节大纲.md` 或 `正文.md`。这类行为视为旧项目污染，不得用于继续本轮写作。

写书阶段不再把 `SF-*` 逐包人工复述当作正式流程。`story-short-analyze finalize` 必须已经产出并校验 `写作资产/仿写无损编译包.json`：完整原文只保留一份，主体全量 `SF-*` 与辅助已选 `SF-*` 的完整 `source_excerpt / source_range / required_sequence / causal_preconditions / information_delay / control_changes / emotion_sequence / source_style_granularity` 均以上游真实内容为准。`validate-prewrite-reads` 会先机械校验或自动升级 `拆文读取回执.json`，`prepare-setting` 再生成并校验项目侧 `写作资产/主体原文完整颗粒包.json`，供设定、细纲和正文链路继续消费。

## 规则台账

通过两份读取门禁后初始化 `规则执行台账.json`。固定 Skill 规则由脚本从下列规则源机械载入和预分类，不要求模型在每本书启动时重新阅读或归并：

- [mandatory-rule-catalog.md](references/governance/mandatory-rule-catalog.md)
- [format-and-structure.md](references/workflow/format-and-structure.md)
- [anti-ai-writing.md](references/anti-ai-writing.md)
- [narrator-voice.md](references/craft/narrator-voice.md)
- [writing-workflow.md](references/workflow/writing-workflow.md)
- [audit-rulebook.json](references/governance/audit-rulebook.json)

模型语义归并只处理本书来源资产，不读取其他项目结论。台账详细命令见 [rule-execution-ledger.md](references/governance/rule-execution-ledger.md)。
如工具箱提示 `skill 规则源已变化，先运行 sync-sources`，必须直接运行 `python3 "$TOOLBOX" --project "{项目目录}" sync-sources`。该命令会同时增量重绑规则台账并重建当前 SHA 对应的 `builtin_sha_bound` 写作规则回执，不要求旧项目重新跑固定规则 AI 复述；通过后立即重跑原被阻断命令。禁止绕过台账哈希校验。

从候选到交付的所有阶段都禁止递归搜索工作区中的旧项目回执、规则输出、台账、设定、大纲或正文作为字段示例。字段结构只能来自当前任务文件的 `result_template`、当前脚本固定输出和本 Skill references。完整写作流程不得委派给子代理；来源全文读取、设定、细纲和逐节正文必须由当前执行模型连续完成。

## 完整首写流程

用户明确要求“跑完整流程”“继续往下写”“不要停”时，`start-draft` 之前一律不得收口、不得输出阶段性总结冒充完成，也不得把“已到细纲前闸/正在补回执”判成可结束状态。只有以下两种情况允许停下：

- 已真正执行到 `start-draft`，并进入 `show-section -> 完整阅读 -> open-section` 的正文首写链。
- 遇到脚本硬错误、文件缺失或校验失败，且当前回合已经给出下一条固定续跑动作；此时只能报告“未完成 + 下一步修哪一张回执/运行哪条命令”，不能写成完成总结。
- 只要还没到 `start-draft`，就禁止输出 `final_answer` 口径，禁止把“仍在修闸/仍在校验失败”包装成收尾消息，禁止触发任何等价于 `task_complete` 的完成判定。
- `outline-validate` 失败后必须继续停留在当前项目、当前回执、当前脚本报错和当前阶段 reference 内修复；除非已经明确给出下一条固定续跑动作，否则不得结束当前回合。

1. 锁定平台、题材壳、主卖点、核心情绪、付费期待和禁止漂移方向。
2. 通过设定写作放行闸后写 `设定.md`。
3. 建立并通过设定内部顺序契约。
4. 通过大纲写作放行闸后写 `小节大纲.md`。
5. 建立跨节事实状态链和相邻小节交接链。
6. 运行 `prepare-draft-gates` 初始化四张正文前契约，且在写正文前补到 `passed`。
7. 每节绑定主体原文切片及全部选中辅助 SF 切片，同时迁移事件、因果、情绪和文风颗粒。
8. 通过完整顺序契约、开头承重契约、细纲表演验收和首写容量契约。
9. 运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" start-draft
```

10. `start-draft` 直接输出并自动打开第一节的紧凑完整包；紧凑包只保留一次完整原文切片、一次完整逐拍合同和一次目标场景/文风合同，禁止重复输出六份同义摘要。只有完整包超过安全上限时才回退 `show-section --part` 分包，读到最后一包后用 `open-section --read-token` 打开。
11. 只写当前节。工具箱生成 schema v2.1 的 `写作资产/当前节逐拍消费回填.json`，并在开节输出和回填顶层直接给出 `minimum_section_chars` 与 `evidence_order_note`。同一次文件编辑中写正文，并为每拍只填写固定顺序的 `evidence=[前态,触发,动作选择,可见结果,下一拍原因]` 与 `performance_equivalence`；五条证据还必须按其在正文中的唯一首次出现位置递增，不得只按语义顺序猜。证据硬门槛虽为 6 个非空白字符，首写默认截取 8—18 个非空白字符，禁止贴着 6 字边界反复返工。工具验证通过后自动判定 `passed`，禁止再让模型手填状态或复述固定字段名。
12. 当前节不合格时当场整场重写，不等待全文完成后统一润色。
13. 直接运行 `advance-section --section N`，不传固定 `judgment` 长串。工具箱机械生成关闭判断，校验逐拍回填、正文格式、原句唯一性、拍序和零容缺状态；通过后关闭当前节，并对安全大小的下一节紧凑包自动开节。正常逐节循环固定为“一次正文+回执编辑，一次 advance”；只有超限分包才增加显式读取与开节。
14. 末节 `advance-section` 关闭后自动固定母稿并初始化首稿基础审计回执；模型一次回填四项基础检查，直接运行 `finalize-basic-review`。该命令通过后自动绑定全流程状态并停靠 `draft_preview`，禁止再手工初始化或补状态文件。
15. 用户明确确认深审后，才进入人工切窗、正式审计、最终台账重绑和写后人工语义复核。

正文入口、逐节回执和停靠规则见 [short-write-execution-core.md](references/governance/short-write-execution-core.md)。

## 首写硬闸

- 原文颗粒度与事件颗粒度同级验收；只读 profile、摘要、桥名或功能概括不算。
- 每节必须使用完整逐节原文颗粒包，禁止以 `模型语义输入.json`、单条 binding 或五拍摘要替代。
- 仿写绑定的每个主体及辅助 `SF-*` 都实行逐拍零容缺：`required_sequence` 有几拍就必须逐拍全部落地，禁止按比例放行、允许漏拍、合并掉承重拍，或用同一个结果句冒充多拍消费。
- 每拍必须保留其前态、触发、动作选择、可见结果和对下一拍的因果作用。状态标签、情绪概括、关键词露面或后文存在一个无关动作，都不能证明该拍已经消费。
- `show-section` 必须展示每个绑定 `SF-*` 的完整 `source_dense_beats`，禁止只截前四拍或以摘要替代末端动作链；默认完整包未读完、超限分包未读到最后一包时均不得 `open-section`。
- 关节必须使用 schema v2.1 的 `当前节逐拍消费回填.json` 留证：每拍的 `evidence` 数组固定按前态、触发、动作选择、可见结果、下一拍原因排列，每项都必须引用当前正文中不少于 6 个非空白字符的真实证据；五组件顺序、跨拍动作顺序、证据唯一性和 `performance_equivalence` 任一不合格都不得 `advance-section`。`passed` 由工具验证后生成，不要求模型手填。
- 知乎/盐言正文从第一节关闭起就必须只含 `1.`、`2.` 连续纯数字节号；`正文.md` 不写书名标题，也不继承大纲小节标题。格式错误必须当节阻断，不得拖到全文结束。
- 知乎/盐言正文对白必须按说话轮次独立成段；单个自然段最多 2 句、100 个非空白字符，单句超过 42 字或连续超过 2 个 22 字中长句时阻断。一个自然段必须独占一个物理行：两句同段要写成 `第一句。第二句。` 后再空一行，禁止写成两个相邻非空行。该硬闸专门拦“句句都不算超长，连起来却没有气口”；不鼓励一句一段，仍须保留长短句交错和连续瞬间。
- 情绪必须包含注意偏移、非自主反应、偏见或自欺、说话失手、动作选择和余痛中的真实过程，不能缩成动作标签。
- 同一连续瞬间优先写成连续气口；禁止动作、证据、反应各自一句一段的电报稿。
- 对白优先试探、回避、错答和找补，不写人人都会总结主题的功能对白。
- 追妻题必须持续兑现男主失位后果、低位补救失败和女主明确边界，不得漂成职业流程文或现实切割说明文。
- 审计不得为了清零命中削弱主体 BID/SF、情绪烈度、信息延迟、物件/空间/身份换主和场末余痛。
- 缺 `拆文读取回执 passed`、细纲表演回执、容量回执、首稿入口回执或逐节执行回执时，不得声称已按完整原文颗粒度完成。

## 阶段资料

- 起盘、设定和仿写细纲资料只能通过工具箱 `stage-reference` 有界入口读取；禁止直接打开对应原始 Markdown，禁止自行 `wc/awk/sed` 分段。
- 起盘与设定：`stage-reference --stage setting`，只返回独立的设定阶段合同。
- 仿写细纲：`stage-reference --stage outline`，单次返回完整且受字节上限约束的仿写资产合同。
- 细纲验收：读取 [outline-performance-contract-gate.md](references/governance/outline-performance-contract-gate.md)。
- 开头验收：读取 [opening-contract-gate.md](references/governance/opening-contract-gate.md)。
- 顺序验收：读取 [sequence-contract-gate.md](references/governance/sequence-contract-gate.md)。
- 写后人工复核：读取 [post-write-human-review-gate.md](references/governance/post-write-human-review-gate.md)。
- 高敏回修确认后才读取 [high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)。
- 原文基线回修读取 [source-baseline-imitation-audit.md](references/governance/source-baseline-imitation-audit.md)。

直接仿写首写前禁止加载通用示例句库。完全原创或写后诊断确认来源缺少对应维度时，才按需读取题材、开头、情绪和对白资料。

## 完成定义

首稿交付与完整深审是两个状态：

- `draft_preview`：逐节首写与基础审计完成，立即交用户确认。
- `completed`：用户放行深审后，顺序、开头、平台格式、窗口前回修、人工窗口、正式审计、规则台账和写后人工语义复核全部通过。

补充约束：

- `prepare-draft-gates`、`outline-precheck`、`outline-validate`、四张正文前契约人工回填，全部属于“未完成中的中间施工态”。
- 只要还没执行 `start-draft`，就不得把当前回合写成“已完成到某一步”，更不得触发完成口径；正确口径只能是“未完成，继续补闸/继续放行”。

任一硬闸缺失只能报告“未完成”，不得用口头说明代替回执。

## 语言

- 跟随用户语言回复。
- 中文排版遵循当前项目规范。
