"""Trusted SSH STDIO bridge; only the isolated remote Native server is exposed."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p36_mm02_native_model.remote import Remote

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", required=True, type=Path)
    p.add_argument("--ready", required=True)
    args = p.parse_args()
    remote = Remote(args.connection)
    service = remote.root + "/benchmarks/maintenance_interface_comparison/service.py"
    raise SystemExit(subprocess.call(remote.argv(["python3", service, "--config", args.ready])))
