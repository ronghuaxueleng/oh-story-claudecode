#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import difflib
import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_SUFFIX = "-脚本版"
CONNECTOR_CANDIDATES = [
    "但是", "不过", "原来", "此时", "紧接着", "说完之后", "目前", "已经",
    "然后", "可是", "于是", "结果", "后来", "忽然", "突然",
]
THINKING_MARKERS = ["心想", "意识到", "感到", "觉得", "认为", "明白"]
AI_TEMPLATE_WORDS = [
    "眼中闪过", "嘴角勾起", "心中暗道", "一股暖流", "不由得多看了几眼",
    "身子一颤", "心头一紧", "倒吸一口凉气", "目光一凝",
]
DEFAULT_LEXICON = "通用高风险词类词典.json"


HEURISTIC_REGEX_RULES: list[tuple[str, str]] = [
    (r"(?m)^#\s+", ""),
    (r"【天黑后，?不得", "【天黑之后，不能"),
    (r"【本公告不可", "【本公告不能"),
    (r"【当前([^：\n]{1,20})：", r"【目前的\1为"),
    (r"【物业终端已([^\n】]{1,8})。】", r"【物业终端已经\1。】"),
    (r"下一秒，", "紧接着"),
    (r"背后一凉", "背后感到一阵凉"),
    (r"胃里一阵翻涌", "觉得自己的胃很不舒服"),
    (r"手指冷得发麻", "手指已经变得冰凉发麻了"),
]


@dataclass(frozen=True)
class Replacement:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class CorpusProfile:
    files: int
    avg_comma_per_sent: float
    avg_excl_per_sent: float
    avg_quote_per_1k: float
    avg_dialogue_line_ratio: float
    avg_short_para_ratio: float
    avg_long_para_ratio: float
    top_connectors: list[str]


@dataclass(frozen=True)
class LexiconApplyStats:
    category: str
    token: str
    replacement: str
    count: int


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def split_paragraphs(text: str) -> list[str]:
    return [p for p in text.split("\n\n") if p.strip()]


def split_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？])", text)
    return [part for part in parts if part.strip()]


def dedupe_replacements(items: Iterable[Replacement]) -> list[Replacement]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Replacement] = []
    for item in items:
        key = (item.source, item.target, item.kind)
        if item.source == item.target or not item.source.strip():
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def learn_aligned_replacements(
    before_parts: list[str],
    after_parts: list[str],
    kind: str,
    min_len: int = 4,
) -> list[Replacement]:
    learned: list[Replacement] = []
    if len(before_parts) != len(after_parts):
        return learned
    for before, after in zip(before_parts, after_parts):
        if before == after:
            continue
        if len(before.strip()) < min_len or len(after.strip()) < min_len:
            continue
        learned.append(Replacement(before, after, kind))
    return learned


def learn_rules(before_text: str, after_text: str) -> list[Replacement]:
    replacements: list[Replacement] = []
    replacements.extend(
        learn_aligned_replacements(split_paragraphs(before_text), split_paragraphs(after_text), "paragraph", min_len=8)
    )
    replacements.extend(
        learn_aligned_replacements(split_lines(before_text), split_lines(after_text), "line", min_len=4)
    )
    replacements.extend(
        learn_aligned_replacements(split_sentences(before_text), split_sentences(after_text), "sentence", min_len=6)
    )
    replacements.extend(learn_phrase_replacements(before_text, after_text))
    replacements = dedupe_replacements(replacements)
    replacements.sort(key=lambda item: (len(item.source), len(item.target)), reverse=True)
    return replacements


def learn_phrase_replacements(before_text: str, after_text: str) -> list[Replacement]:
    learned: list[Replacement] = []
    for before, after in zip(split_lines(before_text), split_lines(after_text)):
        if before == after:
            continue
        matcher = difflib.SequenceMatcher(a=before, b=after)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            src = before[i1:i2].strip()
            dst = after[j1:j2].strip()
            if not src or not dst or src == dst:
                continue
            if len(src) < 2 or len(dst) < 2:
                continue
            if len(src) > 40 or len(dst) > 60:
                continue
            if "\n" in src or "\n" in dst:
                continue
            learned.append(Replacement(src, dst, "phrase"))

        # 补一层基于句子的 replace 块，专抓局部改写
        for before_sent, after_sent in zip(split_sentences(before), split_sentences(after)):
            if before_sent == after_sent:
                continue
            matcher = difflib.SequenceMatcher(a=before_sent, b=after_sent)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue
                src = before_sent[i1:i2].strip()
                dst = after_sent[j1:j2].strip()
                if not src or not dst or src == dst:
                    continue
                if len(src) < 2 or len(dst) < 2:
                    continue
                if len(src) > 24 or len(dst) > 36:
                    continue
                learned.append(Replacement(src, dst, "micro"))
    return learned


def save_rules(path: Path, replacements: list[Replacement]) -> None:
    payload = {
        "version": 1,
        "replacements": [
            {"from": item.source, "to": item.target, "kind": item.kind}
            for item in replacements
        ],
    }
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def merge_rulesets(rule_sets: list[list[Replacement]], min_freq: int = 1) -> list[Replacement]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for rules in rule_sets:
        seen_in_set: set[tuple[str, str]] = set()
        for item in rules:
            key = (item.source, item.target)
            if key in seen_in_set:
                continue
            seen_in_set.add(key)
            if key not in grouped:
                grouped[key] = {"count": 0, "kinds": Counter(), "source": item.source, "target": item.target}
            grouped[key]["count"] = int(grouped[key]["count"]) + 1
            grouped[key]["kinds"][item.kind] += 1

    merged: list[Replacement] = []
    for key, info in grouped.items():
        if int(info["count"]) < min_freq:
            continue
        kind_counter: Counter = info["kinds"]  # type: ignore[assignment]
        dominant_kind = kind_counter.most_common(1)[0][0]
        merged.append(Replacement(source=key[0], target=key[1], kind=dominant_kind))

    merged = dedupe_replacements(merged)
    merged.sort(key=lambda item: (len(item.source), len(item.target)), reverse=True)
    return merged


def save_profile(path: Path, profile: CorpusProfile) -> None:
    payload = {
        "version": 1,
        "profile": {
            "files": profile.files,
            "avg_comma_per_sent": profile.avg_comma_per_sent,
            "avg_excl_per_sent": profile.avg_excl_per_sent,
            "avg_quote_per_1k": profile.avg_quote_per_1k,
            "avg_dialogue_line_ratio": profile.avg_dialogue_line_ratio,
            "avg_short_para_ratio": profile.avg_short_para_ratio,
            "avg_long_para_ratio": profile.avg_long_para_ratio,
            "top_connectors": profile.top_connectors,
        },
    }
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_rules(paths: list[Path]) -> list[Replacement]:
    loaded: list[Replacement] = []
    for path in paths:
        payload = json.loads(read_text(path))
        for item in payload.get("replacements", []):
            loaded.append(
                Replacement(
                    source=item["from"],
                    target=item["to"],
                    kind=item.get("kind", "exact"),
                )
            )
    loaded = dedupe_replacements(loaded)
    loaded.sort(key=lambda item: (len(item.source), len(item.target)), reverse=True)
    return loaded


def load_profile(path: Path | None) -> CorpusProfile | None:
    if not path:
        return None
    payload = json.loads(read_text(path))
    data = payload["profile"]
    return CorpusProfile(
        files=data["files"],
        avg_comma_per_sent=data["avg_comma_per_sent"],
        avg_excl_per_sent=data["avg_excl_per_sent"],
        avg_quote_per_1k=data["avg_quote_per_1k"],
        avg_dialogue_line_ratio=data["avg_dialogue_line_ratio"],
        avg_short_para_ratio=data["avg_short_para_ratio"],
        avg_long_para_ratio=data["avg_long_para_ratio"],
        top_connectors=list(data["top_connectors"]),
    )


def load_lexicon(path: Path | None = None) -> dict:
    lexicon_path = path or resolve_support_file(DEFAULT_LEXICON)
    return json.loads(read_text(lexicon_path))


def pick_replacement(token: str, options: dict[str, list[str]], prefer_delete: bool) -> str | None:
    values = options.get(token, [])
    if not values:
        return None
    cleaned = [value for value in values if value is not None]
    if prefer_delete and "" in cleaned:
        return ""
    for value in cleaned:
        if value != "":
            return value
    return ""


def literal_replace_count(text: str, old: str, new: str) -> tuple[str, int]:
    if not old:
        return text, 0
    count = text.count(old)
    if not count:
        return text, 0
    return text.replace(old, new), count


def apply_lexicon_categories(
    text: str,
    lexicon: dict,
    categories: list[str],
    prefer_delete: bool,
) -> tuple[str, list[LexiconApplyStats]]:
    stats: list[LexiconApplyStats] = []
    category_map = lexicon.get("categories", {})
    for category in categories:
        node = category_map.get(category, {})
        replacement_map = node.get("preferred_replacements", {})
        for token in node.get("tokens", []):
            replacement = pick_replacement(token, replacement_map, prefer_delete=prefer_delete and category == "delete_empty_connectors")
            if replacement is None:
                continue
            text, count = literal_replace_count(text, token, replacement)
            if count:
                stats.append(LexiconApplyStats(category=category, token=token, replacement=replacement, count=count))
    return text, stats


def apply_lexicon_regex_rules(
    text: str,
    lexicon: dict,
    categories: list[str],
) -> tuple[str, list[LexiconApplyStats]]:
    stats: list[LexiconApplyStats] = []
    category_map = lexicon.get("categories", {})
    for category in categories:
        node = category_map.get(category, {})
        for rule in node.get("regex_rules", []):
            pattern = rule.get("pattern")
            replacement = rule.get("replacement")
            label = rule.get("label", pattern or "")
            if not pattern or replacement is None:
                continue
            new_text, count = re.subn(pattern, replacement, text)
            text = new_text
            if count:
                stats.append(
                    LexiconApplyStats(
                        category=category,
                        token=label,
                        replacement=replacement,
                        count=count,
                    )
                )
    return text, stats


def apply_narrative_particle_patterns(text: str, lexicon: dict) -> tuple[str, list[LexiconApplyStats]]:
    patterns = lexicon.get("categories", {}).get("narrative_particle_relaxers", {}).get("patterns", [])
    stats: list[LexiconApplyStats] = []
    direct_patterns = [
        ("发生了。", "就发生了。"),
        ("他看向", "他先朝"),
        ("围观的人反应过来", "围观的人这时候才反应过来"),
    ]
    for old, new in direct_patterns:
        text, count = literal_replace_count(text, old, new)
        if count:
            stats.append(LexiconApplyStats(category="narrative_particle_relaxers", token=old, replacement=new, count=count))
    for pattern in patterns:
        old = pattern.get("from")
        new = pattern.get("to")
        if not old or not new:
            continue
        text, count = literal_replace_count(text, old, new)
        if count:
            stats.append(LexiconApplyStats(category="narrative_particle_relaxers", token=old, replacement=new, count=count))
    return text, stats


def apply_system_panel_decompression(text: str) -> tuple[str, list[LexiconApplyStats]]:
    stats: list[LexiconApplyStats] = []
    rules = [
        (r"【天黑后，?不得", "【天黑后，不能", "不得", "不能"),
        (r"【本公告不可撤回", "【本公告不能撤回", "不可撤回", "不能撤回"),
        (r"不可转发", "不能转发", "不可转发", "不能转发"),
        (r"不可截图", "不能截图", "不可截图", "不能截图"),
        (r"【零点前，所有业主必须", "【零点前，所有业主都要", "必须", "都要"),
        (r"【物业必须维持", "【物业都要维持", "必须", "都要"),
        (r"【物业终端已激活。】", "【物业终端已经开启。】", "已激活", "已经开启"),
        (r"当前小区", "现在的小区", "当前", "现在"),
        (r"当前安全等级", "目前的安全等级", "当前", "目前"),
        (r"当前公共区域秩序", "目前公共区域的秩序", "当前", "目前"),
        (r"将被视为", "就是", "将被视为", "就是"),
        (r"优先承担", "先承担", "优先承担", "先承担"),
    ]
    for pattern, repl, token, replacement in rules:
        new_text, count = re.subn(pattern, repl, text)
        text = new_text
        if count:
            stats.append(LexiconApplyStats(category="system_panel_decompression", token=token, replacement=replacement, count=count))
    return text, stats


def apply_precision_emotion_templates(text: str) -> tuple[str, list[LexiconApplyStats]]:
    stats: list[LexiconApplyStats] = []
    replacements = [
        ("背后一凉", "背后感到一阵凉"),
        ("心脏猛地一沉", "心里顿时感到很沉重"),
        ("胃里一阵翻涌", "觉得胃很不舒服"),
        ("瞳孔缩紧", "瞳孔一缩"),
        ("冷得发麻", "已经变得冰凉发麻了"),
        ("声音尖得刺耳", "声音很尖锐"),
        ("脸上的血色一下退干净了", "脸上的血色立刻就消失了"),
    ]
    for old, new in replacements:
        text, count = literal_replace_count(text, old, new)
        if count:
            stats.append(LexiconApplyStats(category="precision_emotion_templates", token=old, replacement=new, count=count))
    return text, stats


def apply_exact_replacements(text: str, replacements: list[Replacement]) -> str:
    for item in replacements:
        text = text.replace(item.source, item.target)
    return text


def apply_heuristics(text: str, profile: CorpusProfile | None = None) -> str:
    for pattern, repl in HEURISTIC_REGEX_RULES:
        text = re.sub(pattern, repl, text)

    # 规则句降书面压缩感
    text = re.sub(r"【零点前，所有([^。】]{0,30})必须", r"【零点之前，所有的\1都要", text)
    text = re.sub(r"【任务失败：([^。】]{0,30})优先承担惩罚。】", r"【任务失败后，\1先承担惩罚。】", text)

    # 常见压缩词放松
    text = text.replace("不可撤回", "不能撤回")
    text = text.replace("不可转发", "不能转发")
    text = text.replace("不可截图", "不能截图")
    text = text.replace("当前小区", "现在的小区")
    text = text.replace("当前安全等级", "目前的安全等级")
    text = text.replace("当前公共区域秩序", "目前公共区域的秩序")
    text = text.replace("请在零点前", "在零点之前")
    text = text.replace("将被视为", "就是")
    text = text.replace("同样计入", "也要算在")

    # 标准情绪句降精度
    text = text.replace("心脏猛地一沉", "心里顿时感到很沉重")
    text = text.replace("瞳孔缩紧", "瞳孔一缩")
    text = text.replace("屏幕黑了一瞬", "屏幕黑了一下")
    text = text.replace("拇指下意识按住", "不自觉的按下")

    # 去模板词
    template_relax_map = {
        "眼中闪过": "看了一眼",
        "嘴角勾起": "笑了一下",
        "心中暗道": "心里想着",
        "身子一颤": "抖了一下",
        "心头一紧": "心里一紧",
        "目光一凝": "目光顿了一下",
    }
    for old, new in template_relax_map.items():
        text = text.replace(old, new)

    text = relax_thinking_markers(text)
    text = break_smooth_paragraphs(text, profile)
    text = add_connector_noise(text, profile)

    return text


def relax_thinking_markers(text: str) -> str:
    text = re.sub(r"他感到([^。！？，]{1,12})", r"他心里觉得\1", text)
    text = re.sub(r"她感到([^。！？，]{1,12})", r"她心里觉得\1", text)
    text = re.sub(r"他意识到([^。！？]{1,18})", r"他这才反应过来\1", text)
    text = re.sub(r"她意识到([^。！？]{1,18})", r"她这才反应过来\1", text)
    return text


def break_smooth_paragraphs(text: str, profile: CorpusProfile | None) -> str:
    paras = split_paragraphs(text)
    if not paras:
        return text
    target_long_ratio = profile.avg_long_para_ratio if profile else 0.08
    rewritten: list[str] = []
    long_count = 0
    for para in paras:
        if len(para) > 110 and "“" not in para and para.count("。") >= 2:
            parts = split_sentences(para)
            if len(parts) >= 2:
                # 打断“太平滑”的纯叙述段
                first = "".join(parts[:1]).strip()
                rest = "".join(parts[1:]).strip()
                rewritten.extend([first, rest])
                long_count += 1
                continue
        rewritten.append(para)
    if profile and rewritten:
        current_long_ratio = sum(1 for p in rewritten if len(p) >= 45) / len(rewritten)
        if current_long_ratio < target_long_ratio:
            out: list[str] = []
            split_once = False
            for para in rewritten:
                if not split_once and len(para) > 80 and "“" not in para and "。" in para:
                    parts = split_sentences(para)
                    if len(parts) >= 2:
                        out.extend(["".join(parts[:-1]).strip(), parts[-1].strip()])
                        split_once = True
                        continue
                out.append(para)
            rewritten = out
    return "\n\n".join(rewritten)


def add_connector_noise(text: str, profile: CorpusProfile | None) -> str:
    connectors = profile.top_connectors[:3] if profile and profile.top_connectors else ["但是", "原来", "此时"]
    pairs = [
        ("群里没人骂他。", f"{connectors[0]}目前群里面并没有人骂他。"),
        ("最上面弹出一条公告。", "最上面弹出一条公告。"),
        ("他说着，", "说完之后，"),
    ]
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def mine_corpus_profile(corpus_dir: Path, glob_pattern: str) -> CorpusProfile:
    files = sorted(path for path in corpus_dir.rglob(glob_pattern) if path.is_file())
    rows: list[dict[str, float]] = []
    connector_counter: Counter[str] = Counter()
    for path in files:
        text = read_text(path)
        zh = count_chinese(text)
        if zh < 500:
            continue
        paras = split_paragraphs(text)
        sents = [x for x in re.split(r"[。！？]", text) if re.search(r"[\u4e00-\u9fff]", x)]
        lines = [x for x in text.splitlines() if x.strip()]
        dialogue_lines = sum(1 for x in lines if "“" in x or x.startswith("—") or x.startswith("「"))
        rows.append(
            {
                "comma_per_sent": text.count("，") / max(len(sents), 1),
                "excl_per_sent": text.count("！") / max(len(sents), 1),
                "quote_per_1k": text.count("“") / max(zh, 1) * 1000,
                "dialogue_line_ratio": dialogue_lines / max(len(lines), 1),
                "short_para_ratio": sum(1 for p in paras if len(p) <= 8) / max(len(paras), 1),
                "long_para_ratio": sum(1 for p in paras if len(p) >= 45) / max(len(paras), 1),
            }
        )
        for token in CONNECTOR_CANDIDATES:
            connector_counter[token] += text.count(token)
    if not rows:
        raise SystemExit("no healthy corpus files found")
    top_connectors = [item for item, _ in connector_counter.most_common(5)]
    return CorpusProfile(
        files=len(rows),
        avg_comma_per_sent=round(statistics.mean(r["comma_per_sent"] for r in rows), 3),
        avg_excl_per_sent=round(statistics.mean(r["excl_per_sent"] for r in rows), 3),
        avg_quote_per_1k=round(statistics.mean(r["quote_per_1k"] for r in rows), 3),
        avg_dialogue_line_ratio=round(statistics.mean(r["dialogue_line_ratio"] for r in rows), 3),
        avg_short_para_ratio=round(statistics.mean(r["short_para_ratio"] for r in rows), 3),
        avg_long_para_ratio=round(statistics.mean(r["long_para_ratio"] for r in rows), 3),
        top_connectors=top_connectors,
    )


def build_output_path(input_path: Path, output: str | None, suffix: str) -> Path:
    if output:
        return Path(output)
    return input_path.with_name(input_path.stem + suffix + input_path.suffix)


def cmd_learn(args: argparse.Namespace) -> None:
    before_path = Path(args.before)
    after_path = Path(args.after)
    output_path = Path(args.output)

    replacements = learn_rules(read_text(before_path), read_text(after_path))
    save_rules(output_path, replacements)
    print(f"learned_rules: {len(replacements)}")
    print(f"written: {output_path}")


def cmd_mine_corpus(args: argparse.Namespace) -> None:
    profile = mine_corpus_profile(Path(args.corpus), args.glob)
    save_profile(Path(args.output), profile)
    print(f"corpus_files: {profile.files}")
    print(f"avg_comma_per_sent: {profile.avg_comma_per_sent}")
    print(f"avg_dialogue_line_ratio: {profile.avg_dialogue_line_ratio}")
    print(f"written: {args.output}")


def cmd_merge_rules(args: argparse.Namespace) -> None:
    rule_paths = [Path(p) for p in args.rules]
    if not rule_paths:
        raise SystemExit("no rule files provided")
    rule_sets = [load_rules([path]) for path in rule_paths]
    merged = merge_rulesets(rule_sets, min_freq=args.min_freq)
    save_rules(Path(args.output), merged)
    print(f"input_rule_files: {len(rule_paths)}")
    print(f"merged_rules: {len(merged)}")
    print(f"written: {args.output}")


def apply_to_file(
    input_path: Path,
    output_path: Path,
    rules: list[Replacement],
    use_heuristics: bool,
    profile: CorpusProfile | None,
) -> None:
    text = read_text(input_path)
    if rules:
        text = apply_exact_replacements(text, rules)
    if use_heuristics:
        text = apply_heuristics(text, profile)
    write_text(output_path, text)
    print(f"written: {output_path}")


def iter_input_files(input_path: Path, glob_pattern: str) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(path for path in input_path.rglob(glob_pattern) if path.is_file())


def cmd_apply(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    rule_paths = [Path(p) for p in args.rules]
    rules = load_rules(rule_paths) if rule_paths else []
    profile = load_profile(Path(args.profile)) if args.profile else None
    files = iter_input_files(input_path, args.glob)
    use_heuristics = args.with_heuristics or (not rules and not args.no_heuristics)

    if not files:
        raise SystemExit("no input files found")

    if input_path.is_file():
        output_path = build_output_path(input_path, args.output, args.suffix)
        apply_to_file(input_path, output_path, rules, use_heuristics, profile)
        return

    output_dir = Path(args.output_dir) if args.output_dir else input_path
    for src in files:
        rel = src.relative_to(input_path)
        dst = output_dir / rel.parent / f"{src.stem}{args.suffix}{src.suffix}"
        apply_to_file(src, dst, rules, use_heuristics, profile)


def apply_short_fiction_lexicon(
    text: str,
    lexicon: dict,
    enable_narrative_particles: bool,
    prefer_delete: bool,
) -> tuple[str, list[LexiconApplyStats]]:
    categories = [
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
    ]
    text, stats = apply_lexicon_categories(text, lexicon, categories, prefer_delete=prefer_delete)
    text, regex_stats = apply_lexicon_regex_rules(text, lexicon, categories + ["system_panel_decompression", "rule_notice_shells"])
    stats.extend(regex_stats)
    text, emotion_stats = apply_precision_emotion_templates(text)
    stats.extend(emotion_stats)
    text, panel_stats = apply_system_panel_decompression(text)
    stats.extend(panel_stats)
    if enable_narrative_particles:
        text, extra_stats = apply_narrative_particle_patterns(text, lexicon)
        stats.extend(extra_stats)
    return text, stats


def print_lexicon_stats(path: Path, stats: list[LexiconApplyStats]) -> None:
    total = sum(item.count for item in stats)
    print(f"written: {path}")
    print(f"lexicon_replacements: {total}")
    if not stats:
        return
    grouped: Counter[str] = Counter()
    for item in stats:
        grouped[item.category] += item.count
    print("lexicon_categories:")
    for category, count in grouped.most_common():
        print(f"  {category}: {count}")


def cmd_lexicon_apply(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    files = iter_input_files(input_path, args.glob)
    if not files:
        raise SystemExit("no input files found")

    lexicon = load_lexicon(Path(args.lexicon) if args.lexicon else None)

    def transform_and_write(src: Path, dst: Path) -> None:
        text = read_text(src)
        text, stats = apply_short_fiction_lexicon(
            text,
            lexicon=lexicon,
            enable_narrative_particles=args.with_narrative_particles,
            prefer_delete=not args.keep_connectors,
        )
        write_text(dst, text)
        print_lexicon_stats(dst, stats)

    if input_path.is_file():
        output_path = build_output_path(input_path, args.output, args.suffix)
        transform_and_write(input_path, output_path)
        return

    output_dir = Path(args.output_dir) if args.output_dir else input_path
    for src in files:
        rel = src.relative_to(input_path)
        dst = output_dir / rel.parent / f"{src.stem}{args.suffix}{src.suffix}"
        transform_and_write(src, dst)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Learn and apply short-fiction humanization rules.")
    sub = parser.add_subparsers(dest="command", required=True)

    learn = sub.add_parser("learn", help="learn exact replacements from before/after files")
    learn.add_argument("before", help="original file path")
    learn.add_argument("after", help="edited file path")
    learn.add_argument("-o", "--output", required=True, help="output json rule file")
    learn.set_defaults(func=cmd_learn)

    merge = sub.add_parser("merge-rules", help="merge multiple learned rule files into one project rule pack")
    merge.add_argument("rules", nargs="+", help="input rule json files")
    merge.add_argument("-o", "--output", required=True, help="output merged json rule file")
    merge.add_argument("--min-freq", type=int, default=1, help="keep only rules appearing in at least N input files")
    merge.set_defaults(func=cmd_merge_rules)

    mine = sub.add_parser("mine-corpus", help="mine a style profile from a corpus directory")
    mine.add_argument("corpus", help="corpus directory path")
    mine.add_argument("-o", "--output", required=True, help="output profile json file")
    mine.add_argument("--glob", default="*.txt", help="glob used inside the corpus directory")
    mine.set_defaults(func=cmd_mine_corpus)

    apply = sub.add_parser("apply", help="apply learned rules and short-fiction heuristics")
    apply.add_argument("input", help="input file or directory")
    apply.add_argument("--rules", nargs="*", default=[], help="json rule files learned from sample pairs")
    apply.add_argument("--profile", help="style profile json mined from a corpus directory")
    apply.add_argument("-o", "--output", help="output file path when input is a file")
    apply.add_argument("--output-dir", help="output directory when input is a directory")
    apply.add_argument("--suffix", default=DEFAULT_SUFFIX, help="output suffix")
    apply.add_argument("--glob", default="*.md", help="glob used when input is a directory")
    apply.add_argument("--no-heuristics", action="store_true", help="disable built-in heuristic rewrites")
    apply.add_argument("--with-heuristics", action="store_true", help="force heuristic rewrites even when rules are provided")
    apply.set_defaults(func=cmd_apply)

    lexicon_apply = sub.add_parser("lexicon-apply", help="apply the short-fiction anti-AI lexicon")
    lexicon_apply.add_argument("input", help="input file or directory")
    lexicon_apply.add_argument("--lexicon", help="lexicon json path")
    lexicon_apply.add_argument("--with-narrative-particles", action="store_true", help="enable small narrative particles for short fiction")
    lexicon_apply.add_argument("--keep-connectors", action="store_true", help="prefer lighter replacements over deleting empty connectors")
    lexicon_apply.add_argument("-o", "--output", help="output file path when input is a file")
    lexicon_apply.add_argument("--output-dir", help="output directory when input is a directory")
    lexicon_apply.add_argument("--suffix", default="-短篇去味版", help="output suffix")
    lexicon_apply.add_argument("--glob", default="*.md", help="glob used when input is a directory")
    lexicon_apply.set_defaults(func=cmd_lexicon_apply)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
