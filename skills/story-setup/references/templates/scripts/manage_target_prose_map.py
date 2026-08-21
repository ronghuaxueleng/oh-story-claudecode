#!/usr/bin/env python3
"""Manage target prose maps, incremental rebinding, and compact draft audits."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Callable


TARGET_SCHEMA = "story-short-write.target-prose-map.v1"
AUDIT_SCHEMA = "story-short-write.prose-coverage-audit.v2"
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


def parse_outline(outline_path: Path) -> dict[str, Any]:
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
    numeric_count = sum(
        1 for item in regions if item["region_id"].startswith("section:")
    )
    expected = ["opening"] + [
        f"section:{index}" for index in range(1, numeric_count + 1)
    ] + ["epilogue"]
    actual = [item["region_id"] for item in regions]
    if actual != expected:
        errors.append(f"细纲区域必须为导语、连续数字节、尾声: {actual}")
    return {"regions": regions, "errors": errors}


def _outline_nodes(outline: Path) -> list[dict[str, Any]]:
    catalog = parse_outline(outline)
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


def load_target_nodes(project_dir: Path, mind_map: Path | None) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if mind_map is not None:
        path = mind_map.expanduser().resolve()
        return {"kind": "mind_map", **binding(path)}, _mind_map_nodes(path)
    path = project_dir / "小节大纲.md"
    return {"kind": "outline", **binding(path)}, _outline_nodes(path)


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
        "adaptation_decision": "",
        "human_confirmed": False,
    }


def validate_explicit_source_refs(
    target_nodes: list[dict[str, Any]], source: dict[str, Any]
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
    if missing_steps:
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
    if missing_layers:
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
        "manual_confirmation": {
            "mapping_complete": True,
            "event_shell_replacements_confirmed": False,
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
            if len(str(item.get("adaptation_decision") or "").strip()) < 4:
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
    explicit_mappings = explicit_source_ref_mappings(target_nodes, source)
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
    payload["source_map"] = {
        **binding(source_path),
        "content_sha256": source["content_sha256"],
    }
    payload["target_input"] = target_input
    payload["target_nodes"] = target_nodes
    payload["mappings"] = explicit_mappings
    payload["event_shell_replacements"] = replacements
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
    payload["incremental_state"] = {
        "invalidated": sorted(event_shell_invalidations)
    }
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    return payload


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
            for field in ("realized", "topology_preserved", "evidence_quotes", "conclusion"):
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
                "evidence_quotes",
                "conclusion",
            ):
                base[field] = old.get(field)
        plot_reviews.append(base)
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
    source_layers = {item["layer_id"]: item for item in source.get("layers") or []}
    layer_mapping = {
        item["source_id"]: item for item in target["mappings"]["layers"]
    }
    node_regions = {
        item["target_id"]: item["region_id"] for item in target["target_nodes"]
    }
    target_nodes = {item["target_id"]: item for item in target["target_nodes"]}
    source_plots = {item["beat_id"]: item for item in source.get("plot_beats") or []}
    plot_mapping = {
        item["source_id"]: item for item in target["mappings"]["plot_beats"]
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
            quotes = item.get("evidence_quotes")
            if not isinstance(quotes, list) or not quotes:
                errors.append(f"{layer_id} 缺少正文逐字引句")
            else:
                allowed_text = "\n".join(
                    regions.get(region_id, "") for region_id in item.get("target_regions") or []
                )
                for quote in quotes:
                    if not isinstance(quote, str) or not quote.strip() or quote not in allowed_text:
                        errors.append(f"{layer_id} 引句不在绑定的正文区域内: {quote!r}")
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
            quotes = item.get("evidence_quotes")
            if not isinstance(quotes, list) or not quotes:
                errors.append(f"{beat_id} 缺少正文逐字引句")
            else:
                allowed_text = regions.get(expected_region, "")
                for quote in quotes:
                    if not isinstance(quote, str) or not quote.strip() or quote not in allowed_text:
                        errors.append(f"{beat_id} 引句不在绑定正文区域内: {quote!r}")
            if len(str(item.get("conclusion") or "").strip()) < 12:
                errors.append(f"{beat_id} P 拍功能结论不足 12 字")
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


def default_target_path(project_dir: Path) -> Path:
    return project_dir / "写作资产" / "目标成文脑图.json"


def default_audit_path(project_dir: Path) -> Path:
    return project_dir / "写作资产" / "正文覆盖回执.json"


def command_preflight(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    source_path, source = resolve_source_map(
        project, Path(args.source_map).resolve() if args.source_map else None
    )
    target_input, nodes = load_target_nodes(
        project, Path(args.mind_map).resolve() if args.mind_map else None
    )
    errors = validate_explicit_source_refs(nodes, source)
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
    note = str(args.confirmation_note or "").strip()
    if len(note) < 12:
        raise ValueError("confirm-event-shells 必须记录本书专属人工复核说明")
    dimensions = [item.strip() for item in args.dimensions.split(",") if item.strip()]
    if len(set(dimensions)) < 3 or set(dimensions) - REPLACEMENT_DIMENSIONS:
        raise ValueError("dimensions 至少包含三个合法换壳维度")
    evidence = {
        str(item.get("target_id") or ""): str(item.get("evidence") or "").strip()
        for item in payload.get("target_nodes") or []
    }
    target_by_source = {
        str(item["source_id"]): str(item["target_id"])
        for item in payload["mappings"]["plot_beats"]
    }
    for replacement in payload.get("event_shell_replacements") or []:
        source_id = str(replacement["source_id"])
        target_id = target_by_source[source_id]
        replacement["dimensions_changed"] = list(dimensions)
        replacement["adaptation_decision"] = (
            f"人工确认 {source_id} 已换芯到 {target_id}：{evidence[target_id]} {note}"
        )
        replacement["human_confirmed"] = True
    confirmation = payload.setdefault("manual_confirmation", {})
    confirmation["mapping_complete"] = True
    confirmation["event_shell_replacements_confirmed"] = True
    confirmation["note"] = note
    invalidated = (payload.get("incremental_state") or {}).get("invalidated") or []
    payload["incremental_state"] = {
        "invalidated": [
            item for item in invalidated if not str(item).endswith(".event_shell_replacement")
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


def command_audit_confirm(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    reviews = _parse_json_argument(args.reviews_json, "reviews-json")
    audit_reviews = payload.get("layer_reviews") or []
    expected_ids = [str(item.get("source_layer_id") or "") for item in audit_reviews]
    if list(reviews) != expected_ids:
        raise ValueError("reviews-json 必须与来源层同序全量对应")
    for item in audit_reviews:
        layer_id = str(item["source_layer_id"])
        review = reviews[layer_id]
        if not isinstance(review, dict):
            raise ValueError(f"{layer_id} 人工复核必须是对象")
        quotes = review.get("evidence_quotes")
        conclusion = str(review.get("conclusion") or "").strip()
        if not isinstance(quotes, list) or not quotes or any(
            not isinstance(quote, str) or not quote.strip() for quote in quotes
        ):
            raise ValueError(f"{layer_id} 缺少人工逐字引句")
        if len(conclusion) < 12:
            raise ValueError(f"{layer_id} 人工结论不足 12 字")
        item["realized"] = True
        item["topology_preserved"] = True
        item["evidence_quotes"] = [quote.strip() for quote in quotes]
        item["conclusion"] = conclusion
    node_reviews_json = getattr(args, "node_reviews_json", None)
    if node_reviews_json:
        node_reviews = _parse_json_argument(node_reviews_json, "node-reviews-json")
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
    reviews = _parse_json_argument(args.reviews_json, "reviews-json")
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
    reviews = _parse_json_argument(args.reviews_json, "reviews-json")
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
        if not isinstance(review, dict):
            raise ValueError(f"{layer_id} 人工复核必须是对象")
        quotes = review.get("evidence_quotes")
        conclusion = str(review.get("conclusion") or "").strip()
        if not isinstance(quotes, list) or not quotes or any(
            not isinstance(quote, str) or not quote.strip() for quote in quotes
        ):
            raise ValueError(f"{layer_id} 缺少人工逐字引句")
        if len(conclusion) < 12:
            raise ValueError(f"{layer_id} 人工结论不足 12 字")
        item = by_id[layer_id]
        item["realized"] = True
        item["topology_preserved"] = True
        item["evidence_quotes"] = [quote.strip() for quote in quotes]
        item["conclusion"] = conclusion
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
    write_json(path, payload)
    return payload, []


def command_audit_confirm_plots(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    project = Path(args.project_dir).resolve()
    path = Path(args.input).resolve() if args.input else default_audit_path(project)
    payload = read_object(path, "正文覆盖回执")
    reviews = _parse_json_argument(args.reviews_json, "reviews-json")
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
        if not isinstance(review, dict):
            raise ValueError(f"{beat_id} P 拍复核必须是对象")
        quotes = review.get("evidence_quotes")
        conclusion = str(review.get("conclusion") or "").strip()
        if not isinstance(quotes, list) or not quotes or any(
            not isinstance(quote, str) or not quote.strip() for quote in quotes
        ):
            raise ValueError(f"{beat_id} 缺少人工逐字引句")
        if len(conclusion) < 12:
            raise ValueError(f"{beat_id} P 拍功能结论不足 12 字")
        item = by_id[beat_id]
        item["function_preserved"] = True
        item["action_preserved"] = True
        item["control_change_preserved"] = True
        item["information_change_preserved"] = True
        item["consequence_preserved"] = True
        item["evidence_quotes"] = [quote.strip() for quote in quotes]
        item["conclusion"] = conclusion
    payload["gate_status"] = "pending"
    payload["content_sha256"] = content_hash(payload)
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
    init = subparsers.add_parser("init", help="初始化目标成文脑图")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--source-map")
    init.add_argument("--mind-map")
    init.add_argument("--output")
    init.add_argument("--force", action="store_true")
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
    confirm_shells.add_argument("--dimensions", required=True)
    confirm_shells.add_argument("--confirmation-note", required=True)
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
    audit_confirm.add_argument("--reviews-json", required=True)
    audit_confirm.add_argument(
        "--node-reviews-json",
        help="按目标节点顺序提供逐节点正文引句与颗粒度结论",
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
    audit_confirm_plots.add_argument("--reviews-json", required=True)
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
        "migrate-legacy-source-refs": command_migrate_legacy_source_refs,
        "audit-init": command_audit_init,
        "audit-confirm": command_audit_confirm,
        "audit-confirm-nodes": command_audit_confirm_nodes,
        "audit-confirm-layers": command_audit_confirm_layers,
        "audit-confirm-plots": command_audit_confirm_plots,
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
