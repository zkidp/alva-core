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
            env={
                **os.environ,
                "ALVA_VERIFY_DIRTY_TRACKING": "1",
                "ALVA_VERIFY_INCREMENTAL_CHECK": "1",
            },
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
    baseline_check = agent.call("check_transaction")
    assert baseline_check["ok"], baseline_check
    validated = agent.call("inspect_transaction_work")["result"]
    assert validated["full_check_runs"] == 1
    assert validated["affected_check_runs"] == 0
    assert validated["last_semantic_total_modules"] == 2
    assert validated["last_semantic_checked_modules"] == 2
    assert validated["semantic_check_scope"] == "full_project"

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
    assert measured["semantic_check_scope"] == "full_project"
    assert measured["full_check_runs"] == 1
    assert measured["affected_check_runs"] == 0

    checked = agent.call("check_transaction")
    assert checked["ok"], checked
    after_check = agent.call("inspect_transaction_work")["result"]
    assert after_check["full_check_runs"] == 1
    assert after_check["affected_check_runs"] == 1
    assert after_check["last_semantic_total_modules"] == 2
    assert after_check["last_semantic_checked_modules"] == 1
    assert (
        after_check["semantic_check_scope"]
        == "changed_modules_plus_transitive_dependents"
    )
    assert after_check["last_revision_rebuild"] == rebuild

    assert agent.call("abort_transaction")["ok"]

    # A dependency-module change must check both itself and its transitive
    # dependent (`demo.app`), not just the module whose head changed.
    assert agent.call("begin_transaction", project=str(PROJECT))["ok"]
    assert agent.call("check_transaction")["ok"]
    model_changed = agent.call(
        "change_field",
        entity="module:demo.model",
        field="version",
        value="0.1.1",
    )
    assert model_changed["ok"], model_changed
    model_check = agent.call("check_transaction")
    assert model_check["ok"], model_check
    dependent_work = agent.call("inspect_transaction_work")["result"]
    assert dependent_work["changed_modules"] == ["module:demo.model"]
    assert dependent_work["affected_check_runs"] == 1
    assert dependent_work["last_semantic_total_modules"] == 2
    assert dependent_work["last_semantic_checked_modules"] == 2
    assert agent.call("abort_transaction")["ok"]

    # The affected checker must also match the full checker on a failing edit,
    # including the rendered diagnostic rather than merely PASS/FAIL status.
    assert agent.call("begin_transaction", project=str(PROJECT))["ok"]
    assert agent.call("check_transaction")["ok"]
    broken_body = agent.call("inspect_body", function="demo.app.run")
    call = re.search(
        r"call name=demo\.model\.size_of rev=([0-9a-f]{64})",
        broken_body["result"]["body"],
    )
    assert call, broken_body
    broken = agent.call(
        "change_field",
        entity=call.group(1),
        field="name",
        value="demo.model.does_not_exist",
    )
    assert broken["ok"], broken
    failed_check = agent.call("check_transaction")
    assert not failed_check["ok"]
    assert "E_CALL_002" in failed_check["message"], failed_check
    assert "E_AIR_INCREMENTAL_CHECK_MISMATCH" not in failed_check["message"]
    assert agent.call("abort_transaction")["ok"]
    agent.close()
    print("PASS transaction rebuild, revision reuse, and full-check baseline")


if __name__ == "__main__":
    main()
