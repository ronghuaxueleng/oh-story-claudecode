from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


GENERATOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "story-short-write"
    / "scripts"
    / "generate_story_profile.py"
)
SPEC = importlib.util.spec_from_file_location("story_profile_generator", GENERATOR_PATH)
assert SPEC and SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)

AUDIT_PATH = (
    Path(__file__).resolve().parents[2]
    / "story-short-write"
    / "scripts"
    / "run_full_ai_audit.py"
)
AUDIT_SPEC = importlib.util.spec_from_file_location("story_full_audit", AUDIT_PATH)
assert AUDIT_SPEC and AUDIT_SPEC.loader
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)


class StoryProfileSceneAssetsTest(unittest.TestCase):
    def test_event_assets_keep_verbs_and_long_phrases(self) -> None:
        assets = GENERATOR.clean_scene_asset_terms(
            [
                "宋远让董事会撤掉周逢雅的代言并收回资源",
                "匿名视频公开后婚礼秩序当场翻转",
            ]
        )
        self.assertEqual(
            [
                "宋远让董事会撤掉周逢雅的代言并收回资源",
                "匿名视频公开后婚礼秩序当场翻转",
            ],
            assets,
        )

    def test_guardrail_merge_prefers_early_canonical_items_and_caps_lists(self) -> None:
        canonical = {
            "character_face_split": {
                "different_face_evidence": [f"主来源人物证据{i}" for i in range(1, 7)],
                "reaction_order_split": [f"主来源反应顺序{i}" for i in range(1, 5)],
            },
            "consequence_structure": {
                "tail_entry_owner": ["女主回家", "孩子开门"],
            },
        }
        auxiliary = {
            "character_face_split": {
                "different_face_evidence": [f"辅助重复解释{i}" for i in range(1, 10)],
                "reaction_order_split": [f"辅助反应顺序{i}" for i in range(1, 8)],
            },
            "consequence_structure": {
                "tail_entry_owner": ["前夫忏悔", "反派余波", "旁观者总结"],
            },
        }
        merged = GENERATOR.merge_story_guardrail_dicts(canonical, auxiliary)
        self.assertEqual(
            [f"主来源人物证据{i}" for i in range(1, 7)],
            merged["character_face_split"]["different_face_evidence"],
        )
        self.assertEqual(4, len(merged["character_face_split"]["reaction_order_split"]))
        self.assertEqual(["女主回家", "孩子开门"], merged["consequence_structure"]["tail_entry_owner"])

    def test_sample_grading_parser_keeps_layer_grades(self) -> None:
        parsed = GENERATOR.parse_sample_grading_text(
            "## 1. 样本等级\n"
            "- 样本等级：B类骨架样本\n"
            "- structure_grade：A\n"
            "- performance_grade：A\n"
            "- sentence_grade：B\n"
            "- terminal_consequence_grade：C\n"
            "## 2. 可学层\n"
            "- 正向DNA层：人物口气、动作落点\n"
            "- 仅骨架层：句法切分\n"
            "- 反面规则层：终局清算\n"
        )
        grading = parsed["sample_grading"]
        self.assertEqual("A", grading["structure_grade"])
        self.assertEqual("B", grading["sentence_grade"])
        self.assertEqual(["人物口气", "动作落点"], parsed["positive_dna_layers"])

    def test_layer_grade_overrides_whole_book_negative_summary(self) -> None:
        guidance = AUDIT.build_sample_grading_guidance(
            {
                "sample_grading": {
                    "level": "C类负样本",
                    "dna_usable": "不可",
                    "structure_grade": "B",
                    "performance_grade": "A",
                    "sentence_grade": "A",
                    "terminal_consequence_grade": "C",
                    "positive_dna_layers": ["人物口气", "句法节拍"],
                    "skeleton_only_layers": ["结构"],
                    "negative_rule_layers": ["终局清算"],
                    "final_verdict": {"allow_dna": "否", "negative_only": "是"},
                }
            }
        )
        self.assertEqual("A", guidance["sentence_grade"])
        self.assertFalse(
            any("不可并入正向融合" in item for item in guidance["hard_stops"])
        )
        self.assertTrue(
            any("实际调用服从四层 grade" in item for item in guidance["audit_notes"])
        )

    def test_clause_style_assets_preserve_complete_comma_phrases(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 11. style_assets 原始材料\n"
            "- character_bias：谁打你，你就打回去\n"
            "- dialogue_bridges：骚乱，就是从这一刻开始的\n"
        )
        self.assertEqual(
            ["谁打你，你就打回去"],
            parsed["style_assets"]["character_bias"],
        )
        self.assertEqual(
            ["骚乱，就是从这一刻开始的"],
            parsed["style_assets"]["dialogue_bridges"],
        )

    def test_clause_style_cleaner_does_not_split_on_comma(self) -> None:
        self.assertEqual(
            ["我闯祸，她兜底"],
            GENERATOR.clean_style_asset_terms(
                ["我闯祸，她兜底"],
                preserve_commas=True,
            ),
        )

    def test_explicit_style_asset_is_not_rejected_for_semantic_words(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 11. style_assets 原始材料\n"
            "- misdirection：我不是替身\n"
            "- dialogue_bridges：为什么不要我\n"
        )
        self.assertEqual(["我不是替身"], parsed["style_assets"]["misdirection"])
        self.assertEqual(["为什么不要我"], parsed["style_assets"]["dialogue_bridges"])

    def test_explicit_scene_asset_is_not_rejected_as_explanation(self) -> None:
        self.assertEqual(
            ["不是她推人，而是他自己滑倒"],
            GENERATOR.clean_scene_asset_terms(["不是她推人，而是他自己滑倒"]),
        )


if __name__ == "__main__":
    unittest.main()
