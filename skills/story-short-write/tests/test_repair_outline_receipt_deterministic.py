from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "repair_outline_receipt_deterministic.py"
)


class RetiredOutlineRepairTest(unittest.TestCase):
    def test_retired_entry_point_never_mutates_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = root / "细纲表演验收回执.json"
            outline = root / "小节大纲.md"
            receipt.write_text(
                json.dumps(
                    {
                        "reviewed_by_current_model": False,
                        "target_plot_beats": [{"beat_id": "P-001"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            outline.write_text("## 1. 起事\n\n- 原始细纲。\n", encoding="utf-8")
            before = receipt.read_bytes()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--receipt",
                    str(receipt),
                    "--outline",
                    str(outline),
                    "--rebuild-target-semantics",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("outline_receipt_repair: blocked", result.stdout)
            self.assertEqual(before, receipt.read_bytes())


if __name__ == "__main__":
    unittest.main()
