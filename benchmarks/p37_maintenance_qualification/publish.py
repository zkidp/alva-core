"""Verify a completed controlled wave and publish derived evidence, no execution."""
import argparse
import base64
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha
from benchmarks.maintenance_design.feasibility import save
from benchmarks.p37_maintenance_qualification.qualification import scope

HERE = Path(__file__).parent


def verify(folder):
    summary = json.loads((folder / "QUALIFICATION-RESULTS.json").read_text())
    archive = json.loads((folder / "ARCHIVE.json").read_text())
    assert sha((folder / "RAW.zip").read_bytes()) == archive["sha256"]
    assert (folder / "RAW.zip").stat().st_size == archive["bytes"]
    registry = json.loads((HERE / "CANDIDATE-REGISTRY.json").read_text())
    bundles = json.loads((HERE / "TASK-BUNDLES.json").read_text())
    assert sha((HERE / "CANDIDATE-REGISTRY.json").read_bytes()) == summary["registry_sha256"]
    assert [r["id"] for r in summary["rows"]] == registry["selection_order"]
    with zipfile.ZipFile(folder / "RAW.zip") as z:
        assert z.testzip() is None
        assert sorted(z.namelist()) == sorted(i + "-raw.json" for i in registry["selection_order"])
        for row, candidate in zip(summary["rows"], registry["candidates"]):
            name = row["id"] + "-raw.json"
            raw = json.loads(z.read(name))
            assert sha(canonical(raw)) == row["raw_canonical_sha256"]
            if row["disposition"] == "INCONCLUSIVE_WITH_BLOCKER":
                assert row["reason"]
                continue
            assert raw["baseline_regression"]["status"] == row["baseline"]["regression"]
            assert raw["baseline_goal"]["status"] == row["baseline"]["goal"]
            assert "test result: FAILED" in raw["baseline_goal"]["tests"]["stdout"]
            for key in ("goal", "regression"):
                assert raw["text"][key]["status"] == row["text"][key]
            before_text = [e["snapshot"] for e in raw["baseline_inspection"] if e["event"] == "trusted_baseline"][-1]
            after_text = [e["snapshot"] for e in raw["text_inspection"] if e["event"] == "trusted_baseline"][-1]
            assert scope(before_text, after_text, candidate["authorized_functions"]) == row["text"]["scope"]
            original_source = decode(bundles[row["id"]], candidate["bundle_sha256"])
            assert [p for p, b in original_source.items() if base64.b64decode(raw["text"]["source"][p]) != b] == row["text"]["changed_files"]
            if row["disposition"] != "QUALIFIED_MATCHED":
                assert raw.get("native_error") or row["reason"]
                continue
            n = row["native"]
            assert len(raw["native_schemas"]) == 20
            ledger = raw["native_ledger"]
            dispatches = [e for e in ledger if e["event"] == "native_dispatch" and e.get("params", {}).get("name") == "commit_transaction"]
            assert len(dispatches) == n["actual_commit_dispatches"] == 1
            assert not dispatches[0]["response"].get("isError")
            decisions = [e["decision"] for e in ledger if e["event"] == "scope_decision"]
            assert decisions == [n["guard"]] and decisions[0]["status"] == "SCOPE_ALLOWED"
            assert dispatches[0]["response"]["structuredContent"]["revision"] == n["fresh_project_revision"]
            assert n["fresh_body_revisions"] == n["staged_bodies"]
            final_state = [e["snapshot"] for e in ledger if e["event"] == "trusted_baseline"][-1]
            assert scope(raw["native_before"], final_state, candidate["authorized_functions"]) == n["scope"] == "PASS"
            assert sha(canonical(raw["native_before"])) == decisions[0]["baseline_sha256"]
            assert sha(canonical(final_state)) == decisions[0]["staged_sha256"]
            calls = raw["native_calls"]
            commit_index = next(i for i, c in enumerate(calls) if c["operation"] == "commit_transaction")
            fresh = calls[commit_index + 1:]
            fresh_begin = next(c for c in fresh if c["operation"] == "begin_transaction")
            assert fresh_begin["response"]["structuredContent"]["project_revision"] == n["fresh_project_revision"]
            actual_roots = {c["arguments"]["entity"]: c["response"]["structuredContent"]["slots"]["body"][0]
                            for c in fresh if c["operation"] == "inspect_entity"}
            assert actual_roots == n["fresh_body_revisions"]
            source = decode(bundles[row["id"]], candidate["bundle_sha256"])
            final_files = raw["native_final"]["files"]
            assert "alva-air/current" in final_files
            assert all(base64.b64decode(final_files[p]) == b for p, b in source.items())
            for key in ("goal", "regression"):
                assert raw["native_final"][key]["status"] == n[key] == "PASS"
    assert sum(summary["disposition_counts"].values()) == summary["registered_count"] == 4
    return summary, archive


def main(a):
    previous, old_archive = verify(a.first)
    result, archive = verify(a.final)
    assert result["model_generation_calls"] == result["input_token_api_calls"] == 0
    assert previous == json.loads((HERE / "waves/wave-01.json").read_text())
    wave_path = HERE / "waves/wave-02.json"
    if wave_path.exists():
        assert json.loads(wave_path.read_text()) == result, "Never overwrite an existing wave"
    save(wave_path, result)
    save(HERE / "QUALIFICATION-RESULTS.json", result)
    attempts = json.loads((HERE / "ENGINEERING-ATTEMPTS.json").read_text())
    entry = {"id": "wave-02", "execution_commit": result["execution_commit"], "ci_run": 41112699596,
        "summary": "waves/wave-02.json", "dispositions": result["disposition_counts"],
        "registered_count": 4, "matched_qualified_count": result["matched_qualified_count"],
        "raw_zip_sha256": archive["sha256"], "raw_zip_bytes": archive["bytes"],
        "actions_artifact_id": 13004890946, "actions_artifact_sha256": "bf8c87c9e688722d46dbf14195fb23655162dc75b0f335eb6d21cc8526fc1935"}
    if len(attempts["completed_waves"]) == 1:
        attempts["completed_waves"].append(entry)
    else:
        assert attempts["completed_waves"][1] == entry
    attempts["exploratory_waves_closed"] = True
    attempts["subsequent_ci"] = "Zero-model regression repeats of the fixed wave-02 implementation, not new candidate search, witness alternatives or formal model slots; own raw logs/artifacts retained per run."
    save(HERE / "ENGINEERING-ATTEMPTS.json", attempts)
    save(HERE / "ARCHIVES.json", {"wave-01": old_archive, "wave-02": archive,
        "local_controlled_paths": [".local/p37-qualification/wave-01/RAW.zip", ".local/p37-qualification/wave-02/RAW.zip"],
        "raw_archives_committed": False})
    save(HERE / "VALIDATION.json", {"status": "PASS", "registration_commit": result["registration_commit"],
        "both_wave_archives_integrity": "PASS", "all_candidate_raw_hashes_recomputed": True,
        "goal_regression_results_match_actual_execution": True, "guard_commit_fresh_scope_conjunction_verified": True,
        "initial_failures_preserved": True, "registered_definitions_and_assertions_changed": False,
        "final_registered_count": 4, "final_matched_qualified_count": result["matched_qualified_count"],
        "engineering_authorship": "Codex; no independent human review or model success claimed",
        "model_generation_calls": 0, "input_token_api_calls": 0, "formal_model_execution_authorized": False})
    print("Both P37 wave archives verified; all failed and final dispositions retained; no model calls")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("first", type=Path)
    p.add_argument("final", type=Path)
    main(p.parse_args())
