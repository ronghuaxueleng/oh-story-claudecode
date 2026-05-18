#!/usr/bin/env python3
"""按书名/梗概生成首版情节池与大纲种子。"""
import argparse
import json
import re
from pathlib import Path

from search_plot_library import (  # noqa: E402
    PlotNeo4jClient,
    _expand_terms,
    _extract_plot_motifs,
    _extract_query_motifs,
    _is_explicit_numeric_chapter,
    _load_json_plot_sources,
    _safe_chapter_no,
    _score_plot,
)


SITUATION_HINTS = ["流放", "抄家", "逃荒", "废柴", "穿越", "替嫁", "和离", "边疆", "发配", "入狱"]
DRIVER_HINTS = ["系统", "情报", "预警", "日签", "机缘", "复仇", "交易", "面板", "签到", "推演"]
EMOTION_HINTS = ["逆袭", "翻盘", "绝境", "生存", "悬疑", "潜伏", "复仇", "爽感", "压迫", "崛起", "杀机", "危机", "紧绷", "反制", "自救"]
GENERIC_STOPWORDS = {
    "主角", "故事", "小说", "书名", "测试书名", "测试", "一个", "每天", "获得",
    "关键", "信息差", "自己", "他们", "我们", "你们", "因为", "所以", "开始",
}
SITUATION_PATTERNS = [
    r"(流放[\u4e00-\u9fff]{0,4})",
    r"(抄家[\u4e00-\u9fff]{0,4})",
    r"(逃荒[\u4e00-\u9fff]{0,4})",
    r"(边疆[\u4e00-\u9fff]{0,4})",
    r"(废柴[\u4e00-\u9fff]{0,4})",
    r"(入狱[\u4e00-\u9fff]{0,4})",
    r"(替嫁[\u4e00-\u9fff]{0,4})",
    r"(和离[\u4e00-\u9fff]{0,4})",
]
DRIVER_PATTERNS = [
    r"((?:每日|每天|关键)?情报)",
    r"((?:最强|神级|交易|商城)?系统)",
    r"((?:提前|危险)?预警)",
    r"((?:逆天|特殊)?机缘)",
    r"((?:每日|每天)?签到)",
]
DRIVER_CLEAN_PREFIXES = ["解锁", "开启", "获得", "拿到", "绑定", "激活", "拥有", "觉醒", "锁一个", "一个"]
GOAL_HINTS = ["翻盘", "复仇", "崛起", "求生", "自保", "逃生", "夺权", "立足", "逆袭", "复兴", "活下去", "查案", "查清", "破局", "自救"]
OBSTACLE_HINTS = ["追杀", "围攻", "断粮", "压迫", "陷害", "封锁", "赤字", "流放", "抄家", "审判", "灭门", "绝境", "逃荒", "饥荒", "危局", "深宅", "权谋", "杀机", "断水", "内斗"]
OPENING_TEXTURE_WORDS = ["压迫", "求生", "困局", "断粮", "短缺", "追杀", "试探", "围堵", "封锁", "施压", "绝境", "生存"]
MID_TEXTURE_WORDS = ["调查", "布局", "反制", "试探", "联盟", "交易", "周旋", "争夺", "博弈", "推进", "立足", "经营", "交换", "筹码", "拉拢", "试局"]
END_TEXTURE_WORDS = ["反转", "绝境", "真相", "生死", "牺牲", "翻盘", "爆发", "决裂", "追杀", "清算", "摊牌", "揭破", "反杀", "破局"]
SECRET_TEXTURE_WORDS = ["秘密", "线索", "幕后", "身世", "旧案", "真相", "遗物", "失踪", "暗线"]
SECRET_FAMILY_HINTS = {
    "sect": ["祖师", "传承", "失传", "遗物", "叛徒", "旧账", "秘境", "残页", "禁地", "师门", "血脉"],
    "intrigue": ["身世", "旧案", "灭门", "婚书", "遗诏", "庶出", "旧人", "真凶", "证据", "宗卷"],
    "survival": ["水源", "粮仓", "灾因", "疫病", "路线", "隐患", "地图", "旧村", "仓库", "失踪"],
}
TITLE_TRAIL_CUTS = ["靠", "我靠", "凭", "带着", "每天", "获得", "解锁", "养活", "重振", "躲开", "入局"]
INTRIGUE_OPENING_WORDS = ["替嫁", "深宅", "权谋", "后宅", "嫡庶", "内斗", "婚约", "灭门", "入局"]
INTRIGUE_END_WORDS = ["揭破", "清算", "反杀", "翻盘", "摊牌", "失势", "禁足", "问罪", "灭门"]
SURVIVAL_OPENING_WORDS = ["逃荒", "断粮", "饥荒", "流民", "绝境", "求生", "逃难", "村民", "粮药"]
SURVIVAL_MID_WORDS = ["安置", "换粮", "找水", "分粮", "带路", "落脚", "扎营", "筹粮", "药材", "路线"]
SURVIVAL_END_WORDS = ["守住", "翻盘", "反杀", "保全", "突围", "熬过", "撑住", "绝处逢生"]
SECT_CONTEXT_WORDS = ["宗门", "掌门", "长老", "弟子", "外门", "内门", "资源", "灵石", "矿脉", "供奉", "势力"]
INTRIGUE_CONTEXT_WORDS = ["替嫁", "深宅", "权谋", "后宅", "侧妃", "嫡庶", "婚约", "家族", "禁足", "问罪", "王府"]
SURVIVAL_CONTEXT_WORDS = ["逃荒", "流民", "分粮", "村民", "找水", "扎营", "粮药", "路线", "逃难", "换粮"]


def _extract_terms(text: str, hints: list[str]) -> list[str]:
    found = [word for word in hints if word in text]
    return found[:3]


def _build_keyword_groups(title: str, premise: str) -> dict[str, list[str]]:
    text = f"{title} {premise}".strip()
    situation = _extract_terms(text, SITUATION_HINTS)
    driver = _extract_terms(text, DRIVER_HINTS)
    emotion = _extract_terms(text, EMOTION_HINTS)
    goal = _extract_terms(text, GOAL_HINTS)
    obstacle = _extract_terms(text, OBSTACLE_HINTS)

    groups = {
        "situation_driver": (situation + driver)[:5],
        "situation_emotion": (situation + emotion)[:5],
        "driver_emotion": (driver + emotion)[:5],
        "goal_obstacle": (goal + obstacle)[:5],
    }
    return {
        "situation": situation,
        "driver": driver,
        "emotion": emotion,
        "goal": goal,
        "obstacle": obstacle,
        **groups,
    }


def _extract_phrase(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phrase = match.group(1).strip("，。！？；： ")
            if phrase:
                return phrase
    return ""


def _extract_situation_phrase(text: str) -> str:
    phrase = _extract_phrase(text, SITUATION_PATTERNS)
    if phrase:
        for marker in TITLE_TRAIL_CUTS:
            idx = phrase.find(marker)
            if idx > 0:
                phrase = phrase[:idx]
                break
        phrase = phrase.strip("，。！？；： ")
        return phrase
    for hint in SITUATION_HINTS:
        if hint in text:
            return hint
    return ""


def _clean_driver_phrase(text: str) -> str:
    cleaned = text.strip("，。！？；： ")
    for prefix in DRIVER_CLEAN_PREFIXES:
        if cleaned.startswith(prefix) and len(cleaned) > len(prefix):
            cleaned = cleaned[len(prefix):]
    return cleaned or text


def _extract_first_hit(text: str, hints: list[str]) -> str:
    for hint in hints:
        if hint in text:
            return hint
    return ""


def _pick_first_group_term(term_groups: dict[str, list[str]], key: str) -> str:
    values = [value for value in (term_groups.get(key) or []) if value]
    return values[0] if values else ""


def _derive_emotion(text: str, term_groups: dict[str, list[str]]) -> str:
    obstacle_terms = [term for term in term_groups.get("obstacle", []) if term]
    if any(term in text for term in ["灭门", "追杀", "围攻", "抄家", "审判", "压迫", "封锁", "流放"]):
        return "危机"
    if any(term in text for term in ["断粮", "饥荒", "逃荒", "断水"]):
        return "绝境"
    if any(term in text for term in ["深宅", "权谋", "婚约", "入局", "试探"]):
        return "悬疑"
    if any(term in obstacle_terms for term in ["灭门", "追杀", "围攻", "抄家", "审判", "压迫", "封锁", "流放"]):
        return "危机"
    if any(term in obstacle_terms for term in ["断粮", "饥荒", "逃荒", "断水"]):
        return "绝境"
    if any(term in obstacle_terms for term in ["深宅", "权谋", "婚约", "入局", "试探"]):
        return "悬疑"
    return ""


def _derive_goal(text: str, term_groups: dict[str, list[str]]) -> str:
    if any(term in text for term in ["重振", "复兴", "崛起", "再起", "翻身"]):
        return "复兴"
    if any(term in text for term in ["翻盘", "逆袭", "破局", "反击"]):
        return "破局"
    if any(term in text for term in ["养活", "求生", "活下去", "保命", "自保", "自救", "躲开", "躲过"]):
        return "自救"
    if any(term in text for term in ["查案", "查清", "追查", "查明"]):
        return "查案"
    if any(term in text for term in ["收徒", "纳徒", "收留"]):
        return "立足"
    goal_terms = [term for term in term_groups.get("goal", []) if term]
    if goal_terms:
        return goal_terms[0]
    return ""


def _derive_obstacle(text: str, term_groups: dict[str, list[str]]) -> str:
    if any(term in text for term in ["灭门", "追杀", "围攻", "抄家", "审判", "压迫", "封锁", "流放"]):
        return "危局"
    if any(term in text for term in ["断粮", "饥荒", "断水", "逃荒"]):
        return "绝境"
    if any(term in text for term in ["深宅", "权谋", "婚约", "入局", "试探"]):
        return "暗局"
    obstacle_terms = [term for term in term_groups.get("obstacle", []) if term]
    if obstacle_terms:
        return obstacle_terms[0]
    return ""


def _require_non_empty(value: str, label: str) -> str:
    if not value.strip():
        raise RuntimeError(f"无法稳定抽取{label}，请回退到常规写作流程。")
    return value.strip()


def _group_required_terms(group_name: str, term_groups: dict[str, list[str]]) -> list[str]:
    if group_name == "situation_driver":
        return [*(term_groups.get("situation") or []), *(term_groups.get("driver") or [])]
    if group_name == "situation_emotion":
        return [*(term_groups.get("situation") or []), *(term_groups.get("emotion") or [])]
    if group_name == "driver_emotion":
        return [*(term_groups.get("driver") or []), *(term_groups.get("emotion") or [])]
    if group_name == "goal_obstacle":
        return [*(term_groups.get("goal") or []), *(term_groups.get("obstacle") or [])]
    return []


def _plot_text(plot: dict) -> str:
    return " ".join([
        plot.get("plot_name") or plot.get("name") or "",
        plot.get("plot_type") or plot.get("type") or "",
        plot.get("core_conflict") or "",
        plot.get("emotional_arc") or "",
        " ".join(plot.get("themes") or []),
    ])


def _group_parts(group_name: str, term_groups: dict[str, list[str]]) -> list[list[str]]:
    if group_name == "situation_driver":
        return [
            [term for term in term_groups.get("situation", []) if term],
            [term for term in term_groups.get("driver", []) if term],
        ]
    if group_name == "situation_emotion":
        return [
            [term for term in term_groups.get("situation", []) if term],
            [term for term in term_groups.get("emotion", []) if term],
        ]
    if group_name == "driver_emotion":
        return [
            [term for term in term_groups.get("driver", []) if term],
            [term for term in term_groups.get("emotion", []) if term],
        ]
    if group_name == "goal_obstacle":
        return [
            [term for term in term_groups.get("goal", []) if term],
            [term for term in term_groups.get("obstacle", []) if term],
        ]
    return []


def _passes_group_gate(plot: dict, group_name: str, term_groups: dict[str, list[str]]) -> bool:
    part_groups = _group_parts(group_name, term_groups)
    if not part_groups or any(not part for part in part_groups):
        return False
    text = _plot_text(plot)
    return all(any(term in text for term in part) for part in part_groups)


def _has_opening_texture(text: str) -> bool:
    return any(word in text for word in OPENING_TEXTURE_WORDS + INTRIGUE_OPENING_WORDS + SURVIVAL_OPENING_WORDS)


def _has_situation_hit(text: str, term_groups: dict[str, list[str]]) -> bool:
    situation_terms = [term for term in term_groups.get("situation", []) if term]
    return any(term in text for term in situation_terms)


def _has_driver_hit(text: str, term_groups: dict[str, list[str]]) -> bool:
    driver_terms = [term for term in term_groups.get("driver", []) if term]
    return any(term in text for term in driver_terms)


def _has_group_term_hit(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms if term)


def _matches_mid_progression_proxy(text: str, term_groups: dict[str, list[str]]) -> bool:
    if not any(word in text for word in MID_TEXTURE_WORDS + SURVIVAL_MID_WORDS):
        return False
    if _has_driver_hit(text, term_groups):
        return True
    return any(word in text for word in ["交易", "联盟", "调查", "争夺", "布局", "周旋", "交换", "筹码", "拉拢", "经营", *SURVIVAL_MID_WORDS])


def _matches_opening_proxy(text: str, term_groups: dict[str, list[str]]) -> bool:
    if not _has_opening_texture(text):
        return False
    if _has_situation_hit(text, term_groups) or _has_driver_hit(text, term_groups):
        return True
    obstacle_terms = term_groups.get("obstacle") or []
    emotion_terms = term_groups.get("emotion") or []
    if _has_group_term_hit(text, obstacle_terms) or _has_group_term_hit(text, emotion_terms):
        return True
    return any(word in text for word in INTRIGUE_OPENING_WORDS + SURVIVAL_OPENING_WORDS)


def _matches_end_proxy(text: str, term_groups: dict[str, list[str]]) -> bool:
    if not any(word in text for word in END_TEXTURE_WORDS + INTRIGUE_END_WORDS + SURVIVAL_END_WORDS):
        return False
    if _has_driver_hit(text, term_groups):
        return True
    goal_terms = term_groups.get("goal") or []
    obstacle_terms = term_groups.get("obstacle") or []
    if _has_group_term_hit(text, goal_terms) or _has_group_term_hit(text, obstacle_terms):
        return True
    return any(word in text for word in INTRIGUE_END_WORDS + SURVIVAL_END_WORDS)


def _matches_long_term_secret(text: str, term_groups: dict[str, list[str]]) -> bool:
    if not any(word in text for word in SECRET_TEXTURE_WORDS):
        return _matches_long_term_secret_by_family(text, term_groups)
    long_term_signals = ["幕后", "身世", "旧案", "失踪", "遗物", "暗线", "真相", "秘密", "婚约", "血脉", "旧人"]
    if any(word in text for word in long_term_signals):
        return True
    if _matches_long_term_secret_by_family(text, term_groups):
        return True
    if _has_situation_hit(text, term_groups) and any(word in text for word in ["真相", "失踪", "遗物", "幕后"]):
        return True
    return False


def _is_secret_display_candidate(item: dict, term_groups: dict[str, list[str]]) -> bool:
    text = f"{item.get('plot_name') or ''} {item.get('core_conflict') or ''}"
    if not _matches_long_term_secret(text, term_groups):
        return False
    signature = item.get("cluster_signature") or ""
    if "tex:mid" in signature and not any(
        word in text
        for word in ["幕后", "身世", "旧案", "失踪", "遗物", "祖师", "传承", "婚书", "水源", "粮仓", "灾因"]
    ):
        return False
    return True


def _detect_context_families(term_groups: dict[str, list[str]]) -> set[str]:
    merged = " ".join(
        [
            *(term_groups.get("situation") or []),
            *(term_groups.get("driver") or []),
            *(term_groups.get("emotion") or []),
            *(term_groups.get("goal") or []),
            *(term_groups.get("obstacle") or []),
        ]
    )
    families: set[str] = set()
    if any(word in merged for word in ["宗门", "掌门", "长老", "弟子", "灵石", "矿脉", "废柴"]):
        families.add("sect")
    if any(word in merged for word in ["替嫁", "深宅", "权谋", "后宅", "灭门", "婚约", "自保"]):
        families.add("intrigue")
    if any(word in merged for word in ["逃荒", "绝境", "断粮", "流民", "求生", "签到"]):
        families.add("survival")
    return families


def _secret_family_words(family: str) -> list[str]:
    return SECRET_FAMILY_HINTS.get(family, [])


def _matches_context_family(text: str, family: str) -> bool:
    if family == "sect":
        return any(word in text for word in SECT_CONTEXT_WORDS)
    if family == "intrigue":
        return any(word in text for word in INTRIGUE_CONTEXT_WORDS)
    if family == "survival":
        return any(word in text for word in SURVIVAL_CONTEXT_WORDS)
    return False


def _matches_long_term_secret_by_family(text: str, term_groups: dict[str, list[str]]) -> bool:
    families = _detect_context_families(term_groups)
    if not families:
        return False
    for family in families:
        if any(word in text for word in _secret_family_words(family)):
            return True
    return False


def _context_fit_bonus(text: str, term_groups: dict[str, list[str]]) -> int:
    families = _detect_context_families(term_groups)
    if not families:
        return 0
    hits = sum(1 for family in families if _matches_context_family(text, family))
    return min(6, hits * 3)


def _context_match_tier(text: str, base_score: int, term_groups: dict[str, list[str]]) -> str:
    families = _detect_context_families(term_groups)
    if not families:
        return "strong_match"
    hits = sum(1 for family in families if _matches_context_family(text, family))
    if hits >= 1:
        return "strong_match"
    if base_score >= 12:
        return "adaptable_match"
    return "off_topic"


def _conflict_signature(item: dict, term_groups: dict[str, list[str]]) -> str:
    text = f"{item.get('plot_name') or ''} {item.get('core_conflict') or ''}"
    tokens: list[str] = []
    for bucket in ("situation", "driver", "emotion", "goal", "obstacle"):
        hits = [term for term in term_groups.get(bucket, []) if term and term in text]
        if hits:
            tokens.append(f"{bucket}:{'|'.join(hits[:2])}")
    if any(word in text for word in OPENING_TEXTURE_WORDS + INTRIGUE_OPENING_WORDS + SURVIVAL_OPENING_WORDS):
        tokens.append("tex:opening")
    if any(word in text for word in MID_TEXTURE_WORDS + SURVIVAL_MID_WORDS):
        tokens.append("tex:mid")
    if any(word in text for word in END_TEXTURE_WORDS + INTRIGUE_END_WORDS + SURVIVAL_END_WORDS):
        tokens.append("tex:end")
    if any(word in text for word in SECRET_TEXTURE_WORDS):
        tokens.append("tex:secret")
    if not tokens:
        start = _safe_chapter_no(item.get("start_chapter"))
        tokens.append(f"fallback:{item.get('group') or 'g'}:{start // 10}")
    return " / ".join(tokens)


def _merge_reasons(*reason_lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen = set()
    for reasons in reason_lists:
        for reason in reasons:
            if reason not in seen:
                seen.add(reason)
                merged.append(reason)
    return merged


def _dedupe_candidate_clusters(candidates: list[dict], term_groups: dict[str, list[str]]) -> list[dict]:
    clusters: dict[str, dict] = {}
    for item in candidates:
        signature = _conflict_signature(item, term_groups)
        current = clusters.get(signature)
        if current is None:
            clone = dict(item)
            clone["cluster_signature"] = signature
            clusters[signature] = clone
            continue
        if item.get("score", 0) > current.get("score", 0):
            replacement = dict(item)
            replacement["cluster_signature"] = signature
            replacement["match_reasons"] = _merge_reasons(item.get("match_reasons") or [], current.get("match_reasons") or [])
            clusters[signature] = replacement
        else:
            current["match_reasons"] = _merge_reasons(current.get("match_reasons") or [], item.get("match_reasons") or [])
    return sorted(
        clusters.values(),
        key=lambda x: (-x.get("score", 0), str(x.get("novel_id")), _safe_chapter_no(x.get("start_chapter"))),
    )


def _pick_bucket_items(
    ordered_items: list[dict],
    *,
    limit: int,
    used_signatures: set[str] | None = None,
    avoid_signatures: set[str] | None = None,
) -> list[dict]:
    chosen: list[dict] = []
    local_signatures = set()
    external_signatures = used_signatures or set()
    blocked_signatures = avoid_signatures or set()
    for item in ordered_items:
        signature = item.get("cluster_signature") or ""
        if signature in local_signatures or signature in external_signatures or signature in blocked_signatures:
            continue
        chosen.append(item)
        local_signatures.add(signature)
        if len(chosen) >= limit:
            break
    if len(chosen) < limit:
        for item in ordered_items:
            signature = item.get("cluster_signature") or ""
            if signature in local_signatures:
                continue
            chosen.append(item)
            local_signatures.add(signature)
            if len(chosen) >= limit:
                break
    return chosen


def _collect_candidates(term_groups: dict[str, list[str]], limit_per_group: int, json_library: str = "") -> list[dict]:
    candidates = []
    seen = set()
    structure_terms = [
        *(term_groups.get("situation") or []),
        *(term_groups.get("driver") or []),
        *(term_groups.get("emotion") or []),
        *(term_groups.get("goal") or []),
        *(term_groups.get("obstacle") or []),
    ]
    query_motifs = _extract_query_motifs(structure_terms)
    if json_library:
        plots = _load_json_plot_sources(json_library)
        novels = [{"novel_id": "__json__", "title": "json"}]
    else:
        neo4j = PlotNeo4jClient()
        if not neo4j.is_available():
            raise RuntimeError("Neo4j 不可用，且未指定 --json-library。")
        novels = []
        plots = None

    group_order = ["situation_driver", "situation_emotion", "driver_emotion", "goal_obstacle"]
    group_window_multiplier = {
        "situation_driver": 220,
        "driver_emotion": 220,
        "situation_emotion": 140,
        "goal_obstacle": 140,
    }
    for group_name in group_order:
        terms = [t for t in term_groups.get(group_name, []) if t]
        if not terms:
            continue
        expanded = _expand_terms(terms)
        group_hits = []
        if json_library:
            for plot in plots or []:
                if not _passes_group_gate(plot, group_name, term_groups):
                    continue
                plot_motifs = _extract_plot_motifs(plot)
                if plot_motifs - query_motifs:
                    continue
                score, reasons = _score_plot(plot, expanded, structure_terms=structure_terms)
                if score > 0:
                    group_hits.append({
                        "group": group_name,
                        "novel_id": plot.get("novel_id") or "",
                        "plot_name": plot.get("plot_name") or "",
                        "plot_type": plot.get("plot_type") or "",
                        "core_conflict": plot.get("core_conflict") or "",
                        "emotional_arc": plot.get("emotional_arc") or "",
                        "start_chapter": plot.get("start_chapter"),
                        "end_chapter": plot.get("end_chapter"),
                        "score": score,
                        "match_reasons": reasons[:5],
                    })
        else:
            neo4j = PlotNeo4jClient()
            db_candidates = neo4j.search_candidate_plots(
                terms=expanded + structure_terms,
                limit=max(limit_per_group * group_window_multiplier.get(group_name, 120), 800),
            )
            for plot in db_candidates:
                plot_motifs = _extract_plot_motifs(plot)
                if plot_motifs - query_motifs:
                    continue
                plot_text = _plot_text(plot)
                passed_gate = _passes_group_gate(plot, group_name, term_groups)
                proxy_mid_hit = group_name in {"situation_driver", "driver_emotion"} and _matches_mid_progression_proxy(plot_text, term_groups)
                if not passed_gate and not proxy_mid_hit:
                    continue
                score, reasons = _score_plot(plot, expanded, structure_terms=structure_terms)
                tier = _context_match_tier(plot_text, score, term_groups)
                if tier == "off_topic":
                    continue
                context_bonus = _context_fit_bonus(plot_text, term_groups)
                score += context_bonus
                if score > 0:
                    if proxy_mid_hit and not passed_gate:
                        score += 3
                        reasons = ["中段代理命中", *reasons]
                    reasons = [f"语境层级:{tier}", *reasons]
                    if context_bonus > 0:
                        reasons = [f"题材语境贴合+{context_bonus}", *reasons]
                    group_hits.append({
                        "group": group_name,
                        "match_tier": tier,
                        "novel_id": plot.get("novel_id") or "",
                        "plot_name": plot.get("name") or "",
                        "plot_type": plot.get("type") or "",
                        "core_conflict": plot.get("core_conflict") or "",
                        "emotional_arc": plot.get("emotional_arc") or "",
                        "start_chapter": plot.get("start_chapter"),
                        "end_chapter": plot.get("end_chapter"),
                        "score": score,
                        "match_reasons": reasons[:5],
                    })

        group_hits.sort(key=lambda x: (-x["score"], str(x["novel_id"]), _safe_chapter_no(x["start_chapter"])))
        strong_hits = [hit for hit in group_hits if hit.get("match_tier") == "strong_match"]
        adaptable_hits = [hit for hit in group_hits if hit.get("match_tier") == "adaptable_match"]
        selected_hits = strong_hits[:limit_per_group]
        if len(selected_hits) < limit_per_group:
            remaining = limit_per_group - len(selected_hits)
            selected_hits.extend(adaptable_hits[:remaining])
        for hit in selected_hits:
            key = (hit["novel_id"], hit["plot_name"], _safe_chapter_no(hit["start_chapter"]))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(hit)
    return _dedupe_candidate_clusters(candidates, term_groups)


def _bucketize(candidates: list[dict], term_groups: dict[str, list[str]]) -> dict[str, list[dict]]:
    buckets = {
        "opening_hooks": [],
        "mid_progressions": [],
        "volume_end_hooks": [],
        "long_term_secrets": [],
    }
    opening_terms = [
        *(term_groups.get("situation") or []),
        *(term_groups.get("driver") or []),
    ]
    for item in candidates:
        start = _safe_chapter_no(item.get("start_chapter"))
        end_is_numeric = _is_explicit_numeric_chapter(item.get("end_chapter"))
        name = item.get("plot_name") or ""
        conflict = item.get("core_conflict") or ""
        text = f"{name} {conflict}"
        if (
            start <= 20
            and end_is_numeric
            and (
                (any(term in text for term in opening_terms if term) and _has_situation_hit(text, term_groups))
                or _matches_opening_proxy(text, term_groups)
            )
        ):
            buckets["opening_hooks"].append(item)
        if end_is_numeric and _is_secret_display_candidate(item, term_groups):
            buckets["long_term_secrets"].append(item)
        if (
            end_is_numeric
            and start >= 2
            and any(word in text for word in MID_TEXTURE_WORDS + SURVIVAL_MID_WORDS)
            and (
                _has_driver_hit(text, term_groups)
                or any(word in text for word in ["交易", "联盟", "调查", "争夺", "布局", "周旋", "交换", "筹码", "拉拢", *SURVIVAL_MID_WORDS])
            )
        ):
            buckets["mid_progressions"].append(item)
        if (
            end_is_numeric
            and _matches_end_proxy(text, term_groups)
            and not (
                start <= 6
                and any(word in text for word in ["求生", "压迫", "困局", "断粮", "流放"])
                and not any(word in text for word in ["真相", "反转", "翻盘", "摊牌", "清算", "揭破"])
            )
        ):
            buckets["volume_end_hooks"].append(item)
        if end_is_numeric and _matches_long_term_secret(text, term_groups):
            buckets["long_term_secrets"].append(item)

    for key in buckets:
        dedup = []
        seen = set()
        for item in buckets[key]:
            uniq = (item["novel_id"], item["plot_name"])
            if uniq in seen:
                continue
            seen.add(uniq)
            dedup.append(item)
        buckets[key] = sorted(
            dedup,
            key=lambda x: (-x.get("score", 0), str(x.get("novel_id")), _safe_chapter_no(x.get("start_chapter"))),
        )

    used_signatures: set[str] = set()
    opening = _pick_bucket_items(buckets["opening_hooks"], limit=5, used_signatures=used_signatures)
    used_signatures.update(item.get("cluster_signature") or "" for item in opening)
    middle = _pick_bucket_items(buckets["mid_progressions"], limit=5, used_signatures=used_signatures)
    used_signatures.update(item.get("cluster_signature") or "" for item in middle)
    secrets = _pick_bucket_items(
        buckets["long_term_secrets"],
        limit=5,
        used_signatures=used_signatures,
        avoid_signatures={item.get("cluster_signature") or "" for item in middle},
    )
    used_signatures.update(item.get("cluster_signature") or "" for item in secrets)
    ending = _pick_bucket_items(
        buckets["volume_end_hooks"],
        limit=5,
        used_signatures=used_signatures,
        avoid_signatures={item.get("cluster_signature") or "" for item in opening},
    )

    buckets["opening_hooks"] = opening
    buckets["long_term_secrets"] = secrets
    buckets["mid_progressions"] = middle
    buckets["volume_end_hooks"] = ending
    return buckets


def _pick_terms(term_groups: dict[str, list[str]], key: str) -> str:
    values = [x for x in term_groups.get(key, []) if x]
    if values:
        return "、".join(values[:2])
    return ""


def _summarize_items(items: list[dict], limit: int = 2) -> list[str]:
    summaries: list[str] = []
    for item in items[:limit]:
        name = item.get("plot_name") or "未命名情节"
        conflict = item.get("core_conflict") or item.get("emotional_arc") or ""
        if conflict:
            summaries.append(f"{name}：{conflict}")
        else:
            summaries.append(name)
    return summaries


def _dedupe_summaries(items: list[str], limit: int = 2) -> list[str]:
    result: list[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _format_reference_item(item: dict) -> str:
    name = item.get("plot_name") or "未命名情节"
    conflict = item.get("core_conflict") or item.get("emotional_arc") or ""
    label = "可改编参考：" if item.get("match_tier") == "adaptable_match" else ""
    base = f"{name}：{conflict}" if conflict else name
    return f"{label}{base}"


def _summarize_items_by_tier(items: list[dict], limit: int = 2) -> list[str]:
    strong_items = [item for item in items if item.get("match_tier") == "strong_match"]
    adaptable_items = [item for item in items if item.get("match_tier") == "adaptable_match"]
    ordered = strong_items + adaptable_items
    return _dedupe_summaries([_format_reference_item(item) for item in ordered], limit=limit)


def _build_outline_seed(title: str, premise: str, term_groups: dict[str, list[str]], buckets: dict[str, list[dict]]) -> dict:
    merged_text = f"{title} {premise}".strip()
    situation = _extract_situation_phrase(merged_text)
    driver = _extract_phrase(merged_text, DRIVER_PATTERNS)
    driver = _clean_driver_phrase(driver)
    emotion = _extract_first_hit(merged_text, EMOTION_HINTS) or _pick_first_group_term(term_groups, "emotion") or _derive_emotion(merged_text, term_groups)
    goal = _extract_first_hit(merged_text, GOAL_HINTS) or _pick_first_group_term(term_groups, "goal") or _derive_goal(merged_text, term_groups)
    obstacle = _extract_first_hit(merged_text, OBSTACLE_HINTS) or _pick_first_group_term(term_groups, "obstacle") or _derive_obstacle(merged_text, term_groups)

    situation = _require_non_empty(situation, "处境")
    driver = _require_non_empty(driver, "驱动")
    emotion = _require_non_empty(emotion, "情绪")
    goal = _require_non_empty(goal, "目标")
    obstacle = _require_non_empty(obstacle, "阻碍")

    opening_items = buckets.get("opening_hooks") or []
    mid_items = buckets.get("mid_progressions") or []
    end_items = buckets.get("volume_end_hooks") or []
    secret_items = buckets.get("long_term_secrets") or []

    opening_refs = _summarize_items_by_tier(opening_items, limit=2)
    mid_refs = _summarize_items_by_tier(mid_items, limit=2)
    end_refs = _summarize_items_by_tier(end_items, limit=2)
    secret_refs = _summarize_items_by_tier(secret_items, limit=2)

    opening_pull = opening_refs[0] if opening_refs else ""
    secret_pull = secret_refs[0] if secret_refs else ""
    core_lines = [
        f"外部困局线：开篇先把“{situation}”压实，主角必须先活下来、站住脚，才有资格谈后续扩张。",
        f"驱动破局线：主角手里真正能改变局势的不是蛮力，而是“{driver}”带来的先手与判断差。",
        f"长期悬念线：第一卷不能只停留在“{emotion}”，还要把“{secret_pull or '更大秘密'}”这类后手压进主线，逼出中后期回收。",
    ]

    volume_one_conflict = f"第一卷主冲突不是单纯求生，而是“{situation}”下的立足权争夺。主角要靠“{driver}”抢到第一块筹码，证明自己不是待宰对象，而是能改局的人。"
    if opening_pull:
        volume_one_conflict += f" 开局可参考的冲突质感：{opening_pull}"
    if secret_pull:
        volume_one_conflict += f" 长线秘密种子：{secret_pull}"

    thirty_chapter_rhythm = [
        {
            "range": "1-3",
            "goal": f"先用高压事件把“{situation}”砸实，再让主角用“{driver}”完成第一次小破局，证明这不是纯挨打开局。",
            "reference_plots": _summarize_items_by_tier(opening_items, limit=2),
        },
        {
            "range": "4-10",
            "goal": "建立初始班底、落脚点或交换关系，让主角第一次把局势从求生改成反制，并开始拉出自己的小盘子。",
            "reference_plots": _summarize_items_by_tier(opening_items + mid_items[:1], limit=3),
        },
        {
            "range": "11-20",
            "goal": "把局部破局升级成阶段性对抗，引入更具体的规则压力、资源争夺或势力博弈，让主角付出代价也拿到更大筹码。",
            "reference_plots": _summarize_items_by_tier(mid_items, limit=2),
        },
        {
            "range": "21-30",
            "goal": f"第一卷末段必须交付一次明确的“{emotion}”体验，同时把更大的秘密、后台势力或下一卷危机抛出来。",
            "reference_plots": _summarize_items_by_tier(end_items + secret_items[:1], limit=3),
        },
    ]

    return {
        "title": title,
        "premise": premise,
        "core_lines": core_lines,
        "volume_one_conflict": volume_one_conflict,
        "thirty_chapter_rhythm": thirty_chapter_rhythm,
        "reference_focus": {
            "opening_hooks": opening_refs,
            "mid_progressions": mid_refs,
            "volume_end_hooks": end_refs,
            "long_term_secrets": secret_refs,
        },
        "seed_phrases": {
            "situation": situation,
            "driver": driver,
            "emotion": emotion,
            "goal": goal,
            "obstacle": obstacle,
            "opening_pull": opening_pull,
            "secret_pull": secret_pull,
        },
    }


def _format_pool_markdown(result: dict) -> str:
    lines = [
        "# 情节库参考",
        "",
        "> 由 story-plot-extractor/search-for-outline 自动生成",
        "",
        "## 项目信息",
        "",
        f"- 书名：{result.get('title') or ''}",
        f"- 一句话梗概：{result.get('premise') or ''}",
        "",
        "## 题材母题",
        "",
        f"- 处境词：{', '.join(result['keyword_groups'].get('situation') or [])}",
        f"- 驱动词：{', '.join(result['keyword_groups'].get('driver') or [])}",
        f"- 情绪词：{', '.join(result['keyword_groups'].get('emotion') or [])}",
        "",
        "## 检索词",
        "",
        f"- 第一组（处境+驱动）：{', '.join(result['keyword_groups']['search_groups'].get('situation_driver') or [])}",
        f"- 第二组（处境+情绪）：{', '.join(result['keyword_groups']['search_groups'].get('situation_emotion') or [])}",
        f"- 第三组（驱动+情绪）：{', '.join(result['keyword_groups']['search_groups'].get('driver_emotion') or [])}",
        "",
    ]

    section_names = {
        "opening_hooks": "开局桥段",
        "mid_progressions": "中段推进",
        "volume_end_hooks": "卷尾钩子",
        "long_term_secrets": "长线秘密",
    }
    for key, title in section_names.items():
        lines.extend([f"## {title}", ""])
        items = result.get("outline_pool", {}).get(key) or []
        if not items:
            continue
        for item in items:
            lines.append(f"- {item.get('plot_name') or ''}")
            lines.append(f"  情节类型：{item.get('plot_type') or ''}")
            lines.append(f"  章节范围：{item.get('start_chapter')} - {item.get('end_chapter')}")
            lines.append(f"  核心冲突：{item.get('core_conflict') or ''}")
            lines.append(f"  命中原因：{', '.join(item.get('match_reasons') or [])}")
        lines.append("")

    outline_seed = result.get("outline_seed") or {}
    if outline_seed:
        lines.extend([
            "## 大纲种子",
            "",
            "### 核心母线",
            "",
        ])
        for item in outline_seed.get("core_lines") or []:
            lines.append(f"- {item}")
        lines.extend([
            "",
            "### 第一卷主冲突",
            "",
            f"- {outline_seed.get('volume_one_conflict') or ''}",
            "",
            "### 前30章节奏建议",
            "",
        ])
        for block in outline_seed.get("thirty_chapter_rhythm") or []:
            lines.append(f"- {block.get('range')}: {block.get('goal') or ''}")
            refs = block.get("reference_plots") or []
            if refs:
                lines.append(f"  参考情节：{'；'.join(refs)}")
        lines.append("")

    lines.extend([
        "## 改编限制",
        "",
        "- 只借结构，不借角色名/地名/设定名",
        "- 只借冲突与节奏，不直接搬运原剧情外壳",
        "- 所有桥段都要做角色位抽象后再映射到本书角色",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="按书名/梗概生成首版情节池与大纲种子")
    parser.add_argument("title", help="书名")
    parser.add_argument("--premise", default="", help="一句话梗概，可选")
    parser.add_argument("--json-library", help="改用本地 JSON 情节库")
    parser.add_argument("--limit-per-group", type=int, default=8, help="每组关键词最多保留多少候选")
    parser.add_argument("--no-outline-seed", action="store_true", help="只输出情节池，不生成大纲种子")
    parser.add_argument("--save", action="store_true", help="将结果写入当前项目的 参考资料/情节库参考.md")
    parser.add_argument("--output", help="自定义输出 Markdown 路径；默认与 --save 相同")
    args = parser.parse_args()

    term_groups = _build_keyword_groups(args.title, args.premise)
    candidates = _collect_candidates(term_groups, args.limit_per_group, args.json_library or "")
    buckets = _bucketize(candidates, term_groups)

    result = {
        "title": args.title,
        "premise": args.premise,
        "keyword_groups": {
            "situation": term_groups["situation"],
            "driver": term_groups["driver"],
            "emotion": term_groups["emotion"],
            "goal": term_groups["goal"],
            "obstacle": term_groups["obstacle"],
            "search_groups": {
                "situation_driver": term_groups["situation_driver"],
                "situation_emotion": term_groups["situation_emotion"],
                "driver_emotion": term_groups["driver_emotion"],
                "goal_obstacle": term_groups["goal_obstacle"],
            },
        },
        "candidate_count": len(candidates),
        "outline_pool": buckets,
    }

    if not args.no_outline_seed:
        result["outline_seed"] = _build_outline_seed(args.title, args.premise, term_groups, buckets)

    if args.save or args.output:
        output_path = Path(args.output).resolve() if args.output else (Path.cwd() / "参考资料" / "情节库参考.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_format_pool_markdown(result), encoding="utf-8")
        result["saved_to"] = str(output_path)

    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
