"""P38 deterministic engineering wave. Public interfaces only, zero models."""
import argparse
import base64
import difflib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_design import feasibility as prior
from benchmarks.p33_shared_scope.reproduce import Client
from benchmarks.native_prospective.service import files
from benchmarks.p38_authorized_effect_contract import mechanisms as m
from integrations.benchmark_runtime_v2.freeze import pack_git, canonical, decode, sha
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK, LinuxSandbox
from integrations.codex.precommit_scope_guard import GuardedNative

REGISTRATION = "4fe0edceae8721f808e750c2dca266417d92ee98"
PREFIX = "benchmarks/p38_authorized_effect_contract/"
TOOLS = tuple(json.loads((ROOT / "benchmarks/p36_mm02_native_model/FREEZE.json").read_text())["native_tools"])


def registered(name):
    return subprocess.check_output(["git", "show", REGISTRATION + ":" + PREFIX + name], cwd=ROOT)


def bundle(case, phase):
    prefix = PREFIX + "fixtures/" + case["id"] + "/" + phase + "/"
    b = pack_git(ROOT, REGISTRATION, [prefix + p for p in case["hashes"][phase]])
    for e in b["payload"]["entries"]:
        e["path"] = e["path"].removeprefix(prefix)
        assert e["sha256"] == case["hashes"][phase][e["path"]]
    b["payload_sha256"] = sha(canonical(b["payload"]))
    return b


def capture(c, case):
    project = c.call("inspect_project")
    module = c.call("inspect_entity", entity=project["modules"]["module:" + case["module"]])
    snap = {"project_revision": project["project_revision"], "modules": {
        case["module"]: {"fields": module["fields"], "entity": module["entity"],
                         "other_slots": {k: v for k, v in module["slots"].items() if k != "functions"},
                         "function_order": case["functions"]}}, "functions": {}}
    graphs = {}
    actual_order = [c.call("inspect_entity", entity=r)["fields"]["name"] for r in module["slots"]["functions"]]
    assert actual_order == case["functions"]
    for short in actual_order:
        name = case["module"] + "." + short
        n = c.call("inspect_entity", entity=name)
        snap["functions"][name] = {"entity": n["entity"], "fields": n["fields"],
            "metadata_slots": {k: v for k, v in n["slots"].items() if k != "body"}, "body": n["slots"]["body"][0]}
        graphs[name] = c.nodes(name)
    return snap, graphs


def roots(snapshot):
    return {f: n["body"] for f, n in snapshot["functions"].items()}


def inspect_source(b, sdk, case, raw):
    with PersistentSandbox(b, b["payload_sha256"], sdk) as box:
        with box.mcp() as native:
            prior.initialize(native)
            c = Client(native, raw)
            c.begin()
            state = capture(c, case)
            c.call("abort_transaction")
            return state


def edit(c, case):
    target = case["authorized_functions"][0]
    parent = c.call("inspect_entity", entity=target)["slots"]["body"][0]
    if case["id"] == "C3":
        child = c.call("create_literal", type="i64", value="2")["revision"]
    else:
        child = c.call("create_reference", name="x")["revision"]
        if case["id"] != "C4":
            two = c.call("create_literal", type="i64", value="2")["revision"]
            child = c.call("create_binary", op="+", left=child, right=two)["revision"]
    c.call("replace_expression", parent=parent, position="step", child=child)


def publish(b, sdk, case, guarded, raw):
    ledger, calls = [], []
    raw.update(ledger=ledger, calls=calls)
    with PersistentSandbox(b, b["payload_sha256"], sdk, wall_seconds=600, rpc_seconds=30) as box:
        original = files(box)
        transport = box.mcp()
        if guarded:
            transport = GuardedNative(transport, case["guard_policy"], TOOLS, ledger.append)
        with transport as native:
            prior.initialize(native)
            schemas = native.request("tools/list")["tools"]
            assert len(schemas) == 20 and {t["name"] for t in schemas} == set(TOOLS)
            c = Client(native, calls)
            c.begin()
            before, before_graph = capture(c, case)
            edit(c, case)
            staged, staged_graph = capture(c, case)
            preview = c.call("preview_semantic_diff")
            check = c.call("check_transaction")
            assert check == {"problems": []}
            assert files(box) == original, "staging published prematurely"
            start = time.perf_counter_ns()
            commit = c.raw("commit_transaction")
            commit_ms = (time.perf_counter_ns() - start) / 1e6
            committed = not commit.get("isError")
            if not committed:
                c.call("abort_transaction")
        # Real new Native process reads AIR authority, not prior process memory.
        with box.mcp() as native:
            prior.initialize(native)
            c = Client(native, calls)
            c.begin()
            fresh, fresh_graph = capture(c, case)
            c.call("abort_transaction")
        authority = files(box)
        dispatches = [e for e in ledger if e["event"] == "native_dispatch" and
                      e.get("params", {}).get("name") == "commit_transaction"]
        fresh_match = roots(fresh) == roots(staged if committed else before)
        if committed:
            fresh_match &= fresh["project_revision"] == commit["structuredContent"]["revision"]
        assert fresh_match
        assert all(authority[p] == data for p, data in original.items())
        raw.update(before=before, staged=staged, fresh=fresh, before_graph=before_graph,
                   staged_graph=staged_graph, fresh_graph=fresh_graph, commit=commit,
                   authority={p: base64.b64encode(data).decode() for p, data in authority.items()})
        return {"before": before, "staged": staged, "fresh": fresh, "preview": preview, "check": check,
            "guard": commit.get("structuredContent", {}).get("host_scope"), "committed": committed,
            "guard_native_commit_dispatches": len(dispatches) if guarded else None,
            "commit": commit.get("structuredContent"), "air_published": "alva-air/current" in authority,
            "fresh_match": bool(fresh_match), "commit_ms": commit_ms,
            "source_projection_unchanged": True}, authority, (before_graph, staged_graph)


def evaluate(source, sdk, case, phase):
    module = case["module"].replace(".", "_")
    tests = "\n#[cfg(test)] mod p38_tests {\n"
    for i, s in enumerate(case["samples"]):
        expected = s["baseline"] if phase == "baseline" else s["required_candidate"]
        tests += (f'#[test] fn sample_{i}() {{ let v = super::{module}::{s["function"]}({s["input"]}); '
                  f'println!("AEC_OBS={i},{{}}", v); assert_eq!(v, {expected}); }}\n')
    tests += "}\n"
    driver = '''import json,pathlib,subprocess
def run(argv):
 p=subprocess.run(argv,capture_output=True,text=True)
 return {"exit":p.returncode,"stdout":p.stdout[-16000:],"stderr":p.stderr[-8000:]}
r={"check":run(["/sdk/alva","project","check","alva.toml","--json"])}
if r["check"]["exit"]:r["status"]="CHECK_FAIL"
else:
 r["build"]=run(["/sdk/alva","project","build","alva.toml","--out-dir","/work/generated"])
 if r["build"]["exit"]:r["status"]="BUILD_FAIL"
 else:
  crate=pathlib.Path("/work/generated")/CRATE
  with (crate/"src/lib.rs").open("a") as f:f.write(ASSERTIONS)
  r["tests"]=run(["/sdk/toolchain/bin/cargo","test","--offline","--manifest-path",str(crate/"Cargo.toml"),"--","--nocapture","--test-threads=1"])
  r["status"]="PASS" if r["tests"]["exit"]==0 else "TEST_FAIL"
print(json.dumps(r))
'''.replace("CRATE", repr(case["crate"])).replace("ASSERTIONS", repr(tests))
    start = time.perf_counter_ns()
    process = LinuxSandbox(sdk, wall_seconds=120, output_limit=131072).run(source, ["/usr/bin/python3", "-I", "-c", driver])
    if process["status"] != "EXECUTED" or process["exit"] != 0:
        raise RuntimeError("independent evaluator infrastructure failure: " + str(process))
    result = json.loads(process["stdout"]["text"])
    import re
    observed = {int(i): int(v) for i, v in re.findall(r"AEC_OBS=(\d+),(-?\d+)", result.get("tests", {}).get("stdout", ""))}
    result.update(observations=[observed.get(i) for i in range(len(case["samples"]))],
                  evaluation_ms=(time.perf_counter_ns() - start) / 1e6)
    return result


def summary_evaluation(r):
    return {k: r[k] for k in ("status", "observations", "evaluation_ms")} | {
        "check_exit": r["check"]["exit"], "build_exit": r.get("build", {}).get("exit"),
        "tests_exit": r.get("tests", {}).get("exit")}


def timed(function):
    start = time.perf_counter_ns()
    result = function()
    return result | {"decision_ms": (time.perf_counter_ns() - start) / 1e6}


def execute(case, sdk, raw):
    started = time.perf_counter_ns()
    original, candidate = bundle(case, "baseline"), bundle(case, "candidate")
    source, replacement = decode(original, original["payload_sha256"]), decode(candidate, candidate["payload_sha256"])
    baseline = evaluate(source, sdk, case, "baseline")
    assert baseline["status"] == "PASS"
    text_evaluation = evaluate(replacement, sdk, case, "candidate")
    raw.update(baseline=baseline, text_evaluation=text_evaluation, text_inspection=[])
    text_state, _ = inspect_source(candidate, sdk, case, raw["text_inspection"])
    raw["quarantine"] = {}
    quarantine, authority, graphs = publish(original, sdk, case, False, raw["quarantine"])
    assert quarantine["committed"] and quarantine["air_published"]
    assert roots(text_state) == roots(quarantine["staged"]), "Text/Native candidates differ"
    native_evaluation = evaluate(authority, sdk, case, "candidate")
    assert native_evaluation["observations"] == text_evaluation["observations"]
    raw["guarded"] = {}
    guarded, final_authority, _ = publish(original, sdk, case, True, raw["guarded"])
    assert roots(guarded["staged"]) == roots(quarantine["staged"]), "Guard replay candidate differs"
    final_evaluation = evaluate(final_authority, sdk, case, "candidate" if guarded["committed"] else "baseline")
    raw.update(native_evaluation=native_evaluation, final_evaluation=final_evaluation)
    footprint = m.structural(quarantine["before"], quarantine["staged"], case["authorized_functions"])
    potential = m.impact(graphs, footprint["changed"])
    expected_values = [s["required_candidate"] for s in case["samples"]]
    observed = native_evaluation["observations"]
    complete = (native_evaluation["status"] in {"PASS", "TEST_FAIL"} and None not in observed and
                native_evaluation["check"]["exit"] == native_evaluation["build"]["exit"] == 0)
    evidence = {"confirmed_failure": complete and observed != expected_values,
                "bound_complete": bool(complete and quarantine["fresh_match"] and guarded["fresh_match"]),
                "semantic_proof": None}
    text_scope = m.source_scope(source["src/model.alva"].decode(), replacement["src/model.alva"].decode(),
                                [f.rsplit(".", 1)[1] for f in case["authorized_functions"]])
    # Strong source baseline binds evidence to its own exact source candidate;
    # it does not require AIR identities, Native publication or D's graph.
    text_complete = (text_evaluation["status"] in {"PASS", "TEST_FAIL"} and
                     None not in text_evaluation["observations"] and
                     text_evaluation["check"]["exit"] == text_evaluation["build"]["exit"] == 0)
    text_evidence = {"confirmed_failure": text_complete and text_evaluation["observations"] != expected_values,
                     "bound_complete": text_complete, "semantic_proof": None}
    decisions = {
        "A": timed(lambda: m.decide(text_scope, text_evidence, case["evidence_strength"], require_strength=True)),
        "B": timed(lambda: m.decide(footprint, evidence, case["evidence_strength"], require_strength=False)),
        "C": {"verdict": {"SCOPE_ALLOWED": "ALLOW", "SCOPE_VIOLATION": "REJECT", "SCOPE_UNVERIFIED": "UNKNOWN"}[guarded["guard"]["status"]],
              "decision_ms": None, "guarded_commit_roundtrip_ms": guarded["commit_ms"], "reason": "actual unchanged P34 decision"},
        "D": timed(lambda: m.decide(footprint, evidence, case["evidence_strength"], require_strength=True,
                                    coverage=potential["complete_for_fixture"]))}
    diff = "".join(difflib.unified_diff(source["src/model.alva"].decode().splitlines(True), replacement["src/model.alva"].decode().splitlines(True), fromfile="baseline", tofile="candidate"))
    raw["text_diff"] = diff
    reachable = {f: set(g) for f, g in graphs[0].items()}
    shared = [{"functions": [a, b], "revisions": sorted(reachable[a] & reachable[b])}
              for a in reachable for b in reachable if a < b and reachable[a] & reachable[b]]
    changed_observations = [{"function": s["function"], "input": s["input"], "baseline": baseline["observations"][i],
        "candidate": observed[i], "required": expected_values[i]} for i, s in enumerate(case["samples"])]
    return {"id": case["id"], "status": "EXECUTED", "bundle_sha256": original["payload_sha256"],
        "candidate_bundle_sha256": candidate["payload_sha256"], "same_candidate_roots": True,
        "structural": footprint, "potential": potential, "shared_reachable_nodes": shared,
        "observations": changed_observations, "evidence": evidence, "text_scope": text_scope,
        "text_diff_sha256": sha(diff.encode()), "baseline": summary_evaluation(baseline),
        "text_candidate": summary_evaluation(text_evaluation), "native_candidate": summary_evaluation(native_evaluation),
        "guarded_authority": summary_evaluation(final_evaluation), "quarantine": quarantine, "guarded": guarded,
        "decisions": decisions, "total_acquisition_and_evaluation_ms": (time.perf_counter_ns() - started) / 1e6}


def main(args):
    if sys.platform != "linux":
        raise RuntimeError("existing P22/P23 Linux isolation required")
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = ["REGISTRATION.md", "AEC-V0-CONTRACT.md", "COUNTEREXAMPLES.json", "oracle.json"]
    frozen += subprocess.check_output(["git", "ls-tree", "-r", "--name-only", REGISTRATION, "--", PREFIX + "fixtures"], cwd=ROOT, text=True).splitlines()
    frozen = [p if p.startswith(PREFIX) else PREFIX + p for p in frozen]
    assert not subprocess.check_output(["git", "diff", REGISTRATION, "--", *frozen], cwd=ROOT)
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    cases = json.loads(registered("COUNTEREXAMPLES.json"))["cases"]
    rows = []
    for case in cases:
        raw = {}
        print("P38 EXECUTE " + case["id"], flush=True)
        try:
            row = execute(case, sdk, raw)
        except Exception as exc:
            raw["error"] = traceback.format_exc()
            row = {"id": case["id"], "status": "BLOCKED", "reason": type(exc).__name__ + ":" + str(exc)[:1200]}
        rows.append(row)
        prior.save(args.output / (case["id"] + "-raw.json"), raw)
        prior.save(args.output / (case["id"] + "-summary.json"), row)
        print("P38_CASE=" + json.dumps(row), flush=True)
    # Oracle is loaded only after mechanisms have decided, for independent scoring.
    oracle = json.loads(registered("oracle.json"))
    score = {}
    for mechanism in "ABCD":
        completed = [r for r in rows if r["status"] == "EXECUTED"]
        score[mechanism] = {
            "mode": "actual_guarded_publication" if mechanism == "C" else "decision_simulation",
            "correct": sum(r["decisions"][mechanism]["verdict"] == oracle[r["id"]]["verdict"] for r in completed),
            "invalid_allows": sum(r["decisions"][mechanism]["verdict"] == "ALLOW" and oracle[r["id"]]["class"] == "invalid" for r in completed),
            "false_rejections": sum(r["decisions"][mechanism]["verdict"] == "REJECT" and oracle[r["id"]]["class"] == "legitimate" for r in completed),
            "unknown": sum(r["decisions"][mechanism]["verdict"] == "UNKNOWN" for r in completed),
            "proof_insufficient_allows": sum(r["decisions"][mechanism]["verdict"] == "ALLOW" and oracle[r["id"]]["class"] == "insufficient_evidence" for r in completed),
            "actual_contract_invalid_publications": sum(r["guarded"]["committed"] and oracle[r["id"]]["class"] == "invalid" for r in completed) if mechanism == "C" else None,
            "actual_publication_count": sum(r["guarded"]["committed"] for r in completed) if mechanism == "C" else None}
    disposition = "INCONCLUSIVE_WITH_LIMITATION" if any(r["status"] != "EXECUTED" for r in rows) else (
        "NO_OBSERVED_INCREMENTAL_VALUE" if all(r["decisions"]["A"]["verdict"] == r["decisions"]["D"]["verdict"] for r in rows) else "PROMISING_INCREMENTAL_VALUE")
    result = {"schema": "p38-wave/v0", "registration": REGISTRATION,
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "harness_sha256": sha(Path(__file__).read_bytes()), "mechanisms_sha256": sha(Path(m.__file__).read_bytes()),
        "platform": platform.platform(), "model_generation_calls": 0, "input_token_api_calls": 0,
        "executed_cases": sum(r["status"] == "EXECUTED" for r in rows), "disposition": disposition,
        "scores": score, "rows": rows}
    prior.save(args.output / "RESULTS.json", result)
    with zipfile.ZipFile(args.output / "RAW.zip", "x", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(args.output.glob("*-raw.json")):
            z.write(p, p.name)
    archive = {"sha256": sha((args.output / "RAW.zip").read_bytes()), "bytes": (args.output / "RAW.zip").stat().st_size}
    prior.save(args.output / "ARCHIVE.json", archive)
    print("P38_RESULT=" + json.dumps(result), flush=True)
    print("P38_ARCHIVE=" + json.dumps(archive), flush=True)
    if result["executed_cases"] != 4:
        sys.exit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--output", required=True, type=Path)
    main(p.parse_args())
