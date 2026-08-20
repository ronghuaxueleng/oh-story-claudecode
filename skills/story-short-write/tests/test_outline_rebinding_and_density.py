from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTLINE = load_module(
    "test_outline_rebinding_module",
    "validate_outline_migration_contract.py",
)
RELEASE = load_module(
    "test_streamlined_release_module",
    "validate_streamlined_write_release.py",
)
INITIAL_REVIEW = load_module(
    "test_initial_review_refresh_module",
    "validate_initial_draft_review.py",
)


class SourceSubflowCoverageTest(unittest.TestCase):
    def test_uncovered_prose_lines_are_reported_as_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text("甲\n乙\n1\n丙\n丁\n戊\n", encoding="utf-8")
            subflows = [
                {"subflow_id": "SF-01", "source_range": "L2-L4"},
            ]

            with self.assertRaisesRegex(ValueError, "L1, L5-L6"):
                OUTLINE._validate_subflow_source_coverage(original, subflows)

    def test_blank_and_numeric_marker_lines_do_not_require_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text("\n1.\n正文\n2、\n\n", encoding="utf-8")
            subflows = [
                {"subflow_id": "SF-01", "source_range": "L3-L3"},
            ]

            OUTLINE._validate_subflow_source_coverage(original, subflows)


def catalog(region_beats: list[tuple[str, list[tuple[str, str]]]]) -> dict:
    return {
        "regions": [
            {
                "region_id": region_id,
                "target_beats": [
                    {"target_id": target_id, "evidence": evidence}
                    for target_id, evidence in beats
                ],
            }
            for region_id, beats in region_beats
        ],
        "errors": [],
    }


class EvidenceRebindingTest(unittest.TestCase):
    def test_mapping_follows_unchanged_evidence_across_new_sections(self) -> None:
        old_catalog = catalog(
            [
                ("section:1", [("T-1-001", "甲"), ("T-1-002", "乙")]),
                ("section:2", [("T-2-001", "丙")]),
            ]
        )
        new_catalog = catalog(
            [
                ("section:1", [("T-1-001", "甲")]),
                ("section:2", [("T-2-001", "乙")]),
                ("section:3", [("T-3-001", "丙"), ("T-3-002", "新增")]),
            ]
        )
        mapping = {
            "primary_plot_targets": ["T-1-001", "T-1-002", "T-2-001"],
            "primary_emotion_targets": ["T-1-002", "T-2-001"],
            "auxiliary_plot_targets": {"SRC-AUX-01": ["T-2-001"]},
        }

        migrated = OUTLINE.migrate_mapping_by_evidence(
            old_catalog,
            new_catalog,
            mapping,
        )

        self.assertEqual(
            ["T-1-001", "T-2-001", "T-3-001"],
            migrated["primary_plot_targets"],
        )
        self.assertEqual(
            ["T-2-001", "T-3-001"],
            migrated["primary_emotion_targets"],
        )
        self.assertEqual(
            ["T-3-001"],
            migrated["auxiliary_plot_targets"]["SRC-AUX-01"],
        )

    def test_changed_evidence_blocks_deterministic_rebinding(self) -> None:
        old_catalog = catalog([("section:1", [("T-1-001", "原证据")])])
        new_catalog = catalog([("section:1", [("T-1-001", "被改写")])])
        mapping = {
            "primary_plot_targets": ["T-1-001"],
            "primary_emotion_targets": [],
            "auxiliary_plot_targets": {},
        }

        with self.assertRaisesRegex(ValueError, "已被改写或删除"):
            OUTLINE.migrate_mapping_by_evidence(
                old_catalog,
                new_catalog,
                mapping,
            )

    def test_changed_evidence_can_be_left_for_manual_remap(self) -> None:
        old_catalog = catalog(
            [("section:1", [("T-1-001", "保留"), ("T-1-002", "原证据")])]
        )
        new_catalog = catalog(
            [("section:1", [("T-1-001", "保留"), ("T-1-002", "被改写")])]
        )
        mapping = {
            "primary_plot_targets": ["T-1-001", "T-1-002", ""],
            "primary_emotion_targets": ["T-1-002"],
            "auxiliary_plot_targets": {},
        }

        migrated = OUTLINE.migrate_mapping_by_evidence(
            old_catalog,
            new_catalog,
            mapping,
            allow_manual_remap=True,
        )

        self.assertEqual(
            ["T-1-001", "", ""], migrated["primary_plot_targets"]
        )
        self.assertEqual([""], migrated["primary_emotion_targets"])

    def test_rebind_refreshes_changed_project_config_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "项目写作配置.json"
            outline = root / "小节大纲.md"
            receipt_path = root / "细纲表演验收回执.json"
            config.write_text('{"before": true}', encoding="utf-8")
            outline.write_text("细纲", encoding="utf-8")
            old_catalog = catalog([("section:1", [("T-1-001", "甲")])])
            mapping = {
                "primary_plot_targets": ["T-1-001"],
                "primary_emotion_targets": [],
                "auxiliary_plot_targets": {},
            }
            receipt_path.write_text(
                json.dumps({
                    "schema_version": OUTLINE.PREVIOUS_SCHEMA_VERSION,
                    "project_config": OUTLINE.binding(config),
                    "outline_catalog": old_catalog,
                    "mapping": mapping,
                    "manual_confirmation": {"manual_judgment": "已确认旧合同映射。"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            config.write_text('{"after": true}', encoding="utf-8")
            expected_config_sha = OUTLINE.sha256(config)
            spec = {
                "source_id": "SRC-PRIMARY",
                "name": "主体",
                "role": "primary",
                "prose_voice": "exclusive",
                "emotion_transfer": "full",
                "selected_bridge_ids": [],
                "original": {},
                "plot_ledger": {},
                "emotion_ledger": {},
                "subflow_catalog": {},
                "plot_beats": [{"beat_id": "P-001", "bid_ids": ["BID-01"]}],
                "emotion_beats": [],
                "prose_subflows": [],
                "hierarchy_assets": {
                    "profile": {"path": "profile", "sha256": "profile-sha"},
                    "story_core": {"path": "report", "sha256": "report-sha"},
                    "emotion_motherline": {
                        "path": "emotion-motherline",
                        "sha256": "emotion-motherline-sha",
                    },
                    "bridge_rules": [
                        {
                            "id": "BID-01",
                            "must_keep": ["公开掉位"],
                            "emotion_sequence": [],
                        }
                    ],
                },
            }
            current_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            current_receipt["sources"] = [OUTLINE._public_source(spec)]
            current_receipt["source_hierarchy"] = OUTLINE.build_source_hierarchy(
                [spec]
            )
            receipt_path.write_text(
                json.dumps(current_receipt, ensure_ascii=False), encoding="utf-8"
            )
            sequences = {
                "primary_plot_refs": ["SRC-PRIMARY:P-001"],
                "primary_emotion_refs": [],
                "primary_prose_subflow_refs": [],
                "auxiliary_plot_refs": {},
            }
            with mock.patch.object(OUTLINE, "source_specs", return_value=[spec]), \
                mock.patch.object(OUTLINE, "expected_sequences", return_value=sequences), \
                mock.patch.object(OUTLINE, "parse_outline", return_value=old_catalog), \
                mock.patch.object(OUTLINE, "build_granularity_coverage", return_value=[]), \
                mock.patch.object(OUTLINE, "build_sections", return_value=[]), \
                mock.patch.object(OUTLINE, "validate_data", return_value=[]):
                rebound = OUTLINE.rebind_outline(
                    receipt_path, outline, preserve_by_evidence=True
                )

        self.assertEqual(expected_config_sha, rebound["project_config"]["sha256"])
        self.assertEqual([OUTLINE._public_source(spec)], rebound["sources"])
        self.assertEqual(OUTLINE.SCHEMA_VERSION, rebound["schema_version"])


class SectionDensityTest(unittest.TestCase):
    def source_text(self) -> str:
        body = "字" * 600
        return "导语\n" + "\n".join(
            f"{index}{'.' if index % 2 == 0 else ''}\n{body}"
            for index in range(1, 18)
        )

    def outline_catalog(self, section_count: int, target_chars: int) -> dict:
        per_section = target_chars // section_count
        remainder = target_chars % section_count
        regions = []
        for index in range(1, section_count + 1):
            midpoint = per_section + (1 if index <= remainder else 0)
            regions.append(
                {
                    "region_id": f"section:{index}",
                    "target_chars": {"min": midpoint, "max": midpoint},
                }
            )
        return {"regions": regions, "errors": []}

    def test_bare_and_dotted_source_sections_are_recognized(self) -> None:
        sections = RELEASE.source_numeric_sections(self.source_text())
        self.assertEqual(17, len(sections))
        self.assertTrue(all(len(section) == 600 for section in sections))

    def test_minimum_density_blocks_fourteen_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text(self.source_text(), encoding="utf-8")
            target_chars = 25_125

            blocked = RELEASE.validate_section_density(
                self.outline_catalog(14, target_chars),
                original,
            )
            passed = RELEASE.validate_section_density(
                self.outline_catalog(29, target_chars),
                original,
            )

        self.assertTrue(blocked)
        self.assertIn("actual=14", blocked[0])
        self.assertEqual([], passed)

    def test_source_anchored_outline_blocks_total_and_section_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text(self.source_text(), encoding="utf-8")
            config = {
                "length_policy": {
                    "mode": "source_anchored",
                    "max_total_ratio": 1.25,
                    "max_section_ratio": 1.25,
                }
            }
            oversized = RELEASE.validate_source_anchored_outline(
                self.outline_catalog(29, 25_125), original, config
            )
            source_chars = RELEASE.nonspace_count(self.source_text())
            within_limit = RELEASE.validate_source_anchored_outline(
                self.outline_catalog(17, int(source_chars * 1.2)), original, config
            )

        self.assertEqual(2, len(oversized))
        self.assertIn("整体上限", oversized[0])
        self.assertIn("数字节数", oversized[1])
        self.assertEqual([], within_limit)

    def test_source_anchored_draft_uses_only_a_global_upper_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text("字" * 10_000, encoding="utf-8")
            config = {"length_policy": {"mode": "source_anchored"}}

            at_limit = RELEASE.validate_source_anchored_draft(
                "字" * 12_500, original, config
            )
            over_limit = RELEASE.validate_source_anchored_draft(
                "字" * 12_501, original, config
            )
            short_draft = RELEASE.validate_source_anchored_draft(
                "字" * 1_000, original, config
            )

        self.assertEqual([], at_limit)
        self.assertEqual([], short_draft)
        self.assertIn("draft=12501", over_limit[0])

    def test_expansion_mode_requires_explicit_user_authorization(self) -> None:
        _, missing = RELEASE.resolve_length_policy({
            "length_policy": {
                "mode": "explicit_expansion",
                "max_total_ratio": 2,
                "max_section_ratio": 2,
            }
        })
        policy, authorized = RELEASE.resolve_length_policy({
            "length_policy": {
                "mode": "explicit_expansion",
                "max_total_ratio": 2,
                "max_section_ratio": 2,
                "authorized_by_user": True,
                "authorization_note": "用户明确要求扩写为两倍篇幅",
            }
        })

        self.assertTrue(missing)
        self.assertEqual([], authorized)
        self.assertEqual(2.0, policy["max_total_ratio"])


class InitialReviewRefreshTest(unittest.TestCase):
    region_text = "第一条证据。中间内容。第二条证据。"

    def granularity_reviews(self, quote: str = "第一条证据。") -> list[dict]:
        default_quotes = [
            "第一条证据。",
            "中间内容。",
            "第二条证据。",
            "第一条证据。中间内容。",
            "中间内容。第二条证据。",
            self.region_text,
        ]
        return [
            {
                "source_ref": "SF-001",
                "dimensions": {
                    dimension: {
                        "status": "realized",
                        "evidence_quote": (
                            default_quotes[index]
                            if quote == "第一条证据。"
                            else f"{quote}{index}"
                        ),
                        "adaptation_note": f"第{index + 1}维已通过当前场面的专属动作与句间关系完成换芯落地。",
                    }
                    for index, dimension in enumerate(
                        INITIAL_REVIEW.GRANULARITY_DIMENSIONS
                    )
                },
            }
        ]

    def review(self, plot_refs: list[str], region_text: str | None = None) -> dict:
        text = self.region_text if region_text is None else region_text
        return {
            "content_sha256": INITIAL_REVIEW.text_sha256(text),
            "plot_refs": plot_refs,
            "emotion_refs": ["E-001"],
            "auxiliary_plot_refs": [],
            "prose_subflow_refs": ["SF-001"],
            "granularity_dimension_reviews": self.granularity_reviews(),
            "evidence_quotes": ["第一条证据。"],
        }

    def test_unchanged_requirements_and_quotes_can_be_preserved(self) -> None:
        old = self.review(["P-001"])
        refreshed = self.review(["P-001"])
        self.assertTrue(
            INITIAL_REVIEW.can_preserve_region_review(
                old,
                refreshed,
                self.region_text,
            )
        )

    def test_split_region_cannot_inherit_same_numbered_old_review(self) -> None:
        old = self.review(["P-001", "P-002"])
        refreshed = self.review(["P-001"])
        self.assertFalse(
            INITIAL_REVIEW.can_preserve_region_review(
                old,
                refreshed,
                self.region_text,
            )
        )

    def test_changed_region_cannot_inherit_even_when_quotes_survive(self) -> None:
        old = self.review(["P-001"])
        changed_text = "第一条证据。新增并改写的正文。第二条证据。"
        refreshed = self.review(["P-001"], changed_text)
        self.assertFalse(
            INITIAL_REVIEW.can_preserve_region_review(
                old,
                refreshed,
                changed_text,
            )
        )

    def test_stale_granularity_quote_cannot_be_preserved(self) -> None:
        old = self.review(["P-001"])
        old["granularity_dimension_reviews"] = self.granularity_reviews("已删除的证据。")
        refreshed = self.review(["P-001"])
        self.assertFalse(
            INITIAL_REVIEW.can_preserve_region_review(
                old,
                refreshed,
                self.region_text,
            )
        )

    def test_all_six_realized_dimensions_with_current_quotes_pass(self) -> None:
        entries = self.granularity_reviews()
        errors = INITIAL_REVIEW.validate_granularity_dimension_reviews(
            entries,
            [{"source_ref": "SF-001"}],
            self.region_text,
            "region",
        )
        self.assertEqual([], errors)

    def test_partial_or_missing_dimension_blocks(self) -> None:
        partial = self.granularity_reviews()
        partial[0]["dimensions"][INITIAL_REVIEW.GRANULARITY_DIMENSIONS[0]][
            "status"
        ] = "partial"
        partial_errors = INITIAL_REVIEW.validate_granularity_dimension_reviews(
            partial,
            [{"source_ref": "SF-001"}],
            self.region_text,
            "region",
        )
        missing = self.granularity_reviews()
        del missing[0]["dimensions"][INITIAL_REVIEW.GRANULARITY_DIMENSIONS[-1]]
        missing_errors = INITIAL_REVIEW.validate_granularity_dimension_reviews(
            missing,
            [{"source_ref": "SF-001"}],
            self.region_text,
            "region",
        )
        self.assertTrue(any("status 必须为 realized" in item for item in partial_errors))
        self.assertTrue(any("完整包含六维" in item for item in missing_errors))

    def test_dimension_quote_must_exist_in_current_region(self) -> None:
        entries = self.granularity_reviews("不存在的正文引句。")
        errors = INITIAL_REVIEW.validate_granularity_dimension_reviews(
            entries,
            [{"source_ref": "SF-001"}],
            self.region_text,
            "region",
        )
        self.assertTrue(any("逐字来自当前正文区域" in item for item in errors))

    def test_reused_dimension_quote_and_note_blocks(self) -> None:
        entries = self.granularity_reviews()
        for dimension in INITIAL_REVIEW.GRANULARITY_DIMENSIONS:
            entries[0]["dimensions"][dimension]["evidence_quote"] = "第一条证据。"
            entries[0]["dimensions"][dimension]["adaptation_note"] = (
                "六个维度全部复用同一段泛化说明，因此不能证明分别完成。"
            )
        errors = INITIAL_REVIEW.validate_granularity_dimension_reviews(
            entries,
            [{"source_ref": "SF-001"}],
            self.region_text,
            "region",
        )
        self.assertTrue(any("不得复用同一句" in item for item in errors))
        self.assertTrue(any("不得复用模板" in item for item in errors))


class InitialReviewWholeSfChainTest(unittest.TestCase):
    draft_regions = {
        "section:1": (
            "进入证据。动作一证据。场面证据。情绪一证据。"
            "前区补充证据甲。前区补充证据乙。"
        ),
        "section:2": "动作二证据。情绪二证据。退出证据。",
    }

    def scaffold(self) -> list[dict]:
        contract = {
            "granularity_coverage": [
                {
                    "source_ref": "SRC:SF-001",
                    "target_regions": ["section:1", "section:2"],
                    "performance_requirements": {
                        "entry_state": "人物带着尚未说破的疑问进入现场",
                        "required_sequence": ["先追问异常", "再由动作切断对话"],
                        "scene_granularity": "追问、错答、停顿和离场都要写成现场",
                        "emotion_sequence": ["疑问升为警觉", "警觉落成离开决定"],
                        "end_state": "人物结束对话并取得离场主动权",
                        "source_excerpt": "来源片段",
                    },
                    "source_layer_order": ["SF-001-L01", "SF-001-L02"],
                    "source_layer_topology": [
                        {
                            "layer_id": "SF-001-L01",
                            "source_range": "L1-L2",
                            "source_text": "来源现场一",
                            "layer_modes": ["live_scene"],
                            "layer_role": "追问异常并从错答中升起警觉。",
                            "entry_relation": "承接尚未说破的疑问。",
                            "exit_relation": "错答后把警觉送入动作切断。",
                            "narrative_distance": "近景跟随追问与停顿。",
                            "dimension_realization": {},
                            "must_preserve_in_target": ["保持追问错答的近景现场。"],
                        },
                        {
                            "layer_id": "SF-001-L02",
                            "source_range": "L3-L4",
                            "source_text": "来源现场二",
                            "layer_modes": ["live_scene"],
                            "layer_role": "动作切断对话并取得离场主动权。",
                            "entry_relation": "承接前层错答后的警觉。",
                            "exit_relation": "以离场动作关闭整个 SF。",
                            "narrative_distance": "近景跟随切断和离场。",
                            "dimension_realization": {},
                            "must_preserve_in_target": ["保持动作切断后的直接离场。"],
                        },
                    ],
                }
            ],
            "sf_performance_bindings": [
                {
                    "source_ref": "SRC:SF-001",
                    "required_sequence_target_ids": [["T-1"], ["T-2"]],
                    "emotion_sequence_target_ids": [["T-1"], ["T-2"]],
                    "scene_granularity_target_ids": ["T-1", "T-2"],
                    "source_layer_target_bindings": [
                        {
                            "layer_id": "SF-001-L01",
                            "target_ids": ["T-1"],
                            "preserved_layer_modes": ["live_scene"],
                            "adaptation_instruction": "第一层保持近景追问与错答的连续现场，并在停顿处切入下一层。",
                        },
                        {
                            "layer_id": "SF-001-L02",
                            "target_ids": ["T-2"],
                            "preserved_layer_modes": ["live_scene"],
                            "adaptation_instruction": "第二层保持动作切断与直接离场，不退成对关系结果的概述。",
                        },
                    ],
                }
            ],
            "outline_catalog": {
                "regions": [
                    {
                        "region_id": "section:1",
                        "target_beats": [{"target_id": "T-1"}],
                    },
                    {
                        "region_id": "section:2",
                        "target_beats": [{"target_id": "T-2"}],
                    },
                ]
            },
        }
        return INITIAL_REVIEW.required_sf_chain_reviews(
            contract, ["section:1", "section:2"]
        )

    def completed_review(self) -> tuple[list[dict], list[dict]]:
        expected = self.scaffold()
        actual = deepcopy(expected)
        review = actual[0]
        evidence = {
            "entry_state_review": (
                "进入证据。",
                "进入态通过人物落座后的追视和停顿具体落地，没有直接汇报疑问。",
            ),
            "scene_granularity_review": (
                "场面证据。",
                "场面颗粒通过追问、错答与动作停顿连续展开，没有压成结果说明。",
            ),
            "end_state_review": (
                "退出证据。",
                "退出态通过人物主动结束谈话并离场兑现，控制权变化已经可见。",
            ),
        }
        for field, (quote, note) in evidence.items():
            review[field].update(
                {"status": "realized", "evidence_quote": quote, "adaptation_note": note}
            )
        sequence_evidence = [
            ("动作一证据。", "第一条动作以当场追问异常完成换芯，保留了来源动作推进顺序。"),
            ("动作二证据。", "第二条动作以人物切断对话完成换芯，并在后一区域接续前一步。"),
        ]
        emotion_evidence = [
            ("情绪一证据。", "第一段情绪由疑问转成警觉，通过视线与错答后的判断显现。"),
            ("情绪二证据。", "第二段情绪由警觉落到离开决定，通过实际动作改变关系位置。"),
        ]
        for item, (quote, note) in zip(
            review["required_sequence_reviews"], sequence_evidence
        ):
            item.update(
                {"status": "realized", "evidence_quote": quote, "adaptation_note": note}
            )
        for item, (quote, note) in zip(
            review["emotion_sequence_reviews"], emotion_evidence
        ):
            item.update(
                {"status": "realized", "evidence_quote": quote, "adaptation_note": note}
            )
        layer_evidence = [
            (
                "前区补充证据甲。",
                "第一来源层仍以近景追问、错答和停顿运行，并在警觉形成的位置切向后层。",
            ),
            (
                "动作二证据。情绪二证据。",
                "第二来源层承接警觉后用动作切断对话并直接离场，层型和叙述距离均未改变。",
            ),
        ]
        for item, (quote, note) in zip(
            review["source_layer_reviews"], layer_evidence
        ):
            item.update(
                {"status": "realized", "evidence_quote": quote, "adaptation_note": note}
            )
        review["whole_chain_in_order"] = True
        review["whole_layer_topology_preserved"] = True
        review["technical_summary_rejected"] = True
        review["manual_judgment"] = (
            "两区正文从疑问进入、追问错答、动作切断到主动离场保持连续，"
            "动作顺序与情绪位移均未换序，也没有被职业流程或结果说明替代。"
        )
        return actual, expected

    def test_complete_cross_region_chain_passes(self) -> None:
        actual, expected = self.completed_review()
        self.assertEqual(
            [],
            INITIAL_REVIEW.validate_sf_chain_reviews(
                actual, expected, self.draft_regions
            ),
        )

    def test_missing_step_or_changed_requirement_blocks(self) -> None:
        actual, expected = self.completed_review()
        actual[0]["required_sequence_reviews"][1]["status"] = "partial"
        actual[0]["required_sequence_reviews"][0]["source_requirement"] = "泛化动作"
        actual[0]["required_sequence_reviews"][0]["target_ids"] = ["T-OTHER"]
        errors = INITIAL_REVIEW.validate_sf_chain_reviews(
            actual, expected, self.draft_regions
        )
        self.assertTrue(any("status 必须为 realized" in item for item in errors))
        self.assertTrue(any("source_requirement 必须与合同一致" in item for item in errors))
        self.assertTrue(any("target_ids 必须与写前 SF 绑定一致" in item for item in errors))

    def test_step_quote_must_come_from_bound_target_region(self) -> None:
        actual, expected = self.completed_review()
        actual[0]["required_sequence_reviews"][0]["evidence_quote"] = "动作二证据。"
        errors = INITIAL_REVIEW.validate_sf_chain_reviews(
            actual, expected, self.draft_regions
        )
        self.assertTrue(any("目标正文区域" in item for item in errors))

    def test_reused_evidence_and_template_note_blocks(self) -> None:
        actual, expected = self.completed_review()
        for item in actual[0]["required_sequence_reviews"]:
            item["evidence_quote"] = "前区补充证据甲。"
            item["adaptation_note"] = "两个动作步骤复用了同一套泛化说明，因此不能证明逐步完成换芯。"
        errors = INITIAL_REVIEW.validate_sf_chain_reviews(
            actual, expected, self.draft_regions
        )
        self.assertTrue(any("不得复用同一句" in item for item in errors))
        self.assertTrue(any("专属说明" in item for item in errors))

    def test_cross_region_chain_cannot_review_only_first_region(self) -> None:
        actual, expected = self.completed_review()
        second_region_items = (
            actual[0]["required_sequence_reviews"][1],
            actual[0]["emotion_sequence_reviews"][1],
            actual[0]["end_state_review"],
        )
        first_region_quotes = [
            "前区补充证据甲。",
            "前区补充证据乙。",
            "进入证据。动作一证据。",
        ]
        for item, quote in zip(second_region_items, first_region_quotes):
            item["evidence_quote"] = quote
        actual[0]["source_layer_reviews"][1]["evidence_quote"] = (
            "前区补充证据甲。"
        )
        errors = INITIAL_REVIEW.validate_sf_chain_reviews(
            actual, expected, self.draft_regions
        )
        self.assertTrue(any("未覆盖全部跨区落点" in item for item in errors))


class InitialReviewLengthPolicyTest(unittest.TestCase):
    def test_old_receipts_require_refresh_upgrade(self) -> None:
        old_schemas = {
            INITIAL_REVIEW.PREVIOUS_SCHEMA_VERSION,
            *INITIAL_REVIEW.LEGACY_SCHEMA_VERSIONS,
        }
        for schema in old_schemas:
            with self.subTest(schema=schema):
                errors = INITIAL_REVIEW.validate_data({"schema_version": schema})
                self.assertEqual(1, len(errors))
                self.assertIn("refresh-derived", errors[0])

    def test_hot_news_region_requires_current_draft_evidence(self) -> None:
        review = {
            "p_replacement_refs": ["SRC-PRIMARY:P-001"],
            "hot_news_refs": ["HN-001"],
            "plot_complete": True,
            "emotion_complete": True,
            "scene_complete": True,
            "voice_match": True,
            "granularity_dimension_reviews": [],
            "p_replacements_realized": True,
            "source_event_shell_rejected": True,
            "hot_news_mechanisms_realized": False,
        }
        self.assertFalse(INITIAL_REVIEW.region_review_complete(review))
        review["hot_news_mechanisms_realized"] = True
        self.assertTrue(INITIAL_REVIEW.region_review_complete(review))


class SourceHierarchyValidationTest(unittest.TestCase):
    def specs(self) -> list[dict]:
        emotion_beats = [
            {
                "beat_id": "E-001",
                "role": "第一次刺痛",
                "content": "公开掉位",
                "intensity": 7,
                "source_evidence": ["公开名单先出现了别人。"],
                "bid_ids": ["BID-01"],
            },
            {
                "beat_id": "E-002",
                "role": "决定离开",
                "content": "关闭关系入口",
                "intensity": 9,
                "source_evidence": ["她收回最后一项授权。"],
                "bid_ids": ["BID-02"],
            },
        ]
        bridge_rules = [
            {
                "id": "BID-01",
                "must_keep": ["公开掉位"],
                "emotion_sequence": [
                    {
                        "beat_id": "E-001",
                        "role": "第一次刺痛",
                        "content": "公开掉位",
                        "intensity": 7,
                        "source_evidence": "公开名单先出现了别人。",
                    }
                ],
            },
            {
                "id": "BID-02",
                "must_keep": ["关闭关系入口"],
                "emotion_sequence": [
                    {
                        "beat_id": "E-002",
                        "role": "决定离开",
                        "content": "关闭关系入口",
                        "intensity": 9,
                        "source_evidence": "她收回最后一项授权。",
                    }
                ],
            },
        ]
        return [
            {
                "source_id": "SRC-PRIMARY",
                "plot_beats": [
                    {"beat_id": "P-001", "bid_ids": ["BID-01"]},
                    {"beat_id": "P-002", "bid_ids": ["BID-02"]},
                ],
                "emotion_beats": emotion_beats,
                "prose_subflows": [],
                "hierarchy_assets": {
                    "profile": {"path": "profile", "sha256": "profile-sha"},
                    "story_core": {"path": "report", "sha256": "report-sha"},
                    "emotion_motherline": {
                        "path": "emotion-motherline",
                        "sha256": "emotion-motherline-sha",
                    },
                    "bridge_rules": bridge_rules,
                },
            }
        ]

    def test_profile_bridge_order_must_match_ledger_order(self) -> None:
        specs = self.specs()
        specs[0]["hierarchy_assets"]["bridge_rules"].reverse()

        with self.assertRaisesRegex(ValueError, "BID 完全同序"):
            OUTLINE.build_source_hierarchy(specs)

    def test_appended_ledger_bridge_is_derived_from_source_ledgers(self) -> None:
        specs = self.specs()
        specs[0]["plot_beats"].append(
            {"beat_id": "P-003", "action": "公开收回权限", "bid_ids": ["BID-03"]}
        )
        specs[0]["emotion_beats"].append(
            {
                "beat_id": "E-003",
                "role": "追加桥段",
                "content": "新增细分桥段",
                "intensity": 8,
                "source_evidence": ["她收回了权限。"],
                "bid_ids": ["BID-03"],
            }
        )

        hierarchy = OUTLINE.build_source_hierarchy(specs)

        self.assertEqual(["BID-01", "BID-02", "BID-03"], hierarchy["bridge_order"])
        derived = hierarchy["bridges"][2]["profile_rule"]
        self.assertTrue(derived["derived_from_ledgers"])
        self.assertEqual(["E-003"], [item["beat_id"] for item in derived["emotion_sequence"]])

    def test_profile_emotion_intensity_must_match_ledger(self) -> None:
        specs = self.specs()
        specs[0]["hierarchy_assets"]["bridge_rules"][0]["emotion_sequence"][0][
            "intensity"
        ] = 10

        with self.assertRaisesRegex(ValueError, "intensity 必须与 E 总账一致"):
            OUTLINE.build_source_hierarchy(specs)


class HotNewsValidationTest(unittest.TestCase):
    def replacement(
        self,
        source_ref: str = "SRC-PRIMARY:P-001",
        target_id: str = "T-1-001",
        news_ids: list[str] | None = None,
    ) -> dict:
        return {
            "source_ref": source_ref,
            "target_id": target_id,
            "target_evidence": "新事件",
            "preserved_function": "保留关系公开掉位并推动离开的承重功能",
            "changed_dimensions": ["setting", "evidence", "consequence"],
            "news_ids": news_ids if news_ids is not None else ["HN-001"],
            "adaptation_judgment": "目标事件使用新场景、新证据与现实后果制造同一情绪位移，已拒绝主体原文的人物动作和完整事件外壳。",
        }

    def material(
        self,
        published_at: str = "2026-08-10",
        news_id: str = "HN-001",
        publisher: str = "测试新闻社",
        host: str = "news.example.com",
        material_type: str = "social_news",
        social_heat_signal: str = "该话题进入平台热榜并引发多家媒体连续跟进讨论",
    ) -> dict:
        return {
            "news_id": news_id,
            "material_type": material_type,
            "title": "公开授权规则调整",
            "publisher": publisher,
            "published_at": published_at,
            "retrieved_at": "2026-08-19",
            "url": f"https://{host}/authorization",
            "social_heat_signal": social_heat_signal,
            "transferable_mechanism": f"{news_id} 的排他授权会被系统留痕并公开确认优先顺位",
            "fact_boundary": "只采用排他授权与系统留痕机制，真实人物、机构、时间线和具体后果均不进入正文",
        }

    def test_stale_news_is_not_accepted_as_hot_news(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material("2026-01-01")], [self.replacement()]
        )
        self.assertTrue(any("超过社会热点材料 90 天上限" in error for error in errors))

    def test_traceable_current_news_passes_for_single_p_beat(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material()], [self.replacement()]
        )
        self.assertEqual([], errors)

    def test_traceable_internet_meme_passes_for_single_p_beat(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material(material_type="internet_meme")], [self.replacement()]
        )
        self.assertEqual([], errors)

    def test_missing_social_heat_signal_is_rejected(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material(social_heat_signal="")], [self.replacement()]
        )
        self.assertTrue(any("social_heat_signal" in error for error in errors))

    def test_government_domain_is_rejected(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material(host="example.gov.cn")], [self.replacement()]
        )
        self.assertTrue(any("禁止使用政府/政务网站" in error for error in errors))

    def test_government_publisher_is_rejected(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material(publisher="某市应急管理局")], [self.replacement()]
        )
        self.assertTrue(any("禁止使用政府部门或监管机构" in error for error in errors))

    def test_search_engine_result_is_rejected(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material(host="news.google.com")], [self.replacement()]
        )
        self.assertTrue(any("禁止使用搜索引擎或聚合搜索结果" in error for error in errors))

    def test_no_hot_news_passes_when_user_did_not_request_it(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [], [self.replacement(news_ids=[])]
        )
        self.assertEqual([], errors)

    def test_two_news_must_land_on_two_distinct_p_beats(self) -> None:
        materials = [
            self.material(),
            self.material(
                news_id="HN-002",
                publisher="另一测试新闻社",
                host="other.example.com",
            ),
        ]
        replacements = [
            self.replacement(news_ids=["HN-001"]),
            self.replacement(
                source_ref="SRC-PRIMARY:P-002",
                target_id="T-1-002",
                news_ids=["HN-001"],
            ),
        ]

        errors = OUTLINE.validate_hot_news_materials(materials, replacements)

        self.assertTrue(any("不同社会热点材料必须分别落到" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
