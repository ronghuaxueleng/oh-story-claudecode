#!/usr/bin/env python3
"""Render story-setup placeholders without treating names as regular expressions."""

from __future__ import annotations

import argparse
from pathlib import Path


def render(text: str, project_name: str, book_name: str | None) -> str:
    rendered = text.replace("{项目名}", project_name)
    if book_name:
        rendered = rendered.replace("{书名}", book_name)
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--book-name")
    args = parser.parse_args()
    source = Path(args.template)
    output = Path(args.output)
    output.write_text(
        render(source.read_text(encoding="utf-8"), args.project_name, args.book_name),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
