"""Synthetic adapter/scoring tests; CI does not call models or read old traces."""
import copy
import json
import unittest

from benchmarks.p28_optional_descriptor.observer import ObservedNative
from benchmarks.p28_optional_descriptor import pilot


class Native:
    def __init__(self):
        self.body = "body 3"
        self.calls = []
        self.reply = {"structuredContent": {"revision": "r"}, "content": [{"type": "text", "text": "unchanged reply"}]}

    def request(self, method, params, **kwargs):
        self.calls.append((method, copy.deepcopy(params)))
        name = params.get("name")
        if name == "begin_transaction":
            return {"structuredContent": {"transaction_id": "tx"}}
        if name == "inspect_body":
            return {"structuredContent": {"body": self.body}}
        if name == "change_field":
            self.body = "body 4"
        return self.reply


class Tests(unittest.TestCase):
    def wrapped(self):
        self.inner, self.rows = Native(), []
        self.native = ObservedNative(self.inner, self.rows.append)
        self.call("begin_transaction", {"project": "fixture"})

    def call(self, name, args):
        return self.native.request("tools/call", {"name": name, "arguments": args, "_meta": {"callId": name}})

    def test_detached_vs_connected(self):
        self.wrapped()
        answer = self.call("create_reference", {"transaction_id": "tx", "name": "x"})
        self.assertIs(answer, self.inner.reply)
        self.assertFalse(self.rows[-1]["changed_from_transaction_start"])
        self.call("change_field", {"transaction_id": "tx", "field": "value", "value": "4"})
        self.assertTrue(self.rows[-1]["changed_from_transaction_start"])
        observer = [p for m, p in self.inner.calls if p["name"] == "inspect_body"]
        self.assertTrue(all(p["arguments"]["transaction_id"] == "tx" for p in observer))
        self.assertEqual(len(observer), 3)

    def test_host_reads_and_discovery_not_agent_operations(self):
        self.wrapped()
        count = len(self.rows)
        self.native.tool("create_reference", {"transaction_id": "tx", "name": "x"})
        self.native.request("tools/list", {})
        self.assertEqual(len(self.rows), count)

    def test_missing_baseline_fails_closed(self):
        self.inner, self.rows = Native(), []
        self.native = ObservedNative(self.inner, self.rows.append)
        with self.assertRaisesRegex(RuntimeError, "MISSING_TRANSACTION_BASELINE"):
            self.call("create_reference", {"transaction_id": "tx"})

    def test_observer_failure_not_silent_no_change(self):
        self.wrapped()
        original = self.inner.request
        def fail(method, params, **kw):
            if params.get("name") == "inspect_body":
                return {"isError": True}
            return original(method, params, **kw)
        self.inner.request = fail
        with self.assertRaisesRegex(RuntimeError, "BODY_UNAVAILABLE"):
            self.call("create_reference", {"transaction_id": "tx"})

    def test_exact_public_input_and_design(self):
        f = pilot.inputs()
        self.assertEqual([s["condition"] for s in f["schedule"]], ["C1", "C0"])
        self.assertEqual(f["schedule"][0]["prompt"], f["schedule"][1]["prompt"])
        for doc in f["docs"].values():
            self.assertIn(doc, f["schedule"][0]["prompt"])
        self.assertEqual(len(f["native_tools"]), 20)
        self.assertEqual(f["config"]["token_observation_threshold"], 120000)
        self.assertEqual(f["config"]["effort"], "low")
        self.assertIn("only when the advertised schema is insufficient", pilot.OVERRIDE)
        self.assertNotIn("vectors", f["schedule"][0]["prompt"])

    def test_observation_cutoff_and_unknown_completion(self):
        entry = {"id": "synthetic", "condition": "C1"}
        begin = {"method": "item/started", "params": {"item": {
            "type": "mcpToolCall", "id": "x", "tool": "change_field", "arguments": {}}}}
        end = {"method": "item/completed", "params": {"item": {
            "type": "mcpToolCall", "id": "x", "tool": "change_field", "status": "completed", "result": {}}}}
        obs = {"call_id": "x", "after_operation": "change_field", "baseline": False,
               "body_sha256": "new", "baseline_body_sha256": "old",
               "changed_from_transaction_start": True, "observer_calls": 1}
        row = {"events": [begin, end], "first_interrupt_event_boundary": 2}
        result = pilot.summarize(entry, row, {}, [obs])
        self.assertTrue(result["staged_target_changed_before_interrupt"])
        for boundary in (0, 1):
            row["first_interrupt_event_boundary"] = boundary
            self.assertFalse(pilot.summarize(entry, row, {}, [obs])["staged_target_changed_before_interrupt"])
        row = {"events": [begin]}
        self.assertFalse(pilot.summarize(entry, row, {}, [obs])["staged_target_changed_before_interrupt"])

    def test_inherited_interrupt_identity_and_rpc_errors(self):
        self.assertEqual(pilot.old.simulated_validation()["status"], "PASS")

    def test_freeze_runtime_if_present(self):
        path = pilot.HERE / "FREEZE.json"
        if not path.exists():
            self.skipTest("pre-prepare source tests")
        frozen = json.loads(path.read_text())
        for name, digest in frozen["files"].items():
            self.assertEqual(pilot.sha((pilot.ROOT / name).read_bytes()), digest, name)
        c1, c0 = frozen["schedule"]
        self.assertEqual(c1["developer_instructions"], c0["developer_instructions"] + "\n\n" + pilot.OVERRIDE)


if __name__ == "__main__":
    unittest.main()
