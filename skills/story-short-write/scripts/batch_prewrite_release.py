#!/usr/bin/env python3
"""Batch runner for draft-prewrite + outline-performance + write-release gates."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _load_module(filename: str, alias: str):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTLINE = _load_module(
    "validate_outline_performance_contract.py",
    "story_short_write_outline_performance_batch",
)
DRAFT_PREWRITE = _load_module(
    "batch_draft_prewrite.py",
    "story_short_write_batch_draft_prewrite_release",
)
WRITE_RELEASE = _load_module(
    "validate_write_release_gate.py",
    "story_short_write_validate_write_release_gate_batch",
)


def prevalidated_entry(path: Path) -> dict[str, Any] | None:
    """Bind a successful in-process validation to the exact current payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "data": payload,
    }


def validate_batch(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    ledger: Path,
    sequence_receipt: Path,
    opening_contract: Path,
    outline_contract: Path,
    outline: Path,
    prose_contract: Path,
    emotional_contract: Path,
    primary_source_original: Path,
    source_emotion_ledger: Path,
    profile: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    summary: dict[str, Any] = {
        "outline_performance_passed": False,
        "draft_prewrite_passed": False,
        "write_release_passed": False,
        "reused_contract_validations": [],
    }
    prevalidated_contracts: dict[str, Any] = {}

    outline_errors = OUTLINE.validate_receipt(outline_contract, outline)
    if outline_errors:
        errors.append("细纲表演验收门禁未通过")
        errors.extend(outline_errors)
    else:
        summary["outline_performance_passed"] = True
        entry = prevalidated_entry(outline_contract)
        if entry is not None:
            prevalidated_contracts["outline_contract"] = entry

    prewrite_errors, prewrite_summary = DRAFT_PREWRITE.validate_batch(
        prose_receipt=prose_contract,
        emotional_receipt=emotional_contract,
        source_original=primary_source_original,
        source_emotion_ledger=source_emotion_ledger,
        outline=outline,
    )
    if prewrite_errors:
        errors.append("正文前合同批次未通过")
        errors.extend(prewrite_errors)
    else:
        summary["draft_prewrite_passed"] = True
        for key, path in (
            ("prose_contract", prose_contract),
            ("emotional_contract", emotional_contract),
        ):
            entry = prevalidated_entry(path)
            if entry is not None:
                prevalidated_contracts[key] = entry
    summary["draft_prewrite_summary"] = prewrite_summary
    summary["reused_contract_validations"] = list(prevalidated_contracts)

    release_errors = WRITE_RELEASE.validate_release(
        "draft",
        writing_receipt,
        source_receipt,
        ledger,
        opening_contract=opening_contract,
        outline_contract=outline_contract,
        profile=profile,
        sequence_receipt=sequence_receipt,
        prose_contract=prose_contract,
        primary_source_original=primary_source_original,
        emotional_contract=emotional_contract,
        source_emotion_ledger=source_emotion_ledger,
        prevalidated_contracts=prevalidated_contracts,
    )
    if release_errors:
        errors.append("正文写作放行闸未通过")
        errors.extend(release_errors)
    else:
        summary["write_release_passed"] = True

    return errors, summary


def prepare_and_validate_batch(
    *,
    project: str,
    source_original: Path,
    source_emotion_ledger: Path,
    outline: Path,
    prose_receipt: Path,
    emotional_receipt: Path,
    force_prose_receipt: bool,
    force_emotional_receipt: bool,
    prose_plan: Path | None,
    emotional_plan: Path | None,
    beat_mapping: Path | None,
    outline_contract: Path,
    writing_receipt: Path,
    source_receipt: Path,
    ledger: Path,
    sequence_receipt: Path,
    opening_contract: Path,
    profile: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    prepare_errors, prepare_summary = DRAFT_PREWRITE.prepare_batch(
        project=project,
        source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
        outline=outline,
        prose_receipt=prose_receipt,
        emotional_receipt=emotional_receipt,
        force_prose_receipt=force_prose_receipt,
        force_emotional_receipt=force_emotional_receipt,
        prose_plan=prose_plan,
        emotional_plan=emotional_plan,
        beat_mapping=beat_mapping,
        outline_contract=outline_contract,
    )
    summary: dict[str, Any] = {"prepare_summary": prepare_summary}
    if prepare_errors:
        errors.append("正文前合同批次 prepare 未通过")
        errors.extend(prepare_errors)
        return errors, summary

    validate_errors, validate_summary = validate_batch(
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        ledger=ledger,
        sequence_receipt=sequence_receipt,
        opening_contract=opening_contract,
        outline_contract=outline_contract,
        outline=outline,
        prose_contract=prose_receipt,
        emotional_contract=emotional_receipt,
        primary_source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
        profile=profile,
    )
    summary.update(validate_summary)
    return validate_errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch run for draft-prewrite, outline performance, and draft release."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_validate = sub.add_parser("prepare-validate")
    prepare_validate.add_argument("--project", required=True)
    prepare_validate.add_argument("--source-original", required=True)
    prepare_validate.add_argument("--source-emotion-ledger", required=True)
    prepare_validate.add_argument("--outline", required=True)
    prepare_validate.add_argument("--prose-receipt", required=True)
    prepare_validate.add_argument("--emotional-receipt", required=True)
    prepare_validate.add_argument("--force-prose-receipt", action="store_true")
    prepare_validate.add_argument("--force-emotional-receipt", action="store_true")
    prepare_validate.add_argument("--prose-plan")
    prepare_validate.add_argument("--emotional-plan")
    prepare_validate.add_argument("--beat-mapping")
    prepare_validate.add_argument("--writing-receipt", required=True)
    prepare_validate.add_argument("--source-receipt", required=True)
    prepare_validate.add_argument("--ledger", required=True)
    prepare_validate.add_argument("--sequence-receipt", required=True)
    prepare_validate.add_argument("--opening-contract", required=True)
    prepare_validate.add_argument("--outline-contract", required=True)
    prepare_validate.add_argument("--profile", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--writing-receipt", required=True)
    validate.add_argument("--source-receipt", required=True)
    validate.add_argument("--ledger", required=True)
    validate.add_argument("--sequence-receipt", required=True)
    validate.add_argument("--opening-contract", required=True)
    validate.add_argument("--outline-contract", required=True)
    validate.add_argument("--outline", required=True)
    validate.add_argument("--prose-contract", required=True)
    validate.add_argument("--emotional-contract", required=True)
    validate.add_argument("--primary-source-original", required=True)
    validate.add_argument("--source-emotion-ledger", required=True)
    validate.add_argument("--profile", required=True)

    args = parser.parse_args()
    if args.command == "prepare-validate":
        errors, summary = prepare_and_validate_batch(
            project=args.project,
            source_original=Path(args.source_original).resolve(),
            source_emotion_ledger=Path(args.source_emotion_ledger).resolve(),
            outline=Path(args.outline).resolve(),
            prose_receipt=Path(args.prose_receipt).resolve(),
            emotional_receipt=Path(args.emotional_receipt).resolve(),
            force_prose_receipt=bool(args.force_prose_receipt),
            force_emotional_receipt=bool(args.force_emotional_receipt),
            prose_plan=Path(args.prose_plan).resolve() if args.prose_plan else None,
            emotional_plan=Path(args.emotional_plan).resolve() if args.emotional_plan else None,
            beat_mapping=Path(args.beat_mapping).resolve() if args.beat_mapping else None,
            outline_contract=Path(args.outline_contract).resolve(),
            writing_receipt=Path(args.writing_receipt).resolve(),
            source_receipt=Path(args.source_receipt).resolve(),
            ledger=Path(args.ledger).resolve(),
            sequence_receipt=Path(args.sequence_receipt).resolve(),
            opening_contract=Path(args.opening_contract).resolve(),
            profile=Path(args.profile).resolve(),
        )
    else:
        errors, summary = validate_batch(
            writing_receipt=Path(args.writing_receipt).resolve(),
            source_receipt=Path(args.source_receipt).resolve(),
            ledger=Path(args.ledger).resolve(),
            sequence_receipt=Path(args.sequence_receipt).resolve(),
            opening_contract=Path(args.opening_contract).resolve(),
            outline_contract=Path(args.outline_contract).resolve(),
            outline=Path(args.outline).resolve(),
            prose_contract=Path(args.prose_contract).resolve(),
            emotional_contract=Path(args.emotional_contract).resolve(),
            primary_source_original=Path(args.primary_source_original).resolve(),
            source_emotion_ledger=Path(args.source_emotion_ledger).resolve(),
            profile=Path(args.profile).resolve(),
        )
    if errors:
        print("batch_prewrite_release: blocked")
        for item in errors:
            print(f"- {item}")
        return 2
    print("batch_prewrite_release: passed")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
