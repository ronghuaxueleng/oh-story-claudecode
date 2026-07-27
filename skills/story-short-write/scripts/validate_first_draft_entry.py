#!/usr/bin/env python3
"""Validate the only allowed entry for imitation-mode first-draft generation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


_WRITE_RELEASE_GATE_PATH = Path(__file__).with_name("validate_write_release_gate.py")
_WRITE_RELEASE_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_write_release_gate", _WRITE_RELEASE_GATE_PATH
)
assert _WRITE_RELEASE_SPEC and _WRITE_RELEASE_SPEC.loader
_WRITE_RELEASE_MODULE = importlib.util.module_from_spec(_WRITE_RELEASE_SPEC)
_WRITE_RELEASE_SPEC.loader.exec_module(_WRITE_RELEASE_MODULE)

_SECTION_EXECUTION_GATE_PATH = Path(__file__).with_name("validate_section_draft_execution.py")
_SECTION_EXECUTION_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_section_draft_execution", _SECTION_EXECUTION_GATE_PATH
)
assert _SECTION_EXECUTION_SPEC and _SECTION_EXECUTION_SPEC.loader
_SECTION_EXECUTION_MODULE = importlib.util.module_from_spec(_SECTION_EXECUTION_SPEC)
_SECTION_EXECUTION_SPEC.loader.exec_module(_SECTION_EXECUTION_MODULE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256(resolved)}


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def draft_has_user_content(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return bool(text.strip())


def init_entry(
    project: str,
    draft: Path,
    receipt: Path,
    writing_receipt: Path,
    source_receipt: Path,
    ledger: Path,
    opening_contract: Path,
    outline_contract: Path,
    profile: Path,
    sequence_receipt: Path,
    draft_capacity_contract: Path,
    section_source_bundle: Path,
    section_execution_receipt: Path,
    force: bool,
) -> int:
    if receipt.exists() and not force:
        print(f"首稿入口回执已存在，拒绝覆盖: {receipt}")
        return 2
    release_errors = _WRITE_RELEASE_MODULE.validate_release(
        phase="draft",
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        ledger=ledger,
        opening_contract=opening_contract,
        outline_contract=outline_contract,
        profile=profile,
        sequence_receipt=sequence_receipt,
        draft_capacity_contract=draft_capacity_contract,
        section_source_bundle=section_source_bundle,
    )
    if release_errors:
        print("first_draft_entry: blocked")
        for error in release_errors:
            print(f"- {error}")
        return 2
    if draft.exists() and _SECTION_EXECUTION_MODULE.draft_section_ids(draft):
        print("first_draft_entry: blocked\n- 正文已经含数字小节，禁止事后补入口回执")
        return 2
    if draft_has_user_content(draft):
        print("first_draft_entry: blocked\n- 正文已有内容，必须在落笔前先通过首稿入口")
        return 2
    draft.parent.mkdir(parents=True, exist_ok=True)
    if not draft.exists():
        draft.write_text("", encoding="utf-8")
    init_result = _SECTION_EXECUTION_MODULE.init_receipt(
        outline_contract=outline_contract,
        source_receipt=source_receipt,
        section_source_bundle=section_source_bundle,
        draft=draft,
        receipt=section_execution_receipt,
    )
    if init_result != 0:
        return init_result
    execution_data, execution_errors = _SECTION_EXECUTION_MODULE.validate_receipt(
        section_execution_receipt
    )
    if execution_errors:
        print("first_draft_entry: blocked")
        for error in execution_errors:
            print(f"- {error}")
        return 2
    payload = {
        "version": "1.0",
        "gate": "first_draft_entry",
        "project": project,
        "draft_path": str(draft.resolve()),
        "writing_receipt": binding(writing_receipt),
        "source_receipt": binding(source_receipt),
        "ledger": binding(ledger),
        "opening_contract": binding(opening_contract),
        "outline_contract": binding(outline_contract),
        "profile": binding(profile),
        "sequence_receipt": binding(sequence_receipt),
        "draft_capacity_contract": binding(draft_capacity_contract),
        "section_source_bundle": binding(section_source_bundle),
        "section_execution_receipt_path": str(section_execution_receipt.resolve()),
        "section_execution_initialized_sections": [
            str(item.get("section_id") or "")
            for item in execution_data.get("sections", [])
            if isinstance(item, dict)
        ],
        "entry_mode": "direct_imitation",
        "gate_status": "passed",
    }
    write_json(receipt, payload)
    print(f"first_draft_entry: passed\nreceipt: {receipt}")
    return 0


def validate_entry(receipt: Path, draft_override: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        data = read_json(receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"回执无法读取: {exc}"]
    if data.get("gate") != "first_draft_entry":
        errors.append("gate 必须为 first_draft_entry")
        return errors
    required_bindings = (
        "writing_receipt",
        "source_receipt",
        "ledger",
        "opening_contract",
        "outline_contract",
        "profile",
        "sequence_receipt",
        "draft_capacity_contract",
        "section_source_bundle",
    )
    resolved: dict[str, Path] = {}
    for key in required_bindings:
        value = data.get(key)
        if not isinstance(value, dict):
            errors.append(f"{key} 必须是对象")
            continue
        path = Path(str(value.get("path") or "")).expanduser().resolve()
        if not path.is_file():
            errors.append(f"{key} 文件不存在: {path}")
            continue
        if value.get("sha256") != sha256(path):
            errors.append(f"{key} SHA 已变化")
        resolved[key] = path
    draft = draft_override or Path(str(data.get("draft_path") or "")).expanduser().resolve()
    if not draft.is_file():
        errors.append(f"draft_path 文件不存在: {draft}")
    execution_path = Path(str(data.get("section_execution_receipt_path") or "")).expanduser().resolve()
    if not execution_path.is_file():
        errors.append(f"section_execution_receipt_path 文件不存在: {execution_path}")
    if errors:
        return errors
    release_errors = _WRITE_RELEASE_MODULE.validate_release(
        phase="draft",
        writing_receipt=resolved["writing_receipt"],
        source_receipt=resolved["source_receipt"],
        ledger=resolved["ledger"],
        opening_contract=resolved["opening_contract"],
        outline_contract=resolved["outline_contract"],
        profile=resolved["profile"],
        sequence_receipt=resolved["sequence_receipt"],
        draft_capacity_contract=resolved["draft_capacity_contract"],
        section_source_bundle=resolved["section_source_bundle"],
    )
    if release_errors:
        errors.append("首稿入口绑定的正文放行条件已失效")
        errors.extend(release_errors)
    execution_data, execution_errors = _SECTION_EXECUTION_MODULE.validate_receipt(execution_path)
    if execution_errors:
        errors.append("逐节首写执行回执已失效")
        errors.extend(execution_errors)
    else:
        if Path(str(execution_data.get("draft_path") or "")).resolve() != draft.resolve():
            errors.append("首稿入口绑定的正文路径与逐节执行回执不一致")
    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--draft", required=True)
    init.add_argument("--receipt", required=True)
    init.add_argument("--writing-receipt", required=True)
    init.add_argument("--source-receipt", required=True)
    init.add_argument("--ledger", required=True)
    init.add_argument("--opening-contract", required=True)
    init.add_argument("--outline-contract", required=True)
    init.add_argument("--profile", required=True)
    init.add_argument("--sequence-receipt", required=True)
    init.add_argument("--draft-capacity-contract", required=True)
    init.add_argument("--section-source-bundle", required=True)
    init.add_argument("--section-execution-receipt", required=True)
    init.add_argument("--force", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--draft")
    args = parser.parse_args()

    if args.command == "init":
        return init_entry(
            project=args.project,
            draft=Path(args.draft).resolve(),
            receipt=Path(args.receipt).resolve(),
            writing_receipt=Path(args.writing_receipt).resolve(),
            source_receipt=Path(args.source_receipt).resolve(),
            ledger=Path(args.ledger).resolve(),
            opening_contract=Path(args.opening_contract).resolve(),
            outline_contract=Path(args.outline_contract).resolve(),
            profile=Path(args.profile).resolve(),
            sequence_receipt=Path(args.sequence_receipt).resolve(),
            draft_capacity_contract=Path(args.draft_capacity_contract).resolve(),
            section_source_bundle=Path(args.section_source_bundle).resolve(),
            section_execution_receipt=Path(args.section_execution_receipt).resolve(),
            force=args.force,
        )
    draft = Path(args.draft).resolve() if args.draft else None
    errors = validate_entry(Path(args.receipt).resolve(), draft)
    if errors:
        print("first_draft_entry: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("first_draft_entry: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
