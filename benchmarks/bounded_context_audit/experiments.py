"""New deterministic context experiments; no provider or historical replay.

Trusted Core inspections are read/draft operations. Executable behavioral checks
use the unchanged LinuxProjectEvaluator OS boundary. Generated evidence stays local.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.codex.bounded_target_context import BoundedTargetHost, project_context, Unsupported
from integrations.codex.maintenance_host import AgentProcess, MaintenanceHost, canonical, sha, project_source_loader

FACT_FILES = {
    "alva.toml": b'[project]\nname="context_facts"\n[modules]\nmodel="model.alva"\napi="api.alva"\nnoise="noise.alva"\n',
    "model.alva": b'''(module (name "model") (version "1") (export Envelope helper)
 (type Flag (enum (variant on) (variant off)))
 (type Alias (alias Flag))
 (type Item (record (field flag Alias)))
 (type Envelope (record (field item Item) (field history (vec Alias))))
 (fn leaf (params (param item Envelope)) (returns (prim i64)) (pure) (body (int 7)))
 (fn helper (params (param item Envelope)) (returns (prim i64)) (pure)
  (body (call leaf (ref item)))))''',
    "api.alva": b'''(module (name "api") (version "1") (dep "model" "1") (export target)
 (fn target (params (param item model.Envelope)) (returns (prim i64)) (pure)
  (body (call model.helper (ref item)))))''',
    "noise.alva": b'''(module (name "noise") (version "1") (export unused)
 (fn unused (params) (returns (prim string)) (pure)
  (body (string "UNRELATED_BODY_SENTINEL_NOT_CONTEXT"))))''',
}
FACT_POLICY = {"authorized_functions": ["api.target"], "modules": {
    "model": {"functions": ["leaf", "helper"], "types": ["Flag", "Alias", "Item", "Envelope"]},
    "api": {"functions": ["target"], "types": []}, "noise": {"functions": ["unused"], "types": []}}}


def write_project(root, files):
    root.mkdir(parents=True)
    for name, data in files.items():
        (root / name).write_bytes(data)


def native_call(native, name, **args):
    answer = native.request("tools/call", {"name": name, "arguments": args})
    if answer.get("isError"):
        raise RuntimeError("CORE_OPERATION_REJECTED:" + str(answer["structuredContent"])[:1500])
    return answer["structuredContent"]


def reference(snapshot, target, builtins):
    """Independent full-graph relational oracle, not the projection's traversal.

    Precomputes declaration/type/signature tables for ALL modules, then takes a
    fixed point over the selected types. Fixtures also have explicit expectations.
    This is analysis-only; it supplies no hints or runtime treatment information.
    """
    nodes = snapshot["nodes"]
    functions, types, owners = {}, {}, {}
    for root in snapshot["project"]["modules"].values():
        module = nodes[root]
        owner = module["fields"]["name"]
        for slot, table in (("functions", functions), ("types", types)):
            for key in module["slots"][slot]:
                name = owner + "." + nodes[key]["fields"]["name"]
                table[name], owners[name] = nodes[key], owner

    def qualify(name, owner):
        return name if "." in name else owner + "." + name

    def expression(key, owner):
        n = nodes[key]
        shape = n["fields"]["shape"]
        if shape == "prim": return {"prim": n["fields"]["name"]}
        if shape == "named": return {"named": qualify(n["fields"]["name"], owner)}
        fields = {"vec": ["inner"], "map": ["key", "value"], "result": ["ok", "err"]}[shape]
        return {shape: [expression(n["slots"][f][0], owner) for f in fields]}

    def names(value):
        if isinstance(value, dict):
            return ({value["named"]} if "named" in value else set()).union(
                *(names(v) for v in value.values()))
        if isinstance(value, list): return set().union(*(names(v) for v in value))
        return set()

    definitions = {}
    for name, n in types.items():
        item = {"name": name, "revision": n["revision"], "kind": n["fields"]["kind"]}
        if item["kind"] == "record":
            item["fields"] = [{"name": nodes[f]["fields"]["name"],
                "type": expression(nodes[f]["slots"]["type"][0], owners[name])} for f in n["slots"]["fields"]]
        elif item["kind"] == "alias": item["alias"] = expression(n["slots"]["alias"][0], owners[name])
        elif item["kind"] == "enum": item["variants"] = n["fields"]["variants"]
        else: raise ValueError("Reference subset does not support this type kind")
        definitions[name] = item
    signatures = {name: {"function": name, "revision": n["revision"],
        "params": [{"name": nodes[p]["fields"]["name"], "type": expression(nodes[p]["slots"]["type"][0], owners[name])}
                   for p in n["slots"]["params"]],
        "returns": expression(n["slots"]["returns"][0], owners[name]),
        "pure": n["fields"]["pure"], "effects": n["fields"]["eff"]} for name, n in functions.items()}

    # Build full containment reachability for every declaration before selecting.
    contents = {}
    for name, node in functions.items():
        visited, frontier = set(), [node["revision"]]
        while frontier:
            key = frontier.pop()
            if key not in visited:
                visited.add(key)
                frontier += [v for children in nodes[key]["slots"].values() for v in children]
        contents[name] = visited
    calls = {name: {qualify(nodes[k]["fields"]["name"], owners[name]) for k in keys
                    if nodes[k]["kind"] == "call" and nodes[k]["fields"]["name"] not in builtins}
             for name, keys in contents.items()}
    selected = set()
    for key in contents[target]:
        n = nodes[key]
        if n["kind"] == "type_expr": selected |= names(expression(key, owners[target]))
        if n["kind"] in ("record", "record_update", "variant", "match"):
            selected.add(qualify(n["fields"]["type"], owners[target]))
    for callee in calls[target]: selected |= names(signatures[callee])
    while True:
        expanded = selected | set().union(*(names(definitions[n]) for n in selected))
        if expanded == selected: break
        selected = expanded
    return {"types": [definitions[n] for n in sorted(selected)],
            "callees": [signatures[n] for n in sorted(calls[target])],
            "full_call_edges": {n: sorted(v) for n, v in sorted(calls.items())}}


class NeverEvaluate:
    def __call__(self, *_): raise RuntimeError("Read-only experiment unexpectedly requested evaluation")
    def identity(self): return "READ_ONLY_NO_BEHAVIOR_RECEIPT"


def facts(binary, root):
    write_project(root, FACT_FILES)
    source = project_source_loader(root / "alva.toml", list(FACT_FILES))
    original = source()
    native = AgentProcess(binary)
    try:
        begun = native_call(native, "begin_transaction", project=str(root / "alva.toml"))
        tx = begun["transaction_id"]
        snap = native_call(native, "inspect_scope_snapshot", transaction_id=tx)
        context = native_call(native, "read_function_context", transaction_id=tx, function="api.target")
        builtins = {b["name"] for b in context["available_builtins"]}
        projected = project_context(snap, "api.target", builtins)
        expected = reference(snap, "api.target", builtins)
        if projected["types"] != expected["types"] or projected["callees"] != expected["callees"]:
            raise RuntimeError("INDEPENDENT_GRAPH_REFERENCE_DISAGREEMENT")
        if [t["name"] for t in projected["types"]] != ["model.Alias", "model.Envelope", "model.Flag", "model.Item"]:
            raise RuntimeError("FIXTURE_TYPE_EXPECTATION_DISAGREEMENT")
        if [c["function"] for c in projected["callees"]] != ["model.helper"]:
            raise RuntimeError("FIXTURE_CALLEE_EXPECTATION_DISAGREEMENT")
        if projected["status"] != "COMPLETE_WITHIN_BOUNDARY" or "UNRELATED_BODY_SENTINEL" in str(projected):
            raise RuntimeError("PROJECTION_BOUNDARY_FAILURE")
        if expected["full_call_edges"]["model.helper"] != ["model.leaf"]:
            raise RuntimeError("TRANSITIVE_CONTROL_NOT_ESTABLISHED")
        before = native_call(native, "export_transaction", transaction_id=tx)
        again = project_context(snap, "api.target", builtins)
        after = native_call(native, "export_transaction", transaction_id=tx)
        if projected != again or before != after: raise RuntimeError("READ_ONLY_OR_DETERMINISM_FAILURE")
        controls = []
        for name in ("missing_type", "missing_callee", "declaration_bound", "byte_bound", "broken_snapshot"):
            mutant = copy.deepcopy(snap)
            if name == "missing_type":
                key = next(k for k, v in mutant["nodes"].items()
                           if v["kind"] == "type_expr" and v["fields"].get("name") == "model.Envelope")
                mutant["nodes"][key]["fields"]["name"] = "unavailable.Ghost"
            elif name == "missing_callee":
                key = next(k for k, v in mutant["nodes"].items()
                           if v["kind"] == "call" and v["fields"].get("name") == "model.helper")
                mutant["nodes"][key]["fields"]["name"] = "unavailable.remote"
            elif name == "byte_bound":
                key = next(k for k, v in mutant["nodes"].items() if v["kind"] == "type" and v["fields"].get("name") == "Flag")
                mutant["nodes"][key]["fields"]["variants"] = ["oversized_" + "x" * 20000]
            elif name == "broken_snapshot": mutant["nodes"].pop(next(iter(mutant["nodes"])))
            try:
                value = project_context(mutant, "api.target", builtins, max_declarations=1 if name == "declaration_bound" else 64)
                wanted = "PARTIAL" if name.startswith("missing_") else "TOO_BROAD"
                if value["status"] != wanted: raise RuntimeError("FAULT_CONTROL_WRONG_STATUS:" + name)
                if wanted == "TOO_BROAD" and (value["types"] or value["callees"] or len(canonical(value)) > 16384):
                    raise RuntimeError("SILENT_TRUNCATION_OR_BOUND_FAILURE")
                controls.append({"control": name, "status": value["status"], "bytes": len(canonical(value))})
            except Unsupported as exc:
                if name != "broken_snapshot": raise
                controls.append({"control": name, "status": "UNSUPPORTED_INPUT", "reason": str(exc)})
        body = native_call(native, "read_function", transaction_id=tx, function="api.target")
        native_call(native, "replace_function_body", transaction_id=tx, function="api.target",
                    expected_body_revision=body["body_revision"], body="(body (+ (call model.helper (ref item)) (int 1)))")
        changed = native_call(native, "inspect_scope_snapshot", transaction_id=tx)
        current = project_context(changed, "api.target", builtins)
        if current["project_revision"] == projected["project_revision"] or current["body_revision"] == projected["body_revision"]:
            raise RuntimeError("REAL_DRAFT_REVISION_NOT_UPDATED")
        if current["project_revision"] != changed["project"]["project_revision"]:
            raise RuntimeError("DRAFT_CONTEXT_IDENTITY_MISMATCH")
        native_call(native, "abort_transaction", transaction_id=tx)
    finally:
        native.close()
    # Exercise the public read response and measure its actual backend work.
    host_base = MaintenanceHost(lambda: AgentProcess(binary), root / "alva.toml", FACT_POLICY, source, NeverEvaluate())
    host = BoundedTargetHost(host_base)
    original_call = host_base._call
    try:
        ready = host.invoke("read_target", {"function": "api.target"})
        if ready["bounded_dependencies"]["status"] != "COMPLETE_WITHIN_BOUNDARY":
            raise RuntimeError("REAL_HOST_CONTEXT_NOT_READY")
        def incomplete(name, **args):
            value = original_call(name, **args)
            if name == "inspect_scope_snapshot":
                value = copy.deepcopy(value)
                value["nodes"].pop(next(iter(value["nodes"])))
            return value
        host_base._call = incomplete
        failed = host.invoke("read_target", {"function": "api.target"})
        if failed["bounded_dependencies"]["status"] != "UNKNOWN" or host_base.blocked:
            raise RuntimeError("UNKNOWN_NOT_DELIVERED_BY_PUBLIC_HOST")
    finally:
        host_base._call = original_call
        host.close()
    if source() != original or (root / "alva-air/current").exists():
        raise RuntimeError("READ_EXPERIMENT_PUBLISHED_OR_CHANGED_SOURCE")
    return {"status": "PASS", "reference_types": len(expected["types"]), "direct_callees": len(expected["callees"]),
        "full_call_edges": expected["full_call_edges"], "transitive_leaf_body_delivered": False,
        "controls": controls, "host_failure_control": "UNKNOWN", "projection_bytes": len(canonical(projected)),
        "whole_source_bytes": sum(len(v) for p, v in original.items() if p.endswith(".alva")),
        "raw_target_body_bytes": len(ready["body"].encode()), "model_read_target_response_bytes": len(canonical(ready)),
        "projection_work": ready["dependency_projection_work"], "host_backend_work_including_failure_control": host_base.work,
        "base_project_revision": projected["project_revision"], "draft_project_revision": current["project_revision"],
        "source_unchanged": True, "authority_published": False,
        "synthetic_control_limit": "Mutated graph descriptors are fault injections, not claimed valid AIR revisions",
        "payload_limit": "Sizes are deterministic payload measurements, not model exposure or provider token counts"}


def behavior_files(delta):
    op = "+" if delta == 1 else "-"
    return {"alva.toml": b'[project]\nname="behavior_boundary"\n[modules]\nmodel="model.alva"\napi="api.alva"\n',
        "model.alva": f'''(module (name "model") (version "1") (export adjust)
 (fn adjust (params (param x (prim i64))) (returns (prim i64)) (pure)
  (body ({op} (ref x) (int 1)))))'''.encode(),
        "api.alva": b'''(module (name "api") (version "1") (dep "model" "1") (export target)
 (fn target (params (param x (prim i64))) (returns (prim i64)) (pure)
  (body (call model.adjust (ref x)))))'''}


def behavior(sdk, root):
    from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
    from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox
    LinuxSandbox(sdk)
    rows, semantic_facts = [], []
    policy = {"authorized_functions": ["api.target"], "modules": {
        "model": {"functions": ["adjust"], "types": []}, "api": {"functions": ["target"], "types": []}}}
    for delta in (1, -1):
        project = root / ("increment" if delta == 1 else "decrement")
        files = behavior_files(delta)
        write_project(project, files)
        assertions = '''
#[test] fn public_requirement_and_protected_helper() {
 for x in [-5_i64,0,10,100] {
  assert_eq!(crate::api::target(x),x+2);
  assert_eq!(crate::model::adjust(x),x+DELTA);
 }
}'''.replace("DELTA", str(delta))
        evaluator = LinuxProjectEvaluator(sdk, "behavior_boundary", assertions=assertions)
        base = MaintenanceHost(lambda: AgentProcess(sdk.alva), project / "alva.toml", policy,
            project_source_loader(project / "alva.toml", list(files)), evaluator)
        host = BoundedTargetHost(base)
        try:
            ready = host.invoke("read_target", {"function": "api.target"})
            dependencies = ready["bounded_dependencies"]
            facts_only = {"body": ready["body"], "types": dependencies["types"],
                "callees": [{k: v for k, v in c.items() if k != "revision"} for c in dependencies["callees"]]}
            semantic_facts.append(facts_only)
            candidates = []
            for correction in (1, 3):
                result = host.invoke("prepare_change", {"view_id": ready["view_id"],
                    "body": f"(body (+ (call model.adjust (ref x)) (int {correction})))"})
                expected = "PREPARED" if delta + correction == 2 else "VALIDATION_FAILED"
                if result["status"] != expected: raise RuntimeError("BEHAVIOR_CONTROL_MISMATCH:" + str(result))
                candidates.append({"correction": correction, "status": result["status"], "checks": result["checks"]})
            rows.append({"helper_delta": delta, "context_status": dependencies["status"],
                "project_revision": dependencies["project_revision"], "snapshot_sha256": dependencies["snapshot_sha256"],
                "callee_revision": dependencies["callees"][0]["revision"], "candidates": candidates,
                "host_backend_work": base.work, "published": False})
        finally:
            host.close()
        if (project / "alva-air/current").exists(): raise RuntimeError("Behavior experiment must not publish")
    if semantic_facts[0] != semantic_facts[1]: raise RuntimeError("SIGNATURE_CONTROL_NOT_EQUAL")
    if rows[0]["project_revision"] == rows[1]["project_revision"] or rows[0]["callee_revision"] == rows[1]["callee_revision"]:
        raise RuntimeError("REAL_IDENTITY_DIFFERENCE_MISSING")
    return {"status": "PASS", "target_body_and_signature_facts_equal": True, "full_payload_byte_identical": False,
        "opaque_identities_differ": True, "actual_isolated_candidate_evaluations": 4, "rows": rows,
        "conclusion": "Signatures and opaque identities do not specify callee behavior; more implementation evidence can be necessary",
        "not_an_agent_experiment": True}


def main(args):
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"status": "RUNNING", "model_generation_calls": 0, "input_token_api_calls": 0,
              "driver_sha256": sha(Path(__file__).read_bytes()), "binary_sha256": sha(args.alva.read_bytes())}
    try:
        result["E1"] = facts(args.alva, args.output / "facts")
        if args.toolchain and args.registry:
            from integrations.benchmark_runtime_v2.sandbox import SDK
            result["E2"] = behavior(SDK(args.alva, args.toolchain, args.registry), args.output / "behavior")
        else:
            result["E2"] = {"status": "NOT_RUN", "reason": "Linux isolated SDK required; no stub behavior result"}
        result["status"] = "PASS"
    except Exception as exc:
        result.update(status="FAIL", error=type(exc).__name__ + ":" + str(exc)[:2000])
        raise
    finally:
        (args.output / "RESULTS.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "E1": result["E1"]["status"], "E2": result["E2"]["status"]}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--alva", type=lambda s: Path(s).resolve(), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--toolchain", type=lambda s: Path(s).resolve())
    p.add_argument("--registry", type=lambda s: Path(s).resolve())
    a = p.parse_args()
    if bool(a.toolchain) != bool(a.registry): p.error("Supply both toolchain and registry")
    main(a)
