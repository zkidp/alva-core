"""Bounded evidence/driver tests; no historical gates or model calls."""
import copy
import json
import unittest
from benchmarks.p33_shared_scope import reproduce as r


class Tests(unittest.TestCase):
    def task(self):
        return next(t for t in json.loads(r.prior.CATALOGUE.read_text())["candidates"] if t["id"] == "MM02")

    def test_exact_original_and_neutral_control(self):
        t = self.task()
        self.assertEqual(t["bundle"]["payload_sha256"], "352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf")
        source = r.decode(t["bundle"], t["bundle"]["payload_sha256"])
        changed = r.control_source(source)
        self.assertEqual(changed["src/model.alva"], source["src/model.alva"])
        self.assertEqual(changed["alva.toml"], source["alva.toml"])
        text = changed["src/xml.alva"].decode()
        self.assertEqual(text.count("delimiter_found"), 2)
        self.assertEqual(text.replace("delimiter_found", "found").encode(), source["src/xml.alva"])

    def test_recorded_results_and_hash(self):
        summary = json.loads((r.HERE / "RESULTS.json").read_text())
        r.validate(summary)
        for label in ("MM02_original", "nonshared_alpha_control"):
            node = summary["rows"][label]["sharing"]["parent"]
            self.assertEqual(r.if_revision(node), r.SHARED)
            self.assertEqual(node["entity"], "")
        sharing = json.loads((r.HERE / "SHARING.json").read_text())
        staged = sharing["MM02_original"]["staged_parents_at_same_paths"]
        self.assertEqual(staged[r.TARGET], staged[r.OTHER])
        self.assertNotEqual(staged[r.TARGET]["revision"], r.SHARED)
        self.assertEqual(r.if_revision(staged[r.TARGET]), staged[r.TARGET]["revision"])

    def test_false_pass_and_incomplete_preview_rejected(self):
        summary = json.loads((r.HERE / "RESULTS.json").read_text())
        for key, value in (("check", {"problems": ["bad"]}), ("preview", {"diff": "CHANGED function store.xml.parse_prefix"}),
                           ("final", dict(summary["rows"]["MM02_original"]["final"], regression="PASS"))):
            edited = copy.deepcopy(summary)
            edited["rows"]["MM02_original"][key] = value
            with self.assertRaises(AssertionError):
                r.validate(edited)

    def test_historical_input_binding(self):
        summary = json.loads((r.HERE / "RESULTS.json").read_text())
        for name, digest in summary["input_code_sha256"].items():
            if name.startswith("benchmarks/maintenance_design/"):
                self.assertEqual(r.sha((r.ROOT / name).read_bytes()), digest, name)
        old = json.loads((r.prior.HERE / "FEASIBILITY.json").read_text())
        row = next(t for t in old["rows"] if t["id"] == "MM02")
        self.assertEqual(row["native"], "FAILED_NON_TARGET_SCOPE")
        self.assertEqual(row["scope_hazard"]["attachment_parent_revision"], r.SHARED)


if __name__ == "__main__":
    unittest.main()
