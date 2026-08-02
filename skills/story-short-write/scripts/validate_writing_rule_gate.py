#!/usr/bin/env python3
"""Generate and validate the mandatory pre-writing rule-reading receipt."""

from __future__ import annotations

import argparse
import copy
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
RULE_REVIEW_TASK_VERSION = "1.0"
RULE_REVIEW_TASK_KIND = "writing_rule_review_task"
RULE_REVIEW_RESULT_KIND = "writing_rule_review_result"


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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


def build_rule_review_task(
    receipt_path: Path,
    skill_root: Path = SKILL_ROOT,
) -> tuple[dict[str, Any], list[str]]:
    if not receipt_path.is_file():
        return {}, [f"写作规则读取回执不存在: {receipt_path}"]
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"写作规则读取回执不是合法 JSON: {receipt_path}: {exc}"]
    if not isinstance(receipt, dict):
        return {}, [f"写作规则读取回执顶层必须是对象: {receipt_path}"]

    resolved_root = skill_root.resolve()
    rules, errors = discover_rules(resolved_root)
    if errors:
        return {}, errors
    receipt_entries = {
        str(item.get("path") or ""): item
        for item in receipt.get("files", [])
        if isinstance(item, dict)
    }
    task_files: list[dict[str, Any]] = []
    for path in rules:
        relative = path.relative_to(resolved_root).as_posix()
        entry = receipt_entries.get(relative)
        if not entry:
            errors.append(f"写作规则读取回执缺少文件项: {path}")
            continue
        current_sha = sha256(path)
        if entry.get("sha256") != current_sha:
            errors.append(f"规则文件已变化，必须重新初始化读取回执: {path}")
            continue
        task_files.append(
            {
                "path": relative,
                "sha256": current_sha,
                "content": read_text(path),
                "review": {
                    "status": "read",
                    "evidence_terms": [],
                    "takeaways": [],
                    "used_for": [],
                },
            }
        )
    if errors:
        return {}, errors
    task = {
        "version": RULE_REVIEW_TASK_VERSION,
        "kind": RULE_REVIEW_TASK_KIND,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "receipt": {
            "path": str(receipt_path.resolve()),
            "sha256": sha256(receipt_path),
        },
        "instructions": [
            "完整读取每个 content，逐文件填写 review。",
            "evidence_terms 必须逐字存在于当前文件，不得凭记忆改写。",
            "takeaways 和 used_for 必须结合当前写作任务，不得留空。",
            "只填写独立输出文件，禁止直接修改正式写作规则读取回执。",
        ],
        "files": task_files,
        "result_template": {
            "version": RULE_REVIEW_TASK_VERSION,
            "kind": RULE_REVIEW_RESULT_KIND,
            "task_sha256": "填写本任务文件 SHA256",
            "receipt_sha256": sha256(receipt_path),
            "reviews": [
                {
                    "path": item["path"],
                    "review": copy.deepcopy(item["review"]),
                }
                for item in task_files
            ],
        },
    }
    return task, []


def apply_rule_review_result(
    receipt_path: Path,
    task_path: Path,
    result_path: Path,
    output_paths: list[Path] | None = None,
    skill_root: Path = SKILL_ROOT,
) -> list[str]:
    errors: list[str] = []
    for label, path in (
        ("写作规则读取回执", receipt_path),
        ("规则语义输入", task_path),
        ("规则语义输出", result_path),
    ):
        if not path.is_file():
            errors.append(f"{label}不存在: {path}")
    if errors:
        return errors
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        task = json.loads(task_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"规则语义回填文件不是合法 JSON: {exc}"]
    for label, data in (
        ("写作规则读取回执", receipt),
        ("规则语义输入", task),
        ("规则语义输出", result),
    ):
        if not isinstance(data, dict):
            errors.append(f"{label}顶层必须是对象")
    if errors:
        return errors
    if task.get("kind") != RULE_REVIEW_TASK_KIND:
        errors.append("规则语义输入 kind 错误")
    if result.get("kind") != RULE_REVIEW_RESULT_KIND:
        errors.append("规则语义输出 kind 错误")
    if task.get("version") != RULE_REVIEW_TASK_VERSION:
        errors.append("规则语义输入版本过期")
    if result.get("version") != RULE_REVIEW_TASK_VERSION:
        errors.append("规则语义输出版本过期")
    current_receipt_sha = sha256(receipt_path)
    task_receipt = task.get("receipt")
    if not isinstance(task_receipt, dict):
        errors.append("规则语义输入 receipt 必须是对象")
    elif task_receipt.get("sha256") != current_receipt_sha:
        errors.append("写作规则读取回执已变化，必须重新导出规则语义输入")
    if result.get("receipt_sha256") != current_receipt_sha:
        errors.append("规则语义输出绑定的写作规则读取回执已过期")
    if result.get("task_sha256") != sha256(task_path):
        errors.append("规则语义输出绑定的输入任务 SHA 不一致")

    task_items = {
        str(item.get("path") or ""): item
        for item in task.get("files", [])
        if isinstance(item, dict) and str(item.get("path") or "")
    }
    raw_reviews = result.get("reviews")
    if not isinstance(raw_reviews, list):
        errors.append("规则语义输出 reviews 必须是数组")
        raw_reviews = []
    result_items: dict[str, dict[str, Any]] = {}
    for item in raw_reviews:
        if not isinstance(item, dict):
            errors.append("规则语义输出 reviews 只能包含对象")
            continue
        relative = str(item.get("path") or "").strip()
        if not relative:
            errors.append("规则语义输出存在缺少 path 的 review")
        elif relative in result_items:
            errors.append(f"规则语义输出存在重复 review: {relative}")
        else:
            result_items[relative] = item
    missing = sorted(set(task_items) - set(result_items))
    extra = sorted(set(result_items) - set(task_items))
    if missing:
        errors.append("规则语义输出缺少文件: " + ", ".join(missing))
    if extra:
        errors.append("规则语义输出包含未选文件: " + ", ".join(extra))
    if errors:
        return errors

    candidate = copy.deepcopy(receipt)
    candidate_entries = {
        str(item.get("path") or ""): item
        for item in candidate.get("files", [])
        if isinstance(item, dict)
    }
    resolved_root = skill_root.resolve()
    for relative, task_item in task_items.items():
        entry = candidate_entries.get(relative)
        if not entry:
            errors.append(f"写作规则读取回执缺少文件项: {relative}")
            continue
        path = resolved_root / relative
        if not path.is_file():
            errors.append(f"规则文件不存在: {path}")
            continue
        if task_item.get("sha256") != sha256(path):
            errors.append(f"规则文件已变化，必须重新导出规则语义输入: {path}")
            continue
        review = result_items[relative].get("review")
        if not isinstance(review, dict):
            errors.append(f"规则语义输出 review 必须是对象: {relative}")
            continue
        entry.update(copy.deepcopy(review))
    if errors:
        return errors
    candidate["gate_status"] = "passed"
    candidate["confirmed_before_outline"] = True
    candidate["confirmed_before_draft"] = True

    temporary = receipt_path.with_name(f".{receipt_path.name}.review.tmp")
    atomic_write_json(temporary, candidate)
    validation_errors, _ = validate_receipt(
        temporary,
        output_paths,
        resolved_root,
    )
    if validation_errors:
        temporary.unlink(missing_ok=True)
        return validation_errors
    temporary.replace(receipt_path)
    return []


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
