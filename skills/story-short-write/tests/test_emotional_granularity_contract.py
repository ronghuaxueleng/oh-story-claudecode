from __future__ import annotations

import importlib.util
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
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "原文.txt"
        self.outline = self.root / "小节大纲.md"
        self.draft = self.root / "正文.md"
        self.source_quotes = [
            "我没想到执行任务会遇见他。",
            "他抓着我的袖子，求我放过那个学生。",
            "我本来以为他会解释。",
            "可他一开口，问的还是那个学生。",
            "我直接把他的手推开，让他闭嘴。",
            "我走出去以后，冷风先把脑子冻住了。",
        ]
        self.source.write_text("".join(self.source_quotes), encoding="utf-8")
        self.outline_evidence = "丈夫先替别人让妻子交出位置，妻子仍等了一次解释，最后当场夺回席牌。"
        self.outline.write_text(
            f"## 1. 让位\n\n{self.outline_evidence}\n",
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

    def prewrite_receipt(self) -> dict:
        data = GATE.create_receipt("测试", self.source)
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
                "manual_judgment": "本节按主体原文的期待、错答、冷刺和动作爆点组织情绪，不在首稿清洗直接判断。",
            }
        )
        for index, role in enumerate(GATE.REQUIRED_BEAT_ROLES):
            item["source_emotion_beats"][index].update(
                {
                    "trigger": f"主体原文 {role} 的现实触发",
                    "relationship_position_change": "丈夫先偏护，妻子的原位被继续夺走。",
                    "reader_effect": "读者从短暂期待跌进公开受辱。",
                    "intensity": 7 if role != "peak" else 9,
                    "source_evidence": [self.source_quotes[index]],
                }
            )
            item["target_outline_beats"][index].update(
                {
                    "trigger": f"目标细纲 {role} 的现实触发",
                    "relationship_position_change": "席牌换手后，妻子公开夺回控制权。",
                    "reader_effect": "读者先被偏护刺痛，再看到动作爆开。",
                    "intensity": 7 if role != "peak" else 9,
                    "outline_evidence": [self.outline_evidence],
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
                "manual_judgment": "正文保留主体原文式直接判断和不体面破绽，峰值由夺牌动作兑现，没有降成手续播报。",
            }
        )
        source_beats = data["section_contracts"][0]["source_emotion_beats"]
        for index, role in enumerate(GATE.REQUIRED_BEAT_ROLES):
            item["beat_reviews"][index].update(
                {
                    "source_intensity": source_beats[index]["intensity"],
                    "target_intensity": source_beats[index]["intensity"],
                    "target_quotes": [target_quotes[index]],
                    "parity_judgment": f"{role} 由本节真实动作和判断承接，读者体感未低于主体原文。",
                }
            )
        data["draft_status"] = "passed"
        return data

    def test_prewrite_passes_in_source_dominant_mode(self) -> None:
        errors, _ = GATE.validate_prewrite_data(
            self.prewrite_receipt(), self.source, self.outline
        )
        self.assertEqual([], errors)

    def test_prewrite_blocks_lower_target_intensity(self) -> None:
        data = self.prewrite_receipt()
        data["section_contracts"][0]["target_outline_beats"][4]["intensity"] = 8
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("目标烈度低于主体原文" in item for item in errors))

    def test_prewrite_blocks_first_draft_ai_cleanup(self) -> None:
        data = self.prewrite_receipt()
        data["first_draft_policy"]["anti_ai_cleanup_applied_during_first_draft"] = True
        errors, _ = GATE.validate_prewrite_data(data, self.source, self.outline)
        self.assertTrue(any("anti_ai_cleanup" in item for item in errors))

    def test_draft_requires_exact_quotes_and_equal_intensity(self) -> None:
        data = self.completed_receipt()
        errors, _ = GATE.validate_draft_data(data, self.source, self.draft)
        self.assertEqual([], errors)
        data["section_reviews"][0]["beat_reviews"][4]["target_intensity"] = 8
        errors, _ = GATE.validate_draft_data(data, self.source, self.draft)
        self.assertTrue(any("正文烈度低于主体原文" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
