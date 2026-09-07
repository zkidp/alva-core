#!/usr/bin/env python3
"""Acceptance checks for observational typed execution telemetry."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


class Agent:
    def __init__(
        self,
        binary: Path,
        event_log: Path | None,
        session: str,
        transaction: str,
    ):
        command = [
            str(binary),
            "agent",
            "--session-id",
            session,
            "--transaction-id",
            transaction,
        ]
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
        payload = {"request_id": tool, "tool": tool, **arguments}
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
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


def load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


def without_execution(response: dict) -> dict:
    comparable = dict(response)
    comparable.pop("execution", None)
    return comparable


def observational_equivalence(binary: Path, fixture: Path, root: Path) -> None:
    off_project = root / "off"
    on_project = root / "on"
    shutil.copytree(fixture, off_project)
    shutil.copytree(fixture, on_project)
    log = root / "equivalence.jsonl"
    off = Agent(binary, None, "same-session", "same-transaction")
    on = Agent(binary, log, "same-session", "same-transaction")
    off_responses = [
        off.call("begin_transaction", project=str(off_project / "alva.toml")),
        off.call("check_transaction"),
        off.call("preview_source_projection", path="src/x.alva"),
        off.call("commit_transaction"),
    ]
    on_responses = [
        on.call("begin_transaction", project=str(on_project / "alva.toml")),
        on.call("check_transaction"),
        on.call("preview_source_projection", path="src/x.alva"),
        on.call("commit_transaction"),
    ]
    off.close()
    on.close()
    assert [without_execution(item) for item in off_responses] == [
        without_execution(item) for item in on_responses
    ]
    assert off_responses[-1]["result"]["revision"] == on_responses[-1]["result"]["revision"]
    assert (off_project / "src/x.alva").read_bytes() == (on_project / "src/x.alva").read_bytes()
    assert log.exists() and load_events(log)


def stale_chain(binary: Path, fixture: Path, root: Path) -> None:
    project = root / "stale"
    shutil.copytree(fixture, project)
    event_log = root / "stale.jsonl"
    left = Agent(binary, event_log, "session-left", "tx-left")
    right = Agent(binary, event_log, "session-right", "tx-right")
    assert left.call("begin_transaction", project=str(project / "alva.toml"))["ok"]
    assert right.call("begin_transaction", project=str(project / "alva.toml"))["ok"]
    assert left.call("rename_entity", entity="query.x.has", new_name="has_left")["ok"]
    assert right.call("rename_entity", entity="query.x.has", new_name="has_right")["ok"]
    left_commit = left.call("commit_transaction")
    assert left_commit["ok"]
    stale = right.call("commit_transaction")
    assert not stale["ok"]
    assert stale["execution"]["state"] == "stale_write_rejected"
    left.close()
    right.close()

    recorded = load_events(event_log)
    stale_event = next(event for event in reversed(recorded) if event["event"] == "stale_write_rejected")
    rejection = next(event for event in recorded if event["event_id"] == stale_event["parent_event_id"])
    semantic = next(event for event in recorded if event["event_id"] == rejection["parent_event_id"])
    attempted = next(event for event in recorded if event["event_id"] == semantic["parent_event_id"])
    requested = next(event for event in recorded if event["event_id"] == attempted["parent_event_id"])
    assert [
        requested["event"],
        attempted["event"],
        semantic["event"],
        rejection["event"],
        stale_event["event"],
    ] == [
        "operation_requested",
        "commit_attempted",
        "semantic_check_passed",
        "operation_rejected",
        "stale_write_rejected",
    ]
    assert stale_event["transaction_id"] == "tx-right"
    assert stale_event["current_revision"] == left_commit["result"]["revision"]
    assert all(event["schema_version"] == "alva.execution-event.v1" for event in recorded)
    assert all("intent_preserved" not in event for event in recorded)


def mcp_shared_source(binary: Path, fixture: Path, root: Path) -> None:
    project = root / "mcp"
    shutil.copytree(fixture, project)
    event_log = root / "mcp.jsonl"
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
                "clientInfo": {"name": "typed-events", "version": "1"},
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
    assert begun["execution"]["state"] == "transaction_started"
    aborted = request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "abort_transaction",
                "arguments": {"transaction_id": transaction_id},
            },
        }
    )["result"]["structuredContent"]
    assert aborted["aborted"]
    assert aborted["execution"]["state"] == "transaction_aborted"
    process.stdin.close()
    assert process.wait(timeout=10) == 0, process.stderr.read()
    recorded = load_events(event_log)
    assert recorded
    assert all(event["transaction_id"] == transaction_id for event in recorded)
    assert begun["execution"]["event_id"] in {event["event_id"] for event in recorded}
    assert aborted["execution"]["event_id"] in {event["event_id"] for event in recorded}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    fixture = repo / "tests/codegen/query"
    with tempfile.TemporaryDirectory(prefix="alva-typed-events-") as temporary:
        root = Path(temporary)
        observational_equivalence(args.binary, fixture, root)
        stale_chain(args.binary, fixture, root)
        mcp_shared_source(args.binary, fixture, root)
    print("PASS: observational typed events, stale causal chain, shared MCP source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
