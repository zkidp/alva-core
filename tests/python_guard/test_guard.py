"""Deterministic real-Python acceptance for the standalone Guard."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch as mock_patch
from pathlib import Path

from integrations.python_guard import Guard, GuardError, policy_identity
from integrations.python_guard.guard import digest
from integrations.python_guard.patch import apply_patch
from integrations.python_guard.runner import execute


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixture"


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guard-acceptance-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.project = self.directory / "project"
        shutil.copytree(FIXTURE, self.project, ignore=shutil.ignore_patterns("__pycache__"))
        self.scratch = self.directory / "scratch"
        self.scratch.mkdir()
        self.store = self.directory / "evidence"
        self.policy_file = self.directory / "approved-policy.json"
        self.policy = {
            "schema": 1, "project_root": str(self.project), "scratch_root": str(self.scratch),
            "files": ["calc.py", "tests/test_calc.py", "extra.py"], "editable": ["calc.py", "extra.py"],
            "excluded": {".git": "VCS metadata excluded"}, "scratch_outputs": ["__pycache__", "tests/__pycache__"],
            "python": sys.executable, "environment": {}, "trusted_project": True,
            "checks": [{"id": "unit", "argv": ["$PYTHON", "-I", "-m", "unittest", "discover", "-s", "tests"]}],
            "limits": {"max_files": 20, "max_source_bytes": 100000, "max_patch_bytes": 20000,
                       "wall_seconds": 15, "output_bytes_per_stream": 16384, "max_command_invocations": 8,
                       "max_direct_processes": 1, "address_space_bytes": None, "cpu_seconds": None},
        }
        self.approve()

    def approve(self):
        self.policy_file.write_text(json.dumps(self.policy), encoding="utf-8")
        self.policy_id = policy_identity(self.policy_file)
        self.guard = Guard(self.store, self.policy_file)

    def snapshot(self):
        return self.guard.snapshot({"project_root": str(self.project), "policy_id": self.policy_id,
                                    "files": self.policy["files"]})

    def patch(self, new: str, name="calc.py"):
        old = (self.project / name).read_bytes().decode("utf-8") if (self.project / name).exists() else ""
        return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                           fromfile="a/" + name if old else "/dev/null", tofile="b/" + name))

    def request(self, snapshot=None, patch=None):
        snapshot = snapshot or self.snapshot()
        patch = patch if patch is not None else self.patch("def total(values):\n    return sum(values) + 0\n")
        changes = apply_patch(patch, {r["path"]: (self.project / r["path"]).read_bytes() for r in snapshot["manifest"]})
        hashes = {r["path"]: r["sha256"] for r in snapshot["manifest"]}
        return {"snapshot_id": snapshot["snapshot_id"], "policy_id": self.policy_id, "patch_utf8": patch,
                "expected_files": {name: hashes.get(name) for name in changes}}

    def verify(self, request):
        # This invariant is checked for every accepted/rejected/failing verify path.
        before = {p.relative_to(self.project).as_posix(): p.read_bytes()
                  for p in self.project.rglob("*") if p.is_file() and not p.is_symlink()}
        try:
            return self.guard.verify(request)
        finally:
            after = {p.relative_to(self.project).as_posix(): p.read_bytes()
                     for p in self.project.rglob("*") if p.is_file() and not p.is_symlink()}
            self.assertEqual(before, after, "verify modified original project bytes")

    def rejection(self, request, code):
        with self.assertRaises(GuardError) as caught:
            self.verify(request)
        self.assertEqual(caught.exception.code, code)

    def test_valid_patch_real_cli_and_report(self):
        request = self.request()
        request_file = self.directory / "verify.json"
        request_file.write_text(json.dumps(request), encoding="utf-8")
        completed = subprocess.run([sys.executable, "-m", "integrations.python_guard", "--store", str(self.store),
            "--policy", str(self.policy_file), "verify", "--request", str(request_file)], cwd=ROOT,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["checks_status"], "PASS")
        self.assertEqual(result["applicability_status"], "CURRENT")
        current = self.snapshot()
        report = Guard(self.store).report({"verification_id": result["verification_id"],
                                           "current_snapshot_id": current["snapshot_id"]})
        self.assertEqual(report["checks_status"], "PASS")
        self.assertEqual(report["applicability_status"], "CURRENT")
        self.assertEqual(report["evidence_integrity"], "PASS")
        self.assertTrue(all(r["classification"] == "BOTH_PASS" for r in report["regression"]))
        self.assertEqual(len(report["checks"]), 4)

    def test_report_without_fresh_snapshot_never_claims_current(self):
        result = self.verify(self.request())
        (self.project / "calc.py").write_text("changed since verification\n")
        report = self.guard.report({"verification_id": result["verification_id"]})
        self.assertEqual(report["applicability_status"], "UNKNOWN")
        self.assertEqual(report["recorded_applicability_status"], "CURRENT")

    def test_syntax_error_is_new_regression(self):
        result = self.verify(self.request(patch=self.patch("def total(:\n")))
        self.assertEqual(result["checks_status"], "FAIL")
        syntax = next(r for r in result["regression"] if r["id"] == "syntax")
        self.assertEqual(syntax["classification"], "NEW_REGRESSION")

    def test_behavioral_failure_after_syntax_pass(self):
        result = self.verify(self.request(patch=self.patch("def total(values):\n    return 1\n")))
        self.assertEqual(result["checks_status"], "FAIL")
        self.assertEqual(result["checks"][1]["status"], "PASS")
        self.assertEqual(result["regression"][1]["classification"], "NEW_REGRESSION")

    def test_baseline_failure_not_new_regression(self):
        self.policy["checks"] = [{"id": "existing", "argv": ["$PYTHON", "-I", "-c", "raise SystemExit(7)"]}]
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "FAIL")
        self.assertEqual(result["regression"][1]["classification"], "BASELINE_AND_CANDIDATE_FAIL")

    def test_baseline_failure_closed(self):
        (self.project / "calc.py").write_text("def total(values):\n    return -1\n")
        result = self.verify(self.request(patch=self.patch("def total(values):\n    return sum(values)\n")))
        self.assertEqual(result["checks_status"], "PASS")
        self.assertEqual(result["regression"][1]["classification"], "BASELINE_FAILURE_CLOSED")

    def test_protected_tests_rejected(self):
        request = self.request(patch=self.patch("# weakened test\n", "tests/test_calc.py"))
        self.rejection(request, "PROTECTED_FILE")

    def test_dirty_source_bytes_are_snapshot_authority(self):
        (self.project / ".git").mkdir()
        (self.project / ".git" / "HEAD").write_text("unchanged-vcs-ref")
        first = self.snapshot()
        (self.project / "calc.py").write_text("# uncommitted\ndef total(values):\n    return sum(values)\n")
        second = self.snapshot()
        self.assertNotEqual(first["tree_digest"], second["tree_digest"])
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertEqual((self.project / ".git" / "HEAD").read_text(), "unchanged-vcs-ref")
        self.assertEqual(self.verify(self.request(second))["checks_status"], "PASS")

    def test_stale_snapshot_never_executes(self):
        request = self.request()
        (self.project / "calc.py").write_text("def total(values):\n    return -1\n")
        result = self.verify(request)
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertEqual(result["applicability_status"], "STALE")
        self.assertEqual(result["checks"], [])

    def test_report_detects_stale_after_verification(self):
        result = self.verify(self.request())
        (self.project / "extra.py").write_text("x = 1\n")
        current = self.snapshot()
        report = self.guard.report({"verification_id": result["verification_id"],
                                    "current_snapshot_id": current["snapshot_id"]})
        self.assertEqual(report["checks_status"], "PASS")
        self.assertEqual(report["applicability_status"], "STALE")

    def test_wrong_preimage_hash(self):
        request = self.request()
        request["expected_files"]["calc.py"] = "sha256:" + "0" * 64
        self.rejection(request, "PREIMAGE_MISMATCH")

    def test_exact_context_no_offset_or_fuzz(self):
        request = self.request()
        request["patch_utf8"] = request["patch_utf8"].replace("return sum(values)", "return sum(other)")
        self.rejection(request, "PREIMAGE_MISMATCH")

    def test_patch_path_escape(self):
        request = self.request()
        request["patch_utf8"] = request["patch_utf8"].replace("a/calc.py", "a/../calc.py").replace("b/calc.py", "b/../calc.py")
        self.rejection(request, "PATH_OUTSIDE_ROOT")

    def test_symlink_rejected(self):
        target = self.project / "extra.py"
        try:
            target.symlink_to(self.project / "calc.py")
        except OSError:
            self.skipTest("host does not permit symlink creation")
        with self.assertRaises(GuardError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, "UNSUPPORTED_FILE")

    def test_undeclared_file_not_silently_omitted(self):
        (self.project / "surprise.py").write_text("x=1\n")
        with self.assertRaises(GuardError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, "UNDECLARED_FILE")

    def test_untrusted_project_no_execution(self):
        self.policy["trusted_project"] = False
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("UNTRUSTED_EXECUTION_UNSUPPORTED", result["reasons"])
        self.assertEqual(result["checks"], [])

    def test_timeout_is_unknown(self):
        self.policy["checks"] = [{"id": "slow", "argv": ["$PYTHON", "-I", "-c", "import time; time.sleep(20)"]}]
        self.policy["limits"]["wall_seconds"] = 1
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("TIMEOUT", result["reasons"])
        self.assertEqual(result["regression"][1]["classification"], "UNKNOWN")

    def test_output_limit_is_unknown_and_bounded(self):
        self.policy["checks"] = [{"id": "spam", "argv": ["$PYTHON", "-I", "-c", "print('x'*100000)"]}]
        self.policy["limits"]["output_bytes_per_stream"] = 1024
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("OUTPUT_LIMIT", result["reasons"])
        row = next(r for r in result["checks"] if r["id"] == "spam")
        self.assertLessEqual(row["stdout"]["bytes_retained"], 1024)

    def test_missing_interpreter(self):
        self.policy["python"] = str(self.directory / "missing-python")
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("PYTHON_UNAVAILABLE", result["reasons"])

    def test_missing_check_executable(self):
        self.policy["checks"] = [{"id": "missing", "argv": [str(self.directory / "missing-tool")]}]
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("EXECUTION_ENVIRONMENT_UNAVAILABLE", result["reasons"])

    def test_missing_dependency(self):
        self.policy["checks"] = [{"id": "dependency", "argv": ["$PYTHON", "-I", "-c", "import unavailable_guard_fixture_dependency"]}]
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("MISSING_OR_UNUSABLE_DEPENDENCY", result["reasons"])

    def test_mutating_checker_is_unknown(self):
        self.policy["checks"] = [{"id": "mutator", "argv": ["$PYTHON", "-I", "-c",
            "from pathlib import Path; Path('calc.py').write_text('changed')"]}]
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("CHECK_MODIFIED_INPUT", result["reasons"])

    def test_budget_does_not_expand(self):
        request = self.request()
        request["limits"] = {"wall_seconds": 9999}
        self.rejection(request, "INPUT_LIMIT")

    def test_invocation_budget(self):
        self.policy["limits"]["max_command_invocations"] = 2
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertEqual(sum(r["status"] == "NOT_RUN" for r in result["checks"]), 2)

    def test_policy_identity_required(self):
        request = self.request()
        request["policy_id"] = "sha256:" + "0" * 64
        self.rejection(request, "POLICY_UNAVAILABLE")

    def test_mutable_policy_dictionary_cannot_weaken_approval(self):
        self.guard.policy["editable"].append("tests/test_calc.py")
        request = self.request(patch=self.patch("# weakened test\n", "tests/test_calc.py"))
        self.rejection(request, "PROTECTED_FILE")

    def test_policy_inside_source_rejected(self):
        target = self.project / "policy.json"
        target.write_bytes(self.policy_file.read_bytes())
        with self.assertRaises(GuardError):
            Guard(self.store, target)

    def test_snapshot_blob_tamper(self):
        request = self.request()
        snapshot = self.snapshot()
        blob = self.store / "blobs" / snapshot["manifest"][0]["sha256"][7:]
        blob.write_bytes(b"tampered")
        self.rejection(request, "EVIDENCE_TAMPERED")

    def test_unstable_capture_has_no_snapshot(self):
        original_scan = self.guard._scan
        calls = 0

        def racing_scan(*args, **kwargs):
            nonlocal calls
            result = original_scan(*args, **kwargs)
            calls += 1
            if calls == 1:
                (self.project / "calc.py").write_bytes(b"# concurrent capture change\n")
            return result

        with mock_patch.object(self.guard, "_scan", side_effect=racing_scan), self.assertRaises(GuardError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, "UNSTABLE_CAPTURE")
        self.assertEqual(list((self.store / "snapshots").glob("*.json")), [])

    def test_source_changed_during_checks_is_stale_not_restored(self):
        request = self.request()
        original_run = self.guard._run_checks
        concurrent = b"# independent concurrent edit\ndef total(v): return sum(v)\n"

        def concurrent_change(*args):
            original_run(*args)
            (self.project / "calc.py").write_bytes(concurrent)

        with mock_patch.object(self.guard, "_run_checks", side_effect=concurrent_change):
            result = self.guard.verify(request)
        self.assertEqual(result["checks_status"], "PASS")
        self.assertEqual(result["applicability_status"], "STALE")
        self.assertEqual((self.project / "calc.py").read_bytes(), concurrent)

    def test_read_only_report_does_not_rewrite_evidence(self):
        result = self.verify(self.request())
        current = self.snapshot()
        before = {p.relative_to(self.store): p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
        self.guard.report({"verification_id": result["verification_id"], "current_snapshot_id": current["snapshot_id"]})
        after = {p.relative_to(self.store): p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_report_does_not_create_nonexistent_store(self):
        missing = self.directory / "missing-store"
        with self.assertRaises(GuardError):
            Guard(missing)
        self.assertFalse(missing.exists())

    def test_record_tamper(self):
        result = self.verify(self.request())
        path = self.store / "verifications" / (result["verification_id"].split(":")[1] + ".json")
        record = json.loads(path.read_bytes())
        record["checks_status"] = "fabricated"
        path.write_text(json.dumps(record))
        with self.assertRaises(GuardError) as caught:
            self.guard.report({"verification_id": result["verification_id"]})
        self.assertEqual(caught.exception.code, "EVIDENCE_TAMPERED")

    def test_candidate_blob_tamper(self):
        result = self.verify(self.request())
        blob = self.store / "blobs" / result["candidate_manifest"][0]["sha256"][7:]
        blob.write_bytes(b"tampered candidate")
        with self.assertRaises(GuardError):
            self.guard.report({"verification_id": result["verification_id"]})

    def test_patch_blob_tamper_cli_unknown(self):
        result = self.verify(self.request())
        (self.store / "blobs" / result["patch_sha256"][7:]).write_bytes(b"fake patch")
        request = self.directory / "report.json"
        request.write_text(json.dumps({"verification_id": result["verification_id"]}))
        completed = subprocess.run([sys.executable, "-m", "integrations.python_guard", "--store", str(self.store),
            "report", "--request", str(request)], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["checks_status"], "UNKNOWN")
        self.assertEqual(json.loads(completed.stdout)["reason"], "EVIDENCE_TAMPERED")

    def test_policy_blob_tamper(self):
        result = self.verify(self.request())
        (self.store / "blobs" / self.policy_id[7:]).write_bytes(b"changed policy")
        with self.assertRaises(GuardError):
            self.guard.report({"verification_id": result["verification_id"]})

    def test_addition_and_unrelated_edit(self):
        result = self.verify(self.request(patch=self.patch("# unrelated\nx = 1\n", "extra.py")))
        self.assertEqual(result["checks_status"], "PASS")
        self.assertFalse((self.project / "extra.py").exists())

    def test_delete_source(self):
        (self.project / "extra.py").write_bytes(b"x=1\n")
        snapshot = self.snapshot()
        patch = "--- a/extra.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x=1\n"
        result = self.verify(self.request(snapshot, patch))
        self.assertEqual(result["checks_status"], "PASS")
        self.assertTrue((self.project / "extra.py").exists())

    def test_check_environment_does_not_inherit_secrets(self):
        os.environ["ALVA_GUARD_FIXTURE_SECRET"] = "must-not-inherit"
        self.addCleanup(os.environ.pop, "ALVA_GUARD_FIXTURE_SECRET", None)
        self.policy["checks"] = [{"id": "environment", "argv": ["$PYTHON", "-I", "-c",
            "import os; assert 'ALVA_GUARD_FIXTURE_SECRET' not in os.environ"]}]
        self.approve()
        self.assertEqual(self.verify(self.request())["checks_status"], "PASS")

    def test_bounded_capture_limits(self):
        self.policy["limits"]["max_source_bytes"] = 1
        self.approve()
        with self.assertRaises(GuardError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, "INPUT_LIMIT")

    def test_unsupported_resource_envelope_never_passes(self):
        if os.name != "nt":
            self.skipTest("Windows-only unavailable RLIMIT_AS path")
        self.policy["limits"]["address_space_bytes"] = 1024 * 1024 * 1024
        self.approve()
        result = self.verify(self.request())
        self.assertEqual(result["checks_status"], "UNKNOWN")
        self.assertIn("UNSUPPORTED_RESOURCE_LIMIT", result["reasons"])

    @unittest.skipUnless(os.name == "posix", "POSIX address-space envelope")
    def test_address_space_limit_failure_not_green(self):
        self.policy["limits"]["address_space_bytes"] = 128 * 1024 * 1024
        self.policy["checks"] = [{"id": "memory", "argv": ["$PYTHON", "-I", "-c", "x=bytearray(512*1024*1024)"]}]
        self.approve()
        result = self.verify(self.request())
        self.assertNotEqual(result["checks_status"], "PASS")

    def test_owned_descendant_cleanup_after_parent_exits(self):
        pid_file = self.directory / "descendant.pid"
        child = "import os,time,pathlib; pathlib.Path(" + repr(str(pid_file)) + ").write_text(str(os.getpid())); time.sleep(30)"
        parent = "import subprocess,sys; subprocess.Popen([sys.executable,'-I','-c'," + repr(child) + "])"
        started = time.monotonic()
        result = execute([sys.executable, "-I", "-c", parent], self.scratch,
                         {"SystemRoot": os.environ.get("SystemRoot", ""), "PATH": os.defpath},
                         self.policy["limits"] | {"wall_seconds": 1})
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(result["reason"], "TIMEOUT")
        self.assertTrue(pid_file.exists())
        pid = int(pid_file.read_text())
        if os.name == "nt":
            import ctypes
            kernel = ctypes.WinDLL("kernel32")
            handle = kernel.OpenProcess(0x1000, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel.CloseHandle(handle)
                self.assertNotEqual(exit_code.value, 259, "owned descendant is still active")
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            else:
                status = Path(f"/proc/{pid}/status")
                self.assertTrue(status.exists() and "State:\tZ" in status.read_text())


class PatchTests(unittest.TestCase):
    def test_platform_path_aliases_rejected(self):
        for name in ("/absolute.py", "../escape.py", "a/../../escape.py", "C:/escape.py", "a\\escape.py", "a//x.py", "a/./x.py", "CON.py"):
            with self.subTest(name=name), self.assertRaises(GuardError):
                apply_patch(f"--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-a\n+b\n", {name: b"a\n"})

    def test_content_looking_like_file_header(self):
        patch = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n--- old\n+new\n"
        self.assertEqual(apply_patch(patch, {"x.py": b"-- old\n"}), {"x.py": b"new\n"})

    def test_crlf_preserved_exactly(self):
        patch = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-x=1\r\n+x=2\r\n"
        self.assertEqual(apply_patch(patch, {"x.py": b"x=1\r\n"}), {"x.py": b"x=2\r\n"})

    def test_preserve_no_final_newline(self):
        patch = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-x=1\n\\ No newline at end of file\n+x=2\n\\ No newline at end of file\n"
        self.assertEqual(apply_patch(patch, {"x.py": b"x=1"}), {"x.py": b"x=2"})

    def test_wrong_hunk_count(self):
        with self.assertRaises(GuardError):
            apply_patch("--- a/x.py\n+++ b/x.py\n@@ -1,2 +1 @@\n-x=1\n+x=2\n", {"x.py": b"x=1\n"})

    def test_rename_mode_binary_rejected(self):
        for patch in ("old mode 100644\nnew mode 100755\n", "GIT binary patch\n", "--- a/x.py\n+++ b/y.py\n@@ -1 +1 @@\n-a\n+b\n"):
            with self.subTest(patch=patch), self.assertRaises(GuardError):
                apply_patch(patch, {"x.py": b"a\n"})


if __name__ == "__main__":
    unittest.main()
