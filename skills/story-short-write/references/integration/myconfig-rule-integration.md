# myConfig 规则接入表

这份专门说明：

- 外部上游规则源里的哪些规则已经正式接进 `story-short-write`
- 哪些只适合做人工改写参考
- 哪些不该直接拿来做第一层自动审计
- 哪些原始规则文件和脚本副本已经落进 skill 内部，后续默认优先读 skill 内副本

---

## 零、skill 内副本位置

为了避免后续流程仍然依赖 skill 外部目录，正式运行链现在只保留本 skill 必需资产，并把共享 gate 规则上提到共享层：

- 规则文件目录：`references/`
- 预检脚本副本：`scripts/precheck_rewrite_gate.py`

当前 skill 内已并入主 `references/` 的规则包括：

- `story/references/high-risk-gates/reference-index.md`
- `story/references/short-high-risk/reference-index.md`

后续口径：

- 写作流程、回修流程、第二道闸门，默认优先引用共享层正式入口
- 外部规则仓仍是上游来源，但 skill 运行时不应再默认依赖外部绝对路径
- 如果外部规则后续继续补强，需要同步回灌共享层正式入口

---

## 一、已经接进脚本的

### 1. 重审计脚本

skill 内默认副本：

- `scripts/audit_ai_flavor.py`
- `references/governance/通用高风险词类词典.json`

接入位置：

- `scripts/run_full_ai_audit.py`

作用：

- 作为重审计层，负责 finding / metric / hotspot

---

### 2. 二层规则簿

来源：

- `story/references/short-high-risk/reference-index.md`

接入位置：

- `references/governance/audit-rulebook.json`
- `scripts/run_full_ai_audit.py`

当前已落成的二层规则类别：

1. `开头反假`
2. `信息漏出顺序`
3. `后果链`
4. `人物偏手`
5. `失控说话`
6. `烂关系漏出`
7. `外部分块审计影响项映射`
8. `作者站位过高`

使用层级：

- 只做 `正文块 / 高风险片段` 的二层诊断
- 不进入第一层全局排序

### 3. 第二道重写闸门口径

来源：

- `story/references/high-risk-gates/reference-index.md`
- `story/references/short-high-risk/reference-index.md`
- `脚本/precheck_rewrite_gate.py`

接入位置：

- `SKILL.md`
- 回修任务单口径
- 后续待补的通用预检 / 自检脚本

作用：

- 在内部审计之后，再增加一层“当前高风险段能不能继续改”的强制判定
- 防止模型把回修任务做成自由创作、示范腔重写或顺手优化
- 把“失败即重写”从经验口头约束变成固定流程

当前接入原则：

1. 先接文档口径，再补脚本
2. 脚本只输出 finding / failure gate / rewrite task inputs
3. 禁止把题材词、桥段词、角色词硬编码进主逻辑
4. 规则必须优先来自 `profile / rulebook / 词典 / 配置`
5. 允许后续继续补新规则，但补的是配置和规则簿，不是再堆死代码

---

## 二、已经进文档口径，但不单独打分的

来源：

- `story/references/short-high-risk/reference-index.md`

已经吸收的核心口径：

1. 先判断高在句子、场面，还是整套桥段链
2. 原版低分先排除 OCR / 水印 / 杂符号污染
3. 同桥低分不等于桥安全
4. 功能过满优先回桥段层，不先润句
5. 越改越顺但分数升，通常是改成了精修模板稿

落点：

- `SKILL.md`
- `writing-workflow.md`
- `run_full_ai_audit.py` 的任务单排序口径

维护口径：

- 这组短篇高敏专项规则只在共享索引处维护正文
- integration 层只保留“来源入口 + 接入位置 + 作用”，不再重复罗列同一批子文件

---

## 三、不直接自动化的

### 1. `词典/虚词模板词典.json`

这份不直接接进第一层或第二层打分。

原因：

1. 它的用途更接近 `改写参考`
2. 很多词本身不是风险，而是 `怎么用、用在什么句位` 才决定真假
3. 直接自动化很容易把正文改成另一种油滑模板腔

正确使用方式：

- 只作为人工改写参考层
- 用来提醒“句子过硬时，可以怎么钝化、怎么松开、怎么加一点日常废气”
- 不能强制批量套模板
- 参见 `apply-humanizer-reference.md`

### 2. `脚本/apply_humanizer.py`

这份也不直接接进自动改稿链。

原因：

1. 它的强项是 `规则腔降压 / 说明句钝化 / 去模板词`
2. 它的弱项是 `桥段 / 人物 / 对白 / 情绪现场`
3. 如果直接自动跑在情绪短篇正文上，很容易把稿子改成另一种统一松句模板

正确使用方式：

- 只吸收其中可人工借鉴的动作
- 不直接运行脚本改情绪短篇正文
- 具体参考 `apply-humanizer-reference.md`

### 3. 高敏同桥实战目录里的成稿

这些不作为规则源直接喂脚本。

只吸收其中三类总结文件：

1. `原版为什么能过检-*.md`
2. `外部分块审计实战结论-*.md`
3. `网友做法提炼-*.md`

原因：

- 成稿本身容易带项目特定脏数据
- 规则应该提炼成通用判断，不该直接继承某份成稿壳子

---

## 四、后续接入原则

以后再从外部规则仓吸收规则，统一按下面顺序判断：

1. 能不能变成 `第一层排序规则`
   - 只有桥段、大块、场戏功能这类才有资格

2. 能不能变成 `第二层片段规则`
   - 人物偏手、烂关系漏出、作者站位、信息漏出顺序适合这里

3. 还是只能当 `人工改写参考`
   - 虚词、句子钝化模板、局部语气松动模板，多数归这里

总原则：

`不要把“怎么写得像人”误接成“全文关键词命中就扣分”。`

真正该自动化的是：

- 层级判断
- 风险定位
- 改法提示

不是：

- 强行把所有经验变成硬词表。

新增硬约束：

- `precheck_rewrite_gate.py` 已并入 skill，当前定位是正式链路里的通用预检层
- 正式链路里的预检 / 自检脚本必须保持通用版：题材无关、桥段无关、角色名无关
- 如果某条规则只能靠写死词表成立，默认先降级为人工参考或书级 override，不直接并进通用自动审计
- `references/governance/precheck_rewrite_gate.config.json` 现在只允许承载跨题材底座规则；书级专项补充应单独增设 override 配置，不污染底座
