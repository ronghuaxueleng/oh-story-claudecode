from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_pre_window_revision_gate.py"
)
SPEC = importlib.util.spec_from_file_location("pre_window_revision_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class PreWindowRevisionGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.text = self.root / "正文.md"
        self.text.write_text("正文里有一处需要人工复核的句子。", encoding="utf-8")
        self.receipts = {}
        for name in ("writing", "source", "ledger"):
            path = self.root / f"{name}.json"
            path.write_text(json.dumps({"gate_status": "passed"}), encoding="utf-8")
            self.receipts[name] = path

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def receipt(self) -> dict:
        return {
            "status": "completed",
            "execution_mode": "current_model_manual",
            "window_order": "pre_window_revision_before_segmentation",
            "text": {
                "path": str(self.text),
                "sha256": GATE.sha256(self.text),
                "char_count": len(self.text.read_text(encoding="utf-8")),
            },
            "prerequisites": {
                key: {
                    "path": str(path),
                    "sha256": GATE.sha256(path),
                    "gate_status": "passed",
                }
                for key, path in (
                    ("writing_rule_receipt", self.receipts["writing"]),
                    ("source_read_receipt", self.receipts["source"]),
                    ("rule_execution_ledger", self.receipts["ledger"]),
                )
            },
            "required_readings": [
                "references/anti-ai-writing.md",
                "references/craft/narrator-voice.md",
            ],
            "rule_families_applied": ["S_DRAFT_CRAFT"],
            "source_assets_applied": ["写作资产/作者DNA指纹.md"],
            "revision_items": [
                {
                    "rule_or_asset": "S_DRAFT_CRAFT",
                    "status": "completed",
                    "execution_mode": "human",
                    "evidence": [
                        {
                            "quote": "正文里有一处需要人工复核的句子。",
                            "judgment": "已按规则完成人工判断。",
                        }
                    ],
                }
            ],
            "manual_summary": "已完成窗口前规则和主体资产定向回修。",
        }

    def test_valid_receipt_passes(self) -> None:
        receipt = self.root / "receipt.json"
        receipt.write_text(
            json.dumps(self.receipt(), ensure_ascii=False),
            encoding="utf-8",
        )
        self.assertEqual([], GATE.validate(receipt, self.text))

    def test_pending_receipt_is_blocked(self) -> None:
        data = self.receipt()
        data["status"] = "pending"
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps(data), encoding="utf-8")
        errors = GATE.validate(receipt, self.text)
        self.assertTrue(any("status 必须为 completed" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
