#!/usr/bin/env python3
"""plot-extractor 统一入口。"""
import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def _run(script_name: str, forwarded_args: list[str]) -> int:
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path), *forwarded_args]
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="plot-extractor 通用入口：提取、补救、检索、检查、导入、导出情节包"
    )
    parser.add_argument("command", nargs="?", choices=["extract", "retry", "search", "search-for-outline", "search-interlude", "search-micro-task", "inspect", "list", "export", "import", "export-collection"], help="要执行的子命令")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="透传给具体子脚本的参数")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command
    forwarded_args = list(args.args)
    if forwarded_args and forwarded_args[0] == "--":
        forwarded_args = forwarded_args[1:]

    if command == "extract":
        return _run("extract_plot_bundle.py", forwarded_args)
    if command == "retry":
        return _run("retry_plot_bundle.py", forwarded_args)
    if command == "search":
        return _run("search_plot_library.py", forwarded_args)
    if command == "search-for-outline":
        return _run("search_for_outline.py", forwarded_args)
    if command == "search-interlude":
        return _run("search_interlude_plot.py", forwarded_args)
    if command == "search-micro-task":
        return _run("search_micro_task.py", forwarded_args)
    if command in {"inspect", "list"}:
        return _run("inspect_plot_bundle.py", [command, *forwarded_args])
    if command == "export":
        return _run("export_plot_bundle.py", forwarded_args)
    if command == "import":
        return _run("import_json_library.py", forwarded_args)
    if command == "export-collection":
        return _run("export_plot_collection.py", forwarded_args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
