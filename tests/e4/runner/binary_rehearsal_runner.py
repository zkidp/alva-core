#!/usr/bin/env python3
"""12 x 4 binary-backed E4 integration rehearsal; zero provider calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from arm_runtime import CompilerBridge, E4Runtime, TEXT, TEXT_VERIFY, HYBRID, FULL_ALVA
from formal_runner import ScriptedRelay, drive
from full_runtime import FullAlvaRuntime
from semantic_session import SemanticSession
from unified_verifier import verify_final


EXPECTED_BINARY_SHA256 = "eeb8d437c262fbfe1502141d26150fbfdecf15699eb521a4469b90ec7b8cca23"
ARMS = (TEXT, TEXT_VERIFY, HYBRID, FULL_ALVA)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_input_hash(workspace, source_files):
    digest = hashlib.sha256()
    for rel in ["alva.toml", *source_files]:
        digest.update(rel.encode())
        digest.update(hashlib.sha256((Path(workspace) / rel).read_bytes()).digest())
    return digest.hexdigest()


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


def load_tool_names(runner_dir, arm):
    payload = json.loads((runner_dir / "tool-schemas" / f"TOOLS-{arm}.json")
                         .read_text(encoding="utf-8"))
    return frozenset(item["function"]["name"] for item in payload["tools"])


def script_for(arm, source_files, first_content):
    reads = [{"tool": "read_file", "args": {"path": path}}
             for path in source_files]
    same_write = {"tool": "write_file", "args": {
        "path": source_files[0], "content": first_content}}
    if arm == TEXT:
        return ([{"tool": "list_files", "args": {"path": "src"}}]
                + reads + [same_write, {"tool": "check_project"},
                           {"final": "done"}])
    if arm in {TEXT_VERIFY, HYBRID}:
        return ([{"tool": "begin_patch_session"},
                 {"tool": "list_files", "args": {"path": "src"}}]
                + reads + [same_write, {"tool": "check_project"},
                           {"tool": "inspect_project"},
                           {"tool": "commit_patch"}, {"final": "done"}])
    return [{"tool": "begin_transaction", "args": {"project": "alva.toml"}},
            {"tool": "inspect_project"}, {"tool": "check_transaction"},
            {"tool": "commit_transaction"}, {"final": "done"}]


def run(tasks_root, alva, output):
    tasks_root = Path(tasks_root).resolve(strict=True)
    alva = Path(alva).resolve(strict=True)
    if sha256_file(alva) != EXPECTED_BINARY_SHA256:
        raise RuntimeError("frozen ALVA binary SHA mismatch")
    runner_dir = Path(__file__).resolve().parent
    records = []
    for task_dir in sorted(tasks_root.glob("A*")):
        if not (task_dir / "fixture").is_dir():
            continue
        task = task_dir.name
        checkspec = json.loads((task_dir / "checkspec.json").read_text(encoding="utf-8"))
        metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix=f"e4-baseline-{task}-") as base_temp:
            base_ws = Path(base_temp) / "workspace"
            shutil.copytree(task_dir / "fixture", base_ws)
            baseline = baseline_revisions(alva, base_ws, metadata["functions"])
        task_hashes, verifier_results = [], []
        for arm in ARMS:
            with tempfile.TemporaryDirectory(prefix=f"e4-{task}-{arm}-") as temp:
                workspace = Path(temp) / "workspace"
                shutil.copytree(task_dir / "fixture", workspace)
                source_files = sorted(path.relative_to(workspace).as_posix()
                                      for path in (workspace / "src").rglob("*.alva"))
                before = frozen_input_hash(workspace, source_files)
                task_hashes.append(before)
                script = script_for(
                    arm, source_files,
                    (workspace / source_files[0]).read_text(encoding="utf-8"))
                names = load_tool_names(runner_dir, arm)
                if any(item["tool"] not in names for item in script if "tool" in item):
                    raise RuntimeError(f"{task}/{arm}: script exceeds schema")
                if arm == FULL_ALVA:
                    runtime = FullAlvaRuntime(alva, workspace)
                else:
                    runtime = E4Runtime(
                        arm, workspace, source_files,
                        CompilerBridge(alva, workspace),
                        SemanticSession(alva, workspace / "alva.toml")
                        if arm != TEXT else None)
                outcome = drive(runtime, ScriptedRelay(script), task,
                                f"binary rehearsal {arm}", max_tool_steps=32)
                verifier = verify_final(runtime, alva, workspace, checkspec, baseline)
                runtime.close()
                after = frozen_input_hash(workspace, source_files)
                verifier_results.append(verifier["ok"])
                records.append({
                    "task": task, "arm": arm,
                    "fixture_projection_sha256": before,
                    "post_projection_sha256": after,
                    "input_projection_unchanged": before == after,
                    "termination": outcome["termination"],
                    "runtime_failure": outcome.get("failure"),
                    "trajectory_calls": len(outcome["trajectory"]),
                    "final_verifier_ok": verifier["ok"],
                    "final_verifier_reason": verifier["reason"],
                })
        if len(set(task_hashes)) != 1 or len(set(verifier_results)) != 1:
            raise RuntimeError(f"{task}: arm alignment failure")
    tasks = sorted({record["task"] for record in records})
    passed = (len(tasks) == 12 and len(records) == 48 and all(
        record["termination"] == "MODEL_FINAL"
        and record["runtime_failure"] is None
        and record["input_projection_unchanged"] for record in records))
    document = {
        "summary": {
            "status": "PASS" if passed else "FAIL",
            "binary_sha256": sha256_file(alva),
            "task_count": len(tasks), "arm_count": 4,
            "cell_count": len(records), "model_calls": 0,
            "all_unmodified_verifier_results_identical_per_task": True,
            "claim_boundary": "control-path integration rehearsal; no task solution applied",
        },
        "records": records,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--alva", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    document = run(args.tasks, args.alva, args.output)
    print(json.dumps(document["summary"], indent=2))
    return 0 if document["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
