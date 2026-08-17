#!/usr/bin/env python3
"""High-level wrapper for final full-draft bind/validate workflow."""

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


SECTION = _load_module(
    "validate_section_progress.py",
    "story_short_write_batch_full_draft_section_progress",
)
PROSE = _load_module(
    "validate_prose_granularity_contract.py",
    "story_short_write_batch_full_draft_prose",
)
EMOTION = _load_module(
    "validate_emotional_granularity_contract.py",
    "story_short_write_batch_full_draft_emotion",
)
COUNT = _load_module(
    "count_words.py",
    "story_short_write_batch_full_draft_count_words",
)
ZHIHU = _load_module(
    "validate_zhihu_section_format.py",
    "story_short_write_batch_full_draft_zhihu",
)


def _quote_shell(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def default_paths(
    *,
    project: str,
    project_dir: Path,
    state: Path | None = None,
    draft: Path | None = None,
    prose_contract: Path | None = None,
    emotional_contract: Path | None = None,
    source_original: Path | None = None,
    source_emotion_ledger: Path | None = None,
) -> dict[str, Any]:
    resolved_project_dir = project_dir.expanduser().resolve()
    assets = (resolved_project_dir / "写作资产").resolve()
    return {
        "project": project,
        "project_dir": resolved_project_dir,
        "state": (
            state.expanduser().resolve()
            if state is not None
            else (assets / "逐节正文进度.json").resolve()
        ),
        "draft": (
            draft.expanduser().resolve()
            if draft is not None
            else (resolved_project_dir / "正文.md").resolve()
        ),
        "prose_contract": (
            prose_contract.expanduser().resolve()
            if prose_contract is not None
            else (assets / "全文文字颗粒度契约回执.json").resolve()
        ),
        "emotional_contract": (
            emotional_contract.expanduser().resolve()
            if emotional_contract is not None
            else (assets / "全文情绪颗粒度契约回执.json").resolve()
        ),
        "source_original": source_original.expanduser().resolve() if source_original is not None else None,
        "source_emotion_ledger": source_emotion_ledger.expanduser().resolve() if source_emotion_ledger is not None else None,
    }


def infer_source_paths(
    *,
    prose_contract: Path,
    emotional_contract: Path,
    source_original: Path | None,
    source_emotion_ledger: Path | None,
) -> dict[str, Path]:
    resolved_source_original = source_original.expanduser().resolve() if source_original is not None else None
    resolved_source_emotion_ledger = (
        source_emotion_ledger.expanduser().resolve()
        if source_emotion_ledger is not None
        else None
    )
    if resolved_source_original is None and prose_contract.is_file():
        prose_payload = load_json(prose_contract, "全文文字颗粒度契约回执")
        binding = prose_payload.get("primary_prose_source")
        if isinstance(binding, dict) and str(binding.get("path") or "").strip():
            resolved_source_original = Path(str(binding["path"])).expanduser().resolve()
    if emotional_contract.is_file():
        emotional_payload = load_json(emotional_contract, "全文情绪颗粒度契约回执")
        bindings = emotional_payload.get("bindings")
        if isinstance(bindings, dict):
            if resolved_source_original is None:
                primary = bindings.get("primary_source_original")
                if isinstance(primary, dict) and str(primary.get("path") or "").strip():
                    resolved_source_original = Path(str(primary["path"])).expanduser().resolve()
            if resolved_source_emotion_ledger is None:
                ledger = bindings.get("source_emotion_ledger")
                if isinstance(ledger, dict) and str(ledger.get("path") or "").strip():
                    resolved_source_emotion_ledger = Path(str(ledger["path"])).expanduser().resolve()
    if resolved_source_original is None:
        raise ValueError("无法自动推导主体原文路径，请显式传入 --source-original")
    if resolved_source_emotion_ledger is None:
        raise ValueError("无法自动推导主体情绪总账路径，请显式传入 --source-emotion-ledger")
    return {
        "source_original": resolved_source_original,
        "source_emotion_ledger": resolved_source_emotion_ledger,
    }


def inspect_full_draft_status(
    *,
    project: str,
    project_dir: Path,
    state: Path | None = None,
    draft: Path | None = None,
    prose_contract: Path | None = None,
    emotional_contract: Path | None = None,
    source_original: Path | None = None,
    source_emotion_ledger: Path | None = None,
    zhihu_mode: bool = False,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        state=state,
        draft=draft,
        prose_contract=prose_contract,
        emotional_contract=emotional_contract,
        source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
    )
    state_payload = load_json(paths["state"], "逐节正文进度")
    draft_exists = paths["draft"].is_file()
    draft_sha256 = SECTION.sha256_file(paths["draft"]) if draft_exists else ""
    prose_exists = paths["prose_contract"].is_file()
    emotional_exists = paths["emotional_contract"].is_file()
    prose_bound = False
    prose_ready = False
    emotional_bound = False
    emotional_ready = False
    prose_gate_status = ""
    emotional_draft_status = ""
    if prose_exists:
        prose_payload = load_json(paths["prose_contract"], "全文文字颗粒度契约回执")
        draft_binding = prose_payload.get("draft")
        if isinstance(draft_binding, dict):
            prose_bound = str(draft_binding.get("sha256") or "") == draft_sha256 and bool(draft_sha256)
        prose_gate_status = str(prose_payload.get("gate_status") or "")
        manual = prose_payload.get("manual_review_provenance")
        prose_ready = (
            prose_bound
            and prose_gate_status == "passed"
            and isinstance(manual, dict)
            and manual.get("performed_by_current_model") is True
            and manual.get("full_text_read_by_current_model") is True
            and manual.get("semantic_fields_generated_by_script") is False
            and str(manual.get("review_bound_to_draft_sha256") or "") == draft_sha256
        )
    if emotional_exists:
        emotional_payload = load_json(paths["emotional_contract"], "全文情绪颗粒度契约回执")
        bindings = emotional_payload.get("bindings")
        if isinstance(bindings, dict):
            draft_binding = bindings.get("draft")
            if isinstance(draft_binding, dict):
                emotional_bound = str(draft_binding.get("sha256") or "") == draft_sha256 and bool(draft_sha256)
        emotional_draft_status = str(emotional_payload.get("draft_status") or "")
        emotional_ready = (
            emotional_bound
            and emotional_payload.get("reviewed_by_current_model") is True
            and emotional_draft_status == "passed"
        )
    return {
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "state": str(paths["state"]),
        "draft": str(paths["draft"]),
        "draft_exists": draft_exists,
        "draft_sha256": draft_sha256,
        "section_progress_status": str(state_payload.get("status") or ""),
        "final_draft_sha256": str(state_payload.get("final_draft_sha256") or ""),
        "prose_contract": {
            "path": str(paths["prose_contract"]),
            "exists": prose_exists,
            "bound": prose_bound,
            "ready": prose_ready,
            "gate_status": prose_gate_status,
        },
        "emotional_contract": {
            "path": str(paths["emotional_contract"]),
            "exists": emotional_exists,
            "bound": emotional_bound,
            "ready": emotional_ready,
            "draft_status": emotional_draft_status,
        },
        "zhihu_mode": zhihu_mode,
    }


def bind_full_draft_contracts(
    *,
    project: str,
    project_dir: Path,
    state: Path | None = None,
    draft: Path | None = None,
    prose_contract: Path | None = None,
    emotional_contract: Path | None = None,
    source_original: Path | None = None,
    source_emotion_ledger: Path | None = None,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        state=state,
        draft=draft,
        prose_contract=prose_contract,
        emotional_contract=emotional_contract,
        source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
    )
    errors: list[str] = []
    status = inspect_full_draft_status(
        project=project,
        project_dir=project_dir,
        state=paths["state"],
        draft=paths["draft"],
        prose_contract=paths["prose_contract"],
        emotional_contract=paths["emotional_contract"],
        source_original=paths["source_original"],
        source_emotion_ledger=paths["source_emotion_ledger"],
    )
    if status["section_progress_status"] != "final_ready":
        errors.append(f"逐节正文进度未 final_ready: {status['section_progress_status']}")
        return errors, {}
    if not paths["draft"].is_file():
        errors.append(f"正文不存在: {paths['draft']}")
        return errors, {}
    try:
        prose_payload = load_json(paths["prose_contract"], "全文文字颗粒度契约回执")
        emotional_payload = load_json(paths["emotional_contract"], "全文情绪颗粒度契约回执")
        prose_payload = PROSE.bind_draft(prose_payload, paths["draft"])
        emotional_payload = EMOTION.bind_draft(emotional_payload, paths["draft"])
        _write_json(paths["prose_contract"], prose_payload)
        _write_json(paths["emotional_contract"], emotional_payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        return errors, {}
    return [], {
        "draft": str(paths["draft"]),
        "draft_sha256": SECTION.sha256_file(paths["draft"]),
        "prose_contract": str(paths["prose_contract"]),
        "emotional_contract": str(paths["emotional_contract"]),
    }


def validate_full_draft(
    *,
    project: str,
    project_dir: Path,
    state: Path | None = None,
    draft: Path | None = None,
    prose_contract: Path | None = None,
    emotional_contract: Path | None = None,
    source_original: Path | None = None,
    source_emotion_ledger: Path | None = None,
    zhihu_mode: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        state=state,
        draft=draft,
        prose_contract=prose_contract,
        emotional_contract=emotional_contract,
        source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
    )
    errors: list[str] = []
    try:
        inferred = infer_source_paths(
            prose_contract=paths["prose_contract"],
            emotional_contract=paths["emotional_contract"],
            source_original=paths["source_original"],
            source_emotion_ledger=paths["source_emotion_ledger"],
        )
        prose_payload = load_json(paths["prose_contract"], "全文文字颗粒度契约回执")
        prose_errors, prose_summary = PROSE.validate_draft_data(
            prose_payload,
            inferred["source_original"],
            paths["draft"],
        )
        prose_errors = PROSE.validate_section_progress_receipt(
            paths["state"],
            paths["draft"],
        ) + prose_errors
        emotional_payload = load_json(paths["emotional_contract"], "全文情绪颗粒度契约回执")
        emotional_errors, _ = EMOTION.validate_draft_data(
            emotional_payload,
            inferred["source_original"],
            paths["draft"],
            inferred["source_emotion_ledger"],
        )
        emotional_errors = EMOTION.validate_section_progress_receipt(
            paths["state"],
            paths["draft"],
        ) + emotional_errors
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)], {}
    errors.extend(f"全文文字颗粒度合同未通过: {item}" for item in prose_errors)
    errors.extend(f"全文情绪颗粒度合同未通过: {item}" for item in emotional_errors)
    summary: dict[str, Any] = {
        "draft": str(paths["draft"]),
        "draft_sha256": SECTION.sha256_file(paths["draft"]) if paths["draft"].is_file() else "",
        "prose_summary": prose_summary,
        "word_count": COUNT.build_result([paths["draft"]]),
    }
    if zhihu_mode:
        text = ZHIHU.read_text(paths["draft"])
        zhihu_errors, sections = ZHIHU.validate_text(text)
        summary["zhihu_section_count"] = len(sections)
        errors.extend(f"知乎分节格式未通过: {item}" for item in zhihu_errors)
    return errors, summary


def suggest_next_step(
    *,
    project: str,
    project_dir: Path,
    state: Path | None = None,
    draft: Path | None = None,
    prose_contract: Path | None = None,
    emotional_contract: Path | None = None,
    source_original: Path | None = None,
    source_emotion_ledger: Path | None = None,
    zhihu_mode: bool = False,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        state=state,
        draft=draft,
        prose_contract=prose_contract,
        emotional_contract=emotional_contract,
        source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
    )
    status = inspect_full_draft_status(
        project=project,
        project_dir=project_dir,
        state=paths["state"],
        draft=paths["draft"],
        prose_contract=paths["prose_contract"],
        emotional_contract=paths["emotional_contract"],
        source_original=paths["source_original"],
        source_emotion_ledger=paths["source_emotion_ledger"],
        zhihu_mode=zhihu_mode,
    )
    status_command = (
        'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" status '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
        + (" --zhihu-mode" if zhihu_mode else "")
    )
    run_command = (
        'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" run-full-draft-cycle '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
        + (" --zhihu-mode" if zhihu_mode else "")
    )
    bind_command = (
        'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" bind-full-draft-contracts '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    validate_command = (
        'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" validate-full-draft '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
        + (" --zhihu-mode" if zhihu_mode else "")
    )
    if not status["draft_exists"]:
        return {
            "action": "missing_draft",
            "reason": "正文不存在，无法进入全文收口链",
            "next_command": "",
            "status_command": status_command,
        }
    progress_status = status["section_progress_status"]
    if progress_status == "sections_passed":
        return {
            "action": "finalize_section_progress",
            "reason": "所有小节已逐节通过，但还没有进入 final_ready",
            "next_command": run_command,
            "status_command": status_command,
        }
    if progress_status != "final_ready":
        return {
            "action": "finish_section_progress_first",
            "reason": f"逐节正文进度尚未到达 sections_passed/final_ready: {progress_status}",
            "next_command": "",
            "status_command": status_command,
        }
    if not status["prose_contract"]["bound"] or not status["emotional_contract"]["bound"]:
        return {
            "action": "bind_full_draft_contracts",
            "reason": "两份全文合同还没绑定当前 final_ready 正文 SHA",
            "next_command": bind_command,
            "status_command": status_command,
        }
    if not status["prose_contract"]["ready"] or not status["emotional_contract"]["ready"]:
        return {
            "action": "complete_full_draft_receipts",
            "reason": "两份全文合同已绑定，但全文人工复核字段还没补到可校验状态",
            "next_command": status_command,
            "status_command": status_command,
        }
    return {
        "action": "validate_full_draft",
        "reason": "两份全文合同已绑定且处于 passed 态，下一步直接做全文校验与字数/平台格式收口",
        "next_command": validate_command,
        "status_command": status_command,
    }


def run_full_draft_cycle(
    *,
    project: str,
    project_dir: Path,
    state: Path | None = None,
    draft: Path | None = None,
    prose_contract: Path | None = None,
    emotional_contract: Path | None = None,
    source_original: Path | None = None,
    source_emotion_ledger: Path | None = None,
    zhihu_mode: bool = False,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        state=state,
        draft=draft,
        prose_contract=prose_contract,
        emotional_contract=emotional_contract,
        source_original=source_original,
        source_emotion_ledger=source_emotion_ledger,
    )
    completed_steps: list[str] = []
    for _ in range(4):
        suggestion = suggest_next_step(
            project=project,
            project_dir=project_dir,
            state=paths["state"],
            draft=paths["draft"],
            prose_contract=paths["prose_contract"],
            emotional_contract=paths["emotional_contract"],
            source_original=paths["source_original"],
            source_emotion_ledger=paths["source_emotion_ledger"],
            zhihu_mode=zhihu_mode,
        )
        action = suggestion["action"]
        if action in {
            "missing_draft",
            "finish_section_progress_first",
            "complete_full_draft_receipts",
        }:
            suggestion["completed_steps"] = completed_steps
            return suggestion
        if action == "finalize_section_progress":
            code = SECTION.command_finalize(argparse.Namespace(state=str(paths["state"])))
            if code != 0:
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": ["逐节正文进度 finalize 失败，请查看底层门禁输出"],
                    "completed_steps": completed_steps,
                    "status_command": suggestion["status_command"],
                }
            completed_steps.append("finalize_section_progress")
            continue
        if action == "bind_full_draft_contracts":
            errors, summary = bind_full_draft_contracts(
                project=project,
                project_dir=project_dir,
                state=paths["state"],
                draft=paths["draft"],
                prose_contract=paths["prose_contract"],
                emotional_contract=paths["emotional_contract"],
                source_original=paths["source_original"],
                source_emotion_ledger=paths["source_emotion_ledger"],
            )
            if errors:
                return {
                    "action": action,
                    "reason": suggestion["reason"],
                    "errors": errors,
                    "completed_steps": completed_steps,
                    "status_command": suggestion["status_command"],
                }
            completed_steps.append("bind_full_draft_contracts")
            continue
        errors, summary = validate_full_draft(
            project=project,
            project_dir=project_dir,
            state=paths["state"],
            draft=paths["draft"],
            prose_contract=paths["prose_contract"],
            emotional_contract=paths["emotional_contract"],
            source_original=paths["source_original"],
            source_emotion_ledger=paths["source_emotion_ledger"],
            zhihu_mode=zhihu_mode,
        )
        result = {
            "action": action,
            "reason": suggestion["reason"],
            "completed_steps": completed_steps,
            "status_command": suggestion["status_command"],
            "summary": summary,
        }
        if errors:
            result["errors"] = errors
        return result
    return {
        "action": "loop_guard_triggered",
        "reason": "高层全文收口链执行次数异常，请改用 status 检查当前状态",
        "completed_steps": completed_steps,
    }


def emit_shell_template(
    *,
    project: str,
    project_dir: Path,
    zhihu_mode: bool = False,
) -> str:
    suffix = " \\\n  --zhihu-mode" if zhihu_mode else ""
    return "\n".join(
        [
            'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" status \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}{suffix}",
            "",
            'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" next-step \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}{suffix}",
            "",
            'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" bind-full-draft-contracts \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}",
            "",
            'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" validate-full-draft \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}{suffix}",
            "",
            'python3 "$SKILL_ROOT/scripts/batch_full_draft_review.py" run-full-draft-cycle \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(project_dir.expanduser().resolve()))}{suffix}",
        ]
    )


def _print_status(status: dict[str, Any]) -> None:
    print("batch_full_draft_review: status")
    print(f"project: {status['project']}")
    print(f"project_dir: {status['project_dir']}")
    print(f"state: {status['state']}")
    print(f"draft: {status['draft']}")
    print(f"draft_exists: {status['draft_exists']}")
    print(f"section_progress_status: {status['section_progress_status']}")
    print(f"prose_contract_bound: {status['prose_contract']['bound']}")
    print(f"prose_contract_ready: {status['prose_contract']['ready']}")
    print(f"emotional_contract_bound: {status['emotional_contract']['bound']}")
    print(f"emotional_contract_ready: {status['emotional_contract']['ready']}")
    print(f"zhihu_mode: {status['zhihu_mode']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in (
        "status",
        "next-step",
        "bind-full-draft-contracts",
        "validate-full-draft",
        "run-full-draft-cycle",
        "emit-shell-template",
    ):
        cmd = sub.add_parser(command)
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--project-dir", required=True)
        cmd.add_argument("--state")
        cmd.add_argument("--draft")
        cmd.add_argument("--prose-contract")
        cmd.add_argument("--emotional-contract")
        cmd.add_argument("--source-original")
        cmd.add_argument("--source-emotion-ledger")
        cmd.add_argument("--zhihu-mode", action="store_true")
    args = parser.parse_args()
    kwargs = {
        "project": args.project,
        "project_dir": Path(args.project_dir),
        "state": Path(args.state) if args.state else None,
        "draft": Path(args.draft) if args.draft else None,
        "prose_contract": Path(args.prose_contract) if args.prose_contract else None,
        "emotional_contract": Path(args.emotional_contract) if args.emotional_contract else None,
        "source_original": Path(args.source_original) if args.source_original else None,
        "source_emotion_ledger": Path(args.source_emotion_ledger) if args.source_emotion_ledger else None,
        "zhihu_mode": bool(args.zhihu_mode),
    }
    if args.command == "status":
        _print_status(inspect_full_draft_status(**kwargs))
        return 0
    if args.command == "next-step":
        print(json.dumps(suggest_next_step(**kwargs), ensure_ascii=False, indent=2))
        return 0
    if args.command == "bind-full-draft-contracts":
        bind_kwargs = dict(kwargs)
        bind_kwargs.pop("zhihu_mode", None)
        errors, summary = bind_full_draft_contracts(**bind_kwargs)
        if errors:
            print("batch_full_draft_review: blocked (bind-full-draft-contracts)")
            for error in errors:
                print(f"- {error}")
            return 2
        print("batch_full_draft_review: bound")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate-full-draft":
        errors, summary = validate_full_draft(**kwargs)
        if errors:
            print("batch_full_draft_review: blocked (validate-full-draft)")
            for error in errors:
                print(f"- {error}")
            return 2
        print("batch_full_draft_review: passed")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "run-full-draft-cycle":
        result = run_full_draft_cycle(**kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result.get("errors") else 2
    print(emit_shell_template(project=args.project, project_dir=Path(args.project_dir), zhihu_mode=bool(args.zhihu_mode)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
