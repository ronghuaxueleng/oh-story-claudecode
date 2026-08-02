from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_first_draft_basic_review.py"
)
SPEC = importlib.util.spec_from_file_location("first_draft_basic_review", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)

ENTRY_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_first_draft_entry.py"
)
ENTRY_SPEC = importlib.util.spec_from_file_location("first_draft_entry", ENTRY_SCRIPT)
assert ENTRY_SPEC and ENTRY_SPEC.loader
ENTRY = importlib.util.module_from_spec(ENTRY_SPEC)
ENTRY_SPEC.loader.exec_module(ENTRY)


class FirstDraftBasicReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.draft = self.root / "正文.md"
        self.receipt = self.root / "写作资产" / "首稿基础审计回执.json"
        self.source = self.root / "拆文库" / "主体" / "原文.txt"
        self.section_execution = self.root / "写作资产" / "逐节首写执行回执.json"
        self.draft_entry = self.root / "写作资产" / "首稿入口回执.json"
        self.source.parent.mkdir(parents=True)
        self.source.write_text(
            "她看着那把钥匙，原本想问，话到嘴边却换成了别的。\n"
            "钥匙落进别人掌心，她低头看了很久，什么也没解释。\n",
            encoding="utf-8",
        )
        self.draft.write_text(
            "## 1\n\n她原本想问他为什么，却在看见那把钥匙时改了口。\n\n"
            "钥匙交出去以后，她掌心还留着一道红痕。\n",
            encoding="utf-8",
        )
        self.section_execution.parent.mkdir(parents=True, exist_ok=True)
        self.section_execution.write_text(
            json.dumps(
                {
                    "gate_status": "passed",
                    "final_draft_sha256": GATE.sha256(self.draft),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.draft_entry.write_text(
            json.dumps(
                {
                    "gate": "first_draft_entry",
                    "gate_status": "passed",
                    "draft_path": str(self.draft.resolve()),
                    "section_execution_receipt_path": str(self.section_execution.resolve()),
                    "writing_receipt": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "source_receipt": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "ledger": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "opening_contract": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "outline_contract": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "profile": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "sequence_receipt": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "draft_capacity_contract": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                    "section_source_bundle": {"path": str(self.source.resolve()), "sha256": GATE.sha256(self.source)},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.original_entry_validate = GATE._DRAFT_ENTRY_MODULE.validate_entry
        GATE._DRAFT_ENTRY_MODULE.validate_entry = lambda _receipt, _draft=None: []
        GATE.init_receipt(
            self.draft,
            self.receipt,
            force=False,
            imitation_mode=True,
            source_paths=[self.source],
            section_execution_receipt=self.section_execution,
            draft_entry_receipt=self.draft_entry,
        )

    def tearDown(self) -> None:
        GATE._DRAFT_ENTRY_MODULE.validate_entry = self.original_entry_validate
        self.temp.cleanup()

    def passed_receipt(self) -> dict:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        source_sha = GATE.sha256(self.source)
        data["source_granularity_baseline"] = {
            "source_evidence": [
                {
                    "source_path": str(self.source.resolve()),
                    "source_sha256": source_sha,
                    "quote": "她看着那把钥匙，原本想问，话到嘴边却换成了别的。",
                    "function": "用注意偏移和临时改口承担情绪，不补完整解释。",
                },
                {
                    "source_path": str(self.source.resolve()),
                    "source_sha256": source_sha,
                    "quote": "钥匙落进别人掌心，她低头看了很久，什么也没解释。",
                    "function": "动作落下后直接收场，保留空白。",
                },
            ],
            "sentence_rhythm": "短断与稍长句交替，改口处不补因果总结。",
            "narrator_interjection": "叙述贴着人物即时注意，不替读者下结论。",
            "dialogue_action_ratio": "动作和未出口的话共同推进。",
            "information_release": "先给钥匙换手，原因延后。",
            "explanation_density": "动作后不追加主题解释。",
            "scene_ending": "以低头和沉默骤断。",
            "manual_judgment": "基础审计及回修必须保持这种断裂、留白和即时口气。",
        }
        for item in data["review_items"]:
            item["checked"] = True
            item["draft_evidence"] = ["她原本想问他为什么，却在看见那把钥匙时改了口。"]
            item["judgment"] = "句间关系、气口、情感过程和人物口气已结合上下文人工复核。"
        data["reviewed_by_current_model"] = True
        data["preview_ready"] = True
        data["gate_status"] = "passed"
        return data

    def test_imitation_mode_requires_draft_entry_receipt(self) -> None:
        other = self.root / "写作资产" / "另一份回执.json"
        result = GATE.init_receipt(
            self.draft,
            other,
            force=False,
            imitation_mode=True,
            source_paths=[self.source],
            section_execution_receipt=self.section_execution,
            draft_entry_receipt=None,
        )
        self.assertEqual(2, result)

    def test_complete_review_passes(self) -> None:
        data = self.passed_receipt()
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertEqual([], GATE.validate_receipt(self.receipt, self.draft))

    def test_issue_requires_fix_and_basic_revision(self) -> None:
        data = self.passed_receipt()
        data["review_items"][0]["issue_found"] = True
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.draft)
        self.assertTrue(any("基础回修动作" in error for error in errors))
        self.assertTrue(any("basic_revision_performed" in error for error in errors))
        self.assertTrue(any("revision_blocks" in error for error in errors))

    def test_imitation_revision_with_dual_baseline_passes(self) -> None:
        data = self.passed_receipt()
        data["review_items"][0]["issue_found"] = True
        data["review_items"][0]["fixes_applied"] = ["恢复改口和动作后的留白"]
        data["basic_revision_performed"] = True
        self.draft.write_text(
            "## 1\n\n她本来想问为什么。看见钥匙，她改了口。\n\n"
            "钥匙交出去，她低头看着掌心那道红痕。\n",
            encoding="utf-8",
        )
        data["draft"]["sha256"] = GATE.sha256(self.draft)
        execution = json.loads(self.section_execution.read_text(encoding="utf-8"))
        execution["final_draft_sha256"] = GATE.sha256(self.draft)
        self.section_execution.write_text(json.dumps(execution), encoding="utf-8")
        data["section_execution_receipt"] = GATE.source_binding(self.section_execution)
        for item in data["review_items"]:
            item["draft_evidence"] = ["她本来想问为什么。看见钥匙，她改了口。"]
        data["revision_blocks"] = [
            {
                "target_block": "第1节钥匙换手",
                "source_path": str(self.source.resolve()),
                "source_sha256": GATE.sha256(self.source),
                "source_evidence": [
                    "她看着那把钥匙，原本想问，话到嘴边却换成了别的。",
                    "钥匙落进别人掌心，她低头看了很久，什么也没解释。",
                ],
                "base_draft_evidence": ["她原本想问他为什么，却在看见那把钥匙时改了口。"],
                "revised_draft_evidence": ["她本来想问为什么。看见钥匙，她改了口。"],
                "preserved_source_granularity": "保留改口、短断和动作后留白。",
                "removed_draft_extra_ai_shell": "删去过完整的句间说明。",
                "no_added_explanation_density": True,
                "no_source_rhythm_regularization": True,
                "surface_copy_check": True,
                "manual_judgment": "只迁移语言运行方式，没有复制原句。",
            }
        ]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertEqual([], GATE.validate_receipt(self.receipt, self.draft))

    def test_imitation_revision_requires_real_source_evidence(self) -> None:
        data = self.passed_receipt()
        data["source_granularity_baseline"]["source_evidence"][0]["quote"] = "不存在的原文"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.draft)
        self.assertTrue(any("不在原文中" in error for error in errors))

    def test_draft_change_invalidates_receipt(self) -> None:
        data = self.passed_receipt()
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.draft.write_text(self.draft.read_text(encoding="utf-8") + "新增一句。", encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.draft)
        self.assertTrue(any("SHA 已变化" in error for error in errors))

    def test_evidence_must_exist_in_current_draft(self) -> None:
        data = self.passed_receipt()
        data["review_items"][0]["draft_evidence"] = ["不存在的正文原句"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.draft)
        self.assertTrue(any("不在当前正文中" in error for error in errors))

    def test_finalize_rebinds_only_after_dual_baseline_review_passes(self) -> None:
        data = self.passed_receipt()
        data["review_items"][0]["issue_found"] = True
        data["review_items"][0]["fixes_applied"] = ["恢复动作后的停顿"]
        data["basic_revision_performed"] = True
        revised_sentence = "她本来想问为什么。看见钥匙，她改了口。"
        self.draft.write_text(
            f"1.\n\n{revised_sentence}\n\n钥匙交出去，她低头看着掌心那道红痕。\n",
            encoding="utf-8",
        )
        for item in data["review_items"]:
            item["draft_evidence"] = [revised_sentence]
        data["revision_blocks"] = [
            {
                "target_block": "第1节钥匙换手",
                "source_path": str(self.source.resolve()),
                "source_sha256": GATE.sha256(self.source),
                "source_evidence": [
                    "她看着那把钥匙，原本想问，话到嘴边却换成了别的。",
                    "钥匙落进别人掌心，她低头看了很久，什么也没解释。",
                ],
                "base_draft_evidence": ["她原本想问他为什么，却在看见那把钥匙时改了口。"],
                "revised_draft_evidence": [revised_sentence],
                "preserved_source_granularity": "保留改口、动作和停顿。",
                "removed_draft_extra_ai_shell": "删去解释性连接。",
                "no_added_explanation_density": True,
                "no_source_rhythm_regularization": True,
                "surface_copy_check": True,
                "manual_judgment": "迁移运行方式，不复制原句。",
            }
        ]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        old_sha = json.loads(
            self.section_execution.read_text(encoding="utf-8")
        )["final_draft_sha256"]
        self.section_execution.write_text(
            json.dumps(
                {
                    "gate": "section_draft_execution",
                    "gate_status": "passed",
                    "draft_path": str(self.draft.resolve()),
                    "final_draft_sha256": old_sha,
                    "sections": [
                        {
                            "section_id": "1",
                            "status": "completed",
                            "opened_at": "before",
                            "closed_at": "before",
                            "read_judgment": "已读完整原文切片",
                            "manual_judgment": "四项停检通过",
                            "event_flow": "passed",
                            "emotion_flow": "passed",
                            "style_granularity": "passed",
                            "telegraphic_and_relation_check": "passed",
                            "section_sha256": old_sha,
                            "draft_sha256_after_close": old_sha,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["section_execution_receipt"] = GATE.source_binding(self.section_execution)
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        original_validate_receipt = GATE.validate_receipt
        validate_calls: list[Path] = []

        def record_validate_receipt(
            receipt: Path,
            draft_override: Path | None = None,
        ) -> list[str]:
            validate_calls.append(receipt)
            return original_validate_receipt(receipt, draft_override)

        GATE.validate_receipt = record_validate_receipt
        try:
            self.assertEqual(
                [],
                GATE.finalize_after_revision(
                    self.receipt,
                    self.draft,
                    self.section_execution,
                ),
            )
        finally:
            GATE.validate_receipt = original_validate_receipt

        execution = json.loads(self.section_execution.read_text(encoding="utf-8"))
        self.assertEqual(GATE.sha256(self.draft), execution["final_draft_sha256"])
        self.assertEqual(old_sha, execution["first_draft_sha256"])
        self.assertEqual(1, len(validate_calls))
        self.assertNotEqual(self.receipt, validate_calls[0])
        self.assertEqual([], GATE.validate_receipt(self.receipt, self.draft))

    def test_finalize_refuses_missing_revision_evidence(self) -> None:
        data = self.passed_receipt()
        data["review_items"][0]["issue_found"] = True
        data["review_items"][0]["fixes_applied"] = ["声称已修改"]
        data["basic_revision_performed"] = True
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.section_execution.write_text(
            json.dumps(
                {
                    "gate": "section_draft_execution",
                    "gate_status": "passed",
                    "final_draft_sha256": GATE.sha256(self.draft),
                    "sections": [],
                }
            ),
            encoding="utf-8",
        )
        errors = GATE.finalize_after_revision(
            self.receipt,
            self.draft,
            self.section_execution,
        )
        self.assertTrue(any("revision_blocks" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
