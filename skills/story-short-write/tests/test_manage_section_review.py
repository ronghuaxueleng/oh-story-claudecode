from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "manage_section_review.py"
SPEC = importlib.util.spec_from_file_location("manage_section_review", SCRIPT)
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class ManageSectionReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.staged = self.root / "第1节.md"
        self.review = self.root / "第1节.json"
        self.sidecar = self.root / "第1节人工侧车.json"
        self.staged.write_text(
            "他把名牌扶正。\n\n“别走。”她说。\n\n我没有追出去。\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_review(self, passed: bool) -> dict:
        status = "passed" if passed else "pending"
        judgment = "当前模型完整通读本节并逐项完成语义裁决。" if passed else ""
        review = {
            "section_id": "1",
            "review_scaffold": {"generator": "story-short-write/init_section_review.py"},
            "manual_review_provenance": {
                "performed_by_current_model": True if passed else None,
                "full_section_read_by_current_model": True if passed else None,
                "semantic_fields_generated_by_script": False if passed else None,
                "project_scripts_used_for_semantic_population": [],
                "manual_judgment": judgment,
            },
            "positive_generation_constraints": [
                "约束一", "约束二", "约束三", "约束四", "约束五"
            ] if passed else [],
            "issues_fixed": [],
            "final_status": status,
            "prose_review": {
                "status": status,
                "sentence_mappings": [{
                    "target_sentence": "他把名牌扶正。" if passed else "",
                    "source_anchor_sentence": "她把杯子放稳。" if passed else "",
                    "target_surface_evidence": "他把名牌扶正。" if passed else "",
                    "source_surface_evidence": "把杯子放稳" if passed else "",
                    "feature_ids": ["LM-01", "EP-01"] if passed else [],
                    "language_mechanism_match": "以具体物件动作完成关系位置变化。" if passed else "",
                    "contract_used_during_writing": True if passed else None,
                }],
                "continuous_chain_reviews": [],
                "dialogue_voice_reviews": [],
                "relation_micro_reviews": [],
                "source_subflow_reviews": [],
                "source_detail_card_reviews": [],
                "liveliness_review": {
                    "target_live_sentences": [
                        "他把名牌扶正。",
                        "“别走。”",
                        "我没有追出去。",
                    ] if passed else []
                },
                "character_vitality_review": {
                    "character_reviews": [{
                        "character_name": "程雾",
                        "target_quotes": ["他把名牌扶正。", "我没有追出去。"] if passed else [],
                        "evidence_ownership_reviews": [
                            {
                                "quote": "他把名牌扶正。",
                                "ownership_context": "她习惯用物件动作收回自己的位置。",
                                "keep_or_revise": "keep",
                            },
                            {
                                "quote": "我没有追出去。",
                                "ownership_context": "她选择留在原地承担现实后果。",
                                "keep_or_revise": "keep",
                            },
                        ] if passed else [],
                        "interchangeability_judgment": "两个动作都来自她不追人而收回现实位置的选择。" if passed else "",
                    }]
                },
                "dialogue_grounding_review": {
                    "full_dialogue_reviews": [{
                        "quote": "“别走。”",
                        "speaker": "许棠" if passed else "",
                        "scene_pressure": "对方即将离场" if passed else "",
                        "turn_connection": "承接转身动作" if passed else "",
                        "interchangeability_judgment": "只属于此刻求留的人" if passed else "",
                        "decision": "keep" if passed else "pending",
                    }]
                },
            },
            "emotion_review": {
                "status": status,
                "emotion_beat_reviews": [{
                    "beat_id": "E-001",
                    "role": "希望落空",
                    "intensity": 7,
                    "quote": "我没有追出去。" if passed else "",
                    "trigger": "对方转身离场" if passed else "",
                    "relationship_position_change": "她停止追逐并收回主动权" if passed else "",
                    "reader_effect": "读者感到关系已经断开" if passed else "",
                    "judgment": "动作与情绪烈度保持等价" if passed else "",
                    "semantic_parity_status": status,
                }],
                "plot_beat_reviews": [{
                    "beat_id": "P-001",
                    "quote": "他把名牌扶正。" if passed else "",
                    "action_parity": "人物扶正自己的名牌" if passed else "",
                    "external_change": "公开位置重新明确" if passed else "",
                    "relationship_consequence": "她不再等待他人确认" if passed else "",
                    "judgment": "动作与后果在同一现场闭合" if passed else "",
                    "semantic_parity_status": status,
                }],
            },
            "scene_realization_reviews": [{
                "scene_id": "S1-01",
                "status": status,
                "scene_complete": True if passed else None,
                "entry_pressure_quote": "他把名牌扶正。" if passed else "",
                "interaction_exchange_quotes": [
                    "他把名牌扶正。", "“别走。”", "我没有追出去。"
                ] if passed else [],
                "turning_action_quote": "“别走。”她说。" if passed else "",
                "visible_consequence_quote": "我没有追出去。" if passed else "",
                "aftershock_quote": "他把名牌扶正。" if passed else "",
                "reader_emotion_progression": "希望被一句挽留抬起，又被不追的动作压回现实。" if passed else "",
                "why_not_summary": "进场、话轮、动作变化和余波都有独立正文证据。" if passed else "",
                "manual_judgment": "当前模型确认场面通过连续动作与话轮完整发生。" if passed else "",
            }],
        }
        self.review.write_text(
            json.dumps(review, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return review

    def test_export_keeps_semantics_pending_and_registry_is_separate(self) -> None:
        self.write_review(False)
        payload = TOOL.export_template(self.review, self.staged, self.sidecar)

        registry_path = Path(payload["bindings"]["evidence_registry_path"])
        self.assertTrue(registry_path.is_file())
        self.assertNotIn("evidence_registry", payload)
        sentence = next(item for item in payload["manual_items"] if item["item_id"] == "SM-01")
        self.assertEqual("", sentence["fields"]["language_mechanism_match"])
        self.assertEqual([], sentence["evidence"]["target_sentence"])
        self.assertNotIn("target", sentence)

    def test_passed_review_round_trips_without_semantic_generation(self) -> None:
        original = self.write_review(True)
        payload = TOOL.export_template(self.review, self.staged, self.sidecar)
        merged = TOOL.apply_template(self.review, self.staged, self.sidecar)

        self.assertEqual(
            original["prose_review"]["sentence_mappings"],
            merged["prose_review"]["sentence_mappings"],
        )
        self.assertEqual(
            original["prose_review"]["character_vitality_review"],
            merged["prose_review"]["character_vitality_review"],
        )
        self.assertFalse(
            merged["review_scaffold"]["manual_sidecar"]["semantic_fields_generated_by_script"]
        )
        registry = json.loads(
            Path(payload["bindings"]["evidence_registry_path"]).read_text(encoding="utf-8")
        )
        self.assertIn("\n", self.staged.read_text(encoding="utf-8"))
        self.assertIn("“别走。”", registry["evidence"].values())

    def test_stale_staged_sha_is_blocked(self) -> None:
        self.write_review(True)
        TOOL.export_template(self.review, self.staged, self.sidecar)
        self.staged.write_text("正文已经变化。", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "staged_sha256 已失效"):
            TOOL.apply_template(self.review, self.staged, self.sidecar)

    def test_stale_review_sha_is_blocked(self) -> None:
        self.write_review(True)
        TOOL.export_template(self.review, self.staged, self.sidecar)
        review = json.loads(self.review.read_text(encoding="utf-8"))
        review["issues_fixed"] = ["正式回执已变化"]
        self.review.write_text(
            json.dumps(review, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "review_sha256 已失效"):
            TOOL.apply_template(self.review, self.staged, self.sidecar)

    def test_q_range_restores_exact_line_breaks(self) -> None:
        self.write_review(True)
        payload = TOOL.export_template(self.review, self.staged, self.sidecar)
        registry = TOOL.build_registry(self.staged.read_text(encoding="utf-8"))
        index = TOOL.registry_index(registry)
        q_ids = [item["evidence_id"] for item in registry if item["evidence_id"].startswith("Q-")]

        resolved = TOOL.resolve_ref(
            f"{q_ids[0]}..{q_ids[-1]}",
            index,
            self.staged.read_text(encoding="utf-8"),
        )

        self.assertIn("\n\n", resolved)

    def test_duplicate_or_unknown_evidence_id_is_blocked(self) -> None:
        self.write_review(True)
        payload = TOOL.export_template(self.review, self.staged, self.sidecar)
        sidecar = deepcopy(payload)
        sentence = next(item for item in sidecar["manual_items"] if item["item_id"] == "SM-01")
        evidence_id = sentence["evidence"]["target_sentence"][0]
        sentence["evidence"]["target_sentence"] = [evidence_id, evidence_id]
        self.sidecar.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "重复证据 ID"):
            TOOL.apply_template(self.review, self.staged, self.sidecar)

        sidecar["bindings"]["review_sha256"] = TOOL.sha256_file(self.review)
        sentence["evidence"]["target_sentence"] = ["Q-999"]
        self.sidecar.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "未知证据 ID"):
            TOOL.apply_template(self.review, self.staged, self.sidecar)

    def test_empty_semantic_field_cannot_be_applied(self) -> None:
        self.write_review(True)
        payload = TOOL.export_template(self.review, self.staged, self.sidecar)
        sidecar = deepcopy(payload)
        sentence = next(item for item in sidecar["manual_items"] if item["item_id"] == "SM-01")
        sentence["fields"]["language_mechanism_match"] = ""
        self.sidecar.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "尚未人工填写"):
            TOOL.apply_template(self.review, self.staged, self.sidecar)


if __name__ == "__main__":
    unittest.main()
