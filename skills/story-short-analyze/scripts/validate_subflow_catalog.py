#!/usr/bin/env python3
"""Validate the source-layer topology used by short-story writing.

The catalog is authored during analysis.  This validator deliberately checks
source identity, layer partitioning, narrative-mode topology, and per-layer
language realization.  It does not infer missing prose guidance or accept
summary-only substitutes.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-analyze.subflow-catalog.v2"
SOURCE_LINE_RANGE_RE = re.compile(r"L?(\d+)\s*[-~至]\s*L?(\d+)", re.IGNORECASE)
SOURCE_SECTION_MARKER_RE = re.compile(r"\s*\d+(?:[.、．])?\s*")

LANGUAGE_DIMENSIONS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)

LAYER_MODES = {
    "opening_compression",
    "live_scene",
    "compressed_scene",
    "memory_exposition",
    "summary_transition",
    "time_jump",
    "public_discourse",
    "institutional_result",
    "narrator_interjection",
    "rumor_afterword",
    "cold_afterword",
}

LAYER_TEXT_FIELDS = (
    "layer_role",
    "entry_relation",
    "exit_relation",
    "narrative_distance",
)


def parse_line_range(value: Any, label: str) -> tuple[int, int]:
    if isinstance(value, dict):
        start = value.get("start_line")
        end = value.get("end_line")
        if isinstance(start, int) and isinstance(end, int) and 0 < start <= end:
            return start, end
    match = SOURCE_LINE_RANGE_RE.fullmatch(str(value or "").strip())
    if match:
        start, end = map(int, match.groups())
        if 0 < start <= end:
            return start, end
    raise ValueError(f"{label} 无法解析原文行区间: {value!r}")


def prose_line_numbers(lines: list[str], start: int, end: int) -> list[int]:
    return [
        line_number
        for line_number in range(start, end + 1)
        if lines[line_number - 1].strip()
        and not SOURCE_SECTION_MARKER_RE.fullmatch(lines[line_number - 1])
    ]


def format_line_ranges(line_numbers: list[int]) -> str:
    if not line_numbers:
        return ""
    ranges: list[str] = []
    start = previous = line_numbers[0]
    for line_number in line_numbers[1:]:
        if line_number == previous + 1:
            previous = line_number
            continue
        ranges.append(f"L{start}" if start == previous else f"L{start}-L{previous}")
        start = previous = line_number
    ranges.append(f"L{start}" if start == previous else f"L{start}-L{previous}")
    return ", ".join(ranges)


def read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        errors.append(f"缺少子流程索引：{path}")
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{path} 第 {line_number} 行不是有效 JSON：{exc}")
            continue
        if not isinstance(item, dict):
            errors.append(f"{path} 第 {line_number} 行必须是对象")
            continue
        rows.append(item)
    return rows


def merge_normalized_layer_records(
    raw_rows: list[dict[str, Any]], errors: list[str]
) -> list[dict[str, Any]]:
    """Compile normalized source_layer records into their owning SF in memory."""
    subflows: list[dict[str, Any]] = []
    layers_by_subflow: dict[str, list[dict[str, Any]]] = {}
    for row_number, item in enumerate(raw_rows, start=1):
        record_type = str(item.get("record_type") or "subflow").strip()
        if record_type == "subflow":
            subflows.append(dict(item))
            continue
        if record_type != "source_layer":
            errors.append(
                f"子流程索引第 {row_number} 项 record_type 不支持：{record_type!r}"
            )
            continue
        if item.get("schema_version") != SCHEMA_VERSION:
            errors.append(
                f"子流程索引第 {row_number} 项 source_layer.schema_version "
                f"必须为 {SCHEMA_VERSION}"
            )
        subflow_id = str(item.get("subflow_id") or "").strip()
        layer = item.get("layer")
        if not subflow_id or not isinstance(layer, dict):
            errors.append(
                f"子流程索引第 {row_number} 项 source_layer 必须含 subflow_id 和 layer 对象"
            )
            continue
        layers_by_subflow.setdefault(subflow_id, []).append(layer)

    known_ids = {str(item.get("subflow_id") or "").strip() for item in subflows}
    unknown_ids = sorted(set(layers_by_subflow) - known_ids)
    if unknown_ids:
        errors.append(f"source_layer 引用了不存在的 SF：{', '.join(unknown_ids)}")
    for subflow in subflows:
        subflow_id = str(subflow.get("subflow_id") or "").strip()
        normalized_layers = layers_by_subflow.get(subflow_id)
        embedded_layers = subflow.get("source_layer_topology")
        if normalized_layers and embedded_layers:
            errors.append(f"{subflow_id} 不得同时使用内嵌和规范化来源层记录")
        layers = normalized_layers or embedded_layers
        if isinstance(layers, list):
            subflow["schema_version"] = SCHEMA_VERSION
            subflow["source_layer_topology"] = layers
            subflow["source_layer_order"] = [
                layer.get("layer_id") if isinstance(layer, dict) else None
                for layer in layers
            ]
    return subflows


def validate_dimension_realization(
    value: Any,
    layer_text: str,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict) or set(value) != set(LANGUAGE_DIMENSIONS):
        errors.append(f"{label} 必须完整包含六个语言维度，不能用 SF 级摘要代替")
        return
    for dimension in LANGUAGE_DIMENSIONS:
        item = value.get(dimension)
        dimension_label = f"{label}.{dimension}"
        if not isinstance(item, dict):
            errors.append(f"{dimension_label} 必须是对象")
            continue
        status = item.get("status")
        if status not in {"active", "inactive"}:
            errors.append(f"{dimension_label}.status 必须为 active 或 inactive")
        if not isinstance(item.get("how"), str) or not item["how"].strip():
            errors.append(f"{dimension_label}.how 必须明确说明本层怎样起效或为何缺席")
        evidence = item.get("source_evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(quote, str) or not quote.strip() for quote in evidence
        ):
            errors.append(f"{dimension_label}.source_evidence 必须是文本列表")
            continue
        if status == "active" and not evidence:
            errors.append(f"{dimension_label} 激活时必须给本层原文证据")
        if status == "inactive" and evidence:
            errors.append(f"{dimension_label} 缺席时不得伪造原文证据")
        for quote in evidence:
            if quote not in layer_text:
                errors.append(f"{dimension_label} 证据不在本层原文：{quote!r}")


def validate_catalog(
    catalog_path: Path,
    original_path: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not original_path.is_file():
        return [], [f"原文不存在：{original_path}"]
    lines = original_path.read_text(encoding="utf-8").splitlines()
    raw_rows = read_jsonl(catalog_path, errors)
    layer_catalog_path = catalog_path.with_name("子流程层次索引.jsonl")
    if layer_catalog_path.is_file():
        raw_rows.extend(read_jsonl(layer_catalog_path, errors))
    rows = merge_normalized_layer_records(raw_rows, errors)
    ids: list[str] = []
    all_covered: set[int] = set()
    previous_sf_start = 0

    for row_number, item in enumerate(rows, start=1):
        subflow_id = str(item.get("subflow_id") or "").strip()
        label = f"子流程索引第 {row_number} 项 {subflow_id or '<missing>'}"
        if not subflow_id:
            errors.append(f"{label} 缺少 subflow_id")
            continue
        ids.append(subflow_id)
        if item.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{label}.schema_version 必须为 {SCHEMA_VERSION}")
        try:
            sf_start, sf_end = parse_line_range(item.get("source_range"), f"{label}.source_range")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if sf_end > len(lines):
            errors.append(f"{label}.source_range 超出原文总行数 {len(lines)}")
            continue
        if sf_start < previous_sf_start:
            errors.append(f"{label} 必须按原文行区间非递减排列")
        previous_sf_start = sf_start
        exact_excerpt = "\n".join(lines[sf_start - 1 : sf_end])
        if item.get("source_excerpt") != exact_excerpt:
            errors.append(f"{label}.source_excerpt 必须逐字等于 L{sf_start}-L{sf_end}")

        topology = item.get("source_layer_topology")
        if not isinstance(topology, list) or not topology:
            errors.append(f"{label}.source_layer_topology 必须是非空逐层拓扑，摘要字段不能替代")
            continue
        layer_covered: set[int] = set()
        previous_layer_end = sf_start - 1
        expected_layer_ids: list[str] = []
        for index, layer in enumerate(topology, start=1):
            layer_label = f"{label}.source_layer_topology[{index}]"
            expected_layer_id = f"{subflow_id}-L{index:02d}"
            expected_layer_ids.append(expected_layer_id)
            if not isinstance(layer, dict):
                errors.append(f"{layer_label} 必须是对象")
                continue
            if layer.get("layer_id") != expected_layer_id:
                errors.append(f"{layer_label}.layer_id 必须为 {expected_layer_id}")
            try:
                layer_start, layer_end = parse_line_range(
                    layer.get("source_range"), f"{layer_label}.source_range"
                )
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if layer_start < sf_start or layer_end > sf_end:
                errors.append(f"{layer_label}.source_range 必须位于当前 SF 范围内")
                continue
            if layer_start <= previous_layer_end:
                errors.append(f"{layer_label} 与前一层重叠或倒序")
            previous_layer_end = layer_end
            exact_layer_text = "\n".join(lines[layer_start - 1 : layer_end])
            if layer.get("source_text") != exact_layer_text:
                errors.append(
                    f"{layer_label}.source_text 必须逐字等于 L{layer_start}-L{layer_end}"
                )
            modes = layer.get("layer_modes")
            if (
                not isinstance(modes, list)
                or not modes
                or any(mode not in LAYER_MODES for mode in modes)
                or len(modes) != len(set(modes))
            ):
                errors.append(f"{layer_label}.layer_modes 必须是合法、非重复的叙事模式列表")
            for field in LAYER_TEXT_FIELDS:
                if not isinstance(layer.get(field), str) or not layer[field].strip():
                    errors.append(f"{layer_label}.{field} 必须明确填写")
            preserve = layer.get("must_preserve_in_target")
            if not isinstance(preserve, list) or not preserve or any(
                not isinstance(rule, str) or not rule.strip() for rule in preserve
            ):
                errors.append(f"{layer_label}.must_preserve_in_target 必须是非空施工规则列表")
            validate_dimension_realization(
                layer.get("dimension_realization"),
                exact_layer_text,
                f"{layer_label}.dimension_realization",
                errors,
            )
            current_lines = set(prose_line_numbers(lines, layer_start, layer_end))
            duplicates = sorted(layer_covered & current_lines)
            if duplicates:
                errors.append(
                    f"{layer_label} 重复覆盖原文正文行：{format_line_ranges(duplicates)}"
                )
            layer_covered.update(current_lines)

        sf_prose_lines = set(prose_line_numbers(lines, sf_start, sf_end))
        missing = sorted(sf_prose_lines - layer_covered)
        extra = sorted(layer_covered - sf_prose_lines)
        if missing:
            errors.append(f"{label} 层次拓扑漏掉正文行：{format_line_ranges(missing)}")
        if extra:
            errors.append(f"{label} 层次拓扑越界覆盖：{format_line_ranges(extra)}")
        layer_order = item.get("source_layer_order")
        if layer_order != expected_layer_ids:
            errors.append(f"{label}.source_layer_order 必须与逐层拓扑完整同序")
        all_covered.update(sf_prose_lines)

    duplicates = sorted(subflow_id for subflow_id in set(ids) if ids.count(subflow_id) > 1)
    if duplicates:
        errors.append(f"子流程 subflow_id 重复：{', '.join(duplicates)}")
    if not rows:
        errors.append("子流程索引不得为空")
    whole_prose = set(prose_line_numbers(lines, 1, len(lines)))
    missing_whole = sorted(whole_prose - all_covered)
    if missing_whole:
        errors.append(f"子流程索引未覆盖原文全部正文行：{format_line_ranges(missing_whole)}")
    return rows, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="验证短篇子流程完整来源层次拓扑")
    parser.add_argument("catalog", help="写作资产/子流程索引.jsonl")
    parser.add_argument("original", help="对应原文 TXT")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    rows, errors = validate_catalog(Path(args.catalog).resolve(), Path(args.original).resolve())
    payload = {
        "ok": not errors,
        "subflow_count": len(rows),
        "error_count": len(errors),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print("blocked")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"passed: {len(rows)} subflows")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
