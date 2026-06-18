#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


INTERFACE_PHRASES = ("报名字", "递木签", "递木牌", "递簿", "认数", "记门", "见证", "传话", "背书", "落字", "报人头")
INTERFACE_VERBS = ("认", "记", "说", "递", "报")
AGENCY_PHRASES = ("往前一步", "往前半步", "逼了一步", "卡进", "卡住", "扔在案上", "折成两截", "抬手指向", "护得更死", "去堵车", "盯死", "横过来")
AGENCY_VERBS = ("拦", "抢", "逼", "顶", "赌", "退", "扛", "藏", "拖", "砸", "勒", "扑")
SOFT_SPOT_MARKERS = ("弟弟", "妹妹", "母亲", "父亲", "孩子", "软肋")
SOFT_ROLE_HINTS = ("队里最弱的人", "小七", "病人", "冻死", "拖累", "活下来", "先活")
TRANSLATOR_PATTERNS = (
    "这就是",
    "这意味着",
    "现在争的已经不是",
    "真正值钱的是",
    "对啊",
    "所以",
)
AUTHORIAL_SUPPORT_PATTERNS = (
    "压法",
    "第一口群体改线",
    "第一个即时后果",
    "第二个即时后果",
    "更像活路",
    "终于裂了",
)
HIGH_VALUE_HINTS = ("少东家", "代管", "巡边使", "坊主", "掌柜", "票号", "高位", "代管矿监")
WINDOW_RADIUS = 3
COMMON_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费"
    "廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和"
    "穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜"
    "阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍虞万"
    "支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇"
    "邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山"
    "谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶"
    "郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双闻莘党翟谭"
    "贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿"
    "阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙"
    "东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾沙乜养鞠须丰巢"
    "关蒯相查后荆红游竺权逯盖益桓公岳"
)
SURNAME_PATTERN = re.compile(rf"([{COMMON_SURNAMES}][\u4e00-\u9fff]{{1,2}})")
NICKNAME_PATTERN = re.compile(r"(阿[\u4e00-\u9fff]|小[\u4e00-\u9fff]|老[\u4e00-\u9fff])")
STOP_NAMES = {
    "今天", "昨夜", "今夜", "明天", "外头", "堂外", "这一", "一下", "所有人",
    "你们", "我们", "他们", "那几个", "这几个", "这里", "那边", "这边",
}
PRIVATE_STATE_MARKERS = ("病", "热", "冷", "抖", "哭", "怕", "烧", "拖累", "弟弟", "妹妹", "孩子", "眼眶", "血丝")
INVALID_NAME_SUFFIXES = {"把", "这", "的", "眼", "也", "上", "都", "若", "今", "明", "口", "路", "货", "白", "下", "时", "管", "枚"}
INVALID_NAME_PREFIXES = {"这", "那", "都", "时", "白", "管", "路"}


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
        if (parent / "正文").exists() and (parent / "设定").exists():
            return parent
    return path


def chapter_files(project_root: Path) -> list[Path]:
    body_dir = project_root / "正文"
    return sorted(body_dir.glob("*.md"))


def role_cards(project_root: Path) -> list[Path]:
    role_dir = project_root / "设定" / "角色"
    if not role_dir.exists():
        return []
    return sorted(role_dir.glob("*.md"))


def infer_roles_from_body(project_root: Path) -> list[tuple[str, bool, bool]]:
    counts: dict[str, int] = {}
    body_dir = project_root / "正文"
    for chapter in sorted(body_dir.glob("*.md")):
        text = chapter.read_text(encoding="utf-8")
        for line in text.splitlines():
            for name in extract_candidate_names(line):
                if name in STOP_NAMES:
                    continue
                if "第" in name or "章" in name:
                    continue
                counts[name] = counts.get(name, 0) + line.count(name)
    roles: list[tuple[str, bool, bool]] = []
    for name, freq in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        soft, high_value, translator_like, support_like, _ = contextual_role_flags(project_root, name)
        if freq < 2 and not (soft or high_value or translator_like or support_like):
            continue
        roles.append((name, soft, high_value))
    return roles[:12]


def extract_candidate_names(line: str) -> list[str]:
    names = SURNAME_PATTERN.findall(line)
    names.extend(NICKNAME_PATTERN.findall(line))
    cleaned: list[str] = []
    for name in names:
        if len(name) < 2 or len(name) > 3:
            continue
        if name[0] in INVALID_NAME_PREFIXES:
            continue
        if name[-1] in INVALID_NAME_SUFFIXES:
            continue
        cleaned.append(name)
    return cleaned


def detect_roles(cards: list[Path]) -> list[tuple[str, bool, bool]]:
    roles: list[tuple[str, bool, bool]] = []
    for card in cards:
        name = card.stem
        text = card.read_text(encoding="utf-8")
        soft = any(marker in text for marker in SOFT_SPOT_MARKERS) or any(marker in text for marker in SOFT_ROLE_HINTS)
        high_value = any(marker in text for marker in HIGH_VALUE_HINTS)
        roles.append((name, soft, high_value))
    return roles


def collect_name_context(project_root: Path, name: str) -> str:
    snippets: list[str] = []
    for chapter in chapter_files(project_root):
        for line in chapter.read_text(encoding="utf-8").splitlines():
            if name in line:
                snippets.append(line)
    return "\n".join(snippets)


def contextual_role_flags(project_root: Path, name: str) -> tuple[bool, bool, bool, bool, int]:
    context = collect_name_context(project_root, name)
    soft = any(marker in context for marker in SOFT_SPOT_MARKERS)
    high_value = any(marker in context for marker in HIGH_VALUE_HINTS)
    translator_like = any(marker in context for marker in TRANSLATOR_PATTERNS)
    support_like = any(marker in context for marker in AUTHORIAL_SUPPORT_PATTERNS)
    private_hits = sum(context.count(marker) for marker in PRIVATE_STATE_MARKERS)
    return soft, high_value, translator_like, support_like, private_hits


def role_context_hits(text: str, name: str) -> tuple[int, int, int]:
    interface_hits = 0
    agency_hits = 0
    mentions = 0
    for line in text.splitlines():
        if name in line:
            mentions += 1
            interface_hits += sum(line.count(token) for token in INTERFACE_VERBS)
            agency_hits += sum(line.count(token) for token in AGENCY_VERBS)
    return mentions, interface_hits, agency_hits


def role_translator_hits(text: str, name: str) -> int:
    hits = 0
    for line in text.splitlines():
        if name in line:
            hits += sum(line.count(token) for token in TRANSLATOR_PATTERNS)
    return hits


def role_authorial_support_hits(text: str, name: str) -> int:
    hits = 0
    for line in text.splitlines():
        if name in line:
            hits += sum(line.count(token) for token in AUTHORIAL_SUPPORT_PATTERNS)
    return hits


def role_window_stats(text: str, name: str) -> tuple[int, int, int]:
    lines = text.splitlines()
    mentions = 0
    interface_hits = 0
    agency_hits = 0
    for idx, line in enumerate(lines):
        if name not in line:
            continue
        mentions += 1
        start = max(0, idx - WINDOW_RADIUS)
        end = min(len(lines), idx + WINDOW_RADIUS + 1)
        window = "\n".join(lines[start:end])
        interface_hits += sum(window.count(token) for token in INTERFACE_PHRASES)
        interface_hits += sum(window.count(token) for token in INTERFACE_VERBS)
        agency_hits += sum(window.count(token) for token in AGENCY_PHRASES)
        agency_hits += sum(window.count(token) for token in AGENCY_VERBS)
    return mentions, interface_hits, agency_hits


def role_window_pattern_hits(text: str, name: str, patterns: tuple[str, ...]) -> int:
    lines = text.splitlines()
    hits = 0
    for idx, line in enumerate(lines):
        if name not in line:
            continue
        start = max(0, idx - WINDOW_RADIUS)
        end = min(len(lines), idx + WINDOW_RADIUS + 1)
        window = "\n".join(lines[start:end])
        hits += sum(window.count(token) for token in patterns)
    return hits


def lint_project(project_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    chapters = chapter_files(project_root)
    body = "\n".join(path.read_text(encoding="utf-8") for path in chapters)
    cards = role_cards(project_root)
    roles = detect_roles(cards) if cards else infer_roles_from_body(project_root)
    for name, is_soft, is_high_value in roles:
        mentions, interface_hits, agency_hits = role_window_stats(body, name)
        soft_flag, high_value_flag, _, support_like, private_hits = contextual_role_flags(project_root, name)
        is_soft = is_soft or soft_flag
        is_high_value = is_high_value or high_value_flag
        if mentions < 2 and not ((is_high_value and support_like) or is_soft):
            continue
        translator_hits = role_window_pattern_hits(body, name, TRANSLATOR_PATTERNS)
        support_hits = role_window_pattern_hits(body, name, AUTHORIAL_SUPPORT_PATTERNS)
        if interface_hits >= 4 and agency_hits <= 1:
            issues.append(make_issue(project_root / "正文", "人物", "warn", f"角色 `{name}` 近似只承担接口功能，缺少主动动作"))
        if translator_hits >= 1 and agency_hits <= 2:
            issues.append(make_issue(project_root / "正文", "人物", "warn", f"角色 `{name}` 疑似承担翻译器/验收句功能，缺少利益动作"))
        if is_high_value and (support_hits >= 1 or support_like) and agency_hits <= 2:
            issues.append(make_issue(project_root / "正文", "人物", "warn", f"高价值角色 `{name}` 疑似靠旁白补义/判价立住，代价动作不足"))
        if is_soft and mentions >= 2:
            if private_hits <= 1:
                issues.append(make_issue(project_root / "正文", "人物", "warn", f"软肋角色 `{name}` 疑似缺少私人状态回针"))

    if not cards and len(chapters) >= 2:
        first_text = chapters[0].read_text(encoding="utf-8")
        later_text = "\n".join(path.read_text(encoding="utf-8") for path in chapters[1:])
        soft_names = []
        for name, _, _ in roles:
            first_context = "\n".join(line for line in first_text.splitlines() if name in line)
            if sum(first_context.count(marker) for marker in PRIVATE_STATE_MARKERS) >= 2:
                soft_names.append(name)
        for name in soft_names:
            later_context = "\n".join(line for line in later_text.splitlines() if name in line)
            if later_context and sum(later_context.count(marker) for marker in PRIVATE_STATE_MARKERS) == 0:
                issues.append(make_issue(project_root / "正文", "人物", "warn", f"软肋角色 `{name}` 首章已立私人代价，后续章节疑似掉线成接口位"))
    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint character agency / interface-function drift.")
    parser.add_argument("path", help="project root or any file inside project")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    project_root = find_project_root(Path(args.path))
    issues = lint_project(project_root)
    payload = {
        "ok": not any(issue.severity == "error" for issue in issues),
        "summary": {
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warn"),
            "total": len(issues),
        },
        "issues": [asdict(issue) for issue in issues],
        "project_root": str(project_root),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
