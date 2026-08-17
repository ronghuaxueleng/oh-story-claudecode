#!/usr/bin/env python3
"""Batch entry for outline-release receipts."""

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


RULE_LEDGER = _load_module(
    "validate_rule_execution_ledger.py",
    "story_short_write_rule_execution_ledger",
)
SEQUENCE = _load_module(
    "validate_sequence_contract.py",
    "story_short_write_sequence_contract",
)
OPENING = _load_module(
    "validate_opening_contract.py",
    "story_short_write_opening_contract",
)
OUTLINE = _load_module(
    "validate_outline_performance_contract.py",
    "story_short_write_outline_performance_contract",
)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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


def _quote_shell(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _join_shell_flags(flag: str, values: list[Path]) -> str:
    return " ".join(f"{flag} {_quote_shell(str(path))}" for path in values)


def _ensure_writable(path: Path, force: bool, label: str, errors: list[str]) -> None:
    if path.exists() and not force:
        errors.append(f"{label}已存在，拒绝覆盖: {path}")


def _source_roots_from_receipt(source_receipt: Path) -> list[Path]:
    payload = load_json(source_receipt, "拆文读取回执")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("拆文读取回执缺少已绑定 sources，无法推导纲前放行来源路径")
    roots: list[Path] = []
    for index, item in enumerate(sources, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"拆文读取回执 sources[{index - 1}] 必须是对象")
        root_text = str(item.get("root") or "").strip()
        if not root_text:
            raise ValueError(f"拆文读取回执 sources[{index - 1}].root 不能为空")
        roots.append(Path(root_text).expanduser().resolve())
    return roots


def _derive_source_originals(source_roots: list[Path]) -> list[Path]:
    originals: list[Path] = []
    for root in source_roots:
        originals.append((root / "原文" / f"{root.name}.txt").resolve())
    return originals


def default_outline_release_paths(
    *,
    project: str,
    project_dir: Path,
    source_receipt: Path | None = None,
    source_originals: list[Path] | None = None,
    opening_source: Path | None = None,
    export_model_review_output: Path | None = None,
    export_model_plan_output: Path | None = None,
) -> dict[str, Any]:
    resolved_project_dir = project_dir.expanduser().resolve()
    resolved_source_receipt = (
        source_receipt.expanduser().resolve()
        if source_receipt is not None
        else (resolved_project_dir / "写作资产" / "拆文读取回执.json").resolve()
    )
    source_roots = _source_roots_from_receipt(resolved_source_receipt)
    resolved_opening_source = (
        opening_source.expanduser().resolve()
        if opening_source is not None
        else (source_roots[0] / "可直接仿写_导语拆解表.md").resolve()
    )
    resolved_source_originals = (
        [path.expanduser().resolve() for path in source_originals]
        if source_originals
        else _derive_source_originals(source_roots)
    )
    writing_assets = (resolved_project_dir / "写作资产").resolve()
    return {
        "project": project,
        "project_dir": resolved_project_dir,
        "writing_receipt": (writing_assets / "写作规则读取回执.json").resolve(),
        "source_receipt": resolved_source_receipt,
        "ledger": (writing_assets / "规则执行台账.json").resolve(),
        "setting": (resolved_project_dir / "设定.md").resolve(),
        "outline": (resolved_project_dir / "小节大纲.md").resolve(),
        "setting_sequence_receipt": (writing_assets / "设定顺序契约回执.json").resolve(),
        "sequence_receipt": (writing_assets / "顺序契约回执.json").resolve(),
        "opening_source": resolved_opening_source,
        "opening_receipt": (writing_assets / "开头承重契约回执_大纲.json").resolve(),
        "outline_receipt": (writing_assets / "细纲表演验收回执.json").resolve(),
        "source_originals": resolved_source_originals,
        "source_roots": source_roots,
        "model_review_output": (
            export_model_review_output.expanduser().resolve()
            if export_model_review_output is not None
            else (writing_assets / "规则模型分类批次.json").resolve()
        ),
        "model_plan_output": (
            export_model_plan_output.expanduser().resolve()
            if export_model_plan_output is not None
            else (writing_assets / "规则模型归并计划.json").resolve()
        ),
    }


def init_batch(
    *,
    project: str,
    writing_receipt: Path,
    source_receipt: Path,
    ledger: Path,
    setting: Path,
    outline: Path,
    setting_sequence_receipt: Path,
    sequence_receipt: Path,
    opening_source: Path,
    opening_receipt: Path,
    outline_receipt: Path,
    source_originals: list[Path],
    force_ledger: bool,
    force_setting_sequence: bool,
    force_sequence: bool,
    force_opening: bool,
    force_outline_receipt: bool,
    export_model_review_output: Path | None,
    export_model_plan_output: Path | None,
    export_batch_size: int,
    resume_existing: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if export_batch_size < 1:
        errors.append("export-batch-size 必须大于 0")
    if export_model_plan_output is not None and export_model_review_output is None:
        errors.append("导出模型归并计划骨架时必须同时提供 export-model-review-output")

    if not resume_existing:
        _ensure_writable(ledger, force_ledger, "规则执行台账", errors)
        _ensure_writable(
            setting_sequence_receipt,
            force_setting_sequence,
            "设定顺序契约回执",
            errors,
        )
        _ensure_writable(
            sequence_receipt,
            force_sequence,
            "完整顺序契约回执",
            errors,
        )
        _ensure_writable(opening_receipt, force_opening, "开头契约回执", errors)
        _ensure_writable(
            outline_receipt,
            force_outline_receipt,
            "细纲表演验收回执",
            errors,
        )

    if ledger.is_file() and resume_existing and not force_ledger:
        ledger_payload = load_json(ledger, "规则执行台账")
    else:
        ledger_payload, ledger_errors = RULE_LEDGER.create_ledger(
            project,
            writing_receipt,
            source_receipt,
            extra_skill_rule_files=[],
        )
        errors.extend(ledger_errors)

    if opening_receipt.is_file() and resume_existing and not force_opening:
        opening_payload = load_json(opening_receipt, "开头契约回执")
    else:
        try:
            opening_payload = OPENING.create_receipt(
                project,
                opening_source,
                outline,
                "outline",
            )
        except FileNotFoundError as exc:
            errors.append(str(exc))
            opening_payload = None

    if outline_receipt.is_file() and resume_existing and not force_outline_receipt:
        outline_payload = load_json(outline_receipt, "细纲表演验收回执")
    else:
        try:
            outline_payload = OUTLINE.create_receipt(
                project,
                outline,
                source_originals,
                source_mode="full_bridge",
            )
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
            outline_payload = None

    if errors:
        return errors, {
            "ledger_entries": len(ledger_payload.get("skill_rules", [])),
            "opening_ready": opening_payload is not None,
            "outline_ready": outline_payload is not None,
        }

    if ledger.exists() and force_ledger:
        ledger.unlink()
    if setting_sequence_receipt.exists() and force_setting_sequence:
        setting_sequence_receipt.unlink()
    if sequence_receipt.exists() and force_sequence:
        sequence_receipt.unlink()
    if opening_receipt.exists() and force_opening:
        opening_receipt.unlink()
    if outline_receipt.exists() and force_outline_receipt:
        outline_receipt.unlink()

    if not ledger.exists():
        write_json(ledger, ledger_payload)
    if not setting_sequence_receipt.exists():
        SEQUENCE.init_setting_receipt(project, setting, setting_sequence_receipt)
    if not sequence_receipt.exists():
        SEQUENCE.init_receipt(project, setting, outline, None, sequence_receipt)
    if not opening_receipt.exists():
        write_json(opening_receipt, opening_payload)
    if not outline_receipt.exists():
        write_json(outline_receipt, outline_payload)

    summary: dict[str, Any] = {
        "skill_rules": len(ledger_payload["skill_rules"]),
        "source_assets": len(ledger_payload["source_assets"]),
        "asset_rules": sum(len(item["rules"]) for item in ledger_payload["source_assets"]),
        "setting_sequence_receipt": str(setting_sequence_receipt),
        "sequence_receipt": str(sequence_receipt),
        "opening_receipt": str(opening_receipt),
        "outline_receipt": str(outline_receipt),
    }
    if export_model_review_output is not None:
        export_summary = RULE_LEDGER.export_model_review(
            ledger,
            export_model_review_output,
            export_batch_size,
        )
        summary["model_review_output"] = str(export_model_review_output)
        summary["model_review_entries"] = export_summary["entries"]
        summary["model_review_batches"] = export_summary["batches"]
        if export_model_plan_output is not None:
            plan_summary = RULE_LEDGER.export_model_group_plan_template(
                ledger,
                export_model_review_output,
                export_model_plan_output,
            )
            summary["model_plan_output"] = str(export_model_plan_output)
            summary["model_plan_groups"] = plan_summary["groups"]
    return [], summary


def inspect_outline_release_status(
    *,
    project: str,
    project_dir: Path,
    source_receipt: Path | None = None,
    source_originals: list[Path] | None = None,
    opening_source: Path | None = None,
) -> dict[str, Any]:
    paths = default_outline_release_paths(
        project=project,
        project_dir=project_dir,
        source_receipt=source_receipt,
        source_originals=source_originals,
        opening_source=opening_source,
    )

    writing_data = load_json(paths["writing_receipt"], "写作规则读取回执")
    source_data = load_json(paths["source_receipt"], "拆文读取回执")
    status = {
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "writing_receipt": str(paths["writing_receipt"]),
        "source_receipt": str(paths["source_receipt"]),
        "writing_gate_status": str(writing_data.get("gate_status") or "unknown"),
        "source_gate_status": str(source_data.get("gate_status") or "unknown"),
        "source_roots": [str(path) for path in paths["source_roots"]],
        "source_originals": [str(path) for path in paths["source_originals"]],
        "opening_source": str(paths["opening_source"]),
        "required_inputs": {
            "setting_exists": paths["setting"].is_file(),
            "outline_exists": paths["outline"].is_file(),
            "opening_source_exists": paths["opening_source"].is_file(),
            "source_originals_exist": all(path.is_file() for path in paths["source_originals"]),
        },
        "artifacts": {
            "ledger": {
                "path": str(paths["ledger"]),
                "exists": paths["ledger"].is_file(),
                "gate_status": (
                    str(load_json(paths["ledger"], "规则执行台账").get("gate_status") or "unknown")
                    if paths["ledger"].is_file()
                    else "missing"
                ),
            },
            "setting_sequence_receipt": {
                "path": str(paths["setting_sequence_receipt"]),
                "exists": paths["setting_sequence_receipt"].is_file(),
                "status": (
                    str(load_json(paths["setting_sequence_receipt"], "设定顺序契约回执").get("status") or "unknown")
                    if paths["setting_sequence_receipt"].is_file()
                    else "missing"
                ),
                "gate_status": (
                    str(load_json(paths["setting_sequence_receipt"], "设定顺序契约回执").get("gate_status") or "unknown")
                    if paths["setting_sequence_receipt"].is_file()
                    else "missing"
                ),
            },
            "sequence_receipt": {
                "path": str(paths["sequence_receipt"]),
                "exists": paths["sequence_receipt"].is_file(),
                "status": (
                    str(load_json(paths["sequence_receipt"], "顺序契约回执").get("status") or "unknown")
                    if paths["sequence_receipt"].is_file()
                    else "missing"
                ),
                "gate_status": (
                    str(load_json(paths["sequence_receipt"], "顺序契约回执").get("gate_status") or "unknown")
                    if paths["sequence_receipt"].is_file()
                    else "missing"
                ),
            },
            "opening_receipt": {
                "path": str(paths["opening_receipt"]),
                "exists": paths["opening_receipt"].is_file(),
                "gate_status": (
                    str(load_json(paths["opening_receipt"], "开头承重契约回执").get("gate_status") or "unknown")
                    if paths["opening_receipt"].is_file()
                    else "missing"
                ),
            },
            "outline_receipt": {
                "path": str(paths["outline_receipt"]),
                "exists": paths["outline_receipt"].is_file(),
                "gate_status": (
                    str(load_json(paths["outline_receipt"], "细纲表演验收回执").get("gate_status") or "unknown")
                    if paths["outline_receipt"].is_file()
                    else "missing"
                ),
            },
            "model_review_output": {
                "path": str(paths["model_review_output"]),
                "exists": paths["model_review_output"].is_file(),
            },
            "model_plan_output": {
                "path": str(paths["model_plan_output"]),
                "exists": paths["model_plan_output"].is_file(),
            },
        },
    }
    status["initialized"] = all(
        status["artifacts"][key]["exists"]
        for key in (
            "ledger",
            "setting_sequence_receipt",
            "sequence_receipt",
            "opening_receipt",
            "outline_receipt",
            "model_review_output",
            "model_plan_output",
        )
    )
    return status


def suggest_next_step(
    *,
    project: str,
    project_dir: Path,
    source_receipt: Path | None = None,
    source_originals: list[Path] | None = None,
    opening_source: Path | None = None,
    export_batch_size: int,
) -> dict[str, Any]:
    status = inspect_outline_release_status(
        project=project,
        project_dir=project_dir,
        source_receipt=source_receipt,
        source_originals=source_originals,
        opening_source=opening_source,
    )
    paths = default_outline_release_paths(
        project=project,
        project_dir=project_dir,
        source_receipt=source_receipt,
        source_originals=source_originals,
        opening_source=opening_source,
    )

    status_command = (
        'python3 "$SKILL_ROOT/scripts/batch_outline_release.py" status '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    if source_receipt is not None:
        status_command += f' --source-receipt {_quote_shell(str(paths["source_receipt"]))}'
    if opening_source is not None:
        status_command += f' --opening-source {_quote_shell(str(paths["opening_source"]))}'
    if source_originals:
        status_command += " " + _join_shell_flags("--source-original", paths["source_originals"])

    start_command = (
        'python3 "$SKILL_ROOT/scripts/batch_outline_release.py" start-outline-release '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))} '
        f'--export-batch-size {export_batch_size}'
    )
    if source_receipt is not None:
        start_command += f' --source-receipt {_quote_shell(str(paths["source_receipt"]))}'
    if opening_source is not None:
        start_command += f' --opening-source {_quote_shell(str(paths["opening_source"]))}'
    if source_originals:
        start_command += " " + _join_shell_flags("--source-original", paths["source_originals"])

    if status["writing_gate_status"] != "passed" or status["source_gate_status"] != "passed":
        return {
            "action": "complete_read_gates",
            "reason": "两道读取门禁尚未全部 passed，不能初始化纲前放行骨架",
            "next_command": status_command,
        }
    if not status["required_inputs"]["setting_exists"] or not status["required_inputs"]["outline_exists"]:
        return {
            "action": "create_setting_and_outline",
            "reason": "设定.md 或 小节大纲.md 仍不存在，先完成设定与细纲文件再初始化纲前放行骨架",
            "next_command": "",
        }
    if not status["required_inputs"]["opening_source_exists"] or not status["required_inputs"]["source_originals_exist"]:
        return {
            "action": "repair_source_paths",
            "reason": "主体导语资产或原文路径缺失，必须先修正来源路径绑定",
            "next_command": status_command,
        }
    if not status["initialized"]:
        return {
            "action": "start_outline_release",
            "reason": "纲前放行骨架尚未初始化，下一步直接执行高层总入口",
            "next_command": start_command,
        }
    return {
        "action": "enter_manual_outline_review",
        "reason": "纲前放行骨架已生成，继续人工填写台账、顺序契约、开头契约和细纲表演验收回执",
        "next_command": "",
    }


def emit_shell_template(
    *,
    project: str,
    project_dir: Path,
    source_receipt: Path | None,
    source_originals: list[Path] | None,
    opening_source: Path | None,
    export_batch_size: int,
) -> str:
    paths = default_outline_release_paths(
        project=project,
        project_dir=project_dir,
        source_receipt=source_receipt,
        source_originals=source_originals,
        opening_source=opening_source,
    )
    source_original_flags = _join_shell_flags("--source-original", paths["source_originals"])
    lines = [
        'python3 "$SKILL_ROOT/scripts/batch_outline_release.py" status \\',
        f"  --project {_quote_shell(project)} \\",
        f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
    ]
    if source_receipt is not None:
        lines.append(f"  --source-receipt {_quote_shell(str(paths['source_receipt']))} \\")
    if opening_source is not None:
        lines.append(f"  --opening-source {_quote_shell(str(paths['opening_source']))} \\")
    if source_original_flags:
        lines.append(f"  {source_original_flags}")
    else:
        lines[-1] = lines[-1].rstrip(" \\")

    lines.extend(
        [
            "",
            'python3 "$SKILL_ROOT/scripts/batch_outline_release.py" next-step \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --export-batch-size {export_batch_size} \\",
        ]
    )
    if source_receipt is not None:
        lines.append(f"  --source-receipt {_quote_shell(str(paths['source_receipt']))} \\")
    if opening_source is not None:
        lines.append(f"  --opening-source {_quote_shell(str(paths['opening_source']))} \\")
    if source_original_flags:
        lines.append(f"  {source_original_flags}")
    else:
        lines[-1] = lines[-1].rstrip(" \\")

    lines.extend(
        [
            "",
            'python3 "$SKILL_ROOT/scripts/batch_outline_release.py" start-outline-release \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))} \\",
            f"  --export-batch-size {export_batch_size} \\",
        ]
    )
    if source_receipt is not None:
        lines.append(f"  --source-receipt {_quote_shell(str(paths['source_receipt']))} \\")
    if opening_source is not None:
        lines.append(f"  --opening-source {_quote_shell(str(paths['opening_source']))} \\")
    lines.append(f"  --export-model-review-output {_quote_shell(str(paths['model_review_output']))} \\")
    lines.append(f"  --export-model-plan-output {_quote_shell(str(paths['model_plan_output']))} \\")
    if source_original_flags:
        lines.append(f"  {source_original_flags}")
    else:
        lines[-1] = lines[-1].rstrip(" \\")
    return "\n".join(lines)


def start_outline_release(
    *,
    project: str,
    project_dir: Path,
    source_receipt: Path | None,
    source_originals: list[Path] | None,
    opening_source: Path | None,
    force_ledger: bool,
    force_setting_sequence: bool,
    force_sequence: bool,
    force_opening: bool,
    force_outline_receipt: bool,
    export_model_review_output: Path | None,
    export_model_plan_output: Path | None,
    export_batch_size: int,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_outline_release_paths(
        project=project,
        project_dir=project_dir,
        source_receipt=source_receipt,
        source_originals=source_originals,
        opening_source=opening_source,
        export_model_review_output=export_model_review_output,
        export_model_plan_output=export_model_plan_output,
    )
    return init_batch(
        project=project,
        writing_receipt=paths["writing_receipt"],
        source_receipt=paths["source_receipt"],
        ledger=paths["ledger"],
        setting=paths["setting"],
        outline=paths["outline"],
        setting_sequence_receipt=paths["setting_sequence_receipt"],
        sequence_receipt=paths["sequence_receipt"],
        opening_source=paths["opening_source"],
        opening_receipt=paths["opening_receipt"],
        outline_receipt=paths["outline_receipt"],
        source_originals=paths["source_originals"],
        force_ledger=force_ledger,
        force_setting_sequence=force_setting_sequence,
        force_sequence=force_sequence,
        force_opening=force_opening,
        force_outline_receipt=force_outline_receipt,
        export_model_review_output=paths["model_review_output"],
        export_model_plan_output=paths["model_plan_output"],
        export_batch_size=export_batch_size,
        resume_existing=True,
    )


def _print_status_summary(status: dict[str, Any]) -> None:
    print("batch_outline_release: status")
    print(f"project: {status['project']}")
    print(f"project_dir: {status['project_dir']}")
    print(f"writing_gate_status: {status['writing_gate_status']}")
    print(f"source_gate_status: {status['source_gate_status']}")
    print(f"initialized: {status['initialized']}")
    print(
        "required_inputs: "
        f"setting={status['required_inputs']['setting_exists']} "
        f"outline={status['required_inputs']['outline_exists']} "
        f"opening_source={status['required_inputs']['opening_source_exists']} "
        f"source_originals={status['required_inputs']['source_originals_exist']}"
    )
    for key, value in status["artifacts"].items():
        suffix = []
        if "status" in value:
            suffix.append(f"status={value['status']}")
        if "gate_status" in value:
            suffix.append(f"gate_status={value['gate_status']}")
        suffix_text = ("; " + ", ".join(suffix)) if suffix else ""
        print(f"{key}: exists={value['exists']} path={value['path']}{suffix_text}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch initializer and high-level helpers for outline-release receipts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--writing-receipt", required=True)
    init.add_argument("--source-receipt", required=True)
    init.add_argument("--ledger", required=True)
    init.add_argument("--setting", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--setting-sequence-receipt", required=True)
    init.add_argument("--sequence-receipt", required=True)
    init.add_argument("--opening-source", required=True)
    init.add_argument("--opening-receipt", required=True)
    init.add_argument("--outline-receipt", required=True)
    init.add_argument("--source-original", action="append", required=True)
    init.add_argument("--force-ledger", action="store_true")
    init.add_argument("--force-setting-sequence", action="store_true")
    init.add_argument("--force-sequence", action="store_true")
    init.add_argument("--force-opening", action="store_true")
    init.add_argument("--force-outline-receipt", action="store_true")
    init.add_argument("--export-model-review-output")
    init.add_argument("--export-model-plan-output")
    init.add_argument("--export-batch-size", type=int, default=30)

    for name in ("status", "next-step", "emit-shell-template", "start-outline-release"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--project-dir", required=True)
        command.add_argument("--source-receipt")
        command.add_argument("--opening-source")
        command.add_argument("--source-original", action="append")
        if name in {"next-step", "emit-shell-template", "start-outline-release"}:
            command.add_argument("--export-batch-size", type=int, default=30)
        if name == "start-outline-release":
            command.add_argument("--force-ledger", action="store_true")
            command.add_argument("--force-setting-sequence", action="store_true")
            command.add_argument("--force-sequence", action="store_true")
            command.add_argument("--force-opening", action="store_true")
            command.add_argument("--force-outline-receipt", action="store_true")
            command.add_argument("--export-model-review-output")
            command.add_argument("--export-model-plan-output")

    args = parser.parse_args()

    if args.command == "init":
        errors, summary = init_batch(
            project=args.project,
            writing_receipt=Path(args.writing_receipt).resolve(),
            source_receipt=Path(args.source_receipt).resolve(),
            ledger=Path(args.ledger).resolve(),
            setting=Path(args.setting).resolve(),
            outline=Path(args.outline).resolve(),
            setting_sequence_receipt=Path(args.setting_sequence_receipt).resolve(),
            sequence_receipt=Path(args.sequence_receipt).resolve(),
            opening_source=Path(args.opening_source).resolve(),
            opening_receipt=Path(args.opening_receipt).resolve(),
            outline_receipt=Path(args.outline_receipt).resolve(),
            source_originals=[Path(value).resolve() for value in args.source_original],
            force_ledger=bool(args.force_ledger),
            force_setting_sequence=bool(args.force_setting_sequence),
            force_sequence=bool(args.force_sequence),
            force_opening=bool(args.force_opening),
            force_outline_receipt=bool(args.force_outline_receipt),
            export_model_review_output=(
                Path(args.export_model_review_output).resolve()
                if args.export_model_review_output
                else None
            ),
            export_model_plan_output=(
                Path(args.export_model_plan_output).resolve()
                if args.export_model_plan_output
                else None
            ),
            export_batch_size=args.export_batch_size,
            resume_existing=False,
        )
        if errors:
            print("batch_outline_release: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_outline_release: initialized")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0

    common_kwargs = {
        "project": args.project,
        "project_dir": Path(args.project_dir).resolve(),
        "source_receipt": Path(args.source_receipt).resolve() if args.source_receipt else None,
        "opening_source": Path(args.opening_source).resolve() if args.opening_source else None,
        "source_originals": [Path(value).resolve() for value in args.source_original]
        if getattr(args, "source_original", None)
        else None,
    }

    if args.command == "status":
        try:
            status = inspect_outline_release_status(**common_kwargs)
        except (FileNotFoundError, ValueError) as exc:
            print("batch_outline_release: blocked")
            print(f"- {exc}")
            return 2
        _print_status_summary(status)
        return 0

    if args.command == "next-step":
        try:
            suggestion = suggest_next_step(
                **common_kwargs,
                export_batch_size=args.export_batch_size,
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_outline_release: blocked")
            print(f"- {exc}")
            return 2
        print("batch_outline_release: next-step")
        print(f"action: {suggestion['action']}")
        print(f"reason: {suggestion['reason']}")
        if suggestion["next_command"]:
            print(f"next_command: {suggestion['next_command']}")
        return 0

    if args.command == "emit-shell-template":
        try:
            print(
                emit_shell_template(
                    **common_kwargs,
                    export_batch_size=args.export_batch_size,
                )
            )
        except (FileNotFoundError, ValueError) as exc:
            print("batch_outline_release: blocked")
            print(f"- {exc}")
            return 2
        return 0

    if args.command == "start-outline-release":
        errors, summary = start_outline_release(
            **common_kwargs,
            force_ledger=bool(args.force_ledger),
            force_setting_sequence=bool(args.force_setting_sequence),
            force_sequence=bool(args.force_sequence),
            force_opening=bool(args.force_opening),
            force_outline_receipt=bool(args.force_outline_receipt),
            export_model_review_output=(
                Path(args.export_model_review_output).resolve()
                if args.export_model_review_output
                else None
            ),
            export_model_plan_output=(
                Path(args.export_model_plan_output).resolve()
                if args.export_model_plan_output
                else None
            ),
            export_batch_size=args.export_batch_size,
        )
        if errors:
            print("batch_outline_release: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_outline_release: initialized")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0

    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
