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
            "prepare-draft",
            "finish-draft-preview",
        ):
            self.assertIn(command, subparser_action.choices)

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
        generate_wrappers.assert_called_once()


if __name__ == "__main__":
    unittest.main()
