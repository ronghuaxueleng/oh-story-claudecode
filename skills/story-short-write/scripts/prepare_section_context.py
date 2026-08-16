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
SOURCE_TEXT_KEYS = {"source_excerpt", "positive_source_excerpt", "source_quote"}


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


def materialize_section_plan(
    plan: dict[str, Any],
    outline_receipt: dict[str, Any],
    section_id: str,
) -> dict[str, Any]:
    """Expand a compact plan from the SHA-bound outline receipt for consumption."""
    if isinstance(plan.get("scene_units"), list):
        return plan
    refs = plan.get("scene_unit_refs")
    if not isinstance(refs, list):
        raise ValueError("当前节计划缺少 scene_unit_refs 或 scene_units")
    section = get_section(
        outline_receipt.get("sections", []),
        section_id,
        "细纲表演验收回执",
    )
    upstream = section.get("scene_units")
    if not isinstance(upstream, list) or not upstream:
        raise ValueError(f"细纲表演验收回执缺少第 {section_id} 节 scene_units")
    by_id = {
        str(item.get("scene_id") or ""): item
        for item in upstream
        if isinstance(item, dict) and str(item.get("scene_id") or "")
    }
    ref_ids = [
        str(item.get("scene_id") or "")
        for item in refs
        if isinstance(item, dict) and str(item.get("scene_id") or "")
    ]
    upstream_ids = [str(item.get("scene_id") or "") for item in upstream]
    if ref_ids != upstream_ids:
        raise ValueError("紧凑当前节计划的 scene_unit_refs 与细纲场面原序不一致")
    expanded = dict(plan)
    expanded["scene_units"] = [by_id[scene_id] for scene_id in ref_ids]
    return expanded


def section_beat_contracts(
    emotion_receipt: dict[str, Any],
    section_id: str,
    emotion_ids: list[str],
    plot_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve state-machine beat IDs from the canonical emotion contract."""
    section = get_section(
        emotion_receipt.get("section_contracts", []),
        section_id,
        "全文情绪颗粒度契约",
    )
    emotions = {
        str(item.get("beat_id") or ""): item
        for item in section.get("source_emotion_beats", [])
        if isinstance(item, dict)
    }
    plots = {
        str(item.get("beat_id") or ""): item
        for item in section.get("required_plot_beats", [])
        if isinstance(item, dict)
    }
    missing = [
        beat_id
        for beat_id in [*emotion_ids, *plot_ids]
        if beat_id not in emotions and beat_id not in plots
    ]
    if missing:
        raise ValueError(f"全文情绪颗粒度契约缺少当前节 E/P 拍: {missing}")
    return (
        [emotions[beat_id] for beat_id in emotion_ids],
        [plots[beat_id] for beat_id in plot_ids],
    )


def compact_subflow_asset(source: dict[str, Any]) -> dict[str, Any]:
    """Keep the complete source granularity, but drop empty target-side scaffolding."""
    result: dict[str, Any] = {
        "subflow_id": source.get("subflow_id"),
        "parent_bridge_id": source.get("parent_bridge_id"),
        "source_range": source.get("source_range"),
        "source_style_granularity": source.get("source_style_granularity", {}),
        "required_sequence": list(source.get("required_sequence") or []),
        "source_function": source.get("source_function"),
    }
    return result


def compact_detail_asset(source: dict[str, Any]) -> dict[str, Any]:
    """Keep the full card source and migration contract, not pending review fields."""
    fields = (
        "card_id",
        "category",
        "title",
        "source_file",
        "source_range",
        "source_quote",
        "source_function",
        "target_sections",
        "target_adaptation",
        "distinct_function_to_preserve",
        "overlap_binding_ids",
        "overlap_is_not_omission",
    )
    return {field: source.get(field) for field in fields if field in source}


def intern_source_texts(
    value: Any,
    registry: dict[str, str],
    ids_by_text: dict[str, str],
) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if key in SOURCE_TEXT_KEYS and isinstance(child, str) and child:
                source_id = ids_by_text.get(child)
                if source_id is None:
                    source_id = f"SRC-{len(ids_by_text) + 1:03d}"
                    ids_by_text[child] = source_id
                    registry[source_id] = child
                result[f"{key}_ref"] = source_id
            else:
                result[key] = intern_source_texts(child, registry, ids_by_text)
        return result
    if isinstance(value, list):
        return [intern_source_texts(item, registry, ids_by_text) for item in value]
    return value


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
    emotion_path = Path(str(paths.get("emotion_receipt") or "")).resolve()
    outline_receipt_path = outline_path.parent / "写作资产" / "细纲表演验收回执.json"
    plan_path = Path(str(section_state.get("first_draft_plan_path") or "")).resolve()
    for label, path in (
        ("小节大纲", outline_path),
        ("文字合同", prose_path),
        ("当前节计划", plan_path),
    ):
        if not path.is_file():
            raise ValueError(f"{label}不存在: {path}")
    compact_state = not (
        isinstance(section_state.get("emotion_beat_contracts"), list)
        and isinstance(section_state.get("plot_beat_contracts"), list)
    )
    if compact_state and not emotion_path.is_file():
        raise ValueError(f"情绪合同不存在: {emotion_path}")

    prose = load_json(prose_path)
    emotion = load_json(emotion_path) if emotion_path.is_file() else {}
    plan = load_json(plan_path)
    if str(plan.get("section_id")) != section_id:
        raise ValueError("当前节计划 section_id 与状态不一致")
    if sha256_file(plan_path) != section_state.get("first_draft_plan_sha256"):
        raise ValueError("当前节计划 SHA 与 start-section 绑定不一致")
    if not isinstance(plan.get("scene_units"), list):
        if not outline_receipt_path.is_file():
            raise ValueError(f"细纲表演验收回执不存在: {outline_receipt_path}")
        outline_receipt = load_json(outline_receipt_path)
        if plan.get("outline_performance_receipt_sha256") != sha256_file(outline_receipt_path):
            raise ValueError("当前节计划未绑定最新细纲表演验收回执 SHA")
        plan = materialize_section_plan(plan, outline_receipt, section_id)

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
    if compact_state:
        emotion_contracts, plot_contracts = section_beat_contracts(
            emotion,
            section_id,
            [str(value) for value in section_state.get("emotion_beat_ids", [])],
            [str(value) for value in section_state.get("plot_beat_ids", [])],
        )
    else:
        emotion_contracts = list(section_state.get("emotion_beat_contracts", []))
        plot_contracts = list(section_state.get("plot_beat_contracts", []))

    outline_text = outline_path.read_text(encoding="utf-8")
    project_dir = state_path.parent.parent
    source_text_registry: dict[str, str] = {}
    ids_by_text: dict[str, str] = {}
    compact_generation_plan = intern_source_texts(
        generation_plan,
        source_text_registry,
        ids_by_text,
    )
    compact_detail_assets = intern_source_texts(
        [compact_detail_asset(item) for item in detail_assets],
        source_text_registry,
        ids_by_text,
    )
    return {
        "version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "story-short-write/prepare_section_context.py",
        "context_view": "compact_source_complete",
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
        "generation_plan": compact_generation_plan,
        "emotion_beat_contracts": emotion_contracts,
        "plot_beat_contracts": plot_contracts,
        "source_subflow_assets": [compact_subflow_asset(item) for item in sf_assets],
        "source_detail_card_assets": compact_detail_assets,
        "source_text_registry": source_text_registry,
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
