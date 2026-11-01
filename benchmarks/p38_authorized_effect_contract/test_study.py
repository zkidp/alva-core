"""Necessary controls: frozen input identity, evidence strength and fairness."""
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

from benchmarks.p38_authorized_effect_contract import mechanisms as m
from benchmarks.p38_authorized_effect_contract.study import registered, bundle, REGISTRATION
from benchmarks.p38_authorized_effect_contract import study
from integrations.benchmark_runtime_v2.freeze import decode, sha


class StudyControls(unittest.TestCase):
    def test_snapshot_tampering_fails_closed(self):
        snapshot = study.registration_snapshot()
        snapshot["payload"]["entries"][0]["base64"] = "AA=="
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "REGISTERED-INPUTS.json").write_text(json.dumps(snapshot), encoding="utf-8")
            with patch.object(study, "HERE", path):
                with self.assertRaisesRegex(ValueError, "snapshot identity"):
                    registered("COUNTEREXAMPLES.json")

    def test_original_bundle_identities_preserved(self):
        rows = json.loads((study.HERE / "BASELINE-COMPARISON.json").read_bytes())["rows"]
        cases = json.loads(registered("COUNTEREXAMPLES.json"))["cases"]
        for case, row in zip(cases, rows):
            self.assertEqual(case["id"], row["id"])
            self.assertEqual(bundle(case, "baseline")["payload_sha256"], row["bundle_sha256"])
            self.assertEqual(bundle(case, "candidate")["payload_sha256"], row["candidate_bundle_sha256"])

    def test_historyless_checkout_and_changed_input_rejection(self):
        # Export only the current tree, then create a brand-new root commit:
        # no borrowed Git objects, original registration commit, or branch refs.
        archive = subprocess.check_output(
            ["git", "-c", "core.autocrlf=false", "archive", "--format=zip", "HEAD"], cwd=study.ROOT)
        with tempfile.TemporaryDirectory(prefix="p38-historyless-") as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                z.extractall(root)
            env = dict(os.environ)
            for key in tuple(env):
                if key.startswith("GIT_") or key in {"PYTHONPATH", "PYTHONHOME"}:
                    env.pop(key)
            env["GIT_CONFIG_NOSYSTEM"] = "1"
            env["GIT_CONFIG_GLOBAL"] = os.devnull
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, check=True)
            git("init", "-q")
            git("-c", "core.autocrlf=false", "add", ".")
            git("-c", "user.name=P38 Regression", "-c", "user.email=p38@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "-qm", "historyless tree")
            absent = subprocess.run(["git", "cat-file", "-e", REGISTRATION], cwd=root,
                                    env=env, capture_output=True)
            self.assertNotEqual(absent.returncode, 0)
            code = ("import json; from benchmarks.p38_authorized_effect_contract import study as s; "
                    "s.validate_registered_inputs(); "
                    "cases=json.loads(s.registered('COUNTEREXAMPLES.json'))['cases']; "
                    "assert len(cases)==4; "
                    "[s.bundle(c,p) for c in cases for p in ('baseline','candidate')]")
            run = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            fixture = root / study.PREFIX / "fixtures/C1/candidate/src/model.alva"
            fixture.write_bytes(fixture.read_bytes() + b"\n// changed input\n")
            run = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True)
            self.assertNotEqual(run.returncode, 0)
            git("add", ".")
            git("-c", "user.name=P38 Regression", "-c", "user.email=p38@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "-qm", "changed registered fixture")
            run = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True)
            self.assertNotEqual(run.returncode, 0)

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
