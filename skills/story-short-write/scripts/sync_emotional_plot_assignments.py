#!/usr/bin/env python3
"""Sync manually assigned scene P beats into the emotional prewrite contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "story-short-write.emotional-plot-assignment-review.v1"


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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def section_plot_ids(outline_receipt: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for section in outline_receipt.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "")
        ids: list[str] = []
        for scene in section.get("scene_units", []):
            if isinstance(scene, dict):
                ids.extend(str(value) for value in scene.get("plot_beat_ids", []))
        result[section_id] = ids
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--outline-contract", required=True)
    parser.add_argument("--beat-mapping", required=True)
    parser.add_argument("--review", required=True)
    args = parser.parse_args()

    contract_path = Path(args.contract).resolve()
    outline_path = Path(args.outline_contract).resolve()
    mapping_path = Path(args.beat_mapping).resolve()
    review_path = Path(args.review).resolve()
    contract = read_json(contract_path, "全文情绪颗粒度契约回执")
    outline = read_json(outline_path, "细纲表演验收回执")
    mapping = read_json(mapping_path, "逐拍语义映射")
    review = read_json(review_path, "情绪 P 拍同步人工计划")

    errors: list[str] = []
    if review.get("schema_version") != SCHEMA:
        errors.append(f"schema_version 必须为 {SCHEMA}")
    bindings = (
        ("contract_sha256", contract_path),
        ("outline_contract_sha256", outline_path),
        ("beat_mapping_sha256", mapping_path),
    )
    for field, path in bindings:
        if review.get(field) != sha256_file(path):
            errors.append(f"{field} 与当前文件不一致")
    if review.get("reviewed_by_current_model") is not True:
        errors.append("reviewed_by_current_model 必须为 true")
    if review.get("semantic_fields_generated_by_script") is not False:
        errors.append("semantic_fields_generated_by_script 必须为 false")

    expected_by_section = section_plot_ids(outline)
    contract_sections = [
        item
        for item in contract.get("section_contracts", [])
        if isinstance(item, dict)
    ]
    review_sections = [
        item for item in review.get("sections", []) if isinstance(item, dict)
    ]
    expected_section_ids = [str(item.get("section_id")) for item in contract_sections]
    review_section_ids = [str(item.get("section_id")) for item in review_sections]
    if review_section_ids != expected_section_ids:
        errors.append("review.sections 必须与情绪合同数字节全集同序一致")

    plot_by_id = {
        str(item.get("target_beat_id")): item
        for item in mapping.get("plots", [])
        if isinstance(item, dict) and item.get("target_beat_id")
    }
    review_by_section = {
        str(item.get("section_id")): item for item in review_sections
    }
    for section_id in expected_section_ids:
        item = review_by_section.get(section_id, {})
        ids = [str(value) for value in item.get("plot_beat_ids", [])]
        if ids != expected_by_section.get(section_id, []):
            errors.append(f"第 {section_id} 节 plot_beat_ids 与 scene_units 不一致")
        if any(beat_id not in plot_by_id for beat_id in ids):
            errors.append(f"第 {section_id} 节包含逐拍映射中不存在的 P 拍")
        if len(str(item.get("plot_beat_completion_review") or "").strip()) < 20:
            errors.append(f"第 {section_id} 节 plot_beat_completion_review 过短")

    if errors:
        print("emotional_plot_assignments: blocked")
        for error in errors:
            print(f"- {error}")
        return 1

    for section in contract_sections:
        section_id = str(section.get("section_id"))
        review_item = review_by_section[section_id]
        section["required_plot_beats"] = [
            {
                "beat_id": beat_id,
                "action": str(plot_by_id[beat_id].get("action") or ""),
                "outline_evidence": str(plot_by_id[beat_id].get("evidence") or ""),
            }
            for beat_id in review_item["plot_beat_ids"]
        ]
        section["plot_beat_completion_review"] = review_item[
            "plot_beat_completion_review"
        ]
    write_json(contract_path, contract)
    print(f"emotional_plot_assignments: synced ({len(contract_sections)} sections)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
