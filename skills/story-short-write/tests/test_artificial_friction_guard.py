from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "run_full_ai_audit.py"
RULEBOOK_PATH = SKILL_ROOT / "references" / "governance" / "audit-rulebook.json"

SPEC = importlib.util.spec_from_file_location("run_full_ai_audit", SCRIPT_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ArtificialFrictionGuardTest(unittest.TestCase):
    def test_revision_subcauses_do_not_prescribe_random_friction(self) -> None:
        item = {
            "title": "流程件和证据件摆放过整齐",
            "focus_layer": "scene_order",
            "why_it_hits_audit": "流程和责任被一次性讲完。",
            "evidence": ["测试证据"],
        }
        combined = {
            "light_report": {"line_hit_types": {}},
            "style_audits": {},
            "paragraph_scores": [],
        }

        subcauses = AUDIT.build_subcauses(item, combined)
        fixes = "\n".join(entry["fix"] for entry in subcauses)

        self.assertIn("人物自保", fixes)
        self.assertIn("禁止", fixes)
        self.assertNotIn("中间插入翻找、打断、质疑和迟滞", fixes)
        self.assertNotIn("有人拦、有人催、有人插话", fixes)

    def test_result_broadcast_rule_rejects_artificial_friction(self) -> None:
        rulebook = json.loads(RULEBOOK_PATH.read_text(encoding="utf-8"))
        rules = [
            rule
            for section in rulebook["sections"]
            for rule in section["rules"]
            if rule["id"] == "result_broadcast_chain"
        ]

        self.assertEqual(1, len(rules))
        fixes = "\n".join(rules[0]["fix_methods"])
        self.assertIn("人物争夺定义权", fixes)
        self.assertIn("禁止用卡顿、误触、掉落、摔倒", fixes)


if __name__ == "__main__":
    unittest.main()
