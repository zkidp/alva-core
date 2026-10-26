"""P23: real native MCP, same Linux boundary, no models or old pilot replay."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git
from integrations.benchmark_runtime_v2.persistent import Closed, PersistentSandbox
from integrations.benchmark_runtime_v2.persistent import NativeMCP, _Process
from integrations.benchmark_runtime_v2.sandbox import SDK, Unsupported

BASE = "6a0d238159b1f5987b5c8fd1fa1b94aef984eb7f"
PATHS = ["tests/project/alva.toml", "tests/project/src/app.alva", "tests/project/src/model.alva"]
PROJECT = "/work/project/tests/project"


def initialize(mcp):
    answer = mcp.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                      "clientInfo": {"name": "p23-zero-model", "version": "1"}})
    assert answer["protocolVersion"] == "2025-11-25", answer
    mcp.notify("notifications/initialized")


def structured(result):
    assert not result.get("isError"), result
    value = result["structuredContent"]
    assert json.loads(result["content"][0]["text"]) == value
    return value


def run(args):
    record = {"status": "FAIL", "generation_calls": 0, "input_token_calls": 0,
              "platform": sys.platform, "base": BASE, "rows": [], "rpc": []}
    if sys.platform != "linux":
        try:
            PersistentSandbox({}, "not-an-id")
        except Unsupported as exc:
            return {**record, "status": "UNSUPPORTED_FAIL_CLOSED", "reason": str(exc)}
        raise AssertionError("Non-Linux enabled")
    bundle = pack_git(args.repo, BASE, PATHS)
    record["input_bundle_sha256"] = bundle["payload_sha256"]
    sdk = SDK(args.alva.resolve(), args.toolchain.resolve(), args.registry.resolve())
    record["binary_sha256"] = hashlib.sha256(sdk.alva.read_bytes()).hexdigest()
    record["python"] = sys.version
    def workspace(**kw):
        return PersistentSandbox(bundle, bundle["payload_sha256"], sdk, **kw)

    with workspace() as box:
        record["rustc"] = box.run(["/sdk/toolchain/bin/rustc", "--version"])["stdout"].strip()
        record["cargo"] = box.run(["/sdk/toolchain/bin/cargo", "--version"])["stdout"].strip()
        with box.mcp() as mcp:
            initialize(mcp)
            tools = mcp.request("tools/list")["tools"]
            names = {t["name"] for t in tools}
            assert {"begin_transaction", "resolve_entity", "change_field", "commit_transaction"} <= names
            schema = next(t["inputSchema"] for t in tools if t["name"] == "change_field")
            assert "transaction_id" in schema["required"], schema
            record["tool_names"] = sorted(names)
            record["change_field_schema"] = schema
            tx = structured(mcp.tool("begin_transaction", {"project": PROJECT + "/alva.toml"}))["transaction_id"]
            record["first_transaction_id"] = tx
            def tool(operation, **arguments):
                result = structured(mcp.tool(operation, {"transaction_id": tx, **arguments}))
                record["rpc"].append({"tool": operation, "transaction_id": tx, "result": result})
                return result
            entity = tool("resolve_entity", name="demo.app.run", kind="function")["entity"]
            tool("applicable_operations", entity=entity)
            tool("describe_operation", name="change_field")
            tool("describe_construction", kind="field", include_candidates=True)
            body = tool("inspect_body", function="demo.app.run")["body"]
            literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
            assert literal, body
            tool("inspect_entity", entity=literal.group(1))
            # Wrong ID is a native ordinary tool failure, not a transport retry.
            wrong = mcp.tool("inspect_project", {"transaction_id": "not-active"})
            assert wrong["isError"] and "TRANSACTION_NOT_FOUND" in json.dumps(wrong), wrong
            tool("change_field", entity=literal.group(1), field="value", value="p23-stdio")
            assert tool("preview_semantic_diff")["diff"].strip()
            tool("check_transaction")
            tool("commit_transaction")
        record["rows"].append({"test": "initialize_schemas_persistent_transaction_commit", "status": "PASS"})
        with box.mcp() as fresh:
            initialize(fresh)
            tx2 = structured(fresh.tool("begin_transaction", {"project": PROJECT + "/alva.toml"}))["transaction_id"]
            body = structured(fresh.tool("inspect_body", {"transaction_id": tx2, "function": "demo.app.run"}))["body"]
            assert "p23-stdio" in body, body
            structured(fresh.tool("abort_transaction", {"transaction_id": tx2}))
            record["second_transaction_id"] = tx2
        record["rows"].append({"test": "new_process_reloads_committed_air", "status": "PASS"})
        driver = '''import pathlib,subprocess
def command(args):
 p=subprocess.run(args,capture_output=True,text=True)
 assert p.returncode==0,(args,p.stdout,p.stderr)
project=pathlib.Path("/work/project/tests/project")
for source in (project/"src").glob("*.alva"):
 assert source.read_bytes()==(pathlib.Path("/input/tests/project/src")/source.name).read_bytes()
assert (project/"alva-air/current").is_file()
command(["/sdk/alva","project","check",str(project/"alva.toml"),"--json"])
command(["/sdk/alva","project","build",str(project/"alva.toml"),"--out-dir","/work/generated"])
crate=pathlib.Path("/work/generated/demo")
assert any("p23-stdio" in p.read_text() for p in (crate/"src").rglob("*.rs"))
with (crate/"src/lib.rs").open("a") as f:
 f.write('#[test] fn p23_independent_behavior(){assert_eq!(demo_app::run(),6); let m=demo_model::make_meta("x".into(),9,"e".into()); assert_eq!(demo_model::size_of(demo_model::touch_size(m)),10);}')
command(["/sdk/toolchain/bin/cargo","test","--offline","--manifest-path",str(crate/"Cargo.toml")])
print("INDEPENDENT_BEHAVIOR_PASS; SOURCE_UNCHANGED; AIR_USED")
'''
        result = box.run(["/usr/bin/python3", "-I", "-c", driver])
        assert "INDEPENDENT_BEHAVIOR_PASS" in result["stdout"], result
        record["rows"].append({"test": "authority_build_independent_behavior_inside_boundary", "status": "PASS", **result})

    with tempfile.TemporaryDirectory(prefix="p23-host-only-") as directory:
        outside = Path(directory)
        sentinels = [outside / name for name in ("reference", "other-slot", "user-private")]
        for path in sentinels:
            path.write_bytes(b"synthetic-private")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0)); listener.listen()
            port = listener.getsockname()[1]
            with workspace() as box:
                # Actual MCP path accesses, not a fake host/path helper.
                with box.mcp() as mcp:
                    initialize(mcp)
                    for target in sentinels:
                        answer = mcp.tool("begin_transaction", {"project": str(target)})
                        assert answer["isError"], answer
                probe = '''import ctypes,errno,json,pathlib,socket,subprocess
rows=[]
for name in TARGETS:
 for kind in ("read","write"):
  try:
   p=pathlib.Path(name)
   p.read_bytes() if kind=="read" else p.write_bytes(b"bad")
  except OSError as e:rows.append({"kind":kind,"errno":e.errno})
  else:raise AssertionError("host access")
for name in ("/escaped","/input/tests/project/alva.toml","/sdk/alva"):
 try:pathlib.Path(name).write_bytes(b"bad")
 except OSError as e:rows.append({"kind":"readonly","errno":e.errno})
 else:raise AssertionError("escaped write")
for host,port in [("127.0.0.1",PORT),("192.0.2.1",9)]:
 with socket.socket() as s:
  s.settimeout(.2)
  try:s.connect((host,port))
  except OSError as e:rows.append({"kind":"network","errno":e.errno})
  else:raise AssertionError("network")
pathlib.Path("/work/mount-test").mkdir()
libc=ctypes.CDLL(None,use_errno=True)
assert libc.mount(b"tmpfs",b"/work/mount-test",b"tmpfs",0,None)==-1
assert ctypes.get_errno()==errno.EPERM
rows.append({"kind":"mount","errno":ctypes.get_errno()})
assert not pathlib.Path("/home").exists() and not pathlib.Path("/mnt").exists()
print(json.dumps(rows))
'''.replace("TARGETS", repr([str(p) for p in sentinels])).replace("PORT", str(port))
                result = box.run(["/usr/bin/python3", "-I", "-c", probe])
                record["rows"].append({"test": "native_mcp_paths_and_os_read_write_network_mount", "status": "PASS", "events": json.loads(result["stdout"])})
        assert all(p.read_bytes() == b"synthetic-private" for p in sentinels)

    for label, argv, limits in [
        ("abnormal_exit", ["/usr/bin/python3", "-c", "raise SystemExit(7)"], {}),
        ("wall_limit", ["/usr/bin/python3", "-c", "while True: pass"], {"wall_seconds": .3}),
        ("output_limit", ["/usr/bin/python3", "-c", "print('x'*10000)"], {"output_limit": 1024}),
    ]:
        with workspace(**limits) as box:
            try:
                box.run(argv)
            except Closed as exc:
                record["rows"].append({"test": label, "status": "PASS", "failure": str(exc)})
            else:
                raise AssertionError("failure accepted: " + label)
            try:
                box.mcp()
            except Closed:
                pass
            else:
                raise AssertionError("poisoned workspace reused")
    with workspace() as box:
        mcp = box.mcp()
        initialize(mcp)
        try:
            mcp.request("not/a/method")
        except Closed as exc:
            record["rows"].append({"test": "rpc_failure_terminates_no_replay", "status": "PASS", "failure": str(exc)})
        else:
            raise AssertionError("RPC error usable")
    with workspace(wall_seconds=1) as box:
        mcp = box.mcp()
        initialize(mcp)
        time.sleep(1.1)
        assert mcp.process.p.poll() is not None, "idle wall watchdog did not terminate"
        try:
            mcp.request("tools/list")
        except Closed:
            record["rows"].append({"test": "idle_session_wall_watchdog", "status": "PASS"})
        else:
            raise AssertionError("expired session reused")
    # Synthetic faulty peers run INSIDE the same OS boundary. These rows
    # validate transport failure paths, not native ALVA semantic capabilities.
    for label, script in [
        ("malformed_json", 'input();print("not-json",flush=True);input()'),
        ("wrong_rpc_id", 'input();print(\'{"jsonrpc":"2.0","id":99,"result":{}}\',flush=True);input()'),
        ("early_eof", 'input();raise SystemExit(3)'),
        ("rpc_timeout", 'input();import time;time.sleep(10)'),
    ]:
        with workspace(rpc_seconds=.2) as box:
            peer = NativeMCP.__new__(NativeMCP)
            peer.owner, peer.next_id, peer.closed = box, 0, False
            peer.lock = threading.RLock()
            peer.process = _Process(box, ["/usr/bin/python3", "-c", script])
            try:
                peer.request("initialize")
            except Closed as exc:
                assert peer.process.closed and peer.process.p.poll() is not None
                assert box.poisoned
                record["rows"].append({"test": label, "status": "PASS", "failure": str(exc)[:500]})
            else:
                raise AssertionError("faulty peer accepted")
    # Deliberate cleanup confirmation failure: no usable result, no retry.
    # Restore wait only to clean up this deterministic test's real process.
    import subprocess
    with workspace() as box:
        proc = _Process(box, ["/usr/bin/python3", "-c", "import time;time.sleep(10)"])
        wait = proc.p.wait
        def uncertain(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("synthetic-cleanup", 5)
        proc.p.wait = uncertain
        try:
            box._fail(Closed("synthetic cleanup confirmation failure"))
        except Closed as exc:
            assert "TERMINATION_UNCONFIRMED" in str(exc)
            assert box.poisoned
            record["rows"].append({"test": "cleanup_unconfirmed_no_usable_result", "status": "PASS", "scope": "injected wait failure; not an unkillable-process claim"})
        else:
            raise AssertionError("unknown cleanup accepted")
        finally:
            proc.p.wait = wait
            wait(timeout=5)
    record["status"] = "PASS"
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--alva", type=Path)
    parser.add_argument("--toolchain", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        record = run(args)
    except Unsupported as exc:
        record = {"status": "UNSUPPORTED_FAIL_CLOSED", "reason": str(exc), "generation_calls": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": record["status"], "rows": len(record.get("rows", []))}))
    raise SystemExit(0 if record["status"] == "PASS" else 2)
