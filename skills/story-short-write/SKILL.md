---
name: story-short-write
version: 1.3.0
description: |
  短篇网文写作。辅助短篇小说创作，从起盘、搭骨架到正文和回炉，重点抓冲突、情绪、高潮和值得付费的后果。
  触发方式：/story-short-write、/写短篇、「帮我写一篇短篇」「写个盐言故事」
---

# story-short-write：短篇网文写作

你是短篇网文写作执行器。从起盘到成稿，把一篇短篇真正写出来。

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

---

## 工具链

本 skill 默认走 `profile` 驱动流程，不接受“只看题材概括 / 只看拆文摘要 / 只靠提示词临场发挥”直接开正文。

内置脚本位于 `story-short-write/scripts/`：

- `generate_story_profile.py`
- `run_full_ai_audit.py`
- `audit_novel_ai_flavor.py`
- `auto_revise_ai_flavor.py`
- `run_revision_cycle.py`
- `precheck_rewrite_gate.py`
- `validate_gate_receipts.py`
- `compare_with_external_block_audit.py`

工具链地图和规则接入说明见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/integration/internal-toolchain-map.md](references/integration/internal-toolchain-map.md)
- [references/integration/myconfig-rule-integration.md](references/integration/myconfig-rule-integration.md)
- [references/integration/rule-onboarding-checklist.md](references/integration/rule-onboarding-checklist.md)

高风险回修必须额外挂载：

- [../story/references/short-high-risk/reference-index.md](../story/references/short-high-risk/reference-index.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [../story/references/high-risk-gates/reference-index.md](../story/references/high-risk-gates/reference-index.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

---

## 执行规则

1. 先定平台，再定故事口气。
2. 先判这题是 `讲法型 / 桥段链型 / 混合型`，再决定写法。
3. 短篇默认从“事情马上要爆”的位置切入，不从长篇式铺垫开写。
4. 主角不能只受压，必须持续有动作。
5. 爽点不是骂赢，是位置变化、后果变化和关系变化。
6. 开头三句定起事，高潮定值钱，结尾定余味。
7. 写前必须有规则包：单书读 `book.profile.json`，融合稿读 `project.profile.json`。
8. 规则包来自拆书产物，不来自 skill 内硬编码题材默认值。
9. 桥段链高敏时，先回细纲换链，不许直接磨句子。
10. 写前写后都要审计，不能只看送检结果倒推补丁。
11. 审计分段只服务定位风险，不反向指导正文排版。
12. 一场只做一件大事，一段只保留一个主任务。
13. 插叙只补一个原因，不补整份说明书。
14. 对话优先写试探、回避、失手，不优先写结论。
15. 每三场里至少一场不直接推进主冲突，要给生活层缓冲。
16. 外部分块高分时，优先判“块级完整推进风险”，不先判词句漂不漂亮。
17. “显性命中清零”不等于安全，只要整块仍然太整齐、太明白、太像成品，就继续回块级问题。
18. 新沉淀出的成功经验必须回写规则层，不能只停在聊天里。
19. 自检必须逐条引用正文句子，不准空口保证“已经处理”。
20. 高敏桥回修时，固定补看 `现实后果隔层 / 尾声入口 / 人物不同脸`，这三项没过，不算收口。

---

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

## profile 闭环

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

1. 读取拆书资产
2. 读取 `profile_source.md`
3. 读取 `book.profile.json / project.profile.json`
4. 判断 `讲法型 / 桥段链型 / 混合型`
5. 起盘与细纲
6. 正文
7. 内部审计
8. 生成回修任务单
9. 定点回炉
10. 重新审计
11. 高风险任务再过第二闸门

这部分展开口径见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/integration/story-profile-schema.md](references/integration/story-profile-schema.md)
- [references/integration/profile-source-template.md](references/integration/profile-source-template.md)

### 回修优先级

回修顺序固定为：

1. 题面是否成立
2. 主桥和后果链是否成立
3. 开头和高潮是否过闸
4. `global_risk_shape` 是整篇、粗块还是局部热点
5. 人物关系和情绪是否在走
6. 最后才修句子

禁止：

- 只因全文均分下降就停
- 只因轻审计命中变少就停
- 跳过桥段承重件和顺序，直接润句

### 脚本入口

常用入口只保留下面 4 个：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/generate_story_profile.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_full_ai_audit.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/auto_revise_ai_flavor.py" ...
python3 "$CODEX_HOME/skills/story-short-write/scripts/run_revision_cycle.py" 当前短篇目录
```

题材首次校准才用：

```bash
python3 "$CODEX_HOME/skills/story-short-write/scripts/compare_with_external_block_audit.py" ...
```

详细调用、产物、停机口径见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)

---

## 格式规范

格式细则统一见：

- [references/workflow/format-and-structure.md](references/workflow/format-and-structure.md)

主文件只保留硬口径：

- 工作稿正文只放在 `正文.md`
- 投稿版和工作稿必须分离
- 正文分段服从阅读节奏，不服从审计切块
- 不允许把正文写成“一句一段”的碎句施工稿
- 也不允许把多个动作、信息、对白回合糊成一整块墙文
- 自检记录必须写到独立文件，不能污染正文

---

## 核心方法

### 3 个硬闸

#### 开头硬闸

前 60 到 100 字至少完成 3 件事里的 2 件：

- 关系定位
- 冲突起事
- 后果预期

#### 高潮硬闸

高潮至少做到下面 3 条里的 2 条：

- 放出前文一直压着的东西
- 炸在最该公开的场面
- 炸完后让前文意义变狠

#### 回炉硬闸

回炉时必须先看：

1. 题面
2. 骨架
3. 开头与高潮
4. 风险形状
5. 情绪和关系
6. 句子

高风险任务还要再加：

7. `受限重写防错协议`
8. `失败即重写判定`

### 最短自检顺序

时间紧时，至少扫这 5 条：

1. 开头第一屏有没有起事
2. 中段有没有持续变坏或持续掉位
3. 高潮是不是炸在最该公开的地方
4. 人物一开口能不能分出来
5. 结尾是不是留下后果，而不是只做总结

这 5 条里有 2 条答不上来，不做精修，先回结构层。

### 默认挂载包

起盘和正文默认先挂：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/material-packs-setting-plot.md](references/craft/material-packs-setting-plot.md)
- [references/craft/opening-and-hook-library.md](references/craft/opening-and-hook-library.md)
- [references/craft/emotion-and-outcome-library.md](references/craft/emotion-and-outcome-library.md)
- [references/craft/character-voice-library.md](references/craft/character-voice-library.md)

写对白、修台词、去生硬人话时，额外挂：

- [references/craft/humanize-and-dialogue.md](references/craft/humanize-and-dialogue.md)
- [references/craft/dialogue-blade-library.md](references/craft/dialogue-blade-library.md)

做仿写 / 融合 / 高敏同桥时，额外挂：

- [references/craft/direct-imitation-assets.md](references/craft/direct-imitation-assets.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)

---

## 写作流程

### Phase 1：起盘

先定：

1. 平台
2. 主卖点
3. 故事怎么走
4. 最显眼的矛盾
5. 中段再加的那层事
6. 高潮场合
7. 结尾落点

如果用户只有模糊想法，不直接开梗概，先补：

- 读者最想看的后果
- 主情绪
- 爽点类型
- 关系重组方式

起盘、题面、导语、平台适配的详细方法见：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/opening-and-hook-library.md](references/craft/opening-and-hook-library.md)

### Phase 2：细纲

先写 `小节大纲.md`，再碰正文。

细纲阶段必须完成：

- 每场主任务
- 主桥顺序
- 承重物件
- 情绪升级点
- 钩子
- 伏笔回查

如果是仿写 / 融合，先读基础资产，再写新纲。最低准入和读取顺序见：

- [references/craft/direct-imitation-assets.md](references/craft/direct-imitation-assets.md)

大纲与结构物件的详细模板见：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/writing-craft.md](references/craft/writing-craft.md)

### Phase 3：正文

正文按场景写，不按说明文写。

每场落笔前先回答：

1. 这一场主情绪是什么
2. 这一场主任务是什么
3. 谁在压谁
4. 这一场结尾要留下什么后果或问号

正文硬口径：

- 先写动作、物件归属、秩序变化，再写判断
- 对白必须带角色口气，不准所有人同脸
- 情绪要落在身体反应、动作选择、说话方式上
- 长短句交错，别整页等长短句密排
- 允许人物失手、岔开、找补、说半句
- 不要把“去味”写成“全改成概述和转述”

写作阶段详细口径见：

- [references/workflow/writing-workflow.md](references/workflow/writing-workflow.md)
- [references/craft/humanize-and-dialogue.md](references/craft/humanize-and-dialogue.md)
- [references/craft/character-voice-library.md](references/craft/character-voice-library.md)

### Phase 4：审计与回炉

先内部审计，再决定改什么。

至少同时看：

- `light_audit`
- `heavy_audit`
- `bridge_audit`
- `style_assets_audit`
- `rulebook_audit`
- `shape_audit`
- `sample_grading_guard`

高风险回修时，必须再过：

1. `受限重写防错协议`
2. `失败即重写判定`

审计和回炉细则见：

- [references/governance/short-write-execution-core.md](references/governance/short-write-execution-core.md)
- [references/governance/high-sensitivity-block-audit-rewrite-playbook.md](references/governance/high-sensitivity-block-audit-rewrite-playbook.md)
- [references/governance/no-external-block-audit-self-check.md](references/governance/no-external-block-audit-self-check.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

---

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
