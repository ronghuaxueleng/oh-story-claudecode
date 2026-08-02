#!/usr/bin/env python3
"""Complete incremental upgrade tasks for existing short-analyze outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


STYLE_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
LEGACY_TEMPLATE_MARKER = "本 SF 的叙述口气不先替人物下总判断"
STYLE_REANALYSIS_TASKS_FILE = "_style_reanalysis_tasks.json"


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def load_original_lines(root: Path) -> list[str]:
    original_dir = root / "原文"
    lines: list[str] = []
    for path in source_originals(root):
        lines.extend(read_text(path).splitlines())
    return lines


def source_originals(root: Path) -> list[Path]:
    original_dir = root / "原文"
    if not original_dir.is_dir():
        return []
    return sorted(candidate.resolve() for candidate in original_dir.iterdir() if candidate.is_file())


def source_slice(lines: list[str], source_range: str) -> str:
    parts = [
        part.strip()
        for part in re.split(r"[、,，]\s*", source_range.strip())
        if part.strip()
    ]
    slices: list[str] = []
    for part in parts:
        match = re.fullmatch(r"L(\d+)-L(\d+)", part)
        if not match:
            return ""
        start, end = int(match.group(1)), int(match.group(2))
        if start < 1 or end > len(lines) or start > end:
            return ""
        slices.append("\n".join(lines[start - 1 : end]))
    return "\n".join(slices)


def sync_source_excerpts(root: Path) -> dict[str, Any]:
    root = root.resolve()
    index_path = root / "写作资产" / "子流程索引.jsonl"
    if not index_path.is_file():
        return {
            "updated": False,
            "updated_subflows": [],
            "invalid_source_range_subflows": [],
        }

    original_lines = load_original_lines(root)
    updated_subflows: list[str] = []
    invalid_source_range_subflows: list[str] = []
    new_lines: list[str] = []
    changed = False

    for raw in read_text(index_path).splitlines():
        if not raw.strip():
            continue
        entry = json.loads(raw)
        if not isinstance(entry, dict):
            raise ValueError(f"{index_path} 存在非对象 JSONL 条目")
        subflow_id = str(entry.get("subflow_id") or "<unknown>")
        source_range = str(entry.get("source_range") or "").strip()
        excerpt = source_slice(original_lines, source_range)
        if not excerpt:
            invalid_source_range_subflows.append(subflow_id)
        elif str(entry.get("source_excerpt") or "") != excerpt:
            entry["source_excerpt"] = excerpt
            updated_subflows.append(subflow_id)
            changed = True
        new_lines.append(json.dumps(entry, ensure_ascii=False))

    if changed:
        index_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return {
        "updated": changed,
        "updated_subflows": updated_subflows,
        "invalid_source_range_subflows": invalid_source_range_subflows,
    }


def candidate_quotes(entry: dict[str, Any], excerpt: str) -> list[str]:
    quotes: list[str] = []
    for field in ("source_evidence",):
        value = entry.get(field)
        if isinstance(value, list):
            quotes.extend(str(item).strip() for item in value if str(item).strip())
    causal = entry.get("causal_preconditions")
    if isinstance(causal, dict):
        value = causal.get("source_evidence")
        if isinstance(value, list):
            quotes.extend(str(item).strip() for item in value if str(item).strip())
    seen: list[str] = []
    for quote in quotes:
        if quote in excerpt and quote not in seen:
            seen.append(quote)
    if len(seen) >= 2:
        return seen[:2]

    fallback = [
        line.strip()
        for line in excerpt.splitlines()
        if line.strip()
    ]
    for line in fallback:
        if line not in seen:
            seen.append(line)
        if len(seen) >= 2:
            break
    return seen[:2]


def style_validation_reasons(style: Any, excerpt: str) -> list[str]:
    if not isinstance(style, dict):
        return ["missing_source_style_granularity"]
    reasons: list[str] = []
    evidence_groups: dict[tuple[str, ...], list[str]] = {}
    unique_quotes: set[str] = set()
    for field in STYLE_FIELDS:
        item = style.get(field)
        if not isinstance(item, dict):
            reasons.append(f"missing_style_field:{field}")
            continue
        analysis = str(item.get("analysis") or "").strip()
        if not analysis:
            reasons.append(f"empty_style_analysis:{field}")
        elif LEGACY_TEMPLATE_MARKER in analysis:
            reasons.append(f"legacy_templated_style_analysis:{field}")
        evidence = item.get("source_evidence")
        quotes = (
            [str(quote).strip() for quote in evidence if str(quote).strip()]
            if isinstance(evidence, list)
            else []
        )
        if len(set(quotes)) < 2:
            reasons.append(f"insufficient_style_evidence:{field}")
        elif any(quote not in excerpt for quote in quotes):
            reasons.append(f"out_of_range_style_evidence:{field}")
        normalized_quotes = tuple(sorted(set(quotes)))
        if normalized_quotes:
            evidence_groups.setdefault(normalized_quotes, []).append(field)
            unique_quotes.update(normalized_quotes)
    if len(unique_quotes) < 4:
        reasons.append("insufficient_distinct_style_evidence_across_fields")
    for fields in evidence_groups.values():
        if len(fields) >= 4:
            reasons.append(
                "style_evidence_group_reused_across_too_many_fields:"
                + ",".join(fields)
            )
    return reasons


def collect_style_reanalysis_tasks(root: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    root = root.resolve()
    index_path = root / "写作资产" / "子流程索引.jsonl"
    missing_style: list[str] = []
    templated_style: list[str] = []
    task_entries: list[tuple[dict[str, Any], str, str, list[str]]] = []
    tasks: list[dict[str, Any]] = []
    if not index_path.is_file():
        missing_style.append("子流程索引.jsonl")
    else:
        original_files = source_originals(root)
        original_lines = load_original_lines(root)
        entries: list[dict[str, Any]] = []
        for raw in read_text(index_path).splitlines():
            if not raw.strip():
                continue
            entry = json.loads(raw)
            if not isinstance(entry, dict):
                raise ValueError(f"{index_path} 存在非对象 JSONL 条目")
            entries.append(entry)

        repeated_analyses: dict[tuple[str, str], list[str]] = {}
        for entry in entries:
            subflow_id = str(entry.get("subflow_id") or "<unknown>")
            style = entry.get("source_style_granularity")
            if not isinstance(style, dict):
                continue
            for field in STYLE_FIELDS:
                item = style.get(field)
                analysis = str(item.get("analysis") or "").strip() if isinstance(item, dict) else ""
                if analysis:
                    repeated_analyses.setdefault((field, analysis), []).append(subflow_id)
        repeated_subflows = {
            subflow_id
            for subflow_ids in repeated_analyses.values()
            if len(subflow_ids) >= 3
            for subflow_id in subflow_ids
        }

        for entry in entries:
            subflow_id = str(entry.get("subflow_id") or "<unknown>")
            source_range = str(entry.get("source_range") or "").strip()
            excerpt = source_slice(original_lines, source_range)
            reasons = style_validation_reasons(entry.get("source_style_granularity"), excerpt)
            if subflow_id in repeated_subflows:
                reasons.append("cross_subflow_repeated_style_analysis")
            if "missing_source_style_granularity" in reasons:
                missing_style.append(subflow_id)
            if any("templated" in reason or "repeated" in reason for reason in reasons):
                templated_style.append(subflow_id)
            if reasons:
                task_entries.append((entry, source_range, excerpt, reasons))

        for entry, source_range, excerpt, reasons in task_entries:
            subflow_id = str(entry.get("subflow_id") or "<unknown>")
            tasks.append(
                {
                    "subflow_id": subflow_id,
                    "reasons": reasons,
                    "source_files": [str(path) for path in original_files],
                    "source_range": source_range,
                    "source_excerpt": excerpt,
                    "existing_source_evidence": candidate_quotes(entry, excerpt),
                    "required_style_fields": list(STYLE_FIELDS),
                    "write_target": "写作资产/子流程索引.jsonl",
                    "requirements": [
                        "逐条重读 source_excerpt，不得依据事件摘要、旧 analysis 或通用文风模板推断。",
                        "六类 analysis 均须按本 SF 的实际句段、对白、动作和叙述口气独立撰写。",
                        "每类字段至少保留两条不同且完全位于 source_range 的原文证据。",
                        "六类字段合计至少覆盖四条不同原文证据，同一证据组不得覆盖四个及以上字段。",
                        "不得写入旧版自动拼接模板，也不得在此任务文件中填写文风结论。",
                    ],
                }
            )
    return tasks, missing_style, templated_style


def write_style_reanalysis_tasks(root: Path) -> dict[str, Any]:
    root = root.resolve()
    task_path = root / STYLE_REANALYSIS_TASKS_FILE
    tasks, missing_style, templated_style = collect_style_reanalysis_tasks(root)
    if not tasks:
        if task_path.exists():
            task_path.unlink()
        return {
            "path": None,
            "task_count": 0,
            "missing_source_style_subflows": missing_style,
            "templated_source_style_subflows": templated_style,
        }
    payload = {
        "version": 1,
        "kind": "source_style_reanalysis_tasks",
        "root": str(root),
        "instructions": (
            "这是模型执行任务，不是自动补写素材。当前模型必须逐 SF 重读 source_excerpt，"
            "将真实文风分析写回子流程索引；完成后重新运行本检查器与 finalize。"
        ),
        "tasks": tasks,
    }
    task_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(task_path),
        "task_count": len(tasks),
        "missing_source_style_subflows": missing_style,
        "templated_source_style_subflows": templated_style,
    }


def inspect_root(root: Path) -> dict[str, Any]:
    excerpt_sync = sync_source_excerpts(root)
    task_result = write_style_reanalysis_tasks(root)
    missing_style = task_result["missing_source_style_subflows"]
    templated_style = task_result["templated_source_style_subflows"]
    task_path = task_result["path"]
    needs_reanalysis = bool(
        task_result["task_count"] or missing_style or templated_style
    )
    return {
        "root": str(root),
        "status": "needs_model_reanalysis" if needs_reanalysis else "ready_for_finalize",
        "missing_source_style_subflows": missing_style,
        "templated_source_style_subflows": templated_style,
        "source_excerpt_synced_subflows": excerpt_sync["updated_subflows"],
        "invalid_source_range_subflows": excerpt_sync["invalid_source_range_subflows"],
        "style_reanalysis_task_file": task_path,
        "style_reanalysis_task_count": task_result["task_count"],
        "next_action": (
            "逐 SF 重读 source_range 内原文，人工重写六类 source_style_granularity；"
            "不得调用本脚本生成文风字段或标记人工复核完成。"
            if needs_reanalysis
            else "可运行 run_short_analyze_finalize.py 重新生成 profile 与无损编译包。"
        ),
    }


def process_root(root: Path) -> dict[str, Any]:
    """Compatibility entry point: inspect only, never fabricate semantic assets."""
    return inspect_root(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="补齐历史拆书目录的完整增量升级收尾内容")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    payload = inspect_root(Path(args.root))
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
    return 0 if payload["status"] == "ready_for_finalize" else 2


if __name__ == "__main__":
    raise SystemExit(main())
