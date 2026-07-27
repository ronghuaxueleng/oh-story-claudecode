#!/usr/bin/env python3
"""Enforce open-write-close sequencing for source-bound short-story sections."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(r"(?m)^(\d+)\.\s*$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256(path)}


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



def draft_section_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return SECTION_RE.findall(path.read_text(encoding="utf-8"))


def section_text(path: Path, section_id: str) -> str:
    text = path.read_text(encoding="utf-8")
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1) != section_id:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[match.end() : end].strip()
    return ""


def check_binding(value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return None
    path = Path(str(value.get("path") or "")).expanduser().resolve()
    if not path.is_file():
        errors.append(f"{label} 文件不存在: {path}")
        return None
    if value.get("sha256") != sha256(path):
        errors.append(f"{label} SHA 已变化")
    return path


def validate_receipt(path: Path, require_complete: bool = False) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"回执无法读取: {exc}"]
    if data.get("gate") != "section_draft_execution":
        errors.append("gate 必须为 section_draft_execution")
    check_binding(data.get("outline_contract"), "outline_contract", errors)
    check_binding(data.get("source_receipt"), "source_receipt", errors)
    check_binding(data.get("section_source_bundle"), "section_source_bundle", errors)
    draft = Path(str(data.get("draft_path") or "")).expanduser().resolve()
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return data, errors + ["sections 必须是非空数组"]
    expected_ids = [str(item.get("section_id") or "") for item in sections if isinstance(item, dict)]
    completed_ids: list[str] = []
    open_count = 0
    for item in sections:
        if not isinstance(item, dict):
            errors.append("sections 含非对象")
            continue
        status = item.get("status")
        section_id = str(item.get("section_id") or "")
        if status == "completed":
            completed_ids.append(section_id)
            for field in ("opened_at", "closed_at", "read_judgment", "manual_judgment", "section_sha256", "draft_sha256_after_close"):
                if not str(item.get(field) or "").strip():
                    errors.append(f"第 {section_id} 节缺少 {field}")
            for field in ("event_flow", "emotion_flow", "style_granularity", "telegraphic_and_relation_check"):
                if item.get(field) != "passed":
                    errors.append(f"第 {section_id} 节 {field} 必须为 passed")
        elif status == "open":
            open_count += 1
        elif status != "pending":
            errors.append(f"第 {section_id} 节 status 无效: {status!r}")
    if open_count > 1:
        errors.append("同时只能打开一个小节")
    actual_ids = draft_section_ids(draft)
    allowed_ids = completed_ids + [
        str(item.get("section_id")) for item in sections if isinstance(item, dict) and item.get("status") == "open"
    ]
    if actual_ids != allowed_ids:
        errors.append(
            "正文小节与逐节执行状态不一致；禁止先批量写完再补回执: "
            f"正文={actual_ids}, 已放行={allowed_ids}"
        )
    if require_complete:
        if completed_ids != expected_ids:
            errors.append("所有小节必须按顺序逐节完成")
        if not draft.is_file() or data.get("final_draft_sha256") != sha256(draft):
            errors.append("最终正文 SHA 未绑定或已变化")
        if data.get("gate_status") != "passed":
            errors.append("gate_status 必须为 passed")
    return data, errors


def init_receipt(
    outline_contract: Path,
    source_receipt: Path,
    section_source_bundle: Path,
    draft: Path,
    receipt: Path,
) -> int:
    if receipt.exists():
        print(f"逐节首写执行回执已存在，拒绝覆盖: {receipt}")
        return 2
    outline = read_json(outline_contract)
    source = read_json(source_receipt)
    bundle = read_json(section_source_bundle)
    if outline.get("gate_status") != "passed" or source.get("gate_status") != "passed":
        print("section_draft_execution: blocked\n- 细纲表演契约和拆文读取回执必须先通过")
        return 2
    if bundle.get("gate_status") != "passed":
        print("section_draft_execution: blocked\n- 逐节原文颗粒包必须先通过")
        return 2
    if draft_section_ids(draft):
        print("section_draft_execution: blocked\n- 正文已经含数字小节，禁止事后初始化逐节回执")
        return 2
    packets = {
        str(item.get("section_id") or ""): item
        for item in bundle.get("packets", [])
        if isinstance(item, dict)
    }
    sections = []
    for item in outline.get("sections", []):
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "")
        contract = item.get("first_draft_generation_contract")
        bindings = contract.get("source_slice_bindings") if isinstance(contract, dict) else None
        if not isinstance(bindings, list) or not bindings:
            print("section_draft_execution: blocked\n- 每节必须先绑定 source_slice_bindings")
            return 2
        packet = packets.get(section_id)
        if not packet:
            print(f"section_draft_execution: blocked\n- 第 {section_id} 节缺少逐节原文颗粒包")
            return 2
        sections.append({
            "section_id": section_id,
            "status": "pending",
            "granularity_packet_id": str(packet.get("packet_id") or ""),
            "granularity_packet_sha256": str(packet.get("packet_sha256") or ""),
            "source_slice_bindings": bindings,
            "opened_at": "",
            "closed_at": "",
            "read_judgment": "",
            "manual_judgment": "",
            "event_flow": "pending",
            "emotion_flow": "pending",
            "style_granularity": "pending",
            "telegraphic_and_relation_check": "pending",
            "section_sha256": "",
            "draft_sha256_after_close": "",
        })
    data = {
        "version": "1.0",
        "gate": "section_draft_execution",
        "outline_contract": binding(outline_contract),
        "source_receipt": binding(source_receipt),
        "section_source_bundle": binding(section_source_bundle),
        "draft_path": str(draft.resolve()),
        "sections": sections,
        "final_draft_sha256": "",
        "gate_status": "active",
    }
    write_json(receipt, data)
    print("section_draft_execution: initialized")
    return 0


def open_section(receipt: Path, section_id: str, read_judgment: str) -> int:
    data, errors = validate_receipt(receipt)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    sections = data["sections"]
    target = next((item for item in sections if item["section_id"] == section_id), None)
    if not target or target["status"] != "pending":
        print("section_draft_execution: blocked\n- 目标小节不存在或不是 pending")
        return 2
    previous = [item["section_id"] for item in sections[: sections.index(target)]]
    completed = [item["section_id"] for item in sections if item["status"] == "completed"]
    if completed != previous:
        print("section_draft_execution: blocked\n- 必须按顺序完成上一节")
        return 2
    target["status"] = "open"
    target["opened_at"] = now_iso()
    target["read_judgment"] = read_judgment.strip()
    if not target["read_judgment"]:
        print("section_draft_execution: blocked\n- read-judgment 不能为空")
        return 2
    if not target.get("granularity_packet_id") or not target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节缺少逐节原文颗粒包绑定")
        return 2
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} open")
    return 0


def close_section(receipt: Path, section_id: str, judgment: str) -> int:
    data, errors = validate_receipt(receipt)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    target = next((item for item in data["sections"] if item["section_id"] == section_id), None)
    if not target or target["status"] != "open":
        print("section_draft_execution: blocked\n- 目标小节尚未 open")
        return 2
    draft = Path(data["draft_path"])
    content = section_text(draft, section_id)
    if not content:
        print("section_draft_execution: blocked\n- 当前小节正文为空")
        return 2
    target.update({
        "status": "completed",
        "closed_at": now_iso(),
        "manual_judgment": judgment.strip(),
        "event_flow": "passed",
        "emotion_flow": "passed",
        "style_granularity": "passed",
        "telegraphic_and_relation_check": "passed",
        "section_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "draft_sha256_after_close": sha256(draft),
    })
    if not target["manual_judgment"]:
        print("section_draft_execution: blocked\n- judgment 不能为空")
        return 2
    if all(item["status"] == "completed" for item in data["sections"]):
        data["final_draft_sha256"] = sha256(draft)
        data["gate_status"] = "passed"
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} completed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--outline-contract", required=True)
    init.add_argument("--source-receipt", required=True)
    init.add_argument("--section-source-bundle", required=True)
    init.add_argument("--draft", required=True)
    init.add_argument("--receipt", required=True)
    opening = sub.add_parser("open-section")
    opening.add_argument("--receipt", required=True)
    opening.add_argument("--section", required=True)
    opening.add_argument("--read-judgment", required=True)
    closing = sub.add_parser("close-section")
    closing.add_argument("--receipt", required=True)
    closing.add_argument("--section", required=True)
    closing.add_argument("--judgment", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    args = parser.parse_args()
    receipt = Path(getattr(args, "receipt", "")).resolve()
    if args.command == "init":
        return init_receipt(
            Path(args.outline_contract).resolve(),
            Path(args.source_receipt).resolve(),
            Path(args.section_source_bundle).resolve(),
            Path(args.draft).resolve(),
            receipt,
        )
    if args.command == "open-section":
        return open_section(receipt, args.section, args.read_judgment)
    if args.command == "close-section":
        return close_section(receipt, args.section, args.judgment)
    _, errors = validate_receipt(receipt, require_complete=True)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    print("section_draft_execution: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
