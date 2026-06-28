#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
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

SELF_EDIT_PATTERNS = [
    r"[一-龥]{2,}(?:\?|？)\s*(?:no|wait|stop)\b",
    r"[一-龥]{2,}\s*\.\.\.\s*(?:no|wait|stop)\b",
    r"[一-龥]{2,}(?:no|wait|stop)\b",
    r"\b(?:no|wait|stop)\b\s*$",
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

REACTION_VERDICT_PATTERNS = [
    r"她大概没想到我会这么平",
    r"他显然没料到我会这么说",
    r"他这才意识到自己输了",
    r"我看着他，只觉得空",
]

EFFECT_VERDICT_PATTERNS = [
    r"我知道，我这句话进去了",
    r"这句一出去，起效了",
    r"我知道，他听进去了",
    r"这一下算是扎到了",
]

OBJECTLESS_ABSTRACT_PATTERNS = [
    r"脑子里全是喜欢[。！？]",
    r"心里只剩委屈[。！？]",
    r"最在意的就是体面[。！？]",
    r"忽然觉得难堪[。！？]",
]

SENSORY_BREAK_PATTERNS = [
    r"静下来，静得我耳朵都嗡",
    r"看着屏幕，心里一下静了",
    r"天一黑，后背都发麻",
]

HEARING_OVEREXPLAIN_PATTERNS = [
    r"不是哭，是气急了又压着，憋得胸口发闷那种喘",
]

NONHUMAN_PHRASE_PATTERNS = [
    r"往里垫",
    r"把话塞进去",
    r"回头摸墙",
]

ABSTRACT_KOU_PATTERNS = [
    r"第一口(?:收益|势|现实|资源|活路|功|名|权|接口|盘面|命门)",
    r"第二口(?:收益|现实|资源|活路|功|名|权|接口|盘面)",
    r"(?:这|那|哪)一口(?:收益|现实|资源|活路|东西|权|接口|盘面|推进)",
    r"一口(?:收益|现实|资源|活路|功|名|权|接口|盘面|东西)",
    r"那下一口",
    r"接口物",
    r"先说了算的入口",
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

CHAR_COUNT_TOLERANCE = 10

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

SUGGESTIONS = {
    ("字数", "warn"): "建议补强外部反应、群体站位变化或现场细节，不要用解释句凑字。",
    ("字数", "error"): "建议先回到细纲，补足硬场面、外部反应位或第二口收益后再扩写。",
    ("章尾", "error"): "建议把章尾改成新物证、新口径、新名单或新翻面，不要用总结/预告腔收口。",
    ("解释", "error"): "建议删除作者判句，改成现场动作、人物反应或器物/屏幕/环境变化。",
    ("解释", "warn"): "建议减少解释句，优先补具体动作响应。",
    ("模板", "error"): "建议把纲层黑话改成具体对象、具体动作或具体结果，不要把“第一口/第二口/那下一口/一口收益/接口物/先说了算的入口”这类施工词写进正文。",
    ("情报", "error"): "建议补独立情报引号块、兑现动作或情报台账字段。",
    ("污染", "error"): "建议先清工具残片、流程块或执行日志，再复扫。",
    ("动作", "error"): "建议补可见动作链，不要只剩判断和说明。",
    ("结构", "error"): "建议拆长段、补句末停顿，并检查是否大段拖叙。",
    ("流程", "error"): "建议先补齐缺失文件或角色目录，再继续正文流程。",
    ("代判", "error"): "建议删掉作者盖章句，改成沉默、停顿、脸色、站位或接不上话等现场反应。",
    ("悬空", "error"): "建议把抽象词补实：喜欢谁、委屈什么、体面给谁看，别把承重信息省掉。",
    ("感官", "error"): "建议拆开硬焊句，保留同一条感官链，或改成现场能自然推出的感受。",
    ("口气", "error"): "建议先保句子功能，再把怪词退回常用口语层，不要为了新鲜硬拧句子。",
}


@dataclass
class Issue:
    path: str
    message: str
    severity: str = "error"
    category: str = "general"
    suggestion: str | None = None


def count_occurrences(text: str, needles: list[str]) -> int:
    total = 0
    for needle in needles:
        total += text.count(needle)
    return total


def make_issue(path: str, message: str, severity: str = "error", category: str = "general") -> Issue:
    suggestion = SUGGESTIONS.get((category, severity))
    return Issue(path, message, severity, category, suggestion)


def has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def tail(text: str, size: int = 220) -> str:
    return text[-size:] if len(text) > size else text


def project_root_for(path: Path) -> Path:
    for parent in path.parents:
        if (parent / "设定").exists() or (parent / "追踪").exists() or (parent / "正文").exists():
            return parent
    return path.parent


def chapter_no_for(path: Path) -> str | None:
    match = re.search(r"第(\d+)章", path.name)
    if match:
        return match.group(1).zfill(3)
    return None


def chapter_outline_path(project_root: Path, chapter_no: str | None) -> Path | None:
    if not chapter_no:
        return None
    outline_dir = project_root / "大纲"
    if not outline_dir.exists():
        return None
    matches = sorted(outline_dir.glob(f"细纲_第{chapter_no}章*.md"))
    return matches[0] if matches else None


def parse_target_chars(text: str) -> int | None:
    patterns = [
        r"字数目标[:：]\s*(\d+)",
        r"本章目标字数[:：]\s*(\d+)",
        r"目标字数[:：]\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


@dataclass
class ChapterPolicy:
    hard_min: int
    soft_min: int
    hard_max: int
    soft_max: int
    target: int | None = None


def detect_project_mode(project_root: Path) -> str:
    # scene_lint.py 是长短篇共用门禁。
    # 这里只做轻量项目形态识别，把明显的短篇专项规则收进 short 分支，
    # 避免把短篇句型门禁直接打到长篇正文上。
    if (project_root / "正文").is_dir():
        return "long"
    if (project_root / "正文.md").exists():
        return "short"
    return "generic"


def count_explanation_lines(text: str) -> int:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return sum(1 for line in lines if any(pattern in line for pattern in EXPLANATION_PATTERNS))


def count_regex_hits(text: str, patterns: list[str]) -> int:
    return sum(len(re.findall(pattern, text)) for pattern in patterns)


def chapter_targets(path: Path, text: str, project_root: Path) -> ChapterPolicy:
    is_chapter = (
        "正文" in path.parts
        or any(marker in path.name for marker in ("正文", "第0", "第1", "第2", "第3", "第4", "第5", "第6", "第7", "第8", "第9"))
        or "chapter" in path.name.lower()
    )
    if not is_chapter:
        return ChapterPolicy(0, 0, 0, 0, None)

    chapter_no = chapter_no_for(path)
    outline_path = chapter_outline_path(project_root, chapter_no)
    target = None
    if outline_path and outline_path.exists():
        target = parse_target_chars(outline_path.read_text(encoding="utf-8"))

    if target is not None:
        hard_min = max(2700, min(2900, target - 300))
        soft_min = max(2900, target - 120)
        soft_max = max(5100, target + 900)
        hard_max = max(5600, target + 1400)
        return ChapterPolicy(hard_min, soft_min, hard_max, soft_max, target)

    return ChapterPolicy(2800, 3000, 5600, 5100, None)


def lint_file(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    project_root = project_root_for(path)
    project_mode = detect_project_mode(project_root)
    is_prose = "正文" in path.parts or "chapter" in path.name.lower()

    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in text:
            issues.append(make_issue(str(path), f"命中污染片段: {needle}", "error", "污染"))

    for pattern in SELF_EDIT_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            issues.append(make_issue(str(path), f"命中自改残片模式: {pattern}", "error", "污染"))

    for marker in INLINE_GATE_MARKERS:
        if marker in text:
            issues.append(make_issue(str(path), f"正文文件混入流程块: {marker}", "error", "污染"))

    if is_prose:
        explanation_count = count_occurrences(text, EXPLANATION_PATTERNS)
        if explanation_count >= 1:
            issues.append(make_issue(str(path), f"解释腔/作者判句过多: {explanation_count}", "error", "解释"))
        explanation_line_count = count_explanation_lines(text)
        if explanation_line_count >= 3:
            issues.append(make_issue(str(path), f"解释句密度过高: {explanation_line_count}", "error", "解释"))

        summary_count = count_occurrences(tail(text), SUMMARY_PATTERNS)
        if summary_count >= 1 and len(stripped) > 0:
            issues.append(make_issue(str(path), f"章尾总结/预告/盖章风险: {summary_count}", "error", "章尾"))

        abstract_kou_hits = sum(len(re.findall(pattern, text)) for pattern in ABSTRACT_KOU_PATTERNS)
        if abstract_kou_hits >= 1:
            issues.append(make_issue(str(path), f"命中纲层黑话/抽象“口”字模板词: {abstract_kou_hits}", "error", "模板"))

        # 下面这批是短篇专项高精度句型门禁：
        # 高频、字面稳定、误伤可控，但更贴近短篇第一人称现实情感写法。
        # 长篇继续走公共层门禁，不默认吃这批短篇专项。
        if project_mode == "short":
            reaction_verdict_hits = count_regex_hits(text, REACTION_VERDICT_PATTERNS)
            if reaction_verdict_hits >= 1:
                issues.append(make_issue(str(path), f"命中人物反应代判句: {reaction_verdict_hits}", "error", "代判"))

            effect_verdict_hits = count_regex_hits(text, EFFECT_VERDICT_PATTERNS)
            if effect_verdict_hits >= 1:
                issues.append(make_issue(str(path), f"命中效果判词/起效代判句: {effect_verdict_hits}", "error", "代判"))

            objectless_abstract_hits = count_regex_hits(text, OBJECTLESS_ABSTRACT_PATTERNS)
            if objectless_abstract_hits >= 1:
                issues.append(make_issue(str(path), f"命中抽象词悬空/对象省略过度句: {objectless_abstract_hits}", "error", "悬空"))

            sensory_break_hits = count_regex_hits(text, SENSORY_BREAK_PATTERNS)
            if sensory_break_hits >= 1:
                issues.append(make_issue(str(path), f"命中感官逻辑断裂/状态-感官硬焊句: {sensory_break_hits}", "error", "感官"))

            hearing_overexplain_hits = count_regex_hits(text, HEARING_OVEREXPLAIN_PATTERNS)
            if hearing_overexplain_hits >= 1:
                issues.append(make_issue(str(path), f"命中听觉描写解释过满句: {hearing_overexplain_hits}", "error", "感官"))

            nonhuman_phrase_hits = count_regex_hits(text, NONHUMAN_PHRASE_PATTERNS)
            if nonhuman_phrase_hits >= 1:
                issues.append(make_issue(str(path), f"命中高精度非人话表达样本: {nonhuman_phrase_hits}", "error", "口气"))

        policy = chapter_targets(path, text, project_root)
        if policy.hard_min and len(text) < policy.hard_min - CHAR_COUNT_TOLERANCE:
            target_note = f"（细纲目标 {policy.target}）" if policy.target else ""
            issues.append(make_issue(str(path), f"字数不足: {len(text)} < {policy.hard_min}{target_note}", "error", "字数"))
        elif policy.soft_min and len(text) < policy.soft_min - CHAR_COUNT_TOLERANCE:
            target_note = f"（细纲目标 {policy.target}）" if policy.target else ""
            issues.append(make_issue(str(path), f"字数接近下限，建议补强场面或外部反应: {len(text)} < {policy.soft_min}{target_note}", "warn", "字数"))

        if policy.hard_max and len(text) > policy.hard_max + CHAR_COUNT_TOLERANCE:
            target_note = f"（细纲目标 {policy.target}）" if policy.target else ""
            issues.append(make_issue(str(path), f"字数超上限: {len(text)} > {policy.hard_max}{target_note}", "error", "字数"))
        elif policy.soft_max and len(text) > policy.soft_max:
            target_note = f"（细纲目标 {policy.target}）" if policy.target else ""
            issues.append(make_issue(str(path), f"字数偏高，建议检查是否拖叙: {len(text)} > {policy.soft_max}{target_note}", "warn", "字数"))

        if not has_any(text, ACTION_MARKERS):
            issues.append(make_issue(str(path), "缺少明显动作场面标记", "error", "动作"))

        if len(text) > 0 and len(re.findall(r"[。！？]", text)) < 5:
            issues.append(make_issue(str(path), "句末标点偏少，可能存在大段拖叙", "error", "结构"))

    if is_prose and has_any(text, INFO_FLOW_MARKERS):
        if "「" not in text or "」" not in text:
            issues.append(make_issue(str(path), "情报流文本缺少独立情报引号块", "error", "情报"))

        tracking_path = project_root / "追踪" / "情报台账.md"
        if tracking_path.exists():
            tracking_text = tracking_path.read_text(encoding="utf-8")
            missing_columns = [col for col in TRACKING_REQUIRED_COLUMNS if col not in tracking_text]
            if missing_columns:
                issues.append(make_issue(str(tracking_path), f"情报台账缺少字段: {', '.join(missing_columns)}", "error", "情报"))

    if re.search(r"\b(commentary|analysis|assistant to=|functions\.|multi_tool_use\.)\b", text):
        issues.append(make_issue(str(path), "检测到工具/渠道残片", "error", "污染"))

    return issues


def expand_input_paths(raw_inputs: list[str]) -> tuple[list[Path], list[Issue]]:
    paths: list[Path] = []
    issues: list[Issue] = []
    for file_name in raw_inputs:
        path = Path(file_name)
        if not path.exists():
            issues.append(make_issue(file_name, "文件不存在", "error", "流程"))
            continue
        if path.is_dir():
            md_files = sorted(item for item in path.glob("*.md") if item.is_file())
            if not md_files:
                issues.append(make_issue(str(path), "目录下未发现可扫描的 .md 文件", "error", "流程"))
                continue
            paths.extend(md_files)
            continue
        paths.append(path)
    return paths, issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Novel scene lint.")
    parser.add_argument("files", nargs="+", help="Files to lint")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit machine-readable JSON output")
    args = parser.parse_args(argv)

    all_issues: list[Issue] = []
    input_paths, input_issues = expand_input_paths(args.files)
    all_issues.extend(input_issues)
    project_roots = sorted({project_root_for(path) for path in input_paths}, key=lambda p: str(p))
    for project_root in project_roots:
        role_dir = project_root / "设定" / "角色"
        role_file = project_root / "设定.md"
        if not role_dir.exists() and not role_file.exists():
            all_issues.append(make_issue(str(role_dir), "缺少角色设定入口（未发现设定/角色目录或设定.md）", "error", "流程"))
    for path in input_paths:
        all_issues.extend(lint_file(path))

    if all_issues:
        error_count = sum(1 for issue in all_issues if issue.severity == "error")
        warn_count = sum(1 for issue in all_issues if issue.severity == "warn")
        category_counts = Counter(issue.category for issue in all_issues)
        severity_category_counts = Counter(f"{issue.category}.{issue.severity}" for issue in all_issues)
        summary = {
            "errors": error_count,
            "warnings": warn_count,
            "categories": dict(sorted(category_counts.items())),
            "severity_categories": dict(sorted(severity_category_counts.items())),
        }
        payload = {
            "ok": error_count == 0,
            "summary": summary,
            "issues": [
                {
                    "path": issue.path,
                    "severity": issue.severity,
                    "category": issue.category,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                }
                for issue in all_issues
            ],
        }
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            if error_count:
                return 1
            return 0
        for issue in all_issues:
            prefix = "WARN" if issue.severity == "warn" else "ERROR"
            suggestion_suffix = f" | 建议: {issue.suggestion}" if issue.suggestion else ""
            print(f"{prefix}[{issue.category}] {issue.path}: {issue.message}{suggestion_suffix}")
        categories_str = ",".join(f"{name}:{count}" for name, count in sorted(category_counts.items()))
        severity_categories_str = ",".join(
            f"{name}:{count}" for name, count in sorted(severity_category_counts.items())
        )
        print(
            f"SUMMARY errors={error_count} warnings={warn_count} "
            f"categories={categories_str} severity_categories={severity_categories_str}"
        )
        if error_count:
            return 1
        return 0

    if args.json_output:
        print(json.dumps({"ok": True, "summary": {"errors": 0, "warnings": 0, "categories": {}, "severity_categories": {}}, "issues": []}, ensure_ascii=False, indent=2))
        return 0

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
