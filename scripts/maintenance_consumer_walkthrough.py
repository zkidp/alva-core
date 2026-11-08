"""Scripted public consumer of the unchanged three-action MCP Host.

Not an Agent Harness, model trial, external-user study or business deployment.
Only new disposable demo directories are modified. Candidate execution and AIR
projection use the existing Linux OS sandbox, with no host execution fallback.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.sandbox import SDK, LinuxSandbox
from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
from integrations.codex.maintenance_host import AgentProcess, sha, snapshot_digest

SAMPLE = ROOT / "examples/maintenance_packing"
INPUTS = ("alva.toml", "src/model.alva", "src/app.alva")
POLICY = {"authorized_functions": ["model.packs_required"], "modules": {
    "model": {"functions": ["packs_required", "full_pack_units"], "types": []},
    "app": {"functions": ["order_packs"], "types": []}}}
# Public illustrative edits, not model outputs or benchmark reference patches.
WRONG = "(body (+ (/ (ref units) (ref pack_size)) (int 1)))"
CORRECT = """(body (+ (/ (ref units) (ref pack_size))
    (if (> (- (ref units) (* (/ (ref units) (ref pack_size)) (ref pack_size))) (int 0))
        (int 1) (int 0))))"""


class Client:
    """Small independent JSON-RPC consumer, not a replacement Host."""
    def __init__(self, config, operator):
        self.error_file = (operator / "server.stderr.log").open("wb")
        self.process = subprocess.Popen([sys.executable, "-m", "integrations.codex.maintenance_host",
            "--config", str(config)], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.error_file)
        self.lines, self.events = queue.Queue(), []
        def read():
            while line := self.process.stdout.readline(2 * 1024**2 + 1):
                self.lines.put(line)
            self.lines.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        self.seq = 0

    def request(self, method, params=None):
        self.seq += 1
        request = {"jsonrpc": "2.0", "id": self.seq, "method": method, "params": params or {}}
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        self.process.stdin.flush()
        try:
            line = self.lines.get(timeout=180)
        except queue.Empty:
            raise RuntimeError("DEMO_RPC_TIMEOUT_NO_RETRY") from None
        if not line or len(line) > 2 * 1024**2:
            raise RuntimeError("DEMO_INVALID_OR_CLOSED_STREAM")
        response = json.loads(line)
        self.events.append({"request": request, "response": response})
        if response.get("id") != self.seq or "error" in response:
            raise RuntimeError("DEMO_RPC_ERROR")
        return response["result"]

    def tool(self, name, arguments):
        envelope = self.request("tools/call", {"name": name, "arguments": arguments})
        return envelope["structuredContent"]

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
            raise RuntimeError("DEMO_HOST_DID_NOT_CLOSE") from None
        finally:
            self.reader.join(timeout=3)
            self.process.stdout.close()
            self.error_file.close()
        if self.reader.is_alive() or self.process.returncode:
            raise RuntimeError("DEMO_HOST_ABNORMAL_CLOSE")


def source_files(project):
    return {p: (project / p).read_bytes() for p in INPUTS}


def authority_files(project):
    current = (project / "alva-air/current").read_bytes()
    lines = current.decode("utf-8").splitlines()
    if len(lines) != 2 or not re.fullmatch(r"[1-9][0-9]*", lines[0]) or not re.fullmatch(r"[0-9a-f]{64}", lines[1]):
        raise RuntimeError("DEMO_INVALID_CURRENT")
    name = "alva-air/gen-" + lines[0] + ".air"
    return {"alva-air/current": current, name: (project / name).read_bytes()}, lines[1], name


def read_authority(binary, manifest):
    reader = AgentProcess(binary)
    try:
        def call(name, **args):
            response = reader.request("tools/call", {"name": name, "arguments": args})
            if response.get("isError"):
                raise RuntimeError("DEMO_FRESH_READ_REJECTED")
            return response["structuredContent"]
        begun = call("begin_transaction", project=str(manifest))
        info = call("read_function", transaction_id=begun["transaction_id"], function="model.packs_required")
        call("abort_transaction", transaction_id=begun["transaction_id"])
        return begun["project_revision"], info
    finally:
        reader.close()


def save_files(root, files):
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def projected_sources(sdk, snapshot, air_name):
    # All candidate AIR parsing/projection remains inside the existing sandbox.
    script = r'''
import base64,json,pathlib,subprocess
p=subprocess.run(['/sdk/alva','air','import',AIR,'--out-dir','/work/projection'],capture_output=True,text=True)
if p.returncode: raise RuntimeError('AIR_IMPORT_FAILED:'+p.stderr[-1000:])
root=pathlib.Path('/work/projection')
if sorted(x.name for x in root.iterdir())!=['app.alva','model.alva']:raise RuntimeError('UNEXPECTED_PROJECTION_FILES')
print(json.dumps({'src/'+x.name:base64.b64encode(x.read_bytes()).decode() for x in sorted(root.iterdir())}))
'''
    execution = LinuxSandbox(sdk).run(snapshot, ["/usr/bin/python3", "-I", "-c", "AIR=" + repr(air_name) + "\n" + script])
    if execution["status"] != "EXECUTED" or execution["exit"] != 0:
        raise RuntimeError("DEMO_ISOLATED_PROJECTION_FAILED")
    values = json.loads(execution["stdout"]["text"])
    if set(values) != {"src/model.alva", "src/app.alva"}:
        raise RuntimeError("DEMO_UNEXPECTED_PROJECTED_PATH")
    return {"alva.toml": snapshot["alva.toml"], **{p: base64.b64decode(b, validate=True) for p, b in values.items()}}


def walkthrough(sdk, output):
    # Platform/namespace/SDK support is checked before creating any workspace.
    LinuxSandbox(sdk)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project, operator = output / "project", output / "operator"
    operator.mkdir()
    original = {p: (SAMPLE / p).read_bytes() for p in INPUTS}
    save_files(project, original)
    assertions = (SAMPLE / "operator/checks.rs").read_text(encoding="utf-8")
    (operator / "checks.rs").write_text(assertions, encoding="utf-8")
    config = {"alva": str(sdk.alva), "toolchain": str(sdk.rust_toolchain), "registry": str(sdk.registry),
              "project": str(project / "alva.toml"), "inputs": list(INPUTS), "crate": "packing_demo",
              "assertions": assertions, "policy": POLICY}
    config_path = operator / "host.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    evaluator = LinuxProjectEvaluator(sdk, "packing_demo", assertions=assertions)
    report = {"status": "RUNNING", "classification": "SCRIPTED_AUTHOR_CONSUMER_WALKTHROUGH_NOT_AGENT_STUDY",
              "model_generation_calls": 0, "input_token_api_calls": 0,
              "source_before_sha256": snapshot_digest(original), "phase": "baseline", "steps": []}
    client = None
    try:
        initial_revision, initial_info = read_authority(sdk.alva, project / "alva.toml")
        baseline = evaluator(original, initial_revision)
        (operator / "baseline-tests.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        assert baseline["checks"] == {"check": "PASS", "build": "PASS", "test": "FAIL"}, baseline
        report["baseline_checks"] = baseline["checks"]
        report["phase"] = "stdio_host"
        client = Client(config_path, operator)
        client.request("initialize")
        tools = client.request("tools/list")["tools"]
        assert [t["name"] for t in tools] == ["read_target", "prepare_change", "publish_change"]
        def tool(name, args, expected):
            result = client.tool(name, args)
            report["steps"].append({"tool": name, "status": result["status"], "reason": result.get("reason")})
            assert result["status"] == expected, result
            return result
        view = tool("read_target", {"function": "model.packs_required"}, "READY")
        tool("prepare_change", {"view_id": view["view_id"], "body": "(body (int ))"}, "REJECTED")
        wrong = tool("prepare_change", {"view_id": view["view_id"], "body": WRONG}, "VALIDATION_FAILED")
        assert wrong["checks"] == {"check": "PASS", "build": "PASS", "test": "FAIL"}, wrong
        assert not (project / "alva-air/current").exists()
        assert source_files(project) == original
        proposal = tool("prepare_change", {"view_id": view["view_id"], "body": CORRECT}, "PREPARED")
        assert proposal["checks"] == {"check": "PASS", "build": "PASS", "test": "PASS"}
        assert not (project / "alva-air/current").exists()
        publication = tool("publish_change", {"proposal_id": proposal["proposal_id"]}, "PUBLISHED")
        assert publication["fresh_authority_matches"] and publication["scope"] == "SCOPE_ALLOWED"
        tool("publish_change", {"proposal_id": proposal["proposal_id"]}, "REJECTED")
        fresh = tool("read_target", {"function": "model.packs_required"}, "READY")
        assert fresh["body"] != view["body"]
        client.close()
        (operator / "stdio-calls.json").write_text(json.dumps(client.events, indent=2), encoding="utf-8")
        client = None
        report["phase"] = "handoff"
        assert source_files(project) == original
        air, published_revision, air_name = authority_files(project)
        assert published_revision == publication["revision"]
        reread_revision, reread_info = read_authority(sdk.alva, project / "alva.toml")
        assert reread_revision == published_revision and reread_info["body"] == fresh["body"]
        snapshot = {**original, **air}
        final = evaluator(snapshot, published_revision)
        assert final["status"] == "PASS", final
        (operator / "final-air-tests.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
        save_files(output / "handoff-air", snapshot)
        projected = projected_sources(sdk, snapshot, air_name)
        save_files(output / "handoff-source", projected)
        projection_revision, projected_info = read_authority(sdk.alva, output / "handoff-source/alva.toml")
        assert projected_info["body"] == reread_info["body"]
        projected_result = evaluator(projected, projection_revision)
        assert projected_result["status"] == "PASS", projected_result
        assert not (output / "handoff-source/alva-air").exists()
        (operator / "projected-source-tests.json").write_text(json.dumps(projected_result, indent=2), encoding="utf-8")
        assert source_files(project) == original
        report.update(status="PASS", phase="complete", source_files_unchanged=True,
            final_checks=final["checks"], projected_checks=projected_result["checks"],
            initial_revision=initial_revision, published_revision=published_revision,
            projected_revision=projection_revision,
            initial_body_revision=initial_info["body_revision"], final_body_revision=reread_info["body_revision"],
            air_sha256=sha(air[air_name]), tested_final_snapshot_sha256=snapshot_digest(snapshot),
            source_only_snapshot_sha256=snapshot_digest(projected),
            protected_scope="SCOPE_ALLOWED; fixed component function bodies only",
            disclaimer="No external user or model was observed; no economy or general correctness claim")
    except Exception as exc:
        report.update(status="FAIL", error=type(exc).__name__ + ":" + str(exc)[:2000])
        raise
    finally:
        try:
            if client:
                try:
                    client.close()
                finally:
                    (operator / "stdio-calls.json").write_text(json.dumps(client.events, indent=2), encoding="utf-8")
        finally:
            (output / "REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alva", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Must not exist; never overwrite a previous walkthrough")
    args = parser.parse_args()
    sdk = SDK(args.alva.resolve(), args.toolchain.resolve(), args.registry.resolve())
    result = walkthrough(sdk, args.output)
    print(json.dumps(result, indent=2))
