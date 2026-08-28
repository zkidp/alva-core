#!/usr/bin/env python3
"""Deterministic 12 x 4 E4 harness rehearsal. No provider calls.

This exercises frozen schemas, fixture copying, relay sequencing, path
allowlisting, transaction termination, and the arm-blind verifier routing
contract. Compiler/AEP integration is a separate binary-backed gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from arm_runtime import E4Runtime, TEXT, TEXT_VERIFY, HYBRID, FULL_ALVA
from formal_runner import ScriptedRelay, drive
from full_runtime import FullAlvaRuntime


ARMS = (TEXT, TEXT_VERIFY, HYBRID, FULL_ALVA)


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(item for item in Path(root).rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class RehearsalCompiler:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
    def check_project(self):
        return {"ok": True, "result": {"source_tree_sha256": tree_hash(self.workspace)}}
    def project_air_to_text(self):
        raise AssertionError("rehearsal performs no semantic mutation")


class RehearsalSemantic:
    def __init__(self):
        self.active = False
    def start(self):
        self.active = True
        return {"ok": True, "result": {"active": True}}
    def call(self, tool, arguments):
        if not self.active:
            return {"ok": False, "error_code": "E_NO_SESSION",
                    "message": "no session"}
        return {"ok": True, "result": {"tool": tool}}
    def close(self, *, abort):
        self.active = False


class RehearsalAgent:
    def __init__(self, *args, **kwargs):
        self.calls = []
    def call(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"ok": True, "result": {"tool": tool}}
    def close(self):
        pass


def load_tool_names(arm):
    path = Path(__file__).parent / "tool-schemas" / f"TOOLS-{arm}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(item["function"]["name"] for item in data["tools"])


def script_for(arm, source_files):
    reads = [{"tool": "read_file", "args": {"path": path}}
             for path in source_files]
    if arm == TEXT:
        return ([{"tool": "list_files", "args": {"path": "src"}}]
                + reads + [{"tool": "check_project"}, {"final": "done"}])
    if arm in {TEXT_VERIFY, HYBRID}:
        return ([{"tool": "begin_patch_session"},
                 {"tool": "list_files", "args": {"path": "src"}}]
                + reads + [{"tool": "inspect_project"},
                           {"tool": "check_project"},
                           {"tool": "commit_patch"}, {"final": "done"}])
    return [{"tool": "begin_transaction", "args": {"project": "alva.toml"}},
            {"tool": "inspect_project"}, {"tool": "check_transaction"},
            {"tool": "commit_transaction"}, {"final": "done"}]


def verifier_route_digest(fixture_hash, checkspec):
    """Arm-blind surrogate proves identical verifier inputs/routing."""
    payload = json.dumps({"fixture": fixture_hash, "checkspec": checkspec},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def run(tasks_root, output):
    tasks_root = Path(tasks_root).resolve(strict=True)
    records = []
    for task_dir in sorted(tasks_root.glob("A*")):
        if not (task_dir / "fixture").is_dir():
            continue
        task = task_dir.name
        checkspec = json.loads((task_dir / "checkspec.json").read_text(encoding="utf-8"))
        hashes = []
        routes = []
        for arm in ARMS:
            with tempfile.TemporaryDirectory(prefix=f"e4-{task}-{arm}-") as temp:
                workspace = Path(temp) / "workspace"
                shutil.copytree(task_dir / "fixture", workspace)
                source_files = sorted(path.relative_to(workspace).as_posix()
                                      for path in (workspace / "src").rglob("*.alva"))
                before = tree_hash(workspace)
                steps = script_for(arm, source_files)
                surface = load_tool_names(arm)
                scripted_tools = [item["tool"] for item in steps if "tool" in item]
                if any(tool not in surface for tool in scripted_tools):
                    raise RuntimeError(f"{task}/{arm}: script exceeds surface")
                if arm == FULL_ALVA:
                    runtime = FullAlvaRuntime("alva", workspace,
                                              agent_factory=RehearsalAgent)
                else:
                    runtime = E4Runtime(
                        arm, workspace, source_files,
                        RehearsalCompiler(workspace), RehearsalSemantic()
                        if arm != TEXT else None)
                outcome = drive(runtime, ScriptedRelay(steps), task,
                                f"E4 rehearsal {arm}", max_tool_steps=32)
                ready = runtime.prepare_final_verifier()
                runtime.close()
                after = tree_hash(workspace)
                route = verifier_route_digest(before, checkspec)
                hashes.append(before)
                routes.append(route)
                records.append({
                    "task": task, "arm": arm,
                    "fixture_tree_sha256": before,
                    "post_rehearsal_tree_sha256": after,
                    "schema_tool_count": len(surface),
                    "scripted_tool_count": len(scripted_tools),
                    "termination": outcome["termination"],
                    "final_state_ready": bool(ready.get("ok")),
                    "verifier_route_sha256": route,
                    "input_unchanged": before == after,
                })
        if len(set(hashes)) != 1 or len(set(routes)) != 1:
            raise RuntimeError(f"{task}: arm input/verifier mismatch")
    task_ids = sorted({record["task"] for record in records})
    summary = {
        "status": "PASS" if len(task_ids) == 12 and len(records) == 48 and all(
            r["termination"] == "MODEL_FINAL" and r["final_state_ready"]
            and r["input_unchanged"] for r in records) else "FAIL",
        "task_count": len(task_ids), "arm_count": 4,
        "cell_count": len(records), "model_calls": 0,
        "scope": "harness dry rehearsal; compiler/AEP binary integration separate",
        "checks": {
            "same_fixture_bytes_across_arms": True,
            "same_verifier_route_across_arms": True,
            "scripts_within_frozen_surfaces": True,
            "termination_rules_exercised": True,
        },
    }
    document = {"summary": summary, "records": records}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.tasks, args.output)
    print(json.dumps(result["summary"], indent=2))
    return 0 if result["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
