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
        self.project_root = self.root / "测试项目"
        self.config = self.project_root / "写作资产" / "项目写作配置.json"
        self.setting = self.project_root / "设定.md"
        self.outline = self.project_root / "小节大纲.md"
        self.outline_receipt = self.project_root / "写作资产" / "细纲表演验收回执.json"
        self.source_original = self.source / "原文" / "样本.txt"

        self._build_outline_support_assets()
        self.setting.parent.mkdir(parents=True, exist_ok=True)
        self.setting.write_text("设定内容", encoding="utf-8")
        self.outline.write_text("# 标题\n\n## 1. 起事\n\n大纲动作一\n", encoding="utf-8")
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(
            json.dumps(
                {
                    "project_name": "测试项目",
                    "primary": {
                        "name": "样本",
                        "original_path": str(self.source_original),
                    },
                    "auxiliaries": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _build_outline_support_assets(self) -> None:
        plot_ledger = self.source / "写作资产" / "全文情节微拍总账.json"
        emotion_ledger = self.source / "写作资产" / "全文情绪颗粒总账.json"
        bridge_catalog = self.source / "写作资产" / "桥段施工卡.md"
        subflow_catalog = self.source / "写作资产" / "子流程索引.jsonl"
        self.source_original.parent.mkdir(parents=True, exist_ok=True)
        plot_ledger.parent.mkdir(parents=True, exist_ok=True)
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
                    "schema_version": "story-short-analyze.full-text-emotion-ledger.v2",
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

    def test_start_outline_release_creates_only_outline_contract(self) -> None:
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
            force=False,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.outline_receipt.is_file())
        self.assertEqual(str(self.outline_receipt), summary["outline_receipt"])
        payload = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            list(GATE.OUTLINE.SOURCE_STYLE_GRANULARITY_FIELDS),
            payload["granularity_coverage"][0]["style_dimensions"],
        )
        self.assertEqual([], payload["granularity_coverage"][0]["target_regions"])
        self.assertTrue(payload["sources"][0]["subflow_catalog"]["sha256"])
        assets = self.project_root / "写作资产"
        self.assertEqual(
            {"项目写作配置.json", "细纲表演验收回执.json"},
            {path.name for path in assets.iterdir()},
        )

    def test_noncurrent_outline_contract_blocks_without_overwrite(self) -> None:
        self.outline_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.outline_receipt.write_text('{"marker": "preserve"}', encoding="utf-8")
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
            force=False,
        )
        self.assertTrue(errors)
        self.assertFalse(summary["outline_ready"])
        self.assertEqual(
            {"marker": "preserve"},
            json.loads(self.outline_receipt.read_text(encoding="utf-8")),
        )

    def test_current_outline_contract_is_resumed_without_overwrite(self) -> None:
        errors, _ = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )
        self.assertEqual([], errors)
        payload = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        payload["marker"] = "preserve"
        self.outline_receipt.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )
        self.assertEqual([], errors)
        self.assertTrue(summary["resumed_existing"])
        self.assertEqual(
            "preserve",
            json.loads(self.outline_receipt.read_text(encoding="utf-8"))["marker"],
        )

    def test_force_rebuilds_outline_contract(self) -> None:
        self.outline_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.outline_receipt.write_text('{"marker": "old"}', encoding="utf-8")
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
            force=True,
        )
        self.assertEqual([], errors)
        self.assertFalse(summary["resumed_existing"])
        payload = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        self.assertEqual("测试项目", payload["project"])

    def test_project_name_mismatch_blocks(self) -> None:
        errors, summary = GATE.start_outline_release(
            project="另一项目",
            project_dir=self.project_root,
        )
        self.assertTrue(errors)
        self.assertFalse(summary["outline_ready"])

    def test_missing_primary_style_dimension_blocks(self) -> None:
        subflow_catalog = self.source / "写作资产" / "子流程索引.jsonl"
        payload = json.loads(subflow_catalog.read_text(encoding="utf-8"))
        del payload["source_style_granularity"]["narrator_interjection_and_roughness"]
        subflow_catalog.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )
        self.assertTrue(errors)
        self.assertFalse(summary["outline_ready"])
        self.assertIn("narrator_interjection_and_roughness", errors[0])


if __name__ == "__main__":
    unittest.main()
