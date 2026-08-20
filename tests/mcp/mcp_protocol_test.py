#!/usr/bin/env python3
"""Wire and authority acceptance fixtures for `alva mcp`."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {"name": "alva-fixture", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


class Mcp:
    def __init__(self, binary: Path):
        self.process = subprocess.Popen(
            [str(binary), "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert self.process.stdin and self.process.stdout and self.process.stderr

    def request(self, request: dict) -> dict:
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        assert line, self.process.stderr.read()
        return json.loads(line)

    def tool(self, request_id: int, name: str, arguments: dict, modern: bool = False) -> dict:
        params = {"name": name, "arguments": arguments}
        if modern:
            params["_meta"] = MODERN_META
        response = self.request(
            {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": params}
        )
        return response["result"]

    def close(self) -> tuple[str, str]:
        assert self.process.stdin and self.process.stdout and self.process.stderr
        self.process.stdin.close()
        stdout = self.process.stdout.read()
        stderr = self.process.stderr.read()
        code = self.process.wait(timeout=10)
        assert code == 0, stderr
        return stdout, stderr


def structured(call_result: dict) -> dict:
    text = call_result["content"][0]["text"]
    assert json.loads(text) == call_result["structuredContent"]
    return call_result["structuredContent"]


def legacy_fixture(binary: Path) -> None:
    mcp = Mcp(binary)
    initialized = mcp.request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "legacy-fixture", "version": "1"},
            },
        }
    )
    assert initialized["result"]["protocolVersion"] == "2025-11-25"
    first = mcp.request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    second = mcp.request({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
    assert first["result"] == second["result"]
    names = [tool["name"] for tool in first["result"]["tools"]]
    assert names == list(dict.fromkeys(names))
    assert "inspect_change_impact" not in names and "inspect_schema_gaps" not in names
    assert "change_field" in names
    assert "resultType" not in first["result"]
    mcp.close()


def modern_fixture(binary: Path) -> None:
    mcp = Mcp(binary)
    discover = mcp.request(
        {
            "jsonrpc": "2.0",
            "id": "discover",
            "method": "server/discover",
            "params": {"_meta": MODERN_META},
        }
    )["result"]
    assert discover["supportedVersions"] == ["2026-07-28"]
    assert discover["resultType"] == "complete"
    assert discover["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "alva"
    listed = mcp.request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {"_meta": MODERN_META},
        }
    )["result"]
    assert listed["resultType"] == "complete"
    assert listed["ttlMs"] == 0 and listed["cacheScope"] == "private"
    mcp.close()


def errors_fixture(binary: Path) -> None:
    mcp = Mcp(binary)
    assert mcp.process.stdin and mcp.process.stdout
    mcp.process.stdin.write("{not json}\n")
    mcp.process.stdin.flush()
    assert json.loads(mcp.process.stdout.readline())["error"]["code"] == -32700
    unknown = mcp.request({"jsonrpc": "2.0", "id": 4, "method": "alva/nope", "params": {}})
    assert unknown["error"]["code"] == -32601
    missing_name = mcp.request({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {}})
    assert missing_name["error"]["code"] == -32602
    unknown_tool = mcp.tool(6, "not_a_tool", {})
    assert unknown_tool["isError"] is True
    structured(unknown_tool)
    unsupported = mcp.request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/list",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2099-01-01",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
    )
    assert unsupported["error"]["code"] == -32022
    mcp.close()


def semantic_fixture(binary: Path, repo: Path, commit: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="alva-mcp-") as temp:
        project = Path(temp) / "project"
        shutil.copytree(repo / "tests" / "project", project)
        source = project / "src" / "app.alva"
        source_before = source.read_bytes()

        mcp = Mcp(binary)
        begun = structured(mcp.tool(10, "begin_transaction", {"project": str(project / "alva.toml")}))
        transaction = begun["transaction_id"]
        body = structured(
            mcp.tool(11, "inspect_body", {"transaction_id": transaction, "function": "demo.app.run"})
        )["body"]
        literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
        assert literal, body
        changed = mcp.tool(
            12,
            "change_field",
            {
                "transaction_id": transaction,
                "entity": literal.group(1),
                "field": "value",
                "value": "hello from MCP",
            },
        )
        assert changed["isError"] is False, changed
        changed_result = structured(changed)
        assert changed_result["new_revision"] != literal.group(1), changed_result

        if not commit:
            mcp.close()
            assert source.read_bytes() == source_before
            assert not (project / "alva-air").exists()
            return

        diff = structured(mcp.tool(13, "preview_semantic_diff", {"transaction_id": transaction}))
        assert diff["diff"].strip(), diff
        checked = mcp.tool(14, "check_transaction", {"transaction_id": transaction})
        assert checked["isError"] is False, checked
        committed = mcp.tool(15, "commit_transaction", {"transaction_id": transaction})
        assert committed["isError"] is False, committed
        mcp.close()
        assert source.read_bytes() == source_before
        assert (project / "alva-air" / "current").exists()
        subprocess.run([str(binary), "project", "check", str(project / "alva.toml"), "--json"], check=True)
        subprocess.run([str(binary), "project", "build", str(project / "alva.toml")], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    repo = Path(__file__).resolve().parents[2]
    legacy_fixture(binary)
    modern_fixture(binary)
    errors_fixture(binary)
    semantic_fixture(binary, repo, commit=False)
    semantic_fixture(binary, repo, commit=True)
    print("PASS: MCP legacy, modern, errors, authority safety, and semantic commit")


if __name__ == "__main__":
    main()
