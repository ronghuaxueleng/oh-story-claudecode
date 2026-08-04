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
            "1.\n\n第一节正文。\n\n2.\n\n第二节正文。\n"
        )
        self.assertEqual([], errors)
        self.assertEqual([1, 2], sections)

    def test_book_title_on_first_nonempty_line_is_blocked(self) -> None:
        errors, sections = VALIDATOR.validate_text(
            "\n# 测试书名\n\n1.\n\n第一节正文。\n\n2.\n\n第二节正文。\n"
        )
        self.assertTrue(any("正文 Markdown 标题" in error for error in errors))
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

    def test_natural_paragraphs_with_one_blank_line_pass(self) -> None:
        errors, sections = VALIDATOR.validate_text(
            "1.\n\n第一段。\n\n「一轮对话。」\n\n第二段。\n"
        )
        self.assertEqual([], errors)
        self.assertEqual([1], sections)

    def test_long_multi_sentence_paragraph_is_blocked(self) -> None:
        text = (
            "1.\n\n"
            "她把材料放下。门外有人敲门。手机跟着亮了。\n"
        )
        errors, _ = VALIDATOR.validate_text(text)
        self.assertTrue(any("单个自然段最多承载" in error for error in errors))

    def test_embedded_dialogue_is_blocked(self) -> None:
        errors, _ = VALIDATOR.validate_text(
            "1.\n\n她按住材料，说：「你先回答我。」\n"
        )
        self.assertTrue(any("对白必须按说话轮次独立成段" in error for error in errors))

    def test_dialogue_on_its_own_paragraph_passes(self) -> None:
        errors, sections = VALIDATOR.validate_text(
            "1.\n\n她按住材料。\n\n「你先回答我。」\n\n他没有抬头。\n"
        )
        self.assertEqual([], errors)
        self.assertEqual([1], sections)

    def test_three_consecutive_long_sentences_are_blocked(self) -> None:
        long_one = "她站在门口看着那份已经被撤回的说明，直到屏幕重新弹出红色通知才慢慢收回手。"
        long_two = "他明明听见法务说完全部后果，还是越过桌面拿走材料并在手机上撤回自己的签名。"
        long_three = "候场区所有人都看见她的权限被暂停，而他第一件事仍是转身确认另一个女孩有没有哭。"
        errors, _ = VALIDATOR.validate_text(
            f"1.\n\n{long_one}\n\n{long_two}\n\n{long_three}\n"
        )
        self.assertTrue(any("连续超过" in error for error in errors))

    def test_sentence_over_mobile_reading_limit_is_blocked(self) -> None:
        sentence = "她隔着玻璃看见他又一次护在那个女孩面前，却还要装作什么都没有发生地让她再等十分钟，等他处理完别人的事。"
        errors, _ = VALIDATOR.validate_text(f"1.\n\n{sentence}\n")
        self.assertTrue(any("超长句" in error for error in errors))

    def test_three_medium_long_sentences_are_blocked(self) -> None:
        one = "她把停权通知压在桌上，等他当着所有人的面回答刚才那个问题。"
        two = "他避开她的视线，又低头去确认另一个人现在到底有没有哭。"
        three = "所有人都看见了他的选择，只有他还在反复说今天只是一场误会。"
        errors, _ = VALIDATOR.validate_text(
            f"1.\n\n{one}\n\n{two}\n\n{three}\n"
        )
        self.assertTrue(any("连续超过" in error for error in errors))

    def test_missing_paragraph_blank_line_is_blocked(self) -> None:
        errors, _ = VALIDATOR.validate_text(
            "# 测试书名\n\n1.\n第一段。\n第二段。\n"
        )
        self.assertTrue(any("缺少一个空行" in error for error in errors))

    def test_multiple_blank_lines_are_blocked(self) -> None:
        errors, _ = VALIDATOR.validate_text(
            "# 测试书名\n\n\n1.\n\n第一段。\n"
        )
        self.assertTrue(any("连续空行" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
