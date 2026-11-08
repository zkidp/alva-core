"""Finalize an actually qualified freeze on the Windows controller, no API."""
import argparse
import json
from pathlib import Path
import platform
import sys

from benchmarks.context_flash_pilot.freeze import HERE, runtime
from benchmarks.context_flash_pilot.runner import payload
from integrations.codex.maintenance_host import sha


def prepare(qualification, canary):
    frozen = json.loads(qualification.read_bytes())
    if len(frozen["qualification"]) != 9 or any(r["independent_final"] != "PASS" for r in frozen["qualification"]): raise RuntimeError("UNQUALIFIED")
    frozen["runtime"] = runtime()
    frozen["controller_python_sha256"] = sha(Path(sys.executable).read_bytes())
    frozen["controller_python_version"] = platform.python_version()
    frozen["initial_request_sha256"] = {k: sha(json.dumps(payload(frozen, msgs)).encode()) for k, msgs in frozen["initial_inputs"].items()}
    observed = json.loads(canary.read_bytes())
    if len(observed) != 2 or any(r["response"].get("model") != "deepseek-flash" for r in observed): raise RuntimeError("CANARY_NOT_CONFIRMED")
    frozen["canary"] = {"classification": "NON_SCIENTIFIC_TOY", "result": "PASS", "requests": 2,
        "reported_model": "deepseek-flash", "reported_total_tokens": sum(r["response"]["usage"]["total_tokens"] for r in observed),
        "thinking": "enabled", "reasoning_effort": "low", "tool_continuation": "PASS"}
    frozen["pre_freeze_corrections"] = ["Q02 initial nominal alias/i64 mismatch fixed before model use with nested records; no Core change",
        "WSL cannot resolve Windows linked-worktree Git metadata; trusted base SHA passed explicitly and controller Git verifies pushed freeze"]
    with (HERE / "FREEZE.json").open("x", encoding="utf-8") as f: json.dump(frozen, f, indent=2)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("qualification", type=Path)
    p.add_argument("canary", type=Path)
    a = p.parse_args()
    prepare(a.qualification, a.canary)
