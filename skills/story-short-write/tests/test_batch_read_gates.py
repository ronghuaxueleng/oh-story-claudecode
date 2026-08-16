from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone


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
        self.batch_dir = self.project_root / "写作资产" / "读取批次"
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

    def test_export_batches_writes_manifest_and_fulltext_batches(self) -> None:
        GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )

        manifest = GATE.export_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            output_dir=self.batch_dir,
            batch_size=10,
        )

        self.assertEqual("story-short-write.read-batch-index.v1", manifest["schema_version"])
        self.assertTrue((self.batch_dir / "manifest.json").is_file())
        self.assertGreater(len(manifest["batches"]), 1)
        first_batch = json.loads(
            (self.batch_dir / "batch-001.json").read_text(encoding="utf-8")
        )
        self.assertEqual("story-short-write.read-batch.v1", first_batch["schema_version"])
        self.assertIn("content", first_batch["entries"][0])
        self.assertEqual("pending", first_batch["status"])
        self.assertIsNone(first_batch["review_started_at"])
        self.assertIsNone(first_batch["reviewed_at"])
        self.assertFalse(first_batch["reviewed_by_current_model"])

    def test_prepare_batches_runs_init_and_export_in_one_step(self) -> None:
        errors, summary = GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=8,
        )

        self.assertEqual([], errors)
        self.assertTrue(self.writing_receipt.is_file())
        self.assertTrue(self.source_receipt.is_file())
        self.assertTrue((self.batch_dir / "manifest.json").is_file())
        self.assertEqual(8, summary["batch_size"])
        self.assertGreater(int(summary["batch_count"]), 1)

    def test_bootstrap_project_layout_creates_standard_directories(self) -> None:
        target = self.root / "测试项目"
        errors, summary = GATE.bootstrap_project_layout(
            project="测试项目",
            project_dir=target,
        )

        self.assertEqual([], errors)
        self.assertTrue(target.is_dir())
        self.assertTrue((target / "写作资产").is_dir())
        self.assertTrue((target / "写作资产" / "读取批次").is_dir())
        self.assertTrue((target / "写作资产" / "逐节验收" / "侧车").is_dir())
        self.assertTrue((target / "写作资产" / "正式审计").is_dir())
        self.assertTrue((target / "写作资产" / "单节原型测试").is_dir())
        self.assertTrue((target / "对标").is_dir())
        self.assertTrue((target / "拆文库").is_dir())
        self.assertTrue((target / "资料库" / "开头库").is_dir())
        self.assertFalse((target / "设定.md").exists())
        layout_index = json.loads((target / "写作资产" / "项目骨架索引.json").read_text(encoding="utf-8"))
        self.assertEqual("story-short-write.project-layout.v1", layout_index["schema_version"])
        self.assertEqual(str(target / "正文.md"), layout_index["reserved_files"]["draft"])
        self.assertEqual(str(target / "写作资产" / "写作规则读取回执.json"), summary["writing_receipt"])

    def test_bootstrap_project_layout_rejects_mismatched_directory_name(self) -> None:
        target = self.root / "工作名-测试项目"
        errors, summary = GATE.bootstrap_project_layout(
            project="测试项目",
            project_dir=target,
        )

        self.assertTrue(errors)
        self.assertEqual([], summary["created_dirs"])
        self.assertFalse(target.exists())

    def test_bootstrap_project_layout_accepts_precreated_empty_directory(self) -> None:
        target = self.root / "测试项目"
        target.mkdir()

        errors, summary = GATE.bootstrap_project_layout(
            project="测试项目",
            project_dir=target,
        )

        self.assertEqual([], errors)
        self.assertTrue((target / "写作资产" / "读取批次").is_dir())
        self.assertEqual(str(target / "写作资产" / "写作规则读取回执.json"), summary["writing_receipt"])

    def test_bootstrap_project_layout_rejects_precreated_directory_with_files(self) -> None:
        target = self.root / "测试项目"
        (target / "已有文件").mkdir(parents=True)
        (target / "已有文件" / "占位.txt").write_text("x", encoding="utf-8")

        errors, summary = GATE.bootstrap_project_layout(
            project="测试项目",
            project_dir=target,
        )

        self.assertTrue(any("当前目录已含文件" in item for item in errors))
        self.assertEqual([], summary["created_dirs"])

    def test_bootstrap_project_layout_runs_prepare_batches(self) -> None:
        target = self.root / "测试项目"
        layout_errors, layout = GATE.bootstrap_project_layout(
            project="测试项目",
            project_dir=target,
        )
        self.assertEqual([], layout_errors)

        errors, summary = GATE.prepare_batches(
            project="测试项目",
            writing_receipt=Path(layout["writing_receipt"]),
            source_receipt=Path(layout["source_receipt"]),
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=Path(layout["batch_dir"]),
            batch_size=7,
        )

        self.assertEqual([], errors)
        self.assertTrue(Path(layout["writing_receipt"]).is_file())
        self.assertTrue(Path(layout["source_receipt"]).is_file())
        self.assertTrue((Path(layout["batch_dir"]) / "manifest.json").is_file())
        self.assertEqual(7, summary["batch_size"])

    def test_bootstrap_layout_exposes_machine_readable_paths(self) -> None:
        target = self.root / "测试项目"
        errors, layout = GATE.bootstrap_project_layout(
            project="测试项目",
            project_dir=target,
        )
        self.assertEqual([], errors)
        prepare_errors, summary = GATE.prepare_batches(
            project="测试项目",
            writing_receipt=Path(layout["writing_receipt"]),
            source_receipt=Path(layout["source_receipt"]),
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=Path(layout["batch_dir"]),
            batch_size=9,
        )
        self.assertEqual([], prepare_errors)
        payload = {
            "project_dir": layout["project_dir"],
            "layout_index": layout["layout_index"],
            "writing_receipt": layout["writing_receipt"],
            "source_receipt": layout["source_receipt"],
            "batch_dir": layout["batch_dir"],
            "manifest": summary["manifest_path"],
        }
        self.assertEqual(str(target), payload["project_dir"])
        self.assertTrue(Path(payload["layout_index"]).is_file())
        self.assertTrue(Path(payload["manifest"]).is_file())

    def test_emit_shell_template_contains_full_outer_flow(self) -> None:
        script = GATE.emit_shell_template(
            project="测试项目",
            project_dir=self.root / "测试项目",
            source_dirs=[self.source, self.root / "拆文库" / "辅助样本"],
            stage="outline",
            stage_output=self.root / "测试项目" / "小节大纲.md",
            source_outputs=[
                self.root / "测试项目" / "设定.md",
                self.root / "测试项目" / "小节大纲.md",
                self.root / "测试项目" / "正文.md",
            ],
            batch_size=12,
        )

        self.assertIn('batch_read_gates.py" bootstrap-project', script)
        self.assertIn('batch_read_gates.py" status', script)
        self.assertIn('batch_read_gates.py" next-step', script)
        self.assertIn('batch_read_gates.py" run-read-gates-cycle', script)
        self.assertIn("--batch-size 12", script)

    def test_start_new_project_read_gates_flow_bootstraps_and_waits_for_manual_batches(self) -> None:
        target = self.root / "测试项目"
        result = GATE.start_new_project_read_gates_flow(
            project="测试项目",
            project_dir=target,
            source_dirs=[self.source],
            stage="outline",
            stage_output=target / "小节大纲.md",
            source_outputs=[target / "设定.md", target / "小节大纲.md", target / "正文.md"],
            skill_root=self.skill_root,
            batch_size=10,
        )

        self.assertTrue(target.is_dir())
        self.assertTrue((target / "写作资产" / "读取批次" / "manifest.json").is_file())
        self.assertEqual("complete_manual_batches", result["cycle"]["action"])
        self.assertIn('batch_read_gates.py" status', result["cycle"]["next_command"])

    def test_inspect_manifest_batches_summarizes_mixed_statuses(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=4,
        )
        manifest = json.loads((self.batch_dir / "manifest.json").read_text(encoding="utf-8"))
        first_batch = Path(manifest["batches"][0]["path"])
        second_batch = Path(manifest["batches"][1]["path"])
        third_batch = Path(manifest["batches"][2]["path"])

        first = json.loads(first_batch.read_text(encoding="utf-8"))
        first["status"] = "in_progress"
        first["review_started_at"] = datetime.now(timezone.utc).isoformat()
        first_batch.write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        second = json.loads(second_batch.read_text(encoding="utf-8"))
        second["status"] = "reviewed"
        second["review_started_at"] = datetime.now(timezone.utc).isoformat()
        second["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        second["reviewed_by_current_model"] = True
        second["semantic_fields_generated_by_script"] = False
        second_batch.write_text(json.dumps(second, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        third = json.loads(third_batch.read_text(encoding="utf-8"))
        consumed = GATE.consume_sidecar(
            third_batch,
            input_sha256=GATE.sha256_file(third_batch),
            receipt_path=self.source_receipt,
            receipt_sha256=GATE.sha256_file(self.source_receipt),
            operation="batch-read-gates.apply-batch",
            counts={"updated_writing": 0, "updated_source": 0},
        )
        self.assertEqual("consumed", consumed["status"])

        summary = GATE.inspect_manifest_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
        )

        self.assertEqual(len(manifest["batches"]), summary["batch_count"])
        self.assertEqual(1, summary["status_counts"]["in_progress"])
        self.assertEqual(1, summary["status_counts"]["reviewed"])
        self.assertEqual(1, summary["status_counts"]["consumed"])
        self.assertGreaterEqual(summary["status_counts"]["pending"], 1)
        self.assertEqual(manifest["batches"][0]["entry_count"], summary["batches"][0]["entry_count"])
        self.assertEqual(
            manifest["batches"][0]["first_entry_id"],
            summary["batches"][0]["first_entry_id"],
        )
        self.assertEqual(
            manifest["batches"][0]["last_entry_id"],
            summary["batches"][0]["last_entry_id"],
        )
        self.assertIn(str(first_batch), summary["pending_batches"])
        self.assertNotIn(str(third_batch), summary["pending_batches"])

    def test_inspect_batch_file_lists_entries_and_preview(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=5,
        )

        summary = GATE.inspect_batch_file(batch_path=self.batch_dir / "batch-001.json")

        self.assertEqual("batch-001", summary["batch_id"])
        self.assertEqual("pending", summary["status"])
        self.assertEqual(5, summary["entry_count"])
        self.assertEqual("W-001", summary["entries"][0]["entry_id"])
        self.assertIn("format-and-structure.md", summary["entries"][0]["relative_path"])
        self.assertTrue(summary["entries"][0]["preview"])

    def test_suggest_next_step_prefers_manual_completion_when_batches_pending(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=4,
        )

        summary = GATE.suggest_next_step(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
        )

        self.assertEqual("complete_manual_batches", summary["action"])
        self.assertIn('batch_read_gates.py" status', summary["next_command"])

    def test_suggest_next_step_returns_finalize_when_all_batches_reviewed(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=5,
        )
        manifest = json.loads((self.batch_dir / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["batches"]:
            batch_path = Path(item["path"])
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            batch["status"] = "reviewed"
            batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_by_current_model"] = True
            batch["semantic_fields_generated_by_script"] = False
            batch_path.write_text(
                json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        summary = GATE.suggest_next_step(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
        )

        self.assertEqual("finalize_batches", summary["action"])
        self.assertIn('batch_read_gates.py" finalize-batches', summary["next_command"])

    def test_suggest_next_step_returns_validate_after_consumption_without_passed_gate(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=200,
        )
        manifest = json.loads((self.batch_dir / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["batches"]:
            batch_path = Path(item["path"])
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            batch["status"] = "reviewed"
            batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_by_current_model"] = True
            batch["semantic_fields_generated_by_script"] = False
            for entry in batch["entries"]:
                entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
                entry["takeaways"] = ["已逐条读取并提取当前批次的写前约束"]
                entry["used_for"] = ["设定、大纲与正文"]
            batch_path.write_text(
                json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        GATE.apply_manifest(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            consume=True,
        )

        summary = GATE.suggest_next_step(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
        )

        self.assertEqual("validate_receipts", summary["action"])
        self.assertIn('batch_read_gates.py" validate', summary["next_command"])

    def test_run_read_gates_cycle_waits_for_manual_completion(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=4,
        )

        result = GATE.run_read_gates_cycle(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
            skill_root=self.skill_root,
        )

        self.assertEqual("complete_manual_batches", result["action"])
        self.assertIn('batch_read_gates.py" status', result["next_command"])

    def test_run_read_gates_cycle_auto_finalizes_when_batches_ready(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=6,
        )
        manifest = json.loads((self.batch_dir / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["batches"]:
            batch_path = Path(item["path"])
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            batch["status"] = "reviewed"
            batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_by_current_model"] = True
            batch["semantic_fields_generated_by_script"] = False
            for entry in batch["entries"]:
                entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
                entry["takeaways"] = ["已逐条读取并提取当前批次的写前约束"]
                entry["used_for"] = ["设定、大纲与正文"]
            batch_path.write_text(
                json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        result = GATE.run_read_gates_cycle(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
            skill_root=self.skill_root,
        )

        self.assertEqual("finalize_batches", result["action"])
        self.assertEqual([], result["errors"])
        self.assertEqual(3, result["summary"]["writing_read_count"])

    def test_run_read_gates_cycle_auto_validates_after_consumption(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=200,
        )
        manifest = json.loads((self.batch_dir / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["batches"]:
            batch_path = Path(item["path"])
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            batch["status"] = "reviewed"
            batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_by_current_model"] = True
            batch["semantic_fields_generated_by_script"] = False
            for entry in batch["entries"]:
                entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
                entry["takeaways"] = ["已逐条读取并提取当前批次的写前约束"]
                entry["used_for"] = ["设定、大纲与正文"]
            batch_path.write_text(
                json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        GATE.apply_manifest(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            consume=True,
        )

        result = GATE.run_read_gates_cycle(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
            skill_root=self.skill_root,
        )

        self.assertEqual("validate_receipts", result["action"])
        self.assertTrue(result["errors"])

    def test_apply_batch_updates_receipts_and_consume_replaces_sidecar(self) -> None:
        GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )
        manifest = GATE.export_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            output_dir=self.batch_dir,
            batch_size=200,
        )
        batch_path = Path(manifest["batches"][0]["path"])
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        batch["status"] = "reviewed"
        batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
        batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        batch["reviewed_by_current_model"] = True
        batch["semantic_fields_generated_by_script"] = False
        batch["cross_source_decisions"] = ["主体《幼薇》独占正文声线，辅助来源只供机制。"]
        for entry in batch["entries"]:
            entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
            entry["takeaways"] = ["已读取当前文件并提取核心写作约束"]
            entry["used_for"] = ["设定、大纲与正文"]
        batch_path.write_text(
            json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        summary = GATE.apply_batch(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            batch_path=batch_path,
        )
        self.assertEqual(3, summary["updated_writing"])
        self.assertGreater(summary["updated_source"], 10)
        writing = json.loads(self.writing_receipt.read_text(encoding="utf-8"))
        self.assertTrue(all(item["status"] == "read" for item in writing["files"]))
        source = json.loads(self.source_receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            ["主体《幼薇》独占正文声线，辅助来源只供机制。"],
            source["cross_source_decisions"],
        )

        batch_sha = GATE.sha256_file(batch_path)
        payload = GATE.consume_sidecar(
            batch_path,
            input_sha256=batch_sha,
            receipt_path=self.source_receipt,
            receipt_sha256=GATE.sha256_file(self.source_receipt),
            operation="batch-read-gates.apply-batch",
            counts={"updated_writing": summary["updated_writing"], "updated_source": summary["updated_source"]},
        )
        consumed = json.loads(batch_path.read_text(encoding="utf-8"))
        self.assertEqual(payload, consumed)
        self.assertEqual("consumed", consumed["status"])

    def test_apply_batch_rejects_stale_receipt_sha(self) -> None:
        GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )
        manifest = GATE.export_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            output_dir=self.batch_dir,
            batch_size=200,
        )
        batch_path = Path(manifest["batches"][0]["path"])
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        batch["status"] = "reviewed"
        batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
        batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        batch["reviewed_by_current_model"] = True
        batch["bindings"]["source_receipt_sha256"] = "stale"
        batch_path.write_text(
            json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "拆文读取回执 SHA 已失效"):
            GATE.apply_batch(
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                batch_path=batch_path,
            )

    def test_export_batches_restores_reviewed_entries_from_receipts_after_consume(self) -> None:
        GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )
        manifest = GATE.export_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            output_dir=self.batch_dir,
            batch_size=10,
        )
        first_batch_path = Path(manifest["batches"][0]["path"])
        first_batch = json.loads(first_batch_path.read_text(encoding="utf-8"))
        first_batch["status"] = "reviewed"
        first_batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
        first_batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        first_batch["reviewed_by_current_model"] = True
        first_batch["semantic_fields_generated_by_script"] = False
        first_batch["cross_source_decisions"] = ["主体声线只认《幼薇》，辅助样本只借机制。"]
        for entry in first_batch["entries"]:
            entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
            entry["takeaways"] = ["已逐条读取并提取当前批次的写作要点"]
            entry["used_for"] = ["设定、大纲与正文"]
        first_batch_path.write_text(
            json.dumps(first_batch, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        summary = GATE.apply_batch(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            batch_path=first_batch_path,
        )
        batch_sha = GATE.sha256_file(first_batch_path)
        GATE.consume_sidecar(
            first_batch_path,
            input_sha256=batch_sha,
            receipt_path=self.source_receipt,
            receipt_sha256=GATE.sha256_file(self.source_receipt),
            operation="batch-read-gates.apply-batch",
            counts={
                "updated_writing": summary["updated_writing"],
                "updated_source": summary["updated_source"],
            },
        )

        rerun_manifest = GATE.export_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            output_dir=self.batch_dir,
            batch_size=10,
        )

        restored_first_batch = json.loads(
            Path(rerun_manifest["batches"][0]["path"]).read_text(encoding="utf-8")
        )
        pending_second_batch = json.loads(
            Path(rerun_manifest["batches"][1]["path"]).read_text(encoding="utf-8")
        )
        self.assertEqual("reviewed", restored_first_batch["status"])
        self.assertTrue(restored_first_batch["reviewed_by_current_model"])
        self.assertTrue(restored_first_batch["reviewed_at"])
        self.assertTrue(
            all(entry["evidence_terms"] for entry in restored_first_batch["entries"])
        )
        self.assertEqual(
            ["主体声线只认《幼薇》，辅助样本只借机制。"],
            restored_first_batch["cross_source_decisions"],
        )
        self.assertEqual("pending", pending_second_batch["status"])
        self.assertFalse(pending_second_batch["reviewed_by_current_model"])

    def test_apply_manifest_applies_all_batches_and_consumes_each_batch(self) -> None:
        GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )
        manifest = GATE.export_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            output_dir=self.batch_dir,
            batch_size=5,
        )
        manifest_path = self.batch_dir / "manifest.json"
        for item in manifest["batches"]:
            batch_path = Path(item["path"])
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            batch["status"] = "reviewed"
            batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_by_current_model"] = True
            batch["semantic_fields_generated_by_script"] = False
            for entry in batch["entries"]:
                entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
                entry["takeaways"] = ["已逐条读取并提取当前批次的写作要点"]
                entry["used_for"] = ["设定、大纲与正文"]
            batch_path.write_text(
                json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        summary = GATE.apply_manifest(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=manifest_path,
            consume=True,
        )

        self.assertEqual(len(manifest["batches"]), summary["applied_batches"])
        self.assertEqual(len(manifest["batches"]), summary["consumed_batches"])
        self.assertEqual(3, summary["updated_writing"])
        self.assertGreater(summary["updated_source"], 10)
        for item in manifest["batches"]:
            consumed = json.loads(Path(item["path"]).read_text(encoding="utf-8"))
            self.assertEqual("consumed", consumed["status"])

    def test_finalize_batches_applies_manifest_and_validates(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=6,
        )
        manifest = json.loads((self.batch_dir / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["batches"]:
            batch_path = Path(item["path"])
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            batch["status"] = "reviewed"
            batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            batch["reviewed_by_current_model"] = True
            batch["semantic_fields_generated_by_script"] = False
            for entry in batch["entries"]:
                entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
                entry["takeaways"] = ["已逐条读取并提取当前批次的写前约束"]
                entry["used_for"] = ["设定、大纲与正文"]
            batch_path.write_text(
                json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        errors, summary = GATE.finalize_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            manifest_path=self.batch_dir / "manifest.json",
            consume=True,
            stage="outline",
            stage_output=self.outline,
            source_outputs=[self.setting, self.outline, self.draft],
            skill_root=self.skill_root,
        )

        self.assertEqual([], errors)
        self.assertEqual(len(manifest["batches"]), summary["applied_batches"])
        self.assertEqual(len(manifest["batches"]), summary["consumed_batches"])
        self.assertEqual(3, summary["writing_read_count"])
        self.assertGreater(summary["source_read_count"], 10)

    def test_finalize_batches_blocks_when_any_batch_is_not_reviewed(self) -> None:
        GATE.prepare_batches(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
            output_dir=self.batch_dir,
            batch_size=4,
        )
        manifest = json.loads((self.batch_dir / "manifest.json").read_text(encoding="utf-8"))
        first_batch = Path(manifest["batches"][0]["path"])
        batch = json.loads(first_batch.read_text(encoding="utf-8"))
        batch["status"] = "reviewed"
        batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
        batch["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        batch["reviewed_by_current_model"] = True
        batch["semantic_fields_generated_by_script"] = False
        for entry in batch["entries"]:
            entry["evidence_terms"] = ["规则证据"] if entry["gate"] == "writing" else ["资产证据"]
            entry["takeaways"] = ["已逐条读取并提取当前批次的写前约束"]
            entry["used_for"] = ["设定、大纲与正文"]
        first_batch.write_text(
            json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "读取批次存在未完成项"):
            GATE.finalize_batches(
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                manifest_path=self.batch_dir / "manifest.json",
                consume=True,
                stage="outline",
                stage_output=self.outline,
                source_outputs=[self.setting, self.outline, self.draft],
                skill_root=self.skill_root,
            )

        writing = json.loads(self.writing_receipt.read_text(encoding="utf-8"))
        self.assertTrue(all(item["status"] == "pending" for item in writing["files"]))

    def test_apply_batch_blocks_when_status_not_reviewed(self) -> None:
        GATE.init_batch(
            project="测试项目",
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            source_dirs=[self.source],
            skill_root=self.skill_root,
            force_writing_receipt=False,
        )
        manifest = GATE.export_batches(
            writing_receipt=self.writing_receipt,
            source_receipt=self.source_receipt,
            output_dir=self.batch_dir,
            batch_size=200,
        )
        batch_path = Path(manifest["batches"][0]["path"])
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        batch["status"] = "in_progress"
        batch["review_started_at"] = datetime.now(timezone.utc).isoformat()
        batch["reviewed_by_current_model"] = False
        batch["semantic_fields_generated_by_script"] = False
        batch_path.write_text(
            json.dumps(batch, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "status=reviewed"):
            GATE.apply_batch(
                writing_receipt=self.writing_receipt,
                source_receipt=self.source_receipt,
                batch_path=batch_path,
            )


if __name__ == "__main__":
    unittest.main()
