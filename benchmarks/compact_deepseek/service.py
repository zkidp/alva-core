"""New compact-profile service over unchanged MIC/P22/P23 isolation.

The provider and its credential file are never present on this Linux service
or in candidate mounts. No model execution happens in this module.
"""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_interface_comparison import service as prior
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox


def serve(path):
    original = PersistentSandbox._command
    def command(self, argv):
        if argv == ["/sdk/alva", "mcp"]:
            argv = [*argv, "--profile", "maintenance"]
        return original(self, argv)
    with patch.object(PersistentSandbox, "_command", command):
        prior.serve(path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--role", choices=("server", "control", "mcp"), default="mcp")
    a = p.parse_args()
    if a.role == "server":
        serve(a.config)
    elif a.role == "control":
        request = json.loads(sys.stdin.read(1024**2))
        print(json.dumps(prior.old.control(a.config, request["action"], request["arguments"])))
    else:
        prior.old.relay(a.config, "mcp")
