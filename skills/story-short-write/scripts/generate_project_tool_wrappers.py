#!/usr/bin/env python3
"""Generate project-local Python wrappers for story-short-write gates.

Project-local wrappers are convenience launchers only:

- They keep long gate arguments out of ad hoc shell history.
- They are fully regenerable from current project receipts/artifacts.
- They intentionally use Python, not shell, to avoid line-ending and quoting drift.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_ROOT = SCRIPT_DIR.parent / "templates" / "project_scripts"
TEMPLATE_MANIFEST = TEMPLATE_ROOT / "manifest.json"
_REGISTRY_PATH = SCRIPT_DIR / "project_tool_wrapper_registry.py"
_REGISTRY_SPEC = importlib.util.spec_from_file_location(
    "story_short_write_project_tool_wrapper_registry", _REGISTRY_PATH
)
assert _REGISTRY_SPEC and _REGISTRY_SPEC.loader
_REGISTRY_MODULE = importlib.util.module_from_spec(_REGISTRY_SPEC)
_REGISTRY_SPEC.loader.exec_module(_REGISTRY_MODULE)


def project_paths(project: Path) -> dict[str, Path]:
    asset = project / "写作资产"
    return {
        "project": project,
        "asset": asset,
        "profile": project / "profiles" / f"{project.name}.project.profile.json",
        "draft": project / "正文.md",
        "writing_receipt": asset / "写作规则读取回执.json",
        "source_receipt": asset / "拆文读取回执.json",
        "ledger": asset / "规则执行台账.json",
        "sequence_receipt": asset / "顺序契约回执.json",
        "opening_contract": asset / "开头承重契约回执_大纲.json",
        "outline_contract": asset / "细纲表演验收回执.json",
        "draft_capacity_contract": asset / "首写容量契约回执.json",
        "section_source_bundle": asset / "逐节原文颗粒包.json",
        "first_draft_entry": asset / "首稿入口回执.json",
        "first_draft_basic_review": asset / "首稿基础审计回执.json",
        "section_execution_receipt": asset / "逐节首写执行回执.json",
        "completion_state": asset / "短篇全流程状态.json",
        "refresh_bindings_wrapper": asset / "修复旧项目绑定.py",
        "draft_release_wrapper": asset / "运行正文放行.py",
        "first_draft_init_wrapper": asset / "初始化首稿入口.py",
        "first_draft_validate_wrapper": asset / "校验首稿入口.py",
        "project_toolbox_wrapper": asset / "项目工具箱.py",
        "project_audit_wrapper": asset / "项目总诊断.py",
        "legacy_draft_release_wrapper": asset / "运行正文放行.sh",
    }


def project_template_dir(project: Path) -> Path:
    return TEMPLATE_ROOT / project.name


def read_template_manifest() -> dict[str, object]:
    if not TEMPLATE_MANIFEST.is_file():
        return {"default_scripts": [], "projects": []}
    data = json.loads(TEMPLATE_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project script manifest 根节点必须是对象")
    default_scripts = data.get("default_scripts")
    if default_scripts is None:
        data["default_scripts"] = []
    elif not isinstance(default_scripts, list):
        raise ValueError("project script manifest.default_scripts 必须是数组")
    projects = data.get("projects")
    if not isinstance(projects, list):
        raise ValueError("project script manifest.projects 必须是数组")
    return data


def normalize_script_specs(
    scripts: list[object],
    kind_filter: str | None = None,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for script in scripts:
        if not isinstance(script, dict):
            continue
        file = str(script.get("file") or "").strip()
        kind = str(script.get("kind") or "").strip()
        purpose = str(script.get("purpose") or "").strip()
        entrypoint = str(script.get("entrypoint") or "").strip()
        if not file:
            continue
        if kind_filter and kind != kind_filter:
            continue
        normalized.append(
            {
                "file": file,
                "kind": kind,
                "purpose": purpose,
                "entrypoint": entrypoint,
            }
        )
    return normalized


def scripts_for_project(
    project_name: str,
    kind_filter: str | None = None,
) -> list[dict[str, str]]:
    data = read_template_manifest()
    default_scripts = normalize_script_specs(
        list(data.get("default_scripts") or []),
        kind_filter=kind_filter,
    )
    project_scripts: list[dict[str, str]] = []
    for item in data.get("projects", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("project_name") or "") != project_name:
            continue
        scripts = item.get("scripts")
        if not isinstance(scripts, list):
            break
        project_scripts = normalize_script_specs(scripts, kind_filter=kind_filter)
        break
    merged: list[dict[str, str]] = []
    seen_files: set[str] = set()
    for script in default_scripts + project_scripts:
        file = script["file"]
        if file in seen_files:
            continue
        merged.append(script)
        seen_files.add(file)
    return merged


def ensure_exists(paths: dict[str, Path], required_keys: list[str]) -> list[str]:
    errors: list[str] = []
    for key in required_keys:
        path = paths[key]
        if not path.exists():
            errors.append(f"缺少 {key}: {path}")
    return errors


def required_keys_for_purpose(purpose: str) -> list[str]:
    requirements = {
        "refresh_legacy_bindings": [],
        "draft_release_gate": [
            "writing_receipt",
            "source_receipt",
            "ledger",
            "sequence_receipt",
            "opening_contract",
            "outline_contract",
            "draft_capacity_contract",
            "section_source_bundle",
            "profile",
        ],
        "first_draft_entry_init": [
            "writing_receipt",
            "source_receipt",
            "ledger",
            "sequence_receipt",
            "opening_contract",
            "outline_contract",
            "draft_capacity_contract",
            "section_source_bundle",
            "profile",
        ],
        "first_draft_entry_validate": [
            "first_draft_entry",
            "draft",
        ],
        "first_draft_basic_review_init": [],
        "first_draft_basic_review_validate": [
            "first_draft_basic_review",
            "draft",
        ],
        "completion_state_init": [],
        "completion_state_validate": [
            "completion_state",
        ],
        "draft_preview_mark": [
            "completion_state",
        ],
        "deep_review_confirm": [
            "completion_state",
        ],
        "local_stiffness_audit": [
            "draft",
        ],
        "project_toolbox": [],
        "project_audit": [],
    }
    return requirements.get(purpose, [])


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_template_if_present(template_dir: Path, filename: str, target: Path) -> bool:
    source = template_dir / filename
    if not source.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def generate_wrappers(
    project: Path,
    use_git_ledger_fallback: bool,
    remove_legacy_sh: bool,
    include_kinds: set[str] | None = None,
) -> dict[str, object]:
    paths = project_paths(project.resolve())
    template_dir = project_template_dir(paths["project"])
    script_specs = scripts_for_project(paths["project"].name)
    generated: list[str] = []
    errors: list[str] = []
    for spec in script_specs:
        kind = spec["kind"]
        if include_kinds is not None and kind not in include_kinds:
            continue
        filename = spec["file"]
        target = paths["asset"] / filename
        if kind == "python_wrapper":
            missing = ensure_exists(paths, required_keys_for_purpose(spec["purpose"]))
            if missing:
                errors.extend(f"{filename}: {item}" for item in missing)
                continue
            builder = _REGISTRY_MODULE.PYTHON_WRAPPER_BUILDERS.get(spec["purpose"])
            if builder is None:
                return {"ok": False, "errors": [f"未知 python wrapper purpose: {spec['purpose']} ({filename})"]}
            content = builder(
                script_dir=SCRIPT_DIR,
                paths=paths,
                use_git_ledger_fallback=use_git_ledger_fallback,
            )
            write_text(target, content)
            generated.append(str(target))
            continue
        if kind == "project_template":
            if write_template_if_present(template_dir, filename, target):
                generated.append(str(target))
            continue
        return {"ok": False, "errors": [f"未知 script kind: {kind} ({filename})"]}

    if errors and not generated:
        return {"ok": False, "errors": errors}

    removed: list[str] = []
    if remove_legacy_sh and paths["legacy_draft_release_wrapper"].exists():
        paths["legacy_draft_release_wrapper"].unlink()
        removed.append(str(paths["legacy_draft_release_wrapper"]))

    return {
        "ok": True,
        "generated": generated,
        "removed": removed,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="项目目录")
    parser.add_argument("--use-git-ledger-fallback", action="store_true")
    parser.add_argument("--remove-legacy-sh", action="store_true")
    parser.add_argument(
        "--include-kind",
        action="append",
        choices=("python_wrapper", "project_template"),
        help="只生成指定类型；可重复传入",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = generate_wrappers(
        Path(args.project),
        use_git_ledger_fallback=args.use_git_ledger_fallback,
        remove_legacy_sh=args.remove_legacy_sh,
        include_kinds=set(args.include_kind) if args.include_kind else None,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get("ok"):
            print("project_tool_wrappers: passed")
            for path in result.get("generated", []):
                print(f"- generated: {path}")
            for path in result.get("removed", []):
                print(f"- removed: {path}")
        else:
            print("project_tool_wrappers: blocked")
            for item in result.get("errors", []):
                print(f"- {item}")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
