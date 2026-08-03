#!/usr/bin/env python3
"""Build a per-section source granularity bundle from the passed outline contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def source_originals(root: Path) -> list[Path]:
    original_dir = root / "原文"
    if not original_dir.is_dir():
        return []
    return sorted(path for path in original_dir.iterdir() if path.is_file())


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_outline_performance_module() -> Any:
    script = Path(__file__).with_name("validate_outline_performance_contract.py")
    spec = importlib.util.spec_from_file_location("validate_outline_performance_contract", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载细纲表演校验脚本: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def source_excerpt_for_range(source_text: str, source_range: str) -> tuple[str, str | None]:
    """Extract every declared source line range without summarizing or truncating it."""
    parts = [part.strip() for part in re.split(r"[、,，]\s*", source_range) if part.strip()]
    if not parts:
        return "", "source_range 不能为空"
    lines = source_text.splitlines()
    excerpts: list[str] = []
    for part in parts:
        match = re.fullmatch(r"L(\d+)-L(\d+)", part)
        if not match:
            return "", "必须使用 L起始-L结束 或多段 L起始-L结束"
        start, end = int(match.group(1)), int(match.group(2))
        if start < 1 or end < start or end > len(lines):
            return "", f"{part} 超出原文行号范围 1-{len(lines)}"
        excerpts.append("\n".join(lines[start - 1 : end]))
    return "\n".join(excerpts), None


def source_range_parts(source_range: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"[、,，]\s*", str(source_range or ""))
        if re.fullmatch(r"L\d+-L\d+", part.strip())
    ]


def normalized_source_binding(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": str(
            Path(str(value.get("source_path") or "")).expanduser().resolve()
        ),
        "source_sha256": str(value.get("source_sha256") or ""),
        "source_range": str(value.get("source_range") or "").strip(),
        "source_evidence": [
            str(item).strip()
            for item in value.get("source_evidence", [])
            if str(item).strip()
        ],
        "style_fields_consumed": [
            str(item).strip()
            for item in value.get("style_fields_consumed", [])
            if str(item).strip()
        ],
    }


def section_heading_from_contract(section: dict[str, Any]) -> str:
    return str(
        section.get("section_heading")
        or section.get("title")
        or (
            (section.get("original_scene_granularity") or {}).get("source_scene")
            if isinstance(section.get("original_scene_granularity"), dict)
            else ""
        )
        or ""
    ).strip()


def normalized_section_contract(section: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(section)
    heading = section_heading_from_contract(section)
    if heading:
        normalized.setdefault("title", heading)
        normalized.setdefault("section_heading", heading)
    return normalized


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
    errors = load_outline_performance_module().validate_receipt(outline_contract, outline_path)
    return [f"细纲表演验收回执实时复验失败: {error}" for error in errors]


def validate_bundle_inputs(outline_contract: Path, source_receipt: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_outline_contract_receipt(outline_contract))
    try:
        source = read_json(source_receipt)
    except Exception as exc:
        return [f"拆文读取回执不可读取: {exc}"]
    if source.get("gate_status") != "passed":
        errors.append("拆文读取回执必须先通过")
    if str(source.get("writing_mode") or "") != "direct_imitation":
        errors.append("逐节原文颗粒包只允许 direct_imitation 模式")
    return errors


def validate_bundle_inputs_without_outline_revalidation(
    outline_contract: Path,
    source_receipt: Path,
) -> list[str]:
    errors: list[str] = []
    try:
        outline_receipt = read_json(outline_contract)
    except Exception as exc:
        errors.append(f"细纲表演验收回执不可读取: {exc}")
        return errors
    if outline_receipt.get("gate_status") != "passed":
        errors.append("细纲表演验收回执必须先通过")
    outline_binding = outline_receipt.get("outline")
    if not isinstance(outline_binding, dict):
        errors.append("细纲表演验收回执缺少 outline 绑定")
    else:
        outline_path = Path(str(outline_binding.get("path") or "")).expanduser().resolve()
        if not outline_path.is_file():
            errors.append(f"细纲绑定原始细纲不存在: {outline_path}")
        elif outline_binding.get("sha256") != sha256(outline_path):
            errors.append("细纲绑定原始细纲 SHA 已变化")
    try:
        source = read_json(source_receipt)
    except Exception as exc:
        errors.append(f"拆文读取回执不可读取: {exc}")
        return errors
    if source.get("gate_status") != "passed":
        errors.append("拆文读取回执必须先通过")
    if str(source.get("writing_mode") or "") != "direct_imitation":
        errors.append("逐节原文颗粒包只允许 direct_imitation 模式")
    return errors


def build_source_contract_index(
    source_receipt_path: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        receipt = read_json(source_receipt_path)
    except Exception as exc:
        return {}, [f"拆文读取回执不可读取: {exc}"]
    receipt_sources = receipt.get("sources")
    if not isinstance(receipt_sources, list):
        return {}, ["拆文读取回执 sources 必须是数组"]
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for source_index, source in enumerate(receipt_sources, start=1):
        if not isinstance(source, dict):
            errors.append(f"sources[{source_index}] 必须是对象")
            continue
        root = Path(str(source.get("root") or "")).expanduser().resolve()
        originals = source_originals(root)
        if len(originals) != 1:
            errors.append(f"{root / '原文'} 必须且只能有一个原文文件")
            continue
        original = originals[0].resolve()
        source_name = str(source.get("name") or "").strip()
        source_role = str(source.get("role") or "").strip()
        contracts = source.get("selected_subflow_contracts")
        if not isinstance(contracts, list):
            errors.append(f"sources[{source_index}].selected_subflow_contracts 必须是数组")
            continue
        for contract_index, contract in enumerate(contracts, start=1):
            if not isinstance(contract, dict):
                errors.append(
                    f"sources[{source_index}].selected_subflow_contracts[{contract_index}] 必须是对象"
                )
                continue
            source_range = str(contract.get("source_range") or "").strip()
            subflow_id = str(contract.get("subflow_id") or "").strip()
            if not source_range or not subflow_id:
                errors.append(
                    f"sources[{source_index}].selected_subflow_contracts[{contract_index}] 缺少 subflow_id 或 source_range"
                )
                continue
            range_parts = source_range_parts(source_range)
            if not range_parts:
                errors.append(
                    f"sources[{source_index}].selected_subflow_contracts[{contract_index}] source_range 格式无效"
                )
                continue
            for range_part in range_parts:
                key = (str(original), range_part)
                if key in index:
                    errors.append(
                        f"拆文读取回执存在重复原文绑定，无法唯一定位 SF: {original} {range_part}"
                    )
                    continue
                index[key] = {
                    "source_name": source_name,
                    "source_role": source_role,
                    "subflow_id": subflow_id,
                    "source_subflow_contract": copy.deepcopy(contract),
                }
    return index, errors


def create_bundle(
    outline_contract: Path,
    source_receipt: Path,
    *,
    skip_outline_contract_revalidation: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    errors = (
        validate_bundle_inputs_without_outline_revalidation(
            outline_contract, source_receipt
        )
        if skip_outline_contract_revalidation
        else validate_bundle_inputs(outline_contract, source_receipt)
    )
    if errors:
        return {}, errors
    source_contract_index, index_errors = build_source_contract_index(source_receipt)
    if index_errors:
        return {}, index_errors
    outline = read_json(outline_contract)
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
            source_text = read_text(source_path)
            source_excerpt, range_error = source_excerpt_for_range(source_text, source_range)
            source_contract = source_contract_index.get((str(source_path), source_range))
            if source_contract is None:
                errors.append(
                    f"第 {section_id} 节原文绑定无法回溯到拆文读取回执中的完整 SF 契约: "
                    f"{source_path.name} {source_range}"
                )
            if range_error:
                errors.append(
                    f"第 {section_id} 节原文切片范围无效: {source_path} -> {range_error}"
                )
            evidence = item.get("source_evidence")
            if not _nonempty_list(evidence):
                errors.append(f"第 {section_id} 节原文切片缺少 source_evidence")
            else:
                missing = [str(term) for term in evidence if str(term).strip() and str(term) not in source_text]
                if missing:
                    errors.append(
                        f"第 {section_id} 节原文切片证据不在源文件中: {' / '.join(missing)}"
                    )
            style_fields = item.get("style_fields_consumed")
            if not isinstance(style_fields, list) or len(style_fields) < 6:
                errors.append(f"第 {section_id} 节 style_fields_consumed 不足 6 项")
            normalized_bindings.append(
                {
                    "source_path": str(source_path),
                    "source_sha256": current_sha,
                    "source_range": source_range,
                    "source_name": str((source_contract or {}).get("source_name") or "").strip(),
                    "source_role": str((source_contract or {}).get("source_role") or "").strip(),
                    "subflow_id": str((source_contract or {}).get("subflow_id") or "").strip(),
                    "source_excerpt": source_excerpt,
                    "source_evidence": [str(term).strip() for term in (evidence or []) if str(term).strip()],
                    "style_fields_consumed": [str(term).strip() for term in (style_fields or []) if str(term).strip()],
                    "source_subflow_contract": copy.deepcopy(
                        (source_contract or {}).get("source_subflow_contract") or {}
                    ),
                }
            )
        section_heading = section_heading_from_contract(section)
        full_section_contract = normalized_section_contract(section)
        packet_payload = {
            "section_id": section_id,
            "section_heading": section_heading,
            "source_slice_bindings": normalized_bindings,
            # Preserve the complete validated contracts. Convenience fields below
            # remain for existing consumers, but never replace the full objects.
            "section_contract": full_section_contract,
            "first_draft_generation_contract": copy.deepcopy(contract),
            "source_performance_excerpt": contract.get("source_performance_excerpt"),
            "anti_verbatim_transfer_contract": contract.get("anti_verbatim_transfer_contract"),
            "emotion_process": contract.get("emotion_process"),
            "source_style_granularity": contract.get("source_style_granularity"),
            "first_draft_style_plan": contract.get("first_draft_style_plan"),
            "continuous_moment_groups": contract.get("continuous_moment_groups"),
            "paragraph_break_reasons": contract.get("paragraph_break_reasons"),
            "sentence_relation_plan": contract.get("sentence_relation_plan"),
            "function_word_strategy": contract.get("function_word_strategy"),
            "telegraphic_risk": contract.get("telegraphic_risk"),
            "emotion_shorthand_to_avoid": contract.get("emotion_shorthand_to_avoid"),
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
        for field in ("source_style_granularity", "first_draft_style_plan"):
            if not _nonempty_dict(packet_payload.get(field)):
                errors.append(f"第 {section_id} 节颗粒包缺少 {field}")
        if not _nonempty_dict(packet_payload.get("anti_verbatim_transfer_contract")):
            errors.append(f"第 {section_id} 节颗粒包缺少 anti_verbatim_transfer_contract")
        if not _nonempty_dict(packet_payload.get("original_scene_granularity")):
            errors.append(f"第 {section_id} 节颗粒包缺少 original_scene_granularity")
        for field in (
            "continuous_moment_groups",
            "paragraph_break_reasons",
            "sentence_relation_plan",
            "emotion_shorthand_to_avoid",
        ):
            if not _nonempty_list(packet_payload.get(field)):
                errors.append(f"第 {section_id} 节颗粒包缺少 {field}")
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
    outline_sections: dict[str, dict[str, Any]] = {}
    source_contract_index: dict[tuple[str, str], dict[str, Any]] = {}
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
        else:
            outline_data = read_json(outline_path)
            outline_sections = {
                str(item.get("section_id") or ""): normalized_section_contract(item)
                for item in outline_data.get("sections", [])
                if isinstance(item, dict)
            }
    source_binding = data.get("source_receipt")
    if not isinstance(source_binding, dict):
        errors.append("缺少 source_receipt 绑定")
    else:
        source_path = Path(str(source_binding.get("path") or "")).resolve()
        if not source_path.is_file():
            errors.append(f"source_receipt 不存在: {source_path}")
        elif source_binding.get("sha256") != sha256(source_path):
            errors.append("source_receipt SHA 已变化")
        else:
            source_contract_index, index_errors = build_source_contract_index(source_path)
            errors.extend(index_errors)
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
            source_range = str(binding.get("source_range") or "").strip()
            current_excerpt, range_error = source_excerpt_for_range(
                read_text(source_path),
                source_range,
            )
            if range_error:
                errors.append(f"第 {section_id} 节原文切片范围无效: {range_error}")
            elif binding.get("source_excerpt") != current_excerpt:
                errors.append(f"第 {section_id} 节原文完整切片已变化: {source_path}")
            contract_key = (str(source_path), source_range)
            indexed_contract = source_contract_index.get(contract_key)
            if indexed_contract is None:
                errors.append(
                    f"第 {section_id} 节原文绑定已无法回溯到拆文读取回执的完整 SF 契约: "
                    f"{source_path.name} {source_range}"
                )
            else:
                if str(binding.get("subflow_id") or "").strip() != str(indexed_contract.get("subflow_id") or "").strip():
                    errors.append(f"第 {section_id} 节 subflow_id 与拆文读取回执不一致")
                if str(binding.get("source_name") or "").strip() != str(indexed_contract.get("source_name") or "").strip():
                    errors.append(f"第 {section_id} 节 source_name 与拆文读取回执不一致")
                if str(binding.get("source_role") or "").strip() != str(indexed_contract.get("source_role") or "").strip():
                    errors.append(f"第 {section_id} 节 source_role 与拆文读取回执不一致")
                if binding.get("source_subflow_contract") != indexed_contract.get("source_subflow_contract"):
                    errors.append(f"第 {section_id} 节完整 source_subflow_contract 与拆文读取回执不一致")
        full_section = payload.get("section_contract")
        full_generation = payload.get("first_draft_generation_contract")
        if not isinstance(full_section, dict):
            errors.append(f"第 {section_id} 节缺少完整 section_contract")
        elif full_section != outline_sections.get(section_id):
            errors.append(f"第 {section_id} 节完整 section_contract 与当前细纲回执不一致")
        if not isinstance(full_generation, dict):
            errors.append(f"第 {section_id} 节缺少完整 first_draft_generation_contract")
        else:
            expected_generation = (
                full_section.get("first_draft_generation_contract")
                if isinstance(full_section, dict)
                else None
            )
            if full_generation != expected_generation:
                errors.append(f"第 {section_id} 节完整生成契约与节级合同不一致")
            expected_bindings = (
                expected_generation.get("source_slice_bindings")
                if isinstance(expected_generation, dict)
                else None
            )
            normalized_packet_bindings = [
                normalized_source_binding(binding)
                for binding in bindings
                if isinstance(binding, dict)
            ]
            normalized_contract_bindings = [
                normalized_source_binding(binding)
                for binding in expected_bindings
                if isinstance(binding, dict)
            ] if isinstance(expected_bindings, list) else []
            if normalized_packet_bindings != normalized_contract_bindings:
                errors.append(f"第 {section_id} 节完整原文绑定与细纲生成契约不一致")
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
