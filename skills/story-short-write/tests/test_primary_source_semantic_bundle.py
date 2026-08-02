from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = load_module("source_read_gate", "validate_source_read_gate.py")
BUNDLE = load_module(
    "build_primary_source_semantic_bundle", "build_primary_source_semantic_bundle.py"
)


class PrimarySourceSemanticBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "拆文库" / "样本"
        self.receipt_path = self.root / "项目" / "写作资产" / "拆文读取回执.json"
        self.bundle_path = self.root / "项目" / "写作资产" / "主体原文完整颗粒包.json"
        self._build_complete_source()
        self._write_direct_imitation_package()
        self._write_direct_imitation_receipt()
        self._cwd = Path.cwd()

    def tearDown(self) -> None:
        os.chdir(self._cwd)
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
        bridge = self.source / "写作资产" / "桥段施工卡.md"
        bridge.write_text("# 桥段施工卡\n\nBID-01\n资产证据\n", encoding="utf-8")
        subflow_index = self.source / "写作资产" / "子流程索引.jsonl"
        subflow_index.write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "name": "样本子流程",
                    "parent_bridge_id": "BID-01",
                    "source_book": "样本",
                    "source_range": "L1-L1",
                    "source_excerpt": "资产证据：这是完整原文。动作证据。对白证据。气口证据。",
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
                    "function_tags": ["验证", "刺痛"],
                    "source_evidence": ["资产证据"],
                    "source_style_granularity": {
                        field: {
                            "analysis": f"{field} 的逐场文风分析",
                            "source_evidence": evidence,
                        }
                        for field, evidence in zip(
                            GATE.STYLE_GRANULARITY_FIELDS,
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
            )
            + "\n",
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
        profile = {"证据词": "资产证据", "source_asset_coverage": []}
        for key in GATE.DIRECT_IMITATION_PROFILE_KEYS:
            profile[key] = ["资产证据"]
        profile["source_asset_coverage"] = [
            {
                "root": str(self.source.resolve()),
                "file_count": len(covered),
                "files": covered,
            }
        ]
        (self.source / "book.profile.json").write_text(
            json.dumps(profile, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_direct_imitation_package(self) -> None:
        original = GATE.source_originals(self.source)[0]
        bridge = self.source / "写作资产" / "桥段施工卡.md"
        profile = json.loads((self.source / "book.profile.json").read_text(encoding="utf-8"))
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
        package_path = self.source / GATE.DIRECT_IMITATION_PACKAGE
        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")

    def _write_direct_imitation_receipt(self) -> None:
        receipt, errors = GATE.create_receipt(
            "测试项目",
            [self.source],
            writing_mode="direct_imitation",
        )
        self.assertEqual([], errors)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_create_bundle_accepts_package_extra_fields(self) -> None:
        os.chdir(self.root)
        bundle, errors = BUNDLE.create_bundle(self.receipt_path)
        self.assertEqual([], errors)
        self.assertEqual("primary_source_semantic_bundle", bundle["kind"])
        self.assertEqual("SF-01", bundle["subflows"][0]["subflow_id"])

    def test_validate_bundle_accepts_package_extra_fields(self) -> None:
        os.chdir(self.root)
        bundle, errors = BUNDLE.create_bundle(self.receipt_path)
        self.assertEqual([], errors)
        self.bundle_path.parent.mkdir(parents=True, exist_ok=True)
        self.bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        validation_errors = BUNDLE.validate_bundle(self.bundle_path)
        self.assertEqual([], validation_errors)

    def test_create_bundle_can_skip_duplicate_source_receipt_validation(self) -> None:
        os.chdir(self.root)
        with patch.object(
            BUNDLE.SOURCE_READ,
            "validate_receipt",
            side_effect=AssertionError("不应重复复验 source_receipt"),
        ):
            bundle, errors = BUNDLE.create_bundle(
                self.receipt_path,
                validate_source_receipt=False,
            )
        self.assertEqual([], errors)
        self.assertEqual("primary_source_semantic_bundle", bundle["kind"])

    def test_validate_bundle_can_skip_duplicate_source_receipt_validation(self) -> None:
        os.chdir(self.root)
        bundle, errors = BUNDLE.create_bundle(self.receipt_path)
        self.assertEqual([], errors)
        self.bundle_path.parent.mkdir(parents=True, exist_ok=True)
        self.bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch.object(
            BUNDLE.SOURCE_READ,
            "validate_receipt",
            side_effect=AssertionError("不应重复复验 source_receipt"),
        ):
            validation_errors = BUNDLE.validate_bundle(
                self.bundle_path,
                validate_source_receipt=False,
            )
        self.assertEqual([], validation_errors)

    def test_create_bundle_rejects_package_original_outside_source_root(self) -> None:
        package_path = self.source / GATE.DIRECT_IMITATION_PACKAGE
        package = json.loads(package_path.read_text(encoding="utf-8"))
        detached = self.root / "原文" / "样本.txt"
        detached.parent.mkdir(parents=True, exist_ok=True)
        detached.write_text(
            "资产证据：这是完整原文。动作证据。对白证据。气口证据。",
            encoding="utf-8",
        )
        package["original"]["path"] = str(detached.resolve())
        package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")

        os.chdir(self.root)
        bundle, errors = BUNDLE.create_bundle(self.receipt_path)
        self.assertEqual({}, bundle)
        self.assertTrue(
            any(
                "必须使用拆文目录原文" in error
                or "original.path 未绑定拆文目录原文" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
