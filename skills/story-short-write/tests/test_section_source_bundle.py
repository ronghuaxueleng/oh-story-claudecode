from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_section_source_bundle.py"
SPEC = importlib.util.spec_from_file_location("section_source_bundle", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class SectionSourceBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_root = self.root / "拆文库" / "测试书"
        self.source = self.source_root / "原文" / "原文.txt"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("原文第一拍。原文第二拍。原文第三拍。", encoding="utf-8")
        self.outline_source = self.root / "小节大纲.md"
        self.outline_source.write_text("## 1. 节\n- 目标字数：1100\n", encoding="utf-8")
        binding = {
            "source_path": str(self.source.resolve()),
            "source_sha256": GATE.sha256(self.source),
            "source_range": "L1-L1",
            "source_evidence": ["原文第一拍", "原文第二拍"],
            "style_fields_consumed": ["voice", "rhythm", "breath", "dialogue", "weave", "roughness"],
        }
        self.outline = self.root / "细纲回执.json"
        self.outline.write_text(json.dumps({
            "gate_status": "passed",
            "outline": {
                "path": str(self.outline_source.resolve()),
                "sha256": GATE.sha256(self.outline_source),
            },
            "sections": [{
                "section_id": "1",
                "scene_logic_contract": {"ok": True},
                "source_emotion_parity": {"ok": True},
                "original_scene_granularity": {
                    "source_scene": "先护后弃再反刀",
                    "action_sequence": "看见、停住、追问",
                },
                "first_draft_generation_contract": {
                    "source_slice_bindings": [binding],
                    "source_performance_excerpt": "原文第一拍。原文第二拍。",
                    "emotion_process": {"entry_state": "a"},
                    "source_style_granularity": {"voice": {"source_evidence": ["原文第一拍"]}},
                    "first_draft_style_plan": {"voice": "按原文口气迁移，不贴原句。"},
                    "anti_verbatim_transfer_contract": {
                        "preserve_axes": ["保事件密度", "保情绪次序"],
                        "rewrite_axes": ["改写原句", "改写对白壳"],
                        "forbidden_surface_reuse": ["原文第一拍"],
                        "allowed_evidence_usage": "只许校准颗粒，不许扩写原句。",
                        "manual_judgment": "必须重写句面。",
                    },
                    "continuous_moment_groups": ["一组", "二组"],
                    "paragraph_break_reasons": ["视线变了", "话头变了"],
                    "sentence_relation_plan": ["先顺承", "后反刀", "再余痛"],
                    "function_word_strategy": "少解释，多停顿",
                    "telegraphic_risk": "不要一句一动",
                    "emotion_shorthand_to_avoid": ["我看着他", "我没说话"],
                    "manual_judgment": "本节必须保留误认和反刀",
                },
            }],
        }, ensure_ascii=False), encoding="utf-8")
        self.source_receipt = self.root / "拆文回执.json"
        self.source_receipt.write_text(
            json.dumps(
                {
                    "gate_status": "passed",
                    "writing_mode": "direct_imitation",
                    "sources": [
                        {
                            "name": "测试书",
                            "role": "main",
                            "root": str(self.source_root.resolve()),
                            "selected_subflow_contracts": [
                                {
                                    "subflow_id": "SF-01",
                                    "source_range": "L1-L1",
                                    "entry_state": "公开前仍站在原位。",
                                    "required_sequence": ["先看见", "再停住", "再追问"],
                                    "scene_granularity": "动作和反应连续咬合。",
                                    "causal_preconditions": {"arrival_reason": "必须在场。"},
                                    "information_delay": {"unknown_to_protagonist": ["真相"]},
                                    "control_changes": ["对方先控场", "主角被迫接招"],
                                    "emotion_sequence": ["愣住", "刺痛", "反顶"],
                                    "end_state": "关系明显失衡。",
                                    "source_style_granularity": {
                                        "narrative_voice_and_attitude": {"source_evidence": ["原文第一拍"]},
                                        "sentence_relation_and_rhythm": {"source_evidence": ["原文第二拍"]},
                                        "paragraph_breath_and_cut_points": {"source_evidence": ["原文第三拍"]},
                                        "dialogue_misfire_or_avoidance": {"source_evidence": ["原文第一拍"]},
                                        "action_perception_emotion_weave": {"source_evidence": ["原文第二拍"]},
                                        "narrator_interjection_and_roughness": {"source_evidence": ["原文第三拍"]},
                                    },
                                    "source_evidence": ["原文第一拍", "原文第二拍"],
                                }
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_and_validate_bundle(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]):
            bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual([], errors)
        payload = bundle["packets"][0]["payload"]
        self.assertEqual(
            self.source.read_text(encoding="utf-8"),
            payload["source_slice_bindings"][0]["source_excerpt"],
        )
        self.assertEqual("SF-01", payload["source_slice_bindings"][0]["subflow_id"])
        self.assertIn("source_subflow_contract", payload["source_slice_bindings"][0])
        self.assertEqual(
            GATE.normalized_section_contract(
                json.loads(self.outline.read_text(encoding="utf-8"))["sections"][0]
            ),
            payload["section_contract"],
        )
        self.assertEqual("先护后弃再反刀", payload["section_contract"]["title"])
        self.assertEqual("先护后弃再反刀", payload["section_contract"]["section_heading"])
        self.assertIn("source_slice_bindings", payload["first_draft_generation_contract"])
        self.assertIn("source_style_granularity", payload)
        self.assertIn("first_draft_style_plan", payload)
        self.assertIn("anti_verbatim_transfer_contract", payload)
        output = self.root / "颗粒包.json"
        GATE.write_json(output, bundle)
        self.assertEqual([], GATE.validate_bundle(output))

    def test_bundle_rejects_truncated_source_excerpt(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]):
            bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual([], errors)
        bundle["packets"][0]["payload"]["source_slice_bindings"][0]["source_excerpt"] = "原文第一拍。"
        bundle["packets"][0]["packet_sha256"] = GATE.hashlib.sha256(
            json.dumps(
                bundle["packets"][0]["payload"],
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        output = self.root / "颗粒包.json"
        GATE.write_json(output, bundle)
        errors = GATE.validate_bundle(output)
        self.assertTrue(any("完整切片已变化" in error for error in errors))

    def test_bundle_rejects_contract_rewritten_inside_packet(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]):
            bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual([], errors)
        payload = bundle["packets"][0]["payload"]
        payload["section_contract"]["scene_logic_contract"] = {"rewritten": True}
        bundle["packets"][0]["packet_sha256"] = GATE.hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        output = self.root / "颗粒包.json"
        GATE.write_json(output, bundle)
        errors = GATE.validate_bundle(output)
        self.assertTrue(any("与当前细纲回执不一致" in error for error in errors))

    def test_bundle_rejects_missing_upstream_subflow_contract(self) -> None:
        self.source_receipt.write_text(
            json.dumps(
                {
                    "gate_status": "passed",
                    "writing_mode": "direct_imitation",
                    "sources": [
                        {
                            "name": "测试书",
                            "role": "main",
                            "root": str(self.source_root.resolve()),
                            "selected_subflow_contracts": [],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]):
            bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual("blocked", bundle["gate_status"])
        self.assertTrue(any("无法回溯到拆文读取回执中的完整 SF 契约" in error for error in errors))

    def test_bundle_rejects_outline_receipt_that_only_claims_passed(self) -> None:
        with mock.patch.object(
            GATE,
            "validate_outline_contract_receipt",
            return_value=["细纲表演验收回执实时复验失败: 第 1 节缺少完整表演链"],
        ):
            bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual({}, bundle)
        self.assertTrue(any("实时复验失败" in error for error in errors))

    def test_build_bundle_can_skip_duplicate_outline_revalidation_after_release_gate(self) -> None:
        with mock.patch.object(
            GATE,
            "validate_outline_contract_receipt",
            side_effect=AssertionError("不应重复做整份细纲回执实时复验"),
        ):
            bundle, errors = GATE.create_bundle(
                self.outline,
                self.source_receipt,
                skip_outline_contract_revalidation=True,
            )
        self.assertEqual([], errors)
        self.assertEqual("passed", bundle["gate_status"])


if __name__ == "__main__":
    unittest.main()
