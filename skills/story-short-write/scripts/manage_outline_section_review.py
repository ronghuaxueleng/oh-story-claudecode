#!/usr/bin/env python3
"""Export/apply section-level manual review sidecars for outline performance receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


TEMPLATE_SCHEMA = "story-short-write.outline-section-review-template.v1"


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


def export_template(receipt_path: Path, output_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    sections = receipt.get("sections")
    if not isinstance(sections, list):
        raise ValueError("回执缺少 sections 列表")
    payload = {
        "schema_version": TEMPLATE_SCHEMA,
        "receipt_path": str(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "sections": [
            deepcopy(section)
            for section in sections
            if isinstance(section, dict) and str(section.get("section_id") or "").strip()
        ],
    }
    write_json(output_path, payload)
    return payload


def _normalize_section(section: dict[str, Any], label: str) -> dict[str, Any]:
    section_id = str(section.get("section_id") or "").strip()
    if not section_id:
        raise ValueError(f"{label}.section_id 不能为空")
    normalized = deepcopy(section)
    normalized["section_id"] = section_id
    return normalized


def apply_template(receipt_path: Path, template_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲表演验收回执")
    template = read_json(template_path, "节级回填侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError("节级回填侧车 schema_version 不正确")
    expected_sha = str(template.get("receipt_sha256") or "").strip()
    actual_sha = sha256_file(receipt_path)
    if expected_sha and expected_sha != actual_sha:
        raise ValueError("节级回填侧车绑定的 receipt_sha256 已失效，请重新 export")

    receipt_sections = receipt.get("sections")
    template_sections = template.get("sections")
    if not isinstance(receipt_sections, list):
        raise ValueError("回执缺少 sections 列表")
    if not isinstance(template_sections, list):
        raise ValueError("节级回填侧车缺少 sections 列表")

    receipt_index = {
        str(item.get("section_id") or ""): item
        for item in receipt_sections
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    }
    merged = deepcopy(receipt)
    merged_sections = merged["sections"]
    merged_index = {
        str(item.get("section_id") or ""): item
        for item in merged_sections
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    }

    seen_ids: set[str] = set()
    for index, raw in enumerate(template_sections):
        if not isinstance(raw, dict):
            raise ValueError(f"sections[{index}] 必须是对象")
        section = _normalize_section(raw, f"sections[{index}]")
        section_id = section["section_id"]
        if section_id in seen_ids:
            raise ValueError(f"节级回填侧车存在重复 section_id: {section_id}")
        seen_ids.add(section_id)
        if section_id not in receipt_index:
            raise ValueError(f"回执不存在 section_id={section_id} 的小节")
        target = merged_index[section_id]
        target.clear()
        target.update(section)

    write_json(receipt_path, merged)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export/apply section-level manual review sidecars for outline performance receipts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export-template")
    export.add_argument("--receipt", required=True)
    export.add_argument("--output", required=True)

    apply_cmd = sub.add_parser("apply-template")
    apply_cmd.add_argument("--receipt", required=True)
    apply_cmd.add_argument("--input", required=True)

    args = parser.parse_args()
    try:
        if args.command == "export-template":
            payload = export_template(Path(args.receipt).resolve(), Path(args.output).resolve())
            print(f"outline_section_review_template: exported ({len(payload['sections'])} sections)")
            return 0
        apply_template(Path(args.receipt).resolve(), Path(args.input).resolve())
        print("outline_section_review_template: applied")
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print("outline_section_review_template: blocked")
        print(f"- {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
