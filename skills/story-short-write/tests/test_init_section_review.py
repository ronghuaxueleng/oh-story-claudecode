from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "init_section_review.py"
SPEC = importlib.util.spec_from_file_location("init_section_review", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InitSectionReviewTest(unittest.TestCase):
    def test_scaffold_preserves_ids_but_never_approves_semantics(self) -> None:
        state = {"sections": [{
            "section_id": "3", "required_sf_ids": ["SF-04"],
            "emotion_beat_ids": ["E-037"], "plot_beat_ids": ["P-052"],
            "emotion_beat_contracts": [{"beat_id": "E-037", "role": "余望", "intensity": 6}],
            "plot_beat_contracts": [{"beat_id": "P-052", "action": "搬离"}],
        }]}
        dimensions = {name: {"source_evidence": [f"{name}-source"]} for name in MODULE.SF_DIMENSIONS}
        prose = {"source_subflow_reviews": [{"subflow_id": "SF-04", "source_style_granularity": dimensions}]}
        review = MODULE.build_review(state, prose, "3")
        self.assertEqual("pending", review["final_status"])
        beat = review["emotion_review"]["emotion_beat_reviews"][0]
        self.assertEqual("pending", beat["semantic_parity_status"])
        self.assertEqual("", beat["quote"])
        sf = review["prose_review"]["source_subflow_reviews"][0]
        self.assertEqual([], sf["dimension_transfers"]["narrative_voice_and_attitude"]["target_quotes"])

    def test_scaffold_initializes_sf_steps_and_detail_cards_pending(self) -> None:
        state = {"sections": [{
            "section_id": "1", "required_sf_ids": ["SF-01"],
            "required_detail_card_ids": ["DB01"], "emotion_beat_ids": [],
            "plot_beat_ids": [], "emotion_beat_contracts": [], "plot_beat_contracts": [],
        }]}
        dimensions = {name: {"source_evidence": []} for name in MODULE.SF_DIMENSIONS}
        prose = {
            "source_subflow_reviews": [{
                "subflow_id": "SF-01", "required_sequence": ["先补台", "本人拆台"],
                "source_style_granularity": dimensions,
            }],
            "source_detail_card_reviews": [{
                "card_id": "DB01", "category": "对白", "title": "否定句",
                "source_quote": "不爱", "distinct_function_to_preserve": "平静撤销关系前提",
            }],
        }
        review = MODULE.build_review(state, prose, "1")
        sf = review["prose_review"]["source_subflow_reviews"][0]
        self.assertEqual(["先补台", "本人拆台"], [row["source_step"] for row in sf["required_sequence_reviews"]])
        self.assertTrue(all(row["status"] == "pending" for row in sf["required_sequence_reviews"]))
        detail = review["prose_review"]["source_detail_card_reviews"][0]
        self.assertEqual("DB01", detail["card_id"])
        self.assertEqual("pending", detail["status"])
        self.assertIsNone(review["manual_review_provenance"]["semantic_fields_generated_by_script"])


if __name__ == "__main__":
    unittest.main()
