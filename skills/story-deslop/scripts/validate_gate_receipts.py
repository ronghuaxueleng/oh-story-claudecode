#!/usr/bin/env python3
"""
校验第二闸门回执是否填写完整、结构是否自洽。
默认只做结构校验；加 --require-executed / --require-complete 时再提高严格度。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_STATUS = {"pending", "passed", "failed"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def count_structured_checks(structured: dict) -> dict:
    passed = failed = pending = 0
    for item in structured.get("common_errors", []) + structured.get("forbidden_actions", []) + structured.get("checks", []):
        status = item.get("status")
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
        else:
            pending += 1
    for item in structured.get("required_steps", []):
        done = item.get("done")
        if done is True:
            passed += 1
        elif done is False:
            pending += 1
    return {
        "passed_count": passed,
        "failed_count": failed,
        "pending_count": pending,
        "hard_fail_triggered": failed > 0,
    }


def validate_rewrite_gate(data: dict, require_complete: bool) -> list[str]:
    errors: list[str] = []
    structured = data.get("structured_checks", {})
    force_points = structured.get("force_points", {})
    if not isinstance(force_points.get("hurt_facts"), list) or len(force_points.get("hurt_facts", [])) != 3:
        errors.append("rewrite_gate.force_points.hurt_facts 必须是长度为 3 的列表")
    if not isinstance(force_points.get("bias_orders"), list) or len(force_points.get("bias_orders", [])) != 2:
        errors.append("rewrite_gate.force_points.bias_orders 必须是长度为 2 的列表")
    if "undignified_emotion" not in force_points:
        errors.append("rewrite_gate.force_points.undignified_emotion 缺失")

    must_keep = structured.get("must_keep_force_points", [])
    if not isinstance(must_keep, list) or len(must_keep) != 5:
        errors.append("rewrite_gate.must_keep_force_points 必须是长度为 5 的列表")

    for bucket in ("forbidden_actions", "common_errors"):
        for idx, item in enumerate(structured.get(bucket, []), start=1):
            status = item.get("status")
            if status not in ALLOWED_STATUS:
                errors.append(f"rewrite_gate.{bucket}[{idx}] status 非法: {status}")
            if status == "failed" and not item.get("reason"):
                errors.append(f"rewrite_gate.{bucket}[{idx}] failed 时必须填写 reason")
    for idx, item in enumerate(structured.get("required_steps", []), start=1):
        if item.get("done") not in {True, False}:
            errors.append(f"rewrite_gate.required_steps[{idx}] done 必须是 true/false")

    if require_complete:
        if any(not str(x).strip() for x in force_points.get("hurt_facts", [])):
            errors.append("rewrite_gate 完整模式下 hurt_facts 不能留空")
        if any(not str(x).strip() for x in force_points.get("bias_orders", [])):
            errors.append("rewrite_gate 完整模式下 bias_orders 不能留空")
        if not str(force_points.get("undignified_emotion", "")).strip():
            errors.append("rewrite_gate 完整模式下 undignified_emotion 不能留空")
        if any(not str(x).strip() for x in must_keep):
            errors.append("rewrite_gate 完整模式下 must_keep_force_points 不能留空")
    return errors


def validate_failure_gate(data: dict, require_complete: bool) -> list[str]:
    errors: list[str] = []
    structured = data.get("structured_checks", {})
    checks = structured.get("checks", [])
    if not isinstance(checks, list) or not checks:
        errors.append("failure_gate.checks 缺失")
        return errors
    for idx, item in enumerate(checks, start=1):
        status = item.get("status")
        if status not in ALLOWED_STATUS:
            errors.append(f"failure_gate.checks[{idx}] status 非法: {status}")
        if status == "failed":
            if not item.get("reason"):
                errors.append(f"failure_gate.checks[{idx}] failed 时必须填写 reason")
            if not item.get("evidence"):
                errors.append(f"failure_gate.checks[{idx}] failed 时必须填写 evidence")
    actions = structured.get("rewrite_actions", {})
    if require_complete and data.get("status") == "failed":
        if any(not str(x).strip() for x in actions.get("delete_top3_sentences", [])):
            errors.append("failure_gate failed 时 delete_top3_sentences 必须填满 3 条")
        if any(not str(x).strip() for x in actions.get("split_top2_dialogues", [])):
            errors.append("failure_gate failed 时 split_top2_dialogues 必须填满 2 条")
        if not str(actions.get("cut_top1_closure", "")).strip():
            errors.append("failure_gate failed 时 cut_top1_closure 不能为空")
    return errors


def validate_receipt(path: Path, require_executed: bool, require_complete: bool) -> tuple[list[str], dict]:
    data = load_json(path)
    errors: list[str] = []
    gate_type = data.get("gate_type")
    status = data.get("status")
    executed = data.get("executed")
    if gate_type not in {"rewrite_gate", "failure_gate"}:
        errors.append(f"gate_type 非法: {gate_type}")
    if status not in ALLOWED_STATUS:
        errors.append(f"status 非法: {status}")
    if executed not in {True, False}:
        errors.append("executed 必须是 true/false")
    if require_executed and executed is not True:
        errors.append("要求已执行，但 executed != true")
    if status in {"passed", "failed"} and executed is not True:
        errors.append("status 为 passed/failed 时，executed 必须为 true")

    structured = data.get("structured_checks", {})
    actual_summary = count_structured_checks(structured)
    stored_summary = data.get("summary", {})
    for key, value in actual_summary.items():
        if stored_summary.get(key) != value:
            errors.append(f"summary.{key} 与 structured_checks 不一致: {stored_summary.get(key)} != {value}")

    if gate_type == "rewrite_gate":
        errors.extend(validate_rewrite_gate(data, require_complete))
    elif gate_type == "failure_gate":
        errors.extend(validate_failure_gate(data, require_complete))

    if require_complete and actual_summary["pending_count"] > 0:
        errors.append("要求完整填写，但 structured_checks 里仍有 pending 项")
    return errors, actual_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", help="rewrite_gate_receipt.json 或 failure_gate_receipt.json")
    parser.add_argument("--require-executed", action="store_true", help="要求 executed=true")
    parser.add_argument("--require-complete", action="store_true", help="要求所有结构化判定项已填完")
    args = parser.parse_args()

    receipt_path = Path(args.receipt).resolve()
    errors, summary = validate_receipt(receipt_path, args.require_executed, args.require_complete)
    print(f"receipt: {receipt_path}")
    print(f"passed_count: {summary['passed_count']}")
    print(f"failed_count: {summary['failed_count']}")
    print(f"pending_count: {summary['pending_count']}")
    print(f"hard_fail_triggered: {summary['hard_fail_triggered']}")
    if errors:
        print("errors:")
        for item in errors:
            print(f"- {item}")
        return 2
    print("validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
