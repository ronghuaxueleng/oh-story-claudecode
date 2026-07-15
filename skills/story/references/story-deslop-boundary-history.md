# story-deslop 边界与历史依据

这份文件只回答两件事：

1. `story-deslop` 为什么必须保持长短篇共用主干
2. 哪一批提交把它往短篇高敏专项方向拉重了

---

## 一、当前结论

`story-deslop` 的正确职责是：

- 通用去味
- 通用 Gate A-F
- 通用第二闸门完成态
- 通用停机口径

不应把下面这些内容默认塞进主干：

- 短篇高敏检测专项
- 同桥高敏检测专项
- 仿写高敏专项
- 某一类短篇检测器的长期对抗经验

这些内容可以存在，但只能挂在：

- `story-short-write`
- `story-short-analyze`
- `story-deslop/references/scenarios/short-high-risk/`

不能成为 `story-deslop` 的默认身份。

---

## 二、git 历史怎么证明的

### 1. 通用主干阶段

这些提交体现的是“跨篇幅共用的去味能力”：

1. `f420a0f` `feat: 新增去AI味 skill + 融入外部精华参考文件`
2. `7a10081` `fix(story-deslop): rubric bugs + writing-prompt patterns`
3. `04fed58` `feat(story): 去解释腔/上帝感 + 深度限知视角 + 情绪烈度`
4. `0e37ec0` `feat(deslop): 模型退化 + 工程词泄漏检测`
5. `91391f3` `feat(deslop): 碎句号/长段落检测 + 破折号按功能改写`
6. `0ac8934` `feat(deslop): 去AI味改为删除优先`
7. `698c760` `fix(deslop): refine anti-ai prose linting`

这批提交的共同点：

- 改的是通用 AI 味识别
- 改的是句法、节奏、解释腔、退化、工程词泄漏
- 同时波及 `story-long-write / story-short-write / story-review / story-setup`
- 明显不是只服务某一类短篇仿写

所以这批历史证明：

- `story-deslop` 的主干本来就是共用层

### 2. 短篇高敏灌入阶段

关键提交：

1. `b5192d3` `feat: sync story skill audit and rewrite workflow`

它把下面这批东西集中灌进来了：

- `precheck_rewrite_gate.py`
- `run_rewrite_gate_cycle.py`
- `validate_gate_receipts.py`
- 受限重写协议
- 失败即重写判定
- 高风险词典
- 短篇高敏检测核心判断
- 短篇高敏检测自检清单
- 同桥不过检判断
- 作者站位过高判断

这批内容本身不是错的，问题在于：

- 里面既有通用治理
- 也有短篇高敏专项
- 当时被一起塞进 `story-deslop` 主 references

所以后果是：

- skill 主入口开始带上短篇高敏默认身份
- 长篇和普通润稿场景被迫背短篇专项负担

---

## 三、以后怎么判断该放哪

先问 4 个问题：

1. 这是所有篇幅都成立，还是只在短篇高敏场景成立
2. 这是通用治理，还是某个专项检测经验
3. 这是默认必挂，还是命中特定任务才挂
4. 这条规则如果给长篇也默认启用，会不会变成误伤

按结果落层：

- 长短篇都成立：留 `story-deslop` 主干
- 只在短篇高敏成立：放 `story-deslop/references/scenarios/short-high-risk/`
- 涉及换链、桥段重排、样本准入：回 `story-short-write` 或 `story-short-analyze`

---

## 四、当前结构约束

当前固定分层：

- `story-deslop/SKILL.md`
  只写通用定位、流程、第二闸门入口、放行条件
- `story-deslop/references/pipeline/`
  放通用去味执行骨架与索引
- `story-deslop/references/governance/`
  放通用协议、通用词典、通用配置
- `story-deslop/references/scenarios/short-high-risk/`
  放短篇高敏检测、同桥、站位过高等专项

以后如果再把短篇专项直接塞回主入口，视为结构回退。
