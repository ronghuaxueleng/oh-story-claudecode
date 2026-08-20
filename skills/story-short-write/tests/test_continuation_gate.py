from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_continuation_gate.py"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class ContinuationGateTest(unittest.TestCase):
    def run_gate(self, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), "--project-dir", str(project), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_skill_documents_no_goal_and_no_yield_contract(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("validate_continuation_gate.py", text)
        self.assertIn("禁止调用 goal 机制暂停或续跑", text)
        self.assertIn("发送空白 final", text)
        self.assertIn("中间更新后必须立即继续", text)

    def test_progress_report_is_never_a_legal_terminal_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_gate(Path(tmp), "--reason", "progress_report")
        self.assertEqual(result.returncode, 2)
        self.assertIn("terminal_response_forbidden: true", result.stdout)

    def test_empty_final_commentary_yield_and_goal_pause_are_illegal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for reason in ("empty_final", "commentary_only_yield", "goal_pause"):
                with self.subTest(reason=reason):
                    result = self.run_gate(project, "--reason", reason)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("terminal_response_forbidden: true", result.stdout)

    def test_user_stop_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            blocked = self.run_gate(project, "--reason", "user_stop")
            passed = self.run_gate(
                project, "--reason", "user_stop", "--user-stop-confirmed"
            )
        self.assertEqual(blocked.returncode, 2)
        self.assertEqual(passed.returncode, 0)

    def test_initial_draft_stop_rejects_noncurrent_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            assets = project / "写作资产"
            draft = project / "正文.md"
            draft.write_text("# 书名\n1.\n正文。\n", encoding="utf-8")
            write_json(
                assets / "非当前进度.json",
                {
                    "gate_status": "passed",
                },
            )
            result = self.run_gate(
                project, "--reason", "initial_draft_stop", "--platform", "zhihu"
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("正文覆盖回执", result.stdout)

    def test_external_blocker_requires_three_consecutive_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            receipt = project / "blocker.json"
            write_json(
                receipt,
                {
                    "status": "blocked",
                    "recoverable": False,
                    "blocking_condition": "external service unavailable",
                    "blocker_type": "third_party_service_unavailable",
                    "external_dependency": "remote generation service",
                    "consecutive_attempts": 2,
                    "evidence": ["attempt-1", "attempt-2", "attempt-3"],
                },
            )
            blocked = self.run_gate(
                project,
                "--reason",
                "external_blocker",
                "--blocker-receipt",
                str(receipt),
            )
            data = json.loads(receipt.read_text(encoding="utf-8"))
            data["consecutive_attempts"] = 3
            write_json(receipt, data)
            passed = self.run_gate(
                project,
                "--reason",
                "external_blocker",
                "--blocker-receipt",
                str(receipt),
            )
        self.assertEqual(blocked.returncode, 2)
        self.assertEqual(passed.returncode, 0)

    def test_local_validator_errors_are_not_external_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            receipt = project / "blocker.json"
            write_json(
                receipt,
                {
                    "status": "blocked",
                    "recoverable": False,
                    "blocking_condition": "local validator has missing fields",
                    "blocker_type": "local_workflow_error",
                    "external_dependency": "none",
                    "consecutive_attempts": 3,
                    "evidence": ["attempt-1", "attempt-2", "attempt-3"],
                },
            )
            result = self.run_gate(
                project,
                "--reason",
                "external_blocker",
                "--blocker-receipt",
                str(receipt),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("真实外部依赖类型", result.stdout)
