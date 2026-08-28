"""E4 relay loop shared by scripted rehearsal and frozen Luna execution."""

from __future__ import annotations

import json
from pathlib import Path


TERMINATIONS = frozenset({
    "MODEL_FINAL", "MAX_TOOL_STEPS", "RELAY_FAILURE", "RUNTIME_FAILURE"
})


class ScriptedRelay:
    def __init__(self, steps):
        self.steps = list(steps)
        self.index = 0
        self.pending = None

    @classmethod
    def from_file(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def _next(self):
        if self.index >= len(self.steps):
            return {"type": "final", "text": "script exhausted"}
        item = self.steps[self.index]
        self.index += 1
        if "tool" in item:
            self.pending = f"script-call-{self.index}"
            return {"type": "tool", "tool": item["tool"],
                    "args": item.get("args", {}),
                    "tool_call_id": self.pending}
        self.pending = None
        return {"type": "final", "text": item.get("final", "")}

    def start(self, task_statement, instructions):
        return self._next()

    def submit_tool_result(self, call_id, result):
        if call_id != self.pending:
            raise RuntimeError("scripted call_id mismatch")
        return self._next()


def drive(runtime, relay, task_statement, instructions, *, max_tool_steps):
    """Run exactly one serial function-call loop; never auto-commit."""
    trajectory = []
    try:
        step = relay.start(task_statement, instructions)
        for ordinal in range(1, max_tool_steps + 1):
            if step["type"] == "final":
                return {"termination": "MODEL_FINAL", "final": step.get("text", ""),
                        "trajectory": trajectory}
            result = runtime.call(step["tool"], **step.get("args", {}))
            trajectory.append({"ordinal": ordinal, "tool": step["tool"],
                               "args": step.get("args", {}), "result": result,
                               "tool_call_id": step["tool_call_id"]})
            step = relay.submit_tool_result(step["tool_call_id"], result)
        if step["type"] == "final":
            return {"termination": "MODEL_FINAL", "final": step.get("text", ""),
                    "trajectory": trajectory}
        return {"termination": "MAX_TOOL_STEPS", "final": None,
                "trajectory": trajectory}
    except Exception as exc:
        return {"termination": "RUNTIME_FAILURE", "final": None,
                "trajectory": trajectory,
                "failure": f"{type(exc).__name__}: {exc}"}

