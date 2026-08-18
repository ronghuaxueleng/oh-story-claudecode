#!/usr/bin/env python3
"""Validate the compact source-to-outline migration contract.

The contract records only decisions that cannot be recovered mechanically from
the detailed outline: which target fine beat carries each selected source P/E
beat. Section budgets and scene summaries are parsed directly from the outline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-write.outline-migration-contract.v2"
TEMPLATE_SCHEMA = "story-short-write.outline-migration-template.v1"
FULL_BRIDGE_PLOT_LEDGER_SCHEMA = "story-short-analyze.full-text-plot-ledger.v2"
FULL_EMOTION_LEDGER_SCHEMA = "story-short-analyze.full-text-emotion-ledger.v2"
SOURCE_STYLE_GRANULARITY_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
FIELD_RE = re.compile(r"(?m)^- ([^：\n]+)：(.*)$")
SECTION_HEADING_RE = re.compile(r"^(\d+)[.、．](?:\s+.*)?$")
CHAR_RANGE_RE = re.compile(r"(\d+)\s*[-~至]\s*(\d+)\s*字")
SOURCE_LINE_RANGE_RE = re.compile(r"L?(\d+)\s*[-~至]\s*L?(\d+)", re.IGNORECASE)
REQUIRED_OUTLINE_FIELDS = (
    "主事件",
    "子事件",
    "细拍拆分",
    "情绪",
    "读者新获知什么",
    "钩子",
    "伏笔/物件",
    "动静",
    "对话密度",
    "目标字数",
    "场面单元",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, str]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"文件不存在: {resolved}")
    return {"path": str(resolved), "sha256": sha256(resolved)}


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


def _resolve_path(value: Any, project_dir: Path) -> Path:
    path = Path(str(value or "")).expanduser()
    return path.resolve() if path.is_absolute() else (project_dir / path).resolve()


def _derived_original(entry: dict[str, Any], project_dir: Path) -> Path:
    if str(entry.get("original_path") or "").strip():
        return _resolve_path(entry["original_path"], project_dir)
    profile = _resolve_path(entry.get("profile_path"), project_dir)
    name = str(entry.get("name") or "").strip()
    if not name:
        raise ValueError("来源缺少 name，无法推导原文路径")
    return profile.parent / "原文" / f"{name}.txt"


def _ledger_path(
    entry: dict[str, Any], key: str, original: Path, filename: str, project_dir: Path
) -> Path:
    if str(entry.get(key) or "").strip():
        return _resolve_path(entry[key], project_dir)
    return original.parent.parent / "写作资产" / filename


def _subflow_catalog_path(
    entry: dict[str, Any], original: Path, project_dir: Path
) -> Path:
    if str(entry.get("subflow_catalog_path") or "").strip():
        return _resolve_path(entry["subflow_catalog_path"], project_dir)
    return original.parent.parent / "写作资产" / "子流程索引.jsonl"


def _load_beats(path: Path, label: str, expected_schema: str) -> list[dict[str, Any]]:
    payload = read_json(path, label)
    if payload.get("schema_version") != expected_schema:
        raise ValueError(
            f"{label} schema_version 必须为 {expected_schema}: {path}"
        )
    beats = payload.get("beats")
    if not isinstance(beats, list) or not beats or any(not isinstance(item, dict) for item in beats):
        raise ValueError(f"{label}.beats 必须是非空对象列表: {path}")
    ids = [str(item.get("beat_id") or "").strip() for item in beats]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{label} beat_id 缺失或重复: {path}")
    return beats


def _has_text(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_text(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_text(item) for item in value)
    return False


def _line_range(value: Any, label: str) -> tuple[int, int]:
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


def _load_subflows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"主体子流程索引不存在: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"主体子流程索引第 {line_number} 行不是有效 JSON: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"主体子流程索引第 {line_number} 行必须是对象")
        subflow_id = str(item.get("subflow_id") or "").strip()
        if not subflow_id:
            raise ValueError(f"主体子流程索引第 {line_number} 行缺少 subflow_id")
        if not str(item.get("parent_bridge_id") or "").strip():
            raise ValueError(f"主体子流程 {subflow_id} 缺少 parent_bridge_id")
        _line_range(item.get("source_range"), f"主体子流程 {subflow_id}.source_range")
        granularity = item.get("source_style_granularity")
        if not isinstance(granularity, dict):
            raise ValueError(f"主体子流程 {subflow_id} 缺少 source_style_granularity")
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            if field not in granularity or not _has_text(granularity[field]):
                raise ValueError(f"主体子流程 {subflow_id}.{field} 不能为空")
        rows.append(item)
    ids = [str(item["subflow_id"]).strip() for item in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError("主体子流程索引必须非空且 subflow_id 不得重复")
    return rows


def source_specs(config_path: Path) -> list[dict[str, Any]]:
    config = read_json(config_path, "项目写作配置")
    # Relative paths in the config are relative to the config file itself.
    project_dir = config_path.resolve().parent
    primary = config.get("primary")
    if not isinstance(primary, dict):
        raise ValueError("项目写作配置缺少 primary")
    entries: list[tuple[str, dict[str, Any]]] = [("primary", primary)]
    auxiliaries = config.get("auxiliaries") or []
    if not isinstance(auxiliaries, list):
        raise ValueError("项目写作配置 auxiliaries 必须是列表")
    entries.extend(("auxiliary", item) for item in auxiliaries if isinstance(item, dict))

    specs: list[dict[str, Any]] = []
    for index, (role, entry) in enumerate(entries):
        selected = [str(value).strip() for value in entry.get("selected_bids") or [] if str(value).strip()]
        if role == "auxiliary" and not selected:
            continue
        original = _derived_original(entry, project_dir)
        plot_ledger = _ledger_path(
            entry,
            "plot_ledger_path",
            original,
            "全文情节微拍总账.json",
            project_dir,
        )
        emotion_ledger = None
        subflow_catalog = None
        prose_subflows: list[dict[str, Any]] = []
        if role == "primary":
            emotion_ledger = _ledger_path(
                entry,
                "emotion_ledger_path",
                original,
                "全文情绪颗粒总账.json",
                project_dir,
            )
            subflow_catalog = _subflow_catalog_path(entry, original, project_dir)
            prose_subflows = _load_subflows(subflow_catalog)
        plot_beats = _load_beats(plot_ledger, "全文情节微拍总账", FULL_BRIDGE_PLOT_LEDGER_SCHEMA)
        if role == "auxiliary":
            available_bids = {
                str(bid)
                for beat in plot_beats
                for bid in beat.get("bid_ids") or []
                if str(bid).strip()
            }
            missing = [bid for bid in selected if bid not in available_bids]
            if missing:
                raise ValueError(f"辅助来源 selected_bids 不存在: {missing}")
            plot_beats = [
                beat for beat in plot_beats
                if any(bid in selected for bid in beat.get("bid_ids") or [])
            ]
        emotion_beats: list[dict[str, Any]] = []
        if emotion_ledger is not None:
            emotion_beats = _load_beats(
                emotion_ledger,
                "全文情绪颗粒总账",
                FULL_EMOTION_LEDGER_SCHEMA,
            )
        source_id = "SRC-PRIMARY" if role == "primary" else f"SRC-AUX-{index:02d}"
        specs.append(
            {
                "source_id": source_id,
                "name": str(entry.get("name") or original.stem),
                "role": role,
                "prose_voice": "exclusive" if role == "primary" else "forbidden",
                "emotion_transfer": "full" if role == "primary" else "forbidden",
                "selected_bridge_ids": selected,
                "original": binding(original),
                "plot_ledger": binding(plot_ledger),
                "emotion_ledger": binding(emotion_ledger) if emotion_ledger else None,
                "subflow_catalog": binding(subflow_catalog) if subflow_catalog else None,
                "plot_beats": plot_beats,
                "emotion_beats": emotion_beats,
                "prose_subflows": prose_subflows,
            }
        )
    return specs


def _region_id(title: str) -> str | None:
    if title == "导语":
        return "opening"
    if title == "尾声":
        return "epilogue"
    match = SECTION_HEADING_RE.fullmatch(title)
    return f"section:{int(match.group(1))}" if match else None


def parse_outline(outline_path: Path) -> dict[str, Any]:
    text = outline_path.read_text(encoding="utf-8")
    matches = list(HEADING_RE.finditer(text))
    regions: list[dict[str, Any]] = []
    errors: list[str] = []
    target_ids: set[str] = set()
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        region_id = _region_id(title)
        if region_id is None:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        fields: dict[str, list[str]] = {}
        for field_match in FIELD_RE.finditer(body):
            fields.setdefault(field_match.group(1).strip(), []).append(field_match.group(2).strip())
        missing = [field for field in REQUIRED_OUTLINE_FIELDS if not fields.get(field)]
        if missing:
            errors.append(f"{region_id} 缺少细纲字段: {missing}")
        fine_beats = fields.get("细拍拆分") or []
        target_beats: list[dict[str, str]] = []
        prefix = "opening" if region_id == "opening" else "epilogue" if region_id == "epilogue" else region_id.split(":", 1)[1]
        for beat_index, evidence in enumerate(fine_beats, start=1):
            target_id = f"T-{prefix}-{beat_index:03d}"
            if target_id in target_ids:
                errors.append(f"细纲目标拍 ID 重复: {target_id}")
            target_ids.add(target_id)
            target_beats.append({"target_id": target_id, "evidence": evidence})
        if not target_beats:
            errors.append(f"{region_id} 至少需要一条细拍拆分")
        char_min = char_max = 0
        raw_range = (fields.get("目标字数") or [""])[0]
        range_match = CHAR_RANGE_RE.search(raw_range)
        if range_match:
            char_min, char_max = map(int, range_match.groups())
            if char_min <= 0 or char_max < char_min:
                errors.append(f"{region_id} 目标字数范围无效: {raw_range}")
        else:
            errors.append(f"{region_id} 目标字数无法解析: {raw_range!r}")
        regions.append(
            {
                "region_id": region_id,
                "heading": title,
                "main_event": (fields.get("主事件") or [""])[0],
                "emotion": (fields.get("情绪") or [""])[0],
                "hook": (fields.get("钩子") or [""])[0],
                "objects": (fields.get("伏笔/物件") or [""])[0],
                "scene_summary": (fields.get("场面单元") or [""])[0],
                "target_chars": {"min": char_min, "max": char_max},
                "target_beats": target_beats,
            }
        )
    expected = ["opening"] + [f"section:{index}" for index in range(1, 1 + sum(1 for r in regions if r["region_id"].startswith("section:")))] + ["epilogue"]
    actual = [item["region_id"] for item in regions]
    if actual != expected:
        errors.append(f"细纲区域必须为导语、连续数字节、尾声: {actual}")
    return {"regions": regions, "errors": errors}


def _public_source(spec: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(spec[key]) for key in (
        "source_id",
        "name",
        "role",
        "prose_voice",
        "emotion_transfer",
        "selected_bridge_ids",
        "original",
        "plot_ledger",
        "emotion_ledger",
        "subflow_catalog",
    )}


def _source_ref(source_id: str, beat: dict[str, Any]) -> str:
    return f"{source_id}:{str(beat.get('beat_id') or '').strip()}"


def expected_sequences(specs: list[dict[str, Any]]) -> dict[str, Any]:
    primary = specs[0]
    return {
        "primary_plot_refs": [_source_ref(primary["source_id"], beat) for beat in primary["plot_beats"]],
        "primary_emotion_refs": [_source_ref(primary["source_id"], beat) for beat in primary["emotion_beats"]],
        "primary_prose_subflow_refs": [
            f"{primary['source_id']}:{str(item.get('subflow_id') or '').strip()}"
            for item in primary["prose_subflows"]
        ],
        "auxiliary_plot_refs": {
            spec["source_id"]: [_source_ref(spec["source_id"], beat) for beat in spec["plot_beats"]]
            for spec in specs[1:]
        },
    }


def build_granularity_coverage(
    specs: list[dict[str, Any]], outline_catalog: dict[str, Any], mapping: dict[str, Any]
) -> list[dict[str, Any]]:
    primary = specs[0]
    targets = mapping.get("primary_plot_targets") or []
    target_regions = {
        beat["target_id"]: region["region_id"]
        for region in outline_catalog.get("regions") or []
        for beat in region.get("target_beats") or []
    }
    plot_pairs = list(zip(primary["plot_beats"], targets))
    result: list[dict[str, Any]] = []
    for subflow in primary["prose_subflows"]:
        subflow_id = str(subflow["subflow_id"]).strip()
        sf_start, sf_end = _line_range(
            subflow.get("source_range"), f"主体子流程 {subflow_id}.source_range"
        )
        overlapping: list[tuple[dict[str, Any], str]] = []
        for beat, target in plot_pairs:
            beat_id = str(beat.get("beat_id") or "").strip()
            beat_start, beat_end = _line_range(
                beat.get("source_range"), f"主体情节拍 {beat_id}.source_range"
            )
            if beat_start <= sf_end and sf_start <= beat_end:
                overlapping.append((beat, str(target or "").strip()))
        if not overlapping and len(targets) == len(primary["plot_beats"]):
            raise ValueError(f"主体子流程 {subflow_id} 没有可按行区间关联的主体 P 拍")
        regions: list[str] = []
        for _, target in overlapping:
            region = target_regions.get(target)
            if region and region not in regions:
                regions.append(region)
        result.append(
            {
                "source_ref": f"{primary['source_id']}:{subflow_id}",
                "parent_bridge_id": str(subflow.get("parent_bridge_id") or "").strip(),
                "source_range": str(subflow.get("source_range") or "").strip(),
                "style_dimensions": list(SOURCE_STYLE_GRANULARITY_FIELDS),
                "target_regions": regions,
            }
        )
    return result


def build_sections(
    outline_catalog: dict[str, Any],
    sequences: dict[str, Any],
    mapping: dict[str, Any],
    granularity_coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    plot_pairs = dict(zip(sequences["primary_plot_refs"], mapping.get("primary_plot_targets") or []))
    emotion_pairs = dict(zip(sequences["primary_emotion_refs"], mapping.get("primary_emotion_targets") or []))
    aux_pairs = {
        source_id: dict(zip(refs, (mapping.get("auxiliary_plot_targets") or {}).get(source_id) or []))
        for source_id, refs in sequences["auxiliary_plot_refs"].items()
    }
    target_region: dict[str, str] = {}
    for region in outline_catalog["regions"]:
        for beat in region["target_beats"]:
            target_region[beat["target_id"]] = region["region_id"]
    sections: list[dict[str, Any]] = []
    numeric_region_ids = [
        region["region_id"]
        for region in outline_catalog["regions"]
        if region["region_id"].startswith("section:")
    ]
    for region in outline_catalog["regions"]:
        if not region["region_id"].startswith("section:"):
            continue
        section_id = region["region_id"].split(":", 1)[1]
        plot_refs = [ref for ref, target in plot_pairs.items() if target_region.get(target) == region["region_id"]]
        emotion_refs = [ref for ref, target in emotion_pairs.items() if target_region.get(target) == region["region_id"]]
        auxiliary_refs = [
            ref
            for pairs in aux_pairs.values()
            for ref, target in pairs.items()
            if target_region.get(target) == region["region_id"]
        ]
        covered_regions = {region["region_id"]}
        if numeric_region_ids and region["region_id"] == numeric_region_ids[-1]:
            covered_regions.add("epilogue")
        prose_subflow_refs = [
            item["source_ref"]
            for item in granularity_coverage
            if covered_regions.intersection(item["target_regions"])
        ]
        target_chars = region["target_chars"]
        sections.append(
            {
                "section_id": section_id,
                "target_chars": deepcopy(target_chars),
                "outline_evidence": [beat["evidence"] for beat in region["target_beats"]],
                "scene_units": [
                    {
                        "scene_id": f"S{section_id}-01",
                        "summary": region["scene_summary"],
                        "allocated_chars": (target_chars["min"] + target_chars["max"]) // 2,
                        "emotion_beat_ids": [ref.split(":", 1)[1] for ref in emotion_refs],
                        "plot_beat_ids": [ref.split(":", 1)[1] for ref in plot_refs],
                        "auxiliary_plot_beat_refs": auxiliary_refs,
                        "prose_subflow_refs": prose_subflow_refs,
                        "prose_style_dimensions": list(SOURCE_STYLE_GRANULARITY_FIELDS),
                    }
                ],
            }
        )
    return sections


def create_receipt(project: str, outline_path: Path, config_path: Path) -> dict[str, Any]:
    outline = outline_path.resolve()
    config = config_path.resolve()
    specs = source_specs(config)
    if not specs or specs[0]["role"] != "primary":
        raise ValueError("项目必须有且只有第一项主体来源")
    catalog = parse_outline(outline)
    sequences = expected_sequences(specs)
    mapping = {
        "primary_plot_targets": [],
        "primary_emotion_targets": [],
        "auxiliary_plot_targets": {source_id: [] for source_id in sequences["auxiliary_plot_refs"]},
    }
    granularity_coverage = build_granularity_coverage(specs, catalog, mapping)
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "created_at": now_iso(),
        "gate_status": "pending",
        "outline": binding(outline),
        "project_config": binding(config),
        "sources": [_public_source(spec) for spec in specs],
        "outline_catalog": catalog,
        "mapping": mapping,
        "granularity_coverage": granularity_coverage,
        "manual_confirmation": {
            "primary_plot_complete_and_in_order": None,
            "primary_emotion_complete_and_in_order": None,
            "auxiliary_is_plot_mechanism_only": None,
            "primary_is_exclusive_prose_voice": None,
            "primary_full_prose_granularity_loaded": None,
            "manual_judgment": "",
        },
        "sections": build_sections(catalog, sequences, mapping, granularity_coverage),
        "blocking_failures": list(catalog["errors"]),
    }


def _source_hint(spec: dict[str, Any], beat: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "plot":
        summary = " / ".join(
            str(beat.get(key) or "").strip()
            for key in ("actor", "action", "object_or_receiver", "consequence")
            if str(beat.get(key) or "").strip()
        )
    else:
        summary = " / ".join(
            str(beat.get(key) or "").strip()
            for key in ("role", "trigger", "relationship_position_change", "reader_effect")
            if str(beat.get(key) or "").strip()
        )
    evidence = beat.get("source_evidence")
    if isinstance(evidence, list):
        evidence = next((str(item).strip() for item in evidence if str(item).strip()), "")
    return {
        "source_ref": _source_ref(spec["source_id"], beat),
        "bridge_ids": list(beat.get("bid_ids") or []),
        "summary": summary,
        "source_evidence": str(evidence or "").strip(),
    }


def export_template(receipt_path: Path, output_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲迁移合同")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("只能从紧凑纲层迁移合同导出模板")
    config_path = Path(receipt["project_config"]["path"])
    specs = source_specs(config_path)
    manual_confirmation = deepcopy(receipt["manual_confirmation"])
    manual_confirmation.setdefault("primary_full_prose_granularity_loaded", None)
    template = {
        "schema_version": TEMPLATE_SCHEMA,
        "receipt_path": str(receipt_path.resolve()),
        "receipt_sha256": sha256(receipt_path),
        "instructions": "三个 targets 数组分别与对应 source 序列等长同序；每项只填一个 target_id。",
        "target_catalog": [
            {
                "region_id": region["region_id"],
                "target_beats": deepcopy(region["target_beats"]),
            }
            for region in receipt["outline_catalog"]["regions"]
        ],
        "source_sequences": {
            "primary_plot": [_source_hint(specs[0], beat, "plot") for beat in specs[0]["plot_beats"]],
            "primary_emotion": [_source_hint(specs[0], beat, "emotion") for beat in specs[0]["emotion_beats"]],
            "auxiliary_plot": {
                spec["source_id"]: [_source_hint(spec, beat, "plot") for beat in spec["plot_beats"]]
                for spec in specs[1:]
            },
        },
        "mapping": deepcopy(receipt["mapping"]),
        "manual_confirmation": manual_confirmation,
    }
    write_json(output_path, template)
    return template


def _target_rank(catalog: dict[str, Any]) -> dict[str, int]:
    return {
        beat["target_id"]: rank
        for rank, beat in enumerate(
            beat
            for region in catalog.get("regions") or []
            for beat in region.get("target_beats") or []
        )
    }


def _validate_target_sequence(
    targets: Any, refs: list[str], ranks: dict[str, int], label: str, errors: list[str]
) -> list[str]:
    if not isinstance(targets, list):
        errors.append(f"{label} 必须是列表")
        return []
    normalized = [str(item or "").strip() for item in targets]
    if len(normalized) != len(refs):
        errors.append(f"{label} 必须与来源序列等长: expected={len(refs)}, actual={len(normalized)}")
        return normalized
    unknown = [item for item in normalized if item not in ranks]
    if unknown:
        errors.append(f"{label} 含未知 target_id: {unknown[:8]}")
    if len(normalized) != len(set(normalized)):
        errors.append(f"{label} 不得把多个同类来源拍并到同一目标细拍")
    known_ranks = [ranks[item] for item in normalized if item in ranks]
    if known_ranks != sorted(known_ranks):
        errors.append(f"{label} 必须保持来源原序，不能跨目标区域倒序")
    return normalized


def validate_data(data: dict[str, Any], outline_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version 必须为 {SCHEMA_VERSION}"]
    try:
        config_binding = data.get("project_config") or {}
        config_path = Path(str(config_binding.get("path") or "")).resolve()
        if not config_path.is_file() or config_binding.get("sha256") != sha256(config_path):
            errors.append("项目写作配置绑定失效")
            return errors
        specs = source_specs(config_path)
        outline_binding = data.get("outline") or {}
        bound_outline = Path(str(outline_binding.get("path") or "")).resolve()
        actual_outline = outline_path.resolve() if outline_path else bound_outline
        if actual_outline != bound_outline:
            errors.append("--outline 与合同绑定路径不一致")
        if not bound_outline.is_file() or outline_binding.get("sha256") != sha256(bound_outline):
            errors.append("小节大纲绑定失效")
            return errors
        actual_catalog = parse_outline(bound_outline)
        if actual_catalog != data.get("outline_catalog"):
            errors.append("outline_catalog 与当前小节大纲的确定性解析结果不一致")
        errors.extend(actual_catalog["errors"])
        expected_sources = [_public_source(spec) for spec in specs]
        if data.get("sources") != expected_sources:
            errors.append("sources 与项目配置及来源账本不一致")
        sequences = expected_sequences(specs)
        mapping = data.get("mapping") or {}
        ranks = _target_rank(actual_catalog)
        _validate_target_sequence(
            mapping.get("primary_plot_targets"),
            sequences["primary_plot_refs"],
            ranks,
            "mapping.primary_plot_targets",
            errors,
        )
        _validate_target_sequence(
            mapping.get("primary_emotion_targets"),
            sequences["primary_emotion_refs"],
            ranks,
            "mapping.primary_emotion_targets",
            errors,
        )
        aux_targets = mapping.get("auxiliary_plot_targets")
        if not isinstance(aux_targets, dict) or set(aux_targets) != set(sequences["auxiliary_plot_refs"]):
            errors.append("mapping.auxiliary_plot_targets 必须与选中辅助来源完全一致")
            aux_targets = aux_targets if isinstance(aux_targets, dict) else {}
        for source_id, refs in sequences["auxiliary_plot_refs"].items():
            _validate_target_sequence(
                aux_targets.get(source_id), refs, ranks,
                f"mapping.auxiliary_plot_targets.{source_id}", errors,
            )
        confirmation = data.get("manual_confirmation")
        if not isinstance(confirmation, dict):
            errors.append("manual_confirmation 必须是对象")
        else:
            for field in (
                "primary_plot_complete_and_in_order",
                "primary_emotion_complete_and_in_order",
                "auxiliary_is_plot_mechanism_only",
                "primary_is_exclusive_prose_voice",
                "primary_full_prose_granularity_loaded",
            ):
                if confirmation.get(field) is not True:
                    errors.append(f"manual_confirmation.{field} 必须为 true")
            if len(str(confirmation.get("manual_judgment") or "").strip()) < 30:
                errors.append("manual_confirmation.manual_judgment 至少 30 字")
        expected_coverage = build_granularity_coverage(specs, actual_catalog, mapping)
        if data.get("granularity_coverage") != expected_coverage:
            errors.append("granularity_coverage 必须由主体子流程、P 拍映射和原文行区间确定性生成")
        empty_subflows = [
            item["source_ref"]
            for item in expected_coverage
            if not item["target_regions"]
        ]
        if empty_subflows:
            errors.append(f"主体文字子流程未映射到目标区域: {empty_subflows}")
        expected_sections = build_sections(
            actual_catalog, sequences, mapping, expected_coverage
        )
        if data.get("sections") != expected_sections:
            errors.append("sections 必须由当前映射和细纲确定性生成，不得人工改写")
    except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def validate_receipt(receipt_path: Path, outline_path: Path | None = None) -> list[str]:
    return validate_data(read_json(receipt_path, "细纲迁移合同"), outline_path)


def apply_template(receipt_path: Path, template_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲迁移合同")
    template = read_json(template_path, "纲层迁移侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError(f"侧车 schema_version 必须为 {TEMPLATE_SCHEMA}")
    if Path(str(template.get("receipt_path") or "")).resolve() != receipt_path.resolve():
        raise ValueError("侧车 receipt_path 与正式合同不一致")
    if template.get("receipt_sha256") != sha256(receipt_path):
        raise ValueError("侧车绑定的正式合同 SHA 已失效，请重新导出")
    merged = deepcopy(receipt)
    merged["mapping"] = deepcopy(template.get("mapping"))
    merged["manual_confirmation"] = deepcopy(template.get("manual_confirmation"))
    specs = source_specs(Path(merged["project_config"]["path"]))
    sequences = expected_sequences(specs)
    merged["sources"] = [_public_source(spec) for spec in specs]
    coverage = build_granularity_coverage(
        specs, merged["outline_catalog"], merged["mapping"]
    )
    merged["granularity_coverage"] = coverage
    merged["sections"] = build_sections(
        merged["outline_catalog"], sequences, merged["mapping"], coverage
    )
    merged["gate_status"] = "pending"
    merged["blocking_failures"] = []
    errors = validate_data(merged)
    if errors:
        raise ValueError("；".join(errors))
    merged["gate_status"] = "passed"
    merged["reviewed_at"] = now_iso()
    write_json(receipt_path, merged)
    return merged


def _catalog_from_template(template: dict[str, Any]) -> dict[str, Any]:
    regions = template.get("target_catalog")
    if not isinstance(regions, list):
        raise ValueError("纲层迁移侧车缺少 target_catalog")
    return {"regions": deepcopy(regions), "errors": []}


def _mapping_has_targets(mapping: Any) -> bool:
    if not isinstance(mapping, dict):
        return False
    if mapping.get("primary_plot_targets") or mapping.get("primary_emotion_targets"):
        return True
    auxiliaries = mapping.get("auxiliary_plot_targets")
    return isinstance(auxiliaries, dict) and any(auxiliaries.values())


def _preservation_source(
    receipt_path: Path, receipt: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    mapping = receipt.get("mapping")
    if _mapping_has_targets(mapping):
        return (
            deepcopy(receipt.get("outline_catalog") or {}),
            deepcopy(mapping),
            deepcopy(receipt.get("manual_confirmation") or {}),
        )

    sidecar_path = receipt_path.with_name("纲层迁移侧车.json")
    if not sidecar_path.is_file():
        raise ValueError("当前合同没有可迁移映射，且未找到同目录纲层迁移侧车")
    template = read_json(sidecar_path, "纲层迁移侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError(f"纲层迁移侧车 schema_version 必须为 {TEMPLATE_SCHEMA}")
    if Path(str(template.get("receipt_path") or "")).resolve() != receipt_path.resolve():
        raise ValueError("纲层迁移侧车 receipt_path 与正式合同不一致")
    template_mapping = template.get("mapping")
    if not _mapping_has_targets(template_mapping):
        raise ValueError("纲层迁移侧车没有可迁移映射")
    return (
        _catalog_from_template(template),
        deepcopy(template_mapping),
        deepcopy(template.get("manual_confirmation") or {}),
    )


def _targets_by_evidence(catalog: dict[str, Any], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    duplicates: set[str] = set()
    for region in catalog.get("regions") or []:
        for beat in region.get("target_beats") or []:
            evidence = str(beat.get("evidence") or "").strip()
            target_id = str(beat.get("target_id") or "").strip()
            if not evidence or not target_id:
                raise ValueError(f"{label} 含缺少 evidence 或 target_id 的细拍")
            if evidence in result:
                duplicates.add(evidence)
            result[evidence] = target_id
    if duplicates:
        raise ValueError(f"{label} 存在重复细拍证据，无法确定性迁移: {sorted(duplicates)[:3]}")
    return result


def migrate_mapping_by_evidence(
    old_catalog: dict[str, Any],
    new_catalog: dict[str, Any],
    old_mapping: dict[str, Any],
) -> dict[str, Any]:
    old_targets = {
        str(beat.get("target_id") or "").strip(): str(beat.get("evidence") or "").strip()
        for region in old_catalog.get("regions") or []
        for beat in region.get("target_beats") or []
    }
    new_targets = _targets_by_evidence(new_catalog, "新细纲")

    def migrate(targets: Any, label: str) -> list[str]:
        if not isinstance(targets, list):
            raise ValueError(f"{label} 必须是列表")
        migrated: list[str] = []
        for target in targets:
            old_target = str(target or "").strip()
            evidence = old_targets.get(old_target)
            if not evidence:
                raise ValueError(f"{label} 含旧细纲未知 target_id: {old_target}")
            new_target = new_targets.get(evidence)
            if not new_target:
                raise ValueError(f"{label} 的细拍证据已被改写或删除: {evidence}")
            migrated.append(new_target)
        return migrated

    auxiliary = old_mapping.get("auxiliary_plot_targets")
    if not isinstance(auxiliary, dict):
        raise ValueError("mapping.auxiliary_plot_targets 必须是对象")
    return {
        "primary_plot_targets": migrate(
            old_mapping.get("primary_plot_targets"), "mapping.primary_plot_targets"
        ),
        "primary_emotion_targets": migrate(
            old_mapping.get("primary_emotion_targets"), "mapping.primary_emotion_targets"
        ),
        "auxiliary_plot_targets": {
            source_id: migrate(targets, f"mapping.auxiliary_plot_targets.{source_id}")
            for source_id, targets in auxiliary.items()
        },
    }


def rebind_outline(
    receipt_path: Path,
    outline_path: Path,
    preserve_by_evidence: bool = False,
) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲迁移合同")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("只能重绑紧凑纲层迁移合同")
    specs = source_specs(Path(receipt["project_config"]["path"]))
    sequences = expected_sequences(specs)
    catalog = parse_outline(outline_path.resolve())
    if catalog["errors"]:
        raise ValueError("；".join(catalog["errors"]))
    if preserve_by_evidence:
        old_catalog, old_mapping, manual_confirmation = _preservation_source(
            receipt_path, receipt
        )
        mapping = migrate_mapping_by_evidence(old_catalog, catalog, old_mapping)
    else:
        mapping = {
            "primary_plot_targets": [],
            "primary_emotion_targets": [],
            "auxiliary_plot_targets": {
                source_id: [] for source_id in sequences["auxiliary_plot_refs"]
            },
        }
        manual_confirmation = {
            "primary_plot_complete_and_in_order": None,
            "primary_emotion_complete_and_in_order": None,
            "auxiliary_is_plot_mechanism_only": None,
            "primary_is_exclusive_prose_voice": None,
            "primary_full_prose_granularity_loaded": None,
            "manual_judgment": "",
        }
    coverage = build_granularity_coverage(specs, catalog, mapping)
    receipt["outline"] = binding(outline_path)
    receipt["outline_catalog"] = catalog
    receipt["mapping"] = mapping
    receipt["granularity_coverage"] = coverage
    receipt["manual_confirmation"] = manual_confirmation
    receipt["sections"] = build_sections(catalog, sequences, mapping, coverage)
    receipt["gate_status"] = "pending"
    receipt["blocking_failures"] = []
    receipt["rebound_at"] = now_iso()
    if preserve_by_evidence:
        errors = validate_data(receipt)
        if errors:
            raise ValueError("；".join(errors))
        receipt["gate_status"] = "passed"
        receipt["reviewed_at"] = now_iso()
    write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--project-config", required=True)
    init.add_argument("--receipt", required=True)
    export = sub.add_parser("export-template")
    export.add_argument("--receipt", required=True)
    export.add_argument("--output", required=True)
    apply = sub.add_parser("apply-template")
    apply.add_argument("--receipt", required=True)
    apply.add_argument("--input", required=True)
    rebind = sub.add_parser("rebind-outline")
    rebind.add_argument("--receipt", required=True)
    rebind.add_argument("--outline", required=True)
    rebind.add_argument("--preserve-by-evidence", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--outline")
    args = parser.parse_args()
    try:
        if args.command == "init":
            receipt_path = Path(args.receipt).resolve()
            if receipt_path.exists():
                raise ValueError(f"回执已存在，拒绝覆盖: {receipt_path}")
            write_json(
                receipt_path,
                create_receipt(
                    args.project,
                    Path(args.outline).resolve(),
                    Path(args.project_config).resolve(),
                ),
            )
            print("outline_migration_contract: initialized")
            return 0
        if args.command == "export-template":
            export_template(Path(args.receipt).resolve(), Path(args.output).resolve())
            print("outline_migration_contract: template_exported")
            return 0
        if args.command == "apply-template":
            apply_template(Path(args.receipt).resolve(), Path(args.input).resolve())
            print("outline_migration_contract: passed")
            return 0
        if args.command == "rebind-outline":
            rebind_outline(
                Path(args.receipt).resolve(),
                Path(args.outline).resolve(),
                preserve_by_evidence=args.preserve_by_evidence,
            )
            print("outline_migration_contract: rebound")
            return 0
        errors = validate_receipt(
            Path(args.receipt).resolve(),
            Path(args.outline).resolve() if args.outline else None,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("outline_migration_contract: blocked")
        print(f"- {exc}")
        return 2
    if errors:
        print("outline_migration_contract: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("outline_migration_contract: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
