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
        self.genre_source = self.root / "题材公式.md"
        self.base.write_text(
            "# 测试\n原句一。\n他没说话。\n",
            encoding="utf-8",
        )
        self.text.write_text(
            "# 测试\n原句一。\n他没说话。\n难为他，还知道回来。\n",
            encoding="utf-8",
        )
        self.genre_source.write_text(
            "# 追妻公式\n女主波动必须外显。\n",
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
            if item["id"] == GATE.FULL_TEXT_FLOW_CHECK:
                item["scan_scope"] = "full_text"
                item["remaining_storyboard_or_construction_list"] = False
                item["symptoms_checked"] = [
                    "已检查是否一句一个动作。",
                    "已检查是否一句一个证据。",
                    "已检查是否一句一个反应或规则施工。",
                ]
                item["allowed_in_story_artifacts"] = []
        receipt["genre_formula_review"] = {
            "status": "completed",
            "selected_genre": "现代都市追妻",
            "source_files": [
                {
                    "path": str(self.genre_source.resolve()),
                    "sha256": GATE.sha256(self.genre_source),
                }
            ],
            "rules": [
                {
                    "id": rule_id,
                    "rule": rule_id,
                    "status": "passed",
                    "evidence": [
                        {
                            "quote": "他没说话。",
                            "judgment": "测试正文证据已人工核对。",
                            "action": "keep",
                        }
                    ],
                }
                for rule_id in sorted(GATE.CHASE_WIFE_REQUIRED_RULES)
            ],
            "conclusion": "追妻题材专项规则已逐条复核。",
        }
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
        self.assertEqual(
            len(GATE.CHASE_WIFE_REQUIRED_RULES),
            summary["reviewed_genre_rules"],
        )
        self.assertEqual(1, summary["reviewed_changed_sentences"])

    def test_macro_rhythm_checks_are_mandatory(self) -> None:
        self.assertIn("narrator_voice_distribution", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("long_window_dialogue_efficiency", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("cross_block_rhythm_contrast", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("premise_genre_promise_alignment", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("core_selling_point_payoff", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("ending_action_completion", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("interpersonal_exchange_full_text_review", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("author_substitution_in_exchange", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("conflict_carrier_distribution", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("physical_object_space_consequence", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("irreversible_violence_genre_alignment", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("rule_evidence_stiffness_and_liveliness", GATE.REQUIRED_HUMAN_CHECKS)
        self.assertIn("full_text_storyboard_construction_list_review", GATE.REQUIRED_HUMAN_CHECKS)

        receipt = self._write_completed_receipt()
        receipt["human_checks"] = [
            item
            for item in receipt["human_checks"]
            if item["id"] != "premise_genre_promise_alignment"
        ]
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(
            any(
                "缺少人工检查项: premise_genre_promise_alignment" in error
                for error in errors
            )
        )

    def test_chase_wife_required_genre_rule_is_mandatory(self) -> None:
        receipt = self._write_completed_receipt()
        receipt["genre_formula_review"]["rules"] = [
            item
            for item in receipt["genre_formula_review"]["rules"]
            if item["id"] != "female_softening_externalized"
        ]
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(
            any(
                "追妻题缺少强制专项规则: female_softening_externalized" in error
                for error in errors
            )
        )

    def test_chase_wife_timing_and_trigger_rules_are_mandatory(self) -> None:
        self.assertIn(
            "female_softening_trigger_relevance",
            GATE.CHASE_WIFE_REQUIRED_RULES,
        )
        self.assertIn("irreversible_exit_timing", GATE.CHASE_WIFE_REQUIRED_RULES)

    def test_changed_genre_formula_source_invalidates_receipt(self) -> None:
        self._write_completed_receipt()
        self.genre_source.write_text(
            "# 追妻公式\n女主波动必须外显，情绪后不得追加总结。\n",
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(
            any("题材公式来源已变化，必须重新复核" in error for error in errors)
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

    def test_full_text_storyboard_construction_list_is_blocking(self) -> None:
        receipt = self._write_completed_receipt()
        for item in receipt["human_checks"]:
            if item["id"] == GATE.FULL_TEXT_FLOW_CHECK:
                item["remaining_storyboard_or_construction_list"] = True
                break
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(any("全文仍存在分镜清单或规则施工稿" in error for error in errors))

    def test_in_story_artifact_exception_must_quote_text(self) -> None:
        receipt = self._write_completed_receipt()
        for item in receipt["human_checks"]:
            if item["id"] == GATE.FULL_TEXT_FLOW_CHECK:
                item["allowed_in_story_artifacts"] = [
                    {"quote": "不存在的报告", "reason": "情节中真实出现的报告文本。"}
                ]
                break
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.text)
        self.assertTrue(any("情节内清单/报告例外原句不在正文中" in error for error in errors))

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
