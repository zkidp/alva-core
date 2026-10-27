"""Actual P23/Linux observer purity test on a non-task literal fixture.

No model, no HE41 implementation, no P25 witness. Also checks detached-node
exclusion and that the original check/commit/evaluator still work after reads.
"""
import argparse
import base64
import json
from pathlib import Path
import re
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective.service import files, evaluate, inspect_authority
from benchmarks.p28_optional_descriptor.observer import ObservedNative
from integrations.benchmark_runtime_v2.freeze import canonical, sha
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK


def fixture():
    source = {"alva.toml": b'[project]\nname="bench"\n[modules]\n"bench"="src/task.alva"\n',
              "src/task.alva": b'(module (name "bench") (version "0.1.0") (export solve)\n(fn solve (params (param x (prim i64))) (returns (prim string)) (pure) (body (string "a"))))\n'}
    payload = {"schema": "alva-benchmark-freeze/v2", "byte_policy": "exact-git-blob-no-normalization",
               "entries": [{"path": p, "length": len(v), "sha256": sha(v),
                            "base64": base64.b64encode(v).decode()} for p, v in source.items()]}
    return {"payload": payload, "payload_sha256": sha(canonical(payload))}


def initialize(native):
    native.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
        "clientInfo": {"name": "p28-zero-model-observer", "version": "1"}})
    native.notify("notifications/initialized")


def run(args):
    bundle = fixture()
    sdk = SDK(*(Path(getattr(args, k)).resolve() for k in ("alva", "toolchain", "registry")))
    observations = []
    with PersistentSandbox(bundle, bundle["payload_sha256"], sdk) as box:
        initial_files = files(box)
        with ObservedNative(box.mcp(), observations.append) as native:
            initialize(native)
            def call(operation, **arguments):
                answer = native.request("tools/call", {"name": operation, "arguments": arguments,
                    "_meta": {"callId": "zero-" + str(len(observations)) + "-" + operation}})
                assert not answer.get("isError"), answer
                return answer["structuredContent"]
            tx = call("begin_transaction", project="/work/project/alva.toml")["transaction_id"]
            def read(name, **kw):
                return native.inner.tool(name, {"transaction_id": tx, **kw})["structuredContent"]
            baseline = observations[0]["body_sha256"]
            assert read("inspect_project")
            before = {"project": read("inspect_project"), "diff": read("preview_semantic_diff"), "files": files(box),
                      "body": read("inspect_body", function="bench.solve")}
            native.capture(tx, "purity-probe", "trusted_read_only_probe")
            native.capture(tx, "purity-probe-repeat", "trusted_read_only_probe")
            after = {"project": read("inspect_project"), "diff": read("preview_semantic_diff"), "files": files(box),
                     "body": read("inspect_body", function="bench.solve")}
            assert before == after, "Observer changed staged graph/revision/diff/authority/source"
            assert all(o["body_sha256"] == baseline for o in observations)
            call("create_reference", transaction_id=tx, name="x")
            assert not observations[-1]["changed_from_transaction_start"], "Detached node credited"
            body = read("inspect_body", function="bench.solve")["body"]
            literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
            assert literal, body
            call("change_field", transaction_id=tx, entity=literal.group(1), field="value", value="b")
            assert observations[-1]["changed_from_transaction_start"]
            assert files(box) == initial_files, "Staging/observer published authority before commit"
            checked = call("check_transaction", transaction_id=tx)
            call("commit_transaction", transaction_id=tx)
        authority = inspect_authority(box)  # fresh process, not same transaction
        assert authority["body_sha256"] != baseline
        # Only this non-task fixture expects "b"; never model-visible.
        final = evaluate(files(box), sdk, [[0, "b"], [10, "b"]])
        assert final["status"] == "PASS", final
    return {"status": "PASS", "platform": "linux", "generation_calls": 0, "input_token_calls": 0,
            "fixture_sha256": bundle["payload_sha256"], "same_transaction_reads": "PASS",
            "staged_project_diff_source_authority_unchanged_by_reads": True,
            "detached_node_excluded": True, "connected_change_detected": True,
            "no_publication_before_commit": True, "check_commit_fresh_reload": "PASS",
            "isolated_compile_behavior": "PASS", "observer_calls": len(observations),
            "check_result_sha256": sha(canonical(checked)), "model_feedback_rewritten": False}


def relay_probe(ready):
    """Synthetic tool-call envelopes through the real P28/P26 service worker."""
    address = json.loads(Path(ready).read_text())["socket"]
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(30)
        sock.connect(address)
        sock.sendall(b'{"role":"mcp"}\n')
        stream = sock.makefile("rb")
        ordinal = 0
        def request(method, params):
            nonlocal ordinal
            ordinal += 1
            sock.sendall((json.dumps({"jsonrpc": "2.0", "id": ordinal, "method": method, "params": params}) + "\n").encode())
            answer = json.loads(stream.readline(1024**2))
            assert answer["id"] == ordinal and "error" not in answer, answer
            return answer["result"]
        request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "p28-synthetic-relay", "version": "1"}})
        begun = request("tools/call", {"name": "begin_transaction", "arguments": {"project": "/work/project/alva.toml"},
            "_meta": {"callId": "synthetic-begin"}})
        assert not begun.get("isError"), begun
        tx = begun["structuredContent"]["transaction_id"]
        body = request("tools/call", {"name": "inspect_body", "arguments": {"transaction_id": tx, "function": "bench.solve"},
            "_meta": {"callId": "synthetic-inspect"}})
        aborted = request("tools/call", {"name": "abort_transaction", "arguments": {"transaction_id": tx},
            "_meta": {"callId": "synthetic-abort"}})
        assert not body.get("isError") and not aborted.get("isError")
        stream.close()
    return {"status": "PASS", "body_sha256": sha(body["structuredContent"]["body"].encode()),
            "native_model_envelopes": 3, "generation_calls": 0}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--relay-ready")
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k)
    args = p.parse_args()
    print(json.dumps(relay_probe(args.relay_ready) if args.relay_ready else run(args)))
