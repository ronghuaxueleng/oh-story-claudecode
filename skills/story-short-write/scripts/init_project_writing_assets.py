#!/usr/bin/env python3
"""Initialize empty project-owned writing assets without semantic auto-filling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS = SKILL_ROOT / "assets"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"目标已存在，拒绝覆盖: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize project writing assets.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--project-name", required=True)
    args = parser.parse_args()
    project = Path(args.project_dir).resolve()
    if project.name != args.project_name:
        print("project_writing_assets: blocked")
        print("- project-dir basename 必须与 project-name 一致")
        return 2
    config = load(ASSETS / "project-writing-config.template.json")
    config["project_name"] = args.project_name
    config["profile_path"] = f"../profiles/{args.project_name}.project.profile.json"
    beat_mapping = load(ASSETS / "semantic-beat-mapping.template.json")
    scene_mapping = load(ASSETS / "semantic-scene-mapping.template.json")
    targets = (
        project / "写作资产/项目写作配置.json",
        project / "写作资产/逐拍语义映射.json",
        project / "写作资产/逐场语义映射.json",
    )
    occupied = [str(path) for path in targets if path.exists()]
    if occupied:
        print("project_writing_assets: blocked")
        print("- 以下目标已存在，拒绝部分初始化: " + " / ".join(occupied))
        return 2
    try:
        write_new(targets[0], config)
        write_new(targets[1], beat_mapping)
        write_new(targets[2], scene_mapping)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("project_writing_assets: blocked")
        print(f"- {exc}")
        return 2
    print("project_writing_assets: initialized")
    print("status: pending_manual_semantic_review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
