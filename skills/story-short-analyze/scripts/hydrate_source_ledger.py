#!/usr/bin/env python3
"""Serialize explicitly authored compact ledger rows without semantic inference."""
import argparse
import hashlib
import json
import re
from pathlib import Path


PLOT_FIELDS = ("beat_id", "start_line", "end_line", "bid", "actor", "action", "object_or_receiver", "pressure_or_trigger", "control_change", "information_change", "consequence", "evidence")
EMOTION_FIELDS = ("beat_id", "start_line", "end_line", "bid", "role", "content", "trigger", "relationship_position_change", "reader_effect", "intensity", "narrative_function", "evidence")
PLOT_CANDIDATE_FIELDS = ("candidate_id", "start_line", "end_line", "candidate_type", "actor", "decision", "bound_beat", "manual_judgment", "merge_reason")
EMOTION_CANDIDATE_FIELDS = ("candidate_id", "start_line", "end_line", "change_axis", "before_state", "after_state", "decision", "bound_beat", "manual_judgment", "merge_reason")
DIMENSIONS = ("narrative_voice_and_attitude", "sentence_relation_and_rhythm", "paragraph_breath_and_cut_points", "dialogue_misfire_or_avoidance", "action_perception_emotion_weave", "narrator_interjection_and_roughness")


def hydrate_subflows(data, source_path):
    lines = source_path.read_text(encoding="utf-8").splitlines()
    if data.get("source_line_count") != len(lines):
        raise ValueError("Manual source_line_count differs from source")
    flows = []
    layers = []
    for row in data["flow_rows"]:
        item = row_object(row, ("subflow_id", "start_line", "end_line", "parent_bridge_id", "name", "entry_state", "required_sequence", "information_delay", "control_changes", "emotion_sequence", "end_state", "source_evidence"))
        start, end, excerpt = source_range(item, lines)
        item["source_range"] = f"L{start}-L{end}"
        item["source_excerpt"] = excerpt
        item["source_book"] = data["source_book"]
        item["schema_version"] = "story-short-analyze.subflow-catalog.v2"
        item["source_layer_order"] = []
        registry = data.get("causal_preconditions_registry", {})
        causal = registry.get(item["subflow_id"])
        if causal is not None:
            if not isinstance(causal, dict):
                raise ValueError("Explicit causal preconditions must be an object")
            item["causal_preconditions"] = causal
        flows.append(item)
    unknown_causal = set(data.get("causal_preconditions_registry", {})) - {flow["subflow_id"] for flow in flows}
    if unknown_causal:
        raise ValueError(f"Unknown causal flow bindings: {sorted(unknown_causal)}")
    for row in data["layer_rows"]:
        layer = row_object(row, ("subflow_id", "layer_id", "start_line", "end_line", "layer_modes", "layer_role", "entry_relation", "exit_relation", "narrative_distance", "must_preserve_in_target", "dimensions"))
        start, end, excerpt = source_range(layer, lines)
        layer["source_range"] = f"L{start}-L{end}"
        layer["source_text"] = excerpt
        flow_id = layer.pop("subflow_id")
        if layer["layer_id"] not in data.get("layer_mode_registry", {}):
            raise ValueError("Each layer needs an explicit canonical mode declaration")
        layer["layer_modes"] = data["layer_mode_registry"][layer["layer_id"]]
        dimensions = layer.pop("dimensions")
        if not isinstance(dimensions, list) or len(dimensions) != 6:
            raise ValueError("All six explicitly authored dimensions required")
        layer["dimension_realization"] = {}
        for name, dimension in zip(DIMENSIONS, dimensions):
            if not isinstance(dimension, list) or len(dimension) != 2:
                raise ValueError("Each dimension needs an analysis and explicit quote or null")
            how, quote = dimension
            if quote is not None and quote not in excerpt:
                raise ValueError(f"Dimension evidence outside {layer['layer_id']}: {quote}")
            layer["dimension_realization"][name] = {"status": "active" if quote else "inactive", "how": how, "source_evidence": [quote] if quote else []}
        flow = next((flow for flow in flows if flow["subflow_id"] == flow_id), None)
        if flow is None:
            raise ValueError(f"Unknown explicit flow binding: {flow_id}")
        flow["source_layer_order"].append(layer["layer_id"])
        layers.append({"record_type": "source_layer", "schema_version": "story-short-analyze.subflow-catalog.v2", "subflow_id": flow_id, "layer": layer})
    return flows, layers


def row_object(row, fields):
    if not isinstance(row, list) or len(row) != len(fields):
        raise ValueError(f"Expected {len(fields)} explicitly authored fields: {fields}")
    return dict(zip(fields, row))


def source_range(item, lines):
    start, end = item.pop("start_line"), item.pop("end_line")
    if not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= len(lines):
        raise ValueError(f"Invalid source range: {start}-{end}")
    item["source_range"] = {"start_line": start, "end_line": end}
    return start, end, "\n".join(lines[start - 1:end])


def hydrate(data, kind, source_path):
    raw = source_path.read_bytes()
    lines = raw.decode("utf-8-sig").splitlines()
    if data.get("source_line_count") != len(lines):
        raise ValueError("Manual source_line_count differs from source")
    fields = PLOT_FIELDS if kind == "plot" else EMOTION_FIELDS
    beats = []
    for row in data[f"{kind}_rows"]:
        item = row_object(row, fields)
        start, end, excerpt = source_range(item, lines)
        evidence = item.pop("evidence")
        if not isinstance(evidence, str) or not evidence or evidence not in excerpt:
            raise ValueError(f"Evidence outside manually bound range: {item['beat_id']}")
        bid = item.pop("bid")
        item["bid_ids"] = [bid] if bid else []
        item["source_evidence"] = [evidence] if kind == "emotion" else evidence
        if kind == "emotion":
            item.update(start_line=start, end_line=end)
        beats.append(item)
    candidates = []
    candidate_fields = PLOT_CANDIDATE_FIELDS if kind == "plot" else EMOTION_CANDIDATE_FIELDS
    for row in data[f"{kind}_candidates"]:
        item = row_object(row, candidate_fields)
        _, _, excerpt = source_range(item, lines)
        bound = item.pop("bound_beat")
        item["bound_beat_ids"] = [bound] if bound else []
        item["source_evidence"] = excerpt
        candidates.append(item)
    coverage = []
    next_line = 1
    for index, row in enumerate(data[f"{kind}_coverage"], 1):
        segment_fields = ("start_line", "end_line", "kind", "candidate_ids", "reason") if kind == "plot" else ("start_line", "end_line", "kind", "beat_ids", "candidate_ids", "reason")
        segment = row_object(row, segment_fields)
        if segment["start_line"] != next_line:
            raise ValueError("Explicit coverage ranges must be continuous")
        next_line = segment["end_line"] + 1
        segment["segment_id"] = f"{'P' if kind == 'plot' else 'E'}SEG-{index:04d}"
        coverage.append(segment)
        if kind == "emotion":
            for beat_id in segment["beat_ids"]:
                matches = [beat for beat in beats if beat["beat_id"] == beat_id]
                if len(matches) != 1:
                    raise ValueError(f"Missing or duplicated explicit E binding: {beat_id}")
                matches[0]["segment_id"] = segment["segment_id"]
    if next_line != len(lines) + 1:
        raise ValueError("Manual coverage is incomplete; refusing to replace formal ledger")
    review = data.get(f"{kind}_completeness_review")
    if not isinstance(review, dict) or not review:
        raise ValueError("Explicit model completeness review is required")
    return {"schema_version": f"story-short-analyze.full-text-{kind}-ledger.v2", "source": {"path": str(source_path.resolve()), "sha1": hashlib.sha1(raw).hexdigest(), "sha256": hashlib.sha256(raw).hexdigest(), "line_count": len(lines)}, "beats": beats, "coverage_segments": coverage, f"source_{kind}_candidate_audit": candidates, "completeness_review": review}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--kind", required=True, choices=("plot", "emotion", "subflow", "sync-emotion-references"))
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    manifest = json.loads((root / "_source_manifest.json").read_text(encoding="utf-8"))
    source_path = Path(manifest.get("copied_source_path") or manifest.get("copied_path") or "")
    if not source_path.is_file():
        sources = list((root / "原文").glob("*.txt"))
        if len(sources) != 1:
            raise ValueError("Expected one manifest source file")
        source_path = sources[0]
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.kind == "sync-emotion-references":
        ledger = json.loads((root / "写作资产" / "全文情绪颗粒总账.json").read_text(encoding="utf-8"))
        registry = {item["bridge_id"]: item for item in data["bridge_registry"]}
        for relative in data["emotion_reference_targets"]:
            target = root / relative
            original = target.read_text(encoding="utf-8")
            parts = re.split(r"(?=^## BID-\d+\s*$)", original, flags=re.M) if target.name != "profile_source.md" else re.split(r"(?=^- 桥段：BID-\d+\s)", original, flags=re.M)
            changed = []
            for block in parts:
                match = re.match(r"(?:##|\- 桥段：)\s*(BID-\d+)", block)
                if not match:
                    changed.append(block)
                    continue
                bridge_id = match.group(1)
                if bridge_id not in registry:
                    raise ValueError(f"Unregistered bridge: {bridge_id}")
                lines_out = [line for line in block.splitlines() if not re.match(r"^\s*- 情绪拍[：:]", line) and "情绪拍完整性复核：" not in line]
                # Only the explicit bridge reference rows are replaced; prose remains authored.
                refs = [beat for beat in ledger["beats"] if bridge_id in beat["bid_ids"]]
                indent = "  " if target.name == "profile_source.md" else ""
                rows = [f"{indent}- 情绪拍：{beat['beat_id']} | 作用：{beat['role']} | 内容：{beat['content']} | 烈度：{beat['intensity']} | 原文证据：{beat['source_evidence'][0]}" for beat in refs]
                heading_index = next((index for index, line in enumerate(lines_out[1:], 1) if line.startswith("## ")), len(lines_out))
                lines_out[heading_index:heading_index] = rows
                changed.append("\n".join(lines_out) + "\n")
            target.write_text("".join(changed), encoding="utf-8")
        print(json.dumps({"status": "explicit-emotion-references-synchronized", "targets": data["emotion_reference_targets"]}, ensure_ascii=False))
        return
    if args.kind == "subflow":
        flows, layers = hydrate_subflows(data, source_path)
        for name, rows in (("子流程索引.jsonl", flows), ("子流程层次索引.jsonl", layers)):
            (root / "写作资产" / name).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        print(json.dumps({"subflows": len(flows), "layers": len(layers), "status": "serialized-for-validation"}))
        return
    ledger = hydrate(data, args.kind, source_path)
    name = "全文情节微拍总账.json" if args.kind == "plot" else "全文情绪颗粒总账.json"
    (root / "写作资产" / name).write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"kind": args.kind, "beats": len(ledger["beats"]), "status": "serialized-for-validation"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
