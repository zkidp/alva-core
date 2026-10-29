"""Reproduce public derived results from the controlled P32 archive only.

This never executes candidate code or starts a model. Independent checks were
already run inside P22/P23 isolation by the frozen evaluator at slot close.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p32_native_mm01 import pilot as p


def analyze(archive):
    f = json.loads((p.HERE / "FREEZE.json").read_text())
    manifest = json.loads((p.HERE / "ARCHIVE.json").read_text())
    assert p.sha(archive.read_bytes()) == manifest["sha256"]
    assert archive.stat().st_size == manifest["bytes"]
    for name, digest in f["files"].items():
        assert p.sha((ROOT / name).read_bytes()) == digest, name
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == manifest["entries"]
        assert not any(Path(n).name in ("auth.json", "config.toml") for n in z.namelist())
        entry = f["schedule"][0]
        prefix = entry["id"] + "/"
        get = lambda name: json.loads(z.read(prefix + name))
        record, evidence = get("record.json"), get("linux.json")
        observations = [json.loads(s) for s in z.read(prefix + "observer.jsonl").decode().splitlines()] if prefix + "observer.jsonl" in z.namelist() else []
        request, thread, policy = get("turn-start.json"), get("thread-start.json"), get("policy-validation.json")
        assert request["input"] == [{"type": "text", "text": entry["prompt"]}]
        assert request["effort"] == "low" and thread["developerInstructions"] == f["developer_instructions"]
        assert thread["dynamicTools"] == f["tools"]
        assert policy["status"] == "PASS" and len(policy["server"]["enabled_tools"]) == 20
        assert policy["server"]["tools"] == {"commit_transaction": {"approval_mode": "approve"}}
        assert policy["server"]["default_tools_approval_mode"] == "auto"
        assert policy["destructive_annotation_preserved"]
        assert policy["native_schema_sha256"] == p.sha(p.mm.canonical(f["native_tools"]))
        assert record["model_tasks_started"] == 1
        assert evidence["status"] == "CLOSED" and not evidence.get("error") and not evidence.get("worker_error")
        result = p.summarize(entry, record, evidence, observations)
        public = json.loads((p.HERE / "RESULTS.json").read_text())
        assert result == public["slots"][0]
        assert record["freeze_commit"] == public["freeze_commit"]
        assert public["scheduled"] == public["executed"] == 1
        assert subprocess.check_output(["git", "show", record["freeze_commit"] + ":benchmarks/p32_native_mm01/FREEZE.json"], cwd=ROOT) == (p.HERE / "FREEZE.json").read_bytes()
        native = [r for r in evidence["calls"] if r.get("request", {}).get("method") == "tools/call"]
        events = record.get("events", [])
        native_items = [e["params"]["item"] for e in events if e.get("method") == "item/started" and e.get("params", {}).get("item", {}).get("type") == "mcpToolCall"]
        ordinals = {r["id"]: i for i, r in enumerate(native_items, 1)}
        stages = []
        for i, r in enumerate(native, 1):
            params, response = r["request"]["params"], r["response"]
            call_id = params.get("_meta", {}).get("callId")
            stages.append({"native_dispatch_ordinal": i, "native_model_tool_ordinal": ordinals.get(call_id),
                "call_id": call_id, "operation": params["name"], "isError": bool(response.get("isError")),
                "target_change_after_operation": any(o["call_id"] == call_id and o["changed_from_transaction_start"] for o in observations)})
        checks = [{"operation": r["request"]["params"]["name"], "problems": r["response"].get("structuredContent", {}).get("problems"),
                   "isError": bool(r["response"].get("isError"))} for r in native if r["request"]["params"]["name"] == "check_transaction"]
        final = evidence["final"]
        independent = {k: {"exit": v["exit"], "stdout_sha256": p.sha(v.get("stdout", "").encode()),
            "stderr_sha256": p.sha(v.get("stderr", "").encode())} for k, v in final.items() if isinstance(v, dict) and "exit" in v}
        final_file_hashes = {name: p.sha(base64.b64decode(data)) for name, data in evidence["final_files"].items()}
        commit_results = [r["response"].get("structuredContent") for r in native if r["request"]["params"]["name"] == "commit_transaction"]
        authority_matches_commit = bool(commit_results) and commit_results[-1].get("revision") == evidence["final_authority"].get("project_revision")
        other_bodies_preserved = all(before == evidence["final_authority"]["bodies"].get(name)
            for name, before in evidence["initial_authority"]["bodies"].items() if name != f["task"]["target"])
        assert authority_matches_commit == result["air_authority_published"]
        analysis = {"schema": "p32-derived-analysis/v1", "archive_sha256": manifest["sha256"],
            "stages": stages, "transaction_checks": checks, "commit_results": commit_results,
            "independent_evaluation": independent, "final_file_hashes": final_file_hashes,
            "fresh_process_authority_matches_commit_revision": authority_matches_commit,
            "non_target_bodies_preserved": other_bodies_preserved,
            "first_connected_target_native_ordinal": next((s["native_dispatch_ordinal"] for s in stages if s["target_change_after_operation"]), None),
            "observer_calls": result["observer_calls"], "observer_is_model_feedback": False,
            "terminal_status": result["terminal_status"], "stop_reason": result["stop_reason"],
            "usage": result["usage"], "elapsed_seconds": result["elapsed_seconds"],
            "historical_T_pooling": False, "analysis_model_generation_calls": 0}
    historical = subprocess.check_output(["git", "diff", "--name-only", p.BASE, "--", "benchmarks/mm01_pilot", "integrations/codex/native_commit_authorization.py", "docs/native-mcp-commit-authorization.md", "tests/integrations/native_commit_authorization_test.py", "tests/integrations/p31_synthetic_provider.py", "tests/integrations/test_native_commit_authorization.py"], cwd=ROOT, text=True)
    assert historical == ""
    validation = {"status": "PASS", "archive_hash_and_size": True, "derived_result_reproduced": True,
        "exact_pre_execution_freeze_preserved": True, "exact_runtime_preserved": True,
        "actual_prompt_skill_tools_and_policy_bound": True, "scheduled": 1, "model_tasks_started": 1,
        "no_rerun_or_replacement": True, "historical_artifacts_modified": False,
        "analysis_model_generation_calls": 0, "independent_evaluation": "Linux OS isolation, frozen P30 evaluator",
        "raw_evidence_in_git": False, "historical_T_pooling": False}
    p.save(p.HERE / "ANALYSIS.json", analysis)
    p.save(p.HERE / "VALIDATION.json", validation)
    print(json.dumps({"validation": validation, "result": result, "stages": stages, "commit_results": commit_results}, indent=2))


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("archive", type=Path)
    analyze(a.parse_args().archive)
