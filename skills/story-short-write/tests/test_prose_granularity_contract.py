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
        self.dialogue_source_excerpts = [
            (
                "他先叫住我，手还按在钥匙上。"
                "「你先别拿走，我们回家再说行不行？」"
                "「这里就是我家。」"
                "「她刚哭过，你别在这个时候跟她计较。」"
                "「所以你先松手。」"
            ),
            (
                "门都快关上了，他又追过来。"
                "「你一定要把事情弄得这么难看吗？」"
                "「钥匙是谁给她的？」"
                "「我现在跟你说的是一家人的体面。」"
                "「我问的是钥匙。」"
            ),
        ]
        self.source_text = (
            "我没想到今天会在这里遇见他。他伸手拦我，我直接把他的手推了回去。"
            "他问我是不是非要这样。我不知道我哪样了？难道站在这里也是我的错？"
            "我懒得和他争，转身去拿桌上的钥匙。钥匙没拿到，却先听见她哭了。"
            "有意思。明明从头到尾我一句话都没说，现在倒像是我欺负了人。"
            "最后我把门关上。外面还有人在说话，我没再听，反正也不重要了。"
            + "".join(self.dialogue_source_excerpts)
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
            "# 测试\n\n1.\n\n我没想到来取东西会撞见他们。\n\n他伸手拦我，我把钥匙收了回来。\n\n他嘴上说只是借用，手却还按在钥匙上。\n\n「钥匙给我。」\n\n「你先听我解释。」\n\n2.\n\n周远站在门外没动。\n\n她先哭了。\n\n她嘴上说不争，手却还扣着门锁。\n\n有意思，我还什么都没问。\n\n「你还要问什么？」\n\n「我问的是钥匙在哪儿。」\n",
            encoding="utf-8",
        )
        self.outline.write_text(
            "## 1. 撞见\n\n取东西时撞见两人，先收回钥匙。\n\n"
            "## 2. 关门\n\n对方用哭回避，女主拒绝解释并关门。\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_same_file_path_accepts_existing_hardlink_alias(self) -> None:
        alias = self.root / "大纲别名.md"
        alias.hardlink_to(self.outline)

        self.assertTrue(GATE.same_file_path(alias, self.outline))

    def add_source_detail_card(self) -> dict:
        detail_dir = self.source.parent.parent / "原文细节库"
        detail_dir.mkdir(parents=True, exist_ok=True)
        detail_file = detail_dir / "动作细节库.md"
        detail_file.write_text(
            "# 动作细节库\n\n"
            "## 卡 DZ01｜推手后收回钥匙\n\n"
            "- 原文位置：L1-L2\n"
            "- 原文短语：`他伸手拦我，我直接把他的手推了回去`\n"
            "- 动作功能：拒绝阻拦后立刻收回钥匙，让关系撤权落到物件换手。\n"
            "- 这个细节为什么有用：动作不是姿态，而是把进入权从对方手里拿回来。\n",
            encoding="utf-8",
        )
        receipt = GATE.create_receipt("测试", self.source)
        review = receipt["source_detail_card_reviews"][0]
        review.update(
            {
                "planning_status": "passed",
                "target_sections": ["1"],
                "target_adaptation": "女主在取物现场推开阻拦，并把钥匙重新收回自己手中。",
                "distinct_function_to_preserve": "推开动作必须实际改变钥匙持有与进入权限，不能只表现生气。",
                "overlap_binding_ids": ["SF-01", "P-001"],
                "overlap_is_not_omission": "虽然与子流程和情节拍重叠，本卡仍单独验收推手后钥匙换主的动作功能。",
                "semantic_review_method": "current_model_manual",
                "automation_used_for_semantic_judgment": False,
            }
        )
        return receipt

    def test_source_detail_cards_are_inventory_not_optional_candidates(self) -> None:
        receipt = self.add_source_detail_card()
        records = GATE.detail_card_records(self.source)
        self.assertEqual(["DZ01"], [item["card_id"] for item in records])
        errors: list[str] = []
        passed = GATE.validate_detail_card_plans(receipt, records, self.outline, errors)
        self.assertEqual(1, passed)
        self.assertEqual([], errors)

        receipt["source_detail_card_reviews"] = []
        errors = []
        GATE.validate_detail_card_plans(receipt, records, self.outline, errors)
        self.assertTrue(any("全集同序、等数" in item for item in errors))
        self.assertTrue(any("未进入迁移计划" in item for item in errors))

    def test_apply_detail_plan_only_merges_complete_current_model_plan(self) -> None:
        receipt = self.add_source_detail_card()
        review = receipt["source_detail_card_reviews"][0]
        review.update({
            "planning_status": "pending", "target_sections": [], "target_adaptation": "",
            "distinct_function_to_preserve": "", "overlap_binding_ids": [],
            "overlap_is_not_omission": "", "automation_used_for_semantic_judgment": None,
        })
        receipt["outline"] = {"path": str(self.outline), "sha256": GATE.sha256(self.outline)}
        plan = {
            "mode": "full_bridge", "reviewed_by_current_model": True,
            "semantic_fields_generated_by_script": False,
            "manual_judgment": "当前模型逐卡回看原文细节和目标细纲后完成对应关系判断。",
            "cards": [{
                "card_id": "DZ01", "target_sections": ["1"],
                "target_adaptation": "女主推开阻拦者并把钥匙收回自己手中。",
                "distinct_function_to_preserve": "推开动作必须真正改变钥匙持有和进入权限。",
                "overlap_binding_ids": ["P-001", "SF-01"],
                "overlap_is_not_omission": "情节拍记录换手结果，本卡另验推开与收钥匙的动作连续性。",
            }],
        }
        merged = GATE.apply_detail_plan(receipt, plan)
        result = merged["source_detail_card_reviews"][0]
        self.assertEqual("passed", result["planning_status"])
        self.assertEqual(["1"], result["target_sections"])
        self.assertFalse(result["automation_used_for_semantic_judgment"])
        self.assertEqual("pending", result["status"])

        plan["semantic_fields_generated_by_script"] = True
        with self.assertRaisesRegex(ValueError, "禁止由脚本生成"):
            GATE.apply_detail_plan(receipt, plan)

    def test_apply_section_plan_only_serializes_current_model_sidecar(self) -> None:
        receipt = GATE.bind_outline(
            GATE.create_receipt("测试", self.source), self.outline
        )
        supplied = receipt["section_generation_plans"][:1]
        supplied[0]["manual_judgment"] = "当前模型针对本节现场逐项完成的独立文字落笔判断。"
        plan = {
            "reviewed_by_current_model": True,
            "semantic_fields_generated_by_script": False,
            "outline_sha256": GATE.sha256(self.outline),
            "manual_judgment": "当前模型逐节阅读细纲和主体原文后人工完成全部落笔包。",
            "section_generation_plans": supplied,
        }
        merged = GATE.apply_section_plan(receipt, plan)
        self.assertIs(supplied[0], merged["section_generation_plans"][0])
        plan["semantic_fields_generated_by_script"] = True
        with self.assertRaisesRegex(ValueError, "禁止由脚本生成"):
            GATE.apply_section_plan(receipt, plan)
        plan["semantic_fields_generated_by_script"] = False
        plan["outline_sha256"] = "stale"
        with self.assertRaisesRegex(ValueError, "当前细纲 SHA"):
            GATE.apply_section_plan(receipt, plan)

    def test_detail_card_requires_real_draft_quote_even_when_overlap_declared(self) -> None:
        receipt = self.add_source_detail_card()
        records = GATE.detail_card_records(self.source)
        review = receipt["source_detail_card_reviews"][0]
        review.update(
            {
                "status": "passed",
                "target_quotes": [],
                "comparison": "目标动作应把源文推开阻拦后的权限变化迁到钥匙换手。",
                "surface_copy_rejected": True,
                "manual_judgment": "已人工核对动作功能，但尚未绑定正文原句。",
            }
        )
        errors: list[str] = []
        passed = GATE.validate_detail_card_draft_reviews(
            receipt, records, GATE.extract_sections(self.draft.read_text(encoding="utf-8")), errors
        )
        self.assertEqual(0, passed)
        self.assertTrue(any("target_quotes 至少绑定一条正文原句" in item for item in errors))

        review["target_quotes"] = ["他伸手拦我，我把钥匙收了回来。"]
        errors = []
        passed = GATE.validate_detail_card_draft_reviews(
            receipt, records, GATE.extract_sections(self.draft.read_text(encoding="utf-8")), errors
        )
        self.assertEqual(1, passed)
        self.assertEqual([], errors)

    def test_sync_detail_catalog_preserves_existing_manual_review(self) -> None:
        receipt = self.add_source_detail_card()
        review = receipt["source_detail_card_reviews"][0]
        review["target_adaptation"] = "这是已经人工写好的迁移方案，增量同步时必须原样保留。"
        synced = GATE.sync_detail_catalog(receipt, self.source)
        self.assertEqual(
            "这是已经人工写好的迁移方案，增量同步时必须原样保留。",
            synced["source_detail_card_reviews"][0]["target_adaptation"],
        )
        self.assertEqual("pending", synced["prewrite_status"])
        self.assertEqual("pending", synced["gate_status"])

    def test_sync_detail_catalog_refreshes_source_fields_after_catalog_fix(self) -> None:
        receipt = self.add_source_detail_card()
        receipt["source_detail_card_reviews"][0]["source_quote"] = "过时且错误的来源引句"
        synced = GATE.sync_detail_catalog(receipt, self.source)
        self.assertEqual(
            "他伸手拦我，我直接把他的手推了回去",
            synced["source_detail_card_reviews"][0]["source_quote"],
        )

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
                if GATE.explicit_relation_markers(sentence):
                    annotation["feature_ids"] = list(
                        dict.fromkeys(annotation["feature_ids"] + ["LM-02", "SC-05"])
                    )
                relation_markers = GATE.explicit_relation_markers(sentence)
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
                            f"{feature_id} 由当前句中的具体词序、停顿或话语动作提供，"
                            "只标记这句话实际出现的局部机制。"
                        ),
                    }
                    for feature_id in annotation["feature_ids"]
                ]
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
            "feature_assignment_policy": {
                "method": "current_model_sentence_semantic",
                "mechanical_quota_or_rotation_used": False,
                "full_inventory_occurrence_required": False,
                "manual_judgment": "逐句按真实词序、连接、聚焦和语用动作选择特征，不按 52 项覆盖配额分派。",
            },
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
        liveliness_asset_file = self.root / "成文活性层资产.md"
        liveliness_asset_file.write_text("测试成文活性资产", encoding="utf-8")
        liveliness_assets = []
        source_quotes = [
            "我没想到今天会在这里遇见他。",
            "他伸手拦我，我直接把他的手推了回去。",
            "有意思。",
        ]
        for asset_type in GATE.LIVELINESS_ASSET_TYPES:
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
        receipt["prose_liveliness_layer"] = {
            "status": "passed",
            "source_extraction_mode": "current_model_manual",
            "primary_source_only": True,
            "asset_file": {
                "path": str(liveliness_asset_file.resolve()),
                "sha256": GATE.sha256(liveliness_asset_file),
            },
            "asset_types": list(GATE.LIVELINESS_ASSET_TYPES),
            "assets": liveliness_assets,
            "stiffness_prohibitions": [
                {
                    "pattern": f"作者替人物总结的僵硬句面模式{i}",
                    "why_stiff": "作者替人物整理完整意义，现场动作因此失去作用。",
                    "replacement_action": "回到人物动作、错答和物件阻力，保留直接主观声音。",
                }
                for i in range(6)
            ],
            "manual_judgment": "七类资产均从主体原文真实句面人工提取，用于首写时保住人物脾气与不工整的现场活性。",
        }
        personality_assets = []
        personality_quotes = [
            "我没想到今天会在这里遇见他。",
            "有意思。",
        ]
        for asset_type in GATE.CHARACTER_PERSONALITY_ASSET_TYPES:
            for asset_index in range(1, 4):
                personality_assets.append(
                    {
                        "id": f"PERSON-{asset_type}-{asset_index}",
                        "type": asset_type,
                        "source_quotes": personality_quotes,
                        "personality_core": f"第{asset_index}种{asset_type}体现人物先偏看再反应的稳定偏手。",
                        "transfer_mechanism": "迁移人物的注意、错答和动作选择，不复制原身份事件。",
                        "surface_copy_boundary": "拒绝原人物、职业、物件、关系称谓和完整情节表层。",
                        "surface_copy_rejected": True,
                    }
                )
        asset_file = self.root / "人物性格颗粒度资产.md"
        asset_file.write_text("测试人物性格颗粒度资产", encoding="utf-8")
        protagonist_assets = [personality_assets[index]["id"] for index in (0, 3, 6, 9, 12)]
        counterpart_assets = [personality_assets[index]["id"] for index in (1, 4, 7, 10, 13)]
        receipt["character_personality_layer"] = {
            "status": "passed",
            "source_extraction_mode": "current_model_manual",
            "primary_source_only": True,
            "asset_file": {
                "path": str(asset_file.resolve()),
                "sha256": GATE.sha256(asset_file),
            },
            "asset_types": list(GATE.CHARACTER_PERSONALITY_ASSET_TYPES),
            "assets": personality_assets,
            "target_character_profiles": [
                {
                    "name": "林初",
                    "role": "protagonist",
                    "source_asset_ids": protagonist_assets,
                    "attention_bias": "先看谁碰她的钥匙，再判断对方说了什么。",
                    "desire_and_shame": "想被挽留又羞于承认，嘴硬时手会先收东西。",
                    "defense_strategy": "用短问和收回物件保护自己，不先解释委屈。",
                    "speech_pattern": "追具体名词，受伤后插一句不够端正的冷话。",
                    "misfire_pattern": "明明想问关系，却故意只问钥匙归谁。",
                    "action_bias": "一受压就控制门、钥匙和离场方向。",
                    "self_contradiction": "声称不在意，却会停下来听对方是否追上来。",
                    "private_relation_language": "把旧称呼压住，只在最软的一刻漏出半句。",
                    "generic_shells_rejected": ["清醒判词机器", "全程正确提问", "只会冷笑"],
                    "surface_copy_rejected": True,
                    "manual_judgment": "她的性格由钥匙控制、嘴硬等待和不肯解释共同构成，换成普通清醒女主就不能原样成立。",
                },
                {
                    "name": "周远",
                    "role": "relationship_counterpart",
                    "source_asset_ids": counterpart_assets,
                    "attention_bias": "先看现场是否难看，再迟一步看见伴侣的伤。",
                    "desire_and_shame": "想维持好人位置，最怕承认自己的选择带有私心。",
                    "defense_strategy": "用体面理由改写争执题目，把具体责任说成人情。",
                    "speech_pattern": "先叫名字缓和，再用完整解释拖延真正回答。",
                    "misfire_pattern": "被问钥匙时先解释别人为什么哭，暴露保护顺位。",
                    "action_bias": "习惯伸手拦门和替别人收拾残局，越补越越界。",
                    "self_contradiction": "自认公平，身体却总先挡在更弱势的人前面。",
                    "private_relation_language": "只在失去控制时使用旧昵称，平时维持克制称呼。",
                    "generic_shells_rejected": ["只会说别闹", "纯工具渣男", "每次精准递反刀"],
                    "surface_copy_rejected": True,
                    "manual_judgment": "他的性格由体面自证、迟到的照顾和下意识拦挡构成，不能只作为触发女主清醒的错误答案。",
                },
            ],
            "manual_judgment": "目标人物分别迁移原文的偏看、错答、身体先选和口语毛边，人物之间不得共享同一防御与行动方案。",
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
                    "generation_driver": "continuous_source_chain",
                    "single_sentence_features_secondary": True,
                    "source_passage_ids": [f"P-{section_index}"],
                    "surface_copy_rejected": True,
                    "manual_judgment": section_judgments[str(section_index)],
                }
            )
            chain_excerpts = [
                "".join(source_sentences[:5]),
                "".join(source_sentences[5:]),
            ]
            plan["continuous_source_chain_packets"] = [
                {
                    "source_excerpt": excerpt,
                    "source_sentence_chain": GATE.sentence_units(excerpt),
                    "chain_motion": (
                        f"第{section_index}节正例句链{chain_index}先给可见异常，再由短问和动作改变话轮。"
                    ),
                    "target_scene_use": (
                        f"第{section_index}节第{chain_index}组关系压力用钥匙、拦手和哭声依次推进。"
                    ),
                    "target_sentence_relation": (
                        f"第{section_index}节第{chain_index}组目标句保持看见、追问、错答、收物件的先后，不补人物权衡说明。"
                    ),
                    "explanation_to_omit": (
                        f"删除第{section_index}节第{chain_index}组动作后关于人物本质、象征意义和心理算法的翻译。"
                    ),
                    "surface_copy_rejected": True,
                    "manual_judgment": (
                        f"第{section_index}节第{chain_index}组只迁移连续句间反应，不复制测试原文的人物身份、钥匙事件或原句。"
                    ),
                }
                for chain_index, excerpt in enumerate(chain_excerpts, start=1)
            ]
            plan["contrastive_examples"] = [
                {
                    "positive_source_excerpt": excerpt,
                    "positive_effect": (
                        f"正例{example_index}让动作和错答自己递进，叙述者只在现场证据后插入短判断。"
                    ),
                    "negative_example": (
                        f"第{section_index}节错误反例{example_index}把三项情况列完，再解释人物正在权衡什么并总结他的本质。"
                    ),
                    "negative_failure": (
                        f"错误反例{example_index}用规则清单和全知心理代替可观察动作，人物因而失去临场偏手。"
                    ),
                    "rewrite_instruction": (
                        f"第{section_index}节反例{example_index}应删去解释，只保留先看见、再错答、随后控制物件的句间顺序。"
                    ),
                    "surface_copy_rejected": True,
                }
                for example_index, excerpt in enumerate(chain_excerpts, start=1)
            ]
            explicit_rehearsal = (
                "他说钥匙只是借用，手却还压在钥匙扣上，连我要拿时也没有松。"
                if section_index == 1
                else "她一面说自己不争，手却还扣在门锁上，旁人看过来才慢慢松开。"
            )
            explicit_negative = (
                "他说钥匙只是借用，手还压在钥匙扣上，连我要拿时也没有松。"
                if section_index == 1
                else "她一面说自己不争，手还扣在门锁上，旁人看过来才慢慢松开。"
            )
            plan["relation_micro_examples"] = [
                {
                    "source_excerpt": "钥匙没拿到，却先听见她哭了。",
                    "source_relation_type": "counterevidence",
                    "target_relation_type": "counterevidence",
                    "source_marking_mode": "explicit",
                    "target_marking_mode": "explicit",
                    "source_markers": ["却"],
                    "target_markers": ["却"],
                    "source_function_word_skeleton": "前项动作没有完成，却先被另一人的哭声截断。",
                    "target_rehearsal": explicit_rehearsal,
                    "negative_example": explicit_negative,
                    "negative_failure": "前后语义已经相反，错例只用还并排动作，人物的口是心非没有在句面撞开。",
                    "transfer_instruction": "保留却与还叠加形成的反证力，人物、钥匙位置和具体动作允许换新。",
                    "mechanical_marker_insertion_forbidden": True,
                    "surface_copy_rejected": True,
                    "manual_judgment": f"第{section_index}节这组关系需要显式转折，否则嘴上退让和手上占有会读成平直补充。",
                },
                {
                    "source_excerpt": "他伸手拦我，我直接把他的手推了回去。",
                    "source_relation_type": "succession",
                    "target_relation_type": "succession",
                    "source_marking_mode": "implicit",
                    "target_marking_mode": "implicit",
                    "source_markers": [],
                    "target_markers": [],
                    "source_function_word_skeleton": "拦手动作后直接接推回动作，靠动作方向相反完成顺承。",
                    "target_rehearsal": f"他伸手挡住第{section_index}道门，我把钥匙收回掌心，往后退了一步。",
                    "negative_example": f"他伸手挡住第{section_index}道门，所以我把钥匙收回掌心，表达自己的拒绝。",
                    "negative_failure": "错例机械补所以并追加意义说明，破坏两个动作本来就能完成的关系变化。",
                    "transfer_instruction": "目标保留动作紧接动作的隐式顺承，不为统计或过检额外补连接词。",
                    "mechanical_marker_insertion_forbidden": True,
                    "surface_copy_rejected": True,
                    "manual_judgment": f"第{section_index}节这组关系由手的相反方向自然成立，显式因果词反而会让句子变硬。",
                },
            ]
            plan["dialogue_voice_packets"] = [
                {
                    "source_excerpt": excerpt,
                    "source_dialogue_turns": GATE.dialogue_turn_units(excerpt),
                    "target_character": "周远",
                    "turn_motion": f"第{section_index}节原文对白{dialogue_index}先叫住关系人，再找补，随后用别人难处压过钥匙归属。",
                    "target_scene_use": f"第{section_index}节第{dialogue_index}场让周远先缓和称呼，再回避钥匙或门的具体追问。",
                    "target_rehearsal": (
                        f"周远伸手拦住第{dialogue_index}把钥匙。"
                        f"「你先别拿，等我把这边安顿好，我们回去慢慢说。」"
                        f"「我只问钥匙是谁给的。」"
                        f"「她刚哭过，你别在这个时候逼她，行不行？」"
                    ),
                    "oral_texture_transfer": "保留先叫住、先许诺以后解释、再用弱者处境找补的口头展开，不压成一句命令。",
                    "relationship_leverage": "周远利用两人仍有私下谈话入口和主角一贯能体谅的旧习惯施压。",
                    "functional_compression_to_avoid": "禁止压成你先走、她留下之类剧情调度指令。",
                    "negative_example": f"「你先处理第{dialogue_index}件事，她留在这里。」",
                    "negative_failure": "错句只交付剧情功能，没有称呼、找补、关系杠杆和具体请求的口语过程。",
                    "rewrite_instruction": "恢复叫人、承诺稍后解释、借第三人的难处施压和对方追问这四步话轮。",
                    "surface_copy_rejected": True,
                    "manual_judgment": "目标试演保留原文丈夫自认讲理却不断答偏的说话习惯，当前人物和钥匙场面均为原创。",
                }
                for dialogue_index, excerpt in enumerate(
                    self.dialogue_source_excerpts, start=1
                )
            ]
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
            liveliness_indexes = (section_index - 1, section_index + 2, section_index + 5, section_index + 8)
            plan["liveliness_plan"] = {
                "planned_before_draft": True,
                "asset_ids": [liveliness_assets[index]["id"] for index in liveliness_indexes],
                **{
                    field: f"第{section_index}节的{field}按人物受压后的临场偏手具体落笔。"
                    for field in GATE.LIVELINESS_SECTION_PLAN_FIELDS
                },
                "stiffness_patterns_rejected": [
                    "作者主题总结",
                    "对话轮流答题",
                    "物件意义立刻说透",
                ],
                "manual_judgment": f"第{section_index}节先让动作、身体和错答暴露关系，再允许叙述者留下直接判断。",
            }
            plan["character_plan"] = {
                "planned_before_draft": True,
                "active_character_names": ["林初", "周远"],
                "participants": [
                    {
                        "character_name": "林初",
                        "source_asset_ids": protagonist_assets[:2],
                        "scene_want": f"第{section_index}节想拿回钥匙又不肯承认仍在等解释。",
                        "attention_first": "先盯住钥匙和拦门的手，不先听体面理由。",
                        "misread_or_avoidance": "故意把关系伤害缩成钥匙归属，避开问爱不爱。",
                        "speech_boundary": "只追一个具体名词，冷话不超过一次。",
                        "action_or_object_bias": "受压后先收钥匙或关门，用物件决定话轮。",
                        "relationship_private_trigger": "对方伸手拦她时，旧有被照顾惯性短暂回跳。",
                        "generic_function_line_to_reject": "拒绝让她直接总结边界、背叛和清醒结论。",
                    },
                    {
                        "character_name": "周远",
                        "source_asset_ids": counterpart_assets[:2],
                        "scene_want": f"第{section_index}节想保住体面并阻止她把冲突公开。",
                        "attention_first": "先看门外是否有人，再处理她为什么收钥匙。",
                        "misread_or_avoidance": "把她的归属质问误答成现场不要难看。",
                        "speech_boundary": "先叫名字，再解释别人，没有直接认错句。",
                        "action_or_object_bias": "先伸手拦而不是先回答，暴露控制习惯。",
                        "relationship_private_trigger": "她真正关门时才想起旧昵称，却已经来不及。",
                        "generic_function_line_to_reject": "拒绝只说别闹、为了她好或孩子无辜。",
                    },
                ],
                "interchangeability_risk": "若两人都用短问和收钥匙解决冲突，本节会变成同声线答题对白。",
                "manual_judgment": f"第{section_index}节由林初的物件控制和周远的体面回避相撞，双方动作方向必须相反。",
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
            receipt["rewrite_scope_review"] = {
                "mode": "first_draft",
                "full_rewrite_requested": False,
                "expected_section_ids": ["1", "2"],
                "rewritten_section_ids": ["1", "2"],
                "unchanged_section_ids": [],
                "full_text_read_before_rewrite": False,
                "full_text_read_after_rewrite": True,
                "manual_judgment": "这是首次正文落笔，两节均按写前合同生成，并在写后完整通读校验。",
            }
            receipt["manual_review_provenance"] = {
                "performed_by_current_model": True,
                "semantic_fields_generated_by_script": False,
                "receipt_population_method": "current_model_manual_field_entry",
                "full_text_read_by_current_model": True,
                "review_bound_to_draft_sha256": GATE.sha256(self.draft),
                "automation_artifacts_used": [],
                "manual_judgment": "当前模型逐节阅读正文并手工填写对白、句间关系、人物归属与全文裁决。",
            }
            section_quotes = {
                "1": [
                    "我没想到来取东西会撞见他们。",
                    "他伸手拦我，我把钥匙收了回来。",
                    "他嘴上说只是借用，手却还按在钥匙上。",
                    "「钥匙给我。」",
                    "「你先听我解释。」",
                ],
                "2": [
                    "周远站在门外没动。",
                    "她先哭了。",
                    "她嘴上说不争，手却还扣着门锁。",
                    "有意思，我还什么都没问。",
                    "「你还要问什么？」",
                ],
            }
            section_anchors = {
                "1": source_sentences[:4],
                "2": source_sentences[4:8],
            }
            source_annotation_by_sentence = {
                annotation["source_sentence"]: annotation
                for passage in receipt["ultra_fine_source_baseline"]["source_passages"]
                for annotation in passage["sentence_annotations"]
            }

            def completed_mapping(section_id: str, mapping_index: int, target_sentence: str) -> dict:
                source_anchor = source_sentences[
                    (int(section_id) + mapping_index) % len(source_sentences)
                ]
                source_features = source_annotation_by_sentence[source_anchor]["feature_ids"]
                target_evidence = target_sentence.strip("「」“”")
                source_evidence = source_anchor[: min(8, len(source_anchor))]
                minimal = GATE.is_minimal_function_sentence(target_sentence)
                return {
                    "target_sentence": target_sentence,
                    "source_anchor_sentence": source_anchor,
                    "feature_ids": source_features[:2],
                    "target_surface_evidence": target_evidence,
                    "source_surface_evidence": source_evidence,
                    "language_mechanism_match": f"目标证据“{target_evidence}”与源锚证据“{source_evidence}”都让判断跟着当场动作或话轮落下，不另加主题总结。",
                    "minimal_function_sentence_review": {
                        "detected": minimal,
                        "source_parallel_quote": "有意思。" if minimal else "",
                        "relation_change": "短句让争夺对象立即转向钥匙归属。" if minimal else "",
                        "personality_or_body_specificity": "说话者用当场口气抢回话轮，不是摘要。" if minimal else "",
                        "verdict": "keep" if minimal else "not_applicable",
                        "manual_judgment": "该短句改变下一轮应答，并由人物正在争夺的钥匙限定。" if minimal else "",
                    },
                    **{
                        field: f"第{section_id}节第{mapping_index}句在{field}上依据当前目标证据作具体对照并允许原创偏移。"
                        for field in GATE.TARGET_SENTENCE_MAPPING_FIELDS
                    },
                    "contract_used_during_writing": True,
                    "surface_copy_rejected": True,
                }

            def ownership_reviews(name: str, quote_contexts: list[tuple[str, str, str]]) -> list[dict]:
                return [
                    {
                        "quote": quote,
                        "owner_name": name,
                        "ownership_context": context,
                        "actor_or_speaker_marker": marker,
                        "marker_refers_to_owner": True,
                        "other_character_action_misassigned": False,
                        "manual_judgment": f"上下文中的“{marker}”明确指向{name}，该动作或话语由{name}完成。",
                    }
                    for quote, context, marker in quote_contexts
                ]
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
                    "semantic_review_method": "current_model_manual",
                    "automation_used_for_semantic_judgment": False,
                    "continuous_chain_reviews": [
                        {
                            "source_excerpt": packet["source_excerpt"],
                            "target_chain_quotes": quotes,
                            "sequence_comparison": f"第{section_id}节第{chain_index}组目标句先出现具体动作，再由另一人的阻拦或哭声迫使话轮变化，没有先讲规则。",
                            "post_action_explanation_removed": True,
                            "contract_used_during_writing": True,
                            "manual_judgment": f"第{section_id}节第{chain_index}组落笔实际依照连续原文的异常、接招和动作收口次序，未复制原句表层。",
                        }
                        for chain_index, packet in enumerate(
                            receipt["section_generation_plans"][int(section_id) - 1][
                                "continuous_source_chain_packets"
                            ],
                            start=1,
                        )
                    ],
                    "relation_micro_reviews": [
                        {
                            "source_excerpt": plan["source_excerpt"],
                            "target_quotes": (
                                ["他嘴上说只是借用，手却还按在钥匙上。"]
                                if section_id == "1"
                                else ["她嘴上说不争，手却还扣着门锁。"]
                            ),
                            "relation_type": "counterevidence",
                            "marking_mode": "explicit",
                            "target_markers": ["却"],
                            "source_function_word_logic_preserved": True,
                            "mechanical_marker_insertion_avoided": True,
                            "comparison": f"第{section_id}节用却还把口头退让与手上占位明确撞开，避免两个相反动作被读成平直补充。",
                            "manual_judgment": f"第{section_id}节此处显式转折来自人物当场口是心非，不是为增加虚词密度机械添字。",
                        }
                        if relation_index == 1
                        else {
                            "source_excerpt": plan["source_excerpt"],
                            "target_quotes": (
                                ["他伸手拦我，我把钥匙收了回来。"]
                                if section_id == "1"
                                else ["她先哭了。", "有意思，我还什么都没问。"]
                            ),
                            "relation_type": "succession",
                            "marking_mode": "implicit",
                            "target_markers": [],
                            "source_function_word_logic_preserved": True,
                            "mechanical_marker_insertion_avoided": True,
                            "comparison": f"第{section_id}节相邻动作按发生顺序直接推进，关系已由拦手或哭声后的反应成立，无需补所以或但是。",
                            "manual_judgment": f"第{section_id}节这一组保留主体原文的隐式动作承接，加连接词反而会替人物解释现场。",
                        }
                        for relation_index, plan in enumerate(
                            receipt["section_generation_plans"][int(section_id) - 1][
                                "relation_micro_examples"
                            ],
                            start=1,
                        )
                    ],
                    "dialogue_voice_reviews": [
                        {
                            "source_excerpt": packet["source_excerpt"],
                            "target_dialogue_turns": (
                                ["「钥匙给我。」", "「你先听我解释。」"]
                                if section_id == "1"
                                else ["「你还要问什么？」", "「我问的是钥匙在哪儿。」"]
                            ),
                            "oral_texture_preserved": True,
                            "functional_compression_avoided": True,
                            "rehearsal_used_as_voice_calibration": True,
                            "rehearsal_copied_verbatim": False,
                            "turn_sequence_comparison": f"第{section_id}节对白保留具体追问和解释回避，称呼与钥匙归属推动话轮，没有压成情节指令。",
                            "manual_judgment": f"第{section_id}节实际对白比写前试演更短，但仍有一方追物件、一方拖解释的自然接招，未复制试演原句。",
                            "speaker_and_scene_role": "当前说话者是关系中的被追问方，正在用具体物件回避责任。",
                            "concrete_pressure_or_object": "话轮围绕钥匙归属和谁有权拿走展开。",
                            "role_substitution_test": "换成旁观工作人员后不会这样护住自己的关系位置，因此不能由任意角色原样说出。",
                            "context_window_reviewed": "已重读该组对白前后各三至五句，确认追问与答偏连续。",
                            "verdict": "keep",
                        }
                        for packet in receipt["section_generation_plans"][
                            int(section_id) - 1
                        ]["dialogue_voice_packets"]
                    ],
                    "sentence_mappings": [
                        completed_mapping(section_id, mapping_index, target_sentence)
                        for mapping_index, target_sentence in enumerate(quotes, start=1)
                    ],
                    "section_write_judgment": f"第{section_id}节落笔时逐句调用了预先绑定的句法、指代和语用机制，并拒绝表层照抄。",
                    "liveliness_review": {
                        "asset_ids_consumed": receipt["section_generation_plans"][
                            int(section_id) - 1
                        ]["liveliness_plan"]["asset_ids"][:3],
                        "target_quotes": [quotes[0], quotes[1], quotes[1].split("，")[0]],
                        "living_language_preserved": True,
                        "author_summary_override": False,
                        "stiffness_patterns_remaining": [],
                        "explanatory_inference_review": {
                            "automatic_candidate_quotes": [],
                            "candidate_reviews": [],
                            "reviewed_full_section": True,
                            "unresolved_residue": [],
                            "manual_judgment": f"第{section_id}节已逐句复核叙述者说明，没有在动作后追加人物权衡流程、象征翻译或本质总结。",
                        },
                        "manual_judgment": f"第{section_id}节的撞见、拦手或带刺插嘴都改变了人物当场反应，没有由作者再补主题总结。",
                    },
                    "character_vitality_review": {
                        "character_reviews": [
                            {
                                "character_name": "林初",
                                "source_asset_ids_consumed": protagonist_assets[:2],
                                "target_quotes": (
                                    ["我没想到来取东西会撞见他们。", "我把钥匙收了回来"]
                                    if section_id == "1"
                                    else ["有意思，我还什么都没问。", "我还什么都没问"]
                                ),
                                "evidence_ownership_reviews": ownership_reviews(
                                    "林初",
                                    [
                                        ("我没想到来取东西会撞见他们。", "我没想到来取东西会撞见他们。", "我"),
                                        ("我把钥匙收了回来", "他伸手拦我，我把钥匙收了回来。", "我"),
                                    ]
                                    if section_id == "1"
                                    else [
                                        ("有意思，我还什么都没问。", "有意思，我还什么都没问。", "我"),
                                        ("我还什么都没问", "有意思，我还什么都没问。", "我"),
                                    ],
                                ),
                                "personality_dimensions_shown": ["attention_bias", "action_bias", "self_contradiction"],
                                "voice_or_behavior_not_interchangeable": True,
                                "action_not_plot_only": True,
                                "knowledge_or_self_awareness_limited": True,
                                "generic_role_shell_absent": True,
                                "manual_judgment": f"第{section_id}节林初先控制钥匙或话题，嘴上不问关系，动作却泄露她仍在意归属。",
                            },
                            {
                                "character_name": "周远",
                                "source_asset_ids_consumed": counterpart_assets[:2],
                                "target_quotes": ["他伸手拦我"] if section_id == "1" else ["周远站在门外没动。"],
                                "evidence_ownership_reviews": ownership_reviews(
                                    "周远",
                                    [("他伸手拦我", "他伸手拦我，我把钥匙收了回来。", "他")]
                                    if section_id == "1"
                                    else [("周远站在门外没动。", "周远站在门外没动。", "周远")],
                                ),
                                "personality_dimensions_shown": ["defense_strategy", "dialogue_misfire", "action_bias"],
                                "voice_or_behavior_not_interchangeable": True,
                                "action_not_plot_only": True,
                                "knowledge_or_self_awareness_limited": True,
                                "generic_role_shell_absent": True,
                                "manual_judgment": f"第{section_id}节周远先拦或先处理哭声，仍把现场体面放在关系回答前面。",
                            },
                        ],
                        "interchangeability_test": f"第{section_id}节若交换两人的动作，林初不会先替别人维持体面，周远也不会主动收回钥匙结束关系。",
                        "functional_character_residue": [],
                        "dialogue_grounding_review": {
                            "automatic_candidate_quotes": [],
                            "candidate_reviews": [],
                            "full_dialogue_reviews": [
                                {
                                    "quote": turn,
                                    "speaker_and_scene_role": "当前场景中说出该句的人物，身份已结合前后文核定。",
                                    "context_window": GATE.extract_sections(
                                        self.draft.read_text(encoding="utf-8")
                                    )[section_id],
                                    "utterance_goal": "该句回应眼前钥匙归属、拦手或哭声造成的关系压力。",
                                    "adjacency_or_reply_fit": "已核对前一问句、动作或对方偏答，这句与相邻话轮存在真实承接。",
                                    "time_state_fit": "时态与人物说话当刻的已发生、正在发生或尚未发生状态一致。",
                                    "object_and_result_complete": "动作、询问对象及已发生结果均落在句面或紧邻上下文，没有只报动作次数。",
                                    "participant_role_direction": "已核对谁发问、谁行动、动作落到谁身上，主动和被动关系没有倒置。",
                                    "character_specificity": "换成另一人物会改变追问、回避或收回钥匙的说法，不能原样复用。",
                                    "verdict": "keep",
                                    "manual_judgment": "逐字重读该句及前后窗口后确认口语承接、时间状态和人物偏手成立。",
                                }
                                for turn in GATE.dialogue_turn_units(
                                    GATE.extract_sections(
                                        self.draft.read_text(encoding="utf-8")
                                    )[section_id]
                                )
                            ],
                            "reviewed_all_character_dialogue": True,
                            "candidate_zero_is_not_pass": True,
                            "abstract_summary_reply_residue": [],
                            "manual_judgment": f"第{section_id}节已逐句复核对白，回答都落在钥匙、拦手或哭声等具体压力上，没有用抽象训诫替人物概括现场。",
                        },
                        "manual_judgment": f"第{section_id}节两人分别由归属敏感和体面回避驱动，不是一个负责提问、一个负责递反刀。",
                    },
                    "sentence_relation_review": {
                        "automatic_candidate_quotes": [],
                        "candidate_reviews": [],
                        "reviewed_full_section": True,
                        "mechanical_marker_insertion_used": False,
                        "unresolved_residue": [],
                        "manual_judgment": f"第{section_id}节已逐句核对顺承、转折和突断；显式却只落在口是心非处，其余动作关系保持自然隐式。",
                    },
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
                "character_personality_dominant": True,
                "conclusion": "两节均已按主体原文声线复核。",
            }
            receipt["character_arc_reviews"] = [
                {
                    "character_name": "林初",
                    "section_ids": ["1", "2"],
                    "stable_bias_quotes": ["我把钥匙收了回来", "有意思，我还什么都没问。"],
                    "variation_or_break_quotes": ["我没想到来取东西会撞见他们。", "我还什么都没问"],
                    "private_relation_language_quotes": ["有意思，我还什么都没问。"],
                    "profile_consistent_but_not_repetitive": True,
                    "not_functional_role": True,
                    "manual_judgment": "林初始终先控制物件再说话，但第二节由动作转成带刺插嘴，偏手稳定而表现发生变化。",
                },
                {
                    "character_name": "周远",
                    "section_ids": ["1", "2"],
                    "stable_bias_quotes": ["他伸手拦我", "周远站在门外没动。"],
                    "variation_or_break_quotes": ["他伸手拦我，我把钥匙收了回来。", "周远站在门外没动。"],
                    "private_relation_language_quotes": ["他伸手拦我"],
                    "profile_consistent_but_not_repetitive": True,
                    "not_functional_role": True,
                    "manual_judgment": "周远一贯先处理现场外观，第一节用身体阻拦，第二节则被哭声带走注意，回避方式并不重复。",
                },
            ]
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

    def test_explicit_source_relation_requires_function_word_features(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        annotations = receipt["ultra_fine_source_baseline"]["source_passages"][0][
            "sentence_annotations"
        ]
        relation_annotation = next(
            item for item in annotations if "却先听见" in item["source_sentence"]
        )
        relation_annotation["feature_ids"] = [
            item for item in relation_annotation["feature_ids"] if item not in ("LM-02", "SC-05")
        ]
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("必须包含 LM-02" in item for item in errors))
        self.assertTrue(any("必须包含 SC-05" in item for item in errors))

    def test_source_feature_ids_require_sentence_evidence(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        annotation = receipt["ultra_fine_source_baseline"]["source_passages"][0][
            "sentence_annotations"
        ][0]
        annotation["feature_evidence"] = []
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("必须与 feature_ids 一一对应" in item for item in errors))

    def test_mechanical_feature_rotation_blocks_prewrite(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        annotations = [
            annotation
            for passage in receipt["ultra_fine_source_baseline"]["source_passages"]
            for annotation in passage["sentence_annotations"]
        ]
        for annotation in annotations:
            annotation["feature_ids"] = []
            annotation["feature_evidence"] = []
        for feature_index, feature_id in enumerate(GATE.ULTRA_FINE_FEATURE_IDS):
            annotation = annotations[feature_index % len(annotations)]
            annotation["feature_ids"].append(feature_id)
        for annotation in annotations:
            relation_markers = GATE.explicit_relation_markers(annotation["source_sentence"])
            if relation_markers:
                annotation["feature_ids"] = list(
                    dict.fromkeys(annotation["feature_ids"] + ["LM-02", "SC-05"])
                )
            fallback_evidence = annotation["source_sentence"][:8].strip()
            annotation["feature_evidence"] = [
                {
                    "feature_id": feature_id,
                    "source_evidence": (
                        relation_markers[0]
                        if feature_id in ("LM-02", "SC-05") and relation_markers
                        else fallback_evidence
                    ),
                    "mechanism": f"{feature_id} 被机械轮转到当前句，此处仅用于验证配额指纹能够被阻断。",
                }
                for feature_id in annotation["feature_ids"]
            ]
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("配额覆盖指纹" in item for item in errors))

    def test_explicit_relation_cannot_be_declared_implicit(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        example = receipt["section_generation_plans"][0]["relation_micro_examples"][0]
        example["source_marking_mode"] = "implicit"
        example["source_markers"] = []
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("不得自报为 implicit" in item for item in errors))

    def test_relation_marker_after_open_quote_is_detected(self) -> None:
        self.assertEqual(["可"], GATE.explicit_relation_markers("我停了一下，\n「可我没答应。」"))

    def test_missing_section_generation_plan_blocks(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        receipt["section_generation_plans"].pop()
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("正文落笔前缺少小节颗粒度包" in item for item in errors))

    def test_rules_without_continuous_source_chains_block_prewrite(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        plan = receipt["section_generation_plans"][0]
        plan["continuous_source_chain_packets"] = []
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("至少需要 2 组连续原文句链" in item for item in errors))

    def test_prohibition_without_complete_negative_examples_blocks_prewrite(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        plan = receipt["section_generation_plans"][0]
        plan["contrastive_examples"] = []
        plan["manual_judgment"] = "已经写明禁止总结、禁止解释和禁止抽象对白，但没有提供完整错误句面。"
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("至少需要 2 组正反例" in item for item in errors))

    def test_missing_relation_micro_examples_blocks_prewrite(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        receipt["section_generation_plans"][0]["relation_micro_examples"] = []
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("至少需要 2 组句间关系正反例" in item for item in errors))

    def test_dialogue_rules_without_direct_source_turns_block_prewrite(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        plan = receipt["section_generation_plans"][0]
        packet = plan["dialogue_voice_packets"][0]
        packet["source_excerpt"] = self.source_text[:80]
        packet["source_dialogue_turns"] = []
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("至少 2 轮原文直接对白" in item for item in errors))

    def test_dialogue_rule_without_rehearsal_and_full_negative_blocks_prewrite(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        plan = receipt["section_generation_plans"][0]
        packet = plan["dialogue_voice_packets"][0]
        packet["target_rehearsal"] = "只写对白要自然。"
        packet["negative_example"] = "禁止功能句。"
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("至少 3 轮的当前人物自然口语试演" in item for item in errors))
        self.assertTrue(any("完整、独立且不属于主体原文的僵硬错例" in item for item in errors))

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
        self.assertEqual("pending", bound["rewrite_scope_review"]["mode"])
        self.assertIsNone(
            bound["manual_review_provenance"]["semantic_fields_generated_by_script"]
        )
        self.assertEqual("pending", bound["source_subflow_reviews"][0]["status"])
        self.assertEqual([], bound["section_reviews"][0]["dialogue_voice_reviews"])
        self.assertEqual([], bound["section_reviews"][0]["relation_micro_reviews"])

    def test_bind_draft_rebuilds_same_sha_pending_review(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        first = GATE.bind_draft(receipt, self.draft)
        first["section_reviews"][0]["target_quotes"] = ["stale pending quote"]
        rebound = GATE.bind_draft(first, self.draft)
        self.assertEqual([], rebound["section_reviews"][0]["target_quotes"])

    def test_bind_draft_preserves_same_sha_passed_review(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        first = GATE.bind_draft(receipt, self.draft)
        first["section_reviews"][0]["status"] = "passed"
        first["section_reviews"][0]["target_quotes"] = ["第一节起事。"]
        rebound = GATE.bind_draft(first, self.draft)
        self.assertEqual(
            ["第一节起事。"], rebound["section_reviews"][0]["target_quotes"]
        )

    def test_bind_draft_locates_abstract_dialogue_candidate(self) -> None:
        candidate_draft = self.root / "抽象答复正文.md"
        candidate_draft.write_text(
            "# 测试\n\n1.\n\n我伸手去拿席牌。\n\n「这种时候别只盯一张牌。」\n",
            encoding="utf-8",
        )
        receipt = self.completed_receipt(include_draft=False)
        bound = GATE.bind_draft(receipt, candidate_draft)
        grounding = bound["section_reviews"][0]["character_vitality_review"][
            "dialogue_grounding_review"
        ]
        self.assertEqual(
            ["这种时候别只盯一张牌。"], grounding["automatic_candidate_quotes"]
        )
        self.assertEqual("pending", grounding["candidate_reviews"][0]["verdict"])

    def test_functionally_compressed_dialogue_is_flagged(self) -> None:
        dialogue = "念乔刚回国，外面全是拍她的人。她坐里面安全一点，你去后排陪周姨，结束后我找你。"
        self.assertTrue(GATE.is_functionally_compressed_dialogue(dialogue))
        self.assertEqual(
            [dialogue], GATE.abstract_dialogue_candidate_quotes(f"「{dialogue}」")
        )

    def test_grounded_request_without_deferred_repair_is_not_flagged(self) -> None:
        dialogue = "外头那几台机器一直追着她拍。你先去周姨那边坐会儿，行不行？就一张合影。"
        self.assertFalse(GATE.is_functionally_compressed_dialogue(dialogue))
        self.assertEqual([], GATE.abstract_dialogue_candidate_quotes(f"「{dialogue}」"))

    def test_elliptical_question_object_is_flagged(self) -> None:
        dialogue = "我问座牌。"
        self.assertTrue(GATE.is_elliptically_compressed_question_object(dialogue))
        self.assertEqual(
            [dialogue], GATE.abstract_dialogue_candidate_quotes(f"「{dialogue}」")
        )

    def test_transfer_question_without_recipient_is_flagged(self) -> None:
        dialogue = "贺承舟，我的位置为什么要让？"
        self.assertTrue(GATE.is_transfer_target_omitted_dialogue(dialogue))
        self.assertEqual(
            [dialogue], GATE.abstract_dialogue_candidate_quotes(f"「{dialogue}」")
        )

    def test_transfer_question_with_recipient_is_not_flagged(self) -> None:
        for dialogue in (
            "贺承舟，我的位置为什么要让给她？",
            "这笔钱为什么要交给医院？",
            "我为什么要让开？",
        ):
            self.assertFalse(GATE.is_transfer_target_omitted_dialogue(dialogue))

    def test_transfer_question_with_unlisted_object_is_flagged(self) -> None:
        self.assertTrue(GATE.is_transfer_target_omitted_dialogue("我的工位为什么要腾？"))
        self.assertTrue(GATE.is_transfer_target_omitted_dialogue("这份文件凭什么交出去？"))

    def test_complete_question_and_conventional_collocation_are_not_flagged(self) -> None:
        for dialogue in (
            "我问的是座牌在哪儿。",
            "我去问路。",
            "我问清楚了。",
            "我问你为什么拦着报警。",
            "我问你知不知道覆写。",
        ):
            self.assertFalse(GATE.is_elliptically_compressed_question_object(dialogue))
            self.assertEqual([], GATE.abstract_dialogue_candidate_quotes(f"「{dialogue}」"))

    def test_signage_like_staff_dialogue_is_flagged(self) -> None:
        dialogue = "女士，合影区先别进。"
        self.assertTrue(GATE.is_signage_like_staff_dialogue(dialogue))
        self.assertEqual(
            [dialogue], GATE.abstract_dialogue_candidate_quotes(f"「{dialogue}」")
        )

    def test_staff_identity_reason_and_direction_are_not_flagged(self) -> None:
        dialogue = "不好意思，女士，这边只让主创进，观众席在后面。"
        self.assertFalse(GATE.is_signage_like_staff_dialogue(dialogue))
        self.assertEqual([], GATE.abstract_dialogue_candidate_quotes(f"「{dialogue}」"))

    def test_unlisted_staff_address_is_flagged_but_personal_request_is_not(self) -> None:
        self.assertTrue(GATE.is_signage_like_staff_dialogue("媒体朋友，采访线先别越过。"))
        self.assertFalse(GATE.is_signage_like_staff_dialogue("晚照，你现在不要走。"))

    def test_bind_draft_locates_hard_coordination_candidate(self) -> None:
        candidate_draft = self.root / "硬并列正文.md"
        bad_sentence = "她嘴上说着让我拿，手还压在林初两个字上。"
        candidate_draft.write_text(f"1.\n\n{bad_sentence}\n", encoding="utf-8")
        receipt = self.completed_receipt(include_draft=False)
        bound = GATE.bind_draft(receipt, candidate_draft)
        review = bound["section_reviews"][0]["sentence_relation_review"]
        self.assertEqual([bad_sentence], review["automatic_candidate_quotes"])
        self.assertEqual("pending", review["candidate_reviews"][0]["verdict"])

    def test_explicit_contrast_is_not_flagged_as_hard_coordination(self) -> None:
        sentence = "她嘴上说着让我拿，手却还压在林初两个字上。"
        self.assertEqual([], GATE.hard_coordination_candidate_quotes(sentence))

    def test_explanatory_evaluative_simile_is_flagged(self) -> None:
        sentence = "他说得很顺，像临时挪一把椅子。"
        self.assertEqual(
            [sentence], GATE.explanatory_narration_candidate_quotes(sentence)
        )

    def test_observable_scene_sentence_is_not_flagged_as_explanatory_simile(self) -> None:
        sentence = "他说到后排时停了一下，手却越过苏念乔，把我的外套递向最后一排。"
        self.assertEqual([], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_abstract_departure_preview_and_synonym_repeat_are_flagged(self) -> None:
        sentence = "苏念乔退出毕业纪录片项目那天，离开得很突然。"
        self.assertEqual(
            [sentence], GATE.explanatory_narration_candidate_quotes(sentence)
        )

    def test_unlisted_event_object_with_synonym_repeat_is_flagged(self) -> None:
        sentence = "他辞去监护人那天，走得很干脆。"
        self.assertEqual(
            [sentence], GATE.explanatory_narration_candidate_quotes(sentence)
        )

    def test_abstract_event_evaluation_before_concrete_evidence_is_flagged(self) -> None:
        text = "她离开得很突然。凌晨两点，她退了工作群，只留下一句要去国外读书。"
        self.assertEqual(
            ["她离开得很突然。"],
            GATE.explanatory_narration_candidate_quotes(text),
        )

    def test_concrete_departure_evidence_is_not_flagged(self) -> None:
        sentence = "凌晨两点，她退了项目工作群，只留下一句要去国外读书。"
        self.assertEqual([], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_convenient_third_party_stage_direction_is_flagged(self) -> None:
        sentence = "摄影师却正好叫他靠近苏念乔。"
        self.assertEqual(
            [sentence], GATE.explanatory_narration_candidate_quotes(sentence)
        )

    def test_direct_on_scene_instruction_is_not_flagged_as_convenient_timing(self) -> None:
        sentence = "摄影师举着相机喊：「贺老师，再往念乔那边靠一点。」他收回目光，往她身边挪了半步。"
        self.assertEqual([], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_distant_micro_expression_and_sequenced_gaze_are_flagged(self) -> None:
        sentence = "苏念乔低头笑，帽檐底下露出一点发红的眼睛。贺承舟停了一下，先看她，再往后找我。"
        self.assertEqual(
            [
                "苏念乔低头笑，帽檐底下露出一点发红的眼睛。",
                "贺承舟停了一下，先看她，再往后找我。",
            ],
            GATE.explanatory_narration_candidate_quotes(sentence),
        )

    def test_unlisted_visual_obstruction_is_flagged(self) -> None:
        sentence = "我隔着车窗，看见她眼眶发红。"
        self.assertEqual([sentence], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_observable_gesture_and_triggered_gaze_are_not_flagged(self) -> None:
        sentence = "苏念乔低下头，一只手压着帽檐，另一只手在眼角擦了一下。贺承舟说到「最重要的人」，侧过脸看她。"
        self.assertEqual([], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_abstract_response_timing_is_flagged(self) -> None:
        sentence = "他几乎立刻应了。"
        self.assertEqual(
            [sentence], GATE.explanatory_narration_candidate_quotes(sentence)
        )

    def test_long_named_response_timing_is_flagged(self) -> None:
        sentence = "贺承舟几乎立刻应了。"
        self.assertEqual([sentence], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_overlapping_action_with_audible_response_is_not_flagged(self) -> None:
        sentence = "我还握着手机，他已经在那头应她：「来了。」"
        self.assertEqual(
            ["我还握着手机，他已经在那头应她："],
            GATE.explanatory_narration_candidate_quotes(sentence),
        )

    def test_response_followed_by_disconnection_is_not_default_state_timing(self) -> None:
        sentence = "他在那头应她：「来了。」没等我开口，电话就断了。"
        self.assertEqual([], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_unlisted_default_state_object_is_flagged(self) -> None:
        sentence = "他的手还扶着方向盘，苏念乔已经推门下车。"
        self.assertEqual([sentence], GATE.explanatory_narration_candidate_quotes(sentence))

    def test_bare_transitive_action_is_flagged(self) -> None:
        self.assertEqual(
            ["苏念乔先按住了。"],
            GATE.underspecified_action_candidate_quotes("苏念乔先按住了。"),
        )
        self.assertEqual(
            [],
            GATE.underspecified_action_candidate_quotes("苏念乔把座牌往裙摆底下挪了挪。"),
        )

    def test_unlisted_bare_zhu_action_is_flagged_but_intransitive_is_not(self) -> None:
        self.assertEqual(
            ["贺承舟先扣住了。"],
            GATE.underspecified_action_candidate_quotes("贺承舟先扣住了。"),
        )
        self.assertEqual([], GATE.underspecified_action_candidate_quotes("我忍住了。"))
        self.assertEqual(
            [],
            GATE.underspecified_action_candidate_quotes("电池漏液，后盖已经锈住了。"),
        )
        self.assertEqual(
            ["苏念乔先按住了。"],
            GATE.underspecified_action_candidate_quotes("苏念乔先按住了。"),
        )

    def test_bare_stage_direction_is_flagged(self) -> None:
        self.assertEqual(
            ["我捏着牌子站直。"],
            GATE.bare_stage_direction_candidate_quotes("我捏着牌子站直。"),
        )

    def test_direction_and_obstruction_are_not_bare_stage_direction(self) -> None:
        sentence = "我拿着座牌往合影区走，刚走出过道便被工作人员拦住。"
        self.assertEqual([], GATE.bare_stage_direction_candidate_quotes(sentence))

    def test_unlisted_held_action_stage_direction_is_flagged(self) -> None:
        sentence = "她托着文件侧身。"
        self.assertEqual([sentence], GATE.bare_stage_direction_candidate_quotes(sentence))

    def test_bind_draft_locates_bare_stage_direction_candidate(self) -> None:
        candidate_draft = self.root / "空转舞台动作正文.md"
        candidate_draft.write_text("1.\n\n我捏着牌子站直。\n", encoding="utf-8")
        receipt = self.completed_receipt(include_draft=False)
        bound = GATE.bind_draft(receipt, candidate_draft)
        review = bound["section_reviews"][0]["action_continuity_review"]
        self.assertEqual(
            ["我捏着牌子站直。"], review["bare_stage_direction_candidates"]
        )
        self.assertEqual("pending", review["bare_stage_direction_reviews"][0]["verdict"])

    def test_adjacent_duplicate_action_is_flagged_for_manual_review(self) -> None:
        candidates = GATE.action_continuity_candidates(
            "她站了起来。\n他也站了起来。"
        )
        self.assertEqual("站了起来", candidates[0]["verb"])
        self.assertEqual("她站了起来。", candidates[0]["previous"])
        self.assertEqual("他也站了起来。", candidates[0]["current"])

    def test_dialogue_grounding_review_is_required(self) -> None:
        receipt = self.completed_receipt()
        del receipt["section_reviews"][0]["character_vitality_review"][
            "dialogue_grounding_review"
        ]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("dialogue_grounding_review 缺失" in item for item in errors))

    def test_candidate_zero_is_not_a_dialogue_pass(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["character_vitality_review"][
            "dialogue_grounding_review"
        ]["candidate_zero_is_not_pass"] = False
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("candidate_zero_is_not_pass" in item for item in errors))

    def test_every_direct_dialogue_turn_requires_an_explicit_review(self) -> None:
        receipt = self.completed_receipt()
        grounding = receipt["section_reviews"][0]["character_vitality_review"][
            "dialogue_grounding_review"
        ]
        grounding["full_dialogue_reviews"] = grounding["full_dialogue_reviews"][:-1]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("逐条覆盖本节全部直接对白" in item for item in errors))

    def test_full_dialogue_review_requires_time_object_and_reply_checks(self) -> None:
        receipt = self.completed_receipt()
        item = receipt["section_reviews"][0]["character_vitality_review"][
            "dialogue_grounding_review"
        ]["full_dialogue_reviews"][0]
        item["time_state_fit"] = ""
        item["object_and_result_complete"] = ""
        item["participant_role_direction"] = ""
        item["adjacency_or_reply_fit"] = ""
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("time_state_fit" in error for error in errors))
        self.assertTrue(any("object_and_result_complete" in error for error in errors))
        self.assertTrue(any("participant_role_direction" in error for error in errors))
        self.assertTrue(any("adjacency_or_reply_fit" in error for error in errors))

    def test_bind_draft_scaffolds_every_direct_dialogue_turn(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        bound = GATE.bind_draft(receipt, self.draft)
        sections = GATE.extract_sections(self.draft.read_text(encoding="utf-8"))
        for review in bound["section_reviews"]:
            section_id = review["section_id"]
            grounding = review["character_vitality_review"][
                "dialogue_grounding_review"
            ]
            self.assertEqual(
                GATE.dialogue_turn_units(sections[section_id]),
                [item["quote"] for item in grounding["full_dialogue_reviews"]],
            )

    def test_dialogue_turn_units_supports_all_chinese_quote_styles(self) -> None:
        text = "「第一轮对白。」\n“第二轮对白。”\n『第三轮对白。』"
        self.assertEqual(
            ["「第一轮对白。」", "“第二轮对白。”", "『第三轮对白。』"],
            GATE.dialogue_turn_units(text),
        )

    def test_full_rewrite_requires_every_section_and_two_full_reads(self) -> None:
        receipt = self.completed_receipt()
        scope = receipt["rewrite_scope_review"]
        scope.update(
            {
                "mode": "full_rewrite",
                "full_rewrite_requested": True,
                "rewritten_section_ids": ["1"],
                "unchanged_section_ids": ["2"],
                "full_text_read_before_rewrite": False,
            }
        )
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("全文重写必须按顺序覆盖" in item for item in errors))
        self.assertTrue(any("全文重写前必须完整通读" in item for item in errors))
        self.assertTrue(any("不得保留 unchanged_section_ids" in item for item in errors))

    def test_full_rewrite_scope_passes_when_every_section_is_covered(self) -> None:
        receipt = self.completed_receipt()
        receipt["rewrite_scope_review"].update(
            {
                "mode": "full_rewrite",
                "full_rewrite_requested": True,
                "rewritten_section_ids": ["1", "2"],
                "unchanged_section_ids": [],
                "full_text_read_before_rewrite": True,
                "full_text_read_after_rewrite": True,
                "manual_judgment": "重写前后均完整通读，两节全部重新落笔并逐节复核，没有保留未改小节。",
            }
        )
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertEqual([], errors)

    def test_script_generated_semantic_receipt_is_blocked(self) -> None:
        receipt = self.completed_receipt()
        receipt["manual_review_provenance"][
            "semantic_fields_generated_by_script"
        ] = True
        receipt["manual_review_provenance"]["automation_artifacts_used"] = [
            "record_draft_section.py"
        ]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("禁止项目脚本生成" in item for item in errors))
        self.assertTrue(any("受控自动化类别" in item for item in errors))

    def test_nonsemantic_automation_provenance_is_allowed(self) -> None:
        receipt = self.completed_receipt()
        receipt["manual_review_provenance"]["automation_artifacts_used"] = [
            "candidate_localization",
            "sha_binding",
            "schema_initialization",
            "deterministic_serialization",
        ]
        errors, summary = GATE.validate_draft_data(
            receipt, self.source, self.draft
        )
        self.assertEqual([], errors)
        self.assertEqual(2, summary["passed_sections"])

    def test_semantic_automation_provenance_is_blocked(self) -> None:
        receipt = self.completed_receipt()
        receipt["manual_review_provenance"]["automation_artifacts_used"] = [
            "automatic_quote_selection"
        ]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("自动语义生成产物" in item for item in errors))

    def test_dialogue_review_requires_role_substitution_and_context_window(self) -> None:
        receipt = self.completed_receipt()
        dialogue_review = receipt["section_reviews"][0]["dialogue_voice_reviews"][0]
        dialogue_review["role_substitution_test"] = ""
        dialogue_review["context_window_reviewed"] = ""
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("role_substitution_test" in item for item in errors))
        self.assertTrue(any("context_window_reviewed" in item for item in errors))

    def test_relation_micro_reviews_are_required(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["relation_micro_reviews"] = []
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("句间关系与虚词骨架消费复核" in item for item in errors))

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

    def test_action_candidate_review_map_does_not_hide_later_sections(self) -> None:
        receipt = self.completed_receipt()
        first_section = GATE.extract_sections(
            self.draft.read_text(encoding="utf-8")
        )["1"]
        receipt["section_reviews"][0]["action_continuity_review"] = {
            "underspecified_action_candidates": GATE.underspecified_action_candidate_quotes(
                first_section
            ),
            "underspecified_action_reviews": [],
            "bare_stage_direction_candidates": GATE.bare_stage_direction_candidate_quotes(
                first_section
            ),
            "bare_stage_direction_reviews": [],
            "repeated_action_candidates": GATE.action_continuity_candidates(first_section),
            "repeated_action_reviews": [],
            "reviewed_full_section": True,
            "manual_judgment": "第一节已逐句检查动作执行者、对象与相邻动作连续性。",
        }
        receipt["section_reviews"][1]["status"] = "pending"
        errors, summary = GATE.validate_draft_data(
            receipt, self.source, self.draft
        )
        self.assertTrue(any("文字颗粒度未通过: 2" in item for item in errors))
        self.assertEqual(1, summary["passed_sections"])

    def test_manual_sidecar_preflight_blocks_stale_quotes_and_templates(self) -> None:
        receipt = self.completed_receipt()
        sidecar = {
            "draft_sha256": GATE.sha256(self.draft),
            "section_reviews": [
                {
                    "section_id": "1",
                    "target_quotes": ["旧版本里才有的句子。"],
                    "comparison": "同一套模板化句面对照说明。",
                },
                {
                    "section_id": "2",
                    "target_quotes": ["她先哭了。"],
                    "comparison": "同一套模板化句面对照说明。",
                },
            ],
        }
        errors, summary = GATE.preflight_manual_sidecar_data(
            receipt, sidecar, self.draft
        )
        self.assertEqual(2, summary["sidecar_sections"])
        self.assertTrue(any("目标引句不在绑定小节" in item for item in errors))
        self.assertTrue(any("模板化 comparison" in item for item in errors))

    def test_manual_sidecar_preflight_accepts_current_bound_quotes(self) -> None:
        receipt = self.completed_receipt()
        sidecar = {
            "draft_sha256": GATE.sha256(self.draft),
            "section_reviews": [
                {
                    "section_id": "1",
                    "target_quotes": ["「钥匙给我。」"],
                    "comparison": "第一节用直接索取钥匙落下人物当前控制目标。",
                },
                {
                    "section_id": "2",
                    "target_quotes": ["她先哭了。"],
                    "comparison": "第二节以哭声抢先改变话轮并触发叙述者当场判断。",
                },
            ],
        }
        errors, summary = GATE.preflight_manual_sidecar_data(
            receipt, sidecar, self.draft
        )
        self.assertEqual([], errors)
        self.assertEqual(2, summary["sidecar_sections"])

    def test_contract_must_be_used_during_writing(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["sentence_mappings"][0][
            "contract_used_during_writing"
        ] = False
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("contract_used_during_writing" in item for item in errors))

    def test_mapping_target_evidence_must_match_current_target_sentence(self) -> None:
        receipt = self.completed_receipt()
        mapping = receipt["section_reviews"][0]["sentence_mappings"][0]
        mapping["target_surface_evidence"] = "他伸手拦我"
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("当前目标句自身证据" in item for item in errors))

    def test_mapping_mechanism_must_quote_both_local_evidences(self) -> None:
        receipt = self.completed_receipt()
        mapping = receipt["section_reviews"][0]["sentence_mappings"][0]
        mapping["language_mechanism_match"] = "这句话保留了主体原文的现场关系和自然口语颗粒。"
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("同时引用目标句与源锚局部证据" in item for item in errors))

    def test_mapping_feature_ids_must_belong_to_source_anchor(self) -> None:
        receipt = self.completed_receipt()
        mapping = receipt["section_reviews"][0]["sentence_mappings"][0]
        source_anchor = mapping["source_anchor_sentence"]
        annotated_ids = {
            feature_id
            for passage in receipt["ultra_fine_source_baseline"]["source_passages"]
            for annotation in passage["sentence_annotations"]
            if annotation["source_sentence"] == source_anchor
            for feature_id in annotation["feature_ids"]
        }
        foreign_id = next(
            feature_id for feature_id in GATE.ULTRA_FINE_FEATURE_IDS if feature_id not in annotated_ids
        )
        mapping["feature_ids"] = [mapping["feature_ids"][0], foreign_id]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("必须属于 source_anchor_sentence" in item for item in errors))

    def test_minimal_function_sentence_revise_blocks_draft(self) -> None:
        receipt = self.completed_receipt()
        mapping = next(
            item
            for review in receipt["section_reviews"]
            for item in review["sentence_mappings"]
            if GATE.is_minimal_function_sentence(item["target_sentence"])
        )
        mapping["minimal_function_sentence_review"]["verdict"] = "revise"
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("极短功能句仍需先修改正文" in item for item in errors))

    def test_character_evidence_requires_owner_context(self) -> None:
        receipt = self.completed_receipt()
        ownership = receipt["section_reviews"][1]["character_vitality_review"][
            "character_reviews"
        ][1]["evidence_ownership_reviews"][0]
        ownership["owner_name"] = "林初"
        ownership["marker_refers_to_owner"] = False
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("owner_name 必须等于当前人物" in item for item in errors))
        self.assertTrue(any("marker_refers_to_owner 必须为 true" in item for item in errors))

    def test_section_automated_semantic_judgment_blocks(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["automation_used_for_semantic_judgment"] = True
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("正文小节禁止用自动脚本生成语义裁决" in item for item in errors))

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

    def test_interchangeable_character_profiles_block_prewrite(self) -> None:
        receipt = self.completed_receipt(include_draft=False)
        profiles = receipt["character_personality_layer"]["target_character_profiles"]
        for field in ("defense_strategy", "speech_pattern", "action_bias", "self_contradiction"):
            profiles[1][field] = profiles[0][field]
        errors, _ = GATE.validate_prewrite_data(receipt, self.source, self.outline)
        self.assertTrue(any("不得复用同一性格壳" in item for item in errors))

    def test_functional_character_residue_blocks_draft(self) -> None:
        receipt = self.completed_receipt()
        receipt["section_reviews"][0]["character_vitality_review"][
            "functional_character_residue"
        ] = ["周远仍只负责递出错误答案"]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("仍有人物只承担" in item for item in errors))

    def test_missing_character_arc_blocks_draft(self) -> None:
        receipt = self.completed_receipt()
        receipt["character_arc_reviews"] = receipt["character_arc_reviews"][:1]
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("全文人物性格弧 周远 缺失" in item for item in errors))

    def test_changed_draft_invalidates_contract(self) -> None:
        receipt = self.completed_receipt()
        self.draft.write_text(self.draft.read_text(encoding="utf-8") + "又一句。", encoding="utf-8")
        errors, _ = GATE.validate_draft_data(receipt, self.source, self.draft)
        self.assertTrue(any("正文已变化" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
