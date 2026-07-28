from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "story_short_write_project_toolbox.py"
)
SPEC = importlib.util.spec_from_file_location("story_short_write_project_toolbox", SCRIPT)
assert SPEC and SPEC.loader
TOOLBOX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOLBOX)

COLD_START_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "initialize_cold_start_from_source_profiles.py"
)
COLD_START_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_cold_start_test",
    COLD_START_SCRIPT,
)
assert COLD_START_SPEC and COLD_START_SPEC.loader
COLD_START = importlib.util.module_from_spec(COLD_START_SPEC)
COLD_START_SPEC.loader.exec_module(COLD_START)


class StoryShortWriteProjectToolboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "book"
        (self.project / "写作资产").mkdir(parents=True)
        self.paths = TOOLBOX.project_paths(self.project)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_parser_registers_stage_workflows(self) -> None:
        parser = TOOLBOX.build_parser()
        subparser_action = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        for command in (
            "prepare-prewrite",
            "prepare-setting",
            "prepare-outline",
            "compile-outline",
            "prepare-draft",
            "start-draft",
            "write-section",
            "rewrite-section",
            "finish-draft-preview",
            "finish-preview",
            "bootstrap-book",
        ):
            self.assertIn(command, subparser_action.choices)

    def test_start_draft_stops_before_init_when_prepare_fails(self) -> None:
        args = argparse.Namespace(
            json=True,
            force=False,
            auto_refresh_legacy_bindings=False,
            use_git_ledger_fallback=False,
        )
        with patch.object(TOOLBOX, "command_prepare_draft", return_value=2), patch.object(
            TOOLBOX,
            "command_init_first_draft",
        ) as initialize:
            result = TOOLBOX.command_start_draft(self.paths, args)
        self.assertEqual(2, result)
        initialize.assert_not_called()

    def test_rewrite_section_resets_before_reopening(self) -> None:
        args = argparse.Namespace(
            section="1",
            read_judgment="已重新实读。",
            json=True,
        )
        with patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "reset_section",
            return_value=0,
        ) as reset, patch.object(TOOLBOX, "command_write_section", return_value=0) as reopen:
            result = TOOLBOX.command_rewrite_section(self.paths, args)
        self.assertEqual(0, result)
        reset.assert_called_once_with(self.paths["section_execution_receipt"], "1")
        self.assertEqual("open", reopen.call_args.args[1].phase)

    def test_finish_preview_initializes_basic_review_task_when_missing(self) -> None:
        source = self.root / "source.txt"
        source.write_text("source", encoding="utf-8")
        self.paths["draft"].write_text("draft", encoding="utf-8")
        self.paths["section_execution_receipt"].write_text(
            json.dumps(
                {
                    "sections": [
                        {"source_read_records": [{"source_path": str(source)}]},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(json=True)
        with patch.object(TOOLBOX.FIRST_DRAFT, "validate_entry", return_value=[]), patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "validate_receipt",
            return_value=({}, []),
        ), patch.object(
            TOOLBOX.FIRST_DRAFT_BASIC_REVIEW,
            "init_receipt",
            return_value=0,
        ) as initialize:
            result = TOOLBOX.command_finish_draft_preview(self.paths, args)

        self.assertEqual(2, result)
        self.assertEqual([source.resolve()], initialize.call_args.kwargs["source_paths"])
        self.assertTrue(initialize.call_args.kwargs["imitation_mode"])

    def test_finish_preview_initializes_mechanical_completion_bindings(self) -> None:
        for key in (
            "draft",
            "writing_receipt",
            "source_receipt",
            "first_draft_entry",
            "sequence_receipt",
            "opening_contract",
            "section_execution_receipt",
        ):
            self.paths[key].write_text("{}\n", encoding="utf-8")
        self.paths["first_draft_basic_review"].write_text(
            json.dumps({"imitation_mode": True}),
            encoding="utf-8",
        )
        args = argparse.Namespace(json=True)
        with patch.object(TOOLBOX.FIRST_DRAFT, "validate_entry", return_value=[]), patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "validate_receipt",
            return_value=({}, []),
        ), patch.object(
            TOOLBOX.FIRST_DRAFT_BASIC_REVIEW,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "command_mark_draft_preview",
            return_value=0,
        ) as mark_preview:
            result = TOOLBOX.command_finish_draft_preview(self.paths, args)

        self.assertEqual(0, result)
        completion = json.loads(self.paths["completion_state"].read_text(encoding="utf-8"))
        preview_checks = {
            item["label"]: item
            for item in completion["checks"]
            if item["label"] in TOOLBOX.SHORT_WRITE_COMPLETION.FIRST_DRAFT_PREVIEW_CHECK_LABELS
        }
        self.assertTrue(all(item["path"] for item in preview_checks.values()))
        self.assertTrue(all(item["field"] == "gate_status" for item in preview_checks.values()))
        self.assertTrue(completion["imitation_mode"])
        mark_preview.assert_called_once()

    def test_compile_outline_compiles_and_validates_derived_assets(self) -> None:
        self.paths["model_semantic_source"].write_text("{}\n", encoding="utf-8")
        self.paths["outline_contract"].write_text("{}\n", encoding="utf-8")
        self.paths["draft_capacity_contract"].write_text("{}\n", encoding="utf-8")
        args = argparse.Namespace(
            json=True,
            legacy_data_module=None,
            from_existing_receipts=False,
        )
        completed = __import__("subprocess").CompletedProcess([], 0, stdout="{}\n", stderr="")
        with patch.object(TOOLBOX.subprocess, "run", return_value=completed) as run, patch.object(
            TOOLBOX.OUTLINE,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "command_errors_for_opening",
            return_value=[],
        ), patch.object(
            TOOLBOX.SEQUENCE,
            "validate",
            return_value=[],
        ), patch.object(
            TOOLBOX.SECTION_SOURCE_BUNDLE,
            "create_bundle",
            return_value=({"gate_status": "passed"}, []),
        ), patch.object(
            TOOLBOX.SECTION_SOURCE_BUNDLE,
            "write_json",
        ) as write_bundle:
            result = TOOLBOX.command_compile_outline(self.paths, args)

        self.assertEqual(0, result)
        self.assertIn("--semantic-source", run.call_args.args[0])
        write_bundle.assert_called_once_with(
            self.paths["section_source_bundle"],
            {"gate_status": "passed"},
        )

    def test_compile_section_review_preserves_script_generated_bindings(self) -> None:
        review_path = self.project / "写作资产" / "逐节首写停检" / "第2节.json"
        review_path.parent.mkdir()
        review_path.write_text(
            json.dumps(
                {
                    "section_id": "2",
                    "source_read_records": [{"source_path": "source.txt"}],
                    "checks": {},
                    "manual_judgment": "",
                    "gate_status": "pending",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        answer = {
            "checks": {"event_flow": {"status": "passed"}},
            "manual_judgment": "已逐项人工复核。",
            "gate_status": "passed",
        }
        self.paths["model_semantic_source"].write_text(
            json.dumps({"section_reviews": {"2": answer}}, ensure_ascii=False),
            encoding="utf-8",
        )

        errors = TOOLBOX.compile_section_review(self.paths, "2")

        self.assertEqual([], errors)
        compiled = json.loads(review_path.read_text(encoding="utf-8"))
        self.assertEqual([{"source_path": "source.txt"}], compiled["source_read_records"])
        self.assertEqual(answer["checks"], compiled["checks"])
        self.assertEqual("passed", compiled["gate_status"])

    def test_write_section_open_exports_compact_semantic_task(self) -> None:
        self.paths["first_draft_entry"].write_text("{}\n", encoding="utf-8")
        review_path = self.project / "写作资产" / "逐节首写停检" / "第1节.json"

        def open_section(_receipt: Path, _section: str, _judgment: str) -> int:
            review_path.parent.mkdir()
            review_path.write_text(
                json.dumps(
                    {
                        "section_id": "1",
                        "source_read_records": [{"source_path": "source.txt"}],
                        "checks": {"event_flow": {"status": "pending"}},
                        "manual_judgment": "",
                        "gate_status": "pending",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return 0

        args = argparse.Namespace(
            section="1",
            phase="open",
            read_judgment="已完整实读原文。",
            json=True,
        )
        with patch.object(TOOLBOX.FIRST_DRAFT, "validate_entry", return_value=[]), patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "open_section",
            side_effect=open_section,
        ):
            result = TOOLBOX.command_write_section(self.paths, args)

        self.assertEqual(0, result)
        semantic = json.loads(self.paths["model_semantic_source"].read_text(encoding="utf-8"))
        task = semantic["section_reviews"]["1"]
        self.assertEqual({"event_flow": {"status": "pending"}}, task["checks"])
        self.assertNotIn("source_read_records", task)

    def test_prepare_prewrite_stops_after_writing_rule_failure(self) -> None:
        args = argparse.Namespace(json=True, batch_size=30)
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "validate_receipt",
            return_value=(["写作规则未通过"], {}),
        ), patch.object(TOOLBOX.SOURCE_READ, "validate_receipt") as source_validate:
            result = TOOLBOX.command_prepare_prewrite(self.paths, args)
        self.assertEqual(2, result)
        source_validate.assert_not_called()

    def test_prepare_prewrite_initializes_and_exports_ledger(self) -> None:
        args = argparse.Namespace(json=True, batch_size=20)
        ledger_payload = {"gate_status": "pending", "skill_rules": [], "source_assets": []}

        def export_review(_ledger: Path, output: Path, batch_size: int) -> dict[str, int]:
            self.assertEqual(20, batch_size)
            output.write_text("{}\n", encoding="utf-8")
            return {"entries": 0, "batches": 0, "cases": 0, "source_refs": 0}

        with patch.object(TOOLBOX.WRITING_RULE, "validate_receipt", return_value=([], {})), patch.object(
            TOOLBOX.SOURCE_READ,
            "validate_receipt",
            return_value=([], {}),
        ), patch.object(
            TOOLBOX.RULE_LEDGER,
            "create_ledger",
            return_value=(ledger_payload, []),
        ), patch.object(
            TOOLBOX.RULE_LEDGER,
            "export_model_review",
            side_effect=export_review,
        ), patch.object(
            TOOLBOX.RULE_LEDGER,
            "validate_prewrite_ledger",
            return_value=[],
        ):
            result = TOOLBOX.command_prepare_prewrite(self.paths, args)

        self.assertEqual(0, result)
        self.assertEqual(
            ledger_payload,
            json.loads(self.paths["ledger"].read_text(encoding="utf-8")),
        )
        self.assertTrue(self.paths["model_review_task"].is_file())

    def test_prepare_draft_stops_before_bundle_when_outline_fails(self) -> None:
        args = argparse.Namespace(json=True)
        with patch.object(
            TOOLBOX.OUTLINE,
            "validate_receipt",
            return_value=["细纲未通过"],
        ), patch.object(TOOLBOX, "command_errors_for_opening") as validate_opening, patch.object(
            TOOLBOX.SECTION_SOURCE_BUNDLE,
            "create_bundle",
        ) as create_bundle:
            result = TOOLBOX.command_prepare_draft(self.paths, args)
        self.assertEqual(2, result)
        validate_opening.assert_not_called()
        create_bundle.assert_not_called()

    def test_validate_opening_reads_receipt_bindings(self) -> None:
        source = self.root / "opening-source.md"
        target = self.project / "小节大纲.md"
        source.write_text("# opening\n", encoding="utf-8")
        target.write_text("## 1. opening\n", encoding="utf-8")
        self.paths["opening_contract"].write_text(
            json.dumps(
                {
                    "primary_source": {"path": str(source)},
                    "target_text": {"path": str(target)},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(json=True)
        with patch.object(
            TOOLBOX.OPENING,
            "validate_receipt",
            return_value=([], {"passed_checks": 8}),
        ) as validate_receipt:
            result = TOOLBOX.command_validate_opening(self.paths, args)

        self.assertEqual(0, result)
        validate_receipt.assert_called_once_with(
            self.paths["opening_contract"],
            source.resolve(),
            target.resolve(),
        )

        with patch.object(
            TOOLBOX.OPENING,
            "validate_receipt",
            return_value=([], {"passed_checks": 8}),
        ) as prepare_validate_receipt:
            errors = TOOLBOX.command_errors_for_opening(self.paths)

        self.assertEqual([], errors)
        prepare_validate_receipt.assert_called_once_with(
            self.paths["opening_contract"],
            source.resolve(),
            target.resolve(),
        )

    def test_init_first_draft_passes_serializable_project_name(self) -> None:
        args = argparse.Namespace(
            force=False,
            auto_refresh_legacy_bindings=False,
            use_git_ledger_fallback=False,
        )
        with patch.object(TOOLBOX.FIRST_DRAFT, "init_entry", return_value=0) as init_entry:
            result = TOOLBOX.command_init_first_draft(self.paths, args)

        self.assertEqual(0, result)
        self.assertEqual(str(self.project), init_entry.call_args.kwargs["project"])
        self.assertIsInstance(init_entry.call_args.kwargs["project"], str)

    def test_cold_start_generates_project_wrappers(self) -> None:
        source = self.root / "source"
        (source / "写作资产").mkdir(parents=True)
        (source / "原文").mkdir()
        profile = source / "book.profile.json"
        for path, content in (
            (profile, "{}"),
            (source / "写作资产" / "仿写无损编译包.json", "{}"),
            (source / "写作资产" / "桥段施工卡.md", "# bridge"),
            (source / "可直接仿写_导语拆解表.md", "# opening"),
            (source / "原文" / "source.txt", "source"),
        ):
            path.write_text(content, encoding="utf-8")

        with patch.object(COLD_START.WRITING_RULE, "create_receipt", return_value=({}, [])), patch.object(
            COLD_START.SOURCE_READ,
            "create_receipt",
            return_value=({}, []),
        ), patch.object(COLD_START.SEQUENCE, "init_setting_receipt"), patch.object(
            COLD_START.SEQUENCE,
            "init_receipt",
        ), patch.object(COLD_START.OUTLINE, "create_receipt", return_value={}), patch.object(
            COLD_START.OPENING,
            "create_receipt",
            return_value={},
        ), patch.object(COLD_START.DRAFT_CAPACITY, "init", return_value={}), patch.object(
            COLD_START.OUTLINE_REBUILDER_SCAFFOLD,
            "generate_scaffold",
            return_value=("export default {};\n", "export {};\n", {}),
        ), patch.object(
            COLD_START.WRAPPERS,
            "generate_wrappers",
            return_value={"ok": True, "generated": ["toolbox"], "errors": [], "removed": []},
        ) as generate_wrappers:
            result = COLD_START.initialize(
                project=self.project,
                primary_source_profile=profile,
                auxiliary_source_profiles=[],
                target_words=10000,
                force=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual("generated:1", result["actions"]["project_wrappers"])
        self.assertTrue((self.project / "写作资产" / "模型语义输入.json").is_file())
        checklist = (self.project / "写作资产" / "冷启动执行清单.md").read_text(encoding="utf-8")
        self.assertIn("compile-outline", checklist)
        self.assertIn("start-draft", checklist)
        self.assertNotIn("prepare-outline", checklist)
        self.assertFalse(
            (self.project / "写作资产" / "重建细纲与容量回执.scaffold.mjs").exists()
        )
        generate_wrappers.assert_called_once()

    def test_legacy_cold_start_can_generate_outline_scaffold(self) -> None:
        source = self.root / "legacy-source"
        (source / "写作资产").mkdir(parents=True)
        (source / "原文").mkdir()
        profile = source / "book.profile.json"
        for path, content in (
            (profile, "{}"),
            (source / "写作资产" / "仿写无损编译包.json", "{}"),
            (source / "写作资产" / "桥段施工卡.md", "# bridge"),
            (source / "可直接仿写_导语拆解表.md", "# opening"),
            (source / "原文" / "source.txt", "source"),
        ):
            path.write_text(content, encoding="utf-8")

        with patch.object(COLD_START.WRITING_RULE, "create_receipt", return_value=({}, [])), patch.object(
            COLD_START.SOURCE_READ,
            "create_receipt",
            return_value=({}, []),
        ), patch.object(COLD_START.SEQUENCE, "init_setting_receipt"), patch.object(
            COLD_START.SEQUENCE,
            "init_receipt",
        ), patch.object(COLD_START.OUTLINE, "create_receipt", return_value={}), patch.object(
            COLD_START.OPENING,
            "create_receipt",
            return_value={},
        ), patch.object(COLD_START.DRAFT_CAPACITY, "init", return_value={}), patch.object(
            COLD_START.OUTLINE_REBUILDER_SCAFFOLD,
            "generate_scaffold",
            return_value=("export default {};\n", "export {};\n", {}),
        ), patch.object(
            COLD_START.WRAPPERS,
            "generate_wrappers",
            return_value={"ok": True, "generated": [], "errors": [], "removed": []},
        ):
            result = COLD_START.initialize(
                project=self.project,
                primary_source_profile=profile,
                auxiliary_source_profiles=[],
                target_words=10000,
                force=False,
                generate_legacy_scaffold=True,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(
            (self.project / "写作资产" / "重建细纲与容量回执.scaffold.mjs").is_file()
        )


if __name__ == "__main__":
    unittest.main()
