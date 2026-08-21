from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


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
                    {
                        "id": "T-1",
                        "region_id": "section:1",
                        "content": "甲推门",
                        "source_refs": {
                            "plot_beat_ids": ["P-001"],
                            "subflow_steps": ["SF-01#1"],
                            "layer_ids": ["SF-01-L01"],
                        },
                    },
                    {
                        "id": "T-2",
                        "region_id": "section:1",
                        "content": "乙拒绝",
                        "source_refs": {
                            "plot_beat_ids": ["P-002"],
                            "emotion_beat_ids": ["E-001"],
                            "subflow_steps": ["SF-01#2"],
                            "layer_ids": ["SF-01-L02"],
                        },
                    },
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
        source_lines = ["甲推门。", "乙拒绝。"]

        def source_hash(start: int, end: int) -> str:
            return MODULE.sha256_bytes("\n".join(source_lines[start - 1 : end]).encode("utf-8"))

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
                    "actor": "甲",
                    "action": "踹门" if changed_plot else "推门",
                    "object_or_receiver": "乙",
                    "pressure_or_trigger": "必须进入",
                    "control_change": "甲取得入口",
                    "information_change": "乙看见甲",
                    "consequence": "乙必须回应",
                    "bid_ids": ["BID-01"],
                    "source_range": {"start_line": 1, "end_line": 1},
                    "source_text_sha256": source_hash(1, 1),
                }
            ),
            hashed({
                "beat_id": "P-002", "actor": "乙", "action": "拒绝",
                "object_or_receiver": "甲", "pressure_or_trigger": "甲已进门",
                "control_change": "乙撤回许可", "information_change": "甲得知被拒",
                "consequence": "冲突落锤", "bid_ids": ["BID-01"],
                "source_range": {"start_line": 2, "end_line": 2},
                "source_text_sha256": source_hash(2, 2),
            }),
        ]
        emotion = [
            hashed({
                "beat_id": "E-001", "segment_id": "SEG-001", "role": "压迫",
                "content": "紧张", "trigger": "乙拒绝",
                "relationship_position_change": "乙夺回边界",
                "reader_effect": "预期冲突升级", "intensity": 7,
                "narrative_function": "落锤", "bid_ids": ["BID-01"],
                "source_range": {"start_line": 2, "end_line": 2},
                "source_text_sha256": source_hash(2, 2),
            })
        ]
        subflows = [
            hashed(
                {
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "name": "进门后被拒",
                    "required_sequence": ["甲进门", "乙拒绝"],
                    "scene_granularity": "两行连续现场",
                    "causal_preconditions": {"arrival_causes": ["甲必须进入"]},
                    "information_delay": "先进入后拒绝",
                    "control_changes": ["入口权转移"],
                    "emotion_sequence": ["压迫", "拒绝"],
                    "end_state": "冲突成立",
                    "source_range": {"start_line": 1, "end_line": 2},
                    "source_text_sha256": source_hash(1, 2),
                    "layer_ids": ["SF-01-L01", "SF-01-L02"],
                }
            )
        ]
        dimensions = {
            field: {"status": "active", "how": f"{field} 在本层起效"}
            for field in MODULE.SOURCE_MAP_VALIDATOR.DIMENSION_FIELDS
        }
        layers = [
            hashed({
                "layer_id": "SF-01-L01", "subflow_id": "SF-01",
                "source_range": {"start_line": 1, "end_line": 1},
                "source_text_sha256": source_hash(1, 1), "layer_modes": ["live_scene"],
                "layer_role": "甲进入", "entry_relation": "门外",
                "exit_relation": "乙看见甲", "narrative_distance": "近景",
                "dimension_realization": dimensions,
                "must_preserve_in_target": ["进入动作独立落地"],
            }),
            hashed({
                "layer_id": "SF-01-L02", "subflow_id": "SF-01",
                "source_range": {"start_line": 2, "end_line": 2},
                "source_text_sha256": source_hash(2, 2), "layer_modes": ["live_scene"],
                "layer_role": "乙拒绝", "entry_relation": "承接进门",
                "exit_relation": "冲突落锤", "narrative_distance": "近景",
                "dimension_realization": dimensions,
                "must_preserve_in_target": ["拒绝动作独立落地"],
            }),
        ]
        payload = {
            "schema_version": MODULE.SOURCE_MAP_VALIDATOR.SCHEMA_VERSION,
            "source_book": "样书",
            "source_root": str(self.project),
            "compiled_from": {
                "original": {
                    **dependency("样书.txt", "\n".join(source_lines) + "\n"),
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

    def confirm_node_reviews(self, audit: dict) -> dict:
        quotes = {"T-1": "甲推门。", "T-2": "乙拒绝。"}
        for review in audit["node_reviews"]:
            review.update(
                {
                    "realized": True,
                    "granularity_preserved": True,
                    "evidence_quotes": [quotes[review["target_node_id"]]],
                    "conclusion": "本节点动作、反应与控制变化均已独立落实。",
                }
            )
        return audit

    def confirm_plot_reviews(self, audit: dict) -> dict:
        quotes = {"P-001": "甲推门。", "P-002": "乙拒绝。"}
        for review in audit["plot_reviews"]:
            review.update(
                {
                    "function_preserved": True,
                    "action_preserved": True,
                    "control_change_preserved": True,
                    "information_change_preserved": True,
                    "consequence_preserved": True,
                    "evidence_quotes": [quotes[review["source_plot_id"]]],
                    "conclusion": "本拍动作、控制权、信息变化和后果均已换芯保真。",
                }
            )
        return audit

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
            "- 细拍拆分：细拍 <!-- source-map: P=P-001; E=E-001; SF=SF-01#1; L=SF-01-L01 -->\n"
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
        first_beat = catalog["regions"][0]["target_beats"][0]
        self.assertEqual("细拍", first_beat["evidence"])
        self.assertEqual(["P-001"], first_beat["source_refs"]["plot_beat_ids"])

    def test_explicit_source_refs_prefill_all_mapping_surfaces(self) -> None:
        target_input, nodes = MODULE.load_target_nodes(self.project, self.mind_map)
        payload = MODULE.create_target_map(
            self.project, self.source_path, self.source, target_input, nodes
        )

        self.assertEqual(
            ["T-1", "T-2"],
            [item["target_id"] for item in payload["mappings"]["plot_beats"]],
        )
        self.assertEqual("T-2", payload["mappings"]["emotion_beats"][0]["target_id"])
        self.assertEqual(
            [["T-1"], ["T-2"]],
            [
                step["target_node_ids"]
                for step in payload["mappings"]["subflows"][0]["performance_chain"]
            ],
        )
        self.assertEqual(
            [["T-1"], ["T-2"]],
            [item["target_node_ids"] for item in payload["mappings"]["layers"]],
        )
        self.assertTrue(payload["manual_confirmation"]["mapping_complete"])

    def test_preflight_rejects_missing_or_compressed_source_refs(self) -> None:
        _, nodes = MODULE.load_target_nodes(self.project, self.mind_map)
        nodes[0]["source_refs"]["plot_beat_ids"] = ["P-001", "P-002"]
        nodes[1]["source_refs"]["plot_beat_ids"] = []
        nodes[1]["source_refs"]["layer_ids"] = []

        errors = MODULE.validate_explicit_source_refs(nodes, self.source)

        self.assertTrue(any("同时承载多个 P 拍" in item for item in errors))
        self.assertTrue(any("漏掉来源层" in item for item in errors))

    def test_preflight_rejects_legacy_outline_without_source_map_comments(self) -> None:
        outline = self.project / "小节大纲.md"
        fields = (
            "- 主事件：事件\n"
            "- 子事件：子事件\n"
            "- 细拍拆分：没有声明的旧式细拍\n"
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
        _, nodes = MODULE.load_target_nodes(self.project, None)

        errors = MODULE.validate_explicit_source_refs(nodes, self.source)

        self.assertTrue(any("缺少 source-map" in item for item in errors))
        self.assertTrue(any("P 拍声明必须" in item for item in errors))

    def test_confirm_event_shells_does_not_change_explicit_mappings(self) -> None:
        target_input, nodes = MODULE.load_target_nodes(self.project, self.mind_map)
        payload = MODULE.create_target_map(
            self.project, self.source_path, self.source, target_input, nodes
        )
        before = json.loads(json.dumps(payload["mappings"]))
        MODULE.write_json(self.target_path, payload)

        updated, errors = MODULE.command_confirm_event_shells(
            SimpleNamespace(
                project_dir=str(self.project),
                input=str(self.target_path),
                dimensions="actor,setting,object",
                confirmation_note="已人工逐 P 拍确认人物、场域和核心物件均已完成换芯。",
            )
        )

        self.assertEqual([], errors)
        self.assertEqual(before, updated["mappings"])
        self.assertTrue(
            all(item["human_confirmed"] for item in updated["event_shell_replacements"])
        )

    def test_legacy_migration_materializes_existing_reviewed_bindings(self) -> None:
        target_input, nodes = MODULE.load_target_nodes(self.project, self.mind_map)
        payload = MODULE.create_target_map(
            self.project, self.source_path, self.source, target_input, nodes
        )
        refs = MODULE._source_refs_from_mappings(nodes, payload["mappings"])
        outline = self.project / "迁移大纲.md"
        outline.write_text(
            "- 细拍拆分：甲推门\n- 细拍拆分：乙拒绝\n",
            encoding="utf-8",
        )

        MODULE.migrate_outline_source_refs(outline, nodes, refs)
        migrated = outline.read_text(encoding="utf-8")

        self.assertIn(
            "<!-- source-map: P=P-001; SF=SF-01#1; L=SF-01-L01 -->",
            migrated,
        )
        self.assertIn(
            "<!-- source-map: P=P-002; E=E-001; SF=SF-01#2; L=SF-01-L02 -->",
            migrated,
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
                    {
                        "id": "T-9",
                        "region_id": "section:2",
                        "content": "甲推门",
                        "source_refs": {
                            "plot_beat_ids": ["P-001"],
                            "subflow_steps": ["SF-01#1"],
                            "layer_ids": ["SF-01-L01"],
                        },
                    },
                    {
                        "id": "T-2",
                        "region_id": "section:2",
                        "content": "乙拒绝",
                        "source_refs": {
                            "plot_beat_ids": ["P-002"],
                            "emotion_beat_ids": ["E-001"],
                            "subflow_steps": ["SF-01#2"],
                            "layer_ids": ["SF-01-L02"],
                        },
                    },
                ]
            },
        )
        changed_source = self.make_source(changed_plot=True)
        write_json(self.source_path, changed_source)
        target_input, nodes = MODULE.load_target_nodes(self.project, self.mind_map)
        rebound = MODULE.rebind_target_map(
            payload, self.source_path, changed_source, target_input, nodes
        )

        self.assertEqual("T-9", rebound["mappings"]["plot_beats"][0]["target_id"])
        self.assertEqual("T-2", rebound["mappings"]["plot_beats"][1]["target_id"])
        self.assertEqual(["T-9"], rebound["mappings"]["layers"][0]["target_node_ids"])
        self.assertIn(
            "P-001.event_shell_replacement",
            rebound["incremental_state"]["invalidated"],
        )
        self.assertNotIn(
            "P-002.event_shell_replacement",
            rebound["incremental_state"]["invalidated"],
        )
        self.assertTrue(
            all("target_id" not in item for item in rebound["event_shell_replacements"])
        )

    def test_rebind_uses_changed_explicit_refs_and_invalidates_only_changed_shell(self) -> None:
        payload = self.create_target()
        payload["event_shell_replacements"][0].update(
            {
                "dimensions_changed": ["actor", "setting", "object"],
                "adaptation_decision": "原目标已人工完成换壳。",
                "human_confirmed": True,
            }
        )
        write_json(
            self.mind_map,
            {
                "nodes": [
                    {
                        "id": "T-9",
                        "region_id": "section:2",
                        "content": "甲换门",
                        "source_refs": {
                            "plot_beat_ids": ["P-001"],
                            "subflow_steps": ["SF-01#1"],
                            "layer_ids": ["SF-01-L01"],
                        },
                    },
                    {
                        "id": "T-2",
                        "region_id": "section:2",
                        "content": "乙拒绝",
                        "source_refs": {
                            "plot_beat_ids": ["P-002"],
                            "emotion_beat_ids": ["E-001"],
                            "subflow_steps": ["SF-01#2"],
                            "layer_ids": ["SF-01-L02"],
                        },
                    },
                ]
            },
        )
        target_input, nodes = MODULE.load_target_nodes(self.project, self.mind_map)

        rebound = MODULE.rebind_target_map(
            payload, self.source_path, self.source, target_input, nodes
        )

        self.assertEqual("T-9", rebound["mappings"]["plot_beats"][0]["target_id"])
        self.assertEqual(["T-9"], rebound["mappings"]["layers"][0]["target_node_ids"])
        self.assertIn(
            "P-001.event_shell_replacement",
            rebound["incremental_state"]["invalidated"],
        )
        self.assertFalse(rebound["event_shell_replacements"][0]["human_confirmed"])

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
        self.confirm_node_reviews(audit)
        self.confirm_plot_reviews(audit)
        audit["gate_status"] = "passed"
        audit["content_sha256"] = MODULE.content_hash(audit)

        self.assertEqual([], MODULE.validate_audit(audit, self.project))
        serialized = json.dumps(audit, ensure_ascii=False)
        self.assertNotIn("dimension_realization", serialized)
        self.assertNotIn("required_sequence", serialized)
        self.assertLess(len(serialized.encode("utf-8")), 8_000)

    def test_audit_blocks_when_any_target_node_lacks_granularity_review(self) -> None:
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
        self.confirm_node_reviews(audit)
        audit["node_reviews"][1].update(
            {"realized": None, "granularity_preserved": None, "evidence_quotes": []}
        )
        audit["content_sha256"] = MODULE.content_hash(audit)

        errors = MODULE.validate_audit(audit, self.project, require_gate=False)

        self.assertTrue(any("T-2" in item and "granularity" in item for item in errors), errors)

    def test_audit_aliases_epilogue_to_last_numeric_section(self) -> None:
        regions = MODULE.audit_draft_regions(
            "# 测试项目\n1.\n第一节。\n2.\n最后一节含尾声。\n"
        )

        self.assertEqual("最后一节含尾声。", regions["section:2"])
        self.assertEqual(regions["section:2"], regions["epilogue"])

    def test_audit_confirm_requires_and_applies_all_manual_reviews(self) -> None:
        target = self.create_target()
        draft = self.project / "正文.md"
        draft.write_text("# 测试项目\n1.\n甲推门。乙拒绝。\n", encoding="utf-8")
        audit = MODULE.create_audit(self.project, self.target_path, target)
        audit_path = self.assets / "正文覆盖回执.json"
        MODULE.write_json(audit_path, audit)
        reviews = {
            "SF-01-L01": {
                "evidence_quotes": ["甲推门。"],
                "conclusion": "现场进入动作及叙述距离均按第一层顺序落实。",
            },
            "SF-01-L02": {
                "evidence_quotes": ["乙拒绝。"],
                "conclusion": "拒绝动作及冷收关系均按第二层顺序落实。",
            },
        }
        node_reviews = {
            "T-1": {
                "evidence_quotes": ["甲推门。"],
                "conclusion": "进入动作与现场控制变化已经独立落实。",
            },
            "T-2": {
                "evidence_quotes": ["乙拒绝。"],
                "conclusion": "拒绝动作与关系落锤已经独立落实。",
            },
        }

        confirmed, errors = MODULE.command_audit_confirm(
            SimpleNamespace(
                project_dir=str(self.project),
                input=str(audit_path),
                reviews_json=json.dumps(reviews, ensure_ascii=False),
                node_reviews_json=json.dumps(node_reviews, ensure_ascii=False),
            )
        )

        self.assertEqual([], errors)
        self.assertTrue(
            all(item["realized"] is True for item in confirmed["layer_reviews"])
        )
        self.confirm_plot_reviews(confirmed)
        confirmed["content_sha256"] = MODULE.content_hash(confirmed)
        self.assertEqual([], MODULE.validate_audit(confirmed, self.project, require_gate=False))

    def test_audit_confirm_nodes_applies_explicit_subset_only(self) -> None:
        target = self.create_target()
        draft = self.project / "正文.md"
        draft.write_text("# 测试项目\n1.\n甲推门。乙拒绝。\n", encoding="utf-8")
        audit = MODULE.create_audit(self.project, self.target_path, target)
        audit_path = self.assets / "正文覆盖回执.json"
        MODULE.write_json(audit_path, audit)

        confirmed, errors = MODULE.command_audit_confirm_nodes(
            SimpleNamespace(
                project_dir=str(self.project),
                input=str(audit_path),
                reviews_json=json.dumps(
                    {
                        "T-1": {
                            "evidence_quotes": ["甲推门。"],
                            "conclusion": "进入动作与现场控制变化已经独立落实。",
                        }
                    },
                    ensure_ascii=False,
                ),
            )
        )

        self.assertEqual([], errors)
        self.assertTrue(confirmed["node_reviews"][0]["realized"])
        self.assertIsNone(confirmed["node_reviews"][1]["realized"])

    def test_audit_confirm_layers_applies_explicit_subset_only(self) -> None:
        target = self.create_target()
        draft = self.project / "正文.md"
        draft.write_text("# 测试项目\n1.\n甲推门。乙拒绝。\n", encoding="utf-8")
        audit = MODULE.create_audit(self.project, self.target_path, target)
        audit_path = self.assets / "正文覆盖回执.json"
        MODULE.write_json(audit_path, audit)

        confirmed, errors = MODULE.command_audit_confirm_layers(
            SimpleNamespace(
                project_dir=str(self.project),
                input=str(audit_path),
                reviews_json=json.dumps(
                    {
                        "SF-01-L01": {
                            "evidence_quotes": ["甲推门。"],
                            "conclusion": "进入层的现场距离与动作顺序已经落实。",
                        }
                    },
                    ensure_ascii=False,
                ),
            )
        )

        self.assertEqual([], errors)
        self.assertTrue(confirmed["layer_reviews"][0]["realized"])
        self.assertIsNone(confirmed["layer_reviews"][1]["realized"])

    def test_audit_confirm_plots_applies_explicit_subset_only(self) -> None:
        target = self.create_target()
        draft = self.project / "正文.md"
        draft.write_text("# 测试项目\n1.\n甲推门。乙拒绝。\n", encoding="utf-8")
        audit = MODULE.create_audit(self.project, self.target_path, target)
        audit_path = self.assets / "正文覆盖回执.json"
        MODULE.write_json(audit_path, audit)

        confirmed, errors = MODULE.command_audit_confirm_plots(
            SimpleNamespace(
                project_dir=str(self.project),
                input=str(audit_path),
                reviews_json=json.dumps(
                    {
                        "P-001": {
                            "evidence_quotes": ["甲推门。"],
                            "conclusion": "推门动作、入口控制、看见信息和冲突后果均保真。",
                        }
                    },
                    ensure_ascii=False,
                ),
            )
        )

        self.assertEqual([], errors)
        self.assertTrue(confirmed["plot_reviews"][0]["function_preserved"])
        self.assertIsNone(confirmed["plot_reviews"][1]["function_preserved"])

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
