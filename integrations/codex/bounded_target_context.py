"""Opt-in read-only projection of an existing transactional AIR snapshot.

Completeness means target syntax references + direct callee signatures + nested
named types, NOT callee bodies, dynamic effects, new candidate requirements or
whole-program dependency completeness. No source parser or inference engine.
"""
from __future__ import annotations

import argparse
import copy
import re
import time
from pathlib import Path

from integrations.codex.maintenance_context import ContextHost, serve
from integrations.codex.maintenance_host import (
    AgentProcess, MaintenanceHost, canonical, project_source_loader, sha,
)

MAX_BYTES = 16384
MAX_DECLARATIONS = 64
MAX_NODES = 2048
BOUNDARY = "target references; direct callee signatures; recursive named types; NOT callee bodies/effects"


class Unsupported(ValueError):
    pass


def project_context(snapshot, function, builtins, *, max_bytes=MAX_BYTES, max_declarations=MAX_DECLARATIONS):
    """Project actual inspected nodes only. Bounds apply to the entire JSON value."""
    if type(max_bytes) is not int or max_bytes < 1024 or type(max_declarations) is not int or max_declarations < 1:
        raise ValueError("Invalid trusted context limits")
    project, nodes = snapshot["project"], snapshot["nodes"]
    revision = project["project_revision"]
    if not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise Unsupported("INVALID_PROJECT_REVISION")
    if not isinstance(nodes, dict) or len(nodes) > MAX_NODES or len(canonical(snapshot)) > 8 * 1024**2:
        raise Unsupported("SNAPSHOT_BOUND")
    # Verify snapshot coverage before selecting any declarations. Never accept a
    # missing child as an empty type, nor a detached node as a declaration.
    pending, seen = list(project["modules"].values()), set()
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        n = nodes.get(key)
        if not isinstance(n, dict) or n.get("revision") != key or not isinstance(n.get("fields"), dict) or not isinstance(n.get("slots"), dict):
            raise Unsupported("INCOMPLETE_SNAPSHOT")
        seen.add(key)
        for children in n["slots"].values():
            if not isinstance(children, list) or any(not isinstance(c, str) for c in children):
                raise Unsupported("INVALID_SNAPSHOT_SLOT")
            pending.extend(children)
    if seen != set(nodes):
        raise Unsupported("EXTRANEOUS_SNAPSHOT_NODES")
    functions, types = {}, {}
    for module_key, key in sorted(project["modules"].items()):
        module = nodes[key]
        owner = module["fields"].get("name")
        if module["kind"] != "module" or module_key != "module:" + owner:
            raise Unsupported("INVALID_MODULE")
        for slot, kind, table in (("functions", "function", functions), ("types", "type", types)):
            for child in module["slots"][slot]:
                n = nodes[child]
                name = owner + "." + n["fields"]["name"]
                if n["kind"] != kind or name in table:
                    raise Unsupported("AMBIGUOUS_DECLARATION")
                table[name] = (owner, n)
    if function not in functions:
        raise Unsupported("TARGET_NOT_IN_SNAPSHOT")
    owner, target = functions[function]
    body = target["slots"]["body"]
    if len(body) != 1:
        raise Unsupported("INVALID_TARGET_BODY")
    base = {"status": "COMPLETE_WITHIN_BOUNDARY", "boundary": BOUNDARY,
            "project_revision": revision, "function": function,
            "target_revision": target["revision"], "body_revision": body[0],
            "snapshot_sha256": sha(canonical(snapshot)),
            "limits": {"utf8_bytes": max_bytes, "declarations": max_declarations},
            "types": [], "callees": [], "unresolved": [], "unresolved_count": 0}
    type_queue, missing, selected_types, calls = set(), set(), {}, set()

    def qualify(name, module):
        if not isinstance(name, str) or not name:
            raise Unsupported("INVALID_REFERENCE_NAME")
        return name if "." in name else module + "." + name

    def type_expr(key, module, active=frozenset()):
        if key in active:
            raise Unsupported("CYCLIC_TYPE_EXPRESSION")
        n = nodes[key]
        if n["kind"] != "type_expr":
            raise Unsupported("UNSUPPORTED_TYPE_NODE")
        shape = n["fields"].get("shape")
        if shape == "prim":
            return {"prim": n["fields"]["name"]}
        if shape == "named":
            name = qualify(n["fields"]["name"], module)
            type_queue.add(name)
            return {"named": name}
        slots = {"vec": ("inner",), "map": ("key", "value"), "result": ("ok", "err")}.get(shape)
        if slots is None:
            raise Unsupported("UNSUPPORTED_TYPE_SHAPE")
        return {shape: [type_expr(single(n, s), module, active | {key}) for s in slots]}

    def single(n, slot):
        values = n["slots"].get(slot, [])
        if len(values) != 1:
            raise Unsupported("INVALID_TYPE_SLOT")
        return values[0]

    # Traverse only the target, including its contracts and explicit type uses.
    # Merely locating a callee below does not inspect its body or contracts.
    pending, visited = [target["revision"]], set()
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        n = nodes[key]
        if n["kind"] == "call":
            name = n["fields"]["name"]
            if name not in builtins:
                calls.add(qualify(name, owner))
        if n["kind"] == "type_expr" and n["fields"].get("shape") == "named":
            type_queue.add(qualify(n["fields"]["name"], owner))
        if n["kind"] in ("record", "record_update", "variant", "match"):
            type_queue.add(qualify(n["fields"]["type"], owner))
        pending.extend(c for children in n["slots"].values() for c in children)
    for name in sorted(calls):
        found = functions.get(name)
        if found is None:
            missing.add("unresolved_callee:" + name)
            continue
        module, n = found
        params = [{"name": nodes[p]["fields"]["name"], "type": type_expr(single(nodes[p], "type"), module)}
                  for p in n["slots"]["params"]]
        base["callees"].append({"function": name, "revision": n["revision"], "params": params,
                                "returns": type_expr(single(n, "returns"), module),
                                "pure": n["fields"]["pure"], "effects": n["fields"]["eff"]})
    while type_queue:
        name = min(type_queue)
        type_queue.remove(name)
        if name in selected_types or "unresolved_type:" + name in missing:
            continue
        found = types.get(name)
        if found is None:
            missing.add("unresolved_type:" + name)
            continue
        module, n = found
        item = {"name": name, "revision": n["revision"], "kind": n["fields"]["kind"]}
        selected_types[name] = item  # Break recursive named-type cycles.
        if item["kind"] == "record":
            item["fields"] = [{"name": nodes[f]["fields"]["name"], "type": type_expr(single(nodes[f], "type"), module)}
                              for f in n["slots"]["fields"]]
        elif item["kind"] == "enum":
            item["variants"] = n["fields"]["variants"]
        elif item["kind"] == "alias":
            item["alias"] = type_expr(single(n, "alias"), module)
        else:
            raise Unsupported("UNSUPPORTED_TYPE_DECLARATION")
    base["types"] = [selected_types[n] for n in sorted(selected_types)]
    base["unresolved_count"] = len(missing)
    base["unresolved"] = sorted(missing)
    if missing:
        base["status"] = "PARTIAL"
    if len(base["types"]) + len(base["callees"]) > max_declarations or len(canonical(base)) > max_bytes:
        # No partial declaration/field list masquerades as a complete context.
        full_digest = sha(canonical(base))
        base.update(status="TOO_BROAD", types=[], callees=[], unresolved=[],
                    required_declarations=len(selected_types) + len(calls), complete_payload_sha256=full_digest,
                    reason="DECLARATION_OR_BYTE_BOUND; no declarations delivered")
        if len(canonical(base)) > max_bytes:
            raise Unsupported("IDENTITY_ENVELOPE_EXCEEDS_BOUND")
    return base


class BoundedTargetHost(ContextHost):
    """Separate experimental entry. Existing Host/ContextHost defaults unchanged."""
    def invoke(self, name, args):
        with self.lock, self.host.lock:
            result = super().invoke(name, args)
            if name != "read_target" or result.get("status") != "READY":
                return result
            started = time.monotonic()
            before = self.host.work["native_calls"]
            try:
                with self.host.guard._lock:
                    snapshot = self.host._call("inspect_scope_snapshot")
                    info = self.host._call("read_function", function=result["function"])
                    current = self.host._call("inspect_project")
                if current != snapshot["project"] or info["body"] != result["body"]:
                    raise Unsupported("CONTEXT_CHANGED_DURING_READ")
                builtins = {b["name"] for b in result["context"]["available_builtins"]}
                context = project_context(snapshot, result["function"], builtins)
                if context["body_revision"] != info["body_revision"]:
                    raise Unsupported("TARGET_REVISION_MISMATCH")
                result["bounded_dependencies"] = context
            except Exception as exc:
                # Read-context failure does not weaken/bypass mutation admission.
                result["bounded_dependencies"] = {"status": "UNKNOWN", "boundary": BOUNDARY,
                    "reason": str(exc) if isinstance(exc, Unsupported) else type(exc).__name__,
                    "types": [], "callees": [], "recovery": "Use existing read_target/read_source/read_reference; do not infer completeness"}
            result["dependency_projection_work"] = {"native_calls": self.host.work["native_calls"] - before,
                "elapsed_seconds": time.monotonic() - started,
                "response_utf8_bytes": len(canonical(result["bounded_dependencies"]))}
            self.work["context_reply_bytes"] += len(canonical(result["bounded_dependencies"]))
            return copy.deepcopy(result)


if __name__ == "__main__":
    import json
    import sys
    from integrations.benchmark_runtime_v2.sandbox import SDK
    from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    config = json.loads(parser.parse_args().config.read_bytes())
    sdk = SDK(*(Path(config[k]).resolve() for k in ("alva", "toolchain", "registry")))
    host = BoundedTargetHost(MaintenanceHost(lambda: AgentProcess(sdk.alva), config["project"], config["policy"],
        project_source_loader(config["project"], config.get("inputs")),
        LinuxProjectEvaluator(sdk, config["crate"], assertions=config.get("assertions", ""))))
    try:
        serve(host, sys.stdin, sys.stdout)
    finally:
        host.close()
