#!/usr/bin/env python3
"""Measure ALVA MCP wire cost without making model calls.

This is a protocol byte census, not a billed-token estimate. It reports the
deterministic tool-list surface and detects duplicate text/structured payloads
for a minimal read-only transaction. The transaction is always aborted.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {
        "name": "alva-agent-io-audit",
        "version": "1",
    },
    "io.modelcontextprotocol/clientCapabilities": {},
}


def encoded_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def schema_description_bytes(value: Any) -> int:
    if isinstance(value, dict):
        own = len(value.get("description", "").encode("utf-8"))
        return own + sum(schema_description_bytes(child) for child in value.values())
    if isinstance(value, list):
        return sum(schema_description_bytes(child) for child in value)
    return 0


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

    def request(self, request: dict[str, Any]) -> dict[str, Any]:
        assert self.process.stdin and self.process.stdout and self.process.stderr
        self.process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(self.process.stderr.read())
        return json.loads(line)

    def close(self) -> None:
        assert self.process.stdin and self.process.stderr
        self.process.stdin.close()
        stderr = self.process.stderr.read()
        code = self.process.wait(timeout=10)
        if code != 0:
            raise RuntimeError(stderr)


def envelope(request_id: int, method: str, params: dict[str, Any], modern: bool) -> dict[str, Any]:
    if modern:
        params = dict(params)
        params["_meta"] = MODERN_META
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def result_payload_metrics(call_result: dict[str, Any]) -> dict[str, Any]:
    text = call_result.get("content", [{}])[0].get("text", "")
    structured = call_result.get("structuredContent")
    parsed_text = None
    try:
        parsed_text = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        pass
    return {
        "wire_bytes": encoded_size(call_result),
        "content_text_bytes": len(text.encode("utf-8")),
        "structured_content_bytes": encoded_size(structured),
        "text_duplicates_structured_content": parsed_text == structured,
    }


def census(binary: Path, project: Path, modern: bool) -> dict[str, Any]:
    mcp = Mcp(binary)
    version = "2026-07-28" if modern else "2025-11-25"
    init_params: dict[str, Any] = {
        "protocolVersion": version,
        "capabilities": {},
        "clientInfo": {"name": "alva-agent-io-audit", "version": "1"},
    }
    if modern:
        init_params["_meta"] = MODERN_META
    mcp.request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": init_params})

    listed = mcp.request(envelope(2, "tools/list", {}, modern))["result"]
    tools = listed["tools"]
    begin = mcp.request(
        envelope(
            3,
            "tools/call",
            {"name": "begin_transaction", "arguments": {"project": str(project)}},
            modern,
        )
    )["result"]
    transaction_id = begin["structuredContent"]["transaction_id"]
    inspect = mcp.request(
        envelope(
            4,
            "tools/call",
            {
                "name": "inspect_project",
                "arguments": {"transaction_id": transaction_id},
            },
            modern,
        )
    )["result"]
    resolved = mcp.request(
        envelope(
            5,
            "tools/call",
            {
                "name": "resolve_entity",
                "arguments": {
                    "transaction_id": transaction_id,
                    "name": "demo.app.run",
                    "kind": "function",
                },
            },
            modern,
        )
    )["result"]
    resolved_entity = resolved["structuredContent"]["entity"]
    inspected_entity = mcp.request(
        envelope(
            6,
            "tools/call",
            {
                "name": "inspect_entity",
                "arguments": {
                    "transaction_id": transaction_id,
                    "entity": resolved_entity,
                },
            },
            modern,
        )
    )["result"]
    applicable = mcp.request(
        envelope(
            7,
            "tools/call",
            {
                "name": "applicable_operations",
                "arguments": {
                    "transaction_id": transaction_id,
                    "entity": resolved_entity,
                },
            },
            modern,
        )
    )["result"]
    described = mcp.request(
        envelope(
            8,
            "tools/call",
            {
                "name": "describe_operation",
                "arguments": {
                    "transaction_id": transaction_id,
                    "name": "rename_entity",
                },
            },
            modern,
        )
    )["result"]
    prepared = mcp.request(
        envelope(
            9,
            "tools/call",
            {
                "name": "prepare_edit",
                "arguments": {
                    "transaction_id": transaction_id,
                    "entity": "demo.app.run",
                    "kind": "function",
                    "operation": "rename_entity",
                },
            },
            modern,
        )
    )["result"]
    inspected_body = mcp.request(
        envelope(
            10,
            "tools/call",
            {
                "name": "inspect_body",
                "arguments": {
                    "transaction_id": transaction_id,
                    "function": "demo.app.run",
                },
            },
            modern,
        )
    )["result"]
    body = inspected_body["structuredContent"]["body"]
    literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
    if not literal:
        raise RuntimeError("measurement fixture literal not found")
    mutation_arguments = {
        "entity": literal.group(1),
        "field": "value",
        "value": "agent-io-census",
    }
    separate_mutation = mcp.request(
        envelope(
            11,
            "tools/call",
            {
                "name": "change_field",
                "arguments": {"transaction_id": transaction_id, **mutation_arguments},
            },
            modern,
        )
    )["result"]
    separate_diff = mcp.request(
        envelope(
            12,
            "tools/call",
            {
                "name": "preview_semantic_diff",
                "arguments": {"transaction_id": transaction_id},
            },
            modern,
        )
    )["result"]
    separate_check = mcp.request(
        envelope(
            13,
            "tools/call",
            {
                "name": "check_transaction",
                "arguments": {"transaction_id": transaction_id},
            },
            modern,
        )
    )["result"]
    mcp.request(
        envelope(
            14,
            "tools/call",
            {
                "name": "abort_transaction",
                "arguments": {"transaction_id": transaction_id},
            },
            modern,
        )
    )
    second_begin = mcp.request(
        envelope(
            15,
            "tools/call",
            {"name": "begin_transaction", "arguments": {"project": str(project)}},
            modern,
        )
    )["result"]
    second_transaction = second_begin["structuredContent"]["transaction_id"]
    staged = mcp.request(
        envelope(
            16,
            "tools/call",
            {
                "name": "stage_and_check",
                "arguments": {
                    "transaction_id": second_transaction,
                    "operation": "change_field",
                    "arguments": mutation_arguments,
                },
            },
            modern,
        )
    )["result"]
    mcp.request(
        envelope(
            17,
            "tools/call",
            {
                "name": "abort_transaction",
                "arguments": {"transaction_id": second_transaction},
            },
            modern,
        )
    )
    mcp.close()

    return {
        "protocol": version,
        "tool_count": len(tools),
        "tools_list_wire_bytes": encoded_size(listed),
        "tool_description_bytes": sum(
            len(tool.get("description", "").encode("utf-8")) for tool in tools
        ),
        "input_schema_bytes": sum(encoded_size(tool.get("inputSchema", {})) for tool in tools),
        "schema_description_bytes": sum(
            schema_description_bytes(tool.get("inputSchema", {})) for tool in tools
        ),
        "tool_descriptions_with_examples": sum(
            "Example:" in tool.get("description", "") for tool in tools
        ),
        "tool_surface_hash": listed.get("toolSurfaceHash"),
        "schema_profile": listed.get("schemaProfile", "legacy-full"),
        "begin_transaction": result_payload_metrics(begin),
        "inspect_project": result_payload_metrics(inspect),
        "prepare_edit_comparison": {
            "separate_calls": {
                "round_trips": 4,
                "wire_bytes": sum(
                    result_payload_metrics(result)["wire_bytes"]
                    for result in (resolved, inspected_entity, applicable, described)
                ),
            },
            "prepare_edit": {
                "round_trips": 1,
                "wire_bytes": result_payload_metrics(prepared)["wire_bytes"],
            },
        },
        "stage_and_check_comparison": {
            "separate_calls": {
                "round_trips": 3,
                "wire_bytes": sum(
                    result_payload_metrics(result)["wire_bytes"]
                    for result in (separate_mutation, separate_diff, separate_check)
                ),
            },
            "stage_and_check": {
                "round_trips": 1,
                "wire_bytes": result_payload_metrics(staged)["wire_bytes"],
            },
        },
        "round_trips_measured": 17,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--source-revision", default="UNKNOWN")
    args = parser.parse_args()

    binary = args.binary.resolve()
    project = args.project.resolve()
    if not binary.is_file():
        parser.error(f"binary does not exist: {binary}")
    if not project.is_file():
        parser.error(f"project manifest does not exist: {project}")

    report = {
        "schema_version": "alva-agent-io-census-v1",
        "source_revision": args.source_revision,
        "binary": str(binary),
        "project": str(project),
        "measurement_boundary": (
            "UTF-8 JSON wire bytes only; no tokenizer, prompt-cache, reasoning, or billed-token claim"
        ),
        "legacy": census(binary, project, modern=False),
        "modern": census(binary, project, modern=True),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
