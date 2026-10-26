"""Trusted stdio launcher for the unchanged ALVA MCP inside P23 isolation.

Only JSON-RPC envelopes are bridged; no model/provider code executes here.
"""

import argparse
import json
from pathlib import Path
import socket
import tempfile
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.persistent import (
    PersistentSandbox,
    UnsupportedDiscovery,
)
from integrations.benchmark_runtime_v2.sandbox import SDK


def serve(config_path):
    config = json.loads(config_path.read_text())
    bundle = json.loads(Path(config["bundle"]).read_text())
    sdk = SDK(*(Path(config[k]) for k in ("alva", "toolchain", "registry")))
    record = {"status": "FAIL_CLOSED", "generation_calls": 0, "sessions": []}
    workers = []
    try:
        with tempfile.TemporaryDirectory(prefix="alva-host-socket-") as directory:
            with socket.socket(socket.AF_UNIX) as listener:
                address = str(Path(directory) / "native.sock")
                listener.bind(address)
                listener.listen(2)
                listener.settimeout(115)
                Path(config["ready"]).write_text(
                    json.dumps({"socket": address}), encoding="utf-8"
                )
                while True:
                    connection, _ = listener.accept()
                    reader = connection.makefile("rb")
                    role = json.loads(reader.readline(1024))["role"]
                    if role in ("verify", "abort"):
                        with connection, reader:
                            for worker in workers:
                                with worker["lock"]:
                                    worker["stop"].set()
                                    try:
                                        worker["connection"].shutdown(socket.SHUT_RD)
                                    except OSError:
                                        pass
                            for worker in workers:
                                worker["thread"].join(timeout=10)
                                assert not worker[
                                    "thread"
                                ].is_alive(), "MCP close unconfirmed"
                                assert (
                                    worker["record"].get("status") == "CLOSED"
                                ), worker["record"]
                            candidates = [
                                w
                                for w in workers
                                if any(
                                    c.get("params", {}).get("name")
                                    == "commit_transaction"
                                    for c in w["record"]["calls"]
                                )
                            ]
                            if role == "verify":
                                assert (
                                    len(candidates) == 1
                                ), "Exactly one semantic connection required"
                                verify(candidates[0]["box"], record)
                            record["status"] = "PASS" if role == "verify" else "ABORTED"
                            connection.sendall(
                                json.dumps({"status": record["status"]}).encode()
                                + b"\n"
                            )
                        break
                    assert (
                        role == "mcp" and len(workers) < 4
                    ), "Bounded expected MCP contexts"
                    worker = {
                        "record": {"status": "OPEN", "calls": []},
                        "connection": connection,
                        "lock": threading.RLock(),
                        "stop": threading.Event(),
                    }
                    workers.append(worker)
                    record["sessions"].append(worker["record"])

                    def session(worker=worker, reader=reader, connection=connection):
                        try:
                            box = PersistentSandbox(
                                bundle, config["bundle_id"], sdk, wall_seconds=120
                            )
                            worker["box"] = box
                            with connection, reader, box.mcp() as mcp:
                                forward(reader, connection, mcp, worker)
                            worker["record"]["status"] = "CLOSED"
                        except BaseException as exc:
                            worker["record"].update(
                                status="FAIL_CLOSED", error=str(exc)[:1000]
                            )

                    worker["thread"] = threading.Thread(target=session, daemon=True)
                    worker["thread"].start()
    except BaseException as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)[:2000]
        raise
    finally:
        for worker in workers:
            try:
                worker["connection"].shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            worker["thread"].join(timeout=10)
            if "box" in worker:
                worker["box"].close()
        output = Path(config["evidence"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
        )


def forward(reader, connection, mcp, worker):
    record = worker["record"]
    while line := reader.readline(1024**2 + 1):
        with worker["lock"]:
            if worker["stop"].is_set():
                break
            if len(line) > 1024**2 or not line.endswith(b"\n"):
                raise ValueError("Invalid bounded JSON-RPC line")
            request = json.loads(line)
            if request.get("jsonrpc") != "2.0":
                raise ValueError("JSON-RPC version")
            method, params = request["method"], request.get("params", {})
            if "id" not in request:
                mcp.notify(method, params)
                continue
            try:
                result = mcp.request(method, params, optional_discovery=True)
            except UnsupportedDiscovery as exc:
                record["calls"].append(
                    {"method": method, "unsupported_optional_discovery": exc.error}
                )
                connection.sendall(
                    json.dumps(
                        {"jsonrpc": "2.0", "id": request["id"], "error": exc.error}
                    ).encode()
                    + b"\n"
                )
                continue
            record["calls"].append(
                {"method": method, "params": params, "result": result}
            )
            connection.sendall(
                json.dumps(
                    {"jsonrpc": "2.0", "id": request["id"], "result": result}
                ).encode()
                + b"\n"
            )


def verify(box, record):
    # Public zero-model connection fixture only, never a hidden answer.
    with box.mcp() as fresh:
        fresh.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "p24-authority-probe", "version": "1"},
            },
        )
        tx = fresh.tool(
            "begin_transaction", {"project": "/work/project/tests/project/alva.toml"}
        )["structuredContent"]["transaction_id"]
        body = fresh.tool(
            "inspect_body", {"transaction_id": tx, "function": "demo.app.run"}
        )
        assert "native-host-isolated" in json.dumps(body), body
        fresh.tool("abort_transaction", {"transaction_id": tx})
    driver = """import pathlib,subprocess
def run(args):
 p=subprocess.run(args,capture_output=True,text=True)
 assert p.returncode==0,(args,p.stdout,p.stderr)
root=pathlib.Path("/work/project/tests/project")
for p in (root/"src").glob("*.alva"):
 assert p.read_bytes()==(pathlib.Path("/input/tests/project/src")/p.name).read_bytes()
run(["/sdk/alva","project","check",str(root/"alva.toml"),"--json"])
run(["/sdk/alva","project","build",str(root/"alva.toml"),"--out-dir","/work/generated"])
crate=pathlib.Path("/work/generated/demo")
assert any("native-host-isolated" in p.read_text() for p in (crate/"src").rglob("*.rs"))
with (crate/"src/lib.rs").open("a") as f:f.write("#[test] fn independent_host_probe(){assert_eq!(demo_app::run(),6);}")
run(["/sdk/toolchain/bin/cargo","test","--offline","--manifest-path",str(crate/"Cargo.toml")])
print("BUILD_BEHAVIOR_PASS; AIR_USED; SOURCE_UNCHANGED")
"""
    record["independent_build"] = box.run(["/usr/bin/python3", "-I", "-c", driver])


def relay(ready_path, role):
    address = json.loads(ready_path.read_text())["socket"]
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect(address)
        connection.sendall(json.dumps({"role": role}).encode() + b"\n")
        with connection.makefile("rb") as reader:
            if role in ("verify", "abort"):
                answer = reader.readline(1024**2)
                assert json.loads(answer)["status"] == (
                    "PASS" if role == "verify" else "ABORTED"
                )
                print(answer.decode(), end="", flush=True)
                return
            while line := sys.stdin.buffer.readline(1024**2 + 1):
                if len(line) > 1024**2 or not line.endswith(b"\n"):
                    raise ValueError("Unbounded stdio request")
                request = json.loads(line)
                connection.sendall(line)
                if "id" in request:
                    response = reader.readline(8 * 1024**2 + 1)
                    if not response or len(response) > 8 * 1024**2:
                        raise ValueError("Missing/unbounded response")
                    sys.stdout.buffer.write(response)
                    sys.stdout.buffer.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--role", choices=("server", "mcp", "verify", "abort"), default="mcp"
    )
    args = parser.parse_args()
    if args.role == "server":
        serve(args.config)
    else:
        relay(args.config, args.role)
