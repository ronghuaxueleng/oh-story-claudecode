#!/usr/bin/env python3
"""Initialize a pending per-section review without semantic judgments."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


SF_DIMENSIONS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
DEFERRED_REVIEW_MODE = "deferred_full_contract_review"
DIRECT_DIALOGUE_RE = re.compile(
    r"「[^」]*」(?:[^「」\n]{0,40}「[^」]*」)*|“[^”]*”(?:[^“”\n]{0,40}“[^”]*”)*"
)
ATTRIBUTION_RE = re.compile(
    r"[^。！？\n]{0,16}(?:说|问|答|道|回|喊|叫|告诉|回应|解释|追问|提醒)"
)


def iter_direct_dialogue_matches(text: str) -> list[re.Match[str]]:
    return list(DIRECT_DIALOGUE_RE.finditer(text))


def extract_direct_dialogue(text: str) -> list[str]:
    return [match.group(0) for match in iter_direct_dialogue_matches(text)]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def get_section(state: dict[str, Any], section_id: str) -> dict[str, Any]:
    for item in state.get("sections", []):
        if isinstance(item, dict) and str(item.get("section_id")) == section_id:
            return item
    raise ValueError(f"逐节状态不存在第 {section_id} 节")


def pending_sf_review(source: dict[str, Any]) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    source_dimensions = source.get("source_style_granularity") or {}
    for name in SF_DIMENSIONS:
        evidence = list((source_dimensions.get(name) or {}).get("source_evidence") or [])
        dimensions[name] = {
            "evidence_mappings": [
                {"source_quote": quote, "target_quotes": [], "comparison": ""}
                for quote in evidence
            ],
            "target_quotes": [],
            "comparison": "",
            "surface_copy_rejected": None,
        }
    return {
        "subflow_id": source.get("subflow_id"),
        "status": "pending",
        "semantic_review_method": "current_model_manual",
        "automation_used_for_semantic_judgment": False,
        "dimension_transfers": dimensions,
        "required_sequence_reviews": [
            {
                "source_step": step,
                "status": "pending",
                "target_quotes": [],
                "visible_change": "",
                "manual_judgment": "",
            }
            for step in source.get("required_sequence", [])
        ],
        "manual_judgment": "",
    }


def pending_detail_review(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_id": source.get("card_id"),
        "distinct_function_to_preserve": source.get("distinct_function_to_preserve"),
        "status": "pending",
        "target_quotes": [],
        "comparison": "",
        "manual_judgment": "",
        "surface_copy_rejected": None,
    }


def pending_sentence_mappings() -> list[dict[str, Any]]:
    return [
        {
            "target_sentence": "",
            "source_anchor_sentence": "",
            "target_surface_evidence": "",
            "source_surface_evidence": "",
            "feature_ids": [],
            "language_mechanism_match": "",
            "contract_used_during_writing": None,
        }
        for _ in range(4)
    ]


def pending_chain_reviews(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "status": "pending",
            "target_quotes": [],
            "target_chain_quotes": [],
            "sequence_comparison": "",
            "post_action_explanation_removed": None,
            "contract_used_during_writing": None,
            "manual_judgment": "",
        }
        for packet in plan.get("continuous_source_chain_packets", [])
        if isinstance(packet, dict)
    ]


def pending_dialogue_reviews(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "status": "pending",
            "target_quotes": [],
            "target_dialogue_turns": [],
            "oral_texture_preserved": None,
            "functional_compression_avoided": None,
            "rehearsal_used_as_voice_calibration": None,
            "rehearsal_copied_verbatim": None,
            "turn_sequence_comparison": "",
            "manual_judgment": "",
        }
        for packet in plan.get("dialogue_voice_packets", [])
        if isinstance(packet, dict)
    ]


def pending_relation_reviews(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "status": "pending",
            "target_quotes": [],
            "relation_type": packet.get("target_relation_type"),
            "marking_mode": packet.get("target_marking_mode"),
            "target_markers": list(packet.get("target_markers") or []),
            "source_function_word_logic_preserved": None,
            "mechanical_marker_insertion_avoided": None,
            "comparison": "",
            "manual_judgment": "",
        }
        for packet in plan.get("relation_micro_examples", [])
        if isinstance(packet, dict)
    ]


def pending_character_reviews(plan: dict[str, Any]) -> list[dict[str, Any]]:
    participants = (plan.get("character_plan") or {}).get("participants", [])
    return [
        {
            "character_name": participant.get("character_name"),
            "target_quotes": [],
            "evidence_ownership_reviews": [],
            "interchangeability_judgment": "",
        }
        for participant in participants
        if isinstance(participant, dict)
    ]


def pending_dialogue_grounding(staged_text: str) -> list[dict[str, Any]]:
    return [
        {
            "quote": quote,
            "speaker": "",
            "scene_pressure": "",
            "turn_connection": "",
            "interchangeability_judgment": "",
            "decision": "pending",
            "decision_allowed_values": ["keep", "revise"],
        }
        for quote in extract_direct_dialogue(staged_text)
    ]


def pending_scene_reviews(section_plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "scene_id": scene.get("scene_id"),
            "emotion_beat_ids": list(scene.get("emotion_beat_ids") or []),
            "plot_beat_ids": list(scene.get("plot_beat_ids") or []),
            "status": "pending",
            "summary_only": scene.get("summary_only"),
            "scene_complete": None,
            "entry_pressure_quote": "",
            "interaction_exchange_quotes": [],
            "turning_action_quote": "",
            "visible_consequence_quote": "",
            "aftershock_quote": "",
            "reader_emotion_progression": "",
            "why_not_summary": "",
            "manual_judgment": "",
        }
        for scene in section_plan.get("scene_units", [])
        if isinstance(scene, dict)
    ]


def build_review(
    state: dict[str, Any],
    prose: dict[str, Any],
    section_id: str,
    staged_text: str = "",
) -> dict[str, Any]:
    item = get_section(state, section_id)
    plan_path = Path(str(item.get("first_draft_plan_path") or "")).resolve()
    if not plan_path.is_file():
        raise ValueError(f"当前节计划不存在: {plan_path}")
    section_plan = load_json(plan_path)
    context_path = plan_path.parent.parent / "当前节写作包" / f"第{section_id}节.json"
    section_context: dict[str, Any] = {}
    if context_path.is_file():
        section_context = load_json(context_path)
        if str(section_context.get("section_id") or "") != section_id:
            raise ValueError(f"当前节写作包节号不匹配: {context_path}")
        expanded_plan = section_context.get("section_plan")
        if isinstance(expanded_plan, dict):
            section_plan = expanded_plan
    generation_plan = next(
        (
            entry
            for entry in prose.get("section_generation_plans", [])
            if isinstance(entry, dict) and str(entry.get("section_id")) == section_id
        ),
        {},
    )
    if not generation_plan:
        raise ValueError(f"文字合同缺少第 {section_id} 节写前落笔包")
    source_sf = {
        str(entry.get("subflow_id")): entry
        for entry in prose.get("source_subflow_reviews", [])
        if isinstance(entry, dict) and entry.get("subflow_id")
    }
    required_sf_ids = [str(value) for value in item.get("required_sf_ids", [])]
    missing = [sf_id for sf_id in required_sf_ids if sf_id not in source_sf]
    if missing:
        raise ValueError(f"文字合同缺少本节 SF: {missing}")
    source_details = {
        str(entry.get("card_id")): entry
        for entry in prose.get("source_detail_card_reviews", [])
        if isinstance(entry, dict) and entry.get("card_id")
    }
    required_detail_ids = [str(value) for value in item.get("required_detail_card_ids", [])]
    missing_details = [card_id for card_id in required_detail_ids if card_id not in source_details]
    if missing_details:
        raise ValueError(f"文字合同缺少本节主体细节卡: {missing_details}")
    emotion_sources = section_context.get("emotion_beat_contracts")
    plot_sources = section_context.get("plot_beat_contracts")
    if not isinstance(emotion_sources, list) or not emotion_sources:
        emotion_sources = item.get("emotion_beat_contracts")
    if not isinstance(plot_sources, list) or not plot_sources:
        plot_sources = item.get("plot_beat_contracts")
    if not isinstance(emotion_sources, list) or not emotion_sources:
        raise ValueError(f"当前节写作包缺少第 {section_id} 节完整 E 拍合同")
    if not isinstance(plot_sources, list) or not plot_sources:
        raise ValueError(f"当前节写作包缺少第 {section_id} 节完整 P 拍合同")
    if not section_plan.get("scene_units"):
        raise ValueError(f"当前节写作包缺少第 {section_id} 节展开 scene_units")

    review = {
        "section_id": section_id,
        "review_scaffold": {
            "generator": "story-short-write/init_section_review.py",
            "state_sha256": "",
            "semantic_fields_initialized_pending": True,
            "section_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "staged_dialogue_candidates_initialized": bool(staged_text),
            "mechanical_contract": {
                "target_quotes_must_copy_exact_contiguous_staged_text": True,
                "preserve_staged_line_breaks": True,
                "dialogue_decision_allowed_values": ["keep", "revise"],
                "manual_sidecar_manager": "story-short-write/manage_section_review.py",
                "manual_sidecar_generates_semantic_judgment": False,
                "normalizer": "story-short-write/normalize_section_review.py",
                "normalizer_generates_semantic_judgment": False,
            },
        },
        "manual_review_provenance": {
            "performed_by_current_model": None,
            "full_section_read_by_current_model": None,
            "semantic_fields_generated_by_script": None,
            "project_scripts_used_for_semantic_population": [],
            "manual_judgment": "",
        },
        "first_draft_mode": "single_pass_scene_realization",
        "complete_before_target_write": True,
        "substantive_append_or_expansion_after_target_write": False,
        "positive_generation_constraints": [],
        "reviewed_current_section_only": True,
        "semantic_review_method": "current_model_manual",
        "automation_used_for_semantic_judgment": False,
        "prose_review": {
            "status": "pending",
            "sentence_mappings": pending_sentence_mappings(),
            "continuous_chain_reviews": pending_chain_reviews(generation_plan),
            "dialogue_voice_reviews": pending_dialogue_reviews(generation_plan),
            "relation_micro_reviews": pending_relation_reviews(generation_plan),
            "source_subflow_reviews": [pending_sf_review(source_sf[sf_id]) for sf_id in required_sf_ids],
            "source_detail_card_reviews": [
                pending_detail_review(source_details[card_id]) for card_id in required_detail_ids
            ],
            "liveliness_review": {"target_live_sentences": []},
            "character_vitality_review": {
                "character_reviews": pending_character_reviews(generation_plan)
            },
            "dialogue_grounding_review": {
                "full_dialogue_reviews": pending_dialogue_grounding(staged_text)
            },
        },
        "emotion_review": {
            "status": "pending",
            "emotion_beat_ids": list(item.get("emotion_beat_ids", [])),
            "plot_beat_ids": list(item.get("plot_beat_ids", [])),
            "emotion_beat_reviews": [
                {
                    "beat_id": source.get("beat_id"), "role": source.get("role"),
                    "intensity": source.get("intensity"), "quote": "", "trigger": "",
                    "relationship_position_change": "", "reader_effect": "", "judgment": "",
                    "semantic_parity_status": "pending",
                }
                for source in emotion_sources
            ],
            "plot_beat_reviews": [
                {
                    "beat_id": source.get("beat_id"), "quote": "", "action_parity": "",
                    "external_change": "", "relationship_consequence": "", "judgment": "",
                    "semantic_parity_status": "pending",
                }
                for source in plot_sources
            ],
        },
        "scene_realization_reviews": pending_scene_reviews(section_plan),
        "issues_fixed": [],
        "final_status": "pending",
    }
    return review


def mark_review_deferred(
    review: dict[str, Any],
    *,
    state_path: Path,
    staged_path: Path,
    prose_path: Path,
    emotion_path: Path,
) -> dict[str, Any]:
    scaffold = review.setdefault("review_scaffold", {})
    scaffold["review_mode"] = DEFERRED_REVIEW_MODE
    scaffold["staged_sha256"] = hashlib.sha256(staged_path.read_bytes()).hexdigest()
    scaffold["deferred_semantic_review"] = {
        "target_contracts": [
            "全文文字颗粒度契约回执.json: bind-draft/validate-draft",
            "全文情绪颗粒度契约回执.json: bind-draft/validate-draft",
        ],
        "prewrite_contracts_remain_source_of_truth": True,
        "per_section_manual_sidecar_required": False,
        "fallback_on_detected_deviation": "delta_or_full_manual_sidecar",
        "bindings": {
            "state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
            "staged_sha256": hashlib.sha256(staged_path.read_bytes()).hexdigest(),
            "prose_receipt_sha256": hashlib.sha256(prose_path.read_bytes()).hexdigest(),
            "emotion_receipt_sha256": hashlib.sha256(emotion_path.read_bytes()).hexdigest(),
        },
    }
    review["final_status"] = "deferred_to_final_contracts"
    return review


def export_manual_sidecar(
    review_path: Path,
    staged_path: Path,
    sidecar_path: Path,
) -> None:
    script_path = Path(__file__).with_name("manage_section_review.py")
    spec = importlib.util.spec_from_file_location("manage_section_review", script_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载逐节人工侧车入口: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.export_template(review_path, staged_path, sidecar_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--staged", help="可选；默认自动读取写作资产/当前节暂存/第N节.md")
    parser.add_argument("--sidecar-output")
    args = parser.parse_args()
    state_path = Path(args.state).resolve()
    output_path = Path(args.output).resolve()
    if output_path.exists():
        raise SystemExit(f"拒绝覆盖已有逐节回执: {output_path}")
    state = load_json(state_path)
    prose_path = Path(str(state.get("paths", {}).get("prose_receipt") or "")).resolve()
    if not prose_path.is_file():
        raise SystemExit(f"文字合同不存在: {prose_path}")
    emotion_path = Path(str(state.get("paths", {}).get("emotion_receipt") or "")).resolve()
    if not emotion_path.is_file():
        raise SystemExit(f"情绪合同不存在: {emotion_path}")
    staged_path = (
        Path(args.staged).resolve()
        if args.staged
        else state_path.parent / "当前节暂存" / f"第{args.section}节.md"
    )
    staged_text = staged_path.read_text(encoding="utf-8") if staged_path.is_file() else ""
    review = build_review(state, load_json(prose_path), str(args.section), staged_text)
    review["review_scaffold"]["state_sha256"] = hashlib.sha256(state_path.read_bytes()).hexdigest()
    if not args.sidecar_output:
        if not staged_path.is_file():
            raise SystemExit("生成延后复核回执前必须存在当前节暂存稿")
        mark_review_deferred(
            review,
            state_path=state_path,
            staged_path=staged_path,
            prose_path=prose_path,
            emotion_path=emotion_path,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.sidecar_output:
        if not staged_path.is_file():
            raise SystemExit("生成逐节人工侧车前必须存在当前节暂存稿")
        export_manual_sidecar(
            output_path,
            staged_path,
            Path(args.sidecar_output).resolve(),
        )
    print("section_review_scaffold: initialized")
    print(f"section: {args.section}")
    print(f"output: {output_path}")
    if args.sidecar_output:
        print(f"sidecar: {Path(args.sidecar_output).resolve()}")
        print("semantic_status: pending_current_model_manual_review")
    else:
        print(f"review_mode: {DEFERRED_REVIEW_MODE}")
        print("semantic_status: deferred_to_final_contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
