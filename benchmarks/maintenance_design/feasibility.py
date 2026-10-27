"""Maintenance design qualification, not a model runner or general harness.

Windows prepare reads immutable Git blobs. Linux run reuses P22/P23; native
MCP, compiler and generated tests never run at host candidate permissions.
Only sanitized engineering summaries are public; execution logs stay ignored.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git, decode, canonical, sha

BASE = "e78162036c5a373a1a3f1f4644f6149478aac842"
CATALOGUE = HERE / "TASK-CANDIDATES.json"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def prepare():
    candidates = []
    metadata = {
        "MM01": {"type": "record-update-policy", "target": "demo.model.touch_size", "crate": "demo",
            "requirement": "For metadata with negative size, touch_size must return the original metadata unchanged. For nonnegative size retain increment-by-one. Preserve key/etag, size_of, make_meta and application run()==6. Bounded i64 inputs only; overflow policy is unchanged.",
            "risk": ["accidentally altering metadata key/etag", "changing the accessor or application", "overgeneralizing the negative-size rule"],
            "operations": ["create_literal", "create_binary", "create_reference", "create_if", "replace_expression"],
            "functions": ["demo.model.make_meta", "demo.model.size_of", "demo.model.touch_size", "demo.app.run"],
            "stale_probe": "Two transactions share the same initial base; publish the task change, then reject the old transaction's independent application-etag literal edit. Assert complete authority manifest unchanged after refusal. This is an engineering safety probe, not model recovery evidence."},
        "MM02": {"type": "query-parsing-control-flow", "target": "store.xml.parse_prefix", "crate": "store",
            "requirement": "parse_prefix must return the first nonempty URL-decoded prefix value in query order, ignoring later matches and empty decoded values. Preserve missing/empty-query behavior, parse_delimiter's current last-match behavior, XML rendering and response-record functions. Inputs use ordinary ASCII query strings and valid percent escapes; no new decoding policy.",
            "risk": ["global replacement changing parse_delimiter too", "losing percent decoding", "changing XML rendering or response records"],
            "operations": ["create_reference", "create_literal", "create_binary", "create_if", "replace_expression"],
            "functions": ["store.xml.parse_prefix", "store.xml.parse_delimiter", "store.xml.emit_common_prefix", "store.xml.emit_leaf", "store.xml.list_buckets_xml", "store.xml.list_objects_xml", "store.model.text_response", "store.model.xml_response", "store.model.xml_error"],
            "stale_probe": None},
        "MM03": {"type": "cross-module-signature-and-caller", "target": "demo.model.size_of", "crate": "demo",
            "requirement": "Evolve size_of(m) to size_of(m, fallback:i64): return fallback when metadata size is negative, otherwise size. No unary overload required. Update the existing application caller to pass 0 and preserve run()==6. Keep make_meta, touch_size and metadata fields unchanged. Bounded i64 inputs only.",
            "risk": ["caller arity left invalid", "fallback applied to size==0", "changing touch_size instead of size_of"],
            "operations": ["add_param", "add_call_arg", "create_reference", "create_literal", "create_if", "replace_expression"],
            "functions": ["demo.model.make_meta", "demo.model.size_of", "demo.model.touch_size", "demo.app.run"],
            "stale_probe": None},
    }
    adapter_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for ident, spec in metadata.items():
        if ident == "MM02":
            paths = ["examples/store_split/src/model.alva", "examples/store_split/src/xml.alva"]
            bundle = pack_git(ROOT, BASE, paths)
            for entry in bundle["payload"]["entries"]:
                entry["path"] = "src/" + entry["path"].rsplit("/", 1)[1]
            adapter = pack_git(ROOT, adapter_commit, ["benchmarks/maintenance_design/component-store.toml"])
            entry = adapter["payload"]["entries"][0]
            entry["path"] = "alva.toml"
            bundle["payload"]["entries"].append(entry)
            adaptation = "Unchanged store.model/xml source blobs; explicit two-module component manifest. Not the full server/router/storage product."
        else:
            paths = ["tests/project/alva.toml", "tests/project/src/model.alva", "tests/project/src/app.alva"]
            bundle = pack_git(ROOT, BASE, paths)
            for entry in bundle["payload"]["entries"]:
                entry["path"] = entry["path"].removeprefix("tests/project/")
            adaptation = "Exact existing public two-module test project; no answer scaffold or original-source modification."
        bundle["payload_sha256"] = sha(canonical(bundle["payload"]))
        candidates.append({"id": ident, **spec, "source_commit": BASE, "source_paths": paths,
            "source_license": "Repository LICENSE at the source commit", "adaptation": adaptation,
            "public_inputs": sorted(decode(bundle, bundle["payload_sha256"])), "bundle": bundle,
            "non_model_material": ["witnesses.py", "engineering operation sequences", "independent Rust goal/regression assertions", "feasibility output/raw logs"],
            "initial_source_is_full_existing_implementation": True,
            "qualification_source": "FEASIBILITY.json; status not inferred from operation names alone"})
    save(CATALOGUE, {"schema": "alva-maintenance-design/v1", "base": BASE,
        "status": "DESIGN_AND_ZERO_MODEL_QUALIFICATION_ONLY", "model_execution_authorized": False,
        "candidate_selection_before_engineering_execution": [c["id"] for c in candidates],
        "no_substitution_for_unsupported_candidate": True, "candidates": candidates})


class Client:
    def __init__(self, native, operations):
        self.native, self.operations = native, operations
        self.tx = None

    def begin(self):
        self.tx = self.call("begin_transaction", project="/work/project/alva.toml")["transaction_id"]
        return self.tx

    def raw(self, operation, **args):
        if operation != "begin_transaction":
            args = {"transaction_id": self.tx, **args}
        answer = self.native.tool(operation, args)
        self.operations.append({"operation": operation, "is_error": bool(answer.get("isError")), "response_sha256": sha(canonical(answer))})
        return answer

    def call(self, operation, **args):
        answer = self.raw(operation, **args)
        assert not answer.get("isError"), (operation, answer)
        return answer["structuredContent"]

    def nodes(self, function):
        result = {}
        def walk(entity):
            n = self.call("inspect_entity", entity=entity)
            if n["revision"] in result:
                return
            result[n["revision"]] = n
            for children in n["slots"].values():
                for child in children:
                    walk(child)
        walk(function)
        return result

    def bodies(self, functions):
        return {f: sha(self.call("inspect_body", function=f)["body"].encode()) for f in functions}


def initialize(native):
    native.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
        "clientInfo": {"name": "maintenance-engineering-only", "version": "1"}})
    native.notify("notifications/initialized")


def evaluate(box, crate, assertions):
    # Only this separate evaluation process receives host-owned assertions.
    driver = '''import json,pathlib,subprocess
def run(argv):
 p=subprocess.run(argv,capture_output=True,text=True)
 return {"exit":p.returncode,"stdout":p.stdout[-6000:],"stderr":p.stderr[-6000:]}
r={"check":run(["/sdk/alva","project","check","alva.toml","--json"])}
if r["check"]["exit"]:r["status"]="CHECK_FAIL"
else:
 r["build"]=run(["/sdk/alva","project","build","alva.toml","--out-dir","/work/generated"])
 if r["build"]["exit"]:r["status"]="BUILD_FAIL"
 else:
  crate=pathlib.Path("/work/generated")/CRATE
  with (crate/"src/lib.rs").open("a") as f:f.write(ASSERTIONS)
  r["tests"]=run(["/sdk/toolchain/bin/cargo","test","--offline","--manifest-path",str(crate/"Cargo.toml")])
  r["status"]="PASS" if r["tests"]["exit"]==0 else "TEST_FAIL"
print(json.dumps(r))
'''.replace("CRATE", repr(crate)).replace("ASSERTIONS", repr(assertions))
    process = box.run(["/usr/bin/python3", "-I", "-c", driver])
    return json.loads(process["stdout"])


def run(args):
    if sys.platform != "linux":
        raise RuntimeError("UNSUPPORTED: candidate execution requires the existing Linux P22/P23 backend")
    from benchmarks.maintenance_design import witnesses
    from benchmarks.native_prospective.service import files
    from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
    from integrations.benchmark_runtime_v2.sandbox import SDK
    catalogue = json.loads(CATALOGUE.read_text())
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    raw, rows = [], []
    for task in catalogue["candidates"]:
        ident, bundle = task["id"], task["bundle"]
        source = decode(bundle, bundle["payload_sha256"])
        operations = []
        row = {"id": ident, "bundle_sha256": bundle["payload_sha256"], "model_generation_calls": 0}
        print("QUALIFY " + ident, file=sys.stderr, flush=True)
        def workspace():
            return PersistentSandbox(bundle, bundle["payload_sha256"], sdk, wall_seconds=300, rpc_seconds=30)
        try:
            # Baseline behavior and proposed Text edit run in separate namespaces.
            with workspace() as box:
                baseline = evaluate(box, task["crate"], witnesses.regressions(ident))
                unmet = evaluate(box, task["crate"], witnesses.regressions(ident) + witnesses.goals(ident))
                assert baseline["status"] == "PASS", baseline
                assert unmet["status"] == "TEST_FAIL", unmet
            from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox
            changed = witnesses.text_change(ident, source)
            # A task-specific source patch, never an agent candidate or an answer input.
            payload = copy.deepcopy(bundle)
            for entry in payload["payload"]["entries"]:
                data = changed[entry["path"]]
                entry.update(length=len(data), sha256=sha(data), base64=base64.b64encode(data).decode())
            payload["payload_sha256"] = sha(canonical(payload["payload"]))
            with PersistentSandbox(payload, payload["payload_sha256"], sdk, wall_seconds=300) as box:
                text_result = evaluate(box, task["crate"], witnesses.regressions(ident) + witnesses.goals(ident))
                assert text_result["status"] == "PASS", text_result
            row.update(baseline_regression="PASS", baseline_target="EXPECTED_FAIL",
                baseline_failure_basis="new API arity not implemented" if ident == "MM03" else "executed behavioral assertions",
                text="SUPPORTED", text_independent_behavior="PASS",
                text_changed_paths=[p for p in source if source[p] != changed[p]])
            with workspace() as box:
                with box.mcp() as native:
                    initialize(native)
                    schemas = native.request("tools/list")["tools"]
                    names = {t["name"] for t in schemas}
                    row["native_schema_sha256"] = sha(canonical(schemas))
                    c = Client(native, operations)
                    c.begin()
                    before = c.bodies(task["functions"])
                    original = files(box)
                    missing = [op for op in task["operations"] if op not in names]
                    if missing:
                        refusals = [c.raw("describe_operation", name=op) for op in missing]
                        assert all(r.get("isError") and "E_MCP_OPERATION_NOT_EXPOSED" in json.dumps(r) for r in refusals)
                        c.call("abort_transaction")
                        assert files(box) == original
                        row.update(native="UNSUPPORTED_NATIVE_MCP", missing_operations=missing,
                            candidate_local=True, native_authority_unchanged=True)
                    else:
                        for op in task["operations"]:
                            c.call("describe_operation", name=op)
                        stale = None
                        if ident == "MM01":
                            stale = Client(native, operations)
                            stale.begin()
                            app_nodes = stale.nodes("demo.app.run")
                            literal = next(n for n in app_nodes.values() if n["kind"] == "literal" and n["fields"].get("value") == "e1")
                            stale.call("change_field", entity=literal["revision"], field="value", value="concurrent-etag")
                            stale.call("check_transaction")
                        witnesses.mutate_native(ident, c)
                        staged = c.bodies(task["functions"])
                        assert staged[task["target"]] != before[task["target"]]
                        assert all(staged[f] == before[f] for f in before if f != task["target"]), "Non-target body changed"
                        assert files(box) == original, "Staging published program/source before commit"
                        c.call("preview_semantic_diff")
                        checked = c.call("check_transaction")
                        c.call("commit_transaction")
                        published = files(box)
                        if stale:
                            refusal = stale.raw("commit_transaction")
                            assert refusal.get("isError") and "E_AEP_CONFLICT" in json.dumps(refusal), refusal
                            assert files(box) == published
                            stale.call("abort_transaction")
                            row["stale_probe"] = {"result": "E_AEP_CONFLICT", "accepted_stale_write": False,
                                "authority_unchanged_after_refusal": True, "recovery": "NOT_TESTED_LOSER_ABORTED"}
                        assert all(published[p] == source[p] for p in source), "Source projection changed"
                    row["native_operation_counts"] = {op: sum(o["operation"] == op for o in operations) for op in sorted({o["operation"] for o in operations})}
                if not missing:
                    with box.mcp() as fresh:
                        initialize(fresh)
                        reloaded = Client(fresh, operations)
                        reloaded.begin()
                        assert reloaded.bodies(task["functions"]) == staged
                        reloaded.call("abort_transaction")
                    native_result = evaluate(box, task["crate"], witnesses.regressions(ident) + witnesses.goals(ident))
                    assert native_result["status"] == "PASS", native_result
                    row.update(native="SUPPORTED", native_independent_behavior="PASS", effective_target_changed=True,
                        non_target_bodies_unchanged=True, private_staging_no_publication=True,
                        source_projection_unchanged=True, fresh_authority_reread="PASS", native_check_sha256=sha(canonical(checked)))
            raw.append({"id": ident, "baseline": baseline, "unmet": unmet, "text": text_result, "operations": operations})
            row["status"] = "PASS_WITH_CANDIDATE_LOCAL_UNSUPPORTED" if missing else "PASS"
        except Exception as exc:
            row.update(status="FAILED", error=str(exc))
            raw.append({"id": ident, "error": str(exc), "operations": operations})
        rows.append(row)
    # Machine-local raw output is never the public result file.
    save(args.output, raw)
    summary = {"status": "PASS" if all(r["status"].startswith("PASS") for r in rows) else "FAILED",
        "model_generation_calls": 0, "input_token_api_calls": 0, "platform": "linux",
        "authorship": "Codex-assisted engineering witnesses; not model-free development or controlled agent results",
        "catalogue_sha256": sha(CATALOGUE.read_bytes()), "binary_sha256": sha(sdk.alva.read_bytes()),
        "script_sha256": sha(Path(__file__).read_bytes()), "witness_sha256": sha((HERE / "witnesses.py").read_bytes()),
        "raw_evidence_sha256": sha(args.output.read_bytes()), "rows": rows}
    # No stdout/stderr or raw RPC payloads in the public derived summary.
    save(HERE / "FEASIBILITY.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "run"))
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.mode == "prepare":
        prepare()
    else:
        raise SystemExit(run(args))
