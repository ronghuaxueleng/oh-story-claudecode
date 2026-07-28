#!/usr/bin/env python3
"""Run a reusable cold-start smoke test for story-short-write."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BOOTSTRAP = SCRIPT_DIR / "bootstrap_short_project.py"
TOOLBOX = SCRIPT_DIR / "story_short_write_project_toolbox.py"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def parse_json_output(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    text = (proc.stdout or "").strip()
    if not text:
        return {}
    return json.loads(text)


def build_bootstrap_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(BOOTSTRAP),
        "--workspace",
        str(Path(args.workspace).resolve()),
        "--project-name",
        args.project_name,
        "--primary-source",
        args.primary_source,
    ]
    if args.platform:
        cmd.extend(["--platform", args.platform])
    if args.imitation_mode:
        cmd.append("--imitation-mode")
    if args.use_git_ledger_fallback:
        cmd.append("--use-git-ledger-fallback")
    for item in args.aux_source:
        cmd.extend(["--aux-source", item])
    return cmd


def build_toolbox_cmd(project: Path, command: str, extra: list[str] | None = None) -> list[str]:
    cmd = [
        sys.executable,
        str(TOOLBOX),
        "--project",
        str(project),
        "--json",
        command,
    ]
    if extra:
        cmd.extend(extra)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--primary-source", required=True)
    parser.add_argument("--aux-source", action="append", default=[])
    parser.add_argument("--platform", default="知乎盐言")
    parser.add_argument("--imitation-mode", action="store_true", default=True)
    parser.add_argument("--use-git-ledger-fallback", action="store_true")
    parser.add_argument("--output", help="写入 JSON 报告")
    args = parser.parse_args()

    project = Path(args.workspace).resolve() / args.project_name
    bootstrap_proc = run(build_bootstrap_cmd(args))
    wrappers_proc = run(build_toolbox_cmd(project, "generate-wrappers", ["--remove-legacy-sh"]))
    audit_proc = run(build_toolbox_cmd(project, "audit-project"))

    wrappers = parse_json_output(wrappers_proc)
    audit = parse_json_output(audit_proc)

    generated_files = sorted(
        str(path.relative_to(project))
        for path in project.rglob("*")
        if path.is_file()
    ) if project.is_dir() else []

    report = {
        "project": str(project),
        "bootstrap": {
            "returncode": bootstrap_proc.returncode,
            "stdout": (bootstrap_proc.stdout or "").strip(),
            "stderr": (bootstrap_proc.stderr or "").strip(),
            "ok": bootstrap_proc.returncode == 0,
        },
        "generate_wrappers": {
            "returncode": wrappers_proc.returncode,
            "stdout": (wrappers_proc.stdout or "").strip(),
            "stderr": (wrappers_proc.stderr or "").strip(),
            "result": wrappers,
            "ok": wrappers_proc.returncode == 0 and bool(wrappers.get("ok")),
        },
        "audit_project": {
            "returncode": audit_proc.returncode,
            "stdout": (audit_proc.stdout or "").strip(),
            "stderr": (audit_proc.stderr or "").strip(),
            "result": audit,
            "ok": audit_proc.returncode == 0 and bool(audit.get("ok")),
            "expected_to_block_before_receipts": True,
        },
        "generated_files": generated_files,
    }

    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["bootstrap"]["ok"] and report["generate_wrappers"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
