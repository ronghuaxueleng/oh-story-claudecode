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
        roles = ["情绪进入点", "受辱或刺痛", "短暂希望或反抗", "反刀", "场末余痛"]
        return [
            {
                "role": role,
                "trigger": f"{role}的具体触发",
                "relationship_position_change": f"{role}改变关系位置",
                "reader_effect": f"读者在{role}感到关系恶化",
                "intensity": 8,
                "evidence": evidence,
            }
            for role in roles
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
        self.outline.write_text("## 1. 起事\n\n动作一\n动作二\n", encoding="utf-8")
        source_root = self.root / "拆文库" / "测试书"
        self.source_original = source_root / "原文" / "原文.txt"
        self.source_original.parent.mkdir(parents=True)
        self.source_original.write_text("原文场面", encoding="utf-8")
        bridge_catalog = source_root / "写作资产" / "桥段施工卡.md"
        bridge_catalog.parent.mkdir(parents=True)
        bridge_catalog.write_text("## BID-01 公开掉位\n", encoding="utf-8")
        for name in (
            "writing",
            "source",
            "ledger",
            "opening",
            "outline_contract",
            "profile",
            "sequence",
            "setting_sequence",
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
            "outline_bridge_flow_parity_reviewed_before_draft": True,
            "relationship_legibility_reviewed_before_draft": True,
            "professional_shell_translation_reviewed_before_draft": True,
            "source_emotion_flow_parity_reviewed_before_draft": True,
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
                "source_emotion_sequence": self.emotion_beats("原文场面"),
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
                    "source_emotion_sequence": self.emotion_beats("原文场面"),
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
                "scene_granularity_failure_guard": {
                    "not_function_summary": True,
                    "not_evidence_list": True,
                    "not_result_broadcast_chain": True,
                    "not_process_log": True,
                    "scene_resistance": "钥匙卡住入口，旁观者改口前先出现阻拦。",
                    "external_order_or_bystander_pressure": "旁观者停止等待乙决定，现场秩序改变。",
                    "manual_judgment": "本节有抢位置、阻拦失败和旁观者改口，不是结果播报。",
                },
                "forbidden_items": ["不提前解释", "不连续报账"],
                "outline_evidence": ["动作一", "动作二"],
                "manual_judgment": "本场是连续互动，不是清单。",
            }
        )
        payload["reviewed_by_current_model"] = True
        payload["gate_status"] = "passed"
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
