#!/usr/bin/env python3
"""
story-deslop 的第二闸门闭环：
1. 跑去味审计
2. 跑受限重写预检
3. 生成 gate 执行单
4. 生成 gate 回执模板
5. 汇总当前状态
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


HEADING_ERROR_RE = re.compile(r"^###\s*错误\s*(\d+)\s*：\s*(.+?)\s*$", re.MULTILINE)
STEP_HEADING_RE = re.compile(r"^###\s*第\s*(\d+)\s*步：\s*(.+?)\s*$", re.MULTILINE)
FAILURE_ITEM_RE = re.compile(r"^###\s*(\d+)\.\s*(.+?)\s*$", re.MULTILINE)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def resolve_gate_doc(script_dir: Path, filename: str) -> Path:
    shared_dir = script_dir.parent.parent / "story" / "references" / "high-risk-gates"
    target = shared_dir / filename
    if not target.exists():
        raise FileNotFoundError(f"缺少共享第二闸门主文档: {target}")
    return target.resolve()


def parse_rewrite_protocol_schema(protocol_doc: Path) -> dict:
    text = read_text(protocol_doc)
    common_errors = [
        {
            "index": int(index),
            "name": title.strip(),
            "status": "pending",
            "evidence": [],
            "reason": "",
        }
        for index, title in HEADING_ERROR_RE.findall(text)
    ]
    required_steps = [
        {
            "index": int(index),
            "name": title.strip(),
            "done": False,
            "notes": [],
        }
        for index, title in STEP_HEADING_RE.findall(text)
    ]
    return {
        "force_points": {
            "hurt_facts": ["", "", ""],
            "bias_orders": ["", ""],
            "undignified_emotion": "",
        },
        "must_keep_force_points": ["", "", "", "", ""],
        "forbidden_actions": [
            {"name": "禁止补漂亮细节", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止写示范腔动作句", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止把对白写成高功能台词", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止提前总结人物关系", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止用作者口吻解释心理", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止把场面写得过于整齐", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止磨平俗和脏", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止用抽象判断替代事实伤害", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止让人物说太完整的话", "status": "pending", "evidence": [], "reason": ""},
            {"name": "禁止把任务做成总结后再创作", "status": "pending", "evidence": [], "reason": ""},
        ],
        "common_errors": common_errors,
        "required_steps": required_steps,
    }


def parse_failure_gate_schema(failure_doc: Path) -> dict:
    text = read_text(failure_doc)
    checks = [
        {
            "index": int(index),
            "name": title.strip(),
            "status": "pending",
            "evidence": [],
            "reason": "",
        }
        for index, title in FAILURE_ITEM_RE.findall(text)
        if int(index) <= 21
    ]
    return {
        "checks": checks,
        "rewrite_actions": {
            "delete_top3_sentences": ["", "", ""],
            "split_top2_dialogues": ["", ""],
            "cut_top1_closure": "",
        },
    }


def summarize_structured_counts(structured: dict) -> dict:
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


def resolve_source_file(target: Path) -> Path:
    if target.is_file():
        return target.resolve()
    raise FileNotFoundError(f"目标不是文件: {target}")


def build_label(user_label: str | None) -> str:
    return user_label or datetime.now().strftime("%Y%m%d_%H%M%S")


def rewrite_gate_bundle(script_dir: Path) -> dict:
    references_dir = script_dir.parent / "references"
    governance_dir = references_dir / "governance"
    return {
        "lexicon_json": str((governance_dir / "通用高风险词类词典.json").resolve()),
        "precheck_script": str((script_dir / "precheck_rewrite_gate.py").resolve()),
        "precheck_config": str((governance_dir / "precheck_rewrite_gate.config.json").resolve()),
        "protocol_doc": str(resolve_gate_doc(script_dir, "通用-受限重写防错协议.md")),
        "rewrite_prompt_doc": str(resolve_gate_doc(script_dir, "执行模板-受限重写提示词.md")),
        "failure_gate_doc": str(resolve_gate_doc(script_dir, "执行模板-失败即重写判定.md")),
        "execution_order": [
            "先看去味审计报告，确定当前高风险段和主要污染类型。",
            "正文改写前，先跑 precheck_rewrite_gate.py 做第二闸门预检。",
            "预检后，必须按 通用-受限重写防错协议 限制改写范围。",
            "改完后，必须再按 执行模板-失败即重写判定 做失败裁决。",
        ],
        "hard_fail_focus": [
            "场面过于整齐",
            "高功能对白",
            "作者替角色下结论",
            "重大信息闭环链过强",
            "一段同时完成太多任务",
        ],
    }


def gate_receipt_template(source_file: Path, gate_type: str, reference_doc: str | None) -> dict:
    names = {
        "rewrite_gate": "受限重写自检",
        "failure_gate": "失败即重写判定",
    }
    structured = (
        parse_rewrite_protocol_schema(Path(reference_doc))
        if gate_type == "rewrite_gate" and reference_doc
        else parse_failure_gate_schema(Path(reference_doc))
        if gate_type == "failure_gate" and reference_doc
        else {}
    )
    summary = summarize_structured_counts(structured)
    return {
        "source_file": str(source_file),
        "gate_type": gate_type,
        "gate_name": names.get(gate_type, gate_type),
        "schema_version": "1.0",
        "required": True,
        "executed": False,
        "status": "pending",
        "judge": "",
        "operator": "",
        "checked_at": "",
        "reference_doc": reference_doc,
        "summary": summary,
        "structured_checks": structured,
        "notes": [],
    }


def rewrite_gate_task_card(source_file: Path, gate: dict, audit_summary: dict, precheck_counts: dict[str, int]) -> str:
    lines = [
        "# 受限重写自检执行单",
        "",
        f"- 当前正文: `{source_file}`",
        f"- 协议文件: `{gate.get('protocol_doc')}`",
        f"- 预检脚本: `{gate.get('precheck_script')}`",
        f"- 预检配置: `{gate.get('precheck_config')}`",
        f"- 去味审计分: `{audit_summary.get('score')}`",
        f"- 去味审计状态: `{audit_summary.get('status')}`",
        "",
        "## 本轮先看这些污染",
        "",
    ]
    if precheck_counts:
        for key, value in precheck_counts.items():
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- 本轮预检无明显命中，但仍需按协议约束改写范围。")
    lines.extend(["", "## 执行顺序", ""])
    for item in gate.get("execution_order", []):
        lines.append(f"- {item}")
    lines.extend(["", "## 本轮硬限制", ""])
    lines.extend([
        "- 只改当前高风险段，不顺手抹平整篇口气。",
        "- 不准把对话统统改成陈述句。",
        "- 不准新增原文没有的情节、关系、设定和后果。",
        "- 不准只做词语替换，要优先拆作者解释句和整齐收口。",
        "",
        "## 通过标准",
        "",
        "- 当前高风险段不再明显命中作者解释句、提前判断、高功能对白、漂亮收口。",
        "- 当前高风险段不能再一刀完成多个主任务。",
        "- 通过后才允许进入失败即重写判定。",
        "",
    ])
    return "\n".join(lines)


def failure_gate_task_card(source_file: Path, gate: dict) -> str:
    lines = [
        "# 失败即重写判定执行单",
        "",
        f"- 当前正文: `{source_file}`",
        f"- 判定文件: `{gate.get('failure_gate_doc')}`",
        "",
        "## 本轮硬失败重点",
        "",
    ]
    for item in gate.get("hard_fail_focus", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## 输出要求",
        "",
        "- 只判当前高风险段，不顺手点评整篇。",
        "- 命中任一硬失败项，当前高风险段直接作废重写。",
        "- 如果通过，才允许回到去味审计复跑。",
        "",
    ])
    return "\n".join(lines)


def maybe_load_json(path: Path | None) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def normalize_receipt(receipt: dict | None, gate_name: str, task_path: Path, receipt_path: Path) -> dict:
    data = receipt or {}
    summary = summarize_structured_counts(data.get("structured_checks", {}))
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


def build_gate_status(rewrite_receipt_path: Path, failure_receipt_path: Path, rewrite_task_md: Path, failure_task_md: Path) -> dict:
    validator_script = Path(__file__).resolve().parent / "validate_gate_receipts.py"
    rewrite_state = normalize_receipt(maybe_load_json(rewrite_receipt_path), "受限重写自检", rewrite_task_md, rewrite_receipt_path)
    failure_state = normalize_receipt(maybe_load_json(failure_receipt_path), "失败即重写判定", failure_task_md, failure_receipt_path)
    rewrite_validation = validate_receipt_if_needed(validator_script, rewrite_receipt_path, maybe_load_json(rewrite_receipt_path))
    failure_validation = validate_receipt_if_needed(validator_script, failure_receipt_path, maybe_load_json(failure_receipt_path))
    rewrite_state["validation"] = rewrite_validation
    failure_state["validation"] = failure_validation
    stage = "awaiting_rewrite_gate"
    blockers: list[str] = []
    next_action = "先执行受限重写自检，并回填 rewrite_gate_receipt.json。"
    ready = False
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
        blockers.append("受限重写自检未通过，不能把本轮去味当成完整闭环。")
        next_action = "按 rewrite_gate_task.md 重做当前高风险段。"
    elif rewrite_state["status"] == "passed" and failure_state["status"] == "pending":
        stage = "awaiting_failure_gate"
        blockers.append("失败即重写判定尚未执行。")
        next_action = "执行失败即重写判定，并回填 failure_gate_receipt.json。"
    elif failure_state["status"] == "failed":
        stage = "failure_gate_failed"
        blockers.append("失败即重写判定未通过，当前高风险段应作废重写。")
        next_action = "按 failure_gate_task.md 指出的硬失败项重写。"
    elif rewrite_state["status"] == "passed" and failure_state["status"] == "passed":
        stage = "gate_passed"
        ready = True
        next_action = "gate 已通过，可以继续下一轮去味审计。"
    else:
        blockers.append("受限重写自检尚未执行。")
    return {
        "rewrite_gate": rewrite_state,
        "failure_gate": failure_state,
        "stage": stage,
        "ready_for_next_revision": ready,
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
    parser.add_argument("file", help="待去味正文文件")
    parser.add_argument("--output-root", help="产物根目录；默认落到 当前文件同级/数据/去味闸门循环")
    parser.add_argument("--label", help="本轮目录名")
    parser.add_argument("--require-gates-passed", action="store_true", help="若 gate 回执未全部通过，则以非零状态退出")
    args = parser.parse_args()

    source_file = resolve_source_file(Path(args.file))
    script_dir = Path(__file__).resolve().parent
    project_dir = source_file.parent
    output_root = Path(args.output_root).resolve() if args.output_root else (project_dir / "数据" / "去味闸门循环").resolve()
    cycle_dir = output_root / build_label(args.label)
    audit_dir = cycle_dir / "audit"
    gate_dir = cycle_dir / "gate"
    audit_dir.mkdir(parents=True, exist_ok=True)
    gate_dir.mkdir(parents=True, exist_ok=True)

    audit_script = script_dir / "audit_ai_flavor.py"
    precheck_script = script_dir / "precheck_rewrite_gate.py"
    gate = rewrite_gate_bundle(script_dir)

    audit_json = audit_dir / f"{source_file.stem}.审计报告.json"
    audit_md = audit_dir / f"{source_file.stem}.审计报告.md"
    code, stdout, stderr = run([sys.executable, str(audit_script), str(source_file), "--lexicon", gate["lexicon_json"], "--format", "json", "-o", str(audit_json)])
    if code != 0:
        print(f"去味审计失败:\nstdout:\n{stdout}\nstderr:\n{stderr}", file=sys.stderr)
        return code
    code, stdout, stderr = run([sys.executable, str(audit_script), str(source_file), "--lexicon", gate["lexicon_json"], "--format", "md", "-o", str(audit_md)])
    if code != 0:
        print(f"去味审计失败:\nstdout:\n{stdout}\nstderr:\n{stderr}", file=sys.stderr)
        return code

    code, stdout, stderr = run([sys.executable, str(precheck_script), str(source_file), "--config", gate["precheck_config"]])
    if code != 0:
        print(f"重写预检失败:\nstdout:\n{stdout}\nstderr:\n{stderr}", file=sys.stderr)
        return code

    src_precheck_json = source_file.with_name(f"{source_file.stem}-重写预检.json")
    src_precheck_md = source_file.with_name(f"{source_file.stem}-重写预检.md")
    precheck_json = gate_dir / src_precheck_json.name
    precheck_md = gate_dir / src_precheck_md.name
    if src_precheck_json.exists():
        shutil.move(str(src_precheck_json), str(precheck_json))
    if src_precheck_md.exists():
        shutil.move(str(src_precheck_md), str(precheck_md))

    rewrite_gate_task = gate_dir / f"{source_file.stem}.rewrite_gate_task.md"
    failure_gate_task = gate_dir / f"{source_file.stem}.failure_gate_task.md"
    rewrite_gate_receipt = gate_dir / f"{source_file.stem}.rewrite_gate_receipt.json"
    failure_gate_receipt = gate_dir / f"{source_file.stem}.failure_gate_receipt.json"

    audit_report = load_json(audit_json)
    precheck_report = load_json(precheck_json) if precheck_json.exists() else {}
    precheck_counts = {key: len(value) for key, value in precheck_report.items() if isinstance(value, list)}

    write_text(rewrite_gate_task, rewrite_gate_task_card(source_file, gate, audit_report.get("summary", {}), precheck_counts))
    write_text(failure_gate_task, failure_gate_task_card(source_file, gate))
    if not rewrite_gate_receipt.exists():
        write_json(rewrite_gate_receipt, gate_receipt_template(source_file, "rewrite_gate", gate.get("protocol_doc")))
    if not failure_gate_receipt.exists():
        write_json(failure_gate_receipt, gate_receipt_template(source_file, "failure_gate", gate.get("failure_gate_doc")))

    gate_status = build_gate_status(rewrite_gate_receipt, failure_gate_receipt, rewrite_gate_task, failure_gate_task)
    summary = {
        "source_file": str(source_file),
        "cycle_dir": str(cycle_dir),
        "audit": {
            "json_path": str(audit_json),
            "md_path": str(audit_md),
            "score": audit_report.get("summary", {}).get("score"),
            "status": audit_report.get("summary", {}).get("status"),
        },
        "precheck": {
            "json_path": str(precheck_json),
            "md_path": str(precheck_md),
            "counts": precheck_counts,
        },
        "rewrite_gate": {
            "protocol_doc": gate.get("protocol_doc"),
            "failure_gate_doc": gate.get("failure_gate_doc"),
            "precheck_script": gate.get("precheck_script"),
            "precheck_config": gate.get("precheck_config"),
            "artifacts": {
                "rewrite_gate_task_md": str(rewrite_gate_task),
                "failure_gate_task_md": str(failure_gate_task),
                "rewrite_gate_receipt_json": str(rewrite_gate_receipt),
                "failure_gate_receipt_json": str(failure_gate_receipt),
            },
            **gate_status,
        },
    }
    summary_path = cycle_dir / "cycle_summary.json"
    gate_validation_path = cycle_dir / "gate_validation.md"
    status_path = cycle_dir / "STATUS.txt"
    write_json(summary_path, summary)
    write_text(gate_validation_path, render_gate_validation(summary))
    write_text(status_path, render_status_text(summary))

    print("已输出:")
    print(f"- {audit_json}")
    print(f"- {audit_md}")
    print(f"- {precheck_json}")
    print(f"- {precheck_md}")
    print(f"- {rewrite_gate_task}")
    print(f"- {failure_gate_task}")
    print(f"- {rewrite_gate_receipt}")
    print(f"- {failure_gate_receipt}")
    print(f"- {summary_path}")
    print(f"- {gate_validation_path}")
    print(f"- {status_path}")
    print(f"gate_stage: {summary['rewrite_gate']['stage']}")
    print(f"gate_overall_status: {summary['rewrite_gate']['overall_status']}")
    if summary["rewrite_gate"]["blockers"]:
        print("gate_blockers:")
        for item in summary["rewrite_gate"]["blockers"]:
            print(f"- {item}")
    print(f"gate_next_action: {summary['rewrite_gate']['next_action']}")

    if args.require_gates_passed and not summary["rewrite_gate"]["ready_for_next_revision"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
