from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_section_draft_execution.py"
SPEC = importlib.util.spec_from_file_location("section_draft_execution", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class SectionDraftExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "原文.txt"
        self.source.write_text("原文第一拍。原文第二拍。", encoding="utf-8")
        source_sha = GATE.sha256(self.source)
        binding = {
            "source_path": str(self.source.resolve()),
            "source_sha256": source_sha,
            "source_range": "L1-L1",
            "source_evidence": ["原文第一拍", "原文第二拍"],
            "style_fields_consumed": ["a", "b", "c", "d", "e", "f"],
        }
        self.outline = self.root / "细纲回执.json"
        self.outline.write_text(json.dumps({
            "gate_status": "passed",
            "sections": [
                {"section_id": "1", "first_draft_generation_contract": {"source_slice_bindings": [binding]}},
                {"section_id": "2", "first_draft_generation_contract": {"source_slice_bindings": [binding]}},
            ],
        }), encoding="utf-8")
        self.source_receipt = self.root / "拆文回执.json"
        self.source_receipt.write_text('{"gate_status":"passed","writing_mode":"direct_imitation"}', encoding="utf-8")
        self.bundle = self.root / "颗粒包.json"
        self.bundle.write_text(json.dumps({
            "gate": "section_source_bundle",
            "gate_status": "passed",
            "outline_contract": {"path": str(self.outline.resolve()), "sha256": GATE.sha256(self.outline)},
            "source_receipt": {"path": str(self.source_receipt.resolve()), "sha256": GATE.sha256(self.source_receipt)},
            "section_packet_ids": ["section-1", "section-2"],
            "packets": [
                {"packet_id": "section-1", "section_id": "1", "packet_sha256": "a", "payload": {"source_slice_bindings": [binding]}},
                {"packet_id": "section-2", "section_id": "2", "packet_sha256": "b", "payload": {"source_slice_bindings": [binding]}},
            ],
        }), encoding="utf-8")
        self.draft = self.root / "正文.md"
        self.receipt = self.root / "逐节回执.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_sequential_open_write_close_passes(self) -> None:
        self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
        self.assertEqual(0, GATE.open_section(self.receipt, "1", "已重读第一节精确切片"))
        self.draft.write_text("1.\n\n第一节正文。\n", encoding="utf-8")
        self.assertEqual(0, GATE.close_section(self.receipt, "1", "四项逐节停检通过"))
        self.assertEqual(0, GATE.open_section(self.receipt, "2", "已重读第二节精确切片"))
        self.draft.write_text("1.\n\n第一节正文。\n\n2.\n\n第二节正文。\n", encoding="utf-8")
        self.assertEqual(0, GATE.close_section(self.receipt, "2", "四项逐节停检通过"))
        _, errors = GATE.validate_receipt(self.receipt, require_complete=True)
        self.assertEqual([], errors)

    def test_cannot_initialize_after_bulk_draft(self) -> None:
        self.draft.write_text("1.\n\n第一节。\n\n2.\n\n第二节。", encoding="utf-8")
        self.assertEqual(2, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))

    def test_cannot_open_next_section_before_previous_close(self) -> None:
        GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
        GATE.open_section(self.receipt, "1", "已重读")
        self.assertEqual(2, GATE.open_section(self.receipt, "2", "试图抢跑"))


if __name__ == "__main__":
    unittest.main()
