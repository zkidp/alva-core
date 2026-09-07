#!/usr/bin/env python3
"""Acceptance test for durable typed execution/recovery telemetry."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


class Agent:
    def __init__(self, binary: Path, event_log: Path, session: str, transaction: str):
        self.process = subprocess.Popen(
            [
                str(binary),
                "agent",
                "--event-log",
                str(event_log),
                "--session-id",
                session,
                "--transaction-id",
                transaction,
            ],
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


def events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="alva-typed-events-") as temp:
        root = Path(temp)
        project = root / "project"
        shutil.copytree(repo / "tests/codegen/query", project)
        event_log = root / "events.jsonl"
        first = Agent(args.binary, event_log, "session-first", "tx-first")
        premature = first.call("check_transaction")
        assert not premature["ok"]
        assert premature["execution"]["state"] == "operation_rejected"
        begun = first.call("begin_transaction", project=str(project / "alva.toml"))
        assert begun["ok"] and begun["execution"]["state"] == "transaction_started"
        staged = first.call("create_literal", type="i64", value="41")
        assert staged["ok"] and staged["execution"]["state"] == "mutation_staged"
        checked = first.call("check_transaction")
        assert checked["ok"] and checked["execution"]["state"] == "semantic_check_passed"
        committed = first.call("commit_transaction")
        assert committed["ok"] and committed["execution"]["state"] == "commit_succeeded"
        first.close()

        left = Agent(args.binary, event_log, "session-left", "tx-left")
        right = Agent(args.binary, event_log, "session-right", "tx-right")
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

        recorded = events(event_log)
        kinds = [event["event"] for event in recorded]
        for required in [
            "operation_requested",
            "transaction_started",
            "mutation_staged",
            "semantic_check_passed",
            "commit_attempted",
            "commit_succeeded",
            "operation_rejected",
            "stale_write_rejected",
        ]:
            assert required in kinds, required
        stale_event = next(event for event in reversed(recorded) if event["event"] == "stale_write_rejected")
        rejection = next(event for event in recorded if event["event_id"] == stale_event["parent_event_id"])
        semantic_check = next(event for event in recorded if event["event_id"] == rejection["parent_event_id"])
        attempted = next(event for event in recorded if event["event_id"] == semantic_check["parent_event_id"])
        requested = next(event for event in recorded if event["event_id"] == attempted["parent_event_id"])
        assert rejection["event"] == "operation_rejected"
        assert semantic_check["event"] == "semantic_check_passed"
        assert attempted["event"] == "commit_attempted"
        assert requested["event"] == "operation_requested"
        assert stale_event["transaction_id"] == "tx-right"
        assert stale_event["current_revision"] == left_commit["result"]["revision"]
        assert all(event["schema_version"] == "alva.execution-event.v1" for event in recorded)
        assert all("intent_preserved" not in event for event in recorded)

        mcp_log = root / "mcp-events.jsonl"
        mcp = subprocess.Popen(
            [str(args.binary), "mcp", "--event-log", str(mcp_log)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert mcp.stdin and mcp.stdout and mcp.stderr

        def request(payload: dict) -> dict:
            assert mcp.stdin and mcp.stdout
            mcp.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            mcp.stdin.flush()
            return json.loads(mcp.stdout.readline())

        request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "typed-events", "version": "1"}},
            }
        )
        begun_call = request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "begin_transaction", "arguments": {"project": str(project / "alva.toml")}},
            }
        )
        begun_result = begun_call["result"]["structuredContent"]
        transaction_id = begun_result["transaction_id"]
        assert begun_result["execution"]["state"] == "transaction_started"
        aborted_call = request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "abort_transaction", "arguments": {"transaction_id": transaction_id}},
            }
        )
        assert aborted_call["result"]["structuredContent"]["aborted"]
        assert aborted_call["result"]["structuredContent"]["execution"]["state"] == "transaction_aborted"
        mcp.stdin.close()
        assert mcp.wait(timeout=10) == 0, mcp.stderr.read()
        mcp_recorded = events(mcp_log)
        assert mcp_recorded
        assert all(event["transaction_id"] == transaction_id for event in mcp_recorded)
    print("PASS: typed execution events, stale causal chain, compact projection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
