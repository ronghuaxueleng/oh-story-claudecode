from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_sequence_contract.py"
)
SPEC = importlib.util.spec_from_file_location("sequence_contract", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class SequenceContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.setting = self.root / "设定.md"
        self.outline = self.root / "大纲.md"
        self.draft = self.root / "正文.md"
        self.setting.write_text("前线责任 -> 路线授权 -> 私人物件", encoding="utf-8")
        self.outline.write_text("一、前线责任\n二、路线授权\n三、私人物件", encoding="utf-8")
        self.draft.write_text("前线责任。路线授权。私人物件。", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def binding(self, path: Path) -> dict[str, object]:
        return {
            "path": str(path.resolve()),
            "sha256": GATE.sha256(path),
            "char_count": len(path.read_text(encoding="utf-8")),
        }

    def receipt(self, reverse: bool = False) -> dict:
        labels = [
            ("front", "前线责任", "前线责任"),
            ("route", "路线授权", "路线授权"),
            ("object", "私人物件", "私人物件"),
        ]
        if reverse:
            labels[1], labels[2] = labels[2], labels[1]
        sequence = []
        for node_id, label, quote in labels:
            offset = self.draft.read_text(encoding="utf-8").index(quote)
            setting_offset = self.setting.read_text(encoding="utf-8").index(quote)
            outline_offset = self.outline.read_text(encoding="utf-8").index(quote)
            sequence.append(
                {
                    "id": node_id,
                    "label": label,
                    "setting_evidence": [
                        {
                            "quote": quote,
                            "offset": setting_offset,
                            "judgment": "设定原句。",
                        }
                    ],
                    "outline_evidence": [
                        {
                            "quote": quote,
                            "offset": outline_offset,
                            "judgment": "大纲原句。",
                        }
                    ],
                    "draft_evidence": [
                        {
                            "quote": quote,
                            "offset": offset,
                            "judgment": "正文节点。"
                        }
                    ],
                }
            )
        return {
            "scope": "full",
            "status": "completed",
            "gate_status": "passed",
            "execution_mode": "current_model_manual",
            "artifacts": {
                "setting": self.binding(self.setting),
                "outline": self.binding(self.outline),
                "draft": self.binding(self.draft),
            },
            "conflict_review": {"status": "passed", "findings": []},
            "canonical_sequence": sequence,
            "manual_judgment": "已逐层核对。",
        }

    def setting_receipt(self) -> dict:
        text = self.setting.read_text(encoding="utf-8")
        labels = [("front", "前线责任"), ("route", "路线授权"), ("object", "私人物件")]
        return {
            "scope": "setting",
            "status": "completed",
            "gate_status": "passed",
            "execution_mode": "current_model_manual",
            "artifacts": {"setting": self.binding(self.setting)},
            "conflict_review": {
                "setting_internal_status": "passed",
                "findings": [],
            },
            "canonical_sequence": [
                {
                    "id": node_id,
                    "label": label,
                    "setting_evidence": [
                        {
                            "quote": label,
                            "offset": text.index(label),
                            "judgment": "设定原句。",
                        }
                    ],
                }
                for node_id, label in labels
            ],
            "manual_judgment": "已核对设定内部顺序。",
        }

    def test_setting_contract_passes(self) -> None:
        receipt = self.root / "setting-sequence.json"
        receipt.write_text(
            json.dumps(self.setting_receipt(), ensure_ascii=False),
            encoding="utf-8",
        )
        self.assertEqual([], GATE.validate_setting(receipt, self.setting))

    def test_setting_contract_requires_internal_conflict_review(self) -> None:
        data = self.setting_receipt()
        data["conflict_review"]["setting_internal_status"] = "pending"
        receipt = self.root / "setting-sequence.json"
        receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_setting(receipt, self.setting)
        self.assertTrue(any("设定内部顺序冲突审查未通过" in item for item in errors))

    def test_valid_sequence_passes(self) -> None:
        receipt = self.root / "sequence.json"
        receipt.write_text(json.dumps(self.receipt(), ensure_ascii=False), encoding="utf-8")
        self.assertEqual(
            [],
            GATE.validate(receipt, self.setting, self.outline, self.draft),
        )

    def test_reverse_draft_order_is_blocked(self) -> None:
        data = self.receipt(reverse=True)
        receipt = self.root / "sequence.json"
        receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate(receipt, self.setting, self.outline, self.draft)
        self.assertTrue(any("实际出现位置倒序" in item for item in errors))

    def test_unresolved_conflict_is_blocked(self) -> None:
        data = self.receipt()
        data["conflict_review"] = {
            "status": "failed",
            "findings": [
                {
                    "status": "open",
                    "setting_evidence": "路线授权在前",
                    "outline_evidence": "私人物件在前",
                    "resolution": "",
                }
            ],
        }
        receipt = self.root / "sequence.json"
        receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate(receipt, self.setting, self.outline, self.draft)
        self.assertTrue(any("未通过" in item or "未解决" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
