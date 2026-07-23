from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_final_artifact_bindings.py"
)
SPEC = importlib.util.spec_from_file_location("final_artifact_bindings", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class FinalArtifactBindingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "book"
        self.assets = self.project / "写作资产"
        self.text = self.project / "正文.md"
        (self.assets / "正式审计").mkdir(parents=True)
        (self.assets / "原文对照审计").mkdir(parents=True)
        self.text.write_text("# 测试\n\n1.\n正文。\n", encoding="utf-8")
        self.write_bound_artifacts()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, relative: str, data: dict) -> None:
        path = self.assets / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def binding(self) -> dict:
        return {
            "path": str(self.text.resolve()),
            "sha256": GATE.sha256(self.text),
        }

    def write_bound_artifacts(self) -> None:
        binding = self.binding()
        self.write_json(
            "规则执行台账.json",
            {
                "gate_status": "passed",
                "artifacts": [
                    {
                        "name": "正文",
                        "path": binding["path"],
                        "sha256": binding["sha256"],
                    }
                ]
            },
        )
        self.write_json(
            "开头承重契约回执_正文.json",
            {"gate_status": "passed", "target_text": binding},
        )
        self.write_json(
            "窗口前定向回修回执.json",
            {"status": "completed", "text": binding},
        )
        self.write_json(
            "人工模型分段任务.json",
            {
                "status": "completed",
                "source": binding,
                "cross_section_block_shape_review": {"status": "completed"},
            },
        )
        self.write_json(
            "顺序契约回执.json",
            {"gate_status": "passed", "artifacts": {"draft": binding}},
        )
        self.write_json("局部生硬候选报告.json", {"text": binding})
        self.write_json("正式审计/正文.full_audit.json", {"text": binding})
        self.write_json(
            "写后人工语义复核回执.json",
            {"gate_status": "passed", "text": binding},
        )
        self.write_json(
            "原文对照审计/基线对照.json",
            {
                "draft": {
                    "file": binding["path"],
                    "text_sha256": binding["sha256"],
                }
            },
        )

    def test_all_current_bindings_pass(self) -> None:
        result = GATE.validate_project(self.project, self.text, imitation_mode=True)
        self.assertEqual("passed", result["gate_status"])
        self.assertEqual([], result["rebuild_order"])

    def test_text_change_lists_every_stale_artifact_in_dependency_order(self) -> None:
        self.text.write_text("# 测试\n\n1.\n正文变了。\n", encoding="utf-8")
        result = GATE.validate_project(self.project, self.text, imitation_mode=True)
        self.assertEqual("blocked", result["gate_status"])
        self.assertEqual(
            [
                "opening_contract",
                "sequence_contract",
                "rule_execution_ledger",
                "pre_window_revision",
                "model_segmentation",
                "local_stiffness_audit",
                "formal_audit",
                "source_baseline_audit",
                "post_write_human_review",
            ],
            result["rebuild_order"],
        )

    def test_legacy_formal_audit_without_text_binding_is_blocked(self) -> None:
        self.write_json("正式审计/正文.full_audit.json", {"file": str(self.text)})
        result = GATE.validate_project(self.project, self.text, imitation_mode=True)
        formal = next(
            item for item in result["artifacts"] if item["label"] == "formal_audit"
        )
        self.assertEqual("blocked", formal["status"])
        self.assertIn("绑定读取失败", formal["errors"][0])

    def test_pending_post_write_review_is_blocked_even_when_sha_matches(self) -> None:
        binding = self.binding()
        self.write_json(
            "写后人工语义复核回执.json",
            {"gate_status": "pending", "text": binding},
        )
        result = GATE.validate_project(self.project, self.text, imitation_mode=True)
        post_review = next(
            item
            for item in result["artifacts"]
            if item["label"] == "post_write_human_review"
        )
        self.assertEqual("blocked", post_review["status"])
        self.assertIn("产物状态未通过", post_review["errors"][0])

    def test_model_segmentation_requires_cross_section_review(self) -> None:
        binding = self.binding()
        self.write_json(
            "人工模型分段任务.json",
            {"status": "completed", "source": binding},
        )
        result = GATE.validate_project(self.project, self.text, imitation_mode=True)
        segmentation = next(
            item
            for item in result["artifacts"]
            if item["label"] == "model_segmentation"
        )
        self.assertEqual("blocked", segmentation["status"])
        self.assertIn("缺少产物状态字段", segmentation["errors"][0])


if __name__ == "__main__":
    unittest.main()
