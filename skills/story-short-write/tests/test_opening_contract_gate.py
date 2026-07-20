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


if __name__ == "__main__":
    unittest.main()
