#!/usr/bin/env python3
"""Batch entry for writing_rule_gate + source_read_gate."""

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


WRITING_GATE = _load_module(
    "validate_writing_rule_gate.py",
    "story_short_write_writing_rule_gate",
)
SOURCE_GATE = _load_module(
    "validate_source_read_gate.py",
    "story_short_write_source_read_gate",
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def init_batch(
    *,
    project: str,
    writing_receipt: Path,
    source_receipt: Path,
    source_dirs: list[Path],
    skill_root: Path,
    force_writing_receipt: bool,
) -> tuple[list[str], dict[str, int | str]]:
    errors: list[str] = []
    writing_payload, writing_errors = WRITING_GATE.create_receipt(
        project,
        skill_root,
    )
    errors.extend(writing_errors)
    source_payload, source_errors = SOURCE_GATE.create_receipt(project, source_dirs)
    errors.extend(source_errors)

    if writing_receipt.exists() and not force_writing_receipt:
        errors.append(f"写作规则读取回执已存在，拒绝覆盖: {writing_receipt}")

    if errors:
        return errors, {
            "writing_files": len(writing_payload.get("files", [])),
            "source_count": len(source_payload.get("sources", [])),
            "source_files": sum(
                len(source.get("files", []))
                for source in source_payload.get("sources", [])
                if isinstance(source, dict)
            ),
        }

    if writing_receipt.exists():
        writing_receipt.unlink()
    write_json(writing_receipt, writing_payload)
    archived_source_receipt = SOURCE_GATE.archive_existing_receipt(source_receipt)
    SOURCE_GATE.write_json_atomic(source_receipt, source_payload)
    summary: dict[str, int | str] = {
        "writing_files": len(writing_payload["files"]),
        "source_count": len(source_payload["sources"]),
        "source_files": sum(len(source["files"]) for source in source_payload["sources"]),
    }
    if archived_source_receipt is not None:
        summary["archived_source_receipt"] = str(archived_source_receipt)
    return [], summary


def validate_batch(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    stage: str,
    stage_output: Path,
    source_outputs: list[Path],
    skill_root: Path,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    writing_errors, writing_summary = WRITING_GATE.validate_receipt(
        writing_receipt,
        [stage_output],
        skill_root,
        artifact_stage=stage,
    )
    source_errors, source_summary = SOURCE_GATE.validate_receipt(
        source_receipt,
        source_outputs,
    )
    errors.extend(writing_errors)
    errors.extend(source_errors)
    return errors, {
        "writing_file_count": writing_summary["file_count"],
        "writing_read_count": writing_summary["read_count"],
        "source_count": source_summary["source_count"],
        "source_file_count": source_summary["file_count"],
        "source_read_count": source_summary["read_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch init/validate for writing_rule_gate and source_read_gate."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--writing-receipt", required=True)
    init.add_argument("--source-receipt", required=True)
    init.add_argument("--source-dir", action="append", required=True)
    init.add_argument("--skill-root", default=str(WRITING_GATE.SKILL_ROOT))
    init.add_argument("--force-writing-receipt", action="store_true")

    validate = sub.add_parser("validate")
    validate.add_argument("--writing-receipt", required=True)
    validate.add_argument("--source-receipt", required=True)
    validate.add_argument("--stage", choices=tuple(WRITING_GATE.STAGE_TARGET_NAMES), required=True)
    validate.add_argument("--stage-output", required=True)
    validate.add_argument("--output", action="append", required=True)
    validate.add_argument("--skill-root", default=str(WRITING_GATE.SKILL_ROOT))

    args = parser.parse_args()
    if args.command == "init":
        errors, summary = init_batch(
            project=args.project,
            writing_receipt=Path(args.writing_receipt).resolve(),
            source_receipt=Path(args.source_receipt).resolve(),
            source_dirs=[Path(raw) for raw in args.source_dir],
            skill_root=Path(args.skill_root).resolve(),
            force_writing_receipt=bool(args.force_writing_receipt),
        )
        print(f"writing_receipt: {Path(args.writing_receipt).resolve()}")
        print(f"source_receipt: {Path(args.source_receipt).resolve()}")
        print(f"writing_files: {summary['writing_files']}")
        print(f"source_count: {summary['source_count']}")
        print(f"source_files: {summary['source_files']}")
        if "archived_source_receipt" in summary:
            print(f"archived_source_receipt: {summary['archived_source_receipt']}")
        if errors:
            print("batch_read_gates: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_read_gates: initialized")
        return 0

    errors, summary = validate_batch(
        writing_receipt=Path(args.writing_receipt).resolve(),
        source_receipt=Path(args.source_receipt).resolve(),
        stage=args.stage,
        stage_output=Path(args.stage_output).resolve(),
        source_outputs=[Path(raw) for raw in args.output],
        skill_root=Path(args.skill_root).resolve(),
    )
    print(f"stage: {args.stage}")
    print(f"writing_file_count: {summary['writing_file_count']}")
    print(f"writing_read_count: {summary['writing_read_count']}")
    print(f"source_count: {summary['source_count']}")
    print(f"source_file_count: {summary['source_file_count']}")
    print(f"source_read_count: {summary['source_read_count']}")
    if errors:
        print("batch_read_gates: blocked")
        for item in errors:
            print(f"- {item}")
        return 2
    print("batch_read_gates: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
