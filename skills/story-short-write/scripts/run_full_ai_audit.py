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
import hashlib
import json
import re
import statistics
import subprocess
import sys
import tempfile
import importlib.util
from pathlib import Path

try:
    from count_words import count_fanqie
except ModuleNotFoundError:
    _count_words_path = Path(__file__).with_name("count_words.py")
    _count_words_spec = importlib.util.spec_from_file_location(
        "story_short_write_count_words",
        _count_words_path,
    )
    if not _count_words_spec or not _count_words_spec.loader:
        raise
    _count_words_module = importlib.util.module_from_spec(_count_words_spec)
    _count_words_spec.loader.exec_module(_count_words_module)
    count_fanqie = _count_words_module.count_fanqie

try:
    from validate_pre_window_revision_gate import (
        validate as validate_pre_window_revision,
    )
except ModuleNotFoundError:
    _pre_window_path = Path(__file__).with_name("validate_pre_window_revision_gate.py")
    _pre_window_spec = importlib.util.spec_from_file_location(
        "story_short_write_pre_window_revision_gate",
        _pre_window_path,
    )
    if not _pre_window_spec or not _pre_window_spec.loader:
        raise
    _pre_window_module = importlib.util.module_from_spec(_pre_window_spec)
    _pre_window_spec.loader.exec_module(_pre_window_module)
    validate_pre_window_revision = _pre_window_module.validate

try:
    from validate_sequence_contract import (
        validate as validate_sequence_contract,
    )
except ModuleNotFoundError:
    _sequence_path = Path(__file__).with_name("validate_sequence_contract.py")
    _sequence_spec = importlib.util.spec_from_file_location(
        "story_short_write_sequence_contract",
        _sequence_path,
    )
    if not _sequence_spec or not _sequence_spec.loader:
        raise
    _sequence_module = importlib.util.module_from_spec(_sequence_spec)
    _sequence_spec.loader.exec_module(_sequence_module)
    validate_sequence_contract = _sequence_module.validate


def legacy_external_audit_key(suffix: str) -> str:
    return "".join(["zh", "uque_", suffix])


MICRO_SEGMENT_TARGET_CHARS = 260
MICRO_SEGMENT_MIN_CHARS = 180
MICRO_SEGMENT_MAX_CHARS = 340
COARSE_SEGMENT_TARGET_CHARS = 2600
COARSE_SEGMENT_MIN_CHARS = 1800
COARSE_SEGMENT_MAX_CHARS = 3600
RHYTHM_WINDOW_TARGET_CHARS = 1600
RHYTHM_WINDOW_MIN_CHARS = 900

MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")
NARRATOR_PULSE_RE = re.compile(
    r"(难为|原来(?!的)|果然|当然|算了|罢了|白想|没出息|丢人|有病|荒唐|可笑|"
    r"真(?:行|好|巧|细心|认真|恶心|够)|挺(?:好|行|认真|可笑)|"
    # 叙述者声明不知道 / 认知局限——对朱雀困惑度贡献最强
    r"我不知道|说不清|想不明白|至今(?:也|没)|说不准|弄不明白|"
    r"不知道为什么|莫名(?:其妙)?|说不上来|说不出原因|"
    # 通用自问结构（不绑定具体故事措辞）
    r"我(?:图什么|还能怎么办|怎么会|凭什么|算什么|能怎样)|"
    # 补充评价词
    r"没意思|有意思(?!的)|好笑|可惜了|倒也|说来|其实吧|说真的)"
)
DIALOGUE_SPAN_RE = re.compile(
    r'("[^"\n]*"|“[^”\n]*”|「[^」\n]*」|『[^』\n]*』)'
)


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
    structure_grade = str(grading.get("structure_grade", "")).upper()
    performance_grade = str(grading.get("performance_grade", "")).upper()
    sentence_grade = str(grading.get("sentence_grade", "")).upper()
    terminal_grade = str(grading.get("terminal_consequence_grade", "")).upper()
    positive_dna_layers = grading.get("positive_dna_layers", [])
    skeleton_only_layers = grading.get("skeleton_only_layers", [])
    negative_rule_layers = grading.get("negative_rule_layers", [])
    present_layer_grades = [
        grade for grade in (structure_grade, performance_grade, sentence_grade, terminal_grade)
        if grade in {"A", "B", "C"}
    ]
    all_layers_negative = bool(present_layer_grades) and all(
        grade == "C" for grade in present_layer_grades
    )
    effective_dna_usable = source_buckets.get("effective_dna_usable")
    if not isinstance(effective_dna_usable, str) or not effective_dna_usable.strip():
        effective_dna_usable = raw_dna_usable
    dna_usable = effective_dna_usable
    notes: list[str] = []
    if raw_level and raw_level != level:
        notes.append(f"融合包原始最严等级为 `{raw_level}`，但有效写作等级按来源分桶修正为 `{level}`。")
    if level == "B类骨架样本" and sentence_grade != "A":
        notes.append("当前 profile 标记为 `B类骨架样本`：只学骨架、承重件、后果链、场面秩序，不学现成句法壳。")
    elif level == "C类负样本" and (not present_layer_grades or all_layers_negative):
        notes.append("当前 profile 标记为 `C类负样本`：只可用于反面规则和禁写提醒，不可并入正向融合。")
    elif level == "C类负样本":
        notes.append("整书摘要为 `C类负样本`，但存在非 C 分层；实际调用服从四层 grade，不做整书一刀切。")
    elif level == "A类正样本":
        notes.append("当前 profile 标记为 `A类正样本`：可提句法、口气、动作落点和桥段承重件。")
    if isinstance(raw_dna_usable, str) and raw_dna_usable and raw_dna_usable != dna_usable:
        notes.append(f"融合包原始 DNA 可用性为 `{raw_dna_usable}`，但实际写作按 `{dna_usable}` 处理。")
    if isinstance(dna_usable, str) and dna_usable:
        notes.append(f"DNA 提取可用性：`{dna_usable}`。")
    if any((structure_grade, performance_grade, sentence_grade, terminal_grade)):
        notes.append(
            "分层样本等级："
            f"结构={structure_grade or '未知'} / 表演={performance_grade or '未知'} / "
            f"句法={sentence_grade or '未知'} / 终局后果={terminal_grade or '未知'}。"
        )
    if isinstance(positive_dna_layers, list) and positive_dna_layers:
        notes.append(f"正向 DNA 层：`{' / '.join(positive_dna_layers[:6])}`。")
    if isinstance(skeleton_only_layers, list) and skeleton_only_layers:
        notes.append(f"仅骨架层：`{' / '.join(skeleton_only_layers[:6])}`。")
    if isinstance(negative_rule_layers, list) and negative_rule_layers:
        notes.append(f"反面规则层：`{' / '.join(negative_rule_layers[:6])}`。")
    effective_allow_dna = source_buckets.get("effective_allow_dna")
    if not isinstance(effective_allow_dna, str):
        effective_allow_dna = ""
    if isinstance(final_verdict, dict):
        allow_dna_value = effective_allow_dna or final_verdict.get("allow_dna")
        if allow_dna_value in ("否", "不可") and sentence_grade != "A":
            notes.append("这份样本不允许直接当句法 DNA 源使用。")
        if final_verdict.get("negative_only") == "是" and (
            not present_layer_grades or all_layers_negative
        ):
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
    if level == "B类骨架样本" and sentence_grade != "A":
        hard_stops.append("不要把这份参考稿的现成句法壳、总结句和整齐翻刀链当成可继承 DNA。")
    if level == "C类负样本" and (not present_layer_grades or all_layers_negative):
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
        "structure_grade": structure_grade,
        "performance_grade": performance_grade,
        "sentence_grade": sentence_grade,
        "terminal_consequence_grade": terminal_grade,
        "positive_dna_layers": positive_dna_layers if isinstance(positive_dna_layers, list) else [],
        "skeleton_only_layers": skeleton_only_layers if isinstance(skeleton_only_layers, list) else [],
        "negative_rule_layers": negative_rule_layers if isinstance(negative_rule_layers, list) else [],
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


def clean_excerpt(text: str, limit: int = 68) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def trim_evidence_label(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"^[A-Za-z0-9_一-龥]+[:：]\s*", "", text.strip(), count=1)
    return text.strip()


def item_title_matches(item: dict, *keywords: str) -> bool:
    title = str(item.get("title", ""))
    return any(keyword in title for keyword in keywords)


RELATION_FEELING_RULES = [
    {
        "name": "针锋相对",
        "when": "双方都在抢定义权，句子互顶，谁也不肯退到解释位。",
        "title_keywords": ("烂关系",),
        "flag_keywords": ("高效对白块",),
    },
    {
        "name": "假冷静",
        "when": "表面压住声量，但句子功能极强，冷静只是外壳。",
        "title_keywords": ("开头成品感", "对白效率", "人物偏手"),
        "flag_keywords": ("高效对白块", "开头承压"),
    },
    {
        "name": "压着说",
        "when": "人物不正面爆，但一直抢节奏、抢结论、抢现场秩序。",
        "title_keywords": ("对白", "人物偏手"),
        "flag_keywords": ("高效对白块",),
    },
    {
        "name": "被迫解释",
        "when": "一方始终被推到答辩位，只能不停补理由、补证据、补流程。",
        "title_keywords": ("开头成品感", "流程件", "对白"),
        "flag_keywords": ("说明句偏强",),
    },
    {
        "name": "旧账对冲",
        "when": "人物说的不是眼前这件事，而是在拿过去的亏欠互相抵消。",
        "title_keywords": ("烂关系",),
        "flag_keywords": (),
    },
    {
        "name": "关系掉位",
        "when": "名义上的位置还在，但现场权限、边缘站位和默认顺序已经变了。",
        "title_keywords": ("人物偏手", "烂关系"),
        "flag_keywords": ("多资产挤压",),
    },
    {
        "name": "关系先被盖章",
        "when": "还没让读者看到关系自己漏出来，文本先替人物下了定性。",
        "title_keywords": ("开头成品感", "作者替角色下结论"),
        "flag_keywords": ("说明句偏强", "开头承压"),
    },
    {
        "name": "一方在压场，一方在守边界",
        "when": "一方主攻现场秩序和话语节奏，另一方只守住最低边界不让步。",
        "title_keywords": ("人物偏手", "流程件"),
        "flag_keywords": ("高效对白块", "说明句偏强"),
    },
    {
        "name": "对压没接上",
        "when": "人物开口了，但没有形成盯视、停顿、回避、顶回去这类真实接招，只剩孤立台词。",
        "title_keywords": ("没有交流", "交流感缺失"),
        "flag_keywords": (),
    },
    {
        "name": "作者代替交流",
        "when": "本该落在视线、停顿和接话里的压力，被作者一句解释提前包办了。",
        "title_keywords": ("没有交流", "作者替角色下结论"),
        "flag_keywords": ("说明句偏强",),
    },
]


OPENING_SUBCAUSE_LIBRARY = [
    {
        "name": "信息揭露链太顺",
        "why": "首屏把事故、关系、证据、程序和结论排成顺滑链条，读者没有参与追问的空间。",
        "signals": ("opening_signature_risks", "opening_reveal_chain"),
        "fix": "首屏只留事故和第二推进点，关系和证据错后半拍再漏。",
    },
    {
        "name": "对白太快对题",
        "why": "人物开口就解决主问题，缺回避、打岔、压声和现场阻隔。",
        "signals": ("over_effective_dialogue_blocks",),
        "fix": "拆掉最会解释关系的那句，换成控场句、回避句或手续句。",
    },
    {
        "name": "作者先替关系盖章",
        "why": "人还在现场承受，作者已经先总结意义和关系，成品感会立刻升高。",
        "signals": ("author_verdict", "theme_explanation", "direct_mental_state"),
        "fix": "删掉总结句，把关系定性退回动作、走位、停顿和后果里。",
    },
    {
        "name": "首屏物件全都在服务主线",
        "why": "每个物件一出场都直接对题，会像精修过的成品钩子，不像生活现场。",
        "signals": ("opening_metrics",),
        "fix": "首屏只让一个物件承担主功能，其他物件先做噪音和阻力。",
    },
]


EXCHANGE_LAYER_CUES = {
    "视线压力": [
        "看着我", "看着他", "看着她",
        "盯着我", "盯着他", "盯着她",
        "看了我一眼", "看了他一眼", "看了她一眼",
        "没看我", "没看他", "没看她", "避开了我的眼睛",
        "抬头", "低头", "先看了一眼", "目光偏了一下",
    ],
    "肢体摩擦": [
        "抓住", "攥住", "拽住", "扯住", "扣住", "按住",
        "推开", "挥开", "甩开", "撞到", "撞上", "碰到",
        "挡住", "拦住", "退开半步", "抓住我的手腕",
        "从我指间抽走", "手停在半空",
    ],
    "物件摩擦": [
        "抽出来", "推过去", "推回来", "递给他", "递给我",
        "摔在", "砸在", "扔在", "撕开", "扯裂", "折断",
        "抢走", "抽走", "夺过", "掀翻", "踩碎", "摔裂",
        "扣在桌上", "压在桌上", "按平", "翻了个面",
    ],
    "空间压力": [
        "堵在门口", "挡在门口", "拦在门口", "站到中间",
        "退到黄色安全线外", "退到安全线外", "站到了黄线外面",
        "逼到墙边", "抵在墙边", "关上门", "锁了门",
        "拉到白板另一边", "挡着外面的视线", "往前追了两步",
    ],
    "节奏接招": [
        "顿了半秒", "顿了一下", "停了", "没有立刻接话",
        "没立刻再问", "没接", "接话", "打断", "咽了回去",
        "声音压得很低", "把声音压得更低", "没再问",
        "说到一半", "没答", "没回头", "没再往下接",
    ],
    "身份压力": [
        "移出", "停用权限", "暂停权限", "无此人员", "收走钥匙",
        "撤销权限", "临时管理员", "责任栏", "审批人", "申请人",
        "见证人", "交接单", "离场单", "撤签", "管理员钥匙",
    ],
}


CONFLICT_CARRIER_CUES = {
    "dialogue": ["“", "\""],
    "body": EXCHANGE_LAYER_CUES["肢体摩擦"],
    "object": EXCHANGE_LAYER_CUES["物件摩擦"],
    "space": EXCHANGE_LAYER_CUES["空间压力"],
    "identity": EXCHANGE_LAYER_CUES["身份压力"],
}


STRONG_CONFLICT_CUES = [
    "争", "吵", "质问", "逼问", "冲突", "失控", "撤签", "离婚",
    "辞职", "停用权限", "无此人员", "报警", "封存", "追偿",
    "抓住", "拽住", "推开", "摔在", "砸在", "扯裂", "抢走",
]


IRREVERSIBLE_VIOLENCE_CUES = [
    "扇了我", "扇了她", "打了我", "打了她", "一巴掌",
    "掐住脖子", "踹了我", "踹了她", "拳头砸在我",
]


CONFLICT_REVIEW_CARRIERS = {
    "dialogue",
    "body",
    "object",
    "space",
    "identity",
    "rhythm",
}


VIOLENCE_REVIEW_DECISIONS = {
    "absent",
    "aligned_irredeemable",
    "revised",
}


EXCHANGE_CHANGED_TARGETS = {
    "action",
    "position",
    "object",
    "answer_scope",
    "identity",
    "consequence",
}


PROCEDURAL_STIFFNESS_PROBLEM_TYPES = {
    "workflow_log_feel",
    "evidence_inventory_feel",
    "triple_status_receipt",
    "procedure_too_smooth",
    "multi_task_sentence",
    "character_reaction_replaced_by_process",
    "insufficient_scene_resistance",
    "storyboard_or_construction_list",
    "none_found",
}


EXCHANGE_AUTHOR_SUBSTITUTE_CUES = [
    "谁都该自己接上",
    "这口气我太熟了",
    "先压扩散，后补责任",
    "这才像追妻",
    "像是后半句",
    "像是他自己都知道",
]


def collect_exchange_layers(text: str) -> dict[str, list[str]]:
    return {
        layer: collect_term_hits(text, cues, limit=8)
        for layer, cues in EXCHANGE_LAYER_CUES.items()
    }


def collect_item_flags(item: dict, combined: dict) -> list[str]:
    flags = []
    for text in find_related_paragraph_evidence(item, combined, 4):
        parts = [part.strip() for part in text.split("/") if part.strip()]
        if len(parts) >= 3:
            flags.extend([part.strip() for part in parts[2].split(" / ") if part.strip()])
    return normalize_terms(flags)


def build_relation_feelings(item: dict, combined: dict) -> list[dict]:
    title = str(item.get("title", ""))
    flags = collect_item_flags(item, combined)
    matches: list[dict] = []
    for rule in RELATION_FEELING_RULES:
        if any(keyword in title for keyword in rule.get("title_keywords", ())):
            matches.append({"name": rule["name"], "when": rule["when"]})
            continue
        if any(keyword in flags for keyword in rule.get("flag_keywords", ())):
            matches.append({"name": rule["name"], "when": rule["when"]})
    if not matches:
        fallback = infer_relation_tags(item)
        return [{"name": name, "when": "当前命中更接近这类关系气味，需要回到正文确认站位和说话方式。"} for name in fallback]
    deduped: list[dict] = []
    seen = set()
    for item_data in matches:
        name = item_data["name"]
        if name in seen:
            continue
        seen.add(name)
        deduped.append(item_data)
    return deduped[:5]


def build_opening_subcauses_from_library(light_report: dict) -> list[dict]:
    opening_metrics = light_report.get("opening_metrics", {})
    subcauses: list[dict] = []
    for spec in OPENING_SUBCAUSE_LIBRARY:
        evidence: list[str] = []
        for signal in spec.get("signals", ()):
            if signal == "opening_signature_risks":
                evidence.extend(
                    f"{it.get('type')}: {it.get('detail')}" for it in light_report.get("opening_signature_risks", [])[:2]
                )
            elif signal == "opening_reveal_chain":
                evidence.extend(f"翻刀链: {it}" for it in light_report.get("opening_reveal_chain", [])[:2])
            elif signal == "over_effective_dialogue_blocks":
                evidence.extend(
                    f"L{it.get('line')} 段{it.get('paragraph_index')}: {it.get('detail')}"
                    for it in light_report.get("over_effective_dialogue_blocks", [])[:2]
                )
            elif signal == "author_verdict":
                evidence.extend(sample_lines_by_type(light_report, "author_verdict", 2))
            elif signal == "theme_explanation":
                evidence.extend(sample_lines_by_type(light_report, "theme_explanation", 2))
            elif signal == "direct_mental_state":
                evidence.extend(sample_lines_by_type(light_report, "direct_mental_state", 1))
            elif signal == "opening_metrics":
                dialogue_count = opening_metrics.get("dialogue_count", 0)
                single_ratio = opening_metrics.get("single_sentence_ratio", 0)
                if dialogue_count:
                    evidence.append(f"开头1200字对话数 {dialogue_count}")
                if single_ratio:
                    evidence.append(f"开头1200字单句段占比 {single_ratio}")
        clean_evidence = normalize_terms([trim_evidence_label(ev) for ev in evidence if trim_evidence_label(ev)])
        if not clean_evidence:
            continue
        subcauses.append(
            {
                "label": spec["name"],
                "trigger": spec["why"],
                "evidence": clean_evidence[:3],
                "fix": spec["fix"],
            }
        )
    return subcauses


def find_related_paragraph_evidence(item: dict, combined: dict, limit: int = 3) -> list[str]:
    paragraph_scores = combined.get("paragraph_scores", [])
    title = str(item.get("title", ""))
    focus_layer = str(item.get("focus_layer", ""))
    scored: list[tuple[float, str]] = []

    for para in paragraph_scores:
        flags = para.get("flags", [])
        excerpt = clean_excerpt(para.get("excerpt", ""))
        if not excerpt:
            continue
        score = float(para.get("risk_score", 0))
        if "开头成品感过高" in title:
            if para.get("paragraph_index", 999) <= 4:
                score += 30
            if "开头承压" in flags:
                score += 12
            if "说明句偏强" in flags:
                score += 8
        if "流程件和证据件摆放过整齐" in title:
            if "说明句偏强" in flags:
                score += 14
            if "单场戏功能过多" in flags:
                score += 10
        if "人物偏手没有立住" in title:
            if "多资产挤压" in flags:
                score += 10
            if "高效对白块" in flags:
                score += 8
        if "烂关系没有自己漏出来" in title:
            if "多资产挤压" in flags:
                score += 8
            if "说明句偏强" in flags:
                score += 8
        if "对白" in title:
            if "高效对白块" in flags:
                score += 18
            if "短段对白密" in flags:
                score += 8
        if "作者替角色下结论" in title and "说明句偏强" in flags:
            score += 16
        if focus_layer == "scene_order" and "单场戏功能过多" in flags:
            score += 12
        if focus_layer == "sentence_shell" and "说明句偏强" in flags:
            score += 12
        if focus_layer == "dialogue_polish" and "高效对白块" in flags:
            score += 10
        if focus_layer == "character_reaction" and "多资产挤压" in flags:
            score += 6
        if score <= 0:
            continue
        scored.append(
            (
                score,
                f"原始段{para.get('paragraph_index')} / 风险 {para.get('risk_score')} / {' / '.join(flags[:4]) or '局部承压'} / {excerpt}",
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    return normalize_terms([text for _, text in scored[:limit]])


def infer_relation_tags(item: dict) -> list[str]:
    title = str(item.get("title", ""))
    tags: list[str] = []
    if "开头成品感过高" in title:
        tags.extend(["假冷静", "关系先被盖章", "被迫解释"])
    if "流程件和证据件摆放过整齐" in title:
        tags.extend(["答辩感", "被迫解释", "一方压场一方接招"])
    if "人物偏手没有立住" in title:
        tags.extend(["一方在压场，一方在守边界", "假冷静", "关系掉位"])
    if "烂关系没有自己漏出来" in title:
        tags.extend(["针锋相对", "旧账对冲", "掉位但还想维持体面"])
    if "对白效率过高" in title or "对白缺失控层" in title or "对白衔接过直" in title:
        tags.extend(["压着说", "被迫解释", "假冷静"])
    if "人物开口了，但没有交流" in title:
        tags.extend(["对压没接上", "作者代替交流", "假冷静"])
    if "作者替角色下结论" in title:
        tags.extend(["关系被作者代判", "现场还没炸完就先定性"])
    if "情绪没有落进微动作" in title:
        tags.extend(["话在前，身子在后", "表情绪，不表关系"])
    if not tags:
        focus_layer = str(item.get("focus_layer", ""))
        fallback = {
            "scene_order": ["场面被整理过", "关系被秩序盖掉"],
            "character_reaction": ["关系先靠反应漏出", "不要先讲道理"],
            "dialogue_polish": ["话太直", "人物太会接招"],
            "sentence_shell": ["作者口先跑到前面"],
        }
        tags.extend(fallback.get(focus_layer, ["关系气味偏说明层"]))
    return normalize_terms(tags)


def build_subcauses(item: dict, combined: dict) -> list[dict]:
    light_report = combined.get("light_report", {})
    style_audits = combined.get("style_audits", {})
    line_types = light_report.get("line_hit_types", {})
    subcauses: list[dict] = []

    def add(label: str, trigger: str, evidence: list[str], fix: str) -> None:
        clean_evidence = normalize_terms([trim_evidence_label(ev) for ev in evidence if trim_evidence_label(ev)])
        if not clean_evidence:
            return
        subcauses.append(
            {
                "label": label,
                "trigger": trigger,
                "evidence": clean_evidence[:3],
                "fix": fix.strip(),
            }
        )

    if item_title_matches(item, "开头成品感过高"):
        subcauses.extend(build_opening_subcauses_from_library(light_report))

    if item_title_matches(item, "流程件和证据件摆放过整齐"):
        add(
            "证据像案卷一样连续宣读",
            "时间线、证据链、程序节点排得太工整，会有答辩稿味。",
            [item.get("why_it_hits_audit", "")] + item.get("evidence", [])[:3],
            "让证据分两次以上漏出，中间插入翻找、打断、质疑和迟滞。",
        )
        add(
            "手续流不卡壳",
            "流程只负责推进，不负责制造阻力，场面就会被看成整理后的说明件。",
            find_related_paragraph_evidence(item, combined, 2),
            "把程序动作改成有人拦、有人催、有人插话，别一路顺着宣读完。",
        )

    if item_title_matches(item, "人物偏手没有立住"):
        add(
            "人物先说对的话，没先做本能反应",
            "核心人物缺少稳定的第一反应手势，只剩功能型发言。",
            ["人物偏手命中不足"] + find_related_paragraph_evidence(item, combined, 2),
            "先写谁压场、谁守边界、谁先收东西，再补解释句。",
        )
        dialogue_count = style_audits.get("meltdown_dialogue_audit", {}).get("dialogue_count", 0)
        explanation_evidence = find_related_paragraph_evidence(item, combined, 2)
        if dialogue_count:
            explanation_evidence = [f"对白数 {dialogue_count}"] + explanation_evidence
        add(
            "理亏方太会解释",
            "理亏角色如果直接给标准答案，关系张力会塌成作者控场。",
            explanation_evidence + item.get("evidence", [])[:1],
            "让理亏方先绕、先拖、先压程序，不要马上答题。",
        )

    if item_title_matches(item, "人物开口了，但没有交流"):
        exchange_issues = exchange_manual_failures(
            style_audits.get("exchange_audit", {})
        )
        author_substitute_hits = style_audits.get("exchange_audit", {}).get("author_substitute_hits", [])
        issue_evidence = [
            f"{entry.get('scene')} / {entry.get('judgment')}"
            for entry in exchange_issues[:3]
        ]
        add(
            "只有台词，没有接招",
            "人物说了话，但现场没有形成对视、停顿、压声、顶回去这些真正的交流动作。",
            issue_evidence,
            "给关键台词后面补一个被迫接招的动作，不一定回嘴，但一定要让压力落到人身上。",
        )
        add(
            "作者解释抢走了交流位",
            "本该让读者从人和人的反应里读出来的气味，被作者一句概括提前说完了。",
            author_substitute_hits[:3] + sample_lines_by_type(light_report, "author_verdict", 1) + sample_lines_by_type(light_report, "theme_explanation", 1),
            "删掉那句解释，把它拆成视线、停住、没接话、改口或转去压程序。",
        )

    if item_title_matches(item, "烂关系没有自己漏出来"):
        add(
            "关系主要靠旧账复述",
            "坏关系没有先从空间、权限、默认反应里漏出来，只能靠台词解释。",
            ["烂关系漏出资产命中不足"] + find_related_paragraph_evidence(item, combined, 2),
            "把坏关系改写成门口、座位、登记口、物件归属和谁先被晾着。",
        )
        add(
            "掉位感不够具体",
            "读者没法一眼看出谁被挤到边上、谁默认有权限，关系就还是抽象的。",
            item.get("fix_methods", [])[:2],
            "别再加旧账总结，直接补谁站外圈、谁被越过、谁的东西先被动。",
        )

    if item_title_matches(item, "对白效率过高", "对白缺失控层", "对白衔接过直"):
        add(
            "句句都在对题",
            "每句对白都推进主线，会失去真人冲突里的绕、憋、截断和废气。",
            item.get("evidence", [])[:3],
            "每段对白至少拆掉一句直答，换成控场句、回避句或手续句。",
        )
        add(
            "缺现场桥",
            "没有走位、噪音、旁人插话和手续件切断，对话像连续投喂信息。",
            ["对话衔接/对白功能资产命中不足"] + find_related_paragraph_evidence(item, combined, 2),
            "给对话中间塞一次走位或旁人打断，让人物来不及把话说完整。",
        )

    if item_title_matches(item, "作者替角色下结论"):
        add(
            "作者站位跑到人物前面",
            "人物还在承受现场，文本先概括意义，会像后加工评论。",
            item.get("evidence", [])[:3],
            "删掉定性句，改成读者自己能从动作和后果里看出来的东西。",
        )

    if item_title_matches(item, "情绪没有落进微动作"):
        add(
            "情绪词直给，身体没跟上",
            "标准反应和心理句多，手上动作却没承住情绪。",
            [
                f"direct_mental_state {line_types.get('direct_mental_state', 0)}",
                f"standard_reaction {line_types.get('standard_reaction', 0)}",
            ] + find_related_paragraph_evidence(item, combined, 2),
            "删一条情绪句，补一个收回、按住、放回去、划掉之类的动作。",
        )

    return subcauses[:6]


def build_minimal_fix_map(item: dict, subcauses: list[dict]) -> list[str]:
    fixes: list[str] = []
    for subcause in subcauses[:4]:
        fixes.append(f"{subcause['label']} -> {subcause['fix']}")
    if not fixes:
        fixes.extend([method.strip() for method in item.get("fix_methods", [])[:3] if str(method).strip()])
    return normalize_terms(fixes)


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


def bridge_identity_evidence(
    opening_hits: list[str],
    keep_hits: list[str],
    sequence_hits: list[str],
) -> dict:
    core_hits = normalize_terms(opening_hits + keep_hits)
    all_hits = normalize_terms(core_hits + sequence_hits)
    core_weight = round(sum(term_weight(term) for term in core_hits), 4)
    total_weight = round(sum(term_weight(term) for term in all_hits), 4)
    evidence_groups = sum(bool(items) for items in (opening_hits, keep_hits, sequence_hits))

    confirmed = bool(
        (opening_hits and keep_hits)
        or (len(core_hits) >= 2 and core_weight >= 3.0)
        or (core_hits and len(all_hits) >= 3 and total_weight >= 4.0)
    )
    if confirmed:
        reason = "已由多个桥段承重证据共同确认"
    elif not core_hits and sequence_hits:
        reason = "仅命中通用顺序词，不能确认整桥"
    elif len(all_hits) == 1:
        reason = "仅命中单个桥段词，不能确认整桥"
    elif evidence_groups < 2:
        reason = "命中证据只来自一个字段，不能确认整桥"
    else:
        reason = "命中证据的数量或区分度不足，不能确认整桥"
    return {
        "confirmed": confirmed,
        "reason": reason,
        "core_hits": core_hits,
        "all_hits": all_hits,
        "core_weight": core_weight,
        "total_weight": total_weight,
        "evidence_groups": evidence_groups,
    }


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
    # story-short-write 的紧密排版禁止段间空行，因此正文中的每个非空行
    # 才是实际段落。按空白行切分会把整篇误判成一个超长段。
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not MARKDOWN_HEADING_RE.match(line)
    ]


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


def _mark_section_boundaries(text: str, paragraphs: list[dict]) -> list[dict]:
    """给每个段落条目加上 is_section_start 标记——紧跟 markdown 标题之后的段落为 True。"""
    if not paragraphs:
        return paragraphs
    # 扫描原文，记录每个标题行结束后的字符偏移
    heading_end_offsets: list[int] = []
    cursor = 0
    for line in text.splitlines():
        line_end = cursor + len(line) + 1  # +1 for newline
        if MARKDOWN_HEADING_RE.match(line):
            heading_end_offsets.append(line_end)
        cursor = line_end

    result = []
    for para in paragraphs:
        is_start = any(
            0 <= para["start_char"] - h_end <= 40  # 允许40字的空白行容差
            for h_end in heading_end_offsets
        )
        result.append({**para, "is_section_start": is_start})
    return result


def build_rhythm_window_entries(
    text: str,
    paragraphs: list[dict] | None = None,
    target_chars: int = RHYTHM_WINDOW_TARGET_CHARS,
    min_chars: int = RHYTHM_WINDOW_MIN_CHARS,
) -> list[dict]:
    paragraphs = paragraphs or build_paragraph_entries(text)
    if not paragraphs:
        return []

    # ── 自适应 target：根据全文总长自动缩放，不再固定 1600 ──────────────────
    total_chars = sum(p["char_count"] for p in paragraphs)
    if total_chars > 0:
        # desired_n 在 [3, 8] 之间，约每 1500 字一个窗口
        desired_n = max(3, min(8, total_chars // 1500))
        auto_target = max(min_chars, total_chars // desired_n)
        target_chars = min(auto_target, COARSE_SEGMENT_MAX_CHARS)
        min_chars = max(min_chars, target_chars // 2)

    # ── 章节边界感知：标注紧跟标题之后的段落 ───────────────────────────────
    paragraphs = _mark_section_boundaries(text, paragraphs)

    windows: list[dict] = []
    bucket: list[dict] = []
    bucket_chars = 0

    def flush_bucket() -> None:
        nonlocal bucket, bucket_chars
        if not bucket:
            return
        start = bucket[0]["start_char"]
        end = bucket[-1]["end_char"]
        windows.append(
            {
                "window_index": len(windows) + 1,
                "paragraph_start": bucket[0]["paragraph_index"],
                "paragraph_end": bucket[-1]["paragraph_index"],
                "start_char": start,
                "end_char": end,
                "char_count": sum(item["char_count"] for item in bucket),
                "text": text[start:end],
            }
        )
        bucket = []
        bucket_chars = 0

    for para in paragraphs:
        # 优先在章节边界处切割（已积累 >= min_chars 才切，避免产生过小窗口）
        if bucket and para.get("is_section_start") and bucket_chars >= min_chars:
            flush_bucket()
        # 超过 target 也切
        if bucket and bucket_chars >= target_chars:
            flush_bucket()
        bucket.append(para)
        bucket_chars += para["char_count"]
    flush_bucket()

    # 尾窗口过小则合并进前一个
    if len(windows) >= 2 and windows[-1]["char_count"] < min_chars:
        tail = windows.pop()
        previous = windows[-1]
        previous["paragraph_end"] = tail["paragraph_end"]
        previous["end_char"] = tail["end_char"]
        previous["char_count"] += tail["char_count"]
        previous["text"] = text[previous["start_char"] : previous["end_char"]]

    for index, item in enumerate(windows, start=1):
        item["window_index"] = index
    return windows


def _para_has_pulse(para: dict) -> bool:
    """判断一个段落是否含叙述者气口信号。"""
    t = para["text"]
    if NARRATOR_PULSE_RE.search(t):
        return True
    # 短反问句（1-15汉字，以？结尾）
    if (1 <= count_chinese_chars(t) <= 15
            and t.rstrip('""\'「」 ').endswith(("？", "?"))):
        return True
    return False


def build_pulse_aware_windows(
    text: str,
    paragraphs: list[dict] | None = None,
    min_segment_chars: int = 250,
    max_segment_chars: int = 6000,
) -> list[dict]:
    """
    气口感知分段：气口密集区产生小窗口，稀疏叙述区保持大窗口。
    模拟朱雀的内容感知分段行为——high-pulse 区域单独切出，
    low-pulse 区域合并为较大段落。

    参数
    ----
    min_segment_chars : 段落合并阈值，低于此值的段会被吸收进相邻段。
    max_segment_chars : 超过此值的大段会按章节边界或自适应目标再切。
    """
    paragraphs = paragraphs or build_paragraph_entries(text)
    paragraphs = _mark_section_boundaries(text, paragraphs)
    if not paragraphs:
        return []

    # ── Step 1：标注每段的气口状态 ────────────────────────────────────────
    tagged: list[tuple[dict, bool]] = [
        (p, _para_has_pulse(p)) for p in paragraphs
    ]

    # ── Step 2：合并连续同类段 → 初始"段落组" ─────────────────────────────
    groups: list[list[dict]] = []
    group_pulse: list[bool] = []
    for para, has_pulse in tagged:
        if groups and group_pulse[-1] == has_pulse:
            groups[-1].append(para)
        else:
            groups.append([para])
            group_pulse.append(has_pulse)

    # ── Step 3：多轮合并过小的组 ──────────────────────────────────────────
    for _ in range(4):
        changed = False
        new_groups: list[list[dict]] = []
        new_pulse: list[bool] = []
        for paras, has_pulse in zip(groups, group_pulse):
            total = sum(p["char_count"] for p in paras)
            if total < min_segment_chars and new_groups:
                new_groups[-1].extend(paras)
                changed = True
            else:
                new_groups.append(paras)
                new_pulse.append(has_pulse)
        groups, group_pulse = new_groups, new_pulse
        if not changed:
            break

    # ── Step 4：拆分超大组 ────────────────────────────────────────────────
    final_groups: list[list[dict]] = []
    for paras in groups:
        total = sum(p["char_count"] for p in paras)
        if total <= max_segment_chars:
            final_groups.append(paras)
            continue
        # 按章节边界 + 自适应 target 切
        n_splits = max(2, (total + max_segment_chars - 1) // max_segment_chars)
        split_target = max(min_segment_chars, total // n_splits)
        bucket: list[dict] = []
        bucket_chars = 0
        for para in paras:
            if bucket and (
                bucket_chars >= split_target
                or (para.get("is_section_start") and bucket_chars >= min_segment_chars)
            ):
                final_groups.append(bucket)
                bucket = []
                bucket_chars = 0
            bucket.append(para)
            bucket_chars += para["char_count"]
        if bucket:
            final_groups.append(bucket)

    # ── Step 5：组装窗口条目 ──────────────────────────────────────────────
    windows: list[dict] = []
    for i, paras in enumerate(final_groups, start=1):
        start = paras[0]["start_char"]
        end = paras[-1]["end_char"]
        windows.append(
            {
                "window_index": i,
                "paragraph_start": paras[0]["paragraph_index"],
                "paragraph_end": paras[-1]["paragraph_index"],
                "start_char": start,
                "end_char": end,
                "char_count": sum(p["char_count"] for p in paras),
                "text": text[start:end],
            }
        )
    return windows


def is_dialogue_sentence(sentence: str) -> bool:
    return sentence.lstrip().startswith(('"', "“", "「", "『"))


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def build_model_segmented_windows(
    text: str,
    boundaries: list[int],
    paragraphs: list[dict] | None = None,
) -> list[dict]:
    """
    用模型返回的边界位置（字符偏移）构建窗口，模拟朱雀的内容感知分段。

    参数
    ----
    boundaries : 边界字符偏移列表（升序）。每个值是一个分段的起始位置。
                 不需要包含 0 和 len(text)，函数会自动补全。
    paragraphs : 可选的段落条目列表；若不提供则自动从 text 构建。

    调用示例
    ---------
    # 朱雀实测边界 / 模型返回边界
    boundaries = [4782, 5056, 8035, 8562]
    windows = build_model_segmented_windows(text, boundaries)
    """
    paragraphs = paragraphs or build_paragraph_entries(text)
    if not paragraphs or not boundaries:
        return build_rhythm_window_entries(text, paragraphs)

    # 标准化：排序、去重，确保在 [0, len(text)] 范围内
    cuts: list[int] = sorted({0, *[max(0, min(b, len(text))) for b in boundaries], len(text)})

    windows: list[dict] = []
    for seg_idx, (seg_start, seg_end) in enumerate(zip(cuts[:-1], cuts[1:]), start=1):
        if seg_start >= seg_end:
            continue
        # 找落在这个范围内的段落（用于 paragraph_start/end 元信息）
        seg_paras = [
            p for p in paragraphs
            if p["start_char"] >= seg_start and p["end_char"] <= seg_end
        ]
        # 直接用请求的字符边界切文本，以最大限度贴近朱雀分段位置。
        # 正式人工分段在进入这里前已由回执校验保证边界合法且对齐段落；
        # 这里保留任意边界能力，供朱雀结果模拟和诊断测试使用。
        windows.append(
            {
                "window_index": seg_idx,
                "paragraph_start": seg_paras[0]["paragraph_index"] if seg_paras else -1,
                "paragraph_end": seg_paras[-1]["paragraph_index"] if seg_paras else -1,
                "start_char": seg_start,
                "end_char": seg_end,
                "char_count": seg_end - seg_start,
                "text": text[seg_start:seg_end],
                "model_boundary": True,
            }
        )
    return windows

_SEGMENT_PROMPT_TMPL = """\
你是当前正在执行 story-short-write 的写作模型。请完整读取指定小说正文，找出文本 AIGC 信号密度（语言可预测性）发生显著跃变的位置。

核心概念：
- 高 AIGC 信号区（低困惑度）：精确时间戳（凌晨X点X分、七点四十二分）、程序化问答流程（报警接警/调解程序）、格式化动作序列、工整对称短句对话 → 语言高度可预测
- 低 AIGC 信号区（高困惑度）：心理流动与感知碎片、不对称句式、叙述者内在独白、情绪漂移、细节感知（气味/声音/触感）→ 语言不可预测性强

切分规则：
1. 在 AIGC 信号密度发生显著跃变的段落边界处切分；不在章节边界或叙事场景切换处切分（除非同时伴随语言可预测性的显著变化）
2. 最小段长约束：每段字符数不得少于 200 字；若某边界会产生 < 200 字的段，延后至下一个满足约束的段落锚点
3. 同质区合并：连续多章若 AIGC 信号密度相近（均为低密度叙述），归为一段，不因章节边界拆开
3.5. 短高密度尖峰（micro-spike）：若文中出现一段 200-500 字的集中程序化场景（如急诊挂号流程、填表签字、手续办理），其前后 AIGC 信号与相邻内容有显著落差（≥0.15 差值），必须单独切出，不得与前后低密度段合并
4. 目标段数与正文 AIGC 分布一致，通常为 1-13 段，即返回 0-12 个边界；若全文信号高度一致（整体高 AIGC 或整体低 AIGC），可返回 0 个边界（一整段）
5. 边界必须从 task 中的 paragraph_anchors.start_char 选择，不得估算字符位置
6. 必须读取完整正文，不能只看开头、摘要或章节标题
7. 不调用外部 API、Claude CLI 或其他模型；由当前执行 skill 的模型人工完成
8. 回填 receipt 中的 boundaries、boundary_evidence、manual_judgment、status
9. 每个 boundary_evidence 必须写明 offset、该段开头原句（quote）和为什么在这里切（reason）
10. 禁止将边界仅对齐章节标题（## N）：若某候选边界落在章节起始 5 字内，但该章节边界前后 AIGC 信号密度无显著变化，必须放弃该边界，重新选择段落内的密度跃变点
10.5. 每个最终窗口必须估算 AIGC 值并回填至 segment_scores，格式：{{start, end, aigc_estimate, label}}
    - aigc_estimate：0.00-1.00 的浮点数，根据窗口语言特征判断
      · 高程序化场景（挂号/填表/手续/格式化动作序列）→ 0.60-0.85
      · 全流水账/纯清单/精确时间戳密集 → 0.85+
      · 情绪化对话/感知碎片/内心独白 → 0.25-0.45
      · 纯人工感知叙述/强不可预测性 → 0.05-0.25
      · 混合段（程序化+情绪交织）→ 0.45-0.60
    - label：按朱雀标准自动推导，aigc_estimate < 0.50 → "人工特征"，0.50-0.99 → "疑似AI"，≥ 0.99 → "AI特征"

规则辅助切分（必须执行，但不能机械切刀）：
11. 将下面四类规则作为候选边界的观察维度：
   - 结构/章尾：从完整、工整的“起事—解释—决断—收束”转入未完成动作、余波、生活打断或下一场准备；
   - 主角不规则性：从连续最优决策、精准表达转入迟疑、误判、答非所问、动作失手或不体面反应，或反过来恢复为稳定控制；
   - 专业细节功能性：从术语/编号/流程展示转入真正改变判断、权限、风险、资源或后果的现场动作，或从功能性专业细节退回装饰性堆砌；
   - 对白模式：从“提问—回答—确认—解释”的同构回路转入打断、误听、回避、答非所问、旁人闲枝或生活事务，或反向恢复为连续高效对白。
12. 只有当上述规则变化与文本气口、信息功能或 AIGC 信号变化同时成立时，才把位置列为候选边界；单独出现一个术语、一个短句或一个情绪词，不得切窗。
13. 规则只能帮助定位候选边界，不能要求每个窗口都具备“人味”，不能为了制造不规则而新增或改写正文，也不能把规则命中直接判定为正文缺陷。
14. 全局规则不能只在单窗内判断：跨窗口记录章节弧线/章尾是否重复、主角是否连续过度正确、专业细节是否长期无功能、对白是否反复同构；这些属于跨窗复核，不得用一个局部窗口结论代替。
15. 每个最终窗口的人工说明必须注明：使用了哪些规则作为切分依据，哪些规则只做跨窗观察，以及该边界为何比相邻候选更合理。

冲突载体人工复核（必须执行，固定词只算候选）：
16. 完整读取全文后，逐场填写 conflict_carrier_review.scene_reviews；至少覆盖所有承重冲突场，不得只抽一处合格证据。
17. carriers 只能从 dialogue / body / object / space / identity / rhythm 中选择；每场必须引用正文原句并说明压力如何改变动作、站位、物件控制权、身份或后果。
18. dialogue_only_conflict 由当前模型根据全文判断，固定词数量不得直接代判。若强冲突长期只靠克制问答，必须标 true 并先回正文修改，不能把回执标 completed。
19. irreversible_violence_review 必须判断直接殴打是否存在。若存在，必须裁决为 aligned_irredeemable 或先修改正文后标 revised；不得把打人自动包装成爱、吃醋或追妻资格。
20. 脚本输出的 conflict_carrier_audit.candidate_scan_only 永远只是候选，不能直接加风险分、不能直接生成改文结论。

人物交流人工复核（同样必须执行）：
21. 完整读取全文后填写 interaction_exchange_review.scene_reviews，覆盖所有承重对话场，不得按“看、盯、停顿”等词语数量判定。
22. 每场必须写清 pressure_source（谁用什么施压）、response_mode（对方如何接招）、changed_target（动作、站位、物件、回答范围、身份或后果中哪些被改变）。
23. real_exchange 只有在压力实际落到另一个人物并改变其现场反应时才能标 true；孤立台词、答题对白和作者解释不能冒充交流。
24. author_substitution 若为 true，或任一承重场 real_exchange=false，必须先修改正文；正式回执不得标 completed。

流程硬化/证据清单感人工复核（必须逐窗输出并汇总，不能只给分）：
25. 完成 segment_scores 后，必须填写 procedural_stiffness_review，逐个最终窗口判断是否存在以下病灶：
   - workflow_log_feel：像流程日志、状态记录、会议纪要，而不是人物在现场受阻；
   - evidence_inventory_feel：证据、物件、文件一件件上桌，像作者摆道具；
   - triple_status_receipt：三连回执、三连状态、三项条件或三套预案过于工整；
   - procedure_too_smooth：手续推进过顺，出去打电话、回来资料齐，缺阻力和扯皮；
   - multi_task_sentence：一句话完成导出、交接、发送、签字、归档等多个任务；
   - character_reaction_replaced_by_process：人物情绪和反应被流程、回执、权限变化替代；
   - insufficient_scene_resistance：缺临场打断、误读、手忙脚乱、旁人插话、物件摩擦；
   - storyboard_or_construction_list：一句一个动作/证据/反应，或规则 A 执行、证据 B 展示、边界 C 落地。
26. 每个 label 为“疑似AI”或“AI特征”的窗口，window_reviews 中必须至少有一条 status=needs_revision 的具体病灶，除非明确填写 problem_type=none_found 并用原文证明该窗口其实是人物现场反应，不是流程清单。
27. 每条病灶必须写 quote、paragraph_range、why_ai_like、fix_direction、priority、must_revise。quote 必须来自正文原句；fix_direction 必须能直接指导改文，例如“把三连回执拆成手机卡顿、旁人打断、男主误读屏幕”，不能写“增强人味”。
28. procedural_stiffness_review.summary 必须汇总高优先级段落，回答：最像外部检测器会抓的 3-8 处在哪里、为什么抓、先改哪几处。若有 must_revise=true，不得把正式审计说成已通过。

判断顺序：
① 先扫描全文，对每个段落标注 AIGC 信号密度（高/低）
② 标记四类规则在全文的局部变化点和跨窗重复风险
③ 找出同时满足信号跃变、规则变化和段落可读性的候选边界
④ 合并相邻同质段，检查最小段长约束（< 200 字则延后；200-500 字的 micro-spike 高密度段不合并，保留）
⑤ 从满足约束的 paragraph_anchors.start_char 中选出最终边界，并回填边界的规则证据

正文路径：{source_path}
正文 SHA256：{text_sha256}
正文字符数：{total_chars}
统一字数：{total_words}
章节分布：{chapter_map}
"""


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manual_model_segmentation_task(
    source_path: Path,
    text: str,
    sequence_context: list[dict] | None = None,
) -> dict:
    paragraphs = build_paragraph_entries(text)
    chapter_map = ", ".join(
        f"第{m.group(1)}章[{m.start()}]"
        for m in re.finditer(r"^##\s*(\d+)", text, re.MULTILINE)
    )
    prompt = _SEGMENT_PROMPT_TMPL.format(
        source_path=str(source_path.resolve()),
        text_sha256=text_sha256(text),
        total_chars=len(text),
        total_words=count_fanqie(text),
        chapter_map=chapter_map or "无章节标记",
    )
    sequence_context = sequence_context or []
    if sequence_context:
        sequence_lines = "\n".join(
            f"- {item.get('id')}: {item.get('label')}"
            for item in sequence_context
            if isinstance(item, dict)
        )
        prompt += (
            "\n\n顺序契约结构复核（必须执行，不是可选项）：\n"
            "以下是已经绑定设定、大纲和正文的 canonical 顺序节点。"
            "切窗时必须确认每个节点落在哪个窗口，并判断节点之间的先后是否在正文中保持。"
            "如果发现 out_of_order、missing 或 ambiguous，不得把回执标为 completed，"
            "必须先返回顺序契约闸门修复。\n"
            f"{sequence_lines}\n"
        )
    return {
        "version": "1.0",
        "status": "pending",
        "execution_mode": "current_model_manual",
        "source": {
            "path": str(source_path.resolve()),
            "sha256": text_sha256(text),
            "char_count": len(text),
            "word_count": count_fanqie(text),
            "word_count_rule": "fanqie_non_whitespace_without_markdown_headings",
        },
        "prompt": prompt,
        "paragraph_anchors": [
            {
                "paragraph_index": item["paragraph_index"],
                "start_char": item["start_char"],
                "end_char": item["end_char"],
                "text": item["text"],
            }
            for item in paragraphs
        ],
        "boundaries": [],
        "boundary_evidence": [],
        "segment_scores": [],
        "sequence_review": {
            "status": "pending",
            "node_reviews": [],
            "cross_window_risks": [],
            "overall_judgment": "",
        },
        "conflict_carrier_review": {
            "status": "pending",
            "reviewed_full_text": False,
            "scene_reviews": [],
            "dialogue_only_conflict": None,
            "irreversible_violence_review": {
                "status": "pending",
                "present": None,
                "decision": "pending",
                "evidence": [],
                "judgment": "",
            },
            "global_judgment": "",
        },
        "interaction_exchange_review": {
            "status": "pending",
            "reviewed_full_text": False,
            "scene_reviews": [],
            "global_judgment": "",
        },
        "procedural_stiffness_review": {
            "status": "pending",
            "reviewed_full_text": False,
            "window_reviews": [],
            "summary": "",
            "must_revise_count": 0,
        },
        "manual_judgment": "",
    }


def validate_manual_model_segmentation_receipt(
    receipt: dict,
    source_path: Path,
    text: str,
    sequence_context: list[dict] | None = None,
) -> list[int]:
    errors: list[str] = []
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    if receipt.get("status") != "completed":
        errors.append("人工模型分段回执 status 必须为 completed")
    if receipt.get("execution_mode") != "current_model_manual":
        errors.append("人工模型分段回执 execution_mode 必须为 current_model_manual")
    if str(source.get("path") or "") != str(source_path.resolve()):
        errors.append("人工模型分段回执绑定的正文路径不一致")
    if source.get("sha256") != text_sha256(text):
        errors.append("正文 SHA 已变化，必须重新执行人工模型分段")
    if source.get("char_count") != len(text):
        errors.append("人工模型分段回执记录的正文字符数不一致")
    if source.get("word_count") != count_fanqie(text):
        errors.append("人工模型分段回执记录的统一字数不一致")

    raw_boundaries = receipt.get("boundaries")
    boundaries = raw_boundaries if isinstance(raw_boundaries, list) else []
    if not 0 <= len(boundaries) <= 12:
        errors.append("人工模型分段必须返回 0-12 个边界，形成 1-13 段")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in boundaries):
        errors.append("人工模型分段边界必须全部是整数")
    normalized = [value for value in boundaries if isinstance(value, int) and not isinstance(value, bool)]
    if normalized != sorted(set(normalized)):
        errors.append("人工模型分段边界必须严格升序且不能重复")
    if any(value <= 0 or value >= len(text) for value in normalized):
        errors.append("人工模型分段边界必须位于正文内部")

    cuts = [0, *normalized, len(text)]
    short_segments = [
        (start, end, end - start)
        for start, end in zip(cuts[:-1], cuts[1:])
        if end - start < 200
    ]
    if short_segments:
        detail = "、".join(
            f"{start}-{end}({size}字)" for start, end, size in short_segments
        )
        errors.append(f"人工模型分段每段不得少于200字: {detail}")

    paragraphs = build_paragraph_entries(text)
    anchor_map = {item["start_char"]: item for item in paragraphs}
    for value in normalized:
        if value not in anchor_map:
            errors.append(f"人工模型分段边界未对齐段落起点: {value}")

    evidence = receipt.get("boundary_evidence")
    if not isinstance(evidence, list) or len(evidence) != len(normalized):
        errors.append("boundary_evidence 必须与 boundaries 一一对应")
    else:
        evidence_map = {
            item.get("offset"): item
            for item in evidence
            if isinstance(item, dict)
        }
        for value in normalized:
            item = evidence_map.get(value)
            if not item:
                errors.append(f"缺少边界证据: {value}")
                continue
            quote = str(item.get("quote") or "").strip()
            reason = str(item.get("reason") or "").strip()
            anchor = anchor_map.get(value)
            if not quote or not anchor or not anchor["text"].startswith(quote):
                errors.append(f"边界证据原句与段落起点不一致: {value}")
            if not reason:
                errors.append(f"边界证据缺少人工判断: {value}")

    if not str(receipt.get("manual_judgment") or "").strip():
        errors.append("人工模型分段回执缺少整体判断")

    expected_seg_count = len(cuts) - 1
    segment_scores = receipt.get("segment_scores")
    if not isinstance(segment_scores, list) or len(segment_scores) != expected_seg_count:
        errors.append(f"segment_scores 必须与分段数量一致（{expected_seg_count} 个）")
    else:
        valid_labels = {"人工特征", "疑似AI", "AI特征"}
        for i, item in enumerate(segment_scores):
            if not isinstance(item, dict):
                errors.append(f"segment_scores[{i}] 格式错误，必须是对象")
                continue
            seg_start = item.get("start")
            seg_end = item.get("end")
            expected_start = cuts[i]
            expected_end = cuts[i + 1]
            if seg_start != expected_start or seg_end != expected_end:
                errors.append(
                    "segment_scores"
                    f"[{i}] 的 start/end 必须与分段边界一致"
                    f"（应为 {expected_start}-{expected_end}，实际为 {seg_start}-{seg_end}）"
                )
            aigc = item.get("aigc_estimate")
            if not isinstance(aigc, (int, float)) or isinstance(aigc, bool) or not 0.0 <= float(aigc) <= 1.0:
                errors.append(f"segment_scores[{i}].aigc_estimate 必须是 0-1 之间的数值")
            label = item.get("label")
            if label not in valid_labels:
                errors.append(f"segment_scores[{i}].label 必须是 人工特征/疑似AI/AI特征 之一，实际为: {label!r}")
            # 校验 label 与 aigc_estimate 的一致性
            if isinstance(aigc, (int, float)) and not isinstance(aigc, bool) and label in valid_labels:
                v = float(aigc)
                expected_label = "AI特征" if v >= 0.99 else ("疑似AI" if v >= 0.50 else "人工特征")
                if label != expected_label:
                    errors.append(f"segment_scores[{i}].label 与 aigc_estimate={v:.4f} 不一致（应为 {expected_label}）")

    conflict_review = receipt.get("conflict_carrier_review")
    if not isinstance(conflict_review, dict):
        errors.append("人工模型分段回执缺少冲突载体人工复核")
    else:
        if conflict_review.get("status") != "completed":
            errors.append("冲突载体人工复核 status 必须为 completed")
        if conflict_review.get("reviewed_full_text") is not True:
            errors.append("冲突载体人工复核必须确认已完整阅读正文")
        if conflict_review.get("dialogue_only_conflict") is not False:
            errors.append("强冲突仍可能只靠对白，必须先回正文修改并重新复核")
        if not str(conflict_review.get("global_judgment") or "").strip():
            errors.append("冲突载体人工复核缺少全文判断")

        scene_reviews = conflict_review.get("scene_reviews")
        if not isinstance(scene_reviews, list) or not scene_reviews:
            errors.append("冲突载体人工复核缺少逐场记录")
        else:
            for index, item in enumerate(scene_reviews, 1):
                if not isinstance(item, dict):
                    errors.append(f"冲突载体场景复核格式错误[{index}]")
                    continue
                if item.get("status") != "passed":
                    errors.append(f"冲突载体场景尚未通过[{index}]")
                if not str(item.get("scene") or "").strip():
                    errors.append(f"冲突载体场景缺少 scene[{index}]")
                carriers = item.get("carriers")
                if not isinstance(carriers, list) or not carriers:
                    errors.append(f"冲突载体场景缺少 carriers[{index}]")
                else:
                    invalid = [
                        str(value)
                        for value in carriers
                        if value not in CONFLICT_REVIEW_CARRIERS
                    ]
                    if invalid:
                        errors.append(
                            f"冲突载体场景包含无效 carriers[{index}]: "
                            + " / ".join(invalid)
                        )
                evidence_items = item.get("evidence")
                if not isinstance(evidence_items, list) or not evidence_items:
                    errors.append(f"冲突载体场景缺少正文证据[{index}]")
                else:
                    for evidence_index, evidence_item in enumerate(evidence_items, 1):
                        if not isinstance(evidence_item, dict):
                            errors.append(
                                f"冲突载体正文证据格式错误[{index}.{evidence_index}]"
                            )
                            continue
                        quote = str(evidence_item.get("quote") or "").strip()
                        if not quote or quote not in text:
                            errors.append(
                                f"冲突载体正文证据不在正文[{index}.{evidence_index}]"
                            )
                        if not str(evidence_item.get("judgment") or "").strip():
                            errors.append(
                                f"冲突载体正文证据缺少人工判断[{index}.{evidence_index}]"
                            )
                if not str(item.get("consequence") or "").strip():
                    errors.append(f"冲突载体场景缺少实际后果[{index}]")
                if not str(item.get("judgment") or "").strip():
                    errors.append(f"冲突载体场景缺少总判断[{index}]")

        violence_review = conflict_review.get("irreversible_violence_review")
        if not isinstance(violence_review, dict):
            errors.append("冲突载体人工复核缺少直接暴力裁决")
        else:
            if violence_review.get("status") != "completed":
                errors.append("直接暴力裁决 status 必须为 completed")
            present = violence_review.get("present")
            decision = violence_review.get("decision")
            if not isinstance(present, bool):
                errors.append("直接暴力裁决 present 必须是布尔值")
            if decision not in VIOLENCE_REVIEW_DECISIONS:
                errors.append("直接暴力裁决 decision 无效")
            if decision == "absent" and present is not False:
                errors.append("直接暴力裁决 absent 必须对应 present=false")
            if decision == "aligned_irredeemable" and present is not True:
                errors.append("直接暴力裁决 aligned_irredeemable 必须对应 present=true")
            if decision == "revised" and present is not False:
                errors.append("直接暴力裁决 revised 必须对应修改后 present=false")
            if not str(violence_review.get("judgment") or "").strip():
                errors.append("直接暴力裁决缺少人工判断")
            violence_evidence = violence_review.get("evidence")
            if present is True:
                if not isinstance(violence_evidence, list) or not violence_evidence:
                    errors.append("存在直接暴力时必须提供正文证据")
                else:
                    for index, item in enumerate(violence_evidence, 1):
                        quote = str(item.get("quote") or "").strip() if isinstance(item, dict) else ""
                        if not quote or quote not in text:
                            errors.append(f"直接暴力证据不在正文[{index}]")

    exchange_review = receipt.get("interaction_exchange_review")
    if not isinstance(exchange_review, dict):
        errors.append("人工模型分段回执缺少人物交流人工复核")
    else:
        if exchange_review.get("status") != "completed":
            errors.append("人物交流人工复核 status 必须为 completed")
        if exchange_review.get("reviewed_full_text") is not True:
            errors.append("人物交流人工复核必须确认已完整阅读正文")
        if not str(exchange_review.get("global_judgment") or "").strip():
            errors.append("人物交流人工复核缺少全文判断")
        scene_reviews = exchange_review.get("scene_reviews")
        if not isinstance(scene_reviews, list) or not scene_reviews:
            errors.append("人物交流人工复核缺少逐场记录")
        else:
            for index, item in enumerate(scene_reviews, 1):
                if not isinstance(item, dict):
                    errors.append(f"人物交流场景复核格式错误[{index}]")
                    continue
                if item.get("status") != "passed":
                    errors.append(f"人物交流场景尚未通过[{index}]")
                if not str(item.get("scene") or "").strip():
                    errors.append(f"人物交流场景缺少 scene[{index}]")
                if not str(item.get("pressure_source") or "").strip():
                    errors.append(f"人物交流场景缺少 pressure_source[{index}]")
                if not str(item.get("response_mode") or "").strip():
                    errors.append(f"人物交流场景缺少 response_mode[{index}]")
                changed_targets = item.get("changed_target")
                if not isinstance(changed_targets, list) or not changed_targets:
                    errors.append(f"人物交流场景缺少 changed_target[{index}]")
                else:
                    invalid = [
                        str(value)
                        for value in changed_targets
                        if value not in EXCHANGE_CHANGED_TARGETS
                    ]
                    if invalid:
                        errors.append(
                            f"人物交流场景包含无效 changed_target[{index}]: "
                            + " / ".join(invalid)
                        )
                if item.get("real_exchange") is not True:
                    errors.append(f"人物交流场景未形成真实压力交换[{index}]")
                if item.get("author_substitution") is not False:
                    errors.append(f"人物交流场景仍由作者解释抢位[{index}]")
                evidence_items = item.get("evidence")
                if not isinstance(evidence_items, list) or not evidence_items:
                    errors.append(f"人物交流场景缺少正文证据[{index}]")
                else:
                    for evidence_index, evidence_item in enumerate(evidence_items, 1):
                        if not isinstance(evidence_item, dict):
                            errors.append(
                                f"人物交流正文证据格式错误[{index}.{evidence_index}]"
                            )
                            continue
                        quote = str(evidence_item.get("quote") or "").strip()
                        if not quote or quote not in text:
                            errors.append(
                                f"人物交流正文证据不在正文[{index}.{evidence_index}]"
                            )
                        if not str(evidence_item.get("judgment") or "").strip():
                            errors.append(
                                f"人物交流正文证据缺少人工判断[{index}.{evidence_index}]"
                            )
                if not str(item.get("judgment") or "").strip():
                    errors.append(f"人物交流场景缺少总判断[{index}]")

    procedural_review = receipt.get("procedural_stiffness_review")
    if not isinstance(procedural_review, dict):
        errors.append("人工模型分段回执缺少流程硬化/证据清单感人工复核")
    else:
        if procedural_review.get("status") != "completed":
            errors.append("流程硬化/证据清单感人工复核 status 必须为 completed")
        if procedural_review.get("reviewed_full_text") is not True:
            errors.append("流程硬化/证据清单感人工复核必须确认已完整阅读正文")
        if not str(procedural_review.get("summary") or "").strip():
            errors.append("流程硬化/证据清单感人工复核缺少 summary 汇总")
        window_reviews = procedural_review.get("window_reviews")
        if not isinstance(window_reviews, list):
            errors.append("流程硬化/证据清单感人工复核 window_reviews 必须是列表")
            window_reviews = []
        review_by_window: dict[int, list[dict]] = {}
        must_revise_count = 0
        for index, item in enumerate(window_reviews, 1):
            if not isinstance(item, dict):
                errors.append(f"流程硬化病灶条目格式错误[{index}]")
                continue
            window_index = item.get("window_index")
            if not isinstance(window_index, int) or not 1 <= window_index <= expected_seg_count:
                errors.append(f"流程硬化病灶 window_index 无效[{index}]")
            else:
                review_by_window.setdefault(window_index, []).append(item)
            problem_type = item.get("problem_type")
            if problem_type not in PROCEDURAL_STIFFNESS_PROBLEM_TYPES:
                errors.append(f"流程硬化病灶 problem_type 无效[{index}]: {problem_type!r}")
            status = item.get("status")
            if status not in {"needs_revision", "passed", "not_applicable"}:
                errors.append(f"流程硬化病灶 status 无效[{index}]: {status!r}")
            priority = item.get("priority")
            if priority not in {"P0", "P1", "P2", "none"}:
                errors.append(f"流程硬化病灶 priority 无效[{index}]: {priority!r}")
            if item.get("must_revise") is True:
                must_revise_count += 1
                if status != "needs_revision":
                    errors.append(f"must_revise=true 必须对应 needs_revision[{index}]")
                if priority not in {"P0", "P1", "P2"}:
                    errors.append(f"must_revise=true 必须填写 P0/P1/P2[{index}]")
            quote = str(item.get("quote") or "").strip()
            if not quote or quote not in text:
                errors.append(f"流程硬化病灶 quote 不在正文[{index}]")
            paragraph_range = item.get("paragraph_range")
            if (
                not isinstance(paragraph_range, list)
                or len(paragraph_range) != 2
                or any(not isinstance(value, int) for value in paragraph_range)
            ):
                errors.append(f"流程硬化病灶 paragraph_range 必须是两个整数[{index}]")
            if not str(item.get("why_ai_like") or "").strip():
                errors.append(f"流程硬化病灶缺少 why_ai_like[{index}]")
            fix_direction = str(item.get("fix_direction") or "").strip()
            if problem_type != "none_found" and not fix_direction:
                errors.append(f"流程硬化病灶缺少可执行 fix_direction[{index}]")
        declared_count = procedural_review.get("must_revise_count")
        if isinstance(declared_count, int) and declared_count != must_revise_count:
            errors.append(
                "流程硬化/证据清单感问题 must_revise_count 与逐条记录不一致"
            )
        for i, score_item in enumerate(segment_scores if isinstance(segment_scores, list) else [], 1):
            if not isinstance(score_item, dict):
                continue
            label = score_item.get("label")
            if label not in {"疑似AI", "AI特征"}:
                continue
            reviews = review_by_window.get(i, [])
            if not reviews:
                errors.append(f"疑似 AI 窗口缺少流程硬化病灶逐窗复核: window {i}")
                continue
            has_revision = any(
                item.get("status") == "needs_revision"
                and item.get("problem_type") != "none_found"
                for item in reviews
            )
            has_none_found = any(item.get("problem_type") == "none_found" for item in reviews)
            if not has_revision and not has_none_found:
                errors.append(
                    f"疑似 AI 窗口必须给出具体病灶或 none_found 反证: window {i}"
                )

    if sequence_context:
        sequence_review = receipt.get("sequence_review")
        if not isinstance(sequence_review, dict):
            errors.append("人工模型分段回执缺少顺序契约结构复核")
        else:
            if sequence_review.get("status") != "completed":
                errors.append("顺序契约结构复核 status 必须为 completed")
            if not str(sequence_review.get("overall_judgment") or "").strip():
                errors.append("顺序契约结构复核缺少整体判断")
            node_reviews = sequence_review.get("node_reviews")
            review_map = {
                str(item.get("id") or ""): item
                for item in node_reviews
                if isinstance(item, dict) and str(item.get("id") or "")
            } if isinstance(node_reviews, list) else {}
            if not isinstance(node_reviews, list):
                errors.append("顺序契约结构复核 node_reviews 必须是列表")
            for node in sequence_context:
                if not isinstance(node, dict):
                    continue
                node_id = str(node.get("id") or "").strip()
                item = review_map.get(node_id)
                if not item:
                    errors.append(f"顺序契约结构复核缺少节点: {node_id}")
                    continue
                window_index = item.get("window_index")
                if not isinstance(window_index, int) or not 1 <= window_index <= len(cuts) - 1:
                    errors.append(f"顺序契约节点窗口编号无效: {node_id}")
                quote = str(item.get("quote") or "").strip()
                if not quote or quote not in text:
                    errors.append(f"顺序契约节点复核缺少正文原句: {node_id}")
                if not str(item.get("judgment") or "").strip():
                    errors.append(f"顺序契约节点复核缺少人工判断: {node_id}")
                if item.get("order_status") != "preserved":
                    errors.append(
                        f"顺序契约节点未确认保持顺序: {node_id} "
                        f"(order_status={item.get('order_status')!r})"
                    )
            risks = sequence_review.get("cross_window_risks")
            if not isinstance(risks, list):
                errors.append("顺序契约结构复核 cross_window_risks 必须是列表")
            elif any(
                isinstance(item, dict)
                and item.get("status") not in {"resolved", "not_found"}
                for item in risks
            ):
                errors.append("顺序契约结构复核仍有未解决的跨窗口风险")
    if errors:
        raise RuntimeError("\n".join(errors))
    return normalized


def load_sequence_context_for_audit(
    receipt_path: Path,
    draft_path: Path,
) -> tuple[dict, list[dict]]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"顺序契约回执无效: {exc}") from exc
    if not isinstance(receipt, dict):
        raise RuntimeError("顺序契约回执必须是 JSON 对象")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise RuntimeError("顺序契约回执缺少 artifacts")
    paths = {}
    for key in ("setting", "outline", "draft"):
        binding = artifacts.get(key)
        if not isinstance(binding, dict) or not str(binding.get("path") or "").strip():
            raise RuntimeError(f"顺序契约回执缺少 {key} 绑定")
        paths[key] = Path(str(binding["path"])).resolve()
    errors = validate_sequence_contract(
        receipt_path.resolve(),
        paths["setting"],
        paths["outline"],
        draft_path.resolve(),
    )
    if errors:
        raise RuntimeError("顺序契约未通过:\n" + "\n".join(errors))
    sequence = receipt.get("canonical_sequence")
    if not isinstance(sequence, list) or not sequence:
        raise RuntimeError("顺序契约缺少 canonical_sequence")
    return receipt, sequence


def audit_rhythm_distribution(
    text: str,
    paragraphs: list[dict] | None = None,
    *,
    model_boundaries: list[int] | None = None,
) -> dict:
    boundaries: list[int] = []
    boundary_source = "algorithmic"

    if model_boundaries is not None:
        boundaries = [b for b in model_boundaries if isinstance(b, int)]
        boundary_source = "manual-model"

    if boundaries:
        windows = build_model_segmented_windows(text, boundaries, paragraphs)
    else:
        windows = build_rhythm_window_entries(text, paragraphs)

    results: list[dict] = []
    for window in windows:
        narrative_only = DIALOGUE_SPAN_RE.sub("。", window["text"]).replace("\n", "。")
        sentences = split_sentences_with_spans(narrative_only)
        sentence_texts = [item["text"].strip() for item in sentences if item["text"].strip()]
        lengths = [count_chinese_chars(item) for item in sentence_texts if count_chinese_chars(item)]

        short_reactions = [
            item
            for item in sentence_texts
            if 1 <= count_chinese_chars(item) <= 6
            and (
                NARRATOR_PULSE_RE.search(item)
                or item.rstrip('"”’』」 ').endswith(("？", "?"))
            )
        ]
        narrator_questions = [
            item
            for item in sentence_texts
            if item.rstrip('"”’』」 ').endswith(("？", "?"))
        ]
        explicit_asides = [
            item
            for item in sentence_texts
            if NARRATOR_PULSE_RE.search(item)
        ]
        self_qa_pairs = 0
        for index, sentence in enumerate(sentence_texts[:-1]):
            if not sentence.rstrip('"”’』」 ').endswith(("？", "?")):
                continue
            answer_len = count_chinese_chars(sentence_texts[index + 1])
            if 1 <= answer_len <= 15:
                self_qa_pairs += 1

        content_lines = [
            item.strip() for item in window["text"].splitlines() if item.strip()
        ]
        dialogue_flags = [is_dialogue_sentence(item) for item in content_lines]
        dialogue_lines = [
            item for item, is_dialogue in zip(content_lines, dialogue_flags)
            if is_dialogue
        ]
        line_count = len(content_lines)
        dialogue_line_ratio = len(dialogue_lines) / max(line_count, 1)
        dialogue_lens = [count_chinese_chars(ln.strip()) for ln in dialogue_lines if ln.strip()]
        avg_dialogue_len = statistics.mean(dialogue_lens) if dialogue_lens else 0.0
        dialogue_len_cv_val = coeff_var(dialogue_lens) if len(dialogue_lens) >= 3 else 1.0
        max_dialogue_run = 0
        current_dialogue_run = 0
        for is_dialogue in dialogue_flags:
            if is_dialogue:
                current_dialogue_run += 1
                max_dialogue_run = max(max_dialogue_run, current_dialogue_run)
            else:
                current_dialogue_run = 0
        # 对白对称性：高对白占比 + 平均行短 → 一问一答密集链，朱雀低困惑度区
        # 连续对白链用于排除“对白很多、但持续被动作和生活杂音打断”的活场面。
        symmetric_dialogue = (
            len(dialogue_lines) >= 4
            and dialogue_line_ratio >= 0.45
            and avg_dialogue_len <= 12
            and max_dialogue_run >= 4
        )
        # 去重后合并计数，避免短反应句与显式评价句双重计数
        all_pulse_sentences: set[str] = set(short_reactions) | set(explicit_asides)
        # 突发性奖励：高句长方差 = 短句/长句激烈交替，类似朱雀检测的 burstiness 人味信号
        # 对话/动作密集段（如搬陶轮、创可贴场景）即使叙述者评价句少，也应有人味信号
        sentence_length_cv = coeff_var(lengths)
        # 场面活性与叙述者气口是两套证据。动作、对白和生活干扰交错的窗口，
        # 即使没有命中固定气口词典，也不应被误判成匀速平铺。
        scene_variance_coverage = (
            len(lengths) >= 8
            and sentence_length_cv >= 0.5
            and 0.2 <= dialogue_line_ratio <= 0.55
        )
        short_window_high_variance = (
            len(lengths) >= 5
            and window["char_count"] < RHYTHM_WINDOW_MIN_CHARS
            and sentence_length_cv >= 0.6
        )
        burstiness_bonus = (
            2
            if len(lengths) >= 5
            and (sentence_length_cv > 0.75 or short_window_high_variance)
            else 0
        )
        pulse_count = len(all_pulse_sentences) + self_qa_pairs * 2 + burstiness_bonus
        pulse_density = round(pulse_count * 1000 / max(window["char_count"], 1), 3)
        results.append(
            {
                **{k: window[k] for k in (
                    "window_index",
                    "paragraph_start",
                    "paragraph_end",
                    "start_char",
                    "end_char",
                    "char_count",
                )},
                "sentence_count": len(sentence_texts),
                "sentence_length_cv": round(sentence_length_cv, 3),
                "dialogue_line_ratio": round(dialogue_line_ratio, 3),
                "narrator_question_count": len(narrator_questions),
                "self_qa_pair_count": self_qa_pairs,
                "explicit_aside_count": len(explicit_asides),
                "abrupt_reaction_count": len(short_reactions),
                "narrator_pulse_count": pulse_count,
                "narrator_pulse_density": pulse_density,
                "burstiness_bonus": burstiness_bonus,
                "scene_variance_coverage": scene_variance_coverage,
                "short_window_high_variance": short_window_high_variance,
                "avg_dialogue_len": round(avg_dialogue_len, 1),
                "dialogue_len_cv": round(dialogue_len_cv_val, 3),
                "max_dialogue_run": max_dialogue_run,
                "symmetric_dialogue": symmetric_dialogue,
                "pulse_examples": dedupe_keep_order(
                    short_reactions + narrator_questions + explicit_asides
                )[:6],
                "excerpt": window["text"][:160].replace("\n", " "),
            }
        )

    densities = [item["narrator_pulse_density"] for item in results]
    positive = [value for value in densities if value > 0]
    reference_density = statistics.median(positive) if positive else 0.0
    low_threshold = max(0.5, reference_density * 0.55) if results else 0.0
    high_threshold = max(1.0, reference_density * 1.4) if results else 0.0
    for item in results:
        if (
            item["short_window_high_variance"]
            or item["narrator_pulse_density"] >= high_threshold
        ):
            item["status"] = "high-pulse"
        elif item["symmetric_dialogue"]:
            item["status"] = "symmetric-dialogue"
        elif (
            item["char_count"] < RHYTHM_WINDOW_MIN_CHARS
            and item["narrator_pulse_density"] < low_threshold
            and not item["scene_variance_coverage"]
        ):
            item["status"] = "short-window-review"
        elif (
            item["narrator_pulse_density"] < low_threshold
            and not item["scene_variance_coverage"]
        ):
            item["status"] = "low-pulse"
        else:
            item["status"] = "covered"

    low_windows = [item for item in results if item["status"] == "low-pulse"]
    short_review_windows = [
        item for item in results if item["status"] == "short-window-review"
    ]
    symmetric_dialogue_windows = [
        item for item in results if item["status"] == "symmetric-dialogue"
    ]
    density_cv = round(coeff_var(densities), 3)
    return {
        "window_target_chars": RHYTHM_WINDOW_TARGET_CHARS,
        "window_count": len(results),
        "reference_pulse_density": round(reference_density, 3),
        "low_pulse_threshold": round(low_threshold, 3),
        "high_pulse_threshold": round(high_threshold, 3),
        "pulse_density_cv": density_cv,
        "boundary_source": boundary_source,
        "model_boundaries": boundaries if boundaries else [],
        "cross_window_contrast": (
            "insufficient-data"
            if len(results) < 2
            else "too-flat"
            if density_cv < 0.18
            else "varied"
        ),
        "low_pulse_window_count": len(low_windows),
        "low_pulse_windows": low_windows,
        "short_window_review_count": len(short_review_windows),
        "short_window_review_windows": short_review_windows,
        "symmetric_dialogue_window_count": len(symmetric_dialogue_windows),
        "symmetric_dialogue_windows": symmetric_dialogue_windows,
        "windows": results,
    }


def build_rhythm_impact_items(rhythm_audit: dict) -> list[dict]:
    low_windows = rhythm_audit.get("low_pulse_windows", [])
    short_review_windows = rhythm_audit.get("short_window_review_windows", [])
    symmetric_dialogue_windows = rhythm_audit.get("symmetric_dialogue_windows", [])
    items: list[dict] = []
    if low_windows:
        evidence = [
            (
                f"长窗{item['window_index']} 字符 {item['start_char']}-{item['end_char']} "
                f"字数 {item['char_count']} 气口密度 {item['narrator_pulse_density']}"
            )
            for item in low_windows[:4]
        ]
        items.append(
            annotate_impact_item(
                {
                    "title": "长窗叙述者气口覆盖不足",
                    "priority": "P1",
                    "why_it_hits_audit": "局部好句集中在少数短窗时，其他长区间仍会显得匀速、可预测，整篇人味会被稀释。",
                    "evidence": evidence,
                    "fix_methods": [
                        "先人工核对该窗是否真的缺现场反应，不按指标机械加句。",
                        "优先补失控动作、答非所问、生活打断或叙述者即时反应。",
                        "同一位置只补一种气口，避免自问、自嘲和金句连续堆叠。",
                    ],
                },
                source_family="style",
                focus_layer="sentence_shell",
            )
        )
    if rhythm_audit.get("cross_window_contrast") == "too-flat":
        items.append(
            annotate_impact_item(
                {
                    "title": "跨长窗节奏落差不足",
                    "priority": "P1",
                    "why_it_hits_audit": "每个长窗的叙述者气口密度过于接近，会形成统一后处理过的匀速感。",
                    "evidence": [
                        f"气口密度离散度: {rhythm_audit.get('pulse_density_cv')}",
                    ],
                    "fix_methods": [
                        "保留安静窗和爆发窗的真实差异，不追求每窗平均配置。",
                        "检查长短句、生活闲枝和对白错位是否集中在同一处。",
                    ],
                },
                source_family="style",
                focus_layer="sentence_shell",
            )
        )
    if short_review_windows:
        evidence = [
            (
                f"短窗{item['window_index']} 字符 {item['start_char']}-{item['end_char']} "
                f"字数 {item['char_count']} 气口密度 {item['narrator_pulse_density']}"
            )
            for item in short_review_windows[:4]
        ]
        items.append(
            annotate_impact_item(
                {
                    "title": "短模型分段缺少可计算气口，必须人工复核",
                    "priority": "P1",
                    "why_it_hits_audit": "短段不能因为不足长窗阈值就自动算作已覆盖；如果没有词典气口或句式突发信号，需要人工判断它是动作/对白高波动段，还是被错误切碎的平段。",
                    "evidence": evidence,
                    "fix_methods": [
                        "先看该短段是否存在对白错位、荒诞动作、情绪骤变或人物失手。",
                        "若只是平铺叙述被切短，调整人工模型边界，不要靠补短句抬分。",
                    ],
                },
                source_family="rhythm_distribution",
                focus_layer="block_rhythm",
            )
        )
    if symmetric_dialogue_windows:
        evidence = [
            (
                f"长窗{item['window_index']} 字符 {item['start_char']}-{item['end_char']} "
                f"对白占比 {item['dialogue_line_ratio']} 平均对白长度 {item['avg_dialogue_len']} "
                f"最长连续对白 {item['max_dialogue_run']} 行"
            )
            for item in symmetric_dialogue_windows[:4]
        ]
        items.append(
            annotate_impact_item(
                {
                    "title": "连续短对白链需要人工复核",
                    "priority": "P1",
                    "why_it_hits_audit": "高对白占比、短句和连续问答叠加时，场面容易变成高效率的信息交换，缺少动作、回避和生活干扰。",
                    "evidence": evidence,
                    "fix_methods": [
                        "先人工判断连续对白是否符合职业流程或冲突现场，不按命中数量机械拆句。",
                        "若人物每句都准确回应上一句，优先加入回避、误听、动作中断或第三方闲枝。",
                        "若对白已被动作和环境持续打断，保留正文并记录为人工放行，不为脚本改文。",
                    ],
                },
                source_family="rhythm_distribution",
                focus_layer="block_rhythm",
            )
        )
    return items


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
        identity = bridge_identity_evidence(
            opening_hits,
            keep_hits,
            sequence_info["hit_terms"],
        )
        if not identity["confirmed"]:
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
                "bridge_identity_confirmed": True,
                "bridge_identity_reason": identity["reason"],
                "bridge_identity_hits": identity["all_hits"][:10],
                "bridge_identity_weight": identity["total_weight"],
                "bridge_identity_evidence_groups": identity["evidence_groups"],
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
    profile_meta = profile.get("meta", {}) if isinstance(profile.get("meta"), dict) else {}
    sample_buckets = profile.get("sample_source_buckets", {}) if isinstance(profile.get("sample_source_buckets"), dict) else {}
    sample_entries = sample_buckets.get("entries", []) if isinstance(sample_buckets.get("entries"), list) else []
    is_merged_profile = bool(
        profile_meta.get("mode") == "merged_profiles"
        or int(profile_meta.get("source_count") or 0) > 1
        or len(sample_entries) > 1
    )
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
        if is_merged_profile:
            warnings.append(
                "融合 profile 的桥段身份未通过多证据确认；禁止依据单个通用词回灌任一来源桥壳。"
                "先按项目细纲确认目标桥，未确认时只审计当前正文。"
            )
        else:
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
        "is_merged_profile": is_merged_profile,
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
    if (
        level in {"B类骨架样本", "C类负样本"}
        and asset_coverage.get("has_bridge_rules")
        and not asset_coverage.get("bridge_matched_count")
        and not asset_coverage.get("is_merged_profile")
    ):
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


def audit_interpersonal_exchange(text: str, light_report: dict) -> dict:
    paragraphs = split_paragraphs(text)
    candidate_blocks: list[dict] = []
    interaction_hits_all: list[str] = []
    interaction_layers_all: dict[str, list[str]] = {
        layer: [] for layer in EXCHANGE_LAYER_CUES
    }
    author_substitute_hits_all: list[str] = []

    for idx, para in enumerate(paragraphs):
        if "“" not in para and '"' not in para:
            continue
        window_paras = paragraphs[max(0, idx - 1): min(len(paragraphs), idx + 2)]
        window_text = "\n".join(window_paras)
        dialogue_count = sum(1 for item in window_paras if "“" in item or '"' in item)
        interaction_layers = collect_exchange_layers(window_text)
        active_layers = [
            layer for layer, hits in interaction_layers.items() if hits
        ]
        interaction_hits = normalize_terms(
            hit
            for hits in interaction_layers.values()
            for hit in hits
        )
        author_substitute_hits = collect_term_hits(window_text, EXCHANGE_AUTHOR_SUBSTITUTE_CUES, limit=6)
        has_author_line = any(
            hit.get("type") in {"author_verdict", "theme_explanation"}
            for hit in light_report.get("line_hits", [])
            if isinstance(hit, dict) and isinstance(hit.get("text"), str) and hit.get("text") in window_text
        )
        if dialogue_count <= 0:
            continue
        if (
            (len(active_layers) >= 2 or len(interaction_hits) >= 2)
            and not author_substitute_hits
            and not has_author_line
        ):
            interaction_hits_all.extend(interaction_hits)
            for layer, hits in interaction_layers.items():
                interaction_layers_all[layer].extend(hits)
            continue
        candidate_blocks.append(
            {
                "paragraph_index": idx + 1,
                "dialogue_count": dialogue_count,
                "interaction_hits": interaction_hits[:4],
                "interaction_layers": active_layers,
                "author_substitute_hits": author_substitute_hits[:4],
                "has_author_line": has_author_line,
                "candidate_only": True,
                "excerpt": clean_excerpt(window_text, 120),
            }
        )
        interaction_hits_all.extend(interaction_hits)
        for layer, hits in interaction_layers.items():
            interaction_layers_all[layer].extend(hits)
        author_substitute_hits_all.extend(author_substitute_hits)
        if len(candidate_blocks) >= 8:
            break

    return {
        "candidate_scan_only": True,
        "candidate_blocks": candidate_blocks,
        "issue_blocks": [],
        "interaction_hits": normalize_terms(interaction_hits_all)[:12],
        "interaction_layers": {
            layer: normalize_terms(hits)[:12]
            for layer, hits in interaction_layers_all.items()
        },
        "author_substitute_hits": normalize_terms(author_substitute_hits_all)[:12],
        "manual_review": None,
    }


def exchange_manual_failures(exchange_audit: dict) -> list[dict]:
    review = exchange_audit.get("manual_review")
    if not isinstance(review, dict):
        return []
    scene_reviews = review.get("scene_reviews")
    if not isinstance(scene_reviews, list):
        return []
    return [
        item
        for item in scene_reviews
        if isinstance(item, dict)
        and (
            item.get("status") != "passed"
            or item.get("real_exchange") is not True
            or item.get("author_substitution") is True
        )
    ]


def audit_conflict_carrier_distribution(text: str, profile: dict) -> dict:
    dialogue_count = len(split_dialogue_segments(text))
    carrier_hits = {
        carrier: collect_term_hits(text, cues, limit=20)
        for carrier, cues in CONFLICT_CARRIER_CUES.items()
        if carrier != "dialogue"
    }
    active_non_dialogue = [
        carrier for carrier, hits in carrier_hits.items() if hits
    ]
    strong_conflict_hits = collect_term_hits(text, STRONG_CONFLICT_CUES, limit=20)
    irreversible_violence_hits = collect_term_hits(
        text,
        IRREVERSIBLE_VIOLENCE_CUES,
        limit=12,
    )
    return {
        "candidate_scan_only": True,
        "dialogue_count": dialogue_count,
        "strong_conflict_candidates": strong_conflict_hits,
        "carrier_candidates": carrier_hits,
        "active_non_dialogue_candidate_types": active_non_dialogue,
        "irreversible_violence_candidates": irreversible_violence_hits,
        "manual_review": None,
        "manual_rule": (
            "强情绪冲突应按场景分配对白、肢体、物件、空间和身份后果；"
            "直接殴打会改变角色可追性，必须由题材设定主动选择。"
        ),
    }


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

    exchange = style_audits.get("exchange_audit", {})
    if exchange_manual_failures(exchange):
        recs.append("人物开口了，但交流没接上：检查视线、肢体、物件、空间、节奏和身份压力，别只机械补眼神。")

    conflict_review = (
        style_audits.get("conflict_carrier_audit", {}).get("manual_review")
        or {}
    )
    if conflict_review.get("dialogue_only_conflict") is True:
        recs.append("强冲突几乎只靠对白推进：选少数承重场补身体边界、夺物/毁物、拦路或身份后果，不要全篇继续克制答题。")
    violence_review = conflict_review.get("irreversible_violence_review") or {}
    if violence_review.get("decision") == "unresolved":
        recs.append("正文出现直接殴打信号：必须人工确认男主是否已转为不可洗白角色，并同步修改题材承诺、结局和追妻资格。")

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

    exchange = style_audits.get("exchange_audit", {})
    exchange_failures = exchange_manual_failures(exchange)
    if exchange_failures:
        evidence = [
            f"{item.get('scene')} / {item.get('judgment')}"
            for item in exchange_failures[:4]
        ]
        if exchange.get("author_substitute_hits"):
            evidence.append("作者代替交流命中: " + " / ".join(exchange.get("author_substitute_hits", [])[:4]))
        items.append(
            annotate_impact_item(
                {
                "title": "人物开口了，但没有交流",
                "priority": "P0",
                "why_it_hits_audit": "真人冲突不是只把台词摆出来，而是要有人盯住、有人停住、有人被迫接招。只有孤立台词和作者解释时，交流感会直接塌掉。",
                "evidence": evidence[:5],
                "fix_methods": [
                    "先判断该场主压力来自视线、肢体、物件、空间、节奏还是身份，不要所有场都补对视。",
                    "让关键台词改变对方的动作、站位、物件控制权或回答范围。",
                    "删掉替人物解释气味的那句作者话，把压力退回到现场交流里。",
                    "让一句重要台词后面真的有人被逼着接，哪怕只是没接住、咽回去、转去压程序。",
                ],
                },
                source_family="style",
                focus_layer="character_reaction",
            )
        )

    conflict_review = (
        style_audits.get("conflict_carrier_audit", {}).get("manual_review")
        or {}
    )
    if conflict_review.get("dialogue_only_conflict") is True:
        items.append(
            annotate_impact_item(
                {
                    "title": "强冲突只剩对话，没有身体或物件后果",
                    "priority": "P0",
                    "why_it_hits_audit": "强情绪场如果一直靠克制问答、条件陈述和漂亮反击推进，人物不会真正侵犯彼此边界，读者只会觉得板正，不会恨也不会疼。",
                    "evidence": [
                        str(conflict_review.get("global_judgment") or ""),
                    ],
                    "fix_methods": [
                        "只选两到三场承重冲突升级，不要每场都摔东西。",
                        "优先使用拦门、抓腕、夺物、推撞、撕裂珍爱物、把人挤出原有空间等可观察越界。",
                        "伤害必须留下后续：淤痕、物件损坏、权限变化、旁人站位或无法撤回的关系判断。",
                        "直接扇打、掐脖、踢踹会改变角色可追性；只有设定明确要写不可洗白施暴者时才使用。",
                    ],
                },
                source_family="style",
                focus_layer="bridge_structure",
            )
        )
    violence_review = conflict_review.get("irreversible_violence_review") or {}
    if violence_review.get("decision") == "unresolved":
        items.append(
            annotate_impact_item(
                {
                    "title": "直接殴打已改变男主可追性",
                    "priority": "P0",
                    "why_it_hits_audit": "直接殴打不是普通冲突升级，而是角色伦理和文类承诺变化；若仍按可怜追妻、误会解开或补救复合处理，会造成价值判断断裂。",
                    "evidence": [
                        str(violence_review.get("judgment") or "")
                    ],
                    "fix_methods": [
                        "人工确认该角色是否从追妻男主转为不可洗白施暴者。",
                        "若保留，设定、大纲、正文必须同步写明不复合、现实后果和女主安全边界。",
                        "若仍需保留可追性，改成拦路、夺物、抓腕后立刻松手或毁物等严重越界，并保留后果，不能把暴力美化成在乎。",
                    ],
                },
                source_family="style",
                focus_layer="genre_promise",
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
        "exchange_audit": audit_interpersonal_exchange(text, light_report),
        "conflict_carrier_audit": audit_conflict_carrier_distribution(text, profile),
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
    exchange_issues = exchange_manual_failures(
        style_audits.get("exchange_audit", {})
    )
    external_pressure = bool(consequence_audit and consequence_audit.get("external_order_hits"))
    public_pressure = bool(consequence_audit and consequence_audit.get("public_explosion_hits"))
    conflict_surface = bool(
        scene_overload
        or light_report.get("over_effective_dialogue_blocks")
        or meltdown.get("dialogue_count", 0) >= 6
        or exchange_issues
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
    if exchange_issues:
        style_penalty += 5
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
    exchange_issues = exchange_manual_failures(
        style_audits.get("exchange_audit", {})
    )
    conflict_surface = bool(
        scene_overload
        or light_report.get("over_effective_dialogue_blocks")
        or meltdown.get("dialogue_count", 0) >= 6
        or exchange_issues
        or (consequence_audit and consequence_audit.get("public_explosion_hits"))
    )
    relationship_surface = bool(conflict_surface or object_hits or quiet_hits)

    if conflict_surface and not style_audits.get("character_bias_audit", {}).get("hits"):
        flags.append("人物偏手没有立住")
    if exchange_issues:
        flags.append("人物开口了，但没有交流")
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


def procedural_stiffness_priority_tuple(item: dict) -> tuple[int, int, int]:
    priority_order = {"P0": 3, "P1": 2, "P2": 1, "none": 0}
    return (
        1 if item.get("must_revise") else 0,
        priority_order.get(str(item.get("priority") or "none"), 0),
        -int(item.get("window_index") or 0),
    )


def extract_procedural_stiffness_review(receipt: dict | None) -> dict:
    """Extract current-model procedural AI-like findings for reporting."""
    if not isinstance(receipt, dict):
        return {}
    review = receipt.get("procedural_stiffness_review")
    if not isinstance(review, dict):
        return {}
    items = [
        item
        for item in review.get("window_reviews", [])
        if isinstance(item, dict)
        and item.get("problem_type") != "none_found"
        and item.get("status") == "needs_revision"
    ]
    items = sorted(items, key=procedural_stiffness_priority_tuple, reverse=True)
    return {
        "status": review.get("status"),
        "summary": review.get("summary", ""),
        "must_revise_count": sum(1 for item in items if item.get("must_revise") is True),
        "findings": items,
    }


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
    rhythm_audit = combined.get("rhythm_distribution_audit", {})
    if rhythm_audit:
        lines.append("## 长窗节奏覆盖")
        lines.append("")
        lines.append(f"- 长窗数: `{rhythm_audit.get('window_count', 0)}`")
        lines.append(f"- 低气口长窗数: `{rhythm_audit.get('low_pulse_window_count', 0)}`")
        lines.append(
            f"- 连续短对白链窗口数: `{rhythm_audit.get('symmetric_dialogue_window_count', 0)}`"
        )
        lines.append(f"- 跨窗落差: `{rhythm_audit.get('cross_window_contrast')}`")
        lines.append(f"- 气口密度离散度: `{rhythm_audit.get('pulse_density_cv')}`")
        lines.append("- 说明: 这里只做内部定位，不等同于外部检测器的 human/uncertain 分类。")
        for item in rhythm_audit.get("windows", []):
            examples = " / ".join(item.get("pulse_examples", [])[:3]) or "无显式气口"
            lines.append(
                f"- 长窗{item.get('window_index')}: 字符 `{item.get('start_char')}-{item.get('end_char')}` "
                f"字数 `{item.get('char_count')}` 状态 `{item.get('status')}` "
                f"气口 `{item.get('narrator_pulse_count')}` 密度 `{item.get('narrator_pulse_density')}` "
                f"自问自答 `{item.get('self_qa_pair_count')}` 对白占比 `{item.get('dialogue_line_ratio')}` "
                f"例句 `{examples}`"
            )
        lines.append("")
    procedural_stiffness = combined.get("procedural_stiffness_review", {})
    if procedural_stiffness:
        lines.append("## 人工窗口流程硬化问题汇总")
        lines.append("")
        lines.append(f"- 状态: `{procedural_stiffness.get('status')}`")
        lines.append(f"- 必改数量: `{procedural_stiffness.get('must_revise_count', 0)}`")
        if procedural_stiffness.get("summary"):
            lines.append(f"- 人工汇总: {procedural_stiffness.get('summary')}")
        for item in procedural_stiffness.get("findings", [])[:12]:
            para_range = item.get("paragraph_range") or []
            para_text = (
                f"{para_range[0]}-{para_range[1]}"
                if isinstance(para_range, list) and len(para_range) == 2
                else "?"
            )
            lines.append(
                f"- 窗口{item.get('window_index')} / 原始段 `{para_text}` / "
                f"`{item.get('problem_type')}` / `{item.get('priority')}` / "
                f"必改 `{item.get('must_revise')}`"
            )
            lines.append(f"  - 原句: {item.get('quote', '')}")
            lines.append(f"  - 为什么像 AI: {item.get('why_ai_like', '')}")
            lines.append(f"  - 改法: {item.get('fix_direction', '')}")
        lines.append("")
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
        + combined.get("rhythm_impact_items", [])
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
    lines.append("- 先判回修幅度：`global_structure / coarse_block / full_scene / paragraph_cluster / sentence_hotspot / format_only`。")
    lines.append("- 大块病、场戏病、人物机制病必须整块或整场回炉；只有确认是重复词、冒号模板、错字、标点、单句解释过满时才小改。")
    lines.append("- 同一 P0/P1 连续两轮仍在，下一轮必须升级回修幅度，不能继续原位置小补丁。")
    if combined.get("sample_grading_guidance"):
        for item in combined["sample_grading_guidance"].get("hard_stops", [])[:4]:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("## 关系体感词典")
    lines.append("")
    for item in RELATION_FEELING_RULES[:8]:
        lines.append(f"- `{item['name']}`: {item['when']}")
    lines.append("")
    lines.append("## 开头成品感子因库")
    lines.append("")
    for item in OPENING_SUBCAUSE_LIBRARY:
        lines.append(f"- `{item['name']}`: {item['why']} 改法：{item['fix']}")
    lines.append("")
    lines.append("## 当前最影响内部过稿判定的部分")
    lines.append("")
    procedural_stiffness = combined.get("procedural_stiffness_review", {})
    if procedural_stiffness and procedural_stiffness.get("findings"):
        lines.append("### 人工窗口必改项：流程硬化/证据清单感问题")
        lines.append("")
        if procedural_stiffness.get("summary"):
            lines.append(f"- 人工汇总: {procedural_stiffness.get('summary')}")
        for item in procedural_stiffness.get("findings", [])[:10]:
            para_range = item.get("paragraph_range") or []
            para_text = (
                f"{para_range[0]}-{para_range[1]}"
                if isinstance(para_range, list) and len(para_range) == 2
                else "?"
            )
            lines.append(
                f"- 窗口{item.get('window_index')} / 原始段 {para_text} / "
                f"{item.get('priority')} / `{item.get('problem_type')}`"
            )
            lines.append(f"  - 原句: {item.get('quote', '')}")
            lines.append(f"  - 为什么会被外部检测抓: {item.get('why_ai_like', '')}")
            lines.append(f"  - 建议改法: {item.get('fix_direction', '')}")
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
        subcauses = build_subcauses(item, combined)
        relation_feelings = build_relation_feelings(item, combined)
        relation_tags = [item["name"] for item in relation_feelings] or infer_relation_tags(item)
        detailed_evidence = normalize_terms(item.get("evidence", []) + find_related_paragraph_evidence(item, combined, 3))
        minimal_fixes = build_minimal_fix_map(item, subcauses)
        lines.append(f"### {idx}. {item['title']}（{item['priority']}）")
        lines.append("")
        lines.append(f"- 为什么会被打: {item['why_it_hits_audit']}")
        if item.get("sample_bias_note"):
            lines.append(f"- 样本等级调度: {item['sample_bias_note']}")
        if relation_tags:
            lines.append(f"- 关系体感: {' / '.join(relation_tags[:5])}")
        if relation_feelings:
            lines.append("- 关系判词说明:")
            for feeling in relation_feelings[:4]:
                lines.append(f"  - {feeling['name']}：{feeling['when']}")
        if subcauses:
            lines.append("- 失败拆因:")
            for sub_idx, subcause in enumerate(subcauses, start=1):
                lines.append(f"  - {sub_idx}. {subcause['label']}：{subcause['trigger']}")
                for ev in subcause.get("evidence", [])[:3]:
                    lines.append(f"    - 证据: {ev}")
                if subcause.get("fix"):
                    lines.append(f"    - 建议改法: {subcause['fix']}")
        if detailed_evidence:
            lines.append("- 本稿证据:")
            for ev in detailed_evidence[:6]:
                lines.append(f"  - {ev}")
        if minimal_fixes:
            lines.append("- 一条失败对应一条建议改法:")
            for method in minimal_fixes[:5]:
                lines.append(f"  - {method}")
        elif item.get("fix_methods"):
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
    parser.add_argument(
        "--export-model-segmentation-task",
        help="只导出当前模型人工分段任务与待回填回执，然后退出。",
    )
    parser.add_argument(
        "--model-segmentation-receipt",
        help="当前执行 skill 的模型已人工完成的分段回执 JSON；校验正文 SHA 和边界证据后使用。",
    )
    parser.add_argument(
        "--sequence-receipt",
        help="正式人工窗口审计必须绑定并通过的设定—大纲—正文顺序契约回执。",
    )
    parser.add_argument(
        "--pre-window-revision-receipt",
        help="窗口前规则/拆书资产定向回修回执；导出人工分段任务和正式人工窗口审计时必填。",
    )
    args = parser.parse_args()

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"文件不存在: {file_path}", file=sys.stderr)
        return 2
    source_text = file_path.read_text(encoding="utf-8")
    sequence_receipt_path = (
        Path(args.sequence_receipt).resolve()
        if args.sequence_receipt
        else None
    )
    sequence_receipt_data: dict | None = None
    sequence_context: list[dict] = []
    pre_window_receipt_path = (
        Path(args.pre_window_revision_receipt).resolve()
        if args.pre_window_revision_receipt
        else None
    )
    if args.export_model_segmentation_task or args.model_segmentation_receipt:
        if sequence_receipt_path is None:
            print(
                "正式人工窗口必须绑定 --sequence-receipt，"
                "否则只能运行算法预扫",
                file=sys.stderr,
            )
            return 2
        if not sequence_receipt_path.is_file():
            print(f"顺序契约回执不存在: {sequence_receipt_path}", file=sys.stderr)
            return 2
        try:
            sequence_receipt_data, sequence_context = load_sequence_context_for_audit(
                sequence_receipt_path,
                file_path,
            )
        except (OSError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if pre_window_receipt_path is None:
            print(
                "人工窗口必须先完成窗口前规则/拆书资产定向回修，"
                "请传入 --pre-window-revision-receipt",
                file=sys.stderr,
            )
            return 2
        if not pre_window_receipt_path.is_file():
            print(f"窗口前回修回执不存在: {pre_window_receipt_path}", file=sys.stderr)
            return 2
        try:
            pre_window_errors = validate_pre_window_revision(
                pre_window_receipt_path,
                file_path,
            )
        except (json.JSONDecodeError, OSError) as exc:
            print(f"窗口前回修回执无效: {exc}", file=sys.stderr)
            return 2
        if pre_window_errors:
            print("窗口前规则/拆书资产定向回修未通过:", file=sys.stderr)
            for error in pre_window_errors:
                print(f"- {error}", file=sys.stderr)
            return 2
    if args.export_model_segmentation_task:
        task_path = Path(args.export_model_segmentation_task).resolve()
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text(
            json.dumps(
                build_manual_model_segmentation_task(
                    file_path,
                    source_text,
                    sequence_context,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("model_segmentation_task: exported")
        print(f"task: {task_path}")
        return 0

    manual_model_boundaries: list[int] | None = None
    model_segmentation_receipt_path: Path | None = None
    model_segmentation_receipt_data: dict | None = None
    if args.model_segmentation_receipt:
        model_segmentation_receipt_path = Path(args.model_segmentation_receipt).resolve()
        if not model_segmentation_receipt_path.is_file():
            print(
                f"人工模型分段回执不存在: {model_segmentation_receipt_path}",
                file=sys.stderr,
            )
            return 2
        try:
            model_segmentation_receipt_data = json.loads(
                model_segmentation_receipt_path.read_text(encoding="utf-8")
            )
            manual_model_boundaries = validate_manual_model_segmentation_receipt(
                model_segmentation_receipt_data,
                file_path,
                source_text,
                sequence_context,
            )
        except (json.JSONDecodeError, RuntimeError) as exc:
            print(f"人工模型分段回执无效:\n{exc}", file=sys.stderr)
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

    sample_grading_guidance = build_sample_grading_guidance(profile)
    recommendations = build_recommendations(light_report, heavy_report)
    bridge_audit = bridge_rule_audit(source_text, profile)
    consequence_audit = consequence_chain_audit(source_text, profile)
    style_audits = build_style_audits(source_text, profile, light_report)
    if model_segmentation_receipt_data:
        style_audits["exchange_audit"]["manual_review"] = (
            model_segmentation_receipt_data.get("interaction_exchange_review")
        )
        style_audits["conflict_carrier_audit"]["manual_review"] = (
            model_segmentation_receipt_data.get("conflict_carrier_review")
        )
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
    rhythm_distribution_audit = audit_rhythm_distribution(
        source_text,
        paragraphs,
        model_boundaries=manual_model_boundaries,
    )
    rhythm_impact_items = [
        apply_sample_grading_item_bias(item, sample_grading_guidance)
        for item in build_rhythm_impact_items(rhythm_distribution_audit)
    ]
    procedural_stiffness_review = extract_procedural_stiffness_review(
        model_segmentation_receipt_data
    )
    if rhythm_distribution_audit.get("low_pulse_window_count"):
        recommendations.append(
            "按长窗复核叙述者气口分布；只在确有匀速问题的位置补现场反应、错位或打断，不按数量机械加短句。"
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
        "model_segmentation_receipt": (
            str(model_segmentation_receipt_path)
            if model_segmentation_receipt_path
            else None
        ),
        "sequence_receipt": (
            str(sequence_receipt_path)
            if sequence_receipt_path
            else None
        ),
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
        "rhythm_distribution_audit": rhythm_distribution_audit,
        "rhythm_impact_items": rhythm_impact_items,
        "procedural_stiffness_review": procedural_stiffness_review,
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
