#!/usr/bin/env python3
"""Validate the setting -> outline -> draft sequence contract."""

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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{label}不存在: {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label}不是有效 JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}必须是 JSON 对象")
        return None
    return value


def text_evidence(
    evidence: Any,
    text: str,
    label: str,
    errors: list[str],
    *,
    require_offset: bool = False,
) -> list[int]:
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{label}缺少逐项原句证据")
        return []
    offsets: list[int] = []
    for index, item in enumerate(evidence, 1):
        if not isinstance(item, dict):
            errors.append(f"{label}证据格式错误[{index}]")
            continue
        quote = str(item.get("quote") or "")
        if not quote or quote not in text:
            errors.append(f"{label}原句不在绑定产物中[{index}]")
        if not str(item.get("judgment") or "").strip():
            errors.append(f"{label}缺少人工判断[{index}]")
        if require_offset:
            raw_offset = item.get("offset")
            if not isinstance(raw_offset, int) or raw_offset < 0:
                errors.append(f"{label}缺少有效 offset[{index}]")
            elif text[raw_offset : raw_offset + len(quote)] != quote:
                errors.append(f"{label}offset 与原句不一致[{index}]")
            else:
                offsets.append(raw_offset)
    return offsets


def validate_common(data: dict[str, Any], errors: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if data.get("gate_status") != "passed":
        errors.append("顺序契约 gate_status 必须为 passed")
    if data.get("status") != "completed":
        errors.append("顺序契约 status 必须为 completed")
    if data.get("execution_mode") != "current_model_manual":
        errors.append("顺序契约必须由当前执行 skill 的模型人工完成")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("顺序契约缺少 artifacts 绑定")
        artifacts = {}
    sequence = data.get("canonical_sequence")
    if not isinstance(sequence, list) or len(sequence) < 2:
        errors.append("canonical_sequence 至少需要两个顺序节点")
        sequence = []
    ids: list[str] = []
    for index, item in enumerate(sequence, 1):
        if not isinstance(item, dict):
            errors.append(f"顺序节点格式错误[{index}]")
            continue
        node_id = str(item.get("id") or "").strip()
        if not node_id:
            errors.append(f"顺序节点缺少 id[{index}]")
        elif node_id in ids:
            errors.append(f"顺序节点 id 重复: {node_id}")
        else:
            ids.append(node_id)
        if not str(item.get("label") or "").strip():
            errors.append(f"顺序节点缺少 label[{index}]")
    return artifacts, sequence


def validate_setting(
    receipt_path: Path,
    setting_path: Path,
) -> list[str]:
    errors: list[str] = []
    data = load_json(receipt_path, "设定顺序契约回执", errors)
    if data is None:
        return errors
    if data.get("scope") != "setting":
        errors.append("设定顺序契约 scope 必须为 setting")
    artifacts, sequence = validate_common(data, errors)
    binding = artifacts.get("setting")
    if not isinstance(binding, dict):
        errors.append("设定顺序契约缺少 setting 绑定")
    elif Path(str(binding.get("path") or "")).resolve() != setting_path.resolve():
        errors.append("设定顺序契约 setting 路径不一致")
    elif binding.get("sha256") != sha256(setting_path):
        errors.append("设定 SHA 已变化，必须重新审查设定内部顺序")

    text = setting_path.read_text(encoding="utf-8") if setting_path.is_file() else ""
    setting_offsets: list[int] = []
    for index, item in enumerate(sequence, 1):
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or index)
        setting_offsets.extend(
            text_evidence(
                item.get("setting_evidence"),
                text,
                f"顺序节点 {node_id} / setting",
                errors,
                require_offset=True,
            )
        )
    if setting_offsets and setting_offsets != sorted(setting_offsets):
        errors.append("设定内部 canonical 顺序与原文实际位置倒序")

    review = data.get("conflict_review")
    if not isinstance(review, dict):
        errors.append("缺少设定内部顺序冲突审查")
    else:
        if review.get("setting_internal_status") != "passed":
            errors.append("设定内部顺序冲突审查未通过")
        findings = review.get("findings")
        if not isinstance(findings, list):
            errors.append("设定内部冲突 findings 必须是列表")
        else:
            for index, finding in enumerate(findings, 1):
                if not isinstance(finding, dict):
                    errors.append(f"设定内部冲突条目格式错误[{index}]")
                    continue
                if finding.get("status") != "resolved":
                    errors.append(f"仍有未解决的设定内部顺序冲突[{index}]")
                if not str(finding.get("resolution") or "").strip():
                    errors.append(f"设定内部顺序冲突缺少解决方案[{index}]")
                if not str(finding.get("setting_evidence") or "").strip():
                    errors.append(f"设定内部顺序冲突缺少 setting_evidence[{index}]")
    if not str(data.get("manual_judgment") or "").strip():
        errors.append("设定顺序契约缺少人工总判断")
    return errors


def validate(
    receipt_path: Path,
    setting_path: Path,
    outline_path: Path,
    draft_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    data = load_json(receipt_path, "顺序契约回执", errors)
    if data is None:
        return errors
    if data.get("scope") != "full":
        errors.append("设定—大纲—正文顺序契约 scope 必须为 full")
    artifacts, sequence = validate_common(data, errors)
    expected = {
        "setting": setting_path.resolve(),
        "outline": outline_path.resolve(),
    }
    if draft_path is not None:
        expected["draft"] = draft_path.resolve()
    texts: dict[str, str] = {}
    for key, path in expected.items():
        binding = artifacts.get(key)
        if not isinstance(binding, dict):
            errors.append(f"顺序契约缺少 {key} 绑定")
            continue
        if Path(str(binding.get("path") or "")).resolve() != path:
            errors.append(f"顺序契约 {key} 路径不一致")
        if not path.is_file():
            errors.append(f"顺序契约 {key} 产物不存在: {path}")
            continue
        if binding.get("sha256") != sha256(path):
            errors.append(f"顺序契约 {key} SHA 已变化，必须重新审查")
        texts[key] = path.read_text(encoding="utf-8")

    conflict_review = data.get("conflict_review")
    if not isinstance(conflict_review, dict):
        errors.append("缺少设定内部及设定/大纲冲突审查")
    else:
        if conflict_review.get("status") != "passed":
            errors.append("设定/大纲冲突审查未通过")
        findings = conflict_review.get("findings")
        if not isinstance(findings, list):
            errors.append("冲突审查 findings 必须是列表")
        else:
            for index, finding in enumerate(findings, 1):
                if not isinstance(finding, dict):
                    errors.append(f"冲突审查条目格式错误[{index}]")
                    continue
                if finding.get("status") != "resolved":
                    errors.append(f"仍有未解决的顺序冲突[{index}]")
                if not str(finding.get("resolution") or "").strip():
                    errors.append(f"顺序冲突缺少解决方案[{index}]")
                for evidence_key in ("setting_evidence", "outline_evidence"):
                    if not str(finding.get(evidence_key) or "").strip():
                        errors.append(f"顺序冲突缺少 {evidence_key}[{index}]")

    ids: list[str] = []
    draft_offsets: list[int] = []
    setting_offsets: list[int] = []
    outline_offsets: list[int] = []
    for index, item in enumerate(sequence, 1):
        if not isinstance(item, dict):
            errors.append(f"顺序节点格式错误[{index}]")
            continue
        node_id = str(item.get("id") or index)
        setting_offsets.extend(text_evidence(
            item.get("setting_evidence"),
            texts.get("setting", ""),
            f"顺序节点 {node_id} / setting",
            errors,
            require_offset=True,
        ))
        outline_offsets.extend(text_evidence(
            item.get("outline_evidence"),
            texts.get("outline", ""),
            f"顺序节点 {node_id} / outline",
            errors,
            require_offset=True,
        ))
        if draft_path is not None:
            draft_offsets.extend(
                text_evidence(
                    item.get("draft_evidence"),
                    texts.get("draft", ""),
                    f"顺序节点 {node_id} / draft",
                    errors,
                    require_offset=True,
                )
            )

    if setting_offsets and setting_offsets != sorted(setting_offsets):
        errors.append("设定顺序与 canonical_sequence 不一致：节点实际出现位置倒序")
    if outline_offsets and outline_offsets != sorted(outline_offsets):
        errors.append("大纲顺序与 canonical_sequence 不一致：节点实际出现位置倒序")
    if draft_path is not None and draft_offsets:
        if draft_offsets != sorted(draft_offsets):
            errors.append("正文顺序与 canonical_sequence 不一致：节点实际出现位置倒序")
        if len(draft_offsets) != len(sequence):
            errors.append("正文顺序证据数量必须与 canonical_sequence 节点数量一致")

    if not str(data.get("manual_judgment") or "").strip():
        errors.append("顺序契约缺少人工总判断")
    return errors


def init_receipt(project: str, setting: Path, outline: Path, draft: Path | None, output: Path) -> None:
    artifacts: dict[str, Any] = {}
    for key, path in (("setting", setting), ("outline", outline), ("draft", draft)):
        if path is None:
            continue
        text = path.read_text(encoding="utf-8")
        artifacts[key] = {
            "path": str(path.resolve()),
            "sha256": sha256(path.resolve()),
            "char_count": len(text),
            "word_count": count_fanqie(text),
            "word_count_rule": "fanqie_non_whitespace_without_markdown_headings",
        }
    payload = {
        "version": "1.0",
        "project": project,
        "scope": "full",
        "status": "pending",
        "gate_status": "pending",
        "execution_mode": "current_model_manual",
        "artifacts": artifacts,
        "conflict_review": {
            "status": "pending",
            "findings": [],
        },
        "canonical_sequence": [],
        "manual_judgment": "",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_setting_receipt(project: str, setting: Path, output: Path) -> None:
    path = setting.resolve()
    text = path.read_text(encoding="utf-8")
    payload = {
        "version": "1.0",
        "project": project,
        "scope": "setting",
        "status": "pending",
        "gate_status": "pending",
        "execution_mode": "current_model_manual",
        "artifacts": {
            "setting": {
                "path": str(path),
                "sha256": sha256(path),
                "char_count": len(text),
                "word_count": count_fanqie(text),
                "word_count_rule": "fanqie_non_whitespace_without_markdown_headings",
            }
        },
        "conflict_review": {
            "setting_internal_status": "pending",
            "findings": [],
        },
        "canonical_sequence": [],
        "manual_judgment": "",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate setting/outline/draft order contract.")
    sub = parser.add_subparsers(dest="command", required=True)
    init_setting = sub.add_parser("init-setting")
    init_setting.add_argument("--project", required=True)
    init_setting.add_argument("--setting", required=True)
    init_setting.add_argument("--receipt", required=True)
    validate_setting_parser = sub.add_parser("validate-setting")
    validate_setting_parser.add_argument("--receipt", required=True)
    validate_setting_parser.add_argument("--setting", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--setting", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--draft")
    init.add_argument("--receipt", required=True)
    check = sub.add_parser("validate")
    check.add_argument("--receipt", required=True)
    check.add_argument("--setting", required=True)
    check.add_argument("--outline", required=True)
    check.add_argument("--draft")
    args = parser.parse_args()
    if args.command == "init-setting":
        init_setting_receipt(
            args.project,
            Path(args.setting),
            Path(args.receipt),
        )
        print("setting_sequence_contract_gate: initialized")
        return 0
    if args.command == "validate-setting":
        errors = validate_setting(
            Path(args.receipt).resolve(),
            Path(args.setting).resolve(),
        )
        if errors:
            print("setting_sequence_contract_gate: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("setting_sequence_contract_gate: passed")
        return 0
    if args.command == "init":
        init_receipt(
            args.project,
            Path(args.setting),
            Path(args.outline),
            Path(args.draft) if args.draft else None,
            Path(args.receipt),
        )
        print("sequence_contract_gate: initialized")
        return 0
    errors = validate(
        Path(args.receipt).resolve(),
        Path(args.setting).resolve(),
        Path(args.outline).resolve(),
        Path(args.draft).resolve() if args.draft else None,
    )
    if errors:
        print("sequence_contract_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("sequence_contract_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
