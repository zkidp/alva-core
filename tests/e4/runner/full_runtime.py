"""FULL_ALVA adapter preserving the frozen E3 42-tool surface."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_e3_core():
    path = Path(__file__).resolve().parents[2] / "e3" / "runner" / "runner_core.py"
    spec = importlib.util.spec_from_file_location("e3_runner_core_for_e4_full", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("E3 runner core is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FullAlvaRuntime:
    def __init__(self, alva, workspace, *, cmd_prefix=None, agent_factory=None):
        self.workspace = Path(workspace).resolve(strict=True)
        self.project = self.workspace / "alva.toml"
        schema_path = Path(__file__).parent / "tool-schemas" / "TOOLS-FULL_ALVA.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.allowed = frozenset(item["function"]["name"] for item in schema["tools"])
        core = _load_e3_core()
        factory = agent_factory or core.RecordingAgent
        self.call_log = []
        self.agent = factory(str(alva), str(self.project), gate_on=True,
                             call_log=self.call_log, cmd_prefix=cmd_prefix)
        self.closed = False
        self.committed = False

    def call(self, tool, **arguments):
        if self.closed:
            return {"ok": False, "error_code": "E_RUNTIME_CLOSED",
                    "message": "runtime is closed"}
        if tool not in self.allowed:
            return {"ok": False, "error_code": "E_UNKNOWN_TOOL",
                    "message": "tool is not available"}
        safe = dict(arguments)
        if tool == "begin_transaction":
            supplied = safe.get("project")
            if supplied not in {"alva.toml", "./alva.toml"}:
                return {"ok": False, "error_code": "E_INVALID_PROJECT",
                        "message": "project must be alva.toml"}
            safe["project"] = str(self.project)
        result = self.agent.call(tool, **safe)
        if tool == "begin_transaction" and self.call_log:
            self.call_log[-1]["args"] = {"project": "alva.toml"}
        if tool == "commit_transaction" and result.get("ok"):
            self.committed = True
        return result

    def prepare_final_verifier(self):
        if not self.committed:
            return {"ok": False, "error_code": "E_NO_COMMIT",
                    "message": "no committed semantic transaction"}
        return {"ok": True, "result": {"ready": True}}

    def close(self):
        if not self.closed:
            self.agent.close()
            self.closed = True
