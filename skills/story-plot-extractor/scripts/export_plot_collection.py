#!/usr/bin/env python3
"""聚合导出多个工作区为总情节库。"""
import argparse
import json
from pathlib import Path

from export_plot_bundle import build_exchange_payload  # noqa: E402
from plot_extractor_core import load_analysis  # noqa: E402


def _discover_workspaces(output_root: Path) -> list[Path]:
    workspaces = []
    for child in sorted(output_root.iterdir()):
        if child.is_dir() and (child / "metadata.json").exists():
            if load_analysis(child):
                workspaces.append(child)
    return workspaces


def build_collection_payload(workspaces: list[Path]) -> dict:
    novels = []
    plots = []
    characters = []
    for workspace in workspaces:
        payload = build_exchange_payload(workspace)
        novels.append(payload["novel"])
        plots.extend(payload["plots"])
        characters.append({
            "workspace": str(workspace),
            "novel_title": payload["novel"].get("title") or workspace.name,
            "characters": payload.get("characters") or [],
        })
    return {
        "schema_name": "plot-extractor-collection",
        "schema_version": "1.0",
        "workspace_count": len(workspaces),
        "novels": novels,
        "plots": plots,
        "characters": characters,
        "stats": {
            "novel_count": len(novels),
            "plot_count": len(plots),
            "character_group_count": len(characters),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="聚合导出多个工作区为总情节库")
    parser.add_argument("source", help="工作区根目录，或单个工作区目录")
    parser.add_argument("--output", help="输出文件路径；默认写到 source 下的 collection.json")
    parser.add_argument("--plots-only", action="store_true", help="只导出聚合后的 plots 数组")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists():
        print(f"[ERROR] 源路径不存在: {source}", flush=True)
        return 1

    if source.is_dir() and (source / "metadata.json").exists():
        workspaces = [source]
        default_output = source / "collection.json"
    else:
        workspaces = _discover_workspaces(source)
        default_output = source / "collection.json"
    if not workspaces:
        print(f"[ERROR] 未发现有效工作区: {source}", flush=True)
        return 1

    payload = build_collection_payload(workspaces)
    data = payload["plots"] if args.plots_only else payload
    output_path = Path(args.output).resolve() if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "source": str(source),
        "output": str(output_path),
        "plots_only": args.plots_only,
        "workspace_count": payload["stats"]["novel_count"],
        "plot_count": payload["stats"]["plot_count"],
        "schema_version": payload["schema_version"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
