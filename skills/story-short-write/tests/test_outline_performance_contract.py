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
    def emotion_beats(evidence: str) -> list[dict]:
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
                "evidence": evidence,
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
        self.source.write_text("原文场面", encoding="utf-8")
        self.catalog = self.book_root / "写作资产" / "桥段施工卡.md"
        self.catalog.parent.mkdir(parents=True)
        self.catalog.write_text("## BID-01 公开掉位\n", encoding="utf-8")
        self.subflows = [
            {
                "subflow_id": "SF-01",
                "source_book": "测试书",
                "parent_bridge_id": "BID-01",
                "name": "先抢位置再逼出让位",
                "source_range": "L1-L1",
                "function_tags": ["公开失位"],
                "entry_state": "妻子仍被默认拥有现场决定权。",
                "required_sequence": ["第三者先抢入口", "丈夫随后要求妻子让位"],
                "scene_granularity": "第三者先伸手拿钥匙，妻子按住，丈夫开口后她才松手。",
                "information_delay": "本场只漏出偏护，删名责任压到后场。",
                "control_changes": ["钥匙控制权从妻子转给第三者"],
                "emotion_sequence": ["警觉", "受辱", "反刀"],
                "end_state": "妻子失去默认进入权。",
                "embeddable_after": [],
                "incompatible_with": [],
                "source_evidence": ["原文场面", "原文"],
            },
            {
                "subflow_id": "SF-02",
                "source_book": "测试书",
                "parent_bridge_id": "BID-01",
                "name": "旁观者改口确认掉位",
                "source_range": "L1-L1",
                "function_tags": ["外部秩序"],
                "entry_state": "现场仍等待妻子决定。",
                "required_sequence": ["旁观者先看向妻子", "丈夫表态后旁观者改口"],
                "scene_granularity": "旁观者先等妻子点头，丈夫越过她答应后，众人才转向丈夫。",
                "information_delay": "不解释婚姻全貌，只让外部秩序先完成站队。",
                "control_changes": ["现场决定权从妻子转给丈夫"],
                "emotion_sequence": ["短暂期待", "被越过", "余痛"],
                "end_state": "妻子不再是现场默认主位。",
                "embeddable_after": ["SF-01"],
                "incompatible_with": [],
                "source_evidence": ["原文场面", "原文"],
            },
        ]
        self.subflow_catalog = self.book_root / "写作资产" / "子流程索引.jsonl"
        self.subflow_catalog.write_text(
            "".join(
                json.dumps(entry, ensure_ascii=False) + "\n"
                for entry in self.subflows
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
                "source_emotion_sequence": self.emotion_beats("原文场面"),
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
            section["scene_granularity_failure_guard"] = {
                "not_function_summary": True,
                "not_evidence_list": True,
                "not_result_broadcast_chain": True,
                "not_process_log": True,
                "scene_resistance": "钥匙卡住入口，旁观者改口前先出现阻拦。",
                "external_order_or_bystander_pressure": "旁观者停止等待乙的决定，现场秩序改变。",
                "manual_judgment": "本节有抢位置、阻拦失败和旁观者改口，不是结果播报。",
            }
        data["reviewed_by_current_model"] = True
        data["gate_status"] = "passed"
        data["global_review"] = {
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
            "manual_judgment": "每场只压一个不可逆变化，信息延迟到后场。",
        }
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def granularity_data(self) -> dict:
        old = json.loads(self.receipt.read_text(encoding="utf-8"))
        data = GATE.create_receipt(
            "测试",
            self.outline,
            [self.source],
            source_mode="granularity_only",
        )
        data["global_review"] = old["global_review"]
        data["global_review"]["granularity_transfer_contract_reviewed"] = True
        data["sections"] = old["sections"]
        data["reviewed_by_current_model"] = True
        data["gate_status"] = "passed"
        source_path = str(self.source.resolve())
        source_sha = GATE.sha256(self.source)
        data["granularity_transfer_contract"] = [
            {
                "source_subflow_id": entry["subflow_id"],
                "parent_bridge_id": entry["parent_bridge_id"],
                "source_path": source_path,
                "source_sha256": source_sha,
                "source_required_sequence": entry["required_sequence"],
                "source_scene_granularity": entry["scene_granularity"],
                "source_information_delay": entry["information_delay"],
                "source_control_changes": entry["control_changes"],
                "source_end_state": entry["end_state"],
                "child_flow_mode": "original_constructed",
                "target_scene": f"原创场景{index}",
                "target_scene_causal_chain": "目标人物为保住关系位置先争夺入口，再因错误站队失去决定权。",
                "target_child_flow": [f"目标动作{index}A", f"目标反应{index}B"],
                "anti_functionalization_guard": "动作先由人物欲望触发，不按证据、边界、后果逐项报到。",
                "artificial_friction_guard": "不为过检额外添加均匀卡顿、掉落或误触。",
                "adaptation_boundary": "保留主颗粒完整顺序，不复制原人物、职业、物件和原句。",
                "result_broadcast_chain_guard": "信息分次漏出，人物先争夺控制权，不由众人问答播报结果。",
                "rejected_surface_elements": ["原人物", "原职业", "原物件"],
                "target_outline_sections": [str(index)],
                "target_outline_evidence": ["动作一" if index == 1 else "动作三"],
                "manual_judgment": "目标情节自由构造，但主书颗粒未删步、未合并、未改序。",
            }
            for index, entry in enumerate(self.subflows, start=1)
        ]
        return data

    def test_complete_contract_passes(self) -> None:
        self.assertEqual([], GATE.validate_receipt(self.receipt, self.outline))

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

    def test_granularity_only_allows_original_child_flow_with_full_primary_particles(self) -> None:
        data = self.granularity_data()
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertEqual([], errors)

    def test_granularity_only_missing_primary_subflow_blocks(self) -> None:
        data = self.granularity_data()
        data["granularity_transfer_contract"].pop()
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("主书 SF 缺失" in error for error in errors))

    def test_granularity_only_rejects_summarized_primary_sequence(self) -> None:
        data = self.granularity_data()
        data["granularity_transfer_contract"][0]["source_required_sequence"] = [
            "完成一次公开失位"
        ]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("不得概括、合并或改序" in error for error in errors))

    def test_library_selected_rejects_truncated_auxiliary_subflow(self) -> None:
        auxiliary_root = self.root / "拆文库" / "辅助书"
        auxiliary = auxiliary_root / "原文" / "辅助书.txt"
        auxiliary.parent.mkdir(parents=True)
        auxiliary.write_text("辅助原文场面", encoding="utf-8")
        auxiliary_asset_dir = auxiliary_root / "写作资产"
        auxiliary_asset_dir.mkdir(parents=True)
        (auxiliary_asset_dir / "桥段施工卡.md").write_text(
            "## BID-01 辅助桥\n",
            encoding="utf-8",
        )
        auxiliary_subflow = {
            **self.subflows[0],
            "source_book": "辅助书",
            "required_sequence": ["先封住出口", "再由第三人改口", "最后留下未结清后果"],
            "scene_granularity": "第三人先挡门，关系人抢话失败，旁观者最后改口。",
            "information_delay": "先暴露站队，完整原因留后。",
            "control_changes": ["出口控制权换主", "解释权再次换主"],
            "end_state": "主角带着未结清后果离场。",
        }
        (auxiliary_asset_dir / "子流程索引.jsonl").write_text(
            json.dumps(auxiliary_subflow, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        old = self.granularity_data()
        data = GATE.create_receipt(
            "测试",
            self.outline,
            [self.source, auxiliary],
            source_mode="granularity_only",
        )
        data["global_review"] = old["global_review"]
        data["sections"] = old["sections"]
        data["reviewed_by_current_model"] = True
        data["gate_status"] = "passed"
        data["selected_source_originals"][1]["selected_subflow_ids"] = ["SF-01"]
        data["granularity_transfer_contract"] = old["granularity_transfer_contract"]
        first = data["granularity_transfer_contract"][0]
        first["child_flow_mode"] = "library_selected"
        first["auxiliary_source_path"] = str(auxiliary.resolve())
        first["auxiliary_subflow_id"] = "SF-01"
        first["auxiliary_required_sequence"] = ["先封住出口"]
        first["auxiliary_scene_granularity"] = auxiliary_subflow["scene_granularity"]
        first["auxiliary_information_delay"] = auxiliary_subflow["information_delay"]
        first["auxiliary_control_changes"] = auxiliary_subflow["control_changes"]
        first["auxiliary_end_state"] = auxiliary_subflow["end_state"]
        self.receipt.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        errors = GATE.validate_receipt(self.receipt, self.outline)
        self.assertTrue(any("禁止抽取零件混拼" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
