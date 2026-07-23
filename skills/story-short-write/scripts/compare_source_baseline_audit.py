#!/usr/bin/env python3
"""Compare a draft audit with its source-text baseline for imitation tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def total_light_hits(audit: dict[str, Any]) -> int:
    summary = audit.get("light_summary")
    if isinstance(summary, dict) and isinstance(summary.get("total_hits"), int):
        return int(summary["total_hits"])
    report = audit.get("light_report") if isinstance(audit.get("light_report"), dict) else audit
    keys = (
        "line_hits",
        "uniform_paragraph_blocks",
        "dense_flashback_chains",
        "over_effective_dialogue_blocks",
        "opening_signature_risks",
        "opening_signal_overload",
        "opening_reveal_chain",
        "author_stance_overreach",
    )
    total = 0
    for key in keys:
        value = report.get(key)
        if isinstance(value, list):
            total += len(value)
    return total


def heavy_summary(audit: dict[str, Any]) -> dict[str, Any]:
    direct = audit.get("heavy_summary")
    if isinstance(direct, dict):
        return direct
    heavy = audit.get("heavy_report")
    if isinstance(heavy, dict) and isinstance(heavy.get("summary"), dict):
        return heavy["summary"]
    summary = audit.get("summary")
    return summary if isinstance(summary, dict) else {}


def line_hit_types(audit: dict[str, Any]) -> dict[str, int]:
    report = audit.get("light_report") if isinstance(audit.get("light_report"), dict) else audit
    raw = report.get("line_hit_types")
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items() if isinstance(v, int)}
    return {}


def heavy_rule_counts(audit: dict[str, Any]) -> dict[str, int]:
    summary = heavy_summary(audit)
    counts: dict[str, int] = {}
    for key in ("high_findings", "medium_findings", "low_findings"):
        findings = summary.get(key)
        if not isinstance(findings, list):
            continue
        for item in findings:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("rule_id") or item.get("label") or "").strip()
            count = item.get("count")
            if rule_id and isinstance(count, int):
                counts[rule_id] = counts.get(rule_id, 0) + count
    return counts


def risk_band(score: float) -> str:
    if score >= 75:
        return "high-risk"
    if score >= 55:
        return "medium-risk"
    if score >= 35:
        return "low-risk"
    return "clean"


def compare(source: dict[str, Any], draft: dict[str, Any], tolerance: float) -> dict[str, Any]:
    source_heavy = heavy_summary(source)
    draft_heavy = heavy_summary(draft)
    source_score = float(source_heavy.get("score") or 0)
    draft_score = float(draft_heavy.get("score") or 0)
    delta = round(draft_score - source_score, 2)

    source_types = line_hit_types(source)
    draft_types = line_hit_types(draft)
    shared_types = sorted(set(source_types) & set(draft_types))
    draft_extra_types = {
        key: value
        for key, value in draft_types.items()
        if value > source_types.get(key, 0)
    }
    source_like_types = {
        key: draft_types[key]
        for key in shared_types
        if draft_types[key] <= source_types.get(key, 0)
    }
    source_heavy_rules = heavy_rule_counts(source)
    draft_heavy_rules = heavy_rule_counts(draft)
    shared_heavy_rules = {
        key: {
            "source_count": source_heavy_rules[key],
            "draft_count": draft_heavy_rules[key],
        }
        for key in sorted(set(source_heavy_rules) & set(draft_heavy_rules))
        if draft_heavy_rules[key] <= source_heavy_rules[key]
    }
    draft_extra_heavy_rules = {
        key: {
            "source_count": source_heavy_rules.get(key, 0),
            "draft_count": count,
            "delta": count - source_heavy_rules.get(key, 0),
        }
        for key, count in draft_heavy_rules.items()
        if count > source_heavy_rules.get(key, 0)
    }

    # A shared heavy-rule hit can dominate the total score in both texts.
    # Never treat score delta alone as proof that a granularity imitation is over-regularized.
    if not draft_extra_types and not draft_extra_heavy_rules:
        verdict = "baseline_aligned"
        action = "重审计总分差仅作诊断；没有新增规则或轻审计类型时，不因分数本身回炉。"
    else:
        verdict = "manual_extra_shell_review"
        action = (
            "仅人工裁决新增的轻审计类型和新增重审计规则。"
            "共同重审计规则、原文同级短句和高密对白不得仅因总分差进入回炉。"
        )

    return {
        "version": "1.0",
        "comparison_mode": "source_baseline_for_imitation",
        "tolerance": tolerance,
        "source": {
            "file": source.get("file"),
            "light_hits": total_light_hits(source),
            "heavy_score": source_score,
            "heavy_status": source_heavy.get("status") or risk_band(source_score),
            "line_hit_types": source_types,
        },
        "draft": {
            "file": draft.get("file"),
            "light_hits": total_light_hits(draft),
            "heavy_score": draft_score,
            "heavy_status": draft_heavy.get("status") or risk_band(draft_score),
            "line_hit_types": draft_types,
        },
        "delta": {
            "heavy_score": delta,
            "light_hits": total_light_hits(draft) - total_light_hits(source),
        },
        "source_like_line_hit_types": source_like_types,
        "draft_extra_line_hit_types": draft_extra_types,
        "heavy_rule_comparison": {
            "source_rule_counts": source_heavy_rules,
            "draft_rule_counts": draft_heavy_rules,
            "shared_baseline_rules": shared_heavy_rules,
            "draft_extra_rules": draft_extra_heavy_rules,
            "score_delta_is_diagnostic_only": True,
        },
        "verdict": verdict,
        "recommended_action": action,
        "manual_review_required": [
            "事件颗粒度是否保持主体 BID 全集",
            "情绪拍序和同级烈度是否缩水",
            "新增风险是否属于新稿机械壳，而不是原文爆款形状",
            "人物偏手、错答、控制权变化是否仍成立",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-audit", required=True, help="Source full audit JSON")
    parser.add_argument("--draft-audit", required=True, help="Draft full audit JSON")
    parser.add_argument("--output", required=True, help="Output comparison JSON")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=8.0,
        help="Allowed heavy-score delta before treating the draft as more regularized than source",
    )
    args = parser.parse_args()

    result = compare(
        load_json(Path(args.source_audit)),
        load_json(Path(args.draft_audit)),
        args.tolerance,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"source_baseline_audit: {result['verdict']}")
    print(f"source_score: {result['source']['heavy_score']} / draft_score: {result['draft']['heavy_score']} / delta: {result['delta']['heavy_score']}")
    print(f"output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
