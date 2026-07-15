---
name: output-contract
description: |
  story-short-analyze 输出契约。定义 Stage → 文件映射、_meta.json schema、
  下游消费规范（story-short-write 读全套 markdown + 原文 + _meta.json 写新短篇）。
sync-source: skills/story-short-analyze/references/pipeline/output-contract.md
sync-policy: |
  本文件在 story-short-analyze 与 story-short-write 之间需保持字节一致（byte-equal）。
  修改任一副本后，必须同步另一副本，并通过 bash scripts/check-shared-files.sh 验证。
  禁止把本文件加入 IGNORE_NAMES 列表——它必须保持同步，不属于 intentional differences。
---

# 输出契约：story-short-analyze ↔ story-short-write

`story-short-analyze` 拆完一篇短篇后，产物落盘到 `拆文库/{书名}/`。`story-short-write`
写下一篇同题材短篇时，要**一起**读这个目录下的全部产出。

---

## 输出目录与文件树

```
拆文库/{书名}/
├── 原文/                  # 管道前置步骤产出，存放源文件备份
├── 可直接仿写_导语拆解表.md  # 可选：仿写/融合/去原作化时建议落盘
├── 可直接仿写_顺序事件表.md  # 可选：仿写/融合/去原作化时建议落盘
├── 可直接仿写_物件表.md      # 可选
├── 可直接仿写_动作表.md      # 可选
├── 可直接仿写_对白功能表.md  # 可选
├── 可直接仿写_对话衔接表.md  # 可选
├── 可直接仿写_误判表.md      # 可选
├── 可直接仿写_钩子表.md      # 可选
├── 可直接仿写_微动作表.md    # 可选
├── 可直接仿写_安静压迫场表.md # 可选
├── 可直接仿写_人物偏手表.md   # 高情绪题材强烈建议落盘
├── 可直接仿写_失控说话表.md   # 高情绪题材强烈建议落盘
├── 可直接仿写_烂关系漏出表.md # 高情绪题材强烈建议落盘
├── 可直接仿写_外部秩序表.md   # 高情绪题材强烈建议落盘
├── 可直接仿写_公开炸场表.md   # 高情绪题材强烈建议落盘
├── 可直接仿写_后果链表.md     # 高情绪题材强烈建议落盘
├── 写作资产/
│   ├── 样本分级与可学层.md   # 判定整本是否可提DNA，哪些层可学/禁学
│   ├── 作者DNA指纹.md         # 仿写/融合/去原作化硬门槛
│   ├── 仿写约束_禁写清单.md   # 仿写/融合/去原作化硬门槛
│   ├── 同桥段过检规则.md      # 仿写/融合/去原作化硬门槛
│   └── profile_source.md      # 模型先提的 profile 原始材料
├── book.profile.json       # 单书结构化规则包，仿写/融合/去AI味硬门槛
├── 拆文报告.md             # 人类可读综合报告（Stage 2-6 综合）
├── 情节节点.md             # Stage 2 情节节点清单
├── 写作手法.md             # Stage 4 写作手法分析
└── _meta.json             # 管道元数据 + 结构计数（resume + Phase 7 门控数值依据）
```

**文件名约定**：`拆文报告.md / 情节节点.md / 写作手法.md / book.profile.json` 由短篇写作链路固定消费，不能改名。分析叙事走 markdown，数字和枚举走 `_meta.json.structure_counts`，结构化规则走 `book.profile.json`。

**语义约定**：`样本分级与可学层 / 作者DNA指纹 / 仿写约束_禁写清单 / 同桥段过检规则 / profile_source` 不能只是非空文件，必须是“证据型资产”：

- `样本分级与可学层.md`：必须明确写出 `A类正样本 / B类骨架样本 / C类负样本` 三选一，并拆清：
  - `是否可用于DNA提取`
  - `原文检测结论`
  - `原文整体分数`
  - `原文高风险块`
  - `分数使用口径`
  - `可学层`
  - `禁学层`
  - `判定证据`
  - `后续调用方式`
- `作者DNA指纹.md`：至少覆盖句长切句、停顿、口气差、动作替代、旧伤触发器、反面句型
- `仿写约束_禁写清单.md`：每条禁写项后面都要带“为什么假 / 会把文写坏在哪”
- `同桥段过检规则.md`：每个桥段都要带“原文承重件 / 新稿高风险假点 / 不能丢的东西”
- `写作手法.md`：除了 POV / 对话 / 时间 / 信息控制，还必须补 `开场入口 / 回忆职责 / 关键断场点 / 尾声入口 / 收口落点`
- `写作手法.md`：必须按固定骨架落盘，至少包含 `1.POV策略 / 2.对话手法 / 3.时间操控 / 4.章法硬拆 / 5.章法失效测试 / 6.信息控制 / 7.其他手法 / 8.意象物件追踪 / 9.手法总评与迁移提醒`
- `写作资产/profile_source.md`：必须把模型读完整篇后提出来的原始 profile 材料写清，至少覆盖：
  - `样本分级 / 是否可用于DNA提取 / 原文检测结论 / 原文整体分数 / 原文高风险块 / 分数使用口径 / 可学层 / 禁学层`
  - `题材流派 / 主梗 / 副梗`
  - `作者DNA`
  - `桥段承重件`
  - `禁句 / 禁写法`
  - `开头高信息量信号`
  - `场面资产 / 后果链`
  - 其中 `桥段承重件` 不能只停在“承重件 + 假点”，还必须能映射出：
    - `opening_pattern`
    - `recommended_sequence`
    - `why_order_matters`
    - `fake_signals`
    - `why_original_passes`

---

## Stage → 文件映射

| Stage | 名称 | 落地文件 | 主要内容 |
|-------|------|----------|---------|
| 2 | 结构+情节节点 | `拆文报告.md`（故事核/结构/梗概段） + `情节节点.md` | 故事核 / 4-6 段结构 / 故事梗概 / 情节节点清单 |
| 3 | 情感线+爆点 | `拆文报告.md`（情感曲线段+爆点段） | 情感曲线 ≥5 节点 / 爆点 6 维度 / 期待感 |
| 4 | 反转+写作手法 | `拆文报告.md`（反转段） + `写作手法.md` | 前置反转检查 / 反转分析（铺垫 ≥2） / 写作手法 ≥5 项 |
| 5 | 人物+开头结尾 | `拆文报告.md`（人物段+首尾段） | 人物分类+功能评估 / 开头分析 / 结尾分析 / 首尾呼应 |
| 6 | 综合评估 | `拆文报告.md`（综合段） + `_meta.json`（写 structure_counts） | 五维评分 / 爆点性 / 话题性 / 共鸣 ≥3 层 / 可复用结构 ≥3 条 / 节奏速报 |

---

## `_meta.json` schema

`_meta.json` 是管道元数据 + 结构计数。**这里不放分析内容**，只放数字和枚举，给 Phase 7 门控做完整性校验。分析叙事都放在 `拆文报告.md` 里。

```jsonc
{
  "version": "2.0",
  "word_count": 5234,                   // 源文字数（Phase 1 探针填入）
  "genre_detected": "追妻",             // Phase 1 题材识别；未识别填 "通用"
  "created_at": "{ISO8601 时间戳}",      // 拆文启动时间，写入时填当前 UTC
  "stages_completed": [2, 3, 4, 5],     // 已完成 Stage，按完成顺序 append
  "last_stage_in_progress": null,       // 当前正在执行的 Stage；空闲为 null

  "structure_counts": {                 // Stage 6 完成时一次性写入；Phase 7.2 验收依据
    "beats": 5,                         // 结构段数（结构划分，开端/发展/高潮/结局，Stage 2）
    "hooks": 4,                         // 钩子数（Stage 3）
    "setup_clues": 3,                   // 反转铺垫线索数（Stage 4）
    "character_archetypes": 3,          // 有反差人物数（Stage 5）
    "reusable_structures": 3,           // 可复用手法条数（Stage 6）
    "reversal_type": "视角反转"          // 反转类型枚举（视角/身份/动机/时间线/信息/认知/无反转）；甜宠/喜剧/报应型填「无反转」
  }
}
```

### 写入顺序（crash safety）

1. **Stage N 开始前**：先把 `last_stage_in_progress = N` 写盘。
2. **Stage N 文件写完后**：做 non-empty + 最小长度合理性检查（如 `拆文报告.md` 新增段 ≥ 200 字）。
3. **通过**：清空 `last_stage_in_progress`，再把 `N` append 到 `stages_completed[]`。
4. **失败**：`stages_completed` 不动，`last_stage_in_progress` 保留为 `N`。
5. **Stage 6 完成时额外动作**：把 `structure_counts` 一次性算出并写入 `_meta.json`，然后才进 Phase 7。

### Resume 协议

- `last_stage_in_progress` 非空：说明该 Stage 上次中断了，**从头**重跑，不复用半成品。
- `last_stage_in_progress` 为空：从 `max(stages_completed) + 1` 开始。
- `stages_completed` 含 6：说明已经完成，询问用户覆盖还是取消。

**Stage 6 = 内容写完 AND Phase 7 通过**。Phase 7 未过前 `last_stage_in_progress` 保持 `6`、`stages_completed` 不含 `6`；resume 时正文/structure_counts 已在盘上，只重跑 Phase 7 门控，不重写 Stage 6 正文。

---

## Phase 7 门控接入点

Stage 6 内容写完后、`stages_completed[6]` append 前，跑四道门控：

### 7.1 拆文报告 AI 腔自检

扫描 `拆文报告.md` 全文，对照 `skills/story-short-analyze/references/governance/banned-words.md` + `skills/story-short-analyze/references/governance/anti-ai-writing.md`。
命中就不要写 `stages_completed[6]`，列出位置，让用户修订**拆文报告本身**的 AI 腔（源文里有 AI 腔不算，这里扫的是分析师写的报告）。

### 7.2 `_meta.json.structure_counts` 数值校验

| 字段 | 最低值 | 不达标 |
|------|--------|--------|
| `structure_counts.beats` | ≥ 4（结构段：开端/发展/高潮/结局）| 阻断 |
| `structure_counts.hooks` | ≥ 3 | 阻断 |
| `structure_counts.setup_clues` | ≥ 3（reversal_type=无反转时跳过本行）| 阻断 |
| `structure_counts.character_archetypes` | ≥ 2 | 阻断 |
| `structure_counts.reusable_structures` | ≥ 3 | 阻断 |
| `structure_counts.reversal_type` | 在枚举内（含「无反转」）| 阻断 |
| `genre_detected` | 非空 | 阻断 |

> 情节节点数（15-60 个，按字数分档）走 `情节节点.md` 自己的密度校验（见 `material-decomposition.md`），不在本表。`beats` 是结构段数，不是情节节点数。

### 7.3 `story-short-analyze/references/pipeline/output-templates.md` BLOCK 项扫描

扫 `story-short-analyze/references/pipeline/output-templates.md` 里所有 `[BLOCK]` 标注项，看对应产出段是否在 `拆文报告.md` 出现。
任一缺失就阻断。`[WARN]` 项则写入拆文报告末尾的“待补”清单，不阻断。

### 7.4 仿写资产完整性校验

如果该拆文目标包含 `仿写 / 融合 / 去原作化 / 去AI味回修` 中任意一种，额外检查以下 5 份文件必须存在且非空：

- `写作资产/样本分级与可学层.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/仿写约束_禁写清单.md`
- `写作资产/同桥段过检规则.md`
- `写作资产/profile_source.md`

任意缺 1 份，就不能判定为 `ready-for-write`，也不能提示“可直接安全仿写”。
尤其缺 `写作资产/样本分级与可学层.md` 时，默认这本书还没完成“整本可不可以提 DNA、哪些层能学”的判断。
尤其缺 `同桥段过检规则.md` 时，默认还没有拆到“可直接拿去做同桥段融合与去AI味回修”的层级。
尤其缺 `写作资产/profile_source.md` 时，默认这本书还没有完成“模型先提 profile 原始材料”这一步，不允许直接只靠脚本盲抽。

进一步的语义检查口径：

- `写作资产/样本分级与可学层.md` 里如果只有“这本不错 / 可以参考”这种整本评价，没有 `样本等级 + 可学层 + 禁学层 + 证据`，视为未通过
- `作者DNA指纹.md` 里如果只有“文风细腻 / 情绪克制 / 擅长反转”这种标签，没有原文级现象和反面句型，视为未通过
- `仿写约束_禁写清单.md` 里如果只有禁令，没有“为什么假”，视为未通过
- `同桥段过检规则.md` 里如果只有桥段名，没有承重件、假点和保留件，视为未通过
- `同桥段过检规则.md` 里如果缺“原文怎么起手 / 为什么顺序不能乱 / 原文为什么能过”里的任意 1 类，视为未通过
- `写作手法.md` 里如果缺 `开场入口 / 时间线类型 / 回忆职责 / 关键断场点 / 尾声入口 / 收口落点` 里的任意 2 类，视为未通过
- `写作手法.md` 里如果没有按固定骨架落盘，或缺 `章法失效测试 / 手法总评与迁移提醒` 任意 1 节，视为未通过

执行提醒：

- Stage 4 开始前，默认先读 `output-templates.md` 的 `写作手法.md 固定骨架`
- 如果实际落盘标题顺序和固定骨架不一致，默认按未通过处理，不接受“意思差不多”的自由发挥
- `写作资产/profile_source.md` 里如果只有几条抽象标签，没有字段化原始材料，视为未通过
- `写作资产/profile_source.md` 里如果 `桥段承重件` 缺 `原文怎么起手 / 不能丢的顺序 / 为什么这个顺序不能乱 / 最容易写假的点 / 原文为什么能过` 里的任意 2 类，视为未通过
- 这 5 份里任意 1 份缺“正面可学项 + 负面禁写项”双侧信息，默认仍是 `blocked-on-assets`

### 7.5 生成单书 profile

先由模型补出 `写作资产/profile_source.md`，再调用本地 skill 脚本生成 `book.profile.json`。

`profile_source.md` 不是最终规则包，而是“模型先提、脚本后收”的中间层。
禁止跳过这一层，直接让脚本从全部 Markdown 盲抽。

通过 7.4 后，调用本地 skill 脚本生成：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --source "拆文库/{书名}" \
  --name "{书名}" \
  --output "拆文库/{书名}/book.profile.json"
```

如果生成失败，不进入 `ready-for-write`。
如果 `book.profile.json` 缺少基本字段，也不进入 `ready-for-write`。
`book.profile.json` 默认至少要能读到：

- `bridge_rules`
- `scene_assets`
- `style_assets`

其中 `bridge_rules` 里任意命中桥段默认至少要具备：

- `opening_pattern`
- `must_keep`
- `fake_signals`
- `recommended_sequence`

如果桥段只有 `must_keep / must_avoid`，默认仍没拆到可直接支撑同桥段仿写与去 AI 味回修的层级。

### 7.6 通过

清空 `_meta.json.last_stage_in_progress`，append `6` 到 `stages_completed[]`，再提示用户「拆解完成，可调用 `/story-short-write` 写下一篇」。

---

## 下游消费规范（story-short-write 怎么用）

> `story-short-write` 不再只读 3 份 markdown，而是默认读取 `拆文报告.md / 情节节点.md / 写作手法.md / 写作资产/*.md / 可直接仿写_*.md / book.profile.json` 这一整套资产。
> `_meta.json` 是增强层；`book.profile.json` 不是增强层，而是写前规则包。

| 文件 | 角色 | 怎么读 |
|------|------|--------|
| `_meta.json`（可选）| 数字门面 + 题材识别 | 看 `genre_detected` 决定用哪个题材标尺，读 `structure_counts` 确认拆文完整性，读 `structure_counts.reversal_type` 选反转骨架 |
| `写作资产/profile_source.md`（必读） | 模型先提的原始规则层 | 先读它确认模型对这本书的流派判断、禁写壳、桥段承重件、开头信号和场面资产怎么理解；它负责保留脚本难抽出的隐性信息 |
| `book.profile.json`（必读） | 结构化规则包 | 读 `bridge_rules / banned_phrases / opening_signal_groups / opening_chain_patterns / author_stance_patterns / scene_assets / style_assets`，把拆书资产转成写前硬约束和写后审计输入 |
| `写作资产/样本分级与可学层.md`（必读） | 样本准入门槛 | 先判断这本书到底是 `A类正样本 / B类骨架样本 / C类负样本`。如果只是 `B类骨架样本`，后续只学桥段和承重件，不学句法；如果是 `C类负样本`，只拿来反推禁写规则 |
| `写作资产/*.md`（仿写/融合/去原作化硬门槛） | DNA / 禁写 / 过检规则 | 先读 `作者DNA指纹 → 仿写约束_禁写清单 → 同桥段过检规则`。这 3 份先回答“要学什么口气和承重件、绝不能写什么、同桥段为什么原文能过而仿稿会假”；缺任意 1 份，默认不进入正文仿写 |
| `可直接仿写_*.md`（强烈建议，仿写时视作必读） | 仿写/融合直接输入 | 优先按 `导语拆解 → 顺序事件 → 物件 → 动作 → 对白功能 → 对话衔接 → 误判 → 钩子 → 微动作 → 安静压迫场 → 人物偏手 → 失控说话 → 烂关系漏出 → 外部秩序 → 公开炸场 → 后果链` 顺序读取；高情绪题材缺任意 3 张以上，默认仍停在概括层 |
| `拆文报告.md` | 分析叙事主体 | 读「故事核」「结构」「情感曲线」「爆点」「反转分析」「人物」「五维评分」「共鸣分析」「可复用结构」「同类型写作动作」段，是 writer 的主输入 |
| `情节节点.md` | 节奏锚点 | 看每个节点的字数位置 + 功能 + 触发事件，给新故事排节奏 |
| `写作手法.md` | 手法库 | 按固定 9 节骨架输出 POV / 对话 / 时间 / 信息控制 / 意象物件 / 总评，供新篇直接复用 |
| `写作手法.md`（高敏任务） | 章法库 | 除常规手法外，必须读 `章法硬拆 + 章法失效测试 + 手法总评与迁移提醒`，先判断原文怎么藏住成品感 |
| `原文/` | 语感源 | 抄对话调子、节奏、画面感、打脸张力。**不抄具体情节**，只抄写法。 |

### 写作流程建议

1. 先看 `写作资产/样本分级与可学层.md`，先决定这本书是拿来提 DNA，还是只拿骨架，还是只当负样本。
2. 再看 `写作资产/作者DNA指纹.md`、`写作资产/仿写约束_禁写清单.md`、`写作资产/同桥段过检规则.md`，先立“学什么 / 禁什么 / 同桥段怎么过”。
   其中 `作者DNA指纹.md` 先抽“这个作者稳定怎么写”，`仿写约束_禁写清单.md` 再拦“绝对不能怎么写”，`同桥段过检规则.md` 最后决定“同桥时哪些承重件不能丢”。
2. 再读 `写作资产/profile_source.md`，确认模型先提出来的流派判断、桥段起效逻辑、禁写壳和场面资产有没有偏。
3. 再读 `book.profile.json`，确认开头信号阈值、桥段承重件、禁句、作者站位风险、场面资产和 10 类 `style_assets` 已经被脚本标准化。
4. 再看 `_meta.json.genre_detected` 和 `structure_counts.reversal_type` 选骨架。
5. 如果目录里有 `可直接仿写_*.md`，按 `导语拆解 → 顺序事件 → 物件 → 动作 → 对白功能 → 对话衔接 → 误判 → 钩子 → 微动作 → 安静压迫场 → 人物偏手 → 失控说话 → 烂关系漏出 → 外部秩序 → 公开炸场 → 后果链` 读取。
6. 再读 `拆文报告.md` 里的“核心手法”“共鸣分析”“可复用结构”，决定哪些保留，哪些调整。
7. 读 `情节节点.md`，把节奏锚点抄到新故事的字数位置上。
8. 写场景时翻 `写作手法.md` + `原文/`，参考具体写法。
9. 写完后可选：在新文档 frontmatter 写 `derived_from: 拆文库/{书名}/`，方便追溯。

### 维护者本地烟雾测试

```bash
ls 拆文库/{书名}/   # 应有：原文/ 写作资产/ 拆文报告.md 情节节点.md 写作手法.md book.profile.json _meta.json
test -f 拆文库/{书名}/写作资产/profile_source.md
python3 "$CODEX_HOME/skills/story-short-write/scripts/audit_novel_ai_flavor.py" 新稿.md --profile 拆文库/{书名}/book.profile.json --json
/story-short-write 拆文库/{书名}/
# 通过：上游 3 份写作资产 + `profile_source.md` + `book.profile.json` 齐全，且输出 8000+ 字同题材新短篇，prose 带着源文的对话节奏和画面感
# 失败：写得像填空，或 short-write 读不到关键 markdown / 写作资产
```

---

## 版本约定

- `_meta.json.version` 与本文件 `sync-policy` 联动。
- breaking change（字段重命名 / 类型变更 / 必填变更）必须 bump major version 并同步两侧副本，CI 通过 `scripts/check-shared-files.sh` 拦截单边修改。
- additive change（新增可选字段）可 bump minor，旧字段保持读容忍。
