#!/usr/bin/env python3
"""Deterministic S06/S07 acceptance checks for VNext-02B."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


class Agent:
    def __init__(self, binary: Path, event_log: Path | None, session: str):
        command = [str(binary), "agent", "--session-id", session]
        if event_log is not None:
            command += ["--event-log", str(event_log)]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def call(self, tool: str, **arguments: object) -> dict:
        assert self.process.stdin and self.process.stdout and self.process.stderr
        request = {"request_id": tool, "tool": tool, **arguments}
        self.process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        assert line, self.process.stderr.read()
        return json.loads(line)

    def close(self) -> None:
        assert self.process.stdin and self.process.stderr
        self.process.stdin.close()
        stderr = self.process.stderr.read()
        assert self.process.wait(timeout=10) == 0, stderr
        assert not stderr, stderr


def without_execution(response: dict) -> dict:
    result = dict(response)
    result.pop("execution", None)
    return result


def load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


def run_s06(
    binary: Path, fixture: Path, project: Path, event_log: Path | None
) -> tuple[dict, dict, dict, dict]:
    shutil.copytree(fixture, project)
    manifest = str(project / "alva.toml")
    concurrent = Agent(binary, event_log, "s06-concurrent")
    writer = Agent(binary, event_log, "s06-writer")
    assert concurrent.call("begin_transaction", project=manifest)["ok"]
    assert writer.call("begin_transaction", project=manifest)["ok"]
    registered = writer.call(
        "register_recovery_intent",
        original_target="query.x.has",
        original_obligations=["apply discount behavior while preserving the public API"],
    )
    assert registered["ok"], registered
    replacement = writer.call(
        "register_recovery_intent",
        original_target="query.x.has",
        original_obligations=["replace the original task after seeing later state"],
    )
    assert not replacement["ok"]
    assert replacement["message"].startswith(
        "E_AEP_RECOVERY_INTENT_ALREADY_REGISTERED"
    )
    assert writer.call(
        "rename_entity", entity="query.x.has", new_name="writer_private_name"
    )["ok"]
    assert concurrent.call(
        "rename_entity", entity="query.x.has", new_name="compute_price"
    )["ok"]
    concurrent_commit = concurrent.call("commit_transaction")
    assert concurrent_commit["ok"], concurrent_commit
    stale = writer.call("commit_transaction")
    assert not stale["ok"] and "E_AEP_CONFLICT" in stale["message"], stale
    context_response = writer.call("inspect_recovery_context")
    assert context_response["ok"], context_response
    context = context_response["result"]
    assert context["original_target"]["qualified"] == "query.x.has"
    assert context["current_target"]["qualified"] == "query.x.compute_price"
    assert context["target_rebinding"] == "renamed", context
    assert context["original_obligations"] == context["preserved_obligations"]
    assert context["original_obligations"] == context["unresolved_obligations"]
    assert context["validation_state"] == "unknown"
    assert context["rejected_event_id"] == stale["execution"]["event_id"]
    assert "I1" not in json.dumps(context) and "I2" not in json.dumps(context)

    recovery = writer.call("begin_recovery")
    assert recovery["ok"], recovery
    assert recovery["result"]["current_revision"] == concurrent_commit["result"]["revision"]
    action = writer.call("create_literal", type="i64", value="1")
    assert action["ok"], action
    assert action["execution"]["state"] == "recovery_action_succeeded"
    still_unknown = writer.call("inspect_recovery_context")
    assert still_unknown["result"]["validation_state"] == "unknown"
    assert still_unknown["result"]["unresolved_obligations"]
    writer.close()
    concurrent.close()

    observer = Agent(binary, event_log, "s06-observer")
    observed = observer.call("begin_transaction", project=manifest)
    observer.close()
    assert observed["result"]["project_revision"] == concurrent_commit["result"]["revision"]
    return stale, context_response, recovery, observed


def s06_and_observational_equivalence(binary: Path, fixture: Path, root: Path) -> None:
    event_log = root / "s06-events.jsonl"
    logged = run_s06(binary, fixture, root / "s06-on", event_log)
    unlogged = run_s06(binary, fixture, root / "s06-off", None)
    assert [without_execution(item) for item in logged] == [
        without_execution(item) for item in unlogged
    ]
    assert (root / "s06-on/src/x.alva").read_bytes() == (
        root / "s06-off/src/x.alva"
    ).read_bytes()
    events = load_events(event_log)
    recovery_action = next(
        event for event in events if event["event"] == "recovery_action_succeeded"
    )
    assert recovery_action["verification_status"] is None
    assert not any(event["event"] == "recovery_completed" for event in events)
    assert not any(event["event"] == "final_task_verified" for event in events)


def s07_signature_callsite(binary: Path, fixture: Path, root: Path) -> None:
    project = root / "s07"
    shutil.copytree(fixture, project)
    manifest = str(project / "alva.toml")
    source_path = project / "src/x.alva"
    original = source_path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in original else "\n"
    changed = original.replace(
        f"(param x (prim i64))){newline}    (returns",
        f"(param x (prim i64)) (param mode (prim string))){newline}    (returns",
        1,
    )
    changed = changed.replace(
        "(call has (vec (prim i64) (int 1) (int 2) (int 3)) (int 2))",
        '(call has (vec (prim i64) (int 1) (int 2) (int 3)) (int 2) (string "safe"))',
    ).replace(
        "(call has (vec (prim i64) (int 1)) (int 9))",
        '(call has (vec (prim i64) (int 1)) (int 9) (string "safe"))',
    ).replace(
        "(call has (vec (prim i64)) (int 1))",
        '(call has (vec (prim i64)) (int 1) (string "safe"))',
    )
    assert changed != original

    concurrent = Agent(binary, None, "s07-concurrent")
    writer = Agent(binary, None, "s07-writer")
    assert concurrent.call("begin_transaction", project=manifest)["ok"]
    assert writer.call("begin_transaction", project=manifest)["ok"]
    obligation = "update every contains_ok call site using the task-specified mode"
    assert writer.call(
        "register_recovery_intent",
        original_target="query.x.contains_ok",
        original_obligations=[obligation],
    )["ok"]
    writer_mutation = writer.call("create_literal", type="i64", value="7")
    assert writer_mutation["ok"], writer_mutation
    staged = concurrent.call(
        "stage_text_patch",
        path="src/x.alva",
        expected_sha256=hashlib.sha256(original.encode()).hexdigest(),
        old=original,
        new=changed,
        replace_all=False,
    )
    assert staged["ok"], staged
    concurrent_commit = concurrent.call("commit_transaction")
    assert concurrent_commit["ok"], concurrent_commit
    stale = writer.call("commit_transaction")
    assert not stale["ok"] and "E_AEP_CONFLICT" in stale["message"], stale
    context = writer.call("inspect_recovery_context")["result"]
    assert obligation in context["unresolved_obligations"]
    has_change = next(
        change
        for change in context["concurrent_change_summary"]["changed_targets"]
        if change["after"] and change["after"]["qualified"] == "query.x.has"
    )
    assert has_change["change"] == "signature_changed", has_change
    assert "param mode: (prim string)" in has_change["after"]["signature"], has_change
    assert "safe" not in has_change["after"]["signature"]
    assert context["validation_state"] == "unknown"
    assert "I1" not in json.dumps(context) and "I2" not in json.dumps(context)
    writer.close()
    concurrent.close()


def registration_must_precede_mutation(binary: Path, fixture: Path, root: Path) -> None:
    project = root / "late"
    shutil.copytree(fixture, project)
    agent = Agent(binary, None, "late-registration")
    assert agent.call("begin_transaction", project=str(project / "alva.toml"))["ok"]
    assert agent.call(
        "create_literal", type="string", value="unique-staged-before-registration"
    )["ok"]
    late = agent.call(
        "register_recovery_intent",
        original_target="query.x.has",
        original_obligations=["must already exist"],
    )
    assert not late["ok"]
    assert late["message"].startswith("E_AEP_RECOVERY_INTENT_LATE")
    agent.close()


def mcp_uses_the_same_recovery_runtime(binary: Path, fixture: Path, root: Path) -> None:
    project = root / "mcp"
    shutil.copytree(fixture, project)
    event_log = root / "mcp-recovery.jsonl"
    process = subprocess.Popen(
        [str(binary), "mcp", "--event-log", str(event_log)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdin and process.stdout and process.stderr

    def request(payload: dict) -> dict:
        assert process.stdin and process.stdout
        process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "recovery-test", "version": "1"},
            },
        }
    )
    begun = request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "begin_transaction",
                "arguments": {"project": str(project / "alva.toml")},
            },
        }
    )["result"]["structuredContent"]
    transaction_id = begun["transaction_id"]
    registered = request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "register_recovery_intent",
                "arguments": {
                    "transaction_id": transaction_id,
                    "original_target": "query.x.has",
                    "original_obligations": ["preserve public behavior"],
                },
            },
        }
    )["result"]["structuredContent"]
    assert registered["registered"]
    request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "abort_transaction",
                "arguments": {"transaction_id": transaction_id},
            },
        }
    )
    process.stdin.close()
    assert process.wait(timeout=10) == 0, process.stderr.read()
    recorded = load_events(event_log)
    assert recorded
    assert all(event["transaction_id"] == transaction_id for event in recorded)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    fixture = repo / "tests/codegen/query"
    with tempfile.TemporaryDirectory(prefix="alva-intent-recovery-") as temporary:
        root = Path(temporary)
        s06_and_observational_equivalence(args.binary, fixture, root)
        s07_signature_callsite(args.binary, fixture, root)
        registration_must_precede_mutation(args.binary, fixture, root)
        mcp_uses_the_same_recovery_runtime(args.binary, fixture, root)
    print("PASS: S06/S07 intent-preserving recovery with UNKNOWN verifier boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
