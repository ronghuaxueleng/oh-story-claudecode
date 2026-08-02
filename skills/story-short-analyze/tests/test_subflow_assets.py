from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "short_analyze_validator",
    ROOT / "scripts" / "validate_short_analyze_outputs.py",
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)

LIBRARY_SPEC = importlib.util.spec_from_file_location(
    "subflow_library",
    ROOT / "scripts" / "build_subflow_library.py",
)
assert LIBRARY_SPEC and LIBRARY_SPEC.loader
LIBRARY = importlib.util.module_from_spec(LIBRARY_SPEC)
LIBRARY_SPEC.loader.exec_module(LIBRARY)


def subflow(subflow_id: str = "SF-01", bridge_id: str = "BID-01") -> dict:
    return {
        "subflow_id": subflow_id,
        "source_book": "测试书",
        "parent_bridge_id": bridge_id,
        "name": "先抢入口再迫使让位",
        "source_excerpt": "对手先伸手。\n主角挡住。\n关系人表态。\n主角才松手。",
        "source_range": "L1-L4",
        "function_tags": ["公开失位"],
        "entry_state": "主角仍有现场决定权。",
        "required_sequence": ["对手先抢入口", "关系人随后要求主角让位"],
        "scene_granularity": "对手先伸手，主角挡住，关系人表态后主角才松手。",
        "causal_preconditions": {
            "arrival_causes": ["对手先到入口，主角随后赶到阻拦。"],
            "knowledge_boundaries": ["主角只知道入口被抢，不知道关系人会公开偏护。"],
            "object_lifecycle": ["钥匙先在主角手里，表态后才被交出。"],
            "institutional_constraints": ["无外部制度依赖，现场权限只由钥匙控制。"],
            "obvious_alternative_blockers": ["主角不能直接离场，因为入口仍由她负责。"],
            "exit_cause": "关系人公开表态后，主角失去阻拦资格并交出钥匙。",
            "source_evidence": ["对手先伸手。", "主角才松手。"],
        },
        "information_delay": "本场只漏出偏护，完整责任压后。",
        "control_changes": ["入口控制权从主角转给对手"],
        "emotion_sequence": ["警觉", "受辱", "余痛"],
        "end_state": "主角失去默认进入权。",
        "embeddable_after": [],
        "incompatible_with": [],
        "source_evidence": ["对手先伸手。", "主角才松手。"],
        "source_style_granularity": {
            field: {
                "analysis": f"{field} 的逐场分析",
                "source_evidence": ["对手先伸手。", "主角才松手。"],
            }
            for field in VALIDATOR.SUBFLOW_STYLE_GRANULARITY_FIELDS
        },
    }


class SubflowAssetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir(parents=True)
        (asset_dir / "桥段施工卡.md").write_text(
            "## BID-01 公开失位\n",
            encoding="utf-8",
        )
        (asset_dir / "子流程施工卡.md").write_text(
            "## SF-01 先抢入口再迫使让位\n",
            encoding="utf-8",
        )
        self.index = asset_dir / "子流程索引.jsonl"
        self.original = "对手先伸手。\n主角挡住。\n关系人表态。\n主角才松手。"
        style_quotes = {
            "narrative_voice_and_attitude": ["对手先伸手。", "主角挡住。"],
            "sentence_relation_and_rhythm": ["主角挡住。", "关系人表态。"],
            "paragraph_breath_and_cut_points": ["关系人表态。", "主角才松手。"],
            "dialogue_misfire_or_avoidance": ["对手先伸手。", "主角才松手。"],
            "action_perception_emotion_weave": ["对手先伸手。", "关系人表态。"],
            "narrator_interjection_and_roughness": ["主角挡住。", "主角才松手。"],
        }
        self.base_subflow = subflow()
        for field, quotes in style_quotes.items():
            self.base_subflow["source_style_granularity"][field]["source_evidence"] = quotes

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_entries(self, entries: list[dict]) -> None:
        self.index.write_text(
            "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
            encoding="utf-8",
        )

    def test_complete_subflow_assets_pass(self) -> None:
        self.write_entries([self.base_subflow])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertEqual([], errors)

    def test_missing_field_blocks(self) -> None:
        entry = subflow()
        entry = copy.deepcopy(self.base_subflow)
        del entry["end_state"]
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("缺少字段" in error for error in errors))

    def test_uncovered_bridge_blocks(self) -> None:
        card = self.root / "写作资产" / "桥段施工卡.md"
        card.write_text("## BID-01 公开失位\n\n## BID-02 私域换主\n", encoding="utf-8")
        self.write_entries([copy.deepcopy(self.base_subflow)])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("未覆盖全部父 BID" in error for error in errors))

    def test_fake_source_evidence_blocks(self) -> None:
        entry = copy.deepcopy(self.base_subflow)
        entry["source_evidence"] = ["对手先伸手", "并不存在的原句"]
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("不在原文中" in error for error in errors))

    def test_missing_causal_precondition_blocks(self) -> None:
        entry = copy.deepcopy(self.base_subflow)
        entry["causal_preconditions"]["arrival_causes"] = []
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("arrival_causes" in error for error in errors))

    def test_fake_causal_evidence_blocks(self) -> None:
        entry = copy.deepcopy(self.base_subflow)
        entry["causal_preconditions"]["source_evidence"][1] = "并不存在的因果证据"
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("causal_preconditions.source_evidence" in error for error in errors))

    def test_missing_per_subflow_style_blocks(self) -> None:
        entry = copy.deepcopy(self.base_subflow)
        del entry["source_style_granularity"]
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("source_style_granularity" in error for error in errors))

    def test_style_evidence_outside_exact_subflow_range_blocks(self) -> None:
        entry = copy.deepcopy(self.base_subflow)
        entry["source_range"] = "L1-L1"
        entry["source_excerpt"] = "对手先伸手。"
        entry["source_style_granularity"]["sentence_relation_and_rhythm"]["source_evidence"] = [
            "对手先伸手。",
            "不存在于行段",
        ]
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("精确行段" in error for error in errors))

    def test_source_excerpt_must_match_exact_range(self) -> None:
        entry = copy.deepcopy(self.base_subflow)
        entry["source_excerpt"] = "被截断的切片"
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("source_excerpt" in error for error in errors))

    def test_cross_book_library_preserves_source_boundary(self) -> None:
        book_dir = self.root / "拆文库" / "测试书" / "写作资产"
        book_dir.mkdir(parents=True)
        index = book_dir / "子流程索引.jsonl"
        index.write_text(
            json.dumps(subflow(), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (book_dir / "仿写无损编译包.json").write_text("{}", encoding="utf-8")
        entries = LIBRARY.build_library(self.root / "拆文库")
        self.assertEqual("测试书::SF-01", entries[0]["global_subflow_id"])
        self.assertEqual(str(index.resolve()), entries[0]["source_index_path"])
        self.assertEqual(LIBRARY.sha256(index), entries[0]["source_index_sha256"])

    def test_cross_book_library_skips_unreleased_book(self) -> None:
        ready = self.root / "拆文库" / "已放行" / "写作资产"
        stale = self.root / "拆文库" / "未放行" / "写作资产"
        ready.mkdir(parents=True)
        stale.mkdir(parents=True)
        (ready / "子流程索引.jsonl").write_text(
            json.dumps(subflow(), ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (ready / "仿写无损编译包.json").write_text("{}", encoding="utf-8")
        (stale / "子流程索引.jsonl").write_text(
            json.dumps({**subflow("SF-02"), "causal_preconditions": {}}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        entries = LIBRARY.build_library(self.root / "拆文库")
        self.assertEqual(["SF-01"], [entry["subflow_id"] for entry in entries])


if __name__ == "__main__":
    unittest.main()
