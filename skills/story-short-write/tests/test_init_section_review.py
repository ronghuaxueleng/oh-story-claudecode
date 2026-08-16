from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "init_section_review.py"
SPEC = importlib.util.spec_from_file_location("init_section_review", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InitSectionReviewTest(unittest.TestCase):
    def build_review(self, state: dict, prose: dict, section_id: str, staged_text: str = "") -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(
                json.dumps({"section_id": section_id, "scene_units": [{
                    "scene_id": f"S{section_id}-01",
                    "emotion_beat_ids": state["sections"][0].get("emotion_beat_ids", []),
                    "plot_beat_ids": state["sections"][0].get("plot_beat_ids", []),
                    "summary_only": False,
                }]}),
                encoding="utf-8",
            )
            state["sections"][0]["first_draft_plan_path"] = str(plan_path)
            prose.setdefault("section_generation_plans", [{
                "section_id": section_id,
                "continuous_source_chain_packets": [],
                "dialogue_voice_packets": [],
                "relation_micro_examples": [],
                "character_plan": {"participants": []},
            }])
            return MODULE.build_review(state, prose, section_id, staged_text)

    def test_scaffold_preserves_ids_but_never_approves_semantics(self) -> None:
        state = {"sections": [{
            "section_id": "3", "required_sf_ids": ["SF-04"],
            "emotion_beat_ids": ["E-037"], "plot_beat_ids": ["P-052"],
            "emotion_beat_contracts": [{"beat_id": "E-037", "role": "余望", "intensity": 6}],
            "plot_beat_contracts": [{"beat_id": "P-052", "action": "搬离"}],
        }]}
        dimensions = {name: {"source_evidence": [f"{name}-source"]} for name in MODULE.SF_DIMENSIONS}
        prose = {"source_subflow_reviews": [{"subflow_id": "SF-04", "source_style_granularity": dimensions}]}
        review = self.build_review(state, prose, "3")
        self.assertEqual("pending", review["final_status"])
        beat = review["emotion_review"]["emotion_beat_reviews"][0]
        self.assertEqual("pending", beat["semantic_parity_status"])
        self.assertEqual("", beat["quote"])
        sf = review["prose_review"]["source_subflow_reviews"][0]
        self.assertEqual([], sf["dimension_transfers"]["narrative_voice_and_attitude"]["target_quotes"])

    def test_scaffold_initializes_sf_steps_and_detail_cards_pending(self) -> None:
        state = {"sections": [{
            "section_id": "1", "required_sf_ids": ["SF-01"],
            "required_detail_card_ids": ["DB01"], "emotion_beat_ids": ["E-001"],
            "plot_beat_ids": ["P-001"],
            "emotion_beat_contracts": [{"beat_id": "E-001", "role": "进入", "intensity": 5}],
            "plot_beat_contracts": [{"beat_id": "P-001", "action": "位置换主"}],
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
        review = self.build_review(state, prose, "1")
        sf = review["prose_review"]["source_subflow_reviews"][0]
        self.assertEqual(["先补台", "本人拆台"], [row["source_step"] for row in sf["required_sequence_reviews"]])
        self.assertTrue(all(row["status"] == "pending" for row in sf["required_sequence_reviews"]))
        detail = review["prose_review"]["source_detail_card_reviews"][0]
        self.assertEqual("DB01", detail["card_id"])
        self.assertEqual("pending", detail["status"])
        self.assertNotIn("source_quote", detail)
        self.assertNotIn("category", detail)
        self.assertNotIn(
            "source_evidence",
            sf["dimension_transfers"]["narrative_voice_and_attitude"],
        )
        self.assertIsNone(review["manual_review_provenance"]["semantic_fields_generated_by_script"])

    def test_scaffold_matches_validator_shapes_and_extracts_dialogue_candidates(self) -> None:
        state = {"sections": [{
            "section_id": "1", "required_sf_ids": [], "required_detail_card_ids": [],
            "emotion_beat_ids": ["E-001"], "plot_beat_ids": ["P-001"],
            "emotion_beat_contracts": [{"beat_id": "E-001", "role": "错答", "intensity": 7}],
            "plot_beat_contracts": [{"beat_id": "P-001", "action": "人物离场"}],
        }]}
        prose = {"section_generation_plans": [{
            "section_id": "1",
            "continuous_source_chain_packets": [{"source_excerpt": "chain"}],
            "dialogue_voice_packets": [{"source_excerpt": "dialogue"}],
            "relation_micro_examples": [{
                "source_excerpt": "relation", "target_relation_type": "contrast",
                "target_marking_mode": "explicit", "target_markers": ["但是"],
            }],
            "character_plan": {"participants": [{"character_name": "程雾"}]},
        }]}
        review = self.build_review(state, prose, "1", "她问：“你走吗？”\n他答：“不走。”")
        prose_review = review["prose_review"]
        self.assertEqual(4, len(prose_review["sentence_mappings"]))
        self.assertNotIn("source_excerpt", prose_review["continuous_chain_reviews"][0])
        self.assertNotIn("source_excerpt", prose_review["dialogue_voice_reviews"][0])
        self.assertNotIn("source_excerpt", prose_review["relation_micro_reviews"][0])
        self.assertEqual("contrast", prose_review["relation_micro_reviews"][0]["relation_type"])
        self.assertEqual("程雾", prose_review["character_vitality_review"]["character_reviews"][0]["character_name"])
        self.assertEqual(
            ["“你走吗？”", "“不走。”"],
            [row["quote"] for row in prose_review["dialogue_grounding_review"]["full_dialogue_reviews"]],
        )
        self.assertTrue(
            all(
                row["decision_allowed_values"] == ["keep", "revise"]
                for row in prose_review["dialogue_grounding_review"]["full_dialogue_reviews"]
            )
        )
        self.assertEqual(
            "story-short-write/normalize_section_review.py",
            review["review_scaffold"]["mechanical_contract"]["normalizer"],
        )
        self.assertEqual(
            "story-short-write/manage_section_review.py",
            review["review_scaffold"]["mechanical_contract"]["manual_sidecar_manager"],
        )
        self.assertEqual("S1-01", review["scene_realization_reviews"][0]["scene_id"])


if __name__ == "__main__":
    unittest.main()
