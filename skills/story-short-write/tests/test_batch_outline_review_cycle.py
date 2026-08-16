from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_outline_review_cycle.py"
SPEC = importlib.util.spec_from_file_location("batch_outline_review_cycle", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchOutlineReviewCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_dir = self.root / "项目"
        self.assets = self.project_dir / "写作资产"
        self.receipt = self.assets / "细纲表演验收回执.json"
        self.outline = self.project_dir / "小节大纲.md"
        self.bridge_review = self.assets / "桥级回填侧车.json"
        self.bridge_beat_review = self.assets / "桥级逐拍回填侧车.json"
        self.section_review = self.assets / "节级回填侧车.json"
        self.source_dir = self.root / "拆文库" / "测试书" / "原文"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.source_original = self.source_dir / "测试书.txt"
        self.source_original.write_text("示例原文\n", encoding="utf-8")
        self.ledger = self.root / "拆文库" / "测试书" / "写作资产" / "全文情绪颗粒总账.json"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self._write_ledger()
        self._write_receipt()
        self.outline.parent.mkdir(parents=True, exist_ok=True)
        self.outline.write_text("## 1. 新纲\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

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
            ]
        }
        self.ledger.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
                    "source_reversal_beat": None,
                    "target_reversal_beat": None,
                    "source_peak_beat": None,
                    "target_peak_beat": None,
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
            "sections": [
                {
                    "section_id": "1",
                    "verdict": "pending",
                    "irreversible_action": "",
                    "controlling_object": "",
                    "source_function_mechanism": "",
                    "original_scene_granularity": "",
                    "source_mechanism": "",
                    "information_delay": "",
                    "character_missteps": "",
                    "interaction_exchange": "",
                    "conflict_carrier": "",
                    "relationship_legibility": "",
                    "emotion_intensity": "",
                    "professional_shell_translation": "",
                    "source_emotion_parity": [],
                    "forbidden_items": [],
                    "outline_evidence": [],
                    "scene_units": [],
                    "manual_judgment": "",
                }
            ],
            "reviewed_by_current_model": False,
            "gate_status": "pending",
            "blocking_failures": [],
        }
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        self.receipt.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _fill_sidecars(self) -> None:
        bridge = json.loads(self.bridge_review.read_text(encoding="utf-8"))
        bridge["outline_bridge_flow_parity"][0].update(
            {
                "target_outline_sections": ["1"],
                "target_outline_evidence": ["- 场面单元：桥内测试"],
                "plot_granularity_parity_judgment": "桥级颗粒一致",
                "emotion_parity_judgment": "情绪颗粒一致",
                "reader_experience_parity": True,
                "parity_status": "matched",
                "adaptation_reason": "桥内机制已迁移",
                "missing_or_weakened_risk": "无",
                "manual_judgment": "桥内已形成完整承重链",
            }
        )
        bridge["outside_bridge_plot_parity"].update(
            {
                "target_outline_sections": ["1"],
                "target_outline_evidence": ["- 主事件：桥外测试"],
                "plot_granularity_parity_judgment": "桥外颗粒一致",
                "emotion_parity_judgment": "桥外情绪一致",
                "reader_experience_parity": True,
                "parity_status": "adapted",
                "adaptation_reason": "题面前置",
                "missing_or_weakened_risk": "无",
                "manual_judgment": "桥外已承接",
            }
        )
        self.bridge_review.write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        beat = json.loads(self.bridge_beat_review.read_text(encoding="utf-8"))
        beat["outline_bridge_flow_parity"][0].update(
            {
                "target_plot_beats": [{"beat_id": "P-001", "action": "测试"}],
                "plot_beat_mapping": [{"source_beat_id": "P-001", "target_beat_id": "P-001"}],
                "target_emotion_sequence": [{"beat_id": "E-010", "role": "测试"}],
                "source_reversal_beat": 1,
                "target_reversal_beat": 1,
                "source_peak_beat": 1,
                "target_peak_beat": 1,
            }
        )
        beat["outside_bridge_plot_parity"].update(
            {
                "target_plot_beats": [{"beat_id": "P-OUT", "action": "桥外测试"}],
                "plot_beat_mapping": [{"source_beat_id": "P-OUT", "target_beat_id": "P-OUT"}],
            }
        )
        self.bridge_beat_review.write_text(json.dumps(beat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        section = json.loads(self.section_review.read_text(encoding="utf-8"))
        section["sections"][0].update(
            {
                "verdict": "passed",
                "irreversible_action": "当众撤掉解释权",
                "controlling_object": "钥匙",
                "source_function_mechanism": "公开掉位",
                "original_scene_granularity": "一场双压",
                "source_mechanism": "先挡后错答",
                "information_delay": "先不解释钥匙",
                "character_missteps": "他先护别人",
                "interaction_exchange": "拦住-错答-掉位",
                "conflict_carrier": "钥匙归属",
                "relationship_legibility": "她被现场换主",
                "emotion_intensity": "8",
                "professional_shell_translation": "无职业壳污染",
                "source_emotion_parity": [{"beat_id": "E-010"}],
                "forbidden_items": ["不要解释背景"],
                "outline_evidence": ["他先拦我"],
                "scene_units": [{"allocated_chars": 1200, "entry_pressure": "当众选边"}],
                "manual_judgment": "节级已形成完整场面",
            }
        )
        self.section_review.write_text(json.dumps(section, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_prepare_outline_review_exports_all_sidecars(self) -> None:
        errors, summary = GATE.prepare_outline_review(
            project="测试项目",
            project_dir=self.project_dir,
            receipt=None,
            outline=None,
            bridge_review=None,
            bridge_beat_review=None,
            section_review=None,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.bridge_review.is_file())
        self.assertTrue(self.bridge_beat_review.is_file())
        self.assertTrue(self.section_review.is_file())
        self.assertEqual(1, summary["section_review_sections"])

    def test_status_and_next_step_identify_manual_phase(self) -> None:
        GATE.prepare_outline_review(
            project="测试项目",
            project_dir=self.project_dir,
            receipt=None,
            outline=None,
            bridge_review=None,
            bridge_beat_review=None,
            section_review=None,
        )
        status = GATE.inspect_outline_review_status(
            project="测试项目",
            project_dir=self.project_dir,
        )
        self.assertEqual("active", status["bridge_review"]["status"])
        self.assertGreater(status["bridge_review"]["pending_entries"], 0)
        suggestion = GATE.suggest_next_step(
            project="测试项目",
            project_dir=self.project_dir,
            receipt=None,
            outline=None,
            bridge_review=None,
            bridge_beat_review=None,
            section_review=None,
        )
        self.assertEqual("complete_manual_sidecars", suggestion["action"])

    def test_run_cycle_applies_consumes_and_seals(self) -> None:
        GATE.prepare_outline_review(
            project="测试项目",
            project_dir=self.project_dir,
            receipt=None,
            outline=None,
            bridge_review=None,
            bridge_beat_review=None,
            section_review=None,
        )
        self._fill_sidecars()
        with mock.patch.object(GATE.BRIDGE, "load_outline_validator") as loader:
            validator = mock.Mock()
            validator.validate_receipt.return_value = []
            loader.return_value = validator
            result = GATE.run_outline_review_cycle(
                project="测试项目",
                project_dir=self.project_dir,
                receipt=None,
                outline=None,
                bridge_review=None,
                bridge_beat_review=None,
                section_review=None,
            )
        self.assertEqual("apply_outline_review_sidecars", result["action"])
        self.assertEqual("passed", result["final_receipt_gate_status"])
        bridge_sidecar = json.loads(self.bridge_review.read_text(encoding="utf-8"))
        beat_sidecar = json.loads(self.bridge_beat_review.read_text(encoding="utf-8"))
        section_sidecar = json.loads(self.section_review.read_text(encoding="utf-8"))
        self.assertEqual("consumed", bridge_sidecar["status"])
        self.assertEqual("consumed", beat_sidecar["status"])
        self.assertEqual("consumed", section_sidecar["status"])

    def test_emit_shell_template_contains_high_level_commands(self) -> None:
        template = GATE.emit_shell_template(
            project="测试项目",
            project_dir=self.project_dir,
            receipt=None,
            outline=None,
            bridge_review=None,
            bridge_beat_review=None,
            section_review=None,
        )
        self.assertIn('batch_outline_review_cycle.py" prepare-outline-review', template)
        self.assertIn('batch_outline_review_cycle.py" status', template)
        self.assertIn('batch_outline_review_cycle.py" next-step', template)
        self.assertIn('batch_outline_review_cycle.py" run-outline-review-cycle', template)


if __name__ == "__main__":
    unittest.main()
