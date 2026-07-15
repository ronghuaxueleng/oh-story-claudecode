#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])")
DIALOGUE_RE = re.compile(r"[“\"]([^”\"\n]{1,120})[”\"]")
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "references" / "governance" / "precheck_rewrite_gate.config.json"


@dataclass
class Finding:
    kind: str
    sentence: str
    reason: str


def load_config(path: Path | None = None) -> dict:
    config_path = path or DEFAULT_CONFIG
    return json.loads(config_path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if CHINESE_RE.search(p)]


def compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def find_pretty_details(sentences: list[str], detail_config: dict) -> list[Finding]:
    findings: list[Finding] = []
    atmosphere_tokens = detail_config.get("atmosphere_tokens", [])
    fact_anchor_tokens = detail_config.get("fact_anchor_tokens", [])
    action_anchor_tokens = detail_config.get("action_anchor_tokens", [])
    min_atmosphere_hits = int(detail_config.get("min_atmosphere_hits", 1))
    max_anchor_hits = int(detail_config.get("max_anchor_hits", 0))
    for sentence in sentences:
        atmosphere_hits = [t for t in atmosphere_tokens if t in sentence]
        fact_hits = [t for t in fact_anchor_tokens if t in sentence]
        action_hits = [t for t in action_anchor_tokens if t in sentence]
        anchor_hits = fact_hits + action_hits
        if len(atmosphere_hits) >= min_atmosphere_hits and len(anchor_hits) <= max_anchor_hits:
            findings.append(
                Finding(
                    "pretty_detail",
                    sentence,
                    f"氛围词偏多 {atmosphere_hits}，现场锚点不足，事实锚点={fact_hits}，动作锚点={action_hits}",
                )
            )
    return findings


def find_author_explains(sentences: list[str], patterns: list[re.Pattern[str]]) -> list[Finding]:
    findings: list[Finding] = []
    for sentence in sentences:
        for pat in patterns:
            if pat.search(sentence):
                findings.append(Finding("author_explain", sentence, f"匹配作者解释模式 {pat.pattern}"))
                break
    return findings


def find_early_judgements(sentences: list[str], patterns: list[re.Pattern[str]]) -> list[Finding]:
    findings: list[Finding] = []
    for sentence in sentences:
        for pat in patterns:
            if pat.search(sentence):
                findings.append(Finding("early_judgement", sentence, f"匹配提前判断模式 {pat.pattern}"))
                break
    return findings


def find_dialogues(text: str) -> list[str]:
    return [m.group(1).strip() for m in DIALOGUE_RE.finditer(text) if CHINESE_RE.search(m.group(1))]


def find_high_function_dialogues(
    dialogues: list[str],
    explain_patterns: list[re.Pattern[str]],
    judgement_patterns: list[re.Pattern[str]],
    command_patterns: list[re.Pattern[str]],
    min_length: int,
    min_score: int,
) -> list[Finding]:
    findings: list[Finding] = []
    for line in dialogues:
        score = 0
        explain_hits = [pat.pattern for pat in explain_patterns if pat.search(line)]
        judgement_hits = [pat.pattern for pat in judgement_patterns if pat.search(line)]
        command_hits = [pat.pattern for pat in command_patterns if pat.search(line)]
        if explain_hits:
            score += 1
        if judgement_hits:
            score += 1
        if command_hits:
            score += 1
        if len(line) >= min_length:
            score += 1
        if "，" in line or "。" in line:
            score += 1
        if score >= min_score:
            reason = f"疑似高功能对白，解释模式={len(explain_hits)}，判断模式={len(judgement_hits)}，指令模式={len(command_hits)}，长度={len(line)}"
            findings.append(Finding("high_function_dialogue", line, reason))
    return findings


def find_tidy_closure(sentences: list[str], patterns: list[re.Pattern[str]], tail_window: int) -> list[Finding]:
    findings: list[Finding] = []
    tail = sentences[-tail_window:] if len(sentences) >= tail_window else sentences
    for sentence in tail:
        for pat in patterns:
            if pat.search(sentence):
                findings.append(Finding("tidy_closure", sentence, f"匹配段尾收口模式 {pat.pattern}"))
                break
    return findings


def write_report(path: Path, findings: dict[str, list[Finding]]) -> tuple[Path, Path]:
    json_path = path.with_name(path.stem + "-重写预检.json")
    md_path = path.with_name(path.stem + "-重写预检.md")
    serializable = {k: [asdict(x) for x in v] for k, v in findings.items()}
    json_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# 重写预检报告：{path.name}", ""]
    for key, values in findings.items():
        lines.append(f"## {key} ({len(values)})")
        lines.append("")
        if not values:
            lines.append("无")
            lines.append("")
            continue
        for idx, item in enumerate(values, start=1):
            lines.append(f"{idx}. `{item.sentence}`")
            lines.append(f"原因：{item.reason}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="重写前闸门预检脚本")
    parser.add_argument("path", help="待检查的 md/txt 文件")
    parser.add_argument("--config", help="可选：预检配置 JSON；不传时默认读取 skill 内 references/governance/precheck_rewrite_gate.config.json")
    args = parser.parse_args()

    path = Path(args.path)
    text = read_text(path)
    sentences = split_sentences(text)
    dialogues = find_dialogues(text)
    config = load_config(Path(args.config).resolve() if args.config else None)
    detail_config = config.get("pretty_detail", {})
    pattern_groups = config.get("patterns", {})
    dialogue_config = config.get("dialogue", {})
    closure_config = config.get("closure", {})

    findings = {
        "pretty_detail": find_pretty_details(sentences, detail_config),
        "author_explain": find_author_explains(sentences, compile_patterns(pattern_groups.get("author_explain", []))),
        "early_judgement": find_early_judgements(sentences, compile_patterns(pattern_groups.get("early_judgement", []))),
        "high_function_dialogue": find_high_function_dialogues(
            dialogues,
            compile_patterns(dialogue_config.get("explain_patterns", [])),
            compile_patterns(dialogue_config.get("judgement_patterns", [])),
            compile_patterns(dialogue_config.get("command_patterns", [])),
            int(dialogue_config.get("min_length", 18)),
            int(dialogue_config.get("min_score", 3)),
        ),
        "tidy_closure": find_tidy_closure(
            sentences,
            compile_patterns(pattern_groups.get("tidy_closure", [])),
            int(closure_config.get("tail_window", 4)),
        ),
    }

    json_path, md_path = write_report(path, findings)
    print(f"written: {json_path}")
    print(f"written: {md_path}")
    for key, values in findings.items():
        print(f"{key}: {len(values)}")


if __name__ == "__main__":
    main()
