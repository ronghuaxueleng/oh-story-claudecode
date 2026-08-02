from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


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
        original = self.source / "原文" / "样本.txt"
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text(
            "资产证据：这是完整原文。动作证据。对白证据。气口证据。",
            encoding="utf-8",
        )
        subflow_card = self.source / "写作资产" / "子流程施工卡.md"
        subflow_card.write_text("# 子流程施工卡\n\nSF-01\n资产证据\n", encoding="utf-8")
        subflow_index = self.source / "写作资产" / "子流程索引.jsonl"
        subflow_index.write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "source_range": "L1-L1",
                    "entry_state": "人物带着未确认的信息入场",
                    "required_sequence": ["先观察", "再反应"],
                    "scene_granularity": "资产证据落在动作与反应中",
                    "causal_preconditions": {
                        "arrival_causes": ["双方因同一事项到场"],
                        "knowledge_boundaries": ["人物尚不知道结果"],
                        "object_lifecycle": ["证据在现场生成"],
                        "institutional_constraints": ["流程不允许中途撤回"],
                        "obvious_alternative_blockers": ["现场已经开始"],
                        "exit_cause": "证据迫使人物进入下一场",
                        "source_evidence": ["资产证据"],
                    },
                    "information_delay": "本场不提前解释结果",
                    "control_changes": ["观察权转为追问权"],
                    "emotion_sequence": ["迟疑", "刺痛"],
                    "end_state": "人物取得下一场追问依据",
                    "source_evidence": ["资产证据"],
                    "source_style_granularity": {
                        field: {
                            "analysis": f"{field} 的逐场文风分析",
                            "source_evidence": evidence,
                        }
                        for field, evidence in zip(
                            (
                                "narrative_voice_and_attitude",
                                "sentence_relation_and_rhythm",
                                "paragraph_breath_and_cut_points",
                                "dialogue_misfire_or_avoidance",
                                "action_perception_emotion_weave",
                                "narrator_interjection_and_roughness",
                            ),
                            (
                                ["资产证据", "完整原文"],
                                ["动作证据", "对白证据"],
                                ["气口证据", "完整原文"],
                                ["资产证据", "动作证据"],
                                ["对白证据", "气口证据"],
                                ["完整原文", "动作证据"],
                            ),
                        )
                    },
                },
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        covered = []
        for path in sorted(self.source.rglob("*")):
            if not path.is_file() or path.name == "book.profile.json":
                continue
            covered.append(
                {
                    "path": path.relative_to(self.source).as_posix(),
                    "sha256": GATE.sha256(path),
                }
            )
        (self.source / "book.profile.json").write_text(
            json.dumps(
                {
                    "证据词": "资产证据",
                    "source_asset_coverage": [
                        {
                            "root": str(self.source.resolve()),
                            "file_count": len(covered),
                            "files": covered,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _write_completed_receipt(self) -> dict:
        receipt, errors = GATE.create_receipt("测试项目", [self.source], writing_mode="standard")
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

    def _write_direct_imitation_package(self) -> Path:
        profile_path = self.source / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        for key in GATE.DIRECT_IMITATION_PROFILE_KEYS:
            profile.setdefault(key, [])
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        original = GATE.source_originals(self.source)[0]
        bridge = self.source / "写作资产" / "桥段施工卡.md"
        package_path = self.source / GATE.DIRECT_IMITATION_PACKAGE
        package = {
            "version": "1.1",
            "kind": "direct_imitation_semantic_package",
            "source_root": str(self.source.resolve()),
            "source_asset_manifest": profile["source_asset_coverage"][0],
            "original": {
                "path": original.relative_to(self.source).as_posix(),
                "sha256": GATE.sha256(original),
                "text": GATE.read_text(original),
            },
            "bridge_cards": {
                "path": bridge.relative_to(self.source).as_posix(),
                "sha256": GATE.sha256(bridge),
                "text": GATE.read_text(bridge),
            },
            "subflows": list(GATE.subflow_index(self.source).values()),
            "profile_assets": {
                key: profile.get(key) for key in GATE.DIRECT_IMITATION_PROFILE_KEYS
            },
        }
        package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
        return package_path

    def _complete_semantic_reviews(self, receipt: dict) -> None:
        for source in receipt["sources"]:
            for contract in source["selected_subflow_contracts"]:
                contract["semantic_read_review"] = {
                    "status": "read",
                    "consumption_scope": "full_subflow",
                    "source_quote_evidence": ["资产证据", "完整原文"],
                    "event_flow_takeaway": "事件必须完整保留先观察再反应的连续顺序。",
                    "emotion_flow_takeaway": "情绪必须从迟疑推进到刺痛，不能压成结论。",
                    "style_granularity_takeaway": "动作、感知和反应要织在同一连续气口里。",
                    "planned_use": "整条映射进细纲，并在正文逐节重读对应切片。",
                    "manual_judgment": "已逐项读取本 SF 的事件、情绪、因果与文风字段。",
                }

    def test_pending_receipt_is_blocked(self) -> None:
        receipt, errors = GATE.create_receipt("测试项目", [self.source], writing_mode="standard")
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
        self.assertEqual(len(GATE.MAIN_COMPILED_FILES) + 1, summary["read_count"])

    def test_receipt_without_explicit_writing_mode_is_blocked(self) -> None:
        receipt = self._write_completed_receipt()
        receipt.pop("writing_mode")
        self.receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        validation_errors, _ = GATE.validate_receipt(self.receipt_path)
        self.assertTrue(any("缺少 writing_mode" in error for error in validation_errors))

    def test_compiled_inventory_is_smaller_than_full_inventory(self) -> None:
        compiled, compiled_errors = GATE.discover_inventory(self.source)
        full, full_errors = GATE.discover_inventory(self.source, inventory_mode="full")
        self.assertEqual([], compiled_errors)
        self.assertEqual([], full_errors)
        self.assertLess(len(compiled), len(full))

    def test_direct_imitation_uses_one_semantic_package_not_full_inventory(self) -> None:
        self._write_direct_imitation_package()
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertEqual([], errors)
        source = receipt["sources"][0]
        self.assertEqual("passed", receipt["gate_status"])
        self.assertTrue(receipt["confirmed_before_outline"])
        self.assertTrue(receipt["confirmed_before_draft"])
        self.assertEqual(["SF-01"], source["selected_subflow_ids"])
        self.assertEqual(["SF-01"], [item["subflow_id"] for item in source["selected_subflow_contracts"]])
        self.assertIsInstance(source["selected_subflow_contracts"][0]["source_style_granularity"], dict)
        self.assertNotIn("semantic_read_review", source["selected_subflow_contracts"][0])
        self.assertEqual([GATE.DIRECT_IMITATION_PACKAGE], [item["path"] for item in source["files"]])
        self.assertTrue((self.source / GATE.DIRECT_IMITATION_PACKAGE).is_file())
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        validation_errors, summary = GATE.validate_receipt(self.receipt_path)
        self.assertEqual([], validation_errors)
        self.assertEqual(1, summary["read_count"])

    def test_direct_imitation_no_longer_requires_semantic_read_review(self) -> None:
        self._write_direct_imitation_package()
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

        validation_errors, _ = GATE.validate_receipt(self.receipt_path)

        self.assertEqual([], validation_errors)

    def test_direct_imitation_blocks_semantic_review_template_reuse(self) -> None:
        review = {
            "event_flow_takeaway": "同一套事件结论",
            "emotion_flow_takeaway": "同一套情绪结论",
            "style_granularity_takeaway": "同一套文风结论",
            "manual_judgment": "同一套人工判断",
        }
        contracts = {
            f"SF-{number:02d}": {"semantic_read_review": dict(review)}
            for number in range(1, 4)
        }

        errors = GATE.validate_semantic_review_template_reuse(contracts)

        self.assertTrue(any("逐 SF 语义读取套话重复" in error for error in errors))

    def test_semantic_review_task_contains_full_excerpt_and_contract(self) -> None:
        self._write_direct_imitation_package()
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        task, task_errors = GATE.build_semantic_review_task(self.receipt_path)

        self.assertEqual([], task_errors)
        item = task["sources"][0]["subflows"][0]
        self.assertIn("资产证据：这是完整原文", item["source_excerpt"])
        self.assertEqual(
            ["先观察", "再反应"],
            item["contract"]["required_sequence"],
        )
        self.assertIn("source_style_granularity", item["contract"])

    def test_apply_semantic_review_result_atomically_completes_receipt(self) -> None:
        self._write_direct_imitation_package()
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        task, task_errors = GATE.build_semantic_review_task(self.receipt_path)
        self.assertEqual([], task_errors)
        task_path = self.receipt_path.with_name("模型语义输入.json")
        GATE.atomic_write_json(task_path, task)
        result = task["result_template"]
        result["task_sha256"] = GATE.sha256(task_path)
        result["reviews"][0]["semantic_read_review"] = {
            "status": "read",
            "consumption_scope": "full_subflow",
            "source_quote_evidence": ["资产证据", "完整原文"],
            "event_flow_takeaway": "事件完整保留先观察再反应的顺序。",
            "emotion_flow_takeaway": "情绪从迟疑推进到刺痛。",
            "style_granularity_takeaway": "动作感知反应保持同一连续气口。",
            "planned_use": "用于细纲和正文逐节迁移。",
            "manual_judgment": "已完整读取本 SF 全部原文和合同字段。",
        }
        result_path = self.receipt_path.with_name("模型语义输出.json")
        GATE.atomic_write_json(result_path, result)

        apply_errors = GATE.apply_semantic_review_result(
            self.receipt_path,
            task_path,
            result_path,
        )

        self.assertEqual([], apply_errors)
        applied = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("passed", applied["gate_status"])
        self.assertEqual(
            "read",
            applied["sources"][0]["selected_subflow_contracts"][0][
                "semantic_read_review"
            ]["status"],
        )

    def test_apply_semantic_review_result_rejects_stale_task_binding(self) -> None:
        self._write_direct_imitation_package()
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        task, task_errors = GATE.build_semantic_review_task(self.receipt_path)
        self.assertEqual([], task_errors)
        task_path = self.receipt_path.with_name("模型语义输入.json")
        GATE.atomic_write_json(task_path, task)
        result = task["result_template"]
        result["task_sha256"] = "stale"
        result_path = self.receipt_path.with_name("模型语义输出.json")
        GATE.atomic_write_json(result_path, result)

        apply_errors = GATE.apply_semantic_review_result(
            self.receipt_path,
            task_path,
            result_path,
        )

        self.assertTrue(any("任务 SHA" in error for error in apply_errors))
        unchanged = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("passed", unchanged["gate_status"])

    def test_apply_semantic_review_result_rejects_malformed_reviews_without_traceback(
        self,
    ) -> None:
        self._write_direct_imitation_package()
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        task, task_errors = GATE.build_semantic_review_task(self.receipt_path)
        self.assertEqual([], task_errors)
        task_path = self.receipt_path.with_name("模型语义输入.json")
        GATE.atomic_write_json(task_path, task)
        result = {
            "version": GATE.SEMANTIC_REVIEW_TASK_VERSION,
            "kind": GATE.SEMANTIC_REVIEW_RESULT_KIND,
            "task_sha256": GATE.sha256(task_path),
            "receipt_sha256": GATE.sha256(self.receipt_path),
            "reviews": {},
        }
        result_path = self.receipt_path.with_name("模型语义输出.json")
        GATE.atomic_write_json(result_path, result)

        apply_errors = GATE.apply_semantic_review_result(
            self.receipt_path,
            task_path,
            result_path,
        )

        self.assertTrue(any("reviews 必须是数组" in error for error in apply_errors))
        unchanged = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("passed", unchanged["gate_status"])

    def test_direct_imitation_accepts_same_directory_with_different_path_spelling(self) -> None:
        self._write_direct_imitation_package()
        profile_path = self.source / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["source_asset_coverage"][0]["root"] = "/stored/path/with/different/case"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        package_path = self.source / GATE.DIRECT_IMITATION_PACKAGE
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["source_asset_manifest"] = profile["source_asset_coverage"][0]
        package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")

        with patch.object(GATE, "same_location", return_value=True):
            receipt, errors = GATE.create_receipt(
                "测试项目",
                [self.source],
                inventory_mode="compiled",
                writing_mode="direct_imitation",
            )

        self.assertEqual([], errors)
        self.assertEqual(["SF-01"], receipt["sources"][0]["selected_subflow_ids"])

    def test_direct_imitation_prefills_selected_auxiliary_contract(self) -> None:
        self._write_direct_imitation_package()
        auxiliary = self.root / "拆文库" / "辅助"
        import shutil

        shutil.copytree(self.source, auxiliary)
        profile_path = auxiliary / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["source_asset_coverage"][0]["root"] = str(auxiliary.resolve())
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        package_path = auxiliary / GATE.DIRECT_IMITATION_PACKAGE
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["source_root"] = str(auxiliary.resolve())
        package["source_asset_manifest"]["root"] = str(auxiliary.resolve())
        package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source, auxiliary],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
            selected_subflows={"辅助": {"SF-01"}},
        )
        self.assertEqual([], errors)
        source = receipt["sources"][1]
        self.assertEqual(["SF-01"], source["selected_subflow_ids"])
        self.assertEqual("L1-L1", source["selected_subflow_contracts"][0]["source_range"])
        self.assertIsInstance(source["selected_subflow_contracts"][0]["source_style_granularity"], dict)

    def test_direct_imitation_missing_package_blocks_without_creating_it(self) -> None:
        package_path = self.source / GATE.DIRECT_IMITATION_PACKAGE
        self.assertFalse(package_path.exists())
        _, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertTrue(any("story-short-analyze finalize" in error for error in errors))
        self.assertFalse(package_path.exists())

    def test_direct_imitation_stale_package_blocks_without_rewriting_it(self) -> None:
        package_path = self._write_direct_imitation_package()
        before = package_path.read_bytes()
        original = GATE.source_originals(self.source)[0]
        original.write_text(GATE.read_text(original) + "来源变化", encoding="utf-8")
        _, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertTrue(any("已过期" in error or "文件已变化" in error for error in errors))
        self.assertEqual(before, package_path.read_bytes())

    def test_direct_imitation_v1_package_blocks(self) -> None:
        package_path = self._write_direct_imitation_package()
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["version"] = "1.0"
        package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
        _, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertTrue(any("版本过期" in error for error in errors))

    def test_direct_imitation_package_rejects_original_bound_to_workspace_root(self) -> None:
        package_path = self._write_direct_imitation_package()
        package = json.loads(package_path.read_text(encoding="utf-8"))
        detached = self.root / "原文" / "样本.txt"
        detached.parent.mkdir(parents=True, exist_ok=True)
        detached.write_text(GATE.read_text(GATE.source_originals(self.source)[0]), encoding="utf-8")
        package["original"]["path"] = str(detached.resolve())
        package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")

        _, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertTrue(any("original.path 未绑定拆文目录原文" in error for error in errors))

    def test_direct_imitation_rejects_repeated_subflow_style_templates(self) -> None:
        self._write_direct_imitation_package()
        index_path = self.source / "写作资产" / "子流程索引.jsonl"
        base = GATE.subflow_index(self.source)["SF-01"]
        variants = []
        for number in range(1, 4):
            variant = dict(base)
            variant["subflow_id"] = f"SF-{number:02d}"
            variants.append(variant)
        index_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in variants) + "\n",
            encoding="utf-8",
        )
        _, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )
        self.assertTrue(any("文风分析模板重复" in error for error in errors))

    def test_direct_imitation_rejects_one_evidence_pair_for_all_style_fields(self) -> None:
        self._write_direct_imitation_package()
        index_path = self.source / "写作资产" / "子流程索引.jsonl"
        item = GATE.subflow_index(self.source)["SF-01"]
        for style in item["source_style_granularity"].values():
            style["source_evidence"] = ["资产证据", "完整原文"]
        index_path.write_text(
            json.dumps(item, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        _, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            inventory_mode="compiled",
            writing_mode="direct_imitation",
        )

        self.assertTrue(
            any(
                "至少需要四条不同原文证据" in error
                or "文风证据组重复覆盖过多字段" in error
                for error in errors
            )
        )

    def test_auxiliary_compiled_receipt_requires_real_selected_subflow(self) -> None:
        auxiliary = self.root / "拆文库" / "辅助"
        import shutil

        shutil.copytree(self.source, auxiliary)
        profile_path = auxiliary / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["source_asset_coverage"][0]["root"] = str(auxiliary.resolve())
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        receipt, errors = GATE.create_receipt(
            "测试项目", [self.source, auxiliary], writing_mode="standard"
        )
        self.assertEqual([], errors)
        receipt["gate_status"] = "passed"
        receipt["confirmed_before_outline"] = True
        receipt["confirmed_before_draft"] = True
        receipt["cross_source_decisions"] = ["主体全流程优先，辅助只采用 SF-01。"]
        for source in receipt["sources"]:
            for item in source["files"]:
                item.update(
                    {
                        "status": "read",
                        "evidence_terms": ["资产证据"],
                        "takeaways": ["读取完整颗粒"],
                        "used_for": ["细纲"],
                    }
                )
        receipt["sources"][1]["selected_subflow_ids"] = ["SF-99"]
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        validation_errors, _ = GATE.validate_receipt(self.receipt_path)
        self.assertTrue(any("不在子流程索引" in error for error in validation_errors))

    def test_auxiliary_selected_subflow_requires_read_evidence(self) -> None:
        auxiliary = self.root / "拆文库" / "辅助"
        import shutil

        shutil.copytree(self.source, auxiliary)
        profile_path = auxiliary / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["source_asset_coverage"][0]["root"] = str(auxiliary.resolve())
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        receipt, errors = GATE.create_receipt(
            "测试项目", [self.source, auxiliary], writing_mode="standard"
        )
        self.assertEqual([], errors)
        receipt["gate_status"] = "passed"
        receipt["confirmed_before_outline"] = True
        receipt["confirmed_before_draft"] = True
        receipt["cross_source_decisions"] = ["主体全流程优先，辅助只采用 SF-01。"]
        for source in receipt["sources"]:
            for item in source["files"]:
                item.update(
                    {
                        "status": "read",
                        "evidence_terms": ["资产证据"],
                        "takeaways": ["读取完整颗粒"],
                        "used_for": ["细纲"],
                    }
                )
        receipt["sources"][1]["selected_subflow_ids"] = ["SF-01"]
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

        validation_errors, _ = GATE.validate_receipt(self.receipt_path)
        self.assertTrue(any("缺少读取证据" in error for error in validation_errors))

        for item in receipt["sources"][1]["files"]:
            if item["path"] in {
                "写作资产/子流程施工卡.md",
                "写作资产/子流程索引.jsonl",
            }:
                item["evidence_terms"].append("SF-01")
        self.receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        validation_errors, _ = GATE.validate_receipt(self.receipt_path)
        self.assertEqual([], validation_errors)

    def test_missing_asset_requires_reanalysis(self) -> None:
        (self.source / GATE.TABLE_FILES[0]).unlink()
        _, errors = GATE.create_receipt("测试项目", [self.source], writing_mode="standard")
        self.assertTrue(any("缺少拆文资产" in error for error in errors))

    def test_changed_source_requires_reread(self) -> None:
        self._write_completed_receipt()
        path = self.source / "拆文报告.md"
        path.write_text(path.read_text(encoding="utf-8") + "新增内容", encoding="utf-8")
        validation_errors, _ = GATE.validate_receipt(self.receipt_path)
        self.assertTrue(any("文件已变化" in error for error in validation_errors))

    def test_new_formal_asset_invalidates_profile_coverage(self) -> None:
        (self.source / "新增正式资产.md").write_text("新增资产", encoding="utf-8")
        _, errors = GATE.create_receipt("测试项目", [self.source], writing_mode="standard")
        self.assertTrue(any("覆盖清单缺少正式资产" in error for error in errors))

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
        _, errors = GATE.create_receipt("测试项目", [self.source], writing_mode="standard")
        self.assertTrue(any("_sample_comparison.md" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
