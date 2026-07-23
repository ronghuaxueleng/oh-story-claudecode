from __future__ import annotations

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
        "source_range": "L1-L2",
        "function_tags": ["公开失位"],
        "entry_state": "主角仍有现场决定权。",
        "required_sequence": ["对手先抢入口", "关系人随后要求主角让位"],
        "scene_granularity": "对手先伸手，主角挡住，关系人表态后主角才松手。",
        "information_delay": "本场只漏出偏护，完整责任压后。",
        "control_changes": ["入口控制权从主角转给对手"],
        "emotion_sequence": ["警觉", "受辱", "余痛"],
        "end_state": "主角失去默认进入权。",
        "embeddable_after": [],
        "incompatible_with": [],
        "source_evidence": ["对手先伸手", "主角才松手"],
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
        self.original = "对手先伸手，主角挡住，关系人表态后主角才松手。"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_entries(self, entries: list[dict]) -> None:
        self.index.write_text(
            "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
            encoding="utf-8",
        )

    def test_complete_subflow_assets_pass(self) -> None:
        self.write_entries([subflow()])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertEqual([], errors)

    def test_missing_field_blocks(self) -> None:
        entry = subflow()
        del entry["end_state"]
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("缺少字段" in error for error in errors))

    def test_uncovered_bridge_blocks(self) -> None:
        card = self.root / "写作资产" / "桥段施工卡.md"
        card.write_text("## BID-01 公开失位\n\n## BID-02 私域换主\n", encoding="utf-8")
        self.write_entries([subflow()])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("未覆盖全部父 BID" in error for error in errors))

    def test_fake_source_evidence_blocks(self) -> None:
        entry = subflow()
        entry["source_evidence"] = ["对手先伸手", "并不存在的原句"]
        self.write_entries([entry])
        errors: list[str] = []
        VALIDATOR.check_subflow_assets(self.root, self.original, errors)
        self.assertTrue(any("不在原文中" in error for error in errors))

    def test_cross_book_library_preserves_source_boundary(self) -> None:
        book_dir = self.root / "拆文库" / "测试书" / "写作资产"
        book_dir.mkdir(parents=True)
        index = book_dir / "子流程索引.jsonl"
        index.write_text(
            json.dumps(subflow(), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        entries = LIBRARY.build_library(self.root / "拆文库")
        self.assertEqual("测试书::SF-01", entries[0]["global_subflow_id"])
        self.assertEqual(str(index.resolve()), entries[0]["source_index_path"])
        self.assertEqual(LIBRARY.sha256(index), entries[0]["source_index_sha256"])


if __name__ == "__main__":
    unittest.main()
