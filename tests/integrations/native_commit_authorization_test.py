"""P31 real AppServer / synthetic-tool-turn / Linux Native MCP test.

All Responses events come from loopback scripted fixtures, not any model.
Uses the unchanged P26 service and P23 Linux OS isolation. Never reads auth.
"""
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.codex.native_commit_authorization import scoped_server, server_override, toml_value, host_options
from integrations.benchmark_runtime_v2.freeze import canonical, sha
from benchmarks.native_prospective import pilot as old

spec = importlib.util.spec_from_file_location("p31_synthetic", Path(__file__).with_name("p31_synthetic_provider.py"))
synthetic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(synthetic)

ALLOWED = ["begin_transaction", "resolve_entity", "inspect_body", "inspect_entity", "change_field",
           "preview_semantic_diff", "check_transaction", "commit_transaction", "abort_transaction",
           "create_literal", "create_binary", "replace_expression"]


def fixture():
    files = {"alva.toml": b'[project]\nname="bench"\n[modules]\n"bench"="src/probe.alva"\n',
             "src/probe.alva": b'(module (name "bench") (version "0.1.0") (export solve)\n'
                 b' (fn solve (params (param x (prim string))) (returns (prim string)) (pure)\n'
                 b'  (body (string "before"))))\n'}
    payload = {"schema": "alva-benchmark-freeze/v2", "byte_policy": "exact-git-blob-no-normalization", "entries": [
        {"path": p, "length": len(v), "sha256": sha(v), "base64": base64.b64encode(v).decode(),
         "origin": {"kind": "public-p31-standalone-fixture"}} for p, v in sorted(files.items())]}
    return {"payload": payload, "payload_sha256": sha(canonical(payload))}


class Probe:
    def __init__(self, args, path, authorized=True):
        self.args, self.path = args, path
        self.provider = synthetic.SyntheticProvider()
        self.events = []
        self.slot = old.Slot(path, {"id": "isolated-service", "task": "P31", "arm": "N"},
            {"tasks": {"P31": {"bundle": fixture(), "vectors": [["x", "after"], ["y", "after"]]}}, "docs": {}}, args)
        self.home = tempfile.TemporaryDirectory(prefix="p31-empty-codex-home-")
        cwd = path / "host"
        cwd.mkdir()
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA") if k in os.environ}
        env["CODEX_HOME"] = self.home.name
        server = scoped_server("wsl.exe", ["-d", "Ubuntu-26.04", "--exec", "python3", old.linux(self.slot.service),
                                "--config", old.linux(self.slot.ready)], enabled_tools=ALLOWED)
        opts = host_options(server)
        if not authorized:
            server["tools"] = {}  # negative fixture only: reproduce default-auto destructive denial
            opts[-1] = server_override(server)
        self.server_config = server
        provider = {"p31_synthetic": {"name": "P31 deterministic loopback, no model", "base_url": self.provider.url,
            "wire_api": "responses", "requires_openai_auth": False, "request_max_retries": 0, "stream_max_retries": 0,
            "supports_websockets": False}}
        overrides = {"model_provider": "p31_synthetic", "model_providers": provider}
        for k, v in overrides.items(): opts += ["-c", k + "=" + toml_value(v)]
        self.host = old.transport.AppServer(shutil.which("codex"), env, cwd, extra_args=opts)
        self.c = old.Controller(self.host)
        self.c.rpc("initialize", {"clientInfo": {"name": "p31-zero-model", "version": "1"}, "capabilities": {"experimentalApi": True}})
        self.host.send({"method": "initialized", "params": {}})
        self.config_read = self.c.rpc("config/read", {"includeLayers": False})
        self.thread = self.c.rpc("thread/start", {"cwd": str(cwd), "ephemeral": True, "approvalPolicy": "never",
            "sandbox": "read-only", "model": "gpt-5.6-sol", "modelProvider": "p31_synthetic",
            "developerInstructions": "Deterministic local integration fixture. No host execution, shell, web, files or delegation."})
        self.inventory = self.c.rpc("mcpServerStatus/list", {"threadId": self.thread["thread"]["id"]}, timeout=120)
        self.completed = []

    def script(self, code):
        self.action("script", code, expect_native=False)
        outputs = [i for i in self.provider.requests[-1]["input"] if i.get("type") == "custom_tool_call_output"]
        return outputs[-1]["output"]

    def action(self, name, args, *, expect_native=True):
        self.provider.schedule("mcp__alva__" + name if expect_native else "__script__", args)
        turn = self.c.rpc("turn/start", {"threadId": self.thread["thread"]["id"],
            "input": [{"type": "text", "text": "Execute the next deterministic local fixture step."}],
            "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly"}})
        self.c.bind(self.thread, turn)
        deadline = time.monotonic() + 40
        calls = []
        while time.monotonic() < deadline:
            try: e = self.c.next(.5)
            except queue.Empty: continue
            if e is None: raise RuntimeError("APPSERVER_EXIT:" + str(self.host.errors[-8:]))
            self.events.append(e)
            if e.get("method") == "item/completed" and e.get("params", {}).get("item", {}).get("type") == "mcpToolCall":
                calls.append(e["params"]["item"])
            if "id" in e and "method" in e:
                raise RuntimeError("UNEXPECTED_APPROVAL_OR_HOST_REQUEST:" + e["method"])
            terminal = self.c.observe(e)
            if terminal:
                assert terminal == "completed", (terminal, self.host.errors[-5:])
                assert len(calls) == (1 if expect_native else 0), (calls, self.provider.errors, self.host.errors[-10:])
                if expect_native: assert calls[0]["tool"] == name
                self.completed += calls
                return calls[0] if calls else None
        raise RuntimeError("SYNTHETIC_TURN_TIMEOUT:" + str(self.host.errors[-8:]))

    def direct(self, name, args):
        return self.c.rpc("mcpServer/tool/call", {"threadId": self.thread["thread"]["id"], "server": "alva", "tool": name, "arguments": args})

    def snapshot(self):
        return self.slot.dispatch("snapshot", {})["files"]

    def close(self):
        self.host.close()
        self.slot.close()
        self.provider.close()
        self.home.cleanup()
        old.save(self.path / "synthetic-events.json", self.events)
        old.save(self.path / "synthetic-requests.json", self.provider.requests)
        old.save(self.path / "parsed-config.json", self.config_read)
        return json.loads(self.slot.evidence.read_text())


def content(item):
    assert not item.get("error"), item
    result = item["result"]
    assert not result.get("isError"), result
    value = result["structuredContent"]
    assert not value.get("error"), value
    return value


def failed(item):
    return bool(item.get("error") or item.get("result", {}).get("isError") or
                item.get("result", {}).get("structuredContent", {}).get("error"))


def main(args):
    path = ROOT / ".local/p31-commit-authorization" / args.attempt
    path.mkdir(parents=True, exist_ok=False)
    p = Probe(args, path / "authorized")
    summary = {"status": "FAIL", "model_generation_calls": 0, "input_token_calls": 0,
               "fixture": "standalone string-return policy probe; not MM01 or a past model candidate", "rows": []}
    try:
        assert p.thread["modelProvider"] == "p31_synthetic"
        tools = next(s["tools"] for s in p.inventory["data"] if s["name"] == "alva")
        assert set(tools) == set(ALLOWED)
        assert tools["commit_transaction"]["annotations"]["destructiveHint"] is True
        parsed = p.config_read["config"]
        assert parsed["mcp_servers"]["alva"]["tools"]["commit_transaction"]["approval_mode"] == "approve"
        assert parsed["approval_policy"] == "never"
        assert p.thread["approvalPolicy"] == "never"
        assert p.thread["sandbox"]["type"] == "readOnly"
        summary["parsed_policy"] = {"approval_policy": "never", "sandbox": "readOnly",
            "server": "alva", "enabled_tools": ALLOWED, "commit_transaction": "approve", "default": "auto",
            "strict_config": True, "destructiveHint": True}
        b = content(p.action("begin_transaction", {"project": "/work/project/alva.toml"}))
        tx = b["transaction_id"]
        body = content(p.action("inspect_body", {"transaction_id": tx, "function": "bench.solve"}))["body"]
        literal = re.search(r"literal value=before rev=([0-9a-f]{64})", body)
        assert literal, body
        original = p.snapshot()
        content(p.action("change_field", {"transaction_id": tx, "entity": literal.group(1), "field": "value", "value": "after"}))
        assert p.snapshot() == original
        assert content(p.action("preview_semantic_diff", {"transaction_id": tx}))["diff"]
        assert content(p.action("check_transaction", {"transaction_id": tx}))["problems"] == []
        content(p.action("commit_transaction", {"transaction_id": tx}))
        committed = p.snapshot()
        assert "alva-air/current" in committed
        summary["rows"].append({"test": "real_model_tool_path_commit", "status": "PASS"})
        for label, bad in (("wrong_transaction_id", "tx-nonexistent"), ("closed_transaction_id", tx)):
            assert failed(p.action("commit_transaction", {"transaction_id": bad}))
            assert p.snapshot() == committed
            summary["rows"].append({"test": label, "status": "PASS", "authority_unchanged": True})
        tx = content(p.action("begin_transaction", {"project": "/work/project/alva.toml"}))["transaction_id"]
        body = content(p.action("inspect_body", {"transaction_id": tx, "function": "bench.solve"}))["body"]
        literal = re.search(r"literal value=after rev=([0-9a-f]{64})", body).group(1)
        block = re.search(r"block rev=([0-9a-f]{64})", body).group(1)
        integer = content(p.action("create_literal", {"transaction_id": tx, "type": "i64", "value": "1"}))["revision"]
        bad_expr = content(p.action("create_binary", {"transaction_id": tx, "op": "+", "left": literal, "right": integer}))["revision"]
        content(p.action("replace_expression", {"transaction_id": tx, "parent": block, "child": bad_expr, "position": "step"}))
        assert failed(p.action("check_transaction", {"transaction_id": tx}))
        assert p.snapshot() == committed
        assert failed(p.action("commit_transaction", {"transaction_id": tx}))
        assert p.snapshot() == committed
        content(p.action("abort_transaction", {"transaction_id": tx}))
        summary["rows"].append({"test": "invalid_transaction_no_publication", "status": "PASS", "authority_unchanged": True})
        outputs = p.script("text(ALL_TOOLS.map(t=>t.name));")
        names = next(json.loads(o["text"]) for o in outputs if o.get("text", "").startswith("["))
        assert not any(n in names for n in ("exec_command", "write_stdin", "view_image", "web_search", "mcp__alva__describe_operation"))
        result = p.script('try { await tools.mcp__alva__describe_operation({name:"commit_transaction"}); text("UNEXPECTED"); } catch(e) { text("UNAUTHORIZED_TOOL_NOT_AVAILABLE"); }')
        assert "UNAUTHORIZED_TOOL_NOT_AVAILABLE" in json.dumps(result)
        assert p.snapshot() == committed
        sentinel = p.path / "host/forbidden-host-write.txt"
        patch_text = "*** Begin Patch\n*** Add File: " + sentinel.as_posix() + "\n+must-not-write\n*** End Patch"
        p.script("text(await tools.apply_patch(" + json.dumps(patch_text) + "));")
        assert not sentinel.exists(), "Read-only Host allowed a file write"
        summary["rows"].append({"test": "unauthorized_mcp_and_host_tools_unavailable", "status": "PASS", "available_tools": names})
        summary["rows"].append({"test": "readonly_host_patch_denied", "status": "PASS", "host_write_occurred": False})
        print("MODEL_TOOL_APPROVAL_PATH_COMMIT_PASS; no model generation", flush=True)
    finally:
        evidence = p.close()
    assert evidence["final"]["status"] == "PASS", evidence["final"]
    assert evidence["initial_authority"]["body_sha256"] != evidence["final_authority"]["body_sha256"]
    commits = [c for c in evidence["calls"] if c.get("request", {}).get("params", {}).get("name") == "commit_transaction"]
    assert len(commits) == 4 and sum(not c["response"].get("isError") for c in commits) == 1
    assert {c["request"]["params"]["_meta"]["callId"] for c in commits} == {
        c["id"] for c in p.completed if c["tool"] == "commit_transaction"}
    assert all(c.get("request", {}).get("params", {}).get("name") != "describe_operation" for c in evidence["calls"])
    summary["rows"].append({"test": "fresh_process_air_build_behavior", "status": "PASS", "commit_dispatches": 4,
        "successful_commits": 1, "appserver_call_ids_match_native_dispatch": True})
    p = Probe(args, path / "unapproved-default", authorized=False)
    try:
        tx = content(p.action("begin_transaction", {"project": "/work/project/alva.toml"}))["transaction_id"]
        before = p.snapshot()
        denied = p.action("commit_transaction", {"transaction_id": tx})
        assert denied["error"]["message"] == "MCP tool call requires approval, but approval policy is never"
        assert p.snapshot() == before
        direct = p.direct("commit_transaction", {"transaction_id": tx})
        assert not direct.get("isError"), direct
        assert "alva-air/current" in p.snapshot()
    finally:
        negative = p.close()
    commits = [c for c in negative["calls"] if c.get("request", {}).get("params", {}).get("name") == "commit_transaction"]
    assert len(commits) == 1  # direct RPC only: denied model-tool call never dispatched
    assert negative["final"]["status"] == "TEST_FAIL"  # unchanged 'before', not the positive fixture's 'after'
    summary["rows"].append({"test": "default_destructive_model_denied_but_direct_rpc_passes", "status": "PASS",
        "model_denial_reached_mcp": False, "direct_rpc_commit_dispatched": True})
    summary["codex"] = subprocess.check_output([shutil.which("codex"), "--version"], text=True).strip()
    summary["codex_binary_sha256"] = sha(Path(shutil.which("codex")).read_bytes())
    summary["status"] = "PASS"
    summary["model_approval_path"] = "VERIFIED_WITH_LOCAL_SYNTHETIC_RESPONSES_NO_MODEL"
    old.save(path / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    print("FRESH_AIR_BUILD_BEHAVIOR_PASS", flush=True)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--attempt", required=True)
    for key in ("alva", "toolchain", "registry"): a.add_argument("--" + key, required=True)
    main(a.parse_args())
