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


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_receipt(project: str, source_original: Path) -> dict[str, Any]:
    source = source_original.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"主体原文不存在: {source}")
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


def validate_prewrite_data(
    data: dict[str, Any], source_original: Path
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    source_text = validate_source_binding(data, source_original, errors)
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
        if not str(review.get("comparison") or "").strip():
            errors.append(f"正文小节缺少原文—目标文字对照: {section_id}")
            valid = False
        if valid:
            passed_sections += 1

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
    data = json.loads(receipt.read_text(encoding="utf-8"))
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
