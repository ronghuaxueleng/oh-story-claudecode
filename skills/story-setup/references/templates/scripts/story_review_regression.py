#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "测试"
SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Case:
    group: str
    name: str
    rel_dir: str
    tier: str
    expected: str
    expect_errors: int
    expect_warnings: int
    minimum_severity_categories: tuple[tuple[str, int], ...]
    expect_tracking_errors: int | None
    expect_tracking_warnings: int | None
    minimum_tracking_severity_categories: tuple[tuple[str, int], ...]
    expect_recovery_note: str
    expect_postmortem: bool
    expected_regression_files: tuple[str, ...]
    ignore_scene_lint_assertions: bool = False
    expect_agency_warnings: int | None = None
    minimum_agency_warnings: int | None = None
    minimum_agency_messages: tuple[str, ...] = ()
    expect_version_errors: int | None = None
    minimum_version_messages: tuple[str, ...] = ()
    expect_verdict_errors: int | None = None
    minimum_verdict_messages: tuple[str, ...] = ()
    expect_narrow_warnings: int | None = None
    minimum_narrow_messages: tuple[str, ...] = ()
    allow_missing: bool = True
    ignore_tracking_assertions: bool = False
    ignore_regression_files_assertions: bool = False


CASES: tuple[Case, ...] = (
    Case("A组", "人工覆核样本", "skill回归_现代悬疑调查", "minimal", "scene_lint 预期 errors=0, warnings=0；应为人工覆核样本，不应硬造人物层/一致性层问题", 0, 0, (), 0, 0, (), "人工覆核样本，不应乱造问题", False, ("追踪/总施工单_001-004章_story-review-full回归测试.md", "追踪/固定验收清单_001-004章_story-review-full回归测试.md")),
    Case("B组", "旧样本 / 模板黑话过期", "skill回归_江湖帮派经营", "minimal", "旧样本正文已写入模板黑话；当前规则下应命中 `模板.error=2 + 字数.warn=1`，但追踪侧仍应保持无 actionable issues，且不应生成复盘单", 2, 1, (("模板.error", 2), ("字数.warn", 1)), 0, 0, (), "旧样本过期：正文不过 F0，但追踪规则未误伤", False, ("追踪/总施工单_001-004章_story-review-full回归测试.md", "追踪/固定验收清单_001-004章_story-review-full回归测试.md")),
    Case("B组", "F0 + 多预警样本", "skill回归_创业商战", "minimal", "多条字数.warn；仍应为 F0 + 观察项，不应生成复盘单", 0, 4, (("字数.warn", 4),), 0, 0, (), "F0 + 观察项，不应生成复盘单", False, ("追踪/总施工单_001-004章_story-review-full回归测试.md", "追踪/固定验收清单_001-004章_story-review-full回归测试.md")),
    Case("B组", "扩展组 / 古代断案", "skill回归_古代断案追索", "extended", "仅字数.warn；应为 F0 + 观察项", 0, 3, (("字数.warn", 3),), 0, 0, (), "F0 + 观察项", False, ("追踪/总施工单_001-004章_story-review-full回归测试.md", "追踪/固定验收清单_001-004章_story-review-full回归测试.md")),
    Case("B组", "扩展组 / 异题材审美牵引", "skill回归_异题材审美牵引", "extended", "仅字数.warn；应为 F0 + 观察项", 0, 1, (("字数.warn", 1),), 0, 0, (), "F0 + 观察项", False, ("追踪/总施工单_001-004章_story-review-full回归测试.md", "追踪/固定验收清单_001-004章_story-review-full回归测试.md")),
    Case("B组", "扩展组 / 跨场景过桥", "skill回归_跨场景过桥", "extended", "仅字数.warn；应为 F0 + 观察项", 0, 1, (("字数.warn", 1),), 0, 0, (), "F0 + 观察项", False, ("追踪/总施工单_001-003章_story-review-full回归测试.md", "追踪/固定验收清单_001-003章_story-review-full回归测试.md")),
    Case("B组", "扩展组 / 母场景避重复", "skill回归_母场景避重复", "extended", "旧样本已低于当前字数门槛；按现规则应命中 `字数.error=4 + 字数.warn=1`，但追踪侧仍应保持无 actionable issues，且不应生成复盘单", 4, 1, (("字数.error", 4), ("字数.warn", 1)), 0, 0, (), "旧样本过期：正文不过 F0，但追踪规则未误伤", False, ("追踪/总施工单_001-006章_story-review-full回归测试.md", "追踪/固定验收清单_001-006章_story-review-full回归测试.md")),
    Case("C组", "F2 真门禁样本", "开局流放，我每天解锁一个情报", "minimal", "命中当前门禁真实结果；应表现为 `模板.error=1 + 章尾.error=2 + 字数.warn=4`，tracking 命中 `角色卡.error=1`，并生成总施工单、固定验收清单、失效原因复盘单", 3, 4, (("字数.warn", 4), ("模板.error", 1), ("章尾.error", 2)), 1, 0, (("角色卡.error", 1),), "应入门禁层，并生成复盘单", True, ("追踪/总施工单_第001-030章_story-review-full回归测试.md", "追踪/固定验收清单_第001-030章_story-review-full回归测试.md", "追踪/失效原因复盘单_第001-030章_story-review-full回归测试.md")),
    Case("专项组", "专项 / 收益高判", "skill回归_收益高判", "extended", "validate_tracking_state.py 应直接命中 收益高判.error，不得回收成普通追踪措辞问题", 0, 0, (), 5, 0, (("收益高判.error", 5),), "应稳定命中收益档位高判", False, ("追踪/真实full-agents实跑_专项_收益高判.md",), True),
    Case("专项组", "专项 / 双版本并存", "skill回归_双版本并存", "extended", "validate_tracking_state.py 应直接命中 双版本并存.error，不得回收成命名差异", 0, 0, (), 1, 0, (("双版本并存.error", 1),), "应稳定命中双版本并存", False, ("追踪/真实full-agents实跑_专项_双版本并存.md",), True),
    Case("专项组", "专项 / 非情报流误触", "skill回归_非情报流误触", "extended", "scene_lint.py 先报 情报.error，但 tracking 脚本应保持 0 error / 0 warn，供主线程人工分流为非情报流误触候选", 2, 2, (("字数.warn", 2), ("情报.error", 2)), 0, 0, (), "脚本先给情报候选，主线程再分流", False, ("追踪/真实full-agents实跑_专项_非情报流误触.md",)),
    Case("专项组", "专项 / 本组第二章短兑现链", "skill回归_本组第二章短兑现链", "extended", "scene_lint.py 应表现为 第001章字数.warn / 第002章字数.error，tracking 脚本保持全绿，供主线程分流为短兑现链", 1, 1, (("字数.error", 1), ("字数.warn", 1)), 0, 0, (), "脚本先给厚度候选，主线程再判短兑现链", False, ("追踪/真实full-agents实跑_专项_本组第二章短兑现链.md",)),
    Case("专项组", "专项 / 本组第二章最后半拍回弹不足", "skill回归_本组第二章最后半拍回弹不足", "extended", "scene_lint.py 应表现为 第001章字数.warn / 第002章字数.error，tracking 脚本保持全绿，供主线程分流为最后半拍回弹不足", 1, 1, (("字数.error", 1), ("字数.warn", 1)), 0, 0, (), "脚本先给厚度候选，主线程再判最后半拍回弹不足", False, ("追踪/真实full-agents实跑_专项_本组第二章最后半拍回弹不足.md",)),
    Case(
        group="专项组",
        name="专项 / 模板回流收益高判坏样本",
        rel_dir="模板回流收益高判回归/坏样本",
        tier="extended",
        expected="template_exhaustion_lint.py 应稳定命中模板术语回流；后续可继续补入收益高判链路样本",
        expect_errors=0,
        expect_warnings=0,
        minimum_severity_categories=(),
        expect_tracking_errors=None,
        expect_tracking_warnings=None,
        minimum_tracking_severity_categories=(),
        expect_recovery_note="专项坏样本应稳定暴露模板回流",
        expect_postmortem=False,
        expected_regression_files=(),
        ignore_scene_lint_assertions=True,
        allow_missing=True,
        ignore_tracking_assertions=True,
        ignore_regression_files_assertions=True,
    ),
    Case(
        group="专项组",
        name="专项 / 隐性模板标签句坏样本",
        rel_dir="隐性模板标签句回归/坏样本",
        tier="extended",
        expected="scene_narrowness_lint.py 应至少命中 1 条作者代判句/标签句风险",
        expect_errors=0,
        expect_warnings=0,
        minimum_severity_categories=(),
        expect_tracking_errors=None,
        expect_tracking_warnings=None,
        minimum_tracking_severity_categories=(),
        expect_recovery_note="专项坏样本应稳定暴露隐性标签句",
        expect_postmortem=False,
        expected_regression_files=(),
        ignore_scene_lint_assertions=True,
        expect_narrow_warnings=1,
        minimum_narrow_messages=("命中隐性模板标签句",),
        allow_missing=True,
        ignore_tracking_assertions=True,
        ignore_regression_files_assertions=True,
    ),
    Case(
        group="人物专项",
        name="人物 / 高价值角色旁白补义",
        rel_dir="人物接口专项回归/高价值角色旁白补义/坏样本",
        tier="extended",
        expected="人物专项样本：当前至少应展示 `character_agency_lint.py` 输出；后续再收紧为必须命中高价值角色补义风险",
        expect_errors=0,
        expect_warnings=0,
        minimum_severity_categories=(),
        expect_tracking_errors=None,
        expect_tracking_warnings=None,
        minimum_tracking_severity_categories=(),
        expect_recovery_note="人物专项样本已接入回归展示，等待脚本阈值继续打磨",
        expect_postmortem=False,
        expected_regression_files=(),
        ignore_scene_lint_assertions=True,
        expect_agency_warnings=None,
        minimum_agency_warnings=1,
        minimum_agency_messages=("高价值角色",),
        allow_missing=True,
        ignore_tracking_assertions=True,
        ignore_regression_files_assertions=True,
    ),
    Case(
        group="人物专项",
        name="人物 / 配角翻译器",
        rel_dir="人物接口专项回归/配角翻译器/坏样本",
        tier="extended",
        expected="人物专项样本：当前至少应展示 `character_agency_lint.py` 输出；后续再收紧为必须命中配角翻译器风险",
        expect_errors=0,
        expect_warnings=0,
        minimum_severity_categories=(),
        expect_tracking_errors=None,
        expect_tracking_warnings=None,
        minimum_tracking_severity_categories=(),
        expect_recovery_note="人物专项样本已接入回归展示，等待脚本阈值继续打磨",
        expect_postmortem=False,
        expected_regression_files=(),
        ignore_scene_lint_assertions=True,
        expect_agency_warnings=None,
        minimum_agency_warnings=1,
        minimum_agency_messages=("翻译器",),
        allow_missing=True,
        ignore_tracking_assertions=True,
        ignore_regression_files_assertions=True,
    ),
    Case(
        group="人物专项",
        name="人物 / 软肋角色掉线",
        rel_dir="人物接口专项回归/软肋角色掉线/坏样本",
        tier="extended",
        expected="人物专项样本：当前应至少命中 1 条软肋角色掉线/私人状态回针风险",
        expect_errors=0,
        expect_warnings=0,
        minimum_severity_categories=(),
        expect_tracking_errors=None,
        expect_tracking_warnings=None,
        minimum_tracking_severity_categories=(),
        expect_recovery_note="人物专项样本已接入回归展示，软肋回针必须可检出",
        expect_postmortem=False,
        expected_regression_files=(),
        ignore_scene_lint_assertions=True,
        expect_agency_warnings=None,
        minimum_agency_warnings=1,
        minimum_agency_messages=("软肋角色",),
        allow_missing=True,
        ignore_tracking_assertions=True,
        ignore_regression_files_assertions=True,
    ),
)

LEGACY_TRACKING_WARNINGS = {"章组总表", "情报台账"}


def run_json(cmd: list[str], cwd: Path) -> dict:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"命令执行失败: {' '.join(cmd)}\n{proc.stderr or proc.stdout}")
    return json.loads(proc.stdout)


def resolve_script(case_dir: Path, script_name: str) -> Path | None:
    bundled_script = SCRIPT_DIR / script_name
    if bundled_script.exists():
        return bundled_script
    project_script = case_dir / "scripts" / script_name
    if project_script.exists():
        return project_script
    return None


def run_scene_lint(case_dir: Path) -> dict:
    script = resolve_script(case_dir, "scene_lint.py")
    if script is None:
        raise RuntimeError(f"{case_dir}: 未找到 scene_lint.py")
    rel_files = [str(f.relative_to(case_dir)) for f in sorted((case_dir / "正文").glob("*.md"))]
    return run_json([sys.executable, str(script), "--json", *rel_files], case_dir)


def run_tracking_state(case_dir: Path) -> dict | None:
    script = resolve_script(case_dir, "validate_tracking_state.py")
    if script is None:
        return None
    return run_json([sys.executable, str(script), "--json", "--legacy-compat", str(case_dir)], case_dir)


def run_promotion(case_dir: Path) -> dict | None:
    script = resolve_script(case_dir, "detect_key_character_promotion.py")
    if script is None:
        return None
    return run_json([sys.executable, str(script), "--json", str(case_dir)], case_dir)


def run_agency(case_dir: Path) -> dict | None:
    script = resolve_script(case_dir, "character_agency_lint.py")
    if script is None:
        return None
    return run_json([sys.executable, str(script), "--json", str(case_dir)], case_dir)


def run_version(case_dir: Path) -> dict | None:
    script = resolve_script(case_dir, "script_version_check.py")
    if script is None:
        return None
    return run_json([sys.executable, str(script), "--json", str(case_dir)], case_dir)


def run_verdict(case_dir: Path) -> dict | None:
    script = resolve_script(case_dir, "verdict_conflict_lint.py")
    if script is None:
        return None
    return run_json([sys.executable, str(script), "--json", str(case_dir)], case_dir)


def run_narrow(case_dir: Path) -> dict | None:
    script = resolve_script(case_dir, "scene_narrowness_lint.py")
    if script is None:
        return None
    return run_json([sys.executable, str(script), "--json", str(case_dir)], case_dir)


def collect_case(case: Case) -> dict:
    case_dir = TEST_ROOT / case.rel_dir
    if not case_dir.exists():
        missing_failure = [] if case.allow_missing else [f"样本目录缺失: {case_dir}"]
        return {
            "group": case.group,
            "name": case.name,
            "case_dir": str(case_dir.relative_to(ROOT)),
            "chapter_count": 0,
            "expected": case.expected,
            "expected_recovery_note": case.expect_recovery_note,
            "lint_ok": None,
            "errors": 0,
            "warnings": 0,
            "severity_categories": {},
            "issues": [],
            "tracking": None,
            "tracking_severity_categories": {},
            "tracking_legacy_warnings": [],
            "tracking_actionable_issues": [],
            "promotion": None,
            "agency": None,
            "regression_files_present": [],
            "regression_files_missing": [],
            "postmortem_exists": False,
            "skipped": True,
            "skip_reason": f"样本目录不存在: {case_dir}",
            "pass": not missing_failure,
            "failures": missing_failure,
        }
    lint = run_scene_lint(case_dir)
    tracking = run_tracking_state(case_dir)
    promotion = run_promotion(case_dir)
    agency = run_agency(case_dir)
    version = run_version(case_dir)
    verdict = run_verdict(case_dir)
    narrow = run_narrow(case_dir)
    expected_files = [case_dir / rel for rel in case.expected_regression_files]
    existing_files = [str(path.relative_to(case_dir)) for path in expected_files if path.exists()]
    missing_files = [str(path.relative_to(case_dir)) for path in expected_files if not path.exists()]
    postmortem_exists = any(path.exists() for path in expected_files if "失效原因复盘单_" in path.name)
    actual_categories = dict(lint["summary"]["severity_categories"])

    failures: list[str] = []
    if not case.ignore_scene_lint_assertions:
        if lint["summary"]["errors"] != case.expect_errors:
            failures.append(f"errors 预期 {case.expect_errors}，实际 {lint['summary']['errors']}")
        if lint["summary"]["warnings"] != case.expect_warnings:
            failures.append(f"warnings 预期 {case.expect_warnings}，实际 {lint['summary']['warnings']}")
        for category, minimum in case.minimum_severity_categories:
            actual = int(actual_categories.get(category, 0))
            if actual < minimum:
                failures.append(f"severity_categories `{category}` 预期至少 {minimum}，实际 {actual}")
    if missing_files and not case.ignore_regression_files_assertions:
        failures.append("回归落盘文件缺失")
    if case.expect_postmortem and not postmortem_exists:
        failures.append("预期应存在失效原因复盘单，但未找到")
    if not case.expect_postmortem and postmortem_exists:
        failures.append("预期不应存在失效原因复盘单，但检测到存在")

    tracking_legacy_warnings = []
    tracking_actionable_issues = []
    tracking_severity_categories: dict[str, int] = {}
    if tracking:
        tracking_severity_categories = dict(sorted(tracking["summary"].get("severity_categories", {}).items()))
        for issue in tracking["issues"]:
            if issue["severity"] == "warn" and issue["category"] in LEGACY_TRACKING_WARNINGS:
                tracking_legacy_warnings.append(issue)
            else:
                tracking_actionable_issues.append(issue)
        if not case.ignore_tracking_assertions and case.expect_tracking_errors is not None and tracking["summary"]["errors"] != case.expect_tracking_errors:
            failures.append(f"tracking errors 预期 {case.expect_tracking_errors}，实际 {tracking['summary']['errors']}")
        if not case.ignore_tracking_assertions and case.expect_tracking_warnings is not None and tracking["summary"]["warnings"] != case.expect_tracking_warnings:
            failures.append(f"tracking warnings 预期 {case.expect_tracking_warnings}，实际 {tracking['summary']['warnings']}")
        if not case.ignore_tracking_assertions:
            for category, minimum in case.minimum_tracking_severity_categories:
                actual = int(tracking_severity_categories.get(category, 0))
                if actual < minimum:
                    failures.append(f"tracking severity_categories `{category}` 预期至少 {minimum}，实际 {actual}")
    elif case.expect_tracking_errors is not None and not case.ignore_tracking_assertions:
        failures.append("预期应跑 tracking 脚本，但结果缺失")

    if agency and case.expect_agency_warnings is not None:
        if agency["summary"]["warnings"] != case.expect_agency_warnings:
            failures.append(f"agency warnings 预期 {case.expect_agency_warnings}，实际 {agency['summary']['warnings']}")
        for needle in case.minimum_agency_messages:
            if not any(needle in issue["message"] for issue in agency["issues"]):
                failures.append(f"agency issues 未命中预期文案片段: {needle}")
    if agency and case.minimum_agency_warnings is not None:
        if agency["summary"]["warnings"] < case.minimum_agency_warnings:
            failures.append(f"agency warnings 预期至少 {case.minimum_agency_warnings}，实际 {agency['summary']['warnings']}")
        for needle in case.minimum_agency_messages:
            if not any(needle in issue["message"] for issue in agency["issues"]):
                failures.append(f"agency issues 未命中预期文案片段: {needle}")
    if version and case.expect_version_errors is not None:
        if version["summary"]["errors"] != case.expect_version_errors:
            failures.append(f"version errors 预期 {case.expect_version_errors}，实际 {version['summary']['errors']}")
        for needle in case.minimum_version_messages:
            if not any(needle in issue["message"] for issue in version["issues"]):
                failures.append(f"version issues 未命中预期文案片段: {needle}")
    if verdict and case.expect_verdict_errors is not None:
        if verdict["summary"]["errors"] != case.expect_verdict_errors:
            failures.append(f"verdict errors 预期 {case.expect_verdict_errors}，实际 {verdict['summary']['errors']}")
        for needle in case.minimum_verdict_messages:
            if not any(needle in issue["message"] for issue in verdict["issues"]):
                failures.append(f"verdict issues 未命中预期文案片段: {needle}")
    if narrow and case.expect_narrow_warnings is not None:
        if narrow["summary"]["warnings"] < case.expect_narrow_warnings:
            failures.append(f"narrow warnings 预期至少 {case.expect_narrow_warnings}，实际 {narrow['summary']['warnings']}")
        for needle in case.minimum_narrow_messages:
            if not any(needle in issue["message"] for issue in narrow["issues"]):
                failures.append(f"narrow issues 未命中预期文案片段: {needle}")

    return {
        "group": case.group,
        "name": case.name,
        "case_dir": str(case_dir.relative_to(ROOT)),
        "chapter_count": len(list((case_dir / "正文").glob("*.md"))),
        "expected": case.expected,
        "expected_recovery_note": case.expect_recovery_note,
        "lint_ok": lint["ok"],
        "errors": lint["summary"]["errors"],
        "warnings": lint["summary"]["warnings"],
        "severity_categories": lint["summary"]["severity_categories"],
        "issues": lint["issues"],
        "tracking": tracking,
        "tracking_severity_categories": tracking_severity_categories,
        "tracking_legacy_warnings": tracking_legacy_warnings,
        "tracking_actionable_issues": tracking_actionable_issues,
        "promotion": promotion,
        "agency": agency,
        "version": version,
        "verdict": verdict,
        "narrow": narrow,
        "regression_files_present": existing_files,
        "regression_files_missing": missing_files,
        "postmortem_exists": postmortem_exists,
        "skipped": False,
        "skip_reason": "",
        "pass": not failures,
        "failures": failures,
    }


def render_markdown(results: list[dict], mode: str) -> str:
    lines = ["# story-review 回归脚本汇总", "", f"- 模式：`{mode}`", f"- 样本数：`{len(results)}`"]
    passed = sum(1 for item in results if item["pass"])
    skipped = sum(1 for item in results if item.get("skipped"))
    lines.extend([f"- 通过：`{passed}`", f"- 失败：`{len(results) - passed}`", f"- 跳过：`{skipped}`", ""])
    lines.append("| 状态 | 组别 | 样本 | 章节 | scene_lint | 追踪脚本 | 角色/版本/裁决 | 回归落盘 |")
    lines.append("| --- | --- | --- | ---: | --- | --- | --- | --- |")
    for item in results:
        if item.get("skipped"):
            lines.append(f"| `SKIP` | `{item['group']}` | `{Path(item['case_dir']).name}` | 0 | `未跑` | `未跑` | `未跑` | `样本缺失` |")
            continue
        lint_text = f"errors={item['errors']}, warnings={item['warnings']}"
        if item["severity_categories"]:
            lint_text += "; " + ", ".join(f"{k}={v}" for k, v in sorted(item["severity_categories"].items()))
        tracking_text = "未跑" if item["tracking"] is None else f"errors={item['tracking']['summary']['errors']}, warnings={item['tracking']['summary']['warnings']}, 旧债={len(item['tracking_legacy_warnings'])}"
        if item["tracking_severity_categories"]:
            tracking_text += "; " + ", ".join(f"{k}={v}" for k, v in sorted(item["tracking_severity_categories"].items()))
        promotion_text = "未跑" if item["promotion"] is None else f"missing_cards={item['promotion']['summary']['missing_cards']}"
        if item["agency"] is not None:
            promotion_text += f"; agency_warn={item['agency']['summary']['warnings']}"
        if item["version"] is not None:
            promotion_text += f"; version_err={item['version']['summary']['errors']}"
        if item["verdict"] is not None:
            promotion_text += f"; verdict_err={item['verdict']['summary']['errors']}"
        if item["narrow"] is not None:
            promotion_text += f"; narrow_warn={item['narrow']['summary']['warnings']}"
        files_ok = "齐" if not item["regression_files_missing"] else f"缺 {len(item['regression_files_missing'])} 个"
        lines.append(f"| `{'PASS' if item['pass'] else 'FAIL'}` | `{item['group']}` | `{Path(item['case_dir']).name}` | {item['chapter_count']} | `{lint_text}` | `{tracking_text}` | `{promotion_text}` | `{files_ok}` |")

    lines.extend(["", "## 明细", ""])
    for item in results:
        lines.extend([
            f"### {Path(item['case_dir']).name}",
            f"- 组别：`{item['group']}`",
            f"- 预期：{item['expected']}",
            f"- 预期动作：{item['expected_recovery_note']}",
            f"- 状态：`{'SKIP' if item.get('skipped') else ('PASS' if item['pass'] else 'FAIL')}`",
        ])
        if item.get("skipped"):
            lines.extend([
                f"- 跳过原因：`{item['skip_reason']}`",
                "",
            ])
            continue
        lines.extend([
            f"- scene_lint：`errors={item['errors']}, warnings={item['warnings']}`",
            "- 分类：`" + (", ".join(f"{k}={v}" for k, v in sorted(item["severity_categories"].items())) if item["severity_categories"] else "无") + "`",
            "- 追踪脚本：`未跑`" if item["tracking"] is None else f"- 追踪脚本：`errors={item['tracking']['summary']['errors']}, warnings={item['tracking']['summary']['warnings']}`",
            "- 追踪分类：`" + (", ".join(f"{k}={v}" for k, v in sorted(item["tracking_severity_categories"].items())) if item["tracking_severity_categories"] else "无") + "`",
            "- 缺卡脚本：`未跑`" if item["promotion"] is None else f"- 缺卡脚本：`missing_cards={item['promotion']['summary']['missing_cards']}`",
            "- 人物脚本：`未跑`" if item["agency"] is None else f"- 人物脚本：`warnings={item['agency']['summary']['warnings']}`",
            "- 版本脚本：`未跑`" if item["version"] is None else f"- 版本脚本：`errors={item['version']['summary']['errors']}`",
            "- 裁决脚本：`未跑`" if item["verdict"] is None else f"- 裁决脚本：`errors={item['verdict']['summary']['errors']}`",
            "- 过程脚本：`未跑`" if item["narrow"] is None else f"- 过程脚本：`warnings={item['narrow']['summary']['warnings']}`",
            f"- 失效原因复盘单：`{'有' if item['postmortem_exists'] else '无'}`",
            f"- 回归落盘：`{'齐' if not item['regression_files_missing'] else '缺失'}`",
        ])
        if item["regression_files_missing"]:
            lines.append("- 缺失回归落盘：`" + "`, `".join(item["regression_files_missing"]) + "`")
        if item["failures"]:
            lines.append("- 断言失败：")
            lines.extend([f"  - {failure}" for failure in item["failures"]])
        if item["issues"]:
            lines.append("- scene_lint 摘要：")
            lines.extend([f"  - `{issue['severity']}.{issue['category']}` {Path(issue['path']).name}: {issue['message']}" for issue in item["issues"][:6]])
        if item["tracking_legacy_warnings"]:
            lines.append(f"- 追踪旧债：`{len(item['tracking_legacy_warnings'])}`")
            lines.extend([f"  - `{issue['severity']}.{issue['category']}` {Path(issue['path']).name}: {issue['message']}" for issue in item["tracking_legacy_warnings"][:4]])
        if item["tracking_actionable_issues"]:
            lines.append("- 追踪脚本摘要：")
            lines.extend([f"  - `{issue['severity']}.{issue['category']}` {Path(issue['path']).name}: {issue['message']}" for issue in item["tracking_actionable_issues"][:4]])
        if item["promotion"] and item["promotion"]["candidates"]:
            missing = [c for c in item["promotion"]["candidates"] if not c["has_card"]]
            if missing:
                lines.append("- 缺卡候选：")
                lines.extend([f"  - `{candidate['name']}`: 章节={','.join(candidate['chapters'])}，动作命中={candidate['action_hits']}" for candidate in missing[:4]])
        if item["agency"] and item["agency"]["issues"]:
            lines.append("- 人物脚本摘要：")
            lines.extend([f"  - `{issue['severity']}.{issue['category']}` {Path(issue['path']).name}: {issue['message']}" for issue in item["agency"]["issues"][:4]])
        if item["version"] and item["version"]["issues"]:
            lines.append("- 版本脚本摘要：")
            lines.extend([f"  - `{issue['severity']}.{issue['category']}` {Path(issue['path']).name}: {issue['message']}" for issue in item["version"]["issues"][:4]])
        if item["verdict"] and item["verdict"]["issues"]:
            lines.append("- 裁决脚本摘要：")
            lines.extend([f"  - `{issue['severity']}.{issue['category']}` {Path(issue['path']).name}: {issue['message']}" for issue in item["verdict"]["issues"][:4]])
        if item["narrow"] and item["narrow"]["issues"]:
            lines.append("- 过程脚本摘要：")
            lines.extend([f"  - `{issue['severity']}.{issue['category']}` {Path(issue['path']).name}: {issue['message']}" for issue in item["narrow"]["issues"][:4]])
        if not item["issues"] and not (item["tracking"] and item["tracking"]["issues"]):
            lines.append("- 问题摘要：`无`")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    global ROOT, TEST_ROOT
    parser = argparse.ArgumentParser(description="Run story-review regression baseline summary.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--quick", action="store_true", help="只跑最小回归集。")
    mode_group.add_argument("--full", action="store_true", help="跑完整回归集（默认）。")
    parser.add_argument("--root", default=str(ROOT), help="项目根目录，默认取脚本所在项目。")
    parser.add_argument("--output", default=None, help="Markdown summary output path.")
    parser.add_argument("--json-output", default=None, help="JSON summary output path.")
    parser.add_argument("--group", action="append", default=[], help="仅运行指定组别，可重复传入。")
    parser.add_argument("--only-existing", action="store_true", help="只跑当前 root 下存在样本目录的 case。")
    args = parser.parse_args(argv)

    ROOT = Path(args.root).resolve()
    TEST_ROOT = ROOT / "测试"
    if not TEST_ROOT.exists():
        raise SystemExit(f"未找到测试目录: {TEST_ROOT}")

    mode = "quick" if args.quick else "full"
    selected_cases = [case for case in CASES if mode == "full" or case.tier == "minimal"]
    if args.group:
        group_set = set(args.group)
        selected_cases = [case for case in selected_cases if case.group in group_set]
    if args.only_existing:
        selected_cases = [case for case in selected_cases if (TEST_ROOT / case.rel_dir).exists()]
    results = [collect_case(case) for case in selected_cases]
    markdown = render_markdown(results, mode)
    output_path = Path(args.output) if args.output else TEST_ROOT / "story-review_回归脚本汇总.md"
    json_output_path = Path(args.json_output) if args.json_output else TEST_ROOT / "story-review_回归脚本汇总.json"
    output_path.write_text(markdown, encoding="utf-8")
    json_output_path.write_text(json.dumps({"cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Markdown: {output_path}")
    print(f"JSON: {json_output_path}")
    return 0 if all(item["pass"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
