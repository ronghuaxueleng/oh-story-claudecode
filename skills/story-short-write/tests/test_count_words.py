from __future__ import annotations

import importlib.util
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "count_words.py"
SPEC = importlib.util.spec_from_file_location("count_words", SCRIPT_PATH)
assert SPEC and SPEC.loader
COUNT_WORDS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COUNT_WORDS)


class CountWordsTest(unittest.TestCase):
    def test_human_output_is_platform_neutral(self) -> None:
        output = StringIO()
        result = {
            "files": [{"name": "正文.md", "word_count": 1200}],
            "file_count": 1,
            "total_word_count": 1200,
            "total_k_words": 1.2,
        }
        with redirect_stdout(output):
            COUNT_WORDS.print_table(result)
        rendered = output.getvalue()
        self.assertIn("短篇小说字数统计", rendered)
        self.assertIn("按非空白字符口径：1.2 千字", rendered)
        self.assertNotIn("番茄", rendered)


if __name__ == "__main__":
    unittest.main()
