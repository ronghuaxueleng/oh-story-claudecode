from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_formal_audit.py"
SPEC = importlib.util.spec_from_file_location("batch_formal_audit", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchFormalAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_dir = self.root / "项目"
        self.assets = self.project_dir / "写作资产"
        self.draft = self.project_dir / "正文.md"
        self.audit_dir = self.assets / "正式审计"
        self.audit_json = self.audit_dir / "正文.full_audit.json"
        self.summary = self.assets / "外部分块审计对齐摘要.json"
        self.standard = self.assets / "内部审计标准.json"
        self.csv = self.assets / "外部分块审计对齐.csv"
        self.draft.parent.mkdir(parents=True, exist_ok=True)
        self.draft.write_text("正文。", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_audit(self) -> None:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_json.write_text(
            json.dumps({"file": str(self.draft), "source": {"path": str(self.draft)}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_status_and_next_step_require_formal_audit_first(self) -> None:
        status = GATE.inspect_formal_audit_status(
            project="测试项目",
            project_dir=self.project_dir,
        )
        self.assertFalse(status["audit_json"]["exists"])
        suggestion = GATE.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
            with_calibration=True,
        )
        self.assertEqual("run_formal_audit", suggestion["action"])

    def test_next_step_requires_alignment_when_calibration_enabled(self) -> None:
        self._write_audit()
        suggestion = GATE.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
            with_calibration=True,
        )
        self.assertEqual("run_external_alignment", suggestion["action"])

    def test_run_cycle_runs_audit_then_alignment(self) -> None:
        def fake_audit(**_kwargs):
            self._write_audit()
            return [], {"audit_json": str(self.audit_json)}

        def fake_align(**_kwargs):
            self.summary.write_text("{}", encoding="utf-8")
            self.standard.write_text("{}", encoding="utf-8")
            self.csv.write_text("x", encoding="utf-8")
            return [], {"alignment_summary": str(self.summary)}

        with mock.patch.object(GATE, "run_formal_audit", side_effect=fake_audit), mock.patch.object(
            GATE, "run_external_alignment", side_effect=fake_align
        ):
            result = GATE.run_audit_cycle(
                project="测试项目",
                project_dir=self.project_dir,
                with_calibration=True,
            )
        self.assertEqual("formal_audit_ready", result["action"])
        self.assertEqual(["run_formal_audit", "run_external_alignment"], result["completed_steps"])

    def test_emit_shell_template_contains_high_level_commands(self) -> None:
        template = GATE.emit_shell_template(
            project="测试项目",
            project_dir=self.project_dir,
            with_calibration=True,
        )
        self.assertIn('batch_formal_audit.py" status', template)
        self.assertIn('batch_formal_audit.py" next-step', template)
        self.assertIn('batch_formal_audit.py" run-audit-cycle', template)
        self.assertIn("--with-calibration", template)


if __name__ == "__main__":
    unittest.main()
