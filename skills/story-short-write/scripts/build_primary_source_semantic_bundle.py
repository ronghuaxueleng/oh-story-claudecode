#!/usr/bin/env python3
"""Compile the selected primary source subflows into a project-local semantic bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_source_read_module() -> Any:
    script = Path(__file__).with_name("validate_source_read_gate.py")
    spec = importlib.util.spec_from_file_location("validate_source_read_gate", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载拆文读取脚本: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE_READ = load_source_read_module()


def source_contract_by_id(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    contracts = source.get("selected_subflow_contracts")
    if not isinstance(contracts, list):
        return {}
    return {
        str(item.get("subflow_id") or "").strip(): item
        for item in contracts
        if isinstance(item, dict) and str(item.get("subflow_id") or "").strip()
    }


def package_subflow_to_receipt_contract(item: dict[str, Any]) -> dict[str, Any]:
    contract = {
        "subflow_id": str(item.get("subflow_id") or "").strip(),
    }
    for field in SOURCE_READ.SUBFLOW_CONSUMPTION_FIELDS:
        contract[field] = copy.deepcopy(item.get(field))
    contract["source_evidence"] = copy.deepcopy(item.get("source_evidence", []))
    return contract


def canonical_original_path(root: Path) -> tuple[Path | None, list[str]]:
    originals = SOURCE_READ.source_originals(root)
    if len(originals) != 1:
        return None, [f"拆文来源必须且只能有一份完整原文: {root}"]
    return originals[0].resolve(), []


def resolve_package_original_path(root: Path, value: Any) -> Path:
    path = Path(str(value or "")).expanduser()
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    return path


def create_bundle(
    source_receipt: Path,
    *,
    validate_source_receipt: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        receipt = read_json(source_receipt)
    except Exception as exc:
        return {}, [f"拆文读取回执不可读取: {exc}"]
    if receipt.get("gate_status") != "passed":
        errors.append("拆文读取回执必须先通过")
    if str(receipt.get("writing_mode") or "") != "direct_imitation":
        errors.append("主体原文完整颗粒包只允许 direct_imitation 模式")
    if validate_source_receipt:
        receipt_errors, _ = SOURCE_READ.validate_receipt(source_receipt)
        if receipt_errors:
            errors.extend(f"拆文读取回执实时复验失败: {error}" for error in receipt_errors)
    sources = receipt.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("拆文读取回执缺少 sources")
        return {}, errors
    primary = sources[0]
    if not isinstance(primary, dict):
        return {}, ["拆文读取回执主体来源不是对象"]
    if str(primary.get("role") or "") != "main":
        errors.append("拆文读取回执第一来源必须是主体来源 main")
    root = Path(str(primary.get("root") or "")).expanduser().resolve()
    package_path, package_errors = SOURCE_READ.validate_direct_imitation_package(
        root,
        style_subflow_ids=set(SOURCE_READ.nonempty_strings(primary.get("selected_subflow_ids"))),
    )
    if package_errors:
        errors.extend(package_errors)
        return {}, errors
    if package_path is None:
        return {}, ["主体仿写无损编译包校验失败"]
    package = read_json(package_path)
    canonical_original, canonical_errors = canonical_original_path(root)
    if canonical_errors:
        return {}, canonical_errors
    assert canonical_original is not None
    original = package.get("original")
    if not isinstance(original, dict):
        return {}, ["主体仿写无损编译包缺少 original"]
    original_path = resolve_package_original_path(root, original.get("path"))
    if original_path != canonical_original:
        return {}, [f"主体原文绑定错误，必须使用拆文目录原文: {canonical_original}"]
    if not original_path.is_file():
        return {}, [f"主体原文不存在: {original_path}"]
    selected_ids = SOURCE_READ.nonempty_strings(primary.get("selected_subflow_ids"))
    if not selected_ids:
        errors.append("主体来源缺少 selected_subflow_ids")
    receipt_contracts = source_contract_by_id(primary)
    package_subflows = {
        str(item.get("subflow_id") or "").strip(): item
        for item in package.get("subflows", [])
        if isinstance(item, dict) and str(item.get("subflow_id") or "").strip()
    }
    subflows: list[dict[str, Any]] = []
    original_text = read_text(original_path)
    for subflow_id in selected_ids:
        receipt_contract = receipt_contracts.get(subflow_id)
        package_contract = package_subflows.get(subflow_id)
        if receipt_contract is None:
            errors.append(f"主体来源缺少已选 SF 完整契约: {subflow_id}")
            continue
        if package_contract is None:
            errors.append(f"主体无损编译包缺少已选 SF: {subflow_id}")
            continue
        source_excerpt, range_error = SOURCE_READ.source_slice_for_range(
            original_text,
            str(receipt_contract.get("source_range") or ""),
        )
        if range_error:
            errors.append(f"{subflow_id}.source_range {range_error}")
            continue
        if package_subflow_to_receipt_contract(package_contract) != receipt_contract:
            errors.append(f"主体来源 {subflow_id} 在拆文读取回执和无损编译包之间不一致")
            continue
        subflows.append(
            {
                "subflow_id": subflow_id,
                "identity": f"{primary.get('name')}::{subflow_id}",
                "source_excerpt": source_excerpt,
                "contract": copy.deepcopy(receipt_contract),
            }
        )
    if errors:
        return {}, errors
    bundle = {
        "version": "1.0",
        "kind": "primary_source_semantic_bundle",
        "created_at": now_iso(),
        "source_receipt": {
            "path": str(source_receipt.resolve()),
            "sha256": sha256(source_receipt),
        },
        "direct_imitation_package": {
            "path": str(package_path.resolve()),
            "sha256": sha256(package_path),
        },
        "primary_source": {
            "name": str(primary.get("name") or "").strip(),
            "root": str(root),
            "original": {
                "path": str(original_path),
                "sha256": sha256(original_path),
            },
            "selected_subflow_ids": selected_ids,
        },
        "subflows": subflows,
    }
    return bundle, []


def validate_bundle(
    bundle_path: Path,
    *,
    validate_source_receipt: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not bundle_path.is_file():
        return [f"主体原文完整颗粒包不存在: {bundle_path}"]
    try:
        bundle = read_json(bundle_path)
    except Exception as exc:
        return [f"主体原文完整颗粒包不可读取: {exc}"]
    if bundle.get("kind") != "primary_source_semantic_bundle":
        errors.append("kind 必须为 primary_source_semantic_bundle")
    if bundle.get("version") != "1.0":
        errors.append("version 必须为 1.0")

    receipt_binding = bundle.get("source_receipt")
    if not isinstance(receipt_binding, dict):
        return ["缺少 source_receipt 绑定"]
    receipt_path = Path(str(receipt_binding.get("path") or "")).expanduser().resolve()
    if not receipt_path.is_file():
        return [f"source_receipt 不存在: {receipt_path}"]
    if receipt_binding.get("sha256") != sha256(receipt_path):
        errors.append("source_receipt SHA 已变化")
    if validate_source_receipt:
        receipt_errors, _ = SOURCE_READ.validate_receipt(receipt_path)
        if receipt_errors:
            errors.extend(f"拆文读取回执实时复验失败: {error}" for error in receipt_errors)

    package_binding = bundle.get("direct_imitation_package")
    if not isinstance(package_binding, dict):
        errors.append("缺少 direct_imitation_package 绑定")
        return errors
    package_path = Path(str(package_binding.get("path") or "")).expanduser().resolve()
    if not package_path.is_file():
        return [*errors, f"direct_imitation_package 不存在: {package_path}"]
    if package_binding.get("sha256") != sha256(package_path):
        errors.append("direct_imitation_package SHA 已变化")

    receipt = read_json(receipt_path)
    sources = receipt.get("sources")
    if not isinstance(sources, list) or not sources or not isinstance(sources[0], dict):
        return [*errors, "拆文读取回执缺少主体来源"]
    primary = sources[0]
    primary_binding = bundle.get("primary_source")
    if not isinstance(primary_binding, dict):
        return [*errors, "缺少 primary_source 绑定"]
    root = Path(str(primary_binding.get("root") or "")).expanduser().resolve()
    if root != Path(str(primary.get("root") or "")).expanduser().resolve():
        errors.append("primary_source.root 与拆文读取回执主体来源不一致")
    canonical_original, canonical_errors = canonical_original_path(root)
    if canonical_errors:
        return [*errors, *canonical_errors]
    assert canonical_original is not None
    selected_ids = SOURCE_READ.nonempty_strings(primary.get("selected_subflow_ids"))
    if selected_ids != SOURCE_READ.nonempty_strings(primary_binding.get("selected_subflow_ids")):
        errors.append("primary_source.selected_subflow_ids 与拆文读取回执不一致")
    original_binding = primary_binding.get("original")
    if not isinstance(original_binding, dict):
        errors.append("primary_source.original 缺失")
        return errors
    original_path = Path(str(original_binding.get("path") or "")).expanduser().resolve()
    if original_path != canonical_original:
        errors.append(f"primary_source.original 必须绑定拆文目录原文: {canonical_original}")
    if not original_path.is_file():
        return [*errors, f"primary_source.original 不存在: {original_path}"]
    if original_binding.get("sha256") != sha256(original_path):
        errors.append("primary_source.original SHA 已变化")

    package = read_json(package_path)
    package_subflows = {
        str(item.get("subflow_id") or "").strip(): item
        for item in package.get("subflows", [])
        if isinstance(item, dict) and str(item.get("subflow_id") or "").strip()
    }
    receipt_contracts = source_contract_by_id(primary)
    bundle_subflows = bundle.get("subflows")
    if not isinstance(bundle_subflows, list):
        return [*errors, "subflows 必须是数组"]
    actual_ids = []
    original_text = read_text(original_path)
    for entry in bundle_subflows:
        if not isinstance(entry, dict):
            errors.append("subflows 含非对象条目")
            continue
        subflow_id = str(entry.get("subflow_id") or "").strip()
        actual_ids.append(subflow_id)
        contract = entry.get("contract")
        if receipt_contracts.get(subflow_id) != contract:
            errors.append(f"subflow {subflow_id} 与拆文读取回执契约不一致")
        package_contract = package_subflows.get(subflow_id)
        if not isinstance(package_contract, dict):
            errors.append(f"subflow {subflow_id} 与无损编译包契约不一致")
        elif package_subflow_to_receipt_contract(package_contract) != contract:
            errors.append(f"subflow {subflow_id} 与无损编译包契约不一致")
        excerpt, range_error = SOURCE_READ.source_slice_for_range(
            original_text,
            str((contract or {}).get("source_range") or ""),
        )
        if range_error:
            errors.append(f"subflow {subflow_id}.source_range {range_error}")
        elif str(entry.get("source_excerpt") or "") != excerpt:
            errors.append(f"subflow {subflow_id}.source_excerpt 与原文精确切片不一致")
    if actual_ids != selected_ids:
        errors.append("subflows 顺序必须与主体 selected_subflow_ids 完全一致")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or validate project-local primary semantic bundle.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--source-receipt", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--force", action="store_true")

    validate = subparsers.add_parser("validate")
    validate.add_argument("--bundle", required=True)

    args = parser.parse_args()
    if args.command == "build":
        output = Path(args.output).expanduser().resolve()
        if output.exists() and not args.force:
            print("primary_source_semantic_bundle: blocked")
            print(f"- 颗粒包已存在，拒绝覆盖: {output}")
            return 2
        bundle, errors = create_bundle(Path(args.source_receipt).expanduser().resolve())
        if errors:
            print("primary_source_semantic_bundle: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        write_json(output, bundle)
        print("primary_source_semantic_bundle: built")
        print(output)
        return 0

    errors = validate_bundle(Path(args.bundle).expanduser().resolve())
    if errors:
        print("primary_source_semantic_bundle: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("primary_source_semantic_bundle: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
