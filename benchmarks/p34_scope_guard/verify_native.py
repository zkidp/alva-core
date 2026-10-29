"""CI: four real Linux Native+guard cases, not an AppServer/model-path test."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p34_scope_guard.cases import case, CASES, TOOLS
from benchmarks.maintenance_design import feasibility as prior, witnesses
from benchmarks.native_prospective.service import files
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK
from integrations.codex.precommit_scope_guard import GuardedNative


def main(args):
    if sys.platform != "linux":
        raise RuntimeError("UNSUPPORTED: no host execution fallback")
    args.output.mkdir(parents=True, exist_ok=False)
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    rows = []
    for name in CASES:
        fixed, ledger = case(name), []
        with PersistentSandbox(fixed["bundle"], fixed["bundle"]["payload_sha256"], sdk, wall_seconds=300, rpc_seconds=30) as box:
            with GuardedNative(box.mcp(), fixed["policy"], TOOLS, ledger.append) as n:
                prior.initialize(n)
                c = prior.Client(n, [])
                c.begin()
                before = files(box)
                witnesses.mutate_native(fixed["task"]["id"], c)
                checked = c.call("check_transaction")
                assert checked == {"problems": []}
                result = c.raw("commit_transaction")
                decision = result["structuredContent"]["host_scope"]
                assert decision["status"] == fixed["expected_scope"]
                allowed = decision["status"] == "SCOPE_ALLOWED"
                if not allowed:
                    assert result["isError"] and files(box) == before
                    c.call("abort_transaction")
            with box.mcp() as fresh:
                prior.initialize(fresh)
                r = prior.Client(fresh, [])
                r.begin()
                authority = r.bodies(fixed["task"]["functions"])
                r.call("abort_transaction")
            task = fixed["task"]
            goal = prior.evaluate(box, task["crate"], witnesses.goals(task["id"]))
            regression = prior.evaluate(box, task["crate"], witnesses.regressions(task["id"]))
            assert regression["status"] == "PASS"
            assert goal["status"] == ("PASS" if allowed else "TEST_FAIL")
            dispatch = [e for e in ledger if e["event"] == "native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
            assert len(dispatch) == int(allowed)
            rows.append({"id": name, "decision": decision, "actual_native_commits": len(dispatch),
                "authority": authority, "target": goal["status"], "regression": regression["status"]})
        prior.save(args.output / (name + ".json"), {"ledger": ledger, "goal": goal, "regression": regression})
    prior.save(args.output / "SUMMARY.json", {"status": "PASS", "model_generation_calls": 0,
        "model_approval_path": "NOT_EXERCISED_IN_CI; separate local AppServer evidence", "rows": rows})
    print("P34 Linux Native guard cases PASS; model calls=0")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
