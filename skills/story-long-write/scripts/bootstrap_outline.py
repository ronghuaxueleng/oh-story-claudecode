#!/usr/bin/env python3
"""从书名/梗概自动生成情节池与第一卷卷纲初稿。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
PLOT_EXTRACTOR_CLI = REPO_ROOT / "skills" / "story-plot-extractor" / "scripts" / "plot_extractor_cli.py"


def _run_outline_search(project_dir: Path, title: str, premise: str, json_library: str, limit_per_group: int) -> dict:
    cmd = [
        sys.executable,
        str(PLOT_EXTRACTOR_CLI),
        "search-for-outline",
        "--",
        title,
        "--premise",
        premise,
        "--save",
        "--limit-per-group",
        str(limit_per_group),
    ]
    if json_library:
        cmd.extend(["--json-library", json_library])

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(project_dir))
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or "未知错误"
        if "Neo4j 不可用" in detail and not json_library:
            detail += "。请先在项目目录执行 story-setup 生成并填写 .env，或显式传 --json-library。"
        raise RuntimeError(f"search-for-outline 执行失败：{detail}")

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"search-for-outline 输出不是合法 JSON：{exc}") from exc
    if not result.get("outline_seed"):
        raise RuntimeError("search-for-outline 未返回 outline_seed，请回退到常规写作流程。")
    return result


def _build_book_outline_markdown(result: dict) -> str:
    title = result.get("title") or "未命名作品"
    premise = result.get("premise") or ""
    outline_seed = result.get("outline_seed") or {}
    if not outline_seed:
        raise RuntimeError("缺少 outline_seed，不能自动生成大纲。")
    core_lines = outline_seed.get("core_lines") or []
    volume_conflict = outline_seed.get("volume_one_conflict") or ""
    rhythm = outline_seed.get("thirty_chapter_rhythm") or []
    seed_phrases = outline_seed.get("seed_phrases") or {}
    situation = seed_phrases.get("situation") or ""
    driver = seed_phrases.get("driver") or ""
    emotion = seed_phrases.get("emotion") or ""

    lines = [
        f"# {title} 大纲",
        "",
        "## 项目信息",
        f"- 书名：{title}",
        f"- 一句话梗概：{premise}",
        "",
        "## 全书主母线",
        "",
    ]
    for item in core_lines:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## 卷级鸟瞰",
        "",
        "### 第一卷：破局卷（前30章）",
        f"- 功能：建立“{situation}”困局，亮出“{driver}”这张底牌，交付第一轮“{emotion}”体验",
        f"- 核心事件：{volume_conflict}",
        f"- 起始状态 → 结束状态：主角从被动承压，走到靠“{driver}”拿下第一块立足筹码与阶段性主动权",
        "",
        "## 前30章节奏锚点",
        "",
    ])
    for block in rhythm:
        lines.append(f"- {block.get('range')}: {block.get('goal') or ''}")

    lines.extend([
        "",
        "## 使用说明",
        "",
        "- 本大纲由 story-long-write/bootstrap-outline 自动生成。",
        "- 第一卷方向优先服从 `参考资料/情节库参考.md` 中的 `outline_seed`。",
        "- 后续补卷时，先扩展主母线，再补桥段，不要先堆桥段再重拼结构。",
        "",
    ])
    return "\n".join(lines)


def _build_volume_outline_markdown(result: dict) -> str:
    outline_seed = result.get("outline_seed") or {}
    if not outline_seed:
        raise RuntimeError("缺少 outline_seed，不能自动生成卷纲。")
    outline_pool = result.get("outline_pool") or {}
    reference_focus = outline_seed.get("reference_focus") or {}
    rhythm = outline_seed.get("thirty_chapter_rhythm") or []
    volume_conflict = outline_seed.get("volume_one_conflict") or ""
    seed_phrases = outline_seed.get("seed_phrases") or {}
    situation = seed_phrases.get("situation") or ""
    driver = seed_phrases.get("driver") or ""
    emotion = seed_phrases.get("emotion") or ""
    opening_pull = seed_phrases.get("opening_pull") or ""
    secret_pull = seed_phrases.get("secret_pull") or ""

    rhythm_rows = []
    for idx, block in enumerate(rhythm, start=1):
        phase = block.get("range") or ""
        goal = block.get("goal") or ""
        if idx == 1:
            beat = f"把“{situation}”压到主角头上，并让“{driver}”第一次显效。"
        elif idx == 2:
            beat = f"让主角围绕“{driver}”组织人手、关系或资源，第一次打出反制。"
        elif idx == 3:
            beat = "把个人破局升级成规则对抗或势力博弈，逼主角付出代价换更大筹码。"
        else:
            beat = f"交付一次明确的“{emotion}”高潮，并把下一轮危机或秘密抛出来。"
        rhythm_rows.append((phase, goal, beat))

    lines = [
        "# 第一卷 卷纲",
        "",
        "## 核心信息",
        "- 章节范围：第1-30章",
        "- 字数目标：8-12万字",
        f"- 本卷定位：{situation}开局下的破局卷",
        "",
        "## 核心矛盾",
        volume_conflict,
        "",
        "## 卷定位说明",
        f"- 本卷表面任务：先活下来，并拿到第一块立足筹码。",
        f"- 本卷真正卖点：主角不是靠硬顶，而是靠“{driver}”打出主动权。",
        f"- 本卷读者体验：前期压迫，中段反制，卷末交付一次明显“{emotion}”释放。",
        "",
        "## 情绪弧线",
        "- 模板：渐进形 + 首卷末段强钩",
        f"- 选择理由：前段先砸实“{situation}”，中段建立反制能力，末段必须交付第一次明确“{emotion}”。",
        "",
        "| 章节 | 情绪基调 | 强度 | 触发事件 |",
        "|------|----------|------|----------|",
    ]
    for idx, (phase, goal, beat) in enumerate(rhythm_rows, start=1):
        intensity = 6 + min(idx, 3)
        tone = "压迫→试探" if idx == 1 else "试探→反制" if idx == 2 else "拉扯→升级" if idx == 3 else "爆发→留钩"
        lines.append(f"| {phase} | {tone} | {intensity} | {goal or beat} |")

    lines.extend([
        "",
        "## 爽点节奏",
        "| 周期 | 章节范围 | 铺垫(起) | 释放(承) | 反应层 | 衔接(转) |",
        "|------|---------|---------|---------|-------|---------|",
    ])
    for idx, (phase, _goal, beat) in enumerate(rhythm_rows, start=1):
        if idx == 1:
            lines.append(f"| 第{idx}个 | {phase} | 先压局 | 首次破局显效 | 1层 | 逼出更大难题 |")
        elif idx == 2:
            lines.append(f"| 第{idx}个 | {phase} | 组织资源与人手 | 打出第一轮反制 | 1-2层 | 引来正式对手 |")
        elif idx == 3:
            lines.append(f"| 第{idx}个 | {phase} | 规则压力升级 | 代价换筹码 | 2层 | 抬高卷末风险 |")
        else:
            lines.append(f"| 第{idx}个 | {phase} | 卷末危机汇总 | 爆发式翻盘 | 2层 | 留下下一卷大钩子 |")

    lines.extend([
        "",
        "## 四段推进说明",
        "",
    ])
    for phase, goal, beat in rhythm_rows:
        lines.append(f"### 第{phase}章")
        lines.append(f"- 本段任务：{beat}")
        lines.append(f"- 本段目标：{goal}")
        lines.append("- 写法要求：至少要有一个具体事件节点，不能只写抽象状态变化。")
        lines.append("")

    lines.extend([
        "## 第一卷桥段候选池",
        "",
        "### 开局桥段",
    ])
    for item in outline_pool.get("opening_hooks") or []:
        lines.append(f"- {item.get('plot_name') or ''}：{item.get('core_conflict') or ''}")

    lines.extend([
        "",
        "### 中段推进",
    ])
    for item in outline_pool.get("mid_progressions") or []:
        lines.append(f"- {item.get('plot_name') or ''}：{item.get('core_conflict') or ''}")

    lines.extend([
        "",
        "### 卷尾钩子",
    ])
    for item in outline_pool.get("volume_end_hooks") or []:
        lines.append(f"- {item.get('plot_name') or ''}：{item.get('core_conflict') or ''}")

    lines.extend([
        "",
        "### 长线秘密",
    ])
    for item in outline_pool.get("long_term_secrets") or []:
        lines.append(f"- {item.get('plot_name') or ''}：{item.get('core_conflict') or ''}")

    lines.extend([
        "",
        "## 优先参考",
        "",
        f"- 开局优先参考：{'；'.join(reference_focus.get('opening_hooks') or [])}",
        f"- 中段优先参考：{'；'.join(reference_focus.get('mid_progressions') or [])}",
        f"- 卷尾优先参考：{'；'.join(reference_focus.get('volume_end_hooks') or [])}",
        f"- 长线秘密优先参考：{'；'.join(reference_focus.get('long_term_secrets') or [])}",
        "",
        "## 执行规则",
        "",
        "- 先用本卷核心矛盾和四段推进定方向，再从桥段候选池里选具体事件。",
        "- 不能直接搬运候选桥段原设定，只能借冲突结构与节奏。",
        "- 拆前30章细纲时，必须对齐 `1-3 / 4-10 / 11-20 / 21-30` 四段节奏。",
        f"- 本卷最好在前3章内就把“{driver}”的价值亮出来，不能一直闷着不放。",
        f"- 卷末如果有长线秘密，优先把它和“{secret_pull}”这类悬念挂钩。",
        "",
    ])
    return "\n".join(lines)


def _write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="从书名/梗概自动生成情节池与第一卷卷纲初稿")
    parser.add_argument("title", help="书名")
    parser.add_argument("--premise", required=True, help="一句话梗概")
    parser.add_argument("--project-dir", default=".", help="项目目录，默认当前目录")
    parser.add_argument("--json-library", default="", help="改用本地 JSON 情节库")
    parser.add_argument("--limit-per-group", type=int, default=8, help="每组关键词保留多少候选")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的大纲文件")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    result = _run_outline_search(project_dir, args.title, args.premise, args.json_library, args.limit_per_group)

    outline_md = _build_book_outline_markdown(result)
    volume_md = _build_volume_outline_markdown(result)

    outline_path = project_dir / "大纲" / "大纲.md"
    volume_path = project_dir / "大纲" / "卷纲_第一卷.md"

    _write_text(outline_path, outline_md, args.force)
    _write_text(volume_path, volume_md, args.force)

    output = {
        "title": args.title,
        "premise": args.premise,
        "saved_outline_reference": result.get("saved_to") or str(project_dir / "参考资料" / "情节库参考.md"),
        "saved_book_outline": str(outline_path),
        "saved_volume_outline": str(volume_path),
        "candidate_count": result.get("candidate_count", 0),
        "has_outline_seed": bool(result.get("outline_seed")),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
