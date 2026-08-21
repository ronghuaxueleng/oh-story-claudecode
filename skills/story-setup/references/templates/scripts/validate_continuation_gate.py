#!/usr/bin/env python3
"""Fail-closed gate for ending a persistent short-story writing task."""

from __future__ import annotations

import argparse
import importlib.util
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


def validate_initial_draft(project_dir: Path, platform: str) -> list[str]:
    errors: list[str] = []
    assets = project_dir / "写作资产"
    draft = project_dir / "正文.md"
    review_path = assets / "正文覆盖回执.json"
    module_path = Path(__file__).with_name("manage_target_prose_map.py")
    spec = importlib.util.spec_from_file_location(
        "story_short_write_prose_coverage_audit", module_path
    )
    if spec is None or spec.loader is None:
        return [f"无法加载正文覆盖校验器: {module_path}"]
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    review = load_json(review_path, "正文覆盖回执", errors)
    if review:
        errors.extend(module.validate_audit(review, project_dir, require_gate=True))
    if not draft.is_file():
        errors.append(f"正文不存在: {draft}")
        return errors
    text = draft.read_text(encoding="utf-8")
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
    blocker_type = str(data.get("blocker_type") or "").strip()
    allowed_types = {
        "network_unavailable",
        "permission_denied",
        "missing_user_supplied_input",
        "third_party_service_unavailable",
        "external_filesystem_state",
    }
    if blocker_type not in allowed_types:
        errors.append(
            "外部阻断 blocker_type 必须是真实外部依赖类型，"
            "本地 validator 错误、字段缺失、旧资产升级或工作量过大不得使用 external_blocker"
        )
    if not str(data.get("external_dependency") or "").strip():
        errors.append("外部阻断缺少 external_dependency")
    attempts = data.get("consecutive_attempts")
    if not isinstance(attempts, int) or attempts < 3:
        errors.append("同一外部阻断必须连续出现至少三轮")
    evidence = data.get("evidence")
    if (
        not isinstance(evidence, list)
        or len([item for item in evidence if str(item).strip()]) < 3
    ):
        errors.append("外部阻断至少需要三条连续尝试的可核验证据")
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
