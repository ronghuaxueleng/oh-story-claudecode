#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SCRIPT_NAMES = (
    "scene_lint.py",
    "scene_narrowness_lint.py",
    "validate_tracking_state.py",
    "chapter_hook_repeat_lint.py",
    "detect_key_character_promotion.py",
    "character_agency_lint.py",
    "template_exhaustion_lint.py",
    "draft_purity_guard.py",
    "verdict_conflict_lint.py",
)


@dataclass
class Issue:
    path: str
    category: str
    severity: str
    message: str


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_issue(path: Path, severity: str, message: str) -> Issue:
    return Issue(str(path), "脚本版本", severity, message)


def lint(project_root: Path, skill_script_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    story_root = resolve_story_root(project_root)
    project_script_dir = resolve_project_script_dir(project_root, story_root)
    if not project_script_dir.exists():
        issues.append(make_issue(project_script_dir, "error", "项目缺少 scripts 目录，无法保证写作链脚本版本一致"))
        return issues

    for name in SCRIPT_NAMES:
        skill_path = skill_script_dir / name
        project_path = project_script_dir / name
        if not skill_path.exists():
            continue
        if not project_path.exists():
            issues.append(make_issue(project_path, "error", f"项目缺少脚本 `{name}`，应从 skill 同步最新版"))
            continue
        if sha256(skill_path) != sha256(project_path):
            issues.append(make_issue(project_path, "error", f"项目脚本 `{name}` 与 skill 版本不一致，需先同步后再做写后检查/复审"))
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


def resolve_project_script_dir(project_root: Path, story_root: Path) -> Path:
    project_root = project_root.resolve()
    story_root = story_root.resolve()
    story_parent = story_root.parent
    candidates = [
        project_root / "scripts",
        story_root / "scripts",
        story_parent / "scripts",
        project_root.parent / "scripts",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if project_root == story_root:
        return story_parent / "scripts"
    return project_root / "scripts"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check project scripts are in sync with skill scripts.")
    parser.add_argument("project_root")
    parser.add_argument("--skill-script-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    skill_script_dir = Path(args.skill_script_dir).resolve()
    issues = lint(project_root, skill_script_dir)
    payload = {
        "ok": not any(issue.severity == "error" for issue in issues),
        "summary": {
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warn"),
            "total": len(issues),
        },
        "issues": [asdict(issue) for issue in issues],
        "project_root": str(project_root),
        "skill_script_dir": str(skill_script_dir),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
