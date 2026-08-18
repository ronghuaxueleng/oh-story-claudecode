---
name: story-short-write
description: |
  短篇网文写作。辅助短篇小说创作，从起盘、搭骨架到正文和回炉，重点抓冲突、情绪、高潮和值得付费的后果。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」
metadata:
  version: 1.74.1
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

书名必须在 `题材承诺 / 主卖点 / 核心情绪 / 付费期待` 清楚后锁定。用户未指定书名时，在模型内部生成 8-10 个候选，不另建命名回执。候选不能都把剧情写成完整长句，必须至少覆盖五类：2-6 字核心意象或专名、关系悖论、反常事件、触发反转、身份倒置、公开失信、倒计时或物件悬念。

每个候选只保留一个主钩子，不要求同时塞入载体、关系、异常和后果。完整句式最多 2 个，`我……后，他……` 等同一因果句壳最多 1 个；其余必须改变长度、主语、信息顺序和语气。`失去/离开/听不见以后，他才爱、后悔或珍惜` 一类题材概括句，无论是否顺口，都视为泛化迟到情绪模板。

用户提供的书名案例和拆书名只用于抽取吸引机制与形态分布，禁止复用其语序、标点、句壳或只替换名词。最终候选若与任一参考书名存在明显表层仿写关系，即使评分最高也必须淘汰。短标题不因没有复述完整剧情而扣分，只检查它能否形成独有联想、反常关系或明确情绪方向。

评分：探索心 25、关系或题材承诺 20、情绪与付费期待 20、口语与声韵 15、题面独有性 10、结构原创性 10。探索心低于 19、表层仿写风险非低、同形态候选挤占过半或任一硬检查失败，禁止锁名。

锁名后固定执行：

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

目标路径已存在时必须换名，禁止覆盖、复用、备份或移动已有路径。项目目录 basename 必须与书名逐字一致。

## 来源角色

项目配置是来源边界唯一真源：

- 主体原文独占正文声线，供应完整 P 拍、E 拍、情节/情绪骨架和表演颗粒。
- 辅助来源只供应 `selected_bids` 中明确选中的 P 拍机制。
- 辅助来源不得供应声线、句式、语气、对白嘴型、E 拍或人物壳。
- 来源路径、角色、SHA、profile 和辅助边界写入 `项目写作配置.json`，不另建读取证明。

## 唯一正式流程

### Phase 1：设定与细纲

顺序完成 `设定.md` 和 `小节大纲.md`。细纲必须包含导语、连续数字节和尾声；每个区域至少写清：

- 主事件、子事件和逐条细拍。
- 情绪变化、读者新增信息、钩子、物件。
- 动静、对白密度、目标字数和场面单元。

每条细拍承担一个可辨动作、信息变化或关系后果。场面单元必须能指导现场写作，不能只是功能总结。

数字节密度必须迁移主体原文的段落呼吸。写前放行会读取主体原文的连续裸数字或带点数字节号，以主体节均非空白字符、主体节数和细纲目标字数计算最低合理节数；禁止把主体多个完整翻刀点压进一个超长数字节。

### Phase 2：一次紧凑迁移合同

纲层只保留不可机械恢复的三种判断：

1. 主体全部 P 拍映射到哪条目标细拍。
2. 主体全部 E 拍映射到哪条目标细拍。
3. 辅助选中 BID 的 P 拍映射到哪条目标细拍。

字数、场面、物件、主事件、节级承载和证据文本均直接从 `小节大纲.md` 解析，不允许再人工抄成节级合同。来源拍与目标拍使用同序 ID 数组，不逐拍重写 actor、action、后果、期待变化或等价说明。

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

映射不得漏拍、并拍或倒序。辅助来源只有 P 拍数组，没有 E 拍入口。

### Phase 3：正文放行与直接写作

主体声线直接由主体原文、主体 profile 和主体子流程六维颗粒约束；情绪由 E 拍映射和详细细纲约束。正文放行后直接写作。

正文前只运行：

```bash
python3 "$SKILL_ROOT/scripts/validate_streamlined_write_release.py" \
  --project-dir "{项目目录}"
```

通过后直接写入 `正文.md`：首行用 `# 《书名》`，随后写导语，再按 `1.`、`2.` 直到 `N.` 的知乎纯数字分节顺序写正文，尾声并入最后一个数字节。可以分批编辑文件，但不得为每节创建“开始/暂存/验收/提交”行政流程。

写每个区域前，从合同的 `granularity_coverage` 读取该区域全部 `SF-*`，到主体 `子流程索引.jsonl` 展开六维原文颗粒；六维都作为成文约束，但迁移机制而不复制原句、人物或事件壳。每写完一节立即通读并改正文，检查：摘要化、错脸、对白答题、漏动作后果、E/P 错序、六维颗粒降级、辅助声线渗入和主体声线漂移。检查发生在正文上，不另建逐节证明。

### Phase 4：一次合并终审

全文完成后只建立 `初稿终审回执.json`。每个正文区域一次确认 P 拍完整、E 拍完整、场面成形、对应 `SF-*` 六维颗粒完整和主体声线匹配，并引用真实正文句；全局一次检查全部主体 SF 覆盖、题面、实际开头、结尾后果、长句换气、对白效率和声线边界。区域级合并确认替代旧版逐证据重复映射，但不得把“全局声线像”冒充 SF 全集已消费。

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

python3 "$SKILL_ROOT/scripts/validate_initial_draft_review.py" seal \
  --receipt "{项目目录}/写作资产/初稿终审回执.json"
```

终审发现问题必须先改正文，再重新初始化绑定当前正文 SHA；禁止只改回执结论。

### Phase 5：初稿停靠

终审通过后运行连续执行停靠命令。初稿停靠前不执行去 AI 味、正式多轮审计、外部校准或补丁式回炉。

## 正式白名单

单本项目只允许产生：`项目写作配置.json`、项目 profile、`设定.md`、`小节大纲.md`、`细纲表演验收回执.json`、映射填写期间的 `纲层迁移侧车.json`、`正文.md`、`初稿终审回执.json`。

本 skill 只允许调用以下脚本：

- `validate_project_directory_name.py`
- `init_project_writing_assets.py`
- `generate_story_profile.py`
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
- 不复制主体的专名、核心物件、完整关系壳或原句。
- 主体 P/E 拍按合同原序兑现；辅助机制只能叠加，不能替换主体骨架。
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
- 脚本只能做确定性解析、绑定、映射展开和校验，不得生成正文或人工判断。
- 同一语义只保留一个人工真源；下游需要不同形状时确定性派生，不再人工抄写。

## 参考入口

- [短篇正式执行骨架](references/governance/short-write-execution-core.md)
- [短篇写作工作流](references/workflow/writing-workflow.md)
- [格式规范](references/workflow/format-and-structure.md)
- [主体原文主导首稿](references/governance/source-dominant-first-draft.md)
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
