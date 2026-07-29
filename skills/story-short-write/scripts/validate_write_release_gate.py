#!/usr/bin/env python3
"""Hard pre-write release gate for story-short-write."""

from __future__ import annotations

import argparse
import hashlib
import json
import importlib.util
import subprocess
import sys
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

_REFRESH_LEGACY_BINDINGS_PATH = Path(__file__).with_name(
    "refresh_legacy_project_bindings.py"
)


def auto_refresh_legacy_bindings(
    project: Path,
    use_git_ledger_fallback: bool,
    *,
    repair_ledger: bool = False,
) -> list[str]:
    cmd = [
        sys.executable,
        str(_REFRESH_LEGACY_BINDINGS_PATH),
        "--project",
        str(project),
        "--refresh-bindings",
        "--rebuild-section-bundle",
        "--validate",
    ]
    if repair_ledger:
        cmd.append("--repair-ledger")
    if use_git_ledger_fallback:
        cmd.append("--use-git-ledger-fallback")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return []
    detail = (proc.stdout or proc.stderr or "").strip()
    message = "旧项目绑定自动刷新失败"
    if detail:
        return [message, detail]
    return [message]


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


def _nonempty_list_count(value: Any) -> int:
    if not isinstance(value, list):
        return 0
    return sum(1 for item in value if item)


def validate_profile_thickness(
    profile_path: Path,
    *,
    strong_emotion_required: bool,
    errors: list[str],
) -> None:
    profile = load_json(profile_path, "正文写作放行所需 profile", errors)
    if profile is None:
        return
    meta = profile.get("meta") if isinstance(profile.get("meta"), dict) else {}
    source_count = int(meta.get("source_count") or 0)
    is_merged_profile = meta.get("mode") == "merged_profiles" or source_count > 1
    bridge_rules = profile.get("bridge_rules") if isinstance(profile.get("bridge_rules"), list) else []
    causal_assets = (
        profile.get("causal_precondition_assets")
        if isinstance(profile.get("causal_precondition_assets"), list)
        else []
    )
    scene_assets = profile.get("scene_assets") if isinstance(profile.get("scene_assets"), dict) else {}
    story_guardrails = (
        profile.get("story_guardrails") if isinstance(profile.get("story_guardrails"), dict) else {}
    )

    if not is_merged_profile:
        return

    public_explosion_count = _nonempty_list_count(scene_assets.get("public_explosion"))
    external_order_count = _nonempty_list_count(scene_assets.get("external_order"))
    consequence_chain_count = _nonempty_list_count(scene_assets.get("consequence_chain"))

    consequence_guard = (
        story_guardrails.get("consequence_structure")
        if isinstance(story_guardrails.get("consequence_structure"), dict)
        else {}
    )
    face_guard = (
        story_guardrails.get("character_face_split")
        if isinstance(story_guardrails.get("character_face_split"), dict)
        else {}
    )

    bridge_floor = 16 if strong_emotion_required else 12
    causal_floor = 16 if strong_emotion_required else 12
    source_floor = 4 if strong_emotion_required else 3
    consequence_floor = 24 if strong_emotion_required else 16

    if source_count < source_floor:
        errors.append(
            "融合 profile 来源厚度不足："
            f"source_count={source_count}，当前题型正文放行前至少需要 {source_floor} 个来源，"
            "否则主体骨架和辅助颗粒不够厚，容易把原文颗粒写成薄摘要。"
        )
    if len(bridge_rules) < bridge_floor:
        errors.append(
            "融合 profile 的 bridge_rules 厚度不足："
            f"{len(bridge_rules)} < {bridge_floor}；"
            "桥段规则过薄时，正文前无法证明承重桥和辅助桥的迁移密度足够。"
        )
    if len(causal_assets) < causal_floor:
        errors.append(
            "融合 profile 的 causal_precondition_assets 厚度不足："
            f"{len(causal_assets)} < {causal_floor}；"
            "场景因果资产过薄时，scene_logic_contract 很容易退化成模板句。"
        )
    if public_explosion_count < 8:
        errors.append(
            "融合 profile 的 scene_assets.public_explosion 过薄："
            f"{public_explosion_count} < 8；公开失位类场面资产不够。"
        )
    if external_order_count < 8:
        errors.append(
            "融合 profile 的 scene_assets.external_order 过薄："
            f"{external_order_count} < 8；外部秩序接管类场面资产不够。"
        )
    if consequence_chain_count < consequence_floor:
        errors.append(
            "融合 profile 的 scene_assets.consequence_chain 厚度不足："
            f"{consequence_chain_count} < {consequence_floor}；"
            "长尾后果链不足，容易把强情绪后果压成单场伤害。"
        )
    if not consequence_guard.get("pre_evidence_reality_consequences"):
        errors.append("融合 profile 缺少 story_guardrails.consequence_structure.pre_evidence_reality_consequences")
    if not consequence_guard.get("tail_entry_owner"):
        errors.append("融合 profile 缺少 story_guardrails.consequence_structure.tail_entry_owner")
    if not face_guard.get("different_face_evidence"):
        errors.append("融合 profile 缺少 story_guardrails.character_face_split.different_face_evidence")


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
    project: Path | None = None,
    auto_refresh_legacy_bindings_enabled: bool = False,
    use_git_ledger_fallback: bool = False,
) -> list[str]:
    errors: list[str] = []
    if auto_refresh_legacy_bindings_enabled:
        if project is None:
            return ["启用旧项目自动刷新时必须提供 --project"]
        refresh_errors = auto_refresh_legacy_bindings(
            project,
            use_git_ledger_fallback=use_git_ledger_fallback,
            repair_ledger=False,
        )
        if refresh_errors:
            return refresh_errors
    writing_data = load_json(writing_receipt, "写作规则读取回执", errors)
    require_passed(
        writing_data,
        "写作规则读取门禁",
        errors,
    )
    if writing_data is not None:
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
    if source_data is not None:
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
        strong_emotion_required = False
        if draft_capacity_contract is None:
            errors.append("正文写作放行必须提供首写容量契约")
        else:
            capacity_errors = _DRAFT_CAPACITY_MODULE.validate(draft_capacity_contract)
            if capacity_errors:
                errors.append("首写容量契约未通过")
                errors.extend(capacity_errors)
        if section_source_bundle is None:
            errors.append("正文写作放行必须提供逐节原文颗粒包")
        else:
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
                global_review = (
                    outline_contract_data.get("global_review")
                    if isinstance(outline_contract_data.get("global_review"), dict)
                    else {}
                )
                strong_emotion_required = bool(global_review.get("strong_emotion_required"))
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
        else:
            validate_profile_thickness(
                profile,
                strong_emotion_required=strong_emotion_required,
                errors=errors,
            )

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
    parser.add_argument("--project")
    parser.add_argument("--auto-refresh-legacy-bindings", action="store_true")
    parser.add_argument("--use-git-ledger-fallback", action="store_true")
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
        Path(args.project).resolve() if args.project else None,
        args.auto_refresh_legacy_bindings,
        args.use_git_ledger_fallback,
    )
    if errors:
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"write_release_gate: passed ({args.phase})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
