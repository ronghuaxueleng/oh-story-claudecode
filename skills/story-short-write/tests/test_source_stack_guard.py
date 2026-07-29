from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_module(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = load_module("bootstrap_short_project.py", "story_short_write_bootstrap_guard")
COLD_START = load_module(
    "initialize_cold_start_from_source_profiles.py",
    "story_short_write_cold_start_guard",
)


class SourceStackGuardTest(unittest.TestCase):
    def test_bootstrap_blocks_thin_imitation_stack(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "至少需要 1 主 \\+ 3 辅"):
            BOOTSTRAP.validate_source_stack(
                "primary",
                ["aux-1", "aux-2"],
                imitation_mode=True,
            )

    def test_bootstrap_allows_non_imitation_stack(self) -> None:
        BOOTSTRAP.validate_source_stack(
            "primary",
            ["aux-1", "aux-2"],
            imitation_mode=False,
        )

    def test_bootstrap_blocks_duplicate_sources(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "重复"):
            BOOTSTRAP.validate_source_stack(
                "same",
                ["same", "aux-2", "aux-3"],
                imitation_mode=True,
            )

    def test_cold_start_blocks_thin_stack(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "至少需要 1 主 \\+ 3 辅"):
            COLD_START.validate_source_stack(
                Path("/tmp/primary/book.profile.json"),
                [
                    Path("/tmp/aux-1/book.profile.json"),
                    Path("/tmp/aux-2/book.profile.json"),
                ],
            )

    def test_cold_start_allows_thick_stack(self) -> None:
        COLD_START.validate_source_stack(
            Path("/tmp/primary/book.profile.json"),
            [
                Path("/tmp/aux-1/book.profile.json"),
                Path("/tmp/aux-2/book.profile.json"),
                Path("/tmp/aux-3/book.profile.json"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
