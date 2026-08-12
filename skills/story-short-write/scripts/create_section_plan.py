#!/usr/bin/env python3
"""Serialize an approved outline scene-unit contract into a section plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one prewrite section plan.")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--output", required=True)
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
