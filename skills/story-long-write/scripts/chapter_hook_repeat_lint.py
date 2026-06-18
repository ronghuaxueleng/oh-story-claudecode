#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


HOOK_PATTERNS = {
    "人物到场": ("到了", "压进", "进场", "现身"),
    "新证据出现": ("旧印", "新证据", "木牌", "封蜡", "账簿", "半枚"),
    "新命令落地": ("先按", "记上", "开簿", "封给", "先烧", "改记"),
    "战略宣言": ("我想要的", "整条", "接下来", "从这一刻起", "以后"),
    "等待下一步": ("明天", "下一步", "后头", "之后再说"),
}


@dataclass
class Issue:
    path: str
    category: str
    severity: str
    message: str


def make_issue(path: Path, category: str, severity: str, message: str) -> Issue:
    return Issue(str(path), category, severity, message)


def chapter_no(path: Path) -> int:
    match = re.search(r"第(\d+)章", path.name)
    return int(match.group(1)) if match else 0


def find_project_root(path: Path) -> Path:
    if path.is_file():
        path = path.parent
    for parent in (path, *path.parents):
        if (parent / "正文").exists():
            return parent
    return path


def chapter_files(project_root: Path) -> list[Path]:
    body_dir = project_root / "正文"
    return sorted([item for item in body_dir.glob("*.md") if chapter_no(item) > 0], key=chapter_no)


def tail_lines(path: Path, n: int = 12) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-n:])


def classify_hook(text: str) -> str:
    for hook_type, patterns in HOOK_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return hook_type
    return "现场结果"


def lint_project(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    chapters = chapter_files(project_root)
    previous_type: str | None = None
    previous_path: Path | None = None
    for chapter in chapters:
        current_tail = tail_lines(chapter)
        current_type = classify_hook(current_tail)
        if current_type == "战略宣言":
            issues.append(make_issue(chapter, "章尾", "error", "章尾落在战略宣言/长线目标，而非现场新结果"))
        if previous_type and current_type == previous_type and current_type in {"人物到场", "等待下一步", "战略宣言"}:
            issues.append(make_issue(chapter, "章尾", "error", f"与上一章章尾钩子撞型：{current_type}（上一章：{previous_path.name}）"))
        previous_type = current_type
        previous_path = chapter
    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint repeated adjacent chapter ending hook types.")
    parser.add_argument("path", help="project root or chapter file inside project")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    project_root = find_project_root(Path(args.path))
    issues = lint_project(project_root)
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
    sys.exit(main(sys.argv[1:]))
