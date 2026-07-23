from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "compare_source_baseline_audit.py"
)
SPEC = importlib.util.spec_from_file_location("compare_source_baseline_audit", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class CompareSourceBaselineAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_text = self.root / "原文.txt"
        self.draft_text = self.root / "正文.md"
        self.source_text.write_text("原文。", encoding="utf-8")
        self.draft_text.write_text("正文。", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_audit(self, path: Path, text: Path, score: int) -> dict:
        data = {
            "file": str(text.resolve()),
            "text": {
                "path": str(text.resolve()),
                "sha256": AUDIT.sha256(text),
            },
            "light_summary": {"total_hits": 1},
            "heavy_summary": {
                "score": score,
                "status": "medium-risk",
                "high_findings": [],
                "medium_findings": [],
            },
            "light_report": {"line_hit_types": {}},
        }
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def test_comparison_binds_both_audits_and_texts(self) -> None:
        source_audit = self.root / "source.json"
        draft_audit = self.root / "draft.json"
        source = self.write_audit(source_audit, self.source_text, 68)
        draft = self.write_audit(draft_audit, self.draft_text, 60)
        result = AUDIT.compare(
            source,
            draft,
            8.0,
            AUDIT.validate_audit_binding(source, source_audit, "主体原文审计"),
            AUDIT.validate_audit_binding(draft, draft_audit, "目标正文审计"),
        )
        self.assertEqual(AUDIT.sha256(self.source_text), result["source"]["text_sha256"])
        self.assertEqual(AUDIT.sha256(self.draft_text), result["draft"]["text_sha256"])
        self.assertEqual(AUDIT.sha256(draft_audit), result["draft"]["audit"]["sha256"])

    def test_legacy_audit_without_text_binding_is_blocked(self) -> None:
        audit = self.root / "legacy.json"
        audit.write_text(json.dumps({"file": str(self.draft_text)}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "旧审计"):
            AUDIT.validate_audit_binding(
                json.loads(audit.read_text(encoding="utf-8")),
                audit,
                "目标正文审计",
            )

    def test_changed_text_invalidates_audit(self) -> None:
        audit = self.root / "draft.json"
        data = self.write_audit(audit, self.draft_text, 60)
        self.draft_text.write_text("正文已修改。", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "正文已变化"):
            AUDIT.validate_audit_binding(data, audit, "目标正文审计")


if __name__ == "__main__":
    unittest.main()
