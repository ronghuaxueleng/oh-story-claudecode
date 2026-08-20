#!/usr/bin/env python3
"""Validate the compact source-to-outline migration contract.

The contract records only decisions that cannot be recovered mechanically from
the detailed outline: which target fine beat carries each selected source P/E
beat. Section budgets and scene summaries are parsed directly from the outline.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = "story-short-write.outline-migration-contract.v7"
PREVIOUS_SCHEMA_VERSION = "story-short-write.outline-migration-contract.v6"
LEGACY_SCHEMA_VERSIONS = {
    "story-short-write.outline-migration-contract.v5",
    "story-short-write.outline-migration-contract.v4",
}
TEMPLATE_SCHEMA = "story-short-write.outline-migration-template.v5"
FULL_BRIDGE_PLOT_LEDGER_SCHEMA = "story-short-analyze.full-text-plot-ledger.v2"
FULL_EMOTION_LEDGER_SCHEMA = "story-short-analyze.full-text-emotion-ledger.v2"
SOURCE_STYLE_GRANULARITY_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
SOURCE_WHOLE_PERFORMANCE_FIELDS = (
    "entry_state",
    "required_sequence",
    "scene_granularity",
    "emotion_sequence",
    "end_state",
)
P_REPLACEMENT_DIMENSIONS = {
    "character_role",
    "relationship_shell",
    "occupation_domain",
    "setting",
    "trigger",
    "object",
    "evidence",
    "control_mechanism",
    "consequence",
}
P_REPLACEMENT_CORE_DIMENSIONS = {
    "occupation_domain",
    "setting",
    "trigger",
    "evidence",
    "control_mechanism",
    "consequence",
}
HOT_NEWS_MAX_AGE_DAYS = 90
HOT_MATERIAL_TYPES = {"social_news", "internet_meme"}
GOVERNMENT_PUBLISHER_MARKERS = (
    "政府",
    "国务院",
    "网信办",
    "政务",
    "公安部",
    "公安厅",
    "公安局",
    "人民法院",
    "人民检察院",
    "应急管理部",
    "应急管理厅",
    "应急管理局",
    "市场监管",
    "市场监督管理",
    "行政审批",
    "税务局",
    "执法局",
    "管理委员会",
    "监督管理局",
)
SEARCH_ENGINE_HOST_SUFFIXES = (
    "google.com",
    "google.cn",
    "bing.com",
    "sogou.com",
    "duckduckgo.com",
    "yandex.com",
)
SEARCH_ENGINE_EXACT_HOSTS = {
    "baidu.com",
    "www.baidu.com",
    "m.baidu.com",
    "wap.baidu.com",
    "news.baidu.com",
    "so.com",
    "www.so.com",
    "m.so.com",
    "sm.cn",
    "m.sm.cn",
    "search.yahoo.com",
    "search.brave.com",
}
HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
FIELD_RE = re.compile(r"(?m)^- ([^：\n]+)：(.*)$")
SECTION_HEADING_RE = re.compile(r"^(\d+)[.、．](?:\s+.*)?$")
CHAR_RANGE_RE = re.compile(r"(\d+)\s*[-~至]\s*(\d+)\s*字")
SOURCE_LINE_RANGE_RE = re.compile(r"L?(\d+)\s*[-~至]\s*L?(\d+)", re.IGNORECASE)
SOURCE_SECTION_MARKER_RE = re.compile(r"\s*\d+(?:[.、．])?\s*")
REQUIRED_OUTLINE_FIELDS = (
    "主事件",
    "子事件",
    "细拍拆分",
    "情绪",
    "读者新获知什么",
    "钩子",
    "伏笔/物件",
    "动静",
    "对话密度",
    "目标字数",
    "场面单元",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, str]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"文件不存在: {resolved}")
    return {"path": str(resolved), "sha256": sha256(resolved)}


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须是 JSON 对象: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_path(value: Any, project_dir: Path) -> Path:
    path = Path(str(value or "")).expanduser()
    return path.resolve() if path.is_absolute() else (project_dir / path).resolve()


def _derived_original(entry: dict[str, Any], project_dir: Path) -> Path:
    if str(entry.get("original_path") or "").strip():
        return _resolve_path(entry["original_path"], project_dir)
    profile = _resolve_path(entry.get("profile_path"), project_dir)
    name = str(entry.get("name") or "").strip()
    if not name:
        raise ValueError("来源缺少 name，无法推导原文路径")
    return profile.parent / "原文" / f"{name}.txt"


def _ledger_path(
    entry: dict[str, Any], key: str, original: Path, filename: str, project_dir: Path
) -> Path:
    if str(entry.get(key) or "").strip():
        return _resolve_path(entry[key], project_dir)
    return original.parent.parent / "写作资产" / filename


def _subflow_catalog_path(
    entry: dict[str, Any], original: Path, project_dir: Path
) -> Path:
    if str(entry.get("subflow_catalog_path") or "").strip():
        return _resolve_path(entry["subflow_catalog_path"], project_dir)
    return original.parent.parent / "写作资产" / "子流程索引.jsonl"


def _primary_hierarchy_assets(
    entry: dict[str, Any], original: Path, project_dir: Path
) -> dict[str, Any]:
    profile_raw = str(entry.get("profile_path") or "").strip()
    if not profile_raw:
        raise ValueError("主体来源缺少 profile_path，无法绑定完整上层层级")
    profile = _resolve_path(profile_raw, project_dir)
    report = (
        _resolve_path(entry["story_core_path"], project_dir)
        if str(entry.get("story_core_path") or "").strip()
        else original.parent.parent / "拆文报告.md"
    )
    emotion_motherline = (
        _resolve_path(entry["emotion_motherline_path"], project_dir)
        if str(entry.get("emotion_motherline_path") or "").strip()
        else original.parent.parent / "写作资产" / "情绪母线.md"
    )
    profile_data = read_json(profile, "主体 profile")
    bridge_rules = profile_data.get("bridge_rules")
    if not isinstance(bridge_rules, list) or not bridge_rules:
        raise ValueError("主体 profile.bridge_rules 必须是非空列表")
    report_text = report.read_text(encoding="utf-8")
    if "故事核" not in report_text:
        raise ValueError(f"主体拆文报告缺少故事核: {report}")
    if len(re.sub(r"\s+", "", emotion_motherline.read_text(encoding="utf-8"))) < 20:
        raise ValueError(f"主体情绪母线过短，无法作为上层真源: {emotion_motherline}")
    return {
        "profile": binding(profile),
        "story_core": binding(report),
        "emotion_motherline": binding(emotion_motherline),
        "bridge_rules": deepcopy(bridge_rules),
    }


def _load_beats(path: Path, label: str, expected_schema: str) -> list[dict[str, Any]]:
    payload = read_json(path, label)
    if payload.get("schema_version") != expected_schema:
        raise ValueError(
            f"{label} schema_version 必须为 {expected_schema}: {path}"
        )
    beats = payload.get("beats")
    if not isinstance(beats, list) or not beats or any(not isinstance(item, dict) for item in beats):
        raise ValueError(f"{label}.beats 必须是非空对象列表: {path}")
    ids = [str(item.get("beat_id") or "").strip() for item in beats]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{label} beat_id 缺失或重复: {path}")
    return beats


def _has_text(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_text(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_text(item) for item in value)
    return False


def _line_range(value: Any, label: str) -> tuple[int, int]:
    if isinstance(value, dict):
        start = value.get("start_line")
        end = value.get("end_line")
        if isinstance(start, int) and isinstance(end, int) and 0 < start <= end:
            return start, end
    match = SOURCE_LINE_RANGE_RE.fullmatch(str(value or "").strip())
    if match:
        start, end = map(int, match.groups())
        if 0 < start <= end:
            return start, end
    raise ValueError(f"{label} 无法解析原文行区间: {value!r}")


def _load_subflow_validator():
    path = (
        Path(__file__).resolve().parents[2]
        / "story-short-analyze"
        / "scripts"
        / "validate_subflow_catalog.py"
    )
    spec = importlib.util.spec_from_file_location(
        "story_short_analyze_subflow_validator", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载主体子流程 validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SUBFLOW_VALIDATOR = _load_subflow_validator()


def _load_subflows(path: Path, original_path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"主体子流程索引不存在: {path}")
    rows, topology_errors = SUBFLOW_VALIDATOR.validate_catalog(path, original_path)
    if topology_errors:
        raise ValueError("；".join(topology_errors))
    validated_rows: list[dict[str, Any]] = []
    for line_number, item in enumerate(rows, start=1):
        subflow_id = str(item.get("subflow_id") or "").strip()
        if not subflow_id:
            raise ValueError(f"主体子流程索引第 {line_number} 行缺少 subflow_id")
        if not str(item.get("parent_bridge_id") or "").strip():
            raise ValueError(f"主体子流程 {subflow_id} 缺少 parent_bridge_id")
        _line_range(item.get("source_range"), f"主体子流程 {subflow_id}.source_range")
        granularity = item.get("source_style_granularity")
        if not isinstance(granularity, dict):
            raise ValueError(f"主体子流程 {subflow_id} 缺少 source_style_granularity")
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            if field not in granularity or not _has_text(granularity[field]):
                raise ValueError(f"主体子流程 {subflow_id}.{field} 不能为空")
        for field in SOURCE_WHOLE_PERFORMANCE_FIELDS:
            value = item.get(field)
            if field in {"required_sequence", "emotion_sequence"}:
                if not isinstance(value, list) or not value or any(
                    not isinstance(step, str) or not step.strip() for step in value
                ):
                    raise ValueError(
                        f"主体子流程 {subflow_id}.{field} 必须是非空文本列表"
                    )
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f"主体子流程 {subflow_id}.{field} 不能为空")
        validated_rows.append(item)
    ids = [str(item["subflow_id"]).strip() for item in validated_rows]
    if not validated_rows or len(ids) != len(set(ids)):
        raise ValueError("主体子流程索引必须非空且 subflow_id 不得重复")
    return validated_rows


def _format_line_ranges(line_numbers: list[int]) -> str:
    ranges: list[str] = []
    start = previous = line_numbers[0]
    for line_number in line_numbers[1:]:
        if line_number == previous + 1:
            previous = line_number
            continue
        ranges.append(f"L{start}" if start == previous else f"L{start}-L{previous}")
        start = previous = line_number
    ranges.append(f"L{start}" if start == previous else f"L{start}-L{previous}")
    return ", ".join(ranges)


def _validate_subflow_source_coverage(
    original_path: Path,
    subflows: list[dict[str, Any]],
) -> None:
    """Require SF ranges to cover every prose line in the primary original."""
    lines = original_path.read_text(encoding="utf-8").splitlines()
    covered: set[int] = set()
    previous_start = 0
    for subflow in subflows:
        subflow_id = str(subflow.get("subflow_id") or "").strip()
        start, end = _line_range(
            subflow.get("source_range"), f"主体子流程 {subflow_id}.source_range"
        )
        if end > len(lines):
            raise ValueError(
                f"主体子流程 {subflow_id}.source_range 超出原文总行数: "
                f"L{start}-L{end}, total={len(lines)}"
            )
        if start < previous_start:
            raise ValueError(
                f"主体子流程索引必须按原文行区间非递减排列: {subflow_id}=L{start}-L{end}"
            )
        previous_start = start
        covered.update(range(start, end + 1))

    prose_lines = [
        line_number
        for line_number, line in enumerate(lines, start=1)
        if line.strip() and not SOURCE_SECTION_MARKER_RE.fullmatch(line)
    ]
    uncovered = [line_number for line_number in prose_lines if line_number not in covered]
    if uncovered:
        raise ValueError(
            "主体子流程索引未覆盖原文全部正文行: "
            + _format_line_ranges(uncovered)
        )


def source_specs(config_path: Path) -> list[dict[str, Any]]:
    config = read_json(config_path, "项目写作配置")
    # Relative paths in the config are relative to the config file itself.
    project_dir = config_path.resolve().parent
    primary = config.get("primary")
    if not isinstance(primary, dict):
        raise ValueError("项目写作配置缺少 primary")
    entries: list[tuple[str, dict[str, Any]]] = [("primary", primary)]
    auxiliaries = config.get("auxiliaries") or []
    if not isinstance(auxiliaries, list):
        raise ValueError("项目写作配置 auxiliaries 必须是列表")
    entries.extend(("auxiliary", item) for item in auxiliaries if isinstance(item, dict))

    specs: list[dict[str, Any]] = []
    for index, (role, entry) in enumerate(entries):
        selected = [str(value).strip() for value in entry.get("selected_bids") or [] if str(value).strip()]
        if role == "auxiliary" and not selected:
            continue
        original = _derived_original(entry, project_dir)
        plot_ledger = _ledger_path(
            entry,
            "plot_ledger_path",
            original,
            "全文情节微拍总账.json",
            project_dir,
        )
        emotion_ledger = None
        subflow_catalog = None
        prose_subflows: list[dict[str, Any]] = []
        if role == "primary":
            emotion_ledger = _ledger_path(
                entry,
                "emotion_ledger_path",
                original,
                "全文情绪颗粒总账.json",
                project_dir,
            )
            subflow_catalog = _subflow_catalog_path(entry, original, project_dir)
            prose_subflows = _load_subflows(subflow_catalog, original)
            _validate_subflow_source_coverage(original, prose_subflows)
            subflow_layer_catalog = subflow_catalog.with_name(
                "子流程层次索引.jsonl"
            )
            hierarchy_assets = _primary_hierarchy_assets(entry, original, project_dir)
        else:
            hierarchy_assets = None
        plot_beats = _load_beats(plot_ledger, "全文情节微拍总账", FULL_BRIDGE_PLOT_LEDGER_SCHEMA)
        if role == "auxiliary":
            available_bids = {
                str(bid)
                for beat in plot_beats
                for bid in beat.get("bid_ids") or []
                if str(bid).strip()
            }
            missing = [bid for bid in selected if bid not in available_bids]
            if missing:
                raise ValueError(f"辅助来源 selected_bids 不存在: {missing}")
            plot_beats = [
                beat for beat in plot_beats
                if any(bid in selected for bid in beat.get("bid_ids") or [])
            ]
        emotion_beats: list[dict[str, Any]] = []
        if emotion_ledger is not None:
            emotion_beats = _load_beats(
                emotion_ledger,
                "全文情绪颗粒总账",
                FULL_EMOTION_LEDGER_SCHEMA,
            )
        source_id = "SRC-PRIMARY" if role == "primary" else f"SRC-AUX-{index:02d}"
        specs.append(
            {
                "source_id": source_id,
                "name": str(entry.get("name") or original.stem),
                "role": role,
                "prose_voice": "exclusive" if role == "primary" else "forbidden",
                "emotion_transfer": "full" if role == "primary" else "forbidden",
                "selected_bridge_ids": selected,
                "original": binding(original),
                "plot_ledger": binding(plot_ledger),
                "emotion_ledger": binding(emotion_ledger) if emotion_ledger else None,
                "subflow_catalog": binding(subflow_catalog) if subflow_catalog else None,
                "subflow_layer_catalog": (
                    binding(subflow_layer_catalog)
                    if role == "primary" and subflow_layer_catalog.is_file()
                    else None
                ),
                "plot_beats": plot_beats,
                "emotion_beats": emotion_beats,
                "prose_subflows": prose_subflows,
                "hierarchy_assets": hierarchy_assets,
            }
        )
    return specs


def _region_id(title: str) -> str | None:
    if title == "导语":
        return "opening"
    if title == "尾声":
        return "epilogue"
    match = SECTION_HEADING_RE.fullmatch(title)
    return f"section:{int(match.group(1))}" if match else None


def parse_outline(outline_path: Path) -> dict[str, Any]:
    text = outline_path.read_text(encoding="utf-8")
    matches = list(HEADING_RE.finditer(text))
    regions: list[dict[str, Any]] = []
    errors: list[str] = []
    target_ids: set[str] = set()
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        region_id = _region_id(title)
        if region_id is None:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        fields: dict[str, list[str]] = {}
        for field_match in FIELD_RE.finditer(body):
            fields.setdefault(field_match.group(1).strip(), []).append(field_match.group(2).strip())
        missing = [field for field in REQUIRED_OUTLINE_FIELDS if not fields.get(field)]
        if missing:
            errors.append(f"{region_id} 缺少细纲字段: {missing}")
        fine_beats = fields.get("细拍拆分") or []
        target_beats: list[dict[str, str]] = []
        prefix = "opening" if region_id == "opening" else "epilogue" if region_id == "epilogue" else region_id.split(":", 1)[1]
        for beat_index, evidence in enumerate(fine_beats, start=1):
            target_id = f"T-{prefix}-{beat_index:03d}"
            if target_id in target_ids:
                errors.append(f"细纲目标拍 ID 重复: {target_id}")
            target_ids.add(target_id)
            target_beats.append({"target_id": target_id, "evidence": evidence})
        if not target_beats:
            errors.append(f"{region_id} 至少需要一条细拍拆分")
        char_min = char_max = 0
        raw_range = (fields.get("目标字数") or [""])[0]
        range_match = CHAR_RANGE_RE.search(raw_range)
        if range_match:
            char_min, char_max = map(int, range_match.groups())
            if char_min <= 0 or char_max < char_min:
                errors.append(f"{region_id} 目标字数范围无效: {raw_range}")
        else:
            errors.append(f"{region_id} 目标字数无法解析: {raw_range!r}")
        regions.append(
            {
                "region_id": region_id,
                "heading": title,
                "main_event": (fields.get("主事件") or [""])[0],
                "emotion": (fields.get("情绪") or [""])[0],
                "hook": (fields.get("钩子") or [""])[0],
                "objects": (fields.get("伏笔/物件") or [""])[0],
                "scene_summary": (fields.get("场面单元") or [""])[0],
                "target_chars": {"min": char_min, "max": char_max},
                "target_beats": target_beats,
            }
        )
    expected = ["opening"] + [f"section:{index}" for index in range(1, 1 + sum(1 for r in regions if r["region_id"].startswith("section:")))] + ["epilogue"]
    actual = [item["region_id"] for item in regions]
    if actual != expected:
        errors.append(f"细纲区域必须为导语、连续数字节、尾声: {actual}")
    return {"regions": regions, "errors": errors}


def _public_source(spec: dict[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(spec[key]) for key in (
        "source_id",
        "name",
        "role",
        "prose_voice",
        "emotion_transfer",
        "selected_bridge_ids",
        "original",
        "plot_ledger",
        "emotion_ledger",
        "subflow_catalog",
    )}
    result["subflow_layer_catalog"] = deepcopy(spec.get("subflow_layer_catalog"))
    hierarchy_assets = spec.get("hierarchy_assets")
    if spec.get("role") == "primary" and isinstance(hierarchy_assets, dict):
        result["profile"] = deepcopy(hierarchy_assets["profile"])
        result["story_core"] = deepcopy(hierarchy_assets["story_core"])
        result["emotion_motherline"] = deepcopy(
            hierarchy_assets["emotion_motherline"]
        )
    return result


def _source_ref(source_id: str, beat: dict[str, Any]) -> str:
    return f"{source_id}:{str(beat.get('beat_id') or '').strip()}"


def build_source_hierarchy(specs: list[dict[str, Any]]) -> dict[str, Any]:
    primary = specs[0]
    hierarchy_assets = primary.get("hierarchy_assets")
    if not isinstance(hierarchy_assets, dict):
        raise ValueError("主体来源缺少完整上层层级资产")
    bridge_order: list[str] = []

    def add_bridge(value: Any) -> None:
        bridge_id = str(value or "").strip()
        if bridge_id and bridge_id not in bridge_order:
            bridge_order.append(bridge_id)

    for beat in primary["plot_beats"]:
        for bridge_id in beat.get("bid_ids") or []:
            add_bridge(bridge_id)
    for beat in primary["emotion_beats"]:
        for bridge_id in beat.get("bid_ids") or []:
            add_bridge(bridge_id)
    for subflow in primary["prose_subflows"]:
        add_bridge(subflow.get("parent_bridge_id"))

    profile_rules = hierarchy_assets.get("bridge_rules")
    if not isinstance(profile_rules, list):
        raise ValueError("主体 profile.bridge_rules 必须是列表")
    rule_by_id: dict[str, dict[str, Any]] = {}
    profile_bridge_order: list[str] = []
    for index, rule in enumerate(profile_rules, start=1):
        if not isinstance(rule, dict):
            raise ValueError(f"主体 profile.bridge_rules[{index}] 必须是对象")
        bridge_id = str(rule.get("id") or "").strip()
        if not bridge_id:
            raise ValueError(f"主体 profile.bridge_rules[{index}] 缺少 id")
        if bridge_id in rule_by_id:
            raise ValueError(f"主体 profile.bridge_rules id 重复: {bridge_id}")
        must_keep = rule.get("must_keep")
        if not isinstance(must_keep, list) or not any(
            str(item or "").strip() for item in must_keep
        ):
            raise ValueError(
                f"主体 profile.bridge_rules.{bridge_id}.must_keep 必须是非空列表"
            )
        rule_by_id[bridge_id] = rule
        profile_bridge_order.append(bridge_id)
    # Older source profiles can predate a later ledger split. Preserve strict
    # validation for the existing prefix, then derive only newly appended BID
    # shells from the P/E ledgers instead of mutating the source profile.
    if profile_bridge_order != bridge_order[: len(profile_bridge_order)]:
        raise ValueError(
            "主体 profile.bridge_rules 必须与 P/E/SF 总账中的 BID 完全同序，或为其有序前缀: "
            f"profile={profile_bridge_order}, ledgers={bridge_order}"
        )

    emotion_by_bridge: dict[str, list[dict[str, Any]]] = {
        bridge_id: [
            beat
            for beat in primary["emotion_beats"]
            if bridge_id in [str(item) for item in beat.get("bid_ids") or []]
        ]
        for bridge_id in bridge_order
    }
    plot_by_bridge: dict[str, list[dict[str, Any]]] = {
        bridge_id: [
            beat
            for beat in primary["plot_beats"]
            if bridge_id in [str(item) for item in beat.get("bid_ids") or []]
        ]
        for bridge_id in bridge_order
    }

    def ledger_emotion_sequence(bridge_id: str) -> list[dict[str, Any]]:
        sequence: list[dict[str, Any]] = []
        for beat in emotion_by_bridge.get(bridge_id) or []:
            evidence = beat.get("source_evidence")
            if isinstance(evidence, list):
                evidence_value = next(
                    (
                        str(item or "").strip()
                        for item in evidence
                        if str(item or "").strip()
                    ),
                    "",
                )
            else:
                evidence_value = str(evidence or "").strip()
            sequence.append(
                {
                    "beat_id": str(beat.get("beat_id") or "").strip(),
                    "role": beat.get("role"),
                    "content": beat.get("content"),
                    "intensity": beat.get("intensity"),
                    "source_evidence": evidence_value,
                }
            )
        return sequence

    # Legacy profiles used six named emotion slots per bridge rather than the
    # later E-* ledger IDs. Keep that summary for traceability, but make the
    # ledger the canonical sequence used by the contract.
    for bridge_id in profile_bridge_order:
        rule = rule_by_id[bridge_id]
        sequence = rule.get("emotion_sequence")
        expected_ids = [
            str(beat.get("beat_id") or "").strip()
            for beat in emotion_by_bridge.get(bridge_id) or []
        ]
        actual_ids = [
            str(item.get("beat_id") or "").strip()
            for item in sequence
            if isinstance(item, dict)
        ] if isinstance(sequence, list) else []
        if expected_ids and actual_ids != expected_ids and all(
            not value.startswith("E-") for value in actual_ids
        ):
            normalized = deepcopy(rule)
            normalized["profile_summary"] = deepcopy(rule.get("emotion_sequence"))
            normalized["emotion_sequence"] = ledger_emotion_sequence(bridge_id)
            normalized["derived_from_ledgers"] = True
            rule_by_id[bridge_id] = normalized

    for bridge_id in bridge_order[len(profile_bridge_order) :]:
        ledger_emotions = emotion_by_bridge.get(bridge_id) or []
        derived_sequence = ledger_emotion_sequence(bridge_id)
        must_keep = [
            str(beat.get("content") or "").strip()
            for beat in ledger_emotions
            if str(beat.get("content") or "").strip()
        ]
        if not must_keep:
            must_keep = [
                str(beat.get("action") or "").strip()
                for beat in plot_by_bridge.get(bridge_id) or []
                if str(beat.get("action") or "").strip()
            ]
        if not must_keep:
            must_keep = [f"{bridge_id} 总账承重"]
        rule_by_id[bridge_id] = {
            "id": bridge_id,
            "must_keep": must_keep,
            "emotion_sequence": derived_sequence,
            "derived_from_ledgers": True,
        }

    bridges: list[dict[str, Any]] = []
    for bridge_id in bridge_order:
        emotion_beats = emotion_by_bridge.get(bridge_id) or []
        expected_emotion_ids = [
            str(beat.get("beat_id") or "").strip() for beat in emotion_beats
        ]
        profile_rule = rule_by_id[bridge_id]
        profile_emotion_sequence = profile_rule.get("emotion_sequence")
        if not isinstance(profile_emotion_sequence, list):
            raise ValueError(
                f"主体 profile.bridge_rules.{bridge_id}.emotion_sequence 必须是列表"
            )
        if any(not isinstance(item, dict) for item in profile_emotion_sequence):
            raise ValueError(
                f"主体 profile.bridge_rules.{bridge_id}.emotion_sequence 每项必须是对象"
            )
        actual_emotion_ids = [
            str(item.get("beat_id") or "").strip()
            for item in profile_emotion_sequence
        ]
        if actual_emotion_ids != expected_emotion_ids:
            raise ValueError(
                f"主体 profile {bridge_id} 的情绪序列必须与 E 总账完全同序: "
                f"profile={actual_emotion_ids}, ledger={expected_emotion_ids}"
            )
        for profile_beat, ledger_beat in zip(
            profile_emotion_sequence, emotion_beats
        ):
            beat_id = str(ledger_beat.get("beat_id") or "").strip()
            for field in ("role", "content", "intensity"):
                if profile_beat.get(field) != ledger_beat.get(field):
                    raise ValueError(
                        f"主体 profile {bridge_id}/{beat_id}.{field} 必须与 E 总账一致"
                    )
            profile_evidence = str(
                profile_beat.get("source_evidence") or ""
            ).strip()
            ledger_evidence_raw = ledger_beat.get("source_evidence")
            ledger_evidence = (
                [str(item or "").strip() for item in ledger_evidence_raw]
                if isinstance(ledger_evidence_raw, list)
                else [str(ledger_evidence_raw or "").strip()]
            )
            if not profile_evidence or profile_evidence not in ledger_evidence:
                raise ValueError(
                    f"主体 profile {bridge_id}/{beat_id}.source_evidence 必须取自 E 总账"
                )
        bridges.append(
            {
                "bridge_id": bridge_id,
                "source_plot_refs": [
                    _source_ref(primary["source_id"], beat)
                    for beat in primary["plot_beats"]
                    if bridge_id in [str(item) for item in beat.get("bid_ids") or []]
                ],
                "source_emotion_refs": [
                    _source_ref(primary["source_id"], beat)
                    for beat in emotion_beats
                ],
                "source_prose_subflow_refs": [
                    f"{primary['source_id']}:{str(item.get('subflow_id') or '').strip()}"
                    for item in primary["prose_subflows"]
                    if str(item.get("parent_bridge_id") or "").strip() == bridge_id
                ],
                "profile_rule": deepcopy(profile_rule),
            }
        )
    return {
        "story_core_source": deepcopy(hierarchy_assets["story_core"]),
        "emotion_motherline_source": deepcopy(
            hierarchy_assets["emotion_motherline"]
        ),
        "profile_source": deepcopy(hierarchy_assets["profile"]),
        "bridge_order": bridge_order,
        "bridges": bridges,
    }


def expected_sequences(specs: list[dict[str, Any]]) -> dict[str, Any]:
    primary = specs[0]
    return {
        "primary_plot_refs": [_source_ref(primary["source_id"], beat) for beat in primary["plot_beats"]],
        "primary_emotion_refs": [_source_ref(primary["source_id"], beat) for beat in primary["emotion_beats"]],
        "primary_prose_subflow_refs": [
            f"{primary['source_id']}:{str(item.get('subflow_id') or '').strip()}"
            for item in primary["prose_subflows"]
        ],
        "auxiliary_plot_refs": {
            spec["source_id"]: [_source_ref(spec["source_id"], beat) for beat in spec["plot_beats"]]
            for spec in specs[1:]
        },
    }


def _target_evidence(catalog: dict[str, Any]) -> dict[str, str]:
    return {
        str(beat.get("target_id") or "").strip(): str(beat.get("evidence") or "").strip()
        for region in catalog.get("regions") or []
        for beat in region.get("target_beats") or []
    }


def _editable_p_replacements(
    receipt: dict[str, Any], specs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing = {
        str(item.get("source_ref") or "").strip(): item
        for item in receipt.get("p_beat_replacements") or []
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for beat in specs[0]["plot_beats"]:
        source_ref = _source_ref(specs[0]["source_id"], beat)
        current = existing.get(source_ref) or {}
        result.append(
            {
                "source_ref": source_ref,
                "preserved_function": str(current.get("preserved_function") or ""),
                "changed_dimensions": list(current.get("changed_dimensions") or []),
                "news_ids": list(current.get("news_ids") or []),
                "adaptation_judgment": str(current.get("adaptation_judgment") or ""),
            }
        )
    return result


def build_p_replacements(
    raw_replacements: Any,
    specs: list[dict[str, Any]],
    mapping: dict[str, Any],
    outline_catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(raw_replacements, list):
        raise ValueError("p_beat_replacements 必须是列表")
    primary_refs = [
        _source_ref(specs[0]["source_id"], beat) for beat in specs[0]["plot_beats"]
    ]
    if len(raw_replacements) != len(primary_refs):
        raise ValueError(
            "p_beat_replacements 必须与主体 P 拍等长: "
            f"expected={len(primary_refs)}, actual={len(raw_replacements)}"
        )
    targets = mapping.get("primary_plot_targets") or []
    if len(targets) != len(primary_refs):
        raise ValueError("主体 P 拍映射未完成，不能生成 P 拍替换合同")
    evidence_by_target = _target_evidence(outline_catalog)
    result: list[dict[str, Any]] = []
    for index, (expected_ref, target_id, item) in enumerate(
        zip(primary_refs, targets, raw_replacements), start=1
    ):
        if not isinstance(item, dict):
            raise ValueError(f"p_beat_replacements[{index}] 必须是对象")
        source_ref = str(item.get("source_ref") or "").strip()
        if source_ref != expected_ref:
            raise ValueError(
                f"p_beat_replacements[{index}].source_ref 必须与主体 P 拍同序: {expected_ref}"
            )
        normalized_target = str(target_id or "").strip()
        result.append(
            {
                "source_ref": source_ref,
                "target_id": normalized_target,
                "target_evidence": evidence_by_target.get(normalized_target, ""),
                "preserved_function": str(item.get("preserved_function") or "").strip(),
                "changed_dimensions": [
                    str(value or "").strip()
                    for value in item.get("changed_dimensions") or []
                    if str(value or "").strip()
                ],
                "news_ids": [
                    str(value or "").strip()
                    for value in item.get("news_ids") or []
                    if str(value or "").strip()
                ],
                "adaptation_judgment": str(item.get("adaptation_judgment") or "").strip(),
            }
        )
    return result


def validate_p_replacements(
    replacements: Any,
    specs: list[dict[str, Any]],
    mapping: dict[str, Any],
    outline_catalog: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        expected = build_p_replacements(replacements, specs, mapping, outline_catalog)
    except ValueError as exc:
        return [str(exc)]
    if replacements != expected:
        errors.append(
            "p_beat_replacements 的 target_id 与 target_evidence 必须由主体 P 映射和当前细纲确定性生成"
        )
    for index, item in enumerate(expected, start=1):
        label = f"p_beat_replacements[{index}]"
        if len(item["preserved_function"]) < 12:
            errors.append(f"{label}.preserved_function 至少 12 字，必须说明保留的承重功能")
        dimensions = item["changed_dimensions"]
        unknown = sorted(set(dimensions) - P_REPLACEMENT_DIMENSIONS)
        if unknown:
            errors.append(f"{label}.changed_dimensions 含未知维度: {unknown}")
        if len(dimensions) != len(set(dimensions)):
            errors.append(f"{label}.changed_dimensions 不得重复")
        if len(dimensions) < 3:
            errors.append(f"{label}.changed_dimensions 至少替换三个事件壳维度")
        if len(set(dimensions) & P_REPLACEMENT_CORE_DIMENSIONS) < 2:
            errors.append(f"{label}.changed_dimensions 至少包含两个核心现实机制维度")
        if len(item["news_ids"]) != len(set(item["news_ids"])):
            errors.append(f"{label}.news_ids 不得重复")
        if len(item["adaptation_judgment"]) < 30:
            errors.append(f"{label}.adaptation_judgment 至少 30 字")
    return errors


def validate_hot_news_materials(
    materials: Any,
    replacements: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(materials, list):
        return ["hot_news_materials 必须是列表"]
    cited_ids = {
        str(news_id or "").strip()
        for replacement in replacements
        if isinstance(replacement, dict)
        for news_id in replacement.get("news_ids") or []
        if str(news_id or "").strip()
    }
    if not materials and not cited_ids:
        return []
    required_count = min(2, len(replacements))
    if len(materials) < required_count:
        errors.append(f"hot_news_materials 至少需要 {required_count} 条不同社会热点材料")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(materials, start=1):
        label = f"hot_news_materials[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        values = {
            key: str(item.get(key) or "").strip()
            for key in (
                "news_id",
                "material_type",
                "title",
                "publisher",
                "published_at",
                "retrieved_at",
                "url",
                "social_heat_signal",
                "transferable_mechanism",
                "fact_boundary",
            )
        }
        normalized.append(values)
        for key, value in values.items():
            if not value:
                errors.append(f"{label}.{key} 不能为空")
        if not re.fullmatch(r"HN-\d{3,}", values["news_id"]):
            errors.append(f"{label}.news_id 必须使用 HN-001 形态")
        if values["material_type"] not in HOT_MATERIAL_TYPES:
            errors.append(
                f"{label}.material_type 必须为 social_news 或 internet_meme"
            )
        parsed_url = urlparse(values["url"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            errors.append(f"{label}.url 必须是可追溯的 http/https 材料链接")
        host = (parsed_url.hostname or "").rstrip(".").lower()
        host_labels = set(host.split("."))
        if "gov" in host_labels or host.endswith(".gov.cn") or host == "gov.cn":
            errors.append(f"{label}.url 禁止使用政府/政务网站")
        if (
            host in SEARCH_ENGINE_EXACT_HOSTS
            or host.startswith("search.")
            or any(
                host == suffix or host.endswith(f".{suffix}")
                for suffix in SEARCH_ENGINE_HOST_SUFFIXES
            )
        ):
            errors.append(f"{label}.url 禁止使用搜索引擎或聚合搜索结果")
        if any(marker in values["publisher"] for marker in GOVERNMENT_PUBLISHER_MARKERS):
            errors.append(f"{label}.publisher 禁止使用政府部门或监管机构")
        try:
            published = date.fromisoformat(values["published_at"])
            retrieved = date.fromisoformat(values["retrieved_at"])
            age = (retrieved - published).days
            if age < 0:
                errors.append(f"{label} 检索日期不得早于发布日期")
            elif age > HOT_NEWS_MAX_AGE_DAYS:
                errors.append(
                    f"{label} 发布/走热至检索已 {age} 天，超过社会热点材料 {HOT_NEWS_MAX_AGE_DAYS} 天上限"
                )
        except ValueError:
            errors.append(f"{label}.published_at/retrieved_at 必须是 YYYY-MM-DD")
        if len(values["social_heat_signal"]) < 15:
            errors.append(
                f"{label}.social_heat_signal 至少 15 字，说明热榜、跨媒体跟进、平台讨论或当事方回应"
            )
        if len(values["transferable_mechanism"]) < 15:
            errors.append(f"{label}.transferable_mechanism 至少 15 字")
        if len(values["fact_boundary"]) < 20:
            errors.append(f"{label}.fact_boundary 至少 20 字，说明去标识化和虚构边界")

    ids = [item["news_id"] for item in normalized if item["news_id"]]
    if len(ids) != len(set(ids)):
        errors.append("hot_news_materials.news_id 不得重复")
    publishers = {item["publisher"] for item in normalized if item["publisher"]}
    hosts = {
        (urlparse(item["url"]).hostname or "").rstrip(".").lower()
        for item in normalized
        if item["url"]
    }
    distinct_required = min(required_count, len(normalized))
    if len(publishers) < distinct_required or len(hosts) < distinct_required:
        errors.append("社会热点材料必须来自至少两个不同发布者和站点")
    mechanisms = [item["transferable_mechanism"] for item in normalized if item["transferable_mechanism"]]
    if len(mechanisms) != len(set(mechanisms)):
        errors.append("社会热点材料不得用不同链接重复登记同一迁移机制")

    known_ids = set(ids)
    used_ids = {
        str(news_id or "").strip()
        for replacement in replacements
        if isinstance(replacement, dict)
        for news_id in replacement.get("news_ids") or []
        if str(news_id or "").strip()
    }
    unknown = sorted(used_ids - known_ids)
    if unknown:
        errors.append(f"P 拍替换引用了未知社会热点材料: {unknown}")
    unused = sorted(known_ids - used_ids)
    if unused:
        errors.append(f"社会热点材料未落到任何目标 P 拍: {unused}")
    news_by_beat = [
        {
            str(news_id or "").strip()
            for news_id in replacement.get("news_ids") or []
            if str(news_id or "").strip() in known_ids
        }
        for replacement in replacements
        if isinstance(replacement, dict)
    ]
    distinct_assignment_exists = required_count == 0 or (
        required_count == 1 and any(news_by_beat)
    )
    if required_count == 2:
        distinct_assignment_exists = any(
            first_news != second_news
            for first_index, first_ids in enumerate(news_by_beat)
            for second_ids in news_by_beat[first_index + 1 :]
            for first_news in first_ids
            for second_news in second_ids
        )
    if not distinct_assignment_exists:
        errors.append(
            f"至少 {required_count} 条不同社会热点材料必须分别落到 "
            f"{required_count} 个不同目标 P 拍"
        )
    return errors


def ensure_source_assets_unchanged(
    receipt: dict[str, Any], specs: list[dict[str, Any]]
) -> None:
    if receipt.get("sources") != [_public_source(spec) for spec in specs]:
        raise ValueError("来源资产已变更，旧纲层判断失效，请重新初始化并导出侧车")
    if receipt.get("source_hierarchy") != build_source_hierarchy(specs):
        raise ValueError("主体上层层级已变更，旧纲层判断失效，请重新初始化并导出侧车")


def ensure_source_assets_rebindable(
    receipt: dict[str, Any], specs: list[dict[str, Any]]
) -> None:
    """Allow preserve-by-evidence to carry a strictly additive SF repair."""
    expected_sources = [_public_source(spec) for spec in specs]
    expected_hierarchy = build_source_hierarchy(specs)
    if (
        receipt.get("sources") == expected_sources
        and receipt.get("source_hierarchy") == expected_hierarchy
    ):
        return

    old_sources = deepcopy(receipt.get("sources"))
    comparable_sources = deepcopy(expected_sources)
    if (
        not isinstance(old_sources, list)
        or len(old_sources) != len(comparable_sources)
        or not old_sources
    ):
        raise ValueError("来源资产已变更，旧纲层判断失效，请重新初始化并导出侧车")
    for source in (old_sources[0], comparable_sources[0]):
        if not isinstance(source, dict):
            raise ValueError("来源资产已变更，旧纲层判断失效，请重新初始化并导出侧车")
        source.pop("subflow_catalog", None)
        source.pop("subflow_layer_catalog", None)
    if old_sources != comparable_sources:
        raise ValueError("来源资产已变更，旧纲层判断失效，请重新初始化并导出侧车")

    old_hierarchy = deepcopy(receipt.get("source_hierarchy"))
    comparable_hierarchy = deepcopy(expected_hierarchy)
    for hierarchy in (old_hierarchy, comparable_hierarchy):
        if not isinstance(hierarchy, dict):
            raise ValueError("主体上层层级已变更，旧纲层判断失效，请重新初始化并导出侧车")
        for bridge in hierarchy.get("bridges") or []:
            if isinstance(bridge, dict):
                bridge.pop("source_prose_subflow_refs", None)
    if old_hierarchy != comparable_hierarchy:
        raise ValueError("主体上层层级已变更，旧纲层判断失效，请重新初始化并导出侧车")

    old_coverage = receipt.get("granularity_coverage")
    if not isinstance(old_coverage, list) or not old_coverage:
        raise ValueError("旧合同缺少可验证的 SF 覆盖，不能保留纲层判断")
    new_coverage = build_granularity_coverage(
        specs,
        receipt.get("outline_catalog") or {},
        receipt.get("mapping") or {},
    )
    def without_layer_topology(item: Any) -> Any:
        normalized = deepcopy(item)
        if isinstance(normalized, dict):
            normalized.pop("source_layer_order", None)
            normalized.pop("source_layer_topology", None)
        return normalized

    new_by_ref = {
        str(item.get("source_ref") or "").strip(): without_layer_topology(item)
        for item in new_coverage
        if isinstance(item, dict)
    }
    changed_or_missing = [
        str(item.get("source_ref") or "").strip()
        for item in old_coverage
        if not isinstance(item, dict)
        or new_by_ref.get(str(item.get("source_ref") or "").strip())
        != without_layer_topology(item)
    ]
    if changed_or_missing:
        raise ValueError(
            "主体旧 SF 被改写或删除，旧纲层判断失效: "
            + str(changed_or_missing[:8])
        )
    if len(new_coverage) < len(old_coverage):
        raise ValueError("主体 SF 目录发生非增补式变更，旧纲层判断失效")


def _granularity_evidence(value: Any) -> list[str]:
    """Extract only explicitly labelled evidence from a style dimension."""
    evidence: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key in ("evidence", "source_evidence", "quote", "excerpt"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    evidence.append(candidate.strip())
                elif isinstance(candidate, list):
                    for nested in candidate:
                        if isinstance(nested, str) and nested.strip():
                            evidence.append(nested.strip())
            for nested in item.values():
                if isinstance(nested, (dict, list)):
                    visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return list(dict.fromkeys(evidence))


def build_granularity_coverage(
    specs: list[dict[str, Any]], outline_catalog: dict[str, Any], mapping: dict[str, Any]
) -> list[dict[str, Any]]:
    primary = specs[0]
    targets = mapping.get("primary_plot_targets") or []
    target_regions = {
        beat["target_id"]: region["region_id"]
        for region in outline_catalog.get("regions") or []
        for beat in region.get("target_beats") or []
    }
    plot_pairs = list(zip(primary["plot_beats"], targets))
    source_lines = Path(primary["original"]["path"]).read_text(
        encoding="utf-8"
    ).splitlines()
    target_catalog = {
        beat["target_id"]: {
            "target_id": beat["target_id"],
            "target_region": region["region_id"],
            "outline_evidence": beat["evidence"],
        }
        for region in outline_catalog.get("regions") or []
        for beat in region.get("target_beats") or []
    }
    result: list[dict[str, Any]] = []
    for subflow in primary["prose_subflows"]:
        subflow_id = str(subflow["subflow_id"]).strip()
        sf_start, sf_end = _line_range(
            subflow.get("source_range"), f"主体子流程 {subflow_id}.source_range"
        )
        overlapping: list[tuple[dict[str, Any], str]] = []
        for beat, target in plot_pairs:
            beat_id = str(beat.get("beat_id") or "").strip()
            beat_start, beat_end = _line_range(
                beat.get("source_range"), f"主体情节拍 {beat_id}.source_range"
            )
            if beat_start <= sf_end and sf_start <= beat_end:
                overlapping.append((beat, str(target or "").strip()))
        if not overlapping and len(targets) == len(primary["plot_beats"]):
            raise ValueError(f"主体子流程 {subflow_id} 没有可按行区间关联的主体 P 拍")
        regions: list[str] = []
        for _, target in overlapping:
            region = target_regions.get(target)
            if region and region not in regions:
                regions.append(region)
        granularity = subflow["source_style_granularity"]
        target_carriers = []
        for beat, target in overlapping:
            carrier = target_catalog.get(target)
            if not carrier:
                continue
            target_carriers.append(
                {
                    "source_plot_ref": _source_ref(primary["source_id"], beat),
                    "source_range": str(beat.get("source_range") or "").strip(),
                    **deepcopy(carrier),
                }
            )
        result.append(
            {
                "source_ref": f"{primary['source_id']}:{subflow_id}",
                "parent_bridge_id": str(subflow.get("parent_bridge_id") or "").strip(),
                "source_range": str(subflow.get("source_range") or "").strip(),
                "style_dimensions": list(SOURCE_STYLE_GRANULARITY_FIELDS),
                "dimension_requirements": {
                    field: {
                        "analysis": deepcopy(granularity[field]),
                        "source_evidence": _granularity_evidence(granularity[field]),
                    }
                    for field in SOURCE_STYLE_GRANULARITY_FIELDS
                },
                "performance_requirements": {
                    "entry_state": str(subflow["entry_state"]).strip(),
                    "required_sequence": [
                        str(step).strip() for step in subflow["required_sequence"]
                    ],
                    "scene_granularity": str(
                        subflow["scene_granularity"]
                    ).strip(),
                    "emotion_sequence": [
                        str(step).strip() for step in subflow["emotion_sequence"]
                    ],
                    "end_state": str(subflow["end_state"]).strip(),
                    "source_excerpt": "\n".join(source_lines[sf_start - 1 : sf_end]),
                },
                "source_layer_order": deepcopy(subflow["source_layer_order"]),
                "source_layer_topology": deepcopy(
                    subflow["source_layer_topology"]
                ),
                "target_performance_carriers": target_carriers,
                "target_regions": regions,
            }
        )
    return result


def empty_sf_performance_bindings(
    granularity_coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create the manual pre-draft bindings inside the existing outline sidecar."""
    return [
        {
            "source_ref": item["source_ref"],
            "required_sequence_target_ids": [
                [] for _ in item["performance_requirements"]["required_sequence"]
            ],
            "emotion_sequence_target_ids": [
                [] for _ in item["performance_requirements"]["emotion_sequence"]
            ],
            "scene_granularity_target_ids": [],
            "source_layer_target_bindings": [
                {
                    "layer_id": layer["layer_id"],
                    "target_ids": [],
                    "preserved_layer_modes": deepcopy(layer["layer_modes"]),
                    "adaptation_instruction": "",
                }
                for layer in item["source_layer_topology"]
            ],
        }
        for item in granularity_coverage
    ]


def ensure_source_layer_binding_scaffold(
    bindings: list[dict[str, Any]],
    granularity_coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep valid older SF choices while adding the new per-layer decisions."""
    if not bindings:
        return empty_sf_performance_bindings(granularity_coverage)
    by_ref = {
        str(item.get("source_ref") or "").strip(): item
        for item in bindings
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for coverage in granularity_coverage:
        source_ref = str(coverage.get("source_ref") or "").strip()
        existing = deepcopy(by_ref.get(source_ref) or {})
        if not existing:
            existing = next(
                item
                for item in empty_sf_performance_bindings([coverage])
            )
        existing["source_ref"] = source_ref
        expected_layers = coverage.get("source_layer_topology") or []
        old_layers = {
            str(item.get("layer_id") or "").strip(): item
            for item in existing.get("source_layer_target_bindings") or []
            if isinstance(item, dict)
        }
        existing["source_layer_target_bindings"] = [
            deepcopy(old_layers[layer["layer_id"]])
            if layer["layer_id"] in old_layers
            else {
                "layer_id": layer["layer_id"],
                "target_ids": [],
                "preserved_layer_modes": deepcopy(layer["layer_modes"]),
                "adaptation_instruction": "",
            }
            for layer in expected_layers
        ]
        result.append(existing)
    return result


def validate_sf_performance_bindings(
    bindings: Any,
    granularity_coverage: list[dict[str, Any]],
    outline_catalog: dict[str, Any],
) -> list[str]:
    """Require every whole-SF step to have an ordered target carrier before prose."""
    errors: list[str] = []
    if not isinstance(bindings, list):
        return ["sf_performance_bindings 必须是列表"]
    expected_refs = [item["source_ref"] for item in granularity_coverage]
    actual_refs = [
        str(item.get("source_ref") or "").strip()
        for item in bindings
        if isinstance(item, dict)
    ]
    if actual_refs != expected_refs:
        errors.append("sf_performance_bindings 必须与主体全部 SF 完整同序")
    ranks = _target_rank(outline_catalog)
    region_by_target = {
        str(beat.get("target_id") or "").strip(): str(
            region.get("region_id") or ""
        ).strip()
        for region in outline_catalog.get("regions") or []
        for beat in region.get("target_beats") or []
        if isinstance(beat, dict)
    }

    def validate_groups(
        groups: Any,
        expected_count: int,
        allowed_targets: set[str],
        label: str,
    ) -> set[str]:
        used: set[str] = set()
        if not isinstance(groups, list) or len(groups) != expected_count:
            errors.append(f"{label} 必须与来源步骤等长")
            return used
        previous_rank = -1
        missing_steps: list[int] = []
        for index, targets in enumerate(groups, start=1):
            if not isinstance(targets, list) or not targets:
                missing_steps.append(index)
                continue
            normalized = [str(target or "").strip() for target in targets]
            if any(not target or target not in allowed_targets for target in normalized):
                errors.append(f"{label}[{index}] 只能引用当前 SF 的目标承载细拍")
                continue
            target_ranks = [ranks[target] for target in normalized if target in ranks]
            if target_ranks != sorted(target_ranks) or (
                target_ranks and target_ranks[0] < previous_rank
            ):
                errors.append(f"{label}[{index}] 必须保持来源表演顺序")
            if target_ranks:
                previous_rank = target_ranks[-1]
            used.update(normalized)
        if missing_steps:
            errors.append(f"{label} 以下步骤必须绑定目标细拍: {missing_steps}")
        return used

    for expected, actual in zip(granularity_coverage, bindings):
        if not isinstance(actual, dict):
            errors.append("sf_performance_bindings 每项必须是对象")
            continue
        source_ref = expected["source_ref"]
        allowed_targets = {
            str(carrier.get("target_id") or "").strip()
            for carrier in expected.get("target_performance_carriers") or []
            if isinstance(carrier, dict)
        }
        carrier_ranks = sorted(
            ranks[target] for target in allowed_targets if target in ranks
        )
        if carrier_ranks:
            first_carrier_rank = carrier_ranks[0]
            last_carrier_rank = carrier_ranks[-1]
            layer_allowed_targets = {
                target
                for target, rank in ranks.items()
                if first_carrier_rank <= rank <= last_carrier_rank
            }
        else:
            layer_allowed_targets = set(allowed_targets)
        performance = expected.get("performance_requirements")
        if not isinstance(performance, dict):
            errors.append(f"主体 SF {source_ref} 缺少完整写前表演链")
            continue
        sequence_used = validate_groups(
            actual.get("required_sequence_target_ids"),
            len(performance["required_sequence"]),
            allowed_targets,
            f"sf_performance_bindings[{source_ref}].required_sequence_target_ids",
        )
        emotion_used = validate_groups(
            actual.get("emotion_sequence_target_ids"),
            len(performance["emotion_sequence"]),
            allowed_targets,
            f"sf_performance_bindings[{source_ref}].emotion_sequence_target_ids",
        )
        scene_targets = actual.get("scene_granularity_target_ids")
        if not isinstance(scene_targets, list) or not scene_targets:
            errors.append(
                f"sf_performance_bindings[{source_ref}].scene_granularity_target_ids "
                "必须绑定至少一个目标细拍"
            )
            scene_used: set[str] = set()
        else:
            normalized_scene = [str(target or "").strip() for target in scene_targets]
            if any(
                not target or target not in allowed_targets
                for target in normalized_scene
            ):
                errors.append(
                    f"sf_performance_bindings[{source_ref}].scene_granularity_target_ids "
                    "只能引用当前 SF 的目标承载细拍"
                )
            scene_used = set(normalized_scene)
        expected_layers = expected.get("source_layer_topology")
        actual_layers = actual.get("source_layer_target_bindings")
        if not isinstance(expected_layers, list) or not expected_layers:
            errors.append(f"主体 SF {source_ref} 缺少来源逐层拓扑")
            layer_used: set[str] = set()
        elif not isinstance(actual_layers, list) or len(actual_layers) != len(
            expected_layers
        ):
            errors.append(
                f"sf_performance_bindings[{source_ref}].source_layer_target_bindings "
                "必须与来源层次完整同序"
            )
            layer_used = set()
        else:
            layer_used = set()
            previous_layer_rank = -1
            adaptation_notes: list[str] = []
            for layer_index, (source_layer, layer_binding) in enumerate(
                zip(expected_layers, actual_layers), start=1
            ):
                layer_label = (
                    f"sf_performance_bindings[{source_ref}]"
                    f".source_layer_target_bindings[{layer_index}]"
                )
                if not isinstance(layer_binding, dict):
                    errors.append(f"{layer_label} 必须是对象")
                    continue
                if layer_binding.get("layer_id") != source_layer.get("layer_id"):
                    errors.append(f"{layer_label}.layer_id 必须与来源层一致")
                if layer_binding.get("preserved_layer_modes") != source_layer.get(
                    "layer_modes"
                ):
                    errors.append(
                        f"{layer_label}.preserved_layer_modes 不得改写来源层型"
                    )
                targets = layer_binding.get("target_ids")
                if not isinstance(targets, list) or not targets:
                    errors.append(f"{layer_label}.target_ids 必须绑定目标细拍")
                    continue
                normalized_targets = [str(target or "").strip() for target in targets]
                if any(
                    not target or target not in layer_allowed_targets
                    for target in normalized_targets
                ):
                    errors.append(
                        f"{layer_label}.target_ids 只能引用当前 SF 最早与最晚 P 承载细拍"
                        "之间的目标细拍"
                    )
                    continue
                target_ranks = [ranks[target] for target in normalized_targets]
                if target_ranks != sorted(target_ranks) or (
                    target_ranks and target_ranks[0] < previous_layer_rank
                ):
                    errors.append(f"{layer_label} 必须保持来源层次顺序")
                if target_ranks:
                    previous_layer_rank = target_ranks[-1]
                layer_used.update(normalized_targets)
                instruction = str(
                    layer_binding.get("adaptation_instruction") or ""
                ).strip()
                if len(instruction) < 20:
                    errors.append(
                        f"{layer_label}.adaptation_instruction 至少 20 字，"
                        "必须说明目标层怎样保留来源层型、连接和气口"
                    )
                adaptation_notes.append(instruction)
            nonempty_notes = [note for note in adaptation_notes if note]
            if len(nonempty_notes) != len(set(nonempty_notes)):
                errors.append(
                    f"sf_performance_bindings[{source_ref}] 各来源层必须填写专属施工说明，"
                    "不得复用同一模板"
                )
        covered_regions = {
            region_by_target.get(target, "")
            for target in sequence_used | emotion_used | scene_used | layer_used
        }
        if not set(expected.get("target_regions") or []).issubset(covered_regions):
            errors.append(
                f"sf_performance_bindings[{source_ref}] 必须在写前覆盖该 SF 的全部目标区域"
            )
        layer_regions = {
            region_by_target.get(target, "") for target in layer_used
        }
        if not set(expected.get("target_regions") or []).issubset(layer_regions):
            errors.append(
                f"sf_performance_bindings[{source_ref}] 的来源层次绑定必须覆盖全部目标区域"
            )
    return errors


def build_sections(
    outline_catalog: dict[str, Any],
    sequences: dict[str, Any],
    mapping: dict[str, Any],
    granularity_coverage: list[dict[str, Any]],
    p_beat_replacements: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    plot_pairs = dict(zip(sequences["primary_plot_refs"], mapping.get("primary_plot_targets") or []))
    emotion_pairs = dict(zip(sequences["primary_emotion_refs"], mapping.get("primary_emotion_targets") or []))
    aux_pairs = {
        source_id: dict(zip(refs, (mapping.get("auxiliary_plot_targets") or {}).get(source_id) or []))
        for source_id, refs in sequences["auxiliary_plot_refs"].items()
    }
    replacement_by_ref = {
        str(item.get("source_ref") or "").strip(): deepcopy(item)
        for item in p_beat_replacements or []
        if isinstance(item, dict)
    }
    target_region: dict[str, str] = {}
    for region in outline_catalog["regions"]:
        for beat in region["target_beats"]:
            target_region[beat["target_id"]] = region["region_id"]
    sections: list[dict[str, Any]] = []
    numeric_region_ids = [
        region["region_id"]
        for region in outline_catalog["regions"]
        if region["region_id"].startswith("section:")
    ]
    for region in outline_catalog["regions"]:
        if not region["region_id"].startswith("section:"):
            continue
        section_id = region["region_id"].split(":", 1)[1]
        plot_refs = [ref for ref, target in plot_pairs.items() if target_region.get(target) == region["region_id"]]
        emotion_refs = [ref for ref, target in emotion_pairs.items() if target_region.get(target) == region["region_id"]]
        auxiliary_refs = [
            ref
            for pairs in aux_pairs.values()
            for ref, target in pairs.items()
            if target_region.get(target) == region["region_id"]
        ]
        covered_regions = {region["region_id"]}
        if numeric_region_ids and region["region_id"] == numeric_region_ids[-1]:
            covered_regions.add("epilogue")
        prose_subflow_refs = [
            item["source_ref"]
            for item in granularity_coverage
            if covered_regions.intersection(item["target_regions"])
        ]
        target_chars = region["target_chars"]
        sections.append(
            {
                "section_id": section_id,
                "target_chars": deepcopy(target_chars),
                "outline_evidence": [beat["evidence"] for beat in region["target_beats"]],
                "scene_units": [
                    {
                        "scene_id": f"S{section_id}-01",
                        "summary": region["scene_summary"],
                        "allocated_chars": (target_chars["min"] + target_chars["max"]) // 2,
                        "emotion_beat_ids": [ref.split(":", 1)[1] for ref in emotion_refs],
                        "plot_beat_ids": [ref.split(":", 1)[1] for ref in plot_refs],
                        "p_beat_replacements": [
                            replacement_by_ref[ref]
                            for ref in plot_refs
                            if ref in replacement_by_ref
                        ],
                        "auxiliary_plot_beat_refs": auxiliary_refs,
                        "prose_subflow_refs": prose_subflow_refs,
                        "prose_style_dimensions": list(SOURCE_STYLE_GRANULARITY_FIELDS),
                    }
                ],
            }
        )
    return sections


def create_receipt(project: str, outline_path: Path, config_path: Path) -> dict[str, Any]:
    outline = outline_path.resolve()
    config = config_path.resolve()
    specs = source_specs(config)
    if not specs or specs[0]["role"] != "primary":
        raise ValueError("项目必须有且只有第一项主体来源")
    catalog = parse_outline(outline)
    sequences = expected_sequences(specs)
    mapping = {
        "primary_plot_targets": [],
        "primary_emotion_targets": [],
        "auxiliary_plot_targets": {source_id: [] for source_id in sequences["auxiliary_plot_refs"]},
    }
    granularity_coverage = build_granularity_coverage(specs, catalog, mapping)
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "created_at": now_iso(),
        "gate_status": "pending",
        "outline": binding(outline),
        "project_config": binding(config),
        "sources": [_public_source(spec) for spec in specs],
        "source_hierarchy": build_source_hierarchy(specs),
        "outline_catalog": catalog,
        "mapping": mapping,
        "hot_news_materials": [],
        "p_beat_replacements": [],
        "granularity_coverage": granularity_coverage,
        "sf_performance_bindings": [],
        "manual_confirmation": {
            "full_story_hierarchy_preserved": None,
            "primary_plot_slots_replaced_one_to_one_and_in_order": None,
            "primary_emotion_complete_and_in_order": None,
            "auxiliary_is_plot_mechanism_only": None,
            "primary_is_exclusive_prose_voice": None,
            "primary_full_prose_granularity_loaded": None,
            "source_event_shell_rejected": None,
            "hot_news_is_event_mechanism_only": None,
            "manual_judgment": "",
        },
        "sections": build_sections(catalog, sequences, mapping, granularity_coverage, []),
        "blocking_failures": list(catalog["errors"]),
    }


def _source_hint(spec: dict[str, Any], beat: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "plot":
        summary = " / ".join(
            str(beat.get(key) or "").strip()
            for key in ("actor", "action", "object_or_receiver", "consequence")
            if str(beat.get(key) or "").strip()
        )
    else:
        summary = " / ".join(
            str(beat.get(key) or "").strip()
            for key in ("role", "trigger", "relationship_position_change", "reader_effect")
            if str(beat.get(key) or "").strip()
        )
    evidence = beat.get("source_evidence")
    if isinstance(evidence, list):
        evidence = next((str(item).strip() for item in evidence if str(item).strip()), "")
    return {
        "source_ref": _source_ref(spec["source_id"], beat),
        "bridge_ids": list(beat.get("bid_ids") or []),
        "summary": summary,
        "source_evidence": str(evidence or "").strip(),
    }


def export_template(receipt_path: Path, output_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲迁移合同")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("只能从紧凑纲层迁移合同导出模板")
    config_path = Path(receipt["project_config"]["path"])
    specs = source_specs(config_path)
    ensure_source_assets_unchanged(receipt, specs)
    manual_confirmation = deepcopy(receipt["manual_confirmation"])
    manual_confirmation.setdefault("primary_full_prose_granularity_loaded", None)
    template = {
        "schema_version": TEMPLATE_SCHEMA,
        "receipt_path": str(receipt_path.resolve()),
        "receipt_sha256": sha256(receipt_path),
        "instructions": (
            "三个 targets 数组分别与对应 source 序列等长同序；每项只填一个 target_id。"
            "完整保留上层关系/BID/E/SF 层级，只逐拍替换主体 P 拍事件壳；"
            "每个 SF 的必经顺序、情绪序列和场面颗粒必须在写正文前绑定到该 SF 的目标细拍，"
            "每个来源层也必须完整同序绑定目标细拍，保留原层型、连接和气口并填写专属施工说明；"
            "同一数组内保持来源顺序，跨区 SF 必须覆盖全部落点；"
            "只有用户明确要求热点时才填写热点字段，且只允许有热度证据的非政府社会新闻或网络热梗供应目标 P 拍的现实机制。"
        ),
        "target_catalog": [
            {
                "region_id": region["region_id"],
                "target_beats": deepcopy(region["target_beats"]),
            }
            for region in receipt["outline_catalog"]["regions"]
        ],
        "source_sequences": {
            "primary_plot": [_source_hint(specs[0], beat, "plot") for beat in specs[0]["plot_beats"]],
            "primary_emotion": [_source_hint(specs[0], beat, "emotion") for beat in specs[0]["emotion_beats"]],
            "auxiliary_plot": {
                spec["source_id"]: [_source_hint(spec, beat, "plot") for beat in spec["plot_beats"]]
                for spec in specs[1:]
            },
        },
        "mapping": deepcopy(receipt["mapping"]),
        "source_performance_requirements": [
            {
                "source_ref": item["source_ref"],
                "performance_requirements": deepcopy(
                    item["performance_requirements"]
                ),
                "source_layer_order": deepcopy(item["source_layer_order"]),
                "source_layer_topology": deepcopy(item["source_layer_topology"]),
            }
            for item in receipt["granularity_coverage"]
        ],
        "sf_performance_bindings": (
            deepcopy(receipt.get("sf_performance_bindings"))
            if receipt.get("sf_performance_bindings")
            else empty_sf_performance_bindings(receipt["granularity_coverage"])
        ),
        "hot_news_materials": deepcopy(receipt.get("hot_news_materials") or []),
        "p_beat_replacements": _editable_p_replacements(receipt, specs),
        "manual_confirmation": manual_confirmation,
    }
    write_json(output_path, template)
    return template


def _target_rank(catalog: dict[str, Any]) -> dict[str, int]:
    return {
        beat["target_id"]: rank
        for rank, beat in enumerate(
            beat
            for region in catalog.get("regions") or []
            for beat in region.get("target_beats") or []
        )
    }


def _validate_target_sequence(
    targets: Any, refs: list[str], ranks: dict[str, int], label: str, errors: list[str]
) -> list[str]:
    if not isinstance(targets, list):
        errors.append(f"{label} 必须是列表")
        return []
    normalized = [str(item or "").strip() for item in targets]
    if len(normalized) != len(refs):
        errors.append(f"{label} 必须与来源序列等长: expected={len(refs)}, actual={len(normalized)}")
        return normalized
    unknown = [item for item in normalized if item not in ranks]
    if unknown:
        errors.append(f"{label} 含未知 target_id: {unknown[:8]}")
    if len(normalized) != len(set(normalized)):
        errors.append(f"{label} 不得把多个同类来源拍并到同一目标细拍")
    known_ranks = [ranks[item] for item in normalized if item in ranks]
    if known_ranks != sorted(known_ranks):
        errors.append(f"{label} 必须保持来源原序，不能跨目标区域倒序")
    return normalized


def validate_data(data: dict[str, Any], outline_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version 必须为 {SCHEMA_VERSION}"]
    try:
        config_binding = data.get("project_config") or {}
        config_path = Path(str(config_binding.get("path") or "")).resolve()
        if not config_path.is_file() or config_binding.get("sha256") != sha256(config_path):
            errors.append("项目写作配置绑定失效")
            return errors
        specs = source_specs(config_path)
        outline_binding = data.get("outline") or {}
        bound_outline = Path(str(outline_binding.get("path") or "")).resolve()
        actual_outline = outline_path.resolve() if outline_path else bound_outline
        if actual_outline != bound_outline:
            errors.append("--outline 与合同绑定路径不一致")
        if not bound_outline.is_file() or outline_binding.get("sha256") != sha256(bound_outline):
            errors.append("小节大纲绑定失效")
            return errors
        actual_catalog = parse_outline(bound_outline)
        if actual_catalog != data.get("outline_catalog"):
            errors.append("outline_catalog 与当前小节大纲的确定性解析结果不一致")
        errors.extend(actual_catalog["errors"])
        expected_sources = [_public_source(spec) for spec in specs]
        if data.get("sources") != expected_sources:
            errors.append("sources 与项目配置及来源账本不一致")
        expected_hierarchy = build_source_hierarchy(specs)
        if data.get("source_hierarchy") != expected_hierarchy:
            errors.append("source_hierarchy 必须完整保留主体 BID、E 拍和 SF 上层结构")
        sequences = expected_sequences(specs)
        mapping = data.get("mapping") or {}
        ranks = _target_rank(actual_catalog)
        _validate_target_sequence(
            mapping.get("primary_plot_targets"),
            sequences["primary_plot_refs"],
            ranks,
            "mapping.primary_plot_targets",
            errors,
        )
        _validate_target_sequence(
            mapping.get("primary_emotion_targets"),
            sequences["primary_emotion_refs"],
            ranks,
            "mapping.primary_emotion_targets",
            errors,
        )
        aux_targets = mapping.get("auxiliary_plot_targets")
        if not isinstance(aux_targets, dict) or set(aux_targets) != set(sequences["auxiliary_plot_refs"]):
            errors.append("mapping.auxiliary_plot_targets 必须与选中辅助来源完全一致")
            aux_targets = aux_targets if isinstance(aux_targets, dict) else {}
        for source_id, refs in sequences["auxiliary_plot_refs"].items():
            _validate_target_sequence(
                aux_targets.get(source_id), refs, ranks,
                f"mapping.auxiliary_plot_targets.{source_id}", errors,
            )
        replacements = data.get("p_beat_replacements")
        errors.extend(
            validate_p_replacements(replacements, specs, mapping, actual_catalog)
        )
        normalized_replacements = (
            replacements if isinstance(replacements, list) else []
        )
        errors.extend(
            validate_hot_news_materials(
                data.get("hot_news_materials"), normalized_replacements
            )
        )
        confirmation = data.get("manual_confirmation")
        if not isinstance(confirmation, dict):
            errors.append("manual_confirmation 必须是对象")
        else:
            for field in (
                "full_story_hierarchy_preserved",
                "primary_plot_slots_replaced_one_to_one_and_in_order",
                "primary_emotion_complete_and_in_order",
                "auxiliary_is_plot_mechanism_only",
                "primary_is_exclusive_prose_voice",
                "primary_full_prose_granularity_loaded",
                "source_event_shell_rejected",
            ):
                if confirmation.get(field) is not True:
                    errors.append(f"manual_confirmation.{field} 必须为 true")
            if data.get("hot_news_materials") and (
                confirmation.get("hot_news_is_event_mechanism_only") is not True
            ):
                errors.append(
                    "manual_confirmation.hot_news_is_event_mechanism_only 必须为 true"
                )
            if len(str(confirmation.get("manual_judgment") or "").strip()) < 30:
                errors.append("manual_confirmation.manual_judgment 至少 30 字")
        expected_coverage = build_granularity_coverage(specs, actual_catalog, mapping)
        if data.get("granularity_coverage") != expected_coverage:
            errors.append("granularity_coverage 必须由主体子流程、P 拍映射和原文行区间确定性生成")
        empty_subflows = [
            item["source_ref"]
            for item in expected_coverage
            if not item["target_regions"]
        ]
        if empty_subflows:
            errors.append(f"主体文字子流程未映射到目标区域: {empty_subflows}")
        errors.extend(
            validate_sf_performance_bindings(
                data.get("sf_performance_bindings"),
                expected_coverage,
                actual_catalog,
            )
        )
        expected_sections = build_sections(
            actual_catalog,
            sequences,
            mapping,
            expected_coverage,
            normalized_replacements,
        )
        if data.get("sections") != expected_sections:
            errors.append("sections 必须由当前映射和细纲确定性生成，不得人工改写")
    except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def validate_receipt(receipt_path: Path, outline_path: Path | None = None) -> list[str]:
    return validate_data(read_json(receipt_path, "细纲迁移合同"), outline_path)


def apply_template(receipt_path: Path, template_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲迁移合同")
    template = read_json(template_path, "纲层迁移侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError(f"侧车 schema_version 必须为 {TEMPLATE_SCHEMA}")
    if Path(str(template.get("receipt_path") or "")).resolve() != receipt_path.resolve():
        raise ValueError("侧车 receipt_path 与正式合同不一致")
    if template.get("receipt_sha256") != sha256(receipt_path):
        raise ValueError("侧车绑定的正式合同 SHA 已失效，请重新导出")
    expected_performance_requirements = [
        {
            "source_ref": item["source_ref"],
            "performance_requirements": deepcopy(item["performance_requirements"]),
            "source_layer_order": deepcopy(item["source_layer_order"]),
            "source_layer_topology": deepcopy(item["source_layer_topology"]),
        }
        for item in receipt.get("granularity_coverage") or []
    ]
    if template.get("source_performance_requirements") != expected_performance_requirements:
        raise ValueError("侧车中的主体 SF 完整表演要求不得改写或删减")
    merged = deepcopy(receipt)
    merged["mapping"] = deepcopy(template.get("mapping"))
    merged["sf_performance_bindings"] = deepcopy(
        template.get("sf_performance_bindings")
    )
    merged["hot_news_materials"] = deepcopy(template.get("hot_news_materials"))
    merged["manual_confirmation"] = deepcopy(template.get("manual_confirmation"))
    specs = source_specs(Path(merged["project_config"]["path"]))
    ensure_source_assets_unchanged(receipt, specs)
    sequences = expected_sequences(specs)
    merged["sources"] = [_public_source(spec) for spec in specs]
    merged["source_hierarchy"] = build_source_hierarchy(specs)
    replacements = build_p_replacements(
        template.get("p_beat_replacements"),
        specs,
        merged["mapping"],
        merged["outline_catalog"],
    )
    merged["p_beat_replacements"] = replacements
    coverage = build_granularity_coverage(
        specs, merged["outline_catalog"], merged["mapping"]
    )
    merged["granularity_coverage"] = coverage
    merged["sections"] = build_sections(
        merged["outline_catalog"],
        sequences,
        merged["mapping"],
        coverage,
        replacements,
    )
    merged["gate_status"] = "pending"
    merged["blocking_failures"] = []
    errors = validate_data(merged)
    if errors:
        raise ValueError("；".join(errors))
    merged["gate_status"] = "passed"
    merged["reviewed_at"] = now_iso()
    write_json(receipt_path, merged)
    try:
        template_path.unlink()
    except OSError:
        # The merged receipt is authoritative; failed cleanup must not undo it.
        pass
    return merged


def _catalog_from_template(template: dict[str, Any]) -> dict[str, Any]:
    regions = template.get("target_catalog")
    if not isinstance(regions, list):
        raise ValueError("纲层迁移侧车缺少 target_catalog")
    return {"regions": deepcopy(regions), "errors": []}


def _mapping_has_targets(mapping: Any) -> bool:
    if not isinstance(mapping, dict):
        return False
    if mapping.get("primary_plot_targets") or mapping.get("primary_emotion_targets"):
        return True
    auxiliaries = mapping.get("auxiliary_plot_targets")
    return isinstance(auxiliaries, dict) and any(auxiliaries.values())


def _preservation_source(
    receipt_path: Path,
    receipt: dict[str, Any],
    specs: list[dict[str, Any]],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    mapping = receipt.get("mapping")
    if _mapping_has_targets(mapping):
        return (
            deepcopy(receipt.get("outline_catalog") or {}),
            deepcopy(mapping),
            deepcopy(receipt.get("manual_confirmation") or {}),
            deepcopy(receipt.get("hot_news_materials") or []),
            _editable_p_replacements(receipt, specs),
            deepcopy(receipt.get("sf_performance_bindings") or []),
        )

    sidecar_path = receipt_path.with_name("纲层迁移侧车.json")
    if not sidecar_path.is_file():
        raise ValueError("当前合同没有可迁移映射，且未找到同目录纲层迁移侧车")
    template = read_json(sidecar_path, "纲层迁移侧车")
    if template.get("schema_version") != TEMPLATE_SCHEMA:
        raise ValueError(f"纲层迁移侧车 schema_version 必须为 {TEMPLATE_SCHEMA}")
    if Path(str(template.get("receipt_path") or "")).resolve() != receipt_path.resolve():
        raise ValueError("纲层迁移侧车 receipt_path 与正式合同不一致")
    template_mapping = template.get("mapping")
    if not _mapping_has_targets(template_mapping):
        raise ValueError("纲层迁移侧车没有可迁移映射")
    return (
        _catalog_from_template(template),
        deepcopy(template_mapping),
        deepcopy(template.get("manual_confirmation") or {}),
        deepcopy(template.get("hot_news_materials") or []),
        deepcopy(template.get("p_beat_replacements") or []),
        deepcopy(template.get("sf_performance_bindings") or []),
    )


def _targets_by_evidence(catalog: dict[str, Any], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    duplicates: set[str] = set()
    for region in catalog.get("regions") or []:
        for beat in region.get("target_beats") or []:
            evidence = str(beat.get("evidence") or "").strip()
            target_id = str(beat.get("target_id") or "").strip()
            if not evidence or not target_id:
                raise ValueError(f"{label} 含缺少 evidence 或 target_id 的细拍")
            if evidence in result:
                duplicates.add(evidence)
            result[evidence] = target_id
    if duplicates:
        raise ValueError(f"{label} 存在重复细拍证据，无法确定性迁移: {sorted(duplicates)[:3]}")
    return result


def migrate_mapping_by_evidence(
    old_catalog: dict[str, Any],
    new_catalog: dict[str, Any],
    old_mapping: dict[str, Any],
    allow_manual_remap: bool = False,
) -> dict[str, Any]:
    old_targets = {
        str(beat.get("target_id") or "").strip(): str(beat.get("evidence") or "").strip()
        for region in old_catalog.get("regions") or []
        for beat in region.get("target_beats") or []
    }
    new_targets = _targets_by_evidence(new_catalog, "新细纲")

    def migrate(targets: Any, label: str) -> list[str]:
        if not isinstance(targets, list):
            raise ValueError(f"{label} 必须是列表")
        migrated: list[str] = []
        for target in targets:
            old_target = str(target or "").strip()
            if not old_target and allow_manual_remap:
                migrated.append("")
                continue
            evidence = old_targets.get(old_target)
            if not evidence:
                raise ValueError(f"{label} 含旧细纲未知 target_id: {old_target}")
            new_target = new_targets.get(evidence)
            if not new_target:
                if allow_manual_remap:
                    migrated.append("")
                    continue
                raise ValueError(f"{label} 的细拍证据已被改写或删除: {evidence}")
            migrated.append(new_target)
        return migrated

    auxiliary = old_mapping.get("auxiliary_plot_targets")
    if not isinstance(auxiliary, dict):
        raise ValueError("mapping.auxiliary_plot_targets 必须是对象")
    return {
        "primary_plot_targets": migrate(
            old_mapping.get("primary_plot_targets"), "mapping.primary_plot_targets"
        ),
        "primary_emotion_targets": migrate(
            old_mapping.get("primary_emotion_targets"), "mapping.primary_emotion_targets"
        ),
        "auxiliary_plot_targets": {
            source_id: migrate(targets, f"mapping.auxiliary_plot_targets.{source_id}")
            for source_id, targets in auxiliary.items()
        },
    }


def migrate_sf_performance_bindings_by_evidence(
    old_catalog: dict[str, Any],
    new_catalog: dict[str, Any],
    bindings: list[dict[str, Any]],
    allow_manual_remap: bool = False,
) -> list[dict[str, Any]]:
    """Move pre-draft SF carrier choices with unchanged outline evidence."""
    if not bindings:
        return []
    old_targets = {
        str(beat.get("target_id") or "").strip(): str(
            beat.get("evidence") or ""
        ).strip()
        for region in old_catalog.get("regions") or []
        for beat in region.get("target_beats") or []
    }
    new_targets = _targets_by_evidence(new_catalog, "新细纲")

    def migrate_ids(values: Any, label: str) -> list[str]:
        if not isinstance(values, list):
            raise ValueError(f"{label} 必须是列表")
        migrated: list[str] = []
        for value in values:
            old_target = str(value or "").strip()
            evidence = old_targets.get(old_target)
            if not evidence or evidence not in new_targets:
                if allow_manual_remap:
                    continue
                raise ValueError(f"{label} 的细拍证据已被改写或删除")
            migrated.append(new_targets[evidence])
        return migrated

    result = deepcopy(bindings)
    for binding_index, item in enumerate(result, start=1):
        if not isinstance(item, dict):
            raise ValueError("sf_performance_bindings 每项必须是对象")
        for field in (
            "required_sequence_target_ids",
            "emotion_sequence_target_ids",
        ):
            groups = item.get(field)
            if not isinstance(groups, list):
                raise ValueError(
                    f"sf_performance_bindings[{binding_index}].{field} 必须是列表"
                )
            item[field] = [
                migrate_ids(
                    group,
                    f"sf_performance_bindings[{binding_index}].{field}[{group_index}]",
                )
                for group_index, group in enumerate(groups, start=1)
            ]
        item["scene_granularity_target_ids"] = migrate_ids(
            item.get("scene_granularity_target_ids"),
            f"sf_performance_bindings[{binding_index}].scene_granularity_target_ids",
        )
        layer_bindings = item.get("source_layer_target_bindings")
        if layer_bindings is not None:
            if not isinstance(layer_bindings, list):
                raise ValueError(
                    f"sf_performance_bindings[{binding_index}].source_layer_target_bindings "
                    "必须是列表"
                )
            for layer_index, layer_binding in enumerate(layer_bindings, start=1):
                if not isinstance(layer_binding, dict):
                    raise ValueError(
                        f"sf_performance_bindings[{binding_index}]"
                        f".source_layer_target_bindings[{layer_index}] 必须是对象"
                    )
                layer_binding["target_ids"] = migrate_ids(
                    layer_binding.get("target_ids"),
                    f"sf_performance_bindings[{binding_index}]"
                    f".source_layer_target_bindings[{layer_index}].target_ids",
                )
    return result


def rebind_outline(
    receipt_path: Path,
    outline_path: Path,
    preserve_by_evidence: bool = False,
    allow_manual_remap: bool = False,
) -> dict[str, Any]:
    receipt = read_json(receipt_path, "细纲迁移合同")
    receipt_schema = receipt.get("schema_version")
    supported_schemas = {
        SCHEMA_VERSION,
        PREVIOUS_SCHEMA_VERSION,
        *LEGACY_SCHEMA_VERSIONS,
    }
    if receipt_schema not in supported_schemas:
        raise ValueError("只能重绑紧凑纲层迁移合同")
    if receipt_schema != SCHEMA_VERSION and not preserve_by_evidence:
        raise ValueError("旧合同升级必须使用 --preserve-by-evidence，避免丢失既有映射")
    if allow_manual_remap and not preserve_by_evidence:
        raise ValueError("--allow-manual-remap 必须与 --preserve-by-evidence 同时使用")
    config_path = Path(receipt["project_config"]["path"]).resolve()
    specs = source_specs(config_path)
    if preserve_by_evidence:
        ensure_source_assets_rebindable(receipt, specs)
    sequences = expected_sequences(specs)
    catalog = parse_outline(outline_path.resolve())
    if catalog["errors"]:
        raise ValueError("；".join(catalog["errors"]))
    if preserve_by_evidence:
        (
            old_catalog,
            old_mapping,
            manual_confirmation,
            hot_news_materials,
            editable_replacements,
            old_sf_performance_bindings,
        ) = _preservation_source(
            receipt_path, receipt, specs
        )
        mapping = migrate_mapping_by_evidence(
            old_catalog,
            catalog,
            old_mapping,
            allow_manual_remap=allow_manual_remap,
        )
        replacements = build_p_replacements(
            editable_replacements, specs, mapping, catalog
        )
        sf_performance_bindings = migrate_sf_performance_bindings_by_evidence(
            old_catalog,
            catalog,
            old_sf_performance_bindings,
            allow_manual_remap=allow_manual_remap,
        )
    else:
        mapping = {
            "primary_plot_targets": [],
            "primary_emotion_targets": [],
            "auxiliary_plot_targets": {
                source_id: [] for source_id in sequences["auxiliary_plot_refs"]
            },
        }
        manual_confirmation = {
            "full_story_hierarchy_preserved": None,
            "primary_plot_slots_replaced_one_to_one_and_in_order": None,
            "primary_emotion_complete_and_in_order": None,
            "auxiliary_is_plot_mechanism_only": None,
            "primary_is_exclusive_prose_voice": None,
            "primary_full_prose_granularity_loaded": None,
            "source_event_shell_rejected": None,
            "hot_news_is_event_mechanism_only": None,
            "manual_judgment": "",
        }
        hot_news_materials = []
        replacements = []
        sf_performance_bindings = []
    coverage = build_granularity_coverage(specs, catalog, mapping)
    receipt["outline"] = binding(outline_path)
    receipt["schema_version"] = SCHEMA_VERSION
    receipt["project_config"] = binding(config_path)
    receipt["sources"] = [_public_source(spec) for spec in specs]
    receipt["source_hierarchy"] = build_source_hierarchy(specs)
    receipt["outline_catalog"] = catalog
    receipt["mapping"] = mapping
    receipt["hot_news_materials"] = hot_news_materials
    receipt["p_beat_replacements"] = replacements
    receipt["granularity_coverage"] = coverage
    receipt["sf_performance_bindings"] = ensure_source_layer_binding_scaffold(
        sf_performance_bindings,
        coverage,
    )
    receipt["manual_confirmation"] = manual_confirmation
    receipt["sections"] = build_sections(
        catalog, sequences, mapping, coverage, replacements
    )
    receipt["gate_status"] = "pending"
    receipt["blocking_failures"] = []
    receipt["rebound_at"] = now_iso()
    if (
        preserve_by_evidence
        and sf_performance_bindings
        and receipt_schema == SCHEMA_VERSION
        and not allow_manual_remap
    ):
        errors = validate_data(receipt)
        if errors:
            raise ValueError("；".join(errors))
        receipt["gate_status"] = "passed"
        receipt["reviewed_at"] = now_iso()
    write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--outline", required=True)
    init.add_argument("--project-config", required=True)
    init.add_argument("--receipt", required=True)
    export = sub.add_parser("export-template")
    export.add_argument("--receipt", required=True)
    export.add_argument("--output", required=True)
    apply = sub.add_parser("apply-template")
    apply.add_argument("--receipt", required=True)
    apply.add_argument("--input", required=True)
    rebind = sub.add_parser("rebind-outline")
    rebind.add_argument("--receipt", required=True)
    rebind.add_argument("--outline", required=True)
    rebind.add_argument("--preserve-by-evidence", action="store_true")
    rebind.add_argument("--allow-manual-remap", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--outline")
    args = parser.parse_args()
    try:
        if args.command == "init":
            receipt_path = Path(args.receipt).resolve()
            if receipt_path.exists():
                raise ValueError(f"回执已存在，拒绝覆盖: {receipt_path}")
            write_json(
                receipt_path,
                create_receipt(
                    args.project,
                    Path(args.outline).resolve(),
                    Path(args.project_config).resolve(),
                ),
            )
            print("outline_migration_contract: initialized")
            return 0
        if args.command == "export-template":
            export_template(Path(args.receipt).resolve(), Path(args.output).resolve())
            print("outline_migration_contract: template_exported")
            return 0
        if args.command == "apply-template":
            apply_template(Path(args.receipt).resolve(), Path(args.input).resolve())
            print("outline_migration_contract: passed")
            return 0
        if args.command == "rebind-outline":
            rebind_outline(
                Path(args.receipt).resolve(),
                Path(args.outline).resolve(),
                preserve_by_evidence=args.preserve_by_evidence,
                allow_manual_remap=args.allow_manual_remap,
            )
            print("outline_migration_contract: rebound")
            return 0
        errors = validate_receipt(
            Path(args.receipt).resolve(),
            Path(args.outline).resolve() if args.outline else None,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("outline_migration_contract: blocked")
        print(f"- {exc}")
        return 2
    if errors:
        print("outline_migration_contract: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("outline_migration_contract: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
