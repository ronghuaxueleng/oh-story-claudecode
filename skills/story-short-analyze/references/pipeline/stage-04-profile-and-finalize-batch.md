# Stage 4：profile 与收口

这一阶段只做两件事：

1. 把结构化上游补全
2. 跑只读式最终收口，不做任何补写或修复

## 零兜底原则

- `run_short_analyze_finalize.py` 不得补标题、补“为什么假”、扩写情绪母线或改写任何 Markdown。
- profile 生成失败、字段不足或 validator 报错时，直接返回错误。
- 信息不足时回到责任微批由模型重写；禁止脚本使用通用婚姻、家庭、职场或古言内容代填。
- finalize 前后 Markdown SHA1 必须一致；任何变化都阻断。

## profile_source 角色

`profile_source.md` 是 `book.profile.json` 的上游，同时也是单书规则层的第一入口。

因此：

- 结构化字段要稳
- 解释层不要把字段冲散
- `profile_source.md` 自己必须保住“桥规则骨架 + style assets + story_guardrails”
- 更厚的人类施工解释继续写进 `桥段施工卡.md`

额外硬目标：

- `book.profile.json` 不能只做到“有键可过 schema”
- 至少要让 `bridge_rules` 保住 3 类信息：起手、承重件、顺序/假点原因
- 如果生成出的 `book.profile.json` 比同书 `bak` 明显更空，默认本批未完成；但 `bak` 只用于对比厚度和找漏项，不能参与回填或直接回灌正式产物

## profile_source 必补章节

- `## 7. 禁句 / 禁写法`
- `## 8. 场面资产`
- `## 9. 后果链`
- `## 10. 作者站位高危句`
- `## 11. style_assets 原始材料`
- `## 12. 迁移替换资产`

## 7. 禁句 / 禁写法 的硬写法

这里不能只写：

- 禁把门锁失效写成一句“他们同居了”
- 禁把公开投证写成无缘无故的挂人

每条禁写法后面都必须紧跟一条：

- 为什么假：...

最低要求：

- `为什么假` 至少 2 条
- 每条要说清“为什么会写假”，不是只换个说法重复禁令
- 如果 `为什么假` 没写，当前批默认不能进入 finalize

## 当前阶段最常见薄化

1. `为什么假` 不写
2. `scene_assets` 被压成一条长串
3. `story_guardrails` 上游标签不全
4. `style_assets` 混入换壳词
5. `bridge_rules` 只剩 `must_keep` 壳，没有 `must_avoid / fake_signals / why_order_matters / why_original_passes`

这些都要在 finalize 前修。

## 收口规则

最后固定运行：

```bash
python3 "$CODEX_HOME/skills/story-short-analyze/scripts/run_short_analyze_finalize.py" "拆文库/{书名}" --json
```

理解口径：

- `validator 通过` 只表示机械合规
- finalize 只允许生成 `book.profile.json` 和读取正式产物，不允许修改 Markdown
- 仍要人工复核是否出现明显压缩化
- 如果主报告厚、但个别资产文件明显薄，不要在同一长上下文里补丁式连修很多轮
- 优先冷启动回到对应阶段文档，重做那一批
- 冷启动只负责验证这次修改是否真的修好；确认有效后，必须把修复落到正式 skill，再回到正式目录重跑，不允许把冷启动目录当正式产物来源

## finalize 后仍要看什么

下面这些如果出现提示，即使不阻断，也要当作 skill 还可继续优化的证据：

- `scene_assets.public_explosion / external_order` 数量偏少
- `profile_source.md` 的 `为什么假` 偏少
- `情绪母线.md` 明显过短
- `情节节点.md` 中段承重桥保留不足
- `book.profile.json.bridge_rules` 只有 1-2 条，或字段明显薄于 `profile_source.md`

这些不是现在就必须阻断的硬错，但它们通常对应“厚度开始退化”。
