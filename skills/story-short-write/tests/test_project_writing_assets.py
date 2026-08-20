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
POLICY = ROOT / "scripts/apply_project_profile_policy.py"
RELEASE = ROOT / "scripts/validate_streamlined_write_release.py"


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

    def test_init_creates_only_project_config(self) -> None:
        project = self.root / "测试书"
        project.mkdir()
        result = self.run_script(
            INIT, "--project-dir", str(project), "--project-name", "测试书"
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        assets = project / "写作资产"
        config = json.loads((assets / "项目写作配置.json").read_text(encoding="utf-8"))
        self.assertEqual("测试书", config["project_name"])
        self.assertEqual("source_anchored", config["length_policy"]["mode"])
        self.assertEqual(1.25, config["length_policy"]["max_total_ratio"])
        self.assertEqual({"项目写作配置.json"}, {path.name for path in assets.iterdir()})

    def test_init_prechecks_all_targets_before_writing(self) -> None:
        project = self.root / "测试书"
        assets = project / "写作资产"
        assets.mkdir(parents=True)
        (assets / "项目写作配置.json").write_text("{}", encoding="utf-8")
        result = self.run_script(
            INIT, "--project-dir", str(project), "--project-name", "测试书"
        )
        self.assertEqual(2, result.returncode)
        self.assertEqual(
            "{}", (assets / "项目写作配置.json").read_text(encoding="utf-8")
        )

    def test_profile_policy_uses_configured_sources(self) -> None:
        profile = self.root / "project.profile.json"
        primary = self.root / "primary.json"
        auxiliary = self.root / "auxiliary.json"
        profile.write_text(
            json.dumps(
                {
                    "meta": {},
                    "prose_style_contract": {},
                    "scene_assets": {"public_explosion": ["辅助污染"]},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        primary.write_text(
            json.dumps(
                {
                    "meta": {"name": "主体"},
                    "prose_style_contract": {
                        "source_role": "primary_only",
                        "sentence_motion": ["短句落锤"],
                        "narrator_voice": ["事实后判断"],
                        "dialogue_and_character_voice": ["角色口气不同"],
                        "anti_patterns": ["不用空总结"],
                    },
                    "style_assets": {"x": ["y"]},
                    "scene_assets": {"public_explosion": ["主体场面"]},
                    "sample_source_buckets": {"source": "主体"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        auxiliary.write_text("{}", encoding="utf-8")
        config = self.root / "config.json"
        config.write_text(
            json.dumps(
                {
                    "profile_path": str(profile),
                    "primary": {"name": "主体", "profile_path": str(primary)},
                    "auxiliaries": [
                        {
                            "name": "辅助",
                            "profile_path": str(auxiliary),
                            "selected_bids": ["BID-01"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = self.run_script(POLICY, "--config", str(config))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        value = json.loads(profile.read_text(encoding="utf-8"))
        self.assertEqual("主体", value["meta"]["source_policy"]["primary"]["name"])
        self.assertFalse(value["prose_style_contract"]["auxiliary_profiles_supply_prose"])
        self.assertEqual(["主体场面"], value["scene_assets"]["public_explosion"])
        self.assertEqual({"source": "主体"}, value["sample_source_buckets"])

    def test_profile_policy_initializes_missing_profile_from_primary(self) -> None:
        profile = self.root / "profiles" / "project.profile.json"
        primary = self.root / "primary.json"
        auxiliary = self.root / "auxiliary.json"
        primary.write_text(
            json.dumps(
                {
                    "meta": {"name": "主体"},
                    "prose_style_contract": {
                        "source_role": "primary_only",
                        "sentence_motion": ["短句落锤"],
                        "narrator_voice": ["事实后判断"],
                        "dialogue_and_character_voice": ["角色口气不同"],
                        "anti_patterns": ["不用空总结"],
                    },
                    "scene_assets": {"public_explosion": ["主体场面"]},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        auxiliary.write_text(
            json.dumps(
                {"scene_assets": {"public_explosion": ["辅助污染"]}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        config = self.root / "config.json"
        config.write_text(
            json.dumps(
                {
                    "project_name": "测试书",
                    "profile_path": str(profile),
                    "primary": {"name": "主体", "profile_path": str(primary)},
                    "auxiliaries": [
                        {
                            "name": "辅助",
                            "profile_path": str(auxiliary),
                            "role": "plot_mechanism_only",
                            "selected_bids": ["BID-01"],
                            "supplies_prose_voice": False,
                            "supplies_emotion_beats": False,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = self.run_script(POLICY, "--config", str(config))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        value = json.loads(profile.read_text(encoding="utf-8"))
        self.assertEqual("测试书", value["meta"]["name"])
        self.assertEqual("primary_policy", value["meta"]["mode"])
        self.assertEqual(["主体场面"], value["scene_assets"]["public_explosion"])

    def test_release_rejects_empty_prose_guidance(self) -> None:
        spec = importlib.util.spec_from_file_location("streamlined_release", RELEASE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        errors = module.validate_prose_contract(
            {
                "prose_style_contract": {
                    "source_role": "primary_only",
                    "sentence_motion": [],
                    "narrator_voice": [],
                    "dialogue_and_character_voice": [],
                    "anti_patterns": [],
                    "auxiliary_profiles_supply_prose": False,
                }
            }
        )
        self.assertEqual(4, len(errors))


if __name__ == "__main__":
    unittest.main()
