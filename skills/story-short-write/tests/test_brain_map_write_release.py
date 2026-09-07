from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_streamlined_write_release.py"
SPEC = importlib.util.spec_from_file_location("test_brain_map_release", SCRIPT)
assert SPEC and SPEC.loader
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


class BrainMapWriteReleaseDensityTest(unittest.TestCase):
    def run_outline_stage(self, *, outline_only=True, draft=False, preflight_errors=None, beat_policy=None, emotion_policy="primary_full_emotion"):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            assets = project / "写作资产"
            assets.mkdir()
            original = project / "主体.txt"
            original.write_text(self.source_text(), encoding="utf-8")
            (project / "小节大纲.md").write_text("## 导语\n", encoding="utf-8")
            (assets / "规则执行台账.json").write_text("{}", encoding="utf-8")
            profile = assets / "book.profile.json"
            profile.write_text("{}", encoding="utf-8")
            config = {"project_name": project.name, "profile_path": str(profile), "primary": {
                "profile_path": str(profile), "prose_voice": "exclusive",
                "emotion_transfer_policy": emotion_policy,
            }, "auxiliaries": []}
            if beat_policy is not None:
                config["beat_transfer_policy"] = beat_policy
            (assets / "项目写作配置.json").write_text(json.dumps(config), encoding="utf-8")
            if draft:
                (project / "正文.md").write_text("", encoding="utf-8")
            source = {"compiled_from": {"original": {"path": str(original)}}}
            with mock.patch.object(RELEASE, "validate_prose_contract", return_value=[]), \
                 mock.patch.object(RELEASE.RULE_LEDGER, "validate_prewrite_ledger", return_value=[]) as prewrite, \
                 mock.patch.object(RELEASE.RULE_LEDGER, "validate_design_gate", return_value=[]) as design, \
                 mock.patch.object(RELEASE.TARGET_MAP, "resolve_source_map", return_value=(project / "source.json", source)), \
                 mock.patch.object(RELEASE.TARGET_MAP, "preflight_outline_text", return_value=({}, preflight_errors or [])) as preflight, \
                 mock.patch.object(RELEASE.TARGET_MAP, "parse_outline", return_value=self.outline_catalog(17, 10_200)):
                errors = RELEASE.validate_release(project, outline_only=outline_only)
                return errors, prewrite.call_count, design.call_count, preflight.call_args

    def test_outline_mode_does_not_require_future_brain_map(self):
        errors, prewrite_calls, design_calls, preflight_call = self.run_outline_stage()
        self.assertEqual([], errors)
        self.assertEqual(0, prewrite_calls)
        self.assertEqual(1, design_calls)
        self.assertFalse(preflight_call.kwargs["allow_partial"])

    def test_functional_transfer_accepts_new_emotion_proposition(self):
        errors, _, _, _ = self.run_outline_stage(
            beat_policy={"mode": "functional_beat_transfer", "preserve_emotion_function": True, "preserve_emotion_proposition": False},
            emotion_policy="primary_functional_emotion",
        )
        self.assertEqual([], errors)

    def test_functional_transfer_rejects_old_full_emotion_contract(self):
        errors, _, _, _ = self.run_outline_stage(
            beat_policy={"mode": "functional_beat_transfer", "preserve_emotion_function": True, "preserve_emotion_proposition": False},
        )
        self.assertTrue(any("primary_functional_emotion" in error for error in errors))

    def test_functional_transfer_rejects_original_proposition_retention(self):
        errors, _, _, _ = self.run_outline_stage(
            beat_policy={"mode": "functional_beat_transfer", "preserve_emotion_function": True, "preserve_emotion_proposition": True},
            emotion_policy="primary_functional_emotion",
        )
        self.assertTrue(any("不得保留原文具体情绪命题" in error for error in errors))

    def test_default_mode_still_requires_brain_map(self):
        errors, prewrite_calls, _, _ = self.run_outline_stage(outline_only=False)
        self.assertEqual(1, prewrite_calls)
        self.assertTrue(any("目标成文脑图" in error for error in errors))

    def test_outline_mode_cannot_bypass_existing_draft(self):
        errors, _, _, _ = self.run_outline_stage(draft=True)
        self.assertTrue(any("已存在正文" in error for error in errors))

    def test_outline_mode_propagates_full_preflight_failure(self):
        errors, _, _, _ = self.run_outline_stage(preflight_errors=["缺少来源尾拍"])
        self.assertIn("缺少来源尾拍", errors)

    def source_text(self) -> str:
        body = "字" * 600
        return "导语\n" + "\n".join(
            f"{index}{'.' if index % 2 == 0 else ''}\n{body}"
            for index in range(1, 18)
        )

    def outline_catalog(self, section_count: int, target_chars: int) -> dict:
        per_section = target_chars // section_count
        remainder = target_chars % section_count
        return {
            "regions": [
                {
                    "region_id": f"section:{index}",
                    "target_chars": {
                        "min": per_section + (1 if index <= remainder else 0),
                        "max": per_section + (1 if index <= remainder else 0),
                    },
                }
                for index in range(1, section_count + 1)
            ],
            "errors": [],
        }

    def test_bare_and_dotted_source_sections_are_recognized(self) -> None:
        sections = RELEASE.source_numeric_sections(self.source_text())
        self.assertEqual(17, len(sections))
        self.assertTrue(all(len(section) == 600 for section in sections))

    def test_minimum_density_blocks_fourteen_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text(self.source_text(), encoding="utf-8")
            blocked = RELEASE.validate_section_density(
                self.outline_catalog(14, 25_125), original
            )
            passed = RELEASE.validate_section_density(
                self.outline_catalog(29, 25_125), original
            )
        self.assertTrue(blocked)
        self.assertIn("actual=14", blocked[0])
        self.assertEqual([], passed)

    def test_source_anchored_outline_blocks_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text(self.source_text(), encoding="utf-8")
            config = {
                "length_policy": {
                    "mode": "source_anchored",
                    "max_total_ratio": 1.25,
                    "max_section_ratio": 1.25,
                }
            }
            oversized = RELEASE.validate_source_anchored_outline(
                self.outline_catalog(29, 25_125), original, config
            )
            source_chars = RELEASE.nonspace_count(self.source_text())
            within_limit = RELEASE.validate_source_anchored_outline(
                self.outline_catalog(17, int(source_chars * 1.2)), original, config
            )
        self.assertEqual(2, len(oversized))
        self.assertEqual([], within_limit)

    def test_draft_enforces_source_anchored_minimum_and_upper_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text("字" * 10_000, encoding="utf-8")
            config = {"length_policy": {"mode": "source_anchored"}}
            at_limit = RELEASE.validate_source_anchored_draft(
                "字" * 12_500, original, config
            )
            over_limit = RELEASE.validate_source_anchored_draft(
                "字" * 12_501, original, config
            )
            short_draft = RELEASE.validate_source_anchored_draft(
                "字" * 1_000, original, config
            )
        self.assertEqual([], at_limit)
        self.assertIn("required_min", short_draft[0])
        self.assertIn("draft=12501", over_limit[0])

    def test_expansion_requires_explicit_user_authorization(self) -> None:
        _, missing = RELEASE.resolve_length_policy(
            {
                "length_policy": {
                    "mode": "explicit_expansion",
                    "max_total_ratio": 2,
                    "max_section_ratio": 2,
                }
            }
        )
        policy, authorized = RELEASE.resolve_length_policy(
            {
                "length_policy": {
                    "mode": "explicit_expansion",
                    "max_total_ratio": 2,
                    "max_section_ratio": 2,
                    "authorized_by_user": True,
                    "authorization_note": "用户明确要求扩写为两倍篇幅",
                }
            }
        )
        self.assertTrue(missing)
        self.assertEqual([], authorized)
        self.assertEqual(2.0, policy["max_total_ratio"])


if __name__ == "__main__":
    unittest.main()
