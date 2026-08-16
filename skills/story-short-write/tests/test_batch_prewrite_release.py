from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_prewrite_release.py"
SPEC = importlib.util.spec_from_file_location("batch_prewrite_release", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchPrewriteReleaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.writing_receipt = self.root / "写作规则读取回执.json"
        self.source_receipt = self.root / "拆文读取回执.json"
        self.ledger = self.root / "规则执行台账.json"
        self.sequence_receipt = self.root / "顺序契约回执.json"
        self.opening_contract = self.root / "开头承重契约回执_正文.json"
        self.outline_contract = self.root / "细纲表演验收回执.json"
        self.outline = self.root / "小节大纲.md"
        self.prose_contract = self.root / "全文文字颗粒度契约回执.json"
        self.emotional_contract = self.root / "全文情绪颗粒度契约回执.json"
        self.primary_source_original = self.root / "主体书.txt"
        self.source_emotion_ledger = self.root / "全文情绪颗粒总账.json"
        self.profile = self.root / "project.profile.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_validate_passes_when_underlying_gates_pass(self) -> None:
        original_outline = GATE.OUTLINE.validate_receipt
        original_prewrite = GATE.DRAFT_PREWRITE.validate_batch
        original_release = GATE.WRITE_RELEASE.validate_release
        try:
            GATE.OUTLINE.validate_receipt = lambda *_args, **_kwargs: []
            GATE.DRAFT_PREWRITE.validate_batch = (
                lambda **_kwargs: ([], {"prose_summary": {"ok": True}, "emotional_summary": {"ok": True}})
            )
            GATE.WRITE_RELEASE.validate_release = lambda *_args, **_kwargs: []
            errors, summary = GATE.validate_batch(
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                ledger=self.ledger,
                sequence_receipt=self.sequence_receipt,
                opening_contract=self.opening_contract,
                outline_contract=self.outline_contract,
                outline=self.outline,
                prose_contract=self.prose_contract,
                emotional_contract=self.emotional_contract,
                primary_source_original=self.primary_source_original,
                source_emotion_ledger=self.source_emotion_ledger,
                profile=self.profile,
            )
        finally:
            GATE.OUTLINE.validate_receipt = original_outline
            GATE.DRAFT_PREWRITE.validate_batch = original_prewrite
            GATE.WRITE_RELEASE.validate_release = original_release
        self.assertEqual([], errors)
        self.assertTrue(summary["outline_performance_passed"])
        self.assertTrue(summary["draft_prewrite_passed"])
        self.assertTrue(summary["write_release_passed"])

    def test_validate_reuses_successful_contract_checks_in_release_gate(self) -> None:
        original_outline = GATE.OUTLINE.validate_receipt
        original_prewrite = GATE.DRAFT_PREWRITE.validate_batch
        original_release = GATE.WRITE_RELEASE.validate_release
        captured = {}
        try:
            GATE.OUTLINE.validate_receipt = lambda *_args, **_kwargs: []
            GATE.DRAFT_PREWRITE.validate_batch = (
                lambda **_kwargs: ([], {"prose_summary": {}, "emotional_summary": {}})
            )
            for path in (
                self.outline_contract,
                self.prose_contract,
                self.emotional_contract,
            ):
                path.write_text("{}", encoding="utf-8")

            def capture_release(*_args, **kwargs):
                captured.update(kwargs.get("prevalidated_contracts") or {})
                return []

            GATE.WRITE_RELEASE.validate_release = capture_release
            errors, summary = GATE.validate_batch(
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                ledger=self.ledger,
                sequence_receipt=self.sequence_receipt,
                opening_contract=self.opening_contract,
                outline_contract=self.outline_contract,
                outline=self.outline,
                prose_contract=self.prose_contract,
                emotional_contract=self.emotional_contract,
                primary_source_original=self.primary_source_original,
                source_emotion_ledger=self.source_emotion_ledger,
                profile=self.profile,
            )
        finally:
            GATE.OUTLINE.validate_receipt = original_outline
            GATE.DRAFT_PREWRITE.validate_batch = original_prewrite
            GATE.WRITE_RELEASE.validate_release = original_release
        self.assertEqual([], errors)
        self.assertEqual(
            ["outline_contract", "prose_contract", "emotional_contract"],
            summary["reused_contract_validations"],
        )
        self.assertEqual(set(summary["reused_contract_validations"]), set(captured))

    def test_validate_accumulates_all_stage_failures(self) -> None:
        original_outline = GATE.OUTLINE.validate_receipt
        original_prewrite = GATE.DRAFT_PREWRITE.validate_batch
        original_release = GATE.WRITE_RELEASE.validate_release
        try:
            GATE.OUTLINE.validate_receipt = lambda *_args, **_kwargs: ["outline failed"]
            GATE.DRAFT_PREWRITE.validate_batch = (
                lambda **_kwargs: (["prewrite failed"], {"prose_summary": {}, "emotional_summary": {}})
            )
            GATE.WRITE_RELEASE.validate_release = lambda *_args, **_kwargs: ["release failed"]
            errors, summary = GATE.validate_batch(
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                ledger=self.ledger,
                sequence_receipt=self.sequence_receipt,
                opening_contract=self.opening_contract,
                outline_contract=self.outline_contract,
                outline=self.outline,
                prose_contract=self.prose_contract,
                emotional_contract=self.emotional_contract,
                primary_source_original=self.primary_source_original,
                source_emotion_ledger=self.source_emotion_ledger,
                profile=self.profile,
            )
        finally:
            GATE.OUTLINE.validate_receipt = original_outline
            GATE.DRAFT_PREWRITE.validate_batch = original_prewrite
            GATE.WRITE_RELEASE.validate_release = original_release
        self.assertIn("细纲表演验收门禁未通过", errors)
        self.assertIn("正文前合同批次未通过", errors)
        self.assertIn("正文写作放行闸未通过", errors)
        self.assertFalse(summary["outline_performance_passed"])
        self.assertFalse(summary["draft_prewrite_passed"])
        self.assertFalse(summary["write_release_passed"])

    def test_main_validate_prints_passed_summary(self) -> None:
        original_validate = GATE.validate_batch
        original_argv = sys.argv[:]
        stdout = io.StringIO()
        try:
            GATE.validate_batch = lambda **_kwargs: (
                [],
                {
                    "outline_performance_passed": True,
                    "draft_prewrite_passed": True,
                    "write_release_passed": True,
                },
            )
            sys.argv = [
                "batch_prewrite_release.py",
                "validate",
                "--writing-receipt", str(self.writing_receipt),
                "--source-receipt", str(self.source_receipt),
                "--ledger", str(self.ledger),
                "--sequence-receipt", str(self.sequence_receipt),
                "--opening-contract", str(self.opening_contract),
                "--outline-contract", str(self.outline_contract),
                "--outline", str(self.outline),
                "--prose-contract", str(self.prose_contract),
                "--emotional-contract", str(self.emotional_contract),
                "--primary-source-original", str(self.primary_source_original),
                "--source-emotion-ledger", str(self.source_emotion_ledger),
                "--profile", str(self.profile),
            ]
            with contextlib.redirect_stdout(stdout):
                code = GATE.main()
        finally:
            GATE.validate_batch = original_validate
            sys.argv = original_argv
        self.assertEqual(0, code)
        text = stdout.getvalue()
        self.assertIn("batch_prewrite_release: passed", text)
        self.assertIn('"write_release_passed": true', text)

    def test_prepare_and_validate_stops_when_prepare_fails(self) -> None:
        original_prepare = GATE.DRAFT_PREWRITE.prepare_batch
        original_validate = GATE.validate_batch
        try:
            GATE.DRAFT_PREWRITE.prepare_batch = lambda **_kwargs: (
                ["prepare failed"],
                {"prose_outline_bound": False},
            )
            GATE.validate_batch = lambda **_kwargs: self.fail("validate_batch should not run after prepare failure")
            errors, summary = GATE.prepare_and_validate_batch(
                project="测试项目",
                source_original=self.primary_source_original,
                source_emotion_ledger=self.source_emotion_ledger,
                outline=self.outline,
                prose_receipt=self.prose_contract,
                emotional_receipt=self.emotional_contract,
                force_prose_receipt=False,
                force_emotional_receipt=False,
                prose_plan=None,
                emotional_plan=None,
                beat_mapping=None,
                outline_contract=self.outline_contract,
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                ledger=self.ledger,
                sequence_receipt=self.sequence_receipt,
                opening_contract=self.opening_contract,
                profile=self.profile,
            )
        finally:
            GATE.DRAFT_PREWRITE.prepare_batch = original_prepare
            GATE.validate_batch = original_validate
        self.assertIn("正文前合同批次 prepare 未通过", errors)
        self.assertEqual({"prepare_summary": {"prose_outline_bound": False}}, summary)

    def test_prepare_and_validate_runs_validate_after_prepare(self) -> None:
        original_prepare = GATE.DRAFT_PREWRITE.prepare_batch
        original_validate = GATE.validate_batch
        try:
            GATE.DRAFT_PREWRITE.prepare_batch = lambda **_kwargs: (
                [],
                {"prose_outline_bound": True, "emotional_outline_bound": True},
            )
            GATE.validate_batch = lambda **_kwargs: (
                [],
                {
                    "outline_performance_passed": True,
                    "draft_prewrite_passed": True,
                    "write_release_passed": True,
                },
            )
            errors, summary = GATE.prepare_and_validate_batch(
                project="测试项目",
                source_original=self.primary_source_original,
                source_emotion_ledger=self.source_emotion_ledger,
                outline=self.outline,
                prose_receipt=self.prose_contract,
                emotional_receipt=self.emotional_contract,
                force_prose_receipt=False,
                force_emotional_receipt=False,
                prose_plan=None,
                emotional_plan=None,
                beat_mapping=None,
                outline_contract=self.outline_contract,
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                ledger=self.ledger,
                sequence_receipt=self.sequence_receipt,
                opening_contract=self.opening_contract,
                profile=self.profile,
            )
        finally:
            GATE.DRAFT_PREWRITE.prepare_batch = original_prepare
            GATE.validate_batch = original_validate
        self.assertEqual([], errors)
        self.assertTrue(summary["prepare_summary"]["prose_outline_bound"])
        self.assertTrue(summary["write_release_passed"])

    def test_main_prepare_validate_prints_passed_summary(self) -> None:
        original_prepare_validate = GATE.prepare_and_validate_batch
        original_argv = sys.argv[:]
        stdout = io.StringIO()
        try:
            GATE.prepare_and_validate_batch = lambda **_kwargs: (
                [],
                {
                    "prepare_summary": {"prose_outline_bound": True},
                    "outline_performance_passed": True,
                    "draft_prewrite_passed": True,
                    "write_release_passed": True,
                },
            )
            sys.argv = [
                "batch_prewrite_release.py",
                "prepare-validate",
                "--project", "测试项目",
                "--source-original", str(self.primary_source_original),
                "--source-emotion-ledger", str(self.source_emotion_ledger),
                "--outline", str(self.outline),
                "--prose-receipt", str(self.prose_contract),
                "--emotional-receipt", str(self.emotional_contract),
                "--writing-receipt", str(self.writing_receipt),
                "--source-receipt", str(self.source_receipt),
                "--ledger", str(self.ledger),
                "--sequence-receipt", str(self.sequence_receipt),
                "--opening-contract", str(self.opening_contract),
                "--outline-contract", str(self.outline_contract),
                "--profile", str(self.profile),
            ]
            with contextlib.redirect_stdout(stdout):
                code = GATE.main()
        finally:
            GATE.prepare_and_validate_batch = original_prepare_validate
            sys.argv = original_argv
        self.assertEqual(0, code)
        text = stdout.getvalue()
        self.assertIn("batch_prewrite_release: passed", text)
        self.assertIn('"prepare_summary"', text)

    def test_main_prepare_validate_prints_blocked_when_prepare_fails(self) -> None:
        original_prepare_validate = GATE.prepare_and_validate_batch
        original_argv = sys.argv[:]
        stdout = io.StringIO()
        try:
            GATE.prepare_and_validate_batch = lambda **_kwargs: (
                ["prepare failed"],
                {"prepare_summary": {"prose_outline_bound": False}},
            )
            sys.argv = [
                "batch_prewrite_release.py",
                "prepare-validate",
                "--project", "测试项目",
                "--source-original", str(self.primary_source_original),
                "--source-emotion-ledger", str(self.source_emotion_ledger),
                "--outline", str(self.outline),
                "--prose-receipt", str(self.prose_contract),
                "--emotional-receipt", str(self.emotional_contract),
                "--writing-receipt", str(self.writing_receipt),
                "--source-receipt", str(self.source_receipt),
                "--ledger", str(self.ledger),
                "--sequence-receipt", str(self.sequence_receipt),
                "--opening-contract", str(self.opening_contract),
                "--outline-contract", str(self.outline_contract),
                "--profile", str(self.profile),
            ]
            with contextlib.redirect_stdout(stdout):
                code = GATE.main()
        finally:
            GATE.prepare_and_validate_batch = original_prepare_validate
            sys.argv = original_argv
        self.assertEqual(2, code)
        text = stdout.getvalue()
        self.assertIn("batch_prewrite_release: blocked", text)
        self.assertIn("- prepare failed", text)


if __name__ == "__main__":
    unittest.main()
