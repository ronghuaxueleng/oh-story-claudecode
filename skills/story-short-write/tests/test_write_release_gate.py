from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_write_release_gate.py"
)
SPEC = importlib.util.spec_from_file_location("write_release_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class WriteReleaseGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.files = {}
        self.setting = self.root / "设定.md"
        self.outline = self.root / "大纲.md"
        self.setting.write_text("设定", encoding="utf-8")
        self.outline.write_text("大纲", encoding="utf-8")
        for name in (
            "writing",
            "source",
            "ledger",
            "opening",
            "profile",
            "sequence",
            "setting_sequence",
        ):
            path = self.root / f"{name}.json"
            payload = {"gate_status": "passed"}
            if name == "sequence":
                payload["scope"] = "full"
                payload["artifacts"] = {
                    "setting": self.binding(self.setting),
                    "outline": self.binding(self.outline),
                }
            elif name == "setting_sequence":
                payload["scope"] = "setting"
                payload["artifacts"] = {"setting": self.binding(self.setting)}
            path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            self.files[name] = path

    @staticmethod
    def binding(path: Path) -> dict[str, str]:
        import hashlib

        return {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_blocked_ledger_blocks_draft(self) -> None:
        self.files["ledger"].write_text(
            json.dumps({"gate_status": "blocked"}),
            encoding="utf-8",
        )
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
        )
        self.assertTrue(any("规则执行门禁未通过" in item for item in errors))

    def test_draft_requires_opening_contract_and_profile(self) -> None:
        errors = GATE.validate_release(
            "draft",
            self.files["writing"],
            self.files["source"],
            self.files["ledger"],
        )
        self.assertTrue(any("开头承重契约" in item for item in errors))
        self.assertTrue(any("profile" in item for item in errors))

    def test_all_preconditions_pass(self) -> None:
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
        )
        self.assertEqual([], errors)

    def test_outline_requires_setting_sequence_contract(self) -> None:
        errors = GATE.validate_release(
            phase="outline",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
        )
        self.assertTrue(any("设定内部顺序契约" in item for item in errors))

    def test_outline_passes_with_setting_sequence_contract(self) -> None:
        errors = GATE.validate_release(
            phase="outline",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            setting_sequence_receipt=self.files["setting_sequence"],
        )
        self.assertEqual([], errors)

    def test_changed_setting_invalidates_outline_release(self) -> None:
        self.setting.write_text("设定已变化", encoding="utf-8")
        errors = GATE.validate_release(
            phase="outline",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            setting_sequence_receipt=self.files["setting_sequence"],
        )
        self.assertTrue(any("SHA 已变化" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
