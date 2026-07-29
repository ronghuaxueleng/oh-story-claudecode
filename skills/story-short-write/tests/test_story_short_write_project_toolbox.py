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

REGISTRY_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "project_tool_wrapper_registry.py"
)
REGISTRY_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_project_tool_wrapper_registry_test",
    REGISTRY_SCRIPT,
)
assert REGISTRY_SPEC and REGISTRY_SPEC.loader
REGISTRY = importlib.util.module_from_spec(REGISTRY_SPEC)
REGISTRY_SPEC.loader.exec_module(REGISTRY)


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

    def test_parser_enables_legacy_refresh_by_default_for_draft_entrypoints(self) -> None:
        parser = TOOLBOX.build_parser()
        start_args = parser.parse_args(["start-draft"])
        release_args = parser.parse_args(["draft-release"])
        init_args = parser.parse_args(["init-first-draft"])

        self.assertTrue(start_args.auto_refresh_legacy_bindings)
        self.assertTrue(release_args.auto_refresh_legacy_bindings)
        self.assertTrue(init_args.auto_refresh_legacy_bindings)

    def test_repair_source_stack_can_refresh_without_appending_auxiliary_sources(self) -> None:
        args = TOOLBOX.build_parser().parse_args(["repair-source-stack"])

        self.assertEqual([], args.aux_source_profile)

    def test_project_audit_wrapper_forwards_global_args_before_fixed_subcommand(self) -> None:
        fake_skill = self.root / "story_short_write_project_toolbox.py"
        fake_skill.write_text(
            "import json, sys\nprint(json.dumps(sys.argv[1:], ensure_ascii=False))\n",
            encoding="utf-8",
        )
        wrapper = self.root / "项目总诊断.py"
        wrapper.write_text(
            REGISTRY.build_project_audit_wrapper(
                script_dir=self.root,
                paths=self.paths,
                use_git_ledger_fallback=False,
            ),
            encoding="utf-8",
        )

        completed = __import__("subprocess").run(
            ["python3", str(wrapper), "--json"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode)
        self.assertEqual(
            [
                "--project",
                str(self.project),
                "--json",
                "audit-project",
                "--write-report",
            ],
            json.loads(completed.stdout),
        )

    def test_archive_source_stack_receipts_preserves_rule_ledger(self) -> None:
        self.paths["source_receipt"].write_text("{}\n", encoding="utf-8")
        self.paths["ledger"].write_text('{"gate_status":"pending"}\n', encoding="utf-8")
        self.paths["model_review_task"].write_text("{}\n", encoding="utf-8")

        actions = TOOLBOX.archive_source_stack_receipts(
            self.paths,
            "source stack changed",
        )

        self.assertTrue(self.paths["ledger"].is_file())
        self.assertFalse(self.paths["source_receipt"].exists())
        self.assertFalse(self.paths["model_review_task"].exists())
        self.assertFalse(any("规则执行台账.json" in action for action in actions))

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

    def test_write_section_bootstrap_enables_legacy_refresh(self) -> None:
        args = argparse.Namespace(
            section="1",
            phase="open",
            read_judgment="已完整实读。",
            json=True,
        )
        with patch.object(TOOLBOX, "command_prepare_draft", return_value=0), patch.object(
            TOOLBOX,
            "command_init_first_draft",
            return_value=2,
        ) as initialize:
            result = TOOLBOX.command_write_section(self.paths, args)

        self.assertEqual(2, result)
        self.assertTrue(initialize.call_args.args[1].auto_refresh_legacy_bindings)
        self.assertFalse(initialize.call_args.args[1].use_git_ledger_fallback)

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
        with patch.object(
            TOOLBOX,
            "validate_outline_semantic_task",
            return_value=[],
        ), patch.object(TOOLBOX.subprocess, "run", return_value=completed) as run, patch.object(
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

    def test_compile_outline_stops_before_node_when_outline_semantic_task_is_pending(self) -> None:
        self.paths["model_semantic_source"].write_text("{}\n", encoding="utf-8")
        args = argparse.Namespace(
            json=True,
            legacy_data_module=None,
            from_existing_receipts=False,
        )
        with patch.object(
            TOOLBOX,
            "validate_outline_semantic_task",
            return_value=["outline_semantic_task.status 必须为 completed"],
        ), patch.object(TOOLBOX.subprocess, "run") as run:
            result = TOOLBOX.command_compile_outline(self.paths, args)

        self.assertEqual(2, result)
        run.assert_not_called()

    def test_outline_rebuilder_parses_chinese_section_headers(self) -> None:
        rebuilder = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "rebuild_outline_and_capacity_receipts.mjs"
        )
        program = (
            f'import {{ parseSectionBlocks }} from "{rebuilder.as_uri()}";\n'
            'const blocks = parseSectionBlocks("## 第1节 起事\\n甲\\n\\n## 第2节 反刀\\n乙\\n");\n'
            "console.log(JSON.stringify(Object.fromEntries(blocks)));\n"
        )

        completed = __import__("subprocess").run(
            ["node", "--input-type=module", "--eval", program],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual({"1": "甲", "2": "乙"}, json.loads(completed.stdout))

    def test_pending_outline_semantic_task_returns_only_top_level_blockers(self) -> None:
        _, semantic = self.build_completed_outline_semantic_task()
        task = semantic["outline_semantic_task"]
        task["status"] = "pending"
        task["reviewed_by_current_model"] = False
        task["manual_judgment"] = ""
        task["global_source_reads"][0]["read_status"] = "pending"
        task["section_tasks"]["1"]["completion_status"] = "pending"
        self.paths["model_semantic_source"].write_text(
            json.dumps(semantic, ensure_ascii=False),
            encoding="utf-8",
        )

        errors = TOOLBOX.validate_outline_semantic_task(self.paths)

        self.assertEqual(
            [
                "outline_semantic_task.status 必须为 completed",
                "outline_semantic_task 必须由当前执行模型完成人工复核",
                "outline_semantic_task.manual_judgment 不能为空",
            ],
            errors,
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

    def test_write_section_open_exports_raw_source_first_semantic_task(self) -> None:
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
        with patch.object(TOOLBOX, "sync_section_draft_tasks", return_value=[]), patch.object(
            TOOLBOX.FIRST_DRAFT,
            "validate_entry",
            return_value=[],
        ), patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "ensure_prewrite_review",
            return_value=0,
        ), patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "open_section",
            side_effect=open_section,
        ), patch.object(
            TOOLBOX,
            "export_section_raw_source_first_task",
            return_value={
                "path": str(self.paths["model_semantic_source"]),
                "semantic_key": "section_raw_source_first_tasks.1",
                "fingerprint": "fp-1",
            },
        ), patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "bind_raw_source_first_task",
            return_value=0,
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
            output.write_text(
                json.dumps({"version": "1.1", "batches": []}, ensure_ascii=False),
                encoding="utf-8",
            )
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
        self.assertTrue(self.paths["model_group_plan"].is_file())
        legacy_plan = json.loads(self.paths["model_group_plan"].read_text(encoding="utf-8"))
        self.assertEqual([], legacy_plan["groups"])
        completion = json.loads(self.paths["completion_state"].read_text(encoding="utf-8"))
        self.assertEqual("active", completion["status"])
        self.assertTrue(completion["checks"])

    def test_detect_manual_bypass_allows_setting_and_outline_after_valid_prewrite_gates(self) -> None:
        self.paths["setting"].write_text("设定内容\n", encoding="utf-8")
        self.paths["outline"].write_text("大纲内容\n", encoding="utf-8")

        errors = TOOLBOX.detect_manual_bypass(
            self.paths,
            {
                "setting_release": [],
                "setting_sequence": [],
                "outline_release": [],
                "outline": ["细纲表演验收缺失"],
                "draft_release": ["正文放行未通过"],
                "first_draft": ["首稿入口回执不存在"],
                "section_execution": ["逐节首写执行回执不存在"],
            },
        )

        self.assertEqual([], errors)

    def test_detect_manual_bypass_blocks_outline_when_prepare_outline_prerequisites_fail(self) -> None:
        self.paths["outline"].write_text("大纲内容\n", encoding="utf-8")

        errors = TOOLBOX.detect_manual_bypass(
            self.paths,
            {
                "setting_release": [],
                "setting_sequence": ["设定顺序契约未通过"],
                "outline_release": ["outline_release 未通过"],
                "outline": ["细纲表演验收缺失"],
                "draft_release": [],
                "first_draft": [],
                "section_execution": [],
            },
        )

        self.assertEqual(
            ["检测到手写细纲绕过写前门禁：小节大纲.md 已有实质内容，但 prepare-outline 前置门禁仍未通过"],
            errors,
        )

    def test_seed_pending_section_reviews_populates_all_sections(self) -> None:
        self.paths["section_execution_receipt"].write_text(
            json.dumps(
                {
                    "sections": [
                        {"section_id": "1", "status": "pending"},
                        {"section_id": "2", "status": "pending"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        errors = TOOLBOX.seed_pending_section_reviews(self.paths)

        self.assertEqual([], errors)
        semantic = json.loads(self.paths["model_semantic_source"].read_text(encoding="utf-8"))
        self.assertEqual({"1", "2"}, set(semantic["section_reviews"]))
        self.assertEqual(
            "pending",
            semantic["section_reviews"]["1"]["checks"]["style_granularity"]["status"],
        )

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

    def test_prepare_outline_initializes_outline_phase_scaffolds_when_missing(self) -> None:
        primary_root = self.root / "source-main"
        (primary_root / "写作资产").mkdir(parents=True)
        original = primary_root / "原文" / "source.txt"
        original.parent.mkdir()
        original.write_text("source", encoding="utf-8")
        (primary_root / "写作资产" / "桥段施工卡.md").write_text("# bridge", encoding="utf-8")
        (primary_root / "book.profile.json").write_text("{}", encoding="utf-8")
        (primary_root / "可直接仿写_导语拆解表.md").write_text("# opening", encoding="utf-8")
        self.paths["outline"].write_text(
            "## 第1节 开头\n- 钩子：抓人\n- 读者新获知：关系异常\n- 目标字数：1200\n",
            encoding="utf-8",
        )
        self.paths["cold_start_manifest"].write_text(
            json.dumps(
                {
                    "primary_source_root": str(primary_root),
                    "primary_original": str(original),
                    "auxiliary_originals": [],
                    "target_words": 10000,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        args = argparse.Namespace(json=True)
        outline_receipt = {"gate_status": "pending"}
        opening_receipt = {"gate_status": "pending"}
        capacity_receipt = {"gate_status": "pending"}
        with patch.object(TOOLBOX.SEQUENCE, "validate_setting", return_value=[]), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ), patch.object(
            TOOLBOX.OUTLINE,
            "create_receipt",
            return_value=outline_receipt,
        ) as create_outline, patch.object(
            TOOLBOX.OPENING,
            "create_receipt",
            return_value=opening_receipt,
        ) as create_opening, patch.object(
            TOOLBOX.DRAFT_CAPACITY,
            "init",
            return_value=capacity_receipt,
        ) as init_capacity:
            result = TOOLBOX.command_prepare_outline(self.paths, args)

        self.assertEqual(0, result)
        self.assertEqual(outline_receipt, json.loads(self.paths["outline_contract"].read_text(encoding="utf-8")))
        self.assertEqual(opening_receipt, json.loads(self.paths["opening_contract"].read_text(encoding="utf-8")))
        self.assertEqual(
            capacity_receipt,
            json.loads(self.paths["draft_capacity_contract"].read_text(encoding="utf-8")),
        )
        semantic = json.loads(self.paths["model_semantic_source"].read_text(encoding="utf-8"))
        self.assertEqual(self.project.name, semantic["project"])
        self.assertEqual("1", semantic["outline_compilation"]["plans"][0]["id"])
        self.assertEqual("BID-01", semantic["outline_compilation"]["plans"][0]["bridge"])
        self.assertTrue(semantic["outline_compilation"]["bridgeDefs"])
        self.assertIn("manual_judgment", semantic["outline_compilation"]["globalReview"])
        self.assertTrue(semantic["outline_compilation"]["factLedger"])
        task = semantic["outline_semantic_task"]
        self.assertEqual("pending", task["status"])
        self.assertFalse(task["reviewed_by_current_model"])
        self.assertEqual([str(original.resolve())], [item["path"] for item in task["global_source_reads"]])
        self.assertEqual({"1"}, set(task["section_tasks"]))
        self.assertEqual(
            [str(original.resolve())],
            [item["path"] for item in task["section_tasks"]["1"]["source_slice_reviews"]],
        )
        style_reviews = task["section_tasks"]["1"]["source_slice_reviews"][0]["style_dimension_reviews"]
        self.assertEqual(set(TOOLBOX.OUTLINE_STYLE_DIMENSIONS), set(style_reviews))
        self.assertTrue(
            all(
                review == {
                    "source_observation": "",
                    "source_evidence": [],
                    "target_transfer": "",
                    "status": "pending",
                }
                for review in style_reviews.values()
            )
        )
        create_outline.assert_called_once_with(
            self.project.name,
            self.paths["outline"],
            [original.resolve()],
            source_mode="full_bridge",
        )
        create_opening.assert_called_once_with(
            self.project.name,
            (primary_root / "可直接仿写_导语拆解表.md").resolve(),
            self.paths["outline"],
            "outline",
        )
        init_capacity.assert_called_once_with(self.project.name, self.paths["outline"], 10000)

    def test_prepare_outline_keeps_existing_outline_phase_scaffolds(self) -> None:
        primary_root = self.root / "source-main"
        (primary_root / "写作资产").mkdir(parents=True)
        original = primary_root / "原文" / "source.txt"
        original.parent.mkdir()
        original.write_text("source", encoding="utf-8")
        (primary_root / "写作资产" / "桥段施工卡.md").write_text("# bridge", encoding="utf-8")
        (primary_root / "book.profile.json").write_text("{}", encoding="utf-8")
        (primary_root / "可直接仿写_导语拆解表.md").write_text("# opening", encoding="utf-8")
        self.paths["outline"].write_text(
            "## 第1节 已有语义\n"
            "这一节只同步机械上下文。\n\n"
            "节末钩子：已有人工判断不能被覆盖。\n\n"
            "来源绑定：\n"
            "- 主体：`SF-01`\n"
            "- 必保颗粒：动作先行、判断慢半拍\n",
            encoding="utf-8",
        )
        self.paths["cold_start_manifest"].write_text(
            json.dumps(
                {
                    "primary_source_root": str(primary_root),
                    "primary_original": str(original),
                    "auxiliary_originals": [],
                    "target_words": 9800,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        semantic_payload = {
            "project": "keep",
            "outline_compilation": {
                "plans": [{"id": "1", "semanticDecision": "keep"}],
                "bridgeDefs": [{"id": "BID-01"}],
                "globalReview": {"manual_judgment": "keep"},
                "factLedger": [{"fact_id": "F-01"}],
            },
        }
        self.paths["model_semantic_source"].write_text(
            json.dumps(semantic_payload, ensure_ascii=False),
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text('{"keep":"outline"}\n', encoding="utf-8")
        self.paths["opening_contract"].write_text('{"keep":"opening"}\n', encoding="utf-8")
        self.paths["draft_capacity_contract"].write_text('{"keep":"capacity"}\n', encoding="utf-8")

        args = argparse.Namespace(json=True)
        with patch.object(TOOLBOX.SEQUENCE, "validate_setting", return_value=[]), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ), patch.object(TOOLBOX.OUTLINE, "create_receipt") as create_outline, patch.object(
            TOOLBOX.OPENING,
            "create_receipt",
        ) as create_opening, patch.object(TOOLBOX.DRAFT_CAPACITY, "init") as init_capacity:
            result = TOOLBOX.command_prepare_outline(self.paths, args)

        self.assertEqual(0, result)
        semantic = json.loads(self.paths["model_semantic_source"].read_text(encoding="utf-8"))
        self.assertEqual("keep", semantic["outline_compilation"]["plans"][0]["semanticDecision"])
        self.assertEqual("keep", semantic["outline_compilation"]["globalReview"]["manual_judgment"])
        self.assertEqual("已有语义", semantic["outline_compilation"]["plans"][0]["title"])
        self.assertEqual(
            ["动作先行", "判断慢半拍"],
            semantic["outline_compilation"]["plans"][0]["requiredGranularity"],
        )
        self.assertEqual("pending", semantic["outline_semantic_task"]["status"])
        self.assertEqual({"keep": "outline"}, json.loads(self.paths["outline_contract"].read_text(encoding="utf-8")))
        self.assertEqual({"keep": "opening"}, json.loads(self.paths["opening_contract"].read_text(encoding="utf-8")))
        self.assertEqual(
            {"keep": "capacity"},
            json.loads(self.paths["draft_capacity_contract"].read_text(encoding="utf-8")),
        )
        create_outline.assert_not_called()
        create_opening.assert_not_called()
        init_capacity.assert_not_called()

    def test_prepare_outline_upgrades_thin_semantic_source_template(self) -> None:
        primary_root = self.root / "source-main"
        (primary_root / "写作资产").mkdir(parents=True)
        original = primary_root / "原文" / "source.txt"
        original.parent.mkdir()
        original.write_text("source", encoding="utf-8")
        (primary_root / "写作资产" / "桥段施工卡.md").write_text("# bridge", encoding="utf-8")
        (primary_root / "book.profile.json").write_text("{}", encoding="utf-8")
        (primary_root / "可直接仿写_导语拆解表.md").write_text("# opening", encoding="utf-8")
        self.paths["outline"].write_text(
            "## 第1节 开头\n"
            "这一节先把公开失位打穿。\n\n"
            "节末钩子：他当众喊她妻子，却是为了替别人求情。\n\n"
            "来源绑定：\n"
            "- 主体：`SF-12`\n"
            "- 必保颗粒：正式场先控秩序、抓制服求情、女主改用正式称呼\n"
            "- 目标字数：1200\n\n"
            "## 第2节 升级\n- 钩子：逼近\n- 读者新获知：旧账翻出\n- 目标字数：1300\n",
            encoding="utf-8",
        )
        self.paths["cold_start_manifest"].write_text(
            json.dumps(
                {
                    "primary_source_root": str(primary_root),
                    "primary_original": str(original),
                    "auxiliary_originals": [],
                    "target_words": 10000,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.paths["model_semantic_source"].write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "project": self.project.name,
                    "outline_compilation": {
                        "plans": [],
                        "bridgeDefs": [],
                        "globalReview": {},
                        "factLedger": [],
                        "projectName": self.project.name,
                        "targetWords": 10000,
                        "sourceTextRelative": "",
                        "bridgeCatalogRelative": "",
                        "profileRelative": "",
                    },
                    "section_raw_source_first_tasks": {},
                    "section_reviews": {"1": {"gate_status": "pending"}},
                    "section_prewrite_reviews": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        args = argparse.Namespace(json=True)
        with patch.object(TOOLBOX.SEQUENCE, "validate_setting", return_value=[]), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ), patch.object(TOOLBOX.OUTLINE, "create_receipt", return_value={"gate_status": "pending"}), patch.object(
            TOOLBOX.OPENING,
            "create_receipt",
            return_value={"gate_status": "pending"},
        ), patch.object(TOOLBOX.DRAFT_CAPACITY, "init", return_value={"gate_status": "pending"}):
            result = TOOLBOX.command_prepare_outline(self.paths, args)

        self.assertEqual(0, result)
        semantic = json.loads(self.paths["model_semantic_source"].read_text(encoding="utf-8"))
        self.assertEqual({"gate_status": "pending"}, semantic["section_reviews"]["1"])
        self.assertEqual(["1", "2"], [item["id"] for item in semantic["outline_compilation"]["plans"]])
        first_plan = semantic["outline_compilation"]["plans"][0]
        self.assertEqual("开头", first_plan["title"])
        self.assertEqual("他当众喊她妻子，却是为了替别人求情。", first_plan["hook"])
        self.assertEqual("", first_plan["newInfo"])
        self.assertIn("这一节先把公开失位打穿。", first_plan["outlineContext"])
        self.assertEqual(
            [
                "主体：`SF-12`",
                "必保颗粒：正式场先控秩序、抓制服求情、女主改用正式称呼",
                "目标字数：1200",
            ],
            first_plan["sourceBindings"],
        )
        self.assertEqual(
            ["正式场先控秩序", "抓制服求情", "女主改用正式称呼"],
            first_plan["requiredGranularity"],
        )
        self.assertEqual([str(original.resolve())], first_plan["requiredSourceOriginals"])
        self.assertEqual(1200, first_plan["plannedWords"])
        self.assertTrue(semantic["outline_compilation"]["bridgeDefs"])
        self.assertTrue(semantic["outline_compilation"]["factLedger"])
        self.assertEqual("", semantic["outline_compilation"]["globalReview"]["manual_judgment"])
        self.assertEqual({"1", "2"}, set(semantic["outline_semantic_task"]["section_tasks"]))

    def build_completed_outline_semantic_task(self) -> tuple[Path, dict]:
        primary_root = self.root / "source-main"
        (primary_root / "写作资产").mkdir(parents=True)
        original = primary_root / "原文" / "source.txt"
        original.parent.mkdir()
        original.write_text(
            "第一句原文动作。\n"
            "第二句原文错答。\n"
            "第三句原文感知。\n"
            "第四句原文余痛。\n",
            encoding="utf-8",
        )
        (primary_root / "写作资产" / "桥段施工卡.md").write_text("# bridge", encoding="utf-8")
        (primary_root / "book.profile.json").write_text("{}", encoding="utf-8")
        self.paths["outline"].write_text(
            "## 第1节 开头\n"
            "这一节迁移原文的情绪和文风颗粒。\n\n"
            "- 情绪：被现场动作刺中的错愕与强压。\n"
            "- 读者新获知：关系先在动作里失位。\n"
            "- 钩子：下一场会继续核验。\n"
            "- 伏笔/物件：被夺走的记录。\n"
            "- 动静：动作先快，判断后到。\n"
            "- 对话密度：短问短答，避免解释。\n"
            "- 目标字数：1200\n\n"
            "来源绑定：\n"
            "- 主体：`SF-01`\n"
            "- 必保颗粒：动作先行、错答、余痛\n",
            encoding="utf-8",
        )
        self.paths["cold_start_manifest"].write_text(
            json.dumps(
                {
                    "primary_source_root": str(primary_root),
                    "primary_original": str(original),
                    "auxiliary_originals": [],
                    "target_words": 1200,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        semantic = {
            "version": "1.0",
            "project": self.project.name,
            "outline_compilation": TOOLBOX.build_outline_compilation_scaffold(
                self.paths,
                originals=[original.resolve()],
                primary_root=primary_root.resolve(),
                target_words=1200,
            ),
            "section_reviews": {},
        }
        task = TOOLBOX.build_outline_semantic_task(
            self.paths,
            semantic,
            [original.resolve()],
        )
        task["status"] = "completed"
        task["reviewed_by_current_model"] = True
        task["manual_judgment"] = "已完整实读原文并逐节完成颗粒迁移。"
        task["global_source_reads"][0].update(
            {
                "read_status": "completed",
                "evidence": ["第一句原文动作。", "第四句原文余痛。"],
                "manual_judgment": "已完整读取四行原文。",
            }
        )
        section_task = task["section_tasks"]["1"]
        section_task["completion_status"] = "completed"
        section_task["manual_judgment"] = "本节按原文的动作、错答和余痛顺序迁移。"
        slice_review = section_task["source_slice_reviews"][0]
        slice_review.update(
            {
                "source_range": "L1-L4",
                "source_evidence": ["第一句原文动作。", "第二句原文错答。"],
                "manual_judgment": "该切片覆盖本节需要的完整表演和文风颗粒。",
                "status": "completed",
            }
        )
        for dimension, review in slice_review["style_dimension_reviews"].items():
            review.update(
                {
                    "source_observation": f"{dimension} 的原文表现已逐句确认。",
                    "source_evidence": ["第一句原文动作。"],
                    "target_transfer": f"本节迁移 {dimension} 的功能和节奏，不复制原句。",
                    "status": "completed",
                }
            )
        semantic["outline_semantic_task"] = task
        return original, semantic

    def test_validate_outline_semantic_task_requires_evidence_inside_exact_slice(self) -> None:
        _, semantic = self.build_completed_outline_semantic_task()
        review = semantic["outline_semantic_task"]["section_tasks"]["1"]["source_slice_reviews"][0]
        review["source_range"] = "L1-L1"
        self.paths["model_semantic_source"].write_text(
            json.dumps(semantic, ensure_ascii=False),
            encoding="utf-8",
        )

        errors = TOOLBOX.validate_outline_semantic_task(self.paths)

        self.assertTrue(any("切片证据不在精确行段内" in error for error in errors))

    def test_validate_outline_semantic_task_requires_outline_baseline_fields(self) -> None:
        _, semantic = self.build_completed_outline_semantic_task()
        self.paths["outline"].write_text(
            "## 第1节 开头\n\n"
            "这一节迁移原文的情绪和文风颗粒。\n\n"
            "来源绑定：\n"
            "- 主体：`SF-01`\n",
            encoding="utf-8",
        )
        self.paths["model_semantic_source"].write_text(
            json.dumps(semantic, ensure_ascii=False),
            encoding="utf-8",
        )

        errors = TOOLBOX.validate_outline_semantic_task(self.paths)

        self.assertTrue(any("缺少细纲基准字段" in error for error in errors))

    def test_validate_outline_semantic_task_rejects_boolean_only_style_review(self) -> None:
        _, semantic = self.build_completed_outline_semantic_task()
        review = semantic["outline_semantic_task"]["section_tasks"]["1"]["source_slice_reviews"][0]
        review.pop("style_dimension_reviews")
        review["style_dimensions_reviewed"] = {
            dimension: True
            for dimension in TOOLBOX.OUTLINE_STYLE_DIMENSIONS
        }
        self.paths["model_semantic_source"].write_text(
            json.dumps(semantic, ensure_ascii=False),
            encoding="utf-8",
        )

        errors = TOOLBOX.validate_outline_semantic_task(self.paths)

        self.assertTrue(any("缺少六项文风颗粒逐项复核" in error for error in errors))

    def test_validate_outline_semantic_task_accepts_complete_source_granularity_task(self) -> None:
        _, semantic = self.build_completed_outline_semantic_task()
        self.paths["model_semantic_source"].write_text(
            json.dumps(semantic, ensure_ascii=False),
            encoding="utf-8",
        )

        errors = TOOLBOX.validate_outline_semantic_task(self.paths)

        self.assertEqual([], errors)

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
            json=True,
            auto_refresh_legacy_bindings=False,
            use_git_ledger_fallback=False,
        )
        with patch.object(TOOLBOX.FIRST_DRAFT, "init_entry", return_value=0) as init_entry, patch.object(
            TOOLBOX,
            "sync_section_draft_tasks",
            return_value=[],
        ) as sync_tasks, patch.object(
            TOOLBOX,
            "seed_pending_section_reviews",
            return_value=[],
        ) as seed_reviews, patch.object(
            TOOLBOX,
            "ensure_completion_state",
            return_value=[],
        ) as ensure_state:
            result = TOOLBOX.command_init_first_draft(self.paths, args)

        self.assertEqual(0, result)
        self.assertEqual(str(self.project), init_entry.call_args.kwargs["project"])
        self.assertIsInstance(init_entry.call_args.kwargs["project"], str)
        sync_tasks.assert_called_once_with(self.paths)
        seed_reviews.assert_called_once_with(self.paths)
        ensure_state.assert_called_once_with(self.paths)

    def test_cold_start_generates_project_wrappers(self) -> None:
        source = self.root / "source"
        aux_sources = [self.root / f"aux-{index}" for index in range(1, 4)]
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
        aux_profiles: list[Path] = []
        for aux_source in aux_sources:
            (aux_source / "写作资产").mkdir(parents=True)
            (aux_source / "原文").mkdir()
            aux_profile = aux_source / "book.profile.json"
            for path, content in (
                (aux_profile, "{}"),
                (aux_source / "写作资产" / "仿写无损编译包.json", "{}"),
                (aux_source / "写作资产" / "桥段施工卡.md", "# bridge"),
                (aux_source / "可直接仿写_导语拆解表.md", "# opening"),
                (aux_source / "原文" / f"{aux_source.name}.txt", "source"),
            ):
                path.write_text(content, encoding="utf-8")
            aux_profiles.append(aux_profile)

        with patch.object(COLD_START.WRITING_RULE, "create_receipt", return_value=({}, [])), patch.object(
            COLD_START.SOURCE_READ,
            "create_receipt",
            return_value=({}, []),
        ), patch.object(
            COLD_START.PROFILE_GENERATOR,
            "merge_profiles",
            return_value={"meta": {"mode": "merged_profiles", "sources": ["a", "b", "c", "d"]}},
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
                auxiliary_source_profiles=aux_profiles,
                target_words=10000,
                force=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual("generated:1", result["actions"]["project_wrappers"])
        self.assertTrue((self.project / "写作资产" / "模型语义输入.json").is_file())
        self.assertTrue(self.paths["profile"].is_file())
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
        aux_sources = [self.root / f"legacy-aux-{index}" for index in range(1, 4)]
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
        aux_profiles: list[Path] = []
        for aux_source in aux_sources:
            (aux_source / "写作资产").mkdir(parents=True)
            (aux_source / "原文").mkdir()
            aux_profile = aux_source / "book.profile.json"
            for path, content in (
                (aux_profile, "{}"),
                (aux_source / "写作资产" / "仿写无损编译包.json", "{}"),
                (aux_source / "写作资产" / "桥段施工卡.md", "# bridge"),
                (aux_source / "可直接仿写_导语拆解表.md", "# opening"),
                (aux_source / "原文" / f"{aux_source.name}.txt", "source"),
            ):
                path.write_text(content, encoding="utf-8")
            aux_profiles.append(aux_profile)

        with patch.object(COLD_START.WRITING_RULE, "create_receipt", return_value=({}, [])), patch.object(
            COLD_START.SOURCE_READ,
            "create_receipt",
            return_value=({}, []),
        ), patch.object(
            COLD_START.PROFILE_GENERATOR,
            "merge_profiles",
            return_value={"meta": {"mode": "merged_profiles", "sources": ["a", "b", "c", "d"]}},
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
                auxiliary_source_profiles=aux_profiles,
                target_words=10000,
                force=False,
                generate_legacy_scaffold=True,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(
            (self.project / "写作资产" / "重建细纲与容量回执.scaffold.mjs").is_file()
        )

    def test_repair_source_stack_drops_invalid_existing_auxiliary_sources(self) -> None:
        primary = self.root / "primary" / "book.profile.json"
        keep_existing = self.root / "aux-keep" / "book.profile.json"
        drop_existing = self.root / "aux-drop" / "book.profile.json"
        appended_1 = self.root / "aux-new-1" / "book.profile.json"
        appended_2 = self.root / "aux-new-2" / "book.profile.json"
        appended_3 = self.root / "aux-new-3" / "book.profile.json"
        for path in (primary, keep_existing, drop_existing, appended_1, appended_2, appended_3):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")

        args = argparse.Namespace(
            aux_source_profile=[str(appended_1), str(appended_2), str(appended_3)],
            json=True,
        )
        self.paths["source_receipt"].write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "name": "primary",
                            "role": "main",
                            "root": str(primary.parent),
                            "selected_subflow_ids": ["SF-01"],
                        },
                        {
                            "name": "aux-keep",
                            "role": "auxiliary",
                            "root": str(keep_existing.parent),
                            "selected_subflow_ids": ["SF-04"],
                        },
                        {
                            "name": "aux-drop",
                            "role": "auxiliary",
                            "root": str(drop_existing.parent),
                            "selected_subflow_ids": ["SF-09"],
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        def fake_validate(primary_profile: Path, _aux_profiles: list[Path]):
            if primary_profile == drop_existing:
                return (
                    [
                        {
                            "role": "main",
                            "profile": str(drop_existing),
                            "root": str(drop_existing.parent),
                            "ok": False,
                            "errors": ["仿写编译包版本过期"],
                        }
                    ],
                    ["aux-drop: 仿写编译包版本过期"],
                )
            return (
                [
                    {
                        "role": "main",
                        "profile": str(primary_profile),
                        "root": str(primary_profile.parent),
                        "ok": True,
                        "errors": [],
                    }
                ],
                [],
            )

        captured: dict[str, dict] = {}

        def fake_write_json(path: Path, data: dict) -> None:
            captured[str(path)] = data

        with patch.object(
            TOOLBOX,
            "resolve_source_stack",
            return_value=(primary, [keep_existing, drop_existing], 10000),
        ), patch.object(
            TOOLBOX,
            "validate_source_profiles_for_direct_imitation",
            side_effect=fake_validate,
        ), patch.object(
            TOOLBOX.COLD_START,
            "validate_source_stack",
        ) as validate_stack, patch.object(
            TOOLBOX.COLD_START,
            "infer_source_root",
            side_effect=lambda path: path.parent,
        ), patch.object(
            TOOLBOX.COLD_START,
            "source_original_path",
            side_effect=lambda root: root / "原文.txt",
        ), patch.object(
            TOOLBOX.COLD_START,
            "write_checklist",
        ), patch.object(
            TOOLBOX.PROFILE_GENERATOR,
            "merge_profiles",
            return_value={"meta": {"sources": []}},
        ) as merge_profiles, patch.object(
            TOOLBOX.SOURCE_READ,
            "create_receipt",
            return_value=(
                {
                    "gate_status": "pending",
                    "confirmed_before_outline": False,
                    "confirmed_before_draft": False,
                    "sources": [],
                },
                [],
            ),
        ) as create_receipt, patch.object(
            TOOLBOX,
            "archive_source_stack_receipts",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "write_json",
            side_effect=fake_write_json,
        ):
            result = TOOLBOX.command_repair_source_stack(self.paths, args)

        self.assertEqual(0, result)
        expected_aux = [keep_existing, appended_1, appended_2, appended_3]
        validate_stack.assert_called_once_with(primary, expected_aux)
        merge_profiles.assert_called_once_with(
            [primary, *expected_aux],
            self.paths["project"].name,
        )
        create_receipt.assert_called_once_with(
            self.paths["project"].name,
            [
                primary.parent,
                keep_existing.parent,
                appended_1.parent,
                appended_2.parent,
                appended_3.parent,
            ],
            "compiled",
            "direct_imitation",
            {"aux-keep": {"SF-04"}},
        )
        manifest = captured[str(self.paths["cold_start_manifest"])]
        self.assertEqual(
            [str(path) for path in expected_aux],
            manifest["auxiliary_source_profiles"],
        )
        rebuilt_receipt = captured[str(self.paths["source_receipt"])]
        self.assertEqual("pending", rebuilt_receipt["gate_status"])
        self.assertFalse(rebuilt_receipt["confirmed_before_outline"])
        self.assertFalse(rebuilt_receipt["confirmed_before_draft"])

    def test_archive_source_derived_writing_artifacts_clears_stage_outputs(self) -> None:
        for key in ("setting", "outline", "draft"):
            self.paths[key].write_text(f"{key}\n", encoding="utf-8")

        actions = TOOLBOX.archive_source_derived_writing_artifacts(
            self.paths,
            "source stack changed",
        )

        for key in ("setting", "outline", "draft"):
            self.assertFalse(self.paths[key].exists())
        archive_dirs = list(self.paths["asset"].glob("旧稿归档-*"))
        self.assertEqual(1, len(archive_dirs))
        self.assertEqual(
            {"设定.md", "小节大纲.md", "正文.md"},
            {path.name for path in archive_dirs[0].iterdir()},
        )
        self.assertTrue(any("invalidate source-derived writing artifacts" in item for item in actions))


if __name__ == "__main__":
    unittest.main()
