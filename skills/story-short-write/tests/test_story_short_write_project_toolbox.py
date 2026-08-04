from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
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


class StoryShortWriteProjectToolboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "book"
        (self.project / "写作资产").mkdir(parents=True)
        self.paths = TOOLBOX.project_paths(self.project)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_parser_exposes_fixed_workflow_commands(self) -> None:
        parser = TOOLBOX.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        for command in (
            "init-book",
            "allocate-project",
            "candidate-subflows",
            "workspace-rules",
            "export-rule-review",
            "rule-review-next",
            "apply-rule-review-item",
            "apply-rule-review",
            "export-source-review",
            "source-review-next",
            "apply-source-review-item",
            "apply-source-review",
            "validate-prewrite-reads",
            "prepare-setting",
            "setting-context",
            "stage-reference",
            "prepare-draft-gates",
            "opening-precheck",
            "opening-apply",
            "sequence-precheck",
            "sequence-apply",
            "draft-capacity-precheck",
            "draft-capacity-apply",
            "outline-precheck",
            "outline-validate",
            "outline-repair-next",
            "outline-repair-apply",
            "sync-sources",
            "preflight-book",
            "start-draft",
            "show-section",
            "open-section",
            "reopen-section",
            "advance-section",
            "finalize-basic-review",
        ):
            self.assertIn(command, subparsers.choices)

    def test_sync_sources_delegates_to_rule_ledger_gate(self) -> None:
        self.paths["ledger"].write_text("{}\n", encoding="utf-8")
        output = StringIO()

        with patch.object(
            TOOLBOX.RULE_LEDGER,
            "sync_sources",
            return_value=([], {"preserved": 8, "reset": 1}),
        ), redirect_stdout(output):
            result = TOOLBOX.command_sync_sources(self.paths, argparse.Namespace())

        text = output.getvalue()
        self.assertEqual(0, result)
        self.assertIn("project_toolbox: sync-sources passed", text)
        self.assertIn("preserved: 8", text)
        self.assertIn("reset: 1", text)

    def test_sync_sources_refreshes_builtin_rule_receipt_for_existing_project(self) -> None:
        self.paths["ledger"].write_text("{}\n", encoding="utf-8")
        self.paths["writing_receipt"].write_text('{"review_mode":"legacy"}\n', encoding="utf-8")
        candidate = {"files": [], "review_mode": "pending"}

        def apply_builtin(receipt: dict[str, object]) -> list[str]:
            receipt["review_mode"] = "builtin_sha_bound"
            return []

        with patch.object(
            TOOLBOX.WRITING_RULE,
            "create_receipt",
            return_value=(candidate, []),
        ), patch.object(
            TOOLBOX.WRITING_RULE,
            "apply_builtin_rule_reviews",
            side_effect=apply_builtin,
        ), patch.object(
            TOOLBOX.RULE_LEDGER,
            "sync_sources",
            return_value=([], {"preserved": 1, "reset": 0}),
        ):
            result = TOOLBOX.command_sync_sources(self.paths, argparse.Namespace())

        self.assertEqual(0, result)
        refreshed = TOOLBOX.read_json(self.paths["writing_receipt"])
        self.assertEqual("builtin_sha_bound", refreshed["review_mode"])

    def test_outline_progress_requires_title_on_separate_line(self) -> None:
        progress = TOOLBOX.analyze_outline_progress(
            "## 第1节：执法现场\n\n### 标题：执法现场\n\n## 全书事实状态链\n\n## 相邻节交接链\n"
        )

        self.assertEqual([], progress["section_ids"])
        self.assertEqual(["## 第1节：执法现场"], progress["malformed_section_headings"])
        self.assertTrue(any("一级标题必须独占一行" in item for item in progress["missing_items"]))

    def test_outline_progress_accepts_exact_section_heading(self) -> None:
        progress = TOOLBOX.analyze_outline_progress(
            "## 第1节\n\n### 标题：执法现场\n\n## 第9节\n\n## 全书事实状态链\n\n## 相邻节交接链\n"
        )

        self.assertEqual(["1", "9"], progress["section_ids"])
        self.assertEqual([], progress["malformed_section_headings"])

    def test_allocate_project_reserves_unique_directory_and_prints_init_command(
        self,
    ) -> None:
        root = Path(self.temp.name) / "workspace"
        root.mkdir()
        (root / "新书").mkdir()
        args = argparse.Namespace(
            root=str(root),
            name="新书",
            source_dir=[str(self.project / "主体")],
            select_subflow=[],
        )
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_allocate_project(args)

        allocated = root / "新书-2"
        self.assertEqual(0, result)
        self.assertTrue((allocated / TOOLBOX.PROJECT_RESERVATION_FILE).is_file())
        self.assertIn(f"project_path: {allocated}", output.getvalue())
        self.assertIn("--project", output.getvalue())
        self.assertIn("init-book", output.getvalue())
        self.assertNotIn("ls ", output.getvalue())

    def test_init_book_does_not_write_any_output_when_source_gate_blocks(self) -> None:
        args = argparse.Namespace(
            source_dir=[str(self.project / "source")],
            select_subflow=[],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
            force=False,
        )
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "create_receipt",
            return_value=({"kind": "writing"}, []),
        ), patch.object(
            TOOLBOX.WRITING_RULE,
            "apply_builtin_rule_reviews",
            return_value=[],
        ), patch.object(
            TOOLBOX.SOURCE_READ,
            "create_receipt",
            return_value=({}, ["来源包过期"]),
        ), patch.object(TOOLBOX.PROFILE, "merge_profiles") as merge_profiles:
            result = TOOLBOX.command_init_book(self.paths, args)
        self.assertEqual(2, result)
        merge_profiles.assert_not_called()
        self.assertFalse(self.paths["writing_receipt"].exists())
        self.assertFalse(self.paths["source_receipt"].exists())
        self.assertFalse(self.paths["profile"].exists())

    def test_init_book_writes_all_outputs_only_after_validation_passes(self) -> None:
        source = self.project / "source"
        source.mkdir()
        args = argparse.Namespace(
            source_dir=[str(source)],
            select_subflow=[],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
            force=False,
        )
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "create_receipt",
            return_value=({"kind": "writing"}, []),
        ), patch.object(
            TOOLBOX.WRITING_RULE,
            "apply_builtin_rule_reviews",
            return_value=[],
        ), patch.object(
            TOOLBOX.SOURCE_READ,
            "create_receipt",
            return_value=({"kind": "source"}, []),
        ), patch.object(
            TOOLBOX.PROFILE,
            "merge_profiles",
            return_value={"kind": "profile"},
        ), patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["auto-finalize-direct-imitation-source-stage"]),
        ):
            result = TOOLBOX.command_init_book(self.paths, args)
        self.assertEqual(0, result)
        self.assertEqual("writing", TOOLBOX.read_json(self.paths["writing_receipt"])["kind"])
        self.assertEqual("source", TOOLBOX.read_json(self.paths["source_receipt"])["kind"])
        self.assertEqual("profile", TOOLBOX.read_json(self.paths["profile"])["kind"])

    def test_init_book_dedupes_duplicate_source_dirs_before_receipt_and_profile_merge(self) -> None:
        source = self.project / "source"
        source.mkdir()
        args = argparse.Namespace(
            source_dir=[str(source), str(source.resolve()), str(source)],
            select_subflow=[],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
            force=False,
        )
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "create_receipt",
            return_value=({"kind": "writing"}, []),
        ), patch.object(
            TOOLBOX.WRITING_RULE,
            "apply_builtin_rule_reviews",
            return_value=[],
        ), patch.object(
            TOOLBOX.SOURCE_READ,
            "create_receipt",
            return_value=({"kind": "source"}, []),
        ) as create_source_receipt, patch.object(
            TOOLBOX.PROFILE,
            "merge_profiles",
            return_value={"kind": "profile"},
        ) as merge_profiles, patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], []),
        ):
            result = TOOLBOX.command_init_book(self.paths, args)
        self.assertEqual(0, result)
        self.assertEqual([source.resolve()], create_source_receipt.call_args.args[1])
        self.assertEqual(
            [source.resolve() / "book.profile.json"],
            merge_profiles.call_args.args[0],
        )

    def test_merge_profiles_dedupes_duplicate_profile_paths(self) -> None:
        source = self.project / "source"
        source.mkdir()
        profile_path = source / "book.profile.json"
        profile_path.write_text(
            json.dumps(
                {
                    "meta": {"name": "来源A"},
                    "precheck_overrides": {
                        "pretty_detail": {
                            "fact_anchor_patterns": ["花束"],
                            "action_anchor_patterns": ["扔花"],
                        }
                    },
                    "sample_grading": {
                        "level": "B类骨架样本",
                        "dna_usable": "部分可",
                        "structure_grade": "A",
                        "performance_grade": "B",
                        "sentence_grade": "B",
                        "terminal_consequence_grade": "B",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        merged = TOOLBOX.PROFILE.merge_profiles(
            [profile_path, profile_path.resolve(), profile_path],
            "测试项目",
        )

        self.assertEqual(1, merged["meta"]["source_count"])
        self.assertEqual([str(profile_path.resolve())], merged["meta"]["sources"])
        self.assertEqual(
            1,
            len(merged.get("sample_source_buckets", {}).get("entries", [])),
        )

    def test_print_common_repair_packet_header_prefers_summary_object(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            TOOLBOX.print_common_repair_packet_header(
                packet_path=self.paths["opening_repair_packet"],
                result_path=self.paths["opening_repair_item_output"],
                packet={
                    "packet_sha256": "abc",
                    "summary": {
                        "primary_focus_summary": "summary 摘要",
                        "primary_error_preview": "summary 错误",
                        "focus_summary_line": "summary focus",
                        "guidance_summary_line": "summary guidance",
                    },
                },
            )

        text = output.getvalue()
        self.assertIn("primary_focus_summary: summary 摘要", text)
        self.assertIn("primary_error_preview: summary 错误", text)

    def test_packet_summary_map_requires_complete_summary(self) -> None:
        with self.assertRaisesRegex(ValueError, "summary 字段不完整"):
            TOOLBOX.packet_summary_map(
                {
                    "summary": {
                        "primary_focus_summary": "summary 摘要",
                        "primary_error_preview": "",
                        "focus_summary_line": "summary focus",
                        "guidance_summary_line": "",
                    },
                }
            )

    def test_packet_summary_map_rejects_missing_summary(self) -> None:
        with self.assertRaisesRegex(ValueError, "缺少 summary"):
            TOOLBOX.packet_summary_map({"packet_sha256": "abc"})

    def test_normalize_repair_packet_summary_requires_summary_object(self) -> None:
        with self.assertRaisesRegex(ValueError, "缺少 summary"):
            TOOLBOX.normalize_repair_packet_summary(
                {
                    "packet_sha256": "abc",
                    "primary_focus_summary": "顶层摘要",
                    "primary_error_preview": "顶层错误",
                    "focus_summary_line": "顶层 focus",
                    "guidance_summary_line": "顶层 guidance",
                }
            )

    def test_packet_summary_map_reads_summary_only(self) -> None:
        summary = TOOLBOX.packet_summary_map(
            {
                "summary": {
                    "primary_focus_summary": "summary 摘要",
                    "primary_error_preview": "summary 错误",
                    "focus_summary_line": "summary focus",
                    "guidance_summary_line": "summary guidance",
                },
            }
        )

        self.assertEqual("summary 摘要", summary["primary_focus_summary"])
        self.assertEqual("summary 错误", summary["primary_error_preview"])
        self.assertEqual("summary focus", summary["focus_summary_line"])
        self.assertEqual("summary guidance", summary["guidance_summary_line"])

    def test_merge_outline_repair_item_output_prefers_fresh_first_draft_source_bindings(self) -> None:
        template = [
            {
                "section_id": "1",
                "source_emotion_parity": {
                    "source_excerpt": "新的主体切片",
                    "source_emotion_sequence": [{"role": "起拍", "evidence": "新的证据"}],
                },
                "first_draft_generation_contract": {
                    "source_slice_bindings": [{"subflow_id": "SF-01", "source_range": "L1-L2"}],
                    "source_performance_excerpt": "新的精确摘录",
                    "source_performance_evidence": ["新的证据A", "新的证据B"],
                    "emotion_process": {
                        "memory_association_or_attention_drift": "新的逐节漂移",
                        "contradictory_impulse": "保留旧值也没关系",
                    },
                },
            }
        ]
        existing = [
            {
                "section_id": "1",
                "source_emotion_parity": {
                    "source_excerpt": "旧污染摘录",
                    "source_emotion_sequence": [{"role": "起拍", "evidence": "旧污染证据"}],
                },
                "first_draft_generation_contract": {
                    "source_slice_bindings": [{"subflow_id": "SF-99", "source_range": "L9-L9"}],
                    "source_performance_excerpt": "旧污染摘录",
                    "source_performance_evidence": ["旧污染证据"],
                    "emotion_process": {
                        "memory_association_or_attention_drift": "旧污染漂移",
                        "contradictory_impulse": "旧值",
                    },
                },
            }
        ]

        merged = TOOLBOX.merge_outline_repair_item_output(template, existing)
        section = merged[0]

        self.assertEqual("新的主体切片", section["source_emotion_parity"]["source_excerpt"])
        self.assertEqual(
            [{"role": "起拍", "evidence": "新的证据"}],
            section["source_emotion_parity"]["source_emotion_sequence"],
        )
        contract = section["first_draft_generation_contract"]
        self.assertEqual("新的精确摘录", contract["source_performance_excerpt"])
        self.assertEqual(["新的证据A", "新的证据B"], contract["source_performance_evidence"])
        self.assertEqual(
            [{"subflow_id": "SF-01", "source_range": "L1-L2"}],
            contract["source_slice_bindings"],
        )
        self.assertEqual(
            "新的逐节漂移",
            contract["emotion_process"]["memory_association_or_attention_drift"],
        )
        self.assertEqual("旧值", contract["emotion_process"]["contradictory_impulse"])

    def test_minimal_section_repair_template_only_contains_failed_nested_field(self) -> None:
        sections = [
            {
                "section_id": "1",
                "scene_logic_contract": {"scene_entry_state": "入口", "scene_exit_state": "出口"},
                "first_draft_generation_contract": {
                    "emotion_process": {"entry_state": "", "scene_afterpain": "余痛"},
                    "source_performance_excerpt": "很长的原文载荷",
                },
            }
        ]

        template = TOOLBOX.minimal_section_repair_template(
            sections,
            "first-draft",
            ["第 1 节 first_draft_generation_contract.emotion_process.entry_state 不能为空"],
        )

        self.assertEqual(
            [{"section_id": "1", "first_draft_generation_contract": {"emotion_process": {"entry_state": ""}}}],
            template,
        )

    def test_merge_outline_sections_delta_preserves_previously_passed_nested_fields(self) -> None:
        base = [
            {
                "section_id": "1",
                "first_draft_generation_contract": {
                    "emotion_process": {"entry_state": "已通过入口", "scene_afterpain": "已通过余痛"}
                },
                "scene_logic_contract": {"scene_entry_state": "旧入口", "scene_exit_state": "旧出口"},
            }
        ]
        delta = [{"section_id": "1", "scene_logic_contract": {"scene_exit_state": "新出口"}}]

        merged = TOOLBOX.merge_outline_sections_by_id(base, delta, ["1"])

        self.assertEqual("已通过入口", merged[0]["first_draft_generation_contract"]["emotion_process"]["entry_state"])
        self.assertEqual("旧入口", merged[0]["scene_logic_contract"]["scene_entry_state"])
        self.assertEqual("新出口", merged[0]["scene_logic_contract"]["scene_exit_state"])

    def test_first_draft_precheck_respects_focus_section_ids(self) -> None:
        self.paths["outline"].write_text("## 第1节\n\n动作一\n\n## 第2节\n\n动作二\n", encoding="utf-8")
        data = {
            "sections": [
                {"section_id": "1", "first_draft_generation_contract": {}},
                {"section_id": "2", "first_draft_generation_contract": {}},
            ],
            "selected_source_originals": [],
            "primary_subflow_semantic_inventory": [],
            "primary_source_semantic_bundle": {},
            "global_review": {},
        }

        with patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_primary_subflow_inventory",
            return_value={},
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_first_draft_generation_contract",
            side_effect=lambda _contract, _source_texts, _inventory, label, errors, **_kwargs: errors.append(
                f"{label} 当前节错误"
            ),
        ):
            errors, _ = TOOLBOX.outline_precheck_errors_from_data(
                self.paths,
                data,
                {"first-draft"},
                focus_section_ids=["1"],
            )

        self.assertIn("第 1 节 当前节错误", errors)
        self.assertNotIn("第 2 节 当前节错误", errors)

    def test_handoff_repair_template_only_contains_failing_pair(self) -> None:
        data = {
            "section_handoff_chain": [
                {"from_section_id": "1", "to_section_id": "2", "handoff_trigger": "待修"},
                {"from_section_id": "2", "to_section_id": "3", "handoff_trigger": "保留"},
            ]
        }

        template = TOOLBOX.outline_repair_template_for_key(
            data,
            "section_handoff_chain",
            focus_handoff_pairs=[("1", "2")],
        )

        self.assertEqual([{"from_section_id": "1", "to_section_id": "2", "handoff_trigger": "待修"}], template)

    def test_outline_repair_batches_up_to_six_sections(self) -> None:
        section_ids = TOOLBOX.outline_trim_focus_section_ids(
            "sections",
            "sections",
            ["1", "2", "3", "4", "5", "6", "7"],
        )

        self.assertEqual(["1", "2", "3", "4", "5", "6"], section_ids)

    def test_section_repair_template_prefills_declared_scene_states(self) -> None:
        outline_sections = TOOLBOX.parse_outline_sections_map(
            "## 第1节\n\n- 场景入口状态：她已经到门外。\n"
            "- 场景出口状态：她带走了钥匙。\n"
            "\n## 第2节\n\n- 场景入口状态：他发现门已锁。\n"
            "- 场景出口状态：他失去进入权。\n"
        )
        template = [
            {"section_id": "1", "scene_logic_contract": {"scene_entry_state": ""}},
            {
                "section_id": "2",
                "scene_logic_contract": {"scene_entry_state": "人工精确入口"},
            },
        ]

        seeded = TOOLBOX.seed_section_template_scene_states(template, outline_sections)

        self.assertEqual(
            "她已经到门外。",
            seeded[0]["scene_logic_contract"]["scene_entry_state"],
        )
        self.assertEqual(
            "她带走了钥匙。",
            seeded[0]["scene_logic_contract"]["scene_exit_state"],
        )
        self.assertEqual(
            "人工精确入口",
            seeded[1]["scene_logic_contract"]["scene_entry_state"],
        )
        self.assertEqual(
            "他失去进入权。",
            seeded[1]["scene_logic_contract"]["scene_exit_state"],
        )

    def test_rebuilt_section_repair_template_keeps_declared_scene_states(self) -> None:
        self.paths["outline"].write_text(
            "## 第1节\n\n"
            "- 场景入口状态：她已经到门外。\n"
            "- 场景出口状态：她带走了钥匙。\n",
            encoding="utf-8",
        )
        receipt = {
            "sections": [
                {
                    "section_id": "1",
                    "scene_logic_contract": {
                        "scene_entry_state": "",
                        "scene_exit_state": "",
                    },
                }
            ]
        }
        TOOLBOX.atomic_write_json(self.paths["outline_contract"], receipt)
        packet = {
            "receipt_key": "sections",
            "focus_group": "sections",
            "focus_context": {"focus_section_ids": ["1"]},
            "focus_errors": [
                "第 1 节 scene_logic_contract.scene_entry_state 不能为空",
                "第 1 节 scene_logic_contract.scene_exit_state 不能为空",
            ],
        }

        template = TOOLBOX.outline_repair_template_from_packet(self.paths, packet)
        scene_logic = template[0]["scene_logic_contract"]

        self.assertEqual("她已经到门外。", scene_logic["scene_entry_state"])
        self.assertEqual("她带走了钥匙。", scene_logic["scene_exit_state"])

    def test_section_states_are_synchronized_into_adjacent_handoffs(self) -> None:
        receipt = {
            "sections": [
                {
                    "section_id": "1",
                    "scene_logic_contract": {
                        "scene_entry_state": "第一节入口",
                        "scene_exit_state": "第一节出口",
                    },
                },
                {
                    "section_id": "2",
                    "scene_logic_contract": {
                        "scene_entry_state": "第二节入口",
                        "scene_exit_state": "第二节出口",
                    },
                },
            ],
            "section_handoff_chain": [
                {
                    "from_section_id": "1",
                    "to_section_id": "2",
                    "from_exit_state": "旧出口",
                    "to_entry_state": "旧入口",
                    "handoff_trigger": "保留人工语义字段",
                }
            ],
        }

        synchronized = TOOLBOX.synchronize_outline_handoff_states(receipt)
        handoff = synchronized["section_handoff_chain"][0]

        self.assertEqual("第一节出口", handoff["from_exit_state"])
        self.assertEqual("第二节入口", handoff["to_entry_state"])
        self.assertEqual("保留人工语义字段", handoff["handoff_trigger"])
        self.assertEqual("旧出口", receipt["section_handoff_chain"][0]["from_exit_state"])

    def test_eligible_outline_evidence_returns_exact_bounded_lines(self) -> None:
        section = "## 第1节\n\n### 主事件\n- 她当场扣下证件。\n1. 他先替第三人解释。\n"

        evidence = TOOLBOX.eligible_outline_evidence(section)

        self.assertEqual(["她当场扣下证件。", "他先替第三人解释。"], evidence)
        self.assertTrue(all(item in section for item in evidence))

    def test_outline_blocks_prefer_summary_object_lines(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            TOOLBOX.print_outline_repair_focus_block(
                {
                    "focus_group": "sections",
                    "receipt_key": "sections",
                    "focus_context": {"focus_section_ids": ["1"]},
                    "summary": {
                        "primary_focus_summary": "group=sections",
                        "primary_error_preview": "error preview",
                        "focus_summary_line": "summary focus",
                        "guidance_summary_line": "summary guidance",
                    },
                }
            )
            TOOLBOX.print_outline_repair_guidance(
                {
                    "allowed_external_rule_dependency_domains": ["none"],
                    "beat_dependency_chain_fields": ["beat_id"],
                },
                TOOLBOX.packet_summary_text(
                    {
                        "summary": {
                            "primary_focus_summary": "group=sections",
                            "primary_error_preview": "error preview",
                            "focus_summary_line": "summary focus",
                            "guidance_summary_line": "summary guidance",
                        },
                    },
                    "guidance_summary_line",
                ),
            )

        text = output.getvalue()
        self.assertIn("outline_focus_summary_line: summary focus", text)
        self.assertIn("outline_guidance_summary_line: summary guidance", text)

    def test_outline_precheck_can_focus_on_sections_only(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n\n## 2. 失位\n\n动作三\n动作四\n",
            encoding="utf-8",
        )
        receipt = {
            "sections": [
                {
                    "section_id": "1",
                    "verdict": "pending",
                    "irreversible_action": "",
                    "controlling_object": "",
                    "manual_judgment": "",
                    "scene_logic_contract": {
                        "target_outline_evidence": ["动作一"],
                        "beat_dependency_chain": [],
                        "knowledge_state_chain": [],
                        "scene_exit_state": "前节结束",
                        "scene_entry_state": "前节开始",
                    },
                    "outline_evidence": ["动作一", "动作二"],
                },
                {
                    "section_id": "2",
                    "verdict": "passed",
                    "irreversible_action": "掉位成立",
                    "controlling_object": "花束",
                    "manual_judgment": "有余痛",
                    "scene_logic_contract": {
                        "target_outline_evidence": ["动作三"],
                        "beat_dependency_chain": [
                            {
                                "beat_id": "1",
                                "actor": "甲",
                                "action": "看见",
                                "from_state": "起点",
                                "knowledge_before": "已知",
                                "spatial_or_object_access": "可见",
                                "to_state": "终点",
                                "next_beat_cause": "继续",
                            },
                            {
                                "beat_id": "2",
                                "actor": "乙",
                                "action": "回答",
                                "from_state": "终点",
                                "knowledge_before": "已知",
                                "spatial_or_object_access": "可见",
                                "to_state": "再变",
                                "next_beat_cause": "继续",
                            },
                            {
                                "beat_id": "3",
                                "actor": "甲",
                                "action": "离开",
                                "from_state": "再变",
                                "knowledge_before": "已知",
                                "spatial_or_object_access": "可见",
                                "to_state": "收尾",
                                "next_beat_cause": "结束",
                            },
                        ],
                        "knowledge_state_chain": [
                            {
                                "fact_id": "F-1",
                                "character": "甲",
                                "initial_state": "不知",
                                "final_state": "知道",
                                "incompatible_states": ["不知/知道"],
                                "transitions": ["看见后知道"],
                            }
                        ],
                        "scene_exit_state": "后节结束",
                        "scene_entry_state": "后节开始",
                    },
                    "outline_evidence": ["动作三", "动作四"],
                },
            ],
            "outline_bridge_flow_parity": [],
            "section_handoff_chain": [],
            "story_fact_state_ledger": [],
            "auxiliary_subflow_flow_parity": [],
        }
        self.paths["outline_contract"].write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        args = argparse.Namespace(only=["sections"])
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_outline_precheck(self.paths, args)

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("project_toolbox: outline-precheck blocked", text)
        self.assertIn("第 1 节 verdict 必须为 passed", text)
        self.assertIn("第 2 节 beat_dependency_chain[1].trigger 不能为空", text)
        self.assertIn("第 2 节 knowledge_state_chain[1].transitions[1] 必须是对象", text)
        self.assertTrue(self.paths["outline_repair_packet"].is_file())
        self.assertTrue(self.paths["outline_repair_item_output"].is_file())
        self.assertIn("repair_packet:", text)
        self.assertIn("repair_result_template:", text)
        self.assertIn("primary_focus_summary:", text)
        self.assertIn("primary_error_preview:", text)
        self.assertIn("outline-repair-apply --packet-sha", text)
        self.assertIn("禁止继续用 cat/sed/jq", text)
        self.assertIn("completion_state: continue_required_until_start-draft", text)
        self.assertIn("未到 start-draft 前不得收口", text)
        self.assertIn("outline-precheck --only sections", text)
        self.assertIn("禁止搜索其他项目的细纲回执/设定/大纲/正文当模板", text)
        self.assertNotIn("原文桥段对齐", text)
        packet = json.loads(self.paths["outline_repair_packet"].read_text(encoding="utf-8"))
        self.assertIn("summary", packet)
        self.assertIn("primary_focus_summary", packet["summary"])
        self.assertIn("primary_error_preview", packet["summary"])

    def test_outline_repair_apply_sections_only_validates_current_focus_section(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n\n## 2. 失位\n\n动作三\n动作四\n",
            encoding="utf-8",
        )
        receipt = {
            "sections": [
                {
                    "section_id": "1",
                    "verdict": "pending",
                    "irreversible_action": "",
                    "controlling_object": "",
                    "manual_judgment": "",
                    "character_missteps": [],
                    "outline_evidence": ["动作一", "动作二"],
                    "scene_logic_contract": {
                        "target_outline_evidence": ["动作一", "动作二"],
                    },
                },
                {
                    "section_id": "2",
                    "verdict": "pending",
                    "irreversible_action": "",
                    "controlling_object": "",
                    "manual_judgment": "",
                    "character_missteps": [],
                    "outline_evidence": ["动作三", "动作四"],
                    "scene_logic_contract": {
                        "target_outline_evidence": ["动作三", "动作四"],
                    },
                },
            ],
            "outline_bridge_flow_parity": [],
            "section_handoff_chain": [],
            "story_fact_state_ledger": [],
            "auxiliary_subflow_flow_parity": [],
        }
        self.paths["outline_contract"].write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        packet = {
            "summary": {
                "primary_focus_summary": "group=sections | receipt_key=sections | sections=1",
                "primary_error_preview": "第 1 节 verdict 必须为 passed",
                "focus_summary_line": "group=sections | receipt_key=sections | sections=1",
                "guidance_summary_line": "rules=yes | field_groups=5 | sections=1 | candidates=0",
            },
            "packet_sha256": "",
            "receipt_key": "sections",
            "focus_group": "sections",
            "rerun_command": "outline-precheck --only sections",
            "outline_contract_receipt_key_sha256": TOOLBOX.json_value_sha256(
                TOOLBOX.outline_receipt_scope_value(receipt, "sections", ["1"])
            ),
            "focus_context": {"focus_section_ids": ["1"]},
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["outline_repair_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps(
                [
                    {
                        "section_id": "1",
                        "verdict": "passed",
                        "irreversible_action": "起事成立",
                        "controlling_object": "花束",
                        "manual_judgment": "当前节已承重",
                        "character_missteps": ["先忍", "再问"],
                        "outline_evidence": ["动作一", "动作二"],
                        "scene_logic_contract": {
                            "target_outline_evidence": ["动作一", "动作二"],
                        },
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_scene_logic_contract",
            return_value=None,
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_source_emotion_parity",
            return_value=None,
        ):
            with redirect_stdout(output):
                result = TOOLBOX.command_outline_repair_apply(
                    self.paths,
                    argparse.Namespace(packet_sha=packet["packet_sha256"]),
                )

        text = output.getvalue()
        updated_receipt = json.loads(self.paths["outline_contract"].read_text(encoding="utf-8"))
        updated_section_1 = next(
            item for item in updated_receipt["sections"] if item["section_id"] == "1"
        )
        updated_section_2 = next(
            item for item in updated_receipt["sections"] if item["section_id"] == "2"
        )
        self.assertEqual(0, result)
        self.assertIn("project_toolbox: outline-repair-apply passed", text)
        self.assertEqual("passed", updated_section_1["verdict"])
        self.assertEqual("pending", updated_section_2["verdict"])

    def test_repair_output_declares_ready_for_outline_bridge_list_payload(self) -> None:
        path = self.paths["outline_repair_item_output"]
        path.write_text(
            json.dumps(
                [{"source_bridge_id": "BID-01", "target_emotion_sequence": [{"role": "起拍"}]}],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.assertTrue(TOOLBOX.repair_output_declares_ready(path))

    def test_outline_precheck_auto_applies_multiple_outline_packets_in_same_run(self) -> None:
        self.paths["outline_contract"].write_text(
            json.dumps({"sections": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        packet_shas = iter(["sha-1", "sha-2"])
        precheck_results = iter(
            [
                (["第 1 节待修"], ["precheck-1"]),
                (["第 2 节待修"], ["precheck-2"]),
                ([], ["precheck-3"]),
            ]
        )
        apply_calls: list[str] = []
        output = StringIO()

        def fake_precheck(
            _paths: dict[str, Path],
            enabled: set[str],
        ) -> tuple[list[str], list[str]]:
            self.assertEqual({"sections"}, enabled)
            return next(precheck_results)

        def fake_export(
            _paths: dict[str, Path],
            _source_stage: str,
            errors: list[str],
            _rerun_command: str,
            preserve_existing_output: bool = False,
            emit_output: bool = True,
        ) -> dict[str, object]:
            packet_sha = next(packet_shas)
            packet = {
                "packet_sha256": packet_sha,
                "summary": {
                    "primary_focus_summary": "group=sections",
                    "primary_error_preview": errors[0],
                    "focus_summary_line": "group=sections",
                    "guidance_summary_line": "guidance",
                },
            }
            self.paths["outline_repair_packet"].write_text(
                json.dumps(packet, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.paths["outline_repair_item_output"].write_text(
                json.dumps([{"section_id": packet_sha, "verdict": "passed"}], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return packet

        def fake_apply(_paths: dict[str, Path], args: argparse.Namespace) -> int:
            apply_calls.append(args.packet_sha)
            return 0

        with patch.object(
            TOOLBOX,
            "auto_apply_ready_prewrite_repairs",
            return_value=(0, []),
        ), patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            side_effect=fake_precheck,
        ), patch.object(
            TOOLBOX,
            "export_outline_repair_packet",
            side_effect=fake_export,
        ), patch.object(
            TOOLBOX,
            "command_outline_repair_apply",
            side_effect=fake_apply,
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_precheck(
                self.paths,
                argparse.Namespace(only=["sections"]),
            )

        text = output.getvalue()
        self.assertEqual(0, result)
        self.assertEqual(["sha-1", "sha-2"], apply_calls)
        self.assertIn("project_toolbox: outline-precheck passed", text)

    def test_outline_validate_skips_full_validation_when_precheck_fails(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps({"sections": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        args = argparse.Namespace(only=["sections"])
        output = StringIO()

        with patch.object(TOOLBOX.OUTLINE_PERFORMANCE, "validate_receipt") as validate_receipt:
            with redirect_stdout(output):
                result = TOOLBOX.command_outline_validate(self.paths, args)

        text = output.getvalue()
        self.assertEqual(2, result)
        validate_receipt.assert_not_called()
        self.assertIn("project_toolbox: outline-validate blocked", text)
        self.assertIn("skip-full-outline-validation-due-to-precheck-errors", text)
        self.assertTrue(self.paths["outline_repair_packet"].is_file())
        self.assertTrue(self.paths["outline_repair_item_output"].is_file())
        self.assertIn("outline-repair-apply --packet-sha", text)
        self.assertIn("completion_state: continue_required_until_start-draft", text)
        self.assertIn("立即重跑 outline-validate", text)
        self.assertIn("未到 start-draft 前禁止输出 final_answer", text)
        self.assertIn("只能继续 commentary 并给出下一条固定续跑动作", text)

    def test_outline_validate_prints_forced_continue_action_when_full_validation_fails(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n- 子事件：动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(only=["all"])
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=([], ["precheck"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_receipt",
            return_value=["正式强校验失败"],
        ):
            with redirect_stdout(output):
                result = TOOLBOX.command_outline_validate(self.paths, args)

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("project_toolbox: outline-validate blocked", text)
        self.assertIn("正式强校验失败", text)
        self.assertTrue(self.paths["outline_repair_packet"].is_file())
        self.assertTrue(self.paths["outline_repair_item_output"].is_file())
        self.assertIn("outline-repair-apply --packet-sha", text)
        self.assertIn("禁止继续用 cat/sed/jq", text)
        self.assertIn("completion_state: continue_required_until_start-draft", text)
        self.assertIn("未到 start-draft 前禁止输出 final_answer", text)
        self.assertIn("禁止触发 task_complete", text)

    def test_outline_validate_prints_start_draft_action_when_passed(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n- 子事件：动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(only=["all"])
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=([], ["precheck"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["ensure-section-bundle"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=[],
        ):
            with redirect_stdout(output):
                result = TOOLBOX.command_outline_validate(self.paths, args)

        text = output.getvalue()
        self.assertEqual(0, result)
        self.assertIn("project_toolbox: outline-validate passed", text)
        self.assertIn("立即运行 start-draft", text)
        self.assertIn("show-section -> 完整阅读 -> open-section", text)

    def test_outline_validate_blocks_when_draft_prerequisites_remain(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(only=["all"])
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=([], ["precheck"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["ensure-section-bundle"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=["首写容量契约未通过", "第 1 节缺少 source_style_granularity"],
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_validate(self.paths, args)

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("project_toolbox: outline-validate blocked", text)
        self.assertIn("首写容量契约未通过", text)
        self.assertIn("draft_prereq_repair_commands: draft-capacity-precheck", text)
        self.assertIn("draft_prereq_primary_command: draft-capacity-precheck", text)
        self.assertIn("draft_prereq_reason[draft-capacity-precheck]:", text)
        self.assertIn("next_fixed_commands:", text)

    def test_outline_validate_parses_draft_prereq_only_once(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(only=["all"])
        output = StringIO()
        parse_calls: list[list[str]] = []
        original = TOOLBOX.parse_draft_prereq_command_reasons

        def record_parse(
            errors: list[str],
            paths: dict[str, Path] | None = None,
        ) -> list[tuple[str, list[str]]]:
            parse_calls.append(list(errors))
            return original(errors, paths)

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=([], ["precheck"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["ensure-section-bundle"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=["首写容量契约未通过", "第 1 节缺少 source_style_granularity"],
        ), patch.object(
            TOOLBOX,
            "parse_draft_prereq_command_reasons",
            side_effect=record_parse,
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_validate(self.paths, args)

        self.assertEqual(2, result)
        self.assertEqual(
            [["首写容量契约未通过", "第 1 节缺少 source_style_granularity"]],
            parse_calls,
        )

    def test_outline_validate_refreshes_opening_repair_packet_when_opening_is_blocked(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["opening_contract"].write_text(
            json.dumps(
                {
                    "primary_source": {"path": str(self.project / "source.txt")},
                    "target_text": {"path": str(self.paths["outline"])},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(only=["all"])
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=([], ["precheck"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["ensure-section-bundle"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=["开头承重契约门禁未通过"],
        ), patch.object(
            TOOLBOX,
            "validate_opening_receipt_from_binding",
            return_value=["开头承重契约实时复验失败"],
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_validate(self.paths, args)

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertTrue(self.paths["opening_repair_packet"].is_file())
        self.assertTrue(self.paths["opening_repair_item_output"].is_file())
        self.assertIn("draft_prereq_primary_command: opening-precheck", text)
        self.assertNotIn("repair_packet:", text)
        self.assertNotIn("opening-apply --packet-sha", text)

    def test_outline_repair_next_writes_focus_packet_and_result_template(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n- 子事件：动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [{"section_id": "1", "verdict": "pending"}],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=(["第 1 节 verdict 必须为 passed"], ["precheck"]),
        ):
            with redirect_stdout(output):
                result = TOOLBOX.command_outline_repair_next(self.paths, argparse.Namespace())

        self.assertEqual(2, result)
        self.assertTrue(self.paths["outline_repair_packet"].is_file())
        self.assertTrue(self.paths["outline_repair_item_output"].is_file())
        packet = json.loads(self.paths["outline_repair_packet"].read_text(encoding="utf-8"))
        item = json.loads(self.paths["outline_repair_item_output"].read_text(encoding="utf-8"))
        self.assertEqual("outline_repair_packet", packet["kind"])
        self.assertEqual("sections", packet["focus_group"])
        self.assertEqual("sections", packet["receipt_key"])
        self.assertIn("summary", packet)
        self.assertIn("primary_focus_summary", packet["summary"])
        self.assertIn("primary_error_preview", packet["summary"])
        self.assertEqual(
            "group=sections | receipt_key=sections | sections=1",
            packet["summary"]["focus_summary_line"],
        )
        self.assertEqual(TOOLBOX.json_value_sha256(item), packet["result_template_sha256"])
        self.assertIn("repair_guidance", packet)
        text = output.getvalue()
        self.assertIn("repair_packet:", text)
        self.assertIn("repair_result_template:", text)
        self.assertIn("packet_sha256:", text)
        self.assertIn("primary_focus_summary:", text)
        self.assertIn("primary_error_preview:", text)
        self.assertIn("outline_focus_block_begin", text)
        self.assertIn("outline_focus_summary_line: group=sections | receipt_key=sections | sections=1", text)
        self.assertIn("outline_focus_meta_begin", text)
        self.assertIn("focus_group: sections", text)
        self.assertIn("receipt_key: sections", text)
        self.assertIn("outline_focus_meta_end", text)
        self.assertIn("outline_focus_sections_begin", text)
        self.assertIn("focus_sections: 1", text)
        self.assertIn("outline_focus_sections_end", text)
        self.assertIn("outline_focus_block_end", text)
        self.assertIn("outline_guidance_block_begin", text)
        self.assertIn("outline_guidance_block_end", text)
        self.assertIn("outline-repair-apply", text)

    def test_outline_repair_apply_merges_item_output_into_receipt(self) -> None:
        self.paths["outline"].write_text("## 1. 起事\n", encoding="utf-8")
        self.paths["outline_contract"].write_text(
            json.dumps({"sections": [], "gate_status": "pending"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        packet = {
            "packet_sha256": "",
            "outline_contract_sha256": TOOLBOX.file_sha256(self.paths["outline_contract"]),
            "receipt_key": "sections",
            "summary": {
                "primary_focus_summary": "group=sections | receipt_key=sections",
                "primary_error_preview": "第 1 节待修",
                "focus_summary_line": "group=sections | receipt_key=sections",
                "guidance_summary_line": "errors=1",
            },
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["outline_repair_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps([{"section_id": "1", "verdict": "passed"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        outline_packet_mtime = self.paths["outline_repair_packet"].stat().st_mtime + 1
        os.utime(
            self.paths["outline_repair_item_output"],
            (outline_packet_mtime, outline_packet_mtime),
        )
        outline_packet_mtime = self.paths["outline_repair_packet"].stat().st_mtime + 1
        os.utime(
            self.paths["outline_repair_item_output"],
            (outline_packet_mtime, outline_packet_mtime),
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors_from_data",
            return_value=([], []),
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        self.assertEqual(0, result)
        receipt = json.loads(self.paths["outline_contract"].read_text(encoding="utf-8"))
        self.assertEqual([{"section_id": "1", "verdict": "passed"}], receipt["sections"])
        self.assertIn("merge-updated-sections-into-outline-contract", output.getvalue())

    def test_outline_repair_apply_persists_derived_handoff_states(self) -> None:
        self.paths["outline"].write_text("## 第1节\n\n## 第2节\n", encoding="utf-8")
        receipt = {
            "sections": [
                {
                    "section_id": "1",
                    "scene_logic_contract": {
                        "scene_entry_state": "入口1",
                        "scene_exit_state": "旧出口1",
                    },
                },
                {
                    "section_id": "2",
                    "scene_logic_contract": {
                        "scene_entry_state": "入口2",
                        "scene_exit_state": "出口2",
                    },
                },
            ],
            "section_handoff_chain": [
                {
                    "from_section_id": "1",
                    "to_section_id": "2",
                    "from_exit_state": "旧交接出口",
                    "to_entry_state": "旧交接入口",
                }
            ],
        }
        TOOLBOX.atomic_write_json(self.paths["outline_contract"], receipt)
        packet = {
            "packet_sha256": "batch-state-packet",
            "receipt_key": "sections",
            "focus_group": "sections",
            "focus_context": {"focus_section_ids": ["1"]},
            "outline_contract_receipt_key_sha256": TOOLBOX.json_value_sha256(
                TOOLBOX.outline_receipt_scope_value(receipt, "sections", ["1"])
            ),
            "summary": {
                "primary_focus_summary": "group=sections | receipt_key=sections | sections=1",
                "primary_error_preview": "第 1 节待修",
                "focus_summary_line": "group=sections | receipt_key=sections | sections=1",
                "guidance_summary_line": "errors=1",
            },
        }
        TOOLBOX.atomic_write_json(self.paths["outline_repair_packet"], packet)
        TOOLBOX.atomic_write_json_value(
            self.paths["outline_repair_item_output"],
            [
                {
                    "section_id": "1",
                    "scene_logic_contract": {"scene_exit_state": "新出口1"},
                }
            ],
        )

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors_from_data",
            return_value=([], []),
        ):
            result = TOOLBOX.command_outline_repair_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        updated = TOOLBOX.read_json(self.paths["outline_contract"])
        handoff = updated["section_handoff_chain"][0]
        self.assertEqual(0, result)
        self.assertEqual("新出口1", handoff["from_exit_state"])
        self.assertEqual("入口2", handoff["to_entry_state"])

    def test_outline_repair_apply_rejects_invalid_sections_before_merge(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [],
                    "section_handoff_chain": [],
                    "outline_bridge_flow_parity": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        packet = {
            "packet_sha256": "",
            "outline_contract_sha256": TOOLBOX.file_sha256(self.paths["outline_contract"]),
            "receipt_key": "sections",
            "summary": {
                "primary_focus_summary": "group=sections | receipt_key=sections",
                "primary_error_preview": "第 1 节 verdict 必须为 passed",
                "focus_summary_line": "group=sections | receipt_key=sections",
                "guidance_summary_line": "errors=1",
            },
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["outline_repair_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps([{"section_id": "1", "verdict": "pending"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        self.assertEqual(2, result)
        receipt = json.loads(self.paths["outline_contract"].read_text(encoding="utf-8"))
        self.assertEqual([], receipt["sections"])
        self.assertTrue(self.paths["outline_repair_packet"].is_file())
        self.assertTrue(self.paths["outline_repair_item_output"].is_file())
        refreshed_packet = json.loads(self.paths["outline_repair_packet"].read_text(encoding="utf-8"))
        self.assertEqual("outline-repair-apply", refreshed_packet["source_stage"])
        text = output.getvalue()
        self.assertIn("project_toolbox: outline-repair-apply blocked", text)
        self.assertIn("第 1 节 verdict 必须为 passed", text)
        self.assertIn("reject-invalid-outline-repair-writeback-before-merge", text)
        self.assertIn("stage-valid-outline-repair-delta-before-final-merge", text)
        self.assertTrue(self.paths["outline_repair_staging"].is_file())
        self.assertIn("repair_packet:", text)
        self.assertIn("repair_result_template:", text)
        self.assertIn("repair_allowed_external_rule_domains:", text)
        self.assertIn(
            f"next_apply_command: outline-repair-apply --packet-sha {refreshed_packet['packet_sha256']}",
            text,
        )

    def test_outline_repair_apply_accumulates_dependent_packets_before_atomic_merge(self) -> None:
        self.paths["outline"].write_text("## 1. 起事\n", encoding="utf-8")
        original_receipt = {
            "sections": [
                {
                    "section_id": "1",
                    "verdict": "pending",
                    "irreversible_action": "",
                    "scene_logic_contract": {"beat_dependency_chain": []},
                }
            ]
        }
        TOOLBOX.atomic_write_json(self.paths["outline_contract"], original_receipt)

        def write_packet(packet_sha: str) -> dict[str, object]:
            packet = {
                "packet_sha256": packet_sha,
                "receipt_key": "sections",
                "focus_group": "sections",
                "focus_context": {"focus_section_ids": ["1"]},
                "rerun_command": "outline-repair-next",
                "summary": {
                    "primary_focus_summary": "group=sections | receipt_key=sections | sections=1",
                    "primary_error_preview": "第 1 节待修",
                    "focus_summary_line": "group=sections | receipt_key=sections | sections=1",
                    "guidance_summary_line": "errors=1",
                },
                "outline_contract_receipt_key_sha256": TOOLBOX.json_value_sha256(
                    TOOLBOX.outline_receipt_scope_value(original_receipt, "sections", ["1"])
                ),
            }
            TOOLBOX.atomic_write_json(self.paths["outline_repair_packet"], packet)
            return packet

        first_packet = write_packet("static-fields-packet")
        TOOLBOX.atomic_write_json_value(
            self.paths["outline_repair_item_output"],
            [
                {
                    "section_id": "1",
                    "verdict": "passed",
                    "irreversible_action": "她当众签字离开",
                }
            ],
        )
        with patch.object(
            TOOLBOX,
            "outline_precheck_errors_from_data",
            return_value=(["第 1 节 beat_dependency_chain 至少需要 3 拍"], []),
        ), patch.object(TOOLBOX, "export_outline_repair_packet"):
            first_result = TOOLBOX.command_outline_repair_apply(
                self.paths,
                argparse.Namespace(packet_sha=first_packet["packet_sha256"]),
            )

        self.assertEqual(2, first_result)
        self.assertEqual(original_receipt, TOOLBOX.read_json(self.paths["outline_contract"]))
        self.assertTrue(self.paths["outline_repair_staging"].is_file())

        second_packet = write_packet("dependency-chain-packet")
        TOOLBOX.atomic_write_json_value(
            self.paths["outline_repair_item_output"],
            [
                {
                    "section_id": "1",
                    "scene_logic_contract": {
                        "beat_dependency_chain": [{"beat_id": "B1"}, {"beat_id": "B2"}, {"beat_id": "B3"}]
                    },
                }
            ],
        )
        with patch.object(
            TOOLBOX,
            "outline_precheck_errors_from_data",
            return_value=([], []),
        ):
            second_result = TOOLBOX.command_outline_repair_apply(
                self.paths,
                argparse.Namespace(packet_sha=second_packet["packet_sha256"]),
            )

        self.assertEqual(0, second_result)
        merged = TOOLBOX.read_json(self.paths["outline_contract"])["sections"][0]
        self.assertEqual("她当众签字离开", merged["irreversible_action"])
        self.assertEqual(3, len(merged["scene_logic_contract"]["beat_dependency_chain"]))
        self.assertFalse(self.paths["outline_repair_staging"].exists())

    def test_outline_repair_staging_is_discarded_when_outline_changes(self) -> None:
        self.paths["outline"].write_text("## 1. 起事\n", encoding="utf-8")
        receipt = {"sections": [{"section_id": "1", "verdict": "pending"}]}
        TOOLBOX.atomic_write_json(self.paths["outline_contract"], receipt)
        packet = {
            "packet_sha256": "packet-1",
            "receipt_key": "sections",
            "focus_group": "sections",
            "focus_context": {"focus_section_ids": ["1"]},
        }
        candidate = TOOLBOX.merge_outline_repair_value_into_receipt(
            receipt,
            "sections",
            [{"section_id": "1", "verdict": "passed"}],
            ["1"],
        )
        TOOLBOX.write_outline_repair_staging(self.paths, packet, candidate)

        self.paths["outline"].write_text("## 1. 起事\n\n新动作\n", encoding="utf-8")
        effective = TOOLBOX.apply_valid_outline_repair_staging(self.paths, receipt, packet)

        self.assertEqual(receipt, effective)
        self.assertFalse(self.paths["outline_repair_staging"].exists())

    def test_outline_precheck_reads_accumulated_repair_candidate(self) -> None:
        self.paths["outline"].write_text("## 1. 起事\n", encoding="utf-8")
        receipt = {"sections": [{"section_id": "1", "irreversible_action": ""}]}
        TOOLBOX.atomic_write_json(self.paths["outline_contract"], receipt)
        packet = {
            "packet_sha256": "packet-1",
            "receipt_key": "sections",
            "focus_group": "sections",
            "focus_context": {"focus_section_ids": ["1"]},
        }
        candidate = TOOLBOX.merge_outline_repair_value_into_receipt(
            receipt,
            "sections",
            [{"section_id": "1", "irreversible_action": "她当众签字离开"}],
            ["1"],
        )
        TOOLBOX.write_outline_repair_staging(self.paths, packet, candidate)

        def inspect_candidate(
            _paths: dict[str, Path],
            data: dict[str, object],
            enabled: set[str],
            focus_section_ids: list[str] | None = None,
        ) -> tuple[list[str], list[str]]:
            del enabled, focus_section_ids
            sections = data["sections"]
            self.assertIsInstance(sections, list)
            self.assertEqual("她当众签字离开", sections[0]["irreversible_action"])
            return [], []

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors_from_data",
            side_effect=inspect_candidate,
        ):
            errors, actions = TOOLBOX.outline_precheck_errors(self.paths, {"sections"})

        self.assertEqual([], errors)
        self.assertEqual([], actions)

    def test_outline_repair_apply_sections_does_not_force_first_draft_group(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n- 子事件：动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [{"section_id": "1", "verdict": "pending"}],
                    "section_handoff_chain": [],
                    "outline_bridge_flow_parity": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        packet = {
            "packet_sha256": "",
            "outline_contract_sha256": TOOLBOX.file_sha256(self.paths["outline_contract"]),
            "receipt_key": "sections",
            "focus_context": {"focus_section_ids": ["1"]},
            "summary": {
                "primary_focus_summary": "group=sections | receipt_key=sections | sections=1",
                "primary_error_preview": "第 1 节待修",
                "focus_summary_line": "group=sections | receipt_key=sections | sections=1",
                "guidance_summary_line": "errors=1",
            },
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["outline_repair_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps([{"section_id": "1", "verdict": "passed"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        outline_packet_mtime = self.paths["outline_repair_packet"].stat().st_mtime + 1
        os.utime(
            self.paths["outline_repair_item_output"],
            (outline_packet_mtime, outline_packet_mtime),
        )
        output = StringIO()

        def fake_precheck(
            _paths: dict[str, Path],
            _data: dict[str, object],
            enabled: set[str],
            focus_section_ids: list[str] | None = None,
        ) -> tuple[list[str], list[str]]:
            self.assertEqual({"sections"}, enabled)
            self.assertEqual(["1"], focus_section_ids)
            return [], []

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors_from_data",
            side_effect=fake_precheck,
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        self.assertEqual(0, result)
        receipt = json.loads(self.paths["outline_contract"].read_text(encoding="utf-8"))
        self.assertEqual([{"section_id": "1", "verdict": "passed"}], receipt["sections"])
        self.assertIn("merge-updated-sections-into-outline-contract", output.getvalue())

    def test_outline_repair_apply_first_draft_only_validates_first_draft_group(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n\n## 2. 失位\n\n- 主事件：动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [
                        {"section_id": "1", "verdict": "passed"},
                        {"section_id": "2", "verdict": "passed"},
                    ],
                    "section_handoff_chain": [],
                    "outline_bridge_flow_parity": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        packet = {
            "packet_sha256": "",
            "outline_contract_sha256": TOOLBOX.file_sha256(self.paths["outline_contract"]),
            "focus_group": "first-draft",
            "receipt_key": "sections",
            "focus_context": {"focus_section_ids": ["1", "2"]},
            "summary": {
                "primary_focus_summary": "group=first-draft | receipt_key=sections | sections=1,2",
                "primary_error_preview": "第 1 节待修",
                "focus_summary_line": "group=first-draft | receipt_key=sections | sections=1,2",
                "guidance_summary_line": "errors=1",
            },
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["outline_repair_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps(
                [
                    {"section_id": "1", "verdict": "passed"},
                    {"section_id": "2", "verdict": "passed"},
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        def fake_precheck(
            _paths: dict[str, Path],
            _data: dict[str, object],
            enabled: set[str],
            focus_section_ids: list[str] | None = None,
        ) -> tuple[list[str], list[str]]:
            self.assertEqual({"first-draft"}, enabled)
            self.assertEqual(["1", "2"], focus_section_ids)
            return [], []

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors_from_data",
            side_effect=fake_precheck,
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        self.assertEqual(0, result)
        receipt = json.loads(self.paths["outline_contract"].read_text(encoding="utf-8"))
        self.assertEqual(
            [{"section_id": "1", "verdict": "passed"}, {"section_id": "2", "verdict": "passed"}],
            receipt["sections"],
        )
        self.assertIn("merge-updated-sections-into-outline-contract", output.getvalue())

    def test_outline_repair_next_packet_contains_focus_context_for_sections(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n动作一\n动作二\n\n## 2. 失位\n\n动作三\n动作四\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [
                        {"section_id": "1", "verdict": "pending"},
                        {"section_id": "2", "verdict": "passed"},
                    ],
                    "primary_subflow_semantic_inventory": [{"subflow_id": "SF-01"}],
                    "selected_source_originals": [{"path": "/tmp/source.txt"}],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=(["第 1 节 verdict 必须为 passed"], ["precheck"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_next(self.paths, argparse.Namespace())

        self.assertEqual(2, result)
        packet = json.loads(self.paths["outline_repair_packet"].read_text(encoding="utf-8"))
        self.assertEqual(["1"], packet["focus_context"]["focus_section_ids"])
        self.assertIn("## 1. 起事", packet["focus_context"]["outline_sections"]["1"])
        self.assertEqual(
            [{"section_id": "1", "verdict": "pending", "available_causal_asset_ids": [], "outline_evidence": [], "scene_entry_state": "", "scene_exit_state": ""}],
            packet["focus_context"]["current_sections"],
        )
        self.assertNotIn("primary_subflow_semantic_inventory", packet["focus_context"])
        guidance = packet["repair_guidance"]
        self.assertIn("beat_dependency_chain_fields", guidance)
        self.assertIn("knowledge_state_chain_fields", guidance)
        self.assertIn("emotion_beat_fields", guidance)
        self.assertIn("source_slice_binding_fields", guidance)
        self.assertEqual("SF-01", guidance["primary_focus_candidates"][0]["subflow_id"])

    def test_outline_repair_next_prints_repair_guidance(self) -> None:
        source_path = self.project / "原文.txt"
        source_path.write_text("原文证据甲\n原文证据乙\n", encoding="utf-8")
        profile_path = self.project / "book.profile.json"
        profile_path.write_text(
            json.dumps(
                {
                    "causal_precondition_assets": [
                        {
                            "causal_asset_id": "CPA-04",
                            "name": "正式场公开护短",
                            "source_evidence": ["看着他拽在我制服上的手，我忍不住了。"],
                        },
                        {
                            "causal_asset_id": "CPA-01",
                            "name": "多人现场撞见",
                            "source_evidence": ["我没想到执行任务会遇见蒋湛和他的学生。"],
                        },
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n- 子事件：动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [
                        {
                            "section_id": "1",
                            "verdict": "pending",
                            "available_causal_asset_ids": ["CPA-04", "CPA-01"],
                        }
                    ],
                    "primary_subflow_semantic_inventory": [
                        {
                            "subflow_id": "SF-12",
                            "identity": "主体::SF-12",
                            "source_excerpt": "原文片段",
                            "contract": {"source_range": "L9-L39", "required_sequence": ["动作"]},
                        }
                    ],
                    "selected_source_originals": [
                        {
                            "path": str(source_path),
                            "causal_asset_profile": {"path": str(profile_path)},
                        }
                    ],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=(["第 1 节 verdict 必须为 passed"], ["precheck"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_next(self.paths, argparse.Namespace())

        self.assertEqual(2, result)
        text = output.getvalue()
        packet = json.loads(self.paths["outline_repair_packet"].read_text(encoding="utf-8"))
        self.assertEqual(
            "rules=yes | field_groups=5 | sections=1 | candidates=1",
            packet["summary"]["guidance_summary_line"],
        )
        self.assertIn("outline_guidance_block_begin", text)
        self.assertIn("outline_guidance_summary_line: rules=yes | field_groups=5 | sections=1 | candidates=1", text)
        self.assertIn("outline_guidance_rules_begin", text)
        self.assertIn("repair_allowed_external_rule_domains:", text)
        self.assertIn("outline_guidance_rules_end", text)
        self.assertIn("outline_guidance_fields_begin", text)
        self.assertIn("repair_beat_dependency_chain_fields:", text)
        self.assertIn("outline_guidance_fields_end", text)
        self.assertIn("outline_guidance_sections_begin", text)
        self.assertIn("repair_causal_asset_id_rule:", text)
        self.assertIn("repair_section_1_available_causal_asset_ids: CPA-04, CPA-01", text)
        self.assertIn(
            "repair_section_1_causal_asset_candidates: CPA-04=正式场公开护短",
            text,
        )
        self.assertIn("outline_guidance_sections_end", text)
        self.assertIn("outline_guidance_candidates_begin", text)
        self.assertIn("repair_primary_focus_candidates: SF-12@L9-L39", text)
        self.assertIn("outline_guidance_candidates_end", text)
        self.assertIn("outline_guidance_block_end", text)

    def test_outline_repair_next_batches_first_draft_sections(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n\n## 2. 失位\n\n- 主事件：动作二\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [
                        {"section_id": "1", "verdict": "passed", "first_draft_generation_contract": {}},
                        {"section_id": "2", "verdict": "passed", "first_draft_generation_contract": {}},
                    ],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()
        first_draft_errors = [
            "第 1 节 first_draft_generation_contract.source_slice_bindings 至少绑定一段精确原文行段",
            "第 2 节 first_draft_generation_contract.source_slice_bindings 至少绑定一段精确原文行段",
        ]

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=(first_draft_errors, ["precheck"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_next(self.paths, argparse.Namespace())

        self.assertEqual(2, result)
        packet = json.loads(self.paths["outline_repair_packet"].read_text(encoding="utf-8"))
        self.assertEqual("first-draft", packet["focus_group"])
        self.assertEqual("sections", packet["receipt_key"])
        self.assertEqual(["1", "2"], packet["focus_context"]["focus_section_ids"])
        template = json.loads(self.paths["outline_repair_item_output"].read_text(encoding="utf-8"))
        self.assertEqual(["1", "2"], [item["section_id"] for item in template])
        self.assertEqual(
            {"section_id", "first_draft_generation_contract"},
            set(template[0]),
        )

    def test_section_repair_fields_recognize_unqualified_first_draft_source_errors(self) -> None:
        errors = [
            "第 4 节.source_slice_bindings[1].source_range 必须使用 L起始-L结束",
            "第 4 节 source_performance_excerpt 必须来自主体原文完整颗粒包中的精确 SF 切片",
        ]

        self.assertEqual(
            [
                ("first_draft_generation_contract", "source_slice_bindings"),
                ("first_draft_generation_contract", "source_performance_excerpt"),
            ],
            TOOLBOX.section_repair_field_paths("first-draft", errors),
        )

    def test_outline_repair_next_blocks_when_draft_prerequisites_remain(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [{"section_id": "1", "verdict": "passed"}],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=([], ["precheck"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=["首写容量契约未通过"],
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_next(self.paths, argparse.Namespace())

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("project_toolbox: outline-repair-next blocked", text)
        self.assertIn("outline-gates-passed", text)
        self.assertIn("首写容量契约未通过", text)
        self.assertIn("draft_prereq_repair_commands: draft-capacity-precheck", text)
        self.assertIn("draft_prereq_primary_command: draft-capacity-precheck", text)
        self.assertIn("next_fixed_commands:", text)

    def test_outline_repair_next_parses_draft_prereq_only_once(self) -> None:
        self.paths["outline"].write_text(
            "## 1. 起事\n\n- 主事件：动作一\n",
            encoding="utf-8",
        )
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [{"section_id": "1", "verdict": "passed"}],
                    "outline_bridge_flow_parity": [],
                    "section_handoff_chain": [],
                    "story_fact_state_ledger": [],
                    "auxiliary_subflow_flow_parity": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()
        parse_calls: list[list[str]] = []
        original = TOOLBOX.parse_draft_prereq_command_reasons

        def record_parse(
            errors: list[str],
            paths: dict[str, Path] | None = None,
        ) -> list[tuple[str, list[str]]]:
            parse_calls.append(list(errors))
            return original(errors, paths)

        with patch.object(
            TOOLBOX,
            "outline_precheck_errors",
            return_value=([], ["precheck"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_receipt",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=["首写容量契约未通过"],
        ), patch.object(
            TOOLBOX,
            "parse_draft_prereq_command_reasons",
            side_effect=record_parse,
        ), redirect_stdout(output):
            result = TOOLBOX.command_outline_repair_next(
                self.paths, argparse.Namespace()
            )

        self.assertEqual(2, result)
        self.assertEqual([["首写容量契约未通过"]], parse_calls)

    def test_print_draft_prereq_blocked_commands_orders_multiple_contracts(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            TOOLBOX.print_draft_prereq_blocked_commands(
                [
                    "顺序契约门禁未通过: gate_status='pending'",
                    "开头承重契约门禁未通过",
                    "第 1 节缺少 source_style_granularity",
                ]
            )

        text = output.getvalue()
        self.assertIn("completion_state: continue_required_until_start-draft", text)
        self.assertIn(
            "draft_prereq_repair_commands: opening-precheck / sequence-precheck / draft-capacity-precheck",
            text,
        )
        self.assertIn("draft_prereq_primary_command: opening-precheck", text)
        self.assertIn("draft_prereq_reason[opening-precheck]: 开头承重契约门禁未通过", text)
        self.assertIn("draft_prereq_reason[sequence-precheck]: 顺序契约门禁未通过", text)
        self.assertIn("draft_prereq_reason[draft-capacity-precheck]: 第 1 节缺少 source_style_granularity", text)

    def test_print_draft_prereq_blocked_commands_uses_generic_start_draft_for_unmapped_errors(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            TOOLBOX.print_draft_prereq_blocked_commands(
                ["正文写作放行所需 profile 不存在: /tmp/missing-profile.json"]
            )

        text = output.getvalue()
        self.assertIn("draft_prereq_repair_commands: start-draft", text)
        self.assertIn("draft_prereq_primary_command: start-draft", text)
        self.assertIn(
            "draft_prereq_reason[start-draft]: 正文写作放行所需 profile 不存在",
            text,
        )
        self.assertNotIn("opening-precheck / sequence-precheck", text)

    def test_draft_capacity_precheck_reports_capacity_gaps(self) -> None:
        self.paths["draft_capacity_contract"].write_text(
            json.dumps(
                {
                    "gate_status": "pending",
                    "target_words": 9000,
                    "outline": {"path": str(self.paths["outline"]), "sha256": "wrong"},
                    "sections": [
                        {
                            "id": "1",
                            "planned_words": 0,
                            "scene_completion": "",
                            "opening_or_turn": "",
                            "emotion_escalation": "",
                            "end_change": "",
                            "source_mechanism": "",
                            "source_style_granularity": "",
                            "first_draft_style_plan": "",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["outline"].write_text("## 1. 起事\n", encoding="utf-8")
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_draft_capacity_precheck(
                self.paths,
                argparse.Namespace(),
            )

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("project_toolbox: draft-capacity-precheck blocked", text)
        self.assertIn("容量契约 gate_status 必须为 passed", text)
        self.assertIn("第 1 节 planned_words 必须不少于 800", text)
        self.assertIn("section_1_capacity_gaps:", text)
        self.assertIn("capacity_general_gaps:", text)
        self.assertTrue(self.paths["draft_capacity_packet"].is_file())
        self.assertTrue(self.paths["draft_capacity_item_output"].is_file())
        self.assertIn("repair_packet:", text)
        self.assertIn("next_apply_command: draft-capacity-apply --packet-sha", text)
        self.assertIn("补完后立即重跑 draft-capacity-precheck", text)
        packet = json.loads(self.paths["draft_capacity_packet"].read_text(encoding="utf-8"))
        self.assertIn("summary", packet)
        self.assertIn("primary_focus_summary", packet["summary"])
        self.assertIn("primary_error_preview", packet["summary"])
        self.assertEqual(
            "contract=首写容量契约回执.json | sections=1",
            packet["summary"]["focus_summary_line"],
        )
        self.assertEqual(
            "general_errors=4 | section_groups=1 | sections_with_errors=1",
            packet["summary"]["guidance_summary_line"],
        )
        self.assertIn("primary_focus_summary:", text)
        self.assertIn("primary_error_preview:", text)

    def test_draft_capacity_precheck_uses_current_focus_sections(self) -> None:
        self.paths["draft_capacity_contract"].write_text(
            json.dumps(
                {
                    "gate_status": "pending",
                    "target_words": 9000,
                    "outline": {"path": str(self.paths["outline"]), "sha256": "wrong"},
                    "sections": [
                        {
                            "id": "1",
                            "planned_words": 0,
                            "scene_completion": "",
                            "opening_or_turn": "",
                            "emotion_escalation": "",
                            "end_change": "",
                            "source_mechanism": "",
                            "source_style_granularity": "",
                            "first_draft_style_plan": "",
                        },
                        {
                            "id": "2",
                            "planned_words": 0,
                            "scene_completion": "",
                            "opening_or_turn": "",
                            "emotion_escalation": "",
                            "end_change": "",
                            "source_mechanism": "",
                            "source_style_granularity": "",
                            "first_draft_style_plan": "",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["outline"].write_text("## 1. 起事\n## 2. 失位\n", encoding="utf-8")
        self.paths["outline_repair_packet"].write_text(
            json.dumps(
                {
                    "focus_context": {"focus_section_ids": ["2"]},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_draft_capacity_precheck(
                self.paths,
                argparse.Namespace(),
            )

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("focus_sections: 2", text)
        self.assertIn("focus_section_2_capacity_gaps:", text)
        self.assertNotIn("focus_section_1_capacity_gaps:", text)

    def test_draft_capacity_init_reads_bullet_outline_sections(self) -> None:
        self.paths["outline"].write_text(
            "\n".join(
                [
                    "# 《门锁换了以后》小节大纲",
                    "",
                    "## 第1节 执法现场，他先护了她",
                    "",
                    "- 对应来源：",
                    "  - 主体 `SF-12`",
                    "  - 主体 `SF-13`",
                    "- 本节主事件：顾南枝在扫黄行动里撞见丈夫裴叙和女学生林知暖",
                    "- 本节开口：",
                    "  - 第一行直接写“我没想到扫黄会扫到我老公”",
                    "- 子事件：",
                    "  1. 顾南枝带队冲进包厢",
                    "  2. 裴叙抓住她制服替林知暖求情",
                    "- 冲突载体：",
                    "  - `dialogue`：师母、你先冷静",
                    "- 情绪过程：",
                    "  - 任务专注 -> 突然发冷 -> 强行控场",
                    "- 叙述者嘴感：",
                    "  - 现场要有短评句，例如“真行。”",
                    "- 节尾钩子：",
                    "  - 裴叙第一次主动给顾南枝打电话",
                    "- 相邻节交接：",
                    "  - 女主带着愤怒和不信进入核验态",
                ]
            ),
            encoding="utf-8",
        )

        receipt = TOOLBOX.DRAFT_CAPACITY.init(
            "测试项目",
            self.paths["outline"],
            9000,
        )

        section = receipt["sections"][0]
        self.assertEqual("顾南枝带队冲进包厢；裴叙抓住她制服替林知暖求情", section["scene_completion"])
        self.assertEqual("第一行直接写“我没想到扫黄会扫到我老公”", section["opening_or_turn"])
        self.assertEqual("任务专注 -> 突然发冷 -> 强行控场", section["emotion_escalation"])
        self.assertEqual("裴叙第一次主动给顾南枝打电话", section["end_change"])
        self.assertEqual("主体 `SF-12`；主体 `SF-13`", section["source_mechanism"])
        self.assertEqual("现场要有短评句，例如“真行。”", section["source_style_granularity"])
        self.assertEqual("现场要有短评句，例如“真行。”", section["first_draft_style_plan"])

    def test_draft_capacity_apply_merges_focus_sections(self) -> None:
        self.paths["draft_capacity_contract"].write_text(
            json.dumps(
                {
                    "gate_status": "passed",
                    "target_words": 9000,
                    "outline": {"path": str(self.paths["outline"]), "sha256": "ok"},
                    "sections": [
                        {
                            "id": "1",
                            "planned_words": 900,
                            "scene_completion": "旧1",
                            "opening_or_turn": "旧1",
                            "emotion_escalation": "旧1",
                            "end_change": "旧1",
                            "source_mechanism": "旧1",
                            "source_style_granularity": "旧1",
                            "first_draft_style_plan": "旧1",
                        },
                        {
                            "id": "2",
                            "planned_words": 900,
                            "scene_completion": "旧2",
                            "opening_or_turn": "旧2",
                            "emotion_escalation": "旧2",
                            "end_change": "旧2",
                            "source_mechanism": "旧2",
                            "source_style_granularity": "旧2",
                            "first_draft_style_plan": "旧2",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["outline"].write_text("## 1. 起事\n## 2. 失位\n", encoding="utf-8")
        with patch.object(TOOLBOX.DRAFT_CAPACITY, "validate_data", return_value=[]):
            packet = {
                "packet_sha256": "",
                "focus_section_ids": ["2"],
                "rerun_command": "draft-capacity-precheck",
                "summary": {
                    "primary_focus_summary": "contract=首写容量契约回执.json | sections=2",
                    "primary_error_preview": "第 2 节容量待修",
                    "focus_summary_line": "contract=首写容量契约回执.json | sections=2",
                    "guidance_summary_line": "general_errors=0 | section_groups=1 | sections_with_errors=1",
                },
            }
            packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
            self.paths["draft_capacity_packet"].write_text(
                json.dumps(packet, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.paths["draft_capacity_item_output"].write_text(
                json.dumps(
                    {
                        "gate_status": "passed",
                        "sections": [
                            {
                                "id": "2",
                                "planned_words": 1200,
                                "scene_completion": "新2",
                                "opening_or_turn": "新2",
                                "emotion_escalation": "新2",
                                "end_change": "新2",
                                "source_mechanism": "新2",
                                "source_style_granularity": "新2",
                                "first_draft_style_plan": "新2",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                result = TOOLBOX.command_draft_capacity_apply(
                    self.paths,
                    argparse.Namespace(packet_sha=packet["packet_sha256"]),
                )

        self.assertEqual(0, result)
        receipt = json.loads(self.paths["draft_capacity_contract"].read_text(encoding="utf-8"))
        self.assertEqual("passed", receipt["gate_status"])
        self.assertEqual("旧1", receipt["sections"][0]["scene_completion"])
        self.assertEqual("新2", receipt["sections"][1]["scene_completion"])
        self.assertIn("merge-updated-sections-into-draft-capacity-contract", output.getvalue())

    def test_draft_capacity_apply_refreshes_packet_when_merged_result_still_invalid(self) -> None:
        self.paths["draft_capacity_contract"].write_text(
            json.dumps(
                {
                    "gate_status": "pending",
                    "target_words": 9000,
                    "outline": {"path": str(self.paths["outline"]), "sha256": "bad"},
                    "sections": [{"id": "1", "planned_words": 0}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        packet = {
            "packet_sha256": "",
            "focus_section_ids": ["1"],
            "rerun_command": "draft-capacity-precheck",
            "summary": {
                "primary_focus_summary": "contract=首写容量契约回执.json | sections=1",
                "primary_error_preview": "第 1 节 planned_words 必须不少于 800",
                "focus_summary_line": "contract=首写容量契约回执.json | sections=1",
                "guidance_summary_line": "general_errors=0 | section_groups=1 | sections_with_errors=1",
            },
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["draft_capacity_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["draft_capacity_item_output"].write_text(
            json.dumps([{"id": "1", "planned_words": 500}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX.DRAFT_CAPACITY,
            "validate",
            return_value=["第 1 节 planned_words 必须不少于 800"],
        ), redirect_stdout(output):
            result = TOOLBOX.command_draft_capacity_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        self.assertEqual(2, result)
        text = output.getvalue()
        self.assertIn("project_toolbox: draft-capacity-apply blocked", text)
        self.assertIn("repair_packet:", text)
        self.assertIn("next_apply_command: draft-capacity-apply --packet-sha", text)

    def test_draft_capacity_precheck_sanitizes_existing_repair_output_when_preserving(self) -> None:
        self.paths["draft_capacity_contract"].write_text(
            json.dumps(
                {
                    "gate_status": "pending",
                    "target_words": 9000,
                    "outline": {"path": str(self.paths["outline"]), "sha256": "bad"},
                    "sections": [
                        {
                            "id": "1",
                            "planned_words": 0,
                            "scene_completion": "",
                            "opening_or_turn": "",
                            "emotion_escalation": "",
                            "end_change": "",
                            "source_mechanism": "",
                            "source_style_granularity": "",
                            "first_draft_style_plan": "",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["draft_capacity_item_output"].write_text(
            json.dumps(
                {"gate_status": "passed", "sections": ["坏格式小节"]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        TOOLBOX.export_draft_capacity_packet(
            self.paths,
            ["第 1 节 planned_words 必须不少于 800"],
            "draft-capacity-precheck",
            preserve_existing_output=True,
        )

        repair_template = json.loads(
            self.paths["draft_capacity_item_output"].read_text(encoding="utf-8")
        )
        self.assertEqual("passed", repair_template["gate_status"])
        self.assertTrue(all(isinstance(item, dict) for item in repair_template["sections"]))

    def test_opening_precheck_exports_repair_packet(self) -> None:
        self.paths["opening_contract"].write_text(
            json.dumps(
                {
                    "primary_source": {"path": str(self.project / "missing-source.txt")},
                    "target_text": {"path": str(self.paths["outline"])},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_opening_precheck(self.paths, argparse.Namespace())

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("project_toolbox: opening-precheck blocked", text)
        self.assertTrue(self.paths["opening_repair_packet"].is_file())
        self.assertTrue(self.paths["opening_repair_item_output"].is_file())
        packet = json.loads(self.paths["opening_repair_packet"].read_text(encoding="utf-8"))
        self.assertEqual("opening_repair_packet", packet["kind"])
        self.assertIn("summary", packet)
        self.assertIn("primary_focus_summary", packet["summary"])
        self.assertIn("primary_error_preview", packet["summary"])
        self.assertEqual("receipt=开头承重契约回执.json", packet["summary"]["focus_summary_line"])
        self.assertEqual(
            "errors=2 | first_error=主体导语资产不存在: "
            + str((self.project / "missing-source.txt").resolve()),
            packet["summary"]["guidance_summary_line"],
        )
        repair_template = json.loads(self.paths["opening_repair_item_output"].read_text(encoding="utf-8"))
        self.assertEqual(
            {"path", "sha256", "opening_quote", "opening_pattern"},
            set(repair_template["original_opening_comparison"]["samples"][0].keys()),
        )
        self.assertEqual(
            list(TOOLBOX.OPENING_CONTRACT.REQUIRED_CHECKS),
            [item["check_id"] for item in repair_template["target_evidence"]],
        )
        self.assertIn("primary_focus_summary:", text)
        self.assertIn("primary_error_preview:", text)
        self.assertIn("completion_state: continue_required_until_start-draft", text)
        self.assertIn("opening-apply --packet-sha", text)

    def test_opening_precheck_sanitizes_existing_repair_output_when_preserving(self) -> None:
        self.paths["opening_contract"].write_text(
            json.dumps(
                {
                    "primary_source": {"path": str(self.project / "missing-source.txt")},
                    "target_text": {"path": str(self.paths["outline"])},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["opening_repair_item_output"].write_text(
            json.dumps(
                {
                    "source_evidence": ["坏格式证据"],
                    "target_evidence": ["坏格式目标证据"],
                    "checks": {},
                    "gate_status": "passed",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        TOOLBOX.export_opening_repair_packet(
            self.paths,
            [f"主体导语资产不存在: {(self.project / 'missing-source.txt').resolve()}"],
            "opening-precheck",
            preserve_existing_output=True,
        )

        repair_template = json.loads(
            self.paths["opening_repair_item_output"].read_text(encoding="utf-8")
        )
        self.assertEqual(
            list(TOOLBOX.OPENING_CONTRACT.REQUIRED_CHECKS),
            [item["check_id"] for item in repair_template["target_evidence"]],
        )
        self.assertTrue(all(isinstance(item, dict) for item in repair_template["source_evidence"]))

    def test_opening_repair_packet_reuses_existing_packet_when_error_context_unchanged(self) -> None:
        self.paths["opening_contract"].write_text(
            json.dumps(
                {
                    "primary_source": {"path": str(self.project / "missing-source.txt")},
                    "target_text": {"path": str(self.paths["outline"])},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        packet1 = TOOLBOX.export_opening_repair_packet(
            self.paths,
            [f"主体导语资产不存在: {(self.project / 'missing-source.txt').resolve()}"],
            "opening-precheck",
            preserve_existing_output=True,
            emit_output=False,
        )
        packet2 = TOOLBOX.export_opening_repair_packet(
            self.paths,
            [f"主体导语资产不存在: {(self.project / 'missing-source.txt').resolve()}"],
            "opening-precheck",
            preserve_existing_output=True,
            emit_output=False,
        )
        self.assertEqual(packet1["packet_sha256"], packet2["packet_sha256"])
        stored = json.loads(self.paths["opening_repair_packet"].read_text(encoding="utf-8"))
        self.assertEqual(packet1["packet_sha256"], stored["packet_sha256"])

    def test_opening_apply_writes_back_and_requests_rerun(self) -> None:
        receipt = {
            "gate_status": "pending",
            "primary_source": {"path": str(self.project / "source.txt")},
            "target_text": {"path": str(self.paths["outline"])},
        }
        self.paths["opening_contract"].write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        packet = {
            "packet_sha256": "",
            "receipt_sha256": TOOLBOX.file_sha256(self.paths["opening_contract"]),
            "rerun_command": "opening-precheck",
            "summary": {
                "primary_focus_summary": "receipt=开头承重契约回执.json",
                "primary_error_preview": "开头待修",
                "focus_summary_line": "receipt=开头承重契约回执.json",
                "guidance_summary_line": "errors=1",
            },
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["opening_repair_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["opening_repair_item_output"].write_text(
            json.dumps({"gate_status": "passed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "validate_opening_receipt_data",
            return_value=[],
        ), redirect_stdout(output):
            result = TOOLBOX.command_opening_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        self.assertEqual(0, result)
        receipt = json.loads(self.paths["opening_contract"].read_text(encoding="utf-8"))
        self.assertEqual("passed", receipt["gate_status"])
        self.assertIn("rerun-opening-precheck", output.getvalue())
        self.assertIn("next_action: 当前修闸包已成功写回正式回执；", output.getvalue())

    def test_sequence_precheck_exports_repair_packet(self) -> None:
        self.paths["sequence_receipt"].write_text(
            json.dumps(
                {
                    "artifacts": {
                        "setting": {"path": str(self.project / "missing-setting.md")},
                        "outline": {"path": str(self.paths["outline"])},
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_sequence_precheck(self.paths, argparse.Namespace())

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("project_toolbox: sequence-precheck blocked", text)
        self.assertTrue(self.paths["sequence_repair_packet"].is_file())
        self.assertTrue(self.paths["sequence_repair_item_output"].is_file())
        packet = json.loads(self.paths["sequence_repair_packet"].read_text(encoding="utf-8"))
        self.assertEqual("sequence_repair_packet", packet["kind"])
        self.assertIn("summary", packet)
        self.assertIn("primary_focus_summary", packet["summary"])
        self.assertIn("primary_error_preview", packet["summary"])
        self.assertEqual("receipt=顺序契约回执.json", packet["summary"]["focus_summary_line"])
        self.assertEqual(
            "errors=9 | first_error=设定—大纲—正文顺序契约 scope 必须为 full",
            packet["summary"]["guidance_summary_line"],
        )
        repair_template = json.loads(self.paths["sequence_repair_item_output"].read_text(encoding="utf-8"))
        self.assertEqual([], repair_template["canonical_sequence"])
        self.assertEqual({"status", "findings"}, set(repair_template["conflict_review"].keys()))
        self.assertIn("primary_focus_summary:", text)
        self.assertIn("primary_error_preview:", text)
        self.assertIn("completion_state: continue_required_until_start-draft", text)
        self.assertIn("sequence-apply --packet-sha", text)

    def test_sequence_precheck_sanitizes_existing_repair_output_when_preserving(self) -> None:
        self.paths["sequence_receipt"].write_text(
            json.dumps(
                {
                    "artifacts": {
                        "setting": {"path": str(self.project / "missing-setting.md")},
                        "outline": {"path": str(self.paths["outline"])},
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["sequence_repair_item_output"].write_text(
            json.dumps(
                {
                    "canonical_sequence": ["坏格式节点"],
                    "conflict_review": {"findings": ["坏格式冲突"]},
                    "gate_status": "passed",
                    "status": "completed",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        TOOLBOX.export_sequence_repair_packet(
            self.paths,
            ["设定—大纲—正文顺序契约 scope 必须为 full"],
            "sequence-precheck",
            preserve_existing_output=True,
        )

        repair_template = json.loads(
            self.paths["sequence_repair_item_output"].read_text(encoding="utf-8")
        )
        self.assertEqual("passed", repair_template["gate_status"])
        self.assertEqual("completed", repair_template["status"])
        self.assertTrue(all(isinstance(item, dict) for item in repair_template["canonical_sequence"]))
        self.assertTrue(
            all(isinstance(item, dict) for item in repair_template["conflict_review"]["findings"])
        )

    def test_refresh_draft_prereq_packets_exports_sequence_packet_for_pending_receipt(self) -> None:
        self.paths["sequence_receipt"].write_text(
            json.dumps(
                {
                    "scope": "full",
                    "gate_status": "pending",
                    "status": "pending",
                    "artifacts": {
                        "setting": {"path": str(self.project / "missing-setting.md")},
                        "outline": {"path": str(self.paths["outline"])},
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        TOOLBOX.refresh_draft_prereq_packets(
            self.paths,
            ["顺序契约门禁未通过"],
            command_reasons=[("sequence-precheck", ["顺序契约门禁未通过"])],
        )

        self.assertTrue(self.paths["sequence_repair_packet"].is_file())
        self.assertTrue(self.paths["sequence_repair_item_output"].is_file())

    def test_sequence_apply_writes_back_and_requests_rerun(self) -> None:
        receipt = {
            "gate_status": "pending",
            "artifacts": {
                "setting": {"path": str(self.project / "setting.md")},
                "outline": {"path": str(self.paths["outline"])},
            },
        }
        self.paths["sequence_receipt"].write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        packet = {
            "packet_sha256": "",
            "receipt_sha256": TOOLBOX.file_sha256(self.paths["sequence_receipt"]),
            "rerun_command": "sequence-precheck",
            "summary": {
                "primary_focus_summary": "receipt=顺序契约回执.json",
                "primary_error_preview": "顺序待修",
                "focus_summary_line": "receipt=顺序契约回执.json",
                "guidance_summary_line": "errors=1",
            },
        }
        packet["packet_sha256"] = TOOLBOX.json_sha256(packet)
        self.paths["sequence_repair_packet"].write_text(
            json.dumps(packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["sequence_repair_item_output"].write_text(
            json.dumps({"gate_status": "passed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "validate_sequence_receipt_data",
            return_value=[],
        ), redirect_stdout(output):
            result = TOOLBOX.command_sequence_apply(
                self.paths,
                argparse.Namespace(packet_sha=packet["packet_sha256"]),
            )

        self.assertEqual(0, result)
        receipt = json.loads(self.paths["sequence_receipt"].read_text(encoding="utf-8"))
        self.assertEqual("passed", receipt["gate_status"])
        self.assertIn("rerun-sequence-precheck", output.getvalue())
        self.assertIn("next_action: 当前修闸包已成功写回正式回执；", output.getvalue())

    def test_prepare_outline_repair_item_output_keeps_existing_file_when_packet_missing(self) -> None:
        TOOLBOX.atomic_write_json_value(self.paths["outline_repair_item_output"], [{"section_id": "1"}])

        TOOLBOX.prepare_outline_repair_item_output(self.paths["outline_repair_item_output"], None)

        self.assertTrue(self.paths["outline_repair_item_output"].is_file())
        self.assertEqual(
            [{"section_id": "1"}],
            json.loads(self.paths["outline_repair_item_output"].read_text(encoding="utf-8")),
        )

    def test_prepare_outline_repair_item_output_preserves_existing_fields_when_requested(self) -> None:
        packet = {"receipt_key": "sections", "focus_context": {"focus_section_ids": ["1"]}}
        self.paths["outline_contract"].write_text(
            json.dumps(
                {
                    "sections": [
                        {
                            "section_id": "1",
                            "verdict": "pending",
                            "scene_logic_contract": {
                                "scene_entry_state": "",
                                "scene_exit_state": "",
                            },
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps(
                [
                    {
                        "section_id": "1",
                        "verdict": "passed",
                        "scene_logic_contract": {
                            "scene_entry_state": "旧入口状态",
                            "scene_exit_state": "",
                        },
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        TOOLBOX.prepare_outline_repair_item_output(
            self.paths["outline_repair_item_output"],
            packet,
            result_template=TOOLBOX.outline_repair_template_from_packet(self.paths, packet),
            preserve_existing=True,
        )

        merged = json.loads(self.paths["outline_repair_item_output"].read_text(encoding="utf-8"))
        self.assertEqual("passed", merged[0]["verdict"])
        self.assertEqual("旧入口状态", merged[0]["scene_logic_contract"]["scene_entry_state"])

    def test_candidate_subflows_returns_compact_ranked_results(self) -> None:
        library = self.project / "资料库" / "子流程总索引.jsonl"
        library.parent.mkdir(parents=True)
        entries = [
            {
                "global_subflow_id": "主体::SF-01",
                "source_book": "主体",
                "subflow_id": "SF-01",
                "name": "主体追妻",
                "function_tags": ["追妻"],
                "required_sequence": ["道歉"],
                "emotion_sequence": ["痛苦"],
                "end_state": "失败",
                "source_style_granularity": {"large": "不应输出"},
            },
            {
                "global_subflow_id": "辅助::SF-02",
                "source_book": "辅助",
                "subflow_id": "SF-02",
                "name": "高成本追妻失败",
                "function_tags": ["追妻", "补救"],
                "required_sequence": ["劳动补救", "再次选错"],
                "emotion_sequence": ["希望", "反刀"],
                "end_state": "追妻失败",
                "source_style_granularity": {"large": "不应输出"},
            },
        ]
        library.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in entries) + "\n",
            encoding="utf-8",
        )
        candidates, errors = TOOLBOX.load_subflow_candidates(
            library,
            ["追妻", "补救"],
            {"主体"},
            5,
        )
        self.assertEqual([], errors)
        self.assertEqual(["辅助::SF-02"], [item["global_subflow_id"] for item in candidates])
        self.assertNotIn("source_style_granularity", candidates[0])

    def test_candidate_subflows_accepts_fixed_index_query_form(self) -> None:
        library = self.project / "资料库" / "子流程总索引.jsonl"
        library.parent.mkdir(parents=True)
        library.write_text(
            json.dumps(
                {
                    "global_subflow_id": "辅助::SF-01",
                    "source_book": "辅助",
                    "subflow_id": "SF-01",
                    "name": "低位补救失败",
                    "function_tags": ["追妻"],
                    "required_sequence": ["补救", "再次选错"],
                    "emotion_sequence": ["希望", "反刀"],
                    "end_state": "失去资格",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        parser = TOOLBOX.build_parser()
        args = parser.parse_args(
            [
                "candidate-subflows",
                "--index",
                str(library),
                "--query",
                "追妻 补救",
            ]
        )
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "candidate_source_readiness",
            return_value=(True, ""),
        ), redirect_stdout(output):
            result = args.func(args)
        self.assertEqual(0, result)
        self.assertIn("辅助::SF-01", output.getvalue())
        self.assertIn('"source_status": "ready"', output.getvalue())

    def test_expand_subflow_keywords_adds_aliases_without_duplication(self) -> None:
        expanded = TOOLBOX.expand_subflow_keywords(["强情绪", "追妻", "追妻"])

        self.assertEqual("强情绪", expanded[0])
        self.assertIn("崩溃", expanded)
        self.assertIn("补救", expanded)
        self.assertEqual(1, expanded.count("追妻"))

    def test_expand_subflow_keywords_decomposes_compound_chinese_query(self) -> None:
        expanded = TOOLBOX.expand_subflow_keywords(
            ["强情绪追妻", "男主失位补救失败"]
        )

        self.assertIn("强情绪", expanded)
        self.assertIn("追妻", expanded)
        self.assertIn("失位补救", expanded)
        self.assertIn("崩溃", expanded)
        self.assertIn("追不回", expanded)

    def test_candidate_subflows_matches_abstract_query_via_aliases_and_extended_fields(
        self,
    ) -> None:
        library = self.project / "资料库" / "子流程总索引.jsonl"
        library.parent.mkdir(parents=True)
        library.write_text(
            json.dumps(
                {
                    "global_subflow_id": "辅助::SF-09",
                    "source_book": "辅助",
                    "subflow_id": "SF-09",
                    "name": "伴侣缺席后的补救失败",
                    "function_tags": ["关系后果"],
                    "required_sequence": ["现实后果落地"],
                    "emotion_sequence": ["落空9", "反刀9"],
                    "end_state": "失去资格",
                    "entry_state": "男友缺席后，主角已经不再相信口头承诺。",
                    "control_changes": ["男主试图低位补救，但边界已被外人占住"],
                    "information_delay": "先保留婚姻表面，再让越界事实一层层露出来。",
                    "scene_granularity": "大哭之后回家，看见外套还挂在玄关。",
                    "source_evidence": ["你现在补救，晚了。"],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        candidates, errors = TOOLBOX.load_subflow_candidates(
            library,
            ["强情绪", "追妻", "失位补救", "边界拉扯", "误会婚恋"],
            set(),
            5,
        )

        self.assertEqual([], errors)
        self.assertEqual(["辅助::SF-09"], [item["global_subflow_id"] for item in candidates])

    def test_candidate_subflows_prints_deterministic_next_allocate_command(
        self,
    ) -> None:
        args = argparse.Namespace(
            library=str(self.project / "index.jsonl"),
            query="追妻",
            keyword=[],
            exclude_source=[],
            limit=8,
            project_root=str(Path(self.temp.name) / "workspace"),
            project_name="新书",
            primary_source_dir=str(self.project / "主体"),
        )
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "load_subflow_candidates",
            return_value=([], []),
        ), redirect_stdout(output):
            result = TOOLBOX.command_candidate_subflows(args)

        self.assertEqual(0, result)
        self.assertIn("next_allocate_command:", output.getvalue())
        self.assertIn("allocate-project", output.getvalue())
        self.assertIn("--source-dir", output.getvalue())

    def test_export_source_review_reuses_finalized_source_stage(self) -> None:
        args = argparse.Namespace(output=None, force=False, print_task=False)
        self.paths["source_semantic_input"].write_text("{}", encoding="utf-8")
        self.paths["source_semantic_output"].write_text("{}", encoding="utf-8")
        output = StringIO()

        with patch.object(
            TOOLBOX.SOURCE_READ,
            "validate_receipt",
            return_value=([], {}),
        ), redirect_stdout(output):
            result = TOOLBOX.command_export_source_review(self.paths, args)

        self.assertEqual(0, result)
        text = output.getvalue()
        self.assertIn("project_toolbox: export-source-review passed", text)
        self.assertIn("reuse-existing-source-read-receipt", text)
        self.assertIn("禁止回退到来源语义任务入口", text)

    def test_source_review_next_reuses_finalized_source_stage(self) -> None:
        args = argparse.Namespace(input=None)
        output = StringIO()

        with patch.object(
            TOOLBOX.SOURCE_READ,
            "validate_receipt",
            return_value=([], {}),
        ), redirect_stdout(output):
            result = TOOLBOX.command_source_review_next(self.paths, args)

        self.assertEqual(0, result)
        text = output.getvalue()
        self.assertIn("project_toolbox: source-review-next passed", text)
        self.assertIn("reuse-existing-source-read-receipt", text)
        self.assertIn("validate-prewrite-reads / prepare-setting", text)
        self.assertIn("prepare-draft-gates / start-draft", text)

    def test_export_source_review_auto_finalizes_pending_direct_imitation_receipt(self) -> None:
        args = argparse.Namespace(output=None, force=False, print_task=False)
        output = StringIO()

        with patch.object(
            TOOLBOX.SOURCE_READ,
            "validate_receipt",
            side_effect=[
                (["pending"], {}),
                ([], {}),
            ],
        ), patch.object(
            TOOLBOX,
            "auto_finalize_direct_imitation_source_stage",
            return_value=([], ["auto-finalize-direct-imitation-source-stage"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_export_source_review(self.paths, args)

        self.assertEqual(0, result)
        text = output.getvalue()
        self.assertIn("auto-finalize-direct-imitation-source-stage", text)
        self.assertIn("deprecated-for-direct-imitation", text)

    def test_rule_review_next_prefills_current_item_output(self) -> None:
        args = argparse.Namespace(input=None)
        task = {
            "kind": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_KIND,
            "version": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "receipt": {"sha256": "receipt-sha"},
        }
        packet = {
            "task_sha256": "task-sha",
            "receipt_sha256": "receipt-sha",
            "packet_sha256": "packet-sha",
            "file": {
                "path": "references/a.md",
                "segment_index": 1,
                "segment_count": 1,
                "segment_title": "A",
                "content": "证据甲 证据乙",
            },
            "result_template": {
                "version": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_VERSION,
                "kind": TOOLBOX.RULE_REVIEW_ITEM_RESULT_KIND,
                "task_sha256": "task-sha",
                "receipt_sha256": "receipt-sha",
                "packet_sha256": "packet-sha",
                "path": "references/a.md",
                "segment_index": 1,
                "segment_count": 1,
                "review": {
                    "status": "read",
                    "evidence_terms": [],
                    "takeaways": [],
                    "used_for": [],
                },
            },
        }
        self.paths["writing_rule_input"].write_text("{}", encoding="utf-8")
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "read_json",
            return_value=task,
        ), patch.object(
            TOOLBOX,
            "rule_review_task_items",
            return_value=([{"path": "references/a.md"}], []),
        ), patch.object(
            TOOLBOX,
            "validate_rule_review_task_binding",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "read_rule_review_progress",
            return_value=(
                {
                    "kind": TOOLBOX.WRITING_RULE.RULE_REVIEW_RESULT_KIND,
                    "version": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_VERSION,
                    "task_sha256": "task-sha",
                    "receipt_sha256": "receipt-sha",
                    "reviews": [],
                    "packet_reviews": [],
                },
                [],
            ),
        ), patch.object(
            TOOLBOX,
            "validate_rule_review_progress_items",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "validate_rule_review_packet_progress",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "next_pending_rule_review_packet",
            return_value=({"path": "references/a.md"}, packet),
        ), redirect_stdout(output):
            result = TOOLBOX.command_rule_review_next(self.paths, args)

        self.assertEqual(0, result)
        item_output = TOOLBOX.read_json(self.paths["writing_rule_item_output"])
        self.assertEqual("packet-sha", item_output["packet_sha256"])
        self.assertIn("当前规则语义回执.json", output.getvalue())
        self.assertIn("rule_review_item_binding:", output.getvalue())
        self.assertIn("rule_review_item_edit_scope:", output.getvalue())
        self.assertIn("result_template 已原子预写", output.getvalue())
        self.assertIn("禁止再 cat/jq/sed", output.getvalue())

    def test_rule_review_packets_include_evidence_candidates_and_prefill_terms(self) -> None:
        task_path = self.project / "写作资产" / "规则语义输入.json"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        TOOLBOX.atomic_write_json(task_path, {"receipt": {"sha256": "receipt-sha"}})

        packets = TOOLBOX.rule_review_packets_for_item(
            task_path,
            {"receipt": {"sha256": "receipt-sha"}},
            {
                "path": "references/a.md",
                "sha256": "rule-sha",
                "content": "# 标题\n\n- 证据条目\n\n这里有 `规则片段` 和 **加粗证据**。\n",
                "review": {
                    "status": "read",
                    "evidence_terms": [],
                    "takeaways": [],
                    "used_for": [],
                },
            },
        )

        self.assertEqual(1, len(packets))
        self.assertTrue(packets[0]["evidence_term_candidates"])
        self.assertEqual(
            packets[0]["evidence_term_candidates"][:2],
            packets[0]["result_template"]["review"]["evidence_terms"],
        )
        self.assertIn("- 证据条目", packets[0]["evidence_term_candidates"])

    def test_apply_rule_review_item_prefills_next_packet_template(self) -> None:
        args = argparse.Namespace(
            input=None,
            result=None,
            packet_sha="packet-1",
        )
        task = {
            "kind": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_KIND,
            "version": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "receipt": {"sha256": "receipt-sha"},
        }
        item = {
            "version": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "kind": TOOLBOX.RULE_REVIEW_ITEM_RESULT_KIND,
            "task_sha256": "task-sha",
            "receipt_sha256": "receipt-sha",
            "packet_sha256": "packet-1",
            "path": "references/a.md",
            "segment_index": 1,
            "segment_count": 1,
            "review": {
                "status": "read",
                "evidence_terms": ["证据甲"],
                "takeaways": ["要点甲"],
                "used_for": ["用途甲"],
            },
        }
        next_packet = {
            "task_sha256": "task-sha",
            "receipt_sha256": "receipt-sha",
            "packet_sha256": "packet-2",
            "file": {
                "path": "references/b.md",
                "segment_index": 1,
                "segment_count": 1,
                "segment_title": "B",
                "content": "证据乙",
            },
            "result_template": {
                "version": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_VERSION,
                "kind": TOOLBOX.RULE_REVIEW_ITEM_RESULT_KIND,
                "task_sha256": "task-sha",
                "receipt_sha256": "receipt-sha",
                "packet_sha256": "packet-2",
                "path": "references/b.md",
                "segment_index": 1,
                "segment_count": 1,
                "review": {
                    "status": "read",
                    "evidence_terms": [],
                    "takeaways": [],
                    "used_for": [],
                },
            },
        }
        self.paths["writing_rule_input"].write_text("{}", encoding="utf-8")
        TOOLBOX.atomic_write_json(self.paths["writing_rule_item_output"], item)
        progress = {
            "kind": TOOLBOX.WRITING_RULE.RULE_REVIEW_RESULT_KIND,
            "version": TOOLBOX.WRITING_RULE.RULE_REVIEW_TASK_VERSION,
            "task_sha256": "task-sha",
            "receipt_sha256": "receipt-sha",
            "reviews": [],
            "packet_reviews": [],
        }
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "read_json",
            side_effect=[task, item],
        ), patch.object(
            TOOLBOX,
            "rule_review_task_items",
            return_value=([{"path": "references/a.md"}, {"path": "references/b.md"}], []),
        ), patch.object(
            TOOLBOX,
            "validate_rule_review_task_binding",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "read_rule_review_progress",
            return_value=(progress, []),
        ), patch.object(
            TOOLBOX,
            "validate_rule_review_progress_items",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "validate_rule_review_packet_progress",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "rule_review_packets_for_item",
            return_value=[
                {
                    "task_sha256": "task-sha",
                    "receipt_sha256": "receipt-sha",
                    "packet_sha256": "packet-1",
                    "file": {
                        "path": "references/a.md",
                        "segment_index": 1,
                        "segment_count": 1,
                        "segment_title": "A",
                        "content": "证据甲",
                    },
                }
            ],
        ), patch.object(
            TOOLBOX,
            "validate_rule_review_evidence_terms",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "next_pending_rule_review_packet",
            return_value=({"path": "references/b.md"}, next_packet),
        ), redirect_stdout(output):
            result = TOOLBOX.command_apply_rule_review_item(self.paths, args)

        self.assertEqual(0, result)
        item_output = TOOLBOX.read_json(self.paths["writing_rule_item_output"])
        self.assertEqual("packet-2", item_output["packet_sha256"])
        self.assertIn("再次运行 rule-review-next", output.getvalue())
        self.assertIn("rule_review_item_binding:", output.getvalue())

    def test_candidate_subflows_uses_working_name_when_project_name_is_placeholder(
        self,
    ) -> None:
        args = argparse.Namespace(
            library=str(self.project / "index.jsonl"),
            query="强情绪 追妻 火葬场",
            keyword=[],
            exclude_source=[],
            limit=8,
            project_root=str(Path(self.temp.name) / "workspace"),
            project_name="待定",
            primary_source_dir=str(self.project / "扫黄扫到了我老公"),
        )
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "load_subflow_candidates",
            return_value=([], []),
        ), redirect_stdout(output):
            result = TOOLBOX.command_candidate_subflows(args)

        self.assertEqual(0, result)
        self.assertIn("next_allocate_command:", output.getvalue())
        self.assertIn("working_project_name:", output.getvalue())
        self.assertIn("强情绪追妻火葬场", output.getvalue())
        self.assertNotIn("--name 待定", output.getvalue())
        self.assertNotIn("扫黄扫到了我老公-强情绪-追妻-工作稿", output.getvalue())

    def test_candidate_subflows_filters_stale_source_before_init(self) -> None:
        args = argparse.Namespace(
            library=str(self.project / "index.jsonl"),
            query="追妻",
            keyword=[],
            exclude_source=[],
            limit=8,
        )
        candidates = [
            {
                "global_subflow_id": "过期书::SF-01",
                "source_book": "过期书",
                "source_dir": str(self.project / "过期书"),
                "subflow_id": "SF-01",
            }
        ]
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "load_subflow_candidates",
            return_value=(candidates, []),
        ), patch.object(
            TOOLBOX,
            "candidate_source_readiness",
            return_value=(False, "仿写包已过期"),
        ), redirect_stdout(output):
            result = TOOLBOX.command_candidate_subflows(args)
        self.assertEqual(0, result)
        self.assertIn("unavailable: 过期书::SF-01", output.getvalue())
        self.assertNotIn('"global_subflow_id": "过期书::SF-01"', output.getvalue())
        self.assertIn(
            "candidate_fallback: primary-only-no-auto-analyze",
            output.getvalue(),
        )
        self.assertIn("禁止自动调用 story-short-analyze", output.getvalue())

    def test_candidate_subflows_required_auxiliary_blocks_primary_only_fallback(
        self,
    ) -> None:
        args = argparse.Namespace(
            library=str(self.project / "index.jsonl"),
            query="强情绪追妻",
            keyword=[],
            exclude_source=["主体"],
            limit=8,
            project_root=str(self.project.parent),
            project_name="新书",
            primary_source_dir=str(self.project / "主体"),
            require_auxiliary=True,
            auxiliary_source_count=2,
        )
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "load_subflow_candidates",
            return_value=([], []),
        ), redirect_stdout(output):
            result = TOOLBOX.command_candidate_subflows(args)

        self.assertEqual(2, result)
        self.assertIn("禁止降级为仅主体", output.getvalue())
        self.assertNotIn("next_allocate_command:", output.getvalue())

    def test_candidate_subflows_required_auxiliary_binds_distinct_sources_to_init(
        self,
    ) -> None:
        primary = self.project / "主体"
        auxiliary_a = self.project / "辅助甲"
        auxiliary_b = self.project / "辅助乙"
        args = argparse.Namespace(
            library=str(self.project / "index.jsonl"),
            query="强情绪追妻",
            keyword=[],
            exclude_source=["主体"],
            limit=8,
            project_root=str(self.project.parent),
            project_name="新书",
            primary_source_dir=str(primary),
            require_auxiliary=True,
            auxiliary_source_count=2,
        )
        candidates = [
            {
                "global_subflow_id": "辅助甲::SF-03",
                "source_book": "辅助甲",
                "source_dir": str(auxiliary_a),
                "subflow_id": "SF-03",
            },
            {
                "global_subflow_id": "辅助乙::SF-07",
                "source_book": "辅助乙",
                "source_dir": str(auxiliary_b),
                "subflow_id": "SF-07",
            },
        ]
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "load_subflow_candidates",
            return_value=(candidates, []),
        ), patch.object(
            TOOLBOX,
            "candidate_source_readiness",
            return_value=(True, ""),
        ), redirect_stdout(output):
            result = TOOLBOX.command_candidate_subflows(args)

        text = output.getvalue()
        self.assertEqual(0, result)
        self.assertIn(f"--source-dir '{auxiliary_a.resolve()}'", text)
        self.assertIn(f"--source-dir '{auxiliary_b.resolve()}'", text)
        self.assertIn("--select-subflow '辅助甲=SF-03'", text)
        self.assertIn("--select-subflow '辅助乙=SF-07'", text)
        self.assertIn("辅助来源与 SF 已绑定", text)

    def test_candidate_subflows_fills_limit_after_filtering_and_caches_by_source(
        self,
    ) -> None:
        args = argparse.Namespace(
            library=str(self.project / "index.jsonl"),
            query="追妻",
            keyword=[],
            exclude_source=[],
            limit=2,
        )
        candidates = [
            {
                "global_subflow_id": "过期书::SF-01",
                "source_book": "过期书",
                "source_dir": str(self.project / "过期书"),
                "subflow_id": "SF-01",
            },
            {
                "global_subflow_id": "过期书::SF-02",
                "source_book": "过期书",
                "source_dir": str(self.project / "过期书"),
                "subflow_id": "SF-02",
            },
            {
                "global_subflow_id": "可用甲::SF-01",
                "source_book": "可用甲",
                "source_dir": str(self.project / "可用甲"),
                "subflow_id": "SF-01",
            },
            {
                "global_subflow_id": "可用乙::SF-01",
                "source_book": "可用乙",
                "source_dir": str(self.project / "可用乙"),
                "subflow_id": "SF-01",
            },
        ]

        def readiness(
            candidate: dict[str, object],
            base_readiness: tuple[bool, str],
        ) -> tuple[bool, str]:
            if not base_readiness[0]:
                return base_readiness
            return (
                (False, "仿写包已过期")
                if candidate["source_book"] == "过期书"
                else (True, "")
            )

        output = StringIO()
        with patch.object(
            TOOLBOX,
            "load_subflow_candidates",
            return_value=(candidates, []),
        ) as load_candidates, patch.object(
            TOOLBOX,
            "candidate_source_base_readiness",
            side_effect=lambda candidate: (
                (False, "仿写包已过期")
                if candidate["source_book"] == "过期书"
                else (True, "")
            ),
        ) as base_readiness, patch.object(
            TOOLBOX,
            "candidate_source_readiness",
            side_effect=readiness,
        ) as source_readiness, redirect_stdout(output):
            result = TOOLBOX.command_candidate_subflows(args)

        self.assertEqual(0, result)
        load_candidates.assert_called_once_with(
            Path(args.library).resolve(),
            ["追妻"],
            set(),
            8,
        )
        self.assertEqual(3, base_readiness.call_count)
        self.assertEqual(4, source_readiness.call_count)
        self.assertIn('"global_subflow_id": "可用甲::SF-01"', output.getvalue())
        self.assertIn('"global_subflow_id": "可用乙::SF-01"', output.getvalue())

    def test_candidate_source_readiness_rejects_legacy_index_without_paths(
        self,
    ) -> None:
        ready, reason = TOOLBOX.candidate_source_readiness(
            {
                "global_subflow_id": "旧书::SF-01",
                "source_book": "旧书",
            }
        )

        self.assertFalse(ready)
        self.assertIn("必须重新 finalize 拆书", reason)

    def test_candidate_source_readiness_validates_only_current_subflow_style(
        self,
    ) -> None:
        candidate = {
            "global_subflow_id": "辅助::SF-02",
            "source_book": "辅助",
            "source_dir": str(self.project / "辅助"),
            "source_index_path": str(
                self.project / "辅助" / "写作资产" / "子流程索引.jsonl"
            ),
            "subflow_id": "SF-02",
        }
        with patch.object(
            TOOLBOX.SOURCE_READ,
            "validate_direct_imitation_candidate_style",
            return_value=["SF-02.source_style_granularity 证据不足"],
        ) as validate_style:
            ready, reason = TOOLBOX.candidate_source_readiness(
                candidate,
                (True, ""),
            )

        self.assertFalse(ready)
        self.assertIn("SF-02", reason)
        validate_style.assert_called_once_with(
            Path(candidate["source_dir"]).resolve(),
            "SF-02",
        )

    def test_candidate_subflows_blocks_oversized_output(self) -> None:
        args = argparse.Namespace(
            library=str(self.project / "missing.jsonl"),
            query="追妻",
            keyword=[],
            exclude_source=[],
            limit=20,
        )
        output = StringIO()
        with redirect_stdout(output):
            result = TOOLBOX.command_candidate_subflows(args)
        self.assertEqual(2, result)
        self.assertIn("--limit 不得超过 12", output.getvalue())

    def test_preflight_reuses_content_fingerprint_cache(self) -> None:
        dependency = self.project / "dependency.txt"
        dependency.write_text("same", encoding="utf-8")
        fingerprint = {str(dependency.resolve()): TOOLBOX.file_sha256(dependency)}
        TOOLBOX.atomic_write_json(
            self.paths["preflight_cache"],
            {
                "version": TOOLBOX.CACHE_VERSION,
                "gate_status": "passed",
                "dependencies": fingerprint,
            },
        )
        with patch.object(
            TOOLBOX,
            "dependency_paths",
            return_value=([dependency], []),
        ), patch.object(TOOLBOX.WRITING_RULE, "validate_receipt") as writing_validate:
            errors, actions = TOOLBOX.run_preflight(self.paths, force=False)
        self.assertEqual([], errors)
        self.assertEqual(["reuse-mechanical-preflight-cache"], actions)
        writing_validate.assert_not_called()

    def test_export_source_review_uses_fixed_project_paths(self) -> None:
        args = argparse.Namespace(output=None, force=False, print_task=False)
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["reuse-existing-source-read-receipt"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_export_source_review(self.paths, args)
        self.assertEqual(0, result)
        self.assertIn("deprecated-for-direct-imitation", output.getvalue())
        self.assertIn("禁止回退到来源语义任务入口", output.getvalue())

    def test_export_source_review_print_task_is_explicit_opt_in(self) -> None:
        args = argparse.Namespace(output=None, force=False, print_task=True)
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["auto-finalize-direct-imitation-source-stage"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_export_source_review(self.paths, args)
        self.assertEqual(0, result)
        self.assertNotIn('"sources": []', output.getvalue())
        self.assertIn("auto-finalize-direct-imitation-source-stage", output.getvalue())

    def test_source_review_next_is_compatibility_noop_after_receipt_ready(self) -> None:
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["reuse-existing-source-read-receipt"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_source_review_next(
                self.paths,
                argparse.Namespace(input=None),
            )
        self.assertEqual(0, result)
        self.assertIn("deprecated-for-direct-imitation", output.getvalue())
        self.assertIn("prepare-setting", output.getvalue())
        self.assertIn("prepare-draft-gates / start-draft", output.getvalue())

    def test_apply_source_review_item_is_compatibility_noop_after_receipt_ready(
        self,
    ) -> None:
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["reuse-existing-source-read-receipt"]),
        ), redirect_stdout(output):
            result = TOOLBOX.command_apply_source_review_item(
                self.paths,
                argparse.Namespace(input=None, result=None, packet_sha="ignored"),
            )
        self.assertEqual(0, result)
        self.assertIn("deprecated-for-direct-imitation", output.getvalue())

    def test_export_rule_review_uses_independent_task_file(self) -> None:
        args = argparse.Namespace(output=None, force=False, print_task=False)
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": "receipt-sha"},
            "files": [{"path": "rule.md", "content": "完整规则"}],
        }
        output = StringIO()
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "build_rule_review_task",
            return_value=(task, []),
        ), redirect_stdout(output):
            result = TOOLBOX.command_export_rule_review(self.paths, args)
        self.assertEqual(0, result)
        self.assertEqual(
            "writing_rule_review_task",
            TOOLBOX.read_json(self.paths["writing_rule_input"])["kind"],
        )
        progress = TOOLBOX.read_json(self.paths["writing_rule_progress"])
        self.assertEqual("writing_rule_review_result", progress["kind"])
        self.assertEqual([], progress["reviews"])
        self.assertIn("禁止直接修改写作规则读取回执", output.getvalue())
        self.assertNotIn("完整规则", output.getvalue())

    def test_rule_review_next_prints_only_first_pending_rule_file(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [
                {
                    "path": "references/workflow/format-and-structure.md",
                    "sha256": "sha-1",
                    "content": "第一份完整规则。",
                    "review": {
                        "status": "read",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    },
                },
                {
                    "path": "references/anti-ai-writing.md",
                    "sha256": "sha-2",
                    "content": "不应提前打印。",
                    "review": {
                        "status": "read",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    },
                },
            ],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [],
            },
        )
        output = StringIO()
        with redirect_stdout(output):
            result = TOOLBOX.command_rule_review_next(
                self.paths,
                argparse.Namespace(input=None),
            )
        self.assertEqual(0, result)
        self.assertIn("references/workflow/format-and-structure.md", output.getvalue())
        self.assertNotIn("不应提前打印", output.getvalue())
        self.assertIn("packet_sha256", output.getvalue())
        self.assertIn("rule_review_progress: pending 0/2", output.getvalue())

    def test_rule_review_next_splits_large_rule_file_into_safe_packets(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        large_content = (
            "## 反 AI 规则\n\n"
            + "\n\n".join(
                f"第{i}段：" + ("必须完整阅读并提取证据词，禁止压缩成摘要。 " * 12)
                for i in range(1, 8)
            )
        )
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [
                {
                    "path": "references/anti-ai-writing.md",
                    "sha256": "sha-anti-ai",
                    "content": large_content,
                    "review": {
                        "status": "read",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    },
                }
            ],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [],
                "packet_reviews": [],
            },
        )

        with patch.object(TOOLBOX, "RULE_REVIEW_SEGMENT_TARGET_BYTES", 500):
            packets = TOOLBOX.rule_review_packets_for_item(
                self.paths["writing_rule_input"],
                task,
                task["files"][0],
            )
            self.assertGreater(len(packets), 1)
            for packet in packets:
                self.assertLessEqual(
                    len(json.dumps(packet, ensure_ascii=False, indent=2).encode("utf-8")),
                    TOOLBOX.MAX_RULE_REVIEW_PACKET_BYTES,
                )

            output = StringIO()
            with redirect_stdout(output):
                result = TOOLBOX.command_rule_review_next(
                    self.paths,
                    argparse.Namespace(input=None),
                )
        self.assertEqual(0, result)
        self.assertIn("references/anti-ai-writing.md", output.getvalue())
        self.assertIn('"segment_count":', output.getvalue())
        self.assertNotIn("超过 24000 bytes 安全上限", output.getvalue())

    def test_apply_rule_review_item_requires_packet_sha_and_appends_once(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        item = {
            "path": "references/workflow/format-and-structure.md",
            "sha256": "sha-1",
            "content": "完整规则原文，含有证据短语。",
            "review": {
                "status": "read",
                "evidence_terms": [],
                "takeaways": [],
                "used_for": [],
            },
        }
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [item],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [],
            },
        )
        packet = TOOLBOX.rule_review_packet(
            self.paths["writing_rule_input"],
            task,
            item,
        )
        item_result = packet["result_template"]
        item_result["review"] = {
            "status": "read",
            "evidence_terms": ["证据短语"],
            "takeaways": ["用于本书段落结构控制。"],
            "used_for": ["约束正文断段与对白排版。"],
        }
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_item_output"],
            item_result,
        )
        wrong = TOOLBOX.command_apply_rule_review_item(
            self.paths,
            argparse.Namespace(input=None, result=None, packet_sha="wrong"),
        )
        self.assertEqual(2, wrong)
        self.assertEqual(
            [],
            TOOLBOX.read_json(self.paths["writing_rule_progress"])["reviews"],
        )

        result = TOOLBOX.command_apply_rule_review_item(
            self.paths,
            argparse.Namespace(
                input=None,
                result=None,
                packet_sha=packet["packet_sha256"],
            ),
        )
        self.assertEqual(0, result)
        progress = TOOLBOX.read_json(self.paths["writing_rule_progress"])
        self.assertEqual(
            ["references/workflow/format-and-structure.md"],
            [item["path"] for item in progress["reviews"]],
        )
        self.assertFalse(self.paths["writing_rule_item_output"].exists())

    def test_apply_rule_review_item_rejects_nonliteral_evidence_terms_early(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        item = {
            "path": "references/workflow/format-and-structure.md",
            "sha256": "sha-1",
            "content": "规则原文只写纯数字节号和单空行。",
            "review": {
                "status": "read",
                "evidence_terms": [],
                "takeaways": [],
                "used_for": [],
            },
        }
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [item],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [],
                "packet_reviews": [],
            },
        )
        packet = TOOLBOX.rule_review_packet(
            self.paths["writing_rule_input"],
            task,
            item,
        )
        item_result = packet["result_template"]
        item_result["review"] = {
            "status": "read",
            "evidence_terms": ["每节推进一个明确的情节点"],
            "takeaways": ["用于本书结构控制。"],
            "used_for": ["用于正文断段。"],
        }
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_item_output"],
            item_result,
        )

        result = TOOLBOX.command_apply_rule_review_item(
            self.paths,
            argparse.Namespace(
                input=None,
                result=None,
                packet_sha=packet["packet_sha256"],
            ),
        )
        self.assertEqual(2, result)
        progress = TOOLBOX.read_json(self.paths["writing_rule_progress"])
        self.assertEqual([], progress["reviews"])
        self.assertEqual([], progress["packet_reviews"])
        self.assertTrue(self.paths["writing_rule_item_output"].exists())

    def test_apply_rule_review_item_aggregates_only_after_all_segments_complete(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        item = {
            "path": "references/anti-ai-writing.md",
            "sha256": "sha-anti-ai",
            "content": (
                "## 第一段\n\n"
                + ("强约束规则必须保留原文证据。 " * 10)
                + "\n\n## 第二段\n\n"
                + ("禁止把整段规则压成一句摘要。 " * 10)
            ),
            "review": {
                "status": "read",
                "evidence_terms": [],
                "takeaways": [],
                "used_for": [],
            },
        }
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [item],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [],
                "packet_reviews": [],
            },
        )

        with patch.object(TOOLBOX, "RULE_REVIEW_SEGMENT_TARGET_BYTES", 120):
            packets = TOOLBOX.rule_review_packets_for_item(
                self.paths["writing_rule_input"],
                task,
                item,
            )
            self.assertGreaterEqual(len(packets), 2)
            for index, packet in enumerate(packets, start=1):
                segment_content = str(packet["file"]["content"])
                evidence_term = next(
                    (
                        line.strip("。 ")
                        for line in segment_content.splitlines()
                        if line.strip() and "第" not in line and "##" not in line
                    ),
                    segment_content.strip().split("。")[0].strip(),
                )
                item_result = packet["result_template"]
                item_result["review"] = {
                    "status": "read",
                    "evidence_terms": [evidence_term],
                    "takeaways": [f"必须完整读取第{index}个规则分片。"],
                    "used_for": [f"规则分片#{index}绑定首写硬闸。"],
                }
                TOOLBOX.atomic_write_json(self.paths["writing_rule_item_output"], item_result)
                result = TOOLBOX.command_apply_rule_review_item(
                    self.paths,
                    argparse.Namespace(
                        input=None,
                        result=None,
                        packet_sha=packet["packet_sha256"],
                    ),
                )
                self.assertEqual(0, result)
                progress = TOOLBOX.read_json(self.paths["writing_rule_progress"])
                self.assertEqual(index, len(progress["packet_reviews"]))
                if index < len(packets):
                    self.assertEqual([], progress["reviews"])

        progress = TOOLBOX.read_json(self.paths["writing_rule_progress"])
        self.assertEqual(1, len(progress["reviews"]))
        self.assertEqual(len(packets), len(progress["packet_reviews"]))
        self.assertEqual("references/anti-ai-writing.md", progress["reviews"][0]["path"])
        self.assertGreaterEqual(len(progress["reviews"][0]["review"]["evidence_terms"]), 2)

    def test_apply_rule_review_synthesizes_final_result_from_progress(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [
                {
                    "path": "references/workflow/format-and-structure.md",
                    "sha256": "sha-1",
                    "content": "完整规则原文。",
                    "review": {
                        "status": "read",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    },
                }
            ],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [
                    {
                        "path": "references/workflow/format-and-structure.md",
                        "review": {
                            "status": "read",
                            "evidence_terms": ["完整规则"],
                            "takeaways": ["用于本书结构控制。"],
                            "used_for": ["用于正文断段。"],
                        },
                    }
                ],
            },
        )
        args = argparse.Namespace(input=None, result=None)
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "apply_rule_review_result",
            return_value=[],
        ) as apply_review:
            result = TOOLBOX.command_apply_rule_review(self.paths, args)
        self.assertEqual(0, result)
        synthesized = TOOLBOX.read_json(self.paths["writing_rule_output"])
        self.assertEqual("writing_rule_review_result", synthesized["kind"])
        self.assertEqual(1, len(synthesized["reviews"]))
        self.assertEqual(
            [self.paths["setting"], self.paths["outline"], self.paths["draft"]],
            apply_review.call_args.args[3],
        )

    def test_apply_rule_review_prints_next_prewrite_actions(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [
                {
                    "path": "references/workflow/format-and-structure.md",
                    "sha256": "sha-1",
                    "content": "完整规则原文。",
                    "review": {
                        "status": "read",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    },
                }
            ],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [
                    {
                        "path": "references/workflow/format-and-structure.md",
                        "review": {
                            "status": "read",
                            "evidence_terms": ["完整规则"],
                            "takeaways": ["用于本书结构控制。"],
                            "used_for": ["用于正文断段。"],
                        },
                    }
                ],
            },
        )
        output = StringIO()
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "apply_rule_review_result",
            return_value=[],
        ), redirect_stdout(output):
            result = TOOLBOX.command_apply_rule_review(
                self.paths,
                argparse.Namespace(input=None, result=None),
            )
        self.assertEqual(0, result)
        text = output.getvalue()
        self.assertIn("validate-prewrite-reads", text)
        self.assertIn("prepare-setting", text)
        self.assertIn("next_command: validate-prewrite-reads", text)
        self.assertIn("不得把 apply-rule-review 当作自然停点", text)

    def test_apply_rule_review_does_not_publish_output_when_gate_blocks(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["writing_receipt"], {"version": "1.0"})
        receipt_sha = TOOLBOX.file_sha256(self.paths["writing_receipt"])
        task = {
            "version": "1.0",
            "kind": "writing_rule_review_task",
            "receipt": {"sha256": receipt_sha},
            "files": [
                {
                    "path": "references/workflow/format-and-structure.md",
                    "sha256": "sha-1",
                    "content": "完整规则原文。",
                    "review": {
                        "status": "read",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    },
                }
            ],
        }
        TOOLBOX.atomic_write_json(self.paths["writing_rule_input"], task)
        TOOLBOX.atomic_write_json(
            self.paths["writing_rule_progress"],
            {
                "version": "1.0",
                "kind": "writing_rule_review_result",
                "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                "receipt_sha256": receipt_sha,
                "reviews": [
                    {
                        "path": "references/workflow/format-and-structure.md",
                        "review": {
                            "status": "read",
                            "evidence_terms": ["完整规则"],
                            "takeaways": ["用于本书结构控制。"],
                            "used_for": ["用于正文断段。"],
                        },
                    }
                ],
            },
        )

        result = TOOLBOX.command_apply_rule_review(
            self.paths,
            argparse.Namespace(input=None, result=None),
        )
        self.assertEqual(2, result)
        self.assertFalse(self.paths["writing_rule_output"].exists())

    def test_apply_rule_review_passes_fixed_outputs_to_gate(self) -> None:
        args = argparse.Namespace(
            input=str(self.paths["writing_rule_input"]),
            result=str(self.paths["writing_rule_output"]),
        )
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "apply_rule_review_result",
            return_value=[],
        ) as apply_review:
            result = TOOLBOX.command_apply_rule_review(self.paths, args)
        self.assertEqual(0, result)
        self.assertEqual(
            [self.paths["setting"], self.paths["outline"], self.paths["draft"]],
            apply_review.call_args.args[3],
        )

    def test_apply_source_review_passes_fixed_outputs_to_gate(self) -> None:
        args = argparse.Namespace(input=None, result=None)
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["auto-finalize-direct-imitation-source-stage"]),
        ) as ensure_ready:
            result = TOOLBOX.command_apply_source_review(self.paths, args)
        self.assertEqual(0, result)
        ensure_ready.assert_called_once_with(self.paths)

    def test_ensure_source_stage_ready_returns_auto_finalize_errors_instead_of_stale_receipt_errors(self) -> None:
        with patch.object(
            TOOLBOX.SOURCE_READ,
            "validate_receipt",
            return_value=(["旧回执错误"], {}),
        ), patch.object(
            TOOLBOX,
            "auto_finalize_direct_imitation_source_stage",
            return_value=(["自动补建后的真实错误"], []),
        ):
            errors, actions = TOOLBOX.ensure_source_stage_ready(self.paths)
        self.assertEqual(["自动补建后的真实错误"], errors)
        self.assertEqual([], actions)

    def test_validate_prewrite_reads_does_not_require_help_lookup(self) -> None:
        output = StringIO()
        with patch.object(
            TOOLBOX.WRITING_RULE,
            "validate_receipt",
            return_value=([], {}),
        ) as writing_validate, patch.object(
            TOOLBOX.SOURCE_READ,
            "validate_receipt",
            return_value=([], {}),
        ) as source_validate, redirect_stdout(output):
            result = TOOLBOX.command_validate_prewrite_reads(
                self.paths,
                argparse.Namespace(),
            )
        self.assertEqual(0, result)
        expected_outputs = [
            self.paths["setting"],
            self.paths["outline"],
            self.paths["draft"],
        ]
        self.assertEqual(expected_outputs, writing_validate.call_args.args[1])
        self.assertEqual(expected_outputs, source_validate.call_args.args[1])
        self.assertIn("next_command: prepare-setting", output.getvalue())
        self.assertIn("不得停在 validate-prewrite-reads", output.getvalue())

    def test_prepare_setting_initializes_ledger_and_releases_setting(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["source_receipt"], {"gate_status": "passed"})
        args = argparse.Namespace(force=False)
        ledger = {"gate_status": "pending"}
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["reuse-existing-source-read-receipt"]),
        ), patch.object(
            TOOLBOX.PRIMARY_SOURCE_BUNDLE,
            "create_bundle",
            return_value=({"kind": "primary-source-semantic-bundle"}, []),
        ) as create_primary_bundle, patch.object(
            TOOLBOX.RULE_LEDGER,
            "create_ledger",
            return_value=(ledger, []),
        ) as create_ledger, patch.object(
            TOOLBOX.RULE_LEDGER,
            "validate_prewrite_ledger",
            return_value=[],
        ) as validate_ledger, patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ) as validate_release, redirect_stdout(output):
            result = TOOLBOX.command_prepare_setting(self.paths, args)

        self.assertEqual(0, result)
        create_primary_bundle.assert_called_once_with(
            self.paths["source_receipt"],
            validate_source_receipt=False,
        )
        self.assertEqual(
            "primary-source-semantic-bundle",
            TOOLBOX.read_json(self.paths["primary_source_semantic_bundle"])["kind"],
        )
        create_ledger.assert_called_once_with(
            self.paths["project"].name,
            self.paths["writing_receipt"],
            self.paths["source_receipt"],
        )
        self.assertEqual(ledger, TOOLBOX.read_json(self.paths["ledger"]))
        validate_ledger.assert_called_once_with(self.paths["ledger"])
        validate_release.assert_called_once_with(
            "setting",
            self.paths["writing_receipt"],
            self.paths["source_receipt"],
            self.paths["ledger"],
            skip_source_receipt_validation=True,
        )
        self.assertIn("setting-context", output.getvalue())
        self.assertIn("next_command: setting-context", output.getvalue())
        self.assertIn("禁止重复运行 prepare-setting", output.getvalue())

    def test_setting_context_prints_bounded_summary(self) -> None:
        TOOLBOX.atomic_write_json(
            self.paths["profile"],
            {
                "meta": {
                    "name": self.project.name,
                    "mode": "merged_profiles",
                    "source_count": 3,
                    "generated_at": "2026-07-31T21:49:31+08:00",
                    "sources": ["a", "b", "c"],
                },
                "opening_signal_groups": {
                    "registry_or_commitment": ["隐婚", "家属签字", "依法办案"]
                },
                "derived_patterns": {"emotion_core": ["失位", "反刀"]},
                "style_assets": {
                    "opening_hooks": ["先给核验说法", "再给善意返场"],
                    "micro_actions": ["捏杯口", "把话咽回去"],
                },
                "bridge_rules": [
                    {
                        "id": "BR-01",
                        "bridge": "扫黄误认",
                        "opening_pattern": "公开场直接撞破",
                        "must_keep": ["公开羞耻", "关系失位"],
                        "recommended_sequence": ["先错认", "再核验"],
                        "why_order_matters": "先炸开身份再给证据才有情绪差。",
                    }
                ],
            },
        )
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {
                "primary_source": {
                    "name": "扫黄扫到了我老公",
                    "root": "/tmp/source",
                    "original": {"path": "/tmp/source.txt", "sha256": "sha"},
                    "selected_subflow_ids": ["SF-01", "SF-02"],
                },
                "subflows": [
                    {
                        "subflow_id": "SF-01",
                        "identity": "扫黄扫到了我老公::SF-01",
                        "source_excerpt": "原文片段" * 40,
                        "contract": {
                            "source_range": "L1-L30",
                            "required_sequence": ["先错认", "再压证据", "后失位"],
                            "information_delay": {"delay": "先瞒后爆"},
                            "control_changes": ["男主失去解释权"],
                            "emotion_sequence": ["惊", "羞", "恨", "冷"],
                            "source_style_granularity": {"voice": "有嘴", "pressure": "物件压场"},
                        },
                    }
                ],
            },
        )
        TOOLBOX.atomic_write_json(
            self.paths["source_receipt"],
            {
                "version": "1.0",
                "kind": "direct_imitation_source_read_receipt",
                "sources": [
                    {
                        "name": "幼薇",
                        "role": "auxiliary",
                        "root": str((self.project / "auxiliary").resolve()),
                        "selected_subflow_contracts": [],
                    }
                ],
            },
        )
        output = StringIO()

        with redirect_stdout(output):
            result = TOOLBOX.command_setting_context(self.paths, argparse.Namespace())

        self.assertEqual(0, result)
        text = output.getvalue()
        context, errors = TOOLBOX.build_setting_context(self.paths)
        self.assertEqual([], errors)
        self.assertLessEqual(
            len(json.dumps(context, ensure_ascii=False, indent=2).encode("utf-8")),
            TOOLBOX.MAX_STAGE_REFERENCE_BYTES,
        )
        self.assertIn("setting_context: bounded-setting-stage-summary", text)
        self.assertIn('"opening_signal_groups"', text)
        self.assertIn('"subflow_id": "SF-01"', text)
        self.assertIn('"adaptation_contract"', text)
        self.assertNotIn('"source_excerpt_preview"', text)
        self.assertIn("next_command: stage-reference --stage setting", text)

    def test_stage_reference_setting_excludes_postwrite_and_legacy_sections(self) -> None:
        payload, errors = TOOLBOX.build_stage_reference("setting")

        self.assertEqual([], errors)
        self.assertIsNotNone(payload)
        assert payload is not None
        content = payload["content"]
        self.assertIn("# 短篇设定阶段合同", content)
        self.assertIn("## 防套路六问", content)
        self.assertNotIn("写后审计", content)
        self.assertNotIn("## 回炉", content)
        self.assertNotIn("兼容", content)
        self.assertNotIn("$CODEX_HOME", content)
        self.assertLess(
            len(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
            TOOLBOX.MAX_STAGE_REFERENCE_BYTES,
        )

    def test_stage_reference_outline_is_single_bounded_complete_contract(self) -> None:
        payload, errors = TOOLBOX.build_stage_reference("outline")

        self.assertEqual([], errors)
        self.assertIsNotNone(payload)
        assert payload is not None
        content = payload["content"]
        self.assertIn("### 1. 导语拆解表", content)
        self.assertIn("### 16. 后果链表", content)
        self.assertIn("### 22. 16 张表的统一施工层要求", content)
        self.assertLess(
            len(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
            TOOLBOX.MAX_STAGE_REFERENCE_BYTES,
        )

    def test_stage_reference_command_prints_fixed_write_checkpoints(self) -> None:
        self.paths["setting"].write_text("# 设定\n", encoding="utf-8")
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "build_setting_context",
            return_value=({"adaptation_contract": {"required_units": ["主体::SF-01"]}}, []),
        ), patch.object(
            TOOLBOX,
            "validate_setting_adaptation_contract",
            return_value=[],
        ), redirect_stdout(output):
            result = TOOLBOX.command_stage_reference(
                self.paths,
                argparse.Namespace(stage="outline"),
            )

        self.assertEqual(0, result)
        text = output.getvalue()
        self.assertIn("stage_reference: bounded-fixed-stage-content", text)
        self.assertIn("第1-4节、第5-8节", text)
        self.assertIn("next_command_after_write: prepare-draft-gates", text)

    def test_adaptation_matrix_blocks_surface_copy(self) -> None:
        setting = """## 换链差异矩阵

### 换链单元：主体::SF-01
- 来源表层件：病房、花束、咳嗽、喂粥
- 保留机制：善意核验和被后置
- 新稿实现：病房咳嗽 → 丈夫喂粥 → 丢花 → 无借条
- 更换维度：场所、关键物件、触发动作、现实后果
- 用户锁定复用：无
- 禁止回流：病房、花束、咳嗽、喂粥
"""
        errors = TOOLBOX.validate_setting_adaptation_contract(setting, ["主体::SF-01"])
        self.assertTrue(any("仍复用多个来源表层件" in error for error in errors))

    def test_adaptation_matrix_accepts_mechanism_transfer(self) -> None:
        setting = """## 换链差异矩阵

### 换链单元：主体::SF-01
- 来源表层件：病房、花束、咳嗽、喂粥
- 保留机制：善意核验和被后置
- 新稿实现：听证候场 → 直播失控 → 声明撤回 → 停职通知
- 更换维度：场所、职业流程、关键物件、触发动作、现实后果
- 用户锁定复用：无
- 禁止回流：病房、花束、咳嗽、喂粥
"""
        self.assertEqual(
            [], TOOLBOX.validate_setting_adaptation_contract(setting, ["主体::SF-01"])
        )

    def test_prepare_setting_reuses_existing_ledger(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["ledger"], {"gate_status": "pending"})
        TOOLBOX.atomic_write_json(self.paths["source_receipt"], {"gate_status": "passed"})
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"kind": "primary-source-semantic-bundle"},
        )
        args = argparse.Namespace(force=False)
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["reuse-existing-source-read-receipt"]),
        ), patch.object(
            TOOLBOX.PRIMARY_SOURCE_BUNDLE,
            "validate_bundle",
            return_value=[],
        ) as validate_primary_bundle, patch.object(
            TOOLBOX.RULE_LEDGER,
            "create_ledger",
        ) as create_ledger, patch.object(
            TOOLBOX.RULE_LEDGER,
            "validate_prewrite_ledger",
            return_value=[],
        ), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ):
            result = TOOLBOX.command_prepare_setting(self.paths, args)

        self.assertEqual(0, result)
        validate_primary_bundle.assert_called_once_with(
            self.paths["primary_source_semantic_bundle"],
            validate_source_receipt=False,
        )
        create_ledger.assert_not_called()

    def test_prepare_setting_blocks_remaining_source_model_classification(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["ledger"], {"gate_status": "pending"})
        TOOLBOX.atomic_write_json(self.paths["source_receipt"], {"gate_status": "passed"})
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"kind": "primary-source-semantic-bundle"},
        )
        args = argparse.Namespace(force=False)
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["reuse-existing-source-read-receipt"]),
        ), patch.object(
            TOOLBOX.PRIMARY_SOURCE_BUNDLE,
            "validate_bundle",
            return_value=[],
        ), patch.object(
            TOOLBOX.RULE_LEDGER,
            "validate_prewrite_ledger",
            return_value=["规则 ASSET-1 尚未完成模型语义分类"],
        ), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
        ) as validate_release, redirect_stdout(output):
            result = TOOLBOX.command_prepare_setting(self.paths, args)

        self.assertEqual(2, result)
        validate_release.assert_not_called()
        self.assertIn("只处理工具箱明确导出的本书来源条目", output.getvalue())
        self.assertIn("禁止搜索旧项目示例", output.getvalue())

    def test_prepare_setting_blocks_when_primary_source_bundle_generation_fails(self) -> None:
        TOOLBOX.atomic_write_json(self.paths["source_receipt"], {"gate_status": "passed"})
        args = argparse.Namespace(force=False)
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], ["reuse-existing-source-read-receipt"]),
        ), patch.object(
            TOOLBOX.PRIMARY_SOURCE_BUNDLE,
            "create_bundle",
            return_value=({}, ["主体 SF 合同缺失"]),
        ), patch.object(
            TOOLBOX.RULE_LEDGER,
            "create_ledger",
            return_value=({}, []),
        ), redirect_stdout(output):
            result = TOOLBOX.command_prepare_setting(self.paths, args)

        self.assertEqual(2, result)
        self.assertIn("主体 SF 合同缺失", output.getvalue())

    def test_start_draft_prechecks_then_reuses_prereq_release_after_bundle(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["bundle"]),
        ), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ) as release, patch.object(
            TOOLBOX.SECTION_BUNDLE,
            "validate_bundle",
            return_value=[],
        ) as validate_bundle, patch.object(
            TOOLBOX.FIRST_DRAFT,
            "init_entry",
            return_value=0,
        ) as init_entry:
            result = TOOLBOX.command_start_draft(self.paths, args)
        self.assertEqual(0, result)
        self.assertEqual(0, release.call_count)
        validate_bundle.assert_called_once_with(self.paths["section_source_bundle"])
        self.assertTrue(init_entry.call_args.kwargs["release_prevalidated"])

    def test_start_draft_auto_applies_ready_prewrite_repairs_before_preflight(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        opening_packet = {"packet_sha256": "opening-sha"}
        sequence_packet = {"packet_sha256": "sequence-sha"}
        capacity_packet = {"packet_sha256": "capacity-sha"}
        outline_packet = {"packet_sha256": "outline-sha"}
        self.paths["opening_repair_packet"].write_text(
            json.dumps(opening_packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["opening_repair_item_output"].write_text(
            json.dumps({"gate_status": "passed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["sequence_repair_packet"].write_text(
            json.dumps(sequence_packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["sequence_repair_item_output"].write_text(
            json.dumps({"gate_status": "passed", "status": "completed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["draft_capacity_packet"].write_text(
            json.dumps(capacity_packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["draft_capacity_item_output"].write_text(
            json.dumps({"gate_status": "passed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_packet"].write_text(
            json.dumps(outline_packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps([{"section_id": "1", "verdict": "passed"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch.object(
            TOOLBOX,
            "command_opening_apply",
            return_value=0,
        ) as opening_apply, patch.object(
            TOOLBOX,
            "command_sequence_apply",
            return_value=0,
        ) as sequence_apply, patch.object(
            TOOLBOX,
            "command_draft_capacity_apply",
            return_value=0,
        ) as capacity_apply, patch.object(
            TOOLBOX,
            "command_outline_repair_apply",
            return_value=0,
        ) as outline_apply, patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=(["preflight blocked"], ["preflight"]),
        ):
            result = TOOLBOX.command_start_draft(self.paths, args)

        self.assertEqual(2, result)
        self.assertEqual("opening-sha", opening_apply.call_args.args[1].packet_sha)
        self.assertEqual("sequence-sha", sequence_apply.call_args.args[1].packet_sha)
        self.assertEqual("capacity-sha", capacity_apply.call_args.args[1].packet_sha)
        self.assertEqual("outline-sha", outline_apply.call_args.args[1].packet_sha)

    def test_start_draft_skips_auto_apply_for_stale_outline_template(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        self.paths["outline_repair_item_output"].write_text(
            json.dumps([{"section_id": "1", "verdict": "pending"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_packet"].write_text(
            json.dumps({"packet_sha256": "outline-sha"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch.object(
            TOOLBOX,
            "command_outline_repair_apply",
            return_value=0,
        ) as outline_apply, patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=(["preflight blocked"], ["preflight"]),
        ):
            result = TOOLBOX.command_start_draft(self.paths, args)

        self.assertEqual(2, result)
        outline_apply.assert_not_called()

    def test_start_draft_stops_when_auto_apply_ready_outline_repair_fails(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        self.paths["outline_repair_packet"].write_text(
            json.dumps({"packet_sha256": "outline-sha"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps([{"section_id": "1", "verdict": "passed"}], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        outline_packet_mtime = self.paths["outline_repair_packet"].stat().st_mtime + 1
        os.utime(
            self.paths["outline_repair_item_output"],
            (outline_packet_mtime, outline_packet_mtime),
        )

        with patch.object(
            TOOLBOX,
            "command_outline_repair_apply",
            return_value=2,
        ) as outline_apply, patch.object(
            TOOLBOX,
            "run_preflight",
        ) as run_preflight:
            result = TOOLBOX.command_start_draft(self.paths, args)

        self.assertEqual(2, result)
        self.assertEqual("outline-sha", outline_apply.call_args.args[1].packet_sha)
        run_preflight.assert_not_called()

    def test_start_draft_auto_applies_outline_repair_when_list_payload_is_ready(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        self.paths["outline_repair_packet"].write_text(
            json.dumps({"packet_sha256": "outline-sha"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["outline_repair_item_output"].write_text(
            json.dumps(
                [{"section_id": "1", "verdict": "passed", "irreversible_action": "已补完"}],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with patch.object(
            TOOLBOX,
            "command_outline_repair_apply",
            return_value=0,
        ) as outline_apply, patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=(["preflight blocked"], ["preflight"]),
        ):
            result = TOOLBOX.command_start_draft(self.paths, args)

        self.assertEqual(2, result)
        self.assertEqual("outline-sha", outline_apply.call_args.args[1].packet_sha)

    def test_start_draft_skips_auto_apply_for_already_passed_capacity_receipt(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        self.paths["draft_capacity_contract"].write_text(
            json.dumps({"gate_status": "passed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["draft_capacity_packet"].write_text(
            json.dumps({"packet_sha256": "capacity-sha"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.paths["draft_capacity_item_output"].write_text(
            json.dumps({"gate_status": "passed"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch.object(
            TOOLBOX,
            "command_draft_capacity_apply",
            return_value=0,
        ) as capacity_apply, patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=(["preflight blocked"], ["preflight"]),
        ):
            result = TOOLBOX.command_start_draft(self.paths, args)

        self.assertEqual(2, result)
        capacity_apply.assert_not_called()

    def test_start_draft_skips_duplicate_outline_revalidation_when_building_bundle(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["bundle"]),
        ) as ensure_bundle, patch.object(
            TOOLBOX.SECTION_BUNDLE,
            "validate_bundle",
            return_value=[],
        ), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ), patch.object(
            TOOLBOX.FIRST_DRAFT,
            "init_entry",
            return_value=0,
        ):
            result = TOOLBOX.command_start_draft(self.paths, args)
        self.assertEqual(0, result)
        ensure_bundle.assert_called_once_with(
            self.paths,
            skip_outline_contract_revalidation=True,
        )

    def test_start_draft_keeps_full_release_validation_when_bundle_already_exists(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        self.paths["section_source_bundle"].write_text(
            json.dumps({"gate": "section_source_bundle"}, ensure_ascii=False),
            encoding="utf-8",
        )
        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["reuse-complete-section-source-bundle"]),
        ), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[],
        ) as release, patch.object(
            TOOLBOX.FIRST_DRAFT,
            "init_entry",
            return_value=0,
        ):
            result = TOOLBOX.command_start_draft(self.paths, args)
        self.assertEqual(0, result)
        release.assert_called_once()
        self.assertTrue(
            release.call_args.kwargs["skip_writing_receipt_validation"]
        )
        self.assertTrue(
            release.call_args.kwargs["skip_source_receipt_validation"]
        )
        self.assertTrue(
            release.call_args.kwargs["skip_section_source_bundle_validation"]
        )

    def test_prepare_draft_gates_initializes_four_receipts_before_draft(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        source_root = self.project / "主体拆文"
        (source_root / "原文").mkdir(parents=True)
        original = source_root / "原文" / "主体.txt"
        original.write_text("原文", encoding="utf-8")
        (source_root / "book.profile.json").write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.paths["setting"].write_text("# 设定\n", encoding="utf-8")
        self.paths["outline"].write_text(
            "\n".join(
                [f"## {index}. 节\n- 目标字数：1100" for index in range(1, 9)]
            )
            + "\n",
            encoding="utf-8",
        )
        TOOLBOX.atomic_write_json(
            self.paths["source_receipt"],
            {
                "sources": [
                    {
                        "role": "primary",
                        "root": str(source_root),
                    }
                ]
            },
        )
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"kind": "primary-source-semantic-bundle"},
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX.OPENING_CONTRACT,
            "create_receipt",
            return_value={"gate_status": "pending", "target_text": {"path": str(self.paths["outline"])}},
        ) as opening_create, patch.object(
            TOOLBOX.DRAFT_CAPACITY,
            "init",
            return_value={"gate_status": "pending", "target_words": 9000},
        ) as capacity_init, patch.object(
            TOOLBOX.SEQUENCE_CONTRACT,
            "init_receipt",
        ) as sequence_init, patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "create_receipt",
            return_value={"gate_status": "pending"},
        ) as outline_create, redirect_stdout(output):
            result = TOOLBOX.command_prepare_draft_gates(self.paths, args)

        self.assertEqual(0, result)
        opening_create.assert_called_once_with(
            self.project.name,
            original.resolve(),
            self.paths["outline"],
            "outline",
        )
        capacity_init.assert_called_once()
        sequence_init.assert_called_once()
        outline_create.assert_called_once()
        self.assertEqual(
            [source_root / "book.profile.json"],
            outline_create.call_args.kwargs["source_profile_paths"],
        )
        self.assertTrue(self.paths["opening_contract"].is_file())
        self.assertTrue(self.paths["draft_capacity_contract"].is_file())
        self.assertTrue(self.paths["outline_contract"].is_file())
        self.assertTrue(self.paths["opening_repair_packet"].is_file())
        self.assertTrue(self.paths["opening_repair_item_output"].is_file())
        self.assertTrue(self.paths["draft_capacity_packet"].is_file())
        self.assertTrue(self.paths["draft_capacity_item_output"].is_file())
        self.assertTrue(self.paths["outline_repair_packet"].is_file())
        self.assertTrue(self.paths["outline_repair_item_output"].is_file())
        self.assertIn("require-all-four-draft-gates-passed-before-start-draft", output.getvalue())
        self.assertIn("project_toolbox_progress: 正在运行写前机械预检", output.getvalue())
        self.assertIn("project_toolbox_progress: 正在初始化细纲表演验收契约", output.getvalue())
        self.assertIn("outline-precheck --only sections/handoff/bridges/first-draft", output.getvalue())
        self.assertIn("未到 start-draft 前不得收口", output.getvalue())
        self.assertIn("禁止搜索其他项目回执当模板", output.getvalue())

    def test_prepare_draft_gates_reads_profile_from_receipt_root_not_workspace_root(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        source_root = self.project / "主体拆文"
        (source_root / "原文").mkdir(parents=True)
        original = source_root / "原文" / "主体.txt"
        original.write_text("原文", encoding="utf-8")
        profile_path = source_root / "book.profile.json"
        profile_path.write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        catalog_path = source_root / "写作资产" / "桥段施工卡.md"
        catalog_path.parent.mkdir(parents=True)
        catalog_path.write_text("## BID-01 公开掉位\n", encoding="utf-8")
        self.paths["setting"].write_text("# 设定\n", encoding="utf-8")
        self.paths["outline"].write_text("## 1. 节\n- 目标字数：1100\n", encoding="utf-8")
        TOOLBOX.atomic_write_json(
            self.paths["source_receipt"],
            {
                "sources": [
                    {
                        "role": "primary",
                        "root": str(source_root),
                    }
                ]
            },
        )
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"kind": "primary-source-semantic-bundle"},
        )

        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE.PRIMARY_SOURCE_BUNDLE_MODULE,
            "validate_bundle",
            return_value=[],
        ):
            result = TOOLBOX.command_prepare_draft_gates(self.paths, args)

        self.assertEqual(0, result)
        receipt = json.loads(self.paths["outline_contract"].read_text(encoding="utf-8"))
        self.assertEqual(
            str(profile_path.resolve()),
            receipt["selected_source_originals"][0]["causal_asset_profile"]["path"],
        )

    def test_outline_contract_refresh_reasons_detects_empty_primary_inventory(self) -> None:
        source_root = self.project / "主体拆文"
        (source_root / "原文").mkdir(parents=True)
        original = source_root / "原文" / "主体.txt"
        original.write_text("原文", encoding="utf-8")
        profile_path = source_root / "book.profile.json"
        profile_path.write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.paths["outline"].write_text("## 1. 节\n- 目标字数：1100\n", encoding="utf-8")
        TOOLBOX.atomic_write_json(self.paths["source_receipt"], {"sources": []})
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"kind": "primary_source_semantic_bundle"},
        )
        TOOLBOX.atomic_write_json(
            self.paths["outline_contract"],
            {
                "version": "1.8",
                "outline": {
                    "path": str(self.paths["outline"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["outline"]),
                },
                "source_read_receipt": {
                    "path": str(self.paths["source_receipt"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["source_receipt"]),
                },
                "primary_source_semantic_bundle": {
                    "path": str(self.paths["primary_source_semantic_bundle"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["primary_source_semantic_bundle"]),
                },
                "selected_source_originals": [
                    {
                        "path": str(original.resolve()),
                        "sha256": TOOLBOX.file_sha256(original),
                        "role": "primary",
                        "causal_asset_profile": {
                            "path": str(profile_path.resolve()),
                            "sha256": TOOLBOX.file_sha256(profile_path),
                        },
                    }
                ],
                "sections": [{"section_id": "1"}],
                "primary_subflow_semantic_inventory": [],
            },
        )

        with patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_primary_subflow_inventory",
            side_effect=lambda value, binding, errors: errors.append("inventory stale") or {},
        ):
            reasons = TOOLBOX.outline_contract_refresh_reasons(
                self.paths,
                [original.resolve()],
                [profile_path.resolve()],
            )

        self.assertIn("primary-subflow-inventory-stale", reasons)

    def test_outline_contract_refresh_reasons_detects_missing_anti_verbatim_contract(self) -> None:
        source_root = self.project / "主体拆文"
        (source_root / "原文").mkdir(parents=True)
        original = source_root / "原文" / "主体.txt"
        original.write_text("原文", encoding="utf-8")
        profile_path = source_root / "book.profile.json"
        profile_path.write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.paths["outline"].write_text("## 1. 节\n- 目标字数：1100\n", encoding="utf-8")
        TOOLBOX.atomic_write_json(self.paths["source_receipt"], {"sources": []})
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"subflows": []},
        )
        TOOLBOX.atomic_write_json(
            self.paths["outline_contract"],
            {
                "version": "1.8",
                "outline": {
                    "path": str(self.paths["outline"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["outline"]),
                },
                "source_read_receipt": {
                    "path": str(self.paths["source_receipt"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["source_receipt"]),
                },
                "primary_source_semantic_bundle": {
                    "path": str(self.paths["primary_source_semantic_bundle"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["primary_source_semantic_bundle"]),
                },
                "selected_source_originals": [
                    {
                        "path": str(original.resolve()),
                        "sha256": TOOLBOX.file_sha256(original),
                        "role": "primary",
                        "causal_asset_profile": {
                            "path": str(profile_path.resolve()),
                            "sha256": TOOLBOX.file_sha256(profile_path),
                        },
                    }
                ],
                "sections": [
                    {
                        "section_id": "1",
                        "first_draft_generation_contract": {
                            "source_style_granularity": {
                                field: {"analysis": f"{field} analysis"}
                                for field in TOOLBOX.OUTLINE_PERFORMANCE.STYLE_GRANULARITY_FIELDS
                            },
                            "first_draft_style_plan": {},
                        },
                    }
                ],
                "primary_subflow_semantic_inventory": [],
            },
        )

        with patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_primary_subflow_inventory",
            return_value=[],
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "read_primary_source_bundle",
            return_value={"subflows": []},
        ):
            reasons = TOOLBOX.outline_contract_refresh_reasons(
                self.paths,
                [original.resolve()],
                [profile_path.resolve()],
            )

        self.assertIn("outline-section-1-anti-verbatim-schema-stale", reasons)

    def test_outline_contract_refresh_reasons_detects_source_binding_selection_stale(self) -> None:
        source_root = self.project / "主体拆文"
        (source_root / "原文").mkdir(parents=True)
        original = source_root / "原文" / "主体.txt"
        original.write_text("原文", encoding="utf-8")
        profile_path = source_root / "book.profile.json"
        profile_path.write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.paths["outline"].write_text("## 1. 节\n- 目标字数：1100\n", encoding="utf-8")
        TOOLBOX.atomic_write_json(self.paths["source_receipt"], {"sources": []})
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"subflows": []},
        )
        TOOLBOX.atomic_write_json(
            self.paths["outline_contract"],
            {
                "version": "1.8",
                "outline": {
                    "path": str(self.paths["outline"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["outline"]),
                },
                "source_read_receipt": {
                    "path": str(self.paths["source_receipt"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["source_receipt"]),
                },
                "primary_source_semantic_bundle": {
                    "path": str(self.paths["primary_source_semantic_bundle"].resolve()),
                    "sha256": TOOLBOX.file_sha256(self.paths["primary_source_semantic_bundle"]),
                },
                "selected_source_originals": [
                    {
                        "path": str(original.resolve()),
                        "sha256": TOOLBOX.file_sha256(original),
                        "role": "primary",
                        "causal_asset_profile": {
                            "path": str(profile_path.resolve()),
                            "sha256": TOOLBOX.file_sha256(profile_path),
                        },
                    }
                ],
                "sections": [
                    {
                        "section_id": "1",
                        "first_draft_generation_contract": {
                            "source_slice_bindings": [
                                {
                                    "source_path": str(original.resolve()),
                                    "subflow_id": "SF-12",
                                    "source_range": "L1-L9",
                                },
                                {
                                    "source_path": str(original.resolve()),
                                    "subflow_id": "SF-13",
                                    "source_range": "L10-L19",
                                },
                            ],
                            "source_style_granularity": {
                                field: {"analysis": f"{field} analysis"}
                                for field in TOOLBOX.OUTLINE_PERFORMANCE.STYLE_GRANULARITY_FIELDS
                            },
                            "first_draft_style_plan": {},
                            "anti_verbatim_transfer_contract": {},
                        },
                    }
                ],
                "primary_subflow_semantic_inventory": [],
            },
        )

        expected_receipt = {
            "sections": [
                {
                    "section_id": "1",
                    "first_draft_generation_contract": {
                        "source_slice_bindings": [
                            {
                                "source_path": str(original.resolve()),
                                "subflow_id": "SF-12",
                                "source_range": "L1-L9",
                            }
                        ]
                    },
                }
            ]
        }

        with patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "validate_primary_subflow_inventory",
            return_value=[],
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "read_primary_source_bundle",
            return_value={"subflows": []},
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "create_receipt",
            return_value=expected_receipt,
        ):
            reasons = TOOLBOX.outline_contract_refresh_reasons(
                self.paths,
                [original.resolve()],
                [profile_path.resolve()],
            )

        self.assertIn("outline-section-1-source-binding-selection-stale", reasons)

    def test_start_draft_refreshes_stale_outline_contract_before_bundle(self) -> None:
        self.paths["source_receipt"].write_text(json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8")
        self.paths["section_source_bundle"].write_text(json.dumps({"gate_status": "passed"}, ensure_ascii=False), encoding="utf-8")
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "auto_apply_ready_prewrite_repairs",
            return_value=(0, []),
        ), patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "receipt_source_originals",
            return_value=(["/tmp/source.txt"], []),
        ), patch.object(
            TOOLBOX,
            "receipt_source_profile_paths",
            return_value=(["/tmp/book.profile.json"], []),
        ), patch.object(
            TOOLBOX,
            "outline_contract_refresh_reasons",
            return_value=["outline-section-1-anti-verbatim-schema-stale"],
        ), patch.object(
            TOOLBOX,
            "rebuild_outline_contract",
            return_value=([], ["rebuild-outline-performance-contract"]),
        ) as rebuild_outline, patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["build-complete-section-source-bundle"]),
        ), patch.object(
            TOOLBOX,
            "validate_draft_release_after_bundle",
            return_value=([], ["validate-draft-release-once"]),
        ), patch.object(
            TOOLBOX.FIRST_DRAFT,
            "init_entry",
            return_value=0,
        ), redirect_stdout(output):
            result = TOOLBOX.command_start_draft(
                self.paths,
                argparse.Namespace(force_preflight=False, force=False),
            )

        text = output.getvalue()
        self.assertEqual(0, result)
        rebuild_outline.assert_called_once()
        self.assertFalse(self.paths["section_source_bundle"].exists())
        self.assertIn("invalidate-section-source-bundle-after-outline-refresh", text)

    def test_start_draft_auto_resets_stale_first_draft_state_and_reinitializes(self) -> None:
        self.paths["source_receipt"].write_text(json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8")
        self.paths["draft"].write_text("1.\n\n旧正文\n", encoding="utf-8")
        self.paths["first_draft_entry"].write_text(json.dumps({"gate": "first_draft_entry"}, ensure_ascii=False), encoding="utf-8")
        self.paths["section_execution_receipt"].write_text(
            json.dumps({"gate": "section_draft_execution", "sections": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "auto_apply_ready_prewrite_repairs",
            return_value=(0, []),
        ), patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "receipt_source_originals",
            return_value=([], []),
        ), patch.object(
            TOOLBOX,
            "receipt_source_profile_paths",
            return_value=([], []),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "validate_draft_release_after_bundle",
            return_value=([], ["validate-draft-release-once"]),
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["reuse-complete-section-source-bundle"]),
        ), patch.object(
            TOOLBOX.FIRST_DRAFT,
            "validate_entry",
            return_value=["outline_contract SHA 已变化"],
        ), patch.object(
            TOOLBOX.FIRST_DRAFT,
            "init_entry",
            return_value=0,
        ) as init_entry, redirect_stdout(output):
            result = TOOLBOX.command_start_draft(
                self.paths,
                argparse.Namespace(force_preflight=False, force=False),
            )

        text = output.getvalue()
        self.assertEqual(0, result)
        self.assertTrue(any(path.name.startswith("stale-first-draft-backup-") for path in self.paths["asset"].iterdir()))
        self.assertFalse(self.paths["draft"].exists())
        self.assertFalse(self.paths["first_draft_entry"].exists())
        self.assertFalse(self.paths["section_execution_receipt"].exists())
        init_entry.assert_called_once()
        self.assertIn("stale_first_draft_backup:", text)
        self.assertIn("reset-stale-first-draft-entry-before-reinit", text)

    def test_prepare_draft_gates_refreshes_stale_outline_contract(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        source_root = self.project / "主体拆文"
        (source_root / "原文").mkdir(parents=True)
        original = source_root / "原文" / "主体.txt"
        original.write_text("原文", encoding="utf-8")
        profile_path = source_root / "book.profile.json"
        profile_path.write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.paths["setting"].write_text("# 设定\n", encoding="utf-8")
        self.paths["outline"].write_text("## 1. 节\n- 目标字数：1100\n", encoding="utf-8")
        TOOLBOX.atomic_write_json(
            self.paths["source_receipt"],
            {
                "sources": [
                    {
                        "role": "primary",
                        "root": str(source_root),
                    }
                ]
            },
        )
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {"kind": "primary_source_semantic_bundle"},
        )
        TOOLBOX.atomic_write_json(self.paths["outline_contract"], {"version": "1.8"})
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "outline_contract_refresh_reasons",
            return_value=["primary-subflow-inventory-stale"],
        ), patch.object(
            TOOLBOX.OPENING_CONTRACT,
            "create_receipt",
            return_value={"gate_status": "pending", "target_text": {"path": str(self.paths["outline"])}},
        ), patch.object(
            TOOLBOX.DRAFT_CAPACITY,
            "init",
            return_value={"gate_status": "pending", "target_words": 1100},
        ), patch.object(
            TOOLBOX.SEQUENCE_CONTRACT,
            "init_receipt",
        ), patch.object(
            TOOLBOX.OUTLINE_PERFORMANCE,
            "create_receipt",
            return_value={"gate_status": "pending", "primary_subflow_semantic_inventory": [{"subflow_id": "SF-01"}]},
        ) as outline_create, redirect_stdout(output):
            result = TOOLBOX.command_prepare_draft_gates(self.paths, args)

        self.assertEqual(0, result)
        outline_create.assert_called_once()
        self.assertIn("refreshed-outline-performance-contract:primary-subflow-inventory-stale", output.getvalue())

    def test_validate_prewrite_reads_auto_applies_completed_rule_review(self) -> None:
        self.paths["writing_receipt"].write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "project": str(self.project),
                    "gate_status": "pending",
                    "confirmed_before_outline": False,
                    "confirmed_before_draft": False,
                    "files": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["writing_rule_input"].write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "kind": "writing_rule_review_task",
                    "receipt_path": str(self.paths["writing_receipt"]),
                    "receipt_sha256": TOOLBOX.file_sha256(self.paths["writing_receipt"]),
                    "files": [
                        {
                            "path": "references/workflow/format-and-structure.md",
                            "sha256": "sha-a",
                            "segments": [
                                {
                                    "segment_index": 1,
                                    "segment_count": 1,
                                    "title": "# 短篇格式规范与小节结构",
                                }
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.paths["writing_rule_progress"].write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "kind": "writing_rule_review_result",
                    "task_sha256": TOOLBOX.file_sha256(self.paths["writing_rule_input"]),
                    "receipt_sha256": TOOLBOX.file_sha256(self.paths["writing_receipt"]),
                    "reviews": [
                        {
                            "path": "references/workflow/format-and-structure.md",
                            "review": {
                                "status": "read",
                                "evidence_terms": [
                                    "# 短篇格式规范与小节结构",
                                    "## 章节标记",
                                ],
                                "takeaways": ["格式已读"],
                                "used_for": ["用于正文格式"],
                            },
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        output = StringIO()
        validate_calls = iter(
            [
                (["gate_status 必须为 passed"], {}),
                ([], {}),
            ]
        )
        apply_mock = None
        with patch.object(
            TOOLBOX,
            "ensure_source_stage_ready",
            return_value=([], []),
        ), patch.object(
            TOOLBOX.WRITING_RULE,
            "validate_receipt",
            side_effect=lambda *args, **kwargs: next(validate_calls),
        ), patch.object(
            TOOLBOX,
            "command_apply_rule_review",
            return_value=0,
        ) as apply_mock, redirect_stdout(output):
            result = TOOLBOX.command_validate_prewrite_reads(
                self.paths,
                argparse.Namespace(),
            )

        self.assertEqual(0, result)
        self.assertIsNotNone(apply_mock)
        apply_mock.assert_called_once()
        text = output.getvalue()
        self.assertIn("project_toolbox: validate-prewrite-reads passed", text)

    def test_receipt_source_originals_rejects_bundle_original_outside_source_root(self) -> None:
        source_root = self.project / "主体拆文"
        (source_root / "原文").mkdir(parents=True)
        original = source_root / "原文" / "主体.txt"
        original.write_text("原文", encoding="utf-8")
        detached = Path(self.temp.name) / "原文" / "主体.txt"
        detached.parent.mkdir(parents=True, exist_ok=True)
        detached.write_text("原文", encoding="utf-8")
        TOOLBOX.atomic_write_json(
            self.paths["source_receipt"],
            {
                "sources": [
                    {
                        "role": "primary",
                        "root": str(source_root),
                    }
                ]
            },
        )
        TOOLBOX.atomic_write_json(
            self.paths["primary_source_semantic_bundle"],
            {
                "primary_source": {
                    "original": {
                        "path": str(detached.resolve()),
                    }
                }
            },
        )

        originals, errors = TOOLBOX.receipt_source_originals(self.paths)
        self.assertEqual([], originals)
        self.assertTrue(any("未绑定拆文目录原文" in error for error in errors))

    def test_start_draft_blocks_draft_written_before_release(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        self.paths["draft"].write_text("未放行正文", encoding="utf-8")
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "run_preflight",
        ) as run_preflight, redirect_stdout(output):
            result = TOOLBOX.command_start_draft(self.paths, args)

        self.assertEqual(2, result)
        run_preflight.assert_not_called()
        self.assertIn("当前流程顺序错误", output.getvalue())
        self.assertIn("prepare-draft-gates", output.getvalue())

    def test_start_draft_stops_before_bundle_when_outline_gate_already_blocks(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        output = StringIO()
        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX.WRITE_RELEASE,
            "validate_release",
            return_value=[
                "write_release_gate: blocked (draft)；不得生成或修改当前阶段产物",
                "细纲表演验收实时复验失败",
            ],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
        ) as ensure_bundle, redirect_stdout(output):
            result = TOOLBOX.command_start_draft(self.paths, args)

        self.assertEqual(2, result)
        ensure_bundle.assert_not_called()
        self.assertIn("细纲表演验收实时复验失败", output.getvalue())
        self.assertNotIn("build-complete-section-source-bundle", output.getvalue())

    def test_start_draft_prints_draft_prereq_primary_command_before_bundle(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=["首写容量契约未通过", "第 1 节缺少 source_style_granularity"],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
        ) as ensure_bundle, redirect_stdout(output):
            result = TOOLBOX.command_start_draft(self.paths, args)

        text = output.getvalue()
        self.assertEqual(2, result)
        ensure_bundle.assert_not_called()
        self.assertIn("draft_prereq_repair_commands: draft-capacity-precheck", text)
        self.assertIn("draft_prereq_primary_command: draft-capacity-precheck", text)

    def test_start_draft_bundle_only_block_does_not_emit_prereq_repair_commands(self) -> None:
        args = argparse.Namespace(force=False, force_preflight=False)
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "run_preflight",
            return_value=([], ["preflight"]),
        ), patch.object(
            TOOLBOX,
            "draft_release_precheck_without_bundle",
            return_value=[],
        ), patch.object(
            TOOLBOX,
            "ensure_section_bundle",
            return_value=([], ["bundle"]),
        ), patch.object(
            TOOLBOX.SECTION_BUNDLE,
            "validate_bundle",
            return_value=["逐节原文颗粒包缺少 section_id=1 绑定"],
        ), patch.object(
            TOOLBOX,
            "refresh_draft_prereq_packets",
        ) as refresh_packets, redirect_stdout(output):
            result = TOOLBOX.command_start_draft(self.paths, args)

        text = output.getvalue()
        self.assertEqual(2, result)
        refresh_packets.assert_not_called()
        self.assertIn("逐节原文颗粒包未通过", text)
        self.assertIn("completion_state: continue_required_until_start-draft", text)
        self.assertIn("当前阻断仅来自逐节原文颗粒包", text)
        self.assertNotIn("draft_prereq_repair_commands:", text)

    def test_open_section_requires_the_displayed_packet_sha(self) -> None:
        args = argparse.Namespace(
            section="1",
            packet_sha="wrong",
            read_judgment="已完整读取",
        )
        with patch.object(
            TOOLBOX,
            "packet_for_section",
            return_value={"section_id": "1", "packet_sha256": "right"},
        ), patch.object(TOOLBOX.SECTION_EXECUTION, "open_section") as open_section:
            result = TOOLBOX.command_open_section(self.paths, args)
        self.assertEqual(2, result)
        open_section.assert_not_called()

    def test_open_section_reads_packet_without_duplicate_bundle_validation(self) -> None:
        args = argparse.Namespace(
            section="1",
            packet_sha="right",
            read_judgment="已完整读取",
        )
        with patch.object(
            TOOLBOX,
            "packet_for_section",
            return_value={
                "section_id": "1",
                "packet_sha256": "right",
                "payload": {
                    "source_slice_bindings": [
                        {
                            "subflow_id": "SF-01",
                            "source_subflow_contract": {
                                "required_sequence": ["第一拍"]
                            },
                        }
                    ]
                },
            },
        ) as packet_for_section, patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "open_section",
            return_value=0,
        ) as open_section:
            result = TOOLBOX.command_open_section(self.paths, args)
        self.assertEqual(0, result)
        packet_for_section.assert_called_once_with(
            self.paths["section_source_bundle"],
            "1",
            validate_bundle=False,
        )
        open_section.assert_called_once()
        beat_receipt = json.loads(
            self.paths["section_beat_receipt"].read_text(encoding="utf-8")
        )
        self.assertEqual("2.1", beat_receipt["schema_version"])
        self.assertEqual(800, beat_receipt["minimum_section_chars"])
        self.assertEqual(6, beat_receipt["minimum_evidence_chars"])
        self.assertIn("唯一首次出现位置递增", beat_receipt["evidence_order_note"])
        self.assertEqual(["", "", "", "", ""], beat_receipt["beats"][0]["evidence"])

    def test_section_reading_packet_keeps_full_sha_and_preserves_full_granularity_contracts(self) -> None:
        packet = {
            "packet_id": "section-1",
            "section_id": "1",
            "packet_sha256": "packet-sha",
            "payload": {
                "section_id": "1",
                "source_slice_bindings": [
                    {
                        "source_excerpt": "完整原文切片",
                        "source_subflow_contract": {
                            "subflow_id": "SF-01",
                            "required_sequence": ["第一拍", "第二拍"],
                            "causal_preconditions": {
                                "arrival_causes": ["必须先撞见"],
                                "knowledge_boundaries": ["暂时不能解释完"],
                            },
                        },
                    }
                ],
                "section_contract": {
                    "section_id": "1",
                    "title": "第1节 包厢里，他先抓住了我的制服",
                    "verdict": "passed",
                    "irreversible_action": "掉位成立",
                    "controlling_object": "袖口",
                    "source_mechanism": "先护外人再伤妻子",
                    "information_delay": "后情再揭",
                    "character_missteps": "误判",
                    "interaction_exchange": "试探后回避",
                    "conflict_carrier": "身份和袖口",
                    "relationship_legibility": "公开掉位",
                    "emotion_intensity": "反刀到位",
                    "professional_shell_translation": "程序话压私情",
                    "forbidden_items": ["总结主题"],
                    "outline_evidence": ["动作一"],
                    "manual_judgment": "通过",
                    "source_function_mechanism": {"redundant": True},
                    "scene_logic_contract": {"redundant": True},
                    "source_emotion_parity": {"redundant": True},
                    "first_draft_generation_contract": {"redundant": True},
                },
                "first_draft_generation_contract": {
                    "source_performance_excerpt": "正文首写摘录",
                    "source_performance_evidence": ["原文证据一", "原文证据二"],
                    "anti_verbatim_transfer_contract": {
                        "preserve_axes": ["保拍序", "保情绪"],
                        "rewrite_axes": ["改句面", "改对白壳"],
                        "forbidden_surface_reuse": ["完整原文切片"],
                        "allowed_evidence_usage": "只校准颗粒。",
                        "manual_judgment": "不能复写。",
                    },
                    "manual_judgment": "首写必须顶格照吃"
                },
                "scene_logic_contract": {"scene_entry_state": "进入", "scene_exit_state": "退出"},
                "source_emotion_parity": {
                    "source_excerpt": "这里是重复原文，不该再打印一次",
                    "source_emotion_sequence": [{"role": "起拍", "evidence": "原文句子"}],
                    "target_emotion_sequence": [{"role": "反刀", "evidence": "目标句子"}],
                    "parity_status": "adapted_equal_intensity",
                    "adaptation_boundary": "保强度不抄表层",
                    "manual_judgment": "通过",
                },
                "original_scene_granularity": {"source_scene": "原场面"},
            },
        }

        reading_packet = TOOLBOX.section_reading_packet(packet)
        payload = reading_packet["payload"]

        self.assertEqual("packet-sha", reading_packet["packet_sha256"])
        self.assertEqual("第1节 包厢里，他先抓住了我的制服", payload["section_heading"])
        self.assertEqual("完整原文切片", payload["source_slice_bindings"][0]["source_excerpt"])
        self.assertEqual(["第一拍", "第二拍"], payload["source_slice_bindings"][0]["source_dense_beats"])
        self.assertEqual(
            ["必须先撞见"],
            payload["source_slice_bindings"][0]["source_subflow_contract"]["causal_preconditions"]["arrival_causes"],
        )
        self.assertEqual("进入", payload["target_scene_contract"]["scene_entry_state"])
        self.assertIn("anti_verbatim_transfer_contract", payload["target_style_contract"])
        self.assertEqual("掉位成立", payload["section_guardrails"]["irreversible_action"])
        self.assertNotIn("source_emotion_sequence", payload["target_emotion_contract"])

    def test_section_execution_packet_scopes_and_deduplicates_source_beats(self) -> None:
        def binding(subflow_id: str, sequence: list[str], source_range: str) -> dict[str, object]:
            return {
                "source_name": "主体书",
                "source_role": "main",
                "subflow_id": subflow_id,
                "source_range": source_range,
                "source_evidence": [f"{source_range}证据"],
                "source_subflow_contract": {
                    "subflow_id": subflow_id,
                    "required_sequence": sequence,
                },
            }

        sf01 = [f"SF-01 第{index}拍" for index in range(1, 7)]
        sf02 = [f"SF-02 第{index}拍" for index in range(1, 8)]
        sf07 = [f"SF-07 第{index}拍" for index in range(1, 7)]
        packet = {
            "section_id": "1",
            "packet_sha256": "packet-sha",
            "payload": {
                "section_contract": {
                    "source_function_mechanism": {
                        "why_selected_for_this_section": "主体 `SF-01`、主体 `SF-02`前三拍、主体 `SF-07`第一拍。"
                    }
                },
                "source_slice_bindings": [
                    binding("SF-01", sf01, "L1-L10"),
                    binding("SF-02", sf02, "L11-L20"),
                    binding("SF-07", sf07, "L21-L30"),
                    binding("SF-07", sf07, "L31-L40"),
                    binding("SF-07", sf07, "L41-L50"),
                ],
            },
        }

        scoped = TOOLBOX._section_execution_packet(packet)
        payload = scoped["payload"]
        execution = payload["execution_source_bindings"]

        self.assertEqual(5, len(payload["source_slice_bindings"]))
        self.assertEqual(3, len(execution))
        self.assertEqual(sf01, execution[0]["source_subflow_contract"]["required_sequence"])
        self.assertEqual([1, 2, 3, 4, 5, 6], execution[0]["source_subflow_contract"]["source_beat_indices"])
        self.assertEqual(sf02[:3], execution[1]["source_subflow_contract"]["required_sequence"])
        self.assertEqual([1, 2, 3], execution[1]["source_subflow_contract"]["source_beat_indices"])
        self.assertEqual(sf07[:1], execution[2]["source_subflow_contract"]["required_sequence"])
        self.assertEqual([1], execution[2]["source_subflow_contract"]["source_beat_indices"])
        self.assertNotIn("source_subflow_contract", payload["source_slice_bindings"][3])
        self.assertNotIn("source_subflow_contract", payload["source_slice_bindings"][4])
        self.assertEqual(["L21-L30证据"], payload["source_slice_bindings"][2]["source_evidence"])
        self.assertEqual(["L31-L40证据"], payload["source_slice_bindings"][3]["source_evidence"])
        self.assertEqual(["L41-L50证据"], payload["source_slice_bindings"][4]["source_evidence"])

    def test_binding_beat_scope_supports_front_back_single_last_and_all(self) -> None:
        binding = {"source_name": "主体书", "subflow_id": "SF-03"}
        cases = {
            "主体 `SF-03`前两拍。": [1, 2],
            "主体 `SF-03`后三拍。": [6, 7, 8],
            "主体 `SF-03`第五拍回收。": [5],
            "主体 `SF-03`末拍回收。": [8],
            "主体 `SF-03`全八拍。": [1, 2, 3, 4, 5, 6, 7, 8],
            "主体 `SF-03`的证据中继。": [1, 2, 3, 4, 5, 6, 7, 8],
        }
        for description, expected in cases.items():
            with self.subTest(description=description):
                self.assertEqual(expected, TOOLBOX._binding_beat_scope(description, binding, 8))

    def test_show_section_prints_bounded_reading_packet(self) -> None:
        args = argparse.Namespace(section="1", part=None)
        packet = {
            "packet_id": "section-1",
            "section_id": "1",
            "packet_sha256": "packet-1",
            "payload": {
                "section_id": "1",
                "source_slice_bindings": [{"source_excerpt": "完整原文切片", "source_evidence": ["证据A", "证据B"]}],
                "section_contract": {
                    "section_id": "1",
                    "title": "第1节 包厢里，他先抓住了我的制服",
                    "verdict": "passed",
                    "irreversible_action": "掉位成立",
                    "controlling_object": "袖口",
                    "source_mechanism": "先护外人再伤妻子",
                    "information_delay": "后情再揭",
                    "character_missteps": "误判",
                    "interaction_exchange": "试探后回避",
                    "conflict_carrier": "身份和袖口",
                    "relationship_legibility": "公开掉位",
                    "emotion_intensity": "反刀到位",
                    "professional_shell_translation": "程序话压私情",
                    "forbidden_items": ["总结主题"],
                    "outline_evidence": ["动作一"],
                    "manual_judgment": "通过",
                    "source_function_mechanism": {"redundant": True},
                },
                "first_draft_generation_contract": {"manual_judgment": "完整合同"},
                "scene_logic_contract": {"scene_entry_state": "进入"},
                "source_emotion_parity": {
                    "source_excerpt": "重复原文",
                    "source_emotion_sequence": [{"role": "起拍", "evidence": "原文句子"}],
                    "target_emotion_sequence": [{"role": "反刀", "evidence": "目标句子"}],
                    "parity_status": "adapted_equal_intensity",
                    "adaptation_boundary": "保强度不抄表层",
                    "manual_judgment": "通过",
                },
                "original_scene_granularity": {"source_scene": "原场面"},
            },
        }
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "packet_for_section",
            return_value=packet,
        ), redirect_stdout(output):
            result = TOOLBOX.command_show_section(self.paths, args)

        text = output.getvalue()
        self.assertEqual(0, result)
        self.assertIn("packet-1", text)
        self.assertIn("证据A", text)
        self.assertIn("完整原文切片", text)
        self.assertNotIn("重复原文", text)
        self.assertIn("section_source_packet_mode: combined", text)
        self.assertIn("section_source_packet_parts_saved: 5", text)
        self.assertIn("minimum_section_chars:", text)
        self.assertIn("minimum_evidence_chars:", text)
        self.assertIn("evidence_order_note:", text)
        self.assertIn('"target_scene_contract"', text)
        self.assertIn('"target_style_contract"', text)
        self.assertIn("required_read_judgment:", text)
        self.assertIn("required_close_judgment:", text)
        self.assertNotIn("next_read_action:", text)

    def test_section_reading_packet_chunks_split_large_binding_groups(self) -> None:
        packet = {
            "packet_id": "section-1",
            "section_id": "1",
            "packet_sha256": "packet-sha",
            "payload": {
                "section_id": "1",
                "source_slice_bindings": [
                    {
                        "source_excerpt": "A" * 12000,
                        "source_evidence": ["证据A1", "证据A2"],
                        "source_subflow_contract": {
                            "subflow_id": "SF-01",
                            "required_sequence": ["第一拍", "第二拍"],
                            "source_style_granularity": {"voice": "A" * 2000},
                        },
                    },
                    {
                        "source_excerpt": "B" * 12000,
                        "source_evidence": ["证据B1", "证据B2"],
                        "source_subflow_contract": {
                            "subflow_id": "SF-02",
                            "required_sequence": ["第三拍", "第四拍"],
                            "source_style_granularity": {"voice": "B" * 2000},
                        },
                    },
                ],
                "section_contract": {
                    "section_id": "1",
                    "verdict": "passed",
                    "irreversible_action": "掉位成立",
                    "controlling_object": "袖口",
                    "forbidden_items": ["总结主题"],
                    "manual_judgment": "通过",
                },
                "first_draft_generation_contract": {"manual_judgment": "完整合同"},
                "scene_logic_contract": {"scene_entry_state": "进入"},
                "source_emotion_parity": {"manual_judgment": "通过"},
                "original_scene_granularity": {"source_scene": "原场面"},
            },
        }

        chunks = TOOLBOX.section_reading_packet_chunks(packet)

        self.assertEqual(6, len(chunks))
        self.assertEqual(1, chunks[0]["part_index"])
        self.assertEqual(6, chunks[0]["part_count"])
        self.assertEqual("source_bindings", chunks[0]["part_kind"])
        self.assertEqual(2, chunks[1]["part_index"])
        self.assertEqual(6, chunks[1]["part_count"])
        self.assertEqual("source_bindings", chunks[1]["part_kind"])
        self.assertEqual(1, len(chunks[0]["payload"]["source_slice_bindings"]))
        self.assertEqual(3, chunks[2]["part_index"])
        self.assertEqual(6, chunks[2]["part_count"])
        self.assertEqual("target_scene_contract", chunks[2]["part_kind"])
        self.assertEqual(4, chunks[3]["part_index"])
        self.assertEqual(6, chunks[3]["part_count"])
        self.assertEqual("target_style_contract", chunks[3]["part_kind"])
        self.assertEqual(5, chunks[4]["part_index"])
        self.assertEqual(6, chunks[4]["part_count"])
        self.assertEqual("target_emotion_contract", chunks[4]["part_kind"])
        self.assertEqual(6, chunks[5]["part_index"])
        self.assertEqual(6, chunks[5]["part_count"])
        self.assertEqual("section_guardrails", chunks[5]["part_kind"])
        self.assertEqual("packet-sha", chunks[0]["packet_sha256"])
        self.assertEqual("packet-sha", chunks[5]["packet_sha256"])

    def test_section_reading_packet_chunks_split_large_section_contract(self) -> None:
        packet = {
            "packet_id": "section-1",
            "section_id": "1",
            "packet_sha256": "packet-sha",
            "payload": {
                "section_id": "1",
                "source_slice_bindings": [],
                "section_contract": {
                    "section_id": "1",
                    "title": "第1节 包厢里，他先抓住了我的制服",
                    "verdict": "passed",
                    "irreversible_action": "A" * 20000,
                    "character_missteps": "B" * 9000,
                    "interaction_exchange": "B" * 9000,
                    "manual_judgment": "通过",
                },
                "first_draft_generation_contract": {"manual_judgment": "完整合同"},
                "scene_logic_contract": {"scene_entry_state": "进入"},
                "source_emotion_parity": {"manual_judgment": "通过"},
                "original_scene_granularity": {"source_scene": "原场面"},
            },
        }

        chunks = TOOLBOX.section_reading_packet_chunks(packet)
        section_contract_chunks = [chunk for chunk in chunks if chunk["part_kind"] == "section_guardrails"]

        self.assertGreaterEqual(len(section_contract_chunks), 2)
        for chunk in section_contract_chunks:
            self.assertIn("section_heading", chunk["payload"])
            self.assertIn("section_guardrails", chunk["payload"])

    def test_show_section_falls_back_to_chunks_when_combined_packet_is_oversized(self) -> None:
        args = argparse.Namespace(section="1", part=None)
        packet = {
            "packet_id": "section-1",
            "section_id": "1",
            "packet_sha256": "packet-sha",
            "payload": {
                "section_id": "1",
                "source_slice_bindings": [],
                "section_contract": {"section_id": "1", "manual_judgment": "A" * 80000},
                "first_draft_generation_contract": {},
                "scene_logic_contract": {},
                "source_emotion_parity": {},
                "original_scene_granularity": {},
            },
        }
        output = StringIO()
        with patch.object(TOOLBOX, "packet_for_section", return_value=packet), redirect_stdout(output):
            result = TOOLBOX.command_show_section(self.paths, args)
        self.assertEqual(0, result)
        self.assertIn("section_source_packet_mode: chunked", output.getvalue())
        self.assertIn("next_read_action:", output.getvalue())
        self.assertNotIn("required_read_judgment:", output.getvalue())

    def test_advance_closes_current_and_prints_next_full_packet(self) -> None:
        args = argparse.Namespace(section="1", judgment="四项停检通过", part=None)
        TOOLBOX.atomic_write_json(
            self.paths["section_execution_receipt"],
            {
                "sections": [
                    {"section_id": "1", "status": "completed"},
                    {"section_id": "2", "status": "pending"},
                ]
            },
        )
        packet = {
            "section_id": "2",
            "packet_sha256": "packet-2",
            "payload": {
                "source_slice_bindings": [{"source_excerpt": "完整原文切片"}],
                "section_contract": {"section_id": "2"},
                "first_draft_generation_contract": {"manual_judgment": "完整合同"},
            },
        }
        output = StringIO()
        with patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "close_section",
            return_value=0,
        ), patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "open_section",
            return_value=0,
        ), patch.object(
            TOOLBOX,
            "packet_for_section",
            return_value=packet,
        ) as packet_for_section, redirect_stdout(output):
            result = TOOLBOX.command_advance_section(self.paths, args)
        self.assertEqual(0, result)
        packet_for_section.assert_called_once_with(
            self.paths["section_source_bundle"],
            "2",
            validate_bundle=False,
        )
        self.assertIn("packet-2", output.getvalue())
        self.assertIn("auto-opened", output.getvalue())
        self.assertIn("section_source_packet_mode: combined", output.getvalue())
        self.assertIn("minimum_section_chars:", output.getvalue())
        self.assertIn("minimum_evidence_chars:", output.getvalue())
        self.assertIn("evidence_order_note:", output.getvalue())
        self.assertNotIn("next_read_action:", output.getvalue())
        self.assertIn("required_read_judgment:", output.getvalue())
        self.assertIn("required_close_judgment:", output.getvalue())

    def test_reopen_section_resets_and_reprints_current_packet(self) -> None:
        args = argparse.Namespace(section="1", part=None)
        packet = {
            "section_id": "1",
            "packet_sha256": "packet-1",
            "payload": {
                "source_slice_bindings": [{"source_excerpt": "完整原文切片"}],
                "section_contract": {"section_id": "1"},
                "first_draft_generation_contract": {"manual_judgment": "完整合同"},
            },
        }
        output = StringIO()

        with patch.object(
            TOOLBOX.SECTION_EXECUTION,
            "reopen_section",
            return_value=0,
        ) as reopen_section, patch.object(
            TOOLBOX,
            "packet_for_section",
            return_value=packet,
        ) as packet_for_section, redirect_stdout(output):
            result = TOOLBOX.command_reopen_section(self.paths, args)

        self.assertEqual(0, result)
        reopen_section.assert_called_once_with(self.paths["section_execution_receipt"], "1")
        packet_for_section.assert_called_once_with(
            self.paths["section_source_bundle"],
            "1",
            validate_bundle=False,
        )
        self.assertIn("下一步必须重新完整阅读当前节颗粒包", output.getvalue())
        self.assertIn("required_read_judgment:", output.getvalue())

    def test_show_section_last_part_prints_required_judgments(self) -> None:
        args = argparse.Namespace(section="1", part=5)
        packet = {
            "packet_id": "section-1",
            "section_id": "1",
            "packet_sha256": "packet-1",
            "payload": {
                "section_id": "1",
                "source_slice_bindings": [{"source_excerpt": "完整原文切片"}],
                "section_contract": {
                    "section_id": "1",
                    "title": "第1节 包厢里，他先抓住了我的制服",
                    "verdict": "passed",
                    "irreversible_action": "掉位成立",
                    "controlling_object": "袖口",
                    "source_mechanism": "先护外人再伤妻子",
                    "information_delay": "后情再揭",
                    "character_missteps": "误判",
                    "interaction_exchange": "试探后回避",
                    "conflict_carrier": "身份和袖口",
                    "relationship_legibility": "公开掉位",
                    "emotion_intensity": "反刀到位",
                    "professional_shell_translation": "程序话压私情",
                    "forbidden_items": ["总结主题"],
                    "outline_evidence": ["动作一"],
                    "manual_judgment": "通过",
                    "source_function_mechanism": {"redundant": True},
                },
                "first_draft_generation_contract": {"manual_judgment": "完整合同"},
                "scene_logic_contract": {"scene_entry_state": "进入"},
                "source_emotion_parity": {
                    "source_excerpt": "重复原文",
                    "source_emotion_sequence": [{"role": "起拍", "evidence": "原文句子"}],
                    "target_emotion_sequence": [{"role": "反刀", "evidence": "目标句子"}],
                    "parity_status": "adapted_equal_intensity",
                    "adaptation_boundary": "保强度不抄表层",
                    "manual_judgment": "通过",
                },
                "original_scene_granularity": {"source_scene": "原场面"},
            },
        }
        output = StringIO()

        with patch.object(
            TOOLBOX,
            "packet_for_section",
            return_value=packet,
        ), redirect_stdout(output):
            result = TOOLBOX.command_show_section(self.paths, args)

        text = output.getvalue()
        self.assertEqual(0, result)
        self.assertIn("section_source_packet_current_part: 5/5", text)
        self.assertIn("required_read_judgment:", text)
        self.assertIn("read_token=", text)
        self.assertIn("required_close_judgment:", text)


if __name__ == "__main__":
    unittest.main()
