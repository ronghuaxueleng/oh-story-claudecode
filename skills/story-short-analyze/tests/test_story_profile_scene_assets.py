from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


GENERATOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "story-short-write"
    / "scripts"
    / "generate_story_profile.py"
)
SPEC = importlib.util.spec_from_file_location("story_profile_generator", GENERATOR_PATH)
assert SPEC and SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)

AUDIT_PATH = (
    Path(__file__).resolve().parents[2]
    / "story-short-write"
    / "scripts"
    / "run_full_ai_audit.py"
)
AUDIT_SPEC = importlib.util.spec_from_file_location("story_full_audit", AUDIT_PATH)
assert AUDIT_SPEC and AUDIT_SPEC.loader
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)

VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_short_analyze_outputs.py"
)
VALIDATOR_SPEC = importlib.util.spec_from_file_location("story_short_validator", VALIDATOR_PATH)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class StoryProfileSceneAssetsTest(unittest.TestCase):
    def test_dynamic_signal_dictionary_generates_precheck_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "原文").mkdir()
            (root / "写作资产").mkdir()
            (root / "原文" / "正文.txt").write_text(
                "她把风险复核表压在桌上，又降下车窗。",
                encoding="utf-8",
            )
            (root / "写作资产" / "本书动态信号字典.json").write_text(
                json.dumps(
                    {
                        "categories": {
                            "证据载体": [{"term": "风险复核表"}],
                            "动作与微动作": [{"term": "降下车窗"}],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            overrides = GENERATOR.collect_dynamic_precheck_overrides(root)
            self.assertEqual(["风险复核表"], overrides["fact_anchor_patterns"])
            self.assertEqual(["降下车窗"], overrides["action_anchor_patterns"])

    def test_event_assets_keep_verbs_and_long_phrases(self) -> None:
        assets = GENERATOR.clean_scene_asset_terms(
            [
                "宋远让董事会撤掉周逢雅的代言并收回资源",
                "匿名视频公开后婚礼秩序当场翻转",
            ]
        )
        self.assertEqual(
            [
                "宋远让董事会撤掉周逢雅的代言并收回资源",
                "匿名视频公开后婚礼秩序当场翻转",
            ],
            assets,
        )

    def test_event_assets_do_not_split_complete_chinese_enumeration(self) -> None:
        assets = GENERATOR.clean_scene_asset_terms(
            ["记者、警方、司法依次接管公开场后的后果链"]
        )
        self.assertEqual(
            ["记者、警方、司法依次接管公开场后的后果链"],
            assets,
        )

    def test_guardrail_merge_prefers_early_canonical_items_and_caps_lists(self) -> None:
        canonical = {
            "character_face_split": {
                "different_face_evidence": [f"主来源人物证据{i}" for i in range(1, 7)],
                "reaction_order_split": [f"主来源反应顺序{i}" for i in range(1, 5)],
            },
            "consequence_structure": {
                "tail_entry_owner": ["女主回家", "孩子开门"],
            },
        }
        auxiliary = {
            "character_face_split": {
                "different_face_evidence": [f"辅助重复解释{i}" for i in range(1, 10)],
                "reaction_order_split": [f"辅助反应顺序{i}" for i in range(1, 8)],
            },
            "consequence_structure": {
                "tail_entry_owner": ["前夫忏悔", "反派余波", "旁观者总结"],
            },
        }
        merged = GENERATOR.merge_story_guardrail_dicts(canonical, auxiliary)
        self.assertEqual(
            [f"主来源人物证据{i}" for i in range(1, 7)],
            merged["character_face_split"]["different_face_evidence"],
        )
        self.assertEqual(4, len(merged["character_face_split"]["reaction_order_split"]))
        self.assertEqual(["女主回家", "孩子开门"], merged["consequence_structure"]["tail_entry_owner"])

    def test_sample_grading_parser_keeps_layer_grades(self) -> None:
        parsed = GENERATOR.parse_sample_grading_text(
            "## 1. 样本等级\n"
            "- 样本等级：B类骨架样本\n"
            "- structure_grade：A\n"
            "- performance_grade：A\n"
            "- sentence_grade：B\n"
            "- terminal_consequence_grade：C\n"
            "## 2. 可学层\n"
            "- 正向DNA层：人物口气、动作落点\n"
            "- 仅骨架层：句法切分\n"
            "- 反面规则层：终局清算\n"
        )
        grading = parsed["sample_grading"]
        self.assertEqual("A", grading["structure_grade"])
        self.assertEqual("B", grading["sentence_grade"])
        self.assertEqual(["人物口气", "动作落点"], parsed["positive_dna_layers"])

    def test_layer_grade_overrides_whole_book_negative_summary(self) -> None:
        guidance = AUDIT.build_sample_grading_guidance(
            {
                "sample_grading": {
                    "level": "C类负样本",
                    "dna_usable": "不可",
                    "structure_grade": "B",
                    "performance_grade": "A",
                    "sentence_grade": "A",
                    "terminal_consequence_grade": "C",
                    "positive_dna_layers": ["人物口气", "句法节拍"],
                    "skeleton_only_layers": ["结构"],
                    "negative_rule_layers": ["终局清算"],
                    "final_verdict": {"allow_dna": "否", "negative_only": "是"},
                }
            }
        )
        self.assertEqual("A", guidance["sentence_grade"])
        self.assertFalse(
            any("不可并入正向融合" in item for item in guidance["hard_stops"])
        )
        self.assertTrue(
            any("实际调用服从四层 grade" in item for item in guidance["audit_notes"])
        )

    def test_clause_style_assets_preserve_complete_comma_phrases(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 11. style_assets 原始材料\n"
            "- character_bias：谁打你，你就打回去\n"
            "- dialogue_bridges：骚乱，就是从这一刻开始的\n"
        )
        self.assertEqual(
            ["谁打你，你就打回去"],
            parsed["style_assets"]["character_bias"],
        )
        self.assertEqual(
            ["骚乱，就是从这一刻开始的"],
            parsed["style_assets"]["dialogue_bridges"],
        )

    def test_role_bias_variants_preserve_complete_role_sentences(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 12. 迁移替换资产\n"
            "- role_bias_variants：高位者用短命令和资源调度护短，侵占者用道歉、感谢和示弱调用第三人\n"
        )
        self.assertEqual(
            ["高位者用短命令和资源调度护短，侵占者用道歉、感谢和示弱调用第三人"],
            parsed["migration_assets"]["role_bias_variants"],
        )

    def test_profile_source_bridge_keeps_bid_emotion_sequence(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 6. 桥段承重件\n"
            "- 桥段：BID-01 一号候诊单被撤回\n"
            "  - 原文怎么起手：先把候诊单递到她手里\n"
            "  - 承重件：候诊单、窗口\n"
            "  - 不能丢的顺序：拿到号 -> 被撤号 -> 白跑\n"
            "  - 为什么这个顺序不能乱：先给希望，撤回才会疼\n"
            "  - 最容易写假的点：直接宣布她被抛弃\n"
            "  - 原文为什么能过：纸面权利先到手再被拿走\n"
            "  - 情绪进入点：她拿到候诊单 | 烈度：4 | 原文证据：L2 候诊单落进掌心\n"
            "  - 刺痛/受辱拍：窗口当众叫停 | 烈度：7 | 原文证据：L3 先别给她办\n"
            "  - 短暂希望或反抗：她把单子递回去追问 | 烈度：6 | 原文证据：L4 为什么\n"
            "  - 反刀拍：工作人员收走单子 | 烈度：8 | 原文证据：L5 单子被抽走\n"
            "  - 峰值拍：她看见号码给了第三人 | 烈度：9 | 原文证据：L6 号码改到别人名下\n"
            "  - 场末余痛：她空手走出医院 | 烈度：7 | 原文证据：L7 手里只剩折痕\n"
        )
        bridge = parsed["bridge_rules"][0]
        self.assertEqual("BID-01", bridge["id"])
        self.assertEqual(
            [
                "情绪进入点",
                "刺痛/受辱拍",
                "短暂希望或反抗",
                "反刀拍",
                "峰值拍",
                "场末余痛",
            ],
            [item["beat"] for item in bridge["emotion_sequence"]],
        )
        self.assertEqual(9, bridge["emotion_sequence"][4]["intensity"])
        self.assertIn("号码改到别人名下", bridge["emotion_sequence"][4]["source_evidence"])

    def test_clause_style_cleaner_does_not_split_on_comma(self) -> None:
        self.assertEqual(
            ["我闯祸，她兜底"],
            GENERATOR.clean_style_asset_terms(
                ["我闯祸，她兜底"],
                preserve_commas=True,
            ),
        )

    def test_merge_buckets_accept_layered_a_grade_sample_label(self) -> None:
        buckets = GENERATOR.build_sample_source_buckets(
            [
                {
                    "name": "幼薇",
                    "level": "A 级结构样本，B 级句面样本",
                    "dna_usable": "可，但仅提结构、动作权限与场面后果",
                    "structure_grade": "A",
                    "performance_grade": "A",
                    "sentence_grade": "B",
                    "terminal_consequence_grade": "A",
                },
                {
                    "name": "主体骨架",
                    "level": "B类骨架样本",
                    "dna_usable": "部分可",
                    "structure_grade": "A",
                    "performance_grade": "B",
                    "sentence_grade": "C",
                    "terminal_consequence_grade": "B",
                },
            ]
        )
        self.assertEqual(["幼薇"], buckets["positive_dna_sources"])
        self.assertEqual(["主体骨架"], buckets["skeleton_only_sources"])
        self.assertEqual("B类骨架样本", buckets["effective_write_level"])

    def test_merge_buckets_do_not_upgrade_explicit_negative_sample(self) -> None:
        buckets = GENERATOR.build_sample_source_buckets(
            [
                {
                    "name": "反面样本",
                    "level": "C类负样本",
                    "dna_usable": "不可",
                    "structure_grade": "A",
                    "performance_grade": "A",
                    "sentence_grade": "A",
                    "terminal_consequence_grade": "A",
                }
            ]
        )
        self.assertEqual([], buckets["positive_dna_sources"])
        self.assertEqual(["反面样本"], buckets["negative_only_sources"])
        self.assertEqual("C类负样本", buckets["effective_write_level"])

    def test_explicit_story_guardrails_keep_consequence_structure(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 5. 标准翻刀链\n"
            "- profile_story_guardrail::consequence_structure::pre_evidence_reality_consequences：微博热搜、家门失效先把现实后果抬起来\n"
            "- profile_story_guardrail::consequence_structure::consequence_rebound_modes：婚礼直播后舆论和司法一起回灌\n"
            "- profile_story_guardrail::consequence_structure::tail_entry_owner：尾声入口只给墓前告白\n"
            "- profile_story_guardrail::consequence_structure::tail_entry_exclusion_reason：不给追悔线，避免整本塌成火葬场\n"
        )
        self.assertEqual(
            ["微博热搜、家门失效先把现实后果抬起来"],
            parsed["story_guardrails"]["consequence_structure"]["pre_evidence_reality_consequences"],
        )
        self.assertEqual(
            ["尾声入口只给墓前告白"],
            parsed["story_guardrails"]["consequence_structure"]["tail_entry_owner"],
        )

    def test_profile_source_character_guardrails_accept_named_characters(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 3. 作者DNA\n"
            "- 人物不同脸证据：季蘅少解释先退出；温策对敌压场、对她让权\n"
            "- 谁先解释谁先压场：温淮先甩锅，季蘅先点具体员工\n"
            "- 不同角色的动作权限差：温策能挡人，却在季蘅触碰时缩手\n"
        )
        face_split = parsed["story_guardrails"]["character_face_split"]
        self.assertEqual(
            ["季蘅少解释先退出", "温策对敌压场、对她让权"],
            face_split["different_face_evidence"],
        )
        self.assertEqual(
            ["温淮先甩锅，季蘅先点具体员工"],
            face_split["reaction_order_split"],
        )
        self.assertEqual(
            ["温策能挡人，却在季蘅触碰时缩手"],
            face_split["action_authority_split"],
        )

    def test_explicit_style_asset_is_not_rejected_for_semantic_words(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 11. style_assets 原始材料\n"
            "- misdirection：我不是替身\n"
            "- dialogue_bridges：为什么不要我\n"
        )
        self.assertEqual(["我不是替身"], parsed["style_assets"]["misdirection"])
        self.assertEqual(["为什么不要我"], parsed["style_assets"]["dialogue_bridges"])

    def test_explicit_scene_asset_is_not_rejected_as_explanation(self) -> None:
        self.assertEqual(
            ["不是她推人，而是他自己滑倒"],
            GENERATOR.clean_scene_asset_terms(["不是她推人，而是他自己滑倒"]),
        )

    def test_explicit_opening_hooks_override_explanatory_opening_signals(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 4. 开头高信息量信号\n"
            "- 开头信号：电影票这种最日常的双人优惠场，已经默认把主角排除在外\n"
            "## 11. style_assets 原始材料\n"
            "- opening_hooks：到最后总会变成三人行；还有十分钟就开场了；那我退出就好了\n"
        )
        self.assertEqual(
            ["到最后总会变成三人行", "还有十分钟就开场了", "那我退出就好了"],
            parsed["style_assets"]["opening_hooks"],
        )

    def test_merge_style_assets_keeps_explicit_and_table_fallback_layers(self) -> None:
        merged = GENERATOR.merge_style_asset_terms(
            ["初恋赌气嫁给我", "网友都说我是替身"],
            ["婚姻先天错位", "外界已经完成命名"],
        )
        self.assertEqual(
            ["初恋赌气嫁给我", "网友都说我是替身", "婚姻先天错位", "外界已经完成命名"],
            merged,
        )

    def test_merge_character_bias_keeps_short_explicit_and_table_biases(self) -> None:
        merged = GENERATOR.merge_style_asset_terms(
            ["轻刀反打", "高位护短"],
            ["忍", "记账", "轻刀反打"],
            preserve_commas=True,
            allow_short=True,
        )
        self.assertEqual(
            ["轻刀反打", "高位护短", "忍", "记账"],
            merged,
        )

    def test_generate_profile_keeps_profile_source_and_table_opening_hooks_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            (root / "写作资产").mkdir(parents=True)
            (root / "写作资产" / "profile_source.md").write_text(
                "## 4. 开头高信息量信号\n"
                "- 开头信号：初恋赌气嫁给我\n",
                encoding="utf-8",
            )
            (root / "可直接仿写_导语拆解表.md").write_text(
                "## 资产表\n\n"
                "| 原文怎么写 | 钩子内容 |\n"
                "|---|---|\n"
                "| 初恋赌气嫁给我 | 婚姻先天错位 |\n",
                encoding="utf-8",
            )
            profile = GENERATOR.generate_profile_from_sources([root], "样例书")
            self.assertEqual(
                ["初恋赌气嫁给我", "婚姻先天错位"],
                profile["style_assets"]["opening_hooks"],
            )

    def test_generate_profile_extracts_character_bias_from_pian_shou_dong_zuo_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            root.mkdir(parents=True)
            table = (
                "## 资产表\n\n"
                "| 人物 | 偏手动作 | 偏向对象 |\n"
                "|---|---|---|\n"
                "| 蒋湛 | 先护、先解释、先借钱 | 夏禾 |\n"
                "| 许初 | 先忍、先录音、最后再投证 | 自己 |\n"
            )
            (root / "可直接仿写_人物偏手表.md").write_text(table, encoding="utf-8")
            profile = GENERATOR.generate_profile_from_sources([root], "样例书")
            self.assertEqual(
                ["先护", "先解释", "先借钱", "先忍", "先录音", "最后再投证"],
                profile["style_assets"]["character_bias"],
            )

    def test_generate_profile_extracts_opening_hooks_from_yuan_wen_xian_xiang_and_gou_zi_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            root.mkdir(parents=True)
            guide = (
                "## 资产表\n\n"
                "| 位置 | 原文现象 | 功能 |\n"
                "|---|---|---|\n"
                "| 前20字 | 他为了女学生当众跟我拉拉扯扯的求情 | 起钩 |\n"
            )
            hook = (
                "## 资产表\n\n"
                "| 位置 | 钩子 | 类型 |\n"
                "|---|---|---|\n"
                "| 2节末 | 深夜电话被夏禾接起 | 电话钩子 |\n"
            )
            (root / "可直接仿写_导语拆解表.md").write_text(guide, encoding="utf-8")
            (root / "可直接仿写_钩子表.md").write_text(hook, encoding="utf-8")
            profile = GENERATOR.generate_profile_from_sources([root], "样例书")
            self.assertEqual(
                ["他为了女学生当众跟我拉拉扯扯的求情", "深夜电话被夏禾接起"],
                profile["style_assets"]["opening_hooks"],
            )

    def test_generate_profile_object_pressure_filters_out_fact_sentences(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            root.mkdir(parents=True)
            table = (
                "## 资产表\n\n"
                "| 物件 | 首次出现 | 后续回收 |\n"
                "|---|---|---|\n"
                "| 她花粉过敏 | 病房门口 | 花进垃圾桶 |\n"
                "| 我和蒋湛协议离婚了 | 民政局 | 截图回收旧账 |\n"
                "| 副驾驶 | 领证当日 | 长尾补刀 |\n"
                "| 7只黄玫瑰 | 晚饭和解场 | 电话回收 |\n"
                "| 录音，录像整理成了证据册 | 单位门口 | 终局双投 |\n"
            )
            (root / "可直接仿写_物件表.md").write_text(table, encoding="utf-8")
            profile = GENERATOR.generate_profile_from_sources([root], "样例书")
            self.assertEqual(
                ["副驾驶", "7只黄玫瑰", "录音"],
                profile["style_assets"]["object_pressure"],
            )

    def test_generate_profile_keeps_story_specific_pressure_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            source_dir = root / "原文"
            asset_dir = root / "写作资产"
            source_dir.mkdir(parents=True)
            asset_dir.mkdir(parents=True)
            (source_dir / "样例书.txt").write_text(
                "她摘下粗糙的铁戒指。铁盒里放着七十二封信。桌上是一份声明书。",
                encoding="utf-8",
            )
            (asset_dir / "profile_source.md").write_text(
                "## 11. style_assets 原始材料\n"
                "- object_pressure：粗糙的铁戒指\n"
                "- object_pressure：七十二封信\n"
                "- object_pressure：声明书\n",
                encoding="utf-8",
            )
            profile = GENERATOR.generate_profile_from_sources([root], "样例书")
            self.assertEqual(
                ["粗糙的铁戒指", "七十二封信", "声明书"],
                profile["style_assets"]["object_pressure"],
            )

    def test_generate_profile_keeps_medical_process_pressure_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            source_dir = root / "原文"
            asset_dir = root / "写作资产"
            source_dir.mkdir(parents=True)
            asset_dir.mkdir(parents=True)
            objects = [
                "旧听诊器",
                "蓝色医药箱",
                "一号候诊单",
                "压咳红绳",
                "儿童保健册",
                "离婚申请预约回执",
                "胸片报告",
            ]
            (source_dir / "样例书.txt").write_text(
                "，".join(objects),
                encoding="utf-8",
            )
            (asset_dir / "profile_source.md").write_text(
                "## 11. style_assets 原始材料\n"
                + "".join(f"- object_pressure：{item}\n" for item in objects),
                encoding="utf-8",
            )
            profile = GENERATOR.generate_profile_from_sources([root], "样例书")
            self.assertEqual(
                objects,
                profile["style_assets"]["object_pressure"],
            )

    def test_generate_profile_uses_book_dynamic_dictionary_for_unknown_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            source_dir = root / "原文"
            asset_dir = root / "写作资产"
            source_dir.mkdir(parents=True)
            asset_dir.mkdir(parents=True)
            source_text = "门后挂着一枚裂纹陶哨，后来它成了唯一的认亲凭证。"
            (source_dir / "样例书.txt").write_text(source_text, encoding="utf-8")
            (asset_dir / "profile_source.md").write_text(
                "## 11. style_assets 原始材料\n"
                "- object_pressure：裂纹陶哨\n",
                encoding="utf-8",
            )
            dictionary = {
                "categories": {
                    "核心物件": [{"term": "裂纹陶哨"}],
                    "证据载体": [],
                }
            }
            (asset_dir / "本书动态信号字典.json").write_text(
                json.dumps(dictionary, ensure_ascii=False),
                encoding="utf-8",
            )

            profile = GENERATOR.generate_profile_from_sources([root], "样例书")

            self.assertEqual(
                ["裂纹陶哨"],
                profile["style_assets"]["object_pressure"],
            )

    def test_generate_profile_rejects_unknown_object_without_dynamic_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            source_dir = root / "原文"
            asset_dir = root / "写作资产"
            source_dir.mkdir(parents=True)
            asset_dir.mkdir(parents=True)
            (source_dir / "样例书.txt").write_text("门后挂着一枚裂纹陶哨。", encoding="utf-8")
            (asset_dir / "profile_source.md").write_text(
                "## 11. style_assets 原始材料\n"
                "- object_pressure：裂纹陶哨\n",
                encoding="utf-8",
            )

            profile = GENERATOR.generate_profile_from_sources([root], "样例书")

            self.assertEqual([], profile["style_assets"]["object_pressure"])

    def test_generate_profile_dialogue_bridges_use_source_backed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            source_dir = root / "原文"
            asset_dir = root / "写作资产"
            source_dir.mkdir(parents=True)
            asset_dir.mkdir(parents=True)
            (source_dir / "样例书.txt").write_text(
                "“你可以不要。”他说，“但我得让你知道这东西是谁的。”",
                encoding="utf-8",
            )
            (asset_dir / "profile_source.md").write_text(
                "## 11. style_assets 原始材料\n"
                "- dialogue_bridges：你可以不要，但我得让你知道这东西是谁的\n",
                encoding="utf-8",
            )
            (root / "可直接仿写_对白功能表.md").write_text(
                "| 原文证据 | 典型说法类型 |\n"
                "|---|---|\n"
                "| `你可以不要` | 先归还知情权，再保留拒绝权 |\n",
                encoding="utf-8",
            )
            profile = GENERATOR.generate_profile_from_sources([root], "样例书")
            self.assertEqual(
                ["你可以不要"],
                profile["style_assets"]["dialogue_bridges"],
            )

    def test_validator_flags_polluted_object_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "样例书"
            source_dir = root / "原文"
            source_dir.mkdir(parents=True)
            source_text = "她花粉过敏。夏禾坐在他的副驾驶上。餐桌上摆着7只黄玫瑰。"
            (source_dir / "样例书.txt").write_text(source_text, encoding="utf-8")
            profile = {
                "style_assets": {
                    "opening_hooks": [],
                    "misdirection": [],
                    "object_pressure": ["她花粉过敏", "副驾驶"],
                    "action_axis": [],
                    "micro_actions": [],
                    "quiet_pressure": [],
                    "character_bias": [],
                    "meltdown_dialogue": [],
                    "rotten_relationship": [],
                    "dialogue_bridges": [],
                }
            }
            errors: list[str] = []
            VALIDATOR.check_book_profile_quality(
                root / "book.profile.json",
                profile,
                word_count=len(source_text),
                source_text=source_text,
                errors=errors,
                notes=[],
            )
            self.assertTrue(
                any("style_assets.object_pressure 混入非短语资产" in item for item in errors),
                errors,
            )

    def test_validator_accepts_story_specific_pressure_objects(self) -> None:
        for item in ("粗糙的铁戒指", "七十二封", "声明书", "锈铁盒"):
            self.assertIsNone(
                VALIDATOR.object_pressure_pollution_reason(item),
                item,
            )

    def test_validator_accepts_unknown_object_from_book_dynamic_dictionary(self) -> None:
        self.assertIsNotNone(
            VALIDATOR.object_pressure_pollution_reason("裂纹陶哨")
        )
        self.assertIsNone(
            VALIDATOR.object_pressure_pollution_reason(
                "裂纹陶哨",
                {"裂纹陶哨"},
            )
        )
        self.assertIsNotNone(
            VALIDATOR.object_pressure_pollution_reason(
                "她把裂纹陶哨交给了警察",
                {"裂纹陶哨"},
            )
        )
        self.assertIsNotNone(
            VALIDATOR.object_pressure_pollution_reason(
                "裂纹陶哨交给警察",
                {"裂纹陶哨"},
            )
        )

    def test_bridge_audit_ignores_single_generic_sequence_hit(self) -> None:
        profile = {
            "bridge_rules": [
                {
                    "bridge": "BID-04 垃圾站补救失效与独自手术",
                    "opening_pattern": ["洁癖者陪人翻垃圾", "从天黑找到天亮"],
                    "must_keep": ["脏场劳动", "找到碎玉", "手术短信"],
                    "recommended_sequence": ["高成本补救", "电话响", "再次离场"],
                    "why_original_passes": ["补救真实付出代价，但即时选择仍失败"],
                }
            ]
        }

        result = AUDIT.bridge_rule_audit("他口袋里的电话响了。", profile)

        self.assertEqual([], result)
        self.assertEqual([], AUDIT.build_bridge_recommendations(result))

    def test_bridge_audit_ignores_single_generic_core_hit(self) -> None:
        profile = {
            "bridge_rules": [
                {
                    "bridge": "BID-04 垃圾站补救失效与独自手术",
                    "opening_pattern": ["洁癖者陪人翻垃圾"],
                    "must_keep": ["求救电话", "找到碎玉", "手术短信"],
                    "recommended_sequence": ["电话响", "再次离场"],
                }
            ]
        }

        result = AUDIT.bridge_rule_audit("值班室接到一通求救电话。", profile)

        self.assertEqual([], result)

    def test_bridge_audit_accepts_cross_group_identity_evidence(self) -> None:
        profile = {
            "bridge_rules": [
                {
                    "bridge": "BID-301 共同账户被挪去买车",
                    "opening_pattern": ["先让车写她名"],
                    "must_keep": ["共同账户", "结婚基金归零"],
                    "recommended_sequence": ["看到落名", "追问钱", "查余额"],
                }
            ]
        }

        result = AUDIT.bridge_rule_audit(
            "合同先让车写她名。我追问钱从哪里来，才发现共同账户已经空了。",
            profile,
        )

        self.assertEqual(1, len(result))
        self.assertTrue(result[0]["bridge_identity_confirmed"])
        self.assertGreaterEqual(result[0]["bridge_identity_evidence_groups"], 2)

    def test_merged_profile_does_not_turn_unmatched_bridge_into_rewrite_task(self) -> None:
        profile = {
            "meta": {"mode": "merged_profiles", "source_count": 3},
            "bridge_rules": [{"bridge": "BID-04 辅助书原桥", "must_keep": ["碎玉"]}],
            "sample_source_buckets": {"entries": [{}, {}, {}]},
        }

        coverage = AUDIT.audit_profile_asset_coverage(profile, [], {}, {})
        impacts = AUDIT.build_asset_coverage_impact_items(
            coverage,
            {"level": "B类骨架样本"},
        )

        self.assertTrue(coverage["is_merged_profile"])
        self.assertTrue(any("禁止依据单个通用词回灌" in item for item in coverage["warnings"]))
        self.assertFalse(any(item.get("asset_kind") == "bridge_rules" for item in impacts))

    def test_profile_source_bridge_rules_keep_bid_and_full_fields(self) -> None:
        rules = GENERATOR.build_profile_source_bridge_rules(
            "## 6. 桥段承重件\n"
            "- 桥段：[BID-301] 共同账户被挪给闺蜜买车\n"
            "  - 原文怎么起手：先让车写她名，再让主角追问钱从哪里来\n"
            "  - 承重件：车写她名、共同账户、结婚基金归零\n"
            "  - 不能丢的顺序：看到落名 -> 追问钱 -> 查余额\n"
            "  - 为什么这个顺序不能乱：不先让落名成立，后面的归零会变抽象\n"
            "  - 最容易写假的点：只写他为她花钱\n"
            "  - 原文为什么能过：因为钱里埋着主角四年的未来底牌\n"
        )
        self.assertEqual("BID-301", rules[0]["id"])
        self.assertIn("共同账户", rules[0]["must_keep"])
        self.assertIn("只写他为她花钱", rules[0]["must_avoid"])

    def test_story_guardrails_can_read_consequence_fields_from_section_five(self) -> None:
        parsed = GENERATOR.parse_profile_source(
            "## 5. 标准翻刀链\n"
            "- 重大证据前隔开的现实后果：先有共同账户归零和拘留风险，再有公开证明回正\n"
            "- 后果回灌方式：名单回正、黑名单反噬、求婚失效、京市离场\n"
            "- 尾声入口归属：尾声入口必须归主角的新生活\n"
            "- 不给另一条线的原因：不能把尾声让给男方忏悔\n"
        )
        self.assertEqual(
            ["先有共同账户归零和拘留风险，再有公开证明回正"],
            parsed["story_guardrails"]["consequence_structure"]["pre_evidence_reality_consequences"],
        )
        self.assertEqual(
            ["尾声入口必须归主角的新生活"],
            parsed["story_guardrails"]["consequence_structure"]["tail_entry_owner"],
        )


if __name__ == "__main__":
    unittest.main()
