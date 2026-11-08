"""Descriptive continuation results; never turn censored Q01-A into a pair."""
import argparse
import json
from pathlib import Path
import statistics
import zipfile

from benchmarks.context_flash_pilot.freeze import HERE as ORIGINAL, ROOT
from benchmarks.context_flash_resume.runner import HERE
from integrations.codex.maintenance_host import sha


def describe(batch, prior):
    rows = []
    for record in batch["rows"]:
        outcome = record.get("outcome", {})
        events = record.get("tool_events", [])
        complete_usage = record.get("submitted_requests", 0) == len(record.get("requests", []))
        rows.append({k: record.get(k) for k in ("id", "task", "arm", "submitted_requests", "reported_usage", "calls", "first_accepted_change", "active_seconds", "source_exposure", "stop_reason", "infrastructure_hold", "safe_transport_diagnostics")} |
            {"eligible": not bool(record.get("infrastructure_hold")) and complete_usage,
             "usage_complete": complete_usage, "unknown_usage_attempts": record.get("submitted_requests", 0) - len(record.get("requests", [])),
             "correct": outcome.get("correct"), "task_result": outcome.get("task"), "regression": outcome.get("regression"),
             "scope": outcome.get("scope", {}).get("status"), "fresh_authority_matches": outcome.get("fresh_authority_matches"),
             "source_unchanged": outcome.get("original_sources_unchanged"), "host_work": outcome.get("host_work"),
             "source_reads": sum(e["name"] == "read_source" for e in events), "searches": sum(e["name"] == "search_source" for e in events),
             "projection_deliveries": sum("bounded_dependencies" in e["response"] for e in events),
             "projection_bytes": sum(e["response"].get("dependency_projection_work", {}).get("response_utf8_bytes", 0) for e in events)})
    triples, bc_pairs = [], []
    for task in ("Q01", "Q02", "Q03"):
        by = {r["arm"]: r for r in rows if r["task"] == task}
        entry = {"task": task, "observed_continued_arms": sorted(by)}
        if task == "Q01": entry["A_disposition"] = "ORIGINAL_INFRASTRUCTURE_HOLD_EXCLUDED_NOT_RETRIED"
        if set(by) == {"A", "B", "C"} and all(r["eligible"] for r in by.values()):
            costs = {a: by[a]["reported_usage"]["totalTokens"] for a in by}
            entry.update(eligible=True, total_tokens=costs, correct={a: r["correct"] for a, r in by.items()},
                unique_raw_bytes={a: r["source_exposure"]["unique_raw_bytes"] for a, r in by.items()},
                raw_delivered_bytes={a: r["source_exposure"]["raw_delivered_bytes"] for a, r in by.items()}, C_over_A=costs["C"] / costs["A"])
        else: entry["eligible"] = False
        triples.append(entry)
        if all(a in by and by[a]["eligible"] for a in ("B", "C")):
            bc_pairs.append({"task": task, "B_correct": by["B"]["correct"], "C_correct": by["C"]["correct"],
                "C_over_B": by["C"]["reported_usage"]["totalTokens"] / by["B"]["reported_usage"]["totalTokens"]})
    ratios = [t["C_over_A"] for t in triples if t["eligible"]]
    return {"status": batch["status"], "original_overall_status": "INCOMPLETE_Q01_A_TRANSPORT_CENSORED",
        "classification": "DESCRIPTIVE_PARTIAL_CONTINUATION_ONLY" if batch["status"] == "COMPLETED_REMAINING_SLOTS" else "INCONCLUSIVE_INFRASTRUCTURE_HOLD",
        "full_original_screen_evaluable": False, "rows": rows, "task_triples": triples, "BC_pairs": bc_pairs,
        "eligible_AC_pairs": len(ratios), "descriptive_median_C_over_A": statistics.median(ratios) if ratios else None,
        "descriptive_worst_C_over_A": max(ratios) if ratios else None, "continuation_requests_submitted": batch["provider_requests_submitted"],
        "prior_requests_submitted": prior["provider_requests_submitted"], "prior_unknown_usage_attempts": 1,
        "all_scientific_total_tokens": None, "retest_canary_requests_separate": 2,
        "limitations": ["Original Q01-A was not rerun/replaced; missing cost remains UNKNOWN", "No complete 9-slot primary comparison or formal screen outcome",
            "Single fresh session per remaining cell; authored tiny fixtures, not external/independent holdout tasks", "Source-only acquisition control is not a full IDE/LSP", "No statistical, causal or superiority claim"]}


def main(args):
    batch, prior = (json.loads(p.read_bytes()) for p in (args.directory / "RESULTS.json", args.prior))
    frozen = json.loads((ORIGINAL / "FREEZE.json").read_bytes())
    amended = json.loads((HERE / "CONTINUATION-FREEZE.json").read_bytes())
    # Exact original runtime and additive continuation bytes retained privately.
    for path, expected in {**frozen["runtime"], **amended["additive_files"]}.items():
        data = (ROOT / path).read_bytes()
        if sha(data) != expected: raise RuntimeError("ARCHIVE_RUNTIME_DRIFT:" + path)
        target = args.directory / "runtime-snapshot" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    result = describe(batch, prior)
    result["amendment_commit"] = batch["amendment_commit"]
    (HERE / "RESULTS.json").write_bytes(json.dumps(result, indent=2).encode() + b"\n")
    archive = args.directory.parent / (args.directory.name + ".zip")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(args.directory.rglob("*")):
            if path.is_file(): stream.write(path, path.relative_to(args.directory).as_posix())
    manifest = {"archive": archive.name, "sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size,
        "entries": {p.relative_to(args.directory).as_posix(): sha(p.read_bytes()) for p in sorted(args.directory.rglob("*")) if p.is_file()},
        "original_archive_unchanged": amended["prior_archive_sha256"]}
    (HERE / "ARCHIVE.json").write_bytes(json.dumps(manifest, indent=2).encode() + b"\n")
    print(json.dumps({k: result[k] for k in ("status", "eligible_AC_pairs", "descriptive_median_C_over_A", "descriptive_worst_C_over_A", "continuation_requests_submitted")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--prior", type=Path, required=True)
    main(parser.parse_args())
