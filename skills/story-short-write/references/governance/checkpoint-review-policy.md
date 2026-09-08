# 节点审查与首写预检

## 策略与兼容

本文件是审查调度唯一规则，优先于旧工作流中“每区域独立 critic”的描述。没有策略字段的旧台账保持 `per_region`。用户要求减少逐节审查或优化审查耗时时，通过已有台账脚本启用 `whole_book`，不得直接改批准状态：

```bash
python3 "$SKILL_ROOT/scripts/validate_rule_execution_ledger.py" set-review-policy \
  --ledger "{项目目录}/写作资产/规则执行台账.json" --mode whole_book \
  --user-authorization "{用户要求优化审查的原文}" --reason "整纲一次、整稿一次，不做逐节复核"
```

切换只记录策略与授权，不重开已冻结的设定和区域，也不把历史自检改称独立审查。当前有已领取或待确认候选时，先完成该区域再切换。恢复逐区独立审查使用同一命令的 `--mode per_region`，历史记录保留其实际审查身份。

## 三个独立节点

- 设定：沿用原有独立 critic、precommit、confirm，已通过且 SHA 有效的不重做。
- 完整细纲：逐节由 writer 自检八轴并执行 precommit/preflight/confirm；全部完成后进行一次独立整纲审查，记录 `outline_complete`，再运行完整 preflight 与 `--outline-only` 放行。
- 完整初稿：逐节由 writer 完成句法包、颗粒计划、逐句/话轮自检、precommit 和 confirm；全书完成后进行一次独立通读，记录 `draft_complete`，再运行 `validate-draft --require-complete`、正文放行和原有颗粒覆盖终审。

大纲审查状态按区域和文件 SHA 绑定，不能从旧区域推导新区域。任何对 `小节大纲.md` 的新增、删除、重排、source-map 修改、字段修改或尾声补写，都会使受影响区域变为未审查；若文件整体 SHA 变化，`outline_complete` 也必须重新记录。`preflight` 仅是结构门禁，不是审查结论，不能替代 critic、自检证据或独立整纲审查。

`whole_book` 不生成逐节自检 JSON，也不要求逐节句子复核。整纲和整稿统一审查使用 `review_mode: "independent"` 与 `critic_context_isolated: true`。

节点独立审查只看已完成的正式文本、设定边界、必要来源及相关完整规则 case，不接收写作者辩护。整纲侧重跨节因果、信息时序、关系变化、权限与来源保真；整稿侧重声线、连续场面、情绪累积和兑现。不重新抄每节全部检查字段，不要求审查者重新发现或遍历文件。来源可按风险定位回读，不能只凭作者总结裁决。

发现问题只返回“原文证据、违反的具体规则或事实、影响、最小修复范围”；没有实质问题可直接通过，不强制两轮、不要求凑 finding。修复后只复核问题和受影响连接，未变内容复用已读上下文；最终节点记录绑定修复后的实际文本。编号、引句是否存在、哈希和 schema 错误由正式脚本处理，不为文书错误重新开子代理。子代理不可用时不得自动启动多层 `codex exec` 兜底，也不能以自检冒充独立审查；保留待审状态并报告真实工具阻断。

独立节点记录沿用唯一台账，不新增侧车：

```bash
python3 "$SKILL_ROOT/scripts/validate_rule_execution_ledger.py" record-checkpoint \
  --ledger "{项目目录}/写作资产/规则执行台账.json" \
  --stage "{outline_complete 或 draft_complete}" --review-json-file /dev/stdin
```

输入 JSON：`review_mode: "independent"`、`critic_context_isolated: true`、`model_read_final_candidate: true`、`final_verdict: "pass"`、`unresolved_findings: []`；`axis_checks` 必须包含 `causal_continuity / source_fidelity / character_and_permission / voice_and_payoff`，各项提供 `verdict: "pass"`、当前文本逐字 `evidence_quotes` 和至少30字的具体 `judgment`。整纲的 voice 轴检查唯一声线边界与对白施工风险，不预写正文台词。

`bindings` 为审查时文件的“项目相对路径: SHA256”映射，整纲固定绑定 `设定.md`、`小节大纲.md`、`写作资产/项目写作配置.json`；整稿另绑定 `正文.md`、`写作资产/目标成文脑图.json`。正式脚本核验并存入台账，文件变化后节点失效；来源有效性仍由原有来源和脑图门禁核验。不得用旧审查结果配新哈希假装已经读过修改后的文本。

## 首写时检查，而非审后补写

每区域落笔前，把以下适用项并入现有细拍核对或 `plan-section`，不另建清单文件、不重复写一份逐项报告：

- P 四字段与 E 五字段一起对照当前和相邻节点；整条 E 在单节点承接，不能为集中 E 削掉相邻 P 的信息或后果，也不能误判独立轨道共享事实为重复发生。
- 跟随来源层型和进出位置：现场、概述、叙述者插嘴、公共传播和冷尾各归其位。来源要求的亲密或羞辱升级链不能缩为一个结果动作。
- 公共热度与私域传播的作用不同；换媒介仍须保留来源的可见范围、当事人识别方式和关系后果，不为虚构传播检索真实新闻。
- 结构化记录先确定当事人可见字段，再写判断；涉及款项时检查日期、金额、收款方、账号和支付阶段，尤其不能把仍有后续付款的款项写成尾款。无关字段不强制补齐。
- 入场到离场连续核对施事、受事、车辆、物件、位置和力的来源；关键指代、信息获得和权限不能依赖读者猜补。
- 人物换壳核对原文中实际姓名、专属称呼和关系归属，结论并入现有八轴自检及整纲 `source_fidelity`，不增设审查。`actor` 是施事描述，可能是职业、机构、群体或复合短语；不得按二到四字、正则切片或职业白名单猜姓名，动态别名词也不自动成为禁用词。无明确类型化实体依据时，脚本不做专名判决；模型仍须拦截真实姓名和人物壳复用，脚本通过不能替代此项判断。
- 冻结设定约束既定事实、关系和结局，不穷举生活活动；新增细节只在确有时间、事实、资源或权限冲突时阻断。刻意延迟的信息不能因为尚未揭晓而被判错。

这些检查提高首写命中率，不承诺零错误。只有真实未决的因果、医疗法律权限或来源冲突，或同类错误连续出现时，才追加局部独立诊断；不能把题材含医疗/法律等同于每节自动外审，也不能为已修复的小问题重跑全链。
