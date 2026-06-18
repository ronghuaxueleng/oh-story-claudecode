# 本地TXT情节库输出模板

## 总体结构

本 skill 默认交付三大层：

1. `剧情主库`
2. `写法扩展库`
3. `语录与来源扩展库`

目标不是只回答“这本书写了什么”，而是同时回答：

- `后续能复用什么剧情发动机`
- `后续能迁移什么表演机制`
- `哪些地方绝对不能直接照搬`

## A. 剧情主库模板

### 剧情骨架库模板

```md
# 剧情骨架库

## 骨架 0001. {arc_name}
- 阶段定位：{arc_role}
- 覆盖章节：{start_chapter}-{end_chapter}
- 主问题：{main_problem}
- 阶段推进：{phase_progress}
- 阶段转折：{phase_turning}
- 阶段结果：{phase_result}
- 后续承接：{next_hook}
```

### 连续剧情库模板

```md
## 000001. {plot_name}
- 类型：{plot_type}
- 起止章节：{start_chapter}-{end_chapter}
- 核心冲突：{core_conflict}
- 起因：{trigger}
- 推进：{development}
- 关键转折：{turning_points}
- 结果/钩子：{result_or_hook}
- 可迁移价值：{transfer_value}
```

### 细粒度剧情施工库模板

```md
## segment-000001. {segment_name}
- 归属剧情：{parent_plot_name}
- 可支撑章节数：{usable_chapter_count}
- 切入场：{opening_scene}
- 场景顺序：
  1. {scene_1}
  2. {scene_2}
  3. {scene_3}
  4. {scene_4}
  5. {scene_5}
- 冲突升级：{conflict_progression}
- 反转/换刀点：{twist_or_reversal}
- 结果兑现：{payoff}
- 章尾钩子：{chapter_hooks}
- 写作目标：{writing_goals}
- 可迁移说明：{transfer_note}
```

### 跨章情节事件库模板

```md
## event-000001. {event_name}
- 类型：{event_type}
- 起止章节：{start_chapter}-{end_chapter}
- 参与人物：{involved_characters}
- 事件目标：{event_goal}
- 章节推进：
  - {beat_1}
  - {beat_2}
  - {beat_3}
- 转折章节：{turning_chapters}
- 事件结果：{event_outcome}
- 后续承接：{next_link}
```

### 人物关系网模板

```md
## relation-000001. {character_a} - {character_b}
- 关系类型：{relation_type}
- 初始关系：{initial_relation}
- 当前关系：{current_relation}
- 变化路径：{change_path}
- 关键章节：{key_chapters}
- 强弱关系：{dominance}
- 情感偏向：{emotion_bias}
- 未来风险：{future_risk}
```

### 角色状态线模板

```md
## character-000001. {character_name}
- 角色定位：{role_position}
- 初始状态：{initial_state}
- 状态变化：
  - {change_1}
  - {change_2}
  - {change_3}
- 当前状态：{current_state}
- 动机变化：{motivation_shift}
- 能力变化：{power_shift}
- 关系变化：{relation_shift}
- 关键章节：{critical_chapters}
```

## B. 写法扩展库模板

### 文风迁移白名单 / 黑名单

```md
# 文风迁移白名单

## 可借文风机制
- 节奏机制：{tempo_rule}
- 压迫推进方式：{pressure_rule}
- 对话先压住场子的方式：{dialogue_rule}
- 群像放大方式：{crowd_rule}
- 章尾停拍方式：{cliff_rule}
- 金句触发条件：{line_trigger}

## 推荐迁移方式
- {transfer_method}
```

```md
# 文风迁移黑名单

## 慎借文风表皮
- 高频发力词：{high_freq_words}
- 高辨识度连接句：{signature_connectors}
- 高频比喻系统：{signature_metaphors}
- 易造成模仿感的排比/断句：{risky_patterns}

## 禁止直搬标记
- 标志口头禅：{signature_catchphrases}
- 强辨识度语录：{signature_quotes}
- 专属梗句：{exclusive_bits}
- 角色私有语气整段复刻：{private_voice_blocks}
```

### 成文表演迁移白名单

```md
# 成文表演迁移白名单

## 开头抓手
- 反常动作：{abnormal_action_open}
- 死局切入：{deadlock_open}
- 狠问题切入：{hard_question_open}
- 现场先后顺序争夺切入：{authority_open}

## 先压住场子的方式
- 主角先做什么动作：{first_action}
- 主角后说什么话：{follow_line}
- 动作后那句压住场子的话为什么成立：{why_line_lands}

## 群像放大方式
- 谁先动：{first_reactor}
- 谁第二个往前顶上来或往后退开：{second_position_shift}
- 谁最后把原话缩回去：{last_change_voice}

## 章尾停拍方式
- 最后一拍停在：{last_shot_type}
- 为什么能挂人：{why_hooks}

## 动作先后顺序
- 先动作后解释：{action_then_explain}
- 先失态后补上第二下压力：{lose_face_then_finish}
- 先往前压一步或往后退一步，再把狠话甩出来：{shift_then_line}
```

### 开局起爆模板库

```md
## 起爆模板
- 起爆类型：{burst_type}
- 首句功能：{first_line_function}
- 前3段完成了什么：{first_3_paragraphs}
- 信息后补方式：{backfill_mode}
- 可迁移题材：{transferable_genres}
```

### 压场动作链库

```md
## 压场样本
- 场景类型：{scene_type}
- 动作链：{action_chain}
- 谁先动：{first_mover}
- 谁第二个改线：{second_shift}
- 哪句是动作后把场子压住的话：{post_action_line}
- 现实改局点：{reality_shift}
```

### 对话攻防链库

```md
## 攻防样本
- 起手挡法：{opening_block}
- 第一轮拆挡：{first_break}
- 第二轮压价/压命/压脸：{second_pressure}
- 第三方补逻辑位：{third_party_logic}
- 最后谁改手：{last_actor_shift}
```

### 动作-句子绑定样本库

```md
## 绑定样本
- 前置动作：{pre_action}
- 核心句：{core_line}
- 后续动作：{post_action}
- 为什么删掉前后动作后，这句会变空：{why_it_collapses}
```

### 群像反应放大器库

```md
## 放大样本
- 反应类型：{reaction_type}
- 触发动作：{trigger_action}
- 第一反应人：{first_reactor}
- 第二反应人：{second_reactor}
- 放大出的现实变化：{amplified_change}
```

### 章尾停拍拆解库

```md
## 章尾样本
- 章尾类型：{ending_type}
- 章尾前一拍：{pre_last_beat}
- 最后一拍载体：{last_beat_carrier}
- 为什么能挂人：{hook_reason}
- 禁用塌尾写法：{bad_close}
```

### 功能句、句式与句群

```md
# 功能句模板库

## 开场压迫句
- 功能：{function}
- 常见载体：{carrier}

## 翻案句
- 功能：{function}
- 常见载体：{carrier}

## 打脸句
- 功能：{function}
- 常见载体：{carrier}

## 交易句
- 功能：{function}
- 常见载体：{carrier}

## 命令句
- 功能：{function}
- 常见载体：{carrier}

## 章尾钩子句
- 功能：{function}
- 常见载体：{carrier}
```

```md
# 句式风格参数卡

- 短句密度：{short_sentence_density}
- 排比句密度：{parallel_density}
- 反问句密度：{rhetorical_density}
- 断句习惯：{pause_habit}
- 常用结构：{common_patterns}
- 动词强度：{verb_force}
- 物件落地句频率：{object_drop_rate}
- 群体反应句频率：{crowd_reaction_rate}
```

```md
# 句群模板库

## 翻盘句群
- {cluster_item}

## 围堵句群
- {cluster_item}

## 审桌拍案句群
- {cluster_item}

## 交易压价句群
- {cluster_item}

## 群像被逼着选边句群
- {cluster_item}

## 章尾收口句群
- {cluster_item}
```

## C. 语录与来源扩展库模板

### 语录化用库

```md
- quote_id：{quote_id}
- speaker：{speaker}
- chapter：{chapter}
- scene：{scene}
- quote_core：{quote_core}
- function：{function}
- style_type：{style_type}
- suspected_source_type：{source_type}
- rewrite_method：{rewrite_method}
- is_signature_quote：{is_signature_quote}
- transferable_value：{transferable_value}
```

### 疑似来源映射模板

```md
- 来源等级：{source_level}
- 来源类型：{source_type}
- 对应语句/话术：{matched_line}
- 是否建议直避：{avoid_direct_use}
```

## 交付自检

完成前至少自问四件事：

1. 只看 `剧情主库`，能不能知道这本书的发动机怎么跑。
2. 只看 `写法扩展库`，能不能知道这本书为什么写得活。
3. 不翻原始 TXT，只靠当前资料库，能不能回答：
   - `这章怎么更快起爆`
   - `主角怎么先用动作压场`
   - `群像怎么逐层被逼动`
   - `章尾怎么停在现场后果`
4. 能不能明确区分：
   - `可迁移机制`
   - `慎借表皮`
   - `禁止直搬内容`

如果第 3 条答不出来，说明这次抽取仍然偏“结构层”，不能判完成。
