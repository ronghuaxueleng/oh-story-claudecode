#!/usr/bin/env python3
"""Promote scaffold rebuilder files into formal project-local files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def project_paths(project: Path) -> dict[str, Path]:
    asset = project / "写作资产"
    return {
        "project": project,
        "asset": asset,
        "scaffold_wrapper": asset / "重建细纲与容量回执.scaffold.mjs",
        "scaffold_data": asset / "重建细纲与容量回执.scaffold.data.mjs",
        "formal_wrapper": asset / "重建细纲与容量回执.mjs",
        "formal_data": asset / "重建细纲与容量回执.data.mjs",
    }


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def promote(
    *,
    project: Path,
    force: bool,
    keep_scaffold: bool,
) -> dict[str, object]:
    paths = project_paths(project.resolve())
    errors: list[str] = []

    if not paths["scaffold_wrapper"].is_file():
        errors.append(f"缺少 scaffold 包装脚本: {paths['scaffold_wrapper']}")
    if not paths["scaffold_data"].is_file():
        errors.append(f"缺少 scaffold 数据文件: {paths['scaffold_data']}")
    if errors:
        return {"ok": False, "errors": errors}

    for key in ("formal_wrapper", "formal_data"):
        if paths[key].exists() and not force:
            errors.append(f"目标文件已存在，未开启 --force: {paths[key]}")
    if errors:
        return {"ok": False, "errors": errors}

    wrapper_text = paths["scaffold_wrapper"].read_text(encoding="utf-8")
    data_text = paths["scaffold_data"].read_text(encoding="utf-8")
    wrapper_text = wrapper_text.replace(
        "./重建细纲与容量回执.scaffold.data.mjs",
        "./重建细纲与容量回执.data.mjs",
    )

    if force:
        for key in ("formal_wrapper", "formal_data"):
            if paths[key].exists():
                paths[key].unlink()

    _write(paths["formal_wrapper"], wrapper_text)
    _write(paths["formal_data"], data_text)

    actions = ["write_formal_wrapper", "write_formal_data"]
    if not keep_scaffold:
        paths["scaffold_wrapper"].unlink()
        paths["scaffold_data"].unlink()
        actions.extend(["remove_scaffold_wrapper", "remove_scaffold_data"])

    return {
        "ok": True,
        "project": str(paths["project"]),
        "formal_wrapper": str(paths["formal_wrapper"]),
        "formal_data": str(paths["formal_data"]),
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-scaffold", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = promote(
        project=Path(args.project),
        force=args.force,
        keep_scaffold=args.keep_scaffold,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get("ok"):
            print("promote_outline_rebuilder_scaffold: passed")
            print(f"- formal_wrapper: {result['formal_wrapper']}")
            print(f"- formal_data: {result['formal_data']}")
        else:
            print("promote_outline_rebuilder_scaffold: blocked")
            for item in result.get("errors", []):
                print(f"- {item}")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
