#!/usr/bin/env python3
"""Projection reconciliation regression.

Proves that a text-input commit leaves source untouched, canonical AIR output
round-trips before it is offered, stale CAS values cannot write, and an
explicit projection write converges source to the authoritative AIR revision.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


class Agent:
    def __init__(self, binary: str):
        self.proc = subprocess.Popen(
            [binary, "agent"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def call(self, tool: str, **arguments):
        self.proc.stdin.write(json.dumps({"tool": tool, **arguments}) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        assert line, f"agent exited while executing {tool}"
        return json.loads(line)

    def close(self):
        self.proc.kill()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    binary = os.environ.get("ALVA")
    assert binary, "ALVA environment variable is required"
    with tempfile.TemporaryDirectory(prefix="alva-projection-") as temp:
        project = Path(temp) / "project"
        shutil.copytree(ROOT / "tests" / "project", project)
        source = project / "src" / "app.alva"
        original = source.read_bytes()

        agent = Agent(binary)
        begun = agent.call("begin_transaction", project=str(project / "alva.toml"))
        assert begun["ok"], begun
        staged = agent.call(
            "stage_text_patch",
            path="src/app.alva",
            expected_sha256=sha256(original),
            old='(string "a")',
            new='(string "projected-from-air")',
        )
        assert staged["ok"], staged
        committed = agent.call("commit_transaction")
        assert committed["ok"], committed
        assert source.read_bytes() == original

        begun = agent.call("begin_transaction", project=str(project / "alva.toml"))
        assert begun["ok"], begun
        preview = agent.call("preview_source_projection", path="src/app.alva")
        assert preview["ok"], preview
        data = preview["result"]
        assert data["revision"] == committed["result"]["revision"]
        assert data["changed"] is True
        assert "projected-from-air" in data["projection_preview"]
        assert source.read_bytes() == original

        body = agent.call("inspect_body", function="demo.app.run")
        literal = re.search(
            r"literal value=projected-from-air rev=([0-9a-f]{64})",
            body["result"]["body"],
        )
        assert literal, body
        changed = agent.call(
            "change_field",
            entity=literal.group(1),
            field="value",
            value="not-yet-committed",
        )
        assert changed["ok"], changed
        uncommitted_preview = agent.call(
            "preview_source_projection", path="src/app.alva"
        )
        assert uncommitted_preview["ok"], uncommitted_preview
        uncommitted = agent.call(
            "materialize_source_projection",
            path="src/app.alva",
            expected_source_sha256=uncommitted_preview["result"]["source_sha256"],
            expected_projection_sha256=uncommitted_preview["result"][
                "projection_sha256"
            ],
            expected_revision=uncommitted_preview["result"]["revision"],
        )
        assert not uncommitted["ok"]
        assert uncommitted["error_code"] == "E_AEP_PROJECTION_UNCOMMITTED"
        assert source.read_bytes() == original
        assert agent.call("abort_transaction")["ok"]
        begun = agent.call("begin_transaction", project=str(project / "alva.toml"))
        assert begun["ok"], begun
        preview = agent.call("preview_source_projection", path="src/app.alva")
        assert preview["ok"], preview
        data = preview["result"]

        traversal = agent.call("preview_source_projection", path="../src/app.alva")
        assert not traversal["ok"]
        assert traversal["error_code"] == "E_AEP_PROJECTION_PATH"

        stale = agent.call(
            "materialize_source_projection",
            path="src/app.alva",
            expected_source_sha256="0" * 64,
            expected_projection_sha256=data["projection_sha256"],
            expected_revision=data["revision"],
        )
        assert not stale["ok"]
        assert stale["error_code"] == "E_AEP_PROJECTION_STALE_SOURCE"
        assert source.read_bytes() == original

        materialized = agent.call(
            "materialize_source_projection",
            path="src/app.alva",
            expected_source_sha256=data["source_sha256"],
            expected_projection_sha256=data["projection_sha256"],
            expected_revision=data["revision"],
        )
        assert materialized["ok"], materialized
        result = materialized["result"]
        assert result["changed"] is True
        assert result["all_sources_converged"] is True
        assert result["atomic_with_air_commit"] is False
        assert sha256(source.read_bytes()) == data["projection_sha256"]
        assert b"projected-from-air" in source.read_bytes()
        agent.call("abort_transaction")
        agent.close()

        checked = subprocess.run(
            [binary, "project", "check", str(project / "alva.toml"), "--json"],
            text=True,
            capture_output=True,
        )
        assert checked.returncode == 0, checked.stderr

    print("PASS source projection preview, CAS materialization, and convergence")


if __name__ == "__main__":
    main()
