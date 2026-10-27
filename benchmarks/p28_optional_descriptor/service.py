"""Versioned observer adapter over the unchanged P26/P23 trusted service.

No candidate evaluator, native operation, transport or authority implementation
is duplicated. The scoped sandbox factory wraps only its existing MCP client.
"""
import argparse
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import service as existing
from benchmarks.p28_optional_descriptor.observer import ObservedNative
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox


def serve(config_path):
    config = json.loads(config_path.read_text())
    destination = Path(config["observer_evidence"])
    sink_lock = threading.Lock()

    def sink(row):
        # Private host-side evidence, never mounted in candidate namespaces.
        with sink_lock, destination.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    class ObservedSandbox(PersistentSandbox):
        def mcp(self):
            return ObservedNative(super().mcp(), sink)

    with patch.object(existing, "PersistentSandbox", ObservedSandbox):
        existing.serve(config_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--role", choices=("server", "mcp", "control"), default="mcp")
    args = p.parse_args()
    if args.role == "server":
        serve(args.config)
    elif args.role == "mcp":
        existing.relay(args.config, "mcp")
    else:
        req = json.loads(sys.stdin.read(1024**2))
        print(json.dumps(existing.control(args.config, req["action"], req["arguments"])))
