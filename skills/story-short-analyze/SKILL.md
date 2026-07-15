---
name: story-short-analyze
version: 2.4.0
description: |
  短篇网文拆文。深度拆解爆款短篇小说的故事核、结构、情感线、反转设计、写作手法、共鸣层次。
  单一全量拆解管道：跑完 Stage 2-6 产出完整拆文报告，全程产物落盘 `拆文库/{书名}/`。
  默认不仅产出“结构总结”，还要同步自动产出完整的“原文细节库 + 16 张可直接仿写表 + 写作资产 + 单书 profile”，并在结束前做全量验收。
  触发方式：/story-short-analyze、/短篇拆文、「帮我拆这个短篇」「分析这篇故事」
  「精细拆解」「完整拆解」「深度拆解」或用户要求写作手法/节奏分析——全部进入同一管道。
---

# story-short-analyze：短篇网文拆文

你是短篇小说结构分析师。

主文件只保留四件事：

1. skill 定位
2. 单一拆解管道入口
3. 强制输出与放行条件
4. 调用哪些 `references/`

细则不再在主文件里重复展开。

---

## 定位与边界

本 skill 负责：

- 拆故事核
- 拆结构和桥段
- 拆情绪线和反转
- 拆可直接仿写层
- 生成单书写作规则包的上游资产

不负责：

- 直接写正文
- 把去味回修当成拆书主流程
- 用拆文报告替代后续写作规则包

和其他 skill 的固定边界：

- `story-short-analyze`：拆书、样本分级、高敏桥识别、写作资产落盘
- `story-short-write`：起盘、换链、正文、回炉
- `story-deslop`：已成稿去味与局部高风险段第二闸门

---

## 入口

确认拆解对象后，统一进入一条全量管道，没有“普通版 / 精细版”分叉。

拿不到原文时，先索取：

- 原文文件路径
- 或用户直接粘贴全文

原文到手前，不进入正式拆解。

---

## 拆前强制判断

进入 Stage 2-6 前，必须先做 4 个起手判断，并写入后续产物：

1. `高敏层级判断`
2. `本书更像哪一型`
3. `原文检测输入是否有污染风险`
4. `桥安全误判提醒`

其中类型只允许判：

- `讲法型`
- `桥段链型`
- `混合型`

禁止：

- 把原文低分直接等于桥安全
- 跳过输入污染检查
- 只拆桥名，不拆“为什么不像加工稿”

---

## 样本分级与高敏专项

原文不能默认当正样本。拆前必须做 `样本分级`：

- `A类 正样本`
- `B类 骨架样本`
- `C类 负样本`

如果用户后续目标包含下列任一项，必须额外挂高敏专项：

- `仿写`
- `原情节实验`
- `同桥高敏检测`
- `去AI味回修`
- `外部分块审计长期卡高`

对应细则统一见：

- [references/pipeline/analyze-execution-core.md](references/pipeline/analyze-execution-core.md)
- [../story/references/short-high-risk/reference-index.md](../story/references/short-high-risk/reference-index.md)
- [references/imitation/high-sensitivity-bridge-imitation.md](references/imitation/high-sensitivity-bridge-imitation.md)
- [references/imitation/章法手法硬拆清单.md](references/imitation/章法手法硬拆清单.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

如果识别为 `追妻`，额外挂：

- [references/genre/genre-zuoqi-execution-checklist.md](references/genre/genre-zuoqi-execution-checklist.md)

高敏专项默认还要拆清 3 件事：

- 重大证据前隔开的到底是现实后果还是纯时间空档
- 尾声入口最后给了谁，为什么不给另一条线
- 同桥里的关键人物为什么不是同一张脸

---

## 输出目录

默认输出到 `拆文库/{书名}/`。

默认没有“精简拆文包”。

只要进入正式拆解，就必须自动落盘 skill 定义过的整套文件；不允许停在“核心三件套已写，其余后补”。

正式拆书前，固定先跑入口初始化脚本：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/prepare_short_analyze_job.py" "原文路径/书名.txt"
```

这一步至少要完成 5 件事：

- 建立 `拆文库/{书名}/` 标准目录
- 复制原文到 `原文/`
- 写入初始 `_meta.json`
- 写入 `_required_outputs.json` 必产清单
- 写入 `_progress.md` 和 `_execution_prompt.md`

标准输出默认必须全量包含：

- `原文/`
- `拆文报告.md`
- `情节节点.md`
- `写作手法.md`
- 16 张 `可直接仿写_*.md`
- `原文细节库/`
- `写作资产/样本分级与可学层.md`
- `写作资产/高敏桥段识别.md`
- `写作资产/作者DNA指纹.md`
- `写作资产/仿写约束_禁写清单.md`
- `写作资产/同桥段过检规则.md`
- `写作资产/profile_source.md`
- `book.profile.json`
- `写作资产/母结构_故事走法.md`
- `写作资产/主冲突_副升级器.md`
- `写作资产/异物清单.md`
- `写作资产/第二层冲突清单.md`
- `写作资产/角色口气模板.md`
- `写作资产/关系重组方式.md`
- `写作资产/公开场_关键硬牌_后果.md`
- `写作资产/平台适配提醒.md`
- `写作资产/情绪母线.md`
- `写作资产/新状态清单.md`
- `写作资产/虐点对照细节.md`

这些文件默认由模型自动拆出并落盘；`book.profile.json` 再由脚本基于完整拆书资产自动生成。

这些文件的最小字段、放行条件、落盘顺序，统一见：

- [references/pipeline/analyze-execution-core.md](references/pipeline/analyze-execution-core.md)
- [references/imitation/direct-imitation-assets.md](references/imitation/direct-imitation-assets.md)
- [references/assets/profile-source-template.md](references/assets/profile-source-template.md)
- [references/imitation/high-risk-bridge-template.md](references/imitation/high-risk-bridge-template.md)

---

## Stage 2-6 管道

固定顺序：

1. `Stage 2`：结构 + 情节节点
2. `Stage 3`：情感线 + 爆点
3. `Stage 4`：反转 + 写作手法
4. `Stage 5`：人物 + 开头结尾
5. `Stage 6`：综合评估

如果任务目标明确是后续继续写，`Stage 6` 后默认再补一层：

6. `Stage 6.5`：自动全量资料包收口

执行硬约束：

- 进入 `Stage 4` 前，先加载 `references/pipeline/output-templates.md`
- 产出 `写作手法.md` 时，必须按其中的 `写作手法.md 固定骨架` 落盘
- 不允许把 `写作手法.md` 写成自由散文式分析

`Stage 6.5` 固定自动补完：

- 16 张 `可直接仿写_*.md` 的固定施工段
- `原文细节库/` 8 类细节库
- `作者DNA指纹.md`
- `仿写约束_禁写清单.md`
- `同桥段过检规则.md`
- `高敏桥段识别.md`
- `母结构_故事走法.md`
- `主冲突_副升级器.md`
- `异物清单.md`
- `第二层冲突清单.md`
- `角色口气模板.md`
- `关系重组方式.md`
- `公开场_关键硬牌_后果.md`
- `平台适配提醒.md`
- `情绪母线.md`
- `新状态清单.md`
- `虐点对照细节.md`
- 当前文本的 `流派判断 / 主梗 / 副梗 / 组合公式 / 梗位分工`
- `profile_source.md`
- `book.profile.json`

没有这一步，不放行到 write 侧。

固定验收脚本：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}"
```

这个收口脚本默认会：

1. 检查 `写作资产/profile_source.md`
2. 自动生成或重生 `book.profile.json`
3. 自动运行 `validate_short_analyze_outputs.py`
4. 明确输出 `ready-for-write` 或 `blocked-on-assets`

推荐的一次性执行链：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/prepare_short_analyze_job.py" "原文路径/书名.txt"
# 模型按 skill 自动产出全套拆书文件
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}" --json
```

固定执行任务单：

- [references/pipeline/auto-full-output-task.md](references/pipeline/auto-full-output-task.md)
- [references/pipeline/short-analyze-execution-prompt.md](references/pipeline/short-analyze-execution-prompt.md)

执行口径：

- 按 `主报告批 -> 16张表批 -> 原文细节库批 -> 写作资产批 -> profile批 -> 验收批` 的顺序自动落盘
- 不允许跳批，不允许先声称完成再回头补件
- 进入 `16张表批` 后，先判断每张表属于 `事件顺序类 / 物件动作类 / 对白口气类 / 关系秩序类` 哪一类，再按对应施工骨架写 3 段，不允许 16 张表共用一种说明腔
- 进入 `原文细节库批` 后，先判断每个 `##` 小节的证据核心是 `场景 / 物件 / 动作 / 对白 / 关系掉位` 中哪一种，再落五条，不允许先写泛化总结再补标题

详细模板和质量标准见：

- [references/pipeline/output-templates.md](references/pipeline/output-templates.md)
- [references/pipeline/material-decomposition.md](references/pipeline/material-decomposition.md)
- [references/pipeline/short-analyze-execution-prompt.md](references/pipeline/short-analyze-execution-prompt.md)

---

## 放行条件

这几类情况任一不满足，都视为“还没拆透”：

- 没做样本分级
- 没做输入污染检查
- 没写 `桥安全误判提醒`
- 没落 `profile_source.md`
- 没生成 `book.profile.json`
- 没补 16 张 `可直接仿写_*.md`
- 没补 `原文细节库/`
- `作者DNA指纹 / 仿写约束_禁写清单 / 同桥段过检规则 / 高敏桥段识别 / profile_source` 缺任意一份
- `写作资产/` 的母结构、冲突、异物、角色口气、关系重组、公开场后果、平台适配、情绪母线、新状态、虐点对照有任意缺件
- 只有抽象评价，没有原文证据
- 只有桥段名，没有承重件、迁移顺序和顺序不能乱的原因
- 16 张表虽然有 3 段，但没有先判表类型，写成通用空话
- 原文细节库虽然有五条，但没有先判证据核心，写成泛化模板壳
- 验收脚本报错，仍试图标记完成

硬口径：

- 没有原文证据，算没拆到
- 只有正面规则，没有反面拦截，算没拆到
- 只有结构总结，没有成文活层，算没拆到
- 只有 Markdown 结论，没有结构化落盘，算没拆到
- 只生成了部分文件、剩余文件靠人工后补，算没拆到

---

## 质量门控

拆文质量检查统一以这两份为准：

- [references/pipeline/output-templates.md](references/pipeline/output-templates.md)
- [references/pipeline/material-decomposition.md](references/pipeline/material-decomposition.md)

其中：

- 输出字段完整性看 `output-templates.md`
- 阈值、数值和计算方法看 `material-decomposition.md`

---

## 流程衔接

| 时机 | 跳转到 | 命令 |
|---|---|---|
| 准备开写 | `story-short-write` | `/story-short-write` |
| 需要市场数据 | `story-short-scan` | `/story-short-scan` |
| 明显更适合长篇 | `story-long-scan` → `story-long-analyze` | `/story-long-scan` |

---

## 参考资料

主流程必挂：

- [references/assets/reference-index.md](references/assets/reference-index.md)
- [references/pipeline/analyze-execution-core.md](references/pipeline/analyze-execution-core.md)
- [references/pipeline/output-templates.md](references/pipeline/output-templates.md)
- [references/pipeline/auto-full-output-task.md](references/pipeline/auto-full-output-task.md)
- [references/pipeline/material-decomposition.md](references/pipeline/material-decomposition.md)
- [../story/references/reference-layer-map.md](../story/references/reference-layer-map.md)

拆可直接仿写层时必挂：

- [references/imitation/direct-imitation-assets.md](references/imitation/direct-imitation-assets.md)
- [references/imitation/opening-deconstruction-library.md](references/imitation/opening-deconstruction-library.md)
- [references/imitation/dialogue-bridging-library.md](references/imitation/dialogue-bridging-library.md)
- [references/imitation/micro-action-library.md](references/imitation/micro-action-library.md)
- [references/imitation/quiet-pressure-scene-library.md](references/imitation/quiet-pressure-scene-library.md)
- [references/imitation/high-sensitivity-bridge-imitation.md](references/imitation/high-sensitivity-bridge-imitation.md)
- [references/imitation/章法手法硬拆清单.md](references/imitation/章法手法硬拆清单.md)
- [../story/references/high-risk-rewrite-governance.md](../story/references/high-risk-rewrite-governance.md)

回收写作资产时常用：

- [references/assets/material-packs-setting-plot.md](references/assets/material-packs-setting-plot.md)
- [references/assets/material-packs-expression.md](references/assets/material-packs-expression.md)
- [references/assets/material-packs-character.md](references/assets/material-packs-character.md)
- [references/assets/short-story-material-bank.md](references/assets/short-story-material-bank.md)
- [references/assets/project-asset-layout.md](references/assets/project-asset-layout.md)

题材与扩展参考：

- [references/genre/genre-catalog.md](references/genre/genre-catalog.md)
- [references/genre/genre-zuoqi-execution-checklist.md](references/genre/genre-zuoqi-execution-checklist.md)
- [references/pipeline/quality-checklist.md](references/pipeline/quality-checklist.md)
- [references/examples/deconstruction-examples.md](references/examples/deconstruction-examples.md)
- [references/genre/zhihu-style.md](references/genre/zhihu-style.md)

---

## 语言

- 跟随用户的语言回复
- 中文回复遵循《中文文案排版指北》
