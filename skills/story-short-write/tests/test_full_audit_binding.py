from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_full_ai_audit.py"
)
SPEC = importlib.util.spec_from_file_location("run_full_ai_audit", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FullAuditBindingTest(unittest.TestCase):
    def test_binding_uses_file_bytes_sha_instead_of_decoded_text_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "带BOM正文.txt"
            path.write_bytes(b"\xef\xbb\xbftext\r\n")
            decoded = path.read_text(encoding="utf-8-sig")
            binding = AUDIT.build_text_binding(path, decoded)
            self.assertEqual(AUDIT.file_sha256(path), binding["sha256"])
            self.assertNotEqual(AUDIT.text_sha256(decoded), binding["sha256"])
            self.assertEqual(len(decoded), binding["char_count"])


if __name__ == "__main__":
    unittest.main()
