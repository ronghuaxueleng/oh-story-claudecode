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
        judgment = (
            "当前模型完整通读本节，逐项核对人物动作、对白接招、情绪变化与现场后果后完成语义裁决。"
            if passed
            else ""
        )
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
                    "language_mechanism_match": "目标句沿用来源句先落具体物件动作、再让关系位置发生可见变化的句间机制。" if passed else "",
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
                    "trigger": "对方当着她的面转身离场且没有回头回应挽留" if passed else "",
                    "relationship_position_change": "她停止追逐并从求留位置退回不再等待确认的一方" if passed else "",
                    "reader_effect": "读者从短暂期待挽留成功转为确认这段关系已经断开" if passed else "",
                    "judgment": "不追出去的动作承担了关系撤回，情绪烈度与来源拍保持等价" if passed else "",
                    "semantic_parity_status": status,
                }],
                "plot_beat_reviews": [{
                    "beat_id": "P-001",
                    "quote": "他把名牌扶正。" if passed else "",
                    "action_parity": "人物亲手扶正自己的名牌，主动动作与来源拍的收回位置同级" if passed else "",
                    "external_change": "名牌重新朝向现场来宾，公开位置由模糊状态变得明确可见" if passed else "",
                    "relationship_consequence": "她不再等待对方替自己确认身份，而是亲手收回关系解释权" if passed else "",
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
                "reader_emotion_progression": "读者的希望先被一句挽留抬起，随后又被人物留在原地、不再追出的动作压回现实。" if passed else "",
                "why_not_summary": "本场写出了进场压力、挽留话轮、人物不追的转折动作和名牌复位余波，不是结果摘要。" if passed else "",
                "manual_judgment": "当前模型确认这场戏通过连续物件动作与人物话轮完整发生，控制权和关系后果均已可见。" if passed else "",
            }],
        }
        self.review.write_text(
            json.dumps(review, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return review

    def test_export_keeps_semantics_pending_and_registry_is_separate(self) -> None:
        self.write_review(False)
        payload = TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )

        registry_path = Path(payload["bindings"]["evidence_registry_path"])
        self.assertTrue(registry_path.is_file())
        self.assertNotIn("evidence_registry", payload)
        sentence = next(item for item in payload["manual_items"] if item["item_id"] == "SM-01")
        self.assertEqual("", sentence["fields"]["language_mechanism_match"])
        self.assertEqual([], sentence["evidence"]["target_sentence"])
        self.assertNotIn("target", sentence)

    def test_passed_review_round_trips_without_semantic_generation(self) -> None:
        original = self.write_review(True)
        payload = TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )
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
        TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )
        self.staged.write_text("正文已经变化。", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "staged_sha256 已失效"):
            TOOL.apply_template(self.review, self.staged, self.sidecar)

    def test_stale_review_sha_is_blocked(self) -> None:
        self.write_review(True)
        TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )
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
        payload = TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )
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
        payload = TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )
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
        payload = TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )
        sidecar = deepcopy(payload)
        sentence = next(item for item in sidecar["manual_items"] if item["item_id"] == "SM-01")
        sentence["fields"]["language_mechanism_match"] = ""
        self.sidecar.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "尚未人工填写"):
            TOOL.apply_template(self.review, self.staged, self.sidecar)

    def test_sf_parent_quotes_are_derived_from_complete_mapping_evidence(self) -> None:
        review = self.write_review(True)
        review["prose_review"]["source_subflow_reviews"] = [{
            "subflow_id": "SF-01",
            "status": "passed",
            "manual_judgment": "当前模型确认两条来源证据分别迁移成物件复位和关系撤回动作，没有合并或复用同一句证据。",
            "dimension_transfers": {
                "narrative_voice_and_attitude": {
                    "evidence_mappings": [
                        {
                            "source_quote": "来源一",
                            "target_quotes": ["他把名牌扶正。"],
                            "comparison": "第一条来源证据迁移为具体物件动作。",
                        },
                        {
                            "source_quote": "来源二",
                            "target_quotes": ["我没有追出去。"],
                            "comparison": "第二条来源证据迁移为关系撤回动作。",
                        },
                    ],
                    "target_quotes": [],
                    "comparison": "两条证据共同形成动作到撤回的完整维度变化。",
                    "surface_copy_rejected": True,
                }
            },
            "required_sequence_reviews": [],
        }]
        self.review.write_text(
            json.dumps(review, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        TOOL.export_template(
            self.review,
            self.staged,
            self.sidecar,
            review_mode=TOOL.FULL_REVIEW_MODE,
        )
        merged = TOOL.apply_template(self.review, self.staged, self.sidecar)

        transfer = merged["prose_review"]["source_subflow_reviews"][0][
            "dimension_transfers"
        ]["narrative_voice_and_attitude"]
        self.assertEqual(
            ["他把名牌扶正。", "我没有追出去。"],
            transfer["target_quotes"],
        )


if __name__ == "__main__":
    unittest.main()
