"""Create the additive continuation freeze after actual connectivity/canary."""
import argparse
import json
from pathlib import Path

from benchmarks.context_flash_pilot.freeze import ROOT, HERE as ORIGINAL
from benchmarks.context_flash_resume.runner import HERE, verify_original
from integrations.codex.maintenance_host import sha


def remaining(frozen, prior):
    if prior["status"] != "HOLD" or [r["id"] for r in prior["rows"]] != ["Q01-A"]: raise ValueError("Only the original one-slot HOLD is resumable here")
    return frozen["schedule"][1:]


def register(args):
    frozen = json.loads((ORIGINAL / "FREEZE.json").read_bytes())
    verify_original(frozen)
    prior = json.loads(args.prior.read_bytes())
    conn = json.loads(args.connectivity.read_bytes())
    canary = json.loads(args.canary.with_suffix(".diagnostics.json").read_bytes())
    responses = json.loads(args.canary.read_bytes())
    if conn["dns"]["status"] != "PASS" or conn["direct_tls"]["status"] != "PASS" or conn["urllib_unauthenticated_https"]["status"] != "PASS_TRANSPORT": raise RuntimeError("CONNECTIVITY_NOT_PASSED")
    if canary["status"] != "PASS" or canary["requests"] != 2 or canary["transport_failures"]: raise RuntimeError("CANARY_NOT_PASSED")
    manifest = json.loads((ORIGINAL / "ARCHIVE.json").read_bytes())
    if sha(args.archive.read_bytes()) != manifest["sha256"]: raise RuntimeError("PRIOR_ARCHIVE_MISMATCH")
    value = {"schema": "context-flash-authorized-continuation/v1", "authorization": "User requested connectivity retest and continuation; do not retry interrupted Q01-A",
        "original_freeze_sha256": sha((ORIGINAL / "FREEZE.json").read_bytes()), "prior_archive_sha256": manifest["sha256"],
        "prior_results_sha256": sha(args.prior.read_bytes()), "schedule": remaining(frozen, prior),
        "model_inputs_tools_budget_unchanged": True, "original_interrupted_slot": "Q01-A", "original_slot_retried": False,
        "connectivity": conn, "canary": {"requests": 2, "status": "PASS", "reported_model": responses[-1]["response"]["model"],
            "total_received_tokens": sum(r["response"]["usage"]["total_tokens"] for r in responses), "raw_sha256": sha(args.canary.read_bytes())},
        "additive_files": {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(HERE.glob("*.py"))},
        "execution": "Same frozen conversation/WSL service; DiagnosticAPI calls original API and only observes exceptions; no transport retry or request mutation",
        "analysis": "Q01-A remains censored; no complete original 9-slot success/cost score. Report all eight continued slots and available Q02/Q03 A/B/C pairs descriptively; no full-screen success classification."}
    with (HERE / "CONTINUATION-FREEZE.json").open("x", encoding="utf-8") as stream: json.dump(value, stream, indent=2)
    print(json.dumps({"frozen_slots": len(value["schedule"]), "repeated_slots": 0, "canary": value["canary"]["total_received_tokens"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("prior", "archive", "connectivity", "canary"): parser.add_argument("--" + name, type=Path, required=True)
    register(parser.parse_args())
