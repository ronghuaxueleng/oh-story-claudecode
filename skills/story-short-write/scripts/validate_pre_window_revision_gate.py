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


def create_receipt(project: str, text_path: Path, output: Path) -> None:
    text = text_path.read_text(encoding="utf-8")
    data = {
        "version": "1.0",
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
        "manual_summary": "",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        if source.get(gate_key) != "passed":
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

    check = sub.add_parser("validate")
    check.add_argument("--receipt", required=True)
    check.add_argument("--text", required=True)

    args = parser.parse_args()
    if args.command == "init":
        create_receipt(args.project, Path(args.text).resolve(), Path(args.receipt).resolve())
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
