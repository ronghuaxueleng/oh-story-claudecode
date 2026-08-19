#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


PASS_TEXTS = ("[x] `可并入主正文`", "结论：可并入主正文", "- 可并入主正文", "并入裁决：可并入主正文")
FAIL_TEXTS = ("[x] `不可并入主正文`", "[x] `不可继续顺写`", "结论：不可并入主正文", "- 不可并入主正文", "并入裁决：不可并入主正文")
WRITE_AFTER_PAT = re.compile(r"(?:写后验收|写后检查)_第\d+(?:章)?[-－]\d+(?:章)?\.md$")


@dataclass
class Issue:
    path: str
    category: str
    severity: str
    message: str


def make_issue(path: Path, severity: str, message: str) -> Issue:
    return Issue(str(path), "裁决冲突", severity, message)


def extract_verdict(text: str) -> str | None:
    has_marked_pass = any(token in text for token in PASS_TEXTS)
    has_marked_fail = any(token in text for token in FAIL_TEXTS)
    if has_marked_pass and not has_marked_fail:
        return "pass"
    if has_marked_fail and not has_marked_pass:
        return "fail"
    return None


def lint(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    project_root = resolve_story_root(project_root)
    tracking_dir = project_root / "追踪"
    if not tracking_dir.exists():
        return [make_issue(tracking_dir, "error", "缺少追踪目录，无法核对并入口径是否唯一同判")]

    group_files = [p for p in tracking_dir.iterdir() if p.is_file() and WRITE_AFTER_PAT.search(p.name)]
    review_files = [p for p in tracking_dir.iterdir() if p.is_file() and ("总施工单_" in p.name or "固定验收清单_" in p.name)]

    group_verdicts = [(p, extract_verdict(p.read_text(encoding="utf-8"))) for p in group_files]
    review_verdicts = [(p, extract_verdict(p.read_text(encoding="utf-8"))) for p in review_files]

    group_pass = [p.name for p, v in group_verdicts if v == "pass"]
    review_fail = [p.name for p, v in review_verdicts if v == "fail"]
    group_fail = [p.name for p, v in group_verdicts if v == "fail"]
    review_pass = [p.name for p, v in review_verdicts if v == "pass"]

    if group_pass and review_fail:
        issues.append(make_issue(tracking_dir, "error", f"章组写后检查与审查工单并入口径冲突：写后检查={group_pass}，审查工单={review_fail}"))
    if group_fail and review_pass:
        issues.append(make_issue(tracking_dir, "error", f"章组写后检查与审查工单并入口径冲突：写后检查={group_fail}，审查工单={review_pass}"))
    return issues


def resolve_story_root(path: Path) -> Path:
    path = path.resolve()
    if (path / "正文").exists() and (path / "设定").exists():
        return path
    candidates = [
        child for child in path.iterdir()
        if child.is_dir() and (child / "正文").exists() and (child / "设定").exists()
    ] if path.exists() else []
    if len(candidates) == 1:
        return candidates[0]
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check verdict conflicts between postchecks and review work orders.")
    parser.add_argument("project_root")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    issues = lint(project_root)
    payload = {
        "ok": not any(issue.severity == "error" for issue in issues),
        "summary": {
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warn"),
            "total": len(issues),
        },
        "issues": [asdict(issue) for issue in issues],
        "project_root": str(project_root),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
