#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对齐朱雀 PDF 与 full audit JSON，生成代理校准摘要。")
    parser.add_argument("root", help="包含 txt/md 与朱雀 pdf 的目录")
    parser.add_argument("--audit-dir", required=True, help="run_full_ai_audit.py 输出目录")
    parser.add_argument("--output", default="zhuque_alignment.csv", help="输出 CSV 路径")
    parser.add_argument(
        "--summary-output",
        default="zhuque_alignment_summary.json",
        help="输出摘要 JSON 路径",
    )
    parser.add_argument(
        "--internal-standard-output",
        default="internal_audit_standard.json",
        help="输出内部审计标准 JSON 路径；后续日常审计与回炉只依赖这份文件。",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="遇到无法解析的 PDF 直接退出；默认跳过并记录失败清单。",
    )
    return parser.parse_args()


def read_pdf_text(pdf_path: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext 失败: {pdf_path}\n{proc.stderr}")
    return proc.stdout


def parse_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def parse_zhuque_pdf(pdf_path: Path) -> dict:
    text = read_pdf_text(pdf_path)
    tokens = [line.strip() for line in text.splitlines() if line.strip()]
    segments: list[dict] = []
    i = 0
    while i < len(tokens) - 4:
        if (
            re.fullmatch(r"\d+", tokens[i])
            and re.fullmatch(r"片段\d+", tokens[i + 1])
            and re.fullmatch(r"\d+(?:\.\d+)?%", tokens[i + 2])
            and re.fullmatch(r"\d+", tokens[i + 3])
            and re.fullmatch(r"0(?:\.\d+)?|1(?:\.0+)?", tokens[i + 4])
        ):
            segments.append(
                {
                    "index": int(tokens[i]),
                    "label": tokens[i + 1],
                    "ratio_pct": float(tokens[i + 2].rstrip("%")),
                    "chars": int(tokens[i + 3]),
                    "aigc": float(tokens[i + 4]),
                }
            )
            i += 5
            continue
        i += 1
    if not segments:
        raise RuntimeError(f"未能从 PDF 解析到片段表: {pdf_path}")
    weighted_avg = sum(item["aigc"] * item["ratio_pct"] for item in segments) / 100.0
    return {
        "segment_count": len(segments),
        "weighted_avg": round(weighted_avg, 4),
        "max_seg": round(max(item["aigc"] for item in segments), 4),
        "min_seg": round(min(item["aigc"] for item in segments), 4),
        "segments": segments,
    }


def find_source_for_pdf(pdf_path: Path) -> Path | None:
    txt = pdf_path.with_suffix(".txt")
    md = pdf_path.with_suffix(".md")
    if txt.exists():
        return txt
    if md.exists():
        return md
    return None


def load_audit_json(audit_dir: Path, stem: str) -> dict | None:
    path = audit_dir / f"{stem}.full_audit.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def metric_max(items: list[dict], key: str) -> float | None:
    values = [parse_float(item.get(key)) for item in items]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(max(values), 2)


def metric_min(items: list[dict], key: str) -> float | None:
    values = [parse_float(item.get(key)) for item in items]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(min(values), 2)


def metric_mean(items: list[dict], key: str) -> float | None:
    values = [parse_float(item.get(key)) for item in items]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def metric_mean_top_n(items: list[dict], key: str, n: int) -> float | None:
    values = [parse_float(item.get(key)) for item in items]
    values = sorted((value for value in values if value is not None), reverse=True)[:n]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def rankdata(values: list[float]) -> list[float]:
    ordered = sorted((value, idx) for idx, value in enumerate(values))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
            j += 1
        rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[ordered[k][1]] = rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    rx = rankdata(xs)
    ry = rankdata(ys)
    mean_x = statistics.mean(rx)
    mean_y = statistics.mean(ry)
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    den_x = sum((a - mean_x) ** 2 for a in rx)
    den_y = sum((b - mean_y) ** 2 for b in ry)
    den = (den_x * den_y) ** 0.5
    if den == 0:
        return None
    return round(num / den, 4)


def solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    a = [row[:] for row in matrix]
    b = vector[:]
    for i in range(size):
        pivot = max(range(i, size), key=lambda row: abs(a[row][i]))
        if abs(a[pivot][i]) < 1e-12:
            return None
        a[i], a[pivot] = a[pivot], a[i]
        b[i], b[pivot] = b[pivot], b[i]
        div = a[i][i]
        a[i] = [item / div for item in a[i]]
        b[i] /= div
        for row in range(size):
            if row == i:
                continue
            factor = a[row][i]
            a[row] = [left - factor * right for left, right in zip(a[row], a[i])]
            b[row] -= factor * b[i]
    return b


def multi_linear_fit(rows: list[dict], feature_names: list[str], target_key: str) -> dict | None:
    samples: list[tuple[list[float], float]] = []
    for row in rows:
        xs: list[float] = []
        valid = True
        for name in feature_names:
            value = parse_float(row.get(name))
            if value is None:
                valid = False
                break
            xs.append(value)
        y = parse_float(row.get(target_key))
        if not valid or y is None:
            continue
        samples.append((xs, y))
    if len(samples) < 6:
        return None

    size = len(feature_names) + 1
    matrix = [[0.0] * size for _ in range(size)]
    vector = [0.0] * size
    for xs, y in samples:
        row = [1.0] + xs
        for i in range(size):
            vector[i] += row[i] * y
            for j in range(size):
                matrix[i][j] += row[i] * row[j]
    coeffs = solve_linear_system(matrix, vector)
    if not coeffs:
        return None

    ys = [item[1] for item in samples]
    preds = [coeffs[0] + sum(c * x for c, x in zip(coeffs[1:], xs)) for xs, _ in samples]
    mean_y = statistics.mean(ys)
    ss_res = sum((y - pred) ** 2 for y, pred in zip(ys, preds))
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r2 = None if ss_tot == 0 else 1 - ss_res / ss_tot
    return {
        "intercept": round(coeffs[0], 6),
        "coefficients": {name: round(value, 6) for name, value in zip(feature_names, coeffs[1:])},
        "r2": round(r2, 4) if r2 is not None else None,
        "feature_count": len(feature_names),
        "sample_count": len(samples),
        "target": target_key,
    }


def extract_alignment_features(audit: dict) -> dict:
    display_blocks = audit.get("display_block_scores", [])
    paragraph_scores = audit.get("paragraph_scores", [])
    segment_scores = audit.get("segment_scores", [])
    block_max = metric_max(display_blocks, "risk_score")
    block_min = metric_min(display_blocks, "risk_score")
    hot_count_total = 0
    hot_block_count = 0
    hot_peak_max: float | None = None
    for block in display_blocks:
        hot_paragraphs = block.get("hot_paragraphs", [])
        if hot_paragraphs:
            hot_block_count += 1
            hot_count_total += len(hot_paragraphs)
        for item in hot_paragraphs:
            value = parse_float(item.get("risk_score"))
            if value is None:
                continue
            if hot_peak_max is None or value > hot_peak_max:
                hot_peak_max = value
    return {
        "our_display_block_max": block_max,
        "our_display_block_top2_mean": metric_mean_top_n(display_blocks, "risk_score", 2),
        "our_display_block_min": block_min,
        "our_display_block_mean": metric_mean(display_blocks, "risk_score"),
        "our_display_block_range": round(block_max - block_min, 2) if block_max is not None and block_min is not None else None,
        "our_display_block_over25": sum(1 for item in display_blocks if parse_float(item.get("risk_score")) is not None and float(item["risk_score"]) >= 25),
        "our_display_block_over30": sum(1 for item in display_blocks if parse_float(item.get("risk_score")) is not None and float(item["risk_score"]) >= 30),
        "our_hot_paragraph_total": hot_count_total,
        "our_hot_block_count": hot_block_count,
        "our_hot_paragraph_peak": round(hot_peak_max, 2) if hot_peak_max is not None else None,
        "our_dynamic_seg_max": metric_max(segment_scores, "risk_score"),
        "our_dynamic_seg_top3_mean": metric_mean_top_n(segment_scores, "risk_score", 3),
        "our_paragraph_max": metric_max(paragraph_scores, "risk_score"),
        "our_paragraph_top5_mean": metric_mean_top_n(paragraph_scores, "risk_score", 5),
        "our_paragraph_top10_mean": metric_mean_top_n(paragraph_scores, "risk_score", 10),
    }


def build_rows(root: Path, audit_dir: Path, strict: bool = False) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    failures: list[dict] = []
    for pdf_path in sorted(root.rglob("*.pdf")):
        source_path = find_source_for_pdf(pdf_path)
        if not source_path:
            continue
        try:
            zhuque = parse_zhuque_pdf(pdf_path)
        except Exception as exc:  # noqa: BLE001
            if strict:
                raise
            failures.append({"pdf": str(pdf_path), "source": str(source_path), "reason": str(exc)})
            continue
        audit = load_audit_json(audit_dir, source_path.stem)
        row = {
            "source": str(source_path),
            "pdf": str(pdf_path),
            "stem": source_path.stem,
            "zhuque_weighted_avg": zhuque["weighted_avg"],
            "zhuque_max_seg": zhuque["max_seg"],
            "zhuque_min_seg": zhuque["min_seg"],
            "zhuque_segment_count": zhuque["segment_count"],
        }
        if audit:
            row.update(
                {
                    "our_heavy_score": audit.get("heavy_summary", {}).get("score"),
                    "our_heavy_status": audit.get("heavy_summary", {}).get("status"),
                }
            )
            row.update(extract_alignment_features(audit))
        rows.append(row)
    return rows, failures


def correlation_rows(rows: list[dict]) -> list[dict]:
    metrics = [
        "our_heavy_score",
        "our_display_block_max",
        "our_display_block_top2_mean",
        "our_display_block_min",
        "our_display_block_mean",
        "our_display_block_range",
        "our_display_block_over25",
        "our_display_block_over30",
        "our_hot_paragraph_total",
        "our_hot_block_count",
        "our_hot_paragraph_peak",
        "our_dynamic_seg_max",
        "our_dynamic_seg_top3_mean",
        "our_paragraph_max",
        "our_paragraph_top5_mean",
        "our_paragraph_top10_mean",
    ]
    out: list[dict] = []
    for metric in metrics:
        metric_rows = [row for row in rows if row.get(metric) is not None]
        if len(metric_rows) < 3:
            continue
        xs = [float(row[metric]) for row in metric_rows]
        out.append(
            {
                "metric": metric,
                "vs_zhuque_weighted_avg": spearman(xs, [float(row["zhuque_weighted_avg"]) for row in metric_rows]),
                "vs_zhuque_max_seg": spearman(xs, [float(row["zhuque_max_seg"]) for row in metric_rows]),
            }
        )
    return out


def pick_best_metric(correlations: list[dict], target_key: str, positive_only: bool = False) -> dict | None:
    ranked: list[dict] = []
    for item in correlations:
        value = parse_float(item.get(target_key))
        if value is None:
            continue
        if positive_only and value <= 0:
            continue
        ranked.append(item)
    if not ranked:
        return None
    ranked.sort(
        key=lambda item: (
            abs(parse_float(item.get(target_key)) or 0.0),
            abs(parse_float(item.get("vs_zhuque_weighted_avg")) or 0.0),
        ),
        reverse=True,
    )
    return ranked[0]


def build_best_multi_calibration(rows: list[dict], target_key: str) -> dict | None:
    candidates = [
        ["our_heavy_score"],
        ["our_display_block_range"],
        ["our_hot_paragraph_total"],
        ["our_heavy_score", "our_display_block_range"],
        ["our_heavy_score", "our_hot_paragraph_total"],
        ["our_display_block_range", "our_hot_paragraph_total"],
        ["our_display_block_range", "our_hot_block_count"],
        ["our_heavy_score", "our_display_block_over25"],
        ["our_heavy_score", "our_display_block_range", "our_hot_paragraph_total"],
    ]
    fits: list[dict] = []
    for feature_names in candidates:
        fit = multi_linear_fit(rows, feature_names, target_key)
        if fit:
            fits.append(fit)
    if not fits:
        return None
    fits.sort(
        key=lambda item: (
            parse_float(item.get("r2")) or -1.0,
            -int(item.get("feature_count", 99)),
        ),
        reverse=True,
    )
    best = fits[0]
    coefficients = best.pop("coefficients", {})
    best["features"] = list(coefficients.keys())
    best["weights"] = coefficients
    return best


def write_csv(rows: list[dict], output_path: Path) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_summary(rows: list[dict], failures: list[dict], correlations: list[dict], args: argparse.Namespace) -> dict:
    best_weighted = pick_best_metric(correlations, "vs_zhuque_weighted_avg", positive_only=True)
    best_max_seg = pick_best_metric(correlations, "vs_zhuque_max_seg", positive_only=True)
    fallback_weighted = pick_best_metric(correlations, "vs_zhuque_weighted_avg")
    fallback_max_seg = pick_best_metric(correlations, "vs_zhuque_max_seg")
    segment_counts = [int(row["zhuque_segment_count"]) for row in rows if row.get("zhuque_segment_count") is not None]
    return {
        "root": str(Path(args.root).resolve()),
        "audit_dir": str(Path(args.audit_dir).resolve()),
        "sample_count": len(rows),
        "parse_failure_count": len(failures),
        "parse_failures": failures,
        "zhuque_segment_count_range": {
            "min": min(segment_counts) if segment_counts else None,
            "max": max(segment_counts) if segment_counts else None,
            "avg": round(sum(segment_counts) / len(segment_counts), 2) if segment_counts else None,
        },
        "correlations": correlations,
        "best_metric_vs_zhuque_weighted_avg": best_weighted,
        "best_metric_vs_zhuque_max_seg": best_max_seg,
        "fallback_metric_vs_zhuque_weighted_avg": fallback_weighted,
        "fallback_metric_vs_zhuque_max_seg": fallback_max_seg,
        "calibration_models": {
            "zhuque_weighted_avg": build_best_multi_calibration(rows, "zhuque_weighted_avg"),
            "zhuque_max_seg": build_best_multi_calibration(rows, "zhuque_max_seg"),
        },
        "recommendation": {
            "primary_tracking_metric": best_max_seg["metric"] if best_max_seg else None,
            "secondary_tracking_metric": best_weighted["metric"] if best_weighted else None,
            "note": "优先盯最高外部块的正相关代理值，因此先看 vs_zhuque_max_seg 的正相关指标；全文平均只作辅助。",
        },
    }


def build_internal_standard(summary: dict) -> dict:
    return {
        "version": "1.0",
        "type": "internal_audit_standard",
        "calibrated_from": "zhuque_pdf_alignment",
        "sample_count": summary.get("sample_count"),
        "parse_failure_count": summary.get("parse_failure_count"),
        "segment_count_range": summary.get("zhuque_segment_count_range"),
        "calibration_models": summary.get("calibration_models", {}),
        "recommendation": summary.get("recommendation", {}),
        "passline": {
            "priority": "max_block",
            "max_block": {
                "high_risk_gt": 0.75,
                "needs_revision_gte": 0.60,
                "ready_for_check_lt": 0.60,
            },
            "overall": {
                "needs_revision_gte": 0.55,
            },
        },
        "legacy_source": {
            "best_metric_vs_zhuque_weighted_avg": summary.get("best_metric_vs_zhuque_weighted_avg"),
            "best_metric_vs_zhuque_max_seg": summary.get("best_metric_vs_zhuque_max_seg"),
            "fallback_metric_vs_zhuque_weighted_avg": summary.get("fallback_metric_vs_zhuque_weighted_avg"),
            "fallback_metric_vs_zhuque_max_seg": summary.get("fallback_metric_vs_zhuque_max_seg"),
        },
        "notes": [
            "这是一份内部标准文件。校准来源是历史朱雀检测样本，但后续日常使用只依赖本文件。",
            "判定优先看最高块风险分，其次再看整体风险分。",
        ],
    }


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    audit_dir = Path(args.audit_dir).resolve()
    output_path = Path(args.output).resolve()
    summary_output_path = Path(args.summary_output).resolve()
    internal_standard_output_path = Path(args.internal_standard_output).resolve()

    rows, failures = build_rows(root, audit_dir, strict=args.strict)
    write_csv(rows, output_path)
    correlations = correlation_rows(rows)
    summary = build_summary(rows, failures, correlations, args)
    internal_standard = build_internal_standard(summary)
    summary_output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    internal_standard_output_path.write_text(json.dumps(internal_standard, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"有效样本数: {len(rows)}")
    print(f"解析失败数: {len(failures)}")
    print(f"CSV: {output_path}")
    print(f"摘要: {summary_output_path}")
    print(f"内部标准: {internal_standard_output_path}")
    print("相关性:")
    print(json.dumps(correlations, ensure_ascii=False, indent=2))
    if failures:
        print("解析失败样本:")
        print(json.dumps(failures[:10], ensure_ascii=False, indent=2))
    print("推荐追踪指标:")
    print(json.dumps(summary["recommendation"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
