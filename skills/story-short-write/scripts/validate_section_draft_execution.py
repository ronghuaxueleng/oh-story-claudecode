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
STYLE_DIMENSIONS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)


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


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def source_excerpt(path: Path, source_range: str) -> tuple[str, list[tuple[int, int]]]:
    lines = read_text(path).splitlines()
    ranges = [(int(start), int(end)) for start, end in re.findall(r"L(\d+)-L(\d+)", source_range)]
    if not ranges:
        raise ValueError(f"非法 source_range: {source_range!r}")
    excerpts: list[str] = []
    for start, end in ranges:
        if start < 1 or end < start or end > len(lines):
            raise ValueError(f"source_range 越界: L{start}-L{end}，原文共 {len(lines)} 行")
        excerpts.append("\n".join(lines[start - 1 : end]))
    return "\n".join(excerpts), ranges


def section_review_path(receipt: Path, section_id: str) -> Path:
    return receipt.parent / "逐节首写停检" / f"第{section_id}节.json"


def review_check_template() -> dict[str, Any]:
    return {
        "status": "pending",
        "source_evidence": [],
        "target_evidence": [],
        "judgment": "",
    }



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
            records = item.get("source_read_records")
            bindings = item.get("source_slice_bindings")
            if not isinstance(records, list) or not isinstance(bindings, list) or len(records) != len(bindings):
                errors.append(f"第 {section_id} 节必须登记全部原文精确切片实读记录")
            check_binding(item.get("review_receipt"), f"第 {section_id} 节 review_receipt", errors)
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
    force: bool = False,
) -> int:
    if receipt.exists() and not force:
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
            "source_read_records": [],
            "review_receipt": {},
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
    judgment = read_judgment.strip()
    if not judgment:
        print("section_draft_execution: blocked\n- read-judgment 不能为空")
        return 2
    if not target.get("granularity_packet_id") or not target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节缺少逐节原文颗粒包绑定")
        return 2
    bundle_path = Path(str(data["section_source_bundle"]["path"])).resolve()
    bundle = read_json(bundle_path)
    packet = next(
        (
            item
            for item in bundle.get("packets", [])
            if isinstance(item, dict) and str(item.get("section_id") or "") == section_id
        ),
        None,
    )
    if not packet or packet.get("packet_sha256") != target.get("granularity_packet_sha256"):
        print("section_draft_execution: blocked\n- 当前小节颗粒包不存在或 SHA 不一致")
        return 2
    payload = packet.get("payload")
    packet_bindings = payload.get("source_slice_bindings") if isinstance(payload, dict) else None
    if not isinstance(packet_bindings, list) or not packet_bindings:
        print("section_draft_execution: blocked\n- 当前小节颗粒包缺少原文切片")
        return 2
    read_records: list[dict[str, Any]] = []
    printable: list[tuple[dict[str, Any], str]] = []
    for index, item in enumerate(packet_bindings, start=1):
        if not isinstance(item, dict):
            print(f"section_draft_execution: blocked\n- 第 {index} 个原文切片不是对象")
            return 2
        source_path = Path(str(item.get("source_path") or "")).resolve()
        if not source_path.is_file() or item.get("source_sha256") != sha256(source_path):
            print(f"section_draft_execution: blocked\n- 原文文件不存在或 SHA 已变化: {source_path}")
            return 2
        try:
            excerpt, ranges = source_excerpt(source_path, str(item.get("source_range") or ""))
        except ValueError as exc:
            print(f"section_draft_execution: blocked\n- {exc}")
            return 2
        excerpt_sha = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        if item.get("source_excerpt_sha256") != excerpt_sha:
            print(f"section_draft_execution: blocked\n- 原文精确行段 SHA 已变化: {source_path}")
            return 2
        if set(item.get("style_fields_consumed") or []) != set(STYLE_DIMENSIONS):
            print("section_draft_execution: blocked\n- 原文切片未完整绑定六类文风颗粒")
            return 2
        read_records.append(
            {
                "source_path": str(source_path),
                "source_sha256": item["source_sha256"],
                "source_range": item["source_range"],
                "source_excerpt_sha256": excerpt_sha,
                "ranges": [{"start": start, "end": end} for start, end in ranges],
                "read_at": now_iso(),
            }
        )
        printable.append((item, excerpt))
    review_path = section_review_path(receipt, section_id)
    review = {
        "version": "1.0",
        "gate": "section_draft_review",
        "section_id": section_id,
        "draft_path": data["draft_path"],
        "source_read_records": read_records,
        "checks": {
            "event_flow": review_check_template(),
            "emotion_flow": review_check_template(),
            "style_granularity": {
                "status": "pending",
                "dimensions": {name: review_check_template() for name in STYLE_DIMENSIONS},
                "judgment": "",
            },
            "telegraphic_and_relation_check": review_check_template(),
        },
        "manual_judgment": "",
        "gate_status": "pending",
    }
    write_json(review_path, review)
    target["status"] = "open"
    target["opened_at"] = now_iso()
    target["read_judgment"] = judgment
    target["source_read_records"] = read_records
    target["review_receipt"] = {"path": str(review_path.resolve()), "sha256": sha256(review_path)}
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} open")
    print(f"review: {review_path}")
    for index, (item, excerpt) in enumerate(printable, start=1):
        print(f"--- source slice {index}: {item['source_path']} {item['source_range']} ---")
        print(excerpt)
        print(f"--- end source slice {index} ---")
    return 0


def validate_review(
    review_path: Path,
    section_id: str,
    draft: Path,
    content: str,
    source_read_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        review = read_json(review_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {}, [f"逐节停检回执不可读取: {exc}"]
    if review.get("gate") != "section_draft_review":
        errors.append("逐节停检 gate 必须为 section_draft_review")
    if str(review.get("section_id") or "") != section_id:
        errors.append("逐节停检 section_id 不一致")
    if Path(str(review.get("draft_path") or "")).resolve() != draft.resolve():
        errors.append("逐节停检绑定的正文路径不一致")
    if review.get("source_read_records") != source_read_records:
        errors.append("逐节停检没有完整继承本次原文实读记录")
    source_excerpts: list[str] = []
    for record in source_read_records:
        source_path = Path(str(record.get("source_path") or "")).resolve()
        if not source_path.is_file() or record.get("source_sha256") != sha256(source_path):
            errors.append(f"逐节停检绑定的原文不存在或 SHA 已变化: {source_path}")
            continue
        try:
            excerpt, _ = source_excerpt(source_path, str(record.get("source_range") or ""))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if record.get("source_excerpt_sha256") != hashlib.sha256(excerpt.encode("utf-8")).hexdigest():
            errors.append(f"逐节停检绑定的原文精确行段 SHA 已变化: {source_path}")
        source_excerpts.append(excerpt)

    def validate_check(name: str, value: Any, minimum: int = 2) -> None:
        if not isinstance(value, dict):
            errors.append(f"{name} 必须是对象")
            return
        if value.get("status") != "passed":
            errors.append(f"{name}.status 必须为 passed")
        if not str(value.get("judgment") or "").strip():
            errors.append(f"{name}.judgment 不能为空")
        source_evidence = value.get("source_evidence")
        target_evidence = value.get("target_evidence")
        if not isinstance(source_evidence, list) or len(source_evidence) < minimum:
            errors.append(f"{name}.source_evidence 至少需要 {minimum} 条")
        else:
            for quote in source_evidence:
                if not str(quote).strip() or not any(str(quote) in excerpt for excerpt in source_excerpts):
                    errors.append(f"{name} 原文证据不在本节实读切片内: {quote}")
        if not isinstance(target_evidence, list) or len(target_evidence) < minimum:
            errors.append(f"{name}.target_evidence 至少需要 {minimum} 条")
        else:
            for quote in target_evidence:
                if not str(quote).strip() or str(quote) not in content:
                    errors.append(f"{name} 目标证据不在当前小节正文内: {quote}")

    checks = review.get("checks")
    if not isinstance(checks, dict):
        return review, errors + ["逐节停检 checks 必须是对象"]
    validate_check("event_flow", checks.get("event_flow"))
    validate_check("emotion_flow", checks.get("emotion_flow"))
    validate_check("telegraphic_and_relation_check", checks.get("telegraphic_and_relation_check"))
    style = checks.get("style_granularity")
    if not isinstance(style, dict):
        errors.append("style_granularity 必须是对象")
    else:
        if style.get("status") != "passed":
            errors.append("style_granularity.status 必须为 passed")
        if not str(style.get("judgment") or "").strip():
            errors.append("style_granularity.judgment 不能为空")
        dimensions = style.get("dimensions")
        if not isinstance(dimensions, dict) or set(dimensions) != set(STYLE_DIMENSIONS):
            errors.append("style_granularity.dimensions 必须完整覆盖六类文风颗粒")
        else:
            for name in STYLE_DIMENSIONS:
                validate_check(f"style_granularity.{name}", dimensions.get(name))
    if not str(review.get("manual_judgment") or "").strip():
        errors.append("逐节停检 manual_judgment 不能为空")
    if review.get("gate_status") != "passed":
        errors.append("逐节停检 gate_status 必须为 passed")
    return review, errors


def close_section(receipt: Path, section_id: str, review_path: Path) -> int:
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
    expected_review_path = section_review_path(receipt, section_id).resolve()
    if review_path.resolve() != expected_review_path:
        print(f"section_draft_execution: blocked\n- 必须使用当前小节停检回执: {expected_review_path}")
        return 2
    source_read_records = target.get("source_read_records")
    if not isinstance(source_read_records, list) or not source_read_records:
        print("section_draft_execution: blocked\n- 当前小节没有完整原文实读记录")
        return 2
    review, review_errors = validate_review(
        review_path,
        section_id,
        draft,
        content,
        source_read_records,
    )
    if review_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(review_errors))
        return 2
    checks = review["checks"]
    target.update({
        "status": "completed",
        "closed_at": now_iso(),
        "manual_judgment": review["manual_judgment"].strip(),
        "event_flow": checks["event_flow"]["status"],
        "emotion_flow": checks["emotion_flow"]["status"],
        "style_granularity": checks["style_granularity"]["status"],
        "telegraphic_and_relation_check": checks["telegraphic_and_relation_check"]["status"],
        "review_receipt": binding(review_path),
        "section_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "draft_sha256_after_close": sha256(draft),
    })
    if all(item["status"] == "completed" for item in data["sections"]):
        data["final_draft_sha256"] = sha256(draft)
        data["gate_status"] = "passed"
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} completed")
    return 0


def reset_section(receipt: Path, section_id: str) -> int:
    """Archive and reset the latest written section for a clean rewrite."""
    try:
        data = read_json(receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"section_draft_execution: blocked\n- 回执无法读取: {exc}")
        return 2
    binding_errors: list[str] = []
    for key in ("outline_contract", "source_receipt", "section_source_bundle"):
        check_binding(data.get(key), key, binding_errors)
    if binding_errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(binding_errors))
        return 2
    sections = data.get("sections")
    if not isinstance(sections, list):
        print("section_draft_execution: blocked\n- sections 必须是数组")
        return 2
    target = next((item for item in sections if isinstance(item, dict) and item.get("section_id") == section_id), None)
    if not target or target.get("status") not in {"open", "completed"}:
        print("section_draft_execution: blocked\n- 只能重置已打开或已完成的小节")
        return 2
    target_index = sections.index(target)
    if any(item.get("status") != "pending" for item in sections[target_index + 1 :] if isinstance(item, dict)):
        print("section_draft_execution: blocked\n- 后续小节已有写作状态，必须从最后写入的小节开始重置")
        return 2
    draft = Path(str(data.get("draft_path") or "")).resolve()
    text = draft.read_text(encoding="utf-8") if draft.is_file() else ""
    matches = list(SECTION_RE.finditer(text))
    target_match = next((match for match in matches if match.group(1) == section_id), None)
    if not target_match or target_match != matches[-1]:
        print("section_draft_execution: blocked\n- 目标小节不是正文最后一个小节")
        return 2
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    archive_dir = receipt.parent / "首稿小节归档"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"第{section_id}节-{timestamp}.md"
    archive_path.write_text(text[target_match.start() :].rstrip() + "\n", encoding="utf-8")
    retained = text[: target_match.start()].rstrip()
    draft.write_text((retained + "\n") if retained else "", encoding="utf-8")
    old_review = section_review_path(receipt, section_id)
    if old_review.is_file():
        old_review.replace(archive_dir / f"第{section_id}节停检-{timestamp}.json")
    target.update(
        {
            "status": "pending",
            "source_read_records": [],
            "review_receipt": {},
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
        }
    )
    data["final_draft_sha256"] = ""
    data["gate_status"] = "active"
    write_json(receipt, data)
    print(f"section_draft_execution: section {section_id} reset")
    print(f"archive: {archive_path}")
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
    closing.add_argument("--review", required=True)
    reset = sub.add_parser("reset-section")
    reset.add_argument("--receipt", required=True)
    reset.add_argument("--section", required=True)
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
        return close_section(receipt, args.section, Path(args.review).resolve())
    if args.command == "reset-section":
        return reset_section(receipt, args.section)
    _, errors = validate_receipt(receipt, require_complete=True)
    if errors:
        print("section_draft_execution: blocked\n- " + "\n- ".join(errors))
        return 2
    print("section_draft_execution: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
