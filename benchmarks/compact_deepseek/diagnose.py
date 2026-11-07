"""Post-run descriptive call/payload diagnosis; does not change the screen."""
from collections import Counter
import json
from pathlib import Path
import re
import statistics

from benchmarks.compact_deepseek.runner import save

HERE = Path(__file__).parent


def diagnose(directory):
    frozen = json.loads((HERE / "FREEZE.json").read_bytes())
    summary = json.loads((HERE / "RESULTS.json").read_bytes())
    pairs = {(p["task"], p["repeat"]) for p in summary["pairs"] if "ratio" in p}
    groups = {}
    for arm in ("T", "N"):
        selected = [json.loads((directory / r["id"] / "record.json").read_bytes()) for r in summary["rows"]
                    if r["arm"] == arm and (r["task"], r["repeat"]) in pairs]
        calls = Counter(e["name"] for r in selected for e in r["tool_events"])
        groups[arm] = {"matched_success_slots": len(selected),
            "provider_tool_count": len(frozen["provider_tools"][arm]),
            "provider_tool_schema_json_utf8_bytes": len(json.dumps(frozen["provider_tools"][arm]).encode()),
            "median_model_tool_calls": statistics.median(r["observed_tool_calls"] for r in selected),
            "median_submitted_chat_requests": statistics.median(r["submitted_chat_requests"] for r in selected),
            "model_tool_counts": dict(sorted(calls.items())),
            "returned_error_envelopes": sum(bool(e["response"].get("error") or e["response"].get("isError")) for r in selected for e in r["tool_events"]),
            "shared_check_test_failures": sum(e["response"].get("status") in ("COMPILE_FAIL", "TEST_FAIL", "CHECK_FAIL", "BUILD_FAIL")
                for r in selected for e in r["tool_events"] if e["name"] in ("study_check", "study_test"))}
    failed = []
    for row in summary["rows"]:
        if row["correct"]:
            continue
        r = json.loads((directory / row["id"] / "record.json").read_bytes())
        codes = Counter()
        for event in r["tool_events"]:
            if event["response"].get("error") or event["response"].get("isError"):
                codes.update(set(re.findall(r"\bE_[A-Z][A-Z0-9_]+\b", json.dumps(event["response"]))))
        failed.append({"id": r["id"], "stop_reason": r["stop_reason"], "outcome": r["outcome"],
                       "successful_native_commits": r.get("successful_native_commits"),
                       "accepted_body_replacements": sum(e["name"] == "replace_function_body" and not e["response"].get("isError") for e in r["tool_events"]),
                       "accepted_body_replacements_changing_staged_revision": sum(e["name"] == "replace_function_body"
                            and not e["response"].get("isError") and e["response"].get("structuredContent", {}).get("body_revision")
                            != e["arguments"].get("expected_body_revision") for e in r["tool_events"]),
                       "error_code_envelope_counts": dict(sorted(codes.items())),
                       "model_tool_counts": dict(Counter(e["name"] for e in r["tool_events"]))})
    return {"status": "POST_RUN_DESCRIPTIVE_ONLY", "arms_on_six_both_success_pairs": groups,
            "failed_slots": failed,
            "total_backend_call_count": None, "per_category_provider_tokens": None,
            "limitations": ["Logged schemas are bytes, not attributed provider tokens.",
                            "Error envelopes and common check/test failures are different metrics; Native admission errors cannot be equated to source compiler failures.",
                            "P34 internal Host inspection RPCs are not individually retained in this API trace; total backend call count is unavailable.",
                            "All raw Native model-dispatch receipts, scope snapshots and independent evaluation receipts remain retained privately."]}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("directory", type=Path)
    a = p.parse_args(); result = diagnose(a.directory); save(HERE / "DIAGNOSIS.json", result)
    print(json.dumps(result["arms_on_six_both_success_pairs"], indent=2))
