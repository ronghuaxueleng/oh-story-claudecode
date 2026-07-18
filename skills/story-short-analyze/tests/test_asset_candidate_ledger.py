from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_short_analyze_outputs.py"
)
SPEC = importlib.util.spec_from_file_location("short_analyze_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class AssetCandidateLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "写作资产").mkdir()
        (self.root / "原文").mkdir()
        self.source_lines = [f"这是第{i}行的原文锚点" for i in range(1, 241)]
        self.source_path = self.root / "原文" / "样本.txt"
        self.source_path.write_text("\n".join(self.source_lines), encoding="utf-8")

        sha1 = hashlib.sha1(self.source_path.read_bytes()).hexdigest()
        manifest = {
            "source_file": str(self.source_path),
            "copied_to": str(self.source_path),
            "sha1": sha1,
            "copied_sha1": sha1,
            "char_count_no_whitespace": 1000,
            "line_count": len(self.source_lines),
            "chapter_count": 0,
            "chapter_markers": [],
            "chunks": [
                {"id": 1, "start_line": 1, "end_line": 120, "sha1": "unused"},
                {"id": 2, "start_line": 121, "end_line": 240, "sha1": "unused"},
            ],
            "tail_anchor": {"line": 240, "text": self.source_lines[-1]},
        }
        (self.root / "_source_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        self.entries = self._build_entries()
        self._write_targets()
        self._write_ledger()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _build_entries(self) -> list[dict[str, str | int]]:
        categories = [
            "导语",
            "物件",
            "物件",
            "动作",
            "动作",
            "对白功能",
            "对白功能",
            "对话衔接",
            "误判",
            "钩子",
            "钩子",
            "微动作",
            "微动作",
            "安静压迫场",
            "人物偏手",
            "人物偏手",
            "烂关系漏出",
            "后果链",
            "后果链",
        ]
        entries: list[dict[str, str | int]] = []
        for index, category in enumerate(categories, start=1):
            line = index if index < len(categories) else 130
            entries.append(
                {
                    "id": index,
                    "line": line,
                    "anchor": self.source_lines[line - 1],
                    "category": category,
                    "asset": f"{category}资产{index:02d}",
                    "target": VALIDATOR.ASSET_CANDIDATE_CATEGORY_TARGETS[category],
                }
            )
        return entries

    def _write_targets(self) -> None:
        assets_by_target: dict[str, list[str]] = {
            target: [] for target in VALIDATOR.DIRECT_IMITATION_FILES
        }
        for entry in self.entries:
            assets_by_target[str(entry["target"])].append(str(entry["asset"]))
        for target, assets in assets_by_target.items():
            rows = "\n".join(
                f"| {asset} | 对应原文证据 | 保留独立功能 |"
                for asset in assets
            )
            text = (
                "| 资产 | 原文证据 | 迁移提醒 |\n"
                "|---|---|---|\n"
                f"{rows}\n"
            )
            (self.root / target).write_text(text, encoding="utf-8")

    def _write_ledger(
        self,
        include_chunk_2: bool = True,
        chunk_2_empty: bool = False,
    ) -> None:
        lines = ["# 原文资产候选池", ""]
        for entry in self.entries:
            lines.append(
                f"C{entry['id']:03d} | L{entry['line']}-L{entry['line']} | "
                f"锚点：{entry['anchor']} | 类别：{entry['category']} | "
                f"资产名：{entry['asset']} | 去向：{entry['target']} | "
                "状态：已收录 | 理由：保留独立功能与原文证据"
            )
        present_categories = {str(entry["category"]) for entry in self.entries}
        lines.extend(["", "## 类别覆盖确认"])
        for category in VALIDATOR.ASSET_CANDIDATE_CATEGORY_TARGETS:
            if category not in present_categories:
                lines.append(f"- {category}：已扫，原文未发现")
        lines.extend(
            [
                "",
                "## 专项回扫确认",
                "- 物件替换对：已扫，原文资产均已登记",
                "- 微动作角色覆盖：已扫，原文资产均已登记",
                "- 对白侵占与假道歉：已扫，原文未发现额外资产",
                "- 安静等待与未归：已扫，原文未发现额外资产",
                "- 未来公开事件钩子：已扫，原文资产均已登记",
                "",
                "## 分块回扫确认",
                "- Chunk 1：L1-L120 | 状态：已回扫 | 新增候选：C001-C018",
            ]
        )
        if include_chunk_2:
            if chunk_2_empty:
                lines.append(
                    "- Chunk 2：L121-L240 | 状态：已回扫 | 新增候选：无 | "
                    "空缺复核：本块只有环境承接，没有新增独立资产"
                )
            else:
                lines.append("- Chunk 2：L121-L240 | 状态：已回扫 | 新增候选：C019")
        lines.extend(["", "## 反向漏项审计"])
        for index in range(1, 6):
            lines.append(
                f"- A{index:03d} | L{index}-L{index} | 原文：{self.source_lines[index - 1]} | "
                "判定：不收录 | 去向：无 | 理由：与现有候选属于同一事件的重复表述"
            )
        (self.root / "写作资产" / "原文资产候选池.md").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    def _check(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_asset_candidate_ledger(
            self.root,
            self.source_lines,
            1000,
            errors,
            notes,
        )
        return errors, notes

    def test_complete_ledger_passes(self) -> None:
        errors, notes = self._check()
        self.assertEqual([], errors)
        self.assertTrue(any("候选池闸门通过" in note for note in notes))

    def test_source_object_cue_must_be_covered(self) -> None:
        self.source_lines[99] = "拍卖会上出现一枚钻戒"
        errors, _ = self._check()
        self.assertTrue(any("原文出现高价值信号 `钻戒`" in error for error in errors))

    def test_source_micro_action_cue_must_be_covered(self) -> None:
        self.source_lines[100] = "她死死咬住嘴唇，没有解释"
        errors, _ = self._check()
        self.assertTrue(any("原文出现高价值信号 `咬住嘴唇`" in error for error in errors))

    def test_generic_cue_can_be_excluded_by_substantive_audit(self) -> None:
        self.source_lines[99] = "她低下头整理鞋带，动作不承担关系或情绪功能"
        ledger_path = self.root / "写作资产" / "原文资产候选池.md"
        text = ledger_path.read_text(encoding="utf-8")
        ledger_path.write_text(
            text
            + "\n- A006 | L100-L100 | 原文：她低下头整理鞋带 | 判定：不收录 | 去向：无 | "
            "理由：这里只是连续动作中的空间姿态，不改变人物关系、情绪或事件走向\n",
            encoding="utf-8",
        )
        errors, _ = self._check()
        self.assertFalse(any("原文出现高价值信号 `低下头`" in error for error in errors))

    def test_generic_cue_without_matching_audit_still_blocks(self) -> None:
        self.source_lines[99] = "她低下头整理鞋带"
        errors, _ = self._check()
        self.assertTrue(any("原文出现高价值信号 `低下头`" in error for error in errors))

    def test_other_source_cue_categories_must_be_covered(self) -> None:
        cases = (
            ("今晚陪我一起睡", "陪我一起睡"),
            ("他整夜没有回家", "没有回家"),
            ("婚礼改成全程直播", "全程直播"),
        )
        for source_line, expected_cue in cases:
            with self.subTest(cue=expected_cue):
                self.source_lines[101] = source_line
                errors, _ = self._check()
                self.assertTrue(
                    any(f"原文出现高价值信号 `{expected_cue}`" in error for error in errors)
                )
                self.source_lines[101] = "这是第102行的原文锚点"

    def test_included_candidate_must_reach_target_table(self) -> None:
        entry = self.entries[0]
        (self.root / str(entry["target"])).write_text("", encoding="utf-8")
        errors, _ = self._check()
        self.assertTrue(any("标记已收录" in error for error in errors))

    def test_each_chunk_requires_rescan_confirmation(self) -> None:
        self._write_ledger(include_chunk_2=False)
        errors, _ = self._check()
        self.assertTrue(any("缺少 Chunk 2 回扫确认" in error for error in errors))

    def test_sparse_book_and_empty_chunk_do_not_force_filler(self) -> None:
        self.entries = [self.entries[0]]
        self._write_targets()
        self._write_ledger(chunk_2_empty=True)
        errors, notes = self._check()
        self.assertEqual([], errors)
        self.assertTrue(any("低于按篇幅要求的最低值" in note for note in notes))

    def test_long_sample_candidate_floor_is_blocking(self) -> None:
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_asset_candidate_ledger(
            self.root,
            self.source_lines,
            8000,
            errors,
            notes,
        )
        self.assertTrue(any("低于按篇幅要求的最低值 40" in error for error in errors))

    def test_reverse_audit_floor_is_blocking(self) -> None:
        ledger_path = self.root / "写作资产" / "原文资产候选池.md"
        text = ledger_path.read_text(encoding="utf-8")
        audit_start = text.index("## 反向漏项审计")
        ledger_path.write_text(
            text[:audit_start]
            + "## 反向漏项审计\n"
            + "- A001 | L1-L1 | 原文：这是第1行的原文锚点 | 判定：不收录 | "
            + "去向：无 | 理由：与现有候选属于同一事件的重复表述\n",
            encoding="utf-8",
        )
        errors, _ = self._check()
        self.assertTrue(any("低于最低要求 5 项" in error for error in errors))

    def test_missing_category_requires_explicit_absence_declaration(self) -> None:
        ledger_path = self.root / "写作资产" / "原文资产候选池.md"
        text = ledger_path.read_text(encoding="utf-8")
        ledger_path.write_text(
            text.replace("- 顺序事件：已扫，原文未发现\n", ""),
            encoding="utf-8",
        )
        errors, _ = self._check()
        self.assertTrue(any("`顺序事件` 没有候选" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
