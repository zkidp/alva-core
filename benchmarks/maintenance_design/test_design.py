"""Bounded provenance/evidence tests; never starts a model or runs old pilots."""
import json
from pathlib import Path
import subprocess
import unittest

from benchmarks.maintenance_design import feasibility as f
from benchmarks.maintenance_design import witnesses
from integrations.benchmark_runtime_v2.freeze import decode, sha


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = json.loads(f.CATALOGUE.read_text())

    def test_three_predeclared_candidates_and_initial_bytes(self):
        self.assertEqual(self.catalogue["candidate_selection_before_engineering_execution"], ["MM01", "MM02", "MM03"])
        self.assertFalse(self.catalogue["model_execution_authorized"])
        for task in self.catalogue["candidates"]:
            files = decode(task["bundle"], task["bundle"]["payload_sha256"])
            self.assertEqual(sorted(files), task["public_inputs"])
            self.assertTrue(all(p == "alva.toml" or p.startswith("src/") for p in files))
            self.assertTrue(all("witness" not in p and "goal" not in p and "behavior" not in p for p in files))
            for entry in task["bundle"]["payload"]["entries"]:
                original = subprocess.check_output(["git", "cat-file", "blob", entry["origin"]["oid"]], cwd=f.ROOT)
                self.assertEqual(original, files[entry["path"]])

    def test_engineering_patches_do_not_edit_original_inputs(self):
        for task in self.catalogue["candidates"]:
            files = decode(task["bundle"], task["bundle"]["payload_sha256"])
            before = dict(files)
            changed = witnesses.text_change(task["id"], files)
            self.assertEqual(files, before)
            self.assertEqual(files["alva.toml"], changed["alva.toml"])
            self.assertNotEqual(files, changed)

    def test_engineering_outcomes_are_not_model_outcomes(self):
        result = json.loads((f.HERE / "FEASIBILITY.json").read_text())
        self.assertEqual(result["model_generation_calls"], 0)
        self.assertEqual(result["input_token_api_calls"], 0)
        self.assertEqual(result["catalogue_sha256"], sha(f.CATALOGUE.read_bytes()))
        self.assertEqual(result["script_sha256"], sha((f.HERE / "feasibility.py").read_bytes()))
        self.assertEqual(result["witness_sha256"], sha((f.HERE / "witnesses.py").read_bytes()))
        rows = {r["id"]: r for r in result["rows"]}
        self.assertTrue(all(r["text"] == "SUPPORTED" for r in rows.values()))
        self.assertEqual(rows["MM01"]["native"], "SUPPORTED")
        self.assertEqual(rows["MM02"]["native"], "FAILED_NON_TARGET_SCOPE")
        self.assertEqual(rows["MM02"]["native_target_only"], "PASS")
        self.assertTrue(rows["MM02"]["scope_hazard"]["same_parent_in_initial_parse_delimiter"])
        self.assertEqual(rows["MM02"]["scope_hazard"]["executed_counterexample"]["observed"], "/")
        self.assertEqual(rows["MM03"]["missing_operations"], ["add_param", "add_call_arg"])

    def test_historical_counts_and_boundaries(self):
        def load(path):
            return json.loads((f.ROOT / path).read_text(encoding="utf-8"))
        self.assertEqual(load("feasibility/native_api/RESULTS.json")["status"], "SUPPORTED")
        self.assertEqual(load("benchmarks/native_mcp_skill/STATUS.json")["model_tasks_started"], 0)
        p26 = load("benchmarks/native_prospective/RESULTS.json")
        self.assertEqual(p26["executed"], 12)
        native = [r for r in p26["slots"] if r["arm"] == "N"]
        self.assertEqual(len(native), 4)
        self.assertTrue(all(not r["target_body_changed"] and r["disposition"] == "NO_COMMITTED_CANDIDATE" for r in native))
        p28 = load("benchmarks/p28_optional_descriptor/RESULTS.json")
        self.assertEqual(p28["executed"], 2)
        self.assertEqual([r["describe_operation_calls"] for r in p28["slots"]], [1, 3])
        self.assertTrue(all(not r["staged_target_changed_before_interrupt"] for r in p28["slots"]))

    def test_no_old_core_or_frozen_material_changed(self):
        paths = ["alva", "integrations", "feasibility/native_api", "benchmarks/cross_language",
                 "benchmarks/native_mcp_skill", "benchmarks/native_prospective", "benchmarks/p27_bottleneck",
                 "benchmarks/p28_optional_descriptor", "evidence"]
        subprocess.run(["git", "diff", "--exit-code", f.BASE, "--", *paths], cwd=f.ROOT, check=True, capture_output=True)

    def test_design_cannot_be_mistaken_for_execution(self):
        text = (f.ROOT / "docs/research/semantic-maintenance-study-design.md").read_text(encoding="utf-8")
        self.assertIn("DESIGN ONLY; MODEL EXECUTION NOT STARTED", text)
        self.assertIn("MM01 T, MM01 S", text)
        self.assertIn("600,000", text)
        self.assertIn("observation/interruption", text.lower())
        self.assertIn("No slot replacement", text)


if __name__ == "__main__":
    unittest.main()
