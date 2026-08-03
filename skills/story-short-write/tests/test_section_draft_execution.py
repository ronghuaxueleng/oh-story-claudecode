from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_section_draft_execution.py"
SPEC = importlib.util.spec_from_file_location("section_draft_execution", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class SectionDraftExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "原文.txt"
        self.source.write_text("原文第一拍。原文第二拍。", encoding="utf-8")
        source_sha = GATE.sha256(self.source)
        binding = {
            "source_path": str(self.source.resolve()),
            "source_sha256": source_sha,
            "source_range": "L1-L1",
            "subflow_id": "SF-01",
            "source_evidence": ["原文第一拍", "原文第二拍"],
            "style_fields_consumed": [
                "narrative_voice_and_attitude",
                "sentence_relation_and_rhythm",
                "paragraph_breath_and_cut_points",
                "dialogue_misfire_or_avoidance",
                "action_perception_emotion_weave",
                "narrator_interjection_and_roughness",
            ],
        }
        self.outline = self.root / "细纲回执.json"
        self.outline.write_text(json.dumps({
            "gate_status": "passed",
            "sections": [
                {"section_id": "1", "first_draft_generation_contract": {"source_slice_bindings": [binding]}},
                {"section_id": "2", "first_draft_generation_contract": {"source_slice_bindings": [binding]}},
            ],
        }), encoding="utf-8")
        self.source_receipt = self.root / "拆文回执.json"
        self.source_receipt.write_text('{"gate_status":"passed","writing_mode":"direct_imitation"}', encoding="utf-8")
        self.bundle = self.root / "颗粒包.json"
        self.bundle.write_text(json.dumps({
            "gate": "section_source_bundle",
            "gate_status": "passed",
            "outline_contract": {"path": str(self.outline.resolve()), "sha256": GATE.sha256(self.outline)},
            "source_receipt": {"path": str(self.source_receipt.resolve()), "sha256": GATE.sha256(self.source_receipt)},
            "section_packet_ids": ["section-1", "section-2"],
            "packets": [
                {
                    "packet_id": "section-1",
                    "section_id": "1",
                    "packet_sha256": "a",
                    "payload": {
                        "source_slice_bindings": [
                            {
                                **binding,
                                "source_excerpt": "原文第一拍。原文第二拍。" * 20,
                            }
                        ],
                        "first_draft_generation_contract": {
                            "source_performance_excerpt": "原文第一拍。原文第二拍。",
                            "source_performance_evidence": ["原文第一拍", "原文第二拍"],
                            "emotion_process": {"entry_state": "入场"},
                            "source_style_granularity": {"voice": {"source_evidence": ["原文第一拍"]}},
                            "first_draft_style_plan": {"voice": "按原文口气迁移，不贴原句。"},
                            "anti_verbatim_transfer_contract": {
                                "preserve_axes": ["保事件密度", "保情绪次序"],
                                "rewrite_axes": ["改写原句", "改写对白壳"],
                                "forbidden_surface_reuse": ["原文第一拍"],
                                "allowed_evidence_usage": "只许校准颗粒，不许扩写原句。",
                                "manual_judgment": "必须重写句面。",
                            },
                            "sentence_relation_plan": ["先顶住再回刺"],
                            "paragraph_break_reasons": ["压痛后断段"],
                        },
                    },
                },
                {
                    "packet_id": "section-2",
                    "section_id": "2",
                    "packet_sha256": "b",
                    "payload": {
                        "source_slice_bindings": [
                            {
                                **binding,
                                "source_excerpt": "原文第一拍。原文第二拍。" * 20,
                            }
                        ],
                        "first_draft_generation_contract": {
                            "source_performance_excerpt": "原文第一拍。原文第二拍。",
                            "source_performance_evidence": ["原文第一拍", "原文第二拍"],
                            "emotion_process": {"entry_state": "入场"},
                            "source_style_granularity": {"voice": {"source_evidence": ["原文第一拍"]}},
                            "first_draft_style_plan": {"voice": "按原文口气迁移，不贴原句。"},
                            "anti_verbatim_transfer_contract": {
                                "preserve_axes": ["保事件密度", "保情绪次序"],
                                "rewrite_axes": ["改写原句", "改写对白壳"],
                                "forbidden_surface_reuse": ["原文第一拍"],
                                "allowed_evidence_usage": "只许校准颗粒，不许扩写原句。",
                                "manual_judgment": "必须重写句面。",
                            },
                            "sentence_relation_plan": ["先顶住再回刺"],
                            "paragraph_break_reasons": ["压痛后断段"],
                        },
                    },
                },
            ],
        }), encoding="utf-8")
        self.draft = self.root / "正文.md"
        self.receipt = self.root / "逐节回执.json"

    @staticmethod
    def read_judgment(packet_sha: str) -> str:
        return (
            "已完整读取 SF-01 L1-L1；"
            "narrative_voice_and_attitude "
            "sentence_relation_and_rhythm "
            "paragraph_breath_and_cut_points "
            "dialogue_misfire_or_avoidance "
            "action_perception_emotion_weave "
            "narrator_interjection_and_roughness "
            f"read_token={GATE.section_read_token(packet_sha)}"
        )

    @staticmethod
    def close_judgment() -> str:
        return (
            "event_flow=passed; emotion_flow=passed; style_granularity=passed; "
            "telegraphic_and_relation_check=passed; subflows=SF-01; "
            "style_fields_consumed=narrative_voice_and_attitude,sentence_relation_and_rhythm,"
            "paragraph_breath_and_cut_points,dialogue_misfire_or_avoidance,"
            "action_perception_emotion_weave,narrator_interjection_and_roughness; "
            "first_draft_contract=source_performance_excerpt,emotion_process,"
            "source_style_granularity,first_draft_style_plan,anti_verbatim_transfer_contract,"
            "sentence_relation_plan,paragraph_break_reasons"
        )

    @staticmethod
    def rich_section_content(title: str) -> str:
        paragraphs = [
            f"{title}第一段。她抬手拦住人群，先把流程压下去。",
            "“你先别哭。”她盯着对方，“现在跟我走。”",
            "他伸手来拽她，她反问：你凭什么拦我？你又想替谁担责？",
            "她猛地甩开他的手！人群一下静了，空气像被掐断。",
        ]
        payload = "\n\n".join(paragraphs)
        return payload + ("\n" + ("补足承载字数。" * 220))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_sequential_open_write_close_passes(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            self.draft.write_text("1.\n\n" + self.rich_section_content("第一节") + "\n", encoding="utf-8")
            self.assertEqual(0, GATE.close_section(self.receipt, "1", self.close_judgment()))
            self.assertEqual(0, GATE.open_section(self.receipt, "2", self.read_judgment("b")))
            self.draft.write_text(
                "1.\n\n" + self.rich_section_content("第一节") + "\n\n2.\n\n" + self.rich_section_content("第二节") + "\n",
                encoding="utf-8",
            )
            self.assertEqual(0, GATE.close_section(self.receipt, "2", self.close_judgment()))
            _, errors = GATE.validate_receipt(self.receipt, require_complete=True)
            self.assertEqual([], errors)

    def test_cannot_initialize_after_bulk_draft(self) -> None:
        self.draft.write_text("1.\n\n第一节。\n\n2.\n\n第二节。", encoding="utf-8")
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(2, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))

    def test_markdown_section_heading_is_recognized(self) -> None:
        self.draft.write_text(
            "## 第1节 包厢里，他先抓住了我的制服\n\n第一节正文。\n\n## 第2节 他追出来了\n\n第二节正文。\n",
            encoding="utf-8",
        )
        self.assertEqual(["1", "2"], GATE.draft_section_ids(self.draft))
        self.assertEqual("第一节正文。", GATE.section_text(self.draft, "1"))

    def test_compact_level_three_section_heading_is_recognized(self) -> None:
        self.draft.write_text(
            "###1.\n\n第一节正文。\n\n### 2.\n\n第二节正文。\n",
            encoding="utf-8",
        )
        self.assertEqual(["1", "2"], GATE.draft_section_ids(self.draft))
        self.assertEqual("第一节正文。", GATE.section_text(self.draft, "1"))

    def test_cannot_open_next_section_before_previous_close(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt)
            GATE.open_section(self.receipt, "1", self.read_judgment("a"))
            self.assertEqual(2, GATE.open_section(self.receipt, "2", self.read_judgment("b")))

    def test_open_and_close_section_skip_duplicate_static_revalidation(self) -> None:
        with mock.patch.object(
            GATE,
            "validate_outline_contract_receipt",
            return_value=[],
        ), mock.patch.object(
            GATE,
            "validate_section_source_bundle_receipt",
            return_value=[],
        ):
            self.assertEqual(
                0,
                GATE.init_receipt(
                    self.outline,
                    self.source_receipt,
                    self.bundle,
                    self.draft,
                    self.receipt,
                ),
            )
        with mock.patch.object(
            GATE,
            "validate_outline_contract_receipt",
            side_effect=AssertionError("open/close 不应重复深度校验 outline"),
        ), mock.patch.object(
            GATE,
            "validate_section_source_bundle_receipt",
            side_effect=AssertionError("open/close 不应重复深度校验 bundle"),
        ):
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            self.draft.write_text("1.\n\n" + self.rich_section_content("第一节") + "\n", encoding="utf-8")
            self.assertEqual(0, GATE.close_section(self.receipt, "1", self.close_judgment()))

    def test_cannot_initialize_when_outline_receipt_only_claims_passed(self) -> None:
        with mock.patch.object(
            GATE,
            "validate_outline_contract_receipt",
            return_value=["细纲表演验收回执实时复验失败: 第 1 节缺少 source_performance_excerpt"],
        ), mock.patch.object(GATE, "validate_section_source_bundle_receipt", return_value=[]):
            self.assertEqual(2, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))

    def test_cannot_initialize_when_bundle_only_claims_passed(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE,
            "validate_section_source_bundle_receipt",
            return_value=["逐节原文颗粒包实时复验失败: 第 1 节完整原文绑定与细纲生成契约不一致"],
        ):
            self.assertEqual(2, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))

    def test_close_section_blocks_when_judgment_missing_style_and_contract_markers(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            self.draft.write_text("1.\n\n" + self.rich_section_content("第一节") + "\n", encoding="utf-8")
            self.assertEqual(2, GATE.close_section(self.receipt, "1", "四项逐节停检通过"))

    def test_close_section_blocks_when_content_lacks_bound_style_signals(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            self.draft.write_text("1.\n\n" + ("平铺直叙的说明文字" * 260) + "\n", encoding="utf-8")
            self.assertEqual(2, GATE.close_section(self.receipt, "1", self.close_judgment()))

    def test_close_section_blocks_telegraphic_paragraph_dump(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            telegraphic = "\n\n".join(
                [
                    "第一节。她进门了。",
                    "灯很亮。",
                    "他站着。",
                    "女孩在哭。",
                    "她喊师母。",
                    "他去拽她。",
                    "她反问了。",
                    "她把人放倒。",
                    "后来去签字。",
                    "他又来求情。",
                    "她改口叫江先生。",
                    "她走了。",
                ]
            ) + ("\n\n" + ("补字数。" * 220))
            self.draft.write_text("1.\n\n" + telegraphic + "\n", encoding="utf-8")
            self.assertEqual(2, GATE.close_section(self.receipt, "1", self.close_judgment()))

    def test_reopen_allows_last_completed_section_when_later_sections_are_pending(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            self.draft.write_text("1.\n\n" + self.rich_section_content("第一节") + "\n", encoding="utf-8")
            self.assertEqual(0, GATE.close_section(self.receipt, "1", self.close_judgment()))

        self.assertEqual(0, GATE.reopen_section(self.receipt, "1"))
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual("pending", data["sections"][0]["status"])
        self.assertTrue(data["sections"][0]["revision_reopen"])
        self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertFalse(data["sections"][0]["revision_reopen"])

    def test_close_section_blocks_when_source_excerpt_line_coverage_too_low(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            diluted = (
                "1.\n\n"
                "她进场后先看见了不该看见的人，心里很冷，但还是努力维持秩序。"
                "她告诉自己先办事，不要被私人关系影响。"
                "空气很闷，灯很晃，周围人很多，她只能忍着。\n\n"
                "后来他追出来求情，她终于明白自己不是被优先考虑的那个。"
                "她把边界说清楚，也不想再多看他一眼。"
                + ("补字数。" * 260)
            )
            self.draft.write_text(diluted + "\n", encoding="utf-8")
            self.assertEqual(2, GATE.close_section(self.receipt, "1", self.close_judgment()))

    def test_required_sequence_has_zero_missing_beat_tolerance(self) -> None:
        bindings = [
            {
                "subflow_id": "SF-01",
                "source_subflow_contract": {
                    "required_sequence": [
                        "日程说法",
                        "善意返场",
                        "安静画面",
                        "身体信号",
                        "完成照护",
                        "压住爆发",
                    ]
                },
            }
        ]
        content = "日程说法后，她善意返场，看见安静画面。身体信号出现，他完成照护。"
        errors = GATE.validate_required_sequence_coverage(bindings, content)
        self.assertEqual(1, len(errors))
        self.assertIn("6 拍必须零遗漏", errors[0])
        self.assertIn("第6拍：压住爆发", errors[0])

    def test_required_sequence_passes_only_when_every_beat_is_present(self) -> None:
        bindings = [
            {
                "subflow_id": "SF-01",
                "source_subflow_contract": {
                    "required_sequence": ["冷静试探", "身体信号", "最后发现"]
                },
            }
        ]
        errors = GATE.validate_required_sequence_coverage(
            bindings,
            "她先冷静试探。身体信号让他转身照护，最后发现她也在场。",
        )
        self.assertEqual([], errors)

    def test_structured_beat_receipt_requires_unique_ordered_draft_evidence(self) -> None:
        bindings = [
            {
                "subflow_id": "SF-01",
                "source_subflow_contract": {
                    "required_sequence": ["冷静试探", "身体信号", "最后发现"]
                },
            }
        ]
        content = "她先问他今晚在哪。女孩忽然喘不上气，他立刻过去扶人。忙完后，他才看见门边的妻子。"
        receipts = [
            {
                "subflow_id": "SF-01",
                "beat_index": index,
                "source_beat": source_beat,
                "target_evidence": evidence,
                "causal_link": "本拍由前态触发动作，并直接造成下一拍。",
                "performance_equivalence": "保留原拍的动作优先级和关系刺痛。",
                "status": "passed",
            }
            for index, (source_beat, evidence) in enumerate(
                [
                    ("冷静试探", "她先问他今晚在哪。"),
                    ("身体信号", "女孩忽然喘不上气，他立刻过去扶人。"),
                    ("最后发现", "忙完后，他才看见门边的妻子。"),
                ],
                start=1,
            )
        ]
        self.assertEqual(
            [],
            GATE.validate_required_sequence_receipts(bindings, content, receipts),
        )
        receipts[2]["target_evidence"] = receipts[1]["target_evidence"]
        errors = GATE.validate_required_sequence_receipts(bindings, content, receipts)
        self.assertTrue(any("不得与其他拍重复" in error for error in errors))

    def test_structured_beat_receipt_preserves_sparse_source_indices(self) -> None:
        bindings = [
            {
                "subflow_id": "SF-02",
                "source_subflow_contract": {
                    "required_sequence": ["原第六拍", "原第七拍"],
                    "source_beat_indices": [6, 7],
                },
            }
        ]
        content = "她先落下原第六拍的动作。然后转入原第七拍的后果。"
        receipts = [
            {
                "subflow_id": "SF-02",
                "beat_index": 6,
                "source_beat": "原第六拍",
                "target_evidence": "她先落下原第六拍的动作。",
                "causal_link": "前态触发动作，动作造成下一拍。",
                "performance_equivalence": "保留原拍的人物偏手和情绪反应。",
                "status": "passed",
            },
            {
                "subflow_id": "SF-02",
                "beat_index": 7,
                "source_beat": "原第七拍",
                "target_evidence": "然后转入原第七拍的后果。",
                "causal_link": "上一拍结果触发本拍收束。",
                "performance_equivalence": "保留原拍的信息延迟与余痛。",
                "status": "passed",
            },
        ]

        self.assertEqual(
            [],
            GATE.validate_required_sequence_receipts(bindings, content, receipts),
        )
        receipts[0]["beat_index"] = 1
        errors = GATE.validate_required_sequence_receipts(bindings, content, receipts)
        self.assertTrue(any("SF-02#1" in error for error in errors))

    def test_structured_receipts_replace_verbatim_anchor_coverage(self) -> None:
        evidence = "她核对签字后，终于看清他先走向了谁。"
        binding = {
            "subflow_id": "SF-07",
            "source_subflow_contract": {
                "required_sequence": ["第一次越位接触时因现实习惯保留录音。"],
                "source_beat_indices": [1],
                "source_evidence": ["我的手机正开着录音。"],
                "control_changes": ["主角获得可复核权。"],
                "end_state": "材料已存在。",
            },
        }
        receipt = {
            "subflow_id": "SF-07",
            "beat_index": 1,
            "source_beat": "第一次越位接触时因现实习惯保留录音。",
            "target_evidence": evidence,
            "causal_link": "现场冲突触发核验，核验产生可复查记录。",
            "performance_equivalence": "保留先受伤再冷静核验的情绪转换。",
            "status": "passed",
        }
        target = {
            "source_slice_bindings": [binding],
            "required_sequence_receipts": [receipt],
        }

        self.assertTrue(GATE.validate_binding_anchor_coverage([binding], evidence))
        self.assertEqual(
            [],
            GATE.validate_close_content_signals(
                target,
                {"first_draft_generation_contract": {}},
                evidence,
            ),
        )

    def test_close_section_blocks_when_verbatim_source_lines_repeat(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(0, GATE.open_section(self.receipt, "1", self.read_judgment("a")))
            copied = (
                "1.\n\n"
                "原文第一拍。原文第二拍。原文第一拍。原文第二拍。"
                + ("补字数。" * 260)
            )
            self.draft.write_text(copied + "\n", encoding="utf-8")
            self.assertEqual(2, GATE.close_section(self.receipt, "1", self.close_judgment()))

    def test_open_section_blocks_when_read_judgment_missing_style_fields(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.assertEqual(2, GATE.open_section(self.receipt, "1", "已完整读取 SF-01 L1-L1"))

    def test_validate_receipt_blocks_stale_open_section_read_judgment(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            data = GATE.read_json(self.receipt)
            data["sections"][0]["status"] = "open"
            data["sections"][0]["opened_at"] = GATE.now_iso()
            data["sections"][0]["read_judgment"] = "已完整读取第1节全部原文切片与首写契约"
            GATE.write_json(self.receipt, data)
            _, errors = GATE.validate_receipt(self.receipt)
            self.assertTrue(any("open 状态的 read_judgment 失效" in error for error in errors))

    def test_validate_receipt_blocks_stale_completed_section_judgments(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            self.draft.write_text("1.\n\n" + self.rich_section_content("第一节") + "\n", encoding="utf-8")
            data = GATE.read_json(self.receipt)
            data["sections"][0].update(
                {
                    "status": "completed",
                    "opened_at": GATE.now_iso(),
                    "closed_at": GATE.now_iso(),
                    "read_judgment": "已完整读取第1节全部原文切片与首写契约",
                    "manual_judgment": "四项逐节停检通过",
                    "event_flow": "passed",
                    "emotion_flow": "passed",
                    "style_granularity": "passed",
                    "telegraphic_and_relation_check": "passed",
                    "section_sha256": GATE.hashlib.sha256(
                        GATE.section_text(self.draft, "1").encode("utf-8")
                    ).hexdigest(),
                    "draft_sha256_after_close": GATE.sha256(self.draft),
                }
            )
            GATE.write_json(self.receipt, data)
            _, errors = GATE.validate_receipt(self.receipt)
            self.assertTrue(any("已完成回执的 read_judgment 失效" in error for error in errors))
            self.assertTrue(any("已完成回执的 manual_judgment 失效" in error for error in errors))

    def test_reopen_section_resets_invalid_open_state_to_pending(self) -> None:
        with mock.patch.object(GATE, "validate_outline_contract_receipt", return_value=[]), mock.patch.object(
            GATE, "validate_section_source_bundle_receipt", return_value=[]
        ):
            self.assertEqual(0, GATE.init_receipt(self.outline, self.source_receipt, self.bundle, self.draft, self.receipt))
            data = GATE.read_json(self.receipt)
            data["sections"][0]["status"] = "open"
            data["sections"][0]["opened_at"] = GATE.now_iso()
            data["sections"][0]["read_judgment"] = "已完整读取第1节全部原文切片与首写契约"
            GATE.write_json(self.receipt, data)
            self.assertEqual(0, GATE.reopen_section(self.receipt, "1"))
            repaired = GATE.read_json(self.receipt)
            section = repaired["sections"][0]
            self.assertEqual("pending", section["status"])
            self.assertEqual("", section["read_judgment"])
            self.assertEqual("", section["opened_at"])


if __name__ == "__main__":
    unittest.main()
