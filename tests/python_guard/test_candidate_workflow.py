"""P2 workflow regressions; not another P1 capability audit."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from integrations.python_guard import GuardError, policy_identity
from integrations.python_guard.patch import apply_patch
from integrations.python_guard_codex import CandidateSession
from integrations.python_guard_codex.workflow import exact_diff


ROOT = Path(__file__).resolve().parents[2]


def policy_for(project, scratch):
    return {"schema": 1, "project_root": str(project), "scratch_root": str(scratch),
            "files": ["cart.py", "tests/test_cart.py"], "editable": ["cart.py"], "excluded": {},
            "scratch_outputs": ["__pycache__", "tests/__pycache__"], "python": sys.executable,
            "trusted_project": True, "environment": {},
            "checks": [{"id": "unit", "argv": ["$PYTHON", "-I", "-m", "unittest", "discover", "-s", "tests"]}],
            "limits": {"max_files": 20, "max_source_bytes": 100000, "max_patch_bytes": 20000,
                       "wall_seconds": 15, "output_bytes_per_stream": 8192, "max_command_invocations": 8,
                       "max_direct_processes": 1, "address_space_bytes": None, "cpu_seconds": None}}


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guard-candidate-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "source"
        shutil.copytree(ROOT / "examples/python_guard_codex/project", self.project,
                        ignore=shutil.ignore_patterns("__pycache__"))
        # Workflow tests use a task-independent baseline-passing test.
        (self.project / "tests/test_cart.py").write_bytes(
            b"import unittest, sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
            b"from cart import total\nclass Tests(unittest.TestCase):\n"
            b"    def test_total(self):\n        self.assertEqual(total([2, 3]), 5)\n")
        self.policy = policy_for(self.project, self.root / "scratch")
        (self.root / "scratch").mkdir()
        self.policy_file = self.root / "policy.json"
        self.policy_file.write_text(json.dumps(self.policy), encoding="utf-8")
        self.before = self.source_bytes()
        self.session = CandidateSession.prepare(self.root / "control", self.policy_file,
            self.root / "candidate", policy_identity(self.policy_file))
        self.addCleanup(lambda: self.assertEqual(self.before, self.source_bytes()))

    def source_bytes(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}

    def edit(self, body=b"def total(values):\n    return sum(values) + 0\n"):
        (self.session.candidate / "cart.py").write_bytes(body)

    def test_real_cli_candidate_verify_report(self):
        self.edit()
        for operation in ("verify", "report"):
            process = subprocess.run([sys.executable, "-m", "integrations.python_guard_codex", operation,
                "--control", str(self.session.control)], cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result["checks_status"], "PASS")
            self.assertEqual(result["applicability_status"], "CURRENT")
        self.assertTrue(result["candidate_matches_verified_patch"])
        self.assertFalse(result["source_apply_supported"])

    def test_behavior_fail_retained(self):
        self.edit(b"def total(values):\n    return 9\n")
        self.assertEqual(self.session.verify()["checks_status"], "FAIL")
        self.assertEqual(self.session.report()["checks_status"], "FAIL")

    def test_untrusted_unknown_retained(self):
        policy = self.policy | {"trusted_project": False}
        other = self.root / "untrusted.json"
        other.write_text(json.dumps(policy), encoding="utf-8")
        session = CandidateSession.prepare(self.root / "other-control", other, self.root / "other-candidate", policy_identity(other))
        (session.candidate / "cart.py").write_bytes(b"def total(values):\n    return sum(values) + 0\n")
        result = session.verify()
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertEqual(result["checks"], [])

    def test_stale_source_retained(self):
        self.edit()
        self.session.verify()
        path = self.project / "cart.py"
        old = path.read_bytes()
        try:
            path.write_bytes(old + b"# concurrent change\n")
            self.assertEqual(self.session.verify()["applicability_status"], "STALE")
            self.assertEqual(self.session.report()["applicability_status"], "STALE")
        finally:
            path.write_bytes(old)

    def test_candidate_changed_after_verification(self):
        self.edit()
        self.session.verify()
        self.edit(b"def total(values):\n    return 9\n")
        report = self.session.report()
        self.assertEqual(report["checks_status"], "PASS")  # historical evidence only
        self.assertFalse(report["candidate_matches_verified_patch"])
        # Standalone launcher works from the consumer directory and must not
        # return a usable green exit code for evidence about an older candidate.
        process = subprocess.run([sys.executable, str(ROOT / "scripts/python_guard_candidate.py"), "report",
            "--control", str(self.session.control)], cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
        self.assertFalse(json.loads(process.stdout)["candidate_matches_verified_patch"])

    def test_policy_change_not_accepted(self):
        self.edit()
        self.policy_file.write_text(json.dumps(self.policy | {"checks": []}), encoding="utf-8")
        with self.assertRaises(GuardError) as error:
            self.session.verify()
        self.assertEqual(error.exception.code, "POLICY_UNAVAILABLE")

    def test_protected_test_edit_rejected(self):
        (self.session.candidate / "tests/test_cart.py").write_bytes(b"# no tests\n")
        with self.assertRaises(GuardError) as error:
            self.session.verify()
        self.assertEqual(error.exception.code, "PROTECTED_FILE")

    def test_undeclared_file_rejected(self):
        (self.session.candidate / "unapproved.py").write_bytes(b"x = 1\n")
        with self.assertRaises(GuardError) as error:
            self.session.verify()
        self.assertEqual(error.exception.code, "UNDECLARED_FILE")

    def test_no_edit_is_not_pass(self):
        response = self.session.tool_call("guard_verify", {})
        self.assertFalse(response["success"])
        self.assertIn("NO_CANDIDATE_CHANGE", response["contentItems"][0]["text"])

    def test_callback_cannot_override_policy_or_path(self):
        for name, arguments in (("guard_verify", {"trusted_project": True}), ("guard_report", {"control": "/other"}),
                                ("apply", {}), ("guard_verify", [])):
            self.assertFalse(self.session.tool_call(name, arguments)["success"])

    def test_overlapping_candidate_rejected(self):
        with self.assertRaises(GuardError):
            CandidateSession.prepare(self.root / "new-control", self.policy_file, self.project / "candidate", policy_identity(self.policy_file))
        self.assertFalse((self.project / "candidate").exists())

    def test_prepare_requires_exact_approval(self):
        with self.assertRaises(GuardError):
            CandidateSession.prepare(self.root / "new-control", self.policy_file, self.root / "new-candidate", "sha256:" + "0" * 64)
        self.assertFalse((self.root / "new-control").exists())

    def test_exact_patch_byte_roundtrip(self):
        for old, new in ((b"a\r\nb\r\n", b"a\r\nc"), (b"x", b"y"), (b"", b"a\n"), (b"a\n", b"")):
            originals, candidate = {"cart.py": old}, {"cart.py": new}
            self.assertEqual(apply_patch(exact_diff(originals, candidate), originals), candidate)
        for originals, candidate in (({}, {"cart.py": b"x"}), ({"cart.py": b"x"}, {})):
            changes = apply_patch(exact_diff(originals, candidate), originals)
            self.assertEqual(changes, {"cart.py": candidate.get("cart.py")})


if __name__ == "__main__":
    unittest.main()
