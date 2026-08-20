from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "batch_outline_release.py"
SPEC = importlib.util.spec_from_file_location("batch_outline_release", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class BatchOutlineReleaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "拆文库" / "样本"
        self.project_root = self.root / "测试项目"
        self.config = self.project_root / "写作资产" / "项目写作配置.json"
        self.setting = self.project_root / "设定.md"
        self.outline = self.project_root / "小节大纲.md"
        self.outline_receipt = self.project_root / "写作资产" / "细纲表演验收回执.json"
        self.source_original = self.source / "原文" / "样本.txt"
        self.source_profile = self.source / "book.profile.json"

        self._build_outline_support_assets()
        self.setting.parent.mkdir(parents=True, exist_ok=True)
        self.setting.write_text("设定内容", encoding="utf-8")
        self.outline.write_text(
            "# 标题\n\n"
            "## 导语\n\n"
            "- 主事件：开场。\n"
            "- 子事件：开场细节。\n"
            "- 细拍拆分：开场动作。\n"
            "- 情绪：悬念。\n"
            "- 读者新获知什么：关系异常。\n"
            "- 钩子：下一步。\n"
            "- 伏笔/物件：钥匙。\n"
            "- 动静：静。\n"
            "- 对话密度：低。\n"
            "- 目标字数：100-200字。\n"
            "- 场面单元：门口起事。\n\n"
            "## 1. 起事\n\n"
            "- 主事件：起事。\n"
            "- 子事件：关系变化。\n"
            "- 细拍拆分：他先伸手拦我，我把他的手推开。\n"
            "- 情绪：刺痛。\n"
            "- 读者新获知什么：他先解释别人。\n"
            "- 钩子：门会不会关。\n"
            "- 伏笔/物件：钥匙。\n"
            "- 动静：先动后静。\n"
            "- 对话密度：中。\n"
            "- 目标字数：500-700字。\n"
            "- 场面单元：门口争执。\n\n"
            "## 尾声\n\n"
            "- 主事件：门关上。\n"
            "- 子事件：关系结束。\n"
            "- 细拍拆分：最后门关上了。\n"
            "- 情绪：决绝。\n"
            "- 读者新获知什么：关系结束。\n"
            "- 钩子：无。\n"
            "- 伏笔/物件：门。\n"
            "- 动静：静。\n"
            "- 对话密度：低。\n"
            "- 目标字数：100-200字。\n"
            "- 场面单元：门外收束。\n",
            encoding="utf-8",
        )
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(
            json.dumps(
                {
                    "project_name": "测试项目",
                    "primary": {
                        "name": "样本",
                        "original_path": str(self.source_original),
                        "profile_path": str(self.source_profile),
                    },
                    "auxiliaries": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fill_sf_performance_binding(self, template: dict, target_id: str) -> None:
        binding = template["sf_performance_bindings"][0]
        binding["required_sequence_target_ids"] = [
            [target_id] for _ in binding["required_sequence_target_ids"]
        ]
        binding["emotion_sequence_target_ids"] = [
            [target_id] for _ in binding["emotion_sequence_target_ids"]
        ]
        binding["scene_granularity_target_ids"] = [target_id]
        for index, layer in enumerate(
            binding["source_layer_target_bindings"], start=1
        ):
            layer["target_ids"] = [target_id]
            layer["adaptation_instruction"] = (
                f"第{index}层保持来源现场后切入叙述者判断的层型、连接和气口，只替换事件壳。"
            )

    def _build_outline_support_assets(self) -> None:
        plot_ledger = self.source / "写作资产" / "全文情节微拍总账.json"
        emotion_ledger = self.source / "写作资产" / "全文情绪颗粒总账.json"
        bridge_catalog = self.source / "写作资产" / "桥段施工卡.md"
        subflow_catalog = self.source / "写作资产" / "子流程索引.jsonl"
        story_report = self.source / "拆文报告.md"
        emotion_motherline = self.source / "写作资产" / "情绪母线.md"
        self.source_original.parent.mkdir(parents=True, exist_ok=True)
        plot_ledger.parent.mkdir(parents=True, exist_ok=True)
        self.source_original.write_text(
            "原文场面里，他先伸手拦我，我把他的手推开。"
            "我没想到他还会替别人解释。\n"
            "解释什么？"
            "钥匙放在桌上，她先拿走了。"
            "\n"
            "有意思，现在倒像是我进错了门。"
            "最后门关上了。",
            encoding="utf-8",
        )

        plot_ledger.write_text(
            json.dumps(
                {
                    "schema_version": GATE.OUTLINE.FULL_BRIDGE_PLOT_LEDGER_SCHEMA,
                    "beats": [
                        {
                            "beat_id": "P-001",
                            "actor": "他",
                            "action": "伸手拦住",
                            "object_or_receiver": "我",
                            "pressure_or_trigger": "我准备离开",
                            "control_change": "他试图拦截",
                            "information_change": "我意识到他仍先解释别人",
                            "consequence": "关系掉位",
                            "source_range": {"start_line": 1, "end_line": 1},
                            "source_evidence": "原文场面里，他先伸手拦我，我把他的手推开。",
                            "bid_ids": ["BID-01"],
                        }
                    ],
                    "coverage_segments": [{"segment_id": "SEG-01", "beat_ids": ["P-001"]}],
                    "source_plot_candidate_audit": [{"candidate_id": "PC-001"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        emotion_ledger.write_text(
            json.dumps(
                {
                    "schema_version": "story-short-analyze.full-text-emotion-ledger.v2",
                    "beats": [
                        {
                            "beat_id": "E-001",
                            "role": "第一次刺痛",
                            "content": "先护别人",
                            "trigger": "他先解释别人",
                            "relationship_position_change": "我掉位",
                            "reader_effect": "刺痛",
                            "narrative_function": "推进离开",
                            "intensity": 8,
                            "source_evidence": ["我没想到他还会替别人解释。"],
                            "bid_ids": ["BID-01"],
                        }
                    ],
                    "coverage_segments": [{"segment_id": "SEG-01", "beat_ids": ["E-001"]}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        bridge_catalog.write_text(
            "## BID-01\n\n桥段说明\n",
            encoding="utf-8",
        )
        story_report.write_text(
            "# 拆文报告\n\n## 故事核\n\n关系中的公开掉位最终迫使主角离开。\n",
            encoding="utf-8",
        )
        emotion_motherline.write_text(
            "从被优先保护的关系位置跌落，经由公开刺痛确认失去资格，最终主动离开并关闭关系入口。\n",
            encoding="utf-8",
        )
        self.source_profile.write_text(
            json.dumps(
                {
                    "bridge_rules": [
                        {
                            "id": "BID-01",
                            "must_keep": ["公开掉位", "主动离开"],
                            "emotion_sequence": [
                                {
                                    "beat_id": "E-001",
                                    "role": "第一次刺痛",
                                    "content": "先护别人",
                                    "intensity": 8,
                                    "source_evidence": "我没想到他还会替别人解释。",
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        subflow_catalog.write_text(
            json.dumps(
                {
                    "schema_version": GATE.OUTLINE.SUBFLOW_VALIDATOR.SCHEMA_VERSION,
                    "subflow_id": "SF-01",
                    "parent_bridge_id": "BID-01",
                    "source_range": "L1-L3",
                    "entry_state": "我准备离开，他仍试图拦住我。",
                    "required_sequence": [
                        "他先伸手阻拦。",
                        "我推开后发现他仍替别人解释。",
                        "钥匙被拿走，门最终关上。",
                    ],
                    "scene_granularity": "伸手、推开、错答、拿钥匙和关门连续发生。",
                    "emotion_sequence": ["受阻", "错愕", "讥讽", "决绝"],
                    "end_state": "我确认自己掉位并离开。",
                    "source_excerpt": (
                        "原文场面里，他先伸手拦我，我把他的手推开。我没想到他还会替别人解释。\n"
                        "解释什么？钥匙放在桌上，她先拿走了。\n"
                        "有意思，现在倒像是我进错了门。最后门关上了。"
                    ),
                    "source_layer_order": ["SF-01-L01"],
                    "source_layer_topology": [
                        {
                            "layer_id": "SF-01-L01",
                            "source_range": "L1-L3",
                            "source_text": (
                                "原文场面里，他先伸手拦我，我把他的手推开。我没想到他还会替别人解释。\n"
                                "解释什么？钥匙放在桌上，她先拿走了。\n"
                                "有意思，现在倒像是我进错了门。最后门关上了。"
                            ),
                            "layer_modes": ["live_scene", "narrator_interjection"],
                            "layer_role": "阻拦、推开、错答、拿走钥匙和关门连续推进，叙述者在动作链中插入掉位判断。",
                            "entry_relation": "从叙述者准备离开、对方试图阻止的进入态直接起现场。",
                            "exit_relation": "以钥匙换手和门关上结束关系权限，不再补解释。",
                            "narrative_distance": "近景跟随手部动作和短对白，中间只短促插入第一人称判断。",
                            "dimension_realization": {
                                "narrative_voice_and_attitude": {"status": "active", "how": "叙述者在被阻拦时直接判断自己掉位。", "source_evidence": ["我没想到他还会替别人解释。"]},
                                "sentence_relation_and_rhythm": {"status": "active", "how": "阻拦、推开、错答、拿钥匙与关门按动作先后紧接。", "source_evidence": ["最后门关上了。"]},
                                "paragraph_breath_and_cut_points": {"status": "active", "how": "三行分别承担冲突、物件换手和叙述者判词后的关门。", "source_evidence": ["解释什么？"]},
                                "dialogue_misfire_or_avoidance": {"status": "active", "how": "追问没有获得解释，下一动作直接拿走钥匙。", "source_evidence": ["解释什么？"]},
                                "action_perception_emotion_weave": {"status": "active", "how": "推手、拿钥匙与关门让掉位通过动作可见。", "source_evidence": ["钥匙放在桌上，她先拿走了。"]},
                                "narrator_interjection_and_roughness": {"status": "active", "how": "叙述者用有意思即时插嘴，把门内位置判成走错门。", "source_evidence": ["有意思，现在倒像是我进错了门。"]}
                            },
                            "must_preserve_in_target": ["保持近景动作链中插入短促判断，并以关门动作直接切断。"]
                        }
                    ],
                    "source_style_granularity": {
                        "narrative_voice_and_attitude": [{"evidence": "我没想到"}],
                        "sentence_relation_and_rhythm": [{"evidence": "先拦后推"}],
                        "paragraph_breath_and_cut_points": [{"evidence": "动作紧接"}],
                        "dialogue_misfire_or_avoidance": [{"evidence": "解释什么？"}],
                        "action_perception_emotion_weave": [{"evidence": "伸手拦我"}],
                        "narrator_interjection_and_roughness": [{"evidence": "有意思"}],
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_start_outline_release_creates_only_outline_contract(self) -> None:
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
            force=False,
        )
        self.assertEqual([], errors)
        self.assertTrue(self.outline_receipt.is_file())
        self.assertEqual(str(self.outline_receipt), summary["outline_receipt"])
        payload = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            list(GATE.OUTLINE.SOURCE_STYLE_GRANULARITY_FIELDS),
            payload["granularity_coverage"][0]["style_dimensions"],
        )
        requirements = payload["granularity_coverage"][0]["dimension_requirements"]
        self.assertEqual(
            set(GATE.OUTLINE.SOURCE_STYLE_GRANULARITY_FIELDS),
            set(requirements),
        )
        self.assertEqual(
            ["我没想到"],
            requirements["narrative_voice_and_attitude"]["source_evidence"],
        )
        performance = payload["granularity_coverage"][0][
            "performance_requirements"
        ]
        self.assertEqual(3, len(performance["required_sequence"]))
        self.assertIn("解释什么？", performance["source_excerpt"])
        self.assertEqual(
            [], payload["granularity_coverage"][0]["target_performance_carriers"]
        )
        self.assertEqual([], payload["granularity_coverage"][0]["target_regions"])
        self.assertTrue(payload["sources"][0]["subflow_catalog"]["sha256"])
        self.assertEqual(["BID-01"], payload["source_hierarchy"]["bridge_order"])
        self.assertEqual(
            ["SRC-PRIMARY:P-001"],
            payload["source_hierarchy"]["bridges"][0]["source_plot_refs"],
        )
        assets = self.project_root / "写作资产"
        self.assertEqual(
            {"项目写作配置.json", "细纲表演验收回执.json"},
            {path.name for path in assets.iterdir()},
        )

    def test_noncurrent_outline_contract_blocks_without_overwrite(self) -> None:
        self.outline_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.outline_receipt.write_text('{"marker": "preserve"}', encoding="utf-8")
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
            force=False,
        )
        self.assertTrue(errors)
        self.assertFalse(summary["outline_ready"])
        self.assertEqual(
            {"marker": "preserve"},
            json.loads(self.outline_receipt.read_text(encoding="utf-8")),
        )

    def test_current_outline_contract_is_resumed_without_overwrite(self) -> None:
        errors, _ = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )
        self.assertEqual([], errors)
        payload = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        payload["marker"] = "preserve"
        self.outline_receipt.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )
        self.assertEqual([], errors)
        self.assertTrue(summary["resumed_existing"])
        self.assertEqual(
            "preserve",
            json.loads(self.outline_receipt.read_text(encoding="utf-8"))["marker"],
        )

    def test_force_rebuilds_outline_contract(self) -> None:
        self.outline_receipt.parent.mkdir(parents=True, exist_ok=True)
        self.outline_receipt.write_text('{"marker": "old"}', encoding="utf-8")
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
            force=True,
        )
        self.assertEqual([], errors)
        self.assertFalse(summary["resumed_existing"])
        payload = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        self.assertEqual("测试项目", payload["project"])

    def test_apply_template_removes_merged_sidecar(self) -> None:
        errors, _ = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )
        self.assertEqual([], errors)
        sidecar = self.project_root / "写作资产" / "纲层迁移侧车.json"
        template = GATE.OUTLINE.export_template(self.outline_receipt, sidecar)
        receipt = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        target_id = receipt["outline_catalog"]["regions"][0]["target_beats"][0]["target_id"]
        template["mapping"]["primary_plot_targets"] = [target_id]
        template["mapping"]["primary_emotion_targets"] = [target_id]
        self.fill_sf_performance_binding(template, target_id)
        template["hot_news_materials"] = [
            {
                "news_id": "HN-001",
                "material_type": "social_news",
                "title": "平台紧急授权规则调整引发关注",
                "publisher": "测试新闻社",
                "published_at": "2026-08-10",
                "retrieved_at": "2026-08-19",
                "url": "https://news.example.com/rule-change",
                "social_heat_signal": "该话题进入平台热榜后由多家媒体连续跟进并引发讨论",
                "transferable_mechanism": "紧急权限只能授予一人，系统记录会公开固化谁被优先选择",
                "fact_boundary": "只采用权限排他和系统留痕机制，人物、机构、时间线与具体结果全部虚构化处理",
            }
        ]
        template["p_beat_replacements"][0].update(
            {
                "preserved_function": "保留关系中公开掉位并推动离开的承重功能",
                "changed_dimensions": [
                    "occupation_domain",
                    "setting",
                    "evidence",
                    "consequence",
                ],
                "news_ids": ["HN-001"],
                "adaptation_judgment": "目标细拍改用平台紧急授权和系统记录制造公开掉位，人物职业、现场证据与现实后果均已脱离原文门口阻拦事件。",
            }
        )
        template["manual_confirmation"] = {
            "full_story_hierarchy_preserved": True,
            "primary_plot_slots_replaced_one_to_one_and_in_order": True,
            "primary_emotion_complete_and_in_order": True,
            "auxiliary_is_plot_mechanism_only": True,
            "primary_is_exclusive_prose_voice": True,
            "primary_full_prose_granularity_loaded": True,
            "source_event_shell_rejected": True,
            "hot_news_is_event_mechanism_only": True,
            "manual_judgment": "主体关系层级、情绪和文字颗粒均已逐项核对；全部 P 拍只保留承重功能并换成新的现实事件，热点只供应机制。",
        }
        sidecar.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")

        GATE.OUTLINE.apply_template(self.outline_receipt, sidecar)

        self.assertFalse(sidecar.exists())
        merged = json.loads(self.outline_receipt.read_text(encoding="utf-8"))
        self.assertEqual("passed", merged["gate_status"])
        self.assertEqual(target_id, merged["p_beat_replacements"][0]["target_id"])
        self.assertEqual("HN-001", merged["hot_news_materials"][0]["news_id"])

    def test_apply_template_without_hot_news_passes(self) -> None:
        errors, _ = GATE.start_outline_release(
            project="测试项目", project_dir=self.project_root
        )
        self.assertEqual([], errors)
        sidecar = self.project_root / "写作资产" / "纲层迁移侧车.json"
        template = GATE.OUTLINE.export_template(self.outline_receipt, sidecar)
        target_id = template["target_catalog"][0]["target_beats"][0]["target_id"]
        template["mapping"]["primary_plot_targets"] = [target_id]
        template["mapping"]["primary_emotion_targets"] = [target_id]
        self.fill_sf_performance_binding(template, target_id)
        template["p_beat_replacements"][0].update(
            {
                "preserved_function": "保留关系中公开掉位并推动离开的承重功能",
                "changed_dimensions": ["setting", "trigger", "consequence"],
                "news_ids": [],
                "adaptation_judgment": "目标细拍改用全新虚构场景、触发方式与现实后果制造同一关系位移，已经脱离原文人物动作、职业现场和物件链。",
            }
        )
        template["manual_confirmation"] = {
            "full_story_hierarchy_preserved": True,
            "primary_plot_slots_replaced_one_to_one_and_in_order": True,
            "primary_emotion_complete_and_in_order": True,
            "auxiliary_is_plot_mechanism_only": True,
            "primary_is_exclusive_prose_voice": True,
            "primary_full_prose_granularity_loaded": True,
            "source_event_shell_rejected": True,
            "hot_news_is_event_mechanism_only": None,
            "manual_judgment": "主体关系层级、情绪和文字颗粒均已逐项核对；全部 P 拍只保留承重功能并换成新的虚构现实事件，本次未使用热点新闻。",
        }
        sidecar.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")

        merged = GATE.OUTLINE.apply_template(self.outline_receipt, sidecar)

        self.assertEqual("passed", merged["gate_status"])
        self.assertEqual([], merged["hot_news_materials"])
        self.assertEqual([], merged["p_beat_replacements"][0]["news_ids"])

    def test_missing_sf_step_binding_blocks_before_draft_release(self) -> None:
        errors, _ = GATE.start_outline_release(
            project="测试项目", project_dir=self.project_root
        )
        self.assertEqual([], errors)
        sidecar = self.project_root / "写作资产" / "纲层迁移侧车.json"
        template = GATE.OUTLINE.export_template(self.outline_receipt, sidecar)
        target_id = template["target_catalog"][0]["target_beats"][0]["target_id"]
        template["mapping"]["primary_plot_targets"] = [target_id]
        template["mapping"]["primary_emotion_targets"] = [target_id]
        template["p_beat_replacements"][0].update(
            {
                "preserved_function": "保留关系中公开掉位并推动离开的承重功能",
                "changed_dimensions": ["setting", "trigger", "consequence"],
                "news_ids": [],
                "adaptation_judgment": "目标细拍已替换场景、触发和后果，但故意不填写 SF 写前逐步承载，用于验证正文放行前阻断。",
            }
        )
        template["manual_confirmation"] = {
            "full_story_hierarchy_preserved": True,
            "primary_plot_slots_replaced_one_to_one_and_in_order": True,
            "primary_emotion_complete_and_in_order": True,
            "auxiliary_is_plot_mechanism_only": True,
            "primary_is_exclusive_prose_voice": True,
            "primary_full_prose_granularity_loaded": True,
            "source_event_shell_rejected": True,
            "hot_news_is_event_mechanism_only": None,
            "manual_judgment": "主体层级和 P 拍换芯已确认，本用例只验证遗漏 SF 逐步目标承载时不能合并合同。",
        }
        sidecar.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "以下步骤必须绑定目标细拍"):
            GATE.OUTLINE.apply_template(self.outline_receipt, sidecar)

    def test_p_replacement_without_event_shell_change_blocks(self) -> None:
        errors, _ = GATE.start_outline_release(
            project="测试项目", project_dir=self.project_root
        )
        self.assertEqual([], errors)
        sidecar = self.project_root / "写作资产" / "纲层迁移侧车.json"
        template = GATE.OUTLINE.export_template(self.outline_receipt, sidecar)
        target_id = template["target_catalog"][0]["target_beats"][0]["target_id"]
        template["mapping"]["primary_plot_targets"] = [target_id]
        template["mapping"]["primary_emotion_targets"] = [target_id]
        template["p_beat_replacements"][0]["preserved_function"] = "保留关系公开掉位并推动离开的功能"
        template["p_beat_replacements"][0]["changed_dimensions"] = ["object"]
        template["p_beat_replacements"][0]["adaptation_judgment"] = "只换了一个物件，其余人物动作、现场和结果都沿用了原文事件，因此必须被阻断。"
        sidecar.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "至少替换三个事件壳维度"):
            GATE.OUTLINE.apply_template(self.outline_receipt, sidecar)

    def test_source_change_after_export_invalidates_old_sidecar(self) -> None:
        errors, _ = GATE.start_outline_release(
            project="测试项目", project_dir=self.project_root
        )
        self.assertEqual([], errors)
        sidecar = self.project_root / "写作资产" / "纲层迁移侧车.json"
        GATE.OUTLINE.export_template(self.outline_receipt, sidecar)
        profile = json.loads(self.source_profile.read_text(encoding="utf-8"))
        profile["updated_after_export"] = True
        self.source_profile.write_text(
            json.dumps(profile, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "来源资产已变更"):
            GATE.OUTLINE.apply_template(self.outline_receipt, sidecar)

    def test_project_name_mismatch_blocks(self) -> None:
        errors, summary = GATE.start_outline_release(
            project="另一项目",
            project_dir=self.project_root,
        )
        self.assertTrue(errors)
        self.assertFalse(summary["outline_ready"])

    def test_missing_primary_style_dimension_blocks(self) -> None:
        subflow_catalog = self.source / "写作资产" / "子流程索引.jsonl"
        payload = json.loads(subflow_catalog.read_text(encoding="utf-8"))
        del payload["source_style_granularity"]["narrator_interjection_and_roughness"]
        subflow_catalog.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )
        self.assertTrue(errors)
        self.assertFalse(summary["outline_ready"])
        self.assertIn("narrator_interjection_and_roughness", errors[0])

    def test_missing_whole_performance_chain_blocks_before_outline_contract(self) -> None:
        subflow_catalog = self.source / "写作资产" / "子流程索引.jsonl"
        payload = json.loads(subflow_catalog.read_text(encoding="utf-8"))
        del payload["required_sequence"]
        subflow_catalog.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        errors, summary = GATE.start_outline_release(
            project="测试项目",
            project_dir=self.project_root,
        )

        self.assertTrue(errors)
        self.assertFalse(summary["outline_ready"])
        self.assertIn("required_sequence", errors[0])


if __name__ == "__main__":
    unittest.main()
