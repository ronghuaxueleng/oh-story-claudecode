#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ContractLayout:
    root_dirs: list[str]
    root_files: list[str]
    detail_files: list[str]
    asset_files: list[str]


DEFAULT_LAYOUT = ContractLayout(
    root_dirs=["原文", "原文细节库", "写作资产"],
    root_files=[
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
        "book.profile.json",
        "拆文报告.md",
        "情节节点.md",
        "写作手法.md",
        "_meta.json",
    ],
    detail_files=[
        "场景细节库.md",
        "关系细节库.md",
        "情绪细节库.md",
        "对白细节库.md",
        "翻车细节库.md",
        "旧伤细节库.md",
        "动作细节库.md",
        "场面细节库.md",
    ],
    asset_files=[
        "母结构_故事走法.md",
        "主冲突_副升级器.md",
        "异物清单.md",
        "第二层冲突清单.md",
        "角色口气模板.md",
        "关系重组方式.md",
        "公开场_关键硬牌_后果.md",
        "平台适配提醒.md",
        "情绪母线.md",
        "新状态清单.md",
        "虐点对照细节.md",
        "样本分级与可学层.md",
        "高敏桥段识别.md",
        "作者DNA指纹.md",
        "仿写约束_禁写清单.md",
        "同桥段过检规则.md",
        "profile_source.md",
    ],
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def parse_output_contract() -> ContractLayout:
    contract = repo_root_from_script() / "skills" / "story-short-analyze" / "references" / "pipeline" / "output-contract.md"
    if not contract.exists():
        return DEFAULT_LAYOUT
    text = read_text(contract)
    match = re.search(r"```[\r\n]+拆文库/\{书名\}/\n([\s\S]*?)```", text)
    if not match:
        return DEFAULT_LAYOUT

    root_dirs: list[str] = []
    root_files: list[str] = []
    detail_files: list[str] = []
    asset_files: list[str] = []
    current_dir: str | None = None

    for raw_line in match.group(1).splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if "──" not in line:
            continue
        name = line.split("──", 1)[1].strip()
        if not name:
            continue
        depth = line.count("│") + line.count("    ")
        is_dir = name.endswith("/")
        clean_name = name.rstrip("/")
        if depth == 0:
            if is_dir:
                root_dirs.append(clean_name)
                current_dir = clean_name
            else:
                root_files.append(clean_name)
                current_dir = None
            continue
        if current_dir == "原文细节库":
            detail_files.append(clean_name)
        elif current_dir == "写作资产":
            asset_files.append(clean_name)

    parsed = ContractLayout(
        root_dirs=root_dirs,
        root_files=root_files,
        detail_files=detail_files,
        asset_files=asset_files,
    )
    return parsed if parsed.root_dirs and parsed.root_files else DEFAULT_LAYOUT


def count_source_units(text: str) -> int:
    compact = re.sub(r"\s+", "", text)
    return len(compact)


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_meta(path: Path, word_count: int) -> None:
    payload = {
        "version": "2.0",
        "word_count": word_count,
        "genre_detected": "通用",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "stages_completed": [],
        "last_stage_in_progress": None,
        "structure_counts": {
            "beats": 0,
            "hooks": 0,
            "setup_clues": 0,
            "character_archetypes": 0,
            "reusable_structures": 0,
            "reversal_type": "",
        },
    }
    dump_json(path, payload)


def write_required_manifest(path: Path, book_name: str, source_path: Path, layout: ContractLayout) -> None:
    payload = {
        "book_name": book_name,
        "source_file": str(source_path),
        "required": {
            "root_dirs": layout.root_dirs,
            "root_files": layout.root_files,
            "detail_files": layout.detail_files,
            "asset_files": layout.asset_files,
        },
        "final_gate": {
            "prepare": f"python3 skills/story-short-analyze/scripts/prepare_short_analyze_job.py \"{source_path}\"",
            "finalize": f"python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"拆文库/{book_name}\" --json",
        },
    }
    dump_json(path, payload)


def write_source_manifest(path: Path, source_path: Path, copied_path: Path, text: str) -> None:
    payload = {
        "source_file": str(source_path),
        "copied_to": str(copied_path),
        "sha1": sha1_file(source_path),
        "char_count_no_whitespace": count_source_units(text),
    }
    dump_json(path, payload)


def write_progress(path: Path, book_name: str, layout: ContractLayout) -> None:
    lines = [
        f"# {book_name} 拆书进度",
        "",
        "## 当前状态",
        "- [x] 已创建标准拆文目录",
        "- [x] 已复制原文到 `原文/`",
        "- [x] 已写入 `_meta.json`、`_required_outputs.json`、`_source_manifest.json`",
        "- [ ] 已按 skill 完成主报告批",
        "- [ ] 已按 skill 完成 16 张可直接仿写表",
        "- [ ] 已按 skill 完成原文细节库 8 类",
        "- [ ] 已按 skill 完成写作资产全包",
        "- [ ] 已运行 `run_short_analyze_finalize.py` 并通过",
        "",
        "## 根目录必产文件",
    ]
    for name in layout.root_files:
        lines.append(f"- [ ] `{name}`")
    lines.extend([
        "",
        "## 原文细节库必产文件",
    ])
    for name in layout.detail_files:
        lines.append(f"- [ ] `原文细节库/{name}`")
    lines.extend([
        "",
        "## 写作资产必产文件",
    ])
    for name in layout.asset_files:
        lines.append(f"- [ ] `写作资产/{name}`")
    lines.extend([
        "",
        "## 最终验收",
        f"- [ ] `python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"拆文库/{book_name}\" --json`",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_execution_prompt(path: Path, book_name: str, source_copy: Path, out_dir: Path) -> None:
    lines = [
        f"# {book_name} 正式拆书执行提示",
        "",
        "你现在执行 `story-short-analyze` 正式拆书。",
        "目标不是只写分析结论，而是一次性自动产出 skill 定义过的整套拆书资料包，并在结束前通过收口验收。",
        "",
        "## 本次固定上下文",
        f"- 书名：`{book_name}`",
        f"- 原文路径：`{source_copy}`",
        f"- 输出目录：`{out_dir}`",
        "",
        "## 固定执行顺序",
        "1. 先读 `skills/story-short-analyze/SKILL.md`",
        "2. 再读 `skills/story-short-analyze/references/pipeline/short-analyze-execution-prompt.md`",
        "3. 按 `主报告批 -> 16张表批 -> 原文细节库批 -> 写作资产批 -> profile批 -> 验收批` 完整落盘",
        "4. 最后运行：",
        f"   `python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json`",
        "",
        "## 强约束",
        "- 不能只产三件套后停下",
        "- 不能把 16 张表写成同一种说明腔",
        "- 不能把原文细节库写成泛化模板壳句",
        "- `profile_source.md` 必须满足 `- 开头信号：` 至少 3 条、`- 为什么假：` 至少 2 条",
        "- 收口脚本没通过，不算拆完",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare(args: argparse.Namespace) -> dict:
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"源文件不存在：{source}")

    book_name = args.name or source.stem
    output_root = Path(args.output_root).resolve() if args.output_root else source.parent / "拆文库"
    out_dir = output_root / book_name

    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise FileExistsError(f"输出目录已存在且非空：{out_dir}；如需覆盖请加 --force")

    if args.force and out_dir.exists():
        shutil.rmtree(out_dir)

    layout = parse_output_contract()
    out_dir.mkdir(parents=True, exist_ok=True)
    for dirname in layout.root_dirs:
        (out_dir / dirname).mkdir(parents=True, exist_ok=True)

    source_copy = out_dir / "原文" / source.name
    shutil.copy2(source, source_copy)

    text = read_text(source)
    word_count = count_source_units(text)

    write_meta(out_dir / "_meta.json", word_count)
    write_required_manifest(out_dir / "_required_outputs.json", book_name, source, layout)
    write_source_manifest(out_dir / "_source_manifest.json", source, source_copy, text)
    write_progress(out_dir / "_progress.md", book_name, layout)
    write_execution_prompt(out_dir / "_execution_prompt.md", book_name, source_copy, out_dir)

    created = {
        "book_name": book_name,
        "root": str(out_dir),
        "source_copy": str(source_copy),
        "char_count_no_whitespace": word_count,
        "created_files": [
            "_meta.json",
            "_required_outputs.json",
            "_source_manifest.json",
            "_progress.md",
            "_execution_prompt.md",
        ],
        "created_dirs": layout.root_dirs,
        "next_step": f"python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json",
    }
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="短篇拆书入口初始化：建立标准目录、复制原文、写入必产清单")
    parser.add_argument("source", help="原始 TXT / Markdown / 文本文件路径")
    parser.add_argument("--name", help="书名；默认取源文件名（去后缀）")
    parser.add_argument("--output-root", help="拆文库目录；默认使用源文件同级 `拆文库/`")
    parser.add_argument("--force", action="store_true", help="若输出目录已存在，则先删除再重建")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        payload = prepare(args)
    except Exception as exc:  # noqa: BLE001
        error_payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(error_payload, ensure_ascii=False, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 2

    payload["ok"] = True
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"book_name: {payload['book_name']}")
        print(f"root: {payload['root']}")
        print(f"source_copy: {payload['source_copy']}")
        print(f"char_count_no_whitespace: {payload['char_count_no_whitespace']}")
        print("created_files:")
        for item in payload["created_files"]:
            print(f"- {item}")
        print("created_dirs:")
        for item in payload["created_dirs"]:
            print(f"- {item}")
        print(f"next_step: {payload['next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
