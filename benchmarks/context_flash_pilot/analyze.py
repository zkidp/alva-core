"""Predeclared descriptive comparison; private raw records never copied to Git."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import zipfile

from benchmarks.context_flash_pilot.freeze import HERE
from integrations.codex.maintenance_host import canonical, sha


def analyze(directory):
    batch = json.loads((directory / "RESULTS.json").read_bytes())
    frozen = json.loads((HERE / "FREEZE.json").read_bytes())
    rows = []
    for record in batch["rows"]:
        outcome = record.get("outcome", {})
        events = record.get("tool_events", [])
        rows.append({k: record.get(k) for k in ("id", "task", "arm", "submitted_requests", "calls", "first_generation_utc", "last_request_admission", "first_accepted_change", "reported_usage", "source_exposure", "active_seconds", "stop_reason", "infrastructure_hold")} |
            {"correct": outcome.get("correct"), "task_status": outcome.get("task"), "regression": outcome.get("regression"),
             "fresh_authority_matches": outcome.get("fresh_authority_matches"), "original_sources_unchanged": outcome.get("original_sources_unchanged"),
             "scope": outcome.get("scope", {}).get("status"), "host_work": outcome.get("host_work"),
             "read_source_calls": sum(e["name"] == "read_source" for e in events),
             "search_calls": sum(e["name"] == "search_source" for e in events),
             "context_deliveries": sum("bounded_dependencies" in e["response"] for e in events),
             "rejected_calls": sum(e["response"].get("status") in ("REJECTED", "VALIDATION_FAILED", "SCOPE_VIOLATION") for e in events),
             "request_count": len(record.get("requests", [])),
             "target_representation_bytes": sum(len(e["response"].get("body", "").encode()) for e in events if e["name"] == "read_target"),
             "projection_bytes": sum(e["response"].get("dependency_projection_work", {}).get("response_utf8_bytes", 0) for e in events)})
    pairs = []
    for task in frozen["tasks"]:
        by = {r["arm"]: r for r in rows if r["task"] == task}
        pair = {"task": task, "observed_arms": sorted(by)}
        if set(by) == {"A", "B", "C"}:
            costs = {a: (r.get("reported_usage") or {}).get("totalTokens") for a, r in by.items()}
            pair.update(correct={a: r["correct"] for a, r in by.items()}, total_tokens=costs,
                unique_raw_bytes={a: r["source_exposure"]["unique_raw_bytes"] for a, r in by.items()},
                raw_delivered_bytes={a: r["source_exposure"]["raw_delivered_bytes"] for a, r in by.items()},
                C_over_A=costs["C"] / costs["A"] if costs["A"] and costs["C"] is not None else None,
                C_over_B=costs["C"] / costs["B"] if costs["B"] and costs["C"] is not None else None)
        pairs.append(pair)
    complete = batch["status"] == "COMPLETED" and len(rows) == 9 and not any(r["infrastructure_hold"] for r in rows)
    ratios = [p.get("C_over_A") for p in pairs]
    median = statistics.median(ratios) if complete and all(r is not None for r in ratios) else None
    worst = max(ratios) if median is not None else None
    source_lower = complete and sum(p["raw_delivered_bytes"]["C"] for p in pairs) < sum(p["raw_delivered_bytes"]["A"] for p in pairs)
    correct_not_lower = complete and sum(r["correct"] for r in rows if r["arm"] == "C") >= sum(r["correct"] for r in rows if r["arm"] == "A")
    favorable = complete and median is not None and median <= .75 and worst <= 1.5 and source_lower and correct_not_lower
    return {"status": batch["status"], "freeze_commit": batch["freeze_commit"], "freeze_sha256": sha((HERE / "FREEZE.json").read_bytes()),
        "classification": "EXPLORATORY_ECONOMY_SIGNAL" if favorable else ("NO_PREDECLARED_ECONOMY_SIGNAL" if complete else "INCONCLUSIVE_INFRASTRUCTURE_HOLD"),
        "rows": rows, "pairs": pairs, "median_C_over_A": median, "worst_C_over_A": worst,
        "C_raw_delivery_lower_aggregate": source_lower, "C_correct_not_lower": correct_not_lower,
        "scientific_requests_submitted": batch["provider_requests_submitted"], "canary_requests_separate": 2,
        "limitations": [frozen["authorship"], frozen["surface_limits"], "Parsed provider JSON retained; raw HTTP response wire not captured",
            "Single attempt per task/condition, no significance or causal/generalization claim", "Raw source bytes exclude structured representations; both retained separately; provider totals include all context"]}


def main(args):
    report = analyze(args.directory)
    args.public.mkdir(parents=True, exist_ok=True)
    (args.public / "RESULTS.json").write_bytes(json.dumps(report, indent=2).encode() + b"\n")
    archive = args.directory.parent / (args.directory.name + ".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(args.directory.rglob("*")):
            if p.is_file(): z.write(p, p.relative_to(args.directory).as_posix())
    manifest = {"archive": archive.name, "bytes": archive.stat().st_size, "sha256": sha(archive.read_bytes()),
        "entries": {p.relative_to(args.directory).as_posix(): sha(p.read_bytes()) for p in sorted(args.directory.rglob("*")) if p.is_file()}}
    (args.public / "ARCHIVE.json").write_bytes(json.dumps(manifest, indent=2).encode() + b"\n")
    print(json.dumps({k: report[k] for k in ("status", "classification", "scientific_requests_submitted", "median_C_over_A", "worst_C_over_A")}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--public", type=Path, required=True)
    main(p.parse_args())
