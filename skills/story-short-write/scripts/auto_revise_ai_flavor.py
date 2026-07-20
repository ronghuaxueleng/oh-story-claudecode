#!/usr/bin/env python3
"""
内部审计 -> 对比 -> 生成模型改稿任务单。

说明：
- 这个脚本不直接改正文
- 不调用外部检测站点
- 不内置硬编码改写规则
- 只负责把内部审计结果收束成“下一轮该怎么让模型改”的任务单
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def legacy_external_audit_key(suffix: str) -> str:
    return "".join(["zh", "uque_", suffix])


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def rewrite_gate_bundle(script_dir: Path) -> dict:
    references_dir = script_dir.parent / "references"
    governance_dir = references_dir / "governance"
    return {
        "precheck_script": str((script_dir / "precheck_rewrite_gate.py").resolve()),
        "precheck_config": str((governance_dir / "precheck_rewrite_gate.config.json").resolve()),
        "protocol_doc": str(resolve_gate_doc(script_dir, "通用-受限重写防错协议.md")),
        "rewrite_prompt_doc": str(resolve_gate_doc(script_dir, "执行模板-受限重写提示词.md")),
        "failure_gate_doc": str(resolve_gate_doc(script_dir, "执行模板-失败即重写判定.md")),
        "execution_order": [
            "正文改写前，先跑 precheck_rewrite_gate.py 做结构预检。",
            "预检后，必须按 通用-受限重写防错协议 约束本轮改写范围。",
            "改完后，必须再按 执行模板-失败即重写判定 做失败裁决。",
            "命中任一硬失败项时，当前高风险段直接作废重写，不继续润句。",
        ],
        "hard_fail_focus": [
            "场面过于整齐",
            "高功能对白",
            "真相或重大信息闭环链过强",
            "同时完成的大任务过多",
            "检测切片下形成完整推进单元",
            "这一刀无法概括成一个主任务",
        ],
    }


def resolve_internal_standard_path(raw_path: str | None, script_dir: Path, source_file: Path) -> Path | None:
    if raw_path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (source_file.parent / candidate).resolve()
        else:
            candidate = candidate.resolve()
        return candidate
    project_local = source_file.parent / "profiles" / "internal_audit_standard.json"
    if project_local.exists():
        return project_local.resolve()
    default_path = (script_dir.parent / "references" / "internal_audit_standard.json").resolve()
    if default_path.exists():
        return default_path
    return None


def resolve_audit_paths(output_dir: Path, target_file: Path) -> tuple[Path, Path, Path]:
    stem = target_file.stem
    return (
        output_dir / f"{stem}.full_audit.json",
        output_dir / f"{stem}.full_audit.md",
        output_dir / f"{stem}.revision_plan.md",
    )


def ensure_audit(
    audit_script: Path,
    target_file: Path,
    output_dir: Path,
    profile: Path | None,
    internal_standard: Path | None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(audit_script), str(target_file), "--output-dir", str(output_dir)]
    if profile:
        cmd.extend(["--profile", str(profile)])
    if internal_standard:
        cmd.extend(["--internal-standard", str(internal_standard)])
    code, stdout, stderr = run(cmd)
    if code != 0:
        raise RuntimeError(f"审计失败:\nstdout:\n{stdout}\nstderr:\n{stderr}")
    audit_json, _, _ = resolve_audit_paths(output_dir, target_file)
    data = load_json(audit_json)
    data["audit_json_path"] = str(audit_json)
    return data


def top_bridge_issue(bridge_rule_audit: list[dict]) -> dict | None:
    for item in bridge_rule_audit:
        if item.get("must_keep_missing") or item.get("must_avoid_hit"):
            return item
    return None


def bridge_name_from_flag(flag: str) -> str:
    if not isinstance(flag, str):
        return ""
    marker = "同桥承重件不完整："
    return flag.split(marker, 1)[1].strip() if marker in flag else ""


def prioritize_bridge_items(bridge_items: list[dict], high_risk_segments: list[dict]) -> list[dict]:
    focused_names: list[str] = []
    for seg in high_risk_segments:
        for flag in seg.get("bridge_flags", []) or []:
            name = bridge_name_from_flag(flag)
            if name and name not in focused_names:
                focused_names.append(name)

    if not focused_names:
        return bridge_items

    focused = []
    others = []
    for item in bridge_items:
        title = str(item.get("title", ""))
        if any(name and name in title for name in focused_names):
            focused.append(item)
        else:
            others.append(item)
    return focused + others


def prioritize_bridge_audit(bridge_rule_audit: list[dict], high_risk_segments: list[dict]) -> list[dict]:
    focused_names: list[str] = []
    for seg in high_risk_segments:
        for flag in seg.get("bridge_flags", []) or []:
            name = bridge_name_from_flag(flag)
            if name and name not in focused_names:
                focused_names.append(name)

    if not focused_names:
        return bridge_rule_audit

    focused = []
    others = []
    for item in bridge_rule_audit:
        bridge = str(item.get("bridge", ""))
        if bridge in focused_names:
            focused.append(item)
        else:
            others.append(item)
    return focused + others


def audit_summary(data: dict) -> dict:
    light = data.get("light_summary", {})
    heavy = data.get("heavy_summary", {})
    proxy = (
        data.get("internal_proxy_summary")
        or data.get("external_block_audit_proxy_summary", {})
        or data.get(legacy_external_audit_key("proxy_summary"), {})
        or {}
    )
    return {
        "score": heavy.get("score"),
        "status": heavy.get("status"),
        "light_hits": light.get("total_hits"),
        "dialogue_blocks": light.get("over_effective_dialogue_blocks"),
        "opening_dialogue": light.get("opening_metrics", {}).get("dialogue_count"),
        "repeated_openings": heavy.get("repeated_opening_count"),
        "internal_overall_risk": proxy.get("overall_risk"),
        "internal_max_block_risk": proxy.get("max_block_risk"),
        "internal_judgement": (proxy.get("judgement") or {}).get("label"),
        "external_block_audit_weighted_avg": proxy.get("overall_risk"),
        "external_block_audit_max_seg": proxy.get("max_block_risk"),
        "external_block_audit_judgement": (proxy.get("judgement") or {}).get("label"),
        "sample_level": (data.get("sample_grading_guidance") or {}).get("level"),
        "sample_dna_usable": (data.get("sample_grading_guidance") or {}).get("dna_usable"),
    }


def compare_audits(prev: dict | None, curr: dict) -> list[str]:
    if not prev:
        return ["这是第一轮内部任务单，没有上一轮对比。"]
    prev_s = audit_summary(prev)
    curr_s = audit_summary(curr)
    keys = [
        ("score", "重审计分数"),
        ("light_hits", "轻审计命中"),
        ("dialogue_blocks", "高效对白块"),
        ("opening_dialogue", "开头对话数"),
        ("repeated_openings", "重复句首项"),
        ("internal_overall_risk", "内部整体风险分"),
        ("internal_max_block_risk", "内部最高块风险分"),
        ("internal_judgement", "内部过稿判定"),
        ("sample_level", "上游样本等级"),
        ("sample_dna_usable", "DNA可用性"),
    ]
    notes = []
    for key, label in keys:
        notes.append(f"{label}: {prev_s.get(key)} -> {curr_s.get(key)}")
    return notes


def build_segment_actions(flags: list[str], paragraph_range: list[int] | tuple[int, int]) -> list[str]:
    actions: list[str] = []
    flag_text = " ".join(flags)
    if "同桥承重件不完整" in flag_text:
        actions.append("先补这一片段缺失的桥段承重件，再动句子。")
    if "单场戏承担功能过多" in flag_text:
        actions.append("先拆这一片段里最拥挤的场戏，只保留一刀主功能，其余功能后移。")
    if "人物偏手没有立住" in flag_text:
        actions.append("给这一片段的核心人物补第一反应手势，不要让人物一上来就讲道理。")
    if "烂关系没有自己漏出来" in flag_text:
        actions.append("把关系坏改成站位、谁先护谁、谁先被照顾，不要只靠旧账说明。")
    if "公开场后果链不足" in flag_text:
        actions.append("公开场后立刻补秩序后果或现实后果，不要让片段停在打脸。")
    if not actions:
        actions.append("这一片段优先删整齐解释和高效对白，保留剧情骨架。")
    actions.append(f"只改段落 {paragraph_range[0]}-{paragraph_range[1]} 内的问题，不外溢改整篇。")
    return actions[:4]


def build_paragraph_actions(flags: list[str]) -> list[str]:
    actions: list[str] = []
    if "高效对白块" in flags:
        actions.append("把这段连续短对白拆进动作、停顿、旁人插话或手续件。")
    if "单场戏功能过多" in flags:
        actions.append("删掉这段里最会解释的那半句，只保留当前场景最值钱的一刀。")
    if "说明句偏强" in flags:
        actions.append("把说明句改成现场观察或动作结果，不要像案卷播报。")
    if "开头承压" in flags:
        actions.append("减少这一段首屏信息量，不要一段里交代两个以上关键事实。")
    if "短段对白密" in flags and not actions:
        actions.append("只在不影响桥段承重件时微调段落密度，不把短段当主问题。")
    if not actions:
        actions.append("这段只做局部压味，不改剧情，不扩写。")
    return actions[:3]


def task_priority_tuple(item: dict) -> tuple[int, int]:
    type_rank = {
        "global_shape_item": 6,
        "bridge_item": 5,
        "consequence_item": 4,
        "style_item": 3,
        "impact_item": 2,
    }
    priority_rank = {"P0": 2, "P1": 1}
    return (
        int(item.get("sample_bias_rank", 0)),
        type_rank.get(item.get("type", ""), 0),
        priority_rank.get(item.get("priority", "P1"), 0),
    )


def apply_sample_grading_task_bias(task: dict, guidance: dict) -> dict:
    level = guidance.get("level")
    negative_only_sources = guidance.get("negative_only_sources", [])
    skeleton_only_sources = guidance.get("skeleton_only_sources", [])
    task = dict(task)
    task["sample_bias_rank"] = 0
    task.setdefault("sample_bias_note", "")
    if level == "B类骨架样本":
        if task.get("type") in {"style_item", "impact_item"}:
            task["priority"] = "P1"
            task["sample_bias_rank"] = -2
            task["sample_bias_note"] = "上游是骨架样本：这类句法/抛光问题后置，先修桥段承重件、后果链和场面秩序。"
    elif level == "C类负样本":
        if task.get("type") in {"style_item", "impact_item"}:
            task["priority"] = "P1"
            task["sample_bias_rank"] = -3
            task["sample_bias_note"] = "上游是负样本：这类风格模仿任务不作为正向来源，先只处理桥段失真、秩序断裂和禁写点。"
    if task.get("type") == "bridge_item" and isinstance(negative_only_sources, list) and negative_only_sources:
        task["sample_bias_note"] = (
            task.get("sample_bias_note", "")
            + (" " if task.get("sample_bias_note") else "")
            + f"负样本来源只可反推禁写，不可直接复写其桥壳：{' / '.join(negative_only_sources[:4])}。"
        )
    if task.get("type") in {"style_item", "impact_item"} and isinstance(skeleton_only_sources, list) and skeleton_only_sources:
        task["sample_bias_note"] = (
            task.get("sample_bias_note", "")
            + (" " if task.get("sample_bias_note") else "")
            + f"骨架样本只供结构，不供句法：{' / '.join(skeleton_only_sources[:4])}。"
        )
    return task


def build_story_guardrail_guidance(profile: dict) -> dict:
    guardrails = profile.get("story_guardrails", {}) if isinstance(profile, dict) else {}
    if not isinstance(guardrails, dict):
        return {}
    out: dict[str, object] = {}
    face = guardrails.get("character_face_split", {})
    if isinstance(face, dict):
        face_out = {
            key: [item for item in values if isinstance(item, str)][:6]
            for key, values in face.items()
            if isinstance(values, list) and values
        }
        if face_out:
            out["character_face_split"] = face_out
    consequence = guardrails.get("consequence_structure", {})
    if isinstance(consequence, dict):
        consequence_out = {
            key: [item for item in values if isinstance(item, str)][:6]
            for key, values in consequence.items()
            if isinstance(values, list) and values
        }
        if consequence_out:
            out["consequence_structure"] = consequence_out
    return out


def build_story_guardrail_tasks(guardrails: dict) -> list[dict]:
    tasks: list[dict] = []
    consequence = guardrails.get("consequence_structure", {}) if isinstance(guardrails, dict) else {}
    if isinstance(consequence, dict):
        evidence = []
        if consequence.get("pre_evidence_reality_consequences"):
            evidence.append("重大证据前该隔开的现实后果: " + " / ".join(consequence["pre_evidence_reality_consequences"][:4]))
        if consequence.get("consequence_rebound_modes"):
            evidence.append("后果回灌方式: " + " / ".join(consequence["consequence_rebound_modes"][:4]))
        if consequence.get("tail_entry_owner"):
            evidence.append("尾声入口归属: " + " / ".join(consequence["tail_entry_owner"][:4]))
        if consequence.get("tail_entry_exclusion_reason"):
            evidence.append("尾声入口不给次线的原因: " + " / ".join(consequence["tail_entry_exclusion_reason"][:4]))
        if evidence:
            tasks.append(
                {
                    "type": "guardrail_item",
                    "priority": "P0",
                    "title": "高敏结构护栏：现实后果隔层与尾声入口",
                    "why": "这类桥最容易回弹成标准成品链。当前轮必须先确认重大证据前隔着现实后果，而不是只隔时间；尾声入口也不能被次线抢走。",
                    "evidence": evidence[:6],
                    "fix_methods": [
                        "重大证据前先补现实后果，不要只写‘过了几天’。",
                        "把次线收在余波区，不要在真尾声前再给它完整说开戏。",
                        "若尾声必须落主核，就删掉结尾前最完整的次线收口。 ",
                    ],
                }
            )
    face = guardrails.get("character_face_split", {}) if isinstance(guardrails, dict) else {}
    if isinstance(face, dict):
        evidence = []
        if face.get("different_face_evidence"):
            evidence.append("人物不同脸证据: " + " / ".join(face["different_face_evidence"][:4]))
        if face.get("reaction_order_split"):
            evidence.append("谁先解释谁先压场: " + " / ".join(face["reaction_order_split"][:4]))
        if face.get("action_authority_split"):
            evidence.append("动作权限差: " + " / ".join(face["action_authority_split"][:4]))
        if evidence:
            tasks.append(
                {
                    "type": "guardrail_item",
                    "priority": "P0",
                    "title": "高敏结构护栏：人物不能写回同一张脸",
                    "why": "不同位置的人不能只剩立场差，还要有权限差、动作差和节拍差。否则越改越像统一作者口气在分角色念台词。",
                    "evidence": evidence[:6],
                    "fix_methods": [
                        "先区分谁先压场、谁先解释、谁先办手上事务。",
                        "给关键人物补权限差，不要人人都先看着对方再说一句整齐的话。",
                        "删掉最像成熟解释模板的共用句壳。 ",
                    ],
                }
            )
    return tasks


def paragraph_priority_tuple(item: dict, segment_map: dict[int, dict]) -> tuple[int, int, int, float]:
    flags = item.get("flags", []) or []
    seg = segment_map.get(item.get("segment_index")) or {}
    has_bridge = 1 if seg.get("bridge_flags") else 0
    has_consequence = 1 if seg.get("consequence_flags") else 0
    short_only = flags and set(flags) <= {"短段对白密"}
    has_scene_core = 1 if any(flag in flags for flag in ("高效对白块", "单场戏功能过多", "开头承压", "多资产挤压", "说明句偏强")) else 0
    return (
        has_bridge,
        has_consequence,
        has_scene_core if not short_only else 0,
        float(item.get("risk_score", 0)),
    )


def global_shape_rank(shape: str) -> int:
    ranking = {
        "single_global_block": 3,
        "coarse_blocks": 2,
        "local_blocks": 1,
    }
    return ranking.get(shape, 0)


def normalize_global_risk_shape(global_risk_shape: dict | None) -> dict:
    data = global_risk_shape if isinstance(global_risk_shape, dict) else {}
    blocks = data.get("global_blocks", [])
    if not isinstance(blocks, list):
        blocks = []
    return {
        "shape": data.get("shape", "local_blocks"),
        "text_char_count": data.get("text_char_count"),
        "heavy_score": data.get("heavy_score"),
        "coarse_segment_count": data.get("coarse_segment_count"),
        "coarse_score_cv": data.get("coarse_score_cv"),
        "display_block_cv": data.get("display_block_cv"),
        "paragraph_high_ratio": data.get("paragraph_high_ratio"),
        "coarse_min_score": data.get("coarse_min_score"),
        "coarse_max_score": data.get("coarse_max_score"),
        "global_blocks": blocks,
    }


def build_global_shape_actions(shape_data: dict) -> list[str]:
    shape = shape_data.get("shape")
    if shape == "single_global_block":
        return [
            "整篇先按同一块来修，先重构主桥起手、顺序和场戏分工，不先修散点句子。",
            "优先拆掉一场戏里同时举证、判词、翻刀、交代后果的写法。",
            "先补人物偏手、关系权限和秩序件，让坏关系自己漏出来。",
            "等整篇大块压下去，再回头修局部高段和句面。",
        ]
    if shape == "coarse_blocks":
        return [
            "先按粗粒度正文块修，优先处理前 1-2 个高分粗块，不先散修全文。",
            "每个粗块先修桥段顺序、场戏功能和后果落地，再看局部句子。",
            "粗块内先补物件、手续、旁人插话和默认照顾关系，不先补情绪形容词。",
            "粗块压稳后，再处理残留热点段落。",
        ]
    return [
        "当前更像局部热点型，优先修正文高分块和对应段落。",
        "局部也先修桥段承重件和场戏功能，再做句面压味。",
    ]


def global_shape_task(shape_data: dict) -> dict | None:
    shape = shape_data.get("shape")
    if shape == "single_global_block":
        why = "当前不是几段句子假，而是整篇都带统一加工感。先修主桥和大场，才有机会把整篇从一个大块里拆出来。"
        title = "整篇大块先修：主桥顺序、场戏分工、人物偏手"
        priority = "P0"
    elif shape == "coarse_blocks":
        why = "当前不是单点失真，而是 1-2 个粗粒度正文块一起拉高整体风险。先处理这些大块，局部热点才会一起掉。"
        title = "粗块优先：先修前排大块，不先散修局部"
        priority = "P0"
    else:
        return None

    evidence = [
        f"全局形状: {shape_data.get('shape')}",
        f"粗窗数量: {shape_data.get('coarse_segment_count')}",
        f"粗窗离散度: {shape_data.get('coarse_score_cv')}",
        f"正文块离散度: {shape_data.get('display_block_cv')}",
        f"高风险段比例: {shape_data.get('paragraph_high_ratio')}",
    ]
    return {
        "type": "global_shape_item",
        "priority": priority,
        "title": title,
        "why": why,
        "evidence": [item for item in evidence if not item.endswith(": None")][:5],
        "fix_methods": build_global_shape_actions(shape_data),
    }


def coarse_segment_priority_tuple(item: dict) -> tuple[float, int, int]:
    flags = item.get("flags", []) or []
    has_bridge = 1 if any("同桥" in flag for flag in flags) else 0
    has_scene = 1 if any(flag in flags for flag in ("单场戏承担功能过多", "人物偏手没有立住", "烂关系没有自己漏出来")) else 0
    return (
        float(item.get("risk_score", 0)),
        has_bridge,
        has_scene,
    )


def build_coarse_block_actions(flags: list[str], shape: str) -> list[str]:
    actions: list[str] = []
    if any("同桥" in flag for flag in flags):
        actions.append("先按这块命中的同桥规则补起手、顺序和承重件，不先润句。")
    if "单场戏承担功能过多" in flags:
        actions.append("把这块里最挤的那场戏拆开，不要一场戏同时办四件事。")
    if "人物偏手没有立住" in flags:
        actions.append("让人物先按习惯反应做事，再说话，不要一开口就是结论。")
    if "烂关系没有自己漏出来" in flags:
        actions.append("把关系坏改成默认权限、站位和谁先被照顾。")
    if "说明句偏强" in flags:
        actions.append("把这块里的说明句改回手续、物件、旁人插话和动作结果。")
    if not actions:
        actions.append("先修这块的大场秩序和桥段结构，再动局部句子。")
    if shape == "single_global_block":
        actions.append("这块属于整篇大块的一部分，修改时要连同前后场的顺序一起看。")
    return actions[:4]


def bridge_task_from_audit(item: dict) -> dict:
    opening_missing = item.get("opening_pattern_missing", []) or []
    missing = item.get("must_keep_missing", []) or []
    avoid = item.get("must_avoid_hit", []) or []
    fake_hits = item.get("fake_signal_hit", []) or []
    sequence_missing = item.get("recommended_sequence_missing", []) or []
    sequence_out_of_order = item.get("recommended_sequence_out_of_order", []) or []
    evidence = []
    if item.get("opening_pattern_hit"):
        evidence.append("已命中起手件: " + " / ".join(item["opening_pattern_hit"][:4]))
    if opening_missing:
        evidence.append("缺失起手件: " + " / ".join(opening_missing[:4]))
    if item.get("must_keep_hit"):
        evidence.append("已命中承重件: " + " / ".join(item["must_keep_hit"][:6]))
    if missing:
        evidence.append("缺失承重件: " + " / ".join(missing[:6]))
    if item.get("recommended_sequence_hit"):
        evidence.append("已命中顺序件: " + " / ".join(item["recommended_sequence_hit"][:6]))
    if sequence_missing:
        evidence.append("缺失顺序件: " + " / ".join(sequence_missing[:6]))
    if sequence_out_of_order:
        evidence.append("顺序漂移: " + " / ".join(sequence_out_of_order[:4]))
    if avoid:
        evidence.append("踩中禁写点: " + " / ".join(avoid[:6]))
    if fake_hits:
        evidence.append("命中易假点: " + " / ".join(fake_hits[:6]))
    if item.get("why_order_matters"):
        evidence.append("顺序不能乱原因: " + " / ".join(item["why_order_matters"][:4]))
    why = item.get("why_original_passes", []) or []
    if why:
        evidence.append("原文能过关键: " + " / ".join(why[:4]))

    fix_methods = []
    if opening_missing:
        fix_methods.append("先补桥段开场方式，让场景先按原文起手，不要直接说结果。")
    if missing:
        fix_methods.append("不要先润句，先把桥段承重件补回来。")
        fix_methods.append("优先补物件、秩序件、位置件，不优先补情绪形容词。")
    if sequence_missing or sequence_out_of_order:
        fix_methods.append("按原桥段推荐顺序重排现场，不要把后果、审判或结论提前讲掉。")
    if avoid:
        fix_methods.append("先删禁写点，再看还缺哪些承重件。")
    if fake_hits:
        fix_methods.append("把易假写法删掉，恢复现场对话、插话、物件进入和秩序打断。")
    if why:
        fix_methods.append("把原文能过的原因落进现场顺序，而不是写成说明句。")

    return {
        "type": "bridge_item",
        "priority": "P0",
        "title": f"同桥承重件不完整：{item['bridge']}",
        "why": "不是桥段本身有问题，而是你在用这个桥时，缺了原文真正承重的那几件，结果只剩成品剧情壳。",
        "evidence": evidence[:6],
        "fix_methods": fix_methods[:4],
    }


def extract_bridge_names_from_flags(flags: list[str]) -> list[str]:
    names: list[str] = []
    for flag in flags or []:
        name = bridge_name_from_flag(flag)
        if name and name not in names:
            names.append(name)
    return names


def extract_bridge_name_from_title(title: str) -> str:
    marker = "同桥承重件不完整："
    if marker in title:
        return title.split(marker, 1)[1].strip()
    return ""


def build_task_validation(
    tasks: list[dict],
    segment_focus: list[dict],
    paragraph_focus: list[dict],
) -> dict:
    focused_segment_bridges: list[str] = []
    for item in segment_focus:
        for name in extract_bridge_names_from_flags(item.get("flags", [])):
            if name not in focused_segment_bridges:
                focused_segment_bridges.append(name)

    bridge_task_names: list[str] = []
    for item in tasks:
        if item.get("type") != "bridge_item":
            continue
        name = extract_bridge_name_from_title(str(item.get("title", "")))
        if name and name not in bridge_task_names:
            bridge_task_names.append(name)

    top_paragraph_short_only = []
    for item in paragraph_focus[:6]:
        flags = item.get("flags", []) or []
        if flags and set(flags) <= {"短段对白密"}:
            top_paragraph_short_only.append(item.get("paragraph_index"))

    hard_errors: list[str] = []
    warnings: list[str] = []
    if focused_segment_bridges:
        missing = [name for name in focused_segment_bridges[:3] if name not in bridge_task_names[:3]]
        if missing:
            hard_errors.append(
                "前排桥段任务没有覆盖高风险片段里的关键桥段: "
                + " / ".join(missing)
            )
    if top_paragraph_short_only:
        warnings.append("前排段落里出现了纯短段问题，说明排序可能回弹: " + " / ".join(map(str, top_paragraph_short_only)))

    return {
        "focused_segment_bridges": focused_segment_bridges,
        "bridge_task_names": bridge_task_names,
        "bridge_alignment_ok": not hard_errors,
        "short_paragraph_priority_ok": not top_paragraph_short_only,
        "hard_errors": hard_errors,
        "warnings": warnings,
    }


def profile_contract_errors(audit: dict) -> list[str]:
    if not audit.get("profile"):
        return []
    coverage = audit.get("asset_coverage", {})
    if not isinstance(coverage, dict):
        return ["已绑定 profile，但审计结果缺少 asset_coverage。"]

    errors: list[str] = []
    if not coverage.get("has_bridge_rules"):
        errors.append("已绑定 profile，但缺少 bridge_rules；必须重建拆书资产和 profile。")
    for field, label in (
        ("missing_scene_asset_keys", "scene_assets"),
        ("missing_style_asset_keys", "style_assets"),
        ("missing_story_guardrail_keys", "story_guardrails"),
    ):
        missing = coverage.get(field, [])
        if isinstance(missing, list) and missing:
            errors.append(
                f"已绑定 profile，但 {label} 缺失："
                + " / ".join(str(item) for item in missing)
            )
    return errors


def build_model_tasks(curr: dict, prev: dict | None) -> dict:
    impact_items = curr.get("external_block_audit_impact_items", curr.get(legacy_external_audit_key("impact_items"), []))
    high_risk_segments = curr.get("high_risk_segments", []) or []
    display_block_scores = curr.get("display_block_scores", []) or []
    style_items = curr.get("style_impact_items", [])
    consequence_items = curr.get("consequence_impact_items", [])
    recommendations = curr.get("recommendations", [])
    sample_grading_guidance = curr.get("sample_grading_guidance", {}) or {}
    bridge_audit = prioritize_bridge_audit(curr.get("bridge_rule_audit", []), high_risk_segments)
    bridge_issue = top_bridge_issue(bridge_audit)
    paragraph_scores = curr.get("paragraph_scores", []) or []
    global_risk_shape = normalize_global_risk_shape(curr.get("global_risk_shape"))
    coarse_segment_scores = curr.get("coarse_segment_scores", []) or []
    shape = global_risk_shape.get("shape", "local_blocks")
    story_guardrails = build_story_guardrail_guidance(curr.get("profile_payload", {}))

    tasks: list[dict] = []
    shape_task = global_shape_task(global_risk_shape)
    if shape_task:
        tasks.append(apply_sample_grading_task_bias(shape_task, sample_grading_guidance))
    for item in bridge_audit[:2]:
        if item.get("must_keep_missing") or item.get("must_avoid_hit"):
            tasks.append(apply_sample_grading_task_bias(bridge_task_from_audit(item), sample_grading_guidance))
    for item in build_story_guardrail_tasks(story_guardrails):
        tasks.append(apply_sample_grading_task_bias(item, sample_grading_guidance))
    for item in consequence_items[:2]:
        tasks.append(
            apply_sample_grading_task_bias(
            {
                "type": "consequence_item",
                "priority": item.get("priority", "P0"),
                "title": item.get("title"),
                "why": item.get("why_it_hits_audit"),
                "evidence": item.get("evidence", [])[:6],
                "fix_methods": item.get("fix_methods", [])[:4],
            },
            sample_grading_guidance,
            )
        )
    for item in style_items[:4]:
        tasks.append(
            apply_sample_grading_task_bias(
            {
                "type": "style_item",
                "priority": item.get("priority", "P0"),
                "title": item.get("title"),
                "why": item.get("why_it_hits_audit"),
                "evidence": item.get("evidence", [])[:6],
                "fix_methods": item.get("fix_methods", [])[:4],
            },
            sample_grading_guidance,
            )
        )
    for item in impact_items[:4]:
        tasks.append(
            apply_sample_grading_task_bias(
            {
                "type": "impact_item",
                "priority": item.get("priority", "P1"),
                "title": item.get("title"),
                "why": item.get("why_it_hits_audit"),
                "evidence": item.get("evidence", [])[:6],
                "fix_methods": item.get("fix_methods", [])[:4],
            },
            sample_grading_guidance,
            )
        )
    tasks.sort(key=task_priority_tuple, reverse=True)

    must_not = [
        "不要直接重写全篇。",
        "不要新增剧情来掩盖坏味。",
        "不要只换同义词。",
        "不要把桥段承重件写成说明句。",
        "不要把现场对话压成陈述或总结。",
    ]
    for item in sample_grading_guidance.get("hard_stops", [])[:4]:
        if item not in must_not:
            must_not.append(item)
    if bridge_issue and bridge_issue.get("must_avoid_hit"):
        must_not.append("先删已踩中的 must_avoid，再谈润句。")
    consequence_guard = story_guardrails.get("consequence_structure", {}) if isinstance(story_guardrails, dict) else {}
    if isinstance(consequence_guard, dict) and consequence_guard:
        must_not.append("不要把重大证据前的缓冲只写成时间空档，先补现实后果。")
        must_not.append("不要让次线在真尾声前吃掉完整说开戏或告别戏。")
    face_guard = story_guardrails.get("character_face_split", {}) if isinstance(story_guardrails, dict) else {}
    if isinstance(face_guard, dict) and face_guard:
        must_not.append("不要把不同角色写成同一套成熟解释口气。")

    focus = []
    if bridge_issue:
        focus.append(
            {
                "bridge": bridge_issue.get("bridge"),
                "must_keep_missing": bridge_issue.get("must_keep_missing", [])[:8],
                "must_avoid_hit": bridge_issue.get("must_avoid_hit", [])[:8],
                "why_original_passes": bridge_issue.get("why_original_passes", [])[:6],
            }
        )

    coarse_block_focus = []
    if shape in {"single_global_block", "coarse_blocks"}:
        coarse_limit = 1 if shape == "single_global_block" else 2
        top_coarse = sorted(
            coarse_segment_scores,
            key=coarse_segment_priority_tuple,
            reverse=True,
        )[:coarse_limit]
        for order, item in enumerate(top_coarse, start=1):
            flags = item.get("flags", [])[:8]
            coarse_block_focus.append(
                {
                    "revision_order": order,
                    "segment_index": item.get("segment_index"),
                    "risk_score": item.get("risk_score"),
                    "risk_level": item.get("risk_level"),
                    "paragraph_range": [item.get("paragraph_start"), item.get("paragraph_end")],
                    "char_range": [item.get("start_char"), item.get("end_char")],
                    "char_count": item.get("char_count"),
                    "flags": flags,
                    "actions": build_coarse_block_actions(flags, shape),
                    "excerpt": item.get("excerpt", ""),
                }
            )

    segment_focus = []
    for order, item in enumerate(high_risk_segments[:5], start=1):
        flags = (item.get("style_flags", []) + item.get("bridge_flags", []) + item.get("consequence_flags", []))[:8]
        paragraph_range = [item.get("paragraph_start"), item.get("paragraph_end")]
        segment_focus.append(
            {
                "revision_order": order,
                "segment_index": item.get("segment_index"),
                "risk_score": item.get("risk_score"),
                "risk_level": item.get("risk_level"),
                "paragraph_range": paragraph_range,
                "flags": flags,
                "actions": build_segment_actions(flags, paragraph_range),
                "excerpt": item.get("excerpt", ""),
            }
        )

    display_block_focus = []
    display_block_limit = 1 if shape == "single_global_block" else 2 if shape == "coarse_blocks" else 3
    top_blocks = sorted(
        display_block_scores,
        key=lambda x: float(x.get("risk_score", 0)),
        reverse=True,
    )[:display_block_limit]
    for order, item in enumerate(top_blocks, start=1):
        flags = item.get("flags", [])[:6]
        actions: list[str] = []
        if any("同桥" in flag for flag in flags):
            actions.append("先按这一正文块对应的同桥问题回补承重件和顺序，不先润句。")
        if "高效对白块" in flags:
            actions.append("先拆这块里的连续高效对白，不要让对白句句推进主线。")
        if "单场戏承担功能过多" in flags:
            actions.append("把这块里最拥挤的场戏拆开，避免一场戏同时举证、判词、翻刀。")
        if "说明句偏强" in flags:
            actions.append("把这块里的说明句改回现场观察、秩序件和动作结果。")
        if not actions:
            actions.append("先处理这一块的大块秩序问题，再往下修局部段落。")
        display_block_focus.append(
            {
                "revision_order": order,
                "block_index": item.get("block_index"),
                "risk_score": item.get("risk_score"),
                "paragraph_range": [item.get("paragraph_start"), item.get("paragraph_end")],
                "micro_count": item.get("micro_count"),
                "flags": flags,
                "actions": actions[:3],
                "hot_paragraphs": [
                    {
                        "paragraph_index": hot.get("paragraph_index"),
                        "risk_score": hot.get("risk_score"),
                        "flags": hot.get("flags", [])[:4],
                    }
                    for hot in item.get("hot_paragraphs", [])[:3]
                ],
            }
        )

    segment_map = {item.get("segment_index"): item for item in high_risk_segments}

    paragraph_focus = []
    paragraph_limit = 4 if shape == "single_global_block" else 6 if shape == "coarse_blocks" else 10
    ranked_paragraphs = sorted(
        paragraph_scores,
        key=lambda x: paragraph_priority_tuple(x, segment_map),
        reverse=True,
    )[:paragraph_limit]
    for order, item in enumerate(ranked_paragraphs, start=1):
        flags = item.get("flags", [])[:6]
        paragraph_focus.append(
            {
                "revision_order": order,
                "paragraph_index": item.get("paragraph_index"),
                "segment_index": item.get("segment_index"),
                "risk_score": item.get("risk_score"),
                "flags": flags,
                "actions": build_paragraph_actions(flags),
                "excerpt": item.get("excerpt", ""),
            }
        )

    task_validation = build_task_validation(tasks, segment_focus, paragraph_focus)
    task_validation["hard_errors"].extend(profile_contract_errors(curr))
    gate = rewrite_gate_bundle(Path(__file__).resolve().parent)

    return {
        "current_summary": audit_summary(curr),
        "global_risk_shape": global_risk_shape,
        "sample_grading_guidance": sample_grading_guidance,
        "story_guardrails": story_guardrails,
        "comparison": compare_audits(prev, curr),
        "recommendations": recommendations[:8],
        "coarse_block_focus": coarse_block_focus,
        "display_block_focus": display_block_focus,
        "segment_focus": segment_focus,
        "paragraph_focus": paragraph_focus,
        "focus_bridge": focus,
        "tasks": tasks,
        "must_not": must_not,
        "task_validation": task_validation,
        "rewrite_gate": gate,
    }


def markdown_task_card(source_file: Path, curr: dict, prev: dict | None, payload: dict) -> str:
    lines = [
        "# 下一轮模型改稿任务单",
        "",
        f"- 当前正文: `{source_file}`",
        f"- 当前审计 JSON: `{curr.get('audit_json_path')}`" if curr.get("audit_json_path") else "",
        f"- 使用 profile: `{curr.get('profile')}`" if curr.get("profile") else "- 使用 profile: `无`",
        "",
        "## 当前指标",
        "",
    ]
    summary = payload["current_summary"]
    for key in [
        "score",
        "status",
        "light_hits",
        "dialogue_blocks",
        "opening_dialogue",
        "repeated_openings",
        "internal_overall_risk",
        "internal_max_block_risk",
        "internal_judgement",
        "sample_level",
        "sample_dna_usable",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    shape_data = payload.get("global_risk_shape", {})
    lines.extend(["", "## 全局形状", ""])
    lines.append(f"- shape: `{shape_data.get('shape')}`")
    lines.append(f"- coarse_segment_count: `{shape_data.get('coarse_segment_count')}`")
    lines.append(f"- coarse_score_cv: `{shape_data.get('coarse_score_cv')}`")
    lines.append(f"- display_block_cv: `{shape_data.get('display_block_cv')}`")
    lines.append(f"- paragraph_high_ratio: `{shape_data.get('paragraph_high_ratio')}`")
    sample = payload.get("sample_grading_guidance", {})
    if sample:
        lines.extend(["", "## 上游样本准入", ""])
        if sample.get("summary"):
            lines.append(f"- 一句话判断: {sample.get('summary')}")
        if sample.get("learnable_layers"):
            lines.append(f"- 可学层: {' / '.join(sample.get('learnable_layers', [])[:6])}")
        if sample.get("forbidden_layers"):
            lines.append(f"- 禁学层: {' / '.join(sample.get('forbidden_layers', [])[:6])}")
        for item in sample.get("audit_notes", [])[:4]:
            lines.append(f"- 提示: {item}")
    guardrails = payload.get("story_guardrails", {})
    if guardrails:
        lines.extend(["", "## 高敏结构护栏", ""])
        consequence = guardrails.get("consequence_structure", {})
        if isinstance(consequence, dict):
            if consequence.get("pre_evidence_reality_consequences"):
                lines.append("- 重大证据前应先隔现实后果:")
                for item in consequence["pre_evidence_reality_consequences"][:4]:
                    lines.append(f"  - {item}")
            if consequence.get("consequence_rebound_modes"):
                lines.append("- 后果回灌方式:")
                for item in consequence["consequence_rebound_modes"][:4]:
                    lines.append(f"  - {item}")
            if consequence.get("tail_entry_owner"):
                lines.append("- 尾声入口归属:")
                for item in consequence["tail_entry_owner"][:4]:
                    lines.append(f"  - {item}")
        face = guardrails.get("character_face_split", {})
        if isinstance(face, dict):
            if face.get("different_face_evidence"):
                lines.append("- 人物不同脸证据:")
                for item in face["different_face_evidence"][:4]:
                    lines.append(f"  - {item}")
            if face.get("reaction_order_split"):
                lines.append("- 反应顺序差:")
                for item in face["reaction_order_split"][:4]:
                    lines.append(f"  - {item}")
            if face.get("action_authority_split"):
                lines.append("- 动作权限差:")
                for item in face["action_authority_split"][:4]:
                    lines.append(f"  - {item}")
    lines.extend(["", "## 和上一轮对比", ""])
    for note in payload["comparison"]:
        lines.append(f"- {note}")

    if payload.get("coarse_block_focus"):
        lines.extend(["", "## 先处理这些粗粒度大块", ""])
        for item in payload["coarse_block_focus"]:
            lines.append(
                f"- 顺序{item['revision_order']} 粗块{item['segment_index']}：分数 `{item['risk_score']}` "
                f"段落 `{item['paragraph_range'][0]}-{item['paragraph_range'][1]}` "
                f"字数 `{item['char_count']}`"
            )
            if item.get("flags"):
                lines.append(f"  - 风险标签: {' / '.join(item['flags'][:6])}")
            if item.get("actions"):
                lines.append(f"  - 执行口径: {' / '.join(item['actions'][:4])}")
            if item.get("excerpt"):
                lines.append(f"  - 摘录: {item['excerpt']}")

    lines.extend(["", "## 先处理这些正文块", ""])
    if payload.get("display_block_focus"):
        for item in payload["display_block_focus"]:
            lines.append(
                f"- 顺序{item['revision_order']} 正文块{item['block_index']}：分数 `{item['risk_score']}` "
                f"原始段 `{item['paragraph_range'][0]}-{item['paragraph_range'][1]}` "
                f"微切片 `{item['micro_count']}`"
            )
            if item.get("flags"):
                lines.append(f"  - 风险标签: {' / '.join(item['flags'][:6])}")
            if item.get("actions"):
                lines.append(f"  - 执行口径: {' / '.join(item['actions'][:3])}")
            if item.get("hot_paragraphs"):
                lines.append(
                    "  - 热点段落: "
                    + "；".join(
                        f"{hot['paragraph_index']}({hot['risk_score']})"
                        for hot in item["hot_paragraphs"][:3]
                    )
                )
    else:
        lines.append("- 当前没有正文块级风险结果。")

    lines.extend(["", "## 先处理这些片段", ""])
    if payload.get("segment_focus"):
        for item in payload["segment_focus"]:
            lines.append(
                f"- 顺序{item['revision_order']} 片段{item['segment_index']}：分数 `{item['risk_score']}` "
                f"段落 `{item['paragraph_range'][0]}-{item['paragraph_range'][1]}` "
                f"等级 `{item['risk_level']}`"
            )
            if item.get("flags"):
                lines.append(f"  - 风险标签: {' / '.join(item['flags'][:6])}")
            if item.get("actions"):
                lines.append(f"  - 执行口径: {' / '.join(item['actions'][:3])}")
            if item.get("excerpt"):
                lines.append(f"  - 摘录: {item['excerpt']}")
    else:
        lines.append("- 当前没有高风险片段结果。")

    lines.extend(["", "## 先看这些高风险段落", ""])
    if payload.get("paragraph_focus"):
        for item in payload["paragraph_focus"][:8]:
            lines.append(
                f"- 顺序{item['revision_order']} 段落{item['paragraph_index']}：分数 `{item['risk_score']}` "
                f"片段 `{item['segment_index']}`"
            )
            if item.get("flags"):
                lines.append(f"  - 局部标签: {' / '.join(item['flags'][:5])}")
            if item.get("actions"):
                lines.append(f"  - 执行口径: {' / '.join(item['actions'][:3])}")
            if item.get("excerpt"):
                lines.append(f"  - 摘录: {item['excerpt']}")
    else:
        lines.append("- 当前没有高风险段落结果。")

    lines.extend(["", "## 本轮最该改的点", ""])
    for task in payload["tasks"]:
        lines.append(f"### {task['title']}（{task['priority']}）")
        lines.append("")
        lines.append(f"- 为什么改: {task['why']}")
        if task.get("sample_bias_note"):
            lines.append(f"- 样本等级调度: {task['sample_bias_note']}")
        if task.get("evidence"):
            lines.append("- 证据:")
            for item in task["evidence"]:
                lines.append(f"  - {item}")
        if task.get("fix_methods"):
            lines.append("- 改法:")
            for item in task["fix_methods"]:
                lines.append(f"  - {item}")
        lines.append("")

    lines.extend(["## 同桥过检重点", ""])
    if payload["focus_bridge"]:
        for item in payload["focus_bridge"]:
            lines.append(f"- 当前最相关桥段: `{item['bridge']}`")
            if item.get("must_keep_missing"):
                lines.append("- 缺失 must_keep:")
                for x in item["must_keep_missing"]:
                    lines.append(f"  - {x}")
            if item.get("must_avoid_hit"):
                lines.append("- 已踩 must_avoid:")
                for x in item["must_avoid_hit"]:
                    lines.append(f"  - {x}")
            if item.get("why_original_passes"):
                lines.append("- 原文为什么能过:")
                for x in item["why_original_passes"]:
                    lines.append(f"  - {x}")
    else:
        lines.append("- 当前没有明确桥段缺件命中。")

    lines.extend(["", "## 不要这么改", ""])
    for item in payload["must_not"]:
        lines.append(f"- {item}")

    gate = payload.get("rewrite_gate", {})
    lines.extend(["", "## 写后自检闸门", ""])
    if gate:
        lines.append(f"- precheck_script: `{gate.get('precheck_script')}`")
        lines.append(f"- precheck_config: `{gate.get('precheck_config')}`")
        lines.append(f"- protocol_doc: `{gate.get('protocol_doc')}`")
        lines.append(f"- rewrite_prompt_doc: `{gate.get('rewrite_prompt_doc')}`")
        lines.append(f"- failure_gate_doc: `{gate.get('failure_gate_doc')}`")
        lines.append("- 执行顺序:")
        for item in gate.get("execution_order", []):
            lines.append(f"  - {item}")
        lines.append("- 硬失败重点:")
        for item in gate.get("hard_fail_focus", []):
            lines.append(f"  - {item}")
    else:
        lines.append("- 当前没有 gate 配置。")

    lines.extend(["", "## 给模型的执行口径", ""])
    if shape_data.get("shape") == "single_global_block":
        lines.append("- 当前是整篇大块型：先改主桥顺序、场戏分工、人物偏手和烂关系漏出，禁止先做句面回修。")
    elif shape_data.get("shape") == "coarse_blocks":
        lines.append("- 当前是粗块型：先压前 1-2 个粗块，再看正文块和局部段落。")
    else:
        lines.append("- 当前是局部热点型：先改同桥承重件和后果链，再改高风险片段，再改高风险段落，最后才处理通用 P0 / P1 问题。")
    lines.append("- 保留剧情骨架和关键桥段。")
    lines.append("- 短段只算末位节奏提醒，不能压过桥段失真、场戏过载和后果链断裂。")
    lines.append("- 先补桥段承重件、人物偏手、微动作和烂关系漏出，再改句子。")
    lines.append("- 改完后不要直接交稿，先过 写后自检闸门，再重新跑内部审计。")
    lines.extend(["", "## 任务单自检", ""])
    validation = payload.get("task_validation", {})
    lines.append(f"- bridge_alignment_ok: `{validation.get('bridge_alignment_ok')}`")
    lines.append(f"- short_paragraph_priority_ok: `{validation.get('short_paragraph_priority_ok')}`")
    if validation.get("focused_segment_bridges"):
        lines.append("- 高风险片段桥段:")
        for item in validation["focused_segment_bridges"]:
            lines.append(f"  - {item}")
    if validation.get("bridge_task_names"):
        lines.append("- 当前桥段任务:")
        for item in validation["bridge_task_names"]:
            lines.append(f"  - {item}")
    if validation.get("warnings"):
        lines.append("- 警告:")
        for item in validation["warnings"]:
            lines.append(f"  - {item}")
    lines.append("")
    return "\n".join([line for line in lines if line != ""])


def rewrite_gate_task_card(source_file: Path, payload: dict) -> str:
    gate = payload.get("rewrite_gate", {})
    segment_focus = payload.get("segment_focus", [])[:3]
    paragraph_focus = payload.get("paragraph_focus", [])[:5]
    lines = [
        "# 受限重写自检执行单",
        "",
        f"- 当前正文: `{source_file}`",
        f"- 协议文件: `{gate.get('protocol_doc')}`",
        f"- 预检脚本: `{gate.get('precheck_script')}`",
        f"- 预检配置: `{gate.get('precheck_config')}`",
        "",
        "## 这一步要做什么",
        "",
        "- 这不是继续自由润色。",
        "- 这是正文改写前的强制自检。",
        "- 只允许围绕当前高风险块、高风险片段和高风险段落改。",
        "- 不准顺手扩写整篇，不准顺手统一文风。",
        "",
        "## 本轮先看这些位置",
        "",
    ]
    if segment_focus:
        for item in segment_focus:
            lines.append(
                f"- 片段{item.get('segment_index')} 段落 {item.get('paragraph_range', ['?', '?'])[0]}-{item.get('paragraph_range', ['?', '?'])[1]} "
                f"风险 `{item.get('risk_score')}` 标签: {' / '.join(item.get('flags', [])[:6])}"
            )
    else:
        lines.append("- 当前没有片段级焦点，回到正文块和段落级焦点。")

    if paragraph_focus:
        lines.extend(["", "## 重点段落", ""])
        for item in paragraph_focus:
            lines.append(
                f"- 段落{item.get('paragraph_index')} 片段{item.get('segment_index')} "
                f"风险 `{item.get('risk_score')}` 标签: {' / '.join(item.get('flags', [])[:5])}"
            )

    lines.extend(["", "## 执行顺序", ""])
    for item in gate.get("execution_order", []):
        lines.append(f"- {item}")

    lines.extend(["", "## 本轮硬限制", ""])
    for item in payload.get("must_not", [])[:8]:
        lines.append(f"- {item}")

    lines.extend(["", "## 通过标准", ""])
    lines.append("- 当前高风险段改完后，不再明显命中：作者解释句、提前判断、高功能对白、整齐收口。")
    lines.append("- 当前高风险段不能再一刀完成多个主任务。")
    lines.append("- 当前高风险段不能再把桥段写成标准承载方式。")
    if payload.get("story_guardrails"):
        lines.append("- 当前高风险段必须再核对：现实后果隔层、尾声入口归属、人物不同脸。")
    lines.append("- 通过后才允许进入失败即重写判定。")
    lines.append("")
    return "\n".join(lines)


def failure_gate_task_card(source_file: Path, payload: dict) -> str:
    gate = payload.get("rewrite_gate", {})
    lines = [
        "# 失败即重写判定执行单",
        "",
        f"- 当前正文: `{source_file}`",
        f"- 判定文件: `{gate.get('failure_gate_doc')}`",
        "",
        "## 这一步要做什么",
        "",
        "- 当前改写完成后，不准先解释为什么这版还行。",
        "- 先按失败即重写判定逐条找证据。",
        "- 命中任一硬失败项，当前高风险段直接作废重写。",
        "",
        "## 本轮硬失败重点",
        "",
    ]
    for item in gate.get("hard_fail_focus", []):
        lines.append(f"- {item}")

    lines.extend(["", "## 输出要求", ""])
    lines.append("- 只判当前高风险段，不顺手点评整篇。")
    lines.append("- 只要出现明显违规，不准用“基本可用”之类模糊话术。")
    lines.append("- 如果失败，必须明确指出：最该删的句子、最该拆的对白、最该砍的收口。")
    if payload.get("story_guardrails"):
        lines.append("- 还必须指出：是不是只隔了时间没隔现实后果、是不是次线抢了尾声、是不是人物写回同脸。")
    lines.append("- 如果通过，才允许回到内部审计复跑。")
    lines.append("")
    return "\n".join(lines)


def gate_receipt_template(source_file: Path, payload: dict, gate_type: str) -> dict:
    gate = payload.get("rewrite_gate", {})
    docs = {
        "rewrite_gate": gate.get("protocol_doc"),
        "failure_gate": gate.get("failure_gate_doc"),
    }
    names = {
        "rewrite_gate": "受限重写自检",
        "failure_gate": "失败即重写判定",
    }
    protocol_doc = gate.get("protocol_doc")
    failure_doc = gate.get("failure_gate_doc")
    structured = (
        parse_rewrite_protocol_schema(Path(protocol_doc))
        if gate_type == "rewrite_gate" and protocol_doc
        else parse_failure_gate_schema(Path(failure_doc))
        if gate_type == "failure_gate" and failure_doc
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
        "reference_doc": docs.get(gate_type),
        "summary": summary,
        "structured_checks": structured,
        "notes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="待生成任务单的正文")
    parser.add_argument("--profile", help="可选：book/project profile JSON")
    parser.add_argument("--output-dir", default="auto_revise_runs", help="输出目录")
    parser.add_argument("--previous-audit-json", help="可选：上一轮 full_audit.json，用来做对比")
    parser.add_argument("--internal-standard", help="可选：内部审计标准 JSON，用于把内部风险分接入任务单")
    parser.add_argument("--external-block-audit-alignment-summary", help="外部分块审计对标摘要 JSON")
    args = parser.parse_args()

    source_file = Path(args.file).resolve()
    if not source_file.exists():
        print(f"文件不存在: {source_file}", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent
    audit_script = script_dir / "run_full_ai_audit.py"
    output_dir = Path(args.output_dir).resolve()
    profile = Path(args.profile).resolve() if args.profile else None
    internal_standard = resolve_internal_standard_path(args.internal_standard, script_dir, source_file)
    block_audit_alignment_summary = None
    if args.external_block_audit_alignment_summary:
        block_audit_alignment_summary = Path(args.external_block_audit_alignment_summary).resolve()

    curr = ensure_audit(
        audit_script,
        source_file,
        output_dir / "current_audit",
        profile,
        internal_standard or block_audit_alignment_summary,
    )
    prev = load_json(Path(args.previous_audit_json).resolve()) if args.previous_audit_json else None
    payload = build_model_tasks(curr, prev)
    hard_errors = payload.get("task_validation", {}).get("hard_errors", [])
    if hard_errors:
        print("rewrite_task_gate: blocked", file=sys.stderr)
        for error in hard_errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    stem = source_file.stem
    task_json = output_dir / f"{stem}.model_rewrite_task.json"
    task_md = output_dir / f"{stem}.model_rewrite_task.md"
    rewrite_gate_md = output_dir / f"{stem}.rewrite_gate_task.md"
    failure_gate_md = output_dir / f"{stem}.failure_gate_task.md"
    rewrite_gate_receipt = output_dir / f"{stem}.rewrite_gate_receipt.json"
    failure_gate_receipt = output_dir / f"{stem}.failure_gate_receipt.json"
    payload.setdefault("rewrite_gate", {})
    payload["rewrite_gate"]["task_artifacts"] = {
        "rewrite_gate_task_md": str(rewrite_gate_md),
        "failure_gate_task_md": str(failure_gate_md),
        "rewrite_gate_receipt_json": str(rewrite_gate_receipt),
        "failure_gate_receipt_json": str(failure_gate_receipt),
    }
    write_json(task_json, payload)
    write_text(task_md, markdown_task_card(source_file, curr, prev, payload))
    write_text(rewrite_gate_md, rewrite_gate_task_card(source_file, payload))
    write_text(failure_gate_md, failure_gate_task_card(source_file, payload))
    if not rewrite_gate_receipt.exists():
        write_json(rewrite_gate_receipt, gate_receipt_template(source_file, payload, "rewrite_gate"))
    if not failure_gate_receipt.exists():
        write_json(failure_gate_receipt, gate_receipt_template(source_file, payload, "failure_gate"))

    print("已输出:")
    print(f"- {task_json}")
    print(f"- {task_md}")
    print(f"- {rewrite_gate_md}")
    print(f"- {failure_gate_md}")
    print(f"- {rewrite_gate_receipt}")
    print(f"- {failure_gate_receipt}")
    print(f"- {output_dir / 'current_audit'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
