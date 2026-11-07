"""Session-local three-action maintenance Host over the real Native AEP.

Only TOOLS is agent-visible. Native transactions, AIR bytes, authorization,
test configuration and evaluation receipts remain in this trusted process.
No model/provider calls are made here.
"""
from __future__ import annotations

import copy
import hashlib
import json
import queue
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path, PurePosixPath

from integrations.codex.precommit_scope_guard import GuardedNative

PRIVATE_OPERATIONS = frozenset(("begin_transaction", "read_function", "read_function_context",
    "replace_function_body", "inspect_project", "inspect_entity", "preview_semantic_diff",
    "check_transaction", "export_transaction", "commit_transaction", "abort_transaction"))

TOOLS = [
    {"name": "read_target", "description": "Read an authorized function's current body, declaration and direct context. Reuse its view_id for changes; Host owns transactions.",
     "inputSchema": {"type": "object", "properties": {"function": {"type": "string", "minLength": 1}}, "required": ["function"], "additionalProperties": False}},
    {"name": "prepare_change", "description": "Prepare an ALVA (body ...) fragment using view_id. Host checks scope and tests the isolated draft. Does not publish. On rejection revise using the same view_id.",
     "inputSchema": {"type": "object", "properties": {"view_id": {"type": "string", "minLength": 1}, "body": {"type": "string", "minLength": 1, "maxLength": 65536}}, "required": ["view_id", "body"], "additionalProperties": False}},
    {"name": "publish_change", "description": "Publish one successfully prepared proposal_id. Host rechecks the exact draft, test identity, source base and authorization, then verifies fresh AIR. A proposal is single-use.",
     "inputSchema": {"type": "object", "properties": {"proposal_id": {"type": "string", "minLength": 1}}, "required": ["proposal_id"], "additionalProperties": False}},
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def snapshot_digest(files):
    return sha(canonical({path: sha(data) for path, data in files.items()}))


class ToolFailure(RuntimeError):
    def __init__(self, response):
        self.response = response
        super().__init__(str(response.get("structuredContent", {}).get("error", "NATIVE_OPERATION_REJECTED")))


class AepBridge:
    """Trusted adapter, not an extra model-callable MCP server.

    send executes the real `alva agent` JSON-lines protocol. Transaction IDs
    below bind this adapter's single EditSession; Core still enforces its base.
    """
    def __init__(self, send, close):
        self.send, self._close = send, close
        self.tx = None
        self.seq = 0

    def request(self, method, params=None, **_):
        if method != "tools/call":
            raise RuntimeError("HOST_BRIDGE_METHOD_NOT_SUPPORTED")
        name, args = params["name"], copy.deepcopy(params["arguments"])
        if name not in PRIVATE_OPERATIONS:
            raise RuntimeError("HOST_BRIDGE_OPERATION_NOT_ALLOWED")
        if name == "begin_transaction":
            if self.tx:
                raise RuntimeError("HOST_BRIDGE_TRANSACTION_ACTIVE")
        elif args.pop("transaction_id", None) != self.tx or not self.tx:
            raise RuntimeError("HOST_BRIDGE_TRANSACTION_MISMATCH")
        self.seq += 1
        answer = self.send(dict(args, tool=name, request_id="host-" + str(self.seq)))
        if not isinstance(answer, dict) or answer.get("request_id") != "host-" + str(self.seq):
            raise RuntimeError("HOST_BRIDGE_INVALID_REPLY")
        result = copy.deepcopy(answer.get("result"))
        if answer.get("ok"):
            if name == "begin_transaction":
                self.tx = "tx_" + secrets.token_hex(12)
                result["transaction_id"] = self.tx
            elif name in ("abort_transaction", "commit_transaction"):
                self.tx = None
        else:
            result = {"error": answer.get("message", "NATIVE_OPERATION_REJECTED"), "details": result}
        return {"isError": not bool(answer.get("ok")), "structuredContent": result,
                "content": [{"type": "text", "text": json.dumps(result)}]}

    def close(self):
        self._close()


class AgentProcess(AepBridge):
    """A bounded actual AEP child; process and paths are trusted Host config."""
    def __init__(self, binary):
        self.process = subprocess.Popen([str(binary), "agent"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.lines = queue.Queue()
        self.errors = bytearray()
        def read():
            while line := self.process.stdout.readline(24 * 1024**2 + 1): self.lines.put(line)
            self.lines.put(None)
        def stderr():
            while chunk := self.process.stderr.read(4096):
                if len(self.errors) < 65536: self.errors.extend(chunk)
        self.reader = threading.Thread(target=read, daemon=True)
        self.err_reader = threading.Thread(target=stderr, daemon=True)
        self.reader.start(); self.err_reader.start()
        super().__init__(self._send, self._shutdown)

    def _send(self, request):
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        self.process.stdin.flush()
        try: line = self.lines.get(timeout=60)
        except queue.Empty: raise RuntimeError("HOST_NATIVE_TIMEOUT_OUTCOME_UNKNOWN") from None
        if not line or len(line) > 24 * 1024**2: raise RuntimeError("HOST_NATIVE_INVALID_OR_CLOSED_STREAM")
        return json.loads(line)

    def _shutdown(self):
        if not self.process.stdin.closed: self.process.stdin.close()
        try: self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill(); self.process.wait(timeout=5)
        self.reader.join(timeout=2); self.err_reader.join(timeout=2)
        self.process.stdout.close(); self.process.stderr.close()
        if self.reader.is_alive() or self.err_reader.is_alive(): raise RuntimeError("HOST_NATIVE_CLEANUP_UNCONFIRMED")
        if self.process.returncode: raise RuntimeError("HOST_NATIVE_ABNORMAL_EXIT")


class CountedNative:
    def __init__(self, inner, owner): self.inner, self.owner = inner, owner
    def request(self, method, params=None, **kwargs):
        self.owner.work["native_calls"] += 1
        result = self.inner.request(method, params, **kwargs)
        self.owner.work["native_reply_bytes"] += len(canonical(result))
        return result
    def close(self): return self.inner.close()


class MaintenanceHost:
    def __init__(self, native_factory, project, policy, source_loader, evaluator, *, ttl_seconds=900, clock=time.monotonic):
        if ttl_seconds <= 0: raise ValueError("Positive view TTL required")
        self.factory, self.project = native_factory, str(project)
        self.policy = copy.deepcopy(policy)
        self.sources, self.evaluator = source_loader, evaluator
        self.ttl, self.clock = ttl_seconds, clock
        self.native = self.guard = self.tx = self.view = self.proposal = None
        self.blocked = None
        self.lock = threading.RLock()
        self.work = {"agent_tool_calls": 0, "native_calls": 0, "native_reply_bytes": 0,
                     "guard_reads": 0, "evaluation_runs": 0, "evaluation_seconds": 0.0}

    def _event(self, event):
        if event.get("origin") == "guard_read": self.work["guard_reads"] += 1

    def _new_native(self): return CountedNative(self.factory(), self)

    def _load_sources(self):
        files = self.sources()
        if not isinstance(files, dict) or "alva.toml" not in files: raise RuntimeError("INVALID_SOURCE_SNAPSHOT")
        for name, data in files.items():
            if (not isinstance(name, str) or not isinstance(data, bytes) or "\\" in name or ":" in name
                    or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                    or name.split("/")[0].lower() == "alva-air"):
                raise RuntimeError("INVALID_SOURCE_SNAPSHOT")
        if sum(map(len, files.values())) > 16 * 1024**2: raise RuntimeError("SOURCE_INPUT_LIMIT")
        return dict(files)

    def _call(self, name, **args):
        if name != "begin_transaction": args["transaction_id"] = self.tx
        result = self.guard.tool(name, args)
        if result.get("isError"): raise ToolFailure(result)
        return result["structuredContent"]

    def _reset(self):
        native, guard, tx = self.native, self.guard, self.tx
        self.native = self.guard = self.tx = self.view = self.proposal = None
        try:
            if guard and tx: guard.tool("abort_transaction", {"transaction_id": tx})
        finally:
            if native: native.close()

    def _export(self):
        data = self._call("export_transaction")
        if data.get("format") != "ALVA-AIR-1" or not re.fullmatch(r"[0-9a-f]{64}", data.get("project_revision", "")):
            raise RuntimeError("INVALID_DRAFT_DESCRIPTOR")
        air = bytes.fromhex(data["air_hex"])
        if len(air) > 8 * 1024**2 or sha(air) != data["air_sha256"]:
            raise RuntimeError("DRAFT_BYTES_MISMATCH")
        return data, air

    def invoke(self, name, arguments):
        with self.lock:
            self.work["agent_tool_calls"] += 1
            if self.blocked: return {"status": "BLOCKED", "reason": self.blocked}
            expected = {t["name"]: t["inputSchema"] for t in TOOLS}
            if not isinstance(name, str) or name not in expected: return {"status": "REJECTED", "reason": "TOOL_NOT_EXPOSED"}
            if name == "prepare_change": self.proposal = None
            schema = expected[name]
            if not isinstance(arguments, dict) or set(arguments) != set(schema["required"]) or any(not isinstance(v, str) or not v for v in arguments.values()):
                return {"status": "REJECTED", "reason": "INVALID_ARGUMENTS"}
            if "body" in arguments and len(arguments["body"].encode()) > 65536:
                return {"status": "REJECTED", "reason": "BODY_SOURCE_LIMIT"}
            if self.view and self.clock() > self.view["expires"]:
                self._reset()
                if name != "read_target": return {"status": "REJECTED", "reason": "VIEW_EXPIRED_READ_TARGET"}
            try:
                return copy.deepcopy(getattr(self, "_" + name)(**arguments))
            except ToolFailure as e:
                return {"status": "REJECTED", "reason": str(e)[:2400], "recovery": "Revise the body using the same view_id, or read_target after a conflict."}
            except Exception as e:
                self.blocked = self.blocked or "HOST_FAILURE_RESTART_REQUIRED:" + type(e).__name__
                try: self._reset()
                except Exception: pass
                return {"status": "BLOCKED", "reason": self.blocked}

    def _read_target(self, function):
        if function not in self.policy["authorized_functions"]:
            return {"status": "REJECTED", "reason": "FUNCTION_NOT_AUTHORIZED"}
        if not self.view or self.view["function"] != function:
            self._reset()
            self.native = self._new_native()
            self.guard = GuardedNative(self.native, self.policy, PRIVATE_OPERATIONS, self._event)
            self.tx = self._call("begin_transaction", project=self.project)["transaction_id"]
            self.view = {"id": "view_" + secrets.token_hex(12), "function": function, "expires": self.clock() + self.ttl,
                         "source_digest": snapshot_digest(self._load_sources())}
        info = self._call("read_function", function=function)
        context = self._call("read_function_context", function=function)
        self.view.setdefault("initial_body_revision", info["body_revision"])
        return {"status": "READY", "view_id": self.view["id"], "function": function,
                "declaration": info["declaration"], "body": info["body"], "context": context,
                "view_state": "DRAFT" if info["body_revision"] != self.view["initial_body_revision"] else "BASE_SNAPSHOT",
                "scope": "Only this authorized function body may change.",
                "workflow": "prepare_change tests the isolated draft; publish_change publishes only its passing proposal."}

    def _prepare_change(self, view_id, body):
        self.proposal = None  # A failed new attempt cannot publish an older passing draft.
        if not self.view or self.view["id"] != view_id:
            return {"status": "REJECTED", "reason": "UNKNOWN_VIEW_READ_TARGET"}
        target = self.view["function"]
        before = self._call("read_function", function=target)
        changed = self._call("replace_function_body", function=target, expected_body_revision=before["body_revision"], body=body)
        if changed["body_revision"] == before["body_revision"]:
            return {"status": "UNCHANGED", "can_publish": False}
        self._call("check_transaction")
        scope = self.guard.preview_scope(self.tx)
        if scope["status"] != "SCOPE_ALLOWED": return {"status": scope["status"], "can_publish": False}
        if scope["changed_functions"] != [target]:
            return {"status": "REJECTED", "reason": "NO_SINGLE_TARGET_CHANGE", "can_publish": False}
        exported, air = self._export()
        sources = self._load_sources()
        if snapshot_digest(sources) != self.view["source_digest"]:
            self._reset()
            return {"status": "REJECTED", "reason": "SOURCE_CHANGED_READ_TARGET"}
        snapshot = dict(sources)
        snapshot.update({"alva-air/gen-1.air": air, "alva-air/current": ("1\n" + exported["project_revision"] + "\n").encode()})
        identity = self.evaluator.identity()
        start = self.clock()
        self.work["evaluation_runs"] += 1
        digest = snapshot_digest(snapshot)
        result = self.evaluator(dict(snapshot), exported["project_revision"])
        self.work["evaluation_seconds"] += self.clock() - start
        bound = (result.get("tested_snapshot_sha256") == digest and result.get("project_revision") == exported["project_revision"]
                 and self.evaluator.identity() == identity)
        if not bound: return {"status": "UNVERIFIED_TEST_RECEIPT", "can_publish": False}
        checks = {k: result.get("checks", {}).get(k, "UNVERIFIED") for k in ("check", "build", "test")}
        if result.get("status") != "PASS" or any(checks.get(k) != "PASS" for k in ("check", "build", "test")):
            return {"status": "VALIDATION_FAILED", "checks": checks, "can_publish": False}
        current, _ = self._export()
        if current != exported:
            return {"status": "DRAFT_CHANGED_DURING_EVALUATION", "can_publish": False}
        proposal = {"id": "proposal_" + secrets.token_hex(12), "export": exported,
                    "snapshot_digest": digest, "test_identity": identity, "body_revision": changed["body_revision"],
                    "receipt_sha256": sha(canonical(result)), "expires": self.view["expires"]}
        self.proposal = proposal
        diff = self._call("preview_semantic_diff")["diff"]
        return {"status": "PREPARED", "proposal_id": proposal["id"], "can_publish": True,
                "diff": diff, "checks": checks, "scope": "SCOPE_ALLOWED",
                "test_receipt": {"snapshot_sha256": digest, "receipt_sha256": proposal["receipt_sha256"]}}

    def _publish_change(self, proposal_id):
        proposal = self.proposal
        if not proposal or proposal["id"] != proposal_id:
            return {"status": "REJECTED", "reason": "UNKNOWN_OR_CONSUMED_PROPOSAL"}
        self.proposal = None  # Consume BEFORE dispatch, including conflicts/uncertain transport.
        current, _ = self._export()
        if current != proposal["export"] or self.evaluator.identity() != proposal["test_identity"]:
            return {"status": "REJECTED", "reason": "DRAFT_OR_TEST_IDENTITY_CHANGED"}
        if snapshot_digest(self._load_sources()) != self.view["source_digest"]:
            self._reset()
            return {"status": "REJECTED", "reason": "SOURCE_CHANGED_READ_TARGET"}
        target = self.view["function"]
        try:
            commit = self._call("commit_transaction")  # Actual unchanged P34 decision and Native dispatch.
            self.tx = None
        except ToolFailure as e:
            self._reset()
            return {"status": "PUBLISH_REJECTED", "reason": str(e)[:2000]}
        except Exception:
            self.blocked = "PUBLICATION_OUTCOME_UNKNOWN_DO_NOT_RETRY"
            raise
        expected_revision = proposal["export"]["project_revision"]
        self.blocked = "PUBLISHED_REQUIRES_FRESH_VERIFICATION"
        fresh = None
        try:
            self._reset()
            fresh = self._new_native()
            def read(name, **args):
                answer = fresh.request("tools/call", {"name": name, "arguments": args})
                if answer.get("isError"): raise ToolFailure(answer)
                return answer["structuredContent"]
            begun = read("begin_transaction", project=self.project)
            info = read("read_function", transaction_id=begun["transaction_id"], function=target)
            read("abort_transaction", transaction_id=begun["transaction_id"])
            verified = begun["project_revision"] == commit["revision"] == expected_revision and info["body_revision"] == proposal["body_revision"]
            fresh.close()
            fresh = None
        except Exception as e:
            if fresh:
                try: fresh.close()
                except Exception: pass
            return {"status": "PUBLISHED_UNVERIFIED", "commit": commit, "reason": type(e).__name__}
        if not verified:
            self.blocked = "PUBLISHED_BUT_FRESH_AUTHORITY_MISMATCH"
            return {"status": "PUBLISHED_UNVERIFIED", "commit": commit, "reason": self.blocked}
        self.blocked = None
        return {"status": "PUBLISHED", "commit": commit, "fresh_authority_matches": True,
                "test_receipt_sha256": proposal["receipt_sha256"], "host_work": copy.deepcopy(self.work)}

    def close(self):
        with self.lock: self._reset()


def project_source_loader(manifest, inputs=None):
    """Trusted source inputs only; current AIR is exported separately by Core."""
    manifest = Path(manifest).resolve()
    root = manifest.parent
    if inputs is None:
        try: import tomllib
        except ImportError: raise RuntimeError("Python 3.11+ required for automatic manifest discovery; configure explicit inputs") from None
        modules = tomllib.loads(manifest.read_text(encoding="utf-8"))["modules"]
        inputs = [manifest.name, *modules.values()]
    paths = {}
    for value in inputs:
        p = Path(value)
        if p.is_absolute() or ".." in p.parts or "alva-air" in p.parts:
            raise ValueError("Source input must be a relative project source path")
        path = root / p
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError("Source symlinks/escapes are unsupported")
        paths["alva.toml" if path == manifest else p.as_posix()] = path
    if "alva.toml" not in paths: raise ValueError("Manifest must be in trusted inputs")
    def load():
        result = {}
        for name, path in paths.items():
            if path.is_symlink() or not path.resolve().is_relative_to(root): raise RuntimeError("SOURCE_PATH_CHANGED")
            result[name] = path.read_bytes()
        if sum(map(len, result.values())) > 16 * 1024**2: raise RuntimeError("SOURCE_INPUT_LIMIT")
        return result
    return load


def serve(host, incoming, outgoing):
    """MCP STDIO Host entry. Legacy protocol negotiation; no raw Native route."""
    while line := incoming.readline(1024**2 + 1):
        if len(line.encode()) > 1024**2: raise RuntimeError("HOST_REQUEST_LIMIT")
        try:
            request = json.loads(line)
            if not isinstance(request, dict): raise ValueError("Request must be an object")
        except (ValueError, TypeError):
            outgoing.write(json.dumps({"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":"Parse error"}}) + "\n")
            outgoing.flush(); continue
        if "id" not in request: continue
        method = request.get("method")
        if method == "initialize":
            result = {"protocolVersion":"2025-11-25","capabilities":{"tools":{}},
                      "serverInfo":{"name":"alva-maintenance-host","version":"0.1"},
                      "instructions":"Read target, prepare a body, review passing checks, publish its proposal. Host owns all transactions and tests."}
        elif method == "tools/list": result = {"tools":TOOLS}
        elif method == "ping": result = {}
        elif method == "tools/call":
            params = request.get("params", {})
            if not isinstance(params, dict): params = {}
            value = host.invoke(params.get("name"), params.get("arguments"))
            result = {"structuredContent":value,"content":[{"type":"text","text":json.dumps(value)}],
                      "isError":value.get("status") not in ("READY","PREPARED","PUBLISHED","UNCHANGED")}
        else:
            outgoing.write(json.dumps({"jsonrpc":"2.0","id":request["id"],"error":{"code":-32601,"message":"Method not found"}}) + "\n")
            outgoing.flush(); continue
        outgoing.write(json.dumps({"jsonrpc":"2.0","id":request["id"],"result":result}) + "\n")
        outgoing.flush()


if __name__ == "__main__":
    import argparse
    import sys
    from integrations.benchmark_runtime_v2.sandbox import SDK
    from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    args = p.parse_args()
    config = json.loads(args.config.read_bytes())
    sdk = SDK(*(Path(config[k]).resolve() for k in ("alva", "toolchain", "registry")))
    host = MaintenanceHost(lambda:AgentProcess(sdk.alva), config["project"], config["policy"],
        project_source_loader(config["project"], config.get("inputs")),
        LinuxProjectEvaluator(sdk, config["crate"], assertions=config.get("assertions", "")))
    try: serve(host, sys.stdin, sys.stdout)
    finally: host.close()
