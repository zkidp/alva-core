"""Prospective binding/policy/result tests, no model requests."""
import base64
import json
from pathlib import Path
import types
import unittest
from benchmarks.p32_native_mm01 import pilot as p


class Tests(unittest.TestCase):
    def test_scoped_host_and_transport(self):
        f = json.loads(p.P30.read_text())
        slot = types.SimpleNamespace(service=p.mm.HERE / "service.py", ready=p.ROOT / ".local/p32-test/ready.json", frozen=f)
        server = p.authorization(slot)
        self.assertEqual(set(server["enabled_tools"]), set(f["native_tools"]))
        self.assertEqual(len(server["enabled_tools"]), 20)
        self.assertEqual(server["tools"], {"commit_transaction": {"approval_mode": "approve"}})
        options = p.host_options(server)
        self.assertIn('--strict-config', options)
        self.assertIn('approval_policy="never"', options)
        self.assertIn('sandbox_mode="read-only"', options)
        self.assertEqual(p.tomllib.loads(options[-1])["mcp_servers"], {"alva": server})

    def test_unchanged_controller(self):
        self.assertEqual(p.old.simulated_validation()["status"], "PASS")
        self.assertEqual(p.CONFIG["token_observation_threshold"], 600000)
        self.assertFalse(p.CONFIG["hard_provider_token_cap"])

    def test_frozen_input(self):
        path = p.HERE / "FREEZE.json"
        if not path.exists():
            self.skipTest("prepare has not run")
        f = json.loads(path.read_text())
        old = json.loads(p.P30.read_text())
        self.assertEqual(f["base"], p.BASE)
        self.assertEqual(f["parent_input_freeze_sha256"], p.sha(p.P30.read_bytes()))
        self.assertEqual(f["config"], p.CONFIG)
        for key in ("task", "assertions", "docs", "docs_bundle", "language", "public_task_input", "developer_instructions", "native_tools", "tools", "sdk_identity", "codex", "codex_binary_sha256"):
            self.assertEqual(f[key], old[key], key)
        self.assertEqual(len(f["schedule"]), 1)
        self.assertEqual(f["schedule"][0], dict(old["schedule"][1], id="P32-MM01-S"))
        self.assertEqual(f["validation"]["status"], "PASS")
        self.assertEqual(f["validation"]["generation_calls"], 0)
        for name, digest in f["files"].items():
            self.assertEqual(p.sha(base64.b64decode(f["runtime_bytes"][name], validate=True)), digest)
            self.assertEqual(p.sha((p.ROOT / name).read_bytes()), digest, name)

    def test_commit_path_error_not_hidden_by_native_counts(self):
        record = {"events": [{"method": "item/completed", "params": {"item": {
            "type": "mcpToolCall", "id": "blocked", "tool": "commit_transaction", "error": {"message": "denied"}}}}]}
        r = p.summarize({"id": "synthetic", "condition": "S", "arm": "N"}, record, {}, [])
        self.assertEqual(r["appserver_commit_attempts"], 1)
        self.assertFalse(r["commit_reached_native_mcp"])
        self.assertTrue(r["appserver_commit_errors"])
        self.assertFalse(r["historical_T_pooling"])
        self.assertEqual(r["task_correctness"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
