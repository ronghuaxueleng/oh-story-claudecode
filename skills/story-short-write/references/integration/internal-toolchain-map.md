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
- `compare_source_baseline_audit.py`
- `count_words.py`
- `refresh_legacy_project_bindings.py`
- `story_short_write_project_toolbox.py`
- `validate_first_draft_basic_review.py`
- `validate_short_write_completion.py`
- `项目总诊断.py`（项目内包装脚本，由生成器落盘）
- `generate_project_tool_wrappers.py`
- `project_tool_wrapper_registry.py`
- `initialize_cold_start_from_source_profiles.py`
- `generate_project_outline_receipt_rebuilder_scaffold.py`
- `smoke_test_cold_start.py`
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
  - 关键来源契约合并后仍逐来源校验 `applied / not_selected / prohibition_checked`、原句证据和目标落点
  - 主体治理资产被标成未选用、文件级关键契约漏审、规则级父节点与子规则不一致或只用一条公共证据覆盖多来源时阻断
  - 设定/大纲规则按 `target_scene` 逐项目校验 `structural_claim_reviews`，防止用后果证据冒充开头或反转证据
- `validate_opening_contract.py`
  - 绑定主体 `可直接仿写_导语拆解表.md` 与大纲/正文 SHA
  - 固定导出前 `20 / 60 / 80 / 120` 字窗口，由当前模型人工提取主体三拍顺序并逐项裁决
  - 任务说明抢跑、关系锚迟到、题面未兑现或功能顺序被打乱时直接阻断
  - 不调用外部 API 或 CLI，不把主体人物、职业和动作硬编码进通用规则
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
  - 已识别的高风险桥段未进入前排桥段任务时阻断生成；短段和统计波动只保留为诊断提示
  - 已绑定 profile 时，关键 bridge / scene / style / guardrail 资产缺失也阻断生成，要求先重建拆书和 profile
- `run_revision_cycle.py`
  - 串起“审计 -> 任务单 -> 回修 -> 再审计”的循环流程
- `validate_gate_receipts.py`
  - 校验 `rewrite_gate_receipt.json / failure_gate_receipt.json` 是否填写完整
  - 校验 `summary` 是否与结构化判定项一致
  - 防止把半填或乱填的回执当成有效第二闸门结果
- `compare_with_external_block_audit.py`
  - 只用于题材首次校准
  - 生成内部打分标准，不是日常必跑项
- `compare_source_baseline_audit.py`
  - 用于同桥仿写、主干仿写、融合仿写的原文基线对照
  - 输入主体原文全量审计 JSON 与当前稿全量审计 JSON，输出分数差、共同命中、额外命中和建议动作
  - 防止把原文有效短句、高密对白、强钩子误判成新稿必须删除的问题
- `count_words.py`
  - 统一正文、回执和审计中的字数统计口径
  - 番茄口径：去掉 `#` 开头 Markdown 标题行后，统计所有非空白字符
  - 禁止用编辑器估算、人工估算或临时脚本结果替代
- `refresh_legacy_project_bindings.py`
  - 旧项目迁移与历史回执修复入口
  - 自动修复旧 skill 路径、过期 SHA、台账同步和可派生产物重建
  - 默认只处理机械绑定问题，不伪造缺失的人工语义判断
  - 已接入 `validate_write_release_gate.py` 与 `validate_first_draft_entry.py` 的 `--auto-refresh-legacy-bindings`
- `story_short_write_project_toolbox.py`
  - 项目级统一 CLI 入口
  - 自动推断项目目录与常用 receipt / artifact 路径，减少手工 `--help` 与长参数拼接
  - 统一提供 `refresh-bindings / validate-outline / validate-opening / init-setting-sequence / validate-setting-sequence / extend-outline-sequence / validate-sequence / extend-draft-sequence / draft-release / sync-sources / init-first-draft / validate-first-draft / init-first-draft-basic-review / validate-first-draft-basic-review / validate-section-execution / open-section / close-section / generate-wrappers / cold-start-from-source / init-completion / validate-completion / mark-draft-preview / confirm-deep-review / audit-local-stiffness / audit-project`
  - `audit-project` 会输出当前 gate 阻断点以及 `keep / rebuild / invalidate` 文件清单，可直接落盘 JSON 报告
- `validate_first_draft_basic_review.py`
  - 首稿基础审计入口
  - 负责初始化/校验 `首稿基础审计回执.json`，绑定母稿与仿写双基线要求
- `validate_short_write_completion.py`
  - 首稿停靠与深审确认状态机
  - 负责初始化/校验 `短篇全流程状态.json`，并承接 `draft_preview / deep_review_user_confirmed`
- `initialize_cold_start_from_source_profiles.py`
  - 从本地拆书 profile 冷启动新书的强制入口
  - 一次性初始化 `写作规则读取回执 / 拆文读取回执 / 规则执行台账 / 设定顺序契约 / 顺序契约 / 开头承重契约_大纲 / 细纲表演验收回执 / 首写容量契约`
  - 同时落盘 `冷启动来源清单.json` 与 `冷启动执行清单.md`
  - 作用不是代写设定和细纲，而是先把颗粒度硬闸前置，堵住“没建颗粒契约就先写书”的流程缺口
- `generate_project_tool_wrappers.py`
  - 自动生成项目内 Python 包装脚本
  - 用于把长参数的 gate 调用固化到项目 `写作资产/`，避免继续维护 `.sh`
  - `修复旧项目绑定.py / 运行正文放行.py / 初始化首稿入口.py / 校验首稿入口.py / 项目工具箱.py / 项目总诊断.py` 也由 `templates/project_scripts/manifest.json` 显式登记，不再在生成器里写死默认文件名
  - 包装脚本改为按 `purpose` 分别校验前置文件；新建项目即使还没产出回执，也能先生成 `项目工具箱.py / 项目总诊断.py`
  - 可顺手删除遗留 `运行正文放行.sh`
  - 项目模板脚本由 `templates/project_scripts/manifest.json` 显式登记；每条模板可声明 `file / kind / purpose / entrypoint`
  - 当前支持按 `kind` 选择性生成：`python_wrapper` 或 `project_template`
  - 登记后会从 `templates/project_scripts/{项目名}/` 同步回写对应 `.mjs` 辅助脚本，保证项目脚本整体可再生
- `generate_project_outline_receipt_rebuilder_scaffold.py`
  - 项目级 `重建细纲与容量回执` 脚手架生成器
  - 自动从当前项目 `小节大纲.md / 细纲表演验收回执.json / 首写容量契约回执.json` 抽出小节、字数、钩子、来源元数据，生成 `*.data.mjs + *.mjs` 双文件结构
  - `*.data.mjs` 只承载项目数据骨架；`*.mjs` 只做薄包装调用 skill 侧通用重建器
  - 只生成机械层，不代判原文切片、情绪拍、反刀位和句间关系；这些字段仍由当前模型补齐
- `promote_outline_receipt_rebuilder_scaffold.py`
  - 把 `重建细纲与容量回执.scaffold.data.mjs + 重建细纲与容量回执.scaffold.mjs` 提升为正式 `重建细纲与容量回执.data.mjs + 重建细纲与容量回执.mjs`
  - 自动修正包装脚本里的数据导入路径
  - 默认删除 scaffold 文件；需要保留时显式传 `--keep-scaffold`
- `project_tool_wrapper_registry.py`
  - 包装脚本构造注册表
  - 统一维护每个 `purpose` 对应的 Python wrapper 生成逻辑，避免在生成器里散落硬编码
- `smoke_test_cold_start.py`
  - 工具链开发自测脚本
  - 只用于验证冷启动初始化链，不属于用户写书主流程
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
5. 大纲完成后先通过 `validate_opening_contract.py`
6. 正文首写后再次通过 `validate_opening_contract.py`
7. 再读 `references/governance/audit-rulebook.json`
8. 再读 `references/governance/precheck_rewrite_gate.config.json`
9. 再读 `references/governance/通用高风险词类词典.json`
10. 涉及短篇高敏专项时，再转到 `story/references/short-high-risk/reference-index.md`，并把专项规则文件加入执行台账
11. 写作过程中执行一项标记一项
12. 跑自动审计，只把结果当脚本预扫并回填脚本产物
13. 最终正文完成后，先通过 `validate_rule_execution_ledger.py`
14. 重新校验正文 `opening_contract_gate`
15. 再通过 `validate_post_write_human_review_gate.py`
16. 第二闸门回执回填后，还要先过 `validate_gate_receipts.py`
17. 两份回执都过校验后，还要重刷同轮 `cycle_summary.json / gate_validation.md / STATUS.txt`

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
