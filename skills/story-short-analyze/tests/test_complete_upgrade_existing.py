from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


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
        entry = {
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
                }
        entry["source_style_granularity"] = {
            field: {
                "analysis": f"{field} 的逐场人工分析。",
                "source_evidence": ["第一行原文锚点A。", "第二行原文锚点B。"],
            }
            for field in COMPLETE.STYLE_FIELDS
        }
        (self.root / "写作资产" / "子流程索引.jsonl").write_text(
            json.dumps(entry, ensure_ascii=False)
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

    def test_process_root_validates_style_and_requires_explicit_decisions(self) -> None:
        receipt_path = self.root / "_finalize_human_review.json"
        receipt = {
            "upgrade_status": "pending_content_review",
            "upgrade_reviews": [
                {"scope": scope, "status": "pending", "judgement": "", "evidence": []}
                for scope in ("process_plan_refresh", "content_contract_review", "profile_regeneration")
            ],
            "review_items": [
                {"id": "HR-TEST", "status": "pending", "judgement": "", "evidence": []}
            ],
        }
        decisions = {
            "upgrade_reviews": {
                scope: {
                    "status": "resolved",
                    "judgement": f"已人工复核 {scope} 对应内容。",
                    "evidence": ["_upgrade_plan.md"],
                }
                for scope in ("process_plan_refresh", "content_contract_review", "profile_regeneration")
            },
            "review_items": {
                "HR-TEST": {
                    "status": "not_applicable",
                    "judgement": "已读取上下文，确认这是关键词误报。",
                    "evidence": ["拆文报告.md:2"],
                }
            },
        }
        with mock.patch.object(COMPLETE.SYNC, "sync_receipt", return_value=(receipt_path, receipt, False)):
            payload = COMPLETE.process_root(self.root, decisions)
        self.assertEqual(1, payload["style_validation"]["checked"])
        data = [
            json.loads(line)
            for line in (self.root / "写作资产" / "子流程索引.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][0]
        style = data["source_style_granularity"]
        self.assertEqual(set(COMPLETE.STYLE_FIELDS), set(style))
        for field in COMPLETE.STYLE_FIELDS:
            self.assertEqual(
                ["第一行原文锚点A。", "第二行原文锚点B。"],
                style[field]["source_evidence"],
            )
            self.assertTrue(style[field]["analysis"])

        receipt = json.loads((self.root / "_finalize_human_review.json").read_text(encoding="utf-8"))
        self.assertEqual("completed", receipt["upgrade_status"])
        self.assertTrue(all(item["status"] == "resolved" for item in receipt["upgrade_reviews"]))
        self.assertEqual("not_applicable", receipt["review_items"][0]["status"])

        progress = (self.root / "_progress.md").read_text(encoding="utf-8")
        self.assertNotIn("- [ ] 模型人工复核", progress)
        self.assertIn("- [x] 已运行 `run_short_analyze_finalize.py` 并通过", progress)

    def test_missing_review_decision_is_blocked(self) -> None:
        payload = {
            "upgrade_reviews": [],
            "review_items": [{"id": "HR-TEST", "status": "pending"}],
        }
        with self.assertRaisesRegex(ValueError, "HR-TEST"):
            COMPLETE.apply_review_decisions(
                payload,
                {"upgrade_reviews": {}, "review_items": {}},
            )

    def test_missing_style_is_blocked_without_mutating_index(self) -> None:
        path = self.root / "写作资产" / "子流程索引.jsonl"
        entry = json.loads(path.read_text(encoding="utf-8"))
        entry.pop("source_style_granularity")
        original = json.dumps(entry, ensure_ascii=False) + "\n"
        path.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "缺少 source_style_granularity"):
            COMPLETE.validate_subflow_style(self.root)
        self.assertEqual(original, path.read_text(encoding="utf-8"))

    def test_cli_requires_explicit_review_decisions_file(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.root), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("--review-decisions", result.stderr)

    def test_source_slice_supports_multi_ranges(self) -> None:
        lines = ["一", "二", "三", "四", "五"]
        self.assertEqual("一\n二\n四\n五", COMPLETE.source_slice(lines, "L1-L2、L4-L5"))


if __name__ == "__main__":
    unittest.main()
