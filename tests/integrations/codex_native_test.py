#!/usr/bin/env python3
"""Install the existing plugin in isolation and call it through Codex app-server.

No turn/start or provider generation is used. This is a host/tool integration
fixture, not a test of a model's ability to select the right tools.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class AppServer:
    def __init__(self, codex: str, env: dict[str, str], cwd: Path, extra_args: list[str] | None = None):
        self.process = subprocess.Popen(
            [codex, "app-server", "--stdio", *(extra_args or [])], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        self.messages: queue.Queue = queue.Queue()
        self.errors: list[str] = []
        self.ordinal = 0
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()

    def _read(self) -> None:
        assert self.process.stdout
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                self.messages.put({"invalid_json": line})
        self.messages.put(None)

    def _stderr(self) -> None:
        assert self.process.stderr
        for line in self.process.stderr:
            self.errors.append(line.rstrip())
            self.errors[:] = self.errors[-100:]

    def send(self, message: dict) -> None:
        assert self.process.stdin
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict, timeout: float = 60) -> dict:
        self.ordinal += 1
        request_id = self.ordinal
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            try:
                message = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise AssertionError(f"Codex timed out on {method}: {self.errors[-8:]}") from exc
            assert message is not None, (method, self.errors[-8:])
            assert "invalid_json" not in message, message
            if message.get("id") == request_id:
                assert "error" not in message, (method, message)
                return message["result"]
            # No approvals, elicitation, or model-side requests are expected.
            assert "id" not in message, ("unexpected host request", message)

    def close(self) -> None:
        assert self.process.stdin
        self.process.stdin.close()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=10)


def run(command: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                            text=True, encoding="utf-8", timeout=180)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--codex", default=shutil.which("codex"))
    args = parser.parse_args()
    assert args.codex, "Codex CLI required; install it before running this optional host fixture"
    binary = args.binary.resolve()
    assert binary.is_file(), binary
    with tempfile.TemporaryDirectory(prefix="alva-codex-native-") as temp:
        scratch = Path(temp)
        project = scratch / "project"
        shutil.copytree(ROOT / "tests" / "project", project)
        original = {p.relative_to(project): p.read_bytes() for p in project.rglob("*.alva")}
        env = dict(os.environ)
        env["CODEX_HOME"] = str(scratch / "codex-home")
        Path(env["CODEX_HOME"]).mkdir()
        env["PATH"] = str(binary.parent) + os.pathsep + env.get("PATH", "")
        # Do not inherit another host's project-root hint into this test project.
        env.pop("CLAUDE_PROJECT_DIR", None)
        version = run([args.codex, "--version"], env, project).stdout.strip()
        run([str(binary), "doctor"], env, project)
        run([args.codex, "plugin", "marketplace", "add",
             str(ROOT / "integrations" / "codex"), "--json"], env, project)
        installed = json.loads(run([args.codex, "plugin", "add", "alva@alva", "--json"], env, project).stdout)
        assert installed["pluginId"] == "alva@alva", installed
        installed_skill = Path(installed["installedPath"]) / "skills" / "alva"
        canonical_skill = ROOT / "integrations" / "skills" / "alva"
        for source in canonical_skill.rglob("*"):
            if source.is_file():
                assert (installed_skill / source.relative_to(canonical_skill)).read_bytes() == source.read_bytes()

        host = AppServer(args.codex, env, project)
        trace: list[str] = []
        try:
            host.request("initialize", {"clientInfo": {"name": "alva-native-fixture", "version": "1"},
                                        "capabilities": {"experimentalApi": True}})
            host.send({"method": "initialized", "params": {}})
            skills = host.request("skills/list", {"cwds": [str(project)], "forceReload": True})
            assert any(skill.get("pluginId") == "alva@alva" and skill["enabled"]
                       for row in skills["data"] for skill in row["skills"]), skills
            started = host.request("thread/start", {"cwd": str(project), "approvalPolicy": "never",
                                                    "sandbox": "workspace-write", "ephemeral": True})
            thread_id = started["thread"]["id"]
            inventory = host.request("mcpServerStatus/list", {"threadId": thread_id})
            servers = inventory["data"]
            server = next(row for row in servers if row.get("pluginId") == "alva@alva")
            assert server.get("toolsError") is None, server
            tools = server["tools"]
            names = set(tools) if isinstance(tools, dict) else {tool["name"] for tool in tools}
            assert {"begin_transaction", "resolve_entity", "change_field", "commit_transaction"} <= names

            def call(tool: str, arguments: dict) -> dict:
                response = host.request("mcpServer/tool/call", {"threadId": thread_id,
                    "server": server["name"], "tool": tool, "arguments": arguments})
                assert not response.get("isError"), (tool, response)
                content = response["structuredContent"]
                assert isinstance(content, dict), (tool, content)
                trace.append(tool)
                return content

            begun = call("begin_transaction", {"project": str(project / "alva.toml")})
            tx = begun["transaction_id"]

            def tool(operation: str, **arguments) -> dict:
                return call(operation, {"transaction_id": tx, **arguments})

            resolved = tool("resolve_entity", name="demo.app.run", kind="function")["entity"]
            tool("applicable_operations", entity=resolved)
            tool("describe_operation", name="change_field")
            body = tool("inspect_body", function="demo.app.run")["body"]
            literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
            assert literal, body
            tool("inspect_entity", entity=literal.group(1))
            tool("change_field", entity=literal.group(1), field="value", value="hello from installed Codex plugin")
            assert not (project / "alva-air" / "current").exists(), "staged edit published before commit"
            assert tool("preview_semantic_diff")["diff"].strip()
            tool("check_transaction")
            tool("commit_transaction")
            assert (project / "alva-air" / "current").is_file()
            # Prove the committed authority is readable from a new transaction.
            tx = call("begin_transaction", {"project": str(project / "alva.toml")})["transaction_id"]
            body = tool("inspect_body", function="demo.app.run")["body"]
            assert "hello from installed Codex plugin" in body
            committed_current = (project / "alva-air" / "current").read_bytes()
            committed_literal = re.search(r"literal value=hello from installed Codex plugin rev=([0-9a-f]{64})", body)
            assert committed_literal, body
            tool("change_field", entity=committed_literal.group(1), field="value", value="must be aborted")
            tool("abort_transaction")
            assert (project / "alva-air" / "current").read_bytes() == committed_current
        finally:
            host.close()
        for path, before in original.items():
            assert (project / path).read_bytes() == before
        run([str(binary), "project", "check", str(project / "alva.toml"), "--json"], env, project)
        run([str(binary), "project", "build", str(project / "alva.toml"),
             "--out-dir", str(scratch / "build")], env, project)
        run(["cargo", "test", "--manifest-path", str(scratch / "build" / "demo" / "Cargo.toml")], env, project)
        print(json.dumps({"status": "PASS", "codex": version, "plugin": installed["pluginId"],
                          "discovered_tools": sorted(names), "calls": trace,
                          "authority": "AIR commit persisted; source projection unchanged",
                          "provider_generation_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
