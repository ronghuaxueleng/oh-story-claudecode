#!/usr/bin/env python3
"""
小说 AI 味结构审计器（轻量版）

目标：
- 不判断小说好不好
- 只抓容易把小说正文写成“高一致性 AI 整理稿”的常见结构壳

用法：
  .venv/bin/python scripts/audit_novel_ai_flavor.py path/to/file.txt
  .venv/bin/python scripts/audit_novel_ai_flavor.py path/to/file.txt --json

退出码：
  0 = 未命中
  1 = 有命中
  2 = 执行错误
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


PATTERNS = [
    ("binary_contrast", re.compile(r"(不是.{0,20}而是|不在于.{0,20}而在于|与其说.{0,20}不如说)")),
    ("sequence_shell", re.compile(r"(先.{0,12}再|先.{0,12}然后|第一步|第二步|最后一步|从.{0,8}到.{0,8})")),
    ("author_verdict", re.compile(r"(我这才明白|我终于知道|原来他一直|这说明|那一刻我终于|我忽然明白)")),
    ("summary_ending", re.compile(r"(终于轻了|终于过去了|那根.*终于断了|真正放下了|总算结束了|像背了很久的东西)")),
    ("ai_transition", re.compile(r"(忽然觉得|忽然想起|只觉得|有点想笑|低头笑了一下|其实不是想笑)")),
    ("core_claim", re.compile(r"(真正重要的是|真正的问题是|核心在于|本质上|最后比拼的是)")),
    ("theme_explanation", re.compile(r"(更重要的是|说到底|归根结底|这意味着|真正让[我他她].{0,12}的是|问题从来不是.{0,18}而是)")),
    ("direct_mental_state", re.compile(r"([我他她](?:一下子|忽然|终于|才)?(?:觉得|感到|感觉到|意识到|明白了?|知道了?))")),
    ("realization_shell", re.compile(r"(直到这(?:一刻|时候)|那一刻[我他她]?终于|后来才知道|这时候)")),
    ("polished_dialogue_tag", re.compile(r"(沉默了.{0,4}(?:秒|会儿)|缓缓开口|低声说道|轻声说道|抿了抿唇|垂下眼眸|视线微微一顿)")),
    ("standard_reaction", re.compile(r"(鼻尖一酸|眼眶(?:微微)?发热|呼吸一窒|心口发闷|嘴角勾起一抹苦笑|喉咙像堵了(?:团|块)?棉花)")),
    ("task_list_sentence", re.compile(r"((?:写在|记在).{0,10}[：:].{0,40}[、，].{0,20}[、，].{0,20}|便签上[：:].{0,40}[、，].{0,20}|清单上[：:].{0,40}[、，].{0,20})")),
    ("fuzzy_adverb_stack", re.compile(r"((?:像是|仿佛|似乎|微微|轻轻|缓缓|下意识|不由得|忍不住).{0,16}(?:顿|笑|缩|发紧|发麻|开口|垂下|看了一眼))")),
]


SECTION_HEADER_RE = re.compile(r"^#{3,}\s*\d+[.\u3001]?\s*$")
OPENING_CHARS = 1200
OPENING_PLOT_WINDOW = 2200


def is_section_header(line: str) -> bool:
    return bool(SECTION_HEADER_RE.match(line.strip()))


def split_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    current_title = "正文"
    current_lines: list[str] = []
    current_start = 1

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        if is_section_header(line):
            if current_lines:
                sections.append(
                    {
                        "title": current_title,
                        "start_line": current_start,
                        "lines": current_lines,
                    }
                )
            current_title = line.strip()
            current_lines = []
            current_start = line_no + 1
            continue
        if line.strip():
            current_lines.append(line)

    if current_lines:
        sections.append(
            {
                "title": current_title,
                "start_line": current_start,
                "lines": current_lines,
            }
        )

    return sections


def split_paragraphs(text: str) -> list[dict]:
    paragraphs: list[dict] = []
    sections = split_sections(text)
    if sections:
        for section in sections:
            for offset, line in enumerate(section["lines"]):
                stripped = line.strip()
                if not stripped:
                    continue
                paragraphs.append(
                    {
                        "text": stripped,
                        "line": section["start_line"] + offset,
                        "section": section["title"],
                    }
                )
        return paragraphs

    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped:
            paragraphs.append({"text": stripped, "line": idx, "section": "正文"})
    return paragraphs


def count_sentences(paragraph: str) -> int:
    return len([s for s in re.split(r"[。！？!?]", paragraph) if s.strip()])


def paragraph_lengths(paragraphs: list[dict]) -> list[int]:
    return [len(p["text"]) for p in paragraphs if p["text"].strip()]


def find_hits(text: str) -> list[dict]:
    hits = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        for name, pattern in PATTERNS:
            if pattern.search(line):
                hits.append(
                    {
                        "line": idx,
                        "type": name,
                        "text": line.strip()[:140],
                    }
                )
    return hits


def summarize_line_hit_types(hits: list[dict]) -> dict[str, int]:
    counter = Counter(hit["type"] for hit in hits)
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def detect_uniform_paragraphs(paragraphs: list[dict]) -> list[dict]:
    findings = []
    lengths = paragraph_lengths(paragraphs)
    if len(lengths) < 6:
        return findings
    window = 4
    for i in range(0, len(lengths) - window + 1):
        chunk = lengths[i : i + window]
        avg = sum(chunk) / window
        if avg == 0:
            continue
        spread = max(chunk) - min(chunk)
        if spread <= avg * 0.25:
            first = paragraphs[i]
            findings.append(
                {
                    "paragraph_index": i + 1,
                    "line": first["line"],
                    "section": first["section"],
                    "type": "uniform_paragraph_block",
                    "detail": chunk,
                }
            )
    return findings


def detect_dense_flashback(paragraphs: list[dict]) -> list[dict]:
    findings = []
    flashback_markers = ("那天", "后来", "还有一回", "第一回", "第二回", "上回", "去年", "那时候")
    window = 8
    for i in range(0, len(paragraphs) - window + 1):
        chunk = paragraphs[i : i + window]
        joined = "\n".join(item["text"] for item in chunk)
        marker_count = sum(joined.count(m) for m in flashback_markers)
        if marker_count >= 4 and len(joined) > 220:
            first = chunk[0]
            findings.append(
                {
                    "paragraph_index": i + 1,
                    "line": first["line"],
                    "section": first["section"],
                    "type": "dense_flashback_chain",
                    "detail": f"markers={marker_count}, len={len(joined)}, window={window}",
                }
            )
    return findings


def detect_over_effective_dialogue(paragraphs: list[dict]) -> list[dict]:
    findings = []
    window = 6
    for i in range(0, len(paragraphs) - window + 1):
        chunk = paragraphs[i : i + window]
        lines = [item["text"] for item in chunk if item["text"].strip()]
        if len(lines) < window:
            continue
        dialogue_lines = [line for line in lines if "“" in line and "”" in line]
        if len(dialogue_lines) >= 4 and len(dialogue_lines) / len(lines) >= 0.65:
            short_count = sum(1 for line in dialogue_lines if len(line) <= 16)
            if short_count >= 3:
                first = chunk[0]
                findings.append(
                    {
                        "paragraph_index": i + 1,
                        "line": first["line"],
                        "section": first["section"],
                        "type": "over_effective_dialogue_block",
                        "detail": f"dialogue={len(dialogue_lines)}, short={short_count}, window={window}",
                    }
                )
    return findings


def opening_slice(text: str) -> str:
    return text[:OPENING_CHARS]


def opening_paragraphs(text: str) -> list[str]:
    return [
        line.strip()
        for line in opening_slice(text).splitlines()
        if line.strip() and not is_section_header(line)
    ]


def detect_opening_signature_risks(text: str) -> tuple[list[dict], dict]:
    snippet = opening_slice(text)
    paras = opening_paragraphs(text)
    question_count = snippet.count("？") + snippet.count("?")
    exclaim_count = snippet.count("！") + snippet.count("!")
    ellipsis_count = snippet.count("…") + snippet.count("......")
    dash_count = snippet.count("—") + snippet.count("——")
    dialogue_count = snippet.count("“")
    single_sentence_ratio = 0.0
    if paras:
        single_sentence_ratio = sum(1 for p in paras if count_sentences(p) <= 1) / len(paras)

    metrics = {
        "chars": len(snippet),
        "question_count": question_count,
        "exclaim_count": exclaim_count,
        "ellipsis_count": ellipsis_count,
        "dash_count": dash_count,
        "dialogue_count": dialogue_count,
        "single_sentence_ratio": round(single_sentence_ratio, 4),
    }

    findings = []
    if dialogue_count >= 8:
        findings.append(
            {
                "type": "opening_dialogue_overload",
                "detail": f"dialogue={dialogue_count}, window={OPENING_CHARS}",
            }
        )
    if exclaim_count == 0 and ellipsis_count == 0 and dash_count == 0:
        findings.append(
            {
                "type": "opening_punctuation_flat",
                "detail": f"q={question_count}, !={exclaim_count}, …={ellipsis_count}, —={dash_count}",
            }
        )
    return findings, metrics


def load_profile(profile_path: Path | None = None) -> dict:
    if not profile_path:
        return {}
    path = profile_path
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def detect_opening_signal_overload(text: str, profile: dict) -> list[dict]:
    snippet = text[:OPENING_PLOT_WINDOW]
    groups = profile.get("opening_signal_groups", {})
    hit_groups = []
    for name, terms in groups.items():
        if any(term in snippet for term in terms):
            hit_groups.append(name)

    findings = []
    threshold = int(profile.get("opening_signal_group_threshold", 6))
    if len(hit_groups) >= threshold:
        findings.append(
            {
                "type": "opening_signal_overload",
                "detail": f"groups={len(hit_groups)}:{','.join(hit_groups)} chars={OPENING_PLOT_WINDOW} threshold={threshold}",
            }
        )
    return findings


def detect_opening_reveal_chain(text: str, profile: dict) -> list[dict]:
    snippet = text[:OPENING_PLOT_WINDOW]
    raw_patterns = profile.get("opening_chain_patterns", {})
    matched_steps = []
    positions = []
    for name, pattern_text in raw_patterns.items():
        pattern = re.compile(pattern_text)
        match = pattern.search(snippet)
        if match:
            matched_steps.append(name)
            positions.append(match.start())

    findings = []
    threshold = int(profile.get("opening_chain_threshold", 4))
    if len(matched_steps) >= threshold:
        ordered = positions == sorted(positions)
        findings.append(
            {
                "type": "opening_reveal_chain",
                "detail": f"steps={','.join(matched_steps)} ordered={ordered} threshold={threshold}",
            }
        )
    return findings


def detect_author_stance_overreach(text: str, profile: dict) -> list[dict]:
    snippet = text[:OPENING_PLOT_WINDOW]
    findings = []
    hit_names = []
    for item in profile.get("author_stance_patterns", []):
        name = item["name"]
        pattern = re.compile(item["pattern"])
        if pattern.search(snippet):
            hit_names.append(name)
    threshold = int(profile.get("author_stance_threshold", 2))
    if len(hit_names) >= threshold:
        findings.append(
            {
                "type": "author_stance_overreach",
                "detail": f"patterns={','.join(hit_names)} threshold={threshold}",
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="待审计小说文本")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--profile", help="题材/题面规则配置 JSON，可不填")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    sections = split_sections(text)
    paragraphs = split_paragraphs(text)
    profile_arg = Path(args.profile).resolve() if args.profile else None
    profile = load_profile(profile_arg)

    report = {
        "file": str(path),
        "profile": str(profile_arg) if profile_arg else None,
        "line_hits": find_hits(text),
        "line_hit_types": {},
        "uniform_paragraph_blocks": detect_uniform_paragraphs(paragraphs),
        "dense_flashback_chains": detect_dense_flashback(paragraphs),
        "over_effective_dialogue_blocks": detect_over_effective_dialogue(paragraphs),
        "opening_signature_risks": detect_opening_signature_risks(text)[0],
        "opening_metrics": detect_opening_signature_risks(text)[1],
        "opening_signal_overload": detect_opening_signal_overload(text, profile),
        "opening_reveal_chain": detect_opening_reveal_chain(text, profile),
        "author_stance_overreach": detect_author_stance_overreach(text, profile),
        "section_count": len(sections),
        "paragraph_count": len(paragraphs),
    }
    report["line_hit_types"] = summarize_line_hit_types(report["line_hits"])

    total_hits = (
        len(report["line_hits"])
        + len(report["uniform_paragraph_blocks"])
        + len(report["dense_flashback_chains"])
        + len(report["over_effective_dialogue_blocks"])
        + len(report["opening_signature_risks"])
        + len(report["opening_signal_overload"])
        + len(report["opening_reveal_chain"])
        + len(report["author_stance_overreach"])
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"文件: {path}")
        print(f"小节数: {report['section_count']}")
        print(f"段落数: {report['paragraph_count']}")
        print(f"总命中: {total_hits}")
        print(
            "开篇1200字: "
            f"问号={report['opening_metrics']['question_count']} "
            f"感叹={report['opening_metrics']['exclaim_count']} "
            f"省略号={report['opening_metrics']['ellipsis_count']} "
            f"破折号={report['opening_metrics']['dash_count']} "
            f"对话={report['opening_metrics']['dialogue_count']} "
            f"单句段占比={report['opening_metrics']['single_sentence_ratio']}"
        )
        if report["line_hits"]:
            print("\n[行级命中]")
            for hit in report["line_hits"]:
                print(f"- L{hit['line']} {hit['type']}: {hit['text']}")
        if report["line_hit_types"]:
            print("\n[行级命中类型汇总]")
            for name, count in report["line_hit_types"].items():
                print(f"- {name}: {count}")
        if report["opening_signature_risks"]:
            print("\n[开篇口气风险]")
            for item in report["opening_signature_risks"]:
                print(f"- {item['type']}: {item['detail']}")
        if report["opening_signal_overload"]:
            print("\n[开篇信息投喂过满]")
            for item in report["opening_signal_overload"]:
                print(f"- {item['type']}: {item['detail']}")
        if report["opening_reveal_chain"]:
            print("\n[开篇标准翻刀链]")
            for item in report["opening_reveal_chain"]:
                print(f"- {item['type']}: {item['detail']}")
        if report["author_stance_overreach"]:
            print("\n[作者站位过高]")
            for item in report["author_stance_overreach"]:
                print(f"- {item['type']}: {item['detail']}")
        if report["uniform_paragraph_blocks"]:
            print("\n[段长过匀]")
            for item in report["uniform_paragraph_blocks"]:
                print(
                    f"- {item['section']} L{item['line']} 段 {item['paragraph_index']} 起连续块: {item['detail']}"
                )
        if report["dense_flashback_chains"]:
            print("\n[回忆证据链过密]")
            for item in report["dense_flashback_chains"]:
                print(f"- {item['section']} L{item['line']} 段 {item['paragraph_index']}: {item['detail']}")
        if report["over_effective_dialogue_blocks"]:
            print("\n[高效对白块]")
            for item in report["over_effective_dialogue_blocks"]:
                print(f"- {item['section']} L{item['line']} 段 {item['paragraph_index']}: {item['detail']}")

    return 1 if total_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
