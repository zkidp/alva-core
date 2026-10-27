"""Read-only P26 ZIP analysis. No provider, candidate execution or source repair.

Public output contains derived stages/counts/hashes, not raw arguments,
transcripts, private metadata, reasoning text, or candidate programs.
"""

import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = "fac39867f32ab4b3b428ed08a4eaf28be08dafa9"
EXPECTED = "b37b499ec63388824efde38c395c221a71ae04d1367b1ad8555309c3888c6dd2"
P26 = ROOT / "benchmarks/native_prospective"
FIELDS = (
    "totalTokens",
    "inputTokens",
    "cachedInputTokens",
    "cacheWriteInputTokens",
    "outputTokens",
    "reasoningOutputTokens",
)
STAGES = {
    "START": 0,
    "SESSION_BEGIN": 1,
    "SOURCE_INSPECTION": 2,
    "ENTITY_DISCOVERY": 3,
    "SCHEMA_DISCOVERY": 4,
    "NODE_CONSTRUCTION": 5,
    "SOURCE_EDIT": 5,
    "TARGET_ATTACHMENT": 6,
    "CHECK": 7,
    "COMMIT": 8,
    "MODEL_INDEPENDENT_TEST": 9,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def public_blob(name):
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "cat-file",
            "blob",
            BASE + ":benchmarks/native_prospective/" + name,
        ]
    )


def public_json(name):
    return json.loads(public_blob(name))


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def verified_zip(path):
    if sha(path.read_bytes()) != EXPECTED:
        raise ValueError("ARCHIVE_SHA256_MISMATCH: no record reconstruction permitted")
    z = zipfile.ZipFile(path)
    if len(z.namelist()) != len(set(z.namelist())):
        z.close()
        raise ValueError("Duplicate ZIP member")
    return z


def totals(value):
    return {k: value.get(k) for k in FIELDS}


def difference(new, old):
    return {
        k: (
            new[k] - old[k]
            if new.get(k) is not None and old.get(k) is not None
            else None
        )
        for k in FIELDS
    }


def usage_events(events):
    rows = []
    previous = {
        k: 0 for k in FIELDS
    }  # Explicit turn-start accounting origin, not missing usage.
    for i, event in enumerate(events):
        if event.get("method") != "thread/tokenUsage/updated":
            continue
        value = event["params"]["tokenUsage"]
        current = totals(value["total"])
        if rows and any(
            current[k] is not None
            and previous[k] is not None
            and current[k] < previous[k]
            for k in FIELDS
        ):
            raise ValueError("Non-monotonic usage")
        rows.append(
            {
                "ordinal": len(rows) + 1,
                "event_index": i,
                "timestamp_ms": event.get("emittedAtMs"),
                "cumulative": current,
                "increment": difference(current, previous),
                "provider_last": totals(value.get("last", {})),
            }
        )
        previous = current
    return rows


def bracket(usage, start, end):
    before = next((u for u in reversed(usage) if u["event_index"] < start), None)
    after = next((u for u in usage if u["event_index"] > end), None)
    origin = {k: 0 for k in FIELDS}
    return {
        "before_usage_ordinal": before["ordinal"] if before else 0,
        "after_usage_ordinal": after["ordinal"] if after else None,
        "cumulative_before": before["cumulative"] if before else None,
        "before_is_observed_usage": before is not None,
        "unobserved_before_uses_turn_origin_for_interval_only": before is None,
        "cumulative_after": after["cumulative"] if after else None,
        "enclosing_increment": (
            difference(after["cumulative"], before["cumulative"] if before else origin)
            if after
            else None
        ),
        "individual_call_token_charge": None,
    }


def classify(action, operation=None):
    name = operation or action
    if name == "begin_transaction":
        return "SESSION_BEGIN"
    if name in (
        "resolve_entity",
        "inspect_project",
        "inspect_module",
        "inspect_function",
        "inspect_body",
        "inspect_entity",
        "applicable_operations",
    ):
        return "ENTITY_DISCOVERY"
    if name in ("describe_operation", "describe_construction", "list_capabilities"):
        return "SCHEMA_DISCOVERY"
    if name.startswith("create_") or name == "construct_expression":
        return "NODE_CONSTRUCTION"
    if name in ("replace_expression", "change_field", "append_step"):
        return "TARGET_ATTACHMENT"
    if name == "edit":
        return "SOURCE_EDIT"
    if name in ("check", "check_transaction"):
        return "CHECK"
    if name == "commit_transaction":
        return "COMMIT"
    if name == "test":
        return "MODEL_INDEPENDENT_TEST"
    if name == "read":
        return "SOURCE_INSPECTION"
    return "OTHER_EXPLORATION"


def diagnostics(answer):
    check = answer.get("check", {})
    try:
        values = json.loads(check.get("stdout", ""))
    except (ValueError, TypeError):
        return []
    if not isinstance(values, list):
        return []
    rows = []
    for item in values:
        message = item.get("message", "")
        tag = None
        if "unknown expression tag '" in message:
            category = "UNSUPPORTED_EXPRESSION_TAG"
            tag = message.split("unknown expression tag '", 1)[1].split("'", 1)[0]
        elif "block" in message and "requires at least one expression" in message:
            category = "BLOCK_CONSTRUCTION_INVALID"
        elif "requires a (body" in message:
            category = "FUNCTION_BODY_INVALID"
        else:
            category = "OTHER_RECORDED_DIAGNOSTIC"
        rows.append(
            {
                "code": item.get("code"),
                "category": category,
                "tag": tag,
                "message_sha256": sha(message.encode()),
            }
        )
    return rows


def decode_answer(item):
    if item["type"] == "mcpToolCall":
        answer = item.get("result") or {}
        return answer, bool(item.get("error") or answer.get("isError"))
    texts = [
        c["text"]
        for c in item.get("contentItems") or []
        if c.get("type") == "inputText"
    ]
    try:
        answer = json.loads(texts[0]) if len(texts) == 1 else {}
    except ValueError:
        answer = {}
    return (
        answer,
        item.get("success") is False
        or bool(answer.get("error"))
        or answer.get("ok") is False,
    )


def extract_calls(events):
    completed = {
        e["params"]["item"]["id"]: (i, e["params"]["item"])
        for i, e in enumerate(events)
        if e.get("method") == "item/completed"
        and e.get("params", {}).get("item", {}).get("type")
        in ("dynamicToolCall", "mcpToolCall")
    }
    seen = set()
    result = []
    for i, event in enumerate(events):
        item = event.get("params", {}).get("item", {})
        if event.get("method") != "item/started" or item.get("type") not in (
            "dynamicToolCall",
            "mcpToolCall",
        ):
            continue
        if item["id"] in seen:
            raise ValueError("Repeated item/start identity requires explicit handling")
        seen.add(item["id"])
        end, final = completed.get(item["id"], (None, item))
        args = item.get("arguments", {})
        if item["type"] == "dynamicToolCall":
            action = args.get("action", "UNKNOWN")
            try:
                args = json.loads(args.get("arguments", "{}"))
            except ValueError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            operation = args.get("tool") if action == "aep" else None
        else:
            action, operation = "native", item["tool"]
        answer, failed = decode_answer(final)
        result.append(
            {
                "start": i,
                "end": end,
                "item_id": item["id"],
                "action": action,
                "operation": operation,
                "arguments": args,
                "answer": answer,
                "failed": failed,
                "status": final.get("status"),
                "duration_ms": final.get("durationMs"),
            }
        )
    return result


def analyze_slot(entry, raw, linux, frozen, baseline_blob):
    events = raw["events"]
    usage = usage_events(events)
    assert usage[-1]["cumulative"] == totals(raw["usage"]["total"])
    calls = extract_calls(events)
    assert len(calls) == raw["tool_calls"]
    start_ms = next(
        e["emittedAtMs"] for e in events if e.get("method") == "turn/started"
    )
    initial_prompts = [
        e["params"]["item"]
        for e in events
        if e.get("method") == "item/started"
        and e.get("params", {}).get("item", {}).get("type") == "userMessage"
    ]
    assert len(initial_prompts) == 1
    assert initial_prompts[0]["content"][0]["text"] == entry["prompt"]
    wire = {
        c["request"]["params"].get("_meta", {}).get("callId"): (i, c)
        for i, c in enumerate(linux["calls"])
        if c.get("request", {}).get("method") == "tools/call"
    }
    rows = []
    signatures, prior_sources, nodes = {}, {sha(baseline_blob)}, []
    current = baseline_blob
    source_generation = 0
    stateful_signatures = {}
    first = {}
    for ordinal, call in enumerate(calls, 1):
        action, op, args, answer = (
            call[k] for k in ("action", "operation", "arguments", "answer")
        )
        normalized_args = {
            k: v
            for k, v in args.items()
            if k not in ("transaction_id", "request_id", "project")
        }
        signature = sha(canonical([op or action, normalized_args]))
        success = (
            not call["failed"]
            and call["end"] is not None
            and call["status"] == "completed"
        )
        stage = classify(action, op)
        position = {
            "archive_member": entry["id"] + "/result.json",
            "start_event_index": call["start"],
            "end_event_index": call["end"],
        }
        wire_answer = answer
        if action == "native":
            if call["item_id"] not in wire:
                raise ValueError("Native event has no real MCP dispatch record")
            wi, wc = wire[call["item_id"]]
            position["linux_call_index"] = wi
            position["linux_member"] = entry["id"] + "/linux.json"
            assert wc["request"]["params"]["name"] == op
            assert wc["request"]["params"]["arguments"] == args
            wire_answer = wc["response"]
            success = success and not wire_answer.get("isError")
        detail = (
            wire_answer.get("structuredContent", {})
            if action == "native"
            else answer.get("result", {})
        )
        before = bracket(
            usage,
            call["start"],
            call["end"] if call["end"] is not None else len(events),
        )
        row = {
            "ordinal": ordinal,
            "stage": stage,
            "action": action,
            "operation": op,
            "argument_keys": sorted(normalized_args),
            "argument_fingerprint": signature,
            "result": "SUCCESS_ENVELOPE" if success else "ERROR_OR_INCOMPLETE",
            "error_code": wire_answer.get(
                "error_code",
                "MCP_IS_ERROR" if wire_answer.get("isError") else answer.get("error"),
            ),
            "call_duration_ms": call["duration_ms"],
            "source": position,
            "response_canonical_bytes": len(canonical(answer)),
            "response_sha256": sha(canonical(answer)),
            "usage_bracket": before,
            "repeat_of_ordinal": signatures.get(signature),
            "diagnostics": diagnostics(answer),
        }
        row["compiler_check_status"] = (
            answer.get("status") if action == "check" else None
        )
        row["compiler_check_pass"] = (
            answer.get("status") == "PASS" if action == "check" else None
        )
        row["same_arguments_not_equivalent_to_redundant_work"] = True
        row["source_generation_before"] = (
            source_generation if entry["arm"] == "T" else None
        )
        row["source_sha256_before"] = sha(current) if entry["arm"] == "T" else None
        stateful = (signature, source_generation) if entry["arm"] == "T" else None
        row["repeat_with_same_source_state"] = (
            stateful in stateful_signatures if stateful else None
        )
        if stateful:
            stateful_signatures.setdefault(stateful, ordinal)
        signatures.setdefault(signature, ordinal)
        if success and stage in STAGES:
            first.setdefault(stage, ordinal)
        if (
            action == "edit"
            and answer.get("accepted") is True
            and isinstance(args.get("content"), str)
        ):
            candidate = args["content"].encode()
            row["actual_source_bytes_changed"] = candidate != current
            row["source_sha256"] = sha(candidate)
            row["revisits_prior_source"] = row["source_sha256"] in prior_sources
            if candidate != current:
                first.setdefault("EFFECTIVE_SOURCE_EDIT", ordinal)
                source_generation += 1
            current = candidate
            prior_sources.add(sha(candidate))
        if (
            success
            and stage == "NODE_CONSTRUCTION"
            and isinstance(detail, dict)
            and detail.get("revision")
        ):
            row["returned_revision"] = detail["revision"]
            row["revision_returned_previously"] = detail["revision"] in nodes
            nodes.append(detail["revision"])
        if op in frozen["native_tools"] and action == "aep":
            required = set(
                frozen["native_tools"][op]["inputSchema"].get("required", [])
            ) - {"transaction_id"}
            if op == "begin_transaction":
                required.discard("project")  # Host provides this exact field.
            row["missing_required_fields_vs_frozen_native_schema"] = sorted(
                required - set(args)
            )
        if action == "native":
            structured = wire_answer.get("structuredContent")
            text = [
                c.get("text")
                for c in wire_answer.get("content", [])
                if c.get("type") == "text"
            ]
            same = bool(
                structured is not None
                and len(text) == 1
                and json.loads(text[0]) == structured
            )
            row["rpc_text_and_structured_same_payload"] = same
            row["duplicated_rpc_text_bytes"] = len(text[0].encode()) if same else 0
            row["provider_duplicate_tokens"] = None
        rows.append(row)
    # Shared enclosing usage intervals are not additive per-tool costs.
    groups = defaultdict(list)
    for r in rows:
        b = r["usage_bracket"]
        groups[(b["before_usage_ordinal"], b["after_usage_ordinal"])].append(
            r["ordinal"]
        )
    for r in rows:
        b = r["usage_bracket"]
        b["shared_with_call_ordinals"] = groups[
            (b["before_usage_ordinal"], b["after_usage_ordinal"])
        ]
        b["attribution"] = "ENCLOSING_USAGE_INTERVAL_NOT_CAUSAL_CALL_COST"
    thresholds = frozen["config"]
    token_cross = next(
        (
            u
            for u in usage
            if u["cumulative"]["totalTokens"]
            >= thresholds["token_observation_threshold"]
        ),
        None,
    )
    tool_cross = (
        rows[thresholds["tool_callback_limit"] - 1]
        if len(rows) >= thresholds["tool_callback_limit"]
        else None
    )
    token_index = token_cross["event_index"] if token_cross else None
    # New controller tests tool limit after item/tool/call for dynamic tools,
    # whereas N uses item/started; find the actual callback event when present.
    tool_index = tool_cross["source"]["start_event_index"] if tool_cross else None
    if tool_cross and tool_cross["action"] != "native":
        ident = calls[tool_cross["ordinal"] - 1]["item_id"]
        tool_index = next(
            (
                i
                for i, e in enumerate(events)
                if e.get("method") == "item/tool/call"
                and e.get("params", {}).get("callId") == ident
            ),
            tool_index,
        )
    reached = [
        (idx, kind)
        for idx, kind in ((token_index, "TOKEN"), (tool_index, "TOOL"))
        if idx is not None
    ]
    trigger = min(reached)[1] if reached else "WALL_OR_OTHER"
    assert raw["stop_reason"].startswith(trigger), (
        entry["id"],
        trigger,
        raw["stop_reason"],
    )
    deepest = max(
        (
            r["stage"]
            for r in rows
            if r["result"] == "SUCCESS_ENVELOPE" and r["stage"] in STAGES
        ),
        key=lambda k: STAGES[k],
        default="START",
    )
    diag = [d for r in rows for d in r["diagnostics"]]
    labels = []
    if any(d["category"] == "UNSUPPORTED_EXPRESSION_TAG" for d in diag):
        labels.append("LANGUAGE_SYNTAX_MISUSE_OBSERVED")
    if diag and raw["disposition"] == "COMPILE_FAIL":
        labels.append("DIAGNOSTIC_REPAIR_NOT_CLOSED")
    if (
        any(
            r.get("compiler_check_pass") is True
            and (r.get("source_generation_before") or 0) > 0
            for r in rows
        )
        and raw["disposition"] == "COMPILE_FAIL"
    ):
        labels.append("INTERMEDIATE_CHECK_PASS_THEN_INVALID_FINAL")
    if any(r["result"] != "SUCCESS_ENVELOPE" for r in rows):
        labels.append("API_SCHEMA_OR_TOOL_USAGE_ERROR_OBSERVED")
    if any(r["repeat_of_ordinal"] for r in rows):
        labels.append("REPEATED_TOOL_ARGUMENTS_OBSERVED")
    if (
        nodes
        and not linux["final_authority"].get("body_error")
        and not raw.get("target_body_changed")
    ):
        labels.append("NODE_CONSTRUCTION_WITHOUT_TARGET_CHANGE")
    if entry["arm"] == "N":
        labels.append("ADVERTISED_SCHEMA_PLUS_DESCRIPTOR_DISCOVERY")
    labels += [
        "OBSERVATION_BUDGET_CENSORED",
        "OPERATION_COMPOSITION_CAUSAL_ROLE_UNDETERMINED",
    ]
    metrics = {}
    for label in ("EFFECTIVE_SOURCE_EDIT", "NODE_CONSTRUCTION", "TARGET_ATTACHMENT"):
        n = first.get(label)
        metrics[label] = {
            "call_ordinal": n,
            "prior_calls": n - 1 if n else None,
            "usage_bracket": rows[n - 1]["usage_bracket"] if n else None,
        }
    milestones = [
        {
            "stage": "START",
            "source": {
                "archive_member": entry["id"] + "/result.json",
                "event_index": next(
                    i for i, e in enumerate(events) if e.get("method") == "turn/started"
                ),
            },
        }
    ]
    milestones += [
        {"stage": r["stage"], "call_ordinal": r["ordinal"], "source": r["source"]}
        for r in rows
    ]
    milestones += [
        {
            "stage": "MODEL_STOP",
            "reason": raw["stop_reason"],
            "source": {
                "archive_member": entry["id"] + "/result.json",
                "event_index": next(
                    i
                    for i, e in enumerate(events)
                    if e.get("method") == "turn/completed"
                ),
            },
        },
        {
            "stage": "HOST_FINAL_EVALUATION",
            "after_model_stop": True,
            "result": linux["final"]["status"],
            "source": {
                "archive_member": entry["id"] + "/linux.json",
                "json_pointer": "/final",
            },
        },
        {
            "stage": "STOP",
            "model_terminal_before_final_evaluation": True,
            "reason": raw["stop_reason"],
        },
    ]
    return {
        "id": entry["id"],
        "task": entry["task"],
        "arm": entry["arm"],
        "deepest_envelope_success_stage": deepest,
        "check_envelope_success_is_not_check_pass": True,
        "stage_does_not_imply_prior_stages_closed": True,
        "first_successful_stage_call": first,
        "calls": rows,
        "timeline": milestones,
        "last_action": (
            {k: rows[-1][k] for k in ("ordinal", "action", "operation", "result")}
            if rows
            else None
        ),
        "first_mutation_metrics": metrics,
        "construction_calls": len(nodes),
        "distinct_constructed_revisions": len(set(nodes)),
        "repeated_calls": sum(r["repeat_of_ordinal"] is not None for r in rows),
        "source_revisits": sum(r.get("revisits_prior_source", False) for r in rows),
        "same_source_state_repeats": sum(
            r.get("repeat_with_same_source_state") is True for r in rows
        ),
        "model_directed_compiler_checks": sum(r["action"] == "check" for r in rows),
        "compiler_check_passes": sum(
            r.get("compiler_check_pass") is True for r in rows
        ),
        "post_edit_compiler_check_passes": sum(
            r.get("compiler_check_pass") is True
            and (r.get("source_generation_before") or 0) > 0
            for r in rows
        ),
        "distinct_diagnostic_messages": len({d["message_sha256"] for d in diag}),
        "diagnostic_occurrences": len(diag),
        "mechanisms": labels,
        "observed_disposition": raw["disposition"],
        "fresh_target_changed": raw["target_body_changed"],
        "authority_published": "alva-air/current" in linux["final_files"],
        "final_check_pass": linux["final"].get("check", {}).get("exit") == 0,
        "final_compiler_diagnostics": diagnostics(linux["final"]),
        "usage": usage,
        "final_totals": usage[-1]["cumulative"],
        "thresholds": {
            "first_observed_trigger": trigger,
            "token_cross_event_index": token_index,
            "tool_cross_event_index": tool_index,
            "wall_elapsed_seconds": raw["elapsed_seconds"],
            "wall_threshold_seconds": thresholds["wall_observation_seconds"],
            "token_overshoot": usage[-1]["cumulative"]["totalTokens"]
            - thresholds["token_observation_threshold"],
            "terminal": raw["terminal_status"],
            "interrupt_ack": raw["interrupt_ack"],
        },
    }


def main(archive, output):
    frozen = public_json("FREEZE.json")
    source_paths = [
        "FREEZE.json",
        "RESULTS.json",
        "ANALYSIS.json",
        "REPORT.md",
        "ARCHIVE.json",
    ]
    assert public_json("ARCHIVE.json")["sha256"] == EXPECTED
    published = {s["id"]: s for s in public_json("RESULTS.json")["slots"]}
    slots = []
    with verified_zip(archive) as z:
        assert len(z.namelist()) == 50
        for entry in frozen["schedule"]:
            raw = json.loads(z.read(entry["id"] + "/result.json"))
            linux = json.loads(z.read(entry["id"] + "/linux.json"))
            assert (
                raw["id"] == entry["id"]
                and raw["freeze_commit"] == "11bcc73464769b40b93bfb1b82df393c65b34626"
            )
            assert raw["disposition"] == published[entry["id"]]["disposition"]
            assert raw["usage"] == published[entry["id"]]["usage"]
            assert raw["tool_calls"] == published[entry["id"]]["tool_calls"]
            blob = next(
                e
                for e in frozen["tasks"][entry["task"]]["bundle"]["payload"]["entries"]
                if e["path"] == "src/task.alva"
            )
            slots.append(
                analyze_slot(
                    entry, raw, linux, frozen, base64.b64decode(blob["base64"])
                )
            )
    output.mkdir(parents=True, exist_ok=True)
    authority = {
        "baseline": BASE,
        "archive_sha256": EXPECTED,
        "public_source_sha256": {p: sha(public_blob(p)) for p in source_paths},
        "public_source_byte_policy": "exact baseline Git blobs; no checkout EOL normalization",
    }
    save(output / "STAGE-TRAJECTORIES.json", {"source": authority, "slots": slots})
    components = {
        name: {
            "utf8_bytes": len(text.encode()),
            "sha256": sha(text.encode()),
            "provider_component_tokens": None,
        }
        for name, text in frozen["docs"].items()
    }
    costs = {
        "source": authority,
        "components": components,
        "documents_total_utf8_bytes": sum(c["utf8_bytes"] for c in components.values()),
        "study_schema_canonical_json_bytes": len(canonical(frozen["tools"])),
        "native_schemas_canonical_json_bytes": len(canonical(frozen["native_tools"])),
        "native_schema_serialization_is_not_provider_wire": True,
        "provider_token_component_allocation": "UNAVAILABLE; no provider serialized request/token-span records",
        "cached_tokens_not_a_unique_context_size_or_price": True,
        "slots": [
            {
                "id": s["id"],
                "arm": s["arm"],
                "prompt_utf8_bytes": len(e["prompt"].encode()),
                "public_task_requirement_utf8_bytes": len(
                    frozen["tasks"][e["task"]]["public"]["requirement"].encode()
                ),
                "skill_inline_occurrences": {
                    name: e["prompt"].count(text)
                    for name, text in frozen["docs"].items()
                },
                "workspace_doc_availability": s["arm"] == "N",
                "explicit_skill_input_item": False,
                "automatic_skill_provider_injection_count": None,
                "logged_user_message_copies_not_counted_as_separate_delivery": True,
                "first_reported_input_tokens": s["usage"][0]["cumulative"][
                    "inputTokens"
                ],
                "final_totals": s["final_totals"],
                "usage_update_count_not_provider_request_count": len(s["usage"]),
                "total_dispatched_call_duration_ms": sum(
                    r["call_duration_ms"] or 0 for r in s["calls"]
                ),
                "thresholds": s["thresholds"],
            }
            for s, e in zip(slots, frozen["schedule"])
        ],
    }
    save(output / "TOKEN-COSTS.json", costs)
    known = {
        arm: {
            "slots": len([s for s in slots if s["arm"] == arm]),
            "calls": sum(len(s["calls"]) for s in slots if s["arm"] == arm),
            "total_tokens": sum(
                s["final_totals"]["totalTokens"] for s in slots if s["arm"] == arm
            ),
            "schema_discovery_calls": sum(
                r["stage"] == "SCHEMA_DISCOVERY"
                for s in slots
                if s["arm"] == arm
                for r in s["calls"]
            ),
            "repeat_calls": sum(s["repeated_calls"] for s in slots if s["arm"] == arm),
        }
        for arm in ("T", "B", "N")
    }
    save(
        output / "VALIDATION.json",
        {
            "status": "PASS",
            "source": authority,
            "slots": len(slots),
            "archive_entries": 50,
            "native_calls_joined_to_real_dispatch": True,
            "usage_totals_reconcile": True,
            "initial_prompts_match_freeze": True,
            "call_counts_reconcile": True,
            "trigger_order_crosschecked": True,
            "provider_calls": 0,
            "candidate_code_executions": 0,
            "raw_transcripts_copied_to_git": False,
            "historical_inputs_modified": False,
            "known": known,
            "limits": [
                "No serialized provider inputs",
                "No hidden reasoning used",
                "No causal root-cause identification",
                "All slots censored",
            ],
        },
    )
    print(
        json.dumps(
            {
                "validation": "PASS",
                "known": known,
                "components": costs["documents_total_utf8_bytes"],
                "schema_bytes": costs["native_schemas_canonical_json_bytes"],
                "stages": [
                    (
                        s["id"],
                        s["deepest_envelope_success_stage"],
                        s["repeated_calls"],
                        s["source_revisits"],
                    )
                    for s in slots
                ],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    main(args.archive, args.output)
