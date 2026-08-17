from __future__ import annotations

import hashlib
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
        self.assertIn("终止型回复一律禁止", text)
        self.assertIn("禁止调用 `create_goal / get_goal / update_goal`", text)
        self.assertIn("禁止发送空白 `final`", text)
        self.assertIn("commentary-only", text)

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

    def test_initial_draft_stop_requires_final_ready_contracts_and_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            assets = project / "写作资产"
            draft = project / "正文.md"
            draft.write_text("# 书名\n1.\n正文。\n", encoding="utf-8")
            digest = hashlib.sha256(draft.read_bytes()).hexdigest()
            char_count = 5
            write_json(
                assets / "逐节正文进度.json",
                {
                    "status": "final_ready",
                    "final_draft_sha256": digest,
                    "final_char_count": char_count,
                    "sections": [{"section_id": "1", "status": "passed"}],
                },
            )
            write_json(
                assets / "全文文字颗粒度契约回执.json",
                {
                    "gate_status": "passed",
                    "draft": {"path": str(draft), "sha256": digest},
                },
            )
            write_json(
                assets / "全文情绪颗粒度契约回执.json",
                {
                    "draft_status": "passed",
                    "bindings": {"draft": {"path": str(draft), "sha256": digest}},
                },
            )
            result = self.run_gate(
                project, "--reason", "initial_draft_stop", "--platform", "zhihu"
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
                    "consecutive_attempts": 2,
                    "evidence": ["attempt-1", "attempt-2"],
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
