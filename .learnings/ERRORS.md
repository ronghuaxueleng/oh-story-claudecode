# Errors

Command failures and integration errors.

---

## [ERR-20260728-001] unified-exec-session-wait

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
将统一执行会话 ID 误传给了只接受 exec cell ID 的等待接口。

### Error
```text
exec cell 64182 not found
```

### Context
- 长测试已通过 `exec_command` 返回持续会话 ID。
- 测试进程本身没有失败，只是轮询工具选错。

### Suggested Fix
持续 `exec_command` 会话统一使用 `write_stdin` 轮询；只在 `functions.exec` 明确返回 cell ID 时使用 `wait`。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-write/tests

### Resolution
- **Resolved**: 2026-07-28T00:00:00+08:00
- **Notes**: 已切换到 `write_stdin` 轮询当前测试会话。

---

## [ERR-20260728-004] story-short-analyze-full-suite

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
短篇拆文完整测试集中，多段原文范围编译包测试因资产覆盖指纹不一致失败。

### Error
```text
ValueError: source_asset_coverage 与当前正式资产不一致
```

### Context
- 命令：`python3 -m unittest discover -s skills/story-short-analyze/tests -p 'test_*.py'`
- 其余 160 个测试通过；失败用例为 `test_multi_range_source_style_is_supported`。
- 当前技能仓库在测试前已有 `complete_upgrade_existing.py` 与对应测试的未提交修改，需先判断是否为基线工作区影响。

### Suggested Fix
单独复现失败用例，对比测试 fixture 的 coverage SHA 生成顺序与编译包校验逻辑，确认是否与本次内容指纹改动有关。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-analyze/tests/test_direct_imitation_package.py, skills/story-short-analyze/scripts/build_direct_imitation_package.py

### Resolution
- **Resolved**: 2026-07-28T00:00:00+08:00
- **Notes**: 测试修改原文和子流程索引后刷新夹具中的 `source_asset_coverage`；生产校验逻辑未改动。

---

## [ERR-20260728-005] source-gate-test-fixture-filter

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
更新来源门禁测试夹具时，根目录过程文件过滤条件误排除了正式资产 `_sample_comparison.md`。

### Error
```text
profile 覆盖清单缺少正式资产: .../_sample_comparison.md
```

### Context
- 定向运行内容指纹、编译包和来源读取门禁测试时，9 个来源门禁用例失败。
- 生产代码一直明确将 `_sample_comparison.md` 作为例外保留，问题仅在新改的测试夹具过滤条件。

### Suggested Fix
测试夹具必须复用生产规则语义：排除根目录其他下划线过程文件，但保留 `_sample_comparison.md`。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-write/tests/test_source_read_gate.py

### Resolution
- **Resolved**: 2026-07-28T00:00:00+08:00
- **Notes**: 已补正式样本对照文件例外并重跑相关测试。

---

## [ERR-20260728-006] skill-fingerprint-contract-sync

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
新增内容指纹模块后，validator 与 preparer 的 skill fingerprint 文件清单短暂不一致。

### Error
```text
test_preparer_and_validator_use_same_fingerprint_files: tuples differ
```

### Context
- 短篇拆文完整测试集 161 项中仅该契约同步测试失败。
- validator 已纳入 `content_fingerprints.py`，preparer 清单漏加。

### Suggested Fix
新增影响流程语义的脚本时，同时更新 preparer 与 validator 的权威文件清单。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-analyze/scripts/prepare_short_analyze_job.py, skills/story-short-analyze/scripts/validate_short_analyze_outputs.py

### Resolution
- **Resolved**: 2026-07-28T00:00:00+08:00
- **Notes**: 两份 skill fingerprint 文件清单已重新对齐。

---

## [ERR-20260728-007] story-short-write-baseline-suite

**Logged**: 2026-07-28T00:00:00+08:00
**Priority**: medium
**Status**: pending
**Area**: tests

### Summary
写作侧完整测试集存在 5 个与内容指纹改动无关的契约基线失败。

### Error
```text
2 errors: init_entry() 缺少新增参数
3 failures: 细纲长度/基准字段与 original_scene_granularity 新硬闸未同步测试夹具
```

### Context
- 完整执行 `story-short-write/tests` 共 191 项。
- 本次修改直接相关的 profile、编译包、source read gate 70 项定向测试全部通过。
- 失败文件未被本次任务修改，工作区原先已有相应契约演进。

### Suggested Fix
由对应契约任务统一更新 `test_first_draft_entry.py`、`test_outline_performance_contract.py`、`test_section_source_bundle.py` 和 `test_write_release_gate.py` 的调用参数与完整夹具。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-write/tests/test_first_draft_entry.py, skills/story-short-write/tests/test_outline_performance_contract.py, skills/story-short-write/tests/test_section_source_bundle.py, skills/story-short-write/tests/test_write_release_gate.py

---

## [ERR-20260727-001] background_test_process

**Logged**: 2026-07-27T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
在统一执行工具中用 shell 后台任务或 `nohup` 启动测试，启动 shell 结束后子进程被回收，测试未实际执行且日志为空。

### Error
```text
后台 PID 很快结束，测试日志大小为 0，未产生 unittest 结果。
```

### Context
- 尝试后台执行短篇拆文与写作测试套件。
- 普通 `&` 和 `nohup ... &` 均未能让进程跨工具调用存活。

### Suggested Fix
长测试直接通过执行工具启动，并使用其返回的持续会话 ID 轮询，不依赖 shell 后台化。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-analyze/tests, skills/story-short-write/tests

### Resolution
- **Resolved**: 2026-07-27T00:00:00+08:00
- **Notes**: 后续改用执行工具持续会话运行和轮询测试。

---

## [ERR-20260726-002] rg-shell-quoting

**Logged**: 2026-07-26T23:10:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
双引号包裹的 `rg` 模式含 Markdown 反引号，shell 误将其当作命令替换。

### Error
```text
/bin/bash: line 1: cases: command not found
```

### Context
- 只读检索文档时，在双引号正则中直接写了 Markdown 反引号。
- 未修改文件，后续检查正常完成。

### Suggested Fix
含反引号的 shell 检索模式统一用单引号包裹，或显式转义反引号。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-write/SKILL.md

### Resolution
- **Resolved**: 2026-07-26T23:10:00+08:00
- **Notes**: 已改用单引号模式执行后续检索。

---

## [ERR-20260726-001] outline_performance_contract

**Logged**: 2026-07-26T22:08:36+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
新增来源元数据校验参数后，调用点漏传参数。

### Error
```text
TypeError: validate_scene_logic_contract() missing 1 required positional argument: 'errors'
```

### Context
- 运行细纲表演合同与写作放行定向测试时出现。
- 函数签名增加 `source_metadata`，主循环仍使用旧参数列表。

### Suggested Fix
同步更新调用点，并补跑全部相关测试。

### Metadata
- Reproducible: yes
- Related Files: skills/story-short-write/scripts/validate_outline_performance_contract.py

### Resolution
- **Resolved**: 2026-07-26T22:08:36+08:00
- **Notes**: 已补传 `source_metadata`，关联测试恢复通过。

---
