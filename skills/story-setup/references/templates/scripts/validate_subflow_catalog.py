#!/usr/bin/env python3
"""Validate the source-layer topology used by short-story writing.

The catalog is authored during analysis.  This validator deliberately checks
source identity, layer partitioning, narrative-mode topology, and per-layer
language realization.  It does not infer missing prose guidance or accept
summary-only substitutes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "story-short-analyze.subflow-catalog.v2"
SOURCE_LINE_RANGE_RE = re.compile(r"L?(\d+)\s*[-~至]\s*L?(\d+)", re.IGNORECASE)
SOURCE_SECTION_MARKER_RE = re.compile(
    r"\s*\d+(?:[.、．])?(?:\s*[【\[][^】\]\r\n]{1,20}[】\]])?\s*"
)
BOOK_METADATA_LINE_RE = re.compile(
    r"^\s*(?:"
    r"[(（]?全文完[)）]?"
    r"|[【\[]\s*(?:全文)?完(?:结)?\s*[】\]]"
    r"|备案号\s*[:：]"
    r"|[-—_=~·•*]{2,}\s*[(（]?已完结[)）]?\s*[-—_=~·•*]{2,}"
    r")\s*",
    re.IGNORECASE,
)
OUTER_PUNCTUATION_LINES = {"!", "！", "?", "？"}

LANGUAGE_DIMENSIONS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)

LAYER_MODES = {
    "opening_compression",
    "live_scene",
    "compressed_scene",
    "memory_exposition",
    "summary_transition",
    "time_jump",
    "public_discourse",
    "institutional_result",
    "narrator_interjection",
    "rumor_afterword",
    "cold_afterword",
}

LAYER_TEXT_FIELDS = (
    "layer_role",
    "entry_relation",
    "exit_relation",
    "narrative_distance",
)

GENERIC_LAYER_TEXT = {
    "layer_role": "该层承接本段原文的叙事换挡与动作/信息推进。",
    "entry_relation": "承接前一层已建立的场景、关系或信息状态。",
    "exit_relation": "把本层新增动作、信息或情绪压力交给下一层。",
    "narrative_distance": "贴近叙述者的现场感知，必要处短暂拉开作压缩或回叙。",
}

GENERIC_SUBFLOW_TEXT = {
    "entry_state": "承接前文已建立的叙事状态。",
    "end_state": "把该段事实、动作和情绪状态交给后续正式桥段。",
    "information_delay": "不提前解释后文信息。",
}

REPETITIVE_LAYER_TEXT_PATTERNS = {
    "layer_role": (r"^本层通过.+独立完成[‘“\"]?.+[’”\"]?的叙事任务[。.]?$",),
    "entry_relation": (r"^由上一层.+留下的后果推进到本层$",),
    "exit_relation": (r"^以.+迫使叙事换挡到下一层$",),
    "narrative_distance": (
        r"^贴近.+当下所见所听，以动作、话轮和身体反应同步推进[。.]?$",
        r"^从第一人称当前感受拉远到压缩回叙或时间跨越，再在结果处贴回现场[。.]?$",
    ),
}

# These sentence frames are invalid even when they occur in only one layer.
# Quoting a different source phrase does not turn the same generic mechanism
# into layer-specific analysis.
FORBIDDEN_LAYER_SCAFFOLD_PATTERNS = {
    "layer_role": (
        r"^本层围绕<Q>完成关系换权，把可见动作转成关系或信息变化[。.]?$",
        r"^本层围绕<Q>完成.+把可见动作转成关系或信息变化[。.]?$",
        r"^.+从<Q>起势并在<Q>落果，本层承重对象为.+$",
        r"^<Q>先占住叙事焦点，<Q>随即改变本场还能怎样继续$",
    ),
    "entry_relation": (
        r"^<Q>把前一场遗留的压力落实为眼前动作，人物先看见或承受，随后才作回应[。.]?$",
        r"^前态留下的缺口由<Q>打开[。.]?$",
        r"^前一结果落到<Q>身上，本段由<Q>承担新的因果入口$",
        r"^前层结果在L?\d+转为.+本层承接这一具体变化[。.]?$",
    ),
    "exit_relation": (
        r"^<Q>引出的行动在层尾改变关系站位，下一层必须从这个已生效的结果继续[。.]?$",
        r"^末端<Q>改变下一流程的入场条件[。.]?$",
        r"^段末<Q>已造成事实或态度位移，<Q>因此成为后文接点$",
        r"^L?\d+的<Q>留下后果，下一层从后果接入[。.]?$",
    ),
    "narrative_distance": (
        r"^视点由<Q>的可见细节贴入叙述者身体感受，最后退到旁人也能观察到的场面后果[。.]?$",
        r"^<N>维持当事人限知，围绕<Q>到<Q>移动[。.]?$",
        r"^视点跟踪<Q>附近的所见所闻，不越权解释<Q>之后的结果$",
        r"^叙述保持在本层.+可见距离，只拉开到原文明确给出的时间或传闻[。.]?$",
        r"^镜头贴近.+，只让.+所携带的事实进入视野[。.]?$",
        r"^从.+的近景移向.+的结果，仍不越过当时知情边界[。.]?$",
        r"^叙述以.+为观察锚点，.+仅作为现场可见证据出现[。.]?$",
        r"^.+与.+之间保持有限视角，后来的解释不提前倒灌[。.]?$",
    ),
}

FORBIDDEN_DIMENSION_HOW_SCAFFOLD_PATTERNS = {
    "narrative_voice_and_attitude": (
        r"^.+只按眼前的<Q>作判断，末端仍不替别人解释[。.]?该层的视角识别词为.+$",
        r"^叙述口气顺着<Q>的自我判断展开，保留<Q>里的迟疑或冷意$",
        r"^叙述把观察范围锁在.+呈现的当前关系中，未发生之事仍留白[。.]?$",
    ),
    "sentence_relation_and_rhythm": (
        r"^<Q>先起拍，短促结果<Q>随后截断预期[。.]?节奏铰链落在.+$",
        r"^<Q>把句群截成前后两段，<Q>再用长短反差收速$",
        r"^句群由开端的\d+行材料逐次推进，末端用.+改变阅读速度[。.]?$",
    ),
    "paragraph_breath_and_cut_points": (
        r"^开头先亮<Q>，中间不跳步，直到<Q>才换气[。.]?段落承重点对应.+$",
        r"^<Q>完成动作或信息闭合，段落选择在<Q>之后换气$",
        r"^段落在人物或时间真正换位后才停，本层结束点是.+$",
    ),
    "dialogue_misfire_or_avoidance": (
        r"^问答围绕<Q>错开理解，回应没有真正消除误会[。.]?$",
        r"^<Q>依靠沉默结果承压，原文未给可补写的对答$",
        r"^这里没有双方话轮，成文依靠叙述信息连续累积[。.]?$",
        r"^问答的回应方向发生偏转，人物说出口的内容没有解除对方压力[。.]?$",
    ),
    "action_perception_emotion_weave": (
        r"^先出现<Q>的动作或物件，再让身体反应校准情绪[。.]?$",
        r"^<Q>先给身体或空间变化，感受在<Q>处才追上来$",
        r"^<Q>交付的信息承担重量，肢体反应不是这一层载体$",
        r"^可见动作从.+发端，最终使身份、空间或下一步行动条件发生实变[。.]?$",
    ),
    "narrator_interjection_and_roughness": (
        r"^<Q>附近的反问从生活算计生出，随即回到事件[。.]?$",
        r"^<Q>留下当刻主观棱角，<Q>拒绝把它修成普遍道理$",
        r"^旁白保留当前人物的不体面反应或冷判断，让.+自行显出余味[。.]?$",
    ),
}

REPETITIVE_DIMENSION_HOW_PATTERNS = {
    "narrative_voice_and_attitude": (
        r"^第一人称以.+承受本层变化，不替.+洗白或预先解释[。.]?$",
        r"^站位紧跟.+完成.+不提前替.+判清全局[。.]?$",
    ),
    "sentence_relation_and_rhythm": (
        r"^句群围绕.+形成压力、接招、结果三段递进[。.]?$",
    ),
    "paragraph_breath_and_cut_points": (
        r"^在.+坐实后切段，使下一层承接真实后果[。.]?$",
    ),
    "dialogue_misfire_or_avoidance": (
        r"^本层主要由行动或压缩叙述承重，没有独立的对白误击结构[。.]?$",
        r"^话轮围绕.+发生施压、回避或错答，使.+不能被平顺解释掉[。.]?$",
    ),
    "action_perception_emotion_weave": (
        r"^.+同时改变现场控制与.+感受，动作不作装饰[。.]?$",
        r"^具体动作直接改变.+的处境，并把.+留作下一层压力[。.]?$",
    ),
    "narrator_interjection_and_roughness": (
        r"^叙述保留.+的即时偏见与反讽，不抹平成客观概要[。.]?$",
        r".*(?:叙述不替人物抹平|让读者自己抵达该结果|不是先给.+再补理由).*$",
        r"^叙述者把态度藏在.+的落差里，不替任何一方圆场[。.]?$",
        r"^.+带出克制的冷意，.+把讽刺落在具体结果而非标签[。.]?$",
    ),
}


def parse_line_range(value: Any, label: str) -> tuple[int, int]:
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


def prose_line_numbers(lines: list[str], start: int, end: int) -> list[int]:
    nonempty = [index for index, value in enumerate(lines, start=1) if value.strip()]
    outer_nonempty = {nonempty[0], nonempty[-1]} if nonempty else set()
    return [
        line_number
        for line_number in range(start, end + 1)
        if lines[line_number - 1].strip()
        and not SOURCE_SECTION_MARKER_RE.fullmatch(lines[line_number - 1])
        and not BOOK_METADATA_LINE_RE.match(lines[line_number - 1])
        and not (
            line_number in outer_nonempty
            and lines[line_number - 1].strip() in OUTER_PUNCTUATION_LINES
        )
    ]


def format_line_ranges(line_numbers: list[int]) -> str:
    if not line_numbers:
        return ""
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


def read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        errors.append(f"缺少子流程索引：{path}")
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{path} 第 {line_number} 行不是有效 JSON：{exc}")
            continue
        if not isinstance(item, dict):
            errors.append(f"{path} 第 {line_number} 行必须是对象")
            continue
        rows.append(item)
    return rows


def merge_normalized_layer_records(
    raw_rows: list[dict[str, Any]], errors: list[str]
) -> list[dict[str, Any]]:
    """Compile normalized source_layer records into their owning SF in memory."""
    subflows: list[dict[str, Any]] = []
    layers_by_subflow: dict[str, list[dict[str, Any]]] = {}
    for row_number, item in enumerate(raw_rows, start=1):
        record_type = str(item.get("record_type") or "subflow").strip()
        if record_type == "subflow":
            subflows.append(dict(item))
            continue
        if record_type != "source_layer":
            errors.append(
                f"子流程索引第 {row_number} 项 record_type 不支持：{record_type!r}"
            )
            continue
        if item.get("schema_version") != SCHEMA_VERSION:
            errors.append(
                f"子流程索引第 {row_number} 项 source_layer.schema_version "
                f"必须为 {SCHEMA_VERSION}"
            )
        subflow_id = str(item.get("subflow_id") or "").strip()
        layer = item.get("layer")
        if not subflow_id or not isinstance(layer, dict):
            errors.append(
                f"子流程索引第 {row_number} 项 source_layer 必须含 subflow_id 和 layer 对象"
            )
            continue
        layers_by_subflow.setdefault(subflow_id, []).append(layer)

    known_ids = {str(item.get("subflow_id") or "").strip() for item in subflows}
    unknown_ids = sorted(set(layers_by_subflow) - known_ids)
    if unknown_ids:
        errors.append(f"source_layer 引用了不存在的 SF：{', '.join(unknown_ids)}")
    for subflow in subflows:
        subflow_id = str(subflow.get("subflow_id") or "").strip()
        normalized_layers = layers_by_subflow.get(subflow_id)
        embedded_layers = subflow.get("source_layer_topology")
        if normalized_layers and embedded_layers:
            errors.append(f"{subflow_id} 不得同时使用内嵌和规范化来源层记录")
        layers = normalized_layers or embedded_layers
        if isinstance(layers, list):
            subflow["schema_version"] = SCHEMA_VERSION
            subflow["source_layer_topology"] = layers
            subflow["source_layer_order"] = [
                layer.get("layer_id") if isinstance(layer, dict) else None
                for layer in layers
            ]
    return subflows


def validate_declared_subflow_order(
    raw_rows: list[dict[str, Any]], label: str, errors: list[str]
) -> None:
    """Keep each physical catalog ordered before cross-file compilation."""
    previous_start = 0
    for row_number, item in enumerate(raw_rows, start=1):
        if str(item.get("record_type") or "subflow").strip() != "subflow":
            continue
        try:
            start, _ = parse_line_range(
                item.get("source_range"), f"{label}第 {row_number} 项.source_range"
            )
        except ValueError:
            continue
        if start < previous_start:
            errors.append(f"{label}的 subflow 记录必须按原文行区间非递减排列")
            return
        previous_start = start


def sort_compiled_subflows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insert companion-owned compatibility SFs by their source ranges."""
    def key(item: dict[str, Any]) -> tuple[int, int, str]:
        try:
            start, end = parse_line_range(item.get("source_range"), "source_range")
        except ValueError:
            start = end = 10**12
        return start, end, str(item.get("subflow_id") or "")

    return sorted(rows, key=key)


def validate_dimension_realization(
    value: Any,
    layer_text: str,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict) or set(value) != set(LANGUAGE_DIMENSIONS):
        errors.append(f"{label} 必须完整包含六个语言维度，不能用 SF 级摘要代替")
        return
    how_values: list[tuple[str, str]] = []
    how_clauses: dict[str, list[str]] = {}
    for dimension in LANGUAGE_DIMENSIONS:
        item = value.get(dimension)
        dimension_label = f"{label}.{dimension}"
        if not isinstance(item, dict):
            errors.append(f"{dimension_label} 必须是对象")
            continue
        status = item.get("status")
        if status not in {"active", "inactive"}:
            errors.append(f"{dimension_label}.status 必须为 active 或 inactive")
        if not isinstance(item.get("how"), str) or not item["how"].strip():
            errors.append(f"{dimension_label}.how 必须明确说明本层怎样起效或为何缺席")
        else:
            normalized_how = normalize_layer_scaffold(item["how"])
            how_values.append((dimension, normalized_how))
            if any(
                re.search(pattern, normalized_how)
                for pattern in FORBIDDEN_DIMENSION_HOW_SCAFFOLD_PATTERNS.get(
                    dimension, ()
                )
            ):
                errors.append(
                    f"{dimension_label}.how 使用原文嵌施工术语壳；"
                    "必须解释本层可观察的成文机制，不能追加识别词、铰链或承重点占位语"
                )
            for clause in re.split(r"[。！？；\n]+", item["how"]):
                normalized_clause = normalize_layer_scaffold(clause)
                if len(normalized_clause) >= 10:
                    how_clauses.setdefault(normalized_clause, []).append(dimension)
        evidence = item.get("source_evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(quote, str) or not quote.strip() for quote in evidence
        ):
            errors.append(f"{dimension_label}.source_evidence 必须是文本列表")
            continue
        if status == "active" and not evidence:
            errors.append(f"{dimension_label} 激活时必须给本层原文证据")
        if status == "inactive" and evidence:
            errors.append(f"{dimension_label} 缺席时不得伪造原文证据")
        for quote in evidence:
            if quote not in layer_text:
                errors.append(f"{dimension_label} 证据不在本层原文：{quote!r}")
    grouped_hows: dict[str, list[str]] = {}
    for dimension, normalized_how in how_values:
        if normalized_how:
            grouped_hows.setdefault(normalized_how, []).append(dimension)
    duplicates = [dimensions for dimensions in grouped_hows.values() if len(dimensions) >= 2]
    for dimensions in duplicates:
        errors.append(
            f"{label} 同层六维 how 跨维复制：{', '.join(dimensions)}；"
            "每个维度必须分别解释声音、句间、段落、对白、动作感知或叙述插话怎样起效/缺席"
        )
    repeated_clauses = [
        dimensions
        for dimensions in how_clauses.values()
        if len(set(dimensions)) >= 2
    ]
    if repeated_clauses:
        involved = sorted({dimension for dimensions in repeated_clauses for dimension in dimensions})
        errors.append(
            f"{label} 同层六维 how 存在长句跨维复用：{', '.join(involved)}；"
            "把一个维度的结论拼到另一个维度仍属于跨字段复制"
        )


def validate_catalog(
    catalog_path: Path,
    original_path: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not original_path.is_file():
        return [], [f"原文不存在：{original_path}"]
    lines = original_path.read_text(encoding="utf-8").splitlines()
    raw_rows = read_jsonl(catalog_path, errors)
    validate_declared_subflow_order(raw_rows, "子流程主索引", errors)
    layer_catalog_path = catalog_path.with_name("子流程层次索引.jsonl")
    if layer_catalog_path.is_file():
        companion_rows = read_jsonl(layer_catalog_path, errors)
        validate_declared_subflow_order(companion_rows, "子流程层次索引", errors)
        raw_rows.extend(companion_rows)
    rows = sort_compiled_subflows(merge_normalized_layer_records(raw_rows, errors))
    ids: list[str] = []
    all_covered: set[int] = set()
    previous_sf_start = 0
    layer_counts: list[int] = []
    layer_span_lengths: list[int] = []
    layer_text_values: dict[str, list[str]] = {field: [] for field in LAYER_TEXT_FIELDS}
    dimension_hows: dict[str, list[str]] = {name: [] for name in LANGUAGE_DIMENSIONS}

    for row_number, item in enumerate(rows, start=1):
        subflow_id = str(item.get("subflow_id") or "").strip()
        label = f"子流程索引第 {row_number} 项 {subflow_id or '<missing>'}"
        if not subflow_id:
            errors.append(f"{label} 缺少 subflow_id")
            continue
        ids.append(subflow_id)
        if subflow_id.startswith("SF-AUTO-") or re.fullmatch(
            r"原文覆盖补段\s+L\d+(?:-L?\d+)?", str(item.get("name") or "").strip()
        ):
            errors.append(
                f"{label} 残留自动补段占位标记；必须按本书真实事件链命名并人工划分 SF"
            )
        for field, generic_value in GENERIC_SUBFLOW_TEXT.items():
            if normalize_layer_text(item.get(field)) == normalize_layer_text(generic_value):
                errors.append(
                    f"{label}.{field} 使用自动补段概括句；必须写明本 SF 独有的入场或离场状态"
                )
        causal = item.get("causal_preconditions")
        if isinstance(causal, dict) and (
            causal.get("arrival_causes") == ["承接前文"]
            or causal.get("knowledge_boundaries") == ["以原文为准"]
            or causal.get("exit_cause") == "交给后续段落"
        ):
            errors.append(
                f"{label}.causal_preconditions 残留自动补段占位；"
                "必须登记本 SF 的真实到场原因、知情边界和离场因果"
            )
        if item.get("control_changes") == ["保留原文控制权变化"]:
            errors.append(
                f"{label}.control_changes 使用概括占位；必须写出谁取得或失去什么权限"
            )
        if item.get("emotion_sequence") == ["承接"]:
            errors.append(
                f"{label}.emotion_sequence 使用概括占位；必须登记本 SF 的实际情绪位移"
            )
        if item.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{label}.schema_version 必须为 {SCHEMA_VERSION}")
        try:
            sf_start, sf_end = parse_line_range(item.get("source_range"), f"{label}.source_range")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if sf_end > len(lines):
            errors.append(f"{label}.source_range 超出原文总行数 {len(lines)}")
            continue
        if sf_start < previous_sf_start:
            errors.append(f"{label} 必须按原文行区间非递减排列")
        previous_sf_start = sf_start
        exact_excerpt = "\n".join(lines[sf_start - 1 : sf_end])
        if not isinstance(item.get("source_excerpt"), str):
            item["source_excerpt"] = exact_excerpt
        if item.get("source_excerpt") != exact_excerpt:
            errors.append(f"{label}.source_excerpt 必须逐字等于 L{sf_start}-L{sf_end}")

        topology = item.get("source_layer_topology")
        if not isinstance(topology, list) or not topology:
            errors.append(f"{label}.source_layer_topology 必须是非空逐层拓扑，摘要字段不能替代")
            continue
        layer_counts.append(len(topology))
        sf_prose_count = len(prose_line_numbers(lines, sf_start, sf_end))
        required_sequence = item.get("required_sequence")
        required_steps = len(required_sequence) if isinstance(required_sequence, list) else 0
        if len(topology) == 1 and (
            sf_prose_count >= 40 or (sf_prose_count >= 12 and required_steps >= 2)
        ):
            errors.append(
                f"{label} 跨 {sf_prose_count} 个正文行、声明 {required_steps} 个必经步骤，"
                "却只有 1 个来源层；必须按真实叙事模式换挡拆层"
            )
        layer_covered: set[int] = set()
        previous_layer_end = sf_start - 1
        expected_layer_ids: list[str] = []
        for index, layer in enumerate(topology, start=1):
            layer_label = f"{label}.source_layer_topology[{index}]"
            expected_layer_id = f"{subflow_id}-L{index:02d}"
            expected_layer_ids.append(expected_layer_id)
            if not isinstance(layer, dict):
                errors.append(f"{layer_label} 必须是对象")
                continue
            if layer.get("layer_id") != expected_layer_id:
                errors.append(f"{layer_label}.layer_id 必须为 {expected_layer_id}")
            try:
                layer_start, layer_end = parse_line_range(
                    layer.get("source_range"), f"{layer_label}.source_range"
                )
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if layer_start < sf_start or layer_end > sf_end:
                errors.append(f"{layer_label}.source_range 必须位于当前 SF 范围内")
                continue
            if layer_start <= previous_layer_end:
                errors.append(f"{layer_label} 与前一层重叠或倒序")
            previous_layer_end = layer_end
            layer_span_lengths.append(layer_end - layer_start + 1)
            exact_layer_text = "\n".join(lines[layer_start - 1 : layer_end])
            if not isinstance(layer.get("source_text"), str):
                layer["source_text"] = exact_layer_text
            if layer.get("source_text") != exact_layer_text:
                errors.append(
                    f"{layer_label}.source_text 必须逐字等于 L{layer_start}-L{layer_end}"
                )
            modes = layer.get("layer_modes")
            if (
                not isinstance(modes, list)
                or not modes
                or any(mode not in LAYER_MODES for mode in modes)
                or len(modes) != len(set(modes))
            ):
                errors.append(f"{layer_label}.layer_modes 必须是合法、非重复的叙事模式列表")
            for field in LAYER_TEXT_FIELDS:
                if not isinstance(layer.get(field), str) or not layer[field].strip():
                    errors.append(f"{layer_label}.{field} 必须明确填写")
                else:
                    layer_text_values[field].append(layer[field].strip())
                    if normalize_layer_text(layer[field]) == normalize_layer_text(GENERIC_LAYER_TEXT[field]):
                        errors.append(
                            f"{layer_label}.{field} 使用禁用概括占位句；"
                            "必须说明本层独有的叙事作用与衔接"
                        )
                    scaffold = normalize_layer_scaffold(layer[field])
                    if any(
                        re.search(pattern, scaffold)
                        for pattern in FORBIDDEN_LAYER_SCAFFOLD_PATTERNS.get(field, ())
                    ):
                        errors.append(
                            f"{layer_label}.{field} 使用原文嵌固定句式；"
                            "替换引文仍不构成本层独有分析"
                        )
            preserve = layer.get("must_preserve_in_target")
            if not isinstance(preserve, list) or not preserve or any(
                not isinstance(rule, str) or not rule.strip() for rule in preserve
            ):
                errors.append(f"{layer_label}.must_preserve_in_target 必须是非空施工规则列表")
            validate_dimension_realization(
                layer.get("dimension_realization"),
                exact_layer_text,
                f"{layer_label}.dimension_realization",
                errors,
            )
            dimensions = layer.get("dimension_realization")
            if isinstance(dimensions, dict):
                normalized_role = normalize_layer_text(layer.get("layer_role"))
                role_stuffed_dimensions: list[str] = []
                for dimension in LANGUAGE_DIMENSIONS:
                    dimension_item = dimensions.get(dimension)
                    if isinstance(dimension_item, dict) and isinstance(dimension_item.get("how"), str):
                        how = dimension_item["how"].strip()
                        dimension_hows[dimension].append(how)
                        if (
                            len(normalized_role) >= 12
                            and normalized_role in normalize_layer_text(how)
                        ):
                            role_stuffed_dimensions.append(dimension)
                if len(role_stuffed_dimensions) >= 2:
                    errors.append(
                        f"{layer_label}.dimension_realization 将 layer_role 整句嵌入 "
                        f"{len(role_stuffed_dimensions)} 个 how："
                        f"{', '.join(role_stuffed_dimensions)}；"
                        "情节名换壳不能替代各维度的独立成文机制"
                    )
            current_lines = set(prose_line_numbers(lines, layer_start, layer_end))
            duplicates = sorted(layer_covered & current_lines)
            if duplicates:
                errors.append(
                    f"{layer_label} 重复覆盖原文正文行：{format_line_ranges(duplicates)}"
                )
            layer_covered.update(current_lines)

        sf_prose_lines = set(prose_line_numbers(lines, sf_start, sf_end))
        missing = sorted(sf_prose_lines - layer_covered)
        extra = sorted(layer_covered - sf_prose_lines)
        if missing:
            errors.append(f"{label} 层次拓扑漏掉正文行：{format_line_ranges(missing)}")
        if extra:
            errors.append(f"{label} 层次拓扑越界覆盖：{format_line_ranges(extra)}")
        layer_order = item.get("source_layer_order")
        if layer_order != expected_layer_ids:
            errors.append(f"{label}.source_layer_order 必须与逐层拓扑完整同序")
        cross_sf_duplicates = sorted(all_covered & sf_prose_lines)
        if cross_sf_duplicates:
            errors.append(
                f"{label} 与前序子流程重复覆盖正文行："
                f"{format_line_ranges(cross_sf_duplicates)}"
            )
        all_covered.update(sf_prose_lines)

    duplicates = sorted(subflow_id for subflow_id in set(ids) if ids.count(subflow_id) > 1)
    if duplicates:
        errors.append(f"子流程 subflow_id 重复：{', '.join(duplicates)}")
    if not rows:
        errors.append("子流程索引不得为空")
    whole_prose = set(prose_line_numbers(lines, 1, len(lines)))
    if len(rows) >= 2 and len(whole_prose) >= 40 and layer_counts and all(
        count == 1 for count in layer_counts
    ):
        errors.append(
            f"整本子流程层次塌缩：{len(rows)} 个 SF 全部恰好 1 层；"
            "逐层拓扑必须按现场、回叙、压缩、话轮、结果等真实换挡建立"
        )
    total_layers = sum(layer_counts)
    if total_layers >= 20:
        repeated_long_spans = [
            (span, count)
            for span, count in Counter(layer_span_lengths).most_common(2)
            if span >= 8
        ]
        repeated_long_span_count = sum(count for _, count in repeated_long_spans)
        if (
            repeated_long_spans
            and repeated_long_spans[0][1] >= max(8, (total_layers + 3) // 4)
            and repeated_long_span_count >= (total_layers + 1) // 2
        ):
            distribution = ", ".join(
                f"{span} 行 x {count} 层" for span, count in repeated_long_spans
            )
            errors.append(
                f"来源层疑似按固定行数分桶：{distribution}，共 "
                f"{repeated_long_span_count}/{total_layers} 层；"
                "必须回到现场、回叙、话轮、结果或叙述距离的真实换挡点重切"
            )
    repetitive_threshold = max(6, (total_layers * 6 + 9) // 10)
    for field, patterns in REPETITIVE_LAYER_TEXT_PATTERNS.items():
        count = sum(
            any(re.search(pattern, value) for pattern in patterns)
            for value in layer_text_values[field]
        )
        if count >= repetitive_threshold:
            errors.append(
                f"来源层 {field} 句法骨架高比例复用：{count}/{total_layers}；"
                "替换桥段名或结果短语不构成逐层语义"
            )
    for dimension, patterns in REPETITIVE_DIMENSION_HOW_PATTERNS.items():
        count = sum(
            any(re.search(pattern, value) for pattern in patterns)
            for value in dimension_hows[dimension]
        )
        if count >= repetitive_threshold:
            errors.append(
                f"来源层六维 {dimension}.how 句法骨架高比例复用："
                f"{count}/{total_layers}；必须说明本层独有的成文协同或缺席原因"
            )
    scaffold_threshold = max(6, (total_layers + 3) // 4)
    for field, values in layer_text_values.items():
        fingerprint, count = Counter(
            normalize_layer_scaffold(value) for value in values
        ).most_common(1)[0] if values else ("", 0)
        if fingerprint and count >= scaffold_threshold:
            errors.append(
                f"来源层 {field} 去除引文/行号后的固定句法重复："
                f"{count}/{total_layers}；原文嵌壳不算逐层分析"
            )
    for dimension, values in dimension_hows.items():
        fingerprint, count = Counter(
            normalize_layer_scaffold(value) for value in values
        ).most_common(1)[0] if values else ("", 0)
        if fingerprint and count >= scaffold_threshold:
            errors.append(
                f"来源层六维 {dimension}.how 去除引文/行号后的固定句法重复："
                f"{count}/{total_layers}；必须重写本层真实成文机制"
            )
    missing_whole = sorted(whole_prose - all_covered)
    if missing_whole:
        errors.append(f"子流程索引未覆盖原文全部正文行：{format_line_ranges(missing_whole)}")
    return rows, errors


def normalize_layer_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def normalize_layer_scaffold(value: Any) -> str:
    normalized = str(value or "").strip()
    normalized = re.sub(r"`[^`]+`", "<Q>", normalized)
    normalized = re.sub(r"[“「『‘][^”」』’]+[”」』’]", "<Q>", normalized)
    normalized = re.sub(r'"[^"]+"', "<Q>", normalized)
    normalized = re.sub(r"\b(?:SF-)?L?\d+(?:[-~至]L?\d+)?\b", "<N>", normalized)
    return normalize_layer_text(normalized)


def main() -> int:
    parser = argparse.ArgumentParser(description="验证短篇子流程完整来源层次拓扑")
    parser.add_argument("catalog", help="写作资产/子流程索引.jsonl")
    parser.add_argument("original", help="对应原文 TXT")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    rows, errors = validate_catalog(Path(args.catalog).resolve(), Path(args.original).resolve())
    payload = {
        "ok": not errors,
        "subflow_count": len(rows),
        "error_count": len(errors),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print("blocked")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"passed: {len(rows)} subflows")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
