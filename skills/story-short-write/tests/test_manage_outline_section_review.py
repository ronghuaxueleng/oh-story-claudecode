from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "manage_outline_section_review.py"
SPEC = importlib.util.spec_from_file_location("manage_outline_section_review", SCRIPT)
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class ManageOutlineSectionReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.receipt = self.root / "细纲表演验收回执.json"
        self.template = self.root / "节级回填侧车.json"
        self._write_receipt()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_receipt(self) -> None:
        payload = {
            "sections": [
                {
                    "section_id": "1",
                    "verdict": "pending",
                    "irreversible_action": "",
                    "scene_units": [],
                    "manual_judgment": "",
                },
                {
                    "section_id": "2",
                    "verdict": "pending",
                    "irreversible_action": "",
                    "scene_units": [],
                    "manual_judgment": "",
                },
            ]
        }
        self.receipt.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_export_template_preserves_section_ids(self) -> None:
        payload = TOOL.export_template(self.receipt, self.template)
        self.assertEqual("story-short-write.outline-section-review-template.v1", payload["schema_version"])
        self.assertEqual(["1", "2"], [item["section_id"] for item in payload["sections"]])
        self.assertTrue(self.template.is_file())

    def test_apply_template_replaces_target_sections(self) -> None:
        TOOL.export_template(self.receipt, self.template)
        payload = json.loads(self.template.read_text(encoding="utf-8"))
        payload["sections"][0].update(
            {
                "verdict": "passed",
                "irreversible_action": "当众撤掉她的解释权",
                "scene_units": [
                    {
                        "allocated_chars": 1200,
                        "entry_pressure": "公开点名后立刻选边",
                    }
                ],
                "manual_judgment": "已形成完整场面",
            }
        )
        self.template.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        merged = TOOL.apply_template(self.receipt, self.template)
        self.assertEqual("passed", merged["sections"][0]["verdict"])
        self.assertEqual("当众撤掉她的解释权", merged["sections"][0]["irreversible_action"])
        self.assertEqual([], merged["sections"][1]["scene_units"])

    def test_apply_template_rejects_stale_receipt_sha(self) -> None:
        TOOL.export_template(self.receipt, self.template)
        payload = json.loads(self.template.read_text(encoding="utf-8"))
        payload["receipt_sha256"] = "stale"
        self.template.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "receipt_sha256 已失效"):
            TOOL.apply_template(self.receipt, self.template)


if __name__ == "__main__":
    unittest.main()
