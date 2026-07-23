#!/usr/bin/env python3
"""Hard pre-write release gate for story-short-write."""

from __future__ import annotations

import argparse
import hashlib
import json
import importlib.util
from pathlib import Path
from typing import Any


_SEQUENCE_GATE_PATH = Path(__file__).with_name("validate_sequence_contract.py")
_SEQUENCE_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_sequence_contract", _SEQUENCE_GATE_PATH
)
assert _SEQUENCE_SPEC and _SEQUENCE_SPEC.loader
_SEQUENCE_MODULE = importlib.util.module_from_spec(_SEQUENCE_SPEC)
_SEQUENCE_SPEC.loader.exec_module(_SEQUENCE_MODULE)

_OUTLINE_PERFORMANCE_GATE_PATH = Path(__file__).with_name(
    "validate_outline_performance_contract.py"
)
_OUTLINE_PERFORMANCE_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_outline_performance_contract",
    _OUTLINE_PERFORMANCE_GATE_PATH,
)
assert _OUTLINE_PERFORMANCE_SPEC and _OUTLINE_PERFORMANCE_SPEC.loader
_OUTLINE_PERFORMANCE_MODULE = importlib.util.module_from_spec(
    _OUTLINE_PERFORMANCE_SPEC
)
_OUTLINE_PERFORMANCE_SPEC.loader.exec_module(_OUTLINE_PERFORMANCE_MODULE)

_RULE_LEDGER_GATE_PATH = Path(__file__).with_name(
    "validate_rule_execution_ledger.py"
)
_RULE_LEDGER_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_rule_execution_ledger",
    _RULE_LEDGER_GATE_PATH,
)
assert _RULE_LEDGER_SPEC and _RULE_LEDGER_SPEC.loader
_RULE_LEDGER_MODULE = importlib.util.module_from_spec(_RULE_LEDGER_SPEC)
_RULE_LEDGER_SPEC.loader.exec_module(_RULE_LEDGER_MODULE)


def load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{label}不存在: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label}不是有效 JSON: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{label}必须是 JSON 对象")
        return None
    return data


def require_passed(data: dict[str, Any] | None, label: str, errors: list[str]) -> None:
    if data is not None and data.get("gate_status") != "passed":
        errors.append(f"{label}未通过: gate_status={data.get('gate_status')!r}")


def iter_execution_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in ("skill_rules", "source_assets", "asset_rules"):
        value = data.get(key)
        if isinstance(value, list):
            entries.extend(item for item in value if isinstance(item, dict))
    return entries


def require_ledger_prewrite_ready(
    data: dict[str, Any] | None,
    ledger_path: Path,
    phase: str,
    errors: list[str],
) -> None:
    if data is None:
        return
    prewrite_errors = _RULE_LEDGER_MODULE.validate_prewrite_ledger(ledger_path)
    if prewrite_errors:
        errors.append("规则执行台账未完成写前分类与执行计划")
        errors.extend(prewrite_errors)
        return
    status = data.get("gate_status")
    if status == "passed":
        ledger_errors, _ = _RULE_LEDGER_MODULE.validate_ledger(ledger_path)
        if ledger_errors:
            errors.append("规则执行台账虽然标记 passed，但重新校验失败")
            errors.extend(ledger_errors)
        return
    if status != "pending":
        errors.append(f"规则执行门禁未通过: gate_status={status!r}")
        return
    entries = iter_execution_entries(data)
    if not entries:
        errors.append("规则执行台账缺少规则条目")
        return
    unconfirmed = []
    for entry in entries:
        if entry.get("applicability") == "merged":
            continue
        # Some source inventory parent rows are bookkeeping entries and are
        # not exported for model review until final artifact binding. Do not
        # let them deadlock the empty-project setting/outline bootstrap.
        if not str(entry.get("rule_text") or "").strip():
            continue
        if entry.get("classification_confirmed") is not True:
            unconfirmed.append(str(entry.get("id") or "<unknown>"))
        if entry.get("mode_confirmed") is not True:
            unconfirmed.append(str(entry.get("id") or "<unknown>"))
    if unconfirmed:
        preview = " / ".join(unconfirmed[:20])
        suffix = " ..." if len(unconfirmed) > 20 else ""
        errors.append(f"规则执行台账尚未完成模型归类确认: {preview}{suffix}")
    if phase == "draft":
        # 正文前仍允许台账处于 pending，因为最终正文证据尚未存在；
        # 但必须已经完成写前分类，最终交付前再由 validate_rule_execution_ledger.py 要求 passed。
        return


def validate_sequence_bindings(
    data: dict[str, Any],
    required_keys: tuple[str, ...],
    label: str,
    errors: list[str],
) -> None:
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{label}缺少 artifacts 绑定")
        return
    for key in required_keys:
        binding = artifacts.get(key)
        if not isinstance(binding, dict):
            errors.append(f"{label}缺少 {key} 绑定")
            continue
        path = Path(str(binding.get("path") or "")).resolve()
        if not path.is_file():
            errors.append(f"{label}绑定产物不存在: {path}")
            continue
        current_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if binding.get("sha256") != current_sha:
            errors.append(f"{label}绑定的 {key} SHA 已变化，必须重新审查")


def validate_release(
    phase: str,
    writing_receipt: Path,
    source_receipt: Path,
    ledger: Path,
    opening_contract: Path | None = None,
    outline_contract: Path | None = None,
    profile: Path | None = None,
    sequence_receipt: Path | None = None,
    setting_sequence_receipt: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    require_passed(
        load_json(writing_receipt, "写作规则读取回执", errors),
        "写作规则读取门禁",
        errors,
    )
    require_passed(
        load_json(source_receipt, "拆文读取回执", errors),
        "拆文读取门禁",
        errors,
    )
    require_ledger_prewrite_ready(
        load_json(ledger, "规则执行台账", errors),
        ledger,
        phase,
        errors,
    )

    if phase == "outline":
        if setting_sequence_receipt is None:
            errors.append("大纲写作放行必须提供已通过的设定内部顺序契约回执")
        else:
            setting_sequence_data = load_json(
                setting_sequence_receipt,
                "设定内部顺序契约回执",
                errors,
            )
            if (
                setting_sequence_data is not None
                and (
                    setting_sequence_data.get("gate_status") != "passed"
                    or setting_sequence_data.get("scope") != "setting"
                )
            ):
                errors.append("设定内部顺序契约门禁未通过或 scope 不正确")
            if setting_sequence_data is not None:
                validate_sequence_bindings(
                    setting_sequence_data,
                    ("setting",),
                    "设定内部顺序契约",
                    errors,
                )
                binding = setting_sequence_data.get("artifacts", {}).get("setting")
                if isinstance(binding, dict):
                    setting_path = Path(str(binding.get("path") or "")).resolve()
                    if setting_path.is_file():
                        errors.extend(
                            _SEQUENCE_MODULE.validate_setting(
                                setting_sequence_receipt,
                                setting_path,
                            )
                        )
    if phase == "draft":
        if sequence_receipt is None:
            errors.append("正文写作放行必须提供设定—大纲—正文顺序契约回执")
        else:
            sequence_data = load_json(sequence_receipt, "顺序契约回执", errors)
            if sequence_data is not None:
                if sequence_data.get("gate_status") != "passed":
                    errors.append(
                        f"顺序契约门禁未通过: gate_status={sequence_data.get('gate_status')!r}"
                    )
                if sequence_data.get("scope") != "full":
                    errors.append("正文写作放行所需顺序契约 scope 必须为 full")
                validate_sequence_bindings(
                    sequence_data,
                    ("setting", "outline"),
                    "完整顺序契约",
                    errors,
                )

    if phase == "draft":
        if opening_contract is None:
            errors.append("正文写作放行必须提供开头承重契约回执")
        else:
            require_passed(
                load_json(opening_contract, "开头承重契约回执", errors),
                "开头承重契约门禁",
                errors,
            )
        if outline_contract is None:
            errors.append("正文写作放行必须提供细纲表演验收回执")
        else:
            outline_contract_data = load_json(
                outline_contract,
                "细纲表演验收回执",
                errors,
            )
            require_passed(
                outline_contract_data,
                "细纲表演验收门禁",
                errors,
            )
            if outline_contract_data is not None:
                binding = outline_contract_data.get("outline")
                validate_sequence_bindings(
                    {"artifacts": {"outline": binding}},
                    ("outline",),
                    "细纲表演验收",
                    errors,
                )
                if isinstance(binding, dict):
                    outline_path = Path(str(binding.get("path") or "")).resolve()
                    if outline_path.is_file():
                        errors.extend(
                            _OUTLINE_PERFORMANCE_MODULE.validate_receipt(
                                outline_contract,
                                outline_path,
                            )
                        )
        if profile is None:
            errors.append("正文写作放行必须提供单书或融合 profile")
        elif not profile.is_file():
            errors.append(f"正文写作放行所需 profile 不存在: {profile}")

    if errors:
        return [
            f"write_release_gate: blocked ({phase})；不得生成或修改当前阶段产物",
            *errors,
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hard pre-write release gate for story-short-write."
    )
    parser.add_argument("phase", choices=("setting", "outline", "draft"))
    parser.add_argument("--writing-receipt", required=True)
    parser.add_argument("--source-receipt", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--opening-contract")
    parser.add_argument("--outline-contract")
    parser.add_argument("--profile")
    parser.add_argument("--sequence-receipt")
    parser.add_argument("--setting-sequence-receipt")
    args = parser.parse_args()

    errors = validate_release(
        args.phase,
        Path(args.writing_receipt).resolve(),
        Path(args.source_receipt).resolve(),
        Path(args.ledger).resolve(),
        Path(args.opening_contract).resolve() if args.opening_contract else None,
        Path(args.outline_contract).resolve() if args.outline_contract else None,
        Path(args.profile).resolve() if args.profile else None,
        Path(args.sequence_receipt).resolve() if args.sequence_receipt else None,
        Path(args.setting_sequence_receipt).resolve()
        if args.setting_sequence_receipt
        else None,
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"write_release_gate: passed ({args.phase})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
