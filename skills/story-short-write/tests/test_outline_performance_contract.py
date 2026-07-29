from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_outline_performance_contract.py"
)
SPEC = importlib.util.spec_from_file_location("outline_performance_contract", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class OutlinePerformanceContractTest(unittest.TestCase):
    @staticmethod
    def emotion_beats(evidence: str | list[str]) -> list[dict]:
        roles = [
            "情绪进入点",
            "受辱或刺痛",
            "短暂希望或反抗",
            "反刀",
            "场末余痛",
        ]
        return [
            {
                "role": role,
                "trigger": f"{role}的具体触发",
                "relationship_position_change": f"{role}后关系位置发生变化",
                "reader_effect": f"读者在{role}感到关系继续恶化",
                "intensity": 7 + min(index, 2),
                "evidence": evidence[index % len(evidence)] if isinstance(evidence, list) else evidence,
            }
            for index, role in enumerate(roles)
        ]

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.outline = self.root / "小节大纲.md"
        self.outline.write_text(
            (
                "## 1. 起事\n"
                "- 情绪：先期待，再被公开刺痛。\n"
                "- 读者新获知：丈夫已经把优先权让给第三人。\n"
                "- 钩子：钥匙会不会真的交出去。\n"
                "- 伏笔/物件：钥匙、门锁报警、挂件。\n"
                "- 动静：先僵住，再换手。\n"
                "- 对话密度：偏低，错答压场。\n"
                "- 目标字数：1000\n\n"
                "动作一 动作二\n"
                "丈夫刚改口时，她还想等一句补救，可手已经先在钥匙圈上松了一下。"
                "门锁报警的红灯一直闪，她盯着那枚两人一起挑的旧挂件，没把那口气顺出去。"
                "她原本要问他到底把谁放在前面，话到了嘴边却只剩一句钥匙是不是现在就得交。"
                "那句错答没救回脸面，反而把她逼进更低的位置，连旁边等着的人都默认下一步该由别人接手。\n\n"
                "钥匙真正换到对方手里时，她掌心还留着金属硌出的印子。"
                "她没有继续闹，只把这一秒的热和难堪记住，准备带到后场去算。"
                "这一节必须把期待、停顿、错答和余痛压在同一连续现场里，不能只写成交钥匙这件事。\n\n"
                "## 2. 失位\n"
                "- 情绪：嘴上退一步，身份继续下沉。\n"
                "- 读者新获知：旁观者已经默认她不再有现场决定权。\n"
                "- 钩子：她还能不能把位置要回来。\n"
                "- 伏笔/物件：门口站位、改口称呼、手机来电。\n"
                "- 动静：外部秩序逼近，关系位置后撤。\n"
                "- 对话密度：中，压着问句走。\n"
                "- 目标字数：1000\n\n"
                "动作三 动作四\n"
                "她退开半步，本来只是想把场面先稳住，可旁边的人已经顺着丈夫的态度改了称呼。"
                "那一下不是谁骂了她，而是所有人都默认该由别人站在里面。"
                "她还想抓住一个解释口，可手机来电把丈夫直接带走，只留下她在原地接收已经发生的排除。"
                "她说出口的话越来越短，像是不想让自己听见真正该问的那句。\n\n"
                "等人群重新流动起来，她才发现自己连下一步该往哪边站都被安排好了。"
                "这一节要把现实秩序怎么替关系补刀写清楚，不能压成一句她继续受伤。"
            ),
            encoding="utf-8",
        )
        self.book_root = self.root / "拆文库" / "测试书"
        self.source = self.book_root / "原文" / "原文.txt"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("原文场面。原文动作。原文余痛。", encoding="utf-8")
        self.catalog = self.book_root / "写作资产" / "桥段施工卡.md"
        self.catalog.parent.mkdir(parents=True)
        self.catalog.write_text("## BID-01 公开掉位\n", encoding="utf-8")
        (self.book_root / "book.profile.json").write_text(
            json.dumps(
                {"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.receipt = self.root / "细纲表演验收回执.json"
        data = GATE.create_receipt("测试", self.outline, [self.source])
        source_path = str(self.source.resolve())
        source_sha = GATE.sha256(self.source)
        data["source_bridge_flow_inventory"] = [
            {
                "source_path": source_path,
                "source_sha256": source_sha,
                "bridge_id": "BID-01",
                "bridge_name": "公开掉位",
                "source_required_sequence": ["先公开偏护", "再让主角失去位置"],
                "source_must_keep_actions": ["对手抢走位置", "旁观者改变站队"],
                "source_scene_granularity": "先抢位置，再由旁观者确认关系掉位。",
                "source_end_state_change": "主角从默认成员变成被公开排除者。",
                "cannot_merge_or_drop_reason": "这是后续撤离成立的第一层现实证据。",
            }
        ]
        data["outline_bridge_flow_parity"] = [
            {
                "source_bridge_id": "BID-01",
                "source_bridge_name": "公开掉位",
                "source_path": source_path,
                "source_sha256": source_sha,
                "source_required_sequence": ["先公开偏护", "再让主角失去位置"],
                "source_must_keep_actions": ["对手抢走位置", "旁观者改变站队"],
                "source_scene_granularity": "先抢位置，再由旁观者确认关系掉位。",
                "source_emotion_sequence": self.emotion_beats(["原文场面", "原文动作", "原文余痛"]),
                "target_emotion_sequence": self.emotion_beats("动作一"),
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 4,
                "target_peak_beat": 4,
                "reader_experience_parity": True,
                "emotion_parity_judgment": "反刀同位，逐拍烈度不低于原文。",
                "target_outline_sections": ["1", "2"],
                "target_outline_evidence": ["动作一", "动作三"],
                "parity_status": "adapted",
                "adaptation_reason": "更换职业和物件，但保留公开站位被抢的流程。",
                "missing_or_weakened_risk": "不能压成一句偏心结论。",
                "manual_judgment": "两节连续完成施压、失位和状态变化。",
            }
        ]

        for section in data["sections"]:
            section.update(
                {
                    "verdict": "passed",
                    "irreversible_action": "位置不可逆变化",
                    "controlling_object": "一件物品",
                    "character_missteps": ["甲先躲", "乙先错答"],
                    "forbidden_items": ["不提前解释", "不连续报账"],
                    "outline_evidence": ["动作一", "动作二"],
                    "manual_judgment": "现场不是清单。",
                }
            )
            if section["section_id"] == "2":
                section["outline_evidence"] = ["动作三", "动作四"]
            section["source_mechanism"] = {
                "source_path": source_path,
                "source_sha256": source_sha,
                "source_scene": "公开偏护",
                "transferable_mechanism": "先发生站位变化，再让关系结论漏出。",
                "adaptation_boundary": "不复制人物、职业、原句或桥壳。",
            }
            section["source_function_mechanism"] = {
                "asset_path": "写作资产/桥段施工卡.md",
                "function_type": "公开掉位",
                "asset_rule": "先改变现实位置，再漏出关系结论。",
                "why_selected_for_this_section": "本节负责建立撤离前的现实伤害。",
            }
            section["original_scene_granularity"] = {
                "source_path": source_path,
                "source_sha256": source_sha,
                "source_scene": "公开偏护",
                "action_sequence": "甲先抢位置，乙阻拦失败，旁观者随后改口。",
                "body_object_space_control": "钥匙和入口控制权从乙转到甲。",
                "dialogue_forces_action": "一句公开确认迫使乙交出钥匙。",
                "bystander_or_order_shift": "旁观者停止等待乙的决定。",
                "scene_end_residue": "乙失去默认成员身份。",
            }
            section["scene_logic_contract"] = {
                "source_path": source_path,
                "source_sha256": source_sha,
                "causal_asset_id": "CPA-01",
                "source_causal_preconditions": ["甲先到入口，乙随后到场阻拦。"],
                "source_evidence": ["原文场面", "原文动作"],
                "target_entry_causes": ["乙收到门锁报警后赶到入口。"],
                "target_knowledge_state": ["乙只知道门锁异常，不知道甲已获丈夫允许。"],
                "key_object_lifecycle": ["钥匙原由乙持有，丈夫表态后才交给甲。"],
                "external_rule_dependency": {
                    "domain": "none",
                    "verified": True,
                    "authoritative_basis": "冲突只依赖人物持有钥匙和主动表态，不借外部制度强推。",
                },
                "obvious_alternative_blocker": ["乙必须现场处理报警，不能直接离开。"],
                "exit_cause": "钥匙换手使乙失去进入权，只能离场。",
                "target_outline_evidence": section["outline_evidence"],
                "manual_judgment": "人物同场、知情差和物件换手均有前置原因。",
            }
            section["information_delay"] = {
                "entry_known": "只知眼前异常。",
                "leaked_in_scene": "只漏出一次偏手。",
                "deferred_to_later": "完整责任留到后场。",
            }
            section["interaction_exchange"] = {
                "pressure": "甲抢控制权。",
                "forced_response": "乙被迫让位。",
                "visible_change": "物件和站位同时变化。",
            }
            section["conflict_carrier"] = {
                "contested_power": "谁能决定现场。",
                "carrier": "钥匙。",
                "consequence": "乙失去进入权。",
            }
            section["relationship_legibility"] = {
                "plain_relationship_roles": "妻子、丈夫和旧爱在公开场争夺谁被优先保护。",
                "plain_relationship_injury": "丈夫当众保护旧爱，让妻子失去原本的位置。",
                "understandable_without_domain_knowledge": True,
            }
            section["emotion_intensity"] = {
                "score": 8,
                "concrete_humiliation_or_pain": "妻子被丈夫当众留下。",
                "emotional_turn": "先被维护，再被公开放弃。",
                "escalation_vs_previous": "第一节建立羞辱，第二节让身份继续掉位。",
            }
            section["professional_shell_translation"] = {
                "plain_language_conflict": "丈夫为了旧爱，要求妻子让位。",
                "domain_detail_function": "钥匙只负责把让位变成现实后果。",
                "conflict_survives_without_jargon": True,
                "relationship_first": True,
            }
            section["source_emotion_parity"] = {
                "source_excerpt": "原文场面",
                "source_emotion_sequence": self.emotion_beats(["原文场面", "原文动作", "原文余痛"]),
                "target_emotion_sequence": self.emotion_beats(
                    section["outline_evidence"][0]
                ),
                "source_intensity_score": 8,
                "target_intensity_score": 8,
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 4,
                "target_peak_beat": 4,
                "ending_afterpain_equivalent": True,
                "reader_experience_equivalent": True,
                "manual_judgment": "逐拍触发、反刀位置和场末余痛达到同级读者体感。",
                "parity_status": "adapted_equal_intensity",
                "adaptation_boundary": "只迁移情绪顺序和烈度，不复制人物与原句。",
            }
            section["first_draft_generation_contract"] = {
                "source_slice_bindings": [
                    {
                        "source_path": source_path,
                        "source_sha256": source_sha,
                        "source_range": "L1-L1",
                        "source_evidence": ["原文场面", "原文动作"],
                        "style_fields_consumed": [
                            "narrative_voice_and_attitude",
                            "sentence_relation_and_rhythm",
                            "paragraph_breath_and_cut_points",
                            "dialogue_misfire_or_avoidance",
                            "action_perception_emotion_weave",
                            "narrator_interjection_and_roughness",
                        ],
                    }
                ],
                "source_performance_excerpt": "原文场面",
                "source_performance_evidence": ["原文动作", "原文余痛"],
                "technique_recall_contract": [
                    {
                        "technique_name": "先动作后判断",
                        "source_summary": "原文先落动作与物件，再让人物判断慢半拍漏出来。",
                        "source_evidence": ["原文场面"],
                        "linked_style_dimensions": ["action_perception_emotion_weave"],
                        "target_execution": "先让她看挂件和钥匙，再漏出受伤判断。",
                        "must_not_flatten_to": "不能压成一句她很难受。",
                        "target_outline_evidence": section["outline_evidence"],
                    },
                    {
                        "technique_name": "句间反冲",
                        "source_summary": "句子靠改口、停顿和反冲接起来，不走均匀摘要。",
                        "source_evidence": ["原文动作", "原文余痛"],
                        "linked_style_dimensions": ["sentence_relation_and_rhythm"],
                        "target_execution": "用改口前后的反冲把错答和余痛连在一起。",
                        "must_not_flatten_to": "不能拆成独立动作清单。",
                        "target_outline_evidence": section["outline_evidence"],
                    },
                    {
                        "technique_name": "错答压场",
                        "source_summary": "原文用更短的现场问句顶掉真正想问的话。",
                        "source_evidence": ["原文动作"],
                        "linked_style_dimensions": ["dialogue_misfire_or_avoidance"],
                        "target_execution": "她本来要问关系，最终只落一句钥匙怎么交。",
                        "must_not_flatten_to": "不能改成解释型对白。",
                        "target_outline_evidence": section["outline_evidence"],
                    },
                ],
                "source_style_granularity": {
                    "narrative_voice_and_attitude": {
                        "source_summary": "贴脸跟着当事人的即时注意走，不先替她下结论。",
                        "source_evidence": ["原文场面", "原文动作"],
                        "target_style_plan": "先让她看见挂件和人群站位，再让判断慢半拍漏出来。",
                    },
                    "sentence_relation_and_rhythm": {
                        "source_summary": "句子靠因果反冲和临时改口连起来，不走匀速摘要。",
                        "source_evidence": ["原文动作", "原文余痛"],
                        "target_style_plan": "用‘刚、却、才、还’把错答前后的反冲连起来。",
                    },
                    "paragraph_breath_and_cut_points": {
                        "source_summary": "在说话人、控制权和余痛落点变化处断段。",
                        "source_evidence": ["原文场面"],
                        "target_style_plan": "改口、换手、余痛三处各自成段，不把连续瞬间拆成报账。",
                    },
                    "dialogue_misfire_or_avoidance": {
                        "source_summary": "真正想问的话被更短的现场话顶掉。",
                        "source_evidence": ["原文动作"],
                        "target_style_plan": "先让她想追问，再只落一句钥匙什么时候交。",
                    },
                    "action_perception_emotion_weave": {
                        "source_summary": "动作、物件触感和情绪反冲连成同一瞬间。",
                        "source_evidence": ["原文场面", "原文余痛"],
                        "target_style_plan": "把松手、看挂件、改口和掌心余感织成一口气。",
                    },
                    "narrator_interjection_and_roughness": {
                        "source_summary": "场末收在身体余感和难堪上，不补作者总结。",
                        "source_evidence": ["原文余痛"],
                        "target_style_plan": "尾句只留掌心压痕和她记住这一秒，不替她解释大道理。",
                    },
                },
                "source_excerpt_reuse_reason": (
                    "同一原文场面跨两节迁移；本节读取的是失位后的余痛，不是上一节的期待。"
                    if section["section_id"] == "2"
                    else ""
                ),
                "emotion_process": {
                    "entry_state": "她入场时还在期待丈夫会维护自己。",
                    "involuntary_body_response": "听到丈夫改口后，她的手先松开钥匙。",
                    "memory_association_or_attention_drift": "她没想起完整往事，只盯住钥匙上两人共同挑的挂件。",
                    "contradictory_impulse": "她既想追问他为什么，又不愿当众求他选自己。",
                    "speech_misfire_or_avoidance": "她本来要问关系，开口却只问钥匙要不要现在交。",
                    "scene_afterpain": "钥匙换手后，她的手心还保留着金属压痕。",
                },
                "scene_weave_contract": [
                    {
                        "moment_group_id": "MG-1",
                        "source_trigger": "丈夫当众改口",
                        "source_evidence": ["原文场面"],
                        "action": "手先松开钥匙",
                        "perception": "她意识到自己的位置正在被换主",
                        "reaction": "视线只剩挂件，不敢立刻追问",
                        "same_moment_requirement": "动作、注意偏移和误认必须写在同一连续瞬间里",
                        "why_cannot_be_split": "一旦拆开就会退化成先动作后总结的施工稿",
                        "target_outline_evidence": section["outline_evidence"],
                    },
                    {
                        "moment_group_id": "MG-2",
                        "source_trigger": "钥匙真正换手",
                        "source_evidence": ["原文余痛"],
                        "action": "钥匙交出去",
                        "perception": "她明白公开失位已经成事实",
                        "reaction": "余痛落在掌心压痕和场末记住这一秒上",
                        "same_moment_requirement": "换手、认知反冲和余痛必须连写",
                        "why_cannot_be_split": "否则只剩交钥匙这一个功能节点",
                        "target_outline_evidence": section["outline_evidence"],
                    },
                ],
                "continuous_moment_groups": [
                    "听到改口、手松钥匙、看见挂件属于同一反应瞬间。",
                    "想追问、临时改口、交出钥匙属于同一选择瞬间。",
                ],
                "paragraph_break_reasons": [
                    "丈夫开口后说话人与施压位置变化。",
                    "钥匙真正换手后，现实进入权发生变化。",
                ],
                "sentence_relation_plan": [
                    "她因为听到丈夫改口，才下意识松开钥匙。",
                    "她原本想追问，却因为不愿乞求而改口。",
                    "钥匙虽然交了出去，手心的压痕却把余痛留在场末。",
                ],
                "function_word_strategy": "使用‘原本、却、才、还’贴合第一人称口气，不批量撒书面连词。",
                "telegraphic_risk": "最容易把松手、看挂件、改口、交钥匙切成四个动作短段。",
                "emotion_shorthand_to_avoid": ["手指发紧", "我没说话"],
                "target_emotion_landing_plan": [
                    "先让期待落在丈夫是否维护她的具体注意上。",
                    "再让改口暴露自尊和求证冲动的冲突。",
                    "最后用钥匙换手后的身体余感留下场末余痛。",
                ],
                "no_fixed_short_sentence_ratio": True,
                "manual_judgment": "首写要把期待、身体失控、自尊反冲、错答和余痛织进同一连续现场。",
            }
        data["reviewed_by_current_model"] = True
        data["gate_status"] = "passed"
        data["global_review"] = {
            "full_source_mechanisms_reviewed": True,
            "dual_track_function_and_scene_granularity_reviewed": True,
            "scene_causality_reviewed_before_draft": True,
            "source_bridge_flow_inventory_completed": True,
            "outline_bridge_flow_parity_reviewed_before_draft": True,
            "relationship_legibility_reviewed_before_draft": True,
            "professional_shell_translation_reviewed_before_draft": True,
            "source_emotion_flow_parity_reviewed_before_draft": True,
            "first_draft_generation_contract_reviewed": True,
            "paragraph_breath_reviewed_before_draft": True,
            "sentence_relation_and_function_word_strategy_reviewed_before_draft": True,
            "strong_emotion_required": True,
            "mechanism_transfer_boundary": "只迁移表演机制，不复制原文内容。",
            "global_storyboard_or_process_list": False,
            "manual_judgment": "每场只压一个不可逆变化，信息延迟到后场。",
        }
        data["story_fact_state_ledger"] = [
            {
                "fact_id": "FACT-01",
                "initial_state": "乙持有钥匙",
                "incompatible_states": ["交出钥匙前甲已用钥匙进入"],
                "transitions": [
                    {
                        "from_state": "乙持有钥匙",
                        "to_state": "甲持有钥匙",
                        "section_id": "1",
                        "trigger_evidence": ["动作一"],
                    },
                    {
                        "from_state": "甲持有钥匙",
                        "to_state": "乙失去进入权",
                        "section_id": "2",
                        "trigger_evidence": ["动作三"],
                    },
                ],
            }
        ]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_outline_sections_accepts_di_section_headings(self) -> None:
        text = (
            "## 第1节 起事\n"
            "- 钩子：抓人\n\n"
            "## 第2节 失位\n"
            "- 钩子：再压一刀\n"
        )

        self.assertEqual(["1", "2"], GATE.outline_sections(text))
        self.assertEqual({"1": "- 钩子：抓人", "2": "- 钩子：再压一刀"}, GATE.outline_section_blocks(text))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_complete_contract_passes(self) -> None:
        self.assertEqual([], GATE.validate_receipt(self.receipt, self.outline))

    def test_scene_logic_missing_arrival_cause_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["scene_logic_contract"]["target_entry_causes"] = []
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("target_entry_causes" in error for error in errors))

    def test_scene_logic_template_entry_cause_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        contract = data["sections"][0]["scene_logic_contract"]
        contract["target_entry_causes"] = ["- 读者新获知：丈夫已经偏向第三人"]
        contract["target_knowledge_state"] = ["读者新获知：丈夫已经偏向第三人"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("读者新获知" in error for error in errors))
        self.assertTrue(any("知情边界必须拆开写" in error for error in errors))

    def test_scene_logic_causal_asset_must_exist_in_source_profile(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["scene_logic_contract"]["causal_asset_id"] = "CPA-99"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("不在所选原文 profile" in error for error in errors))

    def test_unverified_external_rule_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        dependency = data["sections"][0]["scene_logic_contract"]["external_rule_dependency"]
        dependency.update({"domain": "medical", "verified": False, "authoritative_basis": "听说如此"})
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("必须完成人工核实" in error for error in errors))
        self.assertTrue(any("可靠依据" in error for error in errors))

    def test_fact_state_transition_must_be_continuous(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["story_fact_state_ledger"][0]["transitions"][1]["from_state"] = "乙仍持有钥匙"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("状态迁移不连续" in error for error in errors))

    def test_outline_change_invalidates_receipt(self) -> None:
        self.outline.write_text("## 1. 改写\n\n动作一\n动作二\n", encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("SHA 已变化" in error for error in errors))

    def test_missing_visible_change_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["interaction_exchange"]["visible_change"] = ""
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("visible_change" in error for error in errors))

    def test_strong_emotion_below_source_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["emotion_intensity"]["score"] = 6
        data["sections"][0]["source_emotion_parity"]["target_intensity_score"] = 6
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("烈度不得低于 7" in error for error in errors))
        self.assertTrue(any("情绪烈度低于原文" in error for error in errors))

    def test_domain_jargon_cannot_carry_relationship_conflict(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        shell = data["sections"][0]["professional_shell_translation"]
        shell["conflict_survives_without_jargon"] = False
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("删除职业术语后" in error for error in errors))

    def test_source_emotion_excerpt_must_be_real(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["source_emotion_parity"]["source_excerpt"] = "并不存在的原文"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("必须来自选中原文" in error for error in errors))

    def test_first_draft_excerpt_must_be_real(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        contract = data["sections"][0]["first_draft_generation_contract"]
        contract["source_performance_excerpt"] = "伪造的原文片段"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("source_performance_excerpt" in error for error in errors))

    def test_first_draft_emotion_process_cannot_be_empty(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        process = data["sections"][0]["first_draft_generation_contract"]["emotion_process"]
        process["contradictory_impulse"] = ""
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("contradictory_impulse" in error for error in errors))

    def test_first_draft_emotion_process_cannot_copy_scene_summary(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        section = data["sections"][0]
        process = section["first_draft_generation_contract"]["emotion_process"]
        original = section["original_scene_granularity"]
        process["speech_misfire_or_avoidance"] = original["dialogue_forces_action"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("不能直接照抄 original_scene_granularity 概括句" in error for error in errors))

    def test_first_draft_requires_continuous_moment_groups(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        contract = data["sections"][0]["first_draft_generation_contract"]
        contract["continuous_moment_groups"] = ["只写一组"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("至少两组连续瞬间" in error for error in errors))

    def test_first_draft_requires_sentence_relation_plan(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        contract = data["sections"][0]["first_draft_generation_contract"]
        contract["sentence_relation_plan"] = []
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("至少三条句间关系计划" in error for error in errors))

    def test_first_draft_cannot_restore_fixed_short_sentence_ratio(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        contract = data["sections"][0]["first_draft_generation_contract"]
        contract["no_fixed_short_sentence_ratio"] = False
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("不得设置固定短句" in error for error in errors))

    def test_strong_emotion_cannot_reuse_one_source_evidence_for_all_beats(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        beats = data["sections"][0]["source_emotion_parity"]["source_emotion_sequence"]
        for beat in beats:
            beat["evidence"] = "原文场面"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("同一句原文证据覆盖全部情绪拍" in error for error in errors))

    def test_first_draft_requires_multiple_real_source_details(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        contract = data["sections"][0]["first_draft_generation_contract"]
        contract["source_performance_evidence"] = ["原文场面", "原文场面"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("不得用同一句重复充数" in error for error in errors))

    def test_adjacent_excerpt_reuse_requires_specific_reason(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][1]["first_draft_generation_contract"][
            "source_excerpt_reuse_reason"
        ] = ""
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("source_excerpt_reuse_reason" in error for error in errors))

    def test_reversal_beat_must_match_source(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["source_emotion_parity"]["target_reversal_beat"] = 3
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("反刀拍必须同位" in error for error in errors))

    def test_each_target_emotion_beat_must_not_weaken(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        target = data["sections"][0]["source_emotion_parity"]["target_emotion_sequence"]
        target[1]["intensity"] = 1
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("第 2 拍目标烈度低于原文" in error for error in errors))

    def test_three_sections_cannot_reuse_same_scene_template(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.outline.write_text(
            "## 1. 起事\n\n动作一\n动作二\n\n"
            "## 2. 失位\n\n动作三\n动作四\n\n"
            "## 3. 反刀\n\n动作五\n动作六\n",
            encoding="utf-8",
        )
        data["outline"] = {
            "path": str(self.outline.resolve()),
            "sha256": GATE.sha256(self.outline),
        }
        third = deepcopy(data["sections"][1])
        third["section_id"] = "3"
        third["outline_evidence"] = ["动作五", "动作六"]
        third["source_emotion_parity"]["target_emotion_sequence"] = self.emotion_beats(
            "动作五"
        )
        data["sections"].append(third)
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("连续复用泛化模板" in error for error in errors))
        self.assertTrue(any("连续复用同一句" in error for error in errors))
        self.assertTrue(any("情绪流程连续复用" in error for error in errors))
        self.assertTrue(any("首写生成契约字段" in error for error in errors))

    def test_missing_source_bridge_parity_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["outline_bridge_flow_parity"] = []
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("逐桥证明" in error for error in errors))

    def test_weakened_source_bridge_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["outline_bridge_flow_parity"][0]["parity_status"] = "weakened"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("matched/adapted" in error for error in errors))

    def test_missing_primary_catalog_bridge_blocks(self) -> None:
        self.catalog.write_text(
            "## BID-01 公开掉位\n\n## BID-02 私域换主\n",
            encoding="utf-8",
        )
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        source = data["selected_source_originals"][0]
        source["bridge_catalog"]["sha256"] = GATE.sha256(self.catalog)
        source["available_bridge_ids"] = ["BID-01", "BID-02"]
        source["required_bridge_ids"] = ["BID-01", "BID-02"]
        source["selected_bridge_ids"] = ["BID-01", "BID-02"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("主体来源桥段库存缺失" in error for error in errors))

    def test_missing_selected_auxiliary_bridge_blocks(self) -> None:
        auxiliary_root = self.root / "拆文库" / "辅助书"
        auxiliary = auxiliary_root / "原文" / "辅助书.txt"
        auxiliary.parent.mkdir(parents=True)
        auxiliary.write_text("辅助原文", encoding="utf-8")
        auxiliary_catalog = auxiliary_root / "写作资产" / "桥段施工卡.md"
        auxiliary_catalog.parent.mkdir(parents=True)
        auxiliary_catalog.write_text("## BID-03 稀缺资源撤回\n", encoding="utf-8")
        (auxiliary_root / "book.profile.json").write_text(
            json.dumps(
                {"causal_precondition_assets": [{"causal_asset_id": "CPA-03"}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        old = json.loads(self.receipt.read_text(encoding="utf-8"))
        data = GATE.create_receipt("测试", self.outline, [self.source, auxiliary])
        data["global_review"] = old["global_review"]
        data["source_bridge_flow_inventory"] = old["source_bridge_flow_inventory"]
        data["outline_bridge_flow_parity"] = old["outline_bridge_flow_parity"]
        data["sections"] = old["sections"]
        data["reviewed_by_current_model"] = True
        data["gate_status"] = "passed"
        data["selected_source_originals"][1]["selected_bridge_ids"] = ["BID-03"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("辅助来源桥段库存缺失" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
