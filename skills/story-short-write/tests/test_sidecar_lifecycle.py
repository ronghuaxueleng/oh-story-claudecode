from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sidecar_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("sidecar_lifecycle", SCRIPT)
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class SidecarLifecycleTest(unittest.TestCase):
    def test_consume_replaces_large_sidecar_with_audit_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sidecar = root / "人工侧车.json"
            receipt = root / "正式回执.json"
            sidecar.write_text(
                json.dumps({"manual": "人工内容" * 200}, ensure_ascii=False),
                encoding="utf-8",
            )
            receipt.write_text('{"status":"passed"}\n', encoding="utf-8")
            input_sha = TOOL.sha256_file(sidecar)
            original_size = sidecar.stat().st_size

            payload = TOOL.consume_sidecar(
                sidecar,
                input_sha256=input_sha,
                receipt_path=receipt,
                receipt_sha256=TOOL.sha256_file(receipt),
                operation="test.apply",
                counts={"items": 1},
            )

            consumed = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(payload, consumed)
            self.assertEqual("consumed", consumed["status"])
            self.assertEqual(input_sha, consumed["input"]["sha256"])
            self.assertEqual(1, consumed["counts"]["items"])
            self.assertLess(sidecar.stat().st_size, original_size)


if __name__ == "__main__":
    unittest.main()
