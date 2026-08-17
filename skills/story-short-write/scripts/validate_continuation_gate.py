#!/usr/bin/env python3
"""Fail-closed gate for ending a persistent short-story writing task."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ILLEGAL_REASONS = {
    "commentary_only_yield",
    "empty_final",
    "progress_report",
    "stage_complete",
    "turn_limit",
    "file_volume",
    "goal_pause",
    "tool_wait",
}
LEGAL_REASONS = {"initial_draft_stop", "user_stop", "external_blocker"}
PURE_SECTION = re.compile(r"^(\d+)\.$")
MARKDOWN_HEADING = re.compile(r"^#{1,6}\s*\S+")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{label}不存在: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label}不是有效 JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label}必须是 JSON 对象")
        return {}
    return value


def count_fanqie(text: str) -> int:
    body = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )
    return sum(1 for char in body if not char.isspace())


def validate_zhihu(text: str) -> list[str]:
    errors: list[str] = []
    sections: list[int] = []
    nonempty_index = 0
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        nonempty_index += 1
        match = PURE_SECTION.fullmatch(line)
        if match:
            sections.append(int(match.group(1)))
            continue
        if MARKDOWN_HEADING.match(line):
            if nonempty_index == 1 and line.startswith("# ") and not line.startswith("## "):
                continue
            errors.append(f"第 {line_number} 行存在非法正文标题: {line}")
    if not sections:
        errors.append("正文缺少纯数字分节标记")
    elif sections != list(range(1, len(sections) + 1)):
        errors.append(f"正文分节不连续: {sections}")
    return errors


def draft_binding(receipt: dict[str, Any]) -> dict[str, Any]:
    direct = receipt.get("draft")
    if isinstance(direct, dict):
        return direct
    bindings = receipt.get("bindings")
    if isinstance(bindings, dict) and isinstance(bindings.get("draft"), dict):
        return bindings["draft"]
    return {}


def validate_initial_draft(project_dir: Path, platform: str) -> list[str]:
    errors: list[str] = []
    assets = project_dir / "写作资产"
    draft = project_dir / "正文.md"
    progress = load_json(assets / "逐节正文进度.json", "逐节正文进度", errors)
    prose = load_json(assets / "全文文字颗粒度契约回执.json", "全文文字合同", errors)
    emotion = load_json(assets / "全文情绪颗粒度契约回执.json", "全文情绪合同", errors)

    if progress.get("status") != "final_ready":
        errors.append(f"逐节正文进度未 final_ready: {progress.get('status')}")
    if not draft.is_file():
        errors.append(f"正文不存在: {draft}")
        return errors

    draft_sha = sha256(draft)
    if progress.get("final_draft_sha256") != draft_sha:
        errors.append("正文 SHA 与 final_ready 绑定不一致")
    sections = progress.get("sections")
    if not isinstance(sections, list) or not sections or any(
        not isinstance(item, dict) or item.get("status") != "passed"
        for item in sections
    ):
        errors.append("逐节正文进度仍有未 passed 小节")

    text = draft.read_text(encoding="utf-8")
    actual_count = count_fanqie(text)
    if progress.get("final_char_count") != actual_count:
        errors.append("正文实际字数与 final_ready 字数不一致")

    prose_binding = draft_binding(prose)
    if prose.get("gate_status") != "passed":
        errors.append("全文文字合同 gate_status 未 passed")
    if prose_binding.get("sha256") != draft_sha:
        errors.append("全文文字合同未绑定最终正文 SHA")

    emotion_binding = draft_binding(emotion)
    if emotion.get("draft_status") != "passed":
        errors.append("全文情绪合同 draft_status 未 passed")
    if emotion_binding.get("sha256") != draft_sha:
        errors.append("全文情绪合同未绑定最终正文 SHA")

    if platform == "zhihu":
        errors.extend(validate_zhihu(text))
    return errors


def validate_blocker(path: Path) -> list[str]:
    errors: list[str] = []
    data = load_json(path, "外部阻断回执", errors)
    if data.get("status") != "blocked":
        errors.append("外部阻断回执 status 必须为 blocked")
    if data.get("recoverable") is not False:
        errors.append("外部阻断必须明确 recoverable=false")
    if not str(data.get("blocking_condition") or "").strip():
        errors.append("外部阻断缺少 blocking_condition")
    attempts = data.get("consecutive_attempts")
    if not isinstance(attempts, int) or attempts < 3:
        errors.append("同一外部阻断必须连续出现至少三轮")
    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not any(str(item).strip() for item in evidence):
        errors.append("外部阻断缺少可核验证据")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument(
        "--reason",
        required=True,
        choices=sorted(LEGAL_REASONS | ILLEGAL_REASONS),
    )
    parser.add_argument("--platform", choices=("generic", "zhihu"), default="generic")
    parser.add_argument("--user-stop-confirmed", action="store_true")
    parser.add_argument("--blocker-receipt")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    errors: list[str] = []

    if args.reason in ILLEGAL_REASONS:
        errors.append(f"非法终止原因: {args.reason}")
    elif args.reason == "user_stop":
        if not args.user_stop_confirmed:
            errors.append("用户叫停必须显式传入 --user-stop-confirmed")
    elif args.reason == "external_blocker":
        if not args.blocker_receipt:
            errors.append("外部阻断必须提供 --blocker-receipt")
        else:
            errors.extend(validate_blocker(Path(args.blocker_receipt).resolve()))
    elif args.reason == "initial_draft_stop":
        errors.extend(validate_initial_draft(project_dir, args.platform))

    if errors:
        print("continuation_gate: blocked")
        print("terminal_response_forbidden: true")
        for error in errors:
            print(f"- {error}")
        return 2

    print("continuation_gate: passed")
    print(f"terminal_reason: {args.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
