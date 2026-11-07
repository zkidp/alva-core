"""Post-run launch safety. Never replay a consumed immutable freeze."""
import argparse
import json
from pathlib import Path

from benchmarks.compact_deepseek.runner import ROOT, HERE, run
from integrations.benchmark_runtime_v2.freeze import sha


def reserve(freeze_path, runtime_root):
    identity = sha(freeze_path.read_bytes())
    runtime_root.mkdir(parents=True, exist_ok=True)
    for path in runtime_root.rglob("GENERATION-STARTED.json"):
        if json.loads(path.read_bytes()).get("freeze_sha256") == identity:
            raise RuntimeError("CONSUMED_FREEZE_NO_REPLAY_REGISTER_A_NEW_STUDY")
    marker = runtime_root / ("RESERVED-" + identity + ".json")
    with marker.open("x", encoding="utf-8") as f:
        json.dump({"freeze_sha256": identity, "status": "RESERVED_ONCE"}, f)
    return marker


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", type=Path, required=True)
    p.add_argument("--credentials", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    reserve(HERE / "FREEZE.json", ROOT / ".local/compact-deepseek")
    run(args)
