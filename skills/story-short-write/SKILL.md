---
name: story-short-write
description: |
  短篇网文写作。辅助短篇小说创作，从起盘、搭骨架到正文和回炉，重点抓冲突、情绪、高潮和值得付费的后果。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」
metadata:
  version: 1.78.0
---

# story-short-write：短篇网文写作

本 skill 只运行下文列出的正式流程、正式产物和正式脚本。未列出的过程、回执、侧车或脚本一律不得读取、创建、恢复或作为门禁条件。

## 连续执行终止硬闸

用户明确要求自动连续执行时，进入 `persistent_execution`。初稿停靠前，阶段完成、文件多、耗时长、脚本可修复错误、进度汇报和单回合容量都不是合法停止理由。

- 禁止调用 goal 机制暂停或续跑。
- 禁止以 final 交付阶段报告、要求用户回复“继续”或发送空白 final。
- 中间更新后必须立即继续工具调用或写作。
- 当前门禁失败只停止下游生成；必须留在当前阶段修复。
- 任何终止型回复前必须运行 `validate_continuation_gate.py`。
- 只有用户明确叫停、连续三轮仍不可恢复的真实外部阻断、初稿强制停靠三类原因可终止。

初稿停靠固定命令：

```bash
python3 "$SKILL_ROOT/scripts/validate_continuation_gate.py" \
  --project-dir "{项目目录}" \
  --reason initial_draft_stop \
  --platform zhihu
```

输出不是 `continuation_gate: passed` 时，禁止终止型回复。

## 定位与边界

本 skill 负责起盘、换链、细纲、正文和定点回炉。不把拆书、扫榜、整篇去味或 skill 公共规则维护混入写作主流程。

- `story-short-analyze` 负责拆书和来源账本。
- `story-short-write` 消费来源资产并完成新书。
- `story-deslop` 只在初稿停靠后按用户授权运行。

完整边界见 [skill-boundaries.md](references/governance/skill-boundaries.md)。

## 全新开书隔离

用户要求全新开书时，只允许读取：

- 本轮明确指定的原始样本及其同名拆文目录。
- 本 skill 的 `SKILL.md`、`references/`、`scripts/` 和通用题材规则。
- 本轮新建且未被其他书使用的项目目录。

禁止读取任何旧写作项目的设定、大纲、正文、回执、profile 或所谓流程模板。用户未逐本点名辅助书时，只做文件名级发现，再选择最小辅助集合；未选中的内容禁止读取。

正式开始前列出 `allowed_read_roots` 与 `forbidden_project_roots`。误读其他项目后必须从未污染的新目录重新起盘。

## 锁名与目录

书名必须在 `题材承诺 / 主卖点 / 核心情绪 / 付费期待` 清楚后锁定。用户未指定书名时，在模型内部生成 8-10 个候选，不另建命名回执。候选形态服从题材和目标平台，不强制塞入短意象名，也不限制完整因果句数量；至少从关系伤害与反制、身份翻面、反常事件与不可逆代价、独有物件或职业悬念中选择三种真正适合本书的机制。

强情绪短篇先做无简介冷读：只看书名，读者必须能立即看见至少一项具体关系或伤害动作，并对后果、身份答案或异常原因产生一个可复述的问题。只剩职业术语、抽象意象、人物称谓或后段动作的名字，即使声韵顺口也不得锁定；从某一节的标题、终局台词或题材隐喻直接抽出的书名，必须同时补出前因、代价或身份反差，否则视为“章节节点冒充书名”。

书名优先公开一个高价值前提，再保留下一层更值钱的问题。不能为了避剧透把初恋、替身、失踪、手术、离婚、死亡、罪证等真正卖点全部藏掉，也不能把所有反转写成剧情摘要。`失去/离开/听不见以后，他才爱、后悔或珍惜` 一类只有迟到情绪、没有本书独有关系或事件的句子，仍视为泛化模板。

每项事实必须能由当前设定直接支持；禁止为吸量虚构下跪、怀孕、死亡、出轨、重生等情节。用户提供的书名案例和拆书名只用于抽取吸引机制与形态分布，禁止复用其语序、标点、句壳或只替换名词。用户明确要求网上核验、按榜单起名或评估点击力时，调用 `story-short-scan` 采集公开样本与可见信号；普通开书不把扫榜增设为强制流程。

评分：冷读点击欲 30、核心卖点与关系辨识 25、信息差与付费期待 20、事实准确及正文可兑现 15、题面独有性与结构原创性 10。冷读点击欲低于 24、核心卖点与关系辨识低于 20、事实准确非满分、表层仿写风险非低或任一硬检查失败，禁止锁名。最终候选若仍需读简介才能解释“为什么值得点”，立即淘汰并从卖点层重起，不做句面润色。

锁名后用一条命令完成校验、原子创建与复验：

```bash
python3 "$SKILL_ROOT/scripts/validate_project_directory_name.py" \
  --project-dir "{工作区}/{小说书名}" \
  --title "{小说书名}" \
  --create-new
```

目标路径已存在时必须换名，禁止覆盖、复用、备份或移动已有路径。项目目录 basename 必须与书名逐字一致。

## 来源角色

项目配置是来源边界唯一真源：

- 主体原文独占正文声线，供应完整 P 拍、E 拍、情节/情绪骨架和表演颗粒。
- 辅助来源只供应 `selected_bids` 中明确选中的 P 拍机制。
- 辅助来源不得供应声线、句式、语气、对白嘴型、E 拍或人物壳。
- 来源路径、角色、SHA、profile 和辅助边界写入 `项目写作配置.json`，不另建读取证明。

项目配置人工填完后直接运行来源策略脚本。脚本在目标不存在时从主体 profile 初始化项目 profile，
再写入辅助边界；单书主链不得先单独生成或融合项目 profile：

仿写默认使用 `length_policy.mode=source_anchored`：细纲总上限、正文总量和数字节数都以主体原文为锚，比例不得超过 1.25。它是全书上限，不是必须写满的配额，也不设置迫使补字的下限。只有用户明确要求扩写时，才可切换 `explicit_expansion`，同时记录 `authorized_by_user=true`、用户要求和新的比例；不得凭“情节完整”自行扩容。

```bash
python3 "$SKILL_ROOT/scripts/apply_project_profile_policy.py" \
  --config "{项目目录}/写作资产/项目写作配置.json"
```

## 保留层与 P 拍换芯

主体原文的完整层级必须保留：故事核与关系命题、关系/情绪母线、BID 顺序及进入/退出位置、全部 E 拍的内容烈度与原序、全部 SF 六维成文颗粒，以及主体 P 拍的数量、原序和承重槽位。

只替换主体 P 拍的可见事件内容。每个来源 P 拍必须一对一改造成目标 P 拍；保留“这一步必须完成什么”，替换人物身份、关系壳、职业领域、现场、触发方式、物件、证据、控制权实现和现实后果。禁止把“颗粒全保留”解释成原事件换名复刻。

在细纲定稿前，按各 BID/E 拍的压力机制检索近 30 天热点新闻；没有合适机制时最多扩到 90 天。新闻只供应制度压力、职业规则、舆论机制、证据形态或现实后果，不供应声线，也不得复制真实人物、新闻原句或完整时间线。至少两条不同新闻落到两个不同目标 P 拍；主体只有一个 P 拍时最低数量随之降为一。

检索、去标识化、P 拍替换字段和正反例见 [P 拍热点换芯](references/governance/p-beat-hot-news-replacement.md)。热点与替换判断直接填入既有 `纲层迁移侧车.json`，合并后进入正式合同，不新增新闻回执或素材侧车。

## 唯一正式流程

### Phase 1：设定与细纲

顺序完成 `设定.md` 和 `小节大纲.md`。设定完成后先按 BID/E 压力机制检索热点，再用新的目标 P 拍定稿细纲。细纲必须包含导语、连续数字节和尾声；每个区域至少写清：

- 主事件、子事件和逐条细拍。
- 情绪变化、读者新增信息、钩子、物件。
- 动静、对白密度、目标字数和场面单元。

每条细拍承担一个可辨动作、信息变化或关系后果。场面单元必须能指导现场写作，不能只是功能总结。

数字节密度必须迁移主体原文的段落呼吸。写前放行会读取主体原文的连续裸数字或带点数字节号，以主体节均非空白字符、主体节数和细纲目标字数计算最低合理节数，同时校验全书目标上限与数字节数上限；禁止把主体多个完整翻刀点压进一个超长数字节，也禁止在未获授权时把短篇骨架扩成中篇。

细纲的目标字数只用于写前配重、全书体量上限和分节密度判断，不是正文逐节硬门禁。终审按 P/E 拍、场面、SF 六维和声线完整度判断，并只以主体锚定的全书上限拦截失控扩写；不得因实际字数偏离单节目标而补描写、加回忆、重复情绪或删除必要现场。

### Phase 2：一次紧凑迁移合同

纲层只保留不可机械恢复的判断：

1. 主体全部 P 拍映射到哪条目标细拍。
2. 主体全部 E 拍映射到哪条目标细拍。
3. 辅助选中 BID 的 P 拍映射到哪条目标细拍。
4. 每个主体 P 拍保留什么承重功能、替换了哪些事件壳维度。
5. 哪些热点新闻机制进入哪些目标 P 拍，以及事实与虚构边界。

字数、场面、物件、主事件、节级承载和证据文本均直接从 `小节大纲.md` 解析，不允许再人工抄成节级合同。来源拍与目标拍使用同序 ID 数组，不逐拍重抄来源 actor、action、后果或期待变化。`p_beat_replacements` 与主体 P 拍等长同序，由脚本从映射自动绑定目标 ID 和细纲证据；人工只填写保留功能、至少三个替换维度、新闻 ID 和改编判断。

主体 `子流程索引.jsonl` 是必需来源资产。脚本校验每个 `SF-*` 都具备叙述态度、句间节奏、段落气口、对白错位、动作感知情绪织入、叙述者插嘴与毛边六维颗粒，再按原文行区间和主体 P 拍映射自动派生到目标区域；不得新增人工 SF 映射回执，也不得把辅助来源接入文字颗粒。

初始化或续用：

```bash
python3 "$SKILL_ROOT/scripts/batch_outline_release.py" \
  --project "{项目名}" \
  --project-dir "{项目目录}"
```

细纲只做拆节、合节或移动且既有细拍证据原文未改时，使用正式重绑参数按证据迁移旧 P/E 映射和人工确认，不得另写临时迁移脚本：

```bash
python3 "$SKILL_ROOT/scripts/validate_outline_migration_contract.py" rebind-outline \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --outline "{项目目录}/小节大纲.md" \
  --preserve-by-evidence
```

一次导出、一次回填、一次合并：

```bash
python3 "$SKILL_ROOT/scripts/validate_outline_migration_contract.py" export-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --output "{项目目录}/写作资产/纲层迁移侧车.json"

python3 "$SKILL_ROOT/scripts/validate_outline_migration_contract.py" apply-template \
  --receipt "{项目目录}/写作资产/细纲表演验收回执.json" \
  --input "{项目目录}/写作资产/纲层迁移侧车.json"
```

映射不得漏拍、并拍或倒序。辅助来源只有 P 拍数组，没有 E 拍入口。`apply-template`
成功后自动删除已合并的工作侧车，项目只保留正式合同。

### Phase 3：正文放行与直接写作

主体声线直接由主体原文、主体 profile 和主体子流程六维颗粒约束；情绪由 E 拍映射和详细细纲约束；可见事件只来自已经换芯的目标 P 拍。正文放行后直接写作。

正文前只运行：

```bash
python3 "$SKILL_ROOT/scripts/validate_streamlined_write_release.py" \
  --project-dir "{项目目录}"
```

通过后直接写入 `正文.md`：首行用 `# 《书名》`，随后写导语，再按 `1.`、`2.` 直到 `N.` 的知乎纯数字分节顺序写正文，尾声并入最后一个数字节。可以分批编辑文件，但不得为每节创建“开始/暂存/验收/提交”行政流程。

写每个区域前，从合同的 `granularity_coverage` 读取该区域全部 `SF-*`，同时读取 BID/E 层级、`p_beat_replacements` 和热点机制。六维作为成文约束，目标 P 拍负责制造对应 E 拍；不得复制原句、人物或事件壳。每写完一节立即通读并改正文，检查：摘要化、错脸、对白答题、漏动作后果、E/P 错序、原 P 事件壳回流、热点硬贴、六维颗粒降级、辅助声线渗入和主体声线漂移。检查发生在正文上，不另建逐节证明。

### Phase 4：一次合并终审

全文完成后只建立 `初稿终审回执.json`。每个正文区域一次确认 P 拍换芯已兑现、E 拍完整、场面成形、原事件壳已拒绝、对应 `SF-*` 六维颗粒完整和主体声线匹配，并引用至少一条真实正文句；使用热点的区域另引至少一条热点机制落地句。全局一次检查完整上层层级、全部主体 P 拍替换、全部热点机制、全部主体 SF 覆盖、题面、实际开头、结尾后果、长句换气、对白效率、事实隐私边界和声线边界。不得把“全局声线像”冒充 SF 全集已消费，也不得另填问题修复清单；发现的问题直接修正文后运行 `refresh-derived`。

```bash
python3 "$SKILL_ROOT/scripts/validate_zhihu_section_format.py" \
  --text "{项目目录}/正文.md"

python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" init \
  --project "{项目名}" \
  --draft "{项目目录}/正文.md" \
  --outline "{项目目录}/小节大纲.md" \
  --outline-contract "{项目目录}/写作资产/细纲表演验收回执.json" \
  --project-config "{项目目录}/写作资产/项目写作配置.json" \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"

# 仅在 init 后又修改正文时运行；重绑当前 SHA，并只保留正文未变且引句仍有效的区域判断
python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" refresh-derived \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"

python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" seal \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"
```

终审发现问题必须先改正文，再运行 `refresh-derived` 绑定当前正文 SHA；不得删除正式回执重跑
`init`，也不得只改回执结论。刷新后只重新填写被脚本清空的变更区域和全局判断。
`seal` 输出通过后直接进入 Phase 5，不再单独重跑格式校验或终审 `validate`；停靠闸会复核两者。

### Phase 5：初稿停靠

终审通过后运行连续执行停靠命令。初稿停靠前不执行去 AI 味、正式多轮审计、外部校准或补丁式回炉。

## 正式白名单

单本项目只允许产生：`项目写作配置.json`、项目 profile、`设定.md`、`小节大纲.md`、`细纲表演验收回执.json`、映射填写期间的 `纲层迁移侧车.json`、`正文.md`、`初稿终审回执.json`。

本 skill 只允许调用以下脚本：

- `validate_project_directory_name.py`
- `init_project_writing_assets.py`
- `generate_story_profile.py`（来源 profile 维护工具，单书主链不调用）
- `apply_project_profile_policy.py`
- `batch_outline_release.py`
- `validate_outline_migration_contract.py`
- `validate_streamlined_write_release.py`
- `validate_initial_draft_review.py`
- `validate_continuation_gate.py`
- `validate_zhihu_section_format.py`

未列出的单本写作产物或短篇脚本视为流程污染，发现后不得读取或执行。

## 写作硬标准

- 正文唯一声线来自主体原文。保留主体的句间转折、功能词、叙述距离、即时主观声音、对白轮转和段落呼吸。
- 主体全部 SF 的六维颗粒必须随 P 拍自动落到目标区域；写作和终审都不得只使用 profile 的书级汇总声线。
- 故事核、关系/情绪母线、BID 进出位置和全部 E 拍必须完整保留；任何热点不得改写上层情绪因果。
- 主体 P 拍只保留等量同序承重槽位，每一拍都必须换成新的目标事件；原人物、职业、物件、现场和完整事件壳不得回流。
- 热点新闻只供应目标 P 拍的现实机制，必须可追溯、在检索时不超过 90 天并完成去标识化；不得扩成游离支线。
- 不复制主体的专名、核心物件、完整关系壳或原句。
- 主体 P 拍槽位与 E 拍按合同原序兑现；辅助机制只能叠加，不能替换主体上层骨架。
- 强情绪必须改变人物期待、行动冲动或现实位置，不靠情绪词汇报。
- 追妻必须由失去控制权、接近资格和真实代价推动，不靠突然自白。
- 女主离开必须落到可见决定、物件处置、法律/工作/联系权变化。
- 高潮至少满足两项：压后信息释放、发生在最该公开的场面、让前文意义整体变狠。
- 结尾保留后果和新位置，不做空泛价值总结。
- 多动作、多信息或视线换主的长句必须在自然换气点拆开；单一身体、感官或话轮链可保留长句。
- 不把连续现场压成一行，也不机械拆成“一句一个动作”的施工清单。

## 脚本纪律

- `$SKILL_ROOT` 由当前实际加载的 `SKILL.md` 路径推导，不假设安装层级。
- 已有完整命令时禁止先跑 `--help` 探参。
- 正式产物由官方脚本初始化、绑定和封口；人工字段用 `apply_patch` 小范围填写。
- 临时脚本只允许一次性只读诊断。重复性写入必须并入正式脚本。
- 同一路径上的 `export / apply / validate / seal` 严格串行。
- 续跑时复用绑定仍有效的已通过回执；上游未变更时，不重放已通过的初始化或放行命令。
- `seal` 通过后直接运行停靠闸，不加一次“保险式”格式或终审复验。
- 脚本只能做确定性解析、绑定、映射展开和校验，不得生成正文或人工判断。
- 同一语义只保留一个人工真源；下游需要不同形状时确定性派生，不再人工抄写。

## 参考入口

- [短篇正式执行骨架](references/governance/short-write-execution-core.md)
- [短篇写作工作流](references/workflow/writing-workflow.md)
- [格式规范](references/workflow/format-and-structure.md)
- [主体原文主导首稿](references/governance/source-dominant-first-draft.md)
- [P 拍热点换芯](references/governance/p-beat-hot-news-replacement.md)
- [开头与钩子](references/craft/opening-and-hook-library.md)
- [情绪与后果](references/craft/emotion-and-outcome-library.md)
- [人物与对白](references/craft/character-voice-library.md)
- [高敏回修](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)

技法文件按当前问题读取，不得把“读完全部参考资料”设为正文前流程。

## 流程衔接

| 时机 | 跳转到 |
|---|---|
| 有参考小说要拆 | `story-short-analyze` |
| 初稿停靠后按用户授权去味 | `story-deslop` |
| 需要市场方向 | `story-short-scan` |
| 设定明显更适合长篇 | `story-long-write` |
