#!/usr/bin/env python3
"""Normalize deterministic mechanics in a manually completed section review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


QUOTE_FIELDS = {
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
DIALOGUE_DECISION_ALIASES = {
    "passed": "keep",
    "approved": "keep",
    "failed": "revise",
    "rejected": "revise",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def non_whitespace_index(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    offsets: list[int] = []
    for offset, char in enumerate(text):
        if not char.isspace():
            chars.append(char)
            offsets.append(offset)
    return "".join(chars), offsets


def restore_exact_span(value: str, staged_text: str) -> tuple[str, str | None]:
    if not value or value in staged_text:
        return value, None
    needle = re.sub(r"\s+", "", value)
    if not needle:
        return value, None
    compact_text, offsets = non_whitespace_index(staged_text)
    matches: list[int] = []
    start = 0
    while True:
        found = compact_text.find(needle, start)
        if found < 0:
            break
        matches.append(found)
        start = found + 1
    if len(matches) != 1:
        reason = "不存在" if not matches else "出现多次，无法唯一绑定"
        return value, reason
    match = matches[0]
    exact = staged_text[offsets[match] : offsets[match + len(needle) - 1] + 1]
    return exact, None


def normalize_quote_fields(
    node: Any,
    staged_text: str,
    path: str = "$",
) -> tuple[int, list[str]]:
    changes = 0
    errors: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            current_path = f"{path}.{key}"
            if key in QUOTE_FIELDS:
                if isinstance(value, str):
                    restored, error = restore_exact_span(value, staged_text)
                    if error:
                        errors.append(f"{current_path}: {error}")
                    elif restored != value:
                        node[key] = restored
                        changes += 1
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        if not isinstance(item, str):
                            continue
                        restored, error = restore_exact_span(item, staged_text)
                        item_path = f"{current_path}[{index}]"
                        if error:
                            errors.append(f"{item_path}: {error}")
                        elif restored != item:
                            value[index] = restored
                            changes += 1
            child_changes, child_errors = normalize_quote_fields(value, staged_text, current_path)
            changes += child_changes
            errors.extend(child_errors)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            child_changes, child_errors = normalize_quote_fields(
                item, staged_text, f"{path}[{index}]"
            )
            changes += child_changes
            errors.extend(child_errors)
    return changes, errors


def normalize_dialogue_decisions(review: dict[str, Any]) -> int:
    rows = (
        review.get("prose_review", {})
        .get("dialogue_grounding_review", {})
        .get("full_dialogue_reviews", [])
    )
    changes = 0
    if not isinstance(rows, list):
        return changes
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = str(row.get("decision") or "").strip().lower()
        normalized = DIALOGUE_DECISION_ALIASES.get(decision)
        if normalized:
            row["decision"] = normalized
            changes += 1
    return changes


def validate_sentence_mapping_links(review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    mappings = review.get("prose_review", {}).get("sentence_mappings", [])
    if not isinstance(mappings, list):
        return errors
    for index, mapping in enumerate(mappings, start=1):
        if not isinstance(mapping, dict):
            continue
        sentence = str(mapping.get("target_sentence") or "")
        surface = str(mapping.get("target_surface_evidence") or "")
        if sentence and surface and sentence not in surface:
            errors.append(
                f"$.prose_review.sentence_mappings[{index - 1}]: "
                "target_surface_evidence 未包含 target_sentence"
            )
    return errors


def normalize_review(review: dict[str, Any], staged_text: str) -> tuple[int, list[str]]:
    changes, errors = normalize_quote_fields(review, staged_text)
    changes += normalize_dialogue_decisions(review)
    errors.extend(validate_sentence_mapping_links(review))
    return changes, errors


def apply_normalization(review_path: Path, staged_path: Path) -> tuple[int, list[str]]:
    review = load_json(review_path)
    staged_text = staged_path.read_text(encoding="utf-8")
    changes, errors = normalize_review(review, staged_text)
    if errors:
        return changes, errors
    scaffold = review.setdefault("review_scaffold", {})
    scaffold["mechanical_normalizer"] = "story-short-write/normalize_section_review.py"
    scaffold["mechanical_normalization_applied"] = True
    scaffold["mechanical_normalization_change_count"] = changes
    scaffold["mechanical_normalization_semantic_fields_generated"] = False
    scaffold["staged_sha256_at_normalization"] = hashlib.sha256(
        staged_path.read_bytes()
    ).hexdigest()
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return changes, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True)
    parser.add_argument("--staged", required=True)
    args = parser.parse_args()

    review_path = Path(args.review).resolve()
    staged_path = Path(args.staged).resolve()
    changes, errors = apply_normalization(review_path, staged_path)
    if errors:
        print("section_review_mechanics: blocked")
        for error in errors:
            print(f"- {error}")
        return 1
    print("section_review_mechanics: normalized")
    print(f"changes: {changes}")
    print("semantic_changes: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
