from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_source_read_gate.py"
SPEC = importlib.util.spec_from_file_location("source_read_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class SourceReadGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "拆文库" / "样本"
        self.receipt_path = self.root / "项目" / "写作资产" / "拆文读取回执.json"
        self._build_complete_source()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _build_complete_source(self) -> None:
        for relative in GATE.REQUIRED_FILES:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                path.write_text('{"证据词": "资产证据"}', encoding="utf-8")
            else:
                path.write_text(f"# {path.stem}\n\n资产证据\n", encoding="utf-8")

    def _write_completed_receipt(self) -> dict:
        receipt, errors = GATE.create_receipt("测试项目", [self.source])
        self.assertEqual([], errors)
        receipt["gate_status"] = "passed"
        receipt["confirmed_before_outline"] = True
        receipt["confirmed_before_draft"] = True
        for source in receipt["sources"]:
            for item in source["files"]:
                item["status"] = "read"
                item["evidence_terms"] = ["资产证据"]
                item["takeaways"] = ["已提取该文件的可迁移资产"]
                item["used_for"] = ["细纲与正文"]
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return receipt

    def test_pending_receipt_is_blocked(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目", [self.source])
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        validation_errors, _ = GATE.validate_receipt(self.receipt_path)
        self.assertTrue(any("gate_status" in error for error in validation_errors))
        self.assertTrue(any("尚未标记已读" in error for error in validation_errors))

    def test_complete_receipt_passes(self) -> None:
        self._write_completed_receipt()
        validation_errors, summary = GATE.validate_receipt(self.receipt_path)
        self.assertEqual([], validation_errors)
        self.assertEqual(len(GATE.REQUIRED_FILES), summary["read_count"])

    def test_missing_asset_requires_reanalysis(self) -> None:
        (self.source / GATE.TABLE_FILES[0]).unlink()
        _, errors = GATE.create_receipt("测试项目", [self.source])
        self.assertTrue(any("缺少拆文资产" in error for error in errors))

    def test_changed_source_requires_reread(self) -> None:
        self._write_completed_receipt()
        path = self.source / "拆文报告.md"
        path.write_text(path.read_text(encoding="utf-8") + "新增内容", encoding="utf-8")
        validation_errors, _ = GATE.validate_receipt(self.receipt_path)
        self.assertTrue(any("文件已变化" in error for error in validation_errors))

    def test_retroactive_receipt_is_blocked(self) -> None:
        output = self.root / "项目" / "正文.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("正文", encoding="utf-8")
        old_time = time.time() - 20
        os.utime(output, (old_time, old_time))
        self._write_completed_receipt()
        validation_errors, _ = GATE.validate_receipt(self.receipt_path, [output])
        self.assertTrue(any("事后补填" in error for error in validation_errors))

    def test_sample_comparison_is_mandatory(self) -> None:
        (self.source / "_sample_comparison.md").unlink()
        _, errors = GATE.create_receipt("测试项目", [self.source])
        self.assertTrue(any("_sample_comparison.md" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
