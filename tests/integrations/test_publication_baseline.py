"""Real Git tests; actual ALVA execution is a separate Linux-only integration."""
import tempfile
import unittest
from pathlib import Path
from scripts import publication_baseline_feasibility as study


def receipt(files, status="PASS"):
    # Explicit unit stub; never used by the Linux feasibility execution.
    return {"status": status, "checks": {key: status for key in ("check", "build", "test")}}


class GitBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = {p: (study.SAMPLE / p).read_bytes() for p in study.INPUTS}
        self.git = study.GitPublication(Path(self.temp.name) / "case", self.base)
        self.candidate = study.candidate_source(self.base, study.CORRECT)

    def test_checked_blob_is_published_not_later_editor_bytes(self):
        self.assertEqual(self.git.prepare(self.candidate, receipt)["status"], "PREPARED")
        self.candidate["src/model.alva"] = b"later mutable proposal"
        self.assertEqual(self.git.publish(self.base)["status"], "PUBLISHED")
        self.assertNotEqual(self.git.files(self.git.current()), self.candidate)
        self.assertEqual(self.git.publish(self.base)["status"], "REJECTED")

    def test_real_ref_compare_and_swap_rejects_concurrent_advance(self):
        self.git.prepare(self.candidate, receipt)
        concurrent = self.git.object(study.candidate_source(self.base, study.ALTERNATE))
        self.git.run("update-ref", study.REF, concurrent, self.git.base_oid)
        result = self.git.publish(self.base)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(result["stale_base_confirmed"])
        self.assertEqual(self.git.current(), concurrent)

    def test_changed_source_and_failed_new_preparation_reject(self):
        self.git.prepare(self.candidate, receipt)
        changed = dict(self.base)
        changed["src/app.alva"] += b"\n"
        self.assertEqual(self.git.publish(changed)["reason"], "SOURCE_BASE_CHANGED")
        self.git.prepare(self.candidate, receipt)
        self.git.prepare(self.candidate, lambda files: receipt(files, "FAIL"))
        self.assertEqual(self.git.publish(self.base)["status"], "REJECTED")
        self.assertEqual(self.git.current(), self.git.base_oid)

    def test_protected_bytes_and_paths_are_not_authorized(self):
        bad = dict(self.candidate)
        bad["src/app.alva"] += b"\n"
        self.assertFalse(study.allowed_source_change(self.base, bad))
        bad = dict(self.candidate, **{"extra.alva": b"extra"})
        self.assertFalse(study.allowed_source_change(self.base, bad))
        with self.assertRaises(ValueError):
            self.git.object(bad)


if __name__ == "__main__":
    unittest.main()
