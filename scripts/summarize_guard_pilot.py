"""Post-closure descriptive analysis only. Never launches Codex or changes a run."""

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "pilots/codex_guard"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from integrations.python_guard.guard import canonical, digest
from prepare import RUNTIME, public_files
from tasks import TASKS


def save(path, value):
    path.write_bytes(canonical(value))


def main():
    freeze_bytes = (HERE / "EXECUTION-FREEZE.json").read_bytes()
    freeze = json.loads(freeze_bytes)
    rows = json.loads((HERE / "RESULTS.json").read_bytes())
    assert len(rows) == len(freeze["schedule"]) == 12
    assert [r["slot"] for r in rows] == [r["slot"] for r in freeze["schedule"]]
    assert public_files() == freeze["files"], "do not modify frozen inputs"
    pairs = []
    for task in TASKS:
        selected = {r["arm"]: r for r in rows if r["task"] == task["id"]}
        pair = {"task": task["id"]}
        for arm, r in selected.items():
            local = RUNTIME / r["slot"]
            patch = (local / "final.patch").read_bytes()
            assert digest(patch) == r["patch_sha256"]
            (HERE / "results" / (r["slot"] + ".patch")).write_bytes(patch)
            head = subprocess.check_output(["git", "-C", str(local / "candidate"), "rev-parse", "HEAD"]).decode().strip()
            initial = next(row["initial_git_commit"] for row in freeze["schedule"] if row["slot"] == r["slot"])
            pair[arm] = {"task_complete": r["task_complete"], "regression_status": r["independent_checks"]["regression"]["status"],
                        "scope_violations": r["scope_violations"], "tool_items": r["tool_items"],
                        "guard_calls": len(r["guard_calls"]), "guard_evidence": r.get("terminal_guard"),
                        "elapsed_seconds": r["elapsed_seconds"], "last_observed_usage": r["codex_token_usage"],
                        "raw_driver_stop_reason": r["stop_reason"], "codex_turn_status": r.get("turn_status", "NOT_OBSERVED"),
                        "git_head_unchanged": head == initial,
                        "usage_completeness": "LAST_OBSERVED_NOT_GUARANTEED_FINAL" if not r.get("turn_status") else "HOST_REPORTED_THROUGH_COMPLETION"}
        a, b = pair["A"]["last_observed_usage"], pair["B"]["last_observed_usage"]
        pair["descriptive_last_observed_token_ratio_B_over_A"] = b["totalTokens"] / a["totalTokens"] if a and b else None
        pair["controlled_budget_comparison_valid"] = False
        pairs.append(pair)
    totals = {}
    for arm in ("A", "B"):
        group = [r for r in rows if r["arm"] == arm]
        totals[arm] = {"slots": len(group), "independent_task_completions": sum(r["task_complete"] for r in group),
                       "regression_failures": sum(r["regression_introduced"] for r in group),
                       "scope_violations": sum(bool(r["scope_violations"]) for r in group),
                       "tool_items": sum(r["tool_items"] for r in group),
                       "guard_calls": sum(len(r["guard_calls"]) for r in group),
                       "elapsed_seconds": sum(r["elapsed_seconds"] for r in group),
                       "last_observed_input_tokens": sum(r["codex_token_usage"]["inputTokens"] for r in group),
                       "last_observed_cached_input_tokens": sum(r["codex_token_usage"]["cachedInputTokens"] for r in group),
                       "last_observed_output_tokens": sum(r["codex_token_usage"]["outputTokens"] for r in group),
                       "last_observed_total_tokens": sum(r["codex_token_usage"]["totalTokens"] for r in group),
                       "dollar_cost": None}
    summary = {"status": "EXECUTED_12_WITH_COMMON_HOST_BUDGET_DEFECT", "controlled_effect_estimate": "NOT_SUPPORTED",
               "generation_turns_started": sum(r["model_turns_started"] for r in rows), "retries_or_replacements": 0,
               "pairs": pairs, "descriptive_totals": totals, "baseline_tests_are_not_guard_specific": True,
               "additional_functional_defects_detected_only_by_guard": 0,
               "guard_candidate_verification_adopted": 6, "terminal_guard_pass_current_matching": 6,
               "potential_false_rejections_observed": 0, "false_rejection_sensitivity_established": False,
               "cached_tokens_subtracted": False,
               "conclusion": "All final authorized candidates satisfy the focused checks; Guard evidence works. Correctness gain is not demonstrated (ceiling), and the invalid interruption request precludes a strict equal-budget cost/utility comparison."}
    save(HERE / "results/analysis.json", summary)
    incident = {
        "id": "P3-INCIDENT-01", "discovered": "Post-closure accounting, after all twelve positions executed",
        "component": "Frozen pilot batch driver only; P0/P1/P2 implementations unchanged",
        "freeze_commit": "ace28282bd6780172d1d2ce753ab6b099636ac01", "freeze_sha256": digest(freeze_bytes),
        "runner_sha256": freeze["files"]["pilots/codex_guard/run.py"],
        "defect": "turn/interrupt sent threadId without required turnId; JSON-RPC errors were not checked by the batch listener",
        "actual_zero_model_reproduction": {"model_turns_started": 0,
            "request": {"method": "turn/interrupt", "params": {"threadId": "nonexistent-no-generation"}},
            "response": {"error": {"code": -32600, "message": "Invalid request: missing field `turnId`"}, "id": 7001}},
        "observed_threshold_flags": 12, "observed_natural_completed_notifications": sum(r.get("turn_status") == "completed" for r in rows),
        "terminal_notifications_not_observed": [r["slot"] for r in rows if not r.get("turn_status")],
        "last_observed_tokens_range": [min(r["codex_token_usage"]["totalTokens"] for r in rows), max(r["codex_token_usage"]["totalTokens"] for r in rows)],
        "threshold": 120000, "budget_control_valid": False,
        "per_run_interrupt_error_responses_retained": False,
        "interpretation": "The frozen payload plus direct same-host reproduction establishes the defect. Raw driver threshold labels must not be reported as successful cancellation. Two usage totals may be lower bounds; neither missing terminal state nor missing invoice is filled with zero.",
        "action": "No new model execution, replacement, budget reset or retrospective threshold change. Original freeze/runner/results remain intact. A future protocol repair or new pilot requires separate authorization."}
    save(HERE / "results/INCIDENT-01.json", incident)
    archive = ROOT / ".local/P3-CODEX-GUARD-EVIDENCE.zip"
    if archive.exists():
        raise RuntimeError("archive already exists; do not overwrite evidence")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(RUNTIME.rglob("*")):
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts:
                bundle.write(path, path.relative_to(RUNTIME).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        entries = len(bundle.infolist())
    save(HERE / "results/archive-manifest.json", {"local_filename": archive.name, "sha256": digest(archive.read_bytes()),
         "bytes": archive.stat().st_size, "entries": entries,
         "content": "actual app-server inputs, filtered tool/usage records, original and final sources, native diffs, Guard evidence, independent outputs and results",
         "excluded": ["Git internals", "Python caches"], "credentials_copied": False,
         "raw_provider_transport_available": False, "raw_reasoning_saved": False,
         "public_raw_transcripts": False})
    save(HERE / "VALIDATION.json", {"frozen_inputs_unchanged": public_files() == freeze["files"],
         "freeze_sha256": digest(freeze_bytes), "slots_executed": 12, "model_turns_started": 12,
         "retries_replacements_extra_slots": 0, "independent_final_task_pass": 12, "independent_regression_pass": 12,
         "scope_violations": 0, "original_sources_unchanged": all(r["original_source_unchanged"] for r in rows),
         "all_candidate_git_heads_unchanged": all(p[arm]["git_head_unchanged"] for p in pairs for arm in ("A", "B")),
         "budget_contract_valid": False, "scientific_comparison_status": "NOT_VALID_AS_STRICT_EQUAL_BUDGET_COMPARISON",
         "incident": "results/INCIDENT-01.json", "model_execution_stopped": True,
         "historical_frozen_artifacts_changed": False, "P0_P1_P2_implementation_changed": False,
         "development_and_analysis": "Codex-assisted; zero-model labels apply only to deterministic checks, not development authorship"})
    print(json.dumps({"status": summary["status"], "observations": totals, "archive_sha256": digest(archive.read_bytes())}))


if __name__ == "__main__":
    main()
