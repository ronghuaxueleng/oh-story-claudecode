#!/usr/bin/env python3
"""通用本地情节提取：解析 TXT、切章节、调用 AI 提取 plot 包。"""
import argparse
import json
import re
from pathlib import Path

from plot_extractor_core import (  # noqa: E402
    PlotExtractorAPIClient,
    parse_novel_txt,
    write_chapter_files,
    extract_plots_from_novel,
    extract_characters_from_plots,
    save_analysis,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="提取本地小说情节包")
    parser.add_argument("input_txt", help="本地 txt 小说路径")
    parser.add_argument("--title", help="覆盖解析出的书名")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--batch-size", type=int, default=3)
    parser.add_argument("--max-chars", type=int, default=3000)
    parser.add_argument("--output-root", default=".plot-extractor-output", help="输出根目录")
    parser.add_argument("--chapters-only", action="store_true", help="只切分章节并生成工作区，不调用 AI 提取")
    args = parser.parse_args()

    input_path = Path(args.input_txt).resolve()
    if not input_path.exists() or not input_path.is_file():
        print(f"[ERROR] 输入文件不存在: {input_path}", flush=True)
        return 1

    print(f"[INFO] 读取小说: {input_path}", flush=True)
    parsed = parse_novel_txt(str(input_path))
    title = (args.title or parsed.get("title") or input_path.stem).strip()
    chapters = parsed.get("chapters") or []
    if not chapters:
        print("[ERROR] 未解析出有效章节，无法提取情节。", flush=True)
        return 1

    output_root = Path(args.output_root).resolve()
    workspace = output_root / re.sub(r'[<>:"/\\\\|?*]', '', title).strip()
    workspace.mkdir(parents=True, exist_ok=True)
    chapter_assets = write_chapter_files(chapters, workspace)

    if args.chapters_only:
        metadata = {
            "title": title,
            "author": parsed.get("author") or "",
            "description": parsed.get("description") or "",
            "total_chapters": len(chapters),
            "analyzed_range": "",
            "source_path": str(input_path),
            "failed_ranges": [],
            "workspace": str(workspace),
            "batch_size": args.batch_size,
            "max_chars": args.max_chars,
            "mode": "chapters_only",
        }
        save_dir = save_analysis(output_root, title, metadata, [], [])
        summary = {
            "title": title,
            "total_chapters": len(chapters),
            "plot_count": 0,
            "character_count": 0,
            "failed_ranges": [],
            "save_dir": str(save_dir),
            "chapter_assets": chapter_assets,
            "mode": "chapters_only",
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        return 0

    api = PlotExtractorAPIClient()
    model = args.model

    print(
        f"[INFO] 书名: {title} | 章节数: {len(chapters)} | 模型: {model} | batch_size={args.batch_size}",
        flush=True,
    )

    def on_progress(batch_num: int, total_batches: int, plots_so_far: int):
        print(
            f"[PROGRESS] 批次 {batch_num}/{total_batches} | 当前情节数 {plots_so_far}",
            flush=True,
        )

    all_plots, failed_ranges = extract_plots_from_novel(
        api=api,
        model=model,
        chapters=chapters,
        batch_size=max(1, args.batch_size),
        max_chars_per_chapter=max(500, args.max_chars),
        on_progress=on_progress,
    )
    characters = extract_characters_from_plots(all_plots)

    metadata = {
        "title": title,
        "author": parsed.get("author") or "",
        "description": parsed.get("description") or "",
        "total_chapters": len(chapters),
        "analyzed_range": f"1-{chapters[-1]['number']}",
        "source_path": str(input_path),
        "failed_ranges": failed_ranges,
        "workspace": str(workspace),
        "batch_size": args.batch_size,
        "max_chars": args.max_chars,
        "mode": "local_extract",
    }
    save_dir = save_analysis(output_root, title, metadata, all_plots, characters)

    summary = {
        "title": title,
        "total_chapters": len(chapters),
        "plot_count": len(all_plots),
        "character_count": len(characters),
        "failed_ranges": failed_ranges,
        "save_dir": str(save_dir),
        "chapter_assets": chapter_assets,
        "mode": "full_extract",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
