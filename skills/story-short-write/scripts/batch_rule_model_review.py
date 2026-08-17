#!/usr/bin/env python3
"""High-level wrapper for rule-model review export/apply/validate flow."""

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


LEDGER = _load_module(
    "validate_rule_execution_ledger.py",
    "story_short_write_rule_execution_ledger_batch_wrapper",
)
SIDECAR = _load_module(
    "sidecar_lifecycle.py",
    "story_short_write_sidecar_lifecycle_batch_wrapper",
)


def _quote_shell(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _self_command() -> str:
    return f"python3 {_quote_shell(str((ROOT / 'batch_rule_model_review.py').resolve()))}"


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


def default_rule_model_review_paths(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None = None,
    review_manifest: Path | None = None,
    group_plan: Path | None = None,
) -> dict[str, Any]:
    resolved_project_dir = project_dir.expanduser().resolve()
    writing_assets = (resolved_project_dir / "写作资产").resolve()
    return {
        "project": project,
        "project_dir": resolved_project_dir,
        "ledger": (
            ledger.expanduser().resolve()
            if ledger is not None
            else (writing_assets / "规则执行台账.json").resolve()
        ),
        "review_manifest": (
            review_manifest.expanduser().resolve()
            if review_manifest is not None
            else (writing_assets / "规则模型分类批次.json").resolve()
        ),
        "group_plan": (
            group_plan.expanduser().resolve()
            if group_plan is not None
            else (writing_assets / "规则模型归并计划.json").resolve()
        ),
    }


def default_batch_inspection_output(project_dir: Path, batch_number: int) -> Path:
    return (
        project_dir.expanduser().resolve()
        / "写作资产"
        / "规则模型复核展开"
        / f"batch-{batch_number:03d}.json"
    ).resolve()


def default_all_batch_inspection_output(project_dir: Path) -> Path:
    return (
        project_dir.expanduser().resolve()
        / "写作资产"
        / "规则模型复核展开"
        / "全部批次索引.json"
    ).resolve()


def default_pending_groups_output(project_dir: Path) -> Path:
    return (
        project_dir.expanduser().resolve()
        / "写作资产"
        / "规则模型复核展开"
        / "待补规则组.json"
    ).resolve()


def _missing_plan_fields(group: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(group.get("canonical_rule_text") or "").strip():
        missing.append("canonical_rule_text")
    if str(group.get("taxonomy_decision") or "").strip() in {"", "pending"}:
        missing.append("taxonomy_decision")
    if not str(group.get("classification_notes") or "").strip():
        missing.append("classification_notes")
    applicability = str(group.get("applicability") or "").strip()
    if applicability in {"", "pending"}:
        missing.append("applicability")
    if not str(group.get("decision_reason") or "").strip():
        missing.append("decision_reason")
    if applicability == "applicable":
        if not str(group.get("target_stage") or "").strip():
            missing.append("target_stage")
        taxonomy = (
            group.get("taxonomy")
            if str(group.get("taxonomy_decision") or "").strip() == "override"
            else group.get("suggested_taxonomy")
        )
        role = str((taxonomy or {}).get("rule_role") or "")
        if (
            role in {"setting_constraint", "outline_constraint", "draft_constraint"}
            and not str(group.get("target_scene") or "").strip()
        ):
            missing.append("target_scene")
    return missing


def _effective_taxonomy(group: dict[str, Any]) -> dict[str, Any]:
    decision = str(group.get("taxonomy_decision") or "").strip()
    taxonomy = (
        group.get("taxonomy")
        if decision == "override"
        else group.get("suggested_taxonomy")
    )
    return taxonomy if isinstance(taxonomy, dict) else {}


def _plan_validation_issues(group: dict[str, Any]) -> list[str]:
    if str(group.get("taxonomy_decision") or "").strip() in {"", "pending"}:
        return []
    taxonomy = _effective_taxonomy(group)
    role = str(taxonomy.get("rule_role") or "").strip()
    mode = str(taxonomy.get("execution_mode") or "").strip()
    target = str(taxonomy.get("remediation_target") or "").strip()
    issues: list[str] = []
    if role not in LEDGER.VALID_RULE_ROLES:
        issues.append(f"invalid_rule_role:{role or '<empty>'}")
    if mode not in LEDGER.VALID_EXECUTION_MODES:
        issues.append(f"invalid_execution_mode:{mode or '<empty>'}")
    if target not in LEDGER.VALID_REMEDIATION_TARGETS:
        issues.append(f"invalid_remediation_target:{target or '<empty>'}")
    elif role in LEDGER.ROLE_REMEDIATION_TARGETS:
        if target not in LEDGER.ROLE_REMEDIATION_TARGETS[role]:
            issues.append(f"role_target_mismatch:{role}->{target}")
    return issues


def _summarize_plan_groups(groups: list[dict[str, Any]]) -> dict[str, Any]:
    missing_counts = {
        "canonical_rule_text": 0,
        "taxonomy_decision": 0,
        "classification_notes": 0,
        "applicability": 0,
        "decision_reason": 0,
        "target_stage": 0,
        "target_scene": 0,
    }
    complete = 0
    issue_counts: dict[str, int] = {}
    for group in groups:
        missing = _missing_plan_fields(group)
        issues = _plan_validation_issues(group)
        if not missing and not issues:
            complete += 1
        for field in missing:
            missing_counts[field] += 1
        for issue in issues:
            issue_type = issue.split(":", 1)[0]
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
    return {
        "groups": len(groups),
        "complete_groups": complete,
        "pending_groups": len(groups) - complete,
        "missing_fields": missing_counts,
        "validation_issues": issue_counts,
    }


def inspect_model_review_batch(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None,
    review_manifest: Path | None,
    group_plan: Path | None,
    batch_number: int,
    output: Path | None = None,
) -> dict[str, Any]:
    if batch_number < 1:
        raise ValueError("batch 必须大于 0")
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    expanded = LEDGER.read_model_review_batch(
        paths["ledger"],
        paths["review_manifest"],
        batch_number,
    )
    plan = load_json(paths["group_plan"], "规则模型归并计划")
    raw_groups = plan.get("groups")
    groups = (
        [group for group in raw_groups if isinstance(group, dict)]
        if isinstance(raw_groups, list)
        else []
    )
    invalid_group_count = (
        sum(not isinstance(group, dict) for group in raw_groups)
        if isinstance(raw_groups, list)
        else int(raw_groups is not None)
    )
    group_by_member: dict[str, dict[str, Any]] = {}
    for group in groups:
        for member_id in group.get("member_ids") or []:
            normalized_id = str(member_id or "").strip()
            if normalized_id:
                group_by_member[normalized_id] = group

    index: list[dict[str, Any]] = []
    batch_groups: list[dict[str, Any]] = []
    seen_canonical_ids: set[str] = set()
    for item in expanded.get("items") or []:
        if not isinstance(item, dict):
            continue
        rule_id = str(item.get("id") or "").strip()
        group = group_by_member.get(rule_id)
        missing_fields = _missing_plan_fields(group) if group else ["plan_group"]
        validation_issues = _plan_validation_issues(group) if group else []
        canonical_id = str((group or {}).get("canonical_id") or "")
        if group and canonical_id not in seen_canonical_ids:
            batch_groups.append(group)
            seen_canonical_ids.add(canonical_id)
        index.append(
            {
                "id": rule_id,
                "rule_text": item.get("rule_text"),
                "suggested_rule_role": item.get("suggested_rule_role"),
                "suggested_execution_mode": item.get("suggested_execution_mode"),
                "suggested_remediation_target": item.get(
                    "suggested_remediation_target"
                ),
                "source_ref_count": len(item.get("source_refs") or []),
                "case_count": len(item.get("cases") or []),
                "canonical_id": canonical_id,
                "taxonomy_decision": (group or {}).get("taxonomy_decision"),
                "applicability": (group or {}).get("applicability"),
                "missing_fields": missing_fields,
                "validation_issues": validation_issues,
            }
        )

    resolved_output = (
        output.expanduser().resolve()
        if output is not None
        else default_batch_inspection_output(paths["project_dir"], batch_number)
    )
    payload = {
        "version": "1.0",
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "ledger": str(paths["ledger"]),
        "review_manifest": str(paths["review_manifest"]),
        "group_plan": str(paths["group_plan"]),
        "output": str(resolved_output),
        "batch": batch_number,
        "index": index,
        "batch_plan_status": _summarize_plan_groups(batch_groups),
        "global_plan_status": {
            **_summarize_plan_groups(groups),
            "groups_field_is_list": isinstance(raw_groups, list),
            "invalid_group_count": invalid_group_count,
        },
        "expanded_batch": expanded,
    }
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def inspect_all_model_review_batches(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None,
    review_manifest: Path | None,
    group_plan: Path | None,
    output: Path | None = None,
) -> dict[str, Any]:
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    manifest = load_json(paths["review_manifest"], "规则模型分类批次")
    raw_batches = manifest.get("batches")
    if not isinstance(raw_batches, list) or not raw_batches:
        raise ValueError("规则模型分类批次缺少非空 batches")
    batch_numbers: list[int] = []
    for index, batch in enumerate(raw_batches):
        if not isinstance(batch, dict):
            raise ValueError(f"规则模型分类批次 batches[{index}] 必须是对象")
        batch_number = batch.get("batch")
        if not isinstance(batch_number, int) or batch_number < 1:
            raise ValueError(
                f"规则模型分类批次 batches[{index}].batch 必须是正整数"
            )
        batch_numbers.append(batch_number)
    if len(batch_numbers) != len(set(batch_numbers)):
        raise ValueError("规则模型分类批次存在重复 batch 编号")

    inspections: list[dict[str, Any]] = []
    total_entries = 0
    for batch_number in batch_numbers:
        inspection = inspect_model_review_batch(
            project=project,
            project_dir=paths["project_dir"],
            ledger=paths["ledger"],
            review_manifest=paths["review_manifest"],
            group_plan=paths["group_plan"],
            batch_number=batch_number,
        )
        inspections.append(inspection)
        total_entries += len(inspection.get("index") or [])

    resolved_output = (
        output.expanduser().resolve()
        if output is not None
        else default_all_batch_inspection_output(paths["project_dir"])
    )
    last_global_status = inspections[-1]["global_plan_status"]
    payload = {
        "version": "1.0",
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "ledger": str(paths["ledger"]),
        "review_manifest": str(paths["review_manifest"]),
        "group_plan": str(paths["group_plan"]),
        "output": str(resolved_output),
        "batch_count": len(inspections),
        "entry_count": total_entries,
        "batch_outputs": [
            {
                "batch": inspection["batch"],
                "output": inspection["output"],
                "entry_count": len(inspection.get("index") or []),
                "batch_plan_status": inspection["batch_plan_status"],
            }
            for inspection in inspections
        ],
        "global_plan_status": last_global_status,
    }
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def export_pending_groups(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None,
    review_manifest: Path | None,
    group_plan: Path | None,
    output: Path | None = None,
) -> dict[str, Any]:
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    plan = load_json(paths["group_plan"], "规则模型归并计划")
    groups = plan.get("groups")
    if not isinstance(groups, list):
        raise ValueError("规则模型归并计划 groups 必须是列表")
    manifest = load_json(paths["review_manifest"], "规则模型分类批次")
    rule_text_by_id: dict[str, str] = {}
    for batch in manifest.get("batches") or []:
        if not isinstance(batch, dict):
            continue
        batch_number = batch.get("batch")
        if not isinstance(batch_number, int):
            continue
        expanded = LEDGER.read_model_review_batch(
            paths["ledger"],
            paths["review_manifest"],
            batch_number,
        )
        for item in expanded.get("items") or []:
            if isinstance(item, dict):
                rule_id = str(item.get("id") or "").strip()
                if rule_id:
                    rule_text_by_id[rule_id] = str(item.get("rule_text") or "").strip()
    pending: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        missing = _missing_plan_fields(group)
        issues = _plan_validation_issues(group)
        if not missing and not issues:
            continue
        member_ids = [
            str(item or "").strip()
            for item in group.get("member_ids") or []
            if str(item or "").strip()
        ]
        canonical_id = str(group.get("canonical_id") or "").strip()
        pending.append(
            {
                "canonical_id": canonical_id,
                "member_ids": member_ids,
                "rule_text": rule_text_by_id.get(canonical_id)
                or next(
                    (
                        rule_text_by_id[item]
                        for item in member_ids
                        if item in rule_text_by_id
                    ),
                    "",
                ),
                "missing_fields": missing,
                "validation_issues": issues,
                "canonical_rule_text": group.get("canonical_rule_text"),
                "taxonomy_decision": group.get("taxonomy_decision"),
                "suggested_taxonomy": group.get("suggested_taxonomy"),
                "taxonomy": group.get("taxonomy"),
                "classification_notes": group.get("classification_notes"),
                "applicability": group.get("applicability"),
                "decision_reason": group.get("decision_reason"),
                "target_stage": group.get("target_stage"),
                "target_scene": group.get("target_scene"),
            }
        )
    resolved_output = (
        output.expanduser().resolve()
        if output is not None
        else default_pending_groups_output(paths["project_dir"])
    )
    payload = {
        "version": "1.0",
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "ledger": str(paths["ledger"]),
        "review_manifest": str(paths["review_manifest"]),
        "group_plan": str(paths["group_plan"]),
        "group_plan_sha256": LEDGER.sha256(paths["group_plan"]),
        "pending_group_count": len(pending),
        "groups": pending,
    }
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    payload["output"] = str(resolved_output)
    return payload


def prepare_model_review(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None,
    review_manifest: Path | None,
    group_plan: Path | None,
    batch_size: int,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    errors: list[str] = []
    if batch_size < 1:
        errors.append("batch-size 必须大于 0")
        return errors, {}
    if not paths["ledger"].is_file():
        errors.append(f"规则执行台账不存在: {paths['ledger']}")
        return errors, {}
    try:
        review_summary = LEDGER.export_model_review(
            paths["ledger"],
            paths["review_manifest"],
            batch_size,
        )
        plan_summary = LEDGER.export_model_group_plan_template(
            paths["ledger"],
            paths["review_manifest"],
            paths["group_plan"],
        )
        preset_errors, preset_summary = LEDGER.apply_model_group_presets(
            paths["ledger"],
            paths["group_plan"],
        )
        if preset_errors:
            errors.extend(preset_errors)
            return errors, {}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        return errors, {}
    summary = {
        "review_manifest": str(paths["review_manifest"]),
        "group_plan": str(paths["group_plan"]),
        "entries": review_summary["entries"],
        "batches": review_summary["batches"],
        "groups": plan_summary["groups"],
    }
    summary.update(
        {
            "preset_applied_groups": preset_summary.get("applied_groups", 0),
            "preset_fingerprint_mismatch_groups": preset_summary.get(
                "fingerprint_mismatch_groups", 0
            ),
            "preset_missing_groups": preset_summary.get("missing_preset_groups", 0),
        }
    )
    return [], summary


def _status_for_sidecar(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False, "status": "missing"}
    payload = load_json(path, label)
    schema = str(payload.get("schema_version") or "")
    if schema == SIDECAR.CONSUMED_SCHEMA or payload.get("status") == "consumed":
        return {
            "path": str(path),
            "exists": True,
            "status": "consumed",
            "operation": str(payload.get("operation") or ""),
        }
    info: dict[str, Any] = {"path": str(path), "exists": True, "status": "active"}
    info["schema_version"] = schema or str(payload.get("version") or "")
    if "reviewed_by_current_model" in payload:
        info["reviewed_by_current_model"] = payload.get("reviewed_by_current_model") is True
    if "semantic_fields_generated_by_script" in payload:
        info["semantic_fields_generated_by_script"] = (
            payload.get("semantic_fields_generated_by_script") is True
        )
    if isinstance(payload.get("groups"), list):
        info["groups"] = len(payload["groups"])
        pending = 0
        for group in payload["groups"]:
            if not isinstance(group, dict):
                continue
            if str(group.get("taxonomy_decision") or "").strip() in {"", "pending"}:
                pending += 1
                continue
            if str(group.get("applicability") or "").strip() in {"", "pending"}:
                pending += 1
        info["pending_groups"] = pending
    if isinstance(payload.get("batches"), list):
        info["batches"] = len(payload["batches"])
        info["entries"] = sum(
            len(batch.get("items") or [])
            for batch in payload["batches"]
            if isinstance(batch, dict)
        )
    return info


def inspect_rule_model_review_status(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None = None,
    review_manifest: Path | None = None,
    group_plan: Path | None = None,
) -> dict[str, Any]:
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    if not paths["ledger"].is_file():
        raise FileNotFoundError(f"规则执行台账不存在: {paths['ledger']}")
    ledger_payload = load_json(paths["ledger"], "规则执行台账")
    prewrite_errors = LEDGER.validate_prewrite_ledger(paths["ledger"])
    review_status = _status_for_sidecar(paths["review_manifest"], "规则模型分类批次")
    plan_status = _status_for_sidecar(paths["group_plan"], "规则模型归并计划")
    return {
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "ledger": str(paths["ledger"]),
        "ledger_gate_status": str(ledger_payload.get("gate_status") or "unknown"),
        "execution_summary": ledger_payload.get("execution_summary", {}),
        "review_manifest": review_status,
        "group_plan": plan_status,
        "prewrite_ready": not prewrite_errors,
        "prewrite_errors": prewrite_errors,
    }


def suggest_next_step(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None,
    review_manifest: Path | None,
    group_plan: Path | None,
    batch_size: int,
) -> dict[str, Any]:
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    status = inspect_rule_model_review_status(
        project=project,
        project_dir=project_dir,
        ledger=paths["ledger"],
        review_manifest=paths["review_manifest"],
        group_plan=paths["group_plan"],
    )
    status_command = (
        f"{_self_command()} status "
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    prepare_command = (
        f"{_self_command()} prepare-model-review "
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))} '
        f'--batch-size {batch_size}'
    )
    run_command = (
        f"{_self_command()} run-model-review-cycle "
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    inspect_all_command = (
        f"{_self_command()} inspect-all-model-review-batches "
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    pending_groups_command = (
        f"{_self_command()} export-pending-groups "
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    if status["review_manifest"]["status"] == "missing" or status["group_plan"]["status"] == "missing":
        return {
            "action": "prepare_model_review",
            "reason": "分类批次或归并计划骨架尚未生成，先导出正式人工载体",
            "next_command": prepare_command,
            "status_command": status_command,
        }
    if status["group_plan"]["status"] == "consumed" and not status["prewrite_ready"]:
        return {
            "action": "validate_prewrite",
            "reason": "模型归并计划已应用并消费，但台账写前校验尚未通过",
            "next_command": run_command,
            "status_command": status_command,
        }
    if status["group_plan"]["status"] == "consumed" and status["prewrite_ready"]:
        return {
            "action": "enter_setting_outline_phase",
            "reason": "规则模型复核已完成，台账已通过写前校验，可以继续设定/大纲阶段",
            "next_command": "",
            "status_command": status_command,
        }
    reviewed = status["group_plan"].get("reviewed_by_current_model") is True
    scripted = status["group_plan"].get("semantic_fields_generated_by_script") is True
    pending_groups = int(status["group_plan"].get("pending_groups") or 0)
    if not reviewed or scripted or pending_groups > 0:
        return {
            "action": "complete_manual_group_plan",
            "reason": "归并计划仍缺当前模型的人工裁决；先导出紧凑待补组，确需看完整 cases 时再展开全部批次",
            "next_command": pending_groups_command,
            "status_command": status_command,
            "inspect_all_command": inspect_all_command,
        }
    return {
        "action": "apply_model_groups",
        "reason": "归并计划已补完，下一步应用 canonical 分组并自动补跑写前校验",
        "next_command": run_command,
        "status_command": status_command,
    }


def run_model_review_cycle(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None,
    review_manifest: Path | None,
    group_plan: Path | None,
    batch_size: int,
) -> dict[str, Any]:
    suggestion = suggest_next_step(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
        batch_size=batch_size,
    )
    action = suggestion["action"]
    if action in {"prepare_model_review", "complete_manual_group_plan", "enter_setting_outline_phase"}:
        return suggestion
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    if action == "apply_model_groups":
        try:
            LEDGER.validate_model_review_source(
                paths["ledger"],
                paths["group_plan"],
                paths["review_manifest"],
            )
            plan_sha = LEDGER.sha256(paths["group_plan"])
            review_sha = LEDGER.sha256(paths["review_manifest"])
            errors, results = LEDGER.apply_model_group_plan(
                paths["ledger"],
                paths["group_plan"],
            )
            if errors:
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": errors,
                    "results": results,
                    "status_command": suggestion["status_command"],
                }
            ledger_sha = LEDGER.sha256(paths["ledger"])
            SIDECAR.consume_sidecar(
                paths["group_plan"],
                input_sha256=plan_sha,
                receipt_path=paths["ledger"],
                receipt_sha256=ledger_sha,
                operation="rule-model-groups.apply",
                counts={"groups": len(load_json(paths["group_plan"], "规则模型归并计划").get("groups") or [])},
            )
            review_payload = load_json(paths["review_manifest"], "规则模型分类批次")
            SIDECAR.consume_sidecar(
                paths["review_manifest"],
                input_sha256=review_sha,
                receipt_path=paths["ledger"],
                receipt_sha256=ledger_sha,
                operation="rule-model-review.consume",
                counts={
                    "batches": len(review_payload.get("batches") or []),
                    "entries": sum(
                        len(batch.get("items") or [])
                        for batch in review_payload.get("batches") or []
                        if isinstance(batch, dict)
                    ),
                },
            )
            prewrite_errors = LEDGER.validate_prewrite_ledger(paths["ledger"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {
                "action": action,
                "reason": suggestion["reason"],
                "errors": [str(exc)],
                "status_command": suggestion["status_command"],
            }
        return {
            "action": action,
            "reason": suggestion["reason"],
            "results": results,
            "prewrite_errors": prewrite_errors,
            "prewrite_ready": not prewrite_errors,
            "status_command": suggestion["status_command"],
        }
    if action == "validate_prewrite":
        prewrite_errors = LEDGER.validate_prewrite_ledger(paths["ledger"])
        return {
            "action": action,
            "reason": suggestion["reason"],
            "prewrite_errors": prewrite_errors,
            "prewrite_ready": not prewrite_errors,
            "status_command": suggestion["status_command"],
        }
    return suggestion


def emit_shell_template(
    *,
    project: str,
    project_dir: Path,
    ledger: Path | None,
    review_manifest: Path | None,
    group_plan: Path | None,
    batch_size: int,
) -> str:
    paths = default_rule_model_review_paths(
        project=project,
        project_dir=project_dir,
        ledger=ledger,
        review_manifest=review_manifest,
        group_plan=group_plan,
    )
    return "\n".join(
        [
            f"{_self_command()} prepare-model-review \\",
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --batch-size {batch_size}",
            "",
            f"{_self_command()} status \\",
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
            "",
            f"{_self_command()} inspect-all-model-review-batches \\",
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
            "",
            f"{_self_command()} export-pending-groups \\",
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
            "",
            f"{_self_command()} next-step \\",
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --batch-size {batch_size}",
            "",
            f"{_self_command()} run-model-review-cycle \\",
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --batch-size {batch_size}",
        ]
    )


def _print_status(status: dict[str, Any]) -> None:
    print("batch_rule_model_review: status")
    print(f"project: {status['project']}")
    print(f"project_dir: {status['project_dir']}")
    print(f"ledger: {status['ledger']}")
    print(f"ledger_gate_status: {status['ledger_gate_status']}")
    review = status["review_manifest"]
    plan = status["group_plan"]
    print(f"review_manifest: status={review['status']} path={review['path']}")
    if review.get("batches") is not None:
        print(f"review_batches: {review['batches']}")
    if review.get("entries") is not None:
        print(f"review_entries: {review['entries']}")
    print(f"group_plan: status={plan['status']} path={plan['path']}")
    if plan.get("groups") is not None:
        print(f"plan_groups: {plan['groups']}")
    if plan.get("pending_groups") is not None:
        print(f"plan_pending_groups: {plan['pending_groups']}")
    if "reviewed_by_current_model" in plan:
        print(f"reviewed_by_current_model: {plan['reviewed_by_current_model']}")
    if "semantic_fields_generated_by_script" in plan:
        print(f"semantic_fields_generated_by_script: {plan['semantic_fields_generated_by_script']}")
    print(f"prewrite_ready: {status['prewrite_ready']}")
    if status["prewrite_errors"]:
        print(f"prewrite_errors: {len(status['prewrite_errors'])}")


def _compact_text(value: Any, limit: int = 88) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _print_batch_inspection(payload: dict[str, Any]) -> None:
    print("batch_rule_model_review: batch-inspected")
    print(f"batch: {payload['batch']}")
    print(f"output: {payload['output']}")
    print("index: id | rule | suggested_taxonomy | cases | sources | plan | missing")
    for item in payload["index"]:
        taxonomy = "/".join(
            str(item.get(field) or "")
            for field in (
                "suggested_rule_role",
                "suggested_execution_mode",
                "suggested_remediation_target",
            )
        )
        plan = (
            f"{item.get('canonical_id') or '-'}:"
            f"{item.get('taxonomy_decision') or '-'}:"
            f"{item.get('applicability') or '-'}"
        )
        missing = ",".join(item.get("missing_fields") or []) or "-"
        issues = ",".join(item.get("validation_issues") or []) or "-"
        print(
            f"{item['id']} | {_compact_text(item.get('rule_text'))} | {taxonomy} | "
            f"{item['case_count']} | {item['source_ref_count']} | {plan} | "
            f"missing={missing}; issues={issues}"
        )
    for label in ("batch_plan_status", "global_plan_status"):
        status = payload[label]
        print(
            f"{label}: groups={status['groups']} complete={status['complete_groups']} "
            f"pending={status['pending_groups']} "
            f"missing={json.dumps(status['missing_fields'], ensure_ascii=False)} "
            f"issues={json.dumps(status['validation_issues'], ensure_ascii=False)}"
        )
    global_status = payload["global_plan_status"]
    print(f"plan_groups_field_is_list: {global_status['groups_field_is_list']}")
    print(f"plan_invalid_group_count: {global_status['invalid_group_count']}")


def _print_all_batch_inspections(payload: dict[str, Any]) -> None:
    print("batch_rule_model_review: all-batches-inspected")
    print(f"batch_count: {payload['batch_count']}")
    print(f"entry_count: {payload['entry_count']}")
    print(f"output: {payload['output']}")
    print("batches: batch | entries | output | pending_groups")
    for item in payload["batch_outputs"]:
        print(
            f"{item['batch']} | {item['entry_count']} | {item['output']} | "
            f"{item['batch_plan_status']['pending_groups']}"
        )
    status = payload["global_plan_status"]
    print(
        f"global_plan_status: groups={status['groups']} "
        f"complete={status['complete_groups']} pending={status['pending_groups']} "
        f"missing={json.dumps(status['missing_fields'], ensure_ascii=False)} "
        f"issues={json.dumps(status['validation_issues'], ensure_ascii=False)}"
    )


def _print_pending_groups(payload: dict[str, Any]) -> None:
    print("batch_rule_model_review: pending-groups-exported")
    print(f"output: {payload['output']}")
    print(f"pending_group_count: {payload['pending_group_count']}")
    print("groups: canonical_id | rule | missing | issues")
    for group in payload["groups"]:
        print(
            f"{group['canonical_id']} | {_compact_text(group.get('rule_text'))} | "
            f"{','.join(group.get('missing_fields') or []) or '-'} | "
            f"{','.join(group.get('validation_issues') or []) or '-'}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="High-level wrapper for rule-model review export/apply/validate flow."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in (
        "prepare-model-review",
        "status",
        "inspect-model-review-batch",
        "inspect-all-model-review-batches",
        "export-pending-groups",
        "next-step",
        "run-model-review-cycle",
        "emit-shell-template",
    ):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--project-dir", required=True)
        command.add_argument("--ledger")
        command.add_argument("--review-manifest")
        command.add_argument("--group-plan")
        if name in {
            "prepare-model-review",
            "next-step",
            "run-model-review-cycle",
            "emit-shell-template",
        }:
            command.add_argument("--batch-size", type=int, default=30)
        if name == "inspect-model-review-batch":
            command.add_argument("--batch", type=int, required=True)
            command.add_argument("--output")
        if name == "inspect-all-model-review-batches":
            command.add_argument("--output")
        if name == "export-pending-groups":
            command.add_argument("--output")

    args = parser.parse_args()
    common_kwargs = {
        "project": args.project,
        "project_dir": Path(args.project_dir).resolve(),
        "ledger": Path(args.ledger).resolve() if args.ledger else None,
        "review_manifest": Path(args.review_manifest).resolve() if args.review_manifest else None,
        "group_plan": Path(args.group_plan).resolve() if args.group_plan else None,
    }

    if args.command == "prepare-model-review":
        errors, summary = prepare_model_review(
            **common_kwargs,
            batch_size=args.batch_size,
        )
        if errors:
            print("batch_rule_model_review: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_rule_model_review: prepared")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "status":
        try:
            status = inspect_rule_model_review_status(**common_kwargs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_rule_model_review: blocked")
            print(f"- {exc}")
            return 2
        _print_status(status)
        return 0
    if args.command == "inspect-model-review-batch":
        try:
            payload = inspect_model_review_batch(
                **common_kwargs,
                batch_number=args.batch,
                output=Path(args.output).resolve() if args.output else None,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_rule_model_review: blocked")
            print(f"- {exc}")
            return 2
        _print_batch_inspection(payload)
        return 0
    if args.command == "inspect-all-model-review-batches":
        try:
            payload = inspect_all_model_review_batches(
                **common_kwargs,
                output=Path(args.output).resolve() if args.output else None,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_rule_model_review: blocked")
            print(f"- {exc}")
            return 2
        _print_all_batch_inspections(payload)
        return 0
    if args.command == "export-pending-groups":
        try:
            payload = export_pending_groups(
                **common_kwargs,
                output=Path(args.output).resolve() if args.output else None,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_rule_model_review: blocked")
            print(f"- {exc}")
            return 2
        _print_pending_groups(payload)
        return 0
    if args.command == "next-step":
        try:
            suggestion = suggest_next_step(
                **common_kwargs,
                batch_size=args.batch_size,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_rule_model_review: blocked")
            print(f"- {exc}")
            return 2
        print("batch_rule_model_review: next-step")
        print(f"action: {suggestion['action']}")
        print(f"reason: {suggestion['reason']}")
        if suggestion["next_command"]:
            print(f"next_command: {suggestion['next_command']}")
        return 0
    if args.command == "run-model-review-cycle":
        result = run_model_review_cycle(
            **common_kwargs,
            batch_size=args.batch_size,
        )
        print(f"batch_rule_model_review: {result['action']}")
        print(f"reason: {result['reason']}")
        if result.get("results"):
            for item in result["results"]:
                print(
                    f"group[{item['group']}]: canonical={item['canonical_id']} "
                    f"members={item['members']} cases={item['cases']}"
                )
        if result.get("errors"):
            for item in result["errors"]:
                print(f"- {item}")
            return 2
        if "prewrite_ready" in result:
            print(f"prewrite_ready: {result['prewrite_ready']}")
        if result.get("prewrite_errors"):
            for item in result["prewrite_errors"]:
                print(f"- {item}")
            return 2
        if result.get("next_command"):
            print(f"next_command: {result['next_command']}")
        return 0
    if args.command == "emit-shell-template":
        print(
            emit_shell_template(
                **common_kwargs,
                batch_size=args.batch_size,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
