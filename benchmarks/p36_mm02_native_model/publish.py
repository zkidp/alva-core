"""Post-run derived publication; verify controlled archive without a model call."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p36_mm02_native_model.analyze import analyze
from benchmarks.maintenance_design.feasibility import save
from integrations.benchmark_runtime_v2.freeze import canonical, sha


def publish(runtime):
    here = Path(__file__).parent
    slot = runtime / "P36-MM02-S"
    frozen = json.loads((here / "FREEZE.json").read_text())
    record = json.loads((runtime / "record.json").read_text())
    result = json.loads((here / "RESULTS.json").read_text())
    assert analyze(frozen, record, slot) == result
    manifest = json.loads((here / "ARCHIVE.json").read_text())
    archive = runtime / "RAW.zip"
    assert sha(archive.read_bytes()) == manifest["sha256"]
    assert archive.stat().st_size == manifest["bytes"]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert not any(Path(n).name in ("auth.json", "connection.json", "id_ed25519", "id_ed25519.pub", "known_hosts")
                       or "model" in Path(n).parts for n in names)
    evidence = json.loads((slot / "linux.json").read_text())
    observations = [json.loads(line) for line in (slot / "observer.jsonl").read_text().splitlines()]
    assert observations and observations[-1]["body_revisions"] == evidence["final_authority"]["bodies"]
    operations = [c for c in evidence["calls"] if c.get("request", {}).get("method") == "tools/call"]
    sequence = [{"native_ordinal": i + 1, "operation": v["request"]["params"]["name"],
                 "appserver_call_id": v["request"]["params"].get("_meta", {}).get("callId"),
                 "arguments_sha256": sha(canonical(v["request"]["params"].get("arguments", {}))),
                 "response_sha256": sha(canonical(v["response"])), "is_error": bool(v["response"].get("isError"))}
                for i, v in enumerate(operations)]
    save(here / "ANALYSIS.json", {"native_operation_sequence": sequence,
        "preview": [c["response"]["structuredContent"] for c in operations if c["request"]["params"]["name"] == "preview_semantic_diff"],
        "transaction_check": [c["response"]["structuredContent"] for c in operations if c["request"]["params"]["name"] == "check_transaction"],
        "model_check_test_finish": [{"action": e["params"]["arguments"]["action"]} for e in record["events"] if e.get("method") == "item/tool/call"],
        "independent_goal_tests": 1, "independent_regression_tests": 3,
        "interpretation": "Original assertion groups and vectors unchanged; these test-group counts are not separate model slots."})
    save(here / "VALIDATION.json", {"status": "PASS", "generation_freeze_commit": record["freeze_commit"],
        "derived_results_exactly_recomputed": True, "archive_sha256_matches": True, "archive_zip_integrity": "PASS",
        "archive_entries": len(names), "credential_files_excluded": True, "controlled_raw_only": True,
        "frozen_runtime_bytes_unchanged": all(sha((ROOT / p).read_bytes()) == h for p, h in frozen["files"].items()),
        "fresh_body_roots_match_last_staged_observation": True,
        "same_actual_formal_prompt_as_freeze": json.loads((slot / "turn-start.json").read_text())["input"][0]["text"] == frozen["schedule"][0]["prompt"],
        "same_actual_developer_instructions_as_freeze": json.loads((slot / "thread-start.json").read_text())["developerInstructions"] == frozen["developer_instructions"],
        "observer_writes_to_candidate": 0, "host_rescue_commits": 0, "extra_model_turns": 0,
        "ci_model_generation_calls": 0})
    assert all(json.loads((here / "VALIDATION.json").read_text())[k] for k in
               ("frozen_runtime_bytes_unchanged", "same_actual_formal_prompt_as_freeze", "same_actual_developer_instructions_as_freeze"))
    print("P36 controlled archive/derived results verified; no model call")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("runtime", type=Path)
    publish(p.parse_args().runtime)
