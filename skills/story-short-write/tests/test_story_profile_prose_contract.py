from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "generate_story_profile.py"
)
SPEC = importlib.util.spec_from_file_location("generate_story_profile", SCRIPT_PATH)
assert SPEC and SPEC.loader
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


class StoryProfileProseContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_author_dna_builds_primary_prose_contract(self) -> None:
        source = self.root / "主体"
        dna = source / "写作资产" / "作者DNA指纹.md"
        dna.parent.mkdir(parents=True)
        dna.write_text(
            "## 句长、切句与停顿\n"
            "- 压力越高，人物句子越短。\n"
            "- 先给动作，再让人物短问。\n"
            "## 视角与情绪落点\n"
            "- 叙述者只按眼前事实判断。\n"
            "## 人物不同脸与口气差\n"
            "- 主角短问，对手绕答。\n"
            "## 明显不像的反面句型\n"
            "- 这一刻我终于明白。\n",
            encoding="utf-8",
        )
        contract = PROFILE.build_prose_style_contract(source)
        self.assertEqual("primary_only", contract["source_role"])
        self.assertIn("压力越高，人物句子越短。", contract["sentence_motion"])
        self.assertIn("这一刻我终于明白。", contract["anti_patterns"])

    def test_merge_keeps_only_first_profile_prose_voice(self) -> None:
        profiles = []
        for index, voice in enumerate(("主体口气", "辅助口气"), start=1):
            path = self.root / f"profile-{index}.json"
            path.write_text(
                json.dumps(
                    {
                        "precheck_overrides": {
                            "pretty_detail": {"fact_anchor_patterns": ["事实"]}
                        },
                        "prose_style_contract": {
                            "source_role": "primary_only",
                            "sentence_motion": [voice],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            profiles.append(path)
        merged = PROFILE.merge_profiles(profiles, "融合测试")
        contract = merged["prose_style_contract"]
        self.assertEqual(["主体口气"], contract["sentence_motion"])
        self.assertFalse(contract["auxiliary_profiles_supply_prose"])
        self.assertNotIn("辅助口气", json.dumps(contract, ensure_ascii=False))

    def test_standard_dna_sections_populate_all_prose_dimensions(self) -> None:
        source = self.root / "主体"
        dna = source / "写作资产" / "作者DNA指纹.md"
        dna.parent.mkdir(parents=True)
        dna.write_text(
            "## 一、总指纹\n\n- 总写法。\n"
            "## 三、句法 DNA\n\n### 1. 短判断句落锤\n\n功能：动作后下判断。\n"
            "## 六、人物口气 DNA\n\n| 人物 | 口气 |\n|---|---|\n| 主角 | 短问 |\n"
            "## 七、情绪 DNA\n\n### 1. 大场之后必有空场\n"
            "## 九、反面 DNA：加工稿句型\n\n- 空泛总结句。\n",
            encoding="utf-8",
        )
        contract = PROFILE.build_prose_style_contract(source)
        for field in (
            "sentence_motion",
            "narrator_voice",
            "dialogue_and_character_voice",
            "anti_patterns",
        ):
            with self.subTest(field=field):
                self.assertTrue(contract[field])

    def test_compact_legacy_headings_populate_all_prose_dimensions(self) -> None:
        source = self.root / "主体"
        dna = source / "写作资产" / "作者DNA指纹.md"
        dna.parent.mkdir(parents=True)
        dna.write_text(
            "## 句长切法\n决定句骤短。\n"
            "## 停顿与段落\n硬信息后断场。\n"
            "## 口气差\n主角短答，对手绕答。\n"
            "## 动作替代\n关门替代争辩。\n"
            "## 反面句型\n- 不用空泛总结。\n",
            encoding="utf-8",
        )
        contract = PROFILE.build_prose_style_contract(source)
        for field in (
            "sentence_motion",
            "narrator_voice",
            "dialogue_and_character_voice",
            "anti_patterns",
        ):
            with self.subTest(field=field):
                self.assertTrue(contract[field])

    def test_historical_summary_and_anti_imitation_headings_are_supported(self) -> None:
        source = self.root / "主体"
        dna = source / "写作资产" / "作者DNA指纹.md"
        dna.parent.mkdir(parents=True)
        dna.write_text(
            "## 句长切法\n- 受压场使用短句。\n"
            "## DNA 总述\n- 叙述贴着人物当下判断。\n"
            "## 人物口气差\n- 每个人的解释顺序不同。\n"
            "## 反面仿写句\n- 我早就看穿了一切。\n",
            encoding="utf-8",
        )
        contract = PROFILE.build_prose_style_contract(source)
        self.assertIn("叙述贴着人物当下判断。", contract["narrator_voice"])
        self.assertIn("我早就看穿了一切。", contract["anti_patterns"])

    def test_embedded_explicit_anti_patterns_are_collected(self) -> None:
        source = self.root / "主体"
        dna = source / "写作资产" / "作者DNA指纹.md"
        dna.parent.mkdir(parents=True)
        dna.write_text(
            "## 1. 句长切句、停顿与断场\n"
            "- 稳定写法：短句之后接操作动作。\n"
            "- 反面句型：所有人都震惊地看着我。\n"
            "## 2. 贴脸视角、动作替代与旧伤触发\n"
            "- 视角只报告主角可感的事实。\n"
            "## 3. 人物口气差、反应先后与动作权限\n"
            "- 主角先撤回语言，对手先抢解释权。\n"
            "## 4. 公开秩序压人方式\n"
            "- 风险边界：群众整齐议论不纳入正向 DNA。\n",
            encoding="utf-8",
        )
        contract = PROFILE.build_prose_style_contract(source)
        self.assertIn(
            "反面句型：所有人都震惊地看着我。", contract["anti_patterns"]
        )
        self.assertIn(
            "风险边界：群众整齐议论不纳入正向 DNA。",
            contract["anti_patterns"],
        )

    def test_dynamic_object_term_is_not_rejected_by_closed_suffix_list(self) -> None:
        term = "她留下的旧怀表"
        self.assertTrue(PROFILE.keep_object_pressure_asset(term, {term}))

    def test_unknown_object_without_source_dictionary_still_needs_evidence(self) -> None:
        self.assertFalse(PROFILE.keep_object_pressure_asset("她留下的旧怀表", set()))


if __name__ == "__main__":
    unittest.main()
