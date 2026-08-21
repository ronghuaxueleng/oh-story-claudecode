#!/usr/bin/env python3
"""Compile deterministic short-story assets into one reusable source prose map."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-analyze.source-prose-map.v1"
RANGE_RE = re.compile(r"^L(\d+)(?:-L?(\d+))?$")
SECTION_MARKER_RE = re.compile(r"^\s*\d+(?:[.、．])?\s*$")
DIMENSION_FIELDS = (
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def read_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是 JSON 对象: {path}")
    return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}第 {line_number} 行不是有效 JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{label}第 {line_number} 行必须是 JSON 对象")
        rows.append(value)
    return rows


def source_range(value: Any, label: str) -> dict[str, int]:
    if isinstance(value, dict):
        start = value.get("start_line")
        end = value.get("end_line")
    else:
        match = RANGE_RE.fullmatch(str(value or "").strip())
        if not match:
            raise ValueError(f"{label} source_range 无法解析: {value!r}")
        start = int(match.group(1))
        end = int(match.group(2) or start)
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise ValueError(f"{label} source_range 非法: {value!r}")
    return {"start_line": start, "end_line": end}


def range_text(lines: list[str], value: dict[str, int], label: str) -> str:
    start = value["start_line"]
    end = value["end_line"]
    if end > len(lines):
        raise ValueError(f"{label} 超出原文行数: L{start}-L{end} / {len(lines)}")
    return "\n".join(lines[start - 1 : end])


def binding(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "relative_path": str(path.resolve().relative_to(root.resolve())),
        "sha256": file_sha256(path),
    }


def _clean_dimension(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"status": "", "how": ""}
    return {
        "status": str(value.get("status") or "").strip(),
        "how": str(value.get("how") or "").strip(),
    }


def _beat_copy(beat: dict[str, Any], beat_type: str, lines: list[str]) -> dict[str, Any]:
    beat_id = str(beat.get("beat_id") or "").strip()
    if not beat_id:
        raise ValueError(f"{beat_type} 拍缺少 beat_id")
    if beat_type == "plot":
        item = {
            key: beat.get(key)
            for key in (
                "beat_id",
                "actor",
                "action",
                "object_or_receiver",
                "pressure_or_trigger",
                "control_change",
                "information_change",
                "consequence",
                "bid_ids",
            )
        }
        value = beat.get("source_range")
    else:
        item = {
            key: beat.get(key)
            for key in (
                "beat_id",
                "segment_id",
                "role",
                "content",
                "trigger",
                "relationship_position_change",
                "reader_effect",
                "intensity",
                "narrative_function",
                "bid_ids",
            )
        }
        value = {
            "start_line": beat.get("start_line"),
            "end_line": beat.get("end_line"),
        }
    parsed_range = source_range(value, beat_id)
    item["source_range"] = parsed_range
    item["source_text_sha256"] = sha256_bytes(
        range_text(lines, parsed_range, beat_id).encode("utf-8")
    )
    item["content_sha256"] = canonical_sha256(item)
    return item


def compile_source_map(root: Path) -> dict[str, Any]:
    root = root.resolve()
    assets = root / "写作资产"
    original_candidates = sorted((root / "原文").glob("*.txt"))
    if len(original_candidates) != 1:
        raise ValueError(f"原文目录必须且只能有一个 TXT，实际 {len(original_candidates)} 个")
    original = original_candidates[0]
    plot_path = assets / "全文情节微拍总账.json"
    emotion_path = assets / "全文情绪颗粒总账.json"
    subflow_path = assets / "子流程索引.jsonl"
    layer_path = assets / "子流程层次索引.jsonl"
    profile_path = root / "book.profile.json"

    plot = read_object(plot_path, "全文情节微拍总账")
    emotion = read_object(emotion_path, "全文情绪颗粒总账")
    subflow_rows = read_jsonl(subflow_path, "子流程索引")
    layer_rows = read_jsonl(layer_path, "子流程层次索引")
    profile = read_object(profile_path, "book.profile.json")
    lines = original.read_text(encoding="utf-8").splitlines()

    plot_beats = [_beat_copy(item, "plot", lines) for item in plot.get("beats", [])]
    emotion_beats = [_beat_copy(item, "emotion", lines) for item in emotion.get("beats", [])]
    plot_ids = [item["beat_id"] for item in plot_beats]
    emotion_ids = [item["beat_id"] for item in emotion_beats]
    if len(plot_ids) != len(set(plot_ids)) or not plot_ids:
        raise ValueError("P 拍 ID 必须非空且唯一")
    if len(emotion_ids) != len(set(emotion_ids)) or not emotion_ids:
        raise ValueError("E 拍 ID 必须非空且唯一")

    bridge_rules = profile.get("bridge_rules")
    if not isinstance(bridge_rules, list) or not bridge_rules:
        raise ValueError("book.profile.json 缺少 bridge_rules")
    profile_bid_order = [str(item.get("id") or "").strip() for item in bridge_rules]
    if any(not item for item in profile_bid_order) or len(profile_bid_order) != len(set(profile_bid_order)):
        raise ValueError("bridge_rules 的 BID 必须非空且唯一")

    subflows: list[dict[str, Any]] = []
    subflow_ids: list[str] = []
    for raw in subflow_rows:
        sf_id = str(raw.get("subflow_id") or "").strip()
        if not sf_id:
            raise ValueError("子流程缺少 subflow_id")
        parsed_range = source_range(raw.get("source_range"), sf_id)
        item = {
            key: raw.get(key)
            for key in (
                "subflow_id",
                "parent_bridge_id",
                "name",
                "function_tags",
                "entry_state",
                "required_sequence",
                "scene_granularity",
                "causal_preconditions",
                "information_delay",
                "control_changes",
                "emotion_sequence",
                "end_state",
                "embeddable_after",
                "incompatible_with",
            )
        }
        causal = item.get("causal_preconditions")
        if isinstance(causal, dict):
            causal = dict(causal)
            causal.pop("source_evidence", None)
            item["causal_preconditions"] = causal
        item["source_range"] = parsed_range
        item["source_text_sha256"] = sha256_bytes(
            range_text(lines, parsed_range, sf_id).encode("utf-8")
        )
        item["content_sha256"] = canonical_sha256(item)
        subflows.append(item)
        subflow_ids.append(sf_id)
    if len(subflow_ids) != len(set(subflow_ids)) or not subflow_ids:
        raise ValueError("SF ID 必须非空且唯一")

    bid_first_lines: dict[str, int] = {}
    for item in [*plot_beats, *emotion_beats]:
        for bid in item.get("bid_ids") or []:
            bid_value = str(bid or "").strip()
            if bid_value:
                bid_first_lines[bid_value] = min(
                    bid_first_lines.get(bid_value, item["source_range"]["start_line"]),
                    item["source_range"]["start_line"],
                )
    for item in subflows:
        bid_value = str(item.get("parent_bridge_id") or "").strip()
        if bid_value:
            bid_first_lines[bid_value] = min(
                bid_first_lines.get(bid_value, item["source_range"]["start_line"]),
                item["source_range"]["start_line"],
            )
    ledger_bid_order = [
        bid for bid, _ in sorted(bid_first_lines.items(), key=lambda pair: (pair[1], pair[0]))
    ]
    if ledger_bid_order[: len(profile_bid_order)] != profile_bid_order:
        raise ValueError(
            "book.profile.json bridge_rules 必须是当前 P/E/SF BID 顺序的完整值或连续前缀"
        )
    bid_order = ledger_bid_order or profile_bid_order

    layers: list[dict[str, Any]] = []
    layer_ids: list[str] = []
    for row in layer_rows:
        sf_id = str(row.get("subflow_id") or "").strip()
        layer = row.get("layer")
        if not isinstance(layer, dict):
            raise ValueError(f"{sf_id or '未知 SF'} 的文字层必须是对象")
        layer_id = str(layer.get("layer_id") or "").strip()
        parsed_range = source_range(layer.get("source_range"), layer_id)
        dimensions = {
            field: _clean_dimension((layer.get("dimension_realization") or {}).get(field))
            for field in DIMENSION_FIELDS
        }
        item = {
            "layer_id": layer_id,
            "subflow_id": sf_id,
            "source_range": parsed_range,
            "source_text_sha256": sha256_bytes(
                range_text(lines, parsed_range, layer_id).encode("utf-8")
            ),
            "layer_modes": layer.get("layer_modes") or [],
            "layer_role": layer.get("layer_role") or "",
            "entry_relation": layer.get("entry_relation") or "",
            "exit_relation": layer.get("exit_relation") or "",
            "narrative_distance": layer.get("narrative_distance") or "",
            "dimension_realization": dimensions,
            "must_preserve_in_target": layer.get("must_preserve_in_target") or [],
        }
        item["content_sha256"] = canonical_sha256(item)
        layers.append(item)
        layer_ids.append(layer_id)
    if any(not item for item in layer_ids) or len(layer_ids) != len(set(layer_ids)):
        raise ValueError("文字层 ID 必须非空且唯一")
    unknown_layer_sf = sorted({item["subflow_id"] for item in layers} - set(subflow_ids))
    if unknown_layer_sf:
        raise ValueError("文字层引用未知 SF: " + ", ".join(unknown_layer_sf))
    subflow_positions = {value: index for index, value in enumerate(subflow_ids)}
    layers.sort(
        key=lambda item: (
            subflow_positions[item["subflow_id"]],
            item["source_range"]["start_line"],
            item["source_range"]["end_line"],
            item["layer_id"],
        )
    )
    layer_ids = [item["layer_id"] for item in layers]

    def overlaps(item: dict[str, Any], span: dict[str, int]) -> bool:
        value = item["source_range"]
        return value["start_line"] <= span["end_line"] and value["end_line"] >= span["start_line"]

    for sf in subflows:
        sf["plot_beat_ids"] = [item["beat_id"] for item in plot_beats if overlaps(item, sf["source_range"])]
        sf["emotion_beat_ids"] = [item["beat_id"] for item in emotion_beats if overlaps(item, sf["source_range"])]
        sf["layer_ids"] = [item["layer_id"] for item in layers if item["subflow_id"] == sf["subflow_id"]]
        sf["content_sha256"] = canonical_sha256({key: value for key, value in sf.items() if key != "content_sha256"})

    bridges = []
    for bid in bid_order:
        rule = next((item for item in bridge_rules if item.get("id") == bid), {})
        bridges.append(
            {
                "bid_id": bid,
                "name": str(rule.get("bridge") or bid).strip(),
                "plot_beat_ids": [item["beat_id"] for item in plot_beats if bid in (item.get("bid_ids") or [])],
                "emotion_beat_ids": [item["beat_id"] for item in emotion_beats if bid in (item.get("bid_ids") or [])],
                "subflow_ids": [item["subflow_id"] for item in subflows if item.get("parent_bridge_id") == bid],
            }
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_book": root.name,
        "source_root": str(root),
        "compiled_from": {
            "original": {**binding(root, original), "line_count": len(lines)},
            "plot_ledger": binding(root, plot_path),
            "emotion_ledger": binding(root, emotion_path),
            "subflow_catalog": binding(root, subflow_path),
            "layer_catalog": binding(root, layer_path),
            "profile": binding(root, profile_path),
        },
        "order": {
            "bid_ids": bid_order,
            "plot_beat_ids": plot_ids,
            "emotion_beat_ids": emotion_ids,
            "subflow_ids": subflow_ids,
            "layer_ids": layer_ids,
        },
        "bridges": bridges,
        "plot_beats": plot_beats,
        "emotion_beats": emotion_beats,
        "subflows": subflows,
        "layers": layers,
    }
    payload["content_sha256"] = canonical_sha256(payload)
    return payload


def validate_source_map(payload: dict[str, Any], path: Path | None = None) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须为 {SCHEMA_VERSION}")
    expected_hash = canonical_sha256(
        {key: value for key, value in payload.items() if key != "content_sha256"}
    )
    if payload.get("content_sha256") != expected_hash:
        errors.append("来源成文脑图 content_sha256 与内容不一致")
    order = payload.get("order")
    if not isinstance(order, dict):
        return errors + ["来源成文脑图缺少 order"]
    compiled = payload.get("compiled_from")
    original_path = None
    source_lines: list[str] = []
    if isinstance(compiled, dict) and isinstance(compiled.get("original"), dict):
        original_path = Path(str(compiled["original"].get("path") or "")).expanduser()
        try:
            source_lines = original_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            errors.append(f"compiled_from.original 无法读取: {original_path}")

    def parsed_range(value: Any, label: str) -> tuple[int, int] | None:
        try:
            result = source_range(value, label)
        except ValueError as exc:
            errors.append(str(exc))
            return None
        start, end = result["start_line"], result["end_line"]
        if source_lines and end > len(source_lines):
            errors.append(f"{label} 越出原文总行数 {len(source_lines)}")
            return None
        return start, end

    def verify_source_hash(item: dict[str, Any], label: str) -> tuple[int, int] | None:
        value = parsed_range(item.get("source_range"), f"{label}.source_range")
        if value is None or not source_lines:
            return value
        start, end = value
        expected = sha256_bytes("\n".join(source_lines[start - 1 : end]).encode("utf-8"))
        if item.get("source_text_sha256") != expected:
            errors.append(f"{label}.source_text_sha256 与当前原文不一致")
        return value

    def overlaps(first: tuple[int, int], second: tuple[int, int]) -> bool:
        return first[0] <= second[1] and second[0] <= first[1]

    def prose_lines(start: int, end: int) -> set[int]:
        return {
            line_number
            for line_number in range(start, end + 1)
            if source_lines[line_number - 1].strip()
            and not SECTION_MARKER_RE.fullmatch(source_lines[line_number - 1])
        }
    collections = (
        ("plot_beat_ids", "plot_beats", "beat_id"),
        ("emotion_beat_ids", "emotion_beats", "beat_id"),
        ("subflow_ids", "subflows", "subflow_id"),
        ("layer_ids", "layers", "layer_id"),
    )
    for order_key, collection_key, id_key in collections:
        values = payload.get(collection_key)
        if not isinstance(values, list) or not values:
            errors.append(f"{collection_key} 必须是非空数组")
            continue
        actual = [item.get(id_key) for item in values if isinstance(item, dict)]
        if (
            len(actual) != len(values)
            or any(not isinstance(item, str) or not item for item in actual)
            or len(actual) != len(set(actual))
        ):
            errors.append(f"{collection_key}.{id_key} 必须非空且唯一")
        if order.get(order_key) != actual:
            errors.append(f"order.{order_key} 与 {collection_key} 顺序不一致")
        for item in values:
            if not isinstance(item, dict):
                continue
            content = {key: value for key, value in item.items() if key != "content_sha256"}
            if item.get("content_sha256") != canonical_sha256(content):
                errors.append(f"{item.get(id_key) or collection_key} 内容哈希不一致")

            label = str(item.get(id_key) or collection_key)
            verify_source_hash(item, label)
            if collection_key == "plot_beats":
                required = (
                    "actor", "action", "object_or_receiver", "pressure_or_trigger",
                    "control_change", "information_change", "consequence",
                )
            elif collection_key == "emotion_beats":
                required = (
                    "segment_id", "role", "content", "trigger",
                    "relationship_position_change", "reader_effect",
                    "intensity", "narrative_function",
                )
            elif collection_key == "subflows":
                required = (
                    "parent_bridge_id", "name", "required_sequence",
                    "scene_granularity", "causal_preconditions", "information_delay",
                    "control_changes", "emotion_sequence", "end_state",
                )
            else:
                required = (
                    "subflow_id", "layer_modes", "layer_role", "entry_relation",
                    "exit_relation", "narrative_distance", "dimension_realization",
                    "must_preserve_in_target",
                )
            for field in required:
                value = item.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    errors.append(f"{label} 缺少非空 {field}")

    bridges = payload.get("bridges")
    if not isinstance(bridges, list) or not bridges:
        errors.append("bridges 必须是非空数组")
    else:
        actual_bid_ids = [
            item.get("bid_id") for item in bridges if isinstance(item, dict)
        ]
        if (
            len(actual_bid_ids) != len(bridges)
            or any(not isinstance(item, str) or not item for item in actual_bid_ids)
            or len(actual_bid_ids) != len(set(actual_bid_ids))
        ):
            errors.append("bridges.bid_id 必须非空且唯一")
        if order.get("bid_ids") != actual_bid_ids:
            errors.append("order.bid_ids 与 bridges 顺序不一致")
        plot_beats = payload.get("plot_beats") or []
        emotion_beats = payload.get("emotion_beats") or []
        subflows = payload.get("subflows") or []
        for bridge in bridges:
            if not isinstance(bridge, dict):
                errors.append("bridges 只能包含对象")
                continue
            bid_id = bridge.get("bid_id")
            expected_refs = {
                "plot_beat_ids": [
                    item.get("beat_id")
                    for item in plot_beats
                    if isinstance(item, dict)
                    and isinstance(item.get("bid_ids"), list)
                    and bid_id in item["bid_ids"]
                ],
                "emotion_beat_ids": [
                    item.get("beat_id")
                    for item in emotion_beats
                    if isinstance(item, dict)
                    and isinstance(item.get("bid_ids"), list)
                    and bid_id in item["bid_ids"]
                ],
                "subflow_ids": [
                    item.get("subflow_id")
                    for item in subflows
                    if isinstance(item, dict) and item.get("parent_bridge_id") == bid_id
                ],
            }
            for field, expected in expected_refs.items():
                if bridge.get(field) != expected:
                    errors.append(f"{bid_id or '未知 BID'}.{field} 与来源对象不一致")
        known_bid_ids = set(actual_bid_ids)
        for collection_key in ("plot_beats", "emotion_beats"):
            for item in payload.get(collection_key) or []:
                if not isinstance(item, dict):
                    continue
                bid_ids = item.get("bid_ids")
                if not isinstance(bid_ids, list) or any(
                    not isinstance(value, str) or not value for value in bid_ids
                ):
                    errors.append(f"{item.get('beat_id') or collection_key}.bid_ids 必须是字符串数组")
                    continue
                unknown = sorted(set(bid_ids) - known_bid_ids)
                if unknown:
                    errors.append(
                        f"{item.get('beat_id') or collection_key}.bid_ids 引用未知 BID: {unknown}"
                    )
        for item in payload.get("subflows") or []:
            if not isinstance(item, dict):
                continue
            parent = item.get("parent_bridge_id")
            if parent not in known_bid_ids:
                errors.append(
                    f"{item.get('subflow_id') or '未知 SF'}.parent_bridge_id 引用未知 BID: {parent!r}"
                )

    subflows = payload.get("subflows")
    layers = payload.get("layers")
    if isinstance(subflows, list) and isinstance(layers, list):
        subflow_ranges: dict[str, tuple[int, int]] = {}
        layer_ranges: dict[str, tuple[int, int]] = {}
        for subflow in subflows:
            if not isinstance(subflow, dict):
                continue
            subflow_id = subflow.get("subflow_id")
            expected_layer_ids = [
                item.get("layer_id")
                for item in layers
                if isinstance(item, dict) and item.get("subflow_id") == subflow_id
            ]
            if subflow.get("layer_ids") != expected_layer_ids:
                errors.append(
                    f"{subflow_id or '未知 SF'}.layer_ids 与文字层目录不一致"
                )
            sf_range = verify_source_hash(subflow, str(subflow_id or "未知 SF"))
            if sf_range is not None:
                subflow_ranges[str(subflow_id)] = sf_range
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            layer_id = str(layer.get("layer_id") or "未知层")
            layer_range = verify_source_hash(layer, layer_id)
            if layer_range is None:
                continue
            layer_ranges[layer_id] = layer_range
            modes = layer.get("layer_modes")
            if (
                not isinstance(modes, list)
                or not modes
                or len(modes) != len(set(modes))
                or any(mode not in LAYER_MODES for mode in modes)
            ):
                errors.append(f"{layer_id}.layer_modes 含非法、重复或空叙事模式")
            dimensions = layer.get("dimension_realization")
            if not isinstance(dimensions, dict) or set(dimensions) != set(DIMENSION_FIELDS):
                errors.append(f"{layer_id}.dimension_realization 必须完整包含六个语言维度")
            else:
                for dimension in DIMENSION_FIELDS:
                    value = dimensions.get(dimension)
                    if (
                        not isinstance(value, dict)
                        or value.get("status") not in {"active", "inactive"}
                        or not str(value.get("how") or "").strip()
                    ):
                        errors.append(f"{layer_id}.{dimension} 缺少有效 status/how")
            sf_id = str(layer.get("subflow_id") or "")
            sf_range = subflow_ranges.get(sf_id)
            if sf_range and not (sf_range[0] <= layer_range[0] <= layer_range[1] <= sf_range[1]):
                errors.append(f"{layer_id} 越出所属 {sf_id} 的 source_range")
        if source_lines:
            for sf_id, sf_range in subflow_ranges.items():
                owned = sorted(
                    (layer_ranges[item.get("layer_id")] for item in layers
                     if isinstance(item, dict) and item.get("subflow_id") == sf_id
                     and item.get("layer_id") in layer_ranges),
                    key=lambda value: (value[0], value[1]),
                )
                covered: set[int] = set()
                previous_end = sf_range[0] - 1
                for current in owned:
                    if current[0] <= previous_end:
                        errors.append(f"{sf_id} 文字层重叠或倒序: L{current[0]}-L{current[1]}")
                    previous_end = current[1]
                    covered.update(prose_lines(*current))
                expected = prose_lines(*sf_range)
                if covered != expected:
                    missing = sorted(expected - covered)
                    extra = sorted(covered - expected)
                    if missing:
                        errors.append(f"{sf_id} 文字层漏覆盖原文行: {missing[:12]}")
                    if extra:
                        errors.append(f"{sf_id} 文字层越界覆盖原文行: {extra[:12]}")

        plot_beats = [item for item in payload.get("plot_beats") or [] if isinstance(item, dict)]
        emotion_beats = [item for item in payload.get("emotion_beats") or [] if isinstance(item, dict)]
        for sf in subflows:
            if not isinstance(sf, dict):
                continue
            sf_id = str(sf.get("subflow_id") or "")
            sf_range = subflow_ranges.get(sf_id)
            parent = str(sf.get("parent_bridge_id") or "")
            if not sf_range or not parent:
                continue
            for beat in [*plot_beats, *emotion_beats]:
                beat_range = parsed_range(beat.get("source_range"), str(beat.get("beat_id") or "beat"))
                if not beat_range or not overlaps(beat_range, sf_range):
                    continue
                bids = [str(value) for value in beat.get("bid_ids") or [] if str(value).strip()]
                if bids and bids != [parent]:
                    errors.append(
                        f"{sf_id} parent_bridge_id={parent} 与 {beat.get('beat_id')} bid_ids={bids} 不一致"
                    )
        for beat in [*plot_beats, *emotion_beats]:
            bids = [str(value) for value in beat.get("bid_ids") or [] if str(value).strip()]
            if not bids:
                continue
            beat_range = parsed_range(beat.get("source_range"), str(beat.get("beat_id") or "beat"))
            if not beat_range:
                continue
            if not any(
                str(sf.get("parent_bridge_id") or "") == bids[0]
                and sf_id in subflow_ranges
                and overlaps(beat_range, subflow_ranges[sf_id])
                for sf_id, sf in ((str(item.get("subflow_id") or ""), item) for item in subflows if isinstance(item, dict))
            ):
                errors.append(f"{beat.get('beat_id')} 未被同 BID 的 SF 文字层承接")
    compiled = payload.get("compiled_from")
    if not isinstance(compiled, dict):
        errors.append("来源成文脑图缺少 compiled_from")
    else:
        required_bindings = {
            "original",
            "plot_ledger",
            "emotion_ledger",
            "subflow_catalog",
            "layer_catalog",
            "profile",
        }
        missing_bindings = sorted(required_bindings - set(compiled))
        if missing_bindings:
            errors.append(f"compiled_from 缺少依赖绑定: {missing_bindings}")
        for name, item in compiled.items():
            if not isinstance(item, dict):
                errors.append(f"compiled_from.{name} 必须是对象")
                continue
            source = Path(str(item.get("path") or "")).expanduser()
            if not source.is_file():
                errors.append(f"compiled_from.{name} 文件不存在: {source}")
            elif item.get("sha256") != file_sha256(source):
                errors.append(f"compiled_from.{name} SHA 已失效")
    if path is not None and path.name != "来源成文脑图.json":
        errors.append("来源成文脑图固定文件名必须为 来源成文脑图.json")
    return errors


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--output", help="默认写入 写作资产/来源成文脑图.json")
    parser.add_argument("--check", action="store_true", help="只校验现有脑图，不重新编译")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else root / "写作资产" / "来源成文脑图.json"
    try:
        if args.check:
            payload = read_object(output, "来源成文脑图")
        else:
            payload = compile_source_map(root)
            write_json(output, payload)
        errors = validate_source_map(payload, output)
    except (OSError, ValueError, FileNotFoundError) as exc:
        errors = [str(exc)]
        payload = {}
    result = {
        "ok": not errors,
        "output": str(output),
        "counts": {
            "bridges": len(payload.get("bridges") or []),
            "plot_beats": len(payload.get("plot_beats") or []),
            "emotion_beats": len(payload.get("emotion_beats") or []),
            "subflows": len(payload.get("subflows") or []),
            "layers": len(payload.get("layers") or []),
        },
        "errors": errors,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("source_prose_map: passed" if not errors else "source_prose_map: blocked")
        print(json.dumps(result["counts"], ensure_ascii=False))
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
