from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_first_draft_entry.py"
)
SPEC = importlib.util.spec_from_file_location("first_draft_entry", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class FirstDraftEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "book"
        self.assets = self.project / "写作资产"
        self.assets.mkdir(parents=True)
        self.draft = self.project / "正文.md"
        self.receipt = self.assets / "首稿入口回执.json"
        self.section_execution = self.assets / "逐节首写执行回执.json"
        self.source_original = self.root / "原文.txt"
        self.source_original.write_text("原文场面。原文动作。原文余痛。", encoding="utf-8")
        self.outline = self.project / "小节大纲.md"
        self.outline.parent.mkdir(parents=True, exist_ok=True)
        self.outline.write_text("## 1. 起事\n\n动作一\n", encoding="utf-8")
        self.setting = self.project / "设定.md"
        self.setting.write_text("设定", encoding="utf-8")
        self.files: dict[str, Path] = {}
        self.original_validate_release = GATE._WRITE_RELEASE_MODULE.validate_release
        GATE._WRITE_RELEASE_MODULE.validate_release = lambda **kwargs: []
        for name in (
            "writing",
            "source",
            "ledger",
            "opening",
            "outline_contract",
            "profile",
            "sequence",
            "draft_capacity_contract",
            "section_source_bundle",
        ):
            path = self.root / f"{name}.json"
            payload: dict = {"gate_status": "passed"}
            if name == "opening":
                payload = {
                    "gate_status": "passed",
                    "primary_source": {"path": str(self.source_original.resolve())},
                    "target_text": {"path": str(self.outline.resolve())},
                }
            elif name == "sequence":
                payload = {
                    "gate_status": "passed",
                    "scope": "full",
                    "artifacts": {
                        "setting": self.binding(self.setting),
                        "outline": self.binding(self.outline),
                    },
                }
            elif name == "outline_contract":
                payload = {
                    "gate_status": "passed",
                    "outline": self.binding(self.outline),
                    "sections": [
                        {
                            "section_id": "1",
                            "first_draft_generation_contract": {
                                "source_slice_bindings": [
                                    {
                                        "source_path": str(self.source_original.resolve()),
                                        "source_sha256": self.sha(self.source_original),
                                        "source_range": "L1-L1",
                                        "source_evidence": ["原文场面"],
                                        "style_fields_consumed": ["a", "b", "c", "d", "e", "f"],
                                    }
                                ],
                                "source_performance_excerpt": "原文场面。",
                                "source_performance_evidence": ["原文场面", "原文动作"],
                                "technique_recall_contract": [{"name": "先动作后判断"}],
                                "scene_weave_contract": [{"moment_group_id": "MG-1"}],
                                "source_style_granularity": {
                                    key: {
                                        "source_summary": f"{key} summary",
                                        "source_evidence": ["原文场面"],
                                        "target_style_plan": f"{key} target",
                                    }
                                    for key in GATE._SECTION_EXECUTION_MODULE.STYLE_DIMENSIONS
                                },
                                "continuous_moment_groups": ["同一口气"],
                                "paragraph_break_reasons": ["控制权变化"],
                                "sentence_relation_plan": ["先顺承再反冲"],
                                "function_word_strategy": "少解释，多停顿",
                                "telegraphic_risk": "不要一句一动",
                                "emotion_shorthand_to_avoid": ["我心如死灰"],
                                "target_emotion_landing_plan": ["先误认", "再反刀", "留余痛"],
                                "no_fixed_short_sentence_ratio": True,
                                "manual_judgment": "首稿必须完整消费原文颗粒。",
                            },
                        }
                    ],
                }
            elif name == "section_source_bundle":
                payload = {
                    "gate": "section_source_bundle",
                    "gate_status": "passed",
                    "outline_contract": {"path": str((self.root / "outline_contract.json").resolve()), "sha256": "x"},
                    "source_receipt": {"path": str((self.root / "source.json").resolve()), "sha256": "y"},
                    "section_packet_ids": ["section-1"],
                    "packets": [
                        {
                            "packet_id": "section-1",
                            "section_id": "1",
                            "packet_sha256": "z",
                            "payload": {
                                "source_slice_bindings": [
                                    {
                                        "source_path": str(self.source_original.resolve()),
                                        "source_sha256": self.sha(self.source_original),
                                        "source_range": "L1-L1",
                                        "source_evidence": ["原文场面"],
                                        "style_fields_consumed": ["a", "b", "c", "d", "e", "f"],
                                    }
                                ],
                                "source_performance_excerpt": "原文场面。",
                                "source_performance_evidence": ["原文场面", "原文动作"],
                                "technique_recall_contract": [{"name": "先动作后判断"}],
                                "scene_weave_contract": [{"moment_group_id": "MG-1"}],
                                "source_style_granularity": {
                                    key: {
                                        "source_summary": f"{key} summary",
                                        "source_evidence": ["原文场面"],
                                        "target_style_plan": f"{key} target",
                                    }
                                    for key in GATE._SECTION_EXECUTION_MODULE.STYLE_DIMENSIONS
                                },
                                "source_style_reference_assets": [
                                    {
                                        "book_root": str(self.root),
                                        "style_assets": {"opening_hooks": ["原文场面"]},
                                        "style_assets_source": {
                                            "path": str(self.source_original.resolve()),
                                            "sha256": self.sha(self.source_original),
                                        },
                                        "voice_references": [
                                            {
                                                "path": str(self.source_original.resolve()),
                                                "sha256": self.sha(self.source_original),
                                                "text": "角色压力越大，话越短。",
                                            }
                                        ],
                                    }
                                ],
                                "emotion_process": {"entry_state": "a"},
                                "continuous_moment_groups": ["同一口气"],
                                "paragraph_break_reasons": ["控制权变化"],
                                "sentence_relation_plan": ["先顺承再反冲"],
                                "function_word_strategy": "少解释，多停顿",
                                "telegraphic_risk": "不要一句一动",
                                "emotion_shorthand_to_avoid": ["我心如死灰"],
                                "target_emotion_landing_plan": ["先误认", "再反刀", "留余痛"],
                                "no_fixed_short_sentence_ratio": True,
                                "manual_judgment": "首稿必须完整消费原文颗粒。",
                                "scene_logic_contract": {"ok": True},
                                "source_emotion_parity": {"ok": True},
                                "original_scene_granularity": {"action_sequence": "先动作后反刀"},
                            },
                        }
                    ],
                }
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.files[name] = path

    def tearDown(self) -> None:
        GATE._WRITE_RELEASE_MODULE.validate_release = self.original_validate_release
        self.temp.cleanup()

    @staticmethod
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def binding(path: Path) -> dict[str, str]:
        return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_init_entry_creates_empty_draft_and_section_execution(self) -> None:
        result = GATE.init_entry(
            project="测试",
            draft=self.draft,
            receipt=self.receipt,
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["draft_capacity_contract"],
            section_source_bundle=self.files["section_source_bundle"],
            section_execution_receipt=self.section_execution,
            force=False,
        )
        self.assertEqual(0, result)
        self.assertTrue(self.draft.is_file())
        self.assertEqual("", self.draft.read_text(encoding="utf-8"))
        self.assertTrue(self.section_execution.is_file())
        self.assertEqual([], GATE.validate_entry(self.receipt, self.draft))

    def test_init_entry_blocks_existing_draft_content(self) -> None:
        self.draft.write_text("已有正文", encoding="utf-8")
        result = GATE.init_entry(
            project="测试",
            draft=self.draft,
            receipt=self.receipt,
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["draft_capacity_contract"],
            section_source_bundle=self.files["section_source_bundle"],
            section_execution_receipt=self.section_execution,
            force=False,
        )
        self.assertEqual(2, result)


if __name__ == "__main__":
    unittest.main()
