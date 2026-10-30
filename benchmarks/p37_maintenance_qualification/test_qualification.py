"""Zero-model provenance/input-boundary and honest qualification-result checks."""
import json
from pathlib import Path
import subprocess
import unittest

from benchmarks.p37_maintenance_qualification.inputs import model_inputs
from integrations.benchmark_runtime_v2.freeze import decode

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
REGISTERED = "e800c8808beb6c333e61d23e84119a4bcb6ec747"


class Qualification(unittest.TestCase):
    def test_immutable_registration_and_exact_source(self):
        registry = json.loads((HERE / "CANDIDATE-REGISTRY.json").read_text())
        bundles = json.loads((HERE / "TASK-BUNDLES.json").read_text())
        self.assertEqual([r["id"] for r in registry["candidates"]], ["MM04", "MM05", "MM06", "MM07"])
        for c in registry["candidates"]:
            files = decode(bundles[c["id"]], c["bundle_sha256"])
            source = subprocess.check_output(["git", "show", c["source_commit"] + ":" + c["source_path"]], cwd=ROOT)
            self.assertEqual(files["src/model.alva"], source)
            self.assertEqual(set(files), {"alva.toml", "src/model.alva"})
        names = ["CANDIDATE-REGISTRY.json", "TASK-BUNDLES.json", "SELECTION-PROTOCOL.md", "APPROVED-DOCS.json", "assertions.py"]
        names += ["public/" + i + "/task.json" for i in bundles]
        for name in names:
            expected = subprocess.check_output(["git", "show", REGISTERED + ":benchmarks/p37_maintenance_qualification/" + name], cwd=ROOT)
            self.assertEqual((HERE / name).read_bytes(), expected, name)

    def test_future_mount_allowlist_excludes_qualification_material(self):
        for ident in ("MM04", "MM05", "MM06", "MM07"):
            for condition in ("T", "S"):
                result = model_inputs(ident, condition)
                self.assertEqual(set(result), {"public_task", "project", "approved_docs"})
                self.assertEqual(set(result["project"]), {"alva.toml", "src/model.alva"})
                self.assertNotIn("native_hypothesis", result["public_task"])
                self.assertNotIn("evaluation_plan", result["public_task"])
                self.assertNotIn("guard_policy", result["public_task"])
                self.assertEqual(len(result["approved_docs"]), 1 if condition == "T" else 5)
                self.assertNotIn("qualif", " ".join(result["project"]))

    def test_result_disposition_conjunction_when_published(self):
        path = HERE / "QUALIFICATION-RESULTS.json"
        if not path.exists():
            return  # Registered definitions may be checked before qualification.
        result = json.loads(path.read_text())
        self.assertEqual(result["registered_count"], 4)
        self.assertEqual(sum(result["disposition_counts"].values()), 4)
        self.assertEqual([r["id"] for r in result["rows"]], ["MM04", "MM05", "MM06", "MM07"])
        self.assertEqual(result["model_generation_calls"], 0)
        self.assertEqual(result["input_token_api_calls"], 0)
        for row in result["rows"]:
            if row["disposition"] != "QUALIFIED_MATCHED":
                self.assertTrue(row["reason"])
                continue
            self.assertEqual(row["baseline"]["regression"], "PASS")
            self.assertEqual(row["baseline"]["goal"], "TEST_FAIL")
            for arm in ("text", "native"):
                self.assertEqual([row[arm][k] for k in ("goal", "regression", "scope")], ["PASS"] * 3)
            n = row["native"]
            self.assertEqual(n["guard"]["status"], "SCOPE_ALLOWED")
            self.assertEqual(n["actual_commit_dispatches"], 1)
            self.assertTrue(n["air_published"] and n["fresh_matches_commit_and_staging"] and n["source_projection_unchanged"])


if __name__ == "__main__":
    unittest.main()
