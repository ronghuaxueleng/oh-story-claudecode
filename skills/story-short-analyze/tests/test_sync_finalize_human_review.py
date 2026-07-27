from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_finalize_human_review.py"
SPEC = importlib.util.spec_from_file_location("sync_finalize_review", SCRIPT)
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class SyncFinalizeHumanReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "拆文报告.md").write_text("# 报告\n初版内容\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def resolve_first_upgrade_review(self) -> dict:
        path = self.root / "_finalize_human_review.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["upgrade_status"] = "completed"
        data["upgrade_reviews"][0].update(
            {
                "status": "resolved",
                "judgement": "已核对当前过程计划与新版合同一致。",
                "evidence": ["_parallel_plan.json"],
            }
        )
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def test_same_content_and_skill_preserves_existing_judgement(self) -> None:
        SYNC.sync_receipt(self.root)
        self.resolve_first_upgrade_review()
        _, payload, preserved = SYNC.sync_receipt(self.root)
        self.assertTrue(preserved)
        self.assertEqual("resolved", payload["upgrade_reviews"][0]["status"])
        self.assertIn("新版合同", payload["upgrade_reviews"][0]["judgement"])

    def test_markdown_change_resets_judgements(self) -> None:
        SYNC.sync_receipt(self.root)
        self.resolve_first_upgrade_review()
        (self.root / "拆文报告.md").write_text("# 报告\n内容变化\n", encoding="utf-8")
        _, payload, preserved = SYNC.sync_receipt(self.root)
        self.assertFalse(preserved)
        self.assertEqual("pending", payload["upgrade_reviews"][0]["status"])
        self.assertEqual("", payload["upgrade_reviews"][0]["judgement"])

    def test_skill_fingerprint_change_resets_judgements(self) -> None:
        SYNC.sync_receipt(self.root)
        data = self.resolve_first_upgrade_review()
        data["skill_fingerprint"] = "old-skill"
        (self.root / "_finalize_human_review.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        _, payload, preserved = SYNC.sync_receipt(self.root)
        self.assertFalse(preserved)
        self.assertEqual("pending", payload["upgrade_reviews"][0]["status"])


if __name__ == "__main__":
    unittest.main()
