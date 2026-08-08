#!/usr/bin/env python3
"""Generate and validate the mandatory pre-writing source-reading receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


CORE_FILES = (
    "_sample_comparison.md",
    "book.profile.json",
    "拆文报告.md",
    "情节节点.md",
    "事实与推断台账.md",
    "写作手法.md",
)

TABLE_FILES = (
    "可直接仿写_导语拆解表.md",
    "可直接仿写_顺序事件表.md",
    "可直接仿写_物件表.md",
    "可直接仿写_动作表.md",
    "可直接仿写_对白功能表.md",
    "可直接仿写_对话衔接表.md",
    "可直接仿写_误判表.md",
    "可直接仿写_钩子表.md",
    "可直接仿写_微动作表.md",
    "可直接仿写_安静压迫场表.md",
    "可直接仿写_人物偏手表.md",
    "可直接仿写_失控说话表.md",
    "可直接仿写_烂关系漏出表.md",
    "可直接仿写_外部秩序表.md",
    "可直接仿写_公开炸场表.md",
    "可直接仿写_后果链表.md",
)

DETAIL_FILES = tuple(
    f"原文细节库/{name}"
    for name in (
        "场景细节库.md",
        "关系细节库.md",
        "情绪细节库.md",
        "对白细节库.md",
        "翻车细节库.md",
        "旧伤细节库.md",
        "动作细节库.md",
        "场面细节库.md",
    )
)

ASSET_FILES = tuple(
    f"写作资产/{name}"
    for name in (
        "profile_source.md",
        "母结构_故事走法.md",
        "主冲突_副升级器.md",
        "异物清单.md",
        "第二层冲突清单.md",
        "角色口气模板.md",
        "关系重组方式.md",
        "交流承压拆解.md",
        "冲突载体清单.md",
        "公开场_关键硬牌_后果.md",
        "平台适配提醒.md",
        "情绪母线.md",
        "新状态清单.md",
        "虐点对照细节.md",
        "作者DNA指纹.md",
        "仿写约束_禁写清单.md",
        "同桥段过检规则.md",
        "样本分级与可学层.md",
        "桥段施工卡.md",
        "高敏桥段识别.md",
        "原文资产候选池.md",
        "本书动态信号字典.json",
    )
)

REQUIRED_FILES = CORE_FILES + TABLE_FILES + DETAIL_FILES + ASSET_FILES


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_inventory(root: Path) -> tuple[list[Path], list[str]]:
    errors: list[str] = []
    if not root.is_dir():
        return [], [f"拆文目录不存在: {root}"]

    required = [root / relative for relative in REQUIRED_FILES]
    for path in required:
        if not path.is_file():
            errors.append(f"缺少拆文资产: {path}")

    discovered: set[Path] = {path for path in required if path.is_file()}
    asset_dir = root / "写作资产"
    if asset_dir.is_dir():
        discovered.update(
            path
            for path in asset_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".json"}
        )

    return sorted(discovered, key=lambda path: path.relative_to(root).as_posix()), errors


def create_receipt(project: str, source_dirs: list[Path]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    sources: list[dict[str, Any]] = []
    for index, root in enumerate(source_dirs):
        resolved = root.resolve()
        inventory, source_errors = discover_inventory(resolved)
        errors.extend(source_errors)
        sources.append(
            {
                "name": resolved.name,
                "role": "main" if index == 0 else "auxiliary",
                "root": str(resolved),
                "files": [
                    {
                        "path": path.relative_to(resolved).as_posix(),
                        "sha256": sha256(path),
                        "status": "pending",
                        "evidence_terms": [],
                        "takeaways": [],
                        "used_for": [],
                    }
                    for path in inventory
                ],
            }
        )

    receipt = {
        "version": "1.0",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "confirmed_before_outline": False,
        "confirmed_before_draft": False,
        "sources": sources,
        "cross_source_decisions": [],
    }
    return receipt, errors


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_receipt(
    receipt_path: Path,
    output_paths: list[Path] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        return ["sources 必须是非空列表"], {"source_count": 0, "file_count": 0, "read_count": 0}

    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if data.get("confirmed_before_outline") is not True:
        errors.append("confirmed_before_outline 必须为 true")
    if data.get("confirmed_before_draft") is not True:
        errors.append("confirmed_before_draft 必须为 true")
    if len(sources) > 1 and not nonempty_strings(data.get("cross_source_decisions")):
        errors.append("融合写作必须填写 cross_source_decisions")

    total_files = 0
    read_files = 0
    for source_index, source in enumerate(sources, start=1):
        root = Path(str(source.get("root") or "")).resolve()
        inventory, inventory_errors = discover_inventory(root)
        errors.extend(inventory_errors)
        expected = {path.relative_to(root).as_posix(): path for path in inventory}
        file_entries = source.get("files")
        if not isinstance(file_entries, list):
            errors.append(f"sources[{source_index}].files 必须是列表")
            continue
        actual = {
            str(item.get("path") or ""): item
            for item in file_entries
            if isinstance(item, dict) and str(item.get("path") or "")
        }
        missing_entries = sorted(set(expected) - set(actual))
        extra_entries = sorted(set(actual) - set(expected))
        for relative in missing_entries:
            errors.append(f"读取回执缺少文件项: {root / relative}")
        for relative in extra_entries:
            errors.append(f"读取回执含过期文件项: {root / relative}")

        for relative, path in expected.items():
            total_files += 1
            entry = actual.get(relative)
            if not entry:
                continue
            if entry.get("sha256") != sha256(path):
                errors.append(f"文件已变化，必须重新读取: {path}")
            if entry.get("status") != "read":
                errors.append(f"文件尚未标记已读: {path}")
                continue

            evidence_terms = nonempty_strings(entry.get("evidence_terms"))
            takeaways = nonempty_strings(entry.get("takeaways"))
            used_for = nonempty_strings(entry.get("used_for"))
            if not evidence_terms:
                errors.append(f"缺少原文证据词: {path}")
            else:
                source_text = read_text(path)
                missing_terms = [term for term in evidence_terms if term not in source_text]
                if missing_terms:
                    errors.append(f"证据词不在源文件中: {path} -> {' / '.join(missing_terms)}")
            if not takeaways:
                errors.append(f"缺少读取结论: {path}")
            if not used_for:
                errors.append(f"缺少写作用途: {path}")
            if evidence_terms and takeaways and used_for:
                read_files += 1

    for output in output_paths or []:
        resolved = output.resolve()
        if resolved.exists() and receipt_path.stat().st_mtime > resolved.stat().st_mtime:
            errors.append(f"读取回执晚于写作产物，属于事后补填: {resolved}")

    return errors, {
        "source_count": len(sources),
        "file_count": total_files,
        "read_count": read_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mandatory source-reading gate for story-short-write.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="生成待回填的逐文件读取回执")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--source-dir", action="append", required=True)
    init_parser.add_argument("--receipt", required=True)
    init_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="校验读取回执")
    validate_parser.add_argument("--receipt", required=True)
    validate_parser.add_argument(
        "--output",
        action="append",
        required=True,
        help="必须检查的设定、大纲或正文路径；可重复传入",
    )

    args = parser.parse_args()
    if args.command == "init":
        receipt_path = Path(args.receipt).resolve()
        if receipt_path.exists() and not args.force:
            print(f"读取回执已存在，拒绝覆盖: {receipt_path}")
            return 2
        receipt, errors = create_receipt(
            args.project,
            [Path(raw) for raw in args.source_dir],
        )
        if errors:
            print("source_read_gate: blocked")
            for error in errors:
                print(f"- {error}")
            print("- 缺失资产必须重新执行 story-short-analyze 全量拆书，不做兼容回退。")
            return 2
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"source_read_gate: initialized")
        print(f"receipt: {receipt_path}")
        print(f"sources: {len(receipt['sources'])}")
        print(f"files: {sum(len(source['files']) for source in receipt['sources'])}")
        return 0

    receipt_path = Path(args.receipt).resolve()
    if not receipt_path.is_file():
        print(f"读取回执不存在: {receipt_path}")
        return 2
    errors, summary = validate_receipt(
        receipt_path,
        [Path(raw) for raw in args.output],
    )
    print(f"receipt: {receipt_path}")
    print(f"source_count: {summary['source_count']}")
    print(f"file_count: {summary['file_count']}")
    print(f"read_count: {summary['read_count']}")
    if errors:
        print("source_read_gate: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("source_read_gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
