from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_section_context.py"
SPEC = importlib.util.spec_from_file_location("prepare_section_context", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrepareSectionContextTest(unittest.TestCase):
    def test_assembles_complete_ordered_context_without_semantic_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "写作资产"
            assets.mkdir()
            outline = root / "小节大纲.md"
            outline.write_text(
                "# 大纲\n\n## 1. 第一节\n\n第一节内容\n\n## 2. 第二节\n\n第二节内容\n",
                encoding="utf-8",
            )
            plan = assets / "第1节计划.json"
            plan.write_text(
                json.dumps({
                    "section_id": "1",
                    "target_chars": 2000,
                    "scene_units": [{"scene_id": "S1-01"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            prose = assets / "文字合同.json"
            prose.write_text(
                json.dumps({
                    "section_generation_plans": [{
                        "section_id": "1",
                        "character_plan": {"participants": [{"character_name": "甲"}]},
                    }],
                    "source_subflow_reviews": [
                        {"subflow_id": "SF-02"},
                        {"subflow_id": "SF-01"},
                    ],
                    "source_detail_card_reviews": [
                        {"card_id": "D-02"},
                        {"card_id": "D-01"},
                    ],
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            state_path = assets / "逐节正文进度.json"
            state_path.write_text(
                json.dumps({
                    "paths": {
                        "outline": str(outline),
                        "prose_receipt": str(prose),
                    },
                    "sections": [{
                        "section_id": "1",
                        "status": "writing",
                        "min_chars": 1800,
                        "max_chars": 2200,
                        "emotion_beat_ids": ["E-001"],
                        "plot_beat_ids": ["P-001"],
                        "required_sf_ids": ["SF-01", "SF-02"],
                        "required_detail_card_ids": ["D-01", "D-02"],
                        "emotion_beat_contracts": [{"beat_id": "E-001"}],
                        "plot_beat_contracts": [{"beat_id": "P-001"}],
                        "first_draft_plan_path": str(plan),
                        "first_draft_plan_sha256": MODULE.sha256_file(plan),
                    }],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            context = MODULE.build_context(state_path, "1")

            self.assertFalse(context["semantic_judgment_generated_by_script"])
            self.assertIn("第一节内容", context["outline_section"])
            self.assertNotIn("第二节内容", context["outline_section"])
            self.assertEqual(
                ["SF-01", "SF-02"],
                [row["subflow_id"] for row in context["source_subflow_assets"]],
            )
            self.assertEqual(
                ["D-01", "D-02"],
                [row["card_id"] for row in context["source_detail_card_assets"]],
            )
            self.assertEqual(["E-001"], context["required_ids"]["emotion_beat_ids"])
            self.assertEqual(["P-001"], context["required_ids"]["plot_beat_ids"])

    def test_requires_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "state.json"
            state_path.write_text(
                json.dumps({"sections": [{"section_id": "1", "status": "pending"}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "必须先 start-section"):
                MODULE.build_context(state_path, "1")


if __name__ == "__main__":
    unittest.main()
