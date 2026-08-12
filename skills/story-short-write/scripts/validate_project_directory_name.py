#!/usr/bin/env python3
"""Validate that a short-story project directory uses the final book title."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


WORKING_NAME_PATTERNS = (
    re.compile(r"^新书(?:[-_]|$)"),
    re.compile(r"(?:^|[-_])\d{8}(?:$|[-_])"),
    re.compile(r"(?:主骨架|参考骨架|暂定名|工作名|任务代号)"),
)


def normalize_title(value: str) -> str:
    title = value.strip()
    if title.startswith("《") and title.endswith("》") and len(title) > 2:
        title = title[1:-1].strip()
    return title


def validate(project_dir: Path, title: str, *, new_project: bool = False) -> list[str]:
    errors: list[str] = []
    expected = normalize_title(title)
    actual = project_dir.name

    if not expected:
        errors.append("正式书名不能为空")
        return errors
    if new_project and project_dir.exists():
        errors.append(f"全新开书目录已被占用，不得复用: {project_dir}")
    elif not new_project and not project_dir.is_dir():
        errors.append(f"写作项目目录不存在: {project_dir}")
    if actual != expected:
        errors.append(f"项目目录名必须与正式书名一致: expected={expected!r}, actual={actual!r}")
    if any(pattern.search(actual) for pattern in WORKING_NAME_PATTERNS):
        errors.append("项目目录仍像内部工作代号、骨架名或日期目录")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--new-project",
        action="store_true",
        help="创建前检查：目标路径必须完全不存在",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    errors = validate(project_dir, args.title, new_project=args.new_project)
    if errors:
        print("project_directory_name: blocked")
        for error in errors:
            print(f"- {error}")
        return 1
    print("project_directory_name: passed")
    print(f"project_dir: {project_dir}")
    print(f"title: {normalize_title(args.title)}")
    print(f"mode: {'new_project_preflight' if args.new_project else 'existing_project_validation'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
