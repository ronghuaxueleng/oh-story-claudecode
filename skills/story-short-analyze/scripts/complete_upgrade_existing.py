#!/usr/bin/env python3
"""Complete incremental upgrade tasks for existing short-analyze outputs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


STYLE_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)


def load_module(filename: str, module_name: str) -> Any:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"无法加载模块：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SYNC = load_module("sync_finalize_human_review.py", "short_analyze_sync_finalize")


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是对象")
    return data


def load_original_lines(root: Path) -> list[str]:
    original_dir = root / "原文"
    lines: list[str] = []
    for path in sorted(candidate for candidate in original_dir.iterdir() if candidate.is_file()):
        lines.extend(read_text(path).splitlines())
    return lines


def source_slice(lines: list[str], source_range: str) -> str:
    parts = [
        part.strip()
        for part in re.split(r"[、,，]\s*", source_range.strip())
        if part.strip()
    ]
    slices: list[str] = []
    for part in parts:
        match = re.fullmatch(r"L(\d+)-L(\d+)", part)
        if not match:
            return ""
        start, end = int(match.group(1)), int(match.group(2))
        if start < 1 or end > len(lines) or start > end:
            return ""
        slices.append("\n".join(lines[start - 1 : end]))
    return "\n".join(slices)


def validate_subflow_style(root: Path) -> dict[str, Any]:
    index_path = root / "写作资产" / "子流程索引.jsonl"
    if not index_path.is_file():
        raise FileNotFoundError(f"缺少子流程索引：{index_path}")
    lines = load_original_lines(root)
    raw_lines = read_text(index_path).splitlines()
    checked = 0
    errors: list[str] = []
    for raw in raw_lines:
        if not raw.strip():
            continue
        entry = json.loads(raw)
        if not isinstance(entry, dict):
            raise ValueError(f"{index_path} 存在非对象 JSONL 条目")
        checked += 1
        subflow_id = str(entry.get("subflow_id") or f"line-{checked}")
        excerpt = source_slice(lines, str(entry.get("source_range") or ""))
        style = entry.get("source_style_granularity")
        if not isinstance(style, dict):
            errors.append(f"{subflow_id} 缺少 source_style_granularity")
            continue
        for field in STYLE_FIELDS:
            item = style.get(field)
            if not isinstance(item, dict) or not str(item.get("analysis") or "").strip():
                errors.append(f"{subflow_id}.{field} 缺少模型分析")
                continue
            evidence = item.get("source_evidence")
            if not isinstance(evidence, list) or len({str(value).strip() for value in evidence if str(value).strip()}) < 2:
                errors.append(f"{subflow_id}.{field} 至少需要两条不同原文证据")
                continue
            missing_quotes = [str(value).strip() for value in evidence if str(value).strip() not in excerpt]
            if missing_quotes:
                errors.append(f"{subflow_id}.{field} 证据不在本 SF source_range 内")
    if errors:
        raise ValueError("子流程文风颗粒校验失败：\n- " + "\n- ".join(errors))
    return {"checked": checked, "path": str(index_path)}


def mark_progress_reviewed(root: Path) -> bool:
    path = root / "_progress.md"
    if not path.is_file():
        return False
    lines = []
    changed = False
    for line in read_text(path).splitlines():
        new_line = line
        if "模型人工复核" in line or "run_short_analyze_finalize.py" in line:
            new_line = re.sub(r"^- \[[ xX]\]", "- [x]", line)
        if new_line != line:
            changed = True
        lines.append(new_line)
    if changed:
        write_text(path, "\n".join(lines) + "\n")
    return changed


def read_review_decisions(path: Path) -> dict[str, Any]:
    payload = read_json(path.resolve())
    for key in ("upgrade_reviews", "review_items"):
        if not isinstance(payload.get(key), dict):
            raise ValueError(f"裁决文件 {key} 必须是按 ID/scope 索引的对象")
    return payload


def apply_review_decisions(payload: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    allowed_statuses = {"resolved", "not_applicable"}
    decision_groups = {
        "upgrade_reviews": "scope",
        "review_items": "id",
    }
    for group, identity_field in decision_groups.items():
        items = payload.get(group, [])
        decision_map = decisions.get(group, {})
        expected_ids = {
            str(item.get(identity_field) or "")
            for item in items
            if isinstance(item, dict)
        }
        missing = sorted(expected_ids - set(decision_map))
        extra = sorted(set(decision_map) - expected_ids)
        if missing:
            raise ValueError(f"{group} 缺少显式裁决：{', '.join(missing)}")
        if extra:
            raise ValueError(f"{group} 包含当前回执不存在的裁决：{', '.join(extra)}")
        for item in items:
            if not isinstance(item, dict):
                continue
            identity = str(item.get(identity_field) or "")
            decision = decision_map[identity]
            if not isinstance(decision, dict):
                raise ValueError(f"{group}.{identity} 裁决必须是对象")
            status = str(decision.get("status") or "")
            judgement = str(decision.get("judgement") or "").strip()
            evidence = decision.get("evidence")
            if status not in allowed_statuses:
                raise ValueError(f"{group}.{identity}.status 必须是 resolved 或 not_applicable")
            if len(judgement) < 8:
                raise ValueError(f"{group}.{identity}.judgement 必须是具体人工判断")
            if not isinstance(evidence, list) or not any(str(value).strip() for value in evidence):
                raise ValueError(f"{group}.{identity}.evidence 不能为空")
            item["status"] = status
            item["judgement"] = judgement
            item["evidence"] = [str(value).strip() for value in evidence if str(value).strip()]
    payload["upgrade_status"] = "completed"
    return payload


def complete_receipt(root: Path, decisions: dict[str, Any]) -> dict[str, Any]:
    receipt_path, payload, _ = SYNC.sync_receipt(root)
    payload = apply_review_decisions(payload, decisions)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(receipt_path),
        "review_item_count": len(payload.get("review_items", [])),
        "upgrade_review_count": len(payload.get("upgrade_reviews", [])),
    }


def process_root(root: Path, review_decisions: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    style_result = validate_subflow_style(root)
    receipt_result = complete_receipt(root, review_decisions)
    progress_changed = mark_progress_reviewed(root)
    return {
        "root": str(root),
        "style_validation": style_result,
        "receipt": receipt_result,
        "progress_marked": progress_changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="补齐历史拆书目录的完整增量升级收尾内容")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--review-decisions", required=True, help="当前模型逐项人工裁决 JSON")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    payload = process_root(Path(args.root), read_review_decisions(Path(args.review_decisions)))
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
