# 短篇写作工作流

审查调用频率与身份以 [节点审查与首写预检](../governance/checkpoint-review-policy.md) 为准。`checkpoint` 下本文逐区域 critic 由 writer 如实自检，原有覆盖和脚本门禁保留；仅设定、整纲与整稿调用独立审查，不另加逐节子代理。

## Phase 1：隔离、选源、锁名

列出允许读取的主体原文、同名拆文资产和最小辅助集合。主体独占正文声线并供应完整 P/E、SF 和文字层；辅助只供应明确选中的 P 拍机制。锁名后创建未占用的同名目录，将来源角色、路径、SHA 和 profile 写入项目配置，并在创建 `设定.md` 前初始化 `规则执行台账.json`。

设定先在当前工作上下文形成候选，不落临时文件。独立 critic 只看候选、项目配置、来源资产和当前台账规则 case，先诊断事实权限、人物动机、现实操作、因果与题面风险；writer 定点修复后，critic 对最终候选的六个审查轴清零。`precommit-design --artifact setting` 通过后才第一次写入 `设定.md`，随后 `confirm-design` 只核对正式文件与候选 SHA。

## Phase 2：目标骨架与目标脑图

设定冻结后，再逐拍替换主体 P 拍事件壳并完成 `小节大纲.md`；用户已给 JSON 脑图时，先归一化脑图目标节点，再补足分节施工信息。细纲按导语、连续数字节、尾声顺序，每次只在工作上下文形成一个完整区域候选。每个区域必须同时写入入场状态和离场状态；每条细拍进入候选前，分别核对 P 的动作/控制/信息/后果，E 的内容/触发/关系位置/读者效果/烈度，以及层型、进出关系、保留规则和六维，整条 E 必须由单一节点完整承接。核对后才在行尾登记隐藏 `source-map`，禁止按相邻 ID 机械分配、把 E 拆给前后节点或先写概述占位。

当前区域允许一次形成和提交多条细拍；逐拍核对不等于逐拍单独调用。批量处理的质量边界以 `SKILL.md` 的细拍批量规则为准，不得因拍数多判定无法继续，也不得跨过逐区冻结顺序。

P/E 是独立轨道，来源本身允许共享事实。一项已成立的事实可以分别承担信息取得与后续情绪确认；这不等于事件在正文发生两遍。修复整拍承接时必须同时核对相邻节点的 P 四字段与 E 五字段，禁止为集中 E 而削掉邻接 P 的信息变化或后果，也不能把有来源依据的事实复用误判为拆拍。每个 ID 的唯一、同序绑定规则仍保持不变。

冻结设定锁定题面、关系、人物已知事实、权限和结局边界，不要求穷举所有生活动作、活动和场景。细纲可以首次确定这些具体 P 拍实现；事实冲突 finding 必须引用被违反的具体设定事实、时间约束、权限或来源保留项，不能仅以“设定未列出这项活动”判错。主线持续进行不等于人物每个时刻只能处理主线事务；确有同时性冲突、资源不足或越权时仍须阻断。

区域候选交给独立大纲 critic。critic 不写正文，只检查 `entry_exit_state / plot_emotion_whole_beat / source_layer_mode / information_acquisition / physical_action_chain / real_world_operation / dialogue_plain_speech_risk / future_region_leak`。其中 `dialogue_plain_speech_risk` 要在施工层识别“人物未来只能复述岗位标签、流程字段或关系分析才能完成细拍”的节点，要求大纲改成可由人物说具体事实、短命令或错答来承载；它不能提前替正文写一句固定对白。传给 critic 的规则 case 必须提供完整原文，不得用删掉适用边界的摘要代替；已经明确到人物、对象与具体事实的对白施工，不因尚未写成逐字台词而阻断。来源刻意延迟的答案可以保留为钩子，未在导语回答悬念不等于因果矛盾，须依据来源信息延迟与当前设定判断。

`precommit-design --artifact outline` 通过后才把同一候选第一次追加到正式大纲。随后先运行 `preflight --allow-partial`；脚本预检通过后再运行带 `--preflight-passed` 的 `confirm-design` 冻结区域 SHA，才允许下一区域。preflight 失败时，只重做当前未批准区域的 critic 和 precommit；不得先确认、不得写未来区域。

设定/大纲 critic JSON 使用同一形状，失败类型仍由当前 critic 动态命名：

```json
{
  "artifact": "setting 或 outline",
  "region_id": "setting、opening、section:N 或 epilogue",
  "critic_context_isolated": true,
  "diagnostic_only_first_pass": true,
  "author_intent_ignored": true,
  "model_read_final_candidate": true,
  "rule_refs_considered": ["rule_id:line"],
  "source_refs_considered": ["设定时使用含真实 path/sha256 的对象；大纲时必须逐项同序写 P=...、E=...、SF=...、L=..."],
  "draft_findings": [
    {
      "original_quote": "初稿逐字引句",
      "failure_code": "<critic 针对当前问题动态命名>",
      "rule_refs": ["rule_id:line"],
      "diagnosis": "为什么候选自身不能成立",
      "rewrite_direction": "最小修复方向",
      "resolved_in_final_quote": "最终候选逐字引句"
    }
  ],
  "axis_checks": {
    "当前阶段要求的每一个轴": {
      "verdict": "pass",
      "evidence_quotes": ["最终候选逐字引句"],
      "failure_codes": [],
      "judgment": "只用候选内事实、动作、状态和来源作反向裁决"
    }
  },
  "final_verdict": "pass",
  "final_judgment": "初稿 weakest link 已修复且全部设计轴失败码清零"
}
```

设定轴固定为 `title_promise / fact_and_permission / character_motivation / real_world_operation / causal_continuity / source_boundary`。设定 `source_refs_considered` 的每项必须是实际读取文件的 `{"path":"绝对或可解析路径","sha256":"当前 SHA"}`，脚本逐项核验文件存在与哈希。大纲轴固定为上段八项。大纲 `source_refs_considered` 必须与当前区域所有 `source-map` 中的字段和值逐项同序一致；同一来源跨多个节点重复出现时也保留重复项，不能去重。脚本只校验结构、引用、顺序与 SHA，不替 critic 生成结论。

设定、大纲和正文的 critic 均不以制造一次改写为通过条件。没有实质错误时使用 `draft_findings: []`，同时提交 `weakest_link_review`，字段为：`evidence_quotes`（当前候选逐字引句）、`rule_refs`（真实 case 引用）、`risk_considered`（至少12字，具体说明审查的风险）、`judgment`（至少30字，说明文本如何成立）、`verdict: "pass"`、`failure_codes: []`、`no_rewrite_needed: true`。这只免除无依据的返工，不免除任何设计轴、逐句、话轮或颗粒覆盖审查；已发现的真实错误不得藏进无错声明。

全部区域逐一落盘后才运行不带 `--allow-partial` 的完整 `manage_target_prose_map.py preflight`；在此之前，每个区域落盘后先运行带 `--allow-partial` 的局部预检，只检验当前已形成的连续前缀。全量同序 P 维度 JSON 与来源层短引句 JSON 在全部区域完成后提交，不要求提前读取未来区域或反复提交全书输入。preflight 在目标脑图创建前拦截 P/E 漏拍并拍倒序、SF 漏步、来源层漏层换序、非法 P 维度名和不属于对应行域的引句；通过前禁止初始化目标脑图。脚本不得根据来源行号、字数或相邻 P 拍自动猜测 E/SF/层语义。

随后初始化 `目标成文脑图.json`，P/E/SF/层映射只从细纲显式声明派生，不再人工维护第二套绑定：

- 主体全部 P 拍和 E 拍与来源同序映射目标节点。
- 每个主体 SF 的全部必经步骤逐项绑定目标节点。
- 每个来源文字层逐层绑定目标节点，保持层型、层序、进出关系和叙述距离。
- 每个 P 拍在写细拍时选择至少三个合法事件壳维度；四项承重和改编判断以当前细拍为唯一人工真源，由 init 确定性展开，禁止再人工抄一套版本。
- 每个 E 拍在目标脑图内逐项填写五字段的具体目标实现，并确认 `whole_beat_in_one_node=true`。
- 每个来源层先完整回读原文行域并提交可逐字核验的短引句；层型、进入、退出、叙述距离、全部 `must_preserve_in_target` 和六维由已核对的显式 L 绑定与当前细拍确定性展开，不再逐字段重复填写。短引句不得替代完整行域。
- 只有用户明确启用热点时，才把社会机制和事实边界写入对应目标节点的改编判断。

来源语义、原文行号、六维和保留规则只存在于主体 `来源成文脑图.json`；目标语义和人工映射只存在于 `目标成文脑图.json`。不得重抄大段原文、SF 静态对象或六维要求。

细纲、用户脑图或来源资产变化后运行 `manage_target_prose_map.py rebind`。未变目标证据和来源内容哈希自动迁移；受影响项留空待人工补绑。禁止全书重推和临时迁移脚本。

只有用户明确要求热点时，才读取按需热点规则。达到最低两条合格材料后立即停止扩搜，只调整实际绑定的目标 P 拍，不得借热点重推全书 P/E 映射或延迟细纲落盘。

## Phase 3：直接写正文

放行闸确认项目配置、profile、目标脑图、P 拍换芯、逐 E 五字段、SF 表演链和逐层写前保真有效后，才写 `正文.md`。正文必须一次只写一个区域。写前运行 `prepare-section`，只把当前区域的完整来源行域、连续句链、句间节奏、段落气口、主体书级 `sentence_motion` 和上一节尾句装入上下文；不得凭目标细拍直接生成正文，也不得提前读取或预写后续区域。

当前区域先在工作上下文形成候选，不落临时文件。切换到 diagnostic-only critic，忽略写作者辩护，只引用候选原句和当前台账规则 case：找 weakest link、提交动态失败码与最小修复方向；定点重写后，对最终候选逐句执行朗读、物理、人物注意力和结构化记录检查，并对连续动作/话轮/段落组复验。`precommit-section` 通过并记录候选 SHA 后，才把同一文本第一次追加到 `正文.md`，随后立即运行 `confirm-section`。逐句复核 JSON 固定形状如下，所有句子和对白必须来自当前区域真实文本，不得由脚本生成语义字段：

直接对白还要单独朗读，剥掉从细纲带入的行政与分析标签。角色不能在争执中复述岗位标签、合同身份、关系位置、资源排序、控制变化等施工语言；需要讲职业事实时，只说名单、合同、名字、钱、门禁和谁拿了什么等真人能直接说出口的内容。朗读后仍像作者借人物分析关系，先改再写。

critic 与 writer 必须任务隔离：critic 不接受“我为什么这样写”的解释，只看页面文本、当前规则 case 和项目反馈案例。失败码由当前问题动态命名；finding 必须引用原句、规则 `rule_id:line`、诊断与最小方向。用户纠错通过 `record-feedback` 进入项目台账，不能写成公共 skill 的特定短语黑名单。precommit 只保存候选 SHA 和审查，不保存第二份正文。

结构化记录按人物眼前字段成文：流水、病历、名单、门禁和合同分别落到当前可见的金额/备注/收款方、诊断、姓名/位置、时间/账号/开闭状态和具体条款。critic 的 `structured_record_verdict` 负责拦截把流程摘要冒充人物观察的句子。

`precommit-section` 的人工 JSON 固定形状如下；`failure_code` 由 critic 按当前失败动态命名，脚本不维护固定枚举：

```json
{
  "critic_context_isolated": true,
  "diagnostic_only_first_pass": true,
  "author_intent_ignored": true,
  "model_read_final_candidate": true,
  "rule_refs_considered": ["rule_id:line"],
  "feedback_case_ids_considered": ["<当前台账实际 feedback_id>"],
  "draft_findings": [
    {
      "original_quote": "初稿逐字引句",
      "failure_code": "CURRENT_FAILURE_NAME",
      "rule_refs": ["rule_id:line"],
      "diagnosis": "只诊断为什么失败",
      "rewrite_direction": "最小修复方向",
      "resolved_in_final_quote": "最终候选中的逐字新句"
    }
  ],
  "sentence_checks": [
    {
      "sentence": "最终候选完整真实句子。",
      "most_suspicious_span": "本句最可疑的逐字短语",
      "read_aloud_verdict": "pass",
      "physical_action_verdict": "pass 或 not_applicable",
      "pov_attention_verdict": "pass",
      "structured_record_verdict": "pass 或 not_applicable",
      "failure_codes": [],
      "judgment": "当前句各项检查通过的具体依据"
    }
  ],
  "group_checks": [
    {
      "group_type": "action_chain / dialogue_turns / paragraph_transition",
      "quotes": ["最终候选逐字引句"],
      "weakest_point": "本组最可疑处",
      "verdict": "pass",
      "judgment": "本组动作、话轮或段落连接成立的具体依据"
    }
  ],
  "final_verdict": "pass",
  "final_judgment": "初稿 finding 已修复且最终逐句、逐组失败码清零"
}
```

`rule_refs_considered` 和每条 finding 的 `rule_refs` 必须来自当前台账真实 cases；`feedback_case_ids_considered` 必须与当前项目用户反馈全量同序一致。脚本只做引用、逐字覆盖、字段、哈希与清零校验，不替 critic 生成诊断。

```json
{
  "model_read_entire_region": true,
  "sentence_reviews": [
    {
      "sentence": "当前区域完整真实句子。",
      "subject_or_viewpoint": "当前主语或感知者",
      "independent_unit_count": 1,
      "viewpoint_shift": false,
      "single_continuous_chain": true,
      "breath_point_judgment": "说明逗号、句号和停顿为何符合当前动作链",
      "source_voice_basis": "点明写前句法包中的来源层与连续句机制",
      "decision": "keep",
      "judgment": "说明此句为何保留，不能套用其他句子的结论"
    }
  ],
  "direct_dialogue_reviews": [
    {
      "quote": "“当前区域直接对白。”",
      "speaker": "说话人",
      "scene_pressure": "当前对白承受的具体压力",
      "turn_connection": "它怎样接住上一话轮",
      "response_effect": "它怎样改变动作或关系位置",
      "interchangeable": false,
      "decision": "keep",
      "judgment": "说明为什么只有此人物会这样说"
    }
  ],
  "repeated_sentence_reviews": [],
  "cadence_judgment": "说明本区域长短句如何按来源连续句链运行",
  "scene_sentence_relation_judgment": "说明现场、概述、插嘴和急刹如何落在真实句子中",
  "template_repetition_judgment": "说明没有使用事件句加固定旁白的批量模板",
  "explanatory_inference_review": "逐条裁决叙述者代判和解释性比喻",
  "manual_judgment": "说明当前区域的活动作、身体、对白和物件为何像人物正在过事",
  "region_judgment": "说明当前区域为何可以冻结并进入下一区域"
}
```

`sentence_reviews` 必须与当前区域的全部句子逐字、同序、等数；`direct_dialogue_reviews` 对全部直接对白执行同样要求。一个句子含多个独立动作或信息单元且不是同一身体、感官或话轮链时，必须先把 `decision` 写成 `split/revise`，回正文修改后重新提交，不能直接写 `keep`。重复句必须完整进入 `repeated_sentence_reviews`；只有能说明当前独有功能时才可保留。

`confirm-section` 通过后，台账冻结当前区域 SHA 并清除已领取句法包，才允许下一次 `prepare-section`。一次追加两个区域、跳节、旧区域被改、漏句、漏对白、重复使用同一人工判断或没有先领取句法包都会阻断。现场、概述、插嘴、跳时、急刹和余尾保持各自层型与连接，跨区域 SF 仍作为一个连续写作单元。

每完成一节就在正文上通读和修正 P/E 顺序、事件换芯、主体声线、SF 表演链、来源层型、叙述距离和全部真实句子。逐节判断只写回正式 `规则执行台账.json`，不创建暂存稿或独立侧车。发现上游目标节点不能施工，修改目标骨架后正式增量重绑。

## Phase 4：紧凑终审

全文写完后运行 `audit-init`。默认使用 `audit-confirm-compact`，只提交逐目标节点和逐来源层的正文引句、实现结论与保真布尔；目标脑图在正文前已经锁定 P 四项、E 五字段、SF 表演链、层拓扑和六维，终审不再复制第二套逐字段语义。所有目标节点和来源层都必须显式提交，脚本不得因存在一条引句而自动全置真。高风险项目仍可改用旧的逐字段 `audit-confirm-*` 接口，但不得并行维护两种回执。

终审发现问题先改正文，再运行 `audit-init` 重绑当前正文 SHA；没有变化的层判断按哈希和有效引句保留。`audit-seal` 只在全部层通过、区域覆盖通过且异常为空时放行。通过后执行初稿停靠，停靠前不做去味、正式深审或多轮回炉。

## 回修原则

- 先修题面与骨架，再修场面，再修关系和情绪，最后修句子。
- 连续三节出现同类问题时，回共同上游，不逐节打补丁。
- 目标节点变化后运行正式 `rebind`；正文变化后运行正式 `audit-init`。
- 重复逻辑必须合并进正式脚本，禁止临时写入脚本。
- 同一错误未改变真源时，不连续重跑验证器。

## 按需技法

- [格式规范](format-and-structure.md)
- [主体原文主导首稿](../governance/source-dominant-first-draft.md)
- [P 拍换芯与按需热点](../governance/p-beat-hot-news-replacement.md)（仅用户明确要求热点时读取）
- [起盘与情节](../craft/material-packs-setting-plot.md)
- [开头与钩子](../craft/opening-and-hook-library.md)
- [情绪与后果](../craft/emotion-and-outcome-library.md)
- [人物与对白](../craft/character-voice-library.md)

只读取当前写作问题需要的技法文件。
