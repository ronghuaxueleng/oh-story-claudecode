from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_rule_execution_ledger.py"
SPEC = importlib.util.spec_from_file_location("test_section_sentence_workflow", SCRIPT)
assert SPEC and SPEC.loader
LEDGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEDGER)


def review_for(text: str, *, single_chain: bool = True) -> dict:
    sentences = LEDGER.extract_sentences(text)
    return {
        "model_read_entire_region": True,
        "sentence_reviews": [
            {
                "sentence": sentence,
                "subject_or_viewpoint": "当前叙述者",
                "independent_unit_count": 2 if index == 0 else 1,
                "viewpoint_shift": False,
                "single_continuous_chain": single_chain if index == 0 else True,
                "breath_point_judgment": f"第{index + 1}句停顿跟随当前动作链自然落下。",
                "source_voice_basis": f"第{index + 1}句沿用当前来源层的句间节奏与短判断机制。",
                "decision": "keep",
                "judgment": f"第{index + 1}句只承担本句动作和感知，不与其他句共用裁决。",
            }
            for index, sentence in enumerate(sentences)
        ],
        "direct_dialogue_reviews": [],
        "repeated_sentence_reviews": [],
        "cadence_judgment": "当前区域先完成连续动作，再用短判断收住关系变化。",
        "scene_sentence_relation_judgment": "当前区域的现场动作、感知和余波按真实句子依次落下。",
        "template_repetition_judgment": "当前区域没有复用事件句加固定旁白的批量拼接结构。",
        "explanatory_inference_review": "当前区域的判断都有眼前动作和物件后果支撑，没有作者代判。",
        "manual_judgment": "当前区域的活动作、感知和停顿都属于人物此刻正在经历的现场。",
        "region_judgment": "当前区域全部句子已逐项复核，可以冻结后进入下一区域。",
    }


def precommit_review_for(text: str, *, feedback_ids: list[str] | None = None) -> dict:
    sentences = LEDGER.extract_sentences(text)
    return {
        "critic_context_isolated": True,
        "diagnostic_only_first_pass": True,
        "author_intent_ignored": True,
        "model_read_final_candidate": True,
        "rule_refs_considered": ["skill_text_rules:1"],
        "feedback_case_ids_considered": feedback_ids or [],
        "draft_findings": [
            {
                "original_quote": "初稿里不够自然的完整短句",
                "failure_code": "CURRENT_SENTENCE_FAILURE",
                "rule_refs": ["skill_text_rules:1"],
                "diagnosis": "初稿使用概述替代当前人物眼前动作。",
                "rewrite_direction": "改成当前人物实际能看见和执行的动作。",
                "resolved_in_final_quote": sentences[0],
            }
        ],
        "sentence_checks": [
            {
                "sentence": sentence,
                "most_suspicious_span": sentence[:2],
                "read_aloud_verdict": "pass",
                "physical_action_verdict": "not_applicable",
                "pov_attention_verdict": "pass",
                "structured_record_verdict": "not_applicable",
                "failure_codes": [],
                "judgment": f"第{index + 1}句的朗读、动作和人物注意力检查均有文本内依据。",
            }
            for index, sentence in enumerate(sentences)
        ],
        "group_checks": [
            {
                "group_type": "paragraph_transition",
                "quotes": [sentences[0]],
                "weakest_point": "段落转接是否依赖作者解释",
                "verdict": "pass",
                "judgment": "当前组由句内动作和结果直接连接，不需要创作意图或段外解释才能成立。",
            }
        ],
        "final_verdict": "pass",
        "final_judgment": "盲审先记录并修复初稿 weakest link，最终候选逐句与逐组失败码均已清零。",
    }


def design_review_for(
    ledger_data: dict,
    candidate: str,
    artifact: str,
    region_id: str,
    source_refs: list,
) -> dict:
    first_group = ledger_data["groups"][0]
    rule_ref = f"{first_group['rule_id']}:{first_group['cases'][0]['line']}"
    evidence = candidate.strip().splitlines()[-1]
    axes = LEDGER.DESIGN_REVIEW_AXES[artifact]
    return {
        "artifact": artifact,
        "region_id": region_id,
        "critic_context_isolated": True,
        "diagnostic_only_first_pass": True,
        "author_intent_ignored": True,
        "model_read_final_candidate": True,
        "rule_refs_considered": [rule_ref],
        "source_refs_considered": source_refs,
        "draft_findings": [
            {
                "original_quote": "初稿里存在一个需要提前修正的具体设计问题。",
                "failure_code": "CURRENT_DESIGN_FAILURE",
                "rule_refs": [rule_ref],
                "diagnosis": "初稿的事实、动作或来源承载仍需要依靠作者解释才能成立。",
                "rewrite_direction": "改为候选内可直接核验的事实、动作、状态或来源声明。",
                "resolved_in_final_quote": evidence,
            }
        ],
        "axis_checks": {
            axis: {
                "verdict": "pass",
                "evidence_quotes": [evidence],
                "failure_codes": [],
                "judgment": f"{axis} 已按当前候选的事实、动作与来源证据反向复核并清零。",
            }
            for axis in axes
        },
        "final_verdict": "pass",
        "final_judgment": "隔离 critic 已先诊断初稿 weakest link，最终候选的设定或大纲维度均有逐字证据且失败码清零。",
    }


class SectionSentenceWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "测试书"
        (self.project / "写作资产").mkdir(parents=True)
        self.ledger = self.project / "写作资产" / "规则执行台账.json"
        self.draft = self.project / "正文.md"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_ledger(self, expected: list[str], approved: list[dict] | None = None) -> None:
        self.ledger.write_text(
            json.dumps(
                {
                    "draft_review_state": {
                        "expected_regions": expected,
                        "approved_regions": approved or [],
                        "prepared_region": None,
                        "precommit_region": None,
                        "feedback_cases": [],
                        "status": "ready",
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def install_generation_assets(self) -> None:
        original = self.root / "主体.txt"
        original.write_text("第一句很短。\n第二句接住它。", encoding="utf-8")
        source = self.root / "来源成文脑图.json"
        source.write_text(
            json.dumps(
                {
                    "compiled_from": {"original": {"path": str(original)}},
                    "plot_beats": [{"beat_id": "P-001", "action": "动作"}],
                    "emotion_beats": [{"beat_id": "E-001", "content": "情绪"}],
                    "layers": [
                        {
                            "layer_id": "SF-01-L01",
                            "source_range": {"start_line": 1, "end_line": 2},
                            "layer_modes": ["live_scene"],
                            "entry_relation": "从现场进入",
                            "exit_relation": "以短判断退出",
                            "narrative_distance": "近距",
                            "dimension_realization": {
                                "sentence_relation_and_rhythm": {
                                    "status": "active",
                                    "how": "动作后接短判断",
                                },
                                "paragraph_breath_and_cut_points": {
                                    "status": "active",
                                    "how": "两句一断",
                                },
                                "dialogue_misfire_or_avoidance": {
                                    "status": "inactive",
                                    "how": "本层无对白",
                                },
                            },
                            "must_preserve_in_target": ["保留短判断落点"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        target = {
            "gate_status": "passed",
            "source_map": {"path": str(source)},
            "target_nodes": [
                {
                    "target_id": "T-opening-001",
                    "region_id": "opening",
                    "evidence": "目标动作",
                    "source_refs": {},
                }
            ],
            "mappings": {
                "layers": [
                    {
                        "source_id": "SF-01-L01",
                        "target_node_ids": ["T-opening-001"],
                    }
                ],
                "plot_beats": [
                    {"source_id": "P-001", "target_id": "T-opening-001"}
                ],
                "emotion_beats": [
                    {"source_id": "E-001", "target_id": "T-opening-001"}
                ],
            },
        }
        (self.project / "写作资产" / "目标成文脑图.json").write_text(
            json.dumps(target, ensure_ascii=False), encoding="utf-8"
        )
        profile = self.root / "profile.json"
        profile.write_text(
            json.dumps(
                {
                    "prose_style_contract": {
                        "sentence_motion": ["两句事实后接短判断"],
                        "narrator_voice": ["平静冷落锤"],
                        "dialogue_and_character_voice": ["对白允许答偏"],
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.project / "写作资产" / "项目写作配置.json").write_text(
            json.dumps({"profile_path": str(profile)}, ensure_ascii=False),
            encoding="utf-8",
        )

    def install_design_ledger(self) -> dict:
        config = self.project / "写作资产" / "项目写作配置.json"
        config.write_text('{"project_name":"测试书"}', encoding="utf-8")
        data = LEDGER.build_ledger(self.project, ROOT)
        self.ledger.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return data

    def setting_source_refs(self) -> list[dict]:
        config = self.project / "写作资产" / "项目写作配置.json"
        return [{"path": str(config), "sha256": LEDGER.sha256(config)}]

    def approve_setting_design(self) -> None:
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        candidate = "# 《测试书》设定\n\n## 现实规则\n当前人物只能使用已经建立的权限。"
        review = design_review_for(
            data,
            candidate,
            "setting",
            "setting",
            self.setting_source_refs(),
        )
        self.assertEqual(
            [],
            LEDGER.precommit_design_candidate(
                self.ledger, "setting", candidate, review
            ),
        )
        setting = self.project / "设定.md"
        setting.write_text(candidate, encoding="utf-8")
        self.assertEqual(
            [],
            LEDGER.confirm_design_candidate(
                self.ledger, "setting", setting
            ),
        )

    def test_setting_design_critic_runs_before_first_formal_write(self) -> None:
        data = self.install_design_ledger()
        candidate = "# 《测试书》设定\n\n## 现实规则\n当前人物只能使用已经建立的权限。"
        review = design_review_for(
            data,
            candidate,
            "setting",
            "setting",
            self.setting_source_refs(),
        )

        errors = LEDGER.precommit_design_candidate(
            self.ledger, "setting", candidate, review
        )

        self.assertEqual([], errors)
        state = json.loads(self.ledger.read_text(encoding="utf-8"))[
            "design_review_state"
        ]
        self.assertEqual("setting", state["pending"]["artifact"])
        self.assertIsNone(state["setting"])

    def test_setting_design_precommit_blocks_text_already_written(self) -> None:
        data = self.install_design_ledger()
        candidate = "# 《测试书》设定\n\n## 现实规则\n当前人物只能使用已经建立的权限。"
        (self.project / "设定.md").write_text(candidate, encoding="utf-8")
        review = design_review_for(
            data,
            candidate,
            "setting",
            "setting",
            self.setting_source_refs(),
        )

        errors = LEDGER.precommit_design_candidate(
            self.ledger, "setting", candidate, review
        )

        self.assertTrue(any("提前写入" in error for error in errors))

    def test_outline_design_requires_exact_source_refs_and_preflight(self) -> None:
        self.install_design_ledger()
        self.approve_setting_design()
        candidate = (
            "## 导语\n\n"
            "- 入场状态：人物尚未获得目标权限。\n"
            "- 离场状态：人物失去原有位置。\n"
            "- 细拍拆分：当前动作改变现场站位。 "
            "<!-- source-map: P=P-001; E=E-001; SF=SF-01#1; L=SF-01-L01 -->"
        )
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        refs = LEDGER.outline_source_refs(candidate)
        review = design_review_for(data, candidate, "outline", "opening", refs)

        self.assertEqual(
            [],
            LEDGER.precommit_design_candidate(
                self.ledger,
                "outline",
                candidate,
                review,
                region_id="opening",
            ),
        )
        outline = self.project / "小节大纲.md"
        outline.write_text(f"# 测试书大纲\n\n{candidate}", encoding="utf-8")
        blocked = LEDGER.confirm_design_candidate(
            self.ledger,
            "outline",
            outline,
            region_id="opening",
            preflight_passed=False,
        )
        self.assertTrue(any("preflight --allow-partial" in error for error in blocked))
        self.assertEqual(
            [],
            LEDGER.confirm_design_candidate(
                self.ledger,
                "outline",
                outline,
                region_id="opening",
                preflight_passed=True,
            ),
        )

    def test_outline_design_blocks_missing_source_ref_consumption(self) -> None:
        self.install_design_ledger()
        self.approve_setting_design()
        candidate = (
            "## 导语\n\n"
            "- 入场状态：人物尚未获得目标权限。\n"
            "- 离场状态：人物失去原有位置。\n"
            "- 细拍拆分：当前动作改变现场站位。 "
            "<!-- source-map: P=P-001; E=E-001; SF=SF-01#1; L=SF-01-L01 -->"
        )
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        review = design_review_for(
            data, candidate, "outline", "opening", ["P=P-001"]
        )

        errors = LEDGER.precommit_design_candidate(
            self.ledger,
            "outline",
            candidate,
            review,
            region_id="opening",
        )

        self.assertTrue(any("source-map" in error for error in errors))

    def test_refresh_migrates_existing_project_as_legacy_sha_binding(self) -> None:
        data = self.install_design_ledger()
        data.pop("design_review_state")
        self.ledger.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        setting = self.project / "设定.md"
        outline = self.project / "小节大纲.md"
        setting.write_text("既有设定。", encoding="utf-8")
        outline.write_text("## 导语\n\n- 既有区域。", encoding="utf-8")

        LEDGER.refresh_rule_sources(self.ledger)
        migrated = json.loads(self.ledger.read_text(encoding="utf-8"))
        state = migrated["design_review_state"]

        self.assertEqual("legacy_existing", state["mode"])
        self.assertEqual(
            [], LEDGER.validate_design_gate(migrated, self.project, ["opening"])
        )
        setting.write_text("既有设定被改。", encoding="utf-8")
        self.assertTrue(
            any(
                "SHA 已变化" in error
                for error in LEDGER.validate_design_gate(
                    migrated, self.project, ["opening"]
                )
            )
        )

    def test_expected_regions_follow_source_section_count(self) -> None:
        regions, errors = LEDGER.expected_plan_regions(
            [
                {"target_sections": "opening"},
                {"target_sections": "section:1"},
                {"target_sections": "section:2"},
                {"target_sections": "epilogue"},
            ]
        )
        self.assertEqual([], errors)
        self.assertEqual(
            ["opening", "section:1", "section:2", "epilogue"], regions
        )

    def test_prepare_context_supplies_continuous_source_sentence_chain(self) -> None:
        self.write_ledger(["opening"])
        self.install_generation_assets()
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["groups"] = [
            {
                "rule_id": "liveliness_rules",
                "section_generation_plans": [
                    {"target_sections": "opening", "liveliness_plan": {}},
                    {"target_sections": "epilogue", "liveliness_plan": {}},
                ],
            }
        ]
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            packet, errors = LEDGER.prepare_section_context(
                self.ledger, self.project, self.draft
            )
        self.assertEqual([], errors)
        self.assertEqual(["第一句很短。", "第二句接住它。"], packet["source_layers"][0]["source_sentence_chain"])
        self.assertEqual(["两句事实后接短判断"], packet["primary_sentence_motion"])
        state = json.loads(self.ledger.read_text(encoding="utf-8"))["draft_review_state"]
        self.assertEqual("opening", state["prepared_region"]["region_id"])
        self.assertIsNone(state["precommit_region"])

    def test_precommit_requires_candidate_not_already_written(self) -> None:
        self.write_ledger(["opening"])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["groups"] = [
            {
                "rule_id": "skill_text_rules",
                "cases": [{"line": 1, "text": "当前规则要求具体动作与真实文本。"}],
            }
        ]
        data["draft_review_state"]["prepared_region"] = {
            "region_id": "opening",
            "context_sha256": "context",
        }
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.draft.write_text("# 《测试书》\n\n候选已经提前写入。", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.precommit_section_candidate(
                self.ledger,
                self.draft,
                "opening",
                "这是最终候选文本。",
                precommit_review_for("这是最终候选文本。"),
            )
        self.assertTrue(any("不得提前落盘" in error for error in errors))

    def test_precommit_persists_final_candidate_hash(self) -> None:
        self.write_ledger(["opening"])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["groups"] = [
            {
                "rule_id": "skill_text_rules",
                "cases": [{"line": 1, "text": "当前规则要求具体动作与真实文本。"}],
            }
        ]
        data["draft_review_state"]["prepared_region"] = {
            "region_id": "opening",
            "context_sha256": "context",
        }
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        candidate = "这是最终候选文本。"
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.precommit_section_candidate(
                self.ledger,
                self.draft,
                "opening",
                candidate,
                precommit_review_for(candidate),
            )
        self.assertEqual([], errors)
        state = json.loads(self.ledger.read_text(encoding="utf-8"))["draft_review_state"]
        self.assertEqual(
            LEDGER.text_sha256(candidate), state["precommit_region"]["candidate_sha256"]
        )

    def test_precommit_must_consume_all_project_feedback(self) -> None:
        candidate = "这是最终候选文本。"
        ledger_data = {
            "groups": [
                {
                    "rule_id": "skill_text_rules",
                    "cases": [{"line": 1, "text": "当前规则要求具体动作与真实文本。"}],
                }
            ],
            "draft_review_state": {
                "feedback_cases": [{"feedback_id": LEDGER.text_sha256(candidate)}]
            },
        }
        errors = LEDGER.validate_precommit_review(
            precommit_review_for(candidate), candidate, ledger_data
        )
        self.assertTrue(any("feedback_case_ids_considered" in error for error in errors))

    def test_record_feedback_uses_content_derived_unique_ids(self) -> None:
        self.write_ledger(["opening"])
        first_payload = {
            "source_region": "opening",
            "original_quote": "第一条待纠正的句子。",
            "issue": "人物不会这样观察眼前记录。",
            "preferred_direction": "先写人物实际看见的字段和值。",
        }
        second_payload = {
            **first_payload,
            "original_quote": "另一条待纠正的句子。",
        }

        first_id = LEDGER.record_feedback_case(self.ledger, first_payload)
        duplicate_id = LEDGER.record_feedback_case(self.ledger, first_payload)
        second_id = LEDGER.record_feedback_case(self.ledger, second_payload)

        self.assertEqual(first_id, duplicate_id)
        self.assertNotEqual(first_id, second_id)
        self.assertTrue(first_id.startswith("feedback-"))
        cases = json.loads(self.ledger.read_text(encoding="utf-8"))[
            "draft_review_state"
        ]["feedback_cases"]
        self.assertEqual(2, len(cases))

    def test_prepare_blocks_when_draft_contains_unapproved_future_section(self) -> None:
        self.write_ledger(["opening", "section:1"])
        self.draft.write_text("# 《测试书》\n\n导语。\n\n1.\n\n第一节。", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            _, errors = LEDGER.prepare_section_context(
                self.ledger, self.project, self.draft
            )
        self.assertTrue(any("只能包含已通过区域" in error for error in errors))

    def test_confirm_requires_generation_context(self) -> None:
        self.write_ledger(["opening"])
        self.draft.write_text("# 《测试书》\n\n这是导语。", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.apply_section_review(
                self.ledger,
                self.draft,
                "opening",
                review_for("这是导语。"),
            )
        self.assertTrue(any("prepare-section" in error for error in errors))

    def test_confirm_requires_every_real_sentence(self) -> None:
        self.write_ledger(["opening"])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["draft_review_state"]["prepared_region"] = {
            "region_id": "opening",
            "context_sha256": "context",
        }
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.draft.write_text("# 《测试书》\n\n第一句。第二句。", encoding="utf-8")
        review = review_for("第一句。")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.apply_section_review(
                self.ledger, self.draft, "opening", review
            )
        self.assertTrue(any("全部真实句子" in error for error in errors))

    def test_confirm_requires_matching_precommit_hash(self) -> None:
        text = "这是导语。"
        self.write_ledger(["opening"])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["draft_review_state"]["prepared_region"] = {
            "region_id": "opening",
            "context_sha256": "context",
        }
        data["draft_review_state"]["precommit_region"] = {
            "region_id": "opening",
            "candidate_sha256": LEDGER.text_sha256("另一版导语。"),
            "review": {},
        }
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.draft.write_text(f"# 《测试书》\n\n{text}", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.apply_section_review(
                self.ledger, self.draft, "opening", review_for(text)
            )
        self.assertTrue(any("precommit 最终候选 SHA" in error for error in errors))

    def test_confirm_passes_after_matching_precommit(self) -> None:
        text = "这是导语。"
        self.write_ledger(["opening"])
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["draft_review_state"]["prepared_region"] = {
            "region_id": "opening",
            "context_sha256": "context",
        }
        data["draft_review_state"]["precommit_region"] = {
            "region_id": "opening",
            "candidate_sha256": LEDGER.text_sha256(text),
            "review": {},
        }
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.draft.write_text(f"# 《测试书》\n\n{text}", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.apply_section_review(
                self.ledger, self.draft, "opening", review_for(text)
            )
        self.assertEqual([], errors)
        state = json.loads(self.ledger.read_text(encoding="utf-8"))["draft_review_state"]
        self.assertIsNone(state["precommit_region"])
        self.assertEqual("opening", state["approved_regions"][0]["region_id"])

    def test_legal_single_chain_long_sentence_can_pass_human_review(self) -> None:
        text = "我沿着栏杆摸过去，掌心先碰到雨水，又碰到她留下的那道划痕。"
        review = review_for(text, single_chain=True)
        errors = LEDGER.validate_region_review(review, text, "", [])
        self.assertEqual([], errors)

    def test_multiple_independent_units_cannot_be_kept_as_one_sentence(self) -> None:
        text = "我关上门，另一个人接了电话，门外的人从走廊尽头笑起来。"
        review = review_for(text, single_chain=False)
        errors = LEDGER.validate_region_review(review, text, "", [])
        self.assertTrue(any("多个独立单元" in error for error in errors))

    def test_repeated_sentence_requires_explicit_review(self) -> None:
        text = "她没有看我。"
        review = review_for(text)
        errors = LEDGER.validate_region_review(
            review, text, "上一节。她没有看我。", []
        )
        self.assertTrue(any("repeated_sentence_reviews" in error for error in errors))

    def test_approved_region_hash_is_frozen(self) -> None:
        original = "原导语。"
        approved = [
            {
                "region_id": "opening",
                "content_sha256": LEDGER.text_sha256(original),
                "review": review_for(original),
            }
        ]
        self.write_ledger(["opening", "section:1"], approved)
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["draft_review_state"]["prepared_region"] = {
            "region_id": "section:1",
            "context_sha256": "context",
        }
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.draft.write_text("# 《测试书》\n\n被改过的导语。\n\n1.\n\n第一节。", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.apply_section_review(
                self.ledger,
                self.draft,
                "section:1",
                review_for("第一节。"),
            )
        self.assertTrue(any("文本 SHA 已变化" in error for error in errors))

    def test_reconfirm_latest_approved_region_updates_hash(self) -> None:
        old = "旧句。"
        new = "更新后的自然句。"
        approved = [
            {
                "region_id": "opening",
                "content_sha256": LEDGER.text_sha256(old),
                "generation_context_sha256": "context",
                "review": review_for(old),
            }
        ]
        self.write_ledger(["opening", "section:1"], approved)
        self.draft.write_text(f"# 《测试书》\n\n{new}", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.reconfirm_approved_section(
                self.ledger, self.draft, "opening", review_for(new)
            )
        self.assertEqual([], errors)
        state = json.loads(self.ledger.read_text(encoding="utf-8"))["draft_review_state"]
        self.assertEqual(
            LEDGER.text_sha256(new), state["approved_regions"][0]["content_sha256"]
        )

    def test_reconfirm_rejects_non_latest_region(self) -> None:
        opening = "导语。"
        section = "第一节。"
        approved = [
            {
                "region_id": "opening",
                "content_sha256": LEDGER.text_sha256(opening),
                "generation_context_sha256": "context-opening",
                "review": review_for(opening),
            },
            {
                "region_id": "section:1",
                "content_sha256": LEDGER.text_sha256(section),
                "generation_context_sha256": "context-section",
                "review": review_for(section),
            },
        ]
        self.write_ledger(["opening", "section:1"], approved)
        self.draft.write_text(
            f"# 《测试书》\n\n{opening}\n\n1.\n\n{section}", encoding="utf-8"
        )
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.reconfirm_approved_section(
                self.ledger, self.draft, "opening", review_for(opening)
            )
        self.assertTrue(any("只允许最新已通过区域" in error for error in errors))

    def test_final_draft_requires_every_region_review(self) -> None:
        self.write_ledger(["opening", "section:1"])
        self.draft.write_text("# 《测试书》\n\n导语。\n\n1.\n\n第一节。", encoding="utf-8")
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.validate_draft_review_state(
                self.ledger, self.draft, require_complete=True
            )
        self.assertTrue(any("尚未完成" in error for error in errors))

    def test_complete_reviewed_draft_passes_final_state(self) -> None:
        opening = "导语。"
        section = "第一节。"
        approved = [
            {
                "region_id": "opening",
                "content_sha256": LEDGER.text_sha256(opening),
                "generation_context_sha256": "context-opening",
                "review": review_for(opening),
            },
            {
                "region_id": "section:1",
                "content_sha256": LEDGER.text_sha256(section),
                "generation_context_sha256": "context-section-1",
                "review": review_for(section),
            },
        ]
        self.write_ledger(["opening", "section:1"], approved)
        data = json.loads(self.ledger.read_text(encoding="utf-8"))
        data["draft_review_state"]["status"] = "passed"
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.draft.write_text(
            "# 《测试书》\n\n导语。\n\n1.\n\n第一节。", encoding="utf-8"
        )
        with mock.patch.object(LEDGER, "validate_prewrite_ledger", return_value=[]):
            errors = LEDGER.validate_draft_review_state(
                self.ledger, self.draft, require_complete=True
            )
        self.assertEqual([], errors)


class WeakestLinkReviewTests(unittest.TestCase):
    def clean_review(self):
        candidate = "我把钥匙放到桌上。"
        review = precommit_review_for(candidate)
        review["draft_findings"] = []
        review["weakest_link_review"] = {
            "evidence_quotes": [candidate],
            "rule_refs": ["skill_text_rules:1"],
            "risk_considered": "钥匙是否被错误当成门禁授权，造成物件与权限混同。",
            "judgment": "候选只写叙述者将钥匙放在桌面，没有声称钥匙交付会自动解除门禁，动作对象与实际落点一致，无须增加权限叙述。",
            "verdict": "pass", "failure_codes": [], "no_rewrite_needed": True,
        }
        ledger = {"groups": [{"rule_id": "skill_text_rules", "cases": [{"line": 1}]}],
                  "draft_review_state": {"feedback_cases": []}}
        return candidate, review, ledger

    def test_clean_candidate_requires_no_fabricated_rewrite(self):
        candidate, review, ledger = self.clean_review()
        self.assertEqual([], LEDGER.validate_precommit_review(review, candidate, ledger))

    def test_empty_findings_without_evidence_still_block(self):
        candidate, review, ledger = self.clean_review()
        review.pop("weakest_link_review")
        self.assertTrue(LEDGER.validate_precommit_review(review, candidate, ledger))

    def test_weakest_link_requires_current_quote_and_real_rule(self):
        candidate, review, ledger = self.clean_review()
        review["weakest_link_review"]["evidence_quotes"] = ["未出现的句子"]
        review["weakest_link_review"]["rule_refs"] = ["unknown:999"]
        errors = LEDGER.validate_precommit_review(review, candidate, ledger)
        self.assertTrue(any("逐字" in error for error in errors))
        self.assertTrue(any("真实规则" in error for error in errors))

    def test_remaining_failure_cannot_be_hidden_in_clean_review(self):
        candidate, review, ledger = self.clean_review()
        review["weakest_link_review"]["failure_codes"] = ["REAL_FAILURE"]
        self.assertTrue(LEDGER.validate_precommit_review(review, candidate, ledger))

    def test_clean_design_still_requires_every_axis_to_pass(self):
        candidate, prose_review, ledger = self.clean_review()
        review = design_review_for(ledger, candidate, "setting", "setting", [
            {"path": str(SCRIPT), "sha256": LEDGER.sha256(SCRIPT)}
        ])
        review["draft_findings"] = []
        review["weakest_link_review"] = prose_review["weakest_link_review"]
        self.assertEqual([], LEDGER.validate_design_critic_review(
            review, candidate, ledger, "setting", "setting"
        ))
        review["axis_checks"]["fact_and_permission"]["failure_codes"] = ["UNRESOLVED"]
        self.assertTrue(LEDGER.validate_design_critic_review(
            review, candidate, ledger, "setting", "setting"
        ))


class SourceLayerPlanningTests(unittest.TestCase):
    def test_packet_mode_uses_outline_without_future_prose_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            ledger = project / "写作资产" / "规则执行台账.json"
            (project / "小节大纲.md").write_text(
                "## 导语\n\n## 1.\n\n## 2.\n\n## 尾声\n", encoding="utf-8"
            )
            data = {"groups": [{"rule_id": "liveliness_rules", "planning_policy": "source_layer_packet"}]}
            regions, errors = LEDGER.ledger_plan_regions(data, ledger)
            self.assertEqual([], errors)
            self.assertEqual(["opening", "section:1", "section:2", "epilogue"], regions)

    def test_packet_mode_rejects_missing_outline(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "写作资产" / "规则执行台账.json"
            data = {"groups": [{"rule_id": "liveliness_rules", "planning_policy": "source_layer_packet"}]}
            _, errors = LEDGER.ledger_plan_regions(data, ledger)
            self.assertTrue(errors)

    def test_packet_mode_rejects_skipped_region(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "小节大纲.md").write_text("## 导语\n## 2.\n## 尾声\n", encoding="utf-8")
            data = {"groups": [{"rule_id": "liveliness_rules", "planning_policy": "source_layer_packet"}]}
            _, errors = LEDGER.ledger_plan_regions(data, project / "写作资产" / "规则执行台账.json")
            self.assertTrue(errors)

    def test_legacy_plans_remain_readable(self):
        data = {"groups": [{"rule_id": "liveliness_rules", "section_generation_plans": [
            {"target_sections": region} for region in ("opening", "section:1", "epilogue")
        ]}]}
        regions, errors = LEDGER.ledger_plan_regions(data, Path("unused.json"))
        self.assertEqual([], errors)
        self.assertEqual(["opening", "section:1", "epilogue"], regions)


class CheckpointReviewPolicyTest(unittest.TestCase):
    def evidence_for(self, project, stage="outline_complete"):
        source = project / "source.txt"
        source.write_text("The owner gives back the key. The scene ends at the doorway.", encoding="utf-8")
        config = project / "写作资产/项目写作配置.json"
        config.write_text(json.dumps({"primary": {"original_path": str(source)}}), encoding="utf-8")
        target = "小节大纲.md" if stage == "outline_complete" else "正文.md"
        content = (project / target).read_text(encoding="utf-8")
        order = (LEDGER.split_outline_regions(content)[1] if stage == "outline_complete"
                 else LEDGER.split_draft_regions(content)[1])

        def ref(name, quote):
            return {"path": name, "sha256": LEDGER.sha256(project / name), "quote": quote}

        comparisons = []
        for kind in ("setting_consistency", "state_continuity", "beat_function", "layer_boundary", "ending_payoff"):
            other = (ref("设定.md", "当前设定事实。") if kind in {"setting_consistency", "ending_payoff"}
                     else ref(target, "离场后果。") if kind == "state_continuity"
                     else ref(str(source), "The owner gives back the key."))
            comparisons.append({"kind": kind, "evidence": [ref(target, "人物交还钥匙。"), other],
                                 "verdict": "pass", "judgment": "人物交还钥匙之后失去进入原住处的手段，前后位置和权限连续，没有把结局写成未经触发的跳转。"})
        return {"evidence_contract_version": 1, "reviewed_regions": order, "comparisons": comparisons}

    def test_record_checkpoint_requires_independent_current_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "写作资产").mkdir()
            path = project / "写作资产" / "规则执行台账.json"
            setting = "当前设定事实。"
            outline = "## 导语\n开场事实。\n## 1.\n人物交还钥匙。\n## 尾声\n离场后果。"
            (project / "设定.md").write_text(setting, encoding="utf-8")
            (project / "小节大纲.md").write_text(outline, encoding="utf-8")
            (project / "写作资产/项目写作配置.json").write_text("{}", encoding="utf-8")
            regions, order, _ = LEDGER.split_outline_regions(outline)
            data = {"review_policy": {"mode": "checkpoint"}, "design_review_state": {
                "mode": "enforced", "pending": None,
                "setting": {"content_sha256": LEDGER.text_sha256(setting)},
                "outline_regions": [{"region_id": key, "content_sha256": LEDGER.text_sha256(regions[key])} for key in order],
            }}
            path.write_text(json.dumps(data), encoding="utf-8")
            review = {
                "review_mode": "independent", "critic_context_isolated": True,
                "model_read_final_candidate": True, "final_verdict": "pass", "unresolved_findings": [],
                "bindings": LEDGER.checkpoint_bindings(project, "outline_complete"),
                "axis_checks": {name: {"verdict": "pass", "evidence_quotes": ["人物交还钥匙。"],
                    "judgment": "人物交还钥匙之后失去进入原住处的手段，前后位置和权限连续，没有把结局写成未经触发的跳转。"}
                    for name in ("causal_continuity", "source_fidelity", "character_and_permission", "voice_and_payoff")},
            }
            self.assertTrue(LEDGER.record_checkpoint(path, "outline_complete", review))
            review.update(self.evidence_for(project))
            review["bindings"] = LEDGER.checkpoint_bindings(project, "outline_complete")
            self.assertEqual([], LEDGER.record_checkpoint(path, "outline_complete", review))
            self.assertEqual([], LEDGER.validate_design_gate(LEDGER.load(path), project, order))
            review.update(review_mode="self_check", critic_context_isolated=False)
            self.assertTrue(LEDGER.record_checkpoint(path, "outline_complete", review))
            review.update(review_mode="independent", critic_context_isolated=True)
            review["axis_checks"]["causal_continuity"]["evidence_quotes"] = ["不存在的引句"]
            self.assertTrue(LEDGER.record_checkpoint(path, "outline_complete", review))

    def test_self_check_is_honest_and_opt_in(self):
        review = {"review_mode": "self_check", "critic_context_isolated": False}
        data = {"review_policy": {"mode": "checkpoint"}}
        self.assertEqual([], LEDGER.validate_review_identity(review, data))
        self.assertTrue(LEDGER.validate_review_identity(review, {}))
        self.assertTrue(LEDGER.validate_review_identity(review, data, setting=True))
        review["critic_context_isolated"] = True
        self.assertTrue(LEDGER.validate_review_identity(review, data))

    def test_checkpoint_comparisons_reject_missing_stale_and_unbound_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "写作资产").mkdir()
            (project / "设定.md").write_text("当前设定事实。", encoding="utf-8")
            (project / "小节大纲.md").write_text("## 导语\n人物交还钥匙。\n## 1.\n离场后果。\n## 尾声\n结束。", encoding="utf-8")
            (project / "正文.md").write_text("# 《测试》\n人物交还钥匙。\n\n1.\n离场后果。", encoding="utf-8")
            (project / "写作资产/目标成文脑图.json").write_text("{}", encoding="utf-8")
            for stage in ("outline_complete", "draft_complete"):
                review = self.evidence_for(project, stage)
                self.assertEqual([], LEDGER.validate_checkpoint_evidence(review, project, stage))
                for mutation in ("missing_setting", "stale", "unknown", "missing_region", "same_quote", "missing_source", "state_from_setting", "state_reversed"):
                    with self.subTest(stage=stage, mutation=mutation):
                        broken = json.loads(json.dumps(review))
                        if mutation == "missing_setting":
                            broken["comparisons"][0]["evidence"][1] = broken["comparisons"][1]["evidence"][1]
                        elif mutation == "stale":
                            broken["comparisons"][0]["evidence"][1]["sha256"] = "old"
                        elif mutation == "unknown":
                            broken["comparisons"][0]["evidence"][1]["path"] = "/unrelated.txt"
                        elif mutation == "missing_region":
                            broken["reviewed_regions"].pop()
                        elif mutation == "same_quote":
                            broken["comparisons"][1]["evidence"][1] = broken["comparisons"][1]["evidence"][0]
                        elif mutation == "state_from_setting":
                            broken["comparisons"][1]["evidence"][1] = broken["comparisons"][0]["evidence"][1]
                        elif mutation == "state_reversed":
                            broken["comparisons"][1]["evidence"].reverse()
                        else:
                            broken["comparisons"][2]["evidence"][1] = broken["comparisons"][0]["evidence"][1]
                        self.assertTrue(LEDGER.validate_checkpoint_evidence(broken, project, stage))
                (project / "source.txt").write_text("Changed source", encoding="utf-8")
                self.assertTrue(LEDGER.validate_checkpoint_evidence(review, project, stage))

    def test_self_check_keeps_sentence_and_rule_gates(self):
        data = {"review_policy": {"mode": "checkpoint"}, "groups": [
            {"rule_id": "skill_text_rules", "cases": [{"line": 1}]}
        ]}
        text = "我把钥匙放在桌上。"
        review = precommit_review_for(text)
        review.update(review_mode="self_check", critic_context_isolated=False)
        self.assertEqual([], LEDGER.validate_precommit_review(review, text, data))
        review["sentence_checks"] = []
        self.assertTrue(LEDGER.validate_precommit_review(review, text, data))
        review = precommit_review_for(text)
        review.update(review_mode="self_check", critic_context_isolated=False, rule_refs_considered=["missing:1"])
        self.assertTrue(LEDGER.validate_precommit_review(review, text, data))

    def test_policy_migration_preserves_frozen_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            frozen = {"setting": {"content_sha256": "setting-hash"}, "outline_regions": [
                {"region_id": "opening", "content_sha256": "outline-hash"}
            ]}
            data = {"design_review_state": frozen, "draft_review_state": {"approved_regions": []}}
            path.write_text(json.dumps(data), encoding="utf-8")
            LEDGER.set_review_policy(path, "checkpoint", "减少逐节审核", "保留节点审核")
            updated = LEDGER.load(path)
            self.assertEqual(frozen, updated["design_review_state"])
            self.assertEqual("per_region", updated["review_policy_history"][0]["previous_mode"])
            updated["design_review_state"]["pending"] = {"candidate_sha256": "pending"}
            path.write_text(json.dumps(updated), encoding="utf-8")
            with self.assertRaises(ValueError):
                LEDGER.set_review_policy(path, "per_region", "恢复", "恢复")

    def test_checkpoint_missing_and_changed_binding_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "写作资产").mkdir()
            for name in ("设定.md", "小节大纲.md", "写作资产/项目写作配置.json"):
                (project / name).write_text("original", encoding="utf-8")
            data = {"review_policy": {"mode": "checkpoint"}}
            self.assertTrue(LEDGER.validate_checkpoint(data, project, "outline_complete"))
            data["review_checkpoints"] = {"outline_complete": {
                "bindings": LEDGER.checkpoint_bindings(project, "outline_complete")
            }}
            self.assertTrue(LEDGER.validate_checkpoint(data, project, "outline_complete"))
            (project / "小节大纲.md").write_text("changed", encoding="utf-8")
            self.assertTrue(LEDGER.validate_checkpoint(data, project, "outline_complete"))
            self.assertEqual([], LEDGER.validate_checkpoint({}, project, "outline_complete"))

    def test_complete_gates_require_checkpoint(self):
        data = {"review_policy": {"mode": "checkpoint"}, "design_review_state": {"mode": "enforced"}}
        errors = LEDGER.validate_design_gate(data, Path("nonexistent-project"), [])
        self.assertTrue(any("outline_complete" in error for error in errors))
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "写作资产").mkdir()
            path = project / "写作资产" / "规则执行台账.json"
            draft = project / "正文.md"
            draft.write_text("我把钥匙放下。", encoding="utf-8")
            regions, order = LEDGER.split_draft_regions(draft.read_text(encoding="utf-8"))
            data["draft_review_state"] = {"expected_regions": order, "status": "passed", "approved_regions": [
                {"region_id": key, "content_sha256": LEDGER.text_sha256(value), "generation_context_sha256": "context"}
                for key, value in regions.items()
            ]}
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = LEDGER.validate_draft_review_state(path, draft, require_complete=True, validate_prewrite_first=False)
            self.assertTrue(any("draft_complete" in error for error in errors))
            self.assertEqual([], LEDGER.validate_draft_review_state(path, draft, require_complete=False, validate_prewrite_first=False))


if __name__ == "__main__":
    unittest.main()
