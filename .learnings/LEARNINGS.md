# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260729-002] best_practice

**Logged**: 2026-07-29T00:00:00+08:00
**Priority**: high
**Status**: implemented
**Area**: workflow

### Summary
新增统一流程命令时，必须同步技能入口、执行核心、项目生成清单和回归测试。

### Details
工具箱已经具备新主命令，但技能正文和冷启动清单仍推荐旧底层命令，会让新项目继续走兼容路径。代码入口存在不等于流程已经落地，所有面向模型和项目的操作说明必须同批更新。

### Suggested Action
每次新增或替换主流程入口，都检索旧命令在 `SKILL.md`、`references/`、冷启动生成器和测试中的全部引用；新命令作为默认路径，旧命令只明确标为迁移兼容或定向调试。

### Metadata
- Source: user_feedback
- Related Files: skills/story-short-write/SKILL.md, skills/story-short-write/references/governance/short-write-execution-core.md, skills/story-short-write/scripts/initialize_cold_start_from_source_profiles.py
- Tags: workflow, docs, entrypoint, regression
- Pattern-Key: workflow.code_docs_entrypoint_sync

---

## [LRN-20260729-001] best_practice

**Logged**: 2026-07-29T00:00:00+08:00
**Priority**: high
**Status**: implemented
**Area**: infra

### Summary
写作流程应由模型维护单一紧凑语义源，SHA、路径、模板和大型回执全部交给脚本派生。

### Details
模型直接维护多个大型回执会重复填写机械字段，并使正式回执与项目重建数据发生语义漂移。逐节实读记录、文件指纹和状态字段属于可确定计算；规则裁决、细纲迁移判断和停检结论才属于模型任务。

### Suggested Action
统一采用“脚本生成任务包 -> 模型填写语义答案 -> 脚本编译正式回执并验收”的三段式流程，禁止模型手写派生 SHA、路径与回执外壳。

### Metadata
- Source: user_feedback
- Related Files: skills/story-short-write/scripts/story_short_write_project_toolbox.py, skills/story-short-write/scripts/rebuild_outline_and_capacity_receipts.mjs
- Tags: workflow, semantic-source, receipts, automation
- Pattern-Key: simplify.single_semantic_source

---

## [LRN-20260726-001] best_practice

**Logged**: 2026-07-26T22:08:36+08:00
**Priority**: medium
**Status**: pending
**Area**: tests

### Summary
修改验证函数签名后，必须立即搜索并核对所有调用点。

### Details
为细纲因果合同验证增加 `source_metadata` 参数时，函数定义已更新，但主验证循环漏传该参数，导致关联测试统一抛出 `TypeError`。

### Suggested Action
签名变化后先用 `rg` 枚举全部调用点，再运行最小定向测试，确认参数数量和顺序一致后进入全量测试。

### Metadata
- Source: error
- Related Files: skills/story-short-write/scripts/validate_outline_performance_contract.py
- Tags: validator, function-signature, tests

---
