from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_post_write_human_review_gate.py"
)
SPEC = importlib.util.spec_from_file_location("post_write_human_review_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class PostWriteHumanReviewGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.base = self.root / "母稿.md"
        self.text = self.root / "正文.md"
        self.receipt = self.root / "人工语义复核回执.json"
        self.base.write_text(
            "# 测试\n原句一。\n他没说话。\n",
            encoding="utf-8",
        )
        self.text.write_text(
            "# 测试\n原句一。\n他没说话。\n难为他，还知道回来。\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_completed_receipt(self) -> dict:
        receipt = GATE.create_receipt("测试项目", self.text, self.base)
        receipt["gate_status"] = "passed"
        receipt["automation_limits_acknowledged"] = True
        receipt["reviewed_full_text"] = True
        receipt["confirmed_after_final_revision"] = True
        receipt["automated_scan"] = {
            "status": "completed",
            "artifacts": ["全量审计报告.json"],
            "summary": "脚本预扫完成；语义结论仍由人工复核。",
        }
        for item in receipt["human_checks"]:
            item["status"] = "passed"
            item["evidence"] = [
                {
                    "quote": "他没说话。",
                    "judgment": "这是现场动作，不替人物总结动机。",
                    "action": "keep",
                }
            ]
            item["conclusion"] = "已人工复核全文。"
        for item in receipt["changed_sentence_reviews"]:
            item.update(
                {
                    "status": "reviewed",
                    "scene_observable_basis": "紧接人物回家这一现场动作。",
                    "narrator_or_author": "narrator_voice",
                    "redundant_explanation": False,
                    "substitutes_character_motive": False,
                    "decision": "keep",
                    "reason": "是叙述者当场评价，不解释人物内心。",
                }
            )
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return receipt

    def test_revision_diff_discovers_changed_sentence(self) -> None:
        receipt = GATE.create_receipt("测试项目", self.text, self.base)
        self.assertEqual("revision_diff", receipt["review_mode"])
        self.assertEqual(1, len(receipt["changed_sentence_reviews"]))
        self.assertEqual(
            "难为他，还知道回来。",
            receipt["changed_sentence_reviews"][0]["quote"],
        )

    def test_pending_manual_review_is_blocked(self) -> None:
        receipt = GATE.create_receipt("测试项目", self.text, self.base)
        self.receipt.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(any("人工检查项尚未通过" in error for error in errors))
        self.assertTrue(any("改写句尚未人工复核" in error for error in errors))

    def test_complete_manual_review_passes(self) -> None:
        self._write_completed_receipt()
        errors, summary = GATE.validate_receipt(self.receipt, self.text)
        self.assertEqual([], errors)
        self.assertEqual(len(GATE.REQUIRED_HUMAN_CHECKS), summary["reviewed_human_checks"])
        self.assertEqual(1, summary["reviewed_changed_sentences"])

    def test_macro_rhythm_checks_are_mandatory(self) -> None:
        self.assertIn("narrator_voice_distribution", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("long_window_dialogue_efficiency", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("cross_block_rhythm_contrast", GATE.REQUIRED_HUMAN_CHECKS)

        receipt = self._write_completed_receipt()
        receipt["human_checks"] = [
            item
            for item in receipt["human_checks"]
            if item["id"] != "narrator_voice_distribution"
        ]
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(
            any("缺少人工检查项: narrator_voice_distribution" in error for error in errors)
        )

    def test_changed_text_invalidates_receipt(self) -> None:
        self._write_completed_receipt()
        self.text.write_text(
            self.text.read_text(encoding="utf-8") + "又改了一句。\n",
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(any("正文已变化" in error for error in errors))
        self.assertTrue(any("改写句缺少人工复核" in error for error in errors))

    def test_author_summary_cannot_pass_as_current_text(self) -> None:
        receipt = self._write_completed_receipt()
        receipt["changed_sentence_reviews"][0]["narrator_or_author"] = "author_summary"
        receipt["changed_sentence_reviews"][0]["decision"] = "revise"
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(any("必须先改正文再重建回执" in error for error in errors))

    def test_full_text_mode_does_not_require_base(self) -> None:
        receipt = GATE.create_receipt("测试项目", self.text)
        self.assertEqual("full_text", receipt["review_mode"])
        self.assertEqual([], receipt["changed_sentence_reviews"])

    def test_line_reflow_is_not_a_semantic_change(self) -> None:
        self.base.write_text(
            "# 测试\n第一句话。第二句话很长，但内容没有变化。\n",
            encoding="utf-8",
        )
        self.text.write_text(
            "# 测试\n第一句话。\n第二句话很长，但内容没有变化。\n",
            encoding="utf-8",
        )
        receipt = GATE.create_receipt("测试项目", self.text, self.base)
        self.assertEqual([], receipt["changed_sentence_reviews"])


if __name__ == "__main__":
    unittest.main()
