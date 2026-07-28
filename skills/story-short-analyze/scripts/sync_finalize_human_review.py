#!/usr/bin/env python3
"""Synchronize the finalize human-review receipt without auto-resolving judgments."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def load_validator() -> Any:
    path = Path(__file__).with_name("validate_short_analyze_outputs.py")
    spec = importlib.util.spec_from_file_location("short_analyze_validator_for_review_sync", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"无法加载 validator：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_existing(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def pending_review(scope: str) -> dict[str, Any]:
    return {"scope": scope, "status": "pending", "judgement": "", "evidence": []}


def pending_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "category": item["category"],
        "message": item["message"],
        "status": "pending",
        "judgement": "",
        "evidence": [],
    }


def sync_receipt(root: Path) -> tuple[Path, dict[str, Any], bool]:
    root = root.resolve()
    validator = load_validator()
    receipt_path = root / "_finalize_human_review.json"
    existing = load_existing(receipt_path)
    _, current_manifest = validator.write_content_fingerprint_manifest(root)
    current_fingerprint_ref = validator.content_fingerprint_reference(current_manifest)
    current_fingerprint = validator.compute_skill_fingerprint()
    current_content_matches = existing.get("content_fingerprint") == current_fingerprint_ref
    if not current_content_matches:
        current_content_matches = validator.legacy_markdown_sha1s_match(
            root, existing.get("formal_markdown_sha1s")
        )
    content_unchanged = current_content_matches and (
        existing.get("skill_fingerprint") == current_fingerprint
    )
    _, notes = validator.validate(root)
    expected_items = validator.build_human_review_items(root, notes)

    old_reviews = {
        item.get("scope"): item
        for item in existing.get("upgrade_reviews", [])
        if isinstance(item, dict)
    }
    old_items = {
        item.get("id"): item
        for item in existing.get("review_items", [])
        if isinstance(item, dict)
    }
    if content_unchanged:
        upgrade_reviews = [
            old_reviews.get(scope, pending_review(scope))
            for scope in validator.UPGRADE_REVIEW_SCOPES
        ]
        review_items = []
        for expected in expected_items:
            previous = old_items.get(expected["id"])
            if previous:
                merged = dict(previous)
                merged.update({
                    "id": expected["id"],
                    "category": expected["category"],
                    "message": expected["message"],
                })
                review_items.append(merged)
            else:
                review_items.append(pending_item(expected))
    else:
        upgrade_reviews = [pending_review(scope) for scope in validator.UPGRADE_REVIEW_SCOPES]
        review_items = [pending_item(item) for item in expected_items]

    payload = {
        "version": 2,
        "skill_fingerprint": current_fingerprint,
        "upgrade_status": (
            existing.get("upgrade_status", "pending_content_review")
            if content_unchanged
            else "pending_content_review"
        ),
        "upgrade_reviews": upgrade_reviews,
        "content_fingerprint": current_fingerprint_ref,
        "review_items": review_items,
    }
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt_path, payload, content_unchanged


def main() -> int:
    parser = argparse.ArgumentParser(description="同步拆书 finalize 人工复核清单与规范化内容指纹")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    path, payload, preserved = sync_receipt(Path(args.root))
    result = {
        "ok": True,
        "receipt": str(path),
        "content_unchanged": preserved,
        "review_item_count": len(payload["review_items"]),
        "upgrade_review_count": len(payload["upgrade_reviews"]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
