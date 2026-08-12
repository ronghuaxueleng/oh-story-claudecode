from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_semantic_beat_mapping.py"


class SemanticBeatMappingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.outline = self.root / "小节大纲.md"
        self.source = self.root / "主体原文.txt"
        self.emotion_ledger = self.root / "全文情绪颗粒总账.json"
        self.plot_ledger = self.root / "全文情节微拍总账.json"
        self.mapping = self.root / "逐拍语义映射.json"
        self.emotion_evidence = "沈知夏听见顾临舟先问别人冷不冷，便把自己的围巾收回包里。"
        self.plot_evidence = "顾临舟把唯一的门卡交给林晚，沈知夏当场失去进入权。"
        self.outline.write_text(
            f"## 1. 起事\n\n{self.emotion_evidence}\n\n{self.plot_evidence}\n",
            encoding="utf-8",
        )
        self.source.write_text("来源正文。", encoding="utf-8")
        self.emotion_ledger.write_text(
            json.dumps({"beats": [{"beat_id": "E-X", "role": "期待反落", "intensity": 8}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.plot_ledger.write_text(
            json.dumps({"beats": [{"beat_id": "P-X"}]}, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def binding(path: Path) -> dict[str, str]:
        return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def payload(self) -> dict:
        return {
            "status": "approved",
            "bindings": {
                "outline": self.binding(self.outline),
                "primary_source": self.binding(self.source),
                "primary_emotion_ledger": self.binding(self.emotion_ledger),
                "primary_plot_ledger": self.binding(self.plot_ledger),
            },
            "emotions": [{
                "source_beat_id": "E-X", "target_beat_id": "TE-X", "role": "期待反落", "intensity": 8,
                "target_outline_region": "section:1", "trigger": "顾临舟先关心林晚的冷暖",
                "relationship_position_change": "沈知夏从默认伴侣退到无人过问的位置",
                "reader_effect": "读者看见她的期待被一个问句当场截断",
                "target_story_adaptation": "沈知夏被代词指向时，围巾动作把她的关系掉位落实到现场。",
                "hurt_object": "沈知夏", "expectation_before": "仍期待顾临舟先看见自己的处境",
                "expectation_after": "确认顾临舟首先照顾的是林晚",
                "action_impulse_before": "准备把围巾递给顾临舟并等他回应",
                "action_impulse_after": "收回围巾并停止向顾临舟求证",
                "equivalence_reason": "关心对象换位造成同级期待落空和行动撤回",
                "target_evidence_coverage_review": "证据同时覆盖顾临舟先问林晚这一触发、沈知夏收回围巾的动作以及伴侣位置下降的后果。",
                "evidence": self.emotion_evidence,
            }],
            "plots": [{
                "source_path": str(self.source.resolve()), "source_beat_id": "P-X", "target_beat_id": "TP-X",
                "actor": "顾临舟", "actor_evidence": "顾临舟", "object_or_receiver": "林晚与门卡",
                "pressure_or_trigger": "林晚声称自己需要随时进入住所",
                "action": "顾临舟把唯一门卡交给林晚",
                "control_change": "住所进入权从沈知夏转到林晚",
                "information_change": "沈知夏确认这不是临时借用而是权限换主",
                "consequence": "沈知夏当场失去进入共同住所的权利",
                "adaptation_equivalence": "用门卡换主保留来源拍的控制权转移和现实后果",
                "evidence": self.plot_evidence,
            }],
        }

    def run_gate(self, payload: dict) -> subprocess.CompletedProcess[str]:
        self.mapping.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), "validate", "--mapping", str(self.mapping),
             "--outline", str(self.outline), "--primary-emotion-ledger", str(self.emotion_ledger),
             "--primary-plot-ledger", str(self.plot_ledger), "--primary-source", str(self.source)],
            check=False, capture_output=True, text=True,
        )

    def test_unseen_character_names_are_not_hard_coded(self) -> None:
        result = self.run_gate(self.payload())
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("semantic_beat_mapping: passed", result.stdout)

    def test_sentence_like_actor_is_blocked(self) -> None:
        payload = self.payload()
        payload["plots"][0]["actor"] = "顾临舟把唯一门卡交给林晚"
        result = self.run_gate(payload)
        self.assertEqual(2, result.returncode)
        self.assertIn("不能把时间、地点或整句事件当施事者", result.stdout)

    def test_sentence_like_hurt_object_is_blocked(self) -> None:
        payload = self.payload()
        payload["emotions"][0]["hurt_object"] = "沈知夏听见他先关心别人以后收回围巾"
        result = self.run_gate(payload)
        self.assertEqual(2, result.returncode)
        self.assertIn("不能是整句事件", result.stdout)


if __name__ == "__main__":
    unittest.main()
