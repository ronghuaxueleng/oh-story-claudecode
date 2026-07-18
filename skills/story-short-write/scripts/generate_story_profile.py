#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def collect_original_source_text(roots: list[Path]) -> str:
    chunks: list[str] = []
    for root in roots:
        source_dir = root / "原文"
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
                chunks.append(read_text(path))
    return "\n".join(chunks)


DYNAMIC_OBJECT_CATEGORIES = ("核心物件", "证据载体")


def collect_dynamic_object_terms(root: Path) -> set[str]:
    path = root / "写作资产" / "本书动态信号字典.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(read_text(path))
    except (json.JSONDecodeError, OSError):
        return set()
    categories = data.get("categories")
    if not isinstance(categories, dict):
        return set()

    source_text = collect_original_source_text([root])
    terms: set[str] = set()
    for category in DYNAMIC_OBJECT_CATEGORIES:
        entries = categories.get(category, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            term = str(entry.get("term", "")).strip()
            if 2 <= len(term) <= 32 and term in source_text:
                terms.add(term)
    return terms


def collect_bullets(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def collect_nested_bullets(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        if not line.startswith(("  - ", "\t- ")):
            continue
        stripped = line.strip()
        items.append(stripped[2:].strip())
    return items


def collect_section_bullets(text: str, heading_keywords: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    current_hit = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            current_hit = any(keyword in stripped for keyword in heading_keywords)
            continue
        if current_hit and stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def collect_section_nested_bullets(text: str, heading_keywords: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    current_hit = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            current_hit = any(keyword in stripped for keyword in heading_keywords)
            continue
        if current_hit and line.startswith(("  - ", "\t- ")):
            items.append(stripped[2:].strip())
    return items


def collect_banned_payload_lines(text: str) -> list[str]:
    items: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            capture = False
            continue
        if stripped.startswith("- ") and any(
            key in stripped for key in ("禁句型", "禁写法", "空总结句", "成品体面对话", "轻飘过渡句")
        ):
            capture = True
            continue
        if capture:
            if not stripped:
                capture = False
                continue
            if stripped.startswith("- 为什么假") or stripped.startswith("例如："):
                capture = False
                continue
            if line.startswith("  ") or line.startswith("\t"):
                items.append(stripped)
                continue
            capture = False
    return items


def parse_markdown_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.startswith("## "):
            current = stripped[3:].strip()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def collect_heading_block_lines(text: str, heading_keywords: tuple[str, ...], max_items: int = 6) -> list[str]:
    items: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            capture = any(keyword in stripped for keyword in heading_keywords)
            continue
        if not capture or not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
        elif re.match(r"^\d+\.\s+", stripped):
            items.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
        if len(items) >= max_items:
            break
    return items


def collect_labeled_values(text: str, label_keywords: tuple[str, ...], max_items: int = 6) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("- ", "* ")):
            continue
        body = stripped[2:].strip()
        key, sep, value = body.partition("：")
        if not sep:
            key, sep, value = body.partition(":")
        if not sep:
            continue
        if any(keyword in key for keyword in label_keywords):
            cleaned = value.strip()
            if cleaned:
                items.append(cleaned)
        if len(items) >= max_items:
            break
    return items


def collect_text_lines_with_keywords(text: str, keywords: tuple[str, ...], max_items: int = 6) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not any(keyword in stripped for keyword in keywords):
            continue
        stripped = re.sub(r"^[-*]\s*", "", stripped)
        stripped = re.sub(r"^\d+\.\s*", "", stripped)
        items.append(stripped)
        if len(items) >= max_items:
            break
    return items


def collect_following_list_after_trigger_keywords(text: str, trigger_keywords: tuple[str, ...], max_items: int = 6) -> list[str]:
    items: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if not capture and any(keyword in stripped for keyword in trigger_keywords):
            capture = True
            continue
        if not capture:
            continue
        if stripped.startswith("#"):
            if items:
                break
            capture = False
            continue
        if not stripped:
            if items:
                break
            continue
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
        elif re.match(r"^\d+\.\s+", stripped):
            items.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
        if len(items) >= max_items:
            break
    return items


def collect_profile_source_pairs(lines: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    current_parent: str | None = None
    for raw in lines:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        body = stripped[2:].strip()
        if raw.startswith("  - ") and current_parent:
            key, _, value = body.partition("：")
            if value:
                result[f"{current_parent}::{key.strip()}"].append(value.strip())
            continue
        if re.match(r"^桥段[：:]", body):
            current_parent = body
            result[current_parent]
            continue
        key, _, value = body.partition("：")
        if value:
            result[key.strip()].append(value.strip())
    return result


def collect_table_cells(text: str) -> list[str]:
    cells: list[str] = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        stripped = line.strip()
        if set(stripped.replace("|", "").replace("-", "").replace(" ", "")) == set():
            continue
        parts = [p.strip() for p in stripped.split("|") if p.strip()]
        cells.extend(parts)
    return cells


def extract_quoted_terms(text: str) -> list[str]:
    patterns = [
        r"`([^`]{1,40})`",
        r"“([^”]{1,40})”",
        r"「([^」]{1,40})」",
        r'"([^"\n]{1,40})"',
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text))
    return found


ASSET_BLOCK_MARKERS = (
    "为什么",
    "原文",
    "结论",
    "迁移",
    "顺序",
    "不能乱",
    "最容易写假",
    "新稿",
    "作用",
    "提醒",
    "检查",
    "证据",
    "证据1",
    "证据2",
    "证据3",
    "证据4",
    "结论：",
    "为什么假",
    "为什么能过",
    "原文怎么起手",
    "原文承重件",
    "推荐迁移顺序",
    "后续调用方式",
    "最该保留",
    "这篇最强",
    "这个作者",
    "这类文",
    "有没有",
    "是否",
    "只写",
    "先让",
    "再让",
    "名单特别适合",
    "女主不是",
    "男主不是",
    "继续",
    "建立",
    "承受",
    "翻盘没有",
)

ASSET_LABEL_PREFIXES = (
    "禁句型",
    "禁写法",
    "空总结句",
    "成品体面对话",
    "轻飘过渡句",
    "反面",
    "典型口气",
    "常见模式",
)


def strip_asset_wrappers(text: str) -> str:
    stripped = text.strip().strip("：:，。；;、 ")
    stripped = re.sub(
        r"^(证据\d*|反面\d*|典型口气|常见模式|禁句型|禁写法|空总结句|成品体面对话|轻飘过渡句"
        r"|推荐迁移顺序|不能丢的顺序|为什么这个顺序不能乱|原文为什么能过|原文为什么过检"
        r"|最容易写假的点|新稿最容易写假的点|人物不同脸证据|谁先解释谁先压场|不同角色的动作权限差"
        r"|重大证据前隔开的现实后果|后果回灌方式|尾声入口归属|尾声入口给了谁"
        r"|不给另一条线的原因|尾声入口给了谁\s*/\s*为什么不给另一条线"
        r")\s*[：:]\s*",
        "",
        stripped,
    )
    stripped = stripped.strip("：:，。；;、 ")
    return stripped


def looks_like_explanation(text: str) -> bool:
    if not text:
        return True
    if any(marker in text for marker in ASSET_BLOCK_MARKERS):
        return True
    if text.endswith(("。", "？", "！")) and len(text) > 8:
        return True
    if "，" in text and len(text) > 10:
        return True
    if any(text.startswith(prefix) for prefix in ASSET_LABEL_PREFIXES):
        return True
    if re.search(r"(因为|不是.+而是|不在.+而在|先.+再|最后|尤其|必须|不要|不能|会把|负责|更像|来自|适合写|就会|容易发假|先看|再看|写完|检查)", text):
        return True
    if re.search(r"(女主|男主|闺蜜|后妈|招聘会|生日宴).{4,}(是|有|会|要|在|继续|建立|承受|不是)", text):
        return True
    return False


def split_inline_assets(text: str) -> list[str]:
    text = strip_asset_wrappers(text)
    if not text:
        return []
    if "、" in text and len(text) <= 36:
        return [part.strip() for part in text.split("、") if part.strip()]
    return [text]


def keep_short_asset(text: str) -> bool:
    stripped = strip_asset_wrappers(text)
    if not stripped:
        return False
    if len(stripped) > 16:
        return False
    if looks_like_explanation(stripped):
        return False
    if re.search(r"[，。？！；]", stripped):
        return False
    if stripped.count("的") >= 3:
        return False
    if re.search(r"(我|你|他|她|它|他们|她们).{3,}", stripped):
        return False
    if re.search(r"[=/]", stripped):
        return False
    if re.search(r"(有|会|让|把|去|来|看|做|写|说|读|查|撤|翻|改|等|给|像)$", stripped):
        return False
    return True


def clean_asset_terms(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        for part in split_inline_assets(item):
            stripped = strip_asset_wrappers(part)
            if not keep_short_asset(stripped):
                continue
            cleaned.append(stripped)
    return normalize_items(cleaned)


def clean_banned_phrase_terms(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        quoted = extract_quoted_terms(item)
        if quoted:
            for part in quoted:
                part = strip_asset_wrappers(part)
                if 4 <= len(part) <= 30 and not looks_like_explanation(part):
                    cleaned.append(part)
            continue
        stripped = strip_asset_wrappers(item)
        if 4 <= len(stripped) <= 20 and not looks_like_explanation(stripped):
            cleaned.append(stripped)
    return normalize_items(cleaned)


def split_scene_fragments(text: str) -> list[str]:
    stripped = strip_asset_wrappers(text)
    if not stripped:
        return []
    parts = re.split(r"\s*/\s*|、|，|和", stripped)
    return [part.strip() for part in parts if part.strip()]


def looks_like_asset_fragment(text: str) -> bool:
    if not text:
        return False
    if looks_like_explanation(text):
        return False
    if len(text) > 10:
        return False
    if re.search(r"[，。？！；:=]", text):
        return False
    if re.search(r"(先|再|后|让|把|去|来|看|做|写|说|读|查|翻|改|等|给|走|回|建立|承受|公开反杀|不想回头|从头就)", text):
        return False
    if text.count("的") >= 2:
        return False
    return True


def clean_scene_asset_terms(items: list[str]) -> list[str]:
    """Preserve event-level scene assets instead of reducing them to short tags."""
    cleaned: list[str] = []
    for item in items:
        stripped = strip_asset_wrappers(item).strip("。！？；; ")
        fragments = re.split(r"\s*/\s*|、|；|;", stripped)
        if not fragments:
            fragments = [stripped]
        for fragment in fragments:
            frag = strip_asset_wrappers(fragment).strip("。！？；; ")
            if not frag:
                continue
            if len(frag) > 80 or re.search(r"[`#|]", frag):
                continue
            cleaned.append(frag)
    return normalize_items(cleaned)


def clean_opening_group_terms(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        for fragment in split_scene_fragments(item):
            frag = strip_asset_wrappers(fragment)
            if not frag:
                continue
            if len(frag) <= 8 and looks_like_asset_fragment(frag):
                cleaned.append(frag)
    return normalize_items(cleaned)


def collect_profile_source_fragments(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        fragments = re.split(r"[；;]| -> |\+|、|，", value)
        for fragment in fragments:
            frag = strip_asset_wrappers(fragment)
            if not frag:
                continue
            if looks_like_asset_fragment(frag) or keep_short_asset(frag):
                cleaned.append(frag)
    return normalize_items(cleaned)


def collect_profile_source_reason_lines(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        if not value:
            continue
        parts = re.split(r"[；;]|\s*->\s*|\s*=>\s*", value)
        for part in parts:
            frag = clean_bridge_line(part)
            if not frag:
                continue
            cleaned.append(frag)
    return normalize_items(cleaned)


def filter_character_guardrail_lines(values: list[str]) -> list[str]:
    role_pattern = re.compile(
        r"(男主|女主|主角|反派|配角|旧爱|第三人|丈夫|妻子|姐姐|妹妹|母亲|父亲|医生|护士|长辈|客户|上司|同事|周|唐|宋)"
    )
    filtered = [value for value in values if role_pattern.search(value)]
    return normalize_items(filtered)


def collect_profile_source_bridge_fragments(values: list[str], max_len: int = 40) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        fragments = re.split(r"[；;]| -> |->|、|，", value)
        for fragment in fragments:
            frag = strip_asset_wrappers(fragment)
            if not frag:
                continue
            if len(frag) > max_len:
                continue
            cleaned.append(frag)
    return normalize_items(cleaned)


def clean_bridge_line(text: str) -> str:
    return re.sub(r"\s+", " ", strip_asset_wrappers(text)).strip()


def collect_bridge_step_terms(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = clean_bridge_line(value)
        if not text:
            continue
        parts = re.split(r"\s*(?:->|→|=>|➜)\s*", text)
        for part in parts:
            part = clean_bridge_line(part)
            if not part:
                continue
            if len(part) > 40:
                continue
            cleaned.append(part)
    return normalize_items(cleaned)


def collect_bridge_reason_terms(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = clean_bridge_line(value)
        if not text:
            continue
        cleaned.append(text)
    return normalize_items(cleaned)


def collect_profile_source_style_fragments(
    values: list[str],
    preserve_commas: bool = False,
) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        pattern = r"[；;]| -> |\+|、" if preserve_commas else r"[；;]| -> |\+|、|，"
        fragments = re.split(pattern, value)
        for fragment in fragments:
            frag = strip_asset_wrappers(fragment)
            if keep_explicit_style_asset(frag):
                cleaned.append(frag)
    return normalize_items(cleaned)


def build_profile_story_guardrails(author_pairs: dict[str, list[str]], consequence_pairs: dict[str, list[str]]) -> dict[str, object]:
    character_face_split = {
        "different_face_evidence": collect_profile_source_reason_lines(
            author_pairs.get("人物不同脸证据", [])
        ),
        "reaction_order_split": collect_profile_source_reason_lines(
            author_pairs.get("谁先解释谁先压场", [])
        ),
        "action_authority_split": collect_profile_source_reason_lines(
            author_pairs.get("不同角色的动作权限差", [])
        ),
    }
    character_face_split = {
        key: value for key, value in character_face_split.items() if value
    }

    consequence_structure = {
        "pre_evidence_reality_consequences": collect_profile_source_reason_lines(
            consequence_pairs.get("重大证据前隔开的现实后果", [])
        ),
        "consequence_rebound_modes": collect_profile_source_reason_lines(
            consequence_pairs.get("后果回灌方式", [])
        ),
        "tail_entry_owner": collect_profile_source_reason_lines(
            consequence_pairs.get("尾声入口归属", [])
        ),
        "tail_entry_exclusion_reason": collect_profile_source_reason_lines(
            consequence_pairs.get("不给另一条线的原因", [])
        ),
    }
    consequence_structure = {
        key: value for key, value in consequence_structure.items() if value
    }

    out: dict[str, object] = {}
    if character_face_split:
        out["character_face_split"] = character_face_split
    if consequence_structure:
        out["consequence_structure"] = consequence_structure
    return out


def build_story_guardrails_from_aux_text(text: str, source_kind: str) -> dict[str, object]:
    shared_face_bundle = collect_labeled_values(
        text,
        ("人物不同脸证据 / 谁先解释谁先压场 / 动作权限差",),
    )
    face_evidence = collect_labeled_values(text, ("人物不同脸证据", "不同脸证据")) or shared_face_bundle or collect_text_lines_with_keywords(
        text, ("说话怎么伤人", "身体怎么反应", "遇事先偏向谁", "失控时会干什么", "遮住名字"), max_items=6
    ) or collect_heading_block_lines(
        text, ("人物不同脸", "去同脸", "一张脸"), max_items=8
    )
    reaction_order = collect_labeled_values(text, ("谁先解释谁先压场", "第一反应偏向", "第一反应")) or shared_face_bundle or collect_text_lines_with_keywords(
        text, ("先解释", "先压场", "第一反应"), max_items=6
    )
    action_authority = collect_labeled_values(text, ("动作权限差", "权限差")) or shared_face_bundle or collect_text_lines_with_keywords(
        text, ("权限差", "先把人护住", "先过去处理", "找靠山", "站边上"), max_items=6
    )

    pre_evidence = collect_labeled_values(text, ("重大证据前隔开的现实后果",)) or collect_following_list_after_trigger_keywords(
        text, ("它中间还隔了很多现实后果", "原文真实顺序", "先找原文中间隔着的现实后果"), max_items=8
    ) or collect_heading_block_lines(
        text, ("现实后果", "证据迟到", "证据触发顺序"), max_items=8
    )
    consequence_rebound = collect_labeled_values(text, ("后果回灌方式", "证据迟到方式", "公开风光压人方式")) or collect_text_lines_with_keywords(
        text, ("后果回灌", "迟到方式", "继续公开", "继续风光", "继续挑衅"), max_items=6
    ) or collect_following_list_after_trigger_keywords(
        text, ("后面仿写时的固定施工顺序", "固定施工顺序", "章节顺序模板"), max_items=6
    )
    tail_owner = collect_labeled_values(text, ("尾声入口归属", "尾声入口给了谁", "真正尾声入口")) or collect_text_lines_with_keywords(
        text, ("尾声入口直接", "真正尾声入口", "尾声只收", "真正核心"), max_items=6
    ) or collect_following_list_after_trigger_keywords(
        text, ("尾声只收", "真正尾声入口直接", "直接转真正核心场域"), max_items=6
    ) or collect_heading_block_lines(
        text, ("尾声入口",), max_items=6
    )
    tail_exclusion = collect_labeled_values(text, ("不给另一条线的原因", "尾声入口为什么不给次线", "尾声入口给了谁 / 为什么不给另一条线")) or collect_text_lines_with_keywords(
        text, ("余波区", "不给另一条线", "不准重新吃掉尾声入口", "抢尾声入口"), max_items=6
    )

    character_face_split = {
        "different_face_evidence": filter_character_guardrail_lines(
            collect_profile_source_reason_lines(face_evidence)
        ),
        "reaction_order_split": filter_character_guardrail_lines(
            collect_profile_source_reason_lines(reaction_order)
        ),
        "action_authority_split": filter_character_guardrail_lines(
            collect_profile_source_reason_lines(action_authority)
        ),
    }
    character_face_split = {key: value for key, value in character_face_split.items() if value}

    consequence_structure = {
        "pre_evidence_reality_consequences": collect_profile_source_reason_lines(pre_evidence),
        "consequence_rebound_modes": collect_profile_source_reason_lines(consequence_rebound),
        "tail_entry_owner": collect_profile_source_reason_lines(tail_owner),
        "tail_entry_exclusion_reason": collect_profile_source_reason_lines(tail_exclusion),
    }
    consequence_structure = {key: value for key, value in consequence_structure.items() if value}

    out: dict[str, object] = {}
    if character_face_split:
        out["character_face_split"] = character_face_split
    if consequence_structure:
        out["consequence_structure"] = consequence_structure
    if out:
        out["source_kind"] = source_kind
    return out


def merge_story_guardrail_dicts(*guardrails_list: dict) -> dict[str, object]:
    character_face_split: dict[str, list[str]] = defaultdict(list)
    consequence_structure: dict[str, list[str]] = defaultdict(list)
    for guardrails in guardrails_list:
        if not isinstance(guardrails, dict):
            continue
        face = guardrails.get("character_face_split", {})
        if isinstance(face, dict):
            for key, items in face.items():
                if isinstance(items, list):
                    character_face_split[key].extend(item for item in items if isinstance(item, str))
        consequence = guardrails.get("consequence_structure", {})
        if isinstance(consequence, dict):
            for key, items in consequence.items():
                if isinstance(items, list):
                    consequence_structure[key].extend(item for item in items if isinstance(item, str))
    out: dict[str, object] = {}
    face_out = {
        key: normalize_items(value)[:GUARDRAIL_ITEM_LIMITS.get(key, 4)]
        for key, value in character_face_split.items()
        if value
    }
    consequence_out = {
        key: normalize_items(value)[:GUARDRAIL_ITEM_LIMITS.get(key, 4)]
        for key, value in consequence_structure.items()
        if value
    }
    if face_out:
        out["character_face_split"] = face_out
    if consequence_out:
        out["consequence_structure"] = consequence_out
    return out


def collect_explicit_story_guardrails(text: str) -> dict[str, object]:
    explicit: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- profile_story_guardrail::"):
            continue
        payload = line[2:].strip()
        if "：" in payload:
            key_part, value_part = payload.split("：", 1)
        elif ":" in payload:
            key_part, value_part = payload.split(":", 1)
        else:
            continue
        if not key_part.startswith("profile_story_guardrail::"):
            continue
        parts = key_part.split("::")
        if len(parts) != 3:
            continue
        _, group_name, key_name = parts
        value = value_part.strip()
        if not value:
            continue
        explicit[group_name][key_name].append(value)

    out: dict[str, object] = {}
    for group_name, group in explicit.items():
        normalized_group = {
            key: normalize_items(items)[:GUARDRAIL_ITEM_LIMITS.get(key, 4)]
            for key, items in group.items()
            if items
        }
        if normalized_group:
            out[group_name] = normalized_group
    return out


def parse_sample_grading_text(text: str) -> dict[str, object]:
    sections = parse_markdown_sections(text)
    result: dict[str, object] = {}

    level_lines = sections.get("1. 样本等级", [])
    level_pairs = collect_profile_source_pairs(level_lines)
    level = normalize_items(
        collect_profile_source_reason_lines(level_pairs.get("样本等级", []))
    )
    summary = normalize_items(
        collect_profile_source_reason_lines(level_pairs.get("一句话结论", []))
    )
    dna_usable = normalize_items(
        collect_profile_source_reason_lines(level_pairs.get("是否可用于DNA提取", []))
    )
    source_score_judgement = normalize_items(
        collect_profile_source_reason_lines(level_pairs.get("原文检测结论", []))
    )
    source_score_overall = normalize_items(
        collect_profile_source_reason_lines(level_pairs.get("原文整体分数", []))
    )
    source_score_high_blocks = normalize_items(
        collect_profile_source_reason_lines(level_pairs.get("原文高风险块", []))
    )
    source_score_policy = normalize_items(
        collect_profile_source_reason_lines(level_pairs.get("分数使用口径", []))
    )
    layer_grades = {
        key: normalize_items(
            collect_profile_source_reason_lines(level_pairs.get(key, []))
        )
        for key in SAMPLE_LAYER_GRADE_KEYS
    }
    if level or summary or dna_usable or source_score_judgement or source_score_overall or source_score_high_blocks or source_score_policy or any(layer_grades.values()):
        result["sample_grading"] = {}
        if level:
            result["sample_grading"]["level"] = level[0]
        if summary:
            result["sample_grading"]["summary"] = summary[0]
        if dna_usable:
            result["sample_grading"]["dna_usable"] = dna_usable[0]
        if source_score_judgement:
            result["sample_grading"]["source_score_judgement"] = source_score_judgement[0]
        if source_score_overall:
            result["sample_grading"]["source_score_overall"] = source_score_overall[0]
        if source_score_high_blocks:
            result["sample_grading"]["source_score_high_blocks"] = source_score_high_blocks
        if source_score_policy:
            result["sample_grading"]["source_score_policy"] = source_score_policy[0]
        for key, values in layer_grades.items():
            if values:
                result["sample_grading"][key] = values[0]

    learn_lines = sections.get("2. 可学层", [])
    learn_pairs = collect_profile_source_pairs(learn_lines)
    learnable_layers = collect_profile_source_fragments(
        learn_pairs.get("可学层1", [])
        + learn_pairs.get("可学层2", [])
        + learn_pairs.get("可学层3", [])
        + learn_pairs.get("哪些可以直接进 profile 正向规则", [])
    )
    if learnable_layers:
        result["learnable_layers"] = learnable_layers
    for label, key in (
        ("正向DNA层", "positive_dna_layers"),
        ("仅骨架层", "skeleton_only_layers"),
        ("反面规则层", "negative_rule_layers"),
    ):
        values = collect_profile_source_fragments(learn_pairs.get(label, []))
        if values:
            result[key] = values

    avoid_lines = sections.get("3. 禁学层", [])
    avoid_pairs = collect_profile_source_pairs(avoid_lines)
    forbidden_layers = collect_profile_source_reason_lines(
        avoid_pairs.get("禁学层1", [])
        + avoid_pairs.get("禁学层2", [])
        + avoid_pairs.get("禁学层3", [])
        + avoid_pairs.get("哪些绝不能进 profile 正向规则", [])
    )
    if forbidden_layers:
        result["forbidden_layers"] = forbidden_layers

    evidence_lines = sections.get("4. 判定证据", [])
    evidence_pairs = collect_profile_source_pairs(evidence_lines)
    evidence: dict[str, object] = {}
    for key in ("内部最高块风险分", "内部整体风险分", "开头块情况", "桥段块情况", "高效对白块情况", "是否存在大面积说明句 / 总结句 / 整齐揭露"):
        values = normalize_items(collect_profile_source_reason_lines(evidence_pairs.get(key, [])))
        if values:
            evidence[key] = values[0]
    for key in ("剧情骨架是否能学，为什么", "桥段承重件是否能学，为什么", "动作 / 物件 / 站位是否能学，为什么", "句法表达层是否能学，为什么"):
        values = normalize_items(collect_profile_source_reason_lines(evidence_pairs.get(key, [])))
        if values:
            evidence[key] = values[0]
    original_evidence = normalize_items(
        collect_profile_source_reason_lines(
            evidence_pairs.get("证据1", []) + evidence_pairs.get("证据2", []) + evidence_pairs.get("证据3", [])
        )
    )
    if original_evidence:
        evidence["原文现象证据"] = original_evidence
    if evidence:
        result["grading_evidence"] = evidence

    usage_lines = sections.get("5. 后续调用方式", [])
    usage_pairs = collect_profile_source_pairs(usage_lines)
    usage: dict[str, object] = {}
    for key in ("写新稿时怎么用这本", "融合写作时怎么用这本", "去 AI 味时怎么用这本", "哪些内容只可参考、不可继承"):
        values = normalize_items(collect_profile_source_reason_lines(usage_pairs.get(key, [])))
        if values:
            usage[key] = values[0]
    if usage:
        result["usage_guidance"] = usage

    warning_lines = sections.get("6. 误用警报", [])
    warning_pairs = collect_profile_source_pairs(warning_lines)
    misuse_warnings = normalize_items(
        collect_profile_source_reason_lines(
            warning_pairs.get("最容易误把什么当成正向 DNA", [])
            + warning_pairs.get("最容易把哪层学错", [])
            + warning_pairs.get("如果误用，会把新稿写成什么样", [])
        )
    )
    if misuse_warnings:
        result["misuse_warnings"] = misuse_warnings

    verdict_lines = sections.get("7. 最终准出结论", [])
    verdict_pairs = collect_profile_source_pairs(verdict_lines)
    final_verdict: dict[str, object] = {}
    for key, field in (
        ("是否可进入 DNA 提取", "allow_dna"),
        ("是否可进入桥段融合", "allow_bridge_merge"),
        ("是否只可进入负面规则库", "negative_only"),
    ):
        values = normalize_items(collect_profile_source_reason_lines(verdict_pairs.get(key, [])))
        if values:
            final_verdict[field] = values[0]
    tags = collect_profile_source_fragments(verdict_pairs.get("推荐标签", []))
    if tags:
        final_verdict["tags"] = tags
    if final_verdict:
        result["final_verdict"] = final_verdict
    return result


def build_profile_source_bridge_rules(text: str) -> list[dict]:
    sections = parse_markdown_sections(text)
    bridge_lines = sections.get("6. 桥段承重件", [])
    if not bridge_lines:
        return []
    pairs = collect_profile_source_pairs(bridge_lines)
    rules: list[dict] = []
    bridge_index = 0
    for key in list(pairs.keys()):
        if not key.startswith("桥段") or "::" in key:
            continue
        bridge_index += 1
        title = key
        title_body = title.removeprefix("桥段：").removeprefix("桥段").strip()
        bid_match = re.search(r"\b(BID-\d{2,3})\b", title_body, flags=re.I)
        bid = bid_match.group(1).upper() if bid_match else ""
        title_body = re.sub(r"^\[?(BID-\d{2,3})\]?\s*", "", title_body, flags=re.I).strip()

        def collect_aliases(*aliases: str) -> list[str]:
            values: list[str] = []
            for alias in aliases:
                values.extend(pairs.get(f"{title}::{alias}", []))
            return values

        opening = collect_profile_source_bridge_fragments(
            collect_aliases("原文怎么起手", "原文起手件", "原文起手")
        )
        must_keep = collect_profile_source_bridge_fragments(
            collect_aliases(
                "承重件",
                "原文承重件",
                "原文真正承重件",
                "承重件不可丢",
                "必留承重件",
                "仿写必留",
                "必须保留件",
            )
        )
        order = collect_bridge_step_terms(
            collect_aliases("不能丢的顺序", "推荐迁移顺序")
        )
        must_avoid = collect_bridge_reason_terms(
            collect_aliases(
                "最容易写假的点",
                "新稿最容易写假的点",
                "仿稿最易假点",
                "绝对不能写的 AI 句",
                "绝对不能出现的 AI 句子",
                "禁写",
            )
        )
        order_why = collect_bridge_reason_terms(
            collect_aliases("为什么这个顺序不能乱")
        )
        why_passes = collect_bridge_reason_terms(
            collect_aliases("原文为什么能过", "原文为什么过检", "为什么能过")
        )
        rule = {
            "bridge": f"桥段{bridge_index}：{title_body}" if title_body else f"桥段{bridge_index}",
            "opening_pattern": normalize_items(opening),
            "must_keep": normalize_items(must_keep),
            "must_avoid": normalize_items(must_avoid),
            "fake_signals": normalize_items(must_avoid),
            "recommended_sequence": normalize_items(order),
            "why_order_matters": normalize_items(order_why),
            "why_original_passes": normalize_items(why_passes),
        }
        if bid:
            rule["id"] = bid
            rule["bridge"] = f"{bid} {rule['bridge']}"
        rules.append(rule)
    return rules


def parse_profile_source(text: str) -> dict[str, list[str] | list[dict]]:
    sections = parse_markdown_sections(text)
    result: dict[str, list[str] | list[dict]] = {}

    grading_lines = sections.get("0. 样本分级与可学层", [])
    grading_pairs = collect_profile_source_pairs(grading_lines)
    grading_level = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("样本等级", []))
    )
    grading_dna = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("是否可用于DNA提取", []))
    )
    grading_source_score_judgement = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("原文检测结论", []))
    )
    grading_source_score_overall = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("原文整体分数", []))
    )
    grading_source_score_high_blocks = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("原文高风险块", []))
    )
    grading_source_score_policy = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("分数使用口径", []))
    )
    grading_learn = collect_profile_source_fragments(grading_pairs.get("可学层", []))
    grading_forbid = collect_profile_source_reason_lines(grading_pairs.get("禁学层", []))
    grading_evidence = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("判定证据", []))
    )
    grading_usage = normalize_items(
        collect_profile_source_reason_lines(grading_pairs.get("后续调用方式", []))
    )
    grading_layer_grades = {
        key: normalize_items(
            collect_profile_source_reason_lines(grading_pairs.get(key, []))
        )
        for key in SAMPLE_LAYER_GRADE_KEYS
    }
    grading_usage_layers = {
        "positive_dna_layers": collect_profile_source_fragments(grading_pairs.get("正向DNA层", [])),
        "skeleton_only_layers": collect_profile_source_fragments(grading_pairs.get("仅骨架层", [])),
        "negative_rule_layers": collect_profile_source_fragments(grading_pairs.get("反面规则层", [])),
    }
    if grading_level or grading_dna or grading_source_score_judgement or grading_source_score_overall or grading_source_score_high_blocks or grading_source_score_policy or grading_learn or grading_forbid or grading_evidence or grading_usage or any(grading_layer_grades.values()) or any(grading_usage_layers.values()):
        result["sample_grading"] = {}
        if grading_level:
            result["sample_grading"]["level"] = grading_level[0]
        if grading_dna:
            result["sample_grading"]["dna_usable"] = grading_dna[0]
        if grading_source_score_judgement:
            result["sample_grading"]["source_score_judgement"] = grading_source_score_judgement[0]
        if grading_source_score_overall:
            result["sample_grading"]["source_score_overall"] = grading_source_score_overall[0]
        if grading_source_score_high_blocks:
            result["sample_grading"]["source_score_high_blocks"] = grading_source_score_high_blocks
        if grading_source_score_policy:
            result["sample_grading"]["source_score_policy"] = grading_source_score_policy[0]
        if grading_learn:
            result["sample_grading"]["learnable_layers"] = grading_learn
        if grading_forbid:
            result["sample_grading"]["forbidden_layers"] = grading_forbid
        if grading_evidence:
            result["sample_grading"]["evidence"] = grading_evidence
        if grading_usage:
            result["sample_grading"]["usage_guidance"] = grading_usage
        for key, values in grading_layer_grades.items():
            if values:
                result["sample_grading"][key] = values[0]
        for key, values in grading_usage_layers.items():
            if values:
                result["sample_grading"][key] = values

    risk_lines = sections.get("1.1 高敏层级判断", [])
    risk_pairs = collect_profile_source_pairs(risk_lines)
    risk_layer_type = normalize_items(
        collect_profile_source_fragments(risk_pairs.get("更接近哪一型", []))
    )
    if risk_layer_type:
        result["risk_layer_type"] = risk_layer_type[0]
    result["high_risk_layers"] = {
        "overall": collect_profile_source_fragments(risk_pairs.get("高敏层级判断", [])),
        "sentence": collect_profile_source_reason_lines(risk_pairs.get("句子层高敏点", [])),
        "scene": collect_profile_source_reason_lines(risk_pairs.get("场面层高敏点", [])),
        "bridge_sequence": collect_profile_source_reason_lines(risk_pairs.get("桥段排列层高敏点", [])),
        "input_noise": collect_profile_source_reason_lines(risk_pairs.get("检测输入层高敏点", [])),
    }
    result["high_risk_layers"] = {
        key: value for key, value in result["high_risk_layers"].items() if value
    }

    noise_lines = sections.get("1.2 原文检测输入污染检查", [])
    noise_pairs = collect_profile_source_pairs(noise_lines)
    source_noise_level = normalize_items(
        collect_profile_source_fragments(noise_pairs.get("source_noise_risk", []))
    )
    source_noise_signals = collect_profile_source_reason_lines(
        noise_pairs.get("OCR / 水印 / 杂符号情况", []) +
        noise_pairs.get("这本书的低分是否可能受污染影响", []) +
        noise_pairs.get("采样提醒", [])
    )
    if source_noise_level or source_noise_signals:
        result["source_noise_risk"] = {}
        if source_noise_level:
            result["source_noise_risk"]["level"] = source_noise_level[0]
        if source_noise_signals:
            result["source_noise_risk"]["signals"] = source_noise_signals

    safety_lines = sections.get("1.3 桥安全误判提醒", [])
    safety_pairs = collect_profile_source_pairs(safety_lines)
    bridge_safety_summary = normalize_items(
        collect_profile_source_reason_lines(safety_pairs.get("bridge_safety_warning", []))
    )
    bridge_safety_risky = collect_profile_source_fragments(
        safety_pairs.get("看起来安全但其实高敏的桥", [])
    )
    bridge_safety_why = collect_profile_source_reason_lines(
        safety_pairs.get("原文为什么不像加工稿", [])
    )
    bridge_safety_route = normalize_items(
        collect_profile_source_reason_lines(safety_pairs.get("这本更适合仿讲法还是换骨架", []))
    )
    if bridge_safety_summary or bridge_safety_risky or bridge_safety_why or bridge_safety_route:
        result["bridge_safety_warning"] = {}
        if bridge_safety_summary:
            result["bridge_safety_warning"]["summary"] = bridge_safety_summary[0]
        if bridge_safety_risky:
            result["bridge_safety_warning"]["risky_bridges"] = bridge_safety_risky
        if bridge_safety_why:
            result["bridge_safety_warning"]["why_original_not_processed"] = bridge_safety_why
        if bridge_safety_route:
            result["bridge_safety_warning"]["rewrite_route"] = bridge_safety_route[0]

    opening_lines = sections.get("4. 开头高信息量信号", [])
    opening_pairs = collect_profile_source_pairs(opening_lines)
    result["opening_signal_groups"] = {
        "registry_or_commitment": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.registry_or_commitment", [])),
        "pregnancy_or_child": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.pregnancy_or_child", [])),
        "medical_or_rescue": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.medical_or_rescue", [])),
        "family_pressure": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.family_pressure", [])),
        "social_exposure": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.social_exposure", [])),
        "location_evidence": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.location_evidence", [])),
        "rival_or_third_party": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.rival_or_third_party", [])),
        "contact_control": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.contact_control", [])),
        "paperwork_or_object": collect_profile_source_fragments(opening_pairs.get("opening_signal_groups.paperwork_or_object", [])),
    }
    result["opening_signal_groups"] = {
        key: value for key, value in result["opening_signal_groups"].items() if value
    }
    result["opening_terms"] = collect_profile_source_fragments(
        opening_pairs.get("首屏高信息量件", []) +
        opening_pairs.get("最容易堆满的信号组", []) +
        opening_pairs.get("开头信号", [])
    )

    chain_lines = sections.get("5. 标准翻刀链", [])
    chain_pairs = collect_profile_source_pairs(chain_lines)
    result["opening_chain_patterns"] = {}
    explicit_chain_terms = collect_profile_source_fragments(
        chain_pairs.get("opening_chain_patterns.profile_chain", []) +
        chain_pairs.get("翻刀链", [])
    )
    if explicit_chain_terms:
        escaped = [re.escape(term) for term in explicit_chain_terms if term]
        if escaped:
            result["opening_chain_patterns"]["profile_chain"] = "(" + "|".join(escaped) + ")"

    banned_lines = sections.get("7. 禁句 / 禁写法", [])
    banned_pairs = collect_profile_source_pairs(banned_lines)
    result["banned_phrases"] = clean_banned_phrase_terms(
        banned_pairs.get("禁句壳", []) +
        banned_pairs.get("禁解释句", []) +
        banned_pairs.get("禁成品宣言句", []) +
        banned_pairs.get("禁公开场假爽句", []) +
        banned_pairs.get("禁补字废话", []) +
        banned_pairs.get("禁句型", []) +
        banned_pairs.get("禁写法", [])
    )
    result["fake_reason_terms"] = normalize_items(
        collect_profile_source_reason_lines(banned_pairs.get("为什么假", []))
    )

    scene_lines = sections.get("8. 场面资产", []) or sections.get("8. 场面资产 / 后果链", [])
    scene_pairs = collect_profile_source_pairs(scene_lines)
    result["scene_assets"] = {
        "public_explosion": clean_scene_asset_terms(
            scene_pairs.get("scene_assets.public_explosion", []) or
            (scene_pairs.get("公开场硬件", []) + scene_pairs.get("关系翻牌场", []) + scene_pairs.get("场面资产", []))
        ),
        "external_order": clean_scene_asset_terms(
            scene_pairs.get("scene_assets.external_order", []) or
            (scene_pairs.get("外部秩序件", []) + scene_pairs.get("官方回正件", []))
        ),
        "consequence_chain": clean_scene_asset_terms(
            scene_pairs.get("scene_assets.consequence_chain", []) or
            scene_pairs.get("迟到挽回场", []) + scene_pairs.get("后果链", [])
        ),
    }
    result["scene_assets"] = {
        key: value for key, value in result["scene_assets"].items() if value
    }

    consequence_lines = sections.get("9. 后果链", []) or sections.get("8. 场面资产 / 后果链", [])
    consequence_pairs = collect_profile_source_pairs(consequence_lines)
    flip_pairs = collect_profile_source_pairs(sections.get("5. 标准翻刀链", []))
    merged_consequence_pairs: dict[str, list[str]] = defaultdict(list)
    for pair_map in (flip_pairs, consequence_pairs):
        for key, values in pair_map.items():
            merged_consequence_pairs[key].extend(values)
    result["consequence_terms"] = collect_profile_source_fragments(
        merged_consequence_pairs.get("感情伤抬升到现实伤的节点", []) +
        merged_consequence_pairs.get("秩序回正节点", []) +
        merged_consequence_pairs.get("长尾惩罚节点", []) +
        merged_consequence_pairs.get("离场 / 换图节点", []) +
        merged_consequence_pairs.get("后果链", [])
    )

    author_lines = sections.get("3. 作者DNA", [])
    author_pairs = collect_profile_source_pairs(author_lines)

    stance_lines = sections.get("10. 作者站位高危句", [])
    stance_pairs = collect_profile_source_pairs(stance_lines)
    result["author_stance_terms"] = clean_banned_phrase_terms(
        stance_pairs.get("容易写成作者判词的句型", []) +
        stance_pairs.get("容易写成主题总结的句型", []) +
        stance_pairs.get("容易写成整齐揭露的句型", []) +
        author_pairs.get("反面句型", []) +
        banned_pairs.get("禁句型", [])
    )

    style_lines = sections.get("11. style_assets 原始材料", [])
    style_pairs = collect_profile_source_pairs(style_lines)
    explicit_opening_hooks = clean_explicit_style_asset_terms(style_pairs.get("opening_hooks", []))
    fallback_opening_hooks = clean_style_asset_terms(
        collect_profile_source_style_fragments(opening_pairs.get("开头信号", []))
    )
    result["style_assets"] = {
        "opening_hooks": explicit_opening_hooks or fallback_opening_hooks,
        "misdirection": clean_explicit_style_asset_terms(style_pairs.get("misdirection", [])),
        "object_pressure": clean_explicit_style_asset_terms(style_pairs.get("object_pressure", [])),
        "action_axis": clean_explicit_style_asset_terms(style_pairs.get("action_axis", [])),
        "micro_actions": clean_explicit_style_asset_terms(style_pairs.get("micro_actions", [])),
        "quiet_pressure": clean_explicit_style_asset_terms(style_pairs.get("quiet_pressure", [])),
        "character_bias": clean_explicit_style_asset_terms(
            style_pairs.get("character_bias", []),
            preserve_commas=True,
        ),
        "meltdown_dialogue": clean_explicit_style_asset_terms(style_pairs.get("meltdown_dialogue", [])),
        "rotten_relationship": clean_explicit_style_asset_terms(style_pairs.get("rotten_relationship", [])),
        "dialogue_bridges": clean_explicit_style_asset_terms(
            style_pairs.get("dialogue_bridges", []),
            preserve_commas=True,
        ),
    }
    result["derived_patterns"] = collect_profile_source_reason_lines(
        style_pairs.get("derived_patterns", [])
    )
    migration_lines = sections.get("12. 迁移替换资产", [])
    migration_pairs = collect_profile_source_pairs(migration_lines)
    result["migration_assets"] = {
        "object_substitutes": collect_profile_source_style_fragments(
            migration_pairs.get("object_substitutes", [])
        ),
        "scene_substitutes": collect_profile_source_style_fragments(
            migration_pairs.get("scene_substitutes", [])
        ),
        "action_substitutes": collect_profile_source_style_fragments(
            migration_pairs.get("action_substitutes", [])
        ),
        "dialogue_substitutes": collect_profile_source_style_fragments(
            migration_pairs.get("dialogue_substitutes", [])
        ),
        "role_bias_variants": collect_profile_source_style_fragments(
            migration_pairs.get("role_bias_variants", [])
        ),
    }
    result["migration_assets"] = {
        key: value for key, value in result["migration_assets"].items() if value
    }

    inferred_story_guardrails = build_profile_story_guardrails(author_pairs, merged_consequence_pairs)
    explicit_story_guardrails = collect_explicit_story_guardrails(text)
    story_guardrails = merge_story_guardrail_dicts(
        inferred_story_guardrails,
        explicit_story_guardrails,
    )
    if story_guardrails:
        result["story_guardrails"] = story_guardrails

    result["bridge_rules"] = build_profile_source_bridge_rules(text)
    return result


def existing_file(root: Path, rel: str) -> Path | None:
    path = root / rel
    return path if path.exists() else None


def normalize_items(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in items:
        clean = re.sub(r"\s+", " ", item.strip())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def collect_asset_terms_from_text(text: str) -> list[str]:
    items: list[str] = []
    items.extend(collect_table_cells(text))
    items.extend(collect_nested_bullets(text))
    items.extend(collect_bullets(text))
    items.extend(extract_quoted_terms(text))
    return clean_style_asset_terms(items)


def parse_markdown_table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    headers: list[str] = []
    rows: list[list[str]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    table_started = False
    for line in lines:
        if "|" not in line:
            if table_started and rows:
                break
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if not table_started:
            headers = parts
            table_started = True
            continue
        if all(re.fullmatch(r"[:\-\s]+", cell or "") for cell in parts):
            continue
        if headers and len(parts) == len(headers):
            rows.append(parts)
    return headers, rows


def table_dict_rows(text: str) -> list[dict[str, str]]:
    headers, rows = parse_markdown_table_rows(text)
    if not headers:
        return []
    return [dict(zip(headers, row)) for row in rows]


STYLE_ASSET_STOPWORDS = {
    "原文未发现", "已扫原文未发现",
    "位置", "钩子内容", "原文真正为什么有效", "读者下一步在等什么", "回收位置", "一写就假的方式",
    "动作本体", "对应情绪", "角色状态", "替代的解释句", "可迁移题材",
    "角色", "稳定偏手", "常见触发场", "当场效果", "后续写法提醒",
    "失控类型", "触发点", "失控后暴露了什么",
    "漏出类型", "具体漏出件", "路线优先级",
    "典型说法类型", "口吻特征", "衔接效果",
    "误判方", "先误判了什么", "翻完后前文怎么变",
    "物件", "首次出现", "后续回收", "伤害层", "可替换功能件",
    "动作", "当下效果", "后续效果",
    "场面压力来源", "谁没说话", "未说破结果", "适用公开场",
    "上句功能", "下句接法", "动作垫句", "称呼变化",
}

STYLE_ASSET_KEYS = (
    "opening_hooks",
    "misdirection",
    "object_pressure",
    "action_axis",
    "micro_actions",
    "quiet_pressure",
    "character_bias",
    "meltdown_dialogue",
    "rotten_relationship",
    "dialogue_bridges",
)

GUARDRAIL_ITEM_LIMITS = {
    "different_face_evidence": 6,
    "reaction_order_split": 4,
    "action_authority_split": 4,
    "pre_evidence_reality_consequences": 5,
    "consequence_rebound_modes": 4,
    "tail_entry_owner": 2,
    "tail_entry_exclusion_reason": 3,
}

SAMPLE_LAYER_GRADE_KEYS = (
    "structure_grade",
    "performance_grade",
    "sentence_grade",
    "terminal_consequence_grade",
)

SAMPLE_USAGE_LAYER_KEYS = (
    "positive_dna_layers",
    "skeleton_only_layers",
    "negative_rule_layers",
)


def looks_like_style_header(text: str) -> bool:
    stripped = strip_asset_wrappers(text)
    if not stripped:
        return True
    if stripped in STYLE_ASSET_STOPWORDS:
        return True
    if len(stripped) <= 6 and re.fullmatch(r"(前段|中段|后段|开头|结尾|位置|角色|动作|物件|场面)", stripped):
        return True
    return False


def keep_style_asset(text: str) -> bool:
    stripped = strip_asset_wrappers(text)
    if not stripped:
        return False
    if looks_like_style_header(stripped):
        return False
    if len(stripped) > 14:
        return False
    if re.search(r"[，。？！；:=（）()]", stripped):
        return False
    if any(
        marker in stripped
        for marker in (
            "为什么",
            "会不会",
            "怎么",
            "不是",
            "这篇",
            "原文",
            "后续",
            "读者",
            "流程",
            "如果",
            "迁移",
            "顺序",
            "不能",
            "保证",
            "适合",
        )
    ):
        return False
    if re.search(r"(先|再|然后|最后|至少|必须|不要|不能|容易|适合|说明|负责|形成|完成|体现)$", stripped):
        return False
    if stripped.count("的") >= 2:
        return False
    return True


def keep_explicit_style_asset(text: str) -> bool:
    """Trust model-selected source assets; reject only structural pollution."""
    stripped = strip_asset_wrappers(text)
    if not stripped or len(stripped) > 32:
        return False
    if re.search(r"[。！？；:=（）()]", stripped):
        return False
    if re.search(r"[`#|]", stripped):
        return False
    return True


OBJECT_PRESSURE_CUE_PATTERNS = (
    r"视频",
    r"录音",
    r"录像",
    r"证据册",
    r"协议",
    r"离婚证",
    r"借条",
    r"钥匙",
    r"戒指",
    r"指环",
    r"声明书",
    r"铁盒",
    r"盒子",
    r"听诊器",
    r"医药箱",
    r"候诊(?:号|单)",
    r"红绳",
    r"保健册",
    r"回执",
    r"签收栏",
    r"[零一二三四五六七八九十百千万两\d]+封(?:信)?",
    r"花束",
    r"玫瑰",
    r"礼物",
    r"副驾驶",
    r"主位",
    r"座位",
    r"家属栏",
    r"门禁",
    r"工牌",
    r"账单",
    r"转账",
    r"截图",
    r"照片",
    r"信",
    r"卡",
    r"票",
    r"报告",
    r"档案",
    r"药",
)
OBJECT_PRESSURE_CUE_RE = re.compile("|".join(OBJECT_PRESSURE_CUE_PATTERNS))
OBJECT_PRESSURE_BAD_RE = re.compile(
    r"(花粉过敏|协议离婚了|怎么都|每次都会|不是|已经|开始|结束|回家|彻夜未归|回收成|整理成了)"
)
OBJECT_PRESSURE_SENTENCE_RE = re.compile(r"[我你他她它您咱][和们]?")


def matches_dynamic_object_term(text: str, dynamic_terms: set[str] | None) -> bool:
    if not dynamic_terms:
        return False
    stripped = strip_asset_wrappers(text)
    return stripped in dynamic_terms


def keep_object_pressure_asset(
    text: str,
    dynamic_terms: set[str] | None = None,
) -> bool:
    stripped = strip_asset_wrappers(text)
    if not keep_explicit_style_asset(stripped):
        return False
    if not OBJECT_PRESSURE_CUE_RE.search(stripped) and not matches_dynamic_object_term(
        stripped,
        dynamic_terms,
    ):
        return False
    if OBJECT_PRESSURE_BAD_RE.search(stripped):
        return False
    if OBJECT_PRESSURE_SENTENCE_RE.search(stripped) and not stripped.endswith(("视频", "录音", "录像", "钥匙", "花束", "礼物", "截图", "照片", "协议", "证据册", "副驾驶", "座位", "家属栏", "离婚证")):
        return False
    if len(stripped) > 18 and not stripped.endswith(("视频", "录音", "录像", "证据册")):
        return False
    return True


def clean_explicit_style_asset_terms(
    items: list[str],
    preserve_commas: bool = False,
) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        pattern = r"\s*/\s*|、|；|;" if preserve_commas else r"\s*/\s*|、|，|；|;"
        for part in re.split(pattern, strip_asset_wrappers(item)):
            stripped = strip_asset_wrappers(part)
            if keep_explicit_style_asset(stripped):
                cleaned.append(stripped)
    return normalize_items(cleaned)


def clean_object_pressure_terms(
    items: list[str],
    dynamic_terms: set[str] | None = None,
) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        for part in re.split(r"\s*/\s*|、|，|；|;", strip_asset_wrappers(item)):
            stripped = strip_asset_wrappers(part)
            if keep_object_pressure_asset(stripped, dynamic_terms):
                cleaned.append(stripped)
        cleaned.extend(
            [
                q
                for q in extract_quoted_terms(item)
                if keep_object_pressure_asset(q, dynamic_terms)
            ]
        )
    return normalize_items(cleaned)


def merge_style_asset_terms(
    explicit_items: list[str],
    fallback_items: list[str],
    preserve_commas: bool = False,
    allow_short: bool = False,
    relaxed_fallback: bool = False,
    explicit_cleaner=None,
    fallback_cleaner=None,
) -> list[str]:
    explicit_clean = explicit_cleaner or (
        lambda items: clean_explicit_style_asset_terms(
            items,
            preserve_commas=preserve_commas,
        )
    )
    fallback_clean = fallback_cleaner
    explicit = explicit_clean(explicit_items)
    if relaxed_fallback:
        fallback = (fallback_clean or explicit_clean)(fallback_items)
    else:
        fallback = (
            fallback_clean(fallback_items)
            if fallback_clean
            else clean_style_asset_terms(
                fallback_items,
                preserve_commas=preserve_commas,
                allow_short=allow_short,
            )
        )
    return normalize_items(explicit + fallback)


def clean_style_asset_terms(
    items: list[str],
    preserve_commas: bool = False,
    allow_short: bool = False,
) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        if preserve_commas:
            parts = re.split(r"\s*/\s*|、", strip_asset_wrappers(item))
        else:
            parts = split_scene_fragments(item)
        if not parts:
            parts = split_inline_assets(item)
        if not parts:
            parts = [item]
        for part in parts:
            stripped = strip_asset_wrappers(part)
            if preserve_commas:
                if (
                    ((1 <= len(stripped) <= 32) if allow_short else (3 <= len(stripped) <= 32))
                    and not re.search(r"[。？！；:=（）()]", stripped)
                    and not any(marker in stripped for marker in ("为什么", "迁移", "顺序", "不能", "读者"))
                ):
                    cleaned.append(stripped)
            elif keep_style_asset(stripped):
                cleaned.append(stripped)
    return normalize_items(cleaned)


def clean_style_asset_cell_terms(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        stripped = strip_asset_wrappers(item)
        if keep_style_asset(stripped):
            cleaned.append(stripped)
        cleaned.extend([q for q in extract_quoted_terms(item) if keep_style_asset(q)])
    return normalize_items(cleaned)


def clean_explicit_style_asset_cell_terms(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        stripped = strip_asset_wrappers(item)
        if keep_explicit_style_asset(stripped):
            cleaned.append(stripped)
        cleaned.extend(
            [q for q in extract_quoted_terms(item) if keep_explicit_style_asset(q)]
        )
    return normalize_items(cleaned)


def collect_terms_from_table_columns(text: str, columns: list[str], mode: str = "fragments") -> list[str]:
    rows = table_dict_rows(text)
    items: list[str] = []
    for row in rows:
        for column in columns:
            value = row.get(column, "")
            if value:
                if mode == "cell":
                    items.append(value)
                else:
                    items.extend(split_scene_fragments(value))
                    items.extend(extract_quoted_terms(value))
    if mode == "cell":
        return clean_style_asset_cell_terms(items)
    if mode == "explicit_cell":
        return clean_explicit_style_asset_cell_terms(items)
    return clean_style_asset_terms(items)


def collect_style_asset_terms_by_kind(asset_name: str, text: str, rel: str) -> list[str]:
    specific_columns = {
        "opening_hooks": ["原文怎么写", "钩子内容", "原文现象", "钩子"],
        "misdirection": ["先误判了什么", "从哪开始翻"],
        "object_pressure": ["物件"],
        "action_axis": ["动作", "动作本体"],
        "micro_actions": ["动作本体"],
        "quiet_pressure": ["场面压力来源", "环境音"],
        "character_bias": ["稳定偏手", "偏手动作", "偏手"],
        "meltdown_dialogue": ["失控类型"],
        "rotten_relationship": ["具体漏出件"],
        "dialogue_bridges": ["原文证据", "典型说法类型", "上句功能", "下句接法"],
    }
    specific_modes = {
        "opening_hooks": "explicit_cell",
        "misdirection": "cell",
        "action_axis": "cell",
        "micro_actions": "cell",
        "quiet_pressure": "cell",
        "meltdown_dialogue": "cell",
        "rotten_relationship": "cell",
        "dialogue_bridges": "explicit_cell",
    }

    if asset_name in specific_columns:
        terms = collect_terms_from_table_columns(
            text,
            specific_columns[asset_name],
            mode=specific_modes.get(asset_name, "fragments"),
        )
        if terms:
            return terms

    items: list[str] = []
    if asset_name == "opening_hooks":
        return []
    elif asset_name in {"dialogue_bridges", "meltdown_dialogue"}:
        items.extend(extract_quoted_terms(text))
    return clean_style_asset_terms(items)


def merge_string_lists(profiles: list[dict], field: str) -> list[str]:
    merged: list[str] = []
    for profile in profiles:
        value = profile.get(field, [])
        if isinstance(value, list):
            merged.extend(item for item in value if isinstance(item, str))
    return normalize_items(merged)


def merge_dict_of_lists(profiles: list[dict], field: str) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = defaultdict(list)
    for profile in profiles:
        value = profile.get(field, {})
        if not isinstance(value, dict):
            continue
        for key, items in value.items():
            if isinstance(items, list):
                merged[key].extend(item for item in items if isinstance(item, str))
    return {key: normalize_items(items) for key, items in merged.items() if items}


def merge_risk_layer_type(profiles: list[dict]) -> str | None:
    values: list[str] = []
    for profile in profiles:
        value = profile.get("risk_layer_type")
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    if not values:
        return None
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def merge_high_risk_layers(profiles: list[dict]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = defaultdict(list)
    for profile in profiles:
        value = profile.get("high_risk_layers", {})
        if not isinstance(value, dict):
            continue
        for key, items in value.items():
            if isinstance(items, list):
                merged[key].extend(item for item in items if isinstance(item, str))
    return {key: normalize_items(items) for key, items in merged.items() if items}


def merge_source_noise_risk(profiles: list[dict]) -> dict:
    levels: list[str] = []
    signals: list[str] = []
    for profile in profiles:
        value = profile.get("source_noise_risk", {})
        if not isinstance(value, dict):
            continue
        level = value.get("level")
        if isinstance(level, str) and level.strip():
            levels.append(level.strip())
        items = value.get("signals", [])
        if isinstance(items, list):
            signals.extend(item for item in items if isinstance(item, str))
    out: dict[str, object] = {}
    if levels:
        counts: dict[str, int] = defaultdict(int)
        for level in levels:
            counts[level] += 1
        out["level"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    if signals:
        out["signals"] = normalize_items(signals)
    return out


def merge_bridge_safety_warning(profiles: list[dict]) -> dict:
    summaries: list[str] = []
    risky_bridges: list[str] = []
    why_original_not_processed: list[str] = []
    rewrite_routes: list[str] = []
    for profile in profiles:
        value = profile.get("bridge_safety_warning", {})
        if not isinstance(value, dict):
            continue
        summary = value.get("summary")
        if isinstance(summary, str) and summary.strip():
            summaries.append(summary.strip())
        items = value.get("risky_bridges", [])
        if isinstance(items, list):
            risky_bridges.extend(item for item in items if isinstance(item, str))
        items = value.get("why_original_not_processed", [])
        if isinstance(items, list):
            why_original_not_processed.extend(item for item in items if isinstance(item, str))
        route = value.get("rewrite_route")
        if isinstance(route, str) and route.strip():
            rewrite_routes.append(route.strip())
    out: dict[str, object] = {}
    if summaries:
        out["summary"] = summaries[0]
    if risky_bridges:
        out["risky_bridges"] = normalize_items(risky_bridges)
    if why_original_not_processed:
        out["why_original_not_processed"] = normalize_items(why_original_not_processed)
    if rewrite_routes:
        counts: dict[str, int] = defaultdict(int)
        for route in rewrite_routes:
            counts[route] += 1
        out["rewrite_route"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return out


def merge_story_guardrails(profiles: list[dict]) -> dict:
    return merge_story_guardrail_dicts(
        *[
            profile.get("story_guardrails", {})
            for profile in profiles
            if isinstance(profile, dict)
        ]
    )


def merge_sample_grading(profiles: list[dict]) -> dict:
    levels: list[str] = []
    dna_usable: list[str] = []
    summaries: list[str] = []
    source_score_judgements: list[str] = []
    source_score_overalls: list[str] = []
    source_score_policies: list[str] = []
    source_score_high_blocks: list[str] = []
    learnable_layers: list[str] = []
    forbidden_layers: list[str] = []
    misuse_warnings: list[str] = []
    usage_write: list[str] = []
    usage_merge: list[str] = []
    usage_deslop: list[str] = []
    usage_noninherit: list[str] = []
    tags: list[str] = []
    final_allow_dna: list[str] = []
    final_allow_bridge_merge: list[str] = []
    final_negative_only: list[str] = []
    layer_grades: dict[str, list[str]] = defaultdict(list)
    usage_layers: dict[str, list[str]] = defaultdict(list)

    for profile in profiles:
        grading = profile.get("sample_grading", {})
        if not isinstance(grading, dict):
            continue
        for key, bucket in (
            ("level", levels),
            ("dna_usable", dna_usable),
            ("summary", summaries),
            ("source_score_judgement", source_score_judgements),
            ("source_score_overall", source_score_overalls),
            ("source_score_policy", source_score_policies),
        ):
            value = grading.get(key)
            if isinstance(value, str) and value.strip():
                bucket.append(value.strip())
        for key in SAMPLE_LAYER_GRADE_KEYS:
            value = grading.get(key)
            if isinstance(value, str) and value.strip():
                layer_grades[key].append(value.strip())
        for key in SAMPLE_USAGE_LAYER_KEYS:
            values = grading.get(key, [])
            if isinstance(values, list):
                usage_layers[key].extend(item for item in values if isinstance(item, str))
        high_blocks = grading.get("source_score_high_blocks", [])
        if isinstance(high_blocks, list):
            source_score_high_blocks.extend(item for item in high_blocks if isinstance(item, str))
        for key, bucket in (
            ("learnable_layers", learnable_layers),
            ("forbidden_layers", forbidden_layers),
            ("misuse_warnings", misuse_warnings),
        ):
            values = grading.get(key, [])
            if isinstance(values, list):
                bucket.extend(item for item in values if isinstance(item, str))
        usage = grading.get("usage_guidance", {})
        if isinstance(usage, dict):
            for key, bucket in (
                ("写新稿时怎么用这本", usage_write),
                ("融合写作时怎么用这本", usage_merge),
                ("去 AI 味时怎么用这本", usage_deslop),
                ("哪些内容只可参考、不可继承", usage_noninherit),
            ):
                value = usage.get(key)
                if isinstance(value, str) and value.strip():
                    bucket.append(value.strip())
        final_verdict = grading.get("final_verdict", {})
        if isinstance(final_verdict, dict):
            for key, bucket in (
                ("allow_dna", final_allow_dna),
                ("allow_bridge_merge", final_allow_bridge_merge),
                ("negative_only", final_negative_only),
            ):
                value = final_verdict.get(key)
                if isinstance(value, str) and value.strip():
                    bucket.append(value.strip())
            verdict_tags = final_verdict.get("tags", [])
            if isinstance(verdict_tags, list):
                tags.extend(item for item in verdict_tags if isinstance(item, str))

    out: dict[str, object] = {}
    severity_rank = {"C类负样本": 3, "B类骨架样本": 2, "A类正样本": 1}
    if levels:
        normalized = [item.strip() for item in levels if item.strip()]
        out["level"] = sorted(normalized, key=lambda item: (-severity_rank.get(item, 0), item))[0]
    if dna_usable:
        if any("不可" in item for item in dna_usable):
            out["dna_usable"] = "不可"
        elif any("部分" in item for item in dna_usable):
            out["dna_usable"] = "部分可"
        else:
            out["dna_usable"] = dna_usable[0]
    if summaries:
        out["summary"] = summaries[0]
    grade_rank = {"C": 3, "B": 2, "A": 1}
    for key, values in layer_grades.items():
        normalized = [value.upper() for value in values if value.upper() in grade_rank]
        if normalized:
            out[key] = sorted(normalized, key=lambda value: -grade_rank[value])[0]
    for key, values in usage_layers.items():
        if values:
            out[key] = normalize_items(values)
    if source_score_judgements:
        out["source_score_judgement"] = source_score_judgements[0]
    if source_score_overalls:
        out["source_score_overall"] = source_score_overalls[0]
    if source_score_policies:
        out["source_score_policy"] = source_score_policies[0]
    if source_score_high_blocks:
        out["source_score_high_blocks"] = normalize_items(source_score_high_blocks)
    if learnable_layers:
        out["learnable_layers"] = normalize_items(learnable_layers)
    if forbidden_layers:
        out["forbidden_layers"] = normalize_items(forbidden_layers)
    if misuse_warnings:
        out["misuse_warnings"] = normalize_items(misuse_warnings)
    usage_guidance: dict[str, str] = {}
    for key, bucket in (
        ("写新稿时怎么用这本", usage_write),
        ("融合写作时怎么用这本", usage_merge),
        ("去 AI 味时怎么用这本", usage_deslop),
        ("哪些内容只可参考、不可继承", usage_noninherit),
    ):
        if bucket:
            usage_guidance[key] = bucket[0]
    if usage_guidance:
        out["usage_guidance"] = usage_guidance
    final_verdict: dict[str, object] = {}
    if final_allow_dna:
        final_verdict["allow_dna"] = "否" if any(item in ("否", "不可") for item in final_allow_dna) else final_allow_dna[0]
    if final_allow_bridge_merge:
        final_verdict["allow_bridge_merge"] = "否" if any(item in ("否", "不可") for item in final_allow_bridge_merge) else final_allow_bridge_merge[0]
    if final_negative_only:
        final_verdict["negative_only"] = "是" if any(item in ("是", "仅供反面规则", "仅供负面规则") for item in final_negative_only) else final_negative_only[0]
    if tags:
        final_verdict["tags"] = normalize_items(tags)
    if final_verdict:
        out["final_verdict"] = final_verdict
    return out


def derive_source_label(profile: dict, profile_path: Path | None = None) -> str:
    meta = profile.get("meta", {})
    if isinstance(meta, dict):
        name = meta.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    if profile_path is not None:
        parent = profile_path.parent
        if parent.name == "写作资产" and parent.parent.name:
            return parent.parent.name
        if parent.name:
            return parent.name
    return "未命名来源"


def build_sample_source_entry(profile: dict, profile_path: Path | None = None) -> dict[str, str]:
    grading = profile.get("sample_grading", {})
    if not isinstance(grading, dict) or not grading:
        return {}
    final_verdict = grading.get("final_verdict", {})
    if not isinstance(final_verdict, dict):
        final_verdict = {}
    usage_guidance = grading.get("usage_guidance", {})
    if not isinstance(usage_guidance, dict):
        usage_guidance = {}
    entry = {
        "name": derive_source_label(profile, profile_path),
        "level": str(grading.get("level", "")).strip(),
        "dna_usable": str(grading.get("dna_usable", "")).strip(),
        "source_score_overall": str(grading.get("source_score_overall", "")).strip(),
        "source_score_policy": str(grading.get("source_score_policy", "")).strip(),
        "allow_dna": str(final_verdict.get("allow_dna", "")).strip(),
        "allow_bridge_merge": str(final_verdict.get("allow_bridge_merge", "")).strip(),
        "negative_only": str(final_verdict.get("negative_only", "")).strip(),
        "use_for_write": str(usage_guidance.get("写新稿时怎么用这本", "")).strip(),
        "use_for_merge": str(usage_guidance.get("融合写作时怎么用这本", "")).strip(),
        "noninherit": str(usage_guidance.get("哪些内容只可参考、不可继承", "")).strip(),
    }
    for key in SAMPLE_LAYER_GRADE_KEYS:
        entry[key] = str(grading.get(key, "")).strip()
    return {key: value for key, value in entry.items() if value}


def build_sample_source_buckets(source_entries: list[dict[str, str]]) -> dict[str, object]:
    if not source_entries:
        return {}
    levels = {"A类正样本": [], "B类骨架样本": [], "C类负样本": []}
    positive_dna_sources: list[str] = []
    skeleton_only_sources: list[str] = []
    negative_only_sources: list[str] = []
    blocked_opening_sources: list[str] = []
    for entry in source_entries:
        name = entry.get("name")
        if not name:
            continue
        level = entry.get("level")
        if level in levels:
            levels[level].append(name)
        allow_dna = entry.get("allow_dna")
        negative_only = entry.get("negative_only")
        policy = entry.get("source_score_policy", "")
        dna_usable = entry.get("dna_usable", "")
        if level == "A类正样本" and allow_dna not in {"否", "不可"} and negative_only != "是":
            positive_dna_sources.append(name)
        if level == "B类骨架样本" or "部分" in dna_usable:
            skeleton_only_sources.append(name)
        if level == "C类负样本" or negative_only == "是":
            negative_only_sources.append(name)
        if any(term in policy for term in ("不提开头现成讲法", "不学开头现成写法", "不得拿它做首屏讲法样本", "不提开篇", "不学现成婚礼停流程讲法")):
            blocked_opening_sources.append(name)
    out: dict[str, object] = {
        "entries": source_entries,
        "by_level": {key: sorted(set(value)) for key, value in levels.items() if value},
        "positive_dna_sources": sorted(set(positive_dna_sources)),
        "skeleton_only_sources": sorted(set(skeleton_only_sources)),
        "negative_only_sources": sorted(set(negative_only_sources)),
        "blocked_opening_sources": sorted(set(blocked_opening_sources)),
    }
    out["enforcement"] = {
        "exclude_negative_from_positive_merge": bool(out["negative_only_sources"]),
        "restrict_bone_only_sources": bool(out["skeleton_only_sources"]),
        "require_positive_dna_source": bool(out["positive_dna_sources"]),
    }
    if out["positive_dna_sources"]:
        if out["negative_only_sources"] or out["skeleton_only_sources"]:
            out["effective_write_level"] = "B类骨架样本"
            out["effective_write_policy"] = "融合包存在可用正向 DNA，但混入了骨架样本或负样本；写作时按保守融合口径执行，只从正样本提句法，其余来源只提骨架或反面规则。"
            out["effective_dna_usable"] = "部分可"
            out["effective_allow_dna"] = "部分可"
        else:
            out["effective_write_level"] = "A类正样本"
            out["effective_write_policy"] = "融合来源均可作为正向 DNA 使用，可正常提句法、口气和桥段承重件。"
            out["effective_dna_usable"] = "可"
            out["effective_allow_dna"] = "可"
    else:
        out["effective_write_level"] = "C类负样本"
        out["effective_write_policy"] = "当前融合包没有可用正向 DNA 来源，不得直接开正文，需先补正样本。"
        out["effective_dna_usable"] = "不可"
        out["effective_allow_dna"] = "否"
    return out


def merge_list_of_dicts(profiles: list[dict], field: str, unique_key: str) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for profile in profiles:
        value = profile.get(field, [])
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            key = item.get(unique_key)
            if not isinstance(key, str) or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def normalize_bridge_key(name: str) -> str:
    clean = re.sub(r"\s+", " ", name.strip())
    clean = clean.replace("（", "(").replace("）", ")")
    clean = re.sub(r"^桥段\s*\d+\s*[：:]\s*", "", clean)
    clean = re.sub(r"^\d+\s*[：:]\s*", "", clean)
    clean = re.sub(r"桥段$", "", clean).strip()
    return clean


def extract_bridge_sequence(name: str) -> str:
    chinese_digits = {
        "一": "1",
        "二": "2",
        "三": "3",
        "四": "4",
        "五": "5",
        "六": "6",
        "七": "7",
        "八": "8",
        "九": "9",
        "十": "10",
    }
    match = re.match(r"^(?:桥段\s*)?(\d+|[一二三四五六七八九十]+)\s*[：:]", name.strip())
    if not match:
        return ""
    raw = match.group(1)
    return chinese_digits.get(raw, raw)


def merge_bridge_rule_lists(*rule_lists: list[dict], merge_by_sequence: bool = False) -> list[dict]:
    merged: list[dict] = []
    index_by_key: dict[str, int] = {}
    for rules in rule_lists:
        position = 0
        for item in rules:
            if not isinstance(item, dict):
                continue
            bridge = item.get("bridge")
            if not isinstance(bridge, str) or not bridge.strip():
                continue
            position += 1
            sequence = extract_bridge_sequence(bridge)
            if merge_by_sequence:
                key = f"seq::{sequence or position}"
            else:
                key = normalize_bridge_key(bridge)
            normalized_item = {
                "bridge": bridge.strip(),
                "opening_pattern": normalize_items(item.get("opening_pattern", [])),
                "must_keep": normalize_items(item.get("must_keep", [])),
                "must_avoid": normalize_items(item.get("must_avoid", [])),
                "fake_signals": normalize_items(item.get("fake_signals", [])),
                "recommended_sequence": normalize_items(item.get("recommended_sequence", [])),
                "why_order_matters": normalize_items(item.get("why_order_matters", [])),
                "why_original_passes": normalize_items(item.get("why_original_passes", [])),
            }
            existing_index = index_by_key.get(key)
            if existing_index is None:
                index_by_key[key] = len(merged)
                merged.append(normalized_item)
                continue
            existing = merged[existing_index]
            existing["opening_pattern"] = normalize_items(existing.get("opening_pattern", []) + normalized_item["opening_pattern"])
            existing["must_keep"] = normalize_items(existing.get("must_keep", []) + normalized_item["must_keep"])
            existing["must_avoid"] = normalize_items(existing.get("must_avoid", []) + normalized_item["must_avoid"])
            existing["fake_signals"] = normalize_items(existing.get("fake_signals", []) + normalized_item["fake_signals"])
            existing["recommended_sequence"] = normalize_items(
                existing.get("recommended_sequence", []) + normalized_item["recommended_sequence"]
            )
            existing["why_order_matters"] = normalize_items(
                existing.get("why_order_matters", []) + normalized_item["why_order_matters"]
            )
            existing["why_original_passes"] = normalize_items(
                existing.get("why_original_passes", []) + normalized_item["why_original_passes"]
            )
    return merged


def build_opening_signal_groups(collected: dict[str, list[str]]) -> dict[str, list[str]]:
    explicit_groups = {
        key.split("::", 1)[1]: value
        for key, value in collected.items()
        if key.startswith("profile_opening_group::") and value
    }
    return {
        key: normalize_items(clean_opening_group_terms(value))
        for key, value in explicit_groups.items()
        if clean_opening_group_terms(value)
    }


def build_bridge_rules(text: str) -> list[dict]:
    rules: list[dict] = []
    pattern = re.compile(
        r"^##\s+(桥段\s*\d+|桥段\s*[一二三四五六七八九十]+|桥\d+|桥[一二三四五六七八九十]+)\s*(.*)$",
        flags=re.M,
    )
    matches = list(pattern.finditer(text))
    for idx, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[body_start:body_end]
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        seq_marker = match.group(1).strip()
        title_suffix = match.group(2).strip().lstrip("：: ").strip()
        sequence = extract_bridge_sequence(seq_marker)
        if sequence:
            title = f"桥段{sequence}：{title_suffix}"
        else:
            title = f"桥段：{title_suffix}" if title_suffix else "桥段"
        must_keep: list[str] = []
        must_avoid: list[str] = []
        why: list[str] = []
        opening_pattern: list[str] = []
        recommended_sequence: list[str] = []
        why_order_matters: list[str] = []
        fake_signals: list[str] = []
        current = None
        for line in lines[1:]:
            stripped = line.lstrip()
            if stripped.startswith("### ") or stripped.startswith("## "):
                current = stripped
            elif stripped.startswith("- "):
                item = stripped[2:].strip()
                inline_key = ""
                inline_val = item
                if "：" in item:
                    inline_key, inline_val = item.split("：", 1)
                elif ":" in item:
                    inline_key, inline_val = item.split(":", 1)
                inline_key = inline_key.strip()
                inline_val = inline_val.strip()
                if item.endswith(("：", ":")) and inline_key:
                    current = inline_key
                    continue
                if current and any(k in current for k in ("原文怎么起手", "原文起手件", "原文起手")):
                    opening_pattern.extend(split_inline_assets(item))
                elif inline_key in {"原文怎么起手", "原文起手件", "原文起手"}:
                    opening_pattern.extend(split_inline_assets(inline_val))
                elif current and any(k in current for k in ("推荐迁移顺序", "不能丢的顺序")):
                    recommended_sequence.append(item)
                elif inline_key in {"推荐迁移顺序", "不能丢的顺序"}:
                    recommended_sequence.append(inline_val)
                elif current and "为什么这个顺序不能乱" in current:
                    why_order_matters.append(item)
                elif inline_key == "为什么这个顺序不能乱":
                    why_order_matters.append(inline_val)
                elif current and any(k in current for k in ("易假点", "最容易写假的点", "仿稿最易假点", "禁写")):
                    fake_signals.append(item)
                    must_avoid.append(item)
                elif inline_key in {"易假点", "最容易写假的点", "新稿最容易写假的点", "仿稿最易假点", "禁写", "仿稿会假"}:
                    fake_signals.append(inline_val)
                    must_avoid.append(inline_val)
                elif current and any(k in current for k in ("必须保留", "仿写必留", "承重件不可丢", "必留承重件", "原文承重件", "原文真正承重件")):
                    must_keep.extend(split_inline_assets(item))
                elif inline_key in {"必须保留件", "必须保留的承重件", "必须保留的东西", "原文承重件", "承重件", "原文真正承重件", "承重件不可丢", "必留承重件", "仿写必留"}:
                    must_keep.extend(split_inline_assets(inline_val))
                elif current and any(k in current for k in ("绝对不能出现", "绝对不能写的 AI 句", "绝对不能出现的 AI 句子")):
                    must_avoid.append(item)
                elif inline_key in {"绝对不能出现的 AI 句子", "绝对不能写的 AI 句"}:
                    must_avoid.append(inline_val)
                elif current and any(k in current for k in ("原文为什么能过", "原文为什么过检", "为什么能过", "原文能过 / 仿稿会假")):
                    if inline_key == "仿稿会假":
                        fake_signals.append(inline_val)
                        must_avoid.append(inline_val)
                    elif inline_key == "原文能过":
                        why.append(inline_val)
                    else:
                        why.append(item)
                elif inline_key in {"原文为什么能过", "原文为什么过检", "为什么能过", "原文能过"}:
                    why.append(inline_val)
        rules.append(
            {
                "bridge": title,
                "opening_pattern": clean_asset_terms(opening_pattern),
                "must_keep": clean_asset_terms(must_keep),
                "must_avoid": collect_bridge_reason_terms(must_avoid),
                "fake_signals": collect_bridge_reason_terms(fake_signals),
                "recommended_sequence": collect_bridge_step_terms(recommended_sequence),
                "why_order_matters": collect_bridge_reason_terms(why_order_matters),
                "why_original_passes": collect_bridge_reason_terms(why),
            }
        )
    return rules


def generate_profile_from_sources(sources: list[Path], name: str) -> dict:
    opening_hook_blacklist = {
        "场景",
        "人物",
        "再替换人物",
        "再让人物意识跟上",
        "顺序乱了就会像功能按钮",
    }
    collected: dict[str, list[str]] = defaultdict(list)
    bridge_rules: list[dict] = []
    sample_source_entries: list[dict[str, str]] = []
    dynamic_object_terms: set[str] = set()
    style_asset_files = {
        "opening_hooks": [
            "可直接仿写_导语拆解表.md",
            "可直接仿写_钩子表.md",
        ],
        "misdirection": [
            "可直接仿写_误判表.md",
        ],
        "object_pressure": [
            "可直接仿写_物件表.md",
        ],
        "action_axis": [
            "可直接仿写_动作表.md",
        ],
        "micro_actions": [
            "可直接仿写_微动作表.md",
        ],
        "quiet_pressure": [
            "可直接仿写_安静压迫场表.md",
        ],
        "character_bias": [
            "可直接仿写_人物偏手表.md",
        ],
        "meltdown_dialogue": [
            "可直接仿写_失控说话表.md",
        ],
        "rotten_relationship": [
            "可直接仿写_烂关系漏出表.md",
        ],
        "dialogue_bridges": [
            "可直接仿写_对白功能表.md",
            "可直接仿写_对话衔接表.md",
        ],
    }

    for root in sources:
        dynamic_object_terms.update(collect_dynamic_object_terms(root))
        local_profile_source_bridges: list[dict] = []
        local_bridge_rules: list[dict] = []
        local_story_guardrails: list[dict] = []
        source_entry: dict[str, str] = {"name": root.name}
        sample_grading = existing_file(root, "写作资产/样本分级与可学层.md")
        if sample_grading:
            parsed = parse_sample_grading_text(read_text(sample_grading))
            grading = parsed.get("sample_grading", {})
            if isinstance(grading, dict):
                for key, bucket_key in (
                    ("level", "sample_level"),
                    ("dna_usable", "sample_dna_usable"),
                    ("summary", "sample_summary"),
                    ("source_score_judgement", "sample_source_score_judgement"),
                    ("source_score_overall", "sample_source_score_overall"),
                    ("source_score_policy", "sample_source_score_policy"),
                ):
                    value = grading.get(key)
                    if isinstance(value, str) and value.strip():
                        collected[bucket_key].append(value.strip())
                        if key in {"level", "dna_usable", "source_score_overall", "source_score_policy"}:
                            source_entry[key] = value.strip()
                for key in SAMPLE_LAYER_GRADE_KEYS:
                    value = grading.get(key)
                    if isinstance(value, str) and value.strip():
                        collected[f"sample::{key}"].append(value.strip())
                        source_entry[key] = value.strip()
            for key in ("learnable_layers", "forbidden_layers", "misuse_warnings"):
                values = parsed.get(key, [])
                if isinstance(values, list):
                    collected[f"sample::{key}"].extend(item for item in values if isinstance(item, str))
            for key in SAMPLE_USAGE_LAYER_KEYS:
                values = parsed.get(key, [])
                if isinstance(values, list):
                    collected[f"sample::{key}"].extend(item for item in values if isinstance(item, str))
            source_score_high_blocks = grading.get("source_score_high_blocks", [])
            if isinstance(source_score_high_blocks, list):
                collected["sample::source_score_high_blocks"].extend(
                    item for item in source_score_high_blocks if isinstance(item, str)
                )
            usage = parsed.get("usage_guidance", {})
            if isinstance(usage, dict):
                for key, bucket_key in (
                    ("写新稿时怎么用这本", "sample_usage_write"),
                    ("融合写作时怎么用这本", "sample_usage_merge"),
                    ("去 AI 味时怎么用这本", "sample_usage_deslop"),
                    ("哪些内容只可参考、不可继承", "sample_usage_noninherit"),
                ):
                    value = usage.get(key)
                    if isinstance(value, str) and value.strip():
                        collected[bucket_key].append(value.strip())
            final_verdict = parsed.get("final_verdict", {})
            if isinstance(final_verdict, dict):
                for key, bucket_key in (
                    ("allow_dna", "sample_allow_dna"),
                    ("allow_bridge_merge", "sample_allow_bridge_merge"),
                    ("negative_only", "sample_negative_only"),
                ):
                    value = final_verdict.get(key)
                    if isinstance(value, str) and value.strip():
                        collected[bucket_key].append(value.strip())
                        source_entry[key] = value.strip()
                tags = final_verdict.get("tags", [])
                if isinstance(tags, list):
                    collected["sample_tags"].extend(item for item in tags if isinstance(item, str))
            usage = parsed.get("usage_guidance", {})
            if isinstance(usage, dict):
                for key, entry_key in (
                    ("写新稿时怎么用这本", "use_for_write"),
                    ("融合写作时怎么用这本", "use_for_merge"),
                    ("哪些内容只可参考、不可继承", "noninherit"),
                ):
                    value = usage.get(key)
                    if isinstance(value, str) and value.strip():
                        source_entry[entry_key] = value.strip()
        profile_source = existing_file(root, "写作资产/profile_source.md")
        if profile_source:
            text = read_text(profile_source)
            parsed = parse_profile_source(text)
            sample_grading = parsed.get("sample_grading", {})
            if isinstance(sample_grading, dict):
                for key, bucket_key in (
                    ("level", "sample_level"),
                    ("dna_usable", "sample_dna_usable"),
                    ("source_score_judgement", "sample_source_score_judgement"),
                    ("source_score_overall", "sample_source_score_overall"),
                    ("source_score_policy", "sample_source_score_policy"),
                ):
                    value = sample_grading.get(key)
                    if isinstance(value, str) and value.strip():
                        collected[bucket_key].append(value.strip())
                        entry_key = {
                            "level": "level",
                            "dna_usable": "dna_usable",
                            "source_score_overall": "source_score_overall",
                            "source_score_policy": "source_score_policy",
                        }.get(key)
                        if entry_key:
                            source_entry[entry_key] = value.strip()
                for key in SAMPLE_LAYER_GRADE_KEYS:
                    value = sample_grading.get(key)
                    if isinstance(value, str) and value.strip():
                        collected[f"sample::{key}"].append(value.strip())
                        source_entry[key] = value.strip()
                for key, bucket_key in (
                    ("learnable_layers", "sample::learnable_layers"),
                    ("forbidden_layers", "sample::forbidden_layers"),
                    ("evidence", "sample::evidence"),
                    ("usage_guidance", "sample::usage_guidance"),
                ):
                    values = sample_grading.get(key, [])
                    if isinstance(values, list):
                        collected[bucket_key].extend(item for item in values if isinstance(item, str))
                for key in SAMPLE_USAGE_LAYER_KEYS:
                    values = sample_grading.get(key, [])
                    if isinstance(values, list):
                        collected[f"sample::{key}"].extend(
                            item for item in values if isinstance(item, str)
                        )
                high_blocks = sample_grading.get("source_score_high_blocks", [])
                if isinstance(high_blocks, list):
                    collected["sample::source_score_high_blocks"].extend(
                        item for item in high_blocks if isinstance(item, str)
                    )
            risk_layer_type = parsed.get("risk_layer_type")
            if isinstance(risk_layer_type, str) and risk_layer_type.strip():
                collected["profile_risk_layer_type"].append(risk_layer_type.strip())
            for key, items in parsed.get("high_risk_layers", {}).items():
                if isinstance(items, list):
                    collected[f"profile_high_risk_layer::{key}"].extend(item for item in items if isinstance(item, str))
            source_noise_risk = parsed.get("source_noise_risk", {})
            if isinstance(source_noise_risk, dict):
                level = source_noise_risk.get("level")
                if isinstance(level, str) and level.strip():
                    collected["profile_source_noise_level"].append(level.strip())
                items = source_noise_risk.get("signals", [])
                if isinstance(items, list):
                    collected["profile_source_noise_signals"].extend(item for item in items if isinstance(item, str))
            bridge_safety_warning = parsed.get("bridge_safety_warning", {})
            if isinstance(bridge_safety_warning, dict):
                summary = bridge_safety_warning.get("summary")
                if isinstance(summary, str) and summary.strip():
                    collected["profile_bridge_safety_summary"].append(summary.strip())
                route = bridge_safety_warning.get("rewrite_route")
                if isinstance(route, str) and route.strip():
                    collected["profile_bridge_safety_route"].append(route.strip())
                items = bridge_safety_warning.get("risky_bridges", [])
                if isinstance(items, list):
                    collected["profile_bridge_safety_risky"].extend(item for item in items if isinstance(item, str))
                items = bridge_safety_warning.get("why_original_not_processed", [])
                if isinstance(items, list):
                    collected["profile_bridge_safety_why"].extend(item for item in items if isinstance(item, str))
            collected["profile_opening_terms"].extend(parsed.get("opening_terms", []))
            for chain_name, pattern in parsed.get("opening_chain_patterns", {}).items():
                collected[f"profile_opening_chain::{chain_name}"].append(pattern)
            collected["banned_phrases"].extend(parsed.get("banned_phrases", []))
            for group_name, items in parsed.get("opening_signal_groups", {}).items():
                collected[f"profile_opening_group::{group_name}"].extend(items)
            for asset_name, items in parsed.get("scene_assets", {}).items():
                collected[f"profile_scene_asset::{asset_name}"].extend(items)
            for asset_name, items in parsed.get("style_assets", {}).items():
                collected[f"profile_style_asset::{asset_name}"].extend(items)
            collected["profile_derived_patterns"].extend(parsed.get("derived_patterns", []))
            for asset_name, items in parsed.get("migration_assets", {}).items():
                collected[f"profile_migration_asset::{asset_name}"].extend(items)
            collected["profile_consequence_terms"].extend(parsed.get("consequence_terms", []))
            collected["profile_author_stance"].extend(parsed.get("author_stance_terms", []))
            story_guardrails = parsed.get("story_guardrails", {})
            if isinstance(story_guardrails, dict):
                local_story_guardrails.append(story_guardrails)
                for group_name, group in story_guardrails.items():
                    if not isinstance(group, dict):
                        continue
                    for key, items in group.items():
                        if isinstance(items, list):
                            collected[f"profile_story_guardrail::{group_name}::{key}"].extend(
                                item for item in items if isinstance(item, str)
                            )
            local_profile_source_bridges.extend(parsed.get("bridge_rules", []))

        dna = existing_file(root, "写作资产/作者DNA指纹.md")
        if dna:
            text = read_text(dna)
            collected["dna_terms"].extend(extract_quoted_terms(text))
            collected["dna_terms"].extend(collect_nested_bullets(text))
            aux_guardrails = build_story_guardrails_from_aux_text(text, "作者DNA指纹")
            if aux_guardrails:
                local_story_guardrails.append(aux_guardrails)

        bridge = existing_file(root, "写作资产/同桥段过检规则.md")
        if bridge:
            text = read_text(bridge)
            collected["bridge_terms"].extend(extract_quoted_terms(text))
            collected["bridge_terms"].extend(collect_nested_bullets(text))
            local_bridge_rules.extend(build_bridge_rules(text))
            aux_guardrails = build_story_guardrails_from_aux_text(text, "同桥段过检规则")
            if aux_guardrails:
                local_story_guardrails.append(aux_guardrails)

        high_risk_bridge = existing_file(root, "写作资产/高敏桥段识别.md")
        if high_risk_bridge:
            text = read_text(high_risk_bridge)
            aux_guardrails = build_story_guardrails_from_aux_text(text, "高敏桥段识别")
            if aux_guardrails:
                local_story_guardrails.append(aux_guardrails)

        banned = existing_file(root, "写作资产/仿写约束_禁写清单.md")
        if banned:
            text = read_text(banned)
            collected["banned_phrases"].extend(
                collect_section_bullets(text, ("禁句型", "最该拦掉", "禁写法"))
            )
            collected["banned_phrases"].extend(
                collect_section_nested_bullets(text, ("禁句型", "最该拦掉", "禁写法"))
            )
            collected["banned_phrases"].extend(collect_banned_payload_lines(text))

        for rel in [
            "可直接仿写_公开炸场表.md",
            "可直接仿写_外部秩序表.md",
            "可直接仿写_后果链表.md",
            "可直接仿写_人物偏手表.md",
            "可直接仿写_失控说话表.md",
            "可直接仿写_烂关系漏出表.md",
        ]:
            path = existing_file(root, rel)
            if path:
                collected["table_terms"].extend(clean_asset_terms(collect_table_cells(read_text(path))))

        for asset_name, rel_paths in style_asset_files.items():
            for rel in rel_paths:
                path = existing_file(root, rel)
                if not path:
                    continue
                text = read_text(path)
                collected[f"style_asset::{asset_name}"].extend(
                    collect_style_asset_terms_by_kind(asset_name, text, rel)
                )

        detail_dir = root / "原文细节库"
        if detail_dir.exists():
            for path in detail_dir.glob("*.md"):
                collected["detail_terms"].extend(clean_asset_terms(extract_quoted_terms(read_text(path))))

        if local_profile_source_bridges or local_bridge_rules:
            bridge_rules.extend(
                merge_bridge_rule_lists(local_profile_source_bridges, local_bridge_rules, merge_by_sequence=True)
            )
        if local_story_guardrails:
            merged_local_guardrails = merge_story_guardrail_dicts(*local_story_guardrails)
            for group_name, group in merged_local_guardrails.items():
                if not isinstance(group, dict):
                    continue
                for key, items in group.items():
                    if isinstance(items, list):
                        collected[f"profile_story_guardrail::{group_name}::{key}"].extend(
                            item for item in items if isinstance(item, str)
                        )
        if len(source_entry) > 1:
            sample_source_entries.append(source_entry)

    opening_signal_groups = build_opening_signal_groups(collected)

    author_stance_patterns = []
    banned_phrases = clean_banned_phrase_terms(collected["banned_phrases"])
    banned_phrases = normalize_items(banned_phrases + clean_banned_phrase_terms(collected["profile_author_stance"]))
    for phrase in banned_phrases[:30]:
        if len(phrase) <= 40:
            author_stance_patterns.append(
                {
                    "name": f"banned_phrase::{phrase[:12]}",
                    "pattern": re.escape(phrase),
                }
            )

    opening_chain_patterns = {}
    explicit_chain_patterns = {
        key.split("::", 1)[1]: value[-1]
        for key, value in collected.items()
        if key.startswith("profile_opening_chain::") and value
    }
    opening_chain_patterns.update(
        {
            key: value
            for key, value in explicit_chain_patterns.items()
            if isinstance(value, str) and value
        }
    )

    explicit_scene_assets = {
        key.split("::", 1)[1]: value
        for key, value in collected.items()
        if key.startswith("profile_scene_asset::") and value
    }
    scene_assets_raw = {
        "public_explosion": normalize_items(
            explicit_scene_assets.get("public_explosion", [])
        )[:30],
        "external_order": normalize_items(
            explicit_scene_assets.get("external_order", [])
        )[:30],
        "consequence_chain": normalize_items(
            explicit_scene_assets.get("consequence_chain", []) + collected["profile_consequence_terms"]
        )[:30],
    }
    scene_assets = {
        key: clean_scene_asset_terms(value)
        for key, value in scene_assets_raw.items()
        if clean_scene_asset_terms(value)
    }
    fallback_style_assets_raw: dict[str, list[str]] = defaultdict(list)
    explicit_style_assets_raw: dict[str, list[str]] = defaultdict(list)
    for key, value in collected.items():
        if key.startswith("style_asset::"):
            fallback_style_assets_raw[key.split("::", 1)[1]].extend(value)
        if key.startswith("profile_style_asset::"):
            explicit_style_assets_raw[key.split("::", 1)[1]].extend(value)
    clause_asset_keys = {"character_bias", "dialogue_bridges"}
    style_assets: dict[str, list[str]] = {}
    object_pressure_cleaner = lambda items: clean_object_pressure_terms(
        items,
        dynamic_object_terms,
    )
    for key in STYLE_ASSET_KEYS:
        style_assets[key] = merge_style_asset_terms(
            explicit_style_assets_raw.get(key, []),
            fallback_style_assets_raw.get(key, []),
            preserve_commas=key in clause_asset_keys,
            allow_short=key == "character_bias",
            relaxed_fallback=key == "opening_hooks",
            explicit_cleaner=object_pressure_cleaner if key == "object_pressure" else None,
            fallback_cleaner=object_pressure_cleaner if key == "object_pressure" else None,
        )
    if "opening_hooks" in style_assets:
        style_assets["opening_hooks"] = [
            item for item in style_assets["opening_hooks"]
            if item not in opening_hook_blacklist and len(item.strip()) > 2
        ]
    source_text = collect_original_source_text(sources)
    if source_text:
        style_assets = {
            key: [item for item in items if item in source_text]
            for key, items in style_assets.items()
        }
    derived_patterns = normalize_items(collected["profile_derived_patterns"])

    migration_assets = {
        key.split("::", 1)[1]: clean_explicit_style_asset_terms(value)
        for key, value in collected.items()
        if key.startswith("profile_migration_asset::") and clean_explicit_style_asset_terms(value)
    }

    bridge_rules = merge_bridge_rule_lists(bridge_rules)

    high_risk_layers = {
        key.split("::", 1)[1]: normalize_items(value)
        for key, value in collected.items()
        if key.startswith("profile_high_risk_layer::") and normalize_items(value)
    }

    source_noise_risk: dict[str, object] = {}
    if collected["profile_source_noise_level"]:
        counts: dict[str, int] = defaultdict(int)
        for level in collected["profile_source_noise_level"]:
            counts[level] += 1
        source_noise_risk["level"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    if collected["profile_source_noise_signals"]:
        source_noise_risk["signals"] = normalize_items(collected["profile_source_noise_signals"])

    bridge_safety_warning: dict[str, object] = {}
    if collected["profile_bridge_safety_summary"]:
        bridge_safety_warning["summary"] = collected["profile_bridge_safety_summary"][0]
    if collected["profile_bridge_safety_risky"]:
        bridge_safety_warning["risky_bridges"] = normalize_items(collected["profile_bridge_safety_risky"])
    if collected["profile_bridge_safety_why"]:
        bridge_safety_warning["why_original_not_processed"] = normalize_items(collected["profile_bridge_safety_why"])
    if collected["profile_bridge_safety_route"]:
        counts: dict[str, int] = defaultdict(int)
        for route in collected["profile_bridge_safety_route"]:
            counts[route] += 1
        bridge_safety_warning["rewrite_route"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    story_guardrails: dict[str, object] = {}
    face_prefix = "profile_story_guardrail::character_face_split::"
    face_out = {
        key.split(face_prefix, 1)[1]: normalize_items(value)[
            :GUARDRAIL_ITEM_LIMITS.get(key.split(face_prefix, 1)[1], 4)
        ]
        for key, value in collected.items()
        if key.startswith(face_prefix) and normalize_items(value)
    }
    consequence_prefix = "profile_story_guardrail::consequence_structure::"
    consequence_out = {
        key.split(consequence_prefix, 1)[1]: normalize_items(value)[
            :GUARDRAIL_ITEM_LIMITS.get(key.split(consequence_prefix, 1)[1], 4)
        ]
        for key, value in collected.items()
        if key.startswith(consequence_prefix) and normalize_items(value)
    }
    if face_out:
        story_guardrails["character_face_split"] = face_out
    if consequence_out:
        story_guardrails["consequence_structure"] = consequence_out

    profile = {
        "meta": {
            "name": name,
            "mode": "source_dirs",
            "source_count": len(sources),
            "sources": [str(path) for path in sources],
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        "opening_signal_groups": opening_signal_groups,
        "opening_signal_group_threshold": 6,
        "opening_chain_patterns": opening_chain_patterns,
        "opening_chain_threshold": 4,
        "author_stance_patterns": author_stance_patterns,
        "author_stance_threshold": 2,
        "banned_phrases": banned_phrases,
        "banned_regex": [],
        "bridge_rules": bridge_rules,
        "scene_assets": scene_assets,
        "style_assets": style_assets,
        "derived_patterns": derived_patterns,
        "migration_assets": migration_assets,
    }
    if collected["profile_risk_layer_type"]:
        counts: dict[str, int] = defaultdict(int)
        for item in collected["profile_risk_layer_type"]:
            counts[item] += 1
        profile["risk_layer_type"] = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    if high_risk_layers:
        profile["high_risk_layers"] = high_risk_layers
    if source_noise_risk:
        profile["source_noise_risk"] = source_noise_risk
    if bridge_safety_warning:
        profile["bridge_safety_warning"] = bridge_safety_warning
    if story_guardrails:
        profile["story_guardrails"] = story_guardrails
    sample_grading: dict[str, object] = {}
    if collected["sample_level"]:
        severity_rank = {"C类负样本": 3, "B类骨架样本": 2, "A类正样本": 1}
        sample_grading["level"] = sorted(
            normalize_items(collected["sample_level"]),
            key=lambda item: (-severity_rank.get(item, 0), item),
        )[0]
    if collected["sample_dna_usable"]:
        if any("不可" in item for item in collected["sample_dna_usable"]):
            sample_grading["dna_usable"] = "不可"
        elif any("部分" in item for item in collected["sample_dna_usable"]):
            sample_grading["dna_usable"] = "部分可"
        else:
            sample_grading["dna_usable"] = collected["sample_dna_usable"][0]
    if collected["sample_summary"]:
        sample_grading["summary"] = collected["sample_summary"][0]
    if collected["sample_source_score_judgement"]:
        sample_grading["source_score_judgement"] = collected["sample_source_score_judgement"][0]
    if collected["sample_source_score_overall"]:
        sample_grading["source_score_overall"] = collected["sample_source_score_overall"][0]
    if collected["sample_source_score_policy"]:
        sample_grading["source_score_policy"] = collected["sample_source_score_policy"][0]
    if collected["sample::source_score_high_blocks"]:
        sample_grading["source_score_high_blocks"] = normalize_items(
            collected["sample::source_score_high_blocks"]
        )
    for key in ("learnable_layers", "forbidden_layers", "misuse_warnings", "evidence", "usage_guidance"):
        bucket = collected.get(f"sample::{key}", [])
        if bucket:
            sample_grading[key] = normalize_items(bucket)
    for key in SAMPLE_LAYER_GRADE_KEYS:
        bucket = collected.get(f"sample::{key}", [])
        values = [value.upper() for value in bucket if value.upper() in {"A", "B", "C"}]
        if values:
            sample_grading[key] = values[0]
    for key in SAMPLE_USAGE_LAYER_KEYS:
        bucket = collected.get(f"sample::{key}", [])
        if bucket:
            sample_grading[key] = normalize_items(bucket)
    usage_guidance: dict[str, str] = {}
    for bucket_key, label in (
        ("sample_usage_write", "写新稿时怎么用这本"),
        ("sample_usage_merge", "融合写作时怎么用这本"),
        ("sample_usage_deslop", "去 AI 味时怎么用这本"),
        ("sample_usage_noninherit", "哪些内容只可参考、不可继承"),
    ):
        if collected[bucket_key]:
            usage_guidance[label] = collected[bucket_key][0]
    if usage_guidance:
        sample_grading["usage_guidance"] = usage_guidance
    final_verdict: dict[str, object] = {}
    if collected["sample_allow_dna"]:
        final_verdict["allow_dna"] = "否" if any(item in ("否", "不可") for item in collected["sample_allow_dna"]) else collected["sample_allow_dna"][0]
    if collected["sample_allow_bridge_merge"]:
        final_verdict["allow_bridge_merge"] = "否" if any(item in ("否", "不可") for item in collected["sample_allow_bridge_merge"]) else collected["sample_allow_bridge_merge"][0]
    if collected["sample_negative_only"]:
        final_verdict["negative_only"] = "是" if any(item in ("是", "仅供反面规则", "仅供负面规则") for item in collected["sample_negative_only"]) else collected["sample_negative_only"][0]
    if collected["sample_tags"]:
        final_verdict["tags"] = normalize_items(collected["sample_tags"])
    if final_verdict:
        sample_grading["final_verdict"] = final_verdict
    if sample_grading:
        profile["sample_grading"] = sample_grading
    sample_source_buckets = build_sample_source_buckets(sample_source_entries)
    if sample_source_buckets:
        profile["sample_source_buckets"] = sample_source_buckets
    return profile


def merge_profiles(profile_paths: list[Path], name: str) -> dict:
    profiles = [json.loads(read_text(path)) for path in profile_paths]
    opening_signal_groups = merge_dict_of_lists(profiles, "opening_signal_groups")
    scene_assets = merge_dict_of_lists(profiles, "scene_assets")
    style_assets = merge_dict_of_lists(profiles, "style_assets")
    migration_assets = merge_dict_of_lists(profiles, "migration_assets")
    source_entries = [
        build_sample_source_entry(profile, path)
        for profile, path in zip(profiles, profile_paths)
    ]
    source_entries = [entry for entry in source_entries if entry]
    merged = {
        "meta": {
            "name": name,
            "mode": "merged_profiles",
            "source_count": len(profile_paths),
            "sources": [str(path) for path in profile_paths],
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        "opening_signal_groups": opening_signal_groups,
        "opening_signal_group_threshold": max(
            [int(p.get("opening_signal_group_threshold", 6)) for p in profiles] or [6]
        ),
        "opening_chain_patterns": {
            key: value
            for profile in profiles
            for key, value in profile.get("opening_chain_patterns", {}).items()
            if isinstance(key, str) and isinstance(value, str)
        },
        "opening_chain_threshold": max(
            [int(p.get("opening_chain_threshold", 4)) for p in profiles] or [4]
        ),
        "author_stance_patterns": merge_list_of_dicts(
            profiles, "author_stance_patterns", "name"
        ),
        "author_stance_threshold": max(
            [int(p.get("author_stance_threshold", 2)) for p in profiles] or [2]
        ),
        "banned_phrases": merge_string_lists(profiles, "banned_phrases"),
        "banned_regex": merge_string_lists(profiles, "banned_regex"),
        "bridge_rules": merge_bridge_rule_lists(
            *[
                profile.get("bridge_rules", [])
                for profile in profiles
                if isinstance(profile.get("bridge_rules", []), list)
            ]
        ),
        "scene_assets": scene_assets,
        "style_assets": style_assets,
        "derived_patterns": merge_string_lists(profiles, "derived_patterns"),
        "migration_assets": migration_assets,
    }
    risk_layer_type = merge_risk_layer_type(profiles)
    if risk_layer_type:
        merged["risk_layer_type"] = risk_layer_type
    high_risk_layers = merge_high_risk_layers(profiles)
    if high_risk_layers:
        merged["high_risk_layers"] = high_risk_layers
    source_noise_risk = merge_source_noise_risk(profiles)
    if source_noise_risk:
        merged["source_noise_risk"] = source_noise_risk
    bridge_safety_warning = merge_bridge_safety_warning(profiles)
    if bridge_safety_warning:
        merged["bridge_safety_warning"] = bridge_safety_warning
    story_guardrails = merge_story_guardrails(profiles)
    if story_guardrails:
        merged["story_guardrails"] = story_guardrails
    sample_grading = merge_sample_grading(profiles)
    sample_source_buckets = build_sample_source_buckets(source_entries)
    if sample_grading and sample_source_buckets:
        raw_level = sample_grading.get("level")
        raw_dna_usable = sample_grading.get("dna_usable")
        effective_level = sample_source_buckets.get("effective_write_level")
        effective_dna_usable = sample_source_buckets.get("effective_dna_usable")
        effective_allow_dna = sample_source_buckets.get("effective_allow_dna")
        if isinstance(raw_level, str) and raw_level.strip():
            sample_grading["raw_level"] = raw_level
        if isinstance(raw_dna_usable, str) and raw_dna_usable.strip():
            sample_grading["raw_dna_usable"] = raw_dna_usable
        if isinstance(effective_level, str) and effective_level.strip():
            sample_grading["level"] = effective_level
        if isinstance(effective_dna_usable, str) and effective_dna_usable.strip():
            sample_grading["dna_usable"] = effective_dna_usable
        sample_grading["summary"] = (
            f"融合包共 {len(source_entries)} 本来源："
            f"{len(sample_source_buckets.get('positive_dna_sources', []))} 本可做正向 DNA，"
            f"{len(sample_source_buckets.get('skeleton_only_sources', []))} 本只供骨架，"
            f"{len(sample_source_buckets.get('negative_only_sources', []))} 本只进反面规则。"
        )
        sample_grading["final_verdict"] = {
            "allow_dna": effective_allow_dna or "否",
            "allow_bridge_merge": "可" if source_entries else "否",
            "negative_only": "否" if sample_source_buckets.get("positive_dna_sources") else "是",
            "tags": normalize_items(
                [
                    "融合包",
                    f"正样本{len(sample_source_buckets.get('positive_dna_sources', []))}本",
                    f"骨架样本{len(sample_source_buckets.get('skeleton_only_sources', []))}本",
                    f"负样本{len(sample_source_buckets.get('negative_only_sources', []))}本",
                ]
            ),
        }
    if sample_grading:
        merged["sample_grading"] = sample_grading
    if sample_source_buckets:
        merged["sample_source_buckets"] = sample_source_buckets
    return merged


def collect_profiles_from_dirs(profile_dirs: list[Path], profile_name: str) -> list[Path]:
    collected: list[Path] = []
    seen: set[Path] = set()
    for root in profile_dirs:
        if not root.exists():
            raise SystemExit(f"profile 目录不存在: {root}")
        if not root.is_dir():
            raise SystemExit(f"profile 目录不是文件夹: {root}")
        for path in sorted(root.rglob(profile_name)):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            collected.append(resolved)
    return collected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", help="拆书目录，可重复传入")
    parser.add_argument("--merge-profile", action="append", help="已有 profile.json 路径，可重复传入")
    parser.add_argument("--merge-profile-dir", action="append", help="批量搜集 profile 的目录，可重复传入")
    parser.add_argument("--merge-profile-name", default="book.profile.json", help="批量搜集时递归查找的 profile 文件名，默认 book.profile.json")
    parser.add_argument("--name", required=True, help="profile 名称")
    parser.add_argument("--output", required=True, help="输出 json 路径")
    args = parser.parse_args()

    source_mode = bool(args.source)
    merge_mode = bool(args.merge_profile or args.merge_profile_dir)
    if source_mode == merge_mode:
        raise SystemExit("必须二选一：使用 --source 生成，或使用 --merge-profile / --merge-profile-dir 合并。")

    if args.source:
        sources = [Path(item).resolve() for item in args.source]
        for path in sources:
            if not path.exists():
                raise SystemExit(f"源目录不存在: {path}")
        profile = generate_profile_from_sources(sources, args.name)
    else:
        profile_paths: list[Path] = []
        if args.merge_profile:
            profile_paths.extend(Path(item).resolve() for item in args.merge_profile)
        if args.merge_profile_dir:
            merge_dirs = [Path(item).resolve() for item in args.merge_profile_dir]
            profile_paths.extend(collect_profiles_from_dirs(merge_dirs, args.merge_profile_name))
        deduped: list[Path] = []
        seen: set[Path] = set()
        for path in profile_paths:
            if path in seen:
                continue
            seen.add(path)
            deduped.append(path)
        profile_paths = deduped
        if not profile_paths:
            raise SystemExit("没有找到可合并的 profile。")
        for path in profile_paths:
            if not path.exists():
                raise SystemExit(f"profile 不存在: {path}")
        profile = merge_profiles(profile_paths, args.name)

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
