#!/usr/bin/env python3
"""Validate the human-authored E/P semantic mapping before contract assembly."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


E_FIELDS = (
    "source_beat_id", "target_beat_id", "role", "intensity", "target_outline_region",
    "trigger", "relationship_position_change", "reader_effect", "target_story_adaptation",
    "hurt_object", "expectation_before", "expectation_after", "action_impulse_before",
    "action_impulse_after", "equivalence_reason", "target_evidence_coverage_review", "evidence",
)
P_FIELDS = (
    "source_path", "source_beat_id", "target_beat_id", "actor", "actor_evidence",
    "object_or_receiver", "pressure_or_trigger", "action", "control_change",
    "information_change", "consequence", "adaptation_equivalence", "evidence",
)
CONSTRUCTION_MARKERS = (
    "不照搬", "不能写成", "不承担", "只供应", "公开场不能", "叙述不写成", "机制迁移",
)
GENERIC_MARKERS = (
    "当前关系压力", "继续偏移", "目标婚姻场景", "后果继续传到下一拍", "实际选择与后果",
)
ABSTRACT_HURT_OBJECTS = {"关系", "关系位置", "婚姻", "婚姻位置", "读者预期", "在场者"}
ENTITY_CLAUSE_MARKERS = (
    "之后", "以前", "当时", "现场", "突然", "因为", "为了", "已经", "正在", "开始",
    "完成", "发生", "发现", "决定", "要求", "拿走", "交给", "离开", "回到", "走进",
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def surface(value: Any) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(value or ""))


def actor_tokens(value: Any) -> list[str]:
    return [x.strip() for x in re.split(r"[、,，/；;]|(?:与|和)", str(value or "")) if len(x.strip()) >= 2]


def entity_label_valid(value: Any) -> bool:
    """Accept open-world person/group labels while rejecting sentence-like event labels."""
    label = str(value or "").strip()
    compact = surface(label)
    if not compact or len(compact) > 16:
        return False
    if re.search(r"[。！？!?：:]", label):
        return False
    return not any(marker in label for marker in ENTITY_CLAUSE_MARKERS)


def actor_resolves(item: dict[str, Any]) -> bool:
    tokens = actor_tokens(item.get("actor"))
    actor_evidence = str(item.get("actor_evidence") or "").strip()
    evidence = str(item.get("evidence") or "")
    action = str(item.get("action") or "")
    if actor_evidence not in evidence or not tokens:
        return False
    if any(surface(x) in surface(actor_evidence) for x in tokens):
        return True
    return actor_evidence in {"他", "她", "他们", "她们", "对方", "其", "两人"} and any(
        surface(x) in surface(action) for x in tokens
    )


def require_fields(item: dict[str, Any], fields: tuple[str, ...], label: str, errors: list[str]) -> None:
    for field in fields:
        minimum = 1 if field in {"intensity", "hurt_object", "actor_evidence", "object_or_receiver"} else 2
        if len(str(item.get(field) or "").strip()) < minimum:
            errors.append(f"{label}.{field} 缺失或过短")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("validate", nargs="?")
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--outline", required=True, type=Path)
    parser.add_argument("--primary-emotion-ledger", required=True, type=Path)
    parser.add_argument("--primary-plot-ledger", required=True, type=Path)
    parser.add_argument("--primary-source", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    mapping = load(args.mapping)
    outline = args.outline.read_text(encoding="utf-8")
    emotion_ledger = load(args.primary_emotion_ledger).get("beats", [])
    plot_ledger = load(args.primary_plot_ledger).get("beats", [])
    emotions = mapping.get("emotions") if isinstance(mapping.get("emotions"), list) else []
    plots = mapping.get("plots") if isinstance(mapping.get("plots"), list) else []
    if mapping.get("status") != "approved":
        errors.append("mapping.status 必须为 approved")
    bindings = mapping.get("bindings") if isinstance(mapping.get("bindings"), dict) else {}
    for key, path in (("outline", args.outline), ("primary_source", args.primary_source),
                      ("primary_emotion_ledger", args.primary_emotion_ledger),
                      ("primary_plot_ledger", args.primary_plot_ledger)):
        item = bindings.get(key) if isinstance(bindings.get(key), dict) else {}
        if str(Path(item.get("path", "")).resolve()) != str(path.resolve()) or item.get("sha256") != sha(path):
            errors.append(f"bindings.{key} 路径或 SHA 不匹配")

    expected_e = [str(x.get("beat_id")) for x in emotion_ledger]
    actual_e = [str(x.get("source_beat_id")) for x in emotions]
    if actual_e != expected_e:
        errors.append("主体 E 拍必须与情绪总账全集完全同序")
    primary_key = str(args.primary_source.resolve())
    primary_plots = [x for x in plots if str(Path(x.get("source_path", "")).resolve()) == primary_key]
    expected_p = [str(x.get("beat_id")) for x in plot_ledger]
    actual_p = [str(x.get("source_beat_id")) for x in primary_plots]
    if actual_p != expected_p:
        errors.append("主体 P 拍必须与情节总账全集完全同序")

    used_evidence: dict[str, set[str]] = {"E": set(), "P": set()}
    generic = Counter()
    emotion_signatures: dict[str, list[tuple[str, ...]]] = {}
    source_e = {str(x.get("beat_id")): x for x in emotion_ledger}
    for index, item in enumerate(emotions, 1):
        label = f"emotions[{index}]"
        require_fields(item, E_FIELDS, label, errors)
        source = source_e.get(str(item.get("source_beat_id")), {})
        if item.get("role") != source.get("role") or item.get("intensity") != source.get("intensity"):
            errors.append(f"{label} role/intensity 与来源总账不一致")
        evidence = str(item.get("evidence") or "")
        if evidence not in outline:
            errors.append(f"{label}.evidence 不在当前细纲")
        if evidence in used_evidence["E"]:
            errors.append(f"{label}.evidence 与其他 E 拍重复")
        used_evidence["E"].add(evidence)
        if any(x in evidence for x in CONSTRUCTION_MARKERS):
            errors.append(f"{label}.evidence 是施工说明")
        hurt = str(item.get("hurt_object") or "").strip()
        if hurt not in ABSTRACT_HURT_OBJECTS and not entity_label_valid(hurt):
            errors.append(f"{label}.hurt_object 必须是人物、关系或读者预期，不能是整句事件")
        adaptation = str(item.get("target_story_adaptation") or "")
        has_pronoun = bool(re.search(r"他们|她们|对方|[他她]", evidence))
        if hurt not in ABSTRACT_HURT_OBJECTS and surface(hurt) not in surface(evidence):
            if not has_pronoun or surface(hurt) not in surface(adaptation):
                errors.append(f"{label}.hurt_object 未在证据出现，也没有由代词和适配说明解析")
        if surface(item.get("expectation_before")) == surface(item.get("expectation_after")):
            errors.append(f"{label} 期待前后态未变化")
        if surface(item.get("action_impulse_before")) == surface(item.get("action_impulse_after")):
            errors.append(f"{label} 行动冲动前后态未变化")
        joined = "".join(str(item.get(x) or "") for x in E_FIELDS)
        if any(x in joined for x in GENERIC_MARKERS):
            generic["E"] += 1
        region = str(item.get("target_outline_region") or "")
        emotion_signatures.setdefault(region, []).append(tuple(surface(item.get(field)) for field in (
            "expectation_before", "expectation_after", "action_impulse_before", "action_impulse_after",
        )))

    plot_keys: set[tuple[str, str]] = set()
    for index, item in enumerate(plots, 1):
        label = f"plots[{index}]"
        require_fields(item, P_FIELDS, label, errors)
        key = (str(Path(item.get("source_path", "")).resolve()), str(item.get("source_beat_id")))
        if key in plot_keys:
            errors.append(f"{label} 来源路径 + P 拍 ID 重复")
        plot_keys.add(key)
        tokens = actor_tokens(item.get("actor"))
        if not tokens or any(not entity_label_valid(token) for token in tokens):
            errors.append(f"{label}.actor 必须是目标人物或现场组织，不能把时间、地点或整句事件当施事者")
        evidence = str(item.get("evidence") or "")
        if evidence not in outline:
            errors.append(f"{label}.evidence 不在当前细纲")
        if evidence in used_evidence["P"]:
            errors.append(f"{label}.evidence 与其他 P 拍重复")
        used_evidence["P"].add(evidence)
        actor_evidence = str(item.get("actor_evidence") or "")
        if not actor_resolves(item):
            errors.append(f"{label}.actor_evidence 未点名施事者，或代词未由 action 解析为规范人物名")
        if any(x in evidence for x in CONSTRUCTION_MARKERS):
            errors.append(f"{label}.evidence 是施工说明")
        joined = "".join(str(item.get(x) or "") for x in P_FIELDS)
        if any(x in joined for x in GENERIC_MARKERS):
            generic["P"] += 1
    if generic["E"] >= max(3, len(emotions) // 3):
        errors.append("E 拍通用模板命中过多")
    if generic["P"] >= max(3, len(plots) // 3):
        errors.append("P 拍通用模板命中过多")
    for region, signatures in emotion_signatures.items():
        repeated = Counter(signatures).most_common(1)[0][1] if signatures else 0
        if len(signatures) >= 4 and repeated >= max(3, len(signatures) // 3):
            errors.append(f"{region} 大量 E 拍复用相同期待/行动前后态，必须逐拍裁决")

    if errors:
        print("semantic_beat_mapping: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("semantic_beat_mapping: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
