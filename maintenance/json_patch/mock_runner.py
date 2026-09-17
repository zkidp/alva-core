#!/usr/bin/env python3
"""Zero-provider rehearsal of maintenance-result disposition and accounting."""

from __future__ import annotations

import json


CASES = [
    {"id": "complete", "result": {"task": True, "regression": True}, "cost": {"attempts": 1}},
    {"id": "task_failure", "result": {"task": False, "regression": True}, "cost": {"attempts": 1}},
    {"id": "budget_exhausted", "stop": "budget", "cost": {"attempts": 1}},
    {"id": "expected_tool_error", "stop": "tool_error", "ordinary": True, "cost": {"attempts": 1}},
    {"id": "provider_failure", "stop": "infrastructure", "cost": {"attempts": 1}},
    {"id": "missing_result", "cost": {"attempts": 1}},
]


def disposition(case: dict[str, object]) -> str:
    if "result" in case:
        result = case["result"]
        assert isinstance(result, dict)
        return "PASS" if result.get("task") and result.get("regression") else "TASK_FAIL"
    if case.get("stop") == "budget":
        return "BUDGET_EXHAUSTED"
    if case.get("stop") == "tool_error" and case.get("ordinary") is True:
        return "EXPECTED_TOOL_ERROR"
    if case.get("stop") == "infrastructure":
        return "INFRASTRUCTURE_FAILURE"
    return "MISSING_RESULT"


def main() -> int:
    rows = [{**case, "disposition": disposition(case)} for case in CASES]
    assert sum(int(row["cost"]["attempts"]) for row in rows) == 6
    assert {row["disposition"] for row in rows} == {
        "PASS",
        "TASK_FAIL",
        "BUDGET_EXHAUSTED",
        "EXPECTED_TOOL_ERROR",
        "INFRASTRUCTURE_FAILURE",
        "MISSING_RESULT",
    }
    print(json.dumps({"status": "PASS", "provider_calls": 0, "rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
