"""Two separate deterministic evaluators over the same read-only projection."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.rdr02_treatment_realization import evidence as e

STAGES = ("exposure", "tool_dispatch", "construction", "target_attachment",
          "connected_staging", "host_authorization", "publication", "independent_published_behavior")


def e0(row):
    """Conventional state-aware process/diff/test baseline, not an ok counter."""
    out = {s: "UNKNOWN" for s in STAGES}
    if not row["model_unit"]:
        gap = any(p["advertised_by_registry"] and p["isError"] is True for p in row["coverage_probes"])
        out.update({s: "NOT_APPLICABLE" for s in STAGES})
        out["exposure"] = "FALSE" if gap else "UNKNOWN"
        return {"stages": out, "classification": "CAPABILITY_COVERAGE_GAP" if gap else "UNKNOWN",
                "task_tests": "NOT_APPLICABLE", "staged_behavior": "NOT_APPLICABLE"}
    if "state" not in row:
        return {"stages": out, "classification": "UNKNOWN", "task_tests": "UNKNOWN", "staged_behavior": "UNKNOWN"}
    backend = row["backend"]
    successful = [c for c in backend if c["success"] is True and not c["withheld"]]
    commits = [c for c in successful if c["operation"] == "commit_transaction"]
    denied = any(c["operation"] == "commit_transaction" and c["error"] and
                 "approval" in str(c["error"]).lower() for c in row["frontend"])
    state = row["state"]
    before, after = state["initial_authority"], state["final_authority"]
    changes = [o for o in row["observer"] if not o["baseline"] and
               o["body_sha256"] != before["target_body_sha256"]]
    linked = any(c["operation"] == "replace_expression" and c["call_id"] == o["call_id"]
                 for c in successful for o in changes)
    out["exposure"] = "TRUE" if backend else "UNKNOWN"
    out["tool_dispatch"] = "TRUE" if backend else "UNKNOWN"
    out["construction"] = "TRUE" if any(c["operation"].startswith("create_") and c["result_revision"] for c in successful) else "FALSE"
    if row["observer"]:
        out["target_attachment"] = out["connected_staging"] = "TRUE" if linked else "FALSE"
    out["host_authorization"] = "FALSE" if denied else ("TRUE" if commits else "UNKNOWN")
    published = bool(commits and commits[-1]["generation"] and
                     commits[-1]["result_revision"] == after["project_revision"] == state["stored_current_revision"])
    out["publication"] = "TRUE" if published else ("FALSE" if denied and not commits else "UNKNOWN")
    tests = row["evaluation"]
    task = tests.get("goal", tests.get("execution"))
    task_result = "UNKNOWN" if task is None else ("PASS" if task["exit"] == 0 else "FAIL")
    # Same finalization member records files and evaluation, but has no explicit
    # tested-revision receipt. Do not upgrade co-recording into that missing link.
    if row["evaluation_identity"]["explicit_revision_receipt"] is not None and published:
        bound = row["evaluation_identity"]["explicit_revision_receipt"] == after["project_revision"]
        out["independent_published_behavior"] = "TRUE" if bound and task_result == "PASS" else "FALSE"
    if denied and linked:
        label = "CONNECTED_NOT_PUBLISHED"
    elif published and before["target_body_sha256"] == after["target_body_sha256"]:
        label = "PUBLISHED_WITHOUT_TARGET_CHANGE"
    elif published and task_result == "PASS":
        label = "PUBLISHED_TESTS_PASS_IDENTITY_RECEIPT_UNAVAILABLE"
    else:
        label = "UNKNOWN"
    return {"stages": out, "classification": label, "task_tests": task_result,
            "staged_behavior": "NOT_INDEPENDENTLY_EVALUATED"}


def e1(row):
    """Object-bound lineage analysis, independently implemented from E0."""
    chain = dict.fromkeys(STAGES, "UNKNOWN")
    if row["model_unit"] is False:
        chain = dict.fromkeys(STAGES, "NOT_APPLICABLE")
        mismatch = [p for p in row["coverage_probes"] if p["advertised_by_registry"] is True and p["isError"] is True]
        chain["exposure"] = "FALSE" if mismatch else "UNKNOWN"
        return {"stages": chain, "classification": "CAPABILITY_COVERAGE_GAP" if mismatch else "UNKNOWN",
                "task_tests": "NOT_APPLICABLE", "staged_behavior": "NOT_APPLICABLE"}
    state = row.get("state")
    if state is None:
        return {"stages": chain, "classification": "UNKNOWN", "task_tests": "UNKNOWN", "staged_behavior": "UNKNOWN"}
    by_id = {c["call_id"]: c for c in row["backend"] if c["call_id"] and c["success"] is True and c["withheld"] is False}
    chain["exposure"] = chain["tool_dispatch"] = "TRUE" if row["backend"] else "UNKNOWN"
    created = [c["result_revision"] for c in row["backend"] if c["operation"].startswith("create_") and
               c["success"] is True and not c["withheld"] and c["result_revision"]]
    chain["construction"] = "TRUE" if created else "FALSE"
    attached = False
    for o in row["observer"]:
        c = by_id.get(o["call_id"])
        if c and c["operation"] == "replace_expression" and not o["baseline"]:
            attached |= o["body_sha256"] != state["initial_authority"]["target_body_sha256"]
    if row["observer"]:
        chain["target_attachment"] = chain["connected_staging"] = "TRUE" if attached else "FALSE"
    commit_nodes = [c for c in row["backend"] if c["operation"] == "commit_transaction" and
                    c["success"] is True and c["withheld"] is False]
    denied_ids = {x["call_id"] for x in row["frontend"] if x["operation"] == "commit_transaction" and
                  x["error"] is not None and "approval" in str(x["error"]).lower()}
    chain["host_authorization"] = "FALSE" if denied_ids else ("TRUE" if commit_nodes else "UNKNOWN")
    final_id = state["final_authority"]["project_revision"]
    publication_links = [c for c in commit_nodes if c["generation"] and c["result_revision"] == final_id and
                         state["stored_current_revision"] == final_id]
    chain["publication"] = "TRUE" if publication_links else ("FALSE" if denied_ids and not commit_nodes else "UNKNOWN")
    checks = row["evaluation"]
    behavior = checks.get("goal", checks.get("execution"))
    outcome = "UNKNOWN" if behavior is None else ("FAIL" if behavior["exit"] else "PASS")
    tested_id = row["evaluation_identity"]["explicit_revision_receipt"]
    if tested_id is not None and publication_links:
        chain["independent_published_behavior"] = "TRUE" if tested_id == final_id and outcome == "PASS" else "FALSE"
    if attached and denied_ids:
        result = "CONNECTED_NOT_PUBLISHED"
    elif publication_links and state["initial_authority"]["target_body_sha256"] == state["final_authority"]["target_body_sha256"]:
        result = "PUBLISHED_WITHOUT_TARGET_CHANGE"
    elif publication_links and outcome == "PASS":
        result = "PUBLISHED_TESTS_PASS_IDENTITY_RECEIPT_UNAVAILABLE"
    else:
        result = "UNKNOWN"
    return {"stages": chain, "classification": result, "task_tests": outcome,
            "staged_behavior": "NOT_INDEPENDENTLY_EVALUATED"}


def compare(observations):
    rows = []
    for unit in observations["units"]:
        left, right = e0(unit), e1(unit)
        raw_complete = not unit["model_unit"] or unit["availability"]["status"] == "ARCHIVE_VERIFIED"
        rows.append({"id": unit["id"], "model_unit": unit["model_unit"],
            "evidence_sha256_E0": e.identity(unit), "evidence_sha256_E1": e.identity(unit),
            "E0": left, "E1": right, "agreement": left == right,
            "comparison": "BASELINE_PARITY" if left == right else "DISAGREEMENT_REQUIRES_REVIEW",
            "missing": unit["missing"], "archive_available": raw_complete,
            "full_chain_evidence_sufficient": raw_complete and (not unit["model_unit"] or
                left["stages"]["publication"] == "FALSE" or
                unit.get("evaluation_identity", {}).get("explicit_revision_receipt") is not None),
            "evidence_pointers": [c["evidence"] for c in unit["backend"] + unit["frontend"] + unit["observer"]] +
                                 [p["evidence"] for p in unit["coverage_probes"]]})
    disagreements = sum(not r["agreement"] for r in rows)
    complete = all(r["full_chain_evidence_sufficient"] for r in rows)
    disposition = ("INCONCLUSIVE_EVIDENCE_LIMITATION" if not complete else
                   "OBSERVED_INCREMENTAL_MEASUREMENT_VALUE" if disagreements else "NO_OBSERVED_INCREMENTAL_VALUE")
    return {"schema": "rdr02-comparison/v1", "rows": rows, "actual_disagreement_count": disagreements,
            "substantive_available_evidence_parity": all(r["agreement"] for r in rows),
            "disposition": disposition, "new_measurement_advantage_established": False,
            "direction_D_new_mechanism": "NOT_JUSTIFIED; NO_AUTOMATIC_FOLLOWUP",
            "model_generation_calls": 0, "input_token_api_calls": 0, "next_model_experiment": "NOT_AUTHORIZED"}


def run(paths):
    public = e.public_sources()
    archives, availability = e.read_archives(paths)
    observations = e.project(public | archives, availability)
    return {"OBSERVATIONS.json": observations, "EVIDENCE-AVAILABILITY.json": availability,
            "E0-E1-COMPARISON.json": compare(observations)}


def arguments(parser):
    for u in ("U2", "U3", "U4"):
        parser.add_argument("--" + u.lower(), type=Path)
    return parser


if __name__ == "__main__":
    p = arguments(argparse.ArgumentParser())
    args = p.parse_args()
    print(json.dumps(run({u: getattr(args, u.lower()) for u in ("U2", "U3", "U4")}), indent=2))
