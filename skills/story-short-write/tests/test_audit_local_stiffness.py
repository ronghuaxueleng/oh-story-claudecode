from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_local_stiffness.py"
)
SPEC = importlib.util.spec_from_file_location("audit_local_stiffness", SCRIPT_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AuditLocalStiffnessTest(unittest.TestCase):
    def test_five_candidate_categories_are_located(self) -> None:
        text = """# 测试
## 1
我有一瞬间觉得，我们还能回去。
我还会摸床的另一边。
这些说出来，也不会改变协议。
「你每次都有急事。」
先是门禁冻结。
隔天财务来电。
再后来贴了整改通知。
第二天，事故组要求提交原始记录。
## 2
下一节。
"""
        categories = {item["category"] for item in AUDIT.scan(text)}
        self.assertEqual(
            {
                "direct_psychology_externalization",
                "post_emotion_summary_residue",
                "result_reporting_chain",
                "thesis_dialogue_concreteness",
                "chapter_end_hook_naturalness",
            },
            categories,
        )

    def test_restraint_explanation_and_scene_summary_are_located(self) -> None:
        text = """# 测试
## 1
杯子晃了两下。
我没有拍照。
我不知道是不是同一天。
这件事我后来也没问。
他先说已经断了联系，又说门锁没换。
"""
        categories = {item["category"] for item in AUDIT.scan(text)}
        self.assertIn("restraint_overexplained", categories)
        self.assertIn("high_value_scene_summary_compression", categories)


if __name__ == "__main__":
    unittest.main()
