#!/usr/bin/env python3
"""Validate the mandatory rule/source revision before window analysis."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

try:
    from count_words import count_fanqie
except ModuleNotFoundError:
    _count_words_path = Path(__file__).with_name("count_words.py")
    _count_words_spec = importlib.util.spec_from_file_location(
        "story_short_write_count_words",
        _count_words_path,
    )
    if not _count_words_spec or not _count_words_spec.loader:
        raise
    _count_words_module = importlib.util.module_from_spec(_count_words_spec)
    _count_words_spec.loader.exec_module(_count_words_module)
    count_fanqie = _count_words_module.count_fanqie


VALID_MODES = {"script", "human", "hybrid"}
SOURCE_GRANULARITY_FIELDS = {
    "sentence_rhythm",
    "narrator_interjection",
    "dialogue_action_ratio",
    "information_release",
    "explanation_density",
    "scene_ending",
    "manual_judgment",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def receipt_ref(path: Path, gate_key: str) -> dict[str, Any]:
    data = load(path)
    return {
        "path": str(path),
        "sha256": sha256(path),
        "gate_status": data.get(gate_key),
    }


def ledger_pre_window_ready(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = data.get("gate_status")
    if status == "passed":
        return errors
    if status != "pending":
        return [f"规则执行台账状态不允许进入窗口前回修: gate_status={status!r}"]

    entries: list[dict[str, Any]] = []
    for entry in data.get("skill_rules", []):
        if isinstance(entry, dict):
            entries.append(entry)
    for asset in data.get("source_assets", []):
        if isinstance(asset, dict):
            entries.append(asset)
            for rule in asset.get("rules", []):
                if isinstance(rule, dict):
                    entries.append(rule)

    unconfirmed: list[str] = []
    for entry in entries:
        if entry.get("applicability") == "merged":
            continue
        if not str(entry.get("rule_text") or "").strip():
            continue
        if entry.get("classification_confirmed") is not True:
            unconfirmed.append(str(entry.get("id") or "<unknown>"))
            continue
        if entry.get("mode_confirmed") is not True:
            unconfirmed.append(str(entry.get("id") or "<unknown>"))
    if unconfirmed:
        preview = " / ".join(unconfirmed[:20])
        suffix = " ..." if len(unconfirmed) > 20 else ""
        errors.append(f"规则执行台账尚未完成写前分类确认: {preview}{suffix}")
    return errors


def create_receipt(
    project: str,
    text_path: Path,
    output: Path,
    imitation_mode: bool = False,
    source_paths: list[Path] | None = None,
) -> None:
    text = text_path.read_text(encoding="utf-8")
    sources = [path.resolve() for path in (source_paths or [])]
    if imitation_mode and not sources:
        raise ValueError("仿写模式必须至少传入一个 --source 原文")
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise ValueError("原文不存在: " + " / ".join(missing))
    base_text_path = output.parent / "窗口前回修母稿.md"
    base_text_path.parent.mkdir(parents=True, exist_ok=True)
    base_text_path.write_text(text, encoding="utf-8")
    data = {
        "version": "1.1",
        "project": project,
        "status": "pending",
        "execution_mode": "current_model_manual",
        "window_order": "pre_window_revision_before_segmentation",
        "text": {
            "path": str(text_path),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "char_count": len(text),
            "word_count": count_fanqie(text),
            "word_count_rule": "fanqie_non_whitespace_without_markdown_headings",
        },
        "base_text": {
            "path": str(base_text_path.resolve()),
            "sha256": sha256(base_text_path),
        },
        "imitation_mode": imitation_mode,
        "selected_sources": [
            {"path": str(path), "sha256": sha256(path)} for path in sources
        ],
        "source_granularity_baseline": {
            "source_evidence": [],
            **{field: "" for field in sorted(SOURCE_GRANULARITY_FIELDS)},
        },
        "prerequisites": {
            "writing_rule_receipt": None,
            "source_read_receipt": None,
            "rule_execution_ledger": None,
        },
        "required_readings": [
            "references/anti-ai-writing.md",
            "references/craft/narrator-voice.md",
        ],
        "rule_families_applied": [],
        "source_assets_applied": [],
        "revision_items": [],
        "revision_blocks": [],
        "manual_summary": "",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_binding(value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return None
    path = Path(str(value.get("path") or "")).expanduser().resolve()
    if not path.is_file():
        errors.append(f"{label}不存在: {path}")
        return None
    if value.get("sha256") != sha256(path):
        errors.append(f"{label} SHA 已变化")
    return path


def validate_imitation_revision(
    data: dict[str, Any],
    text: str,
    errors: list[str],
) -> None:
    base_path = validate_binding(data.get("base_text"), "窗口前回修母稿", errors)
    base_text = base_path.read_text(encoding="utf-8") if base_path else ""
    source_texts: dict[str, str] = {}
    sources = data.get("selected_sources")
    if not isinstance(sources, list) or not sources:
        errors.append("仿写窗口前回修必须绑定 selected_sources")
    else:
        for index, binding in enumerate(sources, start=1):
            path = validate_binding(binding, f"selected_sources[{index}]", errors)
            if path:
                source_texts[str(path)] = path.read_text(encoding="utf-8")

    baseline = data.get("source_granularity_baseline")
    if not isinstance(baseline, dict):
        errors.append("仿写窗口前回修缺少 source_granularity_baseline")
    else:
        for field in SOURCE_GRANULARITY_FIELDS:
            if not str(baseline.get(field) or "").strip():
                errors.append(f"source_granularity_baseline.{field} 不能为空")
        evidence = baseline.get("source_evidence")
        if not isinstance(evidence, list) or len(evidence) < 2:
            errors.append("source_granularity_baseline.source_evidence 至少需要两条原文证据")
        else:
            distinct_quotes: set[str] = set()
            for index, item in enumerate(evidence, start=1):
                if not isinstance(item, dict):
                    errors.append(f"原文颗粒证据格式错误[{index}]")
                    continue
                source_path = Path(str(item.get("source_path") or "")).expanduser().resolve()
                source_text = source_texts.get(str(source_path))
                quote = str(item.get("quote") or "").strip()
                if source_text is None:
                    errors.append(f"原文颗粒证据未绑定选中原文[{index}]")
                elif item.get("source_sha256") != sha256(source_path):
                    errors.append(f"原文颗粒证据 SHA 不一致[{index}]")
                elif not quote or quote not in source_text:
                    errors.append(f"原文颗粒证据不在原文中[{index}]")
                if quote:
                    distinct_quotes.add(quote)
                if not str(item.get("function") or "").strip():
                    errors.append(f"原文颗粒证据缺少功能判断[{index}]")
            if len(distinct_quotes) < 2:
                errors.append("原文颗粒证据不得用同一句重复充数")

    items = data.get("revision_items")
    text_changed = any(
        isinstance(item, dict) and item.get("text_changed") is True
        for item in items or []
    )
    if any(isinstance(item, dict) and not isinstance(item.get("text_changed"), bool) for item in items or []):
        errors.append("仿写窗口前回修项必须逐项填写 text_changed=true/false")
    blocks = data.get("revision_blocks")
    if text_changed and (not isinstance(blocks, list) or not blocks):
        errors.append("仿写窗口前回修修改正文后必须填写 revision_blocks")
        return
    if text_changed and base_path and sha256(base_path) == hashlib.sha256(text.encode("utf-8")).hexdigest():
        errors.append("已声明正文发生回修，但母稿与改后正文 SHA 相同；禁止改后重建母稿")
    for index, block in enumerate(blocks or [], start=1):
        label = f"revision_blocks[{index}]"
        if not isinstance(block, dict):
            errors.append(f"{label} 必须是对象")
            continue
        for field in (
            "target_block",
            "preserved_source_granularity",
            "removed_draft_extra_ai_shell",
            "manual_judgment",
        ):
            if not str(block.get(field) or "").strip():
                errors.append(f"{label}.{field} 不能为空")
        source_path = Path(str(block.get("source_path") or "")).expanduser().resolve()
        source_text = source_texts.get(str(source_path))
        if source_text is None:
            errors.append(f"{label}.source_path 必须绑定选中原文")
        elif block.get("source_sha256") != sha256(source_path):
            errors.append(f"{label}.source_sha256 与原文不一致")
        source_evidence = block.get("source_evidence")
        if not isinstance(source_evidence, list) or len({str(x).strip() for x in source_evidence if str(x).strip()}) < 2:
            errors.append(f"{label}.source_evidence 至少需要两条不同原文证据")
        elif source_text is not None:
            for quote in source_evidence:
                if str(quote).strip() not in source_text:
                    errors.append(f"{label}.source_evidence 不在原文中: {quote!r}")
        for field, haystack in (("base_text_evidence", base_text), ("revised_text_evidence", text)):
            evidence = block.get(field)
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{label}.{field} 至少需要一条证据")
            else:
                for quote in evidence:
                    if not str(quote).strip() or str(quote).strip() not in haystack:
                        errors.append(f"{label}.{field} 不在对应文本中: {quote!r}")
        if block.get("base_text_evidence") == block.get("revised_text_evidence"):
            errors.append(f"{label} 母稿证据与改后证据不能完全相同")
        for field in (
            "no_added_explanation_density",
            "no_source_rhythm_regularization",
            "surface_copy_check",
        ):
            if block.get(field) is not True:
                errors.append(f"{label}.{field} 必须为 true")


def validate(receipt_path: Path, text_path: Path) -> list[str]:
    errors: list[str] = []
    data = load(receipt_path)
    text = text_path.read_text(encoding="utf-8")
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    if data.get("status") != "completed":
        errors.append("窗口前规则/资产定向回修回执 status 必须为 completed")
    if data.get("execution_mode") != "current_model_manual":
        errors.append("窗口前回修必须由当前执行 skill 的模型人工完成")
    if data.get("window_order") != "pre_window_revision_before_segmentation":
        errors.append("窗口前回修顺序标记不正确")

    binding = data.get("text") if isinstance(data.get("text"), dict) else {}
    if Path(str(binding.get("path") or "")).resolve() != text_path.resolve():
        errors.append("窗口前回修回执绑定的正文路径不一致")
    if binding.get("sha256") != text_sha:
        errors.append("正文 SHA 已变化，必须重新执行窗口前规则/资产定向回修")
    if binding.get("char_count") != len(text):
        errors.append("正文字符数已变化，必须重新执行窗口前规则/资产定向回修")
    if binding.get("word_count") != count_fanqie(text):
        errors.append("正文统一字数已变化，必须重新执行窗口前规则/资产定向回修")

    if data.get("imitation_mode") is True:
        validate_imitation_revision(data, text, errors)

    prereqs = data.get("prerequisites")
    if not isinstance(prereqs, dict):
        errors.append("缺少窗口前回修前置门禁回执")
        prereqs = {}
    for key, gate_key in (
        ("writing_rule_receipt", "gate_status"),
        ("source_read_receipt", "gate_status"),
        ("rule_execution_ledger", "gate_status"),
    ):
        item = prereqs.get(key)
        if not isinstance(item, dict):
            errors.append(f"缺少前置回执: {key}")
            continue
        path = Path(str(item.get("path") or "")).resolve()
        if not path.is_file():
            errors.append(f"前置回执不存在: {path}")
            continue
        if item.get("sha256") != sha256(path):
            errors.append(f"前置回执 SHA 已变化: {path}")
        try:
            source = load(path)
        except json.JSONDecodeError:
            errors.append(f"前置回执不是有效 JSON: {path}")
            continue
        if key == "rule_execution_ledger":
            errors.extend(ledger_pre_window_ready(source))
        elif source.get(gate_key) != "passed":
            errors.append(f"前置回执未通过: {path}")

    readings = data.get("required_readings")
    if not isinstance(readings, list) or not any("anti-ai-writing.md" in str(x) for x in readings):
        errors.append("窗口前回修未声明 anti-ai-writing.md")
    if not isinstance(readings, list) or not any("narrator-voice.md" in str(x) for x in readings):
        errors.append("窗口前回修未声明 narrator-voice.md")

    families = data.get("rule_families_applied")
    if not isinstance(families, list) or not families:
        errors.append("窗口前回修缺少已执行的 skill 规则族")
    assets = data.get("source_assets_applied")
    if not isinstance(assets, list) or not assets:
        errors.append("窗口前回修缺少已执行的拆书资产")

    items = data.get("revision_items")
    if not isinstance(items, list) or not items:
        errors.append("窗口前回修缺少逐项执行记录")
    else:
        for index, item in enumerate(items, 1):
            if not isinstance(item, dict):
                errors.append(f"窗口前回修项格式错误[{index}]")
                continue
            if item.get("status") != "completed":
                errors.append(f"窗口前回修项未完成[{index}]")
            if item.get("execution_mode") not in VALID_MODES:
                errors.append(f"窗口前回修项执行方式无效[{index}]")
            if not str(item.get("rule_or_asset") or "").strip():
                errors.append(f"窗口前回修项缺少规则或资产名称[{index}]")
            evidence = item.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"窗口前回修项缺少正文证据[{index}]")
                continue
            for evidence_item in evidence:
                if not isinstance(evidence_item, dict):
                    errors.append(f"窗口前回修项正文证据格式错误[{index}]")
                    continue
                quote = str(evidence_item.get("quote") or "").strip()
                if not quote or quote not in text:
                    errors.append(f"窗口前回修项正文证据不在当前正文[{index}]")
                if not str(evidence_item.get("judgment") or "").strip():
                    errors.append(f"窗口前回修项缺少人工判断[{index}]")

    if not str(data.get("manual_summary") or "").strip():
        errors.append("窗口前回修缺少人工总结")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate rule/source revision before window analysis.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--text", required=True)
    init.add_argument("--receipt", required=True)
    init.add_argument("--imitation-mode", action="store_true")
    init.add_argument("--source", action="append", default=[])

    check = sub.add_parser("validate")
    check.add_argument("--receipt", required=True)
    check.add_argument("--text", required=True)

    args = parser.parse_args()
    if args.command == "init":
        try:
            create_receipt(
                args.project,
                Path(args.text).resolve(),
                Path(args.receipt).resolve(),
                imitation_mode=args.imitation_mode,
                source_paths=[Path(path).resolve() for path in args.source],
            )
        except (OSError, ValueError) as exc:
            print(f"pre_window_revision_gate: blocked\n- {exc}")
            return 2
        print("pre_window_revision_gate: initialized")
        return 0

    errors = validate(Path(args.receipt).resolve(), Path(args.text).resolve())
    if errors:
        print("pre_window_revision_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("pre_window_revision_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
