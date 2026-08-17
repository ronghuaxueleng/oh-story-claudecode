from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BATCH_SCRIPT = ROOT / "scripts" / "batch_rule_model_review.py"
BATCH_SPEC = importlib.util.spec_from_file_location("batch_rule_model_review", BATCH_SCRIPT)
assert BATCH_SPEC and BATCH_SPEC.loader
BATCH = importlib.util.module_from_spec(BATCH_SPEC)
BATCH_SPEC.loader.exec_module(BATCH)

LEDGER_SCRIPT = ROOT / "scripts" / "validate_rule_execution_ledger.py"
LEDGER_SPEC = importlib.util.spec_from_file_location("rule_execution_ledger_for_batch_review", LEDGER_SCRIPT)
assert LEDGER_SPEC and LEDGER_SPEC.loader
LEDGER = importlib.util.module_from_spec(LEDGER_SPEC)
LEDGER_SPEC.loader.exec_module(LEDGER)


class BatchRuleModelReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.skill_root = self.root / "story-short-write"
        self.project_dir = self.root / "项目"
        self.source = self.root / "拆文库" / "样本"
        self.writing_receipt = self.project_dir / "写作资产" / "写作规则读取回执.json"
        self.source_receipt = self.project_dir / "写作资产" / "拆文读取回执.json"
        self.ledger = self.project_dir / "写作资产" / "规则执行台账.json"
        self.review_manifest = self.project_dir / "写作资产" / "规则模型分类批次.json"
        self.group_plan = self.project_dir / "写作资产" / "规则模型归并计划.json"
        self._build_skill_files()
        self._build_source_files()
        self._build_receipts()
        self._build_ledger()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _build_skill_files(self) -> None:
        for relative in LEDGER.CORE_SKILL_RULE_FILES:
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
            "| 人物 | 偏手 | 使用规则 |\n|---|---|---|\n| 主角 | 紧张时摸杯沿 | 至少跨场复现两次 |\n",
            encoding="utf-8",
        )
        report = self.source / "拆文报告.md"
        report.write_text("# 报告\n\n这是一份整体分析。\n", encoding="utf-8")
        facts = self.source / "事实与推断台账.md"
        facts.write_text("# 事实与推断台账\n\n- 必须保持事实边界。\n", encoding="utf-8")
        bridge = self.source / "写作资产" / "桥段施工卡.md"
        bridge.parent.mkdir(parents=True, exist_ok=True)
        bridge.write_text(
            "# 桥段施工卡\n\n## 关键桥\n\n- 必须保留的承重件：权限先失效，再出现替代者。\n",
            encoding="utf-8",
        )

    def _build_receipts(self) -> None:
        self.writing_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.writing_receipt.write_text(
            json.dumps(
                {
                    "gate_status": "passed",
                    "files": [
                        {
                            "path": relative,
                            "sha256": LEDGER.sha256(self.skill_root / relative),
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
        for path in sorted(self.source.rglob("*")):
            if not path.is_file():
                continue
            source_files.append(
                {
                    "path": path.relative_to(self.source).as_posix(),
                    "sha256": LEDGER.sha256(path),
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

    def _build_ledger(self) -> None:
        ledger, errors = LEDGER.create_ledger(
            "测试项目",
            self.writing_receipt,
            self.source_receipt,
            self.skill_root,
        )
        self.assertEqual([], errors)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _mark_plan_ready(self) -> None:
        payload = json.loads(self.group_plan.read_text(encoding="utf-8"))
        payload["reviewed_by_current_model"] = True
        payload["semantic_fields_generated_by_script"] = False
        for group in payload["groups"]:
            group["canonical_rule_text"] = "统一后的可执行规则。"
            group["taxonomy_decision"] = "accept_suggestions"
            group["classification_notes"] = "当前模型逐例确认执行动作一致。"
            group["applicability"] = "not_applicable"
            group["decision_reason"] = "当前项目写前不采用这一组规则。"
        self.group_plan.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_prepare_model_review_exports_manifest_and_plan(self) -> None:
        errors, summary = BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=10,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.review_manifest.is_file())
        self.assertTrue(self.group_plan.is_file())
        self.assertGreater(summary["entries"], 0)
        self.assertGreater(summary["groups"], 0)

    def test_status_reports_pending_manual_plan(self) -> None:
        BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=10,
        )
        status = BATCH.inspect_rule_model_review_status(
            project="测试项目",
            project_dir=self.project_dir,
        )
        self.assertEqual("active", status["review_manifest"]["status"])
        self.assertEqual("active", status["group_plan"]["status"])
        self.assertFalse(status["group_plan"]["reviewed_by_current_model"])
        self.assertFalse(status["prewrite_ready"])

    def test_inspect_model_review_batch_writes_full_payload_and_compact_status(self) -> None:
        BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=10,
        )
        payload = BATCH.inspect_model_review_batch(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_number=1,
        )
        output = Path(payload["output"])
        self.assertTrue(output.is_file())
        self.assertEqual(1, payload["batch"])
        self.assertGreater(len(payload["expanded_batch"]["items"]), 0)
        self.assertEqual(
            len(payload["expanded_batch"]["items"]),
            len(payload["index"]),
        )
        self.assertGreater(payload["global_plan_status"]["pending_groups"], 0)
        self.assertGreater(
            payload["global_plan_status"]["missing_fields"]["applicability"],
            0,
        )
        self.assertTrue(
            all("case_count" in item and "source_ref_count" in item for item in payload["index"])
        )

    def test_inspect_model_review_batch_handles_null_plan_groups(self) -> None:
        BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=10,
        )
        plan = json.loads(self.group_plan.read_text(encoding="utf-8"))
        plan["groups"] = None
        self.group_plan.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        payload = BATCH.inspect_model_review_batch(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_number=1,
        )
        self.assertFalse(payload["global_plan_status"]["groups_field_is_list"])
        self.assertEqual(0, payload["global_plan_status"]["groups"])
        self.assertTrue(
            all(item["missing_fields"] == ["plan_group"] for item in payload["index"])
        )

    def test_inspect_model_review_batch_reports_invalid_taxonomy(self) -> None:
        BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=10,
        )
        plan = json.loads(self.group_plan.read_text(encoding="utf-8"))
        group = plan["groups"][0]
        group["canonical_rule_text"] = "统一后的可执行规则。"
        group["taxonomy_decision"] = "override"
        group["taxonomy"] = {
            "rule_role": "custom_role",
            "remediation_target": "draft",
            "execution_mode": "human",
        }
        group["classification_notes"] = "当前模型人工改写分类。"
        group["applicability"] = "not_applicable"
        group["decision_reason"] = "当前项目不采用。"
        self.group_plan.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        payload = BATCH.inspect_model_review_batch(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_number=1,
        )
        self.assertEqual(
            1,
            payload["global_plan_status"]["validation_issues"]["invalid_rule_role"],
        )
        self.assertIn(
            "invalid_rule_role:custom_role",
            payload["index"][0]["validation_issues"],
        )

    def test_inspect_all_model_review_batches_writes_every_batch_and_summary(self) -> None:
        _, summary = BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=2,
        )
        payload = BATCH.inspect_all_model_review_batches(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
        )
        self.assertEqual(summary["batches"], payload["batch_count"])
        self.assertEqual(summary["entries"], payload["entry_count"])
        self.assertTrue(Path(payload["output"]).is_file())
        self.assertEqual(
            list(range(1, payload["batch_count"] + 1)),
            [item["batch"] for item in payload["batch_outputs"]],
        )
        self.assertTrue(
            all(Path(item["output"]).is_file() for item in payload["batch_outputs"])
        )

    def test_export_pending_groups_contains_only_incomplete_groups(self) -> None:
        BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=10,
        )
        plan = json.loads(self.group_plan.read_text(encoding="utf-8"))
        first = plan["groups"][0]
        first["canonical_rule_text"] = "已完成规则。"
        first["taxonomy_decision"] = "accept_suggestions"
        first["classification_notes"] = "当前模型已确认。"
        first["applicability"] = "not_applicable"
        first["decision_reason"] = "当前项目不采用。"
        self.group_plan.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        payload = BATCH.export_pending_groups(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
        )
        self.assertTrue(Path(payload["output"]).is_file())
        self.assertEqual(len(plan["groups"]) - 1, payload["pending_group_count"])
        self.assertNotIn(
            first["canonical_id"],
            {item["canonical_id"] for item in payload["groups"]},
        )
        self.assertTrue(all(item["missing_fields"] for item in payload["groups"]))

    def test_next_step_recommends_prepare_then_manual_then_run(self) -> None:
        suggestion = BATCH.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=12,
        )
        self.assertEqual("prepare_model_review", suggestion["action"])
        self.assertIn('batch_rule_model_review.py" prepare-model-review', suggestion["next_command"])

        BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=12,
        )
        suggestion = BATCH.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=12,
        )
        self.assertEqual("complete_manual_group_plan", suggestion["action"])
        self.assertIn(
            'batch_rule_model_review.py" export-pending-groups',
            suggestion["next_command"],
        )
        self.assertIn(
            'batch_rule_model_review.py" inspect-all-model-review-batches',
            suggestion["inspect_all_command"],
        )

        self._mark_plan_ready()
        suggestion = BATCH.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=12,
        )
        self.assertEqual("apply_model_groups", suggestion["action"])
        self.assertIn('batch_rule_model_review.py" run-model-review-cycle', suggestion["next_command"])

    def test_run_cycle_applies_and_consumes_sidecars(self) -> None:
        BATCH.prepare_model_review(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=20,
        )
        self._mark_plan_ready()
        result = BATCH.run_model_review_cycle(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=20,
        )
        self.assertEqual("apply_model_groups", result["action"])
        self.assertTrue(result["prewrite_ready"])
        consumed_review = json.loads(self.review_manifest.read_text(encoding="utf-8"))
        consumed_plan = json.loads(self.group_plan.read_text(encoding="utf-8"))
        self.assertEqual("consumed", consumed_review["status"])
        self.assertEqual("consumed", consumed_plan["status"])

    def test_emit_shell_template_contains_high_level_commands(self) -> None:
        template = BATCH.emit_shell_template(
            project="测试项目",
            project_dir=self.project_dir,
            ledger=None,
            review_manifest=None,
            group_plan=None,
            batch_size=16,
        )
        self.assertIn('batch_rule_model_review.py" prepare-model-review', template)
        self.assertIn('batch_rule_model_review.py" status', template)
        self.assertIn('batch_rule_model_review.py" inspect-all-model-review-batches', template)
        self.assertIn('batch_rule_model_review.py" export-pending-groups', template)
        self.assertIn('batch_rule_model_review.py" next-step', template)
        self.assertIn('batch_rule_model_review.py" run-model-review-cycle', template)


if __name__ == "__main__":
    unittest.main()
