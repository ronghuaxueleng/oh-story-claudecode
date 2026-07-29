from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
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
        self.source = self.root / "原文.txt"
        self.source.write_text("原文第一拍。原文第二拍。原文第三拍。", encoding="utf-8")
        assets = self.root / "写作资产"
        assets.mkdir()
        (self.root / "book.profile.json").write_text(
            json.dumps({"style_assets": {"opening_hooks": ["原文第一拍"]}}, ensure_ascii=False),
            encoding="utf-8",
        )
        (assets / "角色口气模板.md").write_text("角色压力越大，话越短。", encoding="utf-8")
        binding = {
            "source_path": str(self.source.resolve()),
            "source_sha256": GATE.sha256(self.source),
            "source_range": "L1-L1",
            "source_evidence": ["原文第一拍", "原文第二拍"],
            "style_fields_consumed": list(GATE.REQUIRED_STYLE_FIELDS),
        }
        self.outline = self.root / "细纲回执.json"
        self.outline.write_text(json.dumps({
            "gate_status": "passed",
            "sections": [{
                "section_id": "1",
                "scene_logic_contract": {"ok": True},
                "source_emotion_parity": {"ok": True},
                "original_scene_granularity": {"action_sequence": "先护后弃再反刀"},
                "first_draft_generation_contract": {
                    "source_slice_bindings": [binding],
                    "source_performance_excerpt": "原文第一拍。原文第二拍。",
                    "source_performance_evidence": ["原文第一拍", "原文第二拍"],
                    "technique_recall_contract": [
                        {
                            "technique_name": "先动作后判断",
                            "source_summary": "原文先落动作再漏判断",
                            "source_evidence": ["原文第一拍"],
                            "linked_style_dimensions": ["action_perception_emotion_weave"],
                            "target_execution": "目标稿先写动作与物件，再落误认",
                            "must_not_flatten_to": "不能压成一句她受伤了",
                            "target_outline_evidence": ["动作一"],
                        },
                        {
                            "technique_name": "句间反冲",
                            "source_summary": "句间用停顿和反冲带关系",
                            "source_evidence": ["原文第二拍"],
                            "linked_style_dimensions": ["sentence_relation_and_rhythm"],
                            "target_execution": "保留同一口气里的反冲",
                            "must_not_flatten_to": "不能拆成报账链",
                            "target_outline_evidence": ["动作一"],
                        },
                        {
                            "technique_name": "错答压场",
                            "source_summary": "对白逼出错答",
                            "source_evidence": ["原文第三拍"],
                            "linked_style_dimensions": ["dialogue_misfire_or_avoidance"],
                            "target_execution": "对白后立刻接错答余波",
                            "must_not_flatten_to": "不能改成解释句",
                            "target_outline_evidence": ["动作一"],
                        },
                    ],
                    "source_style_granularity": {
                        "narrative_voice_and_attitude": {
                            "source_summary": "贴脸跟着人物当前注意走。",
                            "source_evidence": ["原文第一拍"],
                            "target_style_plan": "先写她看到的，再漏判断。",
                        },
                        "sentence_relation_and_rhythm": {
                            "source_summary": "句间靠反冲和停顿承接。",
                            "source_evidence": ["原文第二拍"],
                            "target_style_plan": "让错答前后形成反冲。",
                        },
                        "paragraph_breath_and_cut_points": {
                            "source_summary": "控制权换主时断段。",
                            "source_evidence": ["原文第一拍"],
                            "target_style_plan": "在换主与余痛两处断开。",
                        },
                        "dialogue_misfire_or_avoidance": {
                            "source_summary": "对白逼出更短的错答。",
                            "source_evidence": ["原文第三拍"],
                            "target_style_plan": "对白后只接短错答，不补解释。",
                        },
                        "action_perception_emotion_weave": {
                            "source_summary": "动作、感知和情绪写在同一瞬间。",
                            "source_evidence": ["原文第一拍", "原文第二拍"],
                            "target_style_plan": "把动作、感知、余波织成一口气。",
                        },
                        "narrator_interjection_and_roughness": {
                            "source_summary": "尾句停在余痛，不写主题句。",
                            "source_evidence": ["原文第三拍"],
                            "target_style_plan": "场末只留余痛和未尽后果。",
                        },
                    },
                    "emotion_process": {"entry_state": "a"},
                    "scene_weave_contract": [
                        {
                            "moment_group_id": "MG-1",
                            "source_trigger": "看见异常",
                            "source_evidence": ["原文第一拍"],
                            "action": "先碰到物件",
                            "perception": "误认事态还有余地",
                            "reaction": "话到嘴边改口",
                            "same_moment_requirement": "必须写在同一连续瞬间里",
                            "why_cannot_be_split": "一拆就会变成功能节点",
                            "target_outline_evidence": ["动作一"],
                        },
                        {
                            "moment_group_id": "MG-2",
                            "source_trigger": "关系公开掉位",
                            "source_evidence": ["原文第二拍"],
                            "action": "手里一松",
                            "perception": "明白位置被换主",
                            "reaction": "余痛留到场末",
                            "same_moment_requirement": "动作、感知、余痛必须同场连写",
                            "why_cannot_be_split": "否则只剩交付事件",
                            "target_outline_evidence": ["动作一"],
                        },
                    ],
                    "continuous_moment_groups": ["一组", "二组"],
                    "paragraph_break_reasons": ["视线变了", "话头变了"],
                    "sentence_relation_plan": ["先顺承", "后反刀", "再余痛"],
                    "function_word_strategy": "少解释，多停顿",
                    "telegraphic_risk": "不要一句一动",
                    "emotion_shorthand_to_avoid": ["我看着他", "我没说话"],
                    "target_emotion_landing_plan": ["先误认", "再失控", "后余痛"],
                    "no_fixed_short_sentence_ratio": True,
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
                            "name": self.root.name,
                            "role": "main",
                            "root": str(self.root.resolve()),
                            "selected_subflow_contracts": [
                                {
                                    "subflow_id": "SF-01",
                                    "source_range": "L1-L1",
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
        bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual([], errors)
        payload = bundle["packets"][0]["payload"]
        self.assertIn("source_excerpt_sha256", payload["source_slice_bindings"][0])
        self.assertEqual(set(GATE.REQUIRED_STYLE_FIELDS), set(payload["source_style_granularity"]))
        self.assertEqual(3, len(payload["technique_recall_contract"]))
        self.assertEqual(2, len(payload["scene_weave_contract"]))
        self.assertTrue(payload["source_style_reference_assets"][0]["voice_references"])
        output = self.root / "颗粒包.json"
        GATE.write_json(output, bundle)
        self.assertEqual([], GATE.validate_bundle(output))

    def test_missing_section_style_granularity_is_blocked(self) -> None:
        data = json.loads(self.outline.read_text(encoding="utf-8"))
        del data["sections"][0]["first_draft_generation_contract"]["source_style_granularity"]
        self.outline.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        _, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertTrue(any("缺少 source_style_granularity" in item for item in errors))

    def test_book_style_reference_cannot_replace_section_style_contract(self) -> None:
        bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual([], errors)
        payload = bundle["packets"][0]["payload"]
        del payload["source_style_granularity"]
        bundle["packets"][0]["packet_sha256"] = GATE.hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        output = self.root / "颗粒包.json"
        GATE.write_json(output, bundle)

        errors = GATE.validate_bundle(output)
        self.assertTrue(any("缺少 source_style_granularity" in item for item in errors))

    def test_source_evidence_must_be_inside_bound_range(self) -> None:
        data = json.loads(self.outline.read_text(encoding="utf-8"))
        binding = data["sections"][0]["first_draft_generation_contract"]["source_slice_bindings"][0]
        binding["source_range"] = "L1-L1"
        binding["source_evidence"] = ["原文第一拍", "不在原文中"]
        self.outline.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        _, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertTrue(any("不在绑定行段内" in item for item in errors))

    def test_bound_range_must_be_covered_by_selected_subflows(self) -> None:
        data = json.loads(self.outline.read_text(encoding="utf-8"))
        binding = data["sections"][0]["first_draft_generation_contract"]["source_slice_bindings"][0]
        binding["source_range"] = "L1-L2"
        self.outline.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        _, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertTrue(any("未被已选 SF 覆盖" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
