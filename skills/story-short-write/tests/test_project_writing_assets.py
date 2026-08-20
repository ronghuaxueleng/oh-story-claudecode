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


def source_layer(layer_id: str, source_text: str) -> dict:
    return {
        "layer_id": layer_id,
        "source_range": "L1-L2",
        "source_text": source_text,
        "layer_modes": ["live_scene"],
        "layer_role": "现场先阻拦再错答，以关系位置改变收束。",
        "entry_relation": "承接关系尚未翻面的进入态。",
        "exit_relation": "以主角决定离开切出现场。",
        "narrative_distance": "近景跟随动作与对白。",
        "dimension_realization": {},
        "must_preserve_in_target": ["保持现场层型和动作先后。"],
    }


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
            "{}",
            (assets / "项目写作配置.json").read_text(encoding="utf-8"),
        )

    def test_profile_policy_uses_configured_sources(self) -> None:
        profile = self.root / "project.profile.json"
        primary = self.root / "primary.json"
        auxiliary = self.root / "auxiliary.json"
        profile.write_text(
            json.dumps({
                "meta": {},
                "prose_style_contract": {},
                "scene_assets": {"public_explosion": ["辅助污染"]},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        primary.write_text(
            json.dumps({
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
            }),
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
        self.assertEqual(["主体场面"], value["scene_assets"]["public_explosion"])
        self.assertEqual({"source": "主体"}, value["sample_source_buckets"])

    def test_profile_policy_initializes_missing_profile_from_primary(self) -> None:
        profile = self.root / "profiles" / "project.profile.json"
        primary = self.root / "primary.json"
        auxiliary = self.root / "auxiliary.json"
        primary.write_text(
            json.dumps({
                "meta": {"name": "主体"},
                "prose_style_contract": {
                    "source_role": "primary_only",
                    "sentence_motion": ["短句落锤"],
                    "narrator_voice": ["事实后判断"],
                    "dialogue_and_character_voice": ["角色口气不同"],
                    "anti_patterns": ["不用空总结"],
                },
                "scene_assets": {"public_explosion": ["主体场面"]},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        auxiliary.write_text(
            json.dumps({"scene_assets": {"public_explosion": ["辅助污染"]}}, ensure_ascii=False),
            encoding="utf-8",
        )
        config = self.root / "config.json"
        config.write_text(
            json.dumps({
                "project_name": "测试书",
                "profile_path": str(profile),
                "primary": {"name": "主体", "profile_path": str(primary)},
                "auxiliaries": [{
                    "name": "辅助",
                    "profile_path": str(auxiliary),
                    "role": "plot_mechanism_only",
                    "selected_bids": ["BID-01"],
                    "supplies_prose_voice": False,
                    "supplies_emotion_beats": False,
                }],
            }, ensure_ascii=False),
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
        errors = module.validate_prose_contract({
            "prose_style_contract": {
                "source_role": "primary_only",
                "sentence_motion": [],
                "narrator_voice": [],
                "dialogue_and_character_voice": [],
                "anti_patterns": [],
                "auxiliary_profiles_supply_prose": False,
            }
        })
        self.assertEqual(4, len(errors))

    def test_release_requires_whole_sf_chain_and_target_carriers(self) -> None:
        spec = importlib.util.spec_from_file_location("streamlined_release", RELEASE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base = {
            "outline_catalog": {
                "regions": [
                    {
                        "region_id": "section:1",
                        "target_beats": [
                            {"target_id": "T-1", "evidence": "目标动作证据"}
                        ],
                    }
                ]
            },
            "granularity_coverage": [
                {
                    "source_ref": "SRC-PRIMARY:SF-01",
                    "performance_requirements": {
                        "entry_state": "关系尚未翻面。",
                        "required_sequence": ["先阻拦。", "再错答。"],
                        "scene_granularity": "阻拦和错答连续发生。",
                        "emotion_sequence": ["期待", "失望"],
                        "end_state": "主角决定离开。",
                        "source_excerpt": "他先拦住我。随后替别人解释。",
                    },
                    "source_layer_order": ["SF-01-L01"],
                    "source_layer_topology": [
                        source_layer("SF-01-L01", "他先拦住我。随后替别人解释。")
                    ],
                    "target_performance_carriers": [
                        {
                            "source_plot_ref": "SRC-PRIMARY:P-001",
                            "source_range": "L1-L2",
                            "target_id": "T-1",
                            "target_region": "section:1",
                            "outline_evidence": "目标动作证据",
                        }
                    ],
                    "target_regions": ["section:1"],
                }
            ],
            "sf_performance_bindings": [
                {
                    "source_ref": "SRC-PRIMARY:SF-01",
                    "required_sequence_target_ids": [["T-1"], ["T-1"]],
                    "emotion_sequence_target_ids": [["T-1"], ["T-1"]],
                    "scene_granularity_target_ids": ["T-1"],
                    "source_layer_target_bindings": [
                        {
                            "layer_id": "SF-01-L01",
                            "target_ids": ["T-1"],
                            "preserved_layer_modes": ["live_scene"],
                            "adaptation_instruction": "目标仍按近景现场先阻拦再错答，并以离开动作收束这一层。",
                        }
                    ],
                }
            ],
        }

        self.assertEqual([], module.validate_full_sf_write_requirements(base))

        missing_chain = json.loads(json.dumps(base, ensure_ascii=False))
        del missing_chain["granularity_coverage"][0]["performance_requirements"]
        self.assertTrue(module.validate_full_sf_write_requirements(missing_chain))

        missing_carrier = json.loads(json.dumps(base, ensure_ascii=False))
        missing_carrier["granularity_coverage"][0][
            "target_performance_carriers"
        ] = []
        errors = module.validate_full_sf_write_requirements(missing_carrier)
        self.assertTrue(any("禁止开始正文" in error for error in errors))

    def test_source_layers_can_use_non_p_targets_only_inside_sf_carrier_span(self) -> None:
        spec = importlib.util.spec_from_file_location("streamlined_release", RELEASE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target_beats = [
            {"target_id": target_id, "evidence": f"{target_id} 目标细拍证据"}
            for target_id in ("T-0", "T-1", "T-2", "T-3", "T-4")
        ]
        contract = {
            "outline_catalog": {
                "regions": [
                    {"region_id": "section:1", "target_beats": target_beats}
                ]
            },
            "granularity_coverage": [
                {
                    "source_ref": "SRC-PRIMARY:SF-01",
                    "performance_requirements": {
                        "entry_state": "现场尚未公开翻面。",
                        "required_sequence": ["先公开失控。", "再进入处置。"],
                        "scene_granularity": "两端承重动作之间保留叙述者插话。",
                        "emotion_sequence": ["失控", "冷却"],
                        "end_state": "处置结果落定。",
                        "source_excerpt": "现场失控。我插了一句。随后进入处置。",
                    },
                    "source_layer_order": ["SF-01-L01", "SF-01-L02"],
                    "source_layer_topology": [
                        source_layer("SF-01-L01", "现场失控。"),
                        source_layer("SF-01-L02", "我插了一句。"),
                    ],
                    "target_performance_carriers": [
                        {
                            "source_plot_ref": "SRC-PRIMARY:P-001",
                            "source_range": "L1-L1",
                            "target_id": "T-1",
                            "target_region": "section:1",
                            "outline_evidence": "T-1 目标细拍证据",
                        },
                        {
                            "source_plot_ref": "SRC-PRIMARY:P-002",
                            "source_range": "L3-L3",
                            "target_id": "T-3",
                            "target_region": "section:1",
                            "outline_evidence": "T-3 目标细拍证据",
                        },
                    ],
                    "target_regions": ["section:1"],
                }
            ],
            "sf_performance_bindings": [
                {
                    "source_ref": "SRC-PRIMARY:SF-01",
                    "required_sequence_target_ids": [["T-1"], ["T-3"]],
                    "emotion_sequence_target_ids": [["T-1"], ["T-3"]],
                    "scene_granularity_target_ids": ["T-1", "T-3"],
                    "source_layer_target_bindings": [
                        {
                            "layer_id": "SF-01-L01",
                            "target_ids": ["T-1"],
                            "preserved_layer_modes": ["live_scene"],
                            "adaptation_instruction": "第一层保持公开失控的近景现场，并在动作停顿后让叙述者插话。",
                        },
                        {
                            "layer_id": "SF-01-L02",
                            "target_ids": ["T-2"],
                            "preserved_layer_modes": ["live_scene"],
                            "adaptation_instruction": "第二层使用两端承重拍之间的插入细拍，保留突然插嘴和短促气口。",
                        },
                    ],
                }
            ],
        }

        self.assertEqual([], module.validate_full_sf_write_requirements(contract))

        contract["sf_performance_bindings"][0]["source_layer_target_bindings"][1][
            "target_ids"
        ] = ["T-4"]
        errors = module.validate_full_sf_write_requirements(contract)
        self.assertTrue(any("最早与最晚 P 承载细拍之间" in error for error in errors))

    def test_cross_region_sf_must_bind_steps_into_every_target_region(self) -> None:
        spec = importlib.util.spec_from_file_location("streamlined_release", RELEASE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        catalog = {
            "regions": [
                {
                    "region_id": "section:1",
                    "target_beats": [{"target_id": "T-1", "evidence": "先失望"}],
                },
                {
                    "region_id": "section:2",
                    "target_beats": [{"target_id": "T-2", "evidence": "再离开"}],
                },
            ]
        }
        coverage = [
            {
                "source_ref": "SRC-PRIMARY:SF-01",
                "performance_requirements": {
                    "entry_state": "仍抱期待。",
                    "required_sequence": ["先失望。", "再离开。"],
                    "scene_granularity": "两个动作跨节连续完成。",
                    "emotion_sequence": ["失望", "决绝"],
                    "end_state": "关系关闭。",
                    "source_excerpt": "我先失望，后来离开。",
                },
                "source_layer_order": ["SF-01-L01", "SF-01-L02"],
                "source_layer_topology": [
                    source_layer("SF-01-L01", "我先失望。"),
                    source_layer("SF-01-L02", "后来离开。"),
                ],
                "target_performance_carriers": [
                    {
                        "source_plot_ref": "SRC-PRIMARY:P-001",
                        "source_range": "L1-L1",
                        "target_id": "T-1",
                        "target_region": "section:1",
                        "outline_evidence": "先失望",
                    },
                    {
                        "source_plot_ref": "SRC-PRIMARY:P-002",
                        "source_range": "L2-L2",
                        "target_id": "T-2",
                        "target_region": "section:2",
                        "outline_evidence": "再离开",
                    },
                ],
                "target_regions": ["section:1", "section:2"],
            }
        ]
        binding = {
            "source_ref": "SRC-PRIMARY:SF-01",
            "required_sequence_target_ids": [["T-1"], ["T-1"]],
            "emotion_sequence_target_ids": [["T-1"], ["T-1"]],
            "scene_granularity_target_ids": ["T-1"],
            "source_layer_target_bindings": [
                {
                    "layer_id": "SF-01-L01",
                    "target_ids": ["T-1"],
                    "preserved_layer_modes": ["live_scene"],
                    "adaptation_instruction": "第一层保持近景现场，以具体失望反应承接前态并送入离开决定。",
                },
                {
                    "layer_id": "SF-01-L02",
                    "target_ids": ["T-1"],
                    "preserved_layer_modes": ["live_scene"],
                    "adaptation_instruction": "第二层保持近景现场，以离开动作关闭关系，不扩写成结果说明。",
                },
            ],
        }
        errors = module.OUTLINE.validate_sf_performance_bindings(
            [binding], coverage, catalog
        )
        self.assertTrue(any("全部目标区域" in error for error in errors))

        binding["required_sequence_target_ids"] = [["T-1"], ["T-2"]]
        binding["emotion_sequence_target_ids"] = [["T-1"], ["T-2"]]
        binding["scene_granularity_target_ids"] = ["T-1", "T-2"]
        binding["source_layer_target_bindings"][1]["target_ids"] = ["T-2"]
        self.assertEqual(
            [],
            module.OUTLINE.validate_sf_performance_bindings(
                [binding], coverage, catalog
            ),
        )


if __name__ == "__main__":
    unittest.main()
