---
name: story-short-write
description: |
  短篇网文写作。辅助短篇小说创作，从全新起盘、来源筛选、设定、细纲到逐节正文首写、基础审计和定点回炉。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」「继续写」「重写第X节」
---

# story-short-write

执行短篇网文完整写作流程。优先保证原文事件、因果、情绪、表演和文风颗粒真正进入首写，不用事后润色补救写前缺失。

当前流程版本：`1.11.0`。

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

禁止直接打开总文件 `写作资产/规则语义输入.json`。改为循环运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" rule-review-next
```

该命令每次只展示一个有界规则文件包，并已把同一 `result_template` 原子预写到 `写作资产/当前规则语义回执.json`。完整读取当前唯一规则文件后，禁止再 `cat/jq/sed` 探测回执；只定点编辑包内明确允许的三个 `review` 字段，再运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" apply-rule-review-item \
  --packet-sha "{rule-review-next 输出的 packet_sha256}"
```

工具箱逐条校验 SHA、顺序、证据词和非空结论，并原子追加到 `规则语义进度.json`。重复 `rule-review-next -> apply-rule-review-item`，直到显示全部完成后，必须立刻连续运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" apply-rule-review
python3 "$TOOLBOX" --project "{项目目录}" validate-prewrite-reads
```

禁止把 `apply-rule-review` 当作阶段终点；只要它通过，当前流程就必须继续推进到 `validate-prewrite-reads`，随后进入 `prepare-setting -> setting-context`。

### 原文与拆书资产

直接仿写、融合仿写或用户要求原文颗粒度时运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" validate-prewrite-reads
python3 "$TOOLBOX" --project "{项目目录}" prepare-setting
python3 "$TOOLBOX" --project "{项目目录}" setting-context
```

`prepare-setting` 通过后，设定阶段只允许读取 `setting-context` 输出的有界摘要，再运行工具箱给出的 `stage-reference --stage setting`。禁止直接 `cat/wc/awk/sed` 阶段 Markdown，禁止重复运行 `prepare-setting`，禁止 `rg --files` / `find` 枚举项目目录，禁止整包读取 `profiles/{项目名}.project.profile.json` 或 `写作资产/主体原文完整颗粒包.json`；如需字段，必须走 `setting-context`。

设定最多分两次补丁落盘；细纲固定分三批落盘：第 1-4 节、第 5-8 节、第 9 节至末节及全书状态链。禁止先发送“现在写入”后在单次超大补丁前静默生成数分钟。设定落盘后立即运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" stage-reference --stage outline
```

细纲三批全部落盘后立即运行 `prepare-draft-gates`，不得停在大纲文件生成提示上。

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

补 `细纲表演验收回执.json` 时，禁止每改一小块就直接全量跑正式校验。先用工具箱快速预检当前修改块：

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only sections
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only handoff
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only bridges
python3 "$TOOLBOX" --project "{项目目录}" outline-precheck --only first-draft
```

`outline-precheck` 只读 `小节大纲.md + 细纲表演验收回执.json`，用于快速发现空字段、证据句不命中、交接状态不一致和跨节模板复用。只有局部预检通过后，才运行正式全量：

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

当前模型只编辑 `当前细纲修闸回填.json` 这一份局部模板。填完后默认直接重跑：

```bash
python3 "$TOOLBOX" --project "{项目目录}" start-draft
```

`start-draft` 会先自动吸收已完成且已更新的 `opening/sequence/draft-capacity/outline` 修闸回填，再继续 preflight、颗粒包和正文放行。只有需要隔离单张修闸回执调试时，才单独运行：

```bash
python3 "$TOOLBOX" --project "{项目目录}" outline-repair-apply \
  --packet-sha "{outline-repair-next 输出的 packet_sha256}"
```

工具箱会原子写回正式 `细纲表演验收回执.json`。写回后仍应立刻重跑 `start-draft`，不要停在单张回执成功提示上。禁止在修闸阶段手写项目专用临时脚本、临时 `/tmp/*.json` 依赖或整张回执大补丁。

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

10. 第一节执行 `show-section -> 完整阅读 -> open-section`。
11. 只写当前节。写完立即对照原文检查事件流程、情绪过程、文风颗粒、句间关系和段落气口。
12. 当前节不合格时当场整场重写，不等待全文完成后统一润色。
13. 运行 `advance-section` 关闭当前节并展示下一节完整包；读完后再显式 `open-section`。
14. 全文完成后只做首稿基础审计和一次必要回修，随后交付 `draft_preview` 并停靠。
15. 用户明确确认深审后，才进入人工切窗、正式审计、最终台账重绑和写后人工语义复核。

正文入口、逐节回执和停靠规则见 [short-write-execution-core.md](references/governance/short-write-execution-core.md)。

## 首写硬闸

- 原文颗粒度与事件颗粒度同级验收；只读 profile、摘要、桥名或功能概括不算。
- 每节必须使用完整逐节原文颗粒包，禁止以 `模型语义输入.json`、单条 binding 或五拍摘要替代。
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
