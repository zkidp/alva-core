#!/usr/bin/env python3
"""Wire and authority acceptance fixtures for `alva mcp`."""

from __future__ import annotations

import argparse
import hashlib
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


def modern_structured(call_result: dict) -> dict:
    text = call_result["content"][0]["text"]
    assert text.endswith("see structuredContent."), text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    assert parsed != call_result["structuredContent"]
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
    mixed = mcp.request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/list",
            "params": {"_meta": MODERN_META},
        }
    )
    assert mixed["error"]["code"] == -32602, mixed
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
    assert listed["ttlMs"] == 3_600_000 and listed["cacheScope"] == "private"
    assert listed["schemaProfile"] == "compact-v1"
    assert re.fullmatch(r"[0-9a-f]{64}", listed["toolSurfaceHash"])
    assert len(json.dumps(listed, separators=(",", ":"))) < 7000
    unknown_tool = mcp.tool(3, "not_a_tool", {}, modern=True)
    assert unknown_tool["isError"] is True
    assert "E_MCP_UNKNOWN_TOOL" in modern_structured(unknown_tool)["error"]
    mixed = mcp.request({"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}})
    assert mixed["error"]["code"] == -32602, mixed
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
    unknown_field = mcp.tool(
        7,
        "begin_transaction",
        {"project": "does-not-matter.toml", "unexpected_field": True},
    )
    assert unknown_field["isError"] is True
    assert "unknown field 'unexpected_field'" in structured(unknown_field)["error"]
    hidden_nested = mcp.tool(
        8,
        "stage_and_check",
        {"operation": "rename_entity", "arguments": {"entity": "x", "new_name": "y"}},
    )
    assert hidden_nested["isError"] is True
    assert "not an exposed MCP mutation" in structured(hidden_nested)["error"]
    recursive_nested = mcp.tool(
        9,
        "stage_and_check",
        {"operation": "stage_and_check", "arguments": {}},
    )
    assert recursive_nested["isError"] is True
    assert "not an exposed MCP mutation" in structured(recursive_nested)["error"]
    mcp.close()

    missing_version_mcp = Mcp(binary)
    missing_version = missing_version_mcp.request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "server/discover",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
    )
    assert missing_version["error"]["code"] == -32602, missing_version
    missing_version_mcp.close()

    missing_capabilities_mcp = Mcp(binary)
    missing_capabilities = missing_capabilities_mcp.request(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "server/discover",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                }
            },
        }
    )
    assert missing_capabilities["error"]["code"] == -32602, missing_capabilities
    missing_capabilities_mcp.close()

    unsupported_mcp = Mcp(binary)
    unsupported = unsupported_mcp.request(
        {
            "jsonrpc": "2.0",
            "id": 9,
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
    assert unsupported["error"]["data"] == {
        "supported": ["2026-07-28"],
        "requested": "2099-01-01",
    }, unsupported
    unsupported_mcp.close()


def semantic_fixture(binary: Path, repo: Path, commit: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="alva-mcp-") as temp:
        project = Path(temp) / "project"
        shutil.copytree(repo / "tests" / "project", project)
        source = project / "src" / "app.alva"
        source_before = source.read_bytes()

        mcp = Mcp(binary)
        listed = mcp.request(
            {"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}}
        )["result"]
        exposed = {tool["name"] for tool in listed["tools"]}
        begun = structured(mcp.tool(11, "begin_transaction", {"project": str(project / "alva.toml")}))
        transaction = begun["transaction_id"]
        resolved = structured(
            mcp.tool(
                12,
                "resolve_entity",
                {"transaction_id": transaction, "name": "demo.app.run", "kind": "function"},
            )
        )["entity"]
        prepared = structured(
            mcp.tool(
                19,
                "prepare_edit",
                {
                    "transaction_id": transaction,
                    "entity": "demo.app.run",
                    "kind": "function",
                    "operation": "rename_entity",
                },
            )
        )
        assert prepared["revision"] == resolved
        assert prepared["kind"] == "function"
        assert "rename_entity" in prepared["applicable_operations"]
        assert prepared["selected_operation"]["name"] == "rename_entity"
        applicable = structured(
            mcp.tool(
                13,
                "applicable_operations",
                {"transaction_id": transaction, "entity": resolved},
            )
        )
        advertised = set(
            applicable["inspection"]
            + applicable["mutation"]
            + applicable["context_operations"]
        )
        assert advertised <= exposed, (advertised, exposed)
        assert "append_step" not in advertised
        body = structured(
            mcp.tool(14, "inspect_body", {"transaction_id": transaction, "function": "demo.app.run"})
        )["body"]
        literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
        assert literal, body
        staged = mcp.tool(
            15,
            "stage_and_check",
            {
                "transaction_id": transaction,
                "operation": "change_field",
                "arguments": {
                    "entity": literal.group(1),
                    "field": "value",
                    "value": "hello from MCP",
                },
            },
        )
        assert staged["isError"] is False, staged
        staged_result = structured(staged)
        assert staged_result["operation"] == "change_field", staged_result
        assert staged_result["mutation"]["new_revision"] != literal.group(1), staged_result
        assert staged_result["diff"], staged_result
        assert staged_result["check"]["ok"] is True, staged_result
        assert staged_result["check"]["problems"] == [], staged_result

        if not commit:
            mcp.close()
            assert source.read_bytes() == source_before
            assert not (project / "alva-air").exists()
            return

        diff = structured(mcp.tool(16, "preview_semantic_diff", {"transaction_id": transaction}))
        assert diff["diff"].strip(), diff
        checked = mcp.tool(17, "check_transaction", {"transaction_id": transaction})
        assert checked["isError"] is False, checked
        committed = mcp.tool(18, "commit_transaction", {"transaction_id": transaction})
        assert committed["isError"] is False, committed
        mcp.close()
        assert source.read_bytes() == source_before
        assert (project / "alva-air" / "current").exists()
        subprocess.run([str(binary), "project", "check", str(project / "alva.toml"), "--json"], check=True)
        subprocess.run([str(binary), "project", "build", str(project / "alva.toml")], check=True)


def text_patch_fixture(binary: Path, repo: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="alva-mcp-text-") as temp:
        project = Path(temp) / "project"
        shutil.copytree(repo / "tests" / "project", project)
        source = project / "src" / "app.alva"
        source_before = source.read_bytes()
        source_sha = hashlib.sha256(source_before).hexdigest()

        mcp = Mcp(binary)
        begun = structured(mcp.tool(30, "begin_transaction", {"project": str(project / "alva.toml")}))
        transaction = begun["transaction_id"]
        traversal = mcp.tool(
            31,
            "stage_and_check",
            {"transaction_id": transaction, "operation": "stage_text_patch", "arguments": {
                "path": "../project/src/app.alva", "expected_sha256": source_sha,
                "old": '(string "a")', "new": '(string "blocked")'}},
        )
        assert traversal["isError"] is True, traversal
        assert "path traversal is forbidden" in structured(traversal)["error"]
        stale = mcp.tool(
            32,
            "stage_and_check",
            {"transaction_id": transaction, "operation": "stage_text_patch", "arguments": {
                "path": "src/app.alva", "expected_sha256": "0" * 64,
                "old": '(string "a")', "new": '(string "blocked")'}},
        )
        assert stale["isError"] is True, stale
        assert "E_AEP_TEXT_STALE" in structured(stale)["error"]
        staged = mcp.tool(
            33,
            "stage_and_check",
            {
                "transaction_id": transaction,
                "operation": "stage_text_patch",
                "arguments": {
                    "path": "src/app.alva",
                    "expected_sha256": source_sha,
                    "old": '(string "a")',
                    "new": '(string "patched-by-text")',
                },
            },
        )
        assert staged["isError"] is False, staged
        result = structured(staged)
        assert result["operation"] == "stage_text_patch", result
        assert result["mutation"]["source_written"] is False, result
        assert result["mutation"]["authority"] == "AIR", result
        assert result["check"]["ok"] is True, result
        body = structured(
            mcp.tool(
                34,
                "inspect_body",
                {"transaction_id": transaction, "function": "demo.app.run"},
            )
        )["body"]
        assert "literal value=patched-by-text" in body, body
        assert source.read_bytes() == source_before
        aborted = mcp.tool(35, "abort_transaction", {"transaction_id": transaction})
        assert aborted["isError"] is False, aborted
        mcp.close()
        assert source.read_bytes() == source_before
        assert not (project / "alva-air").exists()

        external_mcp = Mcp(binary)
        external_begin = structured(
            external_mcp.tool(36, "begin_transaction", {"project": str(project / "alva.toml")})
        )
        external_tx = external_begin["transaction_id"]
        source.write_bytes(source_before + b"\n# external change\n")
        external = external_mcp.tool(
            37,
            "stage_and_check",
            {"transaction_id": external_tx, "operation": "stage_text_patch", "arguments": {
                "path": "src/app.alva", "expected_sha256": source_sha,
                "old": '(string "a")', "new": '(string "blocked")'}},
        )
        assert external["isError"] is True, external
        assert "E_AEP_TEXT_SOURCE_CHANGED" in structured(external)["error"]
        source.write_bytes(source_before)
        external_mcp.tool(38, "abort_transaction", {"transaction_id": external_tx})
        external_mcp.close()

        mixed_mcp = Mcp(binary)
        mixed_begin = structured(
            mixed_mcp.tool(39, "begin_transaction", {"project": str(project / "alva.toml")})
        )
        mixed_tx = mixed_begin["transaction_id"]
        mixed_body = structured(
            mixed_mcp.tool(
                40,
                "inspect_body",
                {"transaction_id": mixed_tx, "function": "demo.app.run"},
            )
        )["body"]
        mixed_literal = re.search(r"literal value=a rev=([0-9a-f]{64})", mixed_body)
        assert mixed_literal, mixed_body
        changed = mixed_mcp.tool(
            41,
            "change_field",
            {"transaction_id": mixed_tx, "entity": mixed_literal.group(1),
             "field": "value", "value": "semantic-first"},
        )
        assert changed["isError"] is False, changed
        mixed = mixed_mcp.tool(
            42,
            "stage_and_check",
            {"transaction_id": mixed_tx, "operation": "stage_text_patch", "arguments": {
                "path": "src/app.alva", "expected_sha256": source_sha,
                "old": '(string "a")', "new": '(string "blocked")'}},
        )
        assert mixed["isError"] is True, mixed
        assert "E_AEP_TEXT_MIXED_MODE" in structured(mixed)["error"]
        mixed_mcp.tool(43, "abort_transaction", {"transaction_id": mixed_tx})
        mixed_mcp.close()
        assert source.read_bytes() == source_before

        commit_guard_mcp = Mcp(binary)
        guard_begin = structured(
            commit_guard_mcp.tool(
                44, "begin_transaction", {"project": str(project / "alva.toml")}
            )
        )
        guard_tx = guard_begin["transaction_id"]
        guard_stage = commit_guard_mcp.tool(
            45,
            "stage_and_check",
            {"transaction_id": guard_tx, "operation": "stage_text_patch", "arguments": {
                "path": "src/app.alva", "expected_sha256": source_sha,
                "old": '(string "a")', "new": '(string "commit-guard")'}},
        )
        assert guard_stage["isError"] is False, guard_stage
        source.write_bytes(source_before + b"\n# changed before commit\n")
        guarded_commit = commit_guard_mcp.tool(
            46, "commit_transaction", {"transaction_id": guard_tx}
        )
        assert guarded_commit["isError"] is True, guarded_commit
        assert "E_AEP_TEXT_SOURCE_CHANGED" in structured(guarded_commit)["error"]
        assert not (project / "alva-air").exists()
        source.write_bytes(source_before)
        guard_abort = commit_guard_mcp.tool(
            47, "abort_transaction", {"transaction_id": guard_tx}
        )
        assert guard_abort["isError"] is False, guard_abort
        commit_guard_mcp.close()

        commit_mcp = Mcp(binary)
        commit_begin = structured(
            commit_mcp.tool(48, "begin_transaction", {"project": str(project / "alva.toml")})
        )
        commit_tx = commit_begin["transaction_id"]
        commit_stage = commit_mcp.tool(
            49,
            "stage_and_check",
            {"transaction_id": commit_tx, "operation": "stage_text_patch", "arguments": {
                "path": "src/app.alva", "expected_sha256": source_sha,
                "old": '(string "a")', "new": '(string "committed-as-air")'}},
        )
        assert commit_stage["isError"] is False, commit_stage
        committed = commit_mcp.tool(
            50, "commit_transaction", {"transaction_id": commit_tx}
        )
        assert committed["isError"] is False, committed
        commit_mcp.close()
        assert source.read_bytes() == source_before
        assert (project / "alva-air" / "current").is_file()
        subprocess.run(
            [str(binary), "project", "check", str(project / "alva.toml"), "--json"],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    repo = Path(__file__).resolve().parents[2]
    legacy_fixture(binary)
    modern_fixture(binary)
    errors_fixture(binary)
    text_patch_fixture(binary, repo)
    semantic_fixture(binary, repo, commit=False)
    semantic_fixture(binary, repo, commit=True)
    print("PASS: MCP legacy, modern, errors, authority safety, and semantic commit")


if __name__ == "__main__":
    main()
