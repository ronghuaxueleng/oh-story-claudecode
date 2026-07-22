from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_opening_contract.py"
)
SPEC = importlib.util.spec_from_file_location("opening_contract_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class OpeningContractGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "可直接仿写_导语拆解表.md"
        self.original = self.root / "原文.txt"
        self.target = self.root / "正文.md"
        self.receipt = self.root / "开头承重契约回执.json"
        self.source.write_text(
            "# 导语拆解\n"
            "公开越界先起事。\n"
            "随后出现错误辩词。\n"
            "最后正式任务落地。\n"
            "如果先讲任务，首屏冲击下降。\n",
            encoding="utf-8",
        )
        self.original.write_text(
            "丈夫为了女同事当众求情，我把他的手从审批表上拿开。\n"
            "他说她只是第一次犯错。\n"
            "我忽然就懂了，他已经把规矩让给了别人。\n",
            encoding="utf-8",
        )
        self.target.write_text(
            "# 测试\n"
            "丈夫替女同事当众求情，我把他的手从审批表上拿开。"
            "他却说她只是第一次犯错。值班任务这才落到我手里。\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _completed_receipt(self) -> dict:
        receipt = GATE.create_receipt("测试", self.source, self.target, "draft")
        receipt["gate_status"] = "passed"
        receipt["reviewed_by_current_model"] = True
        receipt["source_contract"] = {
            "functional_sequence": ["公开越界", "错误辩词", "正式任务落地"],
            "forbidden_precedence": ["禁止任务说明先于关系冲突"],
            "transferable_requirements": ["先亮错误站位", "随后再交代正式任务"],
        }
        receipt["original_opening_comparison"] = {
            "all_selected_sources_reviewed": True,
            "samples": [
                {
                    "path": str(self.original.resolve()),
                    "sha256": GATE.sha256(self.original),
                    "opening_quote": "丈夫为了女同事当众求情",
                    "opening_pattern": "先用当众求情暴露关系错位，再补任务和规则。",
                }
            ],
            "common_patterns": [
                "先给关系错位或公开动作，不先解释任务背景。",
                "用具体物件承载规则，不写整套流程说明。",
            ],
            "target_opening_application": [
                "目标前 60 字先出现丈夫替女同事求情。",
                "值班任务后置到关系冲突之后。",
            ],
            "exposition_removed_or_deferred": [
                "将值班任务说明后移到第三句以后。",
            ],
        }
        receipt["opening_flow_review"] = {
            "storyboard_or_construction_list": False,
            "symptoms_checked": [
                "已检查是否一句一个动作、一句一个证据、一句一个反应。",
                "已检查是否把规则 A、证据 B、边界 C 写成施工单。",
            ],
            "narrative_flow_evidence": [
                "求情、拿开手和错误辩词在同一段现场里连续发生。",
                "值班任务跟在关系错位后出现，没有单独列成流程说明。",
            ],
            "revision_method": [
                "把任务说明后移，不让开头先报流程。",
                "用手压审批表承载规则冲突，不分行列证据。",
            ],
        }
        receipt["source_evidence"] = [
            {
                "quote": "公开越界先起事。",
                "judgment": "第一拍先暴露关系中的错误站位。",
            },
            {
                "quote": "如果先讲任务，首屏冲击下降。",
                "judgment": "任务说明不得抢在钩子之前。",
            },
        ]
        for check_id in GATE.REQUIRED_CHECKS:
            receipt["checks"][check_id] = True
            receipt["target_evidence"].append(
                {
                    "check_id": check_id,
                    "quote": "丈夫替女同事当众求情",
                    "judgment": "前 120 字内已出现关系锚和错误站位。",
                }
            )
        receipt["manual_judgment"] = "功能顺序与主体导语资产一致，可以进入正文。"
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return receipt

    def test_init_exports_fixed_windows(self) -> None:
        receipt = GATE.create_receipt("测试", self.source, self.target, "draft")
        self.assertEqual(
            20,
            len(receipt["target_text"]["opening_windows"]["20"]),
        )
        self.assertTrue(
            receipt["target_text"]["opening_windows"]["60"].startswith("丈夫替女同事")
        )

    def test_complete_manual_contract_passes(self) -> None:
        self._completed_receipt()
        errors, summary = GATE.validate_receipt(
            self.receipt,
            self.source,
            self.target,
        )
        self.assertEqual([], errors)
        self.assertEqual(len(GATE.REQUIRED_CHECKS), summary["passed_checks"])

    def test_task_exposition_before_hook_is_blocking(self) -> None:
        receipt = self._completed_receipt()
        check_id = "task_exposition_does_not_precede_hook"
        receipt["gate_status"] = "blocked"
        receipt["checks"][check_id] = False
        receipt["blocking_failures"] = [check_id]
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(any("开头承重契约未满足" in error for error in errors))

    def test_changed_target_invalidates_receipt(self) -> None:
        self._completed_receipt()
        self.target.write_text(
            self.target.read_text(encoding="utf-8") + "新增一句。\n",
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(any("目标文本已变化" in error for error in errors))

    def test_changed_source_invalidates_receipt(self) -> None:
        self._completed_receipt()
        self.source.write_text(
            self.source.read_text(encoding="utf-8") + "新增规则。\n",
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(any("主体导语资产已变化" in error for error in errors))

    def test_source_evidence_must_be_real(self) -> None:
        receipt = self._completed_receipt()
        receipt["source_evidence"][0]["quote"] = "不存在的规则"
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(any("主体来源证据不在导语资产中" in error for error in errors))

    def test_original_opening_comparison_is_required(self) -> None:
        receipt = self._completed_receipt()
        receipt.pop("original_opening_comparison")
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(
            any("original_opening_comparison 必须是对象" in error for error in errors)
        )

    def test_original_opening_quote_must_be_from_real_opening(self) -> None:
        receipt = self._completed_receipt()
        receipt["original_opening_comparison"]["samples"][0][
            "opening_quote"
        ] = "不存在的开口"
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(
            any("原文开口样本 quote 不在原文前 1000 字" in error for error in errors)
        )

    def test_storyboard_or_construction_list_is_blocking(self) -> None:
        receipt = self._completed_receipt()
        check_id = "opening_not_storyboard_or_construction_list"
        receipt["gate_status"] = "blocked"
        receipt["checks"][check_id] = False
        receipt["blocking_failures"] = [check_id]
        receipt["opening_flow_review"]["storyboard_or_construction_list"] = True
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(any("必须人工确认开头不是分镜清单" in error for error in errors))
        self.assertTrue(any("开头承重契约未满足" in error for error in errors))

    def test_opening_flow_review_is_required(self) -> None:
        receipt = self._completed_receipt()
        receipt.pop("opening_flow_review")
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        errors, _ = GATE.validate_receipt(self.receipt, self.source, self.target)
        self.assertTrue(any("opening_flow_review 必须是对象" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
