#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ACTION_VERBS = (
    "拦", "卡", "夺", "抢", "按", "压", "抬", "护", "逼", "扔", "接", "踹", "撞", "拖", "翻", "拽",
    "喝", "站", "带", "守", "点", "报", "拿", "推", "落", "改", "换",
)
STOP_NAMES = {
    "第七武校", "教育署", "驻防军", "灰骨猎团", "后勤处", "旁听生", "总务主任", "裁撤代表", "公开实训",
    "营养剂", "走廊", "通知", "名单", "校门", "仓道", "后仓", "台账", "角色状态",
}
NON_ROLE_SUFFIXES = (
    "仓", "棚", "线", "批", "库", "河", "驿", "站", "台", "场", "湾", "门", "路", "口", "区", "营", "队",
    "机房", "码头", "名单", "账", "案", "灶", "粮", "车",
)
NON_NAME_TAILS = ("已经", "还是", "不是", "别再", "先把", "今晚", "今夜", "这个", "那条")
ALIAS_SUFFIXES = ("头儿", "掌柜", "老大", "爷", "哥", "姐", "叔", "伯")
ALIAS_MAP = {
    "韩头儿": "韩守忠",
}


@dataclass
class Candidate:
    name: str
    chapters: list[str]
    action_hits: int
    has_card: bool


def find_project_root(path: Path) -> Path:
    if path.is_file():
        path = path.parent
    for parent in (path, *path.parents):
        if (parent / "正文").exists() or (parent / "追踪").exists() or (parent / "设定").exists():
            return parent
    return path


def chapter_files(project_root: Path) -> list[Path]:
    body_dir = project_root / "正文"
    if not body_dir.exists():
        return []
    files = [path for path in body_dir.glob("*.md") if re.search(r"第\d+章", path.name)]
    return sorted(files, key=lambda p: int(re.search(r"第(\d+)章", p.name).group(1)))


def chapter_label(path: Path) -> str:
    match = re.search(r"(第\d+章)", path.name)
    return match.group(1) if match else path.stem


def existing_cards(project_root: Path) -> set[str]:
    role_dir = project_root / "设定" / "角色"
    if not role_dir.exists():
        return set()
    return {path.stem for path in role_dir.glob("*.md")}


def tracked_names(project_root: Path) -> set[str]:
    role_state = project_root / "追踪" / "角色状态.md"
    if not role_state.exists():
        return set()
    text = role_state.read_text(encoding="utf-8")
    return set(re.findall(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))


def extract_candidates(text: str) -> set[str]:
    counts: dict[str, int] = {}
    for name in re.findall(r"[一-龥]{2,4}", text):
        if name in STOP_NAMES:
            continue
        if any(name.endswith(tail) for tail in NON_NAME_TAILS):
            continue
        if name.startswith(("第", "东", "西", "南", "北")) and any(name.endswith(suffix) for suffix in NON_ROLE_SUFFIXES):
            continue
        if any(name.endswith(suffix) for suffix in NON_ROLE_SUFFIXES):
            continue
        counts[name] = counts.get(name, 0) + 1
    return {name for name, count in counts.items() if count >= 3}


def action_hits_for(name: str, text: str) -> int:
    total = 0
    for line in text.splitlines():
        if name not in line:
            continue
        if any(verb in line for verb in ACTION_VERBS):
            total += 1
    return total


def resolve_alias(name: str, known_names: set[str], chapter_known_names: set[str]) -> str:
    if name in ALIAS_MAP:
        return ALIAS_MAP[name]
    if name in known_names:
        return name
    search_space = chapter_known_names or known_names
    for suffix in ALIAS_SUFFIXES:
        if not name.endswith(suffix) or len(name) <= len(suffix):
            continue
        surname = name[0]
        surname_matches = sorted(
            candidate
            for candidate in search_space
            if candidate.startswith(surname) and candidate != name and not candidate.endswith(suffix)
        )
        if len(surname_matches) == 1:
            return surname_matches[0]
    return name


def detect(project_root: Path) -> list[Candidate]:
    cards = existing_cards(project_root)
    tracked = tracked_names(project_root)
    known_names = cards | tracked
    by_name: dict[str, dict[str, object]] = {}

    for chapter in chapter_files(project_root):
        text = chapter.read_text(encoding="utf-8")
        label = chapter_label(chapter)
        chapter_known_names = {candidate for candidate in known_names if candidate in text}
        candidate_pool = extract_candidates(text) | known_names
        for name in candidate_pool:
            canonical = resolve_alias(name, known_names, chapter_known_names)
            hits = action_hits_for(name, text)
            if hits <= 0:
                continue
            record = by_name.setdefault(canonical, {"chapters": [], "hits": 0})
            record["chapters"].append(label)
            record["hits"] += hits

    results: list[Candidate] = []
    for name, record in by_name.items():
        if any(name != card and name in card for card in cards):
            continue
        chapters = sorted(set(record["chapters"]))
        if len(chapters) < 2:
            continue
        results.append(
            Candidate(
                name=name,
                chapters=chapters,
                action_hits=int(record["hits"]),
                has_card=name in cards,
            )
        )
    results.sort(key=lambda item: (-len(item.chapters), -item.action_hits, item.name))
    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Detect likely promoted key characters missing role cards.")
    parser.add_argument("path", help="Novel project root or any file inside the project")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON result")
    args = parser.parse_args(argv)

    project_root = find_project_root(Path(args.path))
    candidates = detect(project_root)
    missing = [item for item in candidates if not item.has_card]

    payload = {
        "ok": not missing,
        "project_root": str(project_root),
        "summary": {
            "candidates": len(candidates),
            "missing_cards": len(missing),
        },
        "candidates": [asdict(item) for item in candidates],
    }

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
