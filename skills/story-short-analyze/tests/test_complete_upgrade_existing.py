from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "complete_upgrade_existing.py"
SPEC = importlib.util.spec_from_file_location("complete_upgrade_existing", SCRIPT)
assert SPEC and SPEC.loader
COMPLETE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPLETE)


class CompleteUpgradeExistingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "拆文库" / "样本"
        (self.root / "原文").mkdir(parents=True)
        (self.root / "写作资产").mkdir(parents=True)
        (self.root / "原文" / "样本.txt").write_text(
            "第一行原文锚点A。\n第二行原文锚点B。\n第三行原文锚点C。\n",
            encoding="utf-8",
        )
        (self.root / "拆文报告.md").write_text("# 报告\n内容\n", encoding="utf-8")
        (self.root / "写作资产" / "桥段施工卡.md").write_text(
            "## BID-01 桥段\n内容\n",
            encoding="utf-8",
        )
        (self.root / "写作资产" / "子流程施工卡.md").write_text(
            "## SF-01 子流程\n内容\n",
            encoding="utf-8",
        )
        (self.root / "写作资产" / "子流程索引.jsonl").write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "source_book": "样本",
                    "parent_bridge_id": "BID-01",
                    "name": "测试子流程",
                    "source_range": "L1-L2",
                    "function_tags": ["照护掉位", "短问句"],
                    "entry_state": "主角带着核验目的进入现场。",
                    "required_sequence": ["先观察", "再追问", "最后确认"],
                    "scene_granularity": "先看见，再出现动作，最后补一句短问句。",
                    "causal_preconditions": {
                        "arrival_causes": ["人物因核验到场"],
                        "knowledge_boundaries": ["主角不知道全部后果"],
                        "object_lifecycle": ["物件在现场进入视野"],
                        "institutional_constraints": ["公开场合限制立刻翻脸"],
                        "obvious_alternative_blockers": ["电话看不见现场"],
                        "exit_cause": "确认掉位后转入下一场追问。",
                        "source_evidence": ["第一行原文锚点A。", "第二行原文锚点B。"],
                    },
                    "information_delay": "先给异常，再给关系判断。",
                    "control_changes": ["观察权转为追问权"],
                    "emotion_sequence": ["迟疑", "刺痛", "发冷"],
                    "end_state": "主角确认当前站位已经改变。",
                    "embeddable_after": ["前置核验场"],
                    "incompatible_with": ["开场已知全部真相"],
                    "source_evidence": ["第一行原文锚点A。", "第二行原文锚点B。"],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.root / "_progress.md").write_text(
            "## 增量升级复核\n"
            "- [ ] 模型人工复核：finalize前已读取脚本结果并完成最后语义纠偏\n"
            "- [ ] 模型人工复核：高敏桥与BID情绪贯通已逐项复核\n"
            "- [ ] 模型人工复核：profile_source 与 book.profile 迁移字段已重核\n"
            "- [ ] 模型人工复核：human_review_items 已逐条裁决并落盘\n"
            "- [ ] 已运行 `run_short_analyze_finalize.py` 并通过\n",
            encoding="utf-8",
        )
        (self.root / "_parallel_plan.json").write_text('{"ok": true}', encoding="utf-8")
        (self.root / "_upgrade_plan.md").write_text("# 升级计划\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_process_root_rejects_missing_style_without_fabricating_assets(self) -> None:
        payload = COMPLETE.process_root(self.root)
        self.assertEqual("needs_model_reanalysis", payload["status"])
        self.assertEqual(["SF-01"], payload["missing_source_style_subflows"])
        self.assertEqual(1, payload["style_reanalysis_task_count"])
        task_payload = json.loads(
            (self.root / "_style_reanalysis_tasks.json").read_text(encoding="utf-8")
        )
        task = task_payload["tasks"][0]
        self.assertEqual("SF-01", task["subflow_id"])
        self.assertEqual("L1-L2", task["source_range"])
        self.assertEqual(
            "第一行原文锚点A。\n第二行原文锚点B。",
            task["source_excerpt"],
        )
        self.assertEqual(list(COMPLETE.STYLE_FIELDS), task["required_style_fields"])
        data = [
            json.loads(line)
            for line in (self.root / "写作资产" / "子流程索引.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][0]
        self.assertNotIn("source_style_granularity", data)
        self.assertFalse((self.root / "_finalize_human_review.json").exists())
        progress = (self.root / "_progress.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] 模型人工复核", progress)

    def test_process_root_rejects_legacy_style_template(self) -> None:
        index_path = self.root / "写作资产" / "子流程索引.jsonl"
        entry = json.loads(index_path.read_text(encoding="utf-8"))
        entry["source_style_granularity"] = {
            field: {
                "analysis": COMPLETE.LEGACY_TEMPLATE_MARKER,
                "source_evidence": ["第一行原文锚点A。", "第二行原文锚点B。"],
            }
            for field in COMPLETE.STYLE_FIELDS
        }
        index_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
        payload = COMPLETE.process_root(self.root)
        self.assertEqual(["SF-01"], payload["templated_source_style_subflows"])
        task_payload = json.loads(
            (self.root / "_style_reanalysis_tasks.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            any("legacy_templated" in reason for reason in task_payload["tasks"][0]["reasons"])
        )

    def test_process_root_ready_removes_stale_task_without_touching_index(self) -> None:
        index_path = self.root / "写作资产" / "子流程索引.jsonl"
        entry = json.loads(index_path.read_text(encoding="utf-8"))
        entry["source_style_granularity"] = {
            field: {
                "analysis": f"{field} 对应本场独立分析。",
                "source_evidence": ["第一行原文锚点A。", "第二行原文锚点B。"],
            }
            for field in COMPLETE.STYLE_FIELDS
        }
        expected = json.dumps(entry, ensure_ascii=False) + "\n"
        index_path.write_text(expected, encoding="utf-8")
        (self.root / "_style_reanalysis_tasks.json").write_text(
            '{"tasks": [{"subflow_id": "stale"}]}\n',
            encoding="utf-8",
        )

        payload = COMPLETE.process_root(self.root)

        self.assertEqual("ready_for_finalize", payload["status"])
        self.assertEqual(0, payload["style_reanalysis_task_count"])
        self.assertIsNone(payload["style_reanalysis_task_file"])
        self.assertFalse((self.root / "_style_reanalysis_tasks.json").exists())
        self.assertEqual(expected, index_path.read_text(encoding="utf-8"))

    def test_process_root_routes_cross_subflow_repeated_analysis_to_reanalysis(self) -> None:
        index_path = self.root / "写作资产" / "子流程索引.jsonl"
        base = json.loads(index_path.read_text(encoding="utf-8"))
        entries = []
        for number in range(1, 4):
            entry = dict(base)
            entry["subflow_id"] = f"SF-{number:02d}"
            entry["source_style_granularity"] = {
                field: {
                    "analysis": f"跨场复用的 {field} 分析。",
                    "source_evidence": ["第一行原文锚点A。", "第二行原文锚点B。"],
                }
                for field in COMPLETE.STYLE_FIELDS
            }
            entries.append(json.dumps(entry, ensure_ascii=False))
        index_path.write_text("\n".join(entries) + "\n", encoding="utf-8")

        payload = COMPLETE.process_root(self.root)

        self.assertEqual(["SF-01", "SF-02", "SF-03"], payload["templated_source_style_subflows"])
        self.assertEqual(3, payload["style_reanalysis_task_count"])
        tasks = json.loads(
            (self.root / "_style_reanalysis_tasks.json").read_text(encoding="utf-8")
        )["tasks"]
        self.assertTrue(
            all("cross_subflow_repeated_style_analysis" in task["reasons"] for task in tasks)
        )

    def test_process_root_blocks_incomplete_style_even_without_legacy_marker(self) -> None:
        index_path = self.root / "写作资产" / "子流程索引.jsonl"
        entry = json.loads(index_path.read_text(encoding="utf-8"))
        entry["source_style_granularity"] = {
            field: {
                "analysis": f"{field} 对应本场独立分析。",
                "source_evidence": ["第一行原文锚点A。", "第二行原文锚点B。"],
            }
            for field in COMPLETE.STYLE_FIELDS[:-1]
        }
        index_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

        payload = COMPLETE.process_root(self.root)

        self.assertEqual("needs_model_reanalysis", payload["status"])
        task = json.loads(
            (self.root / "_style_reanalysis_tasks.json").read_text(encoding="utf-8")
        )["tasks"][0]
        self.assertIn(
            "missing_style_field:narrator_interjection_and_roughness",
            task["reasons"],
        )

    def test_source_slice_supports_multi_ranges(self) -> None:
        lines = ["一", "二", "三", "四", "五"]
        self.assertEqual("一\n二\n四\n五", COMPLETE.source_slice(lines, "L1-L2、L4-L5"))


if __name__ == "__main__":
    unittest.main()
