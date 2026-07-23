#!/usr/bin/env python3
"""Generate and validate the mandatory post-write human semantic review receipt."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from validate_sequence_contract import validate as validate_sequence_contract
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


REQUIRED_HUMAN_CHECKS = (
    "author_motive_substitution",
    "narrator_voice_boundary",
    "narrator_voice_distribution",
    "redundant_explanation",
    "observable_scene_basis",
    "dialogue_efficiency",
    "long_window_dialogue_efficiency",
    "cross_block_rhythm_contrast",
    "global_structure_and_chapter_endings",
    "protagonist_irregularity_and_agency",
    "technical_detail_function",
    "dialogue_pattern_variation",
    "interpersonal_exchange_full_text_review",
    "author_substitution_in_exchange",
    "conflict_carrier_distribution",
    "physical_object_space_consequence",
    "irreversible_violence_genre_alignment",
    "premise_genre_promise_alignment",
    "core_selling_point_payoff",
    "direct_psychology_externalization",
    "post_emotion_summary_residue",
    "result_reporting_chain",
    "thesis_dialogue_concreteness",
    "chapter_end_hook_naturalness",
    "ending_action_completion",
    "rule_evidence_stiffness_and_liveliness",
    "source_granularity_preservation",
    "section_four_axis_review",
    "full_text_storyboard_construction_list_review",
    "restraint_overexplained",
    "high_value_scene_summary_compression",
    "full_text_legacy_rescan",
)

NARRATOR_OR_AUTHOR = {"narrator_voice", "author_summary", "neutral"}
CHASE_WIFE_REQUIRED_RULES = {
    "female_softening_externalized",
    "female_softening_trigger_relevance",
    "irreversible_exit_timing",
    "no_emotional_after_summary",
    "repair_failure_fact_based",
}
FULL_TEXT_FLOW_CHECK = "full_text_storyboard_construction_list_review"
SOURCE_GRANULARITY_CHECK = "source_granularity_preservation"
SECTION_FOUR_AXIS_CHECK = "section_four_axis_review"
SECTION_HEADING_PATTERN = re.compile(r"^\s*(\d+)[.、．]\s*$", re.MULTILINE)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewable_units(text: str) -> list[dict[str, Any]]:
    kept_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    flattened = "\n".join(kept_lines)
    units: list[dict[str, Any]] = []
    cursor = 0
    canonical_cursor = 0
    for match in re.finditer(
        r'.*?(?:[。！？?!](?:["”’』】])?|$)',
        flattened,
        flags=re.DOTALL,
    ):
        quote = match.group(0).strip()
        if not quote:
            continue
        position = text.find(quote, cursor)
        if position < 0:
            position = text.find(quote)
        line_number = text.count("\n", 0, max(position, 0)) + 1
        canonical = re.sub(r"\s+", "", quote)
        units.append(
            {
                "line": line_number,
                "quote": quote,
                "canonical": canonical,
                "canonical_start": canonical_cursor,
                "canonical_end": canonical_cursor + len(canonical),
            }
        )
        canonical_cursor += len(canonical)
        if position >= 0:
            cursor = position + len(quote)
    return units


def changed_lines(base_text: str, current_text: str) -> list[dict[str, Any]]:
    base_units = reviewable_units(base_text)
    current_units = reviewable_units(current_text)
    matcher = difflib.SequenceMatcher(
        a=[item["canonical"] for item in base_units],
        b=[item["canonical"] for item in current_units],
        autojunk=False,
    )
    changed_indexes: set[int] = set()
    for tag, _, _, current_start, current_end in matcher.get_opcodes():
        if tag in {"insert", "replace"}:
            changed_indexes.update(range(current_start, current_end))

    changed: list[dict[str, Any]] = []
    for index, unit in enumerate(current_units):
        if index not in changed_indexes:
            continue
        changed.append(
            {
                "line": unit["line"],
                "quote": unit["quote"],
                "status": "pending",
                "scene_observable_basis": "",
                "narrator_or_author": "pending",
                "redundant_explanation": None,
                "substitutes_character_motive": None,
                "decision": "pending",
                "reason": "",
            }
        )
    return changed


def create_receipt(
    project: str,
    text_path: Path,
    base_text_path: Path | None = None,
) -> dict[str, Any]:
    resolved_text = text_path.resolve()
    if not resolved_text.is_file():
        raise FileNotFoundError(f"正文不存在: {resolved_text}")

    resolved_base = base_text_path.resolve() if base_text_path else None
    if resolved_base and not resolved_base.is_file():
        raise FileNotFoundError(f"母稿不存在: {resolved_base}")

    current_text = read_text(resolved_text)
    base_text = read_text(resolved_base) if resolved_base else ""
    return {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "review_mode": "revision_diff" if resolved_base else "full_text",
        "text": {
            "path": str(resolved_text),
            "sha256": sha256(resolved_text),
        },
        "base_text": (
            {
                "path": str(resolved_base),
                "sha256": sha256(resolved_base),
            }
            if resolved_base
            else None
        ),
        "automation_limits_acknowledged": False,
        "reviewed_full_text": False,
        "confirmed_after_final_revision": False,
        "automated_scan": {
            "status": "pending",
            "artifacts": [],
            "summary": "",
        },
        "human_checks": [
            create_human_check_entry(check_id) for check_id in REQUIRED_HUMAN_CHECKS
        ],
        "genre_formula_review": {
            "status": "pending",
            "selected_genre": "",
            "source_files": [],
            "rules": [],
            "conclusion": "",
        },
        "changed_sentence_reviews": changed_lines(base_text, current_text)
        if resolved_base
        else [],
    }


def create_human_check_entry(check_id: str) -> dict[str, Any]:
    entry = {
        "id": check_id,
        "status": "pending",
        "evidence": [],
        "conclusion": "",
    }
    if check_id == FULL_TEXT_FLOW_CHECK:
        entry.update(
            {
                "scan_scope": "full_text",
                "remaining_storyboard_or_construction_list": None,
                "symptoms_checked": [],
                "allowed_in_story_artifacts": [],
            }
        )
    if check_id == SOURCE_GRANULARITY_CHECK:
        entry.update(
            {
                "scan_scope": "full_text",
                "source_scenes_checked": [],
                "remaining_result_broadcast_chain": None,
                "remaining_granularity_shrinkage": None,
            }
        )
    if check_id == SECTION_FOUR_AXIS_CHECK:
        entry.update(
            {
                "scan_scope": "all_sections",
                "all_sections_reviewed": None,
                "section_reviews": [],
            }
        )
    return entry


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_sequence_receipt_for_text(
    sequence_receipt_path: Path,
    text_path: Path,
) -> list[str]:
    try:
        data = json.loads(sequence_receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"顺序契约回执无效: {exc}"]
    if not isinstance(data, dict):
        return ["顺序契约回执必须是 JSON 对象"]
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        return ["顺序契约回执缺少 artifacts"]
    paths: dict[str, Path] = {}
    for key in ("setting", "outline", "draft"):
        binding = artifacts.get(key)
        if not isinstance(binding, dict) or not str(binding.get("path") or "").strip():
            return [f"顺序契约回执缺少 {key} 绑定"]
        paths[key] = Path(str(binding["path"])).resolve()
    return validate_sequence_contract(
        sequence_receipt_path.resolve(),
        paths["setting"],
        paths["outline"],
        text_path.resolve(),
    )


def validate_receipt(
    receipt_path: Path,
    text_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    resolved_text = text_path.resolve()
    if not resolved_text.is_file():
        return [f"正文不存在: {resolved_text}"], {
            "human_check_count": len(REQUIRED_HUMAN_CHECKS),
            "reviewed_human_checks": 0,
            "reviewed_genre_rules": 0,
            "changed_sentence_count": 0,
            "reviewed_changed_sentences": 0,
        }

    current_text = read_text(resolved_text)
    text_info = data.get("text") if isinstance(data.get("text"), dict) else {}
    if str(text_info.get("path") or "") != str(resolved_text):
        errors.append("回执绑定的正文路径与当前正文不一致")
    if text_info.get("sha256") != sha256(resolved_text):
        errors.append("正文已变化，必须重新执行人工语义复核")

    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if data.get("automation_limits_acknowledged") is not True:
        errors.append("必须确认自动脚本不能替代人工语义判断")
    if data.get("reviewed_full_text") is not True:
        errors.append("必须确认已人工复扫全文")
    if data.get("confirmed_after_final_revision") is not True:
        errors.append("必须确认人工复核发生在最终一次正文修改之后")

    automated_scan = data.get("automated_scan")
    if not isinstance(automated_scan, dict):
        errors.append("automated_scan 必须是对象")
    else:
        if automated_scan.get("status") != "completed":
            errors.append("自动脚本预扫尚未完成")
        if not nonempty_strings(automated_scan.get("artifacts")):
            errors.append("自动脚本预扫缺少产物记录")
        if not str(automated_scan.get("summary") or "").strip():
            errors.append("自动脚本预扫缺少结果摘要")

    human_entries = data.get("human_checks")
    actual_human: dict[str, dict[str, Any]] = {}
    if isinstance(human_entries, list):
        actual_human = {
            str(item.get("id") or ""): item
            for item in human_entries
            if isinstance(item, dict) and str(item.get("id") or "")
        }
    else:
        errors.append("human_checks 必须是列表")

    for check_id in sorted(set(REQUIRED_HUMAN_CHECKS) - set(actual_human)):
        errors.append(f"缺少人工检查项: {check_id}")
    for check_id in sorted(set(actual_human) - set(REQUIRED_HUMAN_CHECKS)):
        errors.append(f"存在未知人工检查项: {check_id}")

    reviewed_human_checks = 0
    for check_id in REQUIRED_HUMAN_CHECKS:
        entry = actual_human.get(check_id)
        if not entry:
            continue
        if entry.get("status") != "passed":
            errors.append(f"人工检查项尚未通过: {check_id}")
            continue
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"人工检查项缺少正文证据: {check_id}")
            continue
        valid_evidence = True
        for index, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                errors.append(f"人工证据格式错误: {check_id}[{index}]")
                valid_evidence = False
                continue
            quote = str(item.get("quote") or "").strip()
            judgment = str(item.get("judgment") or "").strip()
            action = str(item.get("action") or "").strip()
            if not quote or quote not in current_text:
                errors.append(f"人工证据原句不在正文中: {check_id}[{index}]")
                valid_evidence = False
            if not judgment:
                errors.append(f"人工证据缺少语义判断: {check_id}[{index}]")
                valid_evidence = False
            if action != "keep":
                errors.append(
                    f"人工证据仍需回修，当前检查不得通过: {check_id}[{index}]"
                )
                valid_evidence = False
        if not str(entry.get("conclusion") or "").strip():
            errors.append(f"人工检查项缺少结论: {check_id}")
            valid_evidence = False
        if check_id == FULL_TEXT_FLOW_CHECK and not validate_full_text_flow_check(
            entry, current_text, errors
        ):
            valid_evidence = False
        if check_id == SOURCE_GRANULARITY_CHECK and not validate_source_granularity_check(
            entry, current_text, errors
        ):
            valid_evidence = False
        if check_id == SECTION_FOUR_AXIS_CHECK and not validate_section_four_axis_check(
            entry, current_text, errors
        ):
            valid_evidence = False
        if valid_evidence:
            reviewed_human_checks += 1

    genre_review = data.get("genre_formula_review")
    reviewed_genre_rules = 0
    if not isinstance(genre_review, dict):
        errors.append("genre_formula_review 必须是对象")
    else:
        if genre_review.get("status") != "completed":
            errors.append("题材公式专项复核尚未完成")
        selected_genre = str(genre_review.get("selected_genre") or "").strip()
        if not selected_genre:
            errors.append("题材公式专项复核缺少 selected_genre")
        source_files = genre_review.get("source_files")
        if not isinstance(source_files, list) or not source_files:
            errors.append("题材公式专项复核缺少 source_files")
            source_files = []
        for index, source in enumerate(source_files, start=1):
            if not isinstance(source, dict):
                errors.append(f"题材公式来源格式错误: [{index}]")
                continue
            source_path = Path(str(source.get("path") or "")).resolve()
            source_sha = str(source.get("sha256") or "").strip()
            if not source_path.is_file():
                errors.append(f"题材公式来源不存在: {source_path}")
                continue
            if not source_sha:
                errors.append(f"题材公式来源缺少 sha256: [{index}]")
            elif source_sha != sha256(source_path):
                errors.append(f"题材公式来源已变化，必须重新复核: {source_path}")
        if not str(genre_review.get("conclusion") or "").strip():
            errors.append("题材公式专项复核缺少 conclusion")

        genre_rules = genre_review.get("rules")
        actual_rule_ids: set[str] = set()
        if not isinstance(genre_rules, list) or not genre_rules:
            errors.append("题材公式专项复核必须逐条列出适用规则")
            genre_rules = []
        for index, item in enumerate(genre_rules, start=1):
            if not isinstance(item, dict):
                errors.append(f"题材公式规则格式错误: [{index}]")
                continue
            rule_id = str(item.get("id") or "").strip()
            rule_text = str(item.get("rule") or "").strip()
            if not rule_id:
                errors.append(f"题材公式规则缺少 id: [{index}]")
            else:
                actual_rule_ids.add(rule_id)
            if not rule_text:
                errors.append(f"题材公式规则缺少 rule: [{index}]")
            if item.get("status") != "passed":
                errors.append(f"题材公式规则尚未通过: {rule_id or index}")
                continue
            evidence = item.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"题材公式规则缺少正文证据: {rule_id or index}")
                continue
            valid_rule = True
            for evidence_index, evidence_item in enumerate(evidence, start=1):
                if not isinstance(evidence_item, dict):
                    errors.append(
                        f"题材公式证据格式错误: {rule_id or index}[{evidence_index}]"
                    )
                    valid_rule = False
                    continue
                quote = str(evidence_item.get("quote") or "").strip()
                judgment = str(evidence_item.get("judgment") or "").strip()
                action = str(evidence_item.get("action") or "").strip()
                if not quote or quote not in current_text:
                    errors.append(
                        f"题材公式证据原句不在正文中: {rule_id or index}[{evidence_index}]"
                    )
                    valid_rule = False
                if not judgment:
                    errors.append(
                        f"题材公式证据缺少判断: {rule_id or index}[{evidence_index}]"
                    )
                    valid_rule = False
                if action != "keep":
                    errors.append(
                        f"题材公式证据仍需回修: {rule_id or index}[{evidence_index}]"
                    )
                    valid_rule = False
            if valid_rule:
                reviewed_genre_rules += 1

        if "追妻" in selected_genre:
            missing_rules = sorted(CHASE_WIFE_REQUIRED_RULES - actual_rule_ids)
            for rule_id in missing_rules:
                errors.append(f"追妻题缺少强制专项规则: {rule_id}")

    base_info = data.get("base_text")
    expected_changed: list[dict[str, Any]] = []
    if isinstance(base_info, dict):
        base_path = Path(str(base_info.get("path") or "")).resolve()
        if not base_path.is_file():
            errors.append(f"母稿不存在: {base_path}")
        else:
            if base_info.get("sha256") != sha256(base_path):
                errors.append("母稿已变化，必须重新生成人工复核清单")
            expected_changed = changed_lines(read_text(base_path), current_text)
    elif data.get("review_mode") == "revision_diff":
        errors.append("局部或专项回炉必须绑定母稿")

    changed_entries = data.get("changed_sentence_reviews")
    if not isinstance(changed_entries, list):
        changed_entries = []
        errors.append("changed_sentence_reviews 必须是列表")

    expected_keys = {(item["line"], item["quote"]) for item in expected_changed}
    actual_keys = {
        (item.get("line"), str(item.get("quote") or ""))
        for item in changed_entries
        if isinstance(item, dict)
    }
    for line, quote in sorted(expected_keys - actual_keys):
        errors.append(f"改写句缺少人工复核: 第 {line} 行 {quote}")
    for line, quote in sorted(actual_keys - expected_keys):
        errors.append(f"人工复核含过期改写句: 第 {line} 行 {quote}")

    reviewed_changed_sentences = 0
    for index, item in enumerate(changed_entries, start=1):
        if not isinstance(item, dict):
            errors.append(f"改写句复核格式错误: [{index}]")
            continue
        if item.get("status") != "reviewed":
            errors.append(f"改写句尚未人工复核: 第 {item.get('line')} 行")
            continue
        valid = True
        if not str(item.get("scene_observable_basis") or "").strip():
            errors.append(f"改写句缺少现场可观察依据: 第 {item.get('line')} 行")
            valid = False
        if item.get("narrator_or_author") not in NARRATOR_OR_AUTHOR:
            errors.append(f"改写句未区分叙述者与作者站位: 第 {item.get('line')} 行")
            valid = False
        if not isinstance(item.get("redundant_explanation"), bool):
            errors.append(f"改写句未判断是否多余解释: 第 {item.get('line')} 行")
            valid = False
        if not isinstance(item.get("substitutes_character_motive"), bool):
            errors.append(f"改写句未判断是否代判人物动机: 第 {item.get('line')} 行")
            valid = False
        if item.get("decision") != "keep":
            errors.append(
                f"当前正文仍含待 revise/delete 的改写句，必须先改正文再重建回执: 第 {item.get('line')} 行"
            )
            valid = False
        if not str(item.get("reason") or "").strip():
            errors.append(f"改写句缺少保留理由: 第 {item.get('line')} 行")
            valid = False
        if valid:
            reviewed_changed_sentences += 1

    return errors, {
        "human_check_count": len(REQUIRED_HUMAN_CHECKS),
        "reviewed_human_checks": reviewed_human_checks,
        "reviewed_genre_rules": reviewed_genre_rules,
        "changed_sentence_count": len(expected_changed),
        "reviewed_changed_sentences": reviewed_changed_sentences,
    }


def validate_full_text_flow_check(
    entry: dict[str, Any],
    current_text: str,
    errors: list[str],
) -> bool:
    valid = True
    if entry.get("scan_scope") != "full_text":
        errors.append("全文分镜/施工单检查必须声明 scan_scope=full_text")
        valid = False
    if entry.get("remaining_storyboard_or_construction_list") is not False:
        errors.append("全文仍存在分镜清单或规则施工稿时不得通过")
        valid = False

    symptoms = nonempty_strings(entry.get("symptoms_checked"))
    if len(symptoms) < 3:
        errors.append("全文分镜/施工单检查必须覆盖至少三类症状")
        valid = False
    symptom_text = " / ".join(symptoms)
    required_terms = ("一句一个动作", "一句一个证据", "一句一个反应", "规则施工")
    if not any(term in symptom_text for term in required_terms):
        errors.append("全文分镜/施工单症状必须覆盖动作、证据、反应或规则施工")
        valid = False

    artifacts = entry.get("allowed_in_story_artifacts")
    if not isinstance(artifacts, list):
        errors.append("allowed_in_story_artifacts 必须是列表")
        return False
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, dict):
            errors.append(f"情节内清单/报告例外格式错误: [{index}]")
            valid = False
            continue
        quote = str(artifact.get("quote") or "").strip()
        reason = str(artifact.get("reason") or "").strip()
        if not quote or quote not in current_text:
            errors.append(f"情节内清单/报告例外原句不在正文中: [{index}]")
            valid = False
        if not reason:
            errors.append(f"情节内清单/报告例外缺少情节合理性说明: [{index}]")
            valid = False
    return valid


def validate_source_granularity_check(
    entry: dict[str, Any],
    current_text: str,
    errors: list[str],
) -> bool:
    valid = True
    if entry.get("scan_scope") != "full_text":
        errors.append("原文颗粒度保持检查必须声明 scan_scope=full_text")
        valid = False
    if entry.get("remaining_result_broadcast_chain") is not False:
        errors.append("仍存在结果播报链时，不得通过原文颗粒度保持检查")
        valid = False
    if entry.get("remaining_granularity_shrinkage") is not False:
        errors.append("仍存在原文颗粒度缩水时，不得通过原文颗粒度保持检查")
        valid = False

    source_scenes = entry.get("source_scenes_checked")
    if not isinstance(source_scenes, list) or not source_scenes:
        errors.append("原文颗粒度保持检查必须逐场列出 source_scenes_checked")
        return False
    for index, item in enumerate(source_scenes, start=1):
        label = f"原文颗粒度场景复核[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            valid = False
            continue
        for field in (
            "target_scene",
            "source_granularity",
            "target_granularity",
            "scene_resistance",
            "control_right_change",
            "information_delay",
            "external_order_or_bystander_pressure",
            "result_broadcast_chain_judgment",
            "decision",
        ):
            if not str(item.get(field) or "").strip():
                errors.append(f"{label}.{field} 不能为空")
                valid = False
        quote = str(item.get("target_quote") or "").strip()
        if not quote or quote not in current_text:
            errors.append(f"{label}.target_quote 必须引用当前正文原句")
            valid = False
        if item.get("decision") != "keep":
            errors.append(f"{label} 仍需回修，不得通过: decision={item.get('decision')!r}")
            valid = False
        broadcast_judgment = str(item.get("result_broadcast_chain_judgment") or "")
        if any(
            phrase in broadcast_judgment
            for phrase in ("真相公开即可", "现场混乱即可", "已经承认", "整体成立")
        ):
            errors.append(f"{label}.result_broadcast_chain_judgment 不能用结果概括代替颗粒度反证")
            valid = False
    return valid


def validate_section_four_axis_check(
    entry: dict[str, Any],
    current_text: str,
    errors: list[str],
) -> bool:
    valid = True
    if entry.get("scan_scope") != "all_sections":
        errors.append("逐段四轴复查必须声明 scan_scope=all_sections")
        valid = False
    if entry.get("all_sections_reviewed") is not True:
        errors.append("逐段四轴复查必须确认 all_sections_reviewed=true")
        valid = False

    expected_sections = SECTION_HEADING_PATTERN.findall(current_text)
    section_reviews = entry.get("section_reviews")
    if not isinstance(section_reviews, list):
        errors.append("section_four_axis_review.section_reviews 必须是列表")
        return False
    actual_sections = []
    for index, item in enumerate(section_reviews, start=1):
        label = f"逐段四轴复查[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            valid = False
            continue
        section_id = str(item.get("section_id") or "").strip()
        actual_sections.append(section_id)
        if not section_id:
            errors.append(f"{label}.section_id 不能为空")
            valid = False
        for field in (
            "section_role",
            "source_granularity_preservation",
            "genre_promise_alignment",
            "process_evidence_smoothness",
            "interaction_exchange_and_conflict_carrier",
            "revision_scope_decision",
            "decision",
        ):
            if not str(item.get(field) or "").strip():
                errors.append(f"{label}.{field} 不能为空")
                valid = False
        quote = str(item.get("representative_quote") or "").strip()
        if not quote or quote not in current_text:
            errors.append(f"{label}.representative_quote 必须引用当前正文原句")
            valid = False
        if item.get("decision") != "keep":
            errors.append(f"{label} 仍需回修，不得通过: decision={item.get('decision')!r}")
            valid = False
        if item.get("revision_scope_decision") not in {
            "keep",
            "sentence_hotspot",
            "paragraph_cluster",
            "full_scene",
            "coarse_block",
            "global_structure",
        }:
            errors.append(f"{label}.revision_scope_decision 值无效")
            valid = False
    if expected_sections:
        expected_set = set(expected_sections)
        actual_set = set(actual_sections)
        missing = sorted(expected_set - actual_set, key=lambda value: int(value))
        extra = sorted(actual_set - expected_set)
        if missing:
            errors.append("逐段四轴复查缺少正文小节: " + ", ".join(missing))
            valid = False
        if extra:
            errors.append("逐段四轴复查含正文不存在的小节: " + ", ".join(extra))
            valid = False
    return valid


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mandatory post-write human semantic review gate."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="生成人工语义复核回执")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--text", required=True)
    init_parser.add_argument("--base-text")
    init_parser.add_argument("--receipt", required=True)
    init_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="校验人工语义复核回执")
    validate_parser.add_argument("--receipt", required=True)
    validate_parser.add_argument("--text", required=True)
    validate_parser.add_argument("--sequence-receipt", required=True)

    args = parser.parse_args()
    receipt_path = Path(args.receipt).resolve()
    if args.command == "init":
        if receipt_path.exists() and not args.force:
            print(f"人工复核回执已存在，拒绝覆盖: {receipt_path}")
            return 2
        try:
            receipt = create_receipt(
                args.project,
                Path(args.text),
                Path(args.base_text) if args.base_text else None,
            )
        except FileNotFoundError as exc:
            print("post_write_human_review_gate: blocked")
            print(f"- {exc}")
            return 2
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("post_write_human_review_gate: initialized")
        print(f"receipt: {receipt_path}")
        print(f"mode: {receipt['review_mode']}")
        print(f"changed_sentences: {len(receipt['changed_sentence_reviews'])}")
        return 0

    if not receipt_path.is_file():
        print(f"人工复核回执不存在: {receipt_path}")
        return 2
    text_path = Path(args.text)
    errors = validate_sequence_receipt_for_text(
        Path(args.sequence_receipt).resolve(),
        text_path,
    )
    review_errors, summary = validate_receipt(receipt_path, text_path)
    errors.extend(review_errors)
    print(f"receipt: {receipt_path}")
    print(f"human_checks: {summary['reviewed_human_checks']}/{summary['human_check_count']}")
    print(
        "changed_sentences: "
        f"{summary['reviewed_changed_sentences']}/{summary['changed_sentence_count']}"
    )
    if errors:
        print("post_write_human_review_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("post_write_human_review_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
