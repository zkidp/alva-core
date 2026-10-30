"""Zero-model regression checks for outcome attribution and withheld material."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.p36_mm02_native_model.analyze import analyze

TARGET, OTHER = "store.xml.parse_prefix", "store.xml.parse_delimiter"


class Outcomes(unittest.TestCase):
    def fixture(self, folder, *, commit=False, denied=False, task="PASS", resource=False, mismatch=False):
        from integrations.benchmark_runtime_v2.freeze import canonical, sha
        bundle = {"payload": {"schema": "alva-benchmark-freeze/v2", "byte_policy": "exact-git-blob-no-normalization", "entries": []}}
        bundle["payload_sha256"] = sha(canonical(bundle["payload"]))
        frozen = {"task": {"bundle": bundle, "target": TARGET, "functions": [TARGET, OTHER]}}
        record = {"freeze_commit": "test", "model_tasks_started": 1, "terminal_status": "completed", "events": []}
        before = {TARGET: "before", OTHER: "same"}
        evidence = {"initial_authority": {"bodies": before, "project_revision": "old"},
                    "final_authority": {"bodies": dict(before), "project_revision": "old"},
                    "final_files": {}, "final": {"goal": {"status": task}, "regression": {"status": "PASS"}}}
        rows = []
        if commit or denied:
            record["events"] = [{"method": "item/completed", "params": {"item": {
                "type": "mcpToolCall", "id": "call1", "tool": "commit_transaction", "status": "failed" if denied else "completed"}}}]
            params = {"name": "commit_transaction", "_meta": {"callId": "wrong" if mismatch else "call1"}}
            rows.append({"event": "scope_decision", "params": params,
                         "decision": {"status": "SCOPE_VIOLATION" if denied else "SCOPE_ALLOWED"}})
            if commit:
                rows.append({"event": "native_dispatch", "params": params,
                             "response": {"structuredContent": {"revision": "new"}}})
                evidence["final_authority"] = {"bodies": {TARGET: "after", OTHER: "same"}, "project_revision": "new"}
                evidence["final_files"] = {"alva-air/current": ""}
        if resource:
            record.update(stop_reason="TOKEN_OBSERVATION_LIMIT", terminal_status="interrupted", interrupt_ack=True)
        (folder / "linux.json").write_text(json.dumps(evidence))
        (folder / "guard.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        return analyze(frozen, record, folder)

    def run_case(self, **kwargs):
        with tempfile.TemporaryDirectory() as p:
            return self.fixture(Path(p), **kwargs)

    def test_guard_rejection_is_uncompleted_not_infrastructure(self):
        r = self.run_case(denied=True, task="TEST_FAIL")
        self.assertEqual(r["disposition"], "NO_COMMITTED_CANDIDATE")
        self.assertIsNone(r["infrastructure_hold"])
        self.assertEqual(r["guard_denied"], 1)
        self.assertEqual(r["native_commit_dispatches"], 0)

    def test_detached_or_no_commit_gets_no_success(self):
        self.assertEqual(self.run_case(task="TEST_FAIL")["disposition"], "NO_COMMITTED_CANDIDATE")

    def test_real_commit_and_behavior_conjunction(self):
        self.assertEqual(self.run_case(commit=True)["disposition"], "COMPLETED_CORRECT_MAINTENANCE")
        self.assertEqual(self.run_case(commit=True, task="TEST_FAIL")["disposition"], "COMMITTED_INCORRECT_MAINTENANCE")

    def test_resource_terminal_keeps_authoritative_candidate(self):
        r = self.run_case(commit=True, resource=True)
        self.assertEqual(r["disposition"], "RESOURCE_CENSORED")
        self.assertTrue(r["authoritative_candidate_correct"])

    def test_missing_commit_linkage_is_a_specific_infrastructure_error(self):
        r = self.run_case(commit=True, mismatch=True)
        self.assertEqual(r["disposition"], "INFRASTRUCTURE_HOLD")
        self.assertIn("COMMIT_APP_GUARD_CALL_ID_MISMATCH", r["infrastructure_hold"])


if __name__ == "__main__":
    unittest.main()
