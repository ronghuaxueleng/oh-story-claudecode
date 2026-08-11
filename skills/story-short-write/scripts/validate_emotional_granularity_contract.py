#!/usr/bin/env python3
"""Validate source-level emotional parity during a short-fiction first draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-write.emotional-granularity-contract.v4"
SOURCE_LEDGER_SCHEMA = "story-short-analyze.full-text-emotion-ledger.v1"
SOURCE_LEDGER_SEGMENT_KINDS = {
    "emotion_bearing",
    "non_emotional_support",
    "structural_marker",
}
REQUIRED_PLAN_FIELDS = (
    "immediate_subjective_judgment_plan",
    "untidy_thought_or_emotional_crack_plan",
    "embodied_or_object_action_plan",
    "old_wound_trigger_plan",
    "opponent_pressure_plan",
    "loss_of_control_or_equivalent_plan",
)
REQUIRED_REVIEW_QUOTE_FIELDS = (
    "immediate_subjective_judgment_quotes",
    "untidy_thought_or_emotional_crack_quotes",
    "embodied_or_object_action_quotes",
    "opponent_pressure_quotes",
    "loss_of_control_or_equivalent_quotes",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha1_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def normalize_bound_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def bound_text_contains(container: Any, quote: Any) -> bool:
    return normalize_bound_text(quote) in normalize_bound_text(container)


def same_file_path(left: Path, right: Path) -> bool:
    left_resolved = left.resolve()
    right_resolved = right.resolve()
    try:
        return left_resolved.samefile(right_resolved)
    except (FileNotFoundError, OSError):
        return left_resolved == right_resolved


def binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("回执必须是 JSON 对象")
    return data


def outline_section_ids(text: str) -> list[str]:
    return re.findall(r"(?m)^##\s+(\d+)\.\s*", text)


def outline_emotion_regions(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^##\s+([^\n]+?)\s*$", text))
    regions: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if title == "导语":
            region_id = "opening"
        elif title == "尾声":
            region_id = "epilogue"
        else:
            section_match = re.fullmatch(r"(\d+)\.(?:\s+.*)?", title)
            if section_match is None:
                continue
            region_id = f"section:{section_match.group(1)}"
        if region_id in regions:
            raise ValueError(f"细纲情绪区域重复: {region_id}")
        regions[region_id] = text[match.end() : end].strip()
    return regions


def source_beat_regions(beats: list[dict[str, Any]]) -> dict[str, str]:
    bid_indexes = [index for index, beat in enumerate(beats) if beat.get("bid_ids")]
    if not bid_indexes:
        return {
            str(beat.get("beat_id") or "").strip(): "transition" for beat in beats
        }
    first_bid = bid_indexes[0]
    last_bid = bid_indexes[-1]
    result: dict[str, str] = {}
    for index, beat in enumerate(beats):
        beat_id = str(beat.get("beat_id") or "").strip()
        if beat.get("bid_ids"):
            result[beat_id] = "bridge"
        elif index < first_bid:
            result[beat_id] = "opening"
        elif index > last_bid:
            result[beat_id] = "epilogue"
        else:
            result[beat_id] = "transition"
    return result


def draft_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^(\d+)\.\s*$", text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if index == 0:
            opening = text[: match.start()].strip()
            if opening:
                body = f"{opening}\n\n{body}"
        sections[match.group(1)] = body
    return sections


def section_contract_scaffold(section_id: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "status": "pending",
        "source_excerpt": "",
        "source_emotion_beats": [],
        "target_outline_beats": [],
        "source_reversal_beat": 0,
        "target_reversal_beat": 0,
        "source_peak_beat": 0,
        "target_peak_beat": 0,
        "turning_point_selection_review": "",
        "source_emotion_beat_completion_review": "",
        "required_plot_beats": [],
        "plot_beat_completion_review": "",
        **{field: "" for field in REQUIRED_PLAN_FIELDS},
        "source_like_direct_emotion_preserved": None,
        "surface_copy_rejected": None,
        "manual_judgment": "",
    }


def section_review_scaffold(section_id: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "status": "pending",
        "beat_reviews": [],
        "complete_emotion_beat_review": "",
        "plot_beat_reviews": [],
        "complete_plot_beat_review": "",
        **{field: [] for field in REQUIRED_REVIEW_QUOTE_FIELDS},
        "old_wound_trigger_review": {
            "applicable": None,
            "target_quotes": [],
            "rationale": "",
        },
        "source_like_direct_emotion_preserved": None,
        "target_not_lower_intensity": None,
        "anti_ai_cleanup_applied_during_first_draft": None,
        "auxiliary_prose_voice_used": None,
        "surface_copy_rejected": None,
        "manual_judgment": "",
    }


def create_receipt(
    project: str,
    source_original: Path,
    source_emotion_ledger: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "mode": "source_dominant_first_draft",
        "bindings": {
            "primary_source_original": binding(source_original),
            "source_emotion_ledger": binding(source_emotion_ledger),
            "outline": None,
            "draft": None,
        },
        "first_draft_policy": {
            "primary_source_prose_dominant": True,
            "anti_ai_cleanup_applied_during_first_draft": False,
            "ai_audit_applied_during_first_draft": False,
            "source_like_direct_emotion_preserved": True,
            "auxiliary_prose_voice_allowed": False,
            "surface_copy_rejected": True,
            "obvious_gpt_contamination_blocked_as_source_drift": True,
        },
        "section_contracts": [],
        "section_reviews": [],
        "reviewed_by_current_model": False,
        "prewrite_status": "pending",
        "draft_status": "pending",
    }


def load_source_emotion_ledger(
    path: Path,
    source_original: Path,
    errors: list[str],
) -> list[dict[str, Any]]:
    try:
        data = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"无法读取全文情绪颗粒总账: {exc}")
        return []
    if data.get("schema_version") != SOURCE_LEDGER_SCHEMA:
        errors.append("全文情绪颗粒总账 schema_version 不正确")
    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("全文情绪颗粒总账缺少 source")
    else:
        if source.get("sha1") != sha1_file(source_original):
            errors.append("全文情绪颗粒总账未绑定当前主体原文 SHA1")
        if source.get("line_count") != len(source_original.read_text(encoding="utf-8").splitlines()):
            errors.append("全文情绪颗粒总账原文行数绑定不一致")
    review = data.get("completeness_review")
    if not isinstance(review, dict):
        errors.append("全文情绪颗粒总账缺少 completeness_review")
    else:
        for field in (
            "all_source_lines_classified",
            "non_bid_beats_preserved",
            "bid_derived_after_full_inventory",
            "reviewed_by_current_model",
        ):
            if review.get(field) is not True:
                errors.append(f"全文情绪颗粒总账要求 {field}=true")
        if review.get("automation_used_for_semantic_judgment") is not False:
            errors.append(
                "全文情绪颗粒总账要求 automation_used_for_semantic_judgment=false"
            )
    source_lines = source_original.read_text(encoding="utf-8").splitlines()
    segments = data.get("coverage_segments")
    if not isinstance(segments, list) or not segments:
        errors.append("全文情绪颗粒总账 coverage_segments 为空")
        segments = []
    expected_line = 1
    segment_by_id: dict[str, dict[str, Any]] = {}
    segment_beat_ids: list[str] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            errors.append(f"全文情绪颗粒总账 coverage_segments[{index}] 不是对象")
            continue
        segment_id = str(segment.get("segment_id") or "").strip()
        start_line = segment.get("start_line")
        end_line = segment.get("end_line")
        kind = str(segment.get("kind") or "").strip()
        beat_ids = segment.get("beat_ids")
        if not segment_id or segment_id in segment_by_id:
            errors.append(f"全文情绪颗粒总账 segment_id 缺失或重复: {segment_id or index}")
        else:
            segment_by_id[segment_id] = segment
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            errors.append(f"全文情绪颗粒总账 {segment_id or index} 行范围必须是整数")
            continue
        if start_line != expected_line:
            errors.append(
                f"全文情绪颗粒总账行覆盖不连续: 应从 L{expected_line} 开始，实际从 L{start_line} 开始"
            )
        if end_line < start_line or end_line > len(source_lines):
            errors.append(f"全文情绪颗粒总账 {segment_id or index} 行范围非法")
        expected_line = end_line + 1
        if kind not in SOURCE_LEDGER_SEGMENT_KINDS:
            errors.append(f"全文情绪颗粒总账 {segment_id or index} kind 非法")
        if not isinstance(beat_ids, list):
            errors.append(f"全文情绪颗粒总账 {segment_id or index} beat_ids 必须是列表")
            beat_ids = []
        normalized_ids = [str(item).strip() for item in beat_ids if str(item).strip()]
        if kind == "emotion_bearing" and not normalized_ids:
            errors.append(f"全文情绪颗粒总账 {segment_id or index} 情绪段缺少 beat_id")
        if kind != "emotion_bearing" and normalized_ids:
            errors.append(f"全文情绪颗粒总账 {segment_id or index} 非情绪段不得挂 beat_id")
        segment_beat_ids.extend(normalized_ids)
    if expected_line != len(source_lines) + 1:
        errors.append("全文情绪颗粒总账未连续覆盖到主体原文末行")
    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        errors.append("全文情绪颗粒总账 beats 为空")
        return []
    source_text = source_original.read_text(encoding="utf-8")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    evidence_seen: set[str] = set()
    for index, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict):
            errors.append(f"全文情绪颗粒总账 beats[{index}] 不是对象")
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        segment_id = str(beat.get("segment_id") or "").strip()
        start_line = beat.get("start_line")
        end_line = beat.get("end_line")
        if not beat_id or beat_id in ids:
            errors.append(f"全文情绪颗粒总账 beat_id 缺失或重复: {beat_id or index}")
        ids.add(beat_id)
        for field in (
            "role",
            "content",
            "trigger",
            "relationship_position_change",
            "reader_effect",
            "narrative_function",
        ):
            if not non_empty_text(beat.get(field)):
                errors.append(f"全文情绪颗粒总账 {beat_id or index} 缺少 {field}")
        segment = segment_by_id.get(segment_id)
        if segment is None or beat_id not in [
            str(item).strip() for item in segment.get("beat_ids", [])
        ]:
            errors.append(f"全文情绪颗粒总账 {beat_id or index} 未绑定情绪承载段")
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            errors.append(f"全文情绪颗粒总账 {beat_id or index} 行范围必须是整数")
            source_slice = ""
        elif not 1 <= start_line <= end_line <= len(source_lines):
            errors.append(f"全文情绪颗粒总账 {beat_id or index} 行范围非法")
            source_slice = ""
        else:
            source_slice = "\n".join(source_lines[start_line - 1 : end_line])
            if segment and not (
                segment.get("start_line") <= start_line <= end_line <= segment.get("end_line")
            ):
                errors.append(f"全文情绪颗粒总账 {beat_id or index} 行范围越出绑定段")
        if not isinstance(beat.get("bid_ids"), list):
            errors.append(f"全文情绪颗粒总账 {beat_id or index} bid_ids 必须是列表")
        intensity = beat.get("intensity")
        if not isinstance(intensity, int) or isinstance(intensity, bool) or not 1 <= intensity <= 10:
            errors.append(f"全文情绪颗粒总账 {beat_id or index} intensity 非法")
        evidence = quote_list(beat.get("source_evidence"))
        if not evidence:
            errors.append(f"全文情绪颗粒总账 {beat_id or index} 缺少 source_evidence")
        for quote in evidence:
            if quote not in source_slice:
                errors.append(f"全文情绪颗粒总账 {beat_id or index} 证据不在绑定行范围")
            if quote in evidence_seen:
                errors.append(f"全文情绪颗粒总账 {beat_id or index} 复用了其他拍的证据")
            evidence_seen.add(quote)
        result.append(beat)
    result_ids = [str(beat.get("beat_id") or "").strip() for beat in result]
    if segment_beat_ids != result_ids:
        errors.append(
            "全文情绪颗粒总账 coverage_segments 的 beat_id 必须与 beats 全集同序相等"
        )
    return result


def bind_outline(data: dict[str, Any], outline: Path) -> dict[str, Any]:
    section_ids = outline_section_ids(outline.read_text(encoding="utf-8"))
    if not section_ids:
        raise ValueError("细纲未找到 `## 1.` 形式的数字小节")
    data["bindings"]["outline"] = binding(outline)
    data["bindings"]["draft"] = None
    data["section_contracts"] = [section_contract_scaffold(item) for item in section_ids]
    data["section_reviews"] = []
    data["prewrite_status"] = "pending"
    data["draft_status"] = "pending"
    data["reviewed_by_current_model"] = False
    data["updated_at"] = now_iso()
    return data


def bind_draft(data: dict[str, Any], draft: Path) -> dict[str, Any]:
    sections = draft_sections(draft.read_text(encoding="utf-8"))
    section_ids = list(sections)
    if not section_ids:
        raise ValueError("正文未找到独占一行的 `1.` 形式数字小节")
    data["bindings"]["draft"] = binding(draft)
    existing_reviews = {
        str(item.get("section_id") or ""): item
        for item in data.get("section_reviews", [])
        if isinstance(item, dict)
    }
    reviews: list[dict[str, Any]] = []
    for section_id, section_text in sections.items():
        section_sha256 = hashlib.sha256(section_text.encode("utf-8")).hexdigest()
        review = existing_reviews.get(section_id)
        if not review or review.get("section_sha256") != section_sha256:
            review = section_review_scaffold(section_id)
            review["section_sha256"] = section_sha256
        reviews.append(review)
    data["section_reviews"] = reviews
    data["draft_status"] = "pending"
    data["updated_at"] = now_iso()
    return data


def non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def quote_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def validate_binding(
    value: Any, expected: Path, label: str, errors: list[str]
) -> None:
    if not isinstance(value, dict):
        errors.append(f"缺少 {label} 绑定")
        return
    expected = expected.resolve()
    if not same_file_path(Path(str(value.get("path") or "")), expected):
        errors.append(f"{label} 绑定路径不一致")
    if value.get("sha256") != sha256_file(expected):
        errors.append(f"{label} SHA 已变化，必须重新绑定")


def validate_policy(data: dict[str, Any], errors: list[str]) -> None:
    if data.get("mode") != "source_dominant_first_draft":
        errors.append("首稿模式必须为 source_dominant_first_draft")
    policy = data.get("first_draft_policy")
    if not isinstance(policy, dict):
        errors.append("缺少 first_draft_policy")
        return
    required_true = (
        "primary_source_prose_dominant",
        "source_like_direct_emotion_preserved",
        "surface_copy_rejected",
        "obvious_gpt_contamination_blocked_as_source_drift",
    )
    required_false = (
        "anti_ai_cleanup_applied_during_first_draft",
        "ai_audit_applied_during_first_draft",
        "auxiliary_prose_voice_allowed",
    )
    for field in required_true:
        if policy.get(field) is not True:
            errors.append(f"首稿政策要求 {field}=true")
    for field in required_false:
        if policy.get(field) is not False:
            errors.append(f"首稿政策要求 {field}=false")


def validate_beat_list(
    beats: Any,
    evidence_key: str,
    evidence_text: str,
    label: str,
    errors: list[str],
    used_evidence: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(beats, list) or not beats:
        errors.append(f"{label} 必须填写从原文逐句盘出的全部实际情绪拍，不预设拍数")
        return []
    validated: list[dict[str, Any]] = []
    beat_ids: set[str] = set()
    if used_evidence is None:
        used_evidence = set()
    for index, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict):
            errors.append(f"{label}[{index}] 必须是对象")
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        role = str(beat.get("role") or "").strip()
        if not beat_id:
            errors.append(f"{label}[{index}] 缺少 beat_id")
        elif beat_id in beat_ids:
            errors.append(f"{label}[{index}] beat_id 重复: {beat_id}")
        else:
            beat_ids.add(beat_id)
        if not role:
            errors.append(f"{label}[{index}] 缺少 role")
        for field in ("trigger", "relationship_position_change", "reader_effect"):
            if not non_empty_text(beat.get(field)):
                errors.append(f"{label} {beat_id or index} 缺少 {field}")
        intensity = beat.get("intensity")
        if not isinstance(intensity, int) or isinstance(intensity, bool) or not 1 <= intensity <= 10:
            errors.append(f"{label} {beat_id or index} intensity 必须为 1-10 整数")
        evidence = quote_list(beat.get(evidence_key))
        if not evidence:
            errors.append(f"{label} {beat_id or index} 缺少 {evidence_key}")
        for quote in evidence:
            if not bound_text_contains(evidence_text, quote):
                errors.append(f"{label} {beat_id or index} 证据不在绑定文本中: {quote[:30]}")
            if quote in used_evidence:
                errors.append(f"{label} {beat_id or index} 与前拍复用证据，不能一证多拍")
            else:
                used_evidence.add(quote)
            if evidence_key == "outline_evidence" and len(
                re.sub(r"[\W_]", "", quote, flags=re.UNICODE)
            ) < 6:
                errors.append(
                    f"{label} {beat_id or index} outline_evidence 过短，不能用词组碎片伪造独占拍"
                )
        validated.append(beat)
    return validated


def validate_sequence_parity(
    source_beats: list[dict[str, Any]],
    target_beats: list[dict[str, Any]],
    item: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    source_ids = [str(beat.get("beat_id") or "").strip() for beat in source_beats]
    target_ids = [str(beat.get("beat_id") or "").strip() for beat in target_beats]
    source_roles = [str(beat.get("role") or "").strip() for beat in source_beats]
    target_roles = [str(beat.get("role") or "").strip() for beat in target_beats]
    if len(source_beats) != len(target_beats):
        errors.append(f"{label} 原文实际情绪拍与目标情绪拍数量必须一致，禁止漏拍或并拍")
    if source_ids != target_ids:
        errors.append(f"{label} 目标情绪拍必须沿用原文 beat_id 原顺序逐拍承接")
    if source_roles != target_roles:
        errors.append(f"{label} 原文实际情绪角色序列必须逐拍保留，不得概括或改并")
    for index, (source, target) in enumerate(zip(source_beats, target_beats), start=1):
        source_intensity = source.get("intensity")
        target_intensity = target.get("intensity")
        if isinstance(source_intensity, int) and isinstance(target_intensity, int):
            if target_intensity != source_intensity:
                errors.append(
                    f"{label} 第 {index} 个实际情绪拍目标烈度必须与主体原文精确一致，不得降级或抬高"
                )
        for field in ("trigger", "relationship_position_change", "reader_effect"):
            if str(target.get(field) or "").strip() == str(source.get(field) or "").strip():
                errors.append(
                    f"{label} 第 {index} 个实际情绪拍 {field} 仍照搬原文分析，未迁移到目标故事"
                )
        if len(str(target.get("target_story_adaptation") or "").strip()) < 20:
            errors.append(
                f"{label} 第 {index} 个实际情绪拍缺少具体 target_story_adaptation"
            )
        if len(str(target.get("target_evidence_coverage_review") or "").strip()) < 30:
            errors.append(
                f"{label} 第 {index} 个实际情绪拍缺少 target_evidence_coverage_review；"
                "必须说明目标证据覆盖了触发、关系后果和原拍的全部动作链"
            )
        else:
            coverage = normalize_bound_text(
                target.get("target_evidence_coverage_review")
            )
            for field, field_label in (
                ("trigger", "触发"),
                ("relationship_position_change", "关系位移"),
            ):
                field_value = normalize_bound_text(target.get(field)).strip()
                if field_value and field_value not in coverage:
                    errors.append(
                        f"{label} 第 {index} 个实际情绪拍的 target_evidence_coverage_review "
                        f"未实际覆盖{field_label}，不能用通用套话代判"
                    )
    for source_field, target_field, beat_name in (
        ("source_reversal_beat", "target_reversal_beat", "反刀拍"),
        ("source_peak_beat", "target_peak_beat", "峰值拍"),
    ):
        source_index = item.get(source_field)
        target_index = item.get(target_field)
        if not isinstance(source_index, int) or not 0 <= source_index <= len(source_beats):
            errors.append(f"{label} {source_field} 必须为 0（原文无此拍）或真实拍序号")
        if not isinstance(target_index, int) or not 0 <= target_index <= len(target_beats):
            errors.append(f"{label} {target_field} 必须为 0（原文无此拍）或真实拍序号")
        if isinstance(source_index, int) and isinstance(target_index, int):
            if source_index != target_index:
                errors.append(f"{label} 原文与目标{beat_name}必须同位")
    turn_review = str(item.get("turning_point_selection_review") or "").strip()
    if len(turn_review) < 30:
        errors.append(
            f"{label} turning_point_selection_review 过短；必须依据原文期待、关系和行动的实际转折选择，禁止按最高烈度自动猜"
        )
    else:
        for field in ("source_reversal_beat", "source_peak_beat"):
            beat_index = item.get(field)
            if isinstance(beat_index, int) and beat_index > 0 and beat_index <= len(source_ids):
                beat_id = source_ids[beat_index - 1]
                if beat_id not in turn_review:
                    errors.append(
                        f"{label} turning_point_selection_review 未点名 {field} 对应的 {beat_id}"
                    )


def validate_required_plot_beats(
    value: Any,
    outline_text: str,
    label: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} required_plot_beats 必须列出本节承接的全部细纲情节拍")
        return []
    result: list[dict[str, Any]] = []
    beat_ids: set[str] = set()
    evidence_seen: set[str] = set()
    for index, beat in enumerate(value, start=1):
        if not isinstance(beat, dict):
            errors.append(f"{label} required_plot_beats[{index}] 必须是对象")
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        action = str(beat.get("action") or "").strip()
        evidence = str(beat.get("outline_evidence") or "").strip()
        if not beat_id:
            errors.append(f"{label} required_plot_beats[{index}] 缺少 beat_id")
        elif beat_id in beat_ids:
            errors.append(f"{label} required_plot_beats beat_id 重复: {beat_id}")
        else:
            beat_ids.add(beat_id)
        if not action:
            errors.append(f"{label} {beat_id or index} 缺少 action")
        if not evidence or evidence not in outline_text:
            errors.append(f"{label} {beat_id or index} outline_evidence 不在绑定细纲中")
        elif evidence in evidence_seen:
            errors.append(f"{label} {beat_id or index} 与前情节拍复用细纲证据")
        else:
            evidence_seen.add(evidence)
        result.append(beat)
    return result


def validate_prewrite_data(
    data: dict[str, Any],
    source_original: Path,
    outline: Path,
    source_emotion_ledger: Path | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("情绪颗粒度合同 schema_version 不正确")
    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        errors.append("情绪颗粒度合同缺少 bindings")
        return errors, data
    validate_binding(bindings.get("primary_source_original"), source_original, "主体原文", errors)
    validate_binding(bindings.get("outline"), outline, "细纲", errors)
    if source_emotion_ledger is None:
        ledger_binding = bindings.get("source_emotion_ledger")
        if isinstance(ledger_binding, dict) and ledger_binding.get("path"):
            source_emotion_ledger = Path(str(ledger_binding["path"])).resolve()
    source_ledger_beats: list[dict[str, Any]] = []
    if source_emotion_ledger is None or not source_emotion_ledger.is_file():
        errors.append("缺少主体拆文的全文情绪颗粒总账")
    else:
        validate_binding(
            bindings.get("source_emotion_ledger"),
            source_emotion_ledger,
            "全文情绪颗粒总账",
            errors,
        )
        source_ledger_beats = load_source_emotion_ledger(
            source_emotion_ledger, source_original, errors
        )
    validate_policy(data, errors)
    source_text = source_original.read_text(encoding="utf-8")
    outline_text = outline.read_text(encoding="utf-8")
    try:
        outline_regions = outline_emotion_regions(outline_text)
    except ValueError as exc:
        errors.append(str(exc))
        outline_regions = {}
    expected_ids = outline_section_ids(outline_text)
    contracts = data.get("section_contracts")
    if not isinstance(contracts, list):
        errors.append("section_contracts 必须是列表")
        contracts = []
    by_id = {
        str(item.get("section_id")): item
        for item in contracts
        if isinstance(item, dict)
    }
    if list(by_id) != expected_ids:
        errors.append("逐节情绪合同必须按细纲数字小节完整覆盖且顺序一致")
    distributed_source_beats: list[dict[str, Any]] = []
    distributed_target_beats: list[dict[str, Any]] = []
    global_source_evidence: set[str] = set()
    global_target_evidence: set[str] = set()
    ledger_regions = source_beat_regions(source_ledger_beats)
    for section_id in expected_ids:
        item = by_id.get(section_id)
        if not item:
            continue
        label = f"第 {section_id} 节"
        if item.get("status") != "passed":
            errors.append(f"{label} 写前情绪合同未通过")
        excerpt = str(item.get("source_excerpt") or "").strip()
        if len(excerpt) < 20 or not bound_text_contains(source_text, excerpt):
            errors.append(f"{label} source_excerpt 必须是主体原文中的连续真实片段")
        source_beats = validate_beat_list(
            item.get("source_emotion_beats"),
            "source_evidence",
            source_text,
            f"{label} source_emotion_beats",
            errors,
            global_source_evidence,
        )
        distributed_source_beats.extend(source_beats)
        target_beats = validate_beat_list(
            item.get("target_outline_beats"),
            "outline_evidence",
            outline_text,
            f"{label} target_outline_beats",
            errors,
            global_target_evidence,
        )
        distributed_target_beats.extend(target_beats)
        for beat in target_beats:
            beat_id = str(beat.get("beat_id") or "").strip()
            source_region = ledger_regions.get(beat_id)
            target_region = str(beat.get("target_outline_region") or "").strip()
            if source_region in {"opening", "epilogue"}:
                if target_region != source_region:
                    errors.append(
                        f"{label} {beat_id} 是原文{'导语' if source_region == 'opening' else '尾声'}拍，必须落在目标 {source_region} 真实区域"
                    )
            elif target_region != f"section:{section_id}":
                errors.append(
                    f"{label} {beat_id} target_outline_region 必须是 section:{section_id}"
                )
            region_text = outline_regions.get(target_region)
            if region_text is None:
                errors.append(f"{label} {beat_id} 目标情绪区域不存在: {target_region or '<empty>'}")
            else:
                for quote in quote_list(beat.get("outline_evidence")):
                    if not bound_text_contains(region_text, quote):
                        errors.append(
                            f"{label} {beat_id} outline_evidence 不在声称的 {target_region} 区域内"
                        )
        validate_sequence_parity(source_beats, target_beats, item, label, errors)
        if len(str(item.get("source_emotion_beat_completion_review") or "").strip()) < 20:
            errors.append(f"{label} source_emotion_beat_completion_review 过短，必须说明如何逐句穷尽原文实际情绪拍")
        validate_required_plot_beats(
            item.get("required_plot_beats"), outline_text, label, errors
        )
        if len(str(item.get("plot_beat_completion_review") or "").strip()) < 20:
            errors.append(f"{label} plot_beat_completion_review 过短，必须说明本节如何承接全部分配情节拍")
        for field in REQUIRED_PLAN_FIELDS:
            if not non_empty_text(item.get(field)):
                errors.append(f"{label} 缺少 {field}")
        if item.get("source_like_direct_emotion_preserved") is not True:
            errors.append(f"{label} 必须保留主体原文式直接情绪与即时判断")
        if item.get("surface_copy_rejected") is not True:
            errors.append(f"{label} 必须确认拒绝表层复刻")
        if len(str(item.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{label} manual_judgment 过短")
    ledger_ids = [str(beat.get("beat_id") or "").strip() for beat in source_ledger_beats]
    distributed_ids = [
        str(beat.get("beat_id") or "").strip() for beat in distributed_source_beats
    ]
    if distributed_ids != ledger_ids:
        errors.append(
            "各节 source_emotion_beats 并集必须与全文情绪颗粒总账 beat_id 全集同序相等；"
            "禁止只迁移 BID 拍或漏掉导语、过场、回忆、后果、尾声拍"
        )
    ledger_by_id = {
        str(beat.get("beat_id") or "").strip(): beat for beat in source_ledger_beats
    }
    for beat in distributed_source_beats:
        beat_id = str(beat.get("beat_id") or "").strip()
        ledger_beat = ledger_by_id.get(beat_id)
        if ledger_beat is None:
            continue
        for field in (
            "role",
            "content",
            "trigger",
            "relationship_position_change",
            "reader_effect",
            "intensity",
            "narrative_function",
            "bid_ids",
        ):
            if beat.get(field) != ledger_beat.get(field):
                errors.append(f"{beat_id} {field} 与全文情绪颗粒总账不一致")
        if quote_list(beat.get("source_evidence")) != quote_list(ledger_beat.get("source_evidence")):
            errors.append(f"{beat_id} source_evidence 与全文情绪颗粒总账不一致")
    target_ids = [str(beat.get("beat_id") or "").strip() for beat in distributed_target_beats]
    if target_ids != ledger_ids:
        errors.append("各节 target_outline_beats 并集必须与全文情绪颗粒总账全集同序相等")
    if data.get("reviewed_by_current_model") is not True:
        errors.append("情绪颗粒度合同必须由当前模型逐节人工复核")
    if data.get("prewrite_status") != "passed":
        errors.append("prewrite_status 必须为 passed")
    return errors, data


def validate_quote_fields(
    item: dict[str, Any], section_text: str, label: str, errors: list[str]
) -> None:
    for field in REQUIRED_REVIEW_QUOTE_FIELDS:
        quotes = quote_list(item.get(field))
        if not quotes:
            errors.append(f"{label} 缺少 {field}")
        for quote in quotes:
            if quote not in section_text:
                errors.append(f"{label} {field} 引用不在本节正文中: {quote[:30]}")
    old_wound = item.get("old_wound_trigger_review")
    if not isinstance(old_wound, dict) or not isinstance(old_wound.get("applicable"), bool):
        errors.append(f"{label} 缺少 old_wound_trigger_review 人工裁决")
        return
    quotes = quote_list(old_wound.get("target_quotes"))
    if old_wound.get("applicable") is True and not quotes:
        errors.append(f"{label} 旧伤适用却没有正文证据")
    if old_wound.get("applicable") is False and not non_empty_text(old_wound.get("rationale")):
        errors.append(f"{label} 旧伤不适用必须说明原因")
    for quote in quotes:
        if quote not in section_text:
            errors.append(f"{label} 旧伤证据不在本节正文中: {quote[:30]}")


def validate_draft_data(
    data: dict[str, Any],
    source_original: Path,
    draft: Path,
    source_emotion_ledger: Path | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        return ["情绪颗粒度合同缺少 bindings"], data
    outline_binding = bindings.get("outline")
    outline_path = Path(str(outline_binding.get("path") or "")) if isinstance(outline_binding, dict) else None
    if outline_path is None or not outline_path.is_file():
        return ["情绪颗粒度合同绑定的细纲不存在"], data
    prewrite_errors, _ = validate_prewrite_data(
        data, source_original, outline_path, source_emotion_ledger
    )
    errors.extend(prewrite_errors)
    validate_binding(bindings.get("draft"), draft, "正文", errors)
    sections = draft_sections(draft.read_text(encoding="utf-8"))
    expected_ids = outline_section_ids(outline_path.read_text(encoding="utf-8"))
    if list(sections) != expected_ids:
        errors.append("正文数字小节必须与细纲完整对应且顺序一致")
    contracts = {
        str(item.get("section_id")): item
        for item in data.get("section_contracts", [])
        if isinstance(item, dict)
    }
    reviews = data.get("section_reviews")
    if not isinstance(reviews, list):
        errors.append("section_reviews 必须是列表")
        reviews = []
    by_id = {
        str(item.get("section_id")): item for item in reviews if isinstance(item, dict)
    }
    if list(by_id) != expected_ids:
        errors.append("逐节正文情绪复核必须完整覆盖且顺序一致")
    global_emotion_quotes: set[str] = set()
    global_plot_quotes: set[str] = set()
    for section_id in expected_ids:
        item = by_id.get(section_id)
        if not item:
            continue
        label = f"第 {section_id} 节"
        section_text = sections.get(section_id, "")
        if item.get("status") != "passed":
            errors.append(f"{label} 正文情绪复核未通过")
        contract = contracts.get(section_id, {})
        source_beats = [
            beat
            for beat in contract.get("source_emotion_beats", [])
            if isinstance(beat, dict)
        ]
        beat_reviews = item.get("beat_reviews")
        if not isinstance(beat_reviews, list):
            errors.append(f"{label} beat_reviews 必须是列表")
            beat_reviews = []
        source_ids = [str(beat.get("beat_id") or "").strip() for beat in source_beats]
        review_ids = [
            str(beat.get("beat_id") or "").strip()
            for beat in beat_reviews
            if isinstance(beat, dict)
        ]
        if review_ids != source_ids:
            errors.append(f"{label} beat_reviews 必须按写前合同的全部 beat_id 原顺序完整覆盖")
        for index, (source_beat, beat) in enumerate(zip(source_beats, beat_reviews), start=1):
            if not isinstance(beat, dict):
                errors.append(f"{label} beat_reviews[{index}] 必须是对象")
                continue
            beat_id = str(source_beat.get("beat_id") or "").strip()
            role = str(source_beat.get("role") or "").strip()
            if str(beat.get("role") or "").strip() != role:
                errors.append(f"{label} {beat_id} role 未按写前合同逐拍回填")
            source_intensity = beat.get("source_intensity")
            target_intensity = beat.get("target_intensity")
            if source_intensity != source_beat.get("intensity"):
                errors.append(f"{label} {beat_id} source_intensity 未按写前合同回填")
            if not isinstance(target_intensity, int) or isinstance(target_intensity, bool) or not 1 <= target_intensity <= 10:
                errors.append(f"{label} {beat_id} target_intensity 必须为 1-10 整数")
            elif isinstance(source_intensity, int) and target_intensity != source_intensity:
                errors.append(
                    f"{label} {beat_id} 正文烈度必须与主体原文精确一致，不得降级或抬高"
                )
            quotes = quote_list(beat.get("target_quotes"))
            if not quotes:
                errors.append(f"{label} {beat_id} 缺少正文情绪拍证据")
            for quote in quotes:
                if quote not in section_text:
                    errors.append(f"{label} {beat_id} 引用不在本节正文中: {quote[:30]}")
                if quote in global_emotion_quotes:
                    errors.append(f"{label} {beat_id} 与全文其他拍复用正文证据，不能一证多拍")
                else:
                    global_emotion_quotes.add(quote)
            if len(str(beat.get("parity_judgment") or "").strip()) < 12:
                errors.append(f"{label} {beat_id} parity_judgment 过短")
        if len(str(item.get("complete_emotion_beat_review") or "").strip()) < 20:
            errors.append(f"{label} complete_emotion_beat_review 过短，必须确认全部实际拍均已在正文兑现")
        required_plot_beats = [
            beat
            for beat in contract.get("required_plot_beats", [])
            if isinstance(beat, dict)
        ]
        plot_reviews = item.get("plot_beat_reviews")
        if not isinstance(plot_reviews, list):
            errors.append(f"{label} plot_beat_reviews 必须是列表")
            plot_reviews = []
        required_plot_ids = [
            str(beat.get("beat_id") or "").strip() for beat in required_plot_beats
        ]
        review_plot_ids = [
            str(beat.get("beat_id") or "").strip()
            for beat in plot_reviews
            if isinstance(beat, dict)
        ]
        if review_plot_ids != required_plot_ids:
            errors.append(f"{label} plot_beat_reviews 必须按写前合同原顺序兑现全部情节拍")
        for index, review in enumerate(plot_reviews, start=1):
            if not isinstance(review, dict):
                continue
            beat_id = str(review.get("beat_id") or "").strip()
            quotes = quote_list(review.get("target_quotes"))
            if not quotes:
                errors.append(f"{label} {beat_id or index} 缺少正文情节拍证据")
            for quote in quotes:
                if quote not in section_text:
                    errors.append(f"{label} {beat_id or index} 情节拍引句不在本节正文中")
                if quote in global_plot_quotes:
                    errors.append(f"{label} {beat_id or index} 与全文其他情节拍复用正文证据")
                else:
                    global_plot_quotes.add(quote)
            if len(str(review.get("consequence_judgment") or "").strip()) < 12:
                errors.append(f"{label} {beat_id or index} consequence_judgment 过短")
        if len(str(item.get("complete_plot_beat_review") or "").strip()) < 20:
            errors.append(f"{label} complete_plot_beat_review 过短，必须确认全部情节拍均在正文兑现")
        validate_quote_fields(item, section_text, label, errors)
        expected_flags = {
            "source_like_direct_emotion_preserved": True,
            "target_not_lower_intensity": True,
            "anti_ai_cleanup_applied_during_first_draft": False,
            "auxiliary_prose_voice_used": False,
            "surface_copy_rejected": True,
        }
        for field, expected in expected_flags.items():
            if item.get(field) is not expected:
                errors.append(f"{label} 要求 {field}={str(expected).lower()}")
        if len(str(item.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{label} manual_judgment 过短")
    if data.get("draft_status") != "passed":
        errors.append("draft_status 必须为 passed")
    return errors, data


def validate_section_progress_receipt(progress_path: Path, draft_path: Path) -> list[str]:
    if not progress_path.is_file():
        return [f"逐节正文进度回执不存在: {progress_path}"]
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"逐节正文进度回执无效: {exc}"]
    errors: list[str] = []
    draft = draft_path.resolve()
    if progress.get("status") != "final_ready":
        errors.append(f"逐节正文进度未 final_ready: {progress.get('status')}")
    if str((progress.get("paths") or {}).get("draft") or "") != str(draft):
        errors.append("逐节进度回执绑定的正文路径不一致")
    if not draft.is_file():
        errors.append(f"正文不存在: {draft}")
    elif progress.get("final_draft_sha256") != sha256_file(draft):
        errors.append("正文 SHA 与逐节进度 final_ready 绑定不一致")
    sections = progress.get("sections")
    if not isinstance(sections, list) or not sections or any(
        not isinstance(item, dict) or item.get("status") != "passed" for item in sections
    ):
        errors.append("逐节进度回执中存在未 passed 小节")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--source-original", required=True)
    init_parser.add_argument("--source-emotion-ledger", required=True)
    init_parser.add_argument("--receipt", required=True)

    for command in ("bind-outline", "validate-prewrite", "bind-draft", "validate-draft"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--receipt", required=True)
        if command in ("bind-outline", "validate-prewrite"):
            sub.add_argument("--outline", required=True)
        if command in ("bind-draft", "validate-draft"):
            sub.add_argument("--draft", required=True)
            sub.add_argument("--section-progress", required=True)
        if command in ("validate-prewrite", "validate-draft"):
            sub.add_argument("--source-original", required=True)
            sub.add_argument("--source-emotion-ledger", required=True)

    args = parser.parse_args()
    receipt = Path(args.receipt).resolve()
    if args.command == "init":
        data = create_receipt(
            args.project,
            Path(args.source_original).resolve(),
            Path(args.source_emotion_ledger).resolve(),
        )
        write_json(receipt, data)
        print(f"emotional_granularity_contract: initialized -> {receipt}")
        return 0

    data = load_json(receipt)
    if args.command == "bind-outline":
        data = bind_outline(data, Path(args.outline).resolve())
        write_json(receipt, data)
        print("emotional_granularity_contract: outline bound")
        return 0
    if args.command == "bind-draft":
        progress_errors = validate_section_progress_receipt(
            Path(args.section_progress).resolve(), Path(args.draft).resolve()
        )
        if progress_errors:
            print("emotional_granularity_contract: blocked (bind-draft)")
            for error in progress_errors:
                print(f"- {error}")
            return 2
        data = bind_draft(data, Path(args.draft).resolve())
        write_json(receipt, data)
        print("emotional_granularity_contract: draft bound")
        return 0
    if args.command == "validate-prewrite":
        errors, _ = validate_prewrite_data(
            data,
            Path(args.source_original).resolve(),
            Path(args.outline).resolve(),
            Path(args.source_emotion_ledger).resolve(),
        )
    else:
        errors, _ = validate_draft_data(
            data,
            Path(args.source_original).resolve(),
            Path(args.draft).resolve(),
            Path(args.source_emotion_ledger).resolve(),
        )
        errors = validate_section_progress_receipt(
            Path(args.section_progress).resolve(), Path(args.draft).resolve()
        ) + errors
    if errors:
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"emotional_granularity_contract: passed ({args.command})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
