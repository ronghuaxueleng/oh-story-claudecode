#!/usr/bin/env python3
"""Enforce strictly sequential first-draft writing and per-section review."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(r"(?m)^(\d+)\.\s*$")
OUTLINE_SECTION_RE = re.compile(r"(?m)^##\s+(\d+)\.")
DIRECT_DIALOGUE_RE = re.compile(
    r"「[^」]*」(?:[^「」\n]{0,40}「[^」]*」)*|“[^”]*”(?:[^“”\n]{0,40}“[^”]*”)*"
)
ATTRIBUTION_RE = re.compile(
    r"[^。！？\n]{0,16}(?:说|问|答|道|回|喊|叫|告诉|回应|解释|追问|提醒)"
)
SF_DIMENSIONS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)

CHAR_COUNT_TOLERANCE = 0.20
CHAR_COUNT_SHORTFALL_GRACE = 100


def iter_direct_dialogue_matches(text: str) -> list[re.Match[str]]:
    return list(DIRECT_DIALOGUE_RE.finditer(text))


def extract_direct_dialogue(text: str) -> list[str]:
    return [match.group(0) for match in iter_direct_dialogue_matches(text)]


def tolerated_char_range(minimum: int, maximum: int) -> tuple[int, int]:
    """Return the inclusive actual-draft range allowed around a planned budget."""
    return (
        max(0, math.ceil(minimum * (1 - CHAR_COUNT_TOLERANCE)) - CHAR_COUNT_SHORTFALL_GRACE),
        math.floor(maximum * (1 + CHAR_COUNT_TOLERANCE)),
    )


def char_count_within_tolerance(count: int, minimum: int, maximum: int) -> bool:
    tolerated_minimum, tolerated_maximum = tolerated_char_range(minimum, maximum)
    return tolerated_minimum <= count <= tolerated_maximum


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"文件不存在: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 无效: {path}: {exc}")
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def apply_section_review_mechanical_normalization(
    review_path: Path,
    staged_path: Path,
) -> list[str]:
    script_path = Path(__file__).with_name("normalize_section_review.py")
    spec = importlib.util.spec_from_file_location("normalize_section_review", script_path)
    if spec is None or spec.loader is None:
        return [f"无法加载逐节回执机械归一化入口: {script_path}"]
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        _, errors = module.apply_normalization(review_path, staged_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"逐节回执机械归一化失败: {exc}"]
    return list(errors)


def write_section_context(state_path: Path, section_id: str, output_path: Path) -> None:
    script_path = Path(__file__).with_name("prepare_section_context.py")
    spec = importlib.util.spec_from_file_location("prepare_section_context", script_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载小节写作包入口: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = module.build_context(state_path, section_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_section_review_sidecar(
    review_path: Path,
    staged_path: Path,
    sidecar_path: Path,
) -> None:
    script_path = Path(__file__).with_name("manage_section_review.py")
    spec = importlib.util.spec_from_file_location("manage_section_review", script_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载逐节人工侧车入口: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.apply_template(review_path, staged_path, sidecar_path)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def non_whitespace_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def split_sections(text: str) -> tuple[str, dict[str, str], list[str]]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return text, {}, []
    prefix = text[: matches[0].start()]
    sections: dict[str, str] = {}
    order: list[str] = []
    for index, match in enumerate(matches):
        sid = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[sid] = text[match.end() : end].strip()
        order.append(sid)
    return prefix, sections, order


def load_committed_draft(draft_path: Path, staged_mode: bool) -> tuple[str, list[str]]:
    """A staged first section may create正文.md only after all checks pass."""
    if draft_path.is_file():
        return draft_path.read_text(encoding="utf-8"), []
    if staged_mode:
        return "", []
    return "", ["正文不存在"]


def expected_ids(emotion_receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    contracts = emotion_receipt.get("section_contracts")
    if not isinstance(contracts, list):
        raise ValueError("情绪合同缺少 section_contracts")
    emotion_lookup: dict[str, dict[str, Any]] = {}
    plot_lookup: dict[str, dict[str, Any]] = {}
    original_emotion_ids: list[str] = []
    original_plot_ids: list[str] = []
    for item in contracts:
        if not isinstance(item, dict):
            continue
        for beat in item.get("source_emotion_beats", []):
            if isinstance(beat, dict) and beat.get("beat_id"):
                beat_id = str(beat["beat_id"])
                emotion_lookup[beat_id] = beat
                original_emotion_ids.append(beat_id)
        for beat in item.get("required_plot_beats", []):
            if isinstance(beat, dict) and beat.get("beat_id"):
                beat_id = str(beat["beat_id"])
                plot_lookup[beat_id] = beat
                original_plot_ids.append(beat_id)
    assignments = emotion_receipt.get("section_beat_assignments")
    if not isinstance(assignments, list) or not assignments:
        assignments = [
            {
                "section_id": item.get("section_id"),
                "emotion_beat_ids": [beat.get("beat_id") for beat in item.get("source_emotion_beats", [])],
                "plot_beat_ids": [beat.get("beat_id") for beat in item.get("required_plot_beats", [])],
            }
            for item in contracts
            if isinstance(item, dict)
        ]
    assigned_emotion_ids: list[str] = []
    assigned_plot_ids: list[str] = []
    for item in assignments:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("section_id") or "")
        e_ids = [str(value) for value in item.get("emotion_beat_ids", [])]
        p_ids = [str(value) for value in item.get("plot_beat_ids", [])]
        assigned_emotion_ids.extend(e_ids)
        assigned_plot_ids.extend(p_ids)
        result[sid] = {
            "emotion_beat_ids": e_ids,
            "plot_beat_ids": p_ids,
            "emotion_beat_contracts": [emotion_lookup[beat_id] for beat_id in e_ids if beat_id in emotion_lookup],
            "plot_beat_contracts": [plot_lookup[beat_id] for beat_id in p_ids if beat_id in plot_lookup],
        }
    if assigned_emotion_ids != original_emotion_ids or assigned_plot_ids != original_plot_ids:
        raise ValueError("section_beat_assignments 必须分别与 E/P 全集完全同序相等")
    return result


def validate_sf_assignments(prose: dict[str, Any], expected: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    errors: list[str] = []
    by_section = {sid: [] for sid in expected}
    source_reviews = prose.get("source_subflow_reviews")
    assignments = prose.get("section_sf_assignments")
    if not isinstance(source_reviews, list) or not source_reviews:
        return by_section, ["文字合同缺少 source_subflow_reviews，不能证明主体 SF 全量分配"]
    if not isinstance(assignments, list) or not assignments:
        return by_section, ["文字合同缺少写前 section_sf_assignments"]
    source_ids = [str(item.get("subflow_id")) for item in source_reviews if isinstance(item, dict)]
    seen: set[str] = set()
    assignment_ids: list[str] = []
    for item in assignments:
        if not isinstance(item, dict):
            errors.append("source_subflow_reviews 每项必须是对象")
            continue
        sf_id = str(item.get("subflow_id") or "")
        if not sf_id or sf_id in seen:
            errors.append(f"SF 编号缺失或重复: {sf_id}")
            continue
        seen.add(sf_id)
        assignment_ids.append(sf_id)
        targets = item.get("target_sections")
        if not isinstance(targets, list) or not targets:
            errors.append(f"{sf_id} 尚未在正文前分配 target_sections")
            continue
        normalized = [str(value) for value in targets]
        if len(normalized) != len(set(normalized)) or any(sid not in expected for sid in normalized):
            errors.append(f"{sf_id} target_sections 含重复或未知小节: {normalized}")
            continue
        if len(str(item.get("target_section_rationale") or "").strip()) < 20:
            errors.append(f"{sf_id} 缺少非模板化 target_section_rationale")
        for sid in normalized:
            by_section[sid].append(sf_id)
    if assignment_ids != source_ids:
        errors.append(f"section_sf_assignments 必须与主体 SF 全集同序相等: expected={source_ids}, actual={assignment_ids}")
    for sid, sf_ids in by_section.items():
        if not sf_ids:
            errors.append(f"第 {sid} 节未分配任何 SF 文字颗粒")
    return by_section, errors


def validate_detail_assignments(prose: dict[str, Any], expected: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    by_section = {sid: [] for sid in expected}
    reviews = prose.get("source_detail_card_reviews")
    catalog = (prose.get("primary_detail_catalog") or {}).get("required_card_ids") or []
    if not catalog:
        return by_section, []
    if not isinstance(reviews, list):
        return by_section, ["full_bridge 文字合同缺少 source_detail_card_reviews"]
    actual = [str(item.get("card_id")) for item in reviews if isinstance(item, dict)]
    if actual != [str(value) for value in catalog]:
        return by_section, ["主体细节卡必须与 primary_detail_catalog 全集同序等数"]
    errors: list[str] = []
    for item in reviews:
        card_id = str(item.get("card_id") or "")
        targets = [str(value) for value in item.get("target_sections", [])]
        if item.get("planning_status") != "passed":
            errors.append(f"{card_id}.planning_status 必须在逐节正文初始化前为 passed")
        if not targets or any(sid not in expected for sid in targets):
            errors.append(f"{card_id}.target_sections 必须绑定真实目标小节")
            continue
        for field in ("target_adaptation", "distinct_function_to_preserve", "overlap_is_not_omission"):
            if len(str(item.get(field) or "").strip()) < 12:
                errors.append(f"{card_id}.{field} 缺少写前逐卡计划")
        for sid in targets:
            by_section[sid].append(card_id)
    return by_section, errors


def validate_stale_draft_reset(
    prose: dict[str, Any], emotion: dict[str, Any], draft_path: Path
) -> list[str]:
    errors: list[str] = []
    bindings = [
        ("文字合同", prose.get("draft")),
        ("情绪合同", (emotion.get("bindings") or {}).get("draft")),
    ]
    for label, binding in bindings:
        if not isinstance(binding, dict) or not binding.get("sha256"):
            continue
        reset = prose.get("section_progress_reset") if label == "文字合同" else emotion.get("section_progress_reset")
        if not isinstance(reset, dict):
            errors.append(f"{label}仍绑定旧正文，缺少 section_progress_reset")
            continue
        if reset.get("previous_draft_sha256") != binding.get("sha256"):
            errors.append(f"{label} section_progress_reset 未绑定旧正文 SHA")
        archive_path = Path(str(reset.get("archived_draft_path") or ""))
        if not archive_path.is_file():
            errors.append(f"{label}旧正文归档不存在")
        else:
            archive_sha = sha256_file(archive_path)
            if archive_sha != binding.get("sha256"):
                if reset.get("previous_binding_was_stale") is not True:
                    errors.append(f"{label}旧绑定与归档 SHA 不一致，必须显式标记 previous_binding_was_stale=true")
                if reset.get("archived_draft_sha256") != archive_sha:
                    errors.append(f"{label} section_progress_reset 未绑定实际归档 SHA")
        if reset.get("current_draft_must_be_absent") is not True:
            errors.append(f"{label} section_progress_reset 必须声明 current_draft_must_be_absent=true")
    if draft_path.exists() and draft_path.read_text(encoding="utf-8").strip():
        errors.append("重开逐节正文时当前 draft 路径必须不存在或为空")
    return errors


def validate_budget(data: dict[str, Any], expected: list[str]) -> tuple[int, int, dict[str, dict[str, int]]]:
    total_min = data.get("total_min_chars")
    total_max = data.get("total_max_chars")
    if not isinstance(total_min, int) or not isinstance(total_max, int) or total_min <= 0 or total_max < total_min:
        raise ValueError("字数预算必须提供有效的 total_min_chars / total_max_chars")
    entries = data.get("sections")
    if not isinstance(entries, list):
        raise ValueError("字数预算 sections 必须是列表")
    budgets: dict[str, dict[str, int]] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("字数预算 sections 每项必须是对象")
        sid = str(item.get("section_id") or "")
        minimum = item.get("min_chars")
        maximum = item.get("max_chars")
        if sid in budgets or sid not in expected:
            raise ValueError(f"字数预算包含重复或未知小节: {sid}")
        if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum <= 0 or maximum < minimum:
            raise ValueError(f"第 {sid} 节字数预算无效")
        budgets[sid] = {"min_chars": minimum, "max_chars": maximum}
    if list(budgets) != expected:
        raise ValueError(f"字数预算小节必须连续且完整: expected={expected}, actual={list(budgets)}")
    if sum(item["min_chars"] for item in budgets.values()) < total_min:
        raise ValueError("各节 min_chars 之和不得低于 total_min_chars")
    if sum(item["max_chars"] for item in budgets.values()) > total_max:
        raise ValueError("各节 max_chars 之和不得高于 total_max_chars")
    return total_min, total_max, budgets


def fail(stage: str, errors: list[str]) -> int:
    print(f"section_progress_gate: blocked ({stage})")
    for error in errors:
        print(f"- {error}")
    return 1


def command_init(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    outline_path = Path(args.outline).resolve()
    draft_path = Path(args.draft).resolve()
    prose_path = Path(args.prose_receipt).resolve()
    emotion_path = Path(args.emotion_receipt).resolve()
    budget_path = Path(args.budget).resolve()
    if state_path.exists():
        return fail("init", [f"状态文件已存在，禁止覆盖: {state_path}"])
    if draft_path.exists() and draft_path.read_text(encoding="utf-8").strip():
        return fail("init", ["初始化逐节闸门前正文必须不存在或为空；旧稿应先归档"])
    try:
        outline_text = outline_path.read_text(encoding="utf-8")
        outline_ids = OUTLINE_SECTION_RE.findall(outline_text)
        expected = [str(index) for index in range(1, len(outline_ids) + 1)]
        if outline_ids != expected or not expected:
            raise ValueError(f"大纲数字小节必须从 1 连续排列: {outline_ids}")
        prose = load_json(prose_path)
        generation_ids = [str(item.get("section_id")) for item in prose.get("section_generation_plans", []) if isinstance(item, dict)]
        if generation_ids != expected:
            raise ValueError("文字合同 section_generation_plans 未与大纲连续小节完全一致")
        sf_assignments, sf_errors = validate_sf_assignments(prose, expected)
        if sf_errors:
            raise ValueError("；".join(sf_errors))
        detail_assignments, detail_errors = validate_detail_assignments(prose, expected)
        if detail_errors:
            raise ValueError("；".join(detail_errors))
        emotion = load_json(emotion_path)
        reset_errors = validate_stale_draft_reset(prose, emotion, draft_path)
        if reset_errors:
            raise ValueError("；".join(reset_errors))
        beat_ids = expected_ids(emotion)
        if list(beat_ids) != expected:
            raise ValueError("情绪合同 section_contracts 未与大纲连续小节完全一致")
        total_min, total_max, budgets = validate_budget(load_json(budget_path), expected)
    except (OSError, ValueError) as exc:
        return fail("init", [str(exc)])
    state = {
        "version": "1.1",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "ready",
        "current_section": "1",
        "expected_sections": expected,
        "paths": {
            "outline": str(outline_path),
            "draft": str(draft_path),
            "prose_receipt": str(prose_path),
            "emotion_receipt": str(emotion_path),
            "budget": str(budget_path),
        },
        "source_bindings": {
            "outline_sha256": sha256_file(outline_path),
            "prose_receipt_sha256": sha256_file(prose_path),
            "emotion_receipt_sha256": sha256_file(emotion_path),
            "budget_sha256": sha256_file(budget_path),
        },
        "total_budget": {"min_chars": total_min, "max_chars": total_max},
        "sections": [
            {
                "section_id": sid,
                "status": "pending",
                **budgets[sid],
                "emotion_beat_ids": list(beat_ids[sid]["emotion_beat_ids"]),
                "plot_beat_ids": list(beat_ids[sid]["plot_beat_ids"]),
                "required_sf_ids": sf_assignments[sid],
                "required_detail_card_ids": detail_assignments[sid],
                "review_path": "",
                "text_sha256": "",
                "char_count": 0,
            }
            for sid in expected
        ],
    }
    write_json(state_path, state)
    print("section_progress_gate: initialized")
    print(f"state: {state_path}")
    print(f"current_section: 1/{len(expected)}")
    return 0


def get_section_state(state: dict[str, Any], sid: str) -> dict[str, Any]:
    for item in state.get("sections", []):
        if str(item.get("section_id")) == sid:
            return item
    raise ValueError(f"状态中不存在第 {sid} 节")


def hydrate_section_beat_contracts(
    item: dict[str, Any],
    emotion_receipt: dict[str, Any],
    sid: str,
) -> dict[str, Any]:
    """Resolve full E/P source contracts from the canonical emotion receipt."""
    assignments = expected_ids(emotion_receipt)
    assignment = assignments.get(sid)
    if assignment is None:
        raise ValueError(f"情绪合同没有第 {sid} 节的 E/P 分配")
    hydrated = copy.deepcopy(item)
    hydrated["emotion_beat_ids"] = list(assignment["emotion_beat_ids"])
    hydrated["plot_beat_ids"] = list(assignment["plot_beat_ids"])
    hydrated["emotion_beat_contracts"] = copy.deepcopy(assignment["emotion_beat_contracts"])
    hydrated["plot_beat_contracts"] = copy.deepcopy(assignment["plot_beat_contracts"])
    return hydrated


def verify_source_bindings(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bindings = state.get("source_bindings", {})
    paths = state.get("paths", {})
    for key in ("outline", "prose_receipt", "emotion_receipt", "budget"):
        path = Path(str(paths.get(key) or ""))
        expected_sha = str(bindings.get(f"{key}_sha256") or "")
        if not path.is_file():
            errors.append(f"绑定文件不存在: {path}")
        elif sha256_file(path) != expected_sha:
            errors.append(f"绑定文件已变化，必须重新初始化逐节闸门: {path}")
    return errors


def validate_first_draft_plan(plan: dict[str, Any], item: dict[str, Any], sid: str) -> list[str]:
    errors: list[str] = []
    if str(plan.get("section_id")) != sid:
        errors.append("场面计划 section_id 与当前节不一致")
    if plan.get("mode") != "single_pass_scene_realization":
        errors.append("场面计划 mode 必须为 single_pass_scene_realization")
    target_chars = plan.get("target_chars")
    if not isinstance(target_chars, int) or not int(item.get("min_chars", 0)) <= target_chars <= int(item.get("max_chars", 0)):
        errors.append(f"target_chars 必须在本节预算 {item.get('min_chars')}-{item.get('max_chars')} 内")
    scene_units = plan.get("scene_units")
    if not isinstance(scene_units, list) or not 1 <= len(scene_units) <= 3:
        return errors + ["scene_units 必须包含 1-3 个完整场面"]
    actual_e: list[str] = []
    actual_p: list[str] = []
    allocated = 0
    scene_ids: list[str] = []
    for index, scene in enumerate(scene_units, start=1):
        label = f"scene_units[{index}]"
        if not isinstance(scene, dict):
            errors.append(f"{label} 必须是对象")
            continue
        scene_id = str(scene.get("scene_id") or "")
        scene_ids.append(scene_id)
        actual_e.extend(str(value) for value in scene.get("emotion_beat_ids", []))
        actual_p.extend(str(value) for value in scene.get("plot_beat_ids", []))
        scene_chars = scene.get("allocated_chars")
        if not isinstance(scene_chars, int) or scene_chars < 240:
            errors.append(f"{label}.allocated_chars 必须至少 240，不得把承重场压成梗概")
        else:
            allocated += scene_chars
        if scene.get("full_scene_required") is not True or scene.get("summary_only") is not False:
            errors.append(f"{label} 必须声明 full_scene_required=true 且 summary_only=false")
        if len(str(scene.get("entry_pressure") or "").strip()) < 12:
            errors.append(f"{label}.entry_pressure 缺具体进场压力")
        chain = scene.get("interaction_chain")
        if not isinstance(chain, list) or len(chain) < 3 or any(len(str(value).strip()) < 8 for value in chain):
            errors.append(f"{label}.interaction_chain 至少需要 3 步“施压-接招-再变化”")
        for field in ("turning_action", "visible_consequence", "aftershock", "reader_emotion_path"):
            if len(str(scene.get(field) or "").strip()) < 12:
                errors.append(f"{label}.{field} 缺少可表演的具体内容")
    if not all(scene_ids) or len(scene_ids) != len(set(scene_ids)):
        errors.append("scene_id 不得为空或重复")
    if actual_e != item.get("emotion_beat_ids"):
        errors.append(f"场面计划 E 拍必须完整同序: expected={item.get('emotion_beat_ids')}, actual={actual_e}")
    if actual_p != item.get("plot_beat_ids"):
        errors.append(f"场面计划 P 拍必须完整同序: expected={item.get('plot_beat_ids')}, actual={actual_p}")
    if isinstance(target_chars, int) and allocated != target_chars:
        errors.append(f"场面分配字数之和必须等于 target_chars: allocated={allocated}, target={target_chars}")
    if plan.get("append_or_expand_after_target_write_forbidden") is not True:
        errors.append("场面计划必须声明 append_or_expand_after_target_write_forbidden=true")
    return errors


def verify_committed_draft_integrity(state: dict[str, Any]) -> list[str]:
    """Reject stale green state after any out-of-band draft replacement."""
    draft_path = Path(str((state.get("paths") or {}).get("draft") or ""))
    if not draft_path.is_file():
        return [] if not any(item.get("status") == "passed" for item in state.get("sections", [])) else ["已提交正文不存在"]
    draft_text = draft_path.read_text(encoding="utf-8")
    _, sections, order = split_sections(draft_text)
    passed = [str(item.get("section_id")) for item in state.get("sections", []) if item.get("status") == "passed"]
    errors: list[str] = []
    if order[: len(passed)] != passed:
        errors.append(f"正文已提交小节顺序与状态不一致: expected_prefix={passed}, actual={order}")
    for item in state.get("sections", []):
        if item.get("status") != "passed":
            continue
        sid = str(item.get("section_id"))
        if sha256_text(sections.get(sid, "")) != item.get("text_sha256"):
            errors.append(f"第 {sid} 节通过后被外部改写，旧 passed 立即失效")
    final_sha = str(state.get("final_draft_sha256") or "")
    if state.get("status") == "final_ready" and (not final_sha or sha256_file(draft_path) != final_sha):
        errors.append("当前正文 SHA 与 final_ready 绑定 SHA 不一致，旧完成态立即失效")
    return errors


def scene_units_match_upstream(plan_units: Any, upstream_units: Any) -> bool:
    if not isinstance(plan_units, list) or not isinstance(upstream_units, list):
        return False
    normalized = copy.deepcopy(plan_units)
    for scene in normalized:
        if not isinstance(scene, dict):
            return False
        target_ids = scene.pop("target_emotion_beat_ids", None)
        if target_ids is not None:
            scene["emotion_beat_ids"] = target_ids
    return normalized == upstream_units


def materialize_compact_plan(
    plan: dict[str, Any],
    upstream_units: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve the compact plan against the already-bound outline receipt."""
    refs = plan.get("scene_unit_refs")
    if not isinstance(refs, list):
        return plan
    by_id = {
        str(item.get("scene_id") or ""): item
        for item in upstream_units
        if isinstance(item, dict) and str(item.get("scene_id") or "")
    }
    expected_ids = [str(item.get("scene_id") or "") for item in upstream_units]
    actual_ids = [str(item.get("scene_id") or "") for item in refs if isinstance(item, dict)]
    if actual_ids != expected_ids:
        raise ValueError("紧凑场面计划的 scene_unit_refs 必须与细纲场面原序一致")
    hydrated = copy.deepcopy(plan)
    hydrated["scene_units"] = [copy.deepcopy(by_id[scene_id]) for scene_id in actual_ids]
    return hydrated


def command_start(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    try:
        state = load_json(state_path)
    except ValueError as exc:
        return fail("start-section", [str(exc)])
    sid = str(args.section)
    errors = verify_source_bindings(state)
    if state.get("status") not in ("ready", "in_progress"):
        errors.append(f"当前状态不能开始小节: {state.get('status')}")
    if str(state.get("current_section")) != sid:
        errors.append(f"只能开始当前第 {state.get('current_section')} 节，不能开始第 {sid} 节")
    try:
        item = get_section_state(state, sid)
    except ValueError as exc:
        errors.append(str(exc))
        item = {}
    try:
        plan_path = Path(args.plan).resolve()
        plan = load_json(plan_path)
    except ValueError as exc:
        errors.append(str(exc))
        plan_path = Path(args.plan).resolve()
        plan = {}
    outline_receipt = Path(state["paths"]["outline"]).resolve().parent / "写作资产" / "细纲表演验收回执.json"
    if not outline_receipt.is_file():
        errors.append(f"写前必须存在细纲表演验收回执: {outline_receipt}")
    else:
        try:
            outline_payload = load_json(outline_receipt)
            outline_entry = next(
                entry for entry in outline_payload.get("sections", [])
                if isinstance(entry, dict) and str(entry.get("section_id")) == sid
            )
            upstream_units = outline_entry.get("scene_units")
            if not isinstance(upstream_units, list) or not upstream_units:
                errors.append(f"细纲表演验回执未为第 {sid} 节提供 scene_units，必须先回写小节大纲")
            else:
                try:
                    materialized_plan = materialize_compact_plan(plan, upstream_units)
                except ValueError as exc:
                    errors.append(str(exc))
                    materialized_plan = plan
                if not scene_units_match_upstream(
                    materialized_plan.get("scene_units"), upstream_units
                ):
                    errors.append("当前节计划与已通过的细纲 scene_units 不一致，不得在正文阶段临时改容量")
                plan = materialized_plan
            if plan.get("outline_performance_receipt_sha256") != sha256_file(outline_receipt):
                errors.append("当前节计划未绑定最新细纲表演验收回执 SHA")
        except (ValueError, StopIteration) as exc:
            errors.append(f"细纲表演验回执无法读取当前节: {exc}")
    errors.extend(validate_first_draft_plan(plan, item, sid))
    if item.get("status") != "pending":
        errors.append(f"第 {sid} 节状态必须是 pending，实际为 {item.get('status')}")
    draft_path = Path(state["paths"]["draft"])
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    _, sections, order = split_sections(draft_text)
    prior = [str(index) for index in range(1, int(sid))]
    if order != prior:
        errors.append(f"开始第 {sid} 节前正文只能包含已通过小节 {prior}，实际为 {order}")
    for previous_sid in prior:
        previous = get_section_state(state, previous_sid)
        if previous.get("status") != "passed":
            errors.append(f"第 {previous_sid} 节尚未 passed")
        elif sha256_text(sections.get(previous_sid, "")) != previous.get("text_sha256"):
            errors.append(f"第 {previous_sid} 节通过后被修改，必须停止并重开受影响小节")
    if errors:
        return fail("start-section", errors)
    item["status"] = "writing"
    item["started_at"] = now_iso()
    item["prior_section_hashes"] = {previous_sid: sha256_text(sections[previous_sid]) for previous_sid in prior}
    item["first_draft_plan_path"] = str(plan_path)
    item["first_draft_plan_sha256"] = sha256_file(plan_path)
    state["status"] = "in_progress"
    state["updated_at"] = now_iso()
    write_json(state_path, state)
    context_output = getattr(args, "context_output", None)
    if context_output:
        try:
            write_section_context(state_path, sid, Path(context_output).resolve())
        except (OSError, ValueError) as exc:
            return fail("start-section", [f"小节已启动，但写作包生成失败: {exc}"])
    print(f"section_progress_gate: section_started ({sid})")
    print(f"budget: {item['min_chars']}-{item['max_chars']} chars")
    print(f"required_emotion_beats: {','.join(item['emotion_beat_ids'])}")
    print(f"required_plot_beats: {','.join(item['plot_beat_ids'])}")
    print(f"target_chars: {plan['target_chars']}")
    if context_output:
        print(f"section_context: {Path(context_output).resolve()}")
    print("next_step: write one complete staged section, then commit-section; do not append or expand正文.md")
    return 0


def collect_quotes(value: Any, key: str = "") -> list[str]:
    quotes: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            lowered = child_key.lower()
            if lowered.startswith("source_"):
                continue
            if isinstance(child, str) and ("quote" in lowered or lowered in {"evidence", "target_sentence"}):
                if child.strip():
                    quotes.append(child.strip())
            else:
                quotes.extend(collect_quotes(child, child_key))
    elif isinstance(value, list):
        for child in value:
            quotes.extend(collect_quotes(child, key))
    return quotes


def require_review_group(
    prose_review: dict[str, Any], field: str, expected_count: int, section_text: str, errors: list[str]
) -> None:
    items = prose_review.get(field)
    if not isinstance(items, list) or len(items) != expected_count:
        errors.append(f"prose_review.{field} 必须逐项覆盖写前包: expected={expected_count}")
        return
    for index, item in enumerate(items, start=1):
        label = f"{field}[{index}]"
        if not isinstance(item, dict) or item.get("status") != "passed":
            errors.append(f"{label}.status 必须为 passed")
            continue
        target_quotes = item.get("target_quotes")
        if not isinstance(target_quotes, list) or not target_quotes:
            errors.append(f"{label} 缺少 target_quotes")
        elif any(not isinstance(quote, str) or quote not in section_text for quote in target_quotes):
            errors.append(f"{label} target_quotes 必须全部来自当前节")
        if len(str(item.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{label} manual_judgment 过短")


def validate_sf_reviews(
    prose: dict[str, Any], prose_review: dict[str, Any], required_ids: list[str], section_text: str
) -> list[str]:
    errors: list[str] = []
    source_items = {
        str(item.get("subflow_id")): item
        for item in prose.get("source_subflow_reviews", [])
        if isinstance(item, dict) and item.get("subflow_id")
    }
    reviews = prose_review.get("source_subflow_reviews")
    if not isinstance(reviews, list):
        return ["prose_review.source_subflow_reviews 必须覆盖本节全部 SF"]
    actual_ids = [str(item.get("subflow_id")) for item in reviews if isinstance(item, dict)]
    if actual_ids != required_ids:
        errors.append(f"本节 SF 必须完整同序: expected={required_ids}, actual={actual_ids}")
        return errors
    for review in reviews:
        sf_id = str(review.get("subflow_id"))
        source = source_items.get(sf_id, {})
        if review.get("status") != "passed":
            errors.append(f"{sf_id}.status 必须为 passed")
        if review.get("semantic_review_method") != "current_model_manual":
            errors.append(f"{sf_id}.semantic_review_method 必须为 current_model_manual")
        if review.get("automation_used_for_semantic_judgment") is not False:
            errors.append(f"{sf_id}.automation_used_for_semantic_judgment 必须为 false")
        if len(str(review.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{sf_id}.manual_judgment 过短")
        required_steps = source.get("required_sequence") or []
        step_reviews = review.get("required_sequence_reviews")
        if not isinstance(step_reviews, list) or [item.get("source_step") for item in step_reviews if isinstance(item, dict)] != required_steps:
            errors.append(f"{sf_id}.required_sequence_reviews 必须逐步同序覆盖 SF 必经链")
        else:
            for index, step_review in enumerate(step_reviews, start=1):
                label = f"{sf_id}.required_sequence_reviews[{index}]"
                quotes = step_review.get("target_quotes")
                if step_review.get("status") != "passed":
                    errors.append(f"{label}.status 必须为 passed")
                if not isinstance(quotes, list) or not quotes or any(not isinstance(q, str) or q not in section_text for q in quotes):
                    errors.append(f"{label}.target_quotes 必须来自当前节")
                for field in ("visible_change", "manual_judgment"):
                    if len(str(step_review.get(field) or "").strip()) < 16:
                        errors.append(f"{label}.{field} 缺少当前步骤的独特结果裁决")
        dimensions = review.get("dimension_transfers")
        source_dimensions = source.get("source_style_granularity", {})
        if not isinstance(dimensions, dict):
            errors.append(f"{sf_id} 缺少 dimension_transfers")
            continue
        for dimension in SF_DIMENSIONS:
            label = f"{sf_id}.{dimension}"
            item = dimensions.get(dimension)
            source_evidence = (source_dimensions.get(dimension) or {}).get("source_evidence", [])
            if not isinstance(item, dict):
                errors.append(f"{label} 缺失")
                continue
            target_quotes = item.get("target_quotes")
            if not isinstance(target_quotes, list) or not target_quotes:
                errors.append(f"{label}.target_quotes 不能为空")
            elif any(not isinstance(quote, str) or quote not in section_text for quote in target_quotes):
                errors.append(f"{label}.target_quotes 必须全部来自当前节")
            mappings = item.get("evidence_mappings")
            if not isinstance(mappings, list) or len(mappings) != len(source_evidence):
                errors.append(f"{label}.evidence_mappings 必须逐条覆盖全部主体证据")
            else:
                mapped_parent_quotes: list[str] = []
                for index, mapping in enumerate(mappings):
                    if not isinstance(mapping, dict) or mapping.get("source_quote") != source_evidence[index]:
                        errors.append(f"{label}.evidence_mappings[{index + 1}] 来源证据错位")
                        continue
                    mapped_quotes = mapping.get("target_quotes")
                    if not isinstance(mapped_quotes, list) or not mapped_quotes or any(
                        not isinstance(quote, str) or quote not in section_text for quote in mapped_quotes
                    ):
                        errors.append(f"{label}.evidence_mappings[{index + 1}] 缺少当前节目标引句")
                    else:
                        for quote in mapped_quotes:
                            if quote not in mapped_parent_quotes:
                                mapped_parent_quotes.append(quote)
                    if len(str(mapping.get("comparison") or "").strip()) < 16:
                        errors.append(f"{label}.evidence_mappings[{index + 1}].comparison 过短")
                if target_quotes != mapped_parent_quotes:
                    errors.append(f"{label}.target_quotes 必须由逐条证据映射同序汇总")
            if len(str(item.get("comparison") or "").strip()) < 20:
                errors.append(f"{label}.comparison 过短")
            if item.get("surface_copy_rejected") is not True:
                errors.append(f"{label}.surface_copy_rejected 必须为 true")
    return errors


def validate_detail_reviews(
    prose: dict[str, Any], prose_review: dict[str, Any], required_ids: list[str], section_text: str
) -> list[str]:
    source = {str(item.get("card_id")): item for item in prose.get("source_detail_card_reviews", []) if isinstance(item, dict)}
    reviews = prose_review.get("source_detail_card_reviews")
    if not isinstance(reviews, list):
        return ["prose_review.source_detail_card_reviews 必须覆盖本节主体细节卡"] if required_ids else []
    actual = [str(item.get("card_id")) for item in reviews if isinstance(item, dict)]
    if actual != required_ids:
        return [f"本节主体细节卡必须完整同序: expected={required_ids}, actual={actual}"]
    errors: list[str] = []
    for review in reviews:
        card_id = str(review.get("card_id"))
        planned = source.get(card_id, {})
        label = f"detail_card.{card_id}"
        if review.get("distinct_function_to_preserve") != planned.get("distinct_function_to_preserve"):
            errors.append(f"{label}.distinct_function_to_preserve 不得改写或省略")
        quotes = review.get("target_quotes")
        if review.get("status") != "passed":
            errors.append(f"{label}.status 必须为 passed")
        if not isinstance(quotes, list) or not quotes or any(not isinstance(q, str) or q not in section_text for q in quotes):
            errors.append(f"{label}.target_quotes 必须逐卡绑定当前节原句")
        for field in ("comparison", "manual_judgment"):
            if len(str(review.get(field) or "").strip()) < 20:
                errors.append(f"{label}.{field} 过短")
        if review.get("surface_copy_rejected") is not True:
            errors.append(f"{label}.surface_copy_rejected 必须为 true")
    return errors


def validate_emotion_semantics(emotion_review: dict[str, Any], item: dict[str, Any], section_text: str) -> list[str]:
    errors: list[str] = []
    emotion_items = emotion_review.get("emotion_beat_reviews")
    plot_items = emotion_review.get("plot_beat_reviews")
    if not isinstance(emotion_items, list):
        emotion_items = []
    if not isinstance(plot_items, list):
        plot_items = []
    expected_emotion = item.get("emotion_beat_contracts", [])
    expected_plot = item.get("plot_beat_contracts", [])
    if [entry.get("beat_id") for entry in emotion_items if isinstance(entry, dict)] != item.get("emotion_beat_ids"):
        errors.append("emotion_beat_reviews 必须按原序逐拍覆盖全部 E 拍")
    if [entry.get("beat_id") for entry in plot_items if isinstance(entry, dict)] != item.get("plot_beat_ids"):
        errors.append("plot_beat_reviews 必须按原序逐拍覆盖全部 P 拍")
    for source, review in zip(expected_emotion, emotion_items):
        beat_id = source.get("beat_id")
        if review.get("role") != source.get("role") or review.get("intensity") != source.get("intensity"):
            errors.append(f"{beat_id} role/intensity 必须与来源拍一致")
        for field in ("trigger", "relationship_position_change", "reader_effect", "judgment"):
            if len(str(review.get(field) or "").strip()) < 12:
                errors.append(f"{beat_id}.{field} 缺少具体语义裁决")
        quote = str(review.get("quote") or "")
        if not quote or quote not in section_text:
            errors.append(f"{beat_id}.quote 不在当前节")
        if review.get("semantic_parity_status") != "passed":
            errors.append(f"{beat_id}.semantic_parity_status 必须为 passed")
    for source, review in zip(expected_plot, plot_items):
        beat_id = source.get("beat_id")
        for field in ("action_parity", "external_change", "relationship_consequence", "judgment"):
            if len(str(review.get(field) or "").strip()) < 12:
                errors.append(f"{beat_id}.{field} 缺少具体语义裁决")
        quote = str(review.get("quote") or "")
        if not quote or quote not in section_text:
            errors.append(f"{beat_id}.quote 不在当前节")
        if review.get("semantic_parity_status") != "passed":
            errors.append(f"{beat_id}.semantic_parity_status 必须为 passed")
    return errors


def validate_scene_realization(review: dict[str, Any], item: dict[str, Any], section_text: str) -> list[str]:
    errors: list[str] = []
    if review.get("first_draft_mode") != "single_pass_scene_realization":
        errors.append("first_draft_mode 必须为 single_pass_scene_realization")
    if review.get("complete_before_target_write") is not True:
        errors.append("complete_before_target_write 必须为 true")
    if review.get("substantive_append_or_expansion_after_target_write") is not False:
        errors.append("substantive_append_or_expansion_after_target_write 必须为 false")
    scenes = review.get("scene_realization_reviews")
    if not isinstance(scenes, list) or not scenes:
        return errors + ["scene_realization_reviews 必须逐场证明事件已写成现场"]
    actual_e: list[str] = []
    actual_p: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        label = f"scene_realization_reviews[{index}]"
        if not isinstance(scene, dict):
            errors.append(f"{label} 必须是对象")
            continue
        actual_e.extend(str(value) for value in scene.get("emotion_beat_ids", []))
        actual_p.extend(str(value) for value in scene.get("plot_beat_ids", []))
        if scene.get("status") != "passed" or scene.get("summary_only") is not False or scene.get("scene_complete") is not True:
            errors.append(f"{label} 必须 passed，且 summary_only=false / scene_complete=true")
        quote_fields = ["entry_pressure_quote", "turning_action_quote", "visible_consequence_quote", "aftershock_quote"]
        bound_quotes: list[str] = []
        for field in quote_fields:
            quote = str(scene.get(field) or "")
            bound_quotes.append(quote)
            if not quote or quote not in section_text:
                errors.append(f"{label}.{field} 必须引用当前节真实原句")
        exchanges = scene.get("interaction_exchange_quotes")
        if not isinstance(exchanges, list) or len(exchanges) < 3 or any(
            not isinstance(quote, str) or quote not in section_text for quote in exchanges
        ):
            errors.append(f"{label}.interaction_exchange_quotes 至少需要 3 条当前节施压/接招/变化引句")
        else:
            bound_quotes.extend(exchanges)
        if len({quote for quote in bound_quotes if quote}) < 5:
            errors.append(f"{label} 不得用同一句反复冒充进场、交流、转折和余波")
        for field in ("reader_emotion_progression", "why_not_summary", "manual_judgment"):
            if len(str(scene.get(field) or "").strip()) < 24:
                errors.append(f"{label}.{field} 缺少具体成文裁决")
    if actual_e != item.get("emotion_beat_ids"):
        errors.append(f"场面验收 E 拍必须完整同序: expected={item.get('emotion_beat_ids')}, actual={actual_e}")
    if actual_p != item.get("plot_beat_ids"):
        errors.append(f"场面验收 P 拍必须完整同序: expected={item.get('plot_beat_ids')}, actual={actual_p}")
    emotion_review = review.get("emotion_review") or {}
    e_reviews = emotion_review.get("emotion_beat_reviews") or []
    p_reviews = emotion_review.get("plot_beat_reviews") or []
    if len(e_reviews) >= 3:
        semantic_rows = [
            (entry.get("trigger"), entry.get("relationship_position_change"), entry.get("reader_effect"))
            for entry in e_reviews if isinstance(entry, dict)
        ]
        if len(set(semantic_rows)) < max(2, len(semantic_rows) // 2):
            errors.append("E 拍语义裁决高度重复，疑似模板化批量填写")
    if len(p_reviews) >= 3:
        semantic_rows = [
            (entry.get("action_parity"), entry.get("external_change"), entry.get("relationship_consequence"))
            for entry in p_reviews if isinstance(entry, dict)
        ]
        if len(set(semantic_rows)) < max(2, len(semantic_rows) // 2):
            errors.append("P 拍语义裁决高度重复，疑似用通用套话冒充逐拍验收")
    return errors


def validate_delta_manual_review(
    review: dict[str, Any], item: dict[str, Any], section_text: str
) -> list[str]:
    errors: list[str] = []
    delta = review.get("delta_manual_review")
    if not isinstance(delta, dict):
        return ["差量逐节回执缺少 delta_manual_review"]
    if delta.get("review_mode") != "delta_manual_review":
        errors.append("delta_manual_review.review_mode 不正确")
    if delta.get("no_unlisted_deviations") is not True:
        errors.append("差量模式必须确认不存在未列明偏差")
    if len(str(delta.get("section_judgment") or "").strip()) < 32:
        errors.append("delta_manual_review.section_judgment 过短")

    scenes = delta.get("scene_reviews")
    planned_scenes = review.get("scene_realization_reviews") or []
    if not isinstance(scenes, list) or [
        row.get("scene_id") for row in scenes if isinstance(row, dict)
    ] != [row.get("scene_id") for row in planned_scenes if isinstance(row, dict)]:
        errors.append("差量场景复核必须完整同序覆盖写前 scene_units")
        scenes = []
    actual_e: list[str] = []
    actual_p: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        label = f"delta_manual_review.scene_reviews[{index}]"
        actual_e.extend(str(value) for value in scene.get("emotion_beat_ids") or [])
        actual_p.extend(str(value) for value in scene.get("plot_beat_ids") or [])
        bound: list[str] = []
        for field in (
            "entry_pressure_quote",
            "turning_action_quote",
            "visible_consequence_quote",
            "aftershock_quote",
        ):
            quote = str(scene.get(field) or "")
            bound.append(quote)
            if not quote or quote not in section_text:
                errors.append(f"{label}.{field} 必须来自当前节")
        exchanges = scene.get("interaction_exchange_quotes")
        if not isinstance(exchanges, list) or len(exchanges) < 3 or any(
            not isinstance(quote, str) or quote not in section_text for quote in exchanges
        ):
            errors.append(f"{label}.interaction_exchange_quotes 至少需要三条当前节证据")
        else:
            bound.extend(exchanges)
        if len({quote for quote in bound if quote}) < 5:
            errors.append(f"{label} 不得复用同一句冒充完整场景")
        for field in ("reader_emotion_progression", "why_not_summary", "manual_judgment"):
            if len(str(scene.get(field) or "").strip()) < 24:
                errors.append(f"{label}.{field} 过短")
    if actual_e != item.get("emotion_beat_ids"):
        errors.append("差量场景复核未完整同序领取全部 E 拍")
    if actual_p != item.get("plot_beat_ids"):
        errors.append("差量场景复核未完整同序领取全部 P 拍")

    characters = delta.get("character_reviews")
    if not isinstance(characters, list) or not characters:
        errors.append("差量模式必须逐人物复核不可互换性")
    else:
        for index, row in enumerate(characters, start=1):
            quotes = row.get("target_quotes")
            if not isinstance(quotes, list) or len(quotes) < 2 or any(
                not isinstance(quote, str) or quote not in section_text for quote in quotes
            ):
                errors.append(f"delta_manual_review.character_reviews[{index}] 至少需要两条当前节证据")
            if len(str(row.get("interchangeability_judgment") or "").strip()) < 20:
                errors.append(f"delta_manual_review.character_reviews[{index}] 人物裁决过短")
    if not extract_direct_dialogue(section_text) and any("「" in quote for quote in collect_quotes(delta)):
        errors.append("差量复核对白证据与正文直接对白不一致")
    return errors


def validate_deferred_section_review_bindings(
    review: dict[str, Any],
    state: dict[str, Any],
    item: dict[str, Any],
    staged_path: Path,
    state_path: Path,
) -> list[str]:
    errors: list[str] = []
    scaffold = review.get("review_scaffold") or {}
    if scaffold.get("review_mode") != "deferred_full_contract_review":
        return ["逐节回执不是 deferred_full_contract_review"]
    deferred = scaffold.get("deferred_semantic_review")
    if not isinstance(deferred, dict):
        return ["逐节回执缺少 deferred_semantic_review"]
    if deferred.get("prewrite_contracts_remain_source_of_truth") is not True:
        errors.append("延后模式必须保持写前合同为语义真源")
    if deferred.get("per_section_manual_sidecar_required") is not False:
        errors.append("延后模式不得要求逐节人工侧车")
    if deferred.get("fallback_on_detected_deviation") != "delta_or_full_manual_sidecar":
        errors.append("延后模式缺少偏差回退路径")
    if review.get("final_status") != "deferred_to_final_contracts":
        errors.append("延后模式 final_status 不正确")
    bindings = deferred.get("bindings") or {}
    if bindings.get("state_sha256") != sha256_file(state_path):
        errors.append("延后回执绑定的状态 SHA 已失效")
    if bindings.get("staged_sha256") != sha256_file(staged_path):
        errors.append("延后回执绑定的暂存稿 SHA 已失效")
    prose_path = Path(str((state.get("paths") or {}).get("prose_receipt") or ""))
    emotion_path = Path(str((state.get("paths") or {}).get("emotion_receipt") or ""))
    if not prose_path.is_file() or bindings.get("prose_receipt_sha256") != sha256_file(prose_path):
        errors.append("延后回执绑定的写前文字合同已失效")
    if not emotion_path.is_file() or bindings.get("emotion_receipt_sha256") != sha256_file(emotion_path):
        errors.append("延后回执绑定的写前情绪合同已失效")
    emotion_review = review.get("emotion_review") or {}
    if emotion_review.get("emotion_beat_ids") != item.get("emotion_beat_ids"):
        errors.append("延后回执 E 拍领取与当前状态不一致")
    if emotion_review.get("plot_beat_ids") != item.get("plot_beat_ids"):
        errors.append("延后回执 P 拍领取与当前状态不一致")
    scenes = review.get("scene_realization_reviews") or []
    actual_e = [
        str(beat_id)
        for scene in scenes
        if isinstance(scene, dict)
        for beat_id in (scene.get("emotion_beat_ids") or [])
    ]
    actual_p = [
        str(beat_id)
        for scene in scenes
        if isinstance(scene, dict)
        for beat_id in (scene.get("plot_beat_ids") or [])
    ]
    if actual_e != item.get("emotion_beat_ids"):
        errors.append("延后回执场景未完整同序领取全部 E 拍")
    if actual_p != item.get("plot_beat_ids"):
        errors.append("延后回执场景未完整同序领取全部 P 拍")
    return errors


def finish_section_commit(
    *,
    state_path: Path,
    state: dict[str, Any],
    state_item: dict[str, Any],
    draft_path: Path,
    draft_text: str,
    staged_mode: bool,
    sid: str,
    section_text: str,
    review_path: Path,
    count: int,
) -> int:
    if staged_mode:
        existing = draft_text.rstrip()
        separator = "\n\n" if existing else ""
        committed = f"{existing}{separator}{sid}.\n\n{section_text}\n"
        draft_path.write_text(committed, encoding="utf-8")
    state_item["status"] = "passed"
    state_item["validated_at"] = now_iso()
    state_item["review_path"] = str(review_path)
    state_item["review_sha256"] = sha256_file(review_path)
    state_item["text_sha256"] = sha256_text(section_text)
    state_item["char_count"] = count
    expected_sections = state["expected_sections"]
    if sid == expected_sections[-1]:
        state["current_section"] = ""
        state["status"] = "sections_passed"
    else:
        state["current_section"] = str(int(sid) + 1)
        state["status"] = "in_progress"
    state["updated_at"] = now_iso()
    write_json(state_path, state)
    print(f"section_progress_gate: section_passed ({sid})")
    print(f"char_count: {count}")
    if state["current_section"]:
        print(f"next_section: {state['current_section']}")
    else:
        print("next_step: finalize")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    review_path = Path(args.review).resolve()
    staged_path = Path(args.staged).resolve() if getattr(args, "staged", None) else None
    sidecar_path = (
        Path(args.sidecar).resolve()
        if getattr(args, "sidecar", None)
        else None
    )
    if sidecar_path is not None:
        if staged_path is None:
            return fail("commit-section", ["使用 --sidecar 时必须同时传 --staged"])
        try:
            apply_section_review_sidecar(review_path, staged_path, sidecar_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return fail("commit-section", [f"逐节人工侧车合并失败: {exc}"])
    if staged_path is not None and review_path.is_file() and staged_path.is_file():
        current_review = load_json(review_path)
        manual_review_mode = (
            ((current_review.get("review_scaffold") or {}).get("manual_sidecar") or {}).get("review_mode")
        )
        scaffold_review_mode = (current_review.get("review_scaffold") or {}).get("review_mode")
        if (
            manual_review_mode != "delta_manual_review"
            and scaffold_review_mode != "deferred_full_contract_review"
        ):
            normalization_errors = apply_section_review_mechanical_normalization(
                review_path, staged_path
            )
            if normalization_errors:
                return fail("commit-section", normalization_errors)
    try:
        state = load_json(state_path)
        review = load_json(review_path)
        prose_contract = load_json(Path(state["paths"]["prose_receipt"]))
        emotion_contract = load_json(Path(state["paths"]["emotion_receipt"]))
    except ValueError as exc:
        return fail("validate-section", [str(exc)])
    sid = str(args.section)
    errors = verify_source_bindings(state)
    if str(state.get("current_section")) != sid:
        errors.append(f"只能验收当前第 {state.get('current_section')} 节")
    try:
        state_item = get_section_state(state, sid)
        item = hydrate_section_beat_contracts(
            state_item,
            emotion_contract,
            sid,
        )
    except ValueError as exc:
        return fail("validate-section", [str(exc)])
    if item.get("status") != "writing":
        errors.append(f"第 {sid} 节必须先 start-section，实际状态为 {item.get('status')}")
    staged_mode = bool(getattr(args, "staged", None))
    draft_path = Path(state["paths"]["draft"])
    draft_text, draft_errors = load_committed_draft(draft_path, staged_mode)
    errors.extend(draft_errors)
    _, sections, order = split_sections(draft_text)
    expected_order = [str(index) for index in range(1, int(sid) + (0 if staged_mode else 1))]
    if order != expected_order:
        errors.append(f"验收第 {sid} 节时正文必须且只能包含 {expected_order}，实际为 {order}")
    if staged_mode:
        staged_path = Path(args.staged).resolve()
        if not staged_path.is_file():
            errors.append(f"暂存稿不存在: {staged_path}")
            section_text = ""
        else:
            section_text = staged_path.read_text(encoding="utf-8").strip()
            if SECTION_RE.search(section_text):
                errors.append("暂存稿只允许当前节正文，不得包含数字小节标题")
        plan_path = Path(str(item.get("first_draft_plan_path") or ""))
        if not plan_path.is_file() or sha256_file(plan_path) != item.get("first_draft_plan_sha256"):
            errors.append("当前节场面计划缺失或已变化，必须重新 start-section")
    else:
        section_text = sections.get(sid, "")
    count = non_whitespace_chars(section_text)
    minimum = int(item.get("min_chars", 0))
    maximum = int(item.get("max_chars", 0))
    tolerated_minimum, tolerated_maximum = tolerated_char_range(minimum, maximum)
    if not char_count_within_tolerance(count, minimum, maximum):
        errors.append(
            f"第 {sid} 节字数 {count} 超出预算 {minimum}-{maximum} 的上下 20% 容差范围 "
            f"{tolerated_minimum}-{tolerated_maximum}"
        )
    for previous_sid, expected_hash in item.get("prior_section_hashes", {}).items():
        if sha256_text(sections.get(previous_sid, "")) != expected_hash:
            errors.append(f"写第 {sid} 节时修改了已通过的第 {previous_sid} 节")
    if str(review.get("section_id")) != sid:
        errors.append("逐节回执 section_id 与当前节不一致")
    scaffold = review.get("review_scaffold")
    if not isinstance(scaffold, dict):
        errors.append("逐节回执必须由官方 init_section_review.py 初始化")
        scaffold = {}
    else:
        if scaffold.get("generator") != "story-short-write/init_section_review.py":
            errors.append("review_scaffold.generator 不是官方初始化器")
        if scaffold.get("semantic_fields_initialized_pending") is not True:
            errors.append("review_scaffold 必须证明语义字段从 pending 骨架开始")
        if scaffold.get("state_sha256") != sha256_file(state_path):
            errors.append("review_scaffold 未绑定当前 start-section 状态 SHA")
    if scaffold.get("review_mode") == "deferred_full_contract_review":
        errors.extend(
            validate_deferred_section_review_bindings(
                review, state, item, staged_path, state_path
            )
        )
        if errors:
            return fail("commit-section" if staged_mode else "validate-section", errors)
        return finish_section_commit(
            state_path=state_path,
            state=state,
            state_item=state_item,
            draft_path=draft_path,
            draft_text=draft_text,
            staged_mode=staged_mode,
            sid=sid,
            section_text=section_text,
            review_path=review_path,
            count=count,
        )
    constraints = review.get("positive_generation_constraints")
    if not isinstance(constraints, list) or not 5 <= len(constraints) <= 9 or not all(isinstance(x, str) and x.strip() for x in constraints):
        errors.append("positive_generation_constraints 必须包含 5-9 条非空正向首写约束")
    if review.get("reviewed_current_section_only") is not True:
        errors.append("reviewed_current_section_only 必须为 true")
    if review.get("semantic_review_method") != "current_model_manual":
        errors.append("semantic_review_method 必须为 current_model_manual")
    if review.get("automation_used_for_semantic_judgment") is not False:
        errors.append("automation_used_for_semantic_judgment 必须为 false")
    if isinstance(scaffold, dict):
        sidecar = scaffold.get("manual_sidecar")
        if not isinstance(sidecar, dict):
            errors.append("逐节回执必须先通过官方 manage_section_review.py 人工侧车合并")
        else:
            if sidecar.get("manager") != "story-short-write/manage_section_review.py":
                errors.append("review_scaffold.manual_sidecar.manager 不是官方侧车入口")
            if sidecar.get("semantic_fields_generated_by_script") is not False:
                errors.append("人工侧车不得由脚本生成语义字段")
            if staged_path is not None and sidecar.get("staged_sha256") != sha256_file(staged_path):
                errors.append("人工侧车未绑定当前暂存稿 SHA")
    provenance = review.get("manual_review_provenance")
    if not isinstance(provenance, dict):
        errors.append("缺少 manual_review_provenance，不能证明当前模型逐字段复核")
    else:
        if provenance.get("performed_by_current_model") is not True or provenance.get("full_section_read_by_current_model") is not True:
            errors.append("manual_review_provenance 必须确认当前模型完整读取本节")
        if provenance.get("semantic_fields_generated_by_script") is not False:
            errors.append("semantic_fields_generated_by_script 必须为 false")
        if provenance.get("project_scripts_used_for_semantic_population") != []:
            errors.append("禁止项目脚本批量生成逐节语义字段")
        if len(str(provenance.get("manual_judgment") or "").strip()) < 24:
            errors.append("manual_review_provenance.manual_judgment 过短")
    prose_review = review.get("prose_review")
    emotion_review = review.get("emotion_review")
    if not isinstance(prose_review, dict) or prose_review.get("status") != "passed":
        errors.append("prose_review.status 必须为 passed")
    if not isinstance(emotion_review, dict) or emotion_review.get("status") != "passed":
        errors.append("emotion_review.status 必须为 passed")
    actual_e = emotion_review.get("emotion_beat_ids") if isinstance(emotion_review, dict) else None
    actual_p = emotion_review.get("plot_beat_ids") if isinstance(emotion_review, dict) else None
    if actual_e != item.get("emotion_beat_ids"):
        errors.append(f"E 拍必须完整同序: expected={item.get('emotion_beat_ids')}, actual={actual_e}")
    if actual_p != item.get("plot_beat_ids"):
        errors.append(f"P 拍必须完整同序: expected={item.get('plot_beat_ids')}, actual={actual_p}")
    sidecar_mode = (
        ((scaffold or {}).get("manual_sidecar") or {}).get("review_mode")
        if isinstance(scaffold, dict)
        else None
    )
    if sidecar_mode == "delta_manual_review":
        errors.extend(validate_delta_manual_review(review, item, section_text))
        if review.get("final_status") != "passed":
            errors.append("final_status 必须为 passed")
        if errors:
            return fail("commit-section" if staged_mode else "validate-section", errors)
        return finish_section_commit(
            state_path=state_path,
            state=state,
            state_item=state_item,
            draft_path=draft_path,
            draft_text=draft_text,
            staged_mode=staged_mode,
            sid=sid,
            section_text=section_text,
            review_path=review_path,
            count=count,
        )
    mappings = prose_review.get("sentence_mappings") if isinstance(prose_review, dict) else None
    if not isinstance(mappings, list) or len(mappings) < 4:
        errors.append("prose_review.sentence_mappings 至少需要 4 条")
    else:
        for index, mapping in enumerate(mappings, start=1):
            label = f"sentence_mappings[{index}]"
            if not isinstance(mapping, dict):
                errors.append(f"{label} 必须是对象")
                continue
            target_sentence = str(mapping.get("target_sentence") or "")
            source_sentence = str(mapping.get("source_anchor_sentence") or "")
            target_surface = str(mapping.get("target_surface_evidence") or "")
            source_surface = str(mapping.get("source_surface_evidence") or "")
            if not target_sentence or target_sentence not in section_text:
                errors.append(f"{label}.target_sentence 不在当前节")
            if not source_sentence:
                errors.append(f"{label}.source_anchor_sentence 不能为空")
            if not target_surface or target_surface not in target_sentence:
                errors.append(f"{label}.target_surface_evidence 未绑定当前目标句")
            if not source_surface or source_surface not in source_sentence:
                errors.append(f"{label}.source_surface_evidence 未绑定来源锚句")
            feature_ids = mapping.get("feature_ids")
            if not isinstance(feature_ids, list) or len(feature_ids) < 2:
                errors.append(f"{label}.feature_ids 至少需要 2 项真实来源特征")
            if len(str(mapping.get("language_mechanism_match") or "").strip()) < 20:
                errors.append(f"{label}.language_mechanism_match 过短")
            if mapping.get("contract_used_during_writing") is not True:
                errors.append(f"{label}.contract_used_during_writing 必须为 true")

    plan = next(
        (
            entry
            for entry in prose_contract.get("section_generation_plans", [])
            if isinstance(entry, dict) and str(entry.get("section_id")) == sid
        ),
        {},
    )
    require_review_group(
        prose_review, "continuous_chain_reviews", len(plan.get("continuous_source_chain_packets", [])), section_text, errors
    )
    require_review_group(
        prose_review, "dialogue_voice_reviews", len(plan.get("dialogue_voice_packets", [])), section_text, errors
    )
    require_review_group(
        prose_review, "relation_micro_reviews", len(plan.get("relation_micro_examples", [])), section_text, errors
    )
    errors.extend(validate_sf_reviews(prose_contract, prose_review, item.get("required_sf_ids", []), section_text))
    errors.extend(validate_detail_reviews(prose_contract, prose_review, item.get("required_detail_card_ids", []), section_text))

    liveliness = prose_review.get("liveliness_review") if isinstance(prose_review, dict) else None
    live_sentences = liveliness.get("target_live_sentences") if isinstance(liveliness, dict) else None
    if not isinstance(live_sentences, list) or len(live_sentences) < 3 or any(
        not isinstance(sentence, str) or sentence not in section_text for sentence in live_sentences
    ):
        errors.append("liveliness_review.target_live_sentences 至少需要 3 条当前节活句")

    character_review = prose_review.get("character_vitality_review") if isinstance(prose_review, dict) else None
    character_items = character_review.get("character_reviews") if isinstance(character_review, dict) else None
    expected_characters = [
        entry.get("character_name")
        for entry in (plan.get("character_plan") or {}).get("participants", [])
        if isinstance(entry, dict)
    ]
    actual_characters = [entry.get("character_name") for entry in character_items or [] if isinstance(entry, dict)]
    if actual_characters != expected_characters:
        errors.append(f"character_reviews 必须覆盖本节全部人物: expected={expected_characters}, actual={actual_characters}")
    else:
        for entry in character_items:
            target_quotes = entry.get("target_quotes")
            ownership = entry.get("evidence_ownership_reviews")
            if not isinstance(target_quotes, list) or len(target_quotes) < 2 or any(
                not isinstance(quote, str) or quote not in section_text for quote in target_quotes
            ):
                errors.append(f"{entry.get('character_name')} 至少需要 2 条当前节人物证据")
            if not isinstance(ownership, list) or len(ownership) != len(target_quotes or []):
                errors.append(f"{entry.get('character_name')} 人物证据归属复核不完整")
            if len(str(entry.get("interchangeability_judgment") or "").strip()) < 20:
                errors.append(f"{entry.get('character_name')} interchangeability_judgment 过短")

    dialogue_grounding = prose_review.get("dialogue_grounding_review") if isinstance(prose_review, dict) else None
    full_dialogue = dialogue_grounding.get("full_dialogue_reviews") if isinstance(dialogue_grounding, dict) else None
    actual_dialogue = extract_direct_dialogue(section_text)
    reviewed_dialogue = [entry.get("quote") for entry in full_dialogue or [] if isinstance(entry, dict)]
    if reviewed_dialogue != actual_dialogue:
        errors.append("full_dialogue_reviews 必须按正文顺序逐字覆盖全部直接对白")
    else:
        for index, entry in enumerate(full_dialogue, start=1):
            speaker = str(entry.get("speaker") or "").strip()
            if len(speaker) < 2:
                errors.append(f"full_dialogue_reviews[{index}].speaker 过短")
            for field in ("scene_pressure", "turn_connection", "interchangeability_judgment"):
                if len(str(entry.get(field) or "").strip()) < 4:
                    errors.append(f"full_dialogue_reviews[{index}].{field} 过短")
            if entry.get("decision") != "keep":
                errors.append(f"full_dialogue_reviews[{index}].decision 必须为 keep")

    if isinstance(emotion_review, dict):
        errors.extend(validate_emotion_semantics(emotion_review, item, section_text))
    errors.extend(validate_scene_realization(review, item, section_text))
    quotes = collect_quotes({"prose_review": prose_review, "emotion_review": emotion_review})
    if len(quotes) < 4:
        errors.append("逐节回执至少需要 4 条真实正文引句")
    for quote in quotes:
        if quote not in section_text:
            errors.append(f"回执引句不在当前第 {sid} 节正文中: {quote[:60]}")
    if review.get("final_status") != "passed":
        errors.append("final_status 必须为 passed；存在待改项时只能先修当前节")
    if errors:
        return fail("commit-section" if staged_mode else "validate-section", errors)
    return finish_section_commit(
        state_path=state_path,
        state=state,
        state_item=state_item,
        draft_path=draft_path,
        draft_text=draft_text,
        staged_mode=staged_mode,
        sid=sid,
        section_text=section_text,
        review_path=review_path,
        count=count,
    )


def command_recover_half_commit(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    staged_path = Path(args.staged).resolve()
    review_path = Path(args.review).resolve()
    sid = str(args.section)
    try:
        state = load_json(state_path)
        review = load_json(review_path)
        state_item = get_section_state(state, sid)
        emotion_contract = load_json(Path(state["paths"]["emotion_receipt"]))
        item = hydrate_section_beat_contracts(state_item, emotion_contract, sid)
    except ValueError as exc:
        return fail("recover-half-commit", [str(exc)])

    errors = verify_source_bindings(state)
    section_text = staged_path.read_text(encoding="utf-8").strip() if staged_path.is_file() else ""
    if item.get("status") != "writing":
        errors.append(f"第 {sid} 节必须仍为 writing，实际为 {item.get('status')}")
    if not staged_path.is_file():
        errors.append(f"暂存稿不存在: {staged_path}")
    draft_path = Path(state["paths"]["draft"])
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    _, sections, order = split_sections(draft_text)
    expected_order = [str(index) for index in range(1, int(sid) + 1)]
    if order != expected_order:
        errors.append(f"正文必须恰好包含 {expected_order}，实际为 {order}")
    if sections.get(sid, "") != section_text:
        errors.append("正文当前节与暂存稿不一致")
    expected_current = "" if sid == state["expected_sections"][-1] else str(int(sid) + 1)
    if str(state.get("current_section") or "") not in {sid, expected_current}:
        errors.append("current_section 既不是当前节也不是下一节")
    scaffold = review.get("review_scaffold")
    review_mode = scaffold.get("review_mode") if isinstance(scaffold, dict) else ""
    if str(review.get("section_id")) != sid:
        errors.append("正式逐节回执 section_id 不一致")
    if review_mode == "deferred_full_contract_review":
        errors.extend(
            validate_deferred_section_review_bindings(
                review, state, item, staged_path, state_path
            )
        )
    else:
        sidecar = scaffold.get("manual_sidecar") if isinstance(scaffold, dict) else None
        if review.get("final_status") != "passed":
            errors.append("人工侧车模式的正式逐节回执未通过")
        if not isinstance(sidecar, dict) or sidecar.get("staged_sha256") != sha256_file(staged_path):
            errors.append("人工侧车模式未绑定当前暂存稿 SHA")
        if not isinstance(scaffold, dict) or scaffold.get("mechanical_normalization_applied") is not True:
            errors.append("人工侧车模式未完成机械归一化")
    count = non_whitespace_chars(section_text)
    if not char_count_within_tolerance(count, int(item.get("min_chars", 0)), int(item.get("max_chars", 0))):
        errors.append(f"第 {sid} 节字数 {count} 不在允许范围")
    for previous_sid, expected_hash in item.get("prior_section_hashes", {}).items():
        if sha256_text(sections.get(previous_sid, "")) != expected_hash:
            errors.append(f"已通过的第 {previous_sid} 节 SHA 已变化")
    if errors:
        return fail("recover-half-commit", errors)

    state_item["status"] = "passed"
    state_item["validated_at"] = now_iso()
    state_item["review_path"] = str(review_path)
    state_item["review_sha256"] = sha256_file(review_path)
    state_item["text_sha256"] = sha256_text(section_text)
    state_item["char_count"] = count
    state["current_section"] = expected_current
    state["status"] = "sections_passed" if not expected_current else "in_progress"
    state["updated_at"] = now_iso()
    write_json(state_path, state)
    print(f"section_progress_gate: half_commit_recovered ({sid})")
    print(f"char_count: {count}")
    print(f"next_section: {expected_current}" if expected_current else "next_step: finalize")
    return 0


def command_reopen(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    try:
        state = load_json(state_path)
    except ValueError as exc:
        return fail("reopen-section", [str(exc)])
    sid = str(args.section)
    errors = verify_source_bindings(state)
    try:
        item = get_section_state(state, sid)
    except ValueError as exc:
        return fail("reopen-section", [str(exc)])
    passed_ids = [str(entry.get("section_id")) for entry in state.get("sections", []) if entry.get("status") == "passed"]
    if item.get("status") != "passed" or not passed_ids or passed_ids[-1] != sid:
        errors.append("只能重开最后一个已通过小节")
    for entry in state.get("sections", []):
        if int(str(entry.get("section_id"))) > int(sid) and entry.get("status") != "pending":
            errors.append(f"第 {entry.get('section_id')} 节已经启动，禁止回开第 {sid} 节")
    draft_path = Path(state["paths"]["draft"])
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    _, sections, order = split_sections(draft_text)
    expected_order = [str(index) for index in range(1, int(sid) + 1)]
    if order != expected_order:
        errors.append(f"重开第 {sid} 节前正文只能包含 {expected_order}，实际为 {order}")
    for previous_sid in expected_order[:-1]:
        previous = get_section_state(state, previous_sid)
        if previous.get("status") != "passed" or sha256_text(sections.get(previous_sid, "")) != previous.get("text_sha256"):
            errors.append(f"更早的第 {previous_sid} 节状态或正文 SHA 已变化")
    if errors:
        return fail("reopen-section", errors)
    item["status"] = "writing"
    item["reopened_at"] = now_iso()
    item["prior_section_hashes"] = {
        previous_sid: sha256_text(sections[previous_sid]) for previous_sid in expected_order[:-1]
    }
    item["review_path"] = ""
    item["review_sha256"] = ""
    item["text_sha256"] = ""
    item["char_count"] = 0
    state["current_section"] = sid
    state["status"] = "in_progress"
    state.pop("final_draft_sha256", None)
    state.pop("final_char_count", None)
    state["updated_at"] = now_iso()
    write_json(state_path, state)
    print(f"section_progress_gate: section_reopened ({sid})")
    print("previous review and text SHA invalidated; rewrite and validate this section before advancing")
    return 0


def command_discard_writing(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    try:
        state = load_json(state_path)
    except ValueError as exc:
        return fail("discard-writing-section", [str(exc)])
    sid = str(args.section)
    errors = verify_source_bindings(state)
    if str(state.get("current_section")) != sid:
        errors.append(f"只能废弃当前第 {state.get('current_section')} 节")
    try:
        item = get_section_state(state, sid)
    except ValueError as exc:
        errors.append(str(exc))
        item = {}
    if item.get("status") != "writing":
        errors.append(f"第 {sid} 节必须是 writing，实际为 {item.get('status')}")
    draft_path = Path(state["paths"]["draft"])
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    prefix, sections, order = split_sections(draft_text)
    prior = [str(index) for index in range(1, int(sid))]
    if order not in (prior, prior + [sid]):
        errors.append(f"当前节只能尚未写入正文或是最后一个误写节，实际小节顺序为 {order}")
    if errors:
        return fail("discard-writing-section", errors)
    archive_path: Path | None = None
    if order == prior + [sid]:
        archive_dir = draft_path.parent / "写作资产" / "失败试稿"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"第{sid}节_旧流程短稿_待重写.md"
        archive_path.write_text(f"{sid}.\n\n{sections[sid]}\n", encoding="utf-8")
        prior_text = prefix.rstrip()
        for previous_sid in prior:
            prior_text += f"\n\n{previous_sid}.\n\n{sections[previous_sid]}"
        draft_path.write_text(prior_text.rstrip() + "\n", encoding="utf-8")
    item["status"] = "pending"
    for key in ("started_at", "prior_section_hashes", "first_draft_plan_path", "first_draft_plan_sha256"):
        item.pop(key, None)
    item["char_count"] = 0
    item.pop("review_path", None)
    item.pop("review_sha256", None)
    item.pop("text_sha256", None)
    state["current_section"] = sid
    state["status"] = "in_progress"
    state["updated_at"] = now_iso()
    state["last_discarded_section"] = {
        "section_id": sid,
        "archive_path": str(archive_path) if archive_path else "",
    }
    write_json(state_path, state)
    print(f"section_progress_gate: writing_section_discarded ({sid})")
    if archive_path:
        print(f"archive: {archive_path}")
    else:
        print("no committed section text found; cleared orphan writing state")
    print("next_step: create a scene plan, then start-section with --plan")
    return 0


def command_sync_pending(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    try:
        state = load_json(state_path)
        outline_path = Path(state["paths"]["outline"])
        prose_path = Path(state["paths"]["prose_receipt"])
        emotion_path = Path(state["paths"]["emotion_receipt"])
        outline_ids = OUTLINE_SECTION_RE.findall(outline_path.read_text(encoding="utf-8"))
        expected = state.get("expected_sections", [])
        if outline_ids != expected:
            raise ValueError(f"新大纲数字小节与状态不一致: {outline_ids}")
        prose = load_json(prose_path)
        emotion = load_json(emotion_path)
        generation_ids = [
            str(entry.get("section_id"))
            for entry in prose.get("section_generation_plans", [])
            if isinstance(entry, dict)
        ]
        if generation_ids != expected:
            raise ValueError("新文字合同 section_generation_plans 与状态小节不一致")
        sf_assignments, sf_errors = validate_sf_assignments(prose, expected)
        if sf_errors:
            raise ValueError("；".join(sf_errors))
        beat_assignments = expected_ids(emotion)
        if list(beat_assignments) != expected:
            raise ValueError("新情绪合同小节与状态不一致")
    except (OSError, ValueError) as exc:
        return fail("sync-pending-contracts", [str(exc)])
    draft_path = Path(state["paths"]["draft"])
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    _, sections, order = split_sections(draft_text)
    passed_ids = [
        str(entry.get("section_id")) for entry in state.get("sections", []) if entry.get("status") == "passed"
    ]
    errors: list[str] = []
    if order != passed_ids:
        errors.append(f"同步未写合同前正文只能包含已通过小节 {passed_ids}，实际为 {order}")
    for entry in state.get("sections", []):
        sid = str(entry.get("section_id"))
        new_contract = beat_assignments[sid]
        if entry.get("status") == "passed":
            if entry.get("emotion_beat_ids") != new_contract["emotion_beat_ids"]:
                errors.append(f"已通过第 {sid} 节 E 拍发生变化，禁止同步")
            if entry.get("plot_beat_ids") != new_contract["plot_beat_ids"]:
                errors.append(f"已通过第 {sid} 节 P 拍发生变化，禁止同步")
            if entry.get("required_sf_ids") != sf_assignments[sid]:
                errors.append(f"已通过第 {sid} 节 SF 分配发生变化，禁止同步")
            if sha256_text(sections.get(sid, "")) != entry.get("text_sha256"):
                errors.append(f"已通过第 {sid} 节正文 SHA 发生变化")
        elif entry.get("status") not in ("pending", "writing"):
            errors.append(f"第 {sid} 节状态 {entry.get('status')} 不能同步")
        elif entry.get("status") == "writing" and sid in sections:
            errors.append(f"第 {sid} 节已经落字，必须先完成或归档，不能同步合同")
    if errors:
        return fail("sync-pending-contracts", errors)
    for entry in state.get("sections", []):
        sid = str(entry.get("section_id"))
        if entry.get("status") == "passed":
            continue
        entry.update(beat_assignments[sid])
        entry["required_sf_ids"] = sf_assignments[sid]
        entry["status"] = "pending"
        entry.pop("started_at", None)
        entry.pop("prior_section_hashes", None)
    first_pending = next(
        (str(entry.get("section_id")) for entry in state.get("sections", []) if entry.get("status") == "pending"), ""
    )
    state["current_section"] = first_pending
    state["status"] = "in_progress" if first_pending else "sections_passed"
    state["source_bindings"]["outline_sha256"] = sha256_file(outline_path)
    state["source_bindings"]["prose_receipt_sha256"] = sha256_file(prose_path)
    state["source_bindings"]["emotion_receipt_sha256"] = sha256_file(emotion_path)
    state["updated_at"] = now_iso()
    write_json(state_path, state)
    print("section_progress_gate: pending_contracts_synced")
    print(f"preserved_passed_sections: {','.join(passed_ids) or 'none'}")
    print(f"current_section: {first_pending or 'none'}")
    return 0


def command_finalize(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    try:
        state = load_json(state_path)
    except ValueError as exc:
        return fail("finalize", [str(exc)])
    errors = verify_source_bindings(state)
    if state.get("status") != "sections_passed":
        errors.append(f"所有小节尚未逐节通过: status={state.get('status')}")
    draft_path = Path(state["paths"]["draft"])
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    _, sections, order = split_sections(draft_text)
    if order != state.get("expected_sections"):
        errors.append(f"正文小节不完整或顺序错误: {order}")
    for item in state.get("sections", []):
        sid = str(item.get("section_id"))
        if item.get("status") != "passed":
            errors.append(f"第 {sid} 节未 passed")
            continue
        if sha256_text(sections.get(sid, "")) != item.get("text_sha256"):
            errors.append(f"第 {sid} 节通过后又被修改")
        review_path = Path(str(item.get("review_path") or ""))
        if not review_path.is_file() or sha256_file(review_path) != item.get("review_sha256"):
            errors.append(f"第 {sid} 节逐节回执缺失或已变化")
    total = non_whitespace_chars(draft_text)
    budget = state.get("total_budget", {})
    minimum = int(budget.get("min_chars", 0))
    maximum = int(budget.get("max_chars", 0))
    tolerated_minimum, tolerated_maximum = tolerated_char_range(minimum, maximum)
    if not char_count_within_tolerance(total, minimum, maximum):
        errors.append(
            f"全文字数 {total} 超出预算 {minimum}-{maximum} 的上下 20% 容差范围 "
            f"{tolerated_minimum}-{tolerated_maximum}"
        )
    if errors:
        return fail("finalize", errors)
    state["status"] = "final_ready"
    state["final_draft_sha256"] = sha256_file(draft_path)
    state["final_char_count"] = total
    state["updated_at"] = now_iso()
    write_json(state_path, state)
    print("section_progress_gate: final_ready")
    print(f"draft_sha256: {state['final_draft_sha256']}")
    print(f"char_count: {total}")
    print("next_step: bind full-draft contracts and merge the already validated section reviews")
    return 0


def command_status(args: argparse.Namespace) -> int:
    try:
        state = load_json(Path(args.state).resolve())
    except ValueError as exc:
        return fail("status", [str(exc)])
    integrity_errors = verify_source_bindings(state) + verify_committed_draft_integrity(state)
    if integrity_errors:
        return fail("status", integrity_errors)
    print(f"section_progress_gate: {state.get('status')}")
    print(f"current_section: {state.get('current_section') or 'none'}")
    for item in state.get("sections", []):
        print(f"- {item.get('section_id')}: {item.get('status')} ({item.get('char_count', 0)} chars)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--state", required=True)
    init_parser.add_argument("--outline", required=True)
    init_parser.add_argument("--draft", required=True)
    init_parser.add_argument("--prose-receipt", required=True)
    init_parser.add_argument("--emotion-receipt", required=True)
    init_parser.add_argument("--budget", required=True)

    start_parser = subparsers.add_parser("start-section")
    start_parser.add_argument("--state", required=True)
    start_parser.add_argument("--section", required=True, type=int)
    start_parser.add_argument("--plan", required=True)
    start_parser.add_argument("--context-output")

    validate_parser = subparsers.add_parser("validate-section")
    validate_parser.add_argument("--state", required=True)
    validate_parser.add_argument("--section", required=True, type=int)
    validate_parser.add_argument("--review", required=True)

    commit_parser = subparsers.add_parser("commit-section")
    commit_parser.add_argument("--state", required=True)
    commit_parser.add_argument("--section", required=True, type=int)
    commit_parser.add_argument("--staged", required=True)
    commit_parser.add_argument("--review", required=True)
    commit_parser.add_argument("--sidecar")

    recover_parser = subparsers.add_parser("recover-half-commit")
    recover_parser.add_argument("--state", required=True)
    recover_parser.add_argument("--section", required=True, type=int)
    recover_parser.add_argument("--staged", required=True)
    recover_parser.add_argument("--review", required=True)

    reopen_parser = subparsers.add_parser("reopen-section")
    reopen_parser.add_argument("--state", required=True)
    reopen_parser.add_argument("--section", required=True, type=int)

    discard_parser = subparsers.add_parser("discard-writing-section")
    discard_parser.add_argument("--state", required=True)
    discard_parser.add_argument("--section", required=True, type=int)

    sync_parser = subparsers.add_parser("sync-pending-contracts")
    sync_parser.add_argument("--state", required=True)

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--state", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--state", required=True)

    args = parser.parse_args()
    if args.command == "init":
        return command_init(args)
    if args.command == "start-section":
        return command_start(args)
    if args.command == "validate-section":
        return fail("validate-section", ["validate-section 已废弃：当前节必须在独立暂存稿中完成并使用 commit-section 原子写入"])
    if args.command == "commit-section":
        return command_validate(args)
    if args.command == "recover-half-commit":
        return command_recover_half_commit(args)
    if args.command == "reopen-section":
        return command_reopen(args)
    if args.command == "discard-writing-section":
        return command_discard_writing(args)
    if args.command == "sync-pending-contracts":
        return command_sync_pending(args)
    if args.command == "finalize":
        return command_finalize(args)
    return command_status(args)


if __name__ == "__main__":
    sys.exit(main())
