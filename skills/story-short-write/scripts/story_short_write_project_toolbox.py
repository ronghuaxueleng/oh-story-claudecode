#!/usr/bin/env python3
"""Project-local convenience CLI for story-short-write.

Purpose:
- infer common project paths automatically
- avoid repeated `--help` probing for long gate commands
- centralize high-frequency prewrite / first-draft operations
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(filename: str, module_name: str) -> Any:
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFRESH = load_module("refresh_legacy_project_bindings.py", "story_short_write_refresh_toolbox")
WRITE_RELEASE = load_module("validate_write_release_gate.py", "story_short_write_release_toolbox")
OUTLINE = load_module("validate_outline_performance_contract.py", "story_short_write_outline_toolbox")
OPENING = load_module("validate_opening_contract.py", "story_short_write_opening_toolbox")
SEQUENCE = load_module("validate_sequence_contract.py", "story_short_write_sequence_toolbox")
RULE_LEDGER = load_module("validate_rule_execution_ledger.py", "story_short_write_rule_ledger_toolbox")
FIRST_DRAFT = load_module("validate_first_draft_entry.py", "story_short_write_first_draft_toolbox")
SECTION_EXECUTION = load_module("validate_section_draft_execution.py", "story_short_write_section_toolbox")
WRAPPERS = load_module("generate_project_tool_wrappers.py", "story_short_write_wrappers_toolbox")
COLD_START = load_module("initialize_cold_start_from_source_profiles.py", "story_short_write_cold_start_toolbox")
PROMOTE_OUTLINE_REBUILDER = load_module(
    "promote_outline_receipt_rebuilder_scaffold.py",
    "story_short_write_promote_outline_rebuilder_toolbox",
)
FIRST_DRAFT_BASIC_REVIEW = load_module(
    "validate_first_draft_basic_review.py",
    "story_short_write_first_draft_basic_review_toolbox",
)
SHORT_WRITE_COMPLETION = load_module(
    "validate_short_write_completion.py",
    "story_short_write_completion_toolbox",
)
LOCAL_STIFFNESS = load_module(
    "audit_local_stiffness.py",
    "story_short_write_local_stiffness_toolbox",
)


def infer_project_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "写作资产").is_dir() and (candidate / "设定.md").is_file():
            return candidate
    return None


def resolve_project(project_arg: str | None) -> Path:
    if project_arg:
        project = Path(project_arg).expanduser().resolve()
    else:
        project = infer_project_root(Path.cwd())
        if project is None:
            raise SystemExit("无法自动识别项目目录；请传 --project")
    if not project.is_dir():
        raise SystemExit(f"项目目录不存在: {project}")
    return project


def project_paths(project: Path) -> dict[str, Path]:
    asset = project / "写作资产"
    return {
        "project": project,
        "asset": asset,
        "setting": project / "设定.md",
        "outline": project / "小节大纲.md",
        "draft": project / "正文.md",
        "profile": project / "profiles" / f"{project.name}.project.profile.json",
        "writing_receipt": asset / "写作规则读取回执.json",
        "source_receipt": asset / "拆文读取回执.json",
        "ledger": asset / "规则执行台账.json",
        "opening_contract": asset / "开头承重契约回执_大纲.json",
        "outline_contract": asset / "细纲表演验收回执.json",
        "draft_capacity_contract": asset / "首写容量契约回执.json",
        "section_source_bundle": asset / "逐节原文颗粒包.json",
        "setting_sequence_receipt": asset / "设定顺序契约回执.json",
        "sequence_receipt": asset / "顺序契约回执.json",
        "section_execution_receipt": asset / "逐节首写执行回执.json",
        "first_draft_entry": asset / "首稿入口回执.json",
        "first_draft_basic_review": asset / "首稿基础审计回执.json",
        "completion_state": asset / "短篇全流程状态.json",
        "local_stiffness_candidates": asset / "局部生硬候选.json",
        "audit_report": asset / "项目流程诊断.json",
    }


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def command_refresh(paths: dict[str, Path], args: argparse.Namespace) -> int:
    refresh_paths = REFRESH.project_paths(paths["project"])
    actions: list[str] = []
    errors: list[str] = []
    if args.repair_ledger:
        ledger_errors, ledger_actions = REFRESH.repair_ledger(
            refresh_paths,
            use_git_fallback=args.use_git_ledger_fallback,
        )
        errors.extend(ledger_errors)
        actions.extend(ledger_actions)
    if args.refresh_bindings:
        for step in (
            REFRESH.refresh_outline_contract,
            REFRESH.refresh_opening_contract,
            REFRESH.refresh_draft_capacity_contract,
            REFRESH.refresh_sequence_receipts,
            REFRESH.refresh_section_execution,
            REFRESH.refresh_first_draft_entry,
            REFRESH.refresh_outline_rebuilder_scaffold,
        ):
            step_errors = step(refresh_paths)
            if step_errors:
                errors.extend(step_errors)
            else:
                actions.append(step.__name__)
    if args.rebuild_section_bundle:
        bundle_errors = REFRESH.rebuild_section_bundle(refresh_paths)
        if bundle_errors:
            errors.extend(bundle_errors)
        else:
            actions.append("rebuild_section_bundle")
    validation: dict[str, list[str]] = {}
    if args.validate:
        validation = REFRESH.validate_all(refresh_paths)
        for items in validation.values():
            if items:
                errors.extend(items)
    if args.json:
        print_json({"ok": not errors, "errors": errors, "actions": actions, "validation": validation})
    else:
        print("project_toolbox: refresh passed" if not errors else "project_toolbox: refresh blocked")
        for item in actions:
            print(f"- action: {item}")
        for item in errors:
            print(f"- {item}")
    return 0 if not errors else 2


def command_validate_outline(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = OUTLINE.validate_receipt(paths["outline_contract"], paths["outline"])
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-outline blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-outline passed")
    return 0 if not errors else 2


def command_validate_opening(paths: dict[str, Path], args: argparse.Namespace) -> int:
    receipt = OPENING.read_json(paths["opening_contract"])
    source_path = Path(str(receipt.get("primary_source", {}).get("path") or "")).resolve()
    target_path = Path(str(receipt.get("target_text", {}).get("path") or paths["outline"])).resolve()
    errors, _ = OPENING.validate_receipt(paths["opening_contract"], source_path, target_path)
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-opening blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-opening passed")
    return 0 if not errors else 2


def command_init_setting_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    SEQUENCE.init_setting_receipt(str(paths["project"]), paths["setting"], paths["setting_sequence_receipt"])
    if args.json:
        print_json({"ok": True, "receipt": str(paths["setting_sequence_receipt"])})
    else:
        print("project_toolbox: init-setting-sequence initialized")
        print(f"- receipt: {paths['setting_sequence_receipt']}")
    return 0


def command_validate_setting_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = SEQUENCE.validate_setting(paths["setting_sequence_receipt"], paths["setting"])
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-setting-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-setting-sequence passed")
    return 0 if not errors else 2


def command_extend_outline_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = SEQUENCE.extend_setting_receipt(
        paths["setting_sequence_receipt"],
        paths["setting"],
        paths["outline"],
        paths["sequence_receipt"],
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors, "receipt": str(paths["sequence_receipt"])})
    else:
        if errors:
            print("project_toolbox: extend-outline-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: extend-outline-sequence initialized")
            print(f"- receipt: {paths['sequence_receipt']}")
    return 0 if not errors else 2


def command_validate_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    draft_path = paths["draft"] if args.with_draft else None
    errors = SEQUENCE.validate(
        paths["sequence_receipt"],
        paths["setting"],
        paths["outline"],
        draft_path,
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-sequence passed")
    return 0 if not errors else 2


def command_extend_draft_sequence(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = SEQUENCE.extend_draft_receipt(paths["sequence_receipt"], paths["draft"])
    if args.json:
        print_json({"ok": not errors, "errors": errors, "receipt": str(paths["sequence_receipt"])})
    else:
        if errors:
            print("project_toolbox: extend-draft-sequence blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: extend-draft-sequence initialized")
            print(f"- receipt: {paths['sequence_receipt']}")
    return 0 if not errors else 2


def command_draft_release(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = WRITE_RELEASE.validate_release(
        "draft",
        paths["writing_receipt"],
        paths["source_receipt"],
        paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        setting_sequence_receipt=paths["setting_sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
        project=paths["project"],
        auto_refresh_legacy_bindings_enabled=args.auto_refresh_legacy_bindings,
        use_git_ledger_fallback=args.use_git_ledger_fallback,
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            for item in errors:
                print(item if item.startswith("- ") else f"{item}")
        else:
            print("write_release_gate: passed (draft)")
    return 0 if not errors else 2


def command_sync_sources(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors, summary = RULE_LEDGER.sync_sources(paths["ledger"])
    if args.json:
        print_json({"ok": not errors, "errors": errors, "summary": summary})
    else:
        if errors:
            print("project_toolbox: sync-sources blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: sync-sources passed")
            for key, value in summary.items():
                print(f"- {key}: {value}")
    return 0 if not errors else 2


def command_init_first_draft(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = FIRST_DRAFT.init_entry(
        project=paths["project"],
        draft=paths["draft"],
        receipt=paths["first_draft_entry"],
        writing_receipt=paths["writing_receipt"],
        source_receipt=paths["source_receipt"],
        ledger=paths["ledger"],
        opening_contract=paths["opening_contract"],
        outline_contract=paths["outline_contract"],
        profile=paths["profile"],
        sequence_receipt=paths["sequence_receipt"],
        draft_capacity_contract=paths["draft_capacity_contract"],
        section_source_bundle=paths["section_source_bundle"],
        section_execution_receipt=paths["section_execution_receipt"],
        force=args.force,
        auto_refresh_legacy_bindings_enabled=args.auto_refresh_legacy_bindings,
        use_git_ledger_fallback=args.use_git_ledger_fallback,
    )
    return result


def command_validate_first_draft(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"])
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-first-draft blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-first-draft passed")
    return 0 if not errors else 2


def command_validate_section_execution(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SECTION_EXECUTION.validate_receipt(paths["section_execution_receipt"], require_complete=args.require_complete)
    del data
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-section-execution blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-section-execution passed")
    return 0 if not errors else 2


def command_init_first_draft_basic_review(paths: dict[str, Path], args: argparse.Namespace) -> int:
    source_paths = [Path(raw) for raw in args.source]
    return FIRST_DRAFT_BASIC_REVIEW.init_receipt(
        draft=paths["draft"],
        receipt=paths["first_draft_basic_review"],
        force=args.force,
        imitation_mode=args.imitation_mode,
        source_paths=source_paths,
        section_execution_receipt=paths["section_execution_receipt"] if args.imitation_mode else None,
        draft_entry_receipt=paths["first_draft_entry"] if args.imitation_mode else None,
    )


def command_validate_first_draft_basic_review(paths: dict[str, Path], args: argparse.Namespace) -> int:
    errors = FIRST_DRAFT_BASIC_REVIEW.validate_receipt(
        paths["first_draft_basic_review"],
        paths["draft"],
    )
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-first-draft-basic-review blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-first-draft-basic-review passed")
    return 0 if not errors else 2


def command_init_completion(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return SHORT_WRITE_COMPLETION.init_state(
        paths["completion_state"],
        paths["project"],
        args.force,
    )


def command_validate_completion(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SHORT_WRITE_COMPLETION.validate_state(paths["completion_state"])
    del data
    if args.json:
        print_json({"ok": not errors, "errors": errors})
    else:
        if errors:
            print("project_toolbox: validate-completion blocked")
            for item in errors:
                print(f"- {item}")
        else:
            print("project_toolbox: validate-completion passed")
    return 0 if not errors else 2


def command_mark_draft_preview(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SHORT_WRITE_COMPLETION.validate_state(
        paths["completion_state"],
        target_status="draft_preview",
    )
    if errors:
        if args.json:
            print_json({"ok": False, "errors": errors})
        else:
            print("project_toolbox: mark-draft-preview blocked")
            for item in errors:
                print(f"- {item}")
        return 2
    data["status"] = "draft_preview"
    data["preview_ready_at"] = SHORT_WRITE_COMPLETION.now_iso()
    data["deep_review_user_confirmed"] = False
    data["deep_review_confirmed_at"] = ""
    data["deep_review_confirmation_note"] = ""
    data["next_action"] = "首稿已交用户确认；未获明确确认前禁止进入人工分窗、原文基线和正式审计。"
    SHORT_WRITE_COMPLETION.write_state(paths["completion_state"], data)
    if args.json:
        print_json({"ok": True, "state": str(paths["completion_state"])})
    else:
        print("project_toolbox: draft-preview marked")
    return 0


def command_confirm_deep_review(paths: dict[str, Path], args: argparse.Namespace) -> int:
    data, errors = SHORT_WRITE_COMPLETION.validate_state(paths["completion_state"])
    if errors:
        if args.json:
            print_json({"ok": False, "errors": errors})
        else:
            print("project_toolbox: confirm-deep-review blocked")
            for item in errors:
                print(f"- {item}")
        return 2
    if data.get("status") != "draft_preview":
        message = "只有 draft_preview 状态可以接受深审确认"
        if args.json:
            print_json({"ok": False, "errors": [message]})
        else:
            print("project_toolbox: confirm-deep-review blocked")
            print(f"- {message}")
        return 2
    note = str(args.confirmation_note or "").strip()
    if not note:
        message = "confirmation-note 不能为空"
        if args.json:
            print_json({"ok": False, "errors": [message]})
        else:
            print("project_toolbox: confirm-deep-review blocked")
            print(f"- {message}")
        return 2
    data["status"] = "active"
    data["deep_review_user_confirmed"] = True
    data["deep_review_confirmed_at"] = SHORT_WRITE_COMPLETION.now_iso()
    data["deep_review_confirmation_note"] = note
    data["next_action"] = "用户已确认，继续执行窗口前回修、原文基线、人工分窗和正式审计。"
    SHORT_WRITE_COMPLETION.write_state(paths["completion_state"], data)
    if args.json:
        print_json({"ok": True, "state": str(paths["completion_state"])})
    else:
        print("project_toolbox: deep-review confirmed")
    return 0


def command_audit_local_stiffness(paths: dict[str, Path], args: argparse.Namespace) -> int:
    text_path = paths["draft"]
    if not text_path.is_file():
        errors = [f"正文不存在: {text_path}"]
        if args.json:
            print_json({"ok": False, "errors": errors})
        else:
            print("project_toolbox: audit-local-stiffness blocked")
            for item in errors:
                print(f"- {item}")
        return 2
    payload = {
        "version": "1.0",
        "text": {
            "path": str(text_path.resolve()),
            "sha256": LOCAL_STIFFNESS.sha256(text_path),
        },
        "limitations": "脚本只定位候选，直白心理、总结句和论点对白必须由当前模型人工裁决。",
        "findings": LOCAL_STIFFNESS.scan(LOCAL_STIFFNESS.read_text(text_path)),
    }
    output_path = paths["local_stiffness_candidates"]
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print_json({"ok": True, "output": str(output_path), "count": len(payload["findings"])})
    else:
        print("project_toolbox: audit-local-stiffness passed")
        print(f"- output: {output_path}")
        print(f"- findings: {len(payload['findings'])}")
    return 0


def command_open_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return SECTION_EXECUTION.open_section(
        paths["section_execution_receipt"],
        args.section,
        args.read_judgment,
    )


def command_close_section(paths: dict[str, Path], args: argparse.Namespace) -> int:
    return SECTION_EXECUTION.close_section(
        paths["section_execution_receipt"],
        args.section,
        args.judgment,
    )


def command_generate_wrappers(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = WRAPPERS.generate_wrappers(
        paths["project"],
        use_git_ledger_fallback=args.use_git_ledger_fallback,
        remove_legacy_sh=args.remove_legacy_sh,
        include_kinds=None,
    )
    if args.json:
        print_json(result)
    else:
        if result.get("ok"):
            print("project_toolbox: generate-wrappers passed")
            for item in result.get("generated", []):
                print(f"- generated: {item}")
            for item in result.get("removed", []):
                print(f"- removed: {item}")
        else:
            print("project_toolbox: generate-wrappers blocked")
            for item in result.get("errors", []):
                print(f"- {item}")
    return 0 if result.get("ok") else 2


def command_cold_start_from_source(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = COLD_START.initialize(
        project=paths["project"],
        primary_source_profile=Path(args.primary_source_profile),
        auxiliary_source_profiles=[Path(raw) for raw in args.aux_source_profile],
        target_words=args.target_words,
        force=args.force,
    )
    if args.json:
        print_json(result)
    else:
        print("project_toolbox: cold-start-from-source passed")
        print(f"- project: {result['project']}")
        print(f"- primary_source_root: {result['primary_source_root']}")
        for key, value in result["actions"].items():
            print(f"- {key}: {value}")
    return 0


def command_promote_outline_rebuilder(paths: dict[str, Path], args: argparse.Namespace) -> int:
    result = PROMOTE_OUTLINE_REBUILDER.promote(
        project=paths["project"],
        force=args.force,
        keep_scaffold=args.keep_scaffold,
    )
    if args.json:
        print_json(result)
    else:
        if result.get("ok"):
            print("project_toolbox: promote-outline-rebuilder passed")
            print(f"- formal_wrapper: {result['formal_wrapper']}")
            print(f"- formal_data: {result['formal_data']}")
        else:
            print("project_toolbox: promote-outline-rebuilder blocked")
            for item in result.get("errors", []):
                print(f"- {item}")
    return 0 if result.get("ok") else 2


def compute_file_statuses(paths: dict[str, Path], checks: dict[str, list[str]]) -> dict[str, list[str]]:
    keep = [
        str(paths["setting"]),
        str(paths["writing_receipt"]),
        str(paths["source_receipt"]),
        str(paths["ledger"]),
        str(paths["opening_contract"]),
        str(paths["setting_sequence_receipt"]),
        str(paths["sequence_receipt"]),
        str(paths["draft_capacity_contract"]),
        str(paths["profile"]),
    ]
    rebuild: list[str] = []
    invalidate: list[str] = []
    if checks["outline"]:
        rebuild.extend(
            [
                str(paths["outline"]),
                str(paths["outline_contract"]),
                str(paths["section_source_bundle"]),
            ]
        )
        invalidate.extend(
            [
                str(paths["draft"]),
                str(paths["first_draft_entry"]),
                str(paths["section_execution_receipt"]),
            ]
        )
    else:
        if checks["first_draft"]:
            invalidate.append(str(paths["first_draft_entry"]))
        if checks["section_execution"]:
            invalidate.append(str(paths["section_execution_receipt"]))
    return {
        "keep": sorted(dict.fromkeys(keep)),
        "rebuild": sorted(dict.fromkeys(rebuild)),
        "invalidate": sorted(dict.fromkeys(invalidate)),
    }


def command_audit_project(paths: dict[str, Path], args: argparse.Namespace) -> int:
    checks = {
        "outline": OUTLINE.validate_receipt(paths["outline_contract"], paths["outline"]),
        "draft_release": WRITE_RELEASE.validate_release(
            "draft",
            paths["writing_receipt"],
            paths["source_receipt"],
            paths["ledger"],
            opening_contract=paths["opening_contract"],
            outline_contract=paths["outline_contract"],
            profile=paths["profile"],
            sequence_receipt=paths["sequence_receipt"],
            setting_sequence_receipt=paths["setting_sequence_receipt"],
            draft_capacity_contract=paths["draft_capacity_contract"],
            section_source_bundle=paths["section_source_bundle"],
            project=paths["project"],
            auto_refresh_legacy_bindings_enabled=False,
            use_git_ledger_fallback=args.use_git_ledger_fallback,
        ),
        "first_draft": FIRST_DRAFT.validate_entry(paths["first_draft_entry"], paths["draft"]) if paths["first_draft_entry"].is_file() else ["首稿入口回执不存在"],
        "section_execution": SECTION_EXECUTION.validate_receipt(paths["section_execution_receipt"])[1] if paths["section_execution_receipt"].is_file() else ["逐节首写执行回执不存在"],
    }
    status = compute_file_statuses(paths, checks)
    report = {
        "project": str(paths["project"]),
        "ok": not any(checks.values()),
        "checks": checks,
        "file_status": status,
        "next_steps": [
            "先修 outline/rebuild 类文件，再重新生成下游回执与正文入口"
            if status["rebuild"]
            else "当前项目未发现需要强制回炉的前置文件"
        ],
    }
    if args.write_report:
        paths["audit_report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print_json(report)
    else:
        print("project_toolbox: audit blocked" if not report["ok"] else "project_toolbox: audit passed")
        for key, errors in checks.items():
            print(f"[{key}] {'ok' if not errors else 'blocked'}")
            for item in errors:
                print(f"- {item}")
        if status["rebuild"]:
            print("[rebuild]")
            for item in status["rebuild"]:
                print(f"- {item}")
        if status["invalidate"]:
            print("[invalidate]")
            for item in status["invalidate"]:
                print(f"- {item}")
    return 0 if report["ok"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="项目目录；不传则从当前目录向上自动识别")
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh = subparsers.add_parser("refresh-bindings")
    refresh.add_argument("--repair-ledger", action="store_true", default=True)
    refresh.add_argument("--refresh-bindings", action="store_true", default=True)
    refresh.add_argument("--rebuild-section-bundle", action="store_true", default=True)
    refresh.add_argument("--validate", action="store_true", default=True)
    refresh.add_argument("--use-git-ledger-fallback", action="store_true")
    refresh.set_defaults(func=command_refresh)

    outline = subparsers.add_parser("validate-outline")
    outline.set_defaults(func=command_validate_outline)

    opening = subparsers.add_parser("validate-opening")
    opening.set_defaults(func=command_validate_opening)

    init_setting_sequence = subparsers.add_parser("init-setting-sequence")
    init_setting_sequence.set_defaults(func=command_init_setting_sequence)

    validate_setting_sequence = subparsers.add_parser("validate-setting-sequence")
    validate_setting_sequence.set_defaults(func=command_validate_setting_sequence)

    extend_outline_sequence = subparsers.add_parser("extend-outline-sequence")
    extend_outline_sequence.set_defaults(func=command_extend_outline_sequence)

    validate_sequence = subparsers.add_parser("validate-sequence")
    validate_sequence.add_argument("--with-draft", action="store_true")
    validate_sequence.set_defaults(func=command_validate_sequence)

    extend_draft_sequence = subparsers.add_parser("extend-draft-sequence")
    extend_draft_sequence.set_defaults(func=command_extend_draft_sequence)

    release = subparsers.add_parser("draft-release")
    release.add_argument("--auto-refresh-legacy-bindings", action="store_true")
    release.add_argument("--use-git-ledger-fallback", action="store_true")
    release.set_defaults(func=command_draft_release)

    sync_sources = subparsers.add_parser("sync-sources")
    sync_sources.set_defaults(func=command_sync_sources)

    init_first = subparsers.add_parser("init-first-draft")
    init_first.add_argument("--force", action="store_true")
    init_first.add_argument("--auto-refresh-legacy-bindings", action="store_true")
    init_first.add_argument("--use-git-ledger-fallback", action="store_true")
    init_first.set_defaults(func=command_init_first_draft)

    validate_first = subparsers.add_parser("validate-first-draft")
    validate_first.set_defaults(func=command_validate_first_draft)

    init_first_basic = subparsers.add_parser("init-first-draft-basic-review")
    init_first_basic.add_argument("--force", action="store_true")
    init_first_basic.add_argument("--imitation-mode", action="store_true")
    init_first_basic.add_argument("--source", action="append", default=[])
    init_first_basic.set_defaults(func=command_init_first_draft_basic_review)

    validate_first_basic = subparsers.add_parser("validate-first-draft-basic-review")
    validate_first_basic.set_defaults(func=command_validate_first_draft_basic_review)

    validate_section = subparsers.add_parser("validate-section-execution")
    validate_section.add_argument("--require-complete", action="store_true")
    validate_section.set_defaults(func=command_validate_section_execution)

    open_section = subparsers.add_parser("open-section")
    open_section.add_argument("--section", required=True)
    open_section.add_argument("--read-judgment", required=True)
    open_section.set_defaults(func=command_open_section)

    close_section = subparsers.add_parser("close-section")
    close_section.add_argument("--section", required=True)
    close_section.add_argument("--judgment", required=True)
    close_section.set_defaults(func=command_close_section)

    wrappers = subparsers.add_parser("generate-wrappers")
    wrappers.add_argument("--use-git-ledger-fallback", action="store_true")
    wrappers.add_argument("--remove-legacy-sh", action="store_true")
    wrappers.set_defaults(func=command_generate_wrappers)

    cold_start = subparsers.add_parser("cold-start-from-source")
    cold_start.add_argument("--primary-source-profile", required=True)
    cold_start.add_argument("--aux-source-profile", action="append", default=[])
    cold_start.add_argument("--target-words", type=int, default=10000)
    cold_start.add_argument("--force", action="store_true")
    cold_start.set_defaults(func=command_cold_start_from_source)

    promote_outline_rebuilder = subparsers.add_parser("promote-outline-rebuilder")
    promote_outline_rebuilder.add_argument("--force", action="store_true")
    promote_outline_rebuilder.add_argument("--keep-scaffold", action="store_true")
    promote_outline_rebuilder.set_defaults(func=command_promote_outline_rebuilder)

    init_completion = subparsers.add_parser("init-completion")
    init_completion.add_argument("--force", action="store_true")
    init_completion.set_defaults(func=command_init_completion)

    validate_completion = subparsers.add_parser("validate-completion")
    validate_completion.set_defaults(func=command_validate_completion)

    mark_preview = subparsers.add_parser("mark-draft-preview")
    mark_preview.set_defaults(func=command_mark_draft_preview)

    confirm_deep = subparsers.add_parser("confirm-deep-review")
    confirm_deep.add_argument("--confirmation-note", required=True)
    confirm_deep.set_defaults(func=command_confirm_deep_review)

    local_stiffness = subparsers.add_parser("audit-local-stiffness")
    local_stiffness.set_defaults(func=command_audit_local_stiffness)

    audit = subparsers.add_parser("audit-project")
    audit.add_argument("--write-report", action="store_true")
    audit.add_argument("--use-git-ledger-fallback", action="store_true")
    audit.set_defaults(func=command_audit_project)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    project = resolve_project(args.project)
    paths = project_paths(project)
    return int(args.func(paths, args))


if __name__ == "__main__":
    raise SystemExit(main())
