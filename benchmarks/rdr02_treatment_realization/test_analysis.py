"""Reader/classifier controls, not additional research tasks or model trials."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from benchmarks.rdr02_treatment_realization import evidence as e
from benchmarks.rdr02_treatment_realization import analyze as a
from benchmarks.rdr02_treatment_realization import validate as v


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.obs = json.loads((e.HERE / "OBSERVATIONS.json").read_bytes())
        self.result = json.loads((e.HERE / "E0-E1-COMPARISON.json").read_bytes())

    def test_fixed_units_and_portable_certificate(self):
        self.assertEqual(a.compare(self.obs), self.result)
        check = v.validate(self.obs, self.result)
        self.assertFalse(check["raw_validation_complete"])
        self.assertGreater(check["private_pointers_not_reopened"], 0)
        self.assertEqual(check["mode"], "PUBLIC_CERTIFICATE_ONLY")

    def test_missing_archives_are_not_pass(self):
        result = a.run({})
        for row in result["E0-E1-COMPARISON.json"]["rows"][1:]:
            self.assertEqual(row["E0"]["classification"], "UNKNOWN")
            self.assertFalse(row["archive_available"])
        self.assertEqual(result["E0-E1-COMPARISON.json"]["disposition"], "INCONCLUSIVE_EVIDENCE_LIMITATION")

    def test_archive_corruption_is_candidate_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.zip"
            bad.write_bytes(b"not original evidence")
            _, available = e.read_archives({"U2": bad})
            self.assertIn("IDENTITY_MISMATCH", available["U2"]["reason"])
            self.assertEqual(available["U1"]["status"], "PUBLIC_RECORDS")

    def test_receipt_absence_and_staged_behavior_not_upgraded(self):
        u3, u4 = self.obs["units"][2:]
        for evaluator in (a.e0, a.e1):
            self.assertEqual(evaluator(u3)["staged_behavior"], "NOT_INDEPENDENTLY_EVALUATED")
            self.assertEqual(evaluator(u3)["stages"]["publication"], "FALSE")
            self.assertEqual(evaluator(u4)["task_tests"], "PASS")
            self.assertEqual(evaluator(u4)["stages"]["independent_published_behavior"], "UNKNOWN")
        self.assertFalse(self.result["rows"][0]["model_unit"])

    def test_coverage_descriptor_is_not_native_surface(self):
        u1 = self.obs["units"][0]
        self.assertTrue(all(p["advertised_by_registry"] and not p["advertised_native_tool"] for p in u1["coverage_probes"]))
        for evaluator in (a.e0, a.e1):
            self.assertEqual(evaluator(u1)["classification"], "CAPABILITY_COVERAGE_GAP")
            ordinary = copy.deepcopy(u1)
            for p in ordinary["coverage_probes"]: p["error_text"] = "INVALID_ARGUMENT"
            self.assertEqual(evaluator(ordinary)["classification"], "UNKNOWN")

    def test_tampered_result_and_unfair_inputs_rejected(self):
        for field, value in (("evidence_sha256_E1", "0" * 64), ("agreement", False)):
            changed = copy.deepcopy(self.result)
            changed["rows"][1][field] = value
            with self.assertRaises(AssertionError): v.validate(self.obs, changed)
        changed = copy.deepcopy(self.result)
        changed["rows"][2]["E0"]["staged_behavior"] = "PASS"
        with self.assertRaises(AssertionError): v.validate(self.obs, changed)

    def test_historical_label_poisoning_does_not_change_classifiers(self):
        for row in self.obs["units"]:
            poisoned = copy.deepcopy(row)
            poisoned.update(disposition="PASS", score=1, reference_patch="fake", historical_label="PASS")
            self.assertEqual(a.e0(row), a.e0(poisoned))
            self.assertEqual(a.e1(row), a.e1(poisoned))

    def test_historyless_input_access(self):
        archive = subprocess.check_output(["git", "-c", "core.autocrlf=false", "archive", "--format=zip", "HEAD"], cwd=e.ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(archive)) as z: z.extractall(root)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            git("init", "-q")
            git("-c", "core.autocrlf=false", "add", ".")
            git("-c", "user.name=RDR Test", "-c", "user.email=rdr@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "single root")
            absent = subprocess.run(["git", "cat-file", "-e", e.manifest()["base"]], cwd=root, capture_output=True)
            self.assertNotEqual(absent.returncode, 0)
            run = subprocess.run([sys.executable, "-c", "from benchmarks.rdr02_treatment_realization.evidence import public_sources; assert len(public_sources())==15"],
                                 cwd=root, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
