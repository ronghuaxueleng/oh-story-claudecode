from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillDocumentedCommandsTest(unittest.TestCase):
    def test_section_progress_commands_are_complete_in_main_skill(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_fragments = (
            'validate_section_progress.py" status',
            'validate_section_progress.py" start-section',
            '--plan "{项目目录}/写作资产/当前节计划/第N节.json"',
            'validate_section_progress.py" commit-section',
            '--staged "{项目目录}/写作资产/当前节暂存/第N节.md"',
            '--review "{项目目录}/写作资产/逐节验收/第N节.json"',
            'validate_section_progress.py" reopen-section',
            'validate_section_progress.py" sync-pending-contracts',
            'validate_section_progress.py" discard-writing-section',
            'validate_section_progress.py" finalize',
            'validate_section_progress.py" init',
            'init_section_review.py"',
            'status / finalize / sync-pending-contracts 使用 --state',
            '禁止先运行主脚本或任一子命令的 --help',
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
