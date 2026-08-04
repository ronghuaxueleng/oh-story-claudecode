#!/usr/bin/env python3
"""Validate Zhihu/Yanyan section markers and reading-layout spacing."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PURE_SECTION = re.compile(r"^(\d+)\.$")
MARKDOWN_NUMBERED_HEADING = re.compile(r"^#{1,6}\s*\d+")
CHINESE_CHAPTER_HEADING = re.compile(
    r"^第[零〇一二三四五六七八九十百千万两\d]+[章节回卷部篇]"
    r"(?:$|\s|[：:._、-])"
)
NUMBERED_TITLE = re.compile(r"^\d+[.、]\s*\S+")
NON_ZHIHU_SECTION = re.compile(r"^\d+、")
ANY_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s*\S+")
SENTENCE_END = re.compile(r"[^。！？!?]+[。！？!?]?")
EXPLICIT_DIALOGUE = re.compile(r"[：:]\s*[「“]")
MAX_PARAGRAPH_SENTENCES = 2
MAX_PARAGRAPH_CHARS = 100
MAX_SENTENCE_CHARS = 42
LONG_SENTENCE_CHARS = 22
MAX_CONSECUTIVE_LONG_SENTENCES = 2


def non_whitespace_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def prose_sentences(line: str) -> list[str]:
    return [
        item.strip()
        for item in SENTENCE_END.findall(line)
        if item.strip() and re.search(r"[\w\u4e00-\u9fff]", item)
    ]


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def validate_text(text: str) -> tuple[list[str], list[int]]:
    errors: list[str] = []
    sections: list[int] = []
    nonempty_index = 0
    lines = text.splitlines()

    previous_nonempty_line: int | None = None
    blank_run = 0
    consecutive_long_sentences = 0

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            blank_run += 1
            continue

        if previous_nonempty_line is not None:
            if blank_run == 0:
                errors.append(
                    f"第 {previous_nonempty_line} 与第 {line_number} 行之间缺少一个空行"
                )
            elif blank_run > 1:
                errors.append(
                    f"第 {previous_nonempty_line} 与第 {line_number} 行之间存在 {blank_run} 个连续空行，只允许一个"
                )
        previous_nonempty_line = line_number
        blank_run = 0

        nonempty_index += 1
        pure_match = PURE_SECTION.fullmatch(line)
        if pure_match:
            sections.append(int(pure_match.group(1)))
            consecutive_long_sentences = 0
            continue

        if MARKDOWN_NUMBERED_HEADING.match(line):
            errors.append(
                f"第 {line_number} 行使用了 Markdown 数字章节标题: {line}"
            )
            continue
        if CHINESE_CHAPTER_HEADING.match(line):
            errors.append(f"第 {line_number} 行使用了中文章节名: {line}")
            continue
        if NUMBERED_TITLE.match(line):
            errors.append(f"第 {line_number} 行在分节数字后附加了章节名: {line}")
            continue
        if NON_ZHIHU_SECTION.match(line):
            errors.append(f"第 {line_number} 行使用了非知乎分节符号: {line}")
            continue
        if ANY_MARKDOWN_HEADING.match(line):
            errors.append(f"第 {line_number} 行存在正文 Markdown 标题: {line}")
            continue

        sentence_items = prose_sentences(line)
        paragraph_chars = non_whitespace_chars(line)
        if len(sentence_items) > MAX_PARAGRAPH_SENTENCES:
            errors.append(
                f"第 {line_number} 行含 {len(sentence_items)} 句，知乎正文单个自然段最多承载 "
                f"{MAX_PARAGRAPH_SENTENCES} 句；请按注意对象、说话轮次或情绪转折重新断段"
            )
        if paragraph_chars > MAX_PARAGRAPH_CHARS:
            errors.append(
                f"第 {line_number} 行自然段过长：{paragraph_chars} 字，超过 "
                f"{MAX_PARAGRAPH_CHARS} 字阅读上限"
            )
        if EXPLICIT_DIALOGUE.search(line) and not (
            line.startswith(("「", "“")) and line.endswith(("」", "”"))
        ):
            errors.append(
                f"第 {line_number} 行把对白嵌在叙述段内；知乎正文对白必须按说话轮次独立成段"
            )
        for sentence in sentence_items:
            sentence_chars = non_whitespace_chars(sentence)
            if sentence_chars > MAX_SENTENCE_CHARS:
                errors.append(
                    f"第 {line_number} 行存在 {sentence_chars} 字超长句，超过 "
                    f"{MAX_SENTENCE_CHARS} 字；请拆出动作、错答或反应气口"
                )
            if sentence_chars > LONG_SENTENCE_CHARS:
                consecutive_long_sentences += 1
                if consecutive_long_sentences > MAX_CONSECUTIVE_LONG_SENTENCES:
                    errors.append(
                        f"第 {line_number} 行附近连续超过 {MAX_CONSECUTIVE_LONG_SENTENCES} 个长句，"
                        "缺少短促反应或对白换气"
                    )
            else:
                consecutive_long_sentences = 0

    if not sections:
        errors.append("正文至少需要一个纯数字分节标记，如 `1.`")
        return errors, sections

    expected = list(range(1, len(sections) + 1))
    if sections != expected:
        errors.append(
            "分节序号必须从 1 连续递增；"
            f"实际为 {sections}，预期为 {expected}"
        )

    return errors, sections


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate section markers and single-blank-line reading layout."
    )
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    text_path = Path(args.text).resolve()
    if not text_path.is_file():
        print("zhihu_section_format: blocked")
        print(f"- 正文不存在: {text_path}")
        return 2

    errors, sections = validate_text(read_text(text_path))
    print(f"text: {text_path}")
    print(f"sections: {len(sections)}")
    if errors:
        print("zhihu_section_format: blocked")
        for error in errors:
            print(f"- {error}")
        return 2

    print("zhihu_section_format: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
