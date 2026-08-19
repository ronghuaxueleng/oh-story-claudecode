#!/usr/bin/env python3
"""Initialize and validate the single human review for a completed first draft."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-write.initial-draft-review.v2"
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
    return same_requirements and same_content and quotes_still_bound


def region_review_complete(review: dict[str, Any]) -> bool:
    base_fields = ("plot_complete", "emotion_complete", "scene_complete", "voice_match")
    if not all(review.get(field) is True for field in base_fields):
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


def refresh_receipt(receipt_path: Path) -> dict[str, Any]:
    current = read_json(receipt_path, "初稿终审回执")
    if current.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("只能刷新当前版本初稿终审回执")
    bindings = current.get("bindings") or {}
    refreshed = create_receipt(
        str(current.get("project") or "").strip(),
        Path(bindings["draft"]["path"]),
        Path(bindings["outline"]["path"]),
        Path(bindings["outline_contract"]["path"]),
        Path(bindings["project_config"]["path"]),
    )
    current_reviews = {
        str(item.get("region_id") or ""): item
        for item in current.get("region_reviews") or []
        if isinstance(item, dict)
    }
    preserved_fields = (
        "plot_complete",
        "emotion_complete",
        "scene_complete",
        "voice_match",
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
    old_global = current.get("global_review")
    bindings_unchanged = current.get("bindings") == refreshed.get("bindings")
    if bindings_unchanged and isinstance(old_global, dict):
        for field in refreshed["global_review"]:
            if field in old_global:
                refreshed["global_review"][field] = old_global[field]
    refreshed["summary"]["reviewed_regions"] = sum(
        1 for review in refreshed["region_reviews"] if region_review_complete(review)
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
            "p_replacement_refs",
            "hot_news_refs",
        ):
            if review.get(field) != expected_refs[region_id][field]:
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
            "all_hot_news_mechanisms_realized",
            "source_event_shell_rejected_globally",
            "news_fact_and_privacy_boundary_reviewed",
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
