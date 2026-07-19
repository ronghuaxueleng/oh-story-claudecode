from __future__ import annotations

import importlib.util
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
