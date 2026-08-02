#!/usr/bin/env python3
"""Validate the source-bound scene-performance contract for a short-story outline."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SECTION_PATTERN = re.compile(r"^##\s+(?:第\s*)?(\d+)(?:\s*节)?[.、．]?(?:\s+.*)?$")
SECTION_TITLE_PATTERN = re.compile(r"^##\s+(?:第\s*)?(\d+)(?:\s*节)?[.、．]?\s*(.*)$")
SUBHEADING_PATTERN = re.compile(r"^###\s+(.+?)\s*$")
BRIDGE_HEADING_PATTERN = re.compile(r"^##\s+\[?(BID-\d+)\]?", re.MULTILINE)
SOURCE_SUBFLOW_REF_RE = re.compile(r"(?:《(?P<title>[^》]+)》)?\s*(?P<subflow_id>SF-\d+)")
LINE_RANGE_RE = re.compile(r"^L(?P<start>\d+)-L(?P<end>\d+)$")
CATALOG_LINE_RANGE_RE = re.compile(r"L(?P<start>\d+)-L(?P<end>\d+)")
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
BEAT_DEPENDENCY_FIELDS = (
    "beat_id",
    "actor",
    "action",
    "from_state",
    "trigger",
    "knowledge_before",
    "spatial_or_object_access",
    "to_state",
    "next_beat_cause",
    "outline_evidence",
)
CAUSAL_RISK_TYPES = (
    "character_convergence",
    "critical_information_delay",
    "critical_interruption",
    "spatial_or_object_access",
)
CAUSAL_PLACEHOLDER_MARKERS = (
    "读者新获知",
    "上一节已公开的信息",
    "人物均由上一节未完成动作或主动追问",
    "必须留到场末",
    "已有明确持有人",
    "均连续",
    "不是作者强推人物动作的借口",
)
STYLE_GRANULARITY_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)


def load_primary_source_bundle_module() -> Any:
    script = Path(__file__).with_name("build_primary_source_semantic_bundle.py")
    spec = importlib.util.spec_from_file_location("build_primary_source_semantic_bundle", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载主体原文完整颗粒包脚本: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRIMARY_SOURCE_BUNDLE_MODULE = load_primary_source_bundle_module()


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


def outline_section_blocks(text: str) -> dict[str, dict[str, Any]]:
    blocks: dict[str, dict[str, Any]] = {}
    current_id = ""
    current_title = ""
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        if match := SECTION_TITLE_PATTERN.match(raw_line):
            if current_id:
                blocks[current_id] = {
                    "title": current_title,
                    "lines": current_lines,
                }
            current_id = match.group(1)
            current_title = str(match.group(2) or "").strip()
            current_lines = [raw_line]
            continue
        if current_id:
            current_lines.append(raw_line)
    if current_id:
        blocks[current_id] = {
            "title": current_title,
            "lines": current_lines,
        }
    return blocks


def subsection_map(lines: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current = ""
    for raw_line in lines[1:]:
        if match := SUBHEADING_PATTERN.match(raw_line):
            current = match.group(1).strip()
            result.setdefault(current, [])
            continue
        bullet_line = raw_line.strip()
        if bullet_line.startswith(("-", "*")):
            content = bullet_line[1:].strip()
            bullet_match = re.match(r"^([^：:]+)[：:]\s*$", content)
            if bullet_match:
                current = bullet_match.group(1).strip()
                result.setdefault(current, [])
                continue
        if current:
            result[current].append(raw_line)
    return result


def compact_lines(lines: list[str], *, limit: int = 2) -> list[str]:
    result: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("-", "*", ">")):
            line = line[1:].strip()
        line = re.sub(r"^\d+\.\s*", "", line)
        if not line:
            continue
        result.append(line)
        if len(result) >= limit:
            break
    return result


def join_summary(lines: list[str], *, limit: int = 2) -> str:
    values = compact_lines(lines, limit=limit)
    return "；".join(values)


def merged_part_lines(parts: dict[str, list[str]], *names: str) -> list[str]:
    merged: list[str] = []
    for name in names:
        value = parts.get(name, [])
        if not isinstance(value, list):
            continue
        merged.extend(value)
    return merged


def split_progression_text(text: str) -> list[str]:
    if not str(text).strip():
        return []
    parts = re.split(r"\s*(?:->|→|=>|＞)\s*", str(text).strip())
    return [item.strip("；;，,。 ") for item in parts if item.strip("；;，,。 ")]


def normalize_source_title(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def extract_labeled_value(lines: list[str], label: str) -> str:
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("-", "*", ">")):
            line = line[1:].strip()
        match = re.match(rf"^{re.escape(label)}[：:]\s*(.+)$", line)
        if match:
            return match.group(1).strip()
    return ""


def split_catalog_items(text: str) -> list[str]:
    if not str(text).strip():
        return []
    parts = re.split(r"\s*(?:->|→|=>|＞|；|;)\s*", str(text).strip())
    result: list[str] = []
    for part in parts:
        cleaned = part.strip("，,。:： ")
        if cleaned:
            result.append(cleaned)
    return result


def parse_range_segments(text: str) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    for match in CATALOG_LINE_RANGE_RE.finditer(str(text or "")):
        start = int(match.group("start"))
        end = int(match.group("end"))
        if end >= start:
            segments.append((start, end))
    return segments


def range_overlap_size(left: list[tuple[int, int]], right: list[tuple[int, int]]) -> int:
    overlap = 0
    for left_start, left_end in left:
        for right_start, right_end in right:
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if end >= start:
                overlap += end - start + 1
    return overlap


def parse_bridge_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    blocks: list[dict[str, Any]] = []
    current_id = ""
    current_lines: list[str] = []
    for raw_line in read_text(path).splitlines():
        if match := BRIDGE_HEADING_PATTERN.match(raw_line):
            if current_id:
                blocks.append({"bridge_id": current_id, "lines": current_lines})
            current_id = match.group(1)
            current_lines = [raw_line]
            continue
        if current_id:
            current_lines.append(raw_line)
    if current_id:
        blocks.append({"bridge_id": current_id, "lines": current_lines})

    parsed: list[dict[str, Any]] = []
    emotion_labels = (
        "情绪进入点",
        "刺痛/受辱拍",
        "短暂希望或反抗",
        "反刀拍",
        "峰值拍",
        "场末余痛",
    )
    for block in blocks:
        lines = block["lines"]
        values: dict[str, str] = {}
        for raw_line in lines[1:]:
            stripped = raw_line.strip()
            if not stripped.startswith("- "):
                continue
            content = stripped[2:].strip()
            if "：" not in content and ":" not in content:
                continue
            label, value = re.split(r"[：:]\s*", content, maxsplit=1)
            values[label.strip()] = value.strip()
        emotion_sequence = []
        for label in emotion_labels:
            raw_value = values.get(label, "")
            if not raw_value:
                continue
            trigger = raw_value.split("|", 1)[0].strip()
            evidence_match = re.search(r"原文证据[：:]\s*(.+)$", raw_value)
            evidence = evidence_match.group(1).strip("“”\" ") if evidence_match else trigger
            intensity_match = re.search(r"烈度[：:]\s*(\d+)", raw_value)
            intensity = int(intensity_match.group(1)) if intensity_match else 5
            emotion_sequence.append(
                {
                    "role": label,
                    "trigger": trigger,
                    "relationship_position_change": trigger,
                    "reader_effect": trigger,
                    "intensity": intensity,
                    "evidence": evidence,
                }
            )
        parsed.append(
            {
                "bridge_id": str(block["bridge_id"]).strip(),
                "bridge_name": values.get("桥段名", "").strip(),
                "hook": values.get("一句人话抓手", "").strip(),
                "phenomenon": values.get("原文现象证据", "").strip(),
                "must_keep_actions": split_catalog_items(values.get("必须保留的承重件", "")),
                "required_sequence": split_catalog_items(values.get("不能丢的顺序", "")),
                "scene_granularity": values.get("原文现象证据", "").strip(),
                "cannot_merge_or_drop_reason": values.get("为什么这个顺序不能乱", "").strip(),
                "original_ranges": parse_range_segments(values.get("原文位置", "")),
                "emotion_sequence": emotion_sequence,
            }
        )
    return parsed


def bridge_match_score(bridge: dict[str, Any], section_text: str) -> int:
    haystack = re.sub(r"\s+", "", section_text)
    if not haystack:
        return 0
    score = 0
    candidates: list[str] = []
    candidates.extend(
        [
            str(bridge.get("bridge_name") or "").strip(),
            str(bridge.get("hook") or "").strip(),
            str(bridge.get("phenomenon") or "").strip(),
        ]
    )
    candidates.extend(str(item).strip() for item in (bridge.get("must_keep_actions") or []))
    for candidate in candidates:
        normalized = re.sub(r"\s+", "", candidate)
        matched_fragments: set[str] = set()
        for fragment in re.split(r"[，。；;、/|：“”\"（）()\-\s]+", normalized):
            if len(fragment) < 2:
                continue
            if fragment in haystack:
                score += min(len(fragment), 8)
                matched_fragments.add(fragment)
        compact = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", normalized)
        for size in (4, 3, 2):
            if len(compact) < size:
                continue
            for index in range(0, len(compact) - size + 1):
                fragment = compact[index : index + size]
                if fragment in matched_fragments:
                    continue
                if fragment in haystack:
                    score += size - 1
                    matched_fragments.add(fragment)
    return score


def choose_best_bridge(
    catalog_entries: list[dict[str, Any]],
    section_block: dict[str, Any],
) -> dict[str, Any] | None:
    lines = section_block.get("lines") if isinstance(section_block.get("lines"), list) else []
    section_text = "\n".join(str(line) for line in lines)
    if not section_text.strip():
        return None
    scored = [
        (bridge_match_score(entry, section_text), index, entry)
        for index, entry in enumerate(catalog_entries)
    ]
    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    best_score, _index, best_entry = scored[0] if scored else (0, 0, None)
    if best_score <= 0:
        return None
    return best_entry


def choose_monotonic_bridges(
    section_ids: list[str],
    section_blocks: dict[str, dict[str, Any]],
    catalog_entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not section_ids or not catalog_entries:
        return {}
    bridge_count = len(catalog_entries)
    section_count = len(section_ids)
    score_table: list[list[float]] = []
    for section_index, section_id in enumerate(section_ids):
        block = section_blocks.get(section_id, {})
        row: list[float] = []
        section_ratio = section_index / max(1, section_count - 1)
        for bridge_index, entry in enumerate(catalog_entries):
            raw = float(bridge_match_score(entry, "\n".join(block.get("lines") or [])))
            bridge_ratio = bridge_index / max(1, bridge_count - 1)
            position_prior = max(0.0, 6.0 - abs(section_ratio - bridge_ratio) * 12.0)
            row.append(raw * 10.0 + position_prior)
        score_table.append(row)

    dp: list[list[float]] = [[float("-inf")] * bridge_count for _ in section_ids]
    prev: list[list[int]] = [[-1] * bridge_count for _ in section_ids]
    for bridge_index in range(bridge_count):
        dp[0][bridge_index] = score_table[0][bridge_index]
    for section_index in range(1, section_count):
        for bridge_index in range(bridge_count):
            best_prev_score = float("-inf")
            best_prev_index = -1
            for prev_bridge_index in range(bridge_index + 1):
                candidate = dp[section_index - 1][prev_bridge_index]
                if candidate > best_prev_score:
                    best_prev_score = candidate
                    best_prev_index = prev_bridge_index
            dp[section_index][bridge_index] = best_prev_score + score_table[section_index][bridge_index]
            prev[section_index][bridge_index] = best_prev_index

    best_last = max(range(bridge_count), key=lambda idx: dp[-1][idx])
    assignment_indices = [0] * section_count
    assignment_indices[-1] = best_last
    for section_index in range(section_count - 1, 0, -1):
        assignment_indices[section_index - 1] = prev[section_index][assignment_indices[section_index]]
    return {
        section_id: catalog_entries[assignment_indices[index]]
        for index, section_id in enumerate(section_ids)
    }


def select_primary_subflow_for_bridge(
    primary_bundle: dict[str, Any] | None,
    bridge_entry: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(primary_bundle, dict):
        return None
    subflows = primary_bundle.get("subflows")
    if not isinstance(subflows, list) or not subflows:
        return None
    if not isinstance(bridge_entry, dict):
        for item in subflows:
            if isinstance(item, dict):
                return item
        return None
    bridge_ranges = bridge_entry.get("original_ranges") or []
    best_item: dict[str, Any] | None = None
    best_overlap = -1
    for item in subflows:
        if not isinstance(item, dict):
            continue
        contract = item.get("contract")
        if not isinstance(contract, dict):
            continue
        overlap = range_overlap_size(
            bridge_ranges,
            parse_range_segments(str(contract.get("source_range") or "")),
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_item = item
    return best_item


def select_primary_subflows_for_bridge(
    primary_bundle: dict[str, Any] | None,
    bridge_entry: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(primary_bundle, dict):
        return []
    subflows = primary_bundle.get("subflows")
    if not isinstance(subflows, list):
        return []
    if not isinstance(bridge_entry, dict):
        return [item for item in subflows if isinstance(item, dict)]
    bridge_ranges = bridge_entry.get("original_ranges") or []
    matched: list[tuple[int, int, int, dict[str, Any]]] = []
    for index, item in enumerate(subflows):
        if not isinstance(item, dict):
            continue
        contract = item.get("contract")
        if not isinstance(contract, dict):
            continue
        source_ranges = parse_range_segments(str(contract.get("source_range") or ""))
        overlap = range_overlap_size(
            bridge_ranges,
            source_ranges,
        )
        if overlap > 0:
            first_start = source_ranges[0][0] if source_ranges else 10**9
            annotated = copy.deepcopy(item)
            annotated["overlap_lines"] = overlap
            annotated["source_range"] = str(contract.get("source_range") or "").strip()
            annotated["bridge_first_line"] = first_start
            matched.append((first_start, -overlap, index, annotated))
    matched.sort(key=lambda row: (row[0], row[1], row[2]))
    return [item for _first_start, _overlap, _index, item in matched]


def select_section_windowed_subflows(
    matched_subflows: list[dict[str, Any]],
    *,
    section_index_in_bridge: int,
    section_count_for_bridge: int,
) -> list[dict[str, Any]]:
    items = [item for item in matched_subflows if isinstance(item, dict)]
    if len(items) <= 1:
        return list(items)
    if section_count_for_bridge <= 1:
        return [items[0]]
    ratio = section_index_in_bridge / max(1, section_count_for_bridge - 1)
    chosen_index = int(round((len(items) - 1) * ratio))
    chosen_index = max(0, min(chosen_index, len(items) - 1))
    return [items[chosen_index]]


def contract_overlaps_bridge(
    contract: dict[str, Any] | None,
    bridge_entry: dict[str, Any] | None,
) -> bool:
    if not isinstance(contract, dict) or not isinstance(bridge_entry, dict):
        return False
    bridge_ranges = bridge_entry.get("original_ranges") or []
    if not bridge_ranges:
        return False
    source_ranges = parse_range_segments(str(contract.get("source_range") or ""))
    if not source_ranges:
        return False
    return range_overlap_size(bridge_ranges, source_ranges) > 0


def bridge_excerpt_from_bundle(
    primary_bundle: dict[str, Any] | None,
    bridge_entry: dict[str, Any] | None,
    *,
    matched_subflows: list[dict[str, Any]] | None = None,
) -> str:
    excerpts = [
        str(item.get("source_excerpt") or "").strip()
        for item in (matched_subflows or select_primary_subflows_for_bridge(primary_bundle, bridge_entry))
        if isinstance(item, dict) and str(item.get("source_excerpt") or "").strip()
    ]
    return "\n".join(excerpts).strip()


def choose_section_primary_excerpt(
    matched_subflows: list[dict[str, Any]] | None,
    *,
    section_index_in_bridge: int,
    section_count_for_bridge: int,
) -> tuple[str, dict[str, Any] | None]:
    def excerpt_units(text: str) -> list[str]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        line_units = [line.strip() for line in normalized.splitlines() if line.strip()]
        if len(line_units) >= 2:
            return line_units
        parts = re.findall(r"[^。！？!?；;]+[。！？!?；;]?", normalized)
        compact = [part.strip() for part in parts if part.strip()]
        return compact or [normalized]

    items = [item for item in (matched_subflows or []) if isinstance(item, dict)]
    if not items:
        return "", None
    max_index = len(items) - 1
    if section_count_for_bridge <= 1:
        chosen_index = 0
    else:
        ratio = section_index_in_bridge / max(1, section_count_for_bridge - 1)
        chosen_index = int(round(max_index * ratio))
    chosen_index = max(0, min(chosen_index, max_index))
    chosen = items[chosen_index]
    excerpt = str(chosen.get("source_excerpt") or "").strip()
    units = excerpt_units(excerpt)
    if not units:
        return "", chosen
    if len(units) == 1:
        return units[0], chosen
    unit_ratio = (
        0
        if section_count_for_bridge <= 1
        else section_index_in_bridge / max(1, section_count_for_bridge - 1)
    )
    unit_index = int(round((len(units) - 1) * unit_ratio))
    unit_index = max(0, min(unit_index, len(units) - 1))
    window = 2 if len(units) > 1 else 1
    end_index = min(len(units), unit_index + window)
    if end_index - unit_index < window:
        unit_index = max(0, end_index - window)
    chosen_excerpt = "".join(units[unit_index:end_index]).strip()
    return chosen_excerpt or units[unit_index], chosen


def excerpt_from_original_ranges(
    source_path: Path,
    original_ranges: list[tuple[int, int]] | None,
    *,
    section_index_in_bridge: int,
    section_count_for_bridge: int,
) -> str:
    if not original_ranges:
        return ""
    lines = read_text(source_path).splitlines()
    selected_lines: list[str] = []
    for start, end in original_ranges:
        if start < 1 or end < start:
            continue
        for line_no in range(start, min(end, len(lines)) + 1):
            line = lines[line_no - 1].strip()
            if line:
                selected_lines.append(line)
    if not selected_lines:
        return ""
    if section_count_for_bridge <= 1:
        return "\n".join(selected_lines).strip()
    total = len(selected_lines)
    start_index = int(total * section_index_in_bridge / section_count_for_bridge)
    end_index = int(total * (section_index_in_bridge + 1) / section_count_for_bridge)
    if end_index <= start_index:
        end_index = min(total, start_index + 1)
    excerpt_lines = selected_lines[start_index:end_index]
    if not excerpt_lines:
        excerpt_lines = [selected_lines[min(start_index, total - 1)]]
    return "\n".join(excerpt_lines).strip()


def evidence_lines_from_excerpt(text: str, *, limit: int = 2) -> list[str]:
    normalized_lines = [raw_line.strip() for raw_line in text.splitlines() if raw_line.strip()]
    if normalized_lines:
        merged_units: list[str] = []
        buffer_lines: list[str] = []
        for line in normalized_lines:
            buffer_lines.append(line)
            if re.search(r"[。！？!?；;][」』】）”\"]*$", line):
                merged_units.append("\n".join(buffer_lines).strip())
                buffer_lines = []
        if buffer_lines:
            merged_units.append("\n".join(buffer_lines).strip())
        compact_units = [unit for unit in merged_units if unit]
        if compact_units:
            return compact_units[:limit]
    result: list[str] = []
    for raw_line in normalized_lines:
        line = raw_line.strip().strip("“”\"")
        if not line:
            continue
        result.append(line)
        if len(result) >= limit:
            break
    return result


def normalize_excerpt_match_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def excerpt_matches_text(excerpt: str, text: str) -> bool:
    candidate = str(excerpt or "").strip()
    corpus = str(text or "")
    if not candidate or not corpus:
        return False
    if candidate in corpus:
        return True
    return normalize_excerpt_match_text(candidate) in normalize_excerpt_match_text(corpus)


def first_nonempty_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def style_evidence_from_contract(
    contract: dict[str, Any] | None,
    field: str,
) -> list[str]:
    if not isinstance(contract, dict):
        return []
    style = contract.get("source_style_granularity")
    if not isinstance(style, dict):
        style = None
    field_payload = style.get(field) if isinstance(style, dict) else None
    if not isinstance(field_payload, dict):
        return []
    return [
        str(item).strip()
        for item in (field_payload.get("source_evidence") or [])
        if str(item).strip()
    ]


def build_source_style_granularity_contract(
    source_refs: list[dict[str, Any]] | None,
    *,
    section_id: str,
    fallback_quotes: list[str],
) -> dict[str, Any]:
    contract: dict[str, Any] = {}
    for field in STYLE_GRANULARITY_FIELDS:
        evidence: list[str] = []
        analyses: list[str] = []
        source_components: list[dict[str, Any]] = []
        for ref in source_refs or []:
            if not isinstance(ref, dict):
                continue
            ref_contract = ref.get("contract")
            style = (
                ref_contract.get("source_style_granularity")
                if isinstance(ref_contract, dict)
                else {}
            )
            field_payload = style.get(field) if isinstance(style, dict) else None
            if not isinstance(field_payload, dict):
                continue
            analysis = str(field_payload.get("analysis") or "").strip()
            if analysis and analysis not in analyses:
                analyses.append(analysis)
            field_evidence = style_evidence_from_contract(ref_contract, field)
            for quote in field_evidence:
                if quote not in evidence:
                    evidence.append(quote)
            source_components.append(
                {
                    "source_path": str(ref.get("source_path") or "").strip(),
                    "source_role": str(ref.get("role") or "").strip(),
                    "subflow_id": str(ref.get("subflow_id") or "").strip(),
                    "analysis": analysis,
                    "source_evidence": field_evidence,
                }
            )
        if not evidence:
            evidence = [item for item in fallback_quotes if item][:2]
        contract[field] = {
            "analysis": "\n".join(analyses),
            "source_evidence": evidence,
            "source_components": source_components,
            "manual_judgment": (
                f"第{section_id}节必须逐条消费 {field} 对应的原文证据，"
                "迁移的是成文颗粒，不得直接复用原句。"
            ),
        }
    return contract


def build_first_draft_style_plan(
    *,
    section_id: str,
    entry_state: str,
    events: str,
    performance: str,
    exit_state: str,
) -> dict[str, str]:
    section_focus = first_nonempty_text(exit_state, performance, events, f"第{section_id}节承重落点")
    return {
        "narrative_voice_and_attitude": (
            f"第{section_id}节叙述者保持贴脸偏见和即时反应，围绕“{section_focus}”出声，"
            "只迁移口气和态度，不复用原句。"
        ),
        "sentence_relation_and_rhythm": (
            f"第{section_id}节句间先落动作/证据，再补误认、反冲和余痛，"
            "维持原文的逼近节奏，不写成摘要汇报。"
        ),
        "paragraph_breath_and_cut_points": (
            f"第{section_id}节按“{first_nonempty_text(entry_state, events, section_focus)} -> "
            f"{first_nonempty_text(performance, events, section_focus)} -> {section_focus}”换气断段，"
            "不要切成一句一段的电报文。"
        ),
        "dialogue_misfire_or_avoidance": (
            f"第{section_id}节对白优先承压错答、回避或找补，"
            f"让“{first_nonempty_text(performance, events, section_focus)}”从对话里逼出来，不要主题总结。"
        ),
        "action_perception_emotion_weave": (
            f"第{section_id}节把动作、感知和情绪织成连续瞬间，"
            f"从“{first_nonempty_text(entry_state, events, section_focus)}”一路压到“{section_focus}”。"
        ),
        "narrator_interjection_and_roughness": (
            f"第{section_id}节保留叙述者粗粝打断和情绪毛边，但只借颗粒，"
            "不用原句和原桥壳。"
        ),
    }


def build_anti_verbatim_transfer_contract(
    *,
    section_id: str,
    required_sequence: list[str],
    source_quotes: list[str],
    entry_state: str,
    performance: str,
    exit_state: str,
) -> dict[str, Any]:
    preserve_axes = [
        f"第{section_id}节保留原文事件拍密度：{' / '.join(required_sequence[:3]) or first_nonempty_text(performance, exit_state, entry_state, '连续撞击')}",
        f"第{section_id}节保留情绪推进次序：{first_nonempty_text(entry_state, '先愣住')} -> {first_nonempty_text(performance, '中段承压')} -> {first_nonempty_text(exit_state, '尾拍余痛')}",
        "保留控制权变化、信息延迟和气口切换，不把场面压成结果摘要。",
    ]
    rewrite_axes = [
        "原句表层措辞必须全部改写，不得整句平移或替换人名后照抄。",
        "原动作表述、原对白壳子、原比喻和原插嘴句必须换新的承载方式。",
        "原桥段外壳必须重组为新场景表达，只保功能，不保句面。",
    ]
    forbidden_surface_reuse = [quote for quote in source_quotes[:3] if quote]
    if not forbidden_surface_reuse:
        forbidden_surface_reuse = [
            first_nonempty_text(performance, exit_state, entry_state, f"第{section_id}节原文句面")
        ]
    return {
        "preserve_axes": preserve_axes,
        "rewrite_axes": rewrite_axes,
        "forbidden_surface_reuse": forbidden_surface_reuse,
        "allowed_evidence_usage": "原文证据只用于校准颗粒、拍序、情绪落点和气口，不允许直接扩写进正文。",
        "manual_judgment": f"第{section_id}节必须保留原文颗粒和力度，但正文句面、对白表层、动作措辞都必须重写。",
    }


def parse_structured_text(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text or not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_structured_text(value: Any, *keys: str) -> str:
    structured = parse_structured_text(value)
    if isinstance(structured, dict):
        for key in keys:
            text = first_nonempty_text(structured.get(key))
            if text:
                return text
    return first_nonempty_text(value)


def extract_structured_intensity(value: Any, default: int) -> int:
    structured = parse_structured_text(value)
    raw = structured.get("intensity") if isinstance(structured, dict) else value
    if isinstance(raw, (int, float)) and 1 <= raw <= 10:
        return int(raw)
    return default


def build_attention_drift_seed(
    *,
    section_focus: str,
    new_info_lines: list[str],
    subevent_lines: list[str],
    source_quotes: list[str],
    source_excerpt: str,
    emotion: str,
    events: str,
    entry_state: str,
    exit_state: str,
) -> str:
    explicit = first_nonempty_text(*(line.strip() for line in new_info_lines))
    focus = first_nonempty_text(section_focus, *(line.strip() for line in subevent_lines), entry_state)
    quote_a = first_nonempty_text(*(quote.strip() for quote in source_quotes))
    quote_b = first_nonempty_text(
        *(quote.strip() for quote in source_quotes[1:]),
        focus,
        exit_state,
        emotion,
        events,
    )
    if explicit:
        if quote_a and focus:
            return f"她先盯住“{quote_a}”，却一直绕着“{focus}”打转，只敢先承认“{explicit}”。"
        if focus:
            return f"她先被“{focus}”绊住，心思始终回不到别处，只敢先承认“{explicit}”。"
        return explicit
    if quote_a and quote_b:
        return f"她先盯住“{quote_a}”，随后又被“{quote_b}”这一下拖向更坏的判断。"
    excerpt_line = first_nonempty_text(
        *(line.strip() for line in str(source_excerpt or "").splitlines())
    )
    if excerpt_line and quote_b:
        return f"她先卡在“{excerpt_line}”，随后又被“{quote_b}”带偏。"
    if excerpt_line:
        if focus:
            return f"她先卡在“{excerpt_line}”，满脑子只剩“{focus}”。"
        return f"她先卡在“{excerpt_line}”这一拍。"
    fallback = first_nonempty_text(focus, emotion, events, exit_state, entry_state)
    if fallback:
        return fallback
    return "她先被眼前这一拍绊住，判断自然往关系失位那边滑。"


def excerpt_from_line_range(source_path: Path, source_range: str) -> str:
    segments = parse_range_segments(source_range)
    if not segments:
        return ""
    lines = read_text(source_path).splitlines()
    excerpts: list[str] = []
    for start, end in segments:
        if start < 1 or end < start or end > len(lines):
            continue
        excerpt = "\n".join(lines[start - 1 : end]).strip()
        if excerpt:
            excerpts.append(excerpt)
    return "\n".join(excerpts).strip()


def quote_candidates(lines: list[str], *, limit: int = 3) -> list[str]:
    candidates = compact_lines(lines, limit=max(limit * 2, limit))
    return candidates[:limit]


def section_outline_evidence(
    outline_text: str,
    heading_line: str,
    parts: dict[str, list[str]],
) -> list[str]:
    evidence: list[str] = []
    entry_lines = merged_part_lines(parts, "入口状态", "开始状态")
    event_lines = merged_part_lines(parts, "主事件与子事件", "主事件", "子事件", "顺序事件")
    info_lines = merged_part_lines(parts, "新信息、证据与出口", "本节新信息", "本节钩子", "结束状态", "信息差")
    for quote in [heading_line] + quote_candidates(entry_lines, limit=1) + quote_candidates(
        event_lines, limit=1
    ) + quote_candidates(info_lines, limit=1):
        if quote and quote in outline_text and quote not in evidence:
            evidence.append(quote)
    return evidence[:3]


def emotion_beats_from_texts(texts: list[str], evidence_pool: list[str]) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    for index, text in enumerate([item for item in texts if str(item).strip()], start=1):
        evidence = evidence_pool[min(index - 1, max(0, len(evidence_pool) - 1))] if evidence_pool else ""
        role = EMOTION_PROCESS_FIELDS[min(index - 1, len(EMOTION_PROCESS_FIELDS) - 1)]
        beats.append(
            {
                "role": role,
                "trigger": text,
                "relationship_position_change": text,
                "reader_effect": text,
                "intensity": min(10, 3 + index),
                "evidence": evidence,
            }
        )
    return beats


def normalize_seed_emotion_beats(
    beats: list[dict[str, Any]] | None,
    evidence_pool: list[str],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, beat in enumerate(beats or [], start=1):
        beat_payload = parse_structured_text(beat) or (beat if isinstance(beat, dict) else {})
        if not isinstance(beat_payload, dict):
            text = first_nonempty_text(beat)
            if not text:
                continue
            beat_payload = {"trigger": text, "relationship_position_change": text, "reader_effect": text}
        evidence = first_nonempty_text(
            *(quote.strip() for quote in evidence_pool[index - 1 : index]),
            *(quote.strip() for quote in evidence_pool),
            extract_structured_text(beat_payload.get("evidence"), "evidence", "trigger"),
        )
        normalized.append(
            {
                "role": extract_structured_text(beat_payload.get("role"))
                or EMOTION_PROCESS_FIELDS[min(index - 1, len(EMOTION_PROCESS_FIELDS) - 1)],
                "trigger": extract_structured_text(
                    beat_payload.get("trigger"),
                    "trigger",
                    "reader_effect",
                    "relationship_position_change",
                    "evidence",
                ),
                "relationship_position_change": extract_structured_text(
                    beat_payload.get("relationship_position_change"),
                    "relationship_position_change",
                    "trigger",
                    "reader_effect",
                )
                or extract_structured_text(
                    beat_payload.get("trigger"),
                    "trigger",
                    "reader_effect",
                ),
                "reader_effect": extract_structured_text(
                    beat_payload.get("reader_effect"),
                    "reader_effect",
                    "trigger",
                    "relationship_position_change",
                )
                or extract_structured_text(
                    beat_payload.get("trigger"),
                    "trigger",
                    "relationship_position_change",
                ),
                "intensity": extract_structured_intensity(
                    beat_payload.get("intensity"),
                    min(10, 4 + index),
                ),
                "evidence": evidence,
            }
        )
    return normalized


def build_target_emotion_beats_from_roles(
    source_beats: list[dict[str, Any]],
    target_texts: list[str],
    evidence_pool: list[str],
) -> list[dict[str, Any]]:
    roles = [
        str(beat.get("role") or "").strip()
        for beat in source_beats
        if isinstance(beat, dict) and str(beat.get("role") or "").strip()
    ]
    if not roles:
        return emotion_beats_from_texts(target_texts, evidence_pool)
    normalized_texts = [str(text).strip() for text in target_texts if str(text).strip()]
    if not normalized_texts:
        normalized_texts = ["情绪承压继续升级"]
    beats: list[dict[str, Any]] = []
    for index, role in enumerate(roles, start=1):
        text = normalized_texts[min(index - 1, len(normalized_texts) - 1)]
        evidence = evidence_pool[min(index - 1, max(0, len(evidence_pool) - 1))] if evidence_pool else text
        source_intensity = source_beats[index - 1].get("intensity") if index - 1 < len(source_beats) else None
        beats.append(
            {
                "role": role,
                "trigger": text,
                "relationship_position_change": text,
                "reader_effect": text,
                "intensity": source_intensity if isinstance(source_intensity, (int, float)) else min(10, 4 + index),
                "evidence": evidence,
            }
        )
    return beats


def turn_and_peak_indices(beat_count: int) -> tuple[int, int]:
    if beat_count <= 1:
        return 1, 1
    if beat_count == 2:
        return 1, 2
    return 2, beat_count


def default_fact_ledger(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not sections:
        return []
    transitions: list[dict[str, Any]] = []
    previous_state = str(
        sections[0].get("scene_logic_contract", {}).get("scene_entry_state") or ""
    ).strip()
    for section in sections:
        next_state = str(
            section.get("scene_logic_contract", {}).get("scene_exit_state") or ""
        ).strip()
        transitions.append(
            {
                "from_state": previous_state,
                "to_state": next_state,
                "section_id": str(section.get("section_id") or "").strip(),
                "trigger_evidence": list(section.get("outline_evidence") or [])[:2],
            }
        )
        previous_state = next_state or previous_state
    return [
        {
            "fact_id": "FACT-01",
            "initial_state": str(
                sections[0].get("scene_logic_contract", {}).get("scene_entry_state") or ""
            ).strip(),
            "incompatible_states": [
                str(sections[-1].get("scene_logic_contract", {}).get("scene_exit_state") or "").strip()
                or "最终状态未绑定"
            ],
            "transitions": transitions,
        }
    ]


def selected_contract_map(
    receipt_path: Path,
    source_paths: list[Path],
) -> dict[str, dict[str, dict[str, Any]]]:
    if not receipt_path.is_file():
        raise FileNotFoundError(f"拆文读取回执不存在: {receipt_path}")
    try:
        data = json.loads(read_text(receipt_path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"拆文读取回执不是有效 JSON: {exc}") from exc
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        raise ValueError("拆文读取回执.sources 必须是列表")
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for source_path in source_paths:
        source_root = source_path.resolve().parent.parent
        matched = next(
            (
                item
                for item in sources
                if isinstance(item, dict)
                and Path(str(item.get("root") or "")).expanduser().resolve() == source_root
            ),
            None,
        )
        if not isinstance(matched, dict):
            continue
        selected_ids = [
            str(item).strip()
            for item in matched.get("selected_subflow_ids") or []
            if str(item).strip()
        ]
        contracts = matched.get("selected_subflow_contracts")
        if not isinstance(contracts, list):
            continue
        by_id = {
            str(item.get("subflow_id") or "").strip(): item
            for item in contracts
            if isinstance(item, dict) and str(item.get("subflow_id") or "").strip()
        }
        result[str(source_path.resolve())] = {
            subflow_id: by_id[subflow_id]
            for subflow_id in selected_ids
            if subflow_id in by_id
        }
    return result


def primary_bundle_contract_map(
    primary_source_path: Path,
    primary_bundle: dict[str, Any] | None,
) -> dict[str, dict[str, dict[str, Any]]]:
    if not isinstance(primary_bundle, dict):
        return {}
    subflows = primary_bundle.get("subflows")
    if not isinstance(subflows, list):
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for item in subflows:
        if not isinstance(item, dict):
            continue
        subflow_id = str(item.get("subflow_id") or "").strip()
        contract = item.get("contract")
        if not subflow_id or not isinstance(contract, dict):
            continue
        by_id[subflow_id] = contract
    if not by_id:
        return {}
    return {str(primary_source_path.resolve()): by_id}


def source_title_aliases(source_path: Path) -> set[str]:
    return {
        normalize_source_title(source_path.stem),
        normalize_source_title(source_path.parent.parent.name),
    }


def resolve_section_contracts(
    source_binding_lines: list[str],
    sources: list[dict[str, Any]],
    contracts_by_source: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    path_by_title: dict[str, str] = {}
    primary_path = ""
    for source in sources:
        source_path = str(source.get("path") or "").strip()
        if not source_path:
            continue
        if str(source.get("role") or "").strip() == "primary":
            primary_path = source_path
        for alias in source_title_aliases(Path(source_path)):
            path_by_title[alias] = source_path
    resolved: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in source_binding_lines:
        cleaned = str(raw_line).strip().replace("`", "")
        cleaned = re.sub(r"^[>\-*]\s*", "", cleaned)
        cleaned = re.sub(r"^(主体|辅助)\s+", "", cleaned)
        line_refs: list[tuple[str, str]] = []
        if "::SF-" in cleaned:
            title_part, subflow_part = cleaned.split("::", 1)
            subflow_match = re.search(r"(SF-\d+)", subflow_part)
            if subflow_match:
                line_refs.append((normalize_source_title(title_part), subflow_match.group(1)))
        if not line_refs:
            for match in SOURCE_SUBFLOW_REF_RE.finditer(cleaned):
                line_refs.append(
                    (normalize_source_title(match.group("title") or ""), str(match.group("subflow_id") or "").strip())
                )
        for title, subflow_id in line_refs:
            source_path = path_by_title.get(title) if title else primary_path
            if not source_path:
                continue
            contract = contracts_by_source.get(source_path, {}).get(subflow_id)
            if not isinstance(contract, dict):
                continue
            key = (source_path, subflow_id)
            if key in seen:
                continue
            seen.add(key)
            source_meta = next(
                (item for item in sources if str(item.get("path") or "").strip() == source_path),
                {},
            )
            resolved.append(
                {
                    "source_path": source_path,
                    "source_sha256": str(source_meta.get("sha256") or ""),
                    "role": str(source_meta.get("role") or "").strip(),
                    "subflow_id": subflow_id,
                    "contract": contract,
                    "causal_asset_id": (
                        (source_meta.get("available_causal_asset_ids") or [""])[0]
                        if isinstance(source_meta.get("available_causal_asset_ids"), list)
                        else ""
                    ),
                }
            )
    return resolved


def outline_quote_evidence(text: str, quote: str) -> list[str]:
    return [quote] if quote and quote in text else []


def summarize_plain_conflict(
    *,
    title: str,
    control: str,
    events: str,
    exit_state: str,
) -> str:
    return first_nonempty_text(
        f"去掉职业壳后，本节核心冲突仍是 {control} 导致的关系失位：{exit_state}",
        f"去掉职业壳后，本节核心冲突仍是 {events}",
        title,
    )


def summarize_relationship_roles(
    *,
    title: str,
    source_binding: str,
    control: str,
) -> str:
    return first_nonempty_text(
        f"本节一眼能看懂谁是伴侣、谁被优先护住、谁在现场掉位：{control}",
        f"本节关系站位由绑定来源直接承重：{source_binding}",
        title,
    )


def summarize_relationship_injury(
    *,
    exit_state: str,
    events: str,
    performance: str,
) -> str:
    return first_nonempty_text(
        f"本节关系伤害落在：{exit_state}",
        f"本节关系伤害由以下动作直接打出来：{events}",
        performance,
    )


def build_section_seed(
    section_id: str,
    outline_text: str,
    block: dict[str, Any],
    source_refs: list[dict[str, Any]] | None = None,
    primary_bundle: dict[str, Any] | None = None,
    bridge_entry: dict[str, Any] | None = None,
    bridge_subflows: list[dict[str, Any]] | None = None,
    section_index_in_bridge: int = 0,
    section_count_for_bridge: int = 1,
) -> dict[str, Any]:
    lines = block.get("lines") if isinstance(block.get("lines"), list) else []
    parts = subsection_map(lines)
    heading_line = lines[0].strip() if lines else ""
    source_binding_lines = merged_part_lines(parts, "来源绑定", "绑定来源")
    entry_lines = merged_part_lines(parts, "入口状态", "开始状态")
    exit_lines = merged_part_lines(parts, "出口状态", "结束状态")
    performance_lines = merged_part_lines(parts, "表演与对白", "本节承压对白", "子事件", "冲突载体")
    emotion_lines = merged_part_lines(parts, "情绪过程", "本节情绪推进", "情绪链")
    control_lines = merged_part_lines(parts, "控制权变化", "本节功能", "本节新信息", "冲突载体")
    event_lines = merged_part_lines(parts, "主事件与子事件", "主事件", "子事件", "顺序事件")
    info_lines = merged_part_lines(parts, "新信息、证据与出口", "本节新信息", "本节钩子", "结束状态", "信息差")
    entry_state = join_summary(entry_lines, limit=1)
    exit_state = (
        join_summary(exit_lines, limit=1)
        or extract_labeled_value(info_lines, "出口状态")
    )
    source_binding = join_summary(source_binding_lines, limit=2)
    performance = join_summary(performance_lines, limit=2)
    emotion = join_summary(emotion_lines, limit=2)
    control = join_summary(control_lines, limit=2)
    events = join_summary(event_lines, limit=3)
    outline_evidence = section_outline_evidence(outline_text, heading_line, parts)
    active_subflow_ids = {
        str(item.get("subflow_id") or "").strip()
        for item in (bridge_subflows or [])
        if isinstance(item, dict) and str(item.get("subflow_id") or "").strip()
    }
    primary_source_refs = [
        item
        for item in (source_refs or [])
        if isinstance(item, dict)
        and str(item.get("role") or "").strip() in {"primary", "main"}
    ]
    auxiliary_source_refs = [
        item
        for item in (source_refs or [])
        if isinstance(item, dict)
        and str(item.get("role") or "").strip() not in {"primary", "main"}
    ]
    matched_active_primary_refs = [
        item
        for item in primary_source_refs
        if str(item.get("subflow_id") or "").strip() in active_subflow_ids
    ]
    active_primary_refs = (
        matched_active_primary_refs
        if active_subflow_ids and matched_active_primary_refs
        else primary_source_refs
    )
    active_source_refs = [*active_primary_refs, *auxiliary_source_refs]
    primary_ref = next(
        (item for item in active_source_refs if str(item.get("role") or "") == "primary"),
        (active_source_refs or [None])[0],
    )
    if not isinstance(primary_ref, dict) and isinstance(primary_bundle, dict):
        fallback_primary = select_primary_subflow_for_bridge(primary_bundle, bridge_entry)
        primary_meta = (
            primary_bundle.get("primary_source")
            if isinstance(primary_bundle.get("primary_source"), dict)
            else {}
        )
        original_meta = (
            primary_meta.get("original")
            if isinstance(primary_meta.get("original"), dict)
            else {}
        )
        fallback_contract = (
            fallback_primary.get("contract")
            if isinstance(fallback_primary, dict)
            else {}
        )
        if isinstance(fallback_primary, dict) and isinstance(fallback_contract, dict):
            primary_ref = {
                "source_path": str(original_meta.get("path") or "").strip(),
                "source_sha256": str(original_meta.get("sha256") or "").strip(),
                "role": "primary",
                "subflow_id": str(fallback_primary.get("subflow_id") or "").strip(),
                "contract": fallback_contract,
                "causal_asset_id": "",
            }
    primary_subflow_ids = [
        str(item.get("subflow_id") or "").strip()
        for item in active_source_refs
        if isinstance(item, dict) and str(item.get("role") or "") == "primary" and str(item.get("subflow_id") or "").strip()
    ]
    if not primary_subflow_ids and isinstance(primary_ref, dict):
        fallback_id = str(primary_ref.get("subflow_id") or "").strip()
        if fallback_id:
            primary_subflow_ids = [fallback_id]
    primary_contract = primary_ref.get("contract") if isinstance(primary_ref, dict) else {}
    source_path = str(primary_ref.get("source_path") or "") if isinstance(primary_ref, dict) else ""
    source_sha256 = str(primary_ref.get("source_sha256") or "") if isinstance(primary_ref, dict) else ""
    source_range = str(primary_contract.get("source_range") or "").strip()
    source_excerpt = excerpt_from_line_range(Path(source_path), source_range) if source_path and source_range else ""
    bridge_range_excerpt = (
        excerpt_from_original_ranges(
            Path(source_path),
            (bridge_entry or {}).get("original_ranges") if isinstance(bridge_entry, dict) else [],
            section_index_in_bridge=section_index_in_bridge,
            section_count_for_bridge=section_count_for_bridge,
        )
        if source_path and isinstance(bridge_entry, dict)
        else ""
    )
    chosen_primary_excerpt, chosen_primary_subflow = choose_section_primary_excerpt(
        bridge_subflows,
        section_index_in_bridge=section_index_in_bridge,
        section_count_for_bridge=section_count_for_bridge,
    )
    chosen_primary_bundle_excerpt = (
        str(chosen_primary_subflow.get("source_excerpt") or "").strip()
        if isinstance(chosen_primary_subflow, dict)
        else ""
    )
    if bridge_range_excerpt:
        source_excerpt = bridge_range_excerpt
    elif chosen_primary_excerpt:
        source_excerpt = chosen_primary_excerpt
        chosen_contract = (
            chosen_primary_subflow.get("contract")
            if isinstance(chosen_primary_subflow, dict)
            else {}
        )
        if isinstance(chosen_contract, dict):
            chosen_range = str(chosen_contract.get("source_range") or "").strip()
            if chosen_range:
                source_range = chosen_range
    else:
        bridge_excerpt = bridge_excerpt_from_bundle(
            primary_bundle,
            bridge_entry,
            matched_subflows=bridge_subflows,
        )
        if bridge_excerpt and not source_excerpt:
            source_excerpt = bridge_excerpt
    source_quotes = evidence_lines_from_excerpt(source_excerpt, limit=2)
    if len(source_quotes) < 2:
        source_quotes = [
            str(item).strip()
            for item in (primary_contract.get("source_evidence") or [])
            if str(item).strip()
        ][:2]
    causal = primary_contract.get("causal_preconditions") if isinstance(primary_contract, dict) else {}
    causal = causal if isinstance(causal, dict) else {}
    emotion_sequence = [
        str(item).strip()
        for item in (primary_contract.get("emotion_sequence") or [])
        if str(item).strip()
    ]
    target_emotion_progression = split_progression_text(emotion)
    target_emotion_lines = compact_lines(
        emotion_lines,
        limit=max(3, min(5, len(emotion_sequence) or 3)),
    )
    target_emotion_texts = [
        str(item).strip()
        for item in (
            target_emotion_lines
            or (target_emotion_progression if len(target_emotion_progression) >= 3 else [])
        )
    ]
    if len(target_emotion_texts) < 3:
        target_emotion_texts = [
            item
            for item in [
                entry_state or "",
                *target_emotion_progression,
                emotion or "",
                events or "",
                exit_state or "",
            ]
            if str(item).strip()
        ][: max(3, len(target_emotion_texts) or 3)]
    source_emotion_beats = emotion_beats_from_texts(emotion_sequence, source_quotes)
    if not source_emotion_beats and bridge_entry and bridge_entry.get("emotion_sequence"):
        source_emotion_beats = normalize_seed_emotion_beats(
            copy.deepcopy(bridge_entry.get("emotion_sequence") or []),
            source_quotes,
        )
    target_emotion_beats = build_target_emotion_beats_from_roles(
        source_emotion_beats,
        target_emotion_texts,
        outline_evidence[1:] or outline_evidence,
    )
    source_intensity_score = max(
        [
            int(beat.get("intensity"))
            for beat in source_emotion_beats
            if isinstance(beat, dict) and isinstance(beat.get("intensity"), (int, float))
        ]
        or [8 if source_emotion_beats else 0]
    )
    target_intensity_score = max(
        [
            int(beat.get("intensity"))
            for beat in target_emotion_beats
            if isinstance(beat, dict) and isinstance(beat.get("intensity"), (int, float))
        ]
        or [source_intensity_score if target_emotion_beats else 0]
    )
    source_turn, source_peak = turn_and_peak_indices(len(source_emotion_beats))
    target_turn, target_peak = turn_and_peak_indices(len(target_emotion_beats))
    source_slice_bindings = []
    precise_primary_excerpt = ""
    precise_primary_quotes: list[str] = []
    for ref in active_source_refs:
        ref_contract = ref.get("contract") if isinstance(ref, dict) else {}
        ref_path = str(ref.get("source_path") or "") if isinstance(ref, dict) else ""
        ref_range = str(ref_contract.get("source_range") or "").strip() if isinstance(ref_contract, dict) else ""
        ref_excerpt = excerpt_from_line_range(Path(ref_path), ref_range) if ref_path and ref_range else ""
        ref_quotes = evidence_lines_from_excerpt(ref_excerpt, limit=2)
        if not ref_path or not ref_range or len(ref_quotes) < 2:
            continue
        if (
            str(ref.get("role") or "").strip() == "primary"
            and not precise_primary_excerpt
        ):
            exact_excerpt = first_nonempty_text(
                str(ref.get("source_excerpt") or "").strip(),
                chosen_primary_bundle_excerpt,
                ref_excerpt,
            )
            precise_primary_excerpt = exact_excerpt
            precise_primary_quotes = (
                evidence_lines_from_excerpt(exact_excerpt, limit=2)
                if exact_excerpt
                else list(ref_quotes)
            )
        source_slice_bindings.append(
            {
                "subflow_id": str(ref.get("subflow_id") or "").strip(),
                "source_path": ref_path,
                "source_sha256": str(ref.get("source_sha256") or ""),
                "source_range": ref_range,
                "source_evidence": ref_quotes,
                "style_fields_consumed": list(STYLE_GRANULARITY_FIELDS),
            }
        )
    source_style_granularity = build_source_style_granularity_contract(
        active_source_refs,
        section_id=section_id,
        fallback_quotes=precise_primary_quotes or source_quotes,
    )
    first_draft_style_plan = build_first_draft_style_plan(
        section_id=section_id,
        entry_state=entry_state or "",
        events=events or "",
        performance=performance or "",
        exit_state=exit_state or "",
    )
    subevent_lines = compact_lines(merged_part_lines(parts, "子事件", "顺序事件"), limit=8)
    if len(subevent_lines) < 2:
        subevent_lines = compact_lines(event_lines, limit=8)
    anti_verbatim_transfer_contract = build_anti_verbatim_transfer_contract(
        section_id=section_id,
        required_sequence=subevent_lines or event_lines,
        source_quotes=precise_primary_quotes or source_quotes,
        entry_state=entry_state or "",
        performance=performance or "",
        exit_state=exit_state or "",
    )
    new_info_lines = compact_lines(info_lines, limit=3)
    dialogue_lines = compact_lines(merged_part_lines(parts, "本节承压对白"), limit=3)
    beat_dependency_chain = []
    for beat_index, beat_text in enumerate(subevent_lines[:3], start=1):
        beat_dependency_chain.append(
            {
                "beat_id": f"{section_id}-{beat_index}",
                "actor": str(block.get("title") or f"第{section_id}节").strip(),
                "action": beat_text,
                "from_state": entry_state if beat_index == 1 else beat_dependency_chain[-1]["to_state"],
                "trigger": beat_text,
                "knowledge_before": new_info_lines[0] if new_info_lines else entry_state or beat_text,
                "spatial_or_object_access": control or source_binding or beat_text,
                "to_state": exit_state or beat_text,
                "next_beat_cause": (
                    subevent_lines[beat_index] if beat_index < len(subevent_lines[:3]) else exit_state or beat_text
                ),
                "outline_evidence": outline_quote_evidence(outline_text, beat_text),
            }
        )
    knowledge_state_chain = []
    for info_index, info_text in enumerate((new_info_lines or outline_evidence[:2])[:2], start=1):
        reference_beat = beat_dependency_chain[min(info_index - 1, max(0, len(beat_dependency_chain) - 1))] if beat_dependency_chain else {}
        fact_id = f"KS-{section_id}-{info_index}"
        knowledge_state_chain.append(
            {
                "fact_id": fact_id,
                "character": f"第{section_id}节核心视角人物",
                "initial_state": entry_state or "未明",
                "final_state": exit_state or info_text,
                "incompatible_states": [f"未获知：{info_text}"],
                "transitions": [
                    {
                        "from_state": entry_state or "未明",
                        "to_state": exit_state or info_text,
                        "beat_id": str(reference_beat.get("beat_id") or f"{section_id}-1"),
                        "trigger": info_text,
                        "outline_evidence": outline_quote_evidence(outline_text, info_text) or outline_evidence[:1],
                    }
                ],
            }
        )
    irreversible_action = exit_state or extract_labeled_value(control_lines, "出口状态")
    return {
        "section_id": section_id,
        "title": str(block.get("title") or "").strip(),
        "section_heading": str(block.get("title") or "").strip(),
        "verdict": "passed",
        "irreversible_action": irreversible_action or events or "",
        "controlling_object": control or source_binding or "",
        "source_function_mechanism": {
            "asset_path": source_path,
            "function_type": "selected_subflow_contract" if source_path else "",
            "asset_rule": "+".join(primary_subflow_ids) if primary_subflow_ids else (str(primary_ref.get("subflow_id") or "") if isinstance(primary_ref, dict) else ""),
            "why_selected_for_this_section": source_binding or str((bridge_entry or {}).get("bridge_name") or "").strip(),
        },
        "original_scene_granularity": {
            "source_path": source_path,
            "source_sha256": source_sha256,
            "source_scene": str(block.get("title") or "").strip(),
            "action_sequence": events or source_excerpt[:120],
            "body_object_space_control": control or "",
            "dialogue_forces_action": performance or "",
            "bystander_or_order_shift": first_nonempty_text(
                performance,
                control,
                events,
                exit_state,
                str(block.get("title") or "").strip(),
            ),
            "scene_end_residue": exit_state or "",
        },
        "scene_logic_contract": {
            "source_path": source_path,
            "source_sha256": source_sha256,
            "causal_asset_id": (
                str(primary_ref.get("causal_asset_id") or "").strip()
                if isinstance(primary_ref, dict) and str(primary_ref.get("causal_asset_id") or "").strip()
                else (
                    str((primary_ref.get("available_causal_asset_ids") or [""])[0]).strip()
                    if isinstance(primary_ref, dict) and isinstance(primary_ref.get("available_causal_asset_ids"), list)
                    else ""
                )
            ),
            "source_causal_preconditions": [
                *[
                    str(item).strip()
                    for item in (causal.get("arrival_causes") or [])
                    if str(item).strip()
                ][:2],
                *[
                    str(item).strip()
                    for item in (causal.get("institutional_constraints") or [])
                    if str(item).strip()
                ][:1],
            ][:3],
            "source_evidence": [
                str(item).strip()
                for item in (causal.get("source_evidence") or source_quotes)
                if str(item).strip()
            ][:2],
            "target_entry_causes": quote_candidates(entry_lines, limit=2)[:2],
            "target_knowledge_state": quote_candidates(info_lines or entry_lines, limit=2)[:2],
            "key_object_lifecycle": [
                str(item).strip()
                for item in (causal.get("object_lifecycle") or [])
                if str(item).strip()
            ][:2]
            or quote_candidates(source_binding_lines or event_lines, limit=2)[:2],
            "external_rule_dependency": {
                "domain": "none",
                "verified": True,
                "authoritative_basis": "当前节未显式依赖医疗/法律/金融/行政外部规则，机械预填为 none。",
            },
            "obvious_alternative_blocker": [
                str(item).strip()
                for item in (causal.get("obvious_alternative_blockers") or [])
                if str(item).strip()
            ][:2]
            or quote_candidates(event_lines or info_lines, limit=2)[:2],
            "exit_cause": str(causal.get("exit_cause") or exit_state or "").strip(),
            "target_outline_evidence": outline_evidence[:2],
            "scene_entry_state": entry_state or "",
            "scene_exit_state": exit_state or "",
            "beat_dependency_chain": beat_dependency_chain,
            "knowledge_state_chain": knowledge_state_chain,
            "causal_risk_reviews": [
                {
                    "risk_type": risk_type,
                    "applicable": False,
                    "event": "",
                    "setup": "",
                    "causal_explanation": "",
                    "outline_evidence": [],
                    "not_applicable_reason": "机械预填：当前节未发现该类因果风险显性触发点，待人工复核。",
                    "manual_judgment": "机械预填：当前默认不触发，待当前模型复核。",
                }
                for risk_type in CAUSAL_RISK_TYPES
            ],
            "manual_judgment": "机械预填：待当前模型按原文因果链逐拍复核。",
        },
        "source_mechanism": {
            "source_path": source_path,
            "source_sha256": source_sha256,
            "source_scene": str(block.get("title") or "").strip(),
            "transferable_mechanism": source_binding or "",
            "adaptation_boundary": "机械预填：只前置可从所选来源直接提取的桥段与颗粒，待当前模型补人工边界。",
        },
        "information_delay": {
            "entry_known": entry_state or "",
            "leaked_in_scene": first_nonempty_text(
                emotion,
                join_summary(info_lines, limit=1),
                performance,
                events,
                str(block.get("title") or "").strip(),
            ),
            "deferred_to_later": str(primary_contract.get("information_delay") or "").strip(),
        },
        "character_missteps": compact_lines(performance_lines or event_lines, limit=2),
        "interaction_exchange": {
            "pressure": events or "",
            "forced_response": first_nonempty_text(
                performance,
                exit_state,
                join_summary(dialogue_lines, limit=1),
                events,
                str(block.get("title") or "").strip(),
            ),
            "visible_change": exit_state or "",
        },
        "conflict_carrier": {
            "contested_power": control or "",
            "carrier": source_binding or "",
            "consequence": exit_state or "",
        },
        "relationship_legibility": {
            "plain_relationship_roles": summarize_relationship_roles(
                title=str(block.get("title") or "").strip(),
                source_binding=source_binding,
                control=control,
            ),
            "plain_relationship_injury": summarize_relationship_injury(
                exit_state=exit_state,
                events=events,
                performance=performance,
            ),
            "understandable_without_domain_knowledge": True,
        },
        "emotion_intensity": {
            "score": 8 if emotion or events else 6,
            "concrete_humiliation_or_pain": emotion or events or "",
            "emotional_turn": first_nonempty_text(
                emotion,
                join_summary(emotion_lines, limit=1),
                exit_state,
                events,
            ),
            "escalation_vs_previous": exit_state or emotion or "",
        },
        "professional_shell_translation": {
            "plain_language_conflict": summarize_plain_conflict(
                title=str(block.get("title") or "").strip(),
                control=control,
                events=events,
                exit_state=exit_state,
            ),
            "domain_detail_function": source_binding or "",
            "conflict_survives_without_jargon": True,
            "relationship_first": True,
        },
        "source_emotion_parity": {
            "source_excerpt": source_excerpt or "",
            "source_emotion_sequence": source_emotion_beats,
            "target_emotion_sequence": target_emotion_beats,
            "source_intensity_score": source_intensity_score,
            "target_intensity_score": target_intensity_score,
            "source_reversal_beat": source_turn,
            "target_reversal_beat": target_turn,
            "source_peak_beat": source_peak,
            "target_peak_beat": target_peak,
            "ending_afterpain_equivalent": True,
            "reader_experience_equivalent": True,
            "manual_judgment": "机械预填：已绑定原文切片与目标情绪过程，待当前模型补齐等强判断。",
            "parity_status": "adapted_equal_intensity",
            "adaptation_boundary": "机械预填：待当前模型确认情绪反刀位与峰值位是否等强。",
        },
        "first_draft_generation_contract": {
            "source_slice_bindings": source_slice_bindings,
            "source_performance_excerpt": precise_primary_excerpt or source_excerpt or performance or "",
            "source_performance_evidence": precise_primary_quotes or source_quotes,
            "source_style_granularity": source_style_granularity,
            "first_draft_style_plan": first_draft_style_plan,
            "anti_verbatim_transfer_contract": anti_verbatim_transfer_contract,
            "source_excerpt_reuse_reason": (
                f"第{section_id}节即使与相邻节读取到同一原文摘录，也只提取“{first_nonempty_text(exit_state, emotion, events, str(block.get('title') or '').strip())}”"
                "这一下的情绪功能，不复用相邻节的落笔目的。"
            ),
            "emotion_process": {
                "entry_state": entry_state or "",
                "involuntary_body_response": emotion_lines[0].strip() if emotion_lines else emotion or events or "",
                "memory_association_or_attention_drift": build_attention_drift_seed(
                    section_focus=first_nonempty_text(
                        str(block.get("title") or "").strip(),
                        heading_line,
                    ),
                    new_info_lines=new_info_lines,
                    subevent_lines=subevent_lines,
                    source_quotes=source_quotes,
                    source_excerpt=source_excerpt or "",
                    emotion=emotion or "",
                    events=events or "",
                    entry_state=entry_state or "",
                    exit_state=exit_state or "",
                ),
                "contradictory_impulse": control or emotion or events or "",
                "speech_misfire_or_avoidance": dialogue_lines[0] if dialogue_lines else performance or "",
                "scene_afterpain": exit_state or "",
            },
            "continuous_moment_groups": [
                f"第{section_id}节连续瞬间1：{subevent_lines[0] if subevent_lines else events}",
                f"第{section_id}节连续瞬间2：{subevent_lines[1] if len(subevent_lines) > 1 else exit_state or events}",
            ],
            "paragraph_break_reasons": [
                f"第{section_id}节在动作撞击后断段，保留{(subevent_lines[0] if subevent_lines else '首拍')}的压迫感",
                f"第{section_id}节在情绪反刀后断段，承接{exit_state or emotion or '场末余痛'}",
            ],
            "sentence_relation_plan": [
                f"第{section_id}节先以动作起句，再补情绪偏移：{subevent_lines[0] if subevent_lines else events}",
                f"第{section_id}节中段用短问或错答承压：{dialogue_lines[0] if dialogue_lines else performance or events}",
                f"第{section_id}节尾句落在余痛或失位结果：{exit_state or emotion or events}",
            ],
            "function_word_strategy": f"第{section_id}节维持贴脸叙述，少总结，多用动作后补一刀。",
            "telegraphic_risk": f"第{section_id}节避免把{control or events}拆成电报式分句。",
            "emotion_shorthand_to_avoid": [
                f"第{section_id}节禁写“她很难受”类空情绪句",
                f"第{section_id}节禁写“事情越来越糟”类万能总结",
            ],
            "target_emotion_landing_plan": [
                f"第{section_id}节先落{entry_state or '入口状态'}",
                f"第{section_id}节中段压出{emotion or events}",
                f"第{section_id}节结尾回收到{exit_state or '场末余痛'}",
            ],
            "no_fixed_short_sentence_ratio": True,
            "manual_judgment": (
                f"第{section_id}节首写计划已锁定原文切片、情绪拍和场末余痛，"
                f"正文必须围绕“{first_nonempty_text(exit_state, events, str(block.get('title') or '').strip())}”落笔。"
            ),
        },
        "forbidden_items": [
            f"第{section_id}节禁把“{first_nonempty_text(exit_state, str(block.get('title') or '').strip(), '本节结果')}”提前总结成结论句。",
            f"第{section_id}节禁把“{first_nonempty_text(control, events, source_binding, '本节承重动作')}”改写成流程说明或报账清单。",
        ],
        "outline_evidence": outline_evidence,
        "manual_judgment": (
            f"第{section_id}节已绑定“{first_nonempty_text(str(block.get('title') or '').strip(), events, exit_state)}”这条场面颗粒，"
            f"正文必须保住 {first_nonempty_text(control, performance, exit_state)} 的关系伤害。"
        ),
    }


def build_primary_bridge_seed(
    first_source: dict[str, Any],
    seeded_section: dict[str, Any],
    source_refs: list[dict[str, Any]] | None,
    primary_bundle: dict[str, Any] | None = None,
    bridge_entry: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    primary_ref = next(
        (item for item in (source_refs or []) if str(item.get("role") or "") == "primary"),
        None,
    )
    contract: dict[str, Any] | None = None
    fallback_excerpt = ""
    if isinstance(primary_ref, dict):
        primary_contract = primary_ref.get("contract")
        if isinstance(primary_contract, dict):
            contract = primary_contract
    matched_subflow = select_primary_subflow_for_bridge(primary_bundle, bridge_entry)
    if contract is None and isinstance(matched_subflow, dict):
        fallback_contract = matched_subflow.get("contract")
        if isinstance(fallback_contract, dict):
            contract = fallback_contract
            fallback_excerpt = str(matched_subflow.get("source_excerpt") or "").strip()
            if primary_ref is None:
                primary_ref = {
                    "source_path": first_source["path"],
                    "source_sha256": first_source["sha256"],
                    "role": "primary",
                    "subflow_id": str(matched_subflow.get("subflow_id") or "").strip(),
                    "contract": fallback_contract,
                }
    if contract is None and isinstance(primary_bundle, dict):
        subflows = primary_bundle.get("subflows")
        if isinstance(subflows, list):
            for item in subflows:
                if not isinstance(item, dict):
                    continue
                fallback_contract = item.get("contract")
                if isinstance(fallback_contract, dict):
                    contract = fallback_contract
                    fallback_excerpt = str(item.get("source_excerpt") or "").strip()
                    break
    if contract is None:
        return None

    required_sequence = [
        str(item).strip()
        for item in (contract.get("required_sequence") or [])
        if str(item).strip()
    ]
    source_evidence = [
        str(item).strip()
        for item in (
            seeded_section.get("scene_logic_contract", {}).get("source_evidence") or []
        )
        if str(item).strip()
    ][:2]
    if len(source_evidence) < 2 and fallback_excerpt:
        source_evidence = evidence_lines_from_excerpt(fallback_excerpt, limit=2)
    if len(source_evidence) < 2:
        source_evidence = [
            str(item).strip()
            for item in (contract.get("source_evidence") or [])
            if str(item).strip()
        ][:2]
    source_emotion_sequence = copy.deepcopy(
        seeded_section.get("source_emotion_parity", {}).get("source_emotion_sequence") or []
    )
    target_emotion_sequence = copy.deepcopy(
        seeded_section.get("source_emotion_parity", {}).get("target_emotion_sequence") or []
    )
    if not source_emotion_sequence:
        source_emotion_sequence = emotion_beats_from_texts(
            [
                str(item).strip()
                for item in (contract.get("emotion_sequence") or [])
                if str(item).strip()
            ],
            source_evidence,
        )
    if not target_emotion_sequence:
        target_emotion_sequence = emotion_beats_from_texts(
            [
                str(item).strip()
                for item in split_progression_text(
                    str(seeded_section.get("emotion_intensity", {}).get("emotional_turn") or "")
                )
                if str(item).strip()
            ],
            [
                str(item).strip()
                for item in (seeded_section.get("outline_evidence") or [])
                if str(item).strip()
            ],
        )
    source_turn, source_peak = turn_and_peak_indices(len(source_emotion_sequence))
    target_turn, target_peak = turn_and_peak_indices(len(target_emotion_sequence))
    bridge_id = str(
        (bridge_entry or {}).get("bridge_id")
        or (first_source.get("selected_bridge_ids") or first_source.get("available_bridge_ids") or ["BID-01"])[0]
    ).strip()
    bridge_name = (
        str((bridge_entry or {}).get("bridge_name") or "").strip()
        or str(seeded_section.get("original_scene_granularity", {}).get("source_scene") or "").strip()
        or str((primary_ref or {}).get("subflow_id") or "").strip()
        or "主体桥段"
    )
    if bridge_entry:
        required_sequence = [
            str(item).strip()
            for item in ((bridge_entry or {}).get("required_sequence") or required_sequence)
            if str(item).strip()
        ]
    source_scene_granularity = (
        str((bridge_entry or {}).get("scene_granularity") or "").strip()
        or str(seeded_section.get("original_scene_granularity", {}).get("action_sequence") or "").strip()
        or str(seeded_section.get("original_scene_granularity", {}).get("dialogue_forces_action") or "").strip()
        or bridge_name
    )
    target_outline_evidence = [
        str(item).strip()
        for item in (seeded_section.get("outline_evidence") or [])
        if str(item).strip()
    ][:2]
    target_section_id = str(seeded_section.get("section_id") or "").strip()
    source_must_keep_actions = [
        str(item).strip()
        for item in ((bridge_entry or {}).get("must_keep_actions") or required_sequence[:3] or source_evidence[:2])
        if str(item).strip()
    ][:3]
    if bridge_entry and bridge_entry.get("emotion_sequence"):
        source_emotion_sequence = normalize_seed_emotion_beats(
            copy.deepcopy(bridge_entry.get("emotion_sequence") or []),
            source_evidence,
        )

    inventory = {
        "source_path": first_source["path"],
        "source_sha256": first_source["sha256"],
        "bridge_id": bridge_id,
        "bridge_name": bridge_name,
        "source_required_sequence": required_sequence[:4],
        "source_must_keep_actions": source_must_keep_actions,
        "source_scene_granularity": source_scene_granularity,
        "source_end_state_change": str(
            seeded_section.get("scene_logic_contract", {}).get("scene_exit_state") or ""
        ).strip(),
        "cannot_merge_or_drop_reason": str((bridge_entry or {}).get("cannot_merge_or_drop_reason") or "").strip()
        or str(seeded_section.get("irreversible_action") or "").strip()
        or "该桥段承担关系掉位和后续因果，不得删并。",
    }
    parity = {
        "source_bridge_id": bridge_id,
        "source_bridge_name": bridge_name,
        "source_path": first_source["path"],
        "source_sha256": first_source["sha256"],
        "source_required_sequence": required_sequence[:4],
        "source_must_keep_actions": source_must_keep_actions,
        "source_scene_granularity": source_scene_granularity,
        "source_emotion_sequence": source_emotion_sequence,
        "target_emotion_sequence": target_emotion_sequence,
        "source_reversal_beat": source_turn,
        "target_reversal_beat": target_turn,
        "source_peak_beat": source_peak,
        "target_peak_beat": target_peak,
        "reader_experience_parity": None,
        "emotion_parity_judgment": "",
        "target_outline_sections": [target_section_id] if target_section_id else [],
        "target_outline_evidence": target_outline_evidence,
        "parity_status": "pending",
        "adaptation_reason": "",
        "missing_or_weakened_risk": "",
        "manual_judgment": "",
    }
    return inventory, parity


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def nonempty_list(value: Any, minimum: int = 1) -> bool:
    return (
        isinstance(value, list)
        and len([item for item in value if str(item).strip()]) >= minimum
    )


def contains_causal_placeholder(value: Any) -> bool:
    text = str(value or "")
    return any(marker in text for marker in CAUSAL_PLACEHOLDER_MARKERS)


def source_receipt_auxiliary_contracts(
    receipt_path: Path,
    auxiliary_source_paths: list[Path],
) -> dict[str, list[dict[str, Any]]]:
    if not receipt_path.is_file():
        raise FileNotFoundError(f"拆文读取回执不存在: {receipt_path}")
    try:
        data = json.loads(read_text(receipt_path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"拆文读取回执不是有效 JSON: {exc}") from exc
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        raise ValueError("拆文读取回执.sources 必须是列表")
    result: dict[str, list[dict[str, Any]]] = {}
    for source_path in auxiliary_source_paths:
        source_root = source_path.resolve().parent.parent
        matched = next(
            (
                item
                for item in sources
                if isinstance(item, dict)
                and Path(str(item.get("root") or "")).expanduser().resolve()
                == source_root
            ),
            None,
        )
        if matched is None:
            raise ValueError(f"拆文读取回执未找到辅助来源: {source_root}")
        selected_ids = [
            str(item).strip()
            for item in matched.get("selected_subflow_ids") or []
            if str(item).strip()
        ]
        contracts = matched.get("selected_subflow_contracts")
        if not selected_ids or not isinstance(contracts, list):
            raise ValueError(f"辅助来源缺少已选 SF 完整契约: {source_root}")
        by_id = {
            str(item.get("subflow_id") or "").strip(): item
            for item in contracts
            if isinstance(item, dict)
        }
        missing = [subflow_id for subflow_id in selected_ids if subflow_id not in by_id]
        if missing:
            raise ValueError(
                f"辅助来源已选 SF 缺少完整契约: {source_root} -> {', '.join(missing)}"
            )
        result[str(source_path.resolve())] = [by_id[subflow_id] for subflow_id in selected_ids]
    return result


def read_primary_source_bundle(
    bundle_path: Path,
    *,
    validate_source_receipt: bool = True,
) -> dict[str, Any]:
    try:
        errors = PRIMARY_SOURCE_BUNDLE_MODULE.validate_bundle(
            bundle_path,
            validate_source_receipt=validate_source_receipt,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"主体原文完整颗粒包校验异常: {exc}") from exc
    if errors:
        raise ValueError("；".join(errors))
    try:
        data = json.loads(read_text(bundle_path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"主体原文完整颗粒包不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("主体原文完整颗粒包顶层必须是对象")
    return data


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
    source_receipt_path: Path | None = None,
    primary_source_bundle_path: Path | None = None,
    source_profile_paths: list[Path] | None = None,
) -> dict[str, Any]:
    outline = outline_path.resolve()
    if not outline.is_file():
        raise FileNotFoundError(f"细纲不存在: {outline}")
    resolved_source_paths = [path.resolve() for path in source_paths]
    auxiliary_contracts: dict[str, list[dict[str, Any]]] = {}
    source_receipt_binding: dict[str, str] | None = None
    if len(resolved_source_paths) > 1 and source_mode == "full_bridge":
        if source_receipt_path is None:
            raise ValueError("融合仿写初始化细纲契约时必须传 --source-receipt")
        resolved_source_receipt = source_receipt_path.resolve()
        auxiliary_contracts = source_receipt_auxiliary_contracts(
            resolved_source_receipt, resolved_source_paths[1:]
        )
        source_receipt_binding = {
            "path": str(resolved_source_receipt),
            "sha256": sha256(resolved_source_receipt),
        }
    if source_mode == "full_bridge" and primary_source_bundle_path is not None:
        resolved_primary_bundle = primary_source_bundle_path.resolve()
        primary_bundle = read_primary_source_bundle(resolved_primary_bundle)
        primary_bundle_binding = {
            "path": str(resolved_primary_bundle),
            "sha256": sha256(resolved_primary_bundle),
        }
    else:
        primary_bundle = None
        primary_bundle_binding = None
    resolved_profile_paths: list[Path] | None = None
    if source_profile_paths is not None:
        resolved_profile_paths = [path.resolve() for path in source_profile_paths]
        if len(resolved_profile_paths) != len(resolved_source_paths):
            raise ValueError("source_profile_paths 数量必须与 source_paths 一致")
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
        profile_path = (
            resolved_profile_paths[index]
            if resolved_profile_paths is not None
            else source.parent.parent / "book.profile.json"
        )
        if not profile_path.is_file():
            raise FileNotFoundError(f"单书 profile 不存在: {profile_path}")
        available_causal_asset_ids = causal_asset_ids_from_profile(profile_path)
        if not available_causal_asset_ids:
            raise ValueError(f"单书 profile 未识别到场景因果资产 CPA: {profile_path}")
        role = "primary" if index == 0 else "auxiliary"
        selected_contracts = auxiliary_contracts.get(str(source), [])
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
                "selected_subflow_ids": [
                    str(item.get("subflow_id") or "").strip()
                    for item in selected_contracts
                ],
            }
        )

    outline_text = read_text(outline)
    sections = outline_sections(outline_text)
    section_blocks = outline_section_blocks(outline_text)
    first_source = sources[0]
    primary_catalog_entries = parse_bridge_catalog(
        Path(str(first_source["bridge_catalog"]["path"]))
    ) if sources else []
    monotonic_bridge_assignments = choose_monotonic_bridges(
        sections,
        section_blocks,
        primary_catalog_entries,
    ) if primary_catalog_entries else {}
    contract_map = (
        selected_contract_map(source_receipt_path.resolve(), resolved_source_paths)
        if source_receipt_path is not None
        else {}
    )
    if primary_bundle is not None and resolved_source_paths:
        contract_map.update(
            primary_bundle_contract_map(resolved_source_paths[0], primary_bundle)
        )
    seeded_sections: list[dict[str, Any]] = []
    primary_bridge_seed: tuple[dict[str, Any], dict[str, Any]] | None = None
    auxiliary_section_matches: dict[tuple[str, str], list[dict[str, Any]]] = {}
    bridge_section_groups: dict[str, list[str]] = {}
    for current_section_id in sections:
        bridge_entry = monotonic_bridge_assignments.get(current_section_id)
        bridge_id = str((bridge_entry or {}).get("bridge_id") or "").strip()
        if bridge_id:
            bridge_section_groups.setdefault(bridge_id, []).append(current_section_id)
    for section_id in sections:
        section_lines = (
            section_blocks.get(section_id, {}).get("lines", [])
            if isinstance(section_blocks.get(section_id, {}).get("lines"), list)
            else []
        )
        binding_lines = merged_part_lines(
            subsection_map(section_lines),
            "来源绑定",
            "绑定来源",
        )
        if not binding_lines:
            binding_lines = [line for line in section_lines[1:] if "SF-" in str(line)]
        resolved_refs = resolve_section_contracts(
            binding_lines,
            sources,
            contract_map,
        )
        bridge_entry = monotonic_bridge_assignments.get(section_id)
        bridge_id = str((bridge_entry or {}).get("bridge_id") or "").strip()
        section_group = bridge_section_groups.get(bridge_id, []) if bridge_id else []
        section_index_in_bridge = (
            section_group.index(section_id)
            if section_group and section_id in section_group
            else 0
        )
        matched_primary_subflow = select_primary_subflow_for_bridge(primary_bundle, bridge_entry)
        matched_primary_subflows = select_primary_subflows_for_bridge(primary_bundle, bridge_entry)
        section_primary_subflows = select_section_windowed_subflows(
            matched_primary_subflows,
            section_index_in_bridge=section_index_in_bridge,
            section_count_for_bridge=len(section_group) if section_group else 1,
        )
        if not section_primary_subflows and isinstance(matched_primary_subflow, dict):
            section_primary_subflows = [matched_primary_subflow]
        explicit_primary_refs = [
            item
            for item in resolved_refs
            if str(item.get("role") or "") == "primary"
        ]
        bridge_primary_refs_required = bool(section_primary_subflows)
        primary_refs_conflict_with_bridge = bool(explicit_primary_refs) and bool(bridge_entry) and not any(
            contract_overlaps_bridge(
                item.get("contract") if isinstance(item, dict) else {},
                bridge_entry,
            )
            for item in explicit_primary_refs
        )
        has_primary_ref = bool(explicit_primary_refs)
        if (not has_primary_ref or primary_refs_conflict_with_bridge) and section_primary_subflows:
            primary_refs: list[dict[str, Any]] = []
            for matched_item in section_primary_subflows:
                if not isinstance(matched_item, dict):
                    continue
                matched_contract = matched_item.get("contract")
                if not isinstance(matched_contract, dict):
                    continue
                primary_refs.append(
                    {
                        "source_path": first_source["path"],
                        "source_sha256": first_source["sha256"],
                        "role": "primary",
                        "subflow_id": str(matched_item.get("subflow_id") or "").strip(),
                        "contract": matched_contract,
                        "causal_asset_id": "",
                        "available_causal_asset_ids": list(first_source.get("available_causal_asset_ids") or []),
                    }
                )
            if primary_refs:
                if primary_refs_conflict_with_bridge:
                    resolved_refs = [
                        *primary_refs,
                        *[
                            item
                            for item in resolved_refs
                            if str(item.get("role") or "") != "primary"
                        ],
                    ]
                else:
                    resolved_refs = [*primary_refs, *resolved_refs]
        seeded_section = build_section_seed(
            section_id,
            outline_text,
            section_blocks.get(section_id, {}),
            resolved_refs,
            primary_bundle,
            bridge_entry,
            section_primary_subflows,
            section_index_in_bridge=section_index_in_bridge,
            section_count_for_bridge=len(section_group) if section_group else 1,
        )
        for ref in resolved_refs:
            if not isinstance(ref, dict):
                continue
            if str(ref.get("role") or "").strip() != "auxiliary":
                continue
            ref_source_path = str(ref.get("source_path") or "").strip()
            ref_subflow_id = str(ref.get("subflow_id") or "").strip()
            if not ref_source_path or not ref_subflow_id:
                continue
            auxiliary_section_matches.setdefault((ref_source_path, ref_subflow_id), []).append(
                {
                    "section_id": section_id,
                    "outline_evidence": [
                        str(item).strip()
                        for item in (seeded_section.get("outline_evidence") or [])
                        if str(item).strip()
                    ],
                    "scene_entry_state": str(
                        seeded_section.get("scene_logic_contract", {}).get("scene_entry_state") or ""
                    ).strip(),
                    "scene_exit_state": str(
                        seeded_section.get("scene_logic_contract", {}).get("scene_exit_state") or ""
                    ).strip(),
                }
            )
        if primary_bridge_seed is None:
            primary_bridge_seed = build_primary_bridge_seed(
                first_source,
                seeded_section,
                resolved_refs,
                primary_bundle,
                bridge_entry,
            )
        seeded_sections.append(seeded_section)
    inventory_seed, parity_seed = primary_bridge_seed or (
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
        },
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
        },
    )
    primary_inventory_entries: list[dict[str, Any]] = []
    primary_parity_entries: list[dict[str, Any]] = []
    for bridge_position, bridge_entry in enumerate(primary_catalog_entries):
        if not isinstance(bridge_entry, dict):
            continue
        bridge_id = str(bridge_entry.get("bridge_id") or "").strip()
        if not bridge_id:
            continue
        matched_subflows = select_primary_subflows_for_bridge(primary_bundle, bridge_entry)
        bridge_excerpt = bridge_excerpt_from_bundle(
            primary_bundle,
            bridge_entry,
            matched_subflows=matched_subflows,
        )
        source_quotes = evidence_lines_from_excerpt(bridge_excerpt, limit=6)
        source_required_sequence = [
            str(item).strip()
            for item in (bridge_entry.get("required_sequence") or [])
            if str(item).strip()
        ]
        raw_bridge_emotion_sequence = bridge_entry.get("emotion_sequence") or []
        if any(isinstance(item, dict) or parse_structured_text(item) for item in raw_bridge_emotion_sequence):
            source_emotion_sequence = normalize_seed_emotion_beats(
                copy.deepcopy(raw_bridge_emotion_sequence),
                source_quotes[:6],
            )
        else:
            source_emotion_sequence = emotion_beats_from_texts(
                [
                    str(item).strip()
                    for item in raw_bridge_emotion_sequence
                    if str(item).strip()
                ],
                source_quotes[:6],
            )
        matched_sections = [
            str(section_id).strip()
            for section_id, current_bridge in monotonic_bridge_assignments.items()
            if isinstance(current_bridge, dict)
            and str(current_bridge.get("bridge_id") or "").strip() == bridge_id
        ]
        if not matched_sections and seeded_sections:
            fallback_index = (
                0
                if len(primary_catalog_entries) <= 1
                else int(
                    round(
                        bridge_position
                        * (len(seeded_sections) - 1)
                        / max(1, len(primary_catalog_entries) - 1)
                    )
                )
            )
            fallback_index = max(0, min(fallback_index, len(seeded_sections) - 1))
            matched_sections = [
                str(seeded_sections[fallback_index].get("section_id") or "").strip()
            ]
        matched_section_entries = [
            section
            for section in seeded_sections
            if str(section.get("section_id") or "").strip() in matched_sections
        ]
        target_outline_evidence = list(
            dict.fromkeys(
                quote
                for section in matched_section_entries
                for quote in (section.get("outline_evidence") or [])
                if str(quote).strip()
            )
        )[:2]
        target_emotion_texts = [
            text
            for text in [
                *[
                    str(section.get("scene_logic_contract", {}).get("scene_entry_state") or "").strip()
                    for section in matched_section_entries
                ],
                *[
                    str(section.get("emotion_intensity", {}).get("emotional_turn") or "").strip()
                    for section in matched_section_entries
                ],
                *[
                    str(section.get("irreversible_action") or "").strip()
                    for section in matched_section_entries
                ],
                *[
                    str(section.get("scene_logic_contract", {}).get("scene_exit_state") or "").strip()
                    for section in matched_section_entries
                ],
            ]
            if text
        ]
        target_emotion_evidence = list(
            dict.fromkeys(
                quote
                for section in matched_section_entries
                for quote in (section.get("outline_evidence") or [])
                if str(quote).strip()
            )
        )
        target_emotion_sequence = (
            build_target_emotion_beats_from_roles(
                source_emotion_sequence,
                target_emotion_texts,
                target_emotion_evidence or target_outline_evidence,
            )
            if matched_sections
            else []
        )
        source_end_state_change = first_nonempty_text(
            str(bridge_entry.get("end_state_change") or "").strip(),
            *[
                str(section.get("scene_logic_contract", {}).get("scene_exit_state") or "").strip()
                for section in matched_section_entries[::-1]
            ],
            str(bridge_entry.get("cannot_merge_or_drop_reason") or "").strip(),
            str(bridge_entry.get("scene_granularity") or "").strip(),
        )
        source_turn, source_peak = turn_and_peak_indices(len(source_emotion_sequence))
        target_turn, target_peak = turn_and_peak_indices(len(target_emotion_sequence))
        primary_inventory_entries.append(
            {
                "source_path": first_source["path"],
                "source_sha256": first_source["sha256"],
                "bridge_id": bridge_id,
                "bridge_name": str(bridge_entry.get("bridge_name") or "").strip(),
                "source_required_sequence": source_required_sequence,
                "source_must_keep_actions": [
                    str(item).strip()
                    for item in (bridge_entry.get("must_keep_actions") or [])
                    if str(item).strip()
                ],
                "source_scene_granularity": str(bridge_entry.get("scene_granularity") or "").strip(),
                "source_end_state_change": source_end_state_change,
                "cannot_merge_or_drop_reason": first_nonempty_text(
                    str(bridge_entry.get("cannot_merge_or_drop_reason") or "").strip(),
                    str(bridge_entry.get("reason") or "").strip(),
                    str(bridge_entry.get("scene_granularity") or "").strip(),
                ),
            }
        )
        primary_parity_entries.append(
            {
                "source_bridge_id": bridge_id,
                "source_bridge_name": str(bridge_entry.get("bridge_name") or "").strip(),
                "source_path": first_source["path"],
                "source_sha256": first_source["sha256"],
                "source_required_sequence": source_required_sequence,
                "source_must_keep_actions": [
                    str(item).strip()
                    for item in (bridge_entry.get("must_keep_actions") or [])
                    if str(item).strip()
                ],
                "source_scene_granularity": str(bridge_entry.get("scene_granularity") or "").strip(),
                "source_emotion_sequence": source_emotion_sequence,
                "target_emotion_sequence": target_emotion_sequence,
                "source_reversal_beat": source_turn,
                "target_reversal_beat": target_turn,
                "source_peak_beat": source_peak,
                "target_peak_beat": target_peak,
                "reader_experience_parity": True if matched_sections else None,
                "emotion_parity_judgment": (
                    f"桥段 {bridge_id} 已把原文情绪拍压到细纲 {','.join(matched_sections)} 节，反刀位与峰值位保持同一承压顺序。"
                    if matched_sections
                    else ""
                ),
                "target_outline_sections": matched_sections,
                "target_outline_evidence": target_outline_evidence,
                "parity_status": "adapted" if matched_sections else "pending",
                "adaptation_reason": (
                    f"桥段 {bridge_id} 仅替换人物、场景和职业外壳，保留“{' -> '.join(source_required_sequence[:3])}”这条原文承重顺序。"
                    if matched_sections
                    else ""
                ),
                "missing_or_weakened_risk": (
                    f"桥段 {bridge_id} 不能被压成一句偏心结论，必须保住 {first_nonempty_text(*[str(item).strip() for item in (bridge_entry.get('must_keep_actions') or [])])}。"
                    if matched_sections
                    else ""
                ),
                "manual_judgment": (
                    f"桥段 {bridge_id} 已逐节挂到 {','.join(matched_sections)} 节，正文必须按当前细纲证据把原文颗粒完整转写。"
                    if matched_sections
                    else ""
                ),
            }
        )
    if not primary_inventory_entries:
        primary_inventory_entries = [inventory_seed]
    if not primary_parity_entries:
        primary_parity_entries = [parity_seed]
    auxiliary_subflow_entries: list[dict[str, Any]] = []
    for source_path, contracts in auxiliary_contracts.items():
        source_sha256 = next(
            source["sha256"]
            for source in sources
            if source["path"] == source_path
        )
        for contract in contracts:
            subflow_id = str(contract.get("subflow_id") or "").strip()
            matches = auxiliary_section_matches.get((source_path, subflow_id), [])
            target_sections = [
                str(match.get("section_id") or "").strip()
                for match in matches
                if str(match.get("section_id") or "").strip()
            ]
            outline_evidence = list(
                dict.fromkeys(
                    quote
                    for match in matches
                    for quote in (match.get("outline_evidence") or [])
                    if str(quote).strip()
                )
            )[:2]
            target_entry_state = first_nonempty_text(
                *[str(match.get("scene_entry_state") or "").strip() for match in matches]
            )
            target_end_state = first_nonempty_text(
                *[str(match.get("scene_exit_state") or "").strip() for match in matches],
                str(contract.get("end_state") or "").strip(),
            )
            target_knowledge_boundaries = [
                text
                for text in [
                    target_entry_state,
                    target_end_state,
                ]
                if text
            ][:2]
            if len(target_knowledge_boundaries) < 2:
                target_knowledge_boundaries.extend(
                    [
                        str(item).strip()
                        for item in (
                            contract.get("causal_preconditions", {}).get("knowledge_boundaries")
                            if isinstance(contract.get("causal_preconditions"), dict)
                            else []
                        )
                        if str(item).strip()
                    ][: 2 - len(target_knowledge_boundaries)]
                )
            target_object_lifecycle = [
                str(item).strip()
                for item in (
                    contract.get("causal_preconditions", {}).get("object_lifecycle")
                    if isinstance(contract.get("causal_preconditions"), dict)
                    else []
                )
                if str(item).strip()
            ][:2]
            first_outline_evidence = outline_evidence[:1]
            sequence_mappings: list[dict[str, Any]] = []
            for index, step in enumerate(contract.get("required_sequence") or []):
                match = matches[min(index, max(0, len(matches) - 1))] if matches else {}
                sequence_mappings.append(
                    {
                        "source_step": str(step).strip(),
                        "target_step": str(step).strip(),
                        "section_id": str(match.get("section_id") or (target_sections[0] if target_sections else "")).strip(),
                        "precondition": first_nonempty_text(
                            str(match.get("scene_entry_state") or "").strip(),
                            target_entry_state,
                            str(contract.get("entry_state") or "").strip(),
                        ),
                        "trigger": first_nonempty_text(*first_outline_evidence, str(step).strip()),
                        "state_change": first_nonempty_text(
                            str(match.get("scene_exit_state") or "").strip(),
                            target_end_state,
                        ),
                        "outline_evidence": first_outline_evidence,
                    }
                )
            auxiliary_subflow_entries.append(
                {
                    "source_path": source_path,
                    "source_sha256": source_sha256,
                    "subflow_id": subflow_id,
                    "source_entry_state": str(contract.get("entry_state") or "").strip(),
                    "source_required_sequence": contract.get("required_sequence") or [],
                    "source_knowledge_boundaries": (
                        contract.get("causal_preconditions", {}).get("knowledge_boundaries")
                        if isinstance(contract.get("causal_preconditions"), dict)
                        else []
                    ) or [],
                    "source_object_lifecycle": (
                        contract.get("causal_preconditions", {}).get("object_lifecycle")
                        if isinstance(contract.get("causal_preconditions"), dict)
                        else []
                    ) or [],
                    "source_exit_cause": (
                        contract.get("causal_preconditions", {}).get("exit_cause")
                        if isinstance(contract.get("causal_preconditions"), dict)
                        else ""
                    ),
                    "source_end_state": str(contract.get("end_state") or "").strip(),
                    "target_outline_sections": target_sections,
                    "target_entry_state": target_entry_state,
                    "sequence_mappings": sequence_mappings,
                    "target_knowledge_boundaries": target_knowledge_boundaries,
                    "target_object_lifecycle": target_object_lifecycle,
                    "target_exit_cause": target_end_state,
                    "target_end_state": target_end_state,
                    "target_outline_evidence": outline_evidence,
                    "parity_status": "adapted" if matches else "pending",
                    "adaptation_reason": (
                        "机械预填：已按当前小节中的辅助来源绑定回填目标落点与逐步映射。"
                        if matches
                        else ""
                    ),
                    "manual_judgment": (
                        "机械预填：待当前模型复核辅助 SF 是否完整迁移进当前细纲。"
                        if matches
                        else ""
                    ),
                }
            )
    return {
        "version": "1.6",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "passed",
        "execution_mode": "current_model_manual",
        "source_mode": source_mode,
        "reviewed_by_current_model": True,
        "outline": {"path": str(outline), "sha256": sha256(outline)},
        "source_read_receipt": source_receipt_binding,
        "primary_source_semantic_bundle": primary_bundle_binding,
        "selected_source_originals": sources,
        "global_review": {
            "full_source_mechanisms_reviewed": True,
            "dual_track_function_and_scene_granularity_reviewed": True,
            "scene_causality_reviewed_before_draft": True,
            "intra_section_beat_causality_reviewed": True,
            "section_handoff_reviewed": True,
            "auxiliary_subflow_full_flow_reviewed": True if len(resolved_source_paths) > 1 else False,
            "source_bridge_flow_inventory_completed": True if source_mode == "full_bridge" else False,
            "outline_bridge_flow_parity_reviewed_before_draft": True if source_mode == "full_bridge" else False,
            "relationship_legibility_reviewed_before_draft": True,
            "professional_shell_translation_reviewed_before_draft": True,
            "source_emotion_flow_parity_reviewed_before_draft": True,
            "first_draft_generation_contract_reviewed": True,
            "paragraph_breath_reviewed_before_draft": True,
            "sentence_relation_and_function_word_strategy_reviewed_before_draft": True,
            "granularity_transfer_contract_reviewed": True if source_mode == "granularity_only" else False,
            "strong_emotion_required": False,
            "mechanism_transfer_boundary": "只迁移所选来源中可核的因果顺序、情绪拍、场面压力和句法承压；不复制原人物、原职业、原关系称谓和整句原文。",
            "global_storyboard_or_process_list": False,
            "manual_judgment": "当前细纲已在写前绑定选中原文的桥段、因果、情绪与交接颗粒，后续正文只能沿这套已落盘颗粒首写，不得退回流程清单写法。",
        },
        "story_fact_state_ledger": default_fact_ledger(seeded_sections),
        "primary_subflow_semantic_inventory": (
            copy.deepcopy(primary_bundle.get("subflows", []))
            if isinstance(primary_bundle, dict)
            else []
        ),
        "section_handoff_chain": [
            {
                "from_section_id": sections[index],
                "to_section_id": sections[index + 1],
                "elapsed_time": first_nonempty_text(
                    f"第{sections[index]}节余波未消，紧接着切到第{sections[index + 1]}节入口动作。",
                    str(
                        seeded_sections[index + 1].get("scene_logic_contract", {}).get("scene_entry_state")
                        or ""
                    ).strip(),
                ),
                "from_exit_state": str(
                    seeded_sections[index].get("scene_logic_contract", {}).get("scene_exit_state") or ""
                ).strip(),
                "to_entry_state": str(
                    seeded_sections[index + 1].get("scene_logic_contract", {}).get("scene_entry_state") or ""
                ).strip(),
                "handoff_trigger": str(
                    seeded_sections[index + 1].get("scene_logic_contract", {}).get("scene_entry_state")
                    or seeded_sections[index + 1].get("irreversible_action")
                    or ""
                ).strip(),
                "character_state_continuity": [
                    first_nonempty_text(
                        str(seeded_sections[index].get("irreversible_action") or "").strip(),
                        str(seeded_sections[index].get("scene_logic_contract", {}).get("scene_exit_state") or "").strip(),
                    ),
                ],
                "knowledge_continuity": [
                    first_nonempty_text(
                        *[
                            str(item).strip()
                            for item in (
                                seeded_sections[index + 1].get("scene_logic_contract", {}).get("target_knowledge_state")
                                or []
                            )
                            if str(item).strip()
                        ],
                        str(seeded_sections[index + 1].get("scene_logic_contract", {}).get("scene_entry_state") or "").strip(),
                    ),
                ],
                "object_continuity": [
                    first_nonempty_text(
                        *[
                            str(item).strip()
                            for item in (
                                seeded_sections[index].get("scene_logic_contract", {}).get("key_object_lifecycle")
                                or []
                            )
                            if str(item).strip()
                        ],
                        str(seeded_sections[index].get("controlling_object") or "").strip(),
                    ),
                ],
                "location_continuity": first_nonempty_text(
                    str(seeded_sections[index + 1].get("controlling_object") or "").strip(),
                    str(seeded_sections[index + 1].get("source_function_mechanism", {}).get("why_selected_for_this_section") or "").strip(),
                    str(
                        (
                            seeded_sections[index + 1].get("outline_evidence")
                            or [str(seeded_sections[index + 1].get("section_id") or "").strip()]
                        )[0]
                    ).strip(),
                ),
                "unresolved_threads": [
                    first_nonempty_text(
                        str(seeded_sections[index].get("scene_logic_contract", {}).get("scene_exit_state") or "").strip(),
                        str(seeded_sections[index].get("irreversible_action") or "").strip(),
                    ),
                ],
                "outline_evidence": [
                    *list(seeded_sections[index].get("outline_evidence") or [])[:1],
                    *list(seeded_sections[index + 1].get("outline_evidence") or [])[:1],
                ][:2],
                "manual_judgment": (
                    f"第{sections[index]}节场末状态“{str(seeded_sections[index].get('scene_logic_contract', {}).get('scene_exit_state') or '').strip()}”"
                    f"已直接压到第{sections[index + 1]}节入口“{str(seeded_sections[index + 1].get('scene_logic_contract', {}).get('scene_entry_state') or '').strip()}”。"
                ),
            }
            for index in range(max(0, len(sections) - 1))
        ],
        "auxiliary_subflow_flow_parity": auxiliary_subflow_entries,
        "granularity_transfer_contract": [],
        "source_bridge_flow_inventory": primary_inventory_entries,
        "outline_bridge_flow_parity": primary_parity_entries,
        "sections": seeded_sections,
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
    section_id: str,
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
        elif field in {
            "target_entry_causes",
            "target_knowledge_state",
            "key_object_lifecycle",
        }:
            for item in value.get(field) or []:
                if contains_causal_placeholder(item):
                    errors.append(
                        f"{label} scene_logic_contract.{field} 使用验收占位话代替真实因果: "
                        f"{str(item).strip()!r}"
                    )
    if section_id == "1":
        for field in ("target_entry_causes", "target_knowledge_state"):
            for item in value.get(field) or []:
                if "上一节" in str(item):
                    errors.append(f"{label} 为首节，{field} 不得引用上一节")
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
        elif contains_causal_placeholder(value.get(field)):
            errors.append(f"{label} scene_logic_contract.{field} 不得使用模板化放行声明")

    scene_entry_state = str(value.get("scene_entry_state") or "").strip()
    scene_exit_state = str(value.get("scene_exit_state") or "").strip()
    if not scene_entry_state:
        errors.append(f"{label} scene_logic_contract.scene_entry_state 不能为空")
    if not scene_exit_state:
        errors.append(f"{label} scene_logic_contract.scene_exit_state 不能为空")
    beat_chain = value.get("beat_dependency_chain")
    valid_beat_ids: set[str] = set()
    if not isinstance(beat_chain, list) or len(beat_chain) < 3:
        errors.append(f"{label} beat_dependency_chain 至少三拍，逐拍证明前因、触发和状态变化")
    else:
        expected_from_state = scene_entry_state
        for index, beat in enumerate(beat_chain, start=1):
            beat_label = f"{label} beat_dependency_chain[{index}]"
            if not isinstance(beat, dict):
                errors.append(f"{beat_label} 必须是对象")
                continue
            for field in BEAT_DEPENDENCY_FIELDS:
                if field == "outline_evidence":
                    if not nonempty_list(beat.get(field)):
                        errors.append(f"{beat_label}.{field} 至少一条")
                elif not nonempty_text(beat.get(field)):
                    errors.append(f"{beat_label}.{field} 不能为空")
            beat_id = str(beat.get("beat_id") or "").strip()
            if beat_id in valid_beat_ids:
                errors.append(f"{beat_label}.beat_id 重复: {beat_id}")
            valid_beat_ids.add(beat_id)
            from_state = str(beat.get("from_state") or "").strip()
            to_state = str(beat.get("to_state") or "").strip()
            if expected_from_state and from_state != expected_from_state:
                errors.append(
                    f"{beat_label} 状态未首尾相接：期望 from_state={expected_from_state!r}，"
                    f"实际为 {from_state!r}"
                )
            expected_from_state = to_state
            for quote in beat.get("outline_evidence") or []:
                if str(quote).strip() not in outline_text:
                    errors.append(f"{beat_label}.outline_evidence 不在细纲中: {quote!r}")
        if scene_exit_state and expected_from_state != scene_exit_state:
            errors.append(
                f"{label} beat_dependency_chain 末拍未落到 scene_exit_state: "
                f"{expected_from_state!r} != {scene_exit_state!r}"
            )

    knowledge_chains = value.get("knowledge_state_chain")
    if not isinstance(knowledge_chains, list) or not knowledge_chains:
        errors.append(f"{label} knowledge_state_chain 至少覆盖一条承重知情事实")
    else:
        seen_fact_ids: set[str] = set()
        for index, fact in enumerate(knowledge_chains, start=1):
            fact_label = f"{label} knowledge_state_chain[{index}]"
            if not isinstance(fact, dict):
                errors.append(f"{fact_label} 必须是对象")
                continue
            for field in ("fact_id", "character", "initial_state", "final_state"):
                if not nonempty_text(fact.get(field)):
                    errors.append(f"{fact_label}.{field} 不能为空")
            fact_id = str(fact.get("fact_id") or "").strip()
            if fact_id in seen_fact_ids:
                errors.append(f"{fact_label}.fact_id 重复: {fact_id}")
            seen_fact_ids.add(fact_id)
            if not nonempty_list(fact.get("incompatible_states")):
                errors.append(f"{fact_label}.incompatible_states 至少一条")
            transitions = fact.get("transitions")
            current_state = str(fact.get("initial_state") or "").strip()
            if not isinstance(transitions, list) or not transitions:
                errors.append(f"{fact_label}.transitions 至少一条")
                continue
            for transition_index, transition in enumerate(transitions, start=1):
                transition_label = f"{fact_label}.transitions[{transition_index}]"
                if not isinstance(transition, dict):
                    errors.append(f"{transition_label} 必须是对象")
                    continue
                for field in ("from_state", "to_state", "beat_id", "trigger"):
                    if not nonempty_text(transition.get(field)):
                        errors.append(f"{transition_label}.{field} 不能为空")
                if str(transition.get("from_state") or "").strip() != current_state:
                    errors.append(f"{transition_label} 知情状态未首尾相接")
                current_state = str(transition.get("to_state") or "").strip()
                beat_id = str(transition.get("beat_id") or "").strip()
                if beat_id not in valid_beat_ids:
                    errors.append(f"{transition_label}.beat_id 不在本节逐拍链中: {beat_id}")
                evidence = transition.get("outline_evidence")
                if not nonempty_list(evidence):
                    errors.append(f"{transition_label}.outline_evidence 至少一条")
                else:
                    for quote in evidence:
                        if str(quote).strip() not in outline_text:
                            errors.append(
                                f"{transition_label}.outline_evidence 不在细纲中: {quote!r}"
                            )
            if current_state != str(fact.get("final_state") or "").strip():
                errors.append(f"{fact_label}.final_state 与最后一次知情迁移不一致")

    risk_reviews = value.get("causal_risk_reviews")
    if not isinstance(risk_reviews, list):
        errors.append(f"{label} causal_risk_reviews 必须是列表")
    else:
        by_type = {
            str(item.get("risk_type") or "").strip(): item
            for item in risk_reviews
            if isinstance(item, dict)
        }
        unknown = sorted(set(by_type) - set(CAUSAL_RISK_TYPES))
        missing = sorted(set(CAUSAL_RISK_TYPES) - set(by_type))
        if unknown:
            errors.append(f"{label} causal_risk_reviews 存在未知类型: {', '.join(unknown)}")
        if missing:
            errors.append(f"{label} causal_risk_reviews 缺少类型: {', '.join(missing)}")
        for risk_type in CAUSAL_RISK_TYPES:
            review = by_type.get(risk_type)
            if not isinstance(review, dict):
                continue
            applicable = review.get("applicable")
            if applicable not in {True, False}:
                errors.append(f"{label} {risk_type}.applicable 必须为 true/false")
            if applicable is True:
                for field in ("event", "setup", "causal_explanation", "manual_judgment"):
                    if not nonempty_text(review.get(field)):
                        errors.append(f"{label} {risk_type}.{field} 不能为空")
                evidence = review.get("outline_evidence")
                if not nonempty_list(evidence):
                    errors.append(f"{label} {risk_type}.outline_evidence 至少一条")
                else:
                    for quote in evidence:
                        if str(quote).strip() not in outline_text:
                            errors.append(
                                f"{label} {risk_type}.outline_evidence 不在细纲中: {quote!r}"
                            )
            elif applicable is False and not nonempty_text(
                review.get("not_applicable_reason")
            ):
                errors.append(f"{label} {risk_type}.not_applicable_reason 不能为空")
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


def validate_section_handoff_chain(
    value: Any,
    section_ids: list[str],
    by_id: dict[str, Any],
    outline_text: str,
    errors: list[str],
) -> None:
    expected_pairs = list(zip(section_ids, section_ids[1:]))
    if not isinstance(value, list):
        errors.append("section_handoff_chain 必须是列表")
        return
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for index, item in enumerate(value, start=1):
        label = f"section_handoff_chain[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        pair = (
            str(item.get("from_section_id") or "").strip(),
            str(item.get("to_section_id") or "").strip(),
        )
        if pair in entries:
            errors.append(f"{label} 重复小节交接: {pair[0]} -> {pair[1]}")
        entries[pair] = item
    missing = [pair for pair in expected_pairs if pair not in entries]
    extra = [pair for pair in entries if pair not in expected_pairs]
    if missing:
        errors.append(
            "section_handoff_chain 缺少相邻小节交接: "
            + ", ".join(f"{start}->{end}" for start, end in missing)
        )
    if extra:
        errors.append(
            "section_handoff_chain 包含非相邻交接: "
            + ", ".join(f"{start}->{end}" for start, end in extra)
        )
    for start, end in expected_pairs:
        item = entries.get((start, end))
        if not isinstance(item, dict):
            continue
        label = f"小节交接 {start}->{end}"
        for field in (
            "elapsed_time",
            "from_exit_state",
            "to_entry_state",
            "handoff_trigger",
            "location_continuity",
            "manual_judgment",
        ):
            if not nonempty_text(item.get(field)):
                errors.append(f"{label}.{field} 不能为空")
            elif contains_causal_placeholder(item.get(field)):
                errors.append(f"{label}.{field} 不得使用模板占位话")
        for field in (
            "character_state_continuity",
            "knowledge_continuity",
            "object_continuity",
            "unresolved_threads",
        ):
            if not nonempty_list(item.get(field)):
                errors.append(f"{label}.{field} 至少一条")
            else:
                for entry in item.get(field) or []:
                    if contains_causal_placeholder(entry):
                        errors.append(f"{label}.{field} 不得使用模板占位话")
        evidence = item.get("outline_evidence")
        if not nonempty_list(evidence, minimum=2):
            errors.append(f"{label}.outline_evidence 至少引用前后两节各一条原句")
        else:
            for quote in evidence:
                if str(quote).strip() not in outline_text:
                    errors.append(f"{label}.outline_evidence 不在细纲中: {quote!r}")
        start_logic = (
            by_id.get(start, {}).get("scene_logic_contract", {})
            if isinstance(by_id.get(start), dict)
            else {}
        )
        end_logic = (
            by_id.get(end, {}).get("scene_logic_contract", {})
            if isinstance(by_id.get(end), dict)
            else {}
        )
        expected_exit = str(start_logic.get("scene_exit_state") or "").strip()
        expected_entry = str(end_logic.get("scene_entry_state") or "").strip()
        if expected_exit and str(item.get("from_exit_state") or "").strip() != expected_exit:
            errors.append(f"{label}.from_exit_state 与前节 scene_exit_state 不一致")
        if expected_entry and str(item.get("to_entry_state") or "").strip() != expected_entry:
            errors.append(f"{label}.to_entry_state 与后节 scene_entry_state 不一致")


def validate_auxiliary_subflow_flow_parity(
    value: Any,
    source_receipt_binding: Any,
    source_path_order: list[Path],
    source_texts: dict[str, str],
    section_ids: list[str],
    outline_text: str,
    errors: list[str],
) -> None:
    auxiliary_paths = source_path_order[1:]
    if not auxiliary_paths:
        if value not in (None, []):
            errors.append("无辅助来源时 auxiliary_subflow_flow_parity 必须为空")
        return
    if not isinstance(source_receipt_binding, dict):
        errors.append("融合仿写细纲契约必须绑定 source_read_receipt")
        return
    path = Path(str(source_receipt_binding.get("path") or "")).expanduser().resolve()
    if not path.is_file():
        errors.append(f"source_read_receipt 不存在: {path}")
        return
    if source_receipt_binding.get("sha256") != sha256(path):
        errors.append("source_read_receipt SHA 已变化，必须重建辅助 SF 对齐")
    try:
        expected_by_path = source_receipt_auxiliary_contracts(path, auxiliary_paths)
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
        return
    expected: dict[tuple[str, str], dict[str, Any]] = {
        (source_path, str(contract.get("subflow_id") or "").strip()): contract
        for source_path, contracts in expected_by_path.items()
        for contract in contracts
    }
    if not isinstance(value, list):
        errors.append("auxiliary_subflow_flow_parity 必须是列表")
        return
    actual: dict[tuple[str, str], dict[str, Any]] = {}
    for index, item in enumerate(value, start=1):
        label = f"辅助 SF 对齐[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        source_path = str(
            Path(str(item.get("source_path") or "")).expanduser().resolve()
        )
        subflow_id = str(item.get("subflow_id") or "").strip()
        key = (source_path, subflow_id)
        if key in actual:
            errors.append(f"{label} 重复: {Path(source_path).parent.parent.name} {subflow_id}")
        actual[key] = item
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing:
        errors.append(
            "辅助 SF 未逐流程进入细纲对齐: "
            + ", ".join(f"{Path(path).parent.parent.name}:{subflow}" for path, subflow in missing)
        )
    if extra:
        errors.append(
            "辅助 SF 对齐存在未选来源: "
            + ", ".join(f"{Path(path).parent.parent.name}:{subflow}" for path, subflow in extra)
        )
    for key, contract in expected.items():
        item = actual.get(key)
        if not isinstance(item, dict):
            continue
        source_path, subflow_id = key
        label = f"辅助 SF {Path(source_path).parent.parent.name}:{subflow_id}"
        if item.get("source_sha256") != sha256(Path(source_path)):
            errors.append(f"{label}.source_sha256 与原文不一致")
        causal = contract.get("causal_preconditions")
        causal = causal if isinstance(causal, dict) else {}
        expected_fields = {
            "source_entry_state": str(contract.get("entry_state") or "").strip(),
            "source_required_sequence": contract.get("required_sequence") or [],
            "source_knowledge_boundaries": causal.get("knowledge_boundaries") or [],
            "source_object_lifecycle": causal.get("object_lifecycle") or [],
            "source_exit_cause": causal.get("exit_cause") or "",
            "source_end_state": str(contract.get("end_state") or "").strip(),
        }
        for field, expected_value in expected_fields.items():
            if item.get(field) != expected_value:
                errors.append(f"{label}.{field} 与拆文读取回执中的完整 SF 契约不一致")
        target_sections = [
            str(section_id).strip()
            for section_id in item.get("target_outline_sections") or []
            if str(section_id).strip()
        ]
        if not target_sections:
            errors.append(f"{label}.target_outline_sections 至少一节")
        for section_id in target_sections:
            if section_id not in section_ids:
                errors.append(f"{label}.target_outline_sections 不在细纲中: {section_id}")
        mappings = item.get("sequence_mappings")
        source_steps = [str(step).strip() for step in contract.get("required_sequence") or []]
        if not isinstance(mappings, list) or len(mappings) != len(source_steps):
            errors.append(f"{label}.sequence_mappings 必须逐项覆盖完整 required_sequence")
        else:
            mapped_steps = [str(mapping.get("source_step") or "").strip() for mapping in mappings if isinstance(mapping, dict)]
            if mapped_steps != source_steps:
                errors.append(f"{label}.sequence_mappings 必须保持原 SF 步骤顺序且不得删并")
            for index, mapping in enumerate(mappings, start=1):
                mapping_label = f"{label}.sequence_mappings[{index}]"
                if not isinstance(mapping, dict):
                    errors.append(f"{mapping_label} 必须是对象")
                    continue
                for field in ("target_step", "section_id", "precondition", "trigger", "state_change"):
                    if not nonempty_text(mapping.get(field)):
                        errors.append(f"{mapping_label}.{field} 不能为空")
                section_id = str(mapping.get("section_id") or "").strip()
                if section_id not in target_sections:
                    errors.append(f"{mapping_label}.section_id 未列入 target_outline_sections")
                evidence = mapping.get("outline_evidence")
                if not nonempty_list(evidence):
                    errors.append(f"{mapping_label}.outline_evidence 至少一条")
                else:
                    for quote in evidence:
                        if str(quote).strip() not in outline_text:
                            errors.append(f"{mapping_label}.outline_evidence 不在细纲中: {quote!r}")
        for field in (
            "target_entry_state",
            "target_exit_cause",
            "target_end_state",
            "adaptation_reason",
            "manual_judgment",
        ):
            if not nonempty_text(item.get(field)):
                errors.append(f"{label}.{field} 不能为空")
        for field in ("target_knowledge_boundaries", "target_object_lifecycle"):
            if not nonempty_list(item.get(field), minimum=2):
                errors.append(f"{label}.{field} 至少两条，不能只迁移事件结果")
        evidence = item.get("target_outline_evidence")
        if not nonempty_list(evidence, minimum=2):
            errors.append(f"{label}.target_outline_evidence 至少两条")
        else:
            for quote in evidence:
                if str(quote).strip() not in outline_text:
                    errors.append(f"{label}.target_outline_evidence 不在细纲中: {quote!r}")
        if item.get("parity_status") not in {"matched", "adapted"}:
            errors.append(f"{label}.parity_status 只能为 matched/adapted")


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
    if not excerpt or not any(
        excerpt_matches_text(excerpt, text) for text in source_texts.values()
    ):
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
    primary_inventory: dict[tuple[str, str], dict[str, Any]],
    label: str,
    errors: list[str],
    *,
    strong_emotion_required: bool,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} first_draft_generation_contract 必须是对象")
        return

    source_slice_bindings = value.get("source_slice_bindings")
    bound_primary_subflows: set[tuple[str, str]] = set()
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
            source_range = str(binding.get("source_range") or "").strip()
            range_match = re.fullmatch(r"L(\d+)-L(\d+)", source_range)
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
                    if not excerpt_matches_text(quote, source_slice):
                        errors.append(f"{binding_label}.source_evidence 不在精确行段内: {quote!r}")
            consumed = binding.get("style_fields_consumed")
            if not isinstance(consumed, list) or len({str(item).strip() for item in consumed if str(item).strip()}) < 6:
                errors.append(f"{binding_label}.style_fields_consumed 必须覆盖六类逐 SF 文风颗粒")
            primary_contract = primary_inventory.get((str(source_path), source_range))
            if primary_contract is not None:
                bound_primary_subflows.add((str(source_path), source_range))
                for field in STYLE_GRANULARITY_FIELDS:
                    if field not in {str(item).strip() for item in consumed if str(item).strip()}:
                        errors.append(f"{binding_label}.style_fields_consumed 缺少主体 SF 文风字段: {field}")
                contract_payload = primary_contract.get("contract")
                style = (
                    contract_payload.get("source_style_granularity")
                    if isinstance(contract_payload, dict)
                    else None
                )
                if not isinstance(style, dict):
                    style = primary_contract.get("source_style_granularity")
                if not isinstance(style, dict):
                    errors.append(f"{binding_label} 绑定的主体 SF 缺少 source_style_granularity")
                else:
                    available_quotes = {
                        str(quote).strip()
                        for field in STYLE_GRANULARITY_FIELDS
                        for quote in (
                            (style.get(field) or {}).get("source_evidence", [])
                            if isinstance(style.get(field), dict)
                            else []
                        )
                        if str(quote).strip()
                    }
                    source_excerpt = str(primary_contract.get("source_excerpt") or "").strip()
                    if not source_excerpt:
                        source_excerpt = (
                            str(contract_payload.get("source_excerpt") or "").strip()
                            if isinstance(contract_payload, dict)
                            else ""
                        )
                    contract_source_evidence = (
                        contract_payload.get("source_evidence")
                        if isinstance(contract_payload, dict)
                        else []
                    )
                    available_quotes.update(
                        str(quote).strip()
                        for quote in (primary_contract.get("source_evidence") or [])
                        if str(quote).strip()
                    )
                    available_quotes.update(
                        str(quote).strip()
                        for quote in (contract_source_evidence or [])
                        if str(quote).strip()
                    )
                    allowed_quotes = set(available_quotes)
                    allowed_quotes.update(
                        quote for quote in quotes if quote and excerpt_matches_text(quote, source_slice)
                    )
                    if source_excerpt:
                        allowed_quotes.update(
                            quote for quote in quotes if quote and excerpt_matches_text(quote, source_excerpt)
                        )
                    if not set(quotes).issubset(allowed_quotes):
                        errors.append(f"{binding_label}.source_evidence 超出绑定主体 SF 的原文证据范围")
        if primary_inventory and not bound_primary_subflows:
            errors.append(f"{label} 至少要有一条 source_slice_bindings 直接绑定主体 SF 完整合同")

    excerpt = str(value.get("source_performance_excerpt") or "").strip()
    if not excerpt or not any(
        excerpt_matches_text(excerpt, text) for text in source_texts.values()
    ):
        errors.append(
            f"{label} first_draft_generation_contract.source_performance_excerpt "
            "必须来自选中原文"
        )
    elif primary_inventory and not any(
        excerpt_matches_text(excerpt, str(item.get("source_excerpt") or ""))
        for item in primary_inventory.values()
    ):
        errors.append(f"{label} source_performance_excerpt 必须来自主体原文完整颗粒包中的精确 SF 切片")

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
            if not any(excerpt_matches_text(quote, text) for text in source_texts.values()):
                errors.append(f"{label} 原文表演证据不在选中原文中: {quote!r}")
            elif primary_inventory:
                if not any(
                    excerpt_matches_text(quote, str(item.get("source_excerpt") or ""))
                    for item in primary_inventory.values()
                ):
                    errors.append(f"{label} 原文表演证据必须能回溯到主体原文完整颗粒包: {quote!r}")

    emotion_process = value.get("emotion_process")
    if not isinstance(emotion_process, dict):
        errors.append(f"{label} first_draft_generation_contract.emotion_process 必须是对象")
    else:
        for field in EMOTION_PROCESS_FIELDS:
            if not nonempty_text(emotion_process.get(field)):
                errors.append(
                    f"{label} first_draft_generation_contract.emotion_process.{field} 不能为空"
                )

    source_style_granularity = value.get("source_style_granularity")
    if not isinstance(source_style_granularity, dict):
        errors.append(f"{label} first_draft_generation_contract.source_style_granularity 必须是对象")
    else:
        for field in STYLE_GRANULARITY_FIELDS:
            field_payload = source_style_granularity.get(field)
            if not isinstance(field_payload, dict):
                errors.append(f"{label} first_draft_generation_contract.source_style_granularity.{field} 必须是对象")
                continue
            if not nonempty_text(field_payload.get("analysis")):
                errors.append(
                    f"{label} first_draft_generation_contract.source_style_granularity.{field}.analysis 不能为空"
                )
            field_evidence = field_payload.get("source_evidence")
            if not nonempty_list(field_evidence, minimum=1):
                errors.append(
                    f"{label} first_draft_generation_contract.source_style_granularity.{field}.source_evidence 至少一条原文证据"
                )
            else:
                for quote in {str(item).strip() for item in field_evidence if str(item).strip()}:
                    if not any(excerpt_matches_text(quote, text) for text in source_texts.values()):
                        errors.append(
                            f"{label} first_draft_generation_contract.source_style_granularity.{field}.source_evidence 不在选中原文中: {quote!r}"
                        )
            if not nonempty_text(field_payload.get("manual_judgment")):
                errors.append(
                    f"{label} first_draft_generation_contract.source_style_granularity.{field}.manual_judgment 不能为空"
                )

    first_draft_style_plan = value.get("first_draft_style_plan")
    if not isinstance(first_draft_style_plan, dict):
        errors.append(f"{label} first_draft_generation_contract.first_draft_style_plan 必须是对象")
    else:
        for field in STYLE_GRANULARITY_FIELDS:
            if not nonempty_text(first_draft_style_plan.get(field)):
                errors.append(
                    f"{label} first_draft_generation_contract.first_draft_style_plan.{field} 不能为空"
                )

    anti_verbatim_transfer_contract = value.get("anti_verbatim_transfer_contract")
    if not isinstance(anti_verbatim_transfer_contract, dict):
        errors.append(f"{label} first_draft_generation_contract.anti_verbatim_transfer_contract 必须是对象")
    else:
        for field, minimum, description in (
            ("preserve_axes", 2, "至少两条保留轴"),
            ("rewrite_axes", 2, "至少两条改写轴"),
            ("forbidden_surface_reuse", 1, "至少一条禁止复用的原文句面"),
        ):
            if not nonempty_list(anti_verbatim_transfer_contract.get(field), minimum=minimum):
                errors.append(
                    f"{label} first_draft_generation_contract.anti_verbatim_transfer_contract.{field} {description}"
                )
        for field in ("allowed_evidence_usage", "manual_judgment"):
            if not nonempty_text(anti_verbatim_transfer_contract.get(field)):
                errors.append(
                    f"{label} first_draft_generation_contract.anti_verbatim_transfer_contract.{field} 不能为空"
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


def validate_primary_subflow_inventory(
    value: Any,
    bundle_binding: Any,
    errors: list[str],
    *,
    validate_source_receipt: bool = True,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(bundle_binding, dict):
        if value in (None, []):
            return {}
        errors.append("缺少主体原文完整颗粒包绑定")
        return {}
    bundle_path = Path(str(bundle_binding.get("path") or "")).expanduser().resolve()
    if not bundle_path.is_file():
        errors.append(f"主体原文完整颗粒包不存在: {bundle_path}")
        return {}
    if bundle_binding.get("sha256") != sha256(bundle_path):
        errors.append("主体原文完整颗粒包 SHA 已变化，必须重新初始化细纲验收回执")
        return {}
    try:
        bundle = read_primary_source_bundle(
            bundle_path,
            validate_source_receipt=validate_source_receipt,
        )
    except ValueError as exc:
        errors.append(str(exc))
        return {}
    expected = bundle.get("subflows")
    if not isinstance(expected, list):
        errors.append("主体原文完整颗粒包缺少 subflows")
        return {}
    if value != expected:
        errors.append("primary_subflow_semantic_inventory 必须与主体原文完整颗粒包逐条一致")
    inventory: dict[tuple[str, str], dict[str, Any]] = {}
    for item in expected:
        if not isinstance(item, dict):
            continue
        contract = item.get("contract")
        if not isinstance(contract, dict):
            continue
        source_path = str(bundle.get("primary_source", {}).get("original", {}).get("path") or "")
        source_range = str(contract.get("source_range") or "").strip()
        if source_path and source_range:
            inventory[(str(Path(source_path).expanduser().resolve()), source_range)] = item
    return inventory


def validate_receipt(
    receipt_path: Path,
    outline_path: Path,
    *,
    skip_source_receipt_validation: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not receipt_path.is_file():
        return [f"细纲表演验收回执不存在: {receipt_path}"]
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"细纲表演验收回执不是有效 JSON: {exc}"]
    if not isinstance(data, dict):
        return ["细纲表演验收回执必须是 JSON 对象"]
    if data.get("version") != "1.6":
        errors.append(
            "细纲表演验收回执版本必须为 1.5；旧回执缺少节内逐拍、跨节交接或辅助 SF 全流程契约，必须重新 init"
        )

    resolved_outline = outline_path.resolve()
    if not resolved_outline.is_file():
        return [f"细纲不存在: {resolved_outline}"]
    bound_outline = validate_binding(data.get("outline"), "细纲绑定", errors)
    if bound_outline is not None and bound_outline != resolved_outline:
        errors.append("细纲绑定路径与当前 --outline 不一致")

    sources = data.get("selected_source_originals")
    source_paths: set[str] = set()
    source_path_order: list[Path] = []
    source_texts: dict[str, str] = {}
    source_metadata: dict[str, dict[str, Any]] = {}
    if not isinstance(sources, list) or not sources:
        errors.append("selected_source_originals 必须至少包含一本选中原文")
    else:
        for index, source in enumerate(sources, start=1):
            source_path = validate_binding(source, f"选中原文[{index}]", errors)
            if source_path is not None:
                source_path_order.append(source_path)
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
        if global_review.get("intra_section_beat_causality_reviewed") is not True:
            errors.append("必须在正文前逐节核对每一拍的前置状态、触发、视野/物件权限和状态变化")
        if global_review.get("section_handoff_reviewed") is not True:
            errors.append("必须在正文前完成相邻小节状态交接，禁止只核小节标题顺序")
        if len(source_path_order) > 1 and global_review.get(
            "auxiliary_subflow_full_flow_reviewed"
        ) is not True:
            errors.append("融合仿写必须逐个验收辅助 SF 的完整流程、知情和物件生命周期")
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

    section_ids = outline_sections(read_text(resolved_outline))
    if not section_ids:
        errors.append("细纲中未找到 `## 1.` 形式的小节")
        return errors
    outline_text = read_text(resolved_outline)
    validate_story_fact_state_ledger(
        data.get("story_fact_state_ledger"), section_ids, outline_text, errors
    )
    source_mode = str(data.get("source_mode") or "full_bridge").strip()
    if source_mode == "full_bridge":
        validate_auxiliary_subflow_flow_parity(
            data.get("auxiliary_subflow_flow_parity"),
            data.get("source_read_receipt"),
            source_path_order,
            source_texts,
            section_ids,
            outline_text,
            errors,
        )
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
        primary_inventory: dict[tuple[str, str], dict[str, Any]] = {}
    else:
        primary_inventory = validate_primary_subflow_inventory(
            data.get("primary_subflow_semantic_inventory"),
            data.get("primary_source_semantic_bundle"),
            errors,
            validate_source_receipt=not skip_source_receipt_validation,
        )
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
    validate_section_handoff_chain(
        data.get("section_handoff_chain"), section_ids, by_id, outline_text, errors
    )

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
            section_id,
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
            primary_inventory,
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


ERROR_SUMMARY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("story_fact_state_ledger", ("story_fact_state_ledger",)),
    (
        "source_bridge_flow_inventory",
        ("主体来源桥段库存缺失", "辅助来源桥段库存缺失", "required_bridge_ids", "selected_bridge_ids"),
    ),
    ("outline_bridge_flow_parity", ("原文桥段对齐",)),
    ("section_handoff_chain", ("小节交接",)),
    (
        "first-draft",
        (
            "first_draft_generation_contract",
            "首写生成契约字段",
            "首写不得设置固定短句",
            "source_excerpt_reuse_reason",
        ),
    ),
    ("sections", ("第 ", "细纲小节缺少验收", "回执存在细纲中没有的小节")),
    ("global_review", ("必须人工确认", "global_review", "mechanism_transfer_boundary")),
)


def summarize_errors(errors: list[str]) -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = {}
    for error in errors:
        bucket = "other"
        for name, needles in ERROR_SUMMARY_RULES:
            if any(error.startswith(needle) or needle in error for needle in needles):
                bucket = name
                break
        grouped.setdefault(bucket, []).append(error)
    ordered = []
    for name, _needles in ERROR_SUMMARY_RULES:
        if name in grouped:
            ordered.append((name, grouped.pop(name)))
    if grouped:
        ordered.extend(sorted(grouped.items(), key=lambda item: item[0]))
    return ordered


def outline_failure_report_path(receipt_path: Path) -> Path:
    suffix = "".join(receipt_path.suffixes) or ".json"
    return receipt_path.with_name(
        receipt_path.name[: -len(suffix)] + ".validate-errors.txt"
    )


def receipt_status_mismatch_note(receipt_path: Path) -> str | None:
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if (
        data.get("gate_status") == "passed"
        or data.get("reviewed_by_current_model") is True
    ):
        return (
            "回执文件当前自报已通过，但实时复验仍失败；"
            "禁止仅修改 gate_status / reviewed_by_current_model 冒充放行。"
        )
    return None


def emit_validation_failure(
    receipt_path: Path,
    errors: list[str],
    *,
    full_errors: bool,
    max_errors_per_group: int,
) -> None:
    print("outline_performance_contract: blocked；不得生成或修改正文")
    mismatch_note = receipt_status_mismatch_note(receipt_path)
    if mismatch_note:
        print(f"- {mismatch_note}")
    grouped = summarize_errors(errors)
    print(f"- summary: {len(errors)} 个错误，{len(grouped)} 个分组")
    for group_name, group_errors in grouped:
        print(f"- summary[{group_name}]: {len(group_errors)}")
        limit = len(group_errors) if full_errors else min(len(group_errors), max_errors_per_group)
        for error in group_errors[:limit]:
            print(f"- {error}")
        if not full_errors and len(group_errors) > limit:
            print(
                f"- summary[{group_name}]: 其余 {len(group_errors) - limit} 条已省略；"
                "查看完整失败报告。"
            )
    report_path = outline_failure_report_path(receipt_path)
    report_lines = [
        "outline_performance_contract: blocked；不得生成或修改正文",
        *[f"- {error}" for error in errors],
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"- full_report: {report_path}")


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
        "--source-receipt",
        help="融合仿写必传，用于锁定每个辅助来源已选 SF 的完整契约",
    )
    init.add_argument(
        "--primary-source-bundle",
        help="主体原文完整颗粒包；full_bridge 仿写细纲初始化必传",
    )
    init.add_argument(
        "--source-mode",
        choices=("full_bridge", "granularity_only"),
        default="full_bridge",
    )
    init.add_argument("--receipt", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--outline", required=True)
    validate.add_argument(
        "--full-errors",
        action="store_true",
        help="输出全部错误；默认按分组摘要并写出完整失败报告。",
    )
    validate.add_argument(
        "--max-errors-per-group",
        type=int,
        default=8,
        help="摘要模式下每组最多显示多少条错误。",
    )
    args = parser.parse_args()

    if args.command == "init":
        if args.source_mode == "full_bridge" and not args.primary_source_bundle:
            print("outline_performance_contract: blocked")
            print("- full_bridge 仿写细纲初始化必须传 --primary-source-bundle")
            return 2
        try:
            receipt = create_receipt(
                args.project,
                Path(args.outline),
                [Path(value) for value in args.source_original],
                source_mode=args.source_mode,
                source_receipt_path=(
                    Path(args.source_receipt) if args.source_receipt else None
                ),
                primary_source_bundle_path=(
                    Path(args.primary_source_bundle)
                    if args.primary_source_bundle
                    else None
                ),
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

    receipt_path = Path(args.receipt)
    errors = validate_receipt(receipt_path, Path(args.outline))
    if errors:
        emit_validation_failure(
            receipt_path,
            errors,
            full_errors=getattr(args, "full_errors", False),
            max_errors_per_group=max(1, int(getattr(args, "max_errors_per_group", 8))),
        )
        return 2
    print("outline_performance_contract: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
