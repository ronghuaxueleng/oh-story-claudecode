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


SECTION_RE = re.compile(r"^##\s+(?:第\s*)?(\d+)(?:\s*节)?[.、．]?(?:\s+(.*))?$")
SUBHEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
BULLET_HEADING_RE = re.compile(r"^\s*-\s+(.+?)[：:](?:\s*(.*))?$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sections(path: Path) -> list[str]:
    return [match.group(1) for line in path.read_text(encoding="utf-8").splitlines()
            if (match := SECTION_RE.match(line))]


def section_blocks(path: Path) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if match := SECTION_RE.match(raw_line):
            if current is not None:
                blocks.append(current)
            current = {
                "id": match.group(1),
                "title": str(match.group(2) or "").strip(),
                "lines": [raw_line],
            }
            continue
        if current is not None:
            current["lines"].append(raw_line)
    if current is not None:
        blocks.append(current)
    return blocks


def subsection_map(lines: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current = ""
    for raw_line in lines[1:]:
        stripped = raw_line.strip()
        if match := SUBHEADING_RE.match(raw_line):
            current = match.group(1).strip()
            result.setdefault(current, [])
            continue
        if match := BULLET_HEADING_RE.match(stripped):
            current = match.group(1).strip()
            result.setdefault(current, [])
            inline_value = str(match.group(2) or "").strip()
            if inline_value:
                result[current].append(inline_value)
            continue
        if current:
            result[current].append(raw_line)
    return result


def compact_lines(lines: list[str], *, limit: int = 2) -> list[str]:
    result: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("-", "*", ">")):
            line = line[1:].strip()
        line = re.sub(r"^\d+\.\s*", "", line)
        if not line:
            continue
        result.append(line)
        if len(result) >= limit:
            break
    return result


def join_summary(lines: list[str], *, limit: int = 2) -> str:
    values = compact_lines(lines, limit=limit)
    return "；".join(values)


def allocated_words(section_count: int, target_words: int, index: int) -> int:
    if section_count <= 0:
        return 0
    minimum = 800
    allocated = [minimum] * section_count
    delta = target_words - minimum * section_count
    if delta > 0:
        position = 0
        while delta > 0:
            allocated[position % section_count] += 1
            delta -= 1
            position += 1
    return allocated[index]


def build_section_entry(
    block: dict[str, Any],
    *,
    section_count: int,
    target_words: int,
    index: int,
) -> dict[str, Any]:
    lines = block.get("lines") if isinstance(block.get("lines"), list) else []
    parts = subsection_map(lines)
    title = str(block.get("title") or "").strip()
    opening = join_summary(
        parts.get("首段开口", [])
        or parts.get("本节开口", [])
        or parts.get("主事件", [])
        or parts.get("逐拍因果链", []),
        limit=1,
    )
    source_binding = join_summary(
        parts.get("来源绑定", [])
        or parts.get("对应来源", [])
        or parts.get("主体来源绑定", [])
        or parts.get("辅助来源绑定", [])
        or parts.get("辅助机制回声", []),
        limit=2,
    )
    events = join_summary(
        parts.get("主事件与子事件", [])
        or parts.get("子事件", [])
        or parts.get("本节主事件", [])
        or parts.get("主事件", [])
        or parts.get("逐拍因果链", []),
        limit=3,
    )
    emotion = join_summary(parts.get("情绪过程", []), limit=2)
    hook = join_summary(parts.get("节尾钩子", []) or parts.get("场末钩子", []), limit=1)
    exit_state = join_summary(
        parts.get("出口状态", [])
        or parts.get("场景出口状态", [])
        or parts.get("相邻节交接", [])
        or parts.get("场末余痛", []),
        limit=1,
    )
    performance = join_summary(
        parts.get("表演与对白", [])
        or parts.get("叙述者嘴感", [])
        or parts.get("表演证据锚点", [])
        or parts.get("对话压力交换", [])
        or parts.get("人物偏手", [])
        or parts.get("叙述者气口", []),
        limit=2,
    )
    control = join_summary(
        parts.get("控制权变化", [])
        or parts.get("冲突载体", [])
        or parts.get("本节现实争夺权", [])
        or parts.get("不可逆动作", []),
        limit=2,
    )
    return {
        "id": str(block.get("id") or ""),
        "planned_words": allocated_words(section_count, target_words, index),
        "scene_completion": events or title or "待按本节主事件完成首写",
        "opening_or_turn": opening or title or "待按本节开口起事",
        "emotion_escalation": emotion or control or "待按本节情绪过程推进",
        "end_change": hook or exit_state or "待按本节出口状态收束",
        "source_mechanism": source_binding or "待按来源绑定迁移机制",
        "source_style_granularity": performance or emotion or "待按本节表演与气口执行",
        "first_draft_style_plan": performance or hook or "待按本节首写计划执行",
    }


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
    blocks = section_blocks(outline)
    return {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "passed",
        "execution_mode": "outline_compiled",
        "target_words": target_words,
        "outline": {"path": str(outline.resolve()), "sha256": digest(outline)},
        "sections": [
            build_section_entry(
                block,
                section_count=len(blocks),
                target_words=target_words,
                index=index,
            )
            for index, block in enumerate(blocks)
        ],
    }


def validate(receipt_path: Path, draft: Path | None = None) -> list[str]:
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"容量契约不可读取: {exc}"]
    return validate_data(data, receipt_path, draft)


def validate_data(
    data: dict[str, Any],
    receipt_path: Path,
    draft: Path | None = None,
) -> list[str]:
    errors: list[str] = []
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
