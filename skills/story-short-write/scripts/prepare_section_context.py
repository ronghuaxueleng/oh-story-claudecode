#!/usr/bin/env python3
"""Assemble one section's deterministic writing context from approved assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTLINE_SECTION_RE = re.compile(r"(?m)^##\s+(\d+)\.")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 无效: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_section(items: list[Any], section_id: str, label: str) -> dict[str, Any]:
    for item in items:
        if isinstance(item, dict) and str(item.get("section_id")) == section_id:
            return item
    raise ValueError(f"{label}不存在第 {section_id} 节")


def extract_outline_section(text: str, section_id: str) -> str:
    matches = list(OUTLINE_SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1) != section_id:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[match.start():end].strip()
    raise ValueError(f"小节大纲不存在第 {section_id} 节")


def ordered_lookup(
    source_items: list[Any],
    id_field: str,
    required_ids: list[str],
    label: str,
) -> list[dict[str, Any]]:
    lookup = {
        str(item.get(id_field)): item
        for item in source_items
        if isinstance(item, dict) and item.get(id_field)
    }
    missing = [item_id for item_id in required_ids if item_id not in lookup]
    if missing:
        raise ValueError(f"{label}缺少: {missing}")
    return [lookup[item_id] for item_id in required_ids]


def build_context(state_path: Path, section_id: str) -> dict[str, Any]:
    state = load_json(state_path)
    section_state = get_section(state.get("sections", []), section_id, "逐节正文进度")
    if section_state.get("status") != "writing":
        raise ValueError(
            f"第 {section_id} 节必须先 start-section，实际状态为 {section_state.get('status')}"
        )

    paths = state.get("paths") or {}
    outline_path = Path(str(paths.get("outline") or "")).resolve()
    prose_path = Path(str(paths.get("prose_receipt") or "")).resolve()
    plan_path = Path(str(section_state.get("first_draft_plan_path") or "")).resolve()
    for label, path in (
        ("小节大纲", outline_path),
        ("文字合同", prose_path),
        ("当前节计划", plan_path),
    ):
        if not path.is_file():
            raise ValueError(f"{label}不存在: {path}")

    prose = load_json(prose_path)
    plan = load_json(plan_path)
    if str(plan.get("section_id")) != section_id:
        raise ValueError("当前节计划 section_id 与状态不一致")
    if sha256_file(plan_path) != section_state.get("first_draft_plan_sha256"):
        raise ValueError("当前节计划 SHA 与 start-section 绑定不一致")

    generation_plan = get_section(
        prose.get("section_generation_plans", []),
        section_id,
        "全文文字颗粒度契约写前落笔包",
    )
    required_sf_ids = [str(value) for value in section_state.get("required_sf_ids", [])]
    required_detail_ids = [
        str(value) for value in section_state.get("required_detail_card_ids", [])
    ]
    sf_assets = ordered_lookup(
        prose.get("source_subflow_reviews", []),
        "subflow_id",
        required_sf_ids,
        "文字合同 SF",
    )
    detail_assets = ordered_lookup(
        prose.get("source_detail_card_reviews", []),
        "card_id",
        required_detail_ids,
        "文字合同主体细节卡",
    )

    outline_text = outline_path.read_text(encoding="utf-8")
    project_dir = state_path.parent.parent
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "story-short-write/prepare_section_context.py",
        "deterministic_assembly_only": True,
        "semantic_judgment_generated_by_script": False,
        "section_id": section_id,
        "section_status": section_state.get("status"),
        "budget": {
            "min_chars": section_state.get("min_chars"),
            "max_chars": section_state.get("max_chars"),
            "target_chars": plan.get("target_chars"),
        },
        "required_ids": {
            "emotion_beat_ids": list(section_state.get("emotion_beat_ids", [])),
            "plot_beat_ids": list(section_state.get("plot_beat_ids", [])),
            "sf_ids": required_sf_ids,
            "detail_card_ids": required_detail_ids,
        },
        "paths": {
            "project_dir": str(project_dir),
            "outline": str(outline_path),
            "section_plan": str(plan_path),
            "prose_receipt": str(prose_path),
            "staged": str(project_dir / "写作资产" / "当前节暂存" / f"第{section_id}节.md"),
            "review": str(project_dir / "写作资产" / "逐节验收" / f"第{section_id}节.json"),
        },
        "bindings": {
            "state_sha256": sha256_file(state_path),
            "outline_sha256": sha256_file(outline_path),
            "section_plan_sha256": sha256_file(plan_path),
            "prose_receipt_sha256": sha256_file(prose_path),
        },
        "outline_section": extract_outline_section(outline_text, section_id),
        "section_plan": plan,
        "generation_plan": generation_plan,
        "emotion_beat_contracts": list(section_state.get("emotion_beat_contracts", [])),
        "plot_beat_contracts": list(section_state.get("plot_beat_contracts", [])),
        "source_subflow_assets": sf_assets,
        "source_detail_card_assets": detail_assets,
        "next_step": "当前模型读取完整写作包后，一次写完整暂存稿，再初始化逐节人工回执。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare one complete section writing context.")
    parser.add_argument("--state", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    state_path = Path(args.state).resolve()
    output_path = Path(args.output).resolve()
    try:
        context = build_context(state_path, str(args.section))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(context, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print("section_context: blocked")
        print(f"- {exc}")
        return 2
    print(f"section_context: prepared ({args.section})")
    print(f"output: {output_path}")
    print("semantic_status: deterministic_context_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
