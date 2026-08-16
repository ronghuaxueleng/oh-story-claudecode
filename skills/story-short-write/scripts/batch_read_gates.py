#!/usr/bin/env python3
"""Batch entry for writing_rule_gate + source_read_gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_lifecycle import consume_sidecar, sha256_file


ROOT = Path(__file__).resolve().parent
READ_BATCH_INDEX_SCHEMA = "story-short-write.read-batch-index.v1"
READ_BATCH_SCHEMA = "story-short-write.read-batch.v1"
BATCH_STATUSES = {"pending", "in_progress", "reviewed"}


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
PROJECT_DIR_GATE = _load_module(
    "validate_project_directory_name.py",
    "story_short_write_project_directory_name",
)

PROJECT_DIRS = (
    "拆文库",
    "资料库",
    "资料库/开头库",
    "资料库/对话刀法库",
    "资料库/微动作库",
    "资料库/安静压迫场库",
    "资料库/AI反例库",
    "资料库/角色口气库",
    "写作资产",
    "写作资产/读取批次",
    "写作资产/当前节计划",
    "写作资产/当前节写作包",
    "写作资产/当前节暂存",
    "写作资产/逐节验收",
    "写作资产/逐节验收/侧车",
    "写作资产/正式审计",
    "写作资产/单节原型测试",
    "对标",
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象: {path}")
    return payload


def _nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _read_file_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quote_shell(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _join_shell_flags(flag: str, values: list[Path]) -> str:
    return " ".join(f"{flag} {_quote_shell(str(path))}" for path in values)


def _validate_batch_status(batch: dict[str, Any], *, label: str) -> str:
    status = str(batch.get("status") or "").strip()
    if status not in BATCH_STATUSES:
        raise ValueError(f"{label} status 非法: {status or '<empty>'}")
    reviewed = batch.get("reviewed_by_current_model") is True
    reviewed_at = str(batch.get("reviewed_at") or "").strip()
    started_at = str(batch.get("review_started_at") or "").strip()
    if status == "pending":
        if reviewed:
            raise ValueError(f"{label} status=pending 时 reviewed_by_current_model 必须为 false")
        if reviewed_at:
            raise ValueError(f"{label} status=pending 时 reviewed_at 必须为空")
        return status
    if status == "in_progress":
        if reviewed:
            raise ValueError(f"{label} status=in_progress 时 reviewed_by_current_model 必须为 false")
        if not started_at:
            raise ValueError(f"{label} status=in_progress 时 review_started_at 不能为空")
        if reviewed_at:
            raise ValueError(f"{label} status=in_progress 时 reviewed_at 必须为空")
        return status
    if not reviewed:
        raise ValueError(f"{label} status=reviewed 时 reviewed_by_current_model 必须为 true")
    if not reviewed_at:
        raise ValueError(f"{label} status=reviewed 时 reviewed_at 不能为空")
    return status


def _collect_batch_entries(
    *,
    writing_receipt_path: Path,
    source_receipt_path: Path,
) -> list[dict[str, Any]]:
    writing_receipt = load_json(writing_receipt_path, "写作规则读取回执")
    source_receipt = load_json(source_receipt_path, "拆文读取回执")
    writing_root = Path(str(writing_receipt.get("skill_root_at_init") or "")).resolve()
    entries: list[dict[str, Any]] = []

    writing_files = writing_receipt.get("files")
    if not isinstance(writing_files, list):
        raise ValueError("写作规则读取回执缺少 files 列表")
    for index, item in enumerate(writing_files, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"写作规则读取回执 files[{index - 1}] 必须是对象")
        relative = str(item.get("path") or "").strip()
        if not relative:
            raise ValueError(f"写作规则读取回执 files[{index - 1}].path 不能为空")
        absolute = (writing_root / relative).resolve()
        entries.append(
            {
                "entry_id": f"W-{index:03d}",
                "gate": "writing",
                "group_label": "写作规则",
                "source_root": str(writing_root),
                "relative_path": relative,
                "absolute_path": str(absolute),
                "file_sha256": sha256_file(absolute),
                "content": _read_file_text(absolute),
                "evidence_terms": [],
                "takeaways": [],
                "used_for": [],
            }
        )

    sources = source_receipt.get("sources")
    if not isinstance(sources, list):
        raise ValueError("拆文读取回执缺少 sources 列表")
    global_index = 1
    for source_index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            raise ValueError(f"拆文读取回执 sources[{source_index - 1}] 必须是对象")
        source_root = Path(str(source.get("root") or "")).resolve()
        source_name = str(source.get("name") or source_root.name or f"source-{source_index}")
        file_entries = source.get("files")
        if not isinstance(file_entries, list):
            raise ValueError(f"拆文读取回执 sources[{source_index - 1}].files 必须是列表")
        for item in file_entries:
            if not isinstance(item, dict):
                raise ValueError(f"拆文读取回执 sources[{source_index - 1}].files 含非法项")
            relative = str(item.get("path") or "").strip()
            if not relative:
                raise ValueError("拆文读取回执存在空 path 文件项")
            absolute = (source_root / relative).resolve()
            entries.append(
                {
                    "entry_id": f"S{source_index:02d}-{global_index:03d}",
                    "gate": "source",
                    "group_label": source_name,
                    "source_root": str(source_root),
                    "relative_path": relative,
                    "absolute_path": str(absolute),
                    "file_sha256": sha256_file(absolute),
                    "content": _read_file_text(absolute),
                    "evidence_terms": [],
                    "takeaways": [],
                    "used_for": [],
                }
            )
            global_index += 1
    return entries


def bootstrap_project_layout(*, project: str, project_dir: Path) -> tuple[list[str], dict[str, Any]]:
    project_dir = project_dir.resolve()
    if project_dir.exists():
        if not project_dir.is_dir():
            return [f"全新开书目录必须是目录或不存在路径，当前不是目录: {project_dir}"], {"created_dirs": []}
        errors = PROJECT_DIR_GATE.validate(project_dir, project, new_project=False)
        if errors:
            return errors, {"created_dirs": []}
        existing_files = [
            str(path.relative_to(project_dir))
            for path in sorted(project_dir.rglob("*"))
            if path.is_file()
        ]
        if existing_files:
            return [
                "bootstrap-project 只接受不存在路径，或已按目录硬闸创建但尚未初始化文件的全新目录。",
                f"当前目录已含文件，不得继续当作全新项目骨架复用: {project_dir}",
                f"示例文件: {existing_files[0]}",
            ], {"created_dirs": []}
    else:
        errors = PROJECT_DIR_GATE.validate(project_dir, project, new_project=True)
        if errors:
            return errors, {"created_dirs": []}
        project_dir.mkdir(parents=True, exist_ok=False)

    created_dirs = [str(project_dir.resolve())]
    for relative in PROJECT_DIRS:
        path = (project_dir / relative).resolve()
        path.mkdir(parents=True, exist_ok=True)
        created_dirs.append(str(path))

    layout_index_path = (project_dir / "写作资产" / "项目骨架索引.json").resolve()
    layout_index = {
        "schema_version": "story-short-write.project-layout.v1",
        "project": project,
        "project_dir": str(project_dir.resolve()),
        "created_at": _utc_now_iso(),
        "created_dirs": created_dirs,
        "reserved_files": {
            "setting": str((project_dir / "设定.md").resolve()),
            "outline": str((project_dir / "小节大纲.md").resolve()),
            "draft": str((project_dir / "正文.md").resolve()),
            "writing_receipt": str((project_dir / "写作资产" / "写作规则读取回执.json").resolve()),
            "source_receipt": str((project_dir / "写作资产" / "拆文读取回执.json").resolve()),
            "batch_manifest": str((project_dir / "写作资产" / "读取批次" / "manifest.json").resolve()),
            "section_state": str((project_dir / "写作资产" / "逐节正文进度.json").resolve()),
        },
    }
    write_json(layout_index_path, layout_index)

    return [], {
        "project_dir": str(project_dir.resolve()),
        "created_dirs": created_dirs,
        "layout_index": str(layout_index_path),
        "writing_receipt": str((project_dir / "写作资产" / "写作规则读取回执.json").resolve()),
        "source_receipt": str((project_dir / "写作资产" / "拆文读取回执.json").resolve()),
        "batch_dir": str((project_dir / "写作资产" / "读取批次").resolve()),
    }


def export_batches(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    output_dir: Path,
    batch_size: int,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0")
    entries = _collect_batch_entries(
        writing_receipt_path=writing_receipt,
        source_receipt_path=source_receipt,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    writing_sha = sha256_file(writing_receipt)
    source_sha = sha256_file(source_receipt)
    writing_data = load_json(writing_receipt, "写作规则读取回执")
    source_data = load_json(source_receipt, "拆文读取回执")
    writing_index = _index_writing_entries(writing_data)
    source_index = _index_source_entries(source_data)
    cross_source_decisions = _nonempty_strings(source_data.get("cross_source_decisions"))
    batches: list[dict[str, Any]] = []
    total_batches = (len(entries) + batch_size - 1) // batch_size
    for batch_number, start in enumerate(range(0, len(entries), batch_size), start=1):
        batch_entries = entries[start : start + batch_size]
        batch_id = f"batch-{batch_number:03d}"
        batch_path = output_dir / f"{batch_id}.json"
        restored_entries: list[dict[str, Any]] = []
        restored_count = 0
        for entry in batch_entries:
            restored = dict(entry)
            gate = str(entry.get("gate") or "").strip()
            relative = str(entry.get("relative_path") or "").strip()
            target: dict[str, Any] | None = None
            if gate == "writing":
                target = writing_index.get(relative)
            elif gate == "source":
                source_root = str(entry.get("source_root") or "").strip()
                target = source_index.get((source_root, relative))
            if target and str(target.get("status") or "").strip() == "read":
                evidence_terms = _nonempty_strings(target.get("evidence_terms"))
                takeaways = _nonempty_strings(target.get("takeaways"))
                used_for = _nonempty_strings(target.get("used_for"))
                if evidence_terms and takeaways and used_for:
                    restored["evidence_terms"] = evidence_terms
                    restored["takeaways"] = takeaways
                    restored["used_for"] = used_for
                    restored_count += 1
            restored_entries.append(restored)
        all_reviewed = restored_count == len(restored_entries) and bool(restored_entries)
        restored_at = _utc_now_iso() if all_reviewed else None
        payload = {
            "schema_version": READ_BATCH_SCHEMA,
            "batch_id": batch_id,
            "batch_number": batch_number,
            "total_batches": total_batches,
            "status": "reviewed" if all_reviewed else "pending",
            "review_started_at": restored_at,
            "reviewed_at": restored_at,
            "reviewed_by_current_model": all_reviewed,
            "semantic_fields_generated_by_script": False,
            "cross_source_decisions": cross_source_decisions,
            "bindings": {
                "writing_receipt_path": str(writing_receipt.resolve()),
                "writing_receipt_sha256": writing_sha,
                "source_receipt_path": str(source_receipt.resolve()),
                "source_receipt_sha256": source_sha,
            },
            "entries": restored_entries,
        }
        write_json(batch_path, payload)
        batches.append(
            {
                "batch_id": batch_id,
                "path": str(batch_path.resolve()),
                "entry_count": len(batch_entries),
                "first_entry_id": batch_entries[0]["entry_id"],
                "last_entry_id": batch_entries[-1]["entry_id"],
            }
        )

    manifest = {
        "schema_version": READ_BATCH_INDEX_SCHEMA,
        "writing_receipt_path": str(writing_receipt.resolve()),
        "writing_receipt_sha256": writing_sha,
        "source_receipt_path": str(source_receipt.resolve()),
        "source_receipt_sha256": source_sha,
        "batch_size": batch_size,
        "total_entries": len(entries),
        "batches": batches,
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def prepare_batches(
    *,
    project: str,
    writing_receipt: Path,
    source_receipt: Path,
    source_dirs: list[Path],
    skill_root: Path,
    force_writing_receipt: bool,
    output_dir: Path,
    batch_size: int,
) -> tuple[list[str], dict[str, int | str]]:
    errors, init_summary = init_batch(
        project=project,
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        source_dirs=source_dirs,
        skill_root=skill_root,
        force_writing_receipt=force_writing_receipt,
    )
    summary: dict[str, int | str] = dict(init_summary)
    if errors:
        return errors, summary
    manifest = export_batches(
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        output_dir=output_dir,
        batch_size=batch_size,
    )
    summary.update(
        {
            "manifest_path": str((output_dir / "manifest.json").resolve()),
            "batch_size": manifest["batch_size"],
            "total_entries": manifest["total_entries"],
            "batch_count": len(manifest["batches"]),
        }
    )
    return [], summary


def inspect_manifest_batches(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = load_json(manifest_path, "读取批次清单")
    if manifest.get("schema_version") != READ_BATCH_INDEX_SCHEMA:
        raise ValueError("读取批次清单 schema_version 不正确")
    if str(manifest.get("writing_receipt_sha256") or "").strip() != sha256_file(writing_receipt):
        raise ValueError("读取批次清单绑定的写作规则读取回执 SHA 已失效，请重新 export")
    if str(manifest.get("source_receipt_sha256") or "").strip() != sha256_file(source_receipt):
        raise ValueError("读取批次清单绑定的拆文读取回执 SHA 已失效，请重新 export")
    batches = manifest.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("读取批次清单 batches 不能为空")

    manifest_dir = manifest_path.resolve().parent
    pending_batches: list[str] = []
    status_counts = {
        "pending": 0,
        "in_progress": 0,
        "reviewed": 0,
        "consumed": 0,
    }
    reviewed_batches = 0
    batch_summaries: list[dict[str, Any]] = []
    for index, item in enumerate(batches):
        if not isinstance(item, dict):
            raise ValueError(f"batches[{index}] 必须是对象")
        batch_file = str(item.get("path") or "").strip()
        if not batch_file:
            raise ValueError(f"batches[{index}].path 不能为空")
        batch_path = Path(batch_file)
        if not batch_path.is_absolute():
            batch_path = (manifest_dir / batch_path).resolve()
        batch_data = load_json(batch_path, "读取批次侧车")
        schema_version = str(batch_data.get("schema_version") or "").strip()
        batch_status = "unknown"
        if schema_version == READ_BATCH_SCHEMA:
            batch_status = _validate_batch_status(batch_data, label=f"读取批次侧车 {batch_path}")
        elif batch_data.get("status") == "consumed":
            batch_status = "consumed"
        else:
            raise ValueError(f"批次 schema_version 不正确: {batch_path}")
        if batch_status not in status_counts:
            raise ValueError(f"批次 status 非法: {batch_path} -> {batch_status}")
        status_counts[batch_status] += 1
        batch_summaries.append(
            {
                "batch_id": str(batch_data.get("batch_id") or item.get("batch_id") or "").strip(),
                "path": str(batch_path),
                "status": batch_status,
                "entry_count": int(item.get("entry_count") or 0),
                "first_entry_id": str(item.get("first_entry_id") or "").strip(),
                "last_entry_id": str(item.get("last_entry_id") or "").strip(),
            }
        )
        if batch_status == "reviewed":
            reviewed_batches += 1
            continue
        if batch_status != "consumed":
            pending_batches.append(str(batch_path))

    return {
        "batch_count": len(batches),
        "reviewed_batches": reviewed_batches,
        "pending_batches": pending_batches,
        "status_counts": status_counts,
        "batches": batch_summaries,
    }


def inspect_batch_file(*, batch_path: Path) -> dict[str, Any]:
    batch = load_json(batch_path, "读取批次侧车")
    schema_version = str(batch.get("schema_version") or "").strip()
    if schema_version == READ_BATCH_SCHEMA:
        status = _validate_batch_status(batch, label=f"读取批次侧车 {batch_path}")
    elif batch.get("status") == "consumed":
        status = "consumed"
    else:
        raise ValueError(f"读取批次侧车 schema_version 不正确: {batch_path}")

    entries = batch.get("entries")
    if not isinstance(entries, list):
        entries = []
    entry_summaries: list[dict[str, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        first_nonempty = ""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                first_nonempty = stripped
                break
        entry_summaries.append(
            {
                "entry_id": str(item.get("entry_id") or "").strip(),
                "gate": str(item.get("gate") or "").strip(),
                "group_label": str(item.get("group_label") or "").strip(),
                "relative_path": str(item.get("relative_path") or "").strip(),
                "preview": first_nonempty,
            }
        )

    return {
        "batch_id": str(batch.get("batch_id") or "").strip(),
        "status": status,
        "entry_count": len(entry_summaries),
        "review_started_at": str(batch.get("review_started_at") or "").strip(),
        "reviewed_at": str(batch.get("reviewed_at") or "").strip(),
        "reviewed_by_current_model": batch.get("reviewed_by_current_model") is True,
        "semantic_fields_generated_by_script": batch.get("semantic_fields_generated_by_script") is True,
        "entries": entry_summaries,
    }


def suggest_next_step(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    manifest_path: Path,
    stage: str,
    stage_output: Path,
    source_outputs: list[Path],
) -> dict[str, Any]:
    summary = inspect_manifest_batches(
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        manifest_path=manifest_path,
    )
    status_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" status '
        f'--writing-receipt {_quote_shell(str(writing_receipt.resolve()))} '
        f'--source-receipt {_quote_shell(str(source_receipt.resolve()))} '
        f'--manifest {_quote_shell(str(manifest_path.resolve()))}'
    )
    finalize_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" finalize-batches '
        f'--writing-receipt {_quote_shell(str(writing_receipt.resolve()))} '
        f'--source-receipt {_quote_shell(str(source_receipt.resolve()))} '
        f'--manifest {_quote_shell(str(manifest_path.resolve()))} '
        '--consume '
        f'--stage {stage} '
        f'--stage-output {_quote_shell(str(stage_output.resolve()))} '
        + " ".join(
            f'--output {_quote_shell(str(path.resolve()))}' for path in source_outputs
        )
    )
    validate_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" validate '
        f'--writing-receipt {_quote_shell(str(writing_receipt.resolve()))} '
        f'--source-receipt {_quote_shell(str(source_receipt.resolve()))} '
        f'--stage {stage} '
        f'--stage-output {_quote_shell(str(stage_output.resolve()))} '
        + " ".join(
            f'--output {_quote_shell(str(path.resolve()))}' for path in source_outputs
        )
    )
    if summary["status_counts"]["pending"] or summary["status_counts"]["in_progress"]:
        return {
            "action": "complete_manual_batches",
            "reason": "仍有读取批次未完成，先继续填写 batch-*.json 后再 finalize",
            "next_command": status_command,
            "status_command": status_command,
        }
    if summary["status_counts"]["reviewed"] == summary["batch_count"]:
        return {
            "action": "finalize_batches",
            "reason": "全部读取批次已 reviewed，下一步直接正式合并并校验",
            "next_command": finalize_command,
            "status_command": status_command,
        }

    writing_data = load_json(writing_receipt, "写作规则读取回执")
    source_data = load_json(source_receipt, "拆文读取回执")
    writing_passed = writing_data.get("gate_status") == "passed"
    source_passed = source_data.get("gate_status") == "passed"
    if summary["status_counts"]["consumed"] == summary["batch_count"] and not (
        writing_passed and source_passed
    ):
        return {
            "action": "validate_receipts",
            "reason": "批次已消费，但读取门禁尚未正式 passed，下一步补跑 validate",
            "next_command": validate_command,
            "status_command": status_command,
        }
    return {
        "action": "enter_design_phase",
        "reason": "读取批次已完成且两道门禁已通过，可以进入设定/大纲设计",
        "next_command": "",
        "status_command": status_command,
    }


def run_read_gates_cycle(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    manifest_path: Path,
    stage: str,
    stage_output: Path,
    source_outputs: list[Path],
    skill_root: Path,
) -> dict[str, Any]:
    suggestion = suggest_next_step(
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        manifest_path=manifest_path,
        stage=stage,
        stage_output=stage_output,
        source_outputs=source_outputs,
    )
    action = suggestion["action"]
    if action == "complete_manual_batches":
        return {
            "action": action,
            "reason": suggestion["reason"],
            "next_command": suggestion["next_command"],
            "status_command": suggestion["status_command"],
        }
    if action == "finalize_batches":
        errors, summary = finalize_batches(
            writing_receipt=writing_receipt,
            source_receipt=source_receipt,
            manifest_path=manifest_path,
            consume=True,
            stage=stage,
            stage_output=stage_output,
            source_outputs=source_outputs,
            skill_root=skill_root,
        )
        return {
            "action": "finalize_batches",
            "reason": suggestion["reason"],
            "status_command": suggestion["status_command"],
            "errors": errors,
            "summary": summary,
        }
    if action == "validate_receipts":
        errors, summary = validate_batch(
            writing_receipt=writing_receipt,
            source_receipt=source_receipt,
            stage=stage,
            stage_output=stage_output,
            source_outputs=source_outputs,
            skill_root=skill_root,
        )
        return {
            "action": "validate_receipts",
            "reason": suggestion["reason"],
            "status_command": suggestion["status_command"],
            "errors": errors,
            "summary": summary,
        }
    return {
        "action": action,
        "reason": suggestion["reason"],
        "status_command": suggestion["status_command"],
    }


def emit_shell_template(
    *,
    project: str,
    project_dir: Path,
    source_dirs: list[Path],
    stage: str,
    stage_output: Path,
    source_outputs: list[Path],
    batch_size: int,
) -> str:
    resolved_project_dir = project_dir.expanduser().resolve()
    writing_receipt = resolved_project_dir / "写作资产" / "写作规则读取回执.json"
    source_receipt = resolved_project_dir / "写作资产" / "拆文读取回执.json"
    manifest = resolved_project_dir / "写作资产" / "读取批次" / "manifest.json"
    source_flags = _join_shell_flags("--source-dir", [path.resolve() for path in source_dirs])
    output_flags = _join_shell_flags("--output", [path.resolve() for path in source_outputs])
    return "\n".join(
        [
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" bootstrap-project \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_project_dir))} \\",
            f"  {source_flags} \\",
            f"  --batch-size {batch_size} \\",
            '  --print-paths-json',
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" status \\',
            f"  --writing-receipt {_quote_shell(str(writing_receipt))} \\",
            f"  --source-receipt {_quote_shell(str(source_receipt))} \\",
            f"  --manifest {_quote_shell(str(manifest))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" next-step \\',
            f"  --writing-receipt {_quote_shell(str(writing_receipt))} \\",
            f"  --source-receipt {_quote_shell(str(source_receipt))} \\",
            f"  --manifest {_quote_shell(str(manifest))} \\",
            f"  --stage {stage} \\",
            f"  --stage-output {_quote_shell(str(stage_output.resolve()))} \\",
            f"  {output_flags}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_read_gates.py" run-read-gates-cycle \\',
            f"  --writing-receipt {_quote_shell(str(writing_receipt))} \\",
            f"  --source-receipt {_quote_shell(str(source_receipt))} \\",
            f"  --manifest {_quote_shell(str(manifest))} \\",
            f"  --stage {stage} \\",
            f"  --stage-output {_quote_shell(str(stage_output.resolve()))} \\",
            f"  {output_flags}",
        ]
    )


def start_new_project_read_gates_flow(
    *,
    project: str,
    project_dir: Path,
    source_dirs: list[Path],
    stage: str,
    stage_output: Path,
    source_outputs: list[Path],
    skill_root: Path,
    batch_size: int,
) -> dict[str, Any]:
    layout_errors, layout_summary = bootstrap_project_layout(
        project=project,
        project_dir=project_dir.expanduser().resolve(),
    )
    if layout_errors:
        raise ValueError("；".join(layout_errors))

    errors, prepare_summary = prepare_batches(
        project=project,
        writing_receipt=Path(layout_summary["writing_receipt"]).resolve(),
        source_receipt=Path(layout_summary["source_receipt"]).resolve(),
        source_dirs=source_dirs,
        skill_root=skill_root,
        force_writing_receipt=False,
        output_dir=Path(layout_summary["batch_dir"]).resolve(),
        batch_size=batch_size,
    )
    if errors:
        raise ValueError("；".join(errors))

    cycle_result = run_read_gates_cycle(
        writing_receipt=Path(layout_summary["writing_receipt"]).resolve(),
        source_receipt=Path(layout_summary["source_receipt"]).resolve(),
        manifest_path=Path(prepare_summary["manifest_path"]).resolve(),
        stage=stage,
        stage_output=stage_output,
        source_outputs=source_outputs,
        skill_root=skill_root,
    )
    return {
        "layout": layout_summary,
        "prepare": prepare_summary,
        "cycle": cycle_result,
    }


def apply_manifest(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    manifest_path: Path,
    consume: bool,
) -> dict[str, Any]:
    manifest = load_json(manifest_path, "读取批次清单")
    if manifest.get("schema_version") != READ_BATCH_INDEX_SCHEMA:
        raise ValueError("读取批次清单 schema_version 不正确")
    if str(manifest.get("writing_receipt_sha256") or "").strip() != sha256_file(writing_receipt):
        raise ValueError("读取批次清单绑定的写作规则读取回执 SHA 已失效，请重新 export")
    if str(manifest.get("source_receipt_sha256") or "").strip() != sha256_file(source_receipt):
        raise ValueError("读取批次清单绑定的拆文读取回执 SHA 已失效，请重新 export")
    batches = manifest.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("读取批次清单 batches 不能为空")

    updated_writing = 0
    updated_source = 0
    applied_batches = 0
    consumed_batches = 0
    manifest_dir = manifest_path.resolve().parent
    for index, item in enumerate(batches):
        if not isinstance(item, dict):
            raise ValueError(f"batches[{index}] 必须是对象")
        batch_file = str(item.get("path") or "").strip()
        if not batch_file:
            raise ValueError(f"batches[{index}].path 不能为空")
        batch_path = Path(batch_file)
        if not batch_path.is_absolute():
            batch_path = (manifest_dir / batch_path).resolve()
        batch_data = load_json(batch_path, "读取批次侧车")
        bindings = batch_data.get("bindings")
        if not isinstance(bindings, dict):
            raise ValueError(f"batches[{index}] 绑定的批次缺少 bindings: {batch_path}")
        bindings["writing_receipt_path"] = str(writing_receipt.resolve())
        bindings["writing_receipt_sha256"] = sha256_file(writing_receipt)
        bindings["source_receipt_path"] = str(source_receipt.resolve())
        bindings["source_receipt_sha256"] = sha256_file(source_receipt)
        write_json(batch_path, batch_data)
        batch_sha = sha256_file(batch_path)
        summary = apply_batch(
            writing_receipt=writing_receipt,
            source_receipt=source_receipt,
            batch_path=batch_path,
        )
        updated_writing += summary["updated_writing"]
        updated_source += summary["updated_source"]
        applied_batches += 1
        if consume:
            consume_sidecar(
                batch_path,
                input_sha256=batch_sha,
                receipt_path=source_receipt,
                receipt_sha256=sha256_file(source_receipt),
                operation="batch-read-gates.apply-manifest",
                counts={
                    "updated_writing": summary["updated_writing"],
                    "updated_source": summary["updated_source"],
                },
            )
            consumed_batches += 1

    manifest["writing_receipt_sha256"] = sha256_file(writing_receipt)
    manifest["source_receipt_sha256"] = sha256_file(source_receipt)
    write_json(manifest_path, manifest)

    return {
        "applied_batches": applied_batches,
        "consumed_batches": consumed_batches,
        "updated_writing": updated_writing,
        "updated_source": updated_source,
    }


def _index_writing_entries(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = data.get("files")
    if not isinstance(files, list):
        raise ValueError("写作规则读取回执缺少 files 列表")
    return {
        str(item.get("path") or "").strip(): item
        for item in files
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    }


def _index_source_entries(data: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError("拆文读取回执缺少 sources 列表")
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        root = str(source.get("root") or "").strip()
        files = source.get("files")
        if not isinstance(files, list):
            continue
        for item in files:
            if not isinstance(item, dict):
                continue
            relative = str(item.get("path") or "").strip()
            if relative:
                index[(root, relative)] = item
    return index


def _seal_gate_receipt(receipt_path: Path, source_label: str) -> None:
    data = load_json(receipt_path, source_label)
    data["gate_status"] = "passed"
    data["confirmed_before_outline"] = True
    data["confirmed_before_draft"] = True
    write_json(receipt_path, data)


def apply_batch(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    batch_path: Path,
) -> dict[str, Any]:
    batch = load_json(batch_path, "读取批次侧车")
    if batch.get("schema_version") != READ_BATCH_SCHEMA:
        raise ValueError("读取批次侧车 schema_version 不正确")
    status = _validate_batch_status(batch, label="读取批次侧车")
    if status != "reviewed":
        raise ValueError("读取批次侧车必须先标记 status=reviewed 才能 apply")
    if batch.get("reviewed_by_current_model") is not True:
        raise ValueError("读取批次侧车必须由当前模型标记 reviewed_by_current_model=true")
    if batch.get("semantic_fields_generated_by_script") is not False:
        raise ValueError("读取批次侧车必须声明 semantic_fields_generated_by_script=false")
    bindings = batch.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("读取批次侧车缺少 bindings")
    if str(bindings.get("writing_receipt_sha256") or "").strip() != sha256_file(writing_receipt):
        raise ValueError("读取批次侧车绑定的写作规则读取回执 SHA 已失效，请重新 export")
    if str(bindings.get("source_receipt_sha256") or "").strip() != sha256_file(source_receipt):
        raise ValueError("读取批次侧车绑定的拆文读取回执 SHA 已失效，请重新 export")

    entries = batch.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("读取批次侧车 entries 不能为空")

    writing_data = load_json(writing_receipt, "写作规则读取回执")
    source_data = load_json(source_receipt, "拆文读取回执")
    writing_index = _index_writing_entries(writing_data)
    source_index = _index_source_entries(source_data)

    updated_writing = 0
    updated_source = 0
    seen_ids: set[str] = set()
    for offset, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"entries[{offset}] 必须是对象")
        entry_id = str(entry.get("entry_id") or "").strip()
        if not entry_id:
            raise ValueError(f"entries[{offset}].entry_id 不能为空")
        if entry_id in seen_ids:
            raise ValueError(f"读取批次侧车存在重复 entry_id: {entry_id}")
        seen_ids.add(entry_id)

        gate = str(entry.get("gate") or "").strip()
        source_root = str(entry.get("source_root") or "").strip()
        relative = str(entry.get("relative_path") or "").strip()
        absolute = Path(str(entry.get("absolute_path") or "")).resolve()
        file_sha = str(entry.get("file_sha256") or "").strip()
        if not gate or not source_root or not relative:
            raise ValueError(f"{entry_id} 缺少 gate/source_root/relative_path")
        if not absolute.is_file():
            raise ValueError(f"{entry_id} 对应源文件不存在: {absolute}")
        if file_sha != sha256_file(absolute):
            raise ValueError(f"{entry_id} 绑定的源文件 SHA 已失效，请重新 export: {absolute}")

        evidence_terms = _nonempty_strings(entry.get("evidence_terms"))
        takeaways = _nonempty_strings(entry.get("takeaways"))
        used_for = _nonempty_strings(entry.get("used_for"))
        if not evidence_terms:
            raise ValueError(f"{entry_id} 缺少 evidence_terms")
        if not takeaways:
            raise ValueError(f"{entry_id} 缺少 takeaways")
        if not used_for:
            raise ValueError(f"{entry_id} 缺少 used_for")
        source_text = _read_file_text(absolute)
        missing_terms = [term for term in evidence_terms if term not in source_text]
        if missing_terms:
            raise ValueError(
                f"{entry_id} 的 evidence_terms 不在源文件中: {' / '.join(missing_terms)}"
            )

        if gate == "writing":
            target = writing_index.get(relative)
            if target is None:
                raise ValueError(f"{entry_id} 找不到对应的写作规则回执条目: {relative}")
            target["status"] = "read"
            target["evidence_terms"] = evidence_terms
            target["takeaways"] = takeaways
            target["used_for"] = used_for
            updated_writing += 1
            continue

        if gate != "source":
            raise ValueError(f"{entry_id} 的 gate 非法: {gate}")
        target = source_index.get((source_root, relative))
        if target is None:
            raise ValueError(f"{entry_id} 找不到对应的拆文读取回执条目: {source_root} -> {relative}")
        target["status"] = "read"
        target["evidence_terms"] = evidence_terms
        target["takeaways"] = takeaways
        target["used_for"] = used_for
        updated_source += 1

    cross_source_decisions = _nonempty_strings(batch.get("cross_source_decisions"))
    if cross_source_decisions:
        source_data["cross_source_decisions"] = cross_source_decisions

    write_json(writing_receipt, writing_data)
    write_json(source_receipt, source_data)
    return {
        "updated_writing": updated_writing,
        "updated_source": updated_source,
        "cross_source_decisions": len(cross_source_decisions),
    }


def finalize_batches(
    *,
    writing_receipt: Path,
    source_receipt: Path,
    manifest_path: Path,
    consume: bool,
    stage: str,
    stage_output: Path,
    source_outputs: list[Path],
    skill_root: Path,
) -> tuple[list[str], dict[str, int]]:
    inspection = inspect_manifest_batches(
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        manifest_path=manifest_path,
    )
    if inspection["pending_batches"]:
        pending = " / ".join(inspection["pending_batches"])
        raise ValueError(
            "读取批次存在未完成项，必须先由当前模型完成全部批次再 finalize: "
            f"{pending}"
        )
    manifest_summary = apply_manifest(
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        manifest_path=manifest_path,
        consume=consume,
    )
    _seal_gate_receipt(writing_receipt, "写作规则读取回执")
    _seal_gate_receipt(source_receipt, "拆文读取回执")
    errors, validate_summary = validate_batch(
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        stage=stage,
        stage_output=stage_output,
        source_outputs=source_outputs,
        skill_root=skill_root,
    )
    summary = {
        "applied_batches": manifest_summary["applied_batches"],
        "consumed_batches": manifest_summary["consumed_batches"],
        "updated_writing": manifest_summary["updated_writing"],
        "updated_source": manifest_summary["updated_source"],
        "writing_file_count": validate_summary["writing_file_count"],
        "writing_read_count": validate_summary["writing_read_count"],
        "source_count": validate_summary["source_count"],
        "source_file_count": validate_summary["source_file_count"],
        "source_read_count": validate_summary["source_read_count"],
    }
    return errors, summary


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

    export_batches_cmd = sub.add_parser("export-batches")
    export_batches_cmd.add_argument("--writing-receipt", required=True)
    export_batches_cmd.add_argument("--source-receipt", required=True)
    export_batches_cmd.add_argument("--output-dir", required=True)
    export_batches_cmd.add_argument("--batch-size", type=int, default=20)

    apply_batch_cmd = sub.add_parser("apply-batch")
    apply_batch_cmd.add_argument("--writing-receipt", required=True)
    apply_batch_cmd.add_argument("--source-receipt", required=True)
    apply_batch_cmd.add_argument("--input", required=True)
    apply_batch_cmd.add_argument("--consume", action="store_true")

    apply_manifest_cmd = sub.add_parser("apply-manifest")
    apply_manifest_cmd.add_argument("--writing-receipt", required=True)
    apply_manifest_cmd.add_argument("--source-receipt", required=True)
    apply_manifest_cmd.add_argument("--manifest", required=True)
    apply_manifest_cmd.add_argument("--consume", action="store_true")

    prepare_batches_cmd = sub.add_parser("prepare-batches")
    prepare_batches_cmd.add_argument("--project", required=True)
    prepare_batches_cmd.add_argument("--writing-receipt", required=True)
    prepare_batches_cmd.add_argument("--source-receipt", required=True)
    prepare_batches_cmd.add_argument("--source-dir", action="append", required=True)
    prepare_batches_cmd.add_argument("--skill-root", default=str(WRITING_GATE.SKILL_ROOT))
    prepare_batches_cmd.add_argument("--force-writing-receipt", action="store_true")
    prepare_batches_cmd.add_argument("--output-dir", required=True)
    prepare_batches_cmd.add_argument("--batch-size", type=int, default=20)

    finalize_batches_cmd = sub.add_parser("finalize-batches")
    finalize_batches_cmd.add_argument("--writing-receipt", required=True)
    finalize_batches_cmd.add_argument("--source-receipt", required=True)
    finalize_batches_cmd.add_argument("--manifest", required=True)
    finalize_batches_cmd.add_argument("--consume", action="store_true")
    finalize_batches_cmd.add_argument("--stage", choices=tuple(WRITING_GATE.STAGE_TARGET_NAMES), required=True)
    finalize_batches_cmd.add_argument("--stage-output", required=True)
    finalize_batches_cmd.add_argument("--output", action="append", required=True)
    finalize_batches_cmd.add_argument("--skill-root", default=str(WRITING_GATE.SKILL_ROOT))

    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--writing-receipt", required=True)
    status_cmd.add_argument("--source-receipt", required=True)
    status_cmd.add_argument("--manifest", required=True)

    show_batch_cmd = sub.add_parser("show-batch")
    show_batch_cmd.add_argument("--input", required=True)

    next_step_cmd = sub.add_parser("next-step")
    next_step_cmd.add_argument("--writing-receipt", required=True)
    next_step_cmd.add_argument("--source-receipt", required=True)
    next_step_cmd.add_argument("--manifest", required=True)
    next_step_cmd.add_argument("--stage", choices=tuple(WRITING_GATE.STAGE_TARGET_NAMES), required=True)
    next_step_cmd.add_argument("--stage-output", required=True)
    next_step_cmd.add_argument("--output", action="append", required=True)

    run_cycle_cmd = sub.add_parser("run-read-gates-cycle")
    run_cycle_cmd.add_argument("--writing-receipt", required=True)
    run_cycle_cmd.add_argument("--source-receipt", required=True)
    run_cycle_cmd.add_argument("--manifest", required=True)
    run_cycle_cmd.add_argument("--stage", choices=tuple(WRITING_GATE.STAGE_TARGET_NAMES), required=True)
    run_cycle_cmd.add_argument("--stage-output", required=True)
    run_cycle_cmd.add_argument("--output", action="append", required=True)
    run_cycle_cmd.add_argument("--skill-root", default=str(WRITING_GATE.SKILL_ROOT))

    bootstrap_cmd = sub.add_parser("bootstrap-project")
    bootstrap_cmd.add_argument("--project", required=True)
    bootstrap_cmd.add_argument("--project-dir", required=True)
    bootstrap_cmd.add_argument("--source-dir", action="append", required=True)
    bootstrap_cmd.add_argument("--skill-root", default=str(WRITING_GATE.SKILL_ROOT))
    bootstrap_cmd.add_argument("--batch-size", type=int, default=20)
    bootstrap_cmd.add_argument("--print-paths-json", action="store_true")

    emit_shell_cmd = sub.add_parser("emit-shell-template")
    emit_shell_cmd.add_argument("--project", required=True)
    emit_shell_cmd.add_argument("--project-dir", required=True)
    emit_shell_cmd.add_argument("--source-dir", action="append", required=True)
    emit_shell_cmd.add_argument("--stage", choices=tuple(WRITING_GATE.STAGE_TARGET_NAMES), required=True)
    emit_shell_cmd.add_argument("--stage-output", required=True)
    emit_shell_cmd.add_argument("--output", action="append", required=True)
    emit_shell_cmd.add_argument("--batch-size", type=int, default=20)

    start_flow_cmd = sub.add_parser("start-new-project-read-gates")
    start_flow_cmd.add_argument("--project", required=True)
    start_flow_cmd.add_argument("--project-dir", required=True)
    start_flow_cmd.add_argument("--source-dir", action="append", required=True)
    start_flow_cmd.add_argument("--stage", choices=tuple(WRITING_GATE.STAGE_TARGET_NAMES), required=True)
    start_flow_cmd.add_argument("--stage-output", required=True)
    start_flow_cmd.add_argument("--output", action="append", required=True)
    start_flow_cmd.add_argument("--skill-root", default=str(WRITING_GATE.SKILL_ROOT))
    start_flow_cmd.add_argument("--batch-size", type=int, default=20)

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

    if args.command == "export-batches":
        try:
            manifest = export_batches(
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                output_dir=Path(args.output_dir).resolve(),
                batch_size=args.batch_size,
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print("batch_read_gates: batches_exported")
        print(f"manifest: {Path(args.output_dir).resolve() / 'manifest.json'}")
        print(f"batch_size: {manifest['batch_size']}")
        print(f"total_entries: {manifest['total_entries']}")
        print(f"batch_count: {len(manifest['batches'])}")
        return 0

    if args.command == "prepare-batches":
        try:
            errors, summary = prepare_batches(
                project=args.project,
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                source_dirs=[Path(raw) for raw in args.source_dir],
                skill_root=Path(args.skill_root).resolve(),
                force_writing_receipt=bool(args.force_writing_receipt),
                output_dir=Path(args.output_dir).resolve(),
                batch_size=args.batch_size,
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
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
        print(f"manifest: {summary['manifest_path']}")
        print(f"batch_size: {summary['batch_size']}")
        print(f"total_entries: {summary['total_entries']}")
        print(f"batch_count: {summary['batch_count']}")
        print("batch_read_gates: prepared")
        return 0

    if args.command == "bootstrap-project":
        try:
            layout_errors, layout_summary = bootstrap_project_layout(
                project=args.project,
                project_dir=Path(args.project_dir).expanduser().resolve(),
            )
            if layout_errors:
                print("batch_read_gates: blocked")
                for item in layout_errors:
                    print(f"- {item}")
                return 2
            errors, summary = prepare_batches(
                project=args.project,
                writing_receipt=Path(layout_summary["writing_receipt"]).resolve(),
                source_receipt=Path(layout_summary["source_receipt"]).resolve(),
                source_dirs=[Path(raw) for raw in args.source_dir],
                skill_root=Path(args.skill_root).resolve(),
                force_writing_receipt=False,
                output_dir=Path(layout_summary["batch_dir"]).resolve(),
                batch_size=args.batch_size,
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print(f"project_dir: {layout_summary['project_dir']}")
        print(f"created_dir_count: {len(layout_summary['created_dirs'])}")
        print(f"layout_index: {layout_summary['layout_index']}")
        print(f"writing_receipt: {layout_summary['writing_receipt']}")
        print(f"source_receipt: {layout_summary['source_receipt']}")
        print(f"batch_dir: {layout_summary['batch_dir']}")
        print(f"writing_files: {summary['writing_files']}")
        print(f"source_count: {summary['source_count']}")
        print(f"source_files: {summary['source_files']}")
        print(f"manifest: {summary['manifest_path']}")
        print(f"batch_size: {summary['batch_size']}")
        print(f"total_entries: {summary['total_entries']}")
        print(f"batch_count: {summary['batch_count']}")
        if args.print_paths_json:
            print("paths_json:")
            print(
                json.dumps(
                    {
                        "project_dir": layout_summary["project_dir"],
                        "layout_index": layout_summary["layout_index"],
                        "writing_receipt": layout_summary["writing_receipt"],
                        "source_receipt": layout_summary["source_receipt"],
                        "batch_dir": layout_summary["batch_dir"],
                        "manifest": summary["manifest_path"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        if errors:
            print("batch_read_gates: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_read_gates: bootstrapped")
        return 0

    if args.command == "apply-batch":
        try:
            batch_path = Path(args.input).resolve()
            batch_sha = sha256_file(batch_path)
            summary = apply_batch(
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                batch_path=batch_path,
            )
            if args.consume:
                consume_sidecar(
                    batch_path,
                    input_sha256=batch_sha,
                    receipt_path=Path(args.source_receipt).resolve(),
                    receipt_sha256=sha256_file(Path(args.source_receipt).resolve()),
                    operation="batch-read-gates.apply-batch",
                    counts={
                        "updated_writing": summary["updated_writing"],
                        "updated_source": summary["updated_source"],
                    },
                )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print("batch_read_gates: batch_applied")
        print(f"updated_writing: {summary['updated_writing']}")
        print(f"updated_source: {summary['updated_source']}")
        print(f"cross_source_decisions: {summary['cross_source_decisions']}")
        return 0

    if args.command == "apply-manifest":
        try:
            summary = apply_manifest(
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                manifest_path=Path(args.manifest).resolve(),
                consume=bool(args.consume),
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print("batch_read_gates: manifest_applied")
        print(f"applied_batches: {summary['applied_batches']}")
        print(f"consumed_batches: {summary['consumed_batches']}")
        print(f"updated_writing: {summary['updated_writing']}")
        print(f"updated_source: {summary['updated_source']}")
        return 0

    if args.command == "finalize-batches":
        try:
            errors, summary = finalize_batches(
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                manifest_path=Path(args.manifest).resolve(),
                consume=bool(args.consume),
                stage=args.stage,
                stage_output=Path(args.stage_output).resolve(),
                source_outputs=[Path(raw) for raw in args.output],
                skill_root=Path(args.skill_root).resolve(),
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print(f"stage: {args.stage}")
        print(f"applied_batches: {summary['applied_batches']}")
        print(f"consumed_batches: {summary['consumed_batches']}")
        print(f"updated_writing: {summary['updated_writing']}")
        print(f"updated_source: {summary['updated_source']}")
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

    if args.command == "status":
        try:
            summary = inspect_manifest_batches(
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                manifest_path=Path(args.manifest).resolve(),
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print(f"manifest: {Path(args.manifest).resolve()}")
        print(f"batch_count: {summary['batch_count']}")
        print(f"pending: {summary['status_counts']['pending']}")
        print(f"in_progress: {summary['status_counts']['in_progress']}")
        print(f"reviewed: {summary['status_counts']['reviewed']}")
        print(f"consumed: {summary['status_counts']['consumed']}")
        print("batches:")
        for item in summary["batches"]:
            print(
                f"- {item['batch_id']} | {item['status']} | entries={item['entry_count']} | "
                f"{item['first_entry_id']} -> {item['last_entry_id']}"
            )
        if summary["pending_batches"]:
            print("unfinished_batches:")
            for batch_path in summary["pending_batches"]:
                print(f"- {batch_path}")
        print("batch_read_gates: status_ready")
        return 0

    if args.command == "show-batch":
        try:
            summary = inspect_batch_file(batch_path=Path(args.input).resolve())
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print(f"batch_id: {summary['batch_id']}")
        print(f"status: {summary['status']}")
        print(f"entry_count: {summary['entry_count']}")
        print(f"reviewed_by_current_model: {summary['reviewed_by_current_model']}")
        print(
            "semantic_fields_generated_by_script: "
            f"{summary['semantic_fields_generated_by_script']}"
        )
        if summary["review_started_at"]:
            print(f"review_started_at: {summary['review_started_at']}")
        if summary["reviewed_at"]:
            print(f"reviewed_at: {summary['reviewed_at']}")
        print("entries:")
        for item in summary["entries"]:
            preview = item["preview"]
            preview_part = f" | {preview}" if preview else ""
            print(
                f"- {item['entry_id']} | {item['gate']} | {item['relative_path']}{preview_part}"
            )
        print("batch_read_gates: batch_ready")
        return 0

    if args.command == "next-step":
        try:
            summary = suggest_next_step(
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                manifest_path=Path(args.manifest).resolve(),
                stage=args.stage,
                stage_output=Path(args.stage_output).resolve(),
                source_outputs=[Path(raw) for raw in args.output],
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print(f"action: {summary['action']}")
        print(f"reason: {summary['reason']}")
        if summary["next_command"]:
            print("next_command:")
            print(summary["next_command"])
        print("status_command:")
        print(summary["status_command"])
        print("batch_read_gates: next_step_ready")
        return 0

    if args.command == "run-read-gates-cycle":
        try:
            result = run_read_gates_cycle(
                writing_receipt=Path(args.writing_receipt).resolve(),
                source_receipt=Path(args.source_receipt).resolve(),
                manifest_path=Path(args.manifest).resolve(),
                stage=args.stage,
                stage_output=Path(args.stage_output).resolve(),
                source_outputs=[Path(raw) for raw in args.output],
                skill_root=Path(args.skill_root).resolve(),
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        print(f"action: {result['action']}")
        print(f"reason: {result['reason']}")
        print("status_command:")
        print(result["status_command"])
        if result["action"] == "complete_manual_batches":
            print("next_command:")
            print(result["next_command"])
            print("batch_read_gates: cycle_waiting_manual")
            return 0
        if result["action"] == "finalize_batches":
            summary = result["summary"]
            print(f"applied_batches: {summary['applied_batches']}")
            print(f"consumed_batches: {summary['consumed_batches']}")
            print(f"updated_writing: {summary['updated_writing']}")
            print(f"updated_source: {summary['updated_source']}")
            print(f"writing_read_count: {summary['writing_read_count']}")
            print(f"source_read_count: {summary['source_read_count']}")
            errors = result["errors"]
            if errors:
                print("batch_read_gates: blocked")
                for item in errors:
                    print(f"- {item}")
                return 2
            print("batch_read_gates: cycle_passed")
            return 0
        if result["action"] == "validate_receipts":
            summary = result["summary"]
            print(f"writing_file_count: {summary['writing_file_count']}")
            print(f"writing_read_count: {summary['writing_read_count']}")
            print(f"source_count: {summary['source_count']}")
            print(f"source_file_count: {summary['source_file_count']}")
            print(f"source_read_count: {summary['source_read_count']}")
            errors = result["errors"]
            if errors:
                print("batch_read_gates: blocked")
                for item in errors:
                    print(f"- {item}")
                return 2
            print("batch_read_gates: cycle_passed")
            return 0
        print("batch_read_gates: cycle_ready_for_design")
        return 0

    if args.command == "emit-shell-template":
        script = emit_shell_template(
            project=args.project,
            project_dir=Path(args.project_dir),
            source_dirs=[Path(raw) for raw in args.source_dir],
            stage=args.stage,
            stage_output=Path(args.stage_output),
            source_outputs=[Path(raw) for raw in args.output],
            batch_size=args.batch_size,
        )
        print(script)
        return 0

    if args.command == "start-new-project-read-gates":
        try:
            result = start_new_project_read_gates_flow(
                project=args.project,
                project_dir=Path(args.project_dir),
                source_dirs=[Path(raw).resolve() for raw in args.source_dir],
                stage=args.stage,
                stage_output=Path(args.stage_output).resolve(),
                source_outputs=[Path(raw).resolve() for raw in args.output],
                skill_root=Path(args.skill_root).resolve(),
                batch_size=args.batch_size,
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_read_gates: blocked")
            print(f"- {exc}")
            return 2
        layout = result["layout"]
        prepare = result["prepare"]
        cycle = result["cycle"]
        print(f"project_dir: {layout['project_dir']}")
        print(f"layout_index: {layout['layout_index']}")
        print(f"writing_receipt: {layout['writing_receipt']}")
        print(f"source_receipt: {layout['source_receipt']}")
        print(f"manifest: {prepare['manifest_path']}")
        print(f"batch_count: {prepare['batch_count']}")
        print(f"cycle_action: {cycle['action']}")
        print(f"cycle_reason: {cycle['reason']}")
        print("status_command:")
        print(cycle["status_command"])
        if cycle["action"] == "complete_manual_batches":
            print("next_command:")
            print(cycle["next_command"])
            print("batch_read_gates: new_project_waiting_manual")
            return 0
        if cycle["action"] in {"finalize_batches", "validate_receipts"}:
            errors = cycle["errors"]
            summary = cycle["summary"]
            if cycle["action"] == "finalize_batches":
                print(f"applied_batches: {summary['applied_batches']}")
                print(f"consumed_batches: {summary['consumed_batches']}")
                print(f"writing_read_count: {summary['writing_read_count']}")
                print(f"source_read_count: {summary['source_read_count']}")
            else:
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
            print("batch_read_gates: new_project_cycle_passed")
            return 0
        print("batch_read_gates: new_project_ready_for_design")
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
