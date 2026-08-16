#!/usr/bin/env python3
"""Export/apply subflow-level manual review sidecars for outline performance receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_lifecycle import consume_sidecar


TEMPLATE_SCHEMA = "story-short-write.outline-subflow-review-template.v1"
STYLE_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)


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


def parse_outline_sections(outline_path: Path) -> dict[str, list[str]]:
    if not outline_path.is_file():
        raise FileNotFoundError(f"小节大纲不存在: {outline_path}")
    sections: dict[str, list[str]] = {}
    current_id: str | None = None
    pattern = re.compile(r"^##\s+(\d+)\.\s*(.*?)\s*$")
    for raw_line in outline_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        match = pattern.match(line)
        if match:
            current_id = match.group(1)
            sections[current_id] = []
            continue
        if current_id and line.startswith("- "):
            sections[current_id].append(line[2:].strip())
    return sections


def _bridge_section_index(receipt: dict[str, Any]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for item in receipt.get("outline_bridge_flow_parity") or []:
        if not isinstance(item, dict):
            continue
        bridge_id = str(item.get("source_bridge_id") or "").strip()
        if not bridge_id:
            continue
        index[bridge_id] = [
            str(section_id).strip()
            for section_id in item.get("target_outline_sections") or []
            if str(section_id).strip()
        ]
    return index


def _prefill_transfer(
    transfer: dict[str, Any],
    source_style: dict[str, Any],
    target_evidence: list[str],
) -> dict[str, Any]:
    result = deepcopy(transfer)
    source_evidence = [
        str(item).strip()
        for item in source_style.get("source_evidence") or []
        if str(item).strip()
    ]
    if not result.get("target_outline_evidence"):
        result["target_outline_evidence"] = deepcopy(target_evidence)
    mappings = result.get("source_evidence_mappings")
    if not isinstance(mappings, list) or not mappings:
        result["source_evidence_mappings"] = [
            {
                "source_evidence": quote,
                "target_outline_evidence": deepcopy(target_evidence),
                "mechanism_transfer_judgment": "",
                "independently_realized": True,
            }
            for quote in source_evidence
        ]
    if result.get("surface_copy_rejected") is None:
        result["surface_copy_rejected"] = True
    return result


def export_template(receipt_path: Path, output_path: Path, outline_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    coverages = receipt.get("source_subflow_granularity_coverage")
    if not isinstance(coverages, list):
        raise ValueError("回执缺少 source_subflow_granularity_coverage 列表")
    outline_sections = parse_outline_sections(outline_path)
    bridge_sections = _bridge_section_index(receipt)
    payload = {
        "schema_version": TEMPLATE_SCHEMA,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "outline_path": str(outline_path),
        "subflow_reviews": [],
    }
    for entry in coverages:
        if not isinstance(entry, dict):
            continue
        bridge_id = str(entry.get("parent_bridge_id") or "").strip()
        target_sections = [
            str(item).strip()
            for item in entry.get("target_outline_sections") or []
            if str(item).strip()
        ]
        if not target_sections:
            target_sections = deepcopy(bridge_sections.get(bridge_id, []))
        target_evidence: list[str] = []
        for section_id in target_sections:
            for line in outline_sections.get(section_id, []):
                if line not in target_evidence:
                    target_evidence.append(line)
        transferred = entry.get("transferred_style_fields")
        if not isinstance(transferred, dict):
            transferred = {}
        source_style = entry.get("source_style_granularity")
        if not isinstance(source_style, dict):
            source_style = {}
        payload["subflow_reviews"].append(
            {
                "subflow_id": entry.get("subflow_id", ""),
                "parent_bridge_id": bridge_id,
                "source_range": entry.get("source_range", ""),
                "target_outline_sections": target_sections,
                "outline_section_context": [
                    {
                        "section_id": section_id,
                        "outline_evidence": deepcopy(outline_sections.get(section_id, [])),
                    }
                    for section_id in target_sections
                ],
                "source_style_granularity": deepcopy(source_style),
                "transferred_style_fields": {
                    field: _prefill_transfer(
                        deepcopy(transferred.get(field, {})),
                        source_style.get(field, {}) if isinstance(source_style.get(field), dict) else {},
                        target_evidence,
                    )
                    for field in STYLE_FIELDS
                },
                "coverage_status": entry.get("coverage_status", "pending"),
                "adaptation_boundary": entry.get("adaptation_boundary", ""),
                "manual_judgment": entry.get("manual_judgment", ""),
            }
        )
    write_json(output_path, payload)
    return payload


def apply_template(receipt_path: Path, template_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    template = read_json(template_path, "SF 颗粒度回填侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError("SF 颗粒度回填侧车 schema_version 不正确")
    expected_sha = str(template.get("receipt_sha256") or "").strip()
    actual_sha = sha256_file(receipt_path)
    if expected_sha and expected_sha != actual_sha:
        raise ValueError("SF 颗粒度回填侧车绑定的 receipt_sha256 已失效，请重新 export")
    reviews = template.get("subflow_reviews")
    if not isinstance(reviews, list):
        raise ValueError("SF 颗粒度回填侧车缺少 subflow_reviews 列表")
    coverages = receipt.get("source_subflow_granularity_coverage")
    if not isinstance(coverages, list):
        raise ValueError("回执缺少 source_subflow_granularity_coverage 列表")
    merged = deepcopy(receipt)
    index = {
        str(item.get("subflow_id") or "").strip(): item
        for item in merged["source_subflow_granularity_coverage"]
        if isinstance(item, dict) and str(item.get("subflow_id") or "").strip()
    }
    seen: set[str] = set()
    for i, raw in enumerate(reviews):
        if not isinstance(raw, dict):
            raise ValueError(f"subflow_reviews[{i}] 必须是对象")
        subflow_id = str(raw.get("subflow_id") or "").strip()
        if not subflow_id:
            raise ValueError(f"subflow_reviews[{i}].subflow_id 不能为空")
        if subflow_id in seen:
            raise ValueError(f"SF 颗粒度回填侧车存在重复 subflow_id: {subflow_id}")
        seen.add(subflow_id)
        if subflow_id not in index:
            raise ValueError(f"回执不存在 subflow_id={subflow_id} 的 SF")
        target = index[subflow_id]
        for field in (
            "target_outline_sections",
            "transferred_style_fields",
            "coverage_status",
            "adaptation_boundary",
            "manual_judgment",
        ):
            if field in raw:
                target[field] = deepcopy(raw[field])
    write_json(receipt_path, merged)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export/apply subflow-level manual review sidecars for outline performance receipts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export-template")
    export.add_argument("--receipt", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--outline", required=True)

    apply_cmd = sub.add_parser("apply-template")
    apply_cmd.add_argument("--receipt", required=True)
    apply_cmd.add_argument("--input", required=True)
    apply_cmd.add_argument("--consume", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "export-template":
            payload = export_template(
                Path(args.receipt).resolve(),
                Path(args.output).resolve(),
                Path(args.outline).resolve(),
            )
            print(f"outline_subflow_review_template: exported ({len(payload['subflow_reviews'])} subflows)")
            return 0
        receipt_path = Path(args.receipt).resolve()
        template_path = Path(args.input).resolve()
        template_sha = sha256_file(template_path)
        merged = apply_template(receipt_path, template_path)
        print(
            "outline_subflow_review_template: applied "
            f"({len(merged.get('source_subflow_granularity_coverage', []))} subflows)"
        )
        if args.consume:
            consume_sidecar(
                template_path,
                {
                    "schema_version": TEMPLATE_SCHEMA + ".consumed",
                    "receipt_path": str(receipt_path),
                    "receipt_sha256": sha256_file(receipt_path),
                    "operation": "apply-template",
                    "input_sha256": template_sha,
                    "subflow_count": len(merged.get("source_subflow_granularity_coverage", [])),
                },
            )
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
