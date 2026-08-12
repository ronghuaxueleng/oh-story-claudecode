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
    def emotion_beats(evidence: str, *, target: bool = False) -> list[dict]:
        roles = [
            "情绪进入点",
            "受辱或刺痛",
            "短暂希望或反抗",
            "反刀",
            "情绪峰值",
            "场末余痛",
        ]
        return [
            {
                "beat_id": f"E-{index + 1}",
                "role": role,
                "trigger": f"{'目标人物' if target else '原文人物'}在{role}的具体触发",
                "relationship_position_change": f"{'目标关系' if target else '原文关系'}在{role}后发生位置变化",
                "reader_effect": f"读者在{role}感到关系继续恶化",
                "intensity": 7 + min(index, 2),
                "evidence": f"{evidence}·{index + 1}",
                **(
                    {
                        "hurt_object": "婚姻位置",
                        "expectation_before": f"第{index + 1}拍前仍期待对方维护原有位置",
                        "expectation_after": f"第{index + 1}拍后确认原有位置再次被让给别人",
                        "action_impulse_before": f"第{index + 1}拍前仍准备追问并等待解释",
                        "action_impulse_after": f"第{index + 1}拍后改为收回物件并停止求证",
                        "equivalence_reason": f"第{index + 1}拍用目标动作造成同序失位与行动转向。",
                    }
                    if target
                    else {}
                ),
            }
            for index, role in enumerate(roles)
        ]

    @staticmethod
    def plot_beats(prefix: str, evidence_prefix: str) -> list[dict]:
        beats = [
            {
                "beat_id": f"{prefix}-{index}",
                "action": (
                    f"目标情节拍{index}完成第{index}个新故事动作"
                    if prefix == "TP"
                    else f"第{index}个不可省略动作"
                ),
                "actor": f"目标情节拍{index}" if prefix == "TP" else f"施事者{index}",
                "pressure_or_trigger": f"第{index}拍的现场压力",
                "control_change": f"第{index}拍的控制权变化",
                "information_change": f"第{index}拍新增或延迟的信息",
                "consequence": f"第{index}拍造成的现实后果",
                "evidence": f"{evidence_prefix}{index}",
                **(
                    {
                        "object_or_receiver": f"第{index}拍的动作对象",
                        "source_range": {
                            "start_line": 8 + index,
                            "end_line": 8 + index,
                        },
                        "bid_ids": ["BID-01"],
                    }
                    if prefix == "P"
                    else {
                        "actor_evidence": f"{evidence_prefix}{index}",
                        "object_or_receiver": f"第{index}拍的目标动作对象",
                        "adaptation_equivalence": f"第{index}拍保留控制权变化和现实后果，仅更换目标故事表层。",
                    }
                ),
            }
            for index in range(1, 5)
        ]
        return beats

    @staticmethod
    def plot_mapping() -> list[dict]:
        return [
            {
                "source_beat_id": f"P-{index}",
                "target_beat_id": f"TP-{index}",
                "status": "adapted",
                "adaptation_note": f"第{index}拍只替换人物、职业和表层物件。",
            }
            for index in range(1, 5)
        ]

    @staticmethod
    def write_minimal_plot_ledger(source: Path, bridge_id: str) -> None:
        path = source.parent.parent / "写作资产" / "全文情节微拍总账.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "source": {
                        "path": str(source.resolve()),
                        "sha256": GATE.sha256(source),
                    },
                    "beats": [
                        {
                            "beat_id": "P-AUX-001",
                            "actor": "辅助施事者",
                            "action": "辅助施事者完成一次动作",
                            "object_or_receiver": "辅助动作对象",
                            "pressure_or_trigger": "现场压力",
                            "control_change": "控制权改变",
                            "information_change": "信息变化",
                            "consequence": "现实后果",
                            "source_range": {"start_line": 1, "end_line": 1},
                            "source_evidence": source.read_text(encoding="utf-8"),
                            "bid_ids": [bridge_id],
                        }
                    ],
                    "completeness_review": {
                        "full_text_scanned_l1_to_eof": True,
                        "independent_from_emotion_ledger": True,
                        "no_emotion_beat_substitution": True,
                        "all_effective_plot_beats_preserved": True,
                        "manual_judgment": "已独立扫描。",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.outline = self.root / "小节大纲.md"
        self.outline.write_text(
            "## 1. 起事\n\n动作一\n动作二\n"
            + "\n".join(f"动作一·{index}" for index in range(1, 7))
            + "\n"
            + "\n".join(f"目标情节拍{index}" for index in range(1, 5))
            + "\n\n## 2. 失位\n\n动作三\n动作四\n"
            + "\n".join(f"动作三·{index}" for index in range(1, 7))
            + "\n",
            encoding="utf-8",
        )
        self.book_root = self.root / "拆文库" / "测试书"
        self.source = self.book_root / "原文" / "原文.txt"
        self.source.parent.mkdir(parents=True)
        self.source.write_text(
            "原文场面\n第二条原文证据\n"
            + "\n".join(f"原文场面·{index}" for index in range(1, 7))
            + "\n"
            + "\n".join(f"原文情节拍{index}" for index in range(1, 5)),
            encoding="utf-8",
        )
        self.catalog = self.book_root / "写作资产" / "桥段施工卡.md"
        self.catalog.parent.mkdir(parents=True)
        self.catalog.write_text("## BID-01 公开掉位\n", encoding="utf-8")
        self.subflow_catalog = self.book_root / "写作资产" / "子流程索引.jsonl"
        style_granularity = {
            field: {
                "analysis": f"{field} 的主体原文人工分析。",
                "source_evidence": ["原文场面", "第二条原文证据"],
            }
            for field in GATE.SOURCE_STYLE_GRANULARITY_FIELDS
        }
        self.subflow_catalog.write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "source_range": "L1-L2",
                    "source_style_granularity": style_granularity,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        self.emotion_ledger = self.book_root / "写作资产" / "全文情绪颗粒总账.json"
        self.emotion_ledger.write_text(
            json.dumps(
                {
                    "beats": [
                        {
                            "beat_id": beat["beat_id"],
                            "role": beat["role"],
                            "intensity": beat["intensity"],
                            "content": f"原文情绪内容{index}",
                            "bid_ids": ["BID-01"],
                        }
                        for index, beat in enumerate(self.emotion_beats("原文场面"), 1)
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.plot_ledger = self.book_root / "写作资产" / "全文情节微拍总账.json"
        self.plot_ledger.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "source": {
                        "path": str(self.source.resolve()),
                        "sha256": GATE.sha256(self.source),
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
                        for beat in self.plot_beats("P", "原文情节拍")
                    ],
                    "completeness_review": {
                        "full_text_scanned_l1_to_eof": True,
                        "independent_from_emotion_ledger": True,
                        "no_emotion_beat_substitution": True,
                        "all_effective_plot_beats_preserved": True,
                        "manual_judgment": "已独立逐行盘清外部动作、信息、控制权和后果。",
                    },
                },
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
                "source_required_sequence": ["公开偏护", "短暂反抗", "希望落空", "关系掉位"],
                "source_must_keep_actions": ["对手抢走位置", "旁观者改变站队"],
                "source_scene_granularity": "先抢位置，再由旁观者确认关系掉位。",
                "source_plot_beats": self.plot_beats("P", "原文情节拍"),
                "source_plot_beat_completion_review": "已逐句复核本桥段，四个有效事件拍全部入账。",
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
                "source_required_sequence": ["公开偏护", "短暂反抗", "希望落空", "关系掉位"],
                "source_must_keep_actions": ["对手抢走位置", "旁观者改变站队"],
                "source_scene_granularity": "先抢位置，再由旁观者确认关系掉位。",
                "source_plot_beats": self.plot_beats("P", "原文情节拍"),
                "target_plot_beats": self.plot_beats("TP", "目标情节拍"),
                "plot_beat_mapping": self.plot_mapping(),
                "plot_granularity_parity_judgment": "四个情节拍按原顺序逐拍迁移，没有漏拍、并拍或降格。",
                "source_emotion_sequence": self.emotion_beats("原文场面"),
                "target_emotion_sequence": self.emotion_beats("动作一", target=True),
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 5,
                "target_peak_beat": 5,
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
        coverage = data["source_subflow_granularity_coverage"][0]
        coverage["target_outline_sections"] = ["1"]
        coverage["coverage_status"] = "adapted"
        coverage["adaptation_boundary"] = "只迁移六类局部表演颗粒，不复制原人物和事件。"
        coverage["manual_judgment"] = "六类颗粒均已分别落到第一节的真实场面原句。"
        for field in GATE.SOURCE_STYLE_GRANULARITY_FIELDS:
            coverage["transferred_style_fields"][field] = {
                "target_outline_evidence": ["动作一"],
                "transfer_method": f"将 {field} 转为目标场面中的动作与句面安排。",
                "surface_copy_rejected": True,
            }
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
            section["scene_units"] = [
                {
                    "scene_id": f"S{section['section_id']}-01",
                    "emotion_beat_ids": [f"E-{index}" for index in range(1, 7)],
                    "plot_beat_ids": [f"TP-{index}" for index in range(1, 5)],
                    "allocated_chars": 1000,
                    "target_chars": 1000,
                    "full_scene_required": True,
                    "summary_only": False,
                    "entry_pressure": "当前人物在公开场合的默认位置被人动了。",
                    "interaction_chain": ["甲先抢位", "乙开口阻拦", "旁观者改变站队"],
                    "turning_action": "原本属于乙的钥匙被亲手交给甲。",
                    "visible_consequence": "乙当场失去了进入原有空间的权利。",
                    "aftershock": "旁观者不再等待乙的意见就继续进行。",
                    "reader_emotion_path": "读者从乙还能阻拦的希望转入公开失位的愤怒。",
                    "outline_evidence": section["outline_evidence"],
                }
            ]
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
                "source_emotion_sequence": self.emotion_beats("原文场面"),
                "target_emotion_sequence": self.emotion_beats(
                    section["outline_evidence"][0], target=True
                ),
                "source_intensity_score": 8,
                "target_intensity_score": 8,
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 5,
                "target_peak_beat": 5,
                "ending_afterpain_equivalent": True,
                "reader_experience_equivalent": True,
                "manual_judgment": "逐拍触发、反刀位置和场末余痛达到同级读者体感。",
                "parity_status": "adapted_equal_intensity",
                "adaptation_boundary": "只迁移情绪顺序和烈度，不复制人物与原句。",
            }
        data["reviewed_by_current_model"] = True
        data["gate_status"] = "passed"
        data["global_review"] = {
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
            "manual_judgment": "每场只压一个不可逆变化，信息延迟到后场。",
        }
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_complete_contract_passes(self) -> None:
        self.assertEqual([], GATE.validate_receipt(self.receipt, self.outline))

    def test_auxiliary_plot_only_bridge_does_not_import_auxiliary_emotions(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        inventory = data["source_bridge_flow_inventory"]
        parity = deepcopy(data["outline_bridge_flow_parity"])
        parity[0].update(
            {
                "emotion_transfer_policy": "plot_mechanism_only",
                "source_emotion_sequence": [],
                "target_emotion_sequence": [],
                "source_reversal_beat": 0,
                "target_reversal_beat": 0,
                "source_peak_beat": 0,
                "target_peak_beat": 0,
                "reader_experience_parity": None,
                "emotion_parity_judgment": "辅助书只供应情节和后果机制，不供应目标稿情绪拍。",
            }
        )
        source_path = str(self.source.resolve())
        errors: list[str] = []
        GATE.validate_bridge_parity(
            parity,
            inventory,
            {"BID-01"},
            {source_path: self.source.read_text(encoding="utf-8")},
            {source_path: {"role": "auxiliary"}},
            ["1", "2"],
            self.outline.read_text(encoding="utf-8"),
            errors,
            strong_emotion_required=True,
        )
        self.assertEqual([], errors)

    def test_primary_bridge_cannot_claim_plot_only_emotion_policy(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["outline_bridge_flow_parity"][0][
            "emotion_transfer_policy"
        ] = "plot_mechanism_only"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("主体桥段不得使用" in error for error in errors))

    def test_global_plot_beat_inventory_confirmation_is_required(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["global_review"]["source_plot_beat_inventory_completed"] = False
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("全部有效情节拍" in error for error in errors))

    def test_missing_primary_subflow_coverage_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["source_subflow_granularity_coverage"] = []
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("必须覆盖主体原文全部 SF" in error for error in errors))

    def test_missing_one_subflow_style_field_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        coverage = data["source_subflow_granularity_coverage"][0]
        del coverage["transferred_style_fields"]["narrator_interjection_and_roughness"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("未迁移颗粒字段" in error for error in errors))

    def test_init_scaffolds_every_primary_catalog_bridge(self) -> None:
        self.catalog.write_text(
            "## BID-01 公开掉位\n\n## BID-02 私域换主\n",
            encoding="utf-8",
        )
        data = GATE.create_receipt("测试", self.outline, [self.source])
        self.assertEqual(
            ["BID-01", "BID-02"],
            [item["bridge_id"] for item in data["source_bridge_flow_inventory"]],
        )
        self.assertEqual(
            ["BID-01", "BID-02"],
            [item["source_bridge_id"] for item in data["outline_bridge_flow_parity"]],
        )

    def test_auxiliary_selection_error_lists_available_bridges(self) -> None:
        auxiliary_root = self.root / "拆文库" / "辅助书"
        auxiliary = auxiliary_root / "原文" / "辅助书.txt"
        auxiliary.parent.mkdir(parents=True)
        auxiliary.write_text("辅助原文", encoding="utf-8")
        auxiliary_catalog = auxiliary_root / "写作资产" / "桥段施工卡.md"
        auxiliary_catalog.parent.mkdir(parents=True)
        auxiliary_catalog.write_text("## BID-03 稀缺资源撤回\n", encoding="utf-8")
        self.write_minimal_plot_ledger(auxiliary, "BID-03")

        data = GATE.create_receipt("测试", self.outline, [self.source, auxiliary])
        path = self.root / "待选择回执.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(path, self.outline)
        self.assertTrue(
            any("必须人工选择" in error and "BID-03" in error for error in errors)
        )

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

    def test_missing_target_plot_beat_blocks(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["outline_bridge_flow_parity"][0]["target_plot_beats"].pop(2)
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("情节拍数必须完全一致" in error for error in errors))

    def test_missing_independent_plot_ledger_blocks_initialization(self) -> None:
        self.plot_ledger.unlink()
        with self.assertRaises(FileNotFoundError):
            GATE.create_receipt("测试", self.outline, [self.source])

    def test_emotion_ids_cannot_be_reused_as_plot_ids(self) -> None:
        ledger = json.loads(self.plot_ledger.read_text(encoding="utf-8"))
        ledger["beats"][0]["beat_id"] = "E-1"
        self.plot_ledger.write_text(
            json.dumps(ledger, ensure_ascii=False), encoding="utf-8"
        )
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["selected_source_originals"][0]["plot_beat_ledger"]["sha256"] = GATE.sha256(
            self.plot_ledger
        )
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("共用 beat_id" in error for error in errors))

    def test_receipt_cannot_invent_plot_inventory(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        data["source_bridge_flow_inventory"][0]["source_plot_beats"][0][
            "action"
        ] = "回执填写者临时编的情节动作"
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("独立全文情节微拍总账" in error for error in errors))

    def test_two_source_plot_beats_cannot_merge_into_one_target(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        mapping = data["outline_bridge_flow_parity"][0]["plot_beat_mapping"]
        mapping[2]["target_beat_id"] = mapping[1]["target_beat_id"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("不能合并到同一个目标情节拍" in error for error in errors))

    def test_actual_source_emotion_beat_cannot_be_dropped(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        target = data["outline_bridge_flow_parity"][0]["target_emotion_sequence"]
        target.pop(4)
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("数量必须一致" in error for error in errors))

    def test_source_action_cannot_be_prefixed_and_reused_as_target_beat(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        parity = data["outline_bridge_flow_parity"][0]
        parity["target_plot_beats"][0]["action"] = (
            "换成新故事：" + parity["source_plot_beats"][0]["action"]
        )
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("不能加前缀或换标题冒充" in error for error in errors))

    def test_target_emotion_trigger_must_move_into_target_world(self) -> None:
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        parity = data["outline_bridge_flow_parity"][0]
        parity["target_emotion_sequence"][0]["trigger"] = parity[
            "source_emotion_sequence"
        ][0]["trigger"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("触发仍与原文相同" in error for error in errors))

    def test_bridge_emotion_membership_must_follow_ledger_bid_ids(self) -> None:
        ledger = json.loads(self.emotion_ledger.read_text(encoding="utf-8"))
        ledger["beats"][0]["bid_ids"] = []
        self.emotion_ledger.write_text(
            json.dumps(ledger, ensure_ascii=False), encoding="utf-8"
        )
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("bid_ids 真实边界" in error for error in errors))

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

    def test_scene_interaction_chain_rejects_generic_placeholder(self) -> None:
        scene = {
            "scene_id": "S1-01",
            "emotion_beat_ids": ["E-001"],
            "plot_beat_ids": ["TP-001"],
            "allocated_chars": 1000,
            "target_chars": 1000,
            "full_scene_required": True,
            "summary_only": False,
            "entry_pressure": "甲把钥匙放到桌上。",
            "interaction_chain": [
                "一方用钥匙施压",
                "另一方用错答或抢物被迫接招",
                "现场以钥匙换手出现可见换权",
            ],
            "turning_action": "乙收走钥匙。",
            "visible_consequence": "甲失去进入权。",
            "aftershock": "门在甲面前关上。",
            "reader_emotion_path": "希望转为失位。",
            "outline_evidence": ["动作一", "动作二"],
        }
        errors = GATE.validate_scene_units(
            [scene], "section[1]", "动作一\n动作二", "1"
        )
        self.assertTrue(any("泛化施压/接招模板" in error for error in errors))

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
        self.write_minimal_plot_ledger(auxiliary, "BID-03")

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
