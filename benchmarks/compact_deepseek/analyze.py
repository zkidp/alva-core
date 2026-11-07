"""Prespecified DeepSeek diagnostic analysis; publishes no model text."""
import argparse
import json
from pathlib import Path
import statistics

from benchmarks.compact_deepseek.api import totals
from benchmarks.compact_deepseek.runner import save
from integrations.benchmark_runtime_v2.freeze import sha

HERE = Path(__file__).parent


def analyze(directory):
    frozen = json.loads((HERE / "FREEZE.json").read_bytes())
    raw = json.loads((directory / "RESULTS.json").read_bytes())
    rows = []
    for r in raw["rows"]:
        keep = ("id", "task", "arm", "repeat", "correct", "valid", "model_sessions_started", "terminal_confirmed",
                "stop_reason", "infrastructure_hold", "observed_tool_calls", "dispatched_tool_calls", "submitted_chat_requests",
                "reported_usage", "usage_complete", "setup_seconds", "active_seconds", "finalization_seconds", "outcome",
                "successful_native_commits", "identity_before", "identity_after", "cleanup_confirmed", "evidence_sha256")
        row = {k: r.get(k) for k in keep}
        row["record_sha256"] = sha((directory / r["id"] / "record.json").read_bytes())
        row["provider_models"] = sorted({e["response"].get("model", "UNKNOWN") for e in r.get("responses", [])})
        row["provider_fingerprints"] = sorted({e["response"].get("system_fingerprint", "UNKNOWN") for e in r.get("responses", [])})
        row["tool_errors"] = sum(bool(e["response"].get("error") or e["response"].get("isError")) for e in r.get("tool_events", []))
        rows.append(row)
    paired = []
    counts = {arm: sum(r["correct"] is True and r["valid"] for r in rows if r["arm"] == arm) for arm in ("T", "N")}
    for ident in frozen["tasks"]:
        for rep in (1, 2):
            p = {r["arm"]: r for r in rows if r["task"] == ident and r["repeat"] == rep}
            item = {"task": ident, "repeat": rep, "both_valid": len(p) == 2 and all(r["valid"] for r in p.values()),
                    "T_correct": p.get("T", {}).get("correct"), "N_correct": p.get("N", {}).get("correct")}
            if len(p) == 2 and all(r["valid"] and r["correct"] and r["usage_complete"] for r in p.values()):
                item.update(T_total=p["T"]["reported_usage"]["totalTokens"], N_total=p["N"]["reported_usage"]["totalTokens"])
                item["ratio"] = item["N_total"] / item["T_total"]
            paired.append(item)
    costs = [p for p in paired if "ratio" in p]
    median = statistics.median(p["ratio"] for p in costs) if costs else None
    if len(rows) != 16 or not all(r["valid"] for r in rows): disposition = "INCONCLUSIVE_INFRASTRUCTURE"
    elif len(costs) < 4: disposition = "INCONCLUSIVE_INSUFFICIENT_PAIRED_SUCCESSES"
    elif counts["N"] >= counts["T"] and median <= .75: disposition = "EXPLORATORY_FAVORABLE_SIGNAL"
    else: disposition = "NO_EXPLORATORY_FAVORABLE_SIGNAL"
    arms = {}
    for arm in ("T", "N"):
        selected = [r for r in rows if r["arm"] == arm]
        complete = [r["reported_usage"] for r in selected if r["usage_complete"]]
        arms[arm] = {"scheduled": 8, "observed": len(selected), "correct": counts[arm],
                     "valid": sum(bool(r["valid"]) for r in selected), "complete_usage_slots": len(complete),
                     "observed_complete_usage_sum": totals(complete),
                     "submitted_chat_requests": sum(r["submitted_chat_requests"] or 0 for r in selected),
                     "median_success_total_tokens": statistics.median(p[arm + "_total"] for p in costs) if costs else None,
                     "median_active_seconds": statistics.median(r["active_seconds"] for r in selected if r["active_seconds"] is not None) if selected else None,
                     "provider_generation_requests": None, "dollar_cost": None}
    return {"status": raw["status"], "disposition": disposition, "model": frozen["model"], "effort": "low",
            "freeze_sha256": sha((HERE / "FREEZE.json").read_bytes()), "known_tasks": 4, "independent_new_tasks": 0,
            "model_sessions_started": raw["model_sessions_started"], "submitted_chat_requests": raw["submitted_chat_requests"],
            "input_token_api_calls": 0, "both_success_pairs": len(costs), "median_paired_token_ratio": median,
            "arms": arms, "pairs": paired, "rows": rows,
            "limits": ["Known author-informed tasks; no general superiority or significance claim.",
                       "Success-conditioned token comparison; failures and observed resource use retained.",
                       "No cross-provider/tokenizer comparison with historical GPT results.",
                       "Provider alias/fingerprints do not establish immutable model weights.",
                       "Reasoning usage remains null if unreported; not fabricated or added to output."]}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); result = analyze(a.directory); save(a.output, result)
    print(json.dumps({k: result[k] for k in ("disposition", "model_sessions_started", "both_success_pairs", "median_paired_token_ratio")}))
