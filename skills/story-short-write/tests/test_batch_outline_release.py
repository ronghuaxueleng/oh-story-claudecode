from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_outline_release.py"
SPEC = importlib.util.spec_from_file_location("batch_outline_release", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchOutlineReleaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "拆文库" / "样本"
        self.project_root = self.root / "项目"
        self.writing_receipt = self.project_root / "写作资产" / "写作规则读取回执.json"
        self.source_receipt = self.project_root / "写作资产" / "拆文读取回执.json"
        self.ledger = self.project_root / "写作资产" / "规则执行台账.json"
        self.setting = self.project_root / "设定.md"
        self.outline = self.project_root / "小节大纲.md"
        self.setting_sequence_receipt = self.project_root / "写作资产" / "设定顺序契约回执.json"
        self.sequence_receipt = self.project_root / "写作资产" / "顺序契约回执.json"
        self.opening_source = self.source / "可直接仿写_导语拆解表.md"
        self.opening_receipt = self.project_root / "写作资产" / "开头承重契约回执_大纲.json"
        self.outline_receipt = self.project_root / "写作资产" / "细纲表演验收回执.json"
        self.model_review = self.project_root / "写作资产" / "规则模型分类批次.json"
        self.source_original = self.source / "原文" / "样本.txt"

        self._build_source_inventory()
        self._build_outline_support_assets()
        self._build_passed_read_receipts()
        self.setting.parent.mkdir(parents=True, exist_ok=True)
        self.setting.write_text("设定内容", encoding="utf-8")
        self.outline.write_text("# 标题\n\n## 1. 起事\n\n大纲动作一\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _build_source_inventory(self) -> None:
        required_files = GATE.OUTLINE.source_plot_ledger_path  # type: ignore[attr-defined]
        _ = required_files
        for relative in GATE.RULE_LEDGER.load_json(  # type: ignore[attr-defined]
            # dummy; not executed because replaced below
            ROOT / "tests" / "fixtures" / "nonexistent.json"  # pragma: no cover
        ) if False else []:
            pass

        source_gate_spec = importlib.util.spec_from_file_location(
            "source_read_gate_for_outline_batch",
            ROOT / "scripts" / "validate_source_read_gate.py",
        )
        assert source_gate_spec and source_gate_spec.loader
        source_gate = importlib.util.module_from_spec(source_gate_spec)
        source_gate_spec.loader.exec_module(source_gate)
        for relative in source_gate.REQUIRED_FILES:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                path.write_text('{"证据词": "资产证据"}', encoding="utf-8")
            else:
                path.write_text(f"# {path.stem}\n\n资产证据\n", encoding="utf-8")

    def _build_passed_read_receipts(self) -> None:
        writing_gate_spec = importlib.util.spec_from_file_location(
            "writing_rule_gate_for_outline_batch",
            ROOT / "scripts" / "validate_writing_rule_gate.py",
        )
        assert writing_gate_spec and writing_gate_spec.loader
        writing_gate = importlib.util.module_from_spec(writing_gate_spec)
        writing_gate_spec.loader.exec_module(writing_gate)
        source_gate_spec = importlib.util.spec_from_file_location(
            "source_read_gate_for_outline_batch",
            ROOT / "scripts" / "validate_source_read_gate.py",
        )
        assert source_gate_spec and source_gate_spec.loader
        source_gate = importlib.util.module_from_spec(source_gate_spec)
        source_gate_spec.loader.exec_module(source_gate)

        skill_root = ROOT
        writing_receipt, writing_errors = writing_gate.create_receipt("测试项目", skill_root)
        self.assertEqual([], writing_errors)
        writing_receipt["gate_status"] = "passed"
        writing_receipt["confirmed_before_outline"] = True
        writing_receipt["confirmed_before_draft"] = True
        for item in writing_receipt["files"]:
            item["status"] = "read"
            item["evidence_terms"] = [writing_gate.read_text(skill_root / item["path"]).splitlines()[0].lstrip("# ").strip()]
            item["takeaways"] = ["已读取当前规则并提取写前约束"]
            item["used_for"] = ["设定、大纲与正文"]
        self.writing_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.writing_receipt.write_text(
            json.dumps(writing_receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        source_receipt, source_errors = source_gate.create_receipt("测试项目", [self.source])
        self.assertEqual([], source_errors)
        source_receipt["gate_status"] = "passed"
        source_receipt["confirmed_before_outline"] = True
        source_receipt["confirmed_before_draft"] = True
        for source_item in source_receipt["sources"]:
            for item in source_item["files"]:
                item["status"] = "read"
                item["evidence_terms"] = ["资产证据"]
                item["takeaways"] = ["已提取该文件的可迁移资产"]
                item["used_for"] = ["细纲与正文"]
        self.source_receipt.write_text(
            json.dumps(source_receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_outline_support_assets(self) -> None:
        plot_ledger = self.source / "写作资产" / "全文情节微拍总账.json"
        emotion_ledger = self.source / "写作资产" / "全文情绪颗粒总账.json"
        bridge_catalog = self.source / "写作资产" / "桥段施工卡.md"
        subflow_catalog = self.source / "写作资产" / "子流程索引.jsonl"
        self.source_original.parent.mkdir(parents=True, exist_ok=True)
        self.source_original.write_text(
            "原文场面里，他先伸手拦我，我把他的手推开。"
            "我没想到他还会替别人解释。"
            "解释什么？"
            "钥匙放在桌上，她先拿走了。"
            "有意思，现在倒像是我进错了门。"
            "最后门关上了。",
            encoding="utf-8",
        )

        plot_ledger.write_text(
            json.dumps(
                {
                    "schema_version": GATE.OUTLINE.FULL_BRIDGE_PLOT_LEDGER_SCHEMA,
                    "beats": [
                        {
                            "beat_id": "P-001",
                            "actor": "他",
                            "action": "伸手拦住",
                            "object_or_receiver": "我",
                            "pressure_or_trigger": "我准备离开",
                            "control_change": "他试图拦截",
                            "information_change": "我意识到他仍先解释别人",
                            "consequence": "关系掉位",
                            "source_range": {"start_line": 1, "end_line": 1},
                            "source_evidence": "原文场面里，他先伸手拦我，我把他的手推开。",
                            "bid_ids": ["BID-01"],
                        }
                    ],
                    "coverage_segments": [{"segment_id": "SEG-01", "beat_ids": ["P-001"]}],
                    "source_plot_candidate_audit": [{"candidate_id": "PC-001"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        emotion_ledger.write_text(
            json.dumps(
                {
                    "schema_version": "story-short-analyze.full-text-emotion-ledger.v1",
                    "beats": [
                        {
                            "beat_id": "E-001",
                            "role": "第一次刺痛",
                            "content": "先护别人",
                            "trigger": "他先解释别人",
                            "relationship_position_change": "我掉位",
                            "reader_effect": "刺痛",
                            "narrative_function": "推进离开",
                            "intensity": 8,
                            "source_evidence": ["我没想到他还会替别人解释。"],
                            "bid_ids": ["BID-01"],
                        }
                    ],
                    "coverage_segments": [{"segment_id": "SEG-01", "beat_ids": ["E-001"]}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        bridge_catalog.write_text(
            "## BID-01\n\n桥段说明\n",
            encoding="utf-8",
        )
        subflow_catalog.write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "source_range": "L1-L3",
                    "source_style_granularity": {
                        "narrative_voice_and_attitude": [{"evidence": "我没想到"}],
                        "sentence_relation_and_rhythm": [{"evidence": "先拦后推"}],
                        "paragraph_breath_and_cut_points": [{"evidence": "动作紧接"}],
                        "dialogue_misfire_or_avoidance": [{"evidence": "解释什么？"}],
                        "action_perception_emotion_weave": [{"evidence": "伸手拦我"}],
                        "narrator_interjection_and_roughness": [{"evidence": "有意思"}],
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_init_creates_all_outline_release_receipts(self) -> None:
        errors, summary = GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            ledger=self.ledger,
            setting=self.setting,
            outline=self.outline,
            setting_sequence_receipt=self.setting_sequence_receipt,
            sequence_receipt=self.sequence_receipt,
            opening_source=self.opening_source,
            opening_receipt=self.opening_receipt,
            outline_receipt=self.outline_receipt,
            source_originals=[self.source_original],
            force_ledger=False,
            force_setting_sequence=False,
            force_sequence=False,
            force_opening=False,
            force_outline_receipt=False,
            export_model_review_output=self.model_review,
            export_batch_size=30,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.ledger.is_file())
        self.assertTrue(self.setting_sequence_receipt.is_file())
        self.assertTrue(self.sequence_receipt.is_file())
        self.assertTrue(self.opening_receipt.is_file())
        self.assertTrue(self.outline_receipt.is_file())
        self.assertTrue(self.model_review.is_file())
        self.assertGreater(summary["skill_rules"], 0)
        self.assertGreater(summary["model_review_entries"], 0)

    def test_existing_receipt_blocks_without_force(self) -> None:
        self.opening_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.opening_receipt.write_text("{}", encoding="utf-8")
        errors, _summary = GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            ledger=self.ledger,
            setting=self.setting,
            outline=self.outline,
            setting_sequence_receipt=self.setting_sequence_receipt,
            sequence_receipt=self.sequence_receipt,
            opening_source=self.opening_source,
            opening_receipt=self.opening_receipt,
            outline_receipt=self.outline_receipt,
            source_originals=[self.source_original],
            force_ledger=False,
            force_setting_sequence=False,
            force_sequence=False,
            force_opening=False,
            force_outline_receipt=False,
            export_model_review_output=None,
            export_batch_size=30,
        )
        self.assertTrue(any("开头契约回执已存在" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
