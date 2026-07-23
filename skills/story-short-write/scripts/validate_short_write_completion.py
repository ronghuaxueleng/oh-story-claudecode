#!/usr/bin/env python3
"""Persist and validate story-short-write completion state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_CHECK_LABELS = {
    "writing_rule_gate",
    "source_read_gate",
    "rule_execution_gate",
    "sequence_contract",
    "opening_contract",
    "pre_window_revision",
    "model_segmentation",
    "formal_audit",
    "post_write_human_review",
    "anti_false_pass_review",
}
IMITATION_REQUIRED_CHECK_LABELS = {
    "source_baseline_audit",
}
VALID_STATUSES = {"active", "complete", "paused", "blocked"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def resolve_path(raw: str, project: Path) -> Path:
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (project / path).resolve()


def dotted_get(data: Any, dotted: str) -> Any:
    current = data
    for part in dotted.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(dotted)
    return current


def validate_check(check: dict[str, Any], project: Path) -> list[str]:
    label = str(check.get("label") or "<missing-label>")
    kind = str(check.get("kind") or "")
    raw_path = str(check.get("path") or "")
    if not raw_path:
        return [f"{label}: 缺少 path"]
    path = resolve_path(raw_path, project)
    if not path.is_file():
        return [f"{label}: 文件不存在: {path}"]
    if kind == "file_exists":
        return []
    if kind != "json_field":
        return [f"{label}: kind 无效: {kind}"]
    field = str(check.get("field") or "")
    if not field:
        return [f"{label}: 缺少 field"]
    try:
        actual = dotted_get(read_json(path), field)
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"{label}: JSON 无效: {exc}"]
    except KeyError:
        return [f"{label}: 缺少字段 {field}"]
    expected = check.get("expected")
    if actual != expected:
        return [f"{label}: {field}={actual!r}，期望 {expected!r}"]
    return []


def validate_state(path: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"状态文件无法读取: {exc}"]
    if data.get("workflow") != "story-short-write":
        errors.append("workflow 必须为 story-short-write")
    status = str(data.get("status") or "")
    if status not in VALID_STATUSES:
        errors.append(f"status 无效: {status!r}")
    project_raw = str(data.get("project_path") or "")
    project = resolve_path(project_raw, path.parent) if project_raw else path.parent.parent
    if not project.is_dir():
        errors.append(f"project_path 不存在: {project}")
    checks = data.get("checks")
    if not isinstance(checks, list):
        checks = []
        errors.append("checks 必须是数组")
    labels = [str(item.get("label") or "") for item in checks if isinstance(item, dict)]
    required_labels = set(REQUIRED_CHECK_LABELS)
    if data.get("imitation_mode") is True:
        required_labels.update(IMITATION_REQUIRED_CHECK_LABELS)
    missing = sorted(required_labels - set(labels))
    duplicate = sorted({label for label in labels if label and labels.count(label) > 1})
    if missing:
        errors.append(f"缺少完成检查: {' / '.join(missing)}")
    if duplicate:
        errors.append(f"重复完成检查: {' / '.join(duplicate)}")
    for check in checks:
        if not isinstance(check, dict):
            errors.append("checks 含非对象条目")
            continue
        if status in {"active", "complete"}:
            errors.extend(validate_check(check, project))
    if status == "paused" and not str(data.get("pause_reason") or "").strip():
        errors.append("paused 状态缺少 pause_reason")
    if status == "blocked":
        blocker = data.get("blocker")
        if not isinstance(blocker, dict):
            errors.append("blocked 状态缺少 blocker")
        else:
            attempts = blocker.get("attempts")
            if not isinstance(attempts, list) or len(attempts) < 3:
                errors.append("blocked 状态至少需要 3 条自主排查记录")
            for field in ("reason", "evidence", "resume_entry"):
                if not str(blocker.get(field) or "").strip():
                    errors.append(f"blocked 状态缺少 blocker.{field}")
    return data, errors


def write_state(path: Path, data: dict[str, Any]) -> None:
    data["updated_at"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_state(path: Path, project: Path, force: bool) -> int:
    if path.exists() and not force:
        print(f"状态文件已存在，拒绝覆盖: {path}")
        return 2
    checks = [
        {
            "label": label,
            "kind": "json_field",
            "path": "",
            "field": "",
            "expected": "passed",
        }
        for label in sorted(REQUIRED_CHECK_LABELS)
    ]
    write_state(
        path,
        {
            "version": "1.0",
            "workflow": "story-short-write",
            "project_path": str(project.resolve()),
            "status": "active",
            "imitation_mode": False,
            "started_at": now_iso(),
            "checks": checks,
            "next_action": "填写全部检查路径并继续执行当前未完成门禁。",
            "pause_reason": "",
            "blocker": {},
        },
    )
    print(f"short_write_completion: initialized\nstate: {path}")
    return 0


def discover_states(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.glob("**/写作资产/短篇全流程状态.json")
        if ".git" not in path.parts
    )


def hook_result(root: Path) -> int:
    blocked: list[str] = []
    for path in discover_states(root):
        data, errors = validate_state(path)
        status = str(data.get("status") or "")
        if status == "complete" and not errors:
            continue
        if status in {"paused", "blocked"} and not errors:
            continue
        next_action = str(data.get("next_action") or "继续执行第一个未通过的完成检查。")
        details = errors[:6] or [f"status={status!r}，尚未执行 mark-complete"]
        blocked.append(
            f"{path}: " + "；".join(details) + f"。下一步：{next_action}"
        )
    if not blocked:
        print(json.dumps({"continue": True}, ensure_ascii=False))
        return 0
    reason = (
        "story-short-write 全流程仍处于 active/失效状态，禁止阶段性结束。"
        "不得只报告未完成；立即继续真实执行、回修或复验。\\n- "
        + "\\n- ".join(blocked)
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--state", required=True)
    init.add_argument("--force", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--state", required=True)
    complete = sub.add_parser("mark-complete")
    complete.add_argument("--state", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("--state", required=True)
    hook = sub.add_parser("hook")
    hook.add_argument("--root", required=True)
    args = parser.parse_args()

    if args.command == "init":
        return init_state(Path(args.state).resolve(), Path(args.project).resolve(), args.force)
    if args.command == "hook":
        return hook_result(Path(args.root).resolve())

    state_path = Path(args.state).resolve()
    data, errors = validate_state(state_path)
    if args.command == "validate":
        print(f"state: {state_path}")
        if errors:
            print("short_write_completion: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print(f"short_write_completion: {data.get('status')}")
        return 0
    if args.command == "mark-complete":
        if data.get("status") in {"paused", "blocked"}:
            project = Path(str(data.get("project_path") or state_path.parent.parent)).resolve()
            for check in data.get("checks", []):
                if isinstance(check, dict):
                    errors.extend(validate_check(check, project))
        if errors:
            print("short_write_completion: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        data["status"] = "complete"
        data["completed_at"] = now_iso()
        data["next_action"] = ""
        write_state(state_path, data)
        print("short_write_completion: complete")
        return 0
    data["status"] = "active"
    data["pause_reason"] = ""
    data["blocker"] = {}
    write_state(state_path, data)
    print("short_write_completion: active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
