"""Post-closure, read-only derivation from the verified MM01 archive only.

Never executes candidates or providers. Public output is sanitized stages,
diagnostic codes/digests and accounting, not transcripts or candidate code.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.mm01_pilot import pilot
from benchmarks.p27_bottleneck.audit import extract_calls, usage_events, bracket, classify
from integrations.benchmark_runtime_v2.freeze import canonical, sha

HERE = Path(__file__).resolve().parent


def diagnostics(value):
    found = []
    def walk(v):
        if isinstance(v, dict):
            if isinstance(v.get("code"), str) or isinstance(v.get("error_code"), str):
                found.append({"code": v.get("code") or v.get("error_code"),
                              "message_sha256": sha(str(v.get("message", "")).encode())})
            for child in v.values(): walk(child)
        elif isinstance(v, list):
            for child in v: walk(child)
        elif isinstance(v, str) and v[:1] in ("{", "["):
            try: walk(json.loads(v))
            except ValueError: pass
    walk(value)
    return found


def main(archive):
    manifest = json.loads((HERE / "ARCHIVE.json").read_text())
    assert sha(archive.read_bytes()) == manifest["sha256"]
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    results = json.loads((HERE / "RESULTS.json").read_text())
    assert results["status"] == "CLOSED_COMPLETE" and results["executed"] == 2
    original = subprocess.check_output(["git", "show", results["freeze_commit"] + ":benchmarks/mm01_pilot/FREEZE.json"], cwd=ROOT)
    assert original == (HERE / "FREEZE.json").read_bytes()
    stages = []
    thread_ids, turn_ids, host_blocks = set(), set(), []
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        assert len(names) == len(set(names)) == manifest["entries"]
        assert not any("auth" in p.lower() or "model/" in p for p in names)
        read = lambda p: json.loads(z.read(p))
        assert read("STARTED.json")["freeze_commit"] == results["freeze_commit"]
        member_hashes = {p: sha(z.read(p)) for p in names}
        for entry, public in zip(frozen["schedule"], results["slots"]):
            prefix = entry["id"] + "/"
            record, linux = read(prefix + "record.json"), read(prefix + "linux.json")
            thread_ids.add(record["thread_id"])
            turn_ids.add(record["turn_id"])
            thread, turn = read(prefix + "thread-start.json"), read(prefix + "turn-start.json")
            cfg = read(prefix + "config.json")
            assert thread["model"] == frozen["config"]["model"]
            assert thread["developerInstructions"] == frozen["developer_instructions"]
            assert thread["dynamicTools"] == frozen["tools"]
            assert turn["input"] == [{"type": "text", "text": entry["prompt"]}]
            assert turn["effort"] == frozen["config"]["effort"]
            assert cfg["bundle"] == frozen["task"]["bundle"] and cfg["vectors"] == frozen["assertions"]
            assert linux["status"] == "CLOSED" and not linux.get("worker_error") and not linux.get("error")
            obs = [json.loads(line) for line in z.read(prefix + "observer.jsonl").decode().splitlines()] if prefix + "observer.jsonl" in names else []
            assert pilot.summarize(entry, record, linux, obs) == public
            calls, usage = extract_calls(record["events"]), usage_events(record["events"])
            assert len(calls) == record["tool_calls"]
            native = [c for c in linux["calls"] if c.get("request", {}).get("method") == "tools/call"]
            indexed = {c["request"]["params"].get("_meta", {}).get("callId"): c for c in native}
            sequence = []
            completed_items = {e["params"]["item"]["id"]: e["params"]["item"] for e in record["events"]
                               if e.get("method") == "item/completed"}
            for i, c in enumerate(calls, 1):
                n = indexed.get(c["item_id"], {})
                answer = n.get("response", {})
                content = answer.get("structuredContent", {})
                host_error = completed_items.get(c["item_id"], {}).get("error")
                blocked = bool(c["operation"] == "commit_transaction" and not n and host_error and
                    host_error.get("message") == "MCP tool call requires approval, but approval policy is never")
                if blocked:
                    host_blocks.append({"id": entry["id"], "model_tool_ordinal": i,
                        "code": "HOST_APPROVAL_NEVER_COMMIT_DENIED_BEFORE_NATIVE_DISPATCH",
                        "message": host_error["message"], "event_index": c["end"],
                        "request_reached_isolated_native_mcp": False})
                sequence.append({"model_tool_ordinal": i, "operation": c["operation"], "action": c["action"],
                    "stage": classify(c["action"], c["operation"]), "failed_envelope": c["failed"],
                    "structured_ok": content.get("ok"), "diagnostics": diagnostics(answer),
                    "native_dispatched": bool(n) if c["operation"] else None,
                    "host_commit_denied": blocked,
                    "host_error_sha256": sha(canonical(host_error)) if host_error else None,
                    "request_sha256": sha(canonical(n["request"])) if n else None,
                    "response_sha256": sha(canonical(answer)) if n else None,
                    "usage_interval": bracket(usage, c["start"], c["end"] if c["end"] is not None else c["start"])})
            dynamic = [e["params"]["arguments"] for e in record["events"] if e.get("method") == "item/tool/call"]
            counts = dict(Counter(d["action"] for d in dynamic))
            edits = [c for c in linux["calls"] if c.get("action") == "edit"]
            summaries = {"id": entry["id"], "dynamic_action_counts": counts,
                "source_edit_attempts": len(edits),
                "accepted_source_edits": sum(c.get("response", {}).get("accepted") is True for c in edits),
                "rejected_source_edits": sum(c.get("response", {}).get("accepted") is not True for c in edits),
                "sequence": sequence, "readonly_staging_observations": [
                    {k: v for k, v in o.items() if k not in ("call_id", "transaction_id")} for o in obs],
                "appserver_native_commit_attempts": sum(c["operation"] == "commit_transaction" for c in calls),
                "appserver_native_errors": sum(c["failed"] for c in calls if c["operation"]),
                "appserver_native_parameter_errors": sum(bool(c["answer"].get("isError")) for c in calls if c["operation"]),
                "native_check_responses": [{"structured_ok": c["response"].get("structuredContent", {}).get("ok"),
                    "problems_count": len(c["response"].get("structuredContent", {}).get("problems", []))
                        if isinstance(c["response"].get("structuredContent", {}).get("problems"), list) else None,
                    "diagnostics": diagnostics(c["response"]), "response_sha256": sha(canonical(c["response"]))}
                    for c in native if c["request"]["params"]["name"] == "check_transaction"],
                "active_turn_terminal": record["terminal_status"], "resources": record["usage"]["total"],
                "token_observation_threshold_reached": record["usage"]["total"]["totalTokens"] >= 600000,
                "tool_limit_reached": record["tool_calls"] >= 80,
                "wall_observation_limit_reached": record["elapsed_seconds"] >= 480,
                "final_evaluator_outputs_sha256": sha(canonical(linux["final"]))}
            stages.append(summaries)
    assert len(thread_ids) == len(turn_ids) == 2
    pilot.save(HERE / "ANALYSIS.json", {"archive_sha256": manifest["sha256"], "slots": stages})
    pilot.save(HERE / "SCIENTIFIC-DISPOSITION.json", {
        "execution_record": results["status"], "model_tasks_executed": 2, "repeat_or_replacement": False,
        "scientific_disposition": "NATIVE_COMMIT_HOST_AUTHORIZATION_BLOCKER" if host_blocks else "PAIR_COMPLETED",
        "host_blockers": host_blocks, "clean_paired_utility_comparison": not bool(host_blocks),
        "text_completed_correct_maintenance": results["slots"][0]["disposition"] == "COMPLETED_CORRECT_MAINTENANCE",
        "native_staged_target_change_observed": results["slots"][1]["staged_target_change_observed"],
        "native_effective_commit": results["slots"][1]["native_commits"] > 0,
        "native_uncommitted_behavior": "NOT_INDEPENDENTLY_EVALUATED",
        "no_claim": ["native inability to attach target", "native behavioral incorrectness of staged candidate",
                     "Text superiority", "intrinsic language causality", "agent correctness increment"],
        "next_action": "STOP_FOR_REVIEW; no permission repair, additional slot or rerun in this node"})
    pilot.save(HERE / "VALIDATION.json", {"status": "EVIDENCE_VALIDATED_WITH_NATIVE_COMMIT_HOST_BLOCKER" if host_blocks else "PASS",
        "model_tasks_executed": 2, "provider_generation_requests": None, "input_counter_calls": 0, "extra_tasks": 0,
        "freeze_commit": results["freeze_commit"], "freeze_unchanged": True, "archive_sha256_verified": True,
        "archive_member_hashes": member_hashes, "actual_inputs_match_freeze": True,
        "fresh_thread_and_turn_ids": True, "independent_task_and_regression_scores_recomputed": True,
        "candidate_execution": "existing Linux OS namespaces only", "raw_data_in_git": False,
        "core_aep_mcp_skill_changed": False, "historical_frozen_artifacts_changed": False,
        "analysis_provider_calls": 0, "unexercised_stale_recovery": "NOT_APPLICABLE",
        "preflight_gap": "begin/inspect/abort passed but AppServer commit authorization was not exercised",
        "host_blockers": host_blocks})
    print(json.dumps([{k: s[k] for k in ("id", "dynamic_action_counts", "source_edit_attempts", "accepted_source_edits", "native_check_responses")} for s in stages], indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("archive", type=Path)
    main(p.parse_args().archive)
