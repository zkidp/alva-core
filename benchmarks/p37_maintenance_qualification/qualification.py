"""Prospectively registered wave; actual public Native, P34 Guard, P22/P23 only."""
import argparse
import base64
import copy
import json
from pathlib import Path
import platform
import subprocess
import sys
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_design import feasibility as prior
from benchmarks.p33_shared_scope.reproduce import Client
from benchmarks.p37_maintenance_qualification import assertions, witnesses
from benchmarks.native_prospective.service import files
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK, LinuxSandbox
from integrations.codex.precommit_scope_guard import GuardedNative

HERE = Path(__file__).parent
REGISTRATION = "e800c8808beb6c333e61d23e84119a4bcb6ec747"
TOOLS = tuple(json.loads((ROOT / "benchmarks/p36_mm02_native_model/FREEZE.json").read_text())["native_tools"])


def evaluate(snapshot, sdk, crate, tests):
    class Evaluation:
        def run(self, argv):
            r = LinuxSandbox(sdk, wall_seconds=120, output_limit=131072).run(snapshot, argv)
            if r["status"] != "EXECUTED" or r["exit"] != 0:
                raise RuntimeError("ISOLATED_EVALUATOR_FAILURE:" + str(r))
            return {"stdout": r["stdout"]["text"]}
    return prior.evaluate(Evaluation(), crate, tests)


def snapshot(box, candidate, ledger):
    with GuardedNative(box.mcp(), candidate["guard_policy"], TOOLS, ledger.append) as native:
        prior.initialize(native)
        c = Client(native, [])
        c.begin()
        baseline = next(e["snapshot"] for e in reversed(ledger) if e["event"] == "trusted_baseline")
        c.call("abort_transaction")
        return baseline


def scope(before, after, authorized):
    if "error" in before or "error" in after:
        return "UNKNOWN"
    if before["modules"] != after["modules"] or set(before["functions"]) != set(after["functions"]):
        return "FAIL"
    changed = []
    for f, original in before["functions"].items():
        final = after["functions"][f]
        if {k: v for k, v in original.items() if k != "body"} != {k: v for k, v in final.items() if k != "body"}:
            return "FAIL"
        if original["body"] != final["body"]:
            changed.append(f)
    return "PASS" if set(changed) == set(authorized) else "FAIL"


def changed_bundle(bundle, source):
    result = copy.deepcopy(bundle)
    for entry in result["payload"]["entries"]:
        data = source[entry["path"]]
        entry.update(length=len(data), sha256=sha(data), base64=base64.b64encode(data).decode())
    result["payload_sha256"] = sha(canonical(result["payload"]))
    return result


def qualify(candidate, bundle, sdk, raw):
    source = decode(bundle, candidate["bundle_sha256"])
    row = {"id": candidate["id"], "task_type": candidate["task_type"], "bundle_sha256": candidate["bundle_sha256"]}
    def workspace(b=bundle):
        return PersistentSandbox(b, b["payload_sha256"], sdk, wall_seconds=600, rpc_seconds=30)
    baseline_regression = evaluate(source, sdk, candidate["crate"], assertions.regressions(candidate["id"]))
    baseline_goal = evaluate(source, sdk, candidate["crate"], assertions.goals(candidate["id"]))
    raw.update(baseline_regression=baseline_regression, baseline_goal=baseline_goal)
    row["baseline"] = {"regression": baseline_regression["status"], "goal": baseline_goal["status"],
        "check": baseline_regression["check"]["exit"], "build": baseline_regression.get("build", {}).get("exit"),
        "goal_runtime_assertion_failure": "test result: FAILED" in baseline_goal.get("tests", {}).get("stdout", "")}
    if baseline_regression["status"] != "PASS" or baseline_goal["status"] != "TEST_FAIL" or not row["baseline"]["goal_runtime_assertion_failure"]:
        row.update(disposition="INCONCLUSIVE_WITH_BLOCKER", reason="REGISTERED_BASELINE_EVALUATION_PRECONDITION_NOT_ESTABLISHED")
        return row
    with workspace() as box:
        ledger = []
        initial = snapshot(box, candidate, ledger)
        raw["baseline_inspection"] = ledger
    if "error" in initial:
        row["guard_coverage"] = initial
    changed = witnesses.text_change(candidate, source)
    paths = [p for p in source if source[p] != changed[p]]
    assert paths == ["src/model.alva"] and changed["alva.toml"] == source["alva.toml"]
    text_goal = evaluate(changed, sdk, candidate["crate"], assertions.goals(candidate["id"]))
    text_regression = evaluate(changed, sdk, candidate["crate"], assertions.regressions(candidate["id"]))
    with workspace(changed_bundle(bundle, changed)) as box:
        ledger = []
        text_state = snapshot(box, candidate, ledger)
        raw["text_inspection"] = ledger
    text_scope = scope(initial, text_state, candidate["authorized_functions"])
    row["text"] = {"goal": text_goal["status"], "regression": text_regression["status"], "scope": text_scope,
        "changed_files": paths, "check": text_goal["check"]["exit"], "build": text_goal.get("build", {}).get("exit")}
    raw["text"] = {"source": {p: base64.b64encode(b).decode() for p, b in changed.items()}, "goal": text_goal, "regression": text_regression}
    text_pass = text_goal["status"] == text_regression["status"] == text_scope == "PASS"
    if "error" in initial:
        row.update(disposition="TEXT_ONLY_NATIVE_UNSUPPORTED" if text_pass else "INCONCLUSIVE_WITH_BLOCKER",
                   reason="P34_FIXED_COMPONENT_COVERAGE_UNSUPPORTED")
        return row
    ledger, calls = [], []
    raw.update(native_ledger=ledger, native_calls=calls)
    with workspace() as box:
        original = files(box)
        try:
            with GuardedNative(box.mcp(), candidate["guard_policy"], TOOLS, ledger.append) as native:
                prior.initialize(native)
                schema = native.request("tools/list")["tools"]
                assert {t["name"] for t in schema} == set(TOOLS) and len(schema) == 20
                raw["native_schemas"] = schema
                c = Client(native, calls)
                c.begin()
                before = next(e["snapshot"] for e in reversed(ledger) if e["event"] == "trusted_baseline")
                raw["native_before"] = before
                witnesses.native(candidate, c)
                staged = {f: c.call("inspect_entity", entity=f)["slots"]["body"][0] for f in before["functions"]}
                preview = c.call("preview_semantic_diff")
                check = c.call("check_transaction")
                assert files(box) == original, "Staging unexpectedly published"
                result = c.raw("commit_transaction") if check == {"problems": []} else None
                decision = result.get("structuredContent", {}).get("host_scope") if result else None
                if not result or result.get("isError"):
                    c.call("abort_transaction")
            with box.mcp() as fresh:
                prior.initialize(fresh)
                r = Client(fresh, calls)
                begin = r.call("begin_transaction", project="/work/project/alva.toml")
                r.tx = begin["transaction_id"]
                roots = {f: r.call("inspect_entity", entity=f)["slots"]["body"][0] for f in before["functions"]}
                r.call("abort_transaction")
            authority = files(box)
            with GuardedNative(box.mcp(), candidate["guard_policy"], TOOLS, ledger.append) as inspected:
                prior.initialize(inspected)
                final_client = Client(inspected, calls)
                final_client.begin()
                final_state = next(e["snapshot"] for e in reversed(ledger) if e["event"] == "trusted_baseline")
                final_client.call("abort_transaction")
            native_scope = scope(before, final_state, candidate["authorized_functions"])
            goal = evaluate(authority, sdk, candidate["crate"], assertions.goals(candidate["id"]))
            regression = evaluate(authority, sdk, candidate["crate"], assertions.regressions(candidate["id"]))
            dispatch = [e for e in ledger if e["event"] == "native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
            committed = bool(result and not result.get("isError"))
            fresh_match = bool(committed and begin["project_revision"] == result["structuredContent"]["revision"] and roots == staged)
            row["native"] = {"schema_sha256": sha(canonical(schema)), "staged_bodies": staged, "initial_bodies": {f: b["body"] for f, b in before["functions"].items()},
                "preview": preview, "check": check, "guard": decision, "actual_commit_dispatches": len(dispatch),
                "commit": result.get("structuredContent") if result else None, "air_published": "alva-air/current" in authority,
                "fresh_project_revision": begin["project_revision"], "fresh_body_revisions": roots, "fresh_matches_commit_and_staging": fresh_match,
                "goal": goal["status"], "regression": regression["status"], "scope": native_scope,
                "source_projection_unchanged": all(authority[p] == b for p, b in source.items()),
                "independent_check": goal["check"]["exit"], "independent_build": goal.get("build", {}).get("exit")}
            raw["native_final"] = {"goal": goal, "regression": regression,
                "files": {p: base64.b64encode(b).decode() for p, b in authority.items()}}
            native_pass = bool(fresh_match and len(dispatch) == 1 and decision["status"] == "SCOPE_ALLOWED" and
                goal["status"] == regression["status"] == native_scope == "PASS" and row["native"]["source_projection_unchanged"])
            row["disposition"] = "QUALIFIED_MATCHED" if text_pass and native_pass else "CANDIDATE_LOCAL_FAILURE"
            row["reason"] = "both engineering routes independently pass" if row["disposition"] == "QUALIFIED_MATCHED" else "observed witness behavior/check/Guard/scope failure; no universal impossibility claim"
        except AssertionError as exc:
            raw["native_error"] = traceback.format_exc()
            row.update(disposition="CANDIDATE_LOCAL_FAILURE", reason="NATIVE_ENGINEERING_SEQUENCE_ERROR:" + str(exc)[:400])
    return row


def main(args):
    if sys.platform != "linux":
        raise RuntimeError("P22/P23 Linux execution required; no fallback")
    registered = ["CANDIDATE-REGISTRY.json", "TASK-BUNDLES.json", "assertions.py", "SELECTION-PROTOCOL.md"]
    registered += ["public/" + i + "/task.json" for i in ("MM04", "MM05", "MM06", "MM07")]
    for name in registered:
        blob = subprocess.check_output(["git", "show", REGISTRATION + ":benchmarks/p37_maintenance_qualification/" + name], cwd=ROOT)
        assert blob == (HERE / name).read_bytes(), "Registration changed: " + name
    args.output.mkdir(parents=True, exist_ok=False)
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    registry = json.loads((HERE / "CANDIDATE-REGISTRY.json").read_text())
    bundles = json.loads((HERE / "TASK-BUNDLES.json").read_text())
    rows = []
    for candidate in registry["candidates"]:
        raw = {}
        try:
            row = qualify(candidate, bundles[candidate["id"]], sdk, raw)
        except Exception as exc:
            raw["blocker"] = traceback.format_exc()
            row = {"id": candidate["id"], "task_type": candidate["task_type"], "disposition": "INCONCLUSIVE_WITH_BLOCKER",
                   "reason": type(exc).__name__ + ":" + str(exc)[:400]}
        prior.save(args.output / (candidate["id"] + "-raw.json"), raw)
        row["raw_canonical_sha256"] = sha(canonical(raw))
        rows.append(row)
        print(candidate["id"] + " " + row["disposition"], flush=True)
    counts = {key: sum(r["disposition"] == key for r in rows) for key in
        ("QUALIFIED_MATCHED", "TEXT_ONLY_NATIVE_UNSUPPORTED", "NATIVE_ONLY_TEXT_UNSUPPORTED", "CANDIDATE_LOCAL_FAILURE", "INCONCLUSIVE_WITH_BLOCKER", "EXCLUDED_AT_REGISTRATION")}
    result = {"schema": "alva-p37-qualification/v1", "registration_commit": REGISTRATION,
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "registry_sha256": sha((HERE / "CANDIDATE-REGISTRY.json").read_bytes()), "binary_sha256": sha(sdk.alva.read_bytes()),
        "driver_sha256": sha(Path(__file__).read_bytes()), "witness_sha256": sha(Path(witnesses.__file__).read_bytes()),
        "registered_count": len(rows), "disposition_counts": counts, "matched_qualified_count": counts["QUALIFIED_MATCHED"],
        "model_generation_calls": 0, "input_token_api_calls": 0, "future_formal_model_result": "NOT_STARTED",
        "platform": platform.platform(), "rows": rows}
    prior.save(args.output / "QUALIFICATION-RESULTS.json", result)
    with zipfile.ZipFile(args.output / "RAW.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(args.output.glob("*-raw.json")):
            archive.write(p, p.name)
    prior.save(args.output / "ARCHIVE.json", {"sha256": sha((args.output / "RAW.zip").read_bytes()),
        "bytes": (args.output / "RAW.zip").stat().st_size, "raw_records": len(rows), "controlled_raw_only": True})
    # Structured summary is also recoverable from CI logs without publishing raw records.
    print("P37_RESULT=" + json.dumps(result), flush=True)
    print("P37_ARCHIVE=" + (args.output / "ARCHIVE.json").read_text().replace("\n", ""), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("alva", "toolchain", "registry"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
