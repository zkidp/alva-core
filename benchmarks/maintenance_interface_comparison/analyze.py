"""Describe all scheduled outcomes; no model execution or runtime changes."""
import argparse
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import canonical, sha
from benchmarks.maintenance_interface_comparison.provider_gate import provider_fault

HERE = Path(__file__).parent


def describe(directory):
    freeze = json.loads((HERE / "FREEZE.json").read_text())
    batch = json.loads((directory / "RESULTS.json").read_text())
    rows = []
    for record in batch["rows"]:
        outcome = record.get("outcome", {})
        fault = provider_fault(record)
        usage = (record.get("usage") or {}).get("total")
        item = {k: record.get(k) for k in ("id", "task", "arm", "repeat", "model_tasks_started", "terminal_status", "stop_reason", "tool_calls", "elapsed_seconds", "usage_complete")}
        item.update(correct=None if fault else outcome.get("correct", False), outcome=outcome,
                    inference_outcome="UNKNOWN_PROVIDER_LIMIT" if fault else ("CORRECT" if outcome.get("correct") else "NOT_COMPLETED_CORRECTLY"),
                    reported_usage=usage, infrastructure_hold=record.get("infrastructure_hold"),
                    provider_fault=fault, evaluation_eligible=not bool(fault or record.get("infrastructure_hold")))
        evidence_path = directory / record["id"] / "linux.json"
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
        native = [e for e in evidence.get("calls", []) if e.get("request", {}).get("method") == "tools/call"]
        item["native_calls"] = len(native)
        item["native_tool_errors"] = sum(bool(e["response"].get("isError")) for e in native if isinstance(e.get("response"), dict))
        item["successful_native_commits"] = sum(e["request"]["params"]["name"] == "commit_transaction" and not e["response"].get("isError") for e in native)
        item["check_test_calls"] = sum(e.get("action") in ("check", "test") for e in evidence.get("calls", []))
        item["record_sha256"] = sha((directory / record["id"] / "record.json").read_bytes())
        item["linux_evidence_sha256"] = sha(evidence_path.read_bytes()) if evidence_path.exists() else None
        rows.append(item)
    arms = {}
    for arm in ("T", "N"):
        selected = [r for r in rows if r["arm"] == arm]
        eligible = [r for r in selected if r["evaluation_eligible"]]
        complete_usage = [r["reported_usage"] for r in selected if r["reported_usage"]]
        arms[arm] = {"scheduled": 12, "started": sum(r["model_tasks_started"] for r in selected),
            "observed_rows": len(selected), "correct": sum(bool(r["correct"]) for r in selected),
            "evaluation_eligible_rows": len(eligible), "provider_fault_rows": len(selected) - len(eligible),
            "reported_usage_rows": len(complete_usage),
            "eligible_usage_rows": sum(bool(r["reported_usage"]) for r in eligible),
            "reported_total_tokens": sum(u["totalTokens"] for u in complete_usage) if len(complete_usage) == len(selected) and selected else None,
            "observed_reported_total_lower_bound": sum(u["totalTokens"] for u in complete_usage),
            "eligible_reported_usage_sum": {k: sum(r["reported_usage"][k] for r in eligible) for k in
                ("totalTokens", "inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens")}
                if eligible and all(r["reported_usage"] for r in eligible) else None,
            "active_seconds": sum(r["elapsed_seconds"] for r in selected) if selected and all(r["elapsed_seconds"] is not None for r in selected) else None,
            "eligible_active_seconds": sum(r["elapsed_seconds"] for r in eligible) if eligible and all(r["elapsed_seconds"] is not None for r in eligible) else None,
            "setup_seconds": None,
            "provider_generation_requests": None, "dollar_cost": None}
    pairs = []
    for task in freeze["tasks"]:
        for repeat in (1, 2):
            selected = {r["arm"]: r for r in rows if r["task"] == task and r["repeat"] == repeat}
            entry = {"task": task, "repeat": repeat, "both_observed": set(selected) == {"T", "N"}}
            if entry["both_observed"]:
                entry.update(T_correct=selected["T"]["correct"], N_correct=selected["N"]["correct"])
                entry["both_evaluation_eligible"] = all(r["evaluation_eligible"] for r in selected.values())
                if all(r["correct"] and r["reported_usage"] for r in selected.values()):
                    entry.update(T_total_tokens=selected["T"]["reported_usage"]["totalTokens"],
                                 N_total_tokens=selected["N"]["reported_usage"]["totalTokens"],
                                 T_seconds=selected["T"]["elapsed_seconds"], N_seconds=selected["N"]["elapsed_seconds"])
            pairs.append(entry)
    both = [p for p in pairs if "T_total_tokens" in p]
    T_median = statistics.median(p["T_total_tokens"] for p in both) if both else None
    N_median = statistics.median(p["N_total_tokens"] for p in both) if both else None
    favorable = arms["N"]["correct"] > arms["T"]["correct"] or (
        arms["N"]["correct"] >= arms["T"]["correct"] and len(both) >= 4 and N_median <= .8 * T_median)
    completed = batch["status"] == "COMPLETED" and len(rows) == 24 and all(r["evaluation_eligible"] for r in rows)
    eligible_pairs = [p for p in pairs if p.get("both_evaluation_eligible")]
    faults = [r for r in rows if r["provider_fault"]]
    validation_path = HERE / "VALIDATION.json"
    cli_identity = json.loads(validation_path.read_text()).get("cli_identity") if validation_path.exists() else None
    return {"schema": "mic01-analysis/v1", "batch_status": batch["status"],
        "study_status": "INCOMPLETE_PROVIDER_LIMIT" if faults else ("COMPLETE" if completed else "INFRASTRUCTURE_HOLD"),
        "disposition": ("INCONCLUSIVE_PROVIDER_LIMIT" if faults else "INCONCLUSIVE_INFRASTRUCTURE_HOLD") if not completed else (
            "EXPLORATORY_FAVORABLE_SIGNAL" if favorable else "NO_EXPLORATORY_FAVORABLE_SIGNAL"),
        "not_a_proof_of_general_advantage": True, "known_task_selection": True,
        "eligibility_scope": "quota/outcome availability only; not a certification of uniform CLI binary identity",
        "cli_identity_limitation": cli_identity,
        "unique_tasks": 6, "component_sources": 3, "independent_new_tasks": 0,
        "model": freeze["model"], "effort": freeze["effort"], "model_slots_started": batch["model_tasks_started"],
        "scheduled_slots": 24, "freeze_sha256": sha((HERE / "FREEZE.json").read_bytes()),
        "model_turn_requests_submitted": batch["model_tasks_started"],
        "tool_active_turns": sum(bool(r.get("tool_calls")) for r in rows),
        "complete_eligible_pairs": len(eligible_pairs),
        "eligible_pair_correct": {arm: sum(p[arm + "_correct"] for p in eligible_pairs) for arm in ("T", "N")},
        "protocol_deviation": {"common_provider_fault_not_stopped_by_original_controller": bool(faults),
            "first_fault_slot": faults[0]["id"] if faults else None,
            "additional_turn_requests_after_first_fault": len(rows) - rows.index(faults[0]) - 1 if faults else 0,
            "slot_replacements": 0},
        "arms": arms, "pairs": pairs, "both_success_cost_pairs": len(both),
        "both_success_median_reported_tokens": {"T": T_median, "N": N_median},
        "both_success_median_active_seconds": {arm: statistics.median(p[arm + "_seconds"] for p in both) if both else None for arm in ("T", "N")},
        "both_success_cost_selection_warning": "Excludes failures; do not infer unconditional efficiency from survivor costs.",
        "incomplete_slots": [e["id"] for e in freeze["schedule"] if e["id"] not in {r["id"] for r in rows}],
        "rows": rows}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = describe(args.directory)
    if args.output:
        args.output.write_bytes(json.dumps(result, indent=2).encode() + b"\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "pairs")}, indent=2))
