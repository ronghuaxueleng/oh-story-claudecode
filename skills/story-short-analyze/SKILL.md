---
name: story-short-analyze
description: |
  短篇网文拆文。深度拆解爆款短篇小说的故事核、结构、情感线、反转设计、写作手法、共鸣层次。
  单一全量拆解管道：跑完 Stage 2-6 产出完整拆文报告，全程产物落盘 `拆文库/{书名}/`。
  默认不仅产出“结构总结”，还要同步自动产出完整的“原文细节库 + 16 张可直接仿写表 + 写作资产 + 单书 profile”，并在结束前做全量验收。
  触发方式：/story-short-analyze、/短篇拆文、「帮我拆这个短篇」「分析这篇故事」
  「精细拆解」「完整拆解」「深度拆解」或用户要求写作手法/节奏分析——全部进入同一管道。
---

# story-short-analyze

这个主文件只负责四件事：

1. 定义本 skill 的目标和边界
2. 规定固定产物与放行条件
3. 规定执行顺序和阶段化加载方式
4. 告诉主会话去读哪些阶段文档与样例

详细方法、模板、few-shot 和质量细则，不再堆在主文件里统一加载。

---

## 1. 目标

本 skill 的目标不是“做一份能过格式检查的分析摘要”，而是产出一套后续能直接用于：

- 仿写
- 融合写作
- 回炉修稿
- 去 AI 味
- 单书规则抽取

的厚拆资料包。

固定口径：

- 默认进入 `厚拆模式`
- 厚拆优先保中段承重桥、人物不同脸、动作权限差、物件回流、旧伤触发器、章法失效测试
- 通过 validator 只是放行底线，不是完成标准
- 任何“合规但压缩化”的结果，都默认要回炉
- `bak` 目录、旧拆书目录、冷启动测试目录都只允许拿来对比厚度与找漏项，不允许把其中内容直接回灌到正式产物

---

## 2. 边界

本 skill 负责：

- 读完原文并建立事实边界
- 拆主报告、节点、写作手法
- 建立 16 张仿写表
- 建立 8 类原文细节库
- 建立写作资产、候选池、动态字典
- 生成 `profile_source.md`
- 生成 `book.profile.json`
- 运行最终收口验收

本 skill 不负责：

- 直接写正文
- 把去味回修当作拆书主流程
- 用拆文报告替代写作规则包

协作边界：

- `story-short-analyze`：拆书、样本分级、高敏桥识别、写作资产落盘
- `story-short-write`：起盘、换链、正文、回炉
- `story-deslop`：已成稿去味与高风险段二次闸门

---

## 3. 固定执行顺序

正式拆书时，只允许按下面顺序推进：

1. 初始化目录与元数据
2. 读完原文全部 Chunk，过原文覆盖闸门
3. 读取 1-2 本内置样本并落 `_sample_comparison.md`
4. `事实与推断台账.md`
5. `拆文报告.md`
6. 回看样本反例区并更新 `_sample_comparison.md`
7. `情节节点.md`
8. `写作手法.md + _meta.json`
9. `本书动态信号字典.json + 原文资产候选池.md`
10. 16 张表，默认按结构/动作 8 表与对白/关系 8 表两大批连续落盘
11. 原文细节库，默认 8 份整批连续落盘
12. 写作资产，默认按常规资产与高敏资产两大批连续落盘
13. `profile_source.md`
14. 生成 `book.profile.json`
15. `run_short_analyze_finalize.py`

硬规则：

- 默认使用 `快速厚拆模式`：原文与样本只完整读取一次，后续依赖 `_sample_comparison.md`、事实台账、节点、候选池和精确原文切片，不重复吞全文
- 大批量落盘后立即做文件齐全、输出截断和现有厚度门槛快检；只对失败批次二分重跑，二分仍失败才降级为双文件模式
- 快速厚拆只减少模型往返和重复回读，不降低 57 文件合同、表格行数、细节卡数、高敏资产厚度或 validator 门槛
- 读完原文后先落过程审计 `_sample_comparison.md`；第一个内容产物必须是 `事实与推断台账.md`
- 禁止先铺一圈空壳，再回头补正文
- 禁止“核心三件套先写完，其余后补”
- 禁止为了平均铺满所有文件，把主报告层压薄
- 禁止任何兜底生成、自动补写、自动扩写、默认事件代填或跨书内容借位；依据不足时直接阻断
- finalize 只允许生成 `book.profile.json` 和执行验证，不允许修改任何 Markdown 正式产物

---

## 4. 阶段化加载

主会话不要一次性吞完整个 skill 体系。

固定读取顺序：

1. 先读本文件
2. 再读 [references/pipeline/staged-execution-index.md](references/pipeline/staged-execution-index.md)
3. 根据当前阶段，只加载对应阶段文档
4. few-shot 样本固定只选 1-2 本，不允许把 3 套样本全文一起吞进主上下文

阶段文档：

- [references/pipeline/stage-00-intake-and-sampling.md](references/pipeline/stage-00-intake-and-sampling.md)
- [references/pipeline/stage-01-main-report-batch.md](references/pipeline/stage-01-main-report-batch.md)
- [references/pipeline/stage-02-ledger-and-tables-batch.md](references/pipeline/stage-02-ledger-and-tables-batch.md)
- [references/pipeline/stage-03-detail-assets-batch.md](references/pipeline/stage-03-detail-assets-batch.md)
- [references/pipeline/stage-04-profile-and-finalize-batch.md](references/pipeline/stage-04-profile-and-finalize-batch.md)
- [references/pipeline/session-manual-execution-protocol.md](references/pipeline/session-manual-execution-protocol.md)

通用模板与契约：

- [references/pipeline/output-templates.md](references/pipeline/output-templates.md)
- [references/pipeline/output-contract.md](references/pipeline/output-contract.md)
- [references/pipeline/quality-checklist.md](references/pipeline/quality-checklist.md)
- [references/pipeline/dynamic-signal-dictionary.md](references/pipeline/dynamic-signal-dictionary.md)
- [references/pipeline/source-asset-coverage-ledger.md](references/pipeline/source-asset-coverage-ledger.md)

---

## 5. few-shot 使用规则

先读：

- [references/examples/INDEX.md](references/examples/INDEX.md)

然后按当前最容易拆坏的失败类型，只选 1-2 本：

- 中段桥被压掉 / 题面预期翻转缺失 / 细节库缩水：优先《幼薇》
- 公权场撞见被压成普通抓奸 / 私域越界不实 / 证据链清算变薄：优先《扫黄扫到了我老公》
- 长期剥夺链被写成背景 / 掉马只剩爽点 / 回门清算只剩控诉：优先《归月学生》

固定原则：

- 样例只拿来防失败，不拿来照抄壳
- 样例越多，主会话越容易压缩输出；默认不超过 2 套
- 原文、正例、反例都属于参考材料，不属于行为规则
- 每本所选样本必须实际读取 `README.md + 相关原文段 + 正反例对照.md`
- 必须落 `_sample_comparison.md`，记录所选文件、正例锚点、反例锚点、本书对应风险和受影响产物
- 写完主报告后必须再回看反例区并记录复核裁决；只声明“已选样本”不算使用样本
- 禁止使用其他拆书目录、旧 profile、bak 或上一本文档替代内置样本

---

## 6. 固定产物

正式拆解后，默认必须全量落盘：

- `原文/`
- `_sample_comparison.md`
- `事实与推断台账.md`
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
- `写作资产/桥段施工卡.md`
- `写作资产/原文资产候选池.md`
- `写作资产/本书动态信号字典.json`
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
- `book.profile.json`

---

## 7. 最少硬约束

无论阶段文档怎么展开，下面这些约束永远不可违背：

1. 没读完 `_source_reading_plan.md` 全部分块，不得进入 Stage 2
2. 没有完成 `_sample_comparison.md`，不得写 `事实与推断台账.md`
3. `事实与推断台账.md` 必须先于其他内容产物落盘，且区分 `叙述时点 / 故事时点 / 时间依据`
4. 高主动性判断必须回指 `Fxx`
5. `拆文报告.md / 情节节点.md / 写作手法.md / profile_source.md` 是第一优先级，不能压薄
6. 16 张表、细节库、写作资产都必须按文件语义写，不许写成统一壳
7. `profile_source.md` 同时服务结构化抽取和单书厚规则包；`桥段施工卡.md` 继续承担更厚的人类施工解释层，但不能把桥规则骨架全甩给施工卡
8. `book.profile.json` 由脚本生成，不与 Markdown 同批手写
9. 收口必须跑：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}" --json
```

---

## 8. 放行条件

任一项不满足，都不算拆完：

- 原文覆盖闸门未过
- `_sample_comparison.md` 缺失、空泛或没有主报告后复核
- 没落 `事实与推断台账.md`
- 主报告层缺件或压缩化
- 16 张表缺件
- 原文细节库缺件
- `写作资产/` 关键文件缺件
- 没落 `profile_source.md`
- 没落 `桥段施工卡.md`
- 没生成 `book.profile.json`
- `run_short_analyze_finalize.py` 未通过
- finalize 修改了任一 Markdown 正式产物

---

## 9. 执行建议

如果你发现结果开始出现这些症状：

- 文件都齐了，但内容明显变薄
- 后段资产只剩摘要句
- `同桥段过检规则.md`、`仿写约束_禁写清单.md`、`情绪母线.md` 明显缩水
- `scene_assets` 被压成一条长串

默认不是“继续给主 prompt 加规则”，而是：

1. 冷启动当前失败批次
2. 只加载当前阶段文档
3. 优先读取 `_sample_comparison.md` 中已缓存的样本锚点；只有裁决证据不足时才重读对应样本切片
4. 先补证据层，再补解释层
5. 根据冷启动失败点修改正式 skill 的文档、validator、生成脚本或测试
6. 只重跑责任批次，再回到正式流程并跑 finalize

补充边界：

- 冷启动目录只用于测试 skill 是否已经修好，不是正式产物来源
- 冷启动跑通后，必须让正式流程自己重新产出一遍；不能靠同步文件把测试目录“搬回”正式目录
- `bak` 只负责对比厚度、定位漏项、验证是否更薄；不参与生成，不参与回填
