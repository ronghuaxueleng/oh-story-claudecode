#!/usr/bin/env python3
"""Shared lifecycle helpers for large, temporary manual sidecars."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


CONSUMED_SCHEMA = "story-short-write.consumed-sidecar.v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_sidecar_receipt_sha(sidecar_path: Path, receipt_sha256: str) -> dict[str, Any]:
    """Refresh the top-level receipt_sha256 binding for an active sidecar."""
    resolved = sidecar_path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"侧车不存在，无法刷新 receipt_sha256: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"侧车不是有效 JSON，无法刷新 receipt_sha256: {resolved}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"侧车必须是 JSON 对象，无法刷新 receipt_sha256: {resolved}")
    if str(payload.get("schema_version") or "") == CONSUMED_SCHEMA or payload.get("status") == "consumed":
        raise ValueError(f"已消费侧车不能刷新 receipt_sha256: {resolved}")
    payload["receipt_sha256"] = receipt_sha256
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def consume_sidecar(
    sidecar_path: Path,
    *,
    input_sha256: str,
    receipt_path: Path,
    receipt_sha256: str,
    operation: str,
    counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Replace an applied sidecar with a compact, auditable consumption receipt."""
    resolved_sidecar = sidecar_path.resolve()
    payload: dict[str, Any] = {
        "schema_version": CONSUMED_SCHEMA,
        "status": "consumed",
        "operation": operation,
        "consumed_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "path": str(resolved_sidecar),
            "sha256": input_sha256,
        },
        "applied_receipt": {
            "path": str(receipt_path.resolve()),
            "sha256": receipt_sha256,
        },
    }
    if counts:
        payload["counts"] = counts

    resolved_sidecar.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=resolved_sidecar.parent,
        prefix=f".{resolved_sidecar.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, resolved_sidecar)
    return payload
