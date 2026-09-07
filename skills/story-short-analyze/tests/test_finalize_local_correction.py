from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_short_analyze_finalize.py"
SPEC = importlib.util.spec_from_file_location("finalize_local_correction", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LocalCorrectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.meta_path = self.root / "_meta.json"
        self.receipt_path = self.root / "_finalize_human_review.json"
        self.hashes = {"拆文报告.md": "unchanged"}
        self.meta = {"skill_fingerprint": "old", "stages_completed": [2, 3, 4, 5, 6], "last_stage_in_progress": None}
        self.receipt = {"skill_fingerprint": "old", "formal_markdown_sha1s": self.hashes,
                        "review_items": [{"id": "HR-1", "status": "resolved", "judgement": "保留人工判断"}]}
        self.meta_path.write_text(json.dumps(self.meta), encoding="utf-8")
        self.receipt_path.write_text(json.dumps(self.receipt), encoding="utf-8")
        assets = self.root / "写作资产"
        assets.mkdir()
        (assets / "来源成文脑图.json").write_text("{}", encoding="utf-8")
        self.validator = SimpleNamespace(__file__=str(self.root / "validator.py"),
            formal_markdown_sha1s=lambda _: self.hashes, compute_skill_fingerprint=lambda: "new")

    def tearDown(self):
        self.temp.cleanup()

    def refresh(self, extra_errors=()):
        errors = [f"{self.meta_path} skill_fingerprint 与当前正式 skill 不一致",
                  f"{self.receipt_path} skill_fingerprint 不是当前版本", *extra_errors]
        result = subprocess.CompletedProcess([], 2, json.dumps({"ok": False, "errors": errors}), "")
        with mock.patch.object(MODULE, "run_command", return_value=result):
            return MODULE.refresh_human_review_receipt(self.root, self.validator,
                local_correction_reason="仅修正SF末尾步骤的先后，原文与人工正文均未改变。")

    def test_only_fingerprints_change_and_human_judgment_is_preserved(self):
        self.assertEqual(1, self.refresh())
        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(self.receipt["review_items"], receipt["review_items"])
        self.assertEqual("new", json.loads(self.meta_path.read_text())["skill_fingerprint"])
        self.assertEqual("old", receipt["local_corrections"][0]["previous_skill_fingerprint"])

    def test_changed_markdown_blocks_without_updating_meta(self):
        self.hashes = {"拆文报告.md": "changed"}
        with self.assertRaisesRegex(ValueError, "Markdown 已变化"):
            self.refresh()
        self.assertEqual("old", json.loads(self.meta_path.read_text())["skill_fingerprint"])

    def test_any_content_failure_blocks(self):
        with self.assertRaisesRegex(ValueError, "非指纹错误"):
            self.refresh(["真实来源层漏行"])
        self.assertEqual("old", json.loads(self.meta_path.read_text())["skill_fingerprint"])

    def test_incomplete_directory_cannot_use_local_refresh(self):
        self.meta["stages_completed"] = [2, 3]
        self.meta_path.write_text(json.dumps(self.meta), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "完整拆解"):
            self.refresh()


if __name__ == "__main__":
    unittest.main()
