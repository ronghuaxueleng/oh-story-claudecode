from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_short_write_completion.py"
)
SPEC = importlib.util.spec_from_file_location("short_write_completion", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ShortWriteCompletionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "book"
        self.asset_dir = self.project / "写作资产"
        self.asset_dir.mkdir(parents=True)
        self.state = self.asset_dir / "短篇全流程状态.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_passed_state(self, status: str = "active") -> dict:
        checks = []
        for index, label in enumerate(sorted(GATE.REQUIRED_CHECK_LABELS)):
            receipt = self.asset_dir / f"receipt-{index}.json"
            receipt.write_text(
                json.dumps({"gate_status": "passed"}),
                encoding="utf-8",
            )
            checks.append(
                {
                    "label": label,
                    "kind": "json_field",
                    "path": str(receipt),
                    "field": "gate_status",
                    "expected": "passed",
                }
            )
        return {
            "version": "1.0",
            "workflow": "story-short-write",
            "project_path": str(self.project),
            "status": status,
            "checks": checks,
            "preview_ready_at": "2026-07-26T00:00:00+00:00" if status == "draft_preview" else "",
            "deep_review_user_confirmed": status == "complete",
            "deep_review_confirmed_at": (
                "2026-07-26T00:01:00+00:00" if status == "complete" else ""
            ),
            "deep_review_confirmation_note": "用户确认继续深审" if status == "complete" else "",
            "next_action": "继续执行。",
            "pause_reason": "",
            "blocker": {},
        }

    def test_active_state_blocks_stop_hook(self) -> None:
        GATE.write_state(self.state, self.create_passed_state())
        output = io.StringIO()
        with redirect_stdout(output):
            result = GATE.hook_result(self.root)
        self.assertEqual(0, result)
        payload = json.loads(output.getvalue())
        self.assertEqual("block", payload["decision"])

    def test_complete_state_allows_stop_hook(self) -> None:
        state = self.create_passed_state(status="complete")
        GATE.write_state(self.state, state)
        output = io.StringIO()
        with redirect_stdout(output):
            result = GATE.hook_result(self.root)
        self.assertEqual(0, result)
        self.assertEqual({"continue": True}, json.loads(output.getvalue()))

    def test_draft_preview_allows_stop_without_deep_checks(self) -> None:
        state = self.create_passed_state(status="draft_preview")
        state["checks"] = [
            check
            for check in state["checks"]
            if check["label"] in GATE.FIRST_DRAFT_PREVIEW_CHECK_LABELS
        ]
        GATE.write_state(self.state, state)
        output = io.StringIO()
        with redirect_stdout(output):
            result = GATE.hook_result(self.root)
        self.assertEqual(0, result)
        self.assertEqual({"continue": True}, json.loads(output.getvalue()))

    def test_draft_preview_requires_basic_review(self) -> None:
        state = self.create_passed_state(status="draft_preview")
        state["checks"] = [
            check
            for check in state["checks"]
            if check["label"] != "first_draft_basic_review"
        ]
        GATE.write_state(self.state, state)
        _, errors = GATE.validate_state(self.state)
        self.assertTrue(any("first_draft_basic_review" in error for error in errors))

    def test_complete_requires_explicit_deep_review_confirmation(self) -> None:
        state = self.create_passed_state(status="complete")
        state["deep_review_user_confirmed"] = False
        state["deep_review_confirmed_at"] = ""
        GATE.write_state(self.state, state)
        _, errors = GATE.validate_state(self.state)
        self.assertTrue(any("用户明确确认" in error for error in errors))

    def test_mark_preview_then_confirm_deep_review(self) -> None:
        state = self.create_passed_state(status="active")
        GATE.write_state(self.state, state)
        with patch(
            "sys.argv",
            ["gate", "mark-draft-preview", "--state", str(self.state)],
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(0, GATE.main())
        preview = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual("draft_preview", preview["status"])
        self.assertFalse(preview["deep_review_user_confirmed"])

        with patch(
            "sys.argv",
            [
                "gate",
                "confirm-deep-review",
                "--state",
                str(self.state),
                "--confirmation-note",
                "用户明确说继续深审",
            ],
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(0, GATE.main())
        confirmed = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual("active", confirmed["status"])
        self.assertTrue(confirmed["deep_review_user_confirmed"])

    def test_invalidated_complete_state_blocks_stop_hook(self) -> None:
        state = self.create_passed_state(status="complete")
        GATE.write_state(self.state, state)
        first = Path(state["checks"][0]["path"])
        first.write_text(json.dumps({"gate_status": "blocked"}), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            result = GATE.hook_result(self.root)
        self.assertEqual(0, result)
        payload = json.loads(output.getvalue())
        self.assertEqual("block", payload["decision"])
        self.assertIn("期望 'passed'", payload["reason"])

    def test_blocked_state_requires_three_attempts_and_resume_entry(self) -> None:
        state = self.create_passed_state(status="blocked")
        state["blocker"] = {
            "reason": "外部服务不可用。",
            "evidence": "连续返回权限错误。",
            "attempts": ["检查权限", "重试命令", "核对输入"],
            "resume_entry": "权限恢复后重新运行门禁。",
        }
        GATE.write_state(self.state, state)
        _, errors = GATE.validate_state(self.state)
        self.assertEqual([], errors)
        state["blocker"]["attempts"] = ["只试了一次"]
        GATE.write_state(self.state, state)
        _, errors = GATE.validate_state(self.state)
        self.assertTrue(any("至少需要 3 条" in error for error in errors))

    def test_init_creates_active_incomplete_scaffold(self) -> None:
        result = GATE.init_state(self.state, self.project, force=False)
        self.assertEqual(0, result)
        data, errors = GATE.validate_state(self.state)
        self.assertEqual("active", data["status"])
        self.assertTrue(errors)
        self.assertEqual(
            GATE.REQUIRED_CHECK_LABELS,
            {item["label"] for item in data["checks"]},
        )


if __name__ == "__main__":
    unittest.main()
