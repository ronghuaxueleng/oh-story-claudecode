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
            "## 1. 起事\n\n动作一\n动作二\n\n## 2. 失位\n\n动作三\n动作四\n",
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
                "scene_entry_state": (
                    "乙持有钥匙，甲尚未取得入口控制权"
                    if section["section_id"] == "1"
                    else "甲持有钥匙，乙仍准备争回进入权"
                ),
                "scene_exit_state": (
                    "甲持有钥匙，乙仍准备争回进入权"
                    if section["section_id"] == "1"
                    else "乙失去进入权并转向外部处理"
                ),
                "beat_dependency_chain": [],
                "knowledge_state_chain": [],
                "causal_risk_reviews": [
                    {
                        "risk_type": risk_type,
                        "applicable": False,
                        "event": "",
                        "setup": "",
                        "causal_explanation": "",
                        "outline_evidence": [],
                        "not_applicable_reason": "本测试场没有该类巧合或强制信息延迟。",
                        "manual_judgment": "",
                    }
                    for risk_type in GATE.CAUSAL_RISK_TYPES
                ],
                "manual_judgment": "人物同场、知情差和物件换手均有前置原因。",
            }
            logic = section["scene_logic_contract"]
            first_evidence, second_evidence = section["outline_evidence"]
            intermediate_one = f"{section['section_id']}节第一拍后现场进入争夺"
            intermediate_two = f"{section['section_id']}节第二拍后丈夫公开表态"
            logic["beat_dependency_chain"] = [
                {
                    "beat_id": "B1",
                    "actor": "乙",
                    "action": "乙因门锁报警赶到入口",
                    "from_state": logic["scene_entry_state"],
                    "trigger": "门锁报警出现",
                    "knowledge_before": "乙只知道入口异常",
                    "spatial_or_object_access": "乙持有原钥匙并能到达门口",
                    "to_state": intermediate_one,
                    "next_beat_cause": "甲必须说明自己为何在门内",
                    "outline_evidence": [first_evidence],
                },
                {
                    "beat_id": "B2",
                    "actor": "甲",
                    "action": "甲说明丈夫已经允许自己进入",
                    "from_state": intermediate_one,
                    "trigger": "乙当面阻拦",
                    "knowledge_before": "甲知道丈夫已表态，乙不知道",
                    "spatial_or_object_access": "甲站在门内并接触钥匙",
                    "to_state": intermediate_two,
                    "next_beat_cause": "丈夫必须公开确认钥匙归属",
                    "outline_evidence": [second_evidence],
                },
                {
                    "beat_id": "B3",
                    "actor": "丈夫",
                    "action": "丈夫确认钥匙交给甲",
                    "from_state": intermediate_two,
                    "trigger": "双方同时要求确认归属",
                    "knowledge_before": "丈夫知道自己先前的授权",
                    "spatial_or_object_access": "丈夫在场并拥有授权解释权",
                    "to_state": logic["scene_exit_state"],
                    "next_beat_cause": "钥匙换手形成场末后果",
                    "outline_evidence": [second_evidence],
                },
            ]
            logic["knowledge_state_chain"] = [
                {
                    "fact_id": f"FACT-KNOW-{section['section_id']}",
                    "character": "乙",
                    "initial_state": "乙不知道丈夫已允许甲进入",
                    "incompatible_states": ["乙在丈夫表态前已知道完整授权"],
                    "transitions": [
                        {
                            "from_state": "乙不知道丈夫已允许甲进入",
                            "to_state": "乙听见甲声称获得允许但尚未确认",
                            "beat_id": "B2",
                            "trigger": "甲当面说明授权",
                            "outline_evidence": [second_evidence],
                        }
                    ],
                    "final_state": "乙听见甲声称获得允许但尚未确认",
                }
            ]
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
            "intra_section_beat_causality_reviewed": True,
            "section_handoff_reviewed": True,
            "auxiliary_subflow_full_flow_reviewed": True,
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
        first_logic = data["sections"][0]["scene_logic_contract"]
        second_logic = data["sections"][1]["scene_logic_contract"]
        data["section_handoff_chain"] = [
            {
                "from_section_id": "1",
                "to_section_id": "2",
                "elapsed_time": "同日十分钟后",
                "from_exit_state": first_logic["scene_exit_state"],
                "to_entry_state": second_logic["scene_entry_state"],
                "handoff_trigger": "钥匙换手后，乙立即转到下一处入口继续处理",
                "character_state_continuity": ["乙保持争回进入权的行动目标"],
                "knowledge_continuity": ["乙仍只知道甲声称获得授权，尚未核实"],
                "object_continuity": ["钥匙继续由甲持有，没有离场后自动换手"],
                "location_continuity": "人物从门口移动到相邻入口，路程和到场原因明确",
                "unresolved_threads": ["丈夫授权是否真实仍待下一节确认"],
                "outline_evidence": ["动作二", "动作三"],
                "manual_judgment": "前节钥匙换手直接触发后节核验，不靠新巧合重启剧情。",
            }
        ]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

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

    def test_scene_logic_rejects_reader_information_as_arrival_cause(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["sections"][0]["scene_logic_contract"]["target_entry_causes"] = [
            "读者新获知丈夫偏心，人物均由上一节未完成动作或主动追问进入本场。"
        ]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("验收占位话代替真实因果" in error for error in errors))
        self.assertTrue(any("首节" in error and "上一节" in error for error in errors))

    def test_legacy_receipt_version_requires_reinit(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["version"] = "1.4"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("版本必须为 1.5" in error for error in errors))

    def test_beat_dependency_chain_must_connect_states(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        chain = data["sections"][0]["scene_logic_contract"]["beat_dependency_chain"]
        chain[1]["from_state"] = "凭空出现的另一状态"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("状态未首尾相接" in error for error in errors))

    def test_knowledge_state_chain_must_connect_and_close(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        fact = data["sections"][0]["scene_logic_contract"]["knowledge_state_chain"][0]
        fact["final_state"] = "乙从开场就知道全部授权"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("final_state 与最后一次知情迁移不一致" in error for error in errors))

    def test_applicable_causal_risk_requires_setup_and_evidence(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        review = data["sections"][0]["scene_logic_contract"]["causal_risk_reviews"][0]
        review.update(
            {
                "applicable": True,
                "event": "夫妻意外出现在同一现场",
                "setup": "",
                "causal_explanation": "",
                "outline_evidence": [],
                "not_applicable_reason": "",
                "manual_judgment": "",
            }
        )
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("character_convergence.setup" in error for error in errors))
        self.assertTrue(any("character_convergence.outline_evidence" in error for error in errors))

    def test_missing_section_handoff_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["section_handoff_chain"] = []
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("缺少相邻小节交接" in error for error in errors))

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

        source_receipt = self.root / "拆文读取回执.json"
        source_receipt.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "name": "测试书",
                            "role": "main",
                            "root": str(self.book_root),
                            "selected_subflow_ids": ["SF-01"],
                            "selected_subflow_contracts": [],
                        },
                        {
                            "name": "辅助书",
                            "role": "auxiliary",
                            "root": str(auxiliary_root),
                            "selected_subflow_ids": ["SF-03"],
                            "selected_subflow_contracts": [
                                {
                                    "subflow_id": "SF-03",
                                    "entry_state": "辅助事件已有明确前态。",
                                    "required_sequence": ["先给资源", "再撤回资源"],
                                    "causal_preconditions": {
                                        "knowledge_boundaries": ["主角起初不知道资源会撤回", "责任方知道自己能改动资源"],
                                        "object_lifecycle": ["凭证先交给主角", "凭证随后被系统转走"],
                                        "exit_cause": "资源撤回造成现实损害。",
                                    },
                                    "end_state": "主角失去稀缺资源。",
                                }
                            ],
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        old = json.loads(self.receipt.read_text(encoding="utf-8"))
        data = GATE.create_receipt(
            "测试",
            self.outline,
            [self.source, auxiliary],
            source_receipt_path=source_receipt,
        )
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

    def test_fusion_init_requires_source_receipt(self) -> None:
        auxiliary_root = self.root / "拆文库" / "辅助书"
        auxiliary = auxiliary_root / "原文" / "辅助书.txt"
        auxiliary.parent.mkdir(parents=True)
        auxiliary.write_text("辅助原文", encoding="utf-8")
        (auxiliary_root / "写作资产").mkdir(parents=True)
        (auxiliary_root / "写作资产" / "桥段施工卡.md").write_text(
            "## BID-03 辅助桥段\n", encoding="utf-8"
        )
        (auxiliary_root / "book.profile.json").write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-03"}]}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "必须传 --source-receipt"):
            GATE.create_receipt("测试", self.outline, [self.source, auxiliary])

    def test_auxiliary_subflow_sequence_cannot_drop_steps(self) -> None:
        auxiliary_root = self.root / "拆文库" / "辅助书"
        auxiliary = auxiliary_root / "原文" / "辅助书.txt"
        auxiliary.parent.mkdir(parents=True)
        auxiliary.write_text("辅助原文", encoding="utf-8")
        (auxiliary_root / "写作资产").mkdir(parents=True)
        (auxiliary_root / "写作资产" / "桥段施工卡.md").write_text(
            "## BID-03 辅助桥段\n", encoding="utf-8"
        )
        (auxiliary_root / "book.profile.json").write_text(
            json.dumps({"causal_precondition_assets": [{"causal_asset_id": "CPA-03"}]}),
            encoding="utf-8",
        )
        source_receipt = self.root / "拆文读取回执_辅助.json"
        source_receipt.write_text(
            json.dumps(
                {
                    "sources": [
                        {"root": str(self.book_root), "role": "main"},
                        {
                            "root": str(auxiliary_root),
                            "role": "auxiliary",
                            "selected_subflow_ids": ["SF-03"],
                            "selected_subflow_contracts": [
                                {
                                    "subflow_id": "SF-03",
                                    "entry_state": "资源已经交付。",
                                    "required_sequence": ["交付资源", "系统撤回", "现实受损"],
                                    "causal_preconditions": {
                                        "knowledge_boundaries": ["主角不知道会撤回", "责任方知道可撤回"],
                                        "object_lifecycle": ["凭证先交付", "凭证后失效"],
                                        "exit_cause": "损害迫使主角重新判断关系。",
                                    },
                                    "end_state": "资源已失效且损害发生。",
                                }
                            ],
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        data = GATE.create_receipt(
            "测试",
            self.outline,
            [self.source, auxiliary],
            source_receipt_path=source_receipt,
        )
        data["auxiliary_subflow_flow_parity"][0]["sequence_mappings"] = data[
            "auxiliary_subflow_flow_parity"
        ][0]["sequence_mappings"][:-1]
        temp_receipt = self.root / "辅助细纲回执.json"
        temp_receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(temp_receipt, self.outline)
        self.assertTrue(any("逐项覆盖完整 required_sequence" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
