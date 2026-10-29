"""P29 MM02 replay plus one declared alpha-renaming mechanism control.

No model, no Core edits, no historical output writes. All MCP/compiler/generated
code execution uses the existing P22/P23 Linux namespace backend. Raw engineering
records go only to the caller's local output; public output is derived evidence.
"""
import argparse
import base64
import copy
import json
import re
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_design import feasibility as prior, witnesses
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha

SHARED = "33ecf18b03c1348dd59bf91c15f66a73d06cba29dd757254c4e7917ed96beb5f"
TARGET, OTHER = "store.xml.parse_prefix", "store.xml.parse_delimiter"
HERE = Path(__file__).resolve().parent


def control_source(source):
    """Rename only delimiter's bound accumulator and its sole reference."""
    result = dict(source)
    text = source["src/xml.alva"].decode()
    start, end = text.index("  (fn parse_delimiter"), text.index("  (fn emit_common_prefix")
    middle = text[start:end]
    assert middle.count("(acc found ") == middle.count("(ref found)") == 1
    middle = middle.replace("(acc found ", "(acc delimiter_found ").replace("(ref found)", "(ref delimiter_found)")
    result["src/xml.alva"] = (text[:start] + middle + text[end:]).encode()
    return result


def bundle_with_source(bundle, source):
    result = copy.deepcopy(bundle)
    for entry in result["payload"]["entries"]:
        data = source[entry["path"]]
        entry.update(length=len(data), sha256=sha(data), base64=base64.b64encode(data).decode())
    result["payload_sha256"] = sha(canonical(result["payload"]))
    return result


def if_revision(node):
    """Small audit of the existing ALVANODE1 encoding for this fieldless if.

    Not a language analyzer: compare the exact runtime node with air.rs's
    canonical_node encoding (little-endian lengths; sorted slots; child hashes).
    """
    assert node["kind"] == "if" and not node["fields"]
    def string(text):
        value = text.encode()
        return struct.pack("<I", len(value)) + value
    data = b"ALVANODE1" + string("if") + struct.pack("<I", 0) + struct.pack("<I", len(node["slots"]))
    for slot, children in sorted(node["slots"].items()):
        data += string(slot) + struct.pack("<I", len(children))
        data += b"".join(bytes.fromhex(child) for child in children)
    return sha(data)


def path_to(nodes, function, target):
    name = function.rsplit(".", 1)[1]
    roots = [n for n in nodes.values() if n["kind"] == "function" and n["fields"].get("name") == name]
    assert len(roots) == 1
    def walk(rev, trail, visited):
        if rev == target:
            return trail
        if rev in visited:
            return None
        for slot, children in sorted(nodes[rev]["slots"].items()):
            for i, child in enumerate(children):
                result = walk(child, trail + [{"parent": rev, "slot": slot, "index": i, "child": child}], visited | {rev})
                if result is not None:
                    return result
        return None
    return walk(roots[0]["revision"], [], set())


class Client(prior.Client):
    def __init__(self, native, raw):
        super().__init__(native, [])
        self.raw_records = raw

    def raw(self, operation, **args):
        params = args if operation == "begin_transaction" else {"transaction_id": self.tx, **args}
        response = self.native.tool(operation, params)
        self.raw_records.append({"operation": operation, "arguments": params, "response": response})
        return response


def behavior(box, task):
    regression = prior.evaluate(box, task["crate"], witnesses.regressions("MM02"))
    goal = prior.evaluate(box, task["crate"], witnesses.goals("MM02"))
    # Separate observation, not an altered P29 assertion or substitute evaluator.
    observation = prior.evaluate(box, task["crate"], '''
#[cfg(test)] mod p33_observation {
 use super::store_xml;
 #[test] fn actual_delimiter(){println!("P33_DELIMITER={:?}",store_xml::parse_delimiter("delimiter=%2F&delimiter=%21".into()));}
}
'''.replace('println!', 'eprintln!'))
    # Same-crate observer: generated modules are private, so an external binary
    # cannot import them. Do not change their visibility or candidate sources.
    driver = '''import subprocess,json
p=subprocess.run(["/sdk/toolchain/bin/cargo","test","--offline","--manifest-path","/work/generated/store/Cargo.toml","--lib","p33_observation::","--","--nocapture"],capture_output=True,text=True)
print(json.dumps({"exit":p.returncode,"stdout":p.stdout,"stderr":p.stderr[-6000:]}))
'''
    observed = json.loads(box.run(["/usr/bin/python3", "-I", "-c", driver])["stdout"])
    assert observed["exit"] == 0, observed
    hits = re.findall(r'P33_DELIMITER=("[^"\n]*")', observed["stderr"])
    assert len(hits) == 1, observed
    observed["value"] = json.loads(hits[0])
    return {"regression": regression, "target": goal, "observation": observation, "delimiter": observed}


def public_behavior(raw):
    return {"check": raw["regression"]["check"]["exit"], "build": raw["regression"]["build"]["exit"],
        "regression": raw["regression"]["status"], "target": raw["target"]["status"],
        "delimiter": {"input": "delimiter=%2F&delimiter=%21", "expected": "!", "observed": raw["delimiter"]["value"]},
        "regression_diagnostic_sha256": sha(raw["regression"]["tests"]["stdout"].encode())}


def reproduce(args):
    if sys.platform != "linux":
        raise RuntimeError("UNSUPPORTED: Linux P22/P23 required; no host fallback")
    from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
    from integrations.benchmark_runtime_v2.sandbox import SDK
    from benchmarks.native_prospective.service import files
    task = next(t for t in json.loads(prior.CATALOGUE.read_text())["candidates"] if t["id"] == "MM02")
    source = decode(task["bundle"], task["bundle"]["payload_sha256"])
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    args.output.mkdir(parents=True, exist_ok=False)
    raw, result = {}, {}
    workspace = lambda bundle: PersistentSandbox(bundle, bundle["payload_sha256"], sdk, wall_seconds=300, rpc_seconds=30)
    # Original Text witness, not a new solution or a changed historical score.
    text = witnesses.text_change("MM02", source)
    with workspace(bundle_with_source(task["bundle"], text)) as box:
        raw["text"] = behavior(box, task)
        result["text"] = public_behavior(raw["text"])
    for label, inputs in (("MM02_original", source), ("nonshared_alpha_control", control_source(source))):
        print("REPLAY " + label, flush=True)
        row, records = {}, []
        raw[label] = {"calls": records}
        with workspace(bundle_with_source(task["bundle"], inputs)) as box:
            baseline = behavior(box, task)
            raw[label]["baseline"] = baseline
            row["baseline"] = public_behavior(baseline)
            with box.mcp() as native:
                prior.initialize(native)
                c = Client(native, records)
                begin = c.call("begin_transaction", project="/work/project/alva.toml")
                c.tx = begin["transaction_id"]
                before_graph = {f: c.nodes(f) for f in (TARGET, OTHER)}
                before = c.bodies(task["functions"])
                original = files(box)
                for op in task["operations"]:
                    c.call("describe_operation", name=op)
                attachment = witnesses.mutate_native("MM02", c)
                parent = attachment["attachment_parent_revision"]
                selected = before_graph[TARGET][parent]
                assert if_revision(selected) == parent
                paths = {f: path_to(before_graph[f], f, parent) for f in (TARGET, OTHER)}
                row["sharing"] = {"parent": selected, "canonical_content_hash_recomputed": parent,
                    "paths_from_function_roots": paths, "parent_reachable_from_both": all(v is not None for v in paths.values()),
                    "same_node_content_from_both_inspections": before_graph[OTHER].get(parent) == selected}
                staged = c.bodies(task["functions"])
                staged_graph = {f: c.nodes(f) for f in (TARGET, OTHER)}
                preview = c.call("preview_semantic_diff")
                checked = c.call("check_transaction")
                assert files(box) == original
                commit = c.call("commit_transaction")
                published = files(box)
                row.update(before_body_hashes=before, staged_body_hashes=staged,
                    changed_functions=[f for f in before if before[f] != staged[f]],
                    preview=preview, check=checked, commit=commit,
                    private_staging_no_publication=True, source_projection_unchanged=all(published[p] == inputs[p] for p in inputs))
                raw[label].update(initial_graphs=before_graph, staged_graphs=staged_graph,
                    final_files={p: base64.b64encode(data).decode() for p, data in published.items()})
            with box.mcp() as fresh:
                prior.initialize(fresh)
                reloaded = Client(fresh, records)
                loaded = reloaded.call("begin_transaction", project="/work/project/alva.toml")
                reloaded.tx = loaded["transaction_id"]
                reread = reloaded.bodies(task["functions"])
                reloaded.call("abort_transaction")
                row["fresh_authority"] = {"revision": loaded["project_revision"], "body_hashes": reread,
                    "matches_commit": loaded["project_revision"] == commit["revision"], "matches_staging": reread == staged}
            final = behavior(box, task)
            raw[label]["final"] = final
            row["final"] = public_behavior(final)
        result[label] = row
    prior.save(args.output / "raw.json", raw)
    manifest_names = ["benchmarks/maintenance_design/TASK-CANDIDATES.json", "benchmarks/maintenance_design/FEASIBILITY.json", "benchmarks/maintenance_design/witnesses.py", "benchmarks/maintenance_design/feasibility.py",
        "alva/src/air.rs", "alva/src/main.rs", "alva/src/project.rs", "alva/src/mcp.rs", "alva/src/aep.rs"]
    summary = {"schema": "alva-p33-shared-scope/v1", "base": "da393659ce5336d6927bfc0a29fb49a94be5d539",
        "authorship": "Codex-assisted deterministic engineering; no controlled agent-effect experiment",
        "model_generation_calls": 0, "input_token_calls": 0,
        "bundle_sha256": task["bundle"]["payload_sha256"], "binary_sha256": sha(sdk.alva.read_bytes()),
        "driver_sha256": sha(Path(__file__).read_bytes()), "input_code_sha256": {n: sha((ROOT / n).read_bytes()) for n in manifest_names},
        "raw_sha256": sha((args.output / "raw.json").read_bytes()), "rows": result}
    prior.save(args.output / "RESULTS.json", summary)
    validate(summary)
    print("P33 REPRODUCTION PASS; original scope failure retained; model generation calls=0", flush=True)


def validate(s):
    rows = s["rows"]
    assert s["model_generation_calls"] == s["input_token_calls"] == 0
    assert rows["text"]["regression"] == rows["text"]["target"] == "PASS"
    for name in ("MM02_original", "nonshared_alpha_control"):
        r = rows[name]
        assert r["baseline"]["regression"] == "PASS" and r["baseline"]["target"] == "TEST_FAIL"
        assert r["baseline"]["delimiter"]["observed"] == "!"
        assert r["check"] == {"problems": []}
        assert r["private_staging_no_publication"] and r["source_projection_unchanged"]
        assert r["fresh_authority"]["matches_commit"] and r["fresh_authority"]["matches_staging"]
        assert r["final"]["check"] == r["final"]["build"] == 0 and r["final"]["target"] == "PASS"
        actual = set(r["changed_functions"])
        advertised = {line.removeprefix("CHANGED function ") for line in r["preview"]["diff"].splitlines() if line.startswith("CHANGED function ")}
        assert actual == advertised, (actual, advertised)
    original = rows["MM02_original"]
    assert original["sharing"]["parent"]["revision"] == SHARED
    assert original["sharing"]["parent_reachable_from_both"]
    assert original["sharing"]["same_node_content_from_both_inspections"]
    assert original["changed_functions"] == [TARGET, OTHER]
    assert original["final"]["regression"] == "TEST_FAIL" and original["final"]["delimiter"]["observed"] == "/"
    control = rows["nonshared_alpha_control"]
    assert not control["sharing"]["parent_reachable_from_both"]
    assert control["changed_functions"] == [TARGET]
    assert control["final"]["regression"] == "PASS" and control["final"]["delimiter"]["observed"] == "!"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--output", type=Path, required=True)
    reproduce(p.parse_args())
