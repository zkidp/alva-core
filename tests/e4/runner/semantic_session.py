"""Adapter from the E4 transaction lifecycle to the frozen E3 AEP driver."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_e3_runner_core():
    path = Path(__file__).resolve().parents[2] / "e3" / "runner" / "runner_core.py"
    spec = importlib.util.spec_from_file_location("e3_runner_core_for_e4", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("E3 runner core is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SemanticSession:
    """One internal AEP transaction; lifecycle tools remain host-only."""

    def __init__(self, alva, project_toml, *, cmd_prefix_factory=None):
        self.alva = str(alva)
        self.project_toml = str(project_toml)
        self.cmd_prefix_factory = cmd_prefix_factory
        self._core = _load_e3_runner_core()
        self.agent = None
        self.call_log = []

    def start(self):
        if self.agent is not None:
            return {"ok": False, "error_code": "E_SESSION_ACTIVE",
                    "message": "semantic session is already active"}
        cmd_prefix = (self.cmd_prefix_factory()
                      if self.cmd_prefix_factory is not None else None)
        agent = self._core.RecordingAgent(
            self.alva, self.project_toml, gate_on=True,
            call_log=self.call_log, cmd_prefix=cmd_prefix)
        result = agent.call("begin_transaction", project=self.project_toml)
        if self.call_log:
            self.call_log[-1]["args"] = {"project": "alva.toml"}
        if not result.get("ok"):
            agent.close()
            return result
        self.agent = agent
        return {"ok": True, "result": {"semantic_session": "active"}}

    def call(self, tool, arguments):
        if self.agent is None:
            return {"ok": False, "error_code": "E_NO_SEMANTIC_SESSION",
                    "message": "semantic session is not active"}
        return self.agent.call(tool, **arguments)

    def close(self, *, abort):
        if self.agent is None:
            return
        agent, self.agent = self.agent, None
        try:
            if abort:
                agent.call("abort_transaction")
        finally:
            agent.close()
