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
OUTLINE_METADATA_PREFIXES = (
    "- 情绪：",
    "- 读者新获知",
    "- 钩子：",
    "- 伏笔/物件：",
    "- 伏笔或物件：",
    "- 动静：",
    "- 对话密度：",
    "- 目标字数：",
)
MIN_DIRECT_IMITATION_SECTION_CHARS = 320
REQUIRED_SECTION_FIELDS = (
    "irreversible_action",
    "controlling_object",
    "source_function_mechanism",
    "original_scene_granularity",
    "scene_logic_contract",
    "source_mechanism",
    "information_delay",
    "character_missteps",
    "interaction_exchange",
    "conflict_carrier",
    "relationship_legibility",
    "emotion_intensity",
    "professional_shell_translation",
    "source_emotion_parity",
    "first_draft_generation_contract",
    "forbidden_items",
    "outline_evidence",
    "manual_judgment",
)
REQUIRED_BRIDGE_PARITY_FIELDS = (
    "source_bridge_id",
    "source_bridge_name",
    "source_path",
    "source_sha256",
    "source_required_sequence",
    "source_must_keep_actions",
    "source_scene_granularity",
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
    "role",
    "trigger",
    "relationship_position_change",
    "reader_effect",
    "intensity",
    "evidence",
)
STRONG_EMOTION_MIN_BEATS = 5
EMOTION_PROCESS_FIELDS = (
    "entry_state",
    "involuntary_body_response",
    "memory_association_or_attention_drift",
    "contradictory_impulse",
    "speech_misfire_or_avoidance",
    "scene_afterpain",
)
SCENE_LOGIC_LIST_FIELDS = (
    "source_causal_preconditions",
    "source_evidence",
    "target_entry_causes",
    "target_knowledge_state",
    "key_object_lifecycle",
    "obvious_alternative_blocker",
    "target_outline_evidence",
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


def outline_section_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    matches: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = SECTION_PATTERN.match(line)
        if match:
            matches.append((match.group(1), index))
    blocks: dict[str, str] = {}
    for idx, (section_id, start) in enumerate(matches):
        end = matches[idx + 1][1] if idx + 1 < len(matches) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        blocks[section_id] = body
    return blocks


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


def causal_asset_ids_from_profile(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        return []
    assets = data.get("causal_precondition_assets", []) if isinstance(data, dict) else []
    return list(
        dict.fromkeys(
            str(item.get("causal_asset_id") or "").strip()
            for item in assets
            if isinstance(item, dict) and str(item.get("causal_asset_id") or "").strip()
        )
    )


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
        profile_path = source.parent.parent / "book.profile.json"
        if not profile_path.is_file():
            raise FileNotFoundError(f"单书 profile 不存在: {profile_path}")
        available_causal_asset_ids = causal_asset_ids_from_profile(profile_path)
        if not available_causal_asset_ids:
            raise ValueError(f"单书 profile 未识别到场景因果资产 CPA: {profile_path}")
        role = "primary" if index == 0 else "auxiliary"
        sources.append(
            {
                "path": str(source),
                "sha256": sha256(source),
                "role": role,
                "bridge_catalog": {
                    "path": str(catalog.resolve()),
                    "sha256": sha256(catalog),
                },
                "available_bridge_ids": available_bridge_ids,
                "causal_asset_profile": {
                    "path": str(profile_path.resolve()),
                    "sha256": sha256(profile_path),
                },
                "available_causal_asset_ids": available_causal_asset_ids,
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
            }
        )

    sections = outline_sections(read_text(outline))
    first_source = sources[0]
    return {
        "version": "1.4",
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
            "scene_causality_reviewed_before_draft": False,
            "source_bridge_flow_inventory_completed": False,
            "outline_bridge_flow_parity_reviewed_before_draft": False,
            "relationship_legibility_reviewed_before_draft": False,
            "professional_shell_translation_reviewed_before_draft": False,
            "source_emotion_flow_parity_reviewed_before_draft": False,
            "first_draft_generation_contract_reviewed": False,
            "paragraph_breath_reviewed_before_draft": False,
            "sentence_relation_and_function_word_strategy_reviewed_before_draft": False,
            "granularity_transfer_contract_reviewed": False,
            "strong_emotion_required": False,
            "mechanism_transfer_boundary": "",
            "global_storyboard_or_process_list": None,
            "manual_judgment": "",
        },
        "story_fact_state_ledger": [],
        "granularity_transfer_contract": [],
        "source_bridge_flow_inventory": [
            {
                "source_path": first_source["path"],
                "source_sha256": first_source["sha256"],
                "bridge_id": "BID-01",
                "bridge_name": "",
                "source_required_sequence": [],
                "source_must_keep_actions": [],
                "source_scene_granularity": "",
                "source_end_state_change": "",
                "cannot_merge_or_drop_reason": "",
            }
        ],
        "outline_bridge_flow_parity": [
            {
                "source_bridge_id": "BID-01",
                "source_bridge_name": "",
                "source_path": first_source["path"],
                "source_sha256": first_source["sha256"],
                "source_required_sequence": [],
                "source_must_keep_actions": [],
                "source_scene_granularity": "",
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
        ],
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
                "scene_logic_contract": {
                    "source_path": "",
                    "source_sha256": "",
                    "causal_asset_id": "",
                    "source_causal_preconditions": [],
                    "source_evidence": [],
                    "target_entry_causes": [],
                    "target_knowledge_state": [],
                    "key_object_lifecycle": [],
                    "external_rule_dependency": {
                        "domain": "none",
                        "verified": None,
                        "authoritative_basis": "",
                    },
                    "obvious_alternative_blocker": [],
                    "exit_cause": "",
                    "target_outline_evidence": [],
                    "manual_judgment": "",
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
                "first_draft_generation_contract": {
                    "source_slice_bindings": [],
                    "source_performance_excerpt": "",
                    "source_performance_evidence": [],
                    "source_excerpt_reuse_reason": "",
                    "emotion_process": {
                        "entry_state": "",
                        "involuntary_body_response": "",
                        "memory_association_or_attention_drift": "",
                        "contradictory_impulse": "",
                        "speech_misfire_or_avoidance": "",
                        "scene_afterpain": "",
                    },
                    "continuous_moment_groups": [],
                    "paragraph_break_reasons": [],
                    "sentence_relation_plan": [],
                    "function_word_strategy": "",
                    "telegraphic_risk": "",
                    "emotion_shorthand_to_avoid": [],
                    "target_emotion_landing_plan": [],
                    "no_fixed_short_sentence_ratio": None,
                    "manual_judgment": "",
                },
                "forbidden_items": [],
                "outline_evidence": [],
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


def validate_scene_logic_contract(
    value: Any,
    source_paths: set[str],
    source_texts: dict[str, str],
    source_metadata: dict[str, dict[str, Any]],
    outline_text: str,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} scene_logic_contract 必须是对象")
        return
    source_path = Path(str(value.get("source_path") or "")).expanduser().resolve()
    source_key = str(source_path)
    if source_key not in source_paths:
        errors.append(f"{label} scene_logic_contract 必须绑定选中的原文来源")
    elif value.get("source_sha256") != sha256(source_path):
        errors.append(f"{label} scene_logic_contract 原文 SHA 不一致")
    causal_asset_id = str(value.get("causal_asset_id") or "").strip()
    if not causal_asset_id:
        errors.append(f"{label} scene_logic_contract.causal_asset_id 不能为空")
    elif causal_asset_id not in source_metadata.get(source_key, {}).get(
        "available_causal_asset_ids", []
    ):
        errors.append(
            f"{label} scene_logic_contract.causal_asset_id 不在所选原文 profile 中: "
            f"{causal_asset_id}"
        )
    for field in SCENE_LOGIC_LIST_FIELDS:
        minimum = 2 if field in {"source_evidence", "target_outline_evidence"} else 1
        if not nonempty_list(value.get(field), minimum=minimum):
            errors.append(f"{label} scene_logic_contract.{field} 至少 {minimum} 条")
    for quote in value.get("source_evidence") or []:
        if str(quote).strip() not in source_texts.get(source_key, ""):
            errors.append(f"{label} scene_logic_contract.source_evidence 不在原文中: {quote!r}")
    for quote in value.get("target_outline_evidence") or []:
        if str(quote).strip() not in outline_text:
            errors.append(
                f"{label} scene_logic_contract.target_outline_evidence 不在细纲中: {quote!r}"
            )
    for field in ("exit_cause", "manual_judgment"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} scene_logic_contract.{field} 不能为空")
    dependency = value.get("external_rule_dependency")
    if not isinstance(dependency, dict):
        errors.append(f"{label} scene_logic_contract.external_rule_dependency 必须是对象")
        return
    domain = str(dependency.get("domain") or "").strip().lower()
    if domain not in {"none", "medical", "legal", "financial", "administrative", "other"}:
        errors.append(f"{label} external_rule_dependency.domain 无效: {domain!r}")
    if dependency.get("verified") is not True:
        errors.append(f"{label} external_rule_dependency 必须完成人工核实")
    if not nonempty_text(dependency.get("authoritative_basis")):
        errors.append(f"{label} external_rule_dependency.authoritative_basis 不能为空")
    if domain != "none" and len(str(dependency.get("authoritative_basis") or "").strip()) < 8:
        errors.append(
            f"{label} 涉及医疗/法律/金融/行政制度时必须填写可核的可靠依据；"
            "无法核实时应改成角色主动选择"
        )


def validate_story_fact_state_ledger(
    value: Any,
    section_ids: list[str],
    outline_text: str,
    errors: list[str],
) -> None:
    if not isinstance(value, list) or not value:
        errors.append("story_fact_state_ledger 必须至少包含一条关键事实状态链")
        return
    section_order = {section_id: index for index, section_id in enumerate(section_ids)}
    seen_ids: set[str] = set()
    for index, fact in enumerate(value, start=1):
        label = f"story_fact_state_ledger 第 {index} 条"
        if not isinstance(fact, dict):
            errors.append(f"{label} 必须是对象")
            continue
        fact_id = str(fact.get("fact_id") or "").strip()
        if not fact_id:
            errors.append(f"{label}.fact_id 不能为空")
        elif fact_id in seen_ids:
            errors.append(f"{label}.fact_id 重复: {fact_id}")
        seen_ids.add(fact_id)
        current_state = str(fact.get("initial_state") or "").strip()
        if not current_state:
            errors.append(f"{label}.initial_state 不能为空")
        if not nonempty_list(fact.get("incompatible_states")):
            errors.append(f"{label}.incompatible_states 至少一条")
        transitions = fact.get("transitions")
        if not isinstance(transitions, list) or not transitions:
            errors.append(f"{label}.transitions 至少一条")
            continue
        previous_order = -1
        for transition_index, transition in enumerate(transitions, start=1):
            item_label = f"{label}.transitions[{transition_index}]"
            if not isinstance(transition, dict):
                errors.append(f"{item_label} 必须是对象")
                continue
            from_state = str(transition.get("from_state") or "").strip()
            to_state = str(transition.get("to_state") or "").strip()
            section_id = str(transition.get("section_id") or "").strip()
            if from_state != current_state:
                errors.append(
                    f"{item_label} 状态迁移不连续：期望 from_state={current_state!r}，"
                    f"实际为 {from_state!r}"
                )
            if not to_state:
                errors.append(f"{item_label}.to_state 不能为空")
            current_state = to_state
            if section_id not in section_order:
                errors.append(f"{item_label}.section_id 不在细纲中: {section_id}")
            elif section_order[section_id] < previous_order:
                errors.append(f"{item_label} 小节顺序倒退")
            else:
                previous_order = section_order[section_id]
            evidence = transition.get("trigger_evidence")
            if not nonempty_list(evidence):
                errors.append(f"{item_label}.trigger_evidence 至少一条")
            else:
                for quote in evidence:
                    if str(quote).strip() not in outline_text:
                        errors.append(f"{item_label}.trigger_evidence 不在细纲中: {quote!r}")


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


def validate_emotion_sequence(
    value: Any,
    label: str,
    errors: list[str],
    *,
    evidence_text: str,
    strong_emotion_required: bool,
) -> list[dict[str, Any]]:
    minimum = STRONG_EMOTION_MIN_BEATS if strong_emotion_required else 3
    if not isinstance(value, list) or len(value) < minimum:
        errors.append(f"{label} 至少填写 {minimum} 个完整情绪拍")
        return []
    beats: list[dict[str, Any]] = []
    for index, beat in enumerate(value, start=1):
        beat_label = f"{label}[{index}]"
        if not isinstance(beat, dict):
            errors.append(f"{beat_label} 必须是对象")
            continue
        for field in EMOTION_BEAT_FIELDS:
            if field not in beat:
                errors.append(f"{beat_label}.{field} 缺失")
        for field in (
            "role",
            "trigger",
            "relationship_position_change",
            "reader_effect",
            "evidence",
        ):
            if not nonempty_text(beat.get(field)):
                errors.append(f"{beat_label}.{field} 不能为空")
        intensity = beat.get("intensity")
        if not isinstance(intensity, (int, float)) or not 1 <= intensity <= 10:
            errors.append(f"{beat_label}.intensity 必须为 1-10")
        evidence = str(beat.get("evidence") or "").strip()
        if evidence and evidence not in evidence_text:
            errors.append(f"{beat_label}.evidence 不在绑定文本中: {evidence!r}")
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
    if source_roles and target_roles and source_roles != target_roles:
        errors.append(f"{label} 原文与目标情绪拍角色及顺序必须一致")
    if len(source_beats) != len(target_beats):
        errors.append(f"{label} 原文与目标情绪流程拍数必须一致")
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
        if not isinstance(source_index, int) or not 1 <= source_index <= len(source_beats):
            errors.append(f"{label} {source_field} 必须指向有效情绪拍")
        if not isinstance(target_index, int) or not 1 <= target_index <= len(target_beats):
            errors.append(f"{label} {target_field} 必须指向有效情绪拍")
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
    if strong_emotion_required and source_beats:
        distinct_evidence = {
            str(beat.get("evidence") or "").strip()
            for beat in source_beats
            if isinstance(beat, dict) and str(beat.get("evidence") or "").strip()
        }
        if len(distinct_evidence) < 2:
            errors.append(
                f"{label} 强情绪节不能用同一句原文证据覆盖全部情绪拍，"
                "至少绑定两处承担不同情绪功能的真实原文细节"
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


def validate_first_draft_generation_contract(
    value: Any,
    source_texts: dict[str, str],
    label: str,
    errors: list[str],
    *,
    strong_emotion_required: bool,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} first_draft_generation_contract 必须是对象")
        return

    source_slice_bindings = value.get("source_slice_bindings")
    if not isinstance(source_slice_bindings, list) or not source_slice_bindings:
        errors.append(f"{label} first_draft_generation_contract.source_slice_bindings 至少绑定一段精确原文行段")
    else:
        for index, binding in enumerate(source_slice_bindings, start=1):
            binding_label = f"{label}.source_slice_bindings[{index}]"
            if not isinstance(binding, dict):
                errors.append(f"{binding_label} 必须是对象")
                continue
            source_path = Path(str(binding.get("source_path") or "")).expanduser().resolve()
            source_text = source_texts.get(str(source_path))
            if source_text is None:
                errors.append(f"{binding_label}.source_path 必须绑定选中原文")
                continue
            if binding.get("source_sha256") != sha256(source_path):
                errors.append(f"{binding_label}.source_sha256 与原文不一致")
            range_match = re.fullmatch(r"L(\d+)-L(\d+)", str(binding.get("source_range") or "").strip())
            if not range_match:
                errors.append(f"{binding_label}.source_range 必须使用 L起始-L结束")
                continue
            start, end = int(range_match.group(1)), int(range_match.group(2))
            source_lines = source_text.splitlines()
            if start < 1 or end < start or end > len(source_lines):
                errors.append(f"{binding_label}.source_range 超出原文范围")
                continue
            source_slice = "\n".join(source_lines[start - 1 : end])
            evidence = binding.get("source_evidence")
            quotes = [str(quote).strip() for quote in evidence if str(quote).strip()] if isinstance(evidence, list) else []
            if len(set(quotes)) < 2:
                errors.append(f"{binding_label}.source_evidence 至少两条不同原文证据")
            for quote in quotes:
                if quote not in source_slice:
                    errors.append(f"{binding_label}.source_evidence 不在精确行段内: {quote!r}")
            consumed = binding.get("style_fields_consumed")
            if not isinstance(consumed, list) or len({str(item).strip() for item in consumed if str(item).strip()}) < 6:
                errors.append(f"{binding_label}.style_fields_consumed 必须覆盖六类逐 SF 文风颗粒")

    excerpt = str(value.get("source_performance_excerpt") or "").strip()
    if not excerpt or not any(excerpt in text for text in source_texts.values()):
        errors.append(
            f"{label} first_draft_generation_contract.source_performance_excerpt "
            "必须来自选中原文"
        )

    source_evidence = value.get("source_performance_evidence")
    minimum_source_evidence = 2 if strong_emotion_required else 1
    if not nonempty_list(source_evidence, minimum=minimum_source_evidence):
        errors.append(
            f"{label} first_draft_generation_contract.source_performance_evidence "
            f"至少填写 {minimum_source_evidence} 处真实原文表演证据"
        )
    else:
        distinct_source_evidence = {str(quote).strip() for quote in source_evidence}
        if len(distinct_source_evidence) < minimum_source_evidence:
            errors.append(f"{label} 原文表演证据不得用同一句重复充数")
        for quote in distinct_source_evidence:
            if not any(quote in text for text in source_texts.values()):
                errors.append(f"{label} 原文表演证据不在选中原文中: {quote!r}")

    emotion_process = value.get("emotion_process")
    if not isinstance(emotion_process, dict):
        errors.append(f"{label} first_draft_generation_contract.emotion_process 必须是对象")
    else:
        for field in EMOTION_PROCESS_FIELDS:
            if not nonempty_text(emotion_process.get(field)):
                errors.append(
                    f"{label} first_draft_generation_contract.emotion_process.{field} 不能为空"
                )

    for field, minimum, description in (
        ("continuous_moment_groups", 2, "至少两组连续瞬间"),
        ("paragraph_break_reasons", 2, "至少两条真实断段理由"),
        ("sentence_relation_plan", 3, "至少三条句间关系计划"),
        ("emotion_shorthand_to_avoid", 2, "至少两条情绪标签式写法"),
        ("target_emotion_landing_plan", 3, "至少三条目标正文情感落点计划"),
    ):
        if not nonempty_list(value.get(field), minimum=minimum):
            errors.append(
                f"{label} first_draft_generation_contract.{field} {description}"
            )

    for field in ("function_word_strategy", "telegraphic_risk", "manual_judgment"):
        if not nonempty_text(value.get(field)):
            errors.append(f"{label} first_draft_generation_contract.{field} 不能为空")
    if value.get("no_fixed_short_sentence_ratio") is not True:
        errors.append(f"{label} 首写不得设置固定短句、单句成段或段长比例")


def validate_bridge_inventory(
    value: Any,
    source_metadata: dict[str, dict[str, Any]],
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
            "source_end_state_change",
            "cannot_merge_or_drop_reason",
        ):
            if not nonempty_text(entry.get(field)):
                errors.append(f"{label}.{field} 不能为空")
        if not nonempty_list(entry.get("source_required_sequence"), minimum=2):
            errors.append(f"{label}.source_required_sequence 至少两步，不能只写功能名")
        if not nonempty_list(entry.get("source_must_keep_actions"), minimum=2):
            errors.append(f"{label}.source_must_keep_actions 至少两条必保动作/权力变化")
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
            if role == "primary":
                errors.append(f"主体来源必须填写 {expected_field}: {source_path}")
            # SF-only auxiliary consumption is validated by source_read_gate;
            # do not widen it into a parent BID inventory here.
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
    bridge_ids: set[str],
    source_texts: dict[str, str],
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
            "emotion_parity_judgment",
            "adaptation_reason",
            "missing_or_weakened_risk",
            "manual_judgment",
        ):
            if not nonempty_text(entry.get(field)):
                errors.append(f"{label}.{field} 不能为空")
        if not nonempty_list(entry.get("source_required_sequence"), minimum=2):
            errors.append(f"{label}.source_required_sequence 至少两步")
        if not nonempty_list(entry.get("source_must_keep_actions"), minimum=2):
            errors.append(f"{label}.source_must_keep_actions 至少两条")
        if source_key not in source_texts:
            errors.append(f"{label}.source_path 必须绑定选中的原文")
            source_text = ""
        else:
            source_text = source_texts[source_key]
            if entry.get("source_sha256") != sha256(source_path):
                errors.append(f"{label}.source_sha256 与原文不一致")
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
        for entry in value
        if isinstance(entry, dict) and str(entry.get("bridge_id") or "").strip()
    }
    missing = sorted(inventory_keys - parity_keys)
    if missing:
        errors.append(
            "原文桥段未完成细纲对齐: "
            + ", ".join(f"{Path(source).name}:{bridge_id}" for source, bridge_id in missing)
        )


def validate_granularity_transfer_contract(
    value: Any,
    source_paths: set[str],
    source_texts: dict[str, str],
    source_metadata: dict[str, dict[str, str]],
    section_ids: list[str],
    outline_text: str,
    errors: list[str],
) -> None:
    """Validate source granularity transfer without requiring source plot identity."""
    del source_metadata
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
                causal_profile_path = validate_binding(
                    source.get("causal_asset_profile"),
                    f"选中原文[{index}]场景因果 profile",
                    errors,
                )
                if causal_profile_path is not None:
                    actual_causal_ids = causal_asset_ids_from_profile(causal_profile_path)
                    if source.get("available_causal_asset_ids") != actual_causal_ids:
                        errors.append(
                            f"选中原文[{index}].available_causal_asset_ids 与 book.profile.json 不一致"
                        )
                source_mode = str(data.get("source_mode") or "full_bridge").strip()
                if expected_role == "primary" and source_mode == "full_bridge":
                    if source.get("required_bridge_ids") != source.get(
                        "available_bridge_ids"
                    ):
                        errors.append(
                            "主体来源 required_bridge_ids 必须覆盖桥段施工卡全部 BID"
                        )
                # Auxiliary sources may be consumed as complete SF contracts by the
                # independently required source-read gate. Only explicit BID choices
                # belong to this bridge inventory; an SF-only auxiliary must not be
                # widened into its parent BID here.

    global_review = data.get("global_review")
    if not isinstance(global_review, dict):
        errors.append("global_review 必须是对象")
    else:
        if global_review.get("full_source_mechanisms_reviewed") is not True:
            errors.append("必须人工确认已完整阅读选中原文的表演机制")
        if global_review.get("dual_track_function_and_scene_granularity_reviewed") is not True:
            errors.append("必须人工确认已同时核对拆书功能机制和原文场面颗粒度，不能只做功能映射")
        if global_review.get("scene_causality_reviewed_before_draft") is not True:
            errors.append("必须在正文前核对到场原因、知情边界、物件生命周期、制度约束和离场因果")
        source_mode = str(data.get("source_mode") or "full_bridge").strip()
        if source_mode == "full_bridge":
            if global_review.get("source_bridge_flow_inventory_completed") is not True:
                errors.append("必须先完成人工原文 BID/关键子桥段流程全集，不得边写正文边补")
            if global_review.get("outline_bridge_flow_parity_reviewed_before_draft") is not True:
                errors.append("必须在正文前完成人工逐桥流程对齐验收，不能写完正文后才发现流程错位")
        if global_review.get("relationship_legibility_reviewed_before_draft") is not True:
            errors.append("必须在正文前确认陌生读者无需职业知识即可看懂人物关系与伤害")
        if global_review.get("professional_shell_translation_reviewed_before_draft") is not True:
            errors.append("必须在正文前完成职业外壳白话翻译，禁止术语承担情绪")
        if global_review.get("source_emotion_flow_parity_reviewed_before_draft") is not True:
            errors.append("必须在正文前逐节核对原文情绪流程、反刀时机和烈度")
        if global_review.get("first_draft_generation_contract_reviewed") is not True:
            errors.append("必须在正文前逐节完成首写生成契约，不得先写后补")
        if global_review.get("paragraph_breath_reviewed_before_draft") is not True:
            errors.append("必须在正文前确认连续气口与真实断段理由")
        if global_review.get("sentence_relation_and_function_word_strategy_reviewed_before_draft") is not True:
            errors.append("必须在正文前确认句间关系与虚词连词策略")
        if str(data.get("source_mode") or "full_bridge") == "granularity_only":
            if global_review.get("granularity_transfer_contract_reviewed") is not True:
                errors.append("granularity_only 模式必须人工确认颗粒度迁移契约")
        if not nonempty_text(global_review.get("mechanism_transfer_boundary")):
            errors.append("必须写明机制迁移边界，禁止复制原人物、原职业、原句和完整桥壳")
        if global_review.get("global_storyboard_or_process_list") is not False:
            errors.append("必须人工确认细纲不是流程清单或证据排队表")
        if not nonempty_text(global_review.get("manual_judgment")):
            errors.append("global_review.manual_judgment 不能为空")

    outline_text = read_text(resolved_outline)
    section_ids = outline_sections(outline_text)
    if not section_ids:
        errors.append("细纲中未找到 `## 1.` 形式的小节")
        return errors
    section_blocks = outline_section_blocks(outline_text)
    validate_story_fact_state_ledger(
        data.get("story_fact_state_ledger"), section_ids, outline_text, errors
    )
    source_mode = str(data.get("source_mode") or "full_bridge").strip()
    if source_mode not in {"full_bridge", "granularity_only"}:
        errors.append(f"source_mode 无效: {source_mode!r}")
    if source_mode == "granularity_only":
        validate_granularity_transfer_contract(
            data.get("granularity_transfer_contract"),
            source_paths,
            source_texts,
            source_metadata,
            section_ids,
            outline_text,
            errors,
        )
        bridge_ids: set[str] = set()
    else:
        bridge_ids = validate_bridge_inventory(
            data.get("source_bridge_flow_inventory"),
            source_metadata,
            errors,
        )
    strong_emotion_required = bool(
        isinstance(global_review, dict)
        and global_review.get("strong_emotion_required") is True
    )
    if source_mode == "full_bridge":
        validate_bridge_parity(
            data.get("outline_bridge_flow_parity"),
            bridge_ids,
            source_texts,
            section_ids,
            outline_text,
            errors,
            strong_emotion_required=strong_emotion_required,
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
    repeated_generation_fields: dict[tuple[str, str], list[str]] = {}
    previous_generation_excerpt = ""
    for section_id in section_ids:
        entry = by_id.get(section_id)
        if not isinstance(entry, dict):
            continue
        label = f"第 {section_id} 节"
        section_text = section_blocks.get(section_id, "")
        validate_outline_section_shape(
            section_text,
            section_id,
            source_mode,
            errors,
        )
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
        validate_scene_logic_contract(
            entry.get("scene_logic_contract"),
            source_paths,
            source_texts,
            source_metadata,
            outline_text,
            label,
            errors,
        )
        validate_source_mechanism(entry.get("source_mechanism"), source_paths, label, errors)
        validate_information_delay(entry.get("information_delay"), label, errors)
        if not nonempty_list(entry.get("character_missteps"), minimum=2):
            errors.append(f"{label} character_missteps 至少填写两条人物偏手/错答")
        validate_exchange(entry.get("interaction_exchange"), label, errors)
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
        validate_first_draft_generation_contract(
            entry.get("first_draft_generation_contract"),
            source_texts,
            label,
            errors,
            strong_emotion_required=strong_emotion_required,
        )
        generation_contract = entry.get("first_draft_generation_contract")
        if isinstance(generation_contract, dict):
            generation_excerpt = str(
                generation_contract.get("source_performance_excerpt") or ""
            ).strip()
            if generation_excerpt and generation_excerpt == previous_generation_excerpt:
                if not nonempty_text(generation_contract.get("source_excerpt_reuse_reason")):
                    errors.append(
                        f"{label} 与相邻小节复用同一原文表演摘录时，"
                        "必须填写 source_excerpt_reuse_reason 说明本节读取的不同情感功能"
                    )
            previous_generation_excerpt = generation_excerpt
            emotion_process = generation_contract.get("emotion_process")
            for field in (
                "memory_association_or_attention_drift",
                "contradictory_impulse",
                "speech_misfire_or_avoidance",
            ):
                value = (
                    str(emotion_process.get(field) or "").strip()
                    if isinstance(emotion_process, dict)
                    else ""
                )
                if value:
                    repeated_generation_fields.setdefault((f"emotion_process.{field}", value), []).append(section_id)
            for field in (
                "continuous_moment_groups",
                "paragraph_break_reasons",
                "sentence_relation_plan",
                "function_word_strategy",
                "emotion_shorthand_to_avoid",
                "target_emotion_landing_plan",
            ):
                raw_value = generation_contract.get(field)
                value = (
                    json.dumps(raw_value, ensure_ascii=False, sort_keys=True)
                    if isinstance(raw_value, (list, dict))
                    else str(raw_value or "").strip()
                )
                if value:
                    repeated_generation_fields.setdefault((field, value), []).append(section_id)
        if not nonempty_list(entry.get("forbidden_items"), minimum=2):
            errors.append(f"{label} forbidden_items 至少填写两条禁写项")
        evidence = entry.get("outline_evidence")
        if not nonempty_list(evidence, minimum=2):
            errors.append(f"{label} outline_evidence 至少引用两条当前细纲原句")
        else:
            for quote in evidence:
                if str(quote).strip() not in outline_text:
                    errors.append(f"{label} outline_evidence 不在当前细纲中: {quote!r}")
                if section_text and str(quote).strip() not in section_text:
                    errors.append(f"{label} outline_evidence 不在对应小节正文中: {quote!r}")
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
    for (field, _value), repeated_sections in repeated_generation_fields.items():
        if len(repeated_sections) >= 3:
            errors.append(
                f"首写生成契约字段 {field} 在三节以上复用同一模板，"
                "必须逐节从绑定原文行段提取不同写法: "
                + ", ".join(repeated_sections)
            )

    if data.get("reviewed_by_current_model") is not True:
        errors.append("reviewed_by_current_model 必须为 true")
    if data.get("gate_status") != "passed":
        errors.append(f"gate_status 必须为 passed，当前为 {data.get('gate_status')!r}")
    if data.get("blocking_failures"):
        errors.append("blocking_failures 非空时不得放行")
    return errors


def validate_outline_section_shape(
    section_text: str,
    section_id: str,
    source_mode: str,
    errors: list[str],
) -> None:
    label = f"第 {section_id} 节"
    if not section_text.strip():
        errors.append(f"{label} 在小节大纲中没有正文内容")
        return

    nonempty_lines = [line for line in section_text.splitlines() if line.strip()]
    bullet_count = sum(1 for line in nonempty_lines if line.lstrip().startswith("- "))
    paragraphs = [
        block.strip()
        for block in re.split(r"\n\s*\n", section_text)
        if block.strip()
    ]
    prose_paragraphs = [
        block
        for block in paragraphs
        if not all(line.lstrip().startswith("- ") for line in block.splitlines() if line.strip())
    ]
    metadata_hits = 0
    for prefix in OUTLINE_METADATA_PREFIXES:
        if prefix == "- 读者新获知":
            if any(line.startswith(prefix) for line in nonempty_lines):
                metadata_hits += 1
        elif any(line.startswith(prefix) for line in nonempty_lines):
            metadata_hits += 1

    if source_mode != "granularity_only":
        if len(section_text) < MIN_DIRECT_IMITATION_SECTION_CHARS:
            errors.append(
                f"{label} 大纲正文过短（{len(section_text)} 字），"
                "更像事件摘要而不是可直接首写的原文颗粒场面纲"
            )
        if len(prose_paragraphs) < 2:
            errors.append(
                f"{label} 细纲至少应包含两段以上连续场面/颗粒说明，"
                "单段摘要不能冒充表演型细纲"
            )
        if bullet_count < 4 or metadata_hits < 6:
            errors.append(
                f"{label} 缺少细纲基准字段（情绪/新获知/钩子/伏笔物件/动静/对话密度/目标字数），"
                "不能只写场景摘要"
            )


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
