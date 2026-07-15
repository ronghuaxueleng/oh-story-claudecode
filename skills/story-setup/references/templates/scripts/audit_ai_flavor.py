#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_LEXICON = "通用高风险词类词典.json"
DEFAULT_SUFFIX = "-审计报告"

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")

CONNECTOR_TERMS = [
    "首先", "其次", "再次", "最后", "此外", "与此同时", "另一方面",
    "值得注意的是", "需要指出的是", "综上所述", "总的来说", "换言之", "换句话说",
]

SHORT_FICTION_RULES = [
    ("binary_contrast", "二分句壳", "high", re.compile(r"不是[^。！？\n]{1,30}而是[^。！？\n]{1,40}")),
    ("binary_contrast_alt", "二分句壳变体", "high", re.compile(r"(并非|不再是)[^。！？\n]{1,28}而是[^。！？\n]{1,40}")),
    ("serial_outline", "编号式展开", "medium", re.compile(r"(首先|第一)[^。！？\n]{0,40}(其次|第二)[^。！？\n]{0,40}(最后|第三)")),
    ("definition_summary", "定义解释总结壳", "medium", re.compile(r"(所谓|本质上|归根结底|核心在于)[^。！？\n]{1,40}")),
    ("fake_interaction", "结尾假互动", "medium", re.compile(r"(你是否|你有没有|不妨想想|欢迎在评论区|希望对你有帮助)[^。\n]{0,24}[。！？]?$")),
    ("translationese", "翻译腔壳", "medium", re.compile(r"(对于[^，。\n]{1,20}而言|在[^，。\n]{1,20}层面|某种程度上|从某种意义上说)")),
    ("empty_judgement", "空判断壳", "low", re.compile(r"(非常重要|意义重大|至关重要|显著提升|全面提升|高质量发展)")),
    ("fiction_micro_reaction", "小说反应模板", "medium", re.compile(r"(背后一凉|心头一紧|倒吸一口凉气|瞳孔一缩|胃里一阵翻涌|眼中闪过)")),
    ("fiction_dialogue_tag", "公式化对话标签", "medium", re.compile(r"(缓缓开口|冷冷说道|淡淡说道|沉声说道|轻声说道)")),
    ("telling_emotion", "直说情绪", "medium", re.compile(r"(他|她)(感到|觉得|意识到|明白了)[^。！？\n]{1,18}")),
    ("colon_template", "冒号说明模板", "medium", re.compile(r"[^\n：”“]{2,18}：(?![“\"])[^\n]{6,40}")),
    ("realization_template", "顿悟模板", "medium", re.compile(r"(直到这一刻|就在这时|这时候|他终于明白|她终于明白)[^。！？\n]{0,24}")),
    ("summary_uplift", "总结拔高句", "medium", re.compile(r"(更重要的是|说到底|归根到底|归根结底|某种意义上)[^。！？\n]{0,30}")),
    ("rule_notice_shell", "规则公告壳", "high", re.compile(r"(请严格遵守以下规则|否则后果自负|违反规则者|不得以任何形式|现发布如下公告)")),
]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    label: str
    severity: str
    count: int
    examples: list[str]


@dataclass(frozen=True)
class Metric:
    name: str
    value: float
    threshold: float
    status: str
    note: str


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def resolve_support_file(filename: str) -> Path:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / filename,
        script_dir.parent / "references" / "agent-references" / filename,
        script_dir.parent / "references" / "governance" / filename,
        script_dir.parent / ".codex" / "skills" / "story-setup" / "references" / "agent-references" / filename,
        script_dir.parent / "skills" / "story-setup" / "references" / "agent-references" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def load_lexicon(path: Path | None = None) -> dict:
    lexicon_path = path or resolve_support_file(DEFAULT_LEXICON)
    return json.loads(read_text(lexicon_path))


def split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in text.split("\n\n") if part.strip()]


def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_SPLIT_RE.split(text)
    return [part.strip() for part in parts if CHINESE_RE.search(part)]


def count_chinese(text: str) -> int:
    return len(CHINESE_RE.findall(text))


def coeff_var(values: Iterable[int | float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    mean_value = statistics.mean(values)
    if mean_value == 0:
        return 0.0
    return statistics.pstdev(values) / mean_value


def sample_matches(text: str, pattern: re.Pattern[str], limit: int = 3) -> list[str]:
    items: list[str] = []
    for match in pattern.finditer(text):
        items.append(match.group(0)[:80])
        if len(items) >= limit:
            break
    return items


def category_severity_map() -> dict[str, str]:
    return {
        "delete_empty_connectors": "medium",
        "downgrade_formal_verbs": "medium",
        "downgrade_abstract_buzzwords": "medium",
        "translationese_markers": "medium",
        "sentence_shells": "high",
        "fiction_reaction_templates": "medium",
        "fiction_action_templates": "medium",
        "atmosphere_templates": "medium",
        "atmosphere_horror_templates": "medium",
        "direct_psychology_markers": "medium",
        "explanatory_summary_markers": "medium",
        "precision_emotion_templates": "medium",
        "fear_reaction_templates": "medium",
        "romance_explanatory_shells": "high",
        "romance_reaction_templates": "medium",
        "dialogue_polish_templates": "medium",
        "suspense_explanatory_shells": "high",
        "reveal_templates": "medium",
        "suspense_action_templates": "medium",
        "rule_notice_shells": "high",
        "system_panel_decompression": "high",
    }


def allowed_lexicon_categories(lexicon: dict) -> list[str]:
    base = [
        "delete_empty_connectors",
        "downgrade_formal_verbs",
        "downgrade_abstract_buzzwords",
        "translationese_markers",
        "sentence_shells",
        "fiction_reaction_templates",
        "fiction_action_templates",
        "atmosphere_templates",
        "direct_psychology_markers",
        "explanatory_summary_markers",
        "precision_emotion_templates",
        "system_panel_decompression",
    ]
    categories = lexicon.get("categories", {})
    extra = [key for key, node in categories.items() if node.get("regex_rules")]
    ordered: list[str] = []
    seen: set[str] = set()
    for key in base + extra:
        if key in categories and key not in seen:
            ordered.append(key)
            seen.add(key)
    return ordered


def build_lexicon_findings(text: str, lexicon: dict) -> list[Finding]:
    findings: list[Finding] = []
    category_map = lexicon.get("categories", {})
    category_severity = category_severity_map()
    allowed = allowed_lexicon_categories(lexicon)
    for category in allowed:
        node = category_map.get(category, {})
        hits: list[tuple[str, int]] = []
        for token in node.get("tokens", []):
            count = text.count(token)
            if count:
                hits.append((token, count))
        if not hits:
            continue
        hits.sort(key=lambda item: (-item[1], -len(item[0])))
        findings.append(
            Finding(
                rule_id=category,
                label=category,
                severity=category_severity.get(category, "medium"),
                count=sum(count for _, count in hits),
                examples=[f"{token} x{count}" for token, count in hits[:5]],
            )
        )
    return findings


def build_dynamic_regex_findings(text: str, lexicon: dict) -> list[Finding]:
    findings: list[Finding] = []
    category_map = lexicon.get("categories", {})
    category_severity = category_severity_map()
    for category in allowed_lexicon_categories(lexicon):
        node = category_map.get(category, {})
        for idx, rule in enumerate(node.get("regex_rules", []), start=1):
            pattern_text = rule.get("pattern")
            label = rule.get("label") or f"{category}-regex-{idx}"
            if not pattern_text:
                continue
            pattern = re.compile(pattern_text)
            matches = list(pattern.finditer(text))
            if not matches:
                continue
            findings.append(
                Finding(
                    rule_id=f"{category}::{label}",
                    label=label,
                    severity=category_severity.get(category, "medium"),
                    count=len(matches),
                    examples=sample_matches(text, pattern),
                )
            )
    return findings


def build_structure_findings(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, label, severity, pattern in SHORT_FICTION_RULES:
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        findings.append(
            Finding(
                rule_id=rule_id,
                label=label,
                severity=severity,
                count=len(matches),
                examples=sample_matches(text, pattern),
            )
        )
    return findings


def repeated_openings(sentences: list[str], top_n: int = 5) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for sentence in sentences:
        normalized = re.sub(r"^[^\u4e00-\u9fffA-Za-z]+", "", sentence)
        key = normalized[:4]
        if len(key.strip()) >= 2:
            counter[key] += 1
    return [(token, count) for token, count in counter.most_common(top_n) if count >= 3]


def repeated_ngrams(text: str, min_len: int = 4, max_len: int = 8, top_n: int = 8) -> list[tuple[str, int]]:
    compact = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
    counter: Counter[str] = Counter()
    for n in range(min_len, max_len + 1):
        for idx in range(0, max(len(compact) - n + 1, 0)):
            gram = compact[idx:idx + n]
            if len(set(gram)) == 1:
                continue
            if not CHINESE_RE.search(gram):
                continue
            if count_chinese(gram) < max(2, math.ceil(n / 2)):
                continue
            counter[gram] += 1
    filtered = [
        (gram, count)
        for gram, count in counter.items()
        if count >= 3 and not gram.startswith("的") and not gram.endswith("的") and not is_noise_ngram(gram)
    ]
    filtered.sort(key=lambda item: (-item[1], -len(item[0]), item[0]))
    return filtered[:top_n]


def is_noise_ngram(text: str) -> bool:
    if len(text) < 4:
        return True
    if text in {"这个", "那个", "他们", "我们"}:
        return True
    return False


def build_metrics(text: str) -> list[Metric]:
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)
    zh_count = count_chinese(text)
    sentence_lengths = [count_chinese(sentence) for sentence in sentences if count_chinese(sentence) > 0]
    paragraph_lengths = [count_chinese(paragraph) for paragraph in paragraphs if count_chinese(paragraph) > 0]
    connector_hits = sum(text.count(token) for token in CONNECTOR_TERMS)
    dialogue_lines = sum(1 for line in text.splitlines() if "“" in line or "”" in line)

    metrics: list[Metric] = []

    sent_cv = coeff_var(sentence_lengths)
    para_cv = coeff_var(paragraph_lengths)
    connector_per_1k = connector_hits / max(zh_count, 1) * 1000
    dialogue_ratio = dialogue_lines / max(len([line for line in text.splitlines() if line.strip()]), 1)

    metrics.append(metric_from_bounds("sentence_length_cv", sent_cv, low=0.38, note="句长变化过低时，短篇叙事容易显得过度平滑。"))
    metrics.append(metric_from_bounds("paragraph_length_cv", para_cv, low=0.55, note="段长变化过低时，短篇段落容易像统一后处理。"))
    metrics.append(metric_from_bounds("connector_per_1k", connector_per_1k, high=18.0, note="连接词密度过高时，短篇叙事容易出现说明腔。"))
    metrics.append(metric_from_bounds("dialogue_line_ratio", dialogue_ratio, low=0.12, note="短篇小说对话占比过低时，叙述容易发板。"))
    return metrics


def metric_from_bounds(name: str, value: float, low: float | None = None, high: float | None = None, note: str = "") -> Metric:
    if low is not None and value < low:
        return Metric(name=name, value=round(value, 4), threshold=low, status="warn", note=note)
    if high is not None and value > high:
        return Metric(name=name, value=round(value, 4), threshold=high, status="warn", note=note)
    threshold = low if low is not None else high if high is not None else 0.0
    return Metric(name=name, value=round(value, 4), threshold=threshold, status="ok", note=note)


def severity_weight(severity: str) -> int:
    return {"high": 6, "medium": 3, "low": 1}.get(severity, 1)


def score_family(rule_id: str) -> str:
    return rule_id.split("::", 1)[0]


def summarize_status(score: int) -> str:
    if score >= 70:
        return "high-risk"
    if score >= 40:
        return "medium-risk"
    return "low-risk"


def build_recommendations(findings: list[Finding], metrics: list[Metric], repeated_heads: list[tuple[str, int]], hotspots: list[tuple[str, int]]) -> list[str]:
    tips: list[str] = []
    finding_ids = {finding.rule_id for finding in findings}
    if "downgrade_abstract_buzzwords" in finding_ids:
        tips.append("把抽象名词改成具体动作、对象或后果，不要只做同义词替换。")
    if "delete_empty_connectors" in finding_ids or any(metric.name == "connector_per_1k" and metric.status == "warn" for metric in metrics):
        tips.append("先删空连接词，再重写承接句，避免“首先/其次/综上所述”式模板推进。")
    if "binary_contrast" in finding_ids or repeated_heads:
        tips.append("打散重复句壳，特别是“不是A而是B”“这意味着/这说明”这类开头。")
    if hotspots:
        tips.append("针对重复热点短语逐条人工复查，优先处理出现 3 次以上的短语。")
    if any(metric.name == "sentence_length_cv" and metric.status == "warn" for metric in metrics):
        tips.append("有意识拉开句长差，插入短句、残句和口语停顿。")
    if not tips:
        tips.append("当前文本没有明显单一污染源，优先做人工朗读和局部重写。")
    return tips[:5]


def audit_text(text: str, lexicon: dict) -> dict:
    findings = build_lexicon_findings(text, lexicon) + build_structure_findings(text) + build_dynamic_regex_findings(text, lexicon)
    findings.sort(key=lambda item: (-severity_weight(item.severity), -item.count, item.rule_id))
    metrics = build_metrics(text)
    repeated_heads = repeated_openings(split_sentences(text))
    hotspots = repeated_ngrams(text)
    family_scores: dict[str, int] = defaultdict(int)
    for finding in findings:
        family_scores[score_family(finding.rule_id)] += severity_weight(finding.severity) * min(finding.count, 6)
    score = sum(min(value, 18) for value in family_scores.values())
    score += sum(8 for metric in metrics if metric.status == "warn")
    score += min(sum(count for _, count in repeated_heads), 12)
    score += min(sum(count for _, count in hotspots[:3]), 12)
    score = min(score, 100)
    return {
        "summary": {
            "score": score,
            "status": summarize_status(score),
            "findings": len(findings),
            "warn_metrics": sum(1 for metric in metrics if metric.status == "warn"),
            "chars": count_chinese(text),
        },
        "findings": [
            {
                "rule_id": finding.rule_id,
                "label": finding.label,
                "severity": finding.severity,
                "count": finding.count,
                "examples": finding.examples,
            }
            for finding in findings
        ],
        "metrics": [
            {
                "name": metric.name,
                "value": metric.value,
                "threshold": metric.threshold,
                "status": metric.status,
                "note": metric.note,
            }
            for metric in metrics
        ],
        "repeated_openings": [{"text": text, "count": count} for text, count in repeated_heads],
        "hotspots": [{"text": text, "count": count} for text, count in hotspots],
        "recommendations": build_recommendations(findings, metrics, repeated_heads, hotspots),
    }


def render_markdown(path: Path, report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# 短篇小说 AI 味审计报告",
        "",
        f"- 文件：`{path}`",
        f"- 风险分：`{summary['score']}`",
        f"- 风险级别：`{summary['status']}`",
        f"- 命中项：`{summary['findings']}`",
        f"- 预警指标：`{summary['warn_metrics']}`",
        f"- 汉字数：`{summary['chars']}`",
        "",
        "## 主要命中",
    ]
    if report["findings"]:
        for item in report["findings"][:12]:
            example_text = "；".join(item["examples"]) if item["examples"] else "-"
            lines.append(f"- `{item['severity']}` {item['label']} x{item['count']}：{example_text}")
    else:
        lines.append("- 无明显规则命中。")

    lines.extend(["", "## 指标", ""])
    for item in report["metrics"]:
        lines.append(f"- `{item['name']}` = {item['value']}，状态：`{item['status']}`，说明：{item['note']}")

    lines.extend(["", "## 重复热点", ""])
    if report["repeated_openings"]:
        for item in report["repeated_openings"]:
            lines.append(f"- 句首重复：`{item['text']}` x{item['count']}")
    if report["hotspots"]:
        for item in report["hotspots"][:8]:
            lines.append(f"- 短语热点：`{item['text']}` x{item['count']}")
    if not report["repeated_openings"] and not report["hotspots"]:
        lines.append("- 无明显重复热点。")

    lines.extend(["", "## 建议", ""])
    for item in report["recommendations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def iter_input_files(input_path: Path, glob_pattern: str) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(path for path in input_path.rglob(glob_pattern) if path.is_file())


def build_output_path(src: Path, output: str | None, suffix: str, ext: str) -> Path:
    if output:
        return Path(output)
    return src.with_name(f"{src.stem}{suffix}.{ext}")


def cmd_audit(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    files = iter_input_files(input_path, args.glob)
    if not files:
        raise SystemExit("no input files found")
    lexicon = load_lexicon(Path(args.lexicon) if args.lexicon else None)

    all_reports: dict[str, dict] = {}
    for src in files:
        report = audit_text(read_text(src), lexicon=lexicon)
        all_reports[str(src)] = report
        print(f"{src}: score={report['summary']['score']} status={report['summary']['status']}")
        if input_path.is_file():
            if args.format in ("json", "both"):
                json_path = build_output_path(src, args.output, args.suffix, "json")
                write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                print(f"written: {json_path}")
            if args.format in ("md", "both"):
                md_path = build_output_path(src, None if args.format == "both" else args.output, args.suffix, "md")
                write_text(md_path, render_markdown(src, report))
                print(f"written: {md_path}")
            continue

        if args.output_dir:
            base = Path(args.output_dir)
            rel = src.relative_to(input_path)
            if args.format in ("json", "both"):
                json_path = base / rel.parent / f"{src.stem}{args.suffix}.json"
                write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            if args.format in ("md", "both"):
                md_path = base / rel.parent / f"{src.stem}{args.suffix}.md"
                write_text(md_path, render_markdown(src, report))

    if input_path.is_dir() and args.index:
        index_path = Path(args.index)
        write_text(index_path, json.dumps(all_reports, ensure_ascii=False, indent=2) + "\n")
        print(f"written: {index_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit Chinese short fiction for common AI-flavor patterns.")
    parser.add_argument("input", help="input file or directory")
    parser.add_argument("--lexicon", help="lexicon json path")
    parser.add_argument("--glob", default="*.md", help="glob used when input is a directory")
    parser.add_argument("--format", choices=["json", "md", "both"], default="both", help="output format")
    parser.add_argument("-o", "--output", help="output path when input is a file")
    parser.add_argument("--output-dir", help="output directory when input is a directory")
    parser.add_argument("--index", help="summary json path when input is a directory")
    parser.add_argument("--suffix", default=DEFAULT_SUFFIX, help="output suffix without extension")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    cmd_audit(args)


if __name__ == "__main__":
    main()
