from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_prose_granularity_contract.py"
)
SPEC = importlib.util.spec_from_file_location("prose_granularity_contract", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ProseGranularityContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "原文.txt"
        self.draft = self.root / "正文.md"
        self.receipt = self.root / "全文文字颗粒度契约回执.json"
        self.source_text = (
            "我没想到今天会在这里遇见他。他伸手拦我，我直接把他的手推了回去。"
            "他问我是不是非要这样。我不知道我哪样了？难道站在这里也是我的错？"
            "我懒得和他争，转身去拿桌上的钥匙。钥匙没拿到，倒先听见她哭了。"
            "有意思。明明从头到尾我一句话都没说，现在倒像是我欺负了人。"
            "最后我把门关上。外面还有人在说话，我没再听，反正也不重要了。"
        )
        self.source.write_text(self.source_text, encoding="utf-8")
        self.draft.write_text(
            "# 测试\n\n1.\n\n我没想到来取东西会撞见他们。\n\n他伸手拦我，我把钥匙收了回来。\n\n2.\n\n她先哭了。\n\n有意思，我还什么都没问。\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def completed_receipt(self, include_draft: bool = True) -> dict:
        receipt = GATE.create_receipt("测试", self.source)
        receipt["reviewed_by_current_model"] = True
        receipt["prewrite_status"] = "passed"
        long_quotes = [
            self.source_text[:80],
            self.source_text[20:110],
            self.source_text[50:150],
            self.source_text[80:180],
            self.source_text[110:],
        ]
        purposes = ["开口", "高压", "对白", "日常", "收口"]
        receipt["source_baseline"]["continuous_excerpts"] = [
            {
                "quote": quote,
                "purpose": purpose,
                "language_judgment": "连续口语叙述，人物判断跟着现场发生。",
            }
            for quote, purpose in zip(long_quotes, purposes)
        ]
        anchors = ["我没想到今天会在这里遇见他。", "有意思。"]
        for name in GATE.REQUIRED_DIMENSIONS:
            receipt["source_baseline"]["dimensions"][name] = {
                "rule": f"{name} 使用主体原文口气。",
                "source_quotes": anchors,
                "transfer_rule": "迁移句间关系，不复制人物和事件。",
                "ai_drift_to_reject": "拒绝工整总结和复合钩子加工句。",
            }
        receipt["source_baseline"]["anti_patterns"] = [
            {"pattern": f"AI模板{i}", "why_unlike_source": "原文不会这样总结意义。"}
            for i in range(3)
        ]
        receipt["source_baseline"]["manual_judgment"] = "主体声线基线已人工建立。"
        receipt["calibration_samples"] = [
            {
                "source_quote": "我没想到今天会在这里遇见他。他伸手拦我，我直接把他的手推了回去。",
                "target_sample": f"我没想到回来拿第{i}样东西，也会撞见他们站在门里。",
                "comparison": "都使用完整口语陈述，不挤压多重象征。",
                "functional_alignment_used_as_prose_proof": False,
                "extra_ai_shell": False,
            }
            for i in range(3)
        ]
        if include_draft:
            receipt["gate_status"] = "passed"
            receipt["draft"] = {
                "path": str(self.draft.resolve()),
                "sha256": GATE.sha256(self.draft),
            }
            section_quotes = {
                "1": ["我没想到来取东西会撞见他们。", "他伸手拦我，我把钥匙收了回来。"],
                "2": ["她先哭了。", "有意思，我还什么都没问。"],
            }
            receipt["section_reviews"] = [
                {
                    "section_id": section_id,
                    "status": "passed",
                    "target_quotes": quotes,
                    "source_anchors": anchors,
                    "dimensions_checked": list(GATE.REQUIRED_DIMENSIONS),
                    "source_voice_preserved": True,
                    "functional_alignment_used_as_prose_proof": False,
                    "extra_ai_shell": False,
                    "comparison": "目标句保持主体原文的直白口语和临场判断。",
                }
                for section_id, quotes in section_quotes.items()
            ]
            receipt["full_text_review"] = {
                "reviewed_full_text": True,
                "all_sections_reviewed": True,
                "primary_source_voice_dominant": True,
                "auxiliary_style_contamination": False,
                "functional_alignment_used_as_prose_proof": False,
                "remaining_extra_ai_shell": False,
                "conclusion": "两节均已按主体原文声线复核。",
            }
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return receipt

    def test_complete_prewrite_contract_passes(self) -> None:
        self.completed_receipt(include_draft=False)
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        errors, summary = GATE.validate_prewrite_data(data, self.source)
        self.assertEqual([], errors)
        self.assertEqual(3, summary["valid_calibration_samples"])

    def test_all_draft_sections_must_be_reviewed(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"] = receipt["section_reviews"][:1]
        self.receipt.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("正文小节缺少文字颗粒度复核: 2" in item for item in errors))

    def test_bind_draft_scaffolds_every_section(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        bound = GATE.bind_draft(receipt, self.draft)
        self.assertEqual(["1", "2"], [item["section_id"] for item in bound["section_reviews"]])
        self.assertEqual("pending", bound["gate_status"])
        self.assertEqual(GATE.sha256(self.draft), bound["draft"]["sha256"])

    def test_function_alignment_cannot_replace_prose_comparison(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["functional_alignment_used_as_prose_proof"] = True
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("functional_alignment_used_as_prose_proof" in item for item in errors))

    def test_complete_draft_contract_passes(self) -> None:
        receipt = self.completed_receipt()
        errors, summary = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertEqual([], errors)
        self.assertEqual(2, summary["passed_sections"])

    def test_changed_draft_invalidates_contract(self) -> None:
        receipt = self.completed_receipt()
        self.draft.write_text(self.draft.read_text(encoding="utf-8") + "又一句。", encoding="utf-8")
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("正文已变化" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
