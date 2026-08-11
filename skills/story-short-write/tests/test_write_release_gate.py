from __future__ import annotations

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
    def emotion_beats(evidence: str) -> list[dict]:
        roles = ["情绪进入点", "受辱或刺痛", "短暂希望或反抗", "反刀", "情绪峰值", "场末余痛"]
        return [
            {
                "beat_id": f"E-{index}",
                "role": role,
                "trigger": f"{role}的具体触发",
                "relationship_position_change": f"{role}改变关系位置",
                "reader_effect": f"读者在{role}感到关系恶化",
                "intensity": 8,
                "evidence": f"{evidence}·{index}",
            }
            for index, role in enumerate(roles, start=1)
        ]

    @staticmethod
    def plot_beats(prefix: str, evidence_prefix: str) -> list[dict]:
        side = "原文" if prefix == "P" else "目标"
        return [
            {
                "beat_id": f"{prefix}-{index}",
                "action": f"{side}第{index}拍施事者完成{side}第{index}拍动作",
                "actor": f"{side}第{index}拍施事者",
                "pressure_or_trigger": f"{side}第{index}拍压力",
                "control_change": f"{side}第{index}拍控制权变化",
                "information_change": f"{side}第{index}拍信息变化",
                "consequence": f"{side}第{index}拍现实后果",
                "evidence": f"{evidence_prefix}{index}",
                **(
                    {
                        "object_or_receiver": f"第{index}拍的动作对象",
                        "source_range": {"start_line": 1, "end_line": 1},
                        "bid_ids": ["BID-01"],
                    }
                    if prefix == "P"
                    else {}
                ),
            }
            for index in range(1, 5)
        ]

    @staticmethod
    def bridge_emotion_beats(*, target: bool = False) -> list[dict]:
        roles = ["仍等解释", "第一次刺痛", "短暂反抗", "错答反刺", "动作峰值"]
        source_quotes = [
            "原文场面里，他先伸手拦我，我把他的手推开。",
            "我没想到他还会替别人解释。",
            "解释什么？",
            "钥匙放在桌上，她先拿走了。",
            "有意思，现在倒像是我进错了门。",
        ]
        return [
            {
                "beat_id": f"E-{index}",
                "role": role,
                "trigger": (
                    f"目标人物被第{index}次新场面动作触发"
                    if target
                    else f"原文第{index}个情绪触发"
                ),
                "relationship_position_change": (
                    "目标丈夫偏护后，目标妻子的位置继续下降。"
                    if target
                    else "丈夫偏护后，妻子的位置继续下降。"
                ),
                "reader_effect": f"读者在第{index}拍感到关系恶化",
                "intensity": 7,
                "evidence": f"动作一·{index}" if target else source_quotes[index - 1],
            }
            for index, role in enumerate(roles, start=1)
        ]

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.files = {}
        self.original_validate_ledger = GATE._RULE_LEDGER_MODULE.validate_ledger
        self.original_validate_prewrite_ledger = (
            GATE._RULE_LEDGER_MODULE.validate_prewrite_ledger
        )
        GATE._RULE_LEDGER_MODULE.validate_ledger = lambda _path: ([], {})
        GATE._RULE_LEDGER_MODULE.validate_prewrite_ledger = lambda _path: []
        self.setting = self.root / "设定.md"
        self.outline = self.root / "大纲.md"
        self.setting.write_text("设定", encoding="utf-8")
        self.outline.write_text(
            "## 1. 起事\n\n动作一\n动作二\n"
            + "\n".join(f"动作一·{index}" for index in range(1, 7))
            + "\n"
            + "\n".join(
                f"目标情绪动作片段{index}" for index in range(1, 6)
            )
            + "\n"
            + "\n".join(f"目标情节拍{index}" for index in range(1, 5))
            + "\n\n## 尾声\n\n目标情绪动作片段6\n",
            encoding="utf-8",
        )
        source_root = self.root / "拆文库" / "测试书"
        self.source_original = source_root / "原文" / "原文.txt"
        self.source_original.parent.mkdir(parents=True)
        self.source_original.write_text(
            "原文场面里，他先伸手拦我，我把他的手推开。"
            "我没想到他还会替别人解释。解释什么？我从头到尾一句话都没说。"
            "钥匙放在桌上，她先拿走了。有意思，现在倒像是我进错了门。"
            "我懒得再问，转身去收自己的东西。身后有人叫我，我也没停。"
            "最后门关上了。外面还有声音，反正和我没什么关系了。"
            "他追到门边按住钥匙。"
            "「你先别拿走，我们回去再说行不行？」"
            "「钥匙是谁给她的？」"
            "「她刚哭过，你别在这个时候跟她计较。」"
            "「所以你先松手。」"
            "门都要关了，他还在解释。"
            "「你一定要把事情弄得这么难看吗？」"
            "「我问的是谁动了我的东西。」"
            "「我现在跟你说的是一家人的体面。」"
            "「那就别碰我的门。」"
            + "".join(f"原文场面·{index}" for index in range(1, 7))
            + "".join(f"原文情节拍{index}" for index in range(1, 5)),
            encoding="utf-8",
        )
        self.source_emotion_ledger = source_root / "写作资产" / "全文情绪颗粒总账.json"
        self.source_emotion_ledger.parent.mkdir(parents=True, exist_ok=True)
        source_quotes = [
            "原文场面里，他先伸手拦我，我把他的手推开。",
            "我没想到他还会替别人解释。",
            "解释什么？",
            "钥匙放在桌上，她先拿走了。",
            "有意思，现在倒像是我进错了门。",
            "最后门关上了。",
        ]
        roles = ["仍等解释", "第一次刺痛", "短暂反抗", "错答反刺", "动作峰值", "离场余痛"]
        ledger_beats = [
            {
                "beat_id": f"E-{index + 1}",
                "segment_id": "SEG-01",
                "start_line": 1,
                "end_line": 1,
                "role": role,
                "content": f"原文中{role}这一拍发生。",
                "trigger": f"原文第{index + 1}个情绪触发",
                "relationship_position_change": "丈夫偏护后，妻子的位置继续下降。",
                "reader_effect": "读者先看见期待，再被偏护动作反刺。",
                "narrative_function": "推动关系位置和离场决定变化。",
                "intensity": 7,
                "source_evidence": [source_quotes[index]],
                "bid_ids": [] if index == 5 else ["BID-01"],
            }
            for index, role in enumerate(roles)
        ]
        self.source_emotion_ledger.write_text(
            json.dumps(
                {
                    "schema_version": GATE._EMOTIONAL_GRANULARITY_MODULE.SOURCE_LEDGER_SCHEMA,
                    "source": {
                        "path": str(self.source_original.resolve()),
                        "sha1": GATE._EMOTIONAL_GRANULARITY_MODULE.sha1_file(
                            self.source_original
                        ),
                        "line_count": 1,
                    },
                    "coverage_segments": [
                        {
                            "segment_id": "SEG-01",
                            "start_line": 1,
                            "end_line": 1,
                            "kind": "emotion_bearing",
                            "beat_ids": [beat["beat_id"] for beat in ledger_beats],
                        }
                    ],
                    "beats": ledger_beats,
                    "completeness_review": {
                        "all_source_lines_classified": True,
                        "non_bid_beats_preserved": True,
                        "bid_derived_after_full_inventory": True,
                        "reviewed_by_current_model": True,
                        "automation_used_for_semantic_judgment": False,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.source_plot_ledger = source_root / "写作资产" / "全文情节微拍总账.json"
        source_plot_beats = self.plot_beats("P", "原文情节拍")
        self.source_plot_ledger.write_text(
            json.dumps(
                {
                    "schema_version": "story-short-analyze.full-text-plot-ledger.v1",
                    "source": {
                        "path": str(self.source_original.resolve()),
                        "sha256": GATE._OUTLINE_PERFORMANCE_MODULE.sha256(
                            self.source_original
                        ),
                    },
                    "beats": [
                        {
                            "beat_id": beat["beat_id"],
                            "actor": beat["actor"],
                            "action": beat["action"],
                            "object_or_receiver": beat["object_or_receiver"],
                            "pressure_or_trigger": beat["pressure_or_trigger"],
                            "control_change": beat["control_change"],
                            "information_change": beat["information_change"],
                            "consequence": beat["consequence"],
                            "source_range": beat["source_range"],
                            "source_evidence": beat["evidence"],
                            "bid_ids": beat["bid_ids"],
                        }
                        for beat in source_plot_beats
                    ],
                    "completeness_review": {
                        "full_text_scanned_l1_to_eof": True,
                        "independent_from_emotion_ledger": True,
                        "no_emotion_beat_substitution": True,
                        "all_effective_plot_beats_preserved": True,
                        "manual_judgment": "已独立盘清施事者、对象、动作、信息、控制权和后果。",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        bridge_catalog = source_root / "写作资产" / "桥段施工卡.md"
        bridge_catalog.parent.mkdir(parents=True, exist_ok=True)
        bridge_catalog.write_text("## BID-01 公开掉位\n", encoding="utf-8")
        subflow_catalog = source_root / "写作资产" / "子流程索引.jsonl"
        style_granularity = {
            field: {
                "analysis": f"{field} 的主体原文局部分析。",
                "source_evidence": [
                    "原文场面里，他先伸手拦我，我把他的手推开。",
                    "有意思，现在倒像是我进错了门。",
                ],
            }
            for field in GATE._OUTLINE_PERFORMANCE_MODULE.SOURCE_STYLE_GRANULARITY_FIELDS
        }
        subflow_catalog.write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "source_range": "L1-L5",
                    "source_style_granularity": style_granularity,
                },
                ensure_ascii=False,
            )
            + "\n",
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
            "prose",
            "emotional",
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
            elif name == "prose":
                payload = self.prose_contract_payload()
            elif name == "emotional":
                payload = self.emotional_contract_payload()
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
            "source_bridge_flow_inventory_completed": True,
            "source_plot_beat_inventory_completed": True,
            "plot_and_emotion_ledgers_independently_built": True,
            "outline_bridge_flow_parity_reviewed_before_draft": True,
            "plot_beat_mapping_reviewed_before_draft": True,
            "relationship_legibility_reviewed_before_draft": True,
            "professional_shell_translation_reviewed_before_draft": True,
            "source_emotion_flow_parity_reviewed_before_draft": True,
            "complete_source_emotion_beat_inventory_reviewed": True,
            "source_subflow_granularity_coverage_reviewed": True,
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
                "source_required_sequence": ["公开偏护", "主角反抗", "希望落空", "主角失位"],
                "source_must_keep_actions": ["抢走位置", "旁观者改站队"],
                "source_scene_granularity": "动作和站位连续换主。",
                "source_plot_beats": self.plot_beats("P", "原文情节拍"),
                "source_plot_beat_completion_review": "已逐句复核，全部有效情节拍均已入账。",
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
                "source_required_sequence": ["公开偏护", "主角反抗", "希望落空", "主角失位"],
                "source_must_keep_actions": ["抢走位置", "旁观者改站队"],
                "source_scene_granularity": "动作和站位连续换主。",
                "source_plot_beats": self.plot_beats("P", "原文情节拍"),
                "target_plot_beats": self.plot_beats("TP", "目标情节拍"),
                "plot_beat_mapping": [
                    {
                        "source_beat_id": f"P-{index}",
                        "target_beat_id": f"TP-{index}",
                        "status": "adapted",
                        "adaptation_note": f"第{index}拍仅替换表层元素。",
                    }
                    for index in range(1, 5)
                ],
                "plot_granularity_parity_judgment": "四拍逐一迁移，没有漏拍、并拍或压缩。",
                "source_emotion_sequence": self.bridge_emotion_beats(),
                "target_emotion_sequence": self.bridge_emotion_beats(target=True),
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 5,
                "target_peak_beat": 5,
                "turning_point_selection_review": "已根据期待、关系与行动的真实转折选定 E-4 为反刀、E-5 为峰值，未按最高烈度自动猜测。",
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
        coverage = payload["source_subflow_granularity_coverage"][0]
        coverage.update(
            {
                "target_outline_sections": ["1"],
                "coverage_status": "adapted",
                "adaptation_boundary": "只迁移六类局部颗粒，不复制人物、职业、原句或完整桥壳。",
                "manual_judgment": "主体 SF-01 的六类颗粒均已分别落到细纲原句。",
            }
        )
        for field in GATE._OUTLINE_PERFORMANCE_MODULE.SOURCE_STYLE_GRANULARITY_FIELDS:
            coverage["transferred_style_fields"][field] = {
                "target_outline_evidence": ["动作一"],
                "transfer_method": f"将 {field} 转为目标场面的动作与句面安排。",
                "surface_copy_rejected": True,
            }
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
                "scene_units": [
                    {
                        "scene_id": "S1-01",
                        "emotion_beat_ids": [f"E-{index}" for index in range(1, 7)],
                        "plot_beat_ids": [f"TP-{index}" for index in range(1, 5)],
                        "allocated_chars": 900,
                        "full_scene_required": True,
                        "summary_only": False,
                        "entry_pressure": "甲在公开场拿走乙的钥匙并逼迫乙让出原位。",
                        "interaction_chain": [
                            "甲先拿钥匙并要求乙退后。",
                            "乙追问钥匙归属并伸手阻拦。",
                            "甲借第三人的需要挡回，旁观者随之改口。",
                        ],
                        "turning_action": "甲把钥匙交给第三人，入口控制权当场换主。",
                        "visible_consequence": "乙失去进入权，旁观者不再等待乙作决定。",
                        "aftershock": "乙退出原站位，钥匙留在第三人手里。",
                        "reader_emotion_path": "短暂维护感被公开让位动作截断，转成可见失位。",
                        "outline_evidence": ["动作一", "动作二"],
                    }
                ],
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
                    "source_emotion_sequence": self.emotion_beats("原文场面"),
                    "target_emotion_sequence": self.emotion_beats("动作一"),
                    "source_intensity_score": 8,
                    "target_intensity_score": 8,
                    "source_reversal_beat": 4,
                    "target_reversal_beat": 4,
                    "source_peak_beat": 5,
                    "target_peak_beat": 5,
                    "ending_afterpain_equivalent": True,
                    "reader_experience_equivalent": True,
                    "manual_judgment": "逐拍对齐且没有把公开抛弃降成职业分歧。",
                    "parity_status": "adapted_equal_intensity",
                    "adaptation_boundary": "只迁移情绪结构，不复制人物与原句。",
                },
                "forbidden_items": ["不提前解释", "不连续报账"],
                "outline_evidence": ["动作一", "动作二"],
                "manual_judgment": "本场是连续互动，不是清单。",
            }
        )
        payload["reviewed_by_current_model"] = True
        payload["gate_status"] = "passed"
        return payload

    def prose_contract_payload(self) -> dict:
        prose_gate = GATE._PROSE_GRANULARITY_MODULE
        payload = prose_gate.create_receipt("测试", self.source_original)
        payload = prose_gate.bind_outline(payload, self.outline)
        payload["reviewed_by_current_model"] = True
        payload["prewrite_status"] = "passed"
        source_text = self.source_original.read_text(encoding="utf-8")
        payload["source_baseline"]["continuous_excerpts"] = [
            {
                "quote": source_text[start : start + 70],
                "purpose": purpose,
                "language_judgment": "连续口语叙述，判断跟着现场发生。",
            }
            for start, purpose in zip(
                (0, 20, 40, 60, 80),
                ("开口", "冲突", "对白", "日常", "收口"),
            )
        ]
        anchors = ["原文场面里，他先伸手拦我，我把他的手推开。", "有意思"]
        for name in prose_gate.REQUIRED_DIMENSIONS:
            payload["source_baseline"]["dimensions"][name] = {
                "rule": f"{name} 采用主体原文口语。",
                "source_quotes": anchors,
                "transfer_rule": "迁移句间关系，不复制表层情节。",
                "ai_drift_to_reject": "拒绝工整复合钩子和总结句。",
            }
        payload["source_baseline"]["anti_patterns"] = [
            {"pattern": f"AI模板{i}", "why_unlike_source": "原文不会这样说。"}
            for i in range(3)
        ]
        payload["source_baseline"]["manual_judgment"] = "主体声线已经人工建立。"
        source_sentences = prose_gate.sentence_units(source_text)
        dialogue_source_excerpts = [
            (
                "他追到门边按住钥匙。"
                "「你先别拿走，我们回去再说行不行？」"
                "「钥匙是谁给她的？」"
                "「她刚哭过，你别在这个时候跟她计较。」"
                "「所以你先松手。」"
            ),
            (
                "门都要关了，他还在解释。"
                "「你一定要把事情弄得这么难看吗？」"
                "「我问的是谁动了我的东西。」"
                "「我现在跟你说的是一家人的体面。」"
                "「那就别碰我的门。」"
            ),
        ]
        passages = []
        purposes = ("开口", "冲突", "对白", "日常", "收口")
        for passage_index, purpose in enumerate(purposes, start=1):
            annotations = []
            for sentence_index, sentence in enumerate(source_sentences, start=1):
                annotation = {
                    "source_sentence": sentence,
                    "feature_ids": ["CP-01", "SC-01"],
                }
                if prose_gate.explicit_relation_markers(sentence):
                    annotation["feature_ids"] += ["LM-02", "SC-05"]
                relation_markers = prose_gate.explicit_relation_markers(sentence)
                fallback_evidence = sentence[:8].strip()
                annotation["feature_evidence"] = [
                    {
                        "feature_id": feature_id,
                        "source_evidence": (
                            relation_markers[0]
                            if feature_id in ("LM-02", "SC-05") and relation_markers
                            else fallback_evidence
                        ),
                        "mechanism": (
                            f"{feature_id} 由当前句的具体词序、停顿或话语动作提供，"
                            "只记录实际可见的句面机制。"
                        ),
                    }
                    for feature_id in annotation["feature_ids"]
                ]
                for field_index, field in enumerate(
                    prose_gate.SOURCE_SENTENCE_ANNOTATION_FIELDS, start=1
                ):
                    annotation[field] = (
                        f"{purpose}样本第{sentence_index}句的第{field_index}类句面证据，"
                        "结合当句词序和停顿作出局部判断。"
                    )
                annotations.append(annotation)
            passages.append(
                {
                    "id": f"P-{passage_index}",
                    "quote": source_text,
                    "purpose": purpose,
                    "sentence_annotations": annotations,
                }
            )
        payload["ultra_fine_source_baseline"] = {
            "methodology_reference_read": True,
            "annotation_unit": "sentence",
            "feature_inventory": list(prose_gate.ULTRA_FINE_FEATURE_IDS),
            "feature_assignment_policy": {
                "method": "current_model_sentence_semantic",
                "mechanical_quota_or_rotation_used": False,
                "full_inventory_occurrence_required": False,
                "manual_judgment": "逐句按真实句面选择特征，不用序号轮转或强制覆盖 52 项。",
            },
            "source_passages": passages,
            "distribution_baseline": {
                "measurement_method": "逐句人工复核后记录字符、句长、问句、省略号、段长与虚词次数。",
                "metrics": {
                    "non_whitespace_chars": len(source_text),
                    "sentence_count": len(source_sentences),
                    "sentence_length_median": 18,
                    "sentence_length_p90": 28,
                    "question_count": 2,
                    "ellipsis_count": 0,
                    "paragraph_length_median": len(source_text),
                    "function_word_counts": {"我": 7, "了": 5},
                },
                "interpretation": "原文以中短口语句推进现场，问句承担关系错位，极短判断只在受压节点出现。",
                "mechanical_statistical_matching_forbidden": True,
            },
            "manual_judgment": "连续片段已经逐句检查，正文只迁移句法、焦点和语用机制，不迁移人物事件。",
        }
        liveliness_asset_file = self.root / "成文活性层资产.md"
        liveliness_asset_file.write_text("测试成文活性资产", encoding="utf-8")
        liveliness_assets = []
        source_quotes = [
            "原文场面里，他先伸手拦我，我把他的手推开。",
            "我没想到他还会替别人解释。",
            "有意思，现在倒像是我进错了门。",
        ]
        for asset_type in prose_gate.LIVELINESS_ASSET_TYPES:
            for asset_index, source_quote in enumerate(source_quotes, start=1):
                liveliness_assets.append(
                    {
                        "id": f"LIVE-{asset_type}-{asset_index}",
                        "type": asset_type,
                        "source_quote": source_quote,
                        "live_core": "动作和判断带着人物当场的脾气与注意力偏差。",
                        "transfer_mechanism": "迁移临场反应顺序，不复制原文人物和事件表层。",
                        "surface_copy_boundary": "拒绝复制原人物、职业、物件和完整原句组合。",
                        "surface_copy_rejected": True,
                    }
                )
        payload["prose_liveliness_layer"] = {
            "status": "passed",
            "source_extraction_mode": "current_model_manual",
            "primary_source_only": True,
            "asset_file": self.binding(liveliness_asset_file),
            "asset_types": list(prose_gate.LIVELINESS_ASSET_TYPES),
            "assets": liveliness_assets,
            "stiffness_prohibitions": [
                {
                    "pattern": f"作者替人物总结的僵硬句面模式{i}",
                    "why_stiff": "作者替人物整理了完整意义，现场动作失去作用。",
                    "replacement_action": "回到人物动作、错答和物件阻力，保留直接主观声音。",
                }
                for i in range(6)
            ],
            "manual_judgment": "七类资产均从主体原文真实句面提取，用于首写时保住人物现场和不工整的活性。",
        }
        personality_assets = []
        personality_quotes = [
            "原文场面里，他先伸手拦我，我把他的手推开。",
            "有意思，现在倒像是我进错了门。",
        ]
        for asset_type in prose_gate.CHARACTER_PERSONALITY_ASSET_TYPES:
            for asset_index in range(1, 4):
                personality_assets.append(
                    {
                        "id": f"PERSON-{asset_type}-{asset_index}",
                        "type": asset_type,
                        "source_quotes": personality_quotes,
                        "personality_core": f"第{asset_index}种{asset_type}体现稳定偏手和临场破绽。",
                        "transfer_mechanism": "迁移注意、错答与动作选择，不复制人物身份和事件。",
                        "surface_copy_boundary": "拒绝复制原职业、物件、关系称谓和完整情节表层。",
                        "surface_copy_rejected": True,
                    }
                )
        personality_file = self.root / "人物性格颗粒度资产.md"
        personality_file.write_text("测试人物性格颗粒度资产", encoding="utf-8")
        protagonist_assets = [personality_assets[index]["id"] for index in (0, 3, 6, 9, 12)]
        counterpart_assets = [personality_assets[index]["id"] for index in (1, 4, 7, 10, 13)]
        payload["character_personality_layer"] = {
            "status": "passed",
            "source_extraction_mode": "current_model_manual",
            "primary_source_only": True,
            "asset_file": self.binding(personality_file),
            "asset_types": list(prose_gate.CHARACTER_PERSONALITY_ASSET_TYPES),
            "assets": personality_assets,
            "target_character_profiles": [
                {
                    "name": "林初",
                    "role": "protagonist",
                    "source_asset_ids": protagonist_assets,
                    "attention_bias": "先看钥匙和拦门的手，再听对方解释。",
                    "desire_and_shame": "想被挽留，却羞于承认自己还在等。",
                    "defense_strategy": "用短问和收回物件保护自己，不解释委屈。",
                    "speech_pattern": "追具体名词，受伤后才插一句冷话。",
                    "misfire_pattern": "真正想问关系，却故意只问钥匙归谁。",
                    "action_bias": "一受压就控制门、钥匙和离场方向。",
                    "self_contradiction": "声称不在意，动作却会等对方追上来。",
                    "private_relation_language": "最软时漏出旧昵称，随后立刻收回。",
                    "generic_shells_rejected": ["清醒判词", "全程正确", "只会冷笑"],
                    "surface_copy_rejected": True,
                    "manual_judgment": "她由归属敏感、嘴硬等待和物件控制构成，不能替换成通用清醒女主。",
                },
                {
                    "name": "周远",
                    "role": "relationship_counterpart",
                    "source_asset_ids": counterpart_assets,
                    "attention_bias": "先看现场是否难看，再迟一步看伴侣。",
                    "desire_and_shame": "想维持好人位置，害怕承认偏护来自私心。",
                    "defense_strategy": "把具体归属问题改写成人情和体面问题。",
                    "speech_pattern": "先叫名字缓和，再用长解释拖延回答。",
                    "misfire_pattern": "被问钥匙时先解释别人为什么哭。",
                    "action_bias": "习惯先伸手拦门，再补迟到的照顾。",
                    "self_contradiction": "自认公平，身体却总先挡在别人前面。",
                    "private_relation_language": "失去控制时才叫旧昵称，平时保持克制。",
                    "generic_shells_rejected": ["只会别闹", "工具渣男", "精准递反刀"],
                    "surface_copy_rejected": True,
                    "manual_judgment": "他由体面自证、下意识拦挡和迟到照顾构成，不能只负责说错话。",
                },
            ],
            "manual_judgment": "两名目标人物分别迁移原文的归属偏看与体面回避，不能共享同一反应方案。",
        }
        for plan in payload["section_generation_plans"]:
            chain_excerpts = [
                "".join(source_sentences[:5]),
                "".join(source_sentences[5:]),
            ]
            plan.update(
                {
                    "status": "passed",
                    "planned_before_draft": True,
                    "generation_driver": "continuous_source_chain",
                    "single_sentence_features_secondary": True,
                    "continuous_source_chain_packets": [
                        {
                            "source_excerpt": excerpt,
                            "source_sentence_chain": prose_gate.sentence_units(excerpt),
                            "chain_motion": f"正例句链{index}先给异常和追问，再让错答或动作改变当前话轮。",
                            "target_scene_use": f"第{index}组用于钥匙归属争夺，让关系压力在可见动作里加重。",
                            "target_sentence_relation": f"第{index}组保留看见、追问、回避、收物件的顺序，不补心理算法。",
                            "explanation_to_omit": f"删掉第{index}组动作后关于人物本质、权衡过程和象征意义的翻译。",
                            "surface_copy_rejected": True,
                            "manual_judgment": f"第{index}组只迁移连续反应链，不复制测试原文的人物、钥匙事件和原句表层。",
                        }
                        for index, excerpt in enumerate(chain_excerpts, start=1)
                    ],
                    "contrastive_examples": [
                        {
                            "positive_source_excerpt": excerpt,
                            "positive_effect": f"正例{index}让异常、错答和动作自己递进，判断不越过人物所见。",
                            "negative_example": f"错误反例{index}先列完现场事项，再解释他正在权衡利弊并总结人物本质。",
                            "negative_failure": f"反例{index}以全知说明替代人物接招，具体争夺被抽象心理算法盖住。",
                            "rewrite_instruction": f"反例{index}应删除解释，让追问逼出错答，再由物件换主收掉话轮。",
                            "surface_copy_rejected": True,
                        }
                        for index, excerpt in enumerate(chain_excerpts, start=1)
                    ],
                    "relation_micro_examples": [
                        {
                            "source_excerpt": "「她刚哭过，你别在这个时候跟她计较。」「所以你先松手。」",
                            "source_relation_type": "cause_effect",
                            "target_relation_type": "cause_effect",
                            "source_marking_mode": "explicit",
                            "target_marking_mode": "explicit",
                            "source_markers": ["所以"],
                            "target_markers": ["所以"],
                            "source_function_word_skeleton": "先摆出第三人的哭，再用所以把松手包装成唯一结论。",
                            "target_rehearsal": "「她现在还在哭，所以钥匙先放我这里，等回家我再给你。」",
                            "negative_example": "「她现在还在哭，钥匙先放我这里，等回家我再给你。」",
                            "negative_failure": "错例去掉所以后，男人强行拿第三人推导妻子让步的自以为讲理感变弱。",
                            "transfer_instruction": "保留用所以强行建立因果的错答口气，但替换人物、物件和请求内容。",
                            "mechanical_marker_insertion_forbidden": True,
                            "surface_copy_rejected": True,
                            "manual_judgment": "这一组显式因果属于人物的自证逻辑，连接词本身就是压迫口气的一部分。",
                        },
                        {
                            "source_excerpt": "原文场面里，他先伸手拦我，我把他的手推开。",
                            "source_relation_type": "succession",
                            "target_relation_type": "succession",
                            "source_marking_mode": "implicit",
                            "target_marking_mode": "implicit",
                            "source_markers": [],
                            "target_markers": [],
                            "source_function_word_skeleton": "拦手后直接接推开，动作方向已经把接招关系说明白。",
                            "target_rehearsal": "他把手压到钥匙上，我抽回钥匙，顺手关上了门。",
                            "negative_example": "他把手压到钥匙上，所以我抽回钥匙，以此表达拒绝。",
                            "negative_failure": "错例机械补因果和意义解释，两个连续动作原有的现场速度被拖慢。",
                            "transfer_instruction": "保留动作接动作的隐式顺承，不为了形式完整添加连接词和主题说明。",
                            "mechanical_marker_insertion_forbidden": True,
                            "surface_copy_rejected": True,
                            "manual_judgment": "这一组由动作方向自然衔接，若加所以反而偏离主体原文的短促反应。",
                        },
                    ],
                    "dialogue_voice_packets": [
                        {
                            "source_excerpt": excerpt,
                            "source_dialogue_turns": prose_gate.dialogue_turn_units(excerpt),
                            "target_character": "周远",
                            "turn_motion": f"原文对白{index}先叫住关系人，再找补，随后用第三人的难处压过具体归属追问。",
                            "target_scene_use": f"第{index}组用于当前门口冲突，让压迫者先缓和称呼再答偏钥匙问题。",
                            "target_rehearsal": (
                                f"周远伸手按住第{index}把钥匙。"
                                "「你先别拿，等我安顿完她，我们回去慢慢说。」"
                                "「我只问钥匙是谁给的。」"
                                "「她刚哭过，你非得现在逼她吗？」"
                            ),
                            "oral_texture_transfer": "保留叫住、以后解释、弱者理由和再次追问的口头展开，不压成一句命令。",
                            "relationship_leverage": "压迫者利用旧关系仍可私下谈和主角过去总会体谅的习惯施压。",
                            "functional_compression_to_avoid": "禁止压成你先走、她留下的剧情调度句。",
                            "negative_example": f"「你先处理第{index}件事，她留在这里。」",
                            "negative_failure": "错句只交付人物移动与剧情信息，没有称呼、找补、关系杠杆和接招。",
                            "rewrite_instruction": "恢复叫人、承诺稍后解释、借弱者施压和对方追具体归属四步话轮。",
                            "surface_copy_rejected": True,
                            "manual_judgment": "试演保留主体丈夫自认讲理却不断答偏的口条，当前人物和钥匙场面已经换新。",
                        }
                        for index, excerpt in enumerate(
                            dialogue_source_excerpts, start=1
                        )
                    ],
                    "source_passage_ids": ["P-1"],
                    "sentence_mechanisms": [
                        {
                            "source_sentence": source_sentences[index],
                            "feature_ids": ["CP-01", "SC-01"],
                            "mechanism": f"机制{index}保留动作先于判断的句间次序。",
                            "target_intent": f"服务细纲现场的第{index}个关系压力点。",
                            "allowed_deviation": "允许替换人物物件与句长，不复制表层故事。",
                            "prohibited_shell": "禁止意义总结、排比判词与工整复合钩子。",
                            "surface_copy_rejected": True,
                        }
                        for index in range(3)
                    ],
                    "paragraph_plan": {
                        field: f"{field}按动作变化切段并保留关系空白。"
                        for field in prose_gate.SECTION_PARAGRAPH_PLAN_FIELDS
                    },
                    "window_plan": {
                        field: f"{field}用长短句差和有限插嘴控制窗口。"
                        for field in prose_gate.SECTION_WINDOW_PLAN_FIELDS
                    },
                    "liveliness_plan": {
                        "planned_before_draft": True,
                        "asset_ids": [
                            liveliness_assets[index]["id"] for index in (0, 3, 6, 9)
                        ],
                        **{
                            field: f"{field} 按本节人物受压后的临场偏手具体落笔。"
                            for field in prose_gate.LIVELINESS_SECTION_PLAN_FIELDS
                        },
                        "stiffness_patterns_rejected": [
                            "作者主题总结",
                            "对话轮流答题",
                            "物件意义立刻说透",
                        ],
                        "manual_judgment": "本节先让动作、身体和错答暴露关系，再允许叙述者给一句当场的直接判断。",
                    },
                    "character_plan": {
                        "planned_before_draft": True,
                        "active_character_names": ["林初", "周远"],
                        "participants": [
                            {
                                "character_name": "林初",
                                "source_asset_ids": protagonist_assets[:2],
                                "scene_want": "想拿回钥匙又不肯承认还在等解释。",
                                "attention_first": "先看拦门的手和钥匙，不听体面理由。",
                                "misread_or_avoidance": "故意把关系伤害缩成钥匙归属。",
                                "speech_boundary": "只追一个名词，不做清醒总结。",
                                "action_or_object_bias": "先收钥匙，用物件决定话轮。",
                                "relationship_private_trigger": "对方拦手时旧有照顾惯性短暂回跳。",
                                "generic_function_line_to_reject": "拒绝直接总结背叛和边界。",
                            },
                            {
                                "character_name": "周远",
                                "source_asset_ids": counterpart_assets[:2],
                                "scene_want": "想维持现场体面并阻止她离开。",
                                "attention_first": "先看门外旁观者，再看她的手。",
                                "misread_or_avoidance": "把归属质问错答成不要闹。",
                                "speech_boundary": "先叫名字再解释，没有直接认错。",
                                "action_or_object_bias": "先伸手拦门，不先回答问题。",
                                "relationship_private_trigger": "门真的关上时才漏出旧昵称。",
                                "generic_function_line_to_reject": "拒绝只说为了她好和别闹。",
                            },
                        ],
                        "interchangeability_risk": "若两人都用冷问和收钥匙，本节会退成同声线答题对白。",
                        "manual_judgment": "林初的归属敏感与周远的体面回避相撞，动作方向必须相反。",
                    },
                    "surface_copy_rejected": True,
                    "manual_judgment": "起事节在落笔前绑定拦手与反问的句面机制，让冲突从即时知觉进入。",
                }
            )
        payload["calibration_samples"] = [
            {
                "source_quote": "原文场面里，他先伸手拦我，我把他的手推开。",
                "target_sample": f"我没想到回来拿第{i}样东西，也会看见他们站在门里。",
                "comparison": "均为直白口语陈述。",
                "functional_alignment_used_as_prose_proof": False,
                "extra_ai_shell": False,
            }
            for i in range(3)
        ]
        return payload

    def emotional_contract_payload(self) -> dict:
        emotional_gate = GATE._EMOTIONAL_GRANULARITY_MODULE
        payload = emotional_gate.create_receipt(
            "测试", self.source_original, self.source_emotion_ledger
        )
        payload = emotional_gate.bind_outline(payload, self.outline)
        source_quotes = [
            "原文场面里，他先伸手拦我，我把他的手推开。",
            "我没想到他还会替别人解释。",
            "解释什么？",
            "钥匙放在桌上，她先拿走了。",
            "有意思，现在倒像是我进错了门。",
            "最后门关上了。",
        ]
        roles = ["仍等解释", "第一次刺痛", "短暂反抗", "错答反刺", "动作峰值", "离场余痛"]
        item = payload["section_contracts"][0]
        item.update(
            {
                "status": "passed",
                "source_excerpt": self.source_original.read_text(encoding="utf-8")[:90],
                "immediate_subjective_judgment_plan": "保留女主看见偏护后的直接冷刺，不改成无主语的身体反应。",
                "untidy_thought_or_emotional_crack_plan": "让她短暂盼丈夫解释，随后因错答露出不体面的失望。",
                "embodied_or_object_action_plan": "用拦手、推手和钥匙换主承接情绪，动作必须改变现场。",
                "old_wound_trigger_plan": "本节不展开旧伤，只用进入权失效预埋后续空间触发。",
                "opponent_pressure_plan": "丈夫先替别人解释并拦手，迫使女主从等待转为反抗。",
                "loss_of_control_or_equivalent_plan": "女主直接推开阻拦，形成与原文同级的动作升级。",
                "source_like_direct_emotion_preserved": True,
                "surface_copy_rejected": True,
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 5,
                "target_peak_beat": 5,
                "source_emotion_beat_completion_review": "已逐句通读原文场面，按每次关系位置和期待变化穷尽全部实际情绪拍。",
                "turning_point_selection_review": "已根据期待、关系与行动的真实转折选定 E-4 为反刀、E-5 为峰值，未按最高烈度自动猜测。",
                "required_plot_beats": [
                    {
                        "beat_id": f"TP-{index}",
                        "action": f"第{index}拍动作",
                        "outline_evidence": f"目标情节拍{index}",
                    }
                    for index in range(1, 5)
                ],
                "plot_beat_completion_review": "已核对细纲表演回执全部目标情节拍，四拍均唯一归入本节且顺序一致。",
                "manual_judgment": "这一节保留主体原文从期待解释到直接冷刺的情绪锯齿，目标动作不低于原文。",
            }
        )
        item["source_emotion_beats"] = []
        item["target_outline_beats"] = []
        ledger_beats = json.loads(
            self.source_emotion_ledger.read_text(encoding="utf-8")
        )["beats"]
        for index, role in enumerate(roles):
            ledger_beat = ledger_beats[index]
            item["source_emotion_beats"].append(
                {
                    "beat_id": f"E-{index + 1}",
                    "role": role,
                    "content": ledger_beat["content"],
                    "trigger": ledger_beat["trigger"],
                    "relationship_position_change": ledger_beat[
                        "relationship_position_change"
                    ],
                    "reader_effect": ledger_beat["reader_effect"],
                    "narrative_function": ledger_beat["narrative_function"],
                    "intensity": ledger_beat["intensity"],
                    "source_evidence": ledger_beat["source_evidence"],
                    "bid_ids": ledger_beat["bid_ids"],
                }
            )
            item["target_outline_beats"].append(
                {
                    "beat_id": f"E-{index + 1}",
                    "role": role,
                    "trigger": f"目标第{index + 1}个情绪触发",
                    "relationship_position_change": f"目标第{index + 1}拍让主角在新关系中进一步失位。",
                    "reader_effect": f"读者从目标第{index + 1}拍看见期待如何再次落空。",
                    "intensity": 7,
                    "target_outline_region": (
                        "epilogue" if index == 5 else "section:1"
                    ),
                    "target_story_adaptation": (
                        f"把原文第{index + 1}拍造成的关系落差迁入目标人物的新场面动作，"
                        "保留该拍的期待变化和受伤方向，但更换人物、空间与物件。"
                    ),
                    "target_evidence_coverage_review": (
                        f"已逐句核对完整动作链；触发为目标第{index + 1}个情绪触发，"
                        f"关系位移为目标第{index + 1}拍让主角在新关系中进一步失位。"
                        "两者均已在独占证据中发生，未把连续动作压成结论。"
                    ),
                    "outline_evidence": [f"目标情绪动作片段{index + 1}"],
                }
            )
        payload["reviewed_by_current_model"] = True
        payload["prewrite_status"] = "passed"
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
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
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
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
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
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
        )
        self.assertTrue(any("未完成写前分类与执行计划" in item for item in errors))
        self.assertTrue(any("缺少 canonical_rule_text" in item for item in errors))

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
        self.assertTrue(any("全文文字颗粒度" in item for item in errors))
        self.assertTrue(any("全文情绪颗粒度" in item for item in errors))

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
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
            emotional_contract=self.files["emotional"],
            source_emotion_ledger=self.source_emotion_ledger,
        )
        self.assertEqual([], errors)

    def test_draft_release_blocks_plot_beat_missing_from_section_contract(self) -> None:
        payload = json.loads(self.files["emotional"].read_text(encoding="utf-8"))
        payload["section_contracts"][0]["required_plot_beats"].pop()
        self.files["emotional"].write_text(json.dumps(payload), encoding="utf-8")
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            outline_contract=self.files["outline_contract"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
            emotional_contract=self.files["emotional"],
            source_emotion_ledger=self.source_emotion_ledger,
        )
        self.assertTrue(any("完整覆盖全部 beat_id" in item for item in errors))

    def test_plot_beat_alignment_uses_primary_inside_and_outside_beats_only(self) -> None:
        outline_data = {
            "selected_source_originals": [
                {
                    "path": "/tmp/primary.txt",
                    "role": "primary",
                    "available_plot_beat_ids": ["P-001", "P-002"],
                },
                {
                    "path": "/tmp/auxiliary.txt",
                    "role": "auxiliary",
                    "available_plot_beat_ids": ["P-010"],
                },
            ],
            "outside_bridge_plot_parity": {
                "plot_beat_mapping": [
                    {
                        "source_beat_id": "P-001",
                        "target_beat_id": "TP-OUT-P-001",
                    }
                ]
            },
            "outline_bridge_flow_parity": [
                {
                    "source_path": "/tmp/primary.txt",
                    "plot_beat_mapping": [
                        {
                            "source_beat_id": "P-002",
                            "target_beat_id": "TP-PRIMARY-P-002",
                        }
                    ],
                },
                {
                    "source_path": "/tmp/auxiliary.txt",
                    "plot_beat_mapping": [
                        {
                            "source_beat_id": "P-010",
                            "target_beat_id": "TP-AUX-P-010",
                        }
                    ],
                },
            ],
        }
        emotional_data = {
            "section_contracts": [
                {
                    "required_plot_beats": [
                        {"beat_id": "TP-OUT-P-001"},
                        {"beat_id": "TP-PRIMARY-P-002"},
                    ]
                }
            ]
        }
        errors: list[str] = []

        GATE.validate_plot_beat_contract_alignment(
            outline_data, emotional_data, errors
        )

        self.assertEqual([], errors)

    def test_source_dominant_policy_blocks_first_draft_cleanup(self) -> None:
        payload = json.loads(self.files["emotional"].read_text(encoding="utf-8"))
        payload["first_draft_policy"][
            "anti_ai_cleanup_applied_during_first_draft"
        ] = True
        self.files["emotional"].write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
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
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
            emotional_contract=self.files["emotional"],
            source_emotion_ledger=self.source_emotion_ledger,
        )
        self.assertTrue(any("anti_ai_cleanup" in item for item in errors))

    def test_draft_requires_outline_performance_contract(self) -> None:
        errors = GATE.validate_release(
            phase="draft",
            writing_receipt=self.files["writing"],
            source_receipt=self.files["source"],
            ledger=self.files["ledger"],
            opening_contract=self.files["opening"],
            profile=self.files["profile"],
            sequence_receipt=self.files["sequence"],
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
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
            prose_contract=self.files["prose"],
            primary_source_original=self.source_original,
        )
        self.assertTrue(any("matched/adapted" in item for item in errors))

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
