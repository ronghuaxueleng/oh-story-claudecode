# Story Profile Schema

## 目标

- `profile` 不是默认词包。
- `profile` 必须从拆书产物生成。
- 代码只解释 `profile`，不内置题材经验。
- `profile` 分两层：
  - 拆完单书立即生成 `book.profile.json`
  - 写新书前再把多本 `book.profile.json` 合成 `project.profile.json`
- `profile` 的生成不是“纯脚本盲抽”，而是“两段式”：
  - 模型先产 `写作资产/profile_source.md`
  - 脚本再把 `profile_source.md + 拆书资产` 压成 `book.profile.json`

## 生成时机

### 单书阶段

- 时机：`story-short-analyze` 跑完、拆书资产落盘之后立刻生成。
- 步骤：
  - 先由模型生成 `写作资产/profile_source.md`
  - 再由脚本生成 `book.profile.json`
- 目标：把这一本书的 DNA、桥段承重件、禁句、场面资产固化下来。
- 推荐落点：
  - `拆文库/{书名}/写作资产/profile_source.md`
  - `拆文库/{书名}/book.profile.json`

### 组合阶段

- 时机：正式写新书前，已经确定主骨架书和辅助书之后。
- 目标：把多本单书 `profile` 融合成这次项目专用的组合规则包。
- 推荐落点：
  - `项目目录/profiles/{题材或书名}.project.profile.json`

## 输入来源

每个书目录优先读取这些文件：

- `写作资产/样本分级与可学层.md`
- `写作资产/profile_source.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/同桥段过检规则.md`
- `写作资产/仿写约束_禁写清单.md`
- `写作资产/情绪母线.md`
- `写作资产/角色口气模板.md`
- `可直接仿写_公开炸场表.md`
- `可直接仿写_外部秩序表.md`
- `可直接仿写_后果链表.md`
- `可直接仿写_人物偏手表.md`
- `可直接仿写_失控说话表.md`
- `可直接仿写_烂关系漏出表.md`
- `原文细节库/*.md`

## 输出结构

```json
{
  "meta": {
    "name": "<profile名称>",
    "sources": ["..."],
    "generated_at": "<ISO8601时间>"
  },
  "opening_signal_groups": {
    "group_a": ["<来自拆书的开头信号1>", "<来自拆书的开头信号2>"],
    "group_b": ["<来自拆书的开头信号3>"]
  },
  "opening_signal_group_threshold": 6,
  "opening_chain_patterns": {
    "pattern_a": "<来自拆书的翻刀链正则或模式>"
  },
  "opening_chain_threshold": 4,
  "author_stance_patterns": [
    {
      "name": "<模式名>",
      "pattern": "<来自拆书的作者站位高危模式>"
    }
  ],
  "author_stance_threshold": 2,
  "banned_phrases": ["<来自拆书的禁句>"],
  "banned_regex": ["<来自拆书的禁句正则>"],
  "sample_grading": {
    "level": "<A类正样本 / B类骨架样本 / C类负样本>",
    "dna_usable": "<可 / 部分可 / 不可>",
    "summary": "<一句话判断>",
    "source_score_judgement": "<原文检测结论>",
    "source_score_overall": "<原文整体分数>",
    "source_score_high_blocks": ["<原文高风险块1>", "<原文高风险块2>"],
    "source_score_policy": "<这本分数在写前怎么处理>",
    "learnable_layers": ["<可学层1>", "<可学层2>"],
    "forbidden_layers": ["<禁学层1>", "<禁学层2>"],
    "usage_guidance": {
      "写新稿时怎么用这本": "<写法>",
      "融合写作时怎么用这本": "<写法>"
    },
    "misuse_warnings": ["<最容易误用的点>"],
    "final_verdict": {
      "allow_dna": "<是/否>",
      "allow_bridge_merge": "<是/否>",
      "negative_only": "<是/否>",
      "tags": ["<标签>"]
    }
  },
  "bridge_rules": [
    {
      "bridge": "<桥段名>",
      "opening_pattern": ["<原桥段起手件1>", "<原桥段起手件2>"],
      "must_keep": ["<承重件1>", "<承重件2>"],
      "fake_signals": ["<最容易写假的点1>"],
      "recommended_sequence": ["<推荐顺序件1>", "<推荐顺序件2>"],
      "why_order_matters": ["<为什么这个顺序不能乱>"],
      "must_avoid": ["<禁写点1>"],
      "why_original_passes": ["<原文为什么能过的原因>"]
    }
  ],
  "scene_assets": {
    "public_explosion": ["<来自拆书的公开炸场件1>", "<来自拆书的公开炸场件2>"],
    "external_order": ["<来自拆书的外部秩序件1>", "<来自拆书的外部秩序件2>"],
    "consequence_chain": ["<来自拆书的后果链件1>", "<来自拆书的后果链件2>"]
  },
  "style_assets": {
    "opening_hooks": ["<来自拆书的开头钩子资产>"],
    "misdirection": ["<来自拆书的误判资产>"],
    "object_pressure": ["<来自拆书的物件承压资产>"],
    "action_axis": ["<来自拆书的动作主轴资产>"],
    "micro_actions": ["<来自拆书的微动作资产>"],
    "quiet_pressure": ["<来自拆书的安静压迫场资产>"],
    "character_bias": ["<来自拆书的人物偏手资产>"],
    "meltdown_dialogue": ["<来自拆书的失控说话资产>"],
    "rotten_relationship": ["<来自拆书的烂关系漏出资产>"],
    "dialogue_bridges": ["<来自拆书的对白功能/对话衔接资产>"]
  }
}
```

## 字段说明

### `opening_signal_groups`

- 用来检测首屏是否同时塞太多高信息量信号。
- 来源：
  - `同桥段过检规则`
  - `作者DNA指纹`
  - `公开炸场表`

### `opening_chain_patterns`

- 用来检测首屏是否出现“标准翻刀链”。
- 来源：
  - `同桥段过检规则`
  - `情绪母线`

### `author_stance_patterns`

- 用来检测作者站位过高、替角色整理意义。
- 来源：
  - `仿写约束_禁写清单`
  - `作者DNA指纹`

### `banned_phrases` / `banned_regex`

- 直接来自禁写清单里的“禁句型”“最该拦掉的 AI 坏句”。

### `sample_grading`

- 这是样本准入层，不是作者 DNA 本体。
- 用来回答：
  - 这本书能不能提 DNA
  - 这本书能提哪一层
  - 这本书哪些层绝对不能继承
  - 这本原文自己是不是高分样本，高在哪一块，写前该怎么降权处理
- 默认来源：
  - `写作资产/样本分级与可学层.md`
  - `写作资产/profile_source.md` 里的 `0. 样本分级与可学层`
- 写作侧使用口径：
  - `A类正样本`：可学句法、口气、动作落点、桥段承重件
  - `B类骨架样本`：只学骨架、承重件、后果链、场面秩序，不学现成句法壳
  - `C类负样本`：只进禁写规则、反面桥提醒，不进正向融合
- 如果 `source_score_judgement` 明确写了“原文开头桥段高分 / 原文整本高分 / 原文只局部可学”：
  - 必须优先服从这条分数口径
  - 不允许因为题材爽就把它回升成 `A类正样本`
- 融合时默认从严不从松：
  - 多本里只要出现 `C类负样本`，融合包的样本等级就不能继续按纯正样本理解
  - `dna_usable` 只要有一本写 `不可`，融合包默认不能把整批样本都当可提 DNA
- 融合包额外看 `sample_source_buckets.effective_write_level`
  - 这是“实际开稿时该按什么口径写”的字段
  - 只要还有 `positive_dna_sources`，就不该把整包一刀切成纯 `C类负样本`
  - 如果混入 `B/C`，通常把 `effective_write_level` 压到 `B类骨架样本`
  - 只有 `positive_dna_sources` 为空时，才把整包视为不可直接开稿

### `bridge_rules`

- 现在默认按 7 类信息落盘，不再只是推荐项：
  - `opening_pattern`
  - `must_keep`
  - `must_avoid`
  - `fake_signals`
  - `recommended_sequence`
  - `why_order_matters`
  - `why_original_passes`
- 用法不是同权读取，而是有优先级：
  - 起盘和细纲时，先看 `opening_pattern / recommended_sequence`
  - 写场景时，再看 `must_keep`
  - 回修时，先删 `must_avoid / fake_signals`
  - 最后才参考 `why_original_passes`
- 桥段检测命中后，默认要能回答 4 件事：
  - 这一桥原文怎么起手
  - 这一桥为什么不能把顺序写乱
  - 这一桥最容易假在哪
  - 这一桥原文为什么能过检

### `scene_assets`

- 从各类仿写表里提取高频秩序件、公开件、后果件。
- 后续写前检查、写后扫描都可以复用。

### `style_assets`

- 这是把“那 10 张高价值仿写表”压进结构化规则包的层。
- 推荐至少覆盖：
  - `opening_hooks`
  - `misdirection`
  - `object_pressure`
  - `action_axis`
  - `micro_actions`
  - `quiet_pressure`
  - `character_bias`
  - `meltdown_dialogue`
  - `rotten_relationship`
  - `dialogue_bridges`
- 这些字段不是装饰。它们负责让写前约束、写后审计和模型回修都能直接读到：
  - 开头第二推进点
  - 微动作承情
  - 人物偏手
  - 失控说话
  - 烂关系漏出
  - 对话衔接
  这类过去只留在 Markdown 里的隐性规则。

- 进入局部回炉时，`profile` 还负责给 `segment_scores / paragraph_scores / high_risk_segments` 提供解释层。
  也就是说，分段分数不是孤立数字，后面要能顺着 `bridge_rules / scene_assets / style_assets`
  解释“这一片段为什么高、该先补什么、该先删什么”。

## 生成原则

1. 不猜。
2. 先让模型把隐性的“为什么原文能过”提到 `profile_source.md`。
3. 再让脚本只抽文本里明确写出来的词、句、件、桥。
4. 生成脚本可以做归类，但不要凭空新增题材经验。
5. 同一字段允许保留重复来源，后续再去重。
6. 融合 `project.profile.json` 时，只允许在同一本书内部按桥段序号合并，不允许把不同书的 `桥段1 / 桥段2` 直接拼成同一条桥段规则。
7. 一旦补了拆书、补了 `profile_source.md` 或 `同桥段过检规则.md`，就要重生 `project.profile.json`，不要继续沿用旧融合包。

## `profile_source.md` 最低字段

`profile_source.md` 不要求是最终 JSON，但至少要显式补齐这些区块：

- `样本分级与可学层`
- `题材流派`
- `主梗 / 副梗`
- `作者DNA`
- `桥段承重件`
- `禁句 / 禁写法`
- `开头高信息量信号`
- `标准翻刀链`
- `场面资产`
- `后果链`
- `作者站位高危句`
- `那 10 张仿写表对应的 style_assets 原始材料`

没有这些区块时，后续脚本生成的 `book.profile.json` 通常会偏脏，或者漏掉隐性规则。

模板参考：

- `story-short-write/references/integration/profile-source-template.md`

## 调用方式

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --source '拆文库/从昨天的风景散场' \
  --name '从昨天的风景散场' \
  --output '拆文库/从昨天的风景散场/book.profile.json'
```

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --merge-profile '拆文库/从昨天的风景散场/book.profile.json' \
  --merge-profile '拆文库/你的爱扛不住柴米油盐/book.profile.json' \
  --name '追妻火葬场-组合包' \
  --output 'tmp/zuoqi.project.profile.json'
```

如果确实要从多本拆书目录直接试跑，也可以：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" \
  --source '拆文库/从昨天的风景散场' \
  --source '拆文库/你的爱扛不住柴米油盐' \
  --name '追妻火葬场-组合包' \
  --output tmp/zuoqi.profile.json
```
