"""Opt-in trusted P26 service adapter: every native session is guarded.

No alternate agent-callable commit endpoint; raw native instances and the
control socket remain solely in the trusted process, outside candidate mounts.
"""
import argparse
import json
import itertools
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import service as old
from benchmarks.maintenance_design import feasibility, witnesses
from benchmarks.p34_scope_guard.cases import case, TOOLS
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox
from integrations.codex.precommit_scope_guard import GuardedNative


def serve(path):
    cfg = json.loads(path.read_text())
    fixed = case(cfg["case"])
    assert cfg["bundle"] == fixed["bundle"]  # trusted configuration only
    def sink(row):
        with Path(cfg["guard_evidence"]).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    sessions = itertools.count()
    class Box(PersistentSandbox):
        def mcp(self):
            session = next(sessions)
            return GuardedNative(super().mcp(), fixed["policy"], TOOLS,
                lambda row: sink(dict(row, scope_session_id=session)))
    def authority(box):
        with box.mcp() as n:
            feasibility.initialize(n)
            c = feasibility.Client(n, [])
            begin = c.call("begin_transaction", project="/work/project/alva.toml")
            c.tx = begin["transaction_id"]
            bodies = c.bodies(fixed["task"]["functions"])
            c.call("abort_transaction")
            return {"project_revision": begin["project_revision"], "bodies": bodies}
    def evaluate(snapshot, sdk, _vectors, check_only=False):
        class Evaluation:
            def run(self, argv):
                result = LinuxSandbox(sdk, wall_seconds=120, output_limit=131072).run(snapshot, argv)
                if result["status"] != "EXECUTED" or result["exit"] != 0:
                    raise RuntimeError("ISOLATED_EVALUATOR_FAILURE:" + str(result))
                return {"stdout": result["stdout"]["text"]}
        if check_only:
            command = '''import subprocess,json
p=subprocess.run(["/sdk/alva","project","check","alva.toml","--json"],capture_output=True,text=True)
print(json.dumps({"status":"PASS" if p.returncode==0 else "COMPILE_FAIL","check":{"exit":p.returncode,"stdout":p.stdout,"stderr":p.stderr}}))'''
            return json.loads(Evaluation().run(["/usr/bin/python3", "-I", "-c", command])["stdout"])
        task = fixed["task"]
        regression = feasibility.evaluate(Evaluation(), task["crate"], witnesses.regressions(task["id"]))
        goal = feasibility.evaluate(Evaluation(), task["crate"], witnesses.goals(task["id"]))
        return {"status": "PASS" if goal["status"] == regression["status"] == "PASS" else "TEST_FAIL",
                "check": regression["check"], "build": regression.get("build"), "regression": regression, "goal": goal}
    with patch.object(old, "PersistentSandbox", Box), patch.object(old, "inspect_authority", authority), patch.object(old, "evaluate", evaluate):
        old.serve(path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--role", choices=("server", "mcp", "control"), default="mcp")
    args = p.parse_args()
    if args.role == "server":
        serve(args.config)
    elif args.role == "mcp":
        old.relay(args.config, "mcp")
    else:
        request = json.loads(sys.stdin.read(1024**2))
        print(json.dumps(old.control(args.config, request["action"], request["arguments"])))
