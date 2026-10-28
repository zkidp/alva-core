"""Scoped MM01 adapter: reuse the unchanged P26 service / P23 process owner."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import service as old
from benchmarks.p28_optional_descriptor.observer import ObservedNative
from benchmarks.mm01_pilot.evaluator import evaluate
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox, _Process

FUNCTIONS = ("demo.model.make_meta", "demo.model.size_of", "demo.model.touch_size", "demo.app.run")


def authority(box):
    with box.mcp() as n:
        n.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                "clientInfo": {"name": "mm01-readonly-host", "version": "1"}})
        begun = n.tool("begin_transaction", {"project": "/work/project/alva.toml"})
        if begun.get("isError"):
            return {"body_error": True}
        b = begun["structuredContent"]
        bodies = {}
        for f in FUNCTIONS:
            result = n.tool("inspect_body", {"transaction_id": b["transaction_id"], "function": f})
            bodies[f] = None if result.get("isError") else hashlib.sha256(result["structuredContent"]["body"].encode()).hexdigest()
        n.tool("abort_transaction", {"transaction_id": b["transaction_id"]})
        return {"project_revision": b["project_revision"], "bodies": bodies}


class Observer(ObservedNative):
    def capture(self, tx, call_id, operation, baseline=False):
        start = time.monotonic_ns()
        params = {"name": "inspect_body", "arguments": {"transaction_id": tx, "function": FUNCTIONS[2]}}
        answer = self.inner.request("tools/call", params)
        if answer.get("isError"):
            raise RuntimeError("OBSERVER_BODY_UNAVAILABLE")
        digest = hashlib.sha256(answer["structuredContent"]["body"].encode()).hexdigest()
        if baseline:
            self.baselines[tx] = digest
        self.sink({"call_id": call_id, "transaction_id": tx, "after_operation": operation,
                   "baseline": baseline, "body_sha256": digest, "observer_calls": 1,
                   "changed_from_transaction_start": digest != self.baselines[tx],
                   "elapsed_ns": time.monotonic_ns() - start})


class Lines(old.Lines):
    def __init__(self, box):
        self.box = box
        self.proc = _Process(box, ["/usr/bin/python3", "-I", "-c", Path(__file__).with_name("inside.py").read_text()])


def serve(path):
    cfg = json.loads(path.read_text())
    def sink(row):
        with Path(cfg["observer_evidence"]).open("a", encoding="utf-8") as out:
            out.write(json.dumps(row) + "\n")
    class Box(PersistentSandbox):
        def mcp(self):
            return Observer(super().mcp(), sink)
    with patch.object(old, "PersistentSandbox", Box), patch.object(old, "Lines", Lines), \
         patch.object(old, "inspect_authority", authority), patch.object(old, "evaluate", evaluate):
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
        req = json.loads(sys.stdin.read(1024**2))
        print(json.dumps(old.control(args.config, req["action"], req["arguments"])))
