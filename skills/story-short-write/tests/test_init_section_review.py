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


if __name__ == "__main__":
    unittest.main()
