from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_direct_imitation_package.py"
SPEC = importlib.util.spec_from_file_location("direct_imitation_package", SCRIPT)
assert SPEC and SPEC.loader
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)

FINALIZE_SCRIPT = SCRIPT.with_name("run_short_analyze_finalize.py")
FINALIZE_SPEC = importlib.util.spec_from_file_location("short_analyze_finalize", FINALIZE_SCRIPT)
assert FINALIZE_SPEC and FINALIZE_SPEC.loader
FINALIZE = importlib.util.module_from_spec(FINALIZE_SPEC)
FINALIZE_SPEC.loader.exec_module(FINALIZE)


class DirectImitationPackageTest(unittest.TestCase):
    def refresh_profile_coverage(self) -> None:
        profile_path = self.root / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        files = []
        for path in sorted(self.root.rglob("*")):
            if (
                not path.is_file()
                or path.name == "book.profile.json"
                or (
                    path.parent == self.root
                    and path.name.startswith("_")
                    and path.name != "_sample_comparison.md"
                )
                or path.relative_to(self.root).as_posix() == PACKAGE.PACKAGE_RELATIVE_PATH
            ):
                continue
            files.append({
                "path": path.relative_to(self.root).as_posix(),
                "sha256": PACKAGE.sha256(path),
            })
        profile["source_asset_coverage"] = [{
            "root": str(self.root.resolve()),
            "file_count": len(files),
            "files": files,
        }]
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "拆文库" / "样本"
        (self.root / "原文").mkdir(parents=True)
        (self.root / "写作资产").mkdir(parents=True)
        (self.root / "原文" / "样本.txt").write_text("唯一完整原文。", encoding="utf-8")
        (self.root / "拆文报告.md").write_text("# 拆文报告\n", encoding="utf-8")
        (self.root / "写作资产" / "桥段施工卡.md").write_text("# BID-01\n承重桥。\n", encoding="utf-8")
        self.subflow = {
            "subflow_id": "SF-01",
            "source_range": "L1-L1",
            "entry_state": "误判尚未证实",
            "required_sequence": ["看见", "追问", "翻刀"],
            "scene_granularity": "动作与错答同场发生",
            "causal_preconditions": {
                "arrival_causes": ["双方因同一公开事项到场"],
                "knowledge_boundaries": ["主角入场前不知道对方已改口径"],
                "object_lifecycle": ["证据在现场生成并由主角持有"],
                "institutional_constraints": ["现场流程不允许私下撤回记录"],
                "obvious_alternative_blockers": ["公开流程已开始，无法改日处理"],
                "exit_cause": "事实公开后关系进入下一轮清算",
                "source_evidence": ["唯一完整原文", "承重桥"],
            },
            "information_delay": "先给异常，后给事实",
            "control_changes": ["观察权转为质问权"],
            "emotion_sequence": ["迟疑", "刺痛", "决断"],
            "end_state": "关系进入不可逆状态",
            "source_evidence": ["唯一完整原文"],
            "source_style_granularity": {
                field: {
                    "analysis": f"{field} 的逐场分析",
                    "source_evidence": ["唯一完整", "完整原文"],
                }
                for field in PACKAGE.STYLE_GRANULARITY_FIELDS
            },
        }
        self.index_path = self.root / "写作资产" / "子流程索引.jsonl"
        self.index_path.write_text(json.dumps(self.subflow, ensure_ascii=False) + "\n", encoding="utf-8")
        PACKAGE.FINGERPRINTS.write_manifest(self.root, excluded_names=frozenset())
        profile = {key: [f"{key}-asset"] for key in PACKAGE.PROFILE_ASSET_KEYS}
        profile["scene_assets"] = {"public_explosion": ["公开翻刀"]}
        profile["style_assets"] = {"sentence_rhythm": ["短句追压"]}
        profile["migration_assets"] = {"object_swaps": ["物件迁移"]}
        profile["story_guardrails"] = {"must_keep": ["不可逆后果"]}
        profile["sample_grading"] = {"grade": "A"}
        files = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and not (
                path.parent == self.root
                and path.name.startswith("_")
                and path.name != "_sample_comparison.md"
            ):
                files.append({
                    "path": path.relative_to(self.root).as_posix(),
                    "sha256": PACKAGE.sha256(path),
                })
        profile["source_asset_coverage"] = [{
            "root": str(self.root.resolve()),
            "file_count": len(files),
            "files": files,
        }]
        (self.root / "book.profile.json").write_text(
            json.dumps(profile, ensure_ascii=False), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_contains_exact_original_subflows_and_profile_assets(self) -> None:
        output = PACKAGE.build_package(self.root)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("唯一完整原文。", data["original"]["text"])
        self.assertEqual([self.subflow], data["subflows"])
        profile = json.loads((self.root / "book.profile.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {key: profile[key] for key in PACKAGE.PROFILE_ASSET_KEYS},
            data["profile_assets"],
        )
        manifest_paths = {item["path"] for item in data["source_asset_manifest"]["files"]}
        self.assertNotIn(PACKAGE.PACKAGE_RELATIVE_PATH, manifest_paths)
        self.assertEqual([], PACKAGE.validate_package(self.root))

    def test_source_or_subflow_change_invalidates_without_rewriting(self) -> None:
        output = PACKAGE.build_package(self.root)
        before = output.read_bytes()
        self.index_path.write_text(
            json.dumps({**self.subflow, "end_state": "新的不可逆状态"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        errors = PACKAGE.validate_package(self.root)
        self.assertTrue(any("SF" in error or "source_asset_coverage" in error for error in errors))
        self.assertEqual(before, output.read_bytes())

    def test_bom_and_newline_changes_do_not_invalidate_package(self) -> None:
        PACKAGE.build_package(self.root)
        (self.root / "原文" / "样本.txt").write_bytes(
            "\ufeff唯一完整原文。".encode("utf-8")
        )
        (self.root / "写作资产" / "桥段施工卡.md").write_bytes(
            "\ufeff# BID-01\r\n承重桥。\r\n".encode("utf-8")
        )
        self.assertEqual([], PACKAGE.validate_package(self.root))

    def test_v1_package_is_rejected(self) -> None:
        output = PACKAGE.build_package(self.root)
        data = json.loads(output.read_text(encoding="utf-8"))
        data["version"] = "1.0"
        output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = PACKAGE.validate_package(self.root)
        self.assertTrue(any("版本过期" in error for error in errors))

    def test_empty_causal_assets_blocks_generation(self) -> None:
        profile_path = self.root / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["causal_precondition_assets"] = []
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "causal_precondition_assets"):
            PACKAGE.build_package(self.root)

    def test_missing_subflow_style_blocks_package(self) -> None:
        value = dict(self.subflow)
        value.pop("source_style_granularity")
        self.index_path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source_style_granularity"):
            PACKAGE.build_package(self.root)

    def test_multi_range_source_style_is_supported(self) -> None:
        original = self.root / "原文" / "样本.txt"
        original.write_text("第一行原文\n第二行原文\n第三行原文\n第四行原文\n", encoding="utf-8")
        value = dict(self.subflow)
        value["source_range"] = "L1-L2、L4-L4"
        value["source_evidence"] = ["第一行原文", "第四行原文"]
        value["causal_preconditions"] = dict(self.subflow["causal_preconditions"])
        value["causal_preconditions"]["source_evidence"] = ["第一行原文", "第四行原文"]
        value["source_style_granularity"] = {
            field: {
                "analysis": f"{field} 的逐场分析",
                "source_evidence": ["第一行原文", "第四行原文"],
            }
            for field in PACKAGE.STYLE_GRANULARITY_FIELDS
        }
        self.index_path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
        self.refresh_profile_coverage()
        PACKAGE.build_package(self.root)
        self.assertEqual([], PACKAGE.validate_package(self.root))

    def test_finalize_failure_removes_generated_package(self) -> None:
        finalize = SCRIPT.with_name("run_short_analyze_finalize.py")
        result = subprocess.run(
            [sys.executable, str(finalize), str(self.root), "--skip-profile", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.root / PACKAGE.PACKAGE_RELATIVE_PATH).exists())
        payload = json.loads(result.stdout)
        self.assertTrue(any("已撤销" in note for note in payload["notes"]))

    def test_finalize_reports_full_validation_when_package_build_fails(self) -> None:
        profile_path = self.root / "book.profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["causal_precondition_assets"] = []
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        finalize = SCRIPT.with_name("run_short_analyze_finalize.py")
        result = subprocess.run(
            [sys.executable, str(finalize), str(self.root), "--skip-profile", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertTrue(any("编译包生成失败" in error for error in payload["errors"]))
        self.assertTrue(any("缺少文件" in error for error in payload["errors"]))
        self.assertGreater(payload["error_count"], 2)

    def test_validator_abnormal_exit_removes_generated_package(self) -> None:
        package_path = self.root / PACKAGE.PACKAGE_RELATIVE_PATH

        def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
            if "build_direct_imitation_package.py" in command[1]:
                package_path.write_text("{}", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "{}", "")
            return subprocess.CompletedProcess(command, 3, "", "validator crashed")

        argv = ["finalize", str(self.root), "--skip-profile", "--json"]
        with mock.patch.object(FINALIZE, "run_command", side_effect=fake_run), mock.patch.object(sys, "argv", argv):
            self.assertEqual(2, FINALIZE.main())
        self.assertFalse(package_path.exists())

    def test_library_failure_removes_generated_package(self) -> None:
        package_path = self.root / PACKAGE.PACKAGE_RELATIVE_PATH

        def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
            script = command[1]
            if "build_direct_imitation_package.py" in script:
                package_path.write_text("{}", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "{}", "")
            if "validate_short_analyze_outputs.py" in script:
                payload = {
                    "ok": True,
                    "status": "ready-for-write",
                    "error_count": 0,
                    "errors": [],
                    "notes": [],
                    "human_review_items": [],
                }
                return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
            return subprocess.CompletedProcess(command, 2, "", "library failed")

        argv = ["finalize", str(self.root), "--skip-profile", "--json"]
        with mock.patch.object(FINALIZE, "run_command", side_effect=fake_run), mock.patch.object(sys, "argv", argv):
            self.assertEqual(2, FINALIZE.main())
        self.assertFalse(package_path.exists())


if __name__ == "__main__":
    unittest.main()
