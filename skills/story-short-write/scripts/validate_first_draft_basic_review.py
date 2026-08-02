#!/usr/bin/env python3
"""Initialize and validate the mandatory first-draft basic review receipt."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import importlib.util


REQUIRED_REVIEW_IDS = {
    "sentence_relationships_and_function_words",
    "paragraph_breathing_and_telegraphic_prose",
    "character_emotion_process",
    "character_voice_and_plot_continuity",
}
SOURCE_GRANULARITY_FIELDS = {
    "sentence_rhythm",
    "narrator_interjection",
    "dialogue_action_ratio",
    "information_release",
    "explanation_density",
    "scene_ending",
    "manual_judgment",
}

_DRAFT_ENTRY_GATE_PATH = Path(__file__).with_name("validate_first_draft_entry.py")
_DRAFT_ENTRY_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_first_draft_entry", _DRAFT_ENTRY_GATE_PATH
)
assert _DRAFT_ENTRY_SPEC and _DRAFT_ENTRY_SPEC.loader
_DRAFT_ENTRY_MODULE = importlib.util.module_from_spec(_DRAFT_ENTRY_SPEC)
_DRAFT_ENTRY_SPEC.loader.exec_module(_DRAFT_ENTRY_MODULE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON 根节点必须是对象")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256(resolved)}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validate_finalized_bindings(
    receipt: Path,
    section_execution_receipt: Path,
    draft: Path,
) -> list[str]:
    errors: list[str] = []
    try:
        review = read_json(receipt)
        execution = read_json(section_execution_receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"重绑后回执不可读取: {exc}"]
    draft_info = review.get("draft")
    if not isinstance(draft_info, dict):
        errors.append("重绑后 review.draft 必须是对象")
    else:
        if Path(str(draft_info.get("path") or "")).expanduser().resolve() != draft.resolve():
            errors.append("重绑后 review.draft.path 未绑定当前正文")
        if draft_info.get("sha256") != sha256(draft):
            errors.append("重绑后 review.draft.sha256 未绑定当前正文")
    execution_binding = review.get("section_execution_receipt")
    if not isinstance(execution_binding, dict):
        errors.append("重绑后 review.section_execution_receipt 必须是对象")
    else:
        if (
            Path(str(execution_binding.get("path") or "")).expanduser().resolve()
            != section_execution_receipt.resolve()
        ):
            errors.append("重绑后 review.section_execution_receipt.path 未绑定正式逐节回执")
        if execution_binding.get("sha256") != sha256(section_execution_receipt):
            errors.append("重绑后 review.section_execution_receipt.sha256 未绑定正式逐节回执")
    if execution.get("final_draft_sha256") != sha256(draft):
        errors.append("重绑后逐节回执 final_draft_sha256 未绑定当前正文")
    return errors


def init_receipt(
    draft: Path,
    receipt: Path,
    force: bool,
    imitation_mode: bool = False,
    source_paths: list[Path] | None = None,
    section_execution_receipt: Path | None = None,
    draft_entry_receipt: Path | None = None,
) -> int:
    if receipt.exists() and not force:
        print(f"首稿基础审计回执已存在，拒绝覆盖: {receipt}")
        return 2
    if not draft.is_file():
        print(f"正文不存在: {draft}")
        return 2
    sources = [path.resolve() for path in (source_paths or [])]
    if imitation_mode and not sources:
        print("仿写模式必须至少传入一个 --source 原文")
        return 2
    if imitation_mode and section_execution_receipt is None:
        print("仿写模式必须提供 --section-execution-receipt，禁止批量写完后补逐节记录")
        return 2
    if imitation_mode and draft_entry_receipt is None:
        print("仿写模式必须提供 --draft-entry-receipt，禁止绕过首稿入口直接写正文")
        return 2
    if draft_entry_receipt is not None:
        if not draft_entry_receipt.is_file():
            print(f"首稿入口回执不存在: {draft_entry_receipt}")
            return 2
        entry_errors = _DRAFT_ENTRY_MODULE.validate_entry(draft_entry_receipt, draft)
        if entry_errors:
            print("首稿入口回执未通过")
            for error in entry_errors:
                print(f"- {error}")
            return 2
    if section_execution_receipt is not None:
        if not section_execution_receipt.is_file():
            print(f"逐节首写执行回执不存在: {section_execution_receipt}")
            return 2
        execution = read_json(section_execution_receipt)
        if execution.get("gate_status") != "passed" or execution.get("final_draft_sha256") != sha256(draft):
            print("逐节首写执行回执未通过或未绑定当前正文")
            return 2
    missing_sources = [str(path) for path in sources if not path.is_file()]
    if missing_sources:
        print("原文不存在: " + " / ".join(missing_sources))
        return 2
    base_draft = receipt.parent / "首稿基础审计母稿.md"
    if base_draft.exists() and not force:
        print(f"首稿基础审计母稿已存在，拒绝覆盖: {base_draft}")
        return 2
    base_draft.parent.mkdir(parents=True, exist_ok=True)
    base_draft.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
    review_items = [
        {
            "review_id": review_id,
            "checked": False,
            "issue_found": False,
            "draft_evidence": [],
            "judgment": "",
            "fixes_applied": [],
        }
        for review_id in sorted(REQUIRED_REVIEW_IDS)
    ]
    write_json(
        receipt,
        {
            "version": "1.1",
            "gate": "first_draft_basic_review",
            "draft": {"path": str(draft.resolve()), "sha256": sha256(draft)},
            "base_draft": source_binding(base_draft),
            "imitation_mode": imitation_mode,
            "selected_sources": [source_binding(path) for path in sources],
            "section_execution_receipt": (
                source_binding(section_execution_receipt)
                if section_execution_receipt is not None
                else None
            ),
            "draft_entry_receipt": (
                source_binding(draft_entry_receipt)
                if draft_entry_receipt is not None
                else None
            ),
            "source_granularity_baseline": {
                "source_evidence": [],
                **{field: "" for field in sorted(SOURCE_GRANULARITY_FIELDS)},
            },
            "reviewed_by_current_model": False,
            "review_items": review_items,
            "basic_revision_performed": False,
            "revision_blocks": [],
            "remaining_known_issues": [],
            "preview_ready": False,
            "gate_status": "pending",
        },
    )
    print(f"first_draft_basic_review: initialized\nreceipt: {receipt}")
    return 0


def validate_file_binding(value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return None
    path = Path(str(value.get("path") or "")).expanduser().resolve()
    if not path.is_file():
        errors.append(f"{label}文件不存在: {path}")
        return None
    if value.get("sha256") != sha256(path):
        errors.append(f"{label} SHA 已变化")
    return path


def validate_source_baseline(
    data: dict[str, Any],
    source_texts: dict[str, str],
    errors: list[str],
) -> None:
    baseline = data.get("source_granularity_baseline")
    if not isinstance(baseline, dict):
        errors.append("仿写基础审计缺少 source_granularity_baseline")
        return
    for field in SOURCE_GRANULARITY_FIELDS:
        if not str(baseline.get(field) or "").strip():
            errors.append(f"source_granularity_baseline.{field} 不能为空")
    evidence = baseline.get("source_evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        errors.append("source_granularity_baseline.source_evidence 至少需要两条原文证据")
        return
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
            errors.append(f"原文颗粒证据缺少语言/场面功能判断[{index}]")
    if len(distinct_quotes) < 2:
        errors.append("原文颗粒证据不得用同一句重复充数")


def validate_revision_blocks(
    data: dict[str, Any],
    base_text: str,
    draft_text: str,
    source_texts: dict[str, str],
    errors: list[str],
) -> None:
    blocks = data.get("revision_blocks")
    if not isinstance(blocks, list) or not blocks:
        errors.append("仿写正文发生基础回修时必须填写 revision_blocks")
        return
    for index, block in enumerate(blocks, start=1):
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
        for field, haystack in (
            ("base_draft_evidence", base_text),
            ("revised_draft_evidence", draft_text),
        ):
            evidence = block.get(field)
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{label}.{field} 至少需要一条证据")
                continue
            for quote in evidence:
                if not str(quote).strip() or str(quote).strip() not in haystack:
                    errors.append(f"{label}.{field} 不在对应文本中: {quote!r}")
        if block.get("base_draft_evidence") == block.get("revised_draft_evidence"):
            errors.append(f"{label} 母稿证据与改后证据不能完全相同")
        for field in (
            "no_added_explanation_density",
            "no_source_rhythm_regularization",
            "surface_copy_check",
        ):
            if block.get(field) is not True:
                errors.append(f"{label}.{field} 必须为 true")


def validate_receipt(receipt: Path, draft_override: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        data = read_json(receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"回执无法读取: {exc}"]
    if data.get("gate") != "first_draft_basic_review":
        errors.append("gate 必须为 first_draft_basic_review")
    draft_info = data.get("draft")
    if not isinstance(draft_info, dict):
        return errors + ["draft 必须是对象"]
    draft = draft_override or Path(str(draft_info.get("path") or "")).expanduser().resolve()
    if not draft.is_file():
        return errors + [f"正文不存在: {draft}"]
    if draft_info.get("sha256") != sha256(draft):
        errors.append("正文 SHA 已变化，首稿基础审计回执失效")
    draft_text = draft.read_text(encoding="utf-8")
    base_draft = validate_file_binding(data.get("base_draft"), "base_draft", errors)
    base_text = base_draft.read_text(encoding="utf-8") if base_draft else ""
    source_texts: dict[str, str] = {}
    selected_sources = data.get("selected_sources")
    if data.get("imitation_mode") is True:
        if not isinstance(selected_sources, list) or not selected_sources:
            errors.append("仿写基础审计必须绑定 selected_sources")
        else:
            for index, binding in enumerate(selected_sources, start=1):
                path = validate_file_binding(binding, f"selected_sources[{index}]", errors)
                if path:
                    source_texts[str(path)] = path.read_text(encoding="utf-8")
        validate_source_baseline(data, source_texts, errors)
        execution_path = validate_file_binding(
            data.get("section_execution_receipt"),
            "section_execution_receipt",
            errors,
        )
        draft_entry_path = validate_file_binding(
            data.get("draft_entry_receipt"),
            "draft_entry_receipt",
            errors,
        )
        if execution_path:
            execution = read_json(execution_path)
            if execution.get("gate_status") != "passed":
                errors.append("section_execution_receipt.gate_status 必须为 passed")
            if execution.get("final_draft_sha256") != sha256(draft):
                errors.append("section_execution_receipt 未绑定当前正文")
        if draft_entry_path:
            entry_errors = _DRAFT_ENTRY_MODULE.validate_entry(draft_entry_path, draft)
            if entry_errors:
                errors.append("draft_entry_receipt 未通过")
                errors.extend(entry_errors)
    items = data.get("review_items")
    if not isinstance(items, list):
        return errors + ["review_items 必须是数组"]
    ids = [str(item.get("review_id") or "") for item in items if isinstance(item, dict)]
    missing = sorted(REQUIRED_REVIEW_IDS - set(ids))
    duplicate = sorted({review_id for review_id in ids if review_id and ids.count(review_id) > 1})
    if missing:
        errors.append("缺少基础审计项: " + " / ".join(missing))
    if duplicate:
        errors.append("重复基础审计项: " + " / ".join(duplicate))
    any_issue = False
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"review_items[{index}] 必须是对象")
            continue
        label = str(item.get("review_id") or f"review_items[{index}]")
        if item.get("checked") is not True:
            errors.append(f"{label}.checked 必须为 true")
        if not str(item.get("judgment") or "").strip():
            errors.append(f"{label}.judgment 不能为空")
        evidence = item.get("draft_evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{label}.draft_evidence 至少引用一条当前正文原句")
        else:
            for quote in evidence:
                text = str(quote or "").strip()
                if not text or text not in draft_text:
                    errors.append(f"{label}.draft_evidence 不在当前正文中: {quote!r}")
        if item.get("issue_found") is True:
            any_issue = True
            fixes = item.get("fixes_applied")
            if not isinstance(fixes, list) or not any(str(value).strip() for value in fixes):
                errors.append(f"{label} 发现问题后必须记录基础回修动作")
    if any_issue and data.get("basic_revision_performed") is not True:
        errors.append("发现基础硬伤后 basic_revision_performed 必须为 true")
    if any_issue and data.get("imitation_mode") is True:
        if base_draft and sha256(base_draft) == sha256(draft):
            errors.append("已声明基础回修，但母稿与修改后正文 SHA 相同；禁止改后重建母稿")
        validate_revision_blocks(data, base_text, draft_text, source_texts, errors)
    if data.get("reviewed_by_current_model") is not True:
        errors.append("reviewed_by_current_model 必须为 true")
    if data.get("preview_ready") is not True:
        errors.append("preview_ready 必须为 true")
    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    return errors


def finalize_after_revision(
    receipt: Path,
    draft: Path,
    section_execution_receipt: Path,
) -> list[str]:
    """Validate the real dual-baseline evidence before mechanically rebinding SHA values."""
    try:
        review = read_json(receipt)
        execution = read_json(section_execution_receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"回执不可读取: {exc}"]
    if not draft.is_file():
        return [f"正文不存在: {draft}"]
    if review.get("gate") != "first_draft_basic_review":
        return ["gate 必须为 first_draft_basic_review"]
    if execution.get("gate") != "section_draft_execution":
        return ["逐节回执 gate 必须为 section_draft_execution"]
    if execution.get("gate_status") != "passed":
        return ["逐节回执尚未完成，禁止基础审计后重绑"]

    draft_sha = sha256(draft)
    staged_execution = copy.deepcopy(execution)
    staged_execution.setdefault(
        "first_draft_sha256",
        str(staged_execution.get("final_draft_sha256") or ""),
    )
    staged_execution["final_draft_sha256"] = draft_sha
    staged_execution["post_review_draft_sha256"] = draft_sha
    staged_execution["post_review_rebound_at"] = now_iso()
    for item in staged_execution.get("sections", []):
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "")
        content = _DRAFT_ENTRY_MODULE._SECTION_EXECUTION_MODULE.section_text(
            draft,
            section_id,
        )
        if not content:
            return [f"第 {section_id} 节正文为空，禁止重绑"]
        item["post_review_section_sha256"] = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

    staged_review = copy.deepcopy(review)
    draft_info = staged_review.get("draft")
    if not isinstance(draft_info, dict):
        return ["draft 必须是对象"]
    draft_info["path"] = str(draft.resolve())
    draft_info["sha256"] = draft_sha

    with tempfile.TemporaryDirectory() as temporary_dir:
        temporary_root = Path(temporary_dir)
        temporary_execution = temporary_root / "逐节首写执行回执.json"
        temporary_review = temporary_root / "首稿基础审计回执.json"
        write_json(temporary_execution, staged_execution)
        staged_review["section_execution_receipt"] = source_binding(
            temporary_execution
        )
        write_json(temporary_review, staged_review)
        errors = validate_receipt(temporary_review, draft)
    if errors:
        return errors

    atomic_write_json(section_execution_receipt, staged_execution)
    staged_review["section_execution_receipt"] = source_binding(
        section_execution_receipt
    )
    atomic_write_json(receipt, staged_review)
    final_errors = validate_finalized_bindings(
        receipt,
        section_execution_receipt,
        draft,
    )
    if final_errors:
        return ["重绑后复验失败", *final_errors]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--draft", required=True)
    init.add_argument("--receipt", required=True)
    init.add_argument("--force", action="store_true")
    init.add_argument("--imitation-mode", action="store_true")
    init.add_argument("--source", action="append", default=[])
    init.add_argument("--section-execution-receipt")
    init.add_argument("--draft-entry-receipt")
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--draft")
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--receipt", required=True)
    finalize.add_argument("--draft", required=True)
    finalize.add_argument("--section-execution-receipt", required=True)
    args = parser.parse_args()
    if args.command == "init":
        return init_receipt(
            Path(args.draft).resolve(),
            Path(args.receipt).resolve(),
            args.force,
            imitation_mode=args.imitation_mode,
            source_paths=[Path(path).resolve() for path in args.source],
            section_execution_receipt=(
                Path(args.section_execution_receipt).resolve()
                if args.section_execution_receipt
                else None
            ),
            draft_entry_receipt=(
                Path(args.draft_entry_receipt).resolve()
                if args.draft_entry_receipt
                else None
            ),
        )
    receipt = Path(args.receipt).resolve()
    if args.command == "finalize":
        errors = finalize_after_revision(
            receipt,
            Path(args.draft).resolve(),
            Path(args.section_execution_receipt).resolve(),
        )
        if errors:
            print("first_draft_basic_review: finalize blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("first_draft_basic_review: finalized")
        return 0
    draft = Path(args.draft).resolve() if args.draft else None
    errors = validate_receipt(receipt, draft)
    if errors:
        print("first_draft_basic_review: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("first_draft_basic_review: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
