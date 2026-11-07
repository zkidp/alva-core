"""Prospective MIC-02 screen on normalized trusted receipts; no run launcher."""
import math
import statistics


def screen(design, rows):
    expected = {r["id"]: r for r in design["schedule"]}
    indexed = {}
    for row in rows:
        if row.get("id") not in expected or row["id"] in indexed:
            raise ValueError("Unexpected or duplicate slot")
        if any(row.get(k) != expected[row["id"]][k] for k in ("task", "arm", "repeat")):
            raise ValueError("Slot identity mismatch")
        if row.get("valid") is True and not row.get("provider_fault") and type(row.get("correct")) is not bool:
            raise ValueError("Trusted outcome must explicitly specify correct true/false")
        indexed[row["id"]] = row
    missing = sorted(set(expected) - set(indexed))
    invalid = [r["id"] for r in rows if r.get("provider_fault") or not all(r.get(k) is True for k in
               ("valid", "terminal_confirmed", "identity_match", "cleanup_confirmed", "evidence_bound"))]
    if missing or invalid:
        return {"disposition": "INCONCLUSIVE_INFRASTRUCTURE", "missing_slots": missing, "invalid_slots": invalid}
    counts = {arm: sum(r.get("correct") is True for r in rows if r["arm"] == arm) for arm in ("T", "N")}
    ratios = []
    excluded = []
    for task in design["selection"]["tasks"]:
        for repeat in (1, 2):
            pair = {r["arm"]: r for r in rows if (r["task"], r["repeat"]) == (task, repeat)}
            if not all(r.get("correct") is True for r in pair.values()):
                continue
            usable = True
            for r in pair.values():
                u = r.get("reported_usage") or {}
                fields = ("totalTokens", "inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens")
                if r.get("usage_complete") is not True or any(type(u.get(k)) is not int or u[k] < 0 for k in fields):
                    usable = False
                elif not (u["totalTokens"] > 0 and u["cachedInputTokens"] <= u["inputTokens"]
                          and u["reasoningOutputTokens"] <= u["outputTokens"]):
                    usable = False
            if not usable:
                excluded.append({"task": task, "repeat": repeat, "reason": "INCOMPLETE_OR_INVALID_USAGE"})
                continue
            ratio = pair["N"]["reported_usage"]["totalTokens"] / pair["T"]["reported_usage"]["totalTokens"]
            assert math.isfinite(ratio)
            ratios.append(ratio)
    result = {"correct_counts": counts, "both_success_cost_pairs": len(ratios),
              "excluded_cost_pairs": excluded, "paired_token_ratios": ratios,
              "median_paired_token_ratio": statistics.median(ratios) if ratios else None,
              "warning": "Success-conditioned diagnostic screen; report all failures and total resource use separately."}
    if len(ratios) < design["screen"]["minimum_both_success_pairs"]:
        result["disposition"] = "INCONCLUSIVE_INSUFFICIENT_PAIRED_SUCCESSES"
    elif counts["N"] >= counts["T"] and result["median_paired_token_ratio"] <= 1 - design["screen"]["minimum_relative_token_reduction"]:
        result["disposition"] = "EXPLORATORY_FAVORABLE_SIGNAL"
    else:
        result["disposition"] = "NO_EXPLORATORY_FAVORABLE_SIGNAL"
    return result
