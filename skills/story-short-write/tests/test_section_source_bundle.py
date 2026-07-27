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
            "sections": [{
                "section_id": "1",
                "scene_logic_contract": {"ok": True},
                "source_emotion_parity": {"ok": True},
                "original_scene_granularity": "先护后弃再反刀",
                "first_draft_generation_contract": {
                    "source_slice_bindings": [binding],
                    "source_performance_excerpt": "原文第一拍。原文第二拍。",
                    "emotion_process": {"entry_state": "a"},
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
            json.dumps({"gate_status": "passed", "writing_mode": "direct_imitation"}, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_and_validate_bundle(self) -> None:
        bundle, errors = GATE.create_bundle(self.outline, self.source_receipt)
        self.assertEqual([], errors)
        output = self.root / "颗粒包.json"
        GATE.write_json(output, bundle)
        self.assertEqual([], GATE.validate_bundle(output))


if __name__ == "__main__":
    unittest.main()
