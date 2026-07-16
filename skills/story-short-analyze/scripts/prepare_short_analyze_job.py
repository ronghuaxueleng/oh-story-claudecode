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
        "事实与推断台账.md",
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
        "桥段施工卡.md",
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


def detect_chapter_markers(lines: list[str]) -> list[dict[str, int | str]]:
    markers: list[dict[str, int | str]] = []
    for line_no, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if re.fullmatch(r"(?:第\s*)?\d{1,3}(?:\s*[章节回])?", stripped):
            markers.append({"label": stripped, "line": line_no})
    return markers


def build_source_chunks(lines: list[str], chunk_size: int = 120) -> list[dict[str, int | str]]:
    chunks: list[dict[str, int | str]] = []
    for chunk_id, start_index in enumerate(range(0, len(lines), chunk_size), start=1):
        end_index = min(start_index + chunk_size, len(lines))
        chunk_text = "\n".join(lines[start_index:end_index])
        chunks.append(
            {
                "id": chunk_id,
                "start_line": start_index + 1,
                "end_line": end_index,
                "sha1": hashlib.sha1(chunk_text.encode("utf-8")).hexdigest(),
            }
        )
    return chunks


def tail_anchor(lines: list[str], max_chars: int = 80) -> dict[str, int | str]:
    for line_no in range(len(lines), 0, -1):
        stripped = lines[line_no - 1].strip()
        if stripped:
            return {"line": line_no, "text": stripped[:max_chars]}
    return {"line": 0, "text": ""}


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
    lines = text.splitlines()
    chapter_markers = detect_chapter_markers(lines)
    payload = {
        "source_file": str(source_path),
        "copied_to": str(copied_path),
        "sha1": sha1_file(source_path),
        "copied_sha1": sha1_file(copied_path),
        "char_count_no_whitespace": count_source_units(text),
        "line_count": len(lines),
        "chapter_count": len(chapter_markers),
        "chapter_markers": chapter_markers,
        "chunks": build_source_chunks(lines),
        "tail_anchor": tail_anchor(lines),
    }
    dump_json(path, payload)


def write_source_reading_plan(path: Path, source_copy: Path, text: str) -> None:
    lines = text.splitlines()
    chunks = build_source_chunks(lines)
    chapter_markers = detect_chapter_markers(lines)
    anchor = tail_anchor(lines)
    output = [
        "# 原文读取计划",
        "",
        f"- 原文路径：`{source_copy}`",
        f"- 原文总行数：{len(lines)}",
        f"- 自动识别章节标记数：{len(chapter_markers)}",
        f"- 尾部校验行：L{anchor['line']}",
        f"- 尾部校验锚点：{anchor['text']}",
        "",
        "## 强制读取规则",
        "",
        "- 必须按下面全部分块读到 EOF，不允许把一次有上限的 `sed` / `head` 输出当成全文。",
        "- 每读完一块，确认该块的结束行；全部块完成前不得进入 Stage 2。",
        "- `情节节点.md` 每个节点必须携带 `L起-L止` 与一个能在该范围内找到的短原文锚点。",
        "- 最终 validator 会核对分块覆盖、章节覆盖、尾部覆盖和锚点真实性。",
        "",
        "## 分块命令",
        "",
    ]
    for chunk in chunks:
        output.append(
            f"- Chunk {chunk['id']}："
            f"`nl -ba \"{source_copy}\" | sed -n '{chunk['start_line']},{chunk['end_line']}p'`"
        )
    output.extend(
        [
            "",
            "## 进入 Stage 2 前必须确认",
            "",
            f"- [ ] 已读完全部 {len(chunks)} 个 Chunk",
            f"- [ ] 已读至 L{len(lines)}",
            "- [ ] 已核对最后一节、最后事件、最后关系状态",
            "- [ ] 已准备在 `拆文报告.md` 写入 `### 原文覆盖确认`",
            "",
        ]
    )
    path.write_text("\n".join(output), encoding="utf-8")


def write_progress(path: Path, book_name: str, layout: ContractLayout) -> None:
    lines = [
        f"# {book_name} 拆书进度",
        "",
        "## 当前状态",
        "- [x] 已创建标准拆文目录",
        "- [x] 已复制原文到 `原文/`",
        "- [x] 已写入 `_meta.json`、`_required_outputs.json`、`_source_manifest.json`",
        "- [ ] 已按 `_source_reading_plan.md` 读完全部原文分块并核对 EOF",
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


def write_execution_prompt(
    path: Path,
    book_name: str,
    source_copy: Path,
    out_dir: Path,
    text: str,
) -> None:
    lines_total = len(text.splitlines())
    chunks = build_source_chunks(text.splitlines())
    chapters = detect_chapter_markers(text.splitlines())
    anchor = tail_anchor(text.splitlines())
    lines = [
        f"# {book_name} 正式拆书执行提示",
        "",
        "你现在执行 `story-short-analyze` 正式拆书。",
        "目标不是只写分析结论，而是一次性自动产出 skill 定义过的整套拆书资料包，并在结束前通过收口验收。",
        "默认按厚拆模式执行：不能满足于“文件齐了、脚本过了”，而要先把主报告、节点和手法拆到能直接指导仿写的厚度。",
        "",
        "## 本次固定上下文",
        f"- 书名：`{book_name}`",
        f"- 原文路径：`{source_copy}`",
        f"- 输出目录：`{out_dir}`",
        f"- 原文总行数：`{lines_total}`",
        f"- 自动识别章节标记数：`{len(chapters)}`",
        f"- 读取分块数：`{len(chunks)}`",
        f"- 尾部校验锚点：`L{anchor['line']} {anchor['text']}`",
        "",
        "## 固定执行顺序",
        "1. 先读 `skills/story-short-analyze/SKILL.md`",
        "2. 再读 `skills/story-short-analyze/references/pipeline/short-analyze-execution-prompt.md`",
        "3. 按 `_source_reading_plan.md` 的全部分块读到 EOF，完成原文覆盖确认",
        "4. 按 `主报告批 -> 16张表批 -> 原文细节库批 -> 写作资产批 -> profile批 -> 验收批` 完整落盘",
        "5. 最后运行：",
        f"   `python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json`",
        "",
        "## 强约束",
        "- 原文读取是独立硬闸门；未读完 `_source_reading_plan.md` 的全部分块，不得进入 Stage 2",
        "- 禁止把有行数上限的单次 `sed/head/open` 输出当成全文；必须继续读到 manifest 记录的最后一行",
        "- `拆文报告.md` 必须含 `### 原文覆盖确认`，写明总行数、已读取至、识别章节数、最后事件、尾部原文锚点",
        "- 进入 Stage 2 前先写 `事实与推断台账.md`；至少覆盖 `主体边界 / 时间边界 / 证据来源`",
        "- 台账每条写成 `F序号 | L起-L止 | 锚点：... | 类别：... | 主体：... | 动作：... | 结果：... | 口径：... | 禁止越界：...`",
        "- 高主动性因果判断必须句末回指 `【原文明确 Fxx】` 或 `【人工推断 Fxx】`",
        "- `情节节点.md` 每个 N 节点必须含 `L起-L止`、`锚点：原文短语` 和 `类型 / 情绪 / 涉及 / 状态变化 / 因果`；锚点必须真实存在于对应行范围",
        "- 节点必须覆盖每个自动分块；有章节标记时还必须覆盖每个章节，且最后有效节点必须进入原文最后 10%",
        "- 不允许先把所有文件铺出来，回头再补厚；`主报告批` 必须先过厚拆闸门，后续批次才允许开始",
        "- 如果 token、篇幅或时间紧张，优先保住 `拆文报告.md / 情节节点.md / 写作手法.md / profile_source.md` 的厚拆层，不允许为了平均铺满文件把主报告写薄",
        "- 不能只产三件套后停下",
        "- `拆文报告.md` 不能只保留合规骨架；固定还必须补齐：`#### 1. 脚本硬筛`、`#### 2. 规则拆层判断`、`#### 4. 可学层 / 禁学层`、`#### 5. 后续调用方式`、`### 叙事时间线`、`### 故事核`",
        "- `拆文报告.md` 的 `结构划分` 不能只写概括条目；必须显式写出 `字数范围 / 占比 / 功能 / 对应节`",
        "- `情节节点.md` 必须拆到可施工颗粒度：最低节点数取分档阈值与 `向上取整(原文字数/400)` 的较大值；8000字以上通常不得低于 28 节点",
        "- `情节节点.md` 必须显式保留至少 1 条中段承重桥节点，不能只清开头钩子和终局翻盘",
        "- `写作手法.md` 不允许每节只写 1-2 句总括；`对话手法` 必须显式拆到至少 3 类角色嘴型或口气差，并写清为什么这样成立、怎么迁移、哪里会发假",
        "- 如果原文存在 `办公室冲突 / 公开见血 / 病情暗示 / 搬出家门 / 物件争位 / 私域驱逐` 这类中段承压桥，必须优先保留到主报告、节点和高敏桥里",
        "- 不能把 16 张表写成同一种说明腔",
        "- 16 张表必须保留表名对应的语义列；不能只写任意 4 行证据表",
        "- 不能把原文细节库写成泛化模板壳句",
        "- `profile_source.md` 必须满足 `- 开头信号：` 至少 3 条、`- 为什么假：` 至少 2 条",
        "- `profile_source.md` 必须补齐 `## 7. 禁句 / 禁写法`、`## 8. 场面资产`、`## 9. 后果链`、`## 10. 作者站位高危句`",
        "- `高敏桥段识别.md`、`作者DNA指纹.md`、`同桥段过检规则.md` 必须出现 `原文：` 证据行",
        "- 初始化只建目录和任务元数据，不会预填正式产物；每个正式 Markdown 必须一次写成完整有效版本，禁止先造空壳再追加正式内容",
        "- finalize 会拒绝重复标题、空字段、`桥1/桥段卡1` 占位标题和任何残留模板壳",
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
    write_source_reading_plan(out_dir / "_source_reading_plan.md", source_copy, text)
    write_progress(out_dir / "_progress.md", book_name, layout)
    write_execution_prompt(out_dir / "_execution_prompt.md", book_name, source_copy, out_dir, text)
    source_lines = text.splitlines()
    chapter_markers = detect_chapter_markers(source_lines)
    chunks = build_source_chunks(source_lines)

    created = {
        "book_name": book_name,
        "root": str(out_dir),
        "source_copy": str(source_copy),
        "char_count_no_whitespace": word_count,
        "line_count": len(source_lines),
        "chapter_count": len(chapter_markers),
        "chunk_count": len(chunks),
        "created_files": [
            "_meta.json",
            "_required_outputs.json",
            "_source_manifest.json",
            "_source_reading_plan.md",
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
        print(f"line_count: {payload['line_count']}")
        print(f"chapter_count: {payload['chapter_count']}")
        print(f"chunk_count: {payload['chunk_count']}")
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
