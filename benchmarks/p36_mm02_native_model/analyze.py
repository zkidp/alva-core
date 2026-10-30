"""Recompute scientific disposition from controlled actual events; no model calls."""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha


def lines(path):
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def classify(*, infrastructure, resource, committed, correct):
    if infrastructure:
        return "INFRASTRUCTURE_HOLD"
    if resource:
        return "RESOURCE_CENSORED"
    if committed:
        return "COMPLETED_CORRECT_MAINTENANCE" if correct else "COMMITTED_INCORRECT_MAINTENANCE"
    return "NO_COMMITTED_CANDIDATE"


def analyze(frozen, record, folder):
    evidence = json.loads((folder / "linux.json").read_text())
    guard = lines(folder / "guard.jsonl")
    observations = lines(folder / "observer.jsonl")
    initial, final = evidence.get("initial_authority", {}), evidence.get("final_authority", {})
    before, after = initial.get("bodies", {}), final.get("bodies", {})
    target = frozen["task"]["target"]
    changed = [f for f in before if after.get(f) != before[f]]
    source = decode(frozen["task"]["bundle"], frozen["task"]["bundle"]["payload_sha256"])
    final_files = evidence.get("final_files", {})
    projection_same = all(final_files.get(p) == base64.b64encode(b).decode() for p, b in source.items())
    items = [e["params"]["item"] for e in record.get("events", [])
             if e.get("method") == "item/completed" and e.get("params", {}).get("item", {}).get("type") == "mcpToolCall"]
    app_commits = {i["id"]: i for i in items if i["tool"] == "commit_transaction"}
    decisions = [e for e in guard if e["event"] == "scope_decision"]
    seen_decisions = {e["params"].get("_meta", {}).get("callId") for e in decisions}
    decisions += [e for e in guard if e["event"] == "scope_denied_no_native_dispatch"
                  and e.get("params", {}).get("name") == "commit_transaction"
                  and e["params"].get("_meta", {}).get("callId") not in seen_decisions]
    dispatches = [e for e in guard if e["event"] == "native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
    attempts = []
    errors = []
    for row in decisions:
        params = row["params"]
        call_id = params.get("_meta", {}).get("callId")
        native = [d for d in dispatches if d["params"].get("_meta", {}).get("callId") == call_id]
        item = app_commits.get(call_id)
        status = row["decision"]["status"]
        if not call_id or item is None:
            errors.append("COMMIT_APP_GUARD_CALL_ID_MISMATCH")
        if len(native) != int(status == "SCOPE_ALLOWED"):
            errors.append("GUARD_NATIVE_DISPATCH_MISMATCH")
        response = native[0]["response"] if native else None
        attempts.append({"appserver_call_id": call_id, "appserver_status": item.get("status") if item else None,
            "appserver_error": item.get("error") if item else None, "decision": row["decision"],
            "native_dispatches": len(native), "native_is_error": response.get("isError", False) if response else None,
            "native_commit": response.get("structuredContent") if response else None})
    if set(app_commits) != {a["appserver_call_id"] for a in attempts}:
        errors.append("UNMATCHED_APP_COMMIT")
    good = [a for a in attempts if a["native_dispatches"] == 1 and not a["native_is_error"]]
    published = "alva-air/current" in final_files
    fresh_match = bool(good and final.get("project_revision") == good[-1]["native_commit"].get("revision"))
    compiled = evidence.get("final", {})
    task = compiled.get("goal", {}).get("status", "UNKNOWN")
    regression = compiled.get("regression", {}).get("status", "UNKNOWN")
    scope = "PASS" if projection_same and set(before) == set(after) == set(frozen["task"]["functions"]) and changed == [target] and good and all(a["decision"]["status"] == "SCOPE_ALLOWED" for a in good) else "FAIL"
    infra = record.get("infrastructure_hold") or evidence.get("error") or evidence.get("worker_error") or errors
    if record.get("terminal_status") not in ("completed", "interrupted", "failed"):
        infra = infra or "TERMINAL_UNCONFIRMED"
    if record.get("terminal_status") == "failed":
        infra = infra or "APPSERVER_TURN_FAILED; inspect controlled terminal error"
    resource = record.get("stop_reason") in ("TOKEN_OBSERVATION_LIMIT", "TOOL_LIMIT", "WALL_OBSERVATION_LIMIT")
    correct = bool(good and published and fresh_match and task == regression == scope == "PASS")
    usage = record.get("usage")
    counts = {}
    operations = [c for c in evidence.get("calls", []) if c.get("request", {}).get("method") == "tools/call"]
    for operation in operations:
        name = operation["request"]["params"]["name"]
        counts[name] = counts.get(name, 0) + 1
    result = {"schema": "alva-p36-result/v1", "freeze_commit": record["freeze_commit"],
        "disposition": classify(infrastructure=bool(infra), resource=resource, committed=bool(good), correct=correct),
        "model_slots_started": record["model_tasks_started"], "model_turns": record["model_tasks_started"],
        "model_tool_calls": record.get("tool_calls"), "native_operation_counts": counts,
        "usage": usage, "usage_complete": record.get("usage_complete"), "provider_requests": None, "dollar_cost": None,
        "cached_tokens_subtracted": False, "hard_provider_token_cap": False,
        "elapsed_seconds": record.get("elapsed_seconds"), "terminal_status": record.get("terminal_status"),
        "stop_reason": record.get("stop_reason"), "interrupt_ack": record.get("interrupt_ack"),
        "infrastructure_hold": infra or None, "initial_authority": initial, "final_authority": final,
        "changed_bodies": changed, "target_changed": target in changed,
        "source_projection_unchanged": projection_same, "air_published": published,
        "authoritative_candidate_correct": correct,
        "fresh_revision_matches_commit": fresh_match, "task": task, "regression": regression, "scope": scope,
        "independent_project_check": compiled.get("check", {}).get("exit"),
        "independent_project_build": (compiled.get("build") or {}).get("exit"),
        "guard_allowed": sum(a["decision"]["status"] == "SCOPE_ALLOWED" for a in attempts),
        "guard_denied": sum(a["decision"]["status"] != "SCOPE_ALLOWED" for a in attempts),
        "native_commit_dispatches": len(dispatches), "successful_native_commits": len(good), "commit_attempts": attempts,
        "staged_target_change_observed": any(target in o.get("changed_functions", []) for o in observations),
        "observer_reads": sum(o["observer_calls"] for o in observations), "observer_feedback_to_model": False,
        "staged_observations": [{k: o[k] for k in ("call_id", "transaction_id", "after_operation", "baseline", "body_revisions", "changed_functions")} for o in observations],
        "native_operation_errors": sum(bool(o["response"].get("isError")) for o in operations),
        "raw_record_canonical_sha256": sha(canonical(record)), "raw_evidence_canonical_sha256": sha(canonical(evidence)),
        "historical_T_pooling": False, "engineering_witness_counted_as_model_success": False}
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    a = p.parse_args()
    frozen = json.loads((Path(__file__).parent / "FREEZE.json").read_text())
    record = json.loads((a.folder / "record.json").read_text())
    print(json.dumps(analyze(frozen, record, a.folder / "P36-MM02-S"), indent=2))
