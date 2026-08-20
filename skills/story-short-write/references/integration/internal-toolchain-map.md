# Skill 内部工具链

## 正式主链

- `validate_project_directory_name.py`：一次完成书名校验、目录原子创建与复验。
- `init_project_writing_assets.py`：只初始化项目配置。
- `generate_story_profile.py`：维护来源 profile；单书写作主链不直接调用。
- `apply_project_profile_policy.py`：从主体 profile 初始化项目 profile，并写入项目来源边界。
- `manage_target_prose_map.py`：初始化、校验和增量重绑唯一目标脑图，并初始化、刷新和封存紧凑正文覆盖回执。
- `validate_streamlined_write_release.py`：检查来源角色、profile 和目标脑图后放行正文。
- `validate_continuation_gate.py`：验证合法初稿停靠。
- `validate_zhihu_section_format.py`：按需验证知乎数字分节格式。

以上是短篇正式链允许使用的完整脚本集合。目录中出现其他短篇流程脚本时，视为部署污染并清理。

## 确定性边界

脚本可以解析细纲、绑定路径/SHA、展开来源账本、校验映射与格式。脚本不得选择语义映射、生成正文、替代人工通读或自动写通过结论。
