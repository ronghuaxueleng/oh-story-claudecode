#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


CHECK_WORDS = ("认", "验", "查", "翻", "对", "看", "开", "记")
CHECK_PHRASES = (
    "认印",
    "认簿",
    "认账",
    "认条",
    "验封",
    "验章",
    "对码",
    "对账",
    "翻簿",
    "翻账",
    "开箱",
    "复验",
    "改簿",
    "压签",
)
CONSEQUENCE_PHRASES = (
    "让位",
    "退开",
    "封车",
    "封路",
    "改记",
    "改道",
    "让出",
    "被扣",
    "停手",
    "先按",
    "先烧",
    "先发",
    "先给",
    "归寒山监",
    "失去",
    "被迫",
)
TEMPLATE_JARGON = (
    "第三方该给的那口逻辑",
    "高位角色",
    "顺位",
    "公开改判",
    "这一下比",
    "真正值钱的是",
    "这就是第二口收益",
    "现在争的已经不是",
)
VERDICT_LEAK_PATTERNS = (
    "第一口外部反应，落了",
    "第二口外部反应，落了",
    "第一口群体改线",
    "第二口群体改线",
    "这就是第一个即时后果",
    "这就是第二个即时后果",
    "这就是",
    "终于落了",
)


@dataclass
class Issue:
    path: str
    category: str
    severity: str
    message: str


def make_issue(path: Path, category: str, severity: str, message: str) -> Issue:
    return Issue(str(path), category, severity, message)


def paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return parts


def count_hits(text: str, phrases: tuple[str, ...]) -> int:
    return sum(text.count(item) for item in phrases)


def check_like(text: str) -> bool:
    return count_hits(text, CHECK_PHRASES) > 0 or sum(text.count(word) for word in CHECK_WORDS) >= 3


def consequence_like(text: str) -> bool:
    return count_hits(text, CONSEQUENCE_PHRASES) > 0


def lint_file(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    text = path.read_text(encoding="utf-8")

    for jargon in TEMPLATE_JARGON:
        if jargon in text:
            issues.append(make_issue(path, "模板", "error", f"命中模板术语/判价句: {jargon}"))
    for pattern in VERDICT_LEAK_PATTERNS:
        if pattern in text:
            issues.append(make_issue(path, "模板", "error", f"命中验收句/模板节点标签回流: {pattern}"))

    paras = paragraphs(text)
    consecutive_check = 0
    for idx, para in enumerate(paras, start=1):
        if check_like(para):
            consecutive_check += 1
        else:
            consecutive_check = 0
        if consecutive_check >= 2:
            window = "\n\n".join(paras[max(0, idx - 3): idx])
            consequence_hits = count_hits(window, CONSEQUENCE_PHRASES)
            if consequence_hits == 0:
                issues.append(make_issue(path, "模板", "error", f"连续 {consecutive_check} 段偏查证链，但缺少现实后果词"))
                break
            if consequence_hits <= 1:
                issues.append(make_issue(path, "模板", "warn", f"连续 {consecutive_check} 段偏查证链，现实后果承载偏弱"))
                break

    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint template exhaustion / over-checking risk.")
    parser.add_argument("path", help="chapter file path")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    path = Path(args.path)
    issues = lint_file(path)
    payload = {
        "ok": not any(issue.severity == "error" for issue in issues),
        "summary": {
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warn"),
            "total": len(issues),
        },
        "issues": [asdict(issue) for issue in issues],
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
