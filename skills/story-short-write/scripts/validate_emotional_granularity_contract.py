#!/usr/bin/env python3
"""Validate source-level emotional parity during a short-fiction first draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-write.emotional-granularity-contract.v1"
REQUIRED_BEAT_ROLES = (
    "entry",
    "pain",
    "hope_or_resistance",
    "reversal",
    "peak",
    "afterpain",
)
REQUIRED_PLAN_FIELDS = (
    "immediate_subjective_judgment_plan",
    "untidy_thought_or_emotional_crack_plan",
    "embodied_or_object_action_plan",
    "old_wound_trigger_plan",
    "opponent_pressure_plan",
    "loss_of_control_or_equivalent_plan",
)
REQUIRED_REVIEW_QUOTE_FIELDS = (
    "immediate_subjective_judgment_quotes",
    "untidy_thought_or_emotional_crack_quotes",
    "embodied_or_object_action_quotes",
    "opponent_pressure_quotes",
    "loss_of_control_or_equivalent_quotes",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_file_path(left: Path, right: Path) -> bool:
    left_resolved = left.resolve()
    right_resolved = right.resolve()
    try:
        return left_resolved.samefile(right_resolved)
    except (FileNotFoundError, OSError):
        return left_resolved == right_resolved


def binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("回执必须是 JSON 对象")
    return data


def outline_section_ids(text: str) -> list[str]:
    return re.findall(r"(?m)^##\s+(\d+)\.\s*", text)


def draft_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^(\d+)\.\s*$", text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.end() : end].strip()
    return sections


def beat_scaffold(role: str, evidence_key: str) -> dict[str, Any]:
    return {
        "role": role,
        "trigger": "",
        "relationship_position_change": "",
        "reader_effect": "",
        "intensity": None,
        evidence_key: [],
    }


def section_contract_scaffold(section_id: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "status": "pending",
        "source_excerpt": "",
        "source_emotion_beats": [
            beat_scaffold(role, "source_evidence") for role in REQUIRED_BEAT_ROLES
        ],
        "target_outline_beats": [
            beat_scaffold(role, "outline_evidence") for role in REQUIRED_BEAT_ROLES
        ],
        **{field: "" for field in REQUIRED_PLAN_FIELDS},
        "source_like_direct_emotion_preserved": None,
        "surface_copy_rejected": None,
        "manual_judgment": "",
    }


def beat_review_scaffold(role: str) -> dict[str, Any]:
    return {
        "role": role,
        "source_intensity": None,
        "target_intensity": None,
        "target_quotes": [],
        "parity_judgment": "",
    }


def section_review_scaffold(section_id: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "status": "pending",
        "beat_reviews": [beat_review_scaffold(role) for role in REQUIRED_BEAT_ROLES],
        **{field: [] for field in REQUIRED_REVIEW_QUOTE_FIELDS},
        "old_wound_trigger_review": {
            "applicable": None,
            "target_quotes": [],
            "rationale": "",
        },
        "source_like_direct_emotion_preserved": None,
        "target_not_lower_intensity": None,
        "anti_ai_cleanup_applied_during_first_draft": None,
        "auxiliary_prose_voice_used": None,
        "surface_copy_rejected": None,
        "manual_judgment": "",
    }


def create_receipt(project: str, source_original: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "mode": "source_dominant_first_draft",
        "bindings": {
            "primary_source_original": binding(source_original),
            "outline": None,
            "draft": None,
        },
        "first_draft_policy": {
            "primary_source_prose_dominant": True,
            "anti_ai_cleanup_applied_during_first_draft": False,
            "ai_audit_applied_during_first_draft": False,
            "source_like_direct_emotion_preserved": True,
            "auxiliary_prose_voice_allowed": False,
            "surface_copy_rejected": True,
            "obvious_gpt_contamination_blocked_as_source_drift": True,
        },
        "section_contracts": [],
        "section_reviews": [],
        "reviewed_by_current_model": False,
        "prewrite_status": "pending",
        "draft_status": "pending",
    }


def bind_outline(data: dict[str, Any], outline: Path) -> dict[str, Any]:
    section_ids = outline_section_ids(outline.read_text(encoding="utf-8"))
    if not section_ids:
        raise ValueError("细纲未找到 `## 1.` 形式的数字小节")
    data["bindings"]["outline"] = binding(outline)
    data["bindings"]["draft"] = None
    data["section_contracts"] = [section_contract_scaffold(item) for item in section_ids]
    data["section_reviews"] = []
    data["prewrite_status"] = "pending"
    data["draft_status"] = "pending"
    data["reviewed_by_current_model"] = False
    data["updated_at"] = now_iso()
    return data


def bind_draft(data: dict[str, Any], draft: Path) -> dict[str, Any]:
    section_ids = list(draft_sections(draft.read_text(encoding="utf-8")))
    if not section_ids:
        raise ValueError("正文未找到独占一行的 `1.` 形式数字小节")
    data["bindings"]["draft"] = binding(draft)
    data["section_reviews"] = [section_review_scaffold(item) for item in section_ids]
    data["draft_status"] = "pending"
    data["updated_at"] = now_iso()
    return data


def non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def quote_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def validate_binding(
    value: Any, expected: Path, label: str, errors: list[str]
) -> None:
    if not isinstance(value, dict):
        errors.append(f"缺少 {label} 绑定")
        return
    expected = expected.resolve()
    if not same_file_path(Path(str(value.get("path") or "")), expected):
        errors.append(f"{label} 绑定路径不一致")
    if value.get("sha256") != sha256_file(expected):
        errors.append(f"{label} SHA 已变化，必须重新绑定")


def validate_policy(data: dict[str, Any], errors: list[str]) -> None:
    if data.get("mode") != "source_dominant_first_draft":
        errors.append("首稿模式必须为 source_dominant_first_draft")
    policy = data.get("first_draft_policy")
    if not isinstance(policy, dict):
        errors.append("缺少 first_draft_policy")
        return
    required_true = (
        "primary_source_prose_dominant",
        "source_like_direct_emotion_preserved",
        "surface_copy_rejected",
        "obvious_gpt_contamination_blocked_as_source_drift",
    )
    required_false = (
        "anti_ai_cleanup_applied_during_first_draft",
        "ai_audit_applied_during_first_draft",
        "auxiliary_prose_voice_allowed",
    )
    for field in required_true:
        if policy.get(field) is not True:
            errors.append(f"首稿政策要求 {field}=true")
    for field in required_false:
        if policy.get(field) is not False:
            errors.append(f"首稿政策要求 {field}=false")


def validate_beat_list(
    beats: Any,
    evidence_key: str,
    evidence_text: str,
    label: str,
    errors: list[str],
) -> dict[str, int]:
    if not isinstance(beats, list):
        errors.append(f"{label} 必须是列表")
        return {}
    by_role: dict[str, int] = {}
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        role = str(beat.get("role") or "")
        if role not in REQUIRED_BEAT_ROLES or role in by_role:
            continue
        for field in ("trigger", "relationship_position_change", "reader_effect"):
            if not non_empty_text(beat.get(field)):
                errors.append(f"{label} {role} 缺少 {field}")
        intensity = beat.get("intensity")
        if not isinstance(intensity, int) or isinstance(intensity, bool) or not 1 <= intensity <= 10:
            errors.append(f"{label} {role} intensity 必须为 1-10 整数")
            continue
        evidence = quote_list(beat.get(evidence_key))
        if not evidence:
            errors.append(f"{label} {role} 缺少 {evidence_key}")
        for quote in evidence:
            if quote not in evidence_text:
                errors.append(f"{label} {role} 证据不在绑定文本中: {quote[:30]}")
        by_role[role] = intensity
    missing = [role for role in REQUIRED_BEAT_ROLES if role not in by_role]
    if missing:
        errors.append(f"{label} 缺少情绪拍: {', '.join(missing)}")
    return by_role


def validate_prewrite_data(
    data: dict[str, Any], source_original: Path, outline: Path
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("情绪颗粒度合同 schema_version 不正确")
    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        errors.append("情绪颗粒度合同缺少 bindings")
        return errors, data
    validate_binding(bindings.get("primary_source_original"), source_original, "主体原文", errors)
    validate_binding(bindings.get("outline"), outline, "细纲", errors)
    validate_policy(data, errors)
    source_text = source_original.read_text(encoding="utf-8")
    outline_text = outline.read_text(encoding="utf-8")
    expected_ids = outline_section_ids(outline_text)
    contracts = data.get("section_contracts")
    if not isinstance(contracts, list):
        errors.append("section_contracts 必须是列表")
        contracts = []
    by_id = {
        str(item.get("section_id")): item
        for item in contracts
        if isinstance(item, dict)
    }
    if list(by_id) != expected_ids:
        errors.append("逐节情绪合同必须按细纲数字小节完整覆盖且顺序一致")
    for section_id in expected_ids:
        item = by_id.get(section_id)
        if not item:
            continue
        label = f"第 {section_id} 节"
        if item.get("status") != "passed":
            errors.append(f"{label} 写前情绪合同未通过")
        excerpt = str(item.get("source_excerpt") or "").strip()
        if len(excerpt) < 20 or excerpt not in source_text:
            errors.append(f"{label} source_excerpt 必须是主体原文中的连续真实片段")
        source_intensity = validate_beat_list(
            item.get("source_emotion_beats"),
            "source_evidence",
            source_text,
            f"{label} source_emotion_beats",
            errors,
        )
        target_intensity = validate_beat_list(
            item.get("target_outline_beats"),
            "outline_evidence",
            outline_text,
            f"{label} target_outline_beats",
            errors,
        )
        for role in REQUIRED_BEAT_ROLES:
            if role in source_intensity and role in target_intensity:
                if target_intensity[role] < source_intensity[role]:
                    errors.append(f"{label} {role} 目标烈度低于主体原文")
        for field in REQUIRED_PLAN_FIELDS:
            if not non_empty_text(item.get(field)):
                errors.append(f"{label} 缺少 {field}")
        if item.get("source_like_direct_emotion_preserved") is not True:
            errors.append(f"{label} 必须保留主体原文式直接情绪与即时判断")
        if item.get("surface_copy_rejected") is not True:
            errors.append(f"{label} 必须确认拒绝表层复刻")
        if len(str(item.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{label} manual_judgment 过短")
    if data.get("reviewed_by_current_model") is not True:
        errors.append("情绪颗粒度合同必须由当前模型逐节人工复核")
    if data.get("prewrite_status") != "passed":
        errors.append("prewrite_status 必须为 passed")
    return errors, data


def validate_quote_fields(
    item: dict[str, Any], section_text: str, label: str, errors: list[str]
) -> None:
    for field in REQUIRED_REVIEW_QUOTE_FIELDS:
        quotes = quote_list(item.get(field))
        if not quotes:
            errors.append(f"{label} 缺少 {field}")
        for quote in quotes:
            if quote not in section_text:
                errors.append(f"{label} {field} 引用不在本节正文中: {quote[:30]}")
    old_wound = item.get("old_wound_trigger_review")
    if not isinstance(old_wound, dict) or not isinstance(old_wound.get("applicable"), bool):
        errors.append(f"{label} 缺少 old_wound_trigger_review 人工裁决")
        return
    quotes = quote_list(old_wound.get("target_quotes"))
    if old_wound.get("applicable") is True and not quotes:
        errors.append(f"{label} 旧伤适用却没有正文证据")
    if old_wound.get("applicable") is False and not non_empty_text(old_wound.get("rationale")):
        errors.append(f"{label} 旧伤不适用必须说明原因")
    for quote in quotes:
        if quote not in section_text:
            errors.append(f"{label} 旧伤证据不在本节正文中: {quote[:30]}")


def validate_draft_data(
    data: dict[str, Any], source_original: Path, draft: Path
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        return ["情绪颗粒度合同缺少 bindings"], data
    outline_binding = bindings.get("outline")
    outline_path = Path(str(outline_binding.get("path") or "")) if isinstance(outline_binding, dict) else None
    if outline_path is None or not outline_path.is_file():
        return ["情绪颗粒度合同绑定的细纲不存在"], data
    prewrite_errors, _ = validate_prewrite_data(data, source_original, outline_path)
    errors.extend(prewrite_errors)
    validate_binding(bindings.get("draft"), draft, "正文", errors)
    sections = draft_sections(draft.read_text(encoding="utf-8"))
    expected_ids = outline_section_ids(outline_path.read_text(encoding="utf-8"))
    if list(sections) != expected_ids:
        errors.append("正文数字小节必须与细纲完整对应且顺序一致")
    contracts = {
        str(item.get("section_id")): item
        for item in data.get("section_contracts", [])
        if isinstance(item, dict)
    }
    reviews = data.get("section_reviews")
    if not isinstance(reviews, list):
        errors.append("section_reviews 必须是列表")
        reviews = []
    by_id = {
        str(item.get("section_id")): item for item in reviews if isinstance(item, dict)
    }
    if list(by_id) != expected_ids:
        errors.append("逐节正文情绪复核必须完整覆盖且顺序一致")
    for section_id in expected_ids:
        item = by_id.get(section_id)
        if not item:
            continue
        label = f"第 {section_id} 节"
        section_text = sections.get(section_id, "")
        if item.get("status") != "passed":
            errors.append(f"{label} 正文情绪复核未通过")
        contract = contracts.get(section_id, {})
        source_beats = {
            str(beat.get("role")): beat.get("intensity")
            for beat in contract.get("source_emotion_beats", [])
            if isinstance(beat, dict)
        }
        beat_reviews = item.get("beat_reviews")
        if not isinstance(beat_reviews, list):
            errors.append(f"{label} beat_reviews 必须是列表")
            beat_reviews = []
        beat_by_role = {
            str(beat.get("role")): beat for beat in beat_reviews if isinstance(beat, dict)
        }
        if list(beat_by_role) != list(REQUIRED_BEAT_ROLES):
            errors.append(f"{label} beat_reviews 情绪拍不完整或顺序错误")
        for role in REQUIRED_BEAT_ROLES:
            beat = beat_by_role.get(role)
            if not beat:
                continue
            source_intensity = beat.get("source_intensity")
            target_intensity = beat.get("target_intensity")
            if source_intensity != source_beats.get(role):
                errors.append(f"{label} {role} source_intensity 未按写前合同回填")
            if not isinstance(target_intensity, int) or isinstance(target_intensity, bool) or not 1 <= target_intensity <= 10:
                errors.append(f"{label} {role} target_intensity 必须为 1-10 整数")
            elif isinstance(source_intensity, int) and target_intensity < source_intensity:
                errors.append(f"{label} {role} 正文烈度低于主体原文")
            quotes = quote_list(beat.get("target_quotes"))
            if not quotes:
                errors.append(f"{label} {role} 缺少正文情绪拍证据")
            for quote in quotes:
                if quote not in section_text:
                    errors.append(f"{label} {role} 引用不在本节正文中: {quote[:30]}")
            if len(str(beat.get("parity_judgment") or "").strip()) < 12:
                errors.append(f"{label} {role} parity_judgment 过短")
        validate_quote_fields(item, section_text, label, errors)
        expected_flags = {
            "source_like_direct_emotion_preserved": True,
            "target_not_lower_intensity": True,
            "anti_ai_cleanup_applied_during_first_draft": False,
            "auxiliary_prose_voice_used": False,
            "surface_copy_rejected": True,
        }
        for field, expected in expected_flags.items():
            if item.get(field) is not expected:
                errors.append(f"{label} 要求 {field}={str(expected).lower()}")
        if len(str(item.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{label} manual_judgment 过短")
    if data.get("draft_status") != "passed":
        errors.append("draft_status 必须为 passed")
    return errors, data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--source-original", required=True)
    init_parser.add_argument("--receipt", required=True)

    for command in ("bind-outline", "validate-prewrite", "bind-draft", "validate-draft"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--receipt", required=True)
        if command in ("bind-outline", "validate-prewrite"):
            sub.add_argument("--outline", required=True)
        if command in ("bind-draft", "validate-draft"):
            sub.add_argument("--draft", required=True)
        if command in ("validate-prewrite", "validate-draft"):
            sub.add_argument("--source-original", required=True)

    args = parser.parse_args()
    receipt = Path(args.receipt).resolve()
    if args.command == "init":
        data = create_receipt(args.project, Path(args.source_original).resolve())
        write_json(receipt, data)
        print(f"emotional_granularity_contract: initialized -> {receipt}")
        return 0

    data = load_json(receipt)
    if args.command == "bind-outline":
        data = bind_outline(data, Path(args.outline).resolve())
        write_json(receipt, data)
        print("emotional_granularity_contract: outline bound")
        return 0
    if args.command == "bind-draft":
        data = bind_draft(data, Path(args.draft).resolve())
        write_json(receipt, data)
        print("emotional_granularity_contract: draft bound")
        return 0
    if args.command == "validate-prewrite":
        errors, _ = validate_prewrite_data(
            data, Path(args.source_original).resolve(), Path(args.outline).resolve()
        )
    else:
        errors, _ = validate_draft_data(
            data, Path(args.source_original).resolve(), Path(args.draft).resolve()
        )
    if errors:
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"emotional_granularity_contract: passed ({args.command})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
