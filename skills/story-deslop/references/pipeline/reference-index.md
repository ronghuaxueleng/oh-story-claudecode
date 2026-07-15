# story-deslop references 索引

这份索引只负责导航，不重复去味规则正文。

---

## 1. 主入口

- [deslop-execution-core.md](deslop-execution-core.md)
- [../../../story/references/high-risk-rewrite-governance.md](../../../story/references/high-risk-rewrite-governance.md)

---

## 2. 去味核心规则

- [../anti-ai-writing.md](../anti-ai-writing.md)
- [../banned-words.md](../banned-words.md)

---

## 3. 通用治理层

- [../../../story/references/high-risk-gates/reference-index.md](../../../story/references/high-risk-gates/reference-index.md)
- [../governance/通用高风险词类词典.json](../governance/通用高风险词类词典.json)
- [../governance/虚词模板词典.json](../governance/虚词模板词典.json)
- [../governance/precheck_rewrite_gate.config.json](../governance/precheck_rewrite_gate.config.json)

这些文件属于长短篇共用层。

---

## 4. 短篇高敏专项

- [../scenarios/short-high-risk/reference-index.md](../scenarios/short-high-risk/reference-index.md)

短篇高敏专项不是默认入口，只在 `同桥 / 外部分块审计 / 高敏仿写 / 连续回修炸段` 场景挂载。

---

## 5. 何时回退到别的 skill

- 结构、桥段、顺序问题：回 `story-short-write`
- 样本准入、原文可学层问题：回 `story-short-analyze`
- 只有局部句壳和成品感问题：留在 `story-deslop`
