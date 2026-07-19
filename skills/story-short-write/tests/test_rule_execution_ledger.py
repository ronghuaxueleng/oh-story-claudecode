from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_rule_execution_ledger.py"
)
SPEC = importlib.util.spec_from_file_location("rule_execution_ledger", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class RuleExecutionLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.skill_root = self.root / "story-short-write"
        self.project = self.root / "项目"
        self.source = self.root / "拆文库" / "样本"
        self.writing_receipt = self.project / "写作资产" / "写作规则读取回执.json"
        self.source_receipt = self.project / "写作资产" / "拆文读取回执.json"
        self.ledger_path = self.project / "写作资产" / "规则执行台账.json"
        self.text = self.project / "正文.md"
        self.script_report = self.project / "审计报告.json"
        self._build_skill_files()
        self._build_source_files()
        self._build_receipts()
        self.text.parent.mkdir(parents=True, exist_ok=True)
        self.text.write_text("# 正文\n\n正文证据。\n", encoding="utf-8")
        self.script_report.write_text('{"status": "passed"}\n', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _build_skill_files(self) -> None:
        for relative in GATE.CORE_SKILL_RULE_FILES:
            path = self.skill_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                path.write_text(
                    '{"rules": [{"id": "r1", "description": "检查格式"}]}',
                    encoding="utf-8",
                )
            else:
                path.write_text(
                    "# 规则\n\n1. 人物说话不能过度高效。\n- 检查格式和字数。\n",
                    encoding="utf-8",
                )

    def _build_source_files(self) -> None:
        table = self.source / "可直接仿写_人物偏手表.md"
        table.parent.mkdir(parents=True, exist_ok=True)
        table.write_text(
            "| 人物 | 偏手 | 使用规则 |\n"
            "|---|---|---|\n"
            "| 主角 | 紧张时摸杯沿 | 至少跨场复现两次 |\n",
            encoding="utf-8",
        )
        report = self.source / "拆文报告.md"
        report.write_text("# 报告\n\n这是一份整体分析。\n", encoding="utf-8")

    def _build_receipts(self) -> None:
        self.writing_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.writing_receipt.write_text(
            json.dumps(
                {
                    "gate_status": "passed",
                    "files": [
                        {
                            "path": relative,
                            "sha256": GATE.sha256(self.skill_root / relative),
                            "status": "read",
                        }
                        for relative in (
                            "references/workflow/format-and-structure.md",
                            "references/anti-ai-writing.md",
                            "references/craft/narrator-voice.md",
                        )
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        source_files = []
        for path in sorted(self.source.iterdir()):
            source_files.append(
                {
                    "path": path.name,
                    "sha256": GATE.sha256(path),
                    "status": "read",
                }
            )
        self.source_receipt.write_text(
            json.dumps(
                {
                    "gate_status": "passed",
                    "sources": [
                        {
                            "name": "样本",
                            "role": "main",
                            "root": str(self.source),
                            "files": source_files,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _create_ledger(self) -> dict:
        ledger, errors = GATE.create_ledger(
            "测试项目",
            self.writing_receipt,
            self.source_receipt,
            self.skill_root,
        )
        self.assertEqual([], errors)
        return ledger

    def _complete_entry(self, entry: dict, mode: str = "human") -> None:
        if entry.get("applicability") == "merged":
            return
        entry["execution_mode"] = mode
        entry["mode_confirmed"] = True
        entry["classification_confirmed"] = True
        entry["classification_method"] = "model_semantic_review"
        entry["classification_notes"] = "已阅读规则族及全部变体，确认当前分类。"
        entry["canonical_rule_text"] = "测试 canonical 规则。"
        entry["applicability"] = "applicable"
        entry["status"] = "completed"
        entry["target_stage"] = entry["remediation_target"]
        entry["target_scene"] = "测试场景"
        entry["decision_reason"] = "适用于当前正文。"
        entry["outcome"] = "passed"
        entry["result"] = "已逐项执行并复核。"
        if mode in {"script", "hybrid"}:
            entry["script_artifacts"] = [
                {
                    "path": str(self.script_report),
                    "sha256": GATE.sha256(self.script_report),
                    "summary": "脚本检查通过。",
                }
            ]
        if mode in {"human", "hybrid"}:
            entry["human_judgment"] = "人工确认规则在当前场景中成立。"
            entry["text_evidence"] = [
                {
                    "artifact": "正文",
                    "quote": "正文证据。",
                    "judgment": "该原句是本规则在正文中的落点。",
                }
            ]

    def _write_completed_ledger(self) -> dict:
        ledger = self._create_ledger()
        ledger["gate_status"] = "passed"
        ledger["artifacts"] = [
            {
                "name": "正文",
                "path": str(self.text),
                "sha256": GATE.sha256(self.text),
            }
        ]
        for entry in ledger["skill_rules"]:
            self._complete_entry(entry)
        for asset in ledger["source_assets"]:
            asset["applicability"] = "applicable"
            asset["status"] = "completed"
            asset["decision_reason"] = "已判断该拆书文件适用于当前项目。"
            if asset["rules"]:
                for rule in asset["rules"]:
                    self._complete_entry(rule)
            else:
                self._complete_entry(asset)
        ledger["execution_summary"] = GATE.calculate_execution_summary(ledger)
        self.ledger_path.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ledger

    def _make_manual_merge(self, ledger: dict) -> tuple[dict, dict]:
        entries = [
            entry
            for entry in ledger["skill_rules"]
            if entry["applicability"] != "merged"
        ]
        canonical, duplicate = entries[:2]
        duplicate.update(
            {
                "canonical_rule_id": canonical["id"],
                "merged_into": canonical["id"],
                "classification_confirmed": True,
                "classification_method": "model_semantic_review",
                "classification_notes": "模型确认两条规则属于同一语义规则族。",
                "canonical_rule_text": "",
                "applicability": "merged",
                "status": "completed",
                "decision_reason": "语义近似，归入 canonical。",
                "outcome": "not_applicable",
                "result": f"由 {canonical['id']} 统一执行。",
            }
        )
        return canonical, duplicate

    def test_complete_ledger_passes(self) -> None:
        self._write_completed_ledger()
        errors, summary = GATE.validate_ledger(self.ledger_path)
        self.assertEqual([], errors)
        self.assertGreater(summary["skill_rules"], 0)
        self.assertEqual(2, summary["source_assets"])
        self.assertGreater(summary["asset_rules"], 0)

    def test_missing_skill_rule_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        ledger["skill_rules"].pop()
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("缺少 skill 规则" in error for error in errors))

    def test_missing_source_asset_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        ledger["source_assets"].pop()
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("缺少拆书文件" in error for error in errors))

    def test_script_without_artifact_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        entry = ledger["skill_rules"][0]
        self._complete_entry(entry, "script")
        entry["script_artifacts"] = []
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("缺少脚本执行产物" in error for error in errors))

    def test_human_without_text_evidence_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        entry = ledger["skill_rules"][0]
        entry["text_evidence"] = []
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("缺少正文原句证据或全文范围复核" in error for error in errors))

    def test_hybrid_requires_both_sides(self) -> None:
        ledger = self._write_completed_ledger()
        entry = ledger["skill_rules"][0]
        self._complete_entry(entry, "hybrid")
        entry["human_judgment"] = ""
        entry["script_artifacts"] = []
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("缺少脚本执行产物" in error for error in errors))
        self.assertTrue(any("缺少人工语义判断" in error for error in errors))

    def test_skipped_rule_requires_reason(self) -> None:
        ledger = self._write_completed_ledger()
        entry = ledger["skill_rules"][0]
        entry["applicability"] = "not_applicable"
        entry["status"] = "completed"
        entry["decision_reason"] = ""
        entry["outcome"] = "not_applicable"
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("未填写具体原因" in error for error in errors))

    def test_changed_rule_source_invalidates_ledger(self) -> None:
        self._write_completed_ledger()
        path = self.skill_root / GATE.CORE_SKILL_RULE_FILES[0]
        path.write_text(path.read_text(encoding="utf-8") + "\n- 新规则。\n", encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("skill 规则源已变化" in error for error in errors))

    def test_stale_writing_receipt_blocks_initialization(self) -> None:
        path = self.skill_root / "references/anti-ai-writing.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n- 新规则。\n", encoding="utf-8")
        _, errors = GATE.create_ledger(
            "测试项目",
            self.writing_receipt,
            self.source_receipt,
            self.skill_root,
        )
        self.assertTrue(any("写作规则读取回执已过期" in error for error in errors))

    def test_stale_execution_summary_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        ledger["execution_summary"]["completed"] = 0
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("execution_summary" in error for error in errors))

    def test_failed_outcome_blocks_gate(self) -> None:
        ledger = self._write_completed_ledger()
        entry = next(
            item
            for item in ledger["skill_rules"]
            if item["applicability"] != "merged"
        )
        entry["outcome"] = "failed"
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("执行结果为 failed" in error for error in errors))

    def test_scope_review_can_prove_negative_human_check(self) -> None:
        ledger = self._write_completed_ledger()
        entry = ledger["skill_rules"][0]
        entry["text_evidence"] = []
        entry["human_scope_reviews"] = [
            {
                "artifact": "正文",
                "scope": "全文",
                "judgment": "逐段复核，未发现该禁止模式。",
            }
        ]
        ledger["execution_summary"] = GATE.calculate_execution_summary(ledger)
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertEqual([], errors)

    def test_changed_text_invalidates_evidence(self) -> None:
        self._write_completed_ledger()
        self.text.write_text("# 正文\n\n证据已经被删掉。\n", encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("写作产物已变化" in error for error in errors))
        self.assertTrue(any("证据原句不在产物中" in error for error in errors))

    def test_workflow_failure_does_not_require_draft_change(self) -> None:
        ledger = self._write_completed_ledger()
        entry = next(
            item
            for item in ledger["skill_rules"]
            if item["applicability"] != "merged"
        )
        entry.update(
            {
                "rule_role": "workflow_gate",
                "classification_confirmed": True,
                "remediation_target": "workflow",
                "requires_text_change": False,
                "outcome": "failed",
            }
        )
        summary = GATE.calculate_execution_summary(ledger)
        self.assertEqual(1, summary["workflow_changes"])
        self.assertEqual(0, summary["draft_changes"])

    def test_only_failed_draft_constraint_can_require_text_change(self) -> None:
        ledger = self._write_completed_ledger()
        entry = next(
            item
            for item in ledger["skill_rules"]
            if item["applicability"] != "merged"
        )
        entry.update(
            {
                "rule_role": "draft_constraint",
                "classification_confirmed": True,
                "remediation_target": "draft",
                "requires_text_change": True,
                "outcome": "failed",
            }
        )
        ledger["execution_summary"] = GATE.calculate_execution_summary(ledger)
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertFalse(any("requires_text_change" in error for error in errors))
        self.assertEqual(1, ledger["execution_summary"]["draft_changes"])

        entry["rule_role"] = "workflow_gate"
        entry["remediation_target"] = "workflow"
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("requires_text_change" in error for error in errors))

    def test_unselected_source_candidate_can_be_not_applicable(self) -> None:
        ledger = self._write_completed_ledger()
        entry = next(
            item
            for asset in ledger["source_assets"]
            for item in asset["rules"]
            if item["applicability"] != "merged"
        )
        entry.update(
            {
                "rule_role": "source_candidate",
                "classification_confirmed": True,
                "remediation_target": "none",
                "requires_text_change": False,
                "applicability": "not_applicable",
                "status": "completed",
                "decision_reason": "该人物偏手与当前人物设定冲突，未选用。",
                "outcome": "not_applicable",
            }
        )
        ledger["execution_summary"] = GATE.calculate_execution_summary(ledger)
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertEqual([], errors)

    def test_source_prohibition_can_pass_with_scope_review(self) -> None:
        ledger = self._write_completed_ledger()
        entry = next(
            item
            for asset in ledger["source_assets"]
            for item in asset["rules"]
            if item["applicability"] != "merged"
        )
        entry.update(
            {
                "rule_role": "source_prohibition",
                "classification_confirmed": True,
                "remediation_target": "audit",
                "text_evidence": [],
                "human_scope_reviews": [
                    {
                        "artifact": "正文",
                        "scope": "全文",
                        "judgment": "逐段复核，未命中禁止照搬内容。",
                    }
                ],
            }
        )
        ledger["execution_summary"] = GATE.calculate_execution_summary(ledger)
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertEqual([], errors)

    def test_exact_duplicate_rules_are_automatically_merged(self) -> None:
        entries = [
            GATE.create_rule_entry(
                "ASSET-RULE",
                f"/tmp/source-{index}/可直接仿写_人物偏手表.md",
                f"hash-{index}",
                "拆书资产族::可直接仿写_人物偏手表.md",
                source_kind="asset_rule",
                variants=[f"人物偏手变体 {index}"],
            )
            for index in range(2)
        ]
        GATE.merge_exact_duplicate_rules(entries)
        canonical, duplicate = entries
        self.assertEqual("merged", duplicate["applicability"])
        self.assertEqual(canonical["id"], duplicate["merged_into"])
        self.assertEqual(2, len(canonical["source_refs"]))
        self.assertEqual(2, len(canonical["cases"]))

    def test_model_review_export_uses_rule_families(self) -> None:
        ledger = self._create_ledger()
        self.ledger_path.write_text(
            json.dumps(ledger, ensure_ascii=False),
            encoding="utf-8",
        )
        output = self.project / "写作资产" / "模型分类批次.json"
        summary = GATE.export_model_review(self.ledger_path, output, batch_size=2)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(summary["entries"], sum(len(b["items"]) for b in payload["batches"]))
        self.assertTrue(payload["batches"][0]["items"][0]["cases"])

    def test_model_group_plan_builds_one_rule_with_multiple_cases(self) -> None:
        ledger = self._create_ledger()
        candidates = ledger["skill_rules"][:2]
        self.ledger_path.write_text(
            json.dumps(ledger, ensure_ascii=False),
            encoding="utf-8",
        )
        plan = self.project / "写作资产" / "模型归并计划.json"
        plan.write_text(
            json.dumps(
                {
                    "groups": [
                        {
                            "canonical_id": candidates[0]["id"],
                            "canonical_rule_text": "同类检查只执行一次，案例分别留证。",
                            "member_ids": [item["id"] for item in candidates],
                            "rule_role": "audit_check",
                            "remediation_target": "audit",
                            "execution_mode": "human",
                            "classification_notes": "模型逐条阅读后确认语义相同。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        errors, results = GATE.apply_model_group_plan(self.ledger_path, plan)
        self.assertEqual([], errors)
        self.assertEqual(2, results[0]["members"])
        updated = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        canonical = next(
            item for item in updated["skill_rules"] if item["id"] == candidates[0]["id"]
        )
        duplicate = next(
            item for item in updated["skill_rules"] if item["id"] == candidates[1]["id"]
        )
        self.assertEqual("同类检查只执行一次，案例分别留证。", canonical["canonical_rule_text"])
        self.assertGreaterEqual(len(canonical["cases"]), 2)
        self.assertEqual(canonical["id"], duplicate["merged_into"])

    def test_missing_merge_canonical_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        _, entry = self._make_manual_merge(ledger)
        entry["merged_into"] = "MISSING"
        entry["canonical_rule_id"] = "MISSING"
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("不存在的 canonical" in error for error in errors))

    def test_merge_cycle_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        canonical, duplicate = self._make_manual_merge(ledger)
        canonical.update(
            {
                "merged_into": duplicate["id"],
                "canonical_rule_id": duplicate["id"],
                "applicability": "merged",
                "outcome": "not_applicable",
            }
        )
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("形成环" in error for error in errors))

    def test_incomplete_merge_canonical_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        canonical, _ = self._make_manual_merge(ledger)
        canonical["status"] = "pending"
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("canonical 尚未完成并裁决" in error for error in errors))

    def test_not_applicable_canonical_can_own_merged_candidates(self) -> None:
        ledger = self._write_completed_ledger()
        canonical, _ = self._make_manual_merge(ledger)
        canonical.update(
            {
                "applicability": "not_applicable",
                "status": "completed",
                "decision_reason": "该候选规则卡本次未选用。",
                "outcome": "not_applicable",
            }
        )
        ledger["execution_summary"] = GATE.calculate_execution_summary(ledger)
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertFalse(any("canonical 尚未完成并裁决" in error for error in errors))

    def test_model_group_plan_flattens_existing_merge_descendants(self) -> None:
        ledger = self._create_ledger()
        entries = ledger["skill_rules"][:3]
        first, intermediate, descendant = entries
        descendant.update(
            {
                "canonical_rule_id": intermediate["id"],
                "merged_into": intermediate["id"],
                "classification_confirmed": True,
                "classification_method": "exact_duplicate",
                "classification_notes": "测试已有精确重复。",
                "applicability": "merged",
                "status": "completed",
                "decision_reason": "测试已有精确重复。",
                "outcome": "not_applicable",
                "result": f"由 {intermediate['id']} 统一执行。",
            }
        )
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        plan = self.project / "写作资产" / "扁平归并计划.json"
        plan.write_text(
            json.dumps(
                {
                    "groups": [
                        {
                            "canonical_id": first["id"],
                            "canonical_rule_text": "最终 canonical 规则。",
                            "member_ids": [first["id"], intermediate["id"]],
                            "rule_role": "audit_check",
                            "remediation_target": "audit",
                            "execution_mode": "human",
                            "classification_notes": "模型确认归并。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        errors, _ = GATE.apply_model_group_plan(self.ledger_path, plan)
        self.assertEqual([], errors)
        updated = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        updated_descendant = next(
            item for item in updated["skill_rules"] if item["id"] == descendant["id"]
        )
        self.assertEqual(first["id"], updated_descendant["merged_into"])

    def test_role_and_remediation_mismatch_is_blocked(self) -> None:
        ledger = self._write_completed_ledger()
        entry = next(
            item
            for item in ledger["skill_rules"]
            if item["applicability"] != "merged"
        )
        entry["rule_role"] = "workflow_gate"
        entry["remediation_target"] = "draft"
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("与修复目标" in error for error in errors))

    def test_script_suggestion_cannot_replace_model_review(self) -> None:
        ledger = self._write_completed_ledger()
        entry = next(
            item
            for item in ledger["skill_rules"]
            if item["applicability"] != "merged"
        )
        entry["classification_method"] = "script_suggestion"
        self.ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_ledger(self.ledger_path)
        self.assertTrue(any("必须经过模型语义复核" in error for error in errors))

    def test_summary_separates_remediation_targets(self) -> None:
        ledger = self._write_completed_ledger()
        entries = [
            entry
            for entry in GATE.iter_execution_entries(ledger)
            if entry["applicability"] != "merged"
        ][:4]
        roles = [
            ("workflow_gate", "workflow"),
            ("setting_constraint", "setting"),
            ("outline_constraint", "outline"),
            ("draft_constraint", "draft"),
        ]
        for entry, (role, target) in zip(entries, roles):
            entry["rule_role"] = role
            entry["classification_confirmed"] = True
            entry["remediation_target"] = target
            entry["outcome"] = "failed"
            entry["requires_text_change"] = role == "draft_constraint"
        summary = GATE.calculate_execution_summary(ledger)
        self.assertEqual(1, summary["workflow_changes"])
        self.assertEqual(1, summary["setting_changes"])
        self.assertEqual(1, summary["outline_changes"])
        self.assertEqual(1, summary["draft_changes"])


if __name__ == "__main__":
    unittest.main()
