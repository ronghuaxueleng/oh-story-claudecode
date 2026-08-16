from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "scripts/init_project_writing_assets.py"
PLAN = ROOT / "scripts/create_section_plan.py"
POLICY = ROOT / "scripts/apply_project_profile_policy.py"


class ProjectWritingAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_init_creates_pending_manual_assets(self) -> None:
        project = self.root / "测试书"
        project.mkdir()
        result = self.run_script(
            INIT, "--project-dir", str(project), "--project-name", "测试书"
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        assets = project / "写作资产"
        beat = json.loads((assets / "逐拍语义映射.json").read_text(encoding="utf-8"))
        scene = json.loads((assets / "逐场语义映射.json").read_text(encoding="utf-8"))
        self.assertEqual("pending", beat["status"])
        self.assertEqual([], beat["emotions"])
        self.assertEqual("pending", scene["status"])
        self.assertEqual({}, scene["scenes"])

    def test_init_prechecks_all_targets_before_writing(self) -> None:
        project = self.root / "测试书"
        assets = project / "写作资产"
        assets.mkdir(parents=True)
        (assets / "逐场语义映射.json").write_text("{}", encoding="utf-8")
        result = self.run_script(
            INIT, "--project-dir", str(project), "--project-name", "测试书"
        )
        self.assertEqual(2, result.returncode)
        self.assertFalse((assets / "项目写作配置.json").exists())
        self.assertFalse((assets / "逐拍语义映射.json").exists())

    def test_section_plan_stores_scene_refs_instead_of_copying_scene_units(self) -> None:
        receipt = self.root / "receipt.json"
        output = self.root / "plan.json"
        units = [{"scene_id": "S1-1", "allocated_chars": 800}]
        receipt.write_text(
            json.dumps({"gate_status": "passed", "sections": [{"section_id": "1", "scene_units": units}]}),
            encoding="utf-8",
        )
        result = self.run_script(
            PLAN, "--receipt", str(receipt), "--section", "1", "--output", str(output)
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        plan = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual([{"scene_id": "S1-1", "emotion_beat_ids": [], "target_emotion_beat_ids": [], "plot_beat_ids": []}], plan["scene_unit_refs"])
        self.assertNotIn("scene_units", plan)
        self.assertEqual(800, plan["target_chars"])

    def test_section_plan_maps_target_emotion_ids_by_explicit_semantic_mapping(self) -> None:
        receipt = self.root / "receipt.json"
        mapping = self.root / "mapping.json"
        output = self.root / "plan.json"
        units = [{"scene_id": "S1-1", "emotion_beat_ids": ["TE-X"], "allocated_chars": 800}]
        receipt.write_text(
            json.dumps({"gate_status": "passed", "sections": [{"section_id": "1", "scene_units": units}]}),
            encoding="utf-8",
        )
        mapping.write_text(
            json.dumps({"status": "approved", "emotions": [{"source_beat_id": "E-009", "target_beat_id": "TE-X"}]}),
            encoding="utf-8",
        )
        result = self.run_script(
            PLAN, "--receipt", str(receipt), "--section", "1", "--output", str(output),
            "--beat-mapping", str(mapping),
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        plan = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(["E-009"], plan["scene_unit_refs"][0]["emotion_beat_ids"])
        self.assertEqual(["TE-X"], plan["scene_unit_refs"][0]["target_emotion_beat_ids"])

    def test_section_plan_blocks_target_emotion_ids_without_mapping(self) -> None:
        receipt = self.root / "receipt.json"
        output = self.root / "plan.json"
        receipt.write_text(
            json.dumps({"gate_status": "passed", "sections": [{"section_id": "1", "scene_units": [{"scene_id": "S1-1", "emotion_beat_ids": ["TE-X"], "allocated_chars": 800}]}]}),
            encoding="utf-8",
        )
        result = self.run_script(
            PLAN, "--receipt", str(receipt), "--section", "1", "--output", str(output)
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("--beat-mapping", result.stdout)

    def test_compact_plan_can_be_materialized_from_upstream_scene_units(self) -> None:
        plan_module = importlib.util.spec_from_file_location("create_section_plan", PLAN)
        assert plan_module and plan_module.loader
        module = importlib.util.module_from_spec(plan_module)
        plan_module.loader.exec_module(module)
        plan = {
            "section_id": "1",
            "scene_unit_refs": [
                {
                    "scene_id": "S1-1",
                    "emotion_beat_ids": ["E-001"],
                    "target_emotion_beat_ids": [],
                    "plot_beat_ids": ["P-001"],
                }
            ],
        }
        expanded = module.materialize_plan(
            plan,
            [{"scene_id": "S1-1", "allocated_chars": 800}],
        )
        self.assertEqual(800, expanded["scene_units"][0]["allocated_chars"])

    def test_profile_policy_uses_configured_sources(self) -> None:
        profile = self.root / "project.profile.json"
        primary = self.root / "primary.json"
        auxiliary = self.root / "auxiliary.json"
        profile.write_text(json.dumps({"meta": {}, "prose_style_contract": {}}), encoding="utf-8")
        primary.write_text(
            json.dumps({"prose_style_contract": {"tone": "short"}, "style_assets": {"x": ["y"]}}),
            encoding="utf-8",
        )
        auxiliary.write_text("{}", encoding="utf-8")
        config = self.root / "config.json"
        config.write_text(
            json.dumps({
                "profile_path": str(profile),
                "primary": {"name": "主体", "profile_path": str(primary)},
                "auxiliaries": [{"name": "辅助", "profile_path": str(auxiliary), "selected_bids": ["BID-01"]}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        result = self.run_script(POLICY, "--config", str(config))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        value = json.loads(profile.read_text(encoding="utf-8"))
        self.assertEqual("主体", value["meta"]["source_policy"]["primary"]["name"])
        self.assertFalse(value["prose_style_contract"]["auxiliary_profiles_supply_prose"])


if __name__ == "__main__":
    unittest.main()
