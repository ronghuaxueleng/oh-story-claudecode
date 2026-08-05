from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_prose_granularity_contract.py"
)
SPEC = importlib.util.spec_from_file_location("prose_granularity_contract", SCRIPT_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ProseGranularityContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "拆文库" / "测试书" / "原文" / "原文.txt"
        self.draft = self.root / "正文.md"
        self.outline = self.root / "小节大纲.md"
        self.receipt = self.root / "全文文字颗粒度契约回执.json"
        self.source_text = (
            "我没想到今天会在这里遇见他。他伸手拦我，我直接把他的手推了回去。"
            "他问我是不是非要这样。我不知道我哪样了？难道站在这里也是我的错？"
            "我懒得和他争，转身去拿桌上的钥匙。钥匙没拿到，倒先听见她哭了。"
            "有意思。明明从头到尾我一句话都没说，现在倒像是我欺负了人。"
            "最后我把门关上。外面还有人在说话，我没再听，反正也不重要了。"
        )
        self.source.parent.mkdir(parents=True)
        self.source.write_text(self.source_text, encoding="utf-8")
        self.subflow_catalog = self.source.parent.parent / "写作资产" / "子流程索引.jsonl"
        self.subflow_catalog.parent.mkdir(parents=True)
        source_style = {
            field: {
                "analysis": f"{field} 的主体原文局部颗粒分析。",
                "source_evidence": ["我没想到今天会在这里遇见他。", "有意思。"],
            }
            for field in GATE.SOURCE_STYLE_GRANULARITY_FIELDS
        }
        self.subflow_catalog.write_text(
            json.dumps(
                {
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "source_range": "L1-L5",
                    "source_style_granularity": source_style,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        self.draft.write_text(
            "# 测试\n\n1.\n\n我没想到来取东西会撞见他们。\n\n他伸手拦我，我把钥匙收了回来。\n\n2.\n\n她先哭了。\n\n有意思，我还什么都没问。\n",
            encoding="utf-8",
        )
        self.outline.write_text(
            "## 1. 撞见\n\n取东西时撞见两人，先收回钥匙。\n\n"
            "## 2. 关门\n\n对方用哭回避，女主拒绝解释并关门。\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def completed_receipt(self, include_draft: bool = True) -> dict:
        receipt = GATE.create_receipt("测试", self.source)
        receipt = GATE.bind_outline(receipt, self.outline)
        receipt["reviewed_by_current_model"] = True
        receipt["prewrite_status"] = "passed"
        long_quotes = [
            self.source_text[:80],
            self.source_text[20:110],
            self.source_text[50:150],
            self.source_text[80:180],
            self.source_text[110:],
        ]
        purposes = ["开口", "高压", "对白", "日常", "收口"]
        receipt["source_baseline"]["continuous_excerpts"] = [
            {
                "quote": quote,
                "purpose": purpose,
                "language_judgment": "连续口语叙述，人物判断跟着现场发生。",
            }
            for quote, purpose in zip(long_quotes, purposes)
        ]
        anchors = ["我没想到今天会在这里遇见他。", "有意思。"]
        for name in GATE.REQUIRED_DIMENSIONS:
            receipt["source_baseline"]["dimensions"][name] = {
                "rule": f"{name} 使用主体原文口气。",
                "source_quotes": anchors,
                "transfer_rule": "迁移句间关系，不复制人物和事件。",
                "ai_drift_to_reject": "拒绝工整总结和复合钩子加工句。",
            }
        receipt["source_baseline"]["anti_patterns"] = [
            {"pattern": f"AI模板{i}", "why_unlike_source": "原文不会这样总结意义。"}
            for i in range(3)
        ]
        receipt["source_baseline"]["manual_judgment"] = "主体声线基线已人工建立。"
        passages = []
        for passage_index, purpose in enumerate(("开口", "冲突", "对白", "日常", "收口"), start=1):
            annotations = []
            for sentence_index, sentence in enumerate(GATE.sentence_units(self.source_text), start=1):
                annotation = {
                    "source_sentence": sentence,
                    "feature_ids": [
                        GATE.ULTRA_FINE_FEATURE_IDS[(passage_index + sentence_index) % 52],
                        GATE.ULTRA_FINE_FEATURE_IDS[(passage_index + sentence_index + 17) % 52],
                    ],
                }
                for field_index, field in enumerate(GATE.SOURCE_SENTENCE_ANNOTATION_FIELDS, start=1):
                    annotation[field] = (
                        f"{purpose}段第{sentence_index}句的{field_index}号句面判断，"
                        f"依据词序与停顿说明其局部作用。"
                    )
                annotations.append(annotation)
            passages.append(
                {
                    "id": f"P-{passage_index}",
                    "quote": self.source_text,
                    "purpose": purpose,
                    "sentence_annotations": annotations,
                }
            )
        receipt["ultra_fine_source_baseline"] = {
            "methodology_reference_read": True,
            "annotation_unit": "sentence",
            "feature_inventory": list(GATE.ULTRA_FINE_FEATURE_IDS),
            "source_passages": passages,
            "distribution_baseline": {
                "measurement_method": "按逐句切分结果人工复核字符、句长、问句、省略号、段长与虚词出现次数。",
                "metrics": {
                    "non_whitespace_chars": len(self.source_text),
                    "sentence_count": len(GATE.sentence_units(self.source_text)),
                    "sentence_length_median": 16,
                    "sentence_length_p90": 24,
                    "question_count": 3,
                    "ellipsis_count": 0,
                    "paragraph_length_median": len(self.source_text),
                    "function_word_counts": {"我": 8, "了": 6, "也": 2},
                },
                "interpretation": "主体以中短口语陈述推进，反问和极短插句只在关系受压处出现，数字只作边界参照。",
                "mechanical_statistical_matching_forbidden": True,
            },
            "manual_judgment": "五组连续片段已经逐句检查，迁移对象是句法选择与语用动作，不是人物事件表层。",
        }
        source_sentences = GATE.sentence_units(self.source_text)
        section_judgments = {
            "1": "撞见节在落笔前锁定先看见再收钥匙的知觉顺序，让惊讶只从手部反应露出。",
            "2": "关门节在落笔前锁定哭声错答与拒绝解释，让关系终止停在门外余音里。",
        }
        for section_index, plan in enumerate(receipt["section_generation_plans"], start=1):
            plan.update(
                {
                    "status": "passed",
                    "planned_before_draft": True,
                    "source_passage_ids": [f"P-{section_index}"],
                    "surface_copy_rejected": True,
                    "manual_judgment": section_judgments[str(section_index)],
                }
            )
            plan["sentence_mechanisms"] = [
                {
                    "source_sentence": source_sentences[(section_index + mechanism_index) % len(source_sentences)],
                    "feature_ids": [
                        GATE.ULTRA_FINE_FEATURE_IDS[mechanism_index],
                        GATE.ULTRA_FINE_FEATURE_IDS[mechanism_index + 20],
                    ],
                    "mechanism": f"机制{mechanism_index}保留先见动作后出判断的句间次序。",
                    "target_intent": f"用于本节第{mechanism_index}处关系压力的即时落字。",
                    "allowed_deviation": "允许替换人物物件和句长，不复制原句表层。",
                    "prohibited_shell": "禁止补写意义总结、排比判词与工整复合钩子。",
                    "surface_copy_rejected": True,
                }
                for mechanism_index in range(3)
            ]
            plan["paragraph_plan"] = {
                field: f"第{section_index}节的{field}按现场动作切段并保留关系空白。"
                for field in GATE.SECTION_PARAGRAPH_PLAN_FIELDS
            }
            plan["window_plan"] = {
                field: f"第{section_index}节的{field}使用长短句差和有限插嘴控制窗口。"
                for field in GATE.SECTION_WINDOW_PLAN_FIELDS
            }
        receipt["calibration_samples"] = [
            {
                "source_quote": "我没想到今天会在这里遇见他。他伸手拦我，我直接把他的手推了回去。",
                "target_sample": f"我没想到回来拿第{i}样东西，也会撞见他们站在门里。",
                "comparison": "都使用完整口语陈述，不挤压多重象征。",
                "functional_alignment_used_as_prose_proof": False,
                "extra_ai_shell": False,
            }
            for i in range(3)
        ]
        if include_draft:
            receipt["gate_status"] = "passed"
            receipt["draft"] = {
                "path": str(self.draft.resolve()),
                "sha256": GATE.sha256(self.draft),
            }
            section_quotes = {
                "1": ["我没想到来取东西会撞见他们。", "他伸手拦我，我把钥匙收了回来。"],
                "2": ["她先哭了。", "有意思，我还什么都没问。"],
            }
            section_anchors = {
                "1": ["我没想到今天会在这里遇见他。", "他伸手拦我，我直接把他的手推了回去。"],
                "2": ["有意思。", "最后我把门关上。"],
            }
            receipt["section_reviews"] = [
                {
                    "section_id": section_id,
                    "status": "passed",
                    "target_quotes": quotes,
                    "source_anchors": section_anchors[section_id],
                    "dimensions_checked": list(GATE.REQUIRED_DIMENSIONS),
                    "source_voice_preserved": True,
                    "functional_alignment_used_as_prose_proof": False,
                    "extra_ai_shell": False,
                    "comparison": f"第 {section_id} 节目标句保持主体原文的直白口语和临场判断。",
                    "generation_plan_consumed": True,
                    "sentence_mappings": [
                        {
                            "target_sentence": target_sentence,
                            "source_anchor_sentence": source_sentences[(int(section_id) + mapping_index) % len(source_sentences)],
                            "feature_ids": ["CP-01", "SC-01"],
                            **{
                                field: f"第{section_id}节第{mapping_index}句在{field}上保留现场先后关系并允许原创偏移。"
                                for field in GATE.TARGET_SENTENCE_MAPPING_FIELDS
                            },
                            "contract_used_during_writing": True,
                            "surface_copy_rejected": True,
                        }
                        for mapping_index, target_sentence in enumerate(quotes, start=1)
                    ],
                    "section_write_judgment": f"第{section_id}节落笔时逐句调用了预先绑定的句法、指代和语用机制，并拒绝表层照抄。",
                }
                for section_id, quotes in section_quotes.items()
            ]
            subflow_review = receipt["source_subflow_reviews"][0]
            subflow_review.update(
                {
                    "status": "passed",
                    "target_sections": ["1", "2"],
                    "target_section_rationale": "撞见、拦手和钥匙换主都发生在前两节，完整承接该 SF 的现场压力。",
                    "semantic_review_method": "current_model_manual",
                    "automation_used_for_semantic_judgment": False,
                    "source_voice_preserved": True,
                    "functional_alignment_used_as_prose_proof": False,
                    "extra_ai_shell": False,
                    "manual_judgment": "SF-01 的六类局部颗粒均已在两节目标正文中逐项核对。",
                }
            )
            field_reviews = {
                "narrative_voice_and_attitude": (
                    "女主先压住惊讶再用反问露出不耐，保留主体的嘴硬观察位。",
                    "同两句在这里证明叙述态度由克制转为带刺，不用于替代节奏判断。",
                ),
                "sentence_relation_and_rhythm": (
                    "陈述句铺开撞见事实，短反问随后截断，让句速在受压处突然加快。",
                    "同两句在这里形成一长一短的速度落差，不用于证明叙述态度。",
                ),
                "paragraph_breath_and_cut_points": (
                    "撞见句独立起段，反问句另起一拍，段落切点把人物错位留在空白里。",
                    "同两句在这里负责段落停顿和换气，不用于证明对白错答。",
                ),
                "dialogue_misfire_or_avoidance": (
                    "对方用哭回避钥匙归属，女主不接解释，只用反问缩窄回答范围。",
                    "同两句在这里呈现问钥匙却收到哭声的错答，不用于证明动作织入。",
                ),
                "action_perception_emotion_weave": (
                    "先看见他们再收回钥匙，感知和手部动作替代了抽象的受伤总结。",
                    "同两句在这里连接看见、拦手和收钥匙，不用于证明口语毛边。",
                ),
                "narrator_interjection_and_roughness": (
                    "有意思是一句不够端正的现场插嘴，把委屈拧成带火气的自嘲。",
                    "同两句在这里保留口语插嘴和不体面火气，不用于证明段落结构。",
                ),
            }
            for field in GATE.SOURCE_STYLE_GRANULARITY_FIELDS:
                comparison, reuse_reason = field_reviews[field]
                subflow_review["dimension_transfers"][field] = {
                    "source_evidence": ["我没想到今天会在这里遇见他。", "有意思。"],
                    "evidence_mappings": [
                        {
                            "source_quote": "我没想到今天会在这里遇见他。",
                            "target_quotes": ["我没想到来取东西会撞见他们。"],
                            "comparison": comparison + "第一条原文证据对应目标的撞见开场。",
                        },
                        {
                            "source_quote": "有意思。",
                            "target_quotes": ["有意思，我还什么都没问。"],
                            "comparison": comparison + "第二条原文证据对应目标的反问收束。",
                        },
                    ],
                    "target_quotes": ["我没想到来取东西会撞见他们。", "有意思，我还什么都没问。"],
                    "comparison": comparison,
                    "cross_dimension_reuse_justification": reuse_reason,
                    "surface_copy_rejected": True,
                }
            receipt["full_text_review"] = {
                "reviewed_full_text": True,
                "all_sections_reviewed": True,
                "primary_source_voice_dominant": True,
                "auxiliary_style_contamination": False,
                "functional_alignment_used_as_prose_proof": False,
                "remaining_extra_ai_shell": False,
                "conclusion": "两节均已按主体原文声线复核。",
            }
        self.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return receipt

    def test_complete_prewrite_contract_passes(self) -> None:
        self.completed_receipt(include_draft=False)
        data = json.loads(self.receipt.read_text(encoding="utf-8"))
        errors, summary = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertEqual([], errors)
        self.assertEqual(3, summary["valid_calibration_samples"])

    def test_missing_source_sentence_annotation_blocks(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        receipt["ultra_fine_source_baseline"]["source_passages"][0][
            "sentence_annotations"
        ].pop()
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("不得抽样" in item for item in errors))

    def test_missing_section_generation_plan_blocks(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        receipt["section_generation_plans"].pop()
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("正文落笔前缺少小节颗粒度包" in item for item in errors))

    def test_all_draft_sections_must_be_reviewed(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"] = receipt["section_reviews"][:1]
        self.receipt.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("正文小节缺少文字颗粒度复核: 2" in item for item in errors))

    def test_bind_draft_scaffolds_every_section(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        bound = GATE.bind_draft(receipt, self.draft)
        self.assertEqual(["1", "2"], [item["section_id"] for item in bound["section_reviews"]])
        self.assertEqual("pending", bound["gate_status"])
        self.assertEqual(GATE.sha256(self.draft), bound["draft"]["sha256"])
        self.assertEqual("pending", bound["source_subflow_reviews"][0]["status"])

    def test_function_alignment_cannot_replace_prose_comparison(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["functional_alignment_used_as_prose_proof"] = True
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("functional_alignment_used_as_prose_proof" in item for item in errors))

    def test_complete_draft_contract_passes(self) -> None:
        receipt = self.completed_receipt()
        errors, summary = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertEqual([], errors)
        self.assertEqual(2, summary["passed_sections"])
        self.assertEqual(1, summary["passed_subflows"])

    def test_contract_must_be_used_during_writing(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["sentence_mappings"][0][
            "contract_used_during_writing"
        ] = False
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("contract_used_during_writing" in item for item in errors))

    def test_generation_plan_consumption_is_required(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["generation_plan_consumed"] = False
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("落笔时消费超细颗粒度包" in item for item in errors))

    def test_reused_section_anchor_pair_blocks(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][1]["source_anchors"] = receipt["section_reviews"][0]["source_anchors"]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("不得复用同一组主体声线锚" in item for item in errors))

    def test_reused_section_comparison_blocks(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][1]["comparison"] = receipt["section_reviews"][0]["comparison"]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("不得复用模板化" in item for item in errors))

    def test_missing_subflow_dimension_blocks(self) -> None:
        receipt = self.completed_receipt()
        review = receipt["source_subflow_reviews"][0]
        del review["dimension_transfers"]["narrator_interjection_and_roughness"]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("缺少正文颗粒迁移" in item for item in errors))

    def test_partial_source_evidence_consumption_blocks(self) -> None:
        receipt = self.completed_receipt()
        transfer = receipt["source_subflow_reviews"][0]["dimension_transfers"][
            "sentence_relation_and_rhythm"
        ]
        transfer["source_evidence"] = transfer["source_evidence"][:1]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("必须完整原样覆盖主体字段证据" in item for item in errors))

    def test_missing_per_evidence_mapping_blocks(self) -> None:
        receipt = self.completed_receipt()
        transfer = receipt["source_subflow_reviews"][0]["dimension_transfers"][
            "dialogue_misfire_or_avoidance"
        ]
        transfer["evidence_mappings"] = transfer["evidence_mappings"][:1]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("必须逐条覆盖全部主体证据" in item for item in errors))

    def test_cross_dimension_quote_reuse_without_reasons_blocks(self) -> None:
        receipt = self.completed_receipt()
        review = receipt["source_subflow_reviews"][0]
        for transfer in review["dimension_transfers"].values():
            transfer["cross_dimension_reuse_justification"] = ""
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("跨字段复用同一组目标句" in item for item in errors))

    def test_normalized_dimension_comparison_template_blocks(self) -> None:
        receipt = self.completed_receipt()
        review = receipt["source_subflow_reviews"][0]
        for field, transfer in review["dimension_transfers"].items():
            transfer["comparison"] = f"SF-01 的 {field} 在第 1 节已经完成具体句面对照。"
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("comparison 不得只替换字段名" in item for item in errors))

    def test_automated_semantic_judgment_blocks(self) -> None:
        receipt = self.completed_receipt()
        review = receipt["source_subflow_reviews"][0]
        review["automation_used_for_semantic_judgment"] = True
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("禁止用自动脚本生成语义裁决" in item for item in errors))

    def test_missing_target_section_rationale_blocks(self) -> None:
        receipt = self.completed_receipt()
        review = receipt["source_subflow_reviews"][0]
        review["target_section_rationale"] = ""
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("target_section_rationale" in item for item in errors))

    def test_changed_draft_invalidates_contract(self) -> None:
        receipt = self.completed_receipt()
        self.draft.write_text(self.draft.read_text(encoding="utf-8") + "又一句。", encoding="utf-8")
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("正文已变化" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
