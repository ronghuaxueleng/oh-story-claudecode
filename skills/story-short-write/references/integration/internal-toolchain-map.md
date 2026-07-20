# skill 内部工具链清单

这份文件只回答四件事：

1. 现在有哪些脚本和规则已经正式内收到 skill
2. 它们分别放在哪
3. 它们在流程里负责什么
4. 后面继续补规则时，应该补到哪一层，而不是到处乱塞

---

## 一、总原则

- 运行期默认优先读取 skill 内副本
- 外部规则仓只作为上游来源，不再作为默认运行依赖
- 通用规则进 `skill 内底座`
- 书级 / 项目级专项规则进 `profile` 或 override
- 不能把某一题材、某一本稿子的临时成功经验直接写死进通用脚本

---

## 二、story-short-write 已内收内容

### 1. 核心写作与审计脚本

目录：

- `story-short-write/scripts/`

当前文件：

- `validate_writing_rule_gate.py`
- `validate_source_read_gate.py`
- `validate_rule_execution_ledger.py`
- `validate_post_write_human_review_gate.py`
- `generate_story_profile.py`
- `audit_novel_ai_flavor.py`
- `run_full_ai_audit.py`
- `auto_revise_ai_flavor.py`
- `run_revision_cycle.py`
- `validate_gate_receipts.py`
- `compare_with_external_block_audit.py`
- `audit_ai_flavor.py`
- `precheck_rewrite_gate.py`
- `apply_humanizer.py`
- `normalize-punctuation.js`

职责分层：

- `validate_writing_rule_gate.py`
  - 固定清点格式、去 AI 味和叙述者声音三份写前必读规则
  - 校验证据词、读取结论、写作用途、当前文件哈希和回执时序
  - 规则文件变化或 `narrator-voice.md` 漏读时阻断设定、细纲和正文
- `validate_source_read_gate.py`
  - 从每本主体 / 辅助拆文目录生成完整逐文件读取清单
  - 校验主报告、16 表、8 库、写作资产和动态字典是否齐全
  - 校验证据词、读取结论、写作用途、文件哈希和回执时序
  - 未通过时阻断细纲和正文，不允许只读摘要或 profile 开稿
- `validate_rule_execution_ledger.py`
  - 从写作规则回执和拆文读取回执生成统一逐项执行列表
  - 每个拆书文件都做适用性判断，16 表和承重资产逐规则展开
  - 强制区分 `script / human / hybrid`，校验脚本产物、人工判断和写作产物原句证据
  - 规则源、拆书源或最终正文 SHA 变化后阻断，不接受“已使用”式空口回执
- `validate_post_write_human_review_gate.py`
  - 自动生成全文或母稿 diff 的人工语义复核清单
  - 校验最终正文 SHA、自动预扫产物、九项人工检查和逐条改写句判断
  - 只校验回执完整性与证据真实性，不替人工判断作者代判、叙述站位或多余解释
  - 局部/专项回炉未绑定母稿、正文修改后沿用旧回执时阻断放行
- `generate_story_profile.py`
  - 从拆书资产生成单书 `book.profile.json`
  - 或合成融合 `project.profile.json`
- `run_full_ai_audit.py`
  - 总审计入口
  - 汇总轻审计、重审计、规则簿、profile、块级风险
  - 先导出带正文 SHA 和段落起点的人工模型分段回执，再由当前执行 skill 的模型完整读文并回填边界
  - 不调用外部模型 API 或 Claude CLI；无人工回执时仅使用算法滑窗预扫
  - 短高波动段标为 `high-pulse`，短而无可计算信号的段标为 `short-window-review`
- `audit_novel_ai_flavor.py`
  - 正文级 AI 味审计
  - 输出结构化热点和风险分
- `audit_ai_flavor.py`
  - 轻量风险词类 / 句壳 / 模板味审计支撑
- `auto_revise_ai_flavor.py`
  - 根据审计结果生成回修任务单
  - 不直接改正文
- `run_revision_cycle.py`
  - 串起“审计 -> 任务单 -> 回修 -> 再审计”的循环流程
- `validate_gate_receipts.py`
  - 校验 `rewrite_gate_receipt.json / failure_gate_receipt.json` 是否填写完整
  - 校验 `summary` 是否与结构化判定项一致
  - 防止把半填或乱填的回执当成有效第二闸门结果
- `compare_with_external_block_audit.py`
  - 只用于题材首次校准
  - 生成内部打分标准，不是日常必跑项
- `precheck_rewrite_gate.py`
  - 高风险回修前后的第二道预检闸门
  - 检查解释句、提前判断、功能对白、整齐收口等结构风险
- `apply_humanizer.py`
  - 只作人工参考层
  - 不直接进入正式自动改正文链
- `normalize-punctuation.js`
  - 辅助规范化处理

### 2. 规则与词典文件

目录：

- `story-short-write/references/`

当前文件：

- `precheck_rewrite_gate.config.json`
- `通用高风险词类词典.json`
- `虚词模板词典.json`
- `story/references/high-risk-gates/reference-index.md`
- `story/references/short-high-risk/reference-index.md`

职责分层：

- `precheck_rewrite_gate.config.json`
  - 预检脚本的通用底座配置
  - 只放跨题材成立的结构规则
- `通用高风险词类词典.json`
  - 轻审计支撑词典
- `虚词模板词典.json`
  - 只作人工参考
  - 不直接参与第一层自动扣分
- `story/references/high-risk-gates/reference-index.md`
  - 第二闸门共享 prompt 主入口
  - 统一承接受限重写协议、受限重写提示词、失败即重写判定
- `story/references/short-high-risk/reference-index.md`
  - 短篇高敏共享资产总入口
  - 集中承接所有短篇高敏专项规则，避免在多个 skill 中重复平铺同一组正文

### 3. 规则簿与文档入口

目录：

- `story-short-write/references/`

关键文件：

- `audit-rulebook.json`
- `myconfig-rule-integration.md`
- `profile-source-template.md`
- `story-profile-schema.md`
- `internal-toolchain-map.md`
- `rule-onboarding-checklist.md`

职责：

- `audit-rulebook.json`
  - 正式二层规则簿
  - 不在代码里硬写桥段/题材词
- `myconfig-rule-integration.md`
  - 说明哪些规则已正式接入、哪些只作人工参考
- `profile-source-template.md`
  - 拆书资产补到 profile 前的中间模板
- `story-profile-schema.md`
  - profile 字段规范和调用示例
- `internal-toolchain-map.md`
  - 当前这份总清单
- `rule-onboarding-checklist.md`
  - 新规则接入前的强制检查表
- `audit-rulebook-coverage.md`
  - `audit-rulebook.json` 的已覆盖 / 待补充盘点表

---

## 三、story-deslop 已内收内容

### 1. 脚本

目录：

- `story-deslop/scripts/`

当前文件：

- `audit_ai_flavor.py`
- `precheck_rewrite_gate.py`
- `run_rewrite_gate_cycle.py`
- `validate_gate_receipts.py`
- `apply_humanizer.py`
- `normalize-punctuation.js`

职责：

- `audit_ai_flavor.py`
  - 去味场景下的轻审计支撑
- `precheck_rewrite_gate.py`
  - 去味回修前后的第二道预检闸门
- `run_rewrite_gate_cycle.py`
  - 去味场景的第二闸门标准闭环入口
  - 统一产出审计、预检、gate 执行单、gate 回执、cycle_summary
- `validate_gate_receipts.py`
  - 校验去味场景 gate 回执是否填完整、是否自洽
- `apply_humanizer.py`
  - 只作人工参考，不直接并进自动正式链
- `normalize-punctuation.js`
  - 辅助规范化处理

### 2. 规则与词典副本

目录：

- `story-deslop/references/`

当前文件与 `story-short-write/references/` 中同名规则文件对齐：

- `precheck_rewrite_gate.config.json`
- `通用高风险词类词典.json`
- `虚词模板词典.json`
- `story/references/high-risk-gates/reference-index.md`
- `story/references/short-high-risk/reference-index.md`

用途：

- 作为去味 skill 仍需保留的本地配置与词典层
- 第二闸门 prompt 正文统一改走共享 gate 入口，不再在这里维护重复主文档

---

## 四、运行优先级

默认优先级如下：

1. 先用 `validate_writing_rule_gate.py` 证明当前版三份写作规则已逐文件读取
2. 再用 `validate_source_read_gate.py` 证明主体 / 辅助拆文资产已逐文件读取
3. 立即初始化 `规则执行台账.json`，逐项确认脚本 / 人工 / 混合分工和适用性
4. 再读当前书 / 当前项目的 `book.profile.json` 或 `project.profile.json`
5. 再读 `references/governance/audit-rulebook.json`
6. 再读 `references/governance/precheck_rewrite_gate.config.json`
7. 再读 `references/governance/通用高风险词类词典.json`
8. 涉及短篇高敏专项时，再转到 `story/references/short-high-risk/reference-index.md`，并把专项规则文件加入执行台账
9. 写作过程中执行一项标记一项
10. 跑自动审计，只把结果当脚本预扫并回填脚本产物
11. 最终正文完成后，先通过 `validate_rule_execution_ledger.py`
12. 再通过 `validate_post_write_human_review_gate.py`
13. 第二闸门回执回填后，还要先过 `validate_gate_receipts.py`
14. 两份回执都过校验后，还要重刷同轮 `cycle_summary.json / gate_validation.md / STATUS.txt`

也就是说：

- `profile` 负责书级 / 项目级差异
- `audit-rulebook.json` 负责正式二层规则
- `precheck_rewrite_gate.config.json` 负责通用预检底座
- `通用高风险词类词典.json` 负责轻审计支撑
- `story/references/short-high-risk/reference-index.md` 负责短篇高敏专项共享资产分发
- `虚词模板词典.json` 和 `apply_humanizer.py` 只负责人工参考层
- `validate_post_write_human_review_gate.py` 只负责约束人工复核过程，不生成语义结论

第二闸门判定口径补充：

- `precheck` 清零，不等于第二闸门完成
- `rewrite_gate_task.md / failure_gate_task.md` 已生成，不等于第二闸门完成
- 只有两份 `receipt.json` 回填完成、校验通过，并且同轮状态刷新成 `gate_passed / passed`，才算这一轮真正过闸

### 实战短案例：`v17 -> r5 -> gate_passed`

案例目标：

- 对一篇仿写回修稿执行第二闸门
- 验证“脚本命中清零”和“完整过闸”不是一回事

实际过程：

1. 原稿先跑 `run_rewrite_gate_cycle.py`
2. 首轮结果里：
   - 审计分约 `39`
   - `pretty_detail` 较高
   - 两份 `receipt.json` 都还是 `pending`
   - 这时只能算“执行单已生成”，不能算过闸
3. 按 `precheck` 命中句回修正文，再跑到中间轮：
   - `pretty_detail` 从两位数一路压到 `0`
   - `high_function_dialogue` 也压到 `0`
   - 但如果此时 `receipt` 还没回填，`STATUS.txt` 仍会停在 `awaiting_rewrite_gate`
4. 继续按协议回填：
   - `rewrite_gate_receipt.json`
   - `failure_gate_receipt.json`
5. 回填后必须分别跑：
   - `validate_gate_receipts.py ...rewrite_gate_receipt.json --require-executed --require-complete`
   - `validate_gate_receipts.py ...failure_gate_receipt.json --require-executed --require-complete`
6. 两份回执都过后，还不能停；必须用同一轮 `label` 再跑一次 `run_rewrite_gate_cycle.py`
7. 直到同轮产物刷新成：
   - `gate_stage: gate_passed`
   - `gate_overall_status: passed`
   - 这一轮才算真正过闸

这个案例最后的结果口径是：

- 审计分降到 `12`
- `pretty_detail = 0`
- `author_explain = 0`
- `early_judgement = 0`
- `high_function_dialogue = 0`
- `tidy_closure = 0`
- 两份回执硬校验通过
- `STATUS.txt` 明确写出 `gate_passed`

这个案例说明：

- 只看 `precheck` 清零，容易误判“已经完成”
- 只看回执存在，也容易误判“已经完成”
- 第二闸门真正的完成判定，必须走完：
  - `正文回修`
  - `receipt 回填`
  - `receipt 校验`
  - `summary / gate_validation / STATUS 刷新`
  - `gate_passed`

### 外部分块高分的通用判定口径

如果外部检测结果显示：

- 内部轻审计和第二闸门已经比较干净
- 但外部分块仍有 1 到 3 个块持续偏高

优先不要把原因理解成“还有几个词不自然”，而要先按下面 4 类块病判断：

1. `成品化开头块`
   - 开头太像样板开场
   - 小事实被排成一个很会讲主题的投喂链
2. `偏心实锤块`
   - 一个块里把冲突、偏心确认、关系定性、后果落差一口气做完
3. `连续承重虐点块`
   - 一个块里连续叠伤害事实，每一刀都太准确，读起来像设计好的虐点组件
4. `完整收束结尾块`
   - 旧事、后果、决定、断联、翻篇都塞进同一块，显得太像交付成品

这 4 类块病的共性不是句面花，而是：

- 小事实被组织成主题句
- 一块里主任务过多
- 关系判断来得太早
- 后果链过顺
- 读完太明白、太完整、太像作者已经整理好的版本

处理顺序：

1. 先拆块里的主任务数量
2. 再拆主题句和提前关系判断
3. 再拆“信息到位 -> 看懂 -> 决定 -> 后果 -> 翻篇”的完整闭环
4. 最后才处理词句和局部口气

---

## 五、后续补规则时放哪

### 应该补进通用底座的

放这里：

- `references/governance/precheck_rewrite_gate.config.json`
- `references/governance/通用高风险词类词典.json`
- `references/governance/audit-rulebook.json`

适合补进去的规则：

- 跨题材成立
- 不依赖具体角色名
- 不依赖具体桥段名
- 不依赖具体项目背景
- 可以稳定结构化判断

### 不该补进通用底座的

不要直接放进上面这些文件。

这类内容应进入：

- `book.profile.json`
- `project.profile.json`
- 对应拆书目录下的写作资产文档

典型例子：

- 某一本书专属桥段顺序
- 某个角色专属口气
- 某个题材才成立的场景物件
- 某次送检成功稿里的局部修法

### 只能当人工参考的

保留在：

- `虚词模板词典.json`
- `apply-humanizer-reference.md`
- 其他经验文档

适用范围：

- 句子钝化
- 语气松动
- 虚词使用感
- 局部顺气

不能直接自动化批量执行。

---

## 六、当前状态结论

现在 skill 层面已经做到：

- 运行期默认不依赖外部项目绝对路径
- 自检与审计脚本有 skill 内副本
- 关键规则和词典有 skill 内副本
- 预检配置已去项目化，改成通用底座
- 绝对路径示例和外部项目绑定表述已清掉

后续如果继续补规则，默认先改这份图对应的位置，不要再把新规则直接塞进某个单独脚本里。

---

## 七、规则持续补强口径

这套东西不是一次接完就结束。

以后凡是出现下面任一来源：

- 新的外部分块高分块复盘
- 新的手工回修成功案例
- 新的误伤案例
- 新的失败样式
- 新的桥段型假感

都必须补做这 4 步：

1. 先写清这次新经验到底解决什么问题
2. 再跑 `rule-onboarding-checklist.md` 判断落点
3. 该补文档的补文档，别只补脚本；该补脚本的补脚本，别只写经验
4. 如果涉及第二闸门，还要同步检查 `receipt` 结构和 `validate_gate_receipts.py` 是否要增项

默认原则：

- 协议文档、失败判定模板、receipt 结构、校验脚本必须一起维护
- 不准只改其中一个层，其他层继续老口径

---

## 八、最新补入的“高敏同桥批规则”落点

这批规则的来源是高敏同桥实战复盘，不是整包照搬，而是拆层吸收。

已经正式并入的：

- 进 `audit-rulebook.json`
  - `段内推进完整度`
  - `一段同时完成过多主任务`
  - `旧事补成案情说明`
  - `段尾同时完成伤口、判断、决定`
  - `一刀里时间层过多`
- 进 `story-short-write/SKILL.md`
  - `每场只干一件大事`
  - `每段只保留一个主任务`
  - `插叙只补一个原因`
  - `对话优先试探、回避、失手`
  - `每三场至少一场不直接推进主冲突`
- 进 `story-short-analyze/SKILL.md`
  - `高敏桥段` 先做样本分级
  - 原文高敏桥段默认只提承重件和过检原理，不直接提标准承载方式

没有直接并进通用层的：

- 具体桥段名
  - 如订婚宴围攻、医院催签、主卧让位、背后抱住收束
- 具体角色名和项目名
- 某个版本号上的局部修法

这些内容默认只能进入：

- `样本分级与可学层`
- `同桥段过检规则`
- `book.profile.json / project.profile.json`
- 人工复盘文档
