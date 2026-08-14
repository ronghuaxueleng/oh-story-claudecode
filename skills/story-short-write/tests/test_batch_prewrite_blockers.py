from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_prewrite_blockers.py"
SPEC = importlib.util.spec_from_file_location("batch_prewrite_blockers", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchPrewriteBlockersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.outline_contract = self.root / "细纲表演验收回执.json"
        self.outline = self.root / "小节大纲.md"
        self.prose_receipt = self.root / "全文文字颗粒度契约回执.json"
        self.emotional_receipt = self.root / "全文情绪颗粒度契约回执.json"
        self.source_original = self.root / "主体书.txt"
        self.source_emotion_ledger = self.root / "全文情绪颗粒总账.json"
        self.writing_receipt = self.root / "写作规则读取回执.json"
        self.source_receipt = self.root / "拆文读取回执.json"
        self.ledger = self.root / "规则执行台账.json"
        self.sequence_receipt = self.root / "顺序契约回执.json"
        self.opening_contract = self.root / "开头承重契约回执_正文.json"
        self.profile = self.root / "project.profile.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_scan_groups_and_deduplicates_messages(self) -> None:
        original_outline = GATE.OUTLINE.validate_receipt
        original_prewrite = GATE.DRAFT_PREWRITE.validate_batch
        original_release = GATE.WRITE_RELEASE.validate_release
        try:
            GATE.OUTLINE.validate_receipt = lambda *_args, **_kwargs: [
                "原文桥段对齐[1] 目标情节拍 必须逐句填写原文实际存在的全部情节拍，不设模板拍数",
                "主体 SF 颗粒度覆盖[1].manual_judgment 不能为空",
                "第 1 节 scene_units 必须包含 1-3 个完整场面",
            ]
            GATE.DRAFT_PREWRITE.validate_batch = lambda **_kwargs: (
                [
                    "主体细节卡 GX01.target_sections 必须绑定真实细纲小节",
                    "主体细节卡 GX01.target_sections 必须绑定真实细纲小节",
                    "成文活性资产 active_verb 至少需要 3 条",
                    "逐节情绪合同必须按细纲数字小节完整覆盖且顺序一致",
                    "无法读取全文情绪颗粒总账: Expecting value",
                ],
                {},
            )
            GATE.WRITE_RELEASE.validate_release = lambda *_args, **_kwargs: [
                "写作规则读取回执未通过",
            ]
            report = GATE.scan_blockers(
                outline_contract=self.outline_contract,
                outline=self.outline,
                prose_receipt=self.prose_receipt,
                emotional_receipt=self.emotional_receipt,
                source_original=self.source_original,
                source_emotion_ledger=self.source_emotion_ledger,
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                ledger=self.ledger,
                sequence_receipt=self.sequence_receipt,
                opening_contract=self.opening_contract,
                profile=self.profile,
            )
        finally:
            GATE.OUTLINE.validate_receipt = original_outline
            GATE.DRAFT_PREWRITE.validate_batch = original_prewrite
            GATE.WRITE_RELEASE.validate_release = original_release

        self.assertTrue(report["blocked"])
        labels = [item["label"] for item in report["work_order"]]
        self.assertEqual(
            ["源账本", "桥级对齐", "SF 颗粒", "节级场面", "细节卡计划", "文字合同", "情绪合同", "最终放行"],
            labels,
        )
        detail_cards = next(item for item in report["work_order"] if item["label"] == "细节卡计划")
        self.assertEqual(
            ["主体细节卡 GX01.target_sections 必须绑定真实细纲小节"],
            detail_cards["messages"],
        )
        focus_labels = [item["label"] for item in report["focus_work_order"]]
        self.assertEqual(
            ["桥级情绪边界", "桥级逐拍映射", "节级场面承载"],
            focus_labels,
        )
        focus_boundary = report["focus_work_order"][0]
        self.assertIn("源账本", focus_boundary["source_categories"])
        self.assertEqual(
            ["无法读取全文情绪颗粒总账: Expecting value"],
            focus_boundary["messages"],
        )
        focus_mapping = report["focus_work_order"][1]
        self.assertIn("桥级对齐", focus_mapping["source_categories"])
        self.assertEqual(
            ["原文桥段对齐[1] 目标情节拍 必须逐句填写原文实际存在的全部情节拍，不设模板拍数"],
            focus_mapping["messages"],
        )
        focus_section = report["focus_work_order"][2]
        self.assertIn("节级场面", focus_section["source_categories"])
        self.assertEqual(
            ["第 1 节 scene_units 必须包含 1-3 个完整场面"],
            focus_section["messages"],
        )

    def test_scan_skips_write_release_when_args_absent(self) -> None:
        original_outline = GATE.OUTLINE.validate_receipt
        original_prewrite = GATE.DRAFT_PREWRITE.validate_batch
        try:
            GATE.OUTLINE.validate_receipt = lambda *_args, **_kwargs: []
            GATE.DRAFT_PREWRITE.validate_batch = lambda **_kwargs: ([], {})
            report = GATE.scan_blockers(
                outline_contract=self.outline_contract,
                outline=self.outline,
                prose_receipt=self.prose_receipt,
                emotional_receipt=self.emotional_receipt,
                source_original=self.source_original,
                source_emotion_ledger=self.source_emotion_ledger,
            )
        finally:
            GATE.OUTLINE.validate_receipt = original_outline
            GATE.DRAFT_PREWRITE.validate_batch = original_prewrite
        self.assertFalse(report["blocked"])
        self.assertTrue(report["stage_summary"]["write_release"]["skipped"])

    def test_main_prints_blocked_work_order(self) -> None:
        original_scan = GATE.scan_blockers
        original_argv = sys.argv[:]
        stdout = io.StringIO()
        try:
            GATE.scan_blockers = lambda **_kwargs: {
                "blocked": True,
                "stage_summary": {},
                "total_unique_blockers": 2,
                "focus_work_order": [
                    {
                        "label": "桥级逐拍映射",
                        "stages": ["outline_performance"],
                        "source_categories": ["桥级对齐"],
                        "next_action": "先补桥级 target_plot_beats / plot_beat_mapping / source_emotion_sequence / target_emotion_sequence，再看节级承载。",
                        "messages": ["原文桥段对齐[1] 目标情节拍 必须逐句填写原文实际存在的全部情节拍，不设模板拍数"],
                    }
                ],
                "work_order": [
                    {
                        "label": "桥级对齐",
                        "stages": ["outline_performance"],
                        "next_action": "先补桥级 P/E 拍映射与读者体感同级判断，再看节级字段。",
                        "messages": ["原文桥段对齐[1] 目标情节拍 必须逐句填写原文实际存在的全部情节拍，不设模板拍数"],
                    }
                ],
            }
            sys.argv = [
                "batch_prewrite_blockers.py",
                "--outline-contract", str(self.outline_contract),
                "--outline", str(self.outline),
                "--prose-receipt", str(self.prose_receipt),
                "--emotional-receipt", str(self.emotional_receipt),
                "--source-original", str(self.source_original),
                "--source-emotion-ledger", str(self.source_emotion_ledger),
            ]
            with contextlib.redirect_stdout(stdout):
                code = GATE.main()
        finally:
            GATE.scan_blockers = original_scan
            sys.argv = original_argv
        self.assertEqual(2, code)
        text = stdout.getvalue()
        self.assertIn("batch_prewrite_blockers: blocked", text)
        self.assertIn("聚焦顺序：桥级逐拍映射", text)
        self.assertIn("{桥级逐拍映射}", text)
        self.assertIn("[桥级对齐]", text)

    def test_main_prints_json_when_requested(self) -> None:
        original_scan = GATE.scan_blockers
        original_argv = sys.argv[:]
        stdout = io.StringIO()
        try:
            GATE.scan_blockers = lambda **_kwargs: {
                "blocked": False,
                "stage_summary": {"outline_performance": {"passed": True}},
                "total_unique_blockers": 0,
                "focus_work_order": [],
                "work_order": [],
            }
            sys.argv = [
                "batch_prewrite_blockers.py",
                "--outline-contract", str(self.outline_contract),
                "--outline", str(self.outline),
                "--prose-receipt", str(self.prose_receipt),
                "--emotional-receipt", str(self.emotional_receipt),
                "--source-original", str(self.source_original),
                "--source-emotion-ledger", str(self.source_emotion_ledger),
                "--json",
            ]
            with contextlib.redirect_stdout(stdout):
                code = GATE.main()
        finally:
            GATE.scan_blockers = original_scan
            sys.argv = original_argv
        self.assertEqual(0, code)
        text = stdout.getvalue()
        self.assertIn("batch_prewrite_blockers: passed", text)
        self.assertIn('"total_unique_blockers": 0', text)


if __name__ == "__main__":
    unittest.main()
