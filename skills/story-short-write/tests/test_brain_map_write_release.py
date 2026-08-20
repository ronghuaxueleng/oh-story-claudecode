from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_streamlined_write_release.py"
SPEC = importlib.util.spec_from_file_location("test_brain_map_release", SCRIPT)
assert SPEC and SPEC.loader
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


class BrainMapWriteReleaseDensityTest(unittest.TestCase):
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

    def test_draft_uses_only_global_upper_bound(self) -> None:
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
        self.assertEqual([], short_draft)
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
