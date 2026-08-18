from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTLINE = load_module(
    "test_outline_rebinding_module",
    "validate_outline_migration_contract.py",
)
RELEASE = load_module(
    "test_streamlined_release_module",
    "validate_streamlined_write_release.py",
)
INITIAL_REVIEW = load_module(
    "test_initial_review_refresh_module",
    "validate_initial_draft_review.py",
)


def catalog(region_beats: list[tuple[str, list[tuple[str, str]]]]) -> dict:
    return {
        "regions": [
            {
                "region_id": region_id,
                "target_beats": [
                    {"target_id": target_id, "evidence": evidence}
                    for target_id, evidence in beats
                ],
            }
            for region_id, beats in region_beats
        ],
        "errors": [],
    }


class EvidenceRebindingTest(unittest.TestCase):
    def test_mapping_follows_unchanged_evidence_across_new_sections(self) -> None:
        old_catalog = catalog(
            [
                ("section:1", [("T-1-001", "甲"), ("T-1-002", "乙")]),
                ("section:2", [("T-2-001", "丙")]),
            ]
        )
        new_catalog = catalog(
            [
                ("section:1", [("T-1-001", "甲")]),
                ("section:2", [("T-2-001", "乙")]),
                ("section:3", [("T-3-001", "丙"), ("T-3-002", "新增")]),
            ]
        )
        mapping = {
            "primary_plot_targets": ["T-1-001", "T-1-002", "T-2-001"],
            "primary_emotion_targets": ["T-1-002", "T-2-001"],
            "auxiliary_plot_targets": {"SRC-AUX-01": ["T-2-001"]},
        }

        migrated = OUTLINE.migrate_mapping_by_evidence(
            old_catalog,
            new_catalog,
            mapping,
        )

        self.assertEqual(
            ["T-1-001", "T-2-001", "T-3-001"],
            migrated["primary_plot_targets"],
        )
        self.assertEqual(
            ["T-2-001", "T-3-001"],
            migrated["primary_emotion_targets"],
        )
        self.assertEqual(
            ["T-3-001"],
            migrated["auxiliary_plot_targets"]["SRC-AUX-01"],
        )

    def test_changed_evidence_blocks_deterministic_rebinding(self) -> None:
        old_catalog = catalog([("section:1", [("T-1-001", "原证据")])])
        new_catalog = catalog([("section:1", [("T-1-001", "被改写")])])
        mapping = {
            "primary_plot_targets": ["T-1-001"],
            "primary_emotion_targets": [],
            "auxiliary_plot_targets": {},
        }

        with self.assertRaisesRegex(ValueError, "已被改写或删除"):
            OUTLINE.migrate_mapping_by_evidence(
                old_catalog,
                new_catalog,
                mapping,
            )


class SectionDensityTest(unittest.TestCase):
    def source_text(self) -> str:
        body = "字" * 600
        return "导语\n" + "\n".join(
            f"{index}{'.' if index % 2 == 0 else ''}\n{body}"
            for index in range(1, 18)
        )

    def outline_catalog(self, section_count: int, target_chars: int) -> dict:
        per_section = target_chars // section_count
        remainder = target_chars % section_count
        regions = []
        for index in range(1, section_count + 1):
            midpoint = per_section + (1 if index <= remainder else 0)
            regions.append(
                {
                    "region_id": f"section:{index}",
                    "target_chars": {"min": midpoint, "max": midpoint},
                }
            )
        return {"regions": regions, "errors": []}

    def test_bare_and_dotted_source_sections_are_recognized(self) -> None:
        sections = RELEASE.source_numeric_sections(self.source_text())
        self.assertEqual(17, len(sections))
        self.assertTrue(all(len(section) == 600 for section in sections))

    def test_fourteen_sections_block_but_twenty_nine_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "主体.txt"
            original.write_text(self.source_text(), encoding="utf-8")
            target_chars = 25_125

            blocked = RELEASE.validate_section_density(
                self.outline_catalog(14, target_chars),
                original,
            )
            passed = RELEASE.validate_section_density(
                self.outline_catalog(29, target_chars),
                original,
            )

        self.assertTrue(blocked)
        self.assertIn("actual=14", blocked[0])
        self.assertEqual([], passed)


class InitialReviewRefreshTest(unittest.TestCase):
    region_text = "第一条证据。中间内容。第二条证据。"

    def review(self, plot_refs: list[str], region_text: str | None = None) -> dict:
        text = self.region_text if region_text is None else region_text
        return {
            "content_sha256": INITIAL_REVIEW.text_sha256(text),
            "plot_refs": plot_refs,
            "emotion_refs": ["E-001"],
            "auxiliary_plot_refs": [],
            "prose_subflow_refs": ["SF-001"],
            "evidence_quotes": ["第一条证据。", "第二条证据。"],
        }

    def test_unchanged_requirements_and_quotes_can_be_preserved(self) -> None:
        old = self.review(["P-001"])
        refreshed = self.review(["P-001"])
        self.assertTrue(
            INITIAL_REVIEW.can_preserve_region_review(
                old,
                refreshed,
                self.region_text,
            )
        )

    def test_split_region_cannot_inherit_same_numbered_old_review(self) -> None:
        old = self.review(["P-001", "P-002"])
        refreshed = self.review(["P-001"])
        self.assertFalse(
            INITIAL_REVIEW.can_preserve_region_review(
                old,
                refreshed,
                self.region_text,
            )
        )

    def test_changed_region_cannot_inherit_even_when_quotes_survive(self) -> None:
        old = self.review(["P-001"])
        changed_text = "第一条证据。新增并改写的正文。第二条证据。"
        refreshed = self.review(["P-001"], changed_text)
        self.assertFalse(
            INITIAL_REVIEW.can_preserve_region_review(
                old,
                refreshed,
                changed_text,
            )
        )


if __name__ == "__main__":
    unittest.main()
