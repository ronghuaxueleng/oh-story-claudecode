#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


EVIDENCE_LEVELS = ("线索", "高度相关", "半坐实", "已坐实")
CONCLUSION_TOKENS = (
    "已联手",
    "联手转走",
    "已转走",
    "已主使",
    "已执行",
    "已控制",
    "已背叛",
    "就是主使",
)
SOFT_OUTCOME_TOKENS = ("雏形", "资格", "名分", "候选", "暂挂", "先记事实", "待补", "待定", "占位")
POSTCHECK_PREFIXES = ("写后验收", "写后检查")
OUTCOME_RISK_RULES = (
    {
        "name": "先定说法资格高判",
        "needles": ("解释权", "先定说法资格"),
        "strong": ("生效", "拿到", "持有", "到手", "正式"),
        "body_needles": ("解释权", "先定说法资格"),
        "enemy_loss_needles": ("失去", "把原话收回去", "让位", "交出", "被迫", "收走", "关在外面", "改写"),
        "contested_needles": ("不能证明", "不是解释权", "不是先定说法资格", "先写事实", "给谁", "谁有资格", "要求补清除"),
    },
    {
        "name": "链路/归属高判",
        "needles": ("接触链路持有人", "归后勤", "归夜巡", "样本链路", "押送主导"),
        "strong": ("拿到", "持有", "归", "正式", "到手"),
        "body_needles": ("链路", "押送", "交接", "上车", "转运"),
        "enemy_loss_needles": ("失去", "把原话收回去", "改手", "被挡", "被迫", "关门", "收走"),
        "contested_needles": ("不能证明", "暂缓", "先押送", "临时", "别在这儿耗", "试试"),
    },
)


@dataclass
class Issue:
    path: str
    category: str
    severity: str
    message: str


def make_issue(path: Path, category: str, severity: str, message: str) -> Issue:
    return Issue(str(path), category, severity, message)


def find_project_root(path: Path) -> Path:
    if path.is_file():
        path = path.parent
    for parent in (path, *path.parents):
        if (parent / "正文").exists() or (parent / "追踪").exists() or (parent / "设定").exists():
            return parent
    return path


def chapter_no_from_name(name: str) -> int | None:
    match = re.search(r"第(\d+)章", name)
    return int(match.group(1)) if match else None


def chapter_files(project_root: Path) -> list[Path]:
    body_dir = project_root / "正文"
    if not body_dir.exists():
        return []
    files = [path for path in body_dir.glob("*.md") if chapter_no_from_name(path.name) is not None]
    return sorted(files, key=lambda item: chapter_no_from_name(item.name) or 0)


def chapter_group_postchecks(project_root: Path) -> list[Path]:
    tracking_dir = project_root / "追踪"
    if not tracking_dir.exists():
        return []
    files: list[Path] = []
    for prefix in POSTCHECK_PREFIXES:
        for path in tracking_dir.glob(f"{prefix}_第*.md"):
            if canonical_chapter_range(path.name) is not None:
                files.append(path)
    return sorted(files)


def single_chapter_postchecks(project_root: Path) -> list[Path]:
    tracking_dir = project_root / "追踪"
    if not tracking_dir.exists():
        return []
    files: list[Path] = []
    for prefix in POSTCHECK_PREFIXES:
        for path in tracking_dir.glob(f"{prefix}_第*.md"):
            if canonical_single_chapter(path.name) is not None:
                files.append(path)
    return sorted(files)


def canonical_chapter_range(name: str) -> tuple[int, int] | None:
    match = re.search(r"第(\d+)(?:章)?-(?:第)?(\d+)章", name)
    if match:
        return int(match.group(1)), int(match.group(2))
    nums = [int(item) for item in re.findall(r"第(\d+)章", name)]
    if len(nums) < 2:
        return None
    return min(nums), max(nums)


def canonical_single_chapter(name: str) -> int | None:
    match = re.fullmatch(r"(?:写后验收|写后检查)_第(\d+)章(?:_.+)?\.md", name)
    if match:
        return int(match.group(1))
    return None


def validate_required_files(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    tracking_dir = project_root / "追踪"
    for path in (tracking_dir / "时间线.md", tracking_dir / "角色状态.md"):
        if not path.exists():
            issues.append(make_issue(path, "追踪", "error", "缺少必需追踪主表"))
    info_path = tracking_dir / "情报台账.md"
    if not info_path.exists():
        issues.append(make_issue(info_path, "追踪", "warn", "未发现情报台账；若本书命中情报流，需补建并纳入追踪同步"))
    return issues


def validate_postcheck_presence(project_root: Path, chapters: list[Path]) -> list[Issue]:
    issues: list[Issue] = []
    if len(chapters) < 2:
        return issues
    groups = chapter_group_postchecks(project_root)
    tracking_dir = project_root / "追踪"
    if not groups:
        issues.append(make_issue(tracking_dir, "章组总表", "warn", "正文已有连续两章及以上，但未发现 `写后检查_第XXX-XXX章.md` 或 `写后验收_第XXX-XXX章.md` 章组总表"))
        return issues
    latest = chapters[-4:]
    if len(latest) >= 2:
        first = chapter_no_from_name(latest[0].name)
        last = chapter_no_from_name(latest[-1].name)
        if first is not None and last is not None:
            expected = f"第{first:03d}章-第{last:03d}章"
            if not any(expected in path.name for path in groups):
                issues.append(make_issue(tracking_dir, "章组总表", "warn", f"最近章节范围疑似缺章组总表：{expected}"))
    return issues


def validate_duplicate_postchecks(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    groups = chapter_group_postchecks(project_root)
    seen: dict[tuple[int, int], list[Path]] = {}
    for path in groups:
        chapter_range = canonical_chapter_range(path.name)
        if chapter_range is None:
            continue
        seen.setdefault(chapter_range, []).append(path)
    for chapter_range, paths in seen.items():
        if len(paths) <= 1:
            continue
        labels = "、".join(path.name for path in paths)
        issues.append(
            make_issue(
                project_root / "追踪",
                "双版本并存",
                "error",
                f"同范围写后验收重复并存：第{chapter_range[0]:03d}章-第{chapter_range[1]:03d}章 -> {labels}",
            )
        )
    return issues


def validate_unique_fact_source(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    tracking_dir = project_root / "追踪"
    paths: list[Path] = []
    for prefix in POSTCHECK_PREFIXES:
        paths.extend(sorted(tracking_dir.glob(f"{prefix}_第*.md")))
    paths = sorted(set(paths))
    sources: dict[tuple[int, int], list[Path]] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "唯一事实源" not in text:
            continue
        chapter_range = canonical_chapter_range(path.name)
        if chapter_range is None:
            continue
        sources.setdefault(chapter_range, []).append(path)
    for chapter_range, group in sources.items():
        if len(group) > 1:
            labels = "、".join(item.name for item in group)
            issues.append(
                make_issue(
                    tracking_dir,
                    "双版本并存",
                    "error",
                    f"同范围存在多个自称唯一事实源的写后验收文件：第{chapter_range[0]:03d}章-第{chapter_range[1]:03d}章 -> {labels}",
                )
            )
    return issues


def table_rows(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line.startswith("|") and not re.fullmatch(r"\|[-| ]+\|?", line)]


def validate_info_ledger(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    ledger = project_root / "追踪" / "情报台账.md"
    if not ledger.exists():
        return issues
    text = ledger.read_text(encoding="utf-8")
    rows = table_rows(text)
    for row in rows[1:]:
        has_level = any(level in row for level in EVIDENCE_LEVELS)
        has_conclusion = any(token in row for token in CONCLUSION_TOKENS)
        if not has_level:
            issues.append(make_issue(ledger, "情报台账", "warn", f"台账行缺证据等级标记: {row}"))
        if has_conclusion and not has_level:
            issues.append(make_issue(ledger, "情报台账", "error", f"结论口径未标证据等级: {row}"))
    return issues


def validate_role_state(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    role_state = project_root / "追踪" / "角色状态.md"
    role_dir = project_root / "设定" / "角色"
    if not role_state.exists():
        return issues
    text = role_state.read_text(encoding="utf-8")
    names = re.findall(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)
    for name in names:
        card = role_dir / f"{name}.md"
        if not card.exists():
            issues.append(make_issue(role_state, "角色卡", "error", f"角色状态已收录 `{name}`，但缺少对应角色卡"))
    return issues


def extract_field(text: str, field: str) -> str:
    match = re.search(rf"^\s*-\s*{re.escape(field)}：\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def scene_narrowness_script(project_root: Path) -> Path:
    return Path(__file__).resolve().parent / "scene_narrowness_lint.py"


def run_scene_narrowness(path: Path, script_path: Path) -> dict | None:
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", str(path)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def validate_scene_narrowness_acceptance(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    script_path = scene_narrowness_script(project_root)
    chapter_map = {chapter_no_from_name(path.name): path for path in chapter_files(project_root)}
    for postcheck in single_chapter_postchecks(project_root):
        chapter_no = canonical_single_chapter(postcheck.name)
        chapter_path = chapter_map.get(chapter_no)
        if chapter_no is None or chapter_path is None:
            continue
        payload = run_scene_narrowness(chapter_path, script_path)
        if not payload:
            continue
        warned = any(issue.get("severity") == "warn" for issue in payload.get("issues", []))
        if not warned:
            continue
        text = postcheck.read_text(encoding="utf-8")
        final_code = extract_field(text, "最终失败码")
        verdict = extract_field(text, "并入裁决")
        narrowness_field = extract_field(text, "scene_narrowness_lint 结果")
        missing_answers: list[str] = []
        for field in ("谁的现实位置被改掉", "谁因此吃了即时损失", "本章哪一拍若删掉作者代判句 / 流程说明句后，现场仍能成立"):
            if not extract_field(text, field):
                missing_answers.append(field)
        if not narrowness_field:
            issues.append(
                make_issue(
                    postcheck,
                    "过程写窄消费",
                    "error",
                    f"第{chapter_no:03d}章正文已命中 `scene_narrowness_lint.warn`，但写后检查未填写 `scene_narrowness_lint 结果`",
                )
            )
        if missing_answers:
            issues.append(
                make_issue(
                    postcheck,
                    "过程写窄消费",
                    "error",
                    f"第{chapter_no:03d}章正文已命中 `scene_narrowness_lint.warn`，但写后检查缺少三问：{'、'.join(missing_answers)}",
                )
            )
        if final_code == "F0" or verdict.strip() == "可并入主正文":
            issues.append(
                make_issue(
                    postcheck,
                    "过程写窄消费",
                    "error",
                    f"第{chapter_no:03d}章正文已命中 `scene_narrowness_lint.warn`，写后检查仍高判为 `{final_code or '未写失败码'} / {verdict or '未写并入裁决'}`",
                )
            )
    return issues


def tracking_text_files(project_root: Path) -> list[Path]:
    tracking_dir = project_root / "追踪"
    files: list[Path] = []
    if tracking_dir.exists():
        files.extend(sorted(tracking_dir.glob("*.md")))
    for path in (project_root / "设定" / "角色").glob("*.md"):
        files.append(path)
    return files


def validate_outcome_overclaim(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    body_text = "\n".join(path.read_text(encoding="utf-8") for path in chapter_files(project_root))
    for path in tracking_text_files(project_root):
        text = path.read_text(encoding="utf-8")
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            for rule in OUTCOME_RISK_RULES:
                if not any(token in line for token in rule["needles"]):
                    continue
                if not any(token in line for token in rule["strong"]):
                    continue
                if any(token in line for token in SOFT_OUTCOME_TOKENS):
                    continue
                body_has_core = any(token in body_text for token in rule["body_needles"])
                body_has_loss = any(token in body_text for token in rule["enemy_loss_needles"])
                body_contested = any(token in body_text for token in rule.get("contested_needles", ()))
                if body_has_core and body_has_loss and not body_contested:
                    continue
                severity = "error" if not body_has_core else "warn"
                issues.append(
                    make_issue(
                        path,
                        "收益高判",
                        severity,
                        f"第{lineno}行收益口径可能高于正文已坐实结果：{line}",
                    )
                )
                break
    return issues


def split_legacy_issues(issues: list[Issue]) -> tuple[list[Issue], list[Issue]]:
    legacy_categories = {"章组总表", "情报台账"}
    legacy: list[Issue] = []
    actionable: list[Issue] = []
    for issue in issues:
        if issue.severity == "warn" and issue.category in legacy_categories:
            legacy.append(issue)
        else:
            actionable.append(issue)
    return legacy, actionable


def summarize(issues: list[Issue], legacy_compat: bool) -> dict:
    legacy_issues, actionable_issues = split_legacy_issues(issues)
    errors = sum(1 for issue in actionable_issues if issue.severity == "error")
    warnings = sum(1 for issue in actionable_issues if issue.severity == "warn")
    legacy_errors = sum(1 for issue in legacy_issues if issue.severity == "error")
    legacy_warnings = sum(1 for issue in legacy_issues if issue.severity == "warn")
    actionable_categories: dict[str, int] = {}
    actionable_severity_categories: dict[str, int] = {}
    for issue in actionable_issues:
        actionable_categories[issue.category] = actionable_categories.get(issue.category, 0) + 1
        key = f"{issue.category}.{issue.severity}"
        actionable_severity_categories[key] = actionable_severity_categories.get(key, 0) + 1
    return {
        "ok": errors == 0 if legacy_compat else (errors + legacy_errors) == 0,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "legacy_errors": legacy_errors,
            "legacy_warnings": legacy_warnings,
            "total": len(issues),
            "categories": dict(sorted(actionable_categories.items())),
            "severity_categories": dict(sorted(actionable_severity_categories.items())),
        },
        "issues": [asdict(issue) for issue in actionable_issues],
        "legacy_issues": [asdict(issue) for issue in legacy_issues],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate tracking state, chapter-group postchecks, and evidence levels.")
    parser.add_argument("path", help="Novel project root or any file inside the project")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON result")
    parser.add_argument("--legacy-compat", action="store_true", help="Keep legacy tracking debt separate from actionable issues.")
    args = parser.parse_args(argv)

    project_root = find_project_root(Path(args.path))
    chapters = chapter_files(project_root)

    issues: list[Issue] = []
    issues.extend(validate_required_files(project_root))
    issues.extend(validate_postcheck_presence(project_root, chapters))
    issues.extend(validate_duplicate_postchecks(project_root))
    issues.extend(validate_unique_fact_source(project_root))
    issues.extend(validate_info_ledger(project_root))
    issues.extend(validate_role_state(project_root))
    issues.extend(validate_outcome_overclaim(project_root))
    issues.extend(validate_scene_narrowness_acceptance(project_root))

    payload = summarize(issues, args.legacy_compat)
    payload["project_root"] = str(project_root)
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
