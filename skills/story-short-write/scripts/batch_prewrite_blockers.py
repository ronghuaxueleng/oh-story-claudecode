#!/usr/bin/env python3
"""Aggregate outline/prewrite blocker output into a deduplicated work order."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any
import re


ROOT = Path(__file__).resolve().parent


def _load_module(filename: str, alias: str):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTLINE = _load_module(
    "validate_outline_performance_contract.py",
    "story_short_write_outline_performance_blockers",
)
DRAFT_PREWRITE = _load_module(
    "batch_draft_prewrite.py",
    "story_short_write_batch_draft_prewrite_blockers",
)
WRITE_RELEASE = _load_module(
    "validate_write_release_gate.py",
    "story_short_write_write_release_blockers",
)


CATEGORY_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "source_ledgers",
        "源账本",
        "先修源账本或来源边界，否则后续合同都在吃假阻断。",
        "全文情绪颗粒总账|全文情节微拍总账|bid_ids 真实边界|无法读取全文情绪颗粒总账|无法读取全文情节微拍总账",
    ),
    (
        "bridge_parity",
        "桥级对齐",
        "先补桥级 P/E 拍映射与读者体感同级判断，再看节级字段。",
        "桥外情节微拍对齐|原文桥段对齐\\[",
    ),
    (
        "subflow_granularity",
        "SF 颗粒",
        "把主体 SF 六类局部颗粒逐条落到真实细纲证据，不能只保留桥段摘要。",
        "主体 SF 颗粒度覆盖\\[",
    ),
    (
        "section_performance",
        "节级场面",
        "每节补齐场面承重、关系伤害、冲突载体、情绪同级与 scene_units。",
        "^第 \\d+ 节",
    ),
    (
        "detail_cards",
        "细节卡计划",
        "主体细节卡先绑定真实小节、重叠关系和保留功能，再进入正文前合同。",
        "^主体细节卡 ",
    ),
    (
        "prose_contract",
        "文字合同",
        "先补声线基线、52 项、活性层、人物颗粒和写前包，不要提前写正文。",
        "文字颗粒度维度|52 项|超细|source_baseline|连续样本|成文活性|人物性格颗粒|prewrite_status 必须为 passed|细纲 绑定",
    ),
    (
        "emotional_contract",
        "情绪合同",
        "逐节绑定全文情绪总账，确保数字小节覆盖、顺序一致、人工复核完成。",
        "逐节情绪合同|情绪颗粒度合同必须由当前模型逐节人工复核|仿写情绪烈度低于原文|目标烈度低于原文|source_emotion_parity",
    ),
    (
        "write_release",
        "最终放行",
        "只有上游门禁都 passed 之后，才处理最终写作放行闸。",
        "正文写作放行闸|write_release|release",
    ),
)

FOCUS_RULES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "bridge_emotion_boundary",
        "桥级情绪边界",
        "先核对全文情绪总账 bid_ids、桥外拍归属和来源资产口径冲突，再修桥级或节级字段。",
        ("source_ledgers",),
    ),
    (
        "bridge_mapping_missing",
        "桥级逐拍映射",
        "先补桥级 target_plot_beats / plot_beat_mapping / source_emotion_sequence / target_emotion_sequence，再看节级承载。",
        ("bridge_parity",),
    ),
    (
        "section_scene_units_missing",
        "节级场面承载",
        "桥级边界和逐拍稳定后，再补各节 scene_units、逐节场面验收和节级空 scaffold。",
        ("section_performance",),
    ),
)


def _contains(message: str, pattern_blob: str) -> bool:
    return re.search(pattern_blob, message) is not None


def is_bridge_emotion_boundary(message: str) -> bool:
    return bool(
        re.search(
            r"bid_ids 真实边界|桥外导语|桥外.*塞入|无法读取全文情绪颗粒总账|全文情绪颗粒总账|桥段施工卡.*总账|总账.*桥段施工卡",
            message,
        )
    )


def is_bridge_mapping_missing(message: str) -> bool:
    return bool(
        re.search(
            r"原文桥段对齐\[\d+\].*(目标情节拍|plot_beat_mapping|原文情绪流程|目标情绪流程|原文与目标情节拍数|原文情节拍必须按原顺序|目标情绪拍必须沿用原文 beat_id)",
            message,
        )
    )


def is_section_scene_units_missing(message: str) -> bool:
    return bool(re.search(r"^第 \d+ 节 scene_units 必须包含 1-3 个完整场面$", message))


def classify_error(stage: str, message: str) -> str:
    if stage == "write_release":
        return "write_release"
    for category, _label, _action, pattern_blob in CATEGORY_RULES:
        if _contains(message, pattern_blob):
            return category
    return "misc"


def category_label(category: str) -> str:
    for key, label, _action, _pattern in CATEGORY_RULES:
        if key == category:
            return label
    if category == "misc":
        return "其他阻断"
    raise KeyError(category)


def category_action(category: str) -> str:
    for key, _label, action, _pattern in CATEGORY_RULES:
        if key == category:
            return action
    if category == "misc":
        return "回到对应回执逐条人工处理，避免把杂项阻断继续扩散。"
    raise KeyError(category)


def category_order(category: str) -> int:
    ordered = [item[0] for item in CATEGORY_RULES] + ["misc"]
    return ordered.index(category)


def focus_order(focus_category: str) -> int:
    ordered = [item[0] for item in FOCUS_RULES]
    return ordered.index(focus_category)


def aggregate_focus_work_order(work_order: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in work_order:
        messages = [str(message) for message in item["messages"]]
        focus_category = None
        if any(is_bridge_emotion_boundary(message) for message in messages):
            focus_category = "bridge_emotion_boundary"
        elif any(is_bridge_mapping_missing(message) for message in messages):
            focus_category = "bridge_mapping_missing"
        elif any(is_section_scene_units_missing(message) for message in messages):
            focus_category = "section_scene_units_missing"
        if focus_category is None:
            continue
        if focus_category not in grouped:
            label, next_action = "", ""
            for key, focus_label, action, _source_categories in FOCUS_RULES:
                if key == focus_category:
                    label = focus_label
                    next_action = action
                    break
            grouped[focus_category] = {
                "category": focus_category,
                "label": label,
                "next_action": next_action,
                "source_categories": [],
                "stages": [],
                "messages": [],
            }
        bucket = grouped[focus_category]
        if item["label"] not in bucket["source_categories"]:
            bucket["source_categories"].append(item["label"])
        for stage in item["stages"]:
            if stage not in bucket["stages"]:
                bucket["stages"].append(stage)
        for message in messages:
            if focus_category == "bridge_emotion_boundary" and not is_bridge_emotion_boundary(message):
                continue
            if focus_category == "bridge_mapping_missing" and not is_bridge_mapping_missing(message):
                continue
            if focus_category == "section_scene_units_missing" and not is_section_scene_units_missing(message):
                continue
            if message not in bucket["messages"]:
                bucket["messages"].append(message)
    return sorted(grouped.values(), key=lambda item: focus_order(item["category"]))


def normalize_message(message: str) -> str:
    return " ".join(str(message).split())


def aggregate_errors(stage_errors: list[tuple[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for stage, raw_message in stage_errors:
        message = normalize_message(raw_message)
        category = classify_error(stage, message)
        dedupe_key = (category, message)
        if dedupe_key in seen:
            if stage not in grouped[category]["stages"]:
                grouped[category]["stages"].append(stage)
            continue
        seen.add(dedupe_key)
        bucket = grouped.setdefault(
            category,
            {
                "category": category,
                "label": category_label(category),
                "next_action": category_action(category),
                "stages": [],
                "messages": [],
            },
        )
        if stage not in bucket["stages"]:
            bucket["stages"].append(stage)
        bucket["messages"].append(message)
    return sorted(grouped.values(), key=lambda item: category_order(item["category"]))


def scan_blockers(
    *,
    outline_contract: Path,
    outline: Path,
    prose_receipt: Path,
    emotional_receipt: Path,
    source_original: Path,
    source_emotion_ledger: Path,
    writing_receipt: Path | None = None,
    source_receipt: Path | None = None,
    ledger: Path | None = None,
    sequence_receipt: Path | None = None,
    opening_contract: Path | None = None,
    profile: Path | None = None,
) -> dict[str, Any]:
    stage_errors: list[tuple[str, str]] = []
    stage_summary: dict[str, Any] = {}

    outline_errors = OUTLINE.validate_receipt(outline_contract, outline)
    stage_summary["outline_performance"] = {
        "passed": not outline_errors,
        "error_count": len(outline_errors),
    }
    stage_errors.extend(("outline_performance", item) for item in outline_errors)

    prewrite_errors, prewrite_summary = DRAFT_PREWRITE.validate_batch(
        prose_receipt=prose_receipt,
        emotional_receipt=emotional_receipt,
        source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
        outline=outline,
    )
    stage_summary["draft_prewrite"] = {
        "passed": not prewrite_errors,
        "error_count": len(prewrite_errors),
        "summary": prewrite_summary,
    }
    stage_errors.extend(("draft_prewrite", item) for item in prewrite_errors)

    include_release = all(
        item is not None
        for item in (
            writing_receipt,
            source_receipt,
            ledger,
            sequence_receipt,
            opening_contract,
            profile,
        )
    )
    if include_release:
        release_errors = WRITE_RELEASE.validate_release(
            "draft",
            writing_receipt,
            source_receipt,
            ledger,
            opening_contract=opening_contract,
            outline_contract=outline_contract,
            profile=profile,
            sequence_receipt=sequence_receipt,
            prose_contract=prose_receipt,
            primary_source_original=source_original,
            emotional_contract=emotional_receipt,
            source_emotion_ledger=source_emotion_ledger,
        )
        stage_summary["write_release"] = {
            "passed": not release_errors,
            "error_count": len(release_errors),
        }
        stage_errors.extend(("write_release", item) for item in release_errors)
    else:
        stage_summary["write_release"] = {
            "passed": None,
            "error_count": 0,
            "skipped": True,
        }

    grouped = aggregate_errors(stage_errors)
    focus_work_order = aggregate_focus_work_order(grouped)
    return {
        "blocked": bool(stage_errors),
        "stage_summary": stage_summary,
        "work_order": grouped,
        "focus_work_order": focus_work_order,
        "total_unique_blockers": sum(len(item["messages"]) for item in grouped),
    }


def compact_report(report: dict[str, Any], max_messages: int = 3) -> dict[str, Any]:
    compact = dict(report)
    for key in ("work_order", "focus_work_order"):
        items: list[dict[str, Any]] = []
        for item in report.get(key) or []:
            copy = dict(item)
            messages = list(item.get("messages") or [])
            copy["messages"] = messages[:max_messages]
            copy["omitted_message_count"] = max(0, len(messages) - max_messages)
            items.append(copy)
        compact[key] = items
    return compact


def _print_blocked_report(report: dict[str, Any], max_messages: int = 3) -> None:
    print("batch_prewrite_blockers: blocked")
    if report["focus_work_order"]:
        print(
            "聚焦顺序：" + " -> ".join(item["label"] for item in report["focus_work_order"])
        )
        for item in report["focus_work_order"]:
            print(
                f"{{{item['label']}}} stages={','.join(item['stages'])} source_categories={','.join(item['source_categories'])}"
            )
            print(f"  next_action: {item['next_action']}")
            for message in item["messages"][:max_messages]:
                print(f"  - {message}")
            omitted = max(0, len(item["messages"]) - max_messages)
            if omitted:
                print(f"  ... 省略 {omitted} 条同类阻断")
    print(
        "优先顺序："
        + " -> ".join(item["label"] for item in report["work_order"])
    )
    for item in report["work_order"]:
        print(f"[{item['label']}] stages={','.join(item['stages'])}")
        print(f"  next_action: {item['next_action']}")
        for message in item["messages"][:max_messages]:
            print(f"  - {message}")
        omitted = max(0, len(item["messages"]) - max_messages)
        if omitted:
            print(f"  ... 省略 {omitted} 条同类阻断")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate outline/prewrite blockers into a deduplicated work order."
    )
    parser.add_argument("--outline-contract", required=True)
    parser.add_argument("--outline", required=True)
    parser.add_argument("--prose-receipt", required=True)
    parser.add_argument("--emotional-receipt", required=True)
    parser.add_argument("--source-original", required=True)
    parser.add_argument("--source-emotion-ledger", required=True)
    parser.add_argument("--writing-receipt")
    parser.add_argument("--source-receipt")
    parser.add_argument("--ledger")
    parser.add_argument("--sequence-receipt")
    parser.add_argument("--opening-contract")
    parser.add_argument("--profile")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--max-messages", type=int, default=3)
    args = parser.parse_args()

    report = scan_blockers(
        outline_contract=Path(args.outline_contract).resolve(),
        outline=Path(args.outline).resolve(),
        prose_receipt=Path(args.prose_receipt).resolve(),
        emotional_receipt=Path(args.emotional_receipt).resolve(),
        source_original=Path(args.source_original).resolve(),
        source_emotion_ledger=Path(args.source_emotion_ledger).resolve(),
        writing_receipt=Path(args.writing_receipt).resolve() if args.writing_receipt else None,
        source_receipt=Path(args.source_receipt).resolve() if args.source_receipt else None,
        ledger=Path(args.ledger).resolve() if args.ledger else None,
        sequence_receipt=Path(args.sequence_receipt).resolve() if args.sequence_receipt else None,
        opening_contract=Path(args.opening_contract).resolve() if args.opening_contract else None,
        profile=Path(args.profile).resolve() if args.profile else None,
    )
    if report["blocked"]:
        rendered = (
            report
            if args.full
            else compact_report(report, max(1, args.max_messages))
        )
        if args.json:
            print(json.dumps(rendered, ensure_ascii=False, indent=2))
        else:
            _print_blocked_report(rendered, max(1, args.max_messages))
        return 2
    print("batch_prewrite_blockers: passed")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
