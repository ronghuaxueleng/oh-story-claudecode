from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUDIT_MODULES = [
    load_module(
        ROOT / "story-deslop" / "scripts" / "audit_ai_flavor.py",
        "deslop_audit_format_test",
    ),
    load_module(
        ROOT / "story-short-write" / "scripts" / "audit_ai_flavor.py",
        "short_write_audit_format_test",
    ),
    load_module(
        ROOT / "story-setup" / "references" / "templates" / "scripts" / "audit_ai_flavor.py",
        "setup_audit_format_test",
    ),
]

PRECHECK_MODULES = [
    load_module(
        ROOT / "story-deslop" / "scripts" / "precheck_rewrite_gate.py",
        "deslop_precheck_format_test",
    ),
    load_module(
        ROOT / "story-short-write" / "scripts" / "precheck_rewrite_gate.py",
        "short_write_precheck_format_test",
    ),
    load_module(
        ROOT / "story-setup" / "references" / "templates" / "scripts" / "precheck_rewrite_gate.py",
        "setup_precheck_format_test",
    ),
]


class DeslopFormatCompatTest(unittest.TestCase):
    def test_no_blank_line_working_copy_uses_content_lines_as_paragraphs(self) -> None:
        text = (
            "###1.\n"
            "短句。\n"
            "这是一条明显更长的叙述，用来确认段落长度不会被压成零。\n"
            '"ASCII对白。"\n'
            "收尾动作落在门把手上。\n"
        )
        for module in AUDIT_MODULES:
            with self.subTest(module=module.__name__):
                paragraphs = module.split_paragraphs(text)
                self.assertEqual(4, len(paragraphs))
                metrics = {item.name: item for item in module.build_metrics(text)}
                self.assertGreater(metrics["paragraph_length_cv"].value, 0)

    def test_dialogue_ratio_accepts_common_quote_styles(self) -> None:
        text = (
            '"ASCII对白。"\n'
            "“中文双引号对白。”\n"
            "「直角引号对白。」\n"
            "『书名式引号对白。』\n"
            "这是一行叙述。\n"
        )
        for module in AUDIT_MODULES:
            with self.subTest(module=module.__name__):
                metrics = {item.name: item for item in module.build_metrics(text)}
                self.assertEqual("ok", metrics["dialogue_line_ratio"].status)
                self.assertEqual(0.8, metrics["dialogue_line_ratio"].value)

    def test_precheck_protects_functional_weather_and_risk_terms(self) -> None:
        sentences = [
            "高风险科目核验开始。",
            "暴雨红色预警刚刚升级。",
            "哪位做了今年雨季复测？",
            "发现反光信号，距离约三百米。",
        ]
        for module in PRECHECK_MODULES:
            with self.subTest(module=module.__name__):
                config = module.load_config()["pretty_detail"]
                self.assertEqual([], module.find_pretty_details(sentences, config))

    def test_precheck_still_finds_decorative_atmosphere_cluster(self) -> None:
        sentence = "夜雨打在窗外，灯影晃了一整晚。"
        for module in PRECHECK_MODULES:
            with self.subTest(module=module.__name__):
                config = module.load_config()["pretty_detail"]
                findings = module.find_pretty_details([sentence], config)
                self.assertEqual(1, len(findings))
                self.assertIn("雨", findings[0].reason)
                self.assertIn("灯", findings[0].reason)

    def test_precheck_dialogue_parser_accepts_common_quote_styles(self) -> None:
        text = '"甲。"\n“乙。”\n「丙。」\n『丁。』'
        for module in PRECHECK_MODULES:
            with self.subTest(module=module.__name__):
                self.assertEqual(["甲。", "乙。", "丙。", "丁。"], module.find_dialogues(text))

    def test_single_character_substrings_do_not_count_as_action_anchors(self) -> None:
        sentence = "夜雨打在窗外，故事才刚刚开始。"
        for module in PRECHECK_MODULES:
            with self.subTest(module=module.__name__):
                config = module.load_config()["pretty_detail"]
                findings = module.find_pretty_details([sentence], config)
                self.assertEqual(1, len(findings))
                self.assertEqual([], module.collect_anchor_hits(sentence, ["开"], []))

    def test_profile_and_project_override_merge_on_top_of_base_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = root / "book.project.profile.json"
            override_path = root / "precheck_rewrite_gate.override.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "precheck_overrides": {
                            "pretty_detail": {
                                "fact_anchor_patterns": ["暴雨预警", "风险复核表"],
                                "action_anchor_patterns": ["降下车窗"],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            override_path.write_text(
                json.dumps(
                    {
                        "pretty_detail": {
                            "protected_patterns": ["夜雨"],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            for module in PRECHECK_MODULES:
                with self.subTest(module=module.__name__):
                    config = module.load_config()
                    config = module.merge_config(
                        config,
                        module.load_profile_overrides(profile_path),
                    )
                    config = module.merge_config(config, module.load_config(override_path))
                    detail = config["pretty_detail"]
                    self.assertIn("暴雨预警", detail["fact_anchor_patterns"])
                    self.assertIn("降下车窗", detail["action_anchor_patterns"])
                    self.assertIn("风险复核表", detail["fact_anchor_patterns"])
                    self.assertEqual(
                        [],
                        module.find_pretty_details(
                            ["夜雨打在窗外，风险复核表还压在桌上。"],
                            detail,
                        ),
                    )

    def test_profile_without_precheck_overrides_requires_reanalysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "legacy.profile.json"
            profile_path.write_text(
                json.dumps({"style_assets": {"object_pressure": ["旧物件"]}}, ensure_ascii=False),
                encoding="utf-8",
            )
            for module in PRECHECK_MODULES:
                with self.subTest(module=module.__name__):
                    with self.assertRaisesRegex(SystemExit, "重新拆书"):
                        module.load_profile_overrides(profile_path)


if __name__ == "__main__":
    unittest.main()
