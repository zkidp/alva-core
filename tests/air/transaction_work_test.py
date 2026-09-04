#!/usr/bin/env python3
"""Model-free baseline for graph rebuild/reuse and semantic-check scope."""

import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "tests" / "project" / "alva.toml"


class Agent:
    def __init__(self, binary: str):
        self.proc = subprocess.Popen(
            [binary, "agent"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={**os.environ, "ALVA_VERIFY_DIRTY_TRACKING": "1"},
        )

    def call(self, tool: str, **arguments):
        self.proc.stdin.write(json.dumps({"tool": tool, **arguments}) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        assert line, f"agent exited while executing {tool}"
        return json.loads(line)

    def close(self):
        self.proc.kill()


def main():
    binary = os.environ.get("ALVA")
    assert binary, "ALVA environment variable is required"
    agent = Agent(binary)
    assert agent.call("begin_transaction", project=str(PROJECT))["ok"]

    initial = agent.call("inspect_transaction_work")
    assert initial["ok"], initial
    initial = initial["result"]
    assert initial["reachable_nodes"] == initial["reused_reachable_nodes"]
    assert initial["changed_module_count"] == 0
    assert initial["last_revision_rebuild"]["node_visits"] == 0
    assert initial["full_check_runs"] == 0
    assert initial["graph_construction_scope"] == "none_since_begin"

    body = agent.call("inspect_body", function="demo.app.run")
    literal = re.search(
        r"literal value=a rev=([0-9a-f]{64})", body["result"]["body"]
    )
    assert literal, body
    changed = agent.call(
        "change_field",
        entity=literal.group(1),
        field="value",
        value="work-baseline",
    )
    assert changed["ok"], changed

    measured = agent.call("inspect_transaction_work")
    assert measured["ok"], measured
    measured = measured["result"]
    rebuild = measured["last_revision_rebuild"]
    assert measured["changed_modules"] == ["module:demo.app"]
    assert measured["changed_module_count"] == 1
    assert measured["added_reachable_nodes"] > 0
    assert measured["removed_reachable_nodes"] > 0
    assert measured["reused_reachable_nodes"] > 0
    assert rebuild["candidate_root_modules"] == 2
    assert rebuild["root_modules"] == 1
    assert rebuild["dirty_seed_count"] == 1
    assert rebuild["dirty_detection_node_scans"] == 0
    assert rebuild["affected_root_selection_visits"] > 0
    assert rebuild["node_visits"] >= rebuild["unique_nodes_visited"]
    assert rebuild["unique_nodes_visited"] < measured["reachable_nodes"]
    assert rebuild["rewritten_nodes"] == measured["added_reachable_nodes"]
    assert measured["graph_construction_scope"] == "affected_module_roots_revision_rebuild"
    assert measured["semantic_check_scope"] == "full_project_when_check_runs"
    assert measured["full_check_runs"] == 0

    checked = agent.call("check_transaction")
    assert checked["ok"], checked
    after_check = agent.call("inspect_transaction_work")["result"]
    assert after_check["full_check_runs"] == 1
    assert after_check["last_revision_rebuild"] == rebuild

    assert agent.call("abort_transaction")["ok"]
    agent.close()
    print("PASS transaction rebuild, revision reuse, and full-check baseline")


if __name__ == "__main__":
    main()
