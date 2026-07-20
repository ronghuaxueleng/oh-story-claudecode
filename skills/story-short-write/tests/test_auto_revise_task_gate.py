from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "auto_revise_ai_flavor.py"
)
SPEC = importlib.util.spec_from_file_location("auto_revise_ai_flavor", SCRIPT_PATH)
assert SPEC and SPEC.loader
REVISE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVISE)


class AutoReviseTaskGateTest(unittest.TestCase):
    def test_missing_high_risk_bridge_task_is_hard_error(self) -> None:
        validation = REVISE.build_task_validation(
            tasks=[],
            segment_focus=[
                {
                    "flags": ["同桥承重件不完整：公开掉位桥"],
                }
            ],
            paragraph_focus=[],
        )
        self.assertFalse(validation["bridge_alignment_ok"])
        self.assertTrue(validation["hard_errors"])

    def test_short_paragraph_priority_remains_diagnostic_warning(self) -> None:
        validation = REVISE.build_task_validation(
            tasks=[],
            segment_focus=[],
            paragraph_focus=[
                {
                    "paragraph_index": 7,
                    "flags": ["短段对白密"],
                }
            ],
        )
        self.assertTrue(validation["bridge_alignment_ok"])
        self.assertFalse(validation["short_paragraph_priority_ok"])
        self.assertEqual([], validation["hard_errors"])
        self.assertTrue(validation["warnings"])

    def test_bound_incomplete_profile_is_hard_error(self) -> None:
        errors = REVISE.profile_contract_errors(
            {
                "profile": "/tmp/project.profile.json",
                "asset_coverage": {
                    "has_bridge_rules": False,
                    "missing_scene_asset_keys": ["external_order"],
                    "missing_style_asset_keys": ["character_bias"],
                    "missing_story_guardrail_keys": ["tail_entry_owner"],
                },
            }
        )
        self.assertEqual(4, len(errors))

    def test_standalone_audit_without_profile_keeps_diagnostics_optional(self) -> None:
        errors = REVISE.profile_contract_errors(
            {
                "profile": None,
                "asset_coverage": {
                    "has_bridge_rules": False,
                    "missing_scene_asset_keys": ["external_order"],
                },
            }
        )
        self.assertEqual([], errors)
