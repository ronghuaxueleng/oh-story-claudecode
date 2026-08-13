#!/usr/bin/env python3
"""Serialize an approved outline scene-unit contract into a section plan."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def normalize_emotion_ids(scene_units: list[dict[str, Any]], mapping_path: Path | None) -> list[dict[str, Any]]:
    target_ids = [
        str(beat_id)
        for scene in scene_units
        for beat_id in scene.get("emotion_beat_ids", [])
    ]
    if not any(beat_id.startswith("TE-") for beat_id in target_ids):
        return copy.deepcopy(scene_units)
    if mapping_path is None:
        raise ValueError("scene_units 使用目标情绪拍 ID，必须传 --beat-mapping 显式映射回主体 E 拍")
    mapping = load(mapping_path)
    if mapping.get("status") != "approved":
        raise ValueError("逐拍语义映射未 approved")
    target_to_source: dict[str, str] = {}
    for item in mapping.get("emotions", []):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_beat_id") or "")
        target_id = str(item.get("target_beat_id") or "")
        if not source_id or not target_id:
            continue
        if target_id in target_to_source and target_to_source[target_id] != source_id:
            raise ValueError(f"目标情绪拍存在重复映射: {target_id}")
        target_to_source[target_id] = source_id
    missing = [beat_id for beat_id in target_ids if beat_id not in target_to_source]
    if missing:
        raise ValueError(f"逐拍语义映射缺少目标情绪拍: {missing}")
    normalized = copy.deepcopy(scene_units)
    for scene in normalized:
        scene["target_emotion_beat_ids"] = list(scene.get("emotion_beat_ids", []))
        scene["emotion_beat_ids"] = [
            target_to_source[str(beat_id)] for beat_id in scene.get("emotion_beat_ids", [])
        ]
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one prewrite section plan.")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--beat-mapping", help="逐拍语义映射.json；scene_units 使用 TE-* 时必填")
    parser.add_argument("--constraints", help="可选 JSON 文件，顶层为字符串数组")
    args = parser.parse_args()
    receipt_path = Path(args.receipt).resolve()
    output_path = Path(args.output).resolve()
    try:
        payload = load(receipt_path)
        if payload.get("gate_status") != "passed":
            raise ValueError("细纲表演验收回执未 passed")
        section = next(
            item for item in payload.get("sections", [])
            if isinstance(item, dict) and str(item.get("section_id")) == str(args.section)
        )
        scene_units = section.get("scene_units")
        if not isinstance(scene_units, list) or not scene_units:
            raise ValueError("当前节缺少 scene_units")
        mapping_path = Path(args.beat_mapping).resolve() if args.beat_mapping else None
        scene_units = normalize_emotion_ids(scene_units, mapping_path)
        constraints: list[str] = []
        if args.constraints:
            raw = json.loads(Path(args.constraints).resolve().read_text(encoding="utf-8"))
            if not isinstance(raw, list) or not all(isinstance(x, str) and x.strip() for x in raw):
                raise ValueError("constraints 必须是非空字符串数组")
            constraints = raw
        plan = {
            "section_id": str(args.section),
            "mode": "single_pass_scene_realization",
            "target_chars": sum(int(item["allocated_chars"]) for item in scene_units),
            "outline_performance_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            "append_or_expand_after_target_write_forbidden": True,
            "scene_units": scene_units,
        }
        if mapping_path:
            plan["beat_mapping_sha256"] = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
        if constraints:
            plan["positive_generation_constraints"] = constraints
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, StopIteration, KeyError, json.JSONDecodeError) as exc:
        print("section_plan: blocked")
        print(f"- {exc}")
        return 2
    print("section_plan: created")
    print(f"output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
