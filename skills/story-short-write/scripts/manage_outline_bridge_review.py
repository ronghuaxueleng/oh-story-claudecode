#!/usr/bin/env python3
"""Export/apply bridge-level manual review sidecars for outline performance receipts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_lifecycle import consume_sidecar, refresh_sidecar_receipt_sha


TEMPLATE_SCHEMA = "story-short-write.outline-bridge-review-template.v1"
BEAT_TEMPLATE_SCHEMA = "story-short-write.outline-bridge-beat-review-template.v1"
EMOTION_SYNC_SCHEMA = "story-short-write.outline-bridge-source-emotion-sync.v1"
BRIDGE_FIELDS = (
    "target_outline_sections",
    "target_outline_evidence",
    "plot_granularity_parity_judgment",
    "emotion_parity_judgment",
    "reader_experience_parity",
    "parity_status",
    "adaptation_reason",
    "missing_or_weakened_risk",
    "manual_judgment",
)
BRIDGE_CONTEXT_FIELDS = (
    "source_path",
    "source_sha256",
    "emotion_transfer_policy",
    "source_required_sequence",
    "source_must_keep_actions",
    "source_scene_granularity",
    "source_plot_beats",
    "source_emotion_sequence",
    "target_outline_sections",
    "target_outline_evidence",
)
BRIDGE_BEAT_FIELDS = (
    "target_plot_beats",
    "plot_beat_mapping",
    "target_emotion_sequence",
    "source_reversal_beat",
    "target_reversal_beat",
    "source_peak_beat",
    "target_peak_beat",
)
OUTSIDE_BEAT_FIELDS = (
    "target_plot_beats",
    "plot_beat_mapping",
)
SOURCE_EMOTION_FIELDS = (
    "beat_id",
    "role",
    "trigger",
    "relationship_position_change",
    "reader_effect",
    "intensity",
    "evidence",
)
VALIDATOR_PATH = Path(__file__).resolve().parent / "validate_outline_performance_contract.py"


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


def load_outline_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_outline_performance_contract", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载细纲表演校验器: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def emotion_ledger_path_for_source(source_path: Path) -> Path:
    return source_path.resolve().parent.parent / "写作资产" / "全文情绪颗粒总账.json"


def _source_evidence_text(beat: dict[str, Any]) -> str:
    evidence = beat.get("source_evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, str) and item.strip():
                return item.strip()
    if isinstance(evidence, str) and evidence.strip():
        return evidence.strip()
    return ""


def _normalize_source_emotion_beat(beat: dict[str, Any], label: str) -> dict[str, Any]:
    normalized = {
        "beat_id": str(beat.get("beat_id") or "").strip(),
        "role": str(beat.get("role") or "").strip(),
        "trigger": str(beat.get("trigger") or "").strip(),
        "relationship_position_change": str(beat.get("relationship_position_change") or "").strip(),
        "reader_effect": str(beat.get("reader_effect") or "").strip(),
        "intensity": beat.get("intensity"),
        "evidence": _source_evidence_text(beat),
    }
    for field in SOURCE_EMOTION_FIELDS[:-2]:
        if not normalized[field]:
            raise ValueError(f"{label}.{field} 缺失，无法同步桥级原文情绪序列")
    if not isinstance(normalized["intensity"], (int, float)):
        raise ValueError(f"{label}.intensity 缺失，无法同步桥级原文情绪序列")
    if not normalized["evidence"]:
        raise ValueError(f"{label}.source_evidence 缺失，无法同步桥级原文情绪序列")
    return normalized


def _ledger_emotion_sequence(ledger_path: Path, bridge_id: str | None) -> list[dict[str, Any]]:
    ledger = read_json(ledger_path, "全文情绪颗粒总账")
    beats = ledger.get("beats")
    if not isinstance(beats, list):
        raise ValueError(f"全文情绪颗粒总账缺少 beats 列表: {ledger_path}")
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(beats):
        if not isinstance(raw, dict):
            raise ValueError(f"全文情绪颗粒总账 beats[{index}] 必须是对象: {ledger_path}")
        bid_ids = raw.get("bid_ids") or []
        if not isinstance(bid_ids, list):
            raise ValueError(f"全文情绪颗粒总账 beats[{index}].bid_ids 必须是列表: {ledger_path}")
        include = (bridge_id is None and not bid_ids) or (bridge_id is not None and bridge_id in bid_ids)
        if include:
            result.append(_normalize_source_emotion_beat(raw, f"beats[{index}]"))
    return result


def sync_source_emotions(receipt_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    merged = deepcopy(receipt)
    bridges = merged.get("outline_bridge_flow_parity")
    if not isinstance(bridges, list):
        raise ValueError("回执缺少 outline_bridge_flow_parity 列表")

    ledger_cache: dict[Path, list[dict[str, Any]]] = {}

    def load_sequence(source_path_str: str, bridge_id: str | None) -> list[dict[str, Any]]:
        source_path = Path(source_path_str).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"原文不存在，无法同步桥级原文情绪序列: {source_path}")
        ledger_path = emotion_ledger_path_for_source(source_path)
        cache_key = ledger_path if bridge_id is None else Path(f"{ledger_path}::{bridge_id}")
        if cache_key not in ledger_cache:
            ledger_cache[cache_key] = _ledger_emotion_sequence(ledger_path, bridge_id)
        return deepcopy(ledger_cache[cache_key])

    outside = merged.get("outside_bridge_plot_parity")
    if isinstance(outside, dict):
        source_path_str = str(outside.get("source_path") or "").strip()
        if not source_path_str:
            first_source = next(
                (
                    str(item.get("source_path") or "").strip()
                    for item in bridges
                    if isinstance(item, dict) and str(item.get("source_path") or "").strip()
                ),
                "",
            )
            source_path_str = first_source
        if not source_path_str:
            raise ValueError("outside_bridge_plot_parity 缺少 source_path，且无法从桥级记录继承")
        outside["source_emotion_sequence"] = load_sequence(source_path_str, None)

    for index, entry in enumerate(bridges):
        if not isinstance(entry, dict):
            raise ValueError(f"outline_bridge_flow_parity[{index}] 必须是对象")
        bridge_id = str(entry.get("source_bridge_id") or "").strip()
        source_path_str = str(entry.get("source_path") or "").strip()
        if not bridge_id:
            raise ValueError(f"outline_bridge_flow_parity[{index}].source_bridge_id 不能为空")
        if not source_path_str:
            raise ValueError(f"outline_bridge_flow_parity[{index}].source_path 不能为空")
        if str(entry.get("emotion_transfer_policy") or "").strip() == "plot_mechanism_only":
            entry["source_emotion_sequence"] = []
            continue
        entry["source_emotion_sequence"] = load_sequence(source_path_str, bridge_id)

    write_json(receipt_path, merged)
    return {
        "schema_version": EMOTION_SYNC_SCHEMA,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "outside_count": len((merged.get("outside_bridge_plot_parity") or {}).get("source_emotion_sequence", []))
        if isinstance(merged.get("outside_bridge_plot_parity"), dict)
        else 0,
        "bridge_counts": {
            f"{_normalized_source_path(entry.get('source_path'))}::{str(entry.get('source_bridge_id') or '')}":
            len(entry.get("source_emotion_sequence") or [])
            for entry in bridges
            if isinstance(entry, dict)
        },
    }


def _bridge_sidecar_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_bridge_id": entry.get("source_bridge_id", ""),
        "source_bridge_name": entry.get("source_bridge_name", ""),
        **{field: deepcopy(entry.get(field)) for field in BRIDGE_CONTEXT_FIELDS},
        **{field: deepcopy(entry.get(field)) for field in BRIDGE_FIELDS},
    }


def _compact_plot_beats(beats: Any) -> list[dict[str, Any]]:
    if not isinstance(beats, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in beats:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "beat_id": deepcopy(item.get("beat_id")),
                "action": deepcopy(item.get("action")),
                "object_or_receiver": deepcopy(item.get("object_or_receiver")),
                "consequence": deepcopy(item.get("consequence")),
                "evidence": deepcopy(item.get("evidence")),
            }
        )
    return compact


def _bridge_sidecar_entry_compact(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_bridge_id": entry.get("source_bridge_id", ""),
        "source_bridge_name": entry.get("source_bridge_name", ""),
        "source_path": deepcopy(entry.get("source_path")),
        "source_sha256": deepcopy(entry.get("source_sha256")),
        "emotion_transfer_policy": deepcopy(entry.get("emotion_transfer_policy")),
        "source_scene_granularity": deepcopy(entry.get("source_scene_granularity")),
        "source_required_sequence": deepcopy(entry.get("source_required_sequence")),
        "source_must_keep_actions": deepcopy(entry.get("source_must_keep_actions")),
        "source_plot_beats": _compact_plot_beats(entry.get("source_plot_beats")),
        "source_emotion_sequence": deepcopy(entry.get("source_emotion_sequence")),
        "target_outline_sections": deepcopy(entry.get("target_outline_sections")),
        "target_outline_evidence": deepcopy(entry.get("target_outline_evidence")),
        **{field: deepcopy(entry.get(field)) for field in BRIDGE_FIELDS},
    }


def _normalize_bridge_filter(bridge_ids: list[str] | None) -> set[str]:
    if not bridge_ids:
        return set()
    return {str(item).strip() for item in bridge_ids if str(item).strip()}


def export_template(
    receipt_path: Path,
    output_path: Path,
    bridge_ids: list[str] | None = None,
    compact_context: bool = False,
) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    bridges = receipt.get("outline_bridge_flow_parity")
    outside = receipt.get("outside_bridge_plot_parity")
    if not isinstance(bridges, list):
        raise ValueError("回执缺少 outline_bridge_flow_parity 列表")
    if outside is not None and not isinstance(outside, dict):
        raise ValueError("outside_bridge_plot_parity 必须是对象")
    selected_bridge_ids = _normalize_bridge_filter(bridge_ids)
    filtered_bridges = [
        entry
        for entry in bridges
        if isinstance(entry, dict)
        and (
            not selected_bridge_ids
            or str(entry.get("source_bridge_id") or "").strip() in selected_bridge_ids
        )
    ]

    payload: dict[str, Any] = {
        "schema_version": TEMPLATE_SCHEMA,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "outside_bridge_plot_parity": None,
        "outline_bridge_flow_parity": [],
    }
    first_bridge = next((entry for entry in filtered_bridges if isinstance(entry, dict)), None)
    if isinstance(outside, dict) and not selected_bridge_ids:
        payload["outside_bridge_plot_parity"] = {
            "source_bridge_id": "outside",
            "source_path": deepcopy(outside.get("source_path") or (first_bridge or {}).get("source_path")),
            "source_sha256": deepcopy(outside.get("source_sha256") or (first_bridge or {}).get("source_sha256")),
            "source_plot_beats": deepcopy(outside.get("source_plot_beats")),
            "source_emotion_sequence": deepcopy(outside.get("source_emotion_sequence")),
            **{field: deepcopy(outside.get(field)) for field in BRIDGE_FIELDS},
        }
    payload["outline_bridge_flow_parity"] = [
        (_bridge_sidecar_entry_compact(entry) if compact_context else _bridge_sidecar_entry(entry))
        for entry in filtered_bridges
    ]
    write_json(output_path, payload)
    return payload


def _bridge_beat_sidecar_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_bridge_id": entry.get("source_bridge_id", ""),
        "source_bridge_name": entry.get("source_bridge_name", ""),
        **{field: deepcopy(entry.get(field)) for field in BRIDGE_CONTEXT_FIELDS},
        **{field: deepcopy(entry.get(field)) for field in BRIDGE_BEAT_FIELDS},
    }


def _bridge_beat_sidecar_entry_compact(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_bridge_id": entry.get("source_bridge_id", ""),
        "source_bridge_name": entry.get("source_bridge_name", ""),
        "source_path": deepcopy(entry.get("source_path")),
        "source_sha256": deepcopy(entry.get("source_sha256")),
        "emotion_transfer_policy": deepcopy(entry.get("emotion_transfer_policy")),
        "source_scene_granularity": deepcopy(entry.get("source_scene_granularity")),
        "source_required_sequence": deepcopy(entry.get("source_required_sequence")),
        "source_must_keep_actions": deepcopy(entry.get("source_must_keep_actions")),
        "source_plot_beats": _compact_plot_beats(entry.get("source_plot_beats")),
        "source_emotion_sequence": deepcopy(entry.get("source_emotion_sequence")),
        "target_outline_sections": deepcopy(entry.get("target_outline_sections")),
        "target_outline_evidence": deepcopy(entry.get("target_outline_evidence")),
        **{field: deepcopy(entry.get(field)) for field in BRIDGE_BEAT_FIELDS},
    }


def export_beat_template(
    receipt_path: Path,
    output_path: Path,
    bridge_ids: list[str] | None = None,
    compact_context: bool = False,
) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    bridges = receipt.get("outline_bridge_flow_parity")
    outside = receipt.get("outside_bridge_plot_parity")
    if not isinstance(bridges, list):
        raise ValueError("回执缺少 outline_bridge_flow_parity 列表")
    if outside is not None and not isinstance(outside, dict):
        raise ValueError("outside_bridge_plot_parity 必须是对象")
    selected_bridge_ids = _normalize_bridge_filter(bridge_ids)
    filtered_bridges = [
        entry
        for entry in bridges
        if isinstance(entry, dict)
        and (
            not selected_bridge_ids
            or str(entry.get("source_bridge_id") or "").strip() in selected_bridge_ids
        )
    ]

    payload: dict[str, Any] = {
        "schema_version": BEAT_TEMPLATE_SCHEMA,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "outside_bridge_plot_parity": None,
        "outline_bridge_flow_parity": [
            (_bridge_beat_sidecar_entry_compact(entry) if compact_context else _bridge_beat_sidecar_entry(entry))
            for entry in filtered_bridges
        ],
    }
    first_bridge = next((entry for entry in filtered_bridges if isinstance(entry, dict)), None)
    if isinstance(outside, dict) and not selected_bridge_ids:
        payload["outside_bridge_plot_parity"] = {
            "source_bridge_id": "outside",
            "source_path": deepcopy(outside.get("source_path") or (first_bridge or {}).get("source_path")),
            "source_sha256": deepcopy(outside.get("source_sha256") or (first_bridge or {}).get("source_sha256")),
            "source_plot_beats": deepcopy(outside.get("source_plot_beats")),
            "source_emotion_sequence": deepcopy(outside.get("source_emotion_sequence")),
            "target_outline_sections": deepcopy(outside.get("target_outline_sections")),
            "target_outline_evidence": deepcopy(outside.get("target_outline_evidence")),
            **{field: deepcopy(outside.get(field)) for field in OUTSIDE_BEAT_FIELDS},
        }
    write_json(output_path, payload)
    return payload


def _normalize_string_list(value: Any, field: str, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label}.{field} 必须是字符串列表")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}.{field}[{index}] 必须是非空字符串")
        normalized.append(item)
    return normalized


def _normalized_source_path(value: Any) -> str:
    path_text = str(value or "").strip()
    if not path_text:
        return ""
    return str(Path(path_text).expanduser().resolve())


def _bridge_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (
        _normalized_source_path(entry.get("source_path")),
        str(entry.get("source_bridge_id") or "").strip(),
    )


def _build_bridge_indexes(
    bridges: list[Any], label: str
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, list[tuple[str, str]]]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    by_id: dict[str, list[tuple[str, str]]] = {}
    for index, item in enumerate(bridges):
        if not isinstance(item, dict):
            continue
        key = _bridge_key(item)
        if not key[1]:
            continue
        if key in by_key:
            raise ValueError(
                f"{label}存在重复桥身份: source_path={key[0]!r}, bridge_id={key[1]}"
            )
        by_key[key] = item
        by_id.setdefault(key[1], []).append(key)
    return by_key, by_id


def _resolve_bridge_key(
    entry: dict[str, Any],
    by_key: dict[tuple[str, str], dict[str, Any]],
    by_id: dict[str, list[tuple[str, str]]],
    label: str,
) -> tuple[str, str]:
    source_path, bridge_id = _bridge_key(entry)
    if source_path:
        key = (source_path, bridge_id)
        if key not in by_key:
            raise ValueError(
                f"{label}不存在对应桥: source_path={source_path!r}, bridge_id={bridge_id}"
            )
        return key
    matches = by_id.get(bridge_id, [])
    if not matches:
        raise ValueError(f"{label}不存在 bridge_id={bridge_id} 的桥")
    if len(matches) > 1:
        raise ValueError(
            f"{label}的 bridge_id={bridge_id} 跨来源重名，侧车必须保留 source_path"
        )
    return matches[0]


def _validate_entry(entry: dict[str, Any], label: str) -> dict[str, Any]:
    bridge_id = str(entry.get("source_bridge_id") or "").strip()
    if not bridge_id:
        raise ValueError(f"{label}.source_bridge_id 不能为空")
    result = {
        "source_bridge_id": bridge_id,
        "source_path": _normalized_source_path(entry.get("source_path")),
    }
    if "source_bridge_name" in entry:
        result["source_bridge_name"] = str(entry.get("source_bridge_name") or "").strip()
    result["target_outline_sections"] = _normalize_string_list(
        entry.get("target_outline_sections", []), "target_outline_sections", label
    )
    result["target_outline_evidence"] = _normalize_string_list(
        entry.get("target_outline_evidence", []), "target_outline_evidence", label
    )
    for field in (
        "plot_granularity_parity_judgment",
        "emotion_parity_judgment",
        "adaptation_reason",
        "missing_or_weakened_risk",
        "manual_judgment",
    ):
        value = str(entry.get(field) or "").strip()
        if not value:
            raise ValueError(f"{label}.{field} 不能为空")
        result[field] = value
    reader_experience_parity = entry.get("reader_experience_parity")
    plot_only = (
        str(entry.get("emotion_transfer_policy") or "").strip()
        == "plot_mechanism_only"
    )
    if plot_only:
        if reader_experience_parity is not None:
            raise ValueError(
                f"{label}.reader_experience_parity 在 plot_mechanism_only 模式下必须为 null"
            )
    elif not isinstance(reader_experience_parity, bool):
        raise ValueError(f"{label}.reader_experience_parity 必须为 true/false")
    result["reader_experience_parity"] = reader_experience_parity
    parity_status = str(entry.get("parity_status") or "").strip()
    if parity_status not in {"matched", "adapted"}:
        raise ValueError(f"{label}.parity_status 只能是 matched/adapted")
    result["parity_status"] = parity_status
    return result


def _validate_beat_entry(entry: dict[str, Any], label: str) -> dict[str, Any]:
    bridge_id = str(entry.get("source_bridge_id") or "").strip()
    if not bridge_id:
        raise ValueError(f"{label}.source_bridge_id 不能为空")
    result = {
        "source_bridge_id": bridge_id,
        "source_path": _normalized_source_path(entry.get("source_path")),
    }
    if "source_bridge_name" in entry:
        result["source_bridge_name"] = str(entry.get("source_bridge_name") or "").strip()
    for field in BRIDGE_BEAT_FIELDS:
        result[field] = deepcopy(entry.get(field))
    return result


def _validate_outside_beat_entry(entry: dict[str, Any], label: str) -> dict[str, Any]:
    bridge_id = str(entry.get("source_bridge_id") or "").strip()
    if bridge_id not in {"", "outside"}:
        raise ValueError(f"{label}.source_bridge_id 只能为空或 outside")
    return {
        "source_bridge_id": "outside",
        **{field: deepcopy(entry.get(field)) for field in OUTSIDE_BEAT_FIELDS},
    }


def apply_template(receipt_path: Path, template_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    template = read_json(template_path, "桥级回填侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError("桥级回填侧车 schema_version 不正确")
    expected_sha = str(template.get("receipt_sha256") or "").strip()
    actual_sha = sha256_file(receipt_path)
    if expected_sha and expected_sha != actual_sha:
        raise ValueError("桥级回填侧车绑定的 receipt_sha256 已失效，请重新 export")

    receipt_bridges = receipt.get("outline_bridge_flow_parity")
    if not isinstance(receipt_bridges, list):
        raise ValueError("回执缺少 outline_bridge_flow_parity 列表")
    bridge_index, bridge_id_index = _build_bridge_indexes(
        receipt_bridges, "细纲表演验收回执"
    )
    template_bridges = template.get("outline_bridge_flow_parity")
    if not isinstance(template_bridges, list):
        raise ValueError("桥级回填侧车缺少 outline_bridge_flow_parity 列表")

    merged = deepcopy(receipt)
    merged_bridges = merged["outline_bridge_flow_parity"]
    merged_index, _ = _build_bridge_indexes(merged_bridges, "合并后细纲表演验收回执")
    seen_keys: set[tuple[str, str]] = set()
    for index, raw in enumerate(template_bridges):
        if not isinstance(raw, dict):
            raise ValueError(f"outline_bridge_flow_parity[{index}] 必须是对象")
        entry = _validate_entry(raw, f"outline_bridge_flow_parity[{index}]")
        key = _resolve_bridge_key(
            entry,
            bridge_index,
            bridge_id_index,
            f"outline_bridge_flow_parity[{index}]",
        )
        if key in seen_keys:
            raise ValueError(
                "桥级回填侧车存在重复桥身份: "
                f"source_path={key[0]!r}, bridge_id={key[1]}"
            )
        seen_keys.add(key)
        target = merged_index[key]
        for field in BRIDGE_FIELDS:
            target[field] = deepcopy(entry[field])

    raw_outside = template.get("outside_bridge_plot_parity")
    if raw_outside is not None:
        if not isinstance(raw_outside, dict):
            raise ValueError("outside_bridge_plot_parity 必须是对象或 null")
        outside_entry = _validate_entry(raw_outside, "outside_bridge_plot_parity")
        target = merged.get("outside_bridge_plot_parity")
        if not isinstance(target, dict):
            raise ValueError("回执不存在 outside_bridge_plot_parity")
        for field in BRIDGE_FIELDS:
            target[field] = deepcopy(outside_entry[field])

    write_json(receipt_path, merged)
    return merged


def apply_beat_template(receipt_path: Path, template_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    template = read_json(template_path, "桥级逐拍回填侧车")
    if template.get("schema_version") != BEAT_TEMPLATE_SCHEMA:
        raise ValueError("桥级逐拍回填侧车 schema_version 不正确")
    expected_sha = str(template.get("receipt_sha256") or "").strip()
    actual_sha = sha256_file(receipt_path)
    if expected_sha and expected_sha != actual_sha:
        raise ValueError("桥级逐拍回填侧车绑定的 receipt_sha256 已失效，请重新 export")

    receipt_bridges = receipt.get("outline_bridge_flow_parity")
    if not isinstance(receipt_bridges, list):
        raise ValueError("回执缺少 outline_bridge_flow_parity 列表")
    bridge_index, bridge_id_index = _build_bridge_indexes(
        receipt_bridges, "细纲表演验收回执"
    )
    template_bridges = template.get("outline_bridge_flow_parity")
    if not isinstance(template_bridges, list):
        raise ValueError("桥级逐拍回填侧车缺少 outline_bridge_flow_parity 列表")

    merged = deepcopy(receipt)
    merged_index, _ = _build_bridge_indexes(
        merged.get("outline_bridge_flow_parity", []),
        "合并后细纲表演验收回执",
    )
    seen_keys: set[tuple[str, str]] = set()
    for index, raw in enumerate(template_bridges):
        if not isinstance(raw, dict):
            raise ValueError(f"outline_bridge_flow_parity[{index}] 必须是对象")
        entry = _validate_beat_entry(raw, f"outline_bridge_flow_parity[{index}]")
        key = _resolve_bridge_key(
            entry,
            bridge_index,
            bridge_id_index,
            f"outline_bridge_flow_parity[{index}]",
        )
        if key in seen_keys:
            raise ValueError(
                "桥级逐拍回填侧车存在重复桥身份: "
                f"source_path={key[0]!r}, bridge_id={key[1]}"
            )
        seen_keys.add(key)
        target = merged_index[key]
        for field in BRIDGE_BEAT_FIELDS:
            target[field] = deepcopy(entry[field])

    raw_outside = template.get("outside_bridge_plot_parity")
    if raw_outside is not None:
        if not isinstance(raw_outside, dict):
            raise ValueError("outside_bridge_plot_parity 必须是对象或 null")
        outside_entry = _validate_outside_beat_entry(raw_outside, "outside_bridge_plot_parity")
        target = merged.get("outside_bridge_plot_parity")
        if not isinstance(target, dict):
            raise ValueError("回执不存在 outside_bridge_plot_parity")
        for field in OUTSIDE_BEAT_FIELDS:
            target[field] = deepcopy(outside_entry[field])

    write_json(receipt_path, merged)
    return merged


def rebind_outline(receipt_path: Path, outline_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    if not outline_path.is_file():
        raise FileNotFoundError(f"细纲不存在: {outline_path}")
    merged = deepcopy(receipt)
    merged["outline"] = {"path": str(outline_path), "sha256": sha256_file(outline_path)}
    merged["reviewed_by_current_model"] = False
    merged["gate_status"] = "pending"
    merged["blocking_failures"] = []
    write_json(receipt_path, merged)
    return merged


def seal_review(receipt_path: Path, outline_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    if not outline_path.is_file():
        raise FileNotFoundError(f"细纲不存在: {outline_path}")
    merged = deepcopy(receipt)
    merged["outline"] = {"path": str(outline_path), "sha256": sha256_file(outline_path)}
    merged["reviewed_by_current_model"] = True
    merged["gate_status"] = "passed"
    merged["blocking_failures"] = []

    validator = load_outline_validator()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_receipt = Path(temp_dir) / "细纲表演验收回执.json"
        write_json(temp_receipt, merged)
        errors = validator.validate_receipt(temp_receipt, outline_path)
    if errors:
        raise ValueError(
            "细纲表演验收回执仍未通过，不能 seal-review:\n- " + "\n- ".join(errors)
        )

    write_json(receipt_path, merged)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export/apply bridge-level manual review sidecars for outline performance receipts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export-template")
    export.add_argument("--receipt", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--bridge-id", action="append", default=[])
    export.add_argument("--compact-context", action="store_true")

    export_beat = sub.add_parser("export-beat-template")
    export_beat.add_argument("--receipt", required=True)
    export_beat.add_argument("--output", required=True)
    export_beat.add_argument("--bridge-id", action="append", default=[])
    export_beat.add_argument("--compact-context", action="store_true")

    apply_cmd = sub.add_parser("apply-template")
    apply_cmd.add_argument("--receipt", required=True)
    apply_cmd.add_argument("--input", required=True)
    apply_cmd.add_argument("--consume", action="store_true")
    apply_cmd.add_argument("--refresh-sidecar", action="append", default=[])

    apply_beat_cmd = sub.add_parser("apply-beat-template")
    apply_beat_cmd.add_argument("--receipt", required=True)
    apply_beat_cmd.add_argument("--input", required=True)
    apply_beat_cmd.add_argument("--consume", action="store_true")
    apply_beat_cmd.add_argument("--refresh-sidecar", action="append", default=[])

    sync_cmd = sub.add_parser("sync-source-emotions")
    sync_cmd.add_argument("--receipt", required=True)

    rebind_cmd = sub.add_parser("rebind-outline")
    rebind_cmd.add_argument("--receipt", required=True)
    rebind_cmd.add_argument("--outline", required=True)

    seal_cmd = sub.add_parser("seal-review")
    seal_cmd.add_argument("--receipt", required=True)
    seal_cmd.add_argument("--outline", required=True)

    args = parser.parse_args()
    try:
        if args.command == "export-template":
            payload = export_template(
                Path(args.receipt).resolve(),
                Path(args.output).resolve(),
                args.bridge_id,
                args.compact_context,
            )
            print(
                "outline_bridge_review_template: exported "
                f"({len(payload['outline_bridge_flow_parity'])} bridges)"
            )
            return 0
        if args.command == "export-beat-template":
            payload = export_beat_template(
                Path(args.receipt).resolve(),
                Path(args.output).resolve(),
                args.bridge_id,
                args.compact_context,
            )
            print(
                "outline_bridge_beat_review_template: exported "
                f"({len(payload['outline_bridge_flow_parity'])} bridges)"
            )
            return 0
        if args.command == "sync-source-emotions":
            summary = sync_source_emotions(Path(args.receipt).resolve())
            print("outline_bridge_source_emotions: synced")
            print(
                json.dumps(summary, ensure_ascii=False, indent=2)
            )
            return 0
        if args.command == "rebind-outline":
            rebind_outline(Path(args.receipt).resolve(), Path(args.outline).resolve())
            print("outline_bridge_review_status: rebound")
            return 0
        if args.command == "seal-review":
            seal_review(Path(args.receipt).resolve(), Path(args.outline).resolve())
            print("outline_bridge_review_status: sealed")
            return 0
        if args.command == "apply-beat-template":
            receipt_path = Path(args.receipt).resolve()
            template_path = Path(args.input).resolve()
            template_sha = sha256_file(template_path)
            merged = apply_beat_template(receipt_path, template_path)
            receipt_sha = sha256_file(receipt_path)
            for raw_path in args.refresh_sidecar:
                refresh_sidecar_receipt_sha(Path(raw_path).resolve(), receipt_sha)
            if args.consume:
                consume_sidecar(
                    template_path,
                    input_sha256=template_sha,
                    receipt_path=receipt_path,
                    receipt_sha256=receipt_sha,
                    operation="outline-bridge-beat-review.apply",
                    counts={
                        "bridges": len(merged.get("outline_bridge_flow_parity") or []),
                        "outside_bridges": int(
                            isinstance(merged.get("outside_bridge_plot_parity"), dict)
                        ),
                    },
                )
            print("outline_bridge_beat_review_template: applied")
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
                operation="outline-bridge-review.apply",
                counts={
                    "bridges": len(merged.get("outline_bridge_flow_parity") or []),
                    "outside_bridges": int(
                        isinstance(merged.get("outside_bridge_plot_parity"), dict)
                    ),
                },
            )
        print("outline_bridge_review_template: applied")
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print("outline_bridge_review_template: blocked")
        print(f"- {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
