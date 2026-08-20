from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "manage_target_prose_map.py"
SPEC = importlib.util.spec_from_file_location("test_target_prose_map_module", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hashed(value: dict) -> dict:
    result = dict(value)
    result["content_sha256"] = MODULE.canonical_sha256(result)
    return result


class TargetProseMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "测试项目"
        self.assets = self.project / "写作资产"
        write_json(
            self.assets / "项目写作配置.json",
            {"project_name": "测试项目", "primary": {}},
        )
        self.mind_map = self.project / "用户脑图.json"
        write_json(
            self.mind_map,
            {
                "nodes": [
                    {"id": "T-1", "region_id": "section:1", "content": "甲推门"},
                    {"id": "T-2", "region_id": "section:1", "content": "乙拒绝"},
                ]
            },
        )
        self.source_path = self.project / "来源成文脑图.json"
        self.source = self.make_source()
        write_json(self.source_path, self.source)
        self.target_path = self.assets / "目标成文脑图.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_source(self, changed_plot: bool = False) -> dict:
        inputs = self.project / "source-inputs"
        inputs.mkdir(parents=True, exist_ok=True)

        def dependency(filename: str, content: str) -> dict:
            path = inputs / filename
            path.write_text(content, encoding="utf-8")
            return {
                "path": str(path.resolve()),
                "relative_path": str(path.relative_to(self.project)),
                "sha256": MODULE.file_sha256(path),
            }

        plot = [
            hashed(
                {
                    "beat_id": "P-001",
                    "action": "踹门" if changed_plot else "推门",
                    "bid_ids": ["BID-01"],
                }
            ),
            hashed({"beat_id": "P-002", "action": "拒绝", "bid_ids": ["BID-01"]}),
        ]
        emotion = [
            hashed({"beat_id": "E-001", "content": "紧张", "bid_ids": ["BID-01"]})
        ]
        subflows = [
            hashed(
                {
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "required_sequence": ["甲进门", "乙拒绝"],
                    "layer_ids": ["SF-01-L01", "SF-01-L02"],
                }
            )
        ]
        layers = [
            hashed({"layer_id": "SF-01-L01", "subflow_id": "SF-01"}),
            hashed({"layer_id": "SF-01-L02", "subflow_id": "SF-01"}),
        ]
        payload = {
            "schema_version": MODULE.SOURCE_MAP_VALIDATOR.SCHEMA_VERSION,
            "source_book": "样书",
            "source_root": str(self.project),
            "compiled_from": {
                "original": {
                    **dependency("样书.txt", "甲推门。\n乙拒绝。\n"),
                    "line_count": 2,
                },
                "plot_ledger": dependency(
                    "全文情节微拍总账.json",
                    json.dumps(
                        {"changed_plot": changed_plot}, ensure_ascii=False
                    ),
                ),
                "emotion_ledger": dependency("全文情绪颗粒总账.json", "{}"),
                "subflow_catalog": dependency("子流程索引.jsonl", "{}\n"),
                "layer_catalog": dependency("子流程层次索引.jsonl", "{}\n"),
                "profile": dependency("book.profile.json", "{}"),
            },
            "order": {
                "bid_ids": ["BID-01"],
                "plot_beat_ids": ["P-001", "P-002"],
                "emotion_beat_ids": ["E-001"],
                "subflow_ids": ["SF-01"],
                "layer_ids": ["SF-01-L01", "SF-01-L02"],
            },
            "bridges": [
                {
                    "bid_id": "BID-01",
                    "name": "进门施压",
                    "plot_beat_ids": ["P-001", "P-002"],
                    "emotion_beat_ids": ["E-001"],
                    "subflow_ids": ["SF-01"],
                }
            ],
            "plot_beats": plot,
            "emotion_beats": emotion,
            "subflows": subflows,
            "layers": layers,
        }
        payload["content_sha256"] = MODULE.content_hash(payload)
        return payload

    def create_target(self) -> dict:
        target_input, nodes = MODULE.load_target_nodes(self.project, self.mind_map)
        payload = MODULE.create_target_map(
            self.project, self.source_path, self.source, target_input, nodes
        )
        mappings = payload["mappings"]
        mappings["plot_beats"][0]["target_id"] = "T-1"
        mappings["plot_beats"][1]["target_id"] = "T-2"
        mappings["emotion_beats"][0]["target_id"] = "T-2"
        mappings["subflows"][0]["performance_chain"][0]["target_node_ids"] = ["T-1"]
        mappings["subflows"][0]["performance_chain"][1]["target_node_ids"] = ["T-2"]
        mappings["layers"][0]["target_node_ids"] = ["T-1"]
        mappings["layers"][1]["target_node_ids"] = ["T-2"]
        for replacement in payload["event_shell_replacements"]:
            replacement.update(
                {
                    "dimensions_changed": ["actor", "setting", "object"],
                    "adaptation_decision": "已换人物、场域与承压物。",
                    "human_confirmed": True,
                }
            )
        payload["manual_confirmation"] = {
            "mapping_complete": True,
            "event_shell_replacements_confirmed": True,
            "note": "已逐项确认本书目标节点与换壳边界。",
        }
        payload["gate_status"] = "passed"
        payload["content_sha256"] = MODULE.content_hash(payload)
        write_json(self.target_path, payload)
        return payload

    def test_target_map_has_one_maintained_mapping_surface(self) -> None:
        payload = self.create_target()
        self.assertEqual([], MODULE.validate_target_map(payload))
        self.assertEqual(
            ["P-001", "P-002"],
            [item["source_id"] for item in payload["mappings"]["plot_beats"]],
        )
        self.assertEqual(
            ["SF-01-L01", "SF-01-L02"],
            [item["source_id"] for item in payload["mappings"]["layers"]],
        )
        self.assertNotIn("target_id", payload["event_shell_replacements"][0])
        self.assertNotIn("target_node_ids", payload["mappings"]["subflows"][0])

    def test_outline_parser_is_owned_by_brain_map_script(self) -> None:
        outline = self.project / "小节大纲.md"
        fields = (
            "- 主事件：事件\n"
            "- 子事件：子事件\n"
            "- 细拍拆分：细拍\n"
            "- 情绪：压迫\n"
            "- 读者新获知什么：新信息\n"
            "- 钩子：钩子\n"
            "- 伏笔/物件：物件\n"
            "- 动静：动\n"
            "- 对话密度：中\n"
            "- 目标字数：100-200字\n"
            "- 场面单元：现场\n"
        )
        outline.write_text(
            f"## 导语\n{fields}\n## 1.\n{fields}\n## 尾声\n{fields}",
            encoding="utf-8",
        )

        catalog = MODULE.parse_outline(outline)

        self.assertEqual([], catalog["errors"])
        self.assertEqual(
            ["opening", "section:1", "epilogue"],
            [item["region_id"] for item in catalog["regions"]],
        )

    def test_reversed_plot_or_layer_mapping_is_blocked(self) -> None:
        payload = self.create_target()
        payload["mappings"]["plot_beats"][0]["target_id"] = "T-2"
        payload["mappings"]["plot_beats"][1]["target_id"] = "T-1"
        payload["mappings"]["layers"][0]["target_node_ids"] = ["T-2"]
        payload["mappings"]["layers"][1]["target_node_ids"] = ["T-1"]
        payload["content_sha256"] = MODULE.content_hash(payload)

        errors = MODULE.validate_target_map(payload)

        self.assertTrue(any("plot_beats" in item and "原序" in item for item in errors))
        self.assertTrue(any("layers" in item and "倒序" in item for item in errors))

    def test_rebind_preserves_unchanged_items_and_invalidates_changed_source(self) -> None:
        payload = self.create_target()
        write_json(
            self.mind_map,
            {
                "nodes": [
                    {"id": "T-9", "region_id": "section:2", "content": "甲推门"},
                    {"id": "T-2", "region_id": "section:2", "content": "乙拒绝"},
                ]
            },
        )
        changed_source = self.make_source(changed_plot=True)
        write_json(self.source_path, changed_source)
        target_input, nodes = MODULE.load_target_nodes(self.project, self.mind_map)
        rebound = MODULE.rebind_target_map(
            payload, self.source_path, changed_source, target_input, nodes
        )

        self.assertEqual("", rebound["mappings"]["plot_beats"][0]["target_id"])
        self.assertEqual("T-2", rebound["mappings"]["plot_beats"][1]["target_id"])
        self.assertEqual(["T-9"], rebound["mappings"]["layers"][0]["target_node_ids"])
        self.assertIn("P-001", rebound["incremental_state"]["invalidated"])
        self.assertNotIn("P-002", rebound["incremental_state"]["invalidated"])
        self.assertTrue(
            all("target_id" not in item for item in rebound["event_shell_replacements"])
        )

    def test_stale_source_dependency_blocks_target_map(self) -> None:
        payload = self.create_target()
        plot_ledger = Path(
            self.source["compiled_from"]["plot_ledger"]["path"]
        )
        plot_ledger.write_text('{"changed_after_finalize": true}', encoding="utf-8")

        errors = MODULE.validate_target_map(payload)

        self.assertTrue(
            any("compiled_from.plot_ledger SHA 已失效" in item for item in errors),
            errors,
        )

    def test_compact_audit_keeps_only_quotes_and_manual_layer_conclusions(self) -> None:
        target = self.create_target()
        draft = self.project / "正文.md"
        draft.write_text("# 测试项目\n1.\n甲推门。乙拒绝。\n", encoding="utf-8")
        audit = MODULE.create_audit(self.project, self.target_path, target)
        for index, review in enumerate(audit["layer_reviews"]):
            review.update(
                {
                    "realized": True,
                    "topology_preserved": True,
                    "evidence_quotes": ["甲推门。" if index == 0 else "乙拒绝。"],
                    "conclusion": "动作、层型和进出关系均已在本段按原顺序落实。",
                }
            )
        audit["gate_status"] = "passed"
        audit["content_sha256"] = MODULE.content_hash(audit)

        self.assertEqual([], MODULE.validate_audit(audit, self.project))
        serialized = json.dumps(audit, ensure_ascii=False)
        self.assertNotIn("dimension_realization", serialized)
        self.assertNotIn("required_sequence", serialized)
        self.assertLess(len(serialized.encode("utf-8")), 8_000)

    def test_audit_refresh_preserves_unresolved_exceptions(self) -> None:
        target = self.create_target()
        draft = self.project / "正文.md"
        draft.write_text("# 测试项目\n1.\n甲推门。乙拒绝。\n", encoding="utf-8")
        existing = MODULE.create_audit(self.project, self.target_path, target)
        existing["exceptions"] = [
            {
                "type": "layer_order_mismatch",
                "source_layer_id": "SF-01-L02",
                "note": "第二层在正文中提前出现，尚未修复。",
            }
        ]

        refreshed = MODULE.create_audit(
            self.project, self.target_path, target, existing=existing
        )

        self.assertEqual(existing["exceptions"], refreshed["exceptions"])
        self.assertEqual("pending", refreshed["gate_status"])


if __name__ == "__main__":
    unittest.main()
