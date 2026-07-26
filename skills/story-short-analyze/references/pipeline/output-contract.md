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
├── _sample_comparison.md  # 内置样本选择、正反例锚点、主报告后复核记录
├── 事实与推断台账.md       # 主体、时间、证据来源、因果口径硬底座
├── 可直接仿写_导语拆解表.md
├── 可直接仿写_顺序事件表.md
├── 可直接仿写_物件表.md
├── 可直接仿写_动作表.md
├── 可直接仿写_对白功能表.md
├── 可直接仿写_对话衔接表.md
├── 可直接仿写_误判表.md
├── 可直接仿写_钩子表.md
├── 可直接仿写_微动作表.md
├── 可直接仿写_安静压迫场表.md
├── 可直接仿写_人物偏手表.md
├── 可直接仿写_失控说话表.md
├── 可直接仿写_烂关系漏出表.md
├── 可直接仿写_外部秩序表.md
├── 可直接仿写_公开炸场表.md
├── 可直接仿写_后果链表.md
├── 原文细节库/
│   ├── 场景细节库.md
│   ├── 关系细节库.md
│   ├── 情绪细节库.md
│   ├── 对白细节库.md
│   ├── 翻车细节库.md
│   ├── 旧伤细节库.md
│   ├── 动作细节库.md
│   └── 场面细节库.md
├── 写作资产/
│   ├── 母结构_故事走法.md
│   ├── 主冲突_副升级器.md
│   ├── 异物清单.md
│   ├── 第二层冲突清单.md
│   ├── 角色口气模板.md
│   ├── 关系重组方式.md
│   ├── 交流承压拆解.md
│   ├── 冲突载体清单.md
│   ├── 公开场_关键硬牌_后果.md
│   ├── 平台适配提醒.md
│   ├── 情绪母线.md
│   ├── 新状态清单.md
│   ├── 虐点对照细节.md
│   ├── 样本分级与可学层.md   # 判定整本是否可提DNA，哪些层可学/禁学
│   ├── 高敏桥段识别.md       # 高敏桥与过检机制
│   ├── 作者DNA指纹.md         # 仿写/融合/去原作化硬门槛
│   ├── 仿写约束_禁写清单.md   # 仿写/融合/去原作化硬门槛
│   ├── 同桥段过检规则.md      # 仿写/融合/去原作化硬门槛
│   ├── 原文资产候选池.md       # 全文第二遍资产回扫与16表逐项核销账
│   ├── 本书动态信号字典.json   # 单书信号发现、表后回补与候选关联
│   ├── profile_source.md      # 模型先提的 profile 原始材料
│   ├── 桥段施工卡.md          # 人类可直接调用的厚拆桥段卡
│   ├── 子流程施工卡.md        # BID 内可独立迁移的完整连续子流程
│   └── 子流程索引.jsonl       # 机器可检索的 SF 全量索引
├── book.profile.json       # 单书结构化规则包，仿写/融合/去AI味硬门槛
├── 拆文报告.md             # 人类可读综合报告（Stage 2-6 综合）
├── 情节节点.md             # Stage 2 情节节点清单
├── 写作手法.md             # Stage 4 写作手法分析
└── _meta.json             # 管道元数据 + 结构计数（resume + Phase 7 门控数值依据）
```

**默认产出约定**：上面列出的文件和目录，进入正式拆书后必须全部自动落盘；不存在“可选文件后补”。缺任意 1 项，默认不能进入 `ready-for-write`。

### Few-Shot 对照契约

`_sample_comparison.md` 必须在读完当前原文后、写 `事实与推断台账.md` 前由模型手工落盘。

每本所选样本必须记录：

- `样本名`
- `选择原因`
- `已读文件`，至少包含该样本的 `README.md / 原文.txt / 正反例对照.md`
- `正例锚点`
- `反例锚点`
- `本书对应风险`
- `将影响的正式文件`

主报告完成后必须追加：

- `## 主报告后复核`
- `对照裁决：未滑入反例 / 需要回炉`
- `证据`
- `实际回写文件`

硬规则：

- 只允许使用 `references/examples/` 内置样本
- 不允许使用其他拆书目录、上一本文档、旧 profile、bak 或测试目录替代内置样本
- 只写“已选《幼薇》”而没有具体文件和正反例锚点，视为未使用样本
- `_sample_comparison.md` 不完整时，状态固定为 `blocked-on-assets`

### 原文资产候选池契约

`写作资产/原文资产候选池.md` 必须在 16 张表前建立、表后再回扫更新。固定格式：

```text
C001 | L起-L止 | 锚点：原文短语 | 类别：物件 | 资产名：具体资产名 | 去向：可直接仿写_物件表.md | 状态：已收录 | 理由：为何值得保留
```

硬规则：

- 全部候选都要有可验证原文锚点
- manifest 全部分块必须确认已回扫；允许某块无候选，但要写 `新增候选：无 + 空缺复核`
- `已收录` 候选的资产名或锚点必须真实出现在目标表
- `不收录` 必须写具体排除理由
- 16 类必须逐类确认；无候选的类别写“已扫，原文未发现”，不得凑数
- 必须完成 `物件替换对 / 微动作角色覆盖 / 对白侵占与假道歉 / 安静等待与未归 / 未来公开事件钩子` 五项专项回扫
- 候选数只作非阻断复核提示；发现多少独立资产就登记多少
- 候选池缺失、分块未回扫或候选未核销时，状态固定为 `blocked-on-assets`

### 本书动态信号字典契约

`写作资产/本书动态信号字典.json` 必须在候选池前完成首次全文发现，并在 16 张表后完成回补复扫。

硬规则：

- 固定包含 `人物别名 / 核心物件 / 动作与微动作 / 对白功能信号 / 安静场信号 / 证据载体 / 未来事件 / 关系与秩序变化` 8 个键
- 每条词带原文行号、真实锚点、候选 ID；仅作实体索引时写具体理由
- `首次全文发现 / 表后回扫` 两轮都覆盖 manifest 全部 Chunk
- 新词先回补本书字典，再重扫原文、候选池和目标表
- 连续一轮无新增后才能写 `stabilized: true`
- 单书新词不自动写回全局静态词表

**文件名约定**：`拆文报告.md / 情节节点.md / 写作手法.md / book.profile.json` 由短篇写作链路固定消费，不能改名。分析叙事走 markdown，数字和枚举走 `_meta.json.structure_counts`，结构化规则走 `book.profile.json`。

### 原文覆盖契约

初始化阶段必须额外生成：

- `_source_manifest.json`：记录源文件 SHA1、复制文件 SHA1、无空白字数、总行数、章节标记、固定读取分块、尾部锚点
- `_source_reading_plan.md`：列出全部分块读取命令和 EOF 校验信息

正式产物必须提供可机器校验的覆盖证据：

- `拆文报告.md` 必须含 `### 原文覆盖确认`
- `情节节点.md` 每个节点必须写 `L起-L止` 和 `锚点：原文短语`
- 锚点必须真实存在于对应行范围
- 节点必须覆盖全部读取分块；存在章节标记时还必须覆盖每章
- 最后有效节点必须进入原文最后 10%
- 任一覆盖条件不满足，状态固定为 `blocked-on-source-coverage`，不能生成完成态

BID 贯通另走资产闸门：

- 任一在主报告、桥段资产或 `book.profile.json` 出现的 `BID-xx`，必须直接标注在对应的 `Nxx` 节点行；只写在说明区不算
- 单个节点最多挂 1 个 BID；节点 BID 与主报告、高敏桥、施工卡、profile_source、book.profile 必须双向贯通
- 任一 BID 条件不满足，状态固定为 `blocked-on-assets`

### 事实与推断契约

`事实与推断台账.md` 必须先于 Stage 2 主报告落盘。每条固定写成：

```text
F01 | L起-L止 | 锚点：原文短语 | 类别：主体边界 | 主体：角色 | 动作：原文动作 | 结果：原文结果 | 叙述时点：正文当前位置 | 故事时点：事件实际发生位置 | 时间依据：回指词或顺序证据 | 口径：原文明确 | 禁止越界：不能改写成什么
```

硬规则：

- 类别至少覆盖 `主体边界 / 时间边界 / 证据来源`
- 口径只允许 `原文明确 / 人工推断 / 未知`
- 锚点必须真实存在于对应原文行范围
- 所有事实必须分开记录 `叙述时点 / 故事时点 / 时间依据`；没有回叙时写“与叙述同步”，不能留空
- `拆文报告.md` 必须同时产出 `信息释放顺序 / 故事实际时间线 / 回叙或插叙对照`，并以故事实际时间线约束后续桥段顺序
- `推动 / 策划 / 设计 / 安排 / 搜集证据 / 收束证据 / 操控 / 诱导 / 主动制造` 等高主动性判断，必须在正式产物句末回指 `【原文明确 Fxx】` 或 `【人工推断 Fxx】`
- “选择利用既有条件”与“推动条件形成”必须分开；“收到匿名证据”与“主动搜集证据”必须分开
- `拆文报告.md` 必须用 `原文明确动作 / 叙事意图判断 / 未知边界` 三层写主角能动性；事实谨慎只冻结未知实现，不得抹掉原文支持的借势、选择与策略性
- 台账缺失或高主动性声明无回指，状态固定为 `blocked-on-fact-integrity`

**语义约定**：`样本分级与可学层 / 作者DNA指纹 / 仿写约束_禁写清单 / 同桥段过检规则 / profile_source` 不能只是非空文件，必须是“证据型资产”：

- `样本分级与可学层.md`：必须明确写出 `A类正样本 / B类骨架样本 / C类负样本` 三选一，并拆清：
  - `structure_grade / performance_grade / sentence_grade / terminal_consequence_grade`
  - `正向DNA层 / 仅骨架层 / 反面规则层`
  - 四层不一致时明确写 `分层样本`
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
- `写作手法.md`：至少各有 1 条 `活词 / 句法模板 / 段落节拍 / 反面仿写句`
- `仿写约束_禁写清单.md`：每条禁写项后面都要带“为什么假 / 会把文写坏在哪”
- `同桥段过检规则.md`：每个桥段都要带“原文承重件 / 新稿高风险假点 / 不能丢的东西”
- `写作手法.md`：除了 POV / 对话 / 时间 / 信息控制，还必须补 `开场入口 / 回忆职责 / 关键断场点 / 尾声入口 / 收口落点`
- `写作手法.md`：必须按固定骨架落盘，至少包含 `1.POV策略 / 2.对话手法 / 3.时间操控 / 4.章法硬拆 / 5.章法失效测试 / 6.信息控制 / 7.其他手法 / 8.意象物件追踪 / 9.手法总评与迁移提醒`
- `写作资产/profile_source.md`：必须把模型读完整篇后提出来的原始 profile 材料写清，至少覆盖：
  - `样本分级 / 是否可用于DNA提取 / 原文检测结论 / 原文整体分数 / 原文高风险块 / 分数使用口径 / 可学层 / 禁学层`
  - `高敏层级判断`
  - `题材流派 / 主梗 / 副梗`
  - `作者DNA`
  - `桥段承重件`
  - `禁句 / 禁写法`
  - `开头高信息量信号`
  - `场面资产 / 后果链`
  - `作者站位高危句`
  - `迁移替换资产`
  - 其中 `桥段承重件` 不能只停在“承重件 + 假点”，还必须能映射出：
    - `opening_pattern`
    - `recommended_sequence`
    - `why_order_matters`
    - `fake_signals`
    - `why_original_passes`
  - `高敏桥段识别.md / 作者DNA指纹.md / 同桥段过检规则.md` 不能只写抽象结论，至少要显式出现 `原文：` 证据行
  - 另外有 2 个格式硬要求是脚本直接验的：
    - `开头高信息量信号` 里至少写 3 行独立的 `- 开头信号：`
    - `禁句 / 禁写法` 里至少写 2 行独立的 `- 为什么假：`
  - 另外有 3 组字段硬要求是生成 `book.profile.json` 的直接上游：
    - `场面资产` 使用 `scene_assets.public_explosion / scene_assets.external_order / scene_assets.consequence_chain` 显式标签；`4/4/6`、`3/3/4`、`2/2/3` 仅作按字数档的漏拆复核参考，不得凑数
    - `后果链` 至少补 `感情伤抬升到现实伤的节点 / 秩序回正节点 / 长尾惩罚节点 / 离场 / 换图节点`
    - `作者站位高危句` 至少补 `容易写成作者判词的句型 / 容易写成主题总结的句型 / 容易写成整齐揭露的句型`
    - `迁移替换资产` 使用 `object_substitutes / scene_substitutes / action_substitutes / dialogue_substitutes / role_bias_variants` 显式标签，每类按字数档至少 `4 / 3 / 2`
  - 这两项不能写成合并长句，也不能写成 `为什么假1 / 为什么假2`
- `写作资产/桥段施工卡.md`：必须把原文实际存在且最值钱的桥写成“人类可直接调用”的厚卡，不按字数凑数量，每张卡都覆盖：
  - `桥段名`
  - `一句人话抓手`
  - `桥段角色`
  - `原文位置`
  - `原文现象证据`
  - `原文为什么能过`
  - `为什么不像加工稿`
  - `新稿最容易写假的点`
  - `必须保留的承重件`
  - `不能丢的顺序`
  - `为什么这个顺序不能乱`
  - `后续调用方式`
  - `桥段角色` 使用本书动态归纳的功能标签，不预设掉位、私域旧伤或公开炸场
  - `一句人话抓手` 必须是生活化、可记忆的冲突句；只有权限/秩序/现实后果等抽象词不算
  - 这份文件优先服务写作者直接调用，不承担 json 抽取稳定性的主职责
- `写作资产/子流程施工卡.md + 子流程索引.jsonl`：必须把每个 BID 继续下钻为一个或多个 `SF-*` 完整子流程。每条保留 `进场状态 / 完整动作与反应顺序 / 场面颗粒 / 信息延迟 / 控制权变化 / 情绪顺序 / 场末状态 / 可嵌入位置 / 不兼容条件 / 原文证据`。`SF-*` 不是动作、物件或对白零件，不允许跨条拆散混拼；每个 BID 至少被一条 SF 覆盖，索引必须回指同名施工卡、父 BID 和真实原文。
- `写作资产/交流承压拆解.md`：必须把“人物如何真实发生交流”拆到现场证据层，不得只写“有张力 / 有对视 / 有停顿”。至少包含 `场名 / 原文位置 / 谁先施压 / 压力载体 / 对方被迫改了什么 / 删掉台词是否仍成立 / 为什么不是作者替人物接招 / 仿写最容易写假的点`。其中 `压力载体` 至少从 `肢体 / 物件 / 空间 / 身份 / 节奏 / 外部秩序` 中选 1 项，`对方被迫改了什么` 必须落到 `动作 / 站位 / 物件控制权 / 回答范围 / 身份 / 后果 / 现场秩序`
- `写作资产/冲突载体清单.md`：必须把承重冲突拆成“到底在抢什么现实权力”，不得只写“吵架 / 关系恶化 / 情绪升级”。至少包含 `场名 / 原文位置 / 表层冲突 / 第二层争夺权 / 主载体 / 谁当场失位 / 越界后果 / 如果只保留对白会丢掉什么`。`主载体` 必须从 `dialogue / body / object / space / identity / rhythm` 中至少选 1 项；`第二层争夺权` 必须具体到 `制止权 / 解释权 / 入场权 / 去留决定权 / 物件处置权 / 花钱决定权 / 公开头位`

---

## Stage → 文件映射

| Stage | 名称 | 落地文件 | 主要内容 |
|-------|------|----------|---------|
| 2 | 结构+情节节点 | `事实与推断台账.md` + `拆文报告.md`（故事核/结构/梗概段） + `情节节点.md` | 事实边界 / 故事核 / 4-6 段结构 / 故事梗概 / 情节节点清单 |
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

### 历史目录增量升级协议

旧版本已经拆过的 `拆文库/{书名}/`，如果 skill 新增了必产资产，不允许用 `--force` 删除重建来冒充增量。

固定入口：

```bash
python3 skills/story-short-analyze/scripts/prepare_short_analyze_job.py --upgrade-existing "拆文库/{书名}" --json
```

硬规则：

- `--upgrade-existing` 不删除、不覆盖已有正式产物。
- 脚本刷新 `_required_outputs.json / _parallel_plan.json / _progress.md / _source_reading_plan.md / _execution_prompt.md` 等过程文件，生成 `_upgrade_plan.md` 与 `_finalize_human_review.json`；不覆盖正式 Markdown。
- 缺失的正式 Markdown / JSON 产物只登记到 `_upgrade_plan.md`，不得由脚本写空模板、兜底内容或通用占位。
- 模型必须按 `_upgrade_plan.md` 回读原文、样本、事实台账、节点、写作手法、候选池和对应模板后人工回填。
- `_meta.json.upgrade_status` 在升级后固定为 `pending_content_review`；`missing_files=[]` 也不能直接完成。
- 必须逐项复核当前 first-write contract、逐 BID 六拍情绪贯通和 profile 重生，并在 `_finalize_human_review.json` 记录具体判断、证据与当前正式 Markdown SHA。
- 回填后必须运行 `run_short_analyze_finalize.py`；未通过前不得标记 `ready-for-write`。

---

## Phase 7 门控接入点

Stage 6 内容写完后、`stages_completed[6]` append 前，跑五道门控：

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

### 7.4 全量产物自动落盘校验

默认必须运行：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}"
```

只要出现以下任一情况，就不能进入 `ready-for-write`：

- 少任意一个定义文件
- `_sample_comparison.md` 缺失、没有具体样本文件、没有正反例锚点或没有主报告后复核
- `原文细节库/` 8 类缺任意 1 类
- `写作资产/` 的全量文件缺任意 1 类
- 16 张 `可直接仿写_*.md` 缺任意 1 张
- `拆文报告.md / 写作手法.md / profile_source.md` 缺关键骨架标题
- `_meta.json / book.profile.json` 缺关键字段
- 16 张表的施工层没有引用本表具体条目
- 16 张表多处复用同一句迁移提醒或顺序原因
- 16 张表任一张缺逐行迁移列，或逐行迁移内容为空
- 16 张表有候选未落表，或无候选却未声明“原文未发现”
- `人物偏手表` 与主报告人物完全未对齐
- `原文细节库/` 大量内容仍是统一模板壳句
- `原文细节库/` 多个 `##` 小节五条答案大面积复用，只换标题
- `原文细节库/` 有真实细节却漏记，或无对应细节却未声明“原文未发现”
- `book.profile.json` 虽存在，但 `scene_assets / banned_phrases / author_stance_patterns / must_keep` 等关键资产抽空或抽碎
- `book.profile.json.style_assets` 缺固定键；原文无对应资产时允许空数组
- `book.profile.json.migration_assets` 任一类未达到按原文字数分档的 `4 / 3 / 2` 条唯一短语
- `scene_assets.public_explosion / external_order` 把原文实际存在的事件级动作/后果资产全部压成地点、道具或机构名

### 7.5 仿写资产完整性校验

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
- 高敏桥如果缺 `重大证据前隔开的现实后果 / 尾声入口给了谁 / 为什么不给另一条线 / 人物不同脸证据` 里的任意 2 类，视为未通过
- `写作手法.md` 里如果缺 `开场入口 / 时间线类型 / 回忆职责 / 关键断场点 / 尾声入口 / 收口落点` 里的任意 2 类，视为未通过
- `写作手法.md` 里如果没有按固定骨架落盘，或缺 `章法失效测试 / 手法总评与迁移提醒` 任意 1 节，视为未通过
- 16 张表如果没先按 `事件顺序类 / 物件动作类 / 对白口气类 / 关系秩序类` 判断写法，只是统一说明腔，视为未通过
- 原文细节库如果没先按 `场景 / 物件 / 动作 / 对白 / 关系掉位` 判断证据核心，五条内容大量互相通用，视为未通过

执行提醒：

- Stage 4 开始前，默认先读 `output-templates.md` 的 `写作手法.md 固定骨架`
- 如果实际落盘标题顺序和固定骨架不一致，默认按未通过处理，不接受“意思差不多”的自由发挥
- `写作资产/profile_source.md` 里如果只有几条抽象标签，没有字段化原始材料，视为未通过
- `写作资产/profile_source.md` 里如果 `桥段承重件` 缺 `原文怎么起手 / 不能丢的顺序 / 为什么这个顺序不能乱 / 最容易写假的点 / 原文为什么能过` 里的任意 2 类，视为未通过
- `写作资产/profile_source.md / 桥段施工卡.md / 高敏桥段识别.md` 的每个 BID 都必须包含 `情绪进入点 / 刺痛或受辱拍 / 短暂希望或反抗 / 反刀拍 / 峰值拍 / 场末余痛`；每拍带 `烈度 1-10 + 原文证据`
- `写作资产/profile_source.md` 的 `- 开头信号：` 少于 3 行时进入模型复核，不由脚本直接判错
- `写作资产/profile_source.md` 的 `- 为什么假：` 少于 2 行时进入模型复核，不由脚本直接判错
- `写作资产/profile_source.md` 里如果缺 `## 7. 禁句 / 禁写法 / ## 8. 场面资产 / ## 9. 后果链 / ## 10. 作者站位高危句` 里的任意一节，视为未通过
- `写作资产/profile_source.md` 里如果缺 `scene_assets.public_explosion / scene_assets.external_order / scene_assets.consequence_chain / 感情伤抬升到现实伤的节点 / 秩序回正节点 / 长尾惩罚节点 / 离场 / 换图节点 / 容易写成作者判词的句型 / 容易写成主题总结的句型 / 容易写成整齐揭露的句型` 里的任意关键字段，视为未通过
- `写作资产/profile_source.md` 里如果缺 `## 12. 迁移替换资产` 或 5 类迁移标签，视为未通过
- `写作资产/profile_source.md / 桥段施工卡.md / 高敏桥段识别.md` 如果真实核心桥漏记，或同一桥的功能标签不一致，视为未通过
- `写作资产/桥段施工卡.md` 里如果每张卡缺 `原文现象证据 / 原文为什么能过 / 为什么不像加工稿 / 新稿最容易写假的点 / 必须保留的承重件 / 不能丢的顺序 / 为什么这个顺序不能乱 / 后续调用方式 / 六拍情绪序列` 里的任意 2 项，视为未通过
- `写作资产/桥段施工卡.md` 里如果没有至少 1 张中段承重桥，视为未通过
- 这 5 份里任意 1 份缺“正面可学项 + 负面禁写项”双侧信息，默认仍是 `blocked-on-assets`

### 7.6 生成单书 profile

先由模型补出 `写作资产/profile_source.md`，再调用本地 skill 脚本生成 `book.profile.json`。

`profile_source.md` 不是最终规则包，而是“模型先提、脚本后收”的中间层。
禁止跳过这一层，直接让脚本从全部 Markdown 盲抽。

收口脚本只自动生成 `book.profile.json` 并执行校验，不得修改任何 Markdown。需要单独排查时，才手动调用：

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
- `migration_assets`

其中 `bridge_rules` 里任意命中桥段默认至少要具备：

- `opening_pattern`
- `must_keep`
- `fake_signals`
- `recommended_sequence`
- `emotion_sequence`：固定六拍，每拍含 `beat / content / intensity / source_evidence`

如果桥段只有 `must_keep / must_avoid`，默认仍没拆到可直接支撑同桥段仿写与去 AI 味回修的层级。

validator/finalize 输出的所有 `human_review_items` 必须写入 `_finalize_human_review.json`，逐条标记 `resolved / not_applicable` 并附具体判断和证据。回执缺失、漏项或正式 Markdown SHA 变化时，状态固定为 `blocked-on-assets`。

### 7.7 通过

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
ls 拆文库/{书名}/   # 应有：原文/ 16张可直接仿写表 / 原文细节库/ / 写作资产/ / 拆文报告.md / 情节节点.md / 写作手法.md / book.profile.json / _meta.json
test -f 拆文库/{书名}/写作资产/profile_source.md
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}"
python3 "$CODEX_HOME/skills/story-short-write/scripts/audit_novel_ai_flavor.py" 新稿.md --profile 拆文库/{书名}/book.profile.json --json
/story-short-write 拆文库/{书名}/
# 通过：16张表 + 原文细节库 + 写作资产全包 + `profile_source.md` + `book.profile.json` 齐全，且输出 8000+ 字同题材新短篇，prose 带着源文的对话节奏和画面感
# 失败：写得像填空，或 short-write 读不到关键 markdown / 写作资产
```

---

## 版本约定

- `_meta.json.version` 与本文件 `sync-policy` 联动。
- breaking change（字段重命名 / 类型变更 / 必填变更）必须 bump major version 并同步两侧副本，CI 通过 `scripts/check-shared-files.sh` 拦截单边修改。
- additive change（新增可选字段）可 bump minor，旧字段保持读容忍。
