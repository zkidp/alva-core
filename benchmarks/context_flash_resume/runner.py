"""Authorized remaining-slot continuation, never retry the interrupted slot.

Reuses the frozen conversation, WSL service and Host without edits. Only the
transport exception telemetry and schedule admission wrapper are additive.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from benchmarks.context_flash_pilot.freeze import ROOT, HERE as ORIGINAL
from benchmarks.context_flash_pilot.runner import WSLSlot, conversation, save
from benchmarks.context_flash_resume.transport import DiagnosticAPI
from integrations.codex.maintenance_host import sha

HERE = Path(__file__).parent


def verify_original(frozen):
    for path, expected in frozen["runtime"].items():
        if sha((ROOT / path).read_bytes()) != expected: raise RuntimeError("ORIGINAL_RUNTIME_DRIFT:" + path)
    if sha(Path(sys.executable).read_bytes()) != frozen["controller_python_sha256"]: raise RuntimeError("CONTROLLER_PYTHON_DRIFT")


def verify(amendment, frozen):
    if sha((ORIGINAL / "FREEZE.json").read_bytes()) != amendment["original_freeze_sha256"]: raise RuntimeError("ORIGINAL_FREEZE_DRIFT")
    verify_original(frozen)
    for path, expected in amendment["additive_files"].items():
        if sha((ROOT / path).read_bytes()) != expected: raise RuntimeError("ADDITIVE_CONTROLLER_DRIFT:" + path)
    if amendment["schedule"] != frozen["schedule"][1:]: raise RuntimeError("REMAINING_SCHEDULE_DRIFT")


def run(args):
    frozen = json.loads((ORIGINAL / "FREEZE.json").read_bytes())
    amendment = json.loads((HERE / "CONTINUATION-FREEZE.json").read_bytes())
    verify(amendment, frozen)
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT): raise RuntimeError("DIRTY_WORKTREE")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != subprocess.check_output(["git", "rev-parse", "@{upstream}"], cwd=ROOT, text=True).strip(): raise RuntimeError("UNPUSHED_AMENDMENT")
    prior = json.loads(args.prior.read_bytes())
    if [r["id"] for r in prior["rows"]] != ["Q01-A"] or prior["status"] != "HOLD": raise RuntimeError("PRIOR_NOT_EXPECTED_HOLD")
    if sha(args.prior.read_bytes()) != amendment["prior_results_sha256"]: raise RuntimeError("PRIOR_RECORD_DRIFT")
    args.output.mkdir(parents=True, exist_ok=False)
    reservation = ROOT / ".local" / ("context-flash-continuation-reserved-" + sha((HERE / "CONTINUATION-FREEZE.json").read_bytes()))
    reservation.open("x").close()
    save(args.output / "CONTINUATION-FREEZE.json", amendment)
    api, rows = DiagnosticAPI(args.credentials), []
    for entry in amendment["schedule"]:
        record, slot = dict(entry), None
        print("START " + entry["id"], flush=True)
        try:
            verify(amendment, frozen)
            slot = WSLSlot(entry, frozen, {k: getattr(args, k) for k in ("alva", "toolchain", "registry")})
            conversation(api, slot, frozen, record, args.output / entry["id"])
        except Exception as exc:
            record["infrastructure_hold"] = type(exc).__name__ + ":" + str(exc)[:180]
            record["safe_transport_diagnostics"] = list(api.failures)
        finally:
            if slot:
                try:
                    final = slot.request({"action": "finish"})
                    save(args.output / entry["id"] / "backend.json", final)
                    record["outcome"] = {k: v for k, v in final.items() if k not in ("calls", "evaluations")}
                    slot.close()
                except Exception as exc: record["infrastructure_hold"] = "FINALIZATION:" + type(exc).__name__
            rows.append(record)
            save(args.output / entry["id"] / "record.json", record)
            save(args.output / "RESULTS.json", {"status": "RUNNING", "rows": rows, "amendment_commit": head,
                "provider_requests_submitted": api.submitted_chat_requests, "prior_not_replaced": True})
            print(json.dumps({"id": entry["id"], "stop": record.get("stop_reason"), "hold": record.get("infrastructure_hold"),
                "correct": record.get("outcome", {}).get("correct"), "usage": record.get("reported_usage"),
                "safe_transport_diagnostics": record.get("safe_transport_diagnostics")}), flush=True)
        if record.get("infrastructure_hold"): break
    save(args.output / "RESULTS.json", {"status": "COMPLETED_REMAINING_SLOTS" if len(rows) == 8 and not any(r.get("infrastructure_hold") for r in rows) else "HOLD",
        "rows": rows, "amendment_commit": head, "provider_requests_submitted": api.submitted_chat_requests, "prior_not_replaced": True})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("credentials", "prior", "output"): p.add_argument("--" + name, type=Path, required=True)
    for name in ("alva", "toolchain", "registry"): p.add_argument("--" + name, required=True)
    run(p.parse_args())
