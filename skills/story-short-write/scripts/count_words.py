#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Count draft words with the agreed Fanqie-style rule.

Rule:
    Remove Markdown heading lines that start with "#", then count every
    non-whitespace character in the remaining body. Chinese characters,
    punctuation, digits, letters, and Markdown symbols all count; spaces,
    line breaks, and tabs do not.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def count_fanqie(text: str) -> int:
    """Return the Fanqie-style body word count for one Markdown text."""
    body_lines: list[str] = []
    for line in text.split("\n"):
        if line.strip().startswith("#"):
            continue
        body_lines.append(line)
    body = "\n".join(body_lines)
    return sum(1 for char in body if not char.isspace())


def collect_files(values: list[str]) -> list[Path]:
    """Collect Markdown files from explicit files, directories, or glob patterns."""
    if not values:
        values = ["*.md"]

    files: set[Path] = set()
    for value in values:
        path = Path(value)
        if path.is_dir():
            files.update(item for item in path.glob("*.md") if item.is_file())
        elif path.is_file():
            files.add(path)
        else:
            files.update(Path(item) for item in glob.glob(value) if Path(item).is_file())
    return sorted(files)


def count_file(path: Path) -> int:
    """Read a UTF-8 file and count it with count_fanqie."""
    return count_fanqie(path.read_text(encoding="utf-8"))


def build_result(files: list[Path]) -> dict[str, object]:
    """Build a structured count result for CLI text and JSON output."""
    items = []
    total = 0
    for path in files:
        count = count_file(path)
        total += count
        items.append(
            {
                "path": str(path),
                "name": path.name,
                "word_count": count,
            }
        )
    return {
        "rule": "fanqie_non_whitespace_without_markdown_headings",
        "file_count": len(items),
        "total_word_count": total,
        "total_k_words": round(total / 1000, 1),
        "files": items,
    }


def print_table(result: dict[str, object]) -> None:
    """Print the human-readable table used during writing tasks."""
    files = result["files"]
    assert isinstance(files, list)
    print("=" * 60)
    print("番茄小说字数统计")
    print("=" * 60)
    print(f"{'章节文件':<38} {'字数':>8}")
    print("-" * 60)
    for item in files:
        assert isinstance(item, dict)
        name = str(item["name"])
        if len(name) > 36:
            name = name[:33] + "..."
        print(f"{name:<38} {int(item['word_count']):>8}")
    print("-" * 60)
    print(f"{'合计':<38} {int(result['total_word_count']):>8}")
    print("=" * 60)
    print(f"\n共 {int(result['file_count'])} 章，总计 {int(result['total_word_count'])} 字")
    print(f"按番茄签约标准（千字计费）：{float(result['total_k_words']):.1f} 千字")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Markdown file, directory, or glob pattern")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    args = parser.parse_args()

    files = collect_files(args.paths)
    if not files:
        message = "没有找到任何 .md 文件"
        if args.json:
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2))
        else:
            print(f"⚠️  {message}")
            print("   用法: python3 count_words.py [文件或目录...]")
        return 1

    result = build_result(files)
    if args.json:
        print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    else:
        print_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
