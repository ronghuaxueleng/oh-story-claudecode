#!/usr/bin/env python3
"""Build a source-preserving cross-book subflow index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "subflow_id",
    "source_book",
    "parent_bridge_id",
    "name",
    "source_range",
    "function_tags",
    "entry_state",
    "required_sequence",
    "scene_granularity",
    "information_delay",
    "control_changes",
    "emotion_sequence",
    "end_state",
    "embeddable_after",
    "incompatible_with",
    "source_evidence",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} 不是有效 JSON：{exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} 必须是 JSON 对象")
        missing = [field for field in REQUIRED_FIELDS if field not in value]
        if missing:
            raise ValueError(f"{path}:{line_number} 缺少字段：{', '.join(missing)}")
        entries.append(value)
    if not entries:
        raise ValueError(f"{path} 没有有效子流程")
    return entries


def build_library(corpus_root: Path) -> list[dict[str, Any]]:
    corpus_root = corpus_root.resolve()
    entries: list[dict[str, Any]] = []
    seen_global_ids: set[str] = set()
    index_paths = sorted(corpus_root.glob("*/写作资产/子流程索引.jsonl"))
    for index_path in index_paths:
        book_dir = index_path.parent.parent
        index_hash = sha256(index_path)
        for entry in load_jsonl(index_path):
            source_book = str(entry["source_book"]).strip() or book_dir.name
            subflow_id = str(entry["subflow_id"]).strip()
            global_id = f"{source_book}::{subflow_id}"
            if global_id in seen_global_ids:
                raise ValueError(f"跨书子流程全局 ID 重复：{global_id}")
            seen_global_ids.add(global_id)
            entries.append(
                {
                    "global_subflow_id": global_id,
                    "source_book": source_book,
                    "source_dir": str(book_dir.resolve()),
                    "source_index_path": str(index_path.resolve()),
                    "source_index_sha256": index_hash,
                    **entry,
                }
            )
    return entries


def write_library(entries: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        for entry in entries
    )
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="聚合拆文库内各书完整子流程，并保留来源边界和索引 SHA。"
    )
    parser.add_argument("corpus_root", help="拆文库目录，例如 项目根/拆文库")
    parser.add_argument(
        "--output",
        help="输出路径；默认写到拆文库同级的 资料库/子流程总索引.jsonl",
    )
    args = parser.parse_args()

    corpus_root = Path(args.corpus_root)
    output_path = (
        Path(args.output)
        if args.output
        else corpus_root.parent / "资料库" / "子流程总索引.jsonl"
    )
    try:
        entries = build_library(corpus_root)
        write_library(entries, output_path)
    except ValueError as exc:
        print("subflow_library: blocked")
        print(f"- {exc}")
        return 2
    print(f"subflow_library: built ({len(entries)} entries, {output_path.resolve()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
