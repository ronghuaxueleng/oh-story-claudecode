#!/usr/bin/env python3
"""Validate the source-bound scene-performance contract for a short-story outline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SECTION_PATTERN = re.compile(r"^##\s+(\d+)[.、．]")
BRIDGE_HEADING_PATTERN = re.compile(r"^##\s+\[?(BID-\d+)\]?", re.MULTILINE)
REQUIRED_SECTION_FIELDS = (
    "irreversible_action",
    "controlling_object",
    "source_function_mechanism",
    "original_scene_granularity",
    "source_mechanism",
    "information_delay",
    "character_missteps",
    "interaction_exchange",
    "conflict_carrier",
    "relationship_legibility",
    "emotion_intensity",
    "professional_shell_translation",
    "source_emotion_parity",
    "forbidden_items",
    "outline_evidence",
    "manual_judgment",
    "scene_units",
)
REQUIRED_BRIDGE_PARITY_FIELDS = (
    "source_bridge_id",
    "source_bridge_name",
    "source_path",
    "source_sha256",
    "source_required_sequence",
    "source_must_keep_actions",
    "source_scene_granularity",
    "source_plot_beats",
    "target_plot_beats",
    "plot_beat_mapping",
    "plot_granularity_parity_judgment",
    "source_emotion_sequence",
    "target_emotion_sequence",
    "source_reversal_beat",
    "target_reversal_beat",
    "source_peak_beat",
    "target_peak_beat",
    "reader_experience_parity",
    "emotion_parity_judgment",
    "target_outline_sections",
    "target_outline_evidence",
    "parity_status",
    "adaptation_reason",
    "missing_or_weakened_risk",
    "manual_judgment",
)
EMOTION_BEAT_FIELDS = (
    "beat_id",
    "role",
    "trigger",
    "relationship_position_change",
    "reader_effect",
    "intensity",
    "evidence",
)
TARGET_EMOTION_SEMANTIC_FIELDS = (
    "hurt_object",
    "expectation_before",
    "expectation_after",
    "action_impulse_before",
    "action_impulse_after",
    "equivalence_reason",
)
PLOT_BEAT_FIELDS = (
    "beat_id",
    "action",
    "actor",
    "pressure_or_trigger",
    "control_change",
    "information_change",
    "consequence",
    "evidence",
)
PLOT_BEAT_MAPPING_FIELDS = (
    "source_beat_id",
    "target_beat_id",
    "status",
    "adaptation_note",
)
SOURCE_PLOT_LEDGER_FIELDS = (
    "beat_id",
    "actor",
    "action",
    "object_or_receiver",
    "pressure_or_trigger",
    "control_change",
    "information_change",
    "consequence",
    "source_range",
    "source_evidence",
    "bid_ids",
)
SOURCE_STYLE_GRANULARITY_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def outline_sections(text: str) -> list[str]:
    return [match.group(1) for match in map(SECTION_PATTERN.match, text.splitlines()) if match]


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def nonempty_list(value: Any, minimum: int = 1) -> bool:
    return (
        isinstance(value, list)
        and len([item for item in value if str(item).strip()]) >= minimum
    )


def bridge_catalog_path(source: Path) -> Path:
    return source.parent.parent / "写作资产" / "桥段施工卡.md"


def bridge_ids_from_catalog(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return list(dict.fromkeys(BRIDGE_HEADING_PATTERN.findall(read_text(path))))


def subflow_catalog_path(source: Path) -> Path:
    return source.parent.parent / "写作资产" / "子流程索引.jsonl"


def source_plot_ledger_path(source: Path) -> Path:
    return source.parent.parent / "写作资产" / "全文情节微拍总账.json"


def source_emotion_ledger_path(source: Path) -> Path:
    return source.parent.parent / "写作资产" / "全文情绪颗粒总账.json"


def load_ledger_payload(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        payload = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("beats"), list):
        raise ValueError(f"{label}必须是含 beats 列表的 JSON 对象: {path}")
    return payload


def normalized_plot_ledger_beats(payload: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for beat in payload.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        normalized.append(
            {
                "beat_id": beat.get("beat_id", ""),
                "action": beat.get("action", ""),
                "actor": beat.get("actor", ""),
                "pressure_or_trigger": beat.get("pressure_or_trigger", ""),
                "control_change": beat.get("control_change", ""),
                "information_change": beat.get("information_change", ""),
                "consequence": beat.get("consequence", ""),
                "evidence": beat.get("source_evidence", ""),
                "object_or_receiver": beat.get("object_or_receiver", ""),
                "source_range": beat.get("source_range", {}),
                "bid_ids": beat.get("bid_ids", []),
            }
        )
    return normalized


def subflow_records_from_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"子流程索引 JSONL 第 {line_number} 行无效: {path}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"子流程索引第 {line_number} 行必须是对象: {path}")
        records.append(record)
    return records


def subflow_coverage_scaffold(
    source: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    return {
        "source_path": source["path"],
        "source_sha256": source["sha256"],
        "subflow_id": record.get("subflow_id", ""),
        "parent_bridge_id": record.get("parent_bridge_id", ""),
        "source_range": record.get("source_range", ""),
        "source_style_granularity": record.get("source_style_granularity", {}),
        "target_outline_sections": [],
        "transferred_style_fields": {
            field: {
                "target_outline_evidence": [],
                "transfer_method": "",
                "surface_copy_rejected": None,
            }
            for field in SOURCE_STYLE_GRANULARITY_FIELDS
        },
        "coverage_status": "pending",
        "adaptation_boundary": "",
        "manual_judgment": "",
    }


def create_receipt(
    project: str,
    outline_path: Path,
    source_paths: list[Path],
    source_mode: str = "full_bridge",
) -> dict[str, Any]:
    outline = outline_path.resolve()
    if not outline.is_file():
        raise FileNotFoundError(f"细纲不存在: {outline}")
    sources = []
    for index, source_path in enumerate(source_paths):
        source = source_path.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"原文不存在: {source}")
        catalog = bridge_catalog_path(source)
        if not catalog.is_file():
            raise FileNotFoundError(f"桥段施工卡不存在: {catalog}")
        available_bridge_ids = bridge_ids_from_catalog(catalog)
        if not available_bridge_ids:
            raise ValueError(f"桥段施工卡未识别到 BID: {catalog}")
        role = "primary" if index == 0 else "auxiliary"
        plot_ledger = source_plot_ledger_path(source)
        if source_mode == "full_bridge" and not plot_ledger.is_file():
            raise FileNotFoundError(
                f"全文情节微拍总账不存在，必须先回 story-short-analyze 从 L1 到 EOF 独立抽取: {plot_ledger}"
            )
        plot_payload = (
            load_ledger_payload(plot_ledger, "全文情节微拍总账")
            if source_mode == "full_bridge"
            else {"beats": []}
        )
        plot_beats = normalized_plot_ledger_beats(plot_payload)
        subflow_catalog = subflow_catalog_path(source)
        if role == "primary" and not subflow_catalog.is_file():
            raise FileNotFoundError(f"主体原文子流程索引不存在: {subflow_catalog}")
        subflow_records = (
            subflow_records_from_catalog(subflow_catalog) if role == "primary" else []
        )
        subflow_ids = [
            str(record.get("subflow_id") or "").strip() for record in subflow_records
        ]
        if role == "primary" and (not subflow_ids or any(not item for item in subflow_ids)):
            raise ValueError(f"主体原文子流程索引缺少有效 subflow_id: {subflow_catalog}")
        sources.append(
            {
                "path": str(source),
                "sha256": sha256(source),
                "role": role,
                "bridge_catalog": {
                    "path": str(catalog.resolve()),
                    "sha256": sha256(catalog),
                },
                "plot_beat_ledger": (
                    {
                        "path": str(plot_ledger.resolve()),
                        "sha256": sha256(plot_ledger),
                    }
                    if source_mode == "full_bridge"
                    else None
                ),
                "available_bridge_ids": available_bridge_ids,
                "required_bridge_ids": (
                    available_bridge_ids
                    if role == "primary" and source_mode == "full_bridge"
                    else []
                ),
                "selected_bridge_ids": (
                    available_bridge_ids
                    if role == "primary" and source_mode == "full_bridge"
                    else []
                ),
                "subflow_catalog": (
                    {
                        "path": str(subflow_catalog.resolve()),
                        "sha256": sha256(subflow_catalog),
                    }
                    if role == "primary"
                    else None
                ),
                "available_subflow_ids": subflow_ids,
                "required_subflow_ids": subflow_ids if role == "primary" else [],
                "available_plot_beat_ids": [
                    str(beat.get("beat_id") or "").strip() for beat in plot_beats
                ],
            }
        )

    sections = outline_sections(read_text(outline))
    first_source = sources[0]
    primary_bridge_ids = first_source["required_bridge_ids"]
    primary_plot_payload = (
        load_ledger_payload(
            Path(first_source["plot_beat_ledger"]["path"]),
            "主体全文情节微拍总账",
        )
        if source_mode == "full_bridge"
        else {"beats": []}
    )
    primary_plot_beats = normalized_plot_ledger_beats(primary_plot_payload)
    primary_subflow_records = subflow_records_from_catalog(
        Path(first_source["subflow_catalog"]["path"])
    )
    return {
        "version": "1.3",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "execution_mode": "current_model_manual",
        "source_mode": source_mode,
        "reviewed_by_current_model": False,
        "outline": {"path": str(outline), "sha256": sha256(outline)},
        "selected_source_originals": sources,
        "global_review": {
            "full_source_mechanisms_reviewed": False,
            "dual_track_function_and_scene_granularity_reviewed": False,
            "source_bridge_flow_inventory_completed": False,
            "source_plot_beat_inventory_completed": False,
            "plot_and_emotion_ledgers_independently_built": False,
            "outline_bridge_flow_parity_reviewed_before_draft": False,
            "plot_beat_mapping_reviewed_before_draft": False,
            "relationship_legibility_reviewed_before_draft": False,
            "professional_shell_translation_reviewed_before_draft": False,
            "source_emotion_flow_parity_reviewed_before_draft": False,
            "complete_source_emotion_beat_inventory_reviewed": False,
            "source_subflow_granularity_coverage_reviewed": False,
            "granularity_transfer_contract_reviewed": False,
            "strong_emotion_required": False,
            "mechanism_transfer_boundary": "",
            "global_storyboard_or_process_list": None,
            "manual_judgment": "",
        },
        "granularity_transfer_contract": [],
        "source_subflow_granularity_coverage": [
            subflow_coverage_scaffold(first_source, record)
            for record in primary_subflow_records
        ],
        "source_bridge_flow_inventory": [
            {
                "source_path": first_source["path"],
                "source_sha256": first_source["sha256"],
                "bridge_id": bridge_id,
                "bridge_name": "",
                "source_required_sequence": [],
                "source_must_keep_actions": [],
                "source_scene_granularity": "",
                "source_plot_beats": [
                    beat
                    for beat in primary_plot_beats
                    if bridge_id in (beat.get("bid_ids") or [])
                ],
                "source_plot_beat_completion_review": "",
                "source_end_state_change": "",
                "cannot_merge_or_drop_reason": "",
            }
            for bridge_id in primary_bridge_ids
        ],
        "outline_bridge_flow_parity": [
            {
                "source_bridge_id": bridge_id,
                "source_bridge_name": "",
                "source_path": first_source["path"],
                "source_sha256": first_source["sha256"],
                "source_required_sequence": [],
                "source_must_keep_actions": [],
                "source_scene_granularity": "",
                "source_plot_beats": [
                    beat
                    for beat in primary_plot_beats
                    if bridge_id in (beat.get("bid_ids") or [])
                ],
                "target_plot_beats": [],
                "plot_beat_mapping": [],
                "plot_granularity_parity_judgment": "",
                "source_emotion_sequence": [],
                "target_emotion_sequence": [],
                "source_reversal_beat": 0,
                "target_reversal_beat": 0,
                "source_peak_beat": 0,
                "target_peak_beat": 0,
                "reader_experience_parity": None,
                "emotion_parity_judgment": "",
                "target_outline_sections": [],
                "target_outline_evidence": [],
                "parity_status": "pending",
                "adaptation_reason": "",
                "missing_or_weakened_risk": "",
                "manual_judgment": "",
            }
            for bridge_id in primary_bridge_ids
        ],
        "outside_bridge_plot_parity": {
            "source_plot_beats": [
                beat for beat in primary_plot_beats if not beat.get("bid_ids")
            ],
            "target_plot_beats": [],
            "plot_beat_mapping": [],
            "plot_granularity_parity_judgment": "",
            "target_outline_sections": [],
            "target_outline_evidence": [],
            "parity_status": (
                "pending"
                if any(not beat.get("bid_ids") for beat in primary_plot_beats)
                else "not_applicable"
            ),
            "manual_judgment": "",
        },
        "sections": [
            {
                "section_id": section_id,
                "verdict": "pending",
                "irreversible_action": "",
                "controlling_object": "",
                "source_function_mechanism": {
                    "asset_path": "",
                    "function_type": "",
                    "asset_rule": "",
                    "why_selected_for_this_section": "",
                },
                "original_scene_granularity": {
                    "source_path": "",
                    "source_sha256": "",
                    "source_scene": "",
                    "action_sequence": "",
                    "body_object_space_control": "",
                    "dialogue_forces_action": "",
                    "bystander_or_order_shift": "",
                    "scene_end_residue": "",
                },
                "source_mechanism": {
                    "source_path": "",
                    "source_sha256": "",
                    "source_scene": "",
                    "transferable_mechanism": "",
                    "adaptation_boundary": "",
                },
                "information_delay": {
                    "entry_known": "",
                    "leaked_in_scene": "",
                    "deferred_to_later": "",
                },
                "character_missteps": [],
                "interaction_exchange": {
                    "pressure": "",
                    "forced_response": "",
                    "visible_change": "",
                },
                "conflict_carrier": {
                    "contested_power": "",
                    "carrier": "",
                    "consequence": "",
                },
                "relationship_legibility": {
                    "plain_relationship_roles": "",
                    "plain_relationship_injury": "",
                    "understandable_without_domain_knowledge": None,
                },
                "emotion_intensity": {
                    "score": 0,
                    "concrete_humiliation_or_pain": "",
                    "emotional_turn": "",
                    "escalation_vs_previous": "",
                },
                "professional_shell_translation": {
                    "plain_language_conflict": "",
                    "domain_detail_function": "",
                    "conflict_survives_without_jargon": None,
                    "relationship_first": None,
                },
                "source_emotion_parity": {
                    "source_excerpt": "",
                    "source_emotion_sequence": [],
                    "target_emotion_sequence": [],
                    "source_intensity_score": 0,
                    "target_intensity_score": 0,
                    "source_reversal_beat": 0,
                    "target_reversal_beat": 0,
                    "source_peak_beat": 0,
                    "target_peak_beat": 0,
                    "ending_afterpain_equivalent": None,
                    "reader_experience_equivalent": None,
                    "manual_judgment": "",
                    "parity_status": "pending",
                    "adaptation_boundary": "",
                },
                "forbidden_items": [],
                "outline_evidence": [],
                "scene_units": [],
                "manual_judgment": "",
            }
            for section_id in sections
        ],
        "blocking_failures": [],
    }


def validate_binding(
    binding: Any,
    label: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(binding, dict):
        errors.append(f"{label}必须是对象")
        return None
    path_text = str(binding.get("path") or "").strip()
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        errors.append(f"{label}不存在: {path}")
        return None
    if binding.get("sha256") != sha256(path):
        errors.append(f"{label}SHA 已变化，必须重新人工验收")
    return path


def validate_source_mechanism(
    value: Any,
    source_paths: set[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} source_mechanism 必须是对象")
        return
    source_path = Path(str(value.get("source_path") or "")).expanduser().resolve()
    if str(source_path) not in source_paths:
        errors.append(f"{label} 必须绑定选中的原文来源")
    elif value.get("source_sha256") != sha256(source_path):
        errors.append(f"{label} 原文 SHA 不一致")
    for field in ("source_scene", "transferable_mechanism", "adaptation_boundary"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} source_mechanism.{field} 不能为空")


def validate_source_function_mechanism(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} source_function_mechanism 必须是对象")
        return
    for field in (
        "asset_path",
        "function_type",
        "asset_rule",
        "why_selected_for_this_section",
    ):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} source_function_mechanism.{field} 不能为空")


def validate_original_scene_granularity(
    value: Any,
    source_paths: set[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} original_scene_granularity 必须是对象")
        return
    source_path = Path(str(value.get("source_path") or "")).expanduser().resolve()
    if str(source_path) not in source_paths:
        errors.append(f"{label} original_scene_granularity 必须绑定选中的原文来源")
    elif value.get("source_sha256") != sha256(source_path):
        errors.append(f"{label} original_scene_granularity 原文 SHA 不一致")
    for field in (
        "source_scene",
        "action_sequence",
        "body_object_space_control",
        "dialogue_forces_action",
        "bystander_or_order_shift",
        "scene_end_residue",
    ):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} original_scene_granularity.{field} 不能为空")


def validate_information_delay(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} information_delay 必须是对象")
        return
    for field in ("entry_known", "leaked_in_scene", "deferred_to_later"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} information_delay.{field} 不能为空")


def validate_exchange(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} interaction_exchange 必须是对象")
        return
    for field in ("pressure", "forced_response", "visible_change"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} interaction_exchange.{field} 不能为空")


def validate_scene_units(value: Any, label: str, outline_text: str, section_id: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        errors.append(f"{label} scene_units 必须包含 1-3 个完整场面")
        return errors
    actual_e: list[str] = []
    actual_p: list[str] = []
    allocated = 0
    for index, scene in enumerate(value, start=1):
        scene_label = f"{label}.scene_units[{index}]"
        if not isinstance(scene, dict):
            errors.append(f"{scene_label} 必须是对象")
            continue
        actual_e.extend(str(item).strip() for item in scene.get("emotion_beat_ids", []))
        actual_p.extend(str(item).strip() for item in scene.get("plot_beat_ids", []))
        chars = scene.get("allocated_chars")
        if not isinstance(chars, int) or chars < 240:
            errors.append(f"{scene_label}.allocated_chars 必须至少 240")
        else:
            allocated += chars
        if scene.get("full_scene_required") is not True or scene.get("summary_only") is not False:
            errors.append(f"{scene_label} 必须声明 full_scene_required=true / summary_only=false")
        for field in ("entry_pressure", "turning_action", "visible_consequence", "aftershock", "reader_emotion_path"):
            if not nonempty_text(scene.get(field)):
                errors.append(f"{scene_label}.{field} 不能为空")
        chain = scene.get("interaction_chain")
        if not nonempty_list(chain, minimum=3):
            errors.append(f"{scene_label}.interaction_chain 必须至少 3 步施压/接招")
        else:
            generic_chain_terms = (
                "一方用",
                "另一方用错答或抢物被迫接招",
                "现场以",
                "出现可见换权",
            )
            if any(
                any(term in str(step) for term in generic_chain_terms)
                for step in chain
            ):
                errors.append(
                    f"{scene_label}.interaction_chain 仍含泛化施压/接招模板，必须点名人物、动作和即时结果"
                )
        evidence = scene.get("outline_evidence")
        if not nonempty_list(evidence, minimum=2):
            errors.append(f"{scene_label}.outline_evidence 必须引用至少 2 条当前细纲原句")
        elif any(str(quote).strip() not in outline_text for quote in evidence):
            errors.append(f"{scene_label}.outline_evidence 必须来自当前细纲")
    if len(set(actual_e)) != len(actual_e) or len(set(actual_p)) != len(actual_p):
        errors.append(f"{label}.scene_units E/P 拍不得重复分配")
    target_chars = sum(int(scene.get("allocated_chars", 0)) for scene in value if isinstance(scene, dict))
    declared = next((scene.get("target_chars") for scene in value if isinstance(scene, dict) and scene.get("target_chars")), target_chars)
    if isinstance(declared, int) and target_chars != declared:
        errors.append(f"{label}.scene_units 分配字数之和必须等于 target_chars")
    return errors


def validate_conflict(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} conflict_carrier 必须是对象")
        return
    for field in ("contested_power", "carrier", "consequence"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} conflict_carrier.{field} 不能为空")


def validate_relationship_legibility(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} relationship_legibility 必须是对象")
        return
    for field in ("plain_relationship_roles", "plain_relationship_injury"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} relationship_legibility.{field} 不能为空")
    if value.get("understandable_without_domain_knowledge") is not True:
        errors.append(f"{label} 必须让不了解职业背景的读者直接看懂关系与伤害")


def validate_emotion_intensity(
    value: Any,
    label: str,
    errors: list[str],
    *,
    strong_emotion_required: bool,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} emotion_intensity 必须是对象")
        return
    score = value.get("score")
    if not isinstance(score, (int, float)) or not 1 <= score <= 10:
        errors.append(f"{label} emotion_intensity.score 必须为 1-10")
    elif strong_emotion_required and score < 7:
        errors.append(f"{label} 强情绪稿情绪烈度不得低于 7")
    for field in (
        "concrete_humiliation_or_pain",
        "emotional_turn",
        "escalation_vs_previous",
    ):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} emotion_intensity.{field} 不能为空")


def validate_professional_shell_translation(
    value: Any,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} professional_shell_translation 必须是对象")
        return
    for field in ("plain_language_conflict", "domain_detail_function"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} professional_shell_translation.{field} 不能为空")
    if value.get("conflict_survives_without_jargon") is not True:
        errors.append(f"{label} 删除职业术语后，关系冲突仍必须成立")
    if value.get("relationship_first") is not True:
        errors.append(f"{label} 必须先写关系伤害，再让职业细节承担后果")


def validate_plot_beats(
    value: Any,
    label: str,
    errors: list[str],
    *,
    evidence_text: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} 必须逐句填写原文实际存在的全部情节拍，不设模板拍数")
        return []
    beats: list[dict[str, Any]] = []
    beat_ids: set[str] = set()
    used_evidence: set[str] = set()
    for index, beat in enumerate(value, start=1):
        beat_label = f"{label}[{index}]"
        if not isinstance(beat, dict):
            errors.append(f"{beat_label} 必须是对象")
            continue
        for field in PLOT_BEAT_FIELDS:
            if field not in beat:
                errors.append(f"{beat_label}.{field} 缺失")
            if not nonempty_text(beat.get(field)):
                errors.append(f"{beat_label}.{field} 不能为空")
        beat_id = str(beat.get("beat_id") or "").strip()
        if beat_id in beat_ids:
            errors.append(f"{beat_label}.beat_id 重复: {beat_id}")
        elif beat_id:
            beat_ids.add(beat_id)
        evidence = str(beat.get("evidence") or "").strip()
        if evidence and evidence not in evidence_text:
            errors.append(f"{beat_label}.evidence 不在绑定文本中: {evidence!r}")
        if evidence in used_evidence:
            errors.append(
                f"{beat_label}.evidence 与前拍重复，不能用同一句证据冒充多个有效情节拍"
            )
        elif evidence:
            used_evidence.add(evidence)
        beats.append(beat)
    return beats


def validate_plot_beat_mapping(
    value: Any,
    source_beats: list[dict[str, Any]],
    target_beats: list[dict[str, Any]],
    label: str,
    errors: list[str],
) -> None:
    if len(source_beats) != len(target_beats):
        errors.append(f"{label} 原文与目标情节拍数必须完全一致，禁止漏拍、并拍或压缩")
    if not isinstance(value, list):
        errors.append(f"{label}.plot_beat_mapping 必须是逐拍映射列表")
        return
    if len(value) != len(source_beats):
        errors.append(f"{label}.plot_beat_mapping 数量必须等于原文全部情节拍数")

    source_ids = [str(beat.get("beat_id") or "").strip() for beat in source_beats]
    target_ids = [str(beat.get("beat_id") or "").strip() for beat in target_beats]
    mapped_source_ids: list[str] = []
    mapped_target_ids: list[str] = []
    forbidden_statuses = {"missing", "weakened", "merged", "compressed", "omitted"}
    for index, mapping in enumerate(value, start=1):
        mapping_label = f"{label}.plot_beat_mapping[{index}]"
        if not isinstance(mapping, dict):
            errors.append(f"{mapping_label} 必须是对象")
            continue
        for field in PLOT_BEAT_MAPPING_FIELDS:
            if field not in mapping:
                errors.append(f"{mapping_label}.{field} 缺失")
            if not nonempty_text(mapping.get(field)):
                errors.append(f"{mapping_label}.{field} 不能为空")
        source_id = str(mapping.get("source_beat_id") or "").strip()
        target_id = str(mapping.get("target_beat_id") or "").strip()
        status = str(mapping.get("status") or "").strip()
        mapped_source_ids.append(source_id)
        mapped_target_ids.append(target_id)
        if status not in {"matched", "adapted"}:
            suffix = "；禁止 missing/weakened/merged/compressed/omitted" if status in forbidden_statuses else ""
            errors.append(f"{mapping_label}.status 只能是 matched/adapted{suffix}")

    if mapped_source_ids != source_ids:
        errors.append(f"{label} 原文情节拍必须按原顺序且每拍仅映射一次")
    if mapped_target_ids != target_ids:
        errors.append(f"{label} 目标情节拍必须按对应顺序且每拍仅承接一个原文拍")
    if len(mapped_source_ids) != len(set(mapped_source_ids)):
        errors.append(f"{label} 同一原文情节拍不能重复映射")
    if len(mapped_target_ids) != len(set(mapped_target_ids)):
        errors.append(f"{label} 两个原文情节拍不能合并到同一个目标情节拍")


def normalized_surface_text(value: Any) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(value or ""))


CONSTRUCTION_EVIDENCE_MARKERS = (
    "不照搬",
    "没有照搬",
    "不能写成",
    "不承担",
    "不补",
    "只供应",
    "只保留",
    "公开场不能",
    "叙述不写成",
    "这里没有",
    "机制迁移",
    "目标事件触发",
)
GENERIC_SEMANTIC_MARKERS = (
    "当前关系压力",
    "关系位置发生实际换主",
    "关系后果继续传到下一拍",
    "位置继续偏移",
    "感到该角色",
    "感到这一拍",
    "目标婚姻场景",
    "实际选择与后果",
)


def is_construction_evidence(value: Any) -> bool:
    text = str(value or "")
    return any(marker in text for marker in CONSTRUCTION_EVIDENCE_MARKERS)


def validate_target_semantic_antifraud(
    beats: list[dict[str, Any]], label: str, errors: list[str], *, kind: str
) -> None:
    if not beats:
        return
    semantic_fields = (
        ("pressure_or_trigger", "control_change", "information_change", "consequence")
        if kind == "plot"
        else ("trigger", "relationship_position_change", "reader_effect", *TARGET_EMOTION_SEMANTIC_FIELDS)
    )
    signatures: list[tuple[str, ...]] = []
    generic_hits = 0
    for index, beat in enumerate(beats, start=1):
        beat_label = f"{label}[{index}]"
        evidence = str(beat.get("evidence") or "").strip()
        if is_construction_evidence(evidence):
            errors.append(f"{beat_label}.evidence 是施工/禁写说明，不是目标故事中实际发生的场面证据")
        values = tuple(normalized_surface_text(beat.get(field)) for field in semantic_fields)
        signatures.append(values)
        joined = "".join(str(beat.get(field) or "") for field in semantic_fields)
        if any(marker in joined for marker in GENERIC_SEMANTIC_MARKERS):
            generic_hits += 1
    if len(beats) >= 4 and generic_hits >= max(3, len(beats) // 3):
        errors.append(f"{label} 大量复用通用施压/位移/后果模板，不能用字段非空冒充逐拍语义迁移")
    if len(beats) >= 4 and len(set(signatures)) < max(3, len(beats) // 2):
        errors.append(f"{label} 逐拍语义签名高度重复，必须按每拍真实触发、换权和后果重建")


def target_actor_tokens(value: Any) -> list[str]:
    return [
        token.strip()
        for token in re.split(r"[、,，/；;]|(?:与|和)", str(value or ""))
        if len(token.strip()) >= 2
    ]


def actor_evidence_resolves(actor: Any, actor_evidence: Any, action: Any) -> bool:
    tokens = target_actor_tokens(actor)
    evidence_surface = normalized_surface_text(actor_evidence)
    action_surface = normalized_surface_text(action)
    if tokens and any(normalized_surface_text(token) in evidence_surface for token in tokens):
        return True
    pronouns = {"他", "她", "他们", "她们", "对方", "其", "两人"}
    return bool(tokens) and str(actor_evidence).strip() in pronouns and any(
        normalized_surface_text(token) in action_surface for token in tokens
    )


def validate_target_plot_adaptation(
    source_beats: list[dict[str, Any]],
    target_beats: list[dict[str, Any]],
    label: str,
    errors: list[str],
) -> None:
    """Reject source-side analysis pasted into target beats under a new label."""
    for index, (source, target) in enumerate(zip(source_beats, target_beats), start=1):
        beat_label = f"{label} 目标情节拍[{index}]"
        source_action = normalized_surface_text(source.get("action"))
        target_surface = normalized_surface_text(
            f"{target.get('action', '')}{target.get('evidence', '')}"
        )
        if len(source_action) >= 8 and source_action in target_surface:
            errors.append(
                f"{beat_label} 仍包含原文动作句面，不能加前缀或换标题冒充目标情节拍"
            )
        actor_tokens = target_actor_tokens(target.get("actor"))
        if not actor_tokens or not any(
            normalized_surface_text(token) in target_surface for token in actor_tokens
        ):
            errors.append(
                f"{beat_label} 未在目标 action/evidence 中落下目标施事者，仍可能只是原文功能说明"
            )
        evidence_surface = normalized_surface_text(target.get("evidence"))
        actor_evidence = str(target.get("actor_evidence") or "").strip()
        if not actor_evidence or actor_evidence not in str(target.get("evidence") or ""):
            errors.append(f"{beat_label}.actor_evidence 必须逐字来自本拍 evidence，并证明真实施事者")
        elif actor_tokens and not actor_evidence_resolves(
            target.get("actor"), actor_evidence, target.get("action")
        ):
            errors.append(f"{beat_label}.actor_evidence 未点名施事者，或代词未由 action 解析为规范人物名")
        if len(str(target.get("object_or_receiver") or "").strip()) < 1:
            errors.append(f"{beat_label}.object_or_receiver 缺少逐拍目标动作对象")
        if len(str(target.get("adaptation_equivalence") or "").strip()) < 8:
            errors.append(f"{beat_label}.adaptation_equivalence 缺少等价迁移理由")
        if is_construction_evidence(target.get("evidence")):
            errors.append(f"{beat_label}.evidence 是施工说明，不能充当目标情节拍")
    validate_target_semantic_antifraud(target_beats, label, errors, kind="plot")


def load_bridge_emotion_inventory(
    source_path: Path,
    bridge_id: str,
) -> list[dict[str, Any]] | None:
    ledger_path = source_emotion_ledger_path(source_path)
    if not ledger_path.is_file():
        return None
    try:
        payload = json.loads(read_text(ledger_path))
    except json.JSONDecodeError:
        return None
    beats = payload.get("beats") if isinstance(payload, dict) else None
    if not isinstance(beats, list):
        return None
    return [
        beat
        for beat in beats
        if isinstance(beat, dict) and bridge_id in (beat.get("bid_ids") or [])
    ]


def validate_bridge_emotion_membership(
    source_path: Path,
    bridge_id: str,
    source_beats: list[dict[str, Any]],
    target_beats: list[dict[str, Any]],
    label: str,
    errors: list[str],
) -> None:
    expected = load_bridge_emotion_inventory(source_path, bridge_id)
    if expected is None:
        return
    expected_ids = [str(beat.get("beat_id") or "").strip() for beat in expected]
    actual_ids = [str(beat.get("beat_id") or "").strip() for beat in source_beats]
    if actual_ids != expected_ids:
        errors.append(
            f"{label} 原文情绪拍不符合总账 bid_ids 真实边界；桥外导语、过场、尾声拍不得塞入 {bridge_id}"
        )
    expected_by_id = {
        str(beat.get("beat_id") or "").strip(): beat for beat in expected
    }
    for index, (source, target) in enumerate(zip(source_beats, target_beats), start=1):
        beat_id = str(source.get("beat_id") or "").strip()
        ledger_beat = expected_by_id.get(beat_id)
        if ledger_beat is not None:
            if source.get("role") != ledger_beat.get("role"):
                errors.append(f"{label} {beat_id}.role 与全文情绪颗粒总账不一致")
            if source.get("intensity") != ledger_beat.get("intensity"):
                errors.append(f"{label} {beat_id}.intensity 与全文情绪颗粒总账不一致")
            source_content = normalized_surface_text(ledger_beat.get("content"))
            target_evidence = normalized_surface_text(target.get("evidence"))
            if len(source_content) >= 8 and source_content in target_evidence:
                errors.append(
                    f"{label} 目标情绪拍[{index}]仍粘贴原文内容说明，必须写成目标人物的真实场面拍"
                )
        for field, field_label in (
            ("trigger", "触发"),
            ("relationship_position_change", "关系位移"),
        ):
            if normalized_surface_text(source.get(field)) == normalized_surface_text(
                target.get(field)
            ):
                errors.append(
                    f"{label} 目标情绪拍[{index}]的{field_label}仍与原文相同，未迁移到目标世界"
                )


def validate_emotion_sequence(
    value: Any,
    label: str,
    errors: list[str],
    *,
    evidence_text: str,
    strong_emotion_required: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} 必须逐句填写原文实际存在的全部情绪拍，不设模板拍数")
        return []
    beats: list[dict[str, Any]] = []
    beat_ids: set[str] = set()
    used_evidence: set[str] = set()
    for index, beat in enumerate(value, start=1):
        beat_label = f"{label}[{index}]"
        if not isinstance(beat, dict):
            errors.append(f"{beat_label} 必须是对象")
            continue
        for field in EMOTION_BEAT_FIELDS:
            if field not in beat:
                errors.append(f"{beat_label}.{field} 缺失")
        for field in (
            "beat_id",
            "role",
            "trigger",
            "relationship_position_change",
            "reader_effect",
            "evidence",
        ):
            if not nonempty_text(beat.get(field)):
                errors.append(f"{beat_label}.{field} 不能为空")
        beat_id = str(beat.get("beat_id") or "").strip()
        if beat_id in beat_ids:
            errors.append(f"{beat_label}.beat_id 重复: {beat_id}")
        elif beat_id:
            beat_ids.add(beat_id)
        intensity = beat.get("intensity")
        if not isinstance(intensity, (int, float)) or not 1 <= intensity <= 10:
            errors.append(f"{beat_label}.intensity 必须为 1-10")
        evidence = str(beat.get("evidence") or "").strip()
        if evidence and evidence not in evidence_text:
            errors.append(f"{beat_label}.evidence 不在绑定文本中: {evidence!r}")
        if evidence in used_evidence:
            errors.append(f"{beat_label}.evidence 与前拍重复，不能用同一句证据冒充多个情绪拍")
        elif evidence:
            used_evidence.add(evidence)
        beats.append(beat)
    return beats


def validate_turn_and_peak_alignment(
    value: Any,
    source_beats: list[dict[str, Any]],
    target_beats: list[dict[str, Any]],
    label: str,
    errors: list[str],
    *,
    strong_emotion_required: bool,
) -> None:
    source_roles = [str(beat.get("role") or "").strip() for beat in source_beats]
    target_roles = [str(beat.get("role") or "").strip() for beat in target_beats]
    source_ids = [str(beat.get("beat_id") or "").strip() for beat in source_beats]
    target_ids = [str(beat.get("beat_id") or "").strip() for beat in target_beats]
    if source_roles and target_roles and source_roles != target_roles:
        errors.append(f"{label} 原文与目标情绪拍角色及顺序必须一致")
    if len(source_beats) != len(target_beats):
        errors.append(f"{label} 原文实际情绪拍与目标情绪拍数量必须一致，禁止漏拍或并拍")
    if source_ids and target_ids and source_ids != target_ids:
        errors.append(f"{label} 目标情绪拍必须沿用原文 beat_id 原顺序逐拍承接")
    for index, target_beat in enumerate(target_beats, start=1):
        beat_label = f"{label} 目标情绪拍[{index}]"
        if len(str(target_beat.get("hurt_object") or "").strip()) < 1:
            errors.append(f"{beat_label}.hurt_object 缺少实际受伤对象")
        for field in TARGET_EMOTION_SEMANTIC_FIELDS[1:]:
            if len(str(target_beat.get(field) or "").strip()) < 8:
                errors.append(f"{beat_label}.{field} 缺少可核验的情绪前后态或等价迁移理由")
        evidence = str(target_beat.get("evidence") or "").strip()
        if is_construction_evidence(evidence):
            errors.append(f"{beat_label}.evidence 是施工/禁写说明，不能充当情绪发生证据")
        hurt_object = normalized_surface_text(target_beat.get("hurt_object"))
        evidence_surface = normalized_surface_text(evidence)
        abstract_hurt = str(target_beat.get("hurt_object") or "") in {"夫妻关系", "婚姻位置", "读者预期", "在场者"}
        pronoun_resolved = bool(re.search(r"他们|她们|对方|[他她]", evidence)) and normalized_surface_text(
            target_beat.get("hurt_object")
        ) in normalized_surface_text(target_beat.get("target_story_adaptation"))
        if hurt_object and hurt_object not in evidence_surface and not abstract_hurt and not pronoun_resolved:
            errors.append(f"{beat_label}.hurt_object 必须在证据中出现，或由代词和适配说明解析")
        if normalized_surface_text(target_beat.get("expectation_before")) == normalized_surface_text(
            target_beat.get("expectation_after")
        ):
            errors.append(f"{beat_label} expectation_before/after 没有发生变化")
        if normalized_surface_text(target_beat.get("action_impulse_before")) == normalized_surface_text(
            target_beat.get("action_impulse_after")
        ):
            errors.append(f"{beat_label} action_impulse_before/after 没有发生变化")
    validate_target_semantic_antifraud(target_beats, label, errors, kind="emotion")
    if strong_emotion_required:
        for index, (source_beat, target_beat) in enumerate(
            zip(source_beats, target_beats), start=1
        ):
            source_intensity = source_beat.get("intensity")
            target_intensity = target_beat.get("intensity")
            if (
                isinstance(source_intensity, (int, float))
                and isinstance(target_intensity, (int, float))
                and target_intensity < source_intensity
            ):
                errors.append(
                    f"{label} 第 {index} 拍目标烈度低于原文，不能只保证总分相同"
                )
    for source_field, target_field, field_label in (
        ("source_reversal_beat", "target_reversal_beat", "反刀拍"),
        ("source_peak_beat", "target_peak_beat", "情绪峰值拍"),
    ):
        source_index = value.get(source_field)
        target_index = value.get(target_field)
        if not isinstance(source_index, int) or not 0 <= source_index <= len(source_beats):
            errors.append(f"{label} {source_field} 必须为 0（原文无此拍）或指向真实情绪拍")
        if not isinstance(target_index, int) or not 0 <= target_index <= len(target_beats):
            errors.append(f"{label} {target_field} 必须为 0（原文无此拍）或指向真实情绪拍")
        if (
            isinstance(source_index, int)
            and isinstance(target_index, int)
            and source_index != target_index
        ):
            errors.append(f"{label} 原文与目标的{field_label}必须同位")


def validate_source_emotion_parity(
    value: Any,
    source_texts: dict[str, str],
    outline_text: str,
    label: str,
    errors: list[str],
    *,
    strong_emotion_required: bool,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} source_emotion_parity 必须是对象")
        return
    excerpt = str(value.get("source_excerpt") or "").strip()
    if not excerpt or not any(excerpt in text for text in source_texts.values()):
        errors.append(f"{label} source_emotion_parity.source_excerpt 必须来自选中原文")
    source_beats = validate_emotion_sequence(
        value.get("source_emotion_sequence"),
        f"{label} 原文情绪流程",
        errors,
        evidence_text="\n".join(source_texts.values()),
        strong_emotion_required=strong_emotion_required,
    )
    target_beats = validate_emotion_sequence(
        value.get("target_emotion_sequence"),
        f"{label} 目标情绪流程",
        errors,
        evidence_text=outline_text,
        strong_emotion_required=strong_emotion_required,
    )
    validate_turn_and_peak_alignment(
        value,
        source_beats,
        target_beats,
        label,
        errors,
        strong_emotion_required=strong_emotion_required,
    )
    source_score = value.get("source_intensity_score")
    target_score = value.get("target_intensity_score")
    if not isinstance(source_score, (int, float)) or not 1 <= source_score <= 10:
        errors.append(f"{label} source_intensity_score 必须为 1-10")
    if not isinstance(target_score, (int, float)) or not 1 <= target_score <= 10:
        errors.append(f"{label} target_intensity_score 必须为 1-10")
    elif strong_emotion_required and isinstance(source_score, (int, float)):
        if target_score < source_score:
            errors.append(f"{label} 仿写情绪烈度低于原文，不得以功能对齐代替情绪对齐")
    if value.get("parity_status") not in {"matched", "adapted_equal_intensity"}:
        errors.append(
            f"{label} source_emotion_parity.parity_status 必须为 matched/adapted_equal_intensity"
        )
    if not nonempty_text(value.get("adaptation_boundary")):
        errors.append(f"{label} source_emotion_parity.adaptation_boundary 不能为空")
    if value.get("ending_afterpain_equivalent") is not True:
        errors.append(f"{label} 场末余痛必须与原文承担同级情绪功能")
    if value.get("reader_experience_equivalent") is not True:
        errors.append(f"{label} 必须人工确认读者体感与原文同级")
    if not nonempty_text(value.get("manual_judgment")):
        errors.append(f"{label} source_emotion_parity.manual_judgment 不能为空")


def validate_source_plot_ledgers(
    source_metadata: dict[str, dict[str, Any]],
    source_texts: dict[str, str],
    errors: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Bind plot beats to an independently persisted full-text ledger."""
    result: dict[str, list[dict[str, Any]]] = {}
    for source_key, source_info in source_metadata.items():
        source_path = Path(source_key)
        label = f"{'主体' if source_info.get('role') == 'primary' else '辅助'}全文情节微拍总账"
        ledger_path = validate_binding(
            source_info.get("plot_beat_ledger"), label, errors
        )
        if ledger_path is None:
            continue
        expected_path = source_plot_ledger_path(source_path).resolve()
        if ledger_path != expected_path:
            errors.append(f"{label}必须绑定拆文目录的固定资产: {expected_path}")
        try:
            payload = load_ledger_payload(ledger_path, label)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
            continue
        source_binding = payload.get("source")
        if not isinstance(source_binding, dict):
            errors.append(f"{label}.source 必须绑定原文路径与 SHA")
        else:
            bound_path = Path(str(source_binding.get("path") or "")).expanduser().resolve()
            if bound_path != source_path:
                errors.append(f"{label}.source.path 与选中原文不一致")
            if source_binding.get("sha256") != sha256(source_path):
                errors.append(f"{label}.source.sha256 与当前原文不一致")
        review = payload.get("completeness_review")
        if not isinstance(review, dict):
            errors.append(f"{label}.completeness_review 必须是对象")
        else:
            for field in (
                "full_text_scanned_l1_to_eof",
                "independent_from_emotion_ledger",
                "no_emotion_beat_substitution",
                "all_effective_plot_beats_preserved",
            ):
                if review.get(field) is not True:
                    errors.append(f"{label}.completeness_review.{field} 必须为 true")
            if not nonempty_text(review.get("manual_judgment")):
                errors.append(f"{label}.completeness_review.manual_judgment 不能为空")

        raw_beats = payload.get("beats") or []
        normalized = normalized_plot_ledger_beats(payload)
        if not raw_beats:
            errors.append(f"{label}.beats 不能为空")
        source_lines = source_texts.get(source_key, "").splitlines()
        seen_ids: set[str] = set()
        allowed_bids = set(source_info.get("available_bridge_ids") or [])
        for index, beat in enumerate(raw_beats, start=1):
            beat_label = f"{label}.beats[{index}]"
            if not isinstance(beat, dict):
                errors.append(f"{beat_label} 必须是对象")
                continue
            for field in SOURCE_PLOT_LEDGER_FIELDS:
                if field not in beat:
                    errors.append(f"{beat_label}.{field} 缺失")
            for field in (
                "beat_id",
                "actor",
                "action",
                "object_or_receiver",
                "pressure_or_trigger",
                "control_change",
                "information_change",
                "consequence",
                "source_evidence",
            ):
                if not nonempty_text(beat.get(field)):
                    errors.append(f"{beat_label}.{field} 不能为空")
            beat_id = str(beat.get("beat_id") or "").strip()
            if not re.fullmatch(r"P-[A-Za-z0-9_-]+", beat_id):
                errors.append(f"{beat_label}.beat_id 必须使用独立 P-* ID")
            if beat_id in seen_ids:
                errors.append(f"{beat_label}.beat_id 重复: {beat_id}")
            seen_ids.add(beat_id)
            bid_ids = beat.get("bid_ids")
            if not isinstance(bid_ids, list):
                errors.append(f"{beat_label}.bid_ids 必须是列表")
                bid_ids = []
            if len(bid_ids) > 1:
                errors.append(f"{beat_label}.bid_ids 不得让同一情节拍重复归属多个 BID，避免桥内重复消费")
            unknown_bids = sorted(set(str(item) for item in bid_ids) - allowed_bids)
            if unknown_bids:
                errors.append(f"{beat_label}.bid_ids 含未注册 BID: {', '.join(unknown_bids)}")
            source_range = beat.get("source_range")
            if not isinstance(source_range, dict):
                errors.append(f"{beat_label}.source_range 必须是行范围对象")
                continue
            start_line = source_range.get("start_line")
            end_line = source_range.get("end_line")
            if not isinstance(start_line, int) or not isinstance(end_line, int):
                errors.append(f"{beat_label}.source_range 必须含整数 start_line/end_line")
                continue
            if start_line < 1 or end_line < start_line or end_line > len(source_lines):
                errors.append(f"{beat_label}.source_range 越出原文范围")
                continue
            evidence = str(beat.get("source_evidence") or "").strip()
            line_window = "\n".join(source_lines[start_line - 1 : end_line])
            if evidence and evidence not in line_window:
                errors.append(f"{beat_label}.source_evidence 不在绑定行范围内")

        emotion_path = source_emotion_ledger_path(source_path)
        if emotion_path.is_file():
            try:
                emotion_payload = load_ledger_payload(emotion_path, "全文情绪颗粒总账")
            except (FileNotFoundError, ValueError):
                emotion_payload = {"beats": []}
            emotion_beats = [beat for beat in emotion_payload.get("beats") or [] if isinstance(beat, dict)]
            emotion_ids = [str(beat.get("beat_id") or "").strip() for beat in emotion_beats]
            plot_ids = [str(beat.get("beat_id") or "").strip() for beat in raw_beats if isinstance(beat, dict)]
            overlap = sorted(set(plot_ids) & set(emotion_ids))
            if overlap:
                errors.append(f"{label}与情绪总账共用 beat_id，已混轨: {', '.join(overlap)}")
            if plot_ids and plot_ids == emotion_ids:
                errors.append(f"{label}整套 ID 与情绪总账同序等量，不得用情绪拍冒充情节拍")
            emotion_surfaces = {
                normalized_surface_text(beat.get(field))
                for beat in emotion_beats
                for field in ("content", "role", "trigger", "relationship_position_change")
                if len(normalized_surface_text(beat.get(field))) >= 8
            }
            for index, beat in enumerate(raw_beats, start=1):
                if not isinstance(beat, dict):
                    continue
                action = normalized_surface_text(beat.get("action"))
                if len(action) >= 8 and action in emotion_surfaces:
                    errors.append(
                        f"{label}.beats[{index}].action 仅复制情绪总账内容，未独立抽取外部情节动作"
                    )
        result[source_key] = normalized
    return result


def validate_outside_bridge_plot_parity(
    value: Any,
    expected_source_beats: list[dict[str, Any]],
    outline_text: str,
    section_ids: list[str],
    errors: list[str],
) -> None:
    label = "桥外情节微拍对齐"
    if not isinstance(value, dict):
        errors.append(f"{label} outside_bridge_plot_parity 必须是对象")
        return
    source_beats = value.get("source_plot_beats")
    if source_beats != expected_source_beats:
        errors.append(f"{label}.source_plot_beats 必须与全文情节总账 bid_ids=[] 子序列完全一致")
    if not expected_source_beats:
        if value.get("target_plot_beats") or value.get("plot_beat_mapping"):
            errors.append(f"{label}无原文拍时不得补造目标拍")
        if value.get("parity_status") != "not_applicable":
            errors.append(f"{label}无原文拍时 parity_status 必须为 not_applicable")
        return
    validated_source = validate_plot_beats(
        source_beats, f"{label}原文拍", errors, evidence_text="\n".join(
            str(beat.get("evidence") or "") for beat in expected_source_beats
        )
    )
    target_beats = validate_plot_beats(
        value.get("target_plot_beats"), f"{label}目标拍", errors, evidence_text=outline_text
    )
    validate_plot_beat_mapping(
        value.get("plot_beat_mapping"), validated_source, target_beats, label, errors
    )
    validate_target_plot_adaptation(validated_source, target_beats, label, errors)
    if not nonempty_text(value.get("plot_granularity_parity_judgment")):
        errors.append(f"{label}.plot_granularity_parity_judgment 不能为空")
    if not nonempty_text(value.get("manual_judgment")):
        errors.append(f"{label}.manual_judgment 不能为空")
    if value.get("parity_status") not in {"matched", "adapted"}:
        errors.append(f"{label}.parity_status 必须为 matched/adapted")
    target_sections = [str(item).strip() for item in value.get("target_outline_sections") or []]
    if not target_sections or any(item not in section_ids for item in target_sections):
        errors.append(f"{label}.target_outline_sections 必须绑定存在的目标小节")
    evidence = value.get("target_outline_evidence")
    if not nonempty_list(evidence):
        errors.append(f"{label}.target_outline_evidence 不能为空")
    else:
        for quote in evidence:
            if str(quote).strip() not in outline_text:
                errors.append(f"{label}.target_outline_evidence 不在当前细纲中: {quote!r}")


def validate_bridge_inventory(
    value: Any,
    source_metadata: dict[str, dict[str, Any]],
    source_plot_ledgers: dict[str, list[dict[str, Any]]],
    errors: list[str],
) -> set[str]:
    if not isinstance(value, list) or not value:
        errors.append("source_bridge_flow_inventory 必须列出主体原文 BID/关键子桥段全集")
        return set()
    bridge_ids: set[str] = set()
    bridge_keys: set[tuple[str, str]] = set()
    for index, entry in enumerate(value, start=1):
        label = f"原文桥段库存[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} 必须是对象")
            continue
        source_path = Path(str(entry.get("source_path") or "")).expanduser().resolve()
        source_info = source_metadata.get(str(source_path))
        if source_info is None:
            errors.append(f"{label} 必须绑定选中的原文来源")
        elif entry.get("source_sha256") != sha256(source_path):
            errors.append(f"{label} 原文 SHA 不一致")
        bridge_id = str(entry.get("bridge_id") or "").strip()
        if not bridge_id:
            errors.append(f"{label}.bridge_id 不能为空")
        bridge_key = (str(source_path), bridge_id)
        if bridge_id and bridge_key in bridge_keys:
            errors.append(f"{label}.bridge_id 在同一来源中重复: {bridge_id}")
        else:
            if bridge_id:
                bridge_ids.add(bridge_id)
                bridge_keys.add(bridge_key)
        for field in (
            "bridge_name",
            "source_scene_granularity",
            "source_plot_beat_completion_review",
            "source_end_state_change",
            "cannot_merge_or_drop_reason",
        ):
            if not nonempty_text(entry.get(field)):
                errors.append(f"{label}.{field} 不能为空")
        if not nonempty_list(entry.get("source_required_sequence")):
            errors.append(f"{label}.source_required_sequence 必须逐拍列出原文实际顺序，不能只写功能名")
        if not nonempty_list(entry.get("source_must_keep_actions")):
            errors.append(f"{label}.source_must_keep_actions 必须列出原文实际必保动作/权力变化")
        source_text = read_text(source_path) if source_info is not None else ""
        plot_beats = validate_plot_beats(
            entry.get("source_plot_beats"),
            f"{label} 原文情节拍库存",
            errors,
            evidence_text=source_text,
        )
        expected_plot_beats = [
            beat
            for beat in source_plot_ledgers.get(str(source_path), [])
            if bridge_id in (beat.get("bid_ids") or [])
        ]
        if entry.get("source_plot_beats") != expected_plot_beats:
            errors.append(
                f"{label}.source_plot_beats 必须与独立全文情节微拍总账的 {bridge_id} 子序列完全一致"
            )
        required_sequence = entry.get("source_required_sequence")
        if isinstance(required_sequence, list) and plot_beats:
            if len(required_sequence) != len(plot_beats):
                errors.append(
                    f"{label}.source_required_sequence 必须逐项覆盖全部原文情节拍，数量不得缩减"
                )
    inventory_by_source: dict[str, set[str]] = {}
    for entry in value:
        if not isinstance(entry, dict):
            continue
        source_path = str(
            Path(str(entry.get("source_path") or "")).expanduser().resolve()
        )
        bridge_id = str(entry.get("bridge_id") or "").strip()
        source_bid_match = re.search(r"BID-\d+", bridge_id)
        if source_bid_match:
            inventory_by_source.setdefault(source_path, set()).add(
                source_bid_match.group(0)
            )
    for source_path, source_info in source_metadata.items():
        role = source_info.get("role")
        expected_field = (
            "required_bridge_ids" if role == "primary" else "selected_bridge_ids"
        )
        expected_ids = {
            str(item).strip()
            for item in source_info.get(expected_field) or []
            if str(item).strip()
        }
        if not expected_ids:
            errors.append(
                f"{'主体' if role == 'primary' else '辅助'}来源必须填写 {expected_field}: {source_path}"
            )
            continue
        available_ids = {
            str(item).strip()
            for item in source_info.get("available_bridge_ids") or []
            if str(item).strip()
        }
        unknown_ids = sorted(expected_ids - available_ids)
        if unknown_ids:
            errors.append(
                f"{expected_field} 含桥段施工卡中不存在的 BID: {source_path} -> {', '.join(unknown_ids)}"
            )
        missing_ids = sorted(expected_ids - inventory_by_source.get(source_path, set()))
        if missing_ids:
            errors.append(
                f"{'主体' if role == 'primary' else '辅助'}来源桥段库存缺失: {source_path} -> {', '.join(missing_ids)}"
            )
    return bridge_ids


def validate_bridge_parity(
    value: Any,
    inventory: Any,
    bridge_ids: set[str],
    source_texts: dict[str, str],
    source_metadata: dict[str, dict[str, Any]],
    section_ids: list[str],
    outline_text: str,
    errors: list[str],
    *,
    strong_emotion_required: bool,
) -> None:
    if not isinstance(value, list) or not value:
        errors.append("outline_bridge_flow_parity 必须逐桥证明原文流程已在细纲落成")
        return
    parity_keys: set[tuple[str, str]] = set()
    inventory_by_key = {
        (
            str(Path(str(item.get("source_path") or "")).expanduser().resolve()),
            str(item.get("bridge_id") or "").strip(),
        ): item
        for item in inventory or []
        if isinstance(item, dict)
    }
    valid_status = {"matched", "adapted"}
    for index, entry in enumerate(value, start=1):
        label = f"原文桥段对齐[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} 必须是对象")
            continue
        for field in REQUIRED_BRIDGE_PARITY_FIELDS:
            if field not in entry:
                errors.append(f"{label}.{field} 缺失")
        bridge_id = str(entry.get("source_bridge_id") or "").strip()
        source_path = Path(str(entry.get("source_path") or "")).expanduser().resolve()
        source_key = str(source_path)
        parity_key = (source_key, bridge_id)
        if not bridge_id:
            errors.append(f"{label}.source_bridge_id 不能为空")
        elif bridge_id not in bridge_ids:
            errors.append(f"{label}.source_bridge_id 不在原文桥段库存中: {bridge_id}")
        elif parity_key in parity_keys:
            errors.append(f"{label}.source_bridge_id 在同一来源中重复: {bridge_id}")
        else:
            parity_keys.add(parity_key)
        for field in (
            "source_bridge_name",
            "source_scene_granularity",
            "plot_granularity_parity_judgment",
            "emotion_parity_judgment",
            "adaptation_reason",
            "missing_or_weakened_risk",
            "manual_judgment",
        ):
            if not nonempty_text(entry.get(field)):
                errors.append(f"{label}.{field} 不能为空")
        if not nonempty_list(entry.get("source_required_sequence")):
            errors.append(f"{label}.source_required_sequence 必须逐拍列出原文实际顺序")
        if not nonempty_list(entry.get("source_must_keep_actions")):
            errors.append(f"{label}.source_must_keep_actions 必须列出原文实际必保动作/权力变化")
        if source_key not in source_texts:
            errors.append(f"{label}.source_path 必须绑定选中的原文")
            source_text = ""
        else:
            source_text = source_texts[source_key]
            if entry.get("source_sha256") != sha256(source_path):
                errors.append(f"{label}.source_sha256 与原文不一致")
        source_plot_beats = validate_plot_beats(
            entry.get("source_plot_beats"),
            f"{label} 原文情节拍",
            errors,
            evidence_text=source_text,
        )
        target_plot_beats = validate_plot_beats(
            entry.get("target_plot_beats"),
            f"{label} 目标情节拍",
            errors,
            evidence_text=outline_text,
        )
        validate_plot_beat_mapping(
            entry.get("plot_beat_mapping"),
            source_plot_beats,
            target_plot_beats,
            label,
            errors,
        )
        validate_target_plot_adaptation(
            source_plot_beats,
            target_plot_beats,
            label,
            errors,
        )
        inventory_entry = inventory_by_key.get(parity_key)
        if inventory_entry is not None:
            if entry.get("source_plot_beats") != inventory_entry.get("source_plot_beats"):
                errors.append(f"{label}.source_plot_beats 必须与原文桥段库存逐拍完全一致")
        required_sequence = entry.get("source_required_sequence")
        if isinstance(required_sequence, list) and source_plot_beats:
            if len(required_sequence) != len(source_plot_beats):
                errors.append(
                    f"{label}.source_required_sequence 必须逐项覆盖全部原文情节拍"
                )
        source_role = str(source_metadata.get(source_key, {}).get("role") or "")
        emotion_policy = str(
            entry.get("emotion_transfer_policy") or "primary_full_emotion"
        ).strip()
        plot_only_auxiliary = (
            source_role == "auxiliary" and emotion_policy == "plot_mechanism_only"
        )
        if plot_only_auxiliary:
            if entry.get("source_emotion_sequence") not in ([], None):
                errors.append(f"{label} 辅助桥段为 plot_mechanism_only 时不得混入辅助书情绪拍")
            if entry.get("target_emotion_sequence") not in ([], None):
                errors.append(f"{label} 辅助桥段为 plot_mechanism_only 时不得额外派生目标情绪拍")
            for field in (
                "source_reversal_beat",
                "target_reversal_beat",
                "source_peak_beat",
                "target_peak_beat",
            ):
                if entry.get(field) != 0:
                    errors.append(f"{label}.{field} 在 plot_mechanism_only 模式下必须为 0")
            if entry.get("reader_experience_parity") is not None:
                errors.append(f"{label}.reader_experience_parity 在 plot_mechanism_only 模式下必须为 null")
        else:
            if source_role == "primary" and emotion_policy != "primary_full_emotion":
                errors.append(f"{label} 主体桥段不得使用 plot_mechanism_only 规避情绪全集")
            source_beats = validate_emotion_sequence(
                entry.get("source_emotion_sequence"),
                f"{label} 原文情绪流程",
                errors,
                evidence_text=source_text,
                strong_emotion_required=strong_emotion_required,
            )
            target_beats = validate_emotion_sequence(
                entry.get("target_emotion_sequence"),
                f"{label} 目标情绪流程",
                errors,
                evidence_text=outline_text,
                strong_emotion_required=strong_emotion_required,
            )
            validate_bridge_emotion_membership(
                source_path,
                bridge_id,
                source_beats,
                target_beats,
                label,
                errors,
            )
            validate_turn_and_peak_alignment(
                entry,
                source_beats,
                target_beats,
                label,
                errors,
                strong_emotion_required=strong_emotion_required,
            )
            if entry.get("reader_experience_parity") is not True:
                errors.append(f"{label}.reader_experience_parity 必须由当前模型人工确认为 true")
        target_sections = [str(item).strip() for item in entry.get("target_outline_sections") or []]
        if not target_sections:
            errors.append(f"{label}.target_outline_sections 不能为空")
        for section_id in target_sections:
            if section_id not in section_ids:
                errors.append(f"{label}.target_outline_sections 引用了不存在的小节: {section_id}")
        evidence = entry.get("target_outline_evidence")
        if not nonempty_list(evidence, minimum=2):
            errors.append(f"{label}.target_outline_evidence 至少引用两条当前细纲原句")
        else:
            for quote in evidence:
                if str(quote).strip() not in outline_text:
                    errors.append(f"{label}.target_outline_evidence 不在当前细纲中: {quote!r}")
        status = str(entry.get("parity_status") or "").strip()
        if status not in valid_status:
            errors.append(
                f"{label}.parity_status 必须是 matched/adapted；missing/weakened/merged_unclear 一律不得写正文"
            )
    inventory_keys = {
        (
            str(Path(str(entry.get("source_path") or "")).expanduser().resolve()),
            str(entry.get("bridge_id") or "").strip(),
        )
        for entry in inventory or []
        if isinstance(entry, dict) and str(entry.get("bridge_id") or "").strip()
    }
    missing = sorted(inventory_keys - parity_keys)
    if missing:
        errors.append(
            "原文桥段未完成细纲对齐: "
            + ", ".join(f"{Path(source).name}:{bridge_id}" for source, bridge_id in missing)
        )


def validate_subflow_granularity_coverage(
    value: Any,
    source_metadata: dict[str, dict[str, Any]],
    source_texts: dict[str, str],
    section_ids: list[str],
    outline_text: str,
    errors: list[str],
) -> None:
    primary_items = [
        (path, metadata)
        for path, metadata in source_metadata.items()
        if metadata.get("role") == "primary"
    ]
    if len(primary_items) != 1:
        errors.append("主体原文必须且只能有一本，才能验证全部 SF 颗粒度")
        return
    source_key, metadata = primary_items[0]
    catalog_binding = metadata.get("subflow_catalog")
    catalog_path = validate_binding(catalog_binding, "主体原文子流程索引", errors)
    if catalog_path is None:
        return
    try:
        records = subflow_records_from_catalog(catalog_path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    records_by_id = {
        str(record.get("subflow_id") or "").strip(): record for record in records
    }
    actual_ids = list(records_by_id)
    if metadata.get("available_subflow_ids") != actual_ids:
        errors.append("主体来源 available_subflow_ids 与子流程索引不一致")
    if metadata.get("required_subflow_ids") != actual_ids:
        errors.append("主体来源 required_subflow_ids 必须覆盖子流程索引全部 SF")
    if not isinstance(value, list) or not value:
        errors.append("source_subflow_granularity_coverage 必须覆盖主体原文全部 SF")
        return

    coverage_by_id: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(value, start=1):
        label = f"主体 SF 颗粒度覆盖[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} 必须是对象")
            continue
        subflow_id = str(entry.get("subflow_id") or "").strip()
        if not subflow_id:
            errors.append(f"{label}.subflow_id 不能为空")
            continue
        if subflow_id in coverage_by_id:
            errors.append(f"{label}.subflow_id 重复: {subflow_id}")
            continue
        coverage_by_id[subflow_id] = entry
        record = records_by_id.get(subflow_id)
        if record is None:
            errors.append(f"{label}.subflow_id 不在主体子流程索引中: {subflow_id}")
            continue
        if str(Path(str(entry.get("source_path") or "")).expanduser().resolve()) != source_key:
            errors.append(f"{label}.source_path 必须绑定主体原文")
        if entry.get("source_sha256") != sha256(Path(source_key)):
            errors.append(f"{label}.source_sha256 与主体原文不一致")
        for field in ("parent_bridge_id", "source_range"):
            if entry.get(field) != record.get(field):
                errors.append(f"{label}.{field} 与子流程索引不一致")
        source_style = record.get("source_style_granularity")
        if entry.get("source_style_granularity") != source_style:
            errors.append(f"{label}.source_style_granularity 必须原样绑定子流程索引")
        if not isinstance(source_style, dict):
            errors.append(f"{label} 子流程索引缺少 source_style_granularity")
            source_style = {}
        source_text = source_texts.get(source_key, "")
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            item = source_style.get(field)
            if not isinstance(item, dict):
                errors.append(f"{label} 缺少主体颗粒字段: {field}")
                continue
            if not nonempty_text(item.get("analysis")):
                errors.append(f"{label}.{field}.analysis 不能为空")
            evidence = item.get("source_evidence")
            if not nonempty_list(evidence, minimum=2):
                errors.append(f"{label}.{field}.source_evidence 至少两条")
            else:
                for quote in evidence:
                    if str(quote).strip() not in source_text:
                        errors.append(f"{label}.{field} 原文证据不在主体原文中: {quote!r}")

        target_sections = [
            str(item).strip()
            for item in entry.get("target_outline_sections") or []
            if str(item).strip()
        ]
        if not target_sections:
            errors.append(f"{label}.target_outline_sections 不能为空")
        for section_id in target_sections:
            if section_id not in section_ids:
                errors.append(f"{label} 引用了不存在的小节: {section_id}")
        transferred = entry.get("transferred_style_fields")
        if not isinstance(transferred, dict):
            errors.append(f"{label}.transferred_style_fields 必须逐项覆盖六类颗粒")
            transferred = {}
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            transfer = transferred.get(field)
            if not isinstance(transfer, dict):
                errors.append(f"{label} 未迁移颗粒字段: {field}")
                continue
            target_evidence = transfer.get("target_outline_evidence")
            if not nonempty_list(target_evidence):
                errors.append(f"{label}.{field}.target_outline_evidence 至少一条细纲原句")
            else:
                for quote in target_evidence:
                    if str(quote).strip() not in outline_text:
                        errors.append(f"{label}.{field} 目标证据不在细纲中: {quote!r}")
            if not nonempty_text(transfer.get("transfer_method")):
                errors.append(f"{label}.{field}.transfer_method 不能为空")
            if transfer.get("surface_copy_rejected") is not True:
                errors.append(f"{label}.{field}.surface_copy_rejected 必须为 true")
        if entry.get("coverage_status") not in {"matched", "adapted"}:
            errors.append(f"{label}.coverage_status 必须是 matched/adapted")
        for field in ("adaptation_boundary", "manual_judgment"):
            if not nonempty_text(entry.get(field)):
                errors.append(f"{label}.{field} 不能为空")

    missing = [subflow_id for subflow_id in actual_ids if subflow_id not in coverage_by_id]
    if missing:
        errors.append("主体原文 SF 颗粒度未覆盖: " + ", ".join(missing))


def validate_granularity_transfer_contract(
    value: Any,
    source_paths: set[str],
    source_texts: dict[str, str],
    section_ids: list[str],
    outline_text: str,
    errors: list[str],
) -> None:
    """Validate source granularity transfer without requiring source plot identity."""
    if not isinstance(value, list) or not value:
        errors.append("granularity_only 模式必须填写 granularity_transfer_contract")
        return

    covered_sections: set[str] = set()
    for index, entry in enumerate(value, start=1):
        label = f"颗粒度迁移契约[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} 必须是对象")
            continue
        source_path = Path(str(entry.get("source_path") or "")).expanduser().resolve()
        source_key = str(source_path)
        if source_key not in source_paths:
            errors.append(f"{label}.source_path 必须绑定选中的原文")
        elif entry.get("source_sha256") != sha256(source_path):
            errors.append(f"{label}.source_sha256 与原文不一致")
        for field in (
            "source_scene",
            "source_granularity",
            "target_scene",
            "transferred_beat_density",
            "transferred_information_delay",
            "transferred_control_right_changes",
            "manual_judgment",
        ):
            if not nonempty_text(entry.get(field)):
                errors.append(f"{label}.{field} 不能为空")
        if not nonempty_list(entry.get("rejected_surface_elements"), minimum=3):
            errors.append(f"{label}.rejected_surface_elements 至少三项")
        target_sections = [
            str(item).strip()
            for item in entry.get("target_outline_sections") or []
            if str(item).strip()
        ]
        if not target_sections:
            errors.append(f"{label}.target_outline_sections 不能为空")
        for section_id in target_sections:
            if section_id not in section_ids:
                errors.append(f"{label} 引用了不存在的小节: {section_id}")
            else:
                covered_sections.add(section_id)
        evidence = entry.get("source_evidence")
        if not nonempty_list(evidence):
            errors.append(f"{label}.source_evidence 至少引用一条原文证据")
        else:
            source_text = source_texts.get(source_key, "")
            for quote in evidence:
                if str(quote).strip() not in source_text:
                    errors.append(f"{label}.source_evidence 不在原文中: {quote!r}")
        target_evidence = entry.get("target_outline_evidence")
        if not nonempty_list(target_evidence):
            errors.append(f"{label}.target_outline_evidence 至少引用一条细纲原句")
        else:
            for quote in target_evidence:
                if str(quote).strip() not in outline_text:
                    errors.append(f"{label}.target_outline_evidence 不在细纲中: {quote!r}")

    missing = sorted(set(section_ids) - covered_sections)
    if missing:
        errors.append("颗粒度迁移契约未覆盖细纲小节: " + ", ".join(missing))


def validate_receipt(receipt_path: Path, outline_path: Path) -> list[str]:
    errors: list[str] = []
    if not receipt_path.is_file():
        return [f"细纲表演验收回执不存在: {receipt_path}"]
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"细纲表演验收回执不是有效 JSON: {exc}"]
    if not isinstance(data, dict):
        return ["细纲表演验收回执必须是 JSON 对象"]

    resolved_outline = outline_path.resolve()
    if not resolved_outline.is_file():
        return [f"细纲不存在: {resolved_outline}"]
    bound_outline = validate_binding(data.get("outline"), "细纲绑定", errors)
    if bound_outline is not None and bound_outline != resolved_outline:
        errors.append("细纲绑定路径与当前 --outline 不一致")

    sources = data.get("selected_source_originals")
    source_paths: set[str] = set()
    source_texts: dict[str, str] = {}
    source_metadata: dict[str, dict[str, Any]] = {}
    if not isinstance(sources, list) or not sources:
        errors.append("selected_source_originals 必须至少包含一本选中原文")
    else:
        for index, source in enumerate(sources, start=1):
            source_path = validate_binding(source, f"选中原文[{index}]", errors)
            if source_path is not None:
                source_key = str(source_path)
                source_paths.add(source_key)
                source_texts[source_key] = read_text(source_path)
                source_metadata[source_key] = source
                expected_role = "primary" if index == 1 else "auxiliary"
                if source.get("role") != expected_role:
                    errors.append(
                        f"选中原文[{index}].role 必须为 {expected_role}"
                    )
                catalog_path = validate_binding(
                    source.get("bridge_catalog"),
                    f"选中原文[{index}]桥段施工卡",
                    errors,
                )
                if catalog_path is not None:
                    actual_ids = bridge_ids_from_catalog(catalog_path)
                    if source.get("available_bridge_ids") != actual_ids:
                        errors.append(
                            f"选中原文[{index}].available_bridge_ids 与桥段施工卡不一致"
                        )
                if expected_role == "primary":
                    subflow_path = validate_binding(
                        source.get("subflow_catalog"),
                        "主体原文子流程索引",
                        errors,
                    )
                    if subflow_path is not None:
                        try:
                            actual_subflow_ids = [
                                str(record.get("subflow_id") or "").strip()
                                for record in subflow_records_from_catalog(subflow_path)
                            ]
                        except ValueError as exc:
                            errors.append(str(exc))
                            actual_subflow_ids = []
                        if source.get("available_subflow_ids") != actual_subflow_ids:
                            errors.append(
                                "主体来源 available_subflow_ids 与子流程索引不一致"
                            )
                        if source.get("required_subflow_ids") != actual_subflow_ids:
                            errors.append(
                                "主体来源 required_subflow_ids 必须覆盖子流程索引全部 SF"
                            )
                source_mode = str(data.get("source_mode") or "full_bridge").strip()
                if expected_role == "primary" and source_mode == "full_bridge":
                    if source.get("required_bridge_ids") != source.get(
                        "available_bridge_ids"
                    ):
                        errors.append(
                            "主体来源 required_bridge_ids 必须覆盖桥段施工卡全部 BID"
                        )
                elif (
                    expected_role == "auxiliary"
                    and source_mode == "full_bridge"
                    and not nonempty_list(source.get("selected_bridge_ids"))
                ):
                    available = ", ".join(source.get("available_bridge_ids") or [])
                    errors.append(
                        "辅助来源必须人工选择至少一个 selected_bridge_ids: "
                        f"{source_path}；可选 BID: {available or '无'}"
                    )

    source_mode = str(data.get("source_mode") or "full_bridge").strip()
    source_plot_ledgers = (
        validate_source_plot_ledgers(source_metadata, source_texts, errors)
        if source_mode == "full_bridge"
        else {}
    )

    global_review = data.get("global_review")
    if not isinstance(global_review, dict):
        errors.append("global_review 必须是对象")
    else:
        if global_review.get("full_source_mechanisms_reviewed") is not True:
            errors.append("必须人工确认已完整阅读选中原文的表演机制")
        if global_review.get("dual_track_function_and_scene_granularity_reviewed") is not True:
            errors.append("必须人工确认已同时核对拆书功能机制和原文场面颗粒度，不能只做功能映射")
        source_mode = str(data.get("source_mode") or "full_bridge").strip()
        if source_mode == "full_bridge":
            if global_review.get("source_bridge_flow_inventory_completed") is not True:
                errors.append("必须先完成人工原文 BID/关键子桥段流程全集，不得边写正文边补")
            if global_review.get("source_plot_beat_inventory_completed") is not True:
                errors.append("必须逐句盘清每个 BID 内全部有效情节拍，不得按预设数量抽样")
            if global_review.get("plot_and_emotion_ledgers_independently_built") is not True:
                errors.append("必须人工确认全文情节微拍总账与全文情绪总账已分轨独立建立")
            if global_review.get("outline_bridge_flow_parity_reviewed_before_draft") is not True:
                errors.append("必须在正文前完成人工逐桥流程对齐验收，不能写完正文后才发现流程错位")
            if global_review.get("plot_beat_mapping_reviewed_before_draft") is not True:
                errors.append("必须在正文前人工复核原文与目标全部情节拍的一对一映射")
        if global_review.get("relationship_legibility_reviewed_before_draft") is not True:
            errors.append("必须在正文前确认陌生读者无需职业知识即可看懂人物关系与伤害")
        if global_review.get("professional_shell_translation_reviewed_before_draft") is not True:
            errors.append("必须在正文前完成职业外壳白话翻译，禁止术语承担情绪")
        if global_review.get("source_emotion_flow_parity_reviewed_before_draft") is not True:
            errors.append("必须在正文前逐节核对原文情绪流程、反刀时机和烈度")
        if global_review.get("complete_source_emotion_beat_inventory_reviewed") is not True:
            errors.append("必须盘清原文全部实际情绪拍及同类重复次数，禁止用预设角色表代替完整库存")
        if global_review.get("source_subflow_granularity_coverage_reviewed") is not True:
            errors.append("必须在正文前逐 SF 核对主体原文全部六类颗粒度")
        if str(data.get("source_mode") or "full_bridge") == "granularity_only":
            if global_review.get("granularity_transfer_contract_reviewed") is not True:
                errors.append("granularity_only 模式必须人工确认颗粒度迁移契约")
        if not nonempty_text(global_review.get("mechanism_transfer_boundary")):
            errors.append("必须写明机制迁移边界，禁止复制原人物、原职业、原句和完整桥壳")
        if global_review.get("global_storyboard_or_process_list") is not False:
            errors.append("必须人工确认细纲不是流程清单或证据排队表")
        if not nonempty_text(global_review.get("manual_judgment")):
            errors.append("global_review.manual_judgment 不能为空")

    section_ids = outline_sections(read_text(resolved_outline))
    if not section_ids:
        errors.append("细纲中未找到 `## 1.` 形式的小节")
        return errors
    outline_text = read_text(resolved_outline)
    if source_mode not in {"full_bridge", "granularity_only"}:
        errors.append(f"source_mode 无效: {source_mode!r}")
    if source_mode == "granularity_only":
        validate_granularity_transfer_contract(
            data.get("granularity_transfer_contract"),
            source_paths,
            source_texts,
            section_ids,
            outline_text,
            errors,
        )
        bridge_ids: set[str] = set()
    else:
        bridge_ids = validate_bridge_inventory(
            data.get("source_bridge_flow_inventory"),
            source_metadata,
            source_plot_ledgers,
            errors,
        )
    strong_emotion_required = bool(
        isinstance(global_review, dict)
        and global_review.get("strong_emotion_required") is True
    )
    if source_mode == "full_bridge":
        primary_source_key = next(
            (
                key
                for key, metadata in source_metadata.items()
                if metadata.get("role") == "primary"
            ),
            "",
        )
        validate_outside_bridge_plot_parity(
            data.get("outside_bridge_plot_parity"),
            [
                beat
                for beat in source_plot_ledgers.get(primary_source_key, [])
                if not beat.get("bid_ids")
            ],
            outline_text,
            section_ids,
            errors,
        )
        validate_bridge_parity(
            data.get("outline_bridge_flow_parity"),
            data.get("source_bridge_flow_inventory"),
            bridge_ids,
            source_texts,
            source_metadata,
            section_ids,
            outline_text,
            errors,
            strong_emotion_required=strong_emotion_required,
        )
    validate_subflow_granularity_coverage(
        data.get("source_subflow_granularity_coverage"),
        source_metadata,
        source_texts,
        section_ids,
        outline_text,
        errors,
    )
    section_entries = data.get("sections")
    if not isinstance(section_entries, list):
        errors.append("sections 必须是列表")
        return errors
    by_id = {
        str(entry.get("section_id") or ""): entry
        for entry in section_entries
        if isinstance(entry, dict)
    }
    missing = [section_id for section_id in section_ids if section_id not in by_id]
    extra = [section_id for section_id in by_id if section_id not in section_ids]
    if missing:
        errors.append(f"细纲小节缺少验收: {', '.join(missing)}")
    if extra:
        errors.append(f"回执存在细纲中没有的小节: {', '.join(extra)}")

    repeated_scene_signatures: dict[tuple[str, ...], list[str]] = {}
    repeated_emotion_signatures: dict[tuple[str, ...], list[str]] = {}
    repeated_judgments: dict[str, list[str]] = {}
    for section_id in section_ids:
        entry = by_id.get(section_id)
        if not isinstance(entry, dict):
            continue
        label = f"第 {section_id} 节"
        if entry.get("verdict") != "passed":
            errors.append(f"{label} verdict 必须为 passed")
        for field in ("irreversible_action", "controlling_object", "manual_judgment"):
            if not nonempty_text(entry.get(field)):
                errors.append(f"{label} {field} 不能为空")
        validate_source_function_mechanism(
            entry.get("source_function_mechanism"), label, errors
        )
        validate_original_scene_granularity(
            entry.get("original_scene_granularity"), source_paths, label, errors
        )
        validate_source_mechanism(entry.get("source_mechanism"), source_paths, label, errors)
        validate_information_delay(entry.get("information_delay"), label, errors)
        if not nonempty_list(entry.get("character_missteps"), minimum=2):
            errors.append(f"{label} character_missteps 至少填写两条人物偏手/错答")
        validate_exchange(entry.get("interaction_exchange"), label, errors)
        errors.extend(validate_scene_units(entry.get("scene_units"), label, outline_text, section_id))
        validate_conflict(entry.get("conflict_carrier"), label, errors)
        validate_relationship_legibility(
            entry.get("relationship_legibility"), label, errors
        )
        validate_emotion_intensity(
            entry.get("emotion_intensity"),
            label,
            errors,
            strong_emotion_required=strong_emotion_required,
        )
        validate_professional_shell_translation(
            entry.get("professional_shell_translation"), label, errors
        )
        validate_source_emotion_parity(
            entry.get("source_emotion_parity"),
            source_texts,
            outline_text,
            label,
            errors,
            strong_emotion_required=strong_emotion_required,
        )
        if not nonempty_list(entry.get("forbidden_items"), minimum=2):
            errors.append(f"{label} forbidden_items 至少填写两条禁写项")
        evidence = entry.get("outline_evidence")
        if not nonempty_list(evidence, minimum=2):
            errors.append(f"{label} outline_evidence 至少引用两条当前细纲原句")
        else:
            for quote in evidence:
                if str(quote).strip() not in outline_text:
                    errors.append(f"{label} outline_evidence 不在当前细纲中: {quote!r}")
        granularity = entry.get("original_scene_granularity")
        if isinstance(granularity, dict):
            signature = tuple(
                str(granularity.get(field) or "").strip()
                for field in (
                    "source_scene",
                    "action_sequence",
                    "body_object_space_control",
                    "dialogue_forces_action",
                    "scene_end_residue",
                )
            )
            repeated_scene_signatures.setdefault(signature, []).append(section_id)
        judgment = str(entry.get("manual_judgment") or "").strip()
        repeated_judgments.setdefault(judgment, []).append(section_id)
        emotion_parity = entry.get("source_emotion_parity")
        if isinstance(emotion_parity, dict):
            source_sequence = emotion_parity.get("source_emotion_sequence")
            if isinstance(source_sequence, list):
                emotion_signature = tuple(
                    "|".join(
                        (
                            str(beat.get("role") or "").strip(),
                            str(beat.get("trigger") or "").strip(),
                            str(beat.get("evidence") or "").strip(),
                        )
                    )
                    for beat in source_sequence
                    if isinstance(beat, dict)
                )
                repeated_emotion_signatures.setdefault(
                    emotion_signature, []
                ).append(section_id)

    for signature, repeated_sections in repeated_scene_signatures.items():
        if all(signature) and len(repeated_sections) >= 3:
            errors.append(
                "原文场面颗粒度连续复用泛化模板，必须逐节绑定不同的真实场面: "
                + ", ".join(repeated_sections)
            )
    for judgment, repeated_sections in repeated_judgments.items():
        if judgment and len(repeated_sections) >= 3:
            errors.append(
                "细纲人工判断连续复用同一句，不能用模板批量判过: "
                + ", ".join(repeated_sections)
            )
    for signature, repeated_sections in repeated_emotion_signatures.items():
        if signature and len(repeated_sections) >= 3:
            errors.append(
                "原文情绪流程连续复用同一套模板，必须逐节绑定真实情绪拍: "
                + ", ".join(repeated_sections)
            )

    if data.get("reviewed_by_current_model") is not True:
        errors.append("reviewed_by_current_model 必须为 true")
    if data.get("gate_status") != "passed":
        errors.append(f"gate_status 必须为 passed，当前为 {data.get('gate_status')!r}")
    if data.get("blocking_failures"):
        errors.append("blocking_failures 非空时不得放行")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a source-bound scene-performance outline contract."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--source-original", action="append", required=True)
    init.add_argument(
        "--source-mode",
        choices=("full_bridge", "granularity_only"),
        default="full_bridge",
    )
    init.add_argument("--receipt", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--outline", required=True)
    args = parser.parse_args()

    if args.command == "init":
        try:
            receipt = create_receipt(
                args.project,
                Path(args.outline),
                [Path(value) for value in args.source_original],
                source_mode=args.source_mode,
            )
        except (FileNotFoundError, ValueError) as exc:
            print("outline_performance_contract: blocked")
            print(f"- {exc}")
            return 2
        output = Path(args.receipt)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"outline_performance_contract: initialized ({output})")
        return 0

    errors = validate_receipt(Path(args.receipt), Path(args.outline))
    if errors:
        print("outline_performance_contract: blocked；不得生成或修改正文")
        for error in errors:
            print(f"- {error}")
        return 2
    print("outline_performance_contract: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
