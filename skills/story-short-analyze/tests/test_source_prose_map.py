from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compile_source_prose_map.py"
SPEC = importlib.util.spec_from_file_location("test_source_prose_map_module", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class SourceProseMapTest(unittest.TestCase):
    def build_fixture(self, root: Path) -> None:
        original = root / "原文" / "样书.txt"
        original.parent.mkdir(parents=True)
        original.write_text("开场。\n动作。\n落锤。\n", encoding="utf-8")
        assets = root / "写作资产"
        write_json(
            assets / "全文情节微拍总账.json",
            {
                "beats": [
                    {
                        "beat_id": "P-001",
                        "actor": "甲",
                        "action": "推门",
                        "object_or_receiver": "乙",
                        "pressure_or_trigger": "误会",
                        "control_change": "甲进场",
                        "information_change": "乙看见甲",
                        "consequence": "冲突开始",
                        "source_range": {"start_line": 1, "end_line": 2},
                        "source_evidence": "开场。",
                        "bid_ids": ["BID-01"],
                    }
                ]
            },
        )
        write_json(
            assets / "全文情绪颗粒总账.json",
            {
                "beats": [
                    {
                        "beat_id": "E-001",
                        "segment_id": "SEG-001",
                        "start_line": 1,
                        "end_line": 3,
                        "role": "压迫",
                        "content": "甲逼近乙",
                        "trigger": "推门",
                        "relationship_position_change": "甲占上风",
                        "reader_effect": "紧张",
                        "intensity": 7,
                        "narrative_function": "pressure",
                        "source_evidence": ["动作。"],
                        "bid_ids": ["BID-01"],
                    }
                ]
            },
        )
        subflow = {
            "subflow_id": "SF-01",
            "parent_bridge_id": "BID-01",
            "name": "进门施压",
            "source_range": "L1-L3",
            "required_sequence": ["推门", "逼近", "落锤"],
            "scene_granularity": "三行完成",
            "causal_preconditions": {"arrival_causes": ["误会"]},
            "information_delay": "先给动作，后给落锤",
            "control_changes": ["甲进入现场"],
            "emotion_sequence": ["压迫", "失控"],
            "end_state": "冲突开始",
            "source_excerpt": "禁止复制到脑图的大段原文",
        }
        (assets / "子流程索引.jsonl").write_text(
            json.dumps(subflow, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        layer = {
            "record_type": "source_layer",
            "subflow_id": "SF-01",
            "layer": {
                "layer_id": "SF-01-L01",
                "source_range": "L1-L3",
                "source_text": "禁止复制到脑图的层原文",
                "layer_modes": ["live_scene"],
                "layer_role": "动作后落锤",
                "entry_relation": "从门外进入",
                "exit_relation": "以判断句退出",
                "narrative_distance": "近景",
                "dimension_realization": {
                    field: {
                        "status": "active",
                        "how": f"{field} 的实现",
                        "source_evidence": ["动作。"],
                    }
                    for field in MODULE.DIMENSION_FIELDS
                },
                "must_preserve_in_target": ["动作在判断之前"],
            },
        }
        (assets / "子流程层次索引.jsonl").write_text(
            json.dumps(layer, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        write_json(
            root / "book.profile.json",
            {"bridge_rules": [{"id": "BID-01", "bridge": "BID-01 进门施压"}]},
        )

    def test_compiles_ordered_map_without_copying_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "样书"
            self.build_fixture(root)
            payload = MODULE.compile_source_map(root)
            validation_errors = MODULE.validate_source_map(payload)

        self.assertEqual(MODULE.SCHEMA_VERSION, payload["schema_version"])
        self.assertEqual(["P-001"], payload["order"]["plot_beat_ids"])
        self.assertEqual(["E-001"], payload["order"]["emotion_beat_ids"])
        self.assertEqual(["SF-01-L01"], payload["order"]["layer_ids"])
        self.assertNotIn("source_excerpt", payload["subflows"][0])
        self.assertNotIn("source_text", payload["layers"][0])
        self.assertNotIn(
            "source_evidence",
            payload["layers"][0]["dimension_realization"][
                "narrative_voice_and_attitude"
            ],
        )
        self.assertEqual([], validation_errors)

    def test_item_hash_supports_incremental_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "样书"
            self.build_fixture(root)
            before = MODULE.compile_source_map(root)
            plot_path = root / "写作资产" / "全文情节微拍总账.json"
            plot = json.loads(plot_path.read_text(encoding="utf-8"))
            plot["beats"][0]["action"] = "踹门"
            write_json(plot_path, plot)
            after = MODULE.compile_source_map(root)

        self.assertNotEqual(
            before["plot_beats"][0]["content_sha256"],
            after["plot_beats"][0]["content_sha256"],
        )
        self.assertEqual(
            before["subflows"][0]["source_text_sha256"],
            after["subflows"][0]["source_text_sha256"],
        )

    def test_appended_ledger_bid_extends_profile_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "样书"
            self.build_fixture(root)
            plot_path = root / "写作资产" / "全文情节微拍总账.json"
            plot = json.loads(plot_path.read_text(encoding="utf-8"))
            appended = dict(plot["beats"][0])
            appended.update(
                {
                    "beat_id": "P-002",
                    "action": "落锤",
                    "source_range": {"start_line": 3, "end_line": 3},
                    "bid_ids": ["BID-02"],
                }
            )
            plot["beats"].append(appended)
            write_json(plot_path, plot)

            payload = MODULE.compile_source_map(root)

        self.assertEqual(["BID-01", "BID-02"], payload["order"]["bid_ids"])
        self.assertEqual("BID-02", payload["bridges"][1]["name"])

    def test_tampered_bridge_references_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "样书"
            self.build_fixture(root)
            payload = MODULE.compile_source_map(root)
            payload["bridges"][0]["plot_beat_ids"] = []
            payload["content_sha256"] = MODULE.canonical_sha256(
                {
                    key: value
                    for key, value in payload.items()
                    if key != "content_sha256"
                }
            )

            errors = MODULE.validate_source_map(payload)

        self.assertTrue(
            any("BID-01.plot_beat_ids" in item for item in errors), errors
        )

    def test_tampered_subflow_layer_directory_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "样书"
            self.build_fixture(root)
            payload = MODULE.compile_source_map(root)
            payload["subflows"][0]["layer_ids"] = []
            payload["subflows"][0]["content_sha256"] = MODULE.canonical_sha256(
                {
                    key: value
                    for key, value in payload["subflows"][0].items()
                    if key != "content_sha256"
                }
            )
            payload["content_sha256"] = MODULE.canonical_sha256(
                {
                    key: value
                    for key, value in payload.items()
                    if key != "content_sha256"
                }
            )

            errors = MODULE.validate_source_map(payload)

        self.assertTrue(any("SF-01.layer_ids" in item for item in errors), errors)

    def test_subflow_parent_bridge_must_match_overlapping_beats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "样书"
            self.build_fixture(root)
            payload = MODULE.compile_source_map(root)
            payload["subflows"][0]["parent_bridge_id"] = "BID-02"
            payload["subflows"][0]["content_sha256"] = MODULE.canonical_sha256(
                {
                    key: value
                    for key, value in payload["subflows"][0].items()
                    if key != "content_sha256"
                }
            )
            payload["content_sha256"] = MODULE.canonical_sha256(
                {key: value for key, value in payload.items() if key != "content_sha256"}
            )
            errors = MODULE.validate_source_map(payload)

        self.assertTrue(any("parent_bridge_id" in item for item in errors), errors)

    def test_missing_compiled_dependency_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "样书"
            self.build_fixture(root)
            payload = MODULE.compile_source_map(root)
            del payload["compiled_from"]["plot_ledger"]
            payload["content_sha256"] = MODULE.canonical_sha256(
                {
                    key: value
                    for key, value in payload.items()
                    if key != "content_sha256"
                }
            )

            errors = MODULE.validate_source_map(payload)

        self.assertTrue(any("compiled_from 缺少依赖绑定" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
