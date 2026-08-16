from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_postdraft_release.py"
SPEC = importlib.util.spec_from_file_location("batch_postdraft_release", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchPostdraftReleaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_dir = self.root / "项目"
        self.assets = self.project_dir / "写作资产"
        self.draft = self.project_dir / "正文.md"
        self.setting = self.project_dir / "设定.md"
        self.outline = self.project_dir / "小节大纲.md"
        self.writing_receipt = self.assets / "写作规则读取回执.json"
        self.source_receipt = self.assets / "拆文读取回执.json"
        self.ledger = self.assets / "规则执行台账.json"
        self.sequence = self.assets / "顺序契约回执.json"
        self.opening = self.assets / "开头承重契约回执_正文.json"
        self.post = self.assets / "写后人工语义复核回执.json"
        self.completion = self.assets / "短篇全流程状态.json"
        self.formal_audit = self.assets / "正式审计" / "正文.full_audit.json"
        self.false_pass = self.assets / "外部分块审计对齐摘要.json"
        self.platform = self.assets / "平台格式校验回执.json"
        self.source_root = self.root / "拆文库" / "主体书"
        self.opening_source = self.source_root / "可直接仿写_导语拆解表.md"
        self.draft.parent.mkdir(parents=True, exist_ok=True)
        self.assets.mkdir(parents=True, exist_ok=True)
        self.source_root.mkdir(parents=True, exist_ok=True)
        self.draft.write_text("# 测试\n丈夫替她求情，我把他的手拿开。\n", encoding="utf-8")
        self.setting.write_text("设定。", encoding="utf-8")
        self.outline.write_text("大纲。", encoding="utf-8")
        self.opening_source.write_text("导语资产。", encoding="utf-8")
        self._write_gate_json(self.writing_receipt)
        self._write_gate_json(self.sequence)
        self.platform.write_text(json.dumps({"gate_status": "passed"}, ensure_ascii=False), encoding="utf-8")
        self.source_receipt.write_text(
            json.dumps(
                {"gate_status": "passed", "sources": [{"role": "main", "root": str(self.source_root)}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_gate_json(self, path: Path, status: str = "passed") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"gate_status": status}, ensure_ascii=False), encoding="utf-8")

    def _write_completion_state(self) -> None:
        payload = {
            "version": "1.0",
            "workflow": "story-short-write",
            "project_path": str(self.project_dir),
            "status": "active",
            "checks": GATE.build_completion_checks(
                GATE.default_paths(project="测试项目", project_dir=self.project_dir)
            ),
            "next_action": "继续执行。",
            "pause_reason": "",
            "blocker": {},
        }
        GATE.COMPLETE.write_state(self.completion, payload)

    def _write_completion_dependencies(self) -> None:
        self._write_gate_json(self.assets / "正文开写前最终放行回执.json")
        self._write_gate_json(self.assets / "全文文字颗粒度契约回执.json")
        emotion = self.assets / "全文情绪颗粒度契约回执.json"
        emotion.write_text(json.dumps({"draft_status": "passed"}, ensure_ascii=False), encoding="utf-8")
        self.ledger.write_text(json.dumps({"gate_status": "passed"}, ensure_ascii=False), encoding="utf-8")

    def test_prepare_initializes_opening_postwrite_and_completion(self) -> None:
        with mock.patch.object(GATE.OPENING, "create_receipt", return_value={"gate_status": "pending"}), mock.patch.object(
            GATE.POST, "create_receipt", return_value={"gate_status": "pending"}
        ):
            errors, summary = GATE.prepare_postdraft_release(
                project="测试项目",
                project_dir=self.project_dir,
            )
        self.assertEqual([], errors)
        self.assertTrue(self.opening.is_file())
        self.assertTrue(self.post.is_file())
        self.assertTrue(self.completion.is_file())
        self.assertIn("completion_state_initialized", summary)

    def test_status_and_next_step_stop_at_opening_receipt(self) -> None:
        self.opening.write_text(json.dumps({"gate_status": "pending"}, ensure_ascii=False), encoding="utf-8")
        self.post.write_text(json.dumps({"gate_status": "pending"}, ensure_ascii=False), encoding="utf-8")
        self._write_completion_state()
        with mock.patch.object(GATE.OPENING, "validate_receipt", return_value=(["未通过"], {"passed_checks": 0})):
            status = GATE.inspect_postdraft_release_status(
                project="测试项目",
                project_dir=self.project_dir,
            )
            suggestion = GATE.suggest_next_step(
                project="测试项目",
                project_dir=self.project_dir,
            )
        self.assertFalse(status["opening_receipt"]["passed"])
        self.assertEqual("complete_opening_receipt", suggestion["action"])

    def test_next_step_runs_formal_audit_chain_before_ledger(self) -> None:
        self.opening.write_text(json.dumps({"gate_status": "passed"}, ensure_ascii=False), encoding="utf-8")
        self.post.write_text(json.dumps({"gate_status": "passed"}, ensure_ascii=False), encoding="utf-8")
        self._write_completion_dependencies()
        self._write_completion_state()
        with mock.patch.object(
            GATE.OPENING, "validate_receipt", return_value=([], {"passed_checks": 9})
        ), mock.patch.object(
            GATE.POST, "validate_sequence_receipt_for_text", return_value=[]
        ), mock.patch.object(
            GATE.POST, "validate_receipt", return_value=([], {"reviewed_human_checks": 10})
        ), mock.patch.object(
            GATE.LEDGER, "validate_ledger", return_value=([], {})
        ), mock.patch.object(
            GATE.FORMAL_AUDIT,
            "inspect_formal_audit_status",
            return_value={
                "audit_json": {"exists": False, "fresh": False, "errors": []},
                "alignment_summary": {"exists": False, "fresh": False},
                "internal_standard": {"exists": False, "fresh": False},
            },
        ):
            suggestion = GATE.suggest_next_step(
                project="测试项目",
                project_dir=self.project_dir,
            )
        self.assertEqual("run_formal_audit_chain", suggestion["action"])

    def test_run_cycle_runs_formal_audit_then_ledger_then_marks_complete(self) -> None:
        self.opening.write_text(json.dumps({"gate_status": "passed"}, ensure_ascii=False), encoding="utf-8")
        self.post.write_text(json.dumps({"gate_status": "passed"}, ensure_ascii=False), encoding="utf-8")
        self.ledger.write_text("{}", encoding="utf-8")
        self.formal_audit.parent.mkdir(parents=True, exist_ok=True)
        self.formal_audit.write_text("{}", encoding="utf-8")
        self.false_pass.write_text("{}", encoding="utf-8")
        self._write_completion_dependencies()
        self._write_completion_state()

        def fake_status(**_kwargs):
            return {
                "project": "测试项目",
                "project_dir": str(self.project_dir),
                "opening_receipt": {"exists": True, "passed": True, "errors": [], "passed_checks": 9, "source": ""},
                "post_write_receipt": {"exists": True, "passed": True, "errors": []},
                "ledger": {"exists": True, "passed": False, "errors": ["待绑定"], "summary": {}},
                "formal_audit_exists": True,
                "anti_false_pass_review_exists": True,
                "formal_audit_status": {
                    "audit_json": {"exists": False, "fresh": False, "errors": []},
                    "alignment_summary": {"exists": False, "fresh": False},
                    "internal_standard": {"exists": False, "fresh": False},
                },
                "completion_state": {"exists": True, "valid": True, "errors": []},
            }

        def fake_status_after_audit(**_kwargs):
            return {
                **fake_status(),
                "formal_audit_status": {
                    "audit_json": {"exists": True, "fresh": True, "errors": []},
                    "alignment_summary": {"exists": True, "fresh": True},
                    "internal_standard": {"exists": True, "fresh": True},
                },
            }

        def fake_status_after_ledger(**_kwargs):
            return {
                **fake_status_after_audit(),
                "ledger": {"exists": True, "passed": True, "errors": [], "summary": {}},
            }

        with mock.patch.object(GATE, "inspect_postdraft_release_status", side_effect=[fake_status(), fake_status_after_audit(), fake_status_after_ledger()]), mock.patch.object(
            GATE.FORMAL_AUDIT, "run_audit_cycle", return_value={"action": "formal_audit_ready", "completed_steps": ["run_formal_audit", "run_external_alignment"]}
        ), mock.patch.object(
            GATE.LEDGER, "preflight_final_rebind", return_value=([], {"estimated_manual_rebind_count": 0})
        ), mock.patch.object(
            GATE.LEDGER, "bind_artifacts", return_value=[]
        ), mock.patch.object(
            GATE.LEDGER, "validate_ledger", return_value=([], {"completed": 1})
        ):
            result = GATE.run_postdraft_release_cycle(
                project="测试项目",
                project_dir=self.project_dir,
            )
        self.assertEqual("mark_complete", result["action"])
        self.assertEqual(["run_formal_audit_chain", "bind_and_validate_ledger"], result["completed_steps"])
        state, errors = GATE.COMPLETE.validate_state(self.completion)
        self.assertEqual([], errors)
        self.assertEqual("complete", state["status"])

    def test_emit_shell_template_contains_high_level_commands(self) -> None:
        template = GATE.emit_shell_template(
            project="测试项目",
            project_dir=self.project_dir,
        )
        self.assertIn('batch_postdraft_release.py" prepare-postdraft-release', template)
        self.assertIn('batch_postdraft_release.py" status', template)
        self.assertIn('batch_postdraft_release.py" next-step', template)
        self.assertIn('batch_postdraft_release.py" run-postdraft-release-cycle', template)


if __name__ == "__main__":
    unittest.main()
