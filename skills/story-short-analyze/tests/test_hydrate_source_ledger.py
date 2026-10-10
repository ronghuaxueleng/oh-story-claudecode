import importlib.util
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("hydrate_source_ledger", Path(__file__).parents[1] / "scripts" / "hydrate_source_ledger.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HydrateSourceLedgerTests(unittest.TestCase):
    def test_subflow_keeps_explicit_causal_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.txt"
            source.write_text("speaker asks\n", encoding="utf-8")
            causal = {"arrival_causes": ["speaker needs entry"], "exit_cause": "entry refused"}
            data = {"source_line_count": 1, "source_book": "sample", "flow_rows": [["SF-01", 1, 1, "BID-01", "entry", "outside", ["ask"], "none", ["refusal"], ["hurt"], "outside", ["speaker asks"]]], "layer_rows": [], "causal_preconditions_registry": {"SF-01": causal}}
            flows, _ = MODULE.hydrate_subflows(data, source)
            self.assertEqual(causal, flows[0]["causal_preconditions"])
            data["causal_preconditions_registry"]["SF-02"] = causal
            with self.assertRaisesRegex(ValueError, "Unknown causal"):
                MODULE.hydrate_subflows(data, source)

    def test_preserves_authored_semantics_and_explicit_candidate_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.txt"
            source.write_text("speaker asks\nreceiver refuses\n", encoding="utf-8")
            data = {
                "source_line_count": 2,
                "plot_rows": [["P-1", 1, 2, "BID-01", "speaker", "asks for key", "key", "door is locked", "receiver keeps key", "key is withheld", "speaker remains outside", "receiver refuses"]],
                "plot_candidates": [["PC-1", 1, 1, "request", "speaker", "independent_beat", "P-1", "Request creates a decision point.", ""], ["PC-2", 2, 2, "reply", "receiver", "merged_same_atomic_chain", "P-1", "Refusal answers the pending request.", "The reply closes this key request without opening another action."]],
                "plot_coverage": [[1, 2, "plot_bearing", ["PC-1", "PC-2"], ""]],
                "plot_completeness_review": {"manual_judgment": "Both lines reviewed as one request and reply chain."},
            }
            result = MODULE.hydrate(data, "plot", source)
            self.assertEqual(result["beats"][0]["control_change"], "receiver keeps key")
            self.assertEqual(result["source_plot_candidate_audit"][1]["decision"], "merged_same_atomic_chain")
            self.assertEqual(result["source_plot_candidate_audit"][1]["source_evidence"], "receiver refuses")
            self.assertEqual(data["plot_rows"][0][8], "receiver keeps key")
            data["plot_coverage"] = [[1, 1, "plot_bearing", ["PC-1"], ""]]
            with self.assertRaisesRegex(ValueError, "incomplete"):
                MODULE.hydrate(data, "plot", source)
            data["plot_coverage"] = [[1, 2, "plot_bearing", ["PC-1", "PC-2"], ""]]
            data["plot_rows"][0][-1] = "invented evidence"
            with self.assertRaisesRegex(ValueError, "outside"):
                MODULE.hydrate(data, "plot", source)


if __name__ == "__main__":
    unittest.main()
