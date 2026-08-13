#!/usr/bin/env python3
"""Initialize a pending per-section review without semantic judgments."""

from __future__ import annotations

import argparse
import hashlib
import json
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
            "source_evidence": evidence,
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
        "category": source.get("category"),
        "title": source.get("title"),
        "source_quote": source.get("source_quote"),
        "distinct_function_to_preserve": source.get("distinct_function_to_preserve"),
        "status": "pending",
        "target_quotes": [],
        "comparison": "",
        "manual_judgment": "",
        "surface_copy_rejected": None,
    }


def build_review(state: dict[str, Any], prose: dict[str, Any], section_id: str) -> dict[str, Any]:
    item = get_section(state, section_id)
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

    review = {
        "section_id": section_id,
        "review_scaffold": {
            "generator": "story-short-write/init_section_review.py",
            "state_sha256": "",
            "semantic_fields_initialized_pending": True,
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
            "sentence_mappings": [],
            "continuous_chain_reviews": [],
            "dialogue_voice_reviews": [],
            "relation_micro_reviews": [],
            "source_subflow_reviews": [pending_sf_review(source_sf[sf_id]) for sf_id in required_sf_ids],
            "source_detail_card_reviews": [
                pending_detail_review(source_details[card_id]) for card_id in required_detail_ids
            ],
            "liveliness_review": {"target_live_sentences": []},
            "character_vitality_review": {"character_reviews": []},
            "dialogue_grounding_review": {"full_dialogue_reviews": []},
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
                for source in item.get("emotion_beat_contracts", [])
            ],
            "plot_beat_reviews": [
                {
                    "beat_id": source.get("beat_id"), "quote": "", "action_parity": "",
                    "external_change": "", "relationship_consequence": "", "judgment": "",
                    "semantic_parity_status": "pending",
                }
                for source in item.get("plot_beat_contracts", [])
            ],
        },
        "scene_realization_reviews": [],
        "issues_fixed": [],
        "final_status": "pending",
    }
    return review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    state_path = Path(args.state).resolve()
    output_path = Path(args.output).resolve()
    if output_path.exists():
        raise SystemExit(f"拒绝覆盖已有逐节回执: {output_path}")
    state = load_json(state_path)
    prose_path = Path(str(state.get("paths", {}).get("prose_receipt") or "")).resolve()
    if not prose_path.is_file():
        raise SystemExit(f"文字合同不存在: {prose_path}")
    review = build_review(state, load_json(prose_path), str(args.section))
    review["review_scaffold"]["state_sha256"] = hashlib.sha256(state_path.read_bytes()).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("section_review_scaffold: initialized")
    print(f"section: {args.section}")
    print(f"output: {output_path}")
    print("semantic_status: pending_current_model_manual_review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
