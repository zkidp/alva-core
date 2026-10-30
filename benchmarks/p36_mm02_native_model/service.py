"""Actual P34 mediator and P22/P23 Linux owner, with private read-only observer."""
import argparse
import itertools
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import service as old
from benchmarks.maintenance_design import feasibility, witnesses
from benchmarks.p34_scope_guard.cases import case, TOOLS
from benchmarks.p28_optional_descriptor.observer import ObservedNative
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox
from integrations.codex.precommit_scope_guard import GuardedNative


def serve(path):
    cfg = json.loads(path.read_text())
    fixed = case("MM02_SHARED")
    assert cfg["bundle"] == fixed["bundle"] and cfg["policy"] == fixed["policy"]
    functions = fixed["task"]["functions"]
    def sink(name, row):
        with Path(cfg[name]).open("a", encoding="utf-8") as out:
            out.write(json.dumps(row) + "\n")
    sessions = itertools.count()
    class Observer(ObservedNative):
        def capture(self, tx, call_id, operation, baseline=False):
            started = time.monotonic_ns()
            roots = {}
            for function in functions:
                result = self.inner.tool("inspect_entity", {"transaction_id": tx, "entity": function})
                if result.get("isError"):
                    raise RuntimeError("OBSERVER_BODY_UNAVAILABLE")
                roots[function] = result["structuredContent"]["slots"]["body"][0]
            if baseline:
                self.baselines[tx] = roots
            self.sink({"call_id": call_id, "transaction_id": tx, "after_operation": operation,
                       "baseline": baseline, "body_revisions": roots,
                       "changed_functions": [f for f in roots if roots[f] != self.baselines[tx][f]],
                       "elapsed_ns": time.monotonic_ns() - started, "observer_calls": len(functions)})
    class Box(PersistentSandbox):
        def mcp(self):
            session = next(sessions)
            guard = GuardedNative(super().mcp(), fixed["policy"], TOOLS,
                                  lambda row: sink("guard_evidence", dict(row, session=session)))
            return Observer(guard, lambda row: sink("observer_evidence", dict(row, session=session)))
    def authority(box):
        with box.mcp() as native:
            feasibility.initialize(native)
            c = feasibility.Client(native, [])
            begun = c.call("begin_transaction", project="/work/project/alva.toml")
            c.tx = begun["transaction_id"]
            roots = {f: c.call("inspect_entity", entity=f)["slots"]["body"][0] for f in functions}
            c.call("abort_transaction")
            return {"project_revision": begun["project_revision"], "bodies": roots}
    def evaluate(snapshot, sdk, _vectors, check_only=False):
        class Evaluation:
            def run(self, argv):
                r = LinuxSandbox(sdk, wall_seconds=120, output_limit=131072).run(snapshot, argv)
                if r["status"] != "EXECUTED" or r["exit"] != 0:
                    raise RuntimeError("ISOLATED_EVALUATOR_FAILURE:" + str(r))
                return {"stdout": r["stdout"]["text"]}
        if check_only:
            command = '''import subprocess,json
p=subprocess.run(["/sdk/alva","project","check","alva.toml","--json"],capture_output=True,text=True)
print(json.dumps({"status":"PASS" if p.returncode==0 else "COMPILE_FAIL","check":{"exit":p.returncode,"stdout":p.stdout,"stderr":p.stderr}}))'''
            return json.loads(Evaluation().run(["/usr/bin/python3", "-I", "-c", command])["stdout"])
        task = fixed["task"]
        regression = feasibility.evaluate(Evaluation(), task["crate"], witnesses.regressions("MM02"))
        goal = feasibility.evaluate(Evaluation(), task["crate"], witnesses.goals("MM02"))
        return {"status": "PASS" if goal["status"] == regression["status"] == "PASS" else "TEST_FAIL",
                "check": regression["check"], "build": regression.get("build"),
                "regression": regression, "goal": goal}
    with patch.object(old, "PersistentSandbox", Box), patch.object(old, "inspect_authority", authority), \
         patch.object(old, "evaluate", evaluate):
        old.serve(path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--role", choices=("server", "mcp", "control"), default="mcp")
    a = p.parse_args()
    if a.role == "server":
        serve(a.config)
    elif a.role == "mcp":
        old.relay(a.config, "mcp")
    else:
        request = json.loads(sys.stdin.read(1024**2))
        print(json.dumps(old.control(a.config, request["action"], request["arguments"])))
