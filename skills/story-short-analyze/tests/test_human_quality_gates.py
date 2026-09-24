from __future__ import annotations

import json
import hashlib

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_short_analyze_outputs.py"
)
SPEC = importlib.util.spec_from_file_location("short_analyze_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

FINALIZER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_short_analyze_finalize.py"
)
FINALIZER_SPEC = importlib.util.spec_from_file_location("short_analyze_finalizer", FINALIZER_PATH)
assert FINALIZER_SPEC and FINALIZER_SPEC.loader
FINALIZER = importlib.util.module_from_spec(FINALIZER_SPEC)
FINALIZER_SPEC.loader.exec_module(FINALIZER)

PREPARER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "prepare_short_analyze_job.py"
)
PREPARER_SPEC = importlib.util.spec_from_file_location("short_analyze_preparer", PREPARER_PATH)
assert PREPARER_SPEC and PREPARER_SPEC.loader
PREPARER = importlib.util.module_from_spec(PREPARER_SPEC)
sys.modules[PREPARER_SPEC.name] = PREPARER
PREPARER_SPEC.loader.exec_module(PREPARER)

FOUNDATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_short_analyze_foundation.py"
)
FOUNDATION_SPEC = importlib.util.spec_from_file_location(
    "short_analyze_foundation_validator",
    FOUNDATION_PATH,
)
assert FOUNDATION_SPEC and FOUNDATION_SPEC.loader
FOUNDATION = importlib.util.module_from_spec(FOUNDATION_SPEC)
FOUNDATION_SPEC.loader.exec_module(FOUNDATION)

TIMING_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "record_short_analyze_timing.py"
)
TIMING_SPEC = importlib.util.spec_from_file_location(
    "short_analyze_timing",
    TIMING_PATH,
)
assert TIMING_SPEC and TIMING_SPEC.loader
TIMING = importlib.util.module_from_spec(TIMING_SPEC)
TIMING_SPEC.loader.exec_module(TIMING)


class HumanQualityGateTest(unittest.TestCase):
    def test_metadata_match_requires_the_whole_line(self) -> None:
        self.assertIsNone(VALIDATOR.BOOK_METADATA_LINE_RE.match("完事觉得自己肯定要坐牢了。"))
        self.assertIsNotNone(VALIDATOR.BOOK_METADATA_LINE_RE.match("（全文完）"))
        self.assertIsNotNone(VALIDATOR.BOOK_METADATA_LINE_RE.match("全文完结"))
        self.assertIsNotNone(VALIDATOR.BOOK_METADATA_LINE_RE.match("- 完 -"))
        self.assertIsNotNone(VALIDATOR.SUBFLOW.BOOK_METADATA_LINE_RE.match("- 完 -"))

    def test_subflow_rejects_dynamic_required_sequence_shell(self) -> None:
        self.assertTrue(
            VALIDATOR.SUBFLOW.is_generic_required_sequence(
                ["沈阙先处理一段原文截句", "关系或信息发生一次可见换位"]
            )
        )
        self.assertFalse(
            VALIDATOR.SUBFLOW.is_generic_required_sequence(
                ["香囊坠地后沈阙弯腰重捡", "童养夫旧约公开封死良娣入口"]
            )
        )

    def test_subflow_merge_rejects_declared_layer_order_from_another_sf(self) -> None:
        errors: list[str] = []
        rows = [
            {
                "subflow_id": "SF-30",
                "source_layer_order": ["SF-12-L01"],
            },
            {
                "record_type": "source_layer",
                "schema_version": VALIDATOR.SUBFLOW.SCHEMA_VERSION,
                "subflow_id": "SF-30",
                "layer": {"layer_id": "SF-30-L01"},
            },
        ]
        VALIDATOR.SUBFLOW.merge_normalized_layer_records(rows, errors)
        self.assertTrue(any("声明与规范化来源层不一致" in error for error in errors), errors)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def _write_full_emotion_ledger(self) -> tuple[list[str], Path]:
        source_lines = ["导语里的刺痛。", "普通过场。", "尾声仍然没有回头。"]
        source_sha1 = hashlib.sha1("\n".join(source_lines).encode("utf-8")).hexdigest()
        self._write(
            "_source_manifest.json",
            json.dumps({"copied_sha1": source_sha1}, ensure_ascii=False),
        )
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir(parents=True, exist_ok=True)
        ledger = asset_dir / "全文情绪颗粒总账.json"
        ledger.write_text(
            json.dumps(
                {
                    "schema_version": VALIDATOR.FULL_TEXT_EMOTION_LEDGER_SCHEMA,
                    "source": {"sha1": source_sha1, "line_count": 3},
                    "coverage_segments": [
                        {
                            "segment_id": "SEG-01",
                            "start_line": 1,
                            "end_line": 1,
                            "kind": "emotion_bearing",
                            "beat_ids": ["E-01"],
                        },
                        {
                            "segment_id": "SEG-02",
                            "start_line": 2,
                            "end_line": 2,
                            "kind": "non_emotional_support",
                            "beat_ids": [],
                            "reason": "这一行只承担时间和空间衔接，没有关系位置变化。",
                        },
                        {
                            "segment_id": "SEG-03",
                            "start_line": 3,
                            "end_line": 3,
                            "kind": "emotion_bearing",
                            "beat_ids": ["E-02"],
                        },
                    ],
                    "source_emotion_candidate_audit": [
                        {
                            "candidate_id": "EC-001",
                            "change_axis": "关系位置与读者预期",
                            "before_state": "主角仍被默认处在旧关系中。",
                            "after_state": "主角被确认已经遭到关系伤害。",
                            "source_range": {"start_line": 1, "end_line": 1},
                            "source_evidence": "导语里的刺痛。",
                            "decision": "independent_beat",
                            "bound_beat_ids": ["E-01"],
                            "manual_judgment": "这句改变关系位置与读者预期，需要独立登记为情绪拍。",
                        },
                        {
                            "candidate_id": "EC-002",
                            "change_axis": "行动冲动与尾声余痛",
                            "before_state": "旧关系仍可能要求主角回头。",
                            "after_state": "主角完成离场且不再回头。",
                            "source_range": {"start_line": 3, "end_line": 3},
                            "source_evidence": "尾声仍然没有回头。",
                            "decision": "independent_beat",
                            "bound_beat_ids": ["E-02"],
                            "manual_judgment": "这句改变行动冲动并形成尾声余痛，需要独立登记。",
                        },
                    ],
                    "beats": [
                        {
                            "beat_id": "E-01",
                            "segment_id": "SEG-01",
                            "start_line": 1,
                            "end_line": 1,
                            "role": "导语刺痛",
                            "content": "主角在导语先承认关系伤害。",
                            "trigger": "旧关系被一句话重新提起。",
                            "relationship_position_change": "主角从默认被爱者跌成被舍弃者。",
                            "reader_effect": "读者立刻感到关系不对等。",
                            "narrative_function": "开场挂住伤害结果。",
                            "intensity": 7,
                            "bid_ids": ["BID-01"],
                            "source_evidence": ["导语里的刺痛。"],
                        },
                        {
                            "beat_id": "E-02",
                            "segment_id": "SEG-03",
                            "start_line": 3,
                            "end_line": 3,
                            "role": "尾声余痛",
                            "content": "主角已经离开，但仍确认不会回头。",
                            "trigger": "尾声再次面对旧关系。",
                            "relationship_position_change": "主角彻底退出旧关系。",
                            "reader_effect": "读者得到切断后的余痛。",
                            "narrative_function": "尾声完成情绪收口。",
                            "intensity": 6,
                            "bid_ids": [],
                            "source_evidence": ["尾声仍然没有回头。"],
                        },
                    ],
                    "completeness_review": {
                        "read_start_line": 1,
                        "read_end_line": 3,
                        "all_source_lines_classified": True,
                        "non_bid_beats_preserved": True,
                        "bid_derived_after_full_inventory": True,
                        "reviewed_by_current_model": True,
                        "automation_used_for_semantic_judgment": False,
                        "forward_expectation_scan_completed": True,
                        "reverse_afterpain_scan_completed": True,
                        "all_source_emotion_candidates_adjudicated": True,
                        "split_basis": "逐行读取后，按期待、关系位置、行动冲动和读者预期的每次变化分别切拍。",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return source_lines, ledger

    def _write_full_plot_ledger(self) -> tuple[list[str], Path, dict]:
        source_lines, emotion_ledger_path = self._write_full_emotion_ledger()
        original = self.root / "原文" / "测试.txt"
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text("\n".join(source_lines), encoding="utf-8")
        emotion_ledger = json.loads(emotion_ledger_path.read_text(encoding="utf-8"))
        ledger = self.root / "写作资产" / "全文情节微拍总账.json"
        ledger.write_text(
            json.dumps(
                {
                    "schema_version": VALIDATOR.FULL_TEXT_PLOT_LEDGER_SCHEMA,
                    "source": {
                        "path": str(original.resolve()),
                        "sha1": hashlib.sha1(original.read_bytes()).hexdigest(),
                        "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                        "line_count": len(source_lines),
                    },
                    "coverage_segments": [
                        {"segment_id":"PSEG-01","start_line":1,"end_line":1,"kind":"plot_bearing","candidate_ids":["PC-001"]},
                        {"segment_id":"PSEG-02","start_line":2,"end_line":2,"kind":"non_plot_support","candidate_ids":[],"reason":"这一行只承担普通时间衔接，没有动作、信息或控制权变化。"},
                        {"segment_id":"PSEG-03","start_line":3,"end_line":3,"kind":"plot_bearing","candidate_ids":["PC-002"]}
                    ],
                    "source_plot_candidate_audit": [
                        {"candidate_id":"PC-001","candidate_type":"独立关系动作","actor":"主角","source_range":{"start_line":1,"end_line":1},"source_evidence":"导语里的刺痛。","decision":"independent_beat","bound_beat_ids":["P-001"],"manual_judgment":"这句改变关系事实与回应权，需要独立登记为情节拍。"},
                        {"candidate_id":"PC-002","candidate_type":"完成离场动作","actor":"主角","source_range":{"start_line":3,"end_line":3},"source_evidence":"尾声仍然没有回头。","decision":"independent_beat","bound_beat_ids":["P-002"],"manual_judgment":"这句完成不可逆离场后果，需要独立登记为情节拍。"}
                    ],
                    "source_emotion_candidate_audit": [
                        {"candidate_id":"EC-001","change_axis":"关系位置与读者预期","before_state":"主角仍被默认处在旧关系中。","after_state":"主角被确认已经遭到关系伤害。","source_range":{"start_line":1,"end_line":1},"source_evidence":"导语里的刺痛。","decision":"independent_beat","bound_beat_ids":["E-01"],"manual_judgment":"这句改变关系位置与读者预期，需要独立登记为情绪拍。"},
                        {"candidate_id":"EC-002","change_axis":"行动冲动与尾声余痛","before_state":"旧关系仍可能要求主角回头。","after_state":"主角完成离场且不再回头。","source_range":{"start_line":3,"end_line":3},"source_evidence":"尾声仍然没有回头。","decision":"independent_beat","bound_beat_ids":["E-02"],"manual_judgment":"这句改变行动冲动并形成尾声余痛，需要独立登记。"}
                    ],
                    "beats": [
                        {
                            "beat_id": "P-001",
                            "actor": "主角",
                            "action": "主角当场承认关系已经破裂",
                            "object_or_receiver": "旧关系中的另一人",
                            "pressure_or_trigger": "旧关系被重新提起",
                            "control_change": "主角夺回是否回应的决定权",
                            "information_change": "读者知道关系已经破裂",
                            "consequence": "主角不再维持旧关系",
                            "source_range": {"start_line": 1, "end_line": 1},
                            "source_evidence": "导语里的刺痛。",
                            "bid_ids": ["BID-01"],
                        },
                        {
                            "beat_id": "P-002",
                            "actor": "主角",
                            "action": "主角在尾声完成离场",
                            "object_or_receiver": "旧关系现场",
                            "pressure_or_trigger": "主角再次面对旧关系",
                            "control_change": "旧关系失去对主角的挽留权",
                            "information_change": "对方确认主角不会回头",
                            "consequence": "离开成为无法撤回的现实后果",
                            "source_range": {"start_line": 3, "end_line": 3},
                            "source_evidence": "尾声仍然没有回头。",
                            "bid_ids": [],
                        },
                    ],
                    "completeness_review": {
                        "full_text_scanned_l1_to_eof": True,
                        "independent_from_emotion_ledger": True,
                        "no_emotion_beat_substitution": True,
                        "all_effective_plot_beats_preserved": True,
                        "forward_action_scan_completed": True,
                        "reverse_consequence_scan_completed": True,
                        "all_source_candidates_adjudicated": True,
                        "reviewed_by_current_model": True,
                        "forward_expectation_scan_completed": True,
                        "reverse_afterpain_scan_completed": True,
                        "all_source_emotion_candidates_adjudicated": True,
                        "automation_used_for_semantic_judgment": False,
                        "manual_judgment": "已从施事者、对象、控制权、信息和现实后果独立切拍。",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return source_lines, ledger, emotion_ledger

    def test_full_plot_ledger_passes_when_independently_built(self) -> None:
        source_lines, _, emotion_ledger = self._write_full_plot_ledger()
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertEqual([], errors)

    def test_full_plot_ledger_rejects_generic_semantic_scaffold(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"][0]["action"] = "完成本行所载动作、话轮或叙事推进"
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("禁用概括占位句" in error for error in errors))

    def test_full_emotion_ledger_rejects_generic_semantic_scaffold(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"][0]["role"] = "逐行情绪与预期位移"
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)
        self.assertTrue(any("禁用概括占位句" in error for error in errors))

    def test_plot_ledger_rejects_source_quote_inside_fixed_sentence_frame(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"][0]["information_change"] = "第1行新增事实：导语里的刺痛。"
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("原文嵌入固定句式" in error for error in errors))

    def test_emotion_ledger_rejects_line_number_inside_fixed_sentence_frame(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"][0]["trigger"] = "L1 的具体刺激：导语里的刺痛。"
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)
        self.assertTrue(any("原文嵌入固定句式" in error for error in errors))

    def test_plot_ledger_rejects_raw_quote_as_action(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"][0]["action"] = "看见“导语里的刺痛。”"
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("原文嵌入固定句式" in error for error in errors))

    def test_emotion_ledger_rejects_quote_swapped_generic_frames(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        beat = data["beats"][0]
        beat["trigger"] = "场景中的新事实或回忆触发：导语里的刺痛。"
        beat["relationship_position_change"] = (
            "从短暂松弛移动到旧伤回响，关系距离出现可感变化"
        )
        beat["reader_effect"] = (
            "读者先接收“导语里的刺痛”的表层，再等待其后果兑现"
        )
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)
        self.assertTrue(any("trigger 使用原文嵌入固定句式" in error for error in errors))
        self.assertTrue(
            any("relationship_position_change 使用原文嵌入固定句式" in error for error in errors)
        )
        self.assertTrue(any("reader_effect 使用原文嵌入固定句式" in error for error in errors))

    def test_cloud_style_six_line_scaffolds_are_rejected(self) -> None:
        plot_beats = [{
            "action": "交付“他推门进来”这一步局势变化",
            "pressure_or_trigger": "此前场景推进到L7，他推门进来",
        }]
        emotion_beats = [{
            "content": "她因“他推门进来”从上一状态进入警觉抬升",
            "trigger": "L7出现的施压话轮直接触发这次位移",
            "relationship_position_change": "她在这段中被迫重新判断对方与自身距离",
            "reader_effect": "“他推门进来”让读者在本段末确认警觉抬升已经落地",
        }]
        plot_hits = VALIDATOR.collect_ledger_pattern_hits(
            plot_beats, VALIDATOR.PLOT_LEDGER_FORBIDDEN_SCAFFOLD_PATTERNS
        )
        emotion_hits = VALIDATOR.collect_ledger_pattern_hits(
            emotion_beats, VALIDATOR.EMOTION_LEDGER_FORBIDDEN_SCAFFOLD_PATTERNS
        )
        self.assertEqual(1, plot_hits["action"])
        self.assertEqual(1, plot_hits["pressure_or_trigger"])
        self.assertEqual(1, emotion_hits["content"])
        self.assertEqual(1, emotion_hits["trigger"])
        self.assertEqual(1, emotion_hits["relationship_position_change"])
        self.assertEqual(1, emotion_hits["reader_effect"])

    def test_repetitive_plot_sentence_frames_are_detected(self) -> None:
        beats = [
            {"pressure_or_trigger": f"前拍留下的压力在‘证据{i}’处被接住"}
            for i in range(10)
        ]
        hits = VALIDATOR.collect_ledger_pattern_hits(
            beats, VALIDATOR.PLOT_LEDGER_REPETITIVE_SCAFFOLD_PATTERNS
        )
        self.assertEqual(10, hits["pressure_or_trigger"])

    def test_plot_ledger_rejects_rotating_exact_semantic_categories(self) -> None:
        beats = [
            {
                "pressure_or_trigger": "双方给同一动作相反解释",
                "control_change": "误读者据自己的剧本先行动",
                "information_change": "表层言行和真实意图裂开",
            }
            for _ in range(16)
        ]
        hits = VALIDATOR.collect_excessive_exact_repetitions(
            beats,
            ("pressure_or_trigger", "control_change", "information_change"),
        )
        self.assertEqual(16, hits["pressure_or_trigger"][1])
        self.assertEqual(16, hits["control_change"][1])
        self.assertEqual(16, hits["information_change"][1])

    def test_repetitive_emotion_sentence_frames_are_detected(self) -> None:
        beats = [
            {"reader_effect": f"读者先沿旧剧本误判，再被证据{i}迫使改判"}
            for i in range(10)
        ]
        hits = VALIDATOR.collect_ledger_pattern_hits(
            beats, VALIDATOR.EMOTION_LEDGER_REPETITIVE_SCAFFOLD_PATTERNS
        )
        self.assertEqual(10, hits["reader_effect"])

    def test_plot_ledger_rejects_action_copied_into_object_field(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        template = data["beats"][0]
        data["beats"] = []
        for index in range(8):
            beat = dict(template)
            beat["beat_id"] = f"P-{index + 1:02d}"
            beat["action"] = f"动作{index}"
            beat["object_or_receiver"] = f"动作{index}"
            data["beats"].append(beat)
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("跨字段复制" in error for error in errors))

    def test_direct_table_rejects_literal_asset_placeholder(self) -> None:
        path = self._write(
            "可直接仿写_顺序事件表.md",
            "# 顺序事件表\n|资产|功能|读者情绪|烈度|峰值|余痛|迁移提醒|\n"
            "|---|---|---|---|---|---|---|\n"
            "|顺序事件表资产1|推进|紧张|3|否|无|替换人物与场景|\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 1, errors)
        self.assertTrue(any("字面资产占位符" in error for error in errors))

    def test_detail_libraries_reject_cross_category_copy(self) -> None:
        detail_dir = self.root / "原文细节库"
        detail_dir.mkdir()
        block = (
            "# 细节库\n\n## 同一张卡\n"
            "- 具体发生了什么：同一场景被重复搬运。\n"
            "- 这个细节为什么有用：测试。\n"
            "- 它压的是谁、压在哪：测试。\n"
            "- 后续能迁到什么新桥段：测试。\n"
            "- 它对应的角色 / 情绪 / 反转是什么：测试。\n"
        )
        for filename in VALIDATOR.DETAIL_LIBRARY_FILES[:4]:
            (detail_dir / filename).write_text(block, encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_detail_library_cross_category_overlap(detail_dir, errors)
        self.assertTrue(any("必须按语义分库" in error for error in errors))

    def test_full_plot_ledger_rejects_all_book_plot_bucket_with_structural_marker(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        source_lines[1] = "1"
        original = self.root / "原文" / "测试.txt"
        original.write_text("\n".join(source_lines), encoding="utf-8")
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["source"].update(
            {
                "sha1": hashlib.sha1(original.read_bytes()).hexdigest(),
                "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
            }
        )
        data["coverage_segments"] = [
            {
                "segment_id": "PSEG-ALL",
                "start_line": 1,
                "end_line": 3,
                "kind": "plot_bearing",
                "candidate_ids": ["PC-001", "PC-002"],
            }
        ]
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )

        self.assertTrue(any("必须单列 structural_marker" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_plot_line_outside_candidate_ranges(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["coverage_segments"][1] = {
            "segment_id": "PSEG-02",
            "start_line": 2,
            "end_line": 2,
            "kind": "plot_bearing",
            "candidate_ids": [],
        }
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )

        self.assertTrue(any("未进入任何源文候选行域" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_emotion_id_reuse(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"][0]["beat_id"] = "E-01"
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("共用 beat_id" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_emotion_content_as_action(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"][0]["action"] = emotion_ledger["beats"][0]["content"]
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("复制了情绪总账内容" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_missing_source_candidate_audit(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["source_plot_candidate_audit"] = []
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("源文候选反查" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_candidate_bound_to_missing_beat(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["source_plot_candidate_audit"][0]["bound_beat_ids"] = ["P-404"]
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("不存在的 P 拍" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_dynamic_quote_candidate_scaffold(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["source_plot_candidate_audit"][0]["manual_judgment"] = (
            "“推开房门并拿走钥匙”独立改变持有、知情、名分或现实后果，"
            "删除会切断后续因果。"
        )
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )

        self.assertTrue(any("候选审计固定句壳" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_merge_reason_on_independent_candidate(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["source_plot_candidate_audit"][0]["merge_reason"] = (
            "这条被误填了只应属于合并候选的理由。"
        )
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )

        self.assertTrue(any("independent_beat 不得填写 merge_reason" in error for error in errors), errors)

    def test_full_plot_ledger_rejects_candidate_beat_one_to_one_mirror(self) -> None:
        source_lines, ledger, emotion_ledger = self._write_full_plot_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        template_beat = data["beats"][0]
        template_candidate = data["source_plot_candidate_audit"][0]
        data["beats"] = []
        data["source_plot_candidate_audit"] = []
        for index in range(1, 13):
            beat_id = f"P-{index:03d}"
            data["beats"].append(dict(template_beat, beat_id=beat_id))
            data["source_plot_candidate_audit"].append(
                dict(
                    template_candidate,
                    candidate_id=f"PC-{index:03d}",
                    bound_beat_ids=[beat_id],
                )
            )
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_plot_ledger(
            self.root, source_lines, errors, emotion_ledger
        )
        self.assertTrue(any("等量同序一对一镜像" in error for error in errors), errors)

    def test_full_emotion_ledger_rejects_line_coverage_gap(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["coverage_segments"].pop(1)
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)
        self.assertTrue(any("行覆盖不连续" in error for error in errors), errors)

    def test_full_emotion_ledger_rejects_emotion_line_outside_candidate_ranges(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["coverage_segments"][1] = {
            "segment_id": "SEG-02",
            "start_line": 2,
            "end_line": 2,
            "kind": "emotion_bearing",
            "beat_ids": ["E-01"],
            "reason": "本行被声明为情绪承载行，必须有候选行域实际承接。",
        }
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)

        self.assertTrue(any("未进入任何源文情绪候选行域" in error for error in errors), errors)

    def test_full_emotion_ledger_rejects_dropped_non_bid_beat(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["beats"].pop()
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)
        self.assertTrue(any("与 beats 全集同序相等" in error for error in errors), errors)

    def test_full_emotion_ledger_rejects_candidate_beat_one_to_one_mirror(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        template_beat = data["beats"][0]
        template_candidate = data["source_emotion_candidate_audit"][0]
        data["beats"] = []
        data["source_emotion_candidate_audit"] = []
        for index in range(1, 13):
            beat_id = f"E-{index:03d}"
            data["beats"].append(dict(template_beat, beat_id=beat_id))
            data["source_emotion_candidate_audit"].append(
                dict(
                    template_candidate,
                    candidate_id=f"EC-{index:03d}",
                    bound_beat_ids=[beat_id],
                )
            )
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)
        self.assertTrue(any("等量同序一对一镜像" in error for error in errors), errors)

    def test_full_emotion_ledger_rejects_dynamic_role_candidate_scaffold(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["source_emotion_candidate_audit"][0]["manual_judgment"] = (
            "“开场关系刺痛”使期待对象、关系位置或行动权限发生不可逆变化，"
            "需独立保留。"
        )
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)

        self.assertTrue(any("候选审计固定句壳" in error for error in errors), errors)

    def test_full_emotion_ledger_rejects_merge_reason_on_independent_candidate(self) -> None:
        source_lines, ledger = self._write_full_emotion_ledger()
        data = json.loads(ledger.read_text(encoding="utf-8"))
        data["source_emotion_candidate_audit"][0]["merge_reason"] = (
            "这条被误填了只应属于合并候选的理由。"
        )
        ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_full_text_emotion_ledger(self.root, source_lines, errors)

        self.assertTrue(any("independent_beat 不得填写 merge_reason" in error for error in errors), errors)

    def test_large_direct_table_requires_tiers(self) -> None:
        rows = "\n".join(
            f"| 资产{i} | 原文证据{i} | 迁移{i} |" for i in range(1, 7)
        )
        path = self._write(
            "可直接仿写_物件表.md",
            "| 物件 | 原文证据 | 迁移提醒 |\n|---|---|---|\n"
            + rows
            + "\n## 可直接借的承重结构\n- 资产1和资产2\n- 资产3和资产4\n"
            "## 迁移顺序提醒\n- 资产1再资产2\n- 资产3再资产4\n"
            "## 为什么这个顺序不能乱\n- 资产1不能晚于资产2\n- 资产3不能晚于资产4\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("必须增加 `层级/资产等级`" in error for error in errors))

    def test_direct_table_requires_minimum_rows_for_long_samples(self) -> None:
        path = self._write(
            "可直接仿写_钩子表.md",
            "| 位置 | 钩子内容 | 钩子类型 | 回收位置 | 原文证据 | 迁移提醒 |\n"
            "|---|---|---|---|---|---|\n"
            "| 场末 | 电话被第三人接起 | 信息差 | 医院桥 | 老师他太累睡着了 | 先埋代接再回收 |\n"
            "| 章尾 | 法庭见 | 程序闸门 | 离婚桥 | 我们法庭见吧 | 情绪尾部挂程序 |\n"
            "| 尾声 | 从此是路人 | 收口钩子 | 全文结束 | 从此是路人 | 结尾承担切断 |\n"
            "| 场末 | 门锁失效 | 私域悬念 | 旧宅桥 | 钥匙怎么都塞不进去 | 先卡门再开门 |\n"
            "## 可直接借的承重结构\n- `电话被第三人接起` 先挂住信息差，`法庭见` 再把争执送进秩序。\n"
            "- `从此是路人` 负责收口，不和前两条争抢中段位置。\n"
            "## 迁移顺序提醒\n- 先 `电话被第三人接起`，再 `法庭见`，最后 `从此是路人`。\n"
            "- 如果中段还有公开桥，应该补在前两条之间，不要直接跳收口。\n"
            "## 为什么这个顺序不能乱\n- 如果把 `法庭见` 抢到 `电话被第三人接起` 前面，信息差就还没长出来。\n"
            "- 如果把 `从此是路人` 提前，尾声切断会变成空喊口号。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("表格承重不足" in error for error in errors))

    def test_direct_table_rejects_too_many_core_assets(self) -> None:
        rows = "\n".join(
            f"| 资产{i} | 原文证据{i} | 迁移{i} | 核心 |" for i in range(1, 7)
        )
        path = self._write(
            "可直接仿写_物件表.md",
            "| 物件 | 原文证据 | 迁移提醒 | 层级 |\n|---|---|---|---|\n"
            + rows
            + "\n## 可直接借的承重结构\n- 资产1和资产2\n- 资产3和资产4\n"
            "## 迁移顺序提醒\n- 资产1再资产2\n- 资产3再资产4\n"
            "## 为什么这个顺序不能乱\n- 资产1不能晚于资产2\n- 资产3不能晚于资产4\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("核心资产过多" in error for error in errors))

    def test_skill_fingerprint_rejects_stale_formal_outputs(self) -> None:
        meta_path = self._write(
            "_meta.json",
            '{"skill_fingerprint": "stale-skill-version"}\n',
        )
        errors: list[str] = []
        VALIDATOR.check_skill_fingerprint(
            meta_path,
            {"skill_fingerprint": "stale-skill-version"},
            errors,
        )
        self.assertTrue(
            any("与当前正式 skill 不一致" in error for error in errors),
            errors,
        )
        self.assertTrue(any("--upgrade-existing" in error for error in errors), errors)

    def test_skill_fingerprint_accepts_current_skill(self) -> None:
        fingerprint = VALIDATOR.compute_skill_fingerprint()
        meta_path = self._write(
            "_meta.json",
            f'{{"skill_fingerprint": "{fingerprint}"}}\n',
        )
        errors: list[str] = []
        VALIDATOR.check_skill_fingerprint(
            meta_path,
            {"skill_fingerprint": fingerprint},
            errors,
        )
        self.assertEqual([], errors)

    def test_preparer_and_validator_use_same_fingerprint_files(self) -> None:
        self.assertEqual(
            PREPARER.SKILL_FINGERPRINT_FILES,
            VALIDATOR.SKILL_FINGERPRINT_FILES,
        )
        self.assertEqual(
            PREPARER.compute_skill_fingerprint(),
            VALIDATOR.compute_skill_fingerprint(),
        )

    def test_bridge_card_requires_non_abstract_human_hook(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "## 卡一\n"
            "- 桥段名：家宴翻脸\n"
            "- 一句人话抓手：权限、秩序与现实后果\n"
            "- 桥段角色：规则展示\n"
            "- 原文位置：L1-L10\n"
            "- 原文现象证据：家门口不让女主进门\n"
            "- 原文为什么能过：先卡门再翻旧账\n"
            "- 为什么不像加工稿：人物先处理鞋和钥匙\n"
            "- 新稿最容易写假的点：直接宣布绝交\n"
            "- 必须保留的承重件：门、钥匙、称呼\n"
            "- 不能丢的顺序：卡门 -> 找钥匙 -> 改口\n"
            "- 为什么这个顺序不能乱：先宣布会失去生活阻力\n"
            "- 后续调用方式：换成宿舍门禁也能用\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, notes)
        self.assertFalse(any("只有抽象术语" in error for error in errors))
        self.assertTrue(any("只有抽象术语" in note for note in notes))

    def test_bridge_cards_reject_repeated_cross_bid_explanations(self) -> None:
        repeated_role = "把旧账转成可见的名分、财物、身体或公共秩序后果。"
        blocks = []
        for idx in range(1, 4):
            blocks.append(
                f"## BID-0{idx}\n"
                f"- 桥段名：BID-0{idx} 独立事件{idx}\n"
                f"- 一句人话抓手：人物{idx}在现场完成动作{idx}并改变结果。\n"
                f"- 桥段角色：{repeated_role}\n"
                f"- 原文位置：L{idx}-L{idx + 1}\n"
                f"- 原文现象证据：动作{idx}落地。\n"
                f"- 原文为什么能过：动作{idx}先改变现场再触发后果。\n"
                f"- 为什么不像加工稿：人物{idx}出现犹豫和误判。\n"
                f"- 新稿最容易写假的点：省掉动作{idx}的现实阻力。\n"
                f"- 必须保留的承重件：动作{idx} -> 后果{idx}\n"
                f"- 不能丢的顺序：动作{idx} -> 后果{idx}\n"
                f"- 为什么这个顺序不能乱：后果{idx}依赖动作{idx}。\n"
                f"- 后续调用方式：更换动作{idx}和后果载体。\n"
            )
        path = self._write("桥段施工卡.md", "\n".join(blocks))
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, notes)
        self.assertTrue(
            any("`桥段角色` 跨 BID 完全重复 3/3 次" in error for error in errors),
            errors,
        )

    def test_bridge_card_rejects_must_keep_copied_as_sequence(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "## BID-01\n"
            "- 桥段名：BID-01 门禁夺权\n"
            "- 一句人话抓手：先没收钥匙，再让守门人当众改口。\n"
            "- 桥段角色：用门禁实物完成关系降位。\n"
            "- 原文位置：L1-L8\n"
            "- 原文现象证据：钥匙落到桌上。\n"
            "- 原文为什么能过：钥匙换手后守门人才改口。\n"
            "- 为什么不像加工稿：守门人先摸空口袋才认输。\n"
            "- 新稿最容易写假的点：只宣布权限变化。\n"
            "- 必须保留的承重件：钥匙换手 -> 门禁失效 -> 守门人改口\n"
            "- 不能丢的顺序：钥匙换手 -> 门禁失效 -> 守门人改口\n"
            "- 为什么这个顺序不能乱：没有钥匙换手，改口就没有现实压力。\n"
            "- 后续调用方式：把钥匙替换成门卡或授权章。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, [])
        self.assertTrue(
            any("`必须保留的承重件` 与 `不能丢的顺序` 跨字段复制" in error for error in errors),
            errors,
        )

    def test_high_risk_card_rejects_must_keep_copied_as_sequence(self) -> None:
        path = self._write(
            "高敏桥段识别.md",
            "## BID-01\n"
            "- 桥段名：BID-01 门禁夺权\n"
            "- 桥段角色：用实体门禁完成关系降位。\n"
            "- 原文：钥匙落到桌上。\n"
            "- 必须保留的承重件：钥匙换手 -> 门禁失效 -> 守门人改口\n"
            "- 不能丢的顺序：钥匙换手 -> 门禁失效 -> 守门人改口\n"
            "- 高敏点：钥匙、门禁和改口的完整组合。\n"
            "- 可学层：以实体权限件触发称谓变化。\n"
            "- 禁学层：不要复刻钥匙和守门人话轮。\n"
            "- 情绪拍：E-0001 | 作用：权限撤销 | 内容：钥匙换手后守门人改口 | 烈度：7 | 原文证据：钥匙落到桌上。\n"
            "- 情绪拍完整性复核：已按原序核对。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_high_risk_asset_quality(path, 1000, errors)
        self.assertTrue(
            any("`必须保留的承重件` 与 `不能丢的顺序` 跨字段复制" in error for error in errors),
            errors,
        )

    def test_candidate_ledger_rejects_overcompressed_table_rows(self) -> None:
        (self.root / "写作资产").mkdir(parents=True, exist_ok=True)
        (self.root / "原文").mkdir(parents=True, exist_ok=True)
        source_lines = [f"第{i}行：资产{i}锚点" for i in range(1, 41)]
        self._write("原文/样本.txt", "\n".join(source_lines))
        self._write(
            "_source_manifest.json",
            '{\n  "chunks": [\n    {"id": 1, "start_line": 1, "end_line": 40}\n  ]\n}\n',
        )
        self._write(
            "写作资产/原文资产候选池.md",
            "\n".join(
                [
                    "C001 | L1-L2 | 锚点：资产1锚点 | 类别：钩子 | 资产名：电话代接 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：有信息差",
                    "C002 | L3-L4 | 锚点：资产2锚点 | 类别：钩子 | 资产名：法庭闸门 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：程序切换",
                    "C003 | L5-L6 | 锚点：资产3锚点 | 类别：钩子 | 资产名：旧宅开门 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：私域悬念",
                    "C004 | L7-L8 | 锚点：资产4锚点 | 类别：钩子 | 资产名：证据双投 | 去向：可直接仿写_钩子表.md | 状态：已收录 | 理由：终局等待",
                    "- 类别：导语：已扫，原文未发现",
                    "- 类别：顺序事件：已扫，原文未发现",
                    "- 类别：物件：已扫，原文未发现",
                    "- 类别：动作：已扫，原文未发现",
                    "- 类别：对白功能：已扫，原文未发现",
                    "- 类别：对话衔接：已扫，原文未发现",
                    "- 类别：误判：已扫，原文未发现",
                    "- 类别：微动作：已扫，原文未发现",
                    "- 类别：安静压迫场：已扫，原文未发现",
                    "- 类别：人物偏手：已扫，原文未发现",
                    "- 类别：失控说话：已扫，原文未发现",
                    "- 类别：烂关系漏出：已扫，原文未发现",
                    "- 类别：外部秩序：已扫，原文未发现",
                    "- 类别：公开炸场：已扫，原文未发现",
                    "- 类别：后果链：已扫，原文未发现",
                    "- Chunk 1：L1-L40 | 状态：已回扫 | 新增候选：无 | 空缺复核：其余类别原文未形成独立资产",
                    "- 物件替换对：已扫，原文未发现独立替换对",
                    "- 微动作角色覆盖：已扫，原文未发现独立微动作组",
                    "- 对白侵占与假道歉：已扫，原文未发现可独立入表句型",
                    "- 安静等待与未归：已扫，原文未发现独立静压桥",
                    "- 未来公开事件钩子：已扫，已由 C004 覆盖",
                    "## 反向漏项审计",
                    "- A001 | L9-L10 | 原文：资产9锚点 | 判定：不收录 | 去向：无 | 理由：只是重复提示，不形成新钩子",
                    "- A002 | L11-L12 | 原文：资产11锚点 | 判定：不收录 | 去向：无 | 理由：功能重复，已被前文覆盖",
                    "- A003 | L13-L14 | 原文：资产13锚点 | 判定：不收录 | 去向：无 | 理由：不是钩子而是说明句",
                    "- A004 | L15-L16 | 原文：资产15锚点 | 判定：不收录 | 去向：无 | 理由：没有独立等待线",
                    "- A005 | L17-L18 | 原文：资产17锚点 | 判定：不收录 | 去向：无 | 理由：只承担气氛，不承担事件悬念",
                ]
            ),
        )
        self._write(
            "可直接仿写_钩子表.md",
            "| 位置 | 钩子内容 | 钩子类型 | 回收位置 | 原文证据 | 迁移提醒 |\n"
            "|---|---|---|---|---|---|\n"
            "| 场末 | 电话代接 | 信息差 | 医院桥 | 资产1锚点 | 先埋代接 |\n"
            "| 章尾 | 法庭闸门 | 程序钩子 | 终局桥 | 资产2锚点 | 再挂程序 |\n"
            "| 尾声 | 证据双投 | 公开钩子 | 社会反噬 | 资产4锚点 | 最后再炸场 |\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_asset_candidate_ledger(self.root, source_lines, 8000, errors, notes)
        self.assertTrue(any("不能把多条候选压成几行长解释" in error for error in errors))

    def test_asset_candidate_ledger_requires_object_seat_cue(self) -> None:
        (self.root / "写作资产").mkdir(parents=True, exist_ok=True)
        self._write(
            "_source_manifest.json",
            '{\n  "chunks": [\n    {"id": 1, "start_line": 1, "end_line": 2}\n  ]\n}\n',
        )
        source_lines = [
            "她坐在他的副驾驶上，像是已经替掉了原来的位置。",
            "其余内容。",
        ]
        self._write(
            "写作资产/原文资产候选池.md",
            "\n".join(
                [
                    "- 类别：导语：已扫，原文未发现",
                    "- 类别：顺序事件：已扫，原文未发现",
                    "- 类别：物件：已扫，原文未发现",
                    "- 类别：动作：已扫，原文未发现",
                    "- 类别：对白功能：已扫，原文未发现",
                    "- 类别：对话衔接：已扫，原文未发现",
                    "- 类别：误判：已扫，原文未发现",
                    "- 类别：钩子：已扫，原文未发现",
                    "- 类别：微动作：已扫，原文未发现",
                    "- 类别：安静压迫场：已扫，原文未发现",
                    "- 类别：人物偏手：已扫，原文未发现",
                    "- 类别：失控说话：已扫，原文未发现",
                    "- 类别：烂关系漏出：已扫，原文未发现",
                    "- 类别：外部秩序：已扫，原文未发现",
                    "- 类别：公开炸场：已扫，原文未发现",
                    "- 类别：后果链：已扫，原文未发现",
                    "- Chunk 1：L1-L2 | 状态：已回扫 | 新增候选：无 | 空缺复核：暂未发现独立候选",
                    "- 物件替换对：已扫，原文未发现独立替换对",
                    "- 微动作角色覆盖：已扫，原文未发现独立微动作组",
                    "- 对白侵占与假道歉：已扫，原文未发现可独立入表句型",
                    "- 安静等待与未归：已扫，原文未发现独立静压桥",
                    "- 未来公开事件钩子：已扫，原文未发现独立未来事件",
                    "## 反向漏项审计",
                    "- A001 | L1-L1 | 原文：她坐在他的副驾驶上 | 判定：不收录 | 去向：无 | 理由：暂未处理",
                    "- A002 | L1-L1 | 原文：替掉了原来的位置 | 判定：不收录 | 去向：无 | 理由：暂未处理",
                    "- A003 | L2-L2 | 原文：其余内容 | 判定：不收录 | 去向：无 | 理由：无独立价值",
                    "- A004 | L2-L2 | 原文：其余内容 | 判定：不收录 | 去向：无 | 理由：无独立价值",
                    "- A005 | L2-L2 | 原文：其余内容 | 判定：不收录 | 去向：无 | 理由：无独立价值",
                ]
            ),
        )
        self._write("可直接仿写_物件表.md", "# 资产表\n\n原文未发现\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_asset_candidate_ledger(self.root, source_lines, 8000, errors, notes)
        self.assertTrue(any("原文出现高价值信号 `副驾驶`" in error for error in errors))

    def test_bridge_card_allows_explicit_source_absence(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "# 桥段施工卡\n\n原文未发现可独立抽取的承重桥。\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, notes)
        self.assertEqual([], errors)

    def test_bridge_emotion_asset_rejects_compressed_sequence(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "- 桥段名：BID-01 位置翻转\n"
            "- 情绪拍：E-001（第一拍） -> E-002（第二拍）\n"
            "- 情绪拍完整性复核：已复核。\n",
        )
        ledger = {
            "beats": [
                {"beat_id": "E-001", "role": "进入", "content": "先给位置。", "intensity": 4, "source_evidence": ["先给位置"], "bid_ids": ["BID-01"]},
                {"beat_id": "E-002", "role": "撤回", "content": "再撤位置。", "intensity": 8, "source_evidence": ["再撤位置"], "bid_ids": ["BID-01"]},
            ]
        }
        errors: list[str] = []
        VALIDATOR.check_bridge_emotion_asset_alignment(path, ledger, errors)
        self.assertTrue(any("每个情绪拍必须独占一行" in error for error in errors))
        self.assertTrue(any("原序子集完全一致" in error for error in errors))

    def test_bridge_emotion_asset_accepts_ledger_exact_rows(self) -> None:
        path = self._write(
            "高敏桥段识别.md",
            "- 桥段名：BID-01 位置翻转\n"
            "- 情绪拍：E-001 | 作用：进入 | 内容：先给位置。 | 烈度：4 | 原文证据：先给位置\n"
            "- 情绪拍：E-002 | 作用：撤回 | 内容：再撤位置。 | 烈度：8 | 原文证据：再撤位置\n"
            "- 情绪拍完整性复核：已复核。\n",
        )
        ledger = {
            "beats": [
                {"beat_id": "E-001", "role": "进入", "content": "先给位置。", "intensity": 4, "source_evidence": ["先给位置"], "bid_ids": ["BID-01"]},
                {"beat_id": "E-002", "role": "撤回", "content": "再撤位置。", "intensity": 8, "source_evidence": ["再撤位置"], "bid_ids": ["BID-01"]},
            ]
        }
        errors: list[str] = []
        VALIDATOR.check_bridge_emotion_asset_alignment(path, ledger, errors)
        self.assertEqual([], errors)

    def test_bridge_emotion_asset_accepts_explicit_bid_field(self) -> None:
        path = self._write(
            "高敏桥段识别.md",
            "- BID：BID-01\n"
            "- 桥段名：位置翻转\n"
            "- 情绪拍：E-001 | 作用：进入 | 内容：先给位置。 | 烈度：4 | 原文证据：先给位置\n"
            "- 情绪拍完整性复核：已复核。\n",
        )
        ledger = {
            "beats": [
                {"beat_id": "E-001", "role": "进入", "content": "先给位置。", "intensity": 4, "source_evidence": ["先给位置"], "bid_ids": ["BID-01"]},
            ]
        }
        errors: list[str] = []
        VALIDATOR.check_bridge_emotion_asset_alignment(path, ledger, errors)
        self.assertEqual([], errors)

    def test_bridge_emotion_asset_accepts_bid_in_card_heading(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "## BID-01 位置翻转\n\n"
            "- 桥段名：位置翻转\n"
            "- 情绪拍：E-001 | 作用：进入 | 内容：先给位置。 | 烈度：4 | 原文证据：先给位置\n"
            "- 情绪拍完整性复核：已复核。\n",
        )
        ledger = {
            "beats": [
                {"beat_id": "E-001", "role": "进入", "content": "先给位置。", "intensity": 4, "source_evidence": ["先给位置"], "bid_ids": ["BID-01"]},
            ]
        }
        errors: list[str] = []
        VALIDATOR.check_bridge_emotion_asset_alignment(path, ledger, errors)
        self.assertEqual([], errors)

    def test_bridge_emotion_asset_accepts_suffix_beat_id(self) -> None:
        path = self._write(
            "高敏桥段识别.md",
            "- 桥段名：BID-01 误判补拍\n"
            "- 情绪拍：E-014B | 作用：错判 | 内容：查问后仍误判。 | 烈度：6 | 原文证据：仍未看清来人。\n"
            "- 情绪拍完整性复核：已复核。\n",
        )
        ledger = {
            "beats": [
                {"beat_id": "E-014B", "role": "错判", "content": "查问后仍误判。", "intensity": 6, "source_evidence": ["仍未看清来人。"], "bid_ids": ["BID-01"]},
            ]
        }
        errors: list[str] = []
        VALIDATOR.check_bridge_emotion_asset_alignment(path, ledger, errors)
        self.assertEqual([], errors)

    def test_high_risk_asset_rejects_quote_wrapped_scaffold(self) -> None:
        path = self._write(
            "高敏桥段识别.md",
            "- 桥段名：BID-01 位置翻转\n"
            "- 桥段角色：承接关系换权、信息揭示和现实后果的高敏桥段。\n"
            "- 原文证据：她把花踢到座后。\n"
            "- 高敏点：不可照搬人物身份、具体物件、表达顺序与原句组合。\n"
            "- 可学层：可迁移因果功能、压力递进、动作权限差和后果回流。\n"
            "- 禁学层：禁止照搬。\n"
            "- 情绪拍：E-001 | 作用：叙述者在此处的情绪落点是“她踢走了花”。 | "
            "内容：情绪由前一状态转为对“她踢走了花”的即时感受。 | "
            "烈度：4 | 原文证据：她把花踢到座后。\n"
            "- 情绪拍完整性复核：已复核。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_high_risk_asset_quality(path, 1000, errors)
        self.assertTrue(any("高敏资产固定句壳" in error for error in errors))

    def test_high_risk_asset_accepts_bridge_specific_language(self) -> None:
        path = self._write(
            "高敏桥段识别.md",
            "- 桥段名：BID-01 花枝被踢走\n"
            "- 桥段角色：主角用一个无人注意的脚部动作，主动放弃被选中的位置。\n"
            "- 原文证据：她把花踢到座后。\n"
            "- 高敏点：花枝、夜宴和婚约在同一动作中锁死，组合后极易还原原桥。\n"
            "- 可学层：让弱势者用微动作拒绝表面奖励。\n"
            "- 禁学层：不保留宴席藏花、捡到即成婚的连锁设定。\n"
            "- 情绪拍：E-001 | 作用：拒绝被选中 | 内容：她宁可错过婚约，也不暴露自己捡到了花。 | "
            "烈度：4 | 原文证据：她把花踢到座后。\n"
            "- 情绪拍完整性复核：已复核。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_high_risk_asset_quality(path, 1000, errors)
        self.assertEqual([], errors)

    def test_high_risk_asset_rejects_repeated_cross_bid_boundaries(self) -> None:
        blocks = []
        for idx in range(1, 4):
            blocks.append(
                f"## BID-0{idx}\n"
                f"- 桥段名：BID-0{idx} 独立高敏桥{idx}\n"
                f"- 桥段角色：人物{idx}用动作{idx}改变关系位置。\n"
                f"- 原文证据：动作{idx}发生。\n"
                f"- 高敏点：物件{idx}与场景{idx}组合后容易还原原桥。\n"
                "- 可学层：物件证词、称谓改判、硬牌验心与后果回收。\n"
                "- 禁学层：禁止复刻姓名、身份、物件与原句组合。\n"
                f"- 情绪拍：E-00{idx} | 作用：位置改变 | 内容：动作{idx}改变关系。 | "
                f"烈度：{idx + 3} | 原文证据：动作{idx}发生。\n"
                "- 情绪拍完整性复核：已复核。\n"
            )
        path = self._write("高敏桥段识别.md", "\n".join(blocks))
        errors: list[str] = []
        VALIDATOR.check_high_risk_asset_quality(path, 1000, errors)
        self.assertTrue(
            any("`可学层` 跨 BID 完全重复 3/3 次" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("`禁学层` 跨 BID 完全重复 3/3 次" in error for error in errors),
            errors,
        )

    def test_profile_source_rejects_fixed_emotion_sentence_shells(self) -> None:
        path = self._write(
            "profile_source.md",
            "## 6. 桥段承重件\n"
            "- 桥段：BID-01 花枝被踢走\n"
            "  - 桥段角色：主角用微动作拒绝被选中。\n"
            "  - 原文怎么起手：她认出花枝对应旧婚约。\n"
            "  - 不能丢的顺序：认花 -> 踢花 -> 花被送回。\n"
            "  - 为什么这个顺序不能乱：先成功避开，回花才构成反刀。\n"
            "  - 最容易写假的点：直接让她发表独立宣言。\n"
            "  - 原文为什么能过：拒绝先发生在脚下动作里。\n"
            "  - 情绪拍：E-001 | 作用：叙述者在此处的情绪落点是‘她踢走花枝’。 | "
            "内容：情绪由前一状态转为对‘她踢走花枝’的即时感受。 | "
            "烈度：4 | 原文证据：她踢走花枝。\n"
            "  - 情绪拍完整性复核：已按 BID 子序列复核。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_profile_source_quality(path, 1000, errors)
        self.assertTrue(any("profile_source 固定伪情绪句壳污染" in error for error in errors))

    def test_profile_source_accepts_bridge_specific_emotion_language(self) -> None:
        path = self._write(
            "profile_source.md",
            "## 6. 桥段承重件\n"
            "- 桥段：BID-01 花枝被踢走\n"
            "  - 桥段角色：主角用微动作拒绝被选中。\n"
            "  - 原文怎么起手：她认出花枝对应旧婚约。\n"
            "  - 不能丢的顺序：认花 -> 踢花 -> 花被送回。\n"
            "  - 为什么这个顺序不能乱：先成功避开，回花才构成反刀。\n"
            "  - 最容易写假的点：直接让她发表独立宣言。\n"
            "  - 原文为什么能过：拒绝先发生在脚下动作里。\n"
            "  - 情绪拍：E-001 | 作用：侥幸被阴风夺走 | "
            "内容：花枝重新落回膝上，她刚获得的退路立刻消失。 | "
            "烈度：8 | 原文证据：花落回她膝上。\n"
            "  - 情绪拍完整性复核：已按 BID 子序列复核。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_profile_source_quality(path, 1000, errors)
        self.assertFalse(any("profile_source 固定伪情绪句壳污染" in error for error in errors))

    def test_bridge_reconciliation_accepts_bid_on_node_line(self) -> None:
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        self._write(
            "情节节点.md",
            "N01 | L1-L2 | 锚点：一号候诊单 | 类型：BID-01 中段承重桥 | "
            "情绪：坠落-8 | 涉及：甲 | 状态变化：获得到失去 | "
            "因果：给号 -> 撤号 -> 白跑 | 故事时序：第二天\n",
        )
        self._write("拆文报告.md", "- 桥段名：[BID-01] 一号候诊单被撤回\n")
        for name in ("高敏桥段识别.md", "桥段施工卡.md", "profile_source.md"):
            (asset_dir / name).write_text(
                "- 桥段名：[BID-01] 一号候诊单被撤回\n",
                encoding="utf-8",
            )
        errors: list[str] = []
        notes: list[str] = []

        VALIDATOR.check_bridge_reconciliation(
            self.root,
            {"bridge_rules": [{"id": "BID-01", "must_keep": ["一号候诊单"]}]},
            errors,
            notes,
        )

        self.assertEqual([], errors)
        self.assertFalse(any("未发现 BID" in note for note in notes))

    def test_bridge_reconciliation_rejects_bid_only_in_explanation(self) -> None:
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        self._write(
            "情节节点.md",
            "> 本书承重桥：BID-01\n\n"
            "N01 | L1-L2 | 锚点：一号候诊单 | 类型：中段承重桥 | "
            "情绪：坠落-8 | 涉及：甲 | 状态变化：获得到失去 | "
            "因果：给号 -> 撤号 -> 白跑 | 故事时序：第二天\n",
        )
        self._write("拆文报告.md", "- 桥段名：[BID-01] 一号候诊单被撤回\n")
        for name in ("高敏桥段识别.md", "桥段施工卡.md", "profile_source.md"):
            (asset_dir / name).write_text(
                "- 桥段名：[BID-01] 一号候诊单被撤回\n",
                encoding="utf-8",
            )
        errors: list[str] = []

        VALIDATOR.check_bridge_reconciliation(
            self.root,
            {"bridge_rules": [{"id": "BID-01", "must_keep": ["一号候诊单"]}]},
            errors,
        )

        self.assertTrue(any("承重桥节点缺少 BID" in error for error in errors), errors)
        self.assertTrue(
            any("未在具体 N 节点行显式标注承重桥 BID：BID-01" in error for error in errors),
            errors,
        )

    def test_bridge_reconciliation_rejects_multiple_bids_on_one_node(self) -> None:
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        self._write(
            "情节节点.md",
            "N01 | L1-L2 | 锚点：一号候诊单 | 类型：BID-01 BID-02 承重桥 | "
            "情绪：坠落-8 | 涉及：甲 | 状态变化：获得到失去 | "
            "因果：给号 -> 撤号 -> 白跑 | 故事时序：第二天\n",
        )
        self._write("拆文报告.md", "BID-01 BID-02\n")
        for name in ("高敏桥段识别.md", "桥段施工卡.md", "profile_source.md"):
            (asset_dir / name).write_text("BID-01 BID-02\n", encoding="utf-8")
        errors: list[str] = []

        VALIDATOR.check_bridge_reconciliation(
            self.root,
            {"bridge_rules": [{"id": "BID-01"}, {"id": "BID-02"}]},
            errors,
        )

        self.assertTrue(any("单个节点不得挂多个 BID" in error for error in errors), errors)

    def test_craft_requires_sentence_level_assets(self) -> None:
        path = self._write(
            "写作手法.md",
            "## 2. 对话手法\n"
            "- 角色A嘴型很短，为什么成立\n"
            "- 角色B口气更绕，迁移风险明确\n"
            "- 角色C先找补，不能直接搬\n"
            "- 三人的角色差会决定压场顺序，写错会发假\n",
        )
        errors: list[str] = []
        VALIDATOR.check_craft_quality(path, errors)
        self.assertTrue(any("句法模板" in error for error in errors))
        self.assertTrue(any("段落节拍" in error for error in errors))

    def test_craft_requires_global_shape_audit_with_evidence(self) -> None:
        path = self._write(
            "写作手法.md",
            "\n".join(
                [
                    "## 10. 全局成文形状审计",
                    "### 10.1 全局结构形状与章尾收束",
                    "- 全局结构形状：整体偏工整",
                    "- 章尾收束模式：反复动作收束",
                    "### 10.2 主角不规则性与能动性",
                    "- 主角不规则性：长期做正确决策",
                    "### 10.3 专业细节功能性",
                    "- 专业细节功能性：术语密集",
                    "### 10.4 全文对白模式",
                    "- 全文对白模式：反复问答确认",
                ]
            ),
        )
        errors: list[str] = []
        VALIDATOR.check_global_shape_audit(path, errors)
        self.assertTrue(any("缺少全局成文形状审计标题" in error for error in errors))
        self.assertTrue(any("缺少证据字段" in error for error in errors))

    def test_global_shape_audit_rejects_unverifiable_evidence(self) -> None:
        sections = []
        for heading, label in (
            ("### 10.1 全局结构形状与章尾收束", "全局结构形状"),
            ("### 10.2 主角不规则性与能动性", "主角不规则性"),
            ("### 10.3 专业细节功能性", "专业细节功能性"),
            ("### 10.4 全文对白模式", "全文对白模式"),
        ):
            sections.extend(
                [
                    heading,
                    f"- {label}：这里是足够长的判断",
                    "- 原文证据：整体就是这样",
                    "- 风险判断：这里是足够长的判断",
                    "- 可学层：这里只学承重结构",
                    "- 禁学层：这里禁止照搬成品感",
                    "- 迁移提醒：迁移时必须改变场面后果",
                ]
            )
        path = self._write(
            "写作手法.md",
            "## 10. 全局成文形状审计\n" + "\n".join(sections),
        )
        errors: list[str] = []
        VALIDATOR.check_global_shape_audit(path, errors)
        self.assertTrue(any("没有行号或可核验原文短句" in error for error in errors))

    def test_layered_sample_requires_explicit_layer_consumption(self) -> None:
        path = self._write(
            "样本分级与可学层.md",
            "- structure_grade：A\n"
            "- performance_grade：A\n"
            "- sentence_grade：B\n"
            "- terminal_consequence_grade：C\n"
            "- 正向DNA层：人物口气和动作\n"
            "- 仅骨架层：句法只看切句位置\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_grading_quality(path, errors)
        self.assertTrue(any("分层样本" in error for error in errors))
        self.assertTrue(any("反面规则层" in error for error in errors))

    def test_sample_grading_global_shape_h2_keeps_nested_cases(self) -> None:
        path = self._write(
            "样本分级与可学层.md",
            "- structure_grade：A\n"
            "- performance_grade：A\n"
            "- sentence_grade：A\n"
            "- terminal_consequence_grade：A\n"
            "- 正向DNA层：动作权限和物件权限\n"
            "- 仅骨架层：公开场结构\n"
            "- 反面规则层：高识别组合\n"
            "## 4.4 全局成文形状审计\n"
            "- 全局结构形状：L1-L9 先给误判，L53-L66 再公开掉位。\n"
            "- 章尾收束模式：L66 丢下了我，L269 今天是我预约手术的日子。\n"
            "- 主角不规则性：L94-L95 删信息，L229-L234 砸杯扇人。\n"
            "- 专业细节功能性：L78 夫妻代言，L424-L429 改成全程直播。\n"
            "- 全文对白模式：L58-L60 轮得到你来管我。\n"
            "### 全局结构形状\n"
            "案例：L53-L66 先给公开体面，再用抱走和留下完成掉位。\n"
            "### 章尾收束模式\n"
            "案例：L262-L269 用电话离场和手术短信完成现实落锤。\n"
            "### 主角不规则性\n"
            "案例：L229-L234 砸杯撕领说明主角不是单面受虐。\n"
            "### 专业细节功能性\n"
            "案例：L78 夫妻代言让私事产生公开补台责任。\n"
            "### 全文对白模式\n"
            "案例：L100-L106 称谓争夺后立刻进入戒指见血。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_grading_quality(path, errors, require_global_shape=True)
        self.assertEqual([], errors)

    def test_report_agency_requires_three_distinct_layers(self) -> None:
        path = self._write(
            "拆文报告.md",
            "### 主角能动性三层判断\n"
            "- 原文明确动作：她选择留下并利用已经出现的证据窗口\n"
            "- 叙事意图判断：文本支持她在借势，而不是纯粹等待\n",
        )
        errors: list[str] = []
        VALIDATOR.check_report_agency_layers(path, errors)
        self.assertTrue(any("未知边界" in error for error in errors))

    def test_plot_nodes_require_story_sequence(self) -> None:
        path = self._write(
            "情节节点.md",
            "N1 | L1-L2 | 锚点：那次聚会 | 类型：信息 | 情绪：冷 | "
            "涉及：甲 | 状态变化：未知到知情 | 因果：收到证据后等待\n",
        )
        errors: list[str] = []
        VALIDATOR.check_plot_nodes_quality(path, 1, errors)
        self.assertTrue(any("故事时序" in error for error in errors))

    def test_plot_node_count_is_review_note_not_hard_error(self) -> None:
        path = self._write(
            "情节节点.md",
            "N1 | L1-L2 | 锚点：开场 | 类型：信息 | 情绪：冷 | "
            "涉及：甲 | 状态变化：未知到知情 | 因果：收到证据 | 故事时序：第一件事\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_plot_nodes_quality(path, 8000, errors, notes)
        self.assertFalse(any("颗粒度不足" in error for error in errors))
        self.assertTrue(any("禁止为达数量凑节点" in note for note in notes))

    def test_manual_review_checkpoints_cannot_be_skipped(self) -> None:
        self._write(
            "_progress.md",
            "- [x] 模型人工复核：事实台账\n"
            "- [ ] 模型人工复核：主报告\n"
            "- [x] 模型人工复核：profile\n"
            "- [x] 模型人工复核：finalize\n",
        )
        errors: list[str] = []
        VALIDATOR.check_manual_review_progress(self.root, errors)
        self.assertTrue(any("未完成的模型人工复核" in error for error in errors))

    def test_fact_ledger_requires_dual_timeline_fields(self) -> None:
        path = self._write(
            "事实与推断台账.md",
            "F01 | L1-L1 | 锚点：那次聚会结束后 | 类别：时间边界 | "
            "主体：甲 | 动作：收到录像 | 结果：开始等待 | "
            "口径：原文明确 | 禁止越界：不能排到婚礼后\n",
        )
        errors: list[str] = []
        VALIDATOR.parse_fact_ledger(path, ["那次聚会结束后"], errors)
        self.assertTrue(any("台账格式不完整" in error for error in errors))

    def test_fact_count_is_review_note_not_hard_error(self) -> None:
        path = self._write(
            "事实与推断台账.md",
            "F01 | L1-L1 | 锚点：收到录像证据 | 类别：主体边界/时间边界/证据来源 | "
            "主体：甲 | 动作：收到录像 | 结果：知情 | 叙述时点：开场 | "
            "故事时点：聚会后 | 时间依据：L1 | 口径：原文明确 | 禁止越界：未知来源\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.parse_fact_ledger(path, ["收到录像证据"], errors, notes)
        self.assertFalse(any("事实台账过薄" in error for error in errors))
        self.assertTrue(any("禁止为达数量编造" in note for note in notes))

    def test_profile_asset_counts_are_review_notes(self) -> None:
        errors: list[str] = []
        notes: list[str] = []
        data = {
            "scene_assets": {
                "public_explosion": ["婚礼上公开录像"],
                "external_order": ["警方带走涉事者"],
                "consequence_chain": ["证据公开后关系破裂"],
            },
            "banned_phrases": ["不要替角色总结"],
            "author_stance_patterns": ["让后果自己落地"],
            "style_assets": {
                key: []
                for key in VALIDATOR.REQUIRED_STYLE_ASSET_KEYS
            },
            "derived_patterns": [],
            "migration_assets": {
                key: ["录像"]
                for key in VALIDATOR.REQUIRED_MIGRATION_ASSET_KEYS
            },
            "story_guardrails": {
                "character_face_split": {
                    key: ["证据"]
                    for key in VALIDATOR.REQUIRED_FACE_GUARDRAIL_KEYS
                },
                "consequence_structure": {
                    key: ["后果"]
                    for key in VALIDATOR.REQUIRED_CONSEQUENCE_GUARDRAIL_KEYS
                },
            },
            "bridge_rules": [{"must_keep": ["录像公开"]}],
        }
        VALIDATOR.check_book_profile_quality(
            self.root / "book.profile.json",
            data,
            8000,
            "婚礼上公开录像警方带走涉事者证据公开后关系破裂",
            errors,
            notes,
        )
        self.assertTrue(
            any("style_assets.opening_hooks 为空" in error for error in errors),
            errors,
        )
        self.assertTrue(any("低于篇幅参考值" in note for note in notes))

    def test_profile_style_assets_cannot_all_compile_to_empty(self) -> None:
        data = {
            "scene_assets": {},
            "banned_phrases": ["禁句"],
            "author_stance_patterns": ["站位"],
            "style_assets": {
                key: ([] if key == "misdirection" else ["原文短语"])
                for key in VALIDATOR.REQUIRED_STYLE_ASSET_KEYS
            },
        }
        errors: list[str] = []
        VALIDATOR.check_book_profile_quality(
            self.root / "book.profile.json",
            data,
            1000,
            "原文短语",
            errors,
        )
        self.assertTrue(
            any("style_assets.misdirection 为空" in item for item in errors),
            errors,
        )

    def test_profile_requires_complete_primary_prose_contract(self) -> None:
        data = {
            "scene_assets": {},
            "banned_phrases": ["禁句"],
            "author_stance_patterns": ["站位"],
            "style_assets": {
                key: [] for key in VALIDATOR.REQUIRED_STYLE_ASSET_KEYS
            },
            "derived_patterns": [],
            "migration_assets": {},
            "story_guardrails": {},
            "bridge_rules": [],
            "prose_style_contract": {
                "source_role": "primary_only",
                "sentence_motion": ["短句落锤"],
                "narrator_voice": [],
                "dialogue_and_character_voice": ["人物口气分脸"],
                "anti_patterns": ["禁用空泛总结"],
            },
        }
        errors: list[str] = []
        VALIDATOR.check_book_profile_quality(
            self.root / "book.profile.json", data, 1000, "", errors
        )
        self.assertTrue(
            any("prose_style_contract.narrator_voice 不能为空" in item for item in errors),
            errors,
        )

        data["prose_style_contract"]["narrator_voice"] = ["贴脸叙述"]
        errors = []
        VALIDATOR.check_book_profile_quality(
            self.root / "book.profile.json", data, 1000, "", errors
        )
        self.assertFalse(any("prose_style_contract" in item for item in errors), errors)

    def test_unverified_filename_requires_explicit_status_declaration(self) -> None:
        self._write("拆文报告.md", "墓前结尾完成标题归位。\n")
        errors: list[str] = []
        VALIDATOR.check_title_claim_boundary(
            self.root,
            {"title_status": "unverified-filename"},
            errors,
        )
        self.assertTrue(any("缺少 `标题状态" in error for error in errors))

    def test_title_semantics_are_left_to_model_review(self) -> None:
        self._write(
            "拆文报告.md",
            "- 标题状态：未验证（来自文件名）。\n"
            "正文没有出现书名，不能声称完成标题归位。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_title_claim_boundary(
            self.root,
            {"title_status": "unverified-filename"},
            errors,
        )
        self.assertEqual([], errors)

    def test_backreference_fact_must_point_to_earlier_source_lines(self) -> None:
        source = ["占位"] * 20
        source[14] = "那次聚会结束后，我收到录像"
        path = self._write(
            "事实与推断台账.md",
            "F01 | L15-L15 | 锚点：那次聚会结束后 | 类别：时间边界 | "
            "主体：甲 | 动作：收到录像 | 结果：知情 | 叙述时点：当前 | "
            "故事时点：当前 | 时间依据：按L15顺排 | 口径：原文明确 | "
            "禁止越界：不能乱排\n",
        )
        errors: list[str] = []
        facts = VALIDATOR.parse_fact_ledger(path, source, errors)
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(path, source, facts, notes)
        self.assertFalse(any("未指向更早原文行" in error for error in errors))
        self.assertTrue(any("没有指向更早正文行" in note for note in notes))

    def test_gendered_humiliation_requires_specific_analysis(self) -> None:
        self._write("拆文报告.md", "这是一场普通隐私冲突。\n")
        notes: list[str] = []
        VALIDATOR.check_gendered_humiliation_layer(
            self.root,
            "他的私密照片被拿去威胁别人。",
            notes,
        )
        self.assertTrue(any("性化隐私伤害" in note for note in notes))

    def test_valid_backreference_still_requires_knowledge_cross_check(self) -> None:
        source = ["那次聚会开始了。", "我说手里有证据。", "婚礼将至。", "那次聚会结束后，我收到录像。"]
        facts = {"17": {
            "start": 4, "end": 4, "narrative_time": "婚礼前向读者补揭",
            "story_time": "人物在早前聚会后已经收到录像",
            "time_basis": "L4那次聚会回指L1，不是婚礼前首次收到",
        }}
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(self.root / "事实与推断台账.md", source, facts, notes)
        self.assertEqual(1, len(notes))
        self.assertIn("核对相关 KS、P/E 与 SF", notes[0])
        self.assertNotIn("没有指向更早正文行", notes[0])
        items = VALIDATOR.build_human_review_items(self.root, notes)
        self.assertEqual(1, len(items))
        receipt = {
            "skill_fingerprint": VALIDATOR.compute_skill_fingerprint(),
            "formal_markdown_sha1s": VALIDATOR.formal_markdown_sha1s(self.root),
            "review_items": [],
        }
        self._write("_finalize_human_review.json", json.dumps(receipt, ensure_ascii=False))
        errors: list[str] = []
        VALIDATOR.check_human_review_receipt(self.root, notes, {}, errors)
        self.assertTrue(any(items[0]["id"] in error for error in errors))
        receipt["review_items"] = [{
            "id": items[0]["id"], "status": "resolved",
            "judgement": "人物早前已经获证，此处仅向读者回叙来源；相关知情状态不得写成首次获证。",
            "evidence": ["L1聚会；L4那次聚会结束后"],
        }]
        self._write("_finalize_human_review.json", json.dumps(receipt, ensure_ascii=False))
        errors = []
        VALIDATOR.check_human_review_receipt(self.root, notes, {}, errors)
        self.assertEqual([], errors)

    def test_forward_sequence_and_hearsay_do_not_imply_flashback(self) -> None:
        source = ["我当场丢掉请帖。", "听说，他回去争闹后扩大了婚礼。"]
        facts = {"16": {
            "start": 1, "end": 2, "narrative_time": "离场后", "story_time": "离场后",
            "time_basis": "比较后离场，对方再回去争闹",
        }}
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(self.root / "事实与推断台账.md", source, facts, notes)
        self.assertEqual([], notes)

    def test_annotated_flashback_without_trigger_word_is_reviewed(self) -> None:
        facts = {"03": {
            "start": 1, "end": 1, "narrative_time": "此处插叙", "story_time": "三年前",
            "time_basis": "日期由前文说明",
        }}
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(self.root / "事实与推断台账.md", ["信已经寄到了。"], facts, notes)
        self.assertEqual(1, len(notes))

    def test_ambiguous_backreference_remains_a_review_not_a_fact_rewrite(self) -> None:
        facts = {"04": {
            "start": 1, "end": 1, "narrative_time": "结尾", "story_time": "未知",
            "time_basis": "那次聚会也可能是未叙及的前史",
        }}
        before = json.dumps(facts, ensure_ascii=False)
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(self.root / "事实与推断台账.md", ["那次聚会结束后，她拿到了信。"], facts, notes)
        self.assertEqual(1, len(notes))
        self.assertIn("回指不唯一保留未知", notes[0])
        self.assertEqual(before, json.dumps(facts, ensure_ascii=False))

    def test_timeline_review_ignores_invalid_ranges(self) -> None:
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(self.root / "事实与推断台账.md", ["那次聚会"], {
            "01": {"start": 1, "end": 9, "narrative_time": "回叙"},
        }, notes)
        self.assertEqual([], notes)

    def test_high_agency_negation_is_review_note_not_hard_error(self) -> None:
        self._write("拆文报告.md", "禁止把等待写成主角策划了婚礼。\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_fact_references(self.root, {}, errors, notes)
        self.assertEqual([], errors)
        self.assertTrue(any("高主动性表达" in note for note in notes))

    def test_missing_fact_reference_remains_hard_error(self) -> None:
        self._write("拆文报告.md", "主角等待婚礼【原文明确 F99】。\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_fact_references(self.root, {}, errors, notes)
        self.assertTrue(any("不存在的事实台账 F99" in error for error in errors))

    def test_multiple_fact_references_are_checked_as_joint_support(self) -> None:
        self._write(
            "拆文报告.md",
            "主角推动证据公开传播【原文明确 F01】【原文明确 F02】。\n",
        )
        facts = {
            "01": {
                "stance": "原文明确",
                "action": "主角取得证据并推动调查",
                "result": "调查启动",
                "boundary": "未直接发布",
            },
            "02": {
                "stance": "原文明确",
                "action": "同伴公开传播证据",
                "result": "舆论转向",
                "boundary": "传播者不是主角",
            },
        }
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_fact_references(self.root, facts, errors, notes)
        self.assertEqual([], errors)
        self.assertFalse(any("支持关系不明显" in note for note in notes))

    def test_specific_detail_migration_phrases_are_not_placeholder_warnings(self) -> None:
        detail = self._write(
            "场景细节库.md",
            "\n".join(
                f"## 卡{i}\n- 后续能迁到什么新桥段：可迁到发布会救场、楼道挡镜头{i}。"
                for i in range(1, 6)
            ),
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_detail_library_quality(detail, 9000, errors, notes)
        self.assertFalse(any("常见模板句" in note for note in notes))

    def test_generic_detail_migration_placeholder_still_warns(self) -> None:
        detail = self._write(
            "场景细节库.md",
            "\n".join(
                f"## 卡{i}\n- 后续能迁到什么新桥段：可迁到同题材桥段。"
                for i in range(1, 6)
            ),
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_detail_library_quality(detail, 9000, errors, notes)
        self.assertTrue(any("常见模板句" in note for note in notes))

    def test_completion_updates_meta_but_preserves_manual_checkpoints(self) -> None:
        self._write(
            "_progress.md",
            "- [ ] 普通文件任务\n"
            "- [ ] 模型人工复核：主报告\n",
        )
        self._write(
            "_meta.json",
            '{"genre_detected":"通用","stages_completed":[],"last_stage_in_progress":6}\n',
        )
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        (asset_dir / "profile_source.md").write_text(
            "- 深层流派：替身婚姻清算\n",
            encoding="utf-8",
        )
        FINALIZER.update_completion_state(self.root)
        progress = (self.root / "_progress.md").read_text(encoding="utf-8")
        meta = __import__("json").loads((self.root / "_meta.json").read_text(encoding="utf-8"))
        self.assertIn("- [ ] 普通文件任务", progress)
        self.assertIn("- [ ] 模型人工复核：主报告", progress)
        self.assertEqual("替身婚姻清算", meta["genre_detected"])
        self.assertEqual([2, 3, 4, 5, 6], meta["stages_completed"])
        self.assertIsNone(meta["last_stage_in_progress"])

    def test_sample_comparison_rejects_claim_without_read_files(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "## 主报告后复核\n"
            "- 对照裁决：未滑入反例\n"
            "- 证据：主报告保留三段承重桥\n"
            "- 实际回写文件：拆文报告.md\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertTrue(any("缺少已读文件记录" in error for error in errors), errors)

    def test_sample_comparison_accepts_complete_builtin_sample_audit(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 已读文件：references/examples/yuwei/README.md\n"
            "- 已读文件：references/examples/yuwei/幼薇原文.txt\n"
            "- 已读文件：references/examples/yuwei/正反例对照.md\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "## 主报告后复核\n"
            "- 对照裁决：未滑入反例\n"
            "- 证据：主报告保留三段承重桥\n"
            "- 实际回写文件：拆文报告.md\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertEqual([], errors)

    def test_sample_comparison_blocks_unfinished_rework(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 已读文件：references/examples/yuwei/README.md\n"
            "- 已读文件：references/examples/yuwei/幼薇原文.txt\n"
            "- 已读文件：references/examples/yuwei/正反例对照.md\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "## 主报告后复核\n"
            "- 对照裁决：需要回炉\n"
            "- 证据：主报告仍压缩中段\n"
            "- 实际回写文件：无\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertTrue(any("不得进入 finalize" in error for error in errors), errors)

    def test_sample_comparison_rejects_backup_or_old_profile(self) -> None:
        path = self._write(
            "_sample_comparison.md",
            "## 样本《幼薇》\n"
            "- 选择原因：防止中段桥被压薄\n"
            "- 已读文件：references/examples/yuwei/README.md\n"
            "- 已读文件：references/examples/yuwei/幼薇原文.txt\n"
            "- 已读文件：references/examples/yuwei/正反例对照.md\n"
            "- 正例锚点：保留生活动作链\n"
            "- 反例锚点：只剩结构标签\n"
            "- 本书对应风险：中段压缩\n"
            "- 将影响的正式文件：拆文报告.md\n"
            "- 额外参考：拆文库_bak/旧书/book.profile.json\n"
            "## 主报告后复核\n"
            "- 对照裁决：未滑入反例\n"
            "- 证据：主报告保留三段承重桥\n"
            "- 实际回写文件：拆文报告.md\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_comparison(path, errors)
        self.assertTrue(any("只能使用 references/examples/" in error for error in errors), errors)

    def test_markdown_hashes_detect_formal_output_changes(self) -> None:
        path = self._write("拆文报告.md", "第一版\n")
        before = FINALIZER.markdown_sha1s(self.root)
        path.write_text("第二版\n", encoding="utf-8")
        after = FINALIZER.markdown_sha1s(self.root)
        self.assertNotEqual(before, after)

    def test_refresh_human_review_receipt_updates_only_deterministic_state(self) -> None:
        self._write("拆文报告.md", "正式内容\n")
        self._write("_progress.md", "过程内容\n")
        receipt = {
            "upgrade_status": "completed",
            "upgrade_reviews": [{"scope": "content_contract_review", "status": "resolved"}],
            "review_items": [{"id": "HR-1", "status": "not_applicable"}],
            "skill_fingerprint": "old",
            "formal_markdown_sha1s": {},
        }
        (self.root / "_finalize_human_review.json").write_text(
            json.dumps(receipt, ensure_ascii=False), encoding="utf-8"
        )

        count = FINALIZER.refresh_human_review_receipt(self.root, VALIDATOR)
        refreshed = json.loads(
            (self.root / "_finalize_human_review.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(VALIDATOR.formal_markdown_sha1s(self.root)), count)
        self.assertEqual(VALIDATOR.compute_skill_fingerprint(), refreshed["skill_fingerprint"])
        self.assertEqual(VALIDATOR.formal_markdown_sha1s(self.root), refreshed["formal_markdown_sha1s"])
        self.assertEqual(receipt["upgrade_reviews"], refreshed["upgrade_reviews"])
        self.assertEqual(receipt["review_items"], refreshed["review_items"])

    def test_finalizer_has_no_markdown_repair_helpers(self) -> None:
        self.assertFalse(hasattr(FINALIZER, "repair_assets"))
        self.assertFalse(hasattr(FINALIZER, "repair_emotion_outline"))
        self.assertFalse(hasattr(FINALIZER, "repair_fake_reasons"))

    def test_prepare_rejects_missing_contract_without_default_layout(self) -> None:
        fake_repo = self.root / "missing-repo"
        with mock.patch.object(PREPARER, "repo_root_from_script", return_value=fake_repo):
            with self.assertRaisesRegex(FileNotFoundError, "禁止使用默认清单兜底"):
                PREPARER.parse_output_contract()

    def test_prepare_rejects_unparseable_contract_without_default_layout(self) -> None:
        fake_repo = self.root / "bad-repo"
        contract = (
            fake_repo
            / "skills"
            / "story-short-analyze"
            / "references"
            / "pipeline"
            / "output-contract.md"
        )
        contract.parent.mkdir(parents=True)
        contract.write_text("没有文件树\n", encoding="utf-8")
        with mock.patch.object(PREPARER, "repo_root_from_script", return_value=fake_repo):
            with self.assertRaisesRegex(ValueError, "禁止使用默认清单兜底"):
                PREPARER.parse_output_contract()

    def test_prepare_current_contract_matches_explicit_schema(self) -> None:
        self.assertEqual(PREPARER.CONTRACT_LAYOUT_SCHEMA, PREPARER.parse_output_contract())

    def test_execution_prompt_defaults_to_fast_thick_batches(self) -> None:
        path = self.root / "_execution_prompt.md"
        PREPARER.write_execution_prompt(
            path,
            "测试书",
            self.root / "原文" / "测试书.txt",
            self.root,
            "第一行\n第二行\n第三行\n",
        )
        prompt = path.read_text(encoding="utf-8")
        self.assertIn("第二波仍有 5 条内容 lane，但 lane 不是 agent", prompt)
        self.assertIn("细节库", prompt)
        self.assertIn("失败只二分责任批次", prompt)
        self.assertIn("仍失败才降级为双文件", prompt)
        self.assertIn("_parallel_plan.json", prompt)
        self.assertIn("_analysis_brief.md", prompt)
        self.assertIn("foundation_preflight", prompt)
        self.assertIn("每条 lane 只写自己的文件", prompt)
        self.assertIn("不要整份加载 `output-templates.md`", prompt)
        self.assertIn("主线程 + 3 个复用子 agent", prompt)
        self.assertIn("record_short_analyze_timing.py", prompt)
        self.assertIn("first_write_contract", prompt)
        self.assertIn("foundation_lanes[].first_write_contract", prompt)
        self.assertIn("第一波落盘前检查固定标题逐字命中且各一次", prompt)
        self.assertIn("禁止先写旧模板再靠 validator 返修", prompt)
        self.assertIn("表头、最低行数、表后三段、细节卡五字段", prompt)
        self.assertNotIn("每个微批最多 2 个正式文件", prompt)

    def test_parallel_plan_has_disjoint_lane_ownership(self) -> None:
        path = self.root / "_parallel_plan.json"
        PREPARER.write_parallel_plan(path, self.root / "原文" / "测试书.txt", 10000)
        payload = json.loads(path.read_text(encoding="utf-8"))
        owned: list[str] = []
        for lane in payload["foundation_lanes"] + payload["asset_lanes"]:
            owned.extend(lane["write_files"])
        self.assertEqual(len(owned), len(set(owned)))
        self.assertEqual(len(payload["foundation_lanes"]), 3)
        self.assertEqual(len(payload["asset_lanes"]), 5)
        self.assertEqual(payload["max_concurrent_lanes"], 3)
        self.assertEqual(payload["agent_strategy"]["asset_agent_limit"], 3)
        self.assertEqual(payload["agent_strategy"]["agent_session_limit"], 3)
        self.assertTrue(payload["agent_strategy"]["reuse_agent_sessions_across_waves"])
        self.assertFalse(payload["agent_strategy"]["spawn_each_lane_separately"])
        self.assertIn("foundation validator", payload["agent_strategy"]["disable_agents_for_checks"])
        self.assertIn("出现 429 / rate limit / queueing", payload["agent_strategy"]["degrade_when"])
        self.assertEqual(payload["version"], 8)
        self.assertEqual(payload["executor_profile"], "short-reuse-3-agents")
        self.assertIn("_analysis_brief.md", payload["foundation_start_gate"])
        self.assertIn("validate_short_analyze_foundation.py", payload["foundation_preflight"])
        self.assertIn("拆文报告.md", owned)
        self.assertIn("写作资产/本书动态信号字典.json", owned)
        self.assertIn("写作资产/profile_source.md", payload["coordinator_only_writes"])
        self.assertNotIn("写作资产/profile_source.md", owned)
        self.assertIn("主线程用工具流统一检查 BID 跨文件贯通", payload["asset_join_gate"])
        self.assertTrue(any("prompt cache" in rule for rule in payload["cache_policy"]))
        self.assertNotIn(str(self.root / "原文" / "测试书.txt"), payload["asset_shared_reads"])
        self.assertEqual(payload["asset_shared_reads"], [])
        lane_reads = {lane["id"]: lane["preferred_reads"] for lane in payload["asset_lanes"]}
        delta_reads = {lane["id"]: lane["delta_reads"] for lane in payload["asset_lanes"]}
        self.assertIn("写作手法.md", lane_reads["tables_dialogue_relation"])
        self.assertNotIn("写作手法.md", lane_reads["source_details"])
        self.assertIn("写作资产/原文资产候选池.md", lane_reads["regular_assets"])
        self.assertEqual(delta_reads["source_details"], [])
        self.assertEqual(delta_reads["regular_assets"], [])
        self.assertEqual(delta_reads["sensitive_assets"], [])
        self.assertEqual(
            delta_reads["tables_structure_action"],
            ["写作资产/本书动态信号字典.json", "写作资产/原文资产候选池.md"],
        )
        self.assertEqual(payload["source_on_demand"], str(self.root / "原文" / "测试书.txt"))
        foundation_executors = {
            lane["id"]: lane["executor"] for lane in payload["foundation_lanes"]
        }
        asset_executors = {
            lane["id"]: lane["executor"] for lane in payload["asset_lanes"]
        }
        self.assertEqual(foundation_executors["discovery_index"], "agent-discovery")
        self.assertEqual(asset_executors["source_details"], "agent-discovery")
        self.assertEqual(foundation_executors["main_report"], "agent-core")
        self.assertEqual(asset_executors["tables_structure_action"], "agent-core")
        self.assertEqual(
            payload["worker_sequences"]["agent-core"],
            ["main_report", "tables_structure_action", "sensitive_assets"],
        )
        self.assertEqual(
            payload["asset_dispatch_groups"]["agent-core"],
            ["tables_structure_action", "sensitive_assets"],
        )
        foundation_contracts = {
            lane["id"]: lane["first_write_contract"]
            for lane in payload["foundation_lanes"]
        }
        report_contract = foundation_contracts["main_report"]["files"]["拆文报告.md"]
        self.assertIn("### 原文覆盖确认", report_contract["required_headings"])
        self.assertIn("### 主角能动性三层判断", report_contract["required_headings"])
        self.assertEqual(
            report_contract["structure_table_columns"],
            ["字数范围", "占比", "功能", "对应节"],
        )
        chronology_contract = foundation_contracts["chronology_craft"]
        node_contract = chronology_contract["files"]["情节节点.md"]
        self.assertIn("BID-01 中段承重桥", node_contract["bid_rules"][1])
        self.assertIn("故事时序", node_contract["required_entry_fields"])
        craft_contract = chronology_contract["files"]["写作手法.md"]
        self.assertEqual(len(craft_contract["required_headings"]), 14)
        self.assertIn("反面仿写句", craft_contract["required_sentence_assets"])
        self.assertIn("## 10. 全局成文形状审计", craft_contract["required_headings"])
        self.assertIn("原文证据", craft_contract["global_shape_audit_fields"])
        discovery_contract = foundation_contracts["discovery_index"]["files"]
        self.assertEqual(
            discovery_contract["写作资产/本书动态信号字典.json"]["format"],
            "合法 JSON；禁止 Markdown 代码围栏",
        )
        self.assertEqual(
            discovery_contract["写作资产/原文资产候选池.md"][
                "min_reverse_audit_items"
            ],
            5,
        )
        for lane in payload["foundation_lanes"]:
            self.assertTrue(
                any("first_write_contract" in rule for rule in lane["rules"])
            )
            self.assertTrue(
                any("固定标题逐字命中且各一次" in rule for rule in lane["rules"])
            )
        contracts = {
            lane["id"]: lane["first_write_contract"]
            for lane in payload["asset_lanes"]
        }
        structure_tables = contracts["tables_structure_action"]["tables"]
        dialogue_tables = contracts["tables_dialogue_relation"]["tables"]
        self.assertEqual(
            structure_tables["可直接仿写_导语拆解表.md"]["columns"],
            ["层级", "钩子内容", "第一句功能", "原文证据", "迁移提醒"],
        )
        sequence_columns = structure_tables["可直接仿写_顺序事件表.md"]["columns"]
        for field in ("读者情绪拍", "情绪烈度", "是否反刀或峰值", "场末余痛"):
            self.assertIn(field, sequence_columns)
        self.assertEqual(structure_tables["可直接仿写_动作表.md"]["min_rows"], 5)
        self.assertEqual(dialogue_tables["可直接仿写_公开炸场表.md"]["min_rows"], 4)
        self.assertEqual(
            contracts["tables_structure_action"]["trailing_sections"],
            [
                "## 可直接借的承重结构",
                "## 迁移顺序提醒",
                "## 为什么这个顺序不能乱",
            ],
        )
        self.assertIn(
            "具体发生了什么",
            contracts["source_details"]["card_fields"],
        )
        self.assertEqual(contracts["source_details"]["min_cards_per_file"], 5)
        self.assertEqual(
            contracts["regular_assets"]["required_sections"][
                "写作资产/情绪母线.md"
            ],
            ["## 原文证据层"],
        )
        sample_labels = contracts["sensitive_assets"]["files"][
            "写作资产/样本分级与可学层.md"
        ]["required_labels"]
        self.assertIn("structure_grade: A/B/C", sample_labels)
        bridge_contract = contracts["sensitive_assets"]["files"][
            "写作资产/桥段施工卡.md"
        ]
        self.assertEqual(bridge_contract["card_heading"], "## BID-xx 独一桥段名")
        self.assertIn("原文为什么能过", bridge_contract["required_card_labels"])
        for lane in payload["asset_lanes"]:
            self.assertTrue(
                any("first_write_contract" in rule for rule in lane["rules"])
            )

    def test_parallel_plan_scales_first_write_floors_for_short_source(self) -> None:
        path = self.root / "_parallel_plan.json"
        PREPARER.write_parallel_plan(path, self.root / "原文" / "测试书.txt", 4000)
        payload = json.loads(path.read_text(encoding="utf-8"))
        contracts = {
            lane["id"]: lane["first_write_contract"]
            for lane in payload["asset_lanes"]
        }
        tables = contracts["tables_structure_action"]["tables"]
        self.assertEqual(tables["可直接仿写_动作表.md"]["min_rows"], 4)
        self.assertEqual(tables["可直接仿写_导语拆解表.md"]["min_rows"], 2)
        self.assertEqual(contracts["source_details"]["min_cards_per_file"], 3)

    def test_sequence_event_semantic_contract_requires_emotion_parity_fields(self) -> None:
        semantic_groups = VALIDATOR.DIRECT_SEMANTIC_HEADER_GROUPS[
            "可直接仿写_顺序事件表.md"
        ]
        flattened = {alias for group in semantic_groups for alias in group}
        for field in ("读者情绪拍", "情绪烈度", "是否反刀或峰值", "场末余痛"):
            self.assertIn(field, flattened)

    def test_sensitive_contract_requires_bid_emotion_sequence(self) -> None:
        for rel in ("写作资产/高敏桥段识别.md", "写作资产/桥段施工卡.md"):
            labels = PREPARER.SENSITIVE_ASSET_FIRST_WRITE_CONTRACT[rel][
                "required_card_labels"
            ]
            self.assertIn("情绪拍", labels)
            self.assertIn("情绪拍完整性复核", labels)
            self.assertNotIn("情绪进入点", labels)

    def test_profile_emotion_sequence_preserves_repeated_actual_beats(self) -> None:
        errors: list[str] = []
        data = {
            "scene_assets": {},
            "banned_phrases": ["禁句"],
            "author_stance_patterns": ["站位"],
            "style_assets": {key: [] for key in VALIDATOR.REQUIRED_STYLE_ASSET_KEYS},
            "story_guardrails": {},
            "bridge_rules": [
                {
                    "must_keep": ["承重动作"],
                    "emotion_sequence": [
                        {
                            "beat_id": "E-01",
                            "role": "第一次刺痛",
                            "content": "第一次被当众略过",
                            "intensity": 7,
                            "source_evidence": "L10 第一次略过",
                        },
                        {
                            "beat_id": "E-02",
                            "role": "第二次刺痛",
                            "content": "追问后再次被略过",
                            "intensity": 8,
                            "source_evidence": "L12 再次略过",
                        },
                    ],
                }
            ],
        }
        VALIDATOR.check_book_profile_quality(
            self.root / "book.profile.json", data, 8000, "", errors
        )
        emotion_errors = [item for item in errors if "emotion_sequence" in item or "E-0" in item]
        self.assertEqual([], emotion_errors)

    def test_profile_alignment_error_requires_regenerating_profile_after_ledger_change(self) -> None:
        full_emotion_ledger = {
            "beats": [
                {
                    "beat_id": "E-01",
                    "role": "第一次刺痛",
                    "intensity": 7,
                    "source_evidence": ["L10 第一次略过"],
                    "bid_ids": ["BID-01"],
                },
                {
                    "beat_id": "E-02",
                    "role": "第二次刺痛",
                    "intensity": 8,
                    "source_evidence": ["L12 再次略过"],
                    "bid_ids": ["BID-01"],
                },
            ]
        }
        book_profile = {
            "bridge_rules": [
                {
                    "id": "BID-01",
                    "emotion_sequence": [
                        {
                            "beat_id": "E-01",
                            "role": "第一次刺痛",
                            "intensity": 7,
                            "source_evidence": "L10 第一次略过",
                        }
                    ],
                }
            ]
        }
        errors: list[str] = []
        VALIDATOR.check_book_profile_emotion_ledger_alignment(
            self.root, book_profile, full_emotion_ledger, errors
        )
        self.assertTrue(any("重生 book.profile.json" in item for item in errors))

    def test_profile_alignment_rejects_summarized_emotion_content(self) -> None:
        full_emotion_ledger = {
            "beats": [
                {
                    "beat_id": "E-01",
                    "role": "第一次刺痛",
                    "content": "她当众问出旧案责任，旁观者第一次停止附和。",
                    "intensity": 7,
                    "source_evidence": ["L10 第一次略过"],
                    "bid_ids": ["BID-01"],
                }
            ]
        }
        book_profile = {
            "bridge_rules": [
                {
                    "id": "BID-01",
                    "emotion_sequence": [
                        {
                            "beat_id": "E-01",
                            "role": "第一次刺痛",
                            "content": "她受了委屈。",
                            "intensity": 7,
                            "source_evidence": "L10 第一次略过",
                        }
                    ],
                }
            ]
        }
        errors: list[str] = []
        VALIDATOR.check_book_profile_emotion_ledger_alignment(
            self.root, book_profile, full_emotion_ledger, errors
        )
        self.assertTrue(any("content 与全文情绪总账不一致" in item for item in errors))

    def test_human_review_receipt_must_match_current_notes_and_markdown_hashes(self) -> None:
        self._write("拆文报告.md", "第一版\n")
        notes = [
            f"模型复核提示：{self.root / '拆文报告.md'} 需要人工判断是否压缩化"
        ]
        review_items = VALIDATOR.build_human_review_items(self.root, notes)
        receipt_path = self.root / "_finalize_human_review.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "skill_fingerprint": VALIDATOR.compute_skill_fingerprint(),
                    "upgrade_status": "not_applicable",
                    "upgrade_reviews": [],
                    "formal_markdown_sha1s": VALIDATOR.formal_markdown_sha1s(self.root),
                    "review_items": [
                        {
                            "id": review_items[0]["id"],
                            "status": "resolved",
                            "judgement": "已回看全文，当前段落不是模板壳。",
                            "evidence": ["拆文报告.md"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        errors: list[str] = []
        VALIDATOR.check_human_review_receipt(self.root, notes, {}, errors)
        self.assertEqual([], errors)

        self._write("拆文报告.md", "第二版\n")
        stale_errors: list[str] = []
        VALIDATOR.check_human_review_receipt(self.root, notes, {}, stale_errors)
        self.assertTrue(any("Markdown SHA" in error for error in stale_errors))

    def test_long_parallel_plan_reuses_three_agent_sessions(self) -> None:
        path = self.root / "_parallel_plan.json"
        PREPARER.write_parallel_plan(path, self.root / "原文" / "测试书.txt", 18000)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["executor_profile"], "long-reuse-3-agents")
        self.assertEqual(payload["agent_strategy"]["agent_session_limit"], 3)
        self.assertEqual(
            next(
                lane["executor"]
                for lane in payload["foundation_lanes"]
                if lane["id"] == "discovery_index"
            ),
            "agent-discovery",
        )

    def test_timing_state_records_elapsed_stage(self) -> None:
        PREPARER.write_timing_state(self.root / "_timing.json")
        started = TIMING.update_stage(self.root, "start", "foundation", "测试")
        self.assertEqual(started["status"], "running")
        finished = TIMING.update_stage(self.root, "finish", "foundation", "")
        self.assertEqual(finished["status"], "completed")
        self.assertGreaterEqual(finished["elapsed_seconds"], 0)

    def test_foundation_brief_freezes_valid_bid_registry(self) -> None:
        self._write(
            "_analysis_brief.md",
            "\n".join(
                [
                    "# 分析契约",
                    "- 故事核：规则场掉位后进入现实清算",
                    "- 主角：许初",
                    "- 核心关系：许初 / 蒋湛 / 夏禾",
                    "- 时间边界：扫黄当晚到离婚后三个月",
                    "- 固定称谓：许初、蒋湛、夏禾",
                    "- BID 注册表：以下记录为全书唯一编号",
                    "BID-01 | L2-L4 | 锚点：原文连续锚点 | 桥段角色：现实伤承重",
                ]
            )
            + "\n",
        )
        errors: list[str] = []
        bids = FOUNDATION.check_analysis_brief(
            self.root,
            ["第一行", "原文连续锚点", "第三行", "第四行"],
            errors,
        )
        self.assertEqual(bids, ["BID-01"])
        self.assertEqual(errors, [])

    def test_foundation_bridge_span_allows_dense_bridge_but_rejects_overwide_one(self) -> None:
        source_lines = [f"第{index}行" for index in range(1, 183)]
        source_lines[0] = "桥段锚点"
        self._write(
            "_analysis_brief.md",
            "\n".join(
                [
                    "# 分析契约",
                    "- 故事核：关系规则经过连续现场完成翻转",
                    "- 主角：甲",
                    "- 核心关系：甲 / 乙",
                    "- 时间边界：当日至次日",
                    "- 固定称谓：甲、乙",
                    "- BID 注册表：以下记录为全书唯一编号",
                    "BID-01 | L1-L180 | 锚点：桥段锚点 | 桥段角色：保留连续现场的完整承重链",
                    "BID-02 | L1-L181 | 锚点：桥段锚点 | 桥段角色：故意越过允许的桥段行域上限",
                ]
            )
            + "\n",
        )
        errors: list[str] = []
        bids = FOUNDATION.check_analysis_brief(self.root, source_lines, errors)
        self.assertEqual(bids, ["BID-01", "BID-02"])
        self.assertFalse(any("BID-01 范围过宽" in error for error in errors))
        self.assertTrue(any("BID-02 范围过宽" in error for error in errors))

    def test_foundation_rejects_ledger_bid_outside_frozen_range(self) -> None:
        ledger = {
            "beats": [
                {
                    "beat_id": "P-001",
                    "source_range": {"start_line": 8, "end_line": 9},
                    "bid_ids": ["BID-01"],
                }
            ]
        }
        errors: list[str] = []
        FOUNDATION.check_ledger_bid_ranges(
            ledger,
            "全文情节微拍总账",
            {"BID-01": (2, 4)},
            errors,
        )
        self.assertTrue(any("超出 BID-01 冻结范围" in error for error in errors))

    def test_character_names_prefer_report_character_table(self) -> None:
        path = self._write(
            "拆文报告.md",
            """### 人物分析

| 人物 | 叙事角色 |
|---|---|
| 嘉宁 | 主人公 |
| 傅与宁 | 共同情感主人公 |

**嘉宁为什么不是扁平圣人**：她会误判。
**傅与宁为什么不只是被救男配**：他会试探。

### 开头分析
""",
        )
        self.assertEqual(
            {"嘉宁", "傅与宁"},
            VALIDATOR.extract_report_character_names(path),
        )

    def test_relationship_old_case_label_is_not_reported_missing(self) -> None:
        detail_dir = self.root / "原文细节库"
        detail_dir.mkdir()
        (detail_dir / "关系细节库.md").write_text(
            "# 关系细节库\n\n- 关系起点：两人从利益合作开始。\n"
            "- 旧案标签：童年失约、旧事隐瞒共同构成关系旧案。\n",
            encoding="utf-8",
        )
        notes: list[str] = []
        VALIDATOR.check_cross_asset_semantics(
            self.root,
            "他小时候曾经失约。",
            1000,
            [],
            notes,
        )
        self.assertFalse(any("未命中常用旧案标签" in note for note in notes))

    def test_relationship_old_case_warning_remains_without_semantic_label(self) -> None:
        detail_dir = self.root / "原文细节库"
        detail_dir.mkdir()
        (detail_dir / "关系细节库.md").write_text(
            "# 关系细节库\n\n- 关系起点：两人在公司认识。\n",
            encoding="utf-8",
        )
        notes: list[str] = []
        VALIDATOR.check_cross_asset_semantics(
            self.root,
            "他小时候曾经失约。",
            1000,
            [],
            notes,
        )
        self.assertTrue(any("未命中常用旧案标签" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
