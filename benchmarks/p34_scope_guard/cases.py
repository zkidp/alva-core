"""Trusted fixed-component authorization, never loaded from model arguments."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = tuple(json.loads((ROOT / "benchmarks/mm01_pilot/FREEZE.json").read_text())["native_tools"])
CASES = ("MM02_SHARED", "MM02_NONSHARED", "MM01_VALID", "UNKNOWN_COVERAGE")


def case(name):
    from benchmarks.p33_shared_scope.reproduce import control_source, bundle_with_source
    from integrations.benchmark_runtime_v2.freeze import decode
    task_id = "MM02" if name.startswith("MM02") else "MM01"
    if name not in CASES:
        raise ValueError("Unknown fixed case")
    tasks = json.loads((ROOT / "benchmarks/maintenance_design/TASK-CANDIDATES.json").read_text())
    task = next(c for c in tasks["candidates"] if c["id"] == task_id)
    if task_id == "MM02":
        modules = {"store.model": {"functions": ["text_response", "xml_response", "xml_error"], "types": ["HttpRequest", "RouteResult"]},
            "store.xml": {"functions": ["parse_prefix", "parse_delimiter", "emit_common_prefix", "emit_leaf", "list_buckets_xml", "list_objects_xml"], "types": []}}
    else:
        modules = {"demo.model": {"functions": ["make_meta", "size_of", "touch_size"], "types": ["Meta"]},
                   "demo.app": {"functions": ["run"], "types": []}}
    policy = {"schema": "fixed-component-body-scope/v1", "authorized_functions": [task["target"]], "modules": modules}
    bundle = copy.deepcopy(task["bundle"])
    if name == "MM02_NONSHARED":
        bundle = bundle_with_source(bundle, control_source(decode(bundle, bundle["payload_sha256"])))
    if name == "UNKNOWN_COVERAGE":
        # Explicit trusted-host fault injection; no fixture or Core changes.
        policy["modules"]["demo.model"]["functions"].remove("size_of")
    return {"id": name, "task": task, "bundle": bundle, "policy": policy,
        "expected_scope": "SCOPE_VIOLATION" if name == "MM02_SHARED" else "SCOPE_UNVERIFIED" if name == "UNKNOWN_COVERAGE" else "SCOPE_ALLOWED"}
