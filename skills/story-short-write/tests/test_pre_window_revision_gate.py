from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_pre_window_revision_gate.py"
)
SPEC = importlib.util.spec_from_file_location("pre_window_revision_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class PreWindowRevisionGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.text = self.root / "正文.md"
        self.text.write_text("正文里有一处需要人工复核的句子。", encoding="utf-8")
        self.base_text = self.root / "窗口前回修母稿.md"
        self.base_text.write_text("母稿里有一处完整解释。", encoding="utf-8")
        self.source = self.root / "原文.txt"
        self.source.write_text(
            "他问到一半，忽然改口。\n门关上以后，走廊里没有人再说话。",
            encoding="utf-8",
        )
        self.receipts = {}
        for name in ("writing", "source", "ledger"):
            path = self.root / f"{name}.json"
            path.write_text(json.dumps({"gate_status": "passed"}), encoding="utf-8")
            self.receipts[name] = path

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def receipt(self) -> dict:
        return {
            "status": "completed",
            "execution_mode": "current_model_manual",
            "window_order": "pre_window_revision_before_segmentation",
            "text": {
                "path": str(self.text),
                "sha256": GATE.sha256(self.text),
                "char_count": len(self.text.read_text(encoding="utf-8")),
                "word_count": GATE.count_fanqie(self.text.read_text(encoding="utf-8")),
                "word_count_rule": "fanqie_non_whitespace_without_markdown_headings",
            },
            "prerequisites": {
                key: {
                    "path": str(path),
                    "sha256": GATE.sha256(path),
                    "gate_status": "passed",
                }
                for key, path in (
                    ("writing_rule_receipt", self.receipts["writing"]),
                    ("source_read_receipt", self.receipts["source"]),
                    ("rule_execution_ledger", self.receipts["ledger"]),
                )
            },
            "required_readings": [
                "references/anti-ai-writing.md",
                "references/craft/narrator-voice.md",
            ],
            "rule_families_applied": ["S_DRAFT_CRAFT"],
            "source_assets_applied": ["写作资产/作者DNA指纹.md"],
            "revision_items": [
                {
                    "rule_or_asset": "S_DRAFT_CRAFT",
                    "status": "completed",
                    "execution_mode": "human",
                    "evidence": [
                        {
                            "quote": "正文里有一处需要人工复核的句子。",
                            "judgment": "已按规则完成人工判断。",
                        }
                    ],
                }
            ],
            "manual_summary": "已完成窗口前规则和主体资产定向回修。",
        }

    def test_valid_receipt_passes(self) -> None:
        receipt = self.root / "receipt.json"
        receipt.write_text(
            json.dumps(self.receipt(), ensure_ascii=False),
            encoding="utf-8",
        )
        self.assertEqual([], GATE.validate(receipt, self.text))

    def test_pending_receipt_is_blocked(self) -> None:
        data = self.receipt()
        data["status"] = "pending"
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps(data), encoding="utf-8")
        errors = GATE.validate(receipt, self.text)
        self.assertTrue(any("status 必须为 completed" in item for item in errors))

    def imitation_receipt(self) -> dict:
        data = self.receipt()
        source_path = str(self.source.resolve())
        source_sha = GATE.sha256(self.source)
        data.update(
            {
                "imitation_mode": True,
                "base_text": {
                    "path": str(self.base_text.resolve()),
                    "sha256": GATE.sha256(self.base_text),
                },
                "selected_sources": [{"path": source_path, "sha256": source_sha}],
                "source_granularity_baseline": {
                    "source_evidence": [
                        {
                            "source_path": source_path,
                            "source_sha256": source_sha,
                            "quote": "他问到一半，忽然改口。",
                            "function": "用改口保留人物没有说全的反应。",
                        },
                        {
                            "source_path": source_path,
                            "source_sha256": source_sha,
                            "quote": "门关上以后，走廊里没有人再说话。",
                            "function": "以空间动作收场，不追加总结。",
                        },
                    ],
                    "sentence_rhythm": "短断和停顿随现场压力变化。",
                    "narrator_interjection": "只作即时插嘴，不代替人物解释。",
                    "dialogue_action_ratio": "对白和动作互相截断。",
                    "information_release": "信息从改口中漏出。",
                    "explanation_density": "动作后不补意义。",
                    "scene_ending": "用关门骤断。",
                    "manual_judgment": "回修不得把改口和骤断整理成完整复句。",
                },
            }
        )
        data["revision_items"][0]["text_changed"] = True
        data["revision_blocks"] = [
            {
                "target_block": "关系对峙段",
                "source_path": source_path,
                "source_sha256": source_sha,
                "source_evidence": [
                    "他问到一半，忽然改口。",
                    "门关上以后，走廊里没有人再说话。",
                ],
                "base_text_evidence": ["母稿里有一处完整解释。"],
                "revised_text_evidence": ["正文里有一处需要人工复核的句子。"],
                "preserved_source_granularity": "保留改口、短断和场末空白。",
                "removed_draft_extra_ai_shell": "删除动作后的作者解释。",
                "no_added_explanation_density": True,
                "no_source_rhythm_regularization": True,
                "surface_copy_check": True,
                "manual_judgment": "语言运行方式对齐，但没有复制原句。",
            }
        ]
        return data

    def test_imitation_revision_with_dual_baseline_passes(self) -> None:
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps(self.imitation_receipt(), ensure_ascii=False), encoding="utf-8")
        self.assertEqual([], GATE.validate(receipt, self.text))

    def test_imitation_revision_without_source_blocks_is_blocked(self) -> None:
        data = self.imitation_receipt()
        data["revision_blocks"] = []
        receipt = self.root / "receipt.json"
        receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate(receipt, self.text)
        self.assertTrue(any("必须填写 revision_blocks" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
