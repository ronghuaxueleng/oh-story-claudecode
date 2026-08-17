#!/usr/bin/env python3
"""Validate the human-authored E/P semantic mapping before contract assembly."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


E_FIELDS = (
    "source_beat_id", "target_beat_id", "role", "intensity", "target_outline_region",
    "trigger", "relationship_position_change", "reader_effect", "target_story_adaptation",
    "hurt_object", "expectation_before", "expectation_after", "action_impulse_before",
    "action_impulse_after", "equivalence_reason", "target_evidence_coverage_review", "evidence",
)
P_FIELDS = (
    "source_path", "source_beat_id", "target_beat_id",
    "source_actor", "source_object_or_receiver", "source_pressure_or_trigger",
    "source_action", "source_control_change", "source_information_change",
    "source_consequence", "actor", "actor_evidence",
    "object_or_receiver", "pressure_or_trigger", "action", "control_change",
    "information_change", "consequence", "adaptation_equivalence",
    "action_equivalence_review", "control_change_equivalence_review",
    "information_change_equivalence_review", "consequence_equivalence_review",
    "independent_beat_judgment", "evidence",
)
P_SOURCE_FIELD_MAP = (
    ("source_actor", "actor"),
    ("source_object_or_receiver", "object_or_receiver"),
    ("source_pressure_or_trigger", "pressure_or_trigger"),
    ("source_action", "action"),
    ("source_control_change", "control_change"),
    ("source_information_change", "information_change"),
    ("source_consequence", "consequence"),
)
P_EQUIVALENCE_REVIEW_FIELDS = (
    "action_equivalence_review",
    "control_change_equivalence_review",
    "information_change_equivalence_review",
    "consequence_equivalence_review",
    "independent_beat_judgment",
)
CONSTRUCTION_MARKERS = (
    "不照搬", "不能写成", "不承担", "只供应", "公开场不能", "叙述不写成", "机制迁移",
)
GENERIC_MARKERS = (
    "当前关系压力", "继续偏移", "目标婚姻场景", "后果继续传到下一拍", "实际选择与后果",
)
ABSTRACT_HURT_OBJECTS = {"关系", "关系位置", "婚姻", "婚姻位置", "读者预期", "在场者"}
ENTITY_CLAUSE_MARKERS = (
    "之后", "以前", "当时", "现场", "突然", "因为", "为了", "已经", "正在", "开始",
    "完成", "发生", "发现", "决定", "要求", "拿走", "交给", "离开", "回到", "走进",
)
OUTLINE_SECTION_HEADING = re.compile(
    r"^##[ \t]+(导语|尾声|\d+[.、．](?:[ \t]+[^\n]+)?)[ \t]*$",
    re.MULTILINE,
)
TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def surface(value: Any) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(value or ""))


def content_tokens(text: Any) -> list[str]:
    seen: list[str] = []
    for token in TOKEN_RE.findall(str(text or "")):
        if token not in seen:
            seen.append(token)
    return seen


def infer_hurt_object(text: Any, fallback: Any = "") -> str:
    for source in (text, fallback):
        tokens = content_tokens(source)
        if tokens:
            return tokens[-1]
    return "关系"


def normalize_outline_region(value: Any) -> str:
    label = str(value or "").strip()
    if label in {"导语", "opening"}:
        return "opening"
    if label in {"尾声", "epilogue"}:
        return "epilogue"
    match = re.fullmatch(r"第(\d+)节", label) or re.fullmatch(r"section:(\d+)", label)
    return f"section:{int(match.group(1))}" if match else ""


def binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha(resolved)}


def outline_regions(text: str) -> tuple[dict[str, tuple[int, int]], dict[str, int]]:
    headings = list(OUTLINE_SECTION_HEADING.finditer(text))
    regions: dict[str, tuple[int, int]] = {}
    order: dict[str, int] = {}
    for index, match in enumerate(headings):
        heading = match.group(1)
        if heading == "导语":
            key = "opening"
        elif heading == "尾声":
            key = "epilogue"
        else:
            section_number = re.match(r"\d+", heading)
            if section_number is None:
                continue
            key = f"section:{int(section_number.group())}"
        regions[key] = (match.end(), headings[index + 1].start() if index + 1 < len(headings) else len(text))
        order[key] = index
    return regions, order


def outline_bullets(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            result.append(stripped[2:].strip())
    return result


def region_bullets(text: str, region: str) -> list[str]:
    regions, _ = outline_regions(text)
    bounds = regions.get(region)
    if not bounds:
        return []
    start, end = bounds
    result: list[str] = []
    for line in text[start:end].splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            result.append(stripped[2:].strip())
    return result


def locate_outline_region(text: str, evidence: str) -> str:
    if not evidence:
        return ""
    regions, _ = outline_regions(text)
    offset = text.find(evidence)
    if offset < 0:
        return ""
    for key, (start, end) in regions.items():
        if start <= offset < end:
            return key
    return ""


def expand_to_outline_bullet(text: str, evidence: str) -> str:
    if not evidence:
        return ""
    offset = text.find(evidence)
    if offset < 0:
        return evidence
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end].strip()
    if line.startswith("- "):
        return line[2:].strip()
    return line or evidence


def split_outline_units(line: str) -> list[str]:
    clean = str(line or "").strip()
    if not clean:
        return []
    units: list[str] = []
    if clean not in units:
        units.append(clean)
    parts = [part.strip() for part in re.split(r"[，；：、]", clean) if part.strip()]
    for index, part in enumerate(parts):
        if part and part not in units:
            units.append(part)
        if index + 1 < len(parts):
            joined = "，".join(parts[: index + 2]).strip()
            if joined and joined not in units:
                units.append(joined)
        if index + 1 < len(parts):
            joined_tail = "，".join(parts[index: index + 2]).strip()
            if joined_tail and joined_tail not in units:
                units.append(joined_tail)
    return units


def compose_plot_evidence(full_line: str, fragment: str, actor: str, declared_aliases: dict[str, list[str]]) -> str:
    line = full_line.strip()
    frag = fragment.strip()
    if not line:
        return frag
    if not frag or frag not in line:
        return line
    fragment_has_actor = any(alias and alias in frag for alias in _actor_aliases(actor, declared_aliases))
    fragment_has_pronoun = bool(re.search(r"他们|她们|两人|对方|[我他她]", frag))
    if (fragment_has_actor or fragment_has_pronoun) and len(surface(frag)) >= 5:
        return frag.strip("，。；;、 ")
    actor_aliases = _actor_aliases(actor, declared_aliases)
    actor_offsets = [line.find(alias) for alias in actor_aliases if alias and line.find(alias) >= 0]
    frag_start = line.find(frag)
    frag_end = frag_start + len(frag)
    prior_actor_offsets = [offset for offset in actor_offsets if offset <= frag_start]
    if prior_actor_offsets:
        start = min(prior_actor_offsets)
        return line[start:frag_end].strip("，。；;、 ")
    return frag


def _score_plot_candidate(
    candidate: str,
    source_prior: dict[str, Any],
    actor: str,
    declared_aliases: dict[str, list[str]],
) -> int:
    candidate_text = str(candidate or "").strip()
    compact_candidate = surface(candidate_text)
    score = 0
    for alias in _actor_aliases(actor, declared_aliases):
        if alias and alias in candidate_text:
            score += 18
            break
    if re.search(r"他们|她们|两人|对方|[我他她]", candidate_text):
        score += 5
    for field, weight in (
        ("action", 7),
        ("object_or_receiver", 5),
        ("pressure_or_trigger", 4),
        ("consequence", 3),
        ("information_change", 2),
        ("source_evidence", 6),
        ("evidence", 6),
    ):
        for token in content_tokens(source_prior.get(field)):
            if token and token in compact_candidate:
                score += weight
    if len(compact_candidate) < 4:
        score -= 4
    return score


def _pick_plot_evidence(
    fragment: str,
    full_line: str,
    source_prior: dict[str, Any],
    actor: str,
    declared_aliases: dict[str, list[str]],
    used_evidence: set[str],
) -> str:
    candidates: list[str] = []
    for item in (fragment, full_line):
        text = str(item or "").strip()
        if text and text not in candidates:
            candidates.append(text)
        for unit in split_outline_units(text):
            if unit not in candidates:
                candidates.append(unit)
    best = ""
    best_score = -10**9
    fallback = ""
    fallback_score = -10**9
    for pos, candidate in enumerate(candidates):
        score = _score_plot_candidate(candidate, source_prior, actor, declared_aliases) - pos
        if score > fallback_score:
            fallback = candidate
            fallback_score = score
        if candidate in used_evidence:
            continue
        if score > best_score:
            best = candidate
            best_score = score
    return best or fallback or fragment or full_line


def _neighbor_candidates(all_bullets: list[str], evidence: str) -> list[str]:
    clean = str(evidence or "").strip()
    if not clean:
        return []
    try:
        idx = all_bullets.index(clean)
    except ValueError:
        return []
    candidates: list[str] = []
    for pos in range(max(0, idx - 3), min(len(all_bullets), idx + 4)):
        bullet = all_bullets[pos]
        if bullet not in candidates:
            candidates.append(bullet)
        for unit in split_outline_units(bullet):
            if unit not in candidates:
                candidates.append(unit)
    return candidates


def _region_candidate_pool(outline_text: str, region: str) -> list[str]:
    bullets = region_bullets(outline_text, region)
    candidates: list[str] = []
    for bullet in bullets:
        if bullet not in candidates:
            candidates.append(bullet)
        for unit in split_outline_units(bullet):
            if len(surface(unit)) >= 6 and unit not in candidates:
                candidates.append(unit)
    for start in range(len(bullets)):
        for span in (2, 3):
            end = start + span
            if end > len(bullets):
                continue
            window = "\n".join(f"- {bullet}" for bullet in bullets[start:end])
            if window in outline_text and window not in candidates:
                candidates.append(window)
    return candidates


def _final_global_plot_resolution(
    plots: list[dict[str, Any]],
    plot_index: dict[str, dict[str, dict[str, Any]]],
    outline_text: str,
    declared_aliases: dict[str, list[str]],
) -> None:
    used: set[str] = set()
    for item in plots:
        beat_id = str(item.get("source_beat_id") or "").strip()
        prior = plot_index.get(beat_id) or {}
        source_prior = prior.get("source") if isinstance(prior.get("source"), dict) else {}
        actor = str(item.get("actor") or source_prior.get("actor") or "")
        evidence = str(item.get("evidence") or "").strip()
        region = locate_outline_region(outline_text, evidence)
        if not region:
            target_prior = prior.get("target") if isinstance(prior.get("target"), dict) else {}
            seed = str(target_prior.get("evidence") or "").strip()
            region = locate_outline_region(outline_text, expand_to_outline_bullet(outline_text, seed) or seed)
        candidates = _region_candidate_pool(outline_text, region)
        if evidence and evidence not in candidates:
            candidates.append(evidence)
        needs_repick = evidence in used or not actor_resolves(item, declared_aliases)
        if needs_repick:
            ranked: list[tuple[int, int, str, str]] = []
            for pos, candidate in enumerate(candidates):
                if candidate in used:
                    continue
                actor_evidence = _extract_actor_evidence(actor, candidate, declared_aliases)
                actor_bonus = 40 if actor_evidence else 0
                score = _score_plot_candidate(
                    candidate,
                    source_prior,
                    actor,
                    declared_aliases,
                ) + actor_bonus - pos
                ranked.append((score, -pos, candidate, actor_evidence))
            if ranked:
                _, _, evidence, actor_evidence = max(ranked)
                item["evidence"] = evidence
                item["actor_evidence"] = actor_evidence
        if not str(item.get("actor_evidence") or "").strip():
            item["actor_evidence"] = _extract_actor_evidence(
                actor,
                str(item.get("evidence") or ""),
                declared_aliases,
            )
        resolved = str(item.get("evidence") or "").strip()
        if resolved:
            used.add(resolved)


def _post_resolve_plot_items(
    plots: list[dict[str, Any]],
    plot_index: dict[str, dict[str, dict[str, Any]]],
    outline_text: str,
    declared_aliases: dict[str, list[str]],
) -> None:
    all_bullets = outline_bullets(outline_text)
    by_evidence: dict[str, list[dict[str, Any]]] = {}
    for item in plots:
        evidence = str(item.get("evidence") or "").strip()
        if evidence:
            by_evidence.setdefault(evidence, []).append(item)
    used: set[str] = set()
    for evidence, items in by_evidence.items():
        if len(items) == 1 and str(items[0].get("actor_evidence") or "").strip():
            used.add(evidence)
            continue
        reserved = False
        for item in items:
            beat_id = str(item.get("source_beat_id") or "").strip()
            source_prior = (plot_index.get(beat_id) or {}).get("source") if isinstance((plot_index.get(beat_id) or {}).get("source"), dict) else {}
            actor = str(item.get("actor") or source_prior.get("actor") or "")
            full_line = expand_to_outline_bullet(outline_text, evidence)
            region = locate_outline_region(outline_text, full_line or evidence)
            candidate_pool: list[str] = []
            for candidate in region_bullets(outline_text, region):
                if candidate not in candidate_pool:
                    candidate_pool.append(candidate)
                for unit in split_outline_units(candidate):
                    if unit not in candidate_pool:
                        candidate_pool.append(unit)
            for candidate in _neighbor_candidates(all_bullets, full_line or evidence):
                if candidate not in candidate_pool:
                    candidate_pool.append(candidate)
            if full_line and full_line not in candidate_pool:
                candidate_pool.append(full_line)
            if evidence and evidence not in candidate_pool:
                candidate_pool.append(evidence)
            best = ""
            best_score = -10**9
            for pos, candidate in enumerate(candidate_pool):
                if candidate in used:
                    continue
                if candidate == evidence and reserved:
                    continue
                score = _score_plot_candidate(candidate, source_prior, actor, declared_aliases) - pos
                if score > best_score:
                    best = candidate
                    best_score = score
            if not best:
                if not reserved:
                    best = evidence
                    reserved = True
                else:
                    continue
            resolved = compose_plot_evidence(expand_to_outline_bullet(outline_text, best), best, actor, declared_aliases)
            item["evidence"] = resolved
            item["actor_evidence"] = _extract_actor_evidence(actor, resolved, declared_aliases)
            used.add(resolved)

    items_by_region: dict[str, list[dict[str, Any]]] = {}
    duplicate_evidence = {
        evidence
        for evidence, items in by_evidence.items()
        if evidence and len(items) > 1
    }
    for item in plots:
        evidence = str(item.get("evidence") or "").strip()
        region = locate_outline_region(outline_text, evidence)
        if not region:
            continue
        if evidence in duplicate_evidence or not str(item.get("actor_evidence") or "").strip():
            items_by_region.setdefault(region, []).append(item)

    for region, region_items in items_by_region.items():
        bullets = region_bullets(outline_text, region)
        candidate_pool: list[str] = []
        for bullet in bullets:
            if bullet not in candidate_pool:
                candidate_pool.append(bullet)
            for unit in split_outline_units(bullet):
                if unit not in candidate_pool:
                    candidate_pool.append(unit)
        if not candidate_pool:
            continue
        used_in_region: set[str] = set()
        ordered = sorted(
            region_items,
            key=lambda item: int(re.search(r"(\d+)$", str(item.get("source_beat_id") or "0")).group(1)),
        )
        for item in ordered:
            beat_id = str(item.get("source_beat_id") or "").strip()
            source_prior = (plot_index.get(beat_id) or {}).get("source") if isinstance((plot_index.get(beat_id) or {}).get("source"), dict) else {}
            actor = str(item.get("actor") or source_prior.get("actor") or "")
            best = ""
            best_score = -10**9
            fallback = str(item.get("evidence") or "").strip()
            unused_candidates = [candidate for candidate in candidate_pool if candidate not in used_in_region]
            search_pool = unused_candidates or candidate_pool
            for pos, candidate in enumerate(search_pool):
                score = _score_plot_candidate(candidate, source_prior, actor, declared_aliases) - pos
                if score > best_score:
                    best = candidate
                    best_score = score
            if not best:
                best = fallback
            resolved = compose_plot_evidence(expand_to_outline_bullet(outline_text, best), best, actor, declared_aliases)
            item["evidence"] = resolved
            item["actor_evidence"] = _extract_actor_evidence(actor, resolved, declared_aliases)
            if resolved:
                used_in_region.add(resolved)
    _final_global_plot_resolution(plots, plot_index, outline_text, declared_aliases)


def source_beat_regions(beats: list[dict[str, Any]], segments: list[dict[str, Any]] | None = None) -> dict[str, str]:
    structural_lines = [
        segment.get("start_line")
        for segment in segments or []
        if isinstance(segment, dict)
        and segment.get("kind") == "structural_marker"
        and isinstance(segment.get("start_line"), int)
    ]
    first_body_marker = min(structural_lines) if structural_lines else None
    bid_indexes = [index for index, beat in enumerate(beats) if isinstance(beat, dict) and beat.get("bid_ids")]
    if not bid_indexes:
        result = {
            str(beat.get("beat_id") or "").strip(): "transition"
            for beat in beats
            if isinstance(beat, dict)
        }
        if first_body_marker is not None:
            for beat in beats:
                if (
                    isinstance(beat, dict)
                    and isinstance(beat.get("end_line"), int)
                    and beat["end_line"] < first_body_marker
                ):
                    result[str(beat.get("beat_id") or "").strip()] = "opening"
        return result
    last_bid = bid_indexes[-1]
    result: dict[str, str] = {}
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        if (
            first_body_marker is not None
            and isinstance(beat.get("end_line"), int)
            and beat["end_line"] < first_body_marker
        ):
            result[beat_id] = "opening"
        elif beat.get("bid_ids"):
            result[beat_id] = "bridge"
        elif index > last_bid:
            result[beat_id] = "epilogue"
        else:
            result[beat_id] = "transition"
    return result


def export_template(
    mapping_path: Path,
    outline_path: Path,
    emotion_ledger_path: Path,
    plot_ledger_path: Path,
    primary_source_path: Path,
    outline_contract_path: Path,
) -> None:
    outline = outline_path.read_text(encoding="utf-8")
    emotion_ledger_data = load(emotion_ledger_path)
    emotion_ledger = emotion_ledger_data.get("beats", [])
    plot_ledger = load(plot_ledger_path).get("beats", [])
    outline_contract = load(outline_contract_path)
    existing = load(mapping_path) if mapping_path.is_file() else {}

    region_by_emotion: dict[str, str] = {}
    for section in outline_contract.get("sections", []):
        if not isinstance(section, dict):
            continue
        region = f"section:{section.get('section_id')}"
        parity = section.get("source_emotion_parity") if isinstance(section.get("source_emotion_parity"), dict) else {}
        for beat in parity.get("source_emotion_sequence", []):
            if isinstance(beat, dict):
                beat_id = str(beat.get("beat_id") or "").strip()
                if beat_id:
                    region_by_emotion[beat_id] = region

    outside_parity = outline_contract.get("outside_bridge_plot_parity")
    if isinstance(outside_parity, dict):
        ledger_regions = source_beat_regions(emotion_ledger, emotion_ledger_data.get("coverage_segments"))
        for item in outside_parity.get("source_emotion_sequence", []):
            if not isinstance(item, dict):
                continue
            beat_id = str(item.get("beat_id") or "").strip()
            region = ledger_regions.get(beat_id)
            if region in {"opening", "epilogue"}:
                region_by_emotion.setdefault(beat_id, region)

    existing_emotions = {
        str(item.get("source_beat_id") or ""): item
        for item in existing.get("emotions", [])
        if isinstance(item, dict)
    }
    emotions: list[dict[str, Any]] = []
    for beat in emotion_ledger:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        prior = existing_emotions.get(beat_id, {})
        emotions.append({
            "source_beat_id": beat_id,
            "target_beat_id": str(prior.get("target_beat_id") or beat_id),
            "role": beat.get("role"),
            "intensity": beat.get("intensity"),
            "target_outline_region": str(prior.get("target_outline_region") or region_by_emotion.get(beat_id, "")),
            "trigger": str(prior.get("trigger") or beat.get("trigger") or ""),
            "relationship_position_change": str(prior.get("relationship_position_change") or beat.get("relationship_position_change") or ""),
            "reader_effect": str(prior.get("reader_effect") or beat.get("reader_effect") or ""),
            "target_story_adaptation": str(prior.get("target_story_adaptation") or ""),
            "hurt_object": str(prior.get("hurt_object") or ""),
            "expectation_before": str(prior.get("expectation_before") or ""),
            "expectation_after": str(prior.get("expectation_after") or ""),
            "action_impulse_before": str(prior.get("action_impulse_before") or ""),
            "action_impulse_after": str(prior.get("action_impulse_after") or ""),
            "equivalence_reason": str(prior.get("equivalence_reason") or ""),
            "target_evidence_coverage_review": str(prior.get("target_evidence_coverage_review") or ""),
            "evidence": str(prior.get("evidence") or ""),
        })

    existing_plots = {}
    for item in existing.get("plots", []):
        if isinstance(item, dict):
            key = (str(Path(item.get("source_path", "")).resolve()), str(item.get("source_beat_id") or ""))
            existing_plots[key] = item
    source_key = str(primary_source_path.resolve())
    plots: list[dict[str, Any]] = []
    for beat in plot_ledger:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        prior = existing_plots.get((source_key, beat_id), {})
        plots.append({
            "source_path": source_key,
            "source_beat_id": beat_id,
            "target_beat_id": str(prior.get("target_beat_id") or beat_id),
            "source_actor": beat.get("actor"),
            "source_object_or_receiver": beat.get("object_or_receiver"),
            "source_pressure_or_trigger": beat.get("pressure_or_trigger"),
            "source_action": beat.get("action"),
            "source_control_change": beat.get("control_change"),
            "source_information_change": beat.get("information_change"),
            "source_consequence": beat.get("consequence"),
            "actor": str(prior.get("actor") or beat.get("actor") or ""),
            "actor_evidence": str(prior.get("actor_evidence") or ""),
            "object_or_receiver": str(prior.get("object_or_receiver") or beat.get("object_or_receiver") or ""),
            "pressure_or_trigger": str(prior.get("pressure_or_trigger") or beat.get("pressure_or_trigger") or ""),
            "action": str(prior.get("action") or beat.get("action") or ""),
            "control_change": str(prior.get("control_change") or beat.get("control_change") or ""),
            "information_change": str(prior.get("information_change") or beat.get("information_change") or ""),
            "consequence": str(prior.get("consequence") or beat.get("consequence") or ""),
            "adaptation_equivalence": str(prior.get("adaptation_equivalence") or ""),
            "action_equivalence_review": str(prior.get("action_equivalence_review") or ""),
            "control_change_equivalence_review": str(prior.get("control_change_equivalence_review") or ""),
            "information_change_equivalence_review": str(prior.get("information_change_equivalence_review") or ""),
            "consequence_equivalence_review": str(prior.get("consequence_equivalence_review") or ""),
            "independent_beat_judgment": str(prior.get("independent_beat_judgment") or ""),
            "evidence": str(prior.get("evidence") or ""),
        })

    result = {
        "version": str(existing.get("version") or "1.0"),
        "status": str(existing.get("status") or "pending"),
        "reviewed_by_current_model": bool(existing.get("reviewed_by_current_model", False)),
        "source_policy": str(existing.get("source_policy") or "primary_only_full_emotion_and_plot; prose voice remains exclusive to 幼薇; auxiliary books, if any, may only supply external plot mechanics and must not mix into primary E/P identity."),
        "bindings": {
            "outline": binding(outline_path),
            "primary_source": binding(primary_source_path),
            "primary_emotion_ledger": binding(emotion_ledger_path),
            "primary_plot_ledger": binding(plot_ledger_path),
        },
        "entity_aliases": existing.get("entity_aliases", {}),
        "emotions": emotions,
        "plots": plots,
        "manual_judgment": str(existing.get("manual_judgment") or "官方模板已按主体 E/P 总账全集与已通过细纲重建完整骨架；当前仍待逐拍人工填写 target_story_adaptation、expectation/action 前后态、actor_evidence、adaptation_equivalence 与独占 evidence，未完成前不得改为 approved。"),
    }
    entity_aliases_payload = result["entity_aliases"] if isinstance(result.get("entity_aliases"), dict) else {}
    if "我本人" not in entity_aliases_payload:
        entity_aliases_payload["我本人"] = ["我"]
    result["entity_aliases"] = entity_aliases_payload
    write(mapping_path, result)


def _outline_contract_emotion_index(outline_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for section in outline_contract.get("sections", []):
        if not isinstance(section, dict):
            continue
        parity = section.get("source_emotion_parity") if isinstance(section.get("source_emotion_parity"), dict) else {}
        for item in parity.get("target_emotion_sequence") or []:
            if isinstance(item, dict):
                beat_id = str(item.get("beat_id") or "").strip()
                if beat_id and beat_id not in index:
                    index[beat_id] = item
    for item in ((outline_contract.get("outside_bridge_plot_parity") or {}).get("target_emotion_sequence") or []):
        if isinstance(item, dict):
            beat_id = str(item.get("beat_id") or "").strip()
            if beat_id and beat_id not in index:
                index[beat_id] = item
    for bridge in outline_contract.get("outline_bridge_flow_parity", []):
        if not isinstance(bridge, dict):
            continue
        for item in bridge.get("target_emotion_sequence") or []:
            if isinstance(item, dict):
                beat_id = str(item.get("beat_id") or "").strip()
                if beat_id and beat_id not in index:
                    index[beat_id] = item
    return index


def _outline_contract_plot_index(outline_contract: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {}
    outside = outline_contract.get("outside_bridge_plot_parity") or {}
    for source_item in outside.get("source_plot_beats") or []:
        if isinstance(source_item, dict):
            beat_id = str(source_item.get("beat_id") or "").strip()
            if beat_id:
                index.setdefault(beat_id, {})["source"] = source_item
    for target_item in outside.get("target_plot_beats") or []:
        if isinstance(target_item, dict):
            beat_id = str(target_item.get("beat_id") or "").strip()
            if beat_id:
                index.setdefault(beat_id, {})["target"] = target_item
    for bridge in outline_contract.get("outline_bridge_flow_parity", []):
        if not isinstance(bridge, dict):
            continue
        for source_item in bridge.get("source_plot_beats") or []:
            if isinstance(source_item, dict):
                beat_id = str(source_item.get("beat_id") or "").strip()
                if beat_id:
                    index.setdefault(beat_id, {})["source"] = source_item
        for target_item in bridge.get("target_plot_beats") or []:
            if isinstance(target_item, dict):
                beat_id = str(target_item.get("beat_id") or "").strip()
                if beat_id:
                    index.setdefault(beat_id, {})["target"] = target_item
    return index


def _fill(value: Any, fallback: Any) -> str:
    text = str(value or "").strip()
    return text if text else str(fallback or "").strip()


def _emotion_story_adaptation(item: dict[str, Any]) -> str:
    evidence = str(item.get("evidence") or "").strip()
    role = str(item.get("role") or "").strip()
    trigger = str(item.get("trigger") or "").strip()
    if role and evidence:
        return f"把{role}这一下落到“{evidence}”这句里。"
    if trigger and evidence:
        return f"把“{trigger}”落到“{evidence}”这句里。"
    return ""


def _emotion_evidence_review(item: dict[str, Any]) -> str:
    evidence = str(item.get("evidence") or "").strip()
    role = str(item.get("role") or "").strip()
    relationship = str(item.get("relationship_position_change") or "").strip()
    if evidence and relationship:
        return f"证据直接落在“{evidence}”，把关系推进到{relationship}。"
    if evidence and role:
        return f"证据直接落在“{evidence}”，能托住{role}这拍。"
    return ""


def _score_evidence(source: dict[str, Any], candidate: str) -> int:
    compact_candidate = surface(candidate)
    score = 0
    for field, weight in (
        ("evidence", 7),
        ("trigger", 5),
        ("relationship_position_change", 3),
        ("reader_effect", 2),
        ("role", 1),
    ):
        for token in content_tokens(source.get(field)):
            if token and token in compact_candidate:
                score += weight
    return score


def _pick_best_candidates(source_items: list[dict[str, Any]], candidates: list[str]) -> list[str]:
    pool = [str(item).strip() for item in candidates if str(item).strip()]
    if not pool:
        return [""] * len(source_items)
    chosen: list[str] = []
    used: set[str] = set()
    for index, source in enumerate(source_items):
        best = ""
        best_score = -10**9
        for pos, candidate in enumerate(pool):
            if candidate in used:
                continue
            score = _score_evidence(source, candidate) - pos
            if score > best_score:
                best = candidate
                best_score = score
        if not best:
            best = pool[min(index, len(pool) - 1)]
        used.add(best)
        chosen.append(best)
    return chosen


def _outside_emotion_defaults(
    outline_contract: dict[str, Any],
    outline_text: str,
    emotion_ledger_data: dict[str, Any],
) -> dict[str, dict[str, str]]:
    outside = outline_contract.get("outside_bridge_plot_parity") or {}
    source_items = [item for item in outside.get("source_emotion_sequence") or [] if isinstance(item, dict)]
    ledger_regions = source_beat_regions(
        emotion_ledger_data.get("beats", []),
        emotion_ledger_data.get("coverage_segments"),
    )
    regions, _ = outline_regions(outline_text)
    opening_lines = [
        line[2:].strip()
        for line in outline_text[
            regions.get("opening", (0, 0))[0]:regions.get("opening", (0, 0))[1]
        ].splitlines()
        if line.strip().startswith("- ")
    ]
    epilogue_lines = [
        line[2:].strip()
        for line in outline_text[
            regions.get("epilogue", (0, 0))[0]:regions.get("epilogue", (0, 0))[1]
        ].splitlines()
        if line.strip().startswith("- ")
    ]
    grouped: dict[str, list[dict[str, Any]]] = {"opening": [], "epilogue": []}
    for item in source_items:
        beat_id = str(item.get("beat_id") or "").strip()
        region = ledger_regions.get(beat_id, "")
        if region == "opening":
            grouped["opening"].append(item)
        elif region == "epilogue":
            grouped["epilogue"].append(item)
    result: dict[str, dict[str, str]] = {}
    for region, lines in (("opening", opening_lines), ("epilogue", epilogue_lines)):
        picks = _pick_best_candidates(grouped[region], lines)
        for source, evidence in zip(grouped[region], picks):
            beat_id = str(source.get("beat_id") or "").strip()
            relationship = str(source.get("relationship_position_change") or "").strip()
            hurt_object = infer_hurt_object(
                evidence,
                " / ".join(
                    str(source.get(field) or "")
                    for field in ("relationship_position_change", "trigger", "reader_effect", "evidence")
                ),
            )
            result[beat_id] = {
                "evidence": evidence,
                "trigger": evidence,
                "hurt_object": hurt_object,
                "expectation_before": str(source.get("role") or "").strip() or f"上一拍还没把这层关系说透：{evidence}",
                "expectation_after": relationship or f"这句把关系直接推到了新的位置：{evidence}",
                "action_impulse_before": f"还想先守住前一层期待：{str(source.get('role') or evidence).strip()}",
                "action_impulse_after": f"被这句逼着立刻顺着后果往下走：{relationship or evidence}",
                "equivalence_reason": "桥外首尾拍按当前细纲真实句面补回同拍情绪功能。",
                "target_story_adaptation": f"把{str(source.get('role') or '该拍情绪').strip()}落到“{evidence}”这句里。",
                "target_evidence_coverage_review": f"证据直接落在“{evidence}”，承接该拍触发与关系后果。",
            }
    return result


def _actor_aliases(actor: str, declared_aliases: dict[str, list[str]]) -> list[str]:
    aliases = [actor]
    aliases.extend(declared_aliases.get(actor, []))
    if 3 <= len(actor) <= 4 and all("\u4e00" <= char <= "\u9fff" for char in actor):
        aliases.append(actor[1:])
    return [alias for alias in aliases if alias]


def _extract_actor_evidence(actor: str, evidence: str, declared_aliases: dict[str, list[str]]) -> str:
    for alias in _actor_aliases(actor, declared_aliases):
        if alias in evidence:
            return alias
    pronoun_match = re.search(r"他们|她们|两人|对方|[我他她]", evidence)
    return pronoun_match.group(0) if pronoun_match else ""


def _resolve_target_actor(
    evidence: str,
    source_actor: str,
    declared_aliases: dict[str, list[str]],
) -> str:
    best_name = ""
    best_offset = None
    best_length = -1
    for canonical, aliases in declared_aliases.items():
        tokens = [canonical, *aliases]
        for alias in tokens:
            if not alias:
                continue
            offset = evidence.find(alias)
            if offset >= 0 and (
                best_offset is None
                or offset < best_offset
                or (offset == best_offset and len(canonical) > best_length)
            ):
                best_name = canonical
                best_offset = offset
                best_length = len(canonical)
    if best_name:
        return best_name
    if source_actor == "我":
        return "我本人" if "我本人" in declared_aliases else source_actor
    return source_actor


def sync_from_outline_contract(
    mapping_path: Path,
    outline_path: Path,
    emotion_ledger_path: Path,
    plot_ledger_path: Path,
    primary_source_path: Path,
    outline_contract_path: Path,
) -> None:
    export_template(
        mapping_path,
        outline_path,
        emotion_ledger_path,
        plot_ledger_path,
        primary_source_path,
        outline_contract_path,
    )
    mapping = load(mapping_path)
    outline_contract = load(outline_contract_path)
    emotion_ledger_data = load(emotion_ledger_path)
    outline_text = outline_path.read_text(encoding="utf-8")
    emotion_index = _outline_contract_emotion_index(outline_contract)
    plot_index = _outline_contract_plot_index(outline_contract)
    primary_source = str(primary_source_path.resolve())
    declared_aliases = mapping.get("entity_aliases") if isinstance(mapping.get("entity_aliases"), dict) else {}
    outside_emotion_defaults = _outside_emotion_defaults(outline_contract, outline_text, emotion_ledger_data)
    used_plot_evidence: set[str] = set()

    for item in mapping.get("emotions", []):
        if not isinstance(item, dict):
            continue
        beat_id = str(item.get("source_beat_id") or "").strip()
        prior = emotion_index.get(beat_id)
        if not prior and beat_id not in outside_emotion_defaults:
            continue
        fallback = outside_emotion_defaults.get(beat_id, {})
        item["target_beat_id"] = str((prior or {}).get("beat_id") or item.get("target_beat_id") or beat_id)
        item["trigger"] = str((prior or {}).get("trigger") or fallback.get("trigger") or "")
        item["relationship_position_change"] = str((prior or {}).get("relationship_position_change") or item.get("relationship_position_change") or "")
        item["reader_effect"] = str((prior or {}).get("reader_effect") or item.get("reader_effect") or "")
        item["hurt_object"] = str((prior or {}).get("hurt_object") or fallback.get("hurt_object") or "")
        if not entity_label_valid(item["hurt_object"]):
            candidate_actor = str((prior or {}).get("actor") or "").strip()
            item["hurt_object"] = candidate_actor if entity_label_valid(candidate_actor) else "关系位置"
        item["expectation_before"] = str((prior or {}).get("expectation_before") or fallback.get("expectation_before") or "")
        item["expectation_after"] = str((prior or {}).get("expectation_after") or fallback.get("expectation_after") or "")
        item["action_impulse_before"] = str((prior or {}).get("action_impulse_before") or fallback.get("action_impulse_before") or "")
        item["action_impulse_after"] = str((prior or {}).get("action_impulse_after") or fallback.get("action_impulse_after") or "")
        item["equivalence_reason"] = str((prior or {}).get("equivalence_reason") or fallback.get("equivalence_reason") or "")
        item["evidence"] = str((prior or {}).get("evidence") or fallback.get("evidence") or "")
        item["target_outline_region"] = locate_outline_region(outline_text, item["evidence"]) or str(item.get("target_outline_region") or "")
        item["target_story_adaptation"] = str(fallback.get("target_story_adaptation") or _emotion_story_adaptation(prior or item))
        item["target_evidence_coverage_review"] = str(fallback.get("target_evidence_coverage_review") or _emotion_evidence_review(prior or item))

    for item in mapping.get("plots", []):
        if not isinstance(item, dict):
            continue
        beat_id = str(item.get("source_beat_id") or "").strip()
        prior = plot_index.get(beat_id)
        if not prior:
            continue
        source_prior = prior.get("source") if isinstance(prior.get("source"), dict) else {}
        target_prior = prior.get("target") if isinstance(prior.get("target"), dict) else {}
        fragment = str(target_prior.get("evidence") or "").strip()
        full_line = expand_to_outline_bullet(outline_text, fragment)
        actor = _resolve_target_actor(full_line or fragment, str(source_prior.get("actor") or ""), declared_aliases)
        evidence_seed = _pick_plot_evidence(fragment, full_line, source_prior, actor, declared_aliases, used_plot_evidence)
        evidence = compose_plot_evidence(full_line, evidence_seed, actor, declared_aliases)
        if evidence in used_plot_evidence and evidence != full_line:
            alternative = _pick_plot_evidence(full_line, full_line, source_prior, actor, declared_aliases, used_plot_evidence)
            evidence = compose_plot_evidence(full_line, alternative, actor, declared_aliases)
        actor_evidence = _extract_actor_evidence(actor, evidence, declared_aliases)
        item["source_path"] = primary_source
        item["target_beat_id"] = str(target_prior.get("beat_id") or beat_id)
        item["actor"] = actor
        item["actor_evidence"] = actor_evidence
        item["object_or_receiver"] = str(source_prior.get("object_or_receiver") or "")
        item["pressure_or_trigger"] = str(source_prior.get("pressure_or_trigger") or "")
        item["action"] = str(target_prior.get("action") or source_prior.get("action") or "")
        if actor and item["actor"] not in item["action"]:
            item["action"] = f"{actor}{item['action']}"
        item["control_change"] = str(source_prior.get("control_change") or "")
        item["information_change"] = str(source_prior.get("information_change") or "")
        item["consequence"] = str(source_prior.get("consequence") or "")
        item["adaptation_equivalence"] = str(target_prior.get("adaptation_equivalence") or "")
        item["evidence"] = evidence
        if evidence:
            used_plot_evidence.add(evidence)

    _post_resolve_plot_items(
        [item for item in mapping.get("plots", []) if isinstance(item, dict)],
        plot_index,
        outline_text,
        declared_aliases,
    )

    mapping["manual_judgment"] = _fill(
        mapping.get("manual_judgment"),
        "已从通过的细纲表演验收回执同步现成 E/P 裁决；同步只回收正式真源中的人工字段，不代替剩余逐拍复核。",
    )
    write(mapping_path, mapping)


def actor_tokens(value: Any) -> list[str]:
    return [x.strip() for x in re.split(r"[、,，/；;]|(?:与|和)", str(value or "")) if len(x.strip()) >= 2]


def entity_aliases(value: Any) -> set[str]:
    """Return conservative Chinese name aliases, including a dropped surname."""
    label = surface(value)
    aliases = {label} if label else set()
    if 3 <= len(label) <= 4 and all("\u4e00" <= char <= "\u9fff" for char in label):
        aliases.add(label[1:])
    for suffix in ("母亲", "父亲", "妈妈", "爸爸"):
        if label.endswith(suffix) and len(label) > len(suffix):
            aliases.add(suffix)
    if label.startswith("医院") and len(label) > 2:
        aliases.add(label[2:])
    return aliases


def entity_mentioned(entity: Any, text: Any, declared_aliases: dict[str, list[str]] | None = None) -> bool:
    haystack = surface(text)
    tokens = actor_tokens(entity)
    if len(tokens) > 1:
        return all(entity_mentioned(token, text, declared_aliases) for token in tokens)
    aliases = entity_aliases(entity)
    if declared_aliases:
        aliases.update(surface(alias) for alias in declared_aliases.get(str(entity), []) if surface(alias))
    return any(alias and alias in haystack for alias in aliases)


def entity_label_valid(value: Any) -> bool:
    """Accept open-world person/group labels while rejecting sentence-like event labels."""
    label = str(value or "").strip()
    compact = surface(label)
    if not compact or len(compact) > 16:
        return False
    if re.search(r"[。！？!?：:]", label):
        return False
    return not any(marker in label for marker in ENTITY_CLAUSE_MARKERS)


def actor_resolves(item: dict[str, Any], declared_aliases: dict[str, list[str]] | None = None) -> bool:
    tokens = actor_tokens(item.get("actor"))
    actor_evidence = str(item.get("actor_evidence") or "").strip()
    evidence = str(item.get("evidence") or "")
    action = str(item.get("action") or "")
    if actor_evidence not in evidence or not tokens:
        return False
    if any(entity_mentioned(x, actor_evidence, declared_aliases) for x in tokens):
        return True
    has_pronoun = bool(re.search(r"他们|她们|两人|对方|[他她其]", actor_evidence))
    return has_pronoun and any(
        entity_mentioned(x, action, declared_aliases) for x in tokens
    )


def require_fields(item: dict[str, Any], fields: tuple[str, ...], label: str, errors: list[str]) -> None:
    for field in fields:
        minimum = 1 if field in {"intensity", "hurt_object", "actor_evidence", "object_or_receiver"} else 2
        if len(str(item.get(field) or "").strip()) < minimum:
            errors.append(f"{label}.{field} 缺失或过短")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-template")
    export_parser.add_argument("--mapping", required=True, type=Path)
    export_parser.add_argument("--outline", required=True, type=Path)
    export_parser.add_argument("--primary-emotion-ledger", required=True, type=Path)
    export_parser.add_argument("--primary-plot-ledger", required=True, type=Path)
    export_parser.add_argument("--primary-source", required=True, type=Path)
    export_parser.add_argument("--outline-contract", required=True, type=Path)

    sync_parser = subparsers.add_parser("sync-from-outline-contract")
    sync_parser.add_argument("--mapping", required=True, type=Path)
    sync_parser.add_argument("--outline", required=True, type=Path)
    sync_parser.add_argument("--primary-emotion-ledger", required=True, type=Path)
    sync_parser.add_argument("--primary-plot-ledger", required=True, type=Path)
    sync_parser.add_argument("--primary-source", required=True, type=Path)
    sync_parser.add_argument("--outline-contract", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--mapping", required=True, type=Path)
    validate_parser.add_argument("--outline", required=True, type=Path)
    validate_parser.add_argument("--primary-emotion-ledger", required=True, type=Path)
    validate_parser.add_argument("--primary-plot-ledger", required=True, type=Path)
    validate_parser.add_argument("--primary-source", required=True, type=Path)
    args = parser.parse_args()

    if args.command == "export-template":
        export_template(
            args.mapping.resolve(),
            args.outline.resolve(),
            args.primary_emotion_ledger.resolve(),
            args.primary_plot_ledger.resolve(),
            args.primary_source.resolve(),
            args.outline_contract.resolve(),
        )
        print(f"semantic_beat_mapping: template exported -> {args.mapping.resolve()}")
        return 0

    if args.command == "sync-from-outline-contract":
        sync_from_outline_contract(
            args.mapping.resolve(),
            args.outline.resolve(),
            args.primary_emotion_ledger.resolve(),
            args.primary_plot_ledger.resolve(),
            args.primary_source.resolve(),
            args.outline_contract.resolve(),
        )
        print(f"semantic_beat_mapping: synced from outline contract -> {args.mapping.resolve()}")
        return 0

    errors: list[str] = []
    mapping = load(args.mapping)
    outline = args.outline.read_text(encoding="utf-8")
    emotion_ledger = load(args.primary_emotion_ledger).get("beats", [])
    plot_ledger = load(args.primary_plot_ledger).get("beats", [])
    emotions = mapping.get("emotions") if isinstance(mapping.get("emotions"), list) else []
    plots = mapping.get("plots") if isinstance(mapping.get("plots"), list) else []
    raw_aliases = mapping.get("entity_aliases") if isinstance(mapping.get("entity_aliases"), dict) else {}
    declared_aliases: dict[str, list[str]] = {}
    for entity, values in raw_aliases.items():
        if not entity_label_valid(entity) or not isinstance(values, list) or not values:
            errors.append(f"entity_aliases.{entity} 必须绑定规范实体和非空别名列表")
            continue
        aliases = [str(value).strip() for value in values if str(value).strip()]
        if len(aliases) != len(values) or any(alias not in outline for alias in aliases):
            errors.append(f"entity_aliases.{entity} 含空值或未在细纲出现的别名")
            continue
        declared_aliases[str(entity)] = aliases
    if mapping.get("status") != "approved":
        errors.append("mapping.status 必须为 approved")
    bindings = mapping.get("bindings") if isinstance(mapping.get("bindings"), dict) else {}
    for key, path in (("outline", args.outline), ("primary_source", args.primary_source),
                      ("primary_emotion_ledger", args.primary_emotion_ledger),
                      ("primary_plot_ledger", args.primary_plot_ledger)):
        item = bindings.get(key) if isinstance(bindings.get(key), dict) else {}
        if str(Path(item.get("path", "")).resolve()) != str(path.resolve()) or item.get("sha256") != sha(path):
            errors.append(f"bindings.{key} 路径或 SHA 不匹配")

    expected_e = [str(x.get("beat_id")) for x in emotion_ledger]
    actual_e = [str(x.get("source_beat_id")) for x in emotions]
    if actual_e != expected_e:
        errors.append("主体 E 拍必须与情绪总账全集完全同序")
    primary_key = str(args.primary_source.resolve())
    primary_plots = [x for x in plots if str(Path(x.get("source_path", "")).resolve()) == primary_key]
    expected_p = [str(x.get("beat_id")) for x in plot_ledger]
    actual_p = [str(x.get("source_beat_id")) for x in primary_plots]
    if actual_p != expected_p:
        errors.append("主体 P 拍必须与情节总账全集完全同序")

    used_evidence: dict[str, set[str]] = {"E": set(), "P": set()}
    generic = Counter()
    emotion_signatures: dict[str, list[tuple[str, ...]]] = {}
    source_e = {str(x.get("beat_id")): x for x in emotion_ledger}
    region_bounds, region_order = outline_regions(outline)
    previous_region_order = -1
    for index, item in enumerate(emotions, 1):
        label = f"emotions[{index}]"
        require_fields(item, E_FIELDS, label, errors)
        source = source_e.get(str(item.get("source_beat_id")), {})
        if item.get("role") != source.get("role") or item.get("intensity") != source.get("intensity"):
            errors.append(f"{label} role/intensity 与来源总账不一致")
        evidence = str(item.get("evidence") or "")
        if evidence not in outline:
            errors.append(f"{label}.evidence 不在当前细纲")
        if evidence in used_evidence["E"]:
            errors.append(f"{label}.evidence 与其他 E 拍重复")
        used_evidence["E"].add(evidence)
        if any(x in evidence for x in CONSTRUCTION_MARKERS):
            errors.append(f"{label}.evidence 是施工说明")
        hurt = str(item.get("hurt_object") or "").strip()
        if hurt not in ABSTRACT_HURT_OBJECTS and not entity_label_valid(hurt):
            errors.append(f"{label}.hurt_object 必须是人物、关系或读者预期，不能是整句事件")
        resolution_context = "".join(str(item.get(field) or "") for field in (
            "target_story_adaptation", "trigger", "relationship_position_change",
            "reader_effect", "expectation_before", "expectation_after",
            "action_impulse_before", "action_impulse_after", "equivalence_reason",
            "target_evidence_coverage_review",
        ))
        has_pronoun = bool(re.search(r"他们|她们|对方|[我他她]", evidence))
        if hurt not in ABSTRACT_HURT_OBJECTS and not entity_mentioned(hurt, evidence, declared_aliases):
            if not has_pronoun or not entity_mentioned(hurt, resolution_context, declared_aliases):
                errors.append(f"{label}.hurt_object 未在证据出现，也没有由代词和适配说明解析")
        if surface(item.get("expectation_before")) == surface(item.get("expectation_after")):
            errors.append(f"{label} 期待前后态未变化")
        if surface(item.get("action_impulse_before")) == surface(item.get("action_impulse_after")):
            errors.append(f"{label} 行动冲动前后态未变化")
        joined = "".join(str(item.get(x) or "") for x in E_FIELDS)
        if any(x in joined for x in GENERIC_MARKERS):
            generic["E"] += 1
        region = str(item.get("target_outline_region") or "")
        normalized_region = normalize_outline_region(region)
        if not normalized_region or normalized_region not in region_bounds:
            errors.append(f"{label}.target_outline_region 不是当前细纲中的真实区域: {region or '<empty>'}")
        else:
            start, end = region_bounds[normalized_region]
            evidence_offset = outline.find(evidence)
            if not (start <= evidence_offset < end):
                errors.append(f"{label}.evidence 不在声明的 {region} 区域内")
            current_region_order = region_order[normalized_region]
            if current_region_order < previous_region_order:
                errors.append(f"{label}.target_outline_region 使主体 E 拍跨节倒序: {region}")
            previous_region_order = max(previous_region_order, current_region_order)
        emotion_signatures.setdefault(region, []).append(tuple(surface(item.get(field)) for field in (
            "expectation_before", "expectation_after", "action_impulse_before", "action_impulse_after",
        )))

    plot_keys: set[tuple[str, str]] = set()
    source_p = {str(x.get("beat_id")): x for x in plot_ledger}
    for index, item in enumerate(plots, 1):
        label = f"plots[{index}]"
        require_fields(item, P_FIELDS, label, errors)
        key = (str(Path(item.get("source_path", "")).resolve()), str(item.get("source_beat_id")))
        if key in plot_keys:
            errors.append(f"{label} 来源路径 + P 拍 ID 重复")
        plot_keys.add(key)
        source = source_p.get(str(item.get("source_beat_id")), {})
        for snapshot_field, ledger_field in P_SOURCE_FIELD_MAP:
            if item.get(snapshot_field) != source.get(ledger_field):
                errors.append(
                    f"{label}.{snapshot_field} 必须逐字继承全文情节微拍总账的 {ledger_field}"
                )
        for field in P_EQUIVALENCE_REVIEW_FIELDS:
            if len(str(item.get(field) or "").strip()) < 12:
                errors.append(
                    f"{label}.{field} 过短；必须逐字段比较来源拍与目标拍，不能只凭 P 编号判定覆盖"
                )
        tokens = actor_tokens(item.get("actor"))
        if not tokens or any(not entity_label_valid(token) for token in tokens):
            errors.append(f"{label}.actor 必须是目标人物或现场组织，不能把时间、地点或整句事件当施事者")
        evidence = str(item.get("evidence") or "")
        if evidence not in outline:
            errors.append(f"{label}.evidence 不在当前细纲")
        if evidence in used_evidence["P"]:
            errors.append(f"{label}.evidence 与其他 P 拍重复")
        used_evidence["P"].add(evidence)
        actor_evidence = str(item.get("actor_evidence") or "")
        if not actor_resolves(item, declared_aliases):
            errors.append(f"{label}.actor_evidence 未点名施事者，或代词未由 action 解析为规范人物名")
        if any(x in evidence for x in CONSTRUCTION_MARKERS):
            errors.append(f"{label}.evidence 是施工说明")
        joined = "".join(str(item.get(x) or "") for x in P_FIELDS)
        if any(x in joined for x in GENERIC_MARKERS):
            generic["P"] += 1
    if generic["E"] >= max(3, len(emotions) // 3):
        errors.append("E 拍通用模板命中过多")
    if generic["P"] >= max(3, len(plots) // 3):
        errors.append("P 拍通用模板命中过多")
    for region, signatures in emotion_signatures.items():
        repeated = Counter(signatures).most_common(1)[0][1] if signatures else 0
        if len(signatures) >= 4 and repeated >= max(3, len(signatures) // 3):
            errors.append(f"{region} 大量 E 拍复用相同期待/行动前后态，必须逐拍裁决")

    if errors:
        print("semantic_beat_mapping: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("semantic_beat_mapping: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
