"""Portable policy/loopback protocol tests; no model or candidate execution."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tomllib
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.codex.native_commit_authorization import scoped_server, server_override, host_options


class PolicyTests(unittest.TestCase):
    def server(self):
        return scoped_server("trusted-launcher", ["--stdio", 'quoted " argument'],
                             enabled_tools=["begin_transaction", "commit_transaction", "abort_transaction"])

    def test_exact_per_tool_grant(self):
        s = self.server()
        parsed = tomllib.loads(server_override(s))
        self.assertEqual(set(parsed["mcp_servers"]), {"alva"})
        p = parsed["mcp_servers"]["alva"]
        self.assertEqual(p, s)
        self.assertEqual(p["tools"], {"commit_transaction": {"approval_mode": "approve"}})
        self.assertEqual(p["default_tools_approval_mode"], "auto")

    def test_no_mutation_and_no_unsafe_host_expansion(self):
        s = self.server()
        old = copy.deepcopy(s)
        options = host_options(s)
        self.assertEqual(s, old)
        self.assertEqual(options[0], "--strict-config")
        values = tomllib.loads("\n".join(options[i + 1] for i, value in enumerate(options) if value == "-c"))
        self.assertEqual(values["approval_policy"], "never")
        self.assertEqual(values["sandbox_mode"], "read-only")
        self.assertEqual(values["web_search"], "disabled")
        self.assertFalse(values["features"]["shell_tool"])
        self.assertFalse(values["features"]["view_image"])
        self.assertFalse(values["features"]["apps"])
        self.assertFalse(values["features"]["plugins"])
        self.assertNotIn("--yolo", options)

    def test_widening_rejected(self):
        for key, value in (("default_tools_approval_mode", "approve"), ("tools", {"change_field": {"approval_mode": "approve"}}),
                           ("url", "http://untrusted"), ("enabled_tools", [])):
            with self.subTest(key=key):
                s = self.server(); s[key] = value
                with self.assertRaises(ValueError): host_options(s)

    def test_bad_allowlists_rejected(self):
        for values in ([], ["begin_transaction"], ["commit_transaction", "commit_transaction"], ["commit_transaction", "a.b"], [3]):
            with self.assertRaises(ValueError): scoped_server("launcher", [], enabled_tools=values)

    def test_loopback_returns_scripted_tools_only(self):
        spec = importlib.util.spec_from_file_location("local_fixture", Path(__file__).with_name("p31_synthetic_provider.py"))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        p = module.SyntheticProvider()
        try:
            p.schedule("mcp__alva__commit_transaction", {"transaction_id": "tx-fixture"})
            r = urllib.request.Request(p.url + "/responses", data=b'{"input":[]}', headers={"Content-Type": "application/json"})
            events = [json.loads(s[6:]) for s in urllib.request.urlopen(r).read().decode().splitlines() if s.startswith("data: ")]
            calls = [e["item"] for e in events if e["type"] == "response.output_item.done"]
            self.assertEqual(calls[0]["type"], "custom_tool_call")
            self.assertEqual(calls[0]["namespace"], "functions")
            self.assertIn("tools.mcp__alva__commit_transaction", calls[0]["input"])
            self.assertIn("tx-fixture", calls[0]["input"])
            self.assertEqual(len(p.requests), 1)
            self.assertFalse(p.errors)
        finally:
            p.close()


if __name__ == "__main__":
    unittest.main()
