"""Zero-model pilot contract and separate evidence-binding scenarios."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pilots/codex_guard"))
from integrations.python_guard import GuardError
from integrations.python_guard.guard import canonical, digest
from integrations.python_guard_codex import CandidateSession
from prepare import public_files
from tasks import TASKS
from run import evaluate


class FrozenContract(unittest.TestCase):
    def test_complete_actual_freeze(self):
        freeze = json.loads((ROOT / "pilots/codex_guard/EXECUTION-FREEZE.json").read_bytes())
        self.assertEqual(freeze["files"], public_files())
        self.assertEqual(len(freeze["schedule"]), 12)
        for task in TASKS:
            rows = [row for row in freeze["schedule"] if row["task"] == task["id"]]
            self.assertEqual({row["arm"] for row in rows}, {"A", "B"})
            self.assertEqual(rows[0]["source_manifest"], rows[1]["source_manifest"])
            self.assertEqual(rows[0]["candidate_manifest"], rows[1]["candidate_manifest"])
        for name, identity in freeze["reused_hashes"].items():
            self.assertEqual(digest((ROOT / name).read_bytes()), identity)

    def test_six_baseline_expected_outcomes(self):
        for task in TASKS:
            with self.subTest(task=task["id"]), tempfile.TemporaryDirectory() as temp:
                tree = Path(temp) / "source"
                shutil.copytree(ROOT / "pilots/codex_guard/inputs" / task["id"], tree)
                for group, expected in (("regression", 0), ("task", 1)):
                    result = subprocess.run([sys.executable, "-I", "test_pilot.py", group], cwd=tree,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, expected, result.stderr.decode("utf-8", "replace"))

    def test_agent_test_rewrite_cannot_change_terminal_authority(self):
        from prepare import files_manifest
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT / "pilots/codex_guard/inputs/BOLTONS-EXPORTS", root / "source")
            shutil.copytree(root / "source", root / "candidate")
            subprocess.run(["git", "init", "-q", str(root / "candidate")], check=True)
            (root / "candidate/test_pilot.py").write_bytes(b"raise SystemExit(0)\n")
            result = evaluate({"task": "BOLTONS-EXPORTS", "source_manifest": files_manifest(root / "source")}, root)
            self.assertIn("test_pilot.py", result["scope_violations"])
            self.assertEqual(result["independent_checks"]["task"]["status"], "FAIL")
            self.assertFalse(result["task_complete"])


class BindingScenarios(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.project = root / "source"
        self.project.mkdir()
        (self.project / "calc.py").write_bytes(b"def total(values):\n    return sum(values)\n")
        (self.project / "spec.py").write_bytes(b"from calc import total\nassert total([2, 3]) == 5\n")
        (root / "scratch").mkdir()
        policy = {"schema": 1, "project_root": str(self.project), "scratch_root": str(root / "scratch"),
            "files": ["calc.py", "spec.py"], "editable": ["calc.py"], "excluded": {".git": "VCS metadata"},
            "scratch_outputs": ["__pycache__"], "python": sys.executable, "trusted_project": True, "environment": {},
            "checks": [{"id": "public", "argv": ["$PYTHON", "-I", "-c", "import sys; sys.path.insert(0,'.'); exec(open('spec.py').read())"]}],
            "limits": {"max_files": 10, "max_source_bytes": 10000, "max_patch_bytes": 10000,
                "wall_seconds": 10, "output_bytes_per_stream": 4096, "max_command_invocations": 8,
                "max_direct_processes": 1, "address_space_bytes": None, "cpu_seconds": None}}
        policy_file = root / "policy.json"
        policy_file.write_bytes(canonical(policy))
        self.session = CandidateSession.prepare(root / "control", policy_file, root / "candidate", digest(policy_file.read_bytes()))
        self.candidate = self.session.candidate
        subprocess.run(["git", "init", "-q", str(self.candidate)], check=True)
        subprocess.run(["git", "-C", str(self.candidate), "add", "."], check=True)
        (self.candidate / "calc.py").write_bytes(b"def total(values):\n    return sum(values) + 0\n")
        self.assertEqual(self.session.verify()["checks_status"], "PASS")

    def native_tests(self):
        p = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0,'.'); exec(open('spec.py').read())"],
                           cwd=self.candidate, capture_output=True, timeout=10)
        return p.returncode

    def test_stale_source_separate_from_tests(self):
        (self.project / "calc.py").write_bytes(b"# independent source change\ndef total(values):\n    return sum(values)\n")
        self.assertEqual(self.native_tests(), 0)
        self.assertEqual(self.session.report()["applicability_status"], "STALE")

    def test_changed_candidate_separate_from_tests(self):
        (self.candidate / "calc.py").write_bytes(b"def total(values):\n    return sum(values) + 0 + 0\n")
        self.assertEqual(self.native_tests(), 0)
        self.assertFalse(self.session.report()["candidate_matches_verified_patch"])
        self.assertIn(b"calc.py", subprocess.check_output(["git", "-C", str(self.candidate), "diff", "--name-only"]))

    def test_protected_spec_change_detectable_by_git_and_guard(self):
        (self.candidate / "spec.py").write_bytes(b"# invalid spec weakening\n")
        self.assertEqual(self.native_tests(), 0)
        self.assertIn(b"spec.py", subprocess.check_output(["git", "-C", str(self.candidate), "diff", "--name-only"]))
        with self.assertRaises(GuardError) as caught:
            self.session.verify()
        self.assertEqual(caught.exception.code, "PROTECTED_FILE")


if __name__ == "__main__":
    unittest.main()
