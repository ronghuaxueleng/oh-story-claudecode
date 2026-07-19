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


if __name__ == "__main__":
    unittest.main()
