#!/usr/bin/env python3
"""Manage pre-write rules and sequential, direct-to-draft region reviews.

The script deterministically prepares only the current region's source sentence
context and verifies model-supplied reviews against real draft text. It does not
generate prose or make semantic judgments.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "story-short-write.rule-execution-ledger.v2"
DRAFT_SECTION_RE = re.compile(r"(?m)^(\d+)\.\s*$")
DRAFT_TITLE_RE = re.compile(r"(?m)^#[ \t]+.+?[ \t]*$")
SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?](?:[”」』])?|[^。！？!?\n]+$")
DIRECT_DIALOGUE_RE = re.compile(
    r"「[^」]*」(?:[^「」\n]{0,40}「[^」]*」)*|“[^”]*”(?:[^“”\n]{0,40}“[^”]*”)*"
)
OUTLINE_REGION_RE = re.compile(r"(?m)^##[ \t]+(导语|尾声|(\d+)\.)[ \t]*$")
SOURCE_MAP_RE = re.compile(r"<!--\s*source-map:\s*([^>]+?)\s*-->")
DESIGN_REVIEW_AXES = {
    "setting": (
        "title_promise",
        "fact_and_permission",
        "character_motivation",
        "real_world_operation",
        "causal_continuity",
        "source_boundary",
    ),
    "outline": (
        "entry_exit_state",
        "plot_emotion_whole_beat",
        "source_layer_mode",
        "information_acquisition",
        "physical_action_chain",
        "real_world_operation",
        "dialogue_plain_speech_risk",
        "future_region_leak",
    ),
}
RULE_HINTS = (
    "必须", "不得", "禁止", "不能", "至少", "检查", "确认", "保留",
    "回炉", "声线", "自然度", "指代", "首屏", "动作", "物件", "对白",
    "场面", "字数", "写前", "逐句", "全量", "真实",
)
GROUP_SPECS = (
    ("skill_text_rules", "SKILL.md", "draft", "正文首写与全局文字硬标准"),
    ("format_rules", "references/workflow/format-and-structure.md", "format", "平台格式与段落排版"),
    ("source_dominant_rules", "references/governance/source-dominant-first-draft.md", "draft", "主体声线和来源颗粒迁移"),
    ("liveliness_rules", "references/governance/prose-liveliness-layer.md", "draft", "活性资产与反僵硬写法"),
    ("narrator_voice_rules", "references/craft/narrator-voice.md", "draft", "叙述者距离、气口和语气"),
    ("character_voice_rules", "references/craft/character-voice-library.md", "draft", "人物口气、对白和指代"),
    ("emotion_rules", "references/craft/emotion-and-outcome-library.md", "draft", "情绪变化与现实后果"),
)

# Prose candidates must contain enacted particles, not a compressed outline
# wearing prose formatting.  These are deliberately narrow high-signal
# patterns; normal short sentences remain unrestricted.
SYNOPSIS_PROSE_PATTERNS = (
    re.compile(r"随后(?:，|就)?(?:发生|完成|处理|推进)"),
    re.compile(r"经过一番"),
    re.compile(r"最终(?:，|就)?(?:他们|两人|双方|事情)"),
    re.compile(r"两人关系(?:因此|从此)"),
    re.compile(r"完成(?:了)?(?:这一步|当前区域|控制变化)"),
    re.compile(r"获得或失去(?:了)?一项"),
)

PLAN_SYNOPSIS_PATTERNS = (
    re.compile(r"概括|总结|流程播报|完成控制变化|获得或失去一项"),
    re.compile(r"随后(?:处理|推进|发生)|最终(?:解决|完成)"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_numeric_sections(text: str) -> list[str]:
    lines = text.splitlines()
    markers: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\s*(\d+)(?:[.、．])?\s*", line)
        if match:
            markers.append((index, int(match.group(1))))
    numbers = [number for _, number in markers]
    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        return []
    return [
        "\n".join(
            lines[start + 1 : markers[pos + 1][0] if pos + 1 < len(markers) else len(lines)]
        )
        for pos, (start, _) in enumerate(markers)
    ]


def nonspace_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def validate_candidate_section_length(
    ledger_path: Path, region_id: str, candidate_text: str
) -> list[str]:
    """Block an under-length numeric candidate before it can be precommitted."""
    if not region_id.startswith("section:"):
        return []
    try:
        section_number = int(region_id.split(":", 1)[1])
        project_dir = ledger_path.parent.parent
        config_path = project_dir / "写作资产" / "项目写作配置.json"
        config = load(config_path)
        primary = config.get("primary") or {}
        original_path = resolve_config_path(
            config_path, str(primary.get("original_path") or "")
        )
        source_sections = source_numeric_sections(
            original_path.read_text(encoding="utf-8")
        )
        raw_policy = config.get("length_policy") or {}
        min_ratio = float(raw_policy.get("min_section_ratio", 0.90))
    except (OSError, ValueError, TypeError, IndexError, json.JSONDecodeError) as exc:
        return [f"无法执行候选分节锚定量校验: {exc}"]
    if not source_sections or section_number < 1 or section_number > len(source_sections):
        return [
            f"候选分节锚定量校验缺少主体第 {section_number} 节来源"
        ]
    source_chars = nonspace_count(source_sections[section_number - 1])
    candidate_chars = nonspace_count(candidate_text)
    required = math.ceil(source_chars * min_ratio)
    buffer = max(40, math.ceil(required * 0.05))
    target_floor = required + buffer
    if candidate_chars < target_floor:
        return [
            f"候选正文第 {section_number} 节低于主体分节施工下限: "
            f"candidate={candidate_chars}, required_min={required}, buffer={buffer}, "
            f"target_floor={target_floor}, primary={source_chars}, min_ratio={min_ratio:.2f}"
        ]
    return []


def section_length_metrics(
    ledger_path: Path, region_id: str
) -> dict[str, int | float] | None:
    if not region_id.startswith("section:"):
        return None
    section_number = int(region_id.split(":", 1)[1])
    project_dir = ledger_path.parent.parent
    config_path = project_dir / "写作资产" / "项目写作配置.json"
    config = load(config_path)
    primary = config.get("primary") or {}
    original_path = resolve_config_path(
        config_path, str(primary.get("original_path") or "")
    )
    sections = source_numeric_sections(original_path.read_text(encoding="utf-8"))
    if not sections or not (1 <= section_number <= len(sections)):
        return None
    source_chars = nonspace_count(sections[section_number - 1])
    min_ratio = float((config.get("length_policy") or {}).get("min_section_ratio", 0.90))
    required = math.ceil(source_chars * min_ratio)
    buffer = max(40, math.ceil(required * 0.05))
    return {
        "source_section_chars": source_chars,
        "required_min": required,
        "buffer": buffer,
        "target_floor": required + buffer,
        "min_ratio": min_ratio,
    }


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_cases(path: Path) -> list[dict[str, Any]]:
    lines = read_text(path).splitlines()
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text or text.startswith("```") or text.startswith("#"):
            continue
        if text.startswith("|"):
            parts = [part.strip() for part in text.strip("|").split("|")]
            if not parts or all(re.fullmatch(r":?-{3,}:?", part) for part in parts):
                continue
            text = " | ".join(parts)
        elif re.match(r"^[-*+]\s+", text):
            text = re.sub(r"^[-*+]\s+", "", text)
        elif re.match(r"^\d+[.)]\s+", text):
            text = re.sub(r"^\d+[.)]\s+", "", text)
        if len(text) < 8 or not any(hint in text for hint in RULE_HINTS):
            continue
        text = re.sub(r"\s+", " ", text).strip()
        if text in seen:
            continue
        seen.add(text)
        cases.append({"line": line_no, "text": text})
    return cases


def source_paths(skill_root: Path) -> list[Path]:
    return [skill_root / relative for _, relative, _, _ in GROUP_SPECS]


def split_draft_regions(text: str) -> tuple[dict[str, str], list[str]]:
    markers = list(DRAFT_SECTION_RE.finditer(text))
    prefix_end = markers[0].start() if markers else len(text)
    opening = DRAFT_TITLE_RE.sub("", text[:prefix_end], count=1).strip()
    regions = {"opening": opening}
    order = ["opening"]
    numbers = [int(match.group(1)) for match in markers]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"正文数字节必须从 1 连续排列: {numbers}")
    for index, match in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        region_id = f"section:{match.group(1)}"
        regions[region_id] = text[match.end() : end].strip()
        order.append(region_id)
    return regions, order


def outline_region_id(label: str, number: str | None) -> str:
    if label == "导语":
        return "opening"
    if label == "尾声":
        return "epilogue"
    return f"section:{int(number or '0')}"


def split_outline_regions(
    text: str, *, allow_single_region: bool = False
) -> tuple[dict[str, str], list[str], str]:
    markers = list(OUTLINE_REGION_RE.finditer(text))
    prefix = text[: markers[0].start()] if markers else text
    regions: dict[str, str] = {}
    order: list[str] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        region_id = outline_region_id(marker.group(1), marker.group(2))
        if region_id in regions:
            raise ValueError(f"小节大纲区域重复: {region_id}")
        regions[region_id] = text[marker.start() : end].strip()
        order.append(region_id)
    numeric = [value for value in order if value.startswith("section:")]
    expected_numeric = [f"section:{index}" for index in range(1, len(numeric) + 1)]
    if not (allow_single_region and len(order) == 1) and numeric != expected_numeric:
        raise ValueError(f"小节大纲数字区域必须从 section:1 连续排列: {numeric}")
    if order and order[0] != "opening" and not (allow_single_region and len(order) == 1):
        raise ValueError("小节大纲首个区域必须是 opening")
    if "epilogue" in order and order[-1] != "epilogue":
        raise ValueError("小节大纲 epilogue 后不得再出现其他区域")
    return regions, order, prefix.strip()


def outline_source_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in SOURCE_MAP_RE.finditer(text):
        for field in match.group(1).split(";"):
            if "=" not in field:
                continue
            key, raw_values = field.split("=", 1)
            for value in raw_values.split(","):
                normalized = f"{key.strip()}={value.strip()}"
                if value.strip():
                    refs.append(normalized)
    return refs


def next_outline_region(approved_ids: list[str], requested: str) -> bool:
    if not approved_ids:
        return requested == "opening"
    last = approved_ids[-1]
    if last == "opening":
        return requested == "section:1"
    if last == "epilogue" or not last.startswith("section:"):
        return False
    next_number = int(last.split(":", 1)[1]) + 1
    return requested in {f"section:{next_number}", "epilogue"}


def preflight_outline_candidate(
    project_dir: Path,
    existing_outline_text: str,
    candidate_text: str,
    approved_ids: list[str],
    current_order: list[str],
) -> list[str]:
    """Run the official in-memory outline preflight before accepting a candidate."""
    config_path = project_dir / "写作资产" / "项目写作配置.json"
    try:
        config = load(config_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(config.get("primary"), dict):
        # Legacy unit-test fixtures and pre-contract projects have no source map;
        # their existing critic checks remain authoritative.
        return []
    if current_order == approved_ids:
        prefix_text = existing_outline_text.rstrip()
    elif current_order == approved_ids + [current_order[-1]] and current_order[-1] not in approved_ids:
        markers = list(OUTLINE_REGION_RE.finditer(existing_outline_text))
        if len(markers) != len(current_order):
            return ["无法从正式大纲定位当前未确认区域"]
        prefix_text = existing_outline_text[: markers[len(approved_ids)].start()].rstrip()
    else:
        return ["正式大纲区域顺序不适合候选内存预检"]
    combined = f"{prefix_text}\n{candidate_text.strip()}" if prefix_text else candidate_text.strip()
    skill_root = Path(__file__).resolve().parents[1]
    module_path = skill_root / "scripts" / "manage_target_prose_map.py"
    spec = importlib.util.spec_from_file_location(
        "story_short_write_target_prose_map", module_path
    )
    if spec is None or spec.loader is None:
        return [f"无法加载正式目标脑图预检脚本: {module_path}"]
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        _, errors = module.preflight_outline_text(
            project_dir, combined, allow_partial=True
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"候选大纲内存预检失败: {exc}"]
    return [str(item) for item in errors]


def extract_sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in SENTENCE_RE.finditer(text) if match.group(0).strip()]


def extract_dialogues(text: str) -> list[str]:
    return [match.group(0) for match in DIRECT_DIALOGUE_RE.finditer(text)]


def expected_plan_regions(plans: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not isinstance(plans, list) or len(plans) < 3:
        return [], ["liveliness_rules.section_generation_plans 至少覆盖 opening、一个数字节和 epilogue"]
    region_ids = [
        str(plan.get("target_sections") or "")
        for plan in plans
        if isinstance(plan, dict)
    ]
    if len(region_ids) != len(plans):
        return [], ["liveliness_rules.section_generation_plans 每项必须是对象"]
    if not region_ids or region_ids[0] != "opening" or region_ids[-1] != "epilogue":
        errors.append("section_generation_plans 必须以 opening 开始、epilogue 结束")
    numeric = region_ids[1:-1]
    expected_numeric = [f"section:{index}" for index in range(1, len(numeric) + 1)]
    if numeric != expected_numeric:
        errors.append(
            "section_generation_plans 数字区域必须从 section:1 连续排列: "
            f"actual={numeric}"
        )
    return region_ids, errors


def liveliness_group(data: dict[str, Any]) -> dict[str, Any]:
    return next(
        (
            item
            for item in data.get("groups") or []
            if isinstance(item, dict) and item.get("rule_id") == "liveliness_rules"
        ),
        {},
    )


def empty_design_review_state() -> dict[str, Any]:
    return {
        "mode": "enforced",
        "setting": None,
        "outline_regions": [],
        "pending": None,
    }


def ensure_design_review_state(
    data: dict[str, Any], project_dir: Path
) -> dict[str, Any]:
    state = data.get("design_review_state")
    if isinstance(state, dict):
        return state
    setting_path = project_dir / "设定.md"
    outline_path = project_dir / "小节大纲.md"
    if setting_path.is_file() and outline_path.is_file():
        state = {
            "mode": "legacy_existing",
            "setting": {
                "path": str(setting_path.resolve()),
                "sha256": sha256(setting_path),
            },
            "outline": {
                "path": str(outline_path.resolve()),
                "sha256": sha256(outline_path),
            },
            "pending": None,
        }
    else:
        state = empty_design_review_state()
    data["design_review_state"] = state
    return state


def build_ledger(project: Path, skill_root: Path) -> dict[str, Any]:
    groups = []
    for rule_id, relative, category, scene in GROUP_SPECS:
        path = (skill_root / relative).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"规则来源不存在: {path}")
        groups.append(
            {
                "rule_id": rule_id,
                "source": {"path": str(path), "sha256": sha256(path)},
                "category": category,
                "target_phase": "prewrite",
                "target_scene": scene,
                "cases": extract_cases(path),
                "canonical_rule_text": "",
                "applicability": "",
                "execution_mode": "",
                "judgment": "",
                "status": "pending",
                "rule_use_plan": [],
                "active_assets": [],
                "section_generation_plans": [],
            }
        )
    return {
        "schema_version": SCHEMA,
        "project": project.name,
        "skill_root": str(skill_root.resolve()),
        "source_files": [
            {"path": str(path.resolve()), "sha256": sha256(path)}
            for path in source_paths(skill_root)
        ],
        "groups": groups,
        "prewrite_review": {
            "model_read_all_cases": False,
            "duplicate_rules_merged": False,
            "primary_voice_only": False,
            "auxiliary_voice_rejected": False,
            "prose_mode_policy": "",
            "synopsis_gate_confirmed": False,
            "judgment": "",
        },
        "design_review_state": empty_design_review_state(),
        "draft_review_state": {
            "expected_regions": [],
            "approved_regions": [],
            "prepared_region": None,
            "precommit_region": None,
            "feedback_cases": [],
            "status": "pending_prewrite",
        },
        "gate_status": "pending",
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"规则执行台账必须是 JSON 对象: {path}")
    return value


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"规则执行台账已存在，拒绝覆盖: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_prewrite_ledger(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = load(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    if data.get("schema_version") != SCHEMA:
        errors.append(f"schema_version 必须为 {SCHEMA}")
    skill_root = Path(str(data.get("skill_root") or "")).expanduser()
    if not skill_root.is_dir():
        errors.append(f"skill_root 不存在: {skill_root}")
        return errors
    expected_ids = [item[0] for item in GROUP_SPECS]
    groups = data.get("groups")
    if not isinstance(groups, list) or [item.get("rule_id") for item in groups if isinstance(item, dict)] != expected_ids:
        errors.append("groups 必须与正式规则来源同序全量对应")
        groups = []
    for item, spec in zip(groups, GROUP_SPECS):
        rule_id, relative, _, _ = spec
        label = rule_id
        source = item.get("source") if isinstance(item, dict) else None
        if not isinstance(source, dict):
            errors.append(f"{label}.source 必须是对象")
        else:
            source_path = Path(str(source.get("path") or "")).expanduser()
            if not source_path.is_file():
                errors.append(f"{label} 来源文件不存在: {source_path}")
            elif source.get("sha256") != sha256(source_path):
                errors.append(f"{label} 来源 SHA 已失效，必须重新 init")
            if source_path.resolve() != (skill_root / relative).resolve():
                errors.append(f"{label} source.path 与规则来源不一致")
        cases = item.get("cases") if isinstance(item, dict) else None
        if not isinstance(cases, list) or not cases:
            errors.append(f"{label}.cases 不能为空")
        for field in ("canonical_rule_text", "applicability", "execution_mode", "target_phase", "target_scene", "judgment"):
            if len(str(item.get(field) or "").strip()) < 4:
                errors.append(f"{label}.{field} 尚未完成写前分类")
        if item.get("applicability") not in {"applicable", "rejected", "not_applicable"}:
            errors.append(f"{label}.applicability 非法")
        if item.get("execution_mode") not in {"script", "human", "hybrid"}:
            errors.append(f"{label}.execution_mode 非法")
        if item.get("status") != "ready":
            errors.append(f"{label}.status 必须为 ready")
        plan = item.get("rule_use_plan")
        if not isinstance(plan, list) or not plan:
            errors.append(f"{label}.rule_use_plan 不能为空")
        else:
            for plan_item in plan:
                if not isinstance(plan_item, dict) or len(str(plan_item.get("target_sections") or "").strip()) < 2 or len(str(plan_item.get("execution_note") or "").strip()) < 8:
                    errors.append(f"{label}.rule_use_plan 每项必须写目标区域和执行说明")
        if rule_id == "liveliness_rules":
            assets = item.get("active_assets")
            required_categories = {
                "active_verb", "embodied_perception", "colloquial_interjection",
                "dialogue_rough_edge", "incomplete_sentence", "object_emotion_binding",
                "anti_polished_expression",
            }
            if not isinstance(assets, list) or len(assets) < 21:
                errors.append("liveliness_rules.active_assets 至少需要七类、每类三条主体原文资产")
            else:
                counts = {category: 0 for category in required_categories}
                for asset in assets:
                    if not isinstance(asset, dict):
                        continue
                    category = str(asset.get("category") or "")
                    if category in counts:
                        counts[category] += 1
                    for field in ("source_quote", "active_core", "migration_mechanism", "surface_boundary"):
                        if len(str(asset.get(field) or "").strip()) < 4:
                            errors.append(f"liveliness_rules.active_assets 缺少 {field}")
                    if asset.get("surface_copy_rejected") is not True:
                        errors.append("liveliness_rules.active_assets 必须确认 surface_copy_rejected=true")
                for category, count in counts.items():
                    if count < 3:
                        errors.append(f"liveliness_rules.active_assets.{category} 少于三条")
            plans = item.get("section_generation_plans")
            _, plan_errors = expected_plan_regions(plans)
            errors.extend(plan_errors)
            if not plan_errors:
                for index, plan in enumerate(plans, 1):
                    label = f"liveliness_rules.section_generation_plans[{index}]"
                    if not isinstance(plan, dict):
                        errors.append(f"{label} 必须是对象")
                        continue
                    liveliness_plan = plan.get("liveliness_plan")
                    if not isinstance(liveliness_plan, dict):
                        errors.append(f"{label}.liveliness_plan 必须是对象")
                    else:
                        assets_used = liveliness_plan.get("asset_ids_consumed")
                        if not isinstance(assets_used, list) or len(assets_used) < 4:
                            errors.append(f"{label}.liveliness_plan.asset_ids_consumed 至少绑定4条活性资产")
                        if len(set(str(value) for value in (assets_used or []))) < 4:
                            errors.append(f"{label}.liveliness_plan.asset_ids_consumed 不得重复")
                        if not isinstance(liveliness_plan.get("target_quotes"), list) or len(liveliness_plan["target_quotes"]) < 3:
                            errors.append(f"{label}.liveliness_plan.target_quotes 至少需要3条目标句计划")
                        for field in ("active_action", "body_perception", "dialogue_rough_edge", "object_binding", "narrator_interjection_position", "frozen_cut", "anti_stiffness_rejections", "explanatory_inference_review", "manual_judgment"):
                            if len(str(liveliness_plan.get(field) or "").strip()) < 8:
                                errors.append(f"{label}.liveliness_plan.{field} 尚未完成")
                        rejects = liveliness_plan.get("anti_stiffness_rejections")
                        if not isinstance(rejects, list) or len(rejects) < 3:
                            errors.append(f"{label}.liveliness_plan.anti_stiffness_rejections 至少拒绝3类僵硬句面")
                        if liveliness_plan.get("author_summary_override") is not False:
                            errors.append(f"{label}.liveliness_plan.author_summary_override 必须为 false")
                    for examples_field in ("positive_examples", "negative_examples"):
                        examples = plan.get(examples_field)
                        if not isinstance(examples, list) or len(examples) < 2:
                            errors.append(f"{label}.{examples_field} 至少需要2组连续例句")
    review = data.get("prewrite_review")
    if not isinstance(review, dict):
        errors.append("prewrite_review 必须是对象")
    else:
        for field in ("model_read_all_cases", "duplicate_rules_merged", "primary_voice_only", "auxiliary_voice_rejected", "synopsis_gate_confirmed"):
            if review.get(field) is not True:
                errors.append(f"prewrite_review.{field} 必须显式确认 true")
        if review.get("prose_mode_policy") != "scene_only_unless_source_layer_summary":
            errors.append(
                "prewrite_review.prose_mode_policy 必须为 "
                "scene_only_unless_source_layer_summary"
            )
        if len(str(review.get("judgment") or "").strip()) < 16:
            errors.append("prewrite_review.judgment 必须写总体裁决")
    state = data.get("draft_review_state")
    if not isinstance(state, dict):
        errors.append("draft_review_state 必须是对象")
    else:
        plan_regions, plan_errors = expected_plan_regions(
            liveliness_group(data).get("section_generation_plans")
        )
        if not plan_errors:
            expected_draft_regions = plan_regions[:-1]
            if state.get("expected_regions") != expected_draft_regions:
                errors.append("draft_review_state.expected_regions 与逐区计划不一致")
            errors.extend(
                validate_design_gate(data, path.parent.parent, plan_regions)
            )
        approved = state.get("approved_regions")
        if not isinstance(approved, list):
            errors.append("draft_review_state.approved_regions 必须是数组")
        elif [item.get("region_id") for item in approved if isinstance(item, dict)] != [
            str(value) for value in (state.get("expected_regions") or [])[: len(approved)]
        ]:
            errors.append("draft_review_state.approved_regions 必须是 expected_regions 连续前缀")
        feedback_cases = state.get("feedback_cases")
        if feedback_cases is None:
            state["feedback_cases"] = []
        elif not isinstance(feedback_cases, list):
            errors.append("draft_review_state.feedback_cases 必须是数组")
        else:
            actual_feedback_ids = [
                str(item.get("feedback_id") or "")
                for item in feedback_cases
                if isinstance(item, dict)
            ]
            if (
                len(actual_feedback_ids) != len(feedback_cases)
                or any(not value for value in actual_feedback_ids)
                or len(set(actual_feedback_ids)) != len(actual_feedback_ids)
            ):
                errors.append(
                    "draft_review_state.feedback_cases 每项必须有非空且唯一的动态 ID"
                )
        prepared = state.get("prepared_region")
        if prepared is not None:
            if not isinstance(prepared, dict):
                errors.append("draft_review_state.prepared_region 必须是对象或 null")
            else:
                expected_regions = [str(value) for value in state.get("expected_regions") or []]
                next_region = expected_regions[len(approved)] if len(approved) < len(expected_regions) else ""
                if prepared.get("region_id") != next_region:
                    errors.append("draft_review_state.prepared_region 不是当前唯一待写区域")
                if not str(prepared.get("context_sha256") or ""):
                    errors.append("draft_review_state.prepared_region 缺少 context_sha256")
        precommit = state.get("precommit_region")
        if precommit is not None:
            if not isinstance(precommit, dict):
                errors.append("draft_review_state.precommit_region 必须是对象或 null")
            else:
                expected_regions = [str(value) for value in state.get("expected_regions") or []]
                next_region = expected_regions[len(approved)] if len(approved) < len(expected_regions) else ""
                if precommit.get("region_id") != next_region:
                    errors.append("draft_review_state.precommit_region 不是当前唯一待写区域")
                if not str(precommit.get("candidate_sha256") or ""):
                    errors.append("draft_review_state.precommit_region 缺少 candidate_sha256")
                if not isinstance(precommit.get("review"), dict):
                    errors.append("draft_review_state.precommit_region 缺少盲审 review")
                if str(precommit.get("region_id") or "").startswith("section:"):
                    length_check = precommit.get("length_check")
                    if not isinstance(length_check, dict) or not all(
                        key in length_check for key in ("candidate_chars", "required_min", "buffer", "target_floor")
                    ):
                        errors.append("draft_review_state.precommit_region 缺少候选锚定量与缓冲记录")
    return errors


def apply_prewrite_reviews(path: Path, reviews: dict[str, Any]) -> None:
    data = load(path)
    groups = {str(item.get("rule_id")): item for item in data.get("groups") or [] if isinstance(item, dict)}
    expected = [item[0] for item in GROUP_SPECS]
    if list(reviews) != expected:
        raise ValueError("reviews 必须与规则组同序全量对应")
    for rule_id in expected:
        raw = reviews[rule_id]
        if not isinstance(raw, dict):
            raise ValueError(f"{rule_id} 复核必须是对象")
        item = groups[rule_id]
        for field in ("canonical_rule_text", "applicability", "execution_mode", "target_phase", "target_scene", "judgment"):
            value = str(raw.get(field) or "").strip()
            if len(value) < 4:
                raise ValueError(f"{rule_id}.{field} 不足")
            item[field] = value
        plan = raw.get("rule_use_plan")
        if not isinstance(plan, list) or not plan:
            raise ValueError(f"{rule_id}.rule_use_plan 不能为空")
        item["rule_use_plan"] = plan
        if rule_id == "liveliness_rules":
            assets = raw.get("active_assets")
            if not isinstance(assets, list):
                raise ValueError("liveliness_rules.active_assets 必须是数组")
            item["active_assets"] = assets
            plans = raw.get("section_generation_plans")
            if not isinstance(plans, list):
                raise ValueError("liveliness_rules.section_generation_plans 必须是数组")
            item["section_generation_plans"] = plans
        item["status"] = "ready"
    review = data.setdefault("prewrite_review", {})
    review.update({
        "model_read_all_cases": True,
        "duplicate_rules_merged": True,
        "primary_voice_only": True,
        "auxiliary_voice_rejected": True,
        "prose_mode_policy": "scene_only_unless_source_layer_summary",
        "synopsis_gate_confirmed": True,
        "judgment": "已逐组阅读全部规则案例；首写禁止梗概污染，只有来源本来是总结/公共传播/机构结果/传闻尾声的层才保留粗跳，辅助书仅提供事件机制，不进入声线。",
    })
    plan_regions, plan_errors = expected_plan_regions(
        groups["liveliness_rules"].get("section_generation_plans")
    )
    if plan_errors:
        raise ValueError(" / ".join(plan_errors))
    expected_draft_regions = plan_regions[:-1]
    state = data.setdefault("draft_review_state", {})
    approved = state.get("approved_regions") or []
    if approved and state.get("expected_regions") != expected_draft_regions:
        raise ValueError("已有逐区正文复核时不得改变 expected_regions")
    state.update({
        "expected_regions": expected_draft_regions,
        "approved_regions": approved,
        "prepared_region": state.get("prepared_region"),
        "status": "passed" if len(approved) == len(expected_draft_regions) else "ready",
    })
    data["gate_status"] = "pending"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh_rule_sources(path: Path) -> None:
    """Refresh deterministic rule bindings while preserving model-authored reviews."""
    data = load(path)
    skill_root = Path(str(data.get("skill_root") or "")).expanduser().resolve()
    if not skill_root.is_dir():
        raise ValueError(f"skill_root 不存在: {skill_root}")
    groups = {
        str(item.get("rule_id") or ""): item
        for item in data.get("groups") or []
        if isinstance(item, dict)
    }
    expected = [item[0] for item in GROUP_SPECS]
    if list(groups) != expected:
        raise ValueError("groups 与正式规则来源不一致，不能增量刷新")
    source_files = []
    for rule_id, relative, _, _ in GROUP_SPECS:
        source_path = (skill_root / relative).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"规则来源不存在: {source_path}")
        groups[rule_id]["source"] = {
            "path": str(source_path),
            "sha256": sha256(source_path),
        }
        groups[rule_id]["cases"] = extract_cases(source_path)
        source_files.append({"path": str(source_path), "sha256": sha256(source_path)})
    data["source_files"] = source_files
    ensure_design_review_state(data, path.parent.parent)
    data["gate_status"] = "pending"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_feedback_case(path: Path, raw: dict[str, Any]) -> str:
    data = load(path)
    state = data.setdefault("draft_review_state", {})
    cases = state.setdefault("feedback_cases", [])
    if not isinstance(cases, list):
        raise ValueError("draft_review_state.feedback_cases 必须是数组")
    values = {}
    for field in ("source_region", "original_quote", "issue", "preferred_direction"):
        value = str(raw.get(field) or "").strip()
        if len(value) < 4:
            raise ValueError(f"feedback.{field} 必须写具体内容")
        values[field] = value
    for item in cases:
        if (
            isinstance(item, dict)
            and item.get("source_region") == values["source_region"]
            and item.get("original_quote") == values["original_quote"]
            and item.get("issue") == values["issue"]
        ):
            return str(item.get("feedback_id") or "")
    feedback_id = "feedback-" + text_sha256(
        json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    cases.append({"feedback_id": feedback_id, **values})
    data["gate_status"] = "pending"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return feedback_id


def parse_review_input(value: str, file_value: str | None) -> dict[str, Any]:
    raw = (
        sys.stdin.read()
        if file_value == "/dev/stdin"
        else Path(file_value).read_text(encoding="utf-8")
        if file_value
        else value
    )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("review JSON 顶层必须是对象")
    return payload


def validate_design_critic_review(
    review: dict[str, Any],
    candidate_text: str,
    ledger_data: dict[str, Any],
    artifact: str,
    region_id: str,
) -> list[str]:
    errors: list[str] = []
    valid_rule_refs = {
        f"{group.get('rule_id')}:{case.get('line')}"
        for group in ledger_data.get("groups") or []
        if isinstance(group, dict)
        for case in group.get("cases") or []
        if isinstance(case, dict)
    }
    if review.get("artifact") != artifact:
        errors.append(f"design_review.artifact 必须为 {artifact}")
    if review.get("region_id") != region_id:
        errors.append(f"design_review.region_id 必须为 {region_id}")
    for field in (
        "critic_context_isolated",
        "diagnostic_only_first_pass",
        "author_intent_ignored",
        "model_read_final_candidate",
    ):
        if review.get(field) is not True:
            errors.append(f"design_review.{field} 必须显式为 true")
    rule_refs = review.get("rule_refs_considered")
    if (
        not isinstance(rule_refs, list)
        or not rule_refs
        or any(str(value) not in valid_rule_refs for value in rule_refs)
    ):
        errors.append("design_review.rule_refs_considered 必须引用当前台账真实规则 case")
    source_refs = review.get("source_refs_considered")
    if artifact == "outline":
        expected_refs = outline_source_refs(candidate_text)
        if not expected_refs:
            errors.append("大纲区域候选必须包含 source-map 来源声明")
        if source_refs != expected_refs:
            errors.append(
                "design_review.source_refs_considered 必须全量同序覆盖当前区域 source-map 声明"
            )
    elif not isinstance(source_refs, list) or not source_refs:
        errors.append("设定 critic 必须列出实际消费的项目配置或来源资产引用")
    else:
        for index, source_ref in enumerate(source_refs, 1):
            label = f"design_review.source_refs_considered[{index}]"
            if not isinstance(source_ref, dict):
                errors.append(f"{label} 必须是包含 path 与 sha256 的对象")
                continue
            source_path = Path(str(source_ref.get("path") or "")).expanduser()
            if not source_path.is_file():
                errors.append(f"{label}.path 不是实际文件: {source_path}")
            elif source_ref.get("sha256") != sha256(source_path):
                errors.append(f"{label}.sha256 与当前文件不一致")

    findings = review.get("draft_findings")
    if not isinstance(findings, list) or not findings:
        errors.append("design_review.draft_findings 至少需要一个初稿 weakest-link 修复")
    else:
        for index, finding in enumerate(findings, 1):
            label = f"design_review.draft_findings[{index}]"
            if not isinstance(finding, dict):
                errors.append(f"{label} 必须是对象")
                continue
            code = str(finding.get("failure_code") or "")
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code):
                errors.append(f"{label}.failure_code 必须由 critic 动态生成 UPPER_SNAKE_CASE")
            refs = finding.get("rule_refs")
            if (
                not isinstance(refs, list)
                or not refs
                or any(str(value) not in valid_rule_refs for value in refs)
            ):
                errors.append(f"{label}.rule_refs 必须引用当前台账真实规则 case")
            for field in (
                "original_quote",
                "diagnosis",
                "rewrite_direction",
                "resolved_in_final_quote",
            ):
                if len(str(finding.get(field) or "").strip()) < 6:
                    errors.append(f"{label}.{field} 必须写具体问题与修复")
            resolved = str(finding.get("resolved_in_final_quote") or "").strip()
            if resolved and resolved not in candidate_text:
                errors.append(f"{label}.resolved_in_final_quote 不在最终候选中")

    axis_checks = review.get("axis_checks")
    required_axes = DESIGN_REVIEW_AXES[artifact]
    if not isinstance(axis_checks, dict) or set(axis_checks) != set(required_axes):
        errors.append(
            "design_review.axis_checks 必须完整覆盖: " + ", ".join(required_axes)
        )
        axis_checks = axis_checks if isinstance(axis_checks, dict) else {}
    judgments: list[str] = []
    for axis in required_axes:
        item = axis_checks.get(axis)
        label = f"design_review.axis_checks.{axis}"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if item.get("verdict") != "pass":
            errors.append(f"{label}.verdict 必须为 pass")
        quotes = item.get("evidence_quotes")
        if not isinstance(quotes, list) or not quotes or any(
            not isinstance(quote, str) or not quote.strip() or quote not in candidate_text
            for quote in quotes
        ):
            errors.append(f"{label}.evidence_quotes 必须逐字引用最终候选")
        if item.get("failure_codes") != []:
            errors.append(f"{label}.failure_codes 必须在最终候选中清零")
        judgment = str(item.get("judgment") or "").strip()
        if len(judgment) < 20:
            errors.append(f"{label}.judgment 必须写当前维度专属反向裁决")
        judgments.append(judgment)
    if len(set(judgments)) != len(judgments):
        errors.append("design_review.axis_checks 不得批量套用相同判断")
    if review.get("final_verdict") != "pass":
        errors.append("design_review.final_verdict 必须为 pass")
    if len(str(review.get("final_judgment") or "").strip()) < 30:
        errors.append("design_review.final_judgment 必须写写前 critic 总体放行理由")
    return errors


def precommit_design_candidate(
    ledger_path: Path,
    artifact: str,
    candidate_text: str,
    review: dict[str, Any],
    *,
    region_id: str = "",
) -> list[str]:
    errors: list[str] = []
    data = load(ledger_path)
    project_dir = ledger_path.parent.parent
    state = ensure_design_review_state(data, project_dir)
    if state.get("mode") != "enforced":
        return ["legacy_existing 项目不得补做写前设计 critic 冒充首写门禁"]
    if (data.get("draft_review_state") or {}).get("approved_regions"):
        return ["正文已有批准区域，不得回填写前设计 critic"]
    candidate_text = candidate_text.strip()
    if len(candidate_text) < 20:
        return ["设计候选内容过短"]
    setting_path = project_dir / "设定.md"
    outline_path = project_dir / "小节大纲.md"
    pending = state.get("pending")

    if artifact == "setting":
        actual_region = "setting"
        if state.get("setting") is not None:
            return ["设定已通过写前 critic 并冻结"]
        if setting_path.is_file() and setting_path.read_text(encoding="utf-8").strip() and not (
            isinstance(pending, dict) and pending.get("artifact") == "setting"
        ):
            return ["设定候选已经提前写入正式文件，必须先通过 precommit-design"]
        base_sha = sha256(setting_path) if setting_path.is_file() else ""
    elif artifact == "outline":
        actual_region = region_id
        setting = state.get("setting")
        if not isinstance(setting, dict) or not setting_path.is_file():
            return ["设定尚未通过 confirm-design，禁止预提交大纲区域"]
        if setting.get("content_sha256") != text_sha256(
            setting_path.read_text(encoding="utf-8").strip()
        ):
            return ["已批准设定文本 SHA 已变化"]
        try:
            candidate_regions, candidate_order, candidate_prefix = split_outline_regions(
                candidate_text, allow_single_region=True
            )
        except ValueError as exc:
            return [str(exc)]
        if candidate_prefix or candidate_order != [region_id]:
            return ["大纲候选必须只包含当前一个完整区域标题与内容"]
        approved = state.get("outline_regions") or []
        approved_ids = [str(item.get("region_id") or "") for item in approved]
        replacing_last = bool(approved_ids and region_id == approved_ids[-1])
        if not next_outline_region(approved_ids, region_id) and not replacing_last:
            return [f"大纲区域不是当前唯一后继: approved={approved_ids}, requested={region_id}"]
        outline_text = outline_path.read_text(encoding="utf-8") if outline_path.is_file() else ""
        try:
            actual_regions, actual_order, _ = split_outline_regions(outline_text)
        except ValueError as exc:
            return [str(exc)]
        allowed_orders = [approved_ids, approved_ids + [region_id]]
        if actual_order not in allowed_orders:
            return [
                "大纲正式文件只能包含已批准区域和当前一个可替换未批准区域: "
                f"approved={approved_ids}, actual={actual_order}"
            ]
        for item in approved:
            approved_id = str(item.get("region_id") or "")
            if approved_id != region_id and item.get("content_sha256") != text_sha256(actual_regions.get(approved_id, "")):
                errors.append(f"已批准大纲区域 {approved_id} 文本 SHA 已变化")
        if errors:
            return errors
        candidate_region_text = candidate_regions[region_id]
        # When replacing the last frozen region, validate the candidate against
        # the frozen prefix only. The existing copy of that region (and any
        # later unapproved tail) must not be duplicated into the in-memory
        # preflight document.
        preflight_base = outline_text
        if replacing_last:
            markers = list(OUTLINE_REGION_RE.finditer(outline_text))
            if len(markers) >= len(approved_ids):
                preflight_base = outline_text[: markers[-1].start()].rstrip()
        errors.extend(
            preflight_outline_candidate(
                project_dir,
                preflight_base,
                candidate_region_text,
                approved_ids[:-1] if replacing_last else approved_ids,
                approved_ids[:-1] if replacing_last else actual_order,
            )
        )
        if errors:
            return errors
        candidate_text = candidate_region_text
        base_sha = sha256(outline_path) if outline_path.is_file() else ""
    else:
        return ["artifact 只能是 setting 或 outline"]

    errors.extend(
        validate_design_critic_review(
            review, candidate_text, data, artifact, actual_region
        )
    )
    if errors:
        return errors
    state["pending"] = {
        "artifact": artifact,
        "region_id": actual_region,
        "candidate_sha256": text_sha256(candidate_text),
        "base_artifact_sha256": base_sha,
        "review": review,
    }
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return []


def confirm_design_candidate(
    ledger_path: Path,
    artifact: str,
    artifact_path: Path,
    *,
    region_id: str = "",
    preflight_passed: bool = False,
) -> list[str]:
    data = load(ledger_path)
    project_dir = ledger_path.parent.parent
    state = ensure_design_review_state(data, project_dir)
    if state.get("mode") != "enforced":
        return ["legacy_existing 项目没有可确认的写前设计候选"]
    pending = state.get("pending")
    expected_region = "setting" if artifact == "setting" else region_id
    if (
        not isinstance(pending, dict)
        or pending.get("artifact") != artifact
        or pending.get("region_id") != expected_region
    ):
        return [f"当前没有匹配的 {artifact} 写前 precommit"]
    if not artifact_path.is_file():
        return [f"正式设计文件不存在: {artifact_path}"]

    if artifact == "setting":
        current_text = artifact_path.read_text(encoding="utf-8").strip()
        if pending.get("candidate_sha256") != text_sha256(current_text):
            return ["设定正式文件与 precommit 最终候选 SHA 不一致"]
        state["setting"] = {
            "path": str(artifact_path.resolve()),
            "content_sha256": text_sha256(current_text),
            "review": pending.get("review"),
        }
    elif artifact == "outline":
        if not preflight_passed:
            return ["大纲区域必须先通过 preflight --allow-partial"]
        try:
            regions, actual_order, _ = split_outline_regions(
                artifact_path.read_text(encoding="utf-8")
            )
        except ValueError as exc:
            return [str(exc)]
        approved = state.get("outline_regions") or []
        approved_ids = [str(item.get("region_id") or "") for item in approved]
        expected_confirm_order = approved_ids if (approved_ids and approved_ids[-1] == region_id) else approved_ids + [region_id]
        if actual_order != expected_confirm_order:
            return [
                "确认大纲时正式文件必须只新增当前区域: "
                f"expected={expected_confirm_order}, actual={actual_order}"
            ]
        for item in approved:
            approved_id = str(item.get("region_id") or "")
            if approved_id != region_id and item.get("content_sha256") != text_sha256(regions.get(approved_id, "")):
                return [f"已批准大纲区域 {approved_id} 文本 SHA 已变化"]
        current_text = regions.get(region_id, "")
        if pending.get("candidate_sha256") != text_sha256(current_text):
            return ["大纲正式区域与 precommit 最终候选 SHA 不一致"]
        replacement = {
            "region_id": region_id,
            "content_sha256": text_sha256(current_text),
            "review": pending.get("review"),
        }
        if approved and approved[-1].get("region_id") == region_id:
            approved[-1] = replacement
        else:
            approved.append(replacement)
        state["outline_regions"] = approved
    else:
        return ["artifact 只能是 setting 或 outline"]
    state["pending"] = None
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return []


def validate_design_gate(
    data: dict[str, Any], project_dir: Path, expected_outline_regions: list[str]
) -> list[str]:
    errors: list[str] = []
    state = data.get("design_review_state")
    if not isinstance(state, dict):
        return ["缺少 design_review_state，必须 refresh-rules 或重新 init"]
    if state.get("pending") is not None:
        errors.append("design_review_state 仍有未 confirm 的写前候选")
    mode = state.get("mode")
    if mode == "legacy_existing":
        for field in ("setting", "outline"):
            binding = state.get(field)
            if not isinstance(binding, dict):
                errors.append(f"legacy design_review_state.{field} 缺少绑定")
                continue
            path = Path(str(binding.get("path") or ""))
            if not path.is_file() or binding.get("sha256") != sha256(path):
                errors.append(f"legacy design_review_state.{field} SHA 已变化")
        return errors
    if mode != "enforced":
        return ["design_review_state.mode 非法"]
    setting_path = project_dir / "设定.md"
    setting = state.get("setting")
    if not isinstance(setting, dict) or not setting_path.is_file():
        errors.append("设定尚未通过写前 critic 与 confirm-design")
    elif setting.get("content_sha256") != text_sha256(
        setting_path.read_text(encoding="utf-8").strip()
    ):
        errors.append("已批准设定文本 SHA 已变化")
    outline_path = project_dir / "小节大纲.md"
    approved = state.get("outline_regions")
    approved_ids = [
        str(item.get("region_id") or "")
        for item in approved or []
        if isinstance(item, dict)
    ]
    if approved_ids != expected_outline_regions:
        errors.append(
            "大纲写前 critic 尚未逐区域完成: "
            f"expected={expected_outline_regions}, approved={approved_ids}"
        )
    if outline_path.is_file():
        try:
            regions, actual_order, _ = split_outline_regions(
                outline_path.read_text(encoding="utf-8")
            )
        except ValueError as exc:
            errors.append(str(exc))
            regions, actual_order = {}, []
        if actual_order != approved_ids:
            errors.append("小节大纲正式区域与 design_review_state 不一致")
        for item in approved or []:
            if not isinstance(item, dict):
                continue
            approved_id = str(item.get("region_id") or "")
            if item.get("content_sha256") != text_sha256(regions.get(approved_id, "")):
                errors.append(f"已批准大纲区域 {approved_id} 文本 SHA 已变化")
    else:
        errors.append("小节大纲正式文件不存在")
    return errors


def resolve_config_path(config_path: Path, raw: str) -> Path:
    candidate = Path(raw).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (config_path.parent / candidate).resolve()


def prepare_section_context(
    ledger_path: Path,
    project_dir: Path,
    draft_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    errors = validate_prewrite_ledger(ledger_path)
    if errors:
        return {}, errors
    data = load(ledger_path)
    state = data["draft_review_state"]
    expected = [str(value) for value in state.get("expected_regions") or []]
    approved = state.get("approved_regions") or []
    if len(approved) >= len(expected):
        return {}, ["全部正文区域已经完成复核"]
    next_region = expected[len(approved)]

    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    if draft_text.strip():
        try:
            regions, actual_order = split_draft_regions(draft_text)
        except ValueError as exc:
            return {}, [str(exc)]
        if actual_order == ["opening"] and not regions["opening"]:
            actual_order = []
    else:
        regions, actual_order = {}, []
    approved_ids = [str(item.get("region_id") or "") for item in approved]
    if actual_order != approved_ids:
        return {}, [
            "领取当前区域写前句法包时，正文只能包含已通过区域: "
            f"approved={approved_ids}, actual={actual_order}"
        ]
    for item in approved:
        region_id = str(item["region_id"])
        if item.get("content_sha256") != text_sha256(regions.get(region_id, "")):
            errors.append(f"已通过区域 {region_id} 文本 SHA 已变化")
    if errors:
        return {}, errors

    target_path = project_dir / "写作资产" / "目标成文脑图.json"
    config_path = project_dir / "写作资产" / "项目写作配置.json"
    try:
        target = load(target_path)
        config = load(config_path)
        source_path = Path(str((target.get("source_map") or {}).get("path") or "")).resolve()
        source = load(source_path)
        original_path = Path(
            str(((source.get("compiled_from") or {}).get("original") or {}).get("path") or "")
        ).resolve()
        original_lines = read_text(original_path).splitlines()
        profile_path = resolve_config_path(config_path, str(config.get("profile_path") or ""))
        profile = load(profile_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [str(exc)]
    if target.get("gate_status") != "passed":
        return {}, ["目标成文脑图尚未 gate_status=passed，禁止领取正文句法包"]

    region_ids = [next_region]
    if next_region == expected[-1]:
        region_ids.append("epilogue")
    nodes = [
        item
        for item in target.get("target_nodes") or []
        if isinstance(item, dict) and str(item.get("region_id") or "") in region_ids
    ]
    if not nodes:
        return {}, [f"目标成文脑图缺少当前区域节点: {region_ids}"]
    node_ids = {str(item["target_id"]) for item in nodes}

    source_layers = {
        str(item["layer_id"]): item
        for item in source.get("layers") or []
        if isinstance(item, dict)
    }
    layer_packets = []
    for mapping in target.get("mappings", {}).get("layers") or []:
        targets = [str(value) for value in mapping.get("target_node_ids") or []]
        if not node_ids.intersection(targets):
            continue
        layer_id = str(mapping.get("source_id") or "")
        layer = source_layers.get(layer_id)
        if not layer:
            errors.append(f"来源层不存在: {layer_id}")
            continue
        source_range = layer.get("source_range") or {}
        start = source_range.get("start_line")
        end = source_range.get("end_line")
        if not isinstance(start, int) or not isinstance(end, int) or not (1 <= start <= end <= len(original_lines)):
            errors.append(f"{layer_id} 来源行域非法")
            continue
        excerpt = "\n".join(original_lines[start - 1 : end])
        dimensions = layer.get("dimension_realization") or {}
        layer_packets.append({
            "layer_id": layer_id,
            "target_node_ids": [value for value in targets if value in node_ids],
            "source_range": {"start_line": start, "end_line": end},
            "source_excerpt": excerpt,
            "source_sentence_chain": extract_sentences(excerpt),
            "layer_modes": layer.get("layer_modes") or [],
            "entry_relation": str(layer.get("entry_relation") or ""),
            "exit_relation": str(layer.get("exit_relation") or ""),
            "narrative_distance": str(layer.get("narrative_distance") or ""),
            "sentence_relation_and_rhythm": dimensions.get("sentence_relation_and_rhythm") or {},
            "paragraph_breath_and_cut_points": dimensions.get("paragraph_breath_and_cut_points") or {},
            "dialogue_misfire_or_avoidance": dimensions.get("dialogue_misfire_or_avoidance") or {},
            "must_preserve_in_target": layer.get("must_preserve_in_target") or [],
        })
    if errors:
        return {}, errors
    if not layer_packets:
        return {}, [f"当前区域 {next_region} 没有来源文字层句法包"]

    plot_sources = {str(item["beat_id"]): item for item in source.get("plot_beats") or []}
    emotion_sources = {str(item["beat_id"]): item for item in source.get("emotion_beats") or []}
    plot_packets = [
        plot_sources[str(item["source_id"])]
        for item in target.get("mappings", {}).get("plot_beats") or []
        if str(item.get("target_id") or "") in node_ids
    ]
    emotion_packets = [
        emotion_sources[str(item["source_id"])]
        for item in target.get("mappings", {}).get("emotion_beats") or []
        if str(item.get("target_id") or "") in node_ids
    ]
    plans = liveliness_group(data).get("section_generation_plans") or []
    section_plans = [
        item
        for item in plans
        if isinstance(item, dict) and str(item.get("target_sections") or "") in region_ids
    ]
    contract = (profile.get("prose_style_contract") or {}) if isinstance(profile, dict) else {}
    if not section_plans:
        return {}, [f"当前区域 {next_region} 缺少 section_generation_plans 写前计划"]
    if not contract.get("sentence_motion"):
        return {}, ["项目 profile 缺少 prose_style_contract.sentence_motion"]
    length_metrics = section_length_metrics(ledger_path, next_region)
    previous_tail = extract_sentences("\n".join(regions.get(value, "") for value in approved_ids))[-6:]
    packet: dict[str, Any] = {
        "schema_version": "story-short-write.section-generation-context.v1",
        "project": project_dir.name,
        "region_id": next_region,
        "included_target_regions": region_ids,
        "target_nodes": nodes,
        "plot_beats": plot_packets,
        "emotion_beats": emotion_packets,
        "source_layers": layer_packets,
        "section_generation_plans": section_plans,
        "primary_sentence_motion": contract.get("sentence_motion") or [],
        "primary_narrator_voice": contract.get("narrator_voice") or [],
        "primary_dialogue_voice": contract.get("dialogue_and_character_voice") or [],
        "length_metrics": length_metrics,
        "particle_contract": {
            "source_layer_ids": [item["layer_id"] for item in layer_packets],
            "source_layer_sentence_counts": {
                item["layer_id"]: len(item["source_sentence_chain"])
                for item in layer_packets
            },
            "target_node_ids": [str(item["target_id"]) for item in nodes],
            "required_fields": [
                "source_layer_id",
                "target_node_ids",
                "source_sentence_count",
                "target_sentence_count",
                "action_chain",
                "object_and_force",
                "pov_attention",
                "dialogue_or_silence",
                "result_and_cut",
                "judgment",
            ],
        },
        "previous_region_tail_sentences": previous_tail,
        "user_feedback_cases": data.get("draft_review_state", {}).get("feedback_cases") or [],
        "generation_contract": [
            "只在当前工作上下文形成当前 region_id 的候选；不得预写或输出后续数字节标题，候选通过 precommit-section 前不得写入正文。",
            "逐层消费 source_excerpt 的连续句链，迁移句间机制，不复制人物、物件或原句。",
            "按 sentence_relation_and_rhythm 与 paragraph_breath_and_cut_points 安排长短句；短判断只落在来源本来有落锤的位置。",
            "单一身体、感官或同一话轮链可保留长句；多动作、多信息或视线换主必须在自然换气点拆开。",
            "全部直接对白落盘前必须朗读并剥离细纲腔；角色不得复述职业标签、关系位置、资源排序、控制权或信息机制，只说当前人会直接说的事实与命令。",
            "盲审 critic 不得读取或复述写作者的创作理由，只引用候选原句、提交失败码和最小修复方向；至少修掉一个初稿 weakest link，再对最终候选逐句复验。",
            "读取流水、病历、名单、门禁和合同时，人物只能先看见金额、备注、收款方、诊断、姓名、时间或状态；流程摘要不得进入最终候选。",
            "禁止用‘目标事件句 + 固定旁白句’批量拼接节点，禁止复用 previous_region_tail_sentences 的句面。",
            "首写前必须完成逐来源句的 target_sentence_plan：每个来源句明确目标承接句、动作/受力、物件、人物注意力、对白或静默、结果与断口；任何概括、流程词或空泛判断都会在 plan-section 阶段阻断。",
            "写作者只能依据已通过的 particle_plan 落笔；不得先写一版概括正文再依赖 precommit 或终审补颗粒。",
            "precommit-section 生成最终候选 SHA 后，只把该候选第一次写入正文；随后完整通读真实句子并运行 confirm-section，通过前不得追加下一区域。",
        ],
    }
    packet["content_sha256"] = text_sha256(
        json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    state["prepared_region"] = {
        "region_id": next_region,
        "context_sha256": packet["content_sha256"],
        "base_draft_sha256": sha256(draft_path) if draft_path.is_file() else "",
        "approved_region_hashes": [str(item.get("content_sha256") or "") for item in approved],
        "source_layer_ids": [item["layer_id"] for item in layer_packets],
        "length_metrics": length_metrics,
        "particle_contract": packet["particle_contract"],
    }
    state["precommit_region"] = None
    state["status"] = "prepared"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return packet, []


def validate_region_review(
    review: dict[str, Any],
    region_text: str,
    previous_text: str,
    prior_reviews: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if review.get("model_read_entire_region") is not True:
        errors.append("model_read_entire_region 必须显式为 true")
    actual_sentences = extract_sentences(region_text)
    sentence_reviews = review.get("sentence_reviews")
    if not isinstance(sentence_reviews, list):
        sentence_reviews = []
        errors.append("sentence_reviews 必须是数组")
    reviewed_sentences = [
        str(item.get("sentence") or "")
        for item in sentence_reviews
        if isinstance(item, dict)
    ]
    if reviewed_sentences != actual_sentences:
        mismatch_index = next(
            (
                index
                for index in range(max(len(actual_sentences), len(reviewed_sentences)))
                if index >= len(actual_sentences)
                or index >= len(reviewed_sentences)
                or actual_sentences[index] != reviewed_sentences[index]
            ),
            0,
        )
        actual = actual_sentences[mismatch_index] if mismatch_index < len(actual_sentences) else "<missing>"
        reviewed = reviewed_sentences[mismatch_index] if mismatch_index < len(reviewed_sentences) else "<missing>"
        errors.append(
            "sentence_reviews 必须逐句、同序、逐字覆盖当前区域全部真实句子: "
            f"index={mismatch_index + 1}, actual={actual!r}, reviewed={reviewed!r}, "
            f"actual_count={len(actual_sentences)}, reviewed_count={len(reviewed_sentences)}, "
            f"actual_sequence={json.dumps(actual_sentences, ensure_ascii=False)}"
        )
    judgments: list[str] = []
    for index, item in enumerate(sentence_reviews, 1):
        label = f"sentence_reviews[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if len(str(item.get("subject_or_viewpoint") or "").strip()) < 2:
            errors.append(f"{label}.subject_or_viewpoint 不能为空")
        unit_count = item.get("independent_unit_count")
        if not isinstance(unit_count, int) or unit_count < 1:
            errors.append(f"{label}.independent_unit_count 必须是正整数")
        for field in ("viewpoint_shift", "single_continuous_chain"):
            if not isinstance(item.get(field), bool):
                errors.append(f"{label}.{field} 必须是布尔值")
        decision = str(item.get("decision") or "")
        if decision not in {"keep", "split", "revise"}:
            errors.append(f"{label}.decision 只能是 keep、split 或 revise")
        elif decision != "keep":
            errors.append(f"{label} 仍判定为 {decision}，必须先修改正文再重新复核")
        if (
            isinstance(unit_count, int)
            and unit_count > 1
            and item.get("single_continuous_chain") is False
            and decision == "keep"
        ):
            errors.append(f"{label} 含多个独立单元且不是单一连续链，不能 keep")
        if item.get("viewpoint_shift") is True and decision == "keep":
            errors.append(f"{label} 存在视线/主语换主，不能 keep")
        for field in ("breath_point_judgment", "source_voice_basis", "judgment"):
            value = str(item.get(field) or "").strip()
            if len(value) < 12:
                errors.append(f"{label}.{field} 必须写当前句专属判断")
        judgments.append(str(item.get("judgment") or "").strip())
    if len(judgments) >= 4:
        counts: dict[str, int] = {}
        for value in judgments:
            counts[value] = counts.get(value, 0) + 1
        if counts and max(counts.values()) > 2:
            errors.append("sentence_reviews.judgment 疑似批量套用，同一判断不得重复超过两次")

    actual_dialogues = extract_dialogues(region_text)
    dialogue_reviews = review.get("direct_dialogue_reviews")
    if not isinstance(dialogue_reviews, list):
        dialogue_reviews = []
        errors.append("direct_dialogue_reviews 必须是数组")
    reviewed_dialogues = [
        str(item.get("quote") or "")
        for item in dialogue_reviews
        if isinstance(item, dict)
    ]
    if reviewed_dialogues != actual_dialogues:
        mismatch_index = next(
            (
                index
                for index in range(max(len(actual_dialogues), len(reviewed_dialogues)))
                if index >= len(actual_dialogues)
                or index >= len(reviewed_dialogues)
                or actual_dialogues[index] != reviewed_dialogues[index]
            ),
            0,
        )
        actual = actual_dialogues[mismatch_index] if mismatch_index < len(actual_dialogues) else "<missing>"
        reviewed = reviewed_dialogues[mismatch_index] if mismatch_index < len(reviewed_dialogues) else "<missing>"
        errors.append(
            "direct_dialogue_reviews 必须逐字、同序覆盖当前区域全部直接对白: "
            f"index={mismatch_index + 1}, actual={actual!r}, reviewed={reviewed!r}, "
            f"actual_count={len(actual_dialogues)}, reviewed_count={len(reviewed_dialogues)}, "
            f"actual_sequence={json.dumps(actual_dialogues, ensure_ascii=False)}"
        )
    for index, item in enumerate(dialogue_reviews, 1):
        label = f"direct_dialogue_reviews[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        for field in ("speaker", "scene_pressure", "turn_connection", "response_effect", "judgment"):
            if len(str(item.get(field) or "").strip()) < 4:
                errors.append(f"{label}.{field} 不能为空")
        if item.get("interchangeable") is not False:
            errors.append(f"{label}.interchangeable 必须显式为 false")
        if item.get("decision") != "keep":
            errors.append(f"{label}.decision 必须为 keep")

    prior_sentences = extract_sentences(previous_text)
    seen_prior = set(prior_sentences)
    local_counts: dict[str, int] = {}
    for sentence in actual_sentences:
        local_counts[sentence] = local_counts.get(sentence, 0) + 1
    repeated = []
    for sentence in actual_sentences:
        if (sentence in seen_prior or local_counts[sentence] > 1) and sentence not in repeated:
            repeated.append(sentence)
    repeated_reviews = review.get("repeated_sentence_reviews")
    if not isinstance(repeated_reviews, list):
        repeated_reviews = []
        errors.append("repeated_sentence_reviews 必须是数组")
    if [str(item.get("sentence") or "") for item in repeated_reviews if isinstance(item, dict)] != repeated:
        errors.append("repeated_sentence_reviews 必须完整覆盖当前区域与前文或本区重复的句子")
    for index, item in enumerate(repeated_reviews, 1):
        label = f"repeated_sentence_reviews[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if item.get("decision") not in {"keep", "revise"}:
            errors.append(f"{label}.decision 只能是 keep 或 revise")
        elif item.get("decision") != "keep":
            errors.append(f"{label} 仍需 revise，必须先修改正文")
        for field in ("intentional_function", "judgment"):
            if len(str(item.get(field) or "").strip()) < 12:
                errors.append(f"{label}.{field} 必须写重复保留的专属理由")

    summary_fields = (
        "cadence_judgment",
        "scene_sentence_relation_judgment",
        "template_repetition_judgment",
        "explanatory_inference_review",
        "manual_judgment",
        "region_judgment",
    )
    current_summary = []
    for field in summary_fields:
        value = str(review.get(field) or "").strip()
        current_summary.append(value)
        if len(value) < 20:
            errors.append(f"{field} 必须写当前区域专属裁决")
    for prior in prior_reviews:
        prior_review = prior.get("review") if isinstance(prior, dict) else None
        if isinstance(prior_review, dict) and current_summary == [
            str(prior_review.get(field) or "").strip() for field in summary_fields
        ]:
            errors.append("区域总结裁决与旧区域完全相同，疑似模板化复核")
            break
    return errors


def validate_precommit_review(
    review: dict[str, Any], candidate_text: str, ledger_data: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    valid_rule_refs = {
        f"{group.get('rule_id')}:{case.get('line')}"
        for group in ledger_data.get("groups") or []
        if isinstance(group, dict)
        for case in group.get("cases") or []
        if isinstance(case, dict)
    }
    considered_rule_refs = review.get("rule_refs_considered")
    if (
        not isinstance(considered_rule_refs, list)
        or not considered_rule_refs
        or any(str(value) not in valid_rule_refs for value in considered_rule_refs)
    ):
        errors.append("precommit.rule_refs_considered 必须引用当前台账真实规则 case")
    expected_feedback_ids = [
        str(item.get("feedback_id") or "")
        for item in (ledger_data.get("draft_review_state") or {}).get("feedback_cases") or []
        if isinstance(item, dict)
    ]
    if review.get("feedback_case_ids_considered") != expected_feedback_ids:
        errors.append(
            "precommit.feedback_case_ids_considered 必须全量同序消费当前用户反馈案例"
        )
    for field in (
        "critic_context_isolated",
        "diagnostic_only_first_pass",
        "author_intent_ignored",
        "model_read_final_candidate",
    ):
        if review.get(field) is not True:
            errors.append(f"precommit.{field} 必须显式为 true")

    findings = review.get("draft_findings")
    if not isinstance(findings, list) or not findings:
        errors.append("precommit.draft_findings 至少需要一个初稿 weakest-link 修复")
    else:
        for index, finding in enumerate(findings, 1):
            label = f"precommit.draft_findings[{index}]"
            if not isinstance(finding, dict):
                errors.append(f"{label} 必须是对象")
                continue
            code = str(finding.get("failure_code") or "")
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code):
                errors.append(f"{label}.failure_code 必须是模型按当前问题生成的 UPPER_SNAKE_CASE")
            refs = finding.get("rule_refs")
            if (
                not isinstance(refs, list)
                or not refs
                or any(str(value) not in valid_rule_refs for value in refs)
            ):
                errors.append(f"{label}.rule_refs 必须引用当前台账真实规则 case")
            for field in ("original_quote", "diagnosis", "rewrite_direction", "resolved_in_final_quote"):
                if len(str(finding.get(field) or "").strip()) < 6:
                    errors.append(f"{label}.{field} 必须写具体初稿问题与修复")
            resolved = str(finding.get("resolved_in_final_quote") or "").strip()
            if resolved and resolved not in candidate_text:
                errors.append(f"{label}.resolved_in_final_quote 不在最终候选中")

    actual_sentences = extract_sentences(candidate_text)
    checks = review.get("sentence_checks")
    reviewed_sentences = [
        str(item.get("sentence") or "")
        for item in checks or []
        if isinstance(item, dict)
    ]
    if not isinstance(checks, list) or reviewed_sentences != actual_sentences:
        errors.append(
            "precommit.sentence_checks 必须逐句、同序、逐字覆盖最终候选: "
            f"actual={json.dumps(actual_sentences, ensure_ascii=False)}"
        )
        checks = checks if isinstance(checks, list) else []
    judgments: list[str] = []
    for index, item in enumerate(checks, 1):
        label = f"precommit.sentence_checks[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        sentence = str(item.get("sentence") or "")
        suspect = str(item.get("most_suspicious_span") or "").strip()
        if len(suspect) < 1 or suspect not in sentence:
            errors.append(f"{label}.most_suspicious_span 必须引用本句最可疑原文")
        if item.get("read_aloud_verdict") != "pass":
            errors.append(f"{label}.read_aloud_verdict 必须为 pass")
        if item.get("physical_action_verdict") not in {"pass", "not_applicable"}:
            errors.append(f"{label}.physical_action_verdict 非法")
        if item.get("pov_attention_verdict") != "pass":
            errors.append(f"{label}.pov_attention_verdict 必须为 pass")
        if item.get("structured_record_verdict") not in {"pass", "not_applicable"}:
            errors.append(f"{label}.structured_record_verdict 非法")
        if item.get("failure_codes") != []:
            errors.append(f"{label}.failure_codes 必须在最终候选中清零")
        judgment = str(item.get("judgment") or "").strip()
        if len(judgment) < 20:
            errors.append(f"{label}.judgment 必须写当前句专属检查依据")
        judgments.append(judgment)
    if len(judgments) >= 4 and max((judgments.count(value) for value in set(judgments)), default=0) > 2:
        errors.append("precommit.sentence_checks 疑似批量套用相同判断")

    groups = review.get("group_checks")
    if not isinstance(groups, list) or not groups:
        errors.append("precommit.group_checks 至少需要一组连续动作或话轮检查")
    else:
        for index, item in enumerate(groups, 1):
            label = f"precommit.group_checks[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} 必须是对象")
                continue
            if item.get("group_type") not in {"action_chain", "dialogue_turns", "paragraph_transition"}:
                errors.append(f"{label}.group_type 非法")
            quotes = item.get("quotes")
            if not isinstance(quotes, list) or not quotes or any(
                not isinstance(quote, str) or not quote.strip() or quote not in candidate_text
                for quote in quotes
            ):
                errors.append(f"{label}.quotes 必须逐字引用最终候选")
            if len(str(item.get("weakest_point") or "").strip()) < 6:
                errors.append(f"{label}.weakest_point 必须指出本组最可疑处")
            if item.get("verdict") != "pass":
                errors.append(f"{label}.verdict 必须为 pass")
            if len(str(item.get("judgment") or "").strip()) < 20:
                errors.append(f"{label}.judgment 必须写当前组连接依据")

    if review.get("final_verdict") != "pass":
        errors.append("precommit.final_verdict 必须为 pass")
    if len(str(review.get("final_judgment") or "").strip()) < 30:
        errors.append("precommit.final_judgment 必须写盲审后的总体放行理由")
    return errors


def validate_particle_coverage(
    review: dict[str, Any], prepared: dict[str, Any], candidate_text: str
) -> list[str]:
    """Require explicit per-layer/per-node particle coverage before first write."""
    contract = prepared.get("particle_contract")
    if not isinstance(contract, dict):
        # Keep legacy fixtures/projects compatible; new prepare-section packets
        # always include the contract and therefore take the strict path below.
        return []
    raw = review.get("particle_coverage")
    if not isinstance(raw, list):
        return ["precommit.particle_coverage 必须逐来源层提交颗粒覆盖"]
    expected_layers = [str(value) for value in contract.get("source_layer_ids") or []]
    actual_layers = [str(item.get("source_layer_id") or "") for item in raw if isinstance(item, dict)]
    if actual_layers != expected_layers:
        return [
            "precommit.particle_coverage 必须与当前句法包来源层同序全量对应: "
            f"expected={expected_layers}, actual={actual_layers}"
        ]
    errors: list[str] = []
    synopsis_hits = [
        match.group(0)
        for pattern in SYNOPSIS_PROSE_PATTERNS
        for match in pattern.finditer(candidate_text)
    ]
    if synopsis_hits:
        errors.append(
            "正文候选含概括/流程播报句，必须逐颗粒展开后再提交: "
            + "、".join(sorted(set(synopsis_hits))[:8])
        )
    expected_nodes = [str(value) for value in contract.get("target_node_ids") or []]
    required_fields = [str(value) for value in contract.get("required_fields") or []]
    expected_counts = contract.get("source_layer_sentence_counts") or {}
    for index, item in enumerate(raw, 1):
        label = f"precommit.particle_coverage[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        targets = item.get("target_node_ids")
        if not isinstance(targets, list) or not targets or any(str(value) not in expected_nodes for value in targets):
            errors.append(f"{label}.target_node_ids 必须引用当前区域目标节点")
        if targets and [expected_nodes.index(str(value)) for value in targets] != sorted(set(expected_nodes.index(str(value)) for value in targets)):
            errors.append(f"{label}.target_node_ids 必须保持目标节点原序且不重复")
        expected_count = int(expected_counts.get(str(item.get("source_layer_id") or ""), 0))
        for field in required_fields:
            value = str(item.get(field) or "").strip()
            if field in {"source_layer_id", "target_node_ids", "source_sentence_count", "target_sentence_count"}:
                continue
            if len(value) < 8:
                errors.append(f"{label}.{field} 必须写当前来源层的具体颗粒判断")
        source_count = item.get("source_sentence_count")
        target_count = item.get("target_sentence_count")
        # A live source layer cannot collapse into fewer target sentences than
        # its source chain. Summary/public-discourse layers are allowed to
        # retain their coarse distance, but they still need an explicit
        # one-to-one particle accounting entry rather than a total-only claim.
        layer_mode = str(item.get("layer_mode") or "")
        minimum_target = 1 if layer_mode in {
            "opening_compression", "time_jump", "summary_transition",
            "public_discourse", "institutional_result", "rumor_afterword",
        } else expected_count
        if (
            source_count != expected_count
            or not isinstance(target_count, int)
            or target_count < minimum_target
        ):
            errors.append(
                f"{label} 句链数量不完整: source_sentence_count={source_count}, "
                f"expected={expected_count}, minimum_target={minimum_target}, "
                f"target_sentence_count={target_count}"
            )
        if layer_mode not in {
            "", "opening_compression", "time_jump", "summary_transition",
            "public_discourse", "institutional_result", "rumor_afterword",
            "live_scene", "compressed_scene", "memory_exposition",
        }:
            errors.append(f"{label}.layer_mode 非法")
        quotes = item.get("evidence_quotes")
        if not isinstance(quotes, list) or not quotes or any(not isinstance(q, str) or not q.strip() or q not in candidate_text for q in quotes):
            errors.append(f"{label}.evidence_quotes 必须提供正文逐字引句")
    return errors


def validate_particle_plan(
    plan: dict[str, Any], prepared: dict[str, Any]
) -> list[str]:
    contract = prepared.get("particle_contract")
    if not isinstance(contract, dict):
        return ["当前句法包缺少 particle_contract，必须重新 prepare-section"]
    if str(plan.get("region_id") or "") != str(prepared.get("region_id") or ""):
        return ["particle_plan.region_id 必须与当前 prepared_region 一致"]
    expected_layers = [str(value) for value in contract.get("source_layer_ids") or []]
    expected_counts = contract.get("source_layer_sentence_counts") or {}
    layer_plans = plan.get("source_layer_plans")
    if not isinstance(layer_plans, list) or [str(item.get("source_layer_id") or "") for item in layer_plans if isinstance(item, dict)] != expected_layers:
        return ["particle_plan.source_layer_plans 必须与当前来源层同序全量对应"]
    expected_nodes = [str(value) for value in contract.get("target_node_ids") or []]
    node_plans = plan.get("target_node_plans")
    if not isinstance(node_plans, list) or [str(item.get("target_node_id") or "") for item in node_plans if isinstance(item, dict)] != expected_nodes:
        return ["particle_plan.target_node_plans 必须与当前目标节点同序全量对应"]
    errors: list[str] = []
    required_fields = ("action_chain", "object_and_force", "pov_attention", "dialogue_or_silence", "result_and_cut", "judgment")
    for index, item in enumerate(layer_plans, 1):
        label = f"particle_plan.source_layer_plans[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        targets = item.get("target_node_ids")
        if not isinstance(targets, list) or not targets or any(str(value) not in expected_nodes for value in targets):
            errors.append(f"{label}.target_node_ids 必须引用当前目标节点")
        expected_count = int(expected_counts.get(str(item.get("source_layer_id") or ""), 0))
        units = item.get("unit_plan")
        if not isinstance(units, list) or len(units) != expected_count:
            errors.append(f"{label}.unit_plan 必须逐来源句链提交 {expected_count} 项")
            units = units if isinstance(units, list) else []
        for unit_index, unit in enumerate(units, 1):
            unit_label = f"{label}.unit_plan[{unit_index}]"
            if not isinstance(unit, dict) or unit.get("source_sentence_index") != unit_index:
                errors.append(f"{unit_label} 必须按来源句序编号")
                continue
            if str(unit.get("target_node_id") or "") not in expected_nodes:
                errors.append(f"{unit_label}.target_node_id 必须引用当前目标节点")
            for field in required_fields:
                if len(str(unit.get(field) or "").strip()) < 8:
                    errors.append(f"{unit_label}.{field} 必须写具体落笔计划")
                elif any(pattern.search(str(unit.get(field))) for pattern in PLAN_SYNOPSIS_PATTERNS):
                    errors.append(
                        f"{unit_label}.{field} 含概括/流程词，必须在首写前改为可执行的动作、物件、注意力或结果"
                    )
    for index, item in enumerate(node_plans, 1):
        label = f"particle_plan.target_node_plans[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        for field in required_fields:
            if len(str(item.get(field) or "").strip()) < 8:
                errors.append(f"{label}.{field} 必须写本节点专属施工判断")
            elif any(pattern.search(str(item.get(field))) for pattern in PLAN_SYNOPSIS_PATTERNS):
                errors.append(
                    f"{label}.{field} 含概括/流程词，必须在首写前改为本节点具体施工判断"
                )
    return errors


def record_particle_plan(ledger_path: Path, region_id: str, plan: dict[str, Any]) -> list[str]:
    data = load(ledger_path)
    prepared = (data.get("draft_review_state") or {}).get("prepared_region")
    if not isinstance(prepared, dict) or prepared.get("region_id") != region_id:
        return [f"当前区域 {region_id} 尚未通过 prepare-section"]
    errors = validate_particle_plan(plan, prepared)
    if errors:
        return errors
    state = data["draft_review_state"]
    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    state["prepared_region"]["particle_plan_sha256"] = text_sha256(canonical)
    state["prepared_region"]["particle_plan_target_node_ids"] = list(
        (prepared.get("particle_contract") or {}).get("target_node_ids") or []
    )
    state["prepared_region"]["particle_plan_source_layer_ids"] = list(
        (prepared.get("particle_contract") or {}).get("source_layer_ids") or []
    )
    state["status"] = "particle_planned"
    data["gate_status"] = "pending"
    ledger_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return []


def precommit_section_candidate(
    ledger_path: Path,
    draft_path: Path,
    region_id: str,
    candidate_text: str,
    review: dict[str, Any],
) -> list[str]:
    errors = validate_prewrite_ledger(ledger_path)
    if errors:
        return errors
    data = load(ledger_path)
    state = data["draft_review_state"]
    expected = [str(value) for value in state.get("expected_regions") or []]
    approved = state.get("approved_regions") or []
    if len(approved) >= len(expected):
        return ["全部正文区域已经完成复核"]
    next_region = expected[len(approved)]
    if region_id != next_region:
        return [f"当前只允许 precommit {next_region}，不得跳到 {region_id}"]
    prepared = state.get("prepared_region")
    if not isinstance(prepared, dict) or prepared.get("region_id") != region_id:
        return [f"当前区域 {region_id} 尚未通过 prepare-section"]
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.is_file() else ""
    try:
        regions, actual_order = split_draft_regions(draft_text)
    except ValueError as exc:
        return [str(exc)]
    if actual_order == ["opening"] and not regions.get("opening"):
        actual_order = []
    approved_ids = [str(item.get("region_id") or "") for item in approved]
    if actual_order != approved_ids:
        return [
            "precommit 前正文只能包含已通过区域，当前候选不得提前落盘: "
            f"approved={approved_ids}, actual={actual_order}"
        ]
    if prepared.get("particle_contract") and not str(prepared.get("particle_plan_sha256") or ""):
        return ["当前区域尚未完成 plan-section 写前颗粒施工计划"]
    candidate_text = candidate_text.strip()
    if not candidate_text:
        return ["precommit 候选正文为空"]
    errors.extend(validate_candidate_section_length(ledger_path, region_id, candidate_text))
    if errors:
        return errors
    length_metrics = section_length_metrics(ledger_path, region_id)
    if region_id.startswith("section:") and not length_metrics:
        return [f"无法记录正文 {region_id} 的主体锚定量"]
    errors.extend(validate_particle_coverage(review, prepared, candidate_text))
    if errors:
        return errors
    errors.extend(validate_precommit_review(review, candidate_text, data))
    if errors:
        return errors
    state["precommit_region"] = {
        "region_id": region_id,
        "candidate_sha256": text_sha256(candidate_text),
        "generation_context_sha256": str(prepared.get("context_sha256") or ""),
        "length_check": {
            **(length_metrics or {}),
            "candidate_chars": nonspace_count(candidate_text),
        },
        "review": review,
    }
    state["status"] = "precommitted"
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return []


def apply_section_review(
    ledger_path: Path,
    draft_path: Path,
    region_id: str,
    review: dict[str, Any],
) -> list[str]:
    errors = validate_prewrite_ledger(ledger_path)
    if errors:
        return errors
    data = load(ledger_path)
    state = data["draft_review_state"]
    expected = [str(value) for value in state["expected_regions"]]
    approved = state.get("approved_regions") or []
    if len(approved) >= len(expected):
        return ["全部正文区域已经完成复核"]
    next_region = expected[len(approved)]
    if region_id != next_region:
        return [f"当前只允许复核 {next_region}，不得跳到 {region_id}"]
    prepared = state.get("prepared_region")
    if not isinstance(prepared, dict) or prepared.get("region_id") != region_id:
        return [f"当前区域 {region_id} 尚未通过 prepare-section 领取写前句法包"]
    if not draft_path.is_file():
        return [f"正文不存在: {draft_path}"]
    try:
        regions, actual_order = split_draft_regions(draft_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [str(exc)]
    expected_order = expected[: len(approved) + 1]
    if actual_order != expected_order:
        return [
            "正文只能包含已通过区域和当前一个待审区域: "
            f"expected={expected_order}, actual={actual_order}"
        ]
    for item in approved:
        approved_id = str(item["region_id"])
        if item.get("content_sha256") != text_sha256(regions.get(approved_id, "")):
            errors.append(f"已通过区域 {approved_id} 文本 SHA 已变化")
    current_text = regions.get(region_id, "")
    if not current_text.strip():
        errors.append(f"当前区域 {region_id} 正文为空")
    precommit = state.get("precommit_region")
    if not isinstance(precommit, dict) or precommit.get("region_id") != region_id:
        errors.append(f"当前区域 {region_id} 尚未通过 precommit-section 盲审")
    elif precommit.get("candidate_sha256") != text_sha256(current_text):
        errors.append(
            "正文与 precommit 最终候选 SHA 不一致，说明盲审后又改写或首次落盘内容错误"
        )
    previous_text = "\n".join(regions[value] for value in expected[: len(approved)])
    errors.extend(validate_region_review(review, current_text, previous_text, approved))
    if errors:
        return errors
    approved.append({
        "region_id": region_id,
        "content_sha256": text_sha256(current_text),
        "sentence_count": len(extract_sentences(current_text)),
        "dialogue_count": len(extract_dialogues(current_text)),
        "review": review,
        "generation_context_sha256": str(prepared.get("context_sha256") or ""),
    })
    state["approved_regions"] = approved
    state["prepared_region"] = None
    state["precommit_region"] = None
    state["status"] = "passed" if len(approved) == len(expected) else "in_progress"
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return []


def reconfirm_approved_section(
    ledger_path: Path,
    draft_path: Path,
    region_id: str,
    review: dict[str, Any],
) -> list[str]:
    errors = validate_prewrite_ledger(ledger_path)
    if errors:
        return errors
    data = load(ledger_path)
    state = data["draft_review_state"]
    approved = state.get("approved_regions") or []
    approved_ids = [str(item.get("region_id") or "") for item in approved]
    if not approved_ids or approved_ids[-1] != region_id:
        return [
            "reconfirm-approved-section 只允许最新已通过区域: "
            f"latest={approved_ids[-1] if approved_ids else '<none>'}, requested={region_id}"
        ]
    if not draft_path.is_file():
        return [f"正文不存在: {draft_path}"]
    try:
        regions, actual_order = split_draft_regions(draft_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [str(exc)]
    if actual_order != approved_ids:
        return [
            "定点回修时正文只能包含已通过区域: "
            f"approved={approved_ids}, actual={actual_order}"
        ]
    current_text = regions.get(region_id, "")
    previous_text = "\n".join(regions[value] for value in approved_ids[:-1])
    errors.extend(validate_region_review(review, current_text, previous_text, approved[:-1]))
    if errors:
        return errors
    approved[-1].update({
        "content_sha256": text_sha256(current_text),
        "sentence_count": len(extract_sentences(current_text)),
        "dialogue_count": len(extract_dialogues(current_text)),
        "review": review,
    })
    state["prepared_region"] = None
    state["precommit_region"] = None
    expected = [str(value) for value in state.get("expected_regions") or []]
    state["status"] = "passed" if approved_ids == expected else "in_progress"
    data["gate_status"] = "pending"
    ledger_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return []


def validate_draft_review_state(
    ledger_path: Path,
    draft_path: Path,
    *,
    require_complete: bool,
    validate_prewrite_first: bool = True,
) -> list[str]:
    errors = validate_prewrite_ledger(ledger_path) if validate_prewrite_first else []
    if errors:
        return errors
    if not draft_path.is_file():
        return [f"正文不存在: {draft_path}"]
    data = load(ledger_path)
    state = data.get("draft_review_state")
    if not isinstance(state, dict):
        return ["规则执行台账缺少 v2 draft_review_state，必须重新 init"]
    expected = [str(value) for value in state.get("expected_regions") or []]
    approved = state.get("approved_regions") or []
    try:
        regions, actual_order = split_draft_regions(draft_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [str(exc)]
    approved_ids = [str(item.get("region_id") or "") for item in approved if isinstance(item, dict)]
    if approved_ids != expected[: len(approved_ids)]:
        errors.append("approved_regions 不是 expected_regions 的连续前缀")
    if actual_order != approved_ids:
        errors.append(
            "正文含有尚未完成真实句子复核的区域: "
            f"approved={approved_ids}, actual={actual_order}"
        )
    for item in approved:
        region_id = str(item.get("region_id") or "")
        if item.get("content_sha256") != text_sha256(regions.get(region_id, "")):
            errors.append(f"已通过区域 {region_id} 文本 SHA 已变化")
        if not str(item.get("generation_context_sha256") or ""):
            errors.append(f"已通过区域 {region_id} 缺少写前句法包 SHA")
    if require_complete:
        if approved_ids != expected:
            errors.append(
                "正文逐区域真实句子复核尚未完成: "
                f"expected={expected}, approved={approved_ids}"
            )
        if state.get("status") != "passed":
            errors.append("draft_review_state.status 必须为 passed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--skill-root")
    init.add_argument("--output")
    validate = sub.add_parser("validate-prewrite")
    validate.add_argument("--ledger", required=True)
    confirm = sub.add_parser("confirm-prewrite")
    confirm.add_argument("--ledger", required=True)
    confirm.add_argument("--reviews-json", required=True)
    refresh = sub.add_parser("refresh-rules")
    refresh.add_argument("--ledger", required=True)
    precommit_design = sub.add_parser("precommit-design")
    precommit_design.add_argument("--ledger", required=True)
    precommit_design.add_argument("--artifact", required=True, choices=("setting", "outline"))
    precommit_design.add_argument("--region", default="")
    precommit_design.add_argument("--candidate-json", required=True)
    precommit_design.add_argument("--review-json", default="{}")
    precommit_design.add_argument("--review-json-file")
    confirm_design = sub.add_parser("confirm-design")
    confirm_design.add_argument("--ledger", required=True)
    confirm_design.add_argument("--artifact", required=True, choices=("setting", "outline"))
    confirm_design.add_argument("--region", default="")
    confirm_design.add_argument("--path", required=True)
    confirm_design.add_argument("--preflight-passed", action="store_true")
    record_feedback = sub.add_parser("record-feedback")
    record_feedback.add_argument("--ledger", required=True)
    record_feedback.add_argument("--feedback-json", required=True)
    prepare_section = sub.add_parser("prepare-section")
    prepare_section.add_argument("--ledger", required=True)
    prepare_section.add_argument("--project-dir", required=True)
    prepare_section.add_argument("--draft")
    plan_section = sub.add_parser("plan-section")
    plan_section.add_argument("--ledger", required=True)
    plan_section.add_argument("--region", required=True)
    plan_section.add_argument("--plan-json", required=True)
    confirm_section = sub.add_parser("confirm-section")
    confirm_section.add_argument("--ledger", required=True)
    confirm_section.add_argument("--draft", required=True)
    confirm_section.add_argument("--region", required=True)
    confirm_section.add_argument("--review-json", default="{}")
    confirm_section.add_argument("--review-json-file")
    precommit_section = sub.add_parser("precommit-section")
    precommit_section.add_argument("--ledger", required=True)
    precommit_section.add_argument("--draft", required=True)
    precommit_section.add_argument("--region", required=True)
    precommit_section.add_argument("--candidate-json", required=True)
    precommit_section.add_argument("--review-json", default="{}")
    precommit_section.add_argument("--review-json-file")
    reconfirm_section = sub.add_parser("reconfirm-approved-section")
    reconfirm_section.add_argument("--ledger", required=True)
    reconfirm_section.add_argument("--draft", required=True)
    reconfirm_section.add_argument("--region", required=True)
    reconfirm_section.add_argument("--review-json", default="{}")
    reconfirm_section.add_argument("--review-json-file")
    validate_draft = sub.add_parser("validate-draft")
    validate_draft.add_argument("--ledger", required=True)
    validate_draft.add_argument("--draft", required=True)
    validate_draft.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    if args.command == "init":
        project = Path(args.project_dir).resolve()
        skill_root = Path(args.skill_root).resolve() if args.skill_root else Path(__file__).resolve().parents[1]
        output = Path(args.output).resolve() if args.output else project / "写作资产" / "规则执行台账.json"
        try:
            write_new(output, build_ledger(project, skill_root))
        except (OSError, ValueError, FileNotFoundError) as exc:
            print("rule_execution_ledger: blocked")
            print(f"- {exc}")
            return 2
        print("rule_execution_ledger: initialized")
        print(f"ledger: {output}")
        return 0
    ledger_path = Path(args.ledger).resolve()
    if args.command == "refresh-rules":
        try:
            refresh_rule_sources(ledger_path)
        except (OSError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            print("rule_execution_ledger: blocked")
            print(f"- {exc}")
            return 2
        print("rule_execution_ledger: refreshed")
        return 0
    if args.command == "precommit-design":
        try:
            candidate = json.loads(args.candidate_json)
            if not isinstance(candidate, str):
                raise ValueError("candidate-json 必须是 JSON 字符串")
            review = parse_review_input(args.review_json, args.review_json_file)
            errors = precommit_design_candidate(
                ledger_path,
                args.artifact,
                candidate,
                review,
                region_id=args.region,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors = [str(exc)]
        if errors:
            print("design_precommit: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("design_precommit: passed")
        print(f"artifact: {args.artifact}")
        if args.region:
            print(f"region: {args.region}")
        return 0
    if args.command == "confirm-design":
        try:
            errors = confirm_design_candidate(
                ledger_path,
                args.artifact,
                Path(args.path).resolve(),
                region_id=args.region,
                preflight_passed=args.preflight_passed,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors = [str(exc)]
        if errors:
            print("design_confirm: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("design_confirm: passed")
        print(f"artifact: {args.artifact}")
        if args.region:
            print(f"region: {args.region}")
        return 0
    if args.command == "record-feedback":
        try:
            payload = json.loads(args.feedback_json)
            if not isinstance(payload, dict):
                raise ValueError("feedback-json 顶层必须是对象")
            feedback_id = record_feedback_case(ledger_path, payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("rule_execution_ledger: blocked")
            print(f"- {exc}")
            return 2
        print("rule_execution_ledger: feedback-recorded")
        print(f"feedback_id: {feedback_id}")
        return 0
    if args.command == "confirm-prewrite":
        try:
            reviews = json.loads(args.reviews_json)
            if not isinstance(reviews, dict):
                raise ValueError("reviews-json 顶层必须是对象")
            apply_prewrite_reviews(ledger_path, reviews)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("rule_execution_ledger: blocked")
            print(f"- {exc}")
            return 2
        print("rule_execution_ledger: confirmed")
        return 0
    if args.command == "prepare-section":
        project_dir = Path(args.project_dir).resolve()
        draft_path = Path(args.draft).resolve() if args.draft else project_dir / "正文.md"
        try:
            packet, errors = prepare_section_context(
                ledger_path, project_dir, draft_path
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            packet, errors = {}, [str(exc)]
        if errors:
            print("section_generation_context: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print(json.dumps(packet, ensure_ascii=False, indent=2))
        print("section_generation_context: passed")
        return 0
    if args.command == "plan-section":
        try:
            plan = json.loads(args.plan_json)
            if not isinstance(plan, dict):
                raise ValueError("plan-json 顶层必须是对象")
            errors = record_particle_plan(ledger_path, args.region, plan)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors = [str(exc)]
        if errors:
            print("section_particle_plan: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("section_particle_plan: passed")
        print(f"region: {args.region}")
        return 0
    if args.command == "precommit-section":
        try:
            candidate = json.loads(args.candidate_json)
            if not isinstance(candidate, str):
                raise ValueError("candidate-json 必须是 JSON 字符串")
            review = parse_review_input(args.review_json, args.review_json_file)
            errors = precommit_section_candidate(
                ledger_path,
                Path(args.draft).resolve(),
                args.region,
                candidate,
                review,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors = [str(exc)]
        if errors:
            print("section_precommit: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("section_precommit: passed")
        print(f"region: {args.region}")
        return 0
    if args.command == "confirm-section":
        try:
            review = parse_review_input(args.review_json, args.review_json_file)
            errors = apply_section_review(
                ledger_path,
                Path(args.draft).resolve(),
                args.region,
                review,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors = [str(exc)]
        if errors:
            print("section_sentence_review: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("section_sentence_review: passed")
        print(f"region: {args.region}")
        return 0
    if args.command == "reconfirm-approved-section":
        try:
            review = parse_review_input(args.review_json, args.review_json_file)
            errors = reconfirm_approved_section(
                ledger_path,
                Path(args.draft).resolve(),
                args.region,
                review,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors = [str(exc)]
        if errors:
            print("section_sentence_review: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("section_sentence_review: passed")
        print(f"region: {args.region}")
        return 0
    if args.command == "validate-draft":
        errors = validate_draft_review_state(
            ledger_path,
            Path(args.draft).resolve(),
            require_complete=args.require_complete,
        )
        if errors:
            print("section_draft_review: blocked")
            for error in errors:
                print(f"- {error}")
            return 2
        print("section_draft_review: passed")
        return 0
    errors = validate_prewrite_ledger(ledger_path)
    if errors:
        print("rule_execution_ledger_prewrite: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("rule_execution_ledger_prewrite: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
