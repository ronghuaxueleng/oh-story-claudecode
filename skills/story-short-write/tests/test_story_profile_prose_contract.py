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


if __name__ == "__main__":
    unittest.main()
