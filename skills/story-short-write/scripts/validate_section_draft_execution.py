#!/usr/bin/env python3
"""Enforce open-write-close sequencing for source-bound short-story sections."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(
    r"(?m)^(?:(?:###\s*)?(\d+)\.\s*$|##\s*第\s*(\d+)\s*节(?:\s+.*)?$)"
)
ZHIHU_PLATFORM_RE = re.compile(r"知乎|盐言|盐选")
MIN_SECTION_CHARS = 800
SECTION_CHAR_RATIO = 0.45
MAX_SHORT_PARAGRAPH_RATIO = 0.90
SHORT_PROSE_PARAGRAPH_CHARS = 24
MANDATORY_CLOSE_MARKERS = (
    "event_flow=passed",
    "emotion_flow=passed",
    "style_granularity=passed",
    "telegraphic_and_relation_check=passed",
)
MANDATORY_CLOSE_CONTRACT_FIELDS = (
    "source_performance_excerpt",
    "emotion_process",
    "source_style_granularity",
    "first_draft_style_plan",
    "anti_verbatim_transfer_contract",
    "sentence_relation_plan",
    "paragraph_break_reasons",
)
STYLE_FIELD_DIALOGUE = "dialogue_misfire_or_avoidance"
STYLE_FIELD_PARAGRAPH = "paragraph_breath_and_cut_points"
STYLE_FIELD_ROUGHNESS = "narrator_interjection_and_roughness"
STYLE_FIELD_SENTENCE_RELATION = "sentence_relation_and_rhythm"
BEAT_RECEIPT_SCHEMA_VERSION = "2.1"
LEGACY_BEAT_RECEIPT_SCHEMA_VERSIONS = {"2.0"}
BEAT_EVIDENCE_FIELDS = (
    ("pre_state_evidence", "前态"),
    ("trigger_evidence", "触发"),
    ("action_choice_evidence", "动作选择"),
    ("visible_result_evidence", "可见结果"),
    ("next_beat_cause_evidence", "推动下一拍的原因"),
)
MIN_BEAT_EVIDENCE_CHARS = 6


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section_read_token(packet_sha: str) -> str:
    normalized = str(packet_sha or "").strip()
    if not normalized:
        return ""
    return hashlib.sha256(f"{normalized}:read-complete".encode("utf-8")).hexdigest()[:16]


def binding(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256(path)}


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_sibling_module(name: str) -> Any:
    script = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载脚本: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def infer_draft_format(draft: Path) -> str:
    setting = draft.parent / "设定.md"
    if not setting.is_file():
        return "platform_default"
    try:
        text = setting.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "platform_default"
    platform_lines = [
        line.strip()
        for line in text.splitlines()
        if "目标平台" in line or "正文使用" in line or "正文格式" in line
    ]
    return "zhihu_numeric" if ZHIHU_PLATFORM_RE.search("\n".join(platform_lines)) else "platform_default"


def validate_draft_format(draft: Path, draft_format: str) -> list[str]:
    if draft_format != "zhihu_numeric" or not draft.is_file():
        return []
    module = load_sibling_module("validate_zhihu_section_format")
    errors, _ = module.validate_text(draft.read_text(encoding="utf-8"))
    if not errors:
        return []
    return [
        "知乎/盐言正文格式错误：只允许 `1.`、`2.` 这类独占一行的连续纯数字节号，"
        "正文文件不得包含书名标题或小节标题；" + error
        for error in errors
    ]


def validate_outline_contract_receipt(outline_contract: Path) -> list[str]:
    try:
        outline_receipt = read_json(outline_contract)
    except Exception as exc:
        return [f"细纲表演验收回执不可读取: {exc}"]
    outline_binding = outline_receipt.get("outline")
    if not isinstance(outline_binding, dict):
        return ["细纲表演验收回执缺少 outline 绑定"]
    outline_path = Path(str(outline_binding.get("path") or "")).expanduser().resolve()
    if not outline_path.is_file():
        return [f"细纲绑定原始细纲不存在: {outline_path}"]
    module = load_sibling_module("validate_outline_performance_contract")
    errors = module.validate_receipt(outline_contract, outline_path)
    return [f"细纲表演验收回执实时复验失败: {error}" for error in errors]


def validate_section_source_bundle_receipt(bundle_path: Path) -> list[str]:
    module = load_sibling_module("build_section_source_bundle")
    errors = module.validate_bundle(bundle_path)
    return [f"逐节原文颗粒包实时复验失败: {error}" for error in errors]



def draft_section_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    ids: list[str] = []
    for match in SECTION_RE.finditer(path.read_text(encoding="utf-8")):
        section_id = match.group(1) or match.group(2) or ""
        if section_id:
            ids.append(section_id)
    return ids


def section_text(path: Path, section_id: str) -> str:
    text = path.read_text(encoding="utf-8")
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        matched_section_id = match.group(1) or match.group(2) or ""
        if matched_section_id != section_id:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[match.end() : end].strip()
    return ""


def non_whitespace_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def nonempty_paragraphs(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n\s*\n+", text) if item.strip()]


def is_standalone_dialogue(paragraph: str) -> bool:
    text = paragraph.strip()
    return text.startswith(("「", "“")) and text.endswith(("」", "”"))


def sentence_like_segments(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？!?]+", text) if item.strip()]


def normalized_text_for_match(text: str) -> str:
    return re.sub(r"[\s`“”\"'‘’：:；;，,。！？!?（）()、\-—]+", "", text)


def lexical_markers_from_sequence_line(text: str) -> list[str]:
    candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", str(text))
    filtered: list[str] = []
    stop_words = {
        "主角",
        "责任方",
        "第三方",
        "当前",
        "外部",
        "公开空间",
        "正式职责",
        "现实问题",
        "完整道德解释",
        "程序后果",
    }
    for item in candidates:
        if item in stop_words:
            continue
        if item not in filtered:
            filtered.append(item)
    return filtered[:6]


def validate_required_sequence_coverage(
    bindings: Any,
    content: str,
) -> list[str]:
    if not isinstance(bindings, list):
        return []
    normalized_content = normalized_text_for_match(content)
    errors: list[str] = []
    for item in bindings:
        if not isinstance(item, dict):
            continue
        subflow_id = str(item.get("subflow_id") or "").strip()
        source_contract = item.get("source_subflow_contract")
        if not isinstance(source_contract, dict):
            continue
        required_sequence = [
            str(step).strip()
            for step in (source_contract.get("required_sequence") or [])
            if str(step).strip()
        ]
        if not required_sequence:
            continue
        source_indices = source_contract.get("source_beat_indices")
        beat_indices = (
            source_indices
            if isinstance(source_indices, list) and len(source_indices) == len(required_sequence)
            else list(range(1, len(required_sequence) + 1))
        )
        matched_steps: list[int] = []
        for step_index, step in zip(beat_indices, required_sequence):
            markers = lexical_markers_from_sequence_line(step)
            if markers and any(marker in normalized_content for marker in markers):
                matched_steps.append(step_index)
        missing_steps = [
            (step_index, step)
            for step_index, step in zip(beat_indices, required_sequence)
            if step_index not in matched_steps
        ]
        if missing_steps:
            missing_preview = " / ".join(
                f"第{step_index}拍：{step}" for step_index, step in missing_steps
            )
            errors.append(
                f"正文未完整承接 {subflow_id} 的逐拍链："
                f"{len(required_sequence)} 拍必须零遗漏，当前缺 {len(missing_steps)} 拍；"
                f"{missing_preview}"
            )
    return errors


def validate_required_sequence_receipts(
    bindings: Any,
    content: str,
    receipts: Any,
    schema_version: str = "",
) -> list[str]:
    if not isinstance(bindings, list):
        return []
    required: list[tuple[str, int, str]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        subflow_id = str(binding.get("subflow_id") or "").strip()
        contract = binding.get("source_subflow_contract")
        if not isinstance(contract, dict):
            continue
        sequence = contract.get("required_sequence") or []
        source_indices = contract.get("source_beat_indices")
        beat_indices = (
            source_indices
            if isinstance(source_indices, list) and len(source_indices) == len(sequence)
            else list(range(1, len(sequence) + 1))
        )
        for beat_index, source_beat in zip(beat_indices, sequence):
            source_beat_text = str(source_beat).strip()
            if source_beat_text:
                required.append((subflow_id, beat_index, source_beat_text))
    if not required:
        return []
    if schema_version not in {
        BEAT_RECEIPT_SCHEMA_VERSION,
        *LEGACY_BEAT_RECEIPT_SCHEMA_VERSIONS,
    }:
        return [
            "逐拍消费回填版本过旧：必须 reopen-section 后重新 open-section，"
            f"生成 schema_version={BEAT_RECEIPT_SCHEMA_VERSION} 的五组件证据回执"
        ]
    if not isinstance(receipts, list):
        return ["逐拍消费回填缺失：仿写 required_sequence 必须逐拍零容缺验收"]

    actual: dict[tuple[str, int], dict[str, Any]] = {}
    errors: list[str] = []
    for index, item in enumerate(receipts, start=1):
        if not isinstance(item, dict):
            errors.append(f"逐拍消费回填[{index}] 必须是对象")
            continue
        key = (
            str(item.get("subflow_id") or "").strip(),
            item.get("beat_index") if isinstance(item.get("beat_index"), int) else -1,
        )
        if key in actual:
            errors.append(f"逐拍消费回填重复认领 {key[0]} 第{key[1]}拍")
        actual[key] = item

    required_keys = {(subflow_id, beat_index) for subflow_id, beat_index, _ in required}
    extra_keys = set(actual) - required_keys
    if extra_keys:
        errors.append(
            "逐拍消费回填包含未绑定拍："
            + " / ".join(f"{subflow_id}#{beat_index}" for subflow_id, beat_index in sorted(extra_keys))
        )

    action_positions: list[int] = []
    beat_ranges: list[tuple[int, int]] = []
    seen_evidence: set[str] = set()
    for subflow_id, beat_index, source_beat in required:
        label = f"{subflow_id} 第{beat_index}拍"
        item = actual.get((subflow_id, beat_index))
        if not isinstance(item, dict):
            errors.append(f"逐拍消费回填缺少 {label}：{source_beat}")
            continue
        if str(item.get("source_beat") or "").strip() != source_beat:
            errors.append(f"{label}.source_beat 与完整来源合同不一致")
        component_spans: list[tuple[int, int]] = []
        compact_evidence = item.get("evidence")
        if schema_version == BEAT_RECEIPT_SCHEMA_VERSION:
            if not isinstance(compact_evidence, list) or len(compact_evidence) != len(BEAT_EVIDENCE_FIELDS):
                errors.append(
                    f"{label}.evidence 必须按前态/触发/动作/结果/下一拍原因填写 5 条正文证据"
                )
                compact_evidence = [""] * len(BEAT_EVIDENCE_FIELDS)
        else:
            compact_evidence = [item.get(field) for field, _ in BEAT_EVIDENCE_FIELDS]
        for (field, field_label), raw_evidence in zip(BEAT_EVIDENCE_FIELDS, compact_evidence):
            evidence = str(raw_evidence or "").strip()
            if not evidence:
                errors.append(f"{label}.{field} 必须引用正文中的{field_label}证据")
                continue
            if non_whitespace_chars(evidence) < MIN_BEAT_EVIDENCE_CHARS:
                errors.append(
                    f"{label}.{field} 证据过短，不能用关键词冒充{field_label}: {evidence!r}"
                )
                continue
            if evidence not in content:
                errors.append(f"{label}.{field} 不在当前正文中: {evidence!r}")
                continue
            if content.count(evidence) != 1:
                errors.append(f"{label}.{field} 在当前正文中不是唯一片段，无法精确定位: {evidence!r}")
                continue
            if evidence in seen_evidence:
                errors.append(f"{label}.{field} 不得与其他组件或其他拍重复认领同一证据")
                continue
            seen_evidence.add(evidence)
            position = content.index(evidence)
            component_spans.append((position, position + len(evidence)))
            if field == "action_choice_evidence":
                action_positions.append(position)
        if len(component_spans) == len(BEAT_EVIDENCE_FIELDS):
            if any(
                current_start < previous_end
                for (_, previous_end), (current_start, _) in zip(
                    component_spans,
                    component_spans[1:],
                )
            ):
                errors.append(
                    f"{label} 的五组件证据必须按前态 -> 触发 -> 动作 -> 结果 -> 下一拍原因"
                    "顺序出现且不得重叠"
                )
            else:
                beat_ranges.append((component_spans[0][0], component_spans[-1][1]))
        performance = str(item.get("performance_equivalence") or "").strip()
        if not performance:
            errors.append(f"{label}.performance_equivalence 必须说明表演等强判断")
        elif any(marker in performance for marker in ("机械预填", "待确认", "待复核", "待当前模型")):
            errors.append(f"{label}.performance_equivalence 不得使用机械占位话")
        if item.get("status") not in (None, "passed"):
            errors.append(f"{label}.status 必须为 passed")
    if action_positions != sorted(action_positions) or len(action_positions) != len(required):
        errors.append("逐拍消费回填的动作选择证据顺序与 required_sequence 不一致")
    if len(beat_ranges) == len(required) and any(
        current_start < previous_end
        for (_, previous_end), (current_start, _) in zip(beat_ranges, beat_ranges[1:])
    ):
        errors.append("逐拍消费回填的整拍证据区间发生交叉，未按 required_sequence 完整推进")
    return errors


def source_excerpt_lines_for_binding(item: dict[str, Any]) -> list[str]:
    excerpt = str(item.get("source_excerpt") or "")
    lines: list[str] = []
    for raw_line in excerpt.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        markers = lexical_markers_from_sequence_line(line)
        if not markers:
            continue
        lines.append(line)
    return lines


def validate_source_excerpt_line_coverage(
    bindings: Any,
    content: str,
) -> list[str]:
    if not isinstance(bindings, list):
        return []
    normalized_content = normalized_text_for_match(content)
    errors: list[str] = []
    for item in bindings:
        if not isinstance(item, dict):
            continue
        subflow_id = str(item.get("subflow_id") or "").strip()
        excerpt_lines = source_excerpt_lines_for_binding(item)
        if not excerpt_lines:
            continue
        matched_count = 0
        for line in excerpt_lines:
            markers = lexical_markers_from_sequence_line(line)
            if markers and any(marker in normalized_content for marker in markers):
                matched_count += 1
        minimum_required = max(4, int(len(excerpt_lines) * 0.6))
        if matched_count < minimum_required:
            errors.append(
                f"正文未保住 {subflow_id} 的原文细拍密度：{len(excerpt_lines)} 条原文行中仅检测到 {matched_count} 条落点"
            )
    return errors


def validate_verbatim_source_reuse(
    bindings: Any,
    content: str,
) -> list[str]:
    if not isinstance(bindings, list):
        return []
    normalized_content = normalized_text_for_match(content)
    errors: list[str] = []
    for item in bindings:
        if not isinstance(item, dict):
            continue
        subflow_id = str(item.get("subflow_id") or "").strip()
        excerpt_lines = source_excerpt_lines_for_binding(item)
        exact_hits: list[str] = []
        for line in excerpt_lines:
            normalized_line = normalized_text_for_match(line)
            if len(normalized_line) < 8:
                continue
            if normalized_line in normalized_content:
                exact_hits.append(line)
        if len(exact_hits) >= 2:
            preview = " / ".join(exact_hits[:3])
            errors.append(
                f"正文疑似直接复用 {subflow_id} 原句：检测到 {len(exact_hits)} 条高重合原文行，例如 {preview}"
            )
    return errors


def binding_anchor_markers(item: dict[str, Any]) -> list[str]:
    source_contract = item.get("source_subflow_contract")
    if not isinstance(source_contract, dict):
        return []
    candidates: list[str] = []
    for text in (
        *(source_contract.get("required_sequence") or []),
        *(source_contract.get("source_evidence") or []),
        *(source_contract.get("control_changes") or []),
        source_contract.get("end_state") or "",
    ):
        raw = str(text).strip()
        if not raw:
            continue
        for marker in lexical_markers_from_sequence_line(raw):
            if len(marker) < 2:
                continue
            if marker not in candidates:
                candidates.append(marker)
    return candidates[:12]


def validate_binding_anchor_coverage(
    bindings: Any,
    content: str,
) -> list[str]:
    if not isinstance(bindings, list):
        return []
    normalized_content = normalized_text_for_match(content)
    errors: list[str] = []
    for item in bindings:
        if not isinstance(item, dict):
            continue
        subflow_id = str(item.get("subflow_id") or "").strip()
        markers = binding_anchor_markers(item)
        if not markers:
            continue
        matched = [marker for marker in markers if marker in normalized_content]
        minimum_required = max(2, min(4, len(markers) // 2))
        if len(matched) < minimum_required:
            preview = " / ".join(markers[:5])
            errors.append(
                f"正文未真正消费 {subflow_id} 的具体颗粒锚点：需要至少 {minimum_required} 个，当前仅命中 {len(matched)} 个；锚点示例 {preview}"
            )
    return errors


def unique_binding_requirements(
    bindings: Any,
) -> tuple[list[str], list[str], list[str]]:
    required_subflows: list[str] = []
    required_ranges: list[str] = []
    required_style_fields: list[str] = []
    if not isinstance(bindings, list):
        return required_subflows, required_ranges, required_style_fields
    for item in bindings:
        if not isinstance(item, dict):
            continue
        subflow_id = str(item.get("subflow_id") or "").strip()
        source_range = str(item.get("source_range") or "").strip()
        if subflow_id and subflow_id not in required_subflows:
            required_subflows.append(subflow_id)
        if source_range and source_range not in required_ranges:
            required_ranges.append(source_range)
        for field in item.get("style_fields_consumed", []) or []:
            field_name = str(field).strip()
            if field_name and field_name not in required_style_fields:
                required_style_fields.append(field_name)
    return required_subflows, required_ranges, required_style_fields


def required_read_judgment_template(target: dict[str, Any]) -> str:
    subflows, ranges, style_fields = unique_binding_requirements(
        target.get("source_slice_bindings")
    )
    parts = ["已完整读取"]
    if subflows:
        parts.append("subflows=" + ",".join(subflows))
    if ranges:
        parts.append("source_ranges=" + ",".join(ranges))
    if style_fields:
        parts.append("style_fields_consumed=" + ",".join(style_fields))
    read_token = section_read_token(str(target.get("granularity_packet_sha256") or ""))
    if read_token:
        parts.append("read_token=" + read_token)
    return "; ".join(parts)


def required_close_judgment_template(
    target: dict[str, Any],
    packet_payload: dict[str, Any] | None,
) -> str:
    subflows, _, style_fields = unique_binding_requirements(
        target.get("source_slice_bindings")
    )
    parts = list(MANDATORY_CLOSE_MARKERS)
    if subflows:
        parts.append("subflows=" + ",".join(subflows))
    if style_fields:
        parts.append("style_fields_consumed=" + ",".join(style_fields))
    if packet_payload is not None:
        contract = packet_payload.get("first_draft_generation_contract")
        if isinstance(contract, dict):
            available = [
                field for field in MANDATORY_CLOSE_CONTRACT_FIELDS if field in contract
            ]
            if available:
                parts.append("first_draft_contract=" + ",".join(available))
    return "; ".join(parts)


def validate_close_content_signals(
    target: dict[str, Any],
    packet_payload: dict[str, Any] | None,
    content: str,
) -> list[str]:
    if packet_payload is None:
        return []
    bindings = target.get("source_slice_bindings")
    _, _, style_fields = unique_binding_requirements(bindings)
    style_field_set = set(style_fields)
    contract = packet_payload.get("first_draft_generation_contract")
    if not isinstance(contract, dict):
        return []
    errors: list[str] = []
    paragraphs = nonempty_paragraphs(content)
    if STYLE_FIELD_PARAGRAPH in style_field_set:
        required_breaks = len(
            [
                item
                for item in (contract.get("paragraph_break_reasons") or [])
                if str(item).strip()
            ]
        )
        minimum_paragraphs = max(2, required_breaks + 1)
        if len(paragraphs) < minimum_paragraphs:
            errors.append(
                f"正文段落承载不足：要求至少 {minimum_paragraphs} 段以承接 paragraph_break_reasons，当前仅 {len(paragraphs)} 段"
            )
        prose_paragraphs = [item for item in paragraphs if not is_standalone_dialogue(item)]
        if len(prose_paragraphs) >= 8:
            short_paragraphs = [
                item
                for item in prose_paragraphs
                if non_whitespace_chars(item) <= SHORT_PROSE_PARAGRAPH_CHARS
            ]
            if (
                short_paragraphs
                and len(short_paragraphs) / len(prose_paragraphs)
                >= MAX_SHORT_PARAGRAPH_RATIO
            ):
                errors.append(
                    "正文段落气口失真：短促电报段占比过高，已无法承接 paragraph_breath_and_cut_points 的连续场面颗粒"
                )
        if paragraphs and not any(len(sentence_like_segments(item)) >= 2 for item in paragraphs):
            errors.append(
                "正文缺少连续承载段：所有段落都只剩单句起落，无法承接原文连续瞬间与断段理由"
            )
    if STYLE_FIELD_DIALOGUE in style_field_set:
        source_excerpt = " ".join(
            str(item).strip()
            for item in (contract.get("source_performance_evidence") or [])
            if str(item).strip()
        )
        requires_dialogue = any(
            marker in source_excerpt for marker in ("「", "」", "“", "”", "：", "喊", "说", "问")
        )
        if requires_dialogue and not any(marker in content for marker in ("「", "」", "“", "”", "：")):
            errors.append(
                "正文缺少对白承载信号：source_performance_excerpt 已绑定对白/错答颗粒，但正文没有形成对白落点"
            )
    relation_plan = [
        str(item).strip()
        for item in (contract.get("sentence_relation_plan") or [])
        if str(item).strip()
    ]
    required_sequence_lines: list[str] = []
    if isinstance(bindings, list):
        for item in bindings:
            if not isinstance(item, dict):
                continue
            source_contract = item.get("source_subflow_contract")
            if not isinstance(source_contract, dict):
                continue
            required_sequence = source_contract.get("required_sequence")
            if isinstance(required_sequence, list):
                required_sequence_lines.extend(
                    str(step).strip() for step in required_sequence if str(step).strip()
                )
    if STYLE_FIELD_SENTENCE_RELATION in style_field_set:
        question_hint = any("问" in line for line in relation_plan) or any(
            "反问" in line or "问句" in line for line in required_sequence_lines
        )
        if question_hint:
            required_question_marks = 2 if any("连续反问" in line for line in required_sequence_lines) else 1
            actual_question_marks = content.count("？") + content.count("?")
            if actual_question_marks < required_question_marks:
                errors.append(
                    f"正文缺少句式承载信号：已绑定问句/反问颗粒，至少需要 {required_question_marks} 个问号，当前仅 {actual_question_marks} 个"
                )
    if STYLE_FIELD_ROUGHNESS in style_field_set:
        rough_signal_count = sum(content.count(marker) for marker in ("！", "!", "？", "?"))
        short_paragraphs = [item for item in paragraphs if non_whitespace_chars(item) <= 28]
        if rough_signal_count == 0 and not short_paragraphs:
            errors.append(
                "正文缺少粗粝打断信号：已绑定 narrator_interjection_and_roughness，但正文没有感叹/问句或短促断段"
            )
    sequence_receipts = target.get("required_sequence_receipts")
    errors.extend(
        validate_required_sequence_receipts(
            bindings,
            content,
            sequence_receipts,
            str(target.get("beat_receipt_schema_version") or ""),
        )
    )
    if not isinstance(sequence_receipts, list) or not sequence_receipts:
        errors.extend(validate_binding_anchor_coverage(bindings, content))
    errors.extend(validate_source_excerpt_line_coverage(bindings, content))
    errors.extend(validate_verbatim_source_reuse(bindings, content))
    return errors


def expected_min_section_chars(packet_payload: dict[str, Any]) -> int:
    bindings = packet_payload.get("source_slice_bindings")
    if not isinstance(bindings, list):
        return MIN_SECTION_CHARS
    total_source_chars = 0
    for item in bindings:
        if not isinstance(item, dict):
            continue
        excerpt = str(item.get("source_excerpt") or "")
        total_source_chars += non_whitespace_chars(excerpt)
    if total_source_chars <= 0:
        return MIN_SECTION_CHARS
    return max(MIN_SECTION_CHARS, int(total_source_chars * SECTION_CHAR_RATIO))


def packet_payload_for_section(bundle_path: Path, section_id: str) -> dict[str, Any] | None:
    try:
        bundle = read_json(bundle_path)
    except Exception:
        return None
    for item in bundle.get("packets", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("section_id") or "") != section_id:
            continue
        payload = item.get("payload")
        if isinstance(payload, dict):
            return payload
    return None


def validate_close_judgment(
    section_id: str,
    target: dict[str, Any],
    packet_payload: dict[str, Any] | None,
    content: str,
    judgment: str,
) -> list[str]:
    errors: list[str] = []
    normalized_judgment = judgment.strip()
    if not normalized_judgment:
        errors.append("judgment 不能为空")
        return errors
    section_chars = non_whitespace_chars(content)
    if packet_payload is not None:
        expected_chars = expected_min_section_chars(packet_payload)
        if section_chars < expected_chars:
            errors.append(
                f"第 {section_id} 节正文承载量不足：当前 {section_chars} 字，至少需要 {expected_chars} 字才允许宣称已完整吃入原文颗粒"
            )
    for marker in MANDATORY_CLOSE_MARKERS:
        if marker not in normalized_judgment:
            errors.append(f"close-section judgment 缺少硬闸标记: {marker}")
    bindings = target.get("source_slice_bindings")
    required_subflows, _, required_style_fields = unique_binding_requirements(bindings)
    for subflow_id in required_subflows:
        if subflow_id not in normalized_judgment:
            errors.append(f"close-section judgment 缺少来源绑定确认: {subflow_id}")
    for field_name in required_style_fields:
        if field_name not in normalized_judgment:
            errors.append(f"close-section judgment 缺少文风颗粒确认: {field_name}")
    if packet_payload is not None:
        contract = packet_payload.get("first_draft_generation_contract")
        if isinstance(contract, dict):
            for field in MANDATORY_CLOSE_CONTRACT_FIELDS:
                if field not in normalized_judgment:
                    errors.append(f"close-section judgment 缺少首写合同确认: {field}")
    errors.extend(validate_close_content_signals(target, packet_payload, content))
    return errors


def validate_open_judgment(target: dict[str, Any], read_judgment: str) -> list[str]:
    errors: list[str] = []
    normalized = read_judgment.strip()
    if not normalized:
        errors.append("read-judgment 不能为空")
        return errors
    bindings = target.get("source_slice_bindings")
    if not isinstance(bindings, list) or not bindings:
        errors.append("当前小节缺少逐节原文颗粒包绑定")
        return errors
    required_subflows, required_ranges, required_style_fields = unique_binding_requirements(bindings)
    for subflow_id in required_subflows:
        if subflow_id not in normalized:
            errors.append(f"read-judgment 缺少来源 SF 确认: {subflow_id}")
    for source_range in required_ranges:
        if source_range not in normalized:
            errors.append(f"read-judgment 缺少精确切片范围确认: {source_range}")
    for field_name in required_style_fields:
        if field_name not in normalized:
            errors.append(f"read-judgment 缺少文风颗粒确认: {field_name}")
    expected_token = section_read_token(str(target.get("granularity_packet_sha256") or ""))
    if expected_token and f"read_token={expected_token}" not in normalized:
        errors.append("read-judgment 缺少最终阅读完成令牌，必须完整读到最后一包后再开节")
    return errors


def check_binding(value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return None
    path = Path(str(value.get("path") or "")).expanduser().resolve()
    if not path.is_file():
        errors.append(f"{label} 文件不存在: {path}")
        return None
    if value.get("sha256") != sha256(path):
        errors.append(f"{label} SHA 已变化")
    return path


def validate_receipt(
    path: Path,
    require_complete: bool = False,
    deep_static_validation: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"回执无法读取: {exc}"]
    if data.get("gate") != "section_draft_execution":
        errors.append("gate 必须为 section_draft_execution")
    outline_contract = check_binding(data.get("outline_contract"), "outline_contract", errors)
    source_receipt = check_binding(data.get("source_receipt"), "source_receipt", errors)
    section_source_bundle = check_binding(data.get("section_source_bundle"), "section_source_bundle", errors)
    if outline_contract is not None and deep_static_validation:
        errors.extend(validate_outline_contract_receipt(outline_contract))
    if source_receipt is not None and deep_static_validation:
        try:
            source = read_json(source_receipt)
        except Exception as exc:
            errors.append(f"source_receipt 无法读取: {exc}")
        else:
            if source.get("gate_status") != "passed":
                errors.append("source_receipt 必须先通过")
            if str(source.get("writing_mode") or "") != "direct_imitation":
                errors.append("source_receipt.writing_mode 必须为 direct_imitation")
    if section_source_bundle is not None and deep_static_validation:
        errors.extend(validate_section_source_bundle_receipt(section_source_bundle))
    draft = Path(str(data.get("draft_path") or "")).expanduser().resolve()
    draft_format = str(data.get("draft_format") or infer_draft_format(draft))
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return data, errors + ["sections 必须是非空数组"]
    expected_ids = [str(item.get("section_id") or "") for item in sections if isinstance(item, dict)]
    completed_ids: list[str] = []
    open_count = 0
    bundle_payload_map: dict[str, dict[str, Any]] = {}
    if section_source_bundle is not None:
        try:
            bundle = read_json(section_source_bundle)
        except Exception as exc:
            errors.append(f"section_source_bundle 无法读取: {exc}")
        else:
            for packet in bundle.get("packets", []):
                if not isinstance(packet, dict):
                    continue
                packet_section_id = str(packet.get("section_id") or "").strip()
                payload = packet.get("payload")
                if packet_section_id and isinstance(payload, dict):
                    bundle_payload_map[packet_section_id] = payload
    for item in sections:
        if not isinstance(item, dict):
            errors.append("sections 含非对象")
            continue
        status = item.get("status")
        section_id = str(item.get("section_id") or "")
        packet_payload = bundle_payload_map.get(section_id)
        if status == "completed":
            completed_ids.append(section_id)
            for field in ("opened_at", "closed_at", "read_judgment", "manual_judgment", "section_sha256", "draft_sha256_after_close"):
                if not str(item.get(field) or "").strip():
                    errors.append(f"第 {section_id} 节缺少 {field}")
            for field in ("event_flow", "emotion_flow", "style_granularity", "telegraphic_and_relation_check"):
                if item.get(field) != "passed":
                    errors.append(f"第 {section_id} 节 {field} 必须为 passed")
            open_judgment_errors = validate_open_judgment(
                item,
                str(item.get("read_judgment") or ""),
            )
            errors.extend(
                f"第 {section_id} 节已完成回执的 read_judgment 失效: {error}"
                for error in open_judgment_errors
            )
            if draft.is_file():
                content = section_text(draft, section_id)
                if not content:
                    errors.append(f"第 {section_id} 节已完成但正文缺失")
                else:
                    close_judgment_errors = validate_close_judgment(
                        section_id,
                        item,
                        packet_payload,
                        content,
                        str(item.get("manual_judgment") or ""),
                    )
                    errors.extend(
                        f"第 {section_id} 节已完成回执的 manual_judgment 失效: {error}"
                        for error in close_judgment_errors
                    )
        elif status == "open":
            open_count += 1
            if not str(item.get("opened_at") or "").strip():
                errors.append(f"第 {section_id} 节 open 状态缺少 opened_at")
            open_judgment_errors = validate_open_judgment(
                item,
                str(item.get("read_judgment") or ""),
            )
            errors.extend(
                f"第 {section_id} 节 open 状态的 read_judgment 失效: {error}"
                for error in open_judgment_errors
            )
        elif status != "pending":
            errors.append(f"第 {section_id} 节 status 无效: {status!r}")
    if open_count > 1:
        errors.append("同时只能打开一个小节")
    actual_ids = draft_section_ids(draft)
    allowed_ids = completed_ids + [
        str(item.get("section_id"))
        for item in sections
        if isinstance(item, dict)
        and (
            item.get("status") == "open"
            or (
                item.get("status") == "pending"
                and item.get("revision_reopen") is True
            )
        )
    ]
    if actual_ids != allowed_ids:
        errors.append(
            "正文小节与逐节执行状态不一致；禁止先批量写完再补回执: "
            f"正文={actual_ids}, 已放行={allowed_ids}"
        )
    if actual_ids:
        errors.extend(validate_draft_format(draft, draft_format))
    if require_complete:
        if completed_ids != expected_ids:
            errors.append("所有小节必须按顺序逐节完成")
        if not draft.is_file() or data.get("final_draft_sha256") != sha256(draft):
            errors.append("最终正文 SHA 未绑定或已变化")
        if data.get("gate_status") != "passed":
            errors.append("gate_status 必须为 passed")
    return data, errors


def init_receipt(
    outline_contract: Path,
    source_receipt: Path,
    section_source_bundle: Path,
    draft: Path,
    receipt: Path,
) -> int:
    if receipt.exists():
        print(f"逐节首写执行回执已存在，拒绝覆盖: {receipt}")
        return 2
    outline_errors = validate_outline_contract_receipt(outline_contract)
    if outline_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(outline_errors))
        return 2
    try:
        source = read_json(source_receipt)
    except Exception as exc:
        print(f"section_draft_execution: blocked\n- 拆文读取回执不可读取: {exc}")
        return 2
    if source.get("gate_status") != "passed" or str(source.get("writing_mode") or "") != "direct_imitation":
        print("section_draft_execution: blocked\n- 拆文读取回执必须先通过且 writing_mode=direct_imitation")
        return 2
    bundle_errors = validate_section_source_bundle_receipt(section_source_bundle)
    if bundle_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(bundle_errors))
        return 2
    outline = read_json(outline_contract)
    bundle = read_json(section_source_bundle)
    if draft_section_ids(draft):
        print("section_draft_execution: blocked\n- 正文已经含数字小节，禁止事后初始化逐节回执")
        return 2
    packets = {
        str(item.get("section_id") or ""): item
        for item in bundle.get("packets", [])
        if isinstance(item, dict)
    }
    sections = []
    for item in outline.get("sections", []):
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "")
        contract = item.get("first_draft_generation_contract")
        bindings = contract.get("source_slice_bindings") if isinstance(contract, dict) else None
        if not isinstance(bindings, list) or not bindings:
            print("section_draft_execution: blocked\n- 每节必须先绑定 source_slice_bindings")
            return 2
        packet = packets.get(section_id)
        if not packet:
            print(f"section_draft_execution: blocked\n- 第 {section_id} 节缺少逐节原文颗粒包")
            return 2
        packet_payload = packet.get("payload")
        packet_bindings = (
            packet_payload.get("source_slice_bindings")
            if isinstance(packet_payload, dict)
            else None
        )
        if not isinstance(packet_bindings, list) or not packet_bindings:
            print(f"section_draft_execution: blocked\n- 第 {section_id} 节颗粒包缺少完整来源绑定")
            return 2
        sections.append({
            "section_id": section_id,
            "status": "pending",
            "granularity_packet_id": str(packet.get("packet_id") or ""),
            "granularity_packet_sha256": str(packet.get("packet_sha256") or ""),
            "source_slice_bindings": [
                {key: value for key, value in item.items() if key != "source_excerpt"}
                for item in packet_bindings
                if isinstance(item, dict)
            ],
            "opened_at": "",
            "closed_at": "",
            "read_judgment": "",
            "manual_judgment": "",
            "event_flow": "pending",
            "emotion_flow": "pending",
            "style_granularity": "pending",
            "telegraphic_and_relation_check": "pending",
            "section_sha256": "",
            "draft_sha256_after_close": "",
            "required_sequence_receipts": [],
            "beat_receipt_schema_version": "",
            "revision_reopen": False,
        })
    data = {
        "version": "1.1",
        "gate": "section_draft_execution",
        "outline_contract": binding(outline_contract),
        "source_receipt": binding(source_receipt),
        "section_source_bundle": binding(section_source_bundle),
        "draft_path": str(draft.resolve()),
        "draft_format": infer_draft_format(draft),
        "sections": sections,
        "final_draft_sha256": "",
        "gate_status": "active",
    }
    write_json(receipt, data)
    print("section_draft_execution: initialized")
    return 0


def open_section(receipt: Path, section_id: str, read_judgment: str) -> int:
    data, errors = validate_receipt(receipt, deep_static_validation=False)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    sections = data["sections"]
    target = next((item for item in sections if item["section_id"] == section_id), None)
    if not target or target["status"] != "pending":
        print("section_draft_execution: blocked\n- 目标小节不存在或不是 pending")
        return 2
    previous = [item["section_id"] for item in sections[: sections.index(target)]]
    completed = [item["section_id"] for item in sections if item["status"] == "completed"]
    if completed != previous:
        print("section_draft_execution: blocked\n- 必须按顺序完成上一节")
        return 2
    open_errors = validate_open_judgment(target, read_judgment)
    if open_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(open_errors))
        return 2
    target["status"] = "open"
    target["opened_at"] = now_iso()
    target["read_judgment"] = read_judgment.strip()
    target["revision_reopen"] = False
    if not target.get("granularity_packet_id") or not target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节缺少逐节原文颗粒包绑定")
        return 2
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} open")
    return 0


def close_section(
    receipt: Path,
    section_id: str,
    judgment: str,
    beat_receipt: Path | None = None,
) -> int:
    data, errors = validate_receipt(receipt, deep_static_validation=False)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    target = next((item for item in data["sections"] if item["section_id"] == section_id), None)
    if not target or target["status"] != "open":
        print("section_draft_execution: blocked\n- 目标小节尚未 open")
        return 2
    draft = Path(data["draft_path"])
    content = section_text(draft, section_id)
    if not content:
        print("section_draft_execution: blocked\n- 当前小节正文为空")
        return 2
    format_errors = validate_draft_format(
        draft,
        str(data.get("draft_format") or infer_draft_format(draft)),
    )
    if format_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(format_errors))
        return 2
    if beat_receipt is not None:
        try:
            beat_payload = read_json(beat_receipt)
        except Exception as exc:
            print(f"section_draft_execution: blocked\n- 逐拍消费回填不可读取: {exc}")
            return 2
        if str(beat_payload.get("section_id") or "").strip() != section_id:
            print("section_draft_execution: blocked\n- 逐拍消费回填 section_id 与当前节不一致")
            return 2
        if str(beat_payload.get("granularity_packet_sha256") or "").strip() != str(
            target.get("granularity_packet_sha256") or ""
        ).strip():
            print("section_draft_execution: blocked\n- 逐拍消费回填绑定的颗粒包已过期")
            return 2
        target["required_sequence_receipts"] = beat_payload.get("beats")
        target["beat_receipt_schema_version"] = str(
            beat_payload.get("schema_version") or ""
        ).strip()
    bundle_path = check_binding(
        data.get("section_source_bundle"),
        "section_source_bundle",
        [],
    )
    packet_payload = packet_payload_for_section(bundle_path, section_id) if bundle_path else None
    judgment_errors = validate_close_judgment(
        section_id,
        target,
        packet_payload,
        content,
        judgment,
    )
    if judgment_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(judgment_errors))
        return 2
    target.update({
        "status": "completed",
        "closed_at": now_iso(),
        "manual_judgment": judgment.strip(),
        "event_flow": "passed",
        "emotion_flow": "passed",
        "style_granularity": "passed",
        "telegraphic_and_relation_check": "passed",
        "section_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "draft_sha256_after_close": sha256(draft),
    })
    if all(item["status"] == "completed" for item in data["sections"]):
        data["final_draft_sha256"] = sha256(draft)
        data["gate_status"] = "passed"
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} completed")
    return 0


def reopen_section(receipt: Path, section_id: str) -> int:
    try:
        data = read_json(receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"section_draft_execution: blocked\n- 回执无法读取: {exc}")
        return 2
    if data.get("gate") != "section_draft_execution":
        print("section_draft_execution: blocked\n- gate 必须为 section_draft_execution")
        return 2
    target = next((item for item in data["sections"] if item["section_id"] == section_id), None)
    if not target or target["status"] not in {"open", "completed"}:
        print("section_draft_execution: blocked\n- 目标小节不存在或不是 open/completed")
        return 2
    target_index = data["sections"].index(target)
    if target["status"] == "completed" and any(
        item.get("status") != "pending"
        for item in data["sections"][target_index + 1 :]
        if isinstance(item, dict)
    ):
        print("section_draft_execution: blocked\n- 只能回修最后一个已完成小节，后续小节必须全部为 pending")
        return 2
    if not target.get("granularity_packet_id") or not target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节缺少逐节原文颗粒包绑定")
        return 2
    was_completed = target["status"] == "completed"
    target.update(
        {
            "status": "pending",
            "opened_at": "",
            "closed_at": "",
            "read_judgment": "",
            "manual_judgment": "",
            "event_flow": "pending",
            "emotion_flow": "pending",
            "style_granularity": "pending",
            "telegraphic_and_relation_check": "pending",
            "section_sha256": "",
            "draft_sha256_after_close": "",
            "required_sequence_receipts": [],
            "beat_receipt_schema_version": "",
            "revision_reopen": was_completed,
        }
    )
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} reopened")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--outline-contract", required=True)
    init.add_argument("--source-receipt", required=True)
    init.add_argument("--section-source-bundle", required=True)
    init.add_argument("--draft", required=True)
    init.add_argument("--receipt", required=True)
    opening = sub.add_parser("open-section")
    opening.add_argument("--receipt", required=True)
    opening.add_argument("--section", required=True)
    opening.add_argument("--read-judgment", required=True)
    reopening = sub.add_parser("reopen-section")
    reopening.add_argument("--receipt", required=True)
    reopening.add_argument("--section", required=True)
    closing = sub.add_parser("close-section")
    closing.add_argument("--receipt", required=True)
    closing.add_argument("--section", required=True)
    closing.add_argument("--judgment", required=True)
    closing.add_argument("--beat-receipt")
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    args = parser.parse_args()
    receipt = Path(getattr(args, "receipt", "")).resolve()
    if args.command == "init":
        return init_receipt(
            Path(args.outline_contract).resolve(),
            Path(args.source_receipt).resolve(),
            Path(args.section_source_bundle).resolve(),
            Path(args.draft).resolve(),
            receipt,
        )
    if args.command == "open-section":
        return open_section(receipt, args.section, args.read_judgment)
    if args.command == "reopen-section":
        return reopen_section(receipt, args.section)
    if args.command == "close-section":
        return close_section(
            receipt,
            args.section,
            args.judgment,
            Path(args.beat_receipt).resolve() if args.beat_receipt else None,
        )
    _, errors = validate_receipt(receipt, require_complete=True)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    print("section_draft_execution: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
