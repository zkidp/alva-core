#!/usr/bin/env python3
"""Experiment A formal Luna runner: 12 tasks x 4 arms x 2 reps = 96 cells.

This is the frozen execution driver for the E4 interface-architecture
tournament. It reuses the same control-path components as the binary-backed
rehearsal (arm runtimes, arm-blind verifier, Luna relay) and adds:

  - a deterministic schedule: tasks sorted lexicographically, arms in the
    fixed order (TEXT, TEXT_VERIFY, HYBRID, FULL_ALVA), reps 1 then 2;
  - per-cell evidence files (raw trajectory, telemetry, fingerprint,
    verifier result, frozen metric derivations, wall time, input hashes);
  - checkpoint/resume: completed cells are never re-run; a cell whose file
    is absent is executed again on resume;
  - fail-closed input validation (binary SHA, schema hashes, prompt
    registry, task statements, env-only key);
  - no early stopping and no outcome-based selection: every cell runs to
    terminal state regardless of verifier result.

Credentials are environment-only: OPENAI_API_KEY must be set in the
environment of this process. The key is never written to any file.

Frozen constants (see EXECUTION-FREEZE-01):
  max_tool_steps = 32 (matches the 12x4 binary rehearsal)
  request timeout = 180 s (LunaRelay default)
  model = gpt-5.6-luna, protocol = openai-responses-function-loop-v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from arm_runtime import (
    AFFORDANCE_TOOLS,
    CONTROL_TOOLS,
    CompilerBridge,
    E4Runtime,
    FULL_ALVA,
    HYBRID,
    TEXT,
    TEXT_VERIFY,
)
from formal_runner import drive
from full_runtime import FullAlvaRuntime
from luna_relay import LunaRelay, MODEL, PROTOCOL
from semantic_session import SemanticSession
from unified_verifier import verify_final


EXPECTED_BINARY_SHA256 = (
    "eeb8d437c262fbfe1502141d26150fbfdecf15699eb521a4469b90ec7b8cca23"
)
ARMS = (TEXT, TEXT_VERIFY, HYBRID, FULL_ALVA)
REPS = (1, 2)
MAX_TOOL_STEPS = 32
SCHEMA_MANIFEST = "SCHEMA-MANIFEST.json"

MUTATION_TOOLS = frozenset({
    "write_file", "apply_patch",
    "migrate_signature", "rename_entity", "set_effect",
    "commit_transaction",
})


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def frozen_input_hash(workspace, source_files):
    digest = hashlib.sha256()
    for rel in ["alva.toml", *source_files]:
        digest.update(rel.encode())
        digest.update(hashlib.sha256((Path(workspace) / rel).read_bytes()).digest())
    return digest.hexdigest()


def read_exact_utf8(path):
    """Decode UTF-8 without universal-newline translation."""
    return Path(path).read_bytes().decode("utf-8")


def baseline_revisions(alva, workspace, functions):
    compiler = CompilerBridge(alva, workspace)
    checked = compiler.check_project()
    if not checked.get("ok"):
        raise RuntimeError("baseline compiler gate failed")
    session = SemanticSession(alva, Path(workspace) / "alva.toml")
    started = session.start()
    if not started.get("ok"):
        raise RuntimeError("baseline semantic session failed")
    revisions = {}
    try:
        for function in functions:
            result = session.call("inspect_function", {"name": function})
            if not result.get("ok"):
                raise RuntimeError(f"baseline inspect failed: {function}")
            revisions[function] = result["result"]["revision"]
    finally:
        session.close(abort=True)
    return revisions


def load_schema_tools(runner_dir, arm):
    payload = json.loads(
        (runner_dir / "tool-schemas" / f"TOOLS-{arm}.json")
        .read_text(encoding="utf-8"))
    return payload["tools"] if isinstance(payload, dict) and "tools" in payload else payload


def load_schema_bytes(runner_dir, arm):
    return (runner_dir / "tool-schemas" / f"TOOLS-{arm}.json").read_bytes()


def load_schema_manifest(runner_dir):
    payload = json.loads(
        (runner_dir / "tool-schemas" / SCHEMA_MANIFEST).read_text(encoding="utf-8"))
    return payload


def load_statements(path):
    """Load task statements, accepting the wrapped document format."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "statements" in payload:
        statements = payload["statements"]
    else:
        statements = payload
    if not isinstance(statements, dict):
        raise RuntimeError("task statements file must contain a dict")
    return statements


def render_telemetry(path):
    if not Path(path).is_file():
        return []
    records = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def usage_tokens(record):
    usage = record.get("usage") or {}
    details = usage.get("input_tokens_details") or {}
    out_details = usage.get("output_tokens_details") or {}
    return {
        "input": int(usage.get("input_tokens", 0)),
        "cached": int(details.get("cached_tokens", 0)),
        "cache_write": int(details.get("cache_write_tokens", 0)),
        "output": int(usage.get("output_tokens", 0)),
        "reasoning": int(out_details.get("reasoning_tokens", 0)),
        "total": int(usage.get("total_tokens", 0)),
    }


def classify_failure(error_code):
    """Frozen mechanical classification of failed calls (descriptive tax)."""
    if not error_code:
        return "other"
    if error_code == "E_UNKNOWN_TOOL":
        return "tool_selection_failure"
    if any(token in error_code.upper() for token in
           ("ARG", "INVALID", "MALFORMED", "PARSE", "PATH")):
        return "argument_binding_failure"
    return "other_failure"


def derive_metrics(arm, trajectory, telemetry_records, verifier, wall_s,
                   tool_schema_bytes):
    """Frozen metric derivations (EXPERIMENT-A-PLAN.md section Metrics)."""
    tokens = [usage_tokens(rec) for rec in telemetry_records]
    total_prompt = sum(item["input"] for item in tokens)
    total_cached = sum(item["cached"] for item in tokens)
    total_cache_write = sum(item["cache_write"] for item in tokens)
    total_completion = sum(item["output"] for item in tokens)
    total_reasoning = sum(item["reasoning"] for item in tokens)

    calls = list(trajectory)
    failed_calls = [c for c in calls if not c["result"].get("ok")]
    check_fails = [c for c in calls
                   if c["tool"] == "check_project" and not c["result"].get("ok")]

    first_mut = next(
        (c for c in calls
         if c["tool"] in MUTATION_TOOLS and c["result"].get("ok")), None)
    if first_mut is not None:
        # Serial relay: ordinal k maps to the k-th completed model turn, so
        # the latency prefix is the first `k` telemetry records.
        prefix = tokens[:first_mut["ordinal"]]
        first_change_latency = sum(item["input"] + item["output"] for item in prefix)
    else:
        first_change_latency = None

    if arm == HYBRID:
        semantic_adoption = sum(
            1 for c in calls if c["tool"] in AFFORDANCE_TOOLS)
    elif arm == TEXT_VERIFY:
        semantic_adoption = sum(
            1 for c in calls
            if c["tool"] in CONTROL_TOOLS or c["tool"] == "check_project")
    else:
        semantic_adoption = 0

    tool_selection_failures = sum(
        1 for c in failed_calls if c["result"].get("error_code") == "E_UNKNOWN_TOOL")
    argument_binding_failures = sum(
        1 for c in failed_calls
        if classify_failure(c["result"].get("error_code"))
        == "argument_binding_failure")
    other_failures = sum(
        1 for c in failed_calls
        if classify_failure(c["result"].get("error_code")) == "other_failure")

    edit_payload_bytes = 0
    patch_lines = 0
    for c in calls:
        args = c.get("args") or {}
        if c["tool"] == "write_file" and isinstance(args.get("content"), str):
            edit_payload_bytes += len(args["content"].encode("utf-8"))
        if c["tool"] == "apply_patch" and isinstance(args.get("diff"), str):
            payload = args["diff"].encode("utf-8")
            edit_payload_bytes += len(payload)
            patch_lines += len(args["diff"].splitlines())

    static_schema_bytes = len(tool_schema_bytes)
    static_schema_tokens_est = max(1, static_schema_bytes // 4)
    dynamic_conversation_tokens = max(0, total_prompt - static_schema_tokens_est)

    return {
        "correctness": bool(verifier.get("ok")),
        "total_prompt_tokens": total_prompt,
        "cached_prompt_tokens": total_cached,
        "cache_write_tokens": total_cache_write,
        "completion_tokens": total_completion,
        "reasoning_tokens": total_reasoning,
        "total_tokens": total_prompt + total_completion,
        "wall_seconds": round(wall_s, 3),
        "api_turns": len(telemetry_records),
        "failure_repair_burden": len(failed_calls) + len(check_fails),
        "first_change_latency": first_change_latency,
        "semantic_adoption": semantic_adoption,
        "raw_tool_call_count": len(calls),
        "tool_selection_failures": tool_selection_failures,
        "argument_binding_failures": argument_binding_failures,
        "other_failures": other_failures,
        "edit_payload_bytes": edit_payload_bytes,
        "patch_lines": patch_lines,
        "static_tool_schema_bytes": static_schema_bytes,
        "static_tool_schema_tokens_est": static_schema_tokens_est,
        "dynamic_conversation_tokens": dynamic_conversation_tokens,
    }


def schedule_cells(tasks_root):
    task_ids = sorted(
        path.name for path in tasks_root.glob("A*")
        if path.is_dir() and (path / "fixture").is_dir())
    return [(task, arm, rep)
            for task in task_ids for arm in ARMS for rep in REPS]


def validate_inputs(tasks_root, alva, runner_dir, registry_path, statements_path):
    alva = Path(alva).resolve(strict=True)
    if sha256_file(alva) != EXPECTED_BINARY_SHA256:
        raise RuntimeError(
            f"frozen ALVA binary SHA mismatch: "
            f"got {sha256_file(alva)}, expected {EXPECTED_BINARY_SHA256}")
    tasks_root = Path(tasks_root).resolve(strict=True)
    task_ids = sorted(
        path.name for path in tasks_root.glob("A*")
        if path.is_dir() and (path / "fixture").is_dir())
    if not task_ids:
        raise RuntimeError("no task dirs found")
    for task in task_ids:
        task_dir = tasks_root / task
        for required in ("checkspec.json", "metadata.json"):
            if not (task_dir / required).is_file():
                raise RuntimeError(f"{task}: missing {required}")
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    if set(registry["arms"]) != set(ARMS):
        raise RuntimeError("prompt registry arms do not match frozen arms")
    manifest = load_schema_manifest(runner_dir)
    for arm in ARMS:
        actual = sha256_bytes(load_schema_bytes(runner_dir, arm))
        declared = registry["arms"][arm]["schema_sha256"]
        if actual.lower() != declared.lower():
            raise RuntimeError(f"{arm}: schema hash mismatch "
                              f"(schema {actual[:12]} vs registry {declared[:12]})")
        manifest_value = manifest.get(arm)
        if isinstance(manifest_value, dict):
            declared_manifest = manifest_value.get("sha256")
        else:
            declared_manifest = manifest_value
        if declared_manifest and actual.lower() != str(declared_manifest).lower():
            raise RuntimeError(f"{arm}: schema hash mismatch vs SCHEMA-MANIFEST")
    statements = load_statements(statements_path)
    if set(statements) != set(task_ids):
        raise RuntimeError("task statements do not cover the 12 frozen tasks")
    for task in task_ids:
        if not isinstance(statements[task], str) or not statements[task].strip():
            raise RuntimeError(f"{task}: empty statement")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("FAIL_CLOSED: OPENAI_API_KEY unset")
    return task_ids, registry, statements


def build_runtime(arm, alva, workspace, source_files):
    if arm == FULL_ALVA:
        return FullAlvaRuntime(alva, workspace)
    semantic = SemanticSession(alva, Path(workspace) / "alva.toml") if arm != TEXT else None
    return E4Runtime(
        arm, workspace, source_files,
        CompilerBridge(alva, workspace), semantic)


def run_cell(task, arm, rep, alva, tasks_root, runner_dir, registry,
             statements, out_dir):
    task_dir = tasks_root / task
    checkspec = json.loads((task_dir / "checkspec.json").read_text(encoding="utf-8"))
    metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"e4-baseline-{task}-") as base_temp:
        base_ws = Path(base_temp) / "workspace"
        shutil.copytree(task_dir / "fixture", base_ws)
        baseline = baseline_revisions(alva, base_ws, metadata["functions"])

    tools = load_schema_tools(runner_dir, arm)
    tool_schema_bytes = load_schema_bytes(runner_dir, arm)
    cell_id = f"{task}-{arm}-r{rep}"
    cells_dir = out_dir / "cells"
    telemetry_dir = out_dir / "telemetry"
    fingerprint_dir = out_dir / "fingerprint"
    for directory in (cells_dir, telemetry_dir, fingerprint_dir):
        directory.mkdir(parents=True, exist_ok=True)
    telemetry_path = telemetry_dir / f"{cell_id}.jsonl"
    fingerprint_path = fingerprint_dir / f"{cell_id}.json"

    with tempfile.TemporaryDirectory(prefix=f"e4-{cell_id}-") as temp:
        workspace = Path(temp) / "workspace"
        shutil.copytree(task_dir / "fixture", workspace)
        source_files = sorted(
            path.relative_to(workspace).as_posix()
            for path in (workspace / "src").rglob("*.alva"))
        before = frozen_input_hash(workspace, source_files)
        runtime = build_runtime(arm, alva, workspace, source_files)
        relay = LunaRelay(tools, telemetry_path, fingerprint_path)
        started = time.monotonic()
        outcome = drive(
            runtime, relay,
            statements[task],
            registry["arms"][arm]["prefix"],
            max_tool_steps=MAX_TOOL_STEPS)
        wall_s = time.monotonic() - started
        verifier = verify_final(runtime, alva, workspace, checkspec, baseline)
        runtime.close()
        after = frozen_input_hash(workspace, source_files)

    telemetry = render_telemetry(telemetry_path)
    fingerprint = None
    if fingerprint_path.is_file():
        fingerprint = json.loads(fingerprint_path.read_text(encoding="utf-8"))
    metrics = derive_metrics(
        arm, outcome["trajectory"], telemetry, verifier, wall_s, tool_schema_bytes)
    record = {
        "cell_id": cell_id,
        "task": task,
        "arm": arm,
        "rep": rep,
        "statement_sha256": sha256_bytes(statements[task].encode("utf-8")),
        "termination": outcome["termination"],
        "final": outcome.get("final"),
        "failure": outcome.get("failure"),
        "trajectory": outcome["trajectory"],
        "verifier": verifier,
        "metrics": metrics,
        "input_projection_sha256": before,
        "post_projection_sha256": after,
        "input_projection_unchanged": before == after,
        "model": MODEL,
        "protocol": PROTOCOL,
        "fingerprint": fingerprint,
        "telemetry": telemetry,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    cell_path = cells_dir / f"{cell_id}.json"
    tmp_path = cell_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, cell_path)
    return record


def save_state(out_dir, schedule, completed, started_at):
    state = {
        "schedule_total": len(schedule),
        "completed": sorted(completed),
        "remaining": [f"{t}-{a}-r{r}" for t, a, r in schedule
                      if f"{t}-{a}-r{r}" not in set(completed)],
        "started_at": started_at,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "state.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def run(tasks_root, alva, runner_dir, registry_path, statements_path, out_dir):
    runner_dir = Path(runner_dir).resolve(strict=True)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    task_ids, registry, statements = validate_inputs(
        tasks_root, alva, runner_dir, registry_path, statements_path)
    schedule = schedule_cells(Path(tasks_root))
    if not schedule:
        raise RuntimeError("empty schedule")
    cells_dir = out_dir / "cells"
    cells_dir.mkdir(parents=True, exist_ok=True)
    completed = []
    for path in sorted(cells_dir.glob("*.json")):
        completed.append(path.stem)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for index, (task, arm, rep) in enumerate(schedule, start=1):
        cell_id = f"{task}-{arm}-r{rep}"
        if (cells_dir / f"{cell_id}.json").is_file():
            completed.append(cell_id)
            continue
        print(f"[{index:02d}/{len(schedule)}] START {cell_id}", flush=True)
        try:
            record = run_cell(
                task, arm, rep, str(alva), Path(tasks_root), runner_dir,
                registry, statements, out_dir)
            summary = {
                "termination": record["termination"],
                "verifier_ok": record["verifier"].get("ok"),
                "api_turns": record["metrics"]["api_turns"],
                "wall_s": record["metrics"]["wall_seconds"],
            }
            print(f"[{index:02d}/{len(schedule)}] DONE  {cell_id} {summary}",
                  flush=True)
        except Exception as exc:
            # A cell-level failure must not abort the schedule: record it as
            # a HARNESS_FAILURE cell so it is preserved as evidence, then
            # continue. The schedule itself is never outcome-selected.
            cells_dir.mkdir(parents=True, exist_ok=True)
            cell_path = cells_dir / f"{cell_id}.json"
            record = {
                "cell_id": cell_id,
                "task": task,
                "arm": arm,
                "rep": rep,
                "termination": "HARNESS_FAILURE",
                "failure": f"{type(exc).__name__}: {exc}",
                "trajectory": [],
                "verifier": {"ok": False, "reason": "NOT_RUN",
                             "prepare": {"ok": False},
                             "output": ""},
                "metrics": None,
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            cell_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            print(f"[{index:02d}/{len(schedule)}] HARNESS_FAILURE {cell_id}: "
                  f"{record['failure']}", flush=True)
        save_state(out_dir, schedule, completed, started_at)

    done = sorted(path.stem for path in cells_dir.glob("*.json"))
    summary = {
        "status": "COMPLETED" if len(done) == len(schedule) else "INCOMPLETE",
        "schedule_total": len(schedule),
        "cell_files": len(done),
        "model": MODEL,
        "protocol": PROTOCOL,
        "max_tool_steps": MAX_TOOL_STEPS,
        "binary_sha256": sha256_file(alva),
        "out_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--alva", required=True)
    parser.add_argument("--statements", required=True)
    parser.add_argument("--prompt-registry", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--runner-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runner_dir = Path(args.runner_dir or Path(__file__).resolve().parent)
    if args.dry_run:
        task_ids, registry, _ = validate_inputs(
            args.tasks, args.alva, runner_dir,
            args.prompt_registry, args.statements)
        schedule = schedule_cells(Path(args.tasks))
        print(json.dumps({
            "dry_run": "PASS",
            "tasks": task_ids,
            "cells": len(schedule),
            "binary_sha256": sha256_file(args.alva),
            "arms": list(registry["arms"]),
            "model": MODEL,
        }, indent=2))
        return 0
    summary = run(args.tasks, args.alva, runner_dir,
                  args.prompt_registry, args.statements, args.out)
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
