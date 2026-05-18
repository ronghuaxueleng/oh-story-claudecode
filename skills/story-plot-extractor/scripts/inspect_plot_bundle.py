#!/usr/bin/env python3
"""检查 plot-extractor 工作区或 JSON 情节库。"""
import argparse
import json
from pathlib import Path

from plot_extractor_core import load_analysis  # noqa: E402
from search_plot_library import _load_json_plot_sources  # noqa: E402


def _safe_int(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _top_items(items: list, limit: int = 5) -> list:
    return items[:limit]


def _is_template_name(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    template_terms = ["实力提升", "冲突升级", "迎来危机", "矛盾激化", "新的挑战", "局势变化", "关系变化"]
    return text in template_terms


def _build_workspace_warnings(plots: list[dict], characters: list[dict], failed_ranges: list[dict], total_chapters: int) -> list[dict]:
    warnings: list[dict] = []
    if failed_ranges:
        warnings.append({
            "severity": "high",
            "type": "failed_ranges",
            "message": f"存在 {len(failed_ranges)} 个失败区间，提取结果不完整。",
            "suggestion": "先运行 retry 补救失败区间，再评估 plot 质量。",
        })

    if not plots:
        warnings.append({
            "severity": "high",
            "type": "empty_plots",
            "message": "plots 为空，当前工作区没有可用情节结果。",
            "suggestion": "检查输入 TXT 分章是否正常，或重新运行 extract。",
        })
        return warnings

    spans = []
    empty_conflict = 0
    empty_emotion = 0
    template_names = 0
    ongoing_count = 0
    no_character_count = 0
    for plot in plots:
        start = _safe_int(plot.get("start_chapter"))
        end = _safe_int(plot.get("end_chapter")) or start
        if start > 0:
            spans.append(max(1, end - start + 1))
        if not (plot.get("core_conflict") or "").strip():
            empty_conflict += 1
        if not (plot.get("emotional_arc") or "").strip():
            empty_emotion += 1
        if _is_template_name(plot.get("plot_name") or ""):
            template_names += 1
        if plot.get("plot_status") == "进行中":
            ongoing_count += 1
        if not (plot.get("main_characters") or []):
            no_character_count += 1

    avg_span = sum(spans) / len(spans) if spans else 0
    max_span = max(spans) if spans else 0
    total_plots = len(plots)
    total_characters = len(characters)

    if max_span >= 30 or avg_span > 12:
        warnings.append({
            "severity": "medium",
            "type": "coarse_plots",
            "message": f"情节粒度偏粗，平均跨度 {avg_span:.1f} 章，最大跨度 {max_span} 章。",
            "suggestion": "减小 batch-size，或检查原文分章是否过粗。",
        })

    if total_chapters and total_plots >= total_chapters * 0.8:
        warnings.append({
            "severity": "medium",
            "type": "fragmented_plots",
            "message": f"plot 数量过密，{total_plots} 条 plot 对应 {total_chapters} 章，疑似拆得过碎。",
            "suggestion": "适当增大 batch-size，避免每章都拆成单独 plot。",
        })

    if template_names >= max(3, total_plots // 5):
        warnings.append({
            "severity": "medium",
            "type": "template_plot_names",
            "message": f"存在 {template_names} 条模板化 plot 名称，命名信息量偏低。",
            "suggestion": "重点抽查 plot_name 和 core_conflict，必要时重提相关批次。",
        })

    if empty_conflict >= max(2, total_plots // 6):
        warnings.append({
            "severity": "medium",
            "type": "empty_conflict",
            "message": f"有 {empty_conflict} 条 plot 缺少 core_conflict。",
            "suggestion": "检查提取 prompt 或对异常批次补提。",
        })

    if empty_emotion >= max(2, total_plots // 5):
        warnings.append({
            "severity": "low",
            "type": "empty_emotional_arc",
            "message": f"有 {empty_emotion} 条 plot 缺少 emotional_arc。",
            "suggestion": "可在后处理或补提时强化情绪弧线字段。",
        })

    if no_character_count >= max(3, total_plots // 4):
        warnings.append({
            "severity": "medium",
            "type": "missing_main_characters",
            "message": f"有 {no_character_count} 条 plot 未抽出 main_characters。",
            "suggestion": "检查该批原文是否角色指向不清，或补提角色信息。",
        })

    ongoing_ratio = ongoing_count / total_plots if total_plots else 0
    if ongoing_ratio >= 0.35:
        warnings.append({
            "severity": "medium",
            "type": "too_many_ongoing_plots",
            "message": f"进行中 plot 过多，占比 {ongoing_ratio:.0%}。",
            "suggestion": "检查跨批延续是否合并不足，必要时复查连续章节。",
        })

    if total_characters and total_characters > total_plots * 1.5:
        warnings.append({
            "severity": "low",
            "type": "character_cardinality_high",
            "message": f"角色数 {total_characters} 相对 plot 数 {total_plots} 偏高。",
            "suggestion": "检查是否把大量一次性路人也抽进 characters.json。",
        })

    return warnings


def _build_json_library_warnings(plots: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    if not plots:
        warnings.append({
            "severity": "high",
            "type": "empty_library",
            "message": "JSON 情节库为空，没有可检索 plot。",
            "suggestion": "确认 JSON 文件结构是否符合 schema。",
        })
        return warnings

    missing_title = 0
    missing_conflict = 0
    missing_chapter = 0
    for plot in plots:
        if not (plot.get("novel_title") or "").strip():
            missing_title += 1
        if not (plot.get("core_conflict") or "").strip():
            missing_conflict += 1
        if _safe_int(plot.get("start_chapter")) <= 0:
            missing_chapter += 1

    total = len(plots)
    if missing_title >= max(2, total // 5):
        warnings.append({
            "severity": "medium",
            "type": "missing_novel_title",
            "message": f"有 {missing_title} 条 plot 缺少明确 novel_title。",
            "suggestion": "混合书库时建议每条 plot 显式写 novel_title。",
        })
    if missing_conflict >= max(2, total // 6):
        warnings.append({
            "severity": "medium",
            "type": "missing_core_conflict",
            "message": f"有 {missing_conflict} 条 plot 缺少 core_conflict。",
            "suggestion": "补齐冲突描述，否则搜索相关性会明显下降。",
        })
    if missing_chapter >= max(2, total // 4):
        warnings.append({
            "severity": "low",
            "type": "missing_chapter_span",
            "message": f"有 {missing_chapter} 条 plot 缺少有效 start_chapter。",
            "suggestion": "尽量补齐章节范围，便于按阶段检索。",
        })
    return warnings


def _build_collection_warnings(payload: dict) -> list[dict]:
    warnings: list[dict] = []
    plots = payload.get("plots") or []
    novels = payload.get("novels") or []
    stats = payload.get("stats") or {}

    if not plots:
        warnings.append({
            "severity": "high",
            "type": "empty_collection",
            "message": "聚合库没有任何 plot。",
            "suggestion": "检查 export-collection 的输入工作区是否有效。",
        })
        return warnings

    duplicate_ids = 0
    duplicate_pairs = 0
    missing_title = 0
    missing_conflict = 0
    very_long_span = 0
    seen_ids = set()
    seen_pairs = set()

    for plot in plots:
        novel_title = (plot.get("novel_title") or "").strip()
        plot_id = (plot.get("plot_id") or "").strip()
        plot_name = (plot.get("plot_name") or "").strip()
        if not novel_title:
            missing_title += 1
        if not (plot.get("core_conflict") or "").strip():
            missing_conflict += 1
        start = _safe_int(plot.get("start_chapter"))
        end = _safe_int(plot.get("end_chapter")) or start
        if start > 0 and end >= start and (end - start + 1) >= 50:
            very_long_span += 1
        id_key = (novel_title, plot_id)
        if plot_id:
            if id_key in seen_ids:
                duplicate_ids += 1
            else:
                seen_ids.add(id_key)
        pair_key = (novel_title, plot_name, start, end)
        if plot_name and start > 0:
            if pair_key in seen_pairs:
                duplicate_pairs += 1
            else:
                seen_pairs.add(pair_key)

    if stats.get("plot_count") not in (None, len(plots)):
        warnings.append({
            "severity": "medium",
            "type": "stats_plot_count_mismatch",
            "message": f"stats.plot_count={stats.get('plot_count')}，但实际 plots={len(plots)}。",
            "suggestion": "重新导出 collection，避免上层依赖错误统计。",
        })
    if stats.get("novel_count") not in (None, len(novels)):
        warnings.append({
            "severity": "medium",
            "type": "stats_novel_count_mismatch",
            "message": f"stats.novel_count={stats.get('novel_count')}，但实际 novels={len(novels)}。",
            "suggestion": "重新导出 collection，确保聚合统计一致。",
        })
    if duplicate_ids:
        warnings.append({
            "severity": "high",
            "type": "duplicate_plot_ids",
            "message": f"发现 {duplicate_ids} 条重复 plot_id（按 novel_title + plot_id 判重）。",
            "suggestion": "检查是否重复聚合同一工作区，或导出前先去重。",
        })
    if duplicate_pairs >= max(2, len(plots) // 20):
        warnings.append({
            "severity": "medium",
            "type": "duplicate_plot_pairs",
            "message": f"发现 {duplicate_pairs} 条疑似重复 plot（按书名+情节名+章节范围判重）。",
            "suggestion": "检查聚合源是否包含重复工作区或重复导入的数据。",
        })
    if missing_title >= max(2, len(plots) // 10):
        warnings.append({
            "severity": "medium",
            "type": "missing_novel_title",
            "message": f"有 {missing_title} 条聚合 plot 缺少 novel_title。",
            "suggestion": "导出前确保每个工作区都有稳定书名。",
        })
    if missing_conflict >= max(2, len(plots) // 8):
        warnings.append({
            "severity": "medium",
            "type": "missing_core_conflict",
            "message": f"有 {missing_conflict} 条聚合 plot 缺少 core_conflict。",
            "suggestion": "优先修复源工作区的提取质量，再重新聚合。",
        })
    if very_long_span >= max(3, len(plots) // 12):
        warnings.append({
            "severity": "low",
            "type": "too_many_long_span_plots",
            "message": f"有 {very_long_span} 条聚合 plot 跨度超过 50 章。",
            "suggestion": "这通常说明源工作区情节过粗，可先对源工作区做 inspect。",
        })
    return warnings


def _build_fix_suggestions(mode: str, target: str, warnings: list[dict]) -> list[dict]:
    suggestions: list[dict] = []
    seen = set()
    for warning in warnings:
        wtype = warning.get("type") or ""
        if wtype in seen:
            continue
        seen.add(wtype)

        if mode == "workspace":
            if wtype == "failed_ranges":
                suggestions.append({
                    "priority": "high",
                    "action": "retry_failed_ranges",
                    "command": f'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py retry -- "{target}"',
                    "reason": "先补齐失败区间，否则后续质量判断不完整。",
                })
            elif wtype == "coarse_plots":
                suggestions.append({
                    "priority": "medium",
                    "action": "reextract_with_smaller_batch",
                    "command": 'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py extract -- "小说.txt" --batch-size 1',
                    "reason": "减小 batch-size，降低单条 plot 的跨章跨度。",
                })
            elif wtype == "fragmented_plots":
                suggestions.append({
                    "priority": "medium",
                    "action": "reextract_with_larger_batch",
                    "command": 'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py extract -- "小说.txt" --batch-size 4',
                    "reason": "增大 batch-size，避免每章都被拆成独立 plot。",
                })
            elif wtype in {"template_plot_names", "empty_conflict", "empty_emotional_arc", "missing_main_characters"}:
                suggestions.append({
                    "priority": "medium",
                    "action": "review_and_reextract_problem_batches",
                    "command": f'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py inspect -- "{target}"',
                    "reason": "先定位问题工作区，再针对异常批次补提或重提。",
                })
            elif wtype == "too_many_ongoing_plots":
                suggestions.append({
                    "priority": "medium",
                    "action": "review_cross_batch_merge",
                    "command": f'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py inspect -- "{target}"',
                    "reason": "进行中情节过多，通常意味着跨批延续没有合并好，需要复查连续章节。",
                })
        elif mode == "json_library":
            if wtype in {"missing_novel_title", "missing_core_conflict", "missing_chapter_span"}:
                suggestions.append({
                    "priority": "medium",
                    "action": "normalize_json_library_fields",
                    "command": f'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py inspect -- "{target}" --json-library',
                    "reason": "先定位缺字段问题，再按 schema 补齐书名、冲突和章节范围。",
                })
            elif wtype == "empty_library":
                suggestions.append({
                    "priority": "high",
                    "action": "verify_json_schema",
                    "command": f'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py inspect -- "{target}" --json-library',
                    "reason": "先确认 JSON 文件结构是否符合 skill 支持的三种 schema。",
                })
        elif mode == "collection":
            if wtype in {"duplicate_plot_ids", "duplicate_plot_pairs"}:
                suggestions.append({
                    "priority": "high",
                    "action": "deduplicate_collection_sources",
                    "command": 'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py export-collection -- ".plot-extractor-output"',
                    "reason": "重复 plot 往往来自重复工作区或重复导入，需先清理源工作区再重新聚合。",
                })
            elif wtype in {"stats_plot_count_mismatch", "stats_novel_count_mismatch"}:
                suggestions.append({
                    "priority": "medium",
                    "action": "rebuild_collection",
                    "command": 'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py export-collection -- ".plot-extractor-output"',
                    "reason": "统计不一致通常说明 collection 文件过旧或被手动修改，直接重建更稳妥。",
                })
            elif wtype in {"missing_novel_title", "missing_core_conflict", "too_many_long_span_plots"}:
                suggestions.append({
                    "priority": "medium",
                    "action": "inspect_source_workspaces",
                    "command": 'python3 .codex/skills/plot-extractor/scripts/plot_extractor_cli.py list -- ".plot-extractor-output"',
                    "reason": "聚合库问题多数来自源工作区，先回源头做 inspect 再重新导出。",
                })
    return suggestions


def inspect_collection_file(target: Path, include_fix_suggestions: bool = False) -> dict:
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema_name") != "plot-extractor-collection":
        raise ValueError(f"不是有效的 collection 文件: {target}")
    plots = payload.get("plots") or []
    novels = payload.get("novels") or []
    warnings = _build_collection_warnings(payload)
    result = {
        "mode": "collection",
        "target": str(target),
        "workspace_count": payload.get("workspace_count") or 0,
        "novel_count": len(novels),
        "plot_count": len(plots),
        "warning_count": len(warnings),
        "warnings": warnings,
        "novel_titles": _top_items([n.get("title") or "" for n in novels if n.get("title")]),
        "sample_plots": _top_items([
            {
                "novel_title": p.get("novel_title") or "",
                "plot_name": p.get("plot_name") or "",
                "plot_type": p.get("plot_type") or "",
                "start_chapter": p.get("start_chapter"),
                "end_chapter": p.get("end_chapter"),
            }
            for p in plots
        ]),
        "stats": payload.get("stats") or {},
    }
    if include_fix_suggestions:
        result["fix_suggestions"] = _build_fix_suggestions("collection", str(target), warnings)
    return result


def inspect_workspace(target: Path, include_fix_suggestions: bool = False) -> dict:
    loaded = load_analysis(target)
    if not loaded:
        raise FileNotFoundError(f"未找到有效工作区: {target}")

    metadata = loaded.get("metadata") or {}
    plots = loaded.get("plots") or []
    characters = loaded.get("characters") or []
    failed_ranges = metadata.get("failed_ranges") or []
    chapter_spans = [
        (_safe_int(p.get("start_chapter")), _safe_int(p.get("end_chapter")) or _safe_int(p.get("start_chapter")))
        for p in plots
    ]
    valid_spans = [span for span in chapter_spans if span[0] > 0]
    start_chapter = min((s for s, _ in valid_spans), default=0)
    end_chapter = max((e for _, e in valid_spans), default=0)
    ongoing = [p for p in plots if p.get("plot_status") == "进行中"]
    warnings = _build_workspace_warnings(plots, characters, failed_ranges, metadata.get("total_chapters") or 0)

    result = {
        "mode": "workspace",
        "target": str(target),
        "title": metadata.get("title") or target.name,
        "author": metadata.get("author") or "",
        "total_chapters": metadata.get("total_chapters") or 0,
        "analyzed_range": metadata.get("analyzed_range") or "",
        "plot_count": len(plots),
        "character_count": len(characters),
        "failed_ranges": failed_ranges,
        "failed_range_count": len(failed_ranges),
        "ongoing_plot_count": len(ongoing),
        "warning_count": len(warnings),
        "warnings": warnings,
        "plot_chapter_span": {
            "start": start_chapter,
            "end": end_chapter,
        },
        "sample_plots": _top_items([
            {
                "plot_name": p.get("plot_name") or "",
                "plot_type": p.get("plot_type") or "",
                "start_chapter": p.get("start_chapter"),
                "end_chapter": p.get("end_chapter"),
            }
            for p in plots
        ]),
        "top_characters": _top_items([
            {
                "name": c.get("name") or "",
                "plot_count": c.get("plot_count") or 0,
                "protagonist_score": c.get("protagonist_score") or 0,
            }
            for c in sorted(characters, key=lambda x: -(x.get("plot_count") or 0))
        ]),
    }
    if include_fix_suggestions:
        result["fix_suggestions"] = _build_fix_suggestions("workspace", str(target), warnings)
    return result


def inspect_json_library(target: Path, include_fix_suggestions: bool = False) -> dict:
    plots = _load_json_plot_sources(str(target))
    novel_titles = sorted({p.get("novel_title") or "" for p in plots if p.get("novel_title")})
    plot_types: dict[str, int] = {}
    for plot in plots:
        plot_type = plot.get("plot_type") or "未标注"
        plot_types[plot_type] = plot_types.get(plot_type, 0) + 1

    start_values = [_safe_int(p.get("start_chapter")) for p in plots]
    end_values = [_safe_int(p.get("end_chapter")) or _safe_int(p.get("start_chapter")) for p in plots]
    valid_starts = [x for x in start_values if x > 0]
    valid_ends = [x for x in end_values if x > 0]
    warnings = _build_json_library_warnings(plots)

    result = {
        "mode": "json_library",
        "target": str(target),
        "plot_count": len(plots),
        "novel_count": len(novel_titles),
        "warning_count": len(warnings),
        "warnings": warnings,
        "novel_titles": _top_items(novel_titles),
        "plot_types": plot_types,
        "chapter_span": {
            "start": min(valid_starts, default=0),
            "end": max(valid_ends, default=0),
        },
        "sample_plots": _top_items([
            {
                "novel_title": p.get("novel_title") or "",
                "plot_name": p.get("plot_name") or "",
                "plot_type": p.get("plot_type") or "",
                "start_chapter": p.get("start_chapter"),
                "end_chapter": p.get("end_chapter"),
            }
            for p in plots
        ]),
    }
    if include_fix_suggestions:
        result["fix_suggestions"] = _build_fix_suggestions("json_library", str(target), warnings)
    return result


def list_workspaces(output_root: Path) -> dict:
    if not output_root.exists():
        raise FileNotFoundError(f"目录不存在: {output_root}")
    workspaces = []
    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "metadata.json").exists():
            continue
        loaded = load_analysis(child)
        if not loaded:
            continue
        metadata = loaded.get("metadata") or {}
        plots = loaded.get("plots") or []
        characters = loaded.get("characters") or []
        failed_ranges = metadata.get("failed_ranges") or []
        warnings = _build_workspace_warnings(plots, characters, failed_ranges, metadata.get("total_chapters") or 0)
        workspaces.append({
            "title": metadata.get("title") or child.name,
            "path": str(child),
            "plot_count": len(plots),
            "failed_range_count": len(failed_ranges),
            "warning_count": len(warnings),
            "warning_types": [w.get("type") or "" for w in warnings[:5]],
            "total_chapters": metadata.get("total_chapters") or 0,
            "mode": metadata.get("mode") or "",
        })
    return {
        "mode": "workspace_list",
        "target": str(output_root),
        "count": len(workspaces),
        "workspaces": workspaces,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查工作区或 JSON 情节库")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="检查单个工作区或 JSON 情节库")
    inspect_parser.add_argument("target", help="工作区目录，或 JSON 文件/目录")
    inspect_parser.add_argument("--json-library", action="store_true", help="将 target 按 JSON 情节库处理")
    inspect_parser.add_argument("--collection", action="store_true", help="将 target 按聚合库 collection.json 处理")
    inspect_parser.add_argument("--fix-suggestions", action="store_true", help="附带结构化修复动作建议")

    list_parser = subparsers.add_parser("list", help="列出某个输出根目录下的所有工作区")
    list_parser.add_argument("output_root", help="输出根目录，例如 .plot-extractor-output")

    args = parser.parse_args()

    try:
        if args.command == "inspect":
            target = Path(args.target).resolve()
            if args.collection:
                result = inspect_collection_file(target, include_fix_suggestions=args.fix_suggestions)
            elif target.is_file() and target.suffix.lower() == ".json":
                try:
                    raw = json.loads(target.read_text(encoding="utf-8"))
                except Exception:
                    raw = None
                if isinstance(raw, dict) and raw.get("schema_name") == "plot-extractor-collection":
                    result = inspect_collection_file(target, include_fix_suggestions=args.fix_suggestions)
                elif args.json_library:
                    result = inspect_json_library(target, include_fix_suggestions=args.fix_suggestions)
                else:
                    result = inspect_json_library(target, include_fix_suggestions=args.fix_suggestions)
            else:
                result = (
                    inspect_json_library(target, include_fix_suggestions=args.fix_suggestions)
                    if args.json_library
                    else inspect_workspace(target, include_fix_suggestions=args.fix_suggestions)
                )
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0
        if args.command == "list":
            output_root = Path(args.output_root).resolve()
            result = list_workspaces(output_root)
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", flush=True)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
