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


CONTRACT_LAYOUT_SCHEMA = ContractLayout(
    root_dirs=["原文", "原文细节库", "写作资产"],
    root_files=[
        "_sample_comparison.md",
        "事实与推断台账.md",
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
        "原文资产候选池.md",
        "本书动态信号字典.json",
        "profile_source.md",
        "桥段施工卡.md",
    ],
)

SKILL_FINGERPRINT_FILES = (
    "skills/story-short-analyze/SKILL.md",
    "skills/story-short-analyze/scripts/prepare_short_analyze_job.py",
    "skills/story-short-analyze/scripts/run_short_analyze_finalize.py",
    "skills/story-short-analyze/scripts/validate_short_analyze_outputs.py",
    "skills/story-short-analyze/references/pipeline/stage-00-intake-and-sampling.md",
    "skills/story-short-analyze/references/pipeline/stage-01-main-report-batch.md",
    "skills/story-short-analyze/references/pipeline/stage-02-ledger-and-tables-batch.md",
    "skills/story-short-analyze/references/pipeline/stage-03-detail-assets-batch.md",
    "skills/story-short-analyze/references/pipeline/stage-04-profile-and-finalize-batch.md",
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
        raise FileNotFoundError(f"缺少输出合同，禁止使用默认清单兜底：{contract}")
    text = read_text(contract)
    match = re.search(r"```[\r\n]+拆文库/\{书名\}/\n([\s\S]*?)```", text)
    if not match:
        raise ValueError(f"无法解析输出合同文件树，禁止使用默认清单兜底：{contract}")

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
    if not parsed.root_dirs or not parsed.root_files:
        raise ValueError(f"输出合同文件树为空或不完整，禁止继续初始化：{contract}")
    if parsed != CONTRACT_LAYOUT_SCHEMA:
        raise ValueError(
            "输出合同与初始化脚本清单不一致，禁止使用任一侧兜底继续："
            f"contract={parsed} schema={CONTRACT_LAYOUT_SCHEMA}"
        )
    return parsed


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


def compute_skill_fingerprint() -> str:
    repo_root = repo_root_from_script()
    digest = hashlib.sha1()
    for rel in SKILL_FINGERPRINT_FILES:
        path = repo_root / rel
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        if not path.exists():
            digest.update(b"MISSING")
            digest.update(b"\0")
            continue
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_meta(path: Path, word_count: int, book_name: str, source_text: str) -> None:
    payload = {
        "version": "2.0",
        "skill_fingerprint": compute_skill_fingerprint(),
        "word_count": word_count,
        "source_label": book_name,
        "title_status": "verified-in-source" if book_name and book_name in source_text else "unverified-filename",
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
        "- [ ] 已完成 `_sample_comparison.md`，并实际读取所选样本的 README、原文和正反例对照",
        "- [ ] 模型人工复核：主报告写完后已回看样本反例区并记录是否回炉",
        "- [ ] 模型人工复核：事实台账已对照原文核清主体、双时间轴和证据来源",
        "- [ ] 已按 skill 完成主报告批",
        "- [ ] 模型人工复核：主报告与节点已区分信息释放顺序和故事实际时间线",
        "- [ ] 已按 skill 完成 16 张可直接仿写表",
        "- [ ] 已按 skill 完成原文细节库 8 类",
        "- [ ] 已按 skill 完成写作资产全包",
        "- [ ] 模型人工复核：profile生成后已检查整句资产、标题边界和特殊羞辱机制",
        "- [ ] 模型人工复核：finalize前已读取脚本结果并完成最后语义纠偏",
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
        "目标不是只写分析结论，而是按快速厚拆批次完整产出 skill 定义过的整套拆书资料包，并在结束前通过收口验收。",
        "默认大批量连续落盘：只减少模型往返和重复回读，不降低任何文件合同或厚度门槛。",
        "默认按厚拆模式执行：不能满足于“文件齐了、脚本过了”，而要先把主报告、节点和手法拆到能直接指导仿写的厚度。",
        "",
        "## 本次固定上下文",
        f"- 任务名：`{book_name}`（默认来自文件名，不等于已验证标题）",
        f"- 原文路径：`{source_copy}`",
        f"- 输出目录：`{out_dir}`",
        f"- 原文总行数：`{lines_total}`",
        f"- 自动识别章节标记数：`{len(chapters)}`",
        f"- 读取分块数：`{len(chunks)}`",
        f"- 尾部校验锚点：`L{anchor['line']} {anchor['text']}`",
        "",
        "## 固定执行顺序",
        "1. 先读 `skills/story-short-analyze/SKILL.md`",
        "2. 再读 `skills/story-short-analyze/references/pipeline/staged-execution-index.md`",
        "3. 先按 `stage-00-intake-and-sampling.md` 完成原文覆盖与 few-shot 减载选择",
        "4. 按当前阶段只加载对应阶段文档，不要一次吞完整套执行 prompt 和全部样例",
        "5. 按 `_source_reading_plan.md` 的全部分块读到 EOF，完成原文覆盖确认",
        "6. 读完原文后先落 `_sample_comparison.md`，记录所选样本文件、正反例锚点和将影响的正式文件",
        "7. 按 `样本对照 -> 事实台账 -> 拆文报告 -> 样本反例复核 -> 情节节点 -> 写作手法+meta -> 字典+候选池 -> 16张表8+8 -> 细节库整批 -> 常规资产批 -> 高敏资产批 -> profile -> 验收` 完整落盘",
        "8. 最后运行：",
        f"   `python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json`",
        "",
        "## 当前只记住这些硬约束",
        "- 读完原文后先写过程审计文件 `_sample_comparison.md`；第一个内容产物仍必须是 `事实与推断台账.md`",
        "- 禁止任何兜底生成、自动补写、自动扩写、通用模板代填或跨书内容借位；信息不足就停在当前阶段并报错",
        "- 原文与样本只完整读取一次；后续使用 `_sample_comparison.md`、事实台账、节点、候选池和精确原文切片",
        "- 16 张表默认按 8+8 两批，细节库默认整批，写作资产按常规+高敏两批；失败批次先二分，仍失败才降级为双文件",
        "- 批量模式不得压缩表格行数、细节卡数量、有效字符或高敏桥解释层",
        "- 主报告层（`事实台账 / 拆文报告 / 情节节点 / 写作手法 / profile_source`）优先级最高，不能压薄",
        "- 如果某一批开始明显压缩化，优先冷启动该批并只重载对应 `stage-*.md`",
        "- 冷启动只用于验证 skill 是否修好；冷启动目录、旧拆文目录、`bak` 目录都不能当正式产物来源",
        "- 冷启动跑通后，要把修复落实到正式 skill，再让正式目录按同一流程重新产出；不能靠拷贝测试目录回灌正式结果",
        "- few-shot 只选 1-2 本最相关样例，不能整套吞样例；每本必须实际读取 README、原文相关段和正反例对照，并在 `_sample_comparison.md` 留下证据",
        "- 禁止把别本拆书目录、旧 profile、bak 产物当 few-shot；只允许使用 skill 内置 `references/examples/`",
        "- 写完主报告后必须回看所选样本反例区，并把“未滑入反例 / 需要回炉”的裁决写回 `_sample_comparison.md`",
        "- 最终必须跑 `run_short_analyze_finalize.py`；没通过不算完成",
        "- `run_short_analyze_finalize.py` 只允许生成 `book.profile.json` 和执行校验，禁止修改任何 Markdown 正式产物",
        "- `profile_source.md` 的 `## 7. 禁句 / 禁写法` 里，每条禁写法后必须补 `- 为什么假：...`；少于 2 条视为当前批未完成",
        "- `scene_assets.public_explosion / scene_assets.external_order` 必须拆成多条独立事件，不要用分号把 4 个场面塞成 1 条",
        "- `情节节点.md` 不能只保开头链和终局链；默认至少保 1 条中段承重链，单节点原文范围尽量控制在 80 行内，过宽就继续拆细",
        "- `事实与推断台账.md` 里的单条事实不要吞大段剧情；遇到中段承重桥，宁可拆成 2-3 条 `Fxx`，也不要写成一个超宽范围",
        "- 16 张表不能只靠表后总结过检；表格本身要带原文证据列或同语义列，并且每行都要有迁移字段",
        "- 16 张表优先保表格承重：8000 字以上样本里，`物件/动作/对白功能/钩子/微动作/失控说话` 默认至少保 5 条独立资产行，`公开炸场` 默认至少保 4 条，`顺序事件/对话衔接/误判/安静压迫场/人物偏手/烂关系漏出/后果链` 默认至少保 4 条，`导语拆解/外部秩序` 默认至少保 3 条；解释层再厚也不能代替表格行",
        "- 16 张表后面的 `可直接借的承重结构 / 迁移顺序提醒 / 为什么这个顺序不能乱` 都必须直接点名本表条目，不能只写抽象总结",
        "- `原文资产候选池.md` 里凡是标记“已收录”的资产，目标文件里必须能搜到同名资产名或原文锚点；搜不到就算漏收",
        "- `原文资产候选池.md` 某一表如果已收录了 4-6 条独立候选，目标表就应当至少有同量级行数；不要把 5 条候选压成 3 行‘更概括的总结’",
        "- `原文资产候选池.md` 如果某类资产原文确实没有，必须显式写“已扫，原文未发现”，不能空着",
        "- `profile_source.md`、16 张表和 `book.profile.json.style_assets` 的原文资产，只写原文能逐字命中的短语/短句；解释句、总结句一律改写进说明层或 `derived_patterns`",
        "- `story_guardrails.character_face_split`、中段承重桥 `BID`、`桥段角色` 必须贯通 `拆文报告 / 情节节点 / 对应仿写表 / 高敏桥段识别 / 桥段施工卡 / profile_source / book.profile.json`",
        "- `写作手法.md` 不能只写结构概括，至少要补到 `活词 / 句法模板 / 段落节拍 / 反面仿写句` 这一级",
        "- 收口前必须把 `_progress.md` 的模型人工复核项清掉；只要还挂着未完成复核，就视为没拆完",
        "",
        "## 详细规则去哪里看",
        "- 入口与抽样：`stage-00-intake-and-sampling.md`",
        "- 主报告微批：`stage-01-main-report-batch.md`",
        "- 字典、候选池、16 张表：`stage-02-ledger-and-tables-batch.md`",
        "- 细节库与写作资产：`stage-03-detail-assets-batch.md`",
        "- profile 与收口：`stage-04-profile-and-finalize-batch.md`",
        "- 具体字段模板：`output-templates.md`",
        "- 收口契约与复核：`output-contract.md`、`quality-checklist.md`",
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

    write_meta(out_dir / "_meta.json", word_count, book_name, text)
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
        "next_step": {
            "read_order": [
                "skills/story-short-analyze/SKILL.md",
                "skills/story-short-analyze/references/pipeline/staged-execution-index.md",
                "skills/story-short-analyze/references/pipeline/stage-00-intake-and-sampling.md",
            ],
            "then": "按 _source_reading_plan.md 读完整本原文，再进入事实台账串行批",
            "finalize_after_all_files": f"python3 skills/story-short-analyze/scripts/run_short_analyze_finalize.py \"{out_dir}\" --json",
        },
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
        print("next_step:")
        if isinstance(payload["next_step"], dict):
            print("  read_order:")
            for item in payload["next_step"].get("read_order", []):
                print(f"  - {item}")
            print(f"  then: {payload['next_step'].get('then', '')}")
            print(f"  finalize_after_all_files: {payload['next_step'].get('finalize_after_all_files', '')}")
        else:
            print(f"  {payload['next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
