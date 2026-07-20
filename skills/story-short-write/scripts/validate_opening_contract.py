#!/usr/bin/env python3
"""Generate and validate the mandatory source-bound opening contract receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


WINDOW_SIZES = (20, 60, 80, 120)
REQUIRED_CHECKS = (
    "relationship_anchor_in_first_20_60",
    "relationship_conflict_or_abnormal_position_in_first_60",
    "premise_paid_off_in_first_80_120",
    "reader_question_established",
    "task_exposition_does_not_precede_hook",
    "source_sequence_preserved_at_function_level",
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


def canonical_body(text: str) -> str:
    lines = []
    in_frontmatter = False
    for index, raw_line in enumerate(text.splitlines()):
        stripped = raw_line.strip()
        if index == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return re.sub(r"\s+", "", "".join(lines))


def opening_windows(text: str) -> dict[str, str]:
    body = canonical_body(text)
    return {str(size): body[:size] for size in WINDOW_SIZES}


def create_receipt(
    project: str,
    source_path: Path,
    target_path: Path,
    artifact_kind: str,
) -> dict[str, Any]:
    resolved_source = source_path.resolve()
    resolved_target = target_path.resolve()
    if not resolved_source.is_file():
        raise FileNotFoundError(f"主体导语资产不存在: {resolved_source}")
    if not resolved_target.is_file():
        raise FileNotFoundError(f"目标文本不存在: {resolved_target}")

    target_text = read_text(resolved_target)
    return {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "execution_mode": "current_model_manual",
        "artifact_kind": artifact_kind,
        "reviewed_by_current_model": False,
        "primary_source": {
            "path": str(resolved_source),
            "sha256": sha256(resolved_source),
        },
        "target_text": {
            "path": str(resolved_target),
            "sha256": sha256(resolved_target),
            "opening_windows": opening_windows(target_text),
        },
        "source_contract": {
            "functional_sequence": [],
            "forbidden_precedence": [],
            "transferable_requirements": [],
        },
        "source_evidence": [],
        "checks": {check_id: None for check_id in REQUIRED_CHECKS},
        "target_evidence": [],
        "blocking_failures": [],
        "manual_judgment": "",
    }


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def evidence_map(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    return {
        str(item.get("check_id") or ""): item
        for item in value
        if isinstance(item, dict) and str(item.get("check_id") or "")
    }


def validate_receipt(
    receipt_path: Path,
    source_path: Path,
    target_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    resolved_source = source_path.resolve()
    resolved_target = target_path.resolve()

    if not resolved_source.is_file():
        errors.append(f"主体导语资产不存在: {resolved_source}")
    if not resolved_target.is_file():
        errors.append(f"目标文本不存在: {resolved_target}")
    if errors:
        return errors, {"passed_checks": 0, "check_count": len(REQUIRED_CHECKS)}

    source_text = read_text(resolved_source)
    target_text = read_text(resolved_target)
    target_body = canonical_body(target_text)

    source_info = data.get("primary_source")
    if not isinstance(source_info, dict):
        errors.append("primary_source 必须是对象")
        source_info = {}
    if str(source_info.get("path") or "") != str(resolved_source):
        errors.append("回执绑定的主体导语资产路径与当前输入不一致")
    if source_info.get("sha256") != sha256(resolved_source):
        errors.append("主体导语资产已变化，必须重新提取开头契约")

    target_info = data.get("target_text")
    if not isinstance(target_info, dict):
        errors.append("target_text 必须是对象")
        target_info = {}
    if str(target_info.get("path") or "") != str(resolved_target):
        errors.append("回执绑定的目标文本路径与当前输入不一致")
    if target_info.get("sha256") != sha256(resolved_target):
        errors.append("目标文本已变化，必须重新执行开头硬闸")
    if target_info.get("opening_windows") != opening_windows(target_text):
        errors.append("前 20/60/80/120 字窗口与当前目标文本不一致")

    if data.get("execution_mode") != "current_model_manual":
        errors.append("execution_mode 必须为 current_model_manual")
    if data.get("reviewed_by_current_model") is not True:
        errors.append("必须由当前执行 skill 的模型人工完成开头裁决")
    if data.get("artifact_kind") not in {"outline", "draft"}:
        errors.append("artifact_kind 必须为 outline 或 draft")

    contract = data.get("source_contract")
    if not isinstance(contract, dict):
        errors.append("source_contract 必须是对象")
        contract = {}
    if len(nonempty_strings(contract.get("functional_sequence"))) < 3:
        errors.append("必须从主体导语资产提取至少三拍功能顺序")
    if not nonempty_strings(contract.get("forbidden_precedence")):
        errors.append("必须提取至少一条禁止抢跑/禁止换序规则")
    if len(nonempty_strings(contract.get("transferable_requirements"))) < 2:
        errors.append("必须提取至少两条可迁移开头要求")

    source_evidence = data.get("source_evidence")
    valid_source_evidence = 0
    if not isinstance(source_evidence, list):
        errors.append("source_evidence 必须是列表")
    else:
        for index, item in enumerate(source_evidence, start=1):
            if not isinstance(item, dict):
                errors.append(f"主体来源证据格式错误: [{index}]")
                continue
            quote = str(item.get("quote") or "").strip()
            judgment = str(item.get("judgment") or "").strip()
            if not quote or quote not in source_text:
                errors.append(f"主体来源证据不在导语资产中: [{index}]")
                continue
            if not judgment:
                errors.append(f"主体来源证据缺少功能判断: [{index}]")
                continue
            valid_source_evidence += 1
    if valid_source_evidence < 2:
        errors.append("主体导语资产至少需要两条真实原句证据")

    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks 必须是对象")
        checks = {}
    unknown_checks = sorted(set(checks) - set(REQUIRED_CHECKS))
    missing_checks = sorted(set(REQUIRED_CHECKS) - set(checks))
    for check_id in unknown_checks:
        errors.append(f"存在未知开头检查项: {check_id}")
    for check_id in missing_checks:
        errors.append(f"缺少开头检查项: {check_id}")

    target_evidence = evidence_map(data.get("target_evidence"))
    passed_checks = 0
    failed_checks: list[str] = []
    for check_id in REQUIRED_CHECKS:
        value = checks.get(check_id)
        if not isinstance(value, bool):
            errors.append(f"开头检查项尚未人工裁决: {check_id}")
            continue
        if value:
            passed_checks += 1
        else:
            failed_checks.append(check_id)

        evidence = target_evidence.get(check_id)
        if not evidence:
            errors.append(f"开头检查项缺少目标原文证据: {check_id}")
            continue
        quote = re.sub(r"\s+", "", str(evidence.get("quote") or ""))
        judgment = str(evidence.get("judgment") or "").strip()
        if not quote or quote not in target_body[:120]:
            errors.append(f"开头检查项证据不在目标前 120 字: {check_id}")
        if not judgment:
            errors.append(f"开头检查项缺少人工判断: {check_id}")

    recorded_failures = set(nonempty_strings(data.get("blocking_failures")))
    if recorded_failures != set(failed_checks):
        errors.append("blocking_failures 必须与值为 false 的检查项完全一致")
    if not str(data.get("manual_judgment") or "").strip():
        errors.append("必须填写开头整体人工裁决")

    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if failed_checks:
        errors.append("开头承重契约未满足: " + " / ".join(failed_checks))

    return errors, {
        "passed_checks": passed_checks,
        "check_count": len(REQUIRED_CHECKS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mandatory source-bound opening contract gate."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="生成待人工回填的开头契约回执")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--source", required=True)
    init_parser.add_argument("--target", required=True)
    init_parser.add_argument("--artifact-kind", choices=("outline", "draft"), required=True)
    init_parser.add_argument("--receipt", required=True)
    init_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="校验开头契约回执")
    validate_parser.add_argument("--receipt", required=True)
    validate_parser.add_argument("--source", required=True)
    validate_parser.add_argument("--target", required=True)

    args = parser.parse_args()
    receipt_path = Path(args.receipt).resolve()
    if args.command == "init":
        if receipt_path.exists() and not args.force:
            print(f"开头契约回执已存在，拒绝覆盖: {receipt_path}")
            return 2
        try:
            receipt = create_receipt(
                args.project,
                Path(args.source),
                Path(args.target),
                args.artifact_kind,
            )
        except FileNotFoundError as exc:
            print("opening_contract_gate: blocked")
            print(f"- {exc}")
            return 2
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("opening_contract_gate: initialized")
        print(f"receipt: {receipt_path}")
        for size, window in receipt["target_text"]["opening_windows"].items():
            print(f"first_{size}: {window}")
        return 0

    if not receipt_path.is_file():
        print(f"开头契约回执不存在: {receipt_path}")
        return 2
    errors, summary = validate_receipt(
        receipt_path,
        Path(args.source),
        Path(args.target),
    )
    print(f"receipt: {receipt_path}")
    print(f"checks: {summary['passed_checks']}/{summary['check_count']}")
    if errors:
        print("opening_contract_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("opening_contract_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
