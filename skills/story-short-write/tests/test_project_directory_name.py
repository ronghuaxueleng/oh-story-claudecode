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

    def test_generic_delayed_love_title_is_blocked(self) -> None:
        title = "我听不见以后，他才说爱我"
        project = self.root / title
        project.mkdir()
        errors = GATE.validate(project, title)
        self.assertTrue(any("泛化迟到情绪模板" in error for error in errors), errors)

    def test_concrete_anomaly_title_passes(self) -> None:
        title = "我成了自己作品里的冒名者"
        project = self.root / title
        project.mkdir()
        self.assertEqual([], GATE.validate(project, title))

    def test_working_code_directory_is_blocked(self) -> None:
        project = self.root / "新书-主体骨架-强情绪追妻-20260807"
        project.mkdir()
        errors = GATE.validate(project, "他把我的旧录像送给白月光后，我离婚了")
        self.assertTrue(any("正式书名一致" in error for error in errors))
        self.assertTrue(any("工作代号" in error for error in errors))

    def test_missing_directory_is_blocked(self) -> None:
        project = self.root / "不存在的书"
        errors = GATE.validate(project, "不存在的书")
        self.assertTrue(any("目录不存在" in error for error in errors))

    def test_new_project_preflight_passes_only_when_path_is_absent(self) -> None:
        project = self.root / "他以为我不会走"
        self.assertEqual(
            [],
            GATE.validate(project, "他以为我不会走", new_project=True),
        )

    def test_new_project_preflight_blocks_existing_directory(self) -> None:
        project = self.root / "他以为我不会走"
        project.mkdir()
        errors = GATE.validate(
            project,
            "他以为我不会走",
            new_project=True,
        )
        self.assertTrue(any("目录已被占用" in error for error in errors))

    def test_new_project_preflight_blocks_existing_file(self) -> None:
        project = self.root / "他以为我不会走"
        project.write_text("已占用", encoding="utf-8")
        errors = GATE.validate(
            project,
            "他以为我不会走",
            new_project=True,
        )
        self.assertTrue(any("目录已被占用" in error for error in errors))

    def test_create_new_validates_creates_and_rechecks(self) -> None:
        project = self.root / "旧录像"
        self.assertEqual([], GATE.create_new(project, "《旧录像》"))
        self.assertTrue(project.is_dir())

    def test_create_new_does_not_create_invalid_title(self) -> None:
        title = "我听不见以后，他才说爱我"
        project = self.root / title
        errors = GATE.create_new(project, title)
        self.assertTrue(any("泛化迟到情绪模板" in error for error in errors), errors)
        self.assertFalse(project.exists())

    def test_create_new_blocks_occupied_path(self) -> None:
        project = self.root / "旧录像"
        project.mkdir()
        errors = GATE.create_new(project, "旧录像")
        self.assertTrue(any("目录已被占用" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
