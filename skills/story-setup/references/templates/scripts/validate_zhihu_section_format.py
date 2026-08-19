#!/usr/bin/env python3
"""Validate Zhihu/Yanyan short-story section markers."""

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

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        nonempty_index += 1
        pure_match = PURE_SECTION.fullmatch(line)
        if pure_match:
            sections.append(int(pure_match.group(1)))
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
            if nonempty_index == 1 and line.startswith("# ") and not line.startswith("## "):
                continue
            errors.append(f"第 {line_number} 行存在正文 Markdown 标题: {line}")

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
        description="Validate pure numeric section markers for Zhihu/Yanyan drafts."
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
