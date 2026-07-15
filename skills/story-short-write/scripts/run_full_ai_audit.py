#!/usr/bin/env python3
"""
统一运行项目内轻审计 + skill 内重审计，并合并输出。

用法:
  .venv/bin/python scripts/run_full_ai_audit.py path/to/file.md
  .venv/bin/python scripts/run_full_ai_audit.py path/to/file.md --output-dir audit_reports
  .venv/bin/python scripts/run_full_ai_audit.py path/to/file.md --myconfig-root /path/to/external/myconfig-aiwei
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path


def legacy_external_audit_key(suffix: str) -> str:
    return "".join(["zh", "uque_", suffix])


MICRO_SEGMENT_TARGET_CHARS = 260
MICRO_SEGMENT_MIN_CHARS = 180
MICRO_SEGMENT_MAX_CHARS = 340
COARSE_SEGMENT_TARGET_CHARS = 2600
COARSE_SEGMENT_MIN_CHARS = 1800
COARSE_SEGMENT_MAX_CHARS = 3600


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def load_json_output(name: str, stdout: str, stderr: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} 输出不是合法 JSON。\nstderr:\n{stderr}\nstdout:\n{stdout}") from exc


def load_profile(profile_path: Path | None) -> dict:
    if not profile_path:
        return {}
    if not profile_path.exists():
        raise RuntimeError(f"profile 不存在: {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def load_json_file(path: Path | None) -> dict:
    if not path:
        return {}
    if not path.exists():
        raise RuntimeError(f"JSON 不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_audit_rulebook(path: Path | None) -> dict:
    data = load_json_file(path)
    if not isinstance(data, dict):
        return {}
    if data.get("type") != "story_short_write_audit_rulebook":
        return {}
    return data


def parse_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def coeff_var(values: list[int | float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = statistics.mean(values)
    if mean_value == 0:
        return 0.0
    return statistics.pstdev(values) / mean_value


def build_sample_grading_guidance(profile: dict) -> dict:
    grading = profile.get("sample_grading", {}) if isinstance(profile, dict) else {}
    if not isinstance(grading, dict) or not grading:
        return {}
    raw_level = grading.get("level")
    raw_dna_usable = grading.get("dna_usable")
    summary = grading.get("summary")
    learnable_layers = grading.get("learnable_layers", [])
    forbidden_layers = grading.get("forbidden_layers", [])
    misuse_warnings = grading.get("misuse_warnings", [])
    usage_guidance = grading.get("usage_guidance", {})
    final_verdict = grading.get("final_verdict", {})
    source_buckets = profile.get("sample_source_buckets", {})
    if not isinstance(source_buckets, dict):
        source_buckets = {}
    effective_level = source_buckets.get("effective_write_level")
    if not isinstance(effective_level, str) or not effective_level.strip():
        effective_level = raw_level
    level = effective_level
    effective_dna_usable = source_buckets.get("effective_dna_usable")
    if not isinstance(effective_dna_usable, str) or not effective_dna_usable.strip():
        effective_dna_usable = raw_dna_usable
    dna_usable = effective_dna_usable
    notes: list[str] = []
    if raw_level and raw_level != level:
        notes.append(f"融合包原始最严等级为 `{raw_level}`，但有效写作等级按来源分桶修正为 `{level}`。")
    if level == "B类骨架样本":
        notes.append("当前 profile 标记为 `B类骨架样本`：只学骨架、承重件、后果链、场面秩序，不学现成句法壳。")
    elif level == "C类负样本":
        notes.append("当前 profile 标记为 `C类负样本`：只可用于反面规则和禁写提醒，不可并入正向融合。")
    elif level == "A类正样本":
        notes.append("当前 profile 标记为 `A类正样本`：可提句法、口气、动作落点和桥段承重件。")
    if isinstance(raw_dna_usable, str) and raw_dna_usable and raw_dna_usable != dna_usable:
        notes.append(f"融合包原始 DNA 可用性为 `{raw_dna_usable}`，但实际写作按 `{dna_usable}` 处理。")
    if isinstance(dna_usable, str) and dna_usable:
        notes.append(f"DNA 提取可用性：`{dna_usable}`。")
    effective_allow_dna = source_buckets.get("effective_allow_dna")
    if not isinstance(effective_allow_dna, str):
        effective_allow_dna = ""
    if isinstance(final_verdict, dict):
        allow_dna_value = effective_allow_dna or final_verdict.get("allow_dna")
        if allow_dna_value in ("否", "不可"):
            notes.append("这份样本不允许直接当句法 DNA 源使用。")
        if final_verdict.get("negative_only") == "是":
            notes.append("这份样本只可进入负面规则库。")
    positive_dna_sources = source_buckets.get("positive_dna_sources", [])
    skeleton_only_sources = source_buckets.get("skeleton_only_sources", [])
    negative_only_sources = source_buckets.get("negative_only_sources", [])
    blocked_opening_sources = source_buckets.get("blocked_opening_sources", [])
    effective_write_policy = source_buckets.get("effective_write_policy")
    if isinstance(positive_dna_sources, list) and positive_dna_sources:
        notes.append(f"当前正向 DNA 来源：`{' / '.join(positive_dna_sources[:6])}`。")
    if isinstance(skeleton_only_sources, list) and skeleton_only_sources:
        notes.append(f"当前仅可提骨架来源：`{' / '.join(skeleton_only_sources[:6])}`。")
    if isinstance(negative_only_sources, list) and negative_only_sources:
        notes.append(f"当前只可进反面规则的来源：`{' / '.join(negative_only_sources[:6])}`。")
    hard_stops: list[str] = []
    if level == "B类骨架样本":
        hard_stops.append("不要把这份参考稿的现成句法壳、总结句和整齐翻刀链当成可继承 DNA。")
    if level == "C类负样本":
        hard_stops.append("不要把这份参考稿并入正向融合 profile，也不要提取它的句法口气。")
    if isinstance(forbidden_layers, list):
        for item in forbidden_layers[:6]:
            if isinstance(item, str) and item.strip():
                hard_stops.append(f"禁学层：{item.strip()}")
    if isinstance(negative_only_sources, list) and negative_only_sources:
        hard_stops.append(f"不要把这些来源并入正向融合：{' / '.join(negative_only_sources[:6])}")
    if isinstance(skeleton_only_sources, list) and skeleton_only_sources:
        hard_stops.append(f"这些来源只可提骨架、承重件和后果链：{' / '.join(skeleton_only_sources[:6])}")
    if isinstance(blocked_opening_sources, list) and blocked_opening_sources:
        hard_stops.append(f"这些来源不得直接拿来学首屏讲法：{' / '.join(blocked_opening_sources[:6])}")
    if isinstance(effective_write_policy, str) and effective_write_policy.strip():
        notes.append(effective_write_policy.strip())
    return {
        "level": level,
        "raw_level": raw_level,
        "raw_dna_usable": raw_dna_usable,
        "dna_usable": dna_usable,
        "summary": summary,
        "learnable_layers": [item for item in learnable_layers if isinstance(item, str)][:8],
        "forbidden_layers": [item for item in forbidden_layers if isinstance(item, str)][:8],
        "misuse_warnings": [item for item in misuse_warnings if isinstance(item, str)][:8],
        "usage_guidance": usage_guidance if isinstance(usage_guidance, dict) else {},
        "final_verdict": final_verdict if isinstance(final_verdict, dict) else {},
        "positive_dna_sources": positive_dna_sources if isinstance(positive_dna_sources, list) else [],
        "skeleton_only_sources": skeleton_only_sources if isinstance(skeleton_only_sources, list) else [],
        "negative_only_sources": negative_only_sources if isinstance(negative_only_sources, list) else [],
        "blocked_opening_sources": blocked_opening_sources if isinstance(blocked_opening_sources, list) else [],
        "effective_write_policy": effective_write_policy if isinstance(effective_write_policy, str) else "",
        "effective_allow_dna": effective_allow_dna,
        "audit_notes": notes,
        "hard_stops": normalize_terms(hard_stops),
    }


def summarize_light(report: dict) -> dict:
    return {
        "total_hits": (
            len(report.get("line_hits", []))
            + len(report.get("uniform_paragraph_blocks", []))
            + len(report.get("dense_flashback_chains", []))
            + len(report.get("over_effective_dialogue_blocks", []))
            + len(report.get("opening_signature_risks", []))
        ),
        "line_hits": len(report.get("line_hits", [])),
        "uniform_paragraph_blocks": len(report.get("uniform_paragraph_blocks", [])),
        "dense_flashback_chains": len(report.get("dense_flashback_chains", [])),
        "over_effective_dialogue_blocks": len(report.get("over_effective_dialogue_blocks", [])),
        "opening_signature_risks": len(report.get("opening_signature_risks", [])),
        "opening_signal_overload": len(report.get("opening_signal_overload", [])),
        "opening_reveal_chain": len(report.get("opening_reveal_chain", [])),
        "author_stance_overreach": len(report.get("author_stance_overreach", [])),
        "opening_metrics": report.get("opening_metrics", {}),
        "line_hit_types": report.get("line_hit_types", {}),
    }


def summarize_heavy(report: dict) -> dict:
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    metrics = report.get("metrics", [])
    hotspots = report.get("hotspots", [])
    repeated_openings = report.get("repeated_openings", [])
    score = report.get("score", summary.get("score"))
    status = report.get("status", summary.get("status"))
    return {
        "score": score,
        "status": status,
        "finding_count": len(findings),
        "metric_count": len(metrics),
        "hotspot_count": len(hotspots),
        "repeated_opening_count": len(repeated_openings),
        "high_findings": [item for item in findings if item.get("severity") == "high"][:10],
        "medium_findings": [item for item in findings if item.get("severity") == "medium"][:10],
    }


def build_recommendations(light_report: dict, heavy_report: dict) -> list[str]:
    recs: list[str] = []
    opening_q = light_report.get("opening_signature_risks", [])
    if opening_q:
        recs.append("先改开头 1200 字：减少设计痕迹、整齐揭露和过平口气。")
    if light_report.get("opening_signal_overload"):
        recs.append("开头先减信号量：不要在首屏同时塞领证、孕检、定位、朋友圈、电话、医院。")
    if light_report.get("opening_reveal_chain"):
        recs.append("拆标准翻刀链：别按“等待 -> 定位 -> 社交坐实 -> 电话 -> 医院”完整喂给读者。")
    if light_report.get("author_stance_overreach"):
        recs.append("压作者站位：减少作者替人物安排见证物、围观人和整齐转折。")

    if light_report.get("over_effective_dialogue_blocks"):
        recs.append("压对白效率：让人物少把话说满，避免一问一答直达结论。")

    if light_report.get("dense_flashback_chains"):
        recs.append("拆回忆证据链：不要连续补旧账、旧恩、旧伤来证明当下伤口。")

    line_types = light_report.get("line_hit_types", {})
    if line_types.get("theme_explanation") or line_types.get("author_verdict"):
        recs.append("删作者判词和主题解释句，不要替角色把意义先说透。")
    if line_types.get("direct_mental_state") or line_types.get("standard_reaction"):
        recs.append("把空情绪和标准反应包改成动作、停顿、手上事务和现实后果。")
    if line_types.get("polished_dialogue_tag"):
        recs.append("压抛光对白标签，少写“沉默两秒”“缓缓开口”这类整理腔。")
    if line_types.get("task_list_sentence"):
        recs.append("拆事务清单句，别把生活流程写成便签目录和说明书。")

    score = heavy_report.get("score")
    if isinstance(score, (int, float)) and score >= 70:
        recs.append("优先删作者总结句和二分句壳，再看桥段链是否过于完整。")

    high_findings = heavy_report.get("high_findings", [])
    if any("binary_contrast" in item.get("rule_id", "") for item in high_findings):
        recs.append("重点删 `不是A而是B`、`不在于…而在于…` 这类二分句壳。")

    if any("romance" in item.get("rule_id", "") or "fiction" in item.get("rule_id", "") for item in high_findings):
        recs.append("感情戏里少用模板反应和标准抒情壳，改成动作或场景结果。")

    if not recs:
        recs.append("先查看高风险 finding 和 opening_metrics，再定点改最高频句壳。")
    return recs


def build_sample_grading_recommendations(guidance: dict) -> list[str]:
    if not guidance:
        return []
    recs: list[str] = []
    level = guidance.get("level")
    if level == "B类骨架样本":
        recs.append("这份参考稿是骨架样本：回修时只参考桥段承重件、后果链和场面秩序，不参考现成句法壳。")
    elif level == "C类负样本":
        recs.append("这份参考稿是负样本：回修时只参考禁写点和易假桥提醒，不把它当正向风格来源。")
    verdict = guidance.get("final_verdict", {})
    if isinstance(verdict, dict) and verdict.get("allow_dna") in ("否", "不可"):
        recs.append("当前 profile 明确禁止直接提句法 DNA，优先学动作、物件、顺序和后果链。")
    return normalize_terms(recs)


def annotate_impact_item(
    item: dict,
    *,
    source_family: str,
    focus_layer: str,
    asset_kind: str = "",
) -> dict:
    annotated = dict(item)
    annotated["source_family"] = source_family
    annotated["focus_layer"] = focus_layer
    if asset_kind:
        annotated["asset_kind"] = asset_kind
    return annotated


def apply_sample_grading_item_bias(item: dict, guidance: dict) -> dict:
    level = guidance.get("level")
    biased = dict(item)
    biased["sample_bias_rank"] = 0
    biased.setdefault("sample_bias_note", "")
    source_family = str(biased.get("source_family", ""))
    focus_layer = str(biased.get("focus_layer", ""))
    if level == "B类骨架样本":
        if source_family in {"external_block_audit", "style"} and focus_layer in {"sentence_shell", "surface_style", "dialogue_polish"}:
            biased["priority"] = "P1"
            biased["sample_bias_rank"] = -2
            biased["sample_bias_note"] = "上游是骨架样本：这类句法/抛光类问题后置，先看桥段承重件、后果链和场面秩序。"
    elif level == "C类负样本":
        if source_family in {"external_block_audit", "style"} and focus_layer not in {"bridge_structure", "consequence_chain", "external_order"}:
            biased["priority"] = "P1"
            biased["sample_bias_rank"] = -3
            biased["sample_bias_note"] = "上游是负样本：这类风格模仿问题不作为正向来源，先只处理桥段失真、秩序断裂和禁写点。"
    return biased


def impact_item_priority_tuple(item: dict) -> tuple[int, int, int]:
    priority_rank = {"P0": 2, "P1": 1}
    focus_rank = {
        "bridge_structure": 6,
        "consequence_chain": 5,
        "external_order": 4,
        "scene_order": 3,
        "character_reaction": 2,
        "dialogue_polish": 1,
        "surface_style": 0,
        "sentence_shell": -1,
    }
    return (
        int(item.get("sample_bias_rank", 0)),
        priority_rank.get(item.get("priority", "P1"), 0),
        focus_rank.get(str(item.get("focus_layer", "")), 0),
    )


def sample_lines_by_type(light_report: dict, hit_type: str, limit: int = 3) -> list[str]:
    samples = []
    for hit in light_report.get("line_hits", []):
        if hit.get("type") == hit_type:
            samples.append(f"L{hit.get('line')}: {hit.get('text')}")
        if len(samples) >= limit:
            break
    return samples


def top_hotspots(heavy_report: dict, limit: int = 5) -> list[str]:
    items = []
    for item in heavy_report.get("hotspots", [])[:limit]:
        text = item.get("text")
        count = item.get("count")
        if text:
            items.append(f"`{text}` x{count}")
    return items


def extract_proxy_features(heavy_report: dict, heavy_summary: dict) -> dict[str, float]:
    display_blocks = heavy_report.get("display_block_scores", [])
    values: list[float] = []
    hot_paragraph_total = 0
    for block in display_blocks:
        score = parse_float(block.get("risk_score"))
        if score is not None:
            values.append(score)
        hot_paragraph_total += len(block.get("hot_paragraphs", []))
    block_range = max(values) - min(values) if values else 0.0
    return {
        "our_heavy_score": float(heavy_summary.get("score") or 0.0),
        "our_display_block_range": round(block_range, 4),
        "our_hot_paragraph_total": float(hot_paragraph_total),
        "our_display_block_over25": float(sum(1 for item in values if item >= 25)),
    }


def clamp01(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def apply_linear_proxy(features: dict[str, float], model: dict) -> float | None:
    if not isinstance(model, dict):
        return None
    intercept = parse_float(model.get("intercept"))
    weights = model.get("weights", {})
    if intercept is None or not isinstance(weights, dict):
        return None
    value = intercept
    hit_count = 0
    for name, weight in weights.items():
        feat = parse_float(features.get(name))
        coeff = parse_float(weight)
        if feat is None or coeff is None:
            continue
        value += feat * coeff
        hit_count += 1
    if hit_count == 0:
        return None
    return round(clamp01(value), 4)


def normalize_internal_standard(standard: dict) -> dict:
    if not isinstance(standard, dict):
        return {}
    if standard.get("type") == "internal_audit_standard":
        return standard
    return {
        "type": "internal_audit_standard",
        "calibrated_from": "legacy_external_block_audit_alignment_summary",
        "sample_count": standard.get("sample_count"),
        "parse_failure_count": standard.get("parse_failure_count"),
        "calibration_models": standard.get("calibration_models", {}),
        "recommendation": standard.get("recommendation", {}),
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
    }


def build_internal_proxy_summary(heavy_report: dict, heavy_summary: dict, internal_standard: dict) -> dict:
    models = internal_standard.get("calibration_models", {}) if isinstance(internal_standard, dict) else {}
    weighted_model = models.get("external_block_audit_weighted_avg") or models.get(legacy_external_audit_key("weighted_avg")) or {}
    max_seg_model = models.get("external_block_audit_max_seg") or models.get(legacy_external_audit_key("max_seg")) or {}
    features = extract_proxy_features(heavy_report, heavy_summary)
    weighted_proxy = apply_linear_proxy(features, weighted_model)
    max_seg_proxy = apply_linear_proxy(features, max_seg_model)
    return {
        "features": features,
        "overall_risk": weighted_proxy,
        "max_block_risk": max_seg_proxy,
        "judgement": classify_internal_proxy(weighted_proxy, max_seg_proxy, internal_standard),
        "model_r2": {
            "weighted_avg": parse_float(weighted_model.get("r2")),
            "max_seg": parse_float(max_seg_model.get("r2")),
        },
        "tracking_recommendation": internal_standard.get("recommendation") if isinstance(internal_standard, dict) else None,
        "calibrated_from": internal_standard.get("calibrated_from"),
    }


def classify_internal_proxy(weighted_avg: float | None, max_seg: float | None, internal_standard: dict | None = None) -> dict:
    passline = (internal_standard or {}).get("passline", {})
    max_block = passline.get("max_block", {}) if isinstance(passline, dict) else {}
    overall = passline.get("overall", {}) if isinstance(passline, dict) else {}
    high_risk_gt = parse_float(max_block.get("high_risk_gt")) or 0.75
    needs_revision_gte = parse_float(max_block.get("needs_revision_gte")) or 0.60
    overall_needs_revision_gte = parse_float(overall.get("needs_revision_gte")) or 0.55
    if max_seg is None:
        return {
            "status": "unknown",
            "label": "未校准",
            "note": "缺少最高块风险分，当前只能参考内部审计，不要直接按内部过稿判定送检。",
        }
    if max_seg > high_risk_gt:
        return {
            "status": "high_risk",
            "label": "高危",
            "note": f"最高块风险分高于 {high_risk_gt:.2f}，先回修桥段块、开头块和高效对白块，不建议直接送检。",
        }
    if max_seg >= needs_revision_gte:
        return {
            "status": "needs_revision",
            "label": "建议回修",
            "note": f"最高块风险分在 {needs_revision_gte:.2f}-{high_risk_gt:.2f}，优先修最高风险大块；整体分只作辅助。",
        }
    if weighted_avg is not None and weighted_avg >= overall_needs_revision_gte:
        return {
            "status": "needs_revision",
            "label": "建议回修",
            "note": "虽然最高块风险分已压下，但整体风险分仍偏高，建议再压一轮作者腔和流程件整齐感。",
        }
    return {
        "status": "ready_for_check",
        "label": "可送检",
        "note": "最高块风险分已低于内部过稿线，可进入外部终检；仍应优先复核开头和最大风险块。",
    }


def count_term_hit(text: str, term: str) -> int:
    if not term:
        return 0
    if text.count(term) > 0:
        return text.count(term)
    normalized_text = normalize_match_text(text)
    normalized_term = normalize_match_text(term)
    if normalized_term and normalized_term in normalized_text:
        return 1
    fragments = bridge_match_fragments(term)
    if fragments and fragment_hit_score(text, fragments) >= fragment_pass_threshold(fragments):
        return 1
    return 0


def normalize_terms(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        clean = re.sub(r"\s+", " ", item.strip())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def normalize_match_text(text: str) -> str:
    if not text:
        return ""
    normalized = text
    normalized = normalized.replace("“", "").replace("”", "")
    normalized = normalized.replace("‘", "").replace("’", "")
    normalized = normalized.replace("`", "").replace('"', "")
    normalized = normalized.replace("（", "").replace("）", "")
    normalized = normalized.replace("(", "").replace(")", "")
    normalized = re.sub(r"[\s\u3000]+", "", normalized)
    normalized = re.sub(r"[，。？！；：、,.!?:;\-—_~·/\\\\|]+", "", normalized)
    return normalized


def rulebook_window_text(text: str, window: str) -> str:
    if window == "opening_1200":
        return text[:1200]
    if window == "opening_1600":
        return text[:1600]
    return text


def audit_external_rulebook(text: str, rulebook: dict) -> list[dict]:
    if not isinstance(rulebook, dict):
        return []
    items: list[dict] = []
    for section in rulebook.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("id", "")).strip()
        section_label = str(section.get("label", section_id)).strip() or section_id
        window = str(section.get("window", "full_text"))
        scoped_text = rulebook_window_text(text, window)
        for rule in section.get("rules", []):
            if not isinstance(rule, dict):
                continue
            patterns = [str(item).strip() for item in rule.get("patterns", []) if str(item).strip()]
            if not patterns:
                continue
            hits = [term for term in patterns if count_term_hit(scoped_text, term) > 0]
            min_hits = int(rule.get("min_hits", 1) or 1)
            if len(hits) < min_hits:
                continue
            items.append(
                {
                    "section_id": section_id,
                    "section_label": section_label,
                    "rule_id": str(rule.get("id", "")).strip(),
                    "title": str(rule.get("title", "")).strip(),
                    "priority": str(rule.get("priority", "P1")).strip() or "P1",
                    "focus_layer": str(rule.get("focus_layer", "scene_order")).strip() or "scene_order",
                    "window": window,
                    "pattern_total": len(patterns),
                    "hit_count": len(hits),
                    "hit_terms": hits[:8],
                    "why": str(rule.get("why", "")).strip(),
                    "fix_methods": [str(item).strip() for item in rule.get("fix_methods", []) if str(item).strip()][:6],
                }
            )
    return items


def build_rulebook_recommendations(rulebook_audit: list[dict]) -> list[str]:
    recs: list[str] = []
    for item in rulebook_audit:
        section_id = item.get("section_id")
        title = item.get("title")
        if section_id == "opening_anti_fake":
            recs.append(f"规则簿命中开头反假：{title}，先拆开头组织方式，不先润句。")
        elif section_id == "reveal_order":
            recs.append(f"规则簿命中信息漏出顺序：{title}，先拆定性顺序和旧账投喂量。")
        elif section_id == "consequence_chain":
            recs.append(f"规则簿命中后果链：{title}，先压手续流/安顿流，再补现实余波。")
    return normalize_terms(recs)


def build_rulebook_impact_items(rulebook_audit: list[dict]) -> list[dict]:
    items: list[dict] = []
    for item in rulebook_audit:
        evidence = [
            f"命中规则簿: {item.get('section_label')} / {item.get('title')}",
            "命中词: " + " / ".join(item.get("hit_terms", [])[:6]),
        ]
        items.append(
            annotate_impact_item(
                {
                    "title": f"{item.get('section_label')}：{item.get('title')}",
                    "priority": item.get("priority", "P1"),
                    "why_it_hits_audit": item.get("why") or "命中外置规则簿高风险项，说明这块成文秩序或现场组织仍偏成品化。",
                    "evidence": evidence,
                    "fix_methods": item.get("fix_methods", []),
                },
                source_family="rulebook",
                focus_layer=str(item.get("focus_layer", "scene_order")),
                asset_kind=str(item.get("section_id", "")),
            )
        )
    return items


def build_local_rulebook_flags(rulebook_audit: list[dict]) -> list[str]:
    flags: list[str] = []
    for item in rulebook_audit[:4]:
        section_label = str(item.get("section_label", "")).strip()
        title = str(item.get("title", "")).strip()
        if not section_label or not title:
            continue
        flags.append(f"{section_label}：{title}")
    return flags


def bridge_match_fragments(term: str) -> list[str]:
    quoted = re.findall(r"[`“\"「]([^`”\"」]{1,20})[`”\"」]", term)
    if quoted:
        return normalize_terms([normalize_match_text(item) for item in quoted if normalize_match_text(item)])
    cleaned = normalize_match_text(term)
    if not cleaned:
        return []
    fragments = re.split(
        r"(?:不是来|是来|上来先|先让|再让|最后|然后|再用|再把|先把|先给|再给|同步|继续把|继续|以及|或者|或是|或者是|并且|并|和)",
        cleaned,
    )
    out: list[str] = []
    for frag in fragments:
        frag = frag.strip()
        if len(frag) < 2:
            continue
        if len(frag) > 12:
            subparts = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,8}", frag)
            out.extend(subparts)
            continue
        out.append(frag)
    return normalize_terms([item for item in out if len(item) >= 2])


def fragment_hit_score(text: str, fragments: list[str]) -> int:
    normalized_text = normalize_match_text(text)
    score = 0
    for fragment in fragments:
        if fragment and fragment in normalized_text:
            score += 1
    return score


def fragment_pass_threshold(fragments: list[str]) -> int:
    if not fragments:
        return 999
    if len(fragments) == 1:
        return 1
    if len(fragments) == 2:
        return 1
    return 2


def term_weight(term: str) -> float:
    clean = re.sub(r"\s+", "", term.strip())
    if not clean:
        return 0.0
    length = len(clean)
    if length <= 2:
        return 0.7
    if length == 3:
        return 1.0
    if length == 4:
        return 1.35
    if length == 5:
        return 1.65
    return 2.0


def get_style_assets(profile: dict) -> dict[str, list[str]]:
    assets = profile.get("style_assets", {}) if isinstance(profile, dict) else {}
    if not isinstance(assets, dict):
        return {}
    return {
        key: normalize_terms(value)
        for key, value in assets.items()
        if isinstance(key, str) and isinstance(value, list)
    }


def sample_excerpt(text: str, term: str, radius: int = 16) -> str:
    pos = first_hit_position(text, term)
    if pos < 0:
        return term
    start = max(0, pos - radius)
    end = min(len(text), pos + len(term) + radius)
    return text[start:end].replace("\n", " ")


def collect_term_hits(text: str, terms: list[str], limit: int = 12) -> list[str]:
    hits: list[str] = []
    for term in normalize_terms(terms):
        if term and term in text:
            hits.append(term)
        if len(hits) >= limit:
            break
    return hits


def first_hit_position(text: str, term: str) -> int:
    if not term:
        return -1
    pos = text.find(term)
    if pos >= 0:
        return pos
    fragments = sorted(bridge_match_fragments(term), key=len, reverse=True)
    for fragment in fragments:
        raw_pos = text.find(fragment)
        if raw_pos >= 0:
            return raw_pos
    return -1


def local_bridge_window(text: str, positions: list[int], radius: int = 900) -> str:
    usable = sorted(pos for pos in positions if pos >= 0)
    if not usable:
        return text
    start = max(0, usable[0] - radius)
    end = min(len(text), usable[-1] + radius)
    return text[start:end]


def opening_window_text(text: str) -> str:
    if not text:
        return ""
    window = max(260, min(len(text), int(len(text) * 0.35)))
    return text[:window]


def sequence_audit(text: str, terms: list[str]) -> dict:
    ordered_hits: list[dict] = []
    missing: list[str] = []
    for idx, term in enumerate(normalize_terms(terms), start=1):
        pos = first_hit_position(text, term)
        if pos < 0:
            missing.append(term)
            continue
        ordered_hits.append({"index": idx, "term": term, "position": pos})

    out_of_order: list[str] = []
    if len(ordered_hits) >= 2:
        last_pos = ordered_hits[0]["position"]
        last_term = ordered_hits[0]["term"]
        for item in ordered_hits[1:]:
            if item["position"] < last_pos:
                out_of_order.append(f"{item['term']} 早于 {last_term}")
            else:
                last_pos = item["position"]
                last_term = item["term"]

    return {
        "hit_terms": [item["term"] for item in ordered_hits],
        "missing_terms": missing[:10],
        "out_of_order": out_of_order[:10],
    }


def split_paragraphs(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def split_dialogue_segments(text: str) -> list[str]:
    return [item.strip() for item in re.findall(r'"([^"\n]{1,80})"', text)]


def split_sentences_with_spans(text: str, base_offset: int = 0) -> list[dict]:
    parts: list[dict] = []
    if not text:
        return parts

    sentence_endings = "。！？!?；;"
    start = 0
    idx = 0
    length = len(text)
    while idx < length:
        ch = text[idx]
        if ch in sentence_endings:
            end = idx + 1
            while end < length and text[end] in "”』」\"' ":
                end += 1
            chunk = text[start:end].strip()
            if chunk:
                local_start = text.find(chunk, start, end)
                if local_start < 0:
                    local_start = start
                parts.append(
                    {
                        "text": chunk,
                        "start_char": base_offset + local_start,
                        "end_char": base_offset + local_start + len(chunk),
                    }
                )
            start = end
            idx = end
            continue
        idx += 1

    tail = text[start:].strip()
    if tail:
        local_start = text.find(tail, start)
        if local_start < 0:
            local_start = start
        parts.append(
            {
                "text": tail,
                "start_char": base_offset + local_start,
                "end_char": base_offset + local_start + len(tail),
            }
        )
    return parts


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def risk_level(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    if score >= 35:
        return "low"
    return "safe"


def segment_priority_tuple(item: dict) -> tuple[int, int, float, int]:
    has_bridge = 1 if item.get("bridge_flags") else 0
    has_consequence = 1 if item.get("consequence_flags") else 0
    has_style_core = 1 if item.get("style_flags") else 0
    return (
        has_bridge,
        has_consequence,
        has_style_core,
        float(item.get("risk_score", 0)),
    )


def dynamic_segment_priority_tuple(item: dict) -> tuple[int, int, float, int]:
    has_bridge = 1 if item.get("bridge_flags") else 0
    has_consequence = 1 if item.get("consequence_flags") else 0
    has_style_core = 1 if item.get("style_flags") else 0
    return (
        has_bridge,
        has_consequence,
        has_style_core,
        float(item.get("risk_score", 0)),
    )


def paragraph_priority_tuple(item: dict) -> tuple[int, int, int, float]:
    flags = item.get("flags", []) or []
    short_only = flags and set(flags) <= {"短段对白密"}
    has_scene_core = 1 if any(flag in flags for flag in ("单场戏功能过多", "高效对白块", "开头承压", "多资产挤压", "说明句偏强")) else 0
    has_short_dense = 1 if "短段对白密" in flags else 0
    return (
        has_scene_core,
        0 if short_only else 1,
        0 if has_short_dense and not has_scene_core else 1,
        float(item.get("risk_score", 0)),
    )


def build_paragraph_entries(text: str) -> list[dict]:
    entries: list[dict] = []
    cursor = 0
    for idx, para in enumerate(split_paragraphs(text), start=1):
        pos = text.find(para, cursor)
        if pos < 0:
            pos = cursor
        start = pos
        end = pos + len(para)
        cursor = end
        entries.append(
            {
                "paragraph_index": idx,
                "start_char": start,
                "end_char": end,
                "char_count": len(para),
                "text": para,
            }
        )
    return entries


def build_display_blocks(paragraphs: list[dict], target_blocks: int = 7) -> list[dict]:
    if not paragraphs:
        return []

    total_chars = sum(item["char_count"] for item in paragraphs)
    target_blocks = max(5, min(8, target_blocks))
    target_chars = max(900, int(total_chars / target_blocks))

    blocks: list[dict] = []
    bucket: list[dict] = []
    bucket_chars = 0

    def flush_bucket() -> None:
        nonlocal bucket, bucket_chars
        if not bucket:
            return
        blocks.append(
            {
                "block_index": len(blocks) + 1,
                "paragraph_start": bucket[0]["paragraph_index"],
                "paragraph_end": bucket[-1]["paragraph_index"],
                "start_char": bucket[0]["start_char"],
                "end_char": bucket[-1]["end_char"],
                "char_count": sum(item["char_count"] for item in bucket),
            }
        )
        bucket = []
        bucket_chars = 0

    for para in paragraphs:
        if bucket and bucket_chars >= target_chars:
            flush_bucket()
        bucket.append(para)
        bucket_chars += para["char_count"]

    if bucket:
        flush_bucket()

    if len(blocks) > 8:
        merged: list[dict] = []
        carry: dict | None = None
        for block in blocks:
            if carry is None:
                carry = dict(block)
                continue
            if len(blocks) - len(merged) > 8 or carry["char_count"] < 900:
                carry["paragraph_end"] = block["paragraph_end"]
                carry["end_char"] = block["end_char"]
                carry["char_count"] += block["char_count"]
            else:
                merged.append(carry)
                carry = dict(block)
        if carry is not None:
            merged.append(carry)
        blocks = merged

    for idx, block in enumerate(blocks, start=1):
        block["block_index"] = idx
    return blocks


def build_micro_segment_entries(
    source_text: str,
    paragraphs: list[dict],
    target_chars: int = MICRO_SEGMENT_TARGET_CHARS,
    min_chars: int = MICRO_SEGMENT_MIN_CHARS,
    max_chars: int = MICRO_SEGMENT_MAX_CHARS,
) -> list[dict]:
    if not paragraphs:
        return []

    sentence_units: list[dict] = []
    for para in paragraphs:
        para_sentences = split_sentences_with_spans(para["text"], para["start_char"])
        if not para_sentences:
            para_sentences = [
                {
                    "text": para["text"],
                    "start_char": para["start_char"],
                    "end_char": para["end_char"],
                }
            ]
        for unit in para_sentences:
            sentence_units.append(
                {
                    **unit,
                    "paragraph_index": para["paragraph_index"],
                }
            )

    segments: list[dict] = []
    bucket: list[dict] = []
    bucket_chars = 0

    def flush_bucket() -> None:
        nonlocal bucket, bucket_chars
        if not bucket:
            return
        para_indexes = [item["paragraph_index"] for item in bucket]
        start_char = bucket[0]["start_char"]
        end_char = bucket[-1]["end_char"]
        text = source_text[start_char:end_char].strip()
        if not text:
            text = "".join(item["text"] for item in bucket)
        segments.append(
            {
                "segment_index": len(segments) + 1,
                "paragraph_start": min(para_indexes),
                "paragraph_end": max(para_indexes),
                "paragraph_indexes": sorted(set(para_indexes)),
                "start_char": start_char,
                "end_char": end_char,
                "char_count": len(text),
                "text": text,
            }
        )
        bucket = []
        bucket_chars = 0

    for unit in sentence_units:
        unit_len = len(unit["text"])
        projected = bucket_chars + unit_len
        if bucket and bucket_chars >= min_chars and (
            projected > target_chars or bucket_chars >= max_chars
        ):
            flush_bucket()
        bucket.append(unit)
        bucket_chars += unit_len

    if bucket:
        if segments and bucket_chars < min_chars:
            prev = segments.pop()
            start_char = prev["start_char"]
            end_char = bucket[-1]["end_char"]
            para_indexes = sorted(set(prev.get("paragraph_indexes", []) + [item["paragraph_index"] for item in bucket]))
            text = source_text[start_char:end_char].strip()
            segments.append(
                {
                    "segment_index": prev["segment_index"],
                    "paragraph_start": min(para_indexes),
                    "paragraph_end": max(para_indexes),
                    "paragraph_indexes": para_indexes,
                    "start_char": start_char,
                    "end_char": end_char,
                    "char_count": len(text),
                    "text": text,
                }
            )
        else:
            flush_bucket()
    return segments


def build_coarse_segment_entries(
    source_text: str,
    paragraphs: list[dict],
    target_chars: int = COARSE_SEGMENT_TARGET_CHARS,
    min_chars: int = COARSE_SEGMENT_MIN_CHARS,
    max_chars: int = COARSE_SEGMENT_MAX_CHARS,
) -> list[dict]:
    if not paragraphs:
        return []

    segments: list[dict] = []
    bucket: list[dict] = []
    bucket_chars = 0

    def flush_bucket() -> None:
        nonlocal bucket, bucket_chars
        if not bucket:
            return
        start_char = bucket[0]["start_char"]
        end_char = bucket[-1]["end_char"]
        text = source_text[start_char:end_char].strip()
        segments.append(
            {
                "segment_index": len(segments) + 1,
                "paragraph_start": bucket[0]["paragraph_index"],
                "paragraph_end": bucket[-1]["paragraph_index"],
                "paragraph_indexes": [item["paragraph_index"] for item in bucket],
                "start_char": start_char,
                "end_char": end_char,
                "char_count": len(text),
                "text": text,
            }
        )
        bucket = []
        bucket_chars = 0

    for para in paragraphs:
        projected = bucket_chars + para["char_count"]
        if bucket and bucket_chars >= min_chars and (
            projected > target_chars or bucket_chars >= max_chars
        ):
            flush_bucket()
        bucket.append(para)
        bucket_chars += para["char_count"]

    if bucket:
        if segments and bucket_chars < min_chars:
            prev = segments.pop()
            start_char = prev["start_char"]
            end_char = bucket[-1]["end_char"]
            para_indexes = prev["paragraph_indexes"] + [item["paragraph_index"] for item in bucket]
            text = source_text[start_char:end_char].strip()
            segments.append(
                {
                    "segment_index": prev["segment_index"],
                    "paragraph_start": min(para_indexes),
                    "paragraph_end": max(para_indexes),
                    "paragraph_indexes": para_indexes,
                    "start_char": start_char,
                    "end_char": end_char,
                    "char_count": len(text),
                    "text": text,
                }
            )
        else:
            flush_bucket()
    return segments


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def bridge_name_from_flag(flag: str) -> str:
    if not isinstance(flag, str):
        return ""
    if "：" not in flag:
        return ""
    return flag.split("：", 1)[1].strip()


def dominant_bridge_name(flags: list[str]) -> str:
    for flag in flags or []:
        name = bridge_name_from_flag(flag)
        if name:
            return name
    return ""


def build_paragraph_issue_signature(item: dict) -> set[str]:
    signature: set[str] = set()
    for flag in item.get("flags", []) or []:
        signature.add(f"para::{flag}")
    for flag in item.get("style_flags", []) or []:
        signature.add(f"style::{flag}")
    for flag in item.get("consequence_flags", []) or []:
        signature.add(f"cons::{flag}")
    for flag in item.get("bridge_flags", []) or []:
        name = bridge_name_from_flag(flag)
        if name:
            signature.add(f"bridge::{name}")
        signature.add(f"bridgeflag::{flag.split('：', 1)[0]}")
    for flag in item.get("rulebook_flags", []) or []:
        signature.add(f"rule::{flag}")
    return signature


def should_merge_paragraph_groups(current: dict, nxt: dict, gap: int = 1) -> bool:
    current_sig = current.get("issue_signature", set())
    next_sig = nxt.get("issue_signature", set())
    overlap = bool(current_sig & next_sig)
    current_score = float(current.get("risk_score", 0))
    next_score = float(nxt.get("risk_score", 0))
    current_opening = current.get("paragraph_index", 0) <= 6
    next_opening = nxt.get("paragraph_index", 0) <= 6

    if gap <= 2 and overlap and current_score >= 36 and next_score >= 36:
        return True
    if gap <= 2 and overlap and (current_score >= 45 or next_score >= 45):
        return True
    if gap <= 2 and current_opening and next_opening and current_score >= 35 and next_score >= 35:
        return True
    if gap <= 2 and current_score >= 55 and next_score >= 40:
        return True
    if gap <= 2 and next_score >= 55 and current_score >= 40:
        return True
    return False


def build_dynamic_segment_scores(
    paragraphs: list[dict],
    paragraph_scores: list[dict],
    paragraph_to_segment: dict[int, dict],
) -> list[dict]:
    if not paragraph_scores:
        return []

    para_meta = {item["paragraph_index"]: item for item in paragraphs}
    enriched: list[dict] = []
    for item in paragraph_scores:
        seg = paragraph_to_segment.get(item["paragraph_index"]) or {}
        enriched.append(
            {
                **item,
                "raw_segment_index": seg.get("segment_index"),
                "style_flags": seg.get("style_flags", []),
                "bridge_flags": seg.get("bridge_flags", []),
                "consequence_flags": seg.get("consequence_flags", []),
                "rulebook_flags": seg.get("rulebook_flags", []),
                "issue_signature": build_paragraph_issue_signature(
                    {
                        "flags": item.get("flags", []),
                        "style_flags": seg.get("style_flags", []),
                        "bridge_flags": seg.get("bridge_flags", []),
                        "consequence_flags": seg.get("consequence_flags", []),
                        "rulebook_flags": seg.get("rulebook_flags", []),
                    }
                ),
                "text": para_meta[item["paragraph_index"]]["text"],
                "start_char": para_meta[item["paragraph_index"]]["start_char"],
                "end_char": para_meta[item["paragraph_index"]]["end_char"],
                "char_count": para_meta[item["paragraph_index"]]["char_count"],
            }
        )

    risky = [item for item in enriched if item["risk_score"] >= 35]
    if risky and len(enriched) >= 18:
        ratio = len(risky) / max(len(enriched), 1)
        avg_score = sum(item["risk_score"] for item in risky) / len(risky)
        if ratio >= 0.85 and avg_score >= 48:
            text = "\n\n".join(item["text"] for item in enriched)
            return [
                {
                    "segment_index": 1,
                    "paragraph_start": enriched[0]["paragraph_index"],
                    "paragraph_end": enriched[-1]["paragraph_index"],
                    "start_char": enriched[0]["start_char"],
                    "end_char": enriched[-1]["end_char"],
                    "char_count": len(text),
                    "risk_score": round(avg_score, 2),
                    "risk_ratio": round(avg_score / 100.0, 4),
                    "risk_level": risk_level(avg_score),
                    "style_flags": dedupe_keep_order([f for item in enriched for f in item.get("style_flags", [])])[:6],
                    "bridge_flags": dedupe_keep_order([f for item in enriched for f in item.get("bridge_flags", [])])[:6],
                    "consequence_flags": dedupe_keep_order([f for item in enriched for f in item.get("consequence_flags", [])])[:4],
                    "rulebook_flags": dedupe_keep_order([f for item in enriched for f in item.get("rulebook_flags", [])])[:6],
                    "paragraph_flags": dedupe_keep_order([f for item in enriched for f in item.get("flags", [])])[:8],
                    "excerpt": text[:180].replace("\n", " "),
                }
            ]

    risky_items = [item for item in enriched if item["risk_score"] >= 35]
    merged: list[list[dict]] = []
    current_group: list[dict] = []
    for item in risky_items:
        if not current_group:
            current_group = [item]
            continue
        prev = current_group[-1]
        gap = item["paragraph_index"] - prev["paragraph_index"]
        same_raw_segment = prev.get("raw_segment_index") == item.get("raw_segment_index")
        same_bridge = dominant_bridge_name(prev.get("bridge_flags", [])) and dominant_bridge_name(prev.get("bridge_flags", [])) == dominant_bridge_name(item.get("bridge_flags", []))
        if same_raw_segment and same_bridge and gap <= 12:
            current_group.append(item)
        elif 1 <= gap <= 2 and should_merge_paragraph_groups(prev, item, gap=gap):
            current_group.append(item)
        else:
            merged.append(current_group)
            current_group = [item]
    if current_group:
        merged.append(current_group)

    results: list[dict] = []
    for idx, group in enumerate(merged, start=1):
        para_start = group[0]["paragraph_index"]
        para_end = group[-1]["paragraph_index"]
        full_range = [para_meta[i] for i in range(para_start, para_end + 1) if i in para_meta]
        text = "\n\n".join(item["text"] for item in full_range)
        avg_score = sum(item["risk_score"] for item in group) / len(group)
        max_score = max(item["risk_score"] for item in group)
        group_score = round((avg_score * 0.55) + (max_score * 0.45), 2)
        results.append(
            {
                "segment_index": idx,
                "paragraph_start": para_start,
                "paragraph_end": para_end,
                "start_char": full_range[0]["start_char"],
                "end_char": full_range[-1]["end_char"],
                "char_count": len(text),
                "risk_score": group_score,
                "risk_ratio": round(group_score / 100.0, 4),
                "risk_level": risk_level(group_score),
                "style_flags": dedupe_keep_order([f for item in group for f in item.get("style_flags", [])])[:6],
                "bridge_flags": dedupe_keep_order([f for item in group for f in item.get("bridge_flags", [])])[:6],
                "consequence_flags": dedupe_keep_order([f for item in group for f in item.get("consequence_flags", [])])[:4],
                "rulebook_flags": dedupe_keep_order([f for item in group for f in item.get("rulebook_flags", [])])[:6],
                "paragraph_flags": dedupe_keep_order([f for item in group for f in item.get("flags", [])])[:8],
                "excerpt": text[:180].replace("\n", " "),
            }
        )
    return results


def compute_coarse_segment_score(
    segment: dict,
    paragraph_scores: list[dict],
    raw_segment_scores: list[dict],
) -> dict:
    para_items = [
        item for item in paragraph_scores
        if segment["paragraph_start"] <= item["paragraph_index"] <= segment["paragraph_end"]
    ]
    micro_items = [
        item for item in raw_segment_scores
        if not (
            item["paragraph_end"] < segment["paragraph_start"]
            or item["paragraph_start"] > segment["paragraph_end"]
        )
    ]
    para_scores = [float(item.get("risk_score", 0)) for item in para_items]
    micro_scores = [float(item.get("risk_score", 0)) for item in micro_items]
    all_scores = para_scores + micro_scores
    if all_scores:
        avg_score = sum(all_scores) / len(all_scores)
        top_scores = sorted(all_scores, reverse=True)[:5]
        top_avg = sum(top_scores) / len(top_scores)
        density35 = sum(1 for value in all_scores if value >= 35) / len(all_scores)
        density25 = sum(1 for value in all_scores if value >= 25) / len(all_scores)
        score = clamp(avg_score * 0.4 + top_avg * 0.35 + density35 * 18 + density25 * 7)
    else:
        avg_score = 0.0
        density35 = 0.0
        density25 = 0.0
        score = 0.0
    flags = dedupe_keep_order(
        [flag for item in para_items for flag in item.get("flags", [])]
        + [flag for item in micro_items for flag in item.get("style_flags", [])]
        + [flag for item in micro_items for flag in item.get("bridge_flags", [])]
        + [flag for item in micro_items for flag in item.get("consequence_flags", [])]
        + [flag for item in micro_items for flag in item.get("rulebook_flags", [])]
    )
    return {
        **{k: segment[k] for k in ("segment_index", "paragraph_start", "paragraph_end", "start_char", "end_char", "char_count")},
        "risk_score": round(score, 2),
        "risk_ratio": round(score / 100.0, 4),
        "risk_level": risk_level(score),
        "avg_score": round(avg_score, 2),
        "density_35": round(density35, 4),
        "density_25": round(density25, 4),
        "flags": flags[:10],
        "excerpt": segment["text"][:180].replace("\n", " "),
    }


def build_global_risk_shape(
    source_text: str,
    heavy_summary: dict,
    coarse_segment_scores: list[dict],
    display_block_scores: list[dict],
    paragraph_scores: list[dict],
) -> dict:
    text_char_count = len(source_text.replace("\n", ""))
    heavy_score = float(heavy_summary.get("score") or 0)
    coarse_scores = [float(item.get("risk_score", 0)) for item in coarse_segment_scores]
    block_scores = [float(item.get("risk_score", 0)) for item in display_block_scores]
    paragraph_high = [item for item in paragraph_scores if float(item.get("risk_score", 0)) >= 35]
    paragraph_total = max(len(paragraph_scores), 1)
    paragraph_high_ratio = len(paragraph_high) / paragraph_total
    coarse_cv = coeff_var(coarse_scores) if len(coarse_scores) >= 2 else 0.0
    block_cv = coeff_var(block_scores) if len(block_scores) >= 2 else 0.0
    coarse_min = min(coarse_scores) if coarse_scores else 0.0
    coarse_max = max(coarse_scores) if coarse_scores else 0.0

    is_single_global_block = (
        text_char_count >= 6000
        and heavy_score >= 60
        and len(coarse_segment_scores) >= 2
        and coarse_min >= 18
        and coarse_cv <= 0.22
        and block_cv <= 0.16
    )
    is_coarse_multi_block = (
        not is_single_global_block
        and text_char_count >= 4500
        and heavy_score >= 48
        and len(coarse_segment_scores) >= 2
        and coarse_max >= 28
    )

    if is_single_global_block:
        avg_score = sum(coarse_scores) / len(coarse_scores)
        global_blocks = [
            {
                "block_index": 1,
                "paragraph_start": coarse_segment_scores[0]["paragraph_start"],
                "paragraph_end": coarse_segment_scores[-1]["paragraph_end"],
                "start_char": coarse_segment_scores[0]["start_char"],
                "end_char": coarse_segment_scores[-1]["end_char"],
                "char_count": text_char_count,
                "risk_score": round(avg_score, 2),
                "risk_ratio": round(avg_score / 100.0, 4),
                "risk_level": risk_level(avg_score),
                "flags": dedupe_keep_order(
                    [flag for item in coarse_segment_scores for flag in item.get("flags", [])]
                )[:12],
                "excerpt": source_text[:220].replace("\n", " "),
            }
        ]
        shape = "single_global_block"
    elif is_coarse_multi_block:
        global_blocks = coarse_segment_scores
        shape = "coarse_blocks"
    else:
        global_blocks = []
        shape = "local_blocks"

    return {
        "shape": shape,
        "text_char_count": text_char_count,
        "heavy_score": heavy_score,
        "coarse_segment_count": len(coarse_segment_scores),
        "coarse_score_cv": round(coarse_cv, 4),
        "display_block_cv": round(block_cv, 4),
        "paragraph_high_ratio": round(paragraph_high_ratio, 4),
        "coarse_min_score": round(coarse_min, 2),
        "coarse_max_score": round(coarse_max, 2),
        "global_blocks": global_blocks,
    }


def bridge_rule_audit(text: str, profile: dict, top_n: int = 5) -> list[dict]:
    bridge_rules = profile.get("bridge_rules", [])
    if not isinstance(bridge_rules, list):
        return []

    ranked: list[dict] = []
    for item in bridge_rules:
        bridge = str(item.get("bridge", "")).strip()
        opening_pattern = [str(x).strip() for x in item.get("opening_pattern", []) if str(x).strip()]
        must_keep = [str(x).strip() for x in item.get("must_keep", []) if str(x).strip()]
        must_avoid = [str(x).strip() for x in item.get("must_avoid", []) if str(x).strip()]
        fake_signals = [str(x).strip() for x in item.get("fake_signals", []) if str(x).strip()]
        recommended_sequence = [str(x).strip() for x in item.get("recommended_sequence", []) if str(x).strip()]
        why_order_matters = [str(x).strip() for x in item.get("why_order_matters", []) if str(x).strip()]
        why_passes = [str(x).strip() for x in item.get("why_original_passes", []) if str(x).strip()]

        anchor_terms = must_keep + opening_pattern + recommended_sequence
        anchor_positions = [first_hit_position(text, term) for term in anchor_terms]
        bridge_window = local_bridge_window(text, anchor_positions)

        opening_hits = [term for term in opening_pattern if count_term_hit(bridge_window, term) > 0]
        keep_hits = [term for term in must_keep if count_term_hit(bridge_window, term) > 0 or count_term_hit(text, term) > 0]
        avoid_hits = [term for term in must_avoid if count_term_hit(bridge_window, term) > 0]
        fake_hits = [term for term in fake_signals if count_term_hit(bridge_window, term) > 0]
        sequence_info = sequence_audit(bridge_window, recommended_sequence)
        if not keep_hits and not avoid_hits and not fake_hits and not opening_hits and not sequence_info["hit_terms"]:
            continue

        keep_ratio = round(len(keep_hits) / max(len(must_keep), 1), 4)
        opening_ratio = round(len(opening_hits) / max(len(opening_pattern), 1), 4) if opening_pattern else 0.0
        sequence_ratio = round(len(sequence_info["hit_terms"]) / max(len(recommended_sequence), 1), 4) if recommended_sequence else 0.0
        weighted_keep = round(sum(term_weight(term) for term in keep_hits), 4)
        weighted_avoid = round(sum(term_weight(term) for term in avoid_hits), 4)
        weighted_fake = round(sum(term_weight(term) for term in fake_hits), 4)
        weighted_missing = round(sum(term_weight(term) for term in must_keep if term not in keep_hits), 4)
        opening_missing = [term for term in opening_pattern if term not in opening_hits][:10]
        sequence_missing = sequence_info["missing_terms"][:10]
        sequence_out_of_order = sequence_info["out_of_order"][:10]
        sequence_penalty = len(sequence_out_of_order) * 1.6 + len(sequence_missing) * 0.15
        score = round(
            weighted_keep * 2.2
            + keep_ratio * 3.5
            + opening_ratio * 1.8
            + sequence_ratio * 1.5
            - weighted_avoid * 1.2
            - weighted_fake * 1.1
            - weighted_missing * 0.18
            - sequence_penalty,
            4,
        )
        ranked.append(
            {
                "bridge": bridge,
                "opening_pattern_total": len(opening_pattern),
                "opening_pattern_hit": opening_hits,
                "opening_pattern_missing": opening_missing,
                "must_keep_total": len(must_keep),
                "must_keep_hit": keep_hits,
                "must_keep_missing": [term for term in must_keep if term not in keep_hits][:10],
                "must_avoid_hit": avoid_hits[:10],
                "fake_signal_hit": fake_hits[:10],
                "recommended_sequence_total": len(recommended_sequence),
                "recommended_sequence_hit": sequence_info["hit_terms"][:10],
                "recommended_sequence_missing": sequence_missing,
                "recommended_sequence_out_of_order": sequence_out_of_order,
                "why_order_matters": why_order_matters[:6],
                "why_original_passes": why_passes[:6],
                "opening_ratio": opening_ratio,
                "keep_ratio": keep_ratio,
                "sequence_ratio": sequence_ratio,
                "weighted_keep": weighted_keep,
                "weighted_avoid": weighted_avoid,
                "weighted_fake": weighted_fake,
                "_score": score,
            }
        )

    ranked.sort(
        key=lambda x: (
            x["_score"],
            x["weighted_keep"],
            x["keep_ratio"],
            len(x["must_keep_hit"]),
        ),
        reverse=True,
    )
    for item in ranked:
        item.pop("_score", None)
    return ranked[:top_n]


def consequence_chain_audit(text: str, profile: dict) -> dict:
    assets = profile.get("scene_assets", {}) if isinstance(profile, dict) else {}
    chain_terms = assets.get("consequence_chain", []) if isinstance(assets, dict) else []
    external_terms = assets.get("external_order", []) if isinstance(assets, dict) else []
    public_terms = assets.get("public_explosion", []) if isinstance(assets, dict) else []

    consequence_hits = [term for term in chain_terms if isinstance(term, str) and term and term in text][:20]
    external_hits = [term for term in external_terms if isinstance(term, str) and term and term in text][:12]
    public_hits = [term for term in public_terms if isinstance(term, str) and term and term in text][:12]

    return {
        "consequence_hits": consequence_hits,
        "external_order_hits": external_hits,
        "public_explosion_hits": public_hits,
        "has_public_scene": bool(public_hits),
        "has_external_order": bool(external_hits),
        "has_consequence_chain": len(consequence_hits) >= 2,
    }


def build_bridge_recommendations(bridge_audit: list[dict]) -> list[str]:
    recs: list[str] = []
    if not bridge_audit:
        return recs
    top = bridge_audit[0]
    if top.get("opening_pattern_missing"):
        recs.append(
            f"同桥起手件不足：`{top['bridge']}` 开场先补 "
            + " / ".join(top["opening_pattern_missing"][:4])
        )
    if top.get("must_keep_missing"):
        recs.append(
            f"同桥承重件补全：优先处理 `{top['bridge']}`，补缺的 must_keep，如 "
            + " / ".join(top["must_keep_missing"][:4])
        )
    if top.get("recommended_sequence_out_of_order"):
        recs.append(
            f"同桥顺序漂移：`{top['bridge']}` 当前顺序已乱，如 "
            + " / ".join(top["recommended_sequence_out_of_order"][:3])
        )
    elif top.get("recommended_sequence_missing"):
        recs.append(
            f"同桥顺序件缺失：`{top['bridge']}` 还缺 "
            + " / ".join(top["recommended_sequence_missing"][:4])
        )
    if top.get("must_avoid_hit"):
        recs.append(
            f"同桥禁写点回退：`{top['bridge']}` 已踩到 "
            + " / ".join(top["must_avoid_hit"][:4])
        )
    if top.get("fake_signal_hit"):
        recs.append(
            f"同桥易假点命中：`{top['bridge']}` 已写出 "
            + " / ".join(top["fake_signal_hit"][:4])
        )
    if top.get("why_original_passes"):
        recs.append(
            f"按原文过检原因回修：`{top['bridge']}` 先对照 "
            + " / ".join(top["why_original_passes"][:3])
        )
    if top.get("why_order_matters"):
        recs.append(
            f"同桥顺序不能乱：`{top['bridge']}` 重点记住 "
            + " / ".join(top["why_order_matters"][:3])
        )
    return recs


def audit_profile_asset_coverage(profile: dict, bridge_audit: list[dict], consequence_audit: dict, style_audits: dict) -> dict:
    bridge_rules = profile.get("bridge_rules", []) if isinstance(profile, dict) else []
    scene_assets = profile.get("scene_assets", {}) if isinstance(profile.get("scene_assets"), dict) else {}
    style_assets = get_style_assets(profile)
    story_guardrails = profile.get("story_guardrails", {}) if isinstance(profile.get("story_guardrails"), dict) else {}
    scene_nonempty = {key: value for key, value in scene_assets.items() if isinstance(value, list) and value}
    style_nonempty = {key: value for key, value in style_assets.items() if isinstance(value, list) and value}

    missing_scene_keys = [
        key for key in ("public_explosion", "external_order", "consequence_chain")
        if not scene_nonempty.get(key)
    ]
    missing_style_keys = [
        key for key in ("micro_actions", "character_bias", "dialogue_bridges", "rotten_relationship")
        if not style_nonempty.get(key)
    ]
    missing_guardrail_keys = []
    consequence_guard = story_guardrails.get("consequence_structure", {}) if isinstance(story_guardrails, dict) else {}
    if not (isinstance(consequence_guard, dict) and consequence_guard.get("pre_evidence_reality_consequences")):
        missing_guardrail_keys.append("pre_evidence_reality_consequences")
    if not (isinstance(consequence_guard, dict) and consequence_guard.get("tail_entry_owner")):
        missing_guardrail_keys.append("tail_entry_owner")
    face_guard = story_guardrails.get("character_face_split", {}) if isinstance(story_guardrails, dict) else {}
    if not (isinstance(face_guard, dict) and face_guard.get("different_face_evidence")):
        missing_guardrail_keys.append("different_face_evidence")

    warnings: list[str] = []
    if not bridge_rules:
        warnings.append("profile 缺少 bridge_rules，当前无法判断同桥承重件是否命中。")
    elif not bridge_audit:
        warnings.append("profile 有 bridge_rules，但正文没有命中任何同桥规则；这次前排只能先暴露句法/场面层问题。")
    if missing_scene_keys:
        warnings.append("scene_assets 覆盖不完整：" + " / ".join(missing_scene_keys))
    if missing_style_keys:
        warnings.append("style_assets 关键层缺失：" + " / ".join(missing_style_keys))
    if missing_guardrail_keys:
        warnings.append("story_guardrails 缺失：" + " / ".join(missing_guardrail_keys))

    return {
        "bridge_rule_count": len(bridge_rules) if isinstance(bridge_rules, list) else 0,
        "bridge_matched_count": len(bridge_audit or []),
        "has_bridge_rules": bool(bridge_rules),
        "scene_asset_counts": {key: len(value) for key, value in scene_nonempty.items()},
        "style_asset_counts": {key: len(value) for key, value in style_nonempty.items()},
        "missing_scene_asset_keys": missing_scene_keys,
        "missing_style_asset_keys": missing_style_keys,
        "missing_story_guardrail_keys": missing_guardrail_keys,
        "has_public_scene": bool(consequence_audit.get("has_public_scene")) if isinstance(consequence_audit, dict) else False,
        "has_external_order": bool(consequence_audit.get("has_external_order")) if isinstance(consequence_audit, dict) else False,
        "has_consequence_chain": bool(consequence_audit.get("has_consequence_chain")) if isinstance(consequence_audit, dict) else False,
        "warnings": warnings,
    }


def build_asset_coverage_impact_items(asset_coverage: dict, guidance: dict) -> list[dict]:
    items: list[dict] = []
    if not asset_coverage:
        return items
    level = str((guidance or {}).get("level", ""))
    if level in {"B类骨架样本", "C类负样本"} and asset_coverage.get("has_bridge_rules") and not asset_coverage.get("bridge_matched_count"):
        items.append(
            annotate_impact_item(
                {
                    "title": "桥段资产未命中，当前不要先修句法壳",
                    "priority": "P0",
                    "why_it_hits_audit": "上游样本本来就不适合优先学句法；如果正文又没有命中已拆出的桥段承重件，继续压表面句子只会越修越假。",
                    "evidence": [
                        f"上游样本等级: {level}",
                        f"bridge_rules: {asset_coverage.get('bridge_rule_count', 0)}",
                        "正文命中同桥规则: 0",
                    ],
                    "fix_methods": [
                        "先回到已拆出的桥段规则，确认这篇正文到底用了哪条桥，或者是否根本换桥了。",
                        "如果换桥了，先补新桥的起手件、承重件、顺序件，再谈对白和句壳。",
                        "如果没换桥，就按同桥承重件重建现场秩序，不要先修抛光层。",
                    ],
                },
                source_family="asset_coverage",
                focus_layer="bridge_structure",
                asset_kind="bridge_rules",
            )
        )
    if asset_coverage.get("missing_scene_asset_keys"):
        items.append(
            annotate_impact_item(
                {
                    "title": "profile 的后果链/秩序资产不完整",
                    "priority": "P0",
                    "why_it_hits_audit": "如果 profile 本身没把后果链和外部秩序拆全，审计会过度落到句法层，写作也会缺现实承压件。",
                    "evidence": [
                        "缺失 scene_assets: " + " / ".join(asset_coverage.get("missing_scene_asset_keys", [])[:6])
                    ],
                    "fix_methods": [
                        "先回拆文资产补 `public_explosion / external_order / consequence_chain`。",
                        "补齐后再重生成 profile，再跑全文审计。",
                    ],
                },
                source_family="asset_coverage",
                focus_layer="consequence_chain",
                asset_kind="scene_assets",
            )
        )
    if asset_coverage.get("missing_story_guardrail_keys"):
        items.append(
            annotate_impact_item(
                {
                    "title": "profile 缺少高敏结构护栏",
                    "priority": "P0",
                    "why_it_hits_audit": "如果 profile 里没有现实后果隔层、尾声入口归属、人物不同脸这些高敏结构证据，后续回修任务单就容易只剩通用压味，而抓不到真正的结构炸点。",
                    "evidence": [
                        "缺失 story_guardrails: " + " / ".join(asset_coverage.get("missing_story_guardrail_keys", [])[:6])
                    ],
                    "fix_methods": [
                        "先回拆书资产或 profile_source，补齐高敏结构护栏字段。",
                        "重生成 profile 后，再跑全文审计和回修任务单。",
                    ],
                },
                source_family="asset_coverage",
                focus_layer="bridge_structure",
                asset_kind="story_guardrails",
            )
        )
    return items


def build_consequence_recommendations(consequence_audit: dict) -> list[str]:
    recs: list[str] = []
    if consequence_audit.get("has_public_scene") and not consequence_audit.get("has_consequence_chain"):
        recs.append("公开场后果链不足：有公开炸场，但生活后果、秩序后果、现实代价没真正落下来。")
    if consequence_audit.get("has_public_scene") and not consequence_audit.get("has_external_order"):
        recs.append("公开场缺外部秩序接管：不要只剩吵和打脸，补监控、签字、警方、名单、程序等秩序件。")
    return recs


def build_external_block_audit_impact_items(light_report: dict, heavy_report: dict) -> list[dict]:
    items: list[dict] = []
    line_types = light_report.get("line_hit_types", {})
    opening_metrics = light_report.get("opening_metrics", {})
    hotspots = top_hotspots(heavy_report)
    high_findings = heavy_report.get("high_findings", [])
    medium_findings = heavy_report.get("medium_findings", [])

    if light_report.get("opening_signature_risks") or light_report.get("opening_signal_overload") or light_report.get("opening_reveal_chain"):
        evidence = []
        if light_report.get("opening_signature_risks"):
            evidence.extend(
                f"{item.get('type')}: {item.get('detail')}" for item in light_report.get("opening_signature_risks", [])[:3]
            )
        if opening_metrics:
            evidence.append(
                "开头1200字指标: "
                f"对话={opening_metrics.get('dialogue_count')} "
                f"单句段占比={opening_metrics.get('single_sentence_ratio')}"
            )
        items.append(
            annotate_impact_item(
                {
                "title": "开头成品感过高",
                "priority": "P0",
                "why_it_hits_audit": "外部分块审计通常先砍开头。开头如果信息揭露太整齐、对白太有效、每个物件都在为主线服务，会像整理过的成品稿。",
                "evidence": evidence,
                "fix_methods": [
                    "首屏只保留一个主承重件，不要同步把定位、朋友圈、电话、医院全推上来。",
                    "把解释换成手上事务、动作受阻、现场噪音，不要急着盖章。",
                    "减少一问一答直达结论的对白，让人物先回避、打岔、压着说。 ",
                ],
                },
                source_family="external_block_audit",
                focus_layer="surface_style",
            )
        )

    if light_report.get("over_effective_dialogue_blocks"):
        evidence = [
            f"L{item.get('line')} 段{item.get('paragraph_index')}: {item.get('detail')}"
            for item in light_report.get("over_effective_dialogue_blocks", [])[:4]
        ]
        items.append(
            annotate_impact_item(
                {
                "title": "对白效率过高",
                "priority": "P0",
                "why_it_hits_audit": "人物每句都在推进主线、句句都正中信息点，会让文本像被优化过的剧本对白，不像真人现场。",
                "evidence": evidence,
                "fix_methods": [
                    "删掉最会解释关系的那一句，保留别扭、错位、回避。",
                    "让人物先顾秩序件，再顾情绪，例如先压声音、先拦门、先找人。",
                    "把连续短对白打散到动作、视线、走位、旁人插话里。 ",
                ],
                },
                source_family="external_block_audit",
                focus_layer="dialogue_polish",
            )
        )

    if line_types.get("author_verdict") or line_types.get("theme_explanation") or line_types.get("direct_mental_state"):
        evidence = []
        evidence.extend(sample_lines_by_type(light_report, "author_verdict"))
        evidence.extend(sample_lines_by_type(light_report, "theme_explanation"))
        evidence.extend(sample_lines_by_type(light_report, "direct_mental_state"))
        items.append(
            annotate_impact_item(
                {
                "title": "作者替角色下结论",
                "priority": "P0",
                "why_it_hits_audit": "外部分块审计不只抓词，还抓作者站位。人物还在现场里，作者先把意义总结完，成品感会立刻升高。",
                "evidence": evidence[:4],
                "fix_methods": [
                    "把‘我明白了/这说明/真正的问题是’改成动作、停顿、物件、后果。",
                    "能删就删，不一定非要换句。",
                    "改完后检查这一段是否仍然读得懂，若读得懂，说明总结句本来就是多余的。 ",
                ],
                },
                source_family="external_block_audit",
                focus_layer="sentence_shell",
            )
        )

    if any(item.get("rule_id") == "system_panel_decompression" for item in high_findings) or line_types.get("sequence_shell"):
        evidence = []
        for item in high_findings:
            if item.get("rule_id") == "system_panel_decompression":
                evidence.append(f"{item.get('label')} x{item.get('count')}")
        evidence.extend(sample_lines_by_type(light_report, "sequence_shell"))
        items.append(
            annotate_impact_item(
                {
                "title": "流程件和证据件摆放过整齐",
                "priority": "P0",
                "why_it_hits_audit": "时间线、证据链、流程安排如果排得太清、太顺、太会服务高潮，外部分块审计会把它看成‘加工过的说明型成文秩序’。",
                "evidence": evidence[:4],
                "fix_methods": [
                    "不要总用‘九点几分、十一点几分’一口气报完整套时间线。",
                    "证据分两次以上漏出，别全堆在最戏剧化时刻一次打完。",
                    "把流程改成卡壳、迟滞、翻找、被打断，而不是像宣读案卷。 ",
                ],
                },
                source_family="external_block_audit",
                focus_layer="scene_order",
            )
        )

    if light_report.get("uniform_paragraph_blocks") or hotspots:
        evidence = []
        evidence.extend(
            f"L{item.get('line')} 连续段长块: {item.get('detail')}"
            for item in light_report.get("uniform_paragraph_blocks", [])[:3]
        )
        evidence.extend(hotspots[:4])
        items.append(
            annotate_impact_item(
                {
                "title": "重复热点和段落匀速感",
                "priority": "P1",
                "why_it_hits_audit": "同一热点短语反复出现，配上长度接近的短段，会像统一后处理过的产品稿。",
                "evidence": evidence[:6],
                "fix_methods": [
                    "同一个信息点不要换着壳子重复说三四遍。",
                    "删一半重复短语，把其中一两次改成现场物件或他人动作。",
                    "故意打散段长，不要每段都一到两句、每句都刚好能落刀。 ",
                ],
                },
                source_family="external_block_audit",
                focus_layer="surface_style",
            )
        )

    if any(item.get("rule_id") == "binary_contrast" for item in high_findings) or any(
        item.get("rule_id") == "realization_template" for item in medium_findings
    ):
        evidence = []
        for group in (high_findings, medium_findings):
            for item in group:
                if item.get("rule_id") in {"binary_contrast", "realization_template", "colon_template"}:
                    examples = " | ".join(item.get("examples", [])[:2])
                    evidence.append(f"{item.get('label')}: {examples}")
        items.append(
            annotate_impact_item(
                {
                "title": "标准句壳过强",
                "priority": "P1",
                "why_it_hits_audit": "‘不是A而是B’、‘就在这时’、‘写着：’这类句壳，本身不一定有罪，但集中出现时会把稿子拉回模板感。",
                "evidence": evidence[:4],
                "fix_methods": [
                    "优先删二分句壳，不要只是换同义词。",
                    "把‘就在这时’改成具体声音、走位、物件进入。",
                    "冒号说明句改成散开的视觉观察，不要像展示板。 ",
                ],
                },
                source_family="external_block_audit",
                focus_layer="sentence_shell",
            )
        )

    return items


def build_bridge_impact_items(bridge_audit: list[dict]) -> list[dict]:
    items: list[dict] = []
    for item in bridge_audit[:3]:
        missing = item.get("must_keep_missing", [])
        avoid = item.get("must_avoid_hit", [])
        opening_missing = item.get("opening_pattern_missing", [])
        fake_hits = item.get("fake_signal_hit", [])
        sequence_missing = item.get("recommended_sequence_missing", [])
        sequence_out_of_order = item.get("recommended_sequence_out_of_order", [])
        if not missing and not avoid and not opening_missing and not fake_hits and not sequence_missing and not sequence_out_of_order:
            continue
        evidence = []
        if item.get("opening_pattern_hit"):
            evidence.append("已命中起手件: " + " / ".join(item["opening_pattern_hit"][:4]))
        if opening_missing:
            evidence.append("缺失起手件: " + " / ".join(opening_missing[:4]))
        if item.get("must_keep_hit"):
            evidence.append("已命中承重件: " + " / ".join(item["must_keep_hit"][:6]))
        if missing:
            evidence.append("缺失承重件: " + " / ".join(missing[:6]))
        if item.get("recommended_sequence_hit"):
            evidence.append("已命中顺序件: " + " / ".join(item["recommended_sequence_hit"][:6]))
        if sequence_missing:
            evidence.append("缺失顺序件: " + " / ".join(sequence_missing[:6]))
        if sequence_out_of_order:
            evidence.append("顺序漂移: " + " / ".join(sequence_out_of_order[:4]))
        if avoid:
            evidence.append("踩中禁写点: " + " / ".join(avoid[:6]))
        if fake_hits:
            evidence.append("命中易假点: " + " / ".join(fake_hits[:6]))
        if item.get("why_order_matters"):
            evidence.append("顺序不能乱原因: " + " / ".join(item["why_order_matters"][:4]))
        why = item.get("why_original_passes", [])
        if why:
            evidence.append("原文能过关键: " + " / ".join(why[:4]))

        fix_methods = []
        if opening_missing:
            fix_methods.append("先把桥段起手件放回开场，不要一上来就写成结果说明。")
            fix_methods.append("不要先摆证据桌，先让人物边过边漏出越界感。")
        if missing:
            fix_methods.append("不要先润句，先把桥段承重件补回来。")
            fix_methods.append("优先补物件、秩序件、位置件，不优先补情绪形容词。")
        if sequence_missing or sequence_out_of_order:
            fix_methods.append("按原桥段推荐顺序重排现场，不要把后果或审判提前说穿。")
            fix_methods.append("先事故后关系、先异常后来源、先当下动作后旧账碎片。")
        if avoid:
            fix_methods.append("先删禁写点，再看还缺哪些承重件。")
        if fake_hits:
            fix_methods.append("删掉易假写法，恢复现场对话、证据件和秩序件自己出场。")
            fix_methods.append("对白允许讨嫌、回避、先压秩序，不要句句都像答题。")
        if why:
            fix_methods.append("把原文能过的原因落进现场顺序，而不是写成说明句。")
            fix_methods.append("旧账只带半截，让桥从烂关系里自己冒出来，不要后补成说明资料。")

        items.append(
            annotate_impact_item(
                {
                "title": f"同桥承重件不完整：{item['bridge']}",
                "priority": "P0",
                "why_it_hits_audit": "不是桥段本身有问题，而是你在用这个桥时，缺了原文真正承重的那几件，结果只剩成品剧情壳。",
                "evidence": evidence,
                "fix_methods": fix_methods,
                },
                source_family="bridge",
                focus_layer="bridge_structure",
                asset_kind="bridge_rules",
            )
        )
    return items


def build_consequence_impact_items(consequence_audit: dict) -> list[dict]:
    items: list[dict] = []
    if consequence_audit.get("has_public_scene") and not consequence_audit.get("has_consequence_chain"):
        items.append(
            annotate_impact_item(
                {
                "title": "公开场后果链不足",
                "priority": "P0",
                "why_it_hits_audit": "公开炸场之后如果没有继续改变生活秩序、现实归属和关系位置，就会像只为高潮服务的成品桥。",
                "evidence": [
                    "已命中公开场: " + " / ".join(consequence_audit.get("public_explosion_hits", [])[:6]),
                    "后果链命中不足: " + " / ".join(consequence_audit.get("consequence_hits", [])[:6]),
                ],
                "fix_methods": [
                    "公开场后补真实后果，不要只停在打脸。",
                    "后果优先写归属变动、生活成本、秩序处理，不优先写心情。 ",
                ],
                },
                source_family="consequence",
                focus_layer="consequence_chain",
                asset_kind="scene_assets",
            )
        )
    if consequence_audit.get("has_public_scene") and not consequence_audit.get("has_external_order"):
        items.append(
            annotate_impact_item(
                {
                "title": "公开场缺外部秩序接管",
                "priority": "P0",
                "why_it_hits_audit": "原文能过，常常靠外部秩序接手现场；如果只剩人物互吵，外部分块审计会更容易判成加工过的爽文高潮。",
                "evidence": [
                    "已命中公开场: " + " / ".join(consequence_audit.get("public_explosion_hits", [])[:6]),
                    "外部秩序命中不足: " + " / ".join(consequence_audit.get("external_order_hits", [])[:6]),
                ],
                "fix_methods": [
                    "补监控、签字、名单、警察、程序、医生、律师等外部秩序件。",
                    "让公开场从‘吵赢’推进到‘秩序接管’。 ",
                ],
                },
                source_family="consequence",
                focus_layer="external_order",
                asset_kind="scene_assets",
            )
        )
    return items


def audit_opening_hook(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    opening = text[:1200]
    hook_hits = collect_term_hits(opening, style_assets.get("opening_hooks", []), limit=10)
    misdirection_hits = collect_term_hits(opening, style_assets.get("misdirection", []), limit=6)
    signal_hits = []
    for items in profile.get("opening_signal_groups", {}).values() if isinstance(profile.get("opening_signal_groups"), dict) else []:
        if isinstance(items, list):
            signal_hits.extend(collect_term_hits(opening, items, limit=4))
    signal_hits = normalize_terms(signal_hits)[:10]
    question_count = opening.count("？") + opening.count("?")
    return {
        "hook_hits": hook_hits,
        "misdirection_hits": misdirection_hits,
        "signal_hits": signal_hits,
        "question_count": question_count,
        "has_second_push": len(hook_hits) >= 2 or len(misdirection_hits) >= 1,
    }


def audit_object_pressure(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    hits = collect_term_hits(text, style_assets.get("object_pressure", []), limit=12)
    return {
        "hits": hits,
        "opening_hits": collect_term_hits(text[:1200], style_assets.get("object_pressure", []), limit=6),
        "ending_hits": collect_term_hits(text[-1200:], style_assets.get("object_pressure", []), limit=6),
    }


def audit_action_axis(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    hits = collect_term_hits(text, style_assets.get("action_axis", []), limit=12)
    return {"hits": hits}


def audit_micro_actions(text: str, light_report: dict, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    hits = collect_term_hits(text, style_assets.get("micro_actions", []), limit=12)
    return {
        "hits": hits,
        "direct_mental_state_hits": light_report.get("line_hit_types", {}).get("direct_mental_state", 0),
        "standard_reaction_hits": light_report.get("line_hit_types", {}).get("standard_reaction", 0),
    }


def audit_quiet_pressure(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    hits = collect_term_hits(text, style_assets.get("quiet_pressure", []), limit=12)
    return {"hits": hits}


def audit_character_bias(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    hits = collect_term_hits(text, style_assets.get("character_bias", []), limit=12)
    return {"hits": hits}


def audit_meltdown_dialogue(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    dialogue = split_dialogue_segments(text)
    hits = collect_term_hits(text, style_assets.get("meltdown_dialogue", []), limit=12)
    short_dialogue_count = sum(1 for item in dialogue if len(item) <= 10)
    long_dialogue_count = sum(1 for item in dialogue if len(item) >= 24)
    return {
        "hits": hits,
        "dialogue_count": len(dialogue),
        "short_dialogue_count": short_dialogue_count,
        "long_dialogue_count": long_dialogue_count,
    }


def audit_rotten_relationship(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    hits = collect_term_hits(text, style_assets.get("rotten_relationship", []), limit=12)
    return {"hits": hits}


def audit_dialogue_bridges(text: str, profile: dict) -> dict:
    style_assets = get_style_assets(profile)
    hits = collect_term_hits(text, style_assets.get("dialogue_bridges", []), limit=12)
    return {"hits": hits}


def audit_scene_function_overload(text: str, profile: dict) -> list[dict]:
    style_assets = get_style_assets(profile)
    categories = {
        "opening_hooks": style_assets.get("opening_hooks", []),
        "misdirection": style_assets.get("misdirection", []),
        "object_pressure": style_assets.get("object_pressure", []),
        "action_axis": style_assets.get("action_axis", []),
        "micro_actions": style_assets.get("micro_actions", []),
        "quiet_pressure": style_assets.get("quiet_pressure", []),
        "character_bias": style_assets.get("character_bias", []),
        "meltdown_dialogue": style_assets.get("meltdown_dialogue", []),
        "rotten_relationship": style_assets.get("rotten_relationship", []),
        "dialogue_bridges": style_assets.get("dialogue_bridges", []),
        "public_explosion": profile.get("scene_assets", {}).get("public_explosion", []) if isinstance(profile.get("scene_assets"), dict) else [],
        "external_order": profile.get("scene_assets", {}).get("external_order", []) if isinstance(profile.get("scene_assets"), dict) else [],
        "consequence_chain": profile.get("scene_assets", {}).get("consequence_chain", []) if isinstance(profile.get("scene_assets"), dict) else [],
    }
    overloads: list[dict] = []
    for idx, para in enumerate(split_paragraphs(text), start=1):
        hit_categories = []
        hit_terms = []
        for name, terms in categories.items():
            hits = collect_term_hits(para, terms, limit=2)
            if hits:
                hit_categories.append(name)
                hit_terms.extend(hits)
        if len(hit_categories) >= 4:
            overloads.append(
                {
                    "paragraph_index": idx,
                    "categories": hit_categories,
                    "terms": normalize_terms(hit_terms)[:8],
                    "excerpt": para[:120],
                }
            )
        if len(overloads) >= 6:
            break
    return overloads


def audit_ending_closure(text: str, profile: dict) -> dict:
    ending = text[-1200:]
    scene_assets = profile.get("scene_assets", {}) if isinstance(profile.get("scene_assets"), dict) else {}
    style_assets = get_style_assets(profile)
    object_hits = collect_term_hits(ending, style_assets.get("object_pressure", []), limit=8)
    consequence_hits = collect_term_hits(ending, scene_assets.get("consequence_chain", []), limit=8)
    external_hits = collect_term_hits(ending, scene_assets.get("external_order", []), limit=8)
    return {
        "object_hits": object_hits,
        "consequence_hits": consequence_hits,
        "external_hits": external_hits,
        "looks_like_soft_object_closure": bool(object_hits) and not consequence_hits and not external_hits,
    }


def build_style_recommendations(style_audits: dict) -> list[str]:
    recs: list[str] = []
    opening = style_audits.get("opening_hook_audit", {})
    if opening and not opening.get("has_second_push") and opening.get("signal_hits"):
        recs.append("开头只亮了事故，没有补第二推进点或误判种子，容易像新闻式开头。")

    micro = style_audits.get("micro_action_audit", {})
    if micro and not micro.get("hits") and (micro.get("direct_mental_state_hits") or micro.get("standard_reaction_hits")):
        recs.append("空情绪句偏多，但没有足够微动作承情，先把情绪压回手上动作和物件处理。")

    quiet = style_audits.get("quiet_pressure_audit", {})
    if quiet is not None and not quiet.get("hits"):
        recs.append("安静压迫场资产过少，容易只剩对白推进。补门口、走廊、前台、饭桌这类不解释的压场。")

    bias = style_audits.get("character_bias_audit", {})
    if bias is not None and not bias.get("hits"):
        recs.append("人物偏手没有落到正文里，人物会只剩功能反应。先确定每个核心人物的第一反应手势。")

    meltdown = style_audits.get("meltdown_dialogue_audit", {})
    if meltdown and meltdown.get("dialogue_count", 0) >= 8 and not meltdown.get("hits"):
        recs.append("对白多但缺失控说话资产，人物太会说，会像高效剧本对白。")

    rotten = style_audits.get("rotten_relationship_audit", {})
    if rotten is not None and not rotten.get("hits"):
        recs.append("烂关系没有从空间、站位、默认反应里自己漏出来，关系坏只停在说明层。")

    overload = style_audits.get("scene_function_overload_audit", [])
    if overload:
        recs.append("至少有一场戏承担了过多功能，先拆场，不要让一段同时做钩子、举证、判词、追悔和收尾。")

    ending = style_audits.get("ending_closure_audit", {})
    if ending.get("looks_like_soft_object_closure"):
        recs.append("结尾更像旧物式安静谢幕，缺后果链或外部秩序接管，容易回弹成精修短篇收束。")
    return recs


def build_style_impact_items(style_audits: dict, light_report: dict) -> list[dict]:
    items: list[dict] = []
    opening = style_audits.get("opening_hook_audit", {})
    if opening and opening.get("signal_hits") and not opening.get("has_second_push"):
        items.append(
            annotate_impact_item(
                {
                "title": "开头缺第二推进点或误判种子",
                "priority": "P0",
                "why_it_hits_audit": "只有事故，没有第二推进点和第一问号，开头就会像把题目展开给读者看，不像真人现场继续失控。",
                "evidence": [
                    "开头信号: " + " / ".join(opening.get("signal_hits", [])[:6]),
                    "开头钩子命中: " + " / ".join(opening.get("hook_hits", [])[:4]),
                    "误判命中: " + " / ".join(opening.get("misdirection_hits", [])[:4]),
                ],
                "fix_methods": [
                    "别只保留第一刀，补一个更脏的第二推进点或误判种子。",
                    "让读者在前 80 字里多追一个问号，不要首屏就解释背景。",
                ],
                },
                source_family="style",
                focus_layer="bridge_structure",
            )
        )

    micro = style_audits.get("micro_action_audit", {})
    if micro and not micro.get("hits") and (micro.get("direct_mental_state_hits") or micro.get("standard_reaction_hits")):
        items.append(
            annotate_impact_item(
                {
                "title": "情绪没有落进微动作",
                "priority": "P0",
                "why_it_hits_audit": "空情绪、标准反应多，而人物手上没有活，最容易被判成会写情绪的样稿。",
                "evidence": [
                    f"direct_mental_state: {micro.get('direct_mental_state_hits')}",
                    f"standard_reaction: {micro.get('standard_reaction_hits')}",
                    "微动作命中不足",
                ],
                "fix_methods": [
                    "优先找能替掉情绪词的手上动作、收回动作、流程动作。",
                    "别补漂亮心声，补停顿、放回去、按住、倒扣、划掉这类动作。",
                ],
                },
                source_family="style",
                focus_layer="character_reaction",
            )
        )

    bias = style_audits.get("character_bias_audit", {})
    if bias is not None and not bias.get("hits"):
        items.append(
            annotate_impact_item(
                {
                "title": "人物偏手没有立住",
                "priority": "P0",
                "why_it_hits_audit": "角色如果只会在每场戏里说最对的话，文本会像作者操控，不像人先按本能和旧习惯反应。",
                "evidence": ["人物偏手命中不足"],
                "fix_methods": [
                    "先写人物稳定第一反应，再写道理。",
                    "先明确核心人物各自的第一反应手势，再写完整解释或摊牌。",
                    "男主优先写安排句、分配句、压场句，不要一上来就写标准解释。",
                    "女主遇刀先处理现实、先守位置，真难堪时把话压短。",
                ],
                },
                source_family="style",
                focus_layer="character_reaction",
            )
        )

    meltdown = style_audits.get("meltdown_dialogue_audit", {})
    if meltdown and meltdown.get("dialogue_count", 0) >= 8 and not meltdown.get("hits"):
        items.append(
            annotate_impact_item(
                {
                "title": "对白缺失控层，只剩高效推进",
                "priority": "P0",
                "why_it_hits_audit": "真人冲突里常常先控场、打岔、回避、说短句；如果对白句句回答核心，只会像优化过的剧本。",
                "evidence": [
                    f"dialogue_count: {meltdown.get('dialogue_count')}",
                    f"short_dialogue_count: {meltdown.get('short_dialogue_count')}",
                    f"long_dialogue_count: {meltdown.get('long_dialogue_count')}",
                ],
                "fix_methods": [
                    "把一部分解释对白改成控场句、回避句、手续句。",
                    "允许人物说不完整、说偏、说烦，而不是句句对题。",
                    "理亏的人先绕，不先正答；先用‘先这样 / 回去再说 / 晚点再说’这类控场废气。",
                    "追妻期少写高质量忏悔，多写抓不准重点的笨拙动作句。",
                ],
                },
                source_family="style",
                focus_layer="dialogue_polish",
            )
        )

    rotten = style_audits.get("rotten_relationship_audit", {})
    if rotten is not None and not rotten.get("hits"):
        items.append(
            annotate_impact_item(
                {
                "title": "烂关系没有自己漏出来",
                "priority": "P1",
                "why_it_hits_audit": "关系坏如果只能靠人物复述旧账，会像作者举证；真人稿更常靠空间、站位、默认反应先漏出来。",
                "evidence": ["烂关系漏出资产命中不足"],
                "fix_methods": [
                    "把关系坏落到空间权限、优先级顺序和边缘站位上。",
                    "少列旧账，多写默认反应和边界被碰掉。",
                    "优先补主卧门外、病房门口、前台登记口、电梯口这种掉位站位。",
                    "写谁默认能进哪个空间、谁的东西先被挪开，不要只让人物自己说明关系坏。",
                ],
                },
                source_family="style",
                focus_layer="character_reaction",
            )
        )

    dialogue_bridges = style_audits.get("dialogue_bridges_audit", {})
    if dialogue_bridges is not None and not dialogue_bridges.get("hits") and light_report.get("over_effective_dialogue_blocks"):
        items.append(
            annotate_impact_item(
                {
                "title": "对白衔接过直，缺现场桥",
                "priority": "P1",
                "why_it_hits_audit": "对白如果没有走位、旁人插话、手续件、噪音桥接，很容易变成高密度信息投喂块。",
                "evidence": ["对话衔接/对白功能资产命中不足"],
                "fix_methods": [
                    "把对白拆散到动作、视线、站位、物件和旁人反应里。",
                    "同一段对话不要一问一答把信息全交代完。",
                    "让旁人插话、手续件、噪音桥接先把话截断一次。",
                    "先顾秩序件，再顾情绪件，不要每句都直达核心。",
                ],
                },
                source_family="style",
                focus_layer="dialogue_polish",
            )
        )

    overload = style_audits.get("scene_function_overload_audit", [])
    if overload:
        top = overload[0]
        items.append(
            annotate_impact_item(
                {
                "title": "单场戏承担功能过多",
                "priority": "P0",
                "why_it_hits_audit": "一场戏同时做钩子、举证、关系定性、公开翻刀和后果收束，会像平台成品模块，不像现场自然失控。",
                "evidence": [
                    f"段落 {top.get('paragraph_index')} 类别: " + " / ".join(top.get("categories", [])[:6]),
                    "命中词: " + " / ".join(top.get("terms", [])[:6]),
                    "片段: " + top.get("excerpt", ""),
                ],
                "fix_methods": [
                    "拆功能，不要一场戏一次性做完。",
                    "先保这场最值钱的一刀，其他功能后移到下一场或交给外部秩序。",
                ],
                },
                source_family="style",
                focus_layer="scene_order",
            )
        )

    ending = style_audits.get("ending_closure_audit", {})
    if ending.get("looks_like_soft_object_closure"):
        items.append(
            annotate_impact_item(
                {
                "title": "结尾落成了旧物式安静谢幕",
                "priority": "P1",
                "why_it_hits_audit": "只用旧物或旧房做柔性收束，缺后果链和秩序件，容易显得太会结束、太像短篇谢幕桥。",
                "evidence": [
                    "结尾物件: " + " / ".join(ending.get("object_hits", [])[:6]),
                    "结尾后果链: " + " / ".join(ending.get("consequence_hits", [])[:6]),
                    "结尾外部秩序: " + " / ".join(ending.get("external_hits", [])[:6]),
                ],
                "fix_methods": [
                    "结尾优先落后果，不优先落感悟和旧物抚摸。",
                    "让系统、手续、身份、归属的变化完成最后一刀。",
                ],
                },
                source_family="style",
                focus_layer="consequence_chain",
            )
        )
    return items


def run_light_audit(
    file_path: Path,
    python_bin: str,
    light_script: Path,
    profile_path: Path | None,
) -> dict:
    light_cmd = [python_bin, str(light_script), str(file_path), "--json"]
    if profile_path:
        light_cmd.extend(["--profile", str(profile_path)])
    light_code, light_out, light_err = run_command(light_cmd)
    if light_code not in (0, 1):
        raise RuntimeError(f"轻审计执行失败:\n{light_err}")
    return load_json_output("轻审计", light_out, light_err)


def run_heavy_audit(
    file_path: Path,
    heavy_script: Path,
    heavy_lexicon: Path,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="full_audit_") as tmp_dir:
        heavy_output = Path(tmp_dir) / f"{file_path.stem}.heavy_audit.json"
        heavy_cmd = [
            "python3",
            str(heavy_script),
            str(file_path),
            "--format",
            "json",
            "--lexicon",
            str(heavy_lexicon),
            "--output",
            str(heavy_output),
        ]
        heavy_code, heavy_out, heavy_err = run_command(heavy_cmd)
        if heavy_code != 0:
            raise RuntimeError(f"重审计执行失败:\n{heavy_err or heavy_out}")
        if not heavy_output.exists():
            raise RuntimeError(f"重审计未产出 JSON: {heavy_output}\nstdout:\n{heavy_out}")
        return json.loads(heavy_output.read_text(encoding="utf-8"))


def build_style_audits(text: str, profile: dict, light_report: dict) -> dict:
    return {
        "opening_hook_audit": audit_opening_hook(text, profile),
        "object_pressure_audit": audit_object_pressure(text, profile),
        "action_axis_audit": audit_action_axis(text, profile),
        "micro_action_audit": audit_micro_actions(text, light_report, profile),
        "quiet_pressure_audit": audit_quiet_pressure(text, profile),
        "character_bias_audit": audit_character_bias(text, profile),
        "meltdown_dialogue_audit": audit_meltdown_dialogue(text, profile),
        "rotten_relationship_audit": audit_rotten_relationship(text, profile),
        "dialogue_bridges_audit": audit_dialogue_bridges(text, profile),
        "scene_function_overload_audit": audit_scene_function_overload(text, profile),
        "ending_closure_audit": audit_ending_closure(text, profile),
    }


def compute_local_risk_score(
    light_report: dict,
    heavy_report: dict,
    style_audits: dict,
    bridge_audit: list[dict] | None = None,
    consequence_audit: dict | None = None,
) -> float:
    light_summary = summarize_light(light_report)
    heavy_summary = summarize_heavy(heavy_report)
    score = float(heavy_summary.get("score") or 0)
    score += min(light_summary.get("total_hits", 0) * 1.8, 18)

    if light_report.get("opening_signal_overload"):
        score += 5
    if light_report.get("opening_reveal_chain"):
        score += 4
    if light_report.get("author_stance_overreach"):
        score += 4
    if light_report.get("over_effective_dialogue_blocks"):
        score += min(len(light_report.get("over_effective_dialogue_blocks", [])) * 3, 12)

    scene_overload = style_audits.get("scene_function_overload_audit") or []
    meltdown = style_audits.get("meltdown_dialogue_audit", {})
    object_hits = style_audits.get("object_pressure_audit", {}).get("hits", [])
    quiet_hits = style_audits.get("quiet_pressure_audit", {}).get("hits", [])
    external_pressure = bool(consequence_audit and consequence_audit.get("external_order_hits"))
    public_pressure = bool(consequence_audit and consequence_audit.get("public_explosion_hits"))
    conflict_surface = bool(
        scene_overload
        or light_report.get("over_effective_dialogue_blocks")
        or meltdown.get("dialogue_count", 0) >= 6
        or public_pressure
        or external_pressure
    )
    relationship_surface = bool(
        conflict_surface
        or object_hits
        or quiet_hits
        or style_audits.get("dialogue_bridges_audit", {}).get("hits")
    )

    style_penalty = 0
    if scene_overload:
        style_penalty += 7
    if conflict_surface and not style_audits.get("character_bias_audit", {}).get("hits"):
        style_penalty += 3
    if relationship_surface and not style_audits.get("rotten_relationship_audit", {}).get("hits"):
        style_penalty += 2
    if (
        not style_audits.get("micro_action_audit", {}).get("hits")
        and (
            style_audits.get("micro_action_audit", {}).get("direct_mental_state_hits")
            or style_audits.get("micro_action_audit", {}).get("standard_reaction_hits")
        )
    ):
        style_penalty += 5
    score += style_penalty

    if bridge_audit:
        top = bridge_audit[0]
        missing = len(top.get("must_keep_missing", []))
        avoid = len(top.get("must_avoid_hit", []))
        keep_hit = len(top.get("must_keep_hit", []))
        keep_ratio = float(top.get("keep_ratio") or 0)
        if keep_hit >= 2 or keep_ratio >= 0.25 or avoid:
            score += min(missing * 0.9 + avoid * 2, 8)
        elif keep_hit == 1:
            score += min(missing * 0.25, 2)

    if consequence_audit:
        if consequence_audit.get("has_public_scene") and not consequence_audit.get("has_external_order"):
            score += 4
        if consequence_audit.get("has_public_scene") and not consequence_audit.get("has_consequence_chain"):
            score += 4

    return round(clamp(score), 2)


def build_local_style_flags(style_audits: dict, light_report: dict, consequence_audit: dict | None = None) -> list[str]:
    flags: list[str] = []
    scene_overload = style_audits.get("scene_function_overload_audit") or []
    meltdown = style_audits.get("meltdown_dialogue_audit", {})
    object_hits = style_audits.get("object_pressure_audit", {}).get("hits", [])
    quiet_hits = style_audits.get("quiet_pressure_audit", {}).get("hits", [])
    conflict_surface = bool(
        scene_overload
        or light_report.get("over_effective_dialogue_blocks")
        or meltdown.get("dialogue_count", 0) >= 6
        or (consequence_audit and consequence_audit.get("public_explosion_hits"))
    )
    relationship_surface = bool(conflict_surface or object_hits or quiet_hits)

    if conflict_surface and not style_audits.get("character_bias_audit", {}).get("hits"):
        flags.append("人物偏手没有立住")
    if relationship_surface and not style_audits.get("rotten_relationship_audit", {}).get("hits"):
        flags.append("烂关系没有自己漏出来")
    if scene_overload:
        flags.append("单场戏承担功能过多")
    if (
        not style_audits.get("micro_action_audit", {}).get("hits")
        and (
            style_audits.get("micro_action_audit", {}).get("direct_mental_state_hits")
            or style_audits.get("micro_action_audit", {}).get("standard_reaction_hits")
        )
    ):
        flags.append("情绪没有落进微动作")
    return flags


def build_local_bridge_flags(bridge_audit: list[dict]) -> list[str]:
    flags: list[str] = []
    for item in bridge_audit[:3]:
        keep_hit = len(item.get("must_keep_hit", []))
        keep_ratio = float(item.get("keep_ratio") or 0)
        avoid = len(item.get("must_avoid_hit", []))
        opening_missing = item.get("opening_pattern_missing", [])
        sequence_missing = item.get("recommended_sequence_missing", [])
        sequence_out_of_order = item.get("recommended_sequence_out_of_order", [])
        fake_hits = item.get("fake_signal_hit", [])
        if keep_hit >= 2 or keep_ratio >= 0.25 or avoid or opening_missing or sequence_missing or sequence_out_of_order or fake_hits:
            flags.append(f"同桥承重件不完整：{item['bridge']}")
        if opening_missing:
            flags.append(f"同桥起手件缺失：{item['bridge']}")
        if sequence_out_of_order:
            flags.append(f"同桥顺序漂移：{item['bridge']}")
        elif sequence_missing:
            flags.append(f"同桥顺序件缺失：{item['bridge']}")
        if fake_hits:
            flags.append(f"同桥易假点命中：{item['bridge']}")
    return flags


def score_segments(
    source_text: str,
    file_suffix: str,
    profile: dict,
    profile_path: Path | None,
    rulebook: dict,
    python_bin: str,
    light_script: Path,
    heavy_script: Path,
    heavy_lexicon: Path,
    full_light_report: dict,
    full_style_audits: dict,
 ) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    paragraphs = build_paragraph_entries(source_text)
    display_blocks = build_display_blocks(paragraphs)
    segments = build_micro_segment_entries(source_text, paragraphs)
    if not segments:
        return [], [], [], [], [], [], []

    paragraph_to_block: dict[int, int] = {}
    for block in display_blocks:
        for idx in range(block["paragraph_start"], block["paragraph_end"] + 1):
            paragraph_to_block[idx] = block["block_index"]

    segment_scores: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="segment_audit_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for segment in segments:
            seg_file = tmp_root / f"segment_{segment['segment_index']}{file_suffix}"
            seg_file.write_text(segment["text"], encoding="utf-8")
            seg_light = run_light_audit(seg_file, python_bin, light_script, profile_path)
            seg_heavy = run_heavy_audit(seg_file, heavy_script, heavy_lexicon)
            seg_style = build_style_audits(segment["text"], profile, seg_light)
            seg_bridge = bridge_rule_audit(segment["text"], profile, top_n=2)
            seg_consequence = consequence_chain_audit(segment["text"], profile)
            seg_rulebook = audit_external_rulebook(segment["text"], rulebook)
            risk_score = compute_local_risk_score(seg_light, seg_heavy, seg_style, seg_bridge, seg_consequence)
            heavy_summary = summarize_heavy(seg_heavy)
            light_summary = summarize_light(seg_light)
            segment_scores.append(
                {
                    **{k: segment[k] for k in ("segment_index", "paragraph_start", "paragraph_end", "start_char", "end_char", "char_count")},
                    "display_block_start": paragraph_to_block.get(segment["paragraph_start"]),
                    "display_block_end": paragraph_to_block.get(segment["paragraph_end"]),
                    "risk_score": risk_score,
                    "risk_ratio": round(risk_score / 100.0, 4),
                    "risk_level": risk_level(risk_score),
                    "light_hits": light_summary.get("total_hits", 0),
                    "heavy_score": heavy_summary.get("score"),
                    "heavy_status": heavy_summary.get("status"),
                    "style_flags": build_local_style_flags(seg_style, seg_light, seg_consequence)[:4],
                    "bridge_flags": build_local_bridge_flags(seg_bridge)[:3],
                    "consequence_flags": [item["title"] for item in build_consequence_impact_items(seg_consequence)[:2]],
                    "rulebook_flags": build_local_rulebook_flags(seg_rulebook)[:4],
                    "excerpt": segment["text"][:180].replace("\n", " "),
                }
            )

    paragraph_to_segments: dict[int, list[dict]] = {}
    for seg in segment_scores:
        for idx in seg.get("paragraph_indexes", []) or range(seg["paragraph_start"], seg["paragraph_end"] + 1):
            paragraph_to_segments.setdefault(idx, []).append(seg)

    dialogue_block_paras = {
        item.get("paragraph_index")
        for item in full_light_report.get("over_effective_dialogue_blocks", [])
        if item.get("paragraph_index")
    }
    overload_paras = {
        item.get("paragraph_index")
        for item in full_style_audits.get("scene_function_overload_audit", [])
        if item.get("paragraph_index")
    }
    style_assets = get_style_assets(profile)
    opening_risky = bool(
        full_light_report.get("opening_signature_risks")
        or full_light_report.get("opening_signal_overload")
        or full_light_report.get("opening_reveal_chain")
    )

    paragraph_scores: list[dict] = []
    for para in paragraphs:
        candidate_segments = paragraph_to_segments.get(para["paragraph_index"], [])
        seg = max(candidate_segments, key=lambda x: float(x.get("risk_score", 0)), default=None)
        if candidate_segments:
            top_score = max(float(item.get("risk_score", 0)) for item in candidate_segments)
            avg_score = sum(float(item.get("risk_score", 0)) for item in candidate_segments) / len(candidate_segments)
            base = max(top_score * 0.75 + avg_score * 0.25, avg_score)
        else:
            base = 0.0
        local_bonus = 0.0
        flags: list[str] = []

        if para["paragraph_index"] in dialogue_block_paras:
            local_bonus += 12
            flags.append("高效对白块")
        if para["paragraph_index"] in overload_paras:
            local_bonus += 15
            flags.append("单场戏功能过多")
        if opening_risky and para["paragraph_index"] <= 4:
            local_bonus += 6
            flags.append("开头承压")

        category_hits = 0
        for key in (
            "object_pressure",
            "micro_actions",
            "character_bias",
            "meltdown_dialogue",
            "rotten_relationship",
            "dialogue_bridges",
        ):
            if collect_term_hits(para["text"], style_assets.get(key, []), limit=2):
                category_hits += 1
        if category_hits >= 3:
            local_bonus += 8
            flags.append("多资产挤压")
        elif category_hits == 2:
            local_bonus += 4

        quote_count = para["text"].count("“") + para["text"].count('"')
        # 短段只做末位节奏提醒，不能压过桥段/场戏问题。
        if quote_count >= 2 and para["char_count"] <= 180:
            local_bonus += 1.5
            flags.append("短段对白密")

        if "：" in para["text"] and para["char_count"] <= 160:
            local_bonus += 3
            flags.append("说明句偏强")

        para_score = round(clamp(base * 0.7 + local_bonus), 2)
        paragraph_scores.append(
            {
                "paragraph_index": para["paragraph_index"],
                "segment_index": seg["segment_index"] if seg else None,
                "display_block_index": paragraph_to_block.get(para["paragraph_index"]),
                "start_char": para["start_char"],
                "end_char": para["end_char"],
                "char_count": para["char_count"],
                "risk_score": para_score,
                "risk_ratio": round(para_score / 100.0, 4),
                "risk_level": risk_level(para_score),
                "flags": flags,
                "excerpt": para["text"][:120].replace("\n", " "),
            }
        )

    paragraph_to_primary_segment = {
        para_idx: max(items, key=lambda x: float(x.get("risk_score", 0)))
        for para_idx, items in paragraph_to_segments.items()
    }

    dynamic_segment_scores = build_dynamic_segment_scores(paragraphs, paragraph_scores, paragraph_to_primary_segment)
    for item in dynamic_segment_scores:
        item["display_block_start"] = paragraph_to_block.get(item["paragraph_start"])
        item["display_block_end"] = paragraph_to_block.get(item["paragraph_end"])
    high_risk_segments = sorted(
        [item for item in dynamic_segment_scores if item["risk_score"] >= 35],
        key=dynamic_segment_priority_tuple,
        reverse=True,
    )[:6]

    coarse_segments = build_coarse_segment_entries(source_text, paragraphs)
    coarse_segment_scores = [
        compute_coarse_segment_score(item, paragraph_scores, segment_scores)
        for item in coarse_segments
    ]

    return display_blocks, paragraphs, segment_scores, dynamic_segment_scores, paragraph_scores, high_risk_segments, coarse_segment_scores


def classify_segment_shape(item: dict) -> str:
    para_span = int(item["paragraph_end"]) - int(item["paragraph_start"]) + 1
    char_count = int(item.get("char_count", 0))
    if para_span >= 18 or char_count >= 900:
        return "block"
    if para_span <= 3 and char_count <= 220:
        return "point"
    return "scatter"


def build_segment_views(
    segment_scores: list[dict],
    paragraph_scores: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    para_map = {item["paragraph_index"]: item for item in paragraph_scores}
    block_segments: list[dict] = []
    scatter_segments: list[dict] = []
    point_paragraphs: list[dict] = []

    for item in segment_scores:
        shaped = {**item, "shape": classify_segment_shape(item)}
        local_hotspots: list[dict] = []
        for idx in range(item["paragraph_start"], item["paragraph_end"] + 1):
            para = para_map.get(idx)
            if not para or para["risk_score"] < 40:
                continue
            local_hotspots.append(
                {
                    "paragraph_index": para["paragraph_index"],
                    "display_block_index": para.get("display_block_index"),
                    "risk_score": para["risk_score"],
                    "flags": para.get("flags", [])[:4],
                    "excerpt": para.get("excerpt", ""),
                }
            )
        shaped["hotspot_paragraphs"] = sorted(
            local_hotspots,
            key=lambda x: (x["risk_score"], -x["paragraph_index"]),
            reverse=True,
        )[:5]
        if shaped["shape"] == "block":
            block_segments.append(shaped)
        else:
            scatter_segments.append(shaped)
            if shaped["shape"] == "point":
                point_paragraphs.extend(shaped["hotspot_paragraphs"] or local_hotspots)

    point_paragraphs = sorted(
        point_paragraphs,
        key=lambda x: (x["risk_score"], -x["paragraph_index"]),
        reverse=True,
    )[:8]
    return block_segments, scatter_segments, point_paragraphs


def build_display_block_scores(
    display_blocks: list[dict],
    raw_segment_scores: list[dict],
    paragraph_scores: list[dict],
) -> list[dict]:
    if not display_blocks:
        return []

    para_by_block: dict[int, list[dict]] = {}
    for para in paragraph_scores:
        block_index = para.get("display_block_index")
        if block_index:
            para_by_block.setdefault(block_index, []).append(para)

    micro_by_block: dict[int, list[dict]] = {}
    for seg in raw_segment_scores:
        start = seg.get("display_block_start")
        end = seg.get("display_block_end") or start
        if not start:
            continue
        for block_index in range(int(start), int(end) + 1):
            micro_by_block.setdefault(block_index, []).append(seg)

    results: list[dict] = []
    for block in display_blocks:
        block_index = block["block_index"]
        paras = para_by_block.get(block_index, [])
        micros = micro_by_block.get(block_index, [])
        para_scores = [float(item.get("risk_score", 0)) for item in paras]
        micro_scores = [float(item.get("risk_score", 0)) for item in micros]
        all_scores = para_scores + micro_scores
        if not all_scores:
            score = 0.0
        else:
            avg_score = sum(all_scores) / len(all_scores)
            top_scores = sorted(all_scores, reverse=True)[:3]
            top_avg = sum(top_scores) / len(top_scores)
            density = sum(1 for value in all_scores if value >= 35) / len(all_scores)
            score = clamp(avg_score * 0.45 + top_avg * 0.45 + density * 10)
        hot_paras = sorted(
            [item for item in paras if item.get("risk_score", 0) >= 30],
            key=lambda x: (float(x.get("risk_score", 0)), -int(x.get("paragraph_index", 0))),
            reverse=True,
        )[:5]
        flags = dedupe_keep_order(
            [flag for item in hot_paras for flag in item.get("flags", [])]
            + [flag for item in micros for flag in item.get("style_flags", [])]
            + [flag for item in micros for flag in item.get("bridge_flags", [])]
            + [flag for item in micros for flag in item.get("consequence_flags", [])]
        )
        rulebook_flags = dedupe_keep_order(
            [flag for item in micros for flag in item.get("rulebook_flags", [])]
        )
        results.append(
            {
                **block,
                "risk_score": round(score, 2),
                "risk_ratio": round(score / 100.0, 4),
                "risk_level": risk_level(score),
                "micro_count": len(micros),
                "hot_paragraphs": hot_paras,
                "flags": flags[:8],
                "rulebook_flags": rulebook_flags[:6],
            }
        )
    return results


def block_label(item: dict) -> str:
    start = item.get("display_block_start")
    end = item.get("display_block_end")
    if start and end:
        if start == end:
            return f"正文块{start}"
        return f"正文块{start}-{end}"
    return f"原始段{item.get('paragraph_start')}-{item.get('paragraph_end')}"


def markdown_report(file_path: Path, light: dict, heavy: dict, recommendations: list[str], combined: dict | None = None) -> str:
    light_summary = summarize_light(light)
    heavy_summary = summarize_heavy(heavy)
    combined = combined or {}

    lines: list[str] = []
    lines.append(f"# 全量 AI 味审计报告")
    lines.append("")
    lines.append(f"- 文件: `{file_path}`")
    lines.append(f"- 轻审计命中总数: `{light_summary['total_hits']}`")
    lines.append(f"- 重审计风险分: `{heavy_summary.get('score')}`")
    lines.append(f"- 重审计状态: `{heavy_summary.get('status')}`")
    if combined.get("internal_proxy_summary"):
        lines.append(f"- 内部整体风险分: `{combined['internal_proxy_summary'].get('overall_risk')}`")
        lines.append(f"- 内部最高块风险分: `{combined['internal_proxy_summary'].get('max_block_risk')}`")
    if combined.get("sample_grading_guidance"):
        lines.append(f"- 上游样本等级: `{combined['sample_grading_guidance'].get('level')}`")
    lines.append("")
    lines.append("## 轻审计摘要")
    lines.append("")
    lines.append(f"- 行级命中: `{light_summary['line_hits']}`")
    lines.append(f"- 段长过匀块: `{light_summary['uniform_paragraph_blocks']}`")
    lines.append(f"- 回忆链过密: `{light_summary['dense_flashback_chains']}`")
    lines.append(f"- 高效对白块: `{light_summary['over_effective_dialogue_blocks']}`")
    lines.append(f"- 开篇口气风险: `{light_summary['opening_signature_risks']}`")
    lines.append(f"- 开篇信息投喂过满: `{light_summary['opening_signal_overload']}`")
    lines.append(f"- 开篇标准翻刀链: `{light_summary['opening_reveal_chain']}`")
    lines.append(f"- 作者站位过高: `{light_summary['author_stance_overreach']}`")
    lines.append("")
    if light_summary.get("line_hit_types"):
        lines.append("## 轻审计行级类型")
        lines.append("")
        for name, count in list(light_summary["line_hit_types"].items())[:12]:
            lines.append(f"- `{name}`: `{count}`")
        lines.append("")
    lines.append("## 重审计摘要")
    lines.append("")
    lines.append(f"- finding 数: `{heavy_summary['finding_count']}`")
    lines.append(f"- metric 数: `{heavy_summary['metric_count']}`")
    lines.append(f"- hotspot 数: `{heavy_summary['hotspot_count']}`")
    lines.append(f"- 句首重复项: `{heavy_summary['repeated_opening_count']}`")
    lines.append("")
    if combined.get("internal_proxy_summary"):
        proxy = combined["internal_proxy_summary"]
        lines.append("## 内部过稿标准")
        lines.append("")
        lines.append(f"- 内部整体风险分: `{proxy.get('overall_risk')}`")
        lines.append(f"- 内部最高块风险分: `{proxy.get('max_block_risk')}`")
        lines.append(f"- 内部过稿判定: `{proxy.get('judgement', {}).get('label')}`")
        lines.append(f"- 判定说明: {proxy.get('judgement', {}).get('note')}")
        lines.append(f"- 本稿块波动: `{proxy.get('features', {}).get('our_display_block_range')}`")
        lines.append(f"- 本稿热点段数: `{proxy.get('features', {}).get('our_hot_paragraph_total')}`")
        lines.append(f"- 本稿重审计分: `{proxy.get('features', {}).get('our_heavy_score')}`")
        lines.append("")
    if combined.get("sample_grading_guidance"):
        sample = combined["sample_grading_guidance"]
        lines.append("## 上游样本准入")
        lines.append("")
        lines.append(f"- 样本等级: `{sample.get('level')}`")
        lines.append(f"- DNA可用性: `{sample.get('dna_usable')}`")
        if sample.get("summary"):
            lines.append(f"- 一句话判断: {sample.get('summary')}")
        if sample.get("learnable_layers"):
            lines.append(f"- 可学层: {' / '.join(sample.get('learnable_layers', [])[:6])}")
        if sample.get("forbidden_layers"):
            lines.append(f"- 禁学层: {' / '.join(sample.get('forbidden_layers', [])[:6])}")
        for item in sample.get("audit_notes", [])[:4]:
            lines.append(f"- 提示: {item}")
        if sample.get("level") == "B类骨架样本":
            lines.append("- 当前排序策略: 桥段承重件 / 后果链 / 场面秩序优先，句法抛光类问题后置。")
        elif sample.get("level") == "C类负样本":
            lines.append("- 当前排序策略: 只把这份样本当反面规则源，正向风格模仿类问题一律后置。")
        lines.append("")
    segment_scores = combined.get("segment_scores", [])
    raw_segment_scores = combined.get("raw_segment_scores", [])
    paragraph_scores = combined.get("paragraph_scores", [])
    display_blocks = combined.get("display_blocks", [])
    display_block_scores = combined.get("display_block_scores", [])
    coarse_segment_scores = combined.get("coarse_segment_scores", [])
    global_risk_shape = combined.get("global_risk_shape", {})
    if segment_scores:
        block_segments, scatter_segments, point_paragraphs = build_segment_views(segment_scores, paragraph_scores)
        lines.append("## 动态分段总览")
        lines.append("")
        lines.append(f"- 正文块数: `{len(display_blocks)}`")
        if coarse_segment_scores:
            lines.append(f"- 粗粒度长窗数: `{len(coarse_segment_scores)}`")
        lines.append(
            f"- 内部微切片数: `{len(raw_segment_scores)}`"
        )
        lines.append(
            f"- 动态风险块数: `{len(segment_scores)}`"
        )
        lines.append(
            "- 说明: `正文块` 是人工写作/修稿用的大块；`动态风险块` 是按局部风险自动聚合出来的结果，块数本来就会变化，不设固定目标。"
        )
        lines.append(
            f"- 整块风险: `{len(block_segments)}`"
        )
        lines.append(
            f"- 散点风险: `{len(scatter_segments)}`"
        )
        if global_risk_shape:
            lines.append(
                f"- 全局形状: `{global_risk_shape.get('shape')}` / 粗窗离散度 `{global_risk_shape.get('coarse_score_cv')}` / 高风险段比例 `{global_risk_shape.get('paragraph_high_ratio')}`"
            )
        lines.append("")
        if global_risk_shape and global_risk_shape.get("global_blocks"):
            lines.append("## 全局大块判断")
            lines.append("")
            for item in global_risk_shape.get("global_blocks", [])[:6]:
                flags = " / ".join(item.get("flags", [])[:5]) or "无明显标签"
                lines.append(
                    f"- 大块{item.get('block_index', '?')}: 分数 `{item.get('risk_score')}` "
                    f"原始段 `{item.get('paragraph_start')}-{item.get('paragraph_end')}` "
                    f"字数 `{item.get('char_count')}` "
                    f"风险 `{flags}`"
                )
            lines.append("")
        if display_block_scores:
            lines.append("## 正文块风险排行")
            lines.append("")
            for item in sorted(display_block_scores, key=lambda x: x["risk_score"], reverse=True):
                flags = " / ".join(item.get("flags", [])[:4]) or "无明显集中标签"
                hot_text = "；".join(
                    f"原始段{hot['paragraph_index']} {hot['risk_score']}"
                    for hot in item.get("hot_paragraphs", [])[:3]
                ) or "无明显段落热点"
                lines.append(
                    f"- 正文块{item['block_index']}: 分数 `{item['risk_score']}` "
                    f"原始段 `{item['paragraph_start']}-{item['paragraph_end']}` "
                    f"微切片 `{item['micro_count']}` "
                    f"风险 `{flags}` "
                    f"热点 `{hot_text}`"
                )
            lines.append("")
        if block_segments:
            lines.append("## 整块风险")
            lines.append("")
            for item in block_segments[:8]:
                labels = item.get("bridge_flags", [])[:2] + item.get("paragraph_flags", [])[:2]
                label_text = " / ".join(labels) if labels else "整块成文秩序偏整"
                hotspot_text = "；".join(
                    f"段落{hot['paragraph_index']} {hot['risk_score']}"
                    for hot in item.get("hotspot_paragraphs", [])[:3]
                ) or "无明显单点热点"
                lines.append(
                    f"- 片段{item['segment_index']}: 分数 `{item['risk_score']}` "
                    f"位置 `{block_label(item)}` / 原始段 `{item['paragraph_start']}-{item['paragraph_end']}` "
                    f"字数 `{item['char_count']}` "
                    f"风险 `{label_text}` "
                    f"热点 `{hotspot_text}`"
                )
            lines.append("")
        if scatter_segments:
            lines.append("## 散点风险")
            lines.append("")
            for item in scatter_segments[:10]:
                labels = item.get("bridge_flags", [])[:2] + item.get("paragraph_flags", [])[:2]
                label_text = " / ".join(labels) if labels else "局部桥段或句法偏人工化不足"
                shape_name = "单点" if item["shape"] == "point" else "散段"
                lines.append(
                    f"- {shape_name}片段{item['segment_index']}: 分数 `{item['risk_score']}` "
                    f"位置 `{block_label(item)}` / 原始段 `{item['paragraph_start']}-{item['paragraph_end']}` "
                    f"字数 `{item['char_count']}` "
                    f"风险 `{label_text}`"
                )
            lines.append("")
        if point_paragraphs:
            lines.append("## 段落级热点")
            lines.append("")
            for item in point_paragraphs[:8]:
                flags = " / ".join(item.get("flags", [])[:4]) or "局部风险聚集"
                lines.append(
                    f"- 原始段{item['paragraph_index']}（正文块{item.get('display_block_index', '?')}）: 分数 `{item['risk_score']}` 原因 `{flags}`"
                )
            lines.append("")
    if paragraph_scores:
        lines.append("## 高风险段落")
        lines.append("")
        top_paragraphs = sorted(paragraph_scores, key=lambda x: x["risk_score"], reverse=True)[:8]
        for item in top_paragraphs:
            flags = " / ".join(item.get("flags", [])[:4]) or "局部风险聚集"
            lines.append(
                f"- 原始段{item['paragraph_index']}（正文块{item.get('display_block_index', '?')}）: 分数 `{item['risk_score']}` "
                f"片段 `{item.get('segment_index')}` "
                f"原因 `{flags}`"
            )
        lines.append("")
    if heavy_summary.get("high_findings"):
        lines.append("## 高风险命中")
        lines.append("")
        for item in heavy_summary["high_findings"]:
            examples = " | ".join(item.get("examples", [])[:3])
            lines.append(f"- `{item.get('label')}` x{item.get('count')}: {examples}")
        lines.append("")
    if heavy_summary.get("medium_findings"):
        lines.append("## 中风险命中")
        lines.append("")
        for item in heavy_summary["medium_findings"][:8]:
            examples = " | ".join(item.get("examples", [])[:3])
            lines.append(f"- `{item.get('label')}` x{item.get('count')}: {examples}")
    lines.append("")
    lines.append("## style_assets 审计")
    lines.append("")
    lines.append("- 详见 `full_audit.json` 的 `style_audits / style_impact_items`。")
    lines.append("- 重点看：开头第二推进点、微动作承情、人物偏手、失控说话、烂关系漏出、单场戏功能堆叠。")
    lines.append("")
    rulebook_audit = combined.get("rulebook_audit", [])
    if rulebook_audit:
        lines.append("## 外置规则簿命中")
        lines.append("")
        for item in rulebook_audit[:8]:
            lines.append(
                f"- `{item.get('section_label')} / {item.get('title')}`: 命中 `{item.get('hit_count')}` "
                f"关键词 `{ ' / '.join(item.get('hit_terms', [])[:6]) }`"
            )
        lines.append("")
    asset_coverage = combined.get("asset_coverage", {})
    if asset_coverage:
        lines.append("## 资产覆盖诊断")
        lines.append("")
        lines.append(f"- bridge_rules 数量: `{asset_coverage.get('bridge_rule_count', 0)}`")
        lines.append(f"- 正文命中同桥规则: `{asset_coverage.get('bridge_matched_count', 0)}`")
        lines.append(f"- scene_assets 缺口: `{' / '.join(asset_coverage.get('missing_scene_asset_keys', [])) or '无'}`")
        lines.append(f"- style_assets 缺口: `{' / '.join(asset_coverage.get('missing_style_asset_keys', [])) or '无'}`")
        for item in asset_coverage.get("warnings", [])[:4]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("## 建议")
    lines.append("")
    for rec in recommendations:
        lines.append(f"- {rec}")
    lines.append("")
    return "\n".join(lines)


def markdown_revision_plan(file_path: Path, combined: dict) -> str:
    light_summary = combined["light_summary"]
    heavy_summary = combined["heavy_summary"]
    items = (
        combined["external_block_audit_impact_items"]
        + combined.get("bridge_impact_items", [])
        + combined.get("style_impact_items", [])
        + combined.get("consequence_impact_items", [])
        + combined.get("asset_coverage_impact_items", [])
    )
    items = sorted(items, key=impact_item_priority_tuple, reverse=True)

    lines: list[str] = []
    lines.append("# 内部风险项施工单")
    lines.append("")
    lines.append(f"- 文件: `{file_path}`")
    lines.append(f"- 轻审计命中: `{light_summary['total_hits']}`")
    lines.append(f"- 重审计分数: `{heavy_summary.get('score')}`")
    lines.append(f"- 重审计状态: `{heavy_summary.get('status')}`")
    if combined.get("internal_proxy_summary"):
        lines.append(f"- 内部整体风险分: `{combined['internal_proxy_summary'].get('overall_risk')}`")
        lines.append(f"- 内部最高块风险分: `{combined['internal_proxy_summary'].get('max_block_risk')}`")
        lines.append(f"- 当前判定: `{combined['internal_proxy_summary'].get('judgement', {}).get('label')}`")
    if combined.get("sample_grading_guidance"):
        lines.append(f"- 上游样本等级: `{combined['sample_grading_guidance'].get('level')}`")
    lines.append("")
    lines.append("## 这份单子怎么用")
    lines.append("")
    lines.append("- 先改 `P0`，再改 `P1`。")
    lines.append("- 先改桥段表达秩序，再改句子。")
    lines.append("- 一条改法只解决一类病，不要顺手全文润色。")
    if combined.get("sample_grading_guidance"):
        for item in combined["sample_grading_guidance"].get("hard_stops", [])[:4]:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("## 当前最影响内部过稿判定的部分")
    lines.append("")
    asset_coverage = combined.get("asset_coverage", {})
    if asset_coverage:
        lines.append("### 上游资产命中情况")
        lines.append("")
        lines.append(f"- bridge_rules 数量: `{asset_coverage.get('bridge_rule_count', 0)}`")
        lines.append(f"- 正文命中同桥规则: `{asset_coverage.get('bridge_matched_count', 0)}`")
        lines.append(f"- scene_assets 缺失: `{' / '.join(asset_coverage.get('missing_scene_asset_keys', [])) or '无'}`")
        lines.append(f"- style_assets 缺失: `{' / '.join(asset_coverage.get('missing_style_asset_keys', [])) or '无'}`")
        for item in asset_coverage.get("warnings", [])[:4]:
            lines.append(f"- {item}")
        lines.append("")
    if combined.get("high_risk_segments"):
        segment_scores = combined.get("segment_scores", [])
        raw_segment_scores = combined.get("raw_segment_scores", [])
        paragraph_scores = combined.get("paragraph_scores", [])
        display_block_scores = combined.get("display_block_scores", [])
        block_segments, scatter_segments, point_paragraphs = build_segment_views(segment_scores, paragraph_scores)

        lines.append("### 风险结构总览")
        lines.append("")
        lines.append(f"- 内部微切片: `{len(raw_segment_scores)}`")
        lines.append(f"- 动态风险块: `{len(segment_scores)}`")
        if combined.get("coarse_segment_scores"):
            lines.append(f"- 粗粒度长窗: `{len(combined.get('coarse_segment_scores', []))}`")
        if combined.get("global_risk_shape"):
            shape = combined["global_risk_shape"]
            lines.append(
                f"- 全局形状: `{shape.get('shape')}` / 粗窗离散度 `{shape.get('coarse_score_cv')}` / 高风险段比例 `{shape.get('paragraph_high_ratio')}`"
            )
        lines.append("- 说明: 风险块数量随文本局部高分团变化，不追求固定切成几块。")
        lines.append(f"- 整块风险: `{len(block_segments)}`")
        lines.append(f"- 散点风险: `{len(scatter_segments)}`")
        lines.append("")

        if display_block_scores:
            lines.append("### 先看正文块排行")
            lines.append("")
            for item in sorted(display_block_scores, key=lambda x: x["risk_score"], reverse=True)[:5]:
                flags = " / ".join(item.get("flags", [])[:5]) or "无明显集中标签"
                rulebook_text = " / ".join(item.get("rulebook_flags", [])[:3])
                lines.append(
                    f"- 正文块{item['block_index']}（分数 {item['risk_score']} / 原始段 {item['paragraph_start']}-{item['paragraph_end']} / 风险 {flags}）"
                )
                if rulebook_text:
                    lines.append(f"  - 二层规则: {rulebook_text}")
            lines.append("")

        if block_segments:
            lines.append("### 先改这些整块风险")
            lines.append("")
            for item in block_segments[:5]:
                flags = item.get("style_flags", []) + item.get("bridge_flags", []) + item.get("consequence_flags", [])
                hotspot_text = "；".join(
                    f"段落{hot['paragraph_index']} {hot['risk_score']}"
                    for hot in item.get("hotspot_paragraphs", [])[:3]
                ) or "无明显单点热点"
                lines.append(
                    f"- 片段{item['segment_index']}（{block_label(item)} / 原始段 {item['paragraph_start']}-{item['paragraph_end']} / 分数 {item['risk_score']} / 热点 {hotspot_text}）"
                )
                if flags:
                    lines.append(f"  - 风险标签: {' / '.join(flags[:6])}")
                if item.get("rulebook_flags"):
                    lines.append(f"  - 二层规则: {' / '.join(item.get('rulebook_flags', [])[:4])}")
                lines.append(f"  - 片段摘录: {item.get('excerpt', '')}")
            lines.append("")

        if scatter_segments:
            lines.append("### 再处理这些散点风险")
            lines.append("")
            for item in scatter_segments[:6]:
                flags = item.get("style_flags", []) + item.get("bridge_flags", []) + item.get("consequence_flags", [])
                shape_name = "单点" if item.get("shape") == "point" else "散段"
                lines.append(
                    f"- {shape_name}片段{item['segment_index']}（{block_label(item)} / 原始段 {item['paragraph_start']}-{item['paragraph_end']} / 分数 {item['risk_score']}）"
                )
                if flags:
                    lines.append(f"  - 风险标签: {' / '.join(flags[:6])}")
                if item.get("rulebook_flags"):
                    lines.append(f"  - 二层规则: {' / '.join(item.get('rulebook_flags', [])[:4])}")
                lines.append(f"  - 片段摘录: {item.get('excerpt', '')}")
            lines.append("")

        if point_paragraphs:
            lines.append("### 最后捡这些段落热点")
            lines.append("")
            for item in point_paragraphs[:8]:
                flags = " / ".join(item.get("flags", [])[:4]) or "局部风险聚集"
                lines.append(f"- 原始段{item['paragraph_index']}（正文块{item.get('display_block_index', '?')}） / 分数 {item['risk_score']} / 原因 {flags}")
        lines.append("")
    if not items:
        lines.append("- 当前报告没有足够证据自动生成施工单，先看 `full_audit.md` 的高风险命中。")
        lines.append("")
        return "\n".join(lines)

    for idx, item in enumerate(items, start=1):
        lines.append(f"### {idx}. {item['title']}（{item['priority']}）")
        lines.append("")
        lines.append(f"- 为什么会被打: {item['why_it_hits_audit']}")
        if item.get("sample_bias_note"):
            lines.append(f"- 样本等级调度: {item['sample_bias_note']}")
        if item.get("evidence"):
            lines.append("- 本稿证据:")
            for ev in item["evidence"]:
                lines.append(f"  - {ev}")
        if item.get("fix_methods"):
            lines.append("- 修改方法:")
            for method in item["fix_methods"]:
                lines.append(f"  - {method}")
        lines.append("")

    lines.append("## 固定改稿顺序")
    lines.append("")
    for step in [
        "先处理开头 1200 字的成品感。",
        "再补人物偏手、微动作、烂关系漏出这些真人承重层。",
        "再拆对白高效块和单场戏功能堆叠。",
        "最后再删句壳、热点重复和段长匀速块。",
    ]:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="待审计文本文件")
    parser.add_argument(
        "--output-dir",
        default="audit_reports",
        help="输出目录，默认 audit_reports",
    )
    parser.add_argument(
        "--myconfig-root",
        help="可选：外部上游规则源根目录；不传时默认使用 skill 内 scripts/audit_ai_flavor.py 与 references/governance/通用高风险词类词典.json",
    )
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="运行项目内轻审计使用的 python，默认当前解释器",
    )
    parser.add_argument(
        "--profile",
        help="可选：project/book profile JSON。用于接入同桥段过检规则与题材资产。",
    )
    parser.add_argument(
        "--internal-standard",
        help="可选：内部审计标准 JSON。日常审计与回炉优先使用这份文件。",
    )
    parser.add_argument(
        "--external-block-audit-alignment-summary",
        help="外部分块审计对标摘要 JSON。会自动转成内部标准使用。",
    )
    parser.add_argument(
        "--audit-rulebook",
        help="可选：外置改稿规则簿 JSON。默认读取 skill/references/governance/audit-rulebook.json。",
    )
    args = parser.parse_args()

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"文件不存在: {file_path}", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    light_script = root / "scripts" / "audit_novel_ai_flavor.py"
    rulebook_path = Path(args.audit_rulebook).resolve() if args.audit_rulebook else root / "references" / "audit-rulebook.json"
    if args.myconfig_root:
        heavy_root = Path(args.myconfig_root).resolve()
        heavy_script = heavy_root / "脚本" / "audit_ai_flavor.py"
        heavy_lexicon = heavy_root / "词典" / "通用高风险词类词典.json"
    else:
        heavy_script = root / "scripts" / "audit_ai_flavor.py"
        heavy_lexicon = root / "references" / "governance" / "通用高风险词类词典.json"

    if not light_script.exists():
        print(f"轻审计脚本不存在: {light_script}", file=sys.stderr)
        return 2
    if not heavy_script.exists():
        print(f"重审计脚本不存在: {heavy_script}", file=sys.stderr)
        return 2
    if not heavy_lexicon.exists():
        print(f"重审计词典不存在: {heavy_lexicon}", file=sys.stderr)
        return 2

    profile_path = Path(args.profile).resolve() if args.profile else None
    profile = load_profile(profile_path) if profile_path else {}
    rulebook = load_audit_rulebook(rulebook_path) if rulebook_path.exists() else {}
    internal_standard_path = Path(args.internal_standard).resolve() if args.internal_standard else None
    calibration_path = Path(args.external_block_audit_alignment_summary).resolve() if args.external_block_audit_alignment_summary else None
    standard_path = internal_standard_path or calibration_path
    internal_standard = normalize_internal_standard(load_json_file(standard_path)) if standard_path else {}

    try:
        light_report = run_light_audit(file_path, args.python_bin, light_script, profile_path)
        heavy_report = run_heavy_audit(file_path, heavy_script, heavy_lexicon)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    source_text = file_path.read_text(encoding="utf-8")
    sample_grading_guidance = build_sample_grading_guidance(profile)
    recommendations = build_recommendations(light_report, heavy_report)
    bridge_audit = bridge_rule_audit(source_text, profile)
    consequence_audit = consequence_chain_audit(source_text, profile)
    style_audits = build_style_audits(source_text, profile, light_report)
    asset_coverage = audit_profile_asset_coverage(profile, bridge_audit, consequence_audit, style_audits)
    recommendations.extend(build_bridge_recommendations(bridge_audit))
    recommendations.extend(build_consequence_recommendations(consequence_audit))
    recommendations.extend(build_style_recommendations(style_audits))
    recommendations.extend(asset_coverage.get("warnings", []))
    recommendations.extend(build_sample_grading_recommendations(sample_grading_guidance))
    rulebook_audit = audit_external_rulebook(source_text, rulebook)
    recommendations.extend(build_rulebook_recommendations(rulebook_audit))
    external_block_audit_impact_items = [
        apply_sample_grading_item_bias(item, sample_grading_guidance)
        for item in build_external_block_audit_impact_items(light_report, summarize_heavy(heavy_report) | heavy_report)
    ]
    bridge_impact_items = [
        apply_sample_grading_item_bias(item, sample_grading_guidance)
        for item in build_bridge_impact_items(bridge_audit)
    ]
    consequence_impact_items = [
        apply_sample_grading_item_bias(item, sample_grading_guidance)
        for item in build_consequence_impact_items(consequence_audit)
    ]
    style_impact_items = [
        apply_sample_grading_item_bias(item, sample_grading_guidance)
        for item in build_style_impact_items(style_audits, light_report)
    ]
    asset_coverage_impact_items = [
        apply_sample_grading_item_bias(item, sample_grading_guidance)
        for item in build_asset_coverage_impact_items(asset_coverage, sample_grading_guidance)
    ]
    rulebook_impact_items = [
        apply_sample_grading_item_bias(item, sample_grading_guidance)
        for item in build_rulebook_impact_items(rulebook_audit)
    ]
    display_blocks, paragraphs, raw_segment_scores, segment_scores, paragraph_scores, high_risk_segments, coarse_segment_scores = score_segments(
        source_text=source_text,
        file_suffix=file_path.suffix or ".txt",
        profile=profile,
        profile_path=profile_path,
        rulebook=rulebook,
        python_bin=args.python_bin,
        light_script=light_script,
        heavy_script=heavy_script,
        heavy_lexicon=heavy_lexicon,
        full_light_report=light_report,
        full_style_audits=style_audits,
    )
    display_block_scores = build_display_block_scores(display_blocks, raw_segment_scores, paragraph_scores)
    global_risk_shape = build_global_risk_shape(
        source_text,
        summarize_heavy(heavy_report),
        coarse_segment_scores,
        display_block_scores,
        paragraph_scores,
    )

    combined = {
        "file": str(file_path),
        "profile": str(profile_path) if profile_path else None,
        "profile_payload": profile,
        "light_report": light_report,
        "light_summary": summarize_light(light_report),
        "heavy_report": heavy_report,
        "heavy_summary": summarize_heavy(heavy_report),
        "recommendations": recommendations,
        "sample_grading_guidance": sample_grading_guidance,
        "external_block_audit_impact_items": external_block_audit_impact_items,
        "bridge_rule_audit": bridge_audit,
        "bridge_impact_items": bridge_impact_items,
        "consequence_chain_audit": consequence_audit,
        "consequence_impact_items": consequence_impact_items,
        "style_audits": style_audits,
        "style_impact_items": style_impact_items,
        "rulebook": str(rulebook_path) if rulebook else None,
        "rulebook_audit": rulebook_audit,
        "rulebook_impact_items": rulebook_impact_items,
        "asset_coverage": asset_coverage,
        "asset_coverage_impact_items": asset_coverage_impact_items,
        "paragraphs": [
            {k: item[k] for k in ("paragraph_index", "start_char", "end_char", "char_count")}
            for item in paragraphs
        ],
        "display_blocks": display_blocks,
        "display_block_scores": display_block_scores,
        "raw_segment_scores": raw_segment_scores,
        "segment_scores": segment_scores,
        "paragraph_scores": paragraph_scores,
        "high_risk_segments": high_risk_segments,
        "coarse_segment_scores": coarse_segment_scores,
        "global_risk_shape": global_risk_shape,
    }
    if internal_standard:
        combined["internal_proxy_summary"] = build_internal_proxy_summary(
            combined,
            combined["heavy_summary"],
            internal_standard,
        )
        combined["internal_standard"] = str(standard_path)
        combined["external_block_audit_proxy_summary"] = combined["internal_proxy_summary"]
        if calibration_path:
            combined["external_block_audit_alignment_summary"] = str(calibration_path)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = file_path.stem
    json_path = output_dir / f"{stem}.full_audit.json"
    md_path = output_dir / f"{stem}.full_audit.md"
    plan_path = output_dir / f"{stem}.revision_plan.md"
    json_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown_report(file_path, light_report, heavy_report, recommendations, combined), encoding="utf-8")
    plan_path.write_text(markdown_revision_plan(file_path, combined), encoding="utf-8")

    print(f"已输出:")
    print(f"- {json_path}")
    print(f"- {md_path}")
    print(f"- {plan_path}")
    print(f"轻审计命中: {combined['light_summary']['total_hits']}")
    print(f"重审计分数: {combined['heavy_summary'].get('score')}")
    print(f"重审计状态: {combined['heavy_summary'].get('status')}")
    if combined.get("internal_proxy_summary"):
        print(f"内部整体风险分: {combined['internal_proxy_summary'].get('overall_risk')}")
        print(f"内部最高块风险分: {combined['internal_proxy_summary'].get('max_block_risk')}")
        print(f"内部过稿判定: {combined['internal_proxy_summary'].get('judgement', {}).get('label')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
