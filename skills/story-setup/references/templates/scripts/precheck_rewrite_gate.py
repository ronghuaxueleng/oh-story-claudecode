#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])")
DIALOGUE_RE = re.compile(
    r'“([^”\n]{1,120})”|"([^"\n]{1,120})"|「([^」\n]{1,120})」|『([^』\n]{1,120})』'
)


def resolve_support_file(filename: str) -> Path:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / filename,
        script_dir.parents[1] / "agent-references" / filename,
        script_dir.parent / "references" / "agent-references" / filename,
        script_dir.parent / "references" / "governance" / filename,
        script_dir.parent / ".codex" / "skills" / "story-setup" / "references" / "agent-references" / filename,
        script_dir.parent / "skills" / "story-setup" / "references" / "agent-references" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


DEFAULT_CONFIG = resolve_support_file("precheck_rewrite_gate.config.json")


@dataclass
class Finding:
    kind: str
    sentence: str
    reason: str


def load_config(path: Path | None = None) -> dict:
    config_path = path or DEFAULT_CONFIG
    return json.loads(config_path.read_text(encoding="utf-8"))


def merge_config(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = merge_config(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            merged[key] = list(dict.fromkeys([*current, *value]))
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_profile_overrides(path: Path | None) -> dict:
    if not path or not path.is_file():
        return {}
    profile = json.loads(path.read_text(encoding="utf-8"))
    overrides = profile.get("precheck_overrides")
    pretty_detail = overrides.get("pretty_detail") if isinstance(overrides, dict) else None
    if not isinstance(pretty_detail, dict) or not any(
        isinstance(pretty_detail.get(key), list) and pretty_detail[key]
        for key in ("fact_anchor_patterns", "action_anchor_patterns")
    ):
        raise SystemExit(
            f"profile 缺少有效 precheck_overrides，请重新拆书并重建 profile: {path}"
        )
    return overrides


def resolve_default_profile(source_path: Path) -> Path | None:
    profile_dir = source_path.parent / "profiles"
    if not profile_dir.is_dir():
        return None
    candidates = list(profile_dir.glob("*.project.profile.json"))
    if not candidates:
        candidates = list(profile_dir.glob("*.profile.json"))
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def resolve_default_override(source_path: Path) -> Path | None:
    candidates = (
        source_path.parent / "precheck_rewrite_gate.override.json",
        source_path.with_name(f"{source_path.stem}.precheck.override.json"),
    )
    return next((path for path in candidates if path.is_file()), None)


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


def mask_protected_patterns(text: str, patterns: list[str]) -> str:
    masked = text
    for pattern in patterns:
        masked = re.sub(pattern, "", masked)
    return masked


def collect_atmosphere_hits(text: str, tokens: list[str], token_patterns: dict[str, str]) -> list[str]:
    hits: list[str] = []
    for token in tokens:
        pattern = token_patterns.get(token)
        if pattern:
            matched = re.search(pattern, text) is not None
        else:
            matched = len(token) > 1 and token in text
        if matched:
            hits.append(token)
    return hits


def collect_anchor_hits(text: str, tokens: list[str], patterns: list[str]) -> list[str]:
    hits = [token for token in tokens if len(token) > 1 and token in text]
    hits.extend(pattern for pattern in patterns if re.search(pattern, text))
    return list(dict.fromkeys(hits))


def find_pretty_details(sentences: list[str], detail_config: dict) -> list[Finding]:
    findings: list[Finding] = []
    atmosphere_tokens = detail_config.get("atmosphere_tokens", [])
    atmosphere_patterns = detail_config.get("atmosphere_patterns", {})
    protected_patterns = detail_config.get("protected_patterns", [])
    fact_anchor_tokens = detail_config.get("fact_anchor_tokens", [])
    fact_anchor_patterns = detail_config.get("fact_anchor_patterns", [])
    action_anchor_tokens = detail_config.get("action_anchor_tokens", [])
    action_anchor_patterns = detail_config.get("action_anchor_patterns", [])
    min_atmosphere_hits = int(detail_config.get("min_atmosphere_hits", 1))
    max_anchor_hits = int(detail_config.get("max_anchor_hits", 0))
    for sentence in sentences:
        atmosphere_text = mask_protected_patterns(sentence, protected_patterns)
        atmosphere_hits = collect_atmosphere_hits(
            atmosphere_text,
            atmosphere_tokens,
            atmosphere_patterns,
        )
        fact_hits = collect_anchor_hits(sentence, fact_anchor_tokens, fact_anchor_patterns)
        action_hits = collect_anchor_hits(sentence, action_anchor_tokens, action_anchor_patterns)
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
    dialogues: list[str] = []
    for match in DIALOGUE_RE.finditer(text):
        value = next((group for group in match.groups() if group is not None), "")
        if value and CHINESE_RE.search(value):
            dialogues.append(value.strip())
    return dialogues


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
    parser.add_argument("--config", help="可选：预检配置 JSON；不传时默认读取部署后的 story-setup agent-references 或 skill 内对应配置")
    parser.add_argument("--profile", help="可选：book/project profile JSON；不传时自动读取正文同级 profiles/ 中最新 profile")
    parser.add_argument("--override", help="可选：项目级预检覆盖 JSON；不传时自动读取正文同级 override 文件")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    text = read_text(path)
    sentences = split_sentences(text)
    dialogues = find_dialogues(text)
    config = load_config(Path(args.config).resolve() if args.config else None)
    profile_path = Path(args.profile).resolve() if args.profile else resolve_default_profile(path)
    config = merge_config(config, load_profile_overrides(profile_path))
    override_path = Path(args.override).resolve() if args.override else resolve_default_override(path)
    if override_path:
        config = merge_config(config, load_config(override_path))
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
    if profile_path:
        print(f"profile: {profile_path}")
    if override_path:
        print(f"override: {override_path}")
    for key, values in findings.items():
        print(f"{key}: {len(values)}")


if __name__ == "__main__":
    main()
