from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_draft_prewrite.py"
SPEC = importlib.util.spec_from_file_location("batch_draft_prewrite", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchDraftPrewriteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_root = self.root / "项目"
        self.source_original = self.root / "拆文库" / "样本" / "原文" / "样本.txt"
        self.source_emotion_ledger = self.root / "拆文库" / "样本" / "写作资产" / "全文情绪颗粒总账.json"
        self.subflow_catalog = self.root / "拆文库" / "样本" / "写作资产" / "子流程索引.jsonl"
        self.outline = self.project_root / "小节大纲.md"
        self.prose_receipt = self.project_root / "写作资产" / "全文文字颗粒度契约回执.json"
        self.emotional_receipt = self.project_root / "写作资产" / "全文情绪颗粒度契约回执.json"

        self.source_original.parent.mkdir(parents=True, exist_ok=True)
        self.source_original.write_text(
            "原文场面里，他先伸手拦我，我把他的手推开。"
            "我没想到他还会替别人解释。"
            "解释什么？",
            encoding="utf-8",
        )
        self.source_emotion_ledger.parent.mkdir(parents=True, exist_ok=True)
        self.source_emotion_ledger.write_text(
            json.dumps(
                {
                    "schema_version": GATE.EMOTION.SOURCE_LEDGER_SCHEMA,
                    "source": {"path": str(self.source_original), "sha1": "x", "line_count": 1},
                    "coverage_segments": [{"segment_id": "SEG-01", "start_line": 1, "end_line": 1, "kind": "emotion_bearing", "beat_ids": []}],
                    "beats": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.subflow_catalog.write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "source_range": "L1-L1",
                    "source_style_granularity": {
                        "narrative_voice_and_attitude": {"source_evidence": ["我没想到他还会替别人解释。"]},
                        "sentence_relation_and_rhythm": {"source_evidence": ["他先伸手拦我，我把他的手推开。"]},
                        "paragraph_breath_and_cut_points": {"source_evidence": ["解释什么？"]},
                        "dialogue_misfire_or_avoidance": {"source_evidence": ["解释什么？"]},
                        "action_perception_emotion_weave": {"source_evidence": ["原文场面里，他先伸手拦我，我把他的手推开。"]},
                        "narrator_interjection_and_roughness": {"source_evidence": ["我没想到他还会替别人解释。"]},
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        self.outline.parent.mkdir(parents=True, exist_ok=True)
        self.outline.write_text("# 标题\n\n## 1. 起事\n\n动作一\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_prepare_creates_both_receipts(self) -> None:
        errors, summary = GATE.prepare_batch(
            project="测试项目",
            source_original=self.source_original,
            source_emotion_ledger=self.source_emotion_ledger,
            outline=self.outline,
            prose_receipt=self.prose_receipt,
            emotional_receipt=self.emotional_receipt,
            force_prose_receipt=False,
            force_emotional_receipt=False,
            prose_plan=None,
            emotional_plan=None,
            beat_mapping=None,
            outline_contract=None,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.prose_receipt.is_file())
        self.assertTrue(self.emotional_receipt.is_file())
        self.assertTrue(summary["prose_outline_bound"])
        self.assertTrue(summary["emotional_outline_bound"])

    def test_validate_passes_when_underlying_validators_pass(self) -> None:
        GATE.prepare_batch(
            project="测试项目",
            source_original=self.source_original,
            source_emotion_ledger=self.source_emotion_ledger,
            outline=self.outline,
            prose_receipt=self.prose_receipt,
            emotional_receipt=self.emotional_receipt,
            force_prose_receipt=False,
            force_emotional_receipt=False,
            prose_plan=None,
            emotional_plan=None,
            beat_mapping=None,
            outline_contract=None,
        )
        original_prose = GATE.PROSE.validate_prewrite_data
        original_emotion = GATE.EMOTION.validate_prewrite_data
        try:
            GATE.PROSE.validate_prewrite_data = lambda *_args, **_kwargs: ([], {"ok": True})
            GATE.EMOTION.validate_prewrite_data = lambda *_args, **_kwargs: ([], {"ok": True})
            errors, summary = GATE.validate_batch(
                prose_receipt=self.prose_receipt,
                emotional_receipt=self.emotional_receipt,
                source_original=self.source_original,
                source_emotion_ledger=self.source_emotion_ledger,
                outline=self.outline,
            )
        finally:
            GATE.PROSE.validate_prewrite_data = original_prose
            GATE.EMOTION.validate_prewrite_data = original_emotion
        self.assertEqual([], errors)
        self.assertTrue(summary["prose_summary"]["ok"])
        self.assertTrue(summary["emotional_summary"]["ok"])

    def test_existing_receipt_blocks_without_force(self) -> None:
        self.prose_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.prose_receipt.write_text("{}", encoding="utf-8")
        errors, _summary = GATE.prepare_batch(
            project="测试项目",
            source_original=self.source_original,
            source_emotion_ledger=self.source_emotion_ledger,
            outline=self.outline,
            prose_receipt=self.prose_receipt,
            emotional_receipt=self.emotional_receipt,
            force_prose_receipt=False,
            force_emotional_receipt=False,
            prose_plan=None,
            emotional_plan=None,
            beat_mapping=None,
            outline_contract=None,
        )
        self.assertTrue(any("文字颗粒度合同回执已存在" in item for item in errors))

    def test_prepare_returns_blocked_error_when_prose_prerequisite_missing(self) -> None:
        self.subflow_catalog.unlink()
        errors, summary = GATE.prepare_batch(
            project="测试项目",
            source_original=self.source_original,
            source_emotion_ledger=self.source_emotion_ledger,
            outline=self.outline,
            prose_receipt=self.prose_receipt,
            emotional_receipt=self.emotional_receipt,
            force_prose_receipt=False,
            force_emotional_receipt=False,
            prose_plan=None,
            emotional_plan=None,
            beat_mapping=None,
            outline_contract=None,
        )
        self.assertTrue(any("文字颗粒度合同准备失败" in item for item in errors))
        self.assertFalse(self.prose_receipt.exists())
        self.assertFalse(self.emotional_receipt.exists())
        self.assertFalse(summary["prose_outline_bound"])


if __name__ == "__main__":
    unittest.main()
