"""Verify controlled archive and derive public Host-guard evidence; no calls."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p34_scope_guard.cases import case, CASES
from benchmarks.native_prospective.pilot import save
from integrations.benchmark_runtime_v2.freeze import sha
HERE = Path(__file__).resolve().parent


def publish(folder):
    manifest = json.loads((folder / "ARCHIVE.json").read_text())
    archive = folder / "RAW.zip"
    assert sha(archive.read_bytes()) == manifest["sha256"] and archive.stat().st_size == manifest["bytes"]
    with zipfile.ZipFile(archive) as z:
        summary = json.loads(z.read("RESULTS.json"))
        assert summary == json.loads((folder / "RESULTS.json").read_text())
        assert summary["status"] == "PASS" and summary["model_generation_calls"] == summary["input_token_api_calls"] == 0
        assert [r["id"] for r in summary["rows"]] == list(CASES)
        for row in summary["rows"]:
            name = row["id"]
            fixed = case(name)
            prefix = name + "/isolated-service/"
            guard_data, native_data = z.read(prefix + "guard.jsonl"), z.read(prefix + "linux.json")
            assert sha(guard_data) == row["guard_evidence_sha256"] and sha(native_data) == row["native_evidence_sha256"]
            ledger = [json.loads(line) for line in guard_data.decode().splitlines()]
            native = json.loads(native_data)
            commit_id = row["commit_appserver_call_id"]
            decisions = [e for e in ledger if e["event"] == "scope_decision" and e["params"].get("_meta", {}).get("callId") == commit_id]
            assert len(decisions) == 1 and decisions[0]["decision"] == row["scope_decision"]
            assert row["scope_decision"]["status"] == fixed["expected_scope"]
            assert row["check_transaction"] == {"problems": []}
            commits = [e for e in ledger if e["event"] == "native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
            allowed = fixed["expected_scope"] == "SCOPE_ALLOWED"
            assert len(commits) == int(allowed) == row["native_commit_dispatches"]
            if allowed:
                assert commits[0]["params"]["_meta"]["callId"] == commit_id
                assert row["final_authority"]["project_revision"] == commits[0]["response"]["structuredContent"]["revision"]
                assert row["independent_task"] == row["independent_regression"] == "PASS"
            else:
                assert row["authority_unchanged_when_denied"] and native["initial_authority"] == native["final_authority"]
                assert row["independent_task"] == "TEST_FAIL" and row["independent_regression"] == "PASS"
            assert row["model_tool_approval_error"] is None
            assert row["baseline_attempted_before_mutation"] and row["raw_commit_endpoint_unavailable"]
        assert summary["native_commit_dispatches"] == summary["denied_commits"] == 2
    for name, digest in summary["executed_file_sha256"].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    policies = {name: {"policy": case(name)["policy"], "bundle_sha256": case(name)["bundle"]["payload_sha256"],
        "expected_scope": case(name)["expected_scope"]} for name in CASES}
    validation = {"HOST_GUARD_INTEGRATED": "PASS", "MM02_SHARED_SPILL_BLOCKED": "PASS",
        "MM02_NONSHARED_COMMIT_ALLOWED": "PASS", "MM01_VALID_COMMIT_ALLOWED": "PASS",
        "UNKNOWN_SCOPE_FAIL_CLOSED": "PASS",
        "INDEPENDENT_BEHAVIOR": {"allowed_cases": "task/regression PASS", "denied_cases": "unchanged baseline; new task expected FAIL; regression PASS"},
        "archive_sha256_verified": True, "appserver_native_call_ids_matched": True,
        "historical_artifacts_modified": False, "model_generation_calls": 0, "input_token_api_calls": 0}
    save(HERE / "RESULTS.json", summary)
    save(HERE / "POLICIES.json", policies)
    save(HERE / "ARCHIVE.json", manifest)
    save(HERE / "VALIDATION.json", validation)
    print("P34 archive, actual dispatch, policy and independent results verified; model calls=0")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    publish(p.parse_args().folder)
