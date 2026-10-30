"""Build the prospective manifest from exact Git blobs; no candidate execution."""
import base64
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git, decode, canonical, sha
from benchmarks.maintenance_design.feasibility import save

HERE = Path(__file__).parent
BASE = "6d5eab29e801415be1054e02ef6cf2335a3c091b"
SPECS = [
    ("MM04", "topo_order", "graph-order-completeness", "Return Err when any package cannot be ordered because of a cycle or an unresolved dependency; never return a successful partial order. Keep the existing deterministic dependency-before-dependent, lexicographic same-wave ordering for valid unique-name graphs, including empty input.",
     "topo_order currently returns Ok of the accumulated (possibly partial) order", "cycles and dangling edges; valid ordering and unrelated graph helpers must survive", "existing if/binary/call/result construction and body reconnection expected sufficient", "error/success boundary over a graph algorithm, not MM01 record update or MM02 query parsing"),
    ("MM05", "needs_build", "cache-state-invariant", "Only BUILT or CACHED package states may reuse matching source/dependency hashes. PENDING or FAILED must require a build even when hashes match. Preserve rebuilds caused by changed source, changed dependency output, missing dependency or missing recorded output.",
     "needs_build considers hashes/dependencies but ignores prior build state", "cache reuse of failed/pending output; preserve dependency-sensitive behavior", "existing field construction, public state_label call, boolean construction and body replacement expected sufficient", "enum-state cache invalidation through existing helper/data flow; no arithmetic record update"),
    ("MM06", "reverse_dependents", "stable-collection-deduplication", "Return each matching package name once, in first matching input occurrence order, even when merged package inputs contain duplicate names. Preserve direct-dependency-only matching, nonmatches and empty-input behavior. Inputs need not have unique package names for this query.",
     "reverse_dependents appends every matching package record's name", "duplicates in merged listings; preserve stable order and exclude transitive/nonmatching entries", "existing vec_contains call and conditional reconnection expected sufficient", "stable aggregation with duplicate-name input, not first-nonempty parser selection"),
    ("MM07", "xml_error", "xml-text-encoding", "Escape &, < and > as XML text in both code and message before serializing an error response. Treat existing entity-looking text literally (escape its ampersand once). Preserve status, XML response content type, empty and Unicode text, and all ordinary response helpers. Do not change signatures or introduce another public function.",
     "xml_error concatenates unescaped code/message into XML", "ampersand ordering/double handling, malformed XML text and accidental response-helper edits", "existing split/join calls, literal construction and operand reconnection expected sufficient", "format/encoding invariant through a response helper, not MM01 or MM02")]


def main():
    candidates, bundles = [], {}
    license_blob = pack_git(ROOT, BASE, ["LICENSE"])["payload"]["entries"][0]
    for ident, target, kind, requirement, baseline, risk, expected, difference in SPECS:
        build = ident != "MM07"
        path = "examples/build_system/src/model.alva" if build else "examples/store_split/src/model.alva"
        module, crate = ("build.model", "buildq") if build else ("store.model", "response")
        bundle = pack_git(ROOT, BASE, [path])
        bundle["payload"]["entries"][0]["path"] = "src/model.alva"
        source = decode({**bundle, "payload_sha256": sha(canonical(bundle["payload"]))}, sha(canonical(bundle["payload"])))
        text = source["src/model.alva"].decode()
        manifest_name = "component-build.toml" if build else "component-response.toml"
        data = (HERE / manifest_name).read_bytes()
        bundle["payload"]["entries"].append({"path": "alva.toml", "length": len(data), "sha256": sha(data),
            "base64": base64.b64encode(data).decode(), "origin": {"kind": "p37_explicit_component_manifest", "path": manifest_name}})
        bundle["payload_sha256"] = sha(canonical(bundle["payload"]))
        inventory = {module: {"functions": re.findall(r"^  \(fn ([\w_]+)", text, re.M),
                              "types": re.findall(r"^  \(type ([\w_]+)", text, re.M)}}
        function = module + "." + target
        task = {"id": ident, "target": function, "requirement": requirement,
                "authorized_functions": [function], "editable_files": ["src/model.alva"],
                "protected": ["alva.toml", "all other declarations, signatures, types, exports and module structure"],
                "non_target_behavior": "Preserve all other functions and the original ordinary behavior declared in the requirement."}
        save(HERE / "public" / ident / "task.json", task)
        candidates.append({**task, "task_type": kind, "source_commit": BASE, "source_path": path,
            "license": {"spdx": "Apache-2.0", "git_blob": license_blob["origin"]["oid"], "sha256": license_blob["sha256"]},
            "bundle_sha256": bundle["payload_sha256"], "crate": crate,
            "component_adaptation": "New single-module manifest; entire original source module unchanged, not full application",
            "baseline_behavior": baseline, "maintenance_risks": risk, "native_hypothesis": expected,
            "text_hypothesis": "Body-only source edit expected sufficient; must be executed and independently evaluated",
            "difference_from_MM01_MM02": difference,
            "evaluation_plan": "trusted assertions.py; baseline regression PASS / goal runtime TEST_FAIL; independent generated Rust tests after check/build; all non-authorized body roots and metadata unchanged",
            "guard_policy": {"schema": "fixed-component-body-scope/v1", "authorized_functions": [function], "modules": inventory},
            "registration_disposition": "REGISTERED_NOT_YET_QUALIFIED", "model_result": "NOT_STARTED"})
        bundles[ident] = bundle
    doc_paths = ["alva/README.md"] + ["integrations/skills/alva/" + p for p in
        ("SKILL.md", "references/workflow.md", "references/diagnostics.md", "references/examples.md")]
    save(HERE / "APPROVED-DOCS.json", pack_git(ROOT, BASE, doc_paths))
    save(HERE / "TASK-BUNDLES.json", bundles)
    save(HERE / "CANDIDATE-REGISTRY.json", {"schema": "alva-p37-prospective/v1", "base": BASE,
        "selection_order": [c["id"] for c in candidates], "registered_count": len(candidates),
        "authorship": "Codex-authored deterministic engineering; no independent human review claimed",
        "model_generation_calls": 0, "input_token_api_calls": 0, "candidates": candidates})
    print("Registered 4 prospective definitions; no witnesses executed")


if __name__ == "__main__":
    main()
