"""Offline accounting from public frozen summaries; no inference/provider imports."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]


def total(row):
    usage = row.get("reported_usage")
    if not row.get("usage_complete") or not isinstance(usage, dict):
        return None
    value = usage.get("totalTokens")
    if type(value) is not int or value < 0:
        raise ValueError("Invalid provider total")
    # Cached input is part of input; reasoning output is a subset, not extra.
    return value


class Exposure:
    """Exact UTF-8 source delivery meter for future raw-record analyses.

    Caller must supply verified actual delivery bytes and source identity, not
    reconstructed tool output. Distinct versions never count as duplicate reads.
    This helper is NOT used to invent missing historical exposure measurements.
    """
    def __init__(self):
        self.intervals = {}
        self.delivered = self.unique = 0

    def add(self, path, source, start, delivered):
        if type(start) is not int or start < 0 or not delivered:
            raise ValueError("Nonempty exact byte interval required")
        end = start + len(delivered)
        if source[start:end] != delivered:
            raise ValueError("Delivered bytes do not match source interval")
        delivered.decode("utf-8")
        key = (path, hashlib.sha256(source).hexdigest())
        old = self.intervals.get(key, [])
        overlap = sum(max(0, min(end, b) - max(start, a)) for a, b in old)
        self.delivered += len(delivered)
        self.unique += len(delivered) - overlap
        merged = []
        for a, b in sorted(old + [(start, end)]):
            if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else: merged.append((a, b))
        self.intervals[key] = merged
        return {"delivered": self.delivered, "unique": self.unique,
                "duplicate": self.delivered - self.unique}


def analyze(root=ROOT):
    bindings = {}
    data = {}
    for study in ("context_v4", "maintenance_interface_comparison"):
        path = root / "benchmarks" / study / "RESULTS.json"
        raw = path.read_bytes()
        bindings[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
        data[study] = json.loads(raw)
    v4, mic = data.values()
    pairs = []
    for task in sorted({r["task"] for r in v4["rows"]}):
        rows = {r["arm"]: r for r in v4["rows"] if r["task"] == task}
        costs = {arm: total(rows[arm]) for arm in ("T", "V3", "V4")}
        pairs.append({"task": task, "totals": costs,
            "correct": {a: rows[a]["correct"] for a in costs},
            "V4_over_T": costs["V4"] / costs["T"] if all(costs[a] for a in ("T", "V4")) else None,
            "V4_over_V3": costs["V4"] / costs["V3"] if all(costs[a] for a in ("V3", "V4")) else None})
    aggregate = {a: sum(p["totals"][a] for p in pairs) if all(p["totals"][a] is not None for p in pairs) else None
                 for a in ("T", "V3", "V4")}
    comparisons = {}
    for baseline in ("T", "V3"):
        ratios = [p["V4_over_" + baseline] for p in pairs]
        comparisons[baseline] = {"median_paired_ratio": statistics.median(ratios) if all(r is not None for r in ratios) else None,
            "aggregate_ratio": aggregate["V4"] / aggregate[baseline] if aggregate["V4"] is not None and aggregate[baseline] else None,
            "worst_task": max(pairs, key=lambda p: p["V4_over_" + baseline])["task"]}
    eligible, survivors = [], []
    for task, repeat in sorted({(r["task"], r["repeat"]) for r in mic["rows"]}):
        rows = {r["arm"]: r for r in mic["rows"] if (r["task"], r["repeat"]) == (task, repeat)}
        if set(rows) != {"T", "N"} or not all(r["evaluation_eligible"] for r in rows.values()): continue
        row = {"task": task, "repeat": repeat, "correct": {a: r["correct"] for a, r in rows.items()},
               "tokens": {a: total(r) for a, r in rows.items()}}
        eligible.append(row)
        if all(row["correct"].values()) and all(v is not None for v in row["tokens"].values()): survivors.append(row)
    return {"schema": "bounded-context-offline-audit/v1", "input_sha256": bindings,
        "new_generation_calls": 0, "new_input_token_api_calls": 0,
        "V4": {"pairs": pairs, "aggregate_tokens": aggregate, "comparisons": comparisons,
            "submitted_chat_requests": {a: sum(r["submitted_chat_requests"] for r in v4["rows"] if r["arm"] == a) for a in aggregate},
            "not_P42_treatment": True, "historical_disposition_unchanged": True},
        "MIC01": {"disposition": mic["disposition"], "eligible_pairs": eligible,
            "eligible_pair_correct": {a: sum(p["correct"][a] for p in eligible) for a in ("T", "N")},
            "both_success_pairs": len(survivors),
            "both_success_median_tokens": {a: statistics.median(p["tokens"][a] for p in survivors) for a in ("T", "N")},
            "survivor_selection_warning": "Not unconditional efficiency; failures excluded from survivor medians",
            "cli_identity_limitation": mic["cli_identity_limitation"], "quota_incident_not_erased": True},
        "actual_source_exposure": {"status": "UNKNOWN_RAW_RECORDS_UNAVAILABLE",
            "unique_bytes": None, "duplicate_bytes": None, "relevant_coverage": None,
            "scope": "Scoped local archive search; absence here is not proof archives never existed",
            "reason": "Public totals/diagnostic arguments cannot reconstruct actual source deliveries"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(analyze(), stream, indent=2)
