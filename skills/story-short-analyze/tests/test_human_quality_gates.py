from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_short_analyze_outputs.py"
)
SPEC = importlib.util.spec_from_file_location("short_analyze_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

FINALIZER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_short_analyze_finalize.py"
)
FINALIZER_SPEC = importlib.util.spec_from_file_location("short_analyze_finalizer", FINALIZER_PATH)
assert FINALIZER_SPEC and FINALIZER_SPEC.loader
FINALIZER = importlib.util.module_from_spec(FINALIZER_SPEC)
FINALIZER_SPEC.loader.exec_module(FINALIZER)


class HumanQualityGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_large_direct_table_requires_tiers(self) -> None:
        rows = "\n".join(
            f"| 资产{i} | 原文证据{i} | 迁移{i} |" for i in range(1, 7)
        )
        path = self._write(
            "可直接仿写_物件表.md",
            "| 物件 | 原文证据 | 迁移提醒 |\n|---|---|---|\n"
            + rows
            + "\n## 可直接借的承重结构\n- 资产1和资产2\n- 资产3和资产4\n"
            "## 迁移顺序提醒\n- 资产1再资产2\n- 资产3再资产4\n"
            "## 为什么这个顺序不能乱\n- 资产1不能晚于资产2\n- 资产3不能晚于资产4\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("必须增加 `层级/资产等级`" in error for error in errors))

    def test_direct_table_rejects_too_many_core_assets(self) -> None:
        rows = "\n".join(
            f"| 资产{i} | 原文证据{i} | 迁移{i} | 核心 |" for i in range(1, 7)
        )
        path = self._write(
            "可直接仿写_物件表.md",
            "| 物件 | 原文证据 | 迁移提醒 | 层级 |\n|---|---|---|---|\n"
            + rows
            + "\n## 可直接借的承重结构\n- 资产1和资产2\n- 资产3和资产4\n"
            "## 迁移顺序提醒\n- 资产1再资产2\n- 资产3再资产4\n"
            "## 为什么这个顺序不能乱\n- 资产1不能晚于资产2\n- 资产3不能晚于资产4\n",
        )
        errors: list[str] = []
        VALIDATOR.check_direct_imitation_quality(path, 8000, errors)
        self.assertTrue(any("核心资产过多" in error for error in errors))

    def test_bridge_card_requires_non_abstract_human_hook(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "## 卡一\n"
            "- 桥段名：家宴翻脸\n"
            "- 一句人话抓手：权限、秩序与现实后果\n"
            "- 桥段角色：规则展示\n"
            "- 原文位置：L1-L10\n"
            "- 原文现象证据：家门口不让女主进门\n"
            "- 原文为什么能过：先卡门再翻旧账\n"
            "- 为什么不像加工稿：人物先处理鞋和钥匙\n"
            "- 新稿最容易写假的点：直接宣布绝交\n"
            "- 必须保留的承重件：门、钥匙、称呼\n"
            "- 不能丢的顺序：卡门 -> 找钥匙 -> 改口\n"
            "- 为什么这个顺序不能乱：先宣布会失去生活阻力\n"
            "- 后续调用方式：换成宿舍门禁也能用\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, notes)
        self.assertFalse(any("只有抽象术语" in error for error in errors))
        self.assertTrue(any("只有抽象术语" in note for note in notes))

    def test_bridge_card_allows_explicit_source_absence(self) -> None:
        path = self._write(
            "桥段施工卡.md",
            "# 桥段施工卡\n\n原文未发现可独立抽取的承重桥。\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_bridge_workcards_quality(path, 1000, errors, notes)
        self.assertEqual([], errors)

    def test_craft_requires_sentence_level_assets(self) -> None:
        path = self._write(
            "写作手法.md",
            "## 2. 对话手法\n"
            "- 角色A嘴型很短，为什么成立\n"
            "- 角色B口气更绕，迁移风险明确\n"
            "- 角色C先找补，不能直接搬\n"
            "- 三人的角色差会决定压场顺序，写错会发假\n",
        )
        errors: list[str] = []
        VALIDATOR.check_craft_quality(path, errors)
        self.assertTrue(any("句法模板" in error for error in errors))
        self.assertTrue(any("段落节拍" in error for error in errors))

    def test_layered_sample_requires_explicit_layer_consumption(self) -> None:
        path = self._write(
            "样本分级与可学层.md",
            "- structure_grade：A\n"
            "- performance_grade：A\n"
            "- sentence_grade：B\n"
            "- terminal_consequence_grade：C\n"
            "- 正向DNA层：人物口气和动作\n"
            "- 仅骨架层：句法只看切句位置\n",
        )
        errors: list[str] = []
        VALIDATOR.check_sample_grading_quality(path, errors)
        self.assertTrue(any("分层样本" in error for error in errors))
        self.assertTrue(any("反面规则层" in error for error in errors))

    def test_report_agency_requires_three_distinct_layers(self) -> None:
        path = self._write(
            "拆文报告.md",
            "### 主角能动性三层判断\n"
            "- 原文明确动作：她选择留下并利用已经出现的证据窗口\n"
            "- 叙事意图判断：文本支持她在借势，而不是纯粹等待\n",
        )
        errors: list[str] = []
        VALIDATOR.check_report_agency_layers(path, errors)
        self.assertTrue(any("未知边界" in error for error in errors))

    def test_plot_nodes_require_story_sequence(self) -> None:
        path = self._write(
            "情节节点.md",
            "N1 | L1-L2 | 锚点：那次聚会 | 类型：信息 | 情绪：冷 | "
            "涉及：甲 | 状态变化：未知到知情 | 因果：收到证据后等待\n",
        )
        errors: list[str] = []
        VALIDATOR.check_plot_nodes_quality(path, 1, errors)
        self.assertTrue(any("故事时序" in error for error in errors))

    def test_plot_node_count_is_review_note_not_hard_error(self) -> None:
        path = self._write(
            "情节节点.md",
            "N1 | L1-L2 | 锚点：开场 | 类型：信息 | 情绪：冷 | "
            "涉及：甲 | 状态变化：未知到知情 | 因果：收到证据 | 故事时序：第一件事\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_plot_nodes_quality(path, 8000, errors, notes)
        self.assertFalse(any("颗粒度不足" in error for error in errors))
        self.assertTrue(any("禁止为达数量凑节点" in note for note in notes))

    def test_manual_review_checkpoints_cannot_be_skipped(self) -> None:
        self._write(
            "_progress.md",
            "- [x] 模型人工复核：事实台账\n"
            "- [ ] 模型人工复核：主报告\n"
            "- [x] 模型人工复核：profile\n"
            "- [x] 模型人工复核：finalize\n",
        )
        errors: list[str] = []
        VALIDATOR.check_manual_review_progress(self.root, errors)
        self.assertTrue(any("未完成的模型人工复核" in error for error in errors))

    def test_fact_ledger_requires_dual_timeline_fields(self) -> None:
        path = self._write(
            "事实与推断台账.md",
            "F01 | L1-L1 | 锚点：那次聚会结束后 | 类别：时间边界 | "
            "主体：甲 | 动作：收到录像 | 结果：开始等待 | "
            "口径：原文明确 | 禁止越界：不能排到婚礼后\n",
        )
        errors: list[str] = []
        VALIDATOR.parse_fact_ledger(path, ["那次聚会结束后"], errors)
        self.assertTrue(any("台账格式不完整" in error for error in errors))

    def test_fact_count_is_review_note_not_hard_error(self) -> None:
        path = self._write(
            "事实与推断台账.md",
            "F01 | L1-L1 | 锚点：收到录像证据 | 类别：主体边界/时间边界/证据来源 | "
            "主体：甲 | 动作：收到录像 | 结果：知情 | 叙述时点：开场 | "
            "故事时点：聚会后 | 时间依据：L1 | 口径：原文明确 | 禁止越界：未知来源\n",
        )
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.parse_fact_ledger(path, ["收到录像证据"], errors, notes)
        self.assertFalse(any("事实台账过薄" in error for error in errors))
        self.assertTrue(any("禁止为达数量编造" in note for note in notes))

    def test_profile_asset_counts_are_review_notes(self) -> None:
        errors: list[str] = []
        notes: list[str] = []
        data = {
            "scene_assets": {
                "public_explosion": ["婚礼上公开录像"],
                "external_order": ["警方带走涉事者"],
                "consequence_chain": ["证据公开后关系破裂"],
            },
            "banned_phrases": ["不要替角色总结"],
            "author_stance_patterns": ["让后果自己落地"],
            "style_assets": {
                key: []
                for key in VALIDATOR.REQUIRED_STYLE_ASSET_KEYS
            },
            "derived_patterns": [],
            "migration_assets": {
                key: ["录像"]
                for key in VALIDATOR.REQUIRED_MIGRATION_ASSET_KEYS
            },
            "story_guardrails": {
                "character_face_split": {
                    key: ["证据"]
                    for key in VALIDATOR.REQUIRED_FACE_GUARDRAIL_KEYS
                },
                "consequence_structure": {
                    key: ["后果"]
                    for key in VALIDATOR.REQUIRED_CONSEQUENCE_GUARDRAIL_KEYS
                },
            },
            "bridge_rules": [{"must_keep": ["录像公开"]}],
        }
        VALIDATOR.check_book_profile_quality(
            self.root / "book.profile.json",
            data,
            8000,
            "婚礼上公开录像警方带走涉事者证据公开后关系破裂",
            errors,
            notes,
        )
        self.assertFalse(any("资产过少" in error for error in errors))
        self.assertTrue(any("低于篇幅参考值" in note for note in notes))

    def test_unverified_filename_requires_explicit_status_declaration(self) -> None:
        self._write("拆文报告.md", "墓前结尾完成标题归位。\n")
        errors: list[str] = []
        VALIDATOR.check_title_claim_boundary(
            self.root,
            {"title_status": "unverified-filename"},
            errors,
        )
        self.assertTrue(any("缺少 `标题状态" in error for error in errors))

    def test_title_semantics_are_left_to_model_review(self) -> None:
        self._write(
            "拆文报告.md",
            "- 标题状态：未验证（来自文件名）。\n"
            "正文没有出现书名，不能声称完成标题归位。\n",
        )
        errors: list[str] = []
        VALIDATOR.check_title_claim_boundary(
            self.root,
            {"title_status": "unverified-filename"},
            errors,
        )
        self.assertEqual([], errors)

    def test_backreference_fact_must_point_to_earlier_source_lines(self) -> None:
        source = ["占位"] * 20
        source[14] = "那次聚会结束后，我收到录像"
        path = self._write(
            "事实与推断台账.md",
            "F01 | L15-L15 | 锚点：那次聚会结束后 | 类别：时间边界 | "
            "主体：甲 | 动作：收到录像 | 结果：知情 | 叙述时点：当前 | "
            "故事时点：当前 | 时间依据：按L15顺排 | 口径：原文明确 | "
            "禁止越界：不能乱排\n",
        )
        errors: list[str] = []
        facts = VALIDATOR.parse_fact_ledger(path, source, errors)
        notes: list[str] = []
        VALIDATOR.collect_timeline_review_notes(path, source, facts, notes)
        self.assertFalse(any("未指向更早原文行" in error for error in errors))
        self.assertTrue(any("没有指向更早正文行" in note for note in notes))

    def test_gendered_humiliation_requires_specific_analysis(self) -> None:
        self._write("拆文报告.md", "这是一场普通隐私冲突。\n")
        notes: list[str] = []
        VALIDATOR.check_gendered_humiliation_layer(
            self.root,
            "他的私密照片被拿去威胁别人。",
            notes,
        )
        self.assertTrue(any("性化隐私伤害" in note for note in notes))

    def test_high_agency_negation_is_review_note_not_hard_error(self) -> None:
        self._write("拆文报告.md", "禁止把等待写成主角策划了婚礼。\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_fact_references(self.root, {}, errors, notes)
        self.assertEqual([], errors)
        self.assertTrue(any("高主动性表达" in note for note in notes))

    def test_missing_fact_reference_remains_hard_error(self) -> None:
        self._write("拆文报告.md", "主角等待婚礼【原文明确 F99】。\n")
        errors: list[str] = []
        notes: list[str] = []
        VALIDATOR.check_fact_references(self.root, {}, errors, notes)
        self.assertTrue(any("不存在的事实台账 F99" in error for error in errors))

    def test_completion_updates_meta_but_preserves_manual_checkpoints(self) -> None:
        self._write(
            "_progress.md",
            "- [ ] 普通文件任务\n"
            "- [ ] 模型人工复核：主报告\n",
        )
        self._write(
            "_meta.json",
            '{"genre_detected":"通用","stages_completed":[],"last_stage_in_progress":6}\n',
        )
        asset_dir = self.root / "写作资产"
        asset_dir.mkdir()
        (asset_dir / "profile_source.md").write_text(
            "- 深层流派：替身婚姻清算\n",
            encoding="utf-8",
        )
        FINALIZER.update_completion_state(self.root)
        progress = (self.root / "_progress.md").read_text(encoding="utf-8")
        meta = __import__("json").loads((self.root / "_meta.json").read_text(encoding="utf-8"))
        self.assertIn("- [x] 普通文件任务", progress)
        self.assertIn("- [ ] 模型人工复核：主报告", progress)
        self.assertEqual("替身婚姻清算", meta["genre_detected"])
        self.assertEqual([2, 3, 4, 5, 6], meta["stages_completed"])
        self.assertIsNone(meta["last_stage_in_progress"])


if __name__ == "__main__":
    unittest.main()
