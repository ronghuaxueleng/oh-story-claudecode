#!/usr/bin/env python3
"""Validate the primary-source prose granularity contract for short fiction."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_lifecycle import consume_sidecar


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
    "锈住",
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
        self_contained_ending = any(
            re.search(rf"{re.escape(verb)}了?[。！？!?.]?$", stripped)
            for verb in INTRANSITIVE_OR_SELF_CONTAINED_ZHU_VERBS
        )
        if (
            match
            and match.group("verb") not in INTRANSITIVE_OR_SELF_CONTAINED_ZHU_VERBS
            and not self_contained_ending
        ):
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


def section_generation_plan_scaffold(
    section_id: str,
    outline_section_sha256: str = "",
) -> dict[str, Any]:
    plan = {
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
    if outline_section_sha256:
        plan["outline_section_sha256"] = outline_section_sha256
    return plan


def normalized_source_passage_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = data.get("ultra_fine_source_baseline") or {}
    passages = baseline.get("source_passages") or []
    records: list[dict[str, Any]] = []
    for index, passage in enumerate(passages, start=1):
        if not isinstance(passage, dict):
            continue
        passage_id = str(passage.get("passage_id") or passage.get("id") or "").strip()
        source_excerpt = str(passage.get("source_excerpt") or passage.get("quote") or "").strip()
        purpose = str(passage.get("purpose") or "").strip()
        sentence_annotations = passage.get("sentence_annotations") or []
        normalized_annotations = [
            {
                "source_sentence": str(item.get("source_sentence") or "").strip(),
                "feature_ids": nonempty_strings(item.get("feature_ids")),
            }
            for item in sentence_annotations
            if isinstance(item, dict) and str(item.get("source_sentence") or "").strip()
        ]
        source_sentences = [item["source_sentence"] for item in normalized_annotations]
        if not passage_id:
            passage_id = f"PASSAGE-{index:02d}"
        records.append(
            {
                "passage_id": passage_id,
                "source_excerpt": source_excerpt,
                "purpose": purpose,
                "source_sentences": source_sentences,
                "sentence_annotations": normalized_annotations,
                "sentence_count": len(source_sentences),
            }
        )
    return records


def dialogue_excerpt_candidates_from_text(
    source_text: str,
    minimum_length: int = 60,
    minimum_turns: int = 2,
    limit: int = 12,
) -> list[dict[str, Any]]:
    source_units = sentence_units(source_text)
    source_spans: list[tuple[int, int]] = []
    cursor = 0
    for unit in source_units:
        start = source_text.find(unit, cursor)
        if start < 0:
            return []
        end = start + len(unit)
        source_spans.append((start, end))
        cursor = end
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for start in range(len(source_units)):
        for end in range(start, min(len(source_units), start + 8)):
            excerpt = source_text[
                source_spans[start][0] : source_spans[end][1]
            ].strip()
            turns = dialogue_turn_units(excerpt)
            if len(excerpt) < minimum_length or len(turns) < minimum_turns:
                continue
            if excerpt not in seen:
                candidates.append(
                    {
                        "source_excerpt": excerpt,
                        "source_sentence_chain": sentence_units(excerpt),
                        "source_dialogue_turns": turns,
                    }
                )
                seen.add(excerpt)
            break
        if len(candidates) >= limit:
            break
    return candidates


def source_dialogue_excerpt_candidates(
    data: dict[str, Any],
    minimum_length: int = 60,
    minimum_turns: int = 2,
    limit: int = 12,
) -> list[dict[str, Any]]:
    binding = data.get("primary_prose_source") or {}
    source_path = Path(str(binding.get("path") or "")).resolve()
    if not source_path.is_file():
        return []
    return dialogue_excerpt_candidates_from_text(
        read_text(source_path),
        minimum_length=minimum_length,
        minimum_turns=minimum_turns,
        limit=limit,
    )


def section_editor_hints(
    data: dict[str, Any],
    section_id: str,
    section_text: str,
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    existing_plan = plan if isinstance(plan, dict) else {}
    def short_preview(text: str, limit: int = 3) -> str:
        sentences = sentence_units(text)
        if not sentences:
            return text[:120]
        preview = " ".join(sentences[:limit])
        return preview if len(preview) <= 180 else preview[:177] + "..."
    passage_records = normalized_source_passage_records(data)
    selected_passage_ids = set(nonempty_strings(existing_plan.get("source_passage_ids")))
    recommended_passages = []
    for record in passage_records:
        if selected_passage_ids and record["passage_id"] not in selected_passage_ids:
            continue
        recommended_passages.append(
            {
                "passage_id": record["passage_id"],
                "purpose": record["purpose"],
                "source_excerpt_preview": short_preview(record["source_excerpt"]),
                "source_excerpt_sentence_count": record["sentence_count"],
                "source_sentences": record["source_sentences"],
            }
        )
    if not recommended_passages:
        recommended_passages = [
            {
                "passage_id": record["passage_id"],
                "purpose": record["purpose"],
                "source_excerpt_preview": short_preview(record["source_excerpt"]),
                "source_excerpt_sentence_count": record["sentence_count"],
                "source_sentences": record["source_sentences"],
            }
            for record in passage_records
        ]

    detail_cards = []
    for item in data.get("source_detail_card_reviews") or []:
        if not isinstance(item, dict):
            continue
        if section_id not in nonempty_strings(item.get("target_sections")):
            continue
        detail_cards.append(
            {
                "card_id": str(item.get("card_id") or ""),
                "title": str(item.get("title") or ""),
                "source_range": str(item.get("source_range") or ""),
                "source_quote": str(item.get("source_quote") or ""),
                "source_function": str(item.get("source_function") or ""),
                "target_adaptation": str(item.get("target_adaptation") or ""),
                "distinct_function_to_preserve": str(
                    item.get("distinct_function_to_preserve") or ""
                ),
            }
        )

    subflows = []
    for item in data.get("source_subflow_reviews") or []:
        if not isinstance(item, dict):
            continue
        if section_id not in nonempty_strings(item.get("target_sections")):
            continue
        style = item.get("source_style_granularity") or {}
        subflows.append(
            {
                "subflow_id": str(item.get("subflow_id") or ""),
                "source_range": str(item.get("source_range") or ""),
                "target_section_rationale": str(item.get("target_section_rationale") or ""),
                "style_evidence": {
                    field: nonempty_strings((style.get(field) or {}).get("source_evidence"))
                    for field in SOURCE_STYLE_GRANULARITY_FIELDS
                },
            }
        )

    active_character_names = set(
        nonempty_strings((existing_plan.get("character_plan") or {}).get("active_character_names"))
    )
    participant_asset_ids = {
        asset_id
        for participant in ((existing_plan.get("character_plan") or {}).get("participants") or [])
        if isinstance(participant, dict)
        for asset_id in nonempty_strings(participant.get("source_asset_ids"))
    }
    character_profiles = []
    for item in ((data.get("character_personality_layer") or {}).get("target_character_profiles") or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if active_character_names and name not in active_character_names:
            continue
        character_profiles.append(
            {
                "name": name,
                "role": str(item.get("role") or ""),
                "source_asset_ids": nonempty_strings(item.get("source_asset_ids")),
                "speech_pattern": str(item.get("speech_pattern") or ""),
                "action_bias": str(item.get("action_bias") or ""),
                "misfire_pattern": str(item.get("misfire_pattern") or ""),
                "private_relation_language": str(item.get("private_relation_language") or ""),
                "recommended_source_asset_ids": [
                    asset_id
                    for asset_id in nonempty_strings(item.get("source_asset_ids"))
                    if not participant_asset_ids or asset_id in participant_asset_ids
                ],
            }
        )

    evidence_pool = "\n".join(
        [
            section_text.strip(),
            *[item["source_quote"] for item in detail_cards],
            *[
                quote
                for item in subflows
                for quotes in item["style_evidence"].values()
                for quote in quotes
            ],
            *["\n".join(item["source_sentences"]) for item in recommended_passages],
        ]
    )
    selected_liveliness_ids = set(
        nonempty_strings((existing_plan.get("liveliness_plan") or {}).get("asset_ids"))
    )
    liveliness_assets = []
    for item in ((data.get("prose_liveliness_layer") or {}).get("assets") or []):
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or item.get("id") or "")
        source_quote = str(item.get("source_quote") or "")
        if selected_liveliness_ids:
            if asset_id not in selected_liveliness_ids:
                continue
        elif source_quote and source_quote not in evidence_pool:
            continue
        liveliness_assets.append(
            {
                "asset_id": asset_id,
                "type": str(item.get("type") or ""),
                "source_quote": source_quote,
                "live_core": str(item.get("live_core") or ""),
                "transfer_mechanism": str(item.get("transfer_mechanism") or ""),
            }
        )
    if not selected_liveliness_ids:
        liveliness_assets = liveliness_assets[:8]

    source_material_packets = []
    for record in recommended_passages:
        full_record = next(
            (
                item
                for item in passage_records
                if item["passage_id"] == record["passage_id"]
            ),
            None,
        )
        if not full_record:
            continue
        excerpt = full_record["source_excerpt"]
        units = sentence_units(excerpt)
        turns = dialogue_turn_units(excerpt)
        relation_candidates = []
        for sentence_index, sentence in enumerate(units, start=1):
            if len(sentence) < 12:
                continue
            markers = explicit_relation_markers(sentence)
            relation_candidates.append(
                {
                    "candidate_id": (
                        f"REL-{full_record['passage_id']}-{sentence_index:02d}"
                    ),
                    "source_excerpt": sentence,
                    "detected_source_markers": markers,
                    "detected_marking_mode": "explicit" if markers else "implicit",
                }
            )
        mechanism_candidates = []
        for sentence_index, annotation in enumerate(
            full_record["sentence_annotations"], start=1
        ):
            mechanism_candidates.append(
                {
                    **annotation,
                    "candidate_id": (
                        f"MECH-{full_record['passage_id']}-{sentence_index:02d}"
                    ),
                }
            )
        source_material_packets.append(
            {
                "passage_id": full_record["passage_id"],
                "purpose": full_record["purpose"],
                "source_excerpt": excerpt,
                "source_sentence_chain": units,
                "source_dialogue_turns": turns,
                "relation_sentence_candidates": relation_candidates,
                "mechanism_sentence_candidates": mechanism_candidates,
            }
        )

    return {
        "section_outline_excerpt": section_text.strip(),
        "field_fill_order": [
            "manual_judgment",
            "continuous_source_chain_packets",
            "relation_micro_examples",
            "dialogue_voice_packets",
            "sentence_mechanisms",
            "paragraph_plan",
            "window_plan",
            "character_plan",
        ],
        "recommended_source_passages": recommended_passages,
        "mapped_detail_cards": detail_cards,
        "mapped_subflows": subflows,
        "character_profiles": character_profiles,
        "liveliness_assets": liveliness_assets,
        "source_material_packets": source_material_packets,
        "source_dialogue_excerpt_candidates": source_dialogue_excerpt_candidates(data),
        "hard_field_checklist": {
            "continuous_source_chain_packets": "至少 2 组；每组 source_sentence_chain 必须等于 sentence_units(source_excerpt)。",
            "relation_micro_examples": "至少 2 组；source_relation_type/target_relation_type 只能填允许枚举。",
            "dialogue_voice_packets": "至少 2 组；对白源摘录、目标试演、错例都要独立完整。",
            "sentence_mechanisms": "至少 3 个；source_sentence 必须来自本节绑定 source_passage_ids。",
            "character_plan": "active_character_names 必须含主角；participants 不得复用同一反应方案。",
        },
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


def same_file_bindings(
    bound_files: list[dict[str, Any]],
    expected_files: list[dict[str, Any]],
) -> bool:
    if len(bound_files) != len(expected_files):
        return False
    for bound, expected in zip(bound_files, expected_files):
        if not isinstance(bound, dict) or not isinstance(expected, dict):
            return False
        if str(bound.get("sha256") or "") != str(expected.get("sha256") or ""):
            return False
        if not same_file_path(
            Path(str(bound.get("path") or "")),
            Path(str(expected.get("path") or "")),
        ):
            return False
    return True


def subflow_catalog_path(source: Path) -> Path:
    return source.parent.parent / "写作资产" / "子流程索引.jsonl"


def detail_catalog_path(source: Path) -> Path:
    return source.parent.parent / "原文细节库"


def detail_card_records(source: Path) -> list[dict[str, Any]]:
    detail_dir = detail_catalog_path(source)
    if not detail_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    heading_pattern = re.compile(r"^##\s+卡\s+([^｜|\s]+)\s*[｜|]\s*(.+?)\s*$")
    legacy_heading_pattern = re.compile(r"^##\s+(.+?)\s*$")
    field_pattern = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*)$")
    source_range_pattern = re.compile(r"L(\d+)(?:\s*-\s*L(\d+))?")
    source_lines = read_text(source).splitlines()
    for path in sorted(detail_dir.glob("*.md")):
        lines = read_text(path).splitlines()
        starts = [
            index
            for index, line in enumerate(lines)
            if heading_pattern.match(line) or legacy_heading_pattern.match(line)
        ]
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            match = heading_pattern.match(lines[start])
            legacy_match = legacy_heading_pattern.match(lines[start])
            assert match is not None or legacy_match is not None
            fields: dict[str, str] = {}
            for line in lines[start + 1 : end]:
                field_match = field_pattern.match(line.strip())
                if field_match:
                    fields[field_match.group(1).strip()] = field_match.group(2).strip()
            if match is not None:
                card_id = match.group(1).strip()
                title = match.group(2).strip()
            else:
                card_id = f"{path.stem}-{position + 1:03d}"
                title = legacy_match.group(1).strip()
            source_range = fields.get("原文位置", "").strip()
            if not source_range:
                range_match = source_range_pattern.search(fields.get("具体发生了什么", ""))
                if range_match:
                    end_line = range_match.group(2) or range_match.group(1)
                    source_range = f"L{range_match.group(1)}-L{end_line}"
            source_quote = fields.get("原文短语", "").strip().strip("`")
            if not source_quote and source_range:
                range_match = source_range_pattern.fullmatch(source_range)
                if range_match:
                    start_line = max(1, int(range_match.group(1)))
                    end_line = min(len(source_lines), int(range_match.group(2)))
                    source_quote = "\n".join(source_lines[start_line - 1 : end_line]).strip()
            records.append(
                {
                    "card_id": card_id,
                    "category": path.stem,
                    "title": title,
                    "source_file": str(path.resolve()),
                    "source_range": source_range,
                    "source_quote": source_quote,
                    "source_function": (
                        fields.get("这个细节为什么有用")
                        or fields.get("写作功能")
                        or fields.get("动作功能")
                        or fields.get("对白功能")
                        or fields.get("细节价值")
                        or fields.get("翻车落点")
                        or fields.get("后续触发")
                        or fields.get("具体发生了什么")
                        or ""
                    ).strip(),
                }
            )
    ids = [str(item.get("card_id") or "") for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"主体原文细节库存在重复卡号: {detail_dir}")
    return records


def source_detail_card_review_scaffold(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **record,
        "planning_status": "pending",
        "target_sections": [],
        "target_adaptation": "",
        "distinct_function_to_preserve": "",
        "overlap_binding_ids": [],
        "overlap_is_not_omission": "",
        "status": "pending",
        "target_quotes": [],
        "comparison": "",
        "surface_copy_rejected": None,
        "semantic_review_method": "current_model_manual",
        "automation_used_for_semantic_judgment": None,
        "manual_judgment": "",
    }


def apply_detail_plan(data: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Merge a current-model-authored detail plan without generating semantics."""
    if plan.get("mode") != "full_bridge":
        raise ValueError("主体细节卡写前映射 mode 必须为 full_bridge")
    if plan.get("reviewed_by_current_model") is not True:
        raise ValueError("主体细节卡写前映射必须由当前模型逐卡复核")
    if plan.get("semantic_fields_generated_by_script") is not False:
        raise ValueError("主体细节卡写前映射禁止由脚本生成语义字段")
    if len(str(plan.get("manual_judgment") or "").strip()) < 24:
        raise ValueError("主体细节卡写前映射 manual_judgment 过短")
    cards = plan.get("cards")
    reviews = data.get("source_detail_card_reviews")
    if not isinstance(cards, list) or not isinstance(reviews, list):
        raise ValueError("主体细节卡写前映射或合同细节卡列表缺失")
    expected_ids = [str(item.get("card_id") or "") for item in reviews if isinstance(item, dict)]
    actual_ids = [str(item.get("card_id") or "") for item in cards if isinstance(item, dict)]
    if actual_ids != expected_ids or len(actual_ids) != len(set(actual_ids)):
        raise ValueError("主体细节卡写前映射必须与合同细节卡全集同序、等数且不重复")
    outline_path = Path(str((data.get("outline") or {}).get("path") or ""))
    if not outline_path.is_file():
        raise ValueError("文字合同尚未绑定真实细纲，不能应用细节卡写前映射")
    outline_sections = extract_sections(read_text(outline_path))
    merged: list[dict[str, Any]] = []
    for review, card in zip(reviews, cards):
        card_id = str(card.get("card_id") or "")
        targets = nonempty_strings(card.get("target_sections"))
        if not targets or any(section not in outline_sections for section in targets):
            raise ValueError(f"{card_id}.target_sections 必须绑定真实细纲小节")
        for field in ("target_adaptation", "distinct_function_to_preserve", "overlap_is_not_omission"):
            if len(str(card.get(field) or "").strip()) < 12:
                raise ValueError(f"{card_id}.{field} 缺少当前模型逐卡语义计划")
        overlap_ids = nonempty_strings(card.get("overlap_binding_ids"))
        if not overlap_ids:
            raise ValueError(f"{card_id}.overlap_binding_ids 不能为空")
        merged.append({
            **review,
            "planning_status": "passed",
            "target_sections": targets,
            "target_adaptation": str(card["target_adaptation"]).strip(),
            "distinct_function_to_preserve": str(card["distinct_function_to_preserve"]).strip(),
            "overlap_binding_ids": overlap_ids,
            "overlap_is_not_omission": str(card["overlap_is_not_omission"]).strip(),
            "semantic_review_method": "current_model_manual",
            "automation_used_for_semantic_judgment": False,
            "status": "pending",
            "target_quotes": [],
            "comparison": "",
            "surface_copy_rejected": None,
            "manual_judgment": "",
        })
    result = dict(data)
    result["source_detail_card_reviews"] = merged
    result["detail_plan_provenance"] = {
        "reviewed_by_current_model": True,
        "semantic_fields_generated_by_script": False,
        "manual_judgment": str(plan["manual_judgment"]).strip(),
    }
    result["gate_status"] = "pending"
    result["prewrite_status"] = "pending"
    return result


def apply_source_assets(data: dict[str, Any], sidecar: dict[str, Any]) -> dict[str, Any]:
    """Merge current-model-authored book-level prose assets without generating semantics."""
    if sidecar.get("reviewed_by_current_model") is not True:
        raise ValueError("书级文字资产必须由当前模型人工复核")
    if sidecar.get("semantic_fields_generated_by_script") is not False:
        raise ValueError("书级文字资产禁止由脚本生成语义字段")
    if len(str(sidecar.get("manual_judgment") or "").strip()) < 24:
        raise ValueError("书级文字资产 manual_judgment 过短")
    required = (
        "source_baseline",
        "ultra_fine_source_baseline",
        "calibration_samples",
        "prose_liveliness_layer",
        "character_personality_layer",
    )
    missing = [field for field in required if field not in sidecar]
    if missing:
        raise ValueError("书级文字资产侧车缺少字段: " + ", ".join(missing))

    result = dict(data)
    for field in required:
        result[field] = sidecar[field]
    for layer_name in ("prose_liveliness_layer", "character_personality_layer"):
        layer = result.get(layer_name)
        if not isinstance(layer, dict):
            raise ValueError(f"{layer_name} 必须是对象")
        asset_file_path = Path(str(layer.pop("asset_file_path", "") or "")).resolve()
        if not asset_file_path.is_file():
            raise ValueError(f"{layer_name}.asset_file_path 不存在: {asset_file_path}")
        layer["asset_file"] = {
            "path": str(asset_file_path),
            "sha256": sha256(asset_file_path),
        }
    result["reviewed_by_current_model"] = True
    result["source_asset_provenance"] = {
        "reviewed_by_current_model": True,
        "semantic_fields_generated_by_script": False,
        "manual_judgment": str(sidecar["manual_judgment"]).strip(),
    }
    result["gate_status"] = "pending"
    result["prewrite_status"] = "pending"
    return result


def compact_authoring_scaffold(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_id": str(plan.get("section_id") or ""),
        "manual_judgment": "",
        "chains": [],
        "contrasts": [],
        "relations": [],
        "dialogues": [],
        "mechanisms": [],
        "paragraph": ["", "", "", "", "", "", ""],
        "window": ["", "", "", ""],
        "liveliness": {
            "ids": [],
            "fields": ["", "", "", "", "", ""],
            "reject": [],
            "judgment": "",
        },
        "characters": [],
        "interchangeability": "",
        "character_judgment": "",
    }


def compact_authoring_v2_scaffold(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(plan.get("section_id") or ""),
        "j": "",
        "c": [],
        "x": [],
        "r": [],
        "d": [],
        "m": [],
        "p": [""] * len(SECTION_PARAGRAPH_PLAN_FIELDS),
        "w": [""] * len(SECTION_WINDOW_PLAN_FIELDS),
        "l": [[], [""] * len(LIVELINESS_SECTION_PLAN_FIELDS), [], ""],
        "h": [],
        "i": "",
        "cj": "",
    }


def convert_export_to_compact_authoring(sidecar: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(sidecar)
    plans = result.pop("section_generation_plans", [])
    if not isinstance(plans, list) or not plans:
        raise ValueError("待转换侧车缺少 section_generation_plans")
    result["authoring_mode"] = "compact_manual_v2"
    result["compact_authoring_schema"] = {
        "section_keys": {
            "id": "section_id",
            "j": "manual_judgment",
            "c": "chains",
            "x": "contrasts",
            "r": "relations",
            "d": "dialogues",
            "m": "mechanisms",
            "p": "paragraph",
            "w": "window",
            "l": "liveliness",
            "h": "characters",
            "i": "interchangeability",
            "cj": "character_judgment",
        },
        "c[]": ["ref", "motion", "use", "relation", "omit", "judgment"],
        "x[]": ["ref", "bad", "effect", "failure", "rewrite"],
        "r[]": [
            "ref",
            "type",
            "skeleton",
            "rehearsal",
            "bad",
            "failure",
            "transfer",
            "judgment",
        ],
        "d[]": [
            "ref",
            "character",
            "rehearsal",
            "bad",
            "motion",
            "use",
            "texture",
            "leverage",
            "avoid",
            "failure",
            "rewrite",
            "judgment",
        ],
        "m[]": ["ref", "mechanism", "intent", "deviation", "prohibited"],
        "paragraph": list(SECTION_PARAGRAPH_PLAN_FIELDS),
        "window": list(SECTION_WINDOW_PLAN_FIELDS),
        "l": [
            "asset_ids",
            list(LIVELINESS_SECTION_PLAN_FIELDS),
            "stiffness_patterns_rejected",
            "manual_judgment",
        ],
        "h[]": ["name", "source_asset_ids", *SECTION_CHARACTER_PLAN_FIELDS],
        "semantic_boundary": (
            "仅压缩键名、固定布尔值和可机械检测的关系显隐标记；"
            "其余数组位置与正式人工字段一一对应"
        ),
    }
    result["compact_section_plans"] = [
        compact_authoring_v2_scaffold(plan)
        for plan in plans
        if isinstance(plan, dict)
    ]
    return result


def externalize_compact_editor_catalog(
    sidecar: dict[str, Any],
    catalog_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(sidecar)
    hints = result.pop("editor_hints", None)
    if not isinstance(hints, dict):
        raise ValueError("紧凑人工侧车缺少 editor_hints，无法外置取材目录")
    catalog = {
        "catalog_type": "prose_section_plan_editor_catalog_v1",
        "outline_sha256": result.get("outline_sha256"),
        "editor_hints": hints,
    }
    write_json(catalog_path, catalog)
    result["editor_catalog"] = {
        "path": str(catalog_path.resolve()),
        "sha256": sha256(catalog_path),
        "catalog_type": catalog["catalog_type"],
    }
    return result, catalog


def hydrate_compact_editor_catalog(plan: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    if isinstance(result.get("editor_hints"), dict):
        return result
    binding = result.get("editor_catalog")
    if not isinstance(binding, dict):
        return result
    catalog_path = Path(str(binding.get("path") or "")).resolve()
    if not catalog_path.is_file():
        raise ValueError(f"紧凑人工侧车绑定的取材目录不存在: {catalog_path}")
    if sha256(catalog_path) != str(binding.get("sha256") or ""):
        raise ValueError("紧凑人工侧车绑定的取材目录 SHA 已失效")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict):
        raise ValueError("紧凑人工侧车绑定的取材目录顶层必须是对象")
    if catalog.get("catalog_type") != binding.get("catalog_type"):
        raise ValueError("紧凑人工侧车绑定的取材目录类型不一致")
    if catalog.get("outline_sha256") != result.get("outline_sha256"):
        raise ValueError("紧凑人工侧车绑定的取材目录未绑定当前细纲 SHA")
    hints = catalog.get("editor_hints")
    if not isinstance(hints, dict):
        raise ValueError("紧凑人工侧车绑定的取材目录缺少 editor_hints")
    result["editor_hints"] = hints
    return result


def convert_compact_v2_to_v1(plan: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    compact_plans = result.get("compact_section_plans")
    if not isinstance(compact_plans, list) or not compact_plans:
        raise ValueError("compact_manual_v2 缺少 compact_section_plans")

    def row(values: Any, size: int, label: str) -> list[Any]:
        if not isinstance(values, list) or len(values) != size:
            raise ValueError(f"{label} 必须按 schema 固定填写 {size} 项")
        return values

    converted: list[dict[str, Any]] = []
    for compact in compact_plans:
        if not isinstance(compact, dict):
            raise ValueError("compact_section_plans 每项必须是对象")
        section_id = str(compact.get("id") or "").strip()
        chains = [
            {
                "ref": values[0],
                "motion": values[1],
                "use": values[2],
                "relation": values[3],
                "omit": values[4],
                "judgment": values[5],
            }
            for index, item in enumerate(compact.get("c") or [], start=1)
            for values in [row(item, 6, f"第 {section_id} 节 c[{index}]")]
        ]
        contrasts = [
            {
                "ref": values[0],
                "bad": values[1],
                "effect": values[2],
                "failure": values[3],
                "rewrite": values[4],
            }
            for index, item in enumerate(compact.get("x") or [], start=1)
            for values in [row(item, 5, f"第 {section_id} 节 x[{index}]")]
        ]
        relations = [
            {
                "ref": values[0],
                "type": values[1],
                "skeleton": values[2],
                "rehearsal": values[3],
                "bad": values[4],
                "failure": values[5],
                "transfer": values[6],
                "judgment": values[7],
                "source_mode": "",
                "target_mode": "",
                "source_markers": [],
                "target_markers": [],
            }
            for index, item in enumerate(compact.get("r") or [], start=1)
            for values in [row(item, 8, f"第 {section_id} 节 r[{index}]")]
        ]
        dialogues = [
            {
                "ref": values[0],
                "character": values[1],
                "rehearsal": values[2],
                "bad": values[3],
                "motion": values[4],
                "use": values[5],
                "texture": values[6],
                "leverage": values[7],
                "avoid": values[8],
                "failure": values[9],
                "rewrite": values[10],
                "judgment": values[11],
            }
            for index, item in enumerate(compact.get("d") or [], start=1)
            for values in [row(item, 12, f"第 {section_id} 节 d[{index}]")]
        ]
        mechanisms = [
            {
                "ref": values[0],
                "mechanism": values[1],
                "intent": values[2],
                "deviation": values[3],
                "prohibited": values[4],
            }
            for index, item in enumerate(compact.get("m") or [], start=1)
            for values in [row(item, 5, f"第 {section_id} 节 m[{index}]")]
        ]
        liveliness = row(compact.get("l"), 4, f"第 {section_id} 节 l")
        characters = []
        for index, item in enumerate(compact.get("h") or [], start=1):
            values = row(
                item,
                2 + len(SECTION_CHARACTER_PLAN_FIELDS),
                f"第 {section_id} 节 h[{index}]",
            )
            characters.append(
                {
                    "name": values[0],
                    "ids": values[1],
                    "fields": values[2:],
                }
            )
        converted.append(
            {
                "section_id": section_id,
                "manual_judgment": compact.get("j"),
                "chains": chains,
                "contrasts": contrasts,
                "relations": relations,
                "dialogues": dialogues,
                "mechanisms": mechanisms,
                "paragraph": compact.get("p"),
                "window": compact.get("w"),
                "liveliness": {
                    "ids": liveliness[0],
                    "fields": liveliness[1],
                    "reject": liveliness[2],
                    "judgment": liveliness[3],
                },
                "characters": characters,
                "interchangeability": compact.get("i"),
                "character_judgment": compact.get("cj"),
            }
        )
    result["authoring_mode"] = "compact_manual_v1"
    result["compact_section_plans"] = converted
    return result


def expand_compact_section_plans(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("authoring_mode") == "compact_manual_v2":
        return expand_compact_section_plans(convert_compact_v2_to_v1(plan))
    if plan.get("authoring_mode") != "compact_manual_v1":
        return copy.deepcopy(plan)
    result = copy.deepcopy(plan)
    compact_plans = result.get("compact_section_plans")
    if not isinstance(compact_plans, list) or not compact_plans:
        raise ValueError("compact_manual_v1 缺少 compact_section_plans")

    def fixed_fields(
        values: Any,
        names: tuple[str, ...],
        label: str,
    ) -> dict[str, str]:
        if not isinstance(values, list) or len(values) != len(names):
            raise ValueError(f"{label} 必须按固定顺序填写 {len(names)} 项")
        return {name: str(value or "").strip() for name, value in zip(names, values)}

    expanded: list[dict[str, Any]] = []
    for compact in compact_plans:
        if not isinstance(compact, dict):
            raise ValueError("compact_section_plans 每项必须是对象")
        section_id = str(compact.get("section_id") or "").strip()
        if not section_id:
            raise ValueError("compact_section_plans 包含空 section_id")
        chains = []
        for item in compact.get("chains") or []:
            if not isinstance(item, dict):
                raise ValueError(f"第 {section_id} 节 chains 每项必须是对象")
            chains.append(
                {
                    "source_passage_ref": item.get("ref"),
                    "chain_motion": item.get("motion"),
                    "target_scene_use": item.get("use"),
                    "target_sentence_relation": item.get("relation"),
                    "explanation_to_omit": item.get("omit"),
                    "surface_copy_rejected": True,
                    "manual_judgment": item.get("judgment"),
                }
            )
        contrasts = []
        for item in compact.get("contrasts") or []:
            if not isinstance(item, dict):
                raise ValueError(f"第 {section_id} 节 contrasts 每项必须是对象")
            contrasts.append(
                {
                    "positive_source_ref": item.get("ref"),
                    "negative_example": item.get("bad"),
                    "positive_effect": item.get("effect"),
                    "negative_failure": item.get("failure"),
                    "rewrite_instruction": item.get("rewrite"),
                    "surface_copy_rejected": True,
                }
            )
        relations = []
        for item in compact.get("relations") or []:
            if not isinstance(item, dict):
                raise ValueError(f"第 {section_id} 节 relations 每项必须是对象")
            relations.append(
                {
                    "source_relation_ref": item.get("ref"),
                    "source_relation_type": item.get("type"),
                    "target_relation_type": item.get("type"),
                    "source_marking_mode": item.get("source_mode", "implicit"),
                    "target_marking_mode": item.get("target_mode", "implicit"),
                    "source_markers": item.get("source_markers") or [],
                    "target_markers": item.get("target_markers") or [],
                    "source_function_word_skeleton": item.get("skeleton"),
                    "target_rehearsal": item.get("rehearsal"),
                    "negative_example": item.get("bad"),
                    "negative_failure": item.get("failure"),
                    "transfer_instruction": item.get("transfer"),
                    "manual_judgment": item.get("judgment"),
                    "mechanical_marker_insertion_forbidden": True,
                    "surface_copy_rejected": True,
                }
            )
        dialogues = []
        for item in compact.get("dialogues") or []:
            if not isinstance(item, dict):
                raise ValueError(f"第 {section_id} 节 dialogues 每项必须是对象")
            dialogues.append(
                {
                    "source_dialogue_ref": item.get("ref"),
                    "target_character": item.get("character"),
                    "target_rehearsal": item.get("rehearsal"),
                    "negative_example": item.get("bad"),
                    "turn_motion": item.get("motion"),
                    "target_scene_use": item.get("use"),
                    "oral_texture_transfer": item.get("texture"),
                    "relationship_leverage": item.get("leverage"),
                    "functional_compression_to_avoid": item.get("avoid"),
                    "negative_failure": item.get("failure"),
                    "rewrite_instruction": item.get("rewrite"),
                    "surface_copy_rejected": True,
                    "manual_judgment": item.get("judgment"),
                }
            )
        mechanisms = []
        for item in compact.get("mechanisms") or []:
            if not isinstance(item, dict):
                raise ValueError(f"第 {section_id} 节 mechanisms 每项必须是对象")
            mechanisms.append(
                {
                    "source_mechanism_ref": item.get("ref"),
                    "mechanism": item.get("mechanism"),
                    "target_intent": item.get("intent"),
                    "allowed_deviation": item.get("deviation"),
                    "prohibited_shell": item.get("prohibited"),
                    "surface_copy_rejected": True,
                }
            )
        liveliness = compact.get("liveliness") or {}
        if not isinstance(liveliness, dict):
            raise ValueError(f"第 {section_id} 节 liveliness 必须是对象")
        liveliness_fields = fixed_fields(
            liveliness.get("fields"),
            LIVELINESS_SECTION_PLAN_FIELDS,
            f"第 {section_id} 节 liveliness.fields",
        )
        characters = []
        active_names = []
        for item in compact.get("characters") or []:
            if not isinstance(item, dict):
                raise ValueError(f"第 {section_id} 节 characters 每项必须是对象")
            name = str(item.get("name") or "").strip()
            active_names.append(name)
            character_fields = fixed_fields(
                item.get("fields"),
                SECTION_CHARACTER_PLAN_FIELDS,
                f"第 {section_id} 节人物 {name}.fields",
            )
            characters.append(
                {
                    "character_name": name,
                    "source_asset_ids": item.get("ids") or [],
                    **character_fields,
                }
            )
        expanded.append(
            {
                "section_id": section_id,
                "status": "passed",
                "planned_before_draft": True,
                "generation_driver": "continuous_source_chain",
                "single_sentence_features_secondary": True,
                "continuous_source_chain_packets": chains,
                "contrastive_examples": contrasts,
                "relation_micro_examples": relations,
                "dialogue_voice_packets": dialogues,
                "source_passage_ids": [],
                "sentence_mechanisms": mechanisms,
                "paragraph_plan": fixed_fields(
                    compact.get("paragraph"),
                    SECTION_PARAGRAPH_PLAN_FIELDS,
                    f"第 {section_id} 节 paragraph",
                ),
                "window_plan": fixed_fields(
                    compact.get("window"),
                    SECTION_WINDOW_PLAN_FIELDS,
                    f"第 {section_id} 节 window",
                ),
                "liveliness_plan": {
                    "planned_before_draft": True,
                    "asset_ids": liveliness.get("ids") or [],
                    **liveliness_fields,
                    "stiffness_patterns_rejected": liveliness.get("reject") or [],
                    "manual_judgment": liveliness.get("judgment"),
                },
                "character_plan": {
                    "planned_before_draft": True,
                    "active_character_names": active_names,
                    "participants": characters,
                    "interchangeability_risk": compact.get("interchangeability"),
                    "manual_judgment": compact.get("character_judgment"),
                },
                "surface_copy_rejected": True,
                "manual_judgment": compact.get("manual_judgment"),
            }
        )
    result["section_generation_plans"] = expanded
    result["compact_authoring_provenance"] = {
        "mode": "deterministic_key_projection",
        "semantic_fields_generated_by_script": False,
        "source": "compact_section_plans",
    }
    return result


def resolve_section_plan_references(plan: dict[str, Any]) -> dict[str, Any]:
    """Expand source-data references while leaving every semantic field untouched."""
    result = hydrate_compact_editor_catalog(expand_compact_section_plans(plan))
    hints = result.get("editor_hints") or {}
    material_map = {
        str(item.get("passage_id") or ""): item
        for item in hints.get("shared_source_material") or []
        if isinstance(item, dict) and str(item.get("passage_id") or "")
    }
    relation_map: dict[str, dict[str, Any]] = {}
    mechanism_map: dict[str, dict[str, Any]] = {}
    for passage_id, packet in material_map.items():
        for candidate_index, candidate in enumerate(
            packet.get("relation_sentence_candidates") or [], start=1
        ):
            if isinstance(candidate, dict):
                candidate_id = str(
                    candidate.get("candidate_id")
                    or f"REL-{passage_id}-{candidate_index:02d}"
                )
                if candidate_id:
                    relation_map[candidate_id] = candidate
        for candidate_index, candidate in enumerate(
            packet.get("mechanism_sentence_candidates") or [], start=1
        ):
            if isinstance(candidate, dict):
                candidate_id = str(
                    candidate.get("candidate_id")
                    or f"MECH-{passage_id}-{candidate_index:02d}"
                )
                if candidate_id:
                    mechanism_map[candidate_id] = candidate
    for candidate_index, candidate in enumerate(
        hints.get("shared_relation_sentence_candidates") or [], start=1
    ):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(
            candidate.get("candidate_id") or f"REL-CARD-{candidate_index:03d}"
        )
        relation_map[candidate_id] = candidate
    dialogue_map: dict[str, dict[str, Any]] = {}
    for candidate_index, item in enumerate(
        hints.get("shared_dialogue_excerpt_candidates") or [], start=1
    ):
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or f"DLG-{candidate_index:03d}")
        dialogue_map[candidate_id] = item

    def bind_value(
        item: dict[str, Any],
        field: str,
        expected: Any,
        label: str,
    ) -> None:
        current = item.get(field)
        if current not in (None, "", []):
            if current != expected:
                raise ValueError(f"{label}.{field} 与引用候选不一致")
            return
        item[field] = copy.deepcopy(expected)

    plans = result.get("section_generation_plans")
    if not isinstance(plans, list):
        return result
    for section in plans:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "")
        used_passage_ids: list[str] = []
        for index, packet in enumerate(
            section.get("continuous_source_chain_packets") or [], start=1
        ):
            if not isinstance(packet, dict):
                continue
            passage_id = str(packet.get("source_passage_ref") or "").strip()
            if not passage_id:
                continue
            source_packet = material_map.get(passage_id)
            if source_packet is None:
                raise ValueError(
                    f"第 {section_id} 节连续句链[{index}].source_passage_ref 无效: "
                    f"{passage_id}"
                )
            bind_value(
                packet,
                "source_excerpt",
                source_packet.get("source_excerpt") or "",
                f"第 {section_id} 节连续句链[{index}]",
            )
            bind_value(
                packet,
                "source_sentence_chain",
                source_packet.get("source_sentence_chain") or [],
                f"第 {section_id} 节连续句链[{index}]",
            )
            used_passage_ids.append(passage_id)
        for index, example in enumerate(
            section.get("contrastive_examples") or [], start=1
        ):
            if not isinstance(example, dict):
                continue
            passage_id = str(example.get("positive_source_ref") or "").strip()
            if not passage_id:
                continue
            source_packet = material_map.get(passage_id)
            if source_packet is None:
                raise ValueError(
                    f"第 {section_id} 节正反例[{index}].positive_source_ref 无效: "
                    f"{passage_id}"
                )
            bind_value(
                example,
                "positive_source_excerpt",
                source_packet.get("source_excerpt") or "",
                f"第 {section_id} 节正反例[{index}]",
            )
        for index, example in enumerate(
            section.get("relation_micro_examples") or [], start=1
        ):
            if not isinstance(example, dict):
                continue
            candidate_id = str(example.get("source_relation_ref") or "").strip()
            if not candidate_id:
                continue
            candidate = relation_map.get(candidate_id)
            if candidate is None:
                raise ValueError(
                    f"第 {section_id} 节句间关系包[{index}].source_relation_ref 无效: "
                    f"{candidate_id}"
                )
            bind_value(
                example,
                "source_excerpt",
                candidate.get("source_excerpt") or "",
                f"第 {section_id} 节句间关系包[{index}]",
            )
            bind_value(
                example,
                "source_marking_mode",
                candidate.get("detected_marking_mode") or "implicit",
                f"第 {section_id} 节句间关系包[{index}]",
            )
            bind_value(
                example,
                "source_markers",
                candidate.get("detected_source_markers") or [],
                f"第 {section_id} 节句间关系包[{index}]",
            )
            if not str(example.get("target_marking_mode") or "").strip():
                target_markers = explicit_relation_markers(
                    str(example.get("target_rehearsal") or "")
                )
                example["target_markers"] = target_markers
                example["target_marking_mode"] = (
                    "explicit" if target_markers else "implicit"
                )
        for index, packet in enumerate(
            section.get("dialogue_voice_packets") or [], start=1
        ):
            if not isinstance(packet, dict):
                continue
            candidate_id = str(packet.get("source_dialogue_ref") or "").strip()
            if not candidate_id:
                continue
            candidate = dialogue_map.get(candidate_id)
            if candidate is None:
                raise ValueError(
                    f"第 {section_id} 节对白三联包[{index}].source_dialogue_ref 无效: "
                    f"{candidate_id}"
                )
            bind_value(
                packet,
                "source_excerpt",
                candidate.get("source_excerpt") or "",
                f"第 {section_id} 节对白三联包[{index}]",
            )
            bind_value(
                packet,
                "source_dialogue_turns",
                candidate.get("source_dialogue_turns") or [],
                f"第 {section_id} 节对白三联包[{index}]",
            )
        for index, mechanism in enumerate(
            section.get("sentence_mechanisms") or [], start=1
        ):
            if not isinstance(mechanism, dict):
                continue
            candidate_id = str(mechanism.get("source_mechanism_ref") or "").strip()
            if not candidate_id:
                continue
            candidate = mechanism_map.get(candidate_id)
            if candidate is None:
                raise ValueError(
                    f"第 {section_id} 节句机制[{index}].source_mechanism_ref 无效: "
                    f"{candidate_id}"
                )
            bind_value(
                mechanism,
                "source_sentence",
                candidate.get("source_sentence") or "",
                f"第 {section_id} 节句机制[{index}]",
            )
            bind_value(
                mechanism,
                "feature_ids",
                candidate.get("feature_ids") or [],
                f"第 {section_id} 节句机制[{index}]",
            )
            parts = candidate_id.split("-")
            if len(parts) >= 3:
                used_passage_ids.append("-".join(parts[1:-1]))
        if not nonempty_strings(section.get("source_passage_ids")) and used_passage_ids:
            section["source_passage_ids"] = list(dict.fromkeys(used_passage_ids))
    return result


def compact_section_plan_references(plan: dict[str, Any]) -> dict[str, Any]:
    """Replace repeated deterministic source payloads with stable editor-hint refs."""
    result = copy.deepcopy(plan)
    hints = result.get("editor_hints") or {}
    dialogue_candidates = list(hints.get("shared_dialogue_excerpt_candidates") or [])
    relation_candidates = list(hints.get("shared_relation_sentence_candidates") or [])
    seen_dialogue = {
        str(item.get("source_excerpt") or "")
        for item in dialogue_candidates
        if isinstance(item, dict)
    }
    seen_relation = {
        str(item.get("source_excerpt") or "")
        for item in relation_candidates
        if isinstance(item, dict)
    }
    for section_hint in (hints.get("section_hints") or {}).values():
        if not isinstance(section_hint, dict):
            continue
        for card in section_hint.get("mapped_detail_cards") or []:
            if not isinstance(card, dict):
                continue
            source_quote = str(card.get("source_quote") or "")
            for candidate in dialogue_excerpt_candidates_from_text(
                source_quote, limit=2
            ):
                excerpt = str(candidate.get("source_excerpt") or "")
                if excerpt and excerpt not in seen_dialogue:
                    dialogue_candidates.append(candidate)
                    seen_dialogue.add(excerpt)
            for sentence in sentence_units(source_quote):
                if len(sentence) < 12 or sentence in seen_relation:
                    continue
                markers = explicit_relation_markers(sentence)
                relation_candidates.append(
                    {
                        "source_excerpt": sentence,
                        "detected_source_markers": markers,
                        "detected_marking_mode": (
                            "explicit" if markers else "implicit"
                        ),
                    }
                )
                seen_relation.add(sentence)
    for candidate_index, candidate in enumerate(dialogue_candidates, start=1):
        if isinstance(candidate, dict) and not candidate.get("candidate_id"):
            candidate["candidate_id"] = f"DLG-{candidate_index:03d}"
    for candidate_index, candidate in enumerate(relation_candidates, start=1):
        if isinstance(candidate, dict) and not candidate.get("candidate_id"):
            candidate["candidate_id"] = f"REL-CARD-{candidate_index:03d}"
    hints["shared_dialogue_excerpt_candidates"] = dialogue_candidates
    hints["shared_relation_sentence_candidates"] = relation_candidates
    result["editor_hints"] = hints
    material_map = {
        str(item.get("passage_id") or ""): item
        for item in hints.get("shared_source_material") or []
        if isinstance(item, dict) and str(item.get("passage_id") or "")
    }
    excerpt_to_passage = {
        str(item.get("source_excerpt") or ""): passage_id
        for passage_id, item in material_map.items()
    }
    relation_by_excerpt: dict[str, str] = {}
    mechanism_by_signature: dict[tuple[str, tuple[str, ...]], str] = {}
    for passage_id, packet in material_map.items():
        for candidate_index, candidate in enumerate(
            packet.get("relation_sentence_candidates") or [], start=1
        ):
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(
                candidate.get("candidate_id")
                or f"REL-{passage_id}-{candidate_index:02d}"
            )
            relation_by_excerpt[str(candidate.get("source_excerpt") or "")] = candidate_id
        for candidate_index, candidate in enumerate(
            packet.get("mechanism_sentence_candidates") or [], start=1
        ):
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(
                candidate.get("candidate_id")
                or f"MECH-{passage_id}-{candidate_index:02d}"
            )
            signature = (
                str(candidate.get("source_sentence") or ""),
                tuple(nonempty_strings(candidate.get("feature_ids"))),
            )
            mechanism_by_signature[signature] = candidate_id
    for candidate_index, candidate in enumerate(
        hints.get("shared_relation_sentence_candidates") or [], start=1
    ):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(
            candidate.get("candidate_id") or f"REL-CARD-{candidate_index:03d}"
        )
        relation_by_excerpt[str(candidate.get("source_excerpt") or "")] = candidate_id
    dialogue_by_excerpt: dict[str, str] = {}
    for candidate_index, candidate in enumerate(
        hints.get("shared_dialogue_excerpt_candidates") or [], start=1
    ):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(
            candidate.get("candidate_id") or f"DLG-{candidate_index:03d}"
        )
        dialogue_by_excerpt[str(candidate.get("source_excerpt") or "")] = candidate_id
    plans = result.get("section_generation_plans")
    if not isinstance(plans, list):
        raise ValueError("待压缩逐节侧车缺少 section_generation_plans")
    compacted = 0
    for section in plans:
        if not isinstance(section, dict):
            continue
        for packet in section.get("continuous_source_chain_packets") or []:
            if not isinstance(packet, dict):
                continue
            passage_id = excerpt_to_passage.get(str(packet.get("source_excerpt") or ""))
            if passage_id:
                packet["source_passage_ref"] = passage_id
                packet.pop("source_excerpt", None)
                packet.pop("source_sentence_chain", None)
                compacted += 1
        for example in section.get("contrastive_examples") or []:
            if not isinstance(example, dict):
                continue
            passage_id = excerpt_to_passage.get(
                str(example.get("positive_source_excerpt") or "")
            )
            if passage_id:
                example["positive_source_ref"] = passage_id
                example.pop("positive_source_excerpt", None)
                compacted += 1
        for example in section.get("relation_micro_examples") or []:
            if not isinstance(example, dict):
                continue
            candidate_id = relation_by_excerpt.get(
                str(example.get("source_excerpt") or "")
            )
            if candidate_id:
                example["source_relation_ref"] = candidate_id
                example.pop("source_excerpt", None)
                compacted += 1
        for packet in section.get("dialogue_voice_packets") or []:
            if not isinstance(packet, dict):
                continue
            candidate_id = dialogue_by_excerpt.get(
                str(packet.get("source_excerpt") or "")
            )
            if candidate_id:
                packet["source_dialogue_ref"] = candidate_id
                packet.pop("source_excerpt", None)
                packet.pop("source_dialogue_turns", None)
                compacted += 1
        for mechanism in section.get("sentence_mechanisms") or []:
            if not isinstance(mechanism, dict):
                continue
            signature = (
                str(mechanism.get("source_sentence") or ""),
                tuple(nonempty_strings(mechanism.get("feature_ids"))),
            )
            candidate_id = mechanism_by_signature.get(signature)
            if candidate_id:
                mechanism["source_mechanism_ref"] = candidate_id
                mechanism.pop("source_sentence", None)
                mechanism.pop("feature_ids", None)
                compacted += 1
    result["compact_reference_provenance"] = {
        "deterministic_only": True,
        "semantic_fields_changed": False,
        "compacted_fields": compacted,
    }
    return result


def apply_section_plan(data: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Merge current-model-authored section plans without generating semantics."""
    plan = resolve_section_plan_references(plan)
    if plan.get("reviewed_by_current_model") is not True:
        raise ValueError("文字逐节写前侧车必须由当前模型逐节复核")
    if plan.get("semantic_fields_generated_by_script") is not False:
        raise ValueError("文字逐节写前侧车禁止由脚本生成语义字段")
    if len(str(plan.get("manual_judgment") or "").strip()) < 24:
        raise ValueError("文字逐节写前侧车 manual_judgment 过短")
    outline_binding = data.get("outline") or {}
    outline_path = Path(str(outline_binding.get("path") or ""))
    outline_sha = str(outline_binding.get("sha256") or "")
    if not outline_path.is_file() or sha256(outline_path) != outline_sha:
        raise ValueError("文字合同绑定的细纲不存在或 SHA 已失效")
    if plan.get("outline_sha256") != outline_sha:
        raise ValueError("文字逐节写前侧车未绑定当前细纲 SHA")
    expected = data.get("section_generation_plans")
    supplied = plan.get("section_generation_plans")
    if not isinstance(expected, list) or not isinstance(supplied, list):
        raise ValueError("文字合同或侧车缺少 section_generation_plans")
    expected_ids = [str(item.get("section_id") or "") for item in expected if isinstance(item, dict)]
    actual_ids = [str(item.get("section_id") or "") for item in supplied if isinstance(item, dict)]
    expected_order = {section_id: index for index, section_id in enumerate(expected_ids)}
    if (
        not actual_ids
        or len(actual_ids) != len(set(actual_ids))
        or any(section_id not in expected_order for section_id in actual_ids)
        or actual_ids != sorted(actual_ids, key=expected_order.get)
    ):
        raise ValueError("文字逐节写前侧车必须引用真实小节、保持原序且不重复")
    supplied_by_id = {
        str(item.get("section_id") or ""): item for item in supplied if isinstance(item, dict)
    }
    outline_sections = extract_sections(read_text(outline_path))
    result = dict(data)
    result["section_generation_plans"] = [
        {
            **supplied_by_id.get(str(item.get("section_id") or ""), item),
            "outline_section_sha256": text_sha256(
                outline_sections.get(str(item.get("section_id") or ""), "")
            ),
        }
        for item in expected
    ]
    result["section_plan_provenance"] = {
        "reviewed_by_current_model": True,
        "semantic_fields_generated_by_script": False,
        "outline_sha256": outline_sha,
        "manual_judgment": str(plan.get("manual_judgment") or "").strip(),
    }
    return result


def export_next_section_plan_pair(
    data: dict[str, Any],
    batch_size: int = 2,
) -> dict[str, Any]:
    """Export the next pending section-plan pair as a fresh editable sidecar."""
    if batch_size < 1:
        raise ValueError("batch_size 必须 >= 1")
    outline_binding = data.get("outline") or {}
    outline_sha = str(outline_binding.get("sha256") or "").strip()
    if not outline_sha:
        raise ValueError("文字合同尚未绑定细纲，不能导出逐节侧车")
    outline_path = Path(str(outline_binding.get("path") or "")).resolve()
    if not outline_path.is_file():
        raise ValueError("文字合同绑定的细纲不存在，不能导出逐节侧车")
    sections = extract_sections(read_text(outline_path))
    plans = data.get("section_generation_plans")
    if not isinstance(plans, list):
        raise ValueError("文字合同缺少 section_generation_plans")
    pending = [
        item
        for item in plans
        if isinstance(item, dict) and str(item.get("status") or "").strip() != "passed"
    ]
    if not pending:
        raise ValueError("没有待补的逐节落笔包")
    selected = pending[:batch_size]
    section_hints = {
        str(item.get("section_id") or ""): section_editor_hints(
            data,
            str(item.get("section_id") or ""),
            sections.get(str(item.get("section_id") or ""), ""),
            item,
        )
        for item in selected
        if isinstance(item, dict) and str(item.get("section_id") or "")
    }
    shared_source_material: dict[str, dict[str, Any]] = {}
    shared_dialogue_candidates: list[dict[str, Any]] = []
    shared_relation_candidates: list[dict[str, Any]] = []
    shared_detail_cards: dict[str, dict[str, Any]] = {}
    shared_character_profiles: dict[str, dict[str, Any]] = {}
    shared_liveliness_assets: dict[str, dict[str, Any]] = {}
    seen_dialogue_excerpts: set[str] = set()
    seen_relation_excerpts: set[str] = set()
    for hint in section_hints.values():
        detail_cards = hint.pop("mapped_detail_cards", [])
        section_dialogue_count = 0
        hint["mapped_detail_card_ids"] = [
            str(card.get("card_id") or "")
            for card in detail_cards
            if isinstance(card, dict) and str(card.get("card_id") or "")
        ]
        for card in detail_cards:
            if not isinstance(card, dict):
                continue
            card_id = str(card.get("card_id") or "")
            source_quote = str(card.get("source_quote") or "")
            if card_id:
                shared_detail_cards[card_id] = {
                    key: value
                    for key, value in card.items()
                    if key != "source_quote"
                }
            if section_dialogue_count >= 2:
                continue
            for candidate in dialogue_excerpt_candidates_from_text(source_quote, limit=2):
                excerpt = str(candidate.get("source_excerpt") or "")
                if excerpt and excerpt not in seen_dialogue_excerpts:
                    shared_dialogue_candidates.append(candidate)
                    seen_dialogue_excerpts.add(excerpt)
                    section_dialogue_count += 1
                    if section_dialogue_count >= 2:
                        break
        character_profiles = hint.pop("character_profiles", [])
        hint["character_profile_names"] = [
            str(profile.get("name") or "")
            for profile in character_profiles
            if isinstance(profile, dict) and str(profile.get("name") or "")
        ]
        for profile in character_profiles:
            if isinstance(profile, dict):
                name = str(profile.get("name") or "")
                if name:
                    shared_character_profiles[name] = profile
        liveliness_assets = hint.pop("liveliness_assets", [])
        hint["liveliness_asset_ids"] = [
            str(asset.get("asset_id") or "")
            for asset in liveliness_assets
            if isinstance(asset, dict) and str(asset.get("asset_id") or "")
        ]
        for asset in liveliness_assets:
            if isinstance(asset, dict):
                asset_id = str(asset.get("asset_id") or "")
                if asset_id:
                    shared_liveliness_assets[asset_id] = asset
        packets = hint.pop("source_material_packets", [])
        hint["source_material_packet_ids"] = [
            str(packet.get("passage_id") or "")
            for packet in packets
            if isinstance(packet, dict) and str(packet.get("passage_id") or "")
        ]
        for packet in packets:
            if not isinstance(packet, dict):
                continue
            passage_id = str(packet.get("passage_id") or "")
            if passage_id:
                shared_source_material[passage_id] = packet
        for candidate in hint.pop("source_dialogue_excerpt_candidates", []):
            if not isinstance(candidate, dict):
                continue
            if len(shared_dialogue_candidates) >= 6:
                break
            excerpt = str(candidate.get("source_excerpt") or "")
            if excerpt and excerpt not in seen_dialogue_excerpts:
                shared_dialogue_candidates.append(candidate)
                seen_dialogue_excerpts.add(excerpt)
        for passage in hint.get("recommended_source_passages") or []:
            if isinstance(passage, dict):
                passage.pop("source_sentences", None)
    for candidate_index, candidate in enumerate(shared_dialogue_candidates, start=1):
        candidate["candidate_id"] = f"DLG-{candidate_index:03d}"
    for candidate_index, candidate in enumerate(shared_relation_candidates, start=1):
        candidate["candidate_id"] = f"REL-CARD-{candidate_index:03d}"
    return {
        "outline_sha256": outline_sha,
        "reviewed_by_current_model": True,
        "semantic_fields_generated_by_script": False,
        "manual_judgment": "",
        "section_generation_plans": selected,
        "editor_hints": {
            "generated_by": "validate_prose_granularity_contract.export-next-section-plan-pair",
            "deterministic_only": True,
            "shared_source_material": list(shared_source_material.values()),
            "shared_dialogue_excerpt_candidates": shared_dialogue_candidates,
            "shared_relation_sentence_candidates": shared_relation_candidates,
            "shared_detail_cards": list(shared_detail_cards.values()),
            "shared_character_profiles": list(shared_character_profiles.values()),
            "shared_liveliness_assets": list(shared_liveliness_assets.values()),
            "section_hints": section_hints,
            "compact_reference_schema": {
                "continuous_source_chain_packets": (
                    "用 source_passage_ref=UF-* 代替重复抄写 source_excerpt 与 "
                    "source_sentence_chain"
                ),
                "contrastive_examples": (
                    "用 positive_source_ref=UF-* 代替重复抄写 "
                    "positive_source_excerpt"
                ),
                "relation_micro_examples": (
                    "用 source_relation_ref=REL-* 代替重复抄写 source_excerpt"
                ),
                "dialogue_voice_packets": (
                    "用 source_dialogue_ref=DLG-* 代替重复抄写 source_excerpt 与 "
                    "source_dialogue_turns"
                ),
                "sentence_mechanisms": (
                    "用 source_mechanism_ref=MECH-* 代替重复抄写 source_sentence 与 "
                    "feature_ids"
                ),
                "semantic_boundary": (
                    "引用只展开主体原文与确定性标注；所有迁移说明、人物归属、关系类型、"
                    "试演、正反例和人工裁决仍由当前模型逐项填写"
                ),
            },
            "manual_brevity_budget": {
                "principle": "每个字段只写一个不可替代判断，覆盖全维度但不重复解释",
                "chain_or_contrast_field_chars": "12-36",
                "relation_or_mechanism_field_chars": "12-32",
                "paragraph_or_window_field_chars": "8-28",
                "character_field_chars": "8-28",
                "section_manual_judgment_chars": "24-60",
            },
        },
    }


def split_section_plan_sidecars(sidecar: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a batch sidecar into independent single-section editing files."""
    plans = sidecar.get("section_generation_plans")
    if not isinstance(plans, list) or not plans:
        raise ValueError("待拆分逐节侧车缺少 section_generation_plans")
    editor_hints = sidecar.get("editor_hints") or {}
    section_hints = editor_hints.get("section_hints") or {}
    results: list[dict[str, Any]] = []
    for plan in plans:
        if not isinstance(plan, dict):
            raise ValueError("待拆分逐节侧车包含非对象小节")
        section_id = str(plan.get("section_id") or "").strip()
        if not section_id:
            raise ValueError("待拆分逐节侧车包含空 section_id")
        results.append(
            {
                "outline_sha256": sidecar.get("outline_sha256"),
                "reviewed_by_current_model": True,
                "semantic_fields_generated_by_script": False,
                "manual_judgment": str(plan.get("manual_judgment") or "").strip(),
                "section_generation_plans": [plan],
                "editor_hints": {
                    **editor_hints,
                    "generated_by": (
                        "validate_prose_granularity_contract."
                        "export-next-section-plan-pair.split"
                    ),
                    "section_hints": {
                        section_id: section_hints.get(section_id, {}),
                    },
                },
            }
        )
    return results


def merge_section_plan_sidecars(
    data: dict[str, Any],
    sidecars: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge disjoint current-model-authored sidecars without creating semantics."""
    if len(sidecars) < 2:
        raise ValueError("合并逐节侧车至少需要 2 份单节文件")
    outline_sha = str((data.get("outline") or {}).get("sha256") or "").strip()
    expected_plans = data.get("section_generation_plans")
    if not outline_sha or not isinstance(expected_plans, list):
        raise ValueError("正式文字合同缺少细纲绑定或逐节计划")
    expected_order = {
        str(item.get("section_id") or ""): index
        for index, item in enumerate(expected_plans)
        if isinstance(item, dict)
    }
    merged_plans: list[dict[str, Any]] = []
    judgments: list[str] = []
    seen_ids: set[str] = set()
    merged_hints: dict[str, Any] = {}
    shared_material: dict[str, dict[str, Any]] = {}
    dialogue_candidates: dict[str, dict[str, Any]] = {}
    section_hints: dict[str, Any] = {}
    for index, sidecar in enumerate(sidecars, start=1):
        if sidecar.get("reviewed_by_current_model") is not True:
            raise ValueError(f"第 {index} 份逐节侧车未声明当前模型复核")
        if sidecar.get("semantic_fields_generated_by_script") is not False:
            raise ValueError(f"第 {index} 份逐节侧车禁止由脚本生成语义字段")
        if sidecar.get("outline_sha256") != outline_sha:
            raise ValueError(f"第 {index} 份逐节侧车未绑定当前细纲 SHA")
        plans = sidecar.get("section_generation_plans")
        if not isinstance(plans, list) or len(plans) != 1 or not isinstance(plans[0], dict):
            raise ValueError(f"第 {index} 份待合并侧车必须只含 1 个小节")
        section_id = str(plans[0].get("section_id") or "").strip()
        if section_id not in expected_order:
            raise ValueError(f"第 {index} 份逐节侧车引用未知小节: {section_id}")
        if section_id in seen_ids:
            raise ValueError(f"待合并逐节侧车重复引用小节: {section_id}")
        seen_ids.add(section_id)
        merged_plans.append(plans[0])
        judgment = str(sidecar.get("manual_judgment") or "").strip()
        if len(judgment) < 24:
            raise ValueError(f"第 {section_id} 节侧车 manual_judgment 过短")
        judgments.append(f"第{section_id}节：{judgment}")
        hints = sidecar.get("editor_hints") or {}
        if not merged_hints:
            merged_hints = dict(hints)
        for packet in hints.get("shared_source_material") or []:
            if isinstance(packet, dict):
                passage_id = str(packet.get("passage_id") or "").strip()
                if passage_id:
                    shared_material[passage_id] = packet
        for candidate in hints.get("shared_dialogue_excerpt_candidates") or []:
            if isinstance(candidate, dict):
                excerpt = str(candidate.get("source_excerpt") or "")
                if excerpt:
                    dialogue_candidates[excerpt] = candidate
        hint = (hints.get("section_hints") or {}).get(section_id)
        if isinstance(hint, dict):
            section_hints[section_id] = hint
    merged_plans.sort(key=lambda item: expected_order[str(item.get("section_id") or "")])
    merged_hints.update(
        {
            "generated_by": (
                "validate_prose_granularity_contract.merge-section-plan-sidecars"
            ),
            "deterministic_only": True,
            "shared_source_material": list(shared_material.values()),
            "shared_dialogue_excerpt_candidates": list(dialogue_candidates.values()),
            "section_hints": section_hints,
        }
    )
    return {
        "outline_sha256": outline_sha,
        "reviewed_by_current_model": True,
        "semantic_fields_generated_by_script": False,
        "manual_judgment": "；".join(judgments),
        "section_generation_plans": merged_plans,
        "editor_hints": merged_hints,
    }


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
    detail_records = detail_card_records(source)
    detail_dir = detail_catalog_path(source)
    detail_files = sorted(detail_dir.glob("*.md")) if detail_dir.is_dir() else []
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
        "primary_detail_catalog": {
            "path": str(detail_dir.resolve()),
            "files": [
                {"path": str(path.resolve()), "sha256": sha256(path)}
                for path in detail_files
            ],
            "required_card_ids": [record["card_id"] for record in detail_records],
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
        "source_detail_card_reviews": [
            source_detail_card_review_scaffold(record) for record in detail_records
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


def validate_detail_catalog_data(
    data: dict[str, Any], source_original: Path, source_text: str, errors: list[str]
) -> list[dict[str, Any]]:
    source = source_original.resolve()
    records = detail_card_records(source)
    binding = data.get("primary_detail_catalog")
    if not isinstance(binding, dict):
        errors.append("primary_detail_catalog 必须绑定主体原文细节库")
        return records
    expected_dir = detail_catalog_path(source).resolve()
    if not same_file_path(Path(str(binding.get("path") or "")), expected_dir):
        errors.append("文字颗粒度合同绑定的主体原文细节库路径不一致")
    expected_files = sorted(expected_dir.glob("*.md")) if expected_dir.is_dir() else []
    bound_files = binding.get("files")
    if not isinstance(bound_files, list):
        errors.append("primary_detail_catalog.files 必须绑定全部细节库文件")
        bound_files = []
    expected_file_bindings = [
        {"path": str(path.resolve()), "sha256": sha256(path)} for path in expected_files
    ]
    if not same_file_bindings(bound_files, expected_file_bindings):
        errors.append("主体原文细节库文件或 SHA 已变化，必须重建细节全集合同")
    expected_ids = [str(record.get("card_id") or "") for record in records]
    if binding.get("required_card_ids") != expected_ids:
        errors.append("primary_detail_catalog.required_card_ids 必须覆盖全部原文细节卡")
    for index, record in enumerate(records, start=1):
        label = f"主体细节卡[{index}] {record.get('card_id')}"
        if not record.get("source_range"):
            errors.append(f"{label}.source_range 不能为空")
        quote = str(record.get("source_quote") or "").strip()
        if not quote or quote not in source_text:
            errors.append(f"{label}.source_quote 不是主体原文真实引用")
        if len(str(record.get("source_function") or "").strip()) < 8:
            errors.append(f"{label}.source_function 必须保留该卡独特功能")
    return records


def validate_detail_card_plans(
    data: dict[str, Any], records: list[dict[str, Any]], outline_path: Path | None,
    errors: list[str]
) -> int:
    if outline_path is None:
        outline_binding = data.get("outline")
        if isinstance(outline_binding, dict) and str(outline_binding.get("path") or ""):
            outline_path = Path(str(outline_binding["path"]))
    outline_sections = extract_sections(read_text(outline_path.resolve())) if outline_path and outline_path.is_file() else {}
    reviews = data.get("source_detail_card_reviews")
    if not isinstance(reviews, list):
        errors.append("source_detail_card_reviews 必须覆盖主体原文全部细节卡")
        return 0
    expected = {str(record["card_id"]): record for record in records}
    actual = {
        str(item.get("card_id") or ""): item
        for item in reviews if isinstance(item, dict) and str(item.get("card_id") or "")
    }
    if list(actual) != list(expected):
        errors.append("source_detail_card_reviews 必须与原文细节卡全集同序、等数")
    passed = 0
    for card_id, record in expected.items():
        label = f"主体细节卡 {card_id}"
        review = actual.get(card_id)
        if review is None:
            errors.append(f"原文细节卡未进入迁移计划: {card_id}")
            continue
        valid = True
        for field in ("category", "title", "source_file", "source_range", "source_quote", "source_function"):
            if field == "source_file":
                field_matches = same_file_path(
                    Path(str(review.get(field) or "")),
                    Path(str(record.get(field) or "")),
                )
            else:
                field_matches = review.get(field) == record.get(field)
            if not field_matches:
                errors.append(f"{label}.{field} 与原文细节库不一致")
                valid = False
        sections = nonempty_strings(review.get("target_sections"))
        if not sections or any(section not in outline_sections for section in sections):
            errors.append(f"{label}.target_sections 必须绑定真实细纲小节")
            valid = False
        for field, minimum in (
            ("target_adaptation", 12),
            ("distinct_function_to_preserve", 12),
            ("overlap_is_not_omission", 12),
        ):
            if len(str(review.get(field) or "").strip()) < minimum:
                errors.append(f"{label}.{field} 必须人工说明")
                valid = False
        overlap_ids = nonempty_strings(review.get("overlap_binding_ids"))
        if not overlap_ids:
            errors.append(f"{label}.overlap_binding_ids 至少绑定一个 E/P/SF 或其他合同颗粒")
            valid = False
        if review.get("planning_status") != "passed":
            errors.append(f"{label}.planning_status 必须为 passed")
            valid = False
        if review.get("semantic_review_method") != "current_model_manual":
            errors.append(f"{label}.semantic_review_method 必须为 current_model_manual")
            valid = False
        if review.get("automation_used_for_semantic_judgment") is not False:
            errors.append(f"{label} 禁止自动生成语义迁移裁决")
            valid = False
        if valid:
            passed += 1
    return passed


def validate_detail_card_draft_reviews(
    data: dict[str, Any], records: list[dict[str, Any]], sections: dict[str, str],
    errors: list[str]
) -> int:
    reviews = data.get("source_detail_card_reviews")
    if not isinstance(reviews, list):
        errors.append("source_detail_card_reviews 必须逐卡绑定正文证据")
        return 0
    by_id = {
        str(item.get("card_id") or ""): item
        for item in reviews if isinstance(item, dict) and str(item.get("card_id") or "")
    }
    passed = 0
    for record in records:
        card_id = str(record["card_id"])
        label = f"主体细节卡 {card_id}"
        review = by_id.get(card_id)
        if review is None:
            errors.append(f"原文细节卡未进入正文终验: {card_id}")
            continue
        valid = True
        target_sections = nonempty_strings(review.get("target_sections"))
        target_text = "\n".join(sections.get(section, "") for section in target_sections)
        quotes = nonempty_strings(review.get("target_quotes"))
        if not quotes:
            errors.append(f"{label}.target_quotes 至少绑定一条正文原句")
            valid = False
        for quote in quotes:
            if quote not in target_text:
                errors.append(f"{label} 目标证据不在绑定小节中: {quote!r}")
                valid = False
        for field, minimum in (("comparison", 15), ("manual_judgment", 15)):
            if len(str(review.get(field) or "").strip()) < minimum:
                errors.append(f"{label}.{field} 必须具体说明独特功能如何落入正文")
                valid = False
        if review.get("status") != "passed":
            errors.append(f"{label}.status 必须为 passed")
            valid = False
        if review.get("surface_copy_rejected") is not True:
            errors.append(f"{label}.surface_copy_rejected 必须为 true")
            valid = False
        if review.get("semantic_review_method") != "current_model_manual" or review.get("automation_used_for_semantic_judgment") is not False:
            errors.append(f"{label} 必须由当前模型人工完成正文裁决")
            valid = False
        if valid:
            passed += 1
    if set(by_id) != {str(record["card_id"]) for record in records}:
        errors.append("正文细节卡复核不得缺卡、增卡或使用旧卡号")
    return passed


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
        for match in re.finditer(
            r"「[^」]{2,}」|『[^』]{2,}』|“[^”]{2,}”", text, flags=re.DOTALL
        )
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
    target_section_ids: set[str] | None = None,
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
    if target_section_ids is None:
        for section_id in sorted(set(sections) - set(plan_map)):
            errors.append(f"正文落笔前缺少小节颗粒度包: {section_id}")
        for section_id in sorted(set(plan_map) - set(sections)):
            errors.append(f"颗粒度包引用不存在的细纲小节: {section_id}")
        iter_section_ids = list(sections.keys())
    else:
        missing_targets = sorted(target_section_ids - set(plan_map))
        for section_id in missing_targets:
            errors.append(f"预检侧车缺少目标小节: {section_id}")
        unknown_targets = sorted(target_section_ids - set(sections))
        for section_id in unknown_targets:
            errors.append(f"预检侧车引用不存在的细纲小节: {section_id}")
        iter_section_ids = [section_id for section_id in sections if section_id in target_section_ids]
    passed = 0
    judgment_signatures: dict[str, list[str]] = {}
    for section_id in iter_section_ids:
        section_text = sections[section_id]
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
                errors.append(
                    f"{packet_label}.source_sentence_chain 必须完整保留连续原文句序；"
                    " expected_sentence_units="
                    + json.dumps(expected_chain, ensure_ascii=False)
                )
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
                errors.append(
                    f"{relation_label}.source_relation_type 无效；"
                    " allowed_relation_types="
                    + json.dumps(list(RELATION_TYPES), ensure_ascii=False)
                )
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
                    errors.append(
                        f"{relation_label}.source_markers 必须是验证器识别到的真实关系词；"
                        " detected_source_markers="
                        + json.dumps(detected_source_markers, ensure_ascii=False)
                    )
                    valid = False
            elif source_markers or detected_source_markers:
                errors.append(
                    f"{relation_label} 含显式关系词时不得自报为 implicit；"
                    " detected_source_markers="
                    + json.dumps(detected_source_markers, ensure_ascii=False)
                )
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
                    errors.append(
                        f"{relation_label}.target_markers 必须是正例中真实可识别的关系词；"
                        " detected_target_markers="
                        + json.dumps(detected_target_markers, ensure_ascii=False)
                    )
                    valid = False
            elif target_markers or detected_target_markers:
                errors.append(
                    f"{relation_label} 隐式目标关系不得含显式关系词；"
                    " detected_target_markers="
                    + json.dumps(detected_target_markers, ensure_ascii=False)
                )
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
                errors.append(
                    f"{packet_label}.source_dialogue_turns 必须完整保留至少 2 轮原文直接对白；"
                    " expected_dialogue_turns="
                    + json.dumps(expected_turns, ensure_ascii=False)
                )
                valid = False
            target_character = str(packet.get("target_character") or "").strip()
            if len(target_character) < 2 and target_character not in character_profiles:
                errors.append(
                    f"{packet_label}.target_character 不得使用未绑定母版的单字占位；"
                    " available_character_profiles="
                    + json.dumps(sorted(character_profiles), ensure_ascii=False)
                )
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
            errors.append(
                f"{label}.source_passage_ids 必须绑定已逐句标注的原文段；"
                " available_source_passage_ids="
                + json.dumps(sorted(passage_map), ensure_ascii=False)
            )
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
                errors.append(
                    f"{item_label}.source_sentence 不在本节绑定原文段中；"
                    " allowed_source_sentences="
                    + json.dumps(sorted(allowed_source_sentences), ensure_ascii=False)
                )
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
                available_assets = {
                    asset_id: str(asset.get("type") or "")
                    for asset_id, asset in liveliness_assets.items()
                }
                errors.append(
                    f"{label}.liveliness_plan.asset_ids 至少绑定 4 条有效活性资产；"
                    " available_liveliness_assets="
                    + json.dumps(available_assets, ensure_ascii=False)
                )
                valid = False
            selected_types = {
                str(liveliness_assets[item].get("type") or "")
                for item in asset_ids
                if item in liveliness_assets
            }
            if len(selected_types) < 3:
                errors.append(
                    f"{label}.liveliness_plan 至少覆盖 3 类活性资产；"
                    " selected_types="
                    + json.dumps(sorted(selected_types), ensure_ascii=False)
                )
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


def preflight_section_plan_data(
    data: dict[str, Any],
    plan: dict[str, Any],
    source_original: Path,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    source_text = validate_source_binding(data, source_original, errors)
    ultra_fine_passages = validate_ultra_fine_source_baseline(data, source_text, errors)
    liveliness_assets = validate_prose_liveliness_layer(data, source_text, errors)
    personality_assets, character_profiles = validate_character_personality_layer(
        data, source_text, errors
    )
    expanded_plan = expand_compact_section_plans(plan)
    merged = apply_section_plan(data, plan)
    supplied = expanded_plan.get("section_generation_plans")
    target_section_ids = {
        str(item.get("section_id") or "").strip()
        for item in supplied
        if isinstance(item, dict) and str(item.get("section_id") or "").strip()
    } if isinstance(supplied, list) else set()
    passed_generation_plans = validate_outline_generation_plans(
        merged,
        None,
        source_text,
        ultra_fine_passages,
        liveliness_assets,
        personality_assets,
        character_profiles,
        errors,
        target_section_ids=target_section_ids,
    )
    return errors, {
        "checked_sections": len(target_section_ids),
        "passed_generation_plans": passed_generation_plans,
    }


def validate_prewrite_data(
    data: dict[str, Any], source_original: Path, outline_path: Path | None = None
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    source_text = validate_source_binding(data, source_original, errors)
    subflow_records = validate_subflow_catalog_data(
        data, source_original, source_text, errors
    )
    detail_records = validate_detail_catalog_data(
        data, source_original, source_text, errors
    )
    passed_detail_plans = validate_detail_card_plans(
        data, detail_records, outline_path, errors
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

    return errors, {
        "valid_excerpts": valid_excerpts,
        "required_dimensions": len(REQUIRED_DIMENSIONS),
        "valid_calibration_samples": valid_samples,
        "required_subflows": len(subflow_records),
        "required_detail_cards": len(detail_records),
        "passed_detail_card_plans": passed_detail_plans,
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


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bind_outline(data: dict[str, Any], outline_path: Path) -> dict[str, Any]:
    outline = outline_path.resolve()
    if not outline.is_file():
        raise FileNotFoundError(f"细纲不存在: {outline}")
    sections = extract_sections(read_text(outline))
    new_outline_sha = sha256(outline)
    old_outline_sha = str((data.get("outline") or {}).get("sha256") or "")
    existing_plans = {
        str(item.get("section_id") or ""): item
        for item in data.get("section_generation_plans") or []
        if isinstance(item, dict) and str(item.get("section_id") or "")
    }
    retained_ids: list[str] = []
    reset_ids: list[str] = []
    added_ids: list[str] = []
    rebound_plans: list[dict[str, Any]] = []
    for section_id, section_text in sections.items():
        section_sha = text_sha256(section_text)
        existing = existing_plans.get(section_id)
        existing_section_sha = (
            str(existing.get("outline_section_sha256") or "") if existing else ""
        )
        unchanged = bool(existing) and (
            existing_section_sha == section_sha
            or (not existing_section_sha and old_outline_sha == new_outline_sha)
        )
        if unchanged:
            rebound_plans.append(
                {
                    **existing,
                    "outline_section_sha256": section_sha,
                }
            )
            retained_ids.append(section_id)
            continue
        fresh = section_generation_plan_scaffold(section_id, section_sha)
        if existing:
            prior_candidate = dict(existing)
            prior_candidate.pop("prior_plan_candidate", None)
            fresh["prior_plan_candidate"] = prior_candidate
            reset_ids.append(section_id)
        else:
            added_ids.append(section_id)
        rebound_plans.append(fresh)
    data["version"] = "2.5"
    data["gate_status"] = "pending"
    data["prewrite_status"] = "pending"
    data["outline"] = {"path": str(outline), "sha256": new_outline_sha}
    data["section_generation_plans"] = rebound_plans
    data["outline_rebind_summary"] = {
        "retained_section_ids": retained_ids,
        "reset_section_ids": reset_ids,
        "added_section_ids": added_ids,
        "removed_section_ids": [
            section_id for section_id in existing_plans if section_id not in sections
        ],
        "full_outline_sha_changed": old_outline_sha != new_outline_sha,
        "unchanged_sections_preserved": True,
    }
    data["blocking_failures"] = []
    return data


def sync_detail_catalog(data: dict[str, Any], source_original: Path) -> dict[str, Any]:
    source = source_original.resolve()
    records = detail_card_records(source)
    detail_dir = detail_catalog_path(source)
    detail_files = sorted(detail_dir.glob("*.md")) if detail_dir.is_dir() else []
    existing = {
        str(item.get("card_id") or ""): item
        for item in data.get("source_detail_card_reviews", [])
        if isinstance(item, dict) and str(item.get("card_id") or "")
    }
    data["primary_detail_catalog"] = {
        "path": str(detail_dir.resolve()),
        "files": [
            {"path": str(path.resolve()), "sha256": sha256(path)}
            for path in detail_files
        ],
        "required_card_ids": [record["card_id"] for record in records],
    }
    data["source_detail_card_reviews"] = [
        {
            **source_detail_card_review_scaffold(record),
            **existing.get(str(record["card_id"]), {}),
            **record,
        }
        for record in records
    ]
    data["gate_status"] = "pending"
    data["prewrite_status"] = "pending"
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
        if (
            existing
            and existing.get("section_sha256") == section_sha256
            and existing.get("status") == "passed"
        ):
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
    existing_detail_reviews = data.get("source_detail_card_reviews")
    if not isinstance(existing_detail_reviews, list):
        existing_detail_reviews = []
    data["source_detail_card_reviews"] = [
        {
            **item,
            "status": "pending",
            "target_quotes": [],
            "comparison": "",
            "surface_copy_rejected": None,
            "manual_judgment": "",
        }
        for item in existing_detail_reviews
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
    # A shared sentence can legitimately contain multiple observable actors;
    # ownership evidence is checked separately by continuous context and marker.
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
    provenance_signatures: dict[str, list[str]] = {}
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
        section_provenance = str(review.get("manual_judgment") or "").strip()
        normalized_provenance = normalized_manual_text(section_provenance)
        if normalized_provenance:
            provenance_signatures.setdefault(normalized_provenance, []).append(section_id)
            if len(normalized_provenance) < 24:
                errors.append(f"正文小节人工裁决过短或模板化: {section_id}")
                valid = False
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
    for section_group in provenance_signatures.values():
        if len(section_group) > 1:
            errors.append(
                "正文小节不得复用同一条人工语义裁决: " + ", ".join(section_group)
            )

    passed_subflows = validate_source_subflow_reviews(
        data, source_original, sections, errors
    )
    detail_records = detail_card_records(source_original.resolve())
    passed_detail_cards = validate_detail_card_draft_reviews(
        data, detail_records, sections, errors
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
    summary["passed_detail_cards"] = passed_detail_cards
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
    detail_parser = subparsers.add_parser(
        "sync-detail-catalog",
        help="向旧合同增量绑定主体八类原文细节卡，不覆盖已有人工裁决",
    )
    detail_parser.add_argument("--receipt", required=True)
    detail_parser.add_argument("--source-original", required=True)
    apply_detail_parser = subparsers.add_parser(
        "apply-detail-plan",
        help="校验并原样合并当前模型逐卡填写的 full_bridge 写前细节映射",
    )
    apply_detail_parser.add_argument("--receipt", required=True)
    apply_detail_parser.add_argument("--plan", required=True)
    apply_detail_parser.add_argument("--consume", action="store_true")
    apply_source_parser = subparsers.add_parser(
        "apply-source-assets",
        help="原样合并当前模型人工完成的书级文字基线、活性层与人物层",
    )
    apply_source_parser.add_argument("--receipt", required=True)
    apply_source_parser.add_argument("--sidecar", required=True)
    apply_source_parser.add_argument("--consume", action="store_true")
    apply_section_parser = subparsers.add_parser(
        "apply-section-plan",
        help="校验并原样合并当前模型逐节填写的文字写前侧车",
    )
    apply_section_parser.add_argument("--receipt", required=True)
    apply_section_parser.add_argument("--plan", required=True)
    apply_section_parser.add_argument("--consume", action="store_true")
    export_section_pair_parser = subparsers.add_parser(
        "export-next-section-plan-pair",
        help="从正式真源导出下一对待补小节的可编辑逐节侧车",
    )
    export_section_pair_parser.add_argument("--receipt", required=True)
    export_section_pair_parser.add_argument("--output", required=True)
    export_section_pair_parser.add_argument("--batch-size", type=int, default=2)
    export_section_pair_parser.add_argument("--split-output-dir")
    export_section_pair_parser.add_argument(
        "--compact-authoring",
        action="store_true",
        help="导出短键、定长数组的无损人工填写格式",
    )
    export_section_pair_parser.add_argument(
        "--catalog-output",
        help="紧凑人工模式的只读取材目录；默认与侧车同目录",
    )
    split_section_sidecar_parser = subparsers.add_parser(
        "split-section-plan-sidecar",
        help="把已有批次逐节侧车拆成互不冲突的单节人工侧车",
    )
    split_section_sidecar_parser.add_argument("--receipt", required=True)
    split_section_sidecar_parser.add_argument("--plan", required=True)
    split_section_sidecar_parser.add_argument("--output-dir", required=True)
    merge_section_sidecars_parser = subparsers.add_parser(
        "merge-section-plan-sidecars",
        help="把不同执行者写入不同文件的单节人工侧车确定性合并为正式批次侧车",
    )
    merge_section_sidecars_parser.add_argument("--receipt", required=True)
    merge_section_sidecars_parser.add_argument("--plans", nargs="+", required=True)
    merge_section_sidecars_parser.add_argument("--output", required=True)
    compact_section_sidecar_parser = subparsers.add_parser(
        "compact-section-plan-sidecar",
        help="把完整逐节侧车中的重复主体原文载荷替换为 UF/REL/DLG/MECH 引用",
    )
    compact_section_sidecar_parser.add_argument("--receipt", required=True)
    compact_section_sidecar_parser.add_argument("--plan", required=True)
    compact_section_sidecar_parser.add_argument("--output", required=True)
    preflight_section_parser = subparsers.add_parser(
        "preflight-section-plan",
        help="在正式 apply 前预检当前批次逐节侧车，只校验侧车涉及的小节",
    )
    preflight_section_parser.add_argument("--receipt", required=True)
    preflight_section_parser.add_argument("--plan", required=True)
    preflight_section_parser.add_argument("--source-original", required=True)
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
        result = bind_outline(data, Path(args.outline))
        write_json(receipt, result)
        summary = result.get("outline_rebind_summary") or {}
        print(
            f"prose_granularity_contract: outline bound -> {receipt}"
            f" (retained={len(summary.get('retained_section_ids') or [])},"
            f" reset={len(summary.get('reset_section_ids') or [])},"
            f" added={len(summary.get('added_section_ids') or [])},"
            f" removed={len(summary.get('removed_section_ids') or [])})"
        )
        return 0
    if args.command == "sync-detail-catalog":
        source = Path(args.source_original).resolve()
        write_json(receipt, sync_detail_catalog(data, source))
        print(f"prose_granularity_contract: detail catalog synced -> {receipt}")
        return 0
    if args.command == "apply-detail-plan":
        plan_path = Path(args.plan).resolve()
        try:
            plan_sha = sha256(plan_path)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(plan, dict):
                raise ValueError("主体细节卡写前映射 JSON 顶层必须是对象")
            result = apply_detail_plan(data, plan)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("prose_granularity_contract: blocked (apply-detail-plan)")
            print(f"- {exc}")
            return 2
        result["detail_plan_provenance"]["path"] = str(plan_path)
        result["detail_plan_provenance"]["sha256"] = plan_sha
        write_json(receipt, result)
        if args.consume:
            consume_sidecar(
                plan_path,
                input_sha256=plan_sha,
                receipt_path=receipt,
                receipt_sha256=sha256(receipt),
                operation="prose-detail-plan.apply",
                counts={"cards": len(plan.get("cards") or [])},
            )
        print(f"prose_granularity_contract: detail plan applied -> {receipt}")
        return 0
    if args.command == "apply-source-assets":
        sidecar_path = Path(args.sidecar).resolve()
        try:
            sidecar_sha = sha256(sidecar_path)
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            if not isinstance(sidecar, dict):
                raise ValueError("书级文字资产侧车 JSON 顶层必须是对象")
            result = apply_source_assets(data, sidecar)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("prose_granularity_contract: blocked (apply-source-assets)")
            print(f"- {exc}")
            return 2
        result["source_asset_provenance"]["path"] = str(sidecar_path)
        result["source_asset_provenance"]["sha256"] = sidecar_sha
        write_json(receipt, result)
        if args.consume:
            consume_sidecar(
                sidecar_path,
                input_sha256=sidecar_sha,
                receipt_path=receipt,
                receipt_sha256=sha256(receipt),
                operation="prose-source-assets.apply",
                counts={
                    "calibration_samples": len(sidecar.get("calibration_samples") or []),
                    "character_profiles": len(
                        (sidecar.get("character_personality_layer") or {}).get("characters") or []
                    ),
                },
            )
        print(f"prose_granularity_contract: source assets applied -> {receipt}")
        return 0
    if args.command == "apply-section-plan":
        plan_path = Path(args.plan).resolve()
        try:
            plan_sha = sha256(plan_path)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(plan, dict):
                raise ValueError("文字逐节写前侧车 JSON 顶层必须是对象")
            result = apply_section_plan(data, plan)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("prose_granularity_contract: blocked (apply-section-plan)")
            print(f"- {exc}")
            return 2
        result["section_plan_provenance"].update(
            {"path": str(plan_path), "sha256": plan_sha}
        )
        write_json(receipt, result)
        if args.consume:
            consume_sidecar(
                plan_path,
                input_sha256=plan_sha,
                receipt_path=receipt,
                receipt_sha256=sha256(receipt),
                operation="prose-section-plan.apply",
                counts={
                    "sections": len(
                        expand_compact_section_plans(plan).get(
                            "section_generation_plans"
                        )
                        or []
                    ),
                },
            )
        print(f"prose_granularity_contract: section plan applied -> {receipt}")
        return 0
    if args.command == "export-next-section-plan-pair":
        output = Path(args.output).resolve()
        try:
            sidecar = export_next_section_plan_pair(data, batch_size=args.batch_size)
            if args.compact_authoring:
                sidecar = convert_export_to_compact_authoring(sidecar)
                catalog_output = (
                    Path(args.catalog_output).resolve()
                    if args.catalog_output
                    else output.with_name(f"{output.stem}.catalog.json")
                )
                sidecar, _ = externalize_compact_editor_catalog(
                    sidecar,
                    catalog_output,
                )
        except ValueError as exc:
            print("prose_granularity_contract: blocked (export-next-section-plan-pair)")
            print(f"- {exc}")
            return 2
        write_json(output, sidecar)
        split_paths: list[Path] = []
        if args.split_output_dir:
            split_output_dir = Path(args.split_output_dir).resolve()
            for single_sidecar in split_section_plan_sidecars(sidecar):
                section_id = str(
                    single_sidecar["section_generation_plans"][0].get("section_id") or ""
                )
                split_path = split_output_dir / f"第{section_id}节人工.json"
                write_json(split_path, single_sidecar)
                split_paths.append(split_path)
        section_ids = [
            str(item.get("id") or item.get("section_id") or "")
            for item in (
                sidecar.get("compact_section_plans")
                if args.compact_authoring
                else sidecar.get("section_generation_plans")
            )
            or []
            if isinstance(item, dict)
        ]
        print(
            "prose_granularity_contract: next section plan pair exported"
            f" -> {output} ({', '.join(section_ids)})"
        )
        if args.compact_authoring:
            print(f"- editor_catalog: {sidecar['editor_catalog']['path']}")
        for split_path in split_paths:
            print(f"- independent_sidecar: {split_path}")
        return 0
    if args.command == "split-section-plan-sidecar":
        plan_path = Path(args.plan).resolve()
        output_dir = Path(args.output_dir).resolve()
        try:
            sidecar = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(sidecar, dict):
                raise ValueError("待拆分逐节侧车 JSON 顶层必须是对象")
            if sidecar.get("outline_sha256") != str(
                (data.get("outline") or {}).get("sha256") or ""
            ):
                raise ValueError("待拆分逐节侧车未绑定当前细纲 SHA")
            split_sidecars = split_section_plan_sidecars(sidecar)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("prose_granularity_contract: blocked (split-section-plan-sidecar)")
            print(f"- {exc}")
            return 2
        split_paths: list[Path] = []
        for single_sidecar in split_sidecars:
            section_id = str(
                single_sidecar["section_generation_plans"][0].get("section_id") or ""
            )
            split_path = output_dir / f"第{section_id}节人工.json"
            write_json(split_path, single_sidecar)
            split_paths.append(split_path)
        print(
            "prose_granularity_contract: section sidecar split"
            f" -> {output_dir} ({len(split_paths)} sections)"
        )
        for split_path in split_paths:
            print(f"- independent_sidecar: {split_path}")
        return 0
    if args.command == "merge-section-plan-sidecars":
        output = Path(args.output).resolve()
        try:
            plan_paths = [Path(value).resolve() for value in args.plans]
            sidecars = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in plan_paths
            ]
            if any(not isinstance(sidecar, dict) for sidecar in sidecars):
                raise ValueError("待合并逐节侧车 JSON 顶层必须是对象")
            merged = merge_section_plan_sidecars(data, sidecars)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("prose_granularity_contract: blocked (merge-section-plan-sidecars)")
            print(f"- {exc}")
            return 2
        write_json(output, merged)
        section_ids = [
            str(item.get("section_id") or "")
            for item in merged.get("section_generation_plans") or []
            if isinstance(item, dict)
        ]
        print(
            "prose_granularity_contract: section sidecars merged"
            f" -> {output} ({', '.join(section_ids)})"
        )
        return 0
    if args.command == "compact-section-plan-sidecar":
        plan_path = Path(args.plan).resolve()
        output = Path(args.output).resolve()
        try:
            sidecar = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(sidecar, dict):
                raise ValueError("待压缩逐节侧车 JSON 顶层必须是对象")
            if sidecar.get("outline_sha256") != str(
                (data.get("outline") or {}).get("sha256") or ""
            ):
                raise ValueError("待压缩逐节侧车未绑定当前细纲 SHA")
            compacted = compact_section_plan_references(sidecar)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("prose_granularity_contract: blocked (compact-section-plan-sidecar)")
            print(f"- {exc}")
            return 2
        write_json(output, compacted)
        stats = compacted.get("compact_reference_provenance") or {}
        print(
            "prose_granularity_contract: section sidecar compacted"
            f" -> {output} (fields={stats.get('compacted_fields', 0)})"
        )
        return 0
    if args.command == "preflight-section-plan":
        plan_path = Path(args.plan).resolve()
        source = Path(args.source_original).resolve()
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(plan, dict):
                raise ValueError("文字逐节写前侧车 JSON 顶层必须是对象")
            errors, stats = preflight_section_plan_data(data, plan, source)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print("prose_granularity_contract: blocked (preflight-section-plan)")
            print(f"- {exc}")
            return 2
        if errors:
            print("prose_granularity_contract: blocked (preflight-section-plan)")
            for error in errors:
                print(f"- {error}")
            return 2
        print(
            "prose_granularity_contract: section plan preflight passed"
            f" -> {plan_path} ({stats['checked_sections']} sections)"
        )
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
    if args.command == "validate-prewrite":
        updated = dict(data)
        updated["prewrite_status"] = "passed"
        write_json(receipt, updated)
    print(f"prose_granularity_contract: passed ({label})")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
