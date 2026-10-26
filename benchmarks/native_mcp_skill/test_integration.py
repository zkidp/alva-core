"""Linux transport regression; simulated Codex peer, REAL sandbox/native MCP.

The separate phase_a.py test is the actual Codex Host acceptance.
"""

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git
from integrations.benchmark_runtime_v2.persistent import (
    Closed,
    PersistentSandbox,
    UnsupportedDiscovery,
)
from integrations.benchmark_runtime_v2.sandbox import SDK


def run(args):
    bundle = pack_git(
        args.repo,
        "ca930db61823c8318f1126f5649d1863f10fcc37",
        [
            "tests/project/alva.toml",
            "tests/project/src/app.alva",
            "tests/project/src/model.alva",
        ],
    )
    sdk = SDK(args.alva.resolve(), args.toolchain.resolve(), args.registry.resolve())
    rows = []
    with PersistentSandbox(bundle, bundle["payload_sha256"], sdk) as box:
        with box.mcp() as mcp:
            mcp.request(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "optional-discovery-test", "version": "1"},
                },
            )
            for method in (
                "resources/list",
                "resources/templates/list",
                "prompts/list",
            ):
                try:
                    mcp.request(method, optional_discovery=True)
                except UnsupportedDiscovery as exc:
                    assert exc.error["code"] == -32601
                else:
                    raise AssertionError("Expected original unsupported method")
                assert mcp.request("tools/list")["tools"]
        rows.append(
            {
                "test": "optional_metadata_returns_original_error_session_survives",
                "status": "PASS",
            }
        )
    for method, optional in (("resources/list", False), ("unknown/semantic", True)):
        with PersistentSandbox(bundle, bundle["payload_sha256"], sdk) as box:
            mcp = box.mcp()
            try:
                mcp.request(method, optional_discovery=optional)
            except Closed:
                assert box.poisoned and mcp.process.p.poll() is not None
            else:
                raise AssertionError("Generic RPC failure did not fail closed")
    rows.append(
        {
            "test": "strict_default_and_nonwhitelisted_errors_still_fail_closed",
            "status": "PASS",
        }
    )
    with tempfile.TemporaryDirectory(prefix="native-host-test-") as directory:
        scratch = Path(directory)
        (scratch / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
        config = {
            "bundle": str(scratch / "bundle.json"),
            "bundle_id": bundle["payload_sha256"],
            "alva": str(sdk.alva),
            "toolchain": str(sdk.rust_toolchain),
            "registry": str(sdk.registry),
            "ready": str(scratch / "ready.json"),
            "evidence": str(scratch / "evidence.json"),
        }
        (scratch / "config.json").write_text(json.dumps(config), encoding="utf-8")
        process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "benchmarks/native_mcp_skill/proxy.py"),
                "--role",
                "server",
                "--config",
                str(scratch / "config.json"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        clients = []
        try:
            end = time.monotonic() + 15
            while not (scratch / "ready.json").is_file():
                assert process.poll() is None
                assert time.monotonic() < end
                time.sleep(0.02)
            address = json.loads((scratch / "ready.json").read_text())["socket"]

            def connect(role):
                client = socket.socket(socket.AF_UNIX)
                client.settimeout(30)
                client.connect(address)
                client.sendall(json.dumps({"role": role}).encode() + b"\n")
                clients.append(client)
                return client

            metadata, primary = connect("mcp"), connect("mcp")
            readers = {c: c.makefile("rb") for c in (metadata, primary)}
            ordinal = 0

            def rpc(client, method, params={}):
                nonlocal ordinal
                ordinal += 1
                client.sendall(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": ordinal,
                            "method": method,
                            "params": params,
                        }
                    ).encode()
                    + b"\n"
                )
                response = json.loads(readers[client].readline(1024**2))
                assert response["id"] == ordinal
                return response

            for client in (metadata, primary):
                assert "result" in rpc(
                    client,
                    "initialize",
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "synthetic-host-peer", "version": "1"},
                    },
                )
                assert rpc(client, "tools/list")["result"]["tools"]
                assert (
                    rpc(client, "resources/templates/list")["error"]["code"] == -32601
                )

            def call(name, **arguments):
                result = rpc(
                    primary, "tools/call", {"name": name, "arguments": arguments}
                )["result"]
                assert not result["isError"], result
                return result["structuredContent"]

            tx = call(
                "begin_transaction", project="/work/project/tests/project/alva.toml"
            )["transaction_id"]

            def tool(operation, **arguments):
                return call(operation, transaction_id=tx, **arguments)

            import re

            body = tool("inspect_body", function="demo.app.run")["body"]
            literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
            assert literal
            tool(
                "change_field",
                entity=literal.group(1),
                field="value",
                value="native-host-isolated",
            )
            tool("check_transaction")
            tool("commit_transaction")
            for reader in readers.values():
                reader.close()
            for client in clients:
                client.close()
            control = connect("verify")
            with control.makefile("rb") as reader:
                assert json.loads(reader.readline())["status"] == "PASS"
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, (stdout, stderr)
            evidence = json.loads((scratch / "evidence.json").read_text())
            assert evidence["status"] == "PASS" and len(evidence["sessions"]) == 2
            rows.append(
                {
                    "test": "parallel_metadata_contexts_one_commit_isolated_reopen_build",
                    "status": "PASS",
                    "independent_build": evidence["independent_build"],
                }
            )
        finally:
            for client in clients:
                client.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    return {
        "status": "PASS",
        "rows": rows,
        "generation_calls": 0,
        "input_token_calls": 0,
        "scope": "Synthetic transport peer plus real native MCP/OS boundary; not actual Codex Host acceptance.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument("--alva", type=Path, required=True)
    p.add_argument("--toolchain", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"status": result["status"], "generation_calls": 0}))
