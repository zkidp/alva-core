"""Trusted MIC task adapter; reuses unchanged P22/P23 isolation and Native MCP."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import service as old
from benchmarks.maintenance_design import feasibility as prior
from integrations.benchmark_runtime_v2.persistent import _Process
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox
from integrations.benchmark_runtime_v2.freeze import canonical, sha
from integrations.codex.precommit_scope_guard import GuardedNative
from benchmarks.maintenance_interface_comparison.linux_profile import install

TOOLS = tuple(json.loads((ROOT / "benchmarks/p36_mm02_native_model/FREEZE.json").read_text())["native_tools"])


def inspect(box, task):
    ledger = []
    raw = box.mcp()
    # Actual unchanged P34 collector, no commit interception/policy asymmetry.
    try:
        with GuardedNative(raw, task["policy"], TOOLS, ledger.append) as native:
            prior.initialize(native)
            c = prior.Client(native, [])
            c.begin()
            result = next(e["snapshot"] for e in ledger if e["event"] == "trusted_baseline")
            c.call("abort_transaction")
            return result
    except Exception:
        print("MCP_STARTUP_STDERR=" + bytes(raw.process.err).decode(errors="replace")[-3000:], file=sys.stderr, flush=True)
        raise


def evaluate(snapshot, sdk, task, check_only=False, baseline=False):
    class Evaluation:
        def run(self, argv):
            result = LinuxSandbox(sdk, wall_seconds=120, output_limit=131072).run(snapshot, argv)
            if result["status"] != "EXECUTED" or result["exit"] != 0:
                raise RuntimeError("ISOLATED_EVALUATOR_FAILURE:" + str(result))
            return {"stdout": result["stdout"]["text"]}
    receipt = sha(canonical({p: sha(b) for p, b in snapshot.items()}))
    if check_only:
        driver = '''import json,subprocess
p=subprocess.run(['/sdk/alva','project','check','alva.toml','--json'],capture_output=True,text=True)
print(json.dumps({'status':'PASS' if p.returncode==0 else 'COMPILE_FAIL','check':{'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}}))'''
        return json.loads(Evaluation().run(["/usr/bin/python3", "-I", "-c", driver])["stdout"]) | {"tested_snapshot_sha256": receipt}
    goal = prior.evaluate(Evaluation(), task["crate"], task["assertions"]["goal"])
    regression = prior.evaluate(Evaluation(), task["crate"], task["assertions"]["regression"])
    status = "PASS" if goal["status"] == regression["status"] == "PASS" else (
        "TEST_FAIL" if goal["status"] in {"PASS", "TEST_FAIL"} and regression["status"] in {"PASS", "TEST_FAIL"} else "COMPILE_FAIL")
    return {"status": status, "check": regression["check"], "goal": goal, "regression": regression,
            "tested_snapshot_sha256": receipt}


def inside_source(paths):
    original = (ROOT / "benchmarks/mm01_pilot/inside.py").read_text()
    original = original.replace('PATHS = ("alva.toml", "src/app.alva", "src/model.alva")', "PATHS = " + repr(tuple(paths)))
    extra = '''    if action == "write":
        if name == "alva.toml": return {"error":"PROTECTED_PATH"}
        changed = args["content"].encode("utf-8")
        if len(changed)>65536:return {"error":"SOURCE_LIMIT"}
        path.write_bytes(changed)
        return {"accepted":True,"revision":revision(),"path":name}
'''
    return original.replace('    if action == "edit":', extra + '    if action == "edit":')


def serve(config_path):
    install()
    cfg = json.loads(config_path.read_text())
    task = cfg["task"]
    class SocketRoot:
        def __init__(self, original):
            self.original = original
        def __truediv__(self, name):
            return Path(cfg["ipc_path"]) if name == "host.sock" else self.original / name
    class Box(PersistentSandbox):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Work/input/temp ownership remain under the exact original root.
            # Only the trusted IPC socket uses a short unique host path.
            self.root = SocketRoot(self.root)
    class Lines(old.Lines):
        def __init__(self, box):
            self.box = box
            self.proc = _Process(box, ["/usr/bin/python3", "-I", "-c", inside_source(task["input_paths"])])
    with patch.object(old, "PersistentSandbox", Box), patch.object(old, "Lines", Lines), patch.object(old, "inspect_authority", lambda box: inspect(box, task)), \
         patch.object(old, "evaluate", lambda snapshot, sdk, vectors, check_only=False: evaluate(snapshot, sdk, task, check_only)):
        old.serve(config_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--role", default="mcp", choices=("server", "mcp", "control"))
    args = p.parse_args()
    if args.role == "server":
        serve(args.config)
    elif args.role == "mcp":
        old.relay(args.config, "mcp")
    else:
        request = json.loads(sys.stdin.read(1024**2))
        print(json.dumps(old.control(args.config, request["action"], request["arguments"])))
