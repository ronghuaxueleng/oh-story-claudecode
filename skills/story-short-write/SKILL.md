---
name: story-short-write
description: |
  短篇网文写作。辅助短篇小说创作，从起盘、搭骨架到正文和回炉，重点抓冲突、情绪、高潮和值得付费的后果。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」
metadata:
  version: 1.67.60
---

# story-short-write：短篇网文写作

## 连续执行终止硬闸

用户明确要求“自动连续执行 / 不要询问是否继续 / 直到完成正文”时，立即进入 `persistent_execution`。初稿停靠前，阶段完成、文件多、耗时长、单回合容量、进度汇报、可修复脚本错误和等待人工字段都不是合法停止理由。

固定纪律：

- `persistent_execution` 禁止调用 `create_goal / get_goal / update_goal` 或依赖 goal 的暂停、恢复和续跑状态；执行连续性只由本 skill 当前激活流程管理。
- 初稿停靠前禁止用最终回复交付阶段报告、`继续执行中`、`下一轮继续`或要求用户再次回复“继续”。
- 禁止发送空白 `final`，也禁止用一条 commentary-only 进度消息主动让出当前执行权。中间更新后必须立刻继续下一项工具调用或人工处理。
- 不得声称“目标续跑机制 / 下一自动续跑 / 宿主稍后继续”；当前模型必须在本次 skill 激活中持续推进，直至合法终止条件成立。
- 写作门禁失败只停止当前产物生成，必须留在当前批次修复；不得把“当前阶段被阻断”误写成“整个任务结束”。
- 任何终止型回复前必须运行 `validate_continuation_gate.py`。输出不是 `continuation_gate: passed` 时，终止型回复一律禁止。
- 只有三类终止原因可申请校验：用户明确叫停、连续三轮仍不可恢复的真实外部阻断、正文达到本 skill 的初稿强制停靠点。

初稿停靠固定命令：

```bash
python3 "$SKILL_ROOT/scripts/validate_continuation_gate.py" \
  --project-dir "{项目目录}" \
  --reason initial_draft_stop \
  --platform zhihu
```

用户叫停使用 `--reason user_stop --user-stop-confirmed`。真实外部阻断使用 `--reason external_blocker --blocker-receipt "{阻断回执.json}"`。`progress_report / stage_complete / turn_limit / file_volume / tool_wait / empty_final / commentary_only_yield / goal_pause` 属于永久非法终止原因，脚本必须返回 blocked。

人工语义回执规则：写前文字、情绪和人物合同必须由当前模型逐字段完成；正文逐节提交默认不再重复落盘同一批人工语义，而是绑定当前暂存稿、写前合同、场面领取和 SHA 后确定性提交。全部小节通过后，当前模型必须在两份全文 `bind-draft/validate-draft` 中基于最终正文 SHA 一次性完成 `comparison / manual_judgment / target_sentence / target_quotes / ownership_context / keep-revise` 等正式终审。脚本只能初始化、绑定 SHA 和定位候选；跨节复制、只替换编号、统一模板句或自动降级替换一律阻断。若逐节通读时发现未兑现、错脸、摘要化或偏离写前包，禁止直接提交，必须先重写正文，或显式退回差量/全量人工侧车。

你是短篇网文写作执行器。从起盘到成稿，把一篇短篇真正写出来。

长句与断行复核：`paragraph_breath_and_cut_points` 不等于把连续现场压成一行，也不等于机械“一句一个动作”断成施工清单。写后逐节复核必须标出同时承载两个以上独立动作、信息、后果或视线转移节点的句群；存在自然换气点、视角转移或信息层级变化时，拆为连续的两句或两个短段。重点逐句检查以下多拍形状：`物件出现 -> 回忆/旧画面 -> 当下处置`、`证据出现 -> 人物反应 -> 现实后果`、`人物动作 -> 旁观者反应 -> 秩序变化`。单一身体动作链、感官链或话轮链可保留长句，但必须说明连续性理由。不得按字符数硬切，不得把并列证据改成流水账。正文回修后须输出长句候选清单，逐条记录 `quote / section / node_count / split_or_keep / reason`，不能只挑一条例句处理。

主文件只保留四件事：

1. skill 定位
2. 主流程入口
3. 强制闸门
4. 调用哪些 `references/` 和 `scripts/`

细则不再在主文件里重复展开。

---

## 定位与边界

本 skill 负责：

- 起盘
- 换链
- 细纲
- 正文
- 分块回炉

不负责：

- 把拆书工作混进写作主流程
- 把整篇去味流程混成写作默认动作
- 把通用脚本说明手册塞进正文入口

固定边界见：

- [references/governance/skill-boundaries.md](references/governance/skill-boundaries.md)

硬口径：

- `story-short-write`：起盘、换链、写正文、定点回炉
- `story-short-analyze`：拆书、样本分级、高敏桥识别
- `story-deslop`：已成稿去味、局部高风险段第二闸门

### 全新开书隔离硬闸

用户明确要求“全新开书 / 新开一本 / 另开新项目”时，必须将本次写作与工作区内所有旧写作项目完全隔离。

允许读取的范围只有：

- 用户本次明确指定的原始样本文件。
- 这些样本在 `拆文库/`下的对应拆文资产。
- 本 skill 自身的 `SKILL.md`、`references/`、`scripts/`和通用题材规则。
- 本轮新建且尚未被其他书籍使用的目标项目目录。

用户只说“其他书 / 其余样本 / 辅助书”而未逐本点名时，不得自动把工作区所有旧项目或全部文本加入允许范围。只允许先做元数据级发现：列出工作区顶层原始样本文件名及 `拆文库/` 同名目录名，不读取文件内容；再按用户题意和必备资产完整性选出最小辅助集合。只有被明确选中的原始样本及其同名拆文目录才能加入 `allowed_read_roots`，其余候选继续禁读。

禁止读取、搜索内容、摘要、比较、复用或复制任何旧项目中的：

- `设定.md`、`小节大纲.md`、`正文.md`、导语、书名和人设。
- `写作资产/`下的回执、台账、计划、审计、辅助脚本和中间产物。
- `profiles/`下的旧项目 profile。
- 旧项目中任何声称可作“流程模板 / 结构参考 / 相似任务样例”的文件。

不得以“只参考流程”“不复制正文”“提高效率”为理由读取旧项目。需要流程范例时，只能读 skill 正式文档与 skill 内置脚本。

执行前必须先列出本轮 `allowed_read_roots`和 `forbidden_legacy_roots`。后续搜索、文件枚举和命令必须限定在 `allowed_read_roots`内；若误读旧项目，立即停止写作，向用户说明，并从未受污染的新目录重新起盘。

### 项目目录命名硬闸

正式书名锁定后，写作项目目录 basename 必须与小说书名逐字一致。禁止继续使用 `新书-题材-日期`、主体骨架名、平台名、内部任务代号或“暂定名”作为成书目录。

用户要求“全新开书”时，锁名后、创建目录前必须先运行 `--new-project` 占用预检。目标路径只要已存在，无论是目录、文件、空目录、旧项目还是本轮以外生成物，都必须阻断并重新命名。禁止读取该路径内容判断“是否可复用”，也禁止在预检前用 `mkdir -p`、初始化回执或任何写入动作创建目标路径。

创建项目目录后、初始化任何回执前，再运行一次常规目录命名校验。创建 `设定.md` 前也必须保持该校验通过；目录名不一致时，先重命名目录并同步内部回执路径，不能等正文完成后再补。只有目标文件系统明确禁止书名中的字符时，才允许做最小替换，并在项目内记录 `原书名 -> 目录名`，不得顺手缩写或改成营销代号。

全新开书的固定顺序如下；本动作已文档化，禁止先运行 `--help` 探参：

```bash
python3 "$SKILL_ROOT/scripts/validate_project_directory_name.py" \
  --project-dir "{工作区}/{小说书名}" \
  --title "{小说书名}" \
  --new-project

mkdir "{工作区}/{小说书名}"

python3 "$SKILL_ROOT/scripts/validate_project_directory_name.py" \
  --project-dir "{工作区}/{小说书名}" \
  --title "{小说书名}"
```

两次都输出 `project_directory_name: passed` 才能初始化项目内回执或创建 `设定.md`。预检失败后必须退回书名阶段，不得对已占用路径做快照、备份、移动、归档、覆盖或回执初始化。

### 书名锁定前置硬闸

书名必须在主卖点清楚后锁定，不能用“题材 + 具体物件 + 离婚/分手”的公式抢跑，也不能复用本 skill、其他 skill 或历史任务中的示例标题。锁名前必须先写清 `题材承诺 / 主卖点 / 核心情绪 / 付费期待`，再基于当前故事资产生成 `6-10` 个方向明显不同的候选，并逐个检查：

- 真人口语朗读是否自然，有无生硬搭配、歧义或说明腔。
- 三秒内能否感到主要关系矛盾与情绪期待，而不只是知道发生了什么。
- 是否提前泄露完整剧情、结局或追妻结果。
- 是否依赖尚未在设定中锁定的具体物件、职业或桥段。
- 是否真正承诺本题的核心读点；追妻题至少应带出 `误判 / 失去 / 求回 / 追不回` 中的一项期待。
- 是否产生探索心：读者看到标题后，能提出至少一个具体问题（谁在误判、什么被藏住、为什么会走、他要付出什么才能追回），而不是只得到情绪结论。
- 是否具有当前故事独有的关系张力、反常意象或未解释因果；泛化句如“他后悔了”“我不爱了”“这次我走了”不得直接入选。
- 是否与当前 skill 文档、上下文已有标题或候选标题有高相似度；相似候选必须淘汰并补生成。

用户未指定书名时，执行器默认自动锁定评分最高且探索心达标的候选，不等待用户从候选中点名；回复中简短展示入选名、探索问题和淘汰原因。只有用户明确要求共同选名时，才暂停等待确认。禁止先建一个事件说明式目录，再让该标题反向绑架设定。

命名生成必须覆盖至少四种结构中的三种：`关系误判`、`异常因果`、`未完成承诺`、`后果倒计时`。评分采用 100 分制：探索心 30、关系矛盾 20、情绪与付费期待 20、口语自然 15、未泄底 10、题面独有性 5。探索心低于 22、模板重复风险非低或任一硬检查失败，禁止锁名，必须重新生成。候选和最终评分写入项目命名回执；不得把固定示例名作为兜底值。

反例：`他让白月光穿走我妈的婚纱后，我离婚了`。问题是语序生硬、信息堆满、提前锁死婚纱物件，且主要承诺停在“我离婚了”，没有形成追妻期待。

命名反例：任何只表达“后悔、离开、求回”的通用句，即使口语自然，也不能因为安全而直接锁定；必须补入当前故事的异常关系问题或未解释因果。文档中的示例标题只用于说明禁忌，不得复制到新项目。

用户否定书名时，立即退回命名阶段并停止生成设定、大纲或正文。旧书名不再作为题面、物件或剧情约束；重新完成候选对比并锁定新名后，必须移动整个项目目录，同步项目字段、绝对路径、profile 文件名和回执路径，重跑目录命名校验，以及所有因路径或 skill/source SHA 变化而失效的门禁。禁止只改聊天中的称呼或文件夹外壳。

---

## 工具链

本 skill 默认走 `profile` 驱动流程，不接受“只看题材概括 / 只看拆文摘要 / 只靠提示词临场发挥”直接开正文。

### 脚本参数调用纪律

- 使用系统注入的本 `SKILL.md` 绝对路径推导 `SKILL_ROOT`。文档中的 `$SKILL_ROOT` 始终指当前实际加载的 skill 目录，不得假设 skill 直属 `$CODEX_HOME/skills/`；插件嵌套安装、个人安装和仓库开发路径都必须执行同一份已加载 skill。
- 已有完整命令示例时，禁止先运行脚本或子命令的 `--help`，也禁止用 `rg argparse`、读取参数解析源码、目录枚举或其他项目回执反推参数。
- `validate_project_directory_name.py` 的完整接口已在“项目目录命名硬闸”和 `references/workflow/writing-workflow.md` 中给出；必须直接执行固定命令，不得把它归入“当前动作没有文档化命令”的例外。
- 命令失败时先依据实际错误和对应治理文档修正；只有当前动作没有文档化命令，或实际错误明确表明参数接口已经变化时，才允许对该脚本执行一次 `--help`。不得连续执行顶层与多个子命令的 `--help` 探路。
- 若后续版本提供统一 toolbox，固定流程命令以 toolbox 文档为唯一入口，不再逐个探测底层脚本参数。
- 正式回执、合同、台账和审计产物优先使用官方脚本 `init / bind / apply-* / validate-*` 创建或更新骨架；不得把本轮现场拼出的临时 Python here-doc 当成默认流程入口。
- 读取批次默认使用紧凑人工计划链：`export-review-plan -> 当前模型逐项填写 -> preflight-review-plan -> apply-review-plan --consume -> preflight-manifest -> finalize-batches --consume`。紧凑计划不复制源文件全文，只保存 entry 绑定和人工字段；禁止为了批量回填重新编写临时 Python。
- `finalize-batches` 必须事务化：先在内存中合并全部批次并跑两道最终读取门禁，全部通过后才原子写回正式回执和消费侧车。任何证据词、跨来源裁决、SHA 或时序错误都不得留下半消费状态。
- 只有“官方脚本已初始化目标文件，但需要补写当前模型的人工语义字段或少量确定性字段”时，才允许直接编辑正式回执；此时优先使用 `apply_patch` 做小范围修改，而不是临时写 `python3 - <<'PY'` 批量覆写整份 JSON。
- 临时 Python 只允许用于一次性只读诊断、字段统计、候选定位或把“当前模型已经逐字段明确写出”的结果做确定性落盘；不得用它代替官方初始化器创建正式回执，也不得用它批量生成 `manual_judgment / comparison / target_evidence / source_contract_reviews / parity_status` 等人工裁决字段。
- 如果同类正式回执需要大批量、重复性强的结构化回填，应优先补 skill 自带脚本或侧车入口，再调用官方脚本合并；不要在执行过程中反复临时造 here-doc Python 充当半正式工具链。
- 大型人工侧车只作为临时编辑载体，正式合同或回执才是唯一真源。官方 `apply-*` 支持 `--consume` 时，标准流程必须启用：成功合并后将侧车原子压缩为只含原输入 SHA、正式回执 SHA、操作名和计数的小型消费回执；失败时不得压缩。需要继续修改时从正式真源重新导出，禁止把已消费侧车改回可编辑状态。
- 逐节落笔包链默认按 `2` 节为一批推进，不要一节一节零碎 `apply-section-plan`。优先使用官方入口 `export-next-section-plan-pair` 从正式真源直接导出下一对待补小节侧车，再连续补完 `N/N+1` 两节；除非某节证据特别复杂、同批容易串味，才退回单节批次。
- 禁止把“两名子代理分别写一节”作为逐节落笔包的默认提速手段。该环节瓶颈来自单节人工字段本身，多代理会重复读取 skill 与资产，实测不会缩短单节耗时；默认只由当前主线程连续完成当前两节，避免额外上下文装载、调度等待和语义口径漂移。
- 人工写入默认使用侧车内的紧凑来源引用：连续句链填 `source_passage_ref=UF-*`，正例填 `positive_source_ref=UF-*`，关系句填 `source_relation_ref=REL-*`，对白填 `source_dialogue_ref=DLG-*`，机制句填 `source_mechanism_ref=MECH-*`。正式脚本只按引用原样展开 `source_excerpt / source_sentence_chain / source_dialogue_turns / source_sentence / feature_ids`；不得展开、生成或复用任何人工语义字段。
- 引用式写入后，`chain_motion / target_scene_use / relation_type / target_rehearsal / negative_example / mechanism / character_plan / manual_judgment` 等全部语义裁决仍须由当前模型逐项填写。提速来自不再重复抄主体原文和机械数组，不得删维度、缩成模板句或降低预检门槛。
- 逐节落笔包在首次 `apply-section-plan --consume` 前，必须先跑官方 `preflight-section-plan`。该入口负责把“批内四项自检 + 四条高返工预检”一次做完，不允许再靠临时 Python、jq 或 here-doc 先扫结构错：`source_excerpt` 必须逐字存在于主体原文且满足长度门槛；`target_character` 不得用单字占位；`target_marking_mode=implicit` 的正例不得混入显式关系词；`source_function_word_skeleton / turn_motion / rewrite_instruction` 等硬字段长度必须达标；`continuous_source_chain_packets[*].source_sentence_chain` 必须逐条等于验证器 `sentence_units(source_excerpt)` 的输出；`relation_micro_examples[*].source_relation_type / target_relation_type` 只能填写验证器允许的枚举值；`sentence_mechanisms[*].source_sentence` 只能取自本节 `source_passage_ids` 已绑定原文段里的逐句标注句；若 `character_plan.participants[*].character_name` 新增了当前正式 `target_character_profiles` 里不存在的人物，必须先补正式母版。
- 逐节落笔包默认固定顺序改成官方链：`export-next-section-plan-pair -> 当前主线程用 UF/REL/DLG/MECH 引用连续补完两节 -> preflight-section-plan -> apply-section-plan --consume -> validate-prewrite`。除真实脚本故障外，不再拆给多个子代理，不再手工重建整份逐节侧车骨架，也不再把临时只读脚本当作常规预检入口。
- `bind-outline` 必须按数字小节正文逐节比较摘要，不得因全文细纲 SHA 变化就清空全部 `section_generation_plans`。逐字未变化的小节保留原人工包和通过态；真实变化的小节重置为 `pending`，并只把旧包保存在 `prior_plan_candidate` 供当前模型局部修订，禁止自动沿用其通过态；新增节新建，删除节移除。固定顺序是 `bind-outline 局部差异识别 -> 保留未变节 -> 只导出变化节 -> 人工局部复核 -> preflight-section-plan -> apply-section-plan --consume`。
- `export-next-section-plan-pair` 默认还要一并导出 deterministic `editor_hints`：当前节细纲摘录、已分配细节卡、已分配 SF、完整原文连续句链及其 `sentence_units`、原文对白轮次、关系句候选及检测 markers、机制句候选与真实 feature IDs、人物母版摘要和活性资产摘要。两节共用的原文句链、对白、关系和机制候选只在顶层共享目录保存一次，各节只保留推荐 ID，禁止为了查料方便复制两份大块原文。它们只承担查料与定位，不得替当前模型填写 `manual_judgment / comparison / keep-revise / 人物归属 / 关系语义`。进入该链后，查料类临时脚本不再作为常规步骤。
- `export-next-section-plan-pair` 默认追加 `--compact-authoring`，使用短键和定长元组承载全部人工字段，并把重复的原文候选、细节卡、人物母版和活性资产外置为 SHA 绑定的只读取材目录。可机械检测的来源/目标关系词及显隐模式由正式脚本从引用候选和目标试演确定性回填；关系类型、迁移说明、错例、人物归属和裁决仍须人工填写。元组顺序必须以侧车内 `compact_authoring_schema` 为准，预检与应用时确定性展开为完整正式 schema；不得删维度、降低字段长度门槛、自动选择来源或生成任何迁移语义。若紧凑格式运行失败，先修官方脚本，禁止退回临时脚本或重新手抄完整大 JSON。
- `preflight-section-plan` 报错必须直接附带可机械确定的修复数据：切句错误返回 `expected_sentence_units`，对白错误返回 `expected_dialogue_turns`，关系词错误返回 `detected_source_markers / detected_target_markers`，人物占位错误返回可用正式人物母版名，机制句错绑返回当前允许的原文句。执行器不得再为这些数据读取验证器源码、运行 `rg/sed` 反查内部规则，或创建临时 Python、here-doc、jq 诊断脚本。
- 情绪逐节人工计划默认固定顺序也改成官方链：`export-plan-template -> 人工补当前待写节的计划字段与裁决说明 -> assemble-section-plan --consume -> validate-prewrite`。除真实脚本故障外，不再手工重建整份情绪计划骨架，也不再用临时脚本反查 `E/P` 归属、峰值、反刀或桥外首尾拍。
- 情绪逐节人工计划默认优先导出“窄切片计划”，不要直接打开整份大计划：优先用 `export-plan-template --next-pending` 只导出下一条待补节；明确要回补指定节时再用 `export-plan-template --section-id N`。只有需要全量巡检时，才导出整份计划。
- 第一节拼入 opening E 拍、最后一节拼入 epilogue E 拍后，`export-plan-template` 必须按拼入后的完整节内数组修正反刀/峰值序号；不得继续输出细纲内部未加 opening 偏移的局部序号，否则 `assemble-section-plan` 必须阻断。`editor_hints.turning_points` 与人工计划顶层序号必须一致。
- 同一主体桥跨越多个目标数字节时，细纲合同可在桥内各节保留同一份桥级 E 拍允许集合，但 `export-plan-template / assemble-section-plan` 必须再按 `逐拍语义映射.target_outline_region` 唯一分流到具体数字节；禁止把桥级 E 拍全集复制给桥内每一节。
- 桥级反刀/峰值在跨节分流后必须按实际拥有该 E 拍的小节重新计算局部序号；不拥有该拍的小节记 `0`，拥有该拍的小节按本节 E 数组重新从 `1` 编号。第一节若另拼 opening 拍，再在局部序号上增加 opening 偏移。
- 若当前条 `assemble-section-plan --consume` 后还要立刻接着补下一条情绪计划，优先在本次命令上追加 `--refresh-next-output {下一条计划路径}`，让脚本自动基于最新正式回执导出下一条待补节；不要再手工重跑一次 `export-plan-template --next-pending`。
- 情绪人工计划里的 `status` 只是导出骨架字段，不要求当前模型人工修改。`assemble-section-plan` 仅在当前节全部必填人工字段、E/P 显式 ID、反刀/峰值和上游绑定均通过后，确定性把正式合同当前节写成 `passed`；禁止把模板初始 `pending` 原样带回正式合同，导致 `--refresh-next-output` 重复导出同一节。
- `export-plan-template` 默认还要一并导出 deterministic `editor_hints`：字段填写顺序、当前节 `emotion_beats / plot_beats` 短预览、反刀/峰值来源编号和细纲摘录统计。它们只承担查料与定位，不得替当前模型填写 `manual_judgment / turning_point_selection_review / 各类计划字段 / 语义裁决`。进入该链后，情绪查料类临时脚本不再作为常规步骤。
- 情绪逐节人工计划与正式 `全文情绪颗粒度契约回执.json` 同样执行严格串行：先确认 `assemble-section-plan` 或 `apply-section-plan` 已退出且正式回执 SHA 已更新，再单独启动 `validate-prewrite`。禁止把同一路径上的 `export / assemble|apply / validate` 放进同一次并行工具调用，也禁止后台同时跑。
- 新增目标人物母版时，不要为了过当前一节临时塞一个瘦壳：`target_character_profiles[*].source_asset_ids` 默认至少 `5` 条，且至少覆盖 `4` 类原文性格颗粒；不达标时先补母版，再写依赖该人物的节级 `character_plan / dialogue_voice_packets`，避免先消费两节、再被人物母版门槛卡回去重补。
- 逐节落笔包人工提速默认走“单次取材、单次落包”顺序，不要在 `continuous_source_chain / contrastive / relation / dialogue / mechanism / paragraph / liveliness / character` 之间来回切换找料。推荐固定顺序：先一次性锁定本批两节各 `2` 组连续句链和 `2` 组对白源摘录；再立刻从这同一批源摘录顺手展开 `contrastive_examples / relation_micro_examples / sentence_mechanisms`；最后一次补完 `paragraph_plan / window_plan / liveliness_plan / character_plan`。同一节若已经锁定可用源摘录，就禁止回头重新大段搜原文。
- 人工阶段若发现“本节需要新增目标人物母版”“本节机制句不在已绑定 `source_passage_ids`”或“当前源摘录会触发 `sentence_units` 特殊切句”，必须先处理这三个前置点，再继续写该节剩余字段；不要把一整节先补满，再被这类前置门槛整批打回。默认目标是把返工压到“正式真源 1-4 个局部字段小修”，而不是重做整节人工包。
- `apply-section-plan --consume` 成功后，如果正式 `validate-prewrite` 只剩“刚消费这一个批次里的局部字段真错”，默认直接在正式 `全文文字颗粒度契约回执.json` 小范围回写并立刻复校；不要为了 1-4 个局部字段重建整份逐节大侧车，更不要把消费回执改回可编辑侧车。只有需要新增整节、重做整批结构或正式真源已无法定位修改范围时，才从真源重建新侧车。
- `文字颗粒逐节落笔包链` 上的 `apply-section-plan --consume` 与后续 `validate-prewrite` 必须严格串行：先确认 `apply` 已退出且正式回执 SHA 已更新，再单独启动 `validate`。禁止把这两条命令放进同一次并行工具调用，也禁止后台同时跑；否则按读取旧回执状态的流程错误处理。
- 桥级 `source_emotion_sequence` 属于来源真源消费，不适合在大 JSON 里手工模糊补丁。需要把桥外 `bid_ids=[]` 与各 `BID-*` 的原文情绪序列从主体总账同步回正式回执时，优先使用官方同步入口；禁止靠大段 `apply_patch` 在多个同名字段之间手工搬运。
- 细纲改动后，桥内字段通过不等于整份 `细纲表演验收回执.json` 已重新绑定。优先使用官方入口先重绑 `outline.sha256` 并重置顶层验收态，再继续人工补桥级/节级字段；禁止留着旧 SHA 继续补写，或只在聊天里声明“已经重新验收”。
- 细纲改动后，凡是之前已经 `export-beat-template / export-template` 过的桥级或节级侧车，一律先核对顶层 `receipt_sha256` 是否仍等于当前正式回执 SHA。若 `rebind-outline` 或其他官方入口已经改写正式回执，必须先重新导出侧车，或用官方 `apply-* --refresh-sidecar` 链路自动刷新后续窄侧车绑定；禁止拿失效旧侧车直接试跑合并。
- 同一正式回执或同一侧车路径上的 `export-template / apply-template / export-beat-template / apply-beat-template / validate` 禁止并行执行。固定顺序只能是：先单独 `export-*`，确认文件已落盘且 `receipt_sha256` 已刷新；再单独 `apply-*`；最后再单独 `validate-*` 或状态查询。任何共享同一 `receipt.json` 或同一 `sidecar.json` 的命令都不得放进并行工具调用，也不得在后台同时启动多个会改写同一路径的进程。
- 人工补桥级逐拍或节级回填时，默认优先导出“窄切片侧车”，不要直接打开全量大侧车硬补。桥级用 `manage_outline_bridge_review.py export-beat-template --bridge-id BID-XX` 或 `export-template --bridge-id BID-XX` 只导出单桥；节级用 `manage_outline_section_review.py export-template --section-id N` 只导出单节。完成后再串行 `apply-*` 回正式回执，必要时重新导出下一条。只有需要全量巡检或批量只读统计时，才打开整份大侧车。
- 为了减少人工定位，默认优先使用 `batch_outline_review_cycle.py export-next-compact --kind bridge-beat|section --output ...` 自动导出“下一条待补窄侧车”；只有明确要回查指定桥/指定节时，才手动传 `--bridge-id / --section-id`。
- 若脚本已提供成对入口，活跃侧车阶段默认优先使用 `batch_outline_review_cycle.py prepare-next-fill-pair` 一次导出“当前桥级逐拍 + 当前节级”两份窄侧车；只有需要单独补桥或单独补节时，才退回 `export-next-compact` 或底层 `--bridge-id / --section-id`。
- 窄切片侧车和正式大侧车同样受串行纪律约束：同一时刻只允许一条 `export -> apply -> validate/status` 链，不因文件变小而放宽并行限制；但默认应优先选择小侧车，以减少人工定位、误改相邻桥节和大文件补丁冲突。
- 窄切片 `apply-*` 成功后，正式回执 SHA 会立刻变化。此后凡是还要查看项目级大侧车、继续人工回填下一桥/下一节，或执行 `batch_outline_review_cycle.py status / next-step`，必须先从当前正式回执重导出对应大侧车；否则只能把正式回执当真源，旧大侧车只可视为过期快照。高层状态判断若脚本已支持“receipt 优先 + stale 标记”，仍应把 `stale=true` 视为需要先重导出的阻断信号，而不是继续信任旧侧车内容。
- 若当前条 `apply-*` 后还要立刻接着补下一条窄侧车，优先在本次 `apply-*` 上追加 `--refresh-sidecar {下一条侧车路径}`，让脚本自动刷新顶层 `receipt_sha256`，不要再手工 `apply_patch` 只改 SHA 行。
- 进入“细纲表演验收人工回填”后，默认工作模式必须切成 `单链快速回填`：`export-next-compact -> 人工补当前窄侧车 -> apply-* --refresh-sidecar 下一条 -> 继续补下一条`。除非命令真实报错、正式回执校验失败，或用户明确要求汇报状态，否则禁止在两次 `apply-*` 之间反复执行 `status / next-step / rg 缺口 / sed 大段预览 / here-doc 统计` 这类只读诊断动作；它们会被视为无效耗时，而不是“谨慎执行”。
- 在活跃侧车回填阶段，`SHA 核对 / 下一条定位 / 缺口统计 / receipt 绑定刷新` 一律优先交给官方脚本入口处理；不得再为这些机械目的临时写新的 `python3 - <<'PY'`、`jq` 拼装或一次性诊断片段。临时只读脚本只保留给“官方入口无法回答且已出现真实阻断”的场景，不得作为常规推进手段。
- 若脚本已提供 `apply-fill-pair`，活跃侧车阶段默认只允许两类官方命令：`prepare-next-fill-pair` 和 `apply-fill-pair`。禁止再把它拆回 `export-next-compact -> 手动 refresh SHA -> 单独 apply bridge -> 单独 apply section -> 再单独导出下一条` 的旧链；那条链只留给脚本故障时排障，不作默认流程。
- 桥级逐拍回填在 `apply-beat-template` 前，必须先做人肉相邻拍去重预检：逐桥检查相邻 `target_emotion_sequence[*].evidence`、相邻 `target_plot_beats[*].evidence` 是否复用同一句细纲证据；一旦复用，默认先判“细纲承载不足”或“拍间切分不足”，先扩细拍或改证据归属，不要等正式校验再返工。
- 桥级逐拍回填若要把施事者从“她 / 他 / 对方 / 那人”等代词明确到实名，必须先核对该实名是否真实出现在绑定细纲原句里。若绑定原句只有代词，没有实名或唯一身份标记，默认退回改 `小节大纲.md` 的对应 `细拍拆分`，先把细纲证据写实，再回填 `actor / actor_evidence`；禁止只在正式回执里把代词硬改成实名。
- 桥级逐拍回填必须争取一次过，不允许默认“先填再让校验器帮忙找错”。写每个目标拍时，固定顺序只能是：先锁定唯一 `evidence`，再从该句逐字截 `actor_evidence`，再确认 `actor` 与该截句一一对应，最后才填写 `action / control_change / consequence / hurt_object` 等解释字段。若 `actor_evidence` 需要靠上下文猜、需要事后补实名、或一拍要和前后拍共用同一句证据，立即停下回细纲，不准把半成品先落进正式回执。
- 同一桥成批出现多个 `actor_evidence` 错误，默认判为回填方法错误，不得逐条打补丁后继续。重点排查是否把 `actor/action` 与 `actor_evidence` 分轮填写、把受事者代词误当施事者证据、跨拍批量替换同名字段，或只改 `actor/action` 没同步复核整拍。P 拍必须逐拍原子完成并当场闭合 `actor -> actor_evidence -> object_or_receiver -> evidence` 四元组；禁止跨拍批量生成、批量替换或统一修复 `actor_evidence`。
- `逐拍语义映射` 链进入活跃回填后，默认最多只允许一轮 `export-template -> sync-from-outline-contract -> validate` 空跑定位。若同一批错误在未改正式真源、未改细纲、未补人工字段的前提下再次出现，直接按“当前细纲承载不足”或“当前拍仍未人工闭合”阻断，必须立即停脚本并转入“人工闭合缺口”或“回细纲扩细拍”路径；禁止把 `validate` 当探测器连续空转。
- `sync-from-outline-contract` 若已把某个 P 拍证据从局部 fragment 回收到所在完整 bullet，并重算了 `target_outline_region`，后续仍出现 `evidence 重复 / actor_evidence 不稳 / 施事者不贴证`，默认判为该细纲句对当前多拍承载不足，而不是继续反复同步。同一条 bullet 需要同时承接多拍时，必须先把细纲拆成可独占的细拍句，再回正式真源。
- 因 `逐拍语义映射` 校验失败而回修 `小节大纲.md` 时，后续固定顺序必须是：`改小节大纲.md -> 重绑细纲表演验收正式回执 -> 重导或重同步 逐拍语义映射.json -> 单独 validate_semantic_beat_mapping.py validate`。禁止只改细纲原文或只补聊天说明，就继续沿用旧的细纲回执、旧侧车或旧映射通过态。
- `reviewed_by_current_model / gate_status` 不允许作为手工收口遗留项长期挂在正式回执顶层。桥级、节级和下游合同字段全部补齐后，优先使用官方封口入口做真实校验并落盘通过态；禁止靠口头保证或零散补丁把顶层状态改成 `passed`。

内置脚本位于 `story-short-write/scripts/`：

- `validate_continuation_gate.py`
- `validate_writing_rule_gate.py`
- `batch_read_gates.py`
- `batch_outline_release.py`
- `batch_prewrite_release.py`
- `batch_prewrite_blockers.py`
- `validate_project_directory_name.py`
- `validate_source_read_gate.py`
- `validate_rule_execution_ledger.py`
- `validate_write_release_gate.py`
- `validate_sequence_contract.py`
- `validate_outline_performance_contract.py`
- `manage_outline_bridge_review.py`
- `manage_outline_section_review.py`
- `manage_outline_subflow_review.py`
- `validate_prose_granularity_contract.py`
- `validate_emotional_granularity_contract.py`
- `validate_semantic_beat_mapping.py`
- `init_project_writing_assets.py`
- `apply_project_profile_policy.py`
- `batch_draft_prewrite.py`
- `create_section_plan.py`
- `prepare_section_context.py`
- `init_section_review.py`
- `manage_section_review.py`
- `batch_section_review_cycle.py`
- `batch_full_draft_review.py`
- `batch_postdraft_release.py`
- `normalize_section_review.py`
- `validate_section_progress.py`
- `validate_post_write_human_review_gate.py`
- `validate_zhihu_section_format.py`
- `count_words.py`
- `batch_formal_audit.py`
- `generate_story_profile.py`
- `run_full_ai_audit.py`
- `audit_novel_ai_flavor.py`
- `auto_revise_ai_flavor.py`
- `run_revision_cycle.py`
- `precheck_rewrite_gate.py`
- `validate_gate_receipts.py`
- `validate_short_write_completion.py`
- `compare_with_external_block_audit.py`
- `compare_source_baseline_audit.py`

工具链地图和规则接入说明见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/governance/source-baseline-imitation-audit.md](references/governance/source-baseline-imitation-audit.md)
- [references/governance/prose-granularity-contract.md](references/governance/prose-granularity-contract.md)
- [references/governance/ultra-fine-prose-granularity.md](references/governance/ultra-fine-prose-granularity.md)
- [references/governance/prose-liveliness-layer.md](references/governance/prose-liveliness-layer.md)
- [references/governance/character-personality-granularity.md](references/governance/character-personality-granularity.md)
- [references/governance/source-dominant-first-draft.md](references/governance/source-dominant-first-draft.md)
- [references/governance/write-during-section-compliance.md](references/governance/write-during-section-compliance.md)
- [references/governance/section-progress-gate.md](references/governance/section-progress-gate.md)
- [references/governance/emotional-granularity-contract.md](references/governance/emotional-granularity-contract.md)
- [references/integration/internal-toolchain-map.md](references/integration/internal-toolchain-map.md)
- [references/integration/myconfig-rule-integration.md](references/integration/myconfig-rule-integration.md)
- [references/integration/rule-onboarding-checklist.md](references/integration/rule-onboarding-checklist.md)

高风险回修必须额外挂载：

- [../story/references/short-high-risk/reference-index.md](../story/references/short-high-risk/reference-index.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [references/governance/global-humanity-audit.md](references/governance/global-humanity-audit.md)
- [../story/references/high-risk-gates/reference-index.md](../story/references/high-risk-gates/reference-index.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

---

## 执行规则

完整编号规则统一见 [全量执行规则](references/governance/execution-rules.md)。进入正式项目后必须完整读取该文件；主入口只保留不可绕过的顺序：

1. 全新开书先隔离、锁名、预检未占用目录。
2. 先通过规则读取、拆文读取和规则模型分类，再申请当前阶段写作放行。
3. 设定、大纲、正文严格按顺序契约推进，未放行不得创建目标产物。
4. 主体原文独占声线、全部 E/P/SF 和八类细节卡；辅助来源只消费显式选中的 P 拍机制。
5. 细纲先完成桥级、逐拍、逐场与节级表演验收，再建立文字/情绪写前合同。
6. 正文只经逐节状态机提交；全部小节 `final_ready` 后统一完成两份全文人工终审。
7. 初稿停靠前禁止去味、轻重审计和系统回炉；停靠后等待用户明确授权。
8. 脚本只初始化、绑定、定位和确定性合并，人工语义必须由当前模型逐项填写。

## 高敏任务路由

当前任务如果属于以下任一类，必须走高敏流程：

- `同桥仿写`
- `原情节实验`
- `对标重写`
- `外部分块审计长期卡高`
- `改很多轮后越来越像施工稿`

强制流程：

1. 先判任务类型，不把高敏仿写当普通自由创作。
2. 如果已有多版稿，先选母稿，不从最新安全稿继续补丁。
3. 改前写母稿保护卡。
4. 写活稿时只挂最少限制，不让规则接管正文生成。
5. 写后先做命名式滑窗审计，再判唯一主炸点。
6. 一轮只拆一个活结，不顺手整段回炉。

这部分完整规则和自检项，统一见：

- [../story/references/short-high-risk/reference-index.md](../story/references/short-high-risk/reference-index.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

---

## Profile 与门禁闭环

完整流程、命令、回执字段和失败修复路径统一见 [Profile 与门禁闭环](references/workflow/profile-and-gates.md)。执行时按四批推进：

- 读取批次：规则读取、来源读取、跨来源裁决。
- 纲前放行：规则台账、设定、顺序、开头和细纲表演验收。
- 正文前合同：逐拍映射、文字资产、细节卡、逐节落笔包和情绪计划。
- 正文状态机：逐节暂存、预检、提交、全文双合同终审和初稿停靠。

任一独立门禁未输出 `passed`，停在当前批次修复，不得创建下游产物。

## 写作方法

格式、三大硬闸、起盘、细纲、正文生成和停靠后回炉方法统一见 [写作方法与回炉边界](references/workflow/writing-method.md)。高频直接入口：

- 平台与排版：[格式规范](references/workflow/format-and-structure.md)
- 主体声线首稿：[主体原文主导首稿](references/governance/source-dominant-first-draft.md)
- 文字合同：[文字颗粒度合同](references/governance/prose-granularity-contract.md)
- 情绪合同：[情绪颗粒度合同](references/governance/emotional-granularity-contract.md)
- 逐节状态机：[逐节正文进度](references/governance/section-progress-gate.md)
- 高敏回修：[高敏回修流程](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)

正文初稿完成后只允许双合同验证、字数和平台格式校验，随后立即停靠。

## 流程衔接

| 时机 | 跳转到 | 命令 |
|---|---|---|
| 有参考小说要拆 | `story-short-analyze` | `/story-short-analyze` |
| 成稿去味 | `story-deslop` | `/story-deslop` |
| 需要市场方向 | `story-short-scan` | `/story-short-scan` |
| 设定明显更适合长篇 | `story-long-write` | `/story-long-write` |

---

## 参考资料

主流程常用：

- [references/workflow/reference-index.md](references/workflow/reference-index.md)
- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/workflow/format-and-structure.md](references/workflow/format-and-structure.md)
- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/governance/rule-execution-ledger.md](references/governance/rule-execution-ledger.md)
- [references/governance/skill-boundaries.md](references/governance/skill-boundaries.md)
- [../story/references/reference-layer-map.md](../story/references/reference-layer-map.md)

起盘与结构：

- [references/craft/material-packs-setting-plot.md](references/craft/material-packs-setting-plot.md)
- [references/craft/short-story-material-bank.md](references/craft/short-story-material-bank.md)
- [references/craft/opening-and-hook-library.md](references/craft/opening-and-hook-library.md)
- [references/craft/writing-craft.md](references/craft/writing-craft.md)
- [references/craft/reversal-toolkit.md](references/craft/reversal-toolkit.md)

情绪与人物：

- [references/craft/emotion-and-outcome-library.md](references/craft/emotion-and-outcome-library.md)
- [references/craft/character-voice-library.md](references/craft/character-voice-library.md)
- [references/craft/material-packs-character.md](references/craft/material-packs-character.md)
- [references/craft/humanize-and-dialogue.md](references/craft/humanize-and-dialogue.md)
- [references/craft/dialogue-blade-library.md](references/craft/dialogue-blade-library.md)

仿写与高敏回修：

- [references/craft/direct-imitation-assets.md](references/craft/direct-imitation-assets.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [references/governance/no-external-block-audit-self-check.md](references/governance/no-external-block-audit-self-check.md)
- [../story/references/high-risk-gates/reference-index.md](../story/references/high-risk-gates/reference-index.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

脚本与规则：

- [references/integration/internal-toolchain-map.md](references/integration/internal-toolchain-map.md)
- [references/integration/myconfig-rule-integration.md](references/integration/myconfig-rule-integration.md)
- [references/integration/story-profile-schema.md](references/integration/story-profile-schema.md)
- [references/governance/audit-rulebook-coverage.md](references/governance/audit-rulebook-coverage.md)

---

## 语言

- 跟随用户语言回复
- 中文回复遵循《中文文案排版指北》
