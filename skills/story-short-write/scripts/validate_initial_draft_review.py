#!/usr/bin/env python3
"""Initialize and validate the single human review for a completed first draft."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-write.initial-draft-review.v5"
PREVIOUS_SCHEMA_VERSION = "story-short-write.initial-draft-review.v4"
LEGACY_SCHEMA_VERSIONS = {
    "story-short-write.initial-draft-review.v3",
    "story-short-write.initial-draft-review.v2",
}
SECTION_RE = re.compile(r"(?m)^(\d+)\.\s*$")
H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")


def _load_outline_module():
    path = Path(__file__).with_name("validate_outline_migration_contract.py")
    spec = importlib.util.spec_from_file_location("story_short_write_outline_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTLINE = _load_outline_module()
GRANULARITY_DIMENSIONS = tuple(OUTLINE.SOURCE_STYLE_GRANULARITY_FIELDS)


def _load_release_module():
    path = Path(__file__).with_name("validate_streamlined_write_release.py")
    spec = importlib.util.spec_from_file_location("story_short_write_release", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RELEASE = _load_release_module()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"文件不存在: {resolved}")
    return {"path": str(resolved), "sha256": sha256(resolved)}


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def nonspace_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_draft(text: str) -> tuple[str, dict[str, str], list[str]]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return text.strip(), {}, []
    opening = text[:matches[0].start()]
    opening = H1_RE.sub("", opening, count=1).strip()
    sections: dict[str, str] = {}
    order: list[str] = []
    for index, match in enumerate(matches):
        section_id = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[section_id] = text[match.end():end].strip()
        order.append(section_id)
    return opening, sections, order


def review_regions(draft_text: str) -> dict[str, str]:
    opening, sections, order = split_draft(draft_text)
    result = {"opening": opening}
    result.update({f"section:{section_id}": sections[section_id] for section_id in order})
    return result


def _target_region_map(contract: dict[str, Any]) -> dict[str, str]:
    return {
        beat["target_id"]: region["region_id"]
        for region in contract["outline_catalog"]["regions"]
        for beat in region["target_beats"]
    }


def _source_sequences(contract: dict[str, Any]) -> dict[str, Any]:
    config = Path(contract["project_config"]["path"])
    return OUTLINE.expected_sequences(OUTLINE.source_specs(config))


def required_refs_by_review_region(contract: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    regions = _target_region_map(contract)
    sequences = _source_sequences(contract)
    mapping = contract["mapping"]
    result: dict[str, dict[str, list[str]]] = {
        "opening": {
            "plot_refs": [],
            "emotion_refs": [],
            "auxiliary_plot_refs": [],
            "prose_subflow_refs": [],
            "p_replacement_refs": [],
            "hot_news_refs": [],
        }
    }
    for section in contract.get("sections") or []:
        result[f"section:{section['section_id']}"] = {
            "plot_refs": [],
            "emotion_refs": [],
            "auxiliary_plot_refs": [],
            "prose_subflow_refs": [],
            "p_replacement_refs": [],
            "hot_news_refs": [],
        }

    def review_region(target_id: str) -> str:
        region = regions.get(target_id, "")
        if region == "epilogue":
            numeric = [key for key in result if key.startswith("section:")]
            return numeric[-1] if numeric else region
        return region

    for ref, target in zip(sequences["primary_plot_refs"], mapping["primary_plot_targets"]):
        region = review_region(target)
        if region in result:
            result[region]["plot_refs"].append(ref)
    for ref, target in zip(sequences["primary_emotion_refs"], mapping["primary_emotion_targets"]):
        region = review_region(target)
        if region in result:
            result[region]["emotion_refs"].append(ref)
    for source_id, refs in sequences["auxiliary_plot_refs"].items():
        for ref, target in zip(refs, mapping["auxiliary_plot_targets"][source_id]):
            region = review_region(target)
            if region in result:
                result[region]["auxiliary_plot_refs"].append(ref)
    for item in contract.get("granularity_coverage") or []:
        source_ref = str(item.get("source_ref") or "").strip()
        for target_region in item.get("target_regions") or []:
            region = str(target_region)
            if region == "epilogue":
                numeric = [key for key in result if key.startswith("section:")]
                region = numeric[-1] if numeric else region
            if region in result and source_ref not in result[region]["prose_subflow_refs"]:
                result[region]["prose_subflow_refs"].append(source_ref)
    for item in contract.get("p_beat_replacements") or []:
        if not isinstance(item, dict):
            continue
        source_ref = str(item.get("source_ref") or "").strip()
        region = review_region(str(item.get("target_id") or "").strip())
        if region not in result:
            continue
        if source_ref and source_ref not in result[region]["p_replacement_refs"]:
            result[region]["p_replacement_refs"].append(source_ref)
        for news_id in item.get("news_ids") or []:
            normalized = str(news_id or "").strip()
            if normalized and normalized not in result[region]["hot_news_refs"]:
                result[region]["hot_news_refs"].append(normalized)
    return result


def required_granularity_reviews_by_region(
    contract: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Expand contract SF coverage into ordered, empty review slots."""
    result = {region_id: [] for region_id in required_refs_by_review_region(contract)}
    numeric_regions = [
        region_id for region_id in result if region_id.startswith("section:")
    ]
    for item in contract.get("granularity_coverage") or []:
        source_ref = str(item.get("source_ref") or "").strip()
        dimensions = item.get("style_dimensions")
        if not source_ref or dimensions != list(GRANULARITY_DIMENSIONS):
            raise ValueError(f"主体 SF {source_ref or '<missing>'} 的六维合同不完整")
        for target_region in item.get("target_regions") or []:
            region_id = str(target_region)
            if region_id == "epilogue":
                region_id = numeric_regions[-1] if numeric_regions else region_id
            if region_id not in result:
                continue
            if any(
                existing.get("source_ref") == source_ref
                for existing in result[region_id]
            ):
                continue
            result[region_id].append(
                {
                    "source_ref": source_ref,
                    "dimensions": {
                        dimension: {
                            "status": None,
                            "evidence_quote": "",
                            "adaptation_note": "",
                        }
                        for dimension in GRANULARITY_DIMENSIONS
                    },
                }
            )
    return result


def required_sf_chain_reviews(
    contract: dict[str, Any],
    review_region_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build one whole-chain review scaffold for every source SF."""
    if review_region_ids is None:
        review_region_ids = list(required_refs_by_review_region(contract))
    coverage_entries = contract.get("granularity_coverage") or []
    if not coverage_entries:
        return []
    numeric_regions = [
        region_id for region_id in review_region_ids if region_id.startswith("section:")
    ]
    last_numeric_region = numeric_regions[-1] if numeric_regions else ""
    bindings = {
        str(item.get("source_ref") or "").strip(): item
        for item in contract.get("sf_performance_bindings") or []
        if isinstance(item, dict)
    }
    target_region_by_id = _target_region_map(contract)

    def normalized_regions(values: Any) -> list[str]:
        result: list[str] = []
        for value in values or []:
            region_id = str(value or "").strip()
            if region_id == "epilogue" and last_numeric_region:
                region_id = last_numeric_region
            if region_id in review_region_ids and region_id not in result:
                result.append(region_id)
        return result

    def regions_for_targets(target_ids: Any) -> list[str]:
        return normalized_regions(
            [
                target_region_by_id.get(str(target_id or "").strip(), "")
                for target_id in target_ids
            ]
        )

    def review_item(
        requirement: str,
        target_ids: Any = None,
        evidence_regions: list[str] | None = None,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "source_requirement": requirement,
            "evidence_regions": (
                evidence_regions
                if evidence_regions is not None
                else regions_for_targets(target_ids or [])
            ),
            "status": None,
            "evidence_quote": "",
            "adaptation_note": "",
        }
        if target_ids is not None:
            item["target_ids"] = [str(value or "").strip() for value in target_ids]
        return item

    result: list[dict[str, Any]] = []
    for coverage in coverage_entries:
        if not isinstance(coverage, dict):
            raise ValueError("granularity_coverage 每项必须是对象")
        source_ref = str(coverage.get("source_ref") or "").strip()
        performance = coverage.get("performance_requirements")
        binding = bindings.get(source_ref)
        if not source_ref or not isinstance(performance, dict) or not isinstance(binding, dict):
            raise ValueError(f"主体 SF {source_ref or '<missing>'} 缺少完整表演链或目标绑定")
        required_sequence = performance.get("required_sequence")
        emotion_sequence = performance.get("emotion_sequence")
        required_targets = binding.get("required_sequence_target_ids")
        emotion_targets = binding.get("emotion_sequence_target_ids")
        if (
            not isinstance(required_sequence, list)
            or not isinstance(emotion_sequence, list)
            or not isinstance(required_targets, list)
            or not isinstance(emotion_targets, list)
            or len(required_sequence) != len(required_targets)
            or len(emotion_sequence) != len(emotion_targets)
            or any(not isinstance(group, list) or not group for group in required_targets)
            or any(not isinstance(group, list) or not group for group in emotion_targets)
            or not isinstance(binding.get("scene_granularity_target_ids"), list)
            or not binding.get("scene_granularity_target_ids")
        ):
            raise ValueError(f"主体 SF {source_ref} 的表演步骤与目标绑定不等长")
        target_regions = normalized_regions(coverage.get("target_regions"))
        if not target_regions:
            raise ValueError(f"主体 SF {source_ref} 没有可复核的正文区域")
        source_layers = coverage.get("source_layer_topology")
        layer_bindings = binding.get("source_layer_target_bindings")
        if (
            not isinstance(source_layers, list)
            or not source_layers
            or not isinstance(layer_bindings, list)
            or len(source_layers) != len(layer_bindings)
        ):
            raise ValueError(f"主体 SF {source_ref} 缺少逐层来源拓扑或目标绑定")
        source_layer_reviews: list[dict[str, Any]] = []
        for source_layer, layer_binding in zip(source_layers, layer_bindings):
            if (
                not isinstance(source_layer, dict)
                or not isinstance(layer_binding, dict)
                or source_layer.get("layer_id") != layer_binding.get("layer_id")
            ):
                raise ValueError(f"主体 SF {source_ref} 的逐层绑定与来源层不一致")
            target_ids = layer_binding.get("target_ids")
            if not isinstance(target_ids, list) or not target_ids:
                raise ValueError(f"主体 SF {source_ref} 的来源层未绑定目标细拍")
            source_layer_reviews.append(
                {
                    "layer_id": source_layer["layer_id"],
                    "source_layer": deepcopy(source_layer),
                    "target_ids": deepcopy(target_ids),
                    "evidence_regions": regions_for_targets(target_ids),
                    "status": None,
                    "evidence_quote": "",
                    "adaptation_note": "",
                }
            )
        result.append(
            {
                "source_ref": source_ref,
                "target_regions": target_regions,
                "entry_state_review": review_item(
                    str(performance.get("entry_state") or "").strip(),
                    evidence_regions=regions_for_targets(required_targets[0]),
                ),
                "required_sequence_reviews": [
                    review_item(str(requirement).strip(), target_ids)
                    for requirement, target_ids in zip(
                        required_sequence, required_targets
                    )
                ],
                "scene_granularity_review": review_item(
                    str(performance.get("scene_granularity") or "").strip(),
                    binding.get("scene_granularity_target_ids") or [],
                ),
                "emotion_sequence_reviews": [
                    review_item(str(requirement).strip(), target_ids)
                    for requirement, target_ids in zip(
                        emotion_sequence, emotion_targets
                    )
                ],
                "end_state_review": review_item(
                    str(performance.get("end_state") or "").strip(),
                    evidence_regions=regions_for_targets(required_targets[-1]),
                ),
                "source_layer_reviews": source_layer_reviews,
                "whole_chain_in_order": None,
                "whole_layer_topology_preserved": None,
                "technical_summary_rejected": None,
                "manual_judgment": "",
            }
        )
    return result


def validate_sf_chain_reviews(
    actual_entries: Any,
    expected_entries: list[dict[str, Any]],
    draft_regions: dict[str, str],
) -> list[str]:
    """Validate whole-SF realization instead of accepting unrelated region quotes."""
    errors: list[str] = []
    if not isinstance(actual_entries, list):
        return ["sf_chain_reviews 必须是列表"]
    expected_refs = [entry["source_ref"] for entry in expected_entries]
    actual_refs = [
        str(entry.get("source_ref") or "").strip()
        for entry in actual_entries
        if isinstance(entry, dict)
    ]
    if actual_refs != expected_refs:
        errors.append("sf_chain_reviews 必须与合同全部 SF 完整同序")

    def validate_item(
        actual: Any,
        expected: dict[str, Any],
        region_texts: dict[str, str],
        label: str,
    ) -> tuple[str, str, set[str]]:
        matched_regions: set[str] = set()
        if not isinstance(actual, dict):
            errors.append(f"{label} 必须是对象")
            return "", "", matched_regions
        if actual.get("source_requirement") != expected.get("source_requirement"):
            errors.append(f"{label}.source_requirement 必须与合同一致")
        if "target_ids" in expected and actual.get("target_ids") != expected.get("target_ids"):
            errors.append(f"{label}.target_ids 必须与写前 SF 绑定一致")
        if actual.get("evidence_regions") != expected.get("evidence_regions"):
            errors.append(f"{label}.evidence_regions 必须与目标细拍所在区域一致")
        if actual.get("status") != "realized":
            errors.append(f"{label}.status 必须为 realized")
        quote = str(actual.get("evidence_quote") or "").strip()
        allowed_regions = expected.get("evidence_regions") or []
        if quote:
            matched_regions = {
                region_id
                for region_id in allowed_regions
                if quote in region_texts.get(region_id, "")
            }
        if not quote or not matched_regions:
            errors.append(f"{label}.evidence_quote 必须逐字来自该 SF 的目标正文区域")
        note = str(actual.get("adaptation_note") or "").strip()
        if len(note) < 20:
            errors.append(f"{label}.adaptation_note 至少 20 字并说明该项如何换芯落地")
        return quote, note, matched_regions

    for expected, actual in zip(expected_entries, actual_entries):
        source_ref = expected["source_ref"]
        label = f"sf_chain_reviews[{source_ref}]"
        if not isinstance(actual, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if str(actual.get("source_ref") or "").strip() != source_ref:
            errors.append(f"{label}.source_ref 不得改写")
        target_regions = expected["target_regions"]
        if actual.get("target_regions") != target_regions:
            errors.append(f"{label}.target_regions 必须与合同落点一致")
        region_texts = {
            region_id: draft_regions.get(region_id, "") for region_id in target_regions
        }
        covered_regions: set[str] = set()
        all_notes: list[str] = []

        for field in (
            "entry_state_review",
            "scene_granularity_review",
            "end_state_review",
        ):
            _, note, matched = validate_item(
                actual.get(field), expected[field], region_texts, f"{label}.{field}"
            )
            all_notes.append(note)
            covered_regions.update(matched)

        for field in ("required_sequence_reviews", "emotion_sequence_reviews"):
            actual_items = actual.get(field)
            expected_items = expected[field]
            if not isinstance(actual_items, list) or len(actual_items) != len(expected_items):
                errors.append(f"{label}.{field} 必须与来源步骤等长")
                continue
            quotes: list[str] = []
            notes: list[str] = []
            for index, (actual_item, expected_item) in enumerate(
                zip(actual_items, expected_items), start=1
            ):
                quote, note, matched = validate_item(
                    actual_item,
                    expected_item,
                    region_texts,
                    f"{label}.{field}[{index}]",
                )
                quotes.append(quote)
                notes.append(note)
                all_notes.append(note)
                covered_regions.update(matched)
            if len(set(quotes)) != len(expected_items):
                errors.append(f"{label}.{field} 每个来源步骤必须分别取证，不得复用同一句")
            if len(set(notes)) != len(expected_items):
                errors.append(f"{label}.{field} 每个来源步骤必须使用专属说明")

        actual_layers = actual.get("source_layer_reviews")
        expected_layers = expected.get("source_layer_reviews")
        if not isinstance(actual_layers, list) or len(actual_layers) != len(
            expected_layers
        ):
            errors.append(f"{label}.source_layer_reviews 必须与来源层次完整同序")
        else:
            layer_quotes: list[str] = []
            layer_notes: list[str] = []
            for layer_index, (actual_layer, expected_layer) in enumerate(
                zip(actual_layers, expected_layers), start=1
            ):
                layer_label = f"{label}.source_layer_reviews[{layer_index}]"
                if not isinstance(actual_layer, dict):
                    errors.append(f"{layer_label} 必须是对象")
                    continue
                for field in (
                    "layer_id",
                    "source_layer",
                    "target_ids",
                    "evidence_regions",
                ):
                    if actual_layer.get(field) != expected_layer.get(field):
                        errors.append(f"{layer_label}.{field} 必须与写前来源层绑定一致")
                if actual_layer.get("status") != "realized":
                    errors.append(f"{layer_label}.status 必须为 realized")
                quote = str(actual_layer.get("evidence_quote") or "").strip()
                matched = {
                    region_id
                    for region_id in expected_layer.get("evidence_regions") or []
                    if quote and quote in region_texts.get(region_id, "")
                }
                if not matched:
                    errors.append(
                        f"{layer_label}.evidence_quote 必须逐字来自该来源层绑定的目标正文区域"
                    )
                covered_regions.update(matched)
                note = str(actual_layer.get("adaptation_note") or "").strip()
                if len(note) < 30:
                    errors.append(
                        f"{layer_label}.adaptation_note 至少 30 字，"
                        "必须说明层型、连接、叙述距离和六维协同如何保留"
                    )
                layer_quotes.append(quote)
                layer_notes.append(note)
                all_notes.append(note)
            if len(set(layer_quotes)) != len(expected_layers):
                errors.append(f"{label}.source_layer_reviews 每层必须分别取证")
            if len(set(layer_notes)) != len(expected_layers):
                errors.append(f"{label}.source_layer_reviews 每层必须使用专属说明")

        if len(set(all_notes)) != len(all_notes):
            errors.append(f"{label} 各表演要求的 adaptation_note 不得复用模板")
        if not set(target_regions).issubset(covered_regions):
            missing_regions = [
                region_id for region_id in target_regions if region_id not in covered_regions
            ]
            errors.append(f"{label} 的整链证据未覆盖全部跨区落点: {missing_regions}")
        if actual.get("whole_chain_in_order") is not True:
            errors.append(f"{label}.whole_chain_in_order 必须为 true")
        if actual.get("whole_layer_topology_preserved") is not True:
            errors.append(f"{label}.whole_layer_topology_preserved 必须为 true")
        if actual.get("technical_summary_rejected") is not True:
            errors.append(f"{label}.technical_summary_rejected 必须为 true")
        if len(str(actual.get("manual_judgment") or "").strip()) < 40:
            errors.append(f"{label}.manual_judgment 至少 40 字并说明整链连续性")
    return errors


def create_receipt(
    project: str,
    draft_path: Path,
    outline_path: Path,
    outline_contract_path: Path,
    project_config_path: Path,
) -> dict[str, Any]:
    contract = read_json(outline_contract_path, "细纲迁移合同")
    outline_errors = OUTLINE.validate_receipt(outline_contract_path, outline_path)
    if outline_errors or contract.get("gate_status") != "passed":
        raise ValueError("细纲迁移合同未通过: " + "；".join(outline_errors))
    draft_text = draft_path.read_text(encoding="utf-8")
    primary_original = Path(contract["sources"][0]["original"]["path"]).resolve()
    length_errors = RELEASE.validate_source_anchored_draft(
        draft_text,
        primary_original,
        read_json(project_config_path, "项目写作配置"),
    )
    if length_errors:
        raise ValueError("；".join(length_errors))
    regions = review_regions(draft_text)
    required = required_refs_by_review_region(contract)
    required_granularity = required_granularity_reviews_by_region(contract)
    required_sf_chains = required_sf_chain_reviews(contract, list(required))
    if list(regions) != list(required):
        raise ValueError(f"正文分节与细纲不一致: draft={list(regions)}, expected={list(required)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "created_at": now_iso(),
        "gate_status": "pending",
        "bindings": {
            "draft": binding(draft_path),
            "outline": binding(outline_path),
            "outline_contract": binding(outline_contract_path),
            "project_config": binding(project_config_path),
        },
        "region_reviews": [
            {
                "region_id": region_id,
                "content_sha256": text_sha256(regions[region_id]),
                **required[region_id],
                "granularity_dimension_reviews": required_granularity[region_id],
                "plot_complete": None,
                "emotion_complete": None,
                "scene_complete": None,
                "voice_match": None,
                "p_replacements_realized": None,
                "source_event_shell_rejected": None,
                "hot_news_mechanisms_realized": None,
                "evidence_quotes": [],
                "hot_news_evidence_quotes": [],
                "manual_judgment": "",
            }
            for region_id in required
        ],
        "sf_chain_reviews": required_sf_chains,
        "global_review": {
            "primary_voice_exclusive": None,
            "auxiliary_voice_rejected": None,
            "title_promise_fulfilled": None,
            "opening_bearing_passed": None,
            "ending_consequence_passed": None,
            "long_sentence_breath_reviewed": None,
            "dialogue_efficiency_reviewed": None,
            "all_primary_prose_subflows_covered": None,
            "full_story_hierarchy_preserved": None,
            "all_primary_p_beats_replaced": None,
            "all_hot_news_mechanisms_realized": None,
            "source_event_shell_rejected_globally": None,
            "news_fact_and_privacy_boundary_reviewed": None,
            "source_voice_quotes": [],
            "draft_voice_quotes": [],
            "voice_comparison": "",
            "final_judgment": "",
        },
        "summary": {
            "draft_nonspace_chars": nonspace_count(draft_text),
            "reviewed_regions": 0,
            "reviewed_granularity_dimensions": 0,
            "reviewed_sf_chains": 0,
        },
        "blocking_failures": [],
    }


def can_preserve_region_review(
    old_review: dict[str, Any],
    refreshed_review: dict[str, Any],
    region_text: str,
) -> bool:
    reference_fields = (
        "plot_refs",
        "emotion_refs",
        "auxiliary_plot_refs",
        "prose_subflow_refs",
        "p_replacement_refs",
        "hot_news_refs",
    )
    same_requirements = all(
        old_review.get(field) == refreshed_review.get(field)
        for field in reference_fields
    )
    old_granularity_refs = [
        str(item.get("source_ref") or "")
        for item in old_review.get("granularity_dimension_reviews") or []
        if isinstance(item, dict)
    ]
    refreshed_granularity_refs = [
        str(item.get("source_ref") or "")
        for item in refreshed_review.get("granularity_dimension_reviews") or []
        if isinstance(item, dict)
    ]
    same_requirements = (
        same_requirements
        and old_granularity_refs == refreshed_granularity_refs
        and granularity_reviews_complete(old_review)
    )
    same_content = (
        bool(old_review.get("content_sha256"))
        and old_review.get("content_sha256") == refreshed_review.get("content_sha256")
        and refreshed_review.get("content_sha256") == text_sha256(region_text)
    )
    quotes = old_review.get("evidence_quotes")
    quotes_still_bound = (
        isinstance(quotes, list)
        and len(quotes) >= 1
        and all(
            isinstance(quote, str)
            and quote.strip()
            and quote in region_text
            for quote in quotes
        )
    )
    granularity_quotes_still_bound = all(
        str(dimension_item.get("evidence_quote") or "").strip() in region_text
        for item in old_review.get("granularity_dimension_reviews") or []
        if isinstance(item, dict)
        for dimension_item in (item.get("dimensions") or {}).values()
        if isinstance(dimension_item, dict)
    )
    return (
        same_requirements
        and same_content
        and quotes_still_bound
        and granularity_quotes_still_bound
    )


def granularity_reviews_complete(review: dict[str, Any]) -> bool:
    entries = review.get("granularity_dimension_reviews")
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        dimensions = entry.get("dimensions")
        if not isinstance(dimensions, dict) or set(dimensions) != set(GRANULARITY_DIMENSIONS):
            return False
        for dimension in GRANULARITY_DIMENSIONS:
            item = dimensions.get(dimension)
            if not isinstance(item, dict):
                return False
            if item.get("status") != "realized":
                return False
            if not str(item.get("evidence_quote") or "").strip():
                return False
            if len(str(item.get("adaptation_note") or "").strip()) < 20:
                return False
    return True


def validate_granularity_dimension_reviews(
    actual_entries: Any,
    expected_entries: list[dict[str, Any]],
    region_text: str,
    label: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(actual_entries, list):
        return [f"{label} 必须是列表"]
    expected_refs = [str(item.get("source_ref") or "") for item in expected_entries]
    actual_refs = [
        str(item.get("source_ref") or "")
        for item in actual_entries
        if isinstance(item, dict)
    ]
    if actual_refs != expected_refs:
        errors.append(f"{label} 的 SF 必须与合同完整同序")
    for expected_entry, actual_entry in zip(expected_entries, actual_entries):
        if not isinstance(actual_entry, dict):
            errors.append(f"{label} 每个 SF 必须是对象")
            continue
        source_ref = str(expected_entry.get("source_ref") or "")
        dimensions = actual_entry.get("dimensions")
        if not isinstance(dimensions, dict) or set(dimensions) != set(GRANULARITY_DIMENSIONS):
            errors.append(f"{label}[{source_ref}] 必须完整包含六维且不得增删 key")
            continue
        dimension_quotes: list[str] = []
        dimension_notes: list[str] = []
        for dimension in GRANULARITY_DIMENSIONS:
            dimension_item = dimensions.get(dimension)
            dimension_label = f"{label}[{source_ref}].{dimension}"
            if not isinstance(dimension_item, dict):
                errors.append(f"{dimension_label} 必须是对象")
                continue
            if dimension_item.get("status") != "realized":
                errors.append(f"{dimension_label}.status 必须为 realized")
            evidence_quote = str(dimension_item.get("evidence_quote") or "").strip()
            dimension_quotes.append(evidence_quote)
            if not evidence_quote or evidence_quote not in region_text:
                errors.append(f"{dimension_label}.evidence_quote 必须逐字来自当前正文区域")
            adaptation_note = str(dimension_item.get("adaptation_note") or "").strip()
            dimension_notes.append(adaptation_note)
            if len(adaptation_note) < 20:
                errors.append(f"{dimension_label}.adaptation_note 至少 20 字")
        if len(set(dimension_quotes)) != len(GRANULARITY_DIMENSIONS):
            errors.append(f"{label}[{source_ref}] 六维 evidence_quote 必须分别取证，不得复用同一句")
        if len(set(dimension_notes)) != len(GRANULARITY_DIMENSIONS):
            errors.append(f"{label}[{source_ref}] 六维 adaptation_note 必须维度专属，不得复用模板")
    return errors


def region_review_complete(review: dict[str, Any]) -> bool:
    base_fields = ("plot_complete", "emotion_complete", "scene_complete", "voice_match")
    if not all(review.get(field) is True for field in base_fields):
        return False
    if not granularity_reviews_complete(review):
        return False
    if review.get("p_replacement_refs"):
        if review.get("p_replacements_realized") is not True:
            return False
        if review.get("source_event_shell_rejected") is not True:
            return False
    if review.get("hot_news_refs"):
        if review.get("hot_news_mechanisms_realized") is not True:
            return False
    return True


def sf_chain_review_complete(
    review: dict[str, Any],
    expected: dict[str, Any],
    draft_regions: dict[str, str],
) -> bool:
    return not validate_sf_chain_reviews([review], [expected], draft_regions)


def refresh_receipt(receipt_path: Path) -> dict[str, Any]:
    current = read_json(receipt_path, "初稿终审回执")
    current_schema = current.get("schema_version")
    supported_schemas = {
        SCHEMA_VERSION,
        PREVIOUS_SCHEMA_VERSION,
        *LEGACY_SCHEMA_VERSIONS,
    }
    if current_schema not in supported_schemas:
        raise ValueError("只能刷新当前或受支持旧版本的初稿终审回执")
    bindings = current.get("bindings") or {}
    refreshed = create_receipt(
        str(current.get("project") or "").strip(),
        Path(bindings["draft"]["path"]),
        Path(bindings["outline"]["path"]),
        Path(bindings["outline_contract"]["path"]),
        Path(bindings["project_config"]["path"]),
    )
    expected_sf_chains = deepcopy(refreshed["sf_chain_reviews"])
    current_reviews = {
        str(item.get("region_id") or ""): item
        for item in current.get("region_reviews") or []
        if isinstance(item, dict)
    } if current_schema in {SCHEMA_VERSION, PREVIOUS_SCHEMA_VERSION} else {}
    preserved_fields = (
        "plot_complete",
        "emotion_complete",
        "scene_complete",
        "voice_match",
        "granularity_dimension_reviews",
        "p_replacements_realized",
        "source_event_shell_rejected",
        "hot_news_mechanisms_realized",
        "evidence_quotes",
        "hot_news_evidence_quotes",
        "manual_judgment",
    )
    refreshed_regions = review_regions(
        Path(refreshed["bindings"]["draft"]["path"]).read_text(encoding="utf-8")
    )
    for review in refreshed["region_reviews"]:
        old = current_reviews.get(review["region_id"]) or {}
        region_text = refreshed_regions.get(review["region_id"], "")
        if can_preserve_region_review(old, review, region_text):
            for field in preserved_fields:
                if field in old:
                    review[field] = old[field]
    current_sf_chains = {
        str(item.get("source_ref") or "").strip(): item
        for item in current.get("sf_chain_reviews") or []
        if isinstance(item, dict)
    } if current_schema == SCHEMA_VERSION else {}
    for index, review in enumerate(refreshed["sf_chain_reviews"]):
        old = current_sf_chains.get(review["source_ref"])
        if isinstance(old, dict) and sf_chain_review_complete(
            old, review, refreshed_regions
        ):
            refreshed["sf_chain_reviews"][index] = deepcopy(old)
    old_global = current.get("global_review")
    bindings_unchanged = current.get("bindings") == refreshed.get("bindings")
    if (
        current_schema in {SCHEMA_VERSION, PREVIOUS_SCHEMA_VERSION}
        and bindings_unchanged
        and isinstance(old_global, dict)
    ):
        for field in refreshed["global_review"]:
            if field in old_global:
                refreshed["global_review"][field] = old_global[field]
    refreshed["summary"]["reviewed_regions"] = sum(
        1 for review in refreshed["region_reviews"] if region_review_complete(review)
    )
    refreshed["summary"]["reviewed_granularity_dimensions"] = sum(
        1
        for review in refreshed["region_reviews"]
        for entry in review.get("granularity_dimension_reviews") or []
        if isinstance(entry, dict)
        for dimension in GRANULARITY_DIMENSIONS
        if isinstance(entry.get("dimensions"), dict)
        and isinstance(entry["dimensions"].get(dimension), dict)
        and entry["dimensions"][dimension].get("status") == "realized"
    )
    refreshed["summary"]["reviewed_sf_chains"] = sum(
        1
        for review, expected in zip(
            refreshed["sf_chain_reviews"],
            expected_sf_chains,
        )
        if sf_chain_review_complete(review, expected, refreshed_regions)
    )
    refreshed["refreshed_at"] = now_iso()
    write_json(receipt_path, refreshed)
    return refreshed


def _validate_binding(item: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(item, dict):
        errors.append(f"{label}绑定缺失")
        return None
    path = Path(str(item.get("path") or "")).resolve()
    if not path.is_file():
        errors.append(f"{label}不存在: {path}")
        return None
    if item.get("sha256") != sha256(path):
        errors.append(f"{label} SHA 已失效")
    return path


def validate_data(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") == PREVIOUS_SCHEMA_VERSION:
        return ["旧 v4 回执缺少逐来源层正文证据；请运行 refresh-derived 升级后回填"]
    if data.get("schema_version") in LEGACY_SCHEMA_VERSIONS:
        return ["旧回执缺少逐来源层、逐 SF 六维与完整表演链正文证据；请运行 refresh-derived 升级后重新回填"]
    if data.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version 必须为 {SCHEMA_VERSION}"]
    bindings = data.get("bindings") or {}
    draft_path = _validate_binding(bindings.get("draft"), "正文", errors)
    outline_path = _validate_binding(bindings.get("outline"), "小节大纲", errors)
    contract_path = _validate_binding(bindings.get("outline_contract"), "细纲迁移合同", errors)
    config_path = _validate_binding(bindings.get("project_config"), "项目写作配置", errors)
    if not all((draft_path, outline_path, contract_path, config_path)):
        return errors
    contract = read_json(contract_path, "细纲迁移合同")
    errors.extend(OUTLINE.validate_receipt(contract_path, outline_path))
    if contract.get("gate_status") != "passed":
        errors.append("细纲迁移合同 gate_status 未 passed")
    draft_text = draft_path.read_text(encoding="utf-8")
    primary_original = Path(contract["sources"][0]["original"]["path"]).resolve()
    errors.extend(
        RELEASE.validate_source_anchored_draft(
            draft_text,
            primary_original,
            read_json(config_path, "项目写作配置"),
        )
    )
    regions = review_regions(draft_text)
    expected_refs = required_refs_by_review_region(contract)
    expected_granularity = required_granularity_reviews_by_region(contract)
    expected_sf_chains = required_sf_chain_reviews(contract, list(expected_refs))
    expected_ids = list(expected_refs)
    actual_ids = [str(item.get("region_id") or "") for item in data.get("region_reviews") or [] if isinstance(item, dict)]
    if actual_ids != expected_ids:
        errors.append(f"region_reviews 必须与正文区域完整同序: expected={expected_ids}, actual={actual_ids}")
    review_by_id = {
        str(item.get("region_id") or ""): item
        for item in data.get("region_reviews") or []
        if isinstance(item, dict)
    }
    for region_id in expected_ids:
        review = review_by_id.get(region_id) or {}
        label = f"region_reviews.{region_id}"
        if review.get("content_sha256") != text_sha256(regions.get(region_id, "")):
            errors.append(f"{label}.content_sha256 与当前正文区域不一致")
        for field in (
            "plot_refs",
            "emotion_refs",
            "auxiliary_plot_refs",
            "prose_subflow_refs",
            "granularity_dimension_reviews",
            "p_replacement_refs",
            "hot_news_refs",
        ):
            expected_value = (
                expected_granularity[region_id]
                if field == "granularity_dimension_reviews"
                else expected_refs[region_id][field]
            )
            if field == "granularity_dimension_reviews":
                errors.extend(
                    validate_granularity_dimension_reviews(
                        review.get(field),
                        expected_value,
                        regions.get(region_id, ""),
                        f"{label}.{field}",
                    )
                )
                continue
            if review.get(field) != expected_value:
                errors.append(f"{label}.{field} 不得改写或漏拍")
        for field in ("plot_complete", "emotion_complete", "scene_complete", "voice_match"):
            if review.get(field) is not True:
                errors.append(f"{label}.{field} 必须为 true")
        if review.get("p_replacement_refs"):
            if review.get("p_replacements_realized") is not True:
                errors.append(f"{label}.p_replacements_realized 必须为 true")
            if review.get("source_event_shell_rejected") is not True:
                errors.append(f"{label}.source_event_shell_rejected 必须为 true")
        if review.get("hot_news_refs"):
            if review.get("hot_news_mechanisms_realized") is not True:
                errors.append(f"{label}.hot_news_mechanisms_realized 必须为 true")
        quotes = review.get("evidence_quotes")
        region_text = regions.get(region_id, "")
        if not isinstance(quotes, list) or len(quotes) < 1:
            errors.append(f"{label}.evidence_quotes 至少一条")
        elif any(not isinstance(quote, str) or not quote.strip() or quote not in region_text for quote in quotes):
            errors.append(f"{label}.evidence_quotes 必须来自当前正文区域")
        news_quotes = review.get("hot_news_evidence_quotes")
        if review.get("hot_news_refs"):
            if not isinstance(news_quotes, list) or len(news_quotes) < 1:
                errors.append(f"{label}.hot_news_evidence_quotes 至少一条")
            elif any(
                not isinstance(quote, str)
                or not quote.strip()
                or quote not in region_text
                for quote in news_quotes
            ):
                errors.append(f"{label}.hot_news_evidence_quotes 必须来自当前正文区域")
        if len(str(review.get("manual_judgment") or "").strip()) < 30:
            errors.append(f"{label}.manual_judgment 至少 30 字")

    errors.extend(
        validate_sf_chain_reviews(
            data.get("sf_chain_reviews"), expected_sf_chains, regions
        )
    )

    global_review = data.get("global_review")
    if not isinstance(global_review, dict):
        errors.append("global_review 必须是对象")
    else:
        for field in (
            "primary_voice_exclusive",
            "auxiliary_voice_rejected",
            "title_promise_fulfilled",
            "opening_bearing_passed",
            "ending_consequence_passed",
            "long_sentence_breath_reviewed",
            "dialogue_efficiency_reviewed",
            "all_primary_prose_subflows_covered",
            "full_story_hierarchy_preserved",
            "all_primary_p_beats_replaced",
            "source_event_shell_rejected_globally",
        ):
            if global_review.get(field) is not True:
                errors.append(f"global_review.{field} 必须为 true")
        expected_subflows = [
            item["source_ref"] for item in contract.get("granularity_coverage") or []
        ]
        reviewed_subflows = {
            ref
            for review in review_by_id.values()
            for ref in review.get("prose_subflow_refs") or []
        }
        if reviewed_subflows != set(expected_subflows):
            errors.append("region_reviews 必须覆盖主体全部文字子流程")
        reviewed_chain_refs = [
            str(item.get("source_ref") or "").strip()
            for item in data.get("sf_chain_reviews") or []
            if isinstance(item, dict)
        ]
        if reviewed_chain_refs != expected_subflows:
            errors.append("sf_chain_reviews 必须逐项覆盖主体全部文字子流程")
        expected_dimension_count = sum(
            len(entries) for entries in expected_granularity.values()
        ) * len(GRANULARITY_DIMENSIONS)
        reviewed_dimension_count = 0
        for review in review_by_id.values():
            for entry in review.get("granularity_dimension_reviews") or []:
                dimensions = entry.get("dimensions") if isinstance(entry, dict) else None
                if isinstance(dimensions, dict):
                    reviewed_dimension_count += sum(
                        1
                        for dimension in GRANULARITY_DIMENSIONS
                        if isinstance(dimensions.get(dimension), dict)
                        and dimensions[dimension].get("status") == "realized"
                    )
        if reviewed_dimension_count != expected_dimension_count:
            errors.append("region_reviews 必须逐项完成主体全部 SF 六维颗粒")
        expected_replacements = {
            str(item.get("source_ref") or "").strip()
            for item in contract.get("p_beat_replacements") or []
            if isinstance(item, dict)
        }
        reviewed_replacements = {
            ref
            for review in review_by_id.values()
            for ref in review.get("p_replacement_refs") or []
        }
        if reviewed_replacements != expected_replacements:
            errors.append("region_reviews 必须覆盖主体全部 P 拍替换")
        expected_news = {
            str(item.get("news_id") or "").strip()
            for item in contract.get("hot_news_materials") or []
            if isinstance(item, dict)
        }
        reviewed_news = {
            ref
            for review in review_by_id.values()
            for ref in review.get("hot_news_refs") or []
        }
        if reviewed_news != expected_news:
            errors.append("region_reviews 必须覆盖全部已选热点新闻机制")
        if expected_news:
            for field in (
                "all_hot_news_mechanisms_realized",
                "news_fact_and_privacy_boundary_reviewed",
            ):
                if global_review.get(field) is not True:
                    errors.append(f"global_review.{field} 必须为 true")
        primary_source = Path(contract["sources"][0]["original"]["path"]).read_text(encoding="utf-8")
        source_quotes = global_review.get("source_voice_quotes")
        if not isinstance(source_quotes, list) or len(source_quotes) < 3:
            errors.append("global_review.source_voice_quotes 至少三条主体原文引句")
        elif any(not isinstance(quote, str) or quote not in primary_source for quote in source_quotes):
            errors.append("global_review.source_voice_quotes 必须逐字来自主体原文")
        draft_quotes = global_review.get("draft_voice_quotes")
        if not isinstance(draft_quotes, list) or len(draft_quotes) < 3:
            errors.append("global_review.draft_voice_quotes 至少三条正文引句")
        elif any(not isinstance(quote, str) or quote not in draft_text for quote in draft_quotes):
            errors.append("global_review.draft_voice_quotes 必须逐字来自最终正文")
        if len(str(global_review.get("voice_comparison") or "").strip()) < 60:
            errors.append("global_review.voice_comparison 至少 60 字")
        if len(str(global_review.get("final_judgment") or "").strip()) < 60:
            errors.append("global_review.final_judgment 至少 60 字")

    h1 = H1_RE.search(draft_text)
    expected_title = str(data.get("project") or "").strip()
    actual_title = (h1.group(1).strip().strip("《》") if h1 else "")
    if actual_title != expected_title:
        errors.append(f"正文 H1 书名必须为《{expected_title}》")
    _, _, order = split_draft(draft_text)
    expected_order = [key.split(":", 1)[1] for key in expected_ids if key.startswith("section:")]
    if order != expected_order:
        errors.append(f"正文数字分节必须连续完整: expected={expected_order}, actual={order}")
    summary = data.get("summary") or {}
    if summary.get("draft_nonspace_chars") != nonspace_count(draft_text):
        errors.append("summary.draft_nonspace_chars 与最终正文不一致")
    if summary.get("reviewed_regions") != len(expected_ids):
        errors.append("summary.reviewed_regions 必须等于全部区域数")
    expected_dimension_count = sum(
        len(entries) for entries in expected_granularity.values()
    ) * len(GRANULARITY_DIMENSIONS)
    if summary.get("reviewed_granularity_dimensions") != expected_dimension_count:
        errors.append("summary.reviewed_granularity_dimensions 必须等于全部 SF 区域落点数乘六")
    if summary.get("reviewed_sf_chains") != len(expected_sf_chains):
        errors.append("summary.reviewed_sf_chains 必须等于主体全部 SF 数量")
    return errors


def validate_receipt(receipt_path: Path) -> list[str]:
    return validate_data(read_json(receipt_path, "初稿终审回执"))


def seal_receipt(receipt_path: Path) -> dict[str, Any]:
    data = read_json(receipt_path, "初稿终审回执")
    data["gate_status"] = "pending"
    data["blocking_failures"] = []
    errors = validate_data(data)
    if errors:
        data["blocking_failures"] = errors
        write_json(receipt_path, data)
        raise ValueError("；".join(errors))
    data["gate_status"] = "passed"
    data["reviewed_at"] = now_iso()
    write_json(receipt_path, data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--draft", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--outline-contract", required=True)
    init.add_argument("--project-config", required=True)
    init.add_argument("--receipt", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    refresh = sub.add_parser("refresh-derived")
    refresh.add_argument("--receipt", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            receipt = Path(args.receipt).resolve()
            if receipt.exists():
                raise ValueError(f"初稿终审回执已存在，拒绝覆盖: {receipt}")
            write_json(
                receipt,
                create_receipt(
                    args.project,
                    Path(args.draft).resolve(),
                    Path(args.outline).resolve(),
                    Path(args.outline_contract).resolve(),
                    Path(args.project_config).resolve(),
                ),
            )
            print("initial_draft_review: initialized")
            return 0
        if args.command == "seal":
            seal_receipt(Path(args.receipt).resolve())
            print("initial_draft_review: passed")
            return 0
        if args.command == "refresh-derived":
            refresh_receipt(Path(args.receipt).resolve())
            print("initial_draft_review: refreshed")
            return 0
        errors = validate_receipt(Path(args.receipt).resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("initial_draft_review: blocked")
        print(f"- {exc}")
        return 2
    if errors:
        print("initial_draft_review: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("initial_draft_review: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
