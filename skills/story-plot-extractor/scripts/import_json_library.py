#!/usr/bin/env python3
"""导入本地 JSON 情节库为 plot-extractor 工作区。"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from plot_extractor_core import extract_characters_from_plots, save_analysis, safe_name  # noqa: E402
from search_plot_library import _load_json_plot_sources  # noqa: E402


def _to_workspace_plot(plot: dict) -> dict:
    end_chapter = plot.get("end_chapter")
    return {
        "plot_name": plot.get("plot_name") or "",
        "plot_type": plot.get("plot_type") or "",
        "start_chapter": plot.get("start_chapter"),
        "end_chapter": end_chapter,
        "core_conflict": plot.get("core_conflict") or "",
        "plot_summary": plot.get("plot_summary") or "",
        "emotional_arc": plot.get("emotional_arc") or "",
        "plot_status": plot.get("plot_status") or ("进行中" if end_chapter == "进行中" else "已完结"),
        "key_turning_points": plot.get("key_turning_points") or [],
        "main_characters": plot.get("main_characters") or [],
        "themes": plot.get("themes") or [],
    }


def _safe_chapter_no(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def build_workspaces_from_json(source: Path, output_root: Path) -> dict:
    plots = _load_json_plot_sources(str(source))
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for plot in plots:
        novel_title = (plot.get("novel_title") or "").strip() or "unknown"
        novel_id = str(plot.get("novel_id") or novel_title)
        grouped[(novel_title, novel_id)].append(plot)

    imported = []
    for (novel_title, novel_id), novel_plots in sorted(grouped.items(), key=lambda x: x[0][0]):
        workspace_plots = [_to_workspace_plot(plot) for plot in novel_plots]
        characters = extract_characters_from_plots(workspace_plots)
        chapter_values = []
        for plot in workspace_plots:
            start = _safe_chapter_no(plot.get("start_chapter"))
            end = _safe_chapter_no(plot.get("end_chapter")) or start
            if start > 0:
                chapter_values.extend([start, end])
        max_chapter = max(chapter_values, default=0)
        metadata = {
            "title": novel_title,
            "novel_id": novel_id,
            "author": "",
            "description": "",
            "total_chapters": max_chapter,
            "analyzed_range": f"1-{max_chapter}" if max_chapter else "",
            "source_path": str(source),
            "failed_ranges": [],
            "mode": "imported_json_library",
        }
        save_dir = save_analysis(output_root, novel_title, metadata, workspace_plots, characters)
        imported.append({
            "title": novel_title,
            "novel_id": novel_id,
            "path": str(save_dir),
            "plot_count": len(workspace_plots),
            "character_count": len(characters),
        })

    return {
        "source": str(source),
        "output_root": str(output_root),
        "workspace_count": len(imported),
        "workspaces": imported,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 JSON 情节库为 plot-extractor 工作区")
    parser.add_argument("source", help="JSON 文件或目录")
    parser.add_argument("--output-root", default=".plot-extractor-output", help="导入后的工作区根目录")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists():
        print(f"[ERROR] 源路径不存在: {source}", flush=True)
        return 1
    output_root = Path(args.output_root).resolve()
    result = build_workspaces_from_json(source, output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
