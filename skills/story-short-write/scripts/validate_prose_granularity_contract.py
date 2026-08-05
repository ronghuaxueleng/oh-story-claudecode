#!/usr/bin/env python3
"""Validate the primary-source prose granularity contract for short fiction."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_DIMENSIONS = (
    "sentence_motion",
    "lexical_register",
    "narrator_voice",
    "paragraph_breath",
    "dialogue_connection",
    "emotion_wording",
    "productive_roughness",
)
SOURCE_STYLE_GRANULARITY_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)


def normalized_manual_text(value: Any) -> str:
    """Normalize identifiers away so templated semantic judgments compare equal."""
    text = str(value or "").strip().lower()
    text = re.sub(r"sf[-_ ]?\d+", "<sf>", text, flags=re.IGNORECASE)
    text = re.sub(r"第?\s*\d+\s*节", "<section>", text)
    for field in (*SOURCE_STYLE_GRANULARITY_FIELDS, *REQUIRED_DIMENSIONS):
        text = text.replace(field.lower(), "<field>")
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subflow_catalog_path(source: Path) -> Path:
    return source.parent.parent / "写作资产" / "子流程索引.jsonl"


def subflow_records_from_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"主体原文子流程索引不存在: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"子流程索引 JSONL 第 {line_number} 行无效: {path}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"子流程索引第 {line_number} 行必须是对象: {path}")
        records.append(record)
    if not records:
        raise ValueError(f"主体原文子流程索引为空: {path}")
    return records


def source_subflow_review_scaffold(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "subflow_id": record.get("subflow_id", ""),
        "parent_bridge_id": record.get("parent_bridge_id", ""),
        "source_range": record.get("source_range", ""),
        "source_style_granularity": record.get("source_style_granularity", {}),
        "status": "pending",
        "target_sections": [],
        "target_section_rationale": "",
        "semantic_review_method": "current_model_manual",
        "automation_used_for_semantic_judgment": None,
        "dimension_transfers": {
            field: {
                "source_evidence": nonempty_strings(
                    (record.get("source_style_granularity") or {}).get(field, {}).get(
                        "source_evidence"
                    )
                ),
                "evidence_mappings": [
                    {
                        "source_quote": quote,
                        "target_quotes": [],
                        "comparison": "",
                    }
                    for quote in nonempty_strings(
                        (record.get("source_style_granularity") or {})
                        .get(field, {})
                        .get("source_evidence")
                    )
                ],
                "target_quotes": [],
                "comparison": "",
                "cross_dimension_reuse_justification": "",
                "surface_copy_rejected": None,
            }
            for field in SOURCE_STYLE_GRANULARITY_FIELDS
        },
        "source_voice_preserved": None,
        "functional_alignment_used_as_prose_proof": None,
        "extra_ai_shell": None,
        "manual_judgment": "",
    }


def create_receipt(project: str, source_original: Path) -> dict[str, Any]:
    source = source_original.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"主体原文不存在: {source}")
    subflow_catalog = subflow_catalog_path(source)
    subflow_records = subflow_records_from_catalog(subflow_catalog)
    subflow_ids = [str(record.get("subflow_id") or "").strip() for record in subflow_records]
    if any(not subflow_id for subflow_id in subflow_ids) or len(set(subflow_ids)) != len(subflow_ids):
        raise ValueError(f"主体原文子流程索引存在空或重复 subflow_id: {subflow_catalog}")
    return {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "prewrite_status": "pending",
        "execution_mode": "current_model_manual",
        "reviewed_by_current_model": False,
        "primary_prose_source": {
            "path": str(source),
            "sha256": sha256(source),
            "role": "primary_only",
        },
        "auxiliary_sources_supply_prose": False,
        "primary_subflow_catalog": {
            "path": str(subflow_catalog.resolve()),
            "sha256": sha256(subflow_catalog),
            "required_subflow_ids": subflow_ids,
        },
        "source_baseline": {
            "continuous_excerpts": [],
            "dimensions": {
                name: {
                    "rule": "",
                    "source_quotes": [],
                    "transfer_rule": "",
                    "ai_drift_to_reject": "",
                }
                for name in REQUIRED_DIMENSIONS
            },
            "anti_patterns": [],
            "manual_judgment": "",
        },
        "calibration_samples": [],
        "draft": None,
        "section_reviews": [],
        "source_subflow_reviews": [
            source_subflow_review_scaffold(record) for record in subflow_records
        ],
        "full_text_review": {
            "reviewed_full_text": False,
            "all_sections_reviewed": False,
            "primary_source_voice_dominant": False,
            "auxiliary_style_contamination": None,
            "functional_alignment_used_as_prose_proof": None,
            "remaining_extra_ai_shell": None,
            "conclusion": "",
        },
        "blocking_failures": [],
    }


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_source_binding(
    data: dict[str, Any], source_original: Path, errors: list[str]
) -> str:
    source = source_original.resolve()
    if not source.is_file():
        errors.append(f"主体原文不存在: {source}")
        return ""
    binding = data.get("primary_prose_source")
    if not isinstance(binding, dict):
        errors.append("primary_prose_source 必须是对象")
        return read_text(source)
    if str(binding.get("path") or "") != str(source):
        errors.append("文字颗粒度合同绑定的主体原文路径不一致")
    if binding.get("sha256") != sha256(source):
        errors.append("主体原文已变化，必须重建文字颗粒度合同")
    if binding.get("role") != "primary_only":
        errors.append("主体原文必须是唯一 prose source")
    return read_text(source)


def validate_source_quote(
    quote: str, source_text: str, label: str, errors: list[str]
) -> bool:
    if not quote or quote not in source_text:
        errors.append(f"{label}不是主体原文真实连续引用")
        return False
    return True


def validate_subflow_catalog_data(
    data: dict[str, Any],
    source_original: Path,
    source_text: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    source = source_original.resolve()
    expected_path = subflow_catalog_path(source).resolve()
    binding = data.get("primary_subflow_catalog")
    if not isinstance(binding, dict):
        errors.append("primary_subflow_catalog 必须绑定主体子流程索引")
        return []
    if str(binding.get("path") or "") != str(expected_path):
        errors.append("文字颗粒度合同绑定的主体子流程索引路径不一致")
    if not expected_path.is_file():
        errors.append(f"主体原文子流程索引不存在: {expected_path}")
        return []
    if binding.get("sha256") != sha256(expected_path):
        errors.append("主体子流程索引已变化，必须重建文字颗粒度合同")
    try:
        records = subflow_records_from_catalog(expected_path)
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
        return []
    ids: list[str] = []
    for index, record in enumerate(records, start=1):
        label = f"主体子流程[{index}]"
        subflow_id = str(record.get("subflow_id") or "").strip()
        if not subflow_id:
            errors.append(f"{label}.subflow_id 不能为空")
        ids.append(subflow_id)
        style = record.get("source_style_granularity")
        if not isinstance(style, dict):
            errors.append(f"{label}.source_style_granularity 必须是对象")
            continue
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            item = style.get(field)
            if not isinstance(item, dict):
                errors.append(f"{label} 缺少六类颗粒字段: {field}")
                continue
            if not str(item.get("analysis") or "").strip():
                errors.append(f"{label}.{field}.analysis 不能为空")
            evidence = nonempty_strings(item.get("source_evidence"))
            if len(evidence) < 2:
                errors.append(f"{label}.{field}.source_evidence 至少两条")
            for quote in evidence:
                validate_source_quote(quote, source_text, f"{label}.{field}", errors)
    if len(set(ids)) != len(ids):
        errors.append("主体子流程索引 subflow_id 不得重复")
    if binding.get("required_subflow_ids") != ids:
        errors.append("primary_subflow_catalog.required_subflow_ids 必须覆盖全部 SF")
    return records


def validate_prewrite_data(
    data: dict[str, Any], source_original: Path
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    source_text = validate_source_binding(data, source_original, errors)
    subflow_records = validate_subflow_catalog_data(
        data, source_original, source_text, errors
    )
    if data.get("execution_mode") != "current_model_manual":
        errors.append("execution_mode 必须为 current_model_manual")
    if data.get("reviewed_by_current_model") is not True:
        errors.append("必须由当前写作模型人工建立文字颗粒度基线")
    if data.get("auxiliary_sources_supply_prose") is not False:
        errors.append("辅助来源不得供应正文声线，只能供应情节与场面机制")

    baseline = data.get("source_baseline")
    if not isinstance(baseline, dict):
        errors.append("source_baseline 必须是对象")
        baseline = {}
    excerpts = baseline.get("continuous_excerpts")
    valid_excerpts = 0
    if not isinstance(excerpts, list):
        errors.append("source_baseline.continuous_excerpts 必须是列表")
    else:
        purposes: set[str] = set()
        for index, item in enumerate(excerpts, start=1):
            if not isinstance(item, dict):
                errors.append(f"连续原文样本格式错误: [{index}]")
                continue
            quote = str(item.get("quote") or "").strip()
            purpose = str(item.get("purpose") or "").strip()
            judgment = str(item.get("language_judgment") or "").strip()
            if validate_source_quote(quote, source_text, f"连续原文样本[{index}]", errors):
                if len(quote) < 40:
                    errors.append(f"连续原文样本过短，不能用金句代替气口样本: [{index}]")
                elif purpose and judgment:
                    valid_excerpts += 1
            if not purpose:
                errors.append(f"连续原文样本缺少 purpose: [{index}]")
            else:
                purposes.add(purpose)
            if not judgment:
                errors.append(f"连续原文样本缺少 language_judgment: [{index}]")
        if valid_excerpts < 5:
            errors.append("至少需要 5 组四十字以上的主体原文连续样本")
        if len(purposes) < 4:
            errors.append("连续样本必须覆盖至少 4 类语言场景")

    dimensions = baseline.get("dimensions")
    if not isinstance(dimensions, dict):
        errors.append("source_baseline.dimensions 必须是对象")
        dimensions = {}
    for name in REQUIRED_DIMENSIONS:
        item = dimensions.get(name)
        if not isinstance(item, dict):
            errors.append(f"缺少文字颗粒度维度: {name}")
            continue
        for field in ("rule", "transfer_rule", "ai_drift_to_reject"):
            if not str(item.get(field) or "").strip():
                errors.append(f"文字颗粒度维度 {name}.{field} 不能为空")
        quotes = nonempty_strings(item.get("source_quotes"))
        if len(quotes) < 2:
            errors.append(f"文字颗粒度维度 {name} 至少需要 2 条原文证据")
        for index, quote in enumerate(quotes, start=1):
            validate_source_quote(quote, source_text, f"{name}.source_quotes[{index}]", errors)

    anti_patterns = baseline.get("anti_patterns")
    if not isinstance(anti_patterns, list) or len(anti_patterns) < 3:
        errors.append("至少需要 3 条主体原文不像的 AI 句面反例")
    else:
        for index, item in enumerate(anti_patterns, start=1):
            if not isinstance(item, dict):
                errors.append(f"anti_patterns 格式错误: [{index}]")
                continue
            if not str(item.get("pattern") or "").strip():
                errors.append(f"anti_patterns 缺少 pattern: [{index}]")
            if not str(item.get("why_unlike_source") or "").strip():
                errors.append(f"anti_patterns 缺少 why_unlike_source: [{index}]")
    if not str(baseline.get("manual_judgment") or "").strip():
        errors.append("source_baseline.manual_judgment 不能为空")

    samples = data.get("calibration_samples")
    valid_samples = 0
    if not isinstance(samples, list) or len(samples) < 3:
        errors.append("正文前至少需要 3 组主体原文—原创试写校准样本")
    else:
        for index, item in enumerate(samples, start=1):
            if not isinstance(item, dict):
                errors.append(f"calibration_samples 格式错误: [{index}]")
                continue
            source_quote = str(item.get("source_quote") or "").strip()
            target_sample = str(item.get("target_sample") or "").strip()
            comparison = str(item.get("comparison") or "").strip()
            valid = validate_source_quote(
                source_quote, source_text, f"calibration_samples[{index}].source_quote", errors
            )
            if len(source_quote) < 20:
                errors.append(f"校准原文样本过短: [{index}]")
                valid = False
            if len(target_sample) < 20:
                errors.append(f"原创校准样本过短: [{index}]")
                valid = False
            if not comparison:
                errors.append(f"校准样本缺少人工句面对照: [{index}]")
                valid = False
            if item.get("functional_alignment_used_as_prose_proof") is not False:
                errors.append(f"校准样本不得用功能对齐冒充文字对齐: [{index}]")
                valid = False
            if item.get("extra_ai_shell") is not False:
                errors.append(f"校准样本仍含新增 AI 句面壳: [{index}]")
                valid = False
            if valid:
                valid_samples += 1

    if data.get("prewrite_status") != "passed":
        errors.append("prewrite_status 必须为 passed")
    return errors, {
        "valid_excerpts": valid_excerpts,
        "required_dimensions": len(REQUIRED_DIMENSIONS),
        "valid_calibration_samples": valid_samples,
        "required_subflows": len(subflow_records),
    }


def extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^\s*(?:#{1,6}\s*)?(\d+)\.\s*(?:.*)?$", line)
        if match:
            current = match.group(1)
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    if not sections:
        return {"full": text}
    return {key: "\n".join(lines) for key, lines in sections.items()}


def bind_draft(data: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    draft = draft_path.resolve()
    if not draft.is_file():
        raise FileNotFoundError(f"正文不存在: {draft}")
    sections = extract_sections(read_text(draft))
    data["gate_status"] = "pending"
    data["draft"] = {"path": str(draft), "sha256": sha256(draft)}
    data["section_reviews"] = [
        {
            "section_id": section_id,
            "status": "pending",
            "target_quotes": [],
            "source_anchors": [],
            "dimensions_checked": [],
            "source_voice_preserved": None,
            "functional_alignment_used_as_prose_proof": None,
            "extra_ai_shell": None,
            "comparison": "",
        }
        for section_id in sections
    ]
    existing_subflows = data.get("source_subflow_reviews")
    if not isinstance(existing_subflows, list):
        existing_subflows = []
    data["source_subflow_reviews"] = [
        source_subflow_review_scaffold(item)
        for item in existing_subflows
        if isinstance(item, dict)
    ]
    data["full_text_review"] = {
        "reviewed_full_text": False,
        "all_sections_reviewed": False,
        "primary_source_voice_dominant": False,
        "auxiliary_style_contamination": None,
        "functional_alignment_used_as_prose_proof": None,
        "remaining_extra_ai_shell": None,
        "conclusion": "",
    }
    data["blocking_failures"] = []
    return data


def validate_source_subflow_reviews(
    data: dict[str, Any],
    source_original: Path,
    sections: dict[str, str],
    errors: list[str],
) -> int:
    source = source_original.resolve()
    source_text = read_text(source)
    try:
        records = subflow_records_from_catalog(subflow_catalog_path(source))
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
        return 0
    records_by_id = {
        str(record.get("subflow_id") or "").strip(): record for record in records
    }
    reviews = data.get("source_subflow_reviews")
    if not isinstance(reviews, list):
        errors.append("source_subflow_reviews 必须逐 SF 证明正文消费了全部颗粒")
        return 0
    reviews_by_id: dict[str, dict[str, Any]] = {}
    for index, review in enumerate(reviews, start=1):
        label = f"主体 SF 正文复核[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label} 必须是对象")
            continue
        subflow_id = str(review.get("subflow_id") or "").strip()
        if not subflow_id:
            errors.append(f"{label}.subflow_id 不能为空")
            continue
        if subflow_id in reviews_by_id:
            errors.append(f"{label}.subflow_id 重复: {subflow_id}")
            continue
        reviews_by_id[subflow_id] = review

    passed = 0
    rationale_signatures: dict[str, list[str]] = {}
    judgment_signatures: dict[str, list[str]] = {}
    for subflow_id, record in records_by_id.items():
        label = f"主体 SF {subflow_id}"
        review = reviews_by_id.get(subflow_id)
        if review is None:
            errors.append(f"主体原文 SF 未进入正文颗粒复核: {subflow_id}")
            continue
        valid = True
        for field in ("parent_bridge_id", "source_range", "source_style_granularity"):
            if review.get(field) != record.get(field):
                errors.append(f"{label}.{field} 与主体子流程索引不一致")
                valid = False
        if review.get("status") != "passed":
            errors.append(f"{label}.status 必须为 passed")
            valid = False
        if review.get("semantic_review_method") != "current_model_manual":
            errors.append(f"{label}.semantic_review_method 必须为 current_model_manual")
            valid = False
        if review.get("automation_used_for_semantic_judgment") is not False:
            errors.append(f"{label} 禁止用自动脚本生成语义裁决")
            valid = False
        target_sections = nonempty_strings(review.get("target_sections"))
        if not target_sections:
            errors.append(f"{label}.target_sections 不能为空")
            valid = False
        target_text = "\n".join(
            sections[section_id]
            for section_id in target_sections
            if section_id in sections
        )
        for section_id in target_sections:
            if section_id not in sections:
                errors.append(f"{label}.target_sections 引用了不存在的小节: {section_id}")
                valid = False
        target_section_rationale = str(review.get("target_section_rationale") or "").strip()
        if len(target_section_rationale) < 12:
            errors.append(f"{label}.target_section_rationale 必须具体说明 SF 为何落到目标小节")
            valid = False
        else:
            rationale_signatures.setdefault(
                normalized_manual_text(target_section_rationale), []
            ).append(subflow_id)
        transfers = review.get("dimension_transfers")
        if not isinstance(transfers, dict):
            errors.append(f"{label}.dimension_transfers 必须逐项覆盖六类颗粒")
            transfers = {}
            valid = False
        quote_signatures: dict[tuple[str, ...], list[str]] = {}
        transfer_comparison_signatures: dict[str, list[str]] = {}
        mapping_comparison_signatures: dict[str, list[str]] = {}
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            transfer = transfers.get(field)
            if not isinstance(transfer, dict):
                errors.append(f"{label} 缺少正文颗粒迁移: {field}")
                valid = False
                continue
            quotes = nonempty_strings(transfer.get("target_quotes"))
            if not quotes:
                errors.append(f"{label}.{field}.target_quotes 至少一条目标原句")
                valid = False
            for quote in quotes:
                if quote not in target_text:
                    errors.append(f"{label}.{field} 目标原句不在绑定小节中: {quote!r}")
                    valid = False
            if quotes:
                quote_signatures.setdefault(tuple(sorted(set(quotes))), []).append(field)
            source_evidence = nonempty_strings(transfer.get("source_evidence"))
            expected_source_evidence = nonempty_strings(
                (record.get("source_style_granularity") or {}).get(field, {}).get(
                    "source_evidence"
                )
            )
            if source_evidence != expected_source_evidence:
                errors.append(
                    f"{label}.{field}.source_evidence 必须完整原样覆盖主体字段证据"
                )
                valid = False
            for quote in source_evidence:
                if quote not in source_text:
                    errors.append(f"{label}.{field} 主体证据不在原文中: {quote!r}")
                    valid = False
            mappings = transfer.get("evidence_mappings")
            if not isinstance(mappings, list):
                errors.append(f"{label}.{field}.evidence_mappings 必须逐条映射主体证据")
                mappings = []
                valid = False
            mapped_source_quotes = [
                str(item.get("source_quote") or "").strip()
                for item in mappings
                if isinstance(item, dict)
            ]
            if mapped_source_quotes != expected_source_evidence:
                errors.append(
                    f"{label}.{field}.evidence_mappings 必须逐条覆盖全部主体证据"
                )
                valid = False
            for mapping_index, mapping in enumerate(mappings, start=1):
                if not isinstance(mapping, dict):
                    errors.append(f"{label}.{field}.evidence_mappings[{mapping_index}] 必须是对象")
                    valid = False
                    continue
                mapped_targets = nonempty_strings(mapping.get("target_quotes"))
                if not mapped_targets:
                    errors.append(
                        f"{label}.{field}.evidence_mappings[{mapping_index}] 至少绑定一条目标原句"
                    )
                    valid = False
                for quote in mapped_targets:
                    if quote not in target_text:
                        errors.append(
                            f"{label}.{field}.evidence_mappings[{mapping_index}] 目标原句不在绑定小节中: {quote!r}"
                        )
                        valid = False
                mapping_comparison = str(mapping.get("comparison") or "").strip()
                if not mapping_comparison:
                    errors.append(
                        f"{label}.{field}.evidence_mappings[{mapping_index}].comparison 不能为空"
                    )
                    valid = False
                else:
                    mapping_comparison_signatures.setdefault(
                        normalized_manual_text(mapping_comparison), []
                    ).append(f"{field}[{mapping_index}]")
            transfer_comparison = str(transfer.get("comparison") or "").strip()
            if not transfer_comparison:
                errors.append(f"{label}.{field}.comparison 不能为空")
                valid = False
            else:
                transfer_comparison_signatures.setdefault(
                    normalized_manual_text(transfer_comparison), []
                ).append(field)
            if transfer.get("surface_copy_rejected") is not True:
                errors.append(f"{label}.{field}.surface_copy_rejected 必须为 true")
                valid = False
        for fields in quote_signatures.values():
            if len(fields) < 2:
                continue
            justifications: dict[str, list[str]] = {}
            for field in fields:
                transfer = transfers.get(field) or {}
                justification = str(
                    transfer.get("cross_dimension_reuse_justification") or ""
                ).strip()
                if len(justification) < 12:
                    errors.append(
                        f"{label} 跨字段复用同一组目标句时必须逐字段说明: {field}"
                    )
                    valid = False
                    continue
                justifications.setdefault(
                    normalized_manual_text(justification), []
                ).append(field)
            for reused_fields in justifications.values():
                if len(reused_fields) > 1:
                    errors.append(
                        f"{label} 跨字段复用理由不得模板化: " + ", ".join(reused_fields)
                    )
                    valid = False
        for fields in transfer_comparison_signatures.values():
            if len(fields) > 1:
                errors.append(
                    f"{label} 六类颗粒 comparison 不得只替换字段名: " + ", ".join(fields)
                )
                valid = False
        for mappings in mapping_comparison_signatures.values():
            if len(mappings) > 1:
                errors.append(
                    f"{label} 逐证据句面对照不得模板化: " + ", ".join(mappings)
                )
                valid = False
        for field, expected in (
            ("source_voice_preserved", True),
            ("functional_alignment_used_as_prose_proof", False),
            ("extra_ai_shell", False),
        ):
            if review.get(field) is not expected:
                errors.append(f"{label}.{field} 必须为 {expected}")
                valid = False
        manual_judgment = str(review.get("manual_judgment") or "").strip()
        if len(manual_judgment) < 12:
            errors.append(f"{label}.manual_judgment 不能为空")
            valid = False
        else:
            judgment_signatures.setdefault(
                normalized_manual_text(manual_judgment), []
            ).append(subflow_id)
        if valid:
            passed += 1
    for subflows in rationale_signatures.values():
        if len(subflows) > 1:
            errors.append("不同 SF 不得复用模板化目标小节理由: " + ", ".join(subflows))
    for subflows in judgment_signatures.values():
        if len(subflows) > 1:
            errors.append("不同 SF 不得复用模板化人工裁决: " + ", ".join(subflows))
    extra = sorted(set(reviews_by_id) - set(records_by_id))
    if extra:
        errors.append("正文颗粒复核引用不存在的主体 SF: " + ", ".join(extra))
    return passed


def validate_draft_data(
    data: dict[str, Any], source_original: Path, draft_path: Path
) -> tuple[list[str], dict[str, int]]:
    errors, summary = validate_prewrite_data(data, source_original)
    draft = draft_path.resolve()
    if not draft.is_file():
        errors.append(f"正文不存在: {draft}")
        return errors, summary
    draft_text = read_text(draft)
    binding = data.get("draft")
    if not isinstance(binding, dict):
        errors.append("draft 绑定必须是对象")
    else:
        if str(binding.get("path") or "") != str(draft):
            errors.append("文字颗粒度合同绑定的正文路径不一致")
        if binding.get("sha256") != sha256(draft):
            errors.append("正文已变化，必须重新执行全文文字颗粒度复核")

    sections = extract_sections(draft_text)
    reviews = data.get("section_reviews")
    review_map: dict[str, dict[str, Any]] = {}
    if isinstance(reviews, list):
        review_map = {
            str(item.get("section_id") or ""): item
            for item in reviews
            if isinstance(item, dict) and str(item.get("section_id") or "")
        }
    else:
        errors.append("section_reviews 必须是列表")
    missing = set(sections) - set(review_map)
    extra = set(review_map) - set(sections)
    for section_id in sorted(missing):
        errors.append(f"正文小节缺少文字颗粒度复核: {section_id}")
    for section_id in sorted(extra):
        errors.append(f"文字颗粒度复核引用不存在的小节: {section_id}")

    source_text = read_text(source_original.resolve())
    passed_sections = 0
    anchor_signatures: dict[tuple[str, ...], list[str]] = {}
    comparison_signatures: dict[str, list[str]] = {}
    for section_id, section_text in sections.items():
        review = review_map.get(section_id)
        if not review:
            continue
        valid = True
        if review.get("status") != "passed":
            errors.append(f"正文小节文字颗粒度未通过: {section_id}")
            valid = False
        quotes = nonempty_strings(review.get("target_quotes"))
        if len(quotes) < 2:
            errors.append(f"正文小节至少需要 2 条目标句面证据: {section_id}")
            valid = False
        for index, quote in enumerate(quotes, start=1):
            if quote not in section_text:
                errors.append(f"目标句面证据不在对应正文小节: {section_id}[{index}]")
                valid = False
        anchors = nonempty_strings(review.get("source_anchors"))
        if len(anchors) < 2:
            errors.append(f"正文小节至少需要 2 条主体原文声线锚: {section_id}")
            valid = False
        for index, quote in enumerate(anchors, start=1):
            if quote not in source_text:
                errors.append(f"声线锚不在主体原文中: {section_id}[{index}]")
                valid = False
        if anchors:
            anchor_signatures.setdefault(tuple(anchors), []).append(section_id)
        checked = set(nonempty_strings(review.get("dimensions_checked")))
        if checked != set(REQUIRED_DIMENSIONS):
            errors.append(f"正文小节未覆盖全部文字颗粒度维度: {section_id}")
            valid = False
        for field, expected in (
            ("source_voice_preserved", True),
            ("functional_alignment_used_as_prose_proof", False),
            ("extra_ai_shell", False),
        ):
            if review.get(field) is not expected:
                errors.append(f"正文小节 {field} 必须为 {expected}: {section_id}")
                valid = False
        comparison = str(review.get("comparison") or "").strip()
        if not comparison:
            errors.append(f"正文小节缺少原文—目标文字对照: {section_id}")
            valid = False
        else:
            comparison_signatures.setdefault(comparison, []).append(section_id)
        if valid:
            passed_sections += 1

    for section_group in anchor_signatures.values():
        if len(section_group) > 1:
            errors.append(
                "正文小节不得复用同一组主体声线锚: " + ", ".join(section_group)
            )
    for section_group in comparison_signatures.values():
        if len(section_group) > 1:
            errors.append(
                "正文小节不得复用模板化原文—目标判断: " + ", ".join(section_group)
            )

    passed_subflows = validate_source_subflow_reviews(
        data, source_original, sections, errors
    )

    full_review = data.get("full_text_review")
    if not isinstance(full_review, dict):
        errors.append("full_text_review 必须是对象")
    else:
        expected_values = {
            "reviewed_full_text": True,
            "all_sections_reviewed": True,
            "primary_source_voice_dominant": True,
            "auxiliary_style_contamination": False,
            "functional_alignment_used_as_prose_proof": False,
            "remaining_extra_ai_shell": False,
        }
        for field, expected in expected_values.items():
            if full_review.get(field) is not expected:
                errors.append(f"full_text_review.{field} 必须为 {expected}")
        if not str(full_review.get("conclusion") or "").strip():
            errors.append("full_text_review.conclusion 不能为空")
    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if nonempty_strings(data.get("blocking_failures")):
        errors.append("仍有文字颗粒度阻断项，不能完成初稿停靠")
    summary["draft_sections"] = len(sections)
    summary["passed_sections"] = passed_sections
    summary["passed_subflows"] = passed_subflows
    return errors, summary


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="全文文字颗粒度合同硬闸")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--source-original", required=True)
    init_parser.add_argument("--receipt", required=True)
    prewrite_parser = subparsers.add_parser("validate-prewrite")
    prewrite_parser.add_argument("--receipt", required=True)
    prewrite_parser.add_argument("--source-original", required=True)
    bind_parser = subparsers.add_parser("bind-draft")
    bind_parser.add_argument("--receipt", required=True)
    bind_parser.add_argument("--draft", required=True)
    draft_parser = subparsers.add_parser("validate-draft")
    draft_parser.add_argument("--receipt", required=True)
    draft_parser.add_argument("--source-original", required=True)
    draft_parser.add_argument("--draft", required=True)
    args = parser.parse_args()

    receipt = Path(args.receipt).resolve()
    if args.command == "init":
        source = Path(args.source_original).resolve()
        write_json(receipt, create_receipt(args.project, source))
        print(f"prose_granularity_contract: initialized -> {receipt}")
        return 0
    if not receipt.is_file():
        print(f"prose_granularity_contract: blocked ({args.command})")
        print(f"- 文字颗粒度合同回执不存在: {receipt}")
        return 2
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"prose_granularity_contract: blocked ({args.command})")
        print(f"- 文字颗粒度合同回执不是有效 JSON: {exc}")
        return 2
    if args.command == "bind-draft":
        write_json(receipt, bind_draft(data, Path(args.draft)))
        print(f"prose_granularity_contract: draft bound -> {receipt}")
        return 0
    source = Path(args.source_original).resolve()
    if args.command == "validate-prewrite":
        errors, summary = validate_prewrite_data(data, source)
        label = "prewrite"
    else:
        errors, summary = validate_draft_data(data, source, Path(args.draft))
        label = "draft"
    if errors:
        print(f"prose_granularity_contract: blocked ({label})")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"prose_granularity_contract: passed ({label})")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
