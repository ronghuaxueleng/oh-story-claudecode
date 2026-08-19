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

GENERIC_DELAYED_EMOTION_PATTERNS = (
    re.compile(
        r"(?:以后|之后|离开后|失去后|死后)[，,]?(?:他|她)才(?:说|承认|知道|发现|明白|开始).{0,8}(?:爱|后悔|珍惜|在乎)"
    ),
    re.compile(r"(?:他|她)失去我后[，,]?(?:才|终于).{0,8}(?:爱|后悔|珍惜|在乎)"),
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
    if any(pattern.search(expected) for pattern in GENERIC_DELAYED_EMOTION_PATTERNS):
        errors.append(
            "正式书名仍是泛化迟到情绪模板；必须改成具体载体、关系矛盾和未解释异常"
        )
    return errors


def create_new(project_dir: Path, title: str) -> list[str]:
    errors = validate(project_dir, title, new_project=True)
    if errors:
        return errors
    try:
        project_dir.mkdir()
    except FileExistsError:
        return [f"全新开书目录已被占用，不得复用: {project_dir}"]
    except OSError as exc:
        return [f"无法创建写作项目目录: {exc}"]
    errors = validate(project_dir, title)
    if errors:
        try:
            project_dir.rmdir()
        except OSError:
            pass
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
    parser.add_argument(
        "--create-new",
        action="store_true",
        help="校验、原子创建并复验全新项目目录",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    if args.new_project and args.create_new:
        parser.error("--new-project 与 --create-new 不能同时使用")
    errors = (
        create_new(project_dir, args.title)
        if args.create_new
        else validate(project_dir, args.title, new_project=args.new_project)
    )
    if errors:
        print("project_directory_name: blocked")
        for error in errors:
            print(f"- {error}")
        return 1
    print("project_directory_name: passed")
    print(f"project_dir: {project_dir}")
    print(f"title: {normalize_title(args.title)}")
    mode = (
        "new_project_created"
        if args.create_new
        else "new_project_preflight"
        if args.new_project
        else "existing_project_validation"
    )
    print(f"mode: {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
