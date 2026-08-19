#!/usr/bin/env python3
"""Merge standard level-2 Markdown sections while preserving user-only content."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SECTION_RE = re.compile(r"(?m)^## .+$")


def split_document(text: str) -> tuple[str, list[tuple[str, str]]]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return text, []
    preamble = text[: matches[0].start()]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start() : end]
        sections.append((match.group(0).strip(), block))
    return preamble, sections


def merge_sections(existing: str, template: str) -> str:
    existing_preamble, existing_sections = split_document(existing)
    _, template_sections = split_document(template)
    template_map = dict(template_sections)
    merged: list[str] = []
    seen: set[str] = set()

    for heading, block in existing_sections:
        merged.append(template_map.get(heading, block))
        seen.add(heading)
    for heading, block in template_sections:
        if heading not in seen:
            merged.append(block)

    preamble = existing_preamble.rstrip()
    body = "".join(merged).strip()
    if not body:
        return existing
    return f"{preamble}\n\n{body}\n" if preamble else f"{body}\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    existing = Path(args.existing)
    template = Path(args.template)
    output = Path(args.output)
    output.write_text(
        merge_sections(existing.read_text(encoding="utf-8"), template.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
