#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FORBIDDEN_LITERALS = [
    "狠狠干",
    "*** Begin Patch",
    "*** End Patch",
    "functions.",
    "multi_tool_use.",
    "commentary",
    "analysis",
]

REPLACEABLE_LITERALS = {
    "狠狠干": "",
}

TAIL_PATTERNS = [
    r"[一-龥]{2,}(?:\?|？)\s*(?:no|wait|stop)\b",
    r"[一-龥]{2,}\s*\.\.\.\s*(?:no|wait|stop)\b",
    r"[一-龥]{2,}(?:no|wait|stop)\b",
    r"\b(?:no|wait|stop)\b\s*$",
]

SENTENCE_END = "。！？\n"


def find_first_hit(text: str) -> tuple[int, str] | None:
    hits: list[tuple[int, str]] = []
    for needle in FORBIDDEN_LITERALS:
        idx = text.find(needle)
        if idx != -1:
            hits.append((idx, needle))
    for pattern in TAIL_PATTERNS:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            hits.append((m.start(), pattern))
    if not hits:
        return None
    return min(hits, key=lambda item: item[0])


def find_safe_cut(text: str, hit_at: int) -> int:
    for i in range(hit_at - 1, -1, -1):
        if text[i] in SENTENCE_END:
            return i + 1
    return 0


def normalize_text(text: str) -> tuple[str, list[str]]:
    changed: list[str] = []
    for needle, repl in REPLACEABLE_LITERALS.items():
        if needle in text:
            text = text.replace(needle, repl)
            changed.append(needle)
    text = re.sub(r"，\s*，", "，", text)
    text = re.sub(r"。\s*。", "。", text)
    text = re.sub(r"\s+\n", "\n", text)
    return text, changed


def process(path: Path, apply_fix: bool) -> dict:
    text = path.read_text(encoding="utf-8")
    text, replaced = normalize_text(text)
    if apply_fix and replaced:
        path.write_text(text, encoding="utf-8")
    hit = find_first_hit(text)
    if not hit:
        return {"ok": True, "changed": bool(replaced), "reason": "clean", "replaced": replaced}

    hit_at, marker = hit
    ratio = hit_at / max(len(text), 1)
    if ratio < 0.7:
        return {
            "ok": False,
            "changed": bool(replaced),
            "reason": "hit_too_early",
            "marker": marker,
            "offset": hit_at,
            "replaced": replaced,
        }

    cut = find_safe_cut(text, hit_at)
    new_text = text[:cut].rstrip() + "\n"
    if apply_fix:
        path.write_text(new_text, encoding="utf-8")
    return {
        "ok": True,
        "changed": True,
        "reason": "tail_trimmed",
        "marker": marker,
        "offset": hit_at,
        "cut_at": cut,
        "replaced": replaced,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Trim trailing draft pollution from chapter text.")
    parser.add_argument("file", help="Chapter file to inspect")
    parser.add_argument("--fix", action="store_true", help="Apply safe tail trim in place")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON result")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        payload = {"ok": False, "changed": False, "reason": "missing_file", "path": str(path)}
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"missing_file: {path}")
        return 1

    result = process(path, args.fix)
    result["path"] = str(path)
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
