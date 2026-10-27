"""Minimal trusted P23 slot service; native RPC remains the actual ALVA MCP."""

import argparse
import base64
import json
from pathlib import Path
import hashlib
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.persistent import (
    PersistentSandbox,
    _Process,
    UnsupportedDiscovery,
)
from integrations.benchmark_runtime_v2.sandbox import SDK, LinuxSandbox
from benchmarks.native_mcp_skill.proxy import relay


class Lines:
    """Use P23's bounded process/termination mechanics, not a host subprocess."""

    def __init__(self, box):
        self.box = box
        self.proc = _Process(
            box,
            [
                "/usr/bin/python3",
                "-I",
                "-c",
                Path(__file__).with_name("inside.py").read_text(),
            ],
        )

    def call(self, action, args):
        pending = (json.dumps({"action": action, "arguments": args}) + "\n").encode()
        deadline = time.monotonic() + 30
        while pending or b"\n" not in self.proc.out:
            pending = self.proc.pump(deadline, pending)
            if self.proc.p.poll() is not None:
                raise RuntimeError("SIDECAR_EXIT; no retry")
        line, _, rest = self.proc.out.partition(b"\n")
        self.proc.out = bytearray(rest)
        return json.loads(line)

    def close(self):
        self.proc.shutdown(graceful=True)


def files(box):
    result = {}
    root = box.work / "project"
    for p in root.rglob("*"):
        if p.is_symlink():
            raise RuntimeError("Unexpected candidate symlink")
        if p.is_file() and (
            p.suffix == ".alva" or p.name == "alva.toml" or "alva-air" in p.parts
        ):
            result[p.relative_to(root).as_posix()] = p.read_bytes()
    if sum(map(len, result.values())) > 8 * 1024**2:
        raise RuntimeError("Candidate output limit")
    return result


def evaluate(snapshot, sdk, vectors, check_only=False):
    # Hidden expectations exist only in this separate evaluation process tree,
    # never in the candidate namespace or native MCP input mount.
    rust = lambda x: (
        str(x).lower()
        if type(x) is bool
        else (
            str(x) + "i64"
            if type(x) is int
            else (
                json.dumps(x) + ".to_string()"
                if type(x) is str
                else "vec![" + ",".join(rust(y) for y in x) + "]"
            )
        )
    )
    assertions = "\n#[cfg(test)] mod independent { use super::bench::solve;\n"
    for i, (value, expected) in enumerate(vectors):
        assertions += f"#[test] fn case_{i}(){{assert_eq!(solve({rust(value)}),{rust(expected)});}}\n"
    assertions += "}\n"
    driver = """import json,pathlib,subprocess
def run(args):
 p=subprocess.run(args,capture_output=True,text=True)
 return {"exit":p.returncode,"stdout":p.stdout[-12000:],"stderr":p.stderr[-12000:]}
r={"check":run(["/sdk/alva","project","check","alva.toml","--json"])}
if r["check"]["exit"]:r["status"]="COMPILE_FAIL"
elif CHECK_ONLY:r["status"]="PASS"
else:
 r["build"]=run(["/sdk/alva","project","build","alva.toml","--out-dir","/work/generated"])
 if r["build"]["exit"]:r["status"]="COMPILE_FAIL"
 else:
  crate=pathlib.Path("/work/generated/bench")
  with (crate/"src/lib.rs").open("a") as f:f.write(ASSERTIONS)
  r["execution"]=run(["/sdk/toolchain/bin/cargo","test","--offline","--manifest-path",str(crate/"Cargo.toml")])
  r["status"]="PASS" if r["execution"]["exit"]==0 else "TEST_FAIL"
print(json.dumps(r))
""".replace("CHECK_ONLY", repr(check_only)).replace("ASSERTIONS", repr(assertions))
    raw = LinuxSandbox(sdk, wall_seconds=120, output_limit=131072).run(
        snapshot, ["/usr/bin/python3", "-I", "-c", driver]
    )
    if raw["status"] != "EXECUTED" or raw["exit"] != 0:
        return {"status": "EVALUATION_LIMIT_OR_FAILURE", "execution": raw}
    return json.loads(raw["stdout"]["text"])


def inspect_authority(box):
    with box.mcp() as native:
        native.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "p26-host-authority", "version": "1"},
            },
        )
        begun = native.tool(
            "begin_transaction", {"project": "/work/project/alva.toml"}
        )["structuredContent"]
        body = native.tool(
            "inspect_body",
            {"transaction_id": begun["transaction_id"], "function": "bench.solve"},
        )
        if body.get("isError"):
            # Invalid text candidates are evaluated as compile failures, not
            # rescued by replacing them with the original program.
            return {"project_revision": begun["project_revision"], "body_error": True}
        native.tool("abort_transaction", {"transaction_id": begun["transaction_id"]})
        return {
            "project_revision": begun["project_revision"],
            "body_sha256": hashlib.sha256(
                body["structuredContent"]["body"].encode()
            ).hexdigest(),
        }


def serve(config_path):
    config = json.loads(config_path.read_text())
    sdk = SDK(*(Path(config[k]) for k in ("alva", "toolchain", "registry")))
    box = PersistentSandbox(
        config["bundle"],
        config["bundle"]["payload_sha256"],
        sdk,
        wall_seconds=660,
        rpc_seconds=30,
    )
    lock = threading.RLock()
    native = None
    side = None
    workers = []
    contexts = []
    selected = [None]
    dispatches = [0]
    record = {"calls": [], "status": "OPEN"}
    source_initial = files(box)
    current_process = None
    socket_path = str(box.root / "host.sock")  # outside /work: not mounted
    try:
        record["initial_authority"] = inspect_authority(box)
        if config["arm"] != "N":
            side = Lines(box)
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(socket_path)
            server.listen(4)
            server.settimeout(650)
            Path(config["ready"]).write_text(json.dumps({"socket": socket_path}))
            stop = False
            while not stop:
                connection, _ = server.accept()
                reader = connection.makefile("rb")
                header = json.loads(reader.readline(1024**2))
                role = header["role"]
                if role == "mcp":
                    if config["arm"] != "N" or len(contexts) >= 4:
                        raise RuntimeError("Unexpected native session")
                    context_box = PersistentSandbox(
                        config["bundle"],
                        config["bundle"]["payload_sha256"],
                        sdk,
                        wall_seconds=660,
                        rpc_seconds=30,
                    )
                    native = context_box.mcp()
                    context = {
                        "box": context_box,
                        "native": native,
                        "connection": connection,
                    }
                    contexts.append(context)
                    current_process = native

                    def worker(
                        connection=connection,
                        reader=reader,
                        native=native,
                        context=context,
                    ):
                        try:
                            with connection, reader:
                                while line := reader.readline(1024**2 + 1):
                                    if len(line) > 1024**2 or not line.endswith(b"\n"):
                                        raise RuntimeError("Unbounded native RPC")
                                    request = json.loads(line)
                                    with lock:
                                        if request["method"] == "tools/call":
                                            if (
                                                selected[0] is not None
                                                and selected[0] is not context
                                            ):
                                                raise RuntimeError(
                                                    "Multiple semantic contexts; no authority guessing"
                                                )
                                            selected[0] = context
                                            dispatches[0] += 1
                                            if dispatches[0] > 80:
                                                answer = {
                                                    "isError": True,
                                                    "content": [
                                                        {
                                                            "type": "text",
                                                            "text": "MODEL_TOOL_LIMIT_NO_DISPATCH",
                                                        }
                                                    ],
                                                }
                                                connection.sendall(
                                                    json.dumps(
                                                        {
                                                            "jsonrpc": "2.0",
                                                            "id": request["id"],
                                                            "result": answer,
                                                        }
                                                    ).encode()
                                                    + b"\n"
                                                )
                                                record["calls"].append(
                                                    {
                                                        "request": request,
                                                        "response": answer,
                                                        "withheld": True,
                                                    }
                                                )
                                                continue
                                        if "id" not in request:
                                            native.notify(
                                                request["method"], request.get("params")
                                            )
                                            continue
                                        try:
                                            answer = native.request(
                                                request["method"],
                                                request.get("params"),
                                                optional_discovery=True,
                                            )
                                            output = {
                                                "jsonrpc": "2.0",
                                                "id": request["id"],
                                                "result": answer,
                                            }
                                        except UnsupportedDiscovery as exc:
                                            answer = {
                                                "optional_discovery_error": exc.error
                                            }
                                            output = {
                                                "jsonrpc": "2.0",
                                                "id": request["id"],
                                                "error": exc.error,
                                            }
                                        record["calls"].append(
                                            {"request": request, "response": answer}
                                        )
                                    connection.sendall(
                                        json.dumps(output).encode() + b"\n"
                                    )
                        except BaseException as exc:
                            record["worker_error"] = str(exc)

                    thread = threading.Thread(target=worker, daemon=True)
                    thread.start()
                    workers.append(thread)
                    continue
                with connection, reader, lock:
                    active_box = selected[0]["box"] if selected[0] else box
                    action = header.get("action")
                    args = header.get("arguments", {})
                    if role == "control" and action != "snapshot":
                        dispatches[0] += 1
                        if dispatches[0] > 80:
                            connection.sendall(
                                b'{"error":"MODEL_TOOL_LIMIT_NO_DISPATCH"}\n'
                            )
                            continue
                    if role == "stop":
                        stop = True
                        for context in contexts:
                            try:
                                context["connection"].shutdown(socket.SHUT_RD)
                            except OSError:
                                pass
                        answer = {"stopped": True}
                    elif role != "control":
                        raise RuntimeError("Unknown role")
                    elif action == "snapshot":
                        answer = {
                            "files": {
                                p: base64.b64encode(v).decode()
                                for p, v in files(active_box).items()
                            }
                        }
                    elif action in ("check", "test"):
                        checked = evaluate(
                            files(active_box), sdk, config["vectors"], action == "check"
                        )
                        # No vectors, assertion source, expected values or evaluator implementation
                        # travel back to the model. Ordinary compiler diagnostics are public.
                        answer = {
                            "status": checked["status"],
                            "check": checked.get("check"),
                        }
                        if action == "test":
                            answer["independent_behavior_pass"] = (
                                checked["status"] == "PASS"
                            )
                        record["calls"].append(
                            {"action": action, "evaluation": checked}
                        )
                    elif action == "finish":
                        answer = {"finished": True}
                    elif action == "doc" and config["arm"] == "N":
                        name = args.get("path")
                        answer = (
                            {"content": config["docs"][name]}
                            if name in config["docs"]
                            else {"error": "DOC_PATH_NOT_ALLOWED"}
                        )
                    elif side and action in (
                        ("read", "edit") if config["arm"] == "T" else ("read", "aep")
                    ):
                        answer = side.call(action, args)
                        record["calls"].append(
                            {"action": action, "arguments": args, "response": answer}
                        )
                    elif (
                        action == "read"
                        and config["arm"] == "N"
                        and args.get("path") in source_initial
                    ):
                        answer = {"content": files(active_box)[args["path"]].decode()}
                    else:
                        answer = {"error": "CONDITION_ACTION_NOT_ALLOWED"}
                    if "worker_error" in record:
                        raise RuntimeError(record["worker_error"])
                    connection.sendall(json.dumps(answer).encode() + b"\n")
            for thread in workers:
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("Native relay close unconfirmed")
            for context in contexts:
                context["native"].close()
            if side:
                side.close()
            active_box = selected[0]["box"] if selected[0] else box
            record["final_files"] = {
                p: base64.b64encode(v).decode() for p, v in files(active_box).items()
            }
            # An invalid text candidate may fail transaction creation; do not
            # turn that ordinary compiler failure into a common host defect.
            try:
                record["final_authority"] = inspect_authority(active_box)
            except Exception as exc:
                record["final_authority"] = {"unreadable": type(exc).__name__}
            # Final independent evaluation has no candidate-process access to expectations.
            record["final"] = evaluate(files(active_box), sdk, config["vectors"])
            record["status"] = "CLOSED"
    except BaseException as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        for context in contexts:
            context["box"].close()
        box.close()
        Path(config["evidence"]).write_text(json.dumps(record, indent=2))


def control(path, action, arguments):
    address = json.loads(path.read_text())["socket"]
    with socket.socket(socket.AF_UNIX) as sock:
        sock.connect(address)
        sock.sendall(
            json.dumps(
                {
                    "role": "stop" if action == "stop" else "control",
                    "action": action,
                    "arguments": arguments,
                }
            ).encode()
            + b"\n"
        )
        with sock.makefile("rb") as stream:
            result = stream.readline(8 * 1024**2 + 1)
            if not result.endswith(b"\n") or len(result) > 8 * 1024**2:
                raise RuntimeError("Missing/unbounded control response")
            return json.loads(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--role", choices=("server", "mcp", "control"), default="mcp")
    args = parser.parse_args()
    if args.role == "server":
        serve(args.config)
    elif args.role == "mcp":
        relay(args.config, "mcp")
    else:
        p = json.loads(sys.stdin.read(1024**2))
        print(json.dumps(control(args.config, p["action"], p["arguments"])))
