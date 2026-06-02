# 连续剧情库输出模板

## 六层结构

本 skill 默认产出六层：

1. `剧情骨架库`
2. `连续剧情库`
3. `细粒度剧情施工库`
4. `跨章情节事件库`
5. `人物关系网`
6. `角色状态线`

## 剧情骨架库模板

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

## 连续剧情库模板

```md
## 000001. {plot_name}
- 类型：{plot_type}
- 起止章节：{start_chapter}-{end_chapter}
- 核心冲突：{core_conflict}
- 起因：{trigger}
- 推进：{development}
- 关键转折：{turning_points}
- 结果/钩子：{result_or_hook}
```

## 细粒度剧情施工库模板

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
```

## 跨章情节事件库模板

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

## 人物关系网模板

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

## 角色状态线模板

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

## 施工层提醒

细粒度施工条必须回答：

- 第一章怎么起
- 第二章怎么压
- 第三章怎么翻
- 章尾怎么勾

## 关系层提醒

人物关系网不能只写“朋友/敌人”，必须写变化。

## 状态层提醒

角色状态线不能只写“人物介绍”，必须写时间推进中的变化。
