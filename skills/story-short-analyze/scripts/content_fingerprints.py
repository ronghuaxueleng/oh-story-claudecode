#!/usr/bin/env python3
"""Canonical content fingerprints shared by short-analysis producers and consumers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FILENAME = "_content_fingerprints.json"
SCHEMA_VERSION = 1
ALGORITHM = "sha256"
NORMALIZATION = "utf8-bomless-lf-v1"
TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".txt"}


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def canonical_text_bytes(path: Path) -> bytes:
    """Normalize encoding, BOM, and newlines without changing other whitespace."""
    return canonical_text(path).encode("utf-8")


def canonical_text(path: Path) -> str:
    """Return canonical text for package embedding and semantic comparison."""
    return read_text(path).lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def asset_sha256(path: Path) -> str:
    payload = canonical_text_bytes(path) if path.suffix.lower() in TEXT_SUFFIXES else path.read_bytes()
    return hashlib.sha256(payload).hexdigest()


def markdown_sha256s(
    root: Path,
    *,
    excluded_names: set[str] | frozenset[str] = frozenset(),
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        if path.is_file() and path.name not in excluded_names:
            hashes[path.relative_to(root).as_posix()] = asset_sha256(path)
    return hashes


def aggregate(files: dict[str, str]) -> str:
    payload = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_manifest(root: Path, *, excluded_names: set[str] | frozenset[str]) -> dict:
    files = markdown_sha256s(root, excluded_names=excluded_names)
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm": ALGORITHM,
        "normalization": NORMALIZATION,
        "scope": "formal_markdown",
        "files": files,
        "aggregate_sha256": aggregate(files),
    }


def write_manifest(
    root: Path,
    *,
    excluded_names: set[str] | frozenset[str],
) -> tuple[Path, dict]:
    path = root / FILENAME
    manifest = build_manifest(root, excluded_names=excluded_names)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)
    return path, manifest


def reference(manifest: dict) -> dict[str, str]:
    return {
        "path": FILENAME,
        "aggregate_sha256": str(manifest.get("aggregate_sha256", "")),
    }


def legacy_sha1s_match(
    root: Path,
    recorded: object,
    *,
    excluded_names: set[str] | frozenset[str],
) -> bool:
    """Recognize legacy raw SHA-1 receipts across LF/CRLF during migration."""
    if not isinstance(recorded, dict) or not recorded:
        return False
    current_paths = {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*.md"))
        if path.is_file() and path.name not in excluded_names
    }
    if set(recorded) != set(current_paths):
        return False
    for relative, path in current_paths.items():
        canonical = canonical_text_bytes(path)
        variants = {
            hashlib.sha1(canonical).hexdigest(),
            hashlib.sha1(canonical.replace(b"\n", b"\r\n")).hexdigest(),
        }
        if recorded.get(relative) not in variants:
            return False
    return True
