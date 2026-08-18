# Skill 内部工具链

## 正式主链

- `validate_project_directory_name.py`：书名目录预检与复验。
- `init_project_writing_assets.py`：只初始化项目配置。
- `generate_story_profile.py`：从主体拆文资产生成项目 profile。
- `apply_project_profile_policy.py`：把项目来源边界写入项目 profile。
- `batch_outline_release.py`：初始化或续用纲层合同。
- `validate_outline_migration_contract.py`：一次导出、合并并校验三组紧凑 E/P 映射。
- `validate_streamlined_write_release.py`：检查来源角色、profile 和纲层合同后放行正文。
- `validate_initial_draft_review.py`：初始化并封口唯一初稿终审。
- `validate_continuation_gate.py`：验证合法初稿停靠。
- `validate_zhihu_section_format.py`：按需验证知乎数字分节格式。

以上是短篇正式链允许使用的完整脚本集合。目录中出现其他短篇流程脚本时，视为部署污染并清理。

## 确定性边界

脚本可以解析细纲、绑定路径/SHA、展开来源账本、校验映射与格式。脚本不得选择语义映射、生成正文、替代人工通读或自动写通过结论。
