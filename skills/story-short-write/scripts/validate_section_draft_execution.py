#!/usr/bin/env python3
"""Enforce open-write-close sequencing for source-bound short-story sections."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(r"(?m)^(\d+)\.\s*$")
STYLE_DIMENSIONS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
PREWRITE_CONFIRMATIONS = (
    "source_performance_evidence_read",
    "technique_recall_contract_understood",
    "scene_weave_contract_understood",
    "source_style_granularity_read",
    "source_style_reference_assets_read",
    "emotion_process_understood",
    "continuous_moment_groups_understood",
    "paragraph_break_plan_understood",
    "sentence_relation_plan_understood",
    "function_word_strategy_understood",
    "target_emotion_landing_plan_understood",
    "forbidden_items_checked",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def source_excerpt(path: Path, source_range: str) -> tuple[str, list[tuple[int, int]]]:
    lines = read_text(path).splitlines()
    ranges = [(int(start), int(end)) for start, end in re.findall(r"L(\d+)-L(\d+)", source_range)]
    if not ranges:
        raise ValueError(f"非法 source_range: {source_range!r}")
    excerpts: list[str] = []
    for start, end in ranges:
        if start < 1 or end < start or end > len(lines):
            raise ValueError(f"source_range 越界: L{start}-L{end}，原文共 {len(lines)} 行")
        excerpts.append("\n".join(lines[start - 1 : end]))
    return "\n".join(excerpts), ranges


def section_review_path(receipt: Path, section_id: str) -> Path:
    return receipt.parent / "逐节首写停检" / f"第{section_id}节.json"


def section_prewrite_path(receipt: Path, section_id: str) -> Path:
    return receipt.parent / "逐节写前颗粒确认" / f"第{section_id}节.json"


def review_check_template() -> dict[str, Any]:
    return {
        "status": "pending",
        "source_evidence": [],
        "target_evidence": [],
        "judgment": "",
    }


def task_fingerprint(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_complete_granularity_payload(payload: Any, section_id: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"第 {section_id} 节颗粒包 payload 必须是对象"]
    for field in (
        "source_performance_evidence",
        "technique_recall_contract",
        "scene_weave_contract",
        "source_style_reference_assets",
        "continuous_moment_groups",
        "paragraph_break_reasons",
        "sentence_relation_plan",
        "emotion_shorthand_to_avoid",
        "target_emotion_landing_plan",
    ):
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"第 {section_id} 节颗粒包缺少完整 {field}")
    for field in (
        "source_performance_excerpt",
        "function_word_strategy",
        "telegraphic_risk",
        "manual_judgment",
    ):
        if not str(payload.get(field) or "").strip():
            errors.append(f"第 {section_id} 节颗粒包缺少完整 {field}")
    style = payload.get("source_style_granularity")
    if not isinstance(style, dict) or set(style) != set(STYLE_DIMENSIONS):
        errors.append(f"第 {section_id} 节 source_style_granularity 必须完整覆盖六类文风颗粒")
    else:
        for dimension in STYLE_DIMENSIONS:
            item = style.get(dimension)
            if not isinstance(item, dict):
                errors.append(f"第 {section_id} 节 source_style_granularity.{dimension} 必须是对象")
                continue
            if not str(item.get("source_summary") or "").strip():
                errors.append(f"第 {section_id} 节 source_style_granularity.{dimension}.source_summary 不能为空")
            if not str(item.get("target_style_plan") or "").strip():
                errors.append(f"第 {section_id} 节 source_style_granularity.{dimension}.target_style_plan 不能为空")
            evidence = item.get("source_evidence")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"第 {section_id} 节 source_style_granularity.{dimension}.source_evidence 不能为空")
    if payload.get("no_fixed_short_sentence_ratio") is not True:
        errors.append(f"第 {section_id} 节颗粒包缺少 no_fixed_short_sentence_ratio=true")
    return errors



def draft_section_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return SECTION_RE.findall(path.read_text(encoding="utf-8"))


def section_text(path: Path, section_id: str) -> str:
    text = path.read_text(encoding="utf-8")
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1) != section_id:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[match.end() : end].strip()
    return ""


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


def summarize_prewrite_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_slice_excerpts": [
            {
                "source_path": item.get("source_path", ""),
                "source_range": item.get("source_range", ""),
                "source_excerpt_sha256": item.get("source_excerpt_sha256", ""),
                "source_excerpt_text": item.get("source_excerpt_text", ""),
                "source_evidence": item.get("source_evidence", []),
                "style_fields_consumed": item.get("style_fields_consumed", []),
            }
            for item in payload.get("source_slice_bindings", [])
            if isinstance(item, dict)
        ],
        "source_performance_excerpt": payload.get("source_performance_excerpt", []),
        "source_performance_evidence": payload.get("source_performance_evidence", []),
        "technique_recall_contract": payload.get("technique_recall_contract", []),
        "scene_weave_contract": payload.get("scene_weave_contract", []),
        "source_style_granularity": payload.get("source_style_granularity", {}),
        "source_style_reference_assets": payload.get("source_style_reference_assets", []),
        "emotion_process": payload.get("emotion_process", {}),
        "continuous_moment_groups": payload.get("continuous_moment_groups", []),
        "paragraph_break_reasons": payload.get("paragraph_break_reasons", []),
        "sentence_relation_plan": payload.get("sentence_relation_plan", []),
        "function_word_strategy": payload.get("function_word_strategy", []),
        "emotion_shorthand_to_avoid": payload.get("emotion_shorthand_to_avoid", []),
        "target_emotion_landing_plan": payload.get("target_emotion_landing_plan", []),
        "no_fixed_short_sentence_ratio": payload.get("no_fixed_short_sentence_ratio"),
        "scene_logic_contract": payload.get("scene_logic_contract", {}),
        "source_emotion_parity": payload.get("source_emotion_parity", {}),
        "manual_judgment": payload.get("manual_judgment", ""),
    }


def build_raw_source_first_contract(payload: dict[str, Any]) -> dict[str, Any]:
    original_scene = payload.get("original_scene_granularity")
    return {
        "must_write_from_raw_excerpts_first": True,
        "read_order": [
            "source_slice_excerpts",
            "source_performance_excerpt",
            "source_performance_evidence",
            "technique_recall_contract",
            "scene_weave_contract",
            "source_style_granularity",
            "source_style_reference_assets",
            "original_scene_granularity.action_sequence",
            "emotion_process",
            "target_emotion_landing_plan",
            "sentence_relation_plan",
            "continuous_moment_groups",
            "paragraph_break_reasons",
        ],
        "hard_fail_if_skipped": [
            "不得脱离原文切片和原场动作顺序，改按抽象摘要首写正文。",
            "不得把原文切片压成更完整、更会解释的顺滑稿。",
            "不得先写功能节点，再靠写后扩写补颗粒。",
        ],
        "source_slice_excerpts": summarize_prewrite_payload(payload).get("source_slice_excerpts", []),
        "source_performance_excerpt": payload.get("source_performance_excerpt"),
        "source_performance_evidence": payload.get("source_performance_evidence", []),
        "technique_recall_contract": payload.get("technique_recall_contract", []),
        "scene_weave_contract": payload.get("scene_weave_contract", []),
        "source_style_granularity": payload.get("source_style_granularity", {}),
        "source_style_reference_assets": payload.get("source_style_reference_assets", []),
        "required_action_sequence": original_scene.get("action_sequence", "") if isinstance(original_scene, dict) else "",
        "required_body_object_space_control": (
            original_scene.get("body_object_space_control", "") if isinstance(original_scene, dict) else ""
        ),
        "required_dialogue_misfire": (
            original_scene.get("dialogue_forces_action", "") if isinstance(original_scene, dict) else ""
        ),
        "required_scene_end_residue": original_scene.get("scene_end_residue", "") if isinstance(original_scene, dict) else "",
        "emotion_process": payload.get("emotion_process", {}),
        "target_emotion_landing_plan": payload.get("target_emotion_landing_plan", []),
        "sentence_relation_plan": payload.get("sentence_relation_plan", []),
        "continuous_moment_groups": payload.get("continuous_moment_groups", []),
        "paragraph_break_reasons": payload.get("paragraph_break_reasons", []),
        "function_word_strategy": payload.get("function_word_strategy"),
        "telegraphic_risk": payload.get("telegraphic_risk"),
        "emotion_shorthand_to_avoid": payload.get("emotion_shorthand_to_avoid", []),
    }


def build_section_raw_source_first_task(
    section_id: str,
    packet_id: str,
    packet_sha256: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload_errors = validate_complete_granularity_payload(payload, section_id)
    if payload_errors:
        raise ValueError("; ".join(payload_errors))
    summary = summarize_prewrite_payload(payload)
    raw_source_first_contract = payload.get("raw_source_first_contract")
    if not isinstance(raw_source_first_contract, dict) or not raw_source_first_contract:
        raw_source_first_contract = build_raw_source_first_contract(payload)
    return {
        "section_id": section_id,
        "granularity_packet_id": packet_id,
        "granularity_packet_sha256": packet_sha256,
        "writing_priority": [
            "source_slice_excerpts",
            "source_performance_evidence",
            "technique_recall_contract",
            "scene_weave_contract",
            "source_style_granularity",
            "source_style_reference_assets",
            "emotion_process",
            "target_emotion_landing_plan",
            "raw_source_first_contract",
            "source_slice_bindings",
        ],
        "source_slice_bindings": payload.get("source_slice_bindings", []),
        "source_slice_excerpts": summary.get("source_slice_excerpts", []),
        "source_performance_evidence": summary.get("source_performance_evidence", []),
        "technique_recall_contract": summary.get("technique_recall_contract", []),
        "scene_weave_contract": summary.get("scene_weave_contract", []),
        "source_style_granularity": summary.get("source_style_granularity", {}),
        "source_style_reference_assets": summary.get("source_style_reference_assets", []),
        "emotion_process": summary.get("emotion_process", {}),
        "target_emotion_landing_plan": summary.get("target_emotion_landing_plan", []),
        "raw_source_first_contract": raw_source_first_contract,
    }


def prewrite_contract_matches(review: dict[str, Any], packet: dict[str, Any], draft: Path) -> bool:
    payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
    return (
        str(review.get("section_id") or "") == str(packet.get("section_id") or payload.get("section_id") or "")
        and Path(str(review.get("draft_path") or "")).resolve() == draft.resolve()
        and str(review.get("granularity_packet_id") or "") == str(packet.get("packet_id") or "")
        and str(review.get("granularity_packet_sha256") or "") == str(packet.get("packet_sha256") or "")
        and review.get("source_slice_bindings") == payload.get("source_slice_bindings")
        and review.get("contract_summary") == summarize_prewrite_payload(payload)
    )


def init_prewrite_review(receipt: Path, section_id: str, draft: Path, packet: dict[str, Any]) -> Path:
    payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
    path = section_prewrite_path(receipt, section_id)
    data = {
        "version": "1.0",
        "gate": "section_prewrite_granularity_review",
        "section_id": section_id,
        "draft_path": str(draft.resolve()),
        "granularity_packet_id": str(packet.get("packet_id") or ""),
        "granularity_packet_sha256": str(packet.get("packet_sha256") or ""),
        "source_slice_bindings": payload.get("source_slice_bindings", []),
        "contract_summary": summarize_prewrite_payload(payload),
        "confirmations": {name: False for name in PREWRITE_CONFIRMATIONS},
        "manual_judgment": "",
        "gate_status": "pending",
    }
    write_json(path, data)
    return path


def validate_prewrite_review(
    review_path: Path,
    section_id: str,
    packet: dict[str, Any],
    draft: Path,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        review = read_json(review_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"写前颗粒确认回执不可读取: {exc}"]
    if review.get("gate") != "section_prewrite_granularity_review":
        errors.append("写前颗粒确认 gate 必须为 section_prewrite_granularity_review")
    if str(review.get("section_id") or "") != section_id:
        errors.append("写前颗粒确认 section_id 不一致")
    if Path(str(review.get("draft_path") or "")).resolve() != draft.resolve():
        errors.append("写前颗粒确认绑定的正文路径不一致")
    if str(review.get("granularity_packet_id") or "") != str(packet.get("packet_id") or ""):
        errors.append("写前颗粒确认绑定的颗粒包 ID 不一致")
    if str(review.get("granularity_packet_sha256") or "") != str(packet.get("packet_sha256") or ""):
        errors.append("写前颗粒确认绑定的颗粒包 SHA 不一致")
    payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
    errors.extend(validate_complete_granularity_payload(payload, section_id))
    expected_bindings = payload.get("source_slice_bindings")
    if review.get("source_slice_bindings") != expected_bindings:
        errors.append("写前颗粒确认未完整继承本节原文切片绑定")
    if review.get("contract_summary") != summarize_prewrite_payload(payload):
        errors.append("写前颗粒确认的颗粒合同摘要已失效")
    confirmations = review.get("confirmations")
    if not isinstance(confirmations, dict) or set(confirmations) != set(PREWRITE_CONFIRMATIONS):
        errors.append("写前颗粒确认 confirmations 必须完整覆盖全部前置确认项")
    else:
        for name in PREWRITE_CONFIRMATIONS:
            if confirmations.get(name) is not True:
                errors.append(f"写前颗粒确认 {name} 必须为 true")
    if not str(review.get("manual_judgment") or "").strip():
        errors.append("写前颗粒确认 manual_judgment 不能为空")
    if review.get("gate_status") != "passed":
        errors.append("写前颗粒确认 gate_status 必须为 passed")
    return review, errors


def print_prewrite_contract(section_id: str, packet: dict[str, Any]) -> None:
    payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
    print(f"section_prewrite: section {section_id} contract")
    print(json.dumps(summarize_prewrite_payload(payload), ensure_ascii=False, indent=2))


def validate_raw_task_ref(value: Any, section_id: str, packet: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"第 {section_id} 节 raw_task_ref 必须是对象")
        return
    semantic_path = Path(str(value.get("path") or "")).expanduser().resolve()
    semantic_key = str(value.get("semantic_key") or "")
    fingerprint = str(value.get("fingerprint") or "")
    if not semantic_path.is_file():
        errors.append(f"第 {section_id} 节 raw_task_ref.path 不存在: {semantic_path}")
        return
    expected_key = f"section_raw_source_first_tasks.{section_id}"
    if semantic_key != expected_key:
        errors.append(f"第 {section_id} 节 raw_task_ref.semantic_key 必须为 {expected_key}")
        return
    try:
        semantic = read_json(semantic_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"第 {section_id} 节 raw_task_ref 指向的模型语义输入不可读取: {exc}")
        return
    tasks = semantic.get("section_raw_source_first_tasks")
    task = tasks.get(section_id) if isinstance(tasks, dict) else None
    if not isinstance(task, dict):
        errors.append(f"第 {section_id} 节缺少 section_raw_source_first_tasks.{section_id}")
        return
    try:
        expected_task = build_section_raw_source_first_task(
            section_id,
            str(packet.get("packet_id") or ""),
            str(packet.get("packet_sha256") or ""),
            packet.get("payload") if isinstance(packet.get("payload"), dict) else {},
        )
    except ValueError as exc:
        errors.append(str(exc))
        return
    if task != expected_task:
        errors.append(f"第 {section_id} 节首写原文任务已失效，必须重新导出")
    if fingerprint != task_fingerprint(task):
        errors.append(f"第 {section_id} 节 raw_task_ref.fingerprint 已失效")


def validate_receipt(
    path: Path,
    require_complete: bool = False,
    *,
    allow_open_with_content: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"回执无法读取: {exc}"]
    if data.get("gate") != "section_draft_execution":
        errors.append("gate 必须为 section_draft_execution")
    check_binding(data.get("outline_contract"), "outline_contract", errors)
    check_binding(data.get("source_receipt"), "source_receipt", errors)
    check_binding(data.get("section_source_bundle"), "section_source_bundle", errors)
    draft = Path(str(data.get("draft_path") or "")).expanduser().resolve()
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return data, errors + ["sections 必须是非空数组"]
    expected_ids = [str(item.get("section_id") or "") for item in sections if isinstance(item, dict)]
    completed_ids: list[str] = []
    open_count = 0

    for item in sections:
        if not isinstance(item, dict):
            errors.append("sections 含非对象")
            continue
        status = item.get("status")
        section_id = str(item.get("section_id") or "")
        if status == "completed":
            completed_ids.append(section_id)
            prewrite_path = check_binding(item.get("prewrite_review_receipt"), f"第 {section_id} 节 prewrite_review_receipt", errors)
            packet = None
            if prewrite_path:
                bundle_path = check_binding(data.get("section_source_bundle"), "section_source_bundle", errors)
                if bundle_path:
                    bundle = read_json(bundle_path)
                    packet = next(
                        (
                            packet_item
                            for packet_item in bundle.get("packets", [])
                            if isinstance(packet_item, dict) and str(packet_item.get("section_id") or "") == section_id
                        ),
                        None,
                    )
                    if not packet:
                        errors.append(f"第 {section_id} 节缺少逐节原文颗粒包")
                if packet:
                    _, prewrite_errors = validate_prewrite_review(prewrite_path, section_id, packet, draft)
                    errors.extend(prewrite_errors)
            if packet:
                validate_raw_task_ref(item.get("raw_task_ref"), section_id, packet, errors)
            for field in ("opened_at", "closed_at", "read_judgment", "manual_judgment", "section_sha256", "draft_sha256_after_close"):
                if not str(item.get(field) or "").strip():
                    errors.append(f"第 {section_id} 节缺少 {field}")
            for field in (
                "event_flow",
                "emotion_flow",
                "technique_recall_check",
                "scene_weave_check",
                "style_granularity",
                "telegraphic_and_relation_check",
            ):
                if item.get(field) != "passed":
                    errors.append(f"第 {section_id} 节 {field} 必须为 passed")
            records = item.get("source_read_records")
            bindings = item.get("source_slice_bindings")
            if not isinstance(records, list) or not isinstance(bindings, list) or len(records) != len(bindings):
                errors.append(f"第 {section_id} 节必须登记全部原文精确切片实读记录")
            check_binding(item.get("review_receipt"), f"第 {section_id} 节 review_receipt", errors)
        elif status == "open":
            open_count += 1
            prewrite_path = check_binding(item.get("prewrite_review_receipt"), f"第 {section_id} 节 prewrite_review_receipt", errors)
            packet = None
            if prewrite_path:
                bundle_path = check_binding(data.get("section_source_bundle"), "section_source_bundle", errors)
                if bundle_path:
                    bundle = read_json(bundle_path)
                    packet = next(
                        (
                            packet_item
                            for packet_item in bundle.get("packets", [])
                            if isinstance(packet_item, dict) and str(packet_item.get("section_id") or "") == section_id
                        ),
                        None,
                    )
                    if not packet:
                        errors.append(f"第 {section_id} 节缺少逐节原文颗粒包")
                if packet:
                    _, prewrite_errors = validate_prewrite_review(prewrite_path, section_id, packet, draft)
                    errors.extend(prewrite_errors)
            if packet:
                validate_raw_task_ref(item.get("raw_task_ref"), section_id, packet, errors)
            if not allow_open_with_content:
                current_content = section_text(draft, section_id) if draft.is_file() else ""
                if current_content:
                    errors.append(
                        f"第 {section_id} 节已有正文，但逐节停检尚未通过；"
                        "禁止把未停检内容当作合格首写继续流程"
                    )
        elif status != "pending":
            errors.append(f"第 {section_id} 节 status 无效: {status!r}")
    if open_count > 1:
        errors.append("同时只能打开一个小节")
    actual_ids = draft_section_ids(draft)
    allowed_ids = list(completed_ids)
    for item in sections:
        if not isinstance(item, dict) or item.get("status") != "open":
            continue
        open_section_id = str(item.get("section_id") or "")
        open_content = section_text(draft, open_section_id) if draft.is_file() else ""
        if open_content:
            allowed_ids.append(open_section_id)
    if actual_ids != allowed_ids:
        errors.append(
            "正文小节与逐节执行状态不一致；禁止先批量写完再补回执: "
            f"正文={actual_ids}, 已放行={allowed_ids}"
        )
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
    force: bool = False,
) -> int:
    if receipt.exists() and not force:
        print(f"逐节首写执行回执已存在，拒绝覆盖: {receipt}")
        return 2
    outline = read_json(outline_contract)
    source = read_json(source_receipt)
    bundle = read_json(section_source_bundle)
    if outline.get("gate_status") != "passed" or source.get("gate_status") != "passed":
        print("section_draft_execution: blocked\n- 细纲表演契约和拆文读取回执必须先通过")
        return 2
    if bundle.get("gate_status") != "passed":
        print("section_draft_execution: blocked\n- 逐节原文颗粒包必须先通过")
        return 2
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
        payload_errors = validate_complete_granularity_payload(packet.get("payload"), section_id)
        if payload_errors:
            print("section_draft_execution: blocked\n- " + "\n- ".join(payload_errors))
            return 2
        sections.append({
            "section_id": section_id,
            "status": "pending",
            "granularity_packet_id": str(packet.get("packet_id") or ""),
            "granularity_packet_sha256": str(packet.get("packet_sha256") or ""),
            "prewrite_review_receipt": {},
            "raw_task_ref": {},
            "source_slice_bindings": bindings,
            "source_read_records": [],
            "review_receipt": {},
            "opened_at": "",
            "closed_at": "",
            "read_judgment": "",
            "manual_judgment": "",
            "event_flow": "pending",
            "emotion_flow": "pending",
            "technique_recall_check": "pending",
            "scene_weave_check": "pending",
            "style_granularity": "pending",
            "telegraphic_and_relation_check": "pending",
            "section_sha256": "",
            "draft_sha256_after_close": "",
        })
    data = {
        "version": "1.0",
        "gate": "section_draft_execution",
        "outline_contract": binding(outline_contract),
        "source_receipt": binding(source_receipt),
        "section_source_bundle": binding(section_source_bundle),
        "draft_path": str(draft.resolve()),
        "sections": sections,
        "final_draft_sha256": "",
        "gate_status": "active",
    }
    write_json(receipt, data)
    print("section_draft_execution: initialized")
    return 0


def ensure_prewrite_review(receipt: Path, section_id: str) -> int:
    data, errors = validate_receipt(receipt, allow_open_with_content=True)
    ignored_prefixes = (
        f"第 {section_id} 节 prewrite_review_receipt",
        "写前颗粒确认 ",
    )
    filtered_errors = [
        error
        for error in errors
        if not any(error.startswith(prefix) for prefix in ignored_prefixes)
    ]
    if filtered_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(filtered_errors))
        return 2
    sections = data["sections"]
    target = next((item for item in sections if item["section_id"] == section_id), None)
    if not target:
        print("section_draft_execution: blocked\n- 目标小节不存在")
        return 2
    bundle_path = Path(str(data["section_source_bundle"]["path"])).resolve()
    bundle = read_json(bundle_path)
    packet = next(
        (
            item
            for item in bundle.get("packets", [])
            if isinstance(item, dict) and str(item.get("section_id") or "") == section_id
        ),
        None,
    )
    if not packet or packet.get("packet_sha256") != target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节颗粒包不存在或 SHA 不一致")
        return 2
    draft = Path(str(data["draft_path"])).resolve()
    prewrite_path = section_prewrite_path(receipt, section_id)
    if not prewrite_path.is_file():
        prewrite_path = init_prewrite_review(receipt, section_id, draft, packet)
        target["prewrite_review_receipt"] = binding(prewrite_path)
        write_json(receipt, data)
        print("section_draft_execution: blocked")
        print(f"- 第 {section_id} 节缺少写前颗粒确认，已初始化: {prewrite_path}")
        print("- 必须先确认原文颗粒合同并通过 gate_status=passed，才能 open-section")
        print_prewrite_contract(section_id, packet)
        return 2
    try:
        existing_review = read_json(prewrite_path)
    except (OSError, json.JSONDecodeError, ValueError):
        existing_review = {}
    if not prewrite_contract_matches(existing_review, packet, draft):
        prewrite_path = init_prewrite_review(receipt, section_id, draft, packet)
        target["prewrite_review_receipt"] = binding(prewrite_path)
        write_json(receipt, data)
        print("section_draft_execution: blocked")
        print(f"- 第 {section_id} 节写前颗粒确认已按最新颗粒包重建: {prewrite_path}")
        print("- 旧写前确认不得复用于新颗粒合同，必须重新逐项确认后才能 open-section")
        print_prewrite_contract(section_id, packet)
        return 2
    target["prewrite_review_receipt"] = binding(prewrite_path)
    write_json(receipt, data)
    _, prewrite_errors = validate_prewrite_review(prewrite_path, section_id, packet, draft)
    if prewrite_errors:
        print("section_draft_execution: blocked")
        for error in prewrite_errors:
            print(f"- {error}")
        print(f"- 请先完成写前颗粒确认: {prewrite_path}")
        print_prewrite_contract(section_id, packet)
        return 2
    return 0


def open_section(receipt: Path, section_id: str, read_judgment: str) -> int:
    prewrite_result = ensure_prewrite_review(receipt, section_id)
    if prewrite_result:
        return prewrite_result
    data, errors = validate_receipt(receipt)
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
    judgment = read_judgment.strip()
    if not judgment:
        print("section_draft_execution: blocked\n- read-judgment 不能为空")
        return 2
    if not target.get("granularity_packet_id") or not target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节缺少逐节原文颗粒包绑定")
        return 2
    bundle_path = Path(str(data["section_source_bundle"]["path"])).resolve()
    bundle = read_json(bundle_path)
    packet = next(
        (
            item
            for item in bundle.get("packets", [])
            if isinstance(item, dict) and str(item.get("section_id") or "") == section_id
        ),
        None,
    )
    if not packet or packet.get("packet_sha256") != target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节颗粒包不存在或 SHA 不一致")
        return 2
    payload = packet.get("payload")
    payload_errors = validate_complete_granularity_payload(payload, section_id)
    if payload_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(payload_errors))
        return 2
    packet_bindings = payload.get("source_slice_bindings") if isinstance(payload, dict) else None
    if not isinstance(packet_bindings, list) or not packet_bindings:
        print("section_draft_execution: blocked\n- 当前小节颗粒包缺少原文切片")
        return 2
    read_records: list[dict[str, Any]] = []
    printable: list[tuple[dict[str, Any], str]] = []
    for index, item in enumerate(packet_bindings, start=1):
        if not isinstance(item, dict):
            print(f"section_draft_execution: blocked\n- 第 {index} 个原文切片不是对象")
            return 2
        source_path = Path(str(item.get("source_path") or "")).resolve()
        if not source_path.is_file() or item.get("source_sha256") != sha256(source_path):
            print(f"section_draft_execution: blocked\n- 原文文件不存在或 SHA 已变化: {source_path}")
            return 2
        try:
            excerpt, ranges = source_excerpt(source_path, str(item.get("source_range") or ""))
        except ValueError as exc:
            print(f"section_draft_execution: blocked\n- {exc}")
            return 2
        excerpt_sha = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        if item.get("source_excerpt_sha256") != excerpt_sha:
            print(f"section_draft_execution: blocked\n- 原文精确行段 SHA 已变化: {source_path}")
            return 2
        if set(item.get("style_fields_consumed") or []) != set(STYLE_DIMENSIONS):
            print("section_draft_execution: blocked\n- 原文切片未完整绑定六类文风颗粒")
            return 2
        read_records.append(
            {
                "source_path": str(source_path),
                "source_sha256": item["source_sha256"],
                "source_range": item["source_range"],
                "source_excerpt_sha256": excerpt_sha,
                "ranges": [{"start": start, "end": end} for start, end in ranges],
                "read_at": now_iso(),
            }
        )
        printable.append((item, excerpt))
    review_path = section_review_path(receipt, section_id)
    review = {
        "version": "1.0",
        "gate": "section_draft_review",
        "section_id": section_id,
        "draft_path": data["draft_path"],
        "source_read_records": read_records,
        "checks": {
            "event_flow": review_check_template(),
            "emotion_flow": review_check_template(),
            "technique_recall_check": review_check_template(),
            "scene_weave_check": review_check_template(),
            "style_granularity": {
                "status": "pending",
                "dimensions": {name: review_check_template() for name in STYLE_DIMENSIONS},
                "judgment": "",
            },
            "telegraphic_and_relation_check": review_check_template(),
        },
        "manual_judgment": "",
        "gate_status": "pending",
    }
    write_json(review_path, review)
    target["status"] = "open"
    target["opened_at"] = now_iso()
    target["read_judgment"] = judgment
    target["source_read_records"] = read_records
    target["raw_task_ref"] = {}
    target["review_receipt"] = {"path": str(review_path.resolve()), "sha256": sha256(review_path)}
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} open")
    print(f"review: {review_path}")
    for index, (item, excerpt) in enumerate(printable, start=1):
        print(f"--- source slice {index}: {item['source_path']} {item['source_range']} ---")
        print(excerpt)
        print(f"--- end source slice {index} ---")
    print("--- raw source first contract ---")
    raw_source_first_contract = payload.get("raw_source_first_contract")
    if not isinstance(raw_source_first_contract, dict) or not raw_source_first_contract:
        raw_source_first_contract = build_raw_source_first_contract(payload)
    print(
        json.dumps(
            {
                "writing_priority": [
                    "source_slice_excerpts",
                    "source_performance_evidence",
                    "technique_recall_contract",
                    "scene_weave_contract",
                    "source_style_granularity",
                    "source_style_reference_assets",
                    "emotion_process",
                    "target_emotion_landing_plan",
                    "raw_source_first_contract",
                    "source_slice_bindings",
                    "draft_instructions",
                ],
                "raw_source_first_contract": raw_source_first_contract,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def bind_raw_source_first_task(receipt: Path, section_id: str, raw_task_ref: dict[str, str]) -> int:
    try:
        data = read_json(receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"section_draft_execution: blocked\n- 回执无法读取: {exc}")
        return 2
    binding_errors: list[str] = []
    for key in ("outline_contract", "source_receipt", "section_source_bundle"):
        check_binding(data.get(key), key, binding_errors)
    if binding_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(binding_errors))
        return 2
    sections = data.get("sections")
    if not isinstance(sections, list):
        print("section_draft_execution: blocked\n- sections 必须是数组")
        return 2
    target = next((item for item in sections if isinstance(item, dict) and item.get("section_id") == section_id), None)
    if not target or target["status"] != "open":
        print("section_draft_execution: blocked\n- 目标小节尚未 open")
        return 2
    bundle_path = Path(str(data["section_source_bundle"]["path"])).resolve()
    bundle = read_json(bundle_path)
    packet = next(
        (
            item
            for item in bundle.get("packets", [])
            if isinstance(item, dict) and str(item.get("section_id") or "") == section_id
        ),
        None,
    )
    if not packet:
        print("section_draft_execution: blocked\n- 当前小节缺少逐节原文颗粒包")
        return 2
    binding_errors = []
    validate_raw_task_ref(raw_task_ref, section_id, packet, binding_errors)
    if binding_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(binding_errors))
        return 2
    target["raw_task_ref"] = {
        "path": str(Path(str(raw_task_ref["path"])).expanduser().resolve()),
        "semantic_key": str(raw_task_ref["semantic_key"]),
        "fingerprint": str(raw_task_ref["fingerprint"]),
    }
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} raw-source task bound")
    return 0


def validate_review(
    review_path: Path,
    section_id: str,
    draft: Path,
    content: str,
    source_read_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        review = read_json(review_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"逐节停检回执不可读取: {exc}"]
    if review.get("gate") != "section_draft_review":
        errors.append("逐节停检 gate 必须为 section_draft_review")
    if str(review.get("section_id") or "") != section_id:
        errors.append("逐节停检 section_id 不一致")
    if Path(str(review.get("draft_path") or "")).resolve() != draft.resolve():
        errors.append("逐节停检绑定的正文路径不一致")
    if review.get("source_read_records") != source_read_records:
        errors.append("逐节停检没有完整继承本次原文实读记录")
    source_excerpts: list[str] = []
    for record in source_read_records:
        source_path = Path(str(record.get("source_path") or "")).resolve()
        if not source_path.is_file() or record.get("source_sha256") != sha256(source_path):
            errors.append(f"逐节停检绑定的原文不存在或 SHA 已变化: {source_path}")
            continue
        try:
            excerpt, _ = source_excerpt(source_path, str(record.get("source_range") or ""))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if record.get("source_excerpt_sha256") != hashlib.sha256(excerpt.encode("utf-8")).hexdigest():
            errors.append(f"逐节停检绑定的原文精确行段 SHA 已变化: {source_path}")
        source_excerpts.append(excerpt)

    def validate_check(name: str, value: Any, minimum: int = 2) -> None:
        if not isinstance(value, dict):
            errors.append(f"{name} 必须是对象")
            return
        if value.get("status") != "passed":
            errors.append(f"{name}.status 必须为 passed")
        if not str(value.get("judgment") or "").strip():
            errors.append(f"{name}.judgment 不能为空")
        source_evidence = value.get("source_evidence")
        target_evidence = value.get("target_evidence")
        if not isinstance(source_evidence, list) or len(source_evidence) < minimum:
            errors.append(f"{name}.source_evidence 至少需要 {minimum} 条")
        else:
            for quote in source_evidence:
                if not str(quote).strip() or not any(str(quote) in excerpt for excerpt in source_excerpts):
                    errors.append(f"{name} 原文证据不在本节实读切片内: {quote}")
        if not isinstance(target_evidence, list) or len(target_evidence) < minimum:
            errors.append(f"{name}.target_evidence 至少需要 {minimum} 条")
        else:
            for quote in target_evidence:
                if not str(quote).strip() or str(quote) not in content:
                    errors.append(f"{name} 目标证据不在当前小节正文内: {quote}")

    checks = review.get("checks")
    if not isinstance(checks, dict):
        return review, errors + ["逐节停检 checks 必须是对象"]
    validate_check("event_flow", checks.get("event_flow"))
    validate_check("emotion_flow", checks.get("emotion_flow"))
    validate_check("technique_recall_check", checks.get("technique_recall_check"))
    validate_check("scene_weave_check", checks.get("scene_weave_check"))
    validate_check("telegraphic_and_relation_check", checks.get("telegraphic_and_relation_check"))
    style = checks.get("style_granularity")
    if not isinstance(style, dict):
        errors.append("style_granularity 必须是对象")
    else:
        if style.get("status") != "passed":
            errors.append("style_granularity.status 必须为 passed")
        if not str(style.get("judgment") or "").strip():
            errors.append("style_granularity.judgment 不能为空")
        dimensions = style.get("dimensions")
        if not isinstance(dimensions, dict) or set(dimensions) != set(STYLE_DIMENSIONS):
            errors.append("style_granularity.dimensions 必须完整覆盖六类文风颗粒")
        else:
            for name in STYLE_DIMENSIONS:
                validate_check(f"style_granularity.{name}", dimensions.get(name))
    if not str(review.get("manual_judgment") or "").strip():
        errors.append("逐节停检 manual_judgment 不能为空")
    if review.get("gate_status") != "passed":
        errors.append("逐节停检 gate_status 必须为 passed")
    return review, errors


def close_section(receipt: Path, section_id: str, review_path: Path) -> int:
    data, errors = validate_receipt(receipt, allow_open_with_content=True)
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
    expected_review_path = section_review_path(receipt, section_id).resolve()
    if review_path.resolve() != expected_review_path:
        print(f"section_draft_execution: blocked\n- 必须使用当前小节停检回执: {expected_review_path}")
        return 2
    source_read_records = target.get("source_read_records")
    if not isinstance(source_read_records, list) or not source_read_records:
        print("section_draft_execution: blocked\n- 当前小节没有完整原文实读记录")
        return 2
    review, review_errors = validate_review(
        review_path,
        section_id,
        draft,
        content,
        source_read_records,
    )
    if review_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(review_errors))
        return 2
    checks = review["checks"]
    target.update({
        "status": "completed",
        "closed_at": now_iso(),
        "manual_judgment": review["manual_judgment"].strip(),
        "event_flow": checks["event_flow"]["status"],
        "emotion_flow": checks["emotion_flow"]["status"],
        "technique_recall_check": checks["technique_recall_check"]["status"],
        "scene_weave_check": checks["scene_weave_check"]["status"],
        "style_granularity": checks["style_granularity"]["status"],
        "telegraphic_and_relation_check": checks["telegraphic_and_relation_check"]["status"],
        "review_receipt": binding(review_path),
        "section_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "draft_sha256_after_close": sha256(draft),
    })
    if all(item["status"] == "completed" for item in data["sections"]):
        data["final_draft_sha256"] = sha256(draft)
        data["gate_status"] = "passed"
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} completed")
    return 0


def reset_section(receipt: Path, section_id: str) -> int:
    """Archive and reset the latest written section for a clean rewrite."""
    try:
        data = read_json(receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"section_draft_execution: blocked\n- 回执无法读取: {exc}")
        return 2
    binding_errors: list[str] = []
    for key in ("outline_contract", "source_receipt", "section_source_bundle"):
        check_binding(data.get(key), key, binding_errors)
    if binding_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(binding_errors))
        return 2
    sections = data.get("sections")
    if not isinstance(sections, list):
        print("section_draft_execution: blocked\n- sections 必须是数组")
        return 2
    target = next((item for item in sections if isinstance(item, dict) and item.get("section_id") == section_id), None)
    if not target or target.get("status") not in {"open", "completed"}:
        print("section_draft_execution: blocked\n- 只能重置已打开或已完成的小节")
        return 2
    target_index = sections.index(target)
    if any(item.get("status") != "pending" for item in sections[target_index + 1 :] if isinstance(item, dict)):
        print("section_draft_execution: blocked\n- 后续小节已有写作状态，必须从最后写入的小节开始重置")
        return 2
    draft = Path(str(data.get("draft_path") or "")).resolve()
    text = draft.read_text(encoding="utf-8") if draft.is_file() else ""
    matches = list(SECTION_RE.finditer(text))
    target_match = next((match for match in matches if match.group(1) == section_id), None)
    can_reset_without_archive = (
        target.get("status") == "open"
        and not target_match
        and not text.strip()
    )
    if not can_reset_without_archive:
        if not target_match or target_match != matches[-1]:
            print("section_draft_execution: blocked\n- 目标小节不是正文最后一个小节")
            return 2
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    archive_dir = receipt.parent / "首稿小节归档"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path: Path | None = None
    if target_match:
        archive_path = archive_dir / f"第{section_id}节-{timestamp}.md"
        archive_path.write_text(text[target_match.start() :].rstrip() + "\n", encoding="utf-8")
        retained = text[: target_match.start()].rstrip()
        draft.write_text((retained + "\n") if retained else "", encoding="utf-8")
    elif can_reset_without_archive:
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("", encoding="utf-8")
    old_review = section_review_path(receipt, section_id)
    if old_review.is_file():
        old_review.replace(archive_dir / f"第{section_id}节停检-{timestamp}.json")
    target.update(
        {
            "status": "pending",
            "source_read_records": [],
            "raw_task_ref": {},
            "review_receipt": {},
            "opened_at": "",
            "closed_at": "",
            "read_judgment": "",
            "manual_judgment": "",
            "event_flow": "pending",
            "emotion_flow": "pending",
            "technique_recall_check": "pending",
            "scene_weave_check": "pending",
            "style_granularity": "pending",
            "telegraphic_and_relation_check": "pending",
            "section_sha256": "",
            "draft_sha256_after_close": "",
        }
    )
    data["final_draft_sha256"] = ""
    data["gate_status"] = "active"
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} reset")
    if archive_path is not None:
        print(f"archive: {archive_path}")
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
    bind_task = sub.add_parser("bind-raw-task")
    bind_task.add_argument("--receipt", required=True)
    bind_task.add_argument("--section", required=True)
    bind_task.add_argument("--path", required=True)
    bind_task.add_argument("--semantic-key", required=True)
    bind_task.add_argument("--fingerprint", required=True)
    prewrite = sub.add_parser("ensure-prewrite-review")
    prewrite.add_argument("--receipt", required=True)
    prewrite.add_argument("--section", required=True)
    closing = sub.add_parser("close-section")
    closing.add_argument("--receipt", required=True)
    closing.add_argument("--section", required=True)
    closing.add_argument("--review", required=True)
    reset = sub.add_parser("reset-section")
    reset.add_argument("--receipt", required=True)
    reset.add_argument("--section", required=True)
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
    if args.command == "bind-raw-task":
        return bind_raw_source_first_task(
            receipt,
            args.section,
            {
                "path": args.path,
                "semantic_key": args.semantic_key,
                "fingerprint": args.fingerprint,
            },
        )
    if args.command == "ensure-prewrite-review":
        return ensure_prewrite_review(receipt, args.section)
    if args.command == "close-section":
        return close_section(receipt, args.section, Path(args.review).resolve())
    if args.command == "reset-section":
        return reset_section(receipt, args.section)
    _, errors = validate_receipt(receipt, require_complete=True)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    print("section_draft_execution: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
