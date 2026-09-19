#!/usr/bin/env python3
"""Tests for the acceptance harness, not additional specification samples."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("sm_reproduce", Path(__file__).resolve().parents[1] / "reproduce.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class HarnessTests(unittest.TestCase):
    def result(self, code=1, out=b"", err=b"json.pointer: invalid percent escape"):
        return subprocess.CompletedProcess(["supplied-component"], code, out, err)

    def test_classified_rejection_only(self):
        case = {"id": "reject", "error": "percent escape"}
        demo.check_outcome(self.result(), case, "after")
        bad = [self.result(code=0), self.result(code=-9), self.result(code=101),
               self.result(code=137), self.result(out=b"{}"), self.result(err=b"killed"),
               self.result(err=b"panicked at: percent escape")]
        for result in bad:
            with self.subTest(result=result), self.assertRaises(AssertionError):
                demo.check_outcome(result, case, "after")

    def test_success_exact_types_and_complete_json(self):
        case = {"id": "success", "expected": demo.JSON.semantic_json("9007199254740993.0")}
        demo.check_outcome(self.result(0, b"9007199254740993", b""), case, "after")
        for output in (b"9007199254740992", b"true", b"{", b"", b"1 2", b"NaN", b"\xff"):
            with self.subTest(output=output), self.assertRaises((AssertionError, ValueError, UnicodeError)):
                demo.check_outcome(self.result(0, output, b""), case, "after")

    def test_baseline_unsupported_is_not_after_success(self):
        case = {"id": "new", "new": True, "expected": 1}
        result = self.result(err=b"json.patch: mode must be pointer or patch")
        demo.check_outcome(result, case, "before")
        with self.assertRaises(AssertionError):
            demo.check_outcome(result, case, "after")

    def test_timeout_and_missing_program_are_logged_failures(self):
        for error in (FileNotFoundError("missing"), subprocess.TimeoutExpired("component", 0.01)):
            with tempfile.TemporaryDirectory(prefix="sm-harness-") as temp:
                session = demo.Session(Path(temp), offline=True)
                with patch.object(demo.subprocess, "run", side_effect=error):
                    with self.assertRaises(type(error)):
                        session.run(["missing-component"], payload=b"{}", check=False)
                self.assertIn("infrastructure_error", session.report["commands"][0])
                self.assertTrue((Path(temp) / "RESULTS.json").exists())


if __name__ == "__main__":
    unittest.main()
