"""Resume only the seven unstarted slots after a separately sealed DNS HOLD."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from benchmarks.context_flash_pilot.freeze import ROOT, HERE as ORIGINAL
from benchmarks.context_flash_pilot.runner import WSLSlot, conversation, save
from benchmarks.context_flash_resume.runner import HERE, verify_original
from benchmarks.context_flash_resume.dns_route import RoutedAPI
from integrations.codex.maintenance_host import sha


def register(args):
    frozen = json.loads((ORIGINAL / "FREEZE.json").read_bytes())
    verify_original(frozen)
    second = json.loads(args.second.read_bytes())
    if second["status"] != "HOLD" or [r["id"] for r in second["rows"]] != ["Q01-B"]: raise RuntimeError("SECOND_HOLD_IDENTITY")
    route = json.loads(args.canary.with_suffix(".route.json").read_bytes())
    replies = json.loads(args.canary.read_bytes())
    if route["status"] != "PASS" or route["requests"] != 2 or route["address_sha256"] != sha(args.address.encode()): raise RuntimeError("ROUTED_CANARY_REQUIRED")
    previous = json.loads((HERE / "ARCHIVE.json").read_bytes())
    if sha(args.second_archive.read_bytes()) != previous["sha256"]: raise RuntimeError("SECOND_ARCHIVE_IDENTITY")
    value = {"schema": "context-flash-scoped-dns-continuation/v1", "original_freeze_sha256": sha((ORIGINAL / "FREEZE.json").read_bytes()),
        "previous_hold_preserved": ["Q01-A", "Q01-B"], "second_results_sha256": sha(args.second.read_bytes()),
        "second_archive_sha256": previous["sha256"], "schedule": frozen["schedule"][2:],
        "route_address_sha256": route["address_sha256"], "route_seconds": 300,
        "route_source": "Current public A answer obtained with explicit nslookup against 1.1.1.1; API TLS hostname verified before any credential use. No global DNS change.",
        "canary": {"requests": 2, "status": "PASS", "total_tokens": sum(r["response"]["usage"]["total_tokens"] for r in replies),
                   "raw_sha256": sha(args.canary.read_bytes()), "unauthenticated_probes": 3},
        "controller_files": {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(HERE.glob("*.py"))},
        "unchanged": "Exact task/model/thinking/initial requests/tools/mutation/evaluation/resource rules from original freeze",
        "changed": "TCP connects to a process-local DNS answer, max 300s; URL/Host/SNI/certificate verification unchanged; redirects/foreign origins/proxies rejected; no request retry",
        "analysis": "At most Q02/Q03 complete triples; Q01 A/B censored. Original nine-slot screen remains unevaluable. Full prior cost remains UNKNOWN."}
    with (HERE / "DNS-CONTINUATION-FREEZE.json").open("x", encoding="utf-8") as stream: json.dump(value, stream, indent=2)
    print(json.dumps({"slots": len(value["schedule"]), "retry_slots": 0, "canary_tokens": value["canary"]["total_tokens"]}))


def verify(amendment, frozen, address):
    verify_original(frozen)
    if sha((ORIGINAL / "FREEZE.json").read_bytes()) != amendment["original_freeze_sha256"]: raise RuntimeError("FREEZE_DRIFT")
    if amendment["schedule"] != frozen["schedule"][2:] or sha(address.encode()) != amendment["route_address_sha256"]: raise RuntimeError("SCHEDULE_OR_ROUTE_DRIFT")
    for path, expected in amendment["controller_files"].items():
        if sha((ROOT / path).read_bytes()) != expected: raise RuntimeError("CONTINUATION_CODE_DRIFT:" + path)


def run(args):
    frozen = json.loads((ORIGINAL / "FREEZE.json").read_bytes())
    amendment = json.loads((HERE / "DNS-CONTINUATION-FREEZE.json").read_bytes())
    verify(amendment, frozen, args.address)
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT): raise RuntimeError("DIRTY_WORKTREE")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != subprocess.check_output(["git", "rev-parse", "@{upstream}"], cwd=ROOT, text=True).strip(): raise RuntimeError("UNPUSHED_FREEZE")
    second = json.loads(args.second.read_bytes())
    if sha(args.second.read_bytes()) != amendment["second_results_sha256"]: raise RuntimeError("PRIOR_WAVE_DRIFT")
    args.output.mkdir(parents=True, exist_ok=False)
    (ROOT / ".local" / ("context-flash-dns-reserved-" + sha((HERE / "DNS-CONTINUATION-FREEZE.json").read_bytes()))).open("x").close()
    save(args.output / "DNS-CONTINUATION-FREEZE.json", amendment)
    save(args.output / "private-route.json", {"address": args.address, "max_seconds": 300})
    api, rows = RoutedAPI(args.credentials, address=args.address), []
    for entry in amendment["schedule"]:
        record, slot = dict(entry), None
        print("START " + entry["id"], flush=True)
        try:
            verify(amendment, frozen, args.address)
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
                "provider_requests_submitted": api.submitted_chat_requests})
            print(json.dumps({"id": entry["id"], "stop": record.get("stop_reason"), "hold": record.get("infrastructure_hold"),
                "correct": record.get("outcome", {}).get("correct"), "usage": record.get("reported_usage"),
                "safe_transport_diagnostics": record.get("safe_transport_diagnostics")}), flush=True)
        if record.get("infrastructure_hold"): break
    save(args.output / "RESULTS.json", {"status": "COMPLETED_SEVEN_REMAINING" if len(rows) == 7 and not any(r.get("infrastructure_hold") for r in rows) else "HOLD",
        "rows": rows, "amendment_commit": head, "provider_requests_submitted": api.submitted_chat_requests})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    for key in ("second", "second-archive", "canary", "credentials", "output"): parser.add_argument("--" + key, type=Path)
    parser.add_argument("--address", required=True)
    for key in ("alva", "toolchain", "registry"): parser.add_argument("--" + key)
    a = parser.parse_args()
    if a.register: register(a)
    else: run(a)
