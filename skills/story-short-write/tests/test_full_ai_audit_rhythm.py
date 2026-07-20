from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_full_ai_audit.py"
)
SPEC = importlib.util.spec_from_file_location("run_full_ai_audit", SCRIPT_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FullAiAuditRhythmTest(unittest.TestCase):
    def test_tight_markdown_lines_are_real_paragraphs(self) -> None:
        text = "# 标题\n## 1\n第一段。\n第二段。\n## 2\n第三段。\n"
        paragraphs = AUDIT.build_paragraph_entries(text)
        self.assertEqual(3, len(paragraphs))
        self.assertEqual(
            ["第一段。", "第二段。", "第三段。"],
            [item["text"] for item in paragraphs],
        )

    def test_display_blocks_do_not_collapse_tight_text(self) -> None:
        lines = ["# 标题", "## 1"] + [f"这是第{i}段，包含一些现场动作和信息。" for i in range(1, 361)]
        text = "\n".join(lines)
        paragraphs = AUDIT.build_paragraph_entries(text)
        blocks = AUDIT.build_display_blocks(paragraphs)
        self.assertGreaterEqual(len(blocks), 5)
        self.assertEqual(360, len(paragraphs))

    def test_dialogue_questions_are_not_narrator_pulses(self) -> None:
        text = (
            "# 标题\n## 1\n"
            + "\n".join(['"你去哪？"', '"为什么？"', '"你说话啊？"'] * 80)
        )
        audit = AUDIT.audit_rhythm_distribution(text)
        self.assertTrue(audit["windows"])
        self.assertTrue(
            all(item["narrator_question_count"] == 0 for item in audit["windows"])
        )

    def test_plain_original_modifier_is_not_a_narrator_pulse(self) -> None:
        text = "\n".join(
            ["原来的老师嗓子哑了，让我替半场。" for _ in range(120)]
        )
        audit = AUDIT.audit_rhythm_distribution(text)
        self.assertTrue(
            all(item["explicit_aside_count"] == 0 for item in audit["windows"])
        )

    def test_low_pulse_window_is_reported(self) -> None:
        flat = [f"我把第{i}份记录放进柜子，随后继续核对下一项。" for i in range(90)]
        pulse = [
            "我拨这个干什么？",
            "不知道。",
            "难为他，还记得回来。",
            "白想了。",
        ] * 25
        text = "# 标题\n## 1\n" + "\n".join(flat + pulse)
        audit = AUDIT.audit_rhythm_distribution(text)
        self.assertGreaterEqual(audit["window_count"], 2)
        self.assertGreaterEqual(audit["low_pulse_window_count"], 1)

    def test_short_high_variance_manual_window_is_high_pulse(self) -> None:
        prefix = "\n".join(
            [f"我把第{i}份记录放进柜子，随后继续核对下一项。" for i in range(45)]
        )
        short_window = "\n".join(
            [
                "停。",
                "铁架卡在楼梯拐角，他把重量压到自己那边，手臂擦过旧钉子，血顺着腕骨往下。",
                '"搬上去再说。"',
                '"你们男的是不是都觉得破伤风怕四楼？"',
                "他没接。",
                "黄色小鸭创可贴贴歪了。",
            ]
            * 3
        )
        suffix = "\n".join(
            [f"第{i}项材料已经归档，下一项仍按原顺序处理。" for i in range(45)]
        )
        text = prefix + "\n" + short_window + "\n" + suffix
        start = len(prefix) + 1
        end = start + len(short_window)

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[start, end],
        )

        middle = audit["windows"][1]
        self.assertEqual("manual-model", audit["boundary_source"])
        self.assertTrue(middle["short_window_high_variance"])
        self.assertEqual(2, middle["burstiness_bonus"])
        self.assertEqual("high-pulse", middle["status"])

    def test_short_flat_manual_window_requires_review(self) -> None:
        prefix = "\n".join(["前段继续核对记录。" for _ in range(80)])
        short_window = "\n".join(["我继续核对记录。" for _ in range(12)])
        suffix = "\n".join(["后段继续核对记录。" for _ in range(80)])
        text = prefix + "\n" + short_window + "\n" + suffix
        start = len(prefix) + 1
        end = start + len(short_window)

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[start, end],
        )

        middle = audit["windows"][1]
        self.assertFalse(middle["short_window_high_variance"])
        self.assertEqual("short-window-review", middle["status"])
        self.assertGreaterEqual(audit["short_window_review_count"], 1)
        self.assertIn(middle, audit["short_window_review_windows"])

    def test_lived_scene_without_explicit_aside_is_covered(self) -> None:
        scene = "\n".join(
            [
                "店员少装了一杯豆浆。",
                "我走到车站才发现，又折回去。",
                "「我明明看见你装了。」",
                "「姐，我再给你拿一杯。」",
                "后面排队的人都看过来。",
                "漏了。",
                "我接过杯子，杯盖没扣牢，热豆浆顺着指缝流进袖口，纸巾抽出来时还粘成了一团。",
                "旁边的大爷低头看了半天，才发现鞋底踩着我掉在地上的口红。",
                "「你的？」",
                "「我的。」",
                "公交车走了。",
            ]
            * 12
        )
        text = scene + "\n" + ("后段继续核对记录。\n" * 80)
        boundary = len(scene) + 1

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[boundary],
        )

        first = audit["windows"][0]
        self.assertEqual(0, first["explicit_aside_count"])
        self.assertTrue(first["scene_variance_coverage"])
        self.assertIn(first["status"], {"covered", "high-pulse"})

    def test_repetitive_dialogue_is_classified_as_symmetric_dialogue(self) -> None:
        flat_dialogue = "\n".join(
            ["「请报地址。」", "「幸福家园。」", "「几栋？」", "「二栋。」"] * 30
        )
        text = flat_dialogue + "\n" + ("后段继续核对记录。\n" * 80)
        boundary = len(flat_dialogue) + 1

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[boundary],
        )

        first = audit["windows"][0]
        self.assertFalse(first["scene_variance_coverage"])
        self.assertTrue(first["symmetric_dialogue"])
        self.assertEqual("symmetric-dialogue", first["status"])
        self.assertGreaterEqual(audit["symmetric_dialogue_window_count"], 1)

    def test_lived_dialogue_with_frequent_interruptions_is_not_symmetric(self) -> None:
        lived_dialogue = "\n".join(
            [
                "保温杯滚到桌边。",
                "「地址？」",
                "「幸福家园。」",
                "后排有人说根本没有二栋。",
                "「几栋？」",
                "「我真不知道。」",
                "孩子在后面喊十一栋。",
            ]
            * 30
        )
        text = lived_dialogue + "\n" + ("后段继续核对记录。\n" * 80)
        boundary = len(lived_dialogue) + 1

        audit = AUDIT.audit_rhythm_distribution(
            text,
            model_boundaries=[boundary],
        )

        first = audit["windows"][0]
        self.assertLess(first["max_dialogue_run"], 4)
        self.assertFalse(first["symmetric_dialogue"])
        self.assertNotEqual("symmetric-dialogue", first["status"])

    def test_manual_model_segmentation_receipt_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            paragraphs_text = [
                f"第{i}段。" + ("这里是用于分段校验的正文内容。" * 80)
                for i in range(1, 6)
            ]
            source.write_text(
                "# 测试\n## 1\n" + "\n".join(paragraphs_text) + "\n",
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            anchors = receipt["paragraph_anchors"]
            selected = [anchors[index] for index in (1, 2, 3)]
            receipt["status"] = "completed"
            receipt["boundaries"] = [item["start_char"] for item in selected]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in selected
            ]
            receipt["manual_judgment"] = "当前模型已完整读取正文并人工确定边界。"

            encoded = json.loads(json.dumps(receipt, ensure_ascii=False))
            boundaries = AUDIT.validate_manual_model_segmentation_receipt(
                encoded,
                source,
                text,
            )

            self.assertEqual(receipt["boundaries"], boundaries)
            self.assertIn("不调用外部 API", receipt["prompt"])

    def test_formal_segmentation_requires_sequence_review_when_context_is_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            paragraphs_text = [
                f"第{i}段。" + ("这里是用于分段校验的正文内容。" * 80)
                for i in range(1, 6)
            ]
            source.write_text(
                "# 测试\n## 1\n" + "\n".join(paragraphs_text) + "\n",
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            context = [
                {"id": "a", "label": "第一个节点"},
                {"id": "b", "label": "第二个节点"},
            ]
            receipt = AUDIT.build_manual_model_segmentation_task(source, text, context)
            anchors = receipt["paragraph_anchors"]
            selected = [anchors[index] for index in (1, 2, 3)]
            receipt["status"] = "completed"
            receipt["boundaries"] = [item["start_char"] for item in selected]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in selected
            ]
            receipt["manual_judgment"] = "已人工完成。"
            with self.assertRaisesRegex(RuntimeError, "顺序契约结构复核"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                    context,
                )

    def test_manual_model_segmentation_receipt_rejects_short_segment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            paragraphs_text = [
                f"第{i}段。"
                + (
                    "这里是用于分段校验的正文内容。"
                    * (4 if i == 1 else 80)
                )
                for i in range(1, 5)
            ]
            source.write_text(
                "# 测试\n## 1\n" + "\n".join(paragraphs_text) + "\n",
                encoding="utf-8",
            )
            text = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, text)
            anchors = receipt["paragraph_anchors"]
            receipt["status"] = "completed"
            receipt["boundaries"] = [
                anchors[0]["start_char"],
                anchors[1]["start_char"],
                anchors[2]["start_char"],
            ]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in [anchors[0], anchors[1], anchors[2]]
            ]
            receipt["manual_judgment"] = "已人工完成。"

            with self.assertRaisesRegex(RuntimeError, "每段不得少于500字"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    text,
                )

    def test_manual_model_segmentation_receipt_rejects_stale_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "正文.md"
            source.write_text(
                "# 测试\n## 1\n第一段。\n第二段。\n第三段。\n第四段。\n第五段。\n",
                encoding="utf-8",
            )
            original = source.read_text(encoding="utf-8")
            receipt = AUDIT.build_manual_model_segmentation_task(source, original)
            anchors = receipt["paragraph_anchors"]
            selected = [anchors[index] for index in (1, 2, 3)]
            receipt["status"] = "completed"
            receipt["boundaries"] = [item["start_char"] for item in selected]
            receipt["boundary_evidence"] = [
                {
                    "offset": item["start_char"],
                    "quote": item["text"],
                    "reason": "叙事统计特征在此发生变化。",
                }
                for item in selected
            ]
            receipt["manual_judgment"] = "已人工完成。"

            with self.assertRaisesRegex(RuntimeError, "正文 SHA 已变化"):
                AUDIT.validate_manual_model_segmentation_receipt(
                    receipt,
                    source,
                    original + "新增。",
                )


if __name__ == "__main__":
    unittest.main()
