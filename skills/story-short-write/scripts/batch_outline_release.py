#!/usr/bin/env python3
"""Batch initializer for outline-release receipts."""

from __future__ import annotations

import argparse
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


RULE_LEDGER = _load_module(
    "validate_rule_execution_ledger.py",
    "story_short_write_rule_execution_ledger",
)
SEQUENCE = _load_module(
    "validate_sequence_contract.py",
    "story_short_write_sequence_contract",
)
OPENING = _load_module(
    "validate_opening_contract.py",
    "story_short_write_opening_contract",
)
OUTLINE = _load_module(
    "validate_outline_performance_contract.py",
    "story_short_write_outline_performance_contract",
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _ensure_writable(path: Path, force: bool, label: str, errors: list[str]) -> None:
    if path.exists() and not force:
        errors.append(f"{label}已存在，拒绝覆盖: {path}")


def init_batch(
    *,
    project: str,
    writing_receipt: Path,
    source_receipt: Path,
    ledger: Path,
    setting: Path,
    outline: Path,
    setting_sequence_receipt: Path,
    sequence_receipt: Path,
    opening_source: Path,
    opening_receipt: Path,
    outline_receipt: Path,
    source_originals: list[Path],
    force_ledger: bool,
    force_setting_sequence: bool,
    force_sequence: bool,
    force_opening: bool,
    force_outline_receipt: bool,
    export_model_review_output: Path | None,
    export_batch_size: int,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if export_batch_size < 1:
        errors.append("export-batch-size 必须大于 0")

    _ensure_writable(ledger, force_ledger, "规则执行台账", errors)
    _ensure_writable(
        setting_sequence_receipt,
        force_setting_sequence,
        "设定顺序契约回执",
        errors,
    )
    _ensure_writable(
        sequence_receipt,
        force_sequence,
        "完整顺序契约回执",
        errors,
    )
    _ensure_writable(opening_receipt, force_opening, "开头契约回执", errors)
    _ensure_writable(
        outline_receipt,
        force_outline_receipt,
        "细纲表演验收回执",
        errors,
    )

    ledger_payload, ledger_errors = RULE_LEDGER.create_ledger(
        project,
        writing_receipt,
        source_receipt,
        extra_skill_rule_files=[],
    )
    errors.extend(ledger_errors)

    try:
        opening_payload = OPENING.create_receipt(
            project,
            opening_source,
            outline,
            "outline",
        )
    except FileNotFoundError as exc:
        errors.append(str(exc))
        opening_payload = None

    try:
        outline_payload = OUTLINE.create_receipt(
            project,
            outline,
            source_originals,
            source_mode="full_bridge",
        )
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
        outline_payload = None

    if errors:
        return errors, {
            "ledger_entries": len(ledger_payload.get("skill_rules", [])),
            "opening_ready": opening_payload is not None,
            "outline_ready": outline_payload is not None,
        }

    if ledger.exists():
        ledger.unlink()
    if setting_sequence_receipt.exists():
        setting_sequence_receipt.unlink()
    if sequence_receipt.exists():
        sequence_receipt.unlink()
    if opening_receipt.exists():
        opening_receipt.unlink()
    if outline_receipt.exists():
        outline_receipt.unlink()

    write_json(ledger, ledger_payload)
    SEQUENCE.init_setting_receipt(project, setting, setting_sequence_receipt)
    SEQUENCE.init_receipt(project, setting, outline, None, sequence_receipt)
    write_json(opening_receipt, opening_payload)
    write_json(outline_receipt, outline_payload)

    summary: dict[str, Any] = {
        "skill_rules": len(ledger_payload["skill_rules"]),
        "source_assets": len(ledger_payload["source_assets"]),
        "asset_rules": sum(len(item["rules"]) for item in ledger_payload["source_assets"]),
        "setting_sequence_receipt": str(setting_sequence_receipt),
        "sequence_receipt": str(sequence_receipt),
        "opening_receipt": str(opening_receipt),
        "outline_receipt": str(outline_receipt),
    }
    if export_model_review_output is not None:
        export_summary = RULE_LEDGER.export_model_review(
            ledger,
            export_model_review_output,
            export_batch_size,
        )
        summary["model_review_output"] = str(export_model_review_output)
        summary["model_review_entries"] = export_summary["entries"]
        summary["model_review_batches"] = export_summary["batches"]
    return [], summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch initializer for rule ledger + sequence/opening/outline receipts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--writing-receipt", required=True)
    init.add_argument("--source-receipt", required=True)
    init.add_argument("--ledger", required=True)
    init.add_argument("--setting", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--setting-sequence-receipt", required=True)
    init.add_argument("--sequence-receipt", required=True)
    init.add_argument("--opening-source", required=True)
    init.add_argument("--opening-receipt", required=True)
    init.add_argument("--outline-receipt", required=True)
    init.add_argument("--source-original", action="append", required=True)
    init.add_argument("--force-ledger", action="store_true")
    init.add_argument("--force-setting-sequence", action="store_true")
    init.add_argument("--force-sequence", action="store_true")
    init.add_argument("--force-opening", action="store_true")
    init.add_argument("--force-outline-receipt", action="store_true")
    init.add_argument("--export-model-review-output")
    init.add_argument("--export-batch-size", type=int, default=30)

    args = parser.parse_args()
    errors, summary = init_batch(
        project=args.project,
        writing_receipt=Path(args.writing_receipt).resolve(),
        source_receipt=Path(args.source_receipt).resolve(),
        ledger=Path(args.ledger).resolve(),
        setting=Path(args.setting).resolve(),
        outline=Path(args.outline).resolve(),
        setting_sequence_receipt=Path(args.setting_sequence_receipt).resolve(),
        sequence_receipt=Path(args.sequence_receipt).resolve(),
        opening_source=Path(args.opening_source).resolve(),
        opening_receipt=Path(args.opening_receipt).resolve(),
        outline_receipt=Path(args.outline_receipt).resolve(),
        source_originals=[Path(value).resolve() for value in args.source_original],
        force_ledger=bool(args.force_ledger),
        force_setting_sequence=bool(args.force_setting_sequence),
        force_sequence=bool(args.force_sequence),
        force_opening=bool(args.force_opening),
        force_outline_receipt=bool(args.force_outline_receipt),
        export_model_review_output=(
            Path(args.export_model_review_output).resolve()
            if args.export_model_review_output
            else None
        ),
        export_batch_size=args.export_batch_size,
    )

    if errors:
        print("batch_outline_release: blocked")
        for item in errors:
            print(f"- {item}")
        return 2

    print("batch_outline_release: initialized")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
