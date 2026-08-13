from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_emotional_granularity_contract.py"
)
SPEC = importlib.util.spec_from_file_location("emotional_granularity_contract", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class EmotionalGranularityContractTest(unittest.TestCase):
    def test_source_opening_ends_at_first_structural_marker_not_first_bid(self) -> None:
        beats = [
            {"beat_id": "E-001", "end_line": 2, "bid_ids": []},
            {"beat_id": "E-002", "end_line": 5, "bid_ids": []},
            {"beat_id": "E-003", "end_line": 9, "bid_ids": ["BID-01"]},
        ]
        segments = [
            {"kind": "emotion_bearing", "start_line": 1},
            {"kind": "structural_marker", "start_line": 3},
            {"kind": "emotion_bearing", "start_line": 4},
        ]

        regions = GATE.source_beat_regions(beats, segments)

        self.assertEqual("opening", regions["E-001"])
        self.assertEqual("transition", regions["E-002"])
        self.assertEqual("bridge", regions["E-003"])

    def test_narrative_only_retains_is_not_construction_evidence(self) -> None:
        self.assertFalse(GATE.is_construction_evidence("调查结束后只保留他的普通医生岗位。"))
        self.assertTrue(GATE.is_construction_evidence("新稿只保留情绪颗粒，不复制原句。"))

    def test_hurt_object_resolves_first_person_and_composite_names(self) -> None:
        self.assertTrue(GATE.hurt_object_resolves("林知微", "我把号放回窗口。", "第一人称我指林知微。"))
        self.assertTrue(GATE.hurt_object_resolves("沈砚川", "我说你不再是丈夫。", "第二人称你指沈砚川。"))
        self.assertTrue(GATE.hurt_object_resolves("沈砚川与顾晚晴", "沈砚川伸手，顾晚晴先否认。", "目标公开场。"))
        self.assertTrue(GATE.hurt_object_resolves("沈砚川与顾晚晴", "顾晚晴把手覆在他的手背上。", "他的手背所指沈砚川。"))
        self.assertFalse(GATE.hurt_object_resolves("沈砚川与顾晚晴", "顾晚晴按下启动键。", "沈砚川也在现场。"))
        self.assertFalse(GATE.hurt_object_resolves("林知微", "她把号放回窗口。", "没有人物绑定。"))
        self.assertTrue(GATE.hurt_object_resolves("林知微", "她把号放回窗口。", "触发后知微停止补台。"))

    def test_specific_coverage_review_need_not_copy_full_analysis_sentences(self) -> None:
        data = self.prewrite_receipt()
        target = data["section_contracts"][0]["target_outline_beats"][0]
        target["target_evidence_coverage_review"] = "证据同时写出妻子等待、丈夫偏护和席牌换手后的公开掉位。"
        errors, _ = GATE.validate_prewrite_data(
            data, self.source, self.outline, self.source_emotion_ledger
        )
        self.assertFalse(any("未实际覆盖触发" in item or "未实际覆盖关系位移" in item for item in errors))

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "原文.txt"
        self.outline = self.root / "小节大纲.md"
        self.draft = self.root / "正文.md"
        self.source_emotion_ledger = self.root / "全文情绪颗粒总账.json"
        self.source_quotes = [
            "我没想到执行任务会遇见他。",
            "他抓着我的袖子，求我放过那个学生。",
            "我本来以为他会解释。",
            "可他一开口，问的还是那个学生。",
            "我直接把他的手推开，让他闭嘴。",
            "我走出去以后，冷风先把脑子冻住了。",
        ]
        self.source.write_text("".join(self.source_quotes), encoding="utf-8")
        roles = ["仍有期待", "第一次刺痛", "再次等解释", "希望被反打", "动作爆开", "离场余痛"]
        ledger_beats = [
            {
                "beat_id": f"E-{index + 1}",
                "segment_id": "SEG-01",
                "start_line": 1,
                "end_line": 1,
                "role": role,
                "content": f"主体原文中{role}这一拍发生。",
                "trigger": f"主体原文 {role} 的现实触发",
                "relationship_position_change": "丈夫先偏护，妻子的原位被继续夺走。",
                "reader_effect": "读者从短暂期待跌进公开受辱。",
                "narrative_function": "推动本场关系位置继续变化。",
                "intensity": 9 if index == 4 else 7,
                "source_evidence": [self.source_quotes[index]],
                "bid_ids": [] if index == 5 else ["BID-01"],
            }
            for index, role in enumerate(roles)
        ]
        self.ledger_beats = ledger_beats
        self.source_emotion_ledger.write_text(
            json.dumps(
                {
                    "schema_version": GATE.SOURCE_LEDGER_SCHEMA,
                    "source": {
                        "path": str(self.source.resolve()),
                        "sha1": GATE.sha1_file(self.source),
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
                    "source_emotion_candidate_audit": [
                        {
                            "candidate_id": f"EC-{index + 1:03d}",
                            "change_axis": "关系位置与行动冲动变化",
                            "before_state": f"第{index + 1}拍前仍保留原有期待",
                            "after_state": f"第{index + 1}拍后期待或行动冲动发生变化",
                            "source_range": {"start_line": 1, "end_line": 1},
                            "source_evidence": self.source_quotes[index],
                            "decision": "independent_beat",
                            "bound_beat_ids": [beat["beat_id"]],
                            "manual_judgment": "该候选独立改变期待、受伤对象、关系位置或行动冲动。",
                        }
                        for index, beat in enumerate(ledger_beats)
                    ],
                    "beats": ledger_beats,
                    "completeness_review": {
                        "read_start_line": 1,
                        "read_end_line": 1,
                        "all_source_lines_classified": True,
                        "non_bid_beats_preserved": True,
                        "bid_derived_after_full_inventory": True,
                        "reviewed_by_current_model": True,
                        "forward_expectation_scan_completed": True,
                        "reverse_afterpain_scan_completed": True,
                        "all_source_emotion_candidates_adjudicated": True,
                        "automation_used_for_semantic_judgment": False,
                        "split_basis": "每次期待、受伤对象、关系位置、行动冲动或读者预期改变均独立切拍。",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.outline_quotes = [
            "妻子进场时仍等丈夫替自己说一句话。",
            "丈夫先替别人让妻子交出位置。",
            "妻子追问一次，仍给他解释的机会。",
            "丈夫却让她不要在现场计较。",
            "妻子当着众人的面夺回席牌。",
            "掌声中，她想起母亲卖掉的金镯子。",
        ]
        self.outline_evidence = "".join(self.outline_quotes)
        self.outline.write_text(
            "## 1.\n\n"
            f"{''.join(self.outline_quotes[:5])}\n\n"
            "## 尾声\n\n"
            f"{self.outline_quotes[5]}\n",
            encoding="utf-8",
        )
        self.draft.write_text(
            "1.\n\n"
            "我还真以为他会替我说一句话。\n\n"
            "想得挺美。\n\n"
            "他先把席牌按进她手里，我烫伤的手往回缩了一下。\n\n"
            "“别闹。”他伸手来拦。\n\n"
            "我把他的手甩开，当着所有人的面夺回席牌。\n\n"
            "掌声还在响，我只觉得我妈那两只金镯子卖得真便宜。\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_same_file_path_accepts_existing_hardlink_alias(self) -> None:
        alias = self.root / "大纲别名.md"
        alias.hardlink_to(self.outline)

        self.assertTrue(GATE.same_file_path(alias, self.outline))

    def test_outline_regions_accept_numbered_section_with_title(self) -> None:
        regions = GATE.outline_emotion_regions(
            "## 导语\n\n导语拍\n\n## 1. 起事\n\n数字节拍\n\n## 尾声\n\n尾声拍\n"
        )

        self.assertEqual("导语拍", regions["opening"])
        self.assertEqual("数字节拍", regions["section:1"])
        self.assertEqual("尾声拍", regions["epilogue"])

    def prewrite_receipt(self) -> dict:
        data = GATE.create_receipt(
            "测试", self.source, self.source_emotion_ledger
        )
        data = GATE.bind_outline(data, self.outline)
        item = data["section_contracts"][0]
        item.update(
            {
                "status": "passed",
                "source_excerpt": "".join(self.source_quotes[:3]),
                "immediate_subjective_judgment_plan": "允许女主直接承认自己仍等解释，并保留当场冷刺。",
                "untidy_thought_or_emotional_crack_plan": "保留她想得挺美这种不高尚又不工整的自嘲。",
                "embodied_or_object_action_plan": "由烫伤回缩和夺回席牌把受辱推到现实动作。",
                "old_wound_trigger_plan": "让母亲卖金镯子的旧伤被创始人席牌当场触发。",
                "opponent_pressure_plan": "丈夫拦手并要求别闹，继续剥夺妻子的解释权。",
                "loss_of_control_or_equivalent_plan": "女主甩开阻拦并公开夺牌，强度不能降成邮件通知。",
                "source_like_direct_emotion_preserved": True,
                "surface_copy_rejected": True,
                "source_reversal_beat": 4,
                "target_reversal_beat": 4,
                "source_peak_beat": 5,
                "target_peak_beat": 5,
                "turning_point_selection_review": "已逐拍比对期待、关系与行动转折，反刀选定 E-4，峰值选定 E-5，并非按烈度最高值自动猜测。",
                "source_emotion_beat_completion_review": "已逐句通读绑定原文片段，按每次关系位置或读者期待变化切分全部实际情绪拍。",
                "required_plot_beats": [
                    {
                        "beat_id": "P-01",
                        "action": "丈夫先把席牌交给别人",
                        "outline_evidence": self.outline_quotes[1],
                    },
                    {
                        "beat_id": "P-02",
                        "action": "妻子当场夺回席牌",
                        "outline_evidence": self.outline_quotes[4],
                    },
                ],
                "plot_beat_completion_review": "已核对本节分配的全部细纲情节拍，两个动作分别改变席牌控制权且不能合并。",
                "manual_judgment": "本节按主体原文的期待、错答、冷刺和动作爆点组织情绪，不在首稿清洗直接判断。",
            }
        )
        roles = ["仍有期待", "第一次刺痛", "再次等解释", "希望被反打", "动作爆开", "离场余痛"]
        item["source_emotion_beats"] = []
        item["target_outline_beats"] = []
        for index, role in enumerate(roles):
            ledger_beat = self.ledger_beats[index]
            item["source_emotion_beats"].append(
                {
                    "beat_id": f"E-{index + 1}",
                    "role": role,
                    "content": ledger_beat["content"],
                    "trigger": f"主体原文 {role} 的现实触发",
                    "relationship_position_change": "丈夫先偏护，妻子的原位被继续夺走。",
                    "reader_effect": "读者从短暂期待跌进公开受辱。",
                    "narrative_function": ledger_beat["narrative_function"],
                    "intensity": 9 if index == 4 else 7,
                    "source_evidence": [self.source_quotes[index]],
                    "bid_ids": ledger_beat["bid_ids"],
                }
            )
            item["target_outline_beats"].append(
                {
                    "beat_id": f"E-{index + 1}",
                    "role": role,
                    "trigger": f"目标细纲 {role} 的现实触发",
                    "relationship_position_change": "席牌换手后，妻子公开夺回控制权。",
                    "reader_effect": "读者先被偏护刺痛，再看到动作爆开。",
                    "intensity": 9 if index == 4 else 7,
                    "outline_evidence": [self.outline_quotes[index]],
                    "target_outline_region": "epilogue" if index == 5 else "section:1",
                    "target_story_adaptation": "把原文的关系位移改写为席牌换手与女主当众夺回位置的目标故事现场。",
                    "hurt_object": "婚姻位置",
                    "expectation_before": f"第{index + 1}拍前仍期待丈夫维护自己的公开位置",
                    "expectation_after": f"第{index + 1}拍后确认丈夫再次把公开位置让给别人",
                    "action_impulse_before": f"第{index + 1}拍前仍想追问并等丈夫解释",
                    "action_impulse_after": f"第{index + 1}拍后改为收回席牌并停止求证",
                    "equivalence_reason": f"第{index + 1}拍通过席牌换手造成同序关系掉位和行动转向。",
                    "target_evidence_coverage_review": f"已核对完整动作链；触发为目标细纲 {role} 的现实触发，关系位移为席牌换手后，妻子公开夺回控制权。两者均已在独占证据中发生，未压缩原拍。",
                }
            )
        data["reviewed_by_current_model"] = True
        data["prewrite_status"] = "passed"
        return data

    def completed_receipt(self) -> dict:
        data = GATE.bind_draft(self.prewrite_receipt(), self.draft)
        item = data["section_reviews"][0]
        target_quotes = [
            "我还真以为他会替我说一句话。",
            "想得挺美。",
            "他先把席牌按进她手里，我烫伤的手往回缩了一下。",
            "“别闹。”他伸手来拦。",
            "我把他的手甩开，当着所有人的面夺回席牌。",
            "掌声还在响，我只觉得我妈那两只金镯子卖得真便宜。",
        ]
        item.update(
            {
                "status": "passed",
                "immediate_subjective_judgment_quotes": target_quotes[:2],
                "untidy_thought_or_emotional_crack_quotes": [target_quotes[1]],
                "embodied_or_object_action_quotes": target_quotes[2:3],
                "opponent_pressure_quotes": target_quotes[3:4],
                "loss_of_control_or_equivalent_quotes": target_quotes[4:5],
                "old_wound_trigger_review": {
                    "applicable": True,
                    "target_quotes": target_quotes[5:6],
                    "rationale": "席牌被夺让母亲为品牌付出的旧伤在现场回跳。",
                },
                "source_like_direct_emotion_preserved": True,
                "target_not_lower_intensity": True,
                "anti_ai_cleanup_applied_during_first_draft": False,
                "auxiliary_prose_voice_used": False,
                "surface_copy_rejected": True,
                "complete_emotion_beat_review": "已按写前全部 beat_id 逐拍核对正文，每拍均有独占正文证据且没有合并或遗漏。",
                "plot_beat_reviews": [
                    {
                        "beat_id": "P-01",
                        "target_quotes": [target_quotes[2]],
                        "consequence_judgment": "席牌先落入第三人手中，妻子的公开位置被实际夺走。",
                    },
                    {
                        "beat_id": "P-02",
                        "target_quotes": [target_quotes[4]],
                        "consequence_judgment": "妻子公开夺回席牌，现场控制权发生第二次独立变化。",
                    },
                ],
                "complete_plot_beat_review": "已按写前情节 beat_id 逐拍核对正文，两个动作均有独占引句和现实后果。",
                "manual_judgment": "正文保留主体原文式直接判断和不体面破绽，峰值由夺牌动作兑现，没有降成手续播报。",
            }
        )
        source_beats = data["section_contracts"][0]["source_emotion_beats"]
        item["beat_reviews"] = []
        for index, source_beat in enumerate(source_beats):
            item["beat_reviews"].append(
                {
                    "beat_id": source_beat["beat_id"],
                    "role": source_beat["role"],
                    "source_intensity": source_beats[index]["intensity"],
                    "target_intensity": source_beats[index]["intensity"],
                    "target_quotes": [target_quotes[index]],
                    "parity_judgment": f"{source_beat['role']}由本节真实动作和判断承接，读者体感未低于主体原文。",
                }
            )
        data["draft_status"] = "passed"
        return data

    def test_source_excerpt_accepts_crlf_lf_normalization(self) -> None:
        data = self.prewrite_receipt()
        item = data["section_contracts"][0]
        item["source_excerpt"] = item["source_excerpt"].replace("\n", "\r\n")
        errors, _ = GATE.validate_prewrite_data(
            data, self.source, self.outline, self.source_emotion_ledger
        )
        self.assertFalse(any("source_excerpt" in error for error in errors))

    def test_prewrite_passes_in_source_dominant_mode(self) -> None:
        errors, _ = GATE.validate_prewrite_data(
            self.prewrite_receipt(), self.source, self.outline
        )
        self.assertEqual([], errors)

    def test_emotion_v1_ledger_blocks_prewrite(self) -> None:
        ledger = json.loads(self.source_emotion_ledger.read_text(encoding="utf-8"))
        ledger["schema_version"] = "story-short-analyze.full-text-emotion-ledger.v1"
        self.source_emotion_ledger.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_prewrite_data(
            self.prewrite_receipt(), self.source, self.outline, self.source_emotion_ledger
        )
        self.assertTrue(any("schema_version" in item for item in errors))

    def test_emotion_ledger_without_candidate_audit_blocks_prewrite(self) -> None:
        ledger = json.loads(self.source_emotion_ledger.read_text(encoding="utf-8"))
        ledger.pop("source_emotion_candidate_audit")
        self.source_emotion_ledger.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_prewrite_data(
            self.prewrite_receipt(), self.source, self.outline, self.source_emotion_ledger
        )
        self.assertTrue(any("source_emotion_candidate_audit" in item for item in errors))

    def test_prewrite_blocks_lower_target_intensity(self) -> None:
        data = self.prewrite_receipt()
        data["section_contracts"][0]["target_outline_beats"][4]["intensity"] = 8
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("不得降级或抬高" in item for item in errors))

    def test_prewrite_blocks_higher_target_intensity(self) -> None:
        data = self.prewrite_receipt()
        data["section_contracts"][0]["target_outline_beats"][0]["intensity"] = 8
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("不得降级或抬高" in item for item in errors))

    def test_epilogue_beat_must_use_epilogue_region(self) -> None:
        data = self.prewrite_receipt()
        data["section_contracts"][0]["target_outline_beats"][-1][
            "target_outline_region"
        ] = "section:1"
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("尾声拍" in item and "epilogue" in item for item in errors))

    def test_target_semantics_cannot_copy_source_analysis(self) -> None:
        data = self.prewrite_receipt()
        contract = data["section_contracts"][0]
        contract["target_outline_beats"][0]["trigger"] = contract[
            "source_emotion_beats"
        ][0]["trigger"]
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("仍照搬原文分析" in item for item in errors))

    def test_source_contract_must_match_ledger_trigger(self) -> None:
        data = self.prewrite_receipt()
        data["section_contracts"][0]["source_emotion_beats"][0]["trigger"] = "伪造的原文触发"
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("trigger 与全文情绪颗粒总账不一致" in item for item in errors))

    def test_repeated_same_kind_source_beat_cannot_be_dropped(self) -> None:
        data = self.prewrite_receipt()
        contract = data["section_contracts"][0]
        repeated_source = dict(contract["source_emotion_beats"][1])
        repeated_source.update(
            {
                "beat_id": "E-2B",
                "role": "第二次刺痛",
                "source_evidence": [self.source_quotes[2]],
            }
        )
        contract["source_emotion_beats"].insert(2, repeated_source)
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("数量必须一致" in item for item in errors))

    def test_non_bid_epilogue_beat_cannot_be_dropped(self) -> None:
        data = self.prewrite_receipt()
        contract = data["section_contracts"][0]
        contract["source_emotion_beats"].pop()
        contract["target_outline_beats"].pop()
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("禁止只迁移 BID 拍" in item for item in errors))

    def test_prewrite_blocks_first_draft_ai_cleanup(self) -> None:
        data = self.prewrite_receipt()
        data["first_draft_policy"]["anti_ai_cleanup_applied_during_first_draft"] = True
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("anti_ai_cleanup" in item for item in errors))

    def test_apply_section_plan_only_serializes_current_model_sidecar(self) -> None:
        data = GATE.bind_outline(
            GATE.create_receipt("测试", self.source, self.source_emotion_ledger),
            self.outline,
        )
        supplied = data["section_contracts"][:1]
        plan = {
            "reviewed_by_current_model": True,
            "semantic_fields_generated_by_script": False,
            "outline_sha256": GATE.sha256_file(self.outline),
            "manual_judgment": "当前模型逐节回看原文总账和目标细纲后人工完成情绪合同。",
            "section_contracts": supplied,
        }
        merged = GATE.apply_section_plan(data, plan)
        self.assertIs(supplied[0], merged["section_contracts"][0])
        plan["section_contracts"] = supplied + [supplied[0]]
        with self.assertRaisesRegex(ValueError, "保持原序"):
            GATE.apply_section_plan(data, plan)
        plan["section_contracts"] = supplied
        plan["semantic_fields_generated_by_script"] = True
        with self.assertRaisesRegex(ValueError, "禁止由脚本生成"):
            GATE.apply_section_plan(data, plan)

    def test_assemble_section_plan_copies_approved_assets_by_explicit_ids(self) -> None:
        data = GATE.bind_outline(
            GATE.create_receipt("测试", self.source, self.source_emotion_ledger),
            self.outline,
        )
        source_beat = self.ledger_beats[0]
        mapping = {
            "status": "approved",
            "emotions": [{
                "source_beat_id": source_beat["beat_id"],
                "target_outline_region": "第1节",
                "trigger": "妻子进场仍等丈夫替自己说话",
                "relationship_position_change": "丈夫把席牌交给别人后妻子公开掉位",
                "reader_effect": "读者看见丈夫先偏护第三人",
                "target_story_adaptation": "用席牌换手迁移公开掉位",
                "evidence": self.outline_quotes[0],
                "hurt_object": "妻子",
                "expectation_before": "仍期待丈夫维护妻子位置",
                "expectation_after": "确认丈夫先维护第三人位置",
                "action_impulse_before": "继续等待丈夫开口",
                "action_impulse_after": "准备亲手夺回席牌",
                "equivalence_reason": "席牌换手造成同级关系掉位",
                "target_evidence_coverage_review": "证据同时包含妻子等待、丈夫偏护与席牌控制权变化。",
            }],
            "plots": [{
                "target_beat_id": "TP-001",
                "action": "丈夫把席牌交给别人",
                "evidence": self.outline_quotes[1],
            }],
        }
        outline_contract = {
            "gate_status": "passed",
            "sections": [{
                "section_id": "1",
                "source_emotion_parity": {
                    "source_emotion_sequence": [{"beat_id": source_beat["beat_id"]}],
                    "source_reversal_beat": 0,
                    "source_peak_beat": 1,
                },
                "scene_units": [{"plot_beat_ids": ["TP-001"]}],
            }],
        }
        section_plan = {
            "section_id": "1", "status": "passed",
            "emotion_beat_ids": [source_beat["beat_id"]],
            "plot_beat_ids": ["TP-001"],
            "source_reversal_beat": 0, "source_peak_beat": 1,
            "turning_point_selection_review": "峰值选E-1，席牌换手让妻子公开掉位达到本节最高强度。",
            "source_emotion_beat_completion_review": "逐条领取E-1，来源字段和独占证据均按总账原样保留。",
            "plot_beat_completion_review": "逐条领取TP-001，席牌换手动作具有独占细纲证据。",
            "source_like_direct_emotion_preserved": True,
            "surface_copy_rejected": True,
            "manual_judgment": "当前模型确认本节以席牌换手迁移公开掉位，未复制来源表层。",
            **{field: f"当前模型为本节填写的具体{field}现场计划。" for field in GATE.REQUIRED_PLAN_FIELDS},
        }
        plan = {
            "reviewed_by_current_model": True,
            "semantic_fields_generated_by_script": False,
            "outline_sha256": GATE.sha256_file(self.outline),
            "manual_judgment": "当前模型人工完成逐节计划，装配器只按显式ID复制批准资产。",
            "sections": [section_plan],
        }
        ledger = GATE.load_json(self.source_emotion_ledger)
        ledger["beats"] = [source_beat]
        assembled = GATE.assemble_section_plan(
            data, plan, ledger, mapping, outline_contract, self.source
        )
        contract = assembled["section_contracts"][0]
        self.assertEqual([source_beat["beat_id"]], [item["beat_id"] for item in contract["source_emotion_beats"]])
        self.assertEqual(["TP-001"], [item["beat_id"] for item in contract["required_plot_beats"]])

    def test_draft_cannot_drop_required_plot_beat(self) -> None:
        data = self.completed_receipt()
        data["section_reviews"][0]["plot_beat_reviews"].pop()
        errors, _ = GATE.validate_draft_data(data, self.source, self.draft)
        self.assertTrue(any("兑现全部情节拍" in item for item in errors))

    def test_draft_requires_exact_quotes_and_equal_intensity(self) -> None:
        data = self.completed_receipt()
        errors, _ = GATE.validate_draft_data(data, self.source, self.draft)
        self.assertEqual([], errors)
        data["section_reviews"][0]["beat_reviews"][4]["target_intensity"] = 8
        errors, _ = GATE.validate_draft_data(data, self.source, self.draft)
        self.assertTrue(any("正文烈度必须与主体原文精确一致" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
