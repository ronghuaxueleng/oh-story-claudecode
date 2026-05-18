#!/usr/bin/env python3
"""对本地已提取小说工作区的失败区间做补救重试。"""
import argparse
import json
from pathlib import Path

from plot_extractor_core import (  # noqa: E402
    PlotExtractorAPIClient,
    parse_novel_txt,
    retry_failed_ranges,
    extract_characters_from_plots,
    load_analysis,
    save_analysis,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="重试本地小说情节提取失败区间")
    parser.add_argument("workspace", help="已解析工作区目录")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--max-chars", type=int, default=3000)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    loaded = load_analysis(workspace)
    if not loaded:
        print(f"[ERROR] 未找到已解析工作区: {workspace}", flush=True)
        return 1

    metadata = loaded.get("metadata") or {}
    existing_plots = loaded.get("plots") or []
    failed_ranges = metadata.get("failed_ranges") or []
    source_path = metadata.get("source_path") or ""
    if not source_path:
        print("[ERROR] metadata.json 缺少 source_path，无法重试。", flush=True)
        return 1
    if not failed_ranges:
        print("[INFO] 没有失败区间，无需重试。", flush=True)
        return 0

    source_file = Path(source_path)
    if not source_file.exists():
        print(f"[ERROR] 原始小说文件不存在: {source_file}", flush=True)
        return 1

    parsed = parse_novel_txt(str(source_file))
    chapters = parsed.get("chapters") or []
    if not chapters:
        print("[ERROR] 原始小说未解析出章节，无法重试。", flush=True)
        return 1

    api = PlotExtractorAPIClient()
    recovered, still_failed = retry_failed_ranges(
        api=api,
        model=args.model,
        all_chapters=chapters,
        failed_ranges=failed_ranges,
        existing_plots=existing_plots,
        max_chars_per_chapter=max(500, args.max_chars),
    )
    merged_plots = existing_plots + recovered
    characters = extract_characters_from_plots(merged_plots)
    metadata["failed_ranges"] = still_failed

    save_dir = save_analysis(workspace.parent, metadata.get("title") or workspace.name, metadata, merged_plots, characters)
    summary = {
        "title": metadata.get("title") or workspace.name,
        "recovered_plot_count": len(recovered),
        "remaining_failed_ranges": still_failed,
        "plot_count": len(merged_plots),
        "character_count": len(characters),
        "save_dir": str(save_dir),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
