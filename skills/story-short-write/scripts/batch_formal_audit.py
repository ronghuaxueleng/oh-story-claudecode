#!/usr/bin/env python3
"""High-level wrapper for formal audit and optional external alignment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
AUDIT_SCRIPT = ROOT / "run_full_ai_audit.py"
ALIGN_SCRIPT = ROOT / "compare_with_external_block_audit.py"


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


def default_paths(
    *,
    project: str,
    project_dir: Path,
    draft: Path | None = None,
    audit_dir: Path | None = None,
    profile: Path | None = None,
    internal_standard: Path | None = None,
    alignment_summary: Path | None = None,
    alignment_csv: Path | None = None,
) -> dict[str, Path | str]:
    resolved_project_dir = project_dir.expanduser().resolve()
    assets = (resolved_project_dir / "写作资产").resolve()
    resolved_draft = (
        draft.expanduser().resolve() if draft is not None else (resolved_project_dir / "正文.md").resolve()
    )
    return {
        "project": project,
        "project_dir": resolved_project_dir,
        "draft": resolved_draft,
        "audit_dir": (
            audit_dir.expanduser().resolve()
            if audit_dir is not None
            else (assets / "正式审计").resolve()
        ),
        "audit_json": (
            (audit_dir.expanduser().resolve() if audit_dir is not None else (assets / "正式审计").resolve())
            / f"{resolved_draft.stem}.full_audit.json"
        ),
        "audit_md": (
            (audit_dir.expanduser().resolve() if audit_dir is not None else (assets / "正式审计").resolve())
            / f"{resolved_draft.stem}.full_audit.md"
        ),
        "revision_plan": (
            (audit_dir.expanduser().resolve() if audit_dir is not None else (assets / "正式审计").resolve())
            / f"{resolved_draft.stem}.revision_plan.md"
        ),
        "profile": (
            profile.expanduser().resolve()
            if profile is not None
            else (resolved_project_dir.parent / "profiles" / f"{project}.project.profile.json").resolve()
        ),
        "internal_standard": (
            internal_standard.expanduser().resolve()
            if internal_standard is not None
            else (assets / "内部审计标准.json").resolve()
        ),
        "alignment_summary": (
            alignment_summary.expanduser().resolve()
            if alignment_summary is not None
            else (assets / "外部分块审计对齐摘要.json").resolve()
        ),
        "alignment_csv": (
            alignment_csv.expanduser().resolve()
            if alignment_csv is not None
            else (assets / "外部分块审计对齐.csv").resolve()
        ),
    }


def _is_fresh(output: Path, reference: Path) -> bool:
    return output.is_file() and reference.is_file() and output.stat().st_mtime >= reference.stat().st_mtime


def inspect_formal_audit_status(
    *,
    project: str,
    project_dir: Path,
    draft: Path | None = None,
    audit_dir: Path | None = None,
    profile: Path | None = None,
    internal_standard: Path | None = None,
    alignment_summary: Path | None = None,
    alignment_csv: Path | None = None,
    with_calibration: bool = False,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        draft=draft,
        audit_dir=audit_dir,
        profile=profile,
        internal_standard=internal_standard,
        alignment_summary=alignment_summary,
        alignment_csv=alignment_csv,
    )
    draft_path = Path(str(paths["draft"]))
    audit_json_path = Path(str(paths["audit_json"]))
    audit_payload: dict[str, Any] | None = None
    audit_errors: list[str] = []
    if audit_json_path.is_file():
        try:
            audit_payload = load_json(audit_json_path, "正式审计 JSON")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            audit_errors.append(str(exc))
    audit_fresh = _is_fresh(audit_json_path, draft_path) if draft_path.is_file() else False
    if audit_payload:
        if str(audit_payload.get("file") or "") != str(draft_path):
            audit_errors.append("正式审计绑定的正文路径与当前项目不一致")
        source = audit_payload.get("source")
        if isinstance(source, dict) and str(source.get("path") or "") and str(source.get("path")) != str(draft_path):
            audit_errors.append("正式审计 source.path 与当前正文不一致")
    summary_fresh = _is_fresh(Path(str(paths["alignment_summary"])), audit_json_path) if audit_json_path.is_file() else False
    standard_fresh = _is_fresh(Path(str(paths["internal_standard"])), Path(str(paths["alignment_summary"]))) if Path(str(paths["alignment_summary"])).is_file() else False
    return {
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "draft": str(draft_path),
        "draft_exists": draft_path.is_file(),
        "audit_dir": str(paths["audit_dir"]),
        "audit_json": {
            "path": str(audit_json_path),
            "exists": audit_json_path.is_file(),
            "fresh": audit_fresh,
            "errors": audit_errors,
        },
        "audit_md_exists": Path(str(paths["audit_md"])).is_file(),
        "revision_plan_exists": Path(str(paths["revision_plan"])).is_file(),
        "profile_exists": Path(str(paths["profile"])).is_file(),
        "internal_standard": {
            "path": str(paths["internal_standard"]),
            "exists": Path(str(paths["internal_standard"])).is_file(),
            "fresh": standard_fresh,
        },
        "alignment_summary": {
            "path": str(paths["alignment_summary"]),
            "exists": Path(str(paths["alignment_summary"])).is_file(),
            "fresh": summary_fresh,
        },
        "alignment_csv_exists": Path(str(paths["alignment_csv"])).is_file(),
        "with_calibration": with_calibration,
    }


def _run_command(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore", check=False)
    return proc.returncode, proc.stdout, proc.stderr


def run_formal_audit(
    *,
    project: str,
    project_dir: Path,
    draft: Path | None = None,
    audit_dir: Path | None = None,
    profile: Path | None = None,
    internal_standard: Path | None = None,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        draft=draft,
        audit_dir=audit_dir,
        profile=profile,
        internal_standard=internal_standard,
    )
    cmd = [sys.executable, str(AUDIT_SCRIPT), str(paths["draft"]), "--output-dir", str(paths["audit_dir"])]
    if Path(str(paths["profile"])).is_file():
        cmd.extend(["--profile", str(paths["profile"])])
    if Path(str(paths["internal_standard"])).is_file():
        cmd.extend(["--internal-standard", str(paths["internal_standard"])])
    code, stdout, stderr = _run_command(cmd)
    if code != 0:
        return [stderr.strip() or stdout.strip() or "run_full_ai_audit.py 执行失败"], {"command": cmd}
    return [], {
        "command": cmd,
        "audit_json": str(paths["audit_json"]),
        "audit_md": str(paths["audit_md"]),
        "revision_plan": str(paths["revision_plan"]),
    }


def run_external_alignment(
    *,
    project: str,
    project_dir: Path,
    draft: Path | None = None,
    audit_dir: Path | None = None,
    internal_standard: Path | None = None,
    alignment_summary: Path | None = None,
    alignment_csv: Path | None = None,
    strict: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        draft=draft,
        audit_dir=audit_dir,
        internal_standard=internal_standard,
        alignment_summary=alignment_summary,
        alignment_csv=alignment_csv,
    )
    cmd = [
        sys.executable,
        str(ALIGN_SCRIPT),
        str(paths["project_dir"]),
        "--audit-dir",
        str(paths["audit_dir"]),
        "--output",
        str(paths["alignment_csv"]),
        "--summary-output",
        str(paths["alignment_summary"]),
        "--internal-standard-output",
        str(paths["internal_standard"]),
    ]
    if strict:
        cmd.append("--strict")
    code, stdout, stderr = _run_command(cmd)
    if code != 0:
        return [stderr.strip() or stdout.strip() or "compare_with_external_block_audit.py 执行失败"], {"command": cmd}
    return [], {
        "command": cmd,
        "alignment_summary": str(paths["alignment_summary"]),
        "internal_standard": str(paths["internal_standard"]),
        "alignment_csv": str(paths["alignment_csv"]),
    }


def suggest_next_step(
    *,
    project: str,
    project_dir: Path,
    draft: Path | None = None,
    audit_dir: Path | None = None,
    profile: Path | None = None,
    internal_standard: Path | None = None,
    alignment_summary: Path | None = None,
    alignment_csv: Path | None = None,
    with_calibration: bool = False,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        draft=draft,
        audit_dir=audit_dir,
        profile=profile,
        internal_standard=internal_standard,
        alignment_summary=alignment_summary,
        alignment_csv=alignment_csv,
    )
    status = inspect_formal_audit_status(
        project=project,
        project_dir=project_dir,
        draft=draft,
        audit_dir=audit_dir,
        profile=profile,
        internal_standard=internal_standard,
        alignment_summary=alignment_summary,
        alignment_csv=alignment_csv,
        with_calibration=with_calibration,
    )
    status_command = (
        'python3 "$SKILL_ROOT/scripts/batch_formal_audit.py" status '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
        + (" --with-calibration" if with_calibration else "")
    )
    run_command = (
        'python3 "$SKILL_ROOT/scripts/batch_formal_audit.py" run-audit-cycle '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
        + (" --with-calibration" if with_calibration else "")
    )
    if not status["draft_exists"]:
        return {"action": "missing_draft", "reason": "正文不存在，无法启动正式审计", "next_command": "", "status_command": status_command}
    if not status["audit_json"]["exists"] or not status["audit_json"]["fresh"] or status["audit_json"]["errors"]:
        return {
            "action": "run_formal_audit",
            "reason": "正式审计产物缺失、过期或绑定异常",
            "next_command": run_command,
            "status_command": status_command,
        }
    if with_calibration and (
        not status["alignment_summary"]["exists"]
        or not status["alignment_summary"]["fresh"]
        or not status["internal_standard"]["exists"]
        or not status["internal_standard"]["fresh"]
    ):
        return {
            "action": "run_external_alignment",
            "reason": "题材首次校准产物缺失或过期",
            "next_command": run_command,
            "status_command": status_command,
        }
    return {
        "action": "formal_audit_ready",
        "reason": "正式审计链产物已齐，可以进入后续深审尾链",
        "next_command": status_command,
        "status_command": status_command,
    }


def run_audit_cycle(
    *,
    project: str,
    project_dir: Path,
    draft: Path | None = None,
    audit_dir: Path | None = None,
    profile: Path | None = None,
    internal_standard: Path | None = None,
    alignment_summary: Path | None = None,
    alignment_csv: Path | None = None,
    with_calibration: bool = False,
    strict_calibration: bool = False,
) -> dict[str, Any]:
    completed_steps: list[str] = []
    for _ in range(3):
        suggestion = suggest_next_step(
            project=project,
            project_dir=project_dir,
            draft=draft,
            audit_dir=audit_dir,
            profile=profile,
            internal_standard=internal_standard,
            alignment_summary=alignment_summary,
            alignment_csv=alignment_csv,
            with_calibration=with_calibration,
        )
        action = suggestion["action"]
        if action in {"missing_draft", "formal_audit_ready"}:
            suggestion["completed_steps"] = completed_steps
            return suggestion
        if action == "run_formal_audit":
            errors, summary = run_formal_audit(
                project=project,
                project_dir=project_dir,
                draft=draft,
                audit_dir=audit_dir,
                profile=profile,
                internal_standard=internal_standard,
            )
            if errors:
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": errors,
                    "summary": summary,
                    "completed_steps": completed_steps,
                    "status_command": suggestion["status_command"],
                }
            completed_steps.append("run_formal_audit")
            continue
        errors, summary = run_external_alignment(
            project=project,
            project_dir=project_dir,
            draft=draft,
            audit_dir=audit_dir,
            internal_standard=internal_standard,
            alignment_summary=alignment_summary,
            alignment_csv=alignment_csv,
            strict=strict_calibration,
        )
        if errors:
            return {
                "action": action,
                "reason": suggestion["reason"],
                "errors": errors,
                "summary": summary,
                "completed_steps": completed_steps,
                "status_command": suggestion["status_command"],
            }
        completed_steps.append("run_external_alignment")
    return {"action": "loop_guard_triggered", "reason": "正式审计链执行次数异常，请改用 status 检查当前状态", "completed_steps": completed_steps}


def emit_shell_template(*, project: str, project_dir: Path, with_calibration: bool = False) -> str:
    resolved_dir = project_dir.expanduser().resolve()
    suffix = " \\\n  --with-calibration" if with_calibration else ""
    return "\n".join(
        [
            'python3 "$SKILL_ROOT/scripts/batch_formal_audit.py" status \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_dir))}{suffix}",
            "",
            'python3 "$SKILL_ROOT/scripts/batch_formal_audit.py" next-step \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_dir))}{suffix}",
            "",
            'python3 "$SKILL_ROOT/scripts/batch_formal_audit.py" run-audit-cycle \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(resolved_dir))}{suffix}",
        ]
    )


def _print_status(status: dict[str, Any]) -> None:
    print("batch_formal_audit: status")
    print(f"project: {status['project']}")
    print(f"project_dir: {status['project_dir']}")
    print(f"draft_exists: {status['draft_exists']}")
    print(f"audit_json_exists: {status['audit_json']['exists']}")
    print(f"audit_json_fresh: {status['audit_json']['fresh']}")
    print(f"alignment_summary_exists: {status['alignment_summary']['exists']}")
    print(f"alignment_summary_fresh: {status['alignment_summary']['fresh']}")
    print(f"internal_standard_exists: {status['internal_standard']['exists']}")
    print(f"internal_standard_fresh: {status['internal_standard']['fresh']}")
    print(f"with_calibration: {status['with_calibration']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "next-step", "run-audit-cycle", "emit-shell-template"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--project-dir", required=True)
        cmd.add_argument("--draft")
        cmd.add_argument("--audit-dir")
        cmd.add_argument("--profile")
        cmd.add_argument("--internal-standard")
        cmd.add_argument("--alignment-summary")
        cmd.add_argument("--alignment-csv")
        cmd.add_argument("--with-calibration", action="store_true")
        cmd.add_argument("--strict-calibration", action="store_true")
    args = parser.parse_args()
    kwargs = {
        "project": args.project,
        "project_dir": Path(args.project_dir),
        "draft": Path(args.draft) if args.draft else None,
        "audit_dir": Path(args.audit_dir) if args.audit_dir else None,
        "profile": Path(args.profile) if args.profile else None,
        "internal_standard": Path(args.internal_standard) if args.internal_standard else None,
        "alignment_summary": Path(args.alignment_summary) if args.alignment_summary else None,
        "alignment_csv": Path(args.alignment_csv) if args.alignment_csv else None,
        "with_calibration": bool(args.with_calibration),
    }
    if args.command == "status":
        _print_status(inspect_formal_audit_status(**kwargs))
        return 0
    if args.command == "next-step":
        print(json.dumps(suggest_next_step(**kwargs), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run-audit-cycle":
        result = run_audit_cycle(**kwargs, strict_calibration=bool(args.strict_calibration))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result.get("errors") else 2
    print(emit_shell_template(project=args.project, project_dir=Path(args.project_dir), with_calibration=bool(args.with_calibration)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
