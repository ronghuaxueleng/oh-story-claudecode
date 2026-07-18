#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {
            "version": 1,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "stages": {},
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是对象")
    if not isinstance(data.get("stages"), dict):
        data["stages"] = {}
    return data


def save_state(path: Path, data: dict) -> None:
    data["updated_at"] = utc_now()
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_stage(root: Path, action: str, stage: str, note: str) -> dict:
    path = root / "_timing.json"
    data = load_state(path)
    stages = data["stages"]
    entry = stages.setdefault(stage, {})
    now_epoch = time.time()

    if action == "start":
        entry.clear()
        entry.update(
            {
                "status": "running",
                "started_at": utc_now(),
                "started_epoch": now_epoch,
            }
        )
    elif action == "finish":
        started_epoch = entry.get("started_epoch")
        if not isinstance(started_epoch, (int, float)):
            raise ValueError(f"阶段 `{stage}` 尚未 start，不能 finish")
        entry.update(
            {
                "status": "completed",
                "finished_at": utc_now(),
                "elapsed_seconds": round(now_epoch - started_epoch, 3),
            }
        )
    else:
        entry.update(
            {
                "status": "marked",
                "marked_at": utc_now(),
            }
        )

    if note:
        entry["note"] = note
    save_state(path, data)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description="记录短篇拆文各阶段真实耗时")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("action", choices=("start", "finish", "mark"))
    parser.add_argument("stage", help="阶段标识，如 intake / foundation / assets / finalize")
    parser.add_argument("--note", default="", help="可选备注")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    try:
        entry = update_stage(root, args.action, args.stage, args.note)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 2

    payload = {
        "ok": True,
        "root": str(root),
        "stage": args.stage,
        "entry": entry,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{args.stage}: {entry.get('status')}")
        if "elapsed_seconds" in entry:
            print(f"elapsed_seconds: {entry['elapsed_seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
