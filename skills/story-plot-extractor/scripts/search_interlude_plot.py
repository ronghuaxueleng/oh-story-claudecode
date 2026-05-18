#!/usr/bin/env python3
"""插曲检索：从情节库中搜索适合跨题材改编的小插曲。"""
import argparse
import json
from pathlib import Path

from search_plot_library import PlotNeo4jClient, _expand_terms, _load_json_plot_sources, _passes_interlude_length, _safe_chapter_no, _score_interlude_plot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="从 Neo4j 或本地 JSON 情节库中搜索插曲情节")
    parser.add_argument("terms", nargs="+", help="一个或多个检索关键词")
    parser.add_argument("--novel", help="只搜索标题中包含该词的小说")
    parser.add_argument("--limit", type=int, default=20, help="最多返回多少条候选")
    parser.add_argument("--type", help="按 plot_type 过滤")
    parser.add_argument("--chapter-range", help="按章节范围过滤，格式如 1-120")
    parser.add_argument("--json-library", help="本地 JSON 情节库路径；可传单个 JSON 文件或目录")
    parser.add_argument("--structure-terms", nargs="*", default=[], help="额外传入的结构词")
    parser.add_argument("--length", choices=["light", "short"], default="light", help="插曲长度：light=单章，short=2-3章")
    args = parser.parse_args()

    query_terms = [t.strip() for t in args.terms if t.strip()]
    if not query_terms:
        print("[ERROR] 至少提供一个检索关键词", flush=True)
        return 1
    expanded_terms = _expand_terms(query_terms)
    chapter_start = None
    chapter_end = None
    if args.chapter_range:
        try:
            left, right = args.chapter_range.split("-", 1)
            chapter_start = int(left.strip())
            chapter_end = int(right.strip())
        except Exception:
            print("[ERROR] --chapter-range 格式错误，应为 start-end，例如 1-120", flush=True)
            return 1

    candidates = []
    library_mode = "json" if args.json_library else "neo4j"
    if args.json_library:
        try:
            plots = _load_json_plot_sources(args.json_library)
        except Exception as exc:
            print(f"[ERROR] 读取 JSON 情节库失败: {exc}", flush=True)
            return 1
        if args.novel:
            plots = [p for p in plots if args.novel in (p.get("novel_title") or "")]
        for plot in plots:
            if args.type and args.type not in (plot.get("plot_type") or ""):
                continue
            if not _passes_interlude_length(plot, args.length):
                continue
            if chapter_start is not None and chapter_end is not None:
                start_ch = _safe_chapter_no(plot.get("start_chapter"))
                end_ch = _safe_chapter_no(plot.get("end_chapter")) or start_ch
                if end_ch < chapter_start or start_ch > chapter_end:
                    continue
            score, reasons = _score_interlude_plot(plot, expanded_terms, structure_terms=args.structure_terms)
            if score <= 0:
                continue
            candidates.append({
                "novel_id": plot.get("novel_id") or "",
                "novel_title": plot.get("novel_title") or "",
                "plot_id": plot.get("plot_id") or "",
                "plot_name": plot.get("plot_name") or "",
                "plot_type": plot.get("plot_type") or "",
                "core_conflict": plot.get("core_conflict") or "",
                "emotional_arc": plot.get("emotional_arc") or "",
                "themes": plot.get("themes") or [],
                "start_chapter": plot.get("start_chapter"),
                "end_chapter": plot.get("end_chapter"),
                "source_file": plot.get("source_file") or "",
                "score": score,
                "match_reasons": reasons[:5],
            })
    else:
        neo4j = PlotNeo4jClient()
        if not neo4j.is_available():
            print("[ERROR] Neo4j 不可用。请配置 PLOT_EXTRACTOR_NEO4J_URI/USER/PASSWORD。", flush=True)
            return 1
        plots = neo4j.search_candidate_plots(
            terms=expanded_terms + list(args.structure_terms or []),
            novel_keyword=args.novel or "",
            type_keyword=args.type or "",
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            limit=max(args.limit * 80, 400),
        )
        for plot in plots:
            if not _passes_interlude_length(plot, args.length):
                continue
            score, reasons = _score_interlude_plot(plot, expanded_terms, structure_terms=args.structure_terms)
            if score <= 0:
                continue
            candidates.append({
                "novel_id": plot.get("novel_id") or "",
                "novel_title": plot.get("novel_title") or "",
                "plot_id": plot.get("id") or "",
                "plot_name": plot.get("name") or "",
                "plot_type": plot.get("type") or "",
                "core_conflict": plot.get("core_conflict") or "",
                "emotional_arc": plot.get("emotional_arc") or "",
                "themes": plot.get("themes") or [],
                "start_chapter": plot.get("start_chapter"),
                "end_chapter": plot.get("end_chapter"),
                "source_file": "",
                "score": score,
                "match_reasons": reasons[:5],
            })

    candidates.sort(key=lambda x: (-x["score"], str(x["novel_id"]), _safe_chapter_no(x["start_chapter"])))
    result = {
        "library_mode": library_mode,
        "mode": "interlude",
        "length": args.length,
        "json_library": args.json_library or "",
        "query_terms": query_terms,
        "expanded_terms": expanded_terms,
        "novel_filter": args.novel or "",
        "type_filter": args.type or "",
        "chapter_range": args.chapter_range or "",
        "count": len(candidates[: args.limit]),
        "results": candidates[: args.limit],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
