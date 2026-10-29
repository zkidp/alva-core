"""Trusted mediator for fixed-component, function-body-only commit authority.

Not a semantic dependency analyzer or Core checker. Policy is Host supplied,
deep copied, never accepted from a tool argument. Only complete snapshots with
unchanged declaration/interface structure may authorize a Native commit.
"""
import copy
import hashlib
import json
import threading


class Unverified(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class GuardedNative:
    def __init__(self, inner, policy, allowed_tools, sink=lambda event: None):
        self._inner = inner
        self._policy = copy.deepcopy(policy)
        self._authorized = frozenset(policy["authorized_functions"])
        self._allowed = frozenset(allowed_tools)
        self._sink = sink
        self._lock = threading.RLock()
        self._baselines = {}

    def _forward(self, method, params, origin, **kwargs):
        answer = self._inner.request(method, params, **kwargs)
        self._sink({"event": "native_dispatch", "origin": origin, "method": method,
                    "params": params, "response": answer})
        return answer

    def _read(self, tx, name, **args):
        response = self._forward("tools/call", {"name": name, "arguments": {"transaction_id": tx, **args}}, "guard_read")
        if response.get("isError") or not isinstance(response.get("structuredContent"), dict):
            raise Unverified("STAGED_INSPECTION_FAILED:" + name)
        return response["structuredContent"]

    def _snapshot(self, tx):
        project = self._read(tx, "inspect_project")
        if set(project) != {"modules", "project_revision"} or not isinstance(project["project_revision"], str) or not project["project_revision"]:
            raise Unverified("INCOMPLETE_PROJECT_DESCRIPTOR")
        modules = project.get("modules")
        expected = self._policy["modules"]
        if not isinstance(modules, dict) or set(modules) != {"module:" + m for m in expected}:
            raise Unverified("MODULE_COVERAGE_MISMATCH")
        nodes = {}
        def walk(revision):
            if revision in nodes:
                return nodes[revision]
            if len(nodes) >= 2048:
                raise Unverified("INSPECTION_BOUND_EXCEEDED")
            node = self._read(tx, "inspect_entity", entity=revision)
            if node.get("revision") != revision or set(node) != {"revision", "kind", "entity", "fields", "slots"}:
                raise Unverified("INCOMPLETE_NODE_DESCRIPTOR")
            if not isinstance(node["fields"], dict) or not isinstance(node["slots"], dict):
                raise Unverified("INVALID_NODE_DESCRIPTOR")
            nodes[revision] = node
            for children in node["slots"].values():
                if not isinstance(children, list) or not all(isinstance(c, str) for c in children):
                    raise Unverified("INVALID_SLOT_DESCRIPTOR")
                for child in children:
                    walk(child)
            return node
        snapshot = {"modules": {}, "functions": {}, "project_revision": project.get("project_revision")}
        for module, trusted in expected.items():
            node = walk(modules["module:" + module])
            if node["kind"] != "module" or node["fields"].get("name") != module:
                raise Unverified("MODULE_IDENTITY_MISMATCH")
            if set(node["slots"]) != {"functions", "types", "tests", "externs", "benches"}:
                raise Unverified("UNSUPPORTED_MODULE_STRUCTURE")
            if node["slots"]["externs"] or node["slots"]["benches"]:
                raise Unverified("UNSUPPORTED_EXTERN_OR_BENCH_DECLARATIONS")
            functions = [nodes[x] for x in node["slots"]["functions"]]
            types = [nodes[x] for x in node["slots"]["types"]]
            if [n["fields"].get("name") for n in functions] != trusted["functions"] or any(n["kind"] != "function" for n in functions):
                raise Unverified("FUNCTION_COVERAGE_MISMATCH:" + module)
            if [n["fields"].get("name") for n in types] != trusted["types"]:
                raise Unverified("TYPE_COVERAGE_MISMATCH:" + module)
            snapshot["modules"][module] = {"fields": node["fields"], "entity": node["entity"],
                "function_order": trusted["functions"], "other_slots": {k: v for k, v in node["slots"].items() if k != "functions"}}
            for fn in functions:
                if set(fn["slots"]) != {"body", "inv", "params", "post", "pre", "returns"} or len(fn["slots"]["body"]) != 1:
                    raise Unverified("UNSUPPORTED_FUNCTION_STRUCTURE")
                name = module + "." + fn["fields"]["name"]
                # Every non-body slot is retained, not silently discarded.
                snapshot["functions"][name] = {"fields": fn["fields"], "entity": fn["entity"],
                    "metadata_slots": {k: v for k, v in fn["slots"].items() if k != "body"},
                    "body": fn["slots"]["body"][0]}
        if not self._authorized <= set(snapshot["functions"]):
            raise Unverified("AUTHORIZED_FUNCTION_NOT_COVERED")
        snapshot["coverage_nodes"] = len(nodes)
        return snapshot

    def _decision(self, tx):
        baseline = self._baselines.get(tx)
        if not baseline or "error" in baseline:
            return {"status": "SCOPE_UNVERIFIED", "reason": (baseline or {}).get("error", "NO_TRUSTED_BASELINE")}
        try:
            staged = self._snapshot(tx)
            if staged["modules"] != baseline["modules"]:
                raise Unverified("MODULE_INTERFACE_OR_DECLARATION_STRUCTURE_CHANGED")
            if set(staged["functions"]) != set(baseline["functions"]):
                raise Unverified("DECLARATION_COVERAGE_CHANGED")
            changed = []
            for name, before in baseline["functions"].items():
                after = staged["functions"][name]
                if {k: v for k, v in before.items() if k != "body"} != {k: v for k, v in after.items() if k != "body"}:
                    raise Unverified("UNSUPPORTED_SIGNATURE_CONTRACT_METADATA_CHANGE:" + name)
                if before["body"] != after["body"]:
                    changed.append(name)
            outside = sorted(set(changed) - self._authorized)
            return {"status": "SCOPE_VIOLATION" if outside else "SCOPE_ALLOWED", "changed_functions": sorted(changed),
                "unauthorized_functions": outside, "authorized_functions": sorted(self._authorized),
                "baseline_sha256": digest(baseline), "staged_sha256": digest(staged),
                "baseline_project_revision": baseline["project_revision"], "staged_project_revision": staged["project_revision"],
                "coverage_nodes": staged["coverage_nodes"], "scope": "FIXED_COMPONENT_FUNCTION_BODIES_ONLY"}
        except Exception as exc:
            return {"status": "SCOPE_UNVERIFIED", "reason": type(exc).__name__ + ":" + str(exc)}

    def request(self, method, params=None, **kwargs):
        # One gate covers every mutation, inspection and commit on this owned
        # session. The snapshot-to-forward interval is inside the same lock.
        with self._lock:
            params = copy.deepcopy(params or {})
            if method != "tools/call":
                if method not in {"initialize", "tools/list", "ping", "resources/list", "resources/templates/list", "prompts/list"}:
                    raise Unverified("PROTOCOL_METHOD_NOT_ALLOWED")
                return self._forward(method, params, "protocol", **kwargs)
            name, args = params.get("name"), params.get("arguments", {})
            if name not in self._allowed:
                return self._denied({"status": "SCOPE_UNVERIFIED", "reason": "TOOL_NOT_ALLOWED"}, params)
            if name == "commit_transaction":
                if not isinstance(args, dict) or set(args) != {"transaction_id"} or not isinstance(args["transaction_id"], str):
                    return self._denied({"status": "SCOPE_UNVERIFIED", "reason": "INVALID_COMMIT_ARGUMENTS"}, params)
                decision = self._decision(args["transaction_id"])
                self._sink({"event": "scope_decision", "params": params, "decision": decision})
                if decision["status"] != "SCOPE_ALLOWED":
                    return self._denied(decision, params)
                result = self._forward(method, params, "guarded_commit", **kwargs)
                if not result.get("isError"):
                    self._baselines.pop(args["transaction_id"], None)
                # MCP clients retain structuredContent, not arbitrary envelope
                # extensions. Preserve the native result fields and add a
                # distinct host-owned scope record, never a Core check status.
                return dict(result, structuredContent=dict(result.get("structuredContent", {}), host_scope=decision))
            answer = self._forward(method, params, "tool", **kwargs)
            if name == "begin_transaction" and not answer.get("isError"):
                tx = answer["structuredContent"]["transaction_id"]
                try:
                    self._baselines[tx] = self._snapshot(tx)
                except Exception as exc:
                    self._baselines[tx] = {"error": type(exc).__name__ + ":" + str(exc)}
                self._sink({"event": "trusted_baseline", "transaction_id": tx, "snapshot": self._baselines[tx]})
            elif name == "abort_transaction" and not answer.get("isError"):
                self._baselines.pop(args.get("transaction_id"), None)
            return answer

    def _denied(self, decision, params):
        self._sink({"event": "scope_denied_no_native_dispatch", "params": params, "decision": decision})
        return {"isError": True, "content": [{"type": "text", "text": json.dumps(decision, sort_keys=True)}],
                "structuredContent": {"host_scope": decision}, "host_scope": decision}

    def tool(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def notify(self, *args, **kwargs):
        with self._lock:
            method = args[0] if args else kwargs.get("method")
            if method not in {"notifications/initialized", "notifications/cancelled"}:
                raise Unverified("NOTIFICATION_NOT_ALLOWED")
            return self._inner.notify(*args, **kwargs)

    def close(self):
        with self._lock:
            return self._inner.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        with self._lock:
            return self._inner.__exit__(*args)
