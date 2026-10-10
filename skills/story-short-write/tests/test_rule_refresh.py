from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rule_refresh_ledger", ROOT / "scripts/validate_rule_execution_ledger.py")
LEDGER = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = LEDGER
spec.loader.exec_module(LEDGER)


class RuleRefreshTest(unittest.TestCase):
    def test_changed_rules_require_new_review_and_preserve_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = project / "写作资产/规则执行台账.json"
            old = LEDGER.build_ledger(project, ROOT)
            old["groups"][0]["source"]["sha256"] = "old"
            old["groups"][0]["status"] = "ready"
            old["draft_review_state"]["feedback_cases"] = [{"feedback_id": "F1"}]
            LEDGER.write_new(path, old)
            LEDGER.refresh_prewrite_rules(path)
            new = LEDGER.load(path)
            self.assertEqual("pending", new["groups"][0]["status"])
            self.assertFalse(new["prewrite_review"]["model_read_all_cases"])
            self.assertEqual(old["draft_review_state"], new["draft_review_state"])
            self.assertEqual("old", new["rule_refresh_history"][0]["changes"][0]["previous_source"]["sha256"])

    def test_confirmed_setting_blocks_refresh_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = project / "写作资产/规则执行台账.json"
            old = LEDGER.build_ledger(project, ROOT)
            old["design_review_state"]["setting"] = {"status": "confirmed"}
            LEDGER.write_new(path, old)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                LEDGER.refresh_prewrite_rules(path)
            self.assertEqual(before, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
