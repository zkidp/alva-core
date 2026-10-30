"""Necessary controls: frozen input identity, evidence strength and fairness."""
import inspect
import json
import unittest
from pathlib import Path

from benchmarks.p38_authorized_effect_contract import mechanisms as m
from benchmarks.p38_authorized_effect_contract.study import registered, bundle, REGISTRATION
from integrations.benchmark_runtime_v2.freeze import decode, sha


class StudyControls(unittest.TestCase):
    def test_registered_exact_bytes_and_source_scope(self):
        cases = json.loads(registered("COUNTEREXAMPLES.json"))["cases"]
        self.assertEqual(len(cases), 4)
        for case in cases:
            original = bundle(case, "baseline")
            replacement = bundle(case, "candidate")
            a, b = decode(original, original["payload_sha256"]), decode(replacement, replacement["payload_sha256"])
            for phase, source in (("baseline", a), ("candidate", b)):
                self.assertEqual({p: sha(data) for p, data in source.items()}, case["hashes"][phase])
            scope = m.source_scope(a["src/model.alva"].decode(), b["src/model.alva"].decode(),
                                   [case["functions"][0]])
            self.assertEqual(scope["status"], "REJECT" if case["id"] == "C3" else "ALLOW")
            self.assertEqual(a["alva.toml"], b["alva.toml"])

    def test_missing_proof_and_binding_fail_closed(self):
        scope = {"status": "ALLOW"}
        evidence = {"confirmed_failure": False, "bound_complete": True}
        self.assertEqual(m.decide(scope, evidence, "proof", require_strength=True)["verdict"], "UNKNOWN")
        self.assertEqual(m.decide(scope, evidence, "bounded_samples", require_strength=True)["verdict"], "ALLOW")
        evidence["bound_complete"] = False
        self.assertEqual(m.decide(scope, evidence, "bounded_samples", require_strength=True)["verdict"], "UNKNOWN")
        evidence["confirmed_failure"] = True
        self.assertEqual(m.decide(scope, evidence, "proof", require_strength=True)["verdict"], "REJECT")

    def test_dependency_reachability_is_not_behavior(self):
        graph = {"a.f": {}, "a.g": {"n": {"kind": "call", "fields": {"name": "f"}}}}
        result = m.impact((graph,), ["a.f"])
        self.assertEqual(result["potentially_impacted"], ["a.f", "a.g"])
        self.assertTrue(result["complete_for_fixture"])
        evidence = {"confirmed_failure": False, "bound_complete": True}
        self.assertEqual(m.decide({"status": "ALLOW"}, evidence, "bounded_samples", require_strength=True,
                                  coverage=result["complete_for_fixture"])["verdict"], "ALLOW")
        graph["a.g"]["n"]["fields"]["name"] = "unresolved"
        self.assertFalse(m.impact((graph,), ["a.f"])["complete_for_fixture"])

    def test_mechanisms_have_no_expected_verdict_or_oracle(self):
        source = inspect.getsource(m)
        self.assertNotIn("oracle.json", source)
        self.assertNotIn('case["id"]', source)
        result_path = Path(__file__).parent / "BASELINE-COMPARISON.json"
        if result_path.exists():
            r = json.loads(result_path.read_text())
            self.assertEqual(r["registration"], REGISTRATION)
            self.assertEqual(r["model_generation_calls"], 0)
            self.assertEqual(r["input_token_api_calls"], 0)
            for row in r["rows"]:
                if row["status"] != "EXECUTED":
                    continue
                self.assertTrue(row["same_candidate_roots"])
                self.assertTrue(row["guarded"]["fresh_match"])
                self.assertEqual(row["text_candidate"]["observations"], row["native_candidate"]["observations"])


if __name__ == "__main__":
    unittest.main()
