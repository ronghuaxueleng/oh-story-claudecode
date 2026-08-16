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
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_rule_model_review.py" status '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    prepare_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_rule_model_review.py" prepare-model-review '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))} '
        f'--batch-size {batch_size}'
    )
    run_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_rule_model_review.py" run-model-review-cycle '
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
            "reason": "归并计划仍缺当前模型的人工裁决，先逐批读案例并补完 group 语义字段",
            "next_command": status_command,
            "status_command": status_command,
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
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_rule_model_review.py" prepare-model-review \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --batch-size {batch_size}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_rule_model_review.py" status \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_rule_model_review.py" next-step \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --batch-size {batch_size}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_rule_model_review.py" run-model-review-cycle \\',
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="High-level wrapper for rule-model review export/apply/validate flow."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in (
        "prepare-model-review",
        "status",
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
