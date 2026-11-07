#!/usr/bin/env python3
"""Real STDIO/profile/Guard/authority tests. No model or provider calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.codex.precommit_scope_guard import GuardedNative

TOOLS = (
    "begin_transaction", "inspect_project", "read_function", "inspect_entity",
    "replace_function_body", "preview_semantic_diff", "check_transaction",
    "commit_transaction", "abort_transaction",
)


class Native:
    def __init__(self, binary, profile="maintenance"):
        self.p = subprocess.Popen([str(binary), "mcp", "--profile", profile],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.seq = 0

    def request(self, method, params=None):
        self.seq += 1
        self.p.stdin.write(json.dumps(dict(jsonrpc="2.0", id=self.seq,
                                           method=method, params=params or {})) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        assert line, self.p.stderr.read()
        reply = json.loads(line)
        assert reply["id"] == self.seq and "error" not in reply, reply
        return reply["result"]

    def close(self):
        self.p.stdin.close()
        trailing = self.p.stdout.read()
        errors = self.p.stderr.read()
        assert self.p.wait(timeout=10) == 0, errors
        assert not trailing, trailing
        self.p.stdout.close()
        self.p.stderr.close()


class Client:
    def __init__(self, native, project):
        self.native = native
        self.tx = None
        self.tx = self.call("begin_transaction", project=str(project))["transaction_id"]

    def raw(self, name, **args):
        if self.tx:
            args["transaction_id"] = self.tx
        return self.native.request("tools/call", {"name": name, "arguments": args})

    def call(self, name, **args):
        reply = self.raw(name, **args)
        assert not reply.get("isError"), (name, reply)
        # P34 adds a host-owned scope record to structuredContent, keeping
        # Native's original textual receipt intact.
        native_content = {k: v for k, v in reply["structuredContent"].items() if k != "host_scope"}
        assert json.loads(reply["content"][0]["text"]) == native_content
        return reply["structuredContent"]

    def function(self, name):
        return self.call("read_function", function=name)

    def replace(self, name, body, revision=None):
        return self.raw("replace_function_body", function=name,
                        expected_body_revision=revision or self.function(name)["body_revision"], body=body)


def fixture(binary, allowed="left"):
    target = allowed + ".f"
    other = ("right" if allowed == "left" else "left") + ".f"
    with tempfile.TemporaryDirectory(prefix="alva-body-edit-") as temp:
        project = Path(temp)
        manifest = project / "alva.toml"
        manifest.write_text('[project]\nname="body_edit"\n[modules]\nleft="left.alva"\nright="right.alva"\n')
        for name in ("left", "right"):
            (project / (name + ".alva")).write_text(
                f'(module (name "{name}") (version "1") (export f) '
                '(fn f (params) (returns (prim i64)) (pure) (body (int 1))))\n')
        sources = {p.name: p.read_bytes() for p in project.iterdir()}
        policy = {"schema": "fixed-component-body-scope/v1", "authorized_functions": [target],
                  "modules": {m: {"functions": ["f"], "types": []} for m in ("left", "right")}}
        wire = Native(binary)
        assert tuple(t["name"] for t in wire.request("tools/list")["tools"]) == TOOLS
        ledger = []
        guarded = GuardedNative(wire, policy, TOOLS, ledger.append)
        c = Client(guarded, manifest)
        initial = {m: c.function(m + ".f") for m in ("left", "right")}
        assert initial["left"]["revision"] == initial["right"]["revision"], "entire function must share"
        # A declaration operation still needs Host authorization.
        assert not c.replace(other, "(body (int 9))")["isError"]
        denied = c.raw("commit_transaction")
        assert denied["isError"] and denied["host_scope"]["status"] == "SCOPE_VIOLATION", (denied,
            [e for e in ledger if e.get("response", {}).get("isError")])
        assert not (project / "alva-air").exists()
        c.call("abort_transaction")
        c = Client(guarded, manifest)
        old = c.function(target)
        assert not c.replace(target, old["body"], old["body_revision"])["isError"], "projection must round trip"
        assert c.function(target)["revision"] == old["revision"]
        for text in ['(fn f)', '(body (+ (string "x") (int 1)))', '(body (ref missing))',
                     '(body (string "wrong return"))', '(body)']:
            assert c.replace(target, text)["isError"]
            assert c.function(target) == old, "failed edits must be atomic"
        assert not c.replace(target, "(body (int 2))", old["body_revision"])["isError"]
        staged = c.function(target)
        exact = c.call("inspect_entity", entity=old["revision"])
        assert exact["revision"] == old["revision"], "exact revision reads cannot remap to a new declaration head"
        assert c.function(other) == initial[other.split(".")[0]]
        stale = c.replace(target, "(body (int 3))", old["body_revision"])
        assert stale["isError"] and "STALE_BODY_REVISION" in json.dumps(stale)
        assert c.function(target) == staged
        assert c.call("preview_semantic_diff")["diff"].strip()
        assert c.call("check_transaction") == {"problems": []}
        assert not (project / "alva-air").exists(), "staging cannot publish"
        committed = c.call("commit_transaction")
        assert committed["host_scope"]["status"] == "SCOPE_ALLOWED", committed
        assert committed["host_scope"]["changed_functions"] == [target]
        wire.close()
        commits = [e for e in ledger if e["event"] == "native_dispatch"
                   and e.get("params", {}).get("name") == "commit_transaction"]
        assert len(commits) == 1, "denied commit must not reach Native"
        assert (project / "alva-air/current").exists()
        for name, content in sources.items():
            assert (project / name).read_bytes() == content
        fresh = Native(binary)
        r = Client(fresh, manifest)
        assert r.function(target) == staged
        assert r.function(other) == initial[other.split(".")[0]]
        r.call("abort_transaction")
        fresh.close()
        # Body preconditions are transaction-local. A competing publish must
        # still be rejected by the existing authoritative base check.
        wires = [Native(binary), Native(binary)]
        try:
            clients = [Client(GuardedNative(w, policy, TOOLS), manifest) for w in wires]
            for client, value in zip(clients, (3, 4)):
                assert not client.replace(target, f"(body (int {value}))")["isError"]
            clients[0].call("commit_transaction")
            authority = {p.relative_to(project).as_posix(): p.read_bytes()
                         for p in (project / "alva-air").rglob("*") if p.is_file()}
            refused = clients[1].raw("commit_transaction")
            assert refused["isError"] and "base" in json.dumps(refused).lower(), refused
            assert authority == {p.relative_to(project).as_posix(): p.read_bytes()
                                 for p in (project / "alva-air").rglob("*") if p.is_file()}
            clients[1].call("abort_transaction")
        finally:
            for w in wires:
                w.close()
        subprocess.run([str(binary), "project", "build", str(manifest)], check=True, capture_output=True)
        # Explicit native profile stays exactly the historical 20 tools.
        native = Native(binary, "native")
        names = {t["name"] for t in native.request("tools/list")["tools"]}
        assert len(names) == 20 and "replace_function_body" not in names
        assert Client(native, manifest).raw("replace_function_body")["isError"]
        native.close()
    invalid = subprocess.run([str(binary), "mcp", "--profile", "unknown"], capture_output=True)
    assert invalid.returncode == 2
    print("PASS: maintenance profile, shared declaration, atomic errors, P34 allow/deny, Native commit, fresh AIR, build")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("binary", type=Path)
    binary = p.parse_args().binary.resolve()
    fixture(binary, "left")
    fixture(binary, "right")
