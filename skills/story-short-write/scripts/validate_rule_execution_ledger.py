#!/usr/bin/env python3
"""Build and validate the mandatory rule-execution ledger."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]

CORE_SKILL_RULE_FILES = (
    "SKILL.md",
    "references/workflow/format-and-structure.md",
    "references/anti-ai-writing.md",
    "references/craft/narrator-voice.md",
    "references/workflow/writing-workflow.md",
    "references/governance/audit-rulebook.json",
)

RULE_BEARING_ASSET_NAMES = {
    "作者DNA指纹.md",
    "仿写约束_禁写清单.md",
    "同桥段过检规则.md",
    "桥段施工卡.md",
    "高敏桥段识别.md",
    "本书动态信号字典.json",
    "book.profile.json",
    "project.profile.json",
}

SOURCE_CONTRACT_ASSET_NAMES = {
    "book.profile.json",
    "事实与推断台账.md",
    "可直接仿写_顺序事件表.md",
    "可直接仿写_后果链表.md",
    "可直接仿写_外部秩序表.md",
    "写作资产/作者DNA指纹.md",
    "写作资产/桥段施工卡.md",
    "写作资产/高敏桥段识别.md",
    "写作资产/同桥段过检规则.md",
    "写作资产/仿写约束_禁写清单.md",
    "写作资产/公开场_关键硬牌_后果.md",
    "写作资产/平台适配提醒.md",
    "写作资产/样本分级与可学层.md",
}

MANDATORY_MAIN_SOURCE_CONTRACT_NAMES = {
    "book.profile.json",
    "事实与推断台账.md",
    "可直接仿写_顺序事件表.md",
    "可直接仿写_后果链表.md",
    "可直接仿写_外部秩序表.md",
    "写作资产/作者DNA指纹.md",
    "写作资产/桥段施工卡.md",
    "写作资产/高敏桥段识别.md",
    "写作资产/同桥段过检规则.md",
    "写作资产/仿写约束_禁写清单.md",
    "写作资产/公开场_关键硬牌_后果.md",
    "写作资产/平台适配提醒.md",
    "写作资产/样本分级与可学层.md",
}

VALID_SOURCE_CONTRACT_DISPOSITIONS = {
    "applied",
    "not_selected",
    "prohibition_checked",
}

VALID_EXECUTION_MODES = {"script", "human", "hybrid"}
VALID_APPLICABILITY = {"applicable", "rejected", "not_applicable", "merged"}
VALID_STATUSES = {"pending", "completed"}
VALID_OUTCOMES = {"pending", "passed", "failed", "not_applicable"}
VALID_RULE_ROLES = {
    "workflow_gate",
    "format_check",
    "setting_constraint",
    "outline_constraint",
    "draft_constraint",
    "audit_check",
    "source_candidate",
    "source_prohibition",
}
VALID_REMEDIATION_TARGETS = {
    "workflow",
    "setting",
    "outline",
    "draft",
    "audit",
    "none",
}
ROLE_REMEDIATION_TARGETS = {
    "workflow_gate": {"workflow"},
    "format_check": {"draft", "audit"},
    "setting_constraint": {"setting"},
    "outline_constraint": {"outline"},
    "draft_constraint": {"draft"},
    "audit_check": {"audit"},
    "source_candidate": {"setting", "outline", "draft", "none"},
    "source_prohibition": {"draft", "audit"},
}

SCRIPT_HINTS = (
    "格式",
    "字数",
    "频率",
    "重复",
    "禁词",
    "禁写",
    "标点",
    "sha",
    "文件",
    "字段",
    "结构",
    "比例",
    "数量",
    "命中",
)
HYBRID_HINTS = (
    "节奏",
    "对白",
    "对话",
    "桥段",
    "相似",
    "覆盖",
    "长窗",
    "钩子",
    "顺序",
    "profile",
)
RULE_TEXT_HINTS = (
    "必须",
    "不得",
    "不允许",
    "禁止",
    "不能",
    "不要",
    "至少",
    "默认",
    "优先",
    "检查",
    "确认",
    "确保",
    "需要",
    "应该",
    "应当",
    "先",
    "再",
    "只",
    "写",
    "读",
    "通过",
    "回",
    "补",
    "删",
    "改",
    "保留",
    "避免",
    "运行",
    "生成",
    "绑定",
    "标记",
    "判断",
)
PROFILE_RULE_KEYS = {
    "opening_signal_groups",
    "opening_chain_patterns",
    "author_stance_patterns",
    "banned_phrases",
    "banned_regex",
    "bridge_rules",
    "scene_assets",
    "style_assets",
    "derived_patterns",
    "migration_assets",
    "precheck_overrides",
    "high_risk_layers",
    "source_noise_risk",
    "bridge_safety_warning",
    "story_guardrails",
    "sample_grading",
    "sample_source_buckets",
}


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, source_path: str, rule_text: str) -> str:
    digest = hashlib.sha1(
        f"{source_path}\0{rule_text}".encode("utf-8")
    ).hexdigest()[:12]
    return f"{prefix}-{digest}"


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalized_rule_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    return text.strip("|- ")


def looks_like_rule(text: str) -> bool:
    return any(hint in text for hint in RULE_TEXT_HINTS)


def extract_markdown_rules(text: str, strict: bool = False) -> list[str]:
    rules: list[str] = []
    seen: set[str] = set()
    lines = text.splitlines()
    for line_index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        candidate = ""
        checkbox = None
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not cells or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            next_line = lines[line_index + 1].strip() if line_index + 1 < len(lines) else ""
            if next_line.startswith("|") and all(
                re.fullmatch(r":?-{3,}:?", cell.strip())
                for cell in next_line.strip("|").split("|")
            ):
                continue
            candidate = " | ".join(cells)
        else:
            checkbox = re.match(r"^[-*+]\s+\[[ xX]\]\s+(.+)$", line)
            match = checkbox or re.match(r"^(?:[-*+]|\d+[.)])\s+(.+)$", line)
            if match:
                candidate = match.group(1)
        candidate = normalized_rule_text(candidate)
        if len(candidate) < 4 or candidate in seen:
            continue
        if strict and not checkbox and not looks_like_rule(candidate):
            continue
        seen.add(candidate)
        rules.append(candidate)
    return rules


def extract_heading_blocks(text: str, level: int = 2) -> list[str]:
    marker = "#" * level
    blocks: list[str] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(f"{marker} ") and not line.startswith(f"{marker}#"):
            if current:
                block = normalized_rule_text(" ".join(current))
                if block:
                    blocks.append(block)
            current = [line[len(marker) + 1 :]]
        elif current and line and line != "---":
            current.append(line)
    if current:
        block = normalized_rule_text(" ".join(current))
        if block:
            blocks.append(block)
    return blocks


def extract_numbered_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if re.match(r"^\d+[.)]\s+", line):
            if current:
                block = normalized_rule_text(" ".join(current))
                if block:
                    blocks.append(block)
            current = [line]
        elif current and line and not line.startswith("#") and line != "---":
            current.append(line)
        elif current and (line.startswith("#") or line == "---"):
            block = normalized_rule_text(" ".join(current))
            if block:
                blocks.append(block)
            current = []
    if current:
        block = normalized_rule_text(" ".join(current))
        if block:
            blocks.append(block)
    return blocks


def render_json_item(prefix: str, value: Any) -> str:
    rendered = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    )
    return normalized_rule_text(f"{prefix}: {rendered}")


def iter_named_json_items(prefix: str, value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield render_json_item(f"{prefix}.{key}", item)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield render_json_item(f"{prefix}[{index}]", item)
    elif value not in (None, ""):
        yield render_json_item(prefix, value)


def find_rule_objects(value: Any, prefix: str = "") -> Iterable[str]:
    if isinstance(value, dict):
        rules = value.get("rules")
        if isinstance(rules, list):
            for index, item in enumerate(rules):
                yield render_json_item(f"{prefix}.rules[{index}]".strip("."), item)
        for key, item in value.items():
            if key != "rules":
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                yield from find_rule_objects(item, child_prefix)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from find_rule_objects(item, f"{prefix}[{index}]")


def extract_json_rules(path: Path, data: Any) -> list[str]:
    name = path.name
    candidates: list[str] = []
    if name == "audit-rulebook.json":
        candidates.extend(find_rule_objects(data))
    elif name in {"book.profile.json", "project.profile.json"} and isinstance(data, dict):
        for key in PROFILE_RULE_KEYS:
            if key in data:
                candidates.append(render_json_item(key, data[key]))
    elif name == "本书动态信号字典.json" and isinstance(data, dict):
        categories = data.get("categories")
        if isinstance(categories, dict):
            candidates.extend(
                render_json_item(f"categories.{key}", value)
                for key, value in categories.items()
            )
    else:
        candidates.extend(find_rule_objects(data))

    rules: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if len(item) >= 4 and item not in seen:
            seen.add(item)
            rules.append(item)
    return rules


def extract_rules(path: Path) -> list[str]:
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError:
            return []
        return extract_json_rules(path, data)
    text = read_text(path)
    if path.name in {
        "桥段施工卡.md",
        "高敏桥段识别.md",
        "同桥段过检规则.md",
        "作者DNA指纹.md",
    }:
        return extract_heading_blocks(text)
    if path.name == "仿写约束_禁写清单.md":
        numbered = extract_numbered_blocks(text)
        checklist = [
            rule
            for rule in extract_markdown_rules(text)
            if rule.startswith("是否")
        ]
        return list(dict.fromkeys(numbered + checklist))
    strict = path.name in {"SKILL.md", "writing-workflow.md"}
    return extract_markdown_rules(text, strict=strict)


def extract_markdown_rule_families(path: Path) -> list[dict[str, Any]]:
    text = read_text(path)
    families: list[dict[str, Any]] = []
    current_heading = ""
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        block = "\n".join(current_lines)
        variants = extract_markdown_rules(block, strict=False)
        if not variants:
            return
        heading = current_heading or path.stem
        families.append(
            {
                "rule_text": f"{path.name}::{heading}",
                "variants": variants,
            }
        )

    for raw_line in text.splitlines():
        heading = re.match(r"^(#{2,3})\s+(.+)$", raw_line.strip())
        if heading:
            flush()
            current_heading = normalized_rule_text(heading.group(2))
            current_lines = []
            continue
        current_lines.append(raw_line)
    flush()

    if families:
        return families
    variants = extract_rules(path)
    if not variants:
        return []
    return [{"rule_text": f"{path.name}::{path.stem}", "variants": variants}]


def extract_json_rule_families(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        return []
    if path.name == "audit-rulebook.json" and isinstance(data, dict):
        families: list[dict[str, Any]] = []
        for section in data.get("sections", []):
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id") or section.get("label") or "").strip()
            variants = [
                render_json_item(f"{section_id}.rules[{index}]", item)
                for index, item in enumerate(section.get("rules", []))
            ]
            if section_id and variants:
                families.append(
                    {
                        "rule_text": f"{path.name}::{section_id}",
                        "variants": variants,
                    }
                )
        return families
    variants = extract_json_rules(path, data)
    if not variants:
        return []
    return [{"rule_text": f"{path.name}::资产规则族", "variants": variants}]


def extract_rule_families(
    path: Path,
    source_kind: str,
    relative_path: str = "",
) -> list[dict[str, Any]]:
    if source_kind == "asset_rule":
        variants = extract_rules(path)
        if not variants:
            return []
        family_name = Path(relative_path or path.name).name
        return [
            {
                "rule_text": f"拆书资产族::{family_name}",
                "variants": variants,
            }
        ]
    if path.suffix.lower() == ".json":
        return extract_json_rule_families(path)
    return extract_markdown_rule_families(path)


def is_rule_bearing_asset(relative_path: str) -> bool:
    name = Path(relative_path).name
    return name.startswith("可直接仿写_") or name in RULE_BEARING_ASSET_NAMES


def recommended_mode(rule_text: str) -> str:
    lowered = rule_text.lower()
    if any(hint in lowered for hint in HYBRID_HINTS):
        return "hybrid"
    if any(hint in lowered for hint in SCRIPT_HINTS):
        return "script"
    return "human"


def recommended_rule_role(
    source_path: str,
    rule_text: str,
    source_kind: str,
) -> str:
    name = Path(source_path).name
    lowered = rule_text.lower()
    if source_kind == "source_asset":
        return "source_candidate"
    if source_kind == "asset_rule":
        if name == "仿写约束_禁写清单.md" or any(
            hint in lowered for hint in ("禁止", "禁写", "不得", "不能照搬", "banned_")
        ):
            return "source_prohibition"
        return "source_candidate"
    if name == "format-and-structure.md":
        return "format_check"
    if name == "audit-rulebook.json":
        return "audit_check"
    if name in {"anti-ai-writing.md", "narrator-voice.md"}:
        return "draft_constraint"
    if any(hint in lowered for hint in ("设定.md", "人物设定", "设定阶段", "设定约束")):
        return "setting_constraint"
    if any(hint in lowered for hint in ("大纲", "细纲", "桥段顺序", "场序")):
        return "outline_constraint"
    if any(
        hint in lowered
        for hint in (
            "回执",
            "读取",
            "初始化",
            "绑定",
            "sha",
            "文件缺",
            "运行 ",
            "validate_",
            "gate",
            "台账",
            "执行顺序",
        )
    ):
        return "workflow_gate"
    if any(hint in lowered for hint in ("审计", "检查", "复核", "定位", "扫描", "检测")):
        return "audit_check"
    return "draft_constraint"


def default_remediation_target(rule_role: str) -> str:
    return {
        "workflow_gate": "workflow",
        "format_check": "audit",
        "setting_constraint": "setting",
        "outline_constraint": "outline",
        "draft_constraint": "draft",
        "audit_check": "audit",
        "source_candidate": "none",
        "source_prohibition": "audit",
    }[rule_role]


def blank_execution_fields(
    rule_text: str,
    source_path: str = "",
    source_kind: str = "skill_rule",
) -> dict[str, Any]:
    rule_role = recommended_rule_role(source_path, rule_text, source_kind)
    return {
        "execution_mode": recommended_mode(rule_text),
        "mode_confirmed": False,
        "rule_role": rule_role,
        "classification_confirmed": False,
        "classification_method": "script_suggestion",
        "classification_notes": "",
        "canonical_rule_text": "",
        "remediation_target": default_remediation_target(rule_role),
        "requires_text_change": False,
        "canonical_rule_id": "",
        "merged_into": "",
        "source_refs": [],
        "applicability": "pending",
        "status": "pending",
        "target_stage": "",
        "target_scene": "",
        "script_artifacts": [],
        "human_judgment": "",
        "text_evidence": [],
        "human_scope_reviews": [],
        "source_contract_reviews": [],
        "structural_claim_reviews": [],
        "decision_reason": "",
        "outcome": "pending",
        "result": "",
    }


def create_rule_entry(
    prefix: str,
    source_path: str,
    source_hash: str,
    rule_text: str,
    source_kind: str = "skill_rule",
    variants: list[str] | None = None,
) -> dict[str, Any]:
    rule_id = stable_id(prefix, source_path, rule_text)
    entry = {
        "id": rule_id,
        "source_path": source_path,
        "source_sha256": source_hash,
        "rule_text": rule_text,
        "cases": [
            {
                "source_path": source_path,
                "source_sha256": source_hash,
                "text": variant,
            }
            for variant in (variants or [rule_text])
        ],
        **blank_execution_fields(rule_text, source_path, source_kind),
    }
    entry["canonical_rule_id"] = rule_id
    entry["source_refs"] = [
        {
            "id": rule_id,
            "source_path": source_path,
            "source_sha256": source_hash,
        }
    ]
    return entry


def merge_exact_duplicate_rules(entries: list[dict[str, Any]]) -> None:
    canonical_by_text: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = normalized_rule_text(str(entry.get("rule_text") or ""))
        canonical = canonical_by_text.get(key)
        if canonical is None:
            canonical_by_text[key] = entry
            continue
        canonical_id = str(canonical["id"])
        canonical["source_refs"].extend(entry.get("source_refs", []))
        canonical["cases"].extend(entry.get("cases", []))
        entry.update(
            {
                "classification_confirmed": True,
                "classification_method": "exact_duplicate",
                "classification_notes": "规则族标签完全相同，自动归入 canonical。",
                "canonical_rule_id": canonical_id,
                "merged_into": canonical_id,
                "applicability": "merged",
                "status": "completed",
                "decision_reason": "与 canonical 规则完全重复，初始化时自动合并。",
                "outcome": "not_applicable",
                "result": f"由 {canonical_id} 统一执行。",
            }
        )


def load_receipt(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("gate_status") != "passed":
        raise ValueError(f"{label}尚未通过，不能初始化规则执行台账")
    return data


def create_ledger(
    project: str,
    writing_receipt_path: Path,
    source_receipt_path: Path,
    skill_root: Path = SKILL_ROOT,
    extra_skill_rule_files: list[Path] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    writing_receipt_path = writing_receipt_path.resolve()
    source_receipt_path = source_receipt_path.resolve()
    try:
        writing_receipt = load_receipt(writing_receipt_path, "写作规则读取回执")
        source_receipt = load_receipt(source_receipt_path, "拆文读取回执")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return {}, [str(exc)]

    if any(item.get("status") != "read" for item in writing_receipt.get("files", [])):
        errors.append("写作规则读取回执仍有未读文件")
    writing_entries = {
        str(item.get("path") or ""): item
        for item in writing_receipt.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }
    for relative in (
        "references/workflow/format-and-structure.md",
        "references/anti-ai-writing.md",
        "references/craft/narrator-voice.md",
    ):
        path = skill_root.resolve() / relative
        entry = writing_entries.get(relative)
        if not entry:
            errors.append(f"写作规则读取回执缺少当前强制规则: {path}")
        elif not path.is_file() or entry.get("sha256") != sha256(path):
            errors.append(f"写作规则读取回执已过期，必须重新读取: {path}")
    for source in source_receipt.get("sources", []):
        root = Path(str(source.get("root") or "")).resolve()
        for item in source.get("files", []):
            if item.get("status") != "read":
                errors.append(f"拆文读取回执仍有未读文件: {root / str(item.get('path') or '')}")
                continue
            path = root / str(item.get("path") or "")
            if not path.is_file() or item.get("sha256") != sha256(path):
                errors.append(f"拆文读取回执已过期，必须重新读取: {path}")
    if errors:
        return {}, errors

    resolved_skill_root = skill_root.resolve()
    skill_paths = [resolved_skill_root / relative for relative in CORE_SKILL_RULE_FILES]
    skill_paths.extend(path.resolve() for path in extra_skill_rule_files or [])
    unique_skill_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for path in skill_paths:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        if not path.is_file():
            errors.append(f"缺少 skill 规则文件: {path}")
            continue
        unique_skill_paths.append(path)
    if errors:
        return {}, errors

    skill_rules: list[dict[str, Any]] = []
    skill_rule_files: list[dict[str, Any]] = []
    for path in unique_skill_paths:
        source_path = str(path)
        source_hash = sha256(path)
        extracted = extract_rule_families(path, source_kind="skill_rule")
        skill_rule_files.append(
            {
                "path": source_path,
                "sha256": source_hash,
                "rule_count": len(extracted),
                "variant_count": sum(len(item["variants"]) for item in extracted),
            }
        )
        skill_rules.extend(
            create_rule_entry(
                "SKILL",
                source_path,
                source_hash,
                family["rule_text"],
                source_kind="skill_rule",
                variants=family["variants"],
            )
            for family in extracted
        )

    source_assets: list[dict[str, Any]] = []
    for source in source_receipt.get("sources", []):
        root = Path(str(source.get("root") or "")).resolve()
        for file_entry in source.get("files", []):
            relative = str(file_entry.get("path") or "")
            path = root / relative
            if not path.is_file():
                errors.append(f"拆书资产不存在: {path}")
                continue
            source_hash = sha256(path)
            expanded = (
                extract_rule_families(
                    path,
                    source_kind="asset_rule",
                    relative_path=relative,
                )
                if is_rule_bearing_asset(relative)
                else []
            )
            asset_id = stable_id("ASSET", str(path), relative)
            asset_execution = blank_execution_fields(
                f"拆书文件族::{relative}",
                str(path),
                source_kind="source_asset",
            )
            if not expanded:
                asset_execution.update(
                    {
                        "canonical_rule_id": asset_id,
                        "source_refs": [
                            {
                                "id": asset_id,
                                "source_path": str(path),
                                "source_sha256": source_hash,
                            }
                        ],
                        "cases": [
                            {
                                "source_path": str(path),
                                "source_sha256": source_hash,
                                "text": f"文件级拆书资产：{relative}",
                            }
                        ],
                    }
                )
            source_assets.append(
                {
                    "id": asset_id,
                    "source_name": str(source.get("name") or root.name),
                    "source_role": str(source.get("role") or ""),
                    "asset_path": str(path),
                    "relative_path": relative,
                    "sha256": source_hash,
                    "rule_expansion": "rule_level" if expanded else "file_level",
                    **asset_execution,
                    **({"rule_text": f"拆书文件族::{relative}"} if not expanded else {}),
                    "rules": [
                        create_rule_entry(
                            "ASSET-RULE",
                            str(path),
                            source_hash,
                            family["rule_text"],
                            source_kind="asset_rule",
                            variants=family["variants"],
                        )
                        for family in expanded
                    ],
                }
            )

    expanded_rules = list(skill_rules)
    for asset in source_assets:
        if asset["rules"]:
            expanded_rules.extend(asset["rules"])
        else:
            expanded_rules.append(asset)
    merge_exact_duplicate_rules(expanded_rules)

    ledger = {
        "version": "1.1",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "receipts": {
            "writing_rule_receipt": {
                "path": str(writing_receipt_path),
                "sha256": sha256(writing_receipt_path),
            },
            "source_read_receipt": {
                "path": str(source_receipt_path),
                "sha256": sha256(source_receipt_path),
            },
        },
        "artifacts": [],
        "execution_summary": {
            "script": 0,
            "human": 0,
            "hybrid": 0,
            "completed": 0,
            "rejected": 0,
            "not_applicable": 0,
            "merged": 0,
            "workflow_changes": 0,
            "setting_changes": 0,
            "outline_changes": 0,
            "draft_changes": 0,
            "audit_only": 0,
            "source_candidates": 0,
        },
        "skill_rule_files": skill_rule_files,
        "skill_rules": skill_rules,
        "source_assets": source_assets,
    }
    return ledger, errors


def bind_artifacts(ledger_path: Path, artifact_args: list[str]) -> list[str]:
    errors: list[str] = []
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    artifacts: list[dict[str, str]] = []
    for raw in artifact_args:
        if "=" not in raw:
            errors.append(f"artifact 参数必须是 名称=路径: {raw}")
            continue
        name, raw_path = raw.split("=", 1)
        path = Path(raw_path).resolve()
        if not name.strip() or not path.is_file():
            errors.append(f"写作产物不存在或名称为空: {raw}")
            continue
        artifacts.append(
            {
                "name": name.strip(),
                "path": str(path),
                "sha256": sha256(path),
            }
        )
    if errors:
        return errors
    data["artifacts"] = artifacts
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return []


def iter_execution_entries(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for entry in data.get("skill_rules", []):
        if isinstance(entry, dict):
            yield entry
    for asset in data.get("source_assets", []):
        if not isinstance(asset, dict):
            continue
        rules = asset.get("rules")
        if isinstance(rules, list) and rules:
            for entry in rules:
                if isinstance(entry, dict):
                    yield entry
        else:
            yield asset


def calculate_execution_summary(data: dict[str, Any]) -> dict[str, int]:
    summary = {
        "script": 0,
        "human": 0,
        "hybrid": 0,
        "completed": 0,
        "rejected": 0,
        "not_applicable": 0,
        "merged": 0,
        "workflow_changes": 0,
        "setting_changes": 0,
        "outline_changes": 0,
        "draft_changes": 0,
        "audit_only": 0,
        "source_candidates": 0,
    }
    for entry in iter_execution_entries(data):
        mode = entry.get("execution_mode")
        if mode in VALID_EXECUTION_MODES:
            summary[mode] += 1
        if entry.get("status") == "completed":
            summary["completed"] += 1
        applicability = entry.get("applicability")
        if applicability in {"rejected", "not_applicable"}:
            summary[applicability] += 1
        if applicability == "merged":
            summary["merged"] += 1
        role = entry.get("rule_role")
        if role == "audit_check":
            summary["audit_only"] += 1
        if role == "source_candidate":
            summary["source_candidates"] += 1
        if entry.get("outcome") == "failed":
            target = entry.get("remediation_target")
            change_key = {
                "workflow": "workflow_changes",
                "setting": "setting_changes",
                "outline": "outline_changes",
                "draft": "draft_changes",
            }.get(target)
            if change_key:
                summary[change_key] += 1
    return summary


def derive_rule_level_parent_status(asset: dict[str, Any]) -> dict[str, str]:
    rules = [item for item in asset.get("rules", []) if isinstance(item, dict)]
    if not rules:
        return {}

    total = len(rules)
    completed = sum(item.get("status") == "completed" for item in rules)
    applicable = [
        item for item in rules
        if item.get("applicability") == "applicable"
    ]
    failed = [item for item in applicable if item.get("outcome") == "failed"]
    unresolved = [
        item for item in rules
        if item.get("status") != "completed"
        or item.get("applicability") not in VALID_APPLICABILITY
        or (
            item.get("applicability") == "applicable"
            and item.get("outcome") not in {"passed", "failed"}
        )
    ]

    if unresolved:
        return {
            "applicability": "pending",
            "status": "pending",
            "decision_reason": f"由子规则自动汇总；尚有 {len(unresolved)}/{total} 条未完成裁决。",
            "outcome": "pending",
            "result": f"子规则完成 {completed}/{total}；父节点等待自动收口。",
        }
    if failed:
        return {
            "applicability": "applicable",
            "status": "completed",
            "decision_reason": "由子规则自动汇总；至少一条适用规则执行失败。",
            "outcome": "failed",
            "result": f"子规则已完成 {total}/{total}；失败 {len(failed)} 条，必须修复后重审。",
        }
    if applicable:
        return {
            "applicability": "applicable",
            "status": "completed",
            "decision_reason": "由子规则自动汇总；文件内存在已执行的适用规则。",
            "outcome": "passed",
            "result": f"子规则已完成 {total}/{total}；适用并通过 {len(applicable)} 条。",
        }
    return {
        "applicability": "not_applicable",
        "status": "completed",
        "decision_reason": "由子规则自动汇总；文件内规则均已合并或判定不适用。",
        "outcome": "not_applicable",
        "result": f"子规则已完成 {total}/{total}；本文件无独立适用规则。",
    }


def sync_rule_level_parent_statuses(data: dict[str, Any]) -> None:
    for asset in data.get("source_assets", []):
        if not isinstance(asset, dict) or not asset.get("rules"):
            continue
        asset.update(derive_rule_level_parent_status(asset))


def refresh_summary(ledger_path: Path) -> None:
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    sync_rule_level_parent_statuses(data)
    data["execution_summary"] = calculate_execution_summary(data)
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def export_model_review(
    ledger_path: Path,
    output_path: Path,
    batch_size: int,
) -> dict[str, int]:
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in iter_execution_entries(data)
        if not str(entry.get("merged_into") or "").strip()
    ]
    batches: list[dict[str, Any]] = []
    for start in range(0, len(entries), batch_size):
        items = []
        for entry in entries[start : start + batch_size]:
            items.append(
                {
                    "id": entry.get("id"),
                    "rule_text": entry.get("rule_text")
                    or entry.get("relative_path"),
                    "suggested_rule_role": entry.get("rule_role"),
                    "suggested_execution_mode": entry.get("execution_mode"),
                    "suggested_remediation_target": entry.get("remediation_target"),
                    "source_refs": entry.get("source_refs", []),
                    "cases": entry.get("cases", []),
                }
            )
        batches.append(
            {
                "batch": len(batches) + 1,
                "items": items,
            }
        )
    payload = {
        "version": "1.0",
        "ledger": str(ledger_path),
        "instructions": [
            "必须由当前写作模型逐族阅读 cases 后归纳 canonical_rule_text，脚本建议只能参考。",
            "剔除导航、示例、说明性材料时标 not_applicable，并写具体原因。",
            "语义近似规则合并到唯一 canonical，保留 source_refs 和全部 cases。",
            "source_candidate 是候选资产，不等于必须写入正文。",
            "只有失败的适用 draft_constraint 才能 requires_text_change=true。",
        ],
        "required_plan_fields": [
            "rule_role",
            "canonical_rule_text",
            "classification_confirmed=true",
            "classification_method=model_semantic_review",
            "classification_notes",
            "remediation_target",
            "execution_mode",
            "mode_confirmed=true",
            "applicability",
            "decision_reason",
        ],
        "batches": batches,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"entries": len(entries), "batches": len(batches)}


ALLOWED_PLAN_FIELDS = {
    "execution_mode",
    "mode_confirmed",
    "rule_role",
    "classification_confirmed",
    "classification_method",
    "classification_notes",
    "canonical_rule_text",
    "remediation_target",
    "requires_text_change",
    "canonical_rule_id",
    "merged_into",
    "source_refs",
    "applicability",
    "status",
    "target_stage",
    "target_scene",
    "script_artifacts",
    "human_judgment",
    "text_evidence",
    "human_scope_reviews",
    "source_contract_reviews",
    "structural_claim_reviews",
    "decision_reason",
    "outcome",
    "result",
}


def iter_plan_entries(data: dict[str, Any], scope: str) -> Iterable[dict[str, Any]]:
    if scope in {"skill_rules", "all_rules"}:
        for entry in data.get("skill_rules", []):
            if isinstance(entry, dict):
                yield entry
    if scope in {"source_assets", "all_entries"}:
        for asset in data.get("source_assets", []):
            if isinstance(asset, dict):
                yield asset
    if scope in {"asset_rules", "all_rules", "all_entries"}:
        for asset in data.get("source_assets", []):
            if not isinstance(asset, dict):
                continue
            for entry in asset.get("rules", []):
                if isinstance(entry, dict):
                    yield entry


def entry_matches(entry: dict[str, Any], selector: dict[str, Any]) -> bool:
    for key, expected in selector.items():
        if key == "source_path_contains":
            if str(expected) not in str(entry.get("source_path") or ""):
                return False
        elif key == "asset_path_contains":
            if str(expected) not in str(entry.get("asset_path") or entry.get("source_path") or ""):
                return False
        elif key == "relative_path_glob":
            if not fnmatch.fnmatch(str(entry.get("relative_path") or ""), str(expected)):
                return False
        elif key == "rule_text_contains":
            if str(expected) not in str(entry.get("rule_text") or ""):
                return False
        elif key == "id":
            if str(entry.get("id") or "") != str(expected):
                return False
        elif str(entry.get(key)) != str(expected):
            return False
    return True


def apply_decision_plan(ledger_path: Path, plan_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    operations = plan.get("operations") if isinstance(plan, dict) else None
    if not isinstance(operations, list) or not operations:
        return ["决策计划 operations 必须是非空列表"], []

    results: list[dict[str, Any]] = []
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            errors.append(f"operation[{index}] 必须是对象")
            continue
        scope = str(operation.get("scope") or "")
        if scope not in {
            "skill_rules",
            "source_assets",
            "asset_rules",
            "all_rules",
            "all_entries",
        }:
            errors.append(f"operation[{index}] scope 无效: {scope}")
            continue
        selector = operation.get("selector")
        updates = operation.get("set")
        rationale = str(operation.get("rationale") or "").strip()
        if not isinstance(selector, dict) or not selector:
            errors.append(f"operation[{index}] selector 必须是非空对象")
            continue
        if not isinstance(updates, dict) or not updates:
            errors.append(f"operation[{index}] set 必须是非空对象")
            continue
        unknown = sorted(set(updates) - ALLOWED_PLAN_FIELDS)
        if unknown:
            errors.append(f"operation[{index}] 含未知字段: {' / '.join(unknown)}")
            continue
        if not rationale:
            errors.append(f"operation[{index}] 缺少 rationale")
            continue

        matches = [
            entry
            for entry in iter_plan_entries(data, scope)
            if entry_matches(entry, selector)
        ]
        if not matches:
            errors.append(f"operation[{index}] 没有匹配任何执行项")
            continue
        for entry in matches:
            entry.update(updates)
            merged_into = str(entry.get("merged_into") or "").strip()
            if merged_into:
                entry.update(
                    {
                        "canonical_rule_id": merged_into,
                        "classification_confirmed": True,
                        "classification_method": "model_semantic_review",
                        "applicability": "merged",
                        "status": "completed",
                        "outcome": "not_applicable",
                        "result": f"由 {merged_into} 统一执行。",
                    }
                )
        results.append(
            {
                "operation": index,
                "matched": len(matches),
                "rationale": rationale,
            }
        )

    if errors:
        return errors, results
    rule_entries = {
        str(entry.get("id") or ""): entry
        for entry in iter_execution_entries(data)
        if entry.get("id")
    }
    for entry in rule_entries.values():
        merged_into = str(entry.get("merged_into") or "").strip()
        canonical = rule_entries.get(merged_into)
        if not merged_into or canonical is None:
            continue
        for field in ("source_refs", "cases"):
            existing = canonical.setdefault(field, [])
            seen = {
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for item in existing
            }
            for item in entry.get(field, []):
                key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if key not in seen:
                    existing.append(item)
                    seen.add(key)

    sync_rule_level_parent_statuses(data)
    data["execution_summary"] = calculate_execution_summary(data)
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return [], results


def apply_model_group_plan(
    ledger_path: Path,
    plan_path: Path,
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    groups = plan.get("groups") if isinstance(plan, dict) else None
    if not isinstance(groups, list) or not groups:
        return ["模型归并计划 groups 必须是非空列表"], []

    entries = {
        str(entry.get("id") or ""): entry
        for entry in iter_execution_entries(data)
        if entry.get("id")
    }
    claimed: set[str] = set()
    results: list[dict[str, Any]] = []
    required = {
        "canonical_id",
        "canonical_rule_text",
        "member_ids",
        "rule_role",
        "remediation_target",
        "execution_mode",
        "classification_notes",
    }
    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            errors.append(f"group[{index}] 必须是对象")
            continue
        missing = sorted(
            key for key in required
            if key not in group or group.get(key) in ("", [], None)
        )
        if missing:
            errors.append(f"group[{index}] 缺少字段: {' / '.join(missing)}")
            continue
        canonical_id = str(group["canonical_id"])
        member_ids = [str(item) for item in group["member_ids"]]
        if canonical_id not in member_ids:
            errors.append(f"group[{index}] canonical_id 必须包含在 member_ids")
            continue
        unknown = [rule_id for rule_id in member_ids if rule_id not in entries]
        if unknown:
            errors.append(f"group[{index}] 包含不存在的规则: {' / '.join(unknown)}")
            continue
        repeated = [rule_id for rule_id in member_ids if rule_id in claimed]
        if repeated:
            errors.append(f"group[{index}] 规则被多个语义组重复认领: {' / '.join(repeated)}")
            continue
        rule_role = str(group["rule_role"])
        remediation_target = str(group["remediation_target"])
        execution_mode = str(group["execution_mode"])
        if rule_role not in VALID_RULE_ROLES:
            errors.append(f"group[{index}] rule_role 无效: {rule_role}")
            continue
        if remediation_target not in ROLE_REMEDIATION_TARGETS[rule_role]:
            errors.append(f"group[{index}] 修复目标与规则角色不匹配")
            continue
        if execution_mode not in VALID_EXECUTION_MODES:
            errors.append(f"group[{index}] execution_mode 无效: {execution_mode}")
            continue

        canonical = entries[canonical_id]
        canonical.update(
            {
                "canonical_rule_id": canonical_id,
                "canonical_rule_text": str(group["canonical_rule_text"]).strip(),
                "rule_role": rule_role,
                "classification_confirmed": True,
                "classification_method": "model_semantic_review",
                "classification_notes": str(group["classification_notes"]).strip(),
                "remediation_target": remediation_target,
                "execution_mode": execution_mode,
                "mode_confirmed": True,
            }
        )
        for member_id in member_ids:
            claimed.add(member_id)
            if member_id == canonical_id:
                continue
            member = entries[member_id]
            for field in ("source_refs", "cases"):
                existing = canonical.setdefault(field, [])
                seen = {
                    json.dumps(item, ensure_ascii=False, sort_keys=True)
                    for item in existing
                }
                for item in member.get(field, []):
                    key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                    if key not in seen:
                        existing.append(item)
                        seen.add(key)
            member.update(
                {
                    "canonical_rule_id": canonical_id,
                    "merged_into": canonical_id,
                    "canonical_rule_text": "",
                    "classification_confirmed": True,
                    "classification_method": "model_semantic_review",
                    "classification_notes": str(group["classification_notes"]).strip(),
                    "applicability": "merged",
                    "status": "completed",
                    "decision_reason": f"归入多案例规则卡 {canonical_id}。",
                    "outcome": "not_applicable",
                    "result": f"由 {canonical_id} 统一执行。",
                }
            )
        # Exact duplicate merging may already have descendants pointing at a
        # member. Flatten every descendant directly to the final canonical.
        changed = True
        while changed:
            changed = False
            for descendant in entries.values():
                parent_id = str(descendant.get("merged_into") or "").strip()
                if parent_id in member_ids and parent_id != canonical_id:
                    descendant.update(
                        {
                            "canonical_rule_id": canonical_id,
                            "merged_into": canonical_id,
                            "result": f"由 {canonical_id} 统一执行。",
                        }
                    )
                    changed = True
        results.append(
            {
                "group": index,
                "canonical_id": canonical_id,
                "members": len(member_ids),
                "cases": len(canonical.get("cases", [])),
            }
        )

    if errors:
        return errors, results
    sync_rule_level_parent_statuses(data)
    data["execution_summary"] = calculate_execution_summary(data)
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return [], results


def validate_receipt_binding(info: Any, label: str, errors: list[str]) -> None:
    if not isinstance(info, dict):
        errors.append(f"缺少{label}绑定")
        return
    path = Path(str(info.get("path") or "")).resolve()
    if not path.is_file():
        errors.append(f"{label}不存在: {path}")
        return
    if info.get("sha256") != sha256(path):
        errors.append(f"{label}已变化，必须重新初始化规则执行台账")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(f"{label}不是有效 JSON")
        return
    if data.get("gate_status") != "passed":
        errors.append(f"{label}当前不是 passed")


def validate_script_artifacts(
    artifacts: Any,
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"{label}缺少脚本执行产物")
        return False
    valid = True
    for index, item in enumerate(artifacts, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}脚本产物格式错误[{index}]")
            valid = False
            continue
        path = Path(str(item.get("path") or "")).resolve()
        summary = str(item.get("summary") or "").strip()
        if not path.is_file():
            errors.append(f"{label}脚本产物不存在[{index}]: {path}")
            valid = False
        elif item.get("sha256") != sha256(path):
            errors.append(f"{label}脚本产物已变化[{index}]: {path}")
            valid = False
        if not summary:
            errors.append(f"{label}脚本产物缺少结果摘要[{index}]")
            valid = False
    return valid


def validate_text_evidence(
    evidence: Any,
    artifact_texts: dict[str, str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{label}缺少写作产物原句证据")
        return False
    valid = True
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}正文证据格式错误[{index}]")
            valid = False
            continue
        artifact = str(item.get("artifact") or "").strip()
        quote = str(item.get("quote") or "").strip()
        judgment = str(item.get("judgment") or "").strip()
        if artifact not in artifact_texts:
            errors.append(f"{label}引用了未绑定产物[{index}]: {artifact}")
            valid = False
        elif not quote or quote not in artifact_texts[artifact]:
            errors.append(f"{label}证据原句不在产物中[{index}]: {quote}")
            valid = False
        if not judgment:
            errors.append(f"{label}证据缺少逐项判断[{index}]")
            valid = False
    return valid


def validate_scope_reviews(
    reviews: Any,
    artifact_texts: dict[str, str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(reviews, list) or not reviews:
        return False
    valid = True
    for index, item in enumerate(reviews, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label}范围复核格式错误[{index}]")
            valid = False
            continue
        artifact = str(item.get("artifact") or "").strip()
        scope = str(item.get("scope") or "").strip()
        judgment = str(item.get("judgment") or "").strip()
        if artifact not in artifact_texts:
            errors.append(f"{label}范围复核引用未绑定产物[{index}]: {artifact}")
            valid = False
        if not scope:
            errors.append(f"{label}范围复核缺少检查范围[{index}]")
            valid = False
        if not judgment:
            errors.append(f"{label}范围复核缺少人工结论[{index}]")
            valid = False
    return valid


def normalized_contract_name(path: Path) -> str:
    parts = path.as_posix().split("/")
    if len(parts) >= 2 and parts[-2] == "写作资产":
        return f"写作资产/{parts[-1]}"
    return parts[-1]


def validate_source_contract_reviews(
    entry: dict[str, Any],
    source_roles: dict[str, str],
    artifact_texts: dict[str, str],
    label: str,
    errors: list[str],
) -> None:
    if entry.get("applicability") == "merged":
        return

    required_refs: dict[str, dict[str, Any]] = {}
    for ref in entry.get("source_refs", []):
        if not isinstance(ref, dict):
            continue
        source_path = Path(str(ref.get("source_path") or "")).resolve()
        contract_name = normalized_contract_name(source_path)
        if contract_name not in SOURCE_CONTRACT_ASSET_NAMES:
            continue
        required_refs[str(source_path)] = {
            "path": source_path,
            "contract_name": contract_name,
            "source_role": source_roles.get(str(source_path), ""),
        }
    if not required_refs:
        return

    reviews = entry.get("source_contract_reviews")
    if not isinstance(reviews, list):
        errors.append(f"{label} source_contract_reviews 必须是列表")
        reviews = []
    actual = {
        str(Path(str(item.get("source_path") or "")).resolve()): item
        for item in reviews
        if isinstance(item, dict) and item.get("source_path")
    }
    for source_path in sorted(set(required_refs) - set(actual)):
        errors.append(f"{label}缺少关键来源契约复核: {source_path}")
    for source_path in sorted(set(actual) - set(required_refs)):
        errors.append(f"{label}包含无关来源契约复核: {source_path}")

    for source_path, ref in required_refs.items():
        review = actual.get(source_path)
        if not review:
            continue
        path = ref["path"]
        if not path.is_file():
            errors.append(f"{label}关键来源契约文件不存在: {path}")
            continue
        if review.get("source_sha256") != sha256(path):
            errors.append(f"{label}关键来源契约 SHA 已变化: {path}")
        disposition = review.get("disposition")
        if disposition not in VALID_SOURCE_CONTRACT_DISPOSITIONS:
            errors.append(f"{label}关键来源契约未完成处置: {path}")
            continue
        quote = str(review.get("source_quote") or "").strip()
        judgment = str(review.get("judgment") or "").strip()
        if not quote or quote not in read_text(path):
            errors.append(f"{label}关键来源契约证据不在源文件中: {path}")
        if not judgment:
            errors.append(f"{label}关键来源契约缺少人工判断: {path}")

        if (
            ref["source_role"] == "main"
            and ref["contract_name"] in MANDATORY_MAIN_SOURCE_CONTRACT_NAMES
            and disposition == "not_selected"
        ):
            errors.append(f"{label}主体关键承重契约不得标记未选用: {path}")

        if disposition == "applied":
            validate_text_evidence(
                review.get("target_evidence"),
                artifact_texts,
                f"{label}关键来源契约 {path.name}",
                errors,
            )
        elif disposition == "prohibition_checked":
            if not validate_scope_reviews(
                review.get("scope_reviews"),
                artifact_texts,
                f"{label}关键来源禁止项 {path.name}",
                errors,
            ):
                errors.append(f"{label}关键来源禁止项缺少全文范围复核: {path}")
        else:
            reason = str(review.get("non_dependency_reason") or "").strip()
            if not reason:
                errors.append(f"{label}未选关键来源契约缺少无依赖理由: {path}")
            elif any(
                phrase in reason
                for phrase in ("本轮不需要", "未调用", "保留原", "暂不使用")
            ):
                errors.append(f"{label}未选关键来源契约理由过于宽泛: {path}")


def structural_targets(target_scene: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[、，,；;]|(?:以及)|(?:及)|(?:和)", target_scene)
        if item.strip()
    ]


def validate_structural_claim_reviews(
    entry: dict[str, Any],
    artifact_texts: dict[str, str],
    label: str,
    errors: list[str],
) -> None:
    if entry.get("rule_role") not in {"setting_constraint", "outline_constraint"}:
        return
    if entry.get("applicability") != "applicable":
        return
    targets = structural_targets(str(entry.get("target_scene") or ""))
    if not targets:
        return
    reviews = entry.get("structural_claim_reviews")
    if not isinstance(reviews, list):
        errors.append(f"{label} structural_claim_reviews 必须是列表")
        reviews = []
    actual = {
        str(item.get("target") or "").strip(): item
        for item in reviews
        if isinstance(item, dict) and str(item.get("target") or "").strip()
    }
    for target in sorted(set(targets) - set(actual)):
        errors.append(f"{label}结构结论缺少目标场景证据: {target}")
    for target in sorted(set(actual) - set(targets)):
        errors.append(f"{label}结构结论包含未声明目标: {target}")
    for target in targets:
        review = actual.get(target)
        if not review:
            continue
        validate_text_evidence(
            [review],
            artifact_texts,
            f"{label}结构目标 {target}",
            errors,
        )


def validate_merge_graph(
    entries: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    for rule_id, entry in entries.items():
        merged_into = str(entry.get("merged_into") or "").strip()
        if not merged_into:
            continue
        canonical = entries.get(merged_into)
        if canonical is None:
            errors.append(f"合并规则 {rule_id} 指向不存在的 canonical: {merged_into}")
            continue
        if merged_into == rule_id:
            errors.append(f"合并规则 {rule_id} 不能指向自身")
            continue
        if str(canonical.get("merged_into") or "").strip():
            errors.append(f"合并规则 {rule_id} 指向的 canonical 仍被合并: {merged_into}")
        if (
            canonical.get("status") != "completed"
            or canonical.get("outcome") not in {"passed", "not_applicable"}
        ):
            errors.append(f"合并规则 {rule_id} 的 canonical 尚未完成并裁决: {merged_into}")

        seen = {rule_id}
        cursor = entry
        while str(cursor.get("merged_into") or "").strip():
            next_id = str(cursor["merged_into"])
            if next_id in seen:
                errors.append(f"规则合并形成环: {rule_id} -> {next_id}")
                break
            seen.add(next_id)
            next_entry = entries.get(next_id)
            if next_entry is None:
                break
            cursor = next_entry


def validate_execution_entry(
    entry: dict[str, Any],
    label: str,
    artifact_texts: dict[str, str],
    errors: list[str],
) -> None:
    rule_role = entry.get("rule_role")
    if rule_role not in VALID_RULE_ROLES:
        errors.append(f"{label}缺少有效 rule_role")
        return
    if entry.get("classification_confirmed") is not True:
        errors.append(f"{label}尚未人工确认规则分类")
    classification_method = str(entry.get("classification_method") or "").strip()
    if classification_method not in {"model_semantic_review", "exact_duplicate"}:
        errors.append(f"{label}分类必须经过模型语义复核，不能只用脚本建议")
    if not str(entry.get("classification_notes") or "").strip():
        errors.append(f"{label}缺少分类与合并说明")
    if (
        classification_method == "model_semantic_review"
        and entry.get("applicability") != "merged"
        and not str(entry.get("canonical_rule_text") or "").strip()
    ):
        errors.append(f"{label}模型复核后缺少 canonical_rule_text")
    rule_id = str(entry.get("id") or "")
    canonical_rule_id = str(entry.get("canonical_rule_id") or "").strip()
    merged_into = str(entry.get("merged_into") or "").strip()
    if "rule_text" in entry:
        expected_canonical = merged_into or rule_id
        if canonical_rule_id != expected_canonical:
            errors.append(f"{label}canonical_rule_id 与合并关系不一致")
        if not isinstance(entry.get("source_refs"), list) or not entry.get("source_refs"):
            errors.append(f"{label}缺少 source_refs")
        if not isinstance(entry.get("cases"), list) or not entry.get("cases"):
            errors.append(f"{label}缺少 cases")
    remediation_target = entry.get("remediation_target")
    if remediation_target not in VALID_REMEDIATION_TARGETS:
        errors.append(f"{label}缺少有效 remediation_target")
    elif remediation_target not in ROLE_REMEDIATION_TARGETS[rule_role]:
        errors.append(
            f"{label}规则分类 {rule_role} 与修复目标 {remediation_target} 不匹配"
        )
    requires_text_change = entry.get("requires_text_change")
    if not isinstance(requires_text_change, bool):
        errors.append(f"{label}requires_text_change 必须是布尔值")
    elif requires_text_change and not (
        rule_role == "draft_constraint"
        and remediation_target == "draft"
        and entry.get("applicability") == "applicable"
        and entry.get("outcome") == "failed"
    ):
        errors.append(
            f"{label}只有失败的适用正文约束才能设置 requires_text_change=true"
        )

    applicability = entry.get("applicability")
    if applicability not in VALID_APPLICABILITY:
        errors.append(f"{label}未完成适用性判断")
        return
    if applicability == "merged":
        if not merged_into:
            errors.append(f"{label}标记 merged 但缺少 merged_into")
        if entry.get("status") != "completed":
            errors.append(f"{label}合并规则状态必须是 completed")
        if entry.get("outcome") != "not_applicable":
            errors.append(f"{label}合并规则 outcome 必须是 not_applicable")
        if not str(entry.get("decision_reason") or "").strip():
            errors.append(f"{label}合并规则缺少合并理由")
        return
    reason = str(entry.get("decision_reason") or "").strip()
    if applicability in {"rejected", "not_applicable"}:
        if not reason:
            errors.append(f"{label}跳过规则但未填写具体原因")
        if entry.get("status") != "completed":
            errors.append(f"{label}跳过规则但状态不是 completed")
        if entry.get("outcome") != "not_applicable":
            errors.append(f"{label}跳过规则时 outcome 必须为 not_applicable")
        if rule_role == "source_candidate" and applicability == "rejected":
            errors.append(f"{label}未采用的拆书候选应标 not_applicable，不应标 rejected")
        return

    mode = entry.get("execution_mode")
    if mode not in VALID_EXECUTION_MODES:
        errors.append(f"{label}执行方式必须是 script / human / hybrid")
        return
    if entry.get("mode_confirmed") is not True:
        errors.append(f"{label}尚未人工确认执行方式")
    if entry.get("status") != "completed":
        errors.append(f"{label}尚未标记执行完成")
    if not str(entry.get("target_stage") or "").strip():
        errors.append(f"{label}缺少目标阶段")
    if not str(entry.get("result") or "").strip():
        errors.append(f"{label}缺少执行结果")
    outcome = entry.get("outcome")
    if outcome not in {"passed", "failed"}:
        errors.append(f"{label}outcome 必须是 passed 或 failed")
    elif outcome == "failed":
        errors.append(f"{label}执行结果为 failed，必须修复后重新复核")

    if mode in {"script", "hybrid"}:
        validate_script_artifacts(entry.get("script_artifacts"), label, errors)
    if mode in {"human", "hybrid"}:
        if not str(entry.get("human_judgment") or "").strip():
            errors.append(f"{label}缺少人工语义判断")
        has_text_evidence = isinstance(entry.get("text_evidence"), list) and bool(
            entry.get("text_evidence")
        )
        has_scope_review = isinstance(entry.get("human_scope_reviews"), list) and bool(
            entry.get("human_scope_reviews")
        )
        needs_artifact_evidence = rule_role != "workflow_gate"
        if needs_artifact_evidence and not has_text_evidence and not has_scope_review:
            errors.append(f"{label}缺少正文原句证据或全文范围复核")
        if has_text_evidence:
            validate_text_evidence(entry.get("text_evidence"), artifact_texts, label, errors)
        if has_scope_review:
            validate_scope_reviews(
                entry.get("human_scope_reviews"),
                artifact_texts,
                label,
                errors,
            )
    validate_structural_claim_reviews(entry, artifact_texts, label, errors)


def validate_ledger(ledger_path: Path) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")

    receipts = data.get("receipts") if isinstance(data.get("receipts"), dict) else {}
    validate_receipt_binding(
        receipts.get("writing_rule_receipt"),
        "写作规则读取回执",
        errors,
    )
    validate_receipt_binding(
        receipts.get("source_read_receipt"),
        "拆文读取回执",
        errors,
    )

    artifact_texts: dict[str, str] = {}
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("必须绑定至少一个最终写作产物")
    else:
        for index, item in enumerate(artifacts, start=1):
            if not isinstance(item, dict):
                errors.append(f"写作产物绑定格式错误[{index}]")
                continue
            name = str(item.get("name") or "").strip()
            path = Path(str(item.get("path") or "")).resolve()
            if not name or not path.is_file():
                errors.append(f"写作产物不存在或名称为空[{index}]: {path}")
                continue
            if item.get("sha256") != sha256(path):
                errors.append(f"写作产物已变化，规则证据必须重新复核: {path}")
            artifact_texts[name] = read_text(path)

    skill_rule_files = data.get("skill_rule_files")
    expected_skill_rules: set[str] = set()
    if not isinstance(skill_rule_files, list) or not skill_rule_files:
        errors.append("缺少 skill_rule_files")
    else:
        for item in skill_rule_files:
            if not isinstance(item, dict):
                continue
            path = Path(str(item.get("path") or "")).resolve()
            if not path.is_file():
                errors.append(f"skill 规则源不存在: {path}")
                continue
            if item.get("sha256") != sha256(path):
                errors.append(f"skill 规则源已变化，必须重建台账: {path}")
            for family in extract_rule_families(path, source_kind="skill_rule"):
                expected_skill_rules.add(
                    stable_id("SKILL", str(path), family["rule_text"])
                )

    skill_rules = data.get("skill_rules")
    actual_skill: dict[str, dict[str, Any]] = {}
    if isinstance(skill_rules, list):
        actual_skill = {
            str(item.get("id") or ""): item
            for item in skill_rules
            if isinstance(item, dict) and item.get("id")
        }
    else:
        errors.append("skill_rules 必须是列表")
    for rule_id in sorted(expected_skill_rules - set(actual_skill)):
        errors.append(f"规则执行台账缺少 skill 规则: {rule_id}")
    for rule_id in sorted(set(actual_skill) - expected_skill_rules):
        errors.append(f"规则执行台账含过期 skill 规则: {rule_id}")

    all_rule_entries = {
        str(entry.get("id") or ""): entry
        for entry in iter_execution_entries(data)
        if isinstance(entry, dict) and entry.get("id")
    }
    validate_merge_graph(all_rule_entries, errors)

    counters = {
        "skill_rules": len(expected_skill_rules),
        "source_assets": 0,
        "asset_rules": 0,
        "script": 0,
        "human": 0,
        "hybrid": 0,
        "completed": 0,
    }
    for rule_id in expected_skill_rules:
        entry = actual_skill.get(rule_id)
        if not entry:
            continue
        validate_execution_entry(entry, f"skill 规则 {rule_id}", artifact_texts, errors)
        mode = entry.get("execution_mode")
        if mode in VALID_EXECUTION_MODES:
            counters[mode] += 1
        if entry.get("status") == "completed":
            counters["completed"] += 1

    source_assets = data.get("source_assets")
    if not isinstance(source_assets, list) or not source_assets:
        errors.append("source_assets 必须是非空列表")
        return errors, counters

    source_receipt_info = receipts.get("source_read_receipt", {})
    receipt_path = Path(str(source_receipt_info.get("path") or "")).resolve()
    expected_assets: dict[str, tuple[Path, str]] = {}
    if receipt_path.is_file():
        source_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        for source in source_receipt.get("sources", []):
            root = Path(str(source.get("root") or "")).resolve()
            for item in source.get("files", []):
                relative = str(item.get("path") or "")
                path = root / relative
                expected_assets[str(path)] = (path, relative)

    actual_assets = {
        str(item.get("asset_path") or ""): item
        for item in source_assets
        if isinstance(item, dict) and item.get("asset_path")
    }
    source_roles = {
        str(Path(path).resolve()): str(item.get("source_role") or "")
        for path, item in actual_assets.items()
    }
    for path in sorted(set(expected_assets) - set(actual_assets)):
        errors.append(f"规则执行台账缺少拆书文件: {path}")
    for path in sorted(set(actual_assets) - set(expected_assets)):
        errors.append(f"规则执行台账含过期拆书文件: {path}")

    for asset_path, (path, relative) in expected_assets.items():
        entry = actual_assets.get(asset_path)
        if not entry:
            continue
        counters["source_assets"] += 1
        if not path.is_file():
            errors.append(f"拆书资产不存在: {path}")
            continue
        if entry.get("sha256") != sha256(path):
            errors.append(f"拆书资产已变化，必须重建台账: {path}")

        rules = entry.get("rules")
        expected_rule_ids = {
            stable_id("ASSET-RULE", str(path), family["rule_text"])
            for family in (
                extract_rule_families(
                    path,
                    source_kind="asset_rule",
                    relative_path=relative,
                )
                if is_rule_bearing_asset(relative)
                else []
            )
        }
        actual_rules = {
            str(item.get("id") or ""): item
            for item in rules
            if isinstance(item, dict) and item.get("id")
        } if isinstance(rules, list) else {}
        for rule_id in sorted(expected_rule_ids - set(actual_rules)):
            errors.append(f"拆书资产缺少展开规则: {path} -> {rule_id}")
        for rule_id in sorted(set(actual_rules) - expected_rule_ids):
            errors.append(f"拆书资产含过期展开规则: {path} -> {rule_id}")

        if expected_rule_ids:
            expected_parent = derive_rule_level_parent_status(entry)
            for field in (
                "applicability",
                "status",
                "decision_reason",
                "outcome",
                "result",
            ):
                if entry.get(field) != expected_parent.get(field):
                    errors.append(
                        f"拆书规则级文件父节点未按子规则自动汇总: {path} -> {field}"
                    )
            if expected_parent.get("outcome") == "pending":
                errors.append(f"拆书规则级文件父节点尚未完成裁决: {path}")
            elif expected_parent.get("outcome") == "failed":
                errors.append(f"拆书规则级文件父节点包含失败子规则: {path}")
            for rule_id in expected_rule_ids:
                rule_entry = actual_rules.get(rule_id)
                if not rule_entry:
                    continue
                counters["asset_rules"] += 1
                validate_execution_entry(
                    rule_entry,
                    f"拆书规则 {path.name}/{rule_id}",
                    artifact_texts,
                    errors,
                )
                validate_source_contract_reviews(
                    rule_entry,
                    source_roles,
                    artifact_texts,
                    f"拆书规则 {path.name}/{rule_id}",
                    errors,
                )
                mode = rule_entry.get("execution_mode")
                if mode in VALID_EXECUTION_MODES:
                    counters[mode] += 1
                if rule_entry.get("status") == "completed":
                    counters["completed"] += 1
        else:
            validate_execution_entry(entry, f"拆书文件 {path}", artifact_texts, errors)
            validate_source_contract_reviews(
                entry,
                source_roles,
                artifact_texts,
                f"拆书文件 {path.name}",
                errors,
            )
            mode = entry.get("execution_mode")
            if mode in VALID_EXECUTION_MODES:
                counters[mode] += 1
            if entry.get("status") == "completed":
                counters["completed"] += 1

    expected_summary = calculate_execution_summary(data)
    if data.get("execution_summary") != expected_summary:
        errors.append("execution_summary 与逐项状态不一致，必须先运行 refresh-summary")

    return errors, counters


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mandatory rule-execution ledger gate for story-short-write."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化逐项规则执行台账")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--writing-receipt", required=True)
    init_parser.add_argument("--source-receipt", required=True)
    init_parser.add_argument("--ledger", required=True)
    init_parser.add_argument("--skill-rule-file", action="append", default=[])
    init_parser.add_argument("--force", action="store_true")

    bind_parser = subparsers.add_parser("bind-artifacts", help="绑定最终设定/大纲/正文")
    bind_parser.add_argument("--ledger", required=True)
    bind_parser.add_argument(
        "--artifact",
        action="append",
        required=True,
        help="名称=路径，可重复传入，例如 正文=/path/to/正文.md",
    )

    refresh_parser = subparsers.add_parser("refresh-summary", help="按逐项状态刷新执行汇总")
    refresh_parser.add_argument("--ledger", required=True)

    plan_parser = subparsers.add_parser("apply-plan", help="按可审计选择器批量回填逐项决策")
    plan_parser.add_argument("--ledger", required=True)
    plan_parser.add_argument("--plan", required=True)

    review_parser = subparsers.add_parser(
        "export-model-review",
        help="导出规则族，供当前写作模型逐族做语义分类与近义合并",
    )
    review_parser.add_argument("--ledger", required=True)
    review_parser.add_argument("--output", required=True)
    review_parser.add_argument("--batch-size", type=int, default=30)

    group_parser = subparsers.add_parser(
        "apply-model-groups",
        help="应用模型语义归并计划，生成一条规则、多来源案例的 canonical 规则卡",
    )
    group_parser.add_argument("--ledger", required=True)
    group_parser.add_argument("--plan", required=True)

    validate_parser = subparsers.add_parser("validate", help="校验逐项规则执行台账")
    validate_parser.add_argument("--ledger", required=True)

    args = parser.parse_args()
    ledger_path = Path(args.ledger).resolve()
    if args.command == "init":
        if ledger_path.exists() and not args.force:
            print(f"规则执行台账已存在，拒绝覆盖: {ledger_path}")
            return 2
        ledger, errors = create_ledger(
            args.project,
            Path(args.writing_receipt),
            Path(args.source_receipt),
            extra_skill_rule_files=[Path(raw) for raw in args.skill_rule_file],
        )
        if errors:
            print("rule_execution_gate: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("rule_execution_gate: initialized")
        print(f"ledger: {ledger_path}")
        print(f"skill_rules: {len(ledger['skill_rules'])}")
        print(f"source_assets: {len(ledger['source_assets'])}")
        print(
            "asset_rules: "
            f"{sum(len(item['rules']) for item in ledger['source_assets'])}"
        )
        print("- execution_mode 是建议分类，必须逐项确认 mode_confirmed。")
        return 0

    if not ledger_path.is_file():
        print(f"规则执行台账不存在: {ledger_path}")
        return 2
    if args.command == "bind-artifacts":
        errors = bind_artifacts(ledger_path, args.artifact)
        if errors:
            print("rule_execution_gate: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("rule_execution_gate: artifacts_bound")
        print(f"ledger: {ledger_path}")
        return 0
    if args.command == "refresh-summary":
        refresh_summary(ledger_path)
        print("rule_execution_gate: summary_refreshed")
        print(f"ledger: {ledger_path}")
        return 0
    if args.command == "apply-plan":
        errors, results = apply_decision_plan(ledger_path, Path(args.plan).resolve())
        for item in results:
            print(
                f"operation[{item['operation']}]: matched={item['matched']} "
                f"rationale={item['rationale']}"
            )
        if errors:
            print("rule_execution_gate: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("rule_execution_gate: plan_applied")
        print(f"ledger: {ledger_path}")
        return 0
    if args.command == "export-model-review":
        if args.batch_size < 1:
            print("batch-size 必须大于 0")
            return 2
        summary = export_model_review(
            ledger_path,
            Path(args.output).resolve(),
            args.batch_size,
        )
        print("rule_execution_gate: model_review_exported")
        print(f"entries: {summary['entries']}")
        print(f"batches: {summary['batches']}")
        print(f"output: {Path(args.output).resolve()}")
        return 0
    if args.command == "apply-model-groups":
        errors, results = apply_model_group_plan(
            ledger_path,
            Path(args.plan).resolve(),
        )
        for item in results:
            print(
                f"group[{item['group']}]: canonical={item['canonical_id']} "
                f"members={item['members']} cases={item['cases']}"
            )
        if errors:
            print("rule_execution_gate: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("rule_execution_gate: model_groups_applied")
        print(f"ledger: {ledger_path}")
        return 0

    errors, summary = validate_ledger(ledger_path)
    print(f"ledger: {ledger_path}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    if errors:
        print("rule_execution_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("rule_execution_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
