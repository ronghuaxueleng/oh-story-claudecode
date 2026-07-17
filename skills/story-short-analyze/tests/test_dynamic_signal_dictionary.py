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
SPEC = importlib.util.spec_from_file_location("short_analyze_dynamic_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class DynamicSignalDictionaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "写作资产").mkdir()
        (self.root / "原文").mkdir()
        self.source_lines = ["母亲一直叫我阿宁", "这一称呼只在家里使用"]
        source_path = self.root / "原文" / "样本.txt"
        source_path.write_text("\n".join(self.source_lines), encoding="utf-8")
        sha1 = hashlib.sha1(source_path.read_bytes()).hexdigest()
        manifest = {
            "source_file": str(source_path),
            "copied_to": str(source_path),
            "sha1": sha1,
            "copied_sha1": sha1,
            "char_count_no_whitespace": 20,
            "line_count": 2,
            "chapter_count": 0,
            "chapter_markers": [],
            "chunks": [{"id": 1, "start_line": 1, "end_line": 2, "sha1": "unused"}],
            "tail_anchor": {"line": 2, "text": self.source_lines[-1]},
        }
        (self.root / "_source_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.root / "写作资产" / "原文资产候选池.md").write_text(
            "C001 | L1-L1 | 锚点：母亲一直叫我阿宁 | 类别：人物偏手 | "
            "资产名：家内专属称呼 | 去向：可直接仿写_人物偏手表.md | "
            "状态：已收录 | 理由：称呼限定关系边界",
            encoding="utf-8",
        )
        self.payload = self._payload()
        self._write_payload()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _payload(self) -> dict:
        categories = {category: [] for category in VALIDATOR.DYNAMIC_SIGNAL_CATEGORIES}
        categories["人物别名"] = [
            {
                "term": "阿宁",
                "line_start": 1,
                "line_end": 1,
                "anchor": "母亲一直叫我阿宁",
                "candidate_ids": ["C001"],
                "index_only_reason": "",
            }
        ]
        payload = {
            "version": "1.0",
            "categories": categories,
            "backfill_rounds": [
                {
                    "round": 1,
                    "phase": "首次全文发现",
                    "rescanned_chunks": [1],
                    "added_terms": ["人物别名:阿宁"],
                    "new_candidate_ids": ["C001"],
                    "notes": "首次全文建立信号",
                },
                {
                    "round": 2,
                    "phase": "表后回扫",
                    "rescanned_chunks": [1],
                    "added_terms": [],
                    "new_candidate_ids": [],
                    "notes": "表后复扫无新增",
                },
            ],
        }
        state_sha1 = VALIDATOR.dynamic_state_sha1({"阿宁"}, {"1"})
        payload["stability_checks"] = [
            {
                "round": index,
                "rescanned_chunks": [1],
                "added_terms": [],
                "new_candidate_ids": [],
                "state_sha1": state_sha1,
                "notes": f"独立漏项审计第{index}轮没有发现新增资产",
            }
            for index in (1, 2)
        ]
        payload["stabilized"] = True
        return payload

    def _write_payload(self) -> None:
        (self.root / "写作资产" / "本书动态信号字典.json").write_text(
            json.dumps(self.payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def _check(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_dynamic_signal_dictionary(
            self.root,
            self.source_lines,
            errors,
            notes,
        )
        return errors, notes

    def test_valid_dictionary_passes(self) -> None:
        errors, notes = self._check()
        self.assertEqual([], errors)
        self.assertTrue(any("动态信号字典闸门通过" in note for note in notes))

    def test_anchor_must_exist_in_source_range(self) -> None:
        self.payload["categories"]["人物别名"][0]["anchor"] = "原文不存在"
        self._write_payload()
        errors, _ = self._check()
        self.assertTrue(any("anchor 不在对应原文范围" in error for error in errors))

    def test_candidate_reference_must_exist(self) -> None:
        self.payload["categories"]["人物别名"][0]["candidate_ids"] = ["C999"]
        self._write_payload()
        errors, _ = self._check()
        self.assertTrue(any("不存在的候选 C999" in error for error in errors))

    def test_post_table_rescan_is_required(self) -> None:
        self.payload["backfill_rounds"] = self.payload["backfill_rounds"][:1]
        self._write_payload()
        errors, _ = self._check()
        self.assertTrue(any("缺少回补阶段：表后回扫" in error for error in errors))

    def test_stability_fingerprint_must_match_current_state(self) -> None:
        self.payload["stability_checks"][1]["state_sha1"] = "bad"
        self._write_payload()
        errors, _ = self._check()
        self.assertTrue(any("state_sha1 与当前字典/候选池状态不一致" in error for error in errors))

    def test_stability_check_must_have_no_new_assets(self) -> None:
        self.payload["stability_checks"][0]["new_candidate_ids"] = ["C001"]
        self._write_payload()
        errors, _ = self._check()
        self.assertTrue(any("仍有新增项，不能判定稳定" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
