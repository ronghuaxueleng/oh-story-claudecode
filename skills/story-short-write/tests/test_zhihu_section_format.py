from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_zhihu_section_format.py"
)
SPEC = importlib.util.spec_from_file_location("zhihu_section_format", SCRIPT_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ZhihuSectionFormatTest(unittest.TestCase):
    def test_pure_numeric_sections_pass(self) -> None:
        errors, sections = VALIDATOR.validate_text(
            "1.\n第一节正文。\n2.\n第二节正文。\n"
        )
        self.assertEqual([], errors)
        self.assertEqual([1, 2], sections)

    def test_book_title_on_first_nonempty_line_is_allowed(self) -> None:
        errors, sections = VALIDATOR.validate_text(
            "\n# 测试书名\n\n1.\n第一节正文。\n2.\n第二节正文。\n"
        )
        self.assertEqual([], errors)
        self.assertEqual([1, 2], sections)

    def test_markdown_numbered_heading_is_blocked(self) -> None:
        errors, _ = VALIDATOR.validate_text(
            "# 测试书名\n## 1. 培训名额\n正文。\n"
        )
        self.assertTrue(any("Markdown 数字章节标题" in error for error in errors))

    def test_numbered_title_is_blocked(self) -> None:
        errors, _ = VALIDATOR.validate_text(
            "# 测试书名\n1. 培训名额\n正文。\n"
        )
        self.assertTrue(any("附加了章节名" in error for error in errors))

    def test_chinese_chapter_heading_is_blocked(self) -> None:
        errors, _ = VALIDATOR.validate_text(
            "# 测试书名\n第一章 培训名额\n正文。\n"
        )
        self.assertTrue(any("中文章节名" in error for error in errors))

    def test_chinese_list_separator_is_blocked(self) -> None:
        errors, _ = VALIDATOR.validate_text(
            "# 测试书名\n1.\n正文。\n2、\n正文。\n"
        )
        self.assertTrue(any("非知乎分节符号" in error for error in errors))

    def test_skipped_section_number_is_blocked(self) -> None:
        errors, sections = VALIDATOR.validate_text(
            "# 测试书名\n1.\n正文。\n3.\n正文。\n"
        )
        self.assertEqual([1, 3], sections)
        self.assertTrue(any("连续递增" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
