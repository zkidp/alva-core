"""Scope mediator units. Real native/AppServer evidence is separate."""
import copy
import threading
import unittest
from integrations.codex.precommit_scope_guard import GuardedNative, Unverified


def fixture():
    def node(rev, kind, name, slots):
        return {"revision": rev, "kind": kind, "entity": name, "fields": {"name": name}, "slots": slots}
    graph = {"m": node("m", "module", "m", {"functions": ["a", "b"], "types": [], "tests": [], "externs": [], "benches": []})}
    for name in ("a", "b"):
        graph[name] = node(name, "function", name, {"body": [name + "0"], "params": [], "returns": [], "pre": [], "post": [], "inv": []})
        graph[name + "0"] = node(name + "0", "literal", "", {})
        graph[name + "1"] = node(name + "1", "literal", "", {})
    policy = {"authorized_functions": ["m.a"], "modules": {"m": {"functions": ["a", "b"], "types": []}}}
    class Inner:
        def __init__(self):
            self.graph = graph
            self.calls = []
            self.inspect_failure = False
        def request(self, method, params, **kwargs):
            name, args = params.get("name"), params.get("arguments", {})
            self.calls.append(name or method)
            if name == "begin_transaction":
                value = {"transaction_id": "tx"}
            elif name == "inspect_project":
                value = {"modules": {"module:m": "m"}, "project_revision": "project"}
            elif name == "inspect_entity":
                if self.inspect_failure:
                    return {"isError": True}
                value = copy.deepcopy(self.graph[args["entity"]])
            else:
                value = {"ok": True}
            return {"isError": False, "structuredContent": value}
        def notify(self, *args, **kwargs):
            self.calls.append("notify")
    inner = Inner()
    return inner, policy


class Tests(unittest.TestCase):
    def new(self):
        inner, policy = fixture()
        guard = GuardedNative(inner, policy, {"begin_transaction", "commit_transaction", "change_field", "abort_transaction"})
        guard.tool("begin_transaction", {"project": "fixed"})
        return inner, policy, guard

    def decision(self, guard):
        result = guard.tool("commit_transaction", {"transaction_id": "tx"})
        return result["structuredContent"]["host_scope"]

    def test_allowed_body_and_frozen_policy(self):
        inner, policy, guard = self.new()
        policy["authorized_functions"].append("m.b")
        inner.graph["a"]["slots"]["body"] = ["a1"]
        self.assertEqual(self.decision(guard)["status"], "SCOPE_ALLOWED")
        self.assertEqual(inner.calls.count("commit_transaction"), 1)
        self.assertEqual(guard._authorized, frozenset({"m.a"}))

    def test_spill_denied_before_forward(self):
        inner, _, guard = self.new()
        for n in ("a", "b"):
            inner.graph[n]["slots"]["body"] = [n + "1"]
        decision = self.decision(guard)
        self.assertEqual(decision["status"], "SCOPE_VIOLATION")
        self.assertEqual(decision["unauthorized_functions"], ["m.b"])
        self.assertNotIn("commit_transaction", inner.calls)

    def test_unverified_changes_never_forward(self):
        def change_metadata(g): g["a"]["fields"]["pure"] = False
        def change_return(g): g["a"]["slots"]["returns"] = ["a0"]
        def change_exports(g): g["m"]["fields"]["exports"] = ["b"]
        def remove_declaration(g): g["m"]["slots"]["functions"] = ["a"]
        def add_declaration(g): g["m"]["slots"]["functions"].append("a")
        def unsupported_slot(g): g["m"]["slots"]["new_kind"] = []
        def unsupported_extern(g): g["m"]["slots"]["externs"] = ["a0"]
        for mutation in (change_metadata, change_return, change_exports, remove_declaration, add_declaration, unsupported_slot, unsupported_extern):
            with self.subTest(mutation=mutation.__name__):
                inner, _, guard = self.new()
                mutation(inner.graph)
                self.assertEqual(self.decision(guard)["status"], "SCOPE_UNVERIFIED")
                self.assertNotIn("commit_transaction", inner.calls)

    def test_missing_baseline_and_inspection_failure(self):
        inner, policy = fixture()
        guard = GuardedNative(inner, policy, {"begin_transaction", "commit_transaction"})
        self.assertEqual(self.decision(guard)["status"], "SCOPE_UNVERIFIED")
        inner.inspect_failure = True
        guard.tool("begin_transaction", {})
        inner.inspect_failure = False
        self.assertEqual(self.decision(guard)["status"], "SCOPE_UNVERIFIED")
        self.assertNotIn("commit_transaction", inner.calls)
        inner, _, guard = self.new()
        inner.inspect_failure = True
        self.assertEqual(self.decision(guard)["status"], "SCOPE_UNVERIFIED")

    def test_no_alias_policy_argument_or_notification_bypass(self):
        inner, _, guard = self.new()
        result = guard.tool("commit_transaction", {"transaction_id": "tx", "authorized_functions": ["m.b"]})
        self.assertTrue(result["isError"])
        self.assertTrue(guard.tool("commit", {"transaction_id": "tx"})["isError"])
        with self.assertRaises(Unverified):
            guard.notify("tools/call", {"name": "commit_transaction", "arguments": {"transaction_id": "tx"}})
        with self.assertRaises(Unverified):
            guard.request("commit_transaction", {"transaction_id": "tx"})
        self.assertNotIn("commit_transaction", inner.calls)

    def test_core_rejection_is_not_a_scope_rejection(self):
        inner, _, guard = self.new()
        original = inner.request
        def reject(method, params, **kwargs):
            if params.get("name") == "commit_transaction":
                inner.calls.append("commit_transaction")
                return {"isError": True, "structuredContent": {"diagnostic": "ordinary Core check failure"}}
            return original(method, params, **kwargs)
        inner.request = reject
        result = guard.tool("commit_transaction", {"transaction_id": "tx"})
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["host_scope"]["status"], "SCOPE_ALLOWED")
        self.assertEqual(result["structuredContent"]["diagnostic"], "ordinary Core check failure")
        self.assertIn("tx", guard._baselines)

    def test_snapshot_through_forward_is_serialized(self):
        inner, _, guard = self.new()
        original = guard._snapshot
        entered, release = threading.Event(), threading.Event()
        def snapshot(tx):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test timeout")
            return original(tx)
        guard._snapshot = snapshot
        first = threading.Thread(target=lambda: self.decision(guard))
        second = threading.Thread(target=lambda: guard.tool("change_field", {"transaction_id": "tx"}))
        first.start()
        self.assertTrue(entered.wait(1))
        second.start()
        self.assertNotIn("change_field", inner.calls)
        release.set()
        first.join(4); second.join(4)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertLess(inner.calls.index("commit_transaction"), inner.calls.index("change_field"))


if __name__ == "__main__":
    unittest.main()
