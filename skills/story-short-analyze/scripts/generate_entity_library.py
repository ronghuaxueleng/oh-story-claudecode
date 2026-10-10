#!/usr/bin/env python3
"""Build the root-level cross-book entity and mechanism index.

The library is an index of existing finalized analysis assets. It does not
copy prose or invent entities. Write projects must still authorize each item
through their source contract before use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ENTITY_TYPES = ("person", "relationship", "profession", "institution", "setting", "object", "mechanism", "consequence")
MIGRATION_GROUP_TYPES = {
    "object_substitutes": ("object", "adaptation_object"),
    "scene_substitutes": ("setting", "adaptation_scene"),
    "action_substitutes": ("mechanism", "adaptation_action"),
    "dialogue_substitutes": ("mechanism", "adaptation_dialogue"),
    "role_bias_variants": ("relationship", "adaptation_role_bias"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def add(items: list[dict[str, Any]], seen: set[tuple[str, str, str]], book: str, kind: str, value: str, source_ref: str, role: str, forbidden: bool = False) -> None:
    value = str(value).strip()
    if not value:
        return
    key = (book, kind, value)
    if key in seen:
        return
    seen.add(key)
    items.append({
        "entity_id": f"{book}:{kind}:{len(items)+1:04d}",
        "source_book": book,
        "entity_type": kind,
        "label": value,
        "source_ref": source_ref,
        "asset_type": role,
        "provenance": "adaptation_suggestion" if role.startswith("adaptation_") else "source_analysis",
        "migration_status": "forbidden_reentry" if forbidden else "requires_project_authorization",
        "adaptation_boundary": "可检索功能与压力机制；不得直接复用专名、人物壳、具体事件、完整关系答案或原句。",
        "forbidden_reentry": forbidden,
    })


def build_book(book_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    book = book_dir.name
    profile_path = book_dir / "book.profile.json"
    brain_path = book_dir / "写作资产/来源成文脑图.json"
    report_path = book_dir / "拆文报告.md"
    profile = load(profile_path, {})
    brain = load(brain_path, {})
    entities: list[dict[str, Any]] = []
    mechanisms: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    mechanism_seen: set[tuple[str, str, str]] = set()
    for key, kind in (("scene_assets", "setting"), ("migration_assets", "object")):
        values = profile.get(key, {})
        if isinstance(values, dict):
            for group, entries in values.items():
                if isinstance(entries, list):
                    for entry in entries:
                        # Group metadata, not a label/name heuristic, determines
                        # whether this is an object or an adaptation operation.
                        entry_kind, role = (MIGRATION_GROUP_TYPES.get(group, ("mechanism", "adaptation_untyped"))
                                            if key == "migration_assets" else (kind, "source_scene_analysis"))
                        add(entities, seen, book, entry_kind, str(entry), f"profile:{key}.{group}", role)
    for bridge in profile.get("bridge_rules", []) if isinstance(profile.get("bridge_rules"), list) else []:
        if not isinstance(bridge, dict):
            continue
        bid = str(bridge.get("id") or "")
        for field in ("opening_pattern", "must_keep", "recommended_sequence", "consequence_structure"):
            values = bridge.get(field, [])
            if isinstance(values, list):
                for value in values:
                    text = str(value)
                    add(mechanisms, mechanism_seen, book, "mechanism", text, f"{bid}:{field}", "bridge_mechanism")
    for beat in brain.get("plot_beats", []) if isinstance(brain.get("plot_beats"), list) else []:
        if not isinstance(beat, dict):
            continue
        ref = str(beat.get("beat_id") or "plot")
        for field, kind in (("actor", "person"), ("object_or_receiver", "object"), ("action", "mechanism"), ("consequence", "consequence")):
            add(entities, seen, book, kind, str(beat.get(field) or ""), f"{ref}:{field}", "plot_beat_asset")
    for layer in brain.get("layers", []) if isinstance(brain.get("layers"), list) else []:
        if isinstance(layer, dict):
            for mode in layer.get("layer_modes", []) or []:
                add(entities, seen, book, "mechanism", str(mode), f"layer:{layer.get('layer_id')}:mode", "narrative_layer", False)

    book_index = {
        "source_book": book,
        "source_paths": {
            "profile": str(profile_path.resolve()),
            "profile_sha256": sha(profile_path) if profile_path.is_file() else "",
            "brain_map": str(brain_path.resolve()),
            "brain_map_sha256": sha(brain_path) if brain_path.is_file() else "",
            "report": str(report_path.resolve()) if report_path.is_file() else "",
        },
        "asset_counts": {"entities": len(entities), "mechanisms": len(mechanisms)},
        "read_policy": "index_only; project must authorize selected assets; no prose voice or complete event chain is supplied",
        "entities": entities,
        "mechanisms": mechanisms,
        "forbidden_reentry": [x["entity_id"] for x in entities + mechanisms if x["forbidden_reentry"]],
    }
    return book_index, entities, mechanisms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--require-book", action="append", default=[], help="Require this selected source to be ready before any library write; repeat for multiple books")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    source_root = root / "拆文库"
    out = root / "资料库"
    books = []
    all_entities: list[dict[str, Any]] = []
    all_mechanisms: list[dict[str, Any]] = []
    candidates = [book_dir for book_dir in sorted(source_root.iterdir() if source_root.is_dir() else [])
                  if book_dir.is_dir() and (book_dir / "book.profile.json").is_file()]
    blocked = []
    for book_dir in candidates:
        result = load(book_dir / "_finalize_result.json", {})
        meta = load(book_dir / "_meta.json", {})
        if (result.get("ok") is not True or result.get("status") != "ready-for-write"
                or result.get("error_count") != 0 or meta.get("upgrade_status") == "pending_content_review"
                or not (book_dir / "写作资产/来源成文脑图.json").is_file()):
            blocked.append(book_dir.name)
    required_errors = sorted(set(args.require_book) & set(blocked) | (set(args.require_book) - {b.name for b in candidates}))
    if required_errors:
        print("entity_library: blocked; finalize required sources before indexing: " + ", ".join(required_errors), file=sys.stderr)
        return 2
    if blocked:
        print("entity_library: excluding unfinished sources: " + ", ".join(blocked), file=sys.stderr)
    # Preflight every source before the first write. A blocked book must not
    # leave a mixture of old root indices and newly serialized book folders.
    for book_dir in candidates:
        if book_dir.name in blocked:
            continue
        index, entities, mechanisms = build_book(book_dir)
        books.append(index)
        all_entities.extend(entities)
        all_mechanisms.extend(mechanisms)
        book_out = out / "书目" / book_dir.name
        book_out.mkdir(parents=True, exist_ok=True)
        (book_out / "实体.json").write_text(json.dumps({"source_book": book_dir.name, "entities": entities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (book_out / "机制.json").write_text(json.dumps({"source_book": book_dir.name, "mechanisms": mechanisms}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (book_out / "书目.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    (out / "书目索引.json").write_text(json.dumps({"schema_version": "cross-book-library.v1", "books": [x["source_book"] for x in books], "book_count": len(books)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "实体索引.json").write_text(json.dumps({"schema_version": "cross-book-entity-index.v1", "read_policy": "index_only; authorization required", "entities": all_entities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "机制索引.json").write_text(json.dumps({"schema_version": "cross-book-mechanism-index.v1", "read_policy": "mechanism_only; no prose voice or complete event chain", "mechanisms": all_mechanisms}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"entity_library: generated books={len(books)} entities={len(all_entities)} mechanisms={len(all_mechanisms)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
