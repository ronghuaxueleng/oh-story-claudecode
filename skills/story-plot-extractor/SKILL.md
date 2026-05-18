---
name: story-plot-extractor
description: |
  网文情节提取与情节检索。用于两类场景：一类是从本地 TXT 小说中提取可复用情节包；另一类是从 Neo4j 或本地 JSON 情节库中搜索相似情节，给开书、大纲、细纲、卷设计提供可复用的情节参考。
  触发方式：提到 `情节提取`、`情节库`、`搜情节`、`找相似情节`、`plot-extractor`，或直接说「帮我提取这本书的情节」「给我搜一些类似情节」「找点可改编的桥段」
---

# story-plot-extractor：情节提取与情节检索

这个 skill 负责两件事：

1. 从本地 TXT 小说中提取结构化情节包
2. 从现有情节库中检索相似情节，供写作阶段改编复用

## 适用场景

- 用户给了一本本地小说，想提取 plot/character 包
- 用户正在开书，想搜“相近题材的精彩情节”
- 用户在做大纲、卷纲、细纲时，需要一些可改编桥段
- 用户想检查某个情节库/工作区的质量

## 使用原则

- 提取模式：服务于“建立原始素材池”
- 检索模式：服务于“题材对标、精彩桥段改编、大纲设计”
- 汇报时优先讲“这条情节能借什么”，不是只贴原情节
- 如果同名书不存在，退回到“母题检索”：按关键词、冲突、情绪、阶段功能搜相近情节

## 工作流

### 模式一：本地提取

如果用户给的是本地 TXT：

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py extract -- "小说.txt"
```

### 模式二：情节检索

如果用户是“我要写一本书，帮我搜一些类似情节”：

1. 先抽题材母题
2. 把题材母题拆成关键词组
3. 用检索脚本搜情节库
4. 返回“可借情节母线 + 可改编桥段”

#### 书名/梗概直出情节池

如果用户只给了一个书名，或一行梗概，没有明确关键词：

1. 从书名/梗概中抽三类词：
   - 处境词：如流放、抄家、逃荒、废柴、替嫁、和离
   - 驱动词：如情报、系统、日签、预警、机缘、复仇
   - 情绪词：如逆袭、绝境、翻盘、生存、潜伏、悬疑
2. 自动组 2-3 组检索词：
   - 处境 + 驱动
   - 处境 + 情绪
   - 驱动 + 情绪
3. 从结果中整理出一份 `首版情节池`，至少包含：
   - 开局桥段 3-5 条
   - 中段推进 3-5 条
   - 卷尾钩子 2-3 条
   - 长线秘密 2-3 条
4. 汇报时必须说明：
   - 哪些是“结构可借”
   - 哪些只适合借情绪/节奏，不适合借外壳

示例命令：

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py search -- "流放" "情报" "生存" "逆袭"
```

如果用户只有书名/一句话梗概，直接生成 `首版情节池 + 大纲种子`：

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py search-for-outline -- "开局流放，我每天解锁一个情报" \
  --premise "主角被流放边疆，每天获得一条关键情报，靠信息差求生翻盘"
```

默认会额外产出：

- `core_lines`：核心母线
- `volume_one_conflict`：第一卷主冲突
- `thirty_chapter_rhythm`：前 30 章节奏建议

如果只想保留情节池，不要大纲种子：

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py search-for-outline -- "书名" \
  --premise "一句话梗概" \
  --no-outline-seed
```

如果要直接落盘到当前项目：

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py search-for-outline -- "开局流放，我每天解锁一个情报" \
  --premise "主角被流放边疆，每天获得一条关键情报，靠信息差求生翻盘" \
  --save
```

前提：

- 当前项目 `.env` 中已配置可用的 `NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD`
- 或显式传 `--json-library`

### 模式三：插曲检索

如果当前不是缺主干，而是想往大情节里插一个可改编的小桥段：

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py search-interlude -- "误会 试探 反转" \
  --length light \
  --structure-terms 流放 情报 翻盘
```

- `--length light`：单章插曲
- `--length short`：2-3 章短插段
- 允许跨题材借桥段，再按当前书的设定改编

### 模式四：子任务骨架检索

如果不需要完整情节，只想拿一个“功能骨架”给模型现场补全：

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py search-micro-task -- "误会 试探 反转" \
  --length light \
  --structure-terms 流放 情报 翻盘
```

默认返回：

- `function_tags`
- `tension_type`
- `relationship_effect`
- `surface_dependency`
- `position_hint`
- `expected_effect`
- `trigger_condition`
- `insertion_goal`
- `exit_condition`
- `execution_shape`
- `adaptation_hint`

### 模式五：工作区 / 情节库检查

```bash
python3 skills/story-plot-extractor/scripts/plot_extractor_cli.py inspect -- ".plot-extractor-output/书名" --fix-suggestions
```

## 在写作链路中的接入点

这个 skill 最适合插入以下位置：

1. **选题阶段**：搜相近题材的爆点结构
2. **核心设定阶段**：搜“这个金手指/处境”常见怎么展开
3. **卷纲阶段**：搜中段推进、卷尾反转、阶段性危机
4. **细纲阶段**：搜某一章功能对应的桥段，如“开局钩子”“追杀逃亡”“情报预警”

## 汇报格式

当用户要“给我一些情节”时，优先整理成：

- `核心母线`
- `首版情节池`
- `大纲种子`
- `可借桥段`
- `不建议直接照搬的部分`
- `如何改编成你的书`

不要直接把搜索结果原样甩给用户。

## Bundled Resources

- `scripts/`：完整情节提取/检索/检查/导入导出脚本
- `references/output-schema.md`：提取结果字段和质量检查
- `references/json-library-schema.md`：JSON 情节库与交换格式 schema
