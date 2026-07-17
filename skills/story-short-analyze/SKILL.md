---
name: story-short-analyze
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

默认进入 `厚拆模式`：

- 目标不是产出“刚好能过验收的压缩摘要”，而是尽可能产出后续能直接拿去仿写、融合、回修的可用资料包
- 厚拆不等于平均拉长所有文件，而是优先保留最值钱的层：中段承重桥、人物口气差、动作权限差、物件回流、旧伤触发器、章法失效测试
- 如果原文本身有这些层，默认宁可多保留，不要先压短
- 只有在原文确实没有对应资产时，才允许写薄；不能因为想省篇幅，主动把高价值中段桥和人脸差删掉
- 任何“合规但压缩化”的结果，都不视为理想完成态

固定执行优先级：

- `写手可调用性` 高于 `格式好看`
- `不伪精确` 高于 `把判断写满`
- `最值钱的桥和人物层保住` 高于 `平均铺满所有文件`
- `通过 validator` 是放行底线，不是最高目标；如果结果更像“过验收”而不像“给人直接拿去写”，默认仍算没拆透
- 16 张表不仅要有原文资产，还要逐行给出迁移提醒、可替换件或换壳写法；把迁移层统一塞到表后模板段，不算完整
- `人物偏手表` 必须同时保留事件级偏手和角色级稳定偏手，不能让单一核心人物占满多数行、把外部秩序角色漏掉
- `book.profile.json` 必须把原文 style assets 与迁移替换资产分开保存，不能用房卡、工牌等换壳词污染原文资产桶
- 如果表格或字段写法会把结果推向“机器友好但人难用”，允许优先写成更适合人的版本，再补抽取锚点；不允许反过来为了抽取稳定，把人类说明层压扁

拿不到原文时，先索取：

- 原文文件路径
- 或用户直接粘贴全文

原文到手前，不进入正式拆解。

### 原文读取覆盖闸门

`原文到手` 不等于 `原文已读完`。初始化后必须先读 `_source_reading_plan.md`，按全部 Chunk 读到 `_source_manifest.json.line_count` 记录的最后一行，才允许进入 Stage 2。

硬规则：

- 禁止把一次有行数或输出上限的 `sed / head / open` 结果当成全文
- `拆文报告.md` 必须先写 `### 原文覆盖确认`
- `情节节点.md` 每个 `N` 节点必须带 `L起-L止` 和 `锚点：原文短语`
- 节点锚点必须真实存在于对应原文行范围，并覆盖全部自动分块；有章节标记时还要覆盖每章
- 最后有效节点必须进入原文最后 10%
- 覆盖闸门未通过时，收口状态固定为 `blocked-on-source-coverage`

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
- 没跑检测却把人工阅读判断伪装成实测结果

风险口径硬规则：

- 只有在你 **实际跑过** 对应检测脚本、拿到结果时，才能写具体数值、分段结果、最高块判断
- 没跑检测时，一律写 `未测` / `未知` / `人工判断：...`
- 禁止把人工阅读写成像脚本结论的伪定量句，例如 `中低风险 / 中高风险 / 最高片段为...` 但不标 `人工判断`
- 如果只能人工判断，必须同时补一句“为什么这样判断”，不能只给结论不给依据

---

## 样本分级与高敏专项

原文不能默认当正样本。拆前必须做 `样本分级`，但 A/B/C 只作整书摘要，不得代替分层判断：

- `A类 正样本`
- `B类 骨架样本`
- `C类 负样本`

同时固定给出：

- `structure_grade`：结构与桥段层
- `performance_grade`：人物表演、口气与动作层
- `sentence_grade`：句法与叙述层
- `terminal_consequence_grade`：终局清算与后果层

四层分别使用 `A / B / C`。只要四层不一致，必须明确写成“分层样本”，禁止用一个整书标签抹平可学层与禁学层。

同时固定写 `正向DNA层 / 仅骨架层 / 反面规则层`。下游按四层 grade 和这三项消费；整书 B 不再自动等于“所有句法都不可学”。

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

内置 few-shot 样本：

- [references/examples/INDEX.md](references/examples/INDEX.md)
- [references/examples/yuwei/README.md](references/examples/yuwei/README.md)
- [references/examples/yuwei/幼薇原文.txt](references/examples/yuwei/幼薇原文.txt)
- [references/examples/yuwei/正反例对照.md](references/examples/yuwei/正反例对照.md)
- [references/examples/saohuang/README.md](references/examples/saohuang/README.md)
- [references/examples/saohuang/扫黄扫到了我老公原文.txt](references/examples/saohuang/扫黄扫到了我老公原文.txt)
- [references/examples/saohuang/正反例对照.md](references/examples/saohuang/正反例对照.md)
- [references/examples/guiyue/README.md](references/examples/guiyue/README.md)
- [references/examples/guiyue/归月学生原文.txt](references/examples/guiyue/归月学生原文.txt)
- [references/examples/guiyue/正反例对照.md](references/examples/guiyue/正反例对照.md)

使用原则：

- 先读 [references/examples/INDEX.md](references/examples/INDEX.md)，按失败类型和题材壳选样本，不要无差别吞三本样本全文
- 《幼薇》不是题材模板，而是“厚拆应该怎么保资产”的样本。
- 优先学习它的中段承重桥保留方式、题面预期翻转写法、细节库卡数标准和人物不同脸拆法。
- 《扫黄扫到了我老公》不是抓奸模板，而是“公权场撞见 + 私域越界 + 证据链清算”该怎么厚拆的样本。
- 《归月学生》不是古言换亲模板，而是“长期小剥夺 + 婚嫁大剥夺 + 身份翻盘 + 回门清算”该怎么厚拆的样本。
- 任何新结果如果更像《幼薇》反例，不像正例，默认先回炉，不直接放行。

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

初始化硬规则：

- 初始化脚本只建立目录、复制原文和写任务元数据
- 不允许把 `桥1 / 桥段卡1 / 原文： / 易假点：` 等空骨架预填进正式产物
- 正式 Markdown 必须由执行模型一次写成完整有效版本，不允许向初始化占位壳追加正文

标准输出默认必须全量包含：

- `原文/`
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

其中：

- `profile_source.md`：优先服务脚本抽取，负责稳定生成 `book.profile.json`
- `桥段施工卡.md`：优先服务人直接拿去写，负责保留“为什么原文能过 / 为什么不像加工稿 / 新稿最容易写假的点 / 迁移时怎么保顺序”

硬口径：

- 不允许再把“人读厚拆解释层”和“json 抽取层”全塞进 `profile_source.md` 一份文件里指望两边都做好
- `profile_source.md` 可以结构化，但不能只剩抽象标签
- `profile_source.md` 固定增加 `## 12. 迁移替换资产`，生成 `book.profile.json.migration_assets`
- `桥段施工卡.md` 必须比 `profile_source.md` 更厚；按篇幅可用 `5 / 4 / 3` 张作为漏拆复核参考，但桥段数服从原文，不得为达档位强造
- `原文细节库/` 8 类文件的 `5 / 4 / 3` 张卡不是软建议；validator 默认按篇幅硬卡，不再接受“别的文件写厚了，所以这里可省”
- `高敏桥段识别.md` 不得只保头尾最亮桥；只要 `情节节点.md` 标出了 3 条及以上 `BID`，默认必须显式保留至少 1 条中段承重桥
- `拆文报告.md` 的 `题面拆解` 不得只写题材摘要；固定补 `读者最先以为` 与 `后面哪一步改写了这个预期`
- `原文资产候选池.md` 必须在 16 张表前按全部 Chunk 建池，表完成后再回扫一次；数量只作复核提示，不得为了达到固定条数编造资产
- `本书动态信号字典.json` 必须先于候选池完成首次全文发现，16 张表后再回补并复扫全部 Chunk；之后还要做两轮独立漏项审计。`stabilized` 由 validator 根据两轮审计的全量 Chunk 覆盖、零新增和状态指纹计算，不接受模型自行声明；单书新词不得直接污染全局词表

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

- 进入 `Stage 2` 前，必须先落 `事实与推断台账.md`；它是后续主体、因果、时间和动机判断的事实底座，不是附录
- `事实与推断台账.md` 每条必须写 `F序号 / L起-L止 / 原文锚点 / 类别 / 主体 / 动作 / 结果 / 叙述时点 / 故事时点 / 时间依据 / 口径 / 禁止越界`
- 台账类别至少覆盖 `主体边界 / 时间边界 / 证据来源`；口径只允许 `原文明确 / 人工推断 / 未知`
- `叙述时点` 记录信息在正文哪里被讲出，`故事时点` 记录事件实际发生在故事链的哪里；出现 `那次 / 当时 / 此前 / 后来 / 多年前 / 第二天` 等回指词时，必须写明它指向哪段原文，禁止按当前行号直接顺排
- 正式产物出现 `推动 / 策划 / 设计 / 安排 / 搜集证据 / 收束证据 / 操控 / 诱导 / 主动制造` 等高主动性判断时，句末必须标 `【原文明确 Fxx】` 或 `【人工推断 Fxx】`
- 禁止把“角色选择利用既有条件”改写成“角色推动条件形成”，禁止把“收到匿名证据”改写成“角色主动搜集证据”
- 事实边界不得反向磨平人物：`拆文报告.md` 必须分开写 `原文明确动作 / 叙事意图判断 / 未知边界`，保留原文支持的借势、选择和策略性，只冻结未知执行细节
- 进入 `Stage 4` 前，先加载 `references/pipeline/output-templates.md`
- 产出 `写作手法.md` 时，必须按其中的 `写作手法.md 固定骨架` 落盘
- 不允许把 `写作手法.md` 写成自由散文式分析
- 全流程默认按 `厚拆模式` 执行；不能一边说要做后续写作资料包，一边只产出压缩版摘要
- 正式进入 `16张表批` 前，`拆文报告.md / 情节节点.md / 写作手法.md` 必须先过“厚拆主报告闸门”；不允许用“先把全套文件铺出来，回头再补厚”的方式跳过主报告深拆
- `拆文报告.md` 不允许只保留“样本分级 + 高敏桥 + 题面 + 梗概 + 结构划分”的合规骨架；固定还必须补齐：
  - `#### 1. 脚本硬筛`
  - `#### 2. 规则拆层判断`
  - `#### 4. 可学层 / 禁学层`
  - `#### 5. 后续调用方式`
  - `### 叙事时间线`
  - `#### 信息释放顺序`
  - `#### 故事实际时间线`
  - `#### 回叙 / 插叙对照`
  - `### 故事核`
- `拆文报告.md` 的 `结构划分` 不能只写 4-6 条概括式分段；固定还要显式写出 `字数范围 / 占比 / 功能 / 对应节`
- `情节节点.md` 不能只停在“梗概式大节点表”；可用分档阈值与 `ceil(原文字数 / 400)` 的较大值作漏拆复核参考，但不是硬最低值。节点数服从独立事件和状态变化，validator 只能提示，不得逼模型凑节点
- `情节节点.md` 的数量达标不代表覆盖全文；每个节点必须带可校验行号与锚点，并同时写 `类型 / 情绪 / 涉及 / 状态变化 / 因果 / 故事时序`。节点仍按信息释放顺序列出，但 `故事时序` 必须标明真实发生位置，不能把回叙位置当发生时间
- 原文存在独立中段承重桥时，`情节节点.md` 必须显式保留并分配 BID；原文确实没有时允许声明“原文未发现”，不得为满足结构模板强造
- 原文如果确实存在已宣布但未发生的公开事件、证据上桌前等待或终局预热，`情节节点.md` 必须保留；原文没有时不得强造“终局前夜”
- `写作手法.md` 每个核心节不能只写 1-2 句总括；至少要把“谁怎么说话 / 为什么这样成立 / 换成什么会发假”拆出来，尤其 `对话手法` 必须落到人物嘴型或口气差
- `写作手法.md` 还必须各给至少 1 条 `活词 / 句法模板 / 段落节拍 / 反面仿写句`，不能只拆结构功能、不拆句子怎么活
- 如果原文存在“办公室冲突 / 公开见血 / 病情暗示 / 搬出家门 / 物件争位 / 私域驱逐”这类中段承压桥，默认优先保留到 `拆文报告.md`、`情节节点.md`、`高敏桥段识别.md`；不能因为导语桥和终局桥更亮，就把中段承重桥压没
- 核心桥必须从本书候选池和事实台账动态识别；每座承重桥分配唯一 `BID-01` 格式编号。凡在 `情节节点.md` 标为承重桥的 `BID`，必须贯通 `拆文报告.md / 对应仿写表 / 高敏桥段识别.md / 桥段施工卡.md / profile_source.md / book.profile.json`，不使用某本书的固定名词触发
- `人物分析` 不能把主角默认拆成纯受害者脸；如果原文里主角同时存在 `借影 / 借势 / 利用关系 / 反向利用错位婚姻`，必须显式拆出来，不允许被“更可共情”写法抹平

`Stage 6.5` 固定自动补完：

- 16 张 `可直接仿写_*.md` 的固定施工段
- 16 张表逐行迁移列与表型专属字段；候选池有该类资产时全部核销，原文确实没有时明确写“原文未发现”
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
- `桥段施工卡.md`
- `book.profile.json`

其中 `profile_source.md` 不允许只停在桥段层，固定还必须补齐生成 `book.profile.json` 的专用章节：

- `## 7. 禁句 / 禁写法`
- `## 8. 场面资产`
- `## 9. 后果链`
- `## 10. 作者站位高危句`
- `## 11. style_assets 原始材料`
- `## 12. 迁移替换资产`

这些章节不是附录，是 `generate_story_profile.py` 的直接上游。
缺任意一节，常见后果是：

- `banned_phrases` 为空
- `scene_assets` 为空
- `author_stance_patterns` 为空
- 收口阶段 `blocked-on-assets`

没有这一步，不放行到 write 侧。

`桥段施工卡.md` 固定承担另一层工作：

- 把本书实际存在且最值钱的桥段写成“人类可直接调用”的施工卡；数量服从原文，不按字数强凑
- 每张卡至少显式补：
  - `桥段名`
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
- `桥段角色` 使用本书自己的功能标签，例如“首次规则展示 / 认知翻转 / 证据兑现 / 关系决断”；不得强制所有题材都具备掉位、私域旧伤或公开炸场
- 这份文件优先服务写作者，不是抽 json 的地方；允许解释更厚，但不允许空泛总结

固定验收脚本：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}"
```

这个收口脚本默认会：

1. 检查 `写作资产/profile_source.md`
2. 自动生成或重生 `book.profile.json`
3. 自动运行 `validate_short_analyze_outputs.py`
4. 明确输出 `ready-for-write` 或 `blocked-on-assets`

推荐的完整执行链：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/prepare_short_analyze_job.py" "原文路径/书名.txt"
# 模型按 skill 分微批落盘全套拆书文件，每次最多 2 个正式文件
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}" --json
```

固定执行任务单：

- [references/pipeline/auto-full-output-task.md](references/pipeline/auto-full-output-task.md)
- [references/pipeline/short-analyze-execution-prompt.md](references/pipeline/short-analyze-execution-prompt.md)

执行口径：

- 全流程固定采用 `模型主导、脚本辅助`：脚本只负责初始化、抽取、格式与一致性检查，不得替代模型阅读原文、判断时间回指、人物口气、标题边界和羞辱机制
- 每个微批完成后，模型必须立即重读该批引用的原文范围，执行 `事实复核 -> 时间复核 -> 人话复核 -> 漏项复核`；发现问题就在当前微批回写并重检，禁止脚本通过后自动一路跑到底
- `脚本通过` 只表示机械条件满足，不表示语义正确。模型必须读取脚本输出并人工裁决；有高风险歧义时先在当前批记录 `未知 / 两种解释`，不得为了继续执行强行选一边
- validator 中由关键词触发的时间回指、能动性、羞辱机制、人话程度、人物口气和旧事关系检查只能写入非阻断复核提示，不得直接判错；只有字段缺失、行号越界、锚点不实、Fxx不存在、引用口径不一致等机械问题可以硬阻断
- `profile_source.md` 中模型显式选择的原文资产优先级高于脚本兜底抽取；生成器不得因资产含“不是 / 为什么 / 因为”等语义词再次删掉，只能做长度、空值、Markdown污染等结构清洗
- 用户要求过程介入时，在 `事实台账 / 主报告 / profile生成后 / finalize前` 四个停靠点展示当前判断并等待确认；用户未要求停靠时，由模型自行完成同样的人工判读，不得省略
- 全量产物目标不变，但禁止把几十个文件当成一次生成任务。按 `主报告微批 -> 字典与候选池微批 -> 16张表微批 -> 原文细节库微批 -> 写作资产微批 -> profile微批 -> 验收` 顺序落盘
- 每个微批最多写 `2` 个正式文件；`book.profile.json` 由脚本单独生成，不与 Markdown 同批
- 每写完一个文件立即做该文件局部自检，再写同微批的第二个文件；禁止先在内部规划整批内容、最后集中落盘
- 首个正式文件必须是 `事实与推断台账.md`；读完原文后不得继续长时间规划整套文件
- 微批通过后直接前进，不运行全量 validator；全量 `finalize` 只在所有文件齐备后运行一次，避免“生成一轮、全量修一轮”的补丁循环
- 不允许跳批，不允许先声称完成再回头补件
- 主报告微批固定拆成：`事实台账`、`拆文报告`、`情节节点`、`写作手法 + _meta`，不能把四份内容同时憋在一个生成动作里
- 主报告是全流程第一优先级；宁可后面某些资产微批暂未展开，也不允许先把 `拆文报告.md / 情节节点.md / 写作手法.md` 写成“合规但压缩”的薄版
- 如果 token 或篇幅出现压力，优先保住 `拆文报告.md / 情节节点.md / 写作手法.md / profile_source.md` 的厚拆层，再去扩 16 张表和细节库；不允许因为想平均铺满所有文件，反过来把主报告写薄
- 如果 token 或篇幅出现压力，不允许拿“先过 validator”当收缩理由；当前 validator 已把细节库卡数、题面预期翻转、中段承重桥纳入硬门槛
- 16 张表固定拆成 8 个微批，每批 2 张；写下一微批前先清空上一批的说明句式，不允许 16 张表共用一种说明腔
- 每张表独立判断属于 `事件顺序类 / 物件动作类 / 对白口气类 / 关系秩序类` 哪一类，再按对应施工骨架写 3 段
- 进入 `16张表批` 前，必须先读 [references/pipeline/dynamic-signal-dictionary.md](references/pipeline/dynamic-signal-dictionary.md) 和 [references/pipeline/source-asset-coverage-ledger.md](references/pipeline/source-asset-coverage-ledger.md)，先落盘动态字典首轮，再建立候选池
- 16 张表写完后必须先回补动态字典，再按 `_source_manifest.json.chunks` 重扫全文；新信号先写字典，再追加候选池和目标表。之后从“找漏项”而不是“证明已完成”的立场再做两轮独立审计，两轮都覆盖全部 Chunk、都无新增且状态指纹一致，validator 才计算为稳定
- 16 张表不能只靠行数过关；语义列必须与表名匹配：人物偏手表写 `角色 + 稳定偏手`，误判表写 `先误判了什么 + 从哪开始翻`，安静压迫场表写 `场面压力来源 / 谁没说话 / 环境音 / 未说破结果`，烂关系漏出表写 `具体漏出件`
- 16 张表必须显式包含原文证据列与逐行迁移列；不允许机械统一成 `资产 / 原文位置 / 原文证据 / 原文功能`
- 表格超过 5 条资产行时必须标 `核心 / 次级索引`：核心 2-5 条，施工层优先调用核心。提示词覆盖只负责“有交代”，不再自动升级为核心资产
- `对白功能表 / 对话衔接表 / 失控说话表 / 微动作表` 必须分开保存 `原文短句或原文动作` 与 `功能归纳`；原文存在高价值短句时不得只留下抽象功能标签
- 候选池里标记 `已收录` 的每一条都必须能在目标表找到；某类为零时必须在候选池和目标表明确写“已扫，原文未发现”
- 每行迁移列必须非空，原文资产与换壳替代件必须分栏
- 16 张表的 `可直接借的承重结构 / 迁移顺序提醒 / 为什么这个顺序不能乱` 每段至少写 2 条可施工说明；只有一段概括句视为压缩化
- 16 张表的 3 段施工层，不仅要“像在点名”，而且要直接复用表格里写出的条目名；如果施工层只写概括、不写表内条目原名，默认高概率过不了验收
- 如果某张表存在 `更适合写手直接调用的语义分组` 与 `更适合验收脚本匹配的机械分组` 冲突，优先保留语义分组，再补最少量字段映射；不允许为了过验收，把整张表改写成只有机器好读的壳
- 原文细节库固定拆成 4 个微批，每批 2 个文件；每个文件先判断各 `##` 小节的证据核心是 `场景 / 物件 / 动作 / 对白 / 关系掉位` 中哪一种，再落五条
- 8 类细节库可按篇幅用每类 `5 / 4 / 3` 张作漏拆复核参考；实际数量服从原文，允许明确写“原文未发现”，不得为达档位重复同一细节或编造新卡
- 收口前固定核对候选池五项专项回扫：`物件替换对 / 微动作角色覆盖 / 对白侵占与假道歉 / 安静等待与未归 / 未来公开事件钩子`
- 写作资产每个微批最多 2 个文件，按“结构资产 / 人物口气 / 高敏规则 / profile 上游”分组；不得一次生成整个 `写作资产/`
- 进入 `profile微批` 后，先单独写 `profile_source.md`，局部验收通过后再运行生成器；桥段卡必须显式补 `承重件`，否则 `book.profile.json` 的 `bridge_rules.must_keep` 会空
- 进入 `profile批` 后，`profile_source.md` 优先保住抽取稳定性，不要为了“写得像报告”把字段冲散；更厚的人类说明层写进 `桥段施工卡.md`
- `profile_source.md` 还必须显式补下列可抽取标签，否则 `story_guardrails` 无法成型：
  - `人物不同脸证据`
  - `谁先解释谁先压场`
  - `不同角色的动作权限差`
  - `重大证据前隔开的现实后果`
  - `后果回灌方式`
  - `尾声入口归属`
  - `不给另一条线的原因`
- `profile_source.md` 的 `## 7-10` 还必须至少补出这些键，`## 11` 按原文短语资产纯度规则填写，`## 12` 单独存迁移替换件，否则 `book.profile.json` 经常会空桶或把原文件与换壳件混在一起：
  - `## 7. 禁句 / 禁写法`：逐条写 `- 为什么假：`；两条只作复核参考，不得凑数
  - `## 8. 场面资产`：显式使用 `scene_assets.public_explosion / scene_assets.external_order / scene_assets.consequence_chain` 三个标签；8000 字以上分别至少 `4 / 4 / 6` 条，5000-7999 字至少 `3 / 3 / 4` 条，5000 字以下至少 `2 / 2 / 3` 条
  - `## 9. 后果链`：至少 1 组 `感情伤抬升到现实伤的节点 / 秩序回正节点 / 长尾惩罚节点 / 离场 / 换图节点`
  - `## 10. 作者站位高危句`：至少 1 组 `容易写成作者判词的句型 / 容易写成主题总结的句型 / 容易写成整齐揭露的句型`
- `book.profile.json.style_assets` 固定检查 10 个键存在：`opening_hooks / misdirection / object_pressure / action_axis / micro_actions / quiet_pressure / character_bias / meltdown_dialogue / rotten_relationship / dialogue_bridges`；原文不存在的类别允许空数组，不得用换壳词凑数
- `book.profile.json.style_assets` 还必须通过纯度检查：只保留能在原文中逐字找到的短语型资产，不得混入 `如果 / 为什么 / 读者 / 迁移 / 顺序 / 不能 / 保证` 等施工说明，不得含 Markdown 标记；分析性归纳单独进入 `derived_patterns`
- `character_bias / dialogue_bridges` 属于关系句和接话句资产，允许保留 32 字以内的完整逗号句；禁止为追求“短词纯度”把“谁打你，你就打回去”切成两个残片
- `scene_assets` 是事件级资产，不是十字以内的短词桶；必须保留完整的“主体 + 动作 + 对象/场面 + 结果”短语，不得经过 style asset 的短词过滤
- `scene_assets.public_explosion` 与 `scene_assets.external_order` 不能把事件强行压成地点、道具、机构等硬件名；事件级资产数量服从原文，脚本只提示是否可能过少，由模型判断是否漏提
- `book.profile.json.story_guardrails.character_face_split` 固定检查非空：`different_face_evidence / reaction_order_split / action_authority_split`
- `book.profile.json.story_guardrails.consequence_structure` 固定检查非空：`pre_evidence_reality_consequences / consequence_rebound_modes / tail_entry_owner / tail_entry_exclusion_reason`
- `高敏桥段识别.md`、`作者DNA指纹.md`、`同桥段过检规则.md` 不能只写抽象结论；至少要显式出现 `原文：` 证据行，否则默认未落到原文证据
- `profile_source.md / 桥段施工卡.md / 高敏桥段识别.md` 对同一座桥必须使用一致的功能标签；每张卡还要明确原文证据、承重件、顺序理由、假点和调用方式
- 每张 `桥段施工卡` 必须有 `一句人话抓手`，用生活化冲突句概括桥的记忆点；脚本发现只含“权限/秩序/现实后果/承重结构”等抽象词时只作提示，由模型决定是否回写
- finalize 前固定执行“反向漏项审计”：不看候选池结论，重新寻找可能未被候选池、16 张表或 profile 消费的细节；5 项只作过程完整性参考，不得为达数量制造伪候选。每项必须写 `收录 / 不收录 + 理由`；发现有效新资产时，更新全链路后重新开始两轮稳定审计
- 文件名默认只是 `任务名 / 来源标签`，不是已验证标题。只有标题在原文中明确出现或由用户确认，才允许写“标题照应 / 标题归位”；否则固定标 `标题状态：未验证（来自文件名）`
- 原文出现裸照、私密照片、脱衣羞辱、性化传播等内容时，必须单独判断 `受害者性别如何改变羞耻与旁观机制 / 保护行为为何成立 / 这是否超过普通霸凌或隐私侵犯`，不得只压成“隐私权限”
- 全量 Markdown 必须通过洁净检查：无重复标题、无空字段、无 `桥1 / 桥段卡1 / 待补 / 占位` 标题、无半成品模板壳
- `可直接仿写_导语拆解表.md` 不允许默认写成纯 `前20字 / 前60字 / 前100字` 机械分档；如果原文更适合按 `错位关系 / 公共命名 / 生死反告白 / 真异点` 这类功能钩拆，优先按功能钩落盘，再补回字段映射

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
- 没落 `事实与推断台账.md`，或台账缺主体边界、时间边界、证据来源
- 模型人工确认属于肯定性高主动因果判断，却没有回指 `Fxx`，或把人工推断伪装成原文明确；否定句、禁写示例和引用不由脚本直接判错
- 没落 `profile_source.md`
- 没落 `桥段施工卡.md`
- 没生成 `book.profile.json`
- `profile_source.md` 缺 `## 7-12` 任一节
- `profile_source.md` 有桥段卡但没有 `为什么假 / 场面资产 / 后果链 / 作者站位高危句`
- 没补 16 张 `可直接仿写_*.md`
- 没补 `原文细节库/`
- `作者DNA指纹 / 仿写约束_禁写清单 / 同桥段过检规则 / 高敏桥段识别 / profile_source` 缺任意一份
- `桥段施工卡.md` 缺失，或只有桥名总结没有原文证据、顺序理由和调用方式
- `写作资产/` 的母结构、冲突、异物、角色口气、关系重组、公开场后果、平台适配、情绪母线、新状态、虐点对照有任意缺件
- 只有抽象评价，没有原文证据
- 只有桥段名，没有承重件、迁移顺序和顺序不能乱的原因
- 16 张表虽然有 3 段，但没有先判表类型，写成通用空话
- 原文细节库虽然有五条，但没有先判证据核心，写成泛化模板壳
- 风险判断没跑检测却写成伪实测口径，没有标 `人工判断 / 未测 / 未知`
- 正式产物里残留重复标题、空字段、占位卡或初始化模板壳
- 为了过验收把表写成机械字段壳，导致写手直接调用阻力明显高于同类更自然写法
- `拆文报告.md` 缺 `脚本硬筛 / 规则拆层判断 / 可学层 / 禁学层 / 后续调用方式 / 叙事时间线 / 故事核` 任一层
- `拆文报告.md` 的 `结构划分` 只有概括条目，没有 `字数范围 / 占比 / 功能 / 对应节`
- `情节节点.md` 颗粒度不足，只剩梗概式大节点，没有拆出中段承重桥节点
- `情节节点.md` 只有行号和摘要，没有 `类型 / 情绪 / 涉及 / 状态变化 / 因果`
- `情节节点.md` 虽达到旧分档阈值，但低于 `ceil(原文字数 / 400)` 的动态节点下限
- 原文明明存在终局预热或硬牌上桌前等待，`情节节点.md` 却把它漏掉
- `写作手法.md` 每节只有薄概括，没有角色嘴型差、成立原因和迁移风险
- 验收脚本报错，仍试图标记完成

收口状态硬规则：

- finalize 通过后必须自动把 `_progress.md` 全量勾选
- finalize 通过后必须把 `_meta.json.last_stage_in_progress` 清空
- 产物通过但状态文件仍显示未完成，视为收口失败

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
