#!/usr/bin/env python3
"""库内检索模式：支持 Neo4j Plot 库或本地 JSON 情节库。"""
import argparse
import json
import os
from pathlib import Path

from neo4j import GraphDatabase


def _load_env_file(env_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not env_path.exists() or not env_path.is_file():
        return data
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    except Exception:
        return {}
    return data


def _find_nearest_env(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    candidates = [current] if current.is_dir() else [current.parent]
    candidates.extend(candidates[0].parents)
    seen = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        direct = base / ".env"
        if direct.exists() and direct.is_file():
            return direct
        nested = base / "novel-writer-cli" / ".env"
        if nested.exists() and nested.is_file():
            return nested
    return None


def _discover_project_neo4j_config() -> dict[str, str]:
    env_path = _find_nearest_env()
    env_data = _load_env_file(env_path) if env_path else {}
    return {
        "uri": env_data.get("NEO4J_URI", ""),
        "user": env_data.get("NEO4J_USER", ""),
        "password": env_data.get("NEO4J_PASSWORD", ""),
        "database": env_data.get("NEO4J_DATABASE", "neo4j"),
    }


class PlotNeo4jClient:
    def __init__(self):
        project_cfg = _discover_project_neo4j_config()
        self.uri = os.getenv('PLOT_EXTRACTOR_NEO4J_URI') or os.getenv('NEO4J_URI') or project_cfg.get('uri', '')
        self.user = os.getenv('PLOT_EXTRACTOR_NEO4J_USER') or os.getenv('NEO4J_USER') or project_cfg.get('user', '')
        self.password = os.getenv('PLOT_EXTRACTOR_NEO4J_PASSWORD') or os.getenv('NEO4J_PASSWORD') or project_cfg.get('password', '')
        self.database = os.getenv('PLOT_EXTRACTOR_NEO4J_DATABASE') or os.getenv('NEO4J_DATABASE') or project_cfg.get('database', 'neo4j')
        self.driver = None
        if self.uri and self.user and self.password:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def is_available(self) -> bool:
        return self.driver is not None

    def _run(self, query: str, **params) -> list[dict]:
        if not self.driver:
            return []
        with self.driver.session(database=self.database) as session:
            return [dict(r) for r in session.run(query, **params)]

    def list_novels(self) -> list[dict]:
        query = """
        MATCH (p:Plot)
        WHERE p.novel_id IS NOT NULL
        RETURN p.novel_id AS novel_id, '书' + toString(p.novel_id) AS title, count(p) AS plots
        ORDER BY plots DESC
        """
        return self._run(query)

    def get_candidate_plots(self, novel_keyword: str = "") -> list[dict]:
        rows = self.search_candidate_plots(novel_keyword=novel_keyword)
        normalized: list[dict] = []
        for row in rows:
            themes = row.get("themes")
            if isinstance(themes, str):
                try:
                    row["themes"] = json.loads(themes)
                except Exception:
                    row["themes"] = []
            elif themes is None:
                row["themes"] = []
            row["novel_title"] = f"书{row.get('novel_id')}"
            normalized.append(row)

        if novel_keyword:
            normalized = [row for row in normalized if novel_keyword in (row.get("novel_title") or "")]
        return normalized

    def search_candidate_plots(
        self,
        terms: list[str] | None = None,
        *,
        novel_keyword: str = "",
        type_keyword: str = "",
        chapter_start: int | None = None,
        chapter_end: int | None = None,
        limit: int = 4000,
    ) -> list[dict]:
        query = """
        MATCH (p:Plot)
        WHERE p.novel_id IS NOT NULL
          AND ($novel_keyword = '' OR toString(p.novel_id) CONTAINS $novel_keyword)
          AND ($type_keyword = '' OR coalesce(p.type, '') CONTAINS $type_keyword)
          AND ($chapter_start IS NULL OR coalesce(p.end_chapter, p.start_chapter, 0) >= $chapter_start)
          AND ($chapter_end IS NULL OR coalesce(p.start_chapter, 0) <= $chapter_end)
          AND (
            size($terms) = 0 OR
            any(term IN $terms WHERE
                coalesce(p.name, '') CONTAINS term OR
                coalesce(p.type, '') CONTAINS term OR
                coalesce(p.core_conflict, '') CONTAINS term OR
                coalesce(p.emotional_arc, '') CONTAINS term OR
                any(theme IN coalesce(p.themes, []) WHERE theme CONTAINS term)
            )
          )
        RETURN p.novel_id AS novel_id,
               p.id AS id,
               p.name AS name,
               p.type AS type,
               p.core_conflict AS core_conflict,
               p.emotional_arc AS emotional_arc,
               p.themes AS themes,
               p.start_chapter AS start_chapter,
               p.end_chapter AS end_chapter
        ORDER BY p.start_chapter
        LIMIT $limit
        """
        rows = self._run(
            query,
            terms=[term for term in (terms or []) if term],
            novel_keyword=novel_keyword,
            type_keyword=type_keyword,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            limit=limit,
        )
        normalized: list[dict] = []
        for row in rows:
            themes = row.get("themes")
            if isinstance(themes, str):
                try:
                    row["themes"] = json.loads(themes)
                except Exception:
                    row["themes"] = []
            elif themes is None:
                row["themes"] = []
            row["novel_title"] = f"书{row.get('novel_id')}"
            normalized.append(row)
        return normalized

    def get_all_plots(self, novel_id: int) -> list[dict]:
        query = """
        MATCH (p:Plot {novel_id: $novel_id})
        RETURN p.id AS id,
               p.name AS name,
               p.type AS type,
               p.core_conflict AS core_conflict,
               p.emotional_arc AS emotional_arc,
               p.themes AS themes,
               p.start_chapter AS start_chapter,
               p.end_chapter AS end_chapter
        ORDER BY p.start_chapter
        """
        rows = self._run(query, novel_id=novel_id)
        for row in rows:
            themes = row.get('themes')
            if isinstance(themes, str):
                try:
                    row['themes'] = json.loads(themes)
                except Exception:
                    row['themes'] = []
            elif themes is None:
                row['themes'] = []
        return rows


def _load_json_plot_sources(path_str: str) -> list[dict]:
    root = Path(path_str).resolve()
    if not root.exists():
        raise FileNotFoundError(f"JSON 情节库路径不存在: {root}")

    json_files: list[Path] = []
    if root.is_file():
        json_files = [root]
    else:
        json_files = sorted(p for p in root.rglob("*.json") if p.is_file())

    plots: list[dict] = []
    for file_path in json_files:
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        items: list[dict] = []
        if isinstance(raw, list):
            items = [x for x in raw if isinstance(x, dict)]
        elif isinstance(raw, dict):
            if isinstance(raw.get("plots"), list):
                items = [x for x in raw.get("plots") if isinstance(x, dict)]
            elif raw.get("plot_name") or raw.get("core_conflict"):
                items = [raw]

        for idx, item in enumerate(items, start=1):
            plot_name = item.get("plot_name") or item.get("name") or ""
            core_conflict = item.get("core_conflict") or item.get("plot_summary") or ""
            if not plot_name and not core_conflict:
                continue
            novel_title = (
                item.get("novel_title")
                or item.get("title")
                or item.get("book_title")
                or file_path.parent.name
                or file_path.stem
            )
            themes = item.get("themes") or []
            if isinstance(themes, str):
                themes = [themes]
            elif not isinstance(themes, list):
                themes = []
            plots.append({
                "source_file": str(file_path),
                "novel_id": item.get("novel_id") or "",
                "novel_title": novel_title,
                "plot_id": item.get("plot_id") or item.get("id") or f"{file_path.stem}:{idx}",
                "plot_name": plot_name,
                "plot_type": item.get("plot_type") or item.get("type") or "",
                "core_conflict": core_conflict,
                "plot_summary": item.get("plot_summary") or "",
                "emotional_arc": item.get("emotional_arc") or "",
                "themes": themes,
                "start_chapter": item.get("start_chapter"),
                "end_chapter": item.get("end_chapter"),
                "plot_status": item.get("plot_status") or "",
                "main_characters": item.get("main_characters") or [],
                "key_turning_points": item.get("key_turning_points") or [],
            })
    return plots


def _expand_terms(terms: list[str]) -> list[str]:
    alias_map = {
        "收徒": ["弟子", "纳徒", "门徒"],
        "长老": ["高层", "掌门", "宗门"],
        "资源": ["矿脉", "灵石", "供养"],
        "危机": ["施压", "围攻", "赤字"],
        "改革": ["新法", "整编", "扩张"],
    }
    expanded: list[str] = []
    seen = set()
    for term in terms:
        for item in [term] + alias_map.get(term, []):
            if item and item not in seen:
                expanded.append(item)
                seen.add(item)
    return expanded


STRONG_MOTIFS = {
    "穿越", "重生", "系统", "直播", "算命", "末世", "丧尸", "校园", "娱乐圈",
    "宫斗", "机甲", "星际", "兽世", "军婚", "盗墓", "电竞", "无限流", "修仙",
    "玄幻", "西幻", "克苏鲁", "诡异", "高武", "都市", "灵异",
}

def _normalize_term(term: str) -> str:
    return term.strip().lower()


def _split_query_terms(query_terms: list[str], structure_terms: list[str] | None = None) -> list[str]:
    expanded: list[str] = []
    seen = set()
    active_structure_terms = [term for term in (structure_terms or []) if term]
    for term in query_terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        parts = [cleaned]
        if active_structure_terms and len(cleaned) >= 6:
            for hint in active_structure_terms:
                if hint in cleaned:
                    parts.append(hint)
        for part in parts:
            piece = part.strip()
            if len(piece) <= 1 or piece in seen:
                continue
            seen.add(piece)
            expanded.append(piece)
    return expanded


def _extract_query_motifs(query_terms: list[str]) -> set[str]:
    merged = " ".join(query_terms)
    return {motif for motif in STRONG_MOTIFS if motif and motif in merged}


def _extract_plot_motifs(plot: dict) -> set[str]:
    text = " ".join([
        plot.get("plot_name") or plot.get("name") or "",
        plot.get("plot_type") or plot.get("type") or "",
        plot.get("core_conflict") or "",
        plot.get("emotional_arc") or "",
        " ".join(plot.get("themes") or []),
    ])
    return {motif for motif in STRONG_MOTIFS if motif and motif in text}


def _build_plot_text(plot: dict) -> str:
    return " ".join([
        plot.get("plot_name") or plot.get("name") or "",
        plot.get("plot_type") or plot.get("type") or "",
        plot.get("core_conflict") or "",
        plot.get("emotional_arc") or "",
        " ".join(plot.get("themes") or []),
    ])


def _extract_interlude_tags(plot: dict) -> set[str]:
    text = _build_plot_text(plot)
    tags = set()
    tag_map = {
        "误会": ["误会", "错认", "错送", "错拿", "吃醋"],
        "试探": ["试探", "套话", "刺探", "探底"],
        "反转": ["反转", "翻盘", "揭露", "真相", "打脸"],
        "拖延": ["拖延", "周旋", "转圜", "缓冲"],
        "结盟": ["结盟", "搭档", "联手", "合作"],
        "背锅": ["背锅", "冤枉", "替罪", "顶罪"],
        "埋雷": ["埋雷", "伏笔", "后手", "隐患"],
        "补刀": ["补刀", "反击", "压制", "收尾"],
    }
    for tag, hints in tag_map.items():
        if any(hint in text for hint in hints):
            tags.add(tag)
    return tags


def _score_interlude_plot(plot: dict, query_terms: list[str], structure_terms: list[str] | None = None) -> tuple[int, list[str]]:
    score, reasons = _score_plot(plot, query_terms, structure_terms=structure_terms)
    text = _build_plot_text(plot)
    tags = _extract_interlude_tags(plot)
    if tags:
        score += min(8, 2 * len(tags))
        reasons.append(f"插曲功能:{'、'.join(sorted(tags)[:3])}")
    portability = 0
    if len(text) > 120:
        portability += 1
    if any(word in text for word in ["现代", "古代", "仙侠", "宫廷", "职场", "校园", "都市"]):
        portability += 2
    if any(word in text for word in ["误会", "试探", "反转", "结盟", "背锅", "埋雷"]):
        portability += 3
    score += portability
    if portability:
        reasons.append("可改编性")
    return score, reasons


def _score_plot(plot: dict, query_terms: list[str], structure_terms: list[str] | None = None) -> tuple[int, list[str]]:
    haystacks = {
        "name": (plot.get("plot_name") or plot.get("name") or ""),
        "type": (plot.get("plot_type") or plot.get("type") or ""),
        "core_conflict": (plot.get("core_conflict") or ""),
        "emotional_arc": (plot.get("emotional_arc") or ""),
        "themes": " ".join(plot.get("themes") or []),
    }
    merged_text = " ".join(haystacks.values())
    score = 0
    reasons: list[str] = []
    exact_term_hits = 0
    core_term_hits = 0
    split_terms = _split_query_terms(query_terms, structure_terms=structure_terms)
    active_structure_terms = {term for term in (structure_terms or []) if term}
    for term in split_terms:
        if not term:
            continue
        normalized = _normalize_term(term)
        if len(normalized) <= 1:
            continue
        if term in haystacks["name"]:
            score += 5
            reasons.append(f"命中情节名:{term}")
            exact_term_hits += 1
        if term in haystacks["core_conflict"]:
            score += 4
            reasons.append(f"命中核心冲突:{term}")
            core_term_hits += 1
        if term in haystacks["emotional_arc"]:
            score += 2
            reasons.append(f"命中情感弧:{term}")
        if term in haystacks["themes"]:
            score += 2
            reasons.append(f"命中主题:{term}")
        if term in haystacks["type"]:
            score += 1
            reasons.append(f"命中类型:{term}")
        compact_term = normalized.replace(" ", "")
        if compact_term and compact_term in merged_text.lower().replace(" ", ""):
            score += 1

    if exact_term_hits >= 2:
        score += 4
        reasons.append("多关键词直接命中")
    elif exact_term_hits == 0 and core_term_hits == 0:
        score -= 6
        reasons.append("缺少核心关键词直命中")

    structure_hits = [term for term in split_terms if term in active_structure_terms and term in merged_text]
    if len(structure_hits) >= 2:
        score += 6
        reasons.append(f"结构词共振:{'、'.join(structure_hits[:3])}")
    elif len(structure_hits) == 1:
        score += 2

    query_motifs = _extract_query_motifs(query_terms)
    plot_motifs = _extract_plot_motifs(plot)
    extra_motifs = sorted(plot_motifs - query_motifs)
    if extra_motifs:
        penalty = min(12, 4 * len(extra_motifs))
        score -= penalty
        reasons.append(f"偏题母题:{'、'.join(extra_motifs[:3])}")
    shared_motifs = sorted(plot_motifs & query_motifs)
    if shared_motifs:
        score += min(6, 3 * len(shared_motifs))
        reasons.append(f"同母题:{'、'.join(shared_motifs[:3])}")

    start_ch = plot.get("start_chapter") or 0
    if isinstance(start_ch, int):
        if start_ch <= 120:
            score += 1
            reasons.append("前期情节")
        elif start_ch <= 400:
            score += 0
    return score, reasons


def _safe_chapter_no(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return 0


def _is_explicit_numeric_chapter(value) -> bool:
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.strip().isdigit() and int(value.strip()) > 0
    return False


def _plot_span(plot: dict) -> int:
    start = _safe_chapter_no(plot.get("start_chapter"))
    end = _safe_chapter_no(plot.get("end_chapter"))
    if start <= 0:
        return 0
    if end <= 0:
        end = start
    if end < start:
        end = start
    return end - start + 1


def _passes_interlude_length(plot: dict, length_mode: str) -> bool:
    start = _safe_chapter_no(plot.get("start_chapter"))
    end = _safe_chapter_no(plot.get("end_chapter"))
    span = _plot_span(plot)
    if start <= 0 or span <= 0:
        return False
    if length_mode == "light":
        return _is_explicit_numeric_chapter(plot.get("end_chapter")) and end == start
    if length_mode == "short":
        return _is_explicit_numeric_chapter(plot.get("end_chapter")) and 2 <= span <= 3
    return True


def _infer_micro_task_position(plot: dict) -> str:
    span = _plot_span(plot)
    if span <= 1:
        return "章中段或两个Beat之间"
    if span <= 3:
        return "章中后段的小插段"
    return "作为独立支线前的缓冲段"


def _infer_micro_task_effect(plot: dict) -> str:
    tags = _extract_interlude_tags(plot)
    if "误会" in tags or "试探" in tags:
        return "制造关系波动并暴露立场"
    if "反转" in tags or "补刀" in tags:
        return "让局势短时翻转，抬高情绪"
    if "埋雷" in tags:
        return "埋下后续冲突或秘密线"
    if "拖延" in tags:
        return "延迟主线动作，为后手争时间"
    if "结盟" in tags:
        return "建立临时合作或利益交换"
    return "补一段功能型动作单元"


def _infer_micro_task_trigger(plot: dict) -> str:
    tags = _extract_interlude_tags(plot)
    if "误会" in tags:
        return "当人物之间信息不对称，但还没到彻底撕破脸时插入"
    if "试探" in tags:
        return "当一方需要探底、套话或确认立场时插入"
    if "反转" in tags or "补刀" in tags:
        return "当主线局势刚要定型，想临时掀一下桌面时插入"
    if "拖延" in tags:
        return "当主角需要争取时间、拖住对手或等待后手时插入"
    if "结盟" in tags:
        return "当人物需要临时交换利益、借力过桥时插入"
    if "埋雷" in tags:
        return "当本章需要留一个后续会回收的小隐患时插入"
    return "当两个 Beat 之间缺少过桥动作或关系波动时插入"


def _infer_micro_task_insertion_goal(plot: dict) -> str:
    tags = _extract_interlude_tags(plot)
    if "误会" in tags or "试探" in tags:
        return "让角色关系先绷紧，再把真实立场往前推半步"
    if "反转" in tags or "补刀" in tags:
        return "给本章增加一次短促翻面，避免直线推进"
    if "拖延" in tags:
        return "延迟主线结论，为下一动作腾出空间"
    if "结盟" in tags:
        return "补出一个临时合作节点，给后续推进提供合理抓手"
    if "埋雷" in tags:
        return "把后续冲突种子提前埋进当前场景"
    return "补齐段落功能，让 Beat 连接更自然"


def _infer_micro_task_exit_condition(plot: dict) -> str:
    tags = _extract_interlude_tags(plot)
    if "误会" in tags:
        return "到一方产生错误判断，或关系出现轻微偏移时结束"
    if "试探" in tags:
        return "到一方拿到足够判断依据，但还没有完全摊牌时结束"
    if "反转" in tags or "补刀" in tags:
        return "到局势短时倒挂、强弱位重排后立刻收束"
    if "拖延" in tags:
        return "到关键时间差被争取出来，或外部条件变化时结束"
    if "结盟" in tags:
        return "到双方达成临时交换条件，关系从对立转为合作时结束"
    if "埋雷" in tags:
        return "到隐患被放进场景但暂时没人处理时结束"
    return "到主线可以顺势接回下一个 Beat 时结束"


def _infer_micro_task_execution_shape(plot: dict) -> str:
    tags = _extract_interlude_tags(plot)
    if "误会" in tags or "试探" in tags:
        return "对话拉扯型"
    if "反转" in tags or "补刀" in tags:
        return "动作翻面型"
    if "拖延" in tags:
        return "阻滞周旋型"
    if "结盟" in tags:
        return "交换协商型"
    if "埋雷" in tags:
        return "细节埋钩型"
    return "功能过桥型"


def _infer_tension_type(plot: dict) -> str:
    tags = _extract_interlude_tags(plot)
    if "误会" in tags:
        return "误会拉扯"
    if "试探" in tags:
        return "信息试探"
    if "反转" in tags:
        return "局势反转"
    if "背锅" in tags:
        return "责任转移"
    if "埋雷" in tags:
        return "伏笔埋设"
    if "拖延" in tags:
        return "节奏拖延"
    if "结盟" in tags:
        return "临时结盟"
    return "功能过桥"


def _infer_relationship_effect(plot: dict) -> str:
    tags = _extract_interlude_tags(plot)
    if "误会" in tags or "试探" in tags:
        return "关系紧张但不破裂"
    if "结盟" in tags:
        return "关系拉近并建立合作"
    if "背锅" in tags:
        return "关系失衡，形成压迫"
    if "反转" in tags:
        return "角色地位短时倒挂"
    if "埋雷" in tags:
        return "表面稳定，暗线加深"
    return "为后续关系变化预热"


def _infer_surface_dependency(plot: dict) -> str:
    text = _build_plot_text(plot)
    if any(word in text for word in ["宫廷", "皇帝", "宗门", "灵力", "系统", "直播", "丧尸", "电竞"]):
        return "中"
    if any(word in text for word in ["误会", "试探", "反转", "结盟", "背锅", "埋雷"]):
        return "低"
    return "低"


def _build_micro_task_adaptation(plot: dict, structure_terms: list[str] | None = None) -> str:
    tags = sorted(_extract_interlude_tags(plot))
    structure = "、".join([term for term in (structure_terms or []) if term][:3]) or "当前题材"
    if tags:
        return f"保留“{' / '.join(tags[:3])}”这类功能，把表层设定替换成{structure}语境下的人物互动、场景阻碍或信息交换。"
    return f"只借用冲突功能，不照搬表层设定，改写成{structure}语境下的具体桥段。"


def _build_micro_task(plot: dict, structure_terms: list[str] | None = None) -> dict:
    tags = sorted(_extract_interlude_tags(plot))
    return {
        "source_plot_name": plot.get("plot_name") or plot.get("name") or "",
        "source_plot_type": plot.get("plot_type") or plot.get("type") or "",
        "function_tags": tags,
        "tension_type": _infer_tension_type(plot),
        "relationship_effect": _infer_relationship_effect(plot),
        "surface_dependency": _infer_surface_dependency(plot),
        "position_hint": _infer_micro_task_position(plot),
        "expected_effect": _infer_micro_task_effect(plot),
        "trigger_condition": _infer_micro_task_trigger(plot),
        "insertion_goal": _infer_micro_task_insertion_goal(plot),
        "exit_condition": _infer_micro_task_exit_condition(plot),
        "execution_shape": _infer_micro_task_execution_shape(plot),
        "adaptation_hint": _build_micro_task_adaptation(plot, structure_terms=structure_terms),
        "core_conflict": plot.get("core_conflict") or "",
        "emotional_arc": plot.get("emotional_arc") or "",
        "start_chapter": plot.get("start_chapter"),
        "end_chapter": plot.get("end_chapter"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="从 Neo4j 或本地 JSON 情节库中搜索相关情节")
    parser.add_argument("terms", nargs="+", help="一个或多个检索关键词")
    parser.add_argument("--novel", help="只搜索标题中包含该词的小说")
    parser.add_argument("--limit", type=int, default=20, help="最多返回多少条候选")
    parser.add_argument("--type", help="按 plot_type 过滤，例如 主线情节/冲突事件")
    parser.add_argument("--chapter-range", help="按章节范围过滤，格式如 1-120")
    parser.add_argument("--json-library", help="本地 JSON 情节库路径；可传单个 JSON 文件或目录")
    parser.add_argument("--structure-terms", nargs="*", default=[], help="额外传入本次检索的结构词，如 流放 情报 翻盘")
    parser.add_argument("--mode", choices=["mainline", "interlude"], default="mainline", help="检索模式：主干 or 插曲")
    args = parser.parse_args()

    query_terms = [t.strip() for t in args.terms if t.strip()]
    if not query_terms:
        print("[ERROR] 至少提供一个检索关键词", flush=True)
        return 1
    expanded_terms = _expand_terms(query_terms)
    chapter_start = None
    chapter_end = None
    if args.chapter_range:
        try:
            left, right = args.chapter_range.split("-", 1)
            chapter_start = int(left.strip())
            chapter_end = int(right.strip())
        except Exception:
            print("[ERROR] --chapter-range 格式错误，应为 start-end，例如 1-120", flush=True)
            return 1

    candidates = []
    library_mode = "json" if args.json_library else "neo4j"
    if args.json_library:
        try:
            plots = _load_json_plot_sources(args.json_library)
        except Exception as exc:
            print(f"[ERROR] 读取 JSON 情节库失败: {exc}", flush=True)
            return 1
        if args.novel:
            plots = [p for p in plots if args.novel in (p.get("novel_title") or "")]
        for plot in plots:
            if args.type and args.type not in (plot.get("plot_type") or ""):
                continue
            if chapter_start is not None and chapter_end is not None:
                start_ch = _safe_chapter_no(plot.get("start_chapter"))
                end_ch = _safe_chapter_no(plot.get("end_chapter")) or start_ch
                if end_ch < chapter_start or start_ch > chapter_end:
                    continue
            if args.mode == "interlude":
                score, reasons = _score_interlude_plot(plot, expanded_terms, structure_terms=args.structure_terms)
            else:
                score, reasons = _score_plot(plot, expanded_terms, structure_terms=args.structure_terms)
            if score <= 0:
                continue
            candidates.append({
                "novel_id": plot.get("novel_id") or "",
                "novel_title": plot.get("novel_title") or "",
                "plot_id": plot.get("plot_id") or "",
                "plot_name": plot.get("plot_name") or "",
                "plot_type": plot.get("plot_type") or "",
                "core_conflict": plot.get("core_conflict") or "",
                "emotional_arc": plot.get("emotional_arc") or "",
                "themes": plot.get("themes") or [],
                "start_chapter": plot.get("start_chapter"),
                "end_chapter": plot.get("end_chapter"),
                "source_file": plot.get("source_file") or "",
                "score": score,
                "match_reasons": reasons[:5],
            })
    else:
        neo4j = PlotNeo4jClient()
        if not neo4j.is_available():
            print("[ERROR] Neo4j 不可用。请配置 PLOT_EXTRACTOR_NEO4J_URI/USER/PASSWORD。", flush=True)
            return 1
        plots = neo4j.search_candidate_plots(
            terms=expanded_terms + list(args.structure_terms or []),
            novel_keyword=args.novel or "",
            type_keyword=args.type or "",
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            limit=max(args.limit * 100, 800),
        )
        for plot in plots:
            if args.mode == "interlude":
                score, reasons = _score_interlude_plot(plot, expanded_terms, structure_terms=args.structure_terms)
            else:
                score, reasons = _score_plot(plot, expanded_terms, structure_terms=args.structure_terms)
            if score <= 0:
                continue
            candidates.append({
                "novel_id": plot.get("novel_id") or "",
                "novel_title": plot.get("novel_title") or "",
                "plot_id": plot.get("id") or "",
                "plot_name": plot.get("name") or "",
                "plot_type": plot.get("type") or "",
                "core_conflict": plot.get("core_conflict") or "",
                "emotional_arc": plot.get("emotional_arc") or "",
                "themes": plot.get("themes") or [],
                "start_chapter": plot.get("start_chapter"),
                "end_chapter": plot.get("end_chapter"),
                "source_file": "",
                "score": score,
                "match_reasons": reasons[:5],
            })

    candidates.sort(key=lambda x: (-x["score"], str(x["novel_id"]), _safe_chapter_no(x["start_chapter"])))
    result = {
        "library_mode": library_mode,
        "json_library": args.json_library or "",
        "query_terms": query_terms,
        "expanded_terms": expanded_terms,
        "novel_filter": args.novel or "",
        "type_filter": args.type or "",
        "chapter_range": args.chapter_range or "",
        "count": len(candidates[: args.limit]),
        "results": candidates[: args.limit],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
