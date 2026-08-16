from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_full_draft_review.py"
SPEC = importlib.util.spec_from_file_location("batch_full_draft_review", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchFullDraftReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_dir = self.root / "项目"
        self.assets = self.project_dir / "写作资产"
        self.state = self.assets / "逐节正文进度.json"
        self.draft = self.project_dir / "正文.md"
        self.prose = self.assets / "全文文字颗粒度契约回执.json"
        self.emotion = self.assets / "全文情绪颗粒度契约回执.json"
        self.source = self.root / "拆文库" / "主体书" / "原文" / "主体书.txt"
        self.ledger = self.root / "拆文库" / "主体书" / "写作资产" / "全文情绪颗粒总账.json"
        self.source.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.source.write_text("主体原文。", encoding="utf-8")
        self.ledger.write_text(json.dumps({"beats": []}, ensure_ascii=False), encoding="utf-8")
        self.draft.parent.mkdir(parents=True, exist_ok=True)
        self.draft.write_text("# 测试\n\n1.\n\n第一节正文。\n", encoding="utf-8")
        self._write_state("final_ready")
        self._write_receipts()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_state(self, status: str) -> None:
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(
            json.dumps(
                {
                    "status": status,
                    "paths": {"draft": str(self.draft)},
                    "sections": [],
                    "expected_sections": ["1"],
                    "final_draft_sha256": GATE.SECTION.sha256_file(self.draft) if status == "final_ready" else "",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_receipts(self) -> None:
        self.prose.parent.mkdir(parents=True, exist_ok=True)
        self.prose.write_text(
            json.dumps(
                {
                    "primary_prose_source": {"path": str(self.source)},
                    "draft": None,
                    "gate_status": "pending",
                    "manual_review_provenance": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.emotion.write_text(
            json.dumps(
                {
                    "bindings": {
                        "primary_source_original": {"path": str(self.source)},
                        "source_emotion_ledger": {"path": str(self.ledger)},
                        "draft": None,
                    },
                    "reviewed_by_current_model": False,
                    "draft_status": "pending",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_status_and_next_step_require_full_draft_bindings(self) -> None:
        status = GATE.inspect_full_draft_status(
            project="测试项目",
            project_dir=self.project_dir,
        )
        self.assertEqual("final_ready", status["section_progress_status"])
        self.assertFalse(status["prose_contract"]["bound"])
        self.assertFalse(status["emotional_contract"]["bound"])
        suggestion = GATE.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
        )
        self.assertEqual("bind_full_draft_contracts", suggestion["action"])

    def test_run_cycle_finalizes_then_binds_then_validates(self) -> None:
        self._write_state("sections_passed")

        def fake_finalize(args):
            self._write_state("final_ready")
            return 0

        def fake_bind(**_kwargs):
            prose = json.loads(self.prose.read_text(encoding="utf-8"))
            prose["draft"] = {"sha256": GATE.SECTION.sha256_file(self.draft)}
            prose["gate_status"] = "passed"
            prose["manual_review_provenance"] = {
                "performed_by_current_model": True,
                "full_text_read_by_current_model": True,
                "semantic_fields_generated_by_script": False,
                "review_bound_to_draft_sha256": GATE.SECTION.sha256_file(self.draft),
            }
            self.prose.write_text(json.dumps(prose, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            emotion = json.loads(self.emotion.read_text(encoding="utf-8"))
            emotion["bindings"]["draft"] = {"sha256": GATE.SECTION.sha256_file(self.draft)}
            emotion["reviewed_by_current_model"] = True
            emotion["draft_status"] = "passed"
            self.emotion.write_text(json.dumps(emotion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return [], {"draft": str(self.draft)}

        with mock.patch.object(GATE.SECTION, "command_finalize", side_effect=fake_finalize), mock.patch.object(
            GATE, "bind_full_draft_contracts", side_effect=fake_bind
        ), mock.patch.object(
            GATE,
            "validate_full_draft",
            return_value=([], {"word_count": {"total_word_count": 4}}),
        ):
            result = GATE.run_full_draft_cycle(
                project="测试项目",
                project_dir=self.project_dir,
                zhihu_mode=True,
            )
        self.assertEqual("validate_full_draft", result["action"])
        self.assertEqual(
            ["finalize_section_progress", "bind_full_draft_contracts"],
            result["completed_steps"],
        )
        self.assertEqual(4, result["summary"]["word_count"]["total_word_count"])

    def test_validate_full_draft_returns_word_count_and_zhihu_summary(self) -> None:
        draft_sha = GATE.SECTION.sha256_file(self.draft)
        prose = json.loads(self.prose.read_text(encoding="utf-8"))
        prose["draft"] = {"sha256": draft_sha}
        prose["gate_status"] = "passed"
        prose["manual_review_provenance"] = {
            "performed_by_current_model": True,
            "full_text_read_by_current_model": True,
            "semantic_fields_generated_by_script": False,
            "review_bound_to_draft_sha256": draft_sha,
        }
        self.prose.write_text(json.dumps(prose, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        emotion = json.loads(self.emotion.read_text(encoding="utf-8"))
        emotion["bindings"]["draft"] = {"sha256": draft_sha}
        emotion["reviewed_by_current_model"] = True
        emotion["draft_status"] = "passed"
        self.emotion.write_text(json.dumps(emotion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        with mock.patch.object(GATE.PROSE, "validate_draft_data", return_value=([], {"passed_sections": 1})), mock.patch.object(
            GATE.PROSE, "validate_section_progress_receipt", return_value=[]
        ), mock.patch.object(
            GATE.EMOTION, "validate_draft_data", return_value=([], {})
        ), mock.patch.object(
            GATE.EMOTION, "validate_section_progress_receipt", return_value=[]
        ):
            errors, summary = GATE.validate_full_draft(
                project="测试项目",
                project_dir=self.project_dir,
                zhihu_mode=True,
            )
        self.assertEqual([], errors)
        self.assertEqual(1, summary["prose_summary"]["passed_sections"])
        self.assertEqual(8, summary["word_count"]["total_word_count"])
        self.assertEqual(1, summary["zhihu_section_count"])

    def test_emit_shell_template_contains_high_level_commands(self) -> None:
        template = GATE.emit_shell_template(
            project="测试项目",
            project_dir=self.project_dir,
            zhihu_mode=True,
        )
        self.assertIn('batch_full_draft_review.py" status', template)
        self.assertIn('batch_full_draft_review.py" bind-full-draft-contracts', template)
        self.assertIn('batch_full_draft_review.py" validate-full-draft', template)
        self.assertIn('batch_full_draft_review.py" run-full-draft-cycle', template)

    def test_bind_cli_does_not_forward_zhihu_mode(self) -> None:
        argv = [
            str(SCRIPT),
            "bind-full-draft-contracts",
            "--project",
            "测试项目",
            "--project-dir",
            str(self.project_dir),
            "--zhihu-mode",
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(
                GATE,
                "bind_full_draft_contracts",
                return_value=([], {"bound": True}),
            ) as bind,
        ):
            self.assertEqual(0, GATE.main())
        self.assertNotIn("zhihu_mode", bind.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
