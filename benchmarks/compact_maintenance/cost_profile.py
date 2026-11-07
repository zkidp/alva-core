"""Read-only MIC-01 trace diagnosis. Bytes/calls are NOT token attribution.

Reads JSON directly from the authenticated archive, without extracting paths,
printing transcript content, invoking a provider, or modifying frozen records.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import statistics
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "benchmarks/maintenance_interface_comparison"
HERE = Path(__file__).parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def category(name, arguments):
    if name == "study":
        return {"doc": "documentation", "read": "source_read", "search": "source_read",
                "revision": "navigation", "diff": "preview", "edit": "source_mutation",
                "write": "source_mutation", "check": "check_test", "test": "check_test",
                "finish": "handoff"}.get(arguments.get("action"), "unknown")
    if name.startswith("create_") or name == "construct_expression":
        return "node_construction"
    if name in ("replace_expression", "change_field"):
        return "node_mutation"
    if name in ("resolve_entity", "applicable_operations", "describe_operation", "describe_construction"):
        return "navigation"
    if name.startswith("inspect_"):
        return "graph_inspection"
    if name == "preview_semantic_diff":
        return "preview"
    if name == "check_transaction":
        return "check_test"
    if name in ("begin_transaction", "commit_transaction", "abort_transaction"):
        return "transaction"
    return "unknown"


def text_content(items):
    # Record only explicitly textual content, not structuredContent a second
    # time, transport metadata, or image/resource placeholders.
    return "".join(i["text"] for i in items if isinstance(i, dict)
                     and i.get("type") in ("text", "inputText", "outputText")
                     and isinstance(i.get("text"), str)).encode("utf-8")


def failed(item):
    if item.get("error") or item.get("status") == "failed" or item.get("success") is False:
        return True
    result = item.get("result") or {}
    if result.get("isError"):
        return True
    for block in result.get("content", []) + item.get("contentItems", []):
        if block.get("type") not in ("text", "inputText", "outputText"):
            continue
        try:
            value = json.loads(block["text"])
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(value, dict) and (value.get("error") or value.get("isError")):
            return True
    return False


def profile_record(record):
    rows, seen, duplicates = [], set(), 0
    replies = set()
    for event in record.get("events", []):
        item = event.get("params", {}).get("item", {})
        if event.get("method") != "item/completed" or item.get("type") not in ("mcpToolCall", "dynamicToolCall"):
            continue
        if item["id"] in seen:
            duplicates += 1
            continue
        seen.add(item["id"])
        name, args = item["tool"], item.get("arguments", {})
        result = item.get("result") or {}
        content = item.get("contentItems", []) if item["type"] == "dynamicToolCall" else result.get("content", [])
        text = text_content(content)
        key = digest(text) if text else None
        rows.append({"category": category(name, args), "tool": name,
                     "action": args.get("action") if name == "study" else None,
                     "argument_utf8_bytes": len(encoded(args)),
                     "text_reply_utf8_bytes": len(text),
                     "serialized_reply_utf8_bytes": len(encoded(item.get("contentItems", []) if item["type"] == "dynamicToolCall" else result)),
                     "repeated_reply_utf8_bytes": len(text) if key and key in replies else 0,
                     "failed": failed(item), "duration_ms": item.get("durationMs")})
        if key:
            replies.add(key)
    grouped = {}
    for label in sorted({r["category"] for r in rows}):
        selected = [r for r in rows if r["category"] == label]
        grouped[label] = {"calls": len(selected), "failed_calls": sum(r["failed"] for r in selected),
                          **{k: sum(r[k] for r in selected) for k in (
                              "argument_utf8_bytes", "text_reply_utf8_bytes", "serialized_reply_utf8_bytes", "repeated_reply_utf8_bytes")}}
    return {"completed_model_tool_items": len(rows), "duplicate_terminal_events_ignored": duplicates,
            "recorded_started_tool_calls": record.get("tool_calls"),
            "unfinished_or_unrecorded_terminal_items": (record.get("tool_calls") - len(rows))
                if isinstance(record.get("tool_calls"), int) else None,
            "by_category": grouped, "by_tool": dict(sorted(Counter(r["tool"] for r in rows).items())),
            "failed_model_tool_items": sum(r["failed"] for r in rows),
            "calls_after_first_failed_item": next((len(rows) - i - 1 for i, r in enumerate(rows) if r["failed"]), 0),
            "total_text_reply_utf8_bytes": sum(r["text_reply_utf8_bytes"] for r in rows),
            "repeated_reply_utf8_bytes": sum(r["repeated_reply_utf8_bytes"] for r in rows)}


def analyze(archive):
    manifest = json.loads((OLD / "ARCHIVES.json").read_bytes())
    expected = next(a for a in manifest["archives"] if a["name"] == "MODEL-RAW.zip")
    if archive.stat().st_size != expected["bytes"]:
        raise ValueError("Archive size mismatch; no analysis performed")
    raw = archive.read_bytes()
    if digest(raw) != expected["sha256"]:
        raise ValueError("Archive identity mismatch; no analysis performed")
    old = json.loads((OLD / "RESULTS.json").read_bytes())
    rows = []
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts for n in names):
            raise ValueError("Ambiguous or unsafe archive members")
        for registered in old["rows"]:
            path = registered["id"] + "/record.json"
            data = z.read(path)
            if digest(data) != registered["record_sha256"]:
                raise ValueError("Record identity mismatch: " + registered["id"])
            record = json.loads(data)
            if (record.get("usage") or {}).get("total") != registered["reported_usage"]:
                raise ValueError("Reported usage mismatch: " + registered["id"])
            linux_data = z.read(registered["id"] + "/linux.json")
            if digest(linux_data) != registered["linux_evidence_sha256"]:
                raise ValueError("Backend evidence identity mismatch: " + registered["id"])
            linux = json.loads(linux_data)
            backend = [e for e in linux["calls"] if "request" in e]
            schemas = [e["response"]["tools"] for e in backend if e["request"]["method"] == "tools/list"]
            row = {k: registered[k] for k in ("id", "task", "arm", "repeat", "correct", "evaluation_eligible", "reported_usage")}
            row.update(profile_record(record))
            row.update(backend_rpc_requests=len(backend),
                       backend_native_tool_requests=sum(e["request"]["method"] == "tools/call" for e in backend),
                       backend_study_actions=sum("action" in e for e in linux["calls"]),
                       observed_tools_list_responses=len(schemas),
                       native_schema_canonical_utf8_bytes=len(encoded(schemas[0])) if schemas else None,
                       record_sha256=digest(data), linux_evidence_sha256=digest(linux_data))
            rows.append(row)
    pairs = []
    for p in old["pairs"]:
        if "T_total_tokens" not in p:
            continue
        pair = {r["arm"]: r for r in rows if (r["task"], r["repeat"]) == (p["task"], p["repeat"])}
        pairs.append({"task": p["task"], "repeat": p["repeat"], **{
            arm: {"reported_total_tokens": pair[arm]["reported_usage"]["totalTokens"],
                  "completed_model_tool_items": pair[arm]["completed_model_tool_items"],
                  "total_text_reply_utf8_bytes": pair[arm]["total_text_reply_utf8_bytes"],
                  "failed_model_tool_items": pair[arm]["failed_model_tool_items"]}
            for arm in ("T", "N")}})
    groups = {}
    for arm in ("T", "N"):
        chosen = [r for r in rows if r["arm"] == arm and r["evaluation_eligible"]]
        categories = defaultdict(Counter)
        for r in chosen:
            for label, counters in r["by_category"].items():
                categories[label].update(counters)
        matched = [r for r in chosen if any((p["task"], p["repeat"]) == (r["task"], r["repeat"]) for p in pairs)]
        matched_categories = defaultdict(Counter)
        for r in matched:
            for label, counters in r["by_category"].items():
                matched_categories[label].update(counters)
        groups[arm] = {"eligible_slots": len(chosen), "by_category": dict(sorted(categories.items())),
                       "both_success_slots": len(matched), "both_success_by_category": dict(sorted(matched_categories.items())),
                       "failed_model_tool_items": sum(r["failed_model_tool_items"] for r in chosen),
                       "completed_model_tool_items": sum(r["completed_model_tool_items"] for r in chosen),
                       "reported_usage": {key: sum(r["reported_usage"][key] for r in chosen)
                                          for key in ("totalTokens", "inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens")},
                       "both_success_medians": {key: statistics.median(p[arm][key] for p in pairs)
                                                for key in pairs[0][arm]}}
    return {"schema": "mic02-cost-diagnosis/v1", "status": "READ_ONLY_DESCRIPTIVE_ANALYSIS",
            "archive_sha256": digest(raw), "old_results_sha256": digest(subprocess.check_output(
                ["git", "show", "HEAD:benchmarks/maintenance_interface_comparison/RESULTS.json"], cwd=ROOT)),
            "old_results_hash_basis": "committed Git blob, independent of checkout line endings",
            "model_generation_calls": 0, "input_token_api_calls": 0,
            "per_category_tokens": None, "provider_requests": None, "dollar_cost": None,
            "limitations": ["Bytes are canonicalized log payload sizes, not provider token attribution or exact prompt representation.",
                            "MCP text and structured content are separate metrics; their appearance in actual model context is not known.",
                            "Repeated replies and calls after errors may be necessary; they are not measured avoidable cost.",
                            "Eight both-success pairs are survivor-selected; prior quota and CLI-identity limitations remain.",
                            "Eligible arm aggregates have unequal denominators; use matched pairs for comparisons.",
                            "Historical backend logging is not a complete end-to-end Host execution trace."],
            "rows": rows, "arms": groups, "both_success_pairs": pairs}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("archive", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = analyze(args.archive)
    args.output.write_bytes(json.dumps(result, indent=2).encode() + b"\n")
    print(json.dumps({"slots": len(result["rows"]), "pairs": len(result["both_success_pairs"]),
                      "model_generation_calls": 0, "output_sha256": digest(args.output.read_bytes())}))
