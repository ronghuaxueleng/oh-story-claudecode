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

_WRITING_RULE_GATE_PATH = Path(__file__).with_name("validate_writing_rule_gate.py")
_WRITING_RULE_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_writing_rule_gate",
    _WRITING_RULE_GATE_PATH,
)
assert _WRITING_RULE_SPEC and _WRITING_RULE_SPEC.loader
_WRITING_RULE_MODULE = importlib.util.module_from_spec(_WRITING_RULE_SPEC)
_WRITING_RULE_SPEC.loader.exec_module(_WRITING_RULE_MODULE)

_SOURCE_READ_GATE_PATH = Path(__file__).with_name("validate_source_read_gate.py")
_SOURCE_READ_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_source_read_gate",
    _SOURCE_READ_GATE_PATH,
)
assert _SOURCE_READ_SPEC and _SOURCE_READ_SPEC.loader
_SOURCE_READ_MODULE = importlib.util.module_from_spec(_SOURCE_READ_SPEC)
_SOURCE_READ_SPEC.loader.exec_module(_SOURCE_READ_MODULE)

_OPENING_CONTRACT_GATE_PATH = Path(__file__).with_name("validate_opening_contract.py")
_OPENING_CONTRACT_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_opening_contract",
    _OPENING_CONTRACT_GATE_PATH,
)
assert _OPENING_CONTRACT_SPEC and _OPENING_CONTRACT_SPEC.loader
_OPENING_CONTRACT_MODULE = importlib.util.module_from_spec(_OPENING_CONTRACT_SPEC)
_OPENING_CONTRACT_SPEC.loader.exec_module(_OPENING_CONTRACT_MODULE)

_DRAFT_CAPACITY_GATE_PATH = Path(__file__).with_name("validate_draft_capacity_contract.py")
_DRAFT_CAPACITY_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_draft_capacity_contract", _DRAFT_CAPACITY_GATE_PATH
)
assert _DRAFT_CAPACITY_SPEC and _DRAFT_CAPACITY_SPEC.loader
_DRAFT_CAPACITY_MODULE = importlib.util.module_from_spec(_DRAFT_CAPACITY_SPEC)
_DRAFT_CAPACITY_SPEC.loader.exec_module(_DRAFT_CAPACITY_MODULE)

_SECTION_SOURCE_BUNDLE_PATH = Path(__file__).with_name("build_section_source_bundle.py")
_SECTION_SOURCE_BUNDLE_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_section_source_bundle", _SECTION_SOURCE_BUNDLE_PATH
)
assert _SECTION_SOURCE_BUNDLE_SPEC and _SECTION_SOURCE_BUNDLE_SPEC.loader
_SECTION_SOURCE_BUNDLE_MODULE = importlib.util.module_from_spec(_SECTION_SOURCE_BUNDLE_SPEC)
_SECTION_SOURCE_BUNDLE_SPEC.loader.exec_module(_SECTION_SOURCE_BUNDLE_MODULE)


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
    draft_capacity_contract: Path | None = None,
    section_source_bundle: Path | None = None,
    skip_writing_receipt_validation: bool = False,
    skip_source_receipt_validation: bool = False,
    skip_section_source_bundle_validation: bool = False,
) -> list[str]:
    errors: list[str] = []
    writing_data = load_json(writing_receipt, "写作规则读取回执", errors)
    require_passed(
        writing_data,
        "写作规则读取门禁",
        errors,
    )
    if writing_data is not None and not skip_writing_receipt_validation:
        writing_errors, _ = _WRITING_RULE_MODULE.validate_receipt(writing_receipt)
        if writing_errors:
            errors.append("写作规则读取回执实时复验失败")
            errors.extend(writing_errors)
    source_data = load_json(source_receipt, "拆文读取回执", errors)
    require_passed(
        source_data,
        "拆文读取门禁",
        errors,
    )
    if source_data is not None and not skip_source_receipt_validation:
        source_errors, _ = _SOURCE_READ_MODULE.validate_receipt(source_receipt)
        if source_errors:
            errors.append("拆文读取回执实时复验失败")
            errors.extend(source_errors)
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
        if draft_capacity_contract is None:
            errors.append("正文写作放行必须提供首写容量契约")
        else:
            capacity_errors = _DRAFT_CAPACITY_MODULE.validate(draft_capacity_contract)
            if capacity_errors:
                errors.append("首写容量契约未通过")
                errors.extend(capacity_errors)
        if section_source_bundle is None:
            errors.append("正文写作放行必须提供逐节原文颗粒包")
        elif not skip_section_source_bundle_validation:
            bundle_errors = _SECTION_SOURCE_BUNDLE_MODULE.validate_bundle(
                section_source_bundle
            )
            if bundle_errors:
                errors.append("逐节原文颗粒包未通过")
                errors.extend(bundle_errors)
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
            opening_data = load_json(opening_contract, "开头承重契约回执", errors)
            require_passed(
                opening_data,
                "开头承重契约门禁",
                errors,
            )
            if opening_data is not None:
                source_binding = opening_data.get("primary_source")
                target_binding = opening_data.get("target_text")
                if not isinstance(source_binding, dict) or not isinstance(target_binding, dict):
                    errors.append("开头承重契约缺少来源或目标绑定")
                else:
                    source_path = Path(str(source_binding.get("path") or "")).resolve()
                    target_path = Path(str(target_binding.get("path") or "")).resolve()
                    opening_errors, _ = _OPENING_CONTRACT_MODULE.validate_receipt(
                        opening_contract,
                        source_path,
                        target_path,
                    )
                    if opening_errors:
                        errors.append("开头承重契约实时复验失败")
                        errors.extend(opening_errors)
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
                                skip_source_receipt_validation=skip_source_receipt_validation,
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
    parser.add_argument("--draft-capacity-contract")
    parser.add_argument("--section-source-bundle")
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
        Path(args.draft_capacity_contract).resolve()
        if args.draft_capacity_contract
        else None,
        Path(args.section_source_bundle).resolve()
        if args.section_source_bundle
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
