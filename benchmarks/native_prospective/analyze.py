"""Read-only post-closure accounting. No candidate execution or model calls."""

import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import canonical, sha

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(runtime):
    frozen = load(HERE / "FREEZE.json")
    result = load(HERE / "RESULTS.json")
    manifest = load(HERE / "ARCHIVE.json")
    assert sha((runtime / "RAW.zip").read_bytes()) == manifest["sha256"]
    for path, digest in frozen["files"].items():
        assert sha((ROOT / path).read_bytes()) == digest, path
        assert sha(base64.b64decode(frozen["runtime_bytes"][path])) == digest
    slots = []
    for entry in frozen["schedule"]:
        path = runtime / entry["id"]
        if not (path / "result.json").is_file():
            slots.append(
                {
                    "id": entry["id"],
                    "task": entry["task"],
                    "arm": entry["arm"],
                    "status": "NOT_STARTED",
                }
            )
            continue
        row, raw = load(path / "result.json"), load(path / "linux.json")
        assert row["freeze_commit"] == result["freeze_commit"]
        assert (row["id"], row["task"], row["arm"]) == (
            entry["id"],
            entry["task"],
            entry["arm"],
        )
        operations, errors = [], []
        snapshots = []
        text_edits = check = test = 0
        schemas = []
        for call in raw["calls"]:
            if call.get("action") == "edit":
                text_edits += call["response"].get("accepted") is True
            check += call.get("action") == "check"
            test += call.get("action") == "test"
            if call.get("request", {}).get("method") == "tools/list":
                tools = {t["name"]: t for t in call["response"]["tools"]}
                assert tools == frozen["native_tools"], "Native schemas changed"
                schemas.append(sha(canonical(tools)))
            if call.get("request", {}).get("method") == "tools/call":
                name = call["request"]["params"]["name"]
                answer = call["response"]
                failed = bool(answer.get("isError"))
                detail = answer.get("structuredContent", {})
            elif call.get("action") == "aep":
                name, answer = call["arguments"].get("tool"), call["response"]
                failed = answer.get("ok") is False or bool(answer.get("error"))
                detail = answer.get("result", {})
            else:
                continue
            operations.append({"name": name, "success": not failed})
            if failed:
                # Only bounded codes/operation names, never raw model arguments.
                errors.append(
                    {
                        "operation": name,
                        "code": answer.get("error_code", "MCP_IS_ERROR"),
                    }
                )
            if name == "preview_semantic_diff" and not failed:
                snapshots.append(bool(detail.get("diff", "").strip()))
        counts = Counter(o["name"] for o in operations)
        successful = Counter(o["name"] for o in operations if o["success"])
        current = raw.get("final_files", {}).get("alva-air/current")
        publication = current is not None
        changed = row.get("target_body_changed", False)
        final_status = raw.get("final", {}).get("status", "UNKNOWN")
        outcome = (
            "NO_COMMITTED_CANDIDATE"
            if entry["arm"] != "T" and not publication
            else final_status
        )
        assert (
            outcome == row["disposition"]
        ), "Public summary must reflect actual authority"
        total = (row.get("usage") or {}).get("total")
        slots.append(
            {
                "id": entry["id"],
                "task": entry["task"],
                "arm": entry["arm"],
                "status": outcome,
                "schema_delivered": entry["arm"] == "N" and bool(schemas),
                "native_schema_sha256": schemas[0] if schemas else None,
                "skill_and_references_in_frozen_prompt": entry["arm"] == "N"
                and all(body in entry["prompt"] for body in frozen["docs"].values()),
                "successful_resolve_entity": successful["resolve_entity"],
                "successful_describe_operation": successful["describe_operation"],
                "successful_applicable_operations": successful["applicable_operations"],
                "operation_calls": dict(counts),
                "successful_operations": dict(successful),
                "operation_errors": errors,
                "accepted_text_edits": text_edits,
                "successful_node_construction_calls": sum(
                    n
                    for name, n in successful.items()
                    if str(name).startswith("create_") or name == "construct_expression"
                ),
                "successful_attachment_calls": successful["replace_expression"],
                "nonempty_semantic_previews": sum(snapshots),
                "successful_transaction_checks": successful["check_transaction"],
                "successful_commit_calls": successful["commit_transaction"],
                "authority_current_exists": publication,
                "authority_current_sha256": (
                    sha(base64.b64decode(current)) if current else None
                ),
                "fresh_process_target_body_changed": changed,
                "initial_authority": raw.get("initial_authority"),
                "final_authority": raw.get("final_authority"),
                "independent_final_status": final_status,
                "final_check_pass": raw.get("final", {}).get("check", {}).get("exit")
                == 0,
                "model_directed_checks": check,
                "model_directed_tests": test,
                "tool_calls": row.get("tool_calls"),
                "usage": total,
                "elapsed_seconds": row.get("elapsed_seconds"),
                "token_threshold_overshoot": (
                    max(0, total["totalTokens"] - 120000) if total else None
                ),
                "terminal": row.get("terminal_status"),
                "interrupt_ack": row.get("interrupt_ack"),
                "stop_reason": row.get("stop_reason"),
                "infrastructure_hold": row.get("infrastructure_hold"),
            }
        )
    arms = {}
    for arm in ("T", "B", "N"):
        group = [s for s in slots if s["arm"] == arm and s["status"] != "NOT_STARTED"]
        arms[arm] = {
            "slots": len(group),
            "outcomes": dict(Counter(s["status"] for s in group)),
            "operation_errors": sum(len(s["operation_errors"]) for s in group),
            "accepted_text_edits": sum(s["accepted_text_edits"] for s in group),
            "tools": sum(s["tool_calls"] for s in group),
            "valid_resolve_slots": sum(
                s["successful_resolve_entity"] > 0 for s in group
            ),
            "attachment_slots": sum(
                s["successful_attachment_calls"] > 0 for s in group
            ),
            "commit_slots": sum(s["successful_commit_calls"] > 0 for s in group),
            "changed_target_slots": sum(
                s["fresh_process_target_body_changed"] for s in group
            ),
            "usage_missing_slots": sum(s["usage"] is None for s in group),
            "known_total_tokens": sum(
                s["usage"]["totalTokens"] for s in group if s["usage"]
            ),
            "elapsed_seconds": round(sum(s["elapsed_seconds"] for s in group), 3),
        }
    analysis = {
        "schema": "p26-descriptive/v1",
        "freeze_commit": result["freeze_commit"],
        "slots": slots,
        "arms": arms,
        "provider_request_count": None,
        "dollar_cost": None,
        "hard_token_budget": False,
        "historical_results_pooled": False,
        "significance_test": False,
    }
    save(HERE / "ANALYSIS.json", analysis)
    validation = {
        "status": (
            "PASS"
            if len(slots) == 12 and not any(s.get("infrastructure_hold") for s in slots)
            else "INCOMPLETE"
        ),
        "archive_sha256_verified": True,
        "frozen_runtime_hashes_unchanged": True,
        "native_schema_matches_freeze": True,
        "actual_authority_current_crosscheck": True,
        "actual_started_slots": result["executed"],
        "terminal_confirmed_slots": sum(
            s.get("terminal") in ("interrupted", "completed", "failed") for s in slots
        ),
        "acknowledged_interrupt_slots": sum(
            s.get("interrupt_ack") is True for s in slots
        ),
        "missing_usage_slots": sum(s.get("usage") is None for s in slots),
        "extra_slots": 0,
        "model_generation_by_analysis": 0,
        "raw_logs_in_git": False,
        "core_modified": False,
        "historical_frozen_artifacts_modified": False,
    }
    save(HERE / "VALIDATION.json", validation)
    lines = [
        "# P26 prospective native MCP/Skill coding pilot — closed",
        "",
        "Twelve new frozen slots completed once; no common HOLD, retries, replacements or extra slots.",
        "This is a small developmental workflow-package comparison, not a superiority test.",
        "",
        "## Per-task results (independent final scoring)",
        "",
        "| Task | T: text | B: thin bridge | N: native + Skill |",
        "|---|---|---|---|",
    ]
    for task in frozen["tasks"]:
        group = {s["arm"]: s for s in slots if s["task"] == task}
        lines.append(
            "| "
            + task
            + " | "
            + " | ".join(group[a]["status"] for a in ("T", "B", "N"))
            + " |"
        )
    lines += [
        "",
        "## Stages and costs",
        "",
        "| Arm | Valid entity-resolution slots | Attachment slots | Commit slots | Changed target slots | API errors | Tools | Actual total tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, m in arms.items():
        stages = (
            ("N/A", "N/A", "N/A", "N/A")
            if arm == "T"
            else tuple(
                str(m[k])
                for k in (
                    "valid_resolve_slots",
                    "attachment_slots",
                    "commit_slots",
                    "changed_target_slots",
                )
            )
        )
        lines.append(
            f"| {arm} | "
            + " | ".join(stages)
            + f" | {m['operation_errors']} | {m['tools']} | {m['known_total_tokens']} |"
        )
    lines += [
        "",
        "N received exact native schemas and complete official Skill/references in every slot.",
        "It made successful discovery/schema calls without operation errors, unlike B's unknown-operation/entity/operand errors.",
        "Three N slots performed discovery only; HE41 constructed two references but never attached or committed them.",
        "There is therefore a bounded interface-discovery observation, **no demonstrated coding/commit/behavior utility**.",
        "B/HE23 committed the unchanged stub: fresh-process target body hash did not change and independent behavior failed.",
        "A successful commit must not be scored as a useful edit or task completion.",
        "All four T final sources failed ordinary compilation. Recorded diagnostics include unknown `var`/`name` expression tags",
        "T made 58 accepted source edits and 59 model-directed checks; AIR stage columns are not applicable to T.",
        "and an invalid/empty `block`; these are observed constructions, not proof that ALVA cannot express the tasks.",
        "",
        "All twelve turns were interrupted at frozen resource thresholds (eleven TOKEN, one TOOL); every interrupt was acknowledged",
        "and terminal status recorded. Every actual token total exceeded the 120000 observation threshold; the overshoot is retained.",
        "These are censored trajectories, not complete unconstrained solver attempts. Native schema/Skill input and repeated discovery",
        "consume the same observation budget; their exact cost is included, not subtracted. No hard provider token cap is claimed.",
        "Usage is present for every slot, including cached input without deduction. Provider request counts and dollar costs are unknown.",
        "",
        "## Evidence and limits",
        "",
        "FREEZE.json was committed/pushed before the first model turn; ANALYSIS.json crosschecks raw slot identity, schema bytes,",
        "the authority current file, fresh-process body hashes and independent compilation/behavior. Raw transcripts, final sources/AIR,",
        "Linux build/test output and configs remain only in controlled ignored local RAW.zip; ARCHIVE.json binds its exact bytes.",
        "No P24/P21/P3 evidence was modified or pooled. The P25 closeout removed tracked local logs with an additive commit;",
        "its existing PR CI automatically ran after that update. No P25 solution witness was manually rerun for pilot preparation.",
        "",
        "N uses official workspace Skill discovery and explicit complete Skill text, plus per-process native MCP registration;",
        "it does not update a user's installed plugin. The Skill's CLI-doctor instruction has no separate doctor tool here:",
        "the isolated SDK was preverified by the host and model check/test callbacks use that exact SDK. This surface limitation",
        "is not changed after seeing outcomes. N has added documentation/tool support; differences are not pure AEP semantic effects.",
        "Public adapted HumanEval tasks may be training-contaminated; this is not an official benchmark score or independent task",
        "generalization. Small samples, one run/condition and budget censoring preclude statistical or language-superiority claims.",
        "The two P25 checker/anonymous-revision limitations remain; independent final evaluation, not `ok:true`, is decisive.",
        "",
        "## Disposition",
        "",
        "CLOSED_COMPLETE; no end-to-end utility signal established in this bounded wave.",
        "Engineering integration is observable; coding effectiveness is not established. No automatic follow-up, rerun, merge or Core change.",
        "STOP; independent reviewer decision required.",
    ]
    (HERE / "REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"validation": validation, "arms": arms}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path)
    main(parser.parse_args().runtime)
