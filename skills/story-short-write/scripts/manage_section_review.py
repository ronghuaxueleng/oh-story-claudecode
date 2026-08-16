#!/usr/bin/env python3
"""Export and apply compact manual sidecars for per-section prose reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-write.section-review-sidecar.v1"
LEAN_REVIEW_MODE = "delta_manual_review"
FULL_REVIEW_MODE = "full_manual_review"
DIRECT_DIALOGUE_RE = re.compile(
    r"「[^」]*」(?:[^「」\n]{0,40}「[^」]*」)*|“[^”]*”(?:[^“”\n]{0,40}“[^”]*”)*"
)
ATTRIBUTION_RE = re.compile(
    r"[^。！？\n]{0,16}(?:说|问|答|道|回|喊|叫|告诉|回应|解释|追问|提醒)"
)
SENTENCE_RE = re.compile(r".+?(?:[。！？!?；;](?:[”」』])?|$)", re.S)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label}顶层必须是对象: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_direct_dialogue_matches(text: str) -> list[re.Match[str]]:
    return list(DIRECT_DIALOGUE_RE.finditer(text))


def extract_direct_dialogue(text: str) -> list[str]:
    return [match.group(0) for match in iter_direct_dialogue_matches(text)]


def iter_paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"(?:^|\n[ \t]*\n)(.*?)(?=\n[ \t]*\n|\Z)", text, re.S):
        start, end = match.span(1)
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))
    return spans


def child_spans(text: str, parent_spans: list[tuple[int, int]], pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for parent_start, parent_end in parent_spans:
        segment = text[parent_start:parent_end]
        for match in pattern.finditer(segment):
            start = parent_start + match.start()
            end = parent_start + match.end()
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                spans.append((start, end))
    return spans


def build_registry(staged_text: str, review: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    paragraphs = iter_paragraph_spans(staged_text)
    typed_spans = {
        "Q": child_spans(staged_text, paragraphs, SENTENCE_RE),
        "D": [
            (match.start(), match.end())
            for match in iter_direct_dialogue_matches(staged_text)
        ],
    }
    registry: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for prefix in ("Q", "D"):
        counter = 0
        for start, end in typed_spans[prefix]:
            key = (prefix, start, end)
            if key in seen:
                continue
            seen.add(key)
            counter += 1
            registry.append(
                {
                    "evidence_id": f"{prefix}-{counter:03d}",
                    "kind": {
                        "Q": "sentence",
                        "D": "dialogue",
                    }[prefix],
                    "text": staged_text[start:end],
                    "start": start,
                    "end": end,
                }
            )

    fragments: list[str] = []
    if review:
        collect_existing_quotes(review, fragments)
    known_spans = {(item["start"], item["end"]) for item in registry}
    fragment_counter = 0
    for quote in fragments:
        if not quote:
            continue
        positions = [match.start() for match in re.finditer(re.escape(quote), staged_text)]
        if len(positions) != 1:
            continue
        start = positions[0]
        end = start + len(quote)
        if (start, end) in known_spans:
            continue
        known_spans.add((start, end))
        fragment_counter += 1
        registry.append(
            {
                "evidence_id": f"F-{fragment_counter:03d}",
                "kind": "existing_review_fragment",
                "text": quote,
                "start": start,
                "end": end,
            }
        )
    return registry


def collect_existing_quotes(node: Any, output: list[str], key: str = "") -> None:
    quote_keys = {
        "target_sentence",
        "target_surface_evidence",
        "target_quotes",
        "target_chain_quotes",
        "target_dialogue_turns",
        "quote",
        "entry_pressure_quote",
        "interaction_exchange_quotes",
        "turning_action_quote",
        "visible_consequence_quote",
        "aftershock_quote",
        "target_live_sentences",
    }
    if key in quote_keys:
        if isinstance(node, str):
            output.append(node)
        elif isinstance(node, list):
            output.extend(value for value in node if isinstance(value, str))
        return
    if isinstance(node, dict):
        for child_key, value in node.items():
            collect_existing_quotes(value, output, child_key)
    elif isinstance(node, list):
        for value in node:
            collect_existing_quotes(value, output, key)


def registry_index(registry: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["evidence_id"]): item for item in registry}


def evidence_ref_for_text(text: str, registry: list[dict[str, Any]]) -> str:
    exact = [item for item in registry if item["text"] == text]
    if exact:
        priority = {"D": 0, "Q": 1, "F": 2}
        exact.sort(key=lambda item: priority.get(str(item["evidence_id"])[0], 9))
        return str(exact[0]["evidence_id"])
    raise ValueError(f"无法把既有回执引句绑定到证据注册表: {text[:60]}")


def refs_for_value(value: Any, registry: list[dict[str, Any]]) -> list[str]:
    if isinstance(value, str):
        return [evidence_ref_for_text(value, registry)] if value else []
    if isinstance(value, list):
        return [evidence_ref_for_text(item, registry) for item in value if isinstance(item, str) and item]
    return []


def get_pointer(root: dict[str, Any], pointer: str) -> Any:
    node: Any = root
    for token in pointer.strip("/").split("/"):
        if not token:
            continue
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def add_item(
    items: list[dict[str, Any]],
    review: dict[str, Any],
    registry: list[dict[str, Any]],
    item_id: str,
    target: str,
    evidence_fields: tuple[str, ...] = (),
    manual_fields: tuple[str, ...] = (),
    context: dict[str, Any] | None = None,
) -> None:
    source = get_pointer(review, target)
    item = {
        "item_id": item_id,
        "_target": target,
        "evidence": {
            field: refs_for_value(source.get(field), registry) for field in evidence_fields
        },
        "fields": {field: deepcopy(source.get(field)) for field in manual_fields},
    }
    if context:
        item["context"] = context
    items.append(item)


def build_items(review: dict[str, Any], registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    add_item(
        items,
        review,
        registry,
        "PROVENANCE",
        "/manual_review_provenance",
        manual_fields=(
            "performed_by_current_model",
            "full_section_read_by_current_model",
            "semantic_fields_generated_by_script",
            "project_scripts_used_for_semantic_population",
            "manual_judgment",
        ),
    )
    add_item(
        items,
        review,
        registry,
        "ROOT",
        "/",
        manual_fields=("positive_generation_constraints", "issues_fixed", "final_status"),
    )
    add_item(items, review, registry, "PROSE", "/prose_review", manual_fields=("status",))
    add_item(items, review, registry, "EMOTION", "/emotion_review", manual_fields=("status",))

    prose = review.get("prose_review") or {}
    for index, row in enumerate(prose.get("sentence_mappings") or []):
        add_item(
            items,
            review,
            registry,
            f"SM-{index + 1:02d}",
            f"/prose_review/sentence_mappings/{index}",
            ("target_sentence", "target_surface_evidence"),
            (
                "source_anchor_sentence",
                "source_surface_evidence",
                "feature_ids",
                "language_mechanism_match",
                "contract_used_during_writing",
            ),
        )
    group_specs = (
        (
            "continuous_chain_reviews",
            "CHAIN",
            ("target_quotes", "target_chain_quotes"),
            (
                "status",
                "sequence_comparison",
                "post_action_explanation_removed",
                "contract_used_during_writing",
                "manual_judgment",
            ),
        ),
        (
            "dialogue_voice_reviews",
            "VOICE",
            ("target_quotes", "target_dialogue_turns"),
            (
                "status",
                "oral_texture_preserved",
                "functional_compression_avoided",
                "rehearsal_used_as_voice_calibration",
                "rehearsal_copied_verbatim",
                "turn_sequence_comparison",
                "manual_judgment",
            ),
        ),
        (
            "relation_micro_reviews",
            "REL",
            ("target_quotes",),
            (
                "status",
                "source_function_word_logic_preserved",
                "mechanical_marker_insertion_avoided",
                "comparison",
                "manual_judgment",
            ),
        ),
    )
    for field, prefix, evidence_fields, manual_fields in group_specs:
        for index, row in enumerate(prose.get(field) or []):
            add_item(
                items,
                review,
                registry,
                f"{prefix}-{index + 1:02d}",
                f"/prose_review/{field}/{index}",
                evidence_fields,
            manual_fields,
        )

    for sf_index, sf in enumerate(prose.get("source_subflow_reviews") or []):
        sf_id = str(sf.get("subflow_id") or f"SF-{sf_index + 1}")
        base = f"/prose_review/source_subflow_reviews/{sf_index}"
        add_item(
            items,
            review,
            registry,
            sf_id,
            base,
            manual_fields=("status", "manual_judgment"),
        )
        for dimension, transfer in (sf.get("dimension_transfers") or {}).items():
            dim_code = "".join(part[0] for part in dimension.split("_")).upper()
            dim_base = f"{base}/dimension_transfers/{dimension}"
            add_item(
                items,
                review,
                registry,
                f"{sf_id}-{dim_code}",
                dim_base,
                (),
                ("comparison", "surface_copy_rejected"),
                {"dimension": dimension},
            )
            for mapping_index, mapping in enumerate(transfer.get("evidence_mappings") or []):
                add_item(
                    items,
                    review,
                    registry,
                    f"{sf_id}-{dim_code}-MAP-{mapping_index + 1:02d}",
                    f"{dim_base}/evidence_mappings/{mapping_index}",
                    ("target_quotes",),
                    ("comparison",),
                    {"source_index": mapping_index + 1},
                )
        for step_index, step in enumerate(sf.get("required_sequence_reviews") or []):
            add_item(
                items,
                review,
                registry,
                f"{sf_id}-STEP-{step_index + 1:02d}",
                f"{base}/required_sequence_reviews/{step_index}",
                ("target_quotes",),
                ("status", "visible_change", "manual_judgment"),
                {"source_step": step.get("source_step")},
            )

    for index, row in enumerate(prose.get("source_detail_card_reviews") or []):
        add_item(
            items,
            review,
            registry,
            f"DETAIL-{row.get('card_id') or index + 1}",
            f"/prose_review/source_detail_card_reviews/{index}",
            ("target_quotes",),
            ("status", "comparison", "manual_judgment", "surface_copy_rejected"),
            {"card_id": row.get("card_id"), "title": row.get("title")},
        )
    add_item(
        items,
        review,
        registry,
        "LIVE",
        "/prose_review/liveliness_review",
        ("target_live_sentences",),
    )

    characters = ((prose.get("character_vitality_review") or {}).get("character_reviews") or [])
    for index, row in enumerate(characters):
        item_id = f"CHAR-{index + 1:02d}"
        add_item(
            items,
            review,
            registry,
            item_id,
            f"/prose_review/character_vitality_review/character_reviews/{index}",
            ("target_quotes",),
            ("interchangeability_judgment",),
            {"character_name": row.get("character_name")},
        )
        item = items[-1]
        ownership = []
        for owner_row in row.get("evidence_ownership_reviews") or []:
            ownership.append(
                {
                    "evidence_ref": evidence_ref_for_text(str(owner_row.get("quote") or ""), registry),
                    "ownership_context": owner_row.get("ownership_context"),
                    "keep_or_revise": owner_row.get("keep_or_revise"),
                }
            )
        item["ownership_reviews"] = ownership

    dialogues = ((prose.get("dialogue_grounding_review") or {}).get("full_dialogue_reviews") or [])
    for index, row in enumerate(dialogues):
        add_item(
            items,
            review,
            registry,
            f"DIALOGUE-{index + 1:03d}",
            f"/prose_review/dialogue_grounding_review/full_dialogue_reviews/{index}",
            ("quote",),
            ("speaker", "scene_pressure", "turn_connection", "interchangeability_judgment", "decision"),
        )

    emotion = review.get("emotion_review") or {}
    for index, row in enumerate(emotion.get("emotion_beat_reviews") or []):
        add_item(
            items,
            review,
            registry,
            f"E-{row.get('beat_id') or index + 1}",
            f"/emotion_review/emotion_beat_reviews/{index}",
            ("quote",),
            ("trigger", "relationship_position_change", "reader_effect", "judgment", "semantic_parity_status"),
            {"beat_id": row.get("beat_id"), "role": row.get("role"), "intensity": row.get("intensity")},
        )
    for index, row in enumerate(emotion.get("plot_beat_reviews") or []):
        add_item(
            items,
            review,
            registry,
            f"P-{row.get('beat_id') or index + 1}",
            f"/emotion_review/plot_beat_reviews/{index}",
            ("quote",),
            ("action_parity", "external_change", "relationship_consequence", "judgment", "semantic_parity_status"),
            {"beat_id": row.get("beat_id")},
        )

    for index, row in enumerate(review.get("scene_realization_reviews") or []):
        add_item(
            items,
            review,
            registry,
            f"SCENE-{row.get('scene_id') or index + 1}",
            f"/scene_realization_reviews/{index}",
            (
                "entry_pressure_quote",
                "interaction_exchange_quotes",
                "turning_action_quote",
                "visible_consequence_quote",
                "aftershock_quote",
            ),
            (
                "status",
                "scene_complete",
                "reader_emotion_progression",
                "why_not_summary",
                "manual_judgment",
            ),
            {"scene_id": row.get("scene_id")},
        )
    return items


def build_lean_review(review: dict[str, Any]) -> dict[str, Any]:
    prose = review.get("prose_review") or {}
    characters = ((prose.get("character_vitality_review") or {}).get("character_reviews") or [])
    return {
        "review_mode": LEAN_REVIEW_MODE,
        "performed_by_current_model": None,
        "full_section_read_by_current_model": None,
        "semantic_fields_generated_by_script": False,
        "project_scripts_used_for_semantic_population": [],
        "manual_judgment": "",
        "positive_generation_constraints": [],
        "issues_fixed": [],
        "no_unlisted_deviations": None,
        "section_judgment": "",
        "scene_reviews": [
            {
                "scene_id": row.get("scene_id"),
                "emotion_beat_ids": list(row.get("emotion_beat_ids") or []),
                "plot_beat_ids": list(row.get("plot_beat_ids") or []),
                "evidence": {
                    "entry_pressure_quote": [],
                    "interaction_exchange_quotes": [],
                    "turning_action_quote": [],
                    "visible_consequence_quote": [],
                    "aftershock_quote": [],
                },
                "reader_emotion_progression": "",
                "why_not_summary": "",
                "manual_judgment": "",
            }
            for row in (review.get("scene_realization_reviews") or [])
        ],
        "character_reviews": [
            {
                "character_name": row.get("character_name"),
                "target_quotes": [],
                "interchangeability_judgment": "",
            }
            for row in characters
        ],
        "final_status": "pending",
    }


def export_template(
    review_path: Path,
    staged_path: Path,
    output_path: Path,
    registry_path: Path | None = None,
    review_mode: str = LEAN_REVIEW_MODE,
) -> dict[str, Any]:
    review = load_json(review_path, "逐节回执")
    staged_text = staged_path.read_text(encoding="utf-8")
    registry = build_registry(staged_text, review)
    registry_path = registry_path or output_path.with_name(f"{output_path.stem}.evidence.json")
    registry_payload = {
        "schema_version": f"{SCHEMA_VERSION}.evidence",
        "section_id": str(review.get("section_id") or ""),
        "staged_sha256": sha256_file(staged_path),
        "evidence": {
            str(item["evidence_id"]): str(item["text"]) for item in registry
        },
    }
    write_json(registry_path, registry_payload)
    if review_mode not in {LEAN_REVIEW_MODE, FULL_REVIEW_MODE}:
        raise ValueError(
            f"review_mode 只能是 {LEAN_REVIEW_MODE}/{FULL_REVIEW_MODE}"
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "section_id": str(review.get("section_id") or ""),
        "bindings": {
            "review_path": str(review_path),
            "review_sha256": sha256_file(review_path),
            "staged_path": str(staged_path),
            "staged_sha256": sha256_file(staged_path),
            "evidence_registry_path": str(registry_path),
            "evidence_registry_sha256": sha256_file(registry_path),
        },
        "instructions": {
            "semantic_fields_must_be_filled_by_current_model": True,
            "evidence_refs_accept_exact_ids_only": True,
            "scripts_generate_semantic_judgment": False,
            "compact_structure_must_not_compress_semantics": True,
            "preflight_required_before_apply_or_commit": True,
            "minimum_semantic_lengths": {
                "provenance_manual_judgment": 24,
                "sentence_mechanism": 20,
                "group_or_detail_judgment": 20,
                "sf_mapping_comparison": 16,
                "emotion_or_plot_field": 12,
                "scene_field": 24,
            },
            "short_label_examples_rejected": [
                "物件换主",
                "双物证清楚",
                "动作完整",
                "后果明确",
            ],
            "default_review_mode": LEAN_REVIEW_MODE,
            "lean_mode_boundary": (
                "当前模型完整通读后只填写场景、人物、偏差与终审；"
                "任一未兑现或未列偏差必须退回全量人工侧车"
            ),
        },
    }
    if review_mode == LEAN_REVIEW_MODE:
        payload["lean_manual_review"] = build_lean_review(review)
    else:
        items = build_items(review, registry)
        payload["manual_items"] = [
            {key: deepcopy(value) for key, value in item.items() if key != "_target"}
            for item in items
        ]
    write_json(output_path, payload)
    return payload


def resolve_ref(ref: str, index: dict[str, dict[str, Any]], staged_text: str) -> str:
    if ".." in ref:
        start_id, end_id = ref.split("..", 1)
        if not start_id.startswith("Q-") or not end_id.startswith("Q-"):
            raise ValueError(f"连续证据范围只允许 Q ID: {ref}")
        if start_id not in index or end_id not in index:
            raise ValueError(f"未知证据范围: {ref}")
        start = index[start_id]["start"]
        end = index[end_id]["end"]
        if not isinstance(start, int) or not isinstance(end, int) or start >= end:
            raise ValueError(f"证据范围顺序无效: {ref}")
        return staged_text[start:end]
    if ref not in index:
        raise ValueError(f"未知证据 ID: {ref}")
    return str(index[ref]["text"])


def validate_complete_item(item: dict[str, Any]) -> None:
    item_id = str(item.get("item_id") or "?")
    for field, refs in (item.get("evidence") or {}).items():
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"{item_id}.evidence.{field} 不能为空")
        if len(refs) != len(set(refs)):
            raise ValueError(f"{item_id}.evidence.{field} 含重复证据 ID")
        if not all(isinstance(ref, str) and ref.strip() for ref in refs):
            raise ValueError(f"{item_id}.evidence.{field} 含无效证据 ID")
    for field, value in (item.get("fields") or {}).items():
        if field in {"issues_fixed", "project_scripts_used_for_semantic_population"}:
            if not isinstance(value, list):
                raise ValueError(f"{item_id}.fields.{field} 必须为列表")
            continue
        if value is None or value == "" or value == "pending":
            raise ValueError(f"{item_id}.fields.{field} 尚未人工填写")
        if isinstance(value, list) and not value:
            raise ValueError(f"{item_id}.fields.{field} 尚未人工填写")
    if "ownership_reviews" in item:
        ownership = item["ownership_reviews"]
        target_refs = (item.get("evidence") or {}).get("target_quotes") or []
        if not isinstance(ownership, list) or len(ownership) != len(target_refs):
            raise ValueError(f"{item_id}.ownership_reviews 必须与人物证据一一对应")
        if [row.get("evidence_ref") for row in ownership if isinstance(row, dict)] != target_refs:
            raise ValueError(f"{item_id}.ownership_reviews 证据顺序必须等于 target_quotes")
        for row in ownership:
            if not isinstance(row, dict) or not str(row.get("ownership_context") or "").strip():
                raise ValueError(f"{item_id}.ownership_reviews 缺少人物归属判断")
            if row.get("keep_or_revise") not in {"keep", "revise"}:
                raise ValueError(f"{item_id}.ownership_reviews.keep_or_revise 必须为 keep/revise")


def validate_fixed_semantic_contract(items: list[dict[str, Any]]) -> None:
    by_id = {str(item.get("item_id")): item for item in items}
    provenance = (by_id["PROVENANCE"].get("fields") or {})
    if provenance.get("performed_by_current_model") is not True:
        raise ValueError("PROVENANCE.performed_by_current_model 必须由当前模型确认为 true")
    if provenance.get("full_section_read_by_current_model") is not True:
        raise ValueError("PROVENANCE.full_section_read_by_current_model 必须由当前模型确认为 true")
    if provenance.get("semantic_fields_generated_by_script") is not False:
        raise ValueError("PROVENANCE.semantic_fields_generated_by_script 必须为 false")
    if provenance.get("project_scripts_used_for_semantic_population") != []:
        raise ValueError("PROVENANCE.project_scripts_used_for_semantic_population 必须为空")
    root = by_id["ROOT"].get("fields") or {}
    constraints = root.get("positive_generation_constraints")
    if not isinstance(constraints, list) or not 5 <= len(constraints) <= 9:
        raise ValueError("ROOT.positive_generation_constraints 必须包含 5-9 条")
    if root.get("final_status") != "passed":
        raise ValueError("ROOT.final_status 必须由当前模型裁决为 passed")
    if (by_id["PROSE"].get("fields") or {}).get("status") != "passed":
        raise ValueError("PROSE.status 必须由当前模型裁决为 passed")
    if (by_id["EMOTION"].get("fields") or {}).get("status") != "passed":
        raise ValueError("EMOTION.status 必须由当前模型裁决为 passed")
    for item in items:
        fields = item.get("fields") or {}
        if "status" in fields and fields["status"] != "passed":
            raise ValueError(f"{item['item_id']}.status 必须为 passed")
        if "semantic_parity_status" in fields and fields["semantic_parity_status"] != "passed":
            raise ValueError(f"{item['item_id']}.semantic_parity_status 必须为 passed")
        if "decision" in fields and fields["decision"] != "keep":
            raise ValueError(f"{item['item_id']}.decision 必须在提交前裁决为 keep")
        for row in item.get("ownership_reviews") or []:
            if row.get("keep_or_revise") != "keep":
                raise ValueError(f"{item['item_id']}.keep_or_revise 必须在提交前裁决为 keep")


def validate_semantic_specificity(items: list[dict[str, Any]]) -> None:
    """Mirror commit-time minimums before the sidecar can touch the formal receipt."""
    errors: list[str] = []

    def require_text(item_id: str, fields: dict[str, Any], field: str, minimum: int) -> None:
        value = str(fields.get(field) or "").strip()
        if len(value) < minimum:
            errors.append(f"{item_id}.fields.{field} 过短，至少需要 {minimum} 字的具体语义裁决")

    for item in items:
        item_id = str(item.get("item_id") or "?")
        fields = item.get("fields") or {}
        if item_id == "PROVENANCE":
            require_text(item_id, fields, "manual_judgment", 24)
        elif item_id.startswith("SM-"):
            require_text(item_id, fields, "language_mechanism_match", 20)
        elif item_id.startswith(("CHAIN-", "VOICE-", "REL-")):
            if "comparison" in fields:
                require_text(item_id, fields, "comparison", 20)
            if "sequence_comparison" in fields:
                require_text(item_id, fields, "sequence_comparison", 20)
            if "turn_sequence_comparison" in fields:
                require_text(item_id, fields, "turn_sequence_comparison", 20)
            require_text(item_id, fields, "manual_judgment", 20)
        elif "-MAP-" in item_id:
            require_text(item_id, fields, "comparison", 16)
        elif "-STEP-" in item_id:
            require_text(item_id, fields, "visible_change", 16)
            require_text(item_id, fields, "manual_judgment", 16)
        elif item_id.startswith("SF-"):
            if "comparison" in fields:
                require_text(item_id, fields, "comparison", 20)
            if "manual_judgment" in fields:
                require_text(item_id, fields, "manual_judgment", 20)
        elif item_id.startswith("DETAIL-"):
            require_text(item_id, fields, "comparison", 20)
            require_text(item_id, fields, "manual_judgment", 20)
        elif item_id.startswith("CHAR-"):
            require_text(item_id, fields, "interchangeability_judgment", 20)
            for index, row in enumerate(item.get("ownership_reviews") or [], start=1):
                if len(str(row.get("ownership_context") or "").strip()) < 12:
                    errors.append(
                        f"{item_id}.ownership_reviews[{index}].ownership_context "
                        "过短，必须点名人物/代词、动作或话轮及其归属"
                    )
        elif item_id.startswith("DIALOGUE-"):
            require_text(item_id, fields, "speaker", 2)
            for field in ("scene_pressure", "turn_connection", "interchangeability_judgment"):
                require_text(item_id, fields, field, 4)
        elif item_id.startswith(("E-", "P-")):
            semantic_fields = (
                ("trigger", "relationship_position_change", "reader_effect", "judgment")
                if item_id.startswith("E-")
                else ("action_parity", "external_change", "relationship_consequence", "judgment")
            )
            for field in semantic_fields:
                require_text(item_id, fields, field, 12)
        elif item_id.startswith("SCENE-"):
            for field in ("reader_emotion_progression", "why_not_summary", "manual_judgment"):
                require_text(item_id, fields, field, 24)
    if errors:
        raise ValueError("逐节人工侧车语义预检失败:\n- " + "\n- ".join(errors))


def expand_compact_manual_items(
    compact: dict[str, Any],
    expected_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected_ids = [str(item["item_id"]) for item in expected_items]
    if set(compact) != set(expected_ids):
        missing = [item_id for item_id in expected_ids if item_id not in compact]
        extra = [item_id for item_id in compact if item_id not in expected_ids]
        raise ValueError(f"compact_manual_items 项目不完整: missing={missing}, extra={extra}")
    expanded: list[dict[str, Any]] = []
    for expected in expected_items:
        item_id = str(expected["item_id"])
        row = compact[item_id]
        if not isinstance(row, dict):
            raise ValueError(f"{item_id} 紧凑人工项必须是对象")
        evidence_keys = list((expected.get("evidence") or {}).keys())
        field_keys = list((expected.get("fields") or {}).keys())
        evidence_values = row.get("e")
        field_values = row.get("f")
        if not isinstance(evidence_values, list) or len(evidence_values) != len(evidence_keys):
            raise ValueError(f"{item_id}.e 必须按官方顺序提供 {len(evidence_keys)} 项")
        if not isinstance(field_values, list) or len(field_values) != len(field_keys):
            raise ValueError(f"{item_id}.f 必须按官方顺序提供 {len(field_keys)} 项")
        item = {
            "item_id": item_id,
            "evidence": dict(zip(evidence_keys, evidence_values)),
            "fields": dict(zip(field_keys, field_values)),
        }
        if "ownership_reviews" in expected:
            ownership = row.get("o")
            if not isinstance(ownership, list):
                raise ValueError(f"{item_id}.o 必须提供人物证据归属复核")
            item["ownership_reviews"] = [
                {
                    "evidence_ref": values[0],
                    "ownership_context": values[1],
                    "keep_or_revise": values[2],
                }
                for values in ownership
                if isinstance(values, list) and len(values) == 3
            ]
            if len(item["ownership_reviews"]) != len(ownership):
                raise ValueError(f"{item_id}.o 每项必须是 [证据ID, 归属判断, keep/revise]")
        expanded.append(item)
    return expanded


def derive_sf_parent_quotes(review: dict[str, Any]) -> None:
    """Aggregate already selected mapping evidence without creating semantic judgments."""
    prose = review.get("prose_review") or {}
    for sf in prose.get("source_subflow_reviews") or []:
        if not isinstance(sf, dict):
            continue
        for transfer in (sf.get("dimension_transfers") or {}).values():
            if not isinstance(transfer, dict):
                continue
            target_quotes: list[str] = []
            for mapping in transfer.get("evidence_mappings") or []:
                if not isinstance(mapping, dict):
                    continue
                for quote in mapping.get("target_quotes") or []:
                    if isinstance(quote, str) and quote and quote not in target_quotes:
                        target_quotes.append(quote)
            transfer["target_quotes"] = target_quotes


def apply_template(
    review_path: Path,
    staged_path: Path,
    template_path: Path,
    *,
    write: bool = True,
) -> dict[str, Any]:
    review = load_json(review_path, "逐节回执")
    sidecar = load_json(template_path, "逐节人工侧车")
    if sidecar.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("逐节人工侧车 schema_version 不正确")
    bindings = sidecar.get("bindings") or {}
    if bindings.get("review_sha256") != sha256_file(review_path):
        raise ValueError("逐节人工侧车绑定的 review_sha256 已失效，请重新 export")
    if bindings.get("staged_sha256") != sha256_file(staged_path):
        raise ValueError("逐节人工侧车绑定的 staged_sha256 已失效，请重新 export")
    if str(sidecar.get("section_id") or "") != str(review.get("section_id") or ""):
        raise ValueError("逐节人工侧车 section_id 与正式回执不一致")

    staged_text = staged_path.read_text(encoding="utf-8")
    expected_registry = build_registry(staged_text, review)
    registry_path = Path(str(bindings.get("evidence_registry_path") or "")).resolve()
    registry_payload = load_json(registry_path, "正文证据注册表")
    if bindings.get("evidence_registry_sha256") != sha256_file(registry_path):
        raise ValueError("正文证据注册表 SHA 已失效，请重新 export")
    actual_registry = registry_payload.get("evidence")
    expected_registry_payload = {
        str(item["evidence_id"]): str(item["text"]) for item in expected_registry
    }
    if actual_registry != expected_registry_payload:
        raise ValueError("证据注册表已被修改，必须重新 export")
    expected_items = build_items(review, expected_registry)
    lean_review = sidecar.get("lean_manual_review")
    if isinstance(lean_review, dict):
        return apply_lean_review(
            review,
            staged_text,
            expected_registry,
            lean_review,
            review_path=review_path,
            staged_path=staged_path,
            template_path=template_path,
            bindings=bindings,
            write=write,
        )
    compact_items = sidecar.get("compact_manual_items")
    actual_items = (
        expand_compact_manual_items(compact_items, expected_items)
        if isinstance(compact_items, dict)
        else sidecar.get("manual_items")
    )
    if not isinstance(actual_items, list):
        raise ValueError("逐节人工侧车缺少 manual_items 或 compact_manual_items")
    expected_ids = [item["item_id"] for item in expected_items]
    actual_ids = [item.get("item_id") for item in actual_items if isinstance(item, dict)]
    if actual_ids != expected_ids:
        raise ValueError("manual_items 必须与官方导出项完整同序，禁止缺项、重复或新增项")

    index = registry_index(expected_registry)
    merged = deepcopy(review)
    for expected, actual in zip(expected_items, actual_items):
        if not isinstance(actual, dict):
            raise ValueError(f"{expected['item_id']} 必须是对象")
        if set((actual.get("evidence") or {})) != set(expected.get("evidence") or {}):
            raise ValueError(f"{expected['item_id']}.evidence 字段集合禁止修改")
        if set((actual.get("fields") or {})) != set(expected.get("fields") or {}):
            raise ValueError(f"{expected['item_id']}.fields 字段集合禁止修改")
        validate_complete_item(actual)
        target = get_pointer(merged, str(expected["_target"]))
        for field, refs in (actual.get("evidence") or {}).items():
            original = target.get(field)
            resolved = [resolve_ref(ref, index, staged_text) for ref in refs]
            target[field] = resolved if isinstance(original, list) else resolved[0]
        for field, value in (actual.get("fields") or {}).items():
            target[field] = deepcopy(value)
        if "ownership_reviews" in actual:
            target["evidence_ownership_reviews"] = [
                {
                    "quote": resolve_ref(row["evidence_ref"], index, staged_text),
                    "ownership_context": row["ownership_context"],
                    "keep_or_revise": row["keep_or_revise"],
                }
                for row in actual["ownership_reviews"]
            ]
    derive_sf_parent_quotes(merged)
    validate_fixed_semantic_contract(actual_items)
    validate_semantic_specificity(actual_items)
    scaffold = merged.setdefault("review_scaffold", {})
    scaffold["manual_sidecar"] = {
        "manager": "story-short-write/manage_section_review.py",
        "schema_version": SCHEMA_VERSION,
        "template_sha256": sha256_file(template_path),
        "review_sha256_before_apply": bindings["review_sha256"],
        "staged_sha256": bindings["staged_sha256"],
        "semantic_fields_generated_by_script": False,
    }
    if write:
        write_json(review_path, merged)
    return merged


def apply_lean_review(
    review: dict[str, Any],
    staged_text: str,
    registry: list[dict[str, Any]],
    lean: dict[str, Any],
    *,
    review_path: Path,
    staged_path: Path,
    template_path: Path,
    bindings: dict[str, Any],
    write: bool,
) -> dict[str, Any]:
    if lean.get("review_mode") != LEAN_REVIEW_MODE:
        raise ValueError("lean_manual_review.review_mode 不正确")
    if lean.get("performed_by_current_model") is not True:
        raise ValueError("lean_manual_review.performed_by_current_model 必须为 true")
    if lean.get("full_section_read_by_current_model") is not True:
        raise ValueError("lean_manual_review.full_section_read_by_current_model 必须为 true")
    if lean.get("semantic_fields_generated_by_script") is not False:
        raise ValueError("lean_manual_review.semantic_fields_generated_by_script 必须为 false")
    if lean.get("project_scripts_used_for_semantic_population") != []:
        raise ValueError("lean_manual_review 禁止项目脚本生成语义裁决")
    if len(str(lean.get("manual_judgment") or "").strip()) < 24:
        raise ValueError("lean_manual_review.manual_judgment 过短")
    constraints = lean.get("positive_generation_constraints")
    if not isinstance(constraints, list) or not 5 <= len(constraints) <= 9:
        raise ValueError("lean_manual_review.positive_generation_constraints 必须包含 5-9 条")
    if lean.get("no_unlisted_deviations") is not True:
        raise ValueError("存在未列明偏差时禁止使用差量侧车，必须退回全量侧车")
    if len(str(lean.get("section_judgment") or "").strip()) < 32:
        raise ValueError("lean_manual_review.section_judgment 必须具体说明全文、情绪和颗粒兑现")
    if lean.get("final_status") != "passed":
        raise ValueError("lean_manual_review.final_status 必须为 passed")

    index = registry_index(registry)
    expected_scenes = review.get("scene_realization_reviews") or []
    actual_scenes = lean.get("scene_reviews")
    if not isinstance(actual_scenes, list):
        raise ValueError("lean_manual_review.scene_reviews 必须为列表")
    if [row.get("scene_id") for row in actual_scenes if isinstance(row, dict)] != [
        row.get("scene_id") for row in expected_scenes if isinstance(row, dict)
    ]:
        raise ValueError("lean_manual_review.scene_reviews 必须完整同序覆盖当前节场景")

    expanded_scenes: list[dict[str, Any]] = []
    for expected, actual in zip(expected_scenes, actual_scenes):
        if actual.get("emotion_beat_ids") != expected.get("emotion_beat_ids"):
            raise ValueError(f"{actual.get('scene_id')}.emotion_beat_ids 与写前计划不一致")
        if actual.get("plot_beat_ids") != expected.get("plot_beat_ids"):
            raise ValueError(f"{actual.get('scene_id')}.plot_beat_ids 与写前计划不一致")
        evidence = actual.get("evidence") or {}
        required = (
            "entry_pressure_quote",
            "interaction_exchange_quotes",
            "turning_action_quote",
            "visible_consequence_quote",
            "aftershock_quote",
        )
        if set(evidence) != set(required):
            raise ValueError(f"{actual.get('scene_id')}.evidence 字段不完整")
        resolved: dict[str, Any] = {}
        for field in required:
            refs = evidence.get(field)
            if not isinstance(refs, list) or not refs:
                raise ValueError(f"{actual.get('scene_id')}.evidence.{field} 不能为空")
            values = [resolve_ref(ref, index, staged_text) for ref in refs]
            resolved[field] = values if field == "interaction_exchange_quotes" else values[0]
        if len(resolved["interaction_exchange_quotes"]) < 3:
            raise ValueError(f"{actual.get('scene_id')} 至少需要三步施压与接招证据")
        for field in ("reader_emotion_progression", "why_not_summary", "manual_judgment"):
            if len(str(actual.get(field) or "").strip()) < 24:
                raise ValueError(f"{actual.get('scene_id')}.{field} 过短")
        expanded_scenes.append(
            {
                "scene_id": actual["scene_id"],
                "emotion_beat_ids": list(actual["emotion_beat_ids"]),
                "plot_beat_ids": list(actual["plot_beat_ids"]),
                **resolved,
                "reader_emotion_progression": actual["reader_emotion_progression"],
                "why_not_summary": actual["why_not_summary"],
                "manual_judgment": actual["manual_judgment"],
            }
        )

    expected_characters = [
        row.get("character_name")
        for row in (((review.get("prose_review") or {}).get("character_vitality_review") or {}).get("character_reviews") or [])
    ]
    actual_characters = lean.get("character_reviews")
    if not isinstance(actual_characters, list) or [
        row.get("character_name") for row in actual_characters if isinstance(row, dict)
    ] != expected_characters:
        raise ValueError("lean_manual_review.character_reviews 必须完整同序覆盖写前人物")
    expanded_characters = []
    for row in actual_characters:
        refs = row.get("target_quotes")
        if not isinstance(refs, list) or len(refs) < 2:
            raise ValueError(f"{row.get('character_name')} 至少需要两条人物证据")
        judgment = str(row.get("interchangeability_judgment") or "").strip()
        if len(judgment) < 20:
            raise ValueError(f"{row.get('character_name')}.interchangeability_judgment 过短")
        expanded_characters.append(
            {
                "character_name": row["character_name"],
                "target_quotes": [resolve_ref(ref, index, staged_text) for ref in refs],
                "interchangeability_judgment": judgment,
            }
        )

    merged = deepcopy(review)
    merged["manual_review_provenance"] = {
        "performed_by_current_model": True,
        "full_section_read_by_current_model": True,
        "semantic_fields_generated_by_script": False,
        "project_scripts_used_for_semantic_population": [],
        "manual_judgment": lean["manual_judgment"],
    }
    merged["positive_generation_constraints"] = list(constraints)
    merged["issues_fixed"] = list(lean.get("issues_fixed") or [])
    merged["final_status"] = "passed"
    merged.setdefault("prose_review", {})["status"] = "passed"
    merged.setdefault("emotion_review", {})["status"] = "passed"
    merged["delta_manual_review"] = {
        "review_mode": LEAN_REVIEW_MODE,
        "no_unlisted_deviations": True,
        "section_judgment": lean["section_judgment"],
        "scene_reviews": expanded_scenes,
        "character_reviews": expanded_characters,
    }
    scaffold = merged.setdefault("review_scaffold", {})
    scaffold["manual_sidecar"] = {
        "manager": "story-short-write/manage_section_review.py",
        "schema_version": SCHEMA_VERSION,
        "review_mode": LEAN_REVIEW_MODE,
        "template_sha256": sha256_file(template_path),
        "review_sha256_before_apply": bindings["review_sha256"],
        "staged_sha256": bindings["staged_sha256"],
        "semantic_fields_generated_by_script": False,
        "inherited_prewrite_semantics_only": True,
    }
    if write:
        write_json(review_path, merged)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export/apply compact manual sidecars for per-section prose reviews."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export-template")
    export.add_argument("--review", required=True)
    export.add_argument("--staged", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--registry-output")
    export.add_argument(
        "--review-mode",
        choices=(LEAN_REVIEW_MODE, FULL_REVIEW_MODE),
        default=LEAN_REVIEW_MODE,
    )
    apply_cmd = sub.add_parser("apply-template")
    apply_cmd.add_argument("--review", required=True)
    apply_cmd.add_argument("--staged", required=True)
    apply_cmd.add_argument("--input", required=True)
    preflight = sub.add_parser("preflight-template")
    preflight.add_argument("--review", required=True)
    preflight.add_argument("--staged", required=True)
    preflight.add_argument("--input", required=True)
    args = parser.parse_args()

    try:
        if args.command == "export-template":
            payload = export_template(
                Path(args.review).resolve(),
                Path(args.staged).resolve(),
                Path(args.output).resolve(),
                Path(args.registry_output).resolve() if args.registry_output else None,
                args.review_mode,
            )
            print("section_review_sidecar: exported")
            print(f"evidence_registry: {payload['bindings']['evidence_registry_path']}")
            print(f"review_mode: {args.review_mode}")
            if args.review_mode == LEAN_REVIEW_MODE:
                print(f"scene_review_count: {len(payload['lean_manual_review']['scene_reviews'])}")
                print(f"character_review_count: {len(payload['lean_manual_review']['character_reviews'])}")
            else:
                print(f"manual_item_count: {len(payload['manual_items'])}")
            print("semantic_fields_generated: 0")
            return 0
        if args.command == "preflight-template":
            apply_template(
                Path(args.review).resolve(),
                Path(args.staged).resolve(),
                Path(args.input).resolve(),
                write=False,
            )
            print("section_review_sidecar: preflight_passed")
            print("formal_receipt_modified: false")
            print("semantic_fields_generated: 0")
            return 0
        apply_template(
            Path(args.review).resolve(),
            Path(args.staged).resolve(),
            Path(args.input).resolve(),
        )
        print("section_review_sidecar: applied")
        print("semantic_fields_generated: 0")
        return 0
    except (FileNotFoundError, OSError, ValueError) as exc:
        print("section_review_sidecar: blocked")
        print(f"- {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
