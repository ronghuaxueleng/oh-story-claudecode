# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

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
