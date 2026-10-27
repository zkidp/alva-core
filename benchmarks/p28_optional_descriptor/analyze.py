"""Recompute bounded P28 results from its SHA-verified private archive only.

No provider calls. No previous studies' archives or candidates are consumed.
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p28_optional_descriptor.pilot import HERE, summarize, save, sha, canonical


def analyze(archive):
    manifest = json.loads((HERE / "ARCHIVE.json").read_text())
    assert sha(archive.read_bytes()) == manifest["sha256"], "P28_ARCHIVE_SHA256_MISMATCH"
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    results = json.loads((HERE / "RESULTS.json").read_text())
    rows = []
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == manifest["entries"]
        for entry in frozen["schedule"]:
            prefix = entry["id"] + "/"
            if prefix + "result.json" not in z.namelist():
                break  # common infrastructure HOLD; never synthesize an unrun slot
            record = json.loads(z.read(prefix + "result.json"))
            evidence = json.loads(z.read(prefix + "linux.json")) if prefix + "linux.json" in z.namelist() else {}
            obs = [json.loads(line) for line in z.read(prefix + "observer.jsonl").decode().splitlines()] if prefix + "observer.jsonl" in z.namelist() else []
            rows.append(summarize(entry, record, evidence, obs))
            local_params = json.loads(z.read(prefix + "thread-start.json"))
            assert local_params["developerInstructions"] == entry["developer_instructions"]
            assert local_params["dynamicTools"] == frozen["tools"]
            assert local_params["model"] == frozen["config"]["model"]
            prompts = [e["params"]["item"]["content"][0]["text"] for e in record.get("events", [])
                       if e.get("method") == "item/started" and e.get("params", {}).get("item", {}).get("type") == "userMessage"]
            if record.get("model_tasks_started") and not record.get("infrastructure_hold"):
                assert prompts == [entry["prompt"]], "Actual model input drift"
    assert rows == results["slots"], "P28 derived summaries cannot be reproduced"
    if len(rows) == 2 and results["status"] == "CLOSED_COMPLETE":
        c1, c0 = rows
        fewer = c1["describe_operation_calls"] < c0["describe_operation_calls"]
        if not fewer:
            classification = "NO_OBSERVED_DESCRIPTOR_POLICY_UPTAKE"
        elif not c1["staged_target_changed_before_interrupt"]:
            classification = "DESCRIPTOR_CALLS_REDUCED_NO_OBSERVED_STAGE_PROGRESS_BENEFIT"
        elif c0["staged_target_changed_before_interrupt"]:
            classification = "BOTH_CONDITIONS_REACHED_CONNECTED_STAGING"
        else:
            classification = "SINGLE_PAIR_OPTIONAL_DESCRIPTOR_STAGE_PROGRESS_SIGNAL"
    else:
        classification = "COMMON_INFRASTRUCTURE_HOLD_NO_PAIRED_INTERPRETATION"
        fewer = None
    analysis = {"status": results["status"], "classification": classification,
        "descriptor_calls_reduced": fewer, "primary_unit": "one HE41 observation per condition",
        "order": [e["condition"] for e in frozen["schedule"]], "archive_sha256": manifest["sha256"],
        "no_causal_or_generalization_claim": True, "comparison": [{k: r[k] for k in (
            "condition", "describe_operation_calls", "first_construction_tool_ordinal", "first_connected_tool_ordinal",
            "staged_target_changed_before_interrupt", "successful_commits", "fresh_authority_target_changed",
            "independent_final_status", "disposition", "tool_calls", "usage", "stop_reason", "interrupt_ack",
            "observer_calls", "observer_elapsed_seconds")} for r in rows]}
    validation = {"status": "PASS", "archive_sha256": "PASS", "derived_results_recomputed": "PASS",
        "actual_prompt_and_developer_binding": "PASS", "maximum_model_tasks": 2,
        "model_tasks_started": sum(r["model_tasks_started"] for r in rows),
        "fresh_thread_ids": None, "fresh_sandbox_workspaces": "separate P23 instances per slot",
        "observer_associations_complete": all(r["observer_complete"] for r in rows),
        "terminal_statuses": [r["terminal_status"] for r in rows],
        "interrupt_acknowledgments": [r["interrupt_ack"] for r in rows],
        "no_hard_provider_token_cap_claim": True, "generation_calls_in_analysis": 0,
        "historical_frozen_artifacts_modified": False}
    with zipfile.ZipFile(archive) as z:
        ids = [json.loads(z.read(r["id"] + "/result.json")).get("thread_id") for r in rows]
        validation["fresh_thread_ids"] = bool(all(ids) and len(set(ids)) == len(ids))
    save(HERE / "ANALYSIS.json", analysis)
    save(HERE / "VALIDATION.json", validation)
    print(json.dumps({"classification": classification, "validation": validation}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("archive", type=Path)
    analyze(p.parse_args().archive)
