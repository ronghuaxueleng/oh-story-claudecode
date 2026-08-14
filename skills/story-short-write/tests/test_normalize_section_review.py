from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "normalize_section_review.py"
SPEC = importlib.util.spec_from_file_location("normalize_section_review", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NormalizeSectionReviewTest(unittest.TestCase):
    def test_restores_line_breaks_and_normalizes_explicit_dialogue_alias(self) -> None:
        staged = "他做得很自然。\n\n像四年前每一次替我拉椅子。\n\n我信了一秒。\n\n“别走。”"
        review = {
            "prose_review": {
                "sentence_mappings": [{
                    "target_sentence": "他做得很自然。像四年前每一次替我拉椅子。我信了一秒。",
                    "target_surface_evidence": "他做得很自然。像四年前每一次替我拉椅子。我信了一秒。",
                }],
                "dialogue_grounding_review": {
                    "full_dialogue_reviews": [{
                        "quote": "“别走。”",
                        "decision": "passed",
                    }]
                },
            }
        }

        changes, errors = MODULE.normalize_review(review, staged)

        self.assertEqual([], errors)
        self.assertEqual(3, changes)
        mapping = review["prose_review"]["sentence_mappings"][0]
        self.assertIn("\n\n", mapping["target_sentence"])
        self.assertEqual(mapping["target_sentence"], mapping["target_surface_evidence"])
        dialogue = review["prose_review"]["dialogue_grounding_review"]["full_dialogue_reviews"][0]
        self.assertEqual("keep", dialogue["decision"])

    def test_never_populates_pending_semantics(self) -> None:
        staged = "“别走。”"
        review = {
            "prose_review": {
                "sentence_mappings": [{
                    "target_sentence": "",
                    "target_surface_evidence": "",
                }],
                "dialogue_grounding_review": {
                    "full_dialogue_reviews": [{
                        "quote": "“别走。”",
                        "decision": "pending",
                    }]
                },
            }
        }

        changes, errors = MODULE.normalize_review(review, staged)

        self.assertEqual([], errors)
        self.assertEqual(0, changes)
        self.assertEqual(
            "pending",
            review["prose_review"]["dialogue_grounding_review"]["full_dialogue_reviews"][0][
                "decision"
            ],
        )

    def test_blocks_unknown_or_ambiguous_quote_binding(self) -> None:
        staged = "同一句。\n\n同一句。"
        review = {
            "prose_review": {
                "sentence_mappings": [{
                    "target_sentence": "同一句。",
                    "target_surface_evidence": "不存在的证据。",
                }],
                "dialogue_grounding_review": {"full_dialogue_reviews": []},
            }
        }

        _, errors = MODULE.normalize_review(review, staged)

        self.assertTrue(any("不存在" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
