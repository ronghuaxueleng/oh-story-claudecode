from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_project_directory_name.py"
)
SPEC = importlib.util.spec_from_file_location("project_directory_name", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ProjectDirectoryNameTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_exact_book_title_passes(self) -> None:
        project = self.root / "他把我的旧录像送给白月光后，我离婚了"
        project.mkdir()
        self.assertEqual([], GATE.validate(project, "他把我的旧录像送给白月光后，我离婚了"))

    def test_book_title_wrappers_are_normalized(self) -> None:
        project = self.root / "旧录像"
        project.mkdir()
        self.assertEqual([], GATE.validate(project, "《旧录像》"))

    def test_working_code_directory_is_blocked(self) -> None:
        project = self.root / "新书-幼薇主骨架-强情绪追妻-20260807"
        project.mkdir()
        errors = GATE.validate(project, "他把我的旧录像送给白月光后，我离婚了")
        self.assertTrue(any("正式书名一致" in error for error in errors))
        self.assertTrue(any("工作代号" in error for error in errors))

    def test_missing_directory_is_blocked(self) -> None:
        project = self.root / "不存在的书"
        errors = GATE.validate(project, "不存在的书")
        self.assertTrue(any("目录不存在" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
