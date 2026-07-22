from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "prepare_short_analyze_job.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_short_analyze_job", SCRIPT_PATH)
assert SPEC and SPEC.loader
PREPARE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREPARE
SPEC.loader.exec_module(PREPARE)


class PrepareUpgradeExistingTest(unittest.TestCase):
    def test_upgrade_existing_keeps_existing_outputs_and_writes_backfill_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "拆文库" / "旧书"
            (root / "原文").mkdir(parents=True)
            (root / "原文" / "旧书.txt").write_text("第一行\n第二行", encoding="utf-8")
            (root / "拆文报告.md").write_text("已有厚拆报告，不允许覆盖", encoding="utf-8")
            (root / "_meta.json").write_text(
                json.dumps(
                    {
                        "version": "2.0",
                        "skill_fingerprint": "old-fingerprint",
                        "source_label": "旧书",
                        "structure_counts": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "_source_manifest.json").write_text(
                json.dumps(
                    {
                        "source_file": str(root / "原文" / "旧书.txt"),
                        "copied_to": str(root / "原文" / "旧书.txt"),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = PREPARE.upgrade_existing(
                argparse.Namespace(
                    upgrade_existing=str(root),
                    source=None,
                    name=None,
                )
            )

            self.assertEqual("upgrade-existing", payload["mode"])
            self.assertEqual("已有厚拆报告，不允许覆盖", (root / "拆文报告.md").read_text(encoding="utf-8"))
            self.assertTrue((root / "原文细节库").is_dir())
            self.assertTrue((root / "写作资产").is_dir())
            self.assertFalse((root / "写作资产" / "交流承压拆解.md").exists())
            self.assertFalse((root / "写作资产" / "冲突载体清单.md").exists())
            self.assertIn("写作资产/交流承压拆解.md", payload["missing_files"])
            self.assertIn("写作资产/冲突载体清单.md", payload["missing_files"])

            plan = (root / "_upgrade_plan.md").read_text(encoding="utf-8")
            self.assertIn("不自动生成任何正式 Markdown 内容", plan)
            self.assertIn("文件缺失清单不等于升级完成", plan)
            self.assertIn("finalize 返回 `ok=true`", plan)
            self.assertIn("写作资产/交流承压拆解.md", plan)
            self.assertIn("写作资产/冲突载体清单.md", plan)

            manifest = json.loads((root / "_required_outputs.json").read_text(encoding="utf-8"))
            self.assertIn("交流承压拆解.md", manifest["required"]["asset_files"])
            self.assertIn("冲突载体清单.md", manifest["required"]["asset_files"])

            meta = json.loads((root / "_meta.json").read_text(encoding="utf-8"))
            self.assertNotEqual("old-fingerprint", meta["skill_fingerprint"])
            self.assertEqual("old-fingerprint", meta["upgrade_existing"]["previous_skill_fingerprint"])
            self.assertIn("写作资产/交流承压拆解.md", meta["upgrade_existing"]["missing_files_at_scan"])


if __name__ == "__main__":
    unittest.main()
