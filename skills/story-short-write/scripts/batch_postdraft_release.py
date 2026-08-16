#!/usr/bin/env python3
"""High-level wrapper for post-draft deep-review release workflow."""

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


OPENING = _load_module(
    "validate_opening_contract.py",
    "story_short_write_batch_postdraft_opening",
)
POST = _load_module(
    "validate_post_write_human_review_gate.py",
    "story_short_write_batch_postdraft_human_review",
)
LEDGER = _load_module(
    "validate_rule_execution_ledger.py",
    "story_short_write_batch_postdraft_ledger",
)
COMPLETE = _load_module(
    "validate_short_write_completion.py",
    "story_short_write_batch_postdraft_completion",
)
FORMAL_AUDIT = _load_module(
    "batch_formal_audit.py",
    "story_short_write_batch_postdraft_formal_audit",
)


OPENING_SOURCE_FILENAME = "可直接仿写_导语拆解表.md"


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def default_paths(
    *,
    project: str,
    project_dir: Path,
    writing_receipt: Path | None = None,
    source_receipt: Path | None = None,
    ledger: Path | None = None,
    setting: Path | None = None,
    outline: Path | None = None,
    draft: Path | None = None,
    sequence_receipt: Path | None = None,
    opening_receipt: Path | None = None,
    opening_source: Path | None = None,
    post_write_receipt: Path | None = None,
    completion_state: Path | None = None,
    formal_audit: Path | None = None,
    anti_false_pass_review: Path | None = None,
    platform_format_receipt: Path | None = None,
    base_text: Path | None = None,
) -> dict[str, Path | str | None]:
    resolved_project_dir = project_dir.expanduser().resolve()
    assets = (resolved_project_dir / "写作资产").resolve()
    return {
        "project": project,
        "project_dir": resolved_project_dir,
        "writing_receipt": (
            writing_receipt.expanduser().resolve()
            if writing_receipt is not None
            else (assets / "写作规则读取回执.json").resolve()
        ),
        "source_receipt": (
            source_receipt.expanduser().resolve()
            if source_receipt is not None
            else (assets / "拆文读取回执.json").resolve()
        ),
        "ledger": (
            ledger.expanduser().resolve()
            if ledger is not None
            else (assets / "规则执行台账.json").resolve()
        ),
        "setting": (
            setting.expanduser().resolve()
            if setting is not None
            else (resolved_project_dir / "设定.md").resolve()
        ),
        "outline": (
            outline.expanduser().resolve()
            if outline is not None
            else (resolved_project_dir / "小节大纲.md").resolve()
        ),
        "draft": (
            draft.expanduser().resolve()
            if draft is not None
            else (resolved_project_dir / "正文.md").resolve()
        ),
        "sequence_receipt": (
            sequence_receipt.expanduser().resolve()
            if sequence_receipt is not None
            else (assets / "顺序契约回执.json").resolve()
        ),
        "opening_receipt": (
            opening_receipt.expanduser().resolve()
            if opening_receipt is not None
            else (assets / "开头承重契约回执_正文.json").resolve()
        ),
        "opening_source": opening_source.expanduser().resolve() if opening_source is not None else None,
        "post_write_receipt": (
            post_write_receipt.expanduser().resolve()
            if post_write_receipt is not None
            else (assets / "写后人工语义复核回执.json").resolve()
        ),
        "completion_state": (
            completion_state.expanduser().resolve()
            if completion_state is not None
            else (assets / "短篇全流程状态.json").resolve()
        ),
        "formal_audit": (
            formal_audit.expanduser().resolve()
            if formal_audit is not None
            else (assets / "正式审计" / "正文.full_audit.json").resolve()
        ),
        "anti_false_pass_review": (
            anti_false_pass_review.expanduser().resolve()
            if anti_false_pass_review is not None
            else (assets / "外部分块审计对齐摘要.json").resolve()
        ),
        "platform_format_receipt": (
            platform_format_receipt.expanduser().resolve()
            if platform_format_receipt is not None
            else (assets / "平台格式校验回执.json").resolve()
        ),
        "formal_audit_dir": (assets / "正式审计").resolve(),
        "internal_standard": (assets / "内部审计标准.json").resolve(),
        "alignment_csv": (assets / "外部分块审计对齐.csv").resolve(),
        "alignment_summary": (
            anti_false_pass_review.expanduser().resolve()
            if anti_false_pass_review is not None
            else (assets / "外部分块审计对齐摘要.json").resolve()
        ),
        "base_text": base_text.expanduser().resolve() if base_text is not None else None,
    }


def infer_opening_source(
    *,
    source_receipt: Path,
    opening_receipt: Path,
    explicit_source: Path | None,
) -> Path:
    if explicit_source is not None:
        return explicit_source.expanduser().resolve()
    if opening_receipt.is_file():
        opening_payload = load_json(opening_receipt, "开头承重契约回执_正文")
        binding = opening_payload.get("primary_source")
        if isinstance(binding, dict) and str(binding.get("path") or "").strip():
            return Path(str(binding["path"])).expanduser().resolve()
    source_payload = load_json(source_receipt, "拆文读取回执")
    sources = source_payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("拆文读取回执缺少 sources")
    preferred = None
    for item in sources:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        if role in {"main", "primary", "主体"}:
            preferred = item
            break
        if preferred is None:
            preferred = item
    if not isinstance(preferred, dict) or not str(preferred.get("root") or "").strip():
        raise ValueError("拆文读取回执无法推导主体拆书根目录")
    return (Path(str(preferred["root"])).expanduser().resolve() / OPENING_SOURCE_FILENAME).resolve()


def build_completion_checks(paths: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "label": "writing_rule_gate",
            "kind": "json_field",
            "path": str(paths["writing_receipt"]),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "source_read_gate",
            "kind": "json_field",
            "path": str(paths["source_receipt"]),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "write_release_gate",
            "kind": "json_field",
            "path": str(paths["project_dir"] / "写作资产" / "正文开写前最终放行回执.json"),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "rule_execution_gate",
            "kind": "json_field",
            "path": str(paths["ledger"]),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "sequence_contract",
            "kind": "json_field",
            "path": str(paths["sequence_receipt"]),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "opening_contract",
            "kind": "json_field",
            "path": str(paths["opening_receipt"]),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "prose_granularity_contract",
            "kind": "json_field",
            "path": str(paths["project_dir"] / "写作资产" / "全文文字颗粒度契约回执.json"),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "emotional_granularity_contract",
            "kind": "json_field",
            "path": str(paths["project_dir"] / "写作资产" / "全文情绪颗粒度契约回执.json"),
            "field": "draft_status",
            "expected": "passed",
        },
        {
            "label": "formal_audit",
            "kind": "file_exists",
            "path": str(paths["formal_audit"]),
        },
        {
            "label": "post_write_human_review",
            "kind": "json_field",
            "path": str(paths["post_write_receipt"]),
            "field": "gate_status",
            "expected": "passed",
        },
        {
            "label": "anti_false_pass_review",
            "kind": "file_exists",
            "path": str(paths["anti_false_pass_review"]),
        },
        {
            "label": "platform_format_gate",
            "kind": "json_field",
            "path": str(paths["platform_format_receipt"]),
            "field": "gate_status",
            "expected": "passed",
        },
    ]


def prepare_postdraft_release(
    *,
    project: str,
    project_dir: Path,
    writing_receipt: Path | None = None,
    source_receipt: Path | None = None,
    ledger: Path | None = None,
    setting: Path | None = None,
    outline: Path | None = None,
    draft: Path | None = None,
    sequence_receipt: Path | None = None,
    opening_receipt: Path | None = None,
    opening_source: Path | None = None,
    post_write_receipt: Path | None = None,
    completion_state: Path | None = None,
    formal_audit: Path | None = None,
    anti_false_pass_review: Path | None = None,
    platform_format_receipt: Path | None = None,
    base_text: Path | None = None,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        ledger=ledger,
        setting=setting,
        outline=outline,
        draft=draft,
        sequence_receipt=sequence_receipt,
        opening_receipt=opening_receipt,
        opening_source=opening_source,
        post_write_receipt=post_write_receipt,
        completion_state=completion_state,
        formal_audit=formal_audit,
        anti_false_pass_review=anti_false_pass_review,
        platform_format_receipt=platform_format_receipt,
        base_text=base_text,
    )
    errors: list[str] = []
    summary: dict[str, Any] = {}
    try:
        opening_source_path = infer_opening_source(
            source_receipt=Path(str(paths["source_receipt"])),
            opening_receipt=Path(str(paths["opening_receipt"])),
            explicit_source=paths["opening_source"] if isinstance(paths["opening_source"], Path) else None,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)], {}
    if not Path(str(paths["opening_receipt"])).is_file():
        try:
            payload = OPENING.create_receipt(
                project,
                opening_source_path,
                Path(str(paths["draft"])),
                "draft",
            )
            _write_json(Path(str(paths["opening_receipt"])), payload)
            summary["opening_receipt_initialized"] = str(paths["opening_receipt"])
        except (OSError, ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
            errors.append(str(exc))
    if not Path(str(paths["post_write_receipt"])).is_file():
        try:
            payload = POST.create_receipt(
                project,
                Path(str(paths["draft"])),
                paths["base_text"] if isinstance(paths["base_text"], Path) else None,
            )
            _write_json(Path(str(paths["post_write_receipt"])), payload)
            summary["post_write_receipt_initialized"] = str(paths["post_write_receipt"])
        except (OSError, ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
            errors.append(str(exc))
    if not Path(str(paths["completion_state"])).is_file():
        payload = {
            "version": "1.0",
            "workflow": "story-short-write",
            "project_path": str(Path(str(paths["project_dir"])).resolve()),
            "status": "active",
            "imitation_mode": False,
            "started_at": COMPLETE.now_iso(),
            "checks": build_completion_checks(paths),
            "next_action": "继续完成深审尾链，再执行 mark-complete。",
            "pause_reason": "",
            "blocker": {},
        }
        COMPLETE.write_state(Path(str(paths["completion_state"])), payload)
        summary["completion_state_initialized"] = str(paths["completion_state"])
    return errors, summary


def inspect_postdraft_release_status(
    *,
    project: str,
    project_dir: Path,
    writing_receipt: Path | None = None,
    source_receipt: Path | None = None,
    ledger: Path | None = None,
    setting: Path | None = None,
    outline: Path | None = None,
    draft: Path | None = None,
    sequence_receipt: Path | None = None,
    opening_receipt: Path | None = None,
    opening_source: Path | None = None,
    post_write_receipt: Path | None = None,
    completion_state: Path | None = None,
    formal_audit: Path | None = None,
    anti_false_pass_review: Path | None = None,
    platform_format_receipt: Path | None = None,
    base_text: Path | None = None,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        writing_receipt=writing_receipt,
        source_receipt=source_receipt,
        ledger=ledger,
        setting=setting,
        outline=outline,
        draft=draft,
        sequence_receipt=sequence_receipt,
        opening_receipt=opening_receipt,
        opening_source=opening_source,
        post_write_receipt=post_write_receipt,
        completion_state=completion_state,
        formal_audit=formal_audit,
        anti_false_pass_review=anti_false_pass_review,
        platform_format_receipt=platform_format_receipt,
        base_text=base_text,
    )
    opening_errors: list[str] | None = None
    post_errors: list[str] | None = None
    ledger_errors: list[str] | None = None
    completion_errors: list[str] | None = None
    opening_exists = Path(str(paths["opening_receipt"])).is_file()
    post_exists = Path(str(paths["post_write_receipt"])).is_file()
    ledger_exists = Path(str(paths["ledger"])).is_file()
    completion_exists = Path(str(paths["completion_state"])).is_file()
    opening_source_path = None
    if opening_exists:
        try:
            opening_source_path = infer_opening_source(
                source_receipt=Path(str(paths["source_receipt"])),
                opening_receipt=Path(str(paths["opening_receipt"])),
                explicit_source=paths["opening_source"] if isinstance(paths["opening_source"], Path) else None,
            )
            opening_errors, opening_summary = OPENING.validate_receipt(
                Path(str(paths["opening_receipt"])),
                opening_source_path,
                Path(str(paths["draft"])),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            opening_errors = [str(exc)]
            opening_summary = {"passed_checks": 0}
    else:
        opening_summary = {"passed_checks": 0}
    if post_exists:
        try:
            post_errors = POST.validate_sequence_receipt_for_text(
                Path(str(paths["sequence_receipt"])),
                Path(str(paths["draft"])),
            ) + POST.validate_receipt(
                Path(str(paths["post_write_receipt"])),
                Path(str(paths["draft"])),
            )[0]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            post_errors = [str(exc)]
    if ledger_exists:
        try:
            ledger_errors, ledger_summary = LEDGER.validate_ledger(Path(str(paths["ledger"])))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            ledger_errors = [str(exc)]
            ledger_summary = {}
    else:
        ledger_summary = {}
    if completion_exists:
        _, completion_errors = COMPLETE.validate_state(Path(str(paths["completion_state"])))
    formal_audit_status = FORMAL_AUDIT.inspect_formal_audit_status(
        project=project,
        project_dir=Path(str(paths["project_dir"])),
        draft=Path(str(paths["draft"])),
        audit_dir=Path(str(paths["formal_audit_dir"])),
        internal_standard=Path(str(paths["internal_standard"])),
        alignment_summary=Path(str(paths["alignment_summary"])),
        alignment_csv=Path(str(paths["alignment_csv"])),
        with_calibration=True,
    )
    return {
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "opening_receipt": {
            "path": str(paths["opening_receipt"]),
            "exists": opening_exists,
            "passed": opening_exists and not opening_errors,
            "errors": opening_errors or [],
            "passed_checks": opening_summary.get("passed_checks", 0),
            "source": str(opening_source_path) if opening_source_path else "",
        },
        "post_write_receipt": {
            "path": str(paths["post_write_receipt"]),
            "exists": post_exists,
            "passed": post_exists and not post_errors,
            "errors": post_errors or [],
        },
        "ledger": {
            "path": str(paths["ledger"]),
            "exists": ledger_exists,
            "passed": ledger_exists and not ledger_errors,
            "errors": ledger_errors or [],
            "summary": ledger_summary,
        },
        "formal_audit_exists": Path(str(paths["formal_audit"])).is_file(),
        "anti_false_pass_review_exists": Path(str(paths["anti_false_pass_review"])).is_file(),
        "formal_audit_status": formal_audit_status,
        "completion_state": {
            "path": str(paths["completion_state"]),
            "exists": completion_exists,
            "valid": completion_exists and not completion_errors,
            "errors": completion_errors or [],
        },
    }


def suggest_next_step(**kwargs) -> dict[str, Any]:
    project = kwargs["project"]
    project_dir = kwargs["project_dir"]
    status = inspect_postdraft_release_status(**kwargs)
    status_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_postdraft_release.py" status '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}'
    )
    prepare_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_postdraft_release.py" prepare-postdraft-release '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}'
    )
    run_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_postdraft_release.py" run-postdraft-release-cycle '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}'
    )
    audit_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_formal_audit.py" run-audit-cycle '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(project_dir.expanduser().resolve()))} '
        '--with-calibration'
    )
    if not status["opening_receipt"]["exists"] or not status["post_write_receipt"]["exists"] or not status["completion_state"]["exists"]:
        return {
            "action": "prepare_postdraft_release",
            "reason": "深审尾链的人工回执或 completion 状态文件尚未初始化",
            "next_command": prepare_command,
            "status_command": status_command,
        }
    if not status["opening_receipt"]["passed"]:
        return {
            "action": "complete_opening_receipt",
            "reason": "正文开头承重契约还没补到 passed",
            "next_command": status_command,
            "status_command": status_command,
        }
    formal_audit_action = str(status["formal_audit_status"].get("audit_json", {}).get("exists"))
    if status["formal_audit_status"]["audit_json"]["errors"] or not status["formal_audit_status"]["audit_json"]["exists"] or not status["formal_audit_status"]["audit_json"]["fresh"] or not status["formal_audit_status"]["alignment_summary"]["exists"] or not status["formal_audit_status"]["alignment_summary"]["fresh"] or not status["formal_audit_status"]["internal_standard"]["exists"] or not status["formal_audit_status"]["internal_standard"]["fresh"]:
        return {
            "action": "run_formal_audit_chain",
            "reason": "正式审计链产物缺失、过期或绑定异常，先统一补跑正式审计和题材首次校准",
            "next_command": audit_command,
            "status_command": status_command,
        }
    if not status["ledger"]["passed"]:
        return {
            "action": "bind_and_validate_ledger",
            "reason": "规则执行台账还没完成最终预检/绑定/校验",
            "next_command": run_command,
            "status_command": status_command,
        }
    if not status["post_write_receipt"]["passed"]:
        return {
            "action": "complete_post_write_receipt",
            "reason": "写后人工语义复核回执还没补到 passed",
            "next_command": status_command,
            "status_command": status_command,
        }
    if not status["completion_state"]["valid"] or not status["formal_audit_exists"] or not status["anti_false_pass_review_exists"]:
        return {
            "action": "complete_completion_dependencies",
            "reason": "completion 收口所需的正式审计/反假通过产物或状态文件校验仍未齐",
            "next_command": status_command,
            "status_command": status_command,
        }
    return {
        "action": "mark_complete",
        "reason": "深审尾链全部就绪，下一步直接执行 mark-complete",
        "next_command": run_command,
        "status_command": status_command,
    }


def run_postdraft_release_cycle(**kwargs) -> dict[str, Any]:
    paths = default_paths(
        project=kwargs["project"],
        project_dir=kwargs["project_dir"],
        writing_receipt=kwargs.get("writing_receipt"),
        source_receipt=kwargs.get("source_receipt"),
        ledger=kwargs.get("ledger"),
        setting=kwargs.get("setting"),
        outline=kwargs.get("outline"),
        draft=kwargs.get("draft"),
        sequence_receipt=kwargs.get("sequence_receipt"),
        opening_receipt=kwargs.get("opening_receipt"),
        opening_source=kwargs.get("opening_source"),
        post_write_receipt=kwargs.get("post_write_receipt"),
        completion_state=kwargs.get("completion_state"),
        formal_audit=kwargs.get("formal_audit"),
        anti_false_pass_review=kwargs.get("anti_false_pass_review"),
        platform_format_receipt=kwargs.get("platform_format_receipt"),
        base_text=kwargs.get("base_text"),
    )
    completed_steps: list[str] = []
    for _ in range(4):
        suggestion = suggest_next_step(**kwargs)
        action = suggestion["action"]
        if action == "prepare_postdraft_release":
            errors, summary = prepare_postdraft_release(**kwargs)
            result = {
                "action": action,
                "reason": suggestion["reason"],
                "completed_steps": completed_steps,
                "summary": summary,
                "status_command": suggestion["status_command"],
            }
            if errors:
                result["errors"] = errors
            return result
        if action in {
            "complete_opening_receipt",
            "complete_post_write_receipt",
            "complete_completion_dependencies",
        }:
            suggestion["completed_steps"] = completed_steps
            return suggestion
        if action == "run_formal_audit_chain":
            result = FORMAL_AUDIT.run_audit_cycle(
                project=kwargs["project"],
                project_dir=Path(str(paths["project_dir"])),
                draft=Path(str(paths["draft"])),
                audit_dir=Path(str(paths["formal_audit_dir"])),
                internal_standard=Path(str(paths["internal_standard"])),
                alignment_summary=Path(str(paths["alignment_summary"])),
                alignment_csv=Path(str(paths["alignment_csv"])),
                with_calibration=True,
                strict_calibration=False,
            )
            if result.get("errors"):
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": result["errors"],
                    "summary": result,
                    "completed_steps": completed_steps,
                    "status_command": suggestion["status_command"],
                }
            completed_steps.append("run_formal_audit_chain")
            continue
        if action == "bind_and_validate_ledger":
            artifacts = [
                f"设定={paths['setting']}",
                f"大纲={paths['outline']}",
                f"正文={paths['draft']}",
            ]
            errors, report = LEDGER.preflight_final_rebind(
                Path(str(paths["ledger"])),
                artifacts,
                assume_full_rewrite=False,
            )
            if errors:
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": errors,
                    "report": report,
                    "completed_steps": completed_steps,
                    "status_command": suggestion["status_command"],
                }
            bind_errors = LEDGER.bind_artifacts(Path(str(paths["ledger"])), artifacts)
            if bind_errors:
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": bind_errors,
                    "report": report,
                    "completed_steps": completed_steps,
                    "status_command": suggestion["status_command"],
                }
            ledger_errors, ledger_summary = LEDGER.validate_ledger(Path(str(paths["ledger"])))
            if ledger_errors:
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": ledger_errors,
                    "summary": ledger_summary,
                    "completed_steps": completed_steps,
                    "status_command": suggestion["status_command"],
                }
            completed_steps.append("bind_and_validate_ledger")
            continue
        state_path = Path(str(paths["completion_state"]))
        data, errors = COMPLETE.validate_state(state_path)
        if errors:
            return {
                "action": action,
                "reason": suggestion["reason"],
                "errors": errors,
                "completed_steps": completed_steps,
                "status_command": suggestion["status_command"],
            }
        data["status"] = "complete"
        data["completed_at"] = COMPLETE.now_iso()
        data["next_action"] = ""
        COMPLETE.write_state(state_path, data)
        return {
            "action": action,
            "reason": suggestion["reason"],
            "completed_steps": completed_steps,
            "completion_state": str(state_path),
            "status": "complete",
            "status_command": suggestion["status_command"],
        }
    return {
        "action": "loop_guard_triggered",
        "reason": "高层深审尾链执行次数异常，请改用 status 检查当前状态",
        "completed_steps": completed_steps,
    }


def emit_shell_template(*, project: str, project_dir: Path) -> str:
    resolved_dir = project_dir.expanduser().resolve()
    return "\n".join(
        [
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_postdraft_release.py" prepare-postdraft-release \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_dir))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_postdraft_release.py" status \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_dir))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_postdraft_release.py" next-step \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_dir))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_postdraft_release.py" run-postdraft-release-cycle \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_dir))}",
        ]
    )


def _print_status(status: dict[str, Any]) -> None:
    print("batch_postdraft_release: status")
    print(f"project: {status['project']}")
    print(f"project_dir: {status['project_dir']}")
    print(f"opening_receipt_passed: {status['opening_receipt']['passed']}")
    print(f"post_write_receipt_passed: {status['post_write_receipt']['passed']}")
    print(f"ledger_passed: {status['ledger']['passed']}")
    print(f"formal_audit_exists: {status['formal_audit_exists']}")
    print(f"anti_false_pass_review_exists: {status['anti_false_pass_review_exists']}")
    print(f"formal_audit_json_fresh: {status['formal_audit_status']['audit_json']['fresh']}")
    print(f"alignment_summary_fresh: {status['formal_audit_status']['alignment_summary']['fresh']}")
    print(f"completion_state_valid: {status['completion_state']['valid']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in (
        "prepare-postdraft-release",
        "status",
        "next-step",
        "run-postdraft-release-cycle",
        "emit-shell-template",
    ):
        cmd = sub.add_parser(command)
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--project-dir", required=True)
        cmd.add_argument("--writing-receipt")
        cmd.add_argument("--source-receipt")
        cmd.add_argument("--ledger")
        cmd.add_argument("--setting")
        cmd.add_argument("--outline")
        cmd.add_argument("--draft")
        cmd.add_argument("--sequence-receipt")
        cmd.add_argument("--opening-receipt")
        cmd.add_argument("--opening-source")
        cmd.add_argument("--post-write-receipt")
        cmd.add_argument("--completion-state")
        cmd.add_argument("--formal-audit")
        cmd.add_argument("--anti-false-pass-review")
        cmd.add_argument("--platform-format-receipt")
        cmd.add_argument("--base-text")
    args = parser.parse_args()
    kwargs = {
        "project": args.project,
        "project_dir": Path(args.project_dir),
        "writing_receipt": Path(args.writing_receipt) if args.writing_receipt else None,
        "source_receipt": Path(args.source_receipt) if args.source_receipt else None,
        "ledger": Path(args.ledger) if args.ledger else None,
        "setting": Path(args.setting) if args.setting else None,
        "outline": Path(args.outline) if args.outline else None,
        "draft": Path(args.draft) if args.draft else None,
        "sequence_receipt": Path(args.sequence_receipt) if args.sequence_receipt else None,
        "opening_receipt": Path(args.opening_receipt) if args.opening_receipt else None,
        "opening_source": Path(args.opening_source) if args.opening_source else None,
        "post_write_receipt": Path(args.post_write_receipt) if args.post_write_receipt else None,
        "completion_state": Path(args.completion_state) if args.completion_state else None,
        "formal_audit": Path(args.formal_audit) if args.formal_audit else None,
        "anti_false_pass_review": Path(args.anti_false_pass_review) if args.anti_false_pass_review else None,
        "platform_format_receipt": Path(args.platform_format_receipt) if args.platform_format_receipt else None,
        "base_text": Path(args.base_text) if args.base_text else None,
    }
    if args.command == "prepare-postdraft-release":
        errors, summary = prepare_postdraft_release(**kwargs)
        if errors:
            print("batch_postdraft_release: blocked (prepare-postdraft-release)")
            for error in errors:
                print(f"- {error}")
            return 2
        print("batch_postdraft_release: prepared")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        _print_status(inspect_postdraft_release_status(**kwargs))
        return 0
    if args.command == "next-step":
        print(json.dumps(suggest_next_step(**kwargs), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run-postdraft-release-cycle":
        result = run_postdraft_release_cycle(**kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result.get("errors") else 2
    print(emit_shell_template(project=args.project, project_dir=Path(args.project_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
