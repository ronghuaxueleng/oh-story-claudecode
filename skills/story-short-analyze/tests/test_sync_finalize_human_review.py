from __future__ import annotations

import importlib.util
import hashlib
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

    def test_newline_and_bom_changes_preserve_existing_judgement(self) -> None:
        SYNC.sync_receipt(self.root)
        before = self.resolve_first_upgrade_review()
        manifest_before = json.loads(
            (self.root / "_content_fingerprints.json").read_text(encoding="utf-8")
        )
        (self.root / "拆文报告.md").write_bytes(
            "\ufeff# 报告\r\n初版内容\r\n".encode("utf-8")
        )
        _, payload, preserved = SYNC.sync_receipt(self.root)
        manifest_after = json.loads(
            (self.root / "_content_fingerprints.json").read_text(encoding="utf-8")
        )
        self.assertTrue(preserved)
        self.assertEqual("resolved", payload["upgrade_reviews"][0]["status"])
        self.assertEqual(before["upgrade_reviews"][0]["judgement"], payload["upgrade_reviews"][0]["judgement"])
        self.assertEqual(manifest_before, manifest_after)

    def test_sync_writes_independent_sha256_manifest(self) -> None:
        _, payload, _ = SYNC.sync_receipt(self.root)
        manifest_path = self.root / "_content_fingerprints.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("sha256", manifest["algorithm"])
        self.assertEqual("utf8-bomless-lf-v1", manifest["normalization"])
        self.assertEqual(
            manifest["aggregate_sha256"], payload["content_fingerprint"]["aggregate_sha256"]
        )
        self.assertNotIn("formal_markdown_sha1s", payload)

    def test_equivalent_legacy_sha1_receipt_migrates_without_reset(self) -> None:
        SYNC.sync_receipt(self.root)
        legacy = self.resolve_first_upgrade_review()
        legacy.pop("content_fingerprint")
        legacy["version"] = 1
        legacy["formal_markdown_sha1s"] = {
            "拆文报告.md": hashlib.sha1(
                "# 报告\n初版内容\n".encode("utf-8")
            ).hexdigest()
        }
        (self.root / "_finalize_human_review.json").write_text(
            json.dumps(legacy, ensure_ascii=False), encoding="utf-8"
        )
        _, payload, preserved = SYNC.sync_receipt(self.root)
        self.assertTrue(preserved)
        self.assertEqual(2, payload["version"])
        self.assertEqual("resolved", payload["upgrade_reviews"][0]["status"])
        self.assertNotIn("formal_markdown_sha1s", payload)

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
