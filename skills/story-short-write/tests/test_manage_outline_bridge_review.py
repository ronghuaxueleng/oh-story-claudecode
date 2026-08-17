from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "manage_outline_bridge_review.py"
SPEC = importlib.util.spec_from_file_location("manage_outline_bridge_review", SCRIPT)
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class ManageOutlineBridgeReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.receipt = self.root / "细纲表演验收回执.json"
        self.template = self.root / "桥级回填侧车.json"
        self.source_dir = self.root / "拆文库" / "测试书" / "原文"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.source_original = self.source_dir / "测试书.txt"
        self.source_original.write_text("示例原文\n", encoding="utf-8")
        self.ledger = self.root / "拆文库" / "测试书" / "写作资产" / "全文情绪颗粒总账.json"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self._write_ledger()
        self._write_receipt()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_receipt(self) -> None:
        payload = {
            "outline_bridge_flow_parity": [
                {
                    "source_bridge_id": "BID-01",
                    "source_bridge_name": "公开掉位",
                    "source_path": str(self.source_original),
                    "target_plot_beats": [],
                    "plot_beat_mapping": [],
                    "source_emotion_sequence": [],
                    "target_emotion_sequence": [],
                    "target_outline_sections": [],
                    "target_outline_evidence": [],
                    "plot_granularity_parity_judgment": "",
                    "emotion_parity_judgment": "",
                    "reader_experience_parity": None,
                    "parity_status": "pending",
                    "adaptation_reason": "",
                    "missing_or_weakened_risk": "",
                    "manual_judgment": "",
                }
            ],
            "outside_bridge_plot_parity": {
                "source_path": str(self.source_original),
                "target_plot_beats": [],
                "plot_beat_mapping": [],
                "source_emotion_sequence": [],
                "target_outline_sections": [],
                "target_outline_evidence": [],
                "plot_granularity_parity_judgment": "",
                "emotion_parity_judgment": "",
                "reader_experience_parity": None,
                "parity_status": "pending",
                "adaptation_reason": "",
                "missing_or_weakened_risk": "",
                "manual_judgment": "",
            },
        }
        self.receipt.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_ledger(self) -> None:
        payload = {
            "beats": [
                {
                    "beat_id": "E-001",
                    "role": "桥外拍",
                    "trigger": "桥外触发",
                    "relationship_position_change": "桥外位移",
                    "reader_effect": "桥外体感",
                    "intensity": 5,
                    "bid_ids": [],
                    "source_evidence": ["桥外证据"],
                },
                {
                    "beat_id": "E-010",
                    "role": "桥内拍1",
                    "trigger": "桥内触发1",
                    "relationship_position_change": "桥内位移1",
                    "reader_effect": "桥内体感1",
                    "intensity": 7,
                    "bid_ids": ["BID-01"],
                    "source_evidence": ["桥内证据1"],
                },
                {
                    "beat_id": "E-011",
                    "role": "桥内拍2",
                    "trigger": "桥内触发2",
                    "relationship_position_change": "桥内位移2",
                    "reader_effect": "桥内体感2",
                    "intensity": 8,
                    "bid_ids": ["BID-01"],
                    "source_evidence": ["桥内证据2"],
                },
            ]
        }
        self.ledger.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_export_template_preserves_bridge_identity(self) -> None:
        payload = TOOL.export_template(self.receipt, self.template)
        self.assertEqual("story-short-write.outline-bridge-review-template.v1", payload["schema_version"])
        self.assertEqual("BID-01", payload["outline_bridge_flow_parity"][0]["source_bridge_id"])
        self.assertEqual("outside", payload["outside_bridge_plot_parity"]["source_bridge_id"])
        self.assertTrue(self.template.is_file())

    def test_apply_template_merges_only_bridge_level_non_beat_fields(self) -> None:
        TOOL.export_template(self.receipt, self.template)
        payload = json.loads(self.template.read_text(encoding="utf-8"))
        payload["outline_bridge_flow_parity"][0].update(
            {
                "target_outline_sections": ["1", "2"],
                "target_outline_evidence": ["- 主事件：测试", "- 场面单元：测试"],
                "plot_granularity_parity_judgment": "桥级颗粒一致",
                "emotion_parity_judgment": "情绪颗粒一致",
                "reader_experience_parity": True,
                "parity_status": "adapted",
                "adaptation_reason": "换壳不换桥",
                "missing_or_weakened_risk": "若少掉补台会变弱",
                "manual_judgment": "人工确认通过",
            }
        )
        payload["outside_bridge_plot_parity"].update(
            {
                "target_outline_sections": ["1"],
                "target_outline_evidence": ["- 子事件：测试"],
                "plot_granularity_parity_judgment": "桥外已承接",
                "emotion_parity_judgment": "桥外情绪已承接",
                "reader_experience_parity": True,
                "parity_status": "matched",
                "adaptation_reason": "题面前置",
                "missing_or_weakened_risk": "无",
                "manual_judgment": "人工确认桥外通过",
            }
        )
        self.template.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        merged = TOOL.apply_template(self.receipt, self.template)
        bridge = merged["outline_bridge_flow_parity"][0]
        self.assertEqual(["1", "2"], bridge["target_outline_sections"])
        self.assertEqual("adapted", bridge["parity_status"])
        self.assertEqual([], bridge["target_plot_beats"])
        self.assertEqual([], bridge["plot_beat_mapping"])
        self.assertEqual([], bridge["source_emotion_sequence"])
        self.assertEqual([], bridge["target_emotion_sequence"])

    def test_export_and_apply_beat_template_merges_only_beat_fields(self) -> None:
        payload = TOOL.export_beat_template(self.receipt, self.template)
        self.assertEqual(
            "story-short-write.outline-bridge-beat-review-template.v1",
            payload["schema_version"],
        )
        payload["outline_bridge_flow_parity"][0].update(
            {
                "target_plot_beats": [{"beat_id": "P-001", "action": "测试"}],
                "plot_beat_mapping": [{"source_beat_id": "P-001", "target_beat_id": "P-001"}],
                "target_emotion_sequence": [{"beat_id": "E-001", "role": "测试"}],
                "source_reversal_beat": 1,
                "target_reversal_beat": 1,
                "source_peak_beat": 2,
                "target_peak_beat": 2,
            }
        )
        payload["outside_bridge_plot_parity"].update(
            {
                "target_plot_beats": [{"beat_id": "P-OUT", "action": "桥外测试"}],
                "plot_beat_mapping": [{"source_beat_id": "P-OUT", "target_beat_id": "P-OUT"}],
            }
        )
        self.template.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        merged = TOOL.apply_beat_template(self.receipt, self.template)
        bridge = merged["outline_bridge_flow_parity"][0]
        self.assertEqual([{"beat_id": "P-001", "action": "测试"}], bridge["target_plot_beats"])
        self.assertEqual(1, bridge["source_reversal_beat"])
        self.assertEqual([], bridge["target_outline_sections"])
        self.assertEqual("", bridge["plot_granularity_parity_judgment"])

    def test_plot_only_bridge_accepts_null_reader_parity_and_exports_policy(self) -> None:
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        bridge = receipt["outline_bridge_flow_parity"][0]
        bridge["emotion_transfer_policy"] = "plot_mechanism_only"
        bridge["reader_experience_parity"] = None
        bridge["source_reversal_beat"] = 0
        bridge["target_reversal_beat"] = 0
        bridge["source_peak_beat"] = 0
        bridge["target_peak_beat"] = 0
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        payload = TOOL.export_template(self.receipt, self.template)
        exported = payload["outline_bridge_flow_parity"][0]
        self.assertEqual("plot_mechanism_only", exported["emotion_transfer_policy"])
        exported.update(
            {
                "target_outline_sections": ["1"],
                "target_outline_evidence": ["目标动作一", "目标动作二"],
                "plot_granularity_parity_judgment": "辅助情节拍完整",
                "emotion_parity_judgment": "辅助桥不供应情绪拍",
                "reader_experience_parity": None,
                "parity_status": "adapted",
                "adaptation_reason": "只迁移情节机制",
                "missing_or_weakened_risk": "不得混入辅助声线",
                "manual_judgment": "P 拍完整，情绪保持禁用",
            }
        )
        payload["outside_bridge_plot_parity"] = None
        self.template.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        merged = TOOL.apply_template(self.receipt, self.template)
        self.assertIsNone(
            merged["outline_bridge_flow_parity"][0]["reader_experience_parity"]
        )

        beat_payload = TOOL.export_beat_template(self.receipt, self.template)
        self.assertEqual(
            "plot_mechanism_only",
            beat_payload["outline_bridge_flow_parity"][0][
                "emotion_transfer_policy"
            ],
        )

    def test_same_bridge_id_across_sources_merges_by_source_path(self) -> None:
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        auxiliary = self.root / "拆文库" / "辅助书" / "原文" / "辅助书.txt"
        auxiliary.parent.mkdir(parents=True, exist_ok=True)
        auxiliary.write_text("辅助原文\n", encoding="utf-8")
        second = dict(receipt["outline_bridge_flow_parity"][0])
        second["source_path"] = str(auxiliary)
        second["source_bridge_name"] = "辅助公开掉位"
        receipt["outline_bridge_flow_parity"].append(second)
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        payload = TOOL.export_template(self.receipt, self.template)
        self.assertEqual(2, len(payload["outline_bridge_flow_parity"]))
        for index, entry in enumerate(payload["outline_bridge_flow_parity"], start=1):
            entry.update(
                {
                    "target_outline_sections": [str(index)],
                    "target_outline_evidence": [f"目标动作{index}"],
                    "plot_granularity_parity_judgment": f"桥{index}颗粒一致",
                    "emotion_parity_judgment": f"桥{index}情绪一致",
                    "reader_experience_parity": True,
                    "parity_status": "adapted",
                    "adaptation_reason": f"桥{index}换壳",
                    "missing_or_weakened_risk": "无",
                    "manual_judgment": f"桥{index}已复核",
                }
            )
        payload["outside_bridge_plot_parity"] = None
        self.template.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        merged = TOOL.apply_template(self.receipt, self.template)
        by_source = {
            item["source_path"]: item for item in merged["outline_bridge_flow_parity"]
        }
        self.assertEqual(
            ["1"], by_source[str(self.source_original)]["target_outline_sections"]
        )
        self.assertEqual(["2"], by_source[str(auxiliary)]["target_outline_sections"])

    def test_rebind_outline_resets_review_status_and_updates_sha(self) -> None:
        original = json.loads(self.receipt.read_text(encoding="utf-8"))
        original["reviewed_by_current_model"] = True
        original["gate_status"] = "passed"
        original["blocking_failures"] = ["old"]
        self.receipt.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outline = self.root / "新大纲.md"
        outline.write_text("## 1. 新纲\n", encoding="utf-8")

        merged = TOOL.rebind_outline(self.receipt, outline)
        self.assertEqual(str(outline), merged["outline"]["path"])
        self.assertEqual(TOOL.sha256_file(outline), merged["outline"]["sha256"])
        self.assertFalse(merged["reviewed_by_current_model"])
        self.assertEqual("pending", merged["gate_status"])
        self.assertEqual([], merged["blocking_failures"])

    def test_seal_review_requires_validator_pass(self) -> None:
        outline = self.root / "新大纲.md"
        outline.write_text("## 1. 新纲\n", encoding="utf-8")
        validator = mock.Mock()
        validator.validate_receipt.return_value = []
        with mock.patch.object(TOOL, "load_outline_validator", return_value=validator):
            merged = TOOL.seal_review(self.receipt, outline)
        self.assertTrue(merged["reviewed_by_current_model"])
        self.assertEqual("passed", merged["gate_status"])
        self.assertEqual(str(outline), merged["outline"]["path"])

    def test_seal_review_blocks_when_validator_reports_errors(self) -> None:
        outline = self.root / "新大纲.md"
        outline.write_text("## 1. 新纲\n", encoding="utf-8")
        validator = mock.Mock()
        validator.validate_receipt.return_value = ["桥级未通过", "节级未通过"]
        with mock.patch.object(TOOL, "load_outline_validator", return_value=validator):
            with self.assertRaisesRegex(ValueError, "不能 seal-review"):
                TOOL.seal_review(self.receipt, outline)

    def test_apply_template_rejects_stale_receipt_sha(self) -> None:
        TOOL.export_template(self.receipt, self.template)
        payload = json.loads(self.template.read_text(encoding="utf-8"))
        payload["receipt_sha256"] = "stale"
        self.template.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "receipt_sha256 已失效"):
            TOOL.apply_template(self.receipt, self.template)

    def test_sync_source_emotions_fills_bridge_and_outside_from_ledger(self) -> None:
        summary = TOOL.sync_source_emotions(self.receipt)
        payload = json.loads(self.receipt.read_text(encoding="utf-8"))
        bridge = payload["outline_bridge_flow_parity"][0]
        outside = payload["outside_bridge_plot_parity"]

        self.assertEqual("story-short-write.outline-bridge-source-emotion-sync.v1", summary["schema_version"])
        self.assertEqual(["E-010", "E-011"], [item["beat_id"] for item in bridge["source_emotion_sequence"]])
        self.assertEqual(["桥内证据1", "桥内证据2"], [item["evidence"] for item in bridge["source_emotion_sequence"]])
        self.assertEqual(["E-001"], [item["beat_id"] for item in outside["source_emotion_sequence"]])
        self.assertEqual("桥外证据", outside["source_emotion_sequence"][0]["evidence"])
        self.assertEqual([], bridge["target_emotion_sequence"])

    def test_sync_source_emotions_skips_plot_only_and_keeps_duplicate_source_keys(self) -> None:
        aux_original = self.root / "拆文库" / "辅助书" / "原文" / "辅助书.txt"
        aux_original.parent.mkdir(parents=True, exist_ok=True)
        aux_original.write_text(self.source_original.read_text(encoding="utf-8"), encoding="utf-8")
        aux_ledger = self.root / "拆文库" / "辅助书" / "写作资产" / "全文情绪颗粒总账.json"
        aux_ledger.parent.mkdir(parents=True, exist_ok=True)
        aux_ledger.write_text(self.ledger.read_text(encoding="utf-8"), encoding="utf-8")
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        primary_bridge = receipt["outline_bridge_flow_parity"][0]
        primary_bridge["source_path"] = str(self.source_original)
        auxiliary_bridge = json.loads(json.dumps(primary_bridge, ensure_ascii=False))
        auxiliary_bridge["source_path"] = str(aux_original)
        auxiliary_bridge["emotion_transfer_policy"] = "plot_mechanism_only"
        receipt["outline_bridge_flow_parity"].append(auxiliary_bridge)
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        summary = TOOL.sync_source_emotions(self.receipt)
        merged = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(2, len(summary["bridge_counts"]))
        self.assertEqual(2, len(merged["outline_bridge_flow_parity"][0]["source_emotion_sequence"]))
        self.assertEqual([], merged["outline_bridge_flow_parity"][1]["source_emotion_sequence"])


if __name__ == "__main__":
    unittest.main()
