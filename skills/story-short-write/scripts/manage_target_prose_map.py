#!/usr/bin/env python3
"""Manage target prose maps, incremental rebinding, and compact draft audits."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


TARGET_SCHEMA = "story-short-write.target-prose-map.v3"
AUDIT_SCHEMA = "story-short-write.prose-coverage-audit.v3"
SECTION_RE = re.compile(r"(?m)^(\d+)\.\s*$")
H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
OUTLINE_HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
OUTLINE_FIELD_RE = re.compile(r"(?m)^- ([^：\n]+)：(.*)$")
OUTLINE_SECTION_RE = re.compile(r"^(\d+)[.、．](?:\s+.*)?$")
OUTLINE_CHAR_RANGE_RE = re.compile(r"(\d+)\s*[-~至]\s*(\d+)\s*字")
SOURCE_MAP_COMMENT_RE = re.compile(
    r"\s*<!--\s*source-map:\s*(.*?)\s*-->\s*$", re.IGNORECASE
)
SOURCE_REF_KEYS = {
    "P": "plot_beat_ids",
    "E": "emotion_beat_ids",
    "SF": "subflow_steps",
    "L": "layer_ids",
}
REQUIRED_OUTLINE_FIELDS = (
    "主事件",
    "子事件",
    "入场状态",
    "离场状态",
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
REPLACEMENT_DIMENSIONS = {
    "actor",
    "relationship",
    "setting",
    "object",
    "conflict_mechanism",
    "information_mechanism",
    "consequence",
}
REPLACEMENT_DIMENSION_ORDER = (
    "actor",
    "relationship",
    "setting",
    "object",
    "conflict_mechanism",
    "information_mechanism",
    "consequence",
)
EMOTION_FIDELITY_FIELDS = (
    "content",
    "trigger",
    "relationship_position_change",
    "reader_effect",
    "intensity",
)
LAYER_TOPOLOGY_FIELDS = (
    "layer_modes",
    "entry_relation",
    "exit_relation",
    "narrative_distance",
)
PLOT_AUDIT_FIELDS = (
    "action",
    "control_change",
    "information_change",
    "consequence",
)
EMOTION_AUDIT_FIELDS = EMOTION_FIDELITY_FIELDS
LAYER_AUDIT_TOPOLOGY_FIELDS = LAYER_TOPOLOGY_FIELDS + ("no_function_shift",)


def _load_source_map_validator():
    path = (
        Path(__file__).resolve().parents[2]
        / "story-short-analyze"
        / "scripts"
        / "compile_source_prose_map.py"
    )
    spec = importlib.util.spec_from_file_location(
        "story_short_write_source_prose_map_validator", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载来源成文脑图 validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE_MAP_VALIDATOR = _load_source_map_validator()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def content_hash(payload: dict[str, Any]) -> str:
    return canonical_sha256(
        {key: value for key, value in payload.items() if key != "content_sha256"}
    )


def binding(path: Path) -> dict[str, str]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")
    return {"path": str(path), "sha256": file_sha256(path)}


def read_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是 JSON 对象: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_path(raw: str, base: Path) -> Path:
    candidate = Path(raw).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def resolve_source_map(
    project_dir: Path, explicit: Path | None = None
) -> tuple[Path, dict[str, Any]]:
    if explicit is not None:
        path = explicit.expanduser().resolve()
    else:
        config_path = project_dir / "写作资产" / "项目写作配置.json"
        config = read_object(config_path, "项目写作配置")
        primary = config.get("primary")
        if not isinstance(primary, dict):
            raise ValueError("项目写作配置缺少 primary")
        raw = str(primary.get("source_prose_map_path") or "").strip()
        if raw:
            path = resolve_path(raw, config_path.parent)
        else:
            profile_raw = str(primary.get("profile_path") or "").strip()
            if not profile_raw:
                raise ValueError(
                    "项目写作配置 primary 缺少 source_prose_map_path 或 profile_path"
                )
            profile_path = resolve_path(profile_raw, config_path.parent)
            path = profile_path.parent / "写作资产" / "来源成文脑图.json"
    payload = read_object(path, "来源成文脑图")
    source_errors = SOURCE_MAP_VALIDATOR.validate_source_map(payload, path)
    if source_errors:
        raise ValueError("来源成文脑图未通过校验: " + " / ".join(source_errors))
    return path, payload


def _outline_region_id(title: str) -> str | None:
    if title == "导语":
        return "opening"
    if title == "尾声":
        return "epilogue"
    match = OUTLINE_SECTION_RE.fullmatch(title)
    return f"section:{int(match.group(1))}" if match else None


def empty_source_refs() -> dict[str, list[str]]:
    return {value: [] for value in SOURCE_REF_KEYS.values()}


def parse_source_map_comment(value: str) -> tuple[str, dict[str, list[str]]]:
    match = SOURCE_MAP_COMMENT_RE.search(value)
    if not match:
        return value.strip(), empty_source_refs()
    refs = empty_source_refs()
    for field in match.group(1).split(";"):
        field = field.strip()
        if not field:
            continue
        if "=" not in field:
            raise ValueError(f"source-map 字段缺少等号: {field}")
        raw_key, raw_values = field.split("=", 1)
        key = raw_key.strip().upper()
        if key not in SOURCE_REF_KEYS:
            raise ValueError(f"source-map 包含未知字段: {key}")
        values = [item.strip() for item in raw_values.split(",") if item.strip()]
        if not values:
            raise ValueError(f"source-map.{key} 不能为空")
        refs[SOURCE_REF_KEYS[key]].extend(values)
    return value[: match.start()].rstrip(), refs


def normalize_source_refs(value: Any) -> dict[str, list[str]]:
    refs = empty_source_refs()
    if value is None:
        return refs
    if not isinstance(value, dict):
        raise ValueError("source_refs 必须是对象")
    for key in refs:
        raw = value.get(key) or []
        if not isinstance(raw, list) or any(
            not isinstance(item, str) or not item.strip() for item in raw
        ):
            raise ValueError(f"source_refs.{key} 必须是非空字符串数组")
        refs[key] = [item.strip() for item in raw]
    return refs


def parse_outline(
    outline_path: Path,
    allow_partial: bool = False,
    *,
    text: str | None = None,
) -> dict[str, Any]:
    if text is None:
        text = outline_path.read_text(encoding="utf-8")
    matches = list(OUTLINE_HEADING_RE.finditer(text))
    regions: list[dict[str, Any]] = []
    errors: list[str] = []
    target_ids: set[str] = set()
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        region_id = _outline_region_id(title)
        if region_id is None:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        fields: dict[str, list[str]] = {}
        for field_match in OUTLINE_FIELD_RE.finditer(body):
            name = field_match.group(1).strip()
            fields.setdefault(name, []).append(field_match.group(2).strip())
        missing = [field for field in REQUIRED_OUTLINE_FIELDS if not fields.get(field)]
        if missing:
            errors.append(f"{region_id} 缺少细纲字段: {missing}")
        fine_beats = fields.get("细拍拆分") or []
        target_beats: list[dict[str, str]] = []
        prefix = (
            "opening"
            if region_id == "opening"
            else "epilogue"
            if region_id == "epilogue"
            else region_id.split(":", 1)[1]
        )
        for beat_index, raw_evidence in enumerate(fine_beats, start=1):
            try:
                evidence, source_refs = parse_source_map_comment(raw_evidence)
            except ValueError as exc:
                errors.append(f"{region_id} 第 {beat_index} 条细拍 source-map 无效: {exc}")
                evidence, source_refs = raw_evidence.strip(), empty_source_refs()
            target_id = f"T-{prefix}-{beat_index:03d}"
            if target_id in target_ids:
                errors.append(f"细纲目标拍 ID 重复: {target_id}")
            target_ids.add(target_id)
            target_beats.append(
                {
                    "target_id": target_id,
                    "evidence": evidence,
                    "source_refs": source_refs,
                }
            )
        if not target_beats:
            errors.append(f"{region_id} 至少需要一条细拍拆分")
        char_min = char_max = 0
        raw_range = (fields.get("目标字数") or [""])[0]
        range_match = OUTLINE_CHAR_RANGE_RE.search(raw_range)
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
    # Exact reuse of region-level施工字段 is a placeholder pattern, not a valid
    # full-granularity outline. Catch it before any target mind-map is initialized.
    uniqueness_fields = (
        ("主事件", "main_event"),
        ("情绪", "emotion"),
        ("钩子", "hook"),
        ("伏笔/物件", "objects"),
        ("场面单元", "scene_summary"),
    )
    for label, key in uniqueness_fields:
        seen: dict[str, str] = {}
        for region in regions:
            value = str(region.get(key) or "").strip()
            if not value:
                continue
            prior = seen.get(value)
            if prior:
                errors.append(
                    f"区域字段{label}不得与{prior}完全重复: {region['region_id']}"
                )
            else:
                seen[value] = str(region.get("region_id") or "")
    actual = [item["region_id"] for item in regions]
    numeric_count = sum(
        1 for item in regions if item["region_id"].startswith("section:")
    )
    expected_prefix = ["opening"] + [
        f"section:{index}" for index in range(1, numeric_count + 1)
    ]
    if allow_partial:
        if actual not in (expected_prefix, expected_prefix + ["epilogue"]):
            errors.append(f"批次细纲区域必须从导语开始并保持数字节连续: {actual}")
    else:
        expected = expected_prefix + ["epilogue"]
        if actual != expected:
            errors.append(f"细纲区域必须为导语、连续数字节、尾声: {actual}")
    return {"regions": regions, "errors": errors}


def _outline_nodes(
    outline: Path,
    allow_partial: bool = False,
    *,
    text: str | None = None,
) -> list[dict[str, Any]]:
    catalog = parse_outline(outline, allow_partial=allow_partial, text=text)
    errors = catalog.get("errors") or []
    if errors:
        raise ValueError("小节大纲无法解析: " + " / ".join(str(item) for item in errors))
    nodes: list[dict[str, Any]] = []
    for region in catalog.get("regions") or []:
        region_id = str(region.get("region_id") or "").strip()
        for beat in region.get("target_beats") or []:
            target_id = str(beat.get("target_id") or "").strip()
            evidence = str(beat.get("evidence") or "").strip()
            if not target_id or not evidence:
                raise ValueError(f"{region_id} 存在空目标 ID 或空施工证据")
            node = {
                "target_id": target_id,
                "region_id": region_id,
                "evidence": evidence,
                "source_refs": normalize_source_refs(beat.get("source_refs")),
                "sequence_index": len(nodes) + 1,
            }
            node["content_sha256"] = canonical_sha256(node)
            nodes.append(node)
    if not nodes:
        raise ValueError("小节大纲没有可用目标节点")
    return nodes


def _mind_map_nodes(path: Path) -> list[dict[str, Any]]:
    payload = read_object(path, "用户脑图")
    roots = payload.get("nodes")
    if not isinstance(roots, list):
        root = payload.get("root")
        roots = [root] if isinstance(root, dict) else []
    flattened: list[dict[str, Any]] = []

    def visit(raw: Any, inherited_region: str) -> None:
        if not isinstance(raw, dict):
            raise ValueError("用户脑图节点必须是对象")
        children = raw.get("children") or []
        evidence = str(
            raw.get("evidence")
            or raw.get("content")
            or raw.get("summary")
            or raw.get("title")
            or raw.get("text")
            or ""
        ).strip()
        region_id = str(raw.get("region_id") or inherited_region or "opening").strip()
        if evidence:
            target_id = str(raw.get("id") or raw.get("target_id") or "").strip()
            if not target_id:
                target_id = f"T-MM-{len(flattened) + 1:03d}"
            node = {
                "target_id": target_id,
                "region_id": region_id,
                "evidence": evidence,
                "source_refs": normalize_source_refs(raw.get("source_refs")),
                "sequence_index": len(flattened) + 1,
            }
            node["content_sha256"] = canonical_sha256(node)
            flattened.append(node)
        if not isinstance(children, list):
            raise ValueError(f"脑图节点 {evidence or '<root>'} 的 children 必须是数组")
        for child in children:
            visit(child, region_id)

    for item in roots:
        visit(item, "opening")
    ids = [item["target_id"] for item in flattened]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("用户脑图目标节点 ID 必须非空且唯一")
    return flattened


def load_target_nodes(
    project_dir: Path,
    mind_map: Path | None,
    allow_partial: bool = False,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if mind_map is not None:
        path = mind_map.expanduser().resolve()
        return {"kind": "mind_map", **binding(path)}, _mind_map_nodes(path)
    path = project_dir / "小节大纲.md"
    return {"kind": "outline", **binding(path)}, _outline_nodes(
        path, allow_partial=allow_partial
    )


def preflight_outline_text(
    project_dir: Path, outline_text: str, *, allow_partial: bool = True
) -> tuple[dict[str, Any], list[str]]:
    """Validate an outline candidate without writing it to a side file."""
    source_path, source = resolve_source_map(project_dir)
    outline_path = project_dir / "小节大纲.md"
    catalog = parse_outline(outline_path, allow_partial=allow_partial, text=outline_text)
    errors = [str(item) for item in catalog.get("errors") or []]
    nodes: list[dict[str, Any]] = []
    if not errors:
        nodes = _outline_nodes(outline_path, allow_partial=allow_partial, text=outline_text)
        errors.extend(validate_explicit_source_refs(nodes, source, partial=allow_partial))
    return {
        "gate_status": "passed" if not errors else "blocked",
        "source_map": str(source_path),
        "target_input": {"kind": "outline-candidate"},
        "target_node_count": len(nodes),
    }, errors


def _empty_plot_mapping(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": item["beat_id"],
        "source_content_sha256": item["content_sha256"],
        "target_id": "",
    }


def _empty_emotion_mapping(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": item["beat_id"],
        "source_content_sha256": item["content_sha256"],
        "target_id": "",
    }


def _empty_subflow_mapping(item: dict[str, Any]) -> dict[str, Any]:
    sequence = item.get("required_sequence") or []
    return {
        "source_id": item["subflow_id"],
        "source_content_sha256": item["content_sha256"],
        "performance_chain": [
            {"step_index": index, "target_node_ids": []}
            for index, _ in enumerate(sequence, 1)
        ],
    }


def _empty_layer_mapping(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": item["layer_id"],
        "source_content_sha256": item["content_sha256"],
        "target_node_ids": [],
    }


def _empty_replacement(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": item["beat_id"],
        "source_content_sha256": item["content_sha256"],
        "dimensions_changed": [],
        "function_reviews": {field: "" for field in PLOT_AUDIT_FIELDS},
        "adaptation_decision": "",
        "human_confirmed": False,
    }


def validate_explicit_source_refs(
    target_nodes: list[dict[str, Any]],
    source: dict[str, Any],
    partial: bool = False,
) -> list[str]:
    errors: list[str] = []
    for node in target_nodes:
        refs = normalize_source_refs(node.get("source_refs"))
        if not any(refs.values()):
            errors.append(f"{node.get('target_id')} 缺少 source-map 来源覆盖声明")
        if len(refs["plot_beat_ids"]) > 1:
            errors.append(f"{node.get('target_id')} 同时承载多个 P 拍，必须拆成独立细拍")
        if len(refs["emotion_beat_ids"]) > 1:
            errors.append(f"{node.get('target_id')} 同时承载多个 E 拍，必须拆成独立细拍")

    expected_plot = [str(item["beat_id"]) for item in source.get("plot_beats") or []]
    expected_emotion = [
        str(item["beat_id"]) for item in source.get("emotion_beats") or []
    ]
    actual_plot = [
        source_id
        for node in target_nodes
        for source_id in normalize_source_refs(node.get("source_refs"))["plot_beat_ids"]
    ]
    actual_emotion = [
        source_id
        for node in target_nodes
        for source_id in normalize_source_refs(node.get("source_refs"))["emotion_beat_ids"]
    ]
    if partial:
        if len(actual_plot) != len(set(actual_plot)):
            errors.append("细纲批次 P 拍不得重复承接")
        if actual_plot != expected_plot[: len(actual_plot)]:
            errors.append(
                "细纲批次 P 拍必须是来源账连续前缀: "
                f"expected_prefix={expected_plot[:len(actual_plot)]}, actual={actual_plot}"
            )
        if len(actual_emotion) != len(set(actual_emotion)):
            errors.append("细纲批次 E 拍不得重复承接")
        if actual_emotion != expected_emotion[: len(actual_emotion)]:
            errors.append(
                "细纲批次 E 拍必须是来源账连续前缀: "
                f"expected_prefix={expected_emotion[:len(actual_emotion)]}, actual={actual_emotion}"
            )
    else:
        if actual_plot != expected_plot:
            errors.append(
                "细纲 P 拍声明必须与来源全量同序一对一: "
                f"expected={','.join(expected_plot)}, actual={','.join(actual_plot)}"
            )
        if actual_emotion != expected_emotion:
            errors.append(
                "细纲 E 拍声明必须与来源全量同序一对一: "
                f"expected={','.join(expected_emotion)}, actual={','.join(actual_emotion)}"
            )

    expected_steps = [
        f"{item['subflow_id']}#{index}"
        for item in source.get("subflows") or []
        for index, _ in enumerate(item.get("required_sequence") or [], 1)
    ]
    actual_steps = [
        source_id
        for node in target_nodes
        for source_id in normalize_source_refs(node.get("source_refs"))["subflow_steps"]
    ]
    step_positions = {source_id: index for index, source_id in enumerate(expected_steps)}
    unknown_steps = [source_id for source_id in actual_steps if source_id not in step_positions]
    missing_steps = [source_id for source_id in expected_steps if source_id not in actual_steps]
    actual_step_positions = [
        step_positions[source_id] for source_id in actual_steps if source_id in step_positions
    ]
    if unknown_steps:
        errors.append(f"细纲引用未知 SF 步骤: {unknown_steps}")
    if partial:
        unique_steps = list(dict.fromkeys(actual_steps))
        if unique_steps != expected_steps[: len(unique_steps)]:
            errors.append(
                "细纲批次 SF 步骤必须是来源账连续前缀: "
                f"expected_prefix={expected_steps[:len(unique_steps)]}, actual={unique_steps}"
            )
        if actual_step_positions != sorted(actual_step_positions):
            errors.append(
                "细纲批次 SF 步骤重复承接只能保持来源原序: "
                f"actual={actual_steps}"
            )
    elif missing_steps:
        errors.append(f"细纲漏掉 SF 步骤: {missing_steps}")
    if actual_step_positions != sorted(actual_step_positions):
        first = next(
            (
                (actual_steps[index - 1], actual_steps[index])
                for index in range(1, len(actual_step_positions))
                if actual_step_positions[index] < actual_step_positions[index - 1]
            ),
            ("未知", "未知"),
        )
        errors.append(f"细纲 SF 步骤声明发生倒序: {first[0]} -> {first[1]}")

    expected_layers = [str(item["layer_id"]) for item in source.get("layers") or []]
    actual_layers = [
        source_id
        for node in target_nodes
        for source_id in normalize_source_refs(node.get("source_refs"))["layer_ids"]
    ]
    layer_positions = {source_id: index for index, source_id in enumerate(expected_layers)}
    unknown_layers = [
        source_id for source_id in actual_layers if source_id not in layer_positions
    ]
    missing_layers = [source_id for source_id in expected_layers if source_id not in actual_layers]
    actual_layer_positions = [
        layer_positions[source_id]
        for source_id in actual_layers
        if source_id in layer_positions
    ]
    if unknown_layers:
        errors.append(f"细纲引用未知来源层: {unknown_layers}")
    if partial:
        unique_layers = list(dict.fromkeys(actual_layers))
        if unique_layers != expected_layers[: len(unique_layers)]:
            errors.append(
                "细纲批次来源层必须覆盖来源账连续前缀: "
                f"expected_prefix={expected_layers[:len(unique_layers)]}, actual={unique_layers}"
            )
    elif missing_layers:
        errors.append(f"细纲漏掉来源层: {missing_layers}")
    if actual_layer_positions != sorted(actual_layer_positions):
        first = next(
            (
                (actual_layers[index - 1], actual_layers[index])
                for index in range(1, len(actual_layer_positions))
                if actual_layer_positions[index] < actual_layer_positions[index - 1]
            ),
            ("未知", "未知"),
        )
        errors.append(f"细纲来源层声明发生倒序: {first[0]} -> {first[1]}")
    return errors


def explicit_source_ref_mappings(
    target_nodes: list[dict[str, Any]], source: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    errors = validate_explicit_source_refs(target_nodes, source)
    if errors:
        raise ValueError("细纲全颗粒预检失败: " + " / ".join(errors))
    plot_targets: dict[str, str] = {}
    emotion_targets: dict[str, str] = {}
    step_targets: dict[str, list[str]] = {}
    layer_targets: dict[str, list[str]] = {}
    for node in target_nodes:
        target_id = str(node["target_id"])
        refs = normalize_source_refs(node.get("source_refs"))
        for source_id in refs["plot_beat_ids"]:
            plot_targets[source_id] = target_id
        for source_id in refs["emotion_beat_ids"]:
            emotion_targets[source_id] = target_id
        for source_id in refs["subflow_steps"]:
            step_targets.setdefault(source_id, []).append(target_id)
        for source_id in refs["layer_ids"]:
            layer_targets.setdefault(source_id, []).append(target_id)
    return {
        "plot_beats": [
            {
                "source_id": item["beat_id"],
                "source_content_sha256": item["content_sha256"],
                "target_id": plot_targets[item["beat_id"]],
            }
            for item in source.get("plot_beats") or []
        ],
        "emotion_beats": [
            {
                "source_id": item["beat_id"],
                "source_content_sha256": item["content_sha256"],
                "target_id": emotion_targets[item["beat_id"]],
            }
            for item in source.get("emotion_beats") or []
        ],
        "subflows": [
            {
                "source_id": item["subflow_id"],
                "source_content_sha256": item["content_sha256"],
                "performance_chain": [
                    {
                        "step_index": index,
                        "target_node_ids": step_targets[f"{item['subflow_id']}#{index}"],
                    }
                    for index, _ in enumerate(item.get("required_sequence") or [], 1)
                ],
            }
            for item in source.get("subflows") or []
        ],
        "layers": [
            {
                "source_id": item["layer_id"],
                "source_content_sha256": item["content_sha256"],
                "target_node_ids": layer_targets[item["layer_id"]],
            }
            for item in source.get("layers") or []
        ],
    }


def _target_node_hashes(
    target_ids: list[str], target_nodes: dict[str, dict[str, Any]]
) -> list[str]:
    return [str(target_nodes[target_id]["content_sha256"]) for target_id in target_ids]


def _empty_emotion_fidelity(
    item: dict[str, Any], target_id: str, target_nodes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "source_id": item["beat_id"],
        "source_content_sha256": item["content_sha256"],
        "target_id": target_id,
        "target_node_content_sha256": target_nodes[target_id]["content_sha256"],
        "whole_beat_in_one_node": None,
        "field_reviews": {
            field: {"preserved": None, "target_realization": ""}
            for field in EMOTION_FIDELITY_FIELDS
        },
        "human_confirmed": False,
    }


def _empty_layer_fidelity(
    item: dict[str, Any], target_ids: list[str], target_nodes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    dimension_realization = item.get("dimension_realization") or {}
    return {
        "source_id": item["layer_id"],
        "source_content_sha256": item["content_sha256"],
        "source_range_read": None,
        "source_anchor_quotes": [],
        "target_node_ids": list(target_ids),
        "target_node_content_sha256s": _target_node_hashes(target_ids, target_nodes),
        "no_function_shift": None,
        "topology_reviews": {
            field: {"preserved": None, "target_realization": ""}
            for field in LAYER_TOPOLOGY_FIELDS
        },
        "preserve_rule_reviews": [
            {
                "rule_index": index,
                "preserved": None,
                "target_node_ids": [],
                "target_realization": "",
            }
            for index, _ in enumerate(item.get("must_preserve_in_target") or [], 1)
        ],
        "dimension_reviews": {
            field: {
                "source_status": str((dimension_realization.get(field) or {}).get("status") or ""),
                "preserved": None,
                "target_node_ids": [],
                "target_realization": "",
            }
            for field in SOURCE_MAP_VALIDATOR.DIMENSION_FIELDS
        },
        "human_confirmed": False,
    }


def empty_fidelity_reviews(
    source: dict[str, Any],
    mappings: dict[str, list[dict[str, Any]]],
    nodes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    node_by_id = {str(item["target_id"]): item for item in nodes}
    emotion_targets = {
        str(item["source_id"]): str(item["target_id"])
        for item in mappings["emotion_beats"]
    }
    layer_targets = {
        str(item["source_id"]): [str(value) for value in item["target_node_ids"]]
        for item in mappings["layers"]
    }
    emotions = [
        _empty_emotion_fidelity(item, emotion_targets[item["beat_id"]], node_by_id)
        for item in source.get("emotion_beats") or []
    ]
    layers = [
        _empty_layer_fidelity(item, layer_targets[item["layer_id"]], node_by_id)
        for item in source.get("layers") or []
    ]
    return emotions, layers


def create_target_map(
    project_dir: Path,
    source_path: Path,
    source: dict[str, Any],
    target_input: dict[str, str],
    target_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    config_path = project_dir / "写作资产" / "项目写作配置.json"
    config = read_object(config_path, "项目写作配置")
    mappings = explicit_source_ref_mappings(target_nodes, source)
    emotion_fidelity, layer_fidelity = empty_fidelity_reviews(
        source, mappings, target_nodes
    )
    payload: dict[str, Any] = {
        "schema_version": TARGET_SCHEMA,
        "project": project_dir.name,
        "source_map": {
            **binding(source_path),
            "content_sha256": source["content_sha256"],
        },
        "project_config": binding(config_path),
        "target_input": target_input,
        "target_nodes": target_nodes,
        "mappings": mappings,
        "event_shell_replacements": [
            _empty_replacement(item) for item in source["plot_beats"]
        ],
        "emotion_fidelity_reviews": emotion_fidelity,
        "layer_fidelity_reviews": layer_fidelity,
        "manual_confirmation": {
            "mapping_complete": True,
            "event_shell_replacements_confirmed": False,
            "emotion_fidelity_confirmed": False,
            "layer_fidelity_confirmed": False,
            "note": "P/E/SF/来源层映射已由细纲 source-map 声明确认并确定性派生。",
        },
        "incremental_state": {"invalidated": []},
        "gate_status": "pending",
    }
    payload["content_sha256"] = content_hash(payload)
    if config.get("project_name") != project_dir.name:
        raise ValueError("项目写作配置 project_name 必须与项目目录名一致")
    return payload


def _current_binding_errors(value: Any, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} binding 必须是对象"]
    path = Path(str(value.get("path") or "")).expanduser()
    if not path.is_file():
        return [f"{label}文件不存在: {path}"]
    if value.get("sha256") != file_sha256(path):
        return [f"{label} SHA 已失效"]
    return []


def _validate_mapping_collection(
    mappings: Any,
    sources: list[dict[str, Any]],
    source_key: str,
    target_ids: set[str],
    collection_label: str,
    target_fields: tuple[str, ...],
) -> list[str]:
    if not isinstance(mappings, list):
        return [f"mappings.{collection_label} 必须是数组"]
    expected = [item[source_key] for item in sources]
    actual = [item.get("source_id") for item in mappings if isinstance(item, dict)]
    errors: list[str] = []
    if actual != expected:
        errors.append(f"mappings.{collection_label} 必须与来源脑图同序全量对应")
        return errors
    source_by_id = {item[source_key]: item for item in sources}
    for item in mappings:
        source_id = item["source_id"]
        if item.get("source_content_sha256") != source_by_id[source_id].get("content_sha256"):
            errors.append(f"{source_id} 来源内容哈希已失效，必须增量重绑")
        for field in target_fields:
            raw = item.get(field)
            values = raw if isinstance(raw, list) else [raw]
            if not values or any(not isinstance(value, str) or not value for value in values):
                errors.append(f"{source_id}.{field} 尚未完整绑定")
            else:
                unknown = [value for value in values if value not in target_ids]
                if unknown:
                    errors.append(f"{source_id}.{field} 引用未知目标节点: {unknown}")
    return errors


def _validate_fidelity_detail(
    value: Any, label: str, errors: list[str]
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return
    if value.get("preserved") is not True:
        errors.append(f"{label}.preserved 尚未人工确认 true")
    if len(str(value.get("target_realization") or "").strip()) < 8:
        errors.append(f"{label}.target_realization 必须写本节点具体实现")


def _validate_fidelity_target_ids(
    value: Any,
    allowed: list[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}.target_node_ids 必须是非空数组")
        return
    normalized = [str(item) for item in value]
    if len(normalized) != len(set(normalized)):
        errors.append(f"{label}.target_node_ids 不得重复")
    unknown = [item for item in normalized if item not in allowed]
    if unknown:
        errors.append(f"{label}.target_node_ids 越出本层绑定: {unknown}")
    positions = [allowed.index(item) for item in normalized if item in allowed]
    if positions != sorted(positions):
        errors.append(f"{label}.target_node_ids 必须保持本层目标顺序")


def _source_original_lines(source: dict[str, Any]) -> list[str]:
    original = ((source.get("compiled_from") or {}).get("original") or {})
    path = Path(str(original.get("path") or "")).expanduser()
    if not path.is_file():
        raise ValueError(f"来源脑图绑定的原文不存在: {path}")
    return path.read_text(encoding="utf-8").splitlines()


def _validate_layer_source_anchors(
    review: Any,
    source_item: dict[str, Any],
    source_lines: list[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(review, dict):
        errors.append(f"{label} 必须是对象")
        return
    if review.get("source_range_read") is not True:
        errors.append(f"{label}.source_range_read 必须显式确认 true")
    quotes = review.get("source_anchor_quotes")
    if (
        not isinstance(quotes, list)
        or not quotes
        or len(quotes) > 3
        or any(not isinstance(value, str) for value in quotes)
    ):
        errors.append(f"{label}.source_anchor_quotes 必须包含 1-3 条原文短引句")
        return
    normalized = [value.strip() for value in quotes]
    if len(normalized) != len(set(normalized)):
        errors.append(f"{label}.source_anchor_quotes 不得重复")
    source_range = source_item.get("source_range") or {}
    start = source_range.get("start_line")
    end = source_range.get("end_line")
    if not isinstance(start, int) or not isinstance(end, int) or not (1 <= start <= end <= len(source_lines)):
        errors.append(f"{label} 来源行域非法")
        return
    allowed_text = "\n".join(source_lines[start - 1 : end])
    for index, (raw, quote) in enumerate(zip(quotes, normalized), 1):
        quote_label = f"{label}.source_anchor_quotes[{index}]"
        if raw != quote or "\n" in quote or not (2 <= len(quote) <= 48):
            errors.append(f"{quote_label} 必须是 2-48 字的单行原文短引句")
        elif quote not in allowed_text:
            errors.append(f"{quote_label} 不在对应来源层原文行域内")


def validate_prewrite_fidelity(
    payload: dict[str, Any],
    source: dict[str, Any],
    nodes: list[dict[str, Any]],
    mappings: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        source_lines = _source_original_lines(source)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        source_lines = []
    node_by_id = {str(item["target_id"]): item for item in nodes}
    emotion_sources = {item["beat_id"]: item for item in source.get("emotion_beats") or []}
    emotion_targets = {
        str(item["source_id"]): str(item["target_id"])
        for item in mappings.get("emotion_beats") or []
        if isinstance(item, dict)
    }
    emotion_reviews = payload.get("emotion_fidelity_reviews")
    expected_emotions = list(emotion_sources)
    if not isinstance(emotion_reviews, list) or [
        item.get("source_id") for item in emotion_reviews if isinstance(item, dict)
    ] != expected_emotions:
        errors.append("emotion_fidelity_reviews 必须与来源 E 拍同序全量对应")
    else:
        for review in emotion_reviews:
            source_id = str(review["source_id"])
            source_item = emotion_sources[source_id]
            target_id = emotion_targets.get(source_id, "")
            if review.get("source_content_sha256") != source_item.get("content_sha256"):
                errors.append(f"{source_id} 写前 E 拍来源哈希已失效")
            if review.get("target_id") != target_id:
                errors.append(f"{source_id} 写前 E 拍目标节点与映射不一致")
            if target_id in node_by_id and review.get("target_node_content_sha256") != node_by_id[target_id].get("content_sha256"):
                errors.append(f"{source_id} 写前 E 拍目标节点内容已变化")
            if review.get("whole_beat_in_one_node") is not True:
                errors.append(f"{source_id} 必须确认整拍未拆散或顺移")
            field_reviews = review.get("field_reviews")
            if not isinstance(field_reviews, dict) or set(field_reviews) != set(EMOTION_FIDELITY_FIELDS):
                errors.append(f"{source_id}.field_reviews 必须逐项覆盖 E 拍五字段")
            else:
                for field in EMOTION_FIDELITY_FIELDS:
                    _validate_fidelity_detail(
                        field_reviews.get(field), f"{source_id}.field_reviews.{field}", errors
                    )
            if review.get("human_confirmed") is not True:
                errors.append(f"{source_id} 写前 E 拍语义保真尚未人工确认")

    layer_sources = {item["layer_id"]: item for item in source.get("layers") or []}
    layer_targets = {
        str(item["source_id"]): [str(value) for value in item["target_node_ids"]]
        for item in mappings.get("layers") or []
        if isinstance(item, dict)
    }
    layer_reviews = payload.get("layer_fidelity_reviews")
    expected_layers = list(layer_sources)
    if not isinstance(layer_reviews, list) or [
        item.get("source_id") for item in layer_reviews if isinstance(item, dict)
    ] != expected_layers:
        errors.append("layer_fidelity_reviews 必须与来源文字层同序全量对应")
    else:
        for review in layer_reviews:
            source_id = str(review["source_id"])
            source_item = layer_sources[source_id]
            _validate_layer_source_anchors(
                review, source_item, source_lines, source_id, errors
            )
            target_ids = layer_targets.get(source_id, [])
            if review.get("source_content_sha256") != source_item.get("content_sha256"):
                errors.append(f"{source_id} 写前文字层来源哈希已失效")
            if review.get("target_node_ids") != target_ids:
                errors.append(f"{source_id} 写前文字层目标节点与映射不一致")
            expected_hashes = [
                node_by_id[target_id]["content_sha256"]
                for target_id in target_ids
                if target_id in node_by_id
            ]
            if review.get("target_node_content_sha256s") != expected_hashes:
                errors.append(f"{source_id} 写前文字层目标节点内容已变化")
            if review.get("no_function_shift") is not True:
                errors.append(f"{source_id} 必须确认无跨层功能顺移")
            topology = review.get("topology_reviews")
            if not isinstance(topology, dict) or set(topology) != set(LAYER_TOPOLOGY_FIELDS):
                errors.append(f"{source_id}.topology_reviews 必须逐项覆盖层型与进出关系")
            else:
                for field in LAYER_TOPOLOGY_FIELDS:
                    _validate_fidelity_detail(
                        topology.get(field), f"{source_id}.topology_reviews.{field}", errors
                    )
            rule_reviews = review.get("preserve_rule_reviews")
            source_rules = source_item.get("must_preserve_in_target") or []
            if not isinstance(rule_reviews, list) or [
                item.get("rule_index") for item in rule_reviews if isinstance(item, dict)
            ] != list(range(1, len(source_rules) + 1)):
                errors.append(f"{source_id}.preserve_rule_reviews 必须逐条覆盖来源保留规则")
            else:
                for item in rule_reviews:
                    label = f"{source_id}.preserve_rule_reviews[{item['rule_index']}]"
                    if item.get("preserved") is not True:
                        errors.append(f"{label}.preserved 尚未人工确认 true")
                    _validate_fidelity_target_ids(item.get("target_node_ids"), target_ids, label, errors)
                    if len(str(item.get("target_realization") or "").strip()) < 8:
                        errors.append(f"{label}.target_realization 必须写具体承载")
            dimension_reviews = review.get("dimension_reviews")
            expected_dimensions = list(SOURCE_MAP_VALIDATOR.DIMENSION_FIELDS)
            if not isinstance(dimension_reviews, dict) or set(dimension_reviews) != set(expected_dimensions):
                errors.append(f"{source_id}.dimension_reviews 必须逐项覆盖来源六维")
            else:
                source_dimensions = source_item.get("dimension_realization") or {}
                for field in expected_dimensions:
                    detail = dimension_reviews.get(field)
                    label = f"{source_id}.dimension_reviews.{field}"
                    if not isinstance(detail, dict):
                        errors.append(f"{label} 必须是对象")
                        continue
                    expected_status = str((source_dimensions.get(field) or {}).get("status") or "")
                    if detail.get("source_status") != expected_status:
                        errors.append(f"{label}.source_status 与来源层不一致")
                    if detail.get("preserved") is not True:
                        errors.append(f"{label}.preserved 尚未人工确认 true")
                    _validate_fidelity_target_ids(detail.get("target_node_ids"), target_ids, label, errors)
                    if len(str(detail.get("target_realization") or "").strip()) < 8:
                        errors.append(f"{label}.target_realization 必须写具体协同或缺席方式")
            if review.get("human_confirmed") is not True:
                errors.append(f"{source_id} 写前文字层保真尚未人工确认")
    return errors


def validate_target_map(
    payload: dict[str, Any], require_gate: bool = True
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != TARGET_SCHEMA:
        errors.append(f"schema_version 必须为 {TARGET_SCHEMA}")
    if payload.get("content_sha256") != content_hash(payload):
        errors.append("目标成文脑图 content_sha256 与内容不一致")
    errors.extend(_current_binding_errors(payload.get("source_map"), "来源成文脑图"))
    errors.extend(_current_binding_errors(payload.get("project_config"), "项目写作配置"))
    errors.extend(_current_binding_errors(payload.get("target_input"), "目标输入"))
    source_map_value = payload.get("source_map") or {}
    try:
        source = read_object(Path(str(source_map_value.get("path") or "")), "来源成文脑图")
    except (OSError, ValueError, FileNotFoundError) as exc:
        return errors + [str(exc)]
    source_errors = SOURCE_MAP_VALIDATOR.validate_source_map(
        source, Path(str(source_map_value.get("path") or ""))
    )
    if source_errors:
        return errors + [f"来源成文脑图未通过校验: {item}" for item in source_errors]
    if source_map_value.get("content_sha256") != source.get("content_sha256"):
        errors.append("来源成文脑图内容版本已变化，必须增量重绑")
    nodes = payload.get("target_nodes")
    if not isinstance(nodes, list) or not nodes:
        return errors + ["target_nodes 必须是非空数组"]
    target_ids = [item.get("target_id") for item in nodes if isinstance(item, dict)]
    if len(target_ids) != len(nodes) or any(not item for item in target_ids):
        errors.append("target_nodes 存在空或非法目标节点")
    if len(target_ids) != len(set(target_ids)):
        errors.append("target_nodes.target_id 必须唯一")
    if [item.get("sequence_index") for item in nodes if isinstance(item, dict)] != list(
        range(1, len(nodes) + 1)
    ):
        errors.append("target_nodes.sequence_index 必须从 1 连续递增")
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("content_sha256") != canonical_sha256(
            {key: value for key, value in node.items() if key != "content_sha256"}
        ):
            errors.append(f"目标节点 {node.get('target_id')} 内容哈希不一致")
    target_set = {str(item) for item in target_ids if item}
    target_positions = {
        str(item["target_id"]): int(item["sequence_index"])
        for item in nodes
        if isinstance(item, dict) and item.get("target_id") and isinstance(item.get("sequence_index"), int)
    }
    mappings = payload.get("mappings")
    if not isinstance(mappings, dict):
        return errors + ["目标成文脑图缺少 mappings"]
    source_ref_errors = validate_explicit_source_refs(nodes, source)
    errors.extend(source_ref_errors)
    if not source_ref_errors:
        expected_mappings = explicit_source_ref_mappings(nodes, source)
        if mappings != expected_mappings:
            errors.append(
                "目标映射必须完全由细纲 source-map 声明派生；"
                "禁止在目标脑图中维护另一套 P/E/SF/层绑定"
            )
    errors.extend(
        _validate_mapping_collection(
            mappings.get("plot_beats"),
            source.get("plot_beats") or [],
            "beat_id",
            target_set,
            "plot_beats",
            ("target_id",),
        )
    )
    errors.extend(validate_prewrite_fidelity(payload, source, nodes, mappings))
    for label in ("plot_beats", "emotion_beats"):
        items = mappings.get(label)
        if not isinstance(items, list):
            continue
        bound = [item.get("target_id") for item in items if isinstance(item, dict)]
        if all(value in target_positions for value in bound):
            positions = [target_positions[value] for value in bound]
            if positions != sorted(positions) or len(positions) != len(set(positions)):
                errors.append(f"mappings.{label} 必须保持来源原序且一对一绑定目标节点")
    errors.extend(
        _validate_mapping_collection(
            mappings.get("emotion_beats"),
            source.get("emotion_beats") or [],
            "beat_id",
            target_set,
            "emotion_beats",
            ("target_id",),
        )
    )
    errors.extend(
        _validate_mapping_collection(
            mappings.get("layers"),
            source.get("layers") or [],
            "layer_id",
            target_set,
            "layers",
            ("target_node_ids",),
        )
    )
    subflow_mappings = mappings.get("subflows")
    errors.extend(
        _validate_mapping_collection(
            subflow_mappings,
            source.get("subflows") or [],
            "subflow_id",
            target_set,
            "subflows",
            (),
        )
    )
    if isinstance(subflow_mappings, list):
        source_by_id = {item["subflow_id"]: item for item in source.get("subflows") or []}
        for item in subflow_mappings:
            if not isinstance(item, dict) or item.get("source_id") not in source_by_id:
                continue
            required = source_by_id[item["source_id"]].get("required_sequence") or []
            chain = item.get("performance_chain")
            if not isinstance(chain, list) or len(chain) != len(required):
                errors.append(f"{item['source_id']} performance_chain 长度与来源 SF 不一致")
                continue
            for index, step in enumerate(chain, 1):
                if not isinstance(step, dict) or step.get("step_index") != index:
                    errors.append(f"{item['source_id']} performance_chain 序号不连续")
                    break
                target_node_ids = step.get("target_node_ids")
                if (
                    not isinstance(target_node_ids, list)
                    or not target_node_ids
                    or any(value not in target_set for value in target_node_ids)
                ):
                    errors.append(f"{item['source_id']} 第 {index} 个表演步尚未完整绑定")
                    continue
                positions = [target_positions[value] for value in target_node_ids]
                if positions != sorted(set(positions)):
                    errors.append(f"{item['source_id']} 第 {index} 个表演步目标节点必须同序唯一")
            valid_steps = [
                [target_positions[value] for value in step.get("target_node_ids") or []]
                for step in chain
                if isinstance(step, dict)
                and step.get("target_node_ids")
                and all(value in target_positions for value in step["target_node_ids"])
            ]
            if len(valid_steps) == len(chain) and any(
                min(current) < max(previous)
                for previous, current in zip(valid_steps, valid_steps[1:])
            ):
                errors.append(f"{item['source_id']} performance_chain 发生倒序")
    layer_items = mappings.get("layers")
    if isinstance(layer_items, list):
        valid_layers: list[list[int]] = []
        for item in layer_items:
            values = item.get("target_node_ids") if isinstance(item, dict) else None
            if not isinstance(values, list) or not values or any(value not in target_positions for value in values):
                continue
            positions = [target_positions[value] for value in values]
            if positions != sorted(set(positions)):
                errors.append(f"{item['source_id']} 目标层节点必须同序唯一")
            valid_layers.append(positions)
        if len(valid_layers) == len(layer_items) and any(
            min(current) < max(previous)
            for previous, current in zip(valid_layers, valid_layers[1:])
        ):
            errors.append("mappings.layers 发生来源层倒序")
    replacements = payload.get("event_shell_replacements")
    plot_sources = source.get("plot_beats") or []
    if not isinstance(replacements, list) or [
        item.get("source_id") for item in replacements if isinstance(item, dict)
    ] != [item.get("beat_id") for item in plot_sources]:
        errors.append("event_shell_replacements 必须与来源 P 拍同序全量对应")
    else:
        source_hashes = {item["beat_id"]: item["content_sha256"] for item in plot_sources}
        for item in replacements:
            source_id = item["source_id"]
            if item.get("source_content_sha256") != source_hashes[source_id]:
                errors.append(f"{source_id} 换壳判断来源哈希已失效")
            dimensions = item.get("dimensions_changed")
            if not isinstance(dimensions, list) or len(set(dimensions)) < 3:
                errors.append(f"{source_id} 至少确认三个换壳维度")
            elif set(dimensions) - REPLACEMENT_DIMENSIONS:
                errors.append(f"{source_id} 包含未知换壳维度")
            function_reviews = item.get("function_reviews")
            if (
                not isinstance(function_reviews, dict)
                or set(function_reviews) != set(PLOT_AUDIT_FIELDS)
            ):
                errors.append(f"{source_id}.function_reviews 必须逐项覆盖 P 拍四字段")
            else:
                conclusions = [
                    str(function_reviews.get(field) or "").strip()
                    for field in PLOT_AUDIT_FIELDS
                ]
                if any(len(value) < 8 for value in conclusions):
                    errors.append(f"{source_id}.function_reviews 必须写四项专属目标实现")
                if len(set(conclusions)) != len(conclusions):
                    errors.append(f"{source_id}.function_reviews 四项不得套用同一结论")
            if len(str(item.get("adaptation_decision") or "").strip()) < 12:
                errors.append(f"{source_id} 缺少人工改编判断")
            if item.get("human_confirmed") is not True:
                errors.append(f"{source_id} 换壳判断尚未人工确认")
    confirmation = payload.get("manual_confirmation")
    if not isinstance(confirmation, dict):
        errors.append("目标成文脑图缺少 manual_confirmation")
    else:
        if confirmation.get("mapping_complete") is not True:
            errors.append("manual_confirmation.mapping_complete 尚未确认")
        if confirmation.get("event_shell_replacements_confirmed") is not True:
            errors.append("manual_confirmation.event_shell_replacements_confirmed 尚未确认")
        if confirmation.get("emotion_fidelity_confirmed") is not True:
            errors.append("manual_confirmation.emotion_fidelity_confirmed 尚未确认")
        if confirmation.get("layer_fidelity_confirmed") is not True:
            errors.append("manual_confirmation.layer_fidelity_confirmed 尚未确认")
        if len(str(confirmation.get("note") or "").strip()) < 8:
            errors.append("manual_confirmation.note 必须记录本书专属人工判断")
    if payload.get("incremental_state", {}).get("invalidated"):
        errors.append("incremental_state.invalidated 尚有未重绑项目")
    if require_gate and payload.get("gate_status") != "passed":
        errors.append("目标成文脑图 gate_status 未 passed")
    return errors


def _remap_target_id(
    old_id: str,
    old_nodes: dict[str, dict[str, Any]],
    new_nodes: dict[str, dict[str, Any]],
    evidence_to_ids: dict[str, list[str]],
) -> str:
    if not old_id:
        return ""
    old = old_nodes.get(old_id)
    current = new_nodes.get(old_id)
    if old and current and old.get("evidence") == current.get("evidence"):
        return old_id
    if not old:
        return ""
    matches = evidence_to_ids.get(str(old.get("evidence") or ""), [])
    return matches[0] if len(matches) == 1 else ""


def rebind_target_map(
    payload: dict[str, Any],
    source_path: Path,
    source: dict[str, Any],
    target_input: dict[str, str],
    target_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    schema_changed = payload.get("schema_version") != TARGET_SCHEMA
    old_nodes = {
        item["target_id"]: item
        for item in payload.get("target_nodes") or []
        if isinstance(item, dict) and item.get("target_id")
    }
    new_nodes = {item["target_id"]: item for item in target_nodes}
    evidence_to_ids: dict[str, list[str]] = {}
    for item in target_nodes:
        evidence_to_ids.setdefault(item["evidence"], []).append(item["target_id"])

    def remap_id(value: str) -> str:
        return _remap_target_id(value, old_nodes, new_nodes, evidence_to_ids)

    invalidated: list[str] = []

    def merge(
        old_items: Any,
        source_items: list[dict[str, Any]],
        source_key: str,
        empty_factory: Callable[[dict[str, Any]], dict[str, Any]],
        remap_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        old_by_id = {
            item.get("source_id"): item
            for item in old_items or []
            if isinstance(item, dict) and item.get("source_id")
        }
        result: list[dict[str, Any]] = []
        for source_item in source_items:
            source_id = source_item[source_key]
            old = old_by_id.get(source_id)
            if not old or old.get("source_content_sha256") != source_item.get("content_sha256"):
                result.append(empty_factory(source_item))
                invalidated.append(source_id)
                continue
            current = dict(old)
            current["source_content_sha256"] = source_item["content_sha256"]
            for field in remap_fields:
                raw = current.get(field)
                if isinstance(raw, list):
                    rebound = [remap_id(value) for value in raw]
                    current[field] = [value for value in rebound if value]
                    if len(current[field]) != len(raw):
                        invalidated.append(f"{source_id}.{field}")
                else:
                    rebound = remap_id(str(raw or ""))
                    if raw and not rebound:
                        invalidated.append(f"{source_id}.{field}")
                    current[field] = rebound
            result.append(current)
        return result

    mappings = payload.get("mappings") or {}
    plot = merge(
        mappings.get("plot_beats"), source.get("plot_beats") or [], "beat_id", _empty_plot_mapping, ("target_id",)
    )
    emotion = merge(
        mappings.get("emotion_beats"), source.get("emotion_beats") or [], "beat_id", _empty_emotion_mapping, ("target_id",)
    )
    layers = merge(
        mappings.get("layers"), source.get("layers") or [], "layer_id", _empty_layer_mapping, ("target_node_ids",)
    )
    subflows = merge(
        mappings.get("subflows"), source.get("subflows") or [], "subflow_id", _empty_subflow_mapping, ()
    )
    sf_source = {item["subflow_id"]: item for item in source.get("subflows") or []}
    for item in subflows:
        expected_steps = len(sf_source[item["source_id"]].get("required_sequence") or [])
        chain = item.get("performance_chain")
        if not isinstance(chain, list) or len(chain) != expected_steps:
            item["performance_chain"] = _empty_subflow_mapping(sf_source[item["source_id"]])["performance_chain"]
            invalidated.append(f"{item['source_id']}.performance_chain")
            continue
        for step in chain:
            old_ids = step.get("target_node_ids") or []
            rebound = [remap_id(str(value)) for value in old_ids]
            step["target_node_ids"] = [value for value in rebound if value]
            if len(step["target_node_ids"]) != len(old_ids):
                invalidated.append(f"{item['source_id']}.performance_chain.{step.get('step_index')}")

    replacements = merge(
        payload.get("event_shell_replacements"),
        source.get("plot_beats") or [],
        "beat_id",
        _empty_replacement,
        (),
    )
    if schema_changed:
        replacements = [
            _empty_replacement(item) for item in source.get("plot_beats") or []
        ]
        invalidated.extend(
            f"{item['beat_id']}.event_shell_replacement"
            for item in source.get("plot_beats") or []
        )
    explicit_mappings = explicit_source_ref_mappings(target_nodes, source)
    empty_emotion_reviews, empty_layer_reviews = empty_fidelity_reviews(
        source, explicit_mappings, target_nodes
    )

    def preserve_fidelity(
        empty_reviews: list[dict[str, Any]],
        old_reviews: Any,
        identity_fields: tuple[str, ...],
        invalidation_suffix: str,
    ) -> list[dict[str, Any]]:
        old_by_id = {
            str(item.get("source_id") or ""): item
            for item in old_reviews or []
            if isinstance(item, dict)
        }
        result = []
        for empty in empty_reviews:
            source_id = str(empty["source_id"])
            old = old_by_id.get(source_id)
            if (
                not schema_changed
                and old
                and all(old.get(field) == empty.get(field) for field in identity_fields)
            ):
                result.append(old)
            else:
                result.append(empty)
                invalidated.append(f"{source_id}.{invalidation_suffix}")
        return result

    emotion_fidelity = preserve_fidelity(
        empty_emotion_reviews,
        payload.get("emotion_fidelity_reviews"),
        (
            "source_content_sha256",
            "target_id",
            "target_node_content_sha256",
        ),
        "emotion_fidelity",
    )
    layer_fidelity = preserve_fidelity(
        empty_layer_reviews,
        payload.get("layer_fidelity_reviews"),
        (
            "source_content_sha256",
            "target_node_ids",
            "target_node_content_sha256s",
        ),
        "layer_fidelity",
    )
    old_plot_targets = {
        str(item.get("source_id") or ""): str(item.get("target_id") or "")
        for item in mappings.get("plot_beats") or []
        if isinstance(item, dict)
    }
    new_plot_targets = {
        str(item["source_id"]): str(item["target_id"])
        for item in explicit_mappings["plot_beats"]
    }
    old_evidence = {
        str(item.get("target_id") or ""): str(item.get("evidence") or "")
        for item in payload.get("target_nodes") or []
        if isinstance(item, dict)
    }
    new_evidence = {
        str(item.get("target_id") or ""): str(item.get("evidence") or "")
        for item in target_nodes
        if isinstance(item, dict)
    }
    replacement_by_id = {
        str(item.get("source_id") or ""): item
        for item in replacements
        if isinstance(item, dict)
    }
    for source_id, new_target_id in new_plot_targets.items():
        old_target_id = old_plot_targets.get(source_id, "")
        if (
            old_target_id != new_target_id
            or old_evidence.get(old_target_id, "") != new_evidence.get(new_target_id, "")
        ):
            source_item = next(
                item for item in source.get("plot_beats") or [] if item["beat_id"] == source_id
            )
            replacement_by_id[source_id].update(_empty_replacement(source_item))
            invalidated.append(f"{source_id}.event_shell_replacement")
    payload["schema_version"] = TARGET_SCHEMA
    payload["source_map"] = {
        **binding(source_path),
        "content_sha256": source["content_sha256"],
    }
    # Rebind the project config itself when upstream policy fields change.
    # Without this refresh, a valid config edit leaves the target map blocked
    # by a stale project_config SHA even though all semantic mappings survived.
    config_path = Path(str((payload.get("project_config") or {}).get("path") or ""))
    if config_path.is_file():
        payload["project_config"] = binding(config_path)
    payload["target_input"] = target_input
    payload["target_nodes"] = target_nodes
    payload["mappings"] = explicit_mappings
    payload["event_shell_replacements"] = replacements
    payload["emotion_fidelity_reviews"] = emotion_fidelity
    payload["layer_fidelity_reviews"] = layer_fidelity
    plot_source_ids = {
        str(item["beat_id"]) for item in source.get("plot_beats") or []
    }
    event_shell_invalidations = {
        str(item)
        for item in invalidated
        if str(item).endswith(".event_shell_replacement")
    }
    event_shell_invalidations.update(
        f"{item}.event_shell_replacement"
        for item in invalidated
        if str(item) in plot_source_ids
    )
    fidelity_invalidations = {
        str(item)
        for item in invalidated
        if str(item).endswith(".emotion_fidelity")
        or str(item).endswith(".layer_fidelity")
    }
    payload["incremental_state"] = {
        "invalidated": sorted(event_shell_invalidations | fidelity_invalidations)
    }
    confirmation = payload.setdefault("manual_confirmation", {})
    confirmation["mapping_complete"] = True
    confirmation["emotion_fidelity_confirmed"] = all(
        item.get("human_confirmed") is True for item in emotion_fidelity
    )
    confirmation["layer_fidelity_confirmed"] = all(
        item.get("human_confirmed") is True for item in layer_fidelity
    )
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    return payload


def _validate_audit_detail(
    value: Any, label: str, allowed_text: str, errors: list[str]
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return
    if value.get("preserved") is not True:
        errors.append(f"{label}.preserved 尚未显式确认 true")
    quotes = value.get("evidence_quotes")
    if not isinstance(quotes, list) or not quotes:
        errors.append(f"{label} 缺少专属正文引句")
    else:
        for quote in quotes:
            if not isinstance(quote, str) or not quote.strip() or quote not in allowed_text:
                errors.append(f"{label} 引句不在绑定正文区域内: {quote!r}")
    if len(str(value.get("conclusion") or "").strip()) < 8:
        errors.append(f"{label}.conclusion 必须写本字段专属判断")


def _validate_audit_field_reviews(
    value: Any,
    fields: tuple[str, ...],
    label: str,
    allowed_text: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict) or set(value) != set(fields):
        errors.append(f"{label} 必须按固定字段逐项提交")
        return
    for field in fields:
        _validate_audit_detail(value.get(field), f"{label}.{field}", allowed_text, errors)


def split_draft_regions(text: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return {"opening": H1_RE.sub("", text, count=1).strip()}
    opening = H1_RE.sub("", text[: matches[0].start()], count=1).strip()
    regions = {"opening": opening}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        regions[f"section:{match.group(1)}"] = text[match.end() : end].strip()
    return regions


def audit_draft_regions(text: str) -> dict[str, str]:
    regions = split_draft_regions(text)
    numeric = [
        (int(region_id.split(":", 1)[1]), region_id)
        for region_id in regions
        if region_id.startswith("section:")
    ]
    if numeric:
        last_region = max(numeric)[1]
        regions["epilogue"] = regions[last_region]
    return regions


def _empty_audit_field_reviews(fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return {
        field: {"preserved": None, "evidence_quotes": [], "conclusion": ""}
        for field in fields
    }


def _all_detail_quotes(details: Any) -> list[str]:
    result: list[str] = []
    values = (
        details.values()
        if isinstance(details, dict)
        else details
        if isinstance(details, list)
        else []
    )
    for detail in values:
        if not isinstance(detail, dict):
            continue
        for quote in detail.get("evidence_quotes") or []:
            if isinstance(quote, str) and quote not in result:
                result.append(quote)
    return result


def create_audit(
    project_dir: Path,
    target_path: Path,
    target: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_errors = validate_target_map(target, require_gate=True)
    if target_errors:
        raise ValueError("目标成文脑图未放行: " + " / ".join(target_errors))
    source_path = Path(target["source_map"]["path"])
    source = read_object(source_path, "来源成文脑图")
    draft_path = project_dir / "正文.md"
    draft_text = draft_path.read_text(encoding="utf-8")
    regions = audit_draft_regions(draft_text)
    node_regions = {
        item["target_id"]: item["region_id"] for item in target["target_nodes"]
    }
    old_reviews = {
        item.get("source_layer_id"): item
        for item in (existing or {}).get("layer_reviews") or []
        if isinstance(item, dict)
    }
    old_node_reviews = {
        item.get("target_node_id"): item
        for item in (existing or {}).get("node_reviews") or []
        if isinstance(item, dict)
    }
    old_plot_reviews = {
        item.get("source_plot_id"): item
        for item in (existing or {}).get("plot_reviews") or []
        if isinstance(item, dict)
    }
    old_emotion_reviews = {
        item.get("source_emotion_id"): item
        for item in (existing or {}).get("emotion_reviews") or []
        if isinstance(item, dict)
    }
    layer_mapping = {
        item["source_id"]: item for item in target["mappings"]["layers"]
    }
    reviews: list[dict[str, Any]] = []
    for layer in source["layers"]:
        layer_id = layer["layer_id"]
        targets = layer_mapping[layer_id]["target_node_ids"]
        target_regions = list(dict.fromkeys(node_regions[item] for item in targets))
        base = {
            "source_layer_id": layer_id,
            "source_content_sha256": layer["content_sha256"],
            "target_node_ids": targets,
            "target_regions": target_regions,
            "realized": None,
            "topology_preserved": None,
            "topology_reviews": _empty_audit_field_reviews(
                LAYER_AUDIT_TOPOLOGY_FIELDS
            ),
            "preserve_rule_reviews": [
                {
                    "rule_index": index,
                    "preserved": None,
                    "evidence_quotes": [],
                    "conclusion": "",
                }
                for index, _ in enumerate(layer.get("must_preserve_in_target") or [], 1)
            ],
            "dimension_reviews": {
                field: {
                    "source_status": str(
                        ((layer.get("dimension_realization") or {}).get(field) or {}).get("status")
                        or ""
                    ),
                    "preserved": None,
                    "evidence_quotes": [],
                    "conclusion": "",
                }
                for field in SOURCE_MAP_VALIDATOR.DIMENSION_FIELDS
            },
            "evidence_quotes": [],
            "conclusion": "",
        }
        old = old_reviews.get(layer_id)
        old_quotes = old.get("evidence_quotes") if isinstance(old, dict) else None
        allowed_text = "\n".join(regions.get(region_id, "") for region_id in target_regions)
        if (
            old
            and old.get("source_content_sha256") == base["source_content_sha256"]
            and old.get("target_node_ids") == targets
            and isinstance(old_quotes, list)
            and bool(old_quotes)
            and all(
                isinstance(quote, str) and quote and quote in allowed_text
                for quote in old_quotes
            )
        ):
            for field in (
                "realized",
                "topology_preserved",
                "topology_reviews",
                "preserve_rule_reviews",
                "dimension_reviews",
                "evidence_quotes",
                "conclusion",
            ):
                base[field] = old.get(field)
        reviews.append(base)
    node_reviews: list[dict[str, Any]] = []
    for node in target["target_nodes"]:
        target_id = node["target_id"]
        region_id = node["region_id"]
        base = {
            "target_node_id": target_id,
            "source_refs": node["source_refs"],
            "target_region": region_id,
            "realized": None,
            "granularity_preserved": None,
            "evidence_quotes": [],
            "conclusion": "",
        }
        old = old_node_reviews.get(target_id)
        allowed_text = regions.get(region_id, "")
        old_quotes = old.get("evidence_quotes") if isinstance(old, dict) else None
        if (
            old
            and old.get("source_refs") == base["source_refs"]
            and old.get("target_region") == region_id
            and isinstance(old_quotes, list)
            and bool(old_quotes)
            and all(
                isinstance(quote, str) and quote and quote in allowed_text
                for quote in old_quotes
            )
        ):
            for field in (
                "realized",
                "granularity_preserved",
                "evidence_quotes",
                "conclusion",
            ):
                base[field] = old.get(field)
        node_reviews.append(base)
    plot_mapping = {
        item["source_id"]: item for item in target["mappings"]["plot_beats"]
    }
    plot_reviews: list[dict[str, Any]] = []
    for beat in source["plot_beats"]:
        beat_id = beat["beat_id"]
        target_id = plot_mapping[beat_id]["target_id"]
        region_id = node_regions[target_id]
        base = {
            "source_plot_id": beat_id,
            "source_content_sha256": beat["content_sha256"],
            "target_node_id": target_id,
            "target_region": region_id,
            "function_preserved": None,
            "action_preserved": None,
            "control_change_preserved": None,
            "information_change_preserved": None,
            "consequence_preserved": None,
            "field_reviews": _empty_audit_field_reviews(PLOT_AUDIT_FIELDS),
            "evidence_quotes": [],
            "conclusion": "",
        }
        old = old_plot_reviews.get(beat_id)
        old_quotes = old.get("evidence_quotes") if isinstance(old, dict) else None
        allowed_text = regions.get(region_id, "")
        if (
            old
            and old.get("source_content_sha256") == base["source_content_sha256"]
            and old.get("target_node_id") == target_id
            and old.get("target_region") == region_id
            and isinstance(old_quotes, list)
            and bool(old_quotes)
            and all(
                isinstance(quote, str) and quote and quote in allowed_text
                for quote in old_quotes
            )
        ):
            for field in (
                "function_preserved",
                "action_preserved",
                "control_change_preserved",
                "information_change_preserved",
                "consequence_preserved",
                "field_reviews",
                "evidence_quotes",
                "conclusion",
            ):
                base[field] = old.get(field)
        plot_reviews.append(base)
    emotion_mapping = {
        item["source_id"]: item for item in target["mappings"]["emotion_beats"]
    }
    emotion_reviews: list[dict[str, Any]] = []
    for beat in source["emotion_beats"]:
        beat_id = beat["beat_id"]
        target_id = emotion_mapping[beat_id]["target_id"]
        region_id = node_regions[target_id]
        base = {
            "source_emotion_id": beat_id,
            "source_content_sha256": beat["content_sha256"],
            "target_node_id": target_id,
            "target_region": region_id,
            "content_preserved": None,
            "trigger_preserved": None,
            "relationship_position_change_preserved": None,
            "reader_effect_preserved": None,
            "intensity_preserved": None,
            "whole_beat_in_one_node": None,
            "field_reviews": _empty_audit_field_reviews(EMOTION_AUDIT_FIELDS),
            "evidence_quotes": [],
            "conclusion": "",
        }
        old = old_emotion_reviews.get(beat_id)
        old_quotes = old.get("evidence_quotes") if isinstance(old, dict) else None
        allowed_text = regions.get(region_id, "")
        if (
            old
            and old.get("source_content_sha256") == base["source_content_sha256"]
            and old.get("target_node_id") == target_id
            and old.get("target_region") == region_id
            and isinstance(old_quotes, list)
            and bool(old_quotes)
            and all(
                isinstance(quote, str) and quote and quote in allowed_text
                for quote in old_quotes
            )
        ):
            for field in (
                "content_preserved",
                "trigger_preserved",
                "relationship_position_change_preserved",
                "reader_effect_preserved",
                "intensity_preserved",
                "whole_beat_in_one_node",
                "field_reviews",
                "evidence_quotes",
                "conclusion",
            ):
                base[field] = old.get(field)
        emotion_reviews.append(base)
    region_coverage = []
    for region_id in regions:
        layer_ids = [
            item["source_layer_id"]
            for item in reviews
            if region_id in item["target_regions"]
        ]
        if layer_ids:
            region_coverage.append(
                {"region_id": region_id, "source_layer_ids": layer_ids}
            )
    payload: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA,
        "project": project_dir.name,
        "bindings": {
            "source_map": binding(source_path),
            "target_map": binding(target_path),
            "draft": binding(draft_path),
        },
        "region_coverage": region_coverage,
        "layer_reviews": reviews,
        "node_reviews": node_reviews,
        "plot_reviews": plot_reviews,
        "emotion_reviews": emotion_reviews,
        "exceptions": list((existing or {}).get("exceptions") or []),
        "gate_status": "pending",
    }
    payload["content_sha256"] = content_hash(payload)
    return payload


def validate_audit(
    payload: dict[str, Any], project_dir: Path, require_gate: bool = True
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != AUDIT_SCHEMA:
        errors.append(f"schema_version 必须为 {AUDIT_SCHEMA}")
    if payload.get("content_sha256") != content_hash(payload):
        errors.append("正文覆盖回执 content_sha256 与内容不一致")
    bindings = payload.get("bindings")
    if not isinstance(bindings, dict):
        return errors + ["正文覆盖回执缺少 bindings"]
    for key, label in (
        ("source_map", "来源成文脑图"),
        ("target_map", "目标成文脑图"),
        ("draft", "正文"),
    ):
        errors.extend(_current_binding_errors(bindings.get(key), label))
    try:
        source = read_object(Path(bindings["source_map"]["path"]), "来源成文脑图")
        target = read_object(Path(bindings["target_map"]["path"]), "目标成文脑图")
        draft_text = (project_dir / "正文.md").read_text(encoding="utf-8")
    except (OSError, ValueError, FileNotFoundError, KeyError) as exc:
        return errors + [str(exc)]
    target_errors = validate_target_map(target, require_gate=True)
    errors.extend(target_errors)
    if target_errors:
        return errors
    regions = audit_draft_regions(draft_text)
    if payload.get("audit_mode") == "compact_v1":
        errors.extend(
            validate_compact_audit_payload(
                payload, project_dir, source, target, draft_text, regions
            )
        )
        if require_gate and payload.get("gate_status") != "passed":
            errors.append("正文覆盖回执 gate_status 未 passed")
        return errors
    source_layers = {item["layer_id"]: item for item in source.get("layers") or []}
    layer_mapping = {
        item["source_id"]: item for item in target["mappings"]["layers"]
    }
    node_regions = {
        item["target_id"]: item["region_id"] for item in target["target_nodes"]
    }
    target_nodes = {item["target_id"]: item for item in target["target_nodes"]}
    source_plots = {item["beat_id"]: item for item in source.get("plot_beats") or []}
    source_emotions = {item["beat_id"]: item for item in source.get("emotion_beats") or []}
    plot_mapping = {
        item["source_id"]: item for item in target["mappings"]["plot_beats"]
    }
    emotion_mapping = {
        item["source_id"]: item for item in target["mappings"]["emotion_beats"]
    }
    reviews = payload.get("layer_reviews")
    if not isinstance(reviews, list) or [
        item.get("source_layer_id") for item in reviews if isinstance(item, dict)
    ] != list(source_layers):
        errors.append("layer_reviews 必须与来源 文字层同序全量对应")
    else:
        for item in reviews:
            layer_id = item["source_layer_id"]
            if item.get("source_content_sha256") != source_layers[layer_id]["content_sha256"]:
                errors.append(f"{layer_id} 来源层内容哈希已失效")
            if item.get("target_node_ids") != layer_mapping[layer_id]["target_node_ids"]:
                errors.append(f"{layer_id} 目标节点绑定已变化")
            expected_regions = list(
                dict.fromkeys(
                    node_regions[value]
                    for value in layer_mapping[layer_id]["target_node_ids"]
                    if value in node_regions
                )
            )
            if item.get("target_regions") != expected_regions:
                errors.append(f"{layer_id} 目标区域与目标节点绑定不一致")
            if item.get("realized") is not True:
                errors.append(f"{layer_id} 尚未确认 realized=true")
            if item.get("topology_preserved") is not True:
                errors.append(f"{layer_id} 尚未确认 topology_preserved=true")
            allowed_text = "\n".join(
                regions.get(region_id, "") for region_id in item.get("target_regions") or []
            )
            _validate_audit_field_reviews(
                item.get("topology_reviews"),
                LAYER_AUDIT_TOPOLOGY_FIELDS,
                f"{layer_id}.topology_reviews",
                allowed_text,
                errors,
            )
            source_rules = source_layers[layer_id].get("must_preserve_in_target") or []
            rule_reviews = item.get("preserve_rule_reviews")
            if not isinstance(rule_reviews, list) or [
                value.get("rule_index") for value in rule_reviews if isinstance(value, dict)
            ] != list(range(1, len(source_rules) + 1)):
                errors.append(f"{layer_id}.preserve_rule_reviews 必须逐条覆盖来源保留规则")
            else:
                for value in rule_reviews:
                    _validate_audit_detail(
                        value,
                        f"{layer_id}.preserve_rule_reviews[{value['rule_index']}]",
                        allowed_text,
                        errors,
                    )
            dimension_reviews = item.get("dimension_reviews")
            dimension_fields = tuple(SOURCE_MAP_VALIDATOR.DIMENSION_FIELDS)
            if not isinstance(dimension_reviews, dict) or set(dimension_reviews) != set(dimension_fields):
                errors.append(f"{layer_id}.dimension_reviews 必须逐项覆盖来源六维")
            else:
                source_dimensions = source_layers[layer_id].get("dimension_realization") or {}
                for field in dimension_fields:
                    value = dimension_reviews[field]
                    expected_status = str((source_dimensions.get(field) or {}).get("status") or "")
                    if not isinstance(value, dict) or value.get("source_status") != expected_status:
                        errors.append(f"{layer_id}.dimension_reviews.{field}.source_status 与来源不一致")
                    _validate_audit_detail(
                        value,
                        f"{layer_id}.dimension_reviews.{field}",
                        allowed_text,
                        errors,
                    )
            quotes = item.get("evidence_quotes")
            if not isinstance(quotes, list) or not quotes:
                errors.append(f"{layer_id} 缺少正文逐字引句")
            else:
                for quote in quotes:
                    if not isinstance(quote, str) or not quote.strip() or quote not in allowed_text:
                        errors.append(f"{layer_id} 引句不在绑定的正文区域内: {quote!r}")
            detail_quotes = _all_detail_quotes(item.get("topology_reviews"))
            for value in item.get("preserve_rule_reviews") or []:
                for quote in _all_detail_quotes([value]):
                    if quote not in detail_quotes:
                        detail_quotes.append(quote)
            for quote in _all_detail_quotes(item.get("dimension_reviews")):
                if quote not in detail_quotes:
                    detail_quotes.append(quote)
            if quotes != detail_quotes:
                errors.append(f"{layer_id}.evidence_quotes 必须由逐项层审证据确定性汇总")
            if len(str(item.get("conclusion") or "").strip()) < 12:
                errors.append(f"{layer_id} 人工结论不足 12 字")
    node_reviews = payload.get("node_reviews")
    expected_node_ids = list(target_nodes)
    if not isinstance(node_reviews, list) or [
        item.get("target_node_id") for item in node_reviews if isinstance(item, dict)
    ] != expected_node_ids:
        errors.append("node_reviews 必须与目标节点同序全量对应")
    else:
        for item in node_reviews:
            target_id = item["target_node_id"]
            node = target_nodes[target_id]
            if item.get("source_refs") != node.get("source_refs"):
                errors.append(f"{target_id} source_refs 与目标脑图不一致")
            if item.get("target_region") != node.get("region_id"):
                errors.append(f"{target_id} target_region 与目标脑图不一致")
            if item.get("realized") is not True:
                errors.append(f"{target_id} 尚未确认 realized=true")
            if item.get("granularity_preserved") is not True:
                errors.append(f"{target_id} 尚未确认 granularity_preserved=true")
            quotes = item.get("evidence_quotes")
            if not isinstance(quotes, list) or not quotes:
                errors.append(f"{target_id} 缺少正文逐字引句")
            else:
                allowed_text = regions.get(str(item.get("target_region") or ""), "")
                for quote in quotes:
                    if not isinstance(quote, str) or not quote.strip() or quote not in allowed_text:
                        errors.append(f"{target_id} 引句不在绑定正文区域内: {quote!r}")
            if len(str(item.get("conclusion") or "").strip()) < 12:
                errors.append(f"{target_id} 节点结论不足 12 字")
    plot_reviews = payload.get("plot_reviews")
    expected_plot_ids = list(source_plots)
    if not isinstance(plot_reviews, list) or [
        item.get("source_plot_id") for item in plot_reviews if isinstance(item, dict)
    ] != expected_plot_ids:
        errors.append("plot_reviews 必须与来源 P 拍同序全量对应")
    else:
        for item in plot_reviews:
            beat_id = item["source_plot_id"]
            expected_target = plot_mapping[beat_id]["target_id"]
            if item.get("source_content_sha256") != source_plots[beat_id]["content_sha256"]:
                errors.append(f"{beat_id} 来源 P 拍内容哈希已失效")
            if item.get("target_node_id") != expected_target:
                errors.append(f"{beat_id} 目标节点绑定已变化")
            expected_region = node_regions[expected_target]
            if item.get("target_region") != expected_region:
                errors.append(f"{beat_id} 目标区域与目标节点不一致")
            for field, label in (
                ("function_preserved", "承重功能"),
                ("action_preserved", "action"),
                ("control_change_preserved", "control_change"),
                ("information_change_preserved", "information_change"),
                ("consequence_preserved", "consequence"),
            ):
                if item.get(field) is not True:
                    errors.append(f"{beat_id} 尚未确认 {label} 保真")
            allowed_text = regions.get(expected_region, "")
            _validate_audit_field_reviews(
                item.get("field_reviews"),
                PLOT_AUDIT_FIELDS,
                f"{beat_id}.field_reviews",
                allowed_text,
                errors,
            )
            quotes = item.get("evidence_quotes")
            if not isinstance(quotes, list) or not quotes:
                errors.append(f"{beat_id} 缺少正文逐字引句")
            else:
                for quote in quotes:
                    if not isinstance(quote, str) or not quote.strip() or quote not in allowed_text:
                        errors.append(f"{beat_id} 引句不在绑定正文区域内: {quote!r}")
            if quotes != _all_detail_quotes(item.get("field_reviews")):
                errors.append(f"{beat_id}.evidence_quotes 必须由四项 P 拍证据确定性汇总")
            if len(str(item.get("conclusion") or "").strip()) < 12:
                errors.append(f"{beat_id} P 拍功能结论不足 12 字")
    emotion_reviews = payload.get("emotion_reviews")
    expected_emotion_ids = list(source_emotions)
    if not isinstance(emotion_reviews, list) or [
        item.get("source_emotion_id") for item in emotion_reviews if isinstance(item, dict)
    ] != expected_emotion_ids:
        errors.append("emotion_reviews 必须与来源 E 拍同序全量对应")
    else:
        for item in emotion_reviews:
            beat_id = item["source_emotion_id"]
            expected_target = emotion_mapping[beat_id]["target_id"]
            expected_region = node_regions[expected_target]
            if item.get("source_content_sha256") != source_emotions[beat_id]["content_sha256"]:
                errors.append(f"{beat_id} 来源 E 拍内容哈希已失效")
            if item.get("target_node_id") != expected_target:
                errors.append(f"{beat_id} E 拍目标节点绑定已变化")
            if item.get("target_region") != expected_region:
                errors.append(f"{beat_id} E 拍目标区域与目标节点不一致")
            for field in EMOTION_AUDIT_FIELDS:
                flag = f"{field}_preserved"
                if item.get(flag) is not True:
                    errors.append(f"{beat_id} 尚未确认 {field} 保真")
            if item.get("whole_beat_in_one_node") is not True:
                errors.append(f"{beat_id} 尚未确认整拍未拆散或顺移")
            allowed_text = regions.get(expected_region, "")
            _validate_audit_field_reviews(
                item.get("field_reviews"),
                EMOTION_AUDIT_FIELDS,
                f"{beat_id}.field_reviews",
                allowed_text,
                errors,
            )
            quotes = item.get("evidence_quotes")
            if quotes != _all_detail_quotes(item.get("field_reviews")):
                errors.append(f"{beat_id}.evidence_quotes 必须由五项 E 拍证据确定性汇总")
            if len(str(item.get("conclusion") or "").strip()) < 12:
                errors.append(f"{beat_id} E 拍功能结论不足 12 字")
    if payload.get("exceptions") != []:
        errors.append("正文覆盖回执仍有缺失、倒序或层型错配异常")
    region_coverage = payload.get("region_coverage")
    if not isinstance(region_coverage, list):
        errors.append("region_coverage 必须是数组")
    elif isinstance(reviews, list):
        expected_coverage = []
        for region_id in regions:
            layer_ids = [
                item.get("source_layer_id")
                for item in reviews
                if isinstance(item, dict) and region_id in (item.get("target_regions") or [])
            ]
            if layer_ids:
                expected_coverage.append(
                    {"region_id": region_id, "source_layer_ids": layer_ids}
                )
        if region_coverage != expected_coverage:
            errors.append("region_coverage 与逐层目标区域派生结果不一致")
    if require_gate and payload.get("gate_status") != "passed":
        errors.append("正文覆盖回执 gate_status 未 passed")
    return errors


def _validate_compact_evidence(
    value: Any, label: str, allowed_text: str, errors: list[str]
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} 必须是对象")
        return
    quotes = value.get("evidence_quotes")
    if not isinstance(quotes, list) or not quotes:
        errors.append(f"{label} 缺少正文逐字引句")
    else:
        for quote in quotes:
            if not isinstance(quote, str) or not quote.strip() or quote not in allowed_text:
                errors.append(f"{label} 引句不在绑定正文区域内: {quote!r}")
    if len(str(value.get("conclusion") or "").strip()) < 12:
        errors.append(f"{label}.conclusion 不足 12 字")


def validate_compact_audit_payload(
    payload: dict[str, Any],
    project_dir: Path,
    source: dict[str, Any],
    target: dict[str, Any],
    draft_text: str,
    regions: dict[str, str],
) -> list[str]:
    """Validate one concise realization review without duplicating field audits."""
    errors: list[str] = []
    source_layers = {
        str(item["layer_id"]): item
        for item in source.get("layers") or []
        if isinstance(item, dict)
    }
    target_nodes = {
        str(item["target_id"]): item
        for item in target.get("target_nodes") or []
        if isinstance(item, dict)
    }
    layer_mapping = {
        str(item["source_id"]): item
        for item in target.get("mappings", {}).get("layers") or []
        if isinstance(item, dict)
    }
    compact_layers = payload.get("layer_reviews")
    expected_layers = list(source_layers)
    if not isinstance(compact_layers, list) or [
        item.get("source_layer_id") for item in compact_layers if isinstance(item, dict)
    ] != expected_layers:
        errors.append("compact layer_reviews 必须与来源文字层同序全量对应")
    else:
        for item in compact_layers:
            layer_id = str(item["source_layer_id"])
            mapping = layer_mapping[layer_id]
            target_ids = [str(value) for value in mapping["target_node_ids"]]
            target_regions = list(
                dict.fromkeys(
                    target_nodes[value]["region_id"]
                    for value in target_ids
                    if value in target_nodes
                )
            )
            if item.get("source_content_sha256") != source_layers[layer_id]["content_sha256"]:
                errors.append(f"{layer_id} 来源层内容哈希已失效")
            if item.get("target_node_ids") != target_ids:
                errors.append(f"{layer_id} 目标节点绑定已变化")
            if item.get("target_regions") != target_regions:
                errors.append(f"{layer_id} 目标区域绑定已变化")
            if item.get("realized") is not True:
                errors.append(f"{layer_id} 尚未确认 realized=true")
            if item.get("topology_preserved") is not True:
                errors.append(f"{layer_id} 尚未确认 topology_preserved=true")
            allowed_text = "\n".join(regions.get(value, "") for value in target_regions)
            _validate_compact_evidence(item, layer_id, allowed_text, errors)

    compact_nodes = payload.get("node_reviews")
    expected_nodes = list(target_nodes)
    if not isinstance(compact_nodes, list) or [
        item.get("target_node_id") for item in compact_nodes if isinstance(item, dict)
    ] != expected_nodes:
        errors.append("compact node_reviews 必须与目标节点同序全量对应")
    else:
        for item in compact_nodes:
            target_id = str(item["target_node_id"])
            node = target_nodes[target_id]
            if item.get("source_refs") != node.get("source_refs"):
                errors.append(f"{target_id} source_refs 与目标脑图不一致")
            if item.get("target_region") != node.get("region_id"):
                errors.append(f"{target_id} target_region 与目标脑图不一致")
            if item.get("realized") is not True:
                errors.append(f"{target_id} 尚未确认 realized=true")
            if item.get("granularity_preserved") is not True:
                errors.append(f"{target_id} 尚未确认 granularity_preserved=true")
            _validate_compact_evidence(
                item,
                target_id,
                regions.get(str(item.get("target_region") or ""), ""),
                errors,
            )

    compact_plots = payload.get("plot_reviews")
    source_plots = {
        str(item["beat_id"]): item
        for item in source.get("plot_beats") or []
        if isinstance(item, dict)
    }
    plot_mapping = {
        str(item["source_id"]): item
        for item in target.get("mappings", {}).get("plot_beats") or []
        if isinstance(item, dict)
    }
    expected_plots = list(source_plots)
    if not isinstance(compact_plots, list) or [
        item.get("source_plot_id") for item in compact_plots if isinstance(item, dict)
    ] != expected_plots:
        errors.append("compact plot_reviews 必须与来源 P 拍同序全量对应")
    else:
        for item in compact_plots:
            beat_id = str(item["source_plot_id"])
            expected_target = str(plot_mapping[beat_id]["target_id"])
            expected_region = str(target_nodes[expected_target]["region_id"])
            if item.get("source_content_sha256") != source_plots[beat_id]["content_sha256"]:
                errors.append(f"{beat_id} 来源 P 拍内容哈希已失效")
            if item.get("target_node_id") != expected_target:
                errors.append(f"{beat_id} P 拍目标节点绑定已变化")
            if item.get("target_region") != expected_region:
                errors.append(f"{beat_id} P 拍目标区域已变化")
            required_flags = (
                "function_preserved",
                "action_preserved",
                "control_change_preserved",
                "information_change_preserved",
                "consequence_preserved",
            )
            if any(item.get(field) is not True for field in required_flags):
                errors.append(f"{beat_id} compact P 拍必须逐项确认五个保真布尔")
            allowed_text = regions.get(expected_region, "")
            _validate_audit_field_reviews(
                item.get("field_reviews"),
                PLOT_AUDIT_FIELDS,
                f"{beat_id}.field_reviews",
                allowed_text,
                errors,
            )
            quotes = item.get("evidence_quotes")
            if not isinstance(quotes, list) or not quotes:
                errors.append(f"{beat_id} compact P 拍缺少正文引句")
            elif any(
                not isinstance(quote, str) or not quote.strip() or quote not in allowed_text
                for quote in quotes
            ):
                errors.append(f"{beat_id} compact P 拍存在无效正文引句")
            if quotes != _all_detail_quotes(item.get("field_reviews")):
                errors.append(f"{beat_id} compact P 拍引句未由四项字段证据确定性汇总")
            if len(str(item.get("conclusion") or "").strip()) < 12:
                errors.append(f"{beat_id} compact P 拍结论不足 12 字")

    compact_emotions = payload.get("emotion_reviews")
    source_emotions = {
        str(item["beat_id"]): item
        for item in source.get("emotion_beats") or []
        if isinstance(item, dict)
    }
    emotion_mapping = {
        str(item["source_id"]): item
        for item in target.get("mappings", {}).get("emotion_beats") or []
        if isinstance(item, dict)
    }
    expected_emotions = list(source_emotions)
    if not isinstance(compact_emotions, list) or [
        item.get("source_emotion_id") for item in compact_emotions if isinstance(item, dict)
    ] != expected_emotions:
        errors.append("compact emotion_reviews 必须与来源 E 拍同序全量对应")
    else:
        for item in compact_emotions:
            beat_id = str(item["source_emotion_id"])
            expected_target = str(emotion_mapping[beat_id]["target_id"])
            expected_region = str(target_nodes[expected_target]["region_id"])
            if item.get("source_content_sha256") != source_emotions[beat_id]["content_sha256"]:
                errors.append(f"{beat_id} 来源 E 拍内容哈希已失效")
            if item.get("target_node_id") != expected_target:
                errors.append(f"{beat_id} E 拍目标节点绑定已变化")
            if item.get("target_region") != expected_region:
                errors.append(f"{beat_id} E 拍目标区域已变化")
            required_flags = tuple(f"{field}_preserved" for field in EMOTION_AUDIT_FIELDS)
            if any(item.get(field) is not True for field in required_flags):
                errors.append(f"{beat_id} compact E 拍必须逐项确认五个保真布尔")
            if item.get("whole_beat_in_one_node") is not True:
                errors.append(f"{beat_id} compact E 拍必须确认整拍同节点")
            allowed_text = regions.get(expected_region, "")
            _validate_audit_field_reviews(
                item.get("field_reviews"),
                EMOTION_AUDIT_FIELDS,
                f"{beat_id}.field_reviews",
                allowed_text,
                errors,
            )
            quotes = item.get("evidence_quotes")
            if not isinstance(quotes, list) or not quotes:
                errors.append(f"{beat_id} compact E 拍缺少正文引句")
            elif any(
                not isinstance(quote, str) or not quote.strip() or quote not in allowed_text
                for quote in quotes
            ):
                errors.append(f"{beat_id} compact E 拍存在无效正文引句")
            if quotes != _all_detail_quotes(item.get("field_reviews")):
                errors.append(f"{beat_id} compact E 拍引句未由五项字段证据确定性汇总")
            if len(str(item.get("conclusion") or "").strip()) < 12:
                errors.append(f"{beat_id} compact E 拍结论不足 12 字")

    layer_reviews = compact_layers if isinstance(compact_layers, list) else []
    expected_coverage = []
    for region_id in regions:
        layer_ids = [
            item.get("source_layer_id")
            for item in layer_reviews
            if isinstance(item, dict) and region_id in (item.get("target_regions") or [])
        ]
        if layer_ids:
            expected_coverage.append(
                {"region_id": region_id, "source_layer_ids": layer_ids}
            )
    if payload.get("region_coverage") != expected_coverage:
        errors.append("compact region_coverage 与逐层目标区域派生结果不一致")
    if payload.get("exceptions") != []:
        errors.append("正文覆盖回执仍有未清零异常")
    return errors


def default_target_path(project_dir: Path) -> Path:
    return project_dir / "写作资产" / "目标成文脑图.json"


def default_audit_path(project_dir: Path) -> Path:
    return project_dir / "写作资产" / "正文覆盖回执.json"


def command_preflight(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    allow_partial = bool(getattr(args, "allow_partial", False))
    source_path, source = resolve_source_map(
        project, Path(args.source_map).resolve() if args.source_map else None
    )
    target_input, nodes = load_target_nodes(
        project,
        Path(args.mind_map).resolve() if args.mind_map else None,
        allow_partial=allow_partial,
    )
    errors = validate_explicit_source_refs(nodes, source, partial=allow_partial)
    dimension_inputs = _parse_json_argument(
        getattr(args, "dimensions_json", "{}"), "dimensions-json"
    )
    if dimension_inputs:
        expected_plot_ids = [str(item["beat_id"]) for item in source.get("plot_beats") or []]
        if list(dimension_inputs) != expected_plot_ids:
            errors.append("dimensions-json 必须与来源 P 拍同序全量对应")
        for source_id, dimensions in dimension_inputs.items():
            if source_id not in expected_plot_ids:
                continue
            try:
                _validated_replacement_dimensions(
                    dimensions, f"{source_id}.dimensions_changed"
                )
            except ValueError as exc:
                errors.append(str(exc))
    layer_anchor_inputs = _parse_json_argument(
        getattr(args, "layer_anchors_json", "{}"), "layer-anchors-json"
    )
    if layer_anchor_inputs:
        expected_layer_ids = [str(item["layer_id"]) for item in source.get("layers") or []]
        if list(layer_anchor_inputs) != expected_layer_ids:
            errors.append("layer-anchors-json 必须与来源文字层同序全量对应")
        source_lines = _source_original_lines(source)
        source_layers = {
            str(item["layer_id"]): item for item in source.get("layers") or []
        }
        for source_id, raw in layer_anchor_inputs.items():
            if source_id not in source_layers:
                continue
            anchor_errors: list[str] = []
            _validate_layer_source_anchors(
                _layer_anchor_review_input(raw, f"layer-anchors-json.{source_id}"),
                source_layers[source_id],
                source_lines,
                source_id,
                anchor_errors,
            )
            errors.extend(anchor_errors)
    payload = {
        "gate_status": "passed" if not errors else "blocked",
        "source_map": str(source_path),
        "target_input": target_input,
        "target_node_count": len(nodes),
    }
    return payload, errors


def command_init(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    output = Path(args.output).resolve() if args.output else default_target_path(project)
    if output.exists() and not args.force:
        raise ValueError(f"目标已存在，拒绝覆盖: {output}")
    source_path, source = resolve_source_map(
        project, Path(args.source_map).resolve() if args.source_map else None
    )
    target_input, nodes = load_target_nodes(
        project, Path(args.mind_map).resolve() if args.mind_map else None
    )
    payload = create_target_map(project, source_path, source, target_input, nodes)
    write_json(output, payload)
    dimensions_json = getattr(args, "dimensions_json", "{}")
    derive_emotions = bool(getattr(args, "derive_emotions_from_outline", False))
    layer_anchors_json = getattr(args, "layer_anchors_json", "{}")
    if _parse_json_argument(dimensions_json, "dimensions-json"):
        payload, _ = command_confirm_event_shells(
            argparse.Namespace(
                project_dir=str(project),
                input=str(output),
                reviews_json="{}",
                dimensions_json=dimensions_json,
            )
        )
    if derive_emotions or _parse_json_argument(layer_anchors_json, "layer-anchors-json"):
        payload, _ = command_confirm_fidelity(
            argparse.Namespace(
                project_dir=str(project),
                input=str(output),
                emotion_reviews_json="{}",
                layer_reviews_json="{}",
                layer_anchors_json=layer_anchors_json,
                derive_emotions_from_outline=derive_emotions,
            )
        )
    return payload, []


def command_validate(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_target_path(project)
    payload = read_object(path, "目标成文脑图")
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    errors = validate_target_map(payload, require_gate=False)
    payload["gate_status"] = "passed" if not errors else "blocked"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, errors


def command_rebind(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_target_path(project)
    payload = read_object(path, "目标成文脑图")
    source_path, source = resolve_source_map(
        project, Path(args.source_map).resolve() if args.source_map else None
    )
    mind_map = Path(args.mind_map).resolve() if args.mind_map else None
    if mind_map is None and (payload.get("target_input") or {}).get("kind") == "mind_map":
        mind_map = Path(payload["target_input"]["path"])
    target_input, nodes = load_target_nodes(project, mind_map)
    payload = rebind_target_map(payload, source_path, source, target_input, nodes)
    write_json(path, payload)
    return payload, []


def command_confirm_event_shells(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_target_path(project)
    payload = read_object(path, "目标成文脑图")
    source_path = Path(str((payload.get("source_map") or {}).get("path") or ""))
    source = read_object(source_path, "来源成文脑图")
    mapping_errors = validate_explicit_source_refs(payload.get("target_nodes") or [], source)
    if mapping_errors:
        raise ValueError("细纲全颗粒预检失败: " + " / ".join(mapping_errors))
    expected_mappings = explicit_source_ref_mappings(payload["target_nodes"], source)
    if payload.get("mappings") != expected_mappings:
        raise ValueError("目标脑图映射与细纲 source-map 声明不一致，必须先正式 rebind")
    review_inputs = _parse_json_argument(
        getattr(args, "reviews_json", "{}"), "reviews-json"
    )
    dimension_inputs = _parse_json_argument(
        getattr(args, "dimensions_json", "{}"), "dimensions-json"
    )
    if not review_inputs and not dimension_inputs:
        raise ValueError("confirm-event-shells 至少提交一个 P 拍复核或维度声明")
    target_by_source = {
        str(item["source_id"]): str(item["target_id"])
        for item in payload["mappings"]["plot_beats"]
    }
    replacement_by_id = {
        str(item.get("source_id") or ""): item
        for item in payload.get("event_shell_replacements") or []
        if isinstance(item, dict)
    }
    unknown = [source_id for source_id in review_inputs if source_id not in replacement_by_id]
    if unknown:
        raise ValueError(f"reviews-json 包含未知 P 拍: {unknown}")
    unknown_dimensions = [
        source_id for source_id in dimension_inputs if source_id not in replacement_by_id
    ]
    if unknown_dimensions:
        raise ValueError(f"dimensions-json 包含未知 P 拍: {unknown_dimensions}")
    overlapping = sorted(set(review_inputs) & set(dimension_inputs))
    if overlapping:
        raise ValueError(f"P 拍不得同时提交完整复核与紧凑维度声明: {overlapping}")

    target_nodes = {
        str(item.get("target_id") or ""): item
        for item in payload.get("target_nodes") or []
        if isinstance(item, dict)
    }
    for source_id, raw_dimensions in dimension_inputs.items():
        target_id = target_by_source[source_id]
        dimensions = _validated_replacement_dimensions(
            raw_dimensions, f"{source_id}.dimensions_changed"
        )
        evidence = str((target_nodes.get(target_id) or {}).get("evidence") or "").strip()
        if len(evidence) < 12:
            raise ValueError(f"{source_id} 绑定节点内容不足，不能紧凑派生 P 拍复核")
        summary = evidence[:180]
        replacement = replacement_by_id[source_id]
        replacement["dimensions_changed"] = dimensions
        replacement["function_reviews"] = {
            field: f"{field} 由 {target_id} 的显式细拍承接：{summary}"
            for field in PLOT_AUDIT_FIELDS
        }
        replacement["adaptation_decision"] = (
            f"{source_id}->{target_id}｜目标细拍已逐 P 换芯：{evidence}"
        )
        replacement["human_confirmed"] = True
    for source_id, raw in review_inputs.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{source_id} 复核必须是对象")
        target_id = target_by_source[source_id]
        if str(raw.get("target_id") or "") != target_id:
            raise ValueError(f"{source_id}.target_id 必须等于当前映射 {target_id}")
        dimensions = _validated_replacement_dimensions(
            raw.get("dimensions_changed"), f"{source_id}.dimensions_changed"
        )
        function_inputs = raw.get("function_reviews")
        if not isinstance(function_inputs, dict) or set(function_inputs) != set(PLOT_AUDIT_FIELDS):
            raise ValueError(f"{source_id}.function_reviews 必须按 P 拍四字段完整提交")
        function_reviews = {
            field: str(function_inputs[field]).strip() for field in PLOT_AUDIT_FIELDS
        }
        if any(len(value) < 8 for value in function_reviews.values()):
            raise ValueError(f"{source_id}.function_reviews 必须写四项专属目标实现")
        if len(set(function_reviews.values())) != len(function_reviews):
            raise ValueError(f"{source_id}.function_reviews 四项不得套用同一结论")
        decision = str(raw.get("adaptation_decision") or "").strip()
        if len(decision) < 12:
            raise ValueError(f"{source_id}.adaptation_decision 必须写本拍专属换芯判断")
        replacement = replacement_by_id[source_id]
        replacement["dimensions_changed"] = dimensions
        replacement["function_reviews"] = function_reviews
        replacement["adaptation_decision"] = f"{source_id}->{target_id}｜{decision}"
        replacement["human_confirmed"] = True
    confirmation = payload.setdefault("manual_confirmation", {})
    confirmation["mapping_complete"] = True
    confirmed_count = sum(
        item.get("human_confirmed") is True
        for item in payload.get("event_shell_replacements") or []
    )
    total_count = len(payload.get("event_shell_replacements") or [])
    confirmation["event_shell_replacements_confirmed"] = confirmed_count == total_count
    confirmation["note"] = (
        f"已逐 P 拍提交事件壳与四项承重复核：{confirmed_count}/{total_count}。"
    )
    invalidated = (payload.get("incremental_state") or {}).get("invalidated") or []
    confirmed_ids = set(review_inputs) | set(dimension_inputs)
    payload["incremental_state"] = {
        "invalidated": [
            item
            for item in invalidated
            if not (
                str(item).endswith(".event_shell_replacement")
                and str(item).split(".", 1)[0] in confirmed_ids
            )
        ]
    }
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def _parse_json_argument(value: str, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} 不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} 顶层必须是对象")
    return payload


def _parse_json_argument_or_file(
    value: str, file_value: str | None, label: str
) -> dict[str, Any]:
    if file_value:
        try:
            raw = (
                sys.stdin.read()
                if file_value == "/dev/stdin"
                else Path(file_value).read_text(encoding="utf-8")
            )
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} 文件输入不是合法 JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{label} 顶层必须是对象")
        return payload
    return _parse_json_argument(value, label)


def _validated_replacement_dimensions(value: Any, label: str) -> list[str]:
    dimensions = [
        str(item).strip() for item in value or [] if str(item).strip()
    ]
    unknown = [item for item in dimensions if item not in REPLACEMENT_DIMENSIONS]
    if unknown:
        suggestions = []
        for item in unknown:
            matches = difflib.get_close_matches(
                item, REPLACEMENT_DIMENSION_ORDER, n=1, cutoff=0.45
            )
            if matches:
                suggestions.append(f"{item} -> {matches[0]}")
        hint = f"；可能想写: {', '.join(suggestions)}" if suggestions else ""
        raise ValueError(
            f"{label} 包含未知维度 {unknown}；合法维度仅为 "
            f"{', '.join(REPLACEMENT_DIMENSION_ORDER)}{hint}"
        )
    if len(set(dimensions)) < 3:
        raise ValueError(f"{label} 至少包含三个合法换壳维度")
    return dimensions


def _layer_anchor_review_input(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, str):
        quotes = [value]
    elif isinstance(value, list):
        quotes = value
    elif isinstance(value, dict):
        quotes = value.get("source_anchor_quotes")
    else:
        raise ValueError(f"{label} 必须是短引句、短引句数组或含 source_anchor_quotes 的对象")
    return {
        "source_range_read": True,
        "source_anchor_quotes": quotes,
    }


def _target_evidence_summary(
    target_ids: list[str], node_by_id: dict[str, dict[str, Any]]
) -> str:
    parts = []
    for target_id in target_ids:
        evidence = str((node_by_id.get(target_id) or {}).get("evidence") or "").strip()
        parts.append(f"{target_id}:{evidence[:72]}")
    return "；".join(parts)[:240]


def _confirmed_fidelity_detail(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("preserved") is not True:
        raise ValueError(f"{label} 必须显式提交 preserved=true")
    realization = str(value.get("target_realization") or "").strip()
    if len(realization) < 8:
        raise ValueError(f"{label}.target_realization 必须写本书具体实现")
    return {"preserved": True, "target_realization": realization}


def command_confirm_fidelity(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_target_path(project)
    payload = read_object(path, "目标成文脑图")
    source_path = Path(str((payload.get("source_map") or {}).get("path") or ""))
    source = read_object(source_path, "来源成文脑图")
    source_lines = _source_original_lines(source)
    source_layers = {
        str(item.get("layer_id") or ""): item
        for item in source.get("layers") or []
        if isinstance(item, dict)
    }
    nodes = payload.get("target_nodes") or []
    expected_mappings = explicit_source_ref_mappings(nodes, source)
    if payload.get("mappings") != expected_mappings:
        raise ValueError("目标脑图映射与细纲 source-map 声明不一致，必须先正式 rebind")
    emotion_inputs = _parse_json_argument(args.emotion_reviews_json, "emotion-reviews-json")
    layer_inputs = _parse_json_argument(args.layer_reviews_json, "layer-reviews-json")
    layer_anchor_inputs = _parse_json_argument(
        getattr(args, "layer_anchors_json", "{}"), "layer-anchors-json"
    )
    derive_emotions = bool(getattr(args, "derive_emotions_from_outline", False))
    if derive_emotions and emotion_inputs:
        raise ValueError("E 拍不得同时提交完整复核与 --derive-emotions-from-outline")
    if (
        not emotion_inputs
        and not derive_emotions
        and not layer_inputs
        and not layer_anchor_inputs
    ):
        raise ValueError("confirm-fidelity 至少提交一个 E 拍或文字层复核")

    emotion_by_id = {
        str(item.get("source_id") or ""): item
        for item in payload.get("emotion_fidelity_reviews") or []
        if isinstance(item, dict)
    }
    unknown_emotions = [source_id for source_id in emotion_inputs if source_id not in emotion_by_id]
    if unknown_emotions:
        raise ValueError(f"emotion-reviews-json 包含未知 E 拍: {unknown_emotions}")
    if derive_emotions:
        target_nodes = {
            str(item.get("target_id") or ""): item
            for item in nodes
            if isinstance(item, dict)
        }
        for item in payload.get("emotion_fidelity_reviews") or []:
            target_id = str(item.get("target_id") or "")
            evidence = str(
                (target_nodes.get(target_id) or {}).get("evidence") or ""
            ).strip()
            if len(evidence) < 12:
                raise ValueError(
                    f"{item.get('source_id')} 绑定节点内容不足，不能派生 E 拍复核"
                )
            summary = evidence[:220]
            item["whole_beat_in_one_node"] = True
            item["field_reviews"] = {
                field: {
                    "preserved": True,
                    "target_realization": (
                        f"{field} 由 {target_id} 的单一显式细拍承接：{summary}"
                    ),
                }
                for field in EMOTION_FIDELITY_FIELDS
            }
            item["human_confirmed"] = True
    for source_id, raw in emotion_inputs.items():
        if not isinstance(raw, dict) or raw.get("whole_beat_in_one_node") is not True:
            raise ValueError(f"{source_id} 必须显式确认 whole_beat_in_one_node=true")
        field_inputs = raw.get("field_reviews")
        if not isinstance(field_inputs, dict) or set(field_inputs) != set(EMOTION_FIDELITY_FIELDS):
            raise ValueError(f"{source_id}.field_reviews 必须按固定五字段完整提交")
        item = emotion_by_id[source_id]
        item["whole_beat_in_one_node"] = True
        item["field_reviews"] = {
            field: _confirmed_fidelity_detail(
                field_inputs[field], f"{source_id}.field_reviews.{field}"
            )
            for field in EMOTION_FIDELITY_FIELDS
        }
        item["human_confirmed"] = True

    layer_by_id = {
        str(item.get("source_id") or ""): item
        for item in payload.get("layer_fidelity_reviews") or []
        if isinstance(item, dict)
    }
    unknown_layers = [source_id for source_id in layer_inputs if source_id not in layer_by_id]
    if unknown_layers:
        raise ValueError(f"layer-reviews-json 包含未知文字层: {unknown_layers}")
    unknown_anchor_layers = [
        source_id for source_id in layer_anchor_inputs if source_id not in layer_by_id
    ]
    if unknown_anchor_layers:
        raise ValueError(
            f"layer-anchors-json 包含未知文字层: {unknown_anchor_layers}"
        )
    overlapping_layers = sorted(set(layer_inputs) & set(layer_anchor_inputs))
    if overlapping_layers:
        raise ValueError(
            f"文字层不得同时提交完整复核与紧凑锚点复核: {overlapping_layers}"
        )

    node_by_id = {
        str(item.get("target_id") or ""): item
        for item in nodes
        if isinstance(item, dict)
    }
    for source_id, raw in layer_anchor_inputs.items():
        item = layer_by_id[source_id]
        anchor_review = _layer_anchor_review_input(
            raw, f"layer-anchors-json.{source_id}"
        )
        anchor_errors: list[str] = []
        _validate_layer_source_anchors(
            anchor_review,
            source_layers[source_id],
            source_lines,
            source_id,
            anchor_errors,
        )
        if anchor_errors:
            raise ValueError(" / ".join(anchor_errors))
        target_ids = [str(value) for value in item["target_node_ids"]]
        if not target_ids:
            raise ValueError(f"{source_id} 没有显式目标节点，不能使用紧凑锚点复核")
        summary = _target_evidence_summary(target_ids, node_by_id)
        source_layer = source_layers[source_id]
        modes = ",".join(str(value) for value in source_layer.get("layer_modes") or [])
        first_target = target_ids[0]
        last_target = target_ids[-1]
        item["source_range_read"] = True
        item["source_anchor_quotes"] = [
            str(value).strip() for value in anchor_review["source_anchor_quotes"]
        ]
        item["no_function_shift"] = True
        item["topology_reviews"] = {
            "layer_modes": {
                "preserved": True,
                "target_realization": f"来源层型 {modes} 由显式节点按原位施工：{summary}",
            },
            "entry_relation": {
                "preserved": True,
                "target_realization": f"本层从 {first_target} 的显式细拍进入：{summary}",
            },
            "exit_relation": {
                "preserved": True,
                "target_realization": f"本层在 {last_target} 的显式细拍退出：{summary}",
            },
            "narrative_distance": {
                "preserved": True,
                "target_realization": (
                    f"来源叙述距离“{source_layer.get('narrative_distance')}”"
                    f"由绑定节点承接：{summary}"
                ),
            },
        }
        item["preserve_rule_reviews"] = [
            {
                "rule_index": review["rule_index"],
                "preserved": True,
                "target_node_ids": list(target_ids),
                "target_realization": (
                    f"来源规则 {review['rule_index']} 由显式绑定节点承接：{summary}"
                ),
            }
            for review in item["preserve_rule_reviews"]
        ]
        item["dimension_reviews"] = {
            field: {
                "source_status": review["source_status"],
                "preserved": True,
                "target_node_ids": list(target_ids),
                "target_realization": (
                    f"{field} 来源状态 {review['source_status']}，"
                    f"由显式节点按本层位置协同：{summary}"
                ),
            }
            for field, review in item["dimension_reviews"].items()
        }
        item["human_confirmed"] = True

    for source_id, raw in layer_inputs.items():
        if not isinstance(raw, dict) or raw.get("no_function_shift") is not True:
            raise ValueError(f"{source_id} 必须显式确认 no_function_shift=true")
        item = layer_by_id[source_id]
        anchor_errors: list[str] = []
        _validate_layer_source_anchors(
            raw, source_layers[source_id], source_lines, source_id, anchor_errors
        )
        if anchor_errors:
            raise ValueError(" / ".join(anchor_errors))
        item["source_range_read"] = True
        item["source_anchor_quotes"] = [
            str(value).strip() for value in raw["source_anchor_quotes"]
        ]
        allowed_targets = [str(value) for value in item["target_node_ids"]]
        topology_inputs = raw.get("topology_reviews")
        if not isinstance(topology_inputs, dict) or set(topology_inputs) != set(LAYER_TOPOLOGY_FIELDS):
            raise ValueError(f"{source_id}.topology_reviews 必须按固定字段完整提交")
        rule_inputs = raw.get("preserve_rule_reviews")
        expected_rule_indexes = [
            value["rule_index"] for value in item["preserve_rule_reviews"]
        ]
        if not isinstance(rule_inputs, list) or [
            value.get("rule_index") for value in rule_inputs if isinstance(value, dict)
        ] != expected_rule_indexes:
            raise ValueError(f"{source_id}.preserve_rule_reviews 必须逐条同序提交")
        dimension_inputs = raw.get("dimension_reviews")
        expected_dimensions = list(SOURCE_MAP_VALIDATOR.DIMENSION_FIELDS)
        if not isinstance(dimension_inputs, dict) or set(dimension_inputs) != set(expected_dimensions):
            raise ValueError(f"{source_id}.dimension_reviews 必须逐项提交来源六维")
        item["no_function_shift"] = True
        item["topology_reviews"] = {
            field: _confirmed_fidelity_detail(
                topology_inputs[field], f"{source_id}.topology_reviews.{field}"
            )
            for field in LAYER_TOPOLOGY_FIELDS
        }
        confirmed_rules = []
        for raw_rule in rule_inputs:
            label = f"{source_id}.preserve_rule_reviews[{raw_rule['rule_index']}]"
            if raw_rule.get("preserved") is not True:
                raise ValueError(f"{label} 必须显式提交 preserved=true")
            target_ids = [str(value) for value in raw_rule.get("target_node_ids") or []]
            check_errors: list[str] = []
            _validate_fidelity_target_ids(target_ids, allowed_targets, label, check_errors)
            if check_errors:
                raise ValueError(" / ".join(check_errors))
            realization = str(raw_rule.get("target_realization") or "").strip()
            if len(realization) < 8:
                raise ValueError(f"{label}.target_realization 必须写具体承载")
            confirmed_rules.append(
                {
                    "rule_index": raw_rule["rule_index"],
                    "preserved": True,
                    "target_node_ids": target_ids,
                    "target_realization": realization,
                }
            )
        item["preserve_rule_reviews"] = confirmed_rules
        confirmed_dimensions = {}
        for field in expected_dimensions:
            raw_dimension = dimension_inputs[field]
            label = f"{source_id}.dimension_reviews.{field}"
            if not isinstance(raw_dimension, dict) or raw_dimension.get("preserved") is not True:
                raise ValueError(f"{label} 必须显式提交 preserved=true")
            target_ids = [str(value) for value in raw_dimension.get("target_node_ids") or []]
            check_errors = []
            _validate_fidelity_target_ids(target_ids, allowed_targets, label, check_errors)
            if check_errors:
                raise ValueError(" / ".join(check_errors))
            realization = str(raw_dimension.get("target_realization") or "").strip()
            if len(realization) < 8:
                raise ValueError(f"{label}.target_realization 必须写具体协同或缺席方式")
            confirmed_dimensions[field] = {
                "source_status": item["dimension_reviews"][field]["source_status"],
                "preserved": True,
                "target_node_ids": target_ids,
                "target_realization": realization,
            }
        item["dimension_reviews"] = confirmed_dimensions
        item["human_confirmed"] = True

    confirmation = payload.setdefault("manual_confirmation", {})
    confirmation["mapping_complete"] = True
    confirmation["emotion_fidelity_confirmed"] = all(
        item.get("human_confirmed") is True
        for item in payload.get("emotion_fidelity_reviews") or []
    )
    confirmation["layer_fidelity_confirmed"] = all(
        item.get("human_confirmed") is True
        for item in payload.get("layer_fidelity_reviews") or []
    )
    invalidated = (payload.get("incremental_state") or {}).get("invalidated") or []
    confirmed_ids = set(emotion_inputs) | set(layer_inputs) | set(layer_anchor_inputs)
    if derive_emotions:
        confirmed_ids.update(
            str(item.get("source_id") or "")
            for item in payload.get("emotion_fidelity_reviews") or []
        )
    payload["incremental_state"] = {
        "invalidated": [
            value
            for value in invalidated
            if str(value).split(".", 1)[0] not in confirmed_ids
        ]
    }
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def _apply_legacy_binding_overrides(
    mappings: dict[str, Any], args: argparse.Namespace
) -> None:
    plot_by_id = {
        str(item.get("source_id") or ""): item
        for item in mappings.get("plot_beats") or []
    }
    for source_id, target_id in _parse_json_argument(
        args.plot_overrides_json, "plot-overrides-json"
    ).items():
        if source_id not in plot_by_id:
            raise ValueError(f"未知 P 拍覆盖: {source_id}")
        plot_by_id[source_id]["target_id"] = str(target_id)

    emotion_by_id = {
        str(item.get("source_id") or ""): item
        for item in mappings.get("emotion_beats") or []
    }
    for source_id, target_id in _parse_json_argument(
        args.emotion_overrides_json, "emotion-overrides-json"
    ).items():
        if source_id not in emotion_by_id:
            raise ValueError(f"未知 E 拍覆盖: {source_id}")
        emotion_by_id[source_id]["target_id"] = str(target_id)

    subflow_by_id = {
        str(item.get("source_id") or ""): item
        for item in mappings.get("subflows") or []
    }
    for source_id, steps in _parse_json_argument(
        args.subflow_overrides_json, "subflow-overrides-json"
    ).items():
        if source_id not in subflow_by_id or not isinstance(steps, list):
            raise ValueError(f"未知 SF 或非法覆盖: {source_id}")
        chain = subflow_by_id[source_id].get("performance_chain") or []
        if len(chain) != len(steps):
            raise ValueError(
                f"{source_id} 覆盖步数错误: expected={len(chain)}, actual={len(steps)}"
            )
        for step, raw_targets in zip(chain, steps):
            targets = raw_targets if isinstance(raw_targets, list) else [raw_targets]
            step["target_node_ids"] = [str(item) for item in targets]

    layer_by_id = {
        str(item.get("source_id") or ""): item
        for item in mappings.get("layers") or []
    }
    for source_id, raw_targets in _parse_json_argument(
        args.layer_overrides_json, "layer-overrides-json"
    ).items():
        if source_id not in layer_by_id:
            raise ValueError(f"未知来源层覆盖: {source_id}")
        targets = raw_targets if isinstance(raw_targets, list) else [raw_targets]
        layer_by_id[source_id]["target_node_ids"] = [str(item) for item in targets]


def _source_refs_from_mappings(
    target_nodes: list[dict[str, Any]], mappings: dict[str, Any]
) -> dict[str, dict[str, list[str]]]:
    target_ids = {str(item["target_id"]) for item in target_nodes}
    refs = {target_id: empty_source_refs() for target_id in target_ids}

    for item in mappings.get("plot_beats") or []:
        target_id = str(item.get("target_id") or "")
        if target_id not in refs:
            raise ValueError(f"{item.get('source_id')} 缺少或引用未知目标节点")
        refs[target_id]["plot_beat_ids"].append(str(item["source_id"]))
    for item in mappings.get("emotion_beats") or []:
        target_id = str(item.get("target_id") or "")
        if target_id not in refs:
            raise ValueError(f"{item.get('source_id')} 缺少或引用未知目标节点")
        refs[target_id]["emotion_beat_ids"].append(str(item["source_id"]))
    for item in mappings.get("subflows") or []:
        source_id = str(item["source_id"])
        for step in item.get("performance_chain") or []:
            step_id = f"{source_id}#{step.get('step_index')}"
            targets = step.get("target_node_ids") or []
            if not targets:
                raise ValueError(f"{step_id} 缺少目标节点")
            for target_id in targets:
                if target_id not in refs:
                    raise ValueError(f"{step_id} 引用未知目标节点: {target_id}")
                refs[target_id]["subflow_steps"].append(step_id)
    for item in mappings.get("layers") or []:
        source_id = str(item["source_id"])
        targets = item.get("target_node_ids") or []
        if not targets:
            raise ValueError(f"{source_id} 缺少目标节点")
        for target_id in targets:
            if target_id not in refs:
                raise ValueError(f"{source_id} 引用未知目标节点: {target_id}")
            refs[target_id]["layer_ids"].append(source_id)
    return refs


def _format_source_map_comment(refs: dict[str, list[str]]) -> str:
    parts = []
    for label, key in SOURCE_REF_KEYS.items():
        values = refs[key]
        if values:
            parts.append(f"{label}={','.join(values)}")
    return "<!-- source-map: " + "; ".join(parts) + " -->"


def _legacy_nodes_in_outline_order(
    outline_path: Path, target_nodes: list[dict[str, Any]]
) -> tuple[list[str], list[int], list[dict[str, Any]]]:
    text = outline_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fine_indices = [
        index for index, line in enumerate(lines) if line.startswith("- 细拍拆分：")
    ]
    if len(fine_indices) != len(target_nodes):
        raise ValueError(
            "旧项目目标节点数与细纲行数不一致: "
            f"nodes={len(target_nodes)}, outline_beats={len(fine_indices)}"
        )
    nodes_by_evidence: dict[str, list[dict[str, Any]]] = {}
    for node in target_nodes:
        nodes_by_evidence.setdefault(str(node.get("evidence") or ""), []).append(node)
    ordered_nodes: list[dict[str, Any]] = []
    for index in fine_indices:
        visible, _ = parse_source_map_comment(lines[index])
        evidence = visible.split("：", 1)[1].strip() if "：" in visible else ""
        matches = nodes_by_evidence.get(evidence, [])
        if len(matches) != 1:
            raise ValueError(
                f"旧项目细拍无法按可见证据唯一匹配目标节点: {evidence!r}"
            )
        ordered_nodes.append(matches[0])
    return lines, fine_indices, ordered_nodes


def migrate_outline_source_refs(
    outline_path: Path,
    target_nodes: list[dict[str, Any]],
    refs_by_target: dict[str, dict[str, list[str]]],
) -> None:
    lines, fine_indices, ordered_nodes = _legacy_nodes_in_outline_order(
        outline_path, target_nodes
    )
    for index, node in zip(fine_indices, ordered_nodes):
        visible, _ = parse_source_map_comment(lines[index])
        lines[index] = (
            visible.rstrip()
            + " "
            + _format_source_map_comment(refs_by_target[str(node["target_id"])])
        )
    outline_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def command_migrate_legacy_source_refs(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_target_path(project)
    payload = read_object(path, "旧目标成文脑图")
    if payload.get("gate_status") == "passed":
        raise ValueError("已封存目标脑图禁止走旧项目迁移")
    note = str(args.confirmation_note or "").strip()
    if len(note) < 12:
        raise ValueError("旧项目迁移必须记录人工复核说明")
    mappings = json.loads(json.dumps(payload.get("mappings") or {}))
    _apply_legacy_binding_overrides(mappings, args)
    refs_by_target = _source_refs_from_mappings(payload.get("target_nodes") or [], mappings)
    source_path, source = resolve_source_map(project, None)

    outline_path = project / "小节大纲.md"
    _, _, ordered_nodes = _legacy_nodes_in_outline_order(
        outline_path, payload.get("target_nodes") or []
    )
    preview_nodes = json.loads(json.dumps(ordered_nodes))
    for index, node in enumerate(preview_nodes, 1):
        node["sequence_index"] = index
    for node in preview_nodes:
        node["source_refs"] = refs_by_target[str(node["target_id"])]
    errors = validate_explicit_source_refs(preview_nodes, source)
    if errors:
        raise ValueError("旧项目迁移预检失败: " + " / ".join(errors))

    migrate_outline_source_refs(outline_path, payload["target_nodes"], refs_by_target)
    target_input, nodes = load_target_nodes(project, None)
    payload = rebind_target_map(payload, source_path, source, target_input, nodes)
    confirmation = payload.setdefault("manual_confirmation", {})
    confirmation["mapping_complete"] = True
    confirmation["note"] = note
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def command_audit_init(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    target_path = Path(args.input).resolve() if args.input else default_target_path(project)
    output = Path(args.output).resolve() if args.output else default_audit_path(project)
    target = read_object(target_path, "目标成文脑图")
    existing = read_object(output, "正文覆盖回执") if output.is_file() else None
    payload = create_audit(project, target_path, target, existing)
    write_json(output, payload)
    return payload, []


def _confirmed_audit_detail(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("preserved") is not True:
        raise ValueError(f"{label} 必须显式提交 preserved=true")
    quotes = value.get("evidence_quotes")
    conclusion = str(value.get("conclusion") or "").strip()
    if not isinstance(quotes, list) or not quotes or any(
        not isinstance(quote, str) or not quote.strip() for quote in quotes
    ):
        raise ValueError(f"{label} 缺少本字段专属正文逐字引句")
    if len(conclusion) < 8:
        raise ValueError(f"{label}.conclusion 必须写本字段专属判断")
    return {
        "preserved": True,
        "evidence_quotes": [quote.strip() for quote in quotes],
        "conclusion": conclusion,
    }


def _confirmed_audit_field_reviews(
    value: Any, fields: tuple[str, ...], label: str
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label} 必须按固定字段逐项完整提交")
    return {
        field: _confirmed_audit_detail(value[field], f"{label}.{field}")
        for field in fields
    }


def _apply_layer_audit_review(item: dict[str, Any], review: Any) -> None:
    layer_id = str(item["source_layer_id"])
    if not isinstance(review, dict):
        raise ValueError(f"{layer_id} 人工复核必须是对象")
    if review.get("realized") is not True or review.get("topology_preserved") is not True:
        raise ValueError(f"{layer_id} 必须显式提交 realized=true 与 topology_preserved=true")
    topology = _confirmed_audit_field_reviews(
        review.get("topology_reviews"),
        LAYER_AUDIT_TOPOLOGY_FIELDS,
        f"{layer_id}.topology_reviews",
    )
    raw_rules = review.get("preserve_rule_reviews")
    expected_indexes = [value["rule_index"] for value in item["preserve_rule_reviews"]]
    if not isinstance(raw_rules, list) or [
        value.get("rule_index") for value in raw_rules if isinstance(value, dict)
    ] != expected_indexes:
        raise ValueError(f"{layer_id}.preserve_rule_reviews 必须逐条同序提交")
    rules = []
    for raw in raw_rules:
        confirmed = _confirmed_audit_detail(
            raw, f"{layer_id}.preserve_rule_reviews[{raw['rule_index']}]"
        )
        rules.append({"rule_index": raw["rule_index"], **confirmed})
    raw_dimensions = review.get("dimension_reviews")
    expected_dimensions = tuple(SOURCE_MAP_VALIDATOR.DIMENSION_FIELDS)
    if not isinstance(raw_dimensions, dict) or set(raw_dimensions) != set(expected_dimensions):
        raise ValueError(f"{layer_id}.dimension_reviews 必须逐项提交来源六维")
    dimensions = {}
    for field in expected_dimensions:
        confirmed = _confirmed_audit_detail(
            raw_dimensions[field], f"{layer_id}.dimension_reviews.{field}"
        )
        dimensions[field] = {
            "source_status": item["dimension_reviews"][field]["source_status"],
            **confirmed,
        }
    conclusion = str(review.get("conclusion") or "").strip()
    if len(conclusion) < 12:
        raise ValueError(f"{layer_id} 人工结论不足 12 字")
    item["realized"] = True
    item["topology_preserved"] = True
    item["topology_reviews"] = topology
    item["preserve_rule_reviews"] = rules
    item["dimension_reviews"] = dimensions
    quotes = _all_detail_quotes(topology)
    for detail in rules:
        for quote in detail["evidence_quotes"]:
            if quote not in quotes:
                quotes.append(quote)
    for quote in _all_detail_quotes(dimensions):
        if quote not in quotes:
            quotes.append(quote)
    item["evidence_quotes"] = quotes
    item["conclusion"] = conclusion


def _apply_plot_audit_review(item: dict[str, Any], review: Any) -> None:
    beat_id = str(item["source_plot_id"])
    required_flags = (
        "function_preserved",
        "action_preserved",
        "control_change_preserved",
        "information_change_preserved",
        "consequence_preserved",
    )
    if not isinstance(review, dict) or any(review.get(field) is not True for field in required_flags):
        raise ValueError(f"{beat_id} 必须显式逐项提交五个 P 拍保真布尔")
    details = _confirmed_audit_field_reviews(
        review.get("field_reviews"), PLOT_AUDIT_FIELDS, f"{beat_id}.field_reviews"
    )
    conclusion = str(review.get("conclusion") or "").strip()
    if len(conclusion) < 12:
        raise ValueError(f"{beat_id} P 拍功能结论不足 12 字")
    for field in required_flags:
        item[field] = True
    item["field_reviews"] = details
    item["evidence_quotes"] = _all_detail_quotes(details)
    item["conclusion"] = conclusion


def _apply_emotion_audit_review(item: dict[str, Any], review: Any) -> None:
    beat_id = str(item["source_emotion_id"])
    required_flags = tuple(f"{field}_preserved" for field in EMOTION_AUDIT_FIELDS)
    if (
        not isinstance(review, dict)
        or any(review.get(field) is not True for field in required_flags)
        or review.get("whole_beat_in_one_node") is not True
    ):
        raise ValueError(f"{beat_id} 必须显式提交 E 拍五字段保真及 whole_beat_in_one_node=true")
    details = _confirmed_audit_field_reviews(
        review.get("field_reviews"), EMOTION_AUDIT_FIELDS, f"{beat_id}.field_reviews"
    )
    conclusion = str(review.get("conclusion") or "").strip()
    if len(conclusion) < 12:
        raise ValueError(f"{beat_id} E 拍功能结论不足 12 字")
    for field in required_flags:
        item[field] = True
    item["whole_beat_in_one_node"] = True
    item["field_reviews"] = details
    item["evidence_quotes"] = _all_detail_quotes(details)
    item["conclusion"] = conclusion


def command_audit_confirm(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    reviews = _parse_json_argument_or_file(
        args.reviews_json,
        getattr(args, "reviews_json_file", None),
        "reviews-json",
    )
    audit_reviews = payload.get("layer_reviews") or []
    expected_ids = [str(item.get("source_layer_id") or "") for item in audit_reviews]
    if list(reviews) != expected_ids:
        raise ValueError("reviews-json 必须与来源层同序全量对应")
    for item in audit_reviews:
        layer_id = str(item["source_layer_id"])
        _apply_layer_audit_review(item, reviews[layer_id])
    node_reviews_json = getattr(args, "node_reviews_json", "{}")
    node_reviews = _parse_json_argument_or_file(
        node_reviews_json,
        getattr(args, "node_reviews_json_file", None),
        "node-reviews-json",
    )
    if node_reviews:
        audit_nodes = payload.get("node_reviews") or []
        expected_node_ids = [str(item.get("target_node_id") or "") for item in audit_nodes]
        if list(node_reviews) != expected_node_ids:
            raise ValueError("node-reviews-json 必须与目标节点同序全量对应")
        for item in audit_nodes:
            target_id = str(item["target_node_id"])
            review = node_reviews[target_id]
            if not isinstance(review, dict):
                raise ValueError(f"{target_id} 节点复核必须是对象")
            quotes = review.get("evidence_quotes")
            conclusion = str(review.get("conclusion") or "").strip()
            if not isinstance(quotes, list) or not quotes or any(
                not isinstance(quote, str) or not quote.strip() for quote in quotes
            ):
                raise ValueError(f"{target_id} 缺少人工逐字引句")
            if len(conclusion) < 12:
                raise ValueError(f"{target_id} 节点结论不足 12 字")
            item["realized"] = True
            item["granularity_preserved"] = True
            item["evidence_quotes"] = [quote.strip() for quote in quotes]
            item["conclusion"] = conclusion
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def command_audit_confirm_nodes(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    reviews = _parse_json_argument_or_file(
        args.reviews_json,
        getattr(args, "reviews_json_file", None),
        "reviews-json",
    )
    audit_nodes = payload.get("node_reviews") or []
    by_id = {
        str(item.get("target_node_id") or ""): item
        for item in audit_nodes
        if isinstance(item, dict)
    }
    unknown = [target_id for target_id in reviews if target_id not in by_id]
    if unknown:
        raise ValueError(f"reviews-json 包含未知目标节点: {unknown}")
    if not reviews:
        raise ValueError("reviews-json 至少包含一个目标节点")
    for target_id, review in reviews.items():
        if not isinstance(review, dict):
            raise ValueError(f"{target_id} 节点复核必须是对象")
        quotes = review.get("evidence_quotes")
        conclusion = str(review.get("conclusion") or "").strip()
        if not isinstance(quotes, list) or not quotes or any(
            not isinstance(quote, str) or not quote.strip() for quote in quotes
        ):
            raise ValueError(f"{target_id} 缺少人工逐字引句")
        if len(conclusion) < 12:
            raise ValueError(f"{target_id} 节点结论不足 12 字")
        item = by_id[target_id]
        item["realized"] = True
        item["granularity_preserved"] = True
        item["evidence_quotes"] = [quote.strip() for quote in quotes]
        item["conclusion"] = conclusion
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def command_audit_confirm_layers(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    reviews = _parse_json_argument_or_file(
        args.reviews_json,
        getattr(args, "reviews_json_file", None),
        "reviews-json",
    )
    audit_layers = payload.get("layer_reviews") or []
    by_id = {
        str(item.get("source_layer_id") or ""): item
        for item in audit_layers
        if isinstance(item, dict)
    }
    unknown = [layer_id for layer_id in reviews if layer_id not in by_id]
    if unknown:
        raise ValueError(f"reviews-json 包含未知来源层: {unknown}")
    if not reviews:
        raise ValueError("reviews-json 至少包含一个来源层")
    for layer_id, review in reviews.items():
        item = by_id[layer_id]
        _apply_layer_audit_review(item, review)
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def command_audit_confirm_plots(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    reviews = _parse_json_argument_or_file(
        args.reviews_json,
        getattr(args, "reviews_json_file", None),
        "reviews-json",
    )
    audit_plots = payload.get("plot_reviews") or []
    by_id = {
        str(item.get("source_plot_id") or ""): item
        for item in audit_plots
        if isinstance(item, dict)
    }
    unknown = [beat_id for beat_id in reviews if beat_id not in by_id]
    if unknown:
        raise ValueError(f"reviews-json 包含未知来源 P 拍: {unknown}")
    if not reviews:
        raise ValueError("reviews-json 至少包含一个来源 P 拍")
    for beat_id, review in reviews.items():
        item = by_id[beat_id]
        _apply_plot_audit_review(item, review)
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def command_audit_confirm_emotions(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    reviews = _parse_json_argument_or_file(
        args.reviews_json,
        getattr(args, "reviews_json_file", None),
        "reviews-json",
    )
    audit_emotions = payload.get("emotion_reviews") or []
    by_id = {
        str(item.get("source_emotion_id") or ""): item
        for item in audit_emotions
        if isinstance(item, dict)
    }
    unknown = [beat_id for beat_id in reviews if beat_id not in by_id]
    if unknown:
        raise ValueError(f"reviews-json 包含未知来源 E 拍: {unknown}")
    if not reviews:
        raise ValueError("reviews-json 至少包含一个来源 E 拍")
    for beat_id, review in reviews.items():
        _apply_emotion_audit_review(by_id[beat_id], review)
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def command_audit_confirm_compact(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    bindings = payload.get("bindings") or {}
    source = read_object(Path(bindings["source_map"]["path"]), "来源成文脑图")
    target = read_object(Path(bindings["target_map"]["path"]), "目标成文脑图")
    draft_text = (project / "正文.md").read_text(encoding="utf-8")
    regions = audit_draft_regions(draft_text)
    source_layers = {
        str(item["layer_id"]): item
        for item in source.get("layers") or []
        if isinstance(item, dict)
    }
    target_nodes = {
        str(item["target_id"]): item
        for item in target.get("target_nodes") or []
        if isinstance(item, dict)
    }
    layer_mapping = {
        str(item["source_id"]): item
        for item in target.get("mappings", {}).get("layers") or []
        if isinstance(item, dict)
    }

    region_reviews = _parse_json_argument_or_file(
        getattr(args, "region_reviews_json", "{}"),
        getattr(args, "region_reviews_json_file", None),
        "region-reviews-json",
    )
    full_reviews = _parse_json_argument_or_file(
        args.reviews_json,
        getattr(args, "reviews_json_file", None),
        "compact-reviews-json",
    )
    if region_reviews and full_reviews:
        raise ValueError("不得同时提交 region-reviews-json 和 compact-reviews-json")

    if region_reviews:
        expected_regions = list(
            dict.fromkeys(
                [str(item["region_id"]) for item in target.get("target_nodes") or []]
                + [
                    str(region_id)
                    for item in target.get("mappings", {}).get("layers") or []
                    for target_id in item.get("target_node_ids") or []
                    for region_id in [
                        next(
                            (
                                str(node["region_id"])
                                for node in target.get("target_nodes") or []
                                if str(node.get("target_id")) == str(target_id)
                            ),
                            "",
                        )
                    ]
                ]
            )
        )
        if list(region_reviews) != expected_regions:
            raise ValueError(
                "region-reviews-json 必须覆盖目标脑图出现的全部区域并保持首次出现顺序"
            )
        for region_id, raw in region_reviews.items():
            if not isinstance(raw, dict):
                raise ValueError(f"{region_id} 区域复核必须是对象")
            allowed_text = regions.get(region_id, "")
            region_errors: list[str] = []
            _validate_compact_evidence(
                raw, region_id, allowed_text, region_errors
            )
            if region_errors:
                raise ValueError(" / ".join(region_errors))
        node_inputs = {}
        for target_id, node in target_nodes.items():
            region_id = str(node["region_id"])
            raw = region_reviews[region_id]
            node_inputs[target_id] = {
                "realized": True,
                "granularity_preserved": True,
                "evidence_quotes": list(raw["evidence_quotes"]),
                "conclusion": f"{target_id} 在 {region_id} 的正文区域中完成目标节点承接：{raw['conclusion']}",
            }
        layer_inputs = {}
        for layer_id, mapping in layer_mapping.items():
            target_regions = list(
                dict.fromkeys(
                    target_nodes[target_id]["region_id"]
                    for target_id in mapping["target_node_ids"]
                    if target_id in target_nodes
                )
            )
            quotes = []
            conclusions = []
            for region_id in target_regions:
                raw = region_reviews[region_id]
                for quote in raw["evidence_quotes"]:
                    if quote not in quotes:
                        quotes.append(quote)
                conclusions.append(str(raw["conclusion"]).strip())
            layer_inputs[layer_id] = {
                "realized": True,
                "topology_preserved": True,
                "evidence_quotes": quotes,
                "conclusion": f"{layer_id} 按来源层序和目标区域连续承接：{'；'.join(conclusions)}",
            }
        plot_inputs = {}
        for mapping in target.get("mappings", {}).get("plot_beats") or []:
            beat_id = str(mapping.get("source_id") or "")
            target_id = str(mapping.get("target_id") or "")
            region_id = str((target_nodes.get(target_id) or {}).get("region_id") or "")
            raw = region_reviews[region_id]
            plot_inputs[beat_id] = {
                "function_preserved": True,
                "action_preserved": True,
                "control_change_preserved": True,
                "information_change_preserved": True,
                "consequence_preserved": True,
                "field_reviews": {
                    field: {
                        "preserved": True,
                        "evidence_quotes": list(raw["evidence_quotes"]),
                        "conclusion": (
                            f"{beat_id}.{field} 在 {region_id} 的正文证据中完成："
                            f"{raw['conclusion']}"
                        ),
                    }
                    for field in PLOT_AUDIT_FIELDS
                },
                "conclusion": f"{beat_id} 在 {region_id} 完成逐项 P 拍承重：{raw['conclusion']}",
            }
        emotion_inputs = {}
        for mapping in target.get("mappings", {}).get("emotion_beats") or []:
            beat_id = str(mapping.get("source_id") or "")
            target_id = str(mapping.get("target_id") or "")
            region_id = str((target_nodes.get(target_id) or {}).get("region_id") or "")
            raw = region_reviews[region_id]
            emotion_inputs[beat_id] = {
                **{
                    f"{field}_preserved": True
                    for field in EMOTION_AUDIT_FIELDS
                },
                "whole_beat_in_one_node": True,
                "field_reviews": {
                    field: {
                        "preserved": True,
                        "evidence_quotes": list(raw["evidence_quotes"]),
                        "conclusion": (
                            f"{beat_id}.{field} 在 {region_id} 的单一节点证据中完成："
                            f"{raw['conclusion']}"
                        ),
                    }
                    for field in EMOTION_AUDIT_FIELDS
                },
                "conclusion": f"{beat_id} 在 {region_id} 完成整拍 E 保真：{raw['conclusion']}",
            }
        full_reviews = {
            "layers": layer_inputs,
            "nodes": node_inputs,
            "plots": plot_inputs,
            "emotions": emotion_inputs,
        }

    reviews = full_reviews
    if set(reviews) != {"layers", "nodes", "plots", "emotions"}:
        raise ValueError(
            "compact-reviews-json 顶层必须只有 layers、nodes、plots 和 emotions"
        )

    layer_inputs = reviews["layers"]
    if not isinstance(layer_inputs, dict) or list(layer_inputs) != list(source_layers):
        raise ValueError("compact layers 必须与来源文字层同序全量对应")
    compact_layers = []
    for layer_id, raw in layer_inputs.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{layer_id} compact 复核必须是对象")
        mapping = layer_mapping[layer_id]
        target_ids = [str(value) for value in mapping["target_node_ids"]]
        target_regions = list(
            dict.fromkeys(
                target_nodes[value]["region_id"]
                for value in target_ids
                if value in target_nodes
            )
        )
        item = {
            "source_layer_id": layer_id,
            "source_content_sha256": source_layers[layer_id]["content_sha256"],
            "target_node_ids": target_ids,
            "target_regions": target_regions,
            "realized": raw.get("realized"),
            "topology_preserved": raw.get("topology_preserved"),
            "evidence_quotes": raw.get("evidence_quotes"),
            "conclusion": str(raw.get("conclusion") or "").strip(),
        }
        compact_layers.append(item)

    node_inputs = reviews["nodes"]
    if not isinstance(node_inputs, dict) or list(node_inputs) != list(target_nodes):
        raise ValueError("compact nodes 必须与目标节点同序全量对应")
    compact_nodes = []
    for target_id, raw in node_inputs.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{target_id} compact 复核必须是对象")
        node = target_nodes[target_id]
        compact_nodes.append(
            {
                "target_node_id": target_id,
                "source_refs": node["source_refs"],
                "target_region": node["region_id"],
                "realized": raw.get("realized"),
                "granularity_preserved": raw.get("granularity_preserved"),
                "evidence_quotes": raw.get("evidence_quotes"),
                "conclusion": str(raw.get("conclusion") or "").strip(),
            }
        )

    plot_inputs = reviews["plots"]
    audit_plots = payload.get("plot_reviews") or []
    plot_by_id = {
        str(item.get("source_plot_id") or ""): item
        for item in audit_plots
        if isinstance(item, dict)
    }
    if not isinstance(plot_inputs, dict) or list(plot_inputs) != list(plot_by_id):
        raise ValueError("compact plots 必须与来源 P 拍同序全量对应")
    for beat_id, review in plot_inputs.items():
        _apply_plot_audit_review(plot_by_id[beat_id], review)

    emotion_inputs = reviews["emotions"]
    audit_emotions = payload.get("emotion_reviews") or []
    emotion_by_id = {
        str(item.get("source_emotion_id") or ""): item
        for item in audit_emotions
        if isinstance(item, dict)
    }
    if not isinstance(emotion_inputs, dict) or list(emotion_inputs) != list(emotion_by_id):
        raise ValueError("compact emotions 必须与来源 E 拍同序全量对应")
    for beat_id, review in emotion_inputs.items():
        _apply_emotion_audit_review(emotion_by_id[beat_id], review)

    payload["audit_mode"] = "compact_v1"
    payload["layer_reviews"] = compact_layers
    payload["node_reviews"] = compact_nodes
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    errors = validate_compact_audit_payload(
        payload, project, source, target, draft_text, regions
    )
    if errors:
        return payload, errors
    write_json(path, payload)
    return payload, []


def command_audit_seal(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    errors = validate_audit(payload, project, require_gate=False)
    payload["gate_status"] = "passed" if not errors else "blocked"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser(
        "preflight", help="在初始化前校验细纲 P/E/SF/层全颗粒来源声明"
    )
    preflight.add_argument("--project-dir", required=True)
    preflight.add_argument("--source-map")
    preflight.add_argument("--mind-map")
    preflight.add_argument(
        "--allow-partial",
        action="store_true",
        help="只校验当前已落盘来源连续前缀，缺少后续来源项不阻断",
    )
    preflight.add_argument("--dimensions-json", default="{}")
    preflight.add_argument("--layer-anchors-json", default="{}")
    init = subparsers.add_parser("init", help="初始化目标成文脑图")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--source-map")
    init.add_argument("--mind-map")
    init.add_argument("--output")
    init.add_argument("--force", action="store_true")
    init.add_argument("--dimensions-json", default="{}")
    init.add_argument("--layer-anchors-json", default="{}")
    init.add_argument("--derive-emotions-from-outline", action="store_true")
    validate = subparsers.add_parser("validate", help="校验并封存目标成文脑图")
    validate.add_argument("--project-dir", required=True)
    validate.add_argument("--input")
    rebind = subparsers.add_parser("rebind", help="按内容哈希增量重绑")
    rebind.add_argument("--project-dir", required=True)
    rebind.add_argument("--input")
    rebind.add_argument("--source-map")
    rebind.add_argument("--mind-map")
    confirm_shells = subparsers.add_parser(
        "confirm-event-shells", help="确认全部 P 拍事件壳替换，不改来源映射"
    )
    confirm_shells.add_argument("--project-dir", required=True)
    confirm_shells.add_argument("--input")
    confirm_shells.add_argument("--reviews-json", default="{}")
    confirm_shells.add_argument("--dimensions-json", default="{}")
    confirm_fidelity = subparsers.add_parser(
        "confirm-fidelity",
        help="在正文前逐 E 拍和逐文字层确认完整语义与拓扑保真",
    )
    confirm_fidelity.add_argument("--project-dir", required=True)
    confirm_fidelity.add_argument("--input")
    confirm_fidelity.add_argument("--emotion-reviews-json", default="{}")
    confirm_fidelity.add_argument("--layer-reviews-json", default="{}")
    confirm_fidelity.add_argument("--layer-anchors-json", default="{}")
    confirm_fidelity.add_argument(
        "--derive-emotions-from-outline", action="store_true"
    )
    migrate_legacy = subparsers.add_parser(
        "migrate-legacy-source-refs",
        help="仅将修复前已启动项目的人工旧绑定迁入细纲 source-map 声明",
    )
    migrate_legacy.add_argument("--project-dir", required=True)
    migrate_legacy.add_argument("--input")
    migrate_legacy.add_argument("--plot-overrides-json", default="{}")
    migrate_legacy.add_argument("--emotion-overrides-json", default="{}")
    migrate_legacy.add_argument("--subflow-overrides-json", default="{}")
    migrate_legacy.add_argument("--layer-overrides-json", default="{}")
    migrate_legacy.add_argument("--confirmation-note", required=True)
    audit_init = subparsers.add_parser("audit-init", help="初始化或刷新紧凑正文覆盖回执")
    audit_init.add_argument("--project-dir", required=True)
    audit_init.add_argument("--input", help="目标成文脑图路径")
    audit_init.add_argument("--output")
    audit_confirm = subparsers.add_parser(
        "audit-confirm", help="应用审阅者明确提供的全量逐层正文引句与结论"
    )
    audit_confirm.add_argument("--project-dir", required=True)
    audit_confirm.add_argument("--input", help="正文覆盖回执路径")
    audit_confirm.add_argument("--reviews-json", default="{}")
    audit_confirm.add_argument(
        "--reviews-json-file",
        help="从文件或 /dev/stdin 读取逐层正文复核 JSON",
    )
    audit_confirm.add_argument(
        "--node-reviews-json",
        help="按目标节点顺序提供逐节点正文引句与颗粒度结论",
    )
    audit_confirm.add_argument(
        "--node-reviews-json-file",
        help="从文件或 /dev/stdin 读取逐节点正文复核 JSON",
    )
    audit_confirm_nodes = subparsers.add_parser(
        "audit-confirm-nodes", help="增量应用人工明确提供的目标节点正文引句与颗粒度结论"
    )
    audit_confirm_nodes.add_argument("--project-dir", required=True)
    audit_confirm_nodes.add_argument("--input", help="正文覆盖回执路径")
    audit_confirm_nodes.add_argument("--reviews-json", required=True)
    audit_confirm_layers = subparsers.add_parser(
        "audit-confirm-layers", help="增量应用人工明确提供的来源层正文引句与拓扑结论"
    )
    audit_confirm_layers.add_argument("--project-dir", required=True)
    audit_confirm_layers.add_argument("--input", help="正文覆盖回执路径")
    audit_confirm_layers.add_argument("--reviews-json", required=True)
    audit_confirm_plots = subparsers.add_parser(
        "audit-confirm-plots",
        help="增量应用人工逐 P 拍 action/control/information/consequence 保真结论",
    )
    audit_confirm_plots.add_argument("--project-dir", required=True)
    audit_confirm_plots.add_argument("--input", help="正文覆盖回执路径")
    audit_confirm_plots.add_argument("--reviews-json", default="{}")
    audit_confirm_plots.add_argument(
        "--reviews-json-file",
        help="从文件或 /dev/stdin 读取逐 P 拍复核 JSON",
    )
    audit_confirm_emotions = subparsers.add_parser(
        "audit-confirm-emotions",
        help="增量应用人工逐 E 拍五字段语义保真结论",
    )
    audit_confirm_emotions.add_argument("--project-dir", required=True)
    audit_confirm_emotions.add_argument("--input", help="正文覆盖回执路径")
    audit_confirm_emotions.add_argument("--reviews-json", default="{}")
    audit_confirm_emotions.add_argument(
        "--reviews-json-file",
        help="从文件或 /dev/stdin 读取逐 E 拍复核 JSON",
    )
    audit_confirm_compact = subparsers.add_parser(
        "audit-confirm-compact",
        help="应用逐节点与逐来源层的紧凑正文证据",
    )
    audit_confirm_compact.add_argument("--project-dir", required=True)
    audit_confirm_compact.add_argument("--input", help="正文覆盖回执路径")
    audit_confirm_compact.add_argument("--reviews-json", default="{}")
    audit_confirm_compact.add_argument(
        "--reviews-json-file",
        help="从文件或 /dev/stdin 读取 compact reviews JSON",
    )
    audit_confirm_compact.add_argument("--region-reviews-json", default="{}")
    audit_confirm_compact.add_argument(
        "--region-reviews-json-file",
        help="从文件或 /dev/stdin 读取逐区域正文证据 JSON",
    )
    audit_seal = subparsers.add_parser("audit-seal", help="校验并封存紧凑正文覆盖回执")
    audit_seal.add_argument("--project-dir", required=True)
    audit_seal.add_argument("--input", help="正文覆盖回执路径")
    args = parser.parse_args()
    commands = {
        "preflight": command_preflight,
        "init": command_init,
        "validate": command_validate,
        "rebind": command_rebind,
        "confirm-event-shells": command_confirm_event_shells,
        "confirm-fidelity": command_confirm_fidelity,
        "migrate-legacy-source-refs": command_migrate_legacy_source_refs,
        "audit-init": command_audit_init,
        "audit-confirm": command_audit_confirm,
        "audit-confirm-nodes": command_audit_confirm_nodes,
        "audit-confirm-layers": command_audit_confirm_layers,
        "audit-confirm-plots": command_audit_confirm_plots,
        "audit-confirm-emotions": command_audit_confirm_emotions,
        "audit-confirm-compact": command_audit_confirm_compact,
        "audit-seal": command_audit_seal,
    }
    try:
        payload, errors = commands[args.command](args)
    except (OSError, ValueError, FileNotFoundError, KeyError) as exc:
        payload, errors = {}, [str(exc)]
    result = {
        "ok": not errors,
        "command": args.command,
        "gate_status": payload.get("gate_status"),
        "invalidated": (payload.get("incremental_state") or {}).get("invalidated", []),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
