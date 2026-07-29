#!/usr/bin/env python3
"""Prevent under-scoped first drafts by locking scene and word capacity before prose."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(r"^##\s+(?:第)?(\d+)(?:[.、．]|节)")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sections(path: Path) -> list[str]:
    return [match.group(1) for line in path.read_text(encoding="utf-8").splitlines()
            if (match := SECTION_RE.match(line))]


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def count_story_chars(path: Path) -> int:
    return sum(
        len(re.sub(r"\s+", "", line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


def init(project: str, outline: Path, target_words: int) -> dict[str, Any]:
    if not outline.is_file():
        raise FileNotFoundError(f"细纲不存在: {outline}")
    return {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "target_words": target_words,
        "outline": {"path": str(outline.resolve()), "sha256": digest(outline)},
        "sections": [
            {
                "id": section,
                "planned_words": 0,
                "scene_completion": "",
                "opening_or_turn": "",
                "emotion_escalation": "",
                "end_change": "",
                "source_mechanism": "",
                "source_style_granularity": "",
                "first_draft_style_plan": "",
            }
            for section in sections(outline)
        ],
    }


def validate(receipt_path: Path, draft: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"容量契约不可读取: {exc}"]
    if data.get("gate_status") != "passed":
        errors.append("容量契约 gate_status 必须为 passed")
    target = data.get("target_words")
    if not isinstance(target, int) or not 9000 <= target <= 13000:
        errors.append("短篇首稿目标字数必须在 9000-13000 之间")
    outline = data.get("outline")
    if not isinstance(outline, dict):
        return [*errors, "容量契约缺少 outline 绑定"]
    outline_path = Path(str(outline.get("path") or ""))
    if not outline_path.is_file():
        return [*errors, f"容量契约绑定的细纲不存在: {outline_path}"]
    if outline.get("sha256") != digest(outline_path):
        errors.append("细纲已变化，必须重建容量契约")
    expected = sections(outline_path)
    planned = data.get("sections")
    if not isinstance(planned, list):
        return [*errors, "容量契约 sections 必须为列表"]
    ids = [str(item.get("id") or "") for item in planned if isinstance(item, dict)]
    if ids != expected:
        errors.append("容量契约小节必须与细纲的连续编号完全一致")
    if not 8 <= len(expected) <= 15:
        errors.append("首稿细纲必须有 8-15 节；不足时先扩场，不得直接写正文")
    total = 0
    for item in planned:
        if not isinstance(item, dict):
            errors.append("容量契约含非对象小节")
            continue
        words = item.get("planned_words")
        if not isinstance(words, int) or words < 800:
            errors.append(f"第 {item.get('id')} 节 planned_words 必须不少于 800")
        else:
            total += words
        for field in (
            "scene_completion",
            "opening_or_turn",
            "emotion_escalation",
            "end_change",
            "source_mechanism",
            "source_style_granularity",
            "first_draft_style_plan",
        ):
            if not nonempty(item.get(field)):
                errors.append(f"第 {item.get('id')} 节缺少 {field}")
    if isinstance(target, int) and not target * 0.9 <= total <= target * 1.1:
        errors.append(f"小节预算合计 {total} 未覆盖目标字数 {target} 的 90%-110%")
    if draft is not None:
        if not draft.is_file():
            errors.append(f"正文不存在: {draft}")
        elif isinstance(target, int) and count_story_chars(draft) < target * 0.85:
            errors.append(f"正文仅 {count_story_chars(draft)} 字，低于首稿目标 {target} 的 85%")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate first-draft scene and word capacity.")
    subs = parser.add_subparsers(dest="command", required=True)
    init_parser = subs.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--outline", required=True)
    init_parser.add_argument("--target-words", required=True, type=int)
    init_parser.add_argument("--receipt", required=True)
    init_parser.add_argument("--force", action="store_true")
    validate_parser = subs.add_parser("validate")
    validate_parser.add_argument("--receipt", required=True)
    validate_parser.add_argument("--draft")
    args = parser.parse_args()
    if args.command == "init":
        receipt = Path(args.receipt)
        if receipt.exists() and not args.force:
            print(f"容量契约已存在，拒绝覆盖: {receipt}")
            return 2
        data = init(args.project, Path(args.outline), args.target_words)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"draft_capacity_contract: initialized ({len(data['sections'])} sections)")
        return 0
    errors = validate(Path(args.receipt), Path(args.draft) if args.draft else None)
    if errors:
        print("draft_capacity_contract: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("draft_capacity_contract: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
