"""Original MM02 deterministic engineering; unchanged P22/P23 isolation only."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_design import feasibility as prior, witnesses
from benchmarks.p33_shared_scope.reproduce import Client, SHARED, TARGET, OTHER, path_to
from benchmarks.p34_scope_guard.cases import case, TOOLS
from benchmarks.native_prospective.service import files
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK
from integrations.codex.precommit_scope_guard import GuardedNative


def body_roots(c, functions):
    return {f: c.call("inspect_entity", entity=f)["slots"]["body"][0] for f in functions}


def prepare_local(c):
    nodes, other = c.nodes(TARGET), c.nodes(OTHER)
    shared = nodes[SHARED]
    assert other[SHARED] == shared
    path = path_to(nodes, TARGET, SHARED)
    parent = nodes[path[-1]["parent"]]
    assert parent["kind"] == "binding" and parent["fields"]["name"] == "rest"
    assert parent["slots"]["body"] == [SHARED]
    assert parent["revision"] not in other, "attachment must be prefix-only"
    found = c.call("create_reference", name="found")["revision"]
    empty = c.call("create_literal", type="string", value="")["revision"]
    unset = c.call("create_binary", op="==", left=found, right=empty)["revision"]
    yes = c.call("create_literal", type="bool", value="true")["revision"]
    condition = c.call("create_if", **{"cond": unset, "then": shared["slots"]["cond"][0], "else": yes})["revision"]
    replacement = c.call("create_if", **{"cond": condition, "then": shared["slots"]["then"][0], "else": shared["slots"]["else"][0]})["revision"]
    return {"original_shared": shared, "path": path, "attachment": parent,
            "replacement": replacement, "initial_nodes": nodes, "other_nodes": other}


def main(args):
    if sys.platform != "linux":
        raise RuntimeError("UNSUPPORTED: requires existing P22/P23 Linux backend; no fallback")
    args.output.mkdir(parents=True, exist_ok=False)
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    fixed = case("MM02_SHARED")
    task, bundle = fixed["task"], fixed["bundle"]
    assert bundle["payload_sha256"] == "352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf"
    assert fixed["policy"]["authorized_functions"] == [TARGET]
    rows = []
    for route in ("detached_only", "original_shared_mutation", "prefix_binding_reconnection"):
        ledger, calls = [], []
        with PersistentSandbox(bundle, bundle["payload_sha256"], sdk, wall_seconds=300, rpc_seconds=30) as box:
            original = files(box)
            assert original == decode(bundle, bundle["payload_sha256"])
            baseline_regression = prior.evaluate(box, task["crate"], witnesses.regressions("MM02"))
            baseline_goal = prior.evaluate(box, task["crate"], witnesses.goals("MM02"))
            assert baseline_regression["status"] == "PASS" and baseline_goal["status"] == "TEST_FAIL"
            with GuardedNative(box.mcp(), fixed["policy"], TOOLS, ledger.append) as native:
                prior.initialize(native)
                schemas = native.request("tools/list")["tools"]
                assert {t["name"] for t in schemas} == set(TOOLS) and len(schemas) == 20
                c = Client(native, calls)
                c.begin()
                before = body_roots(c, task["functions"])
                initial_project = c.call("inspect_project")
                diagnostics = {}
                if route == "original_shared_mutation":
                    diagnostics = witnesses.mutate_native("MM02", c)
                else:
                    plan = prepare_local(c)
                    diagnostics = {k: v for k, v in plan.items() if k not in ("initial_nodes", "other_nodes")}
                    # A detached node must never be credited as connected progress.
                    assert body_roots(c, task["functions"]) == before
                    if route == "prefix_binding_reconnection":
                        c.call("replace_expression", parent=plan["attachment"]["revision"],
                               child=plan["replacement"], position="body")
                        current = c.nodes(TARGET)
                        assert current[plan["replacement"]]["kind"] == "if"
                        assert c.call("inspect_entity", entity=SHARED) == plan["original_shared"]
                        assert c.nodes(OTHER) == plan["other_nodes"]
                staged = body_roots(c, task["functions"])
                changed = [f for f in before if before[f] != staged[f]]
                expected = [] if route == "detached_only" else [TARGET, OTHER] if route == "original_shared_mutation" else [TARGET]
                assert set(changed) == set(expected)
                preview = c.call("preview_semantic_diff")
                checked = c.call("check_transaction")
                assert checked == {"problems": []}
                assert files(box) == original, "staging must not publish"
                decision, commit = None, None
                if route == "detached_only":
                    refusals = {name: c.raw("describe_operation", name=name) for name in
                                ("create_binding", "create_block", "append_step")}
                    assert all(r.get("isError") and "E_MCP_OPERATION_NOT_EXPOSED" in json.dumps(r)
                               for r in refusals.values())
                    root_revision = c.call("inspect_entity", entity=TARGET)["revision"]
                    root_attempt = c.raw("replace_expression", parent=root_revision,
                                         child=plan["replacement"], position="body")
                    assert root_attempt.get("isError") and "invalid position" in json.dumps(root_attempt)
                    assert body_roots(c, task["functions"]) == before
                    diagnostics["unexposed_operation_refusals"] = refusals
                    diagnostics["direct_function_body_refusal"] = root_attempt
                    c.call("abort_transaction")
                else:
                    commit = c.raw("commit_transaction")
                    decision = commit["structuredContent"]["host_scope"]
                    assert decision["status"] == ("SCOPE_ALLOWED" if route == "prefix_binding_reconnection" else "SCOPE_VIOLATION")
                    if commit.get("isError"):
                        assert files(box) == original
                        c.call("abort_transaction")
            published = files(box)
            for p, data in original.items():
                assert published[p] == data, "original inputs remain byte-identical"
            with box.mcp() as fresh:
                prior.initialize(fresh)
                r = Client(fresh, calls)
                r.begin()
                final = body_roots(r, task["functions"])
                final_project = r.call("inspect_project")
                r.call("abort_transaction")
            allowed = route == "prefix_binding_reconnection"
            assert final == (staged if allowed else before)
            if allowed:
                assert not commit.get("isError")
                assert final_project["project_revision"] == commit["structuredContent"]["revision"]
            assert (final_project != initial_project) == allowed
            assert bool(set(published) - set(original)) == allowed, "AIR must publish only on allowed route"
            goal = prior.evaluate(box, task["crate"], witnesses.goals("MM02"))
            regression = prior.evaluate(box, task["crate"], witnesses.regressions("MM02"))
            assert goal["status"] == ("PASS" if allowed else "TEST_FAIL")
            assert regression["status"] == "PASS"
            dispatches = [e for e in ledger if e["event"] == "native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
            assert len(dispatches) == int(allowed)
            row = {"route": route, "before_body_revisions": before, "staged_body_revisions": staged,
                   "fresh_body_revisions": final, "changed_functions": changed, "preview": preview,
                   "check": checked, "guard": decision, "actual_native_commits": len(dispatches),
                   "initial_project": initial_project, "fresh_project": final_project,
                   "commit": commit["structuredContent"] if commit else None,
                   "task": goal["status"], "regression": regression["status"],
                   "scope": "PASS" if allowed else "NO_SUCCESS_CREDIT", "diagnostics": diagnostics,
                   "original_input_bytes_unchanged": True, "air_published": allowed}
            raw = {"calls": calls, "ledger": ledger, "goal": goal, "regression": regression,
                   "baseline_goal": baseline_goal, "baseline_regression": baseline_regression}
            prior.save(args.output / (route + "-raw.json"), raw)
            row["raw_sha256"] = sha(canonical(raw))
            rows.append(row)
    result = {"disposition": "EXISTING_NATIVE_OCCURRENCE_SCOPE_FEASIBLE", "model_generation_calls": 0,
              "input_token_api_calls": 0, "bundle_sha256": bundle["payload_sha256"],
              "binary_sha256": sha(Path(args.alva).read_bytes()),
              "driver_sha256": sha(Path(__file__).read_bytes()),
              "policy": fixed["policy"], "rows": rows}
    prior.save(args.output / "RESULTS.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("alva", "toolchain", "registry"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
