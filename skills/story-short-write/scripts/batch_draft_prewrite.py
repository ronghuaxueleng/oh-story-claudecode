#!/usr/bin/env python3
"""Batch entry for prose/emotional draft prewrite contracts."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from json import JSONDecodeError
from typing import Any


ROOT = Path(__file__).resolve().parent


def _load_module(filename: str, alias: str):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROSE = _load_module(
    "validate_prose_granularity_contract.py",
    "story_short_write_prose_granularity_contract",
)
EMOTION = _load_module(
    "validate_emotional_granularity_contract.py",
    "story_short_write_emotional_granularity_contract",
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_writable(path: Path, force: bool, label: str, errors: list[str]) -> None:
    if path.exists() and not force:
        errors.append(f"{label}已存在，拒绝覆盖: {path}")


def prepare_batch(
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
    outline_contract: Path | None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    _ensure_writable(prose_receipt, force_prose_receipt, "文字颗粒度合同回执", errors)
    _ensure_writable(
        emotional_receipt,
        force_emotional_receipt,
        "情绪颗粒度合同回执",
        errors,
    )

    if emotional_plan is not None and (beat_mapping is None) != (outline_contract is None):
        errors.append("情绪人工计划若走 assemble-section-plan，必须同时提供 beat-mapping 和 outline-contract")

    if errors:
        return errors, {}

    prose_data: dict[str, Any] | None = None
    emotion_data: dict[str, Any] | None = None
    try:
        prose_data = PROSE.create_receipt(project, source_original)
        prose_data = PROSE.bind_outline(prose_data, outline)
        if prose_plan is not None:
            plan = load_json(prose_plan)
            prose_data = PROSE.apply_section_plan(prose_data, plan)
            prose_data["section_plan_provenance"].update(
                {"path": str(prose_plan), "sha256": PROSE.sha256(prose_plan)}
            )
    except (FileNotFoundError, ValueError, JSONDecodeError, AttributeError) as exc:
        errors.append(f"文字颗粒度合同准备失败: {exc}")

    try:
        emotion_data = EMOTION.create_receipt(project, source_original, source_emotion_ledger)
        emotion_data = EMOTION.bind_outline(emotion_data, outline)
        if emotional_plan is not None:
            plan = load_json(emotional_plan)
            if beat_mapping is not None and outline_contract is not None:
                emotion_data = EMOTION.assemble_section_plan(
                    emotion_data,
                    plan,
                    load_json(source_emotion_ledger),
                    load_json(beat_mapping),
                    load_json(outline_contract),
                    source_original,
                )
            else:
                emotion_data = EMOTION.apply_section_plan(emotion_data, plan)
            emotion_data["section_plan_provenance"].update(
                {"path": str(emotional_plan), "sha256": EMOTION.sha256_file(emotional_plan)}
            )
    except (FileNotFoundError, ValueError, JSONDecodeError, AttributeError) as exc:
        errors.append(f"情绪颗粒度合同准备失败: {exc}")

    if errors or prose_data is None or emotion_data is None:
        return errors, {
            "prose_outline_bound": bool((prose_data or {}).get("outline")),
            "emotional_outline_bound": bool(
                ((emotion_data or {}).get("bindings") or {}).get("outline")
            ),
            "prose_plan_applied": prose_plan is not None,
            "emotional_plan_applied": emotional_plan is not None,
        }

    if prose_receipt.exists():
        prose_receipt.unlink()
    if emotional_receipt.exists():
        emotional_receipt.unlink()
    write_json(prose_receipt, prose_data)
    write_json(emotional_receipt, emotion_data)
    return [], {
        "prose_receipt": str(prose_receipt),
        "emotional_receipt": str(emotional_receipt),
        "prose_outline_bound": bool(prose_data.get("outline")),
        "emotional_outline_bound": bool((emotion_data.get("bindings") or {}).get("outline")),
        "prose_plan_applied": prose_plan is not None,
        "emotional_plan_applied": emotional_plan is not None,
    }


def validate_batch(
    *,
    prose_receipt: Path,
    emotional_receipt: Path,
    source_original: Path,
    source_emotion_ledger: Path,
    outline: Path,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    prose_summary: dict[str, Any] = {}
    emotional_summary: dict[str, Any] = {}
    try:
        prose_data = load_json(prose_receipt)
        prose_errors, prose_summary = PROSE.validate_prewrite_data(
            prose_data,
            source_original,
            outline,
        )
        errors.extend(prose_errors)
    except (FileNotFoundError, ValueError, JSONDecodeError, AttributeError) as exc:
        errors.append(f"文字颗粒度合同校验失败: {exc}")

    try:
        emotion_data = load_json(emotional_receipt)
        emotion_errors, emotional_summary = EMOTION.validate_prewrite_data(
            emotion_data,
            source_original,
            outline,
            source_emotion_ledger,
        )
        errors.extend(emotion_errors)
    except (FileNotFoundError, ValueError, JSONDecodeError, AttributeError) as exc:
        errors.append(f"情绪颗粒度合同校验失败: {exc}")

    return errors, {
        "prose_summary": prose_summary,
        "emotional_summary": emotional_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch prepare/validate for prose and emotional prewrite contracts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--project", required=True)
    prepare.add_argument("--source-original", required=True)
    prepare.add_argument("--source-emotion-ledger", required=True)
    prepare.add_argument("--outline", required=True)
    prepare.add_argument("--prose-receipt", required=True)
    prepare.add_argument("--emotional-receipt", required=True)
    prepare.add_argument("--force-prose-receipt", action="store_true")
    prepare.add_argument("--force-emotional-receipt", action="store_true")
    prepare.add_argument("--prose-plan")
    prepare.add_argument("--emotional-plan")
    prepare.add_argument("--beat-mapping")
    prepare.add_argument("--outline-contract")

    validate = sub.add_parser("validate")
    validate.add_argument("--prose-receipt", required=True)
    validate.add_argument("--emotional-receipt", required=True)
    validate.add_argument("--source-original", required=True)
    validate.add_argument("--source-emotion-ledger", required=True)
    validate.add_argument("--outline", required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        errors, summary = prepare_batch(
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
            outline_contract=Path(args.outline_contract).resolve() if args.outline_contract else None,
        )
        if errors:
            print("batch_draft_prewrite: blocked (prepare)")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_draft_prewrite: prepared")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0

    errors, summary = validate_batch(
        prose_receipt=Path(args.prose_receipt).resolve(),
        emotional_receipt=Path(args.emotional_receipt).resolve(),
        source_original=Path(args.source_original).resolve(),
        source_emotion_ledger=Path(args.source_emotion_ledger).resolve(),
        outline=Path(args.outline).resolve(),
    )
    if errors:
        print("batch_draft_prewrite: blocked (validate)")
        for item in errors:
            print(f"- {item}")
        return 2
    print("batch_draft_prewrite: passed")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
