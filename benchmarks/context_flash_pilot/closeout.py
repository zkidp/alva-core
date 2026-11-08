"""Additive HOLD closeout; frozen runner/analyzer and raw run remain unchanged.

Clarifies partial usage coverage after an uncertain HTTP attempt. This adds no
new experimental metric selection or success classification and never resumes.
"""
import argparse
import json
from pathlib import Path
import shutil

from benchmarks.context_flash_pilot import analyze
from benchmarks.context_flash_pilot.freeze import ROOT, HERE
from integrations.codex.maintenance_host import sha


def clarify(report, batch, frozen):
    completed = {r["id"] for r in batch["rows"]}
    report["not_started_slots"] = [r for r in frozen["schedule"] if r["id"] not in completed]
    report["post_execution_reporting_clarification"] = "Received usage is not full spend when a submitted request has unknown outcome; no raw/frozen record changed."
    report["batch_total_token_cost"] = None if any(r.get("infrastructure_hold") for r in batch["rows"]) else sum(r["reported_usage"]["totalTokens"] for r in batch["rows"])
    for derived, original in zip(report["rows"], batch["rows"]):
        submitted = original.get("submitted_requests", 0)
        received = len(original.get("requests", []))
        derived["usage_complete_for_submitted_requests"] = submitted == received
        derived["usage_scope"] = "Received responses only; missing attempt usage UNKNOWN, not zero" if submitted != received else "All submitted responses received"
        derived["unknown_usage_attempts"] = submitted - received
        derived["model_performance_eligible"] = not bool(original.get("infrastructure_hold"))
        derived["interpretation"] = "Operational final authority outcome, not an eligible agent-failure outcome under infrastructure HOLD" if original.get("infrastructure_hold") else "Completed candidate-local outcome"
    return report


def main(args):
    frozen = json.loads((HERE / "FREEZE.json").read_bytes())
    # Archive exact original pinned source bytes, not a later checkout recreation.
    for path, expected in frozen["runtime"].items():
        data = (ROOT / path).read_bytes()
        if sha(data) != expected: raise RuntimeError("ORIGINAL_RUNTIME_DRIFT:" + path)
        target = args.directory / "runtime-snapshot" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    shutil.copyfile(HERE / "FREEZE.json", args.directory / "EXECUTION-FREEZE.json")
    analyze.main(args)
    path = args.public / "RESULTS.json"
    report = clarify(json.loads(path.read_bytes()), json.loads((args.directory / "RESULTS.json").read_bytes()), frozen)
    path.write_bytes(json.dumps(report, indent=2).encode() + b"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--public", type=Path, required=True)
    main(parser.parse_args())
