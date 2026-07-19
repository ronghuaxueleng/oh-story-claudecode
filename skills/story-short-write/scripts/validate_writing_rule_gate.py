#!/usr/bin/env python3
"""Generate and validate the mandatory pre-writing rule-reading receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_RULES = (
    "references/workflow/format-and-structure.md",
    "references/anti-ai-writing.md",
    "references/craft/narrator-voice.md",
)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_rules(skill_root: Path = SKILL_ROOT) -> tuple[list[Path], list[str]]:
    errors: list[str] = []
    rules: list[Path] = []
    for relative in REQUIRED_RULES:
        path = skill_root / relative
        if not path.is_file():
            errors.append(f"缺少强制写作规则: {path}")
            continue
        rules.append(path)
    return rules, errors


def create_receipt(
    project: str,
    skill_root: Path = SKILL_ROOT,
) -> tuple[dict[str, Any], list[str]]:
    resolved_root = skill_root.resolve()
    rules, errors = discover_rules(resolved_root)
    receipt = {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "confirmed_before_outline": False,
        "confirmed_before_draft": False,
        "skill_root_at_init": str(resolved_root),
        "files": [
            {
                "path": path.relative_to(resolved_root).as_posix(),
                "sha256": sha256(path),
                "status": "pending",
                "evidence_terms": [],
                "takeaways": [],
                "used_for": [],
            }
            for path in rules
        ],
    }
    return receipt, errors


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_receipt(
    receipt_path: Path,
    output_paths: list[Path] | None = None,
    skill_root: Path = SKILL_ROOT,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    resolved_root = skill_root.resolve()
    rules, rule_errors = discover_rules(resolved_root)
    errors.extend(rule_errors)
    expected = {
        path.relative_to(resolved_root).as_posix(): path
        for path in rules
    }

    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if data.get("confirmed_before_outline") is not True:
        errors.append("confirmed_before_outline 必须为 true")
    if data.get("confirmed_before_draft") is not True:
        errors.append("confirmed_before_draft 必须为 true")

    file_entries = data.get("files")
    if not isinstance(file_entries, list):
        return errors + ["files 必须是列表"], {
            "file_count": len(expected),
            "read_count": 0,
        }

    actual = {
        str(item.get("path") or ""): item
        for item in file_entries
        if isinstance(item, dict) and str(item.get("path") or "")
    }
    for relative in sorted(set(expected) - set(actual)):
        errors.append(f"规则读取回执缺少文件项: {resolved_root / relative}")
    for relative in sorted(set(actual) - set(expected)):
        errors.append(f"规则读取回执含过期文件项: {relative}")

    read_count = 0
    for relative, path in expected.items():
        entry = actual.get(relative)
        if not entry:
            continue
        if entry.get("sha256") != sha256(path):
            errors.append(f"规则文件已变化，必须重新读取: {path}")
        if entry.get("status") != "read":
            errors.append(f"规则文件尚未标记已读: {path}")
            continue

        evidence_terms = nonempty_strings(entry.get("evidence_terms"))
        takeaways = nonempty_strings(entry.get("takeaways"))
        used_for = nonempty_strings(entry.get("used_for"))
        if not evidence_terms:
            errors.append(f"缺少规则证据词: {path}")
        else:
            source_text = read_text(path)
            missing_terms = [term for term in evidence_terms if term not in source_text]
            if missing_terms:
                errors.append(
                    f"证据词不在规则文件中: {path} -> {' / '.join(missing_terms)}"
                )
        if not takeaways:
            errors.append(f"缺少规则读取结论: {path}")
        if not used_for:
            errors.append(f"缺少规则写作用途: {path}")
        if evidence_terms and takeaways and used_for:
            read_count += 1

    for output in output_paths or []:
        resolved = output.resolve()
        if resolved.exists() and receipt_path.stat().st_mtime > resolved.stat().st_mtime:
            errors.append(f"规则读取回执晚于写作产物，属于事后补填: {resolved}")

    return errors, {
        "file_count": len(expected),
        "read_count": read_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mandatory rule-reading gate for story-short-write."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="生成待回填的规则读取回执")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--receipt", required=True)
    init_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="校验规则读取回执")
    validate_parser.add_argument("--receipt", required=True)
    validate_parser.add_argument(
        "--output",
        action="append",
        required=True,
        help="必须检查的设定、大纲或正文路径；可重复传入",
    )

    args = parser.parse_args()
    if args.command == "init":
        receipt_path = Path(args.receipt).resolve()
        if receipt_path.exists() and not args.force:
            print(f"规则读取回执已存在，拒绝覆盖: {receipt_path}")
            return 2
        receipt, errors = create_receipt(args.project)
        if errors:
            print("writing_rule_gate: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("writing_rule_gate: initialized")
        print(f"receipt: {receipt_path}")
        print(f"files: {len(receipt['files'])}")
        return 0

    receipt_path = Path(args.receipt).resolve()
    if not receipt_path.is_file():
        print(f"规则读取回执不存在: {receipt_path}")
        return 2
    errors, summary = validate_receipt(
        receipt_path,
        [Path(raw) for raw in args.output],
    )
    print(f"receipt: {receipt_path}")
    print(f"file_count: {summary['file_count']}")
    print(f"read_count: {summary['read_count']}")
    if errors:
        print("writing_rule_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("writing_rule_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
