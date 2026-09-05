#!/usr/bin/env python3
"""SS3 mechanical regressions for strict stale revisions and AIR atomicity."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


class Agent:
    def __init__(self, binary, env=None):
        self.process = subprocess.Popen(
            [binary, "agent"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    def call(self, tool, **arguments):
        self.process.stdin.write(json.dumps({"tool": tool, **arguments}) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"agent exited during {tool}")
        return json.loads(line)

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()


def initialize(binary, project, output):
    subprocess.run(
        [binary, "air", "export", str(project), "--out-dir", str(output), "--authoritative"],
        check=True,
        text=True,
        capture_output=True,
    )


def mutate(agent, project, value):
    begun = agent.call("begin_transaction", project=str(project))
    assert begun["ok"], begun
    inspected = agent.call("inspect_body", function="demo.app.run")
    match = re.search(r"literal value=a rev=([0-9a-f]{64})", inspected["result"]["body"])
    assert match, inspected
    changed = agent.call("change_field", entity=match.group(1), field="value", value=value)
    assert changed["ok"], changed
    return match.group(1)


def strict_stale(binary):
    with tempfile.TemporaryDirectory(prefix="alva-strict-stale-") as temporary:
        project_dir = Path(temporary) / "project"
        shutil.copytree(ROOT / "tests" / "project", project_dir)
        agent = Agent(binary)
        old_revision = mutate(agent, project_dir / "alva.toml", "first")
        before = agent.call("inspect_transaction_work")
        stale = agent.call("change_field", entity=old_revision, field="value", value="second")
        after = agent.call("inspect_transaction_work")
        assert stale["ok"] is False, stale
        assert stale["error_code"] == "E_AEP_STALE_REVISION", stale
        assert before["result"] == after["result"], (before, after)
        agent.call("abort_transaction")
        agent.close()


def crash_atomicity(binary):
    failpoints = (
        "after_generation_fsync",
        "after_generation_replace",
        "after_current_fsync",
        "after_current_replace",
    )
    for failpoint in failpoints:
        with tempfile.TemporaryDirectory(prefix=f"alva-air-crash-{failpoint}-") as temporary:
            project_dir = Path(temporary) / "project"
            shutil.copytree(ROOT / "tests" / "project", project_dir)
            manifest = project_dir / "alva.toml"
            initialize(binary, manifest, Path(temporary) / "initial-export")
            current_before = (project_dir / "alva-air" / "current").read_text()
            env = {**os.environ, "ALVA_TEST_AIR_FAILPOINT": failpoint}
            agent = Agent(binary, env)
            mutate(agent, manifest, f"crash-{failpoint}")
            assert agent.process.stdin
            agent.process.stdin.write(json.dumps({"tool": "commit_transaction"}) + "\n")
            agent.process.stdin.flush()
            agent.process.wait(timeout=10)
            assert agent.process.returncode == 86, (failpoint, agent.process.returncode)

            checked = subprocess.run(
                [binary, "project", "check", str(manifest), "--json"],
                text=True,
                capture_output=True,
            )
            assert checked.returncode == 0, (failpoint, checked.stdout, checked.stderr)
            current_after = (project_dir / "alva-air" / "current").read_text()
            if current_after != current_before:
                lines = current_after.splitlines()
                assert len(lines) >= 2 and lines[0].isdigit() and len(lines[1]) == 64
                assert (project_dir / "alva-air" / f"gen-{lines[0]}.air").is_file()


def main():
    binary = os.environ.get("ALVA")
    assert binary, "ALVA environment variable is required"
    strict_stale(binary)
    crash_atomicity(binary)
    print("PASS strict stale revision rejection and AIR crash atomicity")


if __name__ == "__main__":
    main()
