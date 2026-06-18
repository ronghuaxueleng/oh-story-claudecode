#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


NARROW_TOKENS = ("旧册", "账", "册", "规矩", "口径", "名单", "班牌", "拍回", "翻开", "补名", "认", "查清", "按册")
REALITY_TOKENS = ("拖起来", "抬炭", "扳闸", "引火", "抽离", "扣进掌心", "换班", "补两个", "先点", "开火", "上坡", "挪位", "逼", "压住")
AUTHORIAL_VERDICT_TOKENS = ("因为这句不是", "这一下比", "这比", "因为它不是", "这半刻，比任何大道理都真", "因为从", "像是忽然")
TEMPLATE_LABEL_TOKENS = (
    "这是第一口外部反应",
    "这是第二口外部反应",
    "这就是现实起效",
    "这就是第一个即时后果",
    "这就是第二个即时后果",
    "第一口外部反应",
    "第二口外部反应",
)


@dataclass
class Issue:
    path: str
    category: str
    severity: str
    message: str


def make_issue(path: Path, severity: str, message: str) -> Issue:
    return Issue(str(path), "过程/句层", severity, message)


def lint_file(path: Path) -> list[Issue]:
    text = path.read_text(encoding="utf-8")
    narrow_hits = sum(text.count(token) for token in NARROW_TOKENS)
    reality_hits = sum(text.count(token) for token in REALITY_TOKENS)
    verdict_hits = [token for token in AUTHORIAL_VERDICT_TOKENS if token in text]
    label_hits = [token for token in TEMPLATE_LABEL_TOKENS if token in text]
    issues: list[Issue] = []
    if narrow_hits >= 20 and narrow_hits >= reality_hits * 3:
        issues.append(make_issue(path, "warn", f"中段疑似偏‘翻册/认账/拍板’推进：流程词命中={narrow_hits}，现实改线词命中={reality_hits}"))
    for token in verdict_hits:
        issues.append(make_issue(path, "warn", f"命中作者代判句/总结句：{token}"))
    for token in label_hits:
        issues.append(make_issue(path, "warn", f"命中隐性模板标签句：{token}"))
    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Detect scene narrowness and authorial verdict leakage.")
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    path = Path(args.path).resolve()
    files = [path] if path.is_file() else sorted((path / "正文").glob("*.md")) if (path / "正文").exists() else sorted(path.glob("*.md"))
    issues: list[Issue] = []
    for file in files:
        issues.extend(lint_file(file))
    payload = {
        "ok": not any(issue.severity == "error" for issue in issues),
        "summary": {
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "warnings": sum(1 for issue in issues if issue.severity == "warn"),
            "total": len(issues),
        },
        "issues": [asdict(issue) for issue in issues],
        "path": str(path),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
