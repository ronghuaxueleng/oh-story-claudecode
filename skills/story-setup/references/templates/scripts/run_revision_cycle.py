#!/usr/bin/env python3
"""
统一执行一轮短篇内部回炉闭环：
1. 跑全量审计
2. 生成模型改稿任务单
3. 汇总本轮关键结果

这个脚本不改正文，只负责把“审计 -> 任务单 -> 自检”串起来。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def legacy_external_audit_key(suffix: str) -> str:
    return "".join(["zh", "uque_", suffix])


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def maybe_load_json(path: Path | None) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def summarize_structured_counts(data: dict) -> dict:
    structured = data.get("structured_checks", {}) if isinstance(data, dict) else {}
    passed = failed = pending = 0
    hard_fail_triggered = False
    if isinstance(structured, dict):
        for item in structured.get("common_errors", []) + structured.get("forbidden_actions", []) + structured.get("checks", []):
            status = item.get("status")
            if status == "passed":
                passed += 1
            elif status == "failed":
                failed += 1
                hard_fail_triggered = True
            else:
                pending += 1
        for item in structured.get("required_steps", []):
            done = item.get("done")
            if done is True:
                passed += 1
            elif done is False:
                pending += 1
    return {
        "passed_count": passed,
        "failed_count": failed,
        "pending_count": pending,
        "hard_fail_triggered": hard_fail_triggered,
    }


def validate_receipt_if_needed(validator_script: Path, receipt_path: Path, receipt_data: dict | None) -> dict:
    result = {
        "attempted": False,
        "skipped": False,
        "reason": "",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "ok": False,
    }
    if not receipt_data:
        result["skipped"] = True
        result["reason"] = "receipt 不存在或不可读"
        return result
    executed = receipt_data.get("executed") is True
    status = receipt_data.get("status")
    if not executed and status == "pending":
        result["skipped"] = True
        result["reason"] = "receipt 仍为 pending，说明第二闸门尚未实际执行"
        return result
    cmd = [
        sys.executable,
        str(validator_script),
        str(receipt_path),
        "--require-executed",
        "--require-complete",
    ]
    code, stdout, stderr = run(cmd)
    result.update(
        {
            "attempted": True,
            "exit_code": code,
            "stdout": stdout,
            "stderr": stderr,
            "ok": code == 0,
        }
    )
    return result


def resolve_audit_json(output_dir: Path, source_file: Path) -> Path:
    return output_dir / f"{source_file.stem}.full_audit.json"


def resolve_task_json(output_dir: Path, source_file: Path) -> Path:
    return output_dir / f"{source_file.stem}.model_rewrite_task.json"


def build_label(user_label: str | None) -> str:
    if user_label:
        return user_label
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve_output_root(raw_output_root: str | None, project_dir: Path) -> Path:
    if raw_output_root:
        candidate = Path(raw_output_root)
        if candidate.is_absolute():
            return candidate.resolve()
        return (project_dir / candidate).resolve()
    return (project_dir / "数据" / "审计循环").resolve()


def resolve_source_file(target: Path) -> Path:
    if target.is_file():
        return target.resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"目标不存在: {target}")
    source_file = (target / "正文.md").resolve()
    if not source_file.exists():
        candidates = sorted(
            [item for item in target.iterdir() if item.is_file() and item.suffix.lower() == ".md" and "正文" in item.stem],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0].resolve()
        raise FileNotFoundError(f"目录中未找到 正文.md 或可兼容的正文版本稿: {target}")
    return source_file


def resolve_default_profile(project_dir: Path) -> Path | None:
    profiles_dir = project_dir / "profiles"
    if not profiles_dir.exists() or not profiles_dir.is_dir():
        return None

    candidates = sorted(
        [item for item in profiles_dir.iterdir() if item.is_file() and item.name.endswith(".json")],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None

    preferred = [item for item in candidates if item.name.endswith(".project.profile.json")]
    return preferred[0] if preferred else candidates[0]


def resolve_internal_standard_path(raw_path: str | None, script_dir: Path, project_dir: Path) -> Path | None:
    if raw_path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (project_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()
        return candidate
    project_local = project_dir / "profiles" / "internal_audit_standard.json"
    if project_local.exists():
        return project_local.resolve()
    default_path = (script_dir.parent / "references" / "internal_audit_standard.json").resolve()
    if default_path.exists():
        return default_path
    return None


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_profile_source_titles(plan_path: Path) -> list[str]:
    text = read_text(plan_path)
    titles: list[str] = []
    seen: set[str] = set()
    patterns = [
        r"-\s*主骨架：`([^`]+)`",
        r"###\s*辅桥[^：]*：`([^`]+)`",
        r"-\s*主骨架来源：`([^`]+)`",
        r"-\s*辅助来源：`([^`]+)`",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text):
            title = match.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            titles.append(title)
    return titles


def iter_bridge_texts(rule: dict) -> list[str]:
    texts: list[str] = []
    for key in ("bridge",):
        value = rule.get(key)
        if isinstance(value, str):
            texts.append(value)
    for key in ("opening_pattern", "must_keep", "recommended_sequence", "why_order_matters", "why_original_passes"):
        value = rule.get(key)
        if isinstance(value, list):
            texts.extend([item for item in value if isinstance(item, str)])
    return texts


def normalize_match_text(text: str) -> str:
    cleaned = text.replace("`", "")
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def bridge_rule_overlap_score(rule: dict, plan_text: str) -> int:
    score = 0
    compact_plan = normalize_match_text(plan_text)
    bridge_name = normalize_match_text(str(rule.get("bridge", "")))
    if bridge_name and bridge_name in compact_plan:
        score += 20

    for text in iter_bridge_texts(rule):
        stripped = normalize_match_text(text)
        if not stripped:
            continue
        if len(stripped) >= 4 and stripped in compact_plan:
            score += min(8, max(2, len(stripped) // 3))
        elif len(stripped) >= 2:
            parts = [part for part in re.split(r"[、，,；;：:\- ]+", stripped) if len(part) >= 2]
            local_hits = sum(1 for part in parts if part in compact_plan)
            score += min(local_hits, 4)
    return score


def narrow_profile_by_plan(output_profile: Path, plan_path: Path) -> None:
    data = json.loads(output_profile.read_text(encoding="utf-8"))
    bridge_rules = data.get("bridge_rules")
    if not isinstance(bridge_rules, list) or not bridge_rules:
        return

    plan_text = read_text(plan_path)
    scored: list[tuple[int, dict]] = []
    for rule in bridge_rules:
        if not isinstance(rule, dict):
            continue
        scored.append((bridge_rule_overlap_score(rule, plan_text), rule))

    positive = [(score, rule) for score, rule in scored if score > 0]
    if not positive:
        return

    positive.sort(key=lambda item: item[0], reverse=True)
    kept = [rule for _, rule in positive[: min(18, len(positive))]]
    data["bridge_rules"] = kept
    meta = data.get("meta", {})
    if isinstance(meta, dict):
        meta["bridge_rules_narrowed_by_plan"] = True
        meta["bridge_rules_before_narrow"] = len(bridge_rules)
        meta["bridge_rules_after_narrow"] = len(kept)
        meta["bridge_rules_plan_path"] = str(plan_path)
        data["meta"] = meta
    output_profile.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def maybe_ensure_book_project_profile(project_dir: Path, script_dir: Path) -> tuple[Path | None, dict]:
    info = {
        "checked": False,
        "generated": False,
        "reason": "",
        "plan_path": None,
        "source_titles": [],
        "source_profiles": [],
        "output_profile": None,
    }
    plan_path = project_dir / "01_主骨架与融合方案.md"
    if not plan_path.exists():
        return None, info

    info["checked"] = True
    info["plan_path"] = str(plan_path)
    source_titles = parse_profile_source_titles(plan_path)
    info["source_titles"] = source_titles
    if not source_titles:
        info["reason"] = "未从 01_主骨架与融合方案.md 识别到主骨架/辅桥来源，跳过自动生成专属 profile"
        return None, info

    merge_dir = find_named_dir(project_dir, "拆文库")
    if not merge_dir:
        info["reason"] = "未找到拆文库，无法根据骨架方案自动生成专属 profile"
        return None, info

    profile_paths: list[Path] = []
    missing_titles: list[str] = []
    for title in source_titles:
        candidate = merge_dir / title / "book.profile.json"
        if candidate.exists():
            profile_paths.append(candidate.resolve())
        else:
            missing_titles.append(title)

    if missing_titles:
        info["reason"] = f"拆文库中缺少来源书的 book.profile.json: {', '.join(missing_titles)}"
        return None, info

    profiles_dir = project_dir / "profiles"
    output_profile = profiles_dir / f"{project_dir.name}.project.profile.json"
    info["output_profile"] = str(output_profile)
    info["source_profiles"] = [str(item) for item in profile_paths]

    latest_source_mtime = max([plan_path.stat().st_mtime, *[item.stat().st_mtime for item in profile_paths]])
    if output_profile.exists() and output_profile.stat().st_mtime >= latest_source_mtime:
        info["reason"] = "当前书专属 profile 已存在且是最新"
        return output_profile.resolve(), info

    generator = script_dir / "generate_story_profile.py"
    cmd = [sys.executable, str(generator)]
    for path in profile_paths:
        cmd.extend(["--merge-profile", str(path)])
    cmd.extend([
        "--name",
        project_dir.name,
        "--output",
        str(output_profile),
    ])
    code, stdout, stderr = run(cmd)
    if code != 0:
        raise RuntimeError(
            "自动生成当前书专属 profile 失败:\n"
            f"cmd: {' '.join(cmd)}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )
    narrow_profile_by_plan(output_profile, plan_path)
    info["generated"] = True
    info["reason"] = "已根据 01_主骨架与融合方案.md 和拆文库来源书自动生成当前书专属 profile，并按当前书方案收窄桥段规则"
    return output_profile.resolve(), info


def find_named_dir(start: Path, name: str, max_up: int = 4) -> Path | None:
    current = start.resolve()
    for _ in range(max_up + 1):
        direct = current / name
        if direct.exists() and direct.is_dir():
            return direct
        if current.parent == current:
            break
        current = current.parent
    return None


def latest_book_profile_mtime(merge_dir: Path, profile_name: str = "book.profile.json") -> tuple[float | None, int]:
    files = sorted(merge_dir.rglob(profile_name))
    if not files:
        return None, 0
    latest = max(item.stat().st_mtime for item in files)
    return latest, len(files)


def maybe_refresh_project_profile(
    profile: Path | None,
    project_dir: Path,
    script_dir: Path,
    auto_refresh: bool,
) -> tuple[Path | None, dict]:
    info = {
        "checked": False,
        "refreshed": False,
        "reason": "",
        "merge_profile_dir": None,
        "book_profile_count": 0,
    }
    if not profile or not profile.exists() or not profile.name.endswith(".project.profile.json"):
        return profile, info

    merge_dir = find_named_dir(project_dir, "拆文库")
    if not merge_dir:
        info["checked"] = True
        info["reason"] = "未找到拆文库，跳过 project profile 过期检查"
        return profile, info

    latest_mtime, count = latest_book_profile_mtime(merge_dir)
    info["checked"] = True
    info["merge_profile_dir"] = str(merge_dir)
    info["book_profile_count"] = count
    if latest_mtime is None:
        info["reason"] = "拆文库中未找到 book.profile.json，跳过 project profile 过期检查"
        return profile, info

    profile_mtime = profile.stat().st_mtime
    if profile_mtime >= latest_mtime:
        info["reason"] = "project profile 已是最新"
        return profile, info

    info["reason"] = "project profile 早于拆文库中的单书 profile"
    if not auto_refresh:
        raise RuntimeError(
            f"profile 已过期且未开启自动重生: {profile}\n"
            f"拆文库: {merge_dir}\n"
            "请先重生 project profile，或移除 --no-refresh-profile-if-stale。"
        )

    generator = script_dir / "generate_story_profile.py"
    profile_name = profile.stem.replace(".project.profile", "")
    cmd = [
        sys.executable,
        str(generator),
        "--merge-profile-dir",
        str(merge_dir),
        "--name",
        profile_name,
        "--output",
        str(profile),
    ]
    code, stdout, stderr = run(cmd)
    if code != 0:
        raise RuntimeError(
            "自动重生 project profile 失败:\n"
            f"cmd: {' '.join(cmd)}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )
    info["refreshed"] = True
    info["reason"] = "project profile 已按最新拆文库自动重生"
    return profile, info


def find_previous_audit_json(output_root: Path, current_label: str, source_file: Path) -> Path | None:
    candidates: list[tuple[float, Path]] = []
    if not output_root.exists():
        return None

    for item in output_root.iterdir():
        if not item.is_dir() or item.name == current_label:
            continue
        summary_path = item / "cycle_summary.json"
        audit_path = item / "audit" / f"{source_file.stem}.full_audit.json"
        if not summary_path.exists() or not audit_path.exists():
            continue
        try:
            summary = load_json(summary_path)
        except Exception:
            continue
        if summary.get("source_file") != str(source_file):
            continue
        candidates.append((summary_path.stat().st_mtime, audit_path))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def build_gate_state(task: dict, task_dir: Path, source_file: Path) -> dict:
    gate = task.get("rewrite_gate", {}) or {}
    artifacts = gate.get("task_artifacts", {}) or {}
    validator_script = Path(__file__).resolve().parent / "validate_gate_receipts.py"

    def to_path(value: str | None, fallback_name: str) -> Path:
        if value:
            candidate = Path(value)
            if candidate.is_absolute():
                return candidate
            return (task_dir / candidate).resolve()
        return (task_dir / fallback_name).resolve()

    stem = source_file.stem
    rewrite_task_md = to_path(artifacts.get("rewrite_gate_task_md"), f"{stem}.rewrite_gate_task.md")
    failure_task_md = to_path(artifacts.get("failure_gate_task_md"), f"{stem}.failure_gate_task.md")
    rewrite_receipt_path = to_path(artifacts.get("rewrite_gate_receipt_json"), f"{stem}.rewrite_gate_receipt.json")
    failure_receipt_path = to_path(artifacts.get("failure_gate_receipt_json"), f"{stem}.failure_gate_receipt.json")

    rewrite_receipt = maybe_load_json(rewrite_receipt_path)
    failure_receipt = maybe_load_json(failure_receipt_path)
    rewrite_validation = validate_receipt_if_needed(validator_script, rewrite_receipt_path, rewrite_receipt)
    failure_validation = validate_receipt_if_needed(validator_script, failure_receipt_path, failure_receipt)

    def normalize_receipt(receipt: dict | None, gate_name: str, task_path: Path, receipt_path: Path) -> dict:
        data = receipt or {}
        summary = summarize_structured_counts(data)
        merged_summary = dict(data.get("summary", {}))
        for key, value in summary.items():
            merged_summary[key] = value
        return {
            "required": True,
            "task_path": str(task_path),
            "receipt_path": str(receipt_path),
            "task_exists": task_path.exists(),
            "receipt_exists": receipt_path.exists(),
            "executed": bool(data.get("executed")),
            "status": data.get("status") or ("pending" if receipt_path.exists() else "missing"),
            "judge": data.get("judge"),
            "operator": data.get("operator"),
            "checked_at": data.get("checked_at"),
            "summary": merged_summary,
            "structured_checks": data.get("structured_checks", {}),
            "notes": data.get("notes", []),
            "reference_doc": data.get("reference_doc"),
            "gate_name": data.get("gate_name") or gate_name,
        }

    rewrite_state = normalize_receipt(rewrite_receipt, "受限重写自检", rewrite_task_md, rewrite_receipt_path)
    failure_state = normalize_receipt(failure_receipt, "失败即重写判定", failure_task_md, failure_receipt_path)
    rewrite_state["validation"] = rewrite_validation
    failure_state["validation"] = failure_validation
    stage = "awaiting_rewrite_gate"
    ready_for_next_revision = False
    blockers: list[str] = []
    next_action = "先执行受限重写自检，并回填 rewrite_gate_receipt.json。"
    if rewrite_validation["attempted"] and not rewrite_validation["ok"]:
        stage = "rewrite_gate_invalid"
        blockers.append("受限重写自检回执已填写，但未通过结构校验。")
        next_action = "先修正 rewrite_gate_receipt.json 的填写，再继续后续流程。"
    elif failure_validation["attempted"] and not failure_validation["ok"]:
        stage = "failure_gate_invalid"
        blockers.append("失败即重写判定回执已填写，但未通过结构校验。")
        next_action = "先修正 failure_gate_receipt.json 的填写，再继续后续流程。"
    elif rewrite_state["status"] == "failed":
        stage = "rewrite_gate_failed"
        blockers.append("受限重写自检未通过，当前高风险段不能继续下游回炉。")
        next_action = "按 rewrite_gate_task.md 重做当前高风险段，直到 rewrite gate 通过。"
    elif rewrite_state["status"] == "passed" and failure_state["status"] == "pending":
        stage = "awaiting_failure_gate"
        blockers.append("失败即重写判定尚未执行，当前轮次不能视为完整闭环。")
        next_action = "执行失败即重写判定，并回填 failure_gate_receipt.json。"
    elif failure_state["status"] == "failed":
        stage = "failure_gate_failed"
        blockers.append("失败即重写判定未通过，当前高风险段应作废重写。")
        next_action = "按 failure_gate_task.md 指出的硬失败项重写当前高风险段。"
    elif rewrite_state["status"] == "passed" and failure_state["status"] == "passed":
        stage = "gate_passed"
        ready_for_next_revision = True
        next_action = "gate 已通过，可以进入下一轮内部审计或送下一层流程。"
    else:
        blockers.append("受限重写自检尚未执行，当前轮次不能视为完整闭环。")
    return {
        "protocol_doc": gate.get("protocol_doc"),
        "failure_gate_doc": gate.get("failure_gate_doc"),
        "precheck_script": gate.get("precheck_script"),
        "precheck_config": gate.get("precheck_config"),
        "required": bool(gate),
        "artifacts": {
            "rewrite_gate_task_md": str(rewrite_task_md),
            "failure_gate_task_md": str(failure_task_md),
            "rewrite_gate_receipt_json": str(rewrite_receipt_path),
            "failure_gate_receipt_json": str(failure_receipt_path),
        },
        "rewrite_gate": rewrite_state,
        "failure_gate": failure_state,
        "stage": stage,
        "ready_for_next_revision": ready_for_next_revision,
        "blockers": blockers,
        "next_action": next_action,
        "overall_status": (
            "passed"
            if rewrite_state["status"] == "passed" and failure_state["status"] == "passed"
            else "failed"
            if "failed" in {rewrite_state["status"], failure_state["status"]}
            else "pending"
        ),
    }


def build_summary(
    audit: dict,
    task: dict,
    source_file: Path,
    profile: Path | None,
    cycle_dir: Path,
    previous_audit_json: Path | None,
    profile_refresh_info: dict | None,
    book_profile_bootstrap_info: dict | None,
) -> dict:
    current = task.get("current_summary", {})
    validation = task.get("task_validation", {})
    segment_focus = task.get("segment_focus", [])
    paragraph_focus = task.get("paragraph_focus", [])
    tasks = task.get("tasks", [])
    gate_state = build_gate_state(task, cycle_dir / "task", source_file)
    legacy_weighted = current.get(legacy_external_audit_key("weighted_avg"))
    legacy_max_seg = current.get(legacy_external_audit_key("max_seg"))
    legacy_judgement = current.get(legacy_external_audit_key("judgement"))
    return {
        "source_file": str(source_file),
        "profile": str(profile) if profile else None,
        "cycle_dir": str(cycle_dir),
        "score": current.get("score"),
        "status": current.get("status"),
        "internal_overall_risk": current.get("internal_overall_risk", current.get("external_block_audit_weighted_avg", legacy_weighted)),
        "internal_max_block_risk": current.get("internal_max_block_risk", current.get("external_block_audit_max_seg", legacy_max_seg)),
        "internal_judgement": current.get("internal_judgement", current.get("external_block_audit_judgement", legacy_judgement)),
        "sample_level": current.get("sample_level"),
        "sample_dna_usable": current.get("sample_dna_usable"),
        "global_risk_shape": task.get("global_risk_shape", {}),
        "global_shape": (task.get("global_risk_shape") or {}).get("shape"),
        "global_block_count": len(((task.get("global_risk_shape") or {}).get("global_blocks") or [])),
        "coarse_segment_scores": [
            {
                "segment_index": item.get("segment_index"),
                "risk_score": item.get("risk_score"),
                "risk_level": item.get("risk_level"),
                "paragraph_range": item.get("paragraph_range"),
                "flags": item.get("flags", [])[:6],
            }
            for item in task.get("coarse_block_focus", [])[:3]
        ],
        "external_block_audit_weighted_avg": current.get("external_block_audit_weighted_avg", legacy_weighted),
        "external_block_audit_max_seg": current.get("external_block_audit_max_seg", legacy_max_seg),
        "external_block_audit_judgement": current.get("external_block_audit_judgement", legacy_judgement),
        "sample_grading_guidance": task.get("sample_grading_guidance", {}),
        "light_hits": current.get("light_hits"),
        "top_display_blocks": [
            {
                "block_index": item.get("block_index"),
                "risk_score": item.get("risk_score"),
                "paragraph_range": item.get("paragraph_range"),
                "flags": item.get("flags", [])[:6],
            }
            for item in task.get("display_block_focus", [])[:3]
        ],
        "top_segment_ranges": [
            {
                "segment_index": item.get("segment_index"),
                "paragraph_range": item.get("paragraph_range"),
                "flags": item.get("flags", [])[:6],
            }
            for item in segment_focus[:5]
        ],
        "top_paragraphs": [
            {
                "paragraph_index": item.get("paragraph_index"),
                "segment_index": item.get("segment_index"),
                "flags": item.get("flags", [])[:4],
            }
            for item in paragraph_focus[:8]
        ],
        "top_task_titles": [item.get("title") for item in tasks[:8]],
        "task_validation": validation,
        "rewrite_gate": gate_state,
        "audit_json": audit.get("audit_json_path"),
        "previous_audit_json": str(previous_audit_json) if previous_audit_json else None,
        "profile_refresh_info": profile_refresh_info or {},
        "book_profile_bootstrap_info": book_profile_bootstrap_info or {},
    }


def render_gate_validation(summary: dict) -> str:
    gate = summary.get("rewrite_gate", {}) or {}
    rewrite_gate = gate.get("rewrite_gate", {}) or {}
    failure_gate = gate.get("failure_gate", {}) or {}

    def render_validation_block(title: str, data: dict) -> list[str]:
        validation = data.get("validation", {}) or {}
        summary_counts = data.get("summary", {}) or {}
        lines = [
            f"## {title}",
            "",
            f"- status: `{data.get('status')}`",
            f"- executed: `{data.get('executed')}`",
            f"- validation_ok: `{validation.get('ok')}`",
            f"- validation_attempted: `{validation.get('attempted')}`",
            f"- validation_skipped: `{validation.get('skipped')}`",
            f"- passed_count: `{summary_counts.get('passed_count')}`",
            f"- failed_count: `{summary_counts.get('failed_count')}`",
            f"- pending_count: `{summary_counts.get('pending_count')}`",
            f"- hard_fail_triggered: `{summary_counts.get('hard_fail_triggered')}`",
        ]
        if validation.get("reason"):
            lines.append(f"- validation_reason: {validation.get('reason')}")
        if validation.get("attempted") and validation.get("stdout"):
            lines.extend(["", "### 校验输出", "", "```text", validation.get("stdout", "").rstrip(), "```"])
        return lines + [""]

    lines = [
        "# Gate 校验结论",
        "",
        f"- source_file: `{summary.get('source_file')}`",
        f"- gate_stage: `{gate.get('stage')}`",
        f"- gate_overall_status: `{gate.get('overall_status')}`",
        f"- ready_for_next_revision: `{gate.get('ready_for_next_revision')}`",
        f"- next_action: {gate.get('next_action')}",
        "",
    ]
    blockers = gate.get("blockers", []) or []
    if blockers:
        lines.append("## 阻断项")
        lines.append("")
        for item in blockers:
            lines.append(f"- {item}")
        lines.append("")
    lines.extend(render_validation_block("受限重写自检", rewrite_gate))
    lines.extend(render_validation_block("失败即重写判定", failure_gate))
    return "\n".join(lines).rstrip() + "\n"


def render_status_text(summary: dict) -> str:
    gate = summary.get("rewrite_gate", {}) or {}
    lines = [
        f"stage={gate.get('stage')}",
        f"overall={gate.get('overall_status')}",
        f"ready={gate.get('ready_for_next_revision')}",
        f"next={gate.get('next_action')}",
    ]
    blockers = gate.get("blockers", []) or []
    if blockers:
        lines.append(f"blocker={blockers[0]}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="正文工作稿路径，或包含 正文.md 的项目目录")
    parser.add_argument("--profile", help="可选：book/project profile JSON；不传时若 target 是目录，自动从 profiles/ 里取最新规则包")
    parser.add_argument("--output-root", help="循环产物根目录；不传时默认落到 当前书目录/数据/审计循环")
    parser.add_argument("--label", help="可选：本轮目录名")
    parser.add_argument("--previous-audit-json", help="可选：上一轮审计 JSON，用于任务单对比；不传时自动从 output-root 找上一轮")
    parser.add_argument("--no-refresh-profile-if-stale", action="store_true", help="若当前 project profile 早于拆文库中的单书 profile，则报错而不是自动重生")
    parser.add_argument("--internal-standard", help="可选：内部审计标准 JSON；传入后整个回炉闭环会带内部风险分判断")
    parser.add_argument("--external-block-audit-alignment-summary", help="外部分块审计对标摘要 JSON")
    parser.add_argument("--require-gates-passed", action="store_true", help="若 gate 回执未全部通过，则以非零状态退出，防止把未过第二闸门的轮次当成完整闭环")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    try:
        source_file = resolve_source_file(target)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    project_dir = target if target.is_dir() else source_file.parent
    book_profile_bootstrap_info: dict | None = None
    profile = Path(args.profile).resolve() if args.profile else resolve_default_profile(project_dir)
    if not args.profile and not profile:
        try:
            profile, book_profile_bootstrap_info = maybe_ensure_book_project_profile(project_dir, script_dir=Path(__file__).resolve().parent)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if profile and not profile.exists():
        print(f"profile 不存在: {profile}", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent
    audit_script = script_dir / "run_full_ai_audit.py"
    task_script = script_dir / "auto_revise_ai_flavor.py"
    internal_standard = resolve_internal_standard_path(args.internal_standard, script_dir, project_dir)
    block_audit_alignment_summary = None
    if args.external_block_audit_alignment_summary:
        block_audit_alignment_summary = Path(args.external_block_audit_alignment_summary).resolve()
    standard_path = internal_standard or block_audit_alignment_summary

    try:
        profile, profile_refresh_info = maybe_refresh_project_profile(
            profile,
            project_dir,
            script_dir,
            auto_refresh=not args.no_refresh_profile_if_stale,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    label = build_label(args.label)
    output_root = resolve_output_root(args.output_root, project_dir)
    cycle_dir = output_root / label
    audit_dir = cycle_dir / "audit"
    task_dir = cycle_dir / "task"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    previous_audit_json = Path(args.previous_audit_json).resolve() if args.previous_audit_json else find_previous_audit_json(output_root, label, source_file)

    audit_cmd = [sys.executable, str(audit_script), str(source_file), "--output-dir", str(audit_dir)]
    if profile:
        audit_cmd.extend(["--profile", str(profile)])
    if standard_path:
        audit_cmd.extend(["--internal-standard", str(standard_path)])
    code, stdout, stderr = run(audit_cmd)
    if code != 0:
        print(f"全量审计失败:\nstdout:\n{stdout}\nstderr:\n{stderr}", file=sys.stderr)
        return code

    task_cmd = [sys.executable, str(task_script), str(source_file), "--output-dir", str(task_dir)]
    if profile:
        task_cmd.extend(["--profile", str(profile)])
    if previous_audit_json:
        task_cmd.extend(["--previous-audit-json", str(previous_audit_json)])
    if standard_path:
        task_cmd.extend(["--internal-standard", str(standard_path)])
    code, stdout, stderr = run(task_cmd)
    if code != 0:
        print(f"任务单生成失败:\nstdout:\n{stdout}\nstderr:\n{stderr}", file=sys.stderr)
        return code

    audit_json_path = resolve_audit_json(audit_dir, source_file)
    task_json_path = resolve_task_json(task_dir, source_file)
    audit = load_json(audit_json_path)
    audit["audit_json_path"] = str(audit_json_path)
    task = load_json(task_json_path)

    summary = build_summary(
        audit,
        task,
        source_file,
        profile,
        cycle_dir,
        previous_audit_json,
        profile_refresh_info,
        book_profile_bootstrap_info,
    )
    summary_path = cycle_dir / "cycle_summary.json"
    gate_validation_path = cycle_dir / "gate_validation.md"
    status_path = cycle_dir / "STATUS.txt"
    write_json(summary_path, summary)
    gate_validation_path.write_text(render_gate_validation(summary), encoding="utf-8")
    status_path.write_text(render_status_text(summary), encoding="utf-8")

    print("已输出:")
    print(f"- {audit_json_path}")
    print(f"- {audit_dir / f'{source_file.stem}.full_audit.md'}")
    print(f"- {task_json_path}")
    print(f"- {task_dir / f'{source_file.stem}.model_rewrite_task.md'}")
    print(f"- {task_dir / f'{source_file.stem}.rewrite_gate_task.md'}")
    print(f"- {task_dir / f'{source_file.stem}.failure_gate_task.md'}")
    print(f"- {summary_path}")
    print(f"- {gate_validation_path}")
    print(f"- {status_path}")
    print(f"previous_audit_json: {summary.get('previous_audit_json')}")
    if summary.get("profile_refresh_info"):
        print(f"profile_refresh: {summary['profile_refresh_info'].get('reason')}")
    if summary.get("book_profile_bootstrap_info"):
        print(f"book_profile_bootstrap: {summary['book_profile_bootstrap_info'].get('reason')}")
    if summary.get("internal_judgement"):
        print(f"internal_risk: {summary.get('internal_judgement')} / overall={summary.get('internal_overall_risk')} / max_block={summary.get('internal_max_block_risk')}")
    if summary.get("global_shape"):
        print(f"global_shape: {summary.get('global_shape')} / global_block_count={summary.get('global_block_count')}")
    print(f"bridge_alignment_ok: {summary['task_validation'].get('bridge_alignment_ok')}")
    print(f"short_paragraph_priority_ok: {summary['task_validation'].get('short_paragraph_priority_ok')}")
    if summary.get("rewrite_gate"):
        print(f"rewrite_gate_protocol: {summary['rewrite_gate'].get('protocol_doc')}")
        print(f"rewrite_gate_failure: {summary['rewrite_gate'].get('failure_gate_doc')}")
        print(f"rewrite_gate_status: {summary['rewrite_gate'].get('rewrite_gate', {}).get('status')}")
        print(f"failure_gate_status: {summary['rewrite_gate'].get('failure_gate', {}).get('status')}")
        print(f"gate_stage: {summary['rewrite_gate'].get('stage')}")
        print(f"gate_overall_status: {summary['rewrite_gate'].get('overall_status')}")
        if summary["rewrite_gate"].get("blockers"):
            print("gate_blockers:")
            for item in summary["rewrite_gate"]["blockers"]:
                print(f"- {item}")
        print(f"gate_next_action: {summary['rewrite_gate'].get('next_action')}")
    if args.require_gates_passed and summary.get("rewrite_gate", {}).get("ready_for_next_revision") is False:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
