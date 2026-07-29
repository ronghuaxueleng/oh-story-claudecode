#!/usr/bin/env python3
"""Bootstrap a new story-short-write project skeleton."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def load_wrapper_module():
    path = SCRIPT_DIR / "generate_project_tool_wrappers.py"
    spec = importlib.util.spec_from_file_location("story_short_write_bootstrap_wrappers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 wrapper 生成器: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cold_start_module():
    path = SCRIPT_DIR / "initialize_cold_start_from_source_profiles.py"
    spec = importlib.util.spec_from_file_location("story_short_write_bootstrap_cold_start", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载冷启动初始化器: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_state(project_dir: Path, imitation_mode: bool) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "version": "1.1",
        "workflow": "story-short-write",
        "project_path": str(project_dir.resolve()),
        "status": "initialized",
        "imitation_mode": imitation_mode,
        "started_at": now,
        "preview_ready_at": "",
        "deep_review_user_confirmed": False,
        "deep_review_confirmed_at": "",
        "deep_review_confirmation_note": "",
        "checks": [],
        "next_action": "补齐设定、大纲、正文与各阶段回执后再进入门禁校验。",
        "pause_reason": "",
        "blocker": {},
        "updated_at": now,
    }


def build_profile(
    project_name: str,
    platform: str,
    primary_source: str,
    auxiliary_sources: list[str],
) -> dict:
    return {
        "meta": {
            "name": project_name,
            "mode": "manual_bootstrap",
            "source_count": 1 + len(auxiliary_sources),
            "sources": [primary_source, *auxiliary_sources],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "platform": platform,
        "primary_source": primary_source,
        "auxiliary_sources": auxiliary_sources,
        "notes": [
            "该 profile 由 bootstrap_short_project.py 初始化。",
            "后续需按实际设定、大纲和正文回填完整项目级 profile 规则。"
        ],
    }


def validate_source_stack(primary_source: str, auxiliary_sources: list[str], *, imitation_mode: bool) -> None:
    if not imitation_mode:
        return
    total_sources = 1 + len(auxiliary_sources)
    if total_sources < 4:
        raise RuntimeError(
            "直接仿写 bootstrap 来源厚度不足："
            f"当前 1 主 + {len(auxiliary_sources)} 辅，共 {total_sources} 个来源；"
            "至少需要 1 主 + 3 辅。否则项目会在正文前因为资料厚度不足被硬闸拦下。"
        )
    unique_sources = {primary_source, *auxiliary_sources}
    if len(unique_sources) != total_sources:
        raise RuntimeError("bootstrap 来源列表存在重复项，必须先去重再建项目。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="项目根目录")
    parser.add_argument("--project-name", required=True, help="新书项目名")
    parser.add_argument("--platform", default="知乎盐言")
    parser.add_argument("--primary-source", required=True, help="主体 book.profile.json 或来源标识")
    parser.add_argument("--aux-source", action="append", default=[], help="辅助来源，可重复传入")
    parser.add_argument("--imitation-mode", action="store_true")
    parser.add_argument("--skip-wrapper-generation", action="store_true", help="仅初始化目录，不生成项目本地工具脚本")
    parser.add_argument("--skip-source-cold-start", action="store_true", help="即使 primary/aux source 是本地拆书 profile，也不自动初始化颗粒度冷启动链")
    parser.add_argument("--use-git-ledger-fallback", action="store_true")
    args = parser.parse_args()

    validate_source_stack(
        args.primary_source,
        args.aux_source,
        imitation_mode=args.imitation_mode,
    )

    workspace = Path(args.workspace).resolve()
    project_dir = workspace / args.project_name
    asset_dir = project_dir / "写作资产"
    profile_dir = project_dir / "profiles"

    project_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    write_text(project_dir / "设定.md", "")
    write_text(project_dir / "小节大纲.md", "")
    write_text(project_dir / "正文.md", "")
    write_json(asset_dir / "短篇全流程状态.json", build_state(project_dir, args.imitation_mode))
    write_json(
        profile_dir / f"{args.project_name}.project.profile.json",
        build_profile(
            args.project_name,
            args.platform,
            args.primary_source,
            args.aux_source,
        ),
    )

    if not args.skip_wrapper_generation:
        wrapper_module = load_wrapper_module()
        result = wrapper_module.generate_wrappers(
            project_dir,
            use_git_ledger_fallback=args.use_git_ledger_fallback,
            remove_legacy_sh=True,
            include_kinds=None,
        )
        if not result.get("ok"):
            print("bootstrap_short_project: wrappers_blocked")
            for item in result.get("errors", []):
                print(f"- {item}")
            return 2

    cold_start_result = None
    source_profile_path = Path(args.primary_source).expanduser()
    aux_profile_paths = [Path(raw).expanduser() for raw in args.aux_source]
    if (
        args.imitation_mode
        and not args.skip_source_cold_start
        and source_profile_path.is_file()
        and source_profile_path.name == "book.profile.json"
    ):
        cold_start_module = load_cold_start_module()
        cold_start_result = cold_start_module.initialize(
            project=project_dir,
            primary_source_profile=source_profile_path,
            auxiliary_source_profiles=[
                path for path in aux_profile_paths if path.is_file() and path.name == "book.profile.json"
            ],
            target_words=10000,
            force=False,
        )

    print("bootstrap_short_project: passed")
    print(f"project: {project_dir}")
    if not args.skip_wrapper_generation:
        print("generated_wrappers:")
        for item in result.get("generated", []):
            print(f"- {item}")
    if cold_start_result:
        print("initialized_cold_start:")
        for key, value in cold_start_result.get("actions", {}).items():
            print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
