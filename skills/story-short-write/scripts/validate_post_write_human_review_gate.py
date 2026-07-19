#!/usr/bin/env python3
"""Generate and validate the mandatory post-write human semantic review receipt."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_HUMAN_CHECKS = (
    "author_motive_substitution",
    "narrator_voice_boundary",
    "narrator_voice_distribution",
    "redundant_explanation",
    "observable_scene_basis",
    "dialogue_efficiency",
    "long_window_dialogue_efficiency",
    "cross_block_rhythm_contrast",
    "full_text_legacy_rescan",
)

NARRATOR_OR_AUTHOR = {"narrator_voice", "author_summary", "neutral"}


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewable_units(text: str) -> list[dict[str, Any]]:
    kept_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    flattened = "\n".join(kept_lines)
    units: list[dict[str, Any]] = []
    cursor = 0
    canonical_cursor = 0
    for match in re.finditer(
        r'.*?(?:[。！？?!](?:["”’』】])?|$)',
        flattened,
        flags=re.DOTALL,
    ):
        quote = match.group(0).strip()
        if not quote:
            continue
        position = text.find(quote, cursor)
        if position < 0:
            position = text.find(quote)
        line_number = text.count("\n", 0, max(position, 0)) + 1
        canonical = re.sub(r"\s+", "", quote)
        units.append(
            {
                "line": line_number,
                "quote": quote,
                "canonical": canonical,
                "canonical_start": canonical_cursor,
                "canonical_end": canonical_cursor + len(canonical),
            }
        )
        canonical_cursor += len(canonical)
        if position >= 0:
            cursor = position + len(quote)
    return units


def changed_lines(base_text: str, current_text: str) -> list[dict[str, Any]]:
    base_units = reviewable_units(base_text)
    current_units = reviewable_units(current_text)
    matcher = difflib.SequenceMatcher(
        a=[item["canonical"] for item in base_units],
        b=[item["canonical"] for item in current_units],
        autojunk=False,
    )
    changed_indexes: set[int] = set()
    for tag, _, _, current_start, current_end in matcher.get_opcodes():
        if tag in {"insert", "replace"}:
            changed_indexes.update(range(current_start, current_end))

    changed: list[dict[str, Any]] = []
    for index, unit in enumerate(current_units):
        if index not in changed_indexes:
            continue
        changed.append(
            {
                "line": unit["line"],
                "quote": unit["quote"],
                "status": "pending",
                "scene_observable_basis": "",
                "narrator_or_author": "pending",
                "redundant_explanation": None,
                "substitutes_character_motive": None,
                "decision": "pending",
                "reason": "",
            }
        )
    return changed


def create_receipt(
    project: str,
    text_path: Path,
    base_text_path: Path | None = None,
) -> dict[str, Any]:
    resolved_text = text_path.resolve()
    if not resolved_text.is_file():
        raise FileNotFoundError(f"正文不存在: {resolved_text}")

    resolved_base = base_text_path.resolve() if base_text_path else None
    if resolved_base and not resolved_base.is_file():
        raise FileNotFoundError(f"母稿不存在: {resolved_base}")

    current_text = read_text(resolved_text)
    base_text = read_text(resolved_base) if resolved_base else ""
    return {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "review_mode": "revision_diff" if resolved_base else "full_text",
        "text": {
            "path": str(resolved_text),
            "sha256": sha256(resolved_text),
        },
        "base_text": (
            {
                "path": str(resolved_base),
                "sha256": sha256(resolved_base),
            }
            if resolved_base
            else None
        ),
        "automation_limits_acknowledged": False,
        "reviewed_full_text": False,
        "confirmed_after_final_revision": False,
        "automated_scan": {
            "status": "pending",
            "artifacts": [],
            "summary": "",
        },
        "human_checks": [
            {
                "id": check_id,
                "status": "pending",
                "evidence": [],
                "conclusion": "",
            }
            for check_id in REQUIRED_HUMAN_CHECKS
        ],
        "changed_sentence_reviews": changed_lines(base_text, current_text)
        if resolved_base
        else [],
    }


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_receipt(
    receipt_path: Path,
    text_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    resolved_text = text_path.resolve()
    if not resolved_text.is_file():
        return [f"正文不存在: {resolved_text}"], {
            "human_check_count": len(REQUIRED_HUMAN_CHECKS),
            "reviewed_human_checks": 0,
            "changed_sentence_count": 0,
            "reviewed_changed_sentences": 0,
        }

    current_text = read_text(resolved_text)
    text_info = data.get("text") if isinstance(data.get("text"), dict) else {}
    if str(text_info.get("path") or "") != str(resolved_text):
        errors.append("回执绑定的正文路径与当前正文不一致")
    if text_info.get("sha256") != sha256(resolved_text):
        errors.append("正文已变化，必须重新执行人工语义复核")

    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if data.get("automation_limits_acknowledged") is not True:
        errors.append("必须确认自动脚本不能替代人工语义判断")
    if data.get("reviewed_full_text") is not True:
        errors.append("必须确认已人工复扫全文")
    if data.get("confirmed_after_final_revision") is not True:
        errors.append("必须确认人工复核发生在最终一次正文修改之后")

    automated_scan = data.get("automated_scan")
    if not isinstance(automated_scan, dict):
        errors.append("automated_scan 必须是对象")
    else:
        if automated_scan.get("status") != "completed":
            errors.append("自动脚本预扫尚未完成")
        if not nonempty_strings(automated_scan.get("artifacts")):
            errors.append("自动脚本预扫缺少产物记录")
        if not str(automated_scan.get("summary") or "").strip():
            errors.append("自动脚本预扫缺少结果摘要")

    human_entries = data.get("human_checks")
    actual_human: dict[str, dict[str, Any]] = {}
    if isinstance(human_entries, list):
        actual_human = {
            str(item.get("id") or ""): item
            for item in human_entries
            if isinstance(item, dict) and str(item.get("id") or "")
        }
    else:
        errors.append("human_checks 必须是列表")

    for check_id in sorted(set(REQUIRED_HUMAN_CHECKS) - set(actual_human)):
        errors.append(f"缺少人工检查项: {check_id}")
    for check_id in sorted(set(actual_human) - set(REQUIRED_HUMAN_CHECKS)):
        errors.append(f"存在未知人工检查项: {check_id}")

    reviewed_human_checks = 0
    for check_id in REQUIRED_HUMAN_CHECKS:
        entry = actual_human.get(check_id)
        if not entry:
            continue
        if entry.get("status") != "passed":
            errors.append(f"人工检查项尚未通过: {check_id}")
            continue
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"人工检查项缺少正文证据: {check_id}")
            continue
        valid_evidence = True
        for index, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                errors.append(f"人工证据格式错误: {check_id}[{index}]")
                valid_evidence = False
                continue
            quote = str(item.get("quote") or "").strip()
            judgment = str(item.get("judgment") or "").strip()
            action = str(item.get("action") or "").strip()
            if not quote or quote not in current_text:
                errors.append(f"人工证据原句不在正文中: {check_id}[{index}]")
                valid_evidence = False
            if not judgment:
                errors.append(f"人工证据缺少语义判断: {check_id}[{index}]")
                valid_evidence = False
            if action not in {"keep", "revise", "delete"}:
                errors.append(f"人工证据 action 非法: {check_id}[{index}]")
                valid_evidence = False
        if not str(entry.get("conclusion") or "").strip():
            errors.append(f"人工检查项缺少结论: {check_id}")
            valid_evidence = False
        if valid_evidence:
            reviewed_human_checks += 1

    base_info = data.get("base_text")
    expected_changed: list[dict[str, Any]] = []
    if isinstance(base_info, dict):
        base_path = Path(str(base_info.get("path") or "")).resolve()
        if not base_path.is_file():
            errors.append(f"母稿不存在: {base_path}")
        else:
            if base_info.get("sha256") != sha256(base_path):
                errors.append("母稿已变化，必须重新生成人工复核清单")
            expected_changed = changed_lines(read_text(base_path), current_text)
    elif data.get("review_mode") == "revision_diff":
        errors.append("局部或专项回炉必须绑定母稿")

    changed_entries = data.get("changed_sentence_reviews")
    if not isinstance(changed_entries, list):
        changed_entries = []
        errors.append("changed_sentence_reviews 必须是列表")

    expected_keys = {(item["line"], item["quote"]) for item in expected_changed}
    actual_keys = {
        (item.get("line"), str(item.get("quote") or ""))
        for item in changed_entries
        if isinstance(item, dict)
    }
    for line, quote in sorted(expected_keys - actual_keys):
        errors.append(f"改写句缺少人工复核: 第 {line} 行 {quote}")
    for line, quote in sorted(actual_keys - expected_keys):
        errors.append(f"人工复核含过期改写句: 第 {line} 行 {quote}")

    reviewed_changed_sentences = 0
    for index, item in enumerate(changed_entries, start=1):
        if not isinstance(item, dict):
            errors.append(f"改写句复核格式错误: [{index}]")
            continue
        if item.get("status") != "reviewed":
            errors.append(f"改写句尚未人工复核: 第 {item.get('line')} 行")
            continue
        valid = True
        if not str(item.get("scene_observable_basis") or "").strip():
            errors.append(f"改写句缺少现场可观察依据: 第 {item.get('line')} 行")
            valid = False
        if item.get("narrator_or_author") not in NARRATOR_OR_AUTHOR:
            errors.append(f"改写句未区分叙述者与作者站位: 第 {item.get('line')} 行")
            valid = False
        if not isinstance(item.get("redundant_explanation"), bool):
            errors.append(f"改写句未判断是否多余解释: 第 {item.get('line')} 行")
            valid = False
        if not isinstance(item.get("substitutes_character_motive"), bool):
            errors.append(f"改写句未判断是否代判人物动机: 第 {item.get('line')} 行")
            valid = False
        if item.get("decision") != "keep":
            errors.append(
                f"当前正文仍含待 revise/delete 的改写句，必须先改正文再重建回执: 第 {item.get('line')} 行"
            )
            valid = False
        if not str(item.get("reason") or "").strip():
            errors.append(f"改写句缺少保留理由: 第 {item.get('line')} 行")
            valid = False
        if valid:
            reviewed_changed_sentences += 1

    return errors, {
        "human_check_count": len(REQUIRED_HUMAN_CHECKS),
        "reviewed_human_checks": reviewed_human_checks,
        "changed_sentence_count": len(expected_changed),
        "reviewed_changed_sentences": reviewed_changed_sentences,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mandatory post-write human semantic review gate."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="生成人工语义复核回执")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--text", required=True)
    init_parser.add_argument("--base-text")
    init_parser.add_argument("--receipt", required=True)
    init_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="校验人工语义复核回执")
    validate_parser.add_argument("--receipt", required=True)
    validate_parser.add_argument("--text", required=True)

    args = parser.parse_args()
    receipt_path = Path(args.receipt).resolve()
    if args.command == "init":
        if receipt_path.exists() and not args.force:
            print(f"人工复核回执已存在，拒绝覆盖: {receipt_path}")
            return 2
        try:
            receipt = create_receipt(
                args.project,
                Path(args.text),
                Path(args.base_text) if args.base_text else None,
            )
        except FileNotFoundError as exc:
            print("post_write_human_review_gate: blocked")
            print(f"- {exc}")
            return 2
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("post_write_human_review_gate: initialized")
        print(f"receipt: {receipt_path}")
        print(f"mode: {receipt['review_mode']}")
        print(f"changed_sentences: {len(receipt['changed_sentence_reviews'])}")
        return 0

    if not receipt_path.is_file():
        print(f"人工复核回执不存在: {receipt_path}")
        return 2
    errors, summary = validate_receipt(receipt_path, Path(args.text))
    print(f"receipt: {receipt_path}")
    print(f"human_checks: {summary['reviewed_human_checks']}/{summary['human_check_count']}")
    print(
        "changed_sentences: "
        f"{summary['reviewed_changed_sentences']}/{summary['changed_sentence_count']}"
    )
    if errors:
        print("post_write_human_review_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("post_write_human_review_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
