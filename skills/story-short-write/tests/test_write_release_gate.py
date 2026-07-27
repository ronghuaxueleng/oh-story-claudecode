from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_write_release_gate.py"
)
SPEC = importlib.util.spec_from_file_location("write_release_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class WriteReleaseGateTest(unittest.TestCase):
    @staticmethod
    def emotion_beats(evidence: str | list[str]) -> list[dict]:
        roles = ["情绪进入点", "受辱或刺痛", "短暂希望或反抗", "反刀", "场末余痛"]
        return [
            {
                "role": role,
                "trigger": f"{role}的具体触发",
                "relationship_position_change": f"{role}改变关系位置",
                "reader_effect": f"读者在{role}感到关系恶化",
                "intensity": 8,
                "evidence": evidence[index % len(evidence)] if isinstance(evidence, list) else evidence,
            }
            for index, role in enumerate(roles)
        ]

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.files = {}
        self.original_validate_ledger = GATE._RULE_LEDGER_MODULE.validate_ledger
        self.original_validate_prewrite_ledger = (
            GATE._RULE_LEDGER_MODULE.validate_prewrite_ledger
        )
        self.original_validate_writing_receipt = GATE._WRITING_RULE_MODULE.validate_receipt
        self.original_validate_source_receipt = GATE._SOURCE_READ_MODULE.validate_receipt
        self.original_validate_capacity_contract = GATE._DRAFT_CAPACITY_MODULE.validate
        self.original_validate_opening_receipt = GATE._OPENING_CONTRACT_MODULE.validate_receipt
        self.original_validate_section_bundle = GATE._SECTION_SOURCE_BUNDLE_MODULE.validate_bundle
        GATE._RULE_LEDGER_MODULE.validate_ledger = lambda _path: ([], {})
        GATE._RULE_LEDGER_MODULE.validate_prewrite_ledger = lambda _path: []
        GATE._WRITING_RULE_MODULE.validate_receipt = lambda _path: ([], {})
        GATE._SOURCE_READ_MODULE.validate_receipt = lambda _path: ([], {})
        GATE._DRAFT_CAPACITY_MODULE.validate = lambda _path: []
        GATE._OPENING_CONTRACT_MODULE.validate_receipt = lambda *_args: ([], {})
        GATE._SECTION_SOURCE_BUNDLE_MODULE.validate_bundle = lambda _path: []
        self.setting = self.root / "设定.md"
        self.outline = self.root / "大纲.md"
        self.setting.write_text("设定", encoding="utf-8")
        self.outline.write_text("## 1. 起事\n\n动作一\n动作二\n", encoding="utf-8")
        source_root = self.root / "拆文库" / "测试书"
        self.source_original = source_root / "原文" / "原文.txt"
        self.source_original.parent.mkdir(parents=True)
        self.source_original.write_text("原文场面。原文动作。原文余痛。", encoding="utf-8")
        bridge_catalog = source_root / "写作资产" / "桥段施工卡.md"
        bridge_catalog.parent.mkdir(parents=True)
        bridge_catalog.write_text("## BID-01 公开掉位\n", encoding="utf-8")
        (source_root / "book.profile.json").write_text(
            json.dumps(
                {"causal_precondition_assets": [{"causal_asset_id": "CPA-01"}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        for name in (
            "writing",
            "source",
            "ledger",
            "opening",
            "outline_contract",
            "profile",
            "sequence",
            "setting_sequence",
            "section_bundle",
        ):
            path = self.root / f"{name}.json"
            payload = {"gate_status": "passed"}
            if name == "sequence":
                payload["scope"] = "full"
                payload["artifacts"] = {
                    "setting": self.binding(self.setting),
                    "outline": self.binding(self.outline),
                }
            elif name == "setting_sequence":
                payload = {
                    "gate_status": "passed",
                    "scope": "setting",
                    "status": "completed",
                    "execution_mode": "current_model_manual",
                    "artifacts": {"setting": self.binding(self.setting)},
                    "canonical_sequence": [
                        {
                            "id": "S1",
                            "label": "设定起点",
                            "setting_evidence": [
                                {
                                    "quote": "设定",
                                    "offset": 0,
                                    "judgment": "设定先给出基础关系。",
                                }
                            ],
                        },
                        {
                            "id": "S2",
                            "label": "设定结果",
                            "setting_evidence": [
                                {
                                    "quote": "设定",
                                    "offset": 0,
                                    "judgment": "测试夹具用同一原句承载第二个抽象节点。",
                                }
                            ],
                        },
                    ],
                    "conflict_review": {
                        "setting_internal_status": "passed",
                        "findings": [],
                    },
                    "manual_judgment": "设定内部顺序已由当前模型复核。",
                }
            elif name == "outline_contract":
                payload = self.outline_contract_payload()
            elif name == "opening":
                payload = {
                    "gate_status": "passed",
                    "primary_source": {"path": str(self.source_original.resolve())},
                    "target_text": {"path": str(self.outline.resolve())},
                }
            elif name == "section_bundle":
                payload = {
                    "gate": "section_source_bundle",
                    "gate_status": "passed",
                    "outline_contract": {"path": str(self.files["outline_contract"].resolve()), "sha256": "x"},
                    "source_receipt": {"path": str(self.files["source"].resolve()), "sha256": "y"},
                    "section_packet_ids": ["section-1"],
                    "packets": [
                        {
                            "packet_id": "section-1",
                            "section_id": "1",
                            "packet_sha256": "z",
                            "payload": {
                                "source_slice_bindings": [
                                    {
                                        "source_path": str(self.source_original.resolve()),
                                        "source_sha256": hashlib.sha256(self.source_original.read_bytes()).hexdigest(),
                                        "source_range": "L1-L1",
                                        "source_evidence": ["原文"],
                                        "style_fields_consumed": ["a", "b", "c", "d", "e", "f"],
                                    }
                                ]
                            },
                        }
                    ],
                }
            path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            self.files[name] = path

    def outline_contract_payload(self) -> dict:
        outline_gate = GATE._OUTLINE_PERFORMANCE_MODULE
        payload = outline_gate.create_receipt(
            "测试",
            self.outline,
            [self.source_original],
        )
        source_path = str(self.source_original.resolve())
        source_sha = outline_gate.sha256(self.source_original)
        payload["global_review"] = {
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
            "manual_judgment": "正文前已逐桥验收。",
        }
        payload["source_bridge_flow_inventory"] = [
            {
                "source_path": source_path,
                "source_sha256": source_sha,
                "bridge_id": "BID-01",
                "bridge_name": "公开掉位",
                "source_required_sequence": ["先公开偏护", "再让主角失位"],
                "source_must_keep_actions": ["抢走位置", "旁观者改站队"],
                "source_scene_granularity": "动作和站位连续换主。",
                "source_end_state_change": "主角失去默认成员身份。",
                "cannot_merge_or_drop_reason": "后续撤离必须由此承重。",
            }
        ]
        payload["outline_bridge_flow_parity"] = [
            {
                "source_bridge_id": "BID-01",
                "source_bridge_name": "公开掉位",
                "source_path": source_path,
                "source_sha256": source_sha,
                "source_required_sequence": ["先公开偏护", "再让主角失位"],
                "source_must_keep_actions": ["抢走位置", "旁观者改站队"],
                "source_scene_granularity": "动作和站位连续换主。",
                "source_emotion_sequence": self.emotion_beats(["原文场面", "原文动作", "原文余痛"]),
                "target_emotion_sequence": self.emotion_beats("动作一"),
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 4,
                "target_peak_beat": 4,
                "reader_experience_parity": True,
                "emotion_parity_judgment": "反刀、峰值和读者体感均与原文同级。",
                "target_outline_sections": ["1"],
                "target_outline_evidence": ["动作一", "动作二"],
                "parity_status": "matched",
                "adaptation_reason": "保留原文流程，仅更换题材载体。",
                "missing_or_weakened_risk": "不能压成一句关系结论。",
                "manual_judgment": "细纲已经写出施压、接招和位置变化。",
            }
        ]
        section = payload["sections"][0]
        section.update(
            {
                "verdict": "passed",
                "irreversible_action": "主角失去位置",
                "controlling_object": "钥匙",
                "source_function_mechanism": {
                    "asset_path": "写作资产/桥段施工卡.md",
                    "function_type": "公开掉位",
                    "asset_rule": "先换位置，再漏关系结论。",
                    "why_selected_for_this_section": "承担撤离前的第一次现实伤害。",
                },
                "original_scene_granularity": {
                    "source_path": source_path,
                    "source_sha256": source_sha,
                    "source_scene": "公开偏护",
                    "action_sequence": "甲先抢，乙后退，旁观者改口。",
                    "body_object_space_control": "入口控制权换主。",
                    "dialogue_forces_action": "公开确认迫使乙交出钥匙。",
                    "bystander_or_order_shift": "旁观者不再等待乙决定。",
                    "scene_end_residue": "乙被公开排除。",
                },
                "scene_logic_contract": {
                    "source_path": source_path,
                    "source_sha256": source_sha,
                    "causal_asset_id": "CPA-01",
                    "source_causal_preconditions": ["人物因公开活动同时到场。"],
                    "source_evidence": ["原文场面", "原文动作"],
                    "target_entry_causes": ["乙收到入口报警后到场。"],
                    "target_knowledge_state": ["乙只知道入口异常，不知道丈夫已允许甲进入。"],
                    "key_object_lifecycle": ["钥匙原由乙持有，丈夫表态后才交给甲。"],
                    "external_rule_dependency": {
                        "domain": "none",
                        "verified": True,
                        "authoritative_basis": "冲突依赖人物主动表态和钥匙持有，不依赖外部制度。",
                    },
                    "obvious_alternative_blocker": ["乙负责处理报警，不能直接离场。"],
                    "exit_cause": "钥匙换手后乙失去进入权，只能离场。",
                    "target_outline_evidence": ["动作一", "动作二"],
                    "scene_entry_state": "乙因入口报警赶到，仍持有钥匙且不知道丈夫已让甲进入。",
                    "scene_exit_state": "甲持有钥匙，乙被公开排除并离开入口。",
                    "beat_dependency_chain": [
                        {
                            "beat_id": "1-B1",
                            "actor": "乙",
                            "action": "乙赶到入口并出示钥匙处理报警。",
                            "from_state": "乙因入口报警赶到，仍持有钥匙且不知道丈夫已让甲进入。",
                            "trigger": "入口报警持续响起。",
                            "knowledge_before": "乙只知道入口异常。",
                            "spatial_or_object_access": "乙是钥匙持有人，因此能进入并处理报警。",
                            "to_state": "乙到达入口并准备开门，甲和丈夫同时在场。",
                            "next_beat_cause": "甲当面要求取得钥匙。",
                            "outline_evidence": ["动作一"],
                        },
                        {
                            "beat_id": "1-B2",
                            "actor": "甲",
                            "action": "甲要求丈夫确认由谁持有钥匙。",
                            "from_state": "乙到达入口并准备开门，甲和丈夫同时在场。",
                            "trigger": "乙拿出钥匙准备处理报警。",
                            "knowledge_before": "甲知道丈夫已经口头允许她进入。",
                            "spatial_or_object_access": "甲只能当面索取，不能凭空取得钥匙。",
                            "to_state": "丈夫必须在乙和甲之间公开表态。",
                            "next_beat_cause": "丈夫选择让乙交出钥匙。",
                            "outline_evidence": ["动作二"],
                        },
                        {
                            "beat_id": "1-B3",
                            "actor": "丈夫",
                            "action": "丈夫要求乙把钥匙交给甲。",
                            "from_state": "丈夫必须在乙和甲之间公开表态。",
                            "trigger": "甲把钥匙归属变成当众选择。",
                            "knowledge_before": "丈夫知道钥匙原由乙持有，也知道交出意味着排除乙。",
                            "spatial_or_object_access": "丈夫只能施压要求换手，钥匙仍需乙亲手交出。",
                            "to_state": "甲持有钥匙，乙被公开排除并离开入口。",
                            "next_beat_cause": "乙失去进入权后离场，关系伤害进入下一场余波。",
                            "outline_evidence": ["动作一", "动作二"],
                        },
                    ],
                    "knowledge_state_chain": [
                        {
                            "fact_id": "KNOW-01",
                            "character": "乙",
                            "initial_state": "不知道丈夫已允许甲进入",
                            "incompatible_states": ["入场前已知道丈夫的选择"],
                            "transitions": [
                                {
                                    "from_state": "不知道丈夫已允许甲进入",
                                    "to_state": "亲耳听见丈夫要求把钥匙交给甲",
                                    "beat_id": "1-B3",
                                    "trigger": "丈夫当众作出选择。",
                                    "outline_evidence": ["动作二"],
                                }
                            ],
                            "final_state": "亲耳听见丈夫要求把钥匙交给甲",
                        }
                    ],
                    "causal_risk_reviews": [
                        {
                            "risk_type": "character_convergence",
                            "applicable": True,
                            "event": "乙、甲和丈夫在入口同时出现。",
                            "setup": "入口报警召来乙，甲和丈夫原本就在入口。",
                            "causal_explanation": "三人的到场分别由既有职责和在场状态触发。",
                            "outline_evidence": ["动作一"],
                            "not_applicable_reason": "",
                            "manual_judgment": "汇合由报警和既有站位促成，不依赖巧合。",
                        },
                        {
                            "risk_type": "critical_information_delay",
                            "applicable": True,
                            "event": "乙入场后才知道丈夫允许甲进入。",
                            "setup": "乙此前只收到入口报警。",
                            "causal_explanation": "丈夫的公开表态首次把选择暴露给乙。",
                            "outline_evidence": ["动作二"],
                            "not_applicable_reason": "",
                            "manual_judgment": "信息延迟来自角色此前未被告知。",
                        },
                        {
                            "risk_type": "critical_interruption",
                            "applicable": False,
                            "event": "",
                            "setup": "",
                            "causal_explanation": "",
                            "outline_evidence": [],
                            "not_applicable_reason": "本节没有用突发身体反应或电话打断关键回答。",
                            "manual_judgment": "",
                        },
                        {
                            "risk_type": "spatial_or_object_access",
                            "applicable": True,
                            "event": "钥匙从乙转交给甲。",
                            "setup": "乙先持有钥匙，甲只能通过丈夫公开施压索取。",
                            "causal_explanation": "丈夫表态后乙亲手交出，物件没有瞬移。",
                            "outline_evidence": ["动作一", "动作二"],
                            "not_applicable_reason": "",
                            "manual_judgment": "持有、索取和换手顺序完整。",
                        },
                    ],
                    "manual_judgment": "同场原因、知情差和物件换手均有前置条件。",
                },
                "source_mechanism": {
                    "source_path": source_path,
                    "source_sha256": source_sha,
                    "source_scene": "公开偏护",
                    "transferable_mechanism": "站位先变，关系结论后漏出。",
                    "adaptation_boundary": "不复制人物、职业、原句或桥壳。",
                },
                "information_delay": {
                    "entry_known": "只知现场异常。",
                    "leaked_in_scene": "只漏一次偏护。",
                    "deferred_to_later": "完整责任后置。",
                },
                "character_missteps": ["甲先抢", "乙错答"],
                "interaction_exchange": {
                    "pressure": "甲抢控制权。",
                    "forced_response": "乙被迫让位。",
                    "visible_change": "钥匙和站位换主。",
                },
                "conflict_carrier": {
                    "contested_power": "现场决定权。",
                    "carrier": "钥匙。",
                    "consequence": "乙失去进入权。",
                },
                "relationship_legibility": {
                    "plain_relationship_roles": "妻子、丈夫和旧爱争夺谁被优先保护。",
                    "plain_relationship_injury": "丈夫当众保护旧爱，让妻子失去原位。",
                    "understandable_without_domain_knowledge": True,
                },
                "emotion_intensity": {
                    "score": 8,
                    "concrete_humiliation_or_pain": "妻子被丈夫当众排除。",
                    "emotional_turn": "刚以为丈夫会维护她，下一拍就被放弃。",
                    "escalation_vs_previous": "从怀疑升级为公开失位。",
                },
                "professional_shell_translation": {
                    "plain_language_conflict": "丈夫为了旧爱要求妻子让位。",
                    "domain_detail_function": "钥匙只把关系伤害落实成进入权后果。",
                    "conflict_survives_without_jargon": True,
                    "relationship_first": True,
                },
                "source_emotion_parity": {
                    "source_excerpt": "原文场面",
                    "source_emotion_sequence": self.emotion_beats(["原文场面", "原文动作", "原文余痛"]),
                    "target_emotion_sequence": self.emotion_beats("动作一"),
                    "source_intensity_score": 8,
                    "target_intensity_score": 8,
                    "source_reversal_beat": 4,
                    "target_reversal_beat": 4,
                    "source_peak_beat": 4,
                    "target_peak_beat": 4,
                    "ending_afterpain_equivalent": True,
                    "reader_experience_equivalent": True,
                    "manual_judgment": "逐拍对齐且没有把公开抛弃降成职业分歧。",
                    "parity_status": "adapted_equal_intensity",
                    "adaptation_boundary": "只迁移情绪结构，不复制人物与原句。",
                },
                "first_draft_generation_contract": {
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
                    "source_excerpt_reuse_reason": "",
                    "emotion_process": {
                        "entry_state": "她还在等丈夫给一个合理解释。",
                        "involuntary_body_response": "他开口偏护时，她的手先松开了钥匙。",
                        "memory_association_or_attention_drift": "她的注意落到两人共同挑的钥匙挂件上。",
                        "contradictory_impulse": "她想追问，又不肯当众乞求。",
                        "speech_misfire_or_avoidance": "她把质问改成了一句钥匙何时交。",
                        "scene_afterpain": "钥匙换手后，她手心的压痕还没散。",
                    },
                    "continuous_moment_groups": [
                        "听见偏护、松手、看见挂件是同一瞬间。",
                        "想追问、改口、交钥匙是同一选择瞬间。",
                    ],
                    "paragraph_break_reasons": [
                        "说话人与施压位置变化。",
                        "钥匙换手导致进入权变化。",
                    ],
                    "sentence_relation_plan": [
                        "因为听见偏护，她才松手。",
                        "她原本想追问，却临时改口。",
                        "钥匙虽交出，压痕却留在场末。",
                    ],
                    "function_word_strategy": "用原本、却、才和还组织自然口气。",
                    "telegraphic_risk": "避免把松手、看挂件、改口和交钥匙切成四个短段。",
                    "emotion_shorthand_to_avoid": ["手指发紧", "我没说话"],
                    "target_emotion_landing_plan": [
                        "期待先落在丈夫是否解释的具体注意上。",
                        "改口承载追问冲动和自尊之间的冲突。",
                        "钥匙换手后的压痕负责留下场末余痛。",
                    ],
                    "no_fixed_short_sentence_ratio": True,
                    "manual_judgment": "第一稿就保留期待、身体失控、自尊反冲、错答和余痛。",
                },
                "forbidden_items": ["不提前解释", "不连续报账"],
                "outline_evidence": ["动作一", "动作二"],
                "manual_judgment": "本场是连续互动，不是清单。",
            }
        )
        payload["reviewed_by_current_model"] = True
        payload["gate_status"] = "passed"
        payload["story_fact_state_ledger"] = [
            {
                "fact_id": "FACT-01",
                "initial_state": "乙持有钥匙",
                "incompatible_states": ["交出前甲已持有钥匙"],
                "transitions": [
                    {
                        "from_state": "乙持有钥匙",
                        "to_state": "甲持有钥匙",
                        "section_id": "1",
                        "trigger_evidence": ["动作一"],
                    }
                ],
            }
        ]
        return payload

    @staticmethod
    def binding(path: Path) -> dict[str, str]:
        import hashlib

        return {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def tearDown(self) -> None:
        GATE._RULE_LEDGER_MODULE.validate_ledger = self.original_validate_ledger
        GATE._RULE_LEDGER_MODULE.validate_prewrite_ledger = (
            self.original_validate_prewrite_ledger
        )
        GATE._WRITING_RULE_MODULE.validate_receipt = self.original_validate_writing_receipt
        GATE._SOURCE_READ_MODULE.validate_receipt = self.original_validate_source_receipt
        GATE._DRAFT_CAPACITY_MODULE.validate = self.original_validate_capacity_contract
        GATE._OPENING_CONTRACT_MODULE.validate_receipt = self.original_validate_opening_receipt
        GATE._SECTION_SOURCE_BUNDLE_MODULE.validate_bundle = self.original_validate_section_bundle
        self.temp_dir.cleanup()

    def test_blocked_ledger_blocks_draft(self) -> None:
        self.files["ledger"].write_text(
            json.dumps({"gate_status": "blocked"}),
            encoding="utf-8",
        )
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertTrue(any("规则执行门禁未通过" in item for item in errors))

    def test_passed_ledger_is_revalidated_instead_of_trusting_status(self) -> None:
        GATE._RULE_LEDGER_MODULE.validate_ledger = lambda _path: (
            ["skill 规则源已变化，必须重建台账"],
            {},
        )
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertTrue(any("重新校验失败" in item for item in errors))
        self.assertTrue(any("skill 规则源已变化" in item for item in errors))

    def test_prewrite_ledger_validation_blocks_draft(self) -> None:
        GATE._RULE_LEDGER_MODULE.validate_prewrite_ledger = lambda _path: [
            "规则 SKILL-test 缺少 canonical_rule_text"
        ]
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertTrue(any("未完成写前分类与执行计划" in item for item in errors))
        self.assertTrue(any("缺少 canonical_rule_text" in item for item in errors))

    def test_passed_source_receipt_is_revalidated(self) -> None:
        GATE._SOURCE_READ_MODULE.validate_receipt = lambda _path: (
            ["profile 覆盖清单已过期"],
            {},
        )
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertTrue(any("拆文读取回执实时复验失败" in item for item in errors))
        self.assertTrue(any("覆盖清单已过期" in item for item in errors))

    def test_draft_requires_opening_contract_and_profile(self) -> None:
        errors = GATE.validate_release(
            "draft",
            self.files["writing"],
            self.files["source"],
            self.files["ledger"],
        )
        self.assertTrue(any("开头承重契约" in item for item in errors))
        self.assertTrue(any("细纲表演验收" in item for item in errors))
        self.assertTrue(any("profile" in item for item in errors))
        self.assertTrue(any("逐节原文颗粒包" in item for item in errors))

    def test_all_preconditions_pass(self) -> None:
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertEqual([], errors)

    def test_draft_requires_outline_performance_contract(self) -> None:
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertTrue(any("细纲表演验收" in item for item in errors))

    def test_draft_revalidates_outline_contract_instead_of_trusting_status(self) -> None:
        payload = json.loads(self.files["outline_contract"].read_text(encoding="utf-8"))
        payload["outline_bridge_flow_parity"][0]["parity_status"] = "weakened"
        payload["gate_status"] = "passed"
        self.files["outline_contract"].write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertTrue(any("matched/adapted" in item for item in errors))

    def test_draft_blocks_invalid_first_draft_generation_contract(self) -> None:
        payload = json.loads(self.files["outline_contract"].read_text(encoding="utf-8"))
        contract = payload["sections"][0]["first_draft_generation_contract"]
        contract["no_fixed_short_sentence_ratio"] = False
        payload["gate_status"] = "passed"
        self.files["outline_contract"].write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            draft_capacity_contract=self.files["profile"],
            section_source_bundle=self.files["section_bundle"],
        )
        self.assertTrue(any("不得设置固定短句" in item for item in errors))

    def test_outline_requires_setting_sequence_contract(self) -> None:
        errors = GATE.validate_release(
            phase="outline",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
        )
        self.assertTrue(any("设定内部顺序契约" in item for item in errors))

    def test_outline_passes_with_setting_sequence_contract(self) -> None:
        errors = GATE.validate_release(
            phase="outline",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            setting_sequence_receipt=self.files["setting_sequence"],
        )
        self.assertEqual([], errors)

    def test_changed_setting_invalidates_outline_release(self) -> None:
        self.setting.write_text("设定已变化", encoding="utf-8")
        errors = GATE.validate_release(
            phase="outline",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            setting_sequence_receipt=self.files["setting_sequence"],
        )
        self.assertTrue(any("SHA 已变化" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
