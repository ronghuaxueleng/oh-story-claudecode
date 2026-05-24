#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN_SUBSTRINGS = [
    "*** Begin Patch",
    "*** End Patch",
    "functions.",
    "multi_tool_use.",
    "commentary",
    "analysis",
    "assistant to=",
    "tool output",
]

EXPLANATION_PATTERNS = [
    "这说明",
    "这意味着",
    "这表明",
    "这证明",
    "真正的",
    "从这一刻起",
    "接下来就是",
    "原来",
    "知道这意味着什么",
    "不管怎么回事",
    "换句话说",
    "值钱的是",
]

SUMMARY_PATTERNS = [
    "终于",
    "总算",
    "最终",
    "这一夜",
    "这一刻",
    "从此",
    "接下来",
    "更大的风暴",
    "谁都看得出来",
    "他已经",
]

ACTION_MARKERS = [
    "抓",
    "按",
    "拽",
    "踹",
    "撞",
    "掀",
    "砸",
    "按住",
    "逼",
    "抢",
    "夺",
    "翻",
    "挡",
    "退",
    "扑",
    "拖",
    "拔",
    "捅",
    "按下",
]

INFO_FLOW_MARKERS = [
    "情报",
    "系统",
    "任务",
    "预知",
    "刷新",
]

INLINE_GATE_MARKERS = [
    "## 本章写前闸门",
    "## 本章写后验收",
]

TRACKING_REQUIRED_COLUMNS = [
    "刷新章",
    "预计兑现章",
    "实际兑现章",
    "实际战果",
]


@dataclass
class Issue:
    path: str
    message: str


def count_occurrences(text: str, needles: list[str]) -> int:
    total = 0
    for needle in needles:
        total += text.count(needle)
    return total


def has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def tail(text: str, size: int = 220) -> str:
    return text[-size:] if len(text) > size else text


def project_root_for(path: Path) -> Path:
    for parent in path.parents:
        if (parent / "设定").exists() or (parent / "追踪").exists() or (parent / "正文").exists():
            return parent
    return path.parent


def count_explanation_lines(text: str) -> int:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return sum(1 for line in lines if any(pattern in line for pattern in EXPLANATION_PATTERNS))


def chapter_targets(path: Path, text: str) -> tuple[int, int]:
    if "正文" in path.parts:
        return (2900, 5100)
    if any(marker in path.name for marker in ("正文", "第0", "第1", "第2", "第3", "第4", "第5", "第6", "第7", "第8", "第9")):
        return (2900, 5100)
    if "chapter" in path.name.lower():
        return (2900, 5100)
    return (0, 0)


def lint_file(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    project_root = project_root_for(path)

    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in text:
            issues.append(Issue(str(path), f"命中污染片段: {needle}"))

    for marker in INLINE_GATE_MARKERS:
        if marker in text:
            issues.append(Issue(str(path), f"正文文件混入流程块: {marker}"))

    explanation_count = count_occurrences(text, EXPLANATION_PATTERNS)
    if explanation_count >= 1:
        issues.append(Issue(str(path), f"解释腔/作者判句过多: {explanation_count}"))
    explanation_line_count = count_explanation_lines(text)
    if explanation_line_count >= 3:
        issues.append(Issue(str(path), f"解释句密度过高: {explanation_line_count}"))

    summary_count = count_occurrences(tail(text), SUMMARY_PATTERNS)
    if summary_count >= 1 and len(stripped) > 0:
        issues.append(Issue(str(path), f"章尾总结/预告/盖章风险: {summary_count}"))

    if "正文" in path.parts or "chapter" in path.name.lower():
        min_chars, max_chars = chapter_targets(path, text)
        if min_chars and len(text) < min_chars:
            issues.append(Issue(str(path), f"字数不足: {len(text)} < {min_chars}"))
        if max_chars and len(text) > max_chars:
            issues.append(Issue(str(path), f"字数超上限: {len(text)} > {max_chars}"))

        if not has_any(text, ACTION_MARKERS):
            issues.append(Issue(str(path), "缺少明显动作场面标记"))

        if len(text) > 0 and len(re.findall(r"[。！？]", text)) < 5:
            issues.append(Issue(str(path), "句末标点偏少，可能存在大段拖叙"))

    if has_any(text, INFO_FLOW_MARKERS):
        if "「" not in text or "」" not in text:
            issues.append(Issue(str(path), "情报流文本缺少独立情报引号块"))

        tracking_path = project_root / "追踪" / "情报台账.md"
        if tracking_path.exists():
            tracking_text = tracking_path.read_text(encoding="utf-8")
            missing_columns = [col for col in TRACKING_REQUIRED_COLUMNS if col not in tracking_text]
            if missing_columns:
                issues.append(Issue(str(tracking_path), f"情报台账缺少字段: {', '.join(missing_columns)}"))

    role_dir = project_root / "设定" / "角色"
    if not role_dir.exists():
        issues.append(Issue(str(role_dir), "缺少设定/角色目录"))

    if re.search(r"\b(commentary|analysis|assistant to=|functions\.|multi_tool_use\.)\b", text):
        issues.append(Issue(str(path), "检测到工具/渠道残片"))

    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Novel scene lint.")
    parser.add_argument("files", nargs="+", help="Files to lint")
    args = parser.parse_args(argv)

    all_issues: list[Issue] = []
    for file_name in args.files:
        path = Path(file_name)
        if not path.exists():
            all_issues.append(Issue(file_name, "文件不存在"))
            continue
        all_issues.extend(lint_file(path))

    if all_issues:
        for issue in all_issues:
            print(f"{issue.path}: {issue.message}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
