#!/usr/bin/env python3
"""Validate the primary-source prose granularity contract for short fiction."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_DIMENSIONS = (
    "sentence_motion",
    "lexical_register",
    "narrator_voice",
    "paragraph_breath",
    "dialogue_connection",
    "emotion_wording",
    "productive_roughness",
)
ULTRA_FINE_FEATURE_GROUPS = {
    "character_punctuation": tuple(f"CP-{index:02d}" for index in range(1, 9)),
    "lexical_morphology": tuple(f"LM-{index:02d}" for index in range(1, 9)),
    "phrase_syntax": tuple(f"PS-{index:02d}" for index in range(1, 9)),
    "sentence_cohesion": tuple(f"SC-{index:02d}" for index in range(1, 9)),
    "focalization_pragmatics": tuple(f"FP-{index:02d}" for index in range(1, 13)),
    "emotion_paragraph_distribution": tuple(f"EP-{index:02d}" for index in range(1, 9)),
}
ULTRA_FINE_FEATURE_IDS = tuple(
    feature_id
    for feature_ids in ULTRA_FINE_FEATURE_GROUPS.values()
    for feature_id in feature_ids
)
SOURCE_SENTENCE_ANNOTATION_FIELDS = (
    "character_and_punctuation",
    "lexical_and_morphology",
    "clause_and_syntax",
    "reference_and_cohesion",
    "focalization_and_knowledge_limit",
    "speech_thought_and_pragmatics",
    "emotion_action_sequence",
    "paragraph_and_negative_space",
    "transfer_constraint",
    "permitted_deviation",
)
SECTION_PARAGRAPH_PLAN_FIELDS = (
    "entry_motion",
    "focalizer_and_knowledge_limit",
    "cohesion_chain",
    "dialogue_strategy",
    "emotion_sequence",
    "exit_cut",
    "negative_space",
)
SECTION_WINDOW_PLAN_FIELDS = (
    "sentence_length_movement",
    "function_word_rhythm",
    "narrator_interjection_distribution",
    "anti_uniformity",
)
TARGET_SENTENCE_MAPPING_FIELDS = (
    "clause_and_function_words",
    "sentence_relation",
    "reference_and_focalization",
    "speech_and_pragmatics",
    "emotion_and_paragraph_function",
    "permitted_deviation",
)
SOURCE_STYLE_GRANULARITY_FIELDS = (
    "narrative_voice_and_attitude",
    "sentence_relation_and_rhythm",
    "paragraph_breath_and_cut_points",
    "dialogue_misfire_or_avoidance",
    "action_perception_emotion_weave",
    "narrator_interjection_and_roughness",
)
ALLOWED_AUTOMATION_ARTIFACTS = {
    "candidate_localization",
    "sha_binding",
    "schema_initialization",
    "deterministic_serialization",
}
FORBIDDEN_SEMANTIC_AUTOMATION_ARTIFACTS = {
    "semantic_field_generation",
    "automatic_quote_selection",
    "automatic_character_ownership",
    "automatic_keep_revise",
}
SIDECAR_TARGET_QUOTE_FIELDS = {
    "quote",
    "target_quotes",
    "target_chain_quotes",
    "target_dialogue_turns",
    "target_sentence",
    "target_surface_evidence",
}
CONTINUOUS_SOURCE_CHAIN_PACKET_FIELDS = (
    "chain_motion",
    "target_scene_use",
    "target_sentence_relation",
    "explanation_to_omit",
)
DIALOGUE_VOICE_PACKET_FIELDS = (
    "turn_motion",
    "target_scene_use",
    "oral_texture_transfer",
    "relationship_leverage",
    "functional_compression_to_avoid",
    "negative_failure",
    "rewrite_instruction",
)
RELATION_TYPES = (
    "succession",
    "contrast",
    "cause_effect",
    "addition",
    "counterevidence",
    "question_echo",
    "interruption",
)
RELATION_MARKING_MODES = ("explicit", "implicit")
FUNCTION_WORD_FEATURE_MARKERS = (
    "而",
    "但",
    "但是",
    "却",
    "可",
    "可是",
    "反倒",
    "反而",
    "偏偏",
    "于是",
    "所以",
    "因为",
    "毕竟",
    "果然",
)
RELATION_MICRO_EXAMPLE_FIELDS = (
    "source_function_word_skeleton",
    "target_rehearsal",
    "negative_example",
    "negative_failure",
    "transfer_instruction",
    "manual_judgment",
)
FEATURE_EVIDENCE_FIELDS = (
    "feature_id",
    "source_evidence",
    "mechanism",
)
LIVELINESS_ASSET_TYPES = (
    "active_verb",
    "embodied_perception",
    "colloquial_interjection",
    "dialogue_rough_edge",
    "incomplete_sentence",
    "object_emotion_binding",
    "anti_polished_expression",
)
LIVELINESS_SECTION_PLAN_FIELDS = (
    "entry_and_attention_bias",
    "active_verb_and_body_sensation",
    "dialogue_rough_edge",
    "object_emotion_binding",
    "narrator_interjection",
    "anti_summary_cut",
)
CHARACTER_PERSONALITY_ASSET_TYPES = (
    "attention_bias",
    "desire_and_shame_leak",
    "defense_strategy",
    "dialogue_misfire",
    "action_bias",
    "self_contradiction",
    "private_relation_language",
)

ABSTRACT_DIALOGUE_CANDIDATE_PATTERNS = (
    re.compile(r"(?:这种时候|这个时候|这种事|这件事|这个问题|这种问题).{0,16}(?:别|不要|不能|只|应该|得)"),
    re.compile(r"(?:别|不要|不能)只"),
    re.compile(r"这不是.{0,12}的问题"),
    re.compile(r"(?:顾全|看)大局"),
)
FUNCTIONAL_DIALOGUE_JUSTIFICATION_PATTERN = re.compile(
    r"(?:刚(?:回国|回来|到)|外面|外头|有人(?:拍|跟|堵)|怕|不方便|安全|等不起|临时)"
)
FUNCTIONAL_DIALOGUE_ASSIGNMENT_PATTERN = re.compile(
    r"你(?:先|去|到|留在|陪|帮|替|回|坐|等|把|拿)"
)
FUNCTIONAL_DIALOGUE_DEFER_PATTERN = re.compile(
    r"(?:结束|散场|等会儿?|待会儿?|回头|晚点|之后|一会儿?)后?"
    r"[^。！？\n]{0,16}(?:我|我们)(?:再|就|马上)?(?:找|陪|接|解释|处理|补|安排)"
    r"|(?:我|我们)(?:回头|晚点|之后|一会儿?|再|马上)(?:找|陪|接|解释|处理|补|安排)"
)
ELLIPTICAL_QUESTION_OBJECT_PATTERN = re.compile(
    r"^(?:我|你|他|她)问"
    r"(?!的是|(?:你|我|他|她)?(?:谁|哪|什么|怎么|为何|为什么|凭什么|知不知道|有没有|是不是|能不能|会不会|要不要|该不该)|清楚|明白|完|过|了|一下)"
    r"(?!路[。！？]?$|价[。！？]?$|好[。！？]?$|安[。！？]?$|诊[。！？]?$)"
    r"[\u4e00-\u9fff]{1,8}[。！？]?$"
)
TRANSFER_TARGET_OMISSION_PATTERN = re.compile(
    r"^(?:[\u4e00-\u9fff]{1,12}[，,])?"
    r"(?P<object_phrase>[^，。！？\n]{1,20}?)"
    r"(?:为什么|凭什么|干吗|干嘛)(?:还|就|非)?要?"
    r"(?:让|留|给|交|递|腾|挪)(?:出去|出来|走|开)?[？?。！!]?$"
)
STAFF_SIGNAGE_DIALOGUE_PATTERN = re.compile(
    r"^(?P<address>[\u4e00-\u9fff]{1,12})[，,]"
    r"(?P<location>[^，。！？\n]{1,18})(?:先别|不要|不能)"
    r"(?P<action>[^，。！？\n]{1,12})[。！？]?$"
)
DISTANT_MICRO_EXPRESSION_PATTERN = re.compile(
    r"(?:帽檐|帽边|口罩|面纱|刘海)[^。！？\n]{0,8}"
    r"(?:底下|下面|后面)[^。！？\n]{0,8}"
    r"(?:露出|看见|显出)[^。！？\n]{0,8}"
    r"(?:发红|泛红|通红|湿润|含泪)(?:的)?(?:眼睛|眼眶|眼角)"
)
DISTANT_OBSTRUCTION_MICRO_EXPRESSION_PATTERN = re.compile(
    r"(?:隔着|透过|藏在|躲在|挡在)[^。！？\n]{1,24}"
    r"(?:看见|瞧见|望见|露出|显出)?[^。！？\n]{0,12}"
    r"(?:(?:眼睛|眼眶|眼角)[^。！？\n]{0,6}(?:发红|泛红|通红|湿润|含泪)"
    r"|(?:发红|泛红|通红|湿润|含泪)(?:的)?(?:眼睛|眼眶|眼角))"
)
SEQUENCED_GAZE_CHOREOGRAPHY_PATTERN = re.compile(
    r"(?:停|顿)[^。！？\n]{0,6}(?:一下|一瞬|半拍)?[^。！？\n]{0,8}"
    r"先(?:看|望|瞧)[^，。！？\n]{1,8}[，,]"
    r"再(?:往[^，。！？\n]{0,8})?(?:看|找|望|瞧)"
)
ABSTRACT_RESPONSE_TIMING_PATTERN = re.compile(
    r"^[^，,。！？\n]{1,12}"
    r"(?:几乎)?(?:立刻|马上|很快|当即)"
    r"(?:应|答|回)(?:了|了一声)?[。！？]?$"
)
DEFAULT_STATE_TIMING_PATTERN = re.compile(
    r"^[^，,。！？\n]{1,12}还[^，,。！？\n]{0,8}(?:着|在)"
    r"[^，,。！？\n]{1,20}[，,]"
    r"[^。！？\n]{1,30}(?:已经|就)[^。！？\n]{1,30}[：:]?[。！？]?$"
)
SYNONYMOUS_EVENT_RESTATEMENT_PATTERN = re.compile(
    r"(?:退出|撤出|辞去|辞职|离职|离开|搬走|消失|分开|结束)"
    r"[^。！？\n]{0,24}[，,][^。！？\n]{0,12}"
    r"(?:离开|退出|走|消失|辞职|离职|分开|结束)得"
    r"(?:很|太|格外|异常)?(?:突然|干脆|仓促|彻底|意外)"
)
ABSTRACT_EVENT_EVALUATION_PATTERN = re.compile(
    r"(?:离开|退出|走|消失|辞职|离职|搬走|分开|结束)得"
    r"(?:很|太|格外|异常)?(?:突然|干脆|仓促|彻底|意外)[。！？]?$"
)
CONCRETE_FOLLOWUP_EVENT_PATTERN = re.compile(
    r"(?:凌晨|清晨|早上|上午|中午|下午|傍晚|晚上|半夜|当天|当晚|第二天|次日|"
    r"第[一二三四五六七八九十百\d]+天|\d{1,2}[点时])"
    r"[^。！？\n]{0,40}"
    r"(?:退(?:出|了)|删(?:掉|了)|搬(?:走|了)|离开|辞职|离职|交(?:出|了)|"
    r"收拾|登上|买了|签了|发了|留下一句)"
)
EXPLANATORY_NARRATION_CANDIDATE_PATTERNS = (
    re.compile(r"像[^。！？\n]{0,60}不是[^。！？\n]{0,30}而是[^。！？\n]{0,60}"),
    re.compile(r"(?:他|她)大概(?:觉得|以为|认为)[^。！？\n]{0,40}"),
    re.compile(r"(?:他|她)得(?:先|挑|选|处理|决定)[^。！？\n]{0,40}"),
    re.compile(r"通常最[^。！？\n]{0,24}(?:是|的)"),
    re.compile(
        r"(?:说|讲|答|解释|安排|做|写|念)[^。！？\n]{0,8}得"
        r"(?:很|太|格外|异常)?(?:顺|顺口|轻巧|自然|熟练|平静|干脆|理所当然)"
        r"[，,]\s*(?:像|仿佛|好像)[^。！？\n]{2,60}"
    ),
    re.compile(
        r"(?:却|但|可)?(?:正好|刚好|恰好)(?:在这时|这时|此时)?"
        r"[^。！？\n]{0,12}(?:叫|让|催|喊|通知|示意)"
        r"[^。！？\n]{1,30}"
    ),
    DISTANT_MICRO_EXPRESSION_PATTERN,
    DISTANT_OBSTRUCTION_MICRO_EXPRESSION_PATTERN,
    SEQUENCED_GAZE_CHOREOGRAPHY_PATTERN,
    ABSTRACT_RESPONSE_TIMING_PATTERN,
    DEFAULT_STATE_TIMING_PATTERN,
    SYNONYMOUS_EVENT_RESTATEMENT_PATTERN,
)
HARD_COORDINATION_CANDIDATE_PATTERNS = (
    re.compile(
        r"(?:嘴上|口口声声|明明|说着|一边)[^。！？\n]{0,36}[，,]"
        r"(?!(?:[^。！？\n]{0,12})(?:却|可|可是|反倒|反而|偏偏|倒是))"
        r"[^。！？\n]{0,24}(?:还|仍|依旧)"
    ),
)
UNDERSPECIFIED_ACTION_PATTERN = re.compile(
    r"^[^。！？\n]{0,8}(?:先|又|却|忽然|赶紧|直接)?"
    r"(?:按住|抓住|拿住|拦住|挡住|拉住|扶住|捏住|握住|压住|盖住|护住)"
    r"了?[。！？!?.]?$"
)
UNDERSPECIFIED_ACTION_FALLBACK_PATTERN = re.compile(
    r"^[^。！？\n]{0,8}(?:先|又|却|忽然|赶紧|直接)?"
    r"(?P<verb>[\u4e00-\u9fff]{1,2}住)了?[。！？!?.]?$"
)
INTRANSITIVE_OR_SELF_CONTAINED_ZHU_VERBS = {
    "站住", "停住", "愣住", "僵住", "忍住", "记住", "稳住", "挺住", "刹住",
}
BARE_STAGE_DIRECTION_PATTERN = re.compile(
    r"^[^，,。！？\n]{1,12}"
    r"(?:捏|拿|攥|握|抓|抱|端)着"
    r"[^。！？\n]{1,10}"
    r"(?:站直|站起来|起身|转身|抬头|低头)"
    r"(?:了)?[。！？!?.]?$"
)
BARE_STAGE_DIRECTION_FALLBACK_PATTERN = re.compile(
    r"^[^，,。！？\n]{1,12}[\u4e00-\u9fff]{1,2}着"
    r"[^。！？\n]{1,12}"
    r"(?:站直|站起来|起身|转身|回头|抬头|低头|侧身|上前|后退)"
    r"(?:了)?[。！？!?.]?$"
)
ACTION_CONTINUITY_VERBS = (
    "站起来", "站了起来", "转身", "回头", "按住", "抓住", "拦住", "挡住",
    "拉住", "扶住", "推开", "松开", "拿起", "拿走", "放下", "坐下",
)
TARGET_CHARACTER_PROFILE_FIELDS = (
    "attention_bias",
    "desire_and_shame",
    "defense_strategy",
    "speech_pattern",
    "misfire_pattern",
    "action_bias",
    "self_contradiction",
    "private_relation_language",
)
SECTION_CHARACTER_PLAN_FIELDS = (
    "scene_want",
    "attention_first",
    "misread_or_avoidance",
    "speech_boundary",
    "action_or_object_bias",
    "relationship_private_trigger",
    "generic_function_line_to_reject",
)


def ultra_fine_source_baseline_scaffold() -> dict[str, Any]:
    return {
        "methodology_reference_read": False,
        "annotation_unit": "sentence",
        "feature_inventory": list(ULTRA_FINE_FEATURE_IDS),
        "feature_assignment_policy": {
            "method": "",
            "mechanical_quota_or_rotation_used": None,
            "full_inventory_occurrence_required": None,
            "manual_judgment": "",
        },
        "source_passages": [],
        "distribution_baseline": {
            "measurement_method": "",
            "metrics": {},
            "interpretation": "",
            "mechanical_statistical_matching_forbidden": True,
        },
        "manual_judgment": "",
    }


def prose_liveliness_layer_scaffold() -> dict[str, Any]:
    return {
        "status": "pending",
        "source_extraction_mode": "current_model_manual",
        "primary_source_only": None,
        "asset_file": None,
        "asset_types": list(LIVELINESS_ASSET_TYPES),
        "assets": [],
        "stiffness_prohibitions": [],
        "manual_judgment": "",
    }


def section_liveliness_plan_scaffold() -> dict[str, Any]:
    return {
        "planned_before_draft": None,
        "asset_ids": [],
        **{field: "" for field in LIVELINESS_SECTION_PLAN_FIELDS},
        "stiffness_patterns_rejected": [],
        "manual_judgment": "",
    }


def explanatory_narration_candidate_quotes(section_text: str) -> list[str]:
    narration = re.sub(r"「[^」]*」|“[^”]*”", "", section_text)
    candidates: list[str] = []
    units = [
        unit.strip()
        for unit in re.findall(r"[^。！？\n]+[。！？]?", narration)
        if unit.strip()
    ]
    for index, quote in enumerate(units):
        if quote and any(
            pattern.search(quote)
            for pattern in EXPLANATORY_NARRATION_CANDIDATE_PATTERNS
        ):
            candidates.append(quote)
            continue
        if (
            ABSTRACT_EVENT_EVALUATION_PATTERN.search(quote)
            and index + 1 < len(units)
            and CONCRETE_FOLLOWUP_EVENT_PATTERN.search(units[index + 1])
        ):
            candidates.append(quote)
    return list(dict.fromkeys(candidates))


def semantic_candidate_review_scaffold(candidate_quotes: list[str]) -> dict[str, Any]:
    return {
        "automatic_candidate_quotes": candidate_quotes,
        "candidate_reviews": [
            {
                "quote": quote,
                "verdict": "pending",
                "observable_scene_basis": "",
                "source_chain_basis": "",
                "manual_judgment": "",
            }
            for quote in candidate_quotes
        ],
        "reviewed_full_section": None,
        "unresolved_residue": [],
        "manual_judgment": "",
    }


def section_liveliness_review_scaffold(
    explanatory_candidates: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "asset_ids_consumed": [],
        "target_quotes": [],
        "living_language_preserved": None,
        "author_summary_override": None,
        "stiffness_patterns_remaining": [],
        "explanatory_inference_review": semantic_candidate_review_scaffold(
            explanatory_candidates or []
        ),
        "manual_judgment": "",
    }


def character_personality_layer_scaffold() -> dict[str, Any]:
    return {
        "status": "pending",
        "source_extraction_mode": "current_model_manual",
        "primary_source_only": None,
        "asset_file": None,
        "asset_types": list(CHARACTER_PERSONALITY_ASSET_TYPES),
        "assets": [],
        "target_character_profiles": [],
        "manual_judgment": "",
    }


def section_character_plan_scaffold() -> dict[str, Any]:
    return {
        "planned_before_draft": None,
        "active_character_names": [],
        "participants": [],
        "interchangeability_risk": "",
        "manual_judgment": "",
    }


def abstract_dialogue_candidate_quotes(section_text: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"「([^」]+)」|“([^”]+)”", section_text):
        quote = next(group for group in match.groups() if group is not None).strip()
        if quote and (
            any(pattern.search(quote) for pattern in ABSTRACT_DIALOGUE_CANDIDATE_PATTERNS)
            or is_functionally_compressed_dialogue(quote)
            or is_elliptically_compressed_question_object(quote)
            or is_transfer_target_omitted_dialogue(quote)
            or is_signage_like_staff_dialogue(quote)
        ):
            candidates.append(quote)
    return list(dict.fromkeys(candidates))


def is_functionally_compressed_dialogue(quote: str) -> bool:
    """Flag one speech turn that compresses excuse, assignment, and deferred repair."""
    functional_categories = (
        FUNCTIONAL_DIALOGUE_JUSTIFICATION_PATTERN.search(quote),
        FUNCTIONAL_DIALOGUE_ASSIGNMENT_PATTERN.search(quote),
        FUNCTIONAL_DIALOGUE_DEFER_PATTERN.search(quote),
    )
    return all(functional_categories)


def is_elliptically_compressed_question_object(quote: str) -> bool:
    """Flag speech-act labels such as '我问座牌' that omit the actual question."""
    return bool(ELLIPTICAL_QUESTION_OBJECT_PATTERN.fullmatch(quote.strip()))


def is_transfer_target_omitted_dialogue(quote: str) -> bool:
    """Flag transfer questions that omit who receives the contested thing."""
    match = TRANSFER_TARGET_OMISSION_PATTERN.fullmatch(quote.strip())
    if not match:
        return False
    object_phrase = match.group("object_phrase").strip()
    return object_phrase not in {"我", "你", "他", "她", "它", "谁", "什么"}


def is_signage_like_staff_dialogue(quote: str) -> bool:
    """Flag staff speech that contains only an address, area, and prohibition."""
    match = STAFF_SIGNAGE_DIALOGUE_PATTERN.fullmatch(quote.strip())
    if not match:
        return False
    location = match.group("location")
    if re.match(r"^(?:我|你|他|她|咱们|我们)[^，,。！？]*$", location):
        return False
    return bool(re.search(r"(?:这|那|里|内|外|上|下|前|后|口|区|场|室|台|道|楼|门|院|店|厅|席|排|线)", location))


def hard_coordination_candidate_quotes(section_text: str) -> list[str]:
    candidates: list[str] = []
    for sentence in sentence_units(section_text):
        if any(pattern.search(sentence) for pattern in HARD_COORDINATION_CANDIDATE_PATTERNS):
            candidates.append(sentence)
    return list(dict.fromkeys(candidates))


def underspecified_action_candidate_quotes(section_text: str) -> list[str]:
    """Locate bare transitive-action labels whose object is absent from the sentence."""
    candidates: list[str] = []
    for sentence in sentence_units(section_text):
        stripped = sentence.strip()
        if UNDERSPECIFIED_ACTION_PATTERN.search(stripped):
            candidates.append(sentence)
            continue
        match = UNDERSPECIFIED_ACTION_FALLBACK_PATTERN.search(stripped)
        if match and match.group("verb") not in INTRANSITIVE_OR_SELF_CONTAINED_ZHU_VERBS:
            candidates.append(sentence)
    return candidates


def bare_stage_direction_candidate_quotes(section_text: str) -> list[str]:
    """Locate held-object plus posture-reset sentences that only bridge two shots."""
    return [
        sentence
        for sentence in sentence_units(section_text)
        if BARE_STAGE_DIRECTION_PATTERN.fullmatch(sentence.strip())
        or BARE_STAGE_DIRECTION_FALLBACK_PATTERN.fullmatch(sentence.strip())
    ]


def action_continuity_candidates(section_text: str) -> list[dict[str, str]]:
    """Find adjacent sentences repeating the same action without an explicit reason."""
    units = sentence_units(section_text)
    candidates: list[dict[str, str]] = []
    for previous, current in zip(units, units[1:]):
        previous_verb = next((verb for verb in ACTION_CONTINUITY_VERBS if verb in previous), "")
        current_verb = next((verb for verb in ACTION_CONTINUITY_VERBS if verb in current), "")
        if previous_verb and current_verb and previous_verb == current_verb:
            candidates.append({"previous": previous, "current": current, "verb": current_verb})
    return candidates


def explicit_relation_markers(text: str) -> list[str]:
    markers = [
        marker
        for marker in FUNCTION_WORD_FEATURE_MARKERS
        if len(marker) > 1 and marker in text
    ]
    if "却" in text:
        markers.append("却")
    for marker in ("而", "但"):
        if re.search(rf"(?:^|[，。！？；\n「『“‘]){marker}", text):
            markers.append(marker)
    if re.search(r"(?:^|[，。！？；\n「『“‘])可(?!以|能)", text):
        markers.append("可")
    return list(dict.fromkeys(markers))


def validate_annotation_feature_evidence(
    annotation: dict[str, Any],
    source_sentence: str,
    feature_ids: list[str],
    sentence_label: str,
    relation_markers: list[str],
    errors: list[str],
) -> None:
    evidence_items = annotation.get("feature_evidence")
    if not isinstance(evidence_items, list):
        errors.append(f"{sentence_label}.feature_evidence 必须逐特征绑定原句证据")
        return

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for evidence_index, item in enumerate(evidence_items, start=1):
        evidence_label = f"{sentence_label}.特征证据[{evidence_index}]"
        if not isinstance(item, dict):
            errors.append(f"{evidence_label} 必须是对象")
            continue
        if any(field not in item for field in FEATURE_EVIDENCE_FIELDS):
            errors.append(f"{evidence_label} 缺少 feature_id / source_evidence / mechanism")
            continue
        feature_id = str(item.get("feature_id") or "").strip()
        source_evidence = str(item.get("source_evidence") or "").strip()
        mechanism = str(item.get("mechanism") or "").strip()
        if not feature_id or feature_id in evidence_by_id:
            errors.append(f"{evidence_label}.feature_id 为空或重复")
            continue
        evidence_by_id[feature_id] = item
        if not source_evidence or source_evidence not in source_sentence:
            errors.append(f"{evidence_label}.source_evidence 必须原样存在于当前源句")
        if len(mechanism) < 12:
            errors.append(f"{evidence_label}.mechanism 必须具体说明该特征怎样在当前句中运作")

    if set(evidence_by_id) != set(feature_ids):
        errors.append(f"{sentence_label}.feature_evidence 必须与 feature_ids 一一对应")

    if relation_markers:
        for feature_id in ("LM-02", "SC-05"):
            item = evidence_by_id.get(feature_id) or {}
            source_evidence = str(item.get("source_evidence") or "").strip()
            if not any(marker in source_evidence for marker in relation_markers):
                errors.append(
                    f"{sentence_label}.{feature_id} 必须直接引用显式关系词作为原句证据"
                )


def section_character_vitality_review_scaffold(
    dialogue_candidates: list[str] | None = None,
    dialogue_turns: list[str] | None = None,
) -> dict[str, Any]:
    dialogue_candidates = dialogue_candidates or []
    dialogue_turns = dialogue_turns or []
    return {
        "character_reviews": [],
        "interchangeability_test": "",
        "functional_character_residue": [],
        "dialogue_grounding_review": {
            "automatic_candidate_quotes": dialogue_candidates,
            "candidate_reviews": [
                {
                    "quote": quote,
                    "verdict": "pending",
                    "concrete_pressure_or_object": "",
                    "character_specific_mechanism": "",
                    "manual_judgment": "",
                }
                for quote in dialogue_candidates
            ],
            "full_dialogue_reviews": [
                {
                    "quote": quote,
                    "speaker_and_scene_role": "",
                    "context_window": "",
                    "utterance_goal": "",
                    "adjacency_or_reply_fit": "",
                    "time_state_fit": "",
                    "object_and_result_complete": "",
                    "participant_role_direction": "",
                    "character_specificity": "",
                    "verdict": "pending",
                    "manual_judgment": "",
                }
                for quote in dialogue_turns
            ],
            "reviewed_all_character_dialogue": None,
            "candidate_zero_is_not_pass": None,
            "abstract_summary_reply_residue": [],
            "manual_judgment": "",
        },
        "manual_judgment": "",
    }


def character_evidence_ownership_review_scaffold() -> dict[str, Any]:
    return {
        "quote": "",
        "owner_name": "",
        "ownership_context": "",
        "actor_or_speaker_marker": "",
        "marker_refers_to_owner": None,
        "other_character_action_misassigned": None,
        "manual_judgment": "",
    }


def section_sentence_relation_review_scaffold(
    candidate_quotes: list[str] | None = None,
) -> dict[str, Any]:
    candidate_quotes = candidate_quotes or []
    return {
        "automatic_candidate_quotes": candidate_quotes,
        "candidate_reviews": [
            {
                "quote": quote,
                "verdict": "pending",
                "relation_type": "",
                "marking_mode": "",
                "source_relation_basis": "",
                "manual_judgment": "",
            }
            for quote in candidate_quotes
        ],
        "reviewed_full_section": None,
        "mechanical_marker_insertion_used": None,
        "unresolved_residue": [],
        "manual_judgment": "",
    }


def action_continuity_review_scaffold(section_text: str) -> dict[str, Any]:
    underspecified = underspecified_action_candidate_quotes(section_text)
    bare_stage_directions = bare_stage_direction_candidate_quotes(section_text)
    repeated = action_continuity_candidates(section_text)
    return {
        "underspecified_action_candidates": underspecified,
        "underspecified_action_reviews": [
            {
                "quote": quote,
                "actor_marker": "",
                "object_or_target": "",
                "visible_change": "",
                "verdict": "pending",
                "manual_judgment": "",
            }
            for quote in underspecified
        ],
        "bare_stage_direction_candidates": bare_stage_directions,
        "bare_stage_direction_reviews": [
            {
                "quote": quote,
                "held_object": "",
                "posture_reset": "",
                "direction_or_pressure": "",
                "visible_change": "",
                "verdict": "pending",
                "manual_judgment": "",
            }
            for quote in bare_stage_directions
        ],
        "repeated_action_candidates": repeated,
        "repeated_action_reviews": [
            {
                **candidate,
                "distinction_or_reason": "",
                "visible_change": "",
                "verdict": "pending",
                "manual_judgment": "",
            }
            for candidate in repeated
        ],
        "reviewed_full_section": None,
        "manual_judgment": "",
    }


def section_generation_plan_scaffold(section_id: str) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "status": "pending",
        "planned_before_draft": None,
        "generation_driver": "",
        "single_sentence_features_secondary": None,
        "continuous_source_chain_packets": [],
        "contrastive_examples": [],
        "relation_micro_examples": [],
        "dialogue_voice_packets": [],
        "source_passage_ids": [],
        "sentence_mechanisms": [],
        "paragraph_plan": {field: "" for field in SECTION_PARAGRAPH_PLAN_FIELDS},
        "window_plan": {field: "" for field in SECTION_WINDOW_PLAN_FIELDS},
        "liveliness_plan": section_liveliness_plan_scaffold(),
        "character_plan": section_character_plan_scaffold(),
        "surface_copy_rejected": None,
        "manual_judgment": "",
    }


def target_sentence_mapping_scaffold() -> dict[str, Any]:
    return {
        "target_sentence": "",
        "source_anchor_sentence": "",
        "feature_ids": [],
        "target_surface_evidence": "",
        "source_surface_evidence": "",
        "language_mechanism_match": "",
        "minimal_function_sentence_review": {
            "detected": None,
            "source_parallel_quote": "",
            "relation_change": "",
            "personality_or_body_specificity": "",
            "verdict": "pending",
            "manual_judgment": "",
        },
        **{field: "" for field in TARGET_SENTENCE_MAPPING_FIELDS},
        "contract_used_during_writing": None,
        "surface_copy_rejected": None,
    }


def compact_prose_unit(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", str(text or ""), flags=re.UNICODE)


def is_minimal_function_sentence(text: str) -> bool:
    compact = compact_prose_unit(text)
    return 0 < len(compact) <= 6


def normalized_manual_text(value: Any) -> str:
    """Normalize identifiers away so templated semantic judgments compare equal."""
    text = str(value or "").strip().lower()
    text = re.sub(r"sf[-_ ]?\d+", "<sf>", text, flags=re.IGNORECASE)
    text = re.sub(r"第?\s*\d+\s*节", "<section>", text)
    for field in (*SOURCE_STYLE_GRANULARITY_FIELDS, *REQUIRED_DIMENSIONS):
        text = text.replace(field.lower(), "<field>")
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_file_path(left: Path, right: Path) -> bool:
    left_resolved = left.resolve()
    right_resolved = right.resolve()
    try:
        return left_resolved.samefile(right_resolved)
    except (FileNotFoundError, OSError):
        return left_resolved == right_resolved


def subflow_catalog_path(source: Path) -> Path:
    return source.parent.parent / "写作资产" / "子流程索引.jsonl"


def subflow_records_from_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"主体原文子流程索引不存在: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"子流程索引 JSONL 第 {line_number} 行无效: {path}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"子流程索引第 {line_number} 行必须是对象: {path}")
        records.append(record)
    if not records:
        raise ValueError(f"主体原文子流程索引为空: {path}")
    return records


def source_subflow_review_scaffold(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "subflow_id": record.get("subflow_id", ""),
        "parent_bridge_id": record.get("parent_bridge_id", ""),
        "source_range": record.get("source_range", ""),
        "source_style_granularity": record.get("source_style_granularity", {}),
        "status": "pending",
        "target_sections": [],
        "target_section_rationale": "",
        "semantic_review_method": "current_model_manual",
        "automation_used_for_semantic_judgment": None,
        "dimension_transfers": {
            field: {
                "source_evidence": nonempty_strings(
                    (record.get("source_style_granularity") or {}).get(field, {}).get(
                        "source_evidence"
                    )
                ),
                "evidence_mappings": [
                    {
                        "source_quote": quote,
                        "target_quotes": [],
                        "comparison": "",
                    }
                    for quote in nonempty_strings(
                        (record.get("source_style_granularity") or {})
                        .get(field, {})
                        .get("source_evidence")
                    )
                ],
                "target_quotes": [],
                "comparison": "",
                "cross_dimension_reuse_justification": "",
                "surface_copy_rejected": None,
            }
            for field in SOURCE_STYLE_GRANULARITY_FIELDS
        },
        "source_voice_preserved": None,
        "functional_alignment_used_as_prose_proof": None,
        "extra_ai_shell": None,
        "manual_judgment": "",
    }


def create_receipt(project: str, source_original: Path) -> dict[str, Any]:
    source = source_original.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"主体原文不存在: {source}")
    subflow_catalog = subflow_catalog_path(source)
    subflow_records = subflow_records_from_catalog(subflow_catalog)
    subflow_ids = [str(record.get("subflow_id") or "").strip() for record in subflow_records]
    if any(not subflow_id for subflow_id in subflow_ids) or len(set(subflow_ids)) != len(subflow_ids):
        raise ValueError(f"主体原文子流程索引存在空或重复 subflow_id: {subflow_catalog}")
    return {
        "version": "2.5",
        "project": project,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_status": "pending",
        "prewrite_status": "pending",
        "execution_mode": "current_model_manual",
        "reviewed_by_current_model": False,
        "primary_prose_source": {
            "path": str(source),
            "sha256": sha256(source),
            "role": "primary_only",
        },
        "auxiliary_sources_supply_prose": False,
        "primary_subflow_catalog": {
            "path": str(subflow_catalog.resolve()),
            "sha256": sha256(subflow_catalog),
            "required_subflow_ids": subflow_ids,
        },
        "source_baseline": {
            "continuous_excerpts": [],
            "dimensions": {
                name: {
                    "rule": "",
                    "source_quotes": [],
                    "transfer_rule": "",
                    "ai_drift_to_reject": "",
                }
                for name in REQUIRED_DIMENSIONS
            },
            "anti_patterns": [],
            "manual_judgment": "",
        },
        "ultra_fine_source_baseline": ultra_fine_source_baseline_scaffold(),
        "prose_liveliness_layer": prose_liveliness_layer_scaffold(),
        "character_personality_layer": character_personality_layer_scaffold(),
        "outline": None,
        "section_generation_plans": [],
        "calibration_samples": [],
        "draft": None,
        "rewrite_scope_review": None,
        "manual_review_provenance": None,
        "section_reviews": [],
        "source_subflow_reviews": [
            source_subflow_review_scaffold(record) for record in subflow_records
        ],
        "character_arc_reviews": [],
        "full_text_review": {
            "reviewed_full_text": False,
            "all_sections_reviewed": False,
            "primary_source_voice_dominant": False,
            "auxiliary_style_contamination": None,
            "functional_alignment_used_as_prose_proof": None,
            "remaining_extra_ai_shell": None,
            "character_personality_dominant": None,
            "conclusion": "",
        },
        "blocking_failures": [],
    }


def nonempty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def validate_source_binding(
    data: dict[str, Any], source_original: Path, errors: list[str]
) -> str:
    source = source_original.resolve()
    if not source.is_file():
        errors.append(f"主体原文不存在: {source}")
        return ""
    binding = data.get("primary_prose_source")
    if not isinstance(binding, dict):
        errors.append("primary_prose_source 必须是对象")
        return read_text(source)
    if not same_file_path(Path(str(binding.get("path") or "")), source):
        errors.append("文字颗粒度合同绑定的主体原文路径不一致")
    if binding.get("sha256") != sha256(source):
        errors.append("主体原文已变化，必须重建文字颗粒度合同")
    if binding.get("role") != "primary_only":
        errors.append("主体原文必须是唯一 prose source")
    return read_text(source)


def validate_source_quote(
    quote: str, source_text: str, label: str, errors: list[str]
) -> bool:
    if not quote or quote not in source_text:
        errors.append(f"{label}不是主体原文真实连续引用")
        return False
    return True


def validate_subflow_catalog_data(
    data: dict[str, Any],
    source_original: Path,
    source_text: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    source = source_original.resolve()
    expected_path = subflow_catalog_path(source).resolve()
    binding = data.get("primary_subflow_catalog")
    if not isinstance(binding, dict):
        errors.append("primary_subflow_catalog 必须绑定主体子流程索引")
        return []
    if not same_file_path(Path(str(binding.get("path") or "")), expected_path):
        errors.append("文字颗粒度合同绑定的主体子流程索引路径不一致")
    if not expected_path.is_file():
        errors.append(f"主体原文子流程索引不存在: {expected_path}")
        return []
    if binding.get("sha256") != sha256(expected_path):
        errors.append("主体子流程索引已变化，必须重建文字颗粒度合同")
    try:
        records = subflow_records_from_catalog(expected_path)
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
        return []
    ids: list[str] = []
    for index, record in enumerate(records, start=1):
        label = f"主体子流程[{index}]"
        subflow_id = str(record.get("subflow_id") or "").strip()
        if not subflow_id:
            errors.append(f"{label}.subflow_id 不能为空")
        ids.append(subflow_id)
        style = record.get("source_style_granularity")
        if not isinstance(style, dict):
            errors.append(f"{label}.source_style_granularity 必须是对象")
            continue
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            item = style.get(field)
            if not isinstance(item, dict):
                errors.append(f"{label} 缺少六类颗粒字段: {field}")
                continue
            if not str(item.get("analysis") or "").strip():
                errors.append(f"{label}.{field}.analysis 不能为空")
            evidence = nonempty_strings(item.get("source_evidence"))
            if len(evidence) < 2:
                errors.append(f"{label}.{field}.source_evidence 至少两条")
            for quote in evidence:
                validate_source_quote(quote, source_text, f"{label}.{field}", errors)
    if len(set(ids)) != len(ids):
        errors.append("主体子流程索引 subflow_id 不得重复")
    if binding.get("required_subflow_ids") != ids:
        errors.append("primary_subflow_catalog.required_subflow_ids 必须覆盖全部 SF")
    return records


def sentence_units(text: str) -> list[str]:
    units: list[str] = []
    buffer: list[str] = []
    pending_terminal = False
    for char in text:
        if char.isspace() and not buffer:
            continue
        if pending_terminal and char not in "」』”’":
            unit = "".join(buffer).strip()
            if unit:
                units.append(unit)
            buffer = []
            pending_terminal = False
            if char.isspace():
                continue
        buffer.append(char)
        if char in "。！？?!":
            pending_terminal = True
        elif pending_terminal and char in "」』”’":
            unit = "".join(buffer).strip()
            if unit:
                units.append(unit)
            buffer = []
            pending_terminal = False
    unit = "".join(buffer).strip()
    if unit:
        units.append(unit)
    return units


def dialogue_turn_units(text: str) -> list[str]:
    """Return direct-speech turns with their original Chinese quote marks."""
    return [
        match.group(0).strip()
        for match in re.finditer(r"[「『][^」』]{2,}[」』]", text, flags=re.DOTALL)
        if match.group(0).strip()
    ]


def validate_ultra_fine_source_baseline(
    data: dict[str, Any], source_text: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    if data.get("version") != "2.5":
        errors.append("超细文字颗粒度契约版本必须为 2.5")
    baseline = data.get("ultra_fine_source_baseline")
    if not isinstance(baseline, dict):
        errors.append("ultra_fine_source_baseline 必须是对象")
        return {}
    if baseline.get("methodology_reference_read") is not True:
        errors.append("必须阅读超细颗粒度方法 reference")
    if baseline.get("annotation_unit") != "sentence":
        errors.append("超细源文标注单位必须为 sentence")
    if baseline.get("feature_inventory") != list(ULTRA_FINE_FEATURE_IDS):
        errors.append("超细契约必须完整绑定 52 项特征库")

    assignment_policy = baseline.get("feature_assignment_policy")
    if not isinstance(assignment_policy, dict):
        errors.append("ultra_fine_source_baseline.feature_assignment_policy 必须是对象")
    else:
        if assignment_policy.get("method") != "current_model_sentence_semantic":
            errors.append("超细特征必须由当前模型按句面语义逐句判断")
        if assignment_policy.get("mechanical_quota_or_rotation_used") is not False:
            errors.append("禁止按配额、序号或轮转方式分派 52 项特征")
        if assignment_policy.get("full_inventory_occurrence_required") is not False:
            errors.append("绑定 52 项特征库不等于强制 52 项都在样本中出现")
        if len(str(assignment_policy.get("manual_judgment") or "").strip()) < 20:
            errors.append("feature_assignment_policy.manual_judgment 必须说明语义标注方法")

    passages = baseline.get("source_passages")
    passage_map: dict[str, dict[str, Any]] = {}
    purposes: set[str] = set()
    annotation_signatures: dict[str, list[str]] = {}
    feature_occurrence_counts = {feature_id: 0 for feature_id in ULTRA_FINE_FEATURE_IDS}
    if not isinstance(passages, list) or len(passages) < 5:
        errors.append("超细写前基线至少需要 5 组连续原文逐句标注")
        passages = []
    for index, passage in enumerate(passages, start=1):
        label = f"超细原文段[{index}]"
        if not isinstance(passage, dict):
            errors.append(f"{label} 必须是对象")
            continue
        passage_id = str(passage.get("id") or "").strip()
        quote = str(passage.get("quote") or "").strip()
        purpose = str(passage.get("purpose") or "").strip()
        if not passage_id or passage_id in passage_map:
            errors.append(f"{label}.id 为空或重复")
            continue
        passage_map[passage_id] = passage
        if len(quote) < 80 or quote not in source_text:
            errors.append(f"{label}.quote 必须是 80 字以上的连续主体原文")
        if not purpose:
            errors.append(f"{label}.purpose 不能为空")
        else:
            purposes.add(purpose)
        annotations = passage.get("sentence_annotations")
        if not isinstance(annotations, list):
            errors.append(f"{label}.sentence_annotations 必须是列表")
            continue
        expected_units = sentence_units(quote)
        annotated_units = [
            str(item.get("source_sentence") or "").strip()
            for item in annotations
            if isinstance(item, dict)
        ]
        if annotated_units != expected_units:
            errors.append(f"{label} 必须按顺序逐句覆盖连续原文，不得抽样")
        for sentence_index, annotation in enumerate(annotations, start=1):
            sentence_label = f"{label}.句[{sentence_index}]"
            if not isinstance(annotation, dict):
                errors.append(f"{sentence_label} 必须是对象")
                continue
            source_sentence = str(annotation.get("source_sentence") or "").strip()
            if not source_sentence or source_sentence not in quote:
                errors.append(f"{sentence_label}.source_sentence 不在该连续原文中")
            feature_ids = nonempty_strings(annotation.get("feature_ids"))
            if not feature_ids or any(
                feature_id not in ULTRA_FINE_FEATURE_IDS for feature_id in feature_ids
            ):
                errors.append(f"{sentence_label}.feature_ids 必须引用 52 项特征库")
            for feature_id in set(feature_ids):
                if feature_id in feature_occurrence_counts:
                    feature_occurrence_counts[feature_id] += 1
            relation_markers = explicit_relation_markers(source_sentence)
            if relation_markers and "LM-02" not in feature_ids:
                errors.append(
                    f"{sentence_label} 含显式关系词 {relation_markers}，feature_ids 必须包含 LM-02"
                )
            if relation_markers and "SC-05" not in feature_ids:
                errors.append(
                    f"{sentence_label} 含显式关系词 {relation_markers}，feature_ids 必须包含 SC-05"
                )
            validate_annotation_feature_evidence(
                annotation,
                source_sentence,
                feature_ids,
                sentence_label,
                relation_markers,
                errors,
            )
            for field in SOURCE_SENTENCE_ANNOTATION_FIELDS:
                value = str(annotation.get(field) or "").strip()
                if len(value) < 8:
                    errors.append(f"{sentence_label}.{field} 必须具体标注")
                elif field not in ("transfer_constraint", "permitted_deviation"):
                    annotation_signatures.setdefault(
                        normalized_manual_text(value), []
                    ).append(f"{passage_id}:{sentence_index}:{field}")
    if len(purposes) < 4:
        errors.append("超细连续原文必须覆盖至少 4 类场景")
    for labels in annotation_signatures.values():
        if len(labels) > 2:
            errors.append("超细逐句标注不得大面积复用模板: " + ", ".join(labels[:6]))

    used_feature_counts = [count for count in feature_occurrence_counts.values() if count > 0]
    single_occurrence_count = sum(count == 1 for count in used_feature_counts)
    if (
        len(used_feature_counts) == len(ULTRA_FINE_FEATURE_IDS)
        and single_occurrence_count >= len(ULTRA_FINE_FEATURE_IDS) - 8
    ):
        errors.append("52 项特征呈近乎各一次的配额覆盖指纹，必须按真实句面重新语义标注")

    distribution = baseline.get("distribution_baseline")
    if not isinstance(distribution, dict):
        errors.append("distribution_baseline 必须是对象")
    else:
        if not str(distribution.get("measurement_method") or "").strip():
            errors.append("distribution_baseline.measurement_method 不能为空")
        metrics = distribution.get("metrics")
        required_metrics = (
            "non_whitespace_chars",
            "sentence_count",
            "sentence_length_median",
            "sentence_length_p90",
            "question_count",
            "ellipsis_count",
            "paragraph_length_median",
            "function_word_counts",
        )
        if not isinstance(metrics, dict):
            errors.append("distribution_baseline.metrics 必须是对象")
        else:
            for field in required_metrics:
                if field not in metrics or metrics.get(field) in (None, "", {}):
                    errors.append(f"distribution_baseline.metrics.{field} 不能为空")
        if len(str(distribution.get("interpretation") or "").strip()) < 20:
            errors.append("distribution_baseline.interpretation 必须解释分布而非只报数")
        if distribution.get("mechanical_statistical_matching_forbidden") is not True:
            errors.append("禁止机械对齐主体原文统计量")
    if len(str(baseline.get("manual_judgment") or "").strip()) < 20:
        errors.append("ultra_fine_source_baseline.manual_judgment 不能为空")
    return passage_map


def validate_prose_liveliness_layer(
    data: dict[str, Any], source_text: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    layer = data.get("prose_liveliness_layer")
    if not isinstance(layer, dict):
        errors.append("prose_liveliness_layer 必须是对象")
        return {}
    if layer.get("status") != "passed":
        errors.append("prose_liveliness_layer.status 必须为 passed")
    if layer.get("source_extraction_mode") != "current_model_manual":
        errors.append("成文活性资产必须由当前模型人工提取")
    if layer.get("primary_source_only") is not True:
        errors.append("成文活性资产只能来自主体原文")
    if layer.get("asset_types") != list(LIVELINESS_ASSET_TYPES):
        errors.append("成文活性层必须完整覆盖七类资产")

    binding = layer.get("asset_file")
    if not isinstance(binding, dict):
        errors.append("prose_liveliness_layer.asset_file 必须绑定落盘资产")
    else:
        asset_path = Path(str(binding.get("path") or "")).resolve()
        if not asset_path.is_file():
            errors.append(f"成文活性资产文件不存在: {asset_path}")
        elif binding.get("sha256") != sha256(asset_path):
            errors.append("成文活性资产文件已变化，必须重新绑定")

    assets = layer.get("assets")
    if not isinstance(assets, list):
        errors.append("prose_liveliness_layer.assets 必须是列表")
        assets = []
    asset_map: dict[str, dict[str, Any]] = {}
    type_counts = {asset_type: 0 for asset_type in LIVELINESS_ASSET_TYPES}
    for index, asset in enumerate(assets, start=1):
        label = f"成文活性资产[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{label} 必须是对象")
            continue
        asset_id = str(asset.get("id") or "").strip()
        asset_type = str(asset.get("type") or "").strip()
        if not asset_id or asset_id in asset_map:
            errors.append(f"{label}.id 为空或重复")
            continue
        asset_map[asset_id] = asset
        if asset_type not in LIVELINESS_ASSET_TYPES:
            errors.append(f"{label}.type 不在七类活性资产中")
        else:
            type_counts[asset_type] += 1
        source_quote = str(asset.get("source_quote") or "").strip()
        validate_source_quote(source_quote, source_text, f"{label}.source_quote", errors)
        for field in ("live_core", "transfer_mechanism", "surface_copy_boundary"):
            if len(str(asset.get(field) or "").strip()) < 8:
                errors.append(f"{label}.{field} 必须具体")
        if asset.get("surface_copy_rejected") is not True:
            errors.append(f"{label}.surface_copy_rejected 必须为 true")
    for asset_type, count in type_counts.items():
        if count < 3:
            errors.append(f"成文活性资产 {asset_type} 至少需要 3 条")

    prohibitions = layer.get("stiffness_prohibitions")
    if not isinstance(prohibitions, list) or len(prohibitions) < 6:
        errors.append("成文活性层至少需要 6 条僵硬句面禁用项")
    else:
        for index, item in enumerate(prohibitions, start=1):
            label = f"僵硬句面禁用项[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} 必须是对象")
                continue
            for field in ("pattern", "why_stiff", "replacement_action"):
                if len(str(item.get(field) or "").strip()) < 8:
                    errors.append(f"{label}.{field} 必须具体")
    if len(str(layer.get("manual_judgment") or "").strip()) < 20:
        errors.append("prose_liveliness_layer.manual_judgment 必须说明活性来源")
    return asset_map


def validate_character_personality_layer(
    data: dict[str, Any], source_text: str, errors: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    layer = data.get("character_personality_layer")
    if not isinstance(layer, dict):
        errors.append("character_personality_layer 必须是对象")
        return {}, {}
    if layer.get("status") != "passed":
        errors.append("character_personality_layer.status 必须为 passed")
    if layer.get("source_extraction_mode") != "current_model_manual":
        errors.append("人物性格颗粒必须由当前模型从主体原文人工提取")
    if layer.get("primary_source_only") is not True:
        errors.append("人物性格颗粒只能来自主体原文")
    if layer.get("asset_types") != list(CHARACTER_PERSONALITY_ASSET_TYPES):
        errors.append("人物性格颗粒必须完整覆盖七类资产")

    binding = layer.get("asset_file")
    if not isinstance(binding, dict):
        errors.append("character_personality_layer.asset_file 必须绑定落盘资产")
    else:
        asset_path = Path(str(binding.get("path") or "")).resolve()
        if not asset_path.is_file():
            errors.append(f"人物性格颗粒资产文件不存在: {asset_path}")
        elif binding.get("sha256") != sha256(asset_path):
            errors.append("人物性格颗粒资产文件已变化，必须重新绑定")

    assets = layer.get("assets")
    if not isinstance(assets, list):
        errors.append("character_personality_layer.assets 必须是列表")
        assets = []
    asset_map: dict[str, dict[str, Any]] = {}
    type_counts = {asset_type: 0 for asset_type in CHARACTER_PERSONALITY_ASSET_TYPES}
    for index, asset in enumerate(assets, start=1):
        label = f"人物性格颗粒资产[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{label} 必须是对象")
            continue
        asset_id = str(asset.get("id") or "").strip()
        asset_type = str(asset.get("type") or "").strip()
        if not asset_id or asset_id in asset_map:
            errors.append(f"{label}.id 为空或重复")
            continue
        asset_map[asset_id] = asset
        if asset_type not in CHARACTER_PERSONALITY_ASSET_TYPES:
            errors.append(f"{label}.type 不在七类人物性格颗粒中")
        else:
            type_counts[asset_type] += 1
        source_quotes = nonempty_strings(asset.get("source_quotes"))
        if len(source_quotes) < 2:
            errors.append(f"{label}.source_quotes 至少需要 2 条主体原文证据")
        for quote in source_quotes:
            validate_source_quote(quote, source_text, f"{label}.source_quotes", errors)
        for field in ("personality_core", "transfer_mechanism", "surface_copy_boundary"):
            if len(str(asset.get(field) or "").strip()) < 8:
                errors.append(f"{label}.{field} 必须具体")
        if asset.get("surface_copy_rejected") is not True:
            errors.append(f"{label}.surface_copy_rejected 必须为 true")
    for asset_type, count in type_counts.items():
        if count < 3:
            errors.append(f"人物性格颗粒 {asset_type} 至少需要 3 条")

    profiles = layer.get("target_character_profiles")
    if not isinstance(profiles, list) or len(profiles) < 2:
        errors.append("target_character_profiles 至少需要主角和一名核心对手/关系人")
        profiles = []
    profile_map: dict[str, dict[str, Any]] = {}
    profile_signatures: dict[str, list[str]] = {}
    protagonist_names: list[str] = []
    for index, profile in enumerate(profiles, start=1):
        label = f"目标人物母版[{index}]"
        if not isinstance(profile, dict):
            errors.append(f"{label} 必须是对象")
            continue
        name = str(profile.get("name") or "").strip()
        role = str(profile.get("role") or "").strip()
        if not name or name in profile_map:
            errors.append(f"{label}.name 为空或重复")
            continue
        profile_map[name] = profile
        if len(role) < 2:
            errors.append(f"{label}.role 不能为空")
        if role == "protagonist":
            protagonist_names.append(name)
        source_asset_ids = nonempty_strings(profile.get("source_asset_ids"))
        if len(source_asset_ids) < 5 or any(item not in asset_map for item in source_asset_ids):
            errors.append(f"{label}.source_asset_ids 至少绑定 5 条有效原文性格颗粒")
        covered_types = {
            str(asset_map[item].get("type") or "")
            for item in source_asset_ids
            if item in asset_map
        }
        if len(covered_types) < 4:
            errors.append(f"{label} 至少消费 4 类原文性格颗粒")
        signature_parts: list[str] = []
        for field in TARGET_CHARACTER_PROFILE_FIELDS:
            value = str(profile.get(field) or "").strip()
            if len(value) < 8:
                errors.append(f"{label}.{field} 必须具体且不可互换")
            if field in ("defense_strategy", "speech_pattern", "action_bias", "self_contradiction"):
                signature_parts.append(normalized_manual_text(value))
        profile_signatures.setdefault("|".join(signature_parts), []).append(name)
        if len(nonempty_strings(profile.get("generic_shells_rejected"))) < 3:
            errors.append(f"{label}.generic_shells_rejected 至少拒绝 3 类功能人物壳")
        if profile.get("surface_copy_rejected") is not True:
            errors.append(f"{label}.surface_copy_rejected 必须为 true")
        if len(str(profile.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{label}.manual_judgment 必须说明人物为何不可替换")
    if len(protagonist_names) != 1:
        errors.append("target_character_profiles 必须且只能有一名 role=protagonist")
    for names in profile_signatures.values():
        if len(names) > 1:
            errors.append("核心人物母版不得复用同一性格壳: " + ", ".join(names))
    if len(str(layer.get("manual_judgment") or "").strip()) < 20:
        errors.append("character_personality_layer.manual_judgment 必须说明迁移裁决")
    return asset_map, profile_map


def validate_section_character_plan(
    plan: dict[str, Any],
    label: str,
    personality_assets: dict[str, dict[str, Any]],
    character_profiles: dict[str, dict[str, Any]],
    errors: list[str],
) -> bool:
    character_plan = plan.get("character_plan")
    if not isinstance(character_plan, dict):
        errors.append(f"{label}.character_plan 必须是对象")
        return False
    valid = True
    if character_plan.get("planned_before_draft") is not True:
        errors.append(f"{label}.character_plan 必须在正文前完成")
        valid = False
    active_names = nonempty_strings(character_plan.get("active_character_names"))
    participants = character_plan.get("participants")
    if not isinstance(participants, list) or not participants:
        errors.append(f"{label}.character_plan.participants 不能为空")
        participants = []
        valid = False
    participant_names: list[str] = []
    participant_signatures: dict[str, list[str]] = {}
    for index, participant in enumerate(participants, start=1):
        item_label = f"{label}.人物计划[{index}]"
        if not isinstance(participant, dict):
            errors.append(f"{item_label} 必须是对象")
            valid = False
            continue
        name = str(participant.get("character_name") or "").strip()
        participant_names.append(name)
        profile = character_profiles.get(name)
        if profile is None:
            errors.append(f"{item_label}.character_name 未绑定目标人物母版: {name}")
            valid = False
            continue
        source_asset_ids = nonempty_strings(participant.get("source_asset_ids"))
        profile_asset_ids = set(nonempty_strings(profile.get("source_asset_ids")))
        if len(source_asset_ids) < 2 or any(
            item not in personality_assets or item not in profile_asset_ids
            for item in source_asset_ids
        ):
            errors.append(f"{item_label}.source_asset_ids 至少消费母版中的 2 条原文颗粒")
            valid = False
        signature_parts: list[str] = []
        for field in SECTION_CHARACTER_PLAN_FIELDS:
            value = str(participant.get(field) or "").strip()
            if len(value) < 8:
                errors.append(f"{item_label}.{field} 必须具体")
                valid = False
            if field in ("misread_or_avoidance", "speech_boundary", "action_or_object_bias"):
                signature_parts.append(normalized_manual_text(value))
        participant_signatures.setdefault("|".join(signature_parts), []).append(name)
    if set(active_names) != set(participant_names) or len(active_names) != len(set(active_names)):
        errors.append(f"{label}.active_character_names 必须与人物计划逐一一致且不重复")
        valid = False
    protagonist_names = {
        name for name, profile in character_profiles.items() if profile.get("role") == "protagonist"
    }
    if not protagonist_names.intersection(active_names):
        errors.append(f"{label}.character_plan 必须包含主角")
        valid = False
    for names in participant_signatures.values():
        if len(names) > 1:
            errors.append(f"{label} 同场人物不得复用同一反应方案: " + ", ".join(names))
            valid = False
    if len(str(character_plan.get("interchangeability_risk") or "").strip()) < 12:
        errors.append(f"{label}.character_plan.interchangeability_risk 必须具体")
        valid = False
    if len(str(character_plan.get("manual_judgment") or "").strip()) < 20:
        errors.append(f"{label}.character_plan.manual_judgment 必须说明人物如何进入场戏")
        valid = False
    return valid


def validate_outline_generation_plans(
    data: dict[str, Any],
    outline_path: Path | None,
    source_text: str,
    passage_map: dict[str, dict[str, Any]],
    liveliness_assets: dict[str, dict[str, Any]],
    personality_assets: dict[str, dict[str, Any]],
    character_profiles: dict[str, dict[str, Any]],
    errors: list[str],
) -> int:
    binding = data.get("outline")
    if not isinstance(binding, dict):
        errors.append("超细文字契约必须在写正文前 bind-outline")
        return 0
    bound_path = Path(str(binding.get("path") or "")).resolve()
    if outline_path is not None and not same_file_path(bound_path, outline_path):
        errors.append("超细文字契约绑定的细纲路径不一致")
    if not bound_path.is_file():
        errors.append(f"超细文字契约绑定细纲不存在: {bound_path}")
        return 0
    if binding.get("sha256") != sha256(bound_path):
        errors.append("细纲已变化，必须重新生成逐节落笔包")
    sections = extract_sections(read_text(bound_path))
    plans = data.get("section_generation_plans")
    if not isinstance(plans, list):
        errors.append("section_generation_plans 必须是列表")
        return 0
    plan_map = {
        str(item.get("section_id") or ""): item
        for item in plans
        if isinstance(item, dict) and str(item.get("section_id") or "")
    }
    for section_id in sorted(set(sections) - set(plan_map)):
        errors.append(f"正文落笔前缺少小节颗粒度包: {section_id}")
    for section_id in sorted(set(plan_map) - set(sections)):
        errors.append(f"颗粒度包引用不存在的细纲小节: {section_id}")
    passed = 0
    judgment_signatures: dict[str, list[str]] = {}
    for section_id, section_text in sections.items():
        plan = plan_map.get(section_id)
        if not plan:
            continue
        label = f"第 {section_id} 节落笔包"
        valid = True
        if plan.get("status") != "passed" or plan.get("planned_before_draft") is not True:
            errors.append(f"{label} 必须在写正文前完成并通过")
            valid = False
        if plan.get("generation_driver") != "continuous_source_chain":
            errors.append(f"{label}.generation_driver 必须为 continuous_source_chain")
            valid = False
        if plan.get("single_sentence_features_secondary") is not True:
            errors.append(f"{label} 必须把单句特征和 52 项标签降为辅助核对")
            valid = False
        chain_packets = plan.get("continuous_source_chain_packets")
        if not isinstance(chain_packets, list) or len(chain_packets) < 2:
            errors.append(f"{label}.continuous_source_chain_packets 至少需要 2 组连续原文句链")
            chain_packets = []
            valid = False
        packet_excerpts: list[str] = []
        packet_signatures: dict[str, list[int]] = {}
        for packet_index, packet in enumerate(chain_packets, start=1):
            packet_label = f"{label}.连续句链[{packet_index}]"
            if not isinstance(packet, dict):
                errors.append(f"{packet_label} 必须是对象")
                valid = False
                continue
            excerpt = str(packet.get("source_excerpt") or "").strip()
            packet_excerpts.append(excerpt)
            if len(excerpt) < 60 or excerpt not in source_text:
                errors.append(f"{packet_label}.source_excerpt 必须是 60 字以上连续主体原文")
                valid = False
            expected_chain = sentence_units(excerpt)
            recorded_chain = nonempty_strings(packet.get("source_sentence_chain"))
            if len(expected_chain) < 3 or recorded_chain != expected_chain:
                errors.append(f"{packet_label}.source_sentence_chain 必须完整保留连续原文句序")
                valid = False
            signature_parts: list[str] = []
            for field in CONTINUOUS_SOURCE_CHAIN_PACKET_FIELDS:
                value = str(packet.get(field) or "").strip()
                if len(value) < 12:
                    errors.append(f"{packet_label}.{field} 必须具体说明句链如何驱动落笔")
                    valid = False
                signature_parts.append(normalized_manual_text(value))
            packet_signatures.setdefault("|".join(signature_parts), []).append(packet_index)
            if packet.get("surface_copy_rejected") is not True:
                errors.append(f"{packet_label}.surface_copy_rejected 必须为 true")
                valid = False
            if len(str(packet.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"{packet_label}.manual_judgment 必须给出连续气口裁决")
                valid = False
        if len(packet_excerpts) != len(set(packet_excerpts)):
            errors.append(f"{label} 不得重复同一连续原文句链充数")
            valid = False
        for indexes in packet_signatures.values():
            if len(indexes) > 1:
                errors.append(f"{label} 连续句链迁移说明不得模板化")
                valid = False

        contrastive_examples = plan.get("contrastive_examples")
        if not isinstance(contrastive_examples, list) or len(contrastive_examples) < 2:
            errors.append(f"{label}.contrastive_examples 至少需要 2 组正反例")
            contrastive_examples = []
            valid = False
        negative_examples: list[str] = []
        contrast_signatures: dict[str, list[int]] = {}
        for example_index, example in enumerate(contrastive_examples, start=1):
            example_label = f"{label}.正反例[{example_index}]"
            if not isinstance(example, dict):
                errors.append(f"{example_label} 必须是对象")
                valid = False
                continue
            positive_excerpt = str(example.get("positive_source_excerpt") or "").strip()
            if positive_excerpt not in packet_excerpts:
                errors.append(f"{example_label}.positive_source_excerpt 必须绑定本节连续句链正例")
                valid = False
            negative_example = str(example.get("negative_example") or "").strip()
            negative_examples.append(negative_example)
            if len(negative_example) < 12 or negative_example in source_text:
                errors.append(f"{example_label}.negative_example 必须是完整且不属于主体原文的错误反例")
                valid = False
            signature_parts = []
            for field in ("positive_effect", "negative_failure", "rewrite_instruction"):
                value = str(example.get(field) or "").strip()
                if len(value) < 12:
                    errors.append(f"{example_label}.{field} 必须具体对照正误句面")
                    valid = False
                signature_parts.append(normalized_manual_text(value))
            contrast_signatures.setdefault("|".join(signature_parts), []).append(example_index)
            if example.get("surface_copy_rejected") is not True:
                errors.append(f"{example_label}.surface_copy_rejected 必须为 true")
                valid = False
        if len(negative_examples) != len(set(negative_examples)):
            errors.append(f"{label} 不得重复同一错误反例充数")
            valid = False
        for indexes in contrast_signatures.values():
            if len(indexes) > 1:
                errors.append(f"{label} 正反例裁决不得模板化")
                valid = False

        relation_examples = plan.get("relation_micro_examples")
        if not isinstance(relation_examples, list) or len(relation_examples) < 2:
            errors.append(f"{label}.relation_micro_examples 至少需要 2 组句间关系正反例")
            relation_examples = []
            valid = False
        relation_source_excerpts: list[str] = []
        relation_target_rehearsals: list[str] = []
        relation_negative_examples: list[str] = []
        relation_signatures: dict[str, list[int]] = {}
        for relation_index, example in enumerate(relation_examples, start=1):
            relation_label = f"{label}.句间关系包[{relation_index}]"
            if not isinstance(example, dict):
                errors.append(f"{relation_label} 必须是对象")
                valid = False
                continue
            source_excerpt = str(example.get("source_excerpt") or "").strip()
            relation_source_excerpts.append(source_excerpt)
            if len(source_excerpt) < 12 or source_excerpt not in source_text:
                errors.append(f"{relation_label}.source_excerpt 必须直接引用主体原文关系句")
                valid = False
            source_relation_type = str(example.get("source_relation_type") or "").strip()
            target_relation_type = str(example.get("target_relation_type") or "").strip()
            if source_relation_type not in RELATION_TYPES:
                errors.append(f"{relation_label}.source_relation_type 无效")
                valid = False
            if target_relation_type != source_relation_type:
                errors.append(f"{relation_label} 目标必须迁移同类句间关系")
                valid = False
            source_mode = str(example.get("source_marking_mode") or "").strip()
            target_mode = str(example.get("target_marking_mode") or "").strip()
            if source_mode not in RELATION_MARKING_MODES:
                errors.append(f"{relation_label}.source_marking_mode 必须为 explicit / implicit")
                valid = False
            if target_mode not in RELATION_MARKING_MODES:
                errors.append(f"{relation_label}.target_marking_mode 必须为 explicit / implicit")
                valid = False
            source_markers = nonempty_strings(example.get("source_markers"))
            detected_source_markers = explicit_relation_markers(source_excerpt)
            if source_mode == "explicit":
                if (
                    not source_markers
                    or any(marker not in detected_source_markers for marker in source_markers)
                ):
                    errors.append(f"{relation_label}.source_markers 必须是验证器识别到的真实关系词")
                    valid = False
            elif source_markers or detected_source_markers:
                errors.append(f"{relation_label} 含显式关系词时不得自报为 implicit")
                valid = False
            target_rehearsal = str(example.get("target_rehearsal") or "").strip()
            relation_target_rehearsals.append(target_rehearsal)
            target_markers = nonempty_strings(example.get("target_markers"))
            detected_target_markers = explicit_relation_markers(target_rehearsal)
            if target_mode == "explicit":
                if (
                    not target_markers
                    or any(marker not in detected_target_markers for marker in target_markers)
                ):
                    errors.append(f"{relation_label}.target_markers 必须是正例中真实可识别的关系词")
                    valid = False
            elif target_markers or detected_target_markers:
                errors.append(f"{relation_label} 隐式目标关系不得含显式关系词")
                valid = False
            negative_example = str(example.get("negative_example") or "").strip()
            relation_negative_examples.append(negative_example)
            if negative_example == target_rehearsal or negative_example in source_text:
                errors.append(f"{relation_label}.negative_example 必须独立于正例和主体原文")
                valid = False
            signature_parts: list[str] = []
            for field in RELATION_MICRO_EXAMPLE_FIELDS:
                value = str(example.get(field) or "").strip()
                if len(value) < 12:
                    errors.append(f"{relation_label}.{field} 必须具体说明关系显隐与虚词骨架")
                    valid = False
                signature_parts.append(normalized_manual_text(value))
            source_skeleton = str(example.get("source_function_word_skeleton") or "").strip()
            if source_mode == "explicit" and any(
                marker not in source_skeleton for marker in source_markers
            ):
                errors.append(f"{relation_label}.source_function_word_skeleton 必须写出源关系词")
                valid = False
            relation_signatures.setdefault("|".join(signature_parts), []).append(relation_index)
            if example.get("mechanical_marker_insertion_forbidden") is not True:
                errors.append(f"{relation_label} 必须禁止机械补转折词")
                valid = False
            if example.get("surface_copy_rejected") is not True:
                errors.append(f"{relation_label}.surface_copy_rejected 必须为 true")
                valid = False
        for values, message in (
            (relation_source_excerpts, "关系源句"),
            (relation_target_rehearsals, "关系正例试演"),
            (relation_negative_examples, "关系错误反例"),
        ):
            if len(values) != len(set(values)):
                errors.append(f"{label} 不得重复同一{message}充数")
                valid = False
        for indexes in relation_signatures.values():
            if len(indexes) > 1:
                errors.append(f"{label} 句间关系裁决不得模板化")
                valid = False

        dialogue_packets = plan.get("dialogue_voice_packets")
        if not isinstance(dialogue_packets, list) or len(dialogue_packets) < 2:
            errors.append(f"{label}.dialogue_voice_packets 至少需要 2 组原文对白、目标试演与错误反例三联包")
            dialogue_packets = []
            valid = False
        dialogue_source_excerpts: list[str] = []
        dialogue_rehearsals: list[str] = []
        dialogue_negatives: list[str] = []
        for dialogue_index, packet in enumerate(dialogue_packets, start=1):
            packet_label = f"{label}.对白三联包[{dialogue_index}]"
            if not isinstance(packet, dict):
                errors.append(f"{packet_label} 必须是对象")
                valid = False
                continue
            source_excerpt = str(packet.get("source_excerpt") or "").strip()
            dialogue_source_excerpts.append(source_excerpt)
            if len(source_excerpt) < 60 or source_excerpt not in source_text:
                errors.append(f"{packet_label}.source_excerpt 必须是 60 字以上连续主体原文")
                valid = False
            expected_turns = dialogue_turn_units(source_excerpt)
            recorded_turns = nonempty_strings(packet.get("source_dialogue_turns"))
            if len(expected_turns) < 2 or recorded_turns != expected_turns:
                errors.append(f"{packet_label}.source_dialogue_turns 必须完整保留至少 2 轮原文直接对白")
                valid = False
            target_character = str(packet.get("target_character") or "").strip()
            if len(target_character) < 2:
                errors.append(f"{packet_label}.target_character 必须绑定当前人物")
                valid = False
            rehearsal = str(packet.get("target_rehearsal") or "").strip()
            dialogue_rehearsals.append(rehearsal)
            rehearsal_turns = dialogue_turn_units(rehearsal)
            if len(rehearsal) < 60 or rehearsal in source_text or len(rehearsal_turns) < 3:
                errors.append(f"{packet_label}.target_rehearsal 必须是 60 字以上、至少 3 轮的当前人物自然口语试演")
                valid = False
            source_turn_texts = {
                turn.strip("「」『』").strip() for turn in expected_turns
            }
            rehearsal_turn_texts = {
                turn.strip("「」『』").strip() for turn in rehearsal_turns
            }
            if source_turn_texts & rehearsal_turn_texts:
                errors.append(f"{packet_label}.target_rehearsal 不得复制主体原文对白")
                valid = False
            negative_example = str(packet.get("negative_example") or "").strip()
            dialogue_negatives.append(negative_example)
            if (
                len(negative_example) < 12
                or negative_example in source_text
                or negative_example == rehearsal
            ):
                errors.append(f"{packet_label}.negative_example 必须是完整、独立且不属于主体原文的僵硬错例")
                valid = False
            for field in DIALOGUE_VOICE_PACKET_FIELDS:
                if len(str(packet.get(field) or "").strip()) < 12:
                    errors.append(f"{packet_label}.{field} 必须具体说明原文口气如何迁移")
                    valid = False
            if packet.get("surface_copy_rejected") is not True:
                errors.append(f"{packet_label}.surface_copy_rejected 必须为 true")
                valid = False
            if len(str(packet.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"{packet_label}.manual_judgment 必须给出当前模型口语裁决")
                valid = False
        for values, message in (
            (dialogue_source_excerpts, "原文对白片段"),
            (dialogue_rehearsals, "目标人物口语试演"),
            (dialogue_negatives, "对白僵硬错例"),
        ):
            if len(values) != len(set(values)):
                errors.append(f"{label} 不得重复同一{message}充数")
                valid = False
        passage_ids = nonempty_strings(plan.get("source_passage_ids"))
        if not passage_ids or any(item not in passage_map for item in passage_ids):
            errors.append(f"{label}.source_passage_ids 必须绑定已逐句标注的原文段")
            valid = False
        allowed_source_sentences = {
            str(annotation.get("source_sentence") or "").strip()
            for passage_id in passage_ids
            for annotation in (passage_map.get(passage_id, {}).get("sentence_annotations") or [])
            if isinstance(annotation, dict)
        }
        mechanisms = plan.get("sentence_mechanisms")
        if not isinstance(mechanisms, list) or len(mechanisms) < 3:
            errors.append(f"{label}.sentence_mechanisms 至少需要 3 个逐句生成机制")
            mechanisms = []
            valid = False
        for index, mechanism in enumerate(mechanisms, start=1):
            item_label = f"{label}.机制[{index}]"
            if not isinstance(mechanism, dict):
                errors.append(f"{item_label} 必须是对象")
                valid = False
                continue
            source_sentence = str(mechanism.get("source_sentence") or "").strip()
            if source_sentence not in allowed_source_sentences:
                errors.append(f"{item_label}.source_sentence 不在本节绑定原文段中")
                valid = False
            feature_ids = nonempty_strings(mechanism.get("feature_ids"))
            if len(feature_ids) < 2 or any(
                feature_id not in ULTRA_FINE_FEATURE_IDS for feature_id in feature_ids
            ):
                errors.append(f"{item_label}.feature_ids 至少绑定 2 项超细特征")
                valid = False
            for field in (
                "mechanism",
                "target_intent",
                "allowed_deviation",
                "prohibited_shell",
            ):
                if len(str(mechanism.get(field) or "").strip()) < 8:
                    errors.append(f"{item_label}.{field} 必须具体")
                    valid = False
            if mechanism.get("surface_copy_rejected") is not True:
                errors.append(f"{item_label}.surface_copy_rejected 必须为 true")
                valid = False
        for group_name, fields in (
            ("paragraph_plan", SECTION_PARAGRAPH_PLAN_FIELDS),
            ("window_plan", SECTION_WINDOW_PLAN_FIELDS),
        ):
            group = plan.get(group_name)
            if not isinstance(group, dict):
                errors.append(f"{label}.{group_name} 必须是对象")
                valid = False
                continue
            for field in fields:
                if len(str(group.get(field) or "").strip()) < 8:
                    errors.append(f"{label}.{group_name}.{field} 必须具体")
                    valid = False
        liveliness_plan = plan.get("liveliness_plan")
        if not isinstance(liveliness_plan, dict):
            errors.append(f"{label}.liveliness_plan 必须是对象")
            valid = False
        else:
            if liveliness_plan.get("planned_before_draft") is not True:
                errors.append(f"{label}.liveliness_plan 必须在正文前完成")
                valid = False
            asset_ids = nonempty_strings(liveliness_plan.get("asset_ids"))
            if len(asset_ids) < 4 or any(item not in liveliness_assets for item in asset_ids):
                errors.append(f"{label}.liveliness_plan.asset_ids 至少绑定 4 条有效活性资产")
                valid = False
            selected_types = {
                str(liveliness_assets[item].get("type") or "")
                for item in asset_ids
                if item in liveliness_assets
            }
            if len(selected_types) < 3:
                errors.append(f"{label}.liveliness_plan 至少覆盖 3 类活性资产")
                valid = False
            for field in LIVELINESS_SECTION_PLAN_FIELDS:
                if len(str(liveliness_plan.get(field) or "").strip()) < 8:
                    errors.append(f"{label}.liveliness_plan.{field} 必须具体")
                    valid = False
            if len(nonempty_strings(liveliness_plan.get("stiffness_patterns_rejected"))) < 3:
                errors.append(f"{label}.liveliness_plan 至少拒绝 3 类僵硬句面")
                valid = False
            if len(str(liveliness_plan.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"{label}.liveliness_plan.manual_judgment 必须具体")
                valid = False
        if not validate_section_character_plan(
            plan, label, personality_assets, character_profiles, errors
        ):
            valid = False
        if plan.get("surface_copy_rejected") is not True:
            errors.append(f"{label}.surface_copy_rejected 必须为 true")
            valid = False
        judgment = str(plan.get("manual_judgment") or "").strip()
        if len(judgment) < 20:
            errors.append(f"{label}.manual_judgment 必须说明如何用于本节落笔")
            valid = False
        else:
            judgment_signatures.setdefault(normalized_manual_text(judgment), []).append(section_id)
        if not str(section_text).strip():
            errors.append(f"{label} 绑定的细纲小节为空")
            valid = False
        if valid:
            passed += 1
    for section_ids in judgment_signatures.values():
        if len(section_ids) > 1:
            errors.append("不同小节不得复用模板化落笔裁决: " + ", ".join(section_ids))
    return passed


def validate_prewrite_data(
    data: dict[str, Any], source_original: Path, outline_path: Path | None = None
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    source_text = validate_source_binding(data, source_original, errors)
    subflow_records = validate_subflow_catalog_data(
        data, source_original, source_text, errors
    )
    if data.get("execution_mode") != "current_model_manual":
        errors.append("execution_mode 必须为 current_model_manual")
    if data.get("reviewed_by_current_model") is not True:
        errors.append("必须由当前写作模型人工建立文字颗粒度基线")
    if data.get("auxiliary_sources_supply_prose") is not False:
        errors.append("辅助来源不得供应正文声线，只能供应情节与场面机制")
    ultra_fine_passages = validate_ultra_fine_source_baseline(
        data, source_text, errors
    )
    liveliness_assets = validate_prose_liveliness_layer(data, source_text, errors)
    personality_assets, character_profiles = validate_character_personality_layer(
        data, source_text, errors
    )
    passed_generation_plans = validate_outline_generation_plans(
        data,
        outline_path,
        source_text,
        ultra_fine_passages,
        liveliness_assets,
        personality_assets,
        character_profiles,
        errors,
    )

    baseline = data.get("source_baseline")
    if not isinstance(baseline, dict):
        errors.append("source_baseline 必须是对象")
        baseline = {}
    excerpts = baseline.get("continuous_excerpts")
    valid_excerpts = 0
    if not isinstance(excerpts, list):
        errors.append("source_baseline.continuous_excerpts 必须是列表")
    else:
        purposes: set[str] = set()
        for index, item in enumerate(excerpts, start=1):
            if not isinstance(item, dict):
                errors.append(f"连续原文样本格式错误: [{index}]")
                continue
            quote = str(item.get("quote") or "").strip()
            purpose = str(item.get("purpose") or "").strip()
            judgment = str(item.get("language_judgment") or "").strip()
            if validate_source_quote(quote, source_text, f"连续原文样本[{index}]", errors):
                if len(quote) < 40:
                    errors.append(f"连续原文样本过短，不能用金句代替气口样本: [{index}]")
                elif purpose and judgment:
                    valid_excerpts += 1
            if not purpose:
                errors.append(f"连续原文样本缺少 purpose: [{index}]")
            else:
                purposes.add(purpose)
            if not judgment:
                errors.append(f"连续原文样本缺少 language_judgment: [{index}]")
        if valid_excerpts < 5:
            errors.append("至少需要 5 组四十字以上的主体原文连续样本")
        if len(purposes) < 4:
            errors.append("连续样本必须覆盖至少 4 类语言场景")

    dimensions = baseline.get("dimensions")
    if not isinstance(dimensions, dict):
        errors.append("source_baseline.dimensions 必须是对象")
        dimensions = {}
    for name in REQUIRED_DIMENSIONS:
        item = dimensions.get(name)
        if not isinstance(item, dict):
            errors.append(f"缺少文字颗粒度维度: {name}")
            continue
        for field in ("rule", "transfer_rule", "ai_drift_to_reject"):
            if not str(item.get(field) or "").strip():
                errors.append(f"文字颗粒度维度 {name}.{field} 不能为空")
        quotes = nonempty_strings(item.get("source_quotes"))
        if len(quotes) < 2:
            errors.append(f"文字颗粒度维度 {name} 至少需要 2 条原文证据")
        for index, quote in enumerate(quotes, start=1):
            validate_source_quote(quote, source_text, f"{name}.source_quotes[{index}]", errors)

    anti_patterns = baseline.get("anti_patterns")
    if not isinstance(anti_patterns, list) or len(anti_patterns) < 3:
        errors.append("至少需要 3 条主体原文不像的 AI 句面反例")
    else:
        for index, item in enumerate(anti_patterns, start=1):
            if not isinstance(item, dict):
                errors.append(f"anti_patterns 格式错误: [{index}]")
                continue
            if not str(item.get("pattern") or "").strip():
                errors.append(f"anti_patterns 缺少 pattern: [{index}]")
            if not str(item.get("why_unlike_source") or "").strip():
                errors.append(f"anti_patterns 缺少 why_unlike_source: [{index}]")
    if not str(baseline.get("manual_judgment") or "").strip():
        errors.append("source_baseline.manual_judgment 不能为空")

    samples = data.get("calibration_samples")
    valid_samples = 0
    if not isinstance(samples, list) or len(samples) < 3:
        errors.append("正文前至少需要 3 组主体原文—原创试写校准样本")
    else:
        for index, item in enumerate(samples, start=1):
            if not isinstance(item, dict):
                errors.append(f"calibration_samples 格式错误: [{index}]")
                continue
            source_quote = str(item.get("source_quote") or "").strip()
            target_sample = str(item.get("target_sample") or "").strip()
            comparison = str(item.get("comparison") or "").strip()
            valid = validate_source_quote(
                source_quote, source_text, f"calibration_samples[{index}].source_quote", errors
            )
            if len(source_quote) < 20:
                errors.append(f"校准原文样本过短: [{index}]")
                valid = False
            if len(target_sample) < 20:
                errors.append(f"原创校准样本过短: [{index}]")
                valid = False
            if not comparison:
                errors.append(f"校准样本缺少人工句面对照: [{index}]")
                valid = False
            if item.get("functional_alignment_used_as_prose_proof") is not False:
                errors.append(f"校准样本不得用功能对齐冒充文字对齐: [{index}]")
                valid = False
            if item.get("extra_ai_shell") is not False:
                errors.append(f"校准样本仍含新增 AI 句面壳: [{index}]")
                valid = False
            if valid:
                valid_samples += 1

    if data.get("prewrite_status") != "passed":
        errors.append("prewrite_status 必须为 passed")
    return errors, {
        "valid_excerpts": valid_excerpts,
        "required_dimensions": len(REQUIRED_DIMENSIONS),
        "valid_calibration_samples": valid_samples,
        "required_subflows": len(subflow_records),
        "ultra_fine_source_passages": len(ultra_fine_passages),
        "passed_generation_plans": passed_generation_plans,
        "liveliness_assets": len(liveliness_assets),
        "personality_assets": len(personality_assets),
        "target_character_profiles": len(character_profiles),
    }


def extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^\s*(?:#{1,6}\s*)?(\d+)\.\s*(?:.*)?$", line)
        if match:
            current = match.group(1)
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    if not sections:
        return {"full": text}
    return {key: "\n".join(lines) for key, lines in sections.items()}


def bind_outline(data: dict[str, Any], outline_path: Path) -> dict[str, Any]:
    outline = outline_path.resolve()
    if not outline.is_file():
        raise FileNotFoundError(f"细纲不存在: {outline}")
    sections = extract_sections(read_text(outline))
    data["version"] = "2.5"
    data["gate_status"] = "pending"
    data["prewrite_status"] = "pending"
    data["outline"] = {"path": str(outline), "sha256": sha256(outline)}
    data["section_generation_plans"] = [
        section_generation_plan_scaffold(section_id) for section_id in sections
    ]
    data["blocking_failures"] = []
    return data


def bind_draft(data: dict[str, Any], draft_path: Path) -> dict[str, Any]:
    draft = draft_path.resolve()
    if not draft.is_file():
        raise FileNotFoundError(f"正文不存在: {draft}")
    sections = extract_sections(read_text(draft))
    data["gate_status"] = "pending"
    data["draft"] = {"path": str(draft), "sha256": sha256(draft)}
    data["rewrite_scope_review"] = {
        "mode": "pending",
        "full_rewrite_requested": None,
        "expected_section_ids": list(sections),
        "rewritten_section_ids": [],
        "unchanged_section_ids": [],
        "full_text_read_before_rewrite": None,
        "full_text_read_after_rewrite": None,
        "manual_judgment": "",
    }
    data["manual_review_provenance"] = {
        "performed_by_current_model": None,
        "semantic_fields_generated_by_script": None,
        "receipt_population_method": "pending",
        "full_text_read_by_current_model": None,
        "review_bound_to_draft_sha256": "",
        "automation_artifacts_used": [],
        "manual_judgment": "",
    }
    existing_reviews = {
        str(item.get("section_id") or ""): item
        for item in data.get("section_reviews", [])
        if isinstance(item, dict)
    }

    def review_for(section_id: str, section_text: str) -> dict[str, Any]:
        section_sha256 = hashlib.sha256(section_text.encode("utf-8")).hexdigest()
        existing = existing_reviews.get(section_id)
        if existing and existing.get("section_sha256") == section_sha256:
            return existing
        return {
            "section_id": section_id,
            "section_sha256": section_sha256,
            "status": "pending",
            "target_quotes": [],
            "source_anchors": [],
            "dimensions_checked": [],
            "source_voice_preserved": None,
            "functional_alignment_used_as_prose_proof": None,
            "extra_ai_shell": None,
            "comparison": "",
            "generation_plan_consumed": None,
            "continuous_chain_reviews": [],
            "relation_micro_reviews": [],
            "dialogue_voice_reviews": [],
            "sentence_mappings": [],
            "semantic_review_method": "",
            "automation_used_for_semantic_judgment": None,
            "liveliness_review": section_liveliness_review_scaffold(
                explanatory_narration_candidate_quotes(section_text)
            ),
            "character_vitality_review": section_character_vitality_review_scaffold(
                abstract_dialogue_candidate_quotes(section_text),
                dialogue_turn_units(section_text),
            ),
            "sentence_relation_review": section_sentence_relation_review_scaffold(
                hard_coordination_candidate_quotes(section_text)
            ),
            "action_continuity_review": action_continuity_review_scaffold(section_text),
            "section_write_judgment": "",
        }

    data["section_reviews"] = [
        review_for(section_id, section_text)
        for section_id, section_text in sections.items()
    ]
    existing_subflows = data.get("source_subflow_reviews")
    if not isinstance(existing_subflows, list):
        existing_subflows = []
    data["source_subflow_reviews"] = [
        source_subflow_review_scaffold(item)
        for item in existing_subflows
        if isinstance(item, dict)
    ]
    data["character_arc_reviews"] = []
    data["full_text_review"] = {
        "reviewed_full_text": False,
        "all_sections_reviewed": False,
        "primary_source_voice_dominant": False,
        "auxiliary_style_contamination": None,
        "functional_alignment_used_as_prose_proof": None,
        "remaining_extra_ai_shell": None,
        "character_personality_dominant": None,
        "conclusion": "",
    }
    data["blocking_failures"] = []
    return data


def validate_source_subflow_reviews(
    data: dict[str, Any],
    source_original: Path,
    sections: dict[str, str],
    errors: list[str],
) -> int:
    source = source_original.resolve()
    source_text = read_text(source)
    try:
        records = subflow_records_from_catalog(subflow_catalog_path(source))
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))
        return 0
    records_by_id = {
        str(record.get("subflow_id") or "").strip(): record for record in records
    }
    reviews = data.get("source_subflow_reviews")
    if not isinstance(reviews, list):
        errors.append("source_subflow_reviews 必须逐 SF 证明正文消费了全部颗粒")
        return 0
    reviews_by_id: dict[str, dict[str, Any]] = {}
    for index, review in enumerate(reviews, start=1):
        label = f"主体 SF 正文复核[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label} 必须是对象")
            continue
        subflow_id = str(review.get("subflow_id") or "").strip()
        if not subflow_id:
            errors.append(f"{label}.subflow_id 不能为空")
            continue
        if subflow_id in reviews_by_id:
            errors.append(f"{label}.subflow_id 重复: {subflow_id}")
            continue
        reviews_by_id[subflow_id] = review

    passed = 0
    rationale_signatures: dict[str, list[str]] = {}
    judgment_signatures: dict[str, list[str]] = {}
    for subflow_id, record in records_by_id.items():
        label = f"主体 SF {subflow_id}"
        review = reviews_by_id.get(subflow_id)
        if review is None:
            errors.append(f"主体原文 SF 未进入正文颗粒复核: {subflow_id}")
            continue
        valid = True
        for field in ("parent_bridge_id", "source_range", "source_style_granularity"):
            if review.get(field) != record.get(field):
                errors.append(f"{label}.{field} 与主体子流程索引不一致")
                valid = False
        if review.get("status") != "passed":
            errors.append(f"{label}.status 必须为 passed")
            valid = False
        if review.get("semantic_review_method") != "current_model_manual":
            errors.append(f"{label}.semantic_review_method 必须为 current_model_manual")
            valid = False
        if review.get("automation_used_for_semantic_judgment") is not False:
            errors.append(f"{label} 禁止用自动脚本生成语义裁决")
            valid = False
        target_sections = nonempty_strings(review.get("target_sections"))
        if not target_sections:
            errors.append(f"{label}.target_sections 不能为空")
            valid = False
        target_text = "\n".join(
            sections[section_id]
            for section_id in target_sections
            if section_id in sections
        )
        for section_id in target_sections:
            if section_id not in sections:
                errors.append(f"{label}.target_sections 引用了不存在的小节: {section_id}")
                valid = False
        target_section_rationale = str(review.get("target_section_rationale") or "").strip()
        if len(target_section_rationale) < 12:
            errors.append(f"{label}.target_section_rationale 必须具体说明 SF 为何落到目标小节")
            valid = False
        else:
            rationale_signatures.setdefault(
                normalized_manual_text(target_section_rationale), []
            ).append(subflow_id)
        transfers = review.get("dimension_transfers")
        if not isinstance(transfers, dict):
            errors.append(f"{label}.dimension_transfers 必须逐项覆盖六类颗粒")
            transfers = {}
            valid = False
        quote_signatures: dict[tuple[str, ...], list[str]] = {}
        transfer_comparison_signatures: dict[str, list[str]] = {}
        mapping_comparison_signatures: dict[str, list[str]] = {}
        for field in SOURCE_STYLE_GRANULARITY_FIELDS:
            transfer = transfers.get(field)
            if not isinstance(transfer, dict):
                errors.append(f"{label} 缺少正文颗粒迁移: {field}")
                valid = False
                continue
            quotes = nonempty_strings(transfer.get("target_quotes"))
            if not quotes:
                errors.append(f"{label}.{field}.target_quotes 至少一条目标原句")
                valid = False
            for quote in quotes:
                if quote not in target_text:
                    errors.append(f"{label}.{field} 目标原句不在绑定小节中: {quote!r}")
                    valid = False
            if quotes:
                quote_signatures.setdefault(tuple(sorted(set(quotes))), []).append(field)
            source_evidence = nonempty_strings(transfer.get("source_evidence"))
            expected_source_evidence = nonempty_strings(
                (record.get("source_style_granularity") or {}).get(field, {}).get(
                    "source_evidence"
                )
            )
            if source_evidence != expected_source_evidence:
                errors.append(
                    f"{label}.{field}.source_evidence 必须完整原样覆盖主体字段证据"
                )
                valid = False
            for quote in source_evidence:
                if quote not in source_text:
                    errors.append(f"{label}.{field} 主体证据不在原文中: {quote!r}")
                    valid = False
            mappings = transfer.get("evidence_mappings")
            if not isinstance(mappings, list):
                errors.append(f"{label}.{field}.evidence_mappings 必须逐条映射主体证据")
                mappings = []
                valid = False
            mapped_source_quotes = [
                str(item.get("source_quote") or "").strip()
                for item in mappings
                if isinstance(item, dict)
            ]
            if mapped_source_quotes != expected_source_evidence:
                errors.append(
                    f"{label}.{field}.evidence_mappings 必须逐条覆盖全部主体证据"
                )
                valid = False
            for mapping_index, mapping in enumerate(mappings, start=1):
                if not isinstance(mapping, dict):
                    errors.append(f"{label}.{field}.evidence_mappings[{mapping_index}] 必须是对象")
                    valid = False
                    continue
                mapped_targets = nonempty_strings(mapping.get("target_quotes"))
                if not mapped_targets:
                    errors.append(
                        f"{label}.{field}.evidence_mappings[{mapping_index}] 至少绑定一条目标原句"
                    )
                    valid = False
                for quote in mapped_targets:
                    if quote not in target_text:
                        errors.append(
                            f"{label}.{field}.evidence_mappings[{mapping_index}] 目标原句不在绑定小节中: {quote!r}"
                        )
                        valid = False
                mapping_comparison = str(mapping.get("comparison") or "").strip()
                if not mapping_comparison:
                    errors.append(
                        f"{label}.{field}.evidence_mappings[{mapping_index}].comparison 不能为空"
                    )
                    valid = False
                else:
                    mapping_comparison_signatures.setdefault(
                        normalized_manual_text(mapping_comparison), []
                    ).append(f"{field}[{mapping_index}]")
            transfer_comparison = str(transfer.get("comparison") or "").strip()
            if not transfer_comparison:
                errors.append(f"{label}.{field}.comparison 不能为空")
                valid = False
            else:
                transfer_comparison_signatures.setdefault(
                    normalized_manual_text(transfer_comparison), []
                ).append(field)
            if transfer.get("surface_copy_rejected") is not True:
                errors.append(f"{label}.{field}.surface_copy_rejected 必须为 true")
                valid = False
        for fields in quote_signatures.values():
            if len(fields) < 2:
                continue
            justifications: dict[str, list[str]] = {}
            for field in fields:
                transfer = transfers.get(field) or {}
                justification = str(
                    transfer.get("cross_dimension_reuse_justification") or ""
                ).strip()
                if len(justification) < 12:
                    errors.append(
                        f"{label} 跨字段复用同一组目标句时必须逐字段说明: {field}"
                    )
                    valid = False
                    continue
                justifications.setdefault(
                    normalized_manual_text(justification), []
                ).append(field)
            for reused_fields in justifications.values():
                if len(reused_fields) > 1:
                    errors.append(
                        f"{label} 跨字段复用理由不得模板化: " + ", ".join(reused_fields)
                    )
                    valid = False
        for fields in transfer_comparison_signatures.values():
            if len(fields) > 1:
                errors.append(
                    f"{label} 六类颗粒 comparison 不得只替换字段名: " + ", ".join(fields)
                )
                valid = False
        for mappings in mapping_comparison_signatures.values():
            if len(mappings) > 1:
                errors.append(
                    f"{label} 逐证据句面对照不得模板化: " + ", ".join(mappings)
                )
                valid = False
        for field, expected in (
            ("source_voice_preserved", True),
            ("functional_alignment_used_as_prose_proof", False),
            ("extra_ai_shell", False),
        ):
            if review.get(field) is not expected:
                errors.append(f"{label}.{field} 必须为 {expected}")
                valid = False
        manual_judgment = str(review.get("manual_judgment") or "").strip()
        if len(manual_judgment) < 12:
            errors.append(f"{label}.manual_judgment 不能为空")
            valid = False
        else:
            judgment_signatures.setdefault(
                normalized_manual_text(manual_judgment), []
            ).append(subflow_id)
        if valid:
            passed += 1
    for subflows in rationale_signatures.values():
        if len(subflows) > 1:
            errors.append("不同 SF 不得复用模板化目标小节理由: " + ", ".join(subflows))
    for subflows in judgment_signatures.values():
        if len(subflows) > 1:
            errors.append("不同 SF 不得复用模板化人工裁决: " + ", ".join(subflows))
    extra = sorted(set(reviews_by_id) - set(records_by_id))
    if extra:
        errors.append("正文颗粒复核引用不存在的主体 SF: " + ", ".join(extra))
    return passed


def validate_section_character_vitality(
    review: dict[str, Any],
    plan: dict[str, Any] | None,
    section_text: str,
    character_profiles: dict[str, dict[str, Any]],
    section_id: str,
    errors: list[str],
) -> bool:
    label = f"正文小节 {section_id}.人物性格复核"
    vitality = review.get("character_vitality_review")
    if not isinstance(vitality, dict):
        errors.append(f"{label} 缺失")
        return False
    character_plan = (plan or {}).get("character_plan") or {}
    planned_participants = {
        str(item.get("character_name") or "").strip(): item
        for item in (character_plan.get("participants") or [])
        if isinstance(item, dict) and str(item.get("character_name") or "").strip()
    }
    reviews = vitality.get("character_reviews")
    if not isinstance(reviews, list):
        errors.append(f"{label}.character_reviews 必须是列表")
        reviews = []
    review_map: dict[str, dict[str, Any]] = {}
    quote_owners: dict[str, list[str]] = {}
    judgment_signatures: dict[str, list[str]] = {}
    valid = True
    for index, item in enumerate(reviews, start=1):
        item_label = f"{label}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_label} 必须是对象")
            valid = False
            continue
        name = str(item.get("character_name") or "").strip()
        if not name or name in review_map:
            errors.append(f"{item_label}.character_name 为空或重复")
            valid = False
            continue
        review_map[name] = item
        if name not in planned_participants or name not in character_profiles:
            errors.append(f"{item_label} 未绑定本节写前人物计划: {name}")
            valid = False
            continue
        target_quotes = nonempty_strings(item.get("target_quotes"))
        minimum_quotes = 2 if character_profiles[name].get("role") == "protagonist" else 1
        if len(target_quotes) < minimum_quotes:
            errors.append(f"{item_label}.target_quotes 至少需要 {minimum_quotes} 条")
            valid = False
        for quote in target_quotes:
            if quote not in section_text:
                errors.append(f"{item_label} 目标句不在当前小节: {quote!r}")
                valid = False
            quote_owners.setdefault(quote, []).append(name)
        ownership_reviews = item.get("evidence_ownership_reviews")
        if not isinstance(ownership_reviews, list):
            errors.append(f"{item_label}.evidence_ownership_reviews 必须逐条覆盖人物引句")
            ownership_reviews = []
            valid = False
        ownership_quotes: list[str] = []
        for ownership_index, ownership in enumerate(ownership_reviews, start=1):
            ownership_label = f"{item_label}.证据归属[{ownership_index}]"
            if not isinstance(ownership, dict):
                errors.append(f"{ownership_label} 必须是对象")
                valid = False
                continue
            quote = str(ownership.get("quote") or "").strip()
            ownership_quotes.append(quote)
            context = str(ownership.get("ownership_context") or "").strip()
            marker = str(ownership.get("actor_or_speaker_marker") or "").strip()
            if str(ownership.get("owner_name") or "").strip() != name:
                errors.append(f"{ownership_label}.owner_name 必须等于当前人物")
                valid = False
            if not context or context not in section_text or quote not in context:
                errors.append(f"{ownership_label}.ownership_context 必须是含引句的正文连续上下文")
                valid = False
            if not marker or marker not in context:
                errors.append(f"{ownership_label}.actor_or_speaker_marker 必须直接出现在归属上下文")
                valid = False
            if ownership.get("marker_refers_to_owner") is not True:
                errors.append(f"{ownership_label}.marker_refers_to_owner 必须为 true")
                valid = False
            if ownership.get("other_character_action_misassigned") is not False:
                errors.append(f"{ownership_label} 禁止把其他人物的动作或对白错配给当前人物")
                valid = False
            if len(str(ownership.get("manual_judgment") or "").strip()) < 12:
                errors.append(f"{ownership_label}.manual_judgment 必须说明说话者或动作执行者")
                valid = False
        if ownership_quotes != target_quotes:
            errors.append(f"{item_label}.evidence_ownership_reviews 必须按顺序覆盖全部 target_quotes")
            valid = False
        dimensions = set(nonempty_strings(item.get("personality_dimensions_shown")))
        if len(dimensions) < 3 or not dimensions.issubset(
            set(CHARACTER_PERSONALITY_ASSET_TYPES)
        ):
            errors.append(f"{item_label} 至少展示 3 类有效人物性格颗粒")
            valid = False
        consumed = nonempty_strings(item.get("source_asset_ids_consumed"))
        planned_assets = set(
            nonempty_strings(planned_participants[name].get("source_asset_ids"))
        )
        if len(consumed) < 2 or any(asset_id not in planned_assets for asset_id in consumed):
            errors.append(f"{item_label} 至少消费写前人物计划中的 2 条原文颗粒")
            valid = False
        for field in (
            "voice_or_behavior_not_interchangeable",
            "action_not_plot_only",
            "knowledge_or_self_awareness_limited",
            "generic_role_shell_absent",
        ):
            if item.get(field) is not True:
                errors.append(f"{item_label}.{field} 必须为 true")
                valid = False
        judgment = str(item.get("manual_judgment") or "").strip()
        if len(judgment) < 20:
            errors.append(f"{item_label}.manual_judgment 必须说明人物为何不可互换")
            valid = False
        else:
            judgment_signatures.setdefault(normalized_manual_text(judgment), []).append(name)
    if set(review_map) != set(planned_participants):
        errors.append(f"{label} 必须逐人覆盖写前人物计划")
        valid = False
    for quote, owners in quote_owners.items():
        if len(set(owners)) > 1:
            errors.append(f"{label} 不得用同一句同时证明多个人物鲜活: {quote!r}")
            valid = False
    for names in judgment_signatures.values():
        if len(names) > 1:
            errors.append(f"{label} 人物人工裁决不得模板化: " + ", ".join(names))
            valid = False
    if len(str(vitality.get("interchangeability_test") or "").strip()) < 20:
        errors.append(f"{label}.interchangeability_test 必须实际执行换人测试")
        valid = False
    if nonempty_strings(vitality.get("functional_character_residue")):
        errors.append(f"{label} 仍有人物只承担递信息、挨骂或触发反刀")
        valid = False
    grounding = vitality.get("dialogue_grounding_review")
    if not isinstance(grounding, dict):
        errors.append(f"{label}.dialogue_grounding_review 缺失")
        valid = False
    else:
        detected_candidates = abstract_dialogue_candidate_quotes(section_text)
        recorded_candidates = nonempty_strings(
            grounding.get("automatic_candidate_quotes")
        )
        if recorded_candidates != detected_candidates:
            errors.append(f"{label} 抽象答复候选必须与当前正文自动定位结果一致")
            valid = False
        candidate_reviews = grounding.get("candidate_reviews")
        if not isinstance(candidate_reviews, list):
            errors.append(f"{label}.dialogue_grounding_review.candidate_reviews 必须是列表")
            candidate_reviews = []
            valid = False
        review_map: dict[str, dict[str, Any]] = {}
        for candidate_index, candidate_review in enumerate(candidate_reviews, start=1):
            candidate_label = f"{label}.抽象答复候选[{candidate_index}]"
            if not isinstance(candidate_review, dict):
                errors.append(f"{candidate_label} 必须是对象")
                valid = False
                continue
            quote = str(candidate_review.get("quote") or "").strip()
            if not quote or quote in review_map:
                errors.append(f"{candidate_label}.quote 为空或重复")
                valid = False
                continue
            review_map[quote] = candidate_review
            verdict = str(candidate_review.get("verdict") or "").strip()
            if verdict == "revise":
                errors.append(f"{candidate_label} 仍需修改正文并重新绑定")
                valid = False
            elif verdict != "keep":
                errors.append(f"{candidate_label}.verdict 必须人工裁决为 keep / revise")
                valid = False
            for field, minimum in (
                ("concrete_pressure_or_object", 4),
                ("character_specific_mechanism", 8),
                ("manual_judgment", 12),
            ):
                if len(str(candidate_review.get(field) or "").strip()) < minimum:
                    errors.append(f"{candidate_label}.{field} 必须给出具体裁决")
                    valid = False
        if set(review_map) != set(detected_candidates):
            errors.append(f"{label} 必须逐条裁决全部自动定位的抽象答复候选")
            valid = False
        expected_dialogue_turns = dialogue_turn_units(section_text)
        full_dialogue_reviews = grounding.get("full_dialogue_reviews")
        if not isinstance(full_dialogue_reviews, list):
            errors.append(f"{label}.full_dialogue_reviews 必须是列表")
            full_dialogue_reviews = []
            valid = False
        reviewed_dialogue_turns: list[str] = []
        for dialogue_index, dialogue_review in enumerate(
            full_dialogue_reviews, start=1
        ):
            dialogue_label = f"{label}.全部对白逐句复核[{dialogue_index}]"
            if not isinstance(dialogue_review, dict):
                errors.append(f"{dialogue_label} 必须是对象")
                valid = False
                continue
            quote = str(dialogue_review.get("quote") or "").strip()
            reviewed_dialogue_turns.append(quote)
            if not quote or quote not in section_text:
                errors.append(f"{dialogue_label}.quote 必须逐字来自当前小节")
                valid = False
            context_window = str(
                dialogue_review.get("context_window") or ""
            ).strip()
            if (
                len(context_window) < len(quote) + 8
                or quote not in context_window
                or context_window not in section_text
            ):
                errors.append(
                    f"{dialogue_label}.context_window 必须绑定含当前对白的正文连续窗口"
                )
                valid = False
            for field, minimum in (
                ("speaker_and_scene_role", 8),
                ("utterance_goal", 12),
                ("adjacency_or_reply_fit", 15),
                ("time_state_fit", 12),
                ("object_and_result_complete", 15),
                ("participant_role_direction", 15),
                ("character_specificity", 15),
                ("manual_judgment", 15),
            ):
                if len(str(dialogue_review.get(field) or "").strip()) < minimum:
                    errors.append(f"{dialogue_label}.{field} 必须给出逐句人工判断")
                    valid = False
            verdict = str(dialogue_review.get("verdict") or "").strip()
            if verdict == "revise":
                errors.append(f"{dialogue_label} 仍需修改正文并重新绑定")
                valid = False
            elif verdict != "keep":
                errors.append(f"{dialogue_label}.verdict 必须为 keep / revise")
                valid = False
        if reviewed_dialogue_turns != expected_dialogue_turns:
            errors.append(f"{label} 必须按正文顺序逐条覆盖本节全部直接对白")
            valid = False
        if grounding.get("reviewed_all_character_dialogue") is not True:
            errors.append(f"{label} 必须人工复核本节全部人物对白")
            valid = False
        if grounding.get("candidate_zero_is_not_pass") is not True:
            errors.append(f"{label}.candidate_zero_is_not_pass 必须明确为 true")
            valid = False
        if nonempty_strings(grounding.get("abstract_summary_reply_residue")):
            errors.append(f"{label} 仍残留具体问题—抽象答复")
            valid = False
        if len(str(grounding.get("manual_judgment") or "").strip()) < 20:
            errors.append(f"{label} 必须说明具体压力如何落回人物自己的错答方式")
            valid = False
    if len(str(vitality.get("manual_judgment") or "").strip()) < 20:
        errors.append(f"{label}.manual_judgment 必须给出整节裁决")
        valid = False
    return valid


def validate_character_arc_reviews(
    data: dict[str, Any],
    character_profiles: dict[str, dict[str, Any]],
    sections: dict[str, str],
    errors: list[str],
) -> int:
    reviews = data.get("character_arc_reviews")
    if not isinstance(reviews, list):
        errors.append("character_arc_reviews 必须逐核心人物做全文性格弧复核")
        return 0
    review_map: dict[str, dict[str, Any]] = {}
    judgment_signatures: dict[str, list[str]] = {}
    passed = 0
    for index, review in enumerate(reviews, start=1):
        label = f"全文人物性格弧[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label} 必须是对象")
            continue
        name = str(review.get("character_name") or "").strip()
        if not name or name in review_map:
            errors.append(f"{label}.character_name 为空或重复")
            continue
        review_map[name] = review
    for name, profile in character_profiles.items():
        label = f"全文人物性格弧 {name}"
        review = review_map.get(name)
        if review is None:
            errors.append(f"{label} 缺失")
            continue
        valid = True
        section_ids = nonempty_strings(review.get("section_ids"))
        if not section_ids or any(section_id not in sections for section_id in section_ids):
            errors.append(f"{label}.section_ids 必须绑定真实正文小节")
            valid = False
        target_text = "\n".join(sections.get(section_id, "") for section_id in section_ids)
        for field, minimum in (
            ("stable_bias_quotes", 2),
            ("variation_or_break_quotes", 2),
            ("private_relation_language_quotes", 1),
        ):
            quotes = nonempty_strings(review.get(field))
            if len(quotes) < minimum:
                errors.append(f"{label}.{field} 至少需要 {minimum} 条")
                valid = False
            for quote in quotes:
                if quote not in target_text:
                    errors.append(f"{label}.{field} 引句不在绑定小节: {quote!r}")
                    valid = False
        if review.get("profile_consistent_but_not_repetitive") is not True:
            errors.append(f"{label}.profile_consistent_but_not_repetitive 必须为 true")
            valid = False
        if review.get("not_functional_role") is not True:
            errors.append(f"{label}.not_functional_role 必须为 true")
            valid = False
        judgment = str(review.get("manual_judgment") or "").strip()
        if len(judgment) < 20:
            errors.append(f"{label}.manual_judgment 必须说明稳定偏手与变化")
            valid = False
        else:
            judgment_signatures.setdefault(normalized_manual_text(judgment), []).append(name)
        if valid:
            passed += 1
    extra = sorted(set(review_map) - set(character_profiles))
    if extra:
        errors.append("人物性格弧引用未建母版人物: " + ", ".join(extra))
    for names in judgment_signatures.values():
        if len(names) > 1:
            errors.append("不同人物不得复用模板化全文性格裁决: " + ", ".join(names))
    return passed


def validate_draft_data(
    data: dict[str, Any], source_original: Path, draft_path: Path
) -> tuple[list[str], dict[str, int]]:
    errors, summary = validate_prewrite_data(data, source_original)
    draft = draft_path.resolve()
    if not draft.is_file():
        errors.append(f"正文不存在: {draft}")
        return errors, summary
    draft_text = read_text(draft)
    binding = data.get("draft")
    if not isinstance(binding, dict):
        errors.append("draft 绑定必须是对象")
    else:
        if not same_file_path(Path(str(binding.get("path") or "")), draft):
            errors.append("文字颗粒度合同绑定的正文路径不一致")
        if binding.get("sha256") != sha256(draft):
            errors.append("正文已变化，必须重新执行全文文字颗粒度复核")

    sections = extract_sections(draft_text)
    scope = data.get("rewrite_scope_review")
    if not isinstance(scope, dict):
        errors.append("rewrite_scope_review 必须声明本轮是初稿、全文重写或局部回修")
    else:
        mode = str(scope.get("mode") or "")
        if mode not in {"first_draft", "full_rewrite", "partial_revision"}:
            errors.append("rewrite_scope_review.mode 必须为 first_draft / full_rewrite / partial_revision")
        expected_ids = nonempty_strings(scope.get("expected_section_ids"))
        rewritten_ids = nonempty_strings(scope.get("rewritten_section_ids"))
        unchanged_ids = nonempty_strings(scope.get("unchanged_section_ids"))
        if expected_ids != list(sections):
            errors.append("rewrite_scope_review.expected_section_ids 必须按顺序覆盖当前正文全部小节")
        if any(section_id not in sections for section_id in rewritten_ids + unchanged_ids):
            errors.append("rewrite_scope_review 引用了当前正文不存在的小节")
        if mode == "full_rewrite":
            if scope.get("full_rewrite_requested") is not True:
                errors.append("全文重写模式必须确认 full_rewrite_requested=true")
            if rewritten_ids != list(sections):
                errors.append("全文重写必须按顺序覆盖当前正文全部数字小节")
            if unchanged_ids:
                errors.append("全文重写不得保留 unchanged_section_ids")
            if scope.get("full_text_read_before_rewrite") is not True:
                errors.append("全文重写前必须完整通读母稿")
            if scope.get("full_text_read_after_rewrite") is not True:
                errors.append("全文重写后必须完整通读新稿")
        if len(str(scope.get("manual_judgment") or "").strip()) < 20:
            errors.append("rewrite_scope_review.manual_judgment 必须说明实际重写范围与验收方法")

    provenance = data.get("manual_review_provenance")
    if not isinstance(provenance, dict):
        errors.append("manual_review_provenance 必须记录人工语义回执来源")
    else:
        if provenance.get("performed_by_current_model") is not True:
            errors.append("人工语义复核必须由当前模型执行")
        if provenance.get("semantic_fields_generated_by_script") is not False:
            errors.append("禁止项目脚本生成 comparison / manual_judgment 等人工语义字段")
        if provenance.get("receipt_population_method") != "current_model_manual_field_entry":
            errors.append("receipt_population_method 必须为 current_model_manual_field_entry")
        if provenance.get("full_text_read_by_current_model") is not True:
            errors.append("当前模型必须完整通读正文后再回填人工语义回执")
        if provenance.get("review_bound_to_draft_sha256") != sha256(draft):
            errors.append("人工语义回执来源未绑定当前正文 SHA")
        raw_automation_artifacts = provenance.get("automation_artifacts_used")
        if not isinstance(raw_automation_artifacts, list):
            errors.append("automation_artifacts_used 必须是受控类别列表")
        automation_artifacts = nonempty_strings(raw_automation_artifacts)
        unknown_automation = sorted(
            set(automation_artifacts)
            - ALLOWED_AUTOMATION_ARTIFACTS
            - FORBIDDEN_SEMANTIC_AUTOMATION_ARTIFACTS
        )
        forbidden_automation = sorted(
            set(automation_artifacts) & FORBIDDEN_SEMANTIC_AUTOMATION_ARTIFACTS
        )
        if forbidden_automation:
            errors.append(
                "人工语义回执不得使用自动语义生成产物: "
                + ", ".join(forbidden_automation)
            )
        if unknown_automation:
            errors.append(
                "automation_artifacts_used 只能填写受控自动化类别: "
                + ", ".join(unknown_automation)
            )
        if len(str(provenance.get("manual_judgment") or "").strip()) < 20:
            errors.append("manual_review_provenance.manual_judgment 必须说明逐节人工复核过程")
    reviews = data.get("section_reviews")
    review_map: dict[str, dict[str, Any]] = {}
    if isinstance(reviews, list):
        review_map = {
            str(item.get("section_id") or ""): item
            for item in reviews
            if isinstance(item, dict) and str(item.get("section_id") or "")
        }
    else:
        errors.append("section_reviews 必须是列表")
    missing = set(sections) - set(review_map)
    extra = set(review_map) - set(sections)
    for section_id in sorted(missing):
        errors.append(f"正文小节缺少文字颗粒度复核: {section_id}")
    for section_id in sorted(extra):
        errors.append(f"文字颗粒度复核引用不存在的小节: {section_id}")

    source_text = read_text(source_original.resolve())
    ultra_fine_baseline = data.get("ultra_fine_source_baseline") or {}
    annotated_source_sentence_features = {
        str(annotation.get("source_sentence") or "").strip(): set(
            nonempty_strings(annotation.get("feature_ids"))
        )
        for passage in (ultra_fine_baseline.get("source_passages") or [])
        if isinstance(passage, dict)
        for annotation in (passage.get("sentence_annotations") or [])
        if isinstance(annotation, dict)
    }
    annotated_source_sentences = set(annotated_source_sentence_features)
    generation_plan_map = {
        str(item.get("section_id") or ""): item
        for item in (data.get("section_generation_plans") or [])
        if isinstance(item, dict) and str(item.get("section_id") or "")
    }
    character_profiles = {
        str(item.get("name") or "").strip(): item
        for item in (
            (data.get("character_personality_layer") or {}).get(
                "target_character_profiles"
            )
            or []
        )
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    passed_sections = 0
    anchor_signatures: dict[tuple[str, ...], list[str]] = {}
    comparison_signatures: dict[str, list[str]] = {}
    for section_id, section_text in sections.items():
        review = review_map.get(section_id)
        if not review:
            continue
        valid = True
        if review.get("status") != "passed":
            errors.append(f"正文小节文字颗粒度未通过: {section_id}")
            valid = False
        quotes = nonempty_strings(review.get("target_quotes"))
        if len(quotes) < 2:
            errors.append(f"正文小节至少需要 2 条目标句面证据: {section_id}")
            valid = False
        for index, quote in enumerate(quotes, start=1):
            if quote not in section_text:
                errors.append(f"目标句面证据不在对应正文小节: {section_id}[{index}]")
                valid = False
        anchors = nonempty_strings(review.get("source_anchors"))
        if len(anchors) < 2:
            errors.append(f"正文小节至少需要 2 条主体原文声线锚: {section_id}")
            valid = False
        for index, quote in enumerate(anchors, start=1):
            if quote not in source_text:
                errors.append(f"声线锚不在主体原文中: {section_id}[{index}]")
                valid = False
        if anchors:
            anchor_signatures.setdefault(tuple(anchors), []).append(section_id)
        checked = set(nonempty_strings(review.get("dimensions_checked")))
        if checked != set(REQUIRED_DIMENSIONS):
            errors.append(f"正文小节未覆盖全部文字颗粒度维度: {section_id}")
            valid = False
        for field, expected in (
            ("source_voice_preserved", True),
            ("functional_alignment_used_as_prose_proof", False),
            ("extra_ai_shell", False),
        ):
            if review.get(field) is not expected:
                errors.append(f"正文小节 {field} 必须为 {expected}: {section_id}")
                valid = False
        comparison = str(review.get("comparison") or "").strip()
        if not comparison:
            errors.append(f"正文小节缺少原文—目标文字对照: {section_id}")
            valid = False
        else:
            comparison_signatures.setdefault(comparison, []).append(section_id)
        if review.get("generation_plan_consumed") is not True:
            errors.append(f"正文小节必须在落笔时消费超细颗粒度包: {section_id}")
            valid = False
        plan = generation_plan_map.get(section_id)
        if not plan or plan.get("status") != "passed":
            errors.append(f"正文小节没有已通过的写前落笔包: {section_id}")
            valid = False
        if review.get("semantic_review_method") != "current_model_manual":
            errors.append(
                f"正文小节 semantic_review_method 必须为 current_model_manual: {section_id}"
            )
            valid = False
        if review.get("automation_used_for_semantic_judgment") is not False:
            errors.append(f"正文小节禁止用自动脚本生成语义裁决: {section_id}")
            valid = False
        planned_packets = {
            str(item.get("source_excerpt") or "").strip(): item
            for item in ((plan or {}).get("continuous_source_chain_packets") or [])
            if isinstance(item, dict) and str(item.get("source_excerpt") or "").strip()
        }
        chain_reviews = review.get("continuous_chain_reviews")
        if not isinstance(chain_reviews, list) or len(chain_reviews) < 2:
            errors.append(f"正文小节至少需要 2 组连续原文句链消费复核: {section_id}")
            chain_reviews = []
            valid = False
        reviewed_excerpts: set[str] = set()
        for chain_index, chain_review in enumerate(chain_reviews, start=1):
            chain_label = f"正文小节 {section_id}.连续句链复核[{chain_index}]"
            if not isinstance(chain_review, dict):
                errors.append(f"{chain_label} 必须是对象")
                valid = False
                continue
            source_excerpt = str(chain_review.get("source_excerpt") or "").strip()
            if source_excerpt not in planned_packets or source_excerpt in reviewed_excerpts:
                errors.append(f"{chain_label}.source_excerpt 必须逐一绑定写前连续句链")
                valid = False
            reviewed_excerpts.add(source_excerpt)
            target_chain_quotes = nonempty_strings(chain_review.get("target_chain_quotes"))
            if len(target_chain_quotes) < 2:
                errors.append(f"{chain_label}.target_chain_quotes 至少需要 2 条连续目标句")
                valid = False
            for quote in target_chain_quotes:
                if quote not in section_text:
                    errors.append(f"{chain_label} 目标句不在当前正文小节")
                    valid = False
            if len(str(chain_review.get("sequence_comparison") or "").strip()) < 20:
                errors.append(f"{chain_label}.sequence_comparison 必须对照句间推进")
                valid = False
            if chain_review.get("post_action_explanation_removed") is not True:
                errors.append(f"{chain_label} 必须确认动作后未补全知心理算法")
                valid = False
            if chain_review.get("contract_used_during_writing") is not True:
                errors.append(f"{chain_label}.contract_used_during_writing 必须为 true")
                valid = False
            if len(str(chain_review.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"{chain_label}.manual_judgment 必须给出当前模型裁决")
                valid = False
        if set(planned_packets) != reviewed_excerpts:
            errors.append(f"正文小节必须消费全部写前连续原文句链: {section_id}")
            valid = False
        planned_relation_examples = {
            str(item.get("source_excerpt") or "").strip(): item
            for item in ((plan or {}).get("relation_micro_examples") or [])
            if isinstance(item, dict) and str(item.get("source_excerpt") or "").strip()
        }
        relation_reviews = review.get("relation_micro_reviews")
        if not isinstance(relation_reviews, list) or len(relation_reviews) < 2:
            errors.append(f"正文小节至少需要 2 组句间关系与虚词骨架消费复核: {section_id}")
            relation_reviews = []
            valid = False
        reviewed_relation_excerpts: set[str] = set()
        for relation_index, relation_review in enumerate(relation_reviews, start=1):
            relation_label = f"正文小节 {section_id}.句间关系复核[{relation_index}]"
            if not isinstance(relation_review, dict):
                errors.append(f"{relation_label} 必须是对象")
                valid = False
                continue
            source_excerpt = str(relation_review.get("source_excerpt") or "").strip()
            relation_plan = planned_relation_examples.get(source_excerpt)
            if relation_plan is None or source_excerpt in reviewed_relation_excerpts:
                errors.append(f"{relation_label}.source_excerpt 必须逐一绑定写前句间关系包")
                valid = False
                relation_plan = {}
            reviewed_relation_excerpts.add(source_excerpt)
            target_quotes = nonempty_strings(relation_review.get("target_quotes"))
            if not target_quotes:
                errors.append(f"{relation_label}.target_quotes 至少需要一条目标原句")
                valid = False
            for quote in target_quotes:
                if quote not in section_text:
                    errors.append(f"{relation_label} 目标原句不在当前小节")
                    valid = False
            relation_type = str(relation_review.get("relation_type") or "").strip()
            if relation_type != relation_plan.get("target_relation_type"):
                errors.append(f"{relation_label}.relation_type 必须与写前目标关系一致")
                valid = False
            marking_mode = str(relation_review.get("marking_mode") or "").strip()
            if marking_mode != relation_plan.get("target_marking_mode"):
                errors.append(f"{relation_label}.marking_mode 必须与写前关系显隐计划一致")
                valid = False
            target_markers = nonempty_strings(relation_review.get("target_markers"))
            joined_targets = "\n".join(target_quotes)
            planned_target_markers = nonempty_strings(relation_plan.get("target_markers"))
            if target_markers != planned_target_markers:
                errors.append(f"{relation_label}.target_markers 必须与写前关系包一致")
                valid = False
            if marking_mode == "explicit" and (
                not target_markers or any(marker not in joined_targets for marker in target_markers)
            ):
                errors.append(f"{relation_label} 显式关系必须在目标原句中保留真实连接词")
                valid = False
            if marking_mode == "implicit" and target_markers:
                errors.append(f"{relation_label} 隐式关系不得靠机械补词冒充迁移")
                valid = False
            if relation_review.get("source_function_word_logic_preserved") is not True:
                errors.append(f"{relation_label} 必须保留源文虚词与关系逻辑")
                valid = False
            if relation_review.get("mechanical_marker_insertion_avoided") is not True:
                errors.append(f"{relation_label} 必须确认没有机械补转折词")
                valid = False
            if len(str(relation_review.get("comparison") or "").strip()) < 20:
                errors.append(f"{relation_label}.comparison 必须对照正反句的衔接差异")
                valid = False
            if len(str(relation_review.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"{relation_label}.manual_judgment 必须给出当前模型裁决")
                valid = False
        if set(planned_relation_examples) != reviewed_relation_excerpts:
            errors.append(f"正文小节必须消费全部写前句间关系包: {section_id}")
            valid = False
        planned_dialogue_packets = {
            str(item.get("source_excerpt") or "").strip(): item
            for item in ((plan or {}).get("dialogue_voice_packets") or [])
            if isinstance(item, dict) and str(item.get("source_excerpt") or "").strip()
        }
        dialogue_reviews = review.get("dialogue_voice_reviews")
        if not isinstance(dialogue_reviews, list) or len(dialogue_reviews) < 2:
            errors.append(f"正文小节至少需要 2 组原文对白三联包消费复核: {section_id}")
            dialogue_reviews = []
            valid = False
        reviewed_dialogue_excerpts: set[str] = set()
        section_dialogue_turns = set(dialogue_turn_units(section_text))
        for dialogue_index, dialogue_review in enumerate(dialogue_reviews, start=1):
            dialogue_label = f"正文小节 {section_id}.对白消费复核[{dialogue_index}]"
            if not isinstance(dialogue_review, dict):
                errors.append(f"{dialogue_label} 必须是对象")
                valid = False
                continue
            source_excerpt = str(dialogue_review.get("source_excerpt") or "").strip()
            if (
                source_excerpt not in planned_dialogue_packets
                or source_excerpt in reviewed_dialogue_excerpts
            ):
                errors.append(f"{dialogue_label}.source_excerpt 必须逐一绑定写前对白三联包")
                valid = False
            reviewed_dialogue_excerpts.add(source_excerpt)
            target_turns = nonempty_strings(dialogue_review.get("target_dialogue_turns"))
            if len(target_turns) < 2:
                errors.append(f"{dialogue_label}.target_dialogue_turns 至少需要 2 轮当前正文直接对白")
                valid = False
            for turn in target_turns:
                if turn not in section_dialogue_turns:
                    errors.append(f"{dialogue_label} 目标对白不在当前正文小节")
                    valid = False
            for field, expected in (
                ("oral_texture_preserved", True),
                ("functional_compression_avoided", True),
                ("rehearsal_used_as_voice_calibration", True),
                ("rehearsal_copied_verbatim", False),
            ):
                if dialogue_review.get(field) is not expected:
                    errors.append(f"{dialogue_label}.{field} 必须为 {expected}")
                    valid = False
            if len(str(dialogue_review.get("turn_sequence_comparison") or "").strip()) < 20:
                errors.append(f"{dialogue_label}.turn_sequence_comparison 必须对照称呼、找补、关系杠杆和请求顺序")
                valid = False
            if len(str(dialogue_review.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"{dialogue_label}.manual_judgment 必须给出当前模型自然口语裁决")
                valid = False
            for field, minimum in (
                ("speaker_and_scene_role", 4),
                ("concrete_pressure_or_object", 8),
                ("role_substitution_test", 15),
                ("context_window_reviewed", 15),
            ):
                if len(str(dialogue_review.get(field) or "").strip()) < minimum:
                    errors.append(f"{dialogue_label}.{field} 必须具体回填")
                    valid = False
            verdict = str(dialogue_review.get("verdict") or "").strip()
            if verdict not in {"keep", "revise"}:
                errors.append(f"{dialogue_label}.verdict 必须为 keep / revise")
                valid = False
            elif verdict == "revise":
                errors.append(f"{dialogue_label} 仍需回炉对白并重读前后窗口")
                valid = False
        if set(planned_dialogue_packets) != reviewed_dialogue_excerpts:
            errors.append(f"正文小节必须消费全部写前对白三联包: {section_id}")
            valid = False
        sentence_relation_review = review.get("sentence_relation_review")
        if not isinstance(sentence_relation_review, dict):
            errors.append(f"正文小节缺少全节句间关系复核: {section_id}")
            valid = False
        else:
            detected_candidates = hard_coordination_candidate_quotes(section_text)
            recorded_candidates = nonempty_strings(
                sentence_relation_review.get("automatic_candidate_quotes")
            )
            if recorded_candidates != detected_candidates:
                errors.append(f"正文小节硬并列候选与当前正文不一致: {section_id}")
                valid = False
            candidate_reviews = sentence_relation_review.get("candidate_reviews")
            if not isinstance(candidate_reviews, list):
                errors.append(f"正文小节硬并列候选复核必须是列表: {section_id}")
                candidate_reviews = []
                valid = False
            candidate_review_map: dict[str, dict[str, Any]] = {}
            for candidate_index, candidate_review in enumerate(candidate_reviews, start=1):
                candidate_label = f"正文小节 {section_id}.硬并列候选[{candidate_index}]"
                if not isinstance(candidate_review, dict):
                    errors.append(f"{candidate_label} 必须是对象")
                    valid = False
                    continue
                quote = str(candidate_review.get("quote") or "").strip()
                if not quote or quote in candidate_review_map:
                    errors.append(f"{candidate_label}.quote 为空或重复")
                    valid = False
                    continue
                candidate_review_map[quote] = candidate_review
                verdict = str(candidate_review.get("verdict") or "").strip()
                if verdict == "revise":
                    errors.append(f"{candidate_label} 仍需先修改正文")
                    valid = False
                elif verdict != "keep":
                    errors.append(f"{candidate_label}.verdict 必须人工裁决为 keep / revise")
                    valid = False
                if str(candidate_review.get("relation_type") or "").strip() not in RELATION_TYPES:
                    errors.append(f"{candidate_label}.relation_type 无效")
                    valid = False
                if str(candidate_review.get("marking_mode") or "").strip() not in RELATION_MARKING_MODES:
                    errors.append(f"{candidate_label}.marking_mode 无效")
                    valid = False
                for field, minimum in (
                    ("source_relation_basis", 12),
                    ("manual_judgment", 12),
                ):
                    if len(str(candidate_review.get(field) or "").strip()) < minimum:
                        errors.append(f"{candidate_label}.{field} 必须具体")
                        valid = False
            if set(candidate_review_map) != set(detected_candidates):
                errors.append(f"正文小节必须逐条裁决全部硬并列候选: {section_id}")
                valid = False
            if sentence_relation_review.get("reviewed_full_section") is not True:
                errors.append(f"正文小节必须人工复核全部句间关系: {section_id}")
                valid = False
            if sentence_relation_review.get("mechanical_marker_insertion_used") is not False:
                errors.append(f"正文小节不得机械补却、但、而等连接词: {section_id}")
                valid = False
            if nonempty_strings(sentence_relation_review.get("unresolved_residue")):
                errors.append(f"正文小节仍有未处理硬并列或关系误标: {section_id}")
                valid = False
            if len(str(sentence_relation_review.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"正文小节全节句间关系复核缺人工裁决: {section_id}")
                valid = False
        action_review = review.get("action_continuity_review")
        detected_underspecified = underspecified_action_candidate_quotes(section_text)
        detected_bare_stage_directions = bare_stage_direction_candidate_quotes(section_text)
        detected_repeated = action_continuity_candidates(section_text)
        if not isinstance(action_review, dict):
            if detected_underspecified or detected_bare_stage_directions or detected_repeated:
                errors.append(f"正文小节缺少动作对象与连续性复核: {section_id}")
                valid = False
        else:
            recorded_underspecified = nonempty_strings(
                action_review.get("underspecified_action_candidates")
            )
            if detected_underspecified:
                errors.append(
                    f"正文小节仍含无宾语及物动作，必须先改写并重新扫描为 0: {section_id}"
                )
                valid = False
            if recorded_underspecified != detected_underspecified:
                errors.append(f"正文小节无宾语动作候选与当前正文不一致: {section_id}")
                valid = False
            underspecified_reviews = action_review.get("underspecified_action_reviews")
            if not isinstance(underspecified_reviews, list):
                underspecified_reviews = []
                valid = False
            underspecified_review_map = {
                str(item.get("quote") or "").strip(): item
                for item in underspecified_reviews
                if isinstance(item, dict)
            }
            if set(underspecified_review_map) != set(detected_underspecified):
                errors.append(f"正文小节必须逐条裁决无宾语动作候选: {section_id}")
                valid = False
            for quote, item in underspecified_review_map.items():
                action_label = f"正文小节 {section_id}.无宾语动作[{quote}]"
                if len(str(item.get("actor_marker") or "").strip()) < 1:
                    errors.append(f"{action_label} 必须标明动作执行者")
                    valid = False
                if len(str(item.get("object_or_target") or "").strip()) < 2:
                    errors.append(f"{action_label} 必须写出具体动作对象")
                    valid = False
                if len(str(item.get("visible_change") or "").strip()) < 8:
                    errors.append(f"{action_label} 必须说明动作造成的现场变化")
                    valid = False
                if str(item.get("verdict") or "").strip() != "revise":
                    errors.append(f"{action_label} 必须裁决为 revise，并回正文补出对象")
                    valid = False
                if len(str(item.get("manual_judgment") or "").strip()) < 15:
                    errors.append(f"{action_label} 缺少人工裁决")
                    valid = False
            recorded_bare_stage_directions = nonempty_strings(
                action_review.get("bare_stage_direction_candidates")
            )
            if recorded_bare_stage_directions != detected_bare_stage_directions:
                errors.append(f"正文小节空转舞台动作候选与当前正文不一致: {section_id}")
                valid = False
            bare_stage_direction_reviews = action_review.get(
                "bare_stage_direction_reviews"
            )
            if not isinstance(bare_stage_direction_reviews, list):
                bare_stage_direction_reviews = []
                valid = False
            stage_review_map = {
                str(item.get("quote") or "").strip(): item
                for item in bare_stage_direction_reviews
                if isinstance(item, dict)
            }
            if set(stage_review_map) != set(detected_bare_stage_directions):
                errors.append(f"正文小节必须逐条裁决空转舞台动作候选: {section_id}")
                valid = False
            for quote, item in stage_review_map.items():
                action_label = f"正文小节 {section_id}.空转舞台动作[{quote}]"
                for field, minimum in (
                    ("held_object", 1),
                    ("posture_reset", 2),
                    ("direction_or_pressure", 4),
                    ("visible_change", 8),
                    ("manual_judgment", 15),
                ):
                    if len(str(item.get(field) or "").strip()) < minimum:
                        errors.append(f"{action_label}.{field} 必须给出具体人工判断")
                        valid = False
                verdict = str(item.get("verdict") or "").strip()
                if verdict not in {"keep", "revise"}:
                    errors.append(f"{action_label}.verdict 必须为 keep / revise")
                    valid = False
                elif verdict == "revise":
                    errors.append(f"{action_label} 仍需并入去向、阻力或现场后果后重新绑定")
                    valid = False
            recorded_repeated = action_review.get("repeated_action_candidates")
            if recorded_repeated != detected_repeated:
                errors.append(f"正文小节重复动作候选与当前正文不一致: {section_id}")
                valid = False
            repeated_reviews = action_review.get("repeated_action_reviews")
            if not isinstance(repeated_reviews, list):
                repeated_reviews = []
                valid = False
            if len(repeated_reviews) != len(detected_repeated):
                errors.append(f"正文小节必须逐条裁决相邻重复动作: {section_id}")
                valid = False
            for index, item in enumerate(repeated_reviews, start=1):
                repeated_label = f"正文小节 {section_id}.重复动作[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{repeated_label} 必须是对象")
                    valid = False
                    continue
                if len(str(item.get("distinction_or_reason") or "").strip()) < 10:
                    errors.append(f"{repeated_label} 必须说明重复动作是不同执行者、对象或有意连续")
                    valid = False
                if len(str(item.get("visible_change") or "").strip()) < 8:
                    errors.append(f"{repeated_label} 必须说明两次动作之间的可见变化")
                    valid = False
                if str(item.get("verdict") or "").strip() not in {"keep", "revise"}:
                    errors.append(f"{repeated_label}.verdict 必须为 keep / revise")
                    valid = False
                if str(item.get("verdict") or "").strip() == "revise":
                    errors.append(f"{repeated_label} 仍需先改写正文")
                    valid = False
                if len(str(item.get("manual_judgment") or "").strip()) < 15:
                    errors.append(f"{repeated_label} 缺少人工裁决")
                    valid = False
            if (
                detected_underspecified
                or detected_bare_stage_directions
                or detected_repeated
            ) and action_review.get(
                "reviewed_full_section"
            ) is not True:
                errors.append(f"正文小节动作对象与连续性复核必须人工通读全节: {section_id}")
                valid = False
            if (
                detected_underspecified
                or detected_bare_stage_directions
                or detected_repeated
            ) and len(
                str(action_review.get("manual_judgment") or "").strip()
            ) < 20:
                errors.append(f"正文小节动作对象与连续性复核缺人工裁决: {section_id}")
                valid = False
        mappings = review.get("sentence_mappings")
        minimum_mappings = min(4, len(sentence_units(section_text)))
        if not isinstance(mappings, list) or len(mappings) < minimum_mappings:
            errors.append(
                f"正文小节至少需要 {minimum_mappings} 条逐句超细映射: {section_id}"
            )
            mappings = []
            valid = False
        mapped_targets: set[str] = set()
        mapping_signatures: dict[str, list[int]] = {}
        for mapping_index, mapping in enumerate(mappings, start=1):
            label = f"正文小节 {section_id}.逐句映射[{mapping_index}]"
            if not isinstance(mapping, dict):
                errors.append(f"{label} 必须是对象")
                valid = False
                continue
            target_sentence = str(mapping.get("target_sentence") or "").strip()
            if not target_sentence or target_sentence not in section_text:
                errors.append(f"{label}.target_sentence 不在当前小节中")
                valid = False
            if target_sentence in mapped_targets:
                errors.append(f"{label}.target_sentence 不得重复充数")
                valid = False
            mapped_targets.add(target_sentence)
            source_anchor = str(mapping.get("source_anchor_sentence") or "").strip()
            if source_anchor not in annotated_source_sentences:
                errors.append(f"{label}.source_anchor_sentence 必须来自写前逐句标注")
                valid = False
            feature_ids = nonempty_strings(mapping.get("feature_ids"))
            if len(feature_ids) < 2 or any(
                feature_id not in ULTRA_FINE_FEATURE_IDS for feature_id in feature_ids
            ):
                errors.append(f"{label}.feature_ids 至少绑定 2 项超细特征")
                valid = False
            elif source_anchor in annotated_source_sentence_features and not set(
                feature_ids
            ).issubset(annotated_source_sentence_features[source_anchor]):
                errors.append(
                    f"{label}.feature_ids 必须属于 source_anchor_sentence 的真实逐句标注"
                )
                valid = False
            target_surface_evidence = str(
                mapping.get("target_surface_evidence") or ""
            ).strip()
            source_surface_evidence = str(
                mapping.get("source_surface_evidence") or ""
            ).strip()
            if not target_surface_evidence or target_surface_evidence not in target_sentence:
                errors.append(f"{label}.target_surface_evidence 必须来自当前目标句自身证据")
                valid = False
            if not source_surface_evidence or source_surface_evidence not in source_anchor:
                errors.append(f"{label}.source_surface_evidence 必须来自当前源锚句自身证据")
                valid = False
            mechanism_match = str(mapping.get("language_mechanism_match") or "").strip()
            if (
                len(mechanism_match) < 20
                or target_surface_evidence not in mechanism_match
                or source_surface_evidence not in mechanism_match
            ):
                errors.append(
                    f"{label}.language_mechanism_match 必须同时引用目标句与源锚局部证据并具体对照"
                )
                valid = False
            minimal_review = mapping.get("minimal_function_sentence_review")
            detected_minimal = is_minimal_function_sentence(target_sentence)
            if not isinstance(minimal_review, dict):
                errors.append(f"{label}.minimal_function_sentence_review 缺失")
                valid = False
            else:
                if minimal_review.get("detected") is not detected_minimal:
                    errors.append(f"{label}.极短功能句定位结果必须与当前目标句一致")
                    valid = False
                if detected_minimal:
                    source_parallel = str(
                        minimal_review.get("source_parallel_quote") or ""
                    ).strip()
                    if not source_parallel or source_parallel not in source_text:
                        errors.append(f"{label}.极短功能句必须绑定主体原文平行颗粒")
                        valid = False
                    for field, minimum in (
                        ("relation_change", 10),
                        ("personality_or_body_specificity", 10),
                        ("manual_judgment", 15),
                    ):
                        if len(str(minimal_review.get(field) or "").strip()) < minimum:
                            errors.append(f"{label}.极短功能句 {field} 必须具体")
                            valid = False
                    verdict = str(minimal_review.get("verdict") or "").strip()
                    if verdict == "revise":
                        errors.append(f"{label}.极短功能句仍需先修改正文")
                        valid = False
                    elif verdict != "keep":
                        errors.append(f"{label}.极短功能句 verdict 必须人工裁决为 keep / revise")
                        valid = False
            signature_parts: list[str] = []
            for field in TARGET_SENTENCE_MAPPING_FIELDS:
                value = str(mapping.get(field) or "").strip()
                if len(value) < 8:
                    errors.append(f"{label}.{field} 必须具体对照")
                    valid = False
                signature_parts.append(normalized_manual_text(value))
            mapping_signatures.setdefault("|".join(signature_parts), []).append(mapping_index)
            if mapping.get("contract_used_during_writing") is not True:
                errors.append(f"{label}.contract_used_during_writing 必须为 true")
                valid = False
            if mapping.get("surface_copy_rejected") is not True:
                errors.append(f"{label}.surface_copy_rejected 必须为 true")
                valid = False
        for mapping_indexes in mapping_signatures.values():
            if len(mapping_indexes) > 1:
                errors.append(
                    f"正文小节 {section_id} 逐句映射不得复用模板: "
                    + ", ".join(str(item) for item in mapping_indexes)
                )
                valid = False
        if len(str(review.get("section_write_judgment") or "").strip()) < 20:
            errors.append(f"正文小节缺少落笔中使用契约的人工裁决: {section_id}")
            valid = False
        liveliness_review = review.get("liveliness_review")
        if not isinstance(liveliness_review, dict):
            errors.append(f"正文小节缺少成文活性复核: {section_id}")
            valid = False
        else:
            plan_liveliness = (plan or {}).get("liveliness_plan") or {}
            planned_asset_ids = set(nonempty_strings(plan_liveliness.get("asset_ids")))
            consumed_asset_ids = nonempty_strings(
                liveliness_review.get("asset_ids_consumed")
            )
            if len(consumed_asset_ids) < 3 or any(
                item not in planned_asset_ids for item in consumed_asset_ids
            ):
                errors.append(f"正文小节至少消费 3 条写前活性资产: {section_id}")
                valid = False
            living_quotes = nonempty_strings(liveliness_review.get("target_quotes"))
            if len(living_quotes) < 3:
                errors.append(f"正文小节至少需要 3 条成文活性目标句: {section_id}")
                valid = False
            for quote in living_quotes:
                if quote not in section_text:
                    errors.append(f"成文活性目标句不在对应正文小节: {section_id}")
                    valid = False
            if liveliness_review.get("living_language_preserved") is not True:
                errors.append(f"正文小节 living_language_preserved 必须为 true: {section_id}")
                valid = False
            if liveliness_review.get("author_summary_override") is not False:
                errors.append(f"正文小节仍有作者总结盖过人物现场: {section_id}")
                valid = False
            if nonempty_strings(liveliness_review.get("stiffness_patterns_remaining")):
                errors.append(f"正文小节仍有未处理僵硬句面: {section_id}")
                valid = False
            inference_review = liveliness_review.get("explanatory_inference_review")
            if not isinstance(inference_review, dict):
                errors.append(f"正文小节缺少叙述者代判候选复核: {section_id}")
                valid = False
            else:
                detected_candidates = explanatory_narration_candidate_quotes(section_text)
                recorded_candidates = nonempty_strings(
                    inference_review.get("automatic_candidate_quotes")
                )
                if recorded_candidates != detected_candidates:
                    errors.append(f"正文小节叙述者代判候选与当前正文不一致: {section_id}")
                    valid = False
                candidate_reviews = inference_review.get("candidate_reviews")
                if not isinstance(candidate_reviews, list):
                    errors.append(f"正文小节叙述者代判候选复核必须是列表: {section_id}")
                    candidate_reviews = []
                    valid = False
                candidate_review_map: dict[str, dict[str, Any]] = {}
                for candidate_index, candidate_review in enumerate(candidate_reviews, start=1):
                    candidate_label = f"正文小节 {section_id}.叙述者代判候选[{candidate_index}]"
                    if not isinstance(candidate_review, dict):
                        errors.append(f"{candidate_label} 必须是对象")
                        valid = False
                        continue
                    quote = str(candidate_review.get("quote") or "").strip()
                    if not quote or quote in candidate_review_map:
                        errors.append(f"{candidate_label}.quote 为空或重复")
                        valid = False
                        continue
                    candidate_review_map[quote] = candidate_review
                    verdict = str(candidate_review.get("verdict") or "").strip()
                    if verdict == "revise":
                        errors.append(f"{candidate_label} 仍需修改正文并重新绑定")
                        valid = False
                    elif verdict != "keep":
                        errors.append(f"{candidate_label}.verdict 必须人工裁决为 keep / revise")
                        valid = False
                    for field, minimum in (
                        ("observable_scene_basis", 8),
                        ("source_chain_basis", 12),
                        ("manual_judgment", 12),
                    ):
                        if len(str(candidate_review.get(field) or "").strip()) < minimum:
                            errors.append(f"{candidate_label}.{field} 必须具体")
                            valid = False
                if set(candidate_review_map) != set(detected_candidates):
                    errors.append(f"正文小节必须逐条裁决全部叙述者代判候选: {section_id}")
                    valid = False
                if inference_review.get("reviewed_full_section") is not True:
                    errors.append(f"正文小节必须人工复核全部叙述句: {section_id}")
                    valid = False
                if nonempty_strings(inference_review.get("unresolved_residue")):
                    errors.append(f"正文小节仍残留动作后心理算法说明: {section_id}")
                    valid = False
                if len(str(inference_review.get("manual_judgment") or "").strip()) < 20:
                    errors.append(f"正文小节叙述者代判复核缺人工裁决: {section_id}")
                    valid = False
            if len(str(liveliness_review.get("manual_judgment") or "").strip()) < 20:
                errors.append(f"正文小节成文活性人工裁决不能为空: {section_id}")
                valid = False
        if not validate_section_character_vitality(
            review,
            plan,
            section_text,
            character_profiles,
            section_id,
            errors,
        ):
            valid = False
        if valid:
            passed_sections += 1

    for section_group in anchor_signatures.values():
        if len(section_group) > 1:
            errors.append(
                "正文小节不得复用同一组主体声线锚: " + ", ".join(section_group)
            )
    for section_group in comparison_signatures.values():
        if len(section_group) > 1:
            errors.append(
                "正文小节不得复用模板化原文—目标判断: " + ", ".join(section_group)
            )

    passed_subflows = validate_source_subflow_reviews(
        data, source_original, sections, errors
    )
    passed_character_arcs = validate_character_arc_reviews(
        data, character_profiles, sections, errors
    )

    full_review = data.get("full_text_review")
    if not isinstance(full_review, dict):
        errors.append("full_text_review 必须是对象")
    else:
        expected_values = {
            "reviewed_full_text": True,
            "all_sections_reviewed": True,
            "primary_source_voice_dominant": True,
            "auxiliary_style_contamination": False,
            "functional_alignment_used_as_prose_proof": False,
            "remaining_extra_ai_shell": False,
            "character_personality_dominant": True,
        }
        for field, expected in expected_values.items():
            if full_review.get(field) is not expected:
                errors.append(f"full_text_review.{field} 必须为 {expected}")
        if not str(full_review.get("conclusion") or "").strip():
            errors.append("full_text_review.conclusion 不能为空")
    if data.get("gate_status") != "passed":
        errors.append("gate_status 必须为 passed")
    if nonempty_strings(data.get("blocking_failures")):
        errors.append("仍有文字颗粒度阻断项，不能完成初稿停靠")
    summary["draft_sections"] = len(sections)
    summary["passed_sections"] = passed_sections
    summary["passed_subflows"] = passed_subflows
    summary["passed_character_arcs"] = passed_character_arcs
    if passed_sections != len(sections):
        errors.append(
            "逐节深层验证未覆盖全部正文小节: "
            f"passed_sections={passed_sections}, draft_sections={len(sections)}"
        )
    return errors, summary


def iter_sidecar_target_quotes(value: Any) -> list[str]:
    quotes: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in SIDECAR_TARGET_QUOTE_FIELDS:
                if isinstance(item, list):
                    quotes.extend(nonempty_strings(item))
                elif isinstance(item, str) and item.strip():
                    quotes.append(item.strip())
            elif isinstance(item, (dict, list)):
                quotes.extend(iter_sidecar_target_quotes(item))
    elif isinstance(value, list):
        for item in value:
            quotes.extend(iter_sidecar_target_quotes(item))
    return quotes


def collect_sidecar_comparisons(value: Any, locations: dict[str, list[str]], path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in {"comparison", "sequence_comparison", "turn_sequence_comparison"}:
                comparison = str(item or "").strip()
                if comparison:
                    locations.setdefault(normalized_manual_text(comparison), []).append(
                        child_path
                    )
            elif isinstance(item, (dict, list)):
                collect_sidecar_comparisons(item, locations, child_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            collect_sidecar_comparisons(item, locations, f"{path}[{index}]")


def preflight_manual_sidecar_data(
    receipt: dict[str, Any], sidecar: dict[str, Any], draft_path: Path
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    draft = draft_path.resolve()
    if not draft.is_file():
        return [f"正文不存在: {draft}"], {"draft_sections": 0, "sidecar_sections": 0}
    sections = extract_sections(read_text(draft))
    expected_sha = sha256(draft)
    sidecar_sha = str(sidecar.get("draft_sha256") or "").strip()
    if not sidecar_sha:
        provenance = sidecar.get("manual_review_provenance")
        if isinstance(provenance, dict):
            sidecar_sha = str(
                provenance.get("review_bound_to_draft_sha256") or ""
            ).strip()
    if sidecar_sha != expected_sha:
        errors.append("人工侧车未绑定当前正文 SHA，旧稿证据不得合并")

    expected_section_ids = {
        str(item.get("section_id") or "").strip()
        for item in (receipt.get("section_reviews") or [])
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    } or set(sections)
    reviews = sidecar.get("section_reviews")
    if not isinstance(reviews, list):
        errors.append("人工侧车 section_reviews 必须是列表")
        reviews = []
    seen_sections: set[str] = set()
    for index, review in enumerate(reviews, start=1):
        label = f"人工侧车.section_reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label} 必须是对象")
            continue
        section_id = str(review.get("section_id") or "").strip()
        if not section_id or section_id in seen_sections:
            errors.append(f"{label}.section_id 为空或重复")
            continue
        seen_sections.add(section_id)
        if section_id not in sections or section_id not in expected_section_ids:
            errors.append(f"{label} 引用不存在的小节: {section_id}")
            continue
        for quote in iter_sidecar_target_quotes(review):
            if quote not in sections[section_id]:
                errors.append(f"{label} 目标引句不在绑定小节: {quote!r}")

    subflow_reviews = sidecar.get("source_subflow_reviews", [])
    if not isinstance(subflow_reviews, list):
        errors.append("人工侧车 source_subflow_reviews 必须是列表")
        subflow_reviews = []
    for index, review in enumerate(subflow_reviews, start=1):
        label = f"人工侧车.source_subflow_reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label} 必须是对象")
            continue
        target_sections = nonempty_strings(review.get("target_sections"))
        if not target_sections or any(item not in sections for item in target_sections):
            errors.append(f"{label}.target_sections 必须绑定当前正文真实小节")
            continue
        target_text = "\n".join(sections[item] for item in target_sections)
        for quote in iter_sidecar_target_quotes(review.get("dimension_transfers")):
            if quote not in target_text:
                errors.append(f"{label} 目标引句不在 target_sections: {quote!r}")

    arc_reviews = sidecar.get("character_arc_reviews", [])
    if not isinstance(arc_reviews, list):
        errors.append("人工侧车 character_arc_reviews 必须是列表")
        arc_reviews = []
    for index, review in enumerate(arc_reviews, start=1):
        label = f"人工侧车.character_arc_reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label} 必须是对象")
            continue
        section_ids = nonempty_strings(review.get("section_ids"))
        if not section_ids or any(item not in sections for item in section_ids):
            errors.append(f"{label}.section_ids 必须绑定当前正文真实小节")
            continue
        target_text = "\n".join(sections[item] for item in section_ids)
        for field in (
            "stable_bias_quotes",
            "variation_or_break_quotes",
            "private_relation_language_quotes",
        ):
            for quote in nonempty_strings(review.get(field)):
                if quote not in target_text:
                    errors.append(f"{label}.{field} 引句不在绑定小节: {quote!r}")

    comparison_locations: dict[str, list[str]] = {}
    collect_sidecar_comparisons(sidecar, comparison_locations, "")
    for locations in comparison_locations.values():
        if len(locations) > 1:
            errors.append("人工侧车不得复用模板化 comparison: " + ", ".join(locations))
    return errors, {
        "draft_sections": len(sections),
        "sidecar_sections": len(seen_sections),
        "sidecar_subflows": len(subflow_reviews),
        "sidecar_character_arcs": len(arc_reviews),
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_section_progress_receipt(progress_path: Path, draft_path: Path) -> list[str]:
    if not progress_path.is_file():
        return [f"逐节正文进度回执不存在: {progress_path}"]
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"逐节正文进度回执无效: {exc}"]
    errors: list[str] = []
    draft = draft_path.resolve()
    if progress.get("status") != "final_ready":
        errors.append(f"逐节正文进度未 final_ready: {progress.get('status')}")
    if str((progress.get("paths") or {}).get("draft") or "") != str(draft):
        errors.append("逐节进度回执绑定的正文路径不一致")
    if not draft.is_file():
        errors.append(f"正文不存在: {draft}")
    elif progress.get("final_draft_sha256") != sha256(draft):
        errors.append("正文 SHA 与逐节进度 final_ready 绑定不一致")
    sections = progress.get("sections")
    if not isinstance(sections, list) or not sections or any(
        not isinstance(item, dict) or item.get("status") != "passed" for item in sections
    ):
        errors.append("逐节进度回执中存在未 passed 小节")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="全文文字颗粒度合同硬闸")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--source-original", required=True)
    init_parser.add_argument("--receipt", required=True)
    outline_parser = subparsers.add_parser("bind-outline")
    outline_parser.add_argument("--receipt", required=True)
    outline_parser.add_argument("--outline", required=True)
    prewrite_parser = subparsers.add_parser("validate-prewrite")
    prewrite_parser.add_argument("--receipt", required=True)
    prewrite_parser.add_argument("--source-original", required=True)
    prewrite_parser.add_argument("--outline", required=True)
    bind_parser = subparsers.add_parser("bind-draft")
    bind_parser.add_argument("--receipt", required=True)
    bind_parser.add_argument("--draft", required=True)
    bind_parser.add_argument("--section-progress", required=True)
    draft_parser = subparsers.add_parser("validate-draft")
    draft_parser.add_argument("--receipt", required=True)
    draft_parser.add_argument("--source-original", required=True)
    draft_parser.add_argument("--draft", required=True)
    draft_parser.add_argument("--section-progress", required=True)
    sidecar_parser = subparsers.add_parser(
        "preflight-manual-sidecar",
        help="合并前只读检查人工侧车中的旧引句、错节绑定和模板化对照",
    )
    sidecar_parser.add_argument("--receipt", required=True)
    sidecar_parser.add_argument("--sidecar", required=True)
    sidecar_parser.add_argument("--draft", required=True)
    args = parser.parse_args()

    receipt = Path(args.receipt).resolve()
    if args.command == "init":
        source = Path(args.source_original).resolve()
        write_json(receipt, create_receipt(args.project, source))
        print(f"prose_granularity_contract: initialized -> {receipt}")
        return 0
    if not receipt.is_file():
        print(f"prose_granularity_contract: blocked ({args.command})")
        print(f"- 文字颗粒度合同回执不存在: {receipt}")
        return 2
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"prose_granularity_contract: blocked ({args.command})")
        print(f"- 文字颗粒度合同回执不是有效 JSON: {exc}")
        return 2
    if args.command == "bind-outline":
        write_json(receipt, bind_outline(data, Path(args.outline)))
        print(f"prose_granularity_contract: outline bound -> {receipt}")
        return 0
    if args.command == "bind-draft":
        progress_errors = validate_section_progress_receipt(
            Path(args.section_progress).resolve(), Path(args.draft)
        )
        if progress_errors:
            print("prose_granularity_contract: blocked (bind-draft)")
            for error in progress_errors:
                print(f"- {error}")
            return 2
        write_json(receipt, bind_draft(data, Path(args.draft)))
        print(f"prose_granularity_contract: draft bound -> {receipt}")
        return 0
    if args.command == "preflight-manual-sidecar":
        sidecar_path = Path(args.sidecar).resolve()
        if not sidecar_path.is_file():
            print("prose_granularity_contract: blocked (manual-sidecar-preflight)")
            print(f"- 人工侧车不存在: {sidecar_path}")
            return 2
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print("prose_granularity_contract: blocked (manual-sidecar-preflight)")
            print(f"- 人工侧车不是有效 JSON: {exc}")
            return 2
        errors, summary = preflight_manual_sidecar_data(
            data, sidecar, Path(args.draft)
        )
        print(json.dumps(summary, ensure_ascii=False))
        if errors:
            print("prose_granularity_contract: blocked (manual-sidecar-preflight)")
            for error in errors:
                print(f"- {error}")
            return 2
        print("prose_granularity_contract: passed (manual-sidecar-preflight)")
        return 0
    source = Path(args.source_original).resolve()
    if args.command == "validate-prewrite":
        errors, summary = validate_prewrite_data(data, source, Path(args.outline))
        label = "prewrite"
    else:
        errors, summary = validate_draft_data(data, source, Path(args.draft))
        errors = validate_section_progress_receipt(
            Path(args.section_progress).resolve(), Path(args.draft)
        ) + errors
        label = "draft"
    if errors:
        print(f"prose_granularity_contract: blocked ({label})")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"prose_granularity_contract: passed ({label})")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
