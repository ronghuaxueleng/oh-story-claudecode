#!/usr/bin/env python3
"""导出 plot-extractor 工作区为统一交换格式。"""
import argparse
import json
from pathlib import Path

from plot_extractor_core import load_analysis  # noqa: E402


def _normalize_plot(plot: dict, novel_title: str, novel_id: str, source_workspace: str, idx: int) -> dict:
    return {
        "source_file": str(Path(source_workspace) / "plots.json"),
        "source_workspace": source_workspace,
        "novel_id": novel_id,
        "novel_title": novel_title,
        "plot_id": plot.get("plot_id") or plot.get("id") or f"plot:{idx}",
        "plot_name": plot.get("plot_name") or plot.get("name") or "",
        "plot_type": plot.get("plot_type") or plot.get("type") or "",
        "core_conflict": plot.get("core_conflict") or "",
        "plot_summary": plot.get("plot_summary") or "",
        "emotional_arc": plot.get("emotional_arc") or "",
        "themes": plot.get("themes") or [],
        "start_chapter": plot.get("start_chapter"),
        "end_chapter": plot.get("end_chapter"),
        "plot_status": plot.get("plot_status") or "",
        "main_characters": plot.get("main_characters") or [],
        "key_turning_points": plot.get("key_turning_points") or [],
    }


def build_exchange_payload(workspace: Path) -> dict:
    loaded = load_analysis(workspace)
    if not loaded:
        raise FileNotFoundError(f"未找到有效工作区: {workspace}")

    metadata = loaded.get("metadata") or {}
    plots = loaded.get("plots") or []
    characters = loaded.get("characters") or []
    title = metadata.get("title") or workspace.name
    novel_id = str(metadata.get("novel_id") or workspace.name)

    normalized_plots = [
        _normalize_plot(plot, title, novel_id, str(workspace), idx)
        for idx, plot in enumerate(plots, start=1)
    ]

    return {
        "schema_name": "plot-extractor-exchange",
        "schema_version": "1.0",
        "exported_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "workspace": str(workspace),
        "novel": {
            "novel_id": novel_id,
            "title": title,
            "author": metadata.get("author") or "",
            "description": metadata.get("description") or "",
            "total_chapters": metadata.get("total_chapters") or 0,
            "analyzed_range": metadata.get("analyzed_range") or "",
            "source_path": metadata.get("source_path") or "",
            "failed_ranges": metadata.get("failed_ranges") or [],
            "mode": metadata.get("mode") or "",
        },
        "plots": normalized_plots,
        "characters": characters,
        "stats": {
            "plot_count": len(normalized_plots),
            "character_count": len(characters),
            "failed_range_count": len(metadata.get("failed_ranges") or []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导出工作区为统一交换格式")
    parser.add_argument("workspace", help="工作区目录")
    parser.add_argument("--output", help="输出文件路径；默认写到工作区下的 exchange.json")
    parser.add_argument("--plots-only", action="store_true", help="只导出标准化后的 plots 数组")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    payload = build_exchange_payload(workspace)
    output_path = Path(args.output).resolve() if args.output else workspace / "exchange.json"

    if args.plots_only:
        data = payload["plots"]
    else:
        data = payload

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "workspace": str(workspace),
        "output": str(output_path),
        "plots_only": args.plots_only,
        "plot_count": payload["stats"]["plot_count"],
        "character_count": payload["stats"]["character_count"],
        "schema_version": payload["schema_version"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
