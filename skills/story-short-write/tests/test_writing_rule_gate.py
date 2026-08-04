from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_writing_rule_gate.py"
SPEC = importlib.util.spec_from_file_location("writing_rule_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class WritingRuleGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.skill_root = self.root / "story-short-write"
        self.receipt_path = self.root / "项目" / "写作资产" / "写作规则读取回执.json"
        for relative in GATE.REQUIRED_RULES:
            path = self.skill_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {path.stem}\n\n规则证据\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_completed_receipt(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目", self.skill_root)
        self.assertEqual([], errors)
        receipt["gate_status"] = "passed"
        receipt["confirmed_before_outline"] = True
        receipt["confirmed_before_draft"] = True
        for item in receipt["files"]:
            item["status"] = "read"
            item["evidence_terms"] = ["规则证据"]
            item["takeaways"] = ["已读取当前规则并提取写前约束"]
            item["used_for"] = ["设定、大纲与正文"]
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_pending_receipt_is_blocked(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目", self.skill_root)
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False),
            encoding="utf-8",
        )
        validation_errors, _ = GATE.validate_receipt(
            self.receipt_path,
            skill_root=self.skill_root,
        )
        self.assertTrue(any("gate_status" in error for error in validation_errors))
        self.assertTrue(any("尚未标记已读" in error for error in validation_errors))

    def test_complete_receipt_passes(self) -> None:
        self._write_completed_receipt()
        validation_errors, summary = GATE.validate_receipt(
            self.receipt_path,
            skill_root=self.skill_root,
        )
        self.assertEqual([], validation_errors)
        self.assertEqual(len(GATE.REQUIRED_RULES), summary["read_count"])

    def test_builtin_reviews_complete_current_skill_rules_without_model_loop(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目")
        self.assertEqual([], errors)
        self.assertEqual([], GATE.apply_builtin_rule_reviews(receipt))
        self.assertEqual("passed", receipt["gate_status"])
        self.assertEqual("builtin_sha_bound", receipt["review_mode"])
        self.assertTrue(all(item["status"] == "read" for item in receipt["files"]))

    def test_changed_rule_requires_reread(self) -> None:
        self._write_completed_receipt()
        path = self.skill_root / "references/anti-ai-writing.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "新增规则",
            encoding="utf-8",
        )
        validation_errors, _ = GATE.validate_receipt(
            self.receipt_path,
            skill_root=self.skill_root,
        )
        self.assertTrue(any("规则文件已变化" in error for error in validation_errors))

    def test_missing_narrator_voice_is_blocked(self) -> None:
        (self.skill_root / "references/craft/narrator-voice.md").unlink()
        _, errors = GATE.create_receipt("测试项目", self.skill_root)
        self.assertTrue(any("narrator-voice.md" in error for error in errors))

    def test_retroactive_receipt_is_blocked(self) -> None:
        output = self.root / "项目" / "正文.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("正文", encoding="utf-8")
        old_time = time.time() - 20
        os.utime(output, (old_time, old_time))
        self._write_completed_receipt()
        validation_errors, _ = GATE.validate_receipt(
            self.receipt_path,
            [output],
            self.skill_root,
        )
        self.assertTrue(any("事后补填" in error for error in validation_errors))

    def test_builtin_sha_bound_receipt_can_be_refreshed_after_existing_output(self) -> None:
        output = self.root / "项目" / "正文.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("正文", encoding="utf-8")
        receipt, errors = GATE.create_receipt("测试项目")
        self.assertEqual([], errors)
        self.assertEqual([], GATE.apply_builtin_rule_reviews(receipt))
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        GATE.atomic_write_json(self.receipt_path, receipt)
        validation_errors, _ = GATE.validate_receipt(self.receipt_path, [output])
        self.assertEqual([], validation_errors)

    def test_rule_review_task_contains_complete_rule_content(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目", self.skill_root)
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        GATE.atomic_write_json(self.receipt_path, receipt)

        task, task_errors = GATE.build_rule_review_task(
            self.receipt_path,
            self.skill_root,
        )

        self.assertEqual([], task_errors)
        self.assertEqual(
            set(GATE.REQUIRED_RULES),
            {item["path"] for item in task["files"]},
        )
        self.assertTrue(
            all("规则证据" in item["content"] for item in task["files"])
        )

    def test_rule_review_result_atomically_completes_receipt(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目", self.skill_root)
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        GATE.atomic_write_json(self.receipt_path, receipt)
        task, task_errors = GATE.build_rule_review_task(
            self.receipt_path,
            self.skill_root,
        )
        self.assertEqual([], task_errors)
        task_path = self.receipt_path.with_name("规则语义输入.json")
        GATE.atomic_write_json(task_path, task)
        result = task["result_template"]
        result["task_sha256"] = GATE.sha256(task_path)
        for item in result["reviews"]:
            item["review"] = {
                "status": "read",
                "evidence_terms": ["规则证据"],
                "takeaways": ["已读取当前规则并提取写前约束"],
                "used_for": ["设定、大纲与正文"],
            }
        result_path = self.receipt_path.with_name("规则语义输出.json")
        GATE.atomic_write_json(result_path, result)

        apply_errors = GATE.apply_rule_review_result(
            self.receipt_path,
            task_path,
            result_path,
            skill_root=self.skill_root,
        )

        self.assertEqual([], apply_errors)
        applied = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("passed", applied["gate_status"])
        self.assertTrue(applied["confirmed_before_outline"])
        self.assertTrue(applied["confirmed_before_draft"])

    def test_rule_review_rejects_stale_task_without_changing_receipt(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目", self.skill_root)
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        GATE.atomic_write_json(self.receipt_path, receipt)
        task, task_errors = GATE.build_rule_review_task(
            self.receipt_path,
            self.skill_root,
        )
        self.assertEqual([], task_errors)
        task_path = self.receipt_path.with_name("规则语义输入.json")
        GATE.atomic_write_json(task_path, task)
        result = task["result_template"]
        result["task_sha256"] = "stale"
        result_path = self.receipt_path.with_name("规则语义输出.json")
        GATE.atomic_write_json(result_path, result)

        apply_errors = GATE.apply_rule_review_result(
            self.receipt_path,
            task_path,
            result_path,
            skill_root=self.skill_root,
        )

        self.assertTrue(any("任务 SHA" in error for error in apply_errors))
        unchanged = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("pending", unchanged["gate_status"])


if __name__ == "__main__":
    unittest.main()
