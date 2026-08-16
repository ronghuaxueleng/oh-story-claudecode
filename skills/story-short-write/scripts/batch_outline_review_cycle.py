#!/usr/bin/env python3
"""High-level wrapper for outline performance manual review sidecars."""

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


BRIDGE = _load_module(
    "manage_outline_bridge_review.py",
    "story_short_write_batch_outline_bridge_review",
)
SECTION = _load_module(
    "manage_outline_section_review.py",
    "story_short_write_batch_outline_section_review",
)
SIDE = _load_module(
    "sidecar_lifecycle.py",
    "story_short_write_batch_outline_sidecar_lifecycle",
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
    receipt: Path | None = None,
    outline: Path | None = None,
    bridge_review: Path | None = None,
    bridge_beat_review: Path | None = None,
    section_review: Path | None = None,
) -> dict[str, Any]:
    resolved_project_dir = project_dir.expanduser().resolve()
    assets = (resolved_project_dir / "写作资产").resolve()
    return {
        "project": project,
        "project_dir": resolved_project_dir,
        "receipt": (
            receipt.expanduser().resolve()
            if receipt is not None
            else (assets / "细纲表演验收回执.json").resolve()
        ),
        "outline": (
            outline.expanduser().resolve()
            if outline is not None
            else (resolved_project_dir / "小节大纲.md").resolve()
        ),
        "bridge_review": (
            bridge_review.expanduser().resolve()
            if bridge_review is not None
            else (assets / "桥级回填侧车.json").resolve()
        ),
        "bridge_beat_review": (
            bridge_beat_review.expanduser().resolve()
            if bridge_beat_review is not None
            else (assets / "桥级逐拍回填侧车.json").resolve()
        ),
        "section_review": (
            section_review.expanduser().resolve()
            if section_review is not None
            else (assets / "节级回填侧车.json").resolve()
        ),
    }


def prepare_outline_review(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None,
    outline: Path | None,
    bridge_review: Path | None,
    bridge_beat_review: Path | None,
    section_review: Path | None,
) -> tuple[list[str], dict[str, Any]]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    errors: list[str] = []
    if not paths["receipt"].is_file():
        errors.append(f"细纲表演验收回执不存在: {paths['receipt']}")
        return errors, {}
    try:
        sync_summary = BRIDGE.sync_source_emotions(paths["receipt"])
        bridge_payload = BRIDGE.export_template(paths["receipt"], paths["bridge_review"])
        beat_payload = BRIDGE.export_beat_template(paths["receipt"], paths["bridge_beat_review"])
        section_payload = SECTION.export_template(
            paths["receipt"],
            paths["section_review"],
            paths["outline"],
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        return errors, {}
    return [], {
        "receipt": str(paths["receipt"]),
        "bridge_review": str(paths["bridge_review"]),
        "bridge_review_bridges": len(bridge_payload.get("outline_bridge_flow_parity") or []),
        "bridge_beat_review": str(paths["bridge_beat_review"]),
        "bridge_beat_review_bridges": len(beat_payload.get("outline_bridge_flow_parity") or []),
        "section_review": str(paths["section_review"]),
        "section_review_sections": len(section_payload.get("sections") or []),
        "synced_outside_beats": sync_summary["outside_count"],
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


def _receipt_bridge_entries(receipt_payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    outside = receipt_payload.get("outside_bridge_plot_parity")
    if isinstance(outside, dict):
        entries.append(outside)
    entries.extend(
        item
        for item in receipt_payload.get("outline_bridge_flow_parity") or []
        if isinstance(item, dict)
    )
    return entries


def _nonempty_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value) and bool(value)


def _refresh_sidecar_receipt_sha(path: Path, current_sha: str, label: str) -> None:
    payload = load_json(path, label)
    payload["receipt_sha256"] = current_sha
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _bridge_manual_complete(entry: dict[str, Any]) -> bool:
    if not _nonempty_string_list(entry.get("target_outline_sections")):
        return False
    if not _nonempty_string_list(entry.get("target_outline_evidence")):
        return False
    for field in (
        "plot_granularity_parity_judgment",
        "emotion_parity_judgment",
        "adaptation_reason",
        "missing_or_weakened_risk",
        "manual_judgment",
    ):
        if not str(entry.get(field) or "").strip():
            return False
    if entry.get("reader_experience_parity") not in {True, False}:
        return False
    if str(entry.get("parity_status") or "").strip() not in {"matched", "adapted"}:
        return False
    return True


def _bridge_beat_complete(entry: dict[str, Any], *, outside: bool) -> bool:
    target_plot_beats = entry.get("target_plot_beats")
    if not isinstance(target_plot_beats, list):
        return False
    plot_beat_mapping = entry.get("plot_beat_mapping")
    if not isinstance(plot_beat_mapping, list):
        return False
    if outside:
        return True
    if not target_plot_beats or not plot_beat_mapping:
        return False
    for field in (
        "target_emotion_sequence",
        "source_reversal_beat",
        "target_reversal_beat",
        "source_peak_beat",
        "target_peak_beat",
    ):
        value = entry.get(field)
        if field == "target_emotion_sequence":
            if not isinstance(value, list) or not value:
                return False
        elif value in ("", None):
            return False
    return True


def _section_manual_complete(entry: dict[str, Any]) -> bool:
    for field in SECTION.SECTION_MANUAL_FIELDS:
        if field not in entry:
            return False
        value = entry.get(field)
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, list) and not value:
            if field == "character_missteps":
                continue
            return False
    return True


def _next_pending_bridge_beat_id(receipt_payload: dict[str, Any]) -> str | None:
    for item in receipt_payload.get("outline_bridge_flow_parity") or []:
        if isinstance(item, dict) and not _bridge_beat_complete(item, outside=False):
            bridge_id = str(item.get("source_bridge_id") or "").strip()
            if bridge_id:
                return bridge_id
    return None


def _next_pending_section_id(receipt_payload: dict[str, Any]) -> str | None:
    for item in receipt_payload.get("sections") or []:
        if isinstance(item, dict) and not _section_manual_complete(item):
            section_id = str(item.get("section_id") or "").strip()
            if section_id:
                return section_id
    return None


def export_next_compact_sidecar(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None,
    outline: Path | None,
    bridge_review: Path | None,
    bridge_beat_review: Path | None,
    section_review: Path | None,
    kind: str,
    output: Path,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    receipt_payload = load_json(paths["receipt"], "细纲表演验收回执")
    if kind == "bridge-beat":
        bridge_id = _next_pending_bridge_beat_id(receipt_payload)
        if not bridge_id:
            raise ValueError("桥级逐拍已全部补完，无下一个待补 bridge_id")
        payload = BRIDGE.export_beat_template(
            paths["receipt"],
            output.resolve(),
            [bridge_id],
            True,
        )
        return {
            "kind": kind,
            "target_id": bridge_id,
            "output": str(output.resolve()),
            "exported_entries": len(payload.get("outline_bridge_flow_parity") or []),
        }
    section_id = _next_pending_section_id(receipt_payload)
    if not section_id:
        raise ValueError("节级人工回填已全部补完，无下一个待补 section_id")
    payload = SECTION.export_template(
        paths["receipt"],
        output.resolve(),
        paths["outline"],
        [section_id],
        True,
    )
    return {
        "kind": kind,
        "target_id": section_id,
        "output": str(output.resolve()),
        "exported_entries": len(payload.get("sections") or []),
    }


def prepare_next_fill_pair(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None,
    outline: Path | None,
    bridge_review: Path | None,
    bridge_beat_review: Path | None,
    section_review: Path | None,
    bridge_output: Path,
    section_output: Path,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    receipt_payload = load_json(paths["receipt"], "细纲表演验收回执")
    bridge_id = _next_pending_bridge_beat_id(receipt_payload)
    section_id = _next_pending_section_id(receipt_payload)
    if not bridge_id and not section_id:
        raise ValueError("桥级逐拍与节级人工回填都已补完，无下一组成对侧车")
    if bridge_id:
        BRIDGE.export_beat_template(
            paths["receipt"],
            bridge_output.resolve(),
            [bridge_id],
            True,
        )
    if section_id:
        SECTION.export_template(
            paths["receipt"],
            section_output.resolve(),
            paths["outline"],
            [section_id],
            True,
        )
    return {
        "bridge_target_id": bridge_id or "",
        "bridge_output": str(bridge_output.resolve()) if bridge_id else "",
        "section_target_id": section_id or "",
        "section_output": str(section_output.resolve()) if section_id else "",
    }


def apply_fill_pair(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None,
    outline: Path | None,
    bridge_review: Path | None,
    bridge_beat_review: Path | None,
    section_review: Path | None,
    bridge_input: Path,
    section_input: Path,
    next_bridge_output: Path | None,
    next_section_output: Path | None,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    bridge_input_path = bridge_input.resolve()
    section_input_path = section_input.resolve()
    if not bridge_input_path.is_file():
        raise FileNotFoundError(f"桥级逐拍窄侧车不存在: {bridge_input_path}")
    if not section_input_path.is_file():
        raise FileNotFoundError(f"节级窄侧车不存在: {section_input_path}")
    BRIDGE.apply_beat_template(paths["receipt"], bridge_input_path)
    receipt_sha = BRIDGE.sha256_file(paths["receipt"])
    SIDE.refresh_sidecar_receipt_sha(section_input_path, receipt_sha)
    SECTION.apply_template(paths["receipt"], section_input_path)

    next_pair: dict[str, str] = {
        "bridge_target_id": "",
        "bridge_output": "",
        "section_target_id": "",
        "section_output": "",
    }
    if next_bridge_output is not None or next_section_output is not None:
        refreshed_receipt = load_json(paths["receipt"], "细纲表演验收回执")
        next_bridge_id = _next_pending_bridge_beat_id(refreshed_receipt)
        next_section_id = _next_pending_section_id(refreshed_receipt)
        if next_bridge_output is not None and next_bridge_id:
            BRIDGE.export_beat_template(
                paths["receipt"],
                next_bridge_output.resolve(),
                [next_bridge_id],
                True,
            )
            next_pair["bridge_target_id"] = next_bridge_id
            next_pair["bridge_output"] = str(next_bridge_output.resolve())
        if next_section_output is not None and next_section_id:
            SECTION.export_template(
                paths["receipt"],
                next_section_output.resolve(),
                paths["outline"],
                [next_section_id],
                True,
            )
            next_pair["section_target_id"] = next_section_id
            next_pair["section_output"] = str(next_section_output.resolve())
    return {
        "bridge_input": str(bridge_input_path),
        "section_input": str(section_input_path),
        **next_pair,
    }


def inspect_outline_review_status(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None = None,
    outline: Path | None = None,
    bridge_review: Path | None = None,
    bridge_beat_review: Path | None = None,
    section_review: Path | None = None,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    receipt_payload = load_json(paths["receipt"], "细纲表演验收回执")
    bridge_status = _sidecar_status(paths["bridge_review"], "桥级回填侧车")
    beat_status = _sidecar_status(paths["bridge_beat_review"], "桥级逐拍回填侧车")
    section_status = _sidecar_status(paths["section_review"], "节级回填侧车")
    status = {
        "project": project,
        "project_dir": str(paths["project_dir"]),
        "receipt": str(paths["receipt"]),
        "outline": str(paths["outline"]),
        "outline_exists": paths["outline"].is_file(),
        "receipt_gate_status": str(receipt_payload.get("gate_status") or "unknown"),
        "reviewed_by_current_model": receipt_payload.get("reviewed_by_current_model") is True,
        "bridge_review": bridge_status,
        "bridge_beat_review": beat_status,
        "section_review": section_status,
    }
    current_receipt_sha = BRIDGE.sha256_file(paths["receipt"])
    if bridge_status["status"] == "active":
        payload = bridge_status["payload"]
        entries = _receipt_bridge_entries(payload)
        status["bridge_review"]["receipt_sha256"] = str(payload.get("receipt_sha256") or "")
        status["bridge_review"]["stale"] = str(payload.get("receipt_sha256") or "") != current_receipt_sha
        status["bridge_review"]["pending_entries"] = sum(0 if _bridge_manual_complete(item) else 1 for item in entries)
        status["bridge_review"]["total_entries"] = len(entries)
    if beat_status["status"] == "active":
        payload = beat_status["payload"]
        entries = []
        outside = payload.get("outside_bridge_plot_parity")
        if isinstance(outside, dict):
            entries.append(("outside", outside))
        entries.extend(
            (str(item.get("source_bridge_id") or ""), item)
            for item in payload.get("outline_bridge_flow_parity") or []
            if isinstance(item, dict)
        )
        status["bridge_beat_review"]["receipt_sha256"] = str(payload.get("receipt_sha256") or "")
        status["bridge_beat_review"]["stale"] = str(payload.get("receipt_sha256") or "") != current_receipt_sha
        status["bridge_beat_review"]["pending_entries"] = sum(
            0 if _bridge_beat_complete(item, outside=(entry_id == "outside")) else 1
            for entry_id, item in entries
        )
        status["bridge_beat_review"]["total_entries"] = len(entries)
    if section_status["status"] == "active":
        payload = section_status["payload"]
        entries = [item for item in payload.get("sections") or [] if isinstance(item, dict)]
        status["section_review"]["receipt_sha256"] = str(payload.get("receipt_sha256") or "")
        status["section_review"]["stale"] = str(payload.get("receipt_sha256") or "") != current_receipt_sha
        status["section_review"]["pending_entries"] = sum(0 if _section_manual_complete(item) else 1 for item in entries)
        status["section_review"]["total_entries"] = len(entries)
    return status


def suggest_next_step(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None,
    outline: Path | None,
    bridge_review: Path | None,
    bridge_beat_review: Path | None,
    section_review: Path | None,
) -> dict[str, Any]:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    status = inspect_outline_review_status(
        project=project,
        project_dir=project_dir,
        receipt=paths["receipt"],
        outline=paths["outline"],
        bridge_review=paths["bridge_review"],
        bridge_beat_review=paths["bridge_beat_review"],
        section_review=paths["section_review"],
    )
    status_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_outline_review_cycle.py" status '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    prepare_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_outline_review_cycle.py" prepare-outline-review '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    run_command = (
        'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_outline_review_cycle.py" run-outline-review-cycle '
        f'--project {_quote_shell(project)} '
        f'--project-dir {_quote_shell(str(paths["project_dir"]))}'
    )
    if not status["outline_exists"]:
        return {
            "action": "repair_outline_path",
            "reason": "小节大纲.md 不存在，不能重绑细纲表演验收回执",
            "next_command": "",
            "status_command": status_command,
        }
    if any(
        status[key]["status"] == "missing"
        for key in ("bridge_review", "bridge_beat_review", "section_review")
    ):
        return {
            "action": "prepare_outline_review",
            "reason": "桥级/逐拍/节级人工侧车尚未全部导出，先准备正式人工载体",
            "next_command": prepare_command,
            "status_command": status_command,
        }
    if any(
        status[key]["status"] == "active" and status[key].get("stale") is True
        for key in ("bridge_review", "bridge_beat_review", "section_review")
    ):
        return {
            "action": "refresh_active_sidecars",
            "reason": "正式回执已经变化，当前 active 侧车至少有一份绑定旧 receipt_sha256，先重导出再继续人工或状态判断",
            "next_command": prepare_command,
            "status_command": status_command,
        }
    if any(
        status[key]["status"] == "active" and int(status[key].get("pending_entries") or 0) > 0
        for key in ("bridge_review", "bridge_beat_review", "section_review")
    ):
        return {
            "action": "complete_manual_sidecars",
            "reason": "桥级、逐拍或节级侧车仍有未补完的人工字段，先完成当前模型回填",
            "next_command": status_command,
            "status_command": status_command,
        }
    if all(status[key]["status"] == "consumed" for key in ("bridge_review", "bridge_beat_review", "section_review")):
        if status["receipt_gate_status"] == "passed" and status["reviewed_by_current_model"]:
            return {
                "action": "enter_prewrite_contracts",
                "reason": "细纲表演验收已封口通过，可以继续正文前合同阶段",
                "next_command": "",
                "status_command": status_command,
            }
        return {
            "action": "seal_review",
            "reason": "侧车已消费，但正式回执还未通过 seal-review，下一步补做重绑与封口",
            "next_command": run_command,
            "status_command": status_command,
        }
    return {
        "action": "apply_outline_review_sidecars",
        "reason": "三份侧车均已补完，下一步统一 apply、consume、rebind-outline 并 seal-review",
        "next_command": run_command,
        "status_command": status_command,
    }


def run_outline_review_cycle(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None,
    outline: Path | None,
    bridge_review: Path | None,
    bridge_beat_review: Path | None,
    section_review: Path | None,
) -> dict[str, Any]:
    suggestion = suggest_next_step(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    if suggestion["action"] in {
        "prepare_outline_review",
        "complete_manual_sidecars",
        "repair_outline_path",
        "enter_prewrite_contracts",
    }:
        return suggestion
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    try:
        if suggestion["action"] == "apply_outline_review_sidecars":
            bridge_sha = BRIDGE.sha256_file(paths["bridge_review"])
            beat_sha = BRIDGE.sha256_file(paths["bridge_beat_review"])
            section_sha = SECTION.sha256_file(paths["section_review"])
            BRIDGE.apply_template(paths["receipt"], paths["bridge_review"])
            receipt_sha = BRIDGE.sha256_file(paths["receipt"])
            _refresh_sidecar_receipt_sha(
                paths["bridge_beat_review"],
                receipt_sha,
                "桥级逐拍回填侧车",
            )
            _refresh_sidecar_receipt_sha(
                paths["section_review"],
                receipt_sha,
                "节级回填侧车",
            )
            BRIDGE.apply_beat_template(paths["receipt"], paths["bridge_beat_review"])
            receipt_sha = BRIDGE.sha256_file(paths["receipt"])
            _refresh_sidecar_receipt_sha(
                paths["section_review"],
                receipt_sha,
                "节级回填侧车",
            )
            SECTION.apply_template(paths["receipt"], paths["section_review"])
            receipt_sha = BRIDGE.sha256_file(paths["receipt"])
            SIDE.consume_sidecar(
                paths["bridge_review"],
                input_sha256=bridge_sha,
                receipt_path=paths["receipt"],
                receipt_sha256=receipt_sha,
                operation="outline-bridge-review.apply",
                counts={"bridges": len(load_json(paths["receipt"], "细纲表演验收回执").get("outline_bridge_flow_parity") or [])},
            )
            SIDE.consume_sidecar(
                paths["bridge_beat_review"],
                input_sha256=beat_sha,
                receipt_path=paths["receipt"],
                receipt_sha256=receipt_sha,
                operation="outline-bridge-beat-review.apply",
                counts={"bridges": len(load_json(paths["receipt"], "细纲表演验收回执").get("outline_bridge_flow_parity") or [])},
            )
            SIDE.consume_sidecar(
                paths["section_review"],
                input_sha256=section_sha,
                receipt_path=paths["receipt"],
                receipt_sha256=receipt_sha,
                operation="outline-section-review.apply",
                counts={"sections": len(load_json(paths["receipt"], "细纲表演验收回执").get("sections") or [])},
            )
        BRIDGE.rebind_outline(paths["receipt"], paths["outline"])
        BRIDGE.seal_review(paths["receipt"], paths["outline"])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "action": suggestion["action"],
            "reason": suggestion["reason"],
            "errors": [str(exc)],
            "status_command": suggestion["status_command"],
        }
    final_status = inspect_outline_review_status(
        project=project,
        project_dir=project_dir,
        receipt=paths["receipt"],
        outline=paths["outline"],
        bridge_review=paths["bridge_review"],
        bridge_beat_review=paths["bridge_beat_review"],
        section_review=paths["section_review"],
    )
    return {
        "action": suggestion["action"],
        "reason": suggestion["reason"],
        "status_command": suggestion["status_command"],
        "final_receipt_gate_status": final_status["receipt_gate_status"],
        "final_reviewed_by_current_model": final_status["reviewed_by_current_model"],
    }


def emit_shell_template(
    *,
    project: str,
    project_dir: Path,
    receipt: Path | None,
    outline: Path | None,
    bridge_review: Path | None,
    bridge_beat_review: Path | None,
    section_review: Path | None,
) -> str:
    paths = default_paths(
        project=project,
        project_dir=project_dir,
        receipt=receipt,
        outline=outline,
        bridge_review=bridge_review,
        bridge_beat_review=bridge_beat_review,
        section_review=section_review,
    )
    return "\n".join(
        [
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_outline_review_cycle.py" prepare-outline-review \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_outline_review_cycle.py" status \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_outline_review_cycle.py" next-step \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
            "",
            'python3 "$CODEX_HOME/skills/story-short-write/scripts/batch_outline_review_cycle.py" run-outline-review-cycle \\',
            f"  --project {_quote_shell(project)} \\",
            f"  --project-dir {_quote_shell(str(paths['project_dir']))}",
        ]
    )


def _print_status(status: dict[str, Any]) -> None:
    print("batch_outline_review_cycle: status")
    print(f"project: {status['project']}")
    print(f"project_dir: {status['project_dir']}")
    print(f"receipt: {status['receipt']}")
    print(f"outline: {status['outline']}")
    print(f"outline_exists: {status['outline_exists']}")
    print(f"receipt_gate_status: {status['receipt_gate_status']}")
    print(f"reviewed_by_current_model: {status['reviewed_by_current_model']}")
    for key in ("bridge_review", "bridge_beat_review", "section_review"):
        item = status[key]
        print(f"{key}: status={item['status']} path={item['path']}")
        if item.get("status") == "active" and "stale" in item:
            print(f"{key}_stale: {item['stale']}")
        if "total_entries" in item:
            print(f"{key}_pending: {item['pending_entries']}/{item['total_entries']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="High-level wrapper for outline performance manual review sidecars."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "prepare-outline-review",
        "status",
        "next-step",
        "run-outline-review-cycle",
        "emit-shell-template",
    ):
        command = sub.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--project-dir", required=True)
        command.add_argument("--receipt")
        command.add_argument("--outline")
        command.add_argument("--bridge-review")
        command.add_argument("--bridge-beat-review")
        command.add_argument("--section-review")
    export_next = sub.add_parser("export-next-compact")
    export_next.add_argument("--project", required=True)
    export_next.add_argument("--project-dir", required=True)
    export_next.add_argument("--receipt")
    export_next.add_argument("--outline")
    export_next.add_argument("--bridge-review")
    export_next.add_argument("--bridge-beat-review")
    export_next.add_argument("--section-review")
    export_next.add_argument("--kind", choices=("bridge-beat", "section"), required=True)
    export_next.add_argument("--output", required=True)
    pair_prepare = sub.add_parser("prepare-next-fill-pair")
    pair_prepare.add_argument("--project", required=True)
    pair_prepare.add_argument("--project-dir", required=True)
    pair_prepare.add_argument("--receipt")
    pair_prepare.add_argument("--outline")
    pair_prepare.add_argument("--bridge-review")
    pair_prepare.add_argument("--bridge-beat-review")
    pair_prepare.add_argument("--section-review")
    pair_prepare.add_argument("--bridge-output", required=True)
    pair_prepare.add_argument("--section-output", required=True)
    pair_apply = sub.add_parser("apply-fill-pair")
    pair_apply.add_argument("--project", required=True)
    pair_apply.add_argument("--project-dir", required=True)
    pair_apply.add_argument("--receipt")
    pair_apply.add_argument("--outline")
    pair_apply.add_argument("--bridge-review")
    pair_apply.add_argument("--bridge-beat-review")
    pair_apply.add_argument("--section-review")
    pair_apply.add_argument("--bridge-input", required=True)
    pair_apply.add_argument("--section-input", required=True)
    pair_apply.add_argument("--next-bridge-output")
    pair_apply.add_argument("--next-section-output")
    args = parser.parse_args()
    common_kwargs = {
        "project": args.project,
        "project_dir": Path(args.project_dir).resolve(),
        "receipt": Path(args.receipt).resolve() if args.receipt else None,
        "outline": Path(args.outline).resolve() if args.outline else None,
        "bridge_review": Path(args.bridge_review).resolve() if args.bridge_review else None,
        "bridge_beat_review": Path(args.bridge_beat_review).resolve() if args.bridge_beat_review else None,
        "section_review": Path(args.section_review).resolve() if args.section_review else None,
    }
    if args.command == "prepare-outline-review":
        errors, summary = prepare_outline_review(**common_kwargs)
        if errors:
            print("batch_outline_review_cycle: blocked")
            for item in errors:
                print(f"- {item}")
            return 2
        print("batch_outline_review_cycle: prepared")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "status":
        try:
            status = inspect_outline_review_status(**common_kwargs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_outline_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        _print_status(status)
        return 0
    if args.command == "next-step":
        try:
            suggestion = suggest_next_step(**common_kwargs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_outline_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        print("batch_outline_review_cycle: next-step")
        print(f"action: {suggestion['action']}")
        print(f"reason: {suggestion['reason']}")
        if suggestion["next_command"]:
            print(f"next_command: {suggestion['next_command']}")
        return 0
    if args.command == "export-next-compact":
        try:
            summary = export_next_compact_sidecar(
                **common_kwargs,
                kind=args.kind,
                output=Path(args.output).resolve(),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_outline_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        print("batch_outline_review_cycle: export-next-compact")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "prepare-next-fill-pair":
        try:
            summary = prepare_next_fill_pair(
                **common_kwargs,
                bridge_output=Path(args.bridge_output).resolve(),
                section_output=Path(args.section_output).resolve(),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_outline_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        print("batch_outline_review_cycle: prepare-next-fill-pair")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "apply-fill-pair":
        try:
            summary = apply_fill_pair(
                **common_kwargs,
                bridge_input=Path(args.bridge_input).resolve(),
                section_input=Path(args.section_input).resolve(),
                next_bridge_output=Path(args.next_bridge_output).resolve() if args.next_bridge_output else None,
                next_section_output=Path(args.next_section_output).resolve() if args.next_section_output else None,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("batch_outline_review_cycle: blocked")
            print(f"- {exc}")
            return 2
        print("batch_outline_review_cycle: apply-fill-pair")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0
    if args.command == "run-outline-review-cycle":
        result = run_outline_review_cycle(**common_kwargs)
        print(f"batch_outline_review_cycle: {result['action']}")
        print(f"reason: {result['reason']}")
        if result.get("errors"):
            for item in result["errors"]:
                print(f"- {item}")
            return 2
        if result.get("next_command"):
            print(f"next_command: {result['next_command']}")
        if "final_receipt_gate_status" in result:
            print(f"final_receipt_gate_status: {result['final_receipt_gate_status']}")
            print(f"final_reviewed_by_current_model: {result['final_reviewed_by_current_model']}")
        return 0
    print(emit_shell_template(**common_kwargs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
