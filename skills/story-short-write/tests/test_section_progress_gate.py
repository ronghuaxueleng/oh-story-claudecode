from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_section_progress.py"
SPEC = importlib.util.spec_from_file_location("section_progress_gate", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class SectionProgressGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.item = {
            "min_chars": 900,
            "max_chars": 1100,
            "emotion_beat_ids": ["E-001", "E-002", "E-003"],
            "plot_beat_ids": ["P-001", "P-002", "P-003"],
        }

    def valid_plan(self) -> dict:
        return {
            "section_id": "1",
            "mode": "single_pass_scene_realization",
            "target_chars": 1000,
            "append_or_expand_after_target_write_forbidden": True,
            "scene_units": [
                {
                    "scene_id": "S1-01",
                    "emotion_beat_ids": ["E-001", "E-002", "E-003"],
                    "plot_beat_ids": ["P-001", "P-002", "P-003"],
                    "allocated_chars": 1000,
                    "full_scene_required": True,
                    "summary_only": False,
                    "entry_pressure": "女主当众发现自己的席位被换给旧爱。",
                    "interaction_chain": [
                        "女主追问谁动了席牌",
                        "男主用现场安排回避",
                        "女主把席牌从主桌收走",
                    ],
                    "turning_action": "男主亲手把黑伞从妻子手中抽走。",
                    "visible_consequence": "旧爱被护送离场，妻子独自留在主桌。",
                    "aftershock": "女主擦干席牌却没有再把它放回去。",
                    "reader_emotion_path": "公开获得名分的希望被同一人的离场选择翻掉。",
                }
            ],
        }

    def test_complete_scene_plan_passes(self) -> None:
        self.assertEqual([], GATE.validate_first_draft_plan(self.valid_plan(), self.item, "1"))

    def test_underallocated_scene_is_blocked_before_writing(self) -> None:
        plan = self.valid_plan()
        plan["target_chars"] = 200
        plan["scene_units"][0]["allocated_chars"] = 200
        errors = GATE.validate_first_draft_plan(plan, self.item, "1")
        self.assertTrue(any("target_chars" in error for error in errors))
        self.assertTrue(any("梗概" in error for error in errors))

    def test_actual_char_count_allows_twenty_percent_tolerance(self) -> None:
        self.assertEqual((620, 1320), GATE.tolerated_char_range(900, 1100))
        self.assertTrue(GATE.char_count_within_tolerance(720, 900, 1100))
        self.assertTrue(GATE.char_count_within_tolerance(1320, 900, 1100))
        self.assertTrue(GATE.char_count_within_tolerance(620, 900, 1100))
        self.assertFalse(GATE.char_count_within_tolerance(619, 900, 1100))
        self.assertFalse(GATE.char_count_within_tolerance(1321, 900, 1100))

    def test_staged_first_section_allows_missing_committed_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            draft = Path(temp_dir) / "正文.md"
            self.assertEqual(("", []), GATE.load_committed_draft(draft, True))
            self.assertEqual(("", ["正文不存在"]), GATE.load_committed_draft(draft, False))

    def test_chinese_full_name_meets_speaker_identity_floor(self) -> None:
        self.assertGreaterEqual(len("贺庭川"), 2)

    def test_template_semantic_receipt_is_blocked(self) -> None:
        quotes = [f"这是场面中第{index}条互不相同的真实句子。" for index in range(1, 8)]
        section = "\n".join(quotes)
        generic_e = {
            "trigger": "本节中的具体动作触发当前情绪拍。",
            "relationship_position_change": "当前人物的关系位置发生可见变化。",
            "reader_effect": "读者由希望转入更强烈的失望与余痛。",
        }
        generic_p = {
            "action_parity": "目标动作承接了来源情节的主要功能。",
            "external_change": "该动作改变了当前现场的外部状态。",
            "relationship_consequence": "动作后人物之间的关系权利完成转移。",
        }
        review = {
            "first_draft_mode": "single_pass_scene_realization",
            "complete_before_target_write": True,
            "substantive_append_or_expansion_after_target_write": False,
            "scene_realization_reviews": [
                {
                    "scene_id": "S1-01",
                    "emotion_beat_ids": self.item["emotion_beat_ids"],
                    "plot_beat_ids": self.item["plot_beat_ids"],
                    "status": "passed",
                    "summary_only": False,
                    "scene_complete": True,
                    "entry_pressure_quote": quotes[0],
                    "interaction_exchange_quotes": quotes[1:4],
                    "turning_action_quote": quotes[4],
                    "visible_consequence_quote": quotes[5],
                    "aftershock_quote": quotes[6],
                    "reader_emotion_progression": "读者先看见妻子被确认，再看见她被同一人丢在原地。",
                    "why_not_summary": "进场、三轮接招、转折、后果和余波都有互不重复的现场原句。",
                    "manual_judgment": "当前模型逐句核对了人物施压、接招和物件换主的完整过程。",
                }
            ],
            "emotion_review": {
                "emotion_beat_reviews": [dict(generic_e) for _ in range(3)],
                "plot_beat_reviews": [dict(generic_p) for _ in range(3)],
            },
        }
        errors = GATE.validate_scene_realization(review, self.item, section)
        self.assertTrue(any("E 拍语义裁决高度重复" in error for error in errors))
        self.assertTrue(any("P 拍语义裁决高度重复" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
