from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
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
                    "schema_version": OUTLINE.SCHEMA_VERSION,
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

    def review(self, plot_refs: list[str], region_text: str | None = None) -> dict:
        text = self.region_text if region_text is None else region_text
        return {
            "content_sha256": INITIAL_REVIEW.text_sha256(text),
            "plot_refs": plot_refs,
            "emotion_refs": ["E-001"],
            "auxiliary_plot_refs": [],
            "prose_subflow_refs": ["SF-001"],
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


class InitialReviewLengthPolicyTest(unittest.TestCase):
    def test_target_char_range_is_not_a_draft_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "正文.md"
            outline = root / "小节大纲.md"
            contract_path = root / "细纲表演验收回执.json"
            config = root / "项目写作配置.json"
            source = root / "主体.txt"
            draft.write_text("# 《测试书》\n\n短导语。\n\n1.\n\n短节。\n", encoding="utf-8")
            outline.write_text("细纲", encoding="utf-8")
            config.write_text("{}", encoding="utf-8")
            source.write_text("主体引句一。主体引句二。主体引句三。", encoding="utf-8")
            contract = {
                "gate_status": "passed",
                "sources": [{"original": {"path": str(source)}}],
                "granularity_coverage": [],
                "outline_catalog": {
                    "regions": [
                        {
                            "region_id": "opening",
                            "target_chars": {"min": 5000, "max": 6000},
                        },
                        {
                            "region_id": "section:1",
                            "target_chars": {"min": 5000, "max": 6000},
                        },
                    ]
                },
            }
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False),
                encoding="utf-8",
            )

            regions = INITIAL_REVIEW.review_regions(draft.read_text(encoding="utf-8"))
            empty_refs = {
                key: {
                    "plot_refs": [],
                    "emotion_refs": [],
                    "auxiliary_plot_refs": [],
                    "prose_subflow_refs": [],
                    "p_replacement_refs": [],
                    "hot_news_refs": [],
                }
                for key in regions
            }
            reviews = [
                {
                    "region_id": region_id,
                    "content_sha256": INITIAL_REVIEW.text_sha256(text),
                    **empty_refs[region_id],
                    "plot_complete": True,
                    "emotion_complete": True,
                    "scene_complete": True,
                    "voice_match": True,
                    "p_replacements_realized": None,
                    "source_event_shell_rejected": None,
                    "hot_news_mechanisms_realized": None,
                    "evidence_quotes": [text],
                    "hot_news_evidence_quotes": [],
                    "manual_judgment": "已按场面、情绪、剧情与声线完整度人工确认通过，不以目标字数代替判断。",
                }
                for region_id, text in regions.items()
            ]
            data = {
                "schema_version": INITIAL_REVIEW.SCHEMA_VERSION,
                "project": "测试书",
                "bindings": {
                    "draft": INITIAL_REVIEW.binding(draft),
                    "outline": INITIAL_REVIEW.binding(outline),
                    "outline_contract": INITIAL_REVIEW.binding(contract_path),
                    "project_config": INITIAL_REVIEW.binding(config),
                },
                "region_reviews": reviews,
                "global_review": {
                    "primary_voice_exclusive": True,
                    "auxiliary_voice_rejected": True,
                    "title_promise_fulfilled": True,
                    "opening_bearing_passed": True,
                    "ending_consequence_passed": True,
                    "long_sentence_breath_reviewed": True,
                    "dialogue_efficiency_reviewed": True,
                    "all_primary_prose_subflows_covered": True,
                    "full_story_hierarchy_preserved": True,
                    "all_primary_p_beats_replaced": True,
                    "all_hot_news_mechanisms_realized": None,
                    "source_event_shell_rejected_globally": True,
                    "news_fact_and_privacy_boundary_reviewed": None,
                    "source_voice_quotes": ["主体引句一。", "主体引句二。", "主体引句三。"],
                    "draft_voice_quotes": ["测试书", "短导语。", "短节。"],
                    "voice_comparison": "主体原文与正文在叙述距离、句间转折、段落气口和即时主观声音上保持同源机制，同时没有复制原句和事件外壳。对白轮转仍由人物关系和现场动作推动，辅助来源也没有进入句式、语气或叙述者声音。",
                    "final_judgment": "全文已完成题面、开头、结尾后果、对白效率、长句换气和来源边界的人工终审，不存在需要依靠补字解决的场面问题。区域中的情节、情绪和声线完整度均由真实引句与人工判断支撑，目标字数只作写前参考。",
                },
                "summary": {
                    "draft_nonspace_chars": INITIAL_REVIEW.nonspace_count(
                        draft.read_text(encoding="utf-8")
                    ),
                    "reviewed_regions": len(regions),
                },
            }
            with mock.patch.object(
                INITIAL_REVIEW.OUTLINE,
                "validate_receipt",
                return_value=[],
            ), mock.patch.object(
                INITIAL_REVIEW,
                "required_refs_by_review_region",
                return_value=empty_refs,
            ):
                errors = INITIAL_REVIEW.validate_data(data)

        self.assertEqual([], errors)

    def test_hot_news_region_requires_current_draft_evidence(self) -> None:
        review = {
            "p_replacement_refs": ["SRC-PRIMARY:P-001"],
            "hot_news_refs": ["HN-001"],
            "plot_complete": True,
            "emotion_complete": True,
            "scene_complete": True,
            "voice_match": True,
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
    ) -> dict:
        return {
            "news_id": news_id,
            "title": "公开授权规则调整",
            "publisher": publisher,
            "published_at": published_at,
            "retrieved_at": "2026-08-19",
            "url": f"https://{host}/authorization",
            "transferable_mechanism": f"{news_id} 的排他授权会被系统留痕并公开确认优先顺位",
            "fact_boundary": "只采用排他授权与系统留痕机制，真实人物、机构、时间线和具体后果均不进入正文",
        }

    def test_stale_news_is_not_accepted_as_hot_news(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material("2026-01-01")], [self.replacement()]
        )
        self.assertTrue(any("超过热点新闻 90 天上限" in error for error in errors))

    def test_traceable_current_news_passes_for_single_p_beat(self) -> None:
        errors = OUTLINE.validate_hot_news_materials(
            [self.material()], [self.replacement()]
        )
        self.assertEqual([], errors)

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

        self.assertTrue(any("不同热点新闻必须分别落到" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
