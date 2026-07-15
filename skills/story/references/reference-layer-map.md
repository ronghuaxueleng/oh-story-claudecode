# 共享 references 分层地图

这份文件只负责回答一件事：

- 当规则需要跨多个 story skill 复用时，应该落到哪一层

---

## 一、共享层放什么

共享层只放跨多个 skill 都成立的规则。

当前包括：

- [high-risk-rewrite-governance.md](high-risk-rewrite-governance.md)
- [high-risk-gates/reference-index.md](high-risk-gates/reference-index.md)
- [story-deslop-boundary-history.md](story-deslop-boundary-history.md)
- [short-high-risk/reference-index.md](short-high-risk/reference-index.md)

适合放进共享层的内容：

- 高风险任务定义
- 跨 skill 切换边界
- 第二闸门完成态
- 统一停机口径
- 第二闸门共享 prompt 主文档

不适合放进共享层的内容：

- 某个 skill 私有脚本用法
- 某类题材独有模板
- 某份词典的具体条目
- 某个执行阶段才会用到的细节说明
- 当前仍被多个脚本直接按本地路径读取的 prompt 正文资产

---

## 二、应该落到哪一层

### 1. `story/references/`

放：

- 跨 `analyze / write / deslop` 共用的治理规则
- 短篇高敏共享资产

### 2. `story-short-analyze/references/`

放：

- 拆书方法
- 样本分级
- 可直接仿写层
- profile 上游资产

### 3. `story-short-write/references/`

放：

- 起盘
- 细纲
- 正文
- 回炉
- 写作工具链

### 4. `story-deslop/references/`

放：

- 去味分级
- Gate A-F
- 去味保护规则
- 第二闸门执行口径
- 短篇高敏专项场景索引

### 5. 各 skill 的主 `references/`

放：

- 已正式接入的规则文件
- 词典
- 预检配置
- 第二闸门执行文档

补充约束：

- 如果某份文档既是“人读规则”，又是“脚本直接读取的 prompt 正文”，在没有改脚本取数路径前，先保留 skill 内本地副本
- 这种文件可以在共享层挂“统一边界和维护口径”，但不急着物理上提，避免把运行路径一起弄断

原则：

- 先判断是不是三边共用，再决定是否放共享层
- 先放最窄的那层，只有明确跨 skill 复用才上提
- 已正式接入的规则，不再额外包一层 `myconfig-import/`
- `story-deslop` 默认是长短篇共用主干，短篇高敏规则只能挂专项场景层

---

## 三、以后继续收口的顺序

后续再整理 references 时，固定按这个顺序判断：

1. 这是共享治理，还是某个 skill 私有执行细则
2. 这是主入口文件，还是下游细节文件
3. 这是正式底座规则，还是导入副本
4. 这是需要长期维护的规则，还是一次性案例沉淀

只要顺序判断错了，文件就会越堆越乱。
