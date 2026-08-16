#!/usr/bin/env python3
"""Export/apply section-level manual review sidecars for outline performance receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_lifecycle import consume_sidecar, refresh_sidecar_receipt_sha


TEMPLATE_SCHEMA = "story-short-write.outline-section-review-template.v1"
SECTION_CONTEXT_FIELDS = (
    "section_title",
    "main_event",
    "sub_events",
    "emotion",
    "reader_gain",
    "hook",
    "foreshadow_objects",
    "motion_state",
    "dialogue_density",
    "target_word_count",
    "scene_unit",
)
SECTION_REFERENCE_FIELDS = (
    "related_bridge_ids",
    "related_subflow_ids",
    "bridge_context",
    "subflow_context",
    "project_mechanism_boundary",
)
SECTION_MANUAL_FIELDS = (
    "verdict",
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
    "scene_units",
    "manual_judgment",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _subflow_catalog_path(source_path: str) -> Path:
    source = Path(source_path).resolve()
    return source.parent.parent / "写作资产" / "子流程索引.jsonl"


def _load_subflow_catalog(source_path: str) -> dict[str, dict[str, Any]]:
    path = _subflow_catalog_path(source_path)
    if not path.is_file():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        subflow_id = str(item.get("subflow_id") or "").strip()
        if subflow_id:
            records[subflow_id] = item
    return records


def _extract_named_entities(texts: list[str]) -> list[str]:
    seen: list[str] = []
    for text in texts:
        for token in re.findall(r"[\u4e00-\u9fff]{2,4}", text):
            if token in {"我们", "你们", "他们", "自己"}:
                continue
            if token not in seen:
                seen.append(token)
    return seen[:5]


def _generic_role_summary(named_entities: list[str]) -> str:
    if named_entities:
        return " / ".join(named_entities)
    return ""


def _has_explicit_outline_conflict(outline_quotes: list[str]) -> bool:
    return len(outline_quotes) >= 2


def _same_text(left: Any, right: Any) -> bool:
    return str(left or "").strip() != "" and str(left or "").strip() == str(right or "").strip()


def _derive_controlling_object(
    outline_quotes: list[str],
    bridge_outline_quotes: list[str],
    foreshadow_objects: str,
    fallback: str,
) -> str:
    if foreshadow_objects.strip():
        return foreshadow_objects.strip()
    for quote in outline_quotes + bridge_outline_quotes:
        cleaned = str(quote).strip()
        if cleaned:
            return cleaned
    return fallback


def _parse_outline_sections(outline_path: Path | None) -> dict[str, dict[str, Any]]:
    if outline_path is None:
        return {}
    if not outline_path.is_file():
        raise FileNotFoundError(f"小节大纲不存在，无法导出节级上下文: {outline_path}")
    sections: dict[str, dict[str, Any]] = {}
    current_id: str | None = None
    current_payload: dict[str, Any] | None = None
    field_map = {
        "主事件": "main_event",
        "子事件": "sub_events",
        "情绪": "emotion",
        "读者新获知什么": "reader_gain",
        "钩子": "hook",
        "伏笔/物件": "foreshadow_objects",
        "动静": "motion_state",
        "对话密度": "dialogue_density",
        "目标字数": "target_word_count",
        "场面单元": "scene_unit",
    }
    pattern = re.compile(r"^##\s+(\d+)\.\s*(.*?)\s*$")
    for raw_line in outline_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        match = pattern.match(line)
        if match:
            current_id = match.group(1)
            current_payload = {
                "section_title": match.group(2),
                "main_event": "",
                "sub_events": "",
                "emotion": "",
                "reader_gain": "",
                "hook": "",
                "foreshadow_objects": "",
                "motion_state": "",
                "dialogue_density": "",
                "target_word_count": "",
                "scene_unit": "",
            }
            sections[current_id] = current_payload
            continue
        if not current_id or current_payload is None or not line.startswith("- "):
            continue
        content = line[2:].strip()
        if "：" not in content:
            if not current_payload["section_title"]:
                current_payload["section_title"] = content[:30]
            if not current_payload["main_event"]:
                current_payload["main_event"] = content
            else:
                existing = current_payload["sub_events"].strip()
                current_payload["sub_events"] = (
                    f"{existing} / {content}" if existing else content
                )
            continue
        key, value = content.split("：", 1)
        mapped = field_map.get(key.strip())
        if mapped:
            current_payload[mapped] = value.strip()
    return sections


def _build_reference_context(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog_cache: dict[str, dict[str, Any]] = {}
    project_boundary = str(
        ((receipt.get("global_review") or {}).get("mechanism_transfer_boundary") or "")
    ).strip()
    bridge_by_section: dict[str, list[dict[str, Any]]] = {}
    for bridge in receipt.get("outline_bridge_flow_parity") or []:
        if not isinstance(bridge, dict):
            continue
        for section_id in bridge.get("target_outline_sections") or []:
            sid = str(section_id).strip()
            if sid:
                bridge_by_section.setdefault(sid, []).append(bridge)

    subflow_by_section: dict[str, list[dict[str, Any]]] = {}
    for subflow in receipt.get("source_subflow_granularity_coverage") or []:
        if not isinstance(subflow, dict):
            continue
        target_sections = [
            str(section_id).strip()
            for section_id in subflow.get("target_outline_sections") or []
            if str(section_id).strip()
        ]
        if not target_sections:
            bridge_sections = [
                str(section_id).strip()
                for section_id in next(
                    (
                        bridge.get("target_outline_sections") or []
                        for bridge in receipt.get("outline_bridge_flow_parity") or []
                        if isinstance(bridge, dict)
                        and str(bridge.get("source_bridge_id") or "").strip()
                        == str(subflow.get("parent_bridge_id") or "").strip()
                    ),
                    [],
                )
                if str(section_id).strip()
            ]
            target_sections = bridge_sections
        for sid in target_sections:
            subflow_by_section.setdefault(sid, []).append(subflow)

    result: dict[str, dict[str, Any]] = {}
    section_ids = set(bridge_by_section) | set(subflow_by_section)
    for section_id in section_ids:
        bridges = bridge_by_section.get(section_id, [])
        subflows = subflow_by_section.get(section_id, [])
        result[section_id] = {
            "project_mechanism_boundary": project_boundary,
            "related_bridge_ids": [
                str(item.get("source_bridge_id") or "").strip()
                for item in bridges
                if str(item.get("source_bridge_id") or "").strip()
            ],
            "related_subflow_ids": [
                str(item.get("subflow_id") or "").strip()
                for item in subflows
                if str(item.get("subflow_id") or "").strip()
            ],
            "bridge_context": [
                {
                    "source_bridge_id": str(item.get("source_bridge_id") or "").strip(),
                    "source_bridge_name": str(item.get("source_bridge_name") or "").strip(),
                    "source_path": deepcopy(item.get("source_path") or ""),
                    "source_sha256": deepcopy(item.get("source_sha256") or ""),
                    "source_scene_granularity": deepcopy(item.get("source_scene_granularity") or ""),
                    "source_required_sequence": deepcopy(item.get("source_required_sequence") or []),
                    "source_must_keep_actions": deepcopy(item.get("source_must_keep_actions") or []),
                    "source_plot_beats": deepcopy(item.get("source_plot_beats") or []),
                    "source_emotion_sequence": deepcopy(item.get("source_emotion_sequence") or []),
                    "target_outline_evidence": deepcopy(item.get("target_outline_evidence") or []),
                    "manual_judgment": deepcopy(item.get("manual_judgment") or ""),
                }
                for item in bridges
            ],
            "subflow_context": [
                {
                    "subflow_id": str(item.get("subflow_id") or "").strip(),
                    "parent_bridge_id": str(item.get("parent_bridge_id") or "").strip(),
                    "source_path": deepcopy(item.get("source_path") or ""),
                    "source_range": deepcopy(item.get("source_range") or ""),
                    "source_excerpt": deepcopy(
                        (
                            catalog_cache.setdefault(
                                str(item.get("source_path") or "").strip(),
                                _load_subflow_catalog(str(item.get("source_path") or "").strip()),
                            ).get(str(item.get("subflow_id") or "").strip(), {})
                        ).get("source_excerpt", "")
                    ),
                    "source_style_granularity": deepcopy(item.get("source_style_granularity") or {}),
                    "target_outline_sections": deepcopy(item.get("target_outline_sections") or []),
                    "manual_judgment": deepcopy(item.get("manual_judgment") or ""),
                }
                for item in subflows
            ],
        }
    return result


def _compact_bridge_context_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_bridge_id": str(item.get("source_bridge_id") or "").strip(),
        "source_bridge_name": str(item.get("source_bridge_name") or "").strip(),
        "source_path": deepcopy(item.get("source_path") or ""),
        "source_sha256": deepcopy(item.get("source_sha256") or ""),
        "source_scene_granularity": deepcopy(item.get("source_scene_granularity") or ""),
        "source_required_sequence": deepcopy(item.get("source_required_sequence") or []),
        "source_must_keep_actions": deepcopy(item.get("source_must_keep_actions") or []),
        "source_plot_beats": [
            {
                "beat_id": deepcopy(beat.get("beat_id")),
                "action": deepcopy(beat.get("action")),
                "evidence": deepcopy(beat.get("evidence")),
            }
            for beat in item.get("source_plot_beats") or []
            if isinstance(beat, dict)
        ],
        "source_emotion_sequence": deepcopy(item.get("source_emotion_sequence") or []),
        "target_outline_evidence": deepcopy(item.get("target_outline_evidence") or []),
        "manual_judgment": deepcopy(item.get("manual_judgment") or ""),
    }


def _compact_subflow_context_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "subflow_id": str(item.get("subflow_id") or "").strip(),
        "parent_bridge_id": str(item.get("parent_bridge_id") or "").strip(),
        "source_path": deepcopy(item.get("source_path") or ""),
        "source_range": deepcopy(item.get("source_range") or ""),
        "source_style_granularity": deepcopy(item.get("source_style_granularity") or {}),
        "target_outline_sections": deepcopy(item.get("target_outline_sections") or []),
        "manual_judgment": deepcopy(item.get("manual_judgment") or ""),
    }


def _compact_section_payload(section_payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(section_payload)
    result["bridge_context"] = [
        _compact_bridge_context_item(item)
        for item in result.get("bridge_context") or []
        if isinstance(item, dict)
    ]
    result["subflow_context"] = [
        _compact_subflow_context_item(item)
        for item in result.get("subflow_context") or []
        if isinstance(item, dict)
    ]
    return result


def _prefill_section_manual_fields(section_payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(section_payload)
    bridge_context = result.get("bridge_context") or []
    first_bridge = bridge_context[0] if bridge_context else {}
    subflow_context = result.get("subflow_context") or []
    outline_quotes = [
        quote
        for quote in (
            [result.get("main_event", "").strip()]
            + [item.strip() for item in str(result.get("sub_events", "")).split(" / ") if item.strip()]
        )
        if quote
    ]
    bridge_outline_quotes = [
        str(item).strip()
        for item in first_bridge.get("target_outline_evidence") or []
        if str(item).strip()
    ]
    role_hints = _generic_role_summary(_extract_named_entities(outline_quotes + bridge_outline_quotes))
    if not result.get("outline_evidence"):
        result["outline_evidence"] = deepcopy(outline_quotes[:2] or bridge_outline_quotes[:2])

    source_path = str(first_bridge.get("source_path") or "").strip()
    source_sha = str(first_bridge.get("source_sha256") or "").strip()
    source_scene = str(first_bridge.get("source_scene_granularity") or "").strip()
    project_boundary = str(result.get("project_mechanism_boundary") or "").strip()
    source_required = [str(item).strip() for item in first_bridge.get("source_required_sequence") or [] if str(item).strip()]
    source_keep = [str(item).strip() for item in first_bridge.get("source_must_keep_actions") or [] if str(item).strip()]
    source_plot_beats = first_bridge.get("source_plot_beats") or []
    source_emotion_sequence = first_bridge.get("source_emotion_sequence") or []
    legacy_boundaries = {
        "仅迁移桥骨与风格颗粒，不复制原人物、原职业、原句。",
        "只迁移桥骨、情绪位移和现场颗粒，不复制原人物、原句面和完整桥壳。",
    }

    sf_fields = []
    subflow_excerpt = ""
    for sf in subflow_context:
        if not isinstance(sf, dict):
            continue
        if not subflow_excerpt and str(sf.get("source_excerpt") or "").strip():
            subflow_excerpt = str(sf.get("source_excerpt") or "").strip()
        style = sf.get("source_style_granularity") or {}
        if isinstance(style, dict):
            for field_name, field_payload in style.items():
                if not isinstance(field_payload, dict):
                    continue
                analysis = str(field_payload.get("analysis") or "").strip()
                if analysis:
                    sf_fields.append(f"{sf.get('subflow_id')}-{field_name}: {analysis}")

    source_function = result.get("source_function_mechanism") or {}
    if not source_function.get("asset_path") and source_path:
        source_function["asset_path"] = source_path
    if not source_function.get("function_type") and first_bridge.get("source_bridge_name"):
        source_function["function_type"] = str(first_bridge.get("source_bridge_name") or "").strip()
    if not source_function.get("asset_rule") and source_required:
        source_function["asset_rule"] = " / ".join(source_required[:3])
    if not source_function.get("why_selected_for_this_section") and source_keep:
        source_function["why_selected_for_this_section"] = " / ".join(source_keep[:2])
    result["source_function_mechanism"] = source_function

    original_scene = result.get("original_scene_granularity") or {}
    if not original_scene.get("source_path") and source_path:
        original_scene["source_path"] = source_path
    if not original_scene.get("source_sha256") and source_sha:
        original_scene["source_sha256"] = source_sha
    if not original_scene.get("source_scene") and source_scene:
        original_scene["source_scene"] = source_scene
    if not original_scene.get("action_sequence") and source_required:
        original_scene["action_sequence"] = " / ".join(source_required[:4])
    if not original_scene.get("body_object_space_control") and source_keep:
        original_scene["body_object_space_control"] = " / ".join(source_keep[:3])
    if not original_scene.get("dialogue_forces_action") and bridge_outline_quotes:
        original_scene["dialogue_forces_action"] = " / ".join(bridge_outline_quotes[:2])
    if not original_scene.get("scene_end_residue") and outline_quotes:
        original_scene["scene_end_residue"] = outline_quotes[-1]
    if _same_text(original_scene.get("bystander_or_order_shift"), first_bridge.get("manual_judgment")):
        original_scene["bystander_or_order_shift"] = ""
    result["original_scene_granularity"] = original_scene

    source_mechanism = result.get("source_mechanism") or {}
    if not source_mechanism.get("source_path") and source_path:
        source_mechanism["source_path"] = source_path
    if not source_mechanism.get("source_sha256") and source_sha:
        source_mechanism["source_sha256"] = source_sha
    if not source_mechanism.get("source_scene") and source_scene:
        source_mechanism["source_scene"] = source_scene
    if not source_mechanism.get("transferable_mechanism") and source_keep:
        source_mechanism["transferable_mechanism"] = " / ".join(source_keep[:3])
    if (
        (not source_mechanism.get("adaptation_boundary"))
        or str(source_mechanism.get("adaptation_boundary") or "").strip() in legacy_boundaries
    ) and project_boundary:
        source_mechanism["adaptation_boundary"] = project_boundary
    result["source_mechanism"] = source_mechanism

    if not result.get("irreversible_action") and outline_quotes:
        result["irreversible_action"] = outline_quotes[-1]
    if not result.get("controlling_object"):
        result["controlling_object"] = _derive_controlling_object(
            outline_quotes,
            bridge_outline_quotes,
            str(result.get("foreshadow_objects") or ""),
            str(first_bridge.get("source_bridge_name") or ""),
        )

    info_delay = result.get("information_delay") or {}
    if not info_delay.get("entry_known") and outline_quotes:
        info_delay["entry_known"] = outline_quotes[0]
    if not info_delay.get("leaked_in_scene") and len(outline_quotes) >= 2:
        info_delay["leaked_in_scene"] = outline_quotes[1]
    if not info_delay.get("deferred_to_later") and len(outline_quotes) >= 3:
        info_delay["deferred_to_later"] = outline_quotes[-1]
    result["information_delay"] = info_delay

    interaction = result.get("interaction_exchange") or {}
    if not interaction.get("pressure") and outline_quotes:
        interaction["pressure"] = outline_quotes[0]
    if not interaction.get("forced_response") and len(outline_quotes) >= 2:
        interaction["forced_response"] = outline_quotes[1]
    if not interaction.get("visible_change"):
        interaction["visible_change"] = outline_quotes[-1] if outline_quotes else first_bridge.get("source_bridge_name", "")
    result["interaction_exchange"] = interaction

    conflict = result.get("conflict_carrier") or {}
    if not conflict.get("contested_power"):
        conflict["contested_power"] = first_bridge.get("source_bridge_name", "")
    if not conflict.get("carrier"):
        conflict["carrier"] = result.get("controlling_object") or first_bridge.get("source_bridge_name", "")
    if not conflict.get("consequence") and outline_quotes:
        conflict["consequence"] = outline_quotes[-1]
    result["conflict_carrier"] = conflict

    relationship = result.get("relationship_legibility") or {}
    if not relationship.get("plain_relationship_roles") and role_hints:
        relationship["plain_relationship_roles"] = role_hints
    if not relationship.get("plain_relationship_injury") and outline_quotes:
        relationship["plain_relationship_injury"] = " / ".join(outline_quotes[:2])
    if (
        relationship.get("understandable_without_domain_knowledge") is None
        and _has_explicit_outline_conflict(outline_quotes)
    ):
        relationship["understandable_without_domain_knowledge"] = True
    result["relationship_legibility"] = relationship

    emotion_intensity = result.get("emotion_intensity") or {}
    source_scores = [
        int(item.get("intensity"))
        for item in source_emotion_sequence
        if isinstance(item, dict) and isinstance(item.get("intensity"), (int, float))
    ]
    peak_score = max(source_scores) if source_scores else 7
    if not emotion_intensity.get("score"):
        emotion_intensity["score"] = peak_score
    if not emotion_intensity.get("concrete_humiliation_or_pain") and outline_quotes:
        emotion_intensity["concrete_humiliation_or_pain"] = outline_quotes[-1]
    if not emotion_intensity.get("emotional_turn") and len(outline_quotes) >= 2:
        emotion_intensity["emotional_turn"] = f"{outline_quotes[0]} -> {outline_quotes[-1]}"
    if not emotion_intensity.get("escalation_vs_previous"):
        emotion_intensity["escalation_vs_previous"] = first_bridge.get("source_bridge_name", "")
    result["emotion_intensity"] = emotion_intensity

    shell = result.get("professional_shell_translation") or {}
    if not shell.get("plain_language_conflict") and outline_quotes:
        shell["plain_language_conflict"] = " / ".join(outline_quotes[:2])
    if not shell.get("domain_detail_function") and first_bridge.get("source_bridge_name"):
        shell["domain_detail_function"] = str(first_bridge.get("source_bridge_name") or "").strip()
    if (
        shell.get("conflict_survives_without_jargon") is None
        and _has_explicit_outline_conflict(outline_quotes)
    ):
        shell["conflict_survives_without_jargon"] = True
    if shell.get("relationship_first") is None and role_hints:
        shell["relationship_first"] = True
    result["professional_shell_translation"] = shell

    emotion_parity = result.get("source_emotion_parity") or {}
    plot_evidence = [
        str(item.get("evidence") or "").strip()
        for item in source_plot_beats
        if isinstance(item, dict) and str(item.get("evidence") or "").strip()
    ]
    emotion_evidence = [
        str(item.get("evidence") or "").strip()
        for item in source_emotion_sequence
        if isinstance(item, dict) and str(item.get("evidence") or "").strip()
    ]
    canonical_excerpt = "\n".join(
        (plot_evidence[:2] or emotion_evidence[:2] or ([subflow_excerpt] if subflow_excerpt else []) or [source_scene])
    )
    if canonical_excerpt:
        emotion_parity["source_excerpt"] = canonical_excerpt
    if not emotion_parity.get("source_emotion_sequence") and source_emotion_sequence:
        emotion_parity["source_emotion_sequence"] = deepcopy(source_emotion_sequence)
    if not emotion_parity.get("source_intensity_score"):
        emotion_parity["source_intensity_score"] = peak_score
    if not emotion_parity.get("target_intensity_score"):
        emotion_parity["target_intensity_score"] = peak_score
    result["source_emotion_parity"] = emotion_parity
    result["source_mechanism"] = source_mechanism
    return result


def _normalize_section_filter(section_ids: list[str] | None) -> set[str]:
    if not section_ids:
        return set()
    return {str(item).strip() for item in section_ids if str(item).strip()}


def export_template(
    receipt_path: Path,
    output_path: Path,
    outline_path: Path | None = None,
    section_ids: list[str] | None = None,
    compact_context: bool = False,
) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    sections = receipt.get("sections")
    if not isinstance(sections, list):
        raise ValueError("回执缺少 sections 列表")
    outline_context = _parse_outline_sections(outline_path)
    reference_context = _build_reference_context(receipt)
    selected_section_ids = _normalize_section_filter(section_ids)
    payload = {
        "schema_version": TEMPLATE_SCHEMA,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "sections": [
            (
                _compact_section_payload(
                    _prefill_section_manual_fields({
                        "section_id": str(section.get("section_id") or ""),
                        **{
                            field: deepcopy(outline_context.get(str(section.get("section_id") or ""), {}).get(field, ""))
                            for field in SECTION_CONTEXT_FIELDS
                        },
                        **{
                            field: deepcopy(reference_context.get(str(section.get("section_id") or ""), {}).get(field, []))
                            for field in SECTION_REFERENCE_FIELDS
                        },
                        **{
                            field: deepcopy(section[field])
                            for field in SECTION_MANUAL_FIELDS
                            if field in section
                        },
                    })
                )
                if compact_context
                else _prefill_section_manual_fields({
                "section_id": str(section.get("section_id") or ""),
                **{
                    field: deepcopy(outline_context.get(str(section.get("section_id") or ""), {}).get(field, ""))
                    for field in SECTION_CONTEXT_FIELDS
                },
                **{
                    field: deepcopy(reference_context.get(str(section.get("section_id") or ""), {}).get(field, []))
                    for field in SECTION_REFERENCE_FIELDS
                },
                **{
                    field: deepcopy(section[field])
                    for field in SECTION_MANUAL_FIELDS
                    if field in section
                },
                })
            )
            for section in sections
            if isinstance(section, dict)
            and str(section.get("section_id") or "").strip()
            and (
                not selected_section_ids
                or str(section.get("section_id") or "").strip() in selected_section_ids
            )
        ],
    }
    write_json(output_path, payload)
    return payload


def _normalize_section(section: dict[str, Any], label: str) -> dict[str, Any]:
    section_id = str(section.get("section_id") or "").strip()
    if not section_id:
        raise ValueError(f"{label}.section_id 不能为空")
    normalized = deepcopy(section)
    normalized["section_id"] = section_id
    return normalized


def apply_template(receipt_path: Path, template_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    template = read_json(template_path, "节级回填侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError("节级回填侧车 schema_version 不正确")
    expected_sha = str(template.get("receipt_sha256") or "").strip()
    actual_sha = sha256_file(receipt_path)
    if expected_sha and expected_sha != actual_sha:
        raise ValueError("节级回填侧车绑定的 receipt_sha256 已失效，请重新 export")

    receipt_sections = receipt.get("sections")
    template_sections = template.get("sections")
    if not isinstance(receipt_sections, list):
        raise ValueError("回执缺少 sections 列表")
    if not isinstance(template_sections, list):
        raise ValueError("节级回填侧车缺少 sections 列表")

    receipt_index = {
        str(item.get("section_id") or ""): item
        for item in receipt_sections
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    }
    merged = deepcopy(receipt)
    merged_sections = merged["sections"]
    merged_index = {
        str(item.get("section_id") or ""): item
        for item in merged_sections
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    }

    seen_ids: set[str] = set()
    for index, raw in enumerate(template_sections):
        if not isinstance(raw, dict):
            raise ValueError(f"sections[{index}] 必须是对象")
        section = _normalize_section(raw, f"sections[{index}]")
        section_id = section["section_id"]
        if section_id in seen_ids:
            raise ValueError(f"节级回填侧车存在重复 section_id: {section_id}")
        seen_ids.add(section_id)
        if section_id not in receipt_index:
            raise ValueError(f"回执不存在 section_id={section_id} 的小节")
        target = merged_index[section_id]
        for field in SECTION_MANUAL_FIELDS:
            if field in section:
                target[field] = deepcopy(section[field])

    write_json(receipt_path, merged)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export/apply section-level manual review sidecars for outline performance receipts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export-template")
    export.add_argument("--receipt", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--outline")
    export.add_argument("--section-id", action="append", default=[])
    export.add_argument("--compact-context", action="store_true")

    apply_cmd = sub.add_parser("apply-template")
    apply_cmd.add_argument("--receipt", required=True)
    apply_cmd.add_argument("--input", required=True)
    apply_cmd.add_argument("--consume", action="store_true")
    apply_cmd.add_argument("--refresh-sidecar", action="append", default=[])

    args = parser.parse_args()
    try:
        if args.command == "export-template":
            payload = export_template(
                Path(args.receipt).resolve(),
                Path(args.output).resolve(),
                Path(args.outline).resolve() if args.outline else None,
                args.section_id,
                args.compact_context,
            )
            print(f"outline_section_review_template: exported ({len(payload['sections'])} sections)")
            return 0
        receipt_path = Path(args.receipt).resolve()
        template_path = Path(args.input).resolve()
        template_sha = sha256_file(template_path)
        merged = apply_template(receipt_path, template_path)
        receipt_sha = sha256_file(receipt_path)
        for raw_path in args.refresh_sidecar:
            refresh_sidecar_receipt_sha(Path(raw_path).resolve(), receipt_sha)
        if args.consume:
            consume_sidecar(
                template_path,
                input_sha256=template_sha,
                receipt_path=receipt_path,
                receipt_sha256=receipt_sha,
                operation="outline-section-review.apply",
                counts={"sections": len(merged.get("sections") or [])},
            )
        print("outline_section_review_template: applied")
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print("outline_section_review_template: blocked")
        print(f"- {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
