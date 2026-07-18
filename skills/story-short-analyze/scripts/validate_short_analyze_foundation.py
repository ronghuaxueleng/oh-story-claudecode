#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path


def load_full_validator():
    path = Path(__file__).with_name("validate_short_analyze_outputs.py")
    spec = importlib.util.spec_from_file_location("short_analyze_full_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载全量 validator：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_full_validator()

FOUNDATION_FILES = (
    "_analysis_brief.md",
    "_sample_comparison.md",
    "事实与推断台账.md",
    "拆文报告.md",
    "情节节点.md",
    "写作手法.md",
    "写作资产/本书动态信号字典.json",
    "写作资产/原文资产候选池.md",
)

BRIEF_REQUIRED_LABELS = (
    "故事核",
    "主角",
    "核心关系",
    "时间边界",
    "固定称谓",
    "BID 注册表",
)

BRIEF_BID_PATTERN = re.compile(
    r"^(?P<id>BID-\d{2})\s*\|\s*L(?P<start>\d+)\s*-\s*L?(?P<end>\d+)"
    r"\s*\|\s*锚点[：:]\s*`?(?P<anchor>[^|`]+)`?"
    r"\s*\|\s*桥段角色[：:]\s*(?P<role>\S.+?)\s*$",
    flags=re.M,
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def check_analysis_brief(root: Path, source_lines: list[str], errors: list[str]) -> list[str]:
    path = root / "_analysis_brief.md"
    if not path.is_file():
        errors.append(f"缺少并发基础契约：{path}")
        return []

    text = read_text(path)
    for label in BRIEF_REQUIRED_LABELS:
        if not re.search(rf"^\s*-\s*{re.escape(label)}[：:]\s*\S+", text, flags=re.M):
            errors.append(f"{path} 缺少非空字段：{label}")

    bids: list[str] = []
    for match in BRIEF_BID_PATTERN.finditer(text):
        bid = match.group("id")
        start = int(match.group("start"))
        end = int(match.group("end"))
        anchor = VALIDATOR.clean_anchor(match.group("anchor"))
        role = match.group("role").strip()
        bids.append(bid)
        if start < 1 or end < start or end > len(source_lines):
            errors.append(f"{path} {bid} 原文范围越界：L{start}-L{end}")
            continue
        if end - start + 1 > 140:
            errors.append(f"{path} {bid} 范围过宽：L{start}-L{end}")
        source_block = "\n".join(source_lines[start - 1:end])
        if len(anchor) < 4:
            errors.append(f"{path} {bid} 锚点过短：`{anchor}`")
        elif anchor not in source_block:
            errors.append(f"{path} {bid} 锚点不在 L{start}-L{end}：`{anchor}`")
        if len(VALIDATOR.normalize_text(role)) < 4:
            errors.append(f"{path} {bid} 桥段角色过短：`{role}`")

    if "原文无独立承重桥" not in text and not bids:
        errors.append(
            f"{path} `BID 注册表` 没有可解析记录；"
            "有承重桥时使用 `BID-01 | L起-L止 | 锚点：... | 桥段角色：...`"
        )
    duplicates = sorted(bid for bid in set(bids) if bids.count(bid) > 1)
    if duplicates:
        errors.append(f"{path} BID 重复：{', '.join(duplicates)}")
    return bids


def check_bid_alignment(root: Path, bids: list[str], errors: list[str]) -> None:
    if not bids:
        return
    for rel in ("拆文报告.md", "情节节点.md"):
        path = root / rel
        if not path.is_file():
            continue
        text = read_text(path)
        missing = [bid for bid in bids if bid not in text]
        if missing:
            errors.append(f"{path} 未贯通 `_analysis_brief.md` BID：{', '.join(missing)}")


def validate(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []

    for rel in FOUNDATION_FILES:
        path = root / rel
        if not path.is_file():
            errors.append(f"缺少 foundation 文件：{path}")
        elif path.suffix == ".md":
            VALIDATOR.check_markdown_hygiene(path, errors)

    manifest_errors: list[str] = []
    manifest = VALIDATOR.load_source_manifest(root, manifest_errors)
    _, source_lines = VALIDATOR.read_manifest_source(root, manifest, manifest_errors)
    errors.extend(manifest_errors)
    if not source_lines:
        return errors, notes

    bids = check_analysis_brief(root, source_lines, errors)
    VALIDATOR.check_sample_comparison(root / "_sample_comparison.md", errors)
    VALIDATOR.check_source_coverage_gate(root, errors, notes)
    VALIDATOR.check_fact_integrity_gate(root, source_lines, errors, notes)

    meta_errors: list[str] = []
    meta = VALIDATOR.check_json_keys(root / "_meta.json", VALIDATOR.META_KEYS, meta_errors)
    errors.extend(meta_errors)
    word_count = meta.get("word_count", 0) if isinstance(meta.get("word_count"), int) else 0

    VALIDATOR.check_contains_all(root / "拆文报告.md", VALIDATOR.REPORT_HEADINGS, errors)
    VALIDATOR.check_contains_all(root / "写作手法.md", VALIDATOR.CRAFT_HEADINGS, errors)
    VALIDATOR.check_report_quality(root / "拆文报告.md", word_count, errors, notes)
    VALIDATOR.check_report_agency_layers(root / "拆文报告.md", errors, notes)
    VALIDATOR.check_plot_nodes_quality(root / "情节节点.md", word_count, errors, notes)
    VALIDATOR.check_craft_quality(root / "写作手法.md", errors, notes)
    check_bid_alignment(root, bids, errors)

    candidate_errors: list[str] = []
    VALIDATOR.check_asset_candidate_ledger(
        root,
        source_lines,
        word_count,
        candidate_errors,
        notes,
    )
    errors.extend(
        item
        for item in candidate_errors
        if "标记已收录，但资产名/锚点未出现在" not in item
    )
    VALIDATOR.check_dynamic_signal_dictionary(root, source_lines, errors, notes)

    if not errors:
        notes.append("foundation 预检通过，可以启动第二波资产 lane。")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="短篇拆书第一波并发产物预检")
    parser.add_argument("root", help="拆文库/{书名} 目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors, notes = validate(root)
    payload = {
        "root": str(root),
        "ok": not errors,
        "status": "ready-for-asset-lanes" if not errors else "blocked-on-foundation",
        "error_count": len(errors),
        "errors": errors,
        "notes": notes,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"root: {root}")
        print(f"status: {payload['status']}")
        for item in errors:
            print(f"- {item}")
        for item in notes:
            print(f"- {item}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
