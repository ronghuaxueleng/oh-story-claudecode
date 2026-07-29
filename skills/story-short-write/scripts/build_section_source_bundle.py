#!/usr/bin/env python3
"""Build a per-section source granularity bundle from the passed outline contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

REQUIRED_STYLE_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
MAX_SOURCE_SLICE_LINES = 35

STYLE_REFERENCE_FILENAMES = (
    "角色口气模板.md",
    "可直接仿写_对话衔接表.md",
    "可直接仿写_失控说话表.md",
    "可直接仿写_安静压迫场表.md",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=512)
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=512)
def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


@lru_cache(maxsize=1024)
def source_excerpt(path: Path, source_range: str) -> str:
    """Return the exact line ranges bound to one source slice."""
    lines = read_text(path).splitlines()
    ranges = re.findall(r"L(\d+)-L(\d+)", source_range)
    if not ranges:
        raise ValueError(f"非法 source_range: {source_range!r}")
    excerpts: list[str] = []
    for raw_start, raw_end in ranges:
        start, end = int(raw_start), int(raw_end)
        if start < 1 or end < start or end > len(lines):
            raise ValueError(f"source_range 越界: L{start}-L{end}，原文共 {len(lines)} 行")
        excerpts.append("\n".join(lines[start - 1 : end]))
    return "\n".join(excerpts)


@lru_cache(maxsize=256)
def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def discover_book_root_from_source(source_path: Path) -> Path | None:
    resolved = source_path.expanduser().resolve()
    for parent in (resolved.parent, *resolved.parents):
        if (parent / "book.profile.json").is_file():
            return parent
    return None


@lru_cache(maxsize=64)
def load_style_reference_assets(book_root: Path) -> dict[str, Any]:
    assets_dir = book_root / "写作资产"
    result: dict[str, Any] = {
        "book_root": str(book_root),
        "style_assets": {},
        "style_assets_source": {},
        "voice_references": [],
    }
    compile_pkg = assets_dir / "仿写无损编译包.json"
    if compile_pkg.is_file():
        try:
            compile_data = read_json(compile_pkg)
        except Exception:
            compile_data = {}
        profile_assets = compile_data.get("profile_assets") if isinstance(compile_data, dict) else {}
        style_assets = profile_assets.get("style_assets") if isinstance(profile_assets, dict) else {}
        if isinstance(style_assets, dict):
            result["style_assets"] = style_assets
            result["style_assets_source"] = {
                "path": str(compile_pkg),
                "sha256": sha256(compile_pkg),
            }
    if not result["style_assets"]:
        profile_path = book_root / "book.profile.json"
        if profile_path.is_file():
            try:
                profile_data = read_json(profile_path)
            except Exception:
                profile_data = {}
            style_assets = profile_data.get("style_assets") if isinstance(profile_data, dict) else {}
            if isinstance(style_assets, dict):
                result["style_assets"] = style_assets
                result["style_assets_source"] = {
                    "path": str(profile_path),
                    "sha256": sha256(profile_path),
                }
    for filename in STYLE_REFERENCE_FILENAMES:
        path = assets_dir / filename
        if path.is_file():
            result["voice_references"].append(
                {
                    "path": str(path),
                    "sha256": sha256(path),
                    "text": read_text(path),
                }
            )
    return result


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def parse_source_range_segments(source_range: str) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    for raw_start, raw_end in re.findall(r"L(\d+)-L(\d+)", source_range):
        segments.append((int(raw_start), int(raw_end)))
    return segments


def collect_selected_subflow_coverage(
    source_receipt: dict[str, Any],
) -> dict[Path, dict[str, Any]]:
    coverage: dict[Path, dict[str, Any]] = {}
    for source in source_receipt.get("sources", []):
        if not isinstance(source, dict):
            continue
        root_text = str(source.get("root") or "").strip()
        if not root_text:
            continue
        root = Path(root_text).expanduser().resolve()
        contracts = source.get("selected_subflow_contracts")
        if not isinstance(contracts, list):
            continue
        segments: list[tuple[int, int, str]] = []
        for contract in contracts:
            if not isinstance(contract, dict):
                continue
            subflow_id = str(contract.get("subflow_id") or "").strip() or "UNKNOWN-SF"
            for start, end in parse_source_range_segments(str(contract.get("source_range") or "")):
                segments.append((start, end, subflow_id))
        coverage[root] = {
            "name": str(source.get("name") or root.name),
            "role": str(source.get("role") or ""),
            "segments": segments,
        }
    return coverage


def find_uncovered_binding_segments(
    binding_range: str,
    covered_segments: list[tuple[int, int, str]],
) -> list[tuple[int, int]]:
    uncovered: list[tuple[int, int]] = []
    for binding_start, binding_end in parse_source_range_segments(binding_range):
        cursor = binding_start
        overlapping = sorted(
            (
                (start, end)
                for start, end, _subflow_id in covered_segments
                if end >= binding_start and start <= binding_end
            ),
            key=lambda item: (item[0], item[1]),
        )
        for start, end in overlapping:
            if end < cursor:
                continue
            if start > cursor:
                uncovered.append((cursor, min(binding_end, start - 1)))
            cursor = max(cursor, end + 1)
            if cursor > binding_end:
                break
        if cursor <= binding_end:
            uncovered.append((cursor, binding_end))
    return uncovered


def format_segments(segments: list[tuple[int, int]]) -> str:
    return "、".join(f"L{start}-L{end}" for start, end in segments)


def validate_style_reference_assets(
    assets: Any,
    section_id: str,
    errors: list[str],
) -> None:
    if not isinstance(assets, list) or not assets:
        errors.append(f"第 {section_id} 节颗粒包缺少 source_style_reference_assets")
        return
    for index, asset in enumerate(assets, start=1):
        label = f"第 {section_id} 节 source_style_reference_assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if not _nonempty_dict(asset.get("style_assets")):
            errors.append(f"{label}.style_assets 不能为空")
        source = asset.get("style_assets_source")
        if not isinstance(source, dict) or not _nonempty_text(source.get("path")) or not _nonempty_text(source.get("sha256")):
            errors.append(f"{label}.style_assets_source 必须绑定路径和 SHA")
        references = asset.get("voice_references")
        if not isinstance(references, list) or not references:
            errors.append(f"{label}.voice_references 不能为空")
            continue
        for ref_index, reference in enumerate(references, start=1):
            ref_label = f"{label}.voice_references[{ref_index}]"
            if not isinstance(reference, dict):
                errors.append(f"{ref_label} 必须是对象")
                continue
            for field in ("path", "sha256", "text"):
                if not _nonempty_text(reference.get(field)):
                    errors.append(f"{ref_label}.{field} 不能为空")


def validate_style_granularity(
    value: Any,
    section_id: str,
    source_excerpts: list[str],
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"第 {section_id} 节颗粒包缺少 source_style_granularity")
        return
    for style_field in REQUIRED_STYLE_FIELDS:
        item = value.get(style_field)
        label = f"第 {section_id} 节 source_style_granularity.{style_field}"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if not _nonempty_text(item.get("source_summary")):
            errors.append(f"{label}.source_summary 不能为空")
        if not _nonempty_text(item.get("target_style_plan")):
            errors.append(f"{label}.target_style_plan 不能为空")
        evidence = item.get("source_evidence")
        if not _nonempty_list(evidence):
            errors.append(f"{label}.source_evidence 至少需要 1 条")
            continue
        for quote in evidence:
            if not any(str(quote) in excerpt for excerpt in source_excerpts):
                errors.append(f"{label}.source_evidence 不在本节原文切片内: {quote}")


def validate_bundle_inputs(outline_contract: Path, source_receipt: Path) -> list[str]:
    errors: list[str] = []
    try:
        outline = read_json(outline_contract)
    except Exception as exc:
        return [f"细纲表演验收回执不可读取: {exc}"]
    try:
        source = read_json(source_receipt)
    except Exception as exc:
        return [f"拆文读取回执不可读取: {exc}"]
    if outline.get("gate_status") != "passed":
        errors.append("细纲表演验收回执必须先通过")
    if source.get("gate_status") != "passed":
        errors.append("拆文读取回执必须先通过")
    if str(source.get("writing_mode") or "") != "direct_imitation":
        errors.append("逐节原文颗粒包只允许 direct_imitation 模式")
    return errors


def create_bundle(outline_contract: Path, source_receipt: Path) -> tuple[dict[str, Any], list[str]]:
    errors = validate_bundle_inputs(outline_contract, source_receipt)
    if errors:
        return {}, errors
    outline = read_json(outline_contract)
    source_receipt_data = read_json(source_receipt)
    selected_subflow_coverage = collect_selected_subflow_coverage(source_receipt_data)
    packets: list[dict[str, Any]] = []
    packet_ids: list[str] = []
    for section in outline.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "").strip()
        contract = section.get("first_draft_generation_contract")
        if not section_id:
            errors.append("存在缺少 section_id 的小节")
            continue
        if not isinstance(contract, dict):
            errors.append(f"第 {section_id} 节缺少 first_draft_generation_contract")
            continue
        bindings = contract.get("source_slice_bindings")
        if not isinstance(bindings, list) or not bindings:
            errors.append(f"第 {section_id} 节缺少 source_slice_bindings")
            continue
        normalized_bindings: list[dict[str, Any]] = []
        source_excerpts: list[str] = []
        style_reference_assets: list[dict[str, Any]] = []
        seen_book_roots: set[str] = set()
        for index, item in enumerate(bindings, start=1):
            if not isinstance(item, dict):
                errors.append(f"第 {section_id} 节 source_slice_bindings[{index}] 不是对象")
                continue
            source_path = Path(str(item.get("source_path") or "")).expanduser().resolve()
            if not source_path.is_file():
                errors.append(f"第 {section_id} 节原文切片不存在: {source_path}")
                continue
            current_sha = sha256(source_path)
            if item.get("source_sha256") != current_sha:
                errors.append(f"第 {section_id} 节原文切片 SHA 已变化: {source_path}")
            source_range = str(item.get("source_range") or "").strip()
            book_root = discover_book_root_from_source(source_path)
            if book_root:
                source_meta = selected_subflow_coverage.get(book_root.resolve())
                if source_meta:
                    uncovered_segments = find_uncovered_binding_segments(
                        source_range,
                        source_meta["segments"],
                    )
                    if uncovered_segments:
                        errors.append(
                            f"第 {section_id} 节绑定的原文区间未被已选 SF 覆盖："
                            f"{source_meta['name']} {format_segments(uncovered_segments)}；"
                            "必须先回到 story-short-analyze 补齐子流程，再重新编译细纲与颗粒包"
                        )
            try:
                excerpt = source_excerpt(source_path, source_range)
            except ValueError as exc:
                errors.append(f"第 {section_id} 节原文切片范围无效: {exc}")
                excerpt = ""
            line_ranges = re.findall(r"L(\d+)-L(\d+)", source_range)
            source_lines = read_text(source_path).splitlines()
            for raw_start, raw_end in line_ranges:
                start, end = int(raw_start), int(raw_end)
                if end - start + 1 > MAX_SOURCE_SLICE_LINES:
                    errors.append(
                        f"第 {section_id} 节原文切片过宽（L{start}-L{end}，{end - start + 1} 行）；"
                        "正文首写不得绑定跨场大切片"
                    )
                excerpt_lines = source_lines[start - 1 : end]
                chapter_markers = [
                    line.strip()
                    for line in excerpt_lines
                    if re.fullmatch(r"(?:第?\d+[章节节]?|[0-9]+[.、]?)", line.strip())
                ]
                if chapter_markers:
                    errors.append(
                        f"第 {section_id} 节原文切片疑似跨自然节/章节标记: {' / '.join(chapter_markers[:3])}"
                    )
            evidence = item.get("source_evidence")
            if not _nonempty_list(evidence):
                errors.append(f"第 {section_id} 节原文切片缺少 source_evidence")
            else:
                missing = [str(term) for term in evidence if str(term).strip() and str(term) not in excerpt]
                if missing:
                    errors.append(
                        f"第 {section_id} 节原文证据不在绑定行段内: {' / '.join(missing)}"
                    )
            style_fields = item.get("style_fields_consumed")
            if not isinstance(style_fields, list) or set(style_fields) != set(REQUIRED_STYLE_FIELDS):
                errors.append(f"第 {section_id} 节 style_fields_consumed 必须完整覆盖六类文风颗粒")
            normalized_bindings.append(
                {
                    "source_path": str(source_path),
                    "source_sha256": current_sha,
                    "source_range": source_range,
                    "source_excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                    "source_excerpt_text": excerpt,
                    "source_evidence": [str(term).strip() for term in (evidence or []) if str(term).strip()],
                    "style_fields_consumed": [str(term).strip() for term in (style_fields or []) if str(term).strip()],
                }
            )
            source_excerpts.append(excerpt)
            if book_root and str(book_root) not in seen_book_roots:
                seen_book_roots.add(str(book_root))
                style_reference_assets.append(load_style_reference_assets(book_root))
        packet_payload = {
            "section_id": section_id,
            "source_slice_bindings": normalized_bindings,
            "source_performance_excerpt": contract.get("source_performance_excerpt"),
            "source_performance_evidence": contract.get("source_performance_evidence"),
            "technique_recall_contract": contract.get("technique_recall_contract"),
            "scene_weave_contract": contract.get("scene_weave_contract"),
            "source_style_granularity": contract.get("source_style_granularity"),
            "source_excerpt_reuse_reason": contract.get("source_excerpt_reuse_reason"),
            "source_style_reference_assets": style_reference_assets,
            "emotion_process": contract.get("emotion_process"),
            "continuous_moment_groups": contract.get("continuous_moment_groups"),
            "paragraph_break_reasons": contract.get("paragraph_break_reasons"),
            "sentence_relation_plan": contract.get("sentence_relation_plan"),
            "function_word_strategy": contract.get("function_word_strategy"),
            "telegraphic_risk": contract.get("telegraphic_risk"),
            "emotion_shorthand_to_avoid": contract.get("emotion_shorthand_to_avoid"),
            "target_emotion_landing_plan": contract.get("target_emotion_landing_plan"),
            "no_fixed_short_sentence_ratio": contract.get("no_fixed_short_sentence_ratio"),
            "manual_judgment": contract.get("manual_judgment"),
            "scene_logic_contract": section.get("scene_logic_contract"),
            "source_emotion_parity": section.get("source_emotion_parity"),
            "original_scene_granularity": section.get("original_scene_granularity"),
        }
        for field in (
            "source_performance_excerpt",
            "function_word_strategy",
            "telegraphic_risk",
            "manual_judgment",
        ):
            if not _nonempty_text(packet_payload.get(field)):
                errors.append(f"第 {section_id} 节颗粒包缺少 {field}")
        for field in (
            "source_performance_evidence",
            "technique_recall_contract",
            "scene_weave_contract",
        ):
            if not _nonempty_list(packet_payload.get(field)):
                errors.append(f"第 {section_id} 节颗粒包缺少 {field}")
        for quote in packet_payload.get("source_performance_evidence") or []:
            if not any(str(quote) in excerpt for excerpt in source_excerpts):
                errors.append(f"第 {section_id} 节 source_performance_evidence 不在本节原文切片内: {quote}")
        validate_style_granularity(
            packet_payload.get("source_style_granularity"),
            section_id,
            source_excerpts,
            errors,
        )
        validate_style_reference_assets(
            packet_payload.get("source_style_reference_assets"),
            section_id,
            errors,
        )
        if not _nonempty_dict(packet_payload.get("original_scene_granularity")):
            errors.append(f"第 {section_id} 节颗粒包缺少 original_scene_granularity")
        for field in (
            "continuous_moment_groups",
            "paragraph_break_reasons",
            "sentence_relation_plan",
            "emotion_shorthand_to_avoid",
            "target_emotion_landing_plan",
        ):
            if not _nonempty_list(packet_payload.get(field)):
                errors.append(f"第 {section_id} 节颗粒包缺少 {field}")
        if packet_payload.get("no_fixed_short_sentence_ratio") is not True:
            errors.append(f"第 {section_id} 节颗粒包缺少 no_fixed_short_sentence_ratio=true")
        packet_id = f"section-{section_id}"
        packet_ids.append(packet_id)
        packets.append(
            {
                "packet_id": packet_id,
                "section_id": section_id,
                "payload": packet_payload,
                "packet_sha256": hashlib.sha256(
                    json.dumps(packet_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest(),
            }
        )
    bundle = {
        "version": "1.0",
        "gate": "section_source_bundle",
        "created_at": now_iso(),
        "outline_contract": {
            "path": str(outline_contract.resolve()),
            "sha256": sha256(outline_contract),
        },
        "source_receipt": {
            "path": str(source_receipt.resolve()),
            "sha256": sha256(source_receipt),
        },
        "section_packet_ids": packet_ids,
        "packets": packets,
        "gate_status": "passed" if not errors else "blocked",
    }
    return bundle, errors


def validate_bundle(bundle_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = read_json(bundle_path)
    except Exception as exc:
        return [f"颗粒包不可读取: {exc}"]
    if data.get("gate") != "section_source_bundle":
        errors.append("gate 必须为 section_source_bundle")
    outline_binding = data.get("outline_contract")
    if not isinstance(outline_binding, dict):
        errors.append("缺少 outline_contract 绑定")
    else:
        outline_path = Path(str(outline_binding.get("path") or "")).resolve()
        if not outline_path.is_file():
            errors.append(f"outline_contract 不存在: {outline_path}")
        elif outline_binding.get("sha256") != sha256(outline_path):
            errors.append("outline_contract SHA 已变化")
    source_binding = data.get("source_receipt")
    source_receipt_data: dict[str, Any] | None = None
    selected_subflow_coverage: dict[Path, dict[str, Any]] = {}
    if not isinstance(source_binding, dict):
        errors.append("缺少 source_receipt 绑定")
    else:
        source_path = Path(str(source_binding.get("path") or "")).resolve()
        if not source_path.is_file():
            errors.append(f"source_receipt 不存在: {source_path}")
        elif source_binding.get("sha256") != sha256(source_path):
            errors.append("source_receipt SHA 已变化")
        else:
            source_receipt_data = read_json(source_path)
            selected_subflow_coverage = collect_selected_subflow_coverage(source_receipt_data)
    packets = data.get("packets")
    if not isinstance(packets, list) or not packets:
        return errors + ["packets 必须为非空数组"]
    ids = data.get("section_packet_ids")
    actual_ids = [str(item.get("packet_id") or "") for item in packets if isinstance(item, dict)]
    if ids != actual_ids:
        errors.append("section_packet_ids 与 packets 顺序不一致")
    for item in packets:
        if not isinstance(item, dict):
            errors.append("packets 含非对象")
            continue
        payload = item.get("payload")
        section_id = str(item.get("section_id") or "")
        if not isinstance(payload, dict):
            errors.append(f"第 {section_id} 节 payload 不是对象")
            continue
        expected_sha = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if item.get("packet_sha256") != expected_sha:
            errors.append(f"第 {section_id} 节 packet_sha256 已变化")
        bindings = payload.get("source_slice_bindings")
        if not isinstance(bindings, list) or not bindings:
            errors.append(f"第 {section_id} 节缺少 source_slice_bindings")
            continue
        source_excerpts: list[str] = []
        for binding in bindings:
            if not isinstance(binding, dict):
                errors.append(f"第 {section_id} 节存在非法 source_slice_binding")
                continue
            source_path = Path(str(binding.get("source_path") or "")).resolve()
            if not source_path.is_file():
                errors.append(f"第 {section_id} 节原文切片不存在: {source_path}")
                continue
            if binding.get("source_sha256") != sha256(source_path):
                errors.append(f"第 {section_id} 节原文切片 SHA 已变化: {source_path}")
                continue
            try:
                excerpt = source_excerpt(source_path, str(binding.get("source_range") or ""))
            except ValueError as exc:
                errors.append(f"第 {section_id} 节原文切片范围无效: {exc}")
                continue
            book_root = discover_book_root_from_source(source_path)
            if book_root:
                source_meta = selected_subflow_coverage.get(book_root.resolve())
                if source_meta:
                    uncovered_segments = find_uncovered_binding_segments(
                        str(binding.get("source_range") or ""),
                        source_meta["segments"],
                    )
                    if uncovered_segments:
                        errors.append(
                            f"第 {section_id} 节绑定的原文区间未被已选 SF 覆盖："
                            f"{source_meta['name']} {format_segments(uncovered_segments)}；"
                            "必须先回到 story-short-analyze 补齐子流程，再重新编译细纲与颗粒包"
                        )
            for raw_start, raw_end in re.findall(r"L(\d+)-L(\d+)", str(binding.get("source_range") or "")):
                start, end = int(raw_start), int(raw_end)
                if end - start + 1 > MAX_SOURCE_SLICE_LINES:
                    errors.append(
                        f"第 {section_id} 节原文切片过宽（L{start}-L{end}，{end - start + 1} 行）"
                    )
            excerpt_sha = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            if binding.get("source_excerpt_sha256") != excerpt_sha:
                errors.append(f"第 {section_id} 节原文精确行段 SHA 已变化: {source_path}")
            if str(binding.get("source_excerpt_text") or "") != excerpt:
                errors.append(f"第 {section_id} 节原文切片正文未完整绑定: {source_path}")
            source_excerpts.append(excerpt)
            if set(binding.get("style_fields_consumed") or []) != set(REQUIRED_STYLE_FIELDS):
                errors.append(f"第 {section_id} 节未完整绑定六类文风颗粒")
            missing = [
                str(term)
                for term in binding.get("source_evidence", [])
                if str(term).strip() and str(term) not in excerpt
            ]
            if missing:
                errors.append(f"第 {section_id} 节原文证据不在绑定行段内: {' / '.join(missing)}")
        for field in (
            "source_performance_evidence",
            "technique_recall_contract",
            "scene_weave_contract",
            "target_emotion_landing_plan",
        ):
            if not _nonempty_list(payload.get(field)):
                errors.append(f"第 {section_id} 节颗粒包缺少 {field}")
        for quote in payload.get("source_performance_evidence") or []:
            if not any(str(quote) in excerpt for excerpt in source_excerpts):
                errors.append(f"第 {section_id} 节 source_performance_evidence 不在本节原文切片内: {quote}")
        validate_style_granularity(
            payload.get("source_style_granularity"),
            section_id,
            source_excerpts,
            errors,
        )
        validate_style_reference_assets(
            payload.get("source_style_reference_assets"),
            section_id,
            errors,
        )
        if payload.get("no_fixed_short_sentence_ratio") is not True:
            errors.append(f"第 {section_id} 节颗粒包缺少 no_fixed_short_sentence_ratio=true")
    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--outline-contract", required=True)
    build.add_argument("--source-receipt", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--force", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--bundle", required=True)
    args = parser.parse_args()
    if args.command == "build":
        output = Path(args.output).resolve()
        if output.exists() and not args.force:
            print(f"section_source_bundle: blocked\n- 颗粒包已存在，拒绝覆盖: {output}")
            return 2
        bundle, errors = create_bundle(
            Path(args.outline_contract).resolve(),
            Path(args.source_receipt).resolve(),
        )
        if errors:
            print("section_source_bundle: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        write_json(output, bundle)
        print("section_source_bundle: built")
        print(f"bundle: {output}")
        print(f"sections: {len(bundle['packets'])}")
        return 0
    errors = validate_bundle(Path(args.bundle).resolve())
    if errors:
        print("section_source_bundle: blocked")
        for item in errors:
            print(f"- {item}")
        return 2
    print("section_source_bundle: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
