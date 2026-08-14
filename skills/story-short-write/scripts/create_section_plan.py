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


def build_plan(
    payload: dict[str, Any],
    receipt_path: Path,
    section_id: str,
    mapping_path: Path | None,
    constraints: list[str],
) -> dict[str, Any]:
    section = next(
        item for item in payload.get("sections", [])
        if isinstance(item, dict) and str(item.get("section_id")) == section_id
    )
    scene_units = section.get("scene_units")
    if not isinstance(scene_units, list) or not scene_units:
        raise ValueError(f"第 {section_id} 节缺少 scene_units")
    scene_units = normalize_emotion_ids(scene_units, mapping_path)
    plan = {
        "section_id": section_id,
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
    return plan


def write_plan(output_path: Path, plan: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def validate_full_beat_coverage(payload: dict[str, Any], mapping: dict[str, Any]) -> None:
    scene_emotions: list[str] = []
    scene_plots: list[str] = []
    for section in payload.get("sections", []):
        if not isinstance(section, dict):
            continue
        for scene in section.get("scene_units", []):
            if not isinstance(scene, dict):
                continue
            scene_emotions.extend(str(value) for value in scene.get("emotion_beat_ids", []))
            scene_plots.extend(str(value) for value in scene.get("plot_beat_ids", []))
    expected_emotions = [
        str(item.get("target_beat_id"))
        for item in mapping.get("emotions", [])
        if isinstance(item, dict) and item.get("target_beat_id")
    ]
    expected_plots = [
        str(item.get("target_beat_id"))
        for item in mapping.get("plots", [])
        if isinstance(item, dict) and item.get("target_beat_id")
    ]
    errors: list[str] = []
    if len(scene_emotions) != len(set(scene_emotions)):
        errors.append("细纲场面存在重复 E 拍")
    if len(scene_plots) != len(set(scene_plots)):
        errors.append("细纲场面存在重复 P 拍")
    if scene_emotions != expected_emotions:
        missing = [value for value in expected_emotions if value not in scene_emotions]
        extra = [value for value in scene_emotions if value not in expected_emotions]
        errors.append(f"E 拍未与逐拍映射完整同序: missing={missing}, extra={extra}")
    if scene_plots != expected_plots:
        missing = [value for value in expected_plots if value not in scene_plots]
        extra = [value for value in scene_plots if value not in expected_plots]
        errors.append(f"P 拍未与逐拍映射完整同序: missing={missing}, extra={extra}")
    if errors:
        raise ValueError("；".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one prewrite section plan.")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--section", required=True, help="小节编号，或 all")
    parser.add_argument("--output", help="单节输出路径")
    parser.add_argument("--output-dir", help="--section all 时的输出目录")
    parser.add_argument("--beat-mapping", help="逐拍语义映射.json；scene_units 使用 TE-* 时必填")
    parser.add_argument("--constraints", help="可选 JSON 文件，顶层为字符串数组")
    args = parser.parse_args()
    receipt_path = Path(args.receipt).resolve()
    try:
        payload = load(receipt_path)
        if payload.get("gate_status") != "passed":
            raise ValueError("细纲表演验收回执未 passed")
        mapping_path = Path(args.beat_mapping).resolve() if args.beat_mapping else None
        constraints: list[str] = []
        if args.constraints:
            raw = json.loads(Path(args.constraints).resolve().read_text(encoding="utf-8"))
            if not isinstance(raw, list) or not all(isinstance(x, str) and x.strip() for x in raw):
                raise ValueError("constraints 必须是非空字符串数组")
            constraints = raw
        if str(args.section).lower() == "all":
            if not args.output_dir:
                raise ValueError("--section all 必须传 --output-dir")
            if mapping_path is None:
                raise ValueError("--section all 必须传 --beat-mapping 做全书 E/P 覆盖检查")
            validate_full_beat_coverage(payload, load(mapping_path))
            output_dir = Path(args.output_dir).resolve()
            section_ids = [
                str(item.get("section_id"))
                for item in payload.get("sections", [])
                if isinstance(item, dict) and item.get("section_id") is not None
            ]
            if not section_ids:
                raise ValueError("细纲表演验收回执没有小节")
            for section_id in section_ids:
                write_plan(
                    output_dir / f"第{section_id}节.json",
                    build_plan(payload, receipt_path, section_id, mapping_path, constraints),
                )
            print(f"section_plan: refreshed_all ({len(section_ids)})")
            print(f"output_dir: {output_dir}")
            return 0
        if not args.output:
            raise ValueError("单节模式必须传 --output")
        output_path = Path(args.output).resolve()
        write_plan(
            output_path,
            build_plan(payload, receipt_path, str(args.section), mapping_path, constraints),
        )
    except (OSError, ValueError, StopIteration, KeyError, json.JSONDecodeError) as exc:
        print("section_plan: blocked")
        print(f"- {exc}")
        return 2
    print("section_plan: created")
    print(f"output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
