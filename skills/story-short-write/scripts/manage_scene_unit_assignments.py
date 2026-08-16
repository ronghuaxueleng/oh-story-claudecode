#!/usr/bin/env python3
"""Apply current-model scene-unit assignments without copying the full section sidecar."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "story-short-write.scene-unit-assignments.v1"
REQUIRED_SCENE_FIELDS = (
    "scene_id",
    "plot_beat_ids",
    "emotion_beat_ids",
    "allocated_chars",
    "full_scene_required",
    "summary_only",
    "entry_pressure",
    "turning_action",
    "visible_consequence",
    "aftershock",
    "reader_emotion_path",
    "interaction_chain",
    "outline_evidence",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_scene(scene: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(scene, dict):
        return [f"{label}必须是对象"]
    for field in REQUIRED_SCENE_FIELDS:
        if field not in scene:
            errors.append(f"{label}.{field} 缺失")
    if not nonempty_text(scene.get("scene_id")):
        errors.append(f"{label}.scene_id 不能为空")
    for field in ("plot_beat_ids", "emotion_beat_ids", "interaction_chain", "outline_evidence"):
        if not isinstance(scene.get(field), list):
            errors.append(f"{label}.{field} 必须是数组")
    if not isinstance(scene.get("allocated_chars"), int) or scene.get("allocated_chars", 0) < 240:
        errors.append(f"{label}.allocated_chars 必须至少 240")
    if scene.get("full_scene_required") is not True or scene.get("summary_only") is not False:
        errors.append(f"{label} 必须声明 full_scene_required=true / summary_only=false")
    for field in (
        "entry_pressure",
        "turning_action",
        "visible_consequence",
        "aftershock",
        "reader_emotion_path",
    ):
        if not nonempty_text(scene.get(field)):
            errors.append(f"{label}.{field} 不能为空")
    if not isinstance(scene.get("interaction_chain"), list) or len(scene["interaction_chain"]) < 3:
        errors.append(f"{label}.interaction_chain 必须至少 3 步")
    if not isinstance(scene.get("outline_evidence"), list) or len(scene["outline_evidence"]) < 2:
        errors.append(f"{label}.outline_evidence 必须至少 2 条")
    return errors


def expected_ids(mapping: dict[str, Any], key: str) -> list[str]:
    values: list[str] = []
    for item in mapping.get(key, []):
        if not isinstance(item, dict):
            continue
        beat_id = str(item.get("target_beat_id") or "").strip()
        if beat_id:
            values.append(beat_id)
    return values


def validate_payload(
    receipt_path: Path,
    receipt: dict[str, Any],
    mapping: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA:
        errors.append(f"schema_version 必须为 {SCHEMA}")
    if payload.get("receipt_sha256") != sha256_file(receipt_path):
        errors.append("窄侧车 receipt_sha256 与当前正式回执不一致")
    if payload.get("reviewed_by_current_model") is not True:
        errors.append("reviewed_by_current_model 必须为 true")
    if payload.get("semantic_fields_generated_by_script") is not False:
        errors.append("semantic_fields_generated_by_script 必须为 false")
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return errors + ["sections 必须是数组"]

    receipt_ids = [
        str(item.get("section_id"))
        for item in receipt.get("sections", [])
        if isinstance(item, dict)
    ]
    payload_ids = [
        str(item.get("section_id"))
        for item in sections
        if isinstance(item, dict)
    ]
    if payload_ids != receipt_ids:
        errors.append("窄侧车 sections 必须与正式回执数字节全集同序一致")

    all_e: list[str] = []
    all_p: list[str] = []
    scene_ids: list[str] = []
    for section_index, section in enumerate(sections):
        label = f"sections[{section_index}]"
        if not isinstance(section, dict):
            errors.append(f"{label}必须是对象")
            continue
        scenes = section.get("scene_units")
        if not isinstance(scenes, list) or not 1 <= len(scenes) <= 3:
            errors.append(f"{label}.scene_units 必须包含 1-3 个场面")
            continue
        for scene_index, scene in enumerate(scenes):
            scene_label = f"{label}.scene_units[{scene_index}]"
            errors.extend(validate_scene(scene, scene_label))
            if not isinstance(scene, dict):
                continue
            scene_ids.append(str(scene.get("scene_id") or ""))
            all_e.extend(str(value) for value in scene.get("emotion_beat_ids", []))
            all_p.extend(str(value) for value in scene.get("plot_beat_ids", []))

    if len(scene_ids) != len(set(scene_ids)):
        errors.append("scene_id 必须在全书范围唯一")
    if len(all_e) != len(set(all_e)):
        errors.append("scene_units 存在重复 E 拍")
    if len(all_p) != len(set(all_p)):
        errors.append("scene_units 存在重复 P 拍")
    expected_e = expected_ids(mapping, "emotions")
    expected_p = expected_ids(mapping, "plots")
    if all_e != expected_e:
        errors.append(
            f"E 拍必须与逐拍映射全集同序一致: "
            f"missing={[value for value in expected_e if value not in all_e]}, "
            f"extra={[value for value in all_e if value not in expected_e]}"
        )
    if all_p != expected_p:
        errors.append(
            f"P 拍必须与逐拍映射全集同序一致: "
            f"missing={[value for value in expected_p if value not in all_p]}, "
            f"extra={[value for value in all_p if value not in expected_p]}"
        )
    return errors


def apply_assignments(
    receipt_path: Path,
    mapping_path: Path,
    input_path: Path,
) -> int:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    mapping = read_json(mapping_path, "逐拍语义映射")
    payload = read_json(input_path, "scene_units 窄侧车")
    errors = validate_payload(receipt_path, receipt, mapping, payload)
    if errors:
        print("scene_unit_assignments: blocked")
        for error in errors:
            print(f"- {error}")
        return 1

    sections_by_id = {
        str(item.get("section_id")): item
        for item in receipt.get("sections", [])
        if isinstance(item, dict)
    }
    for item in payload["sections"]:
        section_id = str(item["section_id"])
        sections_by_id[section_id]["scene_units"] = item["scene_units"]
    receipt["reviewed_by_current_model"] = False
    receipt["gate_status"] = "pending"
    receipt["blocking_failures"] = []
    write_json(receipt_path, receipt)
    print(f"scene_unit_assignments: applied ({len(payload['sections'])} sections)")
    return 0


def export_assignments(receipt_path: Path, output_path: Path) -> int:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    sections: list[dict[str, Any]] = []
    for item in receipt.get("sections", []):
        if not isinstance(item, dict):
            continue
        sections.append(
            {
                "section_id": str(item.get("section_id") or ""),
                "scene_units": copy.deepcopy(item.get("scene_units") or []),
            }
        )
    payload = {
        "schema_version": SCHEMA,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "reviewed_by_current_model": False,
        "semantic_fields_generated_by_script": False,
        "sections": sections,
        "manual_judgment": "",
    }
    write_json(output_path, payload)
    print(f"scene_unit_assignments: exported ({len(sections)} sections)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--receipt", required=True)
    export_parser.add_argument("--output", required=True)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--receipt", required=True)
    apply_parser.add_argument("--beat-mapping", required=True)
    apply_parser.add_argument("--input", required=True)
    args = parser.parse_args()
    if args.command == "export":
        return export_assignments(
            Path(args.receipt).resolve(),
            Path(args.output).resolve(),
        )
    if args.command == "apply":
        return apply_assignments(
            Path(args.receipt).resolve(),
            Path(args.beat_mapping).resolve(),
            Path(args.input).resolve(),
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
