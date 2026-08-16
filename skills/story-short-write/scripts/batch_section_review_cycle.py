#!/usr/bin/env python3
"""High-level wrapper for deterministic per-section commit workflow."""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
from pathlib import Path
from typing import Any
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parent


def _load_module(filename: str, alias: str):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INIT = _load_module(
    "init_section_review.py",
    "story_short_write_batch_section_init_review",
)
MANAGE = _load_module(
    "manage_section_review.py",
    "story_short_write_batch_manage_section_review",
)
STATE = _load_module(
    "validate_section_progress.py",
    "story_short_write_batch_validate_section_progress",
)
SIDE = _load_module(
    "sidecar_lifecycle.py",
    "story_short_write_batch_section_sidecar",
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


def default_paths(
    *,
    project: str,
    project_dir: Path,
    section: int,
    state: Path | None = None,
    staged: Path | None = None,
    review: Path | None = None,
    sidecar: Path | None = None,
    context_output: Path | None = None,
) -> dict[str, Any]:
    resolved_project_dir = project_dir.expanduser().resolve()
    assets = (resolved_project_dir / "写作资产").resolve()
    return {
        "project": project,
        "project_dir": resolved_project_dir,
        "section": str(section),
        "state": (
            state.expanduser().resolve()
            if state is not None
            else (assets / "逐节正文进度.json").resolve()
        ),
        "staged": (
            staged.expanduser().resolve()
            if staged is not None
            else (assets / "当前节暂存" / f"第{section}节.md").resolve()
        ),
        "review": (
            review.expanduser().resolve()
            if review is not None
            else (assets / "逐节验收" / f"第{section}节.json").resolve()
        ),
        "sidecar": (
            sidecar.expanduser().resolve()
            if sidecar is not None
            else (assets / "逐节验收" / "侧车" / f"第{section}节人工.json").resolve()
        ),
        "context_output": (
            context_output.expanduser().resolve()
            if context_output is not None
            else (assets / "当前节写作包" / f"第{section}节.json").resolve()
        ),
    }


def prepare_section_review(
    *,
    project: str,
    project_dir: Path,
    section: int,
    state: Path | None,
    staged: Path | None,
    review: Path | None,
    sidecar: Path | None,
    context_output: Path | None,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        section=section,
        state=state,
        staged=staged,
        review=review,
        sidecar=sidecar,
        context_output=context_output,
    )
    errors: list[str] = []
    if not paths["state"].is_file():
        errors.append(f"逐节正文进度不存在: {paths['state']}")
        return errors, {}
    if not paths["staged"].is_file():
        errors.append(f"当前节暂存稿不存在: {paths['staged']}")
        return errors, {}
    if paths["review"].exists():
        errors.append(f"逐节回执已存在，拒绝覆盖: {paths['review']}")
        return errors, {}
    try:
        state_payload = INIT.load_json(paths["state"])
        prose_path = Path(str(state_payload.get("paths", {}).get("prose_receipt") or "")).resolve()
        if not prose_path.is_file():
            raise ValueError(f"文字合同不存在: {prose_path}")
        staged_text = paths["staged"].read_text(encoding="utf-8")
        review_payload = INIT.build_review(
            state_payload,
            INIT.load_json(prose_path),
            paths["section"],
            staged_text,
        )
        review_payload["review_scaffold"]["state_sha256"] = INIT.hashlib.sha256(
            paths["state"].read_bytes()
        ).hexdigest()
        paths["review"].parent.mkdir(parents=True, exist_ok=True)
        emotion_path = Path(
            str(state_payload.get("paths", {}).get("emotion_receipt") or "")
        ).resolve()
        if not emotion_path.is_file():
            raise ValueError(f"情绪合同不存在: {emotion_path}")
        INIT.mark_review_deferred(
            review_payload,
            state_path=paths["state"],
            staged_path=paths["staged"],
            prose_path=prose_path,
            emotion_path=emotion_path,
        )
        paths["review"].write_text(
            json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        return errors, {}
    return [], {
        "review": str(paths["review"]),
        "review_mode": INIT.DEFERRED_REVIEW_MODE,
        "staged": str(paths["staged"]),
        "context_output": str(paths["context_output"]),
    }


def _sidecar_status(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False, "status": "missing"}
    payload = load_json(path, label)
    schema = str(payload.get("schema_version") or "")
    if schema == SIDE.CONSUMED_SCHEMA or payload.get("status") == "consumed":
        return {
            "path": str(path),
            "exists": True,
            "status": "consumed",
            "operation": str(payload.get("operation") or ""),
        }
    return {
        "path": str(path),
        "exists": True,
        "status": "active",
        "schema_version": schema,
        "payload": payload,
    }


def _is_manual_item_complete(item: dict[str, Any]) -> bool:
    try:
        MANAGE.validate_complete_item(item)
        return True
    except ValueError:
        return False


def inspect_section_review_status(
    *,
    project: str,
    project_dir: Path,
    section: int,
    state: Path | None = None,
    staged: Path | None = None,
    review: Path | None = None,
    sidecar: Path | None = None,
    context_output: Path | None = None,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        section=section,
        state=state,
        staged=staged,
        review=review,
        sidecar=sidecar,
        context_output=context_output,
    )
    state_payload = STATE.load_json(paths["state"])
    item = STATE.get_section_state(state_payload, paths["section"])
    sidecar_status = _sidecar_status(paths["sidecar"], "逐节人工侧车")
    review_exists = paths["review"].is_file()
    review_status = "missing"
    review_final_status = ""
    if review_exists:
        review_payload = load_json(paths["review"], "逐节回执")
        review_final_status = str(review_payload.get("final_status") or "")
        review_mode = str((review_payload.get("review_scaffold") or {}).get("review_mode") or "")
        review_status = "ready" if review_mode == INIT.DEFERRED_REVIEW_MODE else "active"
    status = {
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "section": paths["section"],
        "state": str(paths["state"]),
        "section_status": str(item.get("status") or ""),
        "current_section": str(state_payload.get("current_section") or ""),
        "staged": str(paths["staged"]),
        "staged_exists": paths["staged"].is_file(),
        "review": {"path": str(paths["review"]), "exists": review_exists, "status": review_status, "final_status": review_final_status},
        "sidecar": sidecar_status,
    }
    if review_exists:
        status["review"]["review_mode"] = review_mode
    if review_exists and review_mode == INIT.DEFERRED_REVIEW_MODE:
        status["sidecar"] = {
            "path": str(paths["sidecar"]),
            "exists": paths["sidecar"].is_file(),
            "status": "not_required",
        }
        return status
    if sidecar_status["status"] == "active":
        payload = sidecar_status["payload"]
        lean_review = payload.get("lean_manual_review")
        if isinstance(lean_review, dict):
            scene_count = len(lean_review.get("scene_reviews") or [])
            character_count = len(lean_review.get("character_reviews") or [])
            status["sidecar"]["review_mode"] = str(lean_review.get("review_mode") or "")
            status["sidecar"]["total_items"] = 1 + scene_count + character_count
            try:
                MANAGE.apply_template(
                    paths["review"],
                    paths["staged"],
                    paths["sidecar"],
                    write=False,
                )
                status["sidecar"]["pending_items"] = 0
            except ValueError as exc:
                status["sidecar"]["pending_items"] = status["sidecar"]["total_items"]
                status["sidecar"]["preflight_error"] = str(exc)
            return status
        manual_items = [
            item for item in (payload.get("manual_items") or [])
            if isinstance(item, dict)
        ]
        if isinstance(payload.get("compact_manual_items"), dict) and review_exists and paths["staged"].is_file():
            review_payload = load_json(paths["review"], "逐节回执")
            registry = MANAGE.build_registry(
                paths["staged"].read_text(encoding="utf-8"),
                review_payload,
            )
            expected_items = MANAGE.build_items(review_payload, registry)
            try:
                manual_items = MANAGE.expand_compact_manual_items(
                    payload["compact_manual_items"],
                    expected_items,
                )
            except ValueError as exc:
                status["sidecar"]["preflight_error"] = str(exc)
        status["sidecar"]["total_items"] = len(manual_items)
        status["sidecar"]["pending_items"] = sum(0 if _is_manual_item_complete(item) else 1 for item in manual_items)
        if status["sidecar"]["pending_items"] == 0:
            try:
                MANAGE.validate_fixed_semantic_contract(manual_items)
                MANAGE.validate_semantic_specificity(manual_items)
            except ValueError as exc:
                status["sidecar"]["preflight_error"] = str(exc)
    return status


def suggest_next_step(
    *,
    project: str,
    project_dir: Path,
    section: int,
    state: Path | None,
    staged: Path | None,
    review: Path | None,
    sidecar: Path | None,
    context_output: Path | None,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        section=section,
        state=state,
        staged=staged,
        review=review,
        sidecar=sidecar,
        context_output=context_output,
    )
    status = inspect_section_review_status(
        project=project,
        project_dir=project_dir,
        section=section,
        state=paths["state"],
        staged=paths["staged"],
        review=paths["review"],
        sidecar=paths["sidecar"],
        context_output=paths["context_output"],
    )
    status_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" status '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))} '
        f'--section {section}'
    )
    prepare_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" prepare-section-review '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))} '
        f'--section {section}'
    )
    run_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" run-section-review-cycle '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))} '
        f'--section {section}'
    )
    if status["section_status"] == "passed":
        return {
            "action": "enter_next_section_or_finalize",
            "reason": "当前节已 passed，不需要再初始化或提交本节回执",
            "next_command": "",
            "status_command": status_command,
        }
    if status["section_status"] != "writing":
        return {
            "action": "start_section_first",
            "reason": "当前节还没有进入 writing 状态，必须先完成 start-section",
            "next_command": "",
            "status_command": status_command,
        }
    if not status["review"]["exists"]:
        return {
            "action": "prepare_section_review",
            "reason": "逐节确定性回执尚未创建，先绑定当前暂存稿与写前合同",
            "next_command": prepare_command,
            "status_command": status_command,
        }
    if status["review"].get("review_mode") == INIT.DEFERRED_REVIEW_MODE:
        return {
            "action": "commit_section",
            "reason": "逐节语义复核已延后到最终全文合同，当前节可直接执行确定性提交",
            "next_command": run_command,
            "status_command": status_command,
        }
    if status["sidecar"]["status"] == "missing":
        return {
            "action": "prepare_manual_sidecar",
            "reason": "当前回执采用人工侧车模式，但侧车不存在",
            "next_command": status_command,
            "status_command": status_command,
        }
    if status["sidecar"]["status"] == "consumed":
        return {
            "action": "review_already_consumed",
            "reason": "人工侧车已消费；若当前节仍未 passed，先检查 commit-section 失败原因或重新 reopen-section",
            "next_command": status_command,
            "status_command": status_command,
        }
    pending_items = int(status["sidecar"].get("pending_items") or 0)
    if pending_items > 0:
        return {
            "action": "complete_manual_sidecar",
            "reason": "逐节人工侧车仍有未补完字段，先完成当前模型回填",
            "next_command": status_command,
            "status_command": status_command,
        }
    if status["sidecar"].get("preflight_error"):
        return {
            "action": "fix_manual_sidecar_specificity",
            "reason": str(status["sidecar"]["preflight_error"]),
            "next_command": status_command,
            "status_command": status_command,
        }
    return {
        "action": "commit_section",
        "reason": "逐节人工侧车已补完，下一步直接 commit-section --sidecar 提交本节",
        "next_command": run_command,
        "status_command": status_command,
    }


def run_section_review_cycle(
    *,
    project: str,
    project_dir: Path,
    section: int,
    state: Path | None,
    staged: Path | None,
    review: Path | None,
    sidecar: Path | None,
    context_output: Path | None,
) -> dict[str, Any]:
    suggestion = suggest_next_step(
        project=project,
        project_dir=project_dir,
        section=section,
        state=state,
        staged=staged,
        review=review,
        sidecar=sidecar,
        context_output=context_output,
    )
    if suggestion["action"] in {
        "start_section_first",
        "complete_manual_sidecar",
        "fix_manual_sidecar_specificity",
        "enter_next_section_or_finalize",
        "review_already_consumed",
        "prepare_manual_sidecar",
    }:
        return suggestion
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        section=section,
        state=state,
        staged=staged,
        review=review,
        sidecar=sidecar,
        context_output=context_output,
    )
    if suggestion["action"] == "prepare_section_review":
        errors, summary = prepare_section_review(
            project=project,
            project_dir=project_dir,
            section=section,
            state=paths["state"],
            staged=paths["staged"],
            review=paths["review"],
            sidecar=paths["sidecar"],
            context_output=paths["context_output"],
        )
        result: dict[str, Any] = {
            "action": suggestion["action"],
            "reason": suggestion["reason"],
            "status_command": suggestion["status_command"],
        }
        if errors:
            result["errors"] = errors
        else:
            result["summary"] = summary
        return result
    try:
        review_payload = load_json(paths["review"], "逐节回执")
        deferred = (
            (review_payload.get("review_scaffold") or {}).get("review_mode")
            == INIT.DEFERRED_REVIEW_MODE
        )
        sidecar_sha = ""
        if not deferred:
            MANAGE.apply_template(
                paths["review"],
                paths["staged"],
                paths["sidecar"],
                write=False,
            )
            sidecar_sha = MANAGE.sha256_file(paths["sidecar"])
        command_output = io.StringIO()
        with redirect_stdout(command_output):
            code = STATE.command_validate(
                argparse.Namespace(
                    state=str(paths["state"]),
                    section=section,
                    staged=str(paths["staged"]),
                    review=str(paths["review"]),
                    sidecar=None if deferred else str(paths["sidecar"]),
                )
            )
        stdout_text = command_output.getvalue()
        if code != 0:
            return {
                "action": suggestion["action"],
                "reason": suggestion["reason"],
                "errors": [line for line in stdout_text.splitlines() if line.strip()],
                "status_command": suggestion["status_command"],
            }
        if not deferred:
            SIDE.consume_sidecar(
                paths["sidecar"],
                input_sha256=sidecar_sha,
                receipt_path=paths["review"],
                receipt_sha256=MANAGE.sha256_file(paths["review"]),
                operation="section-review.commit",
                counts={"section": section},
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "action": suggestion["action"],
            "reason": suggestion["reason"],
            "errors": [str(exc)],
            "status_command": suggestion["status_command"],
        }
    final_status = inspect_section_review_status(
        project=project,
        project_dir=project_dir,
        section=section,
        state=paths["state"],
        staged=paths["staged"],
        review=paths["review"],
        sidecar=paths["sidecar"],
        context_output=paths["context_output"],
    )
    return {
        "action": suggestion["action"],
        "reason": suggestion["reason"],
        "final_section_status": final_status["section_status"],
        "review_final_status": final_status["review"]["final_status"],
        "status_command": suggestion["status_command"],
    }


def emit_shell_template(
    *,
    project: str,
    project_dir: Path,
    section: int,
    state: Path | None,
    staged: Path | None,
    review: Path | None,
    sidecar: Path | None,
    context_output: Path | None,
) -> str:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        section=section,
        state=state,
        staged=staged,
        review=review,
        sidecar=sidecar,
        context_output=context_output,
    )
    return "\n".join(
        [
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" prepare-section-review \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --section {section}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" status \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --section {section}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" preflight-section-review \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --section {section}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" next-step \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --section {section}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_section_review_cycle.py" run-section-review-cycle \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --section {section}",
        ]
    )


def _print_status(status: dict[str, Any]) -> None:
    print("batch_section_review_cycle: status")
    print(f"project: {status['project']}")
    print(f"project_dir: {status['project_dir']}")
    print(f"section: {status['section']}")
    print(f"state: {status['state']}")
    print(f"section_status: {status['section_status']}")
    print(f"current_section: {status['current_section']}")
    print(f"staged_exists: {status['staged_exists']}")
    print(f"review: status={status['review']['status']} path={status['review']['path']}")
    print(f"review_final_status: {status['review']['final_status']}")
    print(f"sidecar: status={status['sidecar']['status']} path={status['sidecar']['path']}")
    if "pending_items" in status["sidecar"]:
        print(f"sidecar_pending_items: {status['sidecar']['pending_items']}/{status['sidecar']['total_items']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="High-level wrapper for per-section review sidecar workflow."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "prepare-section-review",
        "preflight-section-review",
        "status",
        "next-step",
        "run-section-review-cycle",
        "emit-shell-template",
    ):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--project-dir", required=True)
        command.add_argument("--section", type=int, required=True)
        command.add_argument("--state")
        command.add_argument("--staged")
        command.add_argument("--review")
        command.add_argument("--sidecar")
        command.add_argument("--context-output")
    args = parser.parse_args()
    common_kwargs = {
        "project": args.project,
        "project_dir": Path(args.project_dir).resolve(),
        "section": args.section,
        "state": Path(args.state).resolve() if args.state else None,
        "staged": Path(args.staged).resolve() if args.staged else None,
        "review": Path(args.review).resolve() if args.review else None,
        "sidecar": Path(args.sidecar).resolve() if args.sidecar else None,
        "context_output": Path(args.context_output).resolve() if args.context_output else None,
    }
    if args.command == "prepare-section-review":
        errors, summary = prepare_section_review(**common_kwargs)
        if errors:
            print("batch_section_review_cycle: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_section_review_cycle: prepared")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "status":
        try:
            status = inspect_section_review_status(**common_kwargs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_section_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        _print_status(status)
        return 0
    if args.command == "preflight-section-review":
        paths = default_paths(**common_kwargs)
        try:
            review_payload = load_json(paths["review"], "逐节回执")
            if (
                (review_payload.get("review_scaffold") or {}).get("review_mode")
                == INIT.DEFERRED_REVIEW_MODE
            ):
                state_payload = STATE.load_json(paths["state"])
                errors = STATE.validate_deferred_section_review_bindings(
                    review_payload,
                    state_payload,
                    STATE.get_section_state(state_payload, str(args.section)),
                    paths["staged"],
                    paths["state"],
                )
                if errors:
                    raise ValueError("\n- ".join(errors))
            else:
                MANAGE.apply_template(
                    paths["review"],
                    paths["staged"],
                    paths["sidecar"],
                    write=False,
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_section_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        print("batch_section_review_cycle: preflight_passed")
        print("formal_receipt_modified: false")
        print("semantic_fields_generated: 0")
        return 0
    if args.command == "next-step":
        try:
            suggestion = suggest_next_step(**common_kwargs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_section_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        print("batch_section_review_cycle: next-step")
        print(f"action: {suggestion['action']}")
        print(f"reason: {suggestion['reason']}")
        if suggestion["next_command"]:
            print(f"next_command: {suggestion['next_command']}")
        return 0
    if args.command == "run-section-review-cycle":
        result = run_section_review_cycle(**common_kwargs)
        print(f"batch_section_review_cycle: {result['action']}")
        print(f"reason: {result['reason']}")
        if result.get("errors"):
            for item in result["errors"]:
                print(f"- {item}")
            return 2
        if result.get("summary"):
            for key, value in result["summary"].items():
                print(f"{key}: {value}")
        if result.get("next_command"):
            print(f"next_command: {result['next_command']}")
        if "final_section_status" in result:
            print(f"final_section_status: {result['final_section_status']}")
            print(f"review_final_status: {result['review_final_status']}")
        return 0
    print(emit_shell_template(**common_kwargs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
