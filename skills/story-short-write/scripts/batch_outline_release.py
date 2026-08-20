#!/usr/bin/env python3
"""Initialize or resume the single outline-layer writing contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _load_module(filename: str, alias: str):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OUTLINE = _load_module(
    "validate_outline_migration_contract.py",
    "story_short_write_outline_migration_contract",
)


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


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _configured_source_originals(config: dict[str, Any]) -> list[Path]:
    primary = config.get("primary")
    if not isinstance(primary, dict):
        raise ValueError("项目写作配置缺少 primary")
    primary_path = str(primary.get("original_path") or "").strip()
    if not primary_path:
        raise ValueError("项目写作配置 primary.original_path 不能为空")

    originals = [Path(primary_path).expanduser().resolve()]
    auxiliaries = config.get("auxiliaries", [])
    if not isinstance(auxiliaries, list):
        raise ValueError("项目写作配置 auxiliaries 必须是列表")
    for index, auxiliary in enumerate(auxiliaries, start=1):
        if not isinstance(auxiliary, dict):
            raise ValueError(f"项目写作配置 auxiliaries[{index - 1}] 必须是对象")
        selected_bids = auxiliary.get("selected_bids", [])
        if not isinstance(selected_bids, list) or not selected_bids:
            continue
        original_path = str(auxiliary.get("original_path") or "").strip()
        if not original_path:
            profile_path = str(auxiliary.get("profile_path") or "").strip()
            name = str(auxiliary.get("name") or "").strip()
            if profile_path and name:
                original_path = str(
                    Path(profile_path).expanduser().resolve().parent
                    / "原文"
                    / f"{name}.txt"
                )
        if not original_path:
            raise ValueError(
                f"项目写作配置辅助来源[{index}]已选择桥段但无法定位 original_path"
            )
        originals.append(Path(original_path).expanduser().resolve())
    return originals


def resolve_inputs(
    *,
    project: str,
    project_dir: Path,
    project_config: Path | None = None,
    source_originals: list[Path] | None = None,
) -> dict[str, Any]:
    resolved_project_dir = project_dir.expanduser().resolve()
    resolved_config = (
        project_config.expanduser().resolve()
        if project_config is not None
        else (resolved_project_dir / "写作资产" / "项目写作配置.json").resolve()
    )
    config = load_json(resolved_config, "项目写作配置")
    configured_project = str(config.get("project_name") or "").strip()
    if configured_project != project:
        raise ValueError(
            f"项目写作配置 project_name 与 --project 不一致: {configured_project!r} != {project!r}"
        )
    if resolved_project_dir.name != project:
        raise ValueError("project-dir basename 必须与 project 一致")

    originals = (
        [path.expanduser().resolve() for path in source_originals]
        if source_originals
        else _configured_source_originals(config)
    )
    missing = [str(path) for path in originals if not path.is_file()]
    if missing:
        raise FileNotFoundError("来源原文不存在: " + " / ".join(missing))

    setting = (resolved_project_dir / "设定.md").resolve()
    outline = (resolved_project_dir / "小节大纲.md").resolve()
    for path, label in ((setting, "设定"), (outline, "小节大纲")):
        if not path.is_file():
            raise FileNotFoundError(f"{label}不存在: {path}")

    return {
        "project_dir": resolved_project_dir,
        "project_config": resolved_config,
        "setting": setting,
        "outline": outline,
        "outline_receipt": (
            resolved_project_dir / "写作资产" / "细纲表演验收回执.json"
        ).resolve(),
        "source_originals": originals,
    }


def start_outline_release(
    *,
    project: str,
    project_dir: Path,
    project_config: Path | None = None,
    source_originals: list[Path] | None = None,
    force: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    try:
        paths = resolve_inputs(
            project=project,
            project_dir=project_dir,
            project_config=project_config,
            source_originals=source_originals,
        )
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)], {"outline_ready": False}

    receipt = paths["outline_receipt"]
    if receipt.is_file() and not force:
        try:
            existing = load_json(receipt, "细纲合同")
        except ValueError as exc:
            return [str(exc)], {"outline_ready": False}
        if existing.get("schema_version") == OUTLINE.SCHEMA_VERSION:
            return [], {
                "outline_receipt": str(receipt),
                "outline_ready": True,
                "resumed_existing": True,
            }
        if existing.get("schema_version") in {
            OUTLINE.PREVIOUS_SCHEMA_VERSION,
            *OUTLINE.LEGACY_SCHEMA_VERSIONS,
        }:
            try:
                OUTLINE.rebind_outline(
                    receipt,
                    paths["outline"],
                    preserve_by_evidence=True,
                )
            except (FileNotFoundError, ValueError) as exc:
                return [f"旧纲层合同升级失败: {exc}"], {"outline_ready": False}
            return [], {
                "outline_receipt": str(receipt),
                "outline_ready": True,
                "resumed_existing": True,
                "upgraded_contract": True,
                "requires_sf_performance_binding": True,
            }
        return ["现有细纲回执不是当前合同；请移出该文件后重新初始化"], {
            "outline_ready": False
        }
    try:
        payload = OUTLINE.create_receipt(
            project,
            paths["outline"],
            paths["project_config"],
        )
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)], {"outline_ready": False}
    write_json(receipt, payload)
    return [], {
        "outline_receipt": str(receipt),
        "outline_ready": True,
        "resumed_existing": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize or resume the sole outline-layer contract."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--project-config")
    parser.add_argument("--source-original", action="append")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    errors, summary = start_outline_release(
        project=args.project,
        project_dir=Path(args.project_dir).resolve(),
        project_config=(
            Path(args.project_config).resolve() if args.project_config else None
        ),
        source_originals=(
            [Path(value).resolve() for value in args.source_original]
            if args.source_original
            else None
        ),
        force=bool(args.force),
    )
    if errors:
        print("batch_outline_release: blocked")
        for item in errors:
            print(f"- {item}")
        return 2
    print("batch_outline_release: ready")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
