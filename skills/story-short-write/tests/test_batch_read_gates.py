from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_read_gates.py"
SPEC = importlib.util.spec_from_file_location("batch_read_gates", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchReadGatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skill_root = self.root / "story-short-write"
        self.source = self.root / "拆文库" / "样本"
        self.project_root = self.root / "项目"
        self.writing_receipt = self.project_root / "写作资产" / "写作规则读取回执.json"
        self.source_receipt = self.project_root / "写作资产" / "拆文读取回执.json"
        self.setting = self.project_root / "设定.md"
        self.outline = self.project_root / "小节大纲.md"
        self.draft = self.project_root / "正文.md"

        for relative in GATE.WRITING_GATE.REQUIRED_RULES:
            path = self.skill_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {path.stem}\n\n规则证据\n", encoding="utf-8")
        for relative in GATE.SOURCE_GATE.REQUIRED_FILES:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                path.write_text('{"证据词": "资产证据"}', encoding="utf-8")
            else:
                path.write_text(f"# {path.stem}\n\n资产证据\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _complete_receipts(self) -> None:
        writing = json.loads(self.writing_receipt.read_text(encoding="utf-8"))
        writing["gate_status"] = "passed"
        writing["confirmed_before_outline"] = True
        writing["confirmed_before_draft"] = True
        for item in writing["files"]:
            item["status"] = "read"
            item["evidence_terms"] = ["规则证据"]
            item["takeaways"] = ["已读取当前规则并提取写前约束"]
            item["used_for"] = ["设定、大纲与正文"]
        self.writing_receipt.write_text(
            json.dumps(writing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        source = json.loads(self.source_receipt.read_text(encoding="utf-8"))
        source["gate_status"] = "passed"
        source["confirmed_before_outline"] = True
        source["confirmed_before_draft"] = True
        for source_item in source["sources"]:
            for item in source_item["files"]:
                item["status"] = "read"
                item["evidence_terms"] = ["资产证据"]
                item["takeaways"] = ["已提取该文件的可迁移资产"]
                item["used_for"] = ["细纲与正文"]
        self.source_receipt.write_text(
            json.dumps(source, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_init_creates_both_receipts(self) -> None:
        errors, summary = GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.writing_receipt.is_file())
        self.assertTrue(self.source_receipt.is_file())
        self.assertEqual(3, summary["writing_files"])
        self.assertGreater(summary["source_files"], 10)

    def test_validate_passes_when_both_receipts_pass(self) -> None:
        GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )
        self._complete_receipts()
        self.setting.parent.mkdir(parents=True, exist_ok=True)
        self.setting.write_text("设定", encoding="utf-8")
        self.outline.write_text("大纲", encoding="utf-8")
        self.draft.write_text("", encoding="utf-8")

        errors, summary = GATE.validate_batch(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
            skill_root=self.skill_root,
        )

        self.assertEqual([], errors)
        self.assertEqual(3, summary["writing_read_count"])
        self.assertGreater(summary["source_read_count"], 10)

    def test_init_blocks_existing_writing_receipt_without_force(self) -> None:
        self.writing_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.writing_receipt.write_text("{}", encoding="utf-8")

        errors, _summary = GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )

        self.assertTrue(any("写作规则读取回执已存在" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
