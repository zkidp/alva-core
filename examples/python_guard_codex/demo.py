#!/usr/bin/env python3
"""Real Codex app-server consumer. Default: no model; --model-demo: one bounded turn.

Reuses the existing app-server test client, not another agent loop or MCP server.
No credentials, raw messages or reasoning are written to the public result.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/integrations"))
from codex_native_test import AppServer
from integrations.python_guard import policy_identity
from integrations.python_guard.guard import canonical
from integrations.python_guard_codex import CandidateSession, TOOLS


SKILL = ROOT / "integrations/skills/python-guard"


def make_session(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    project = directory / "source"
    shutil.copytree(Path(__file__).parent / "project", project, ignore=shutil.ignore_patterns("__pycache__"))
    scratch = directory / "check-scratch"
    scratch.mkdir()
    policy = {"schema": 1, "project_root": str(project), "scratch_root": str(scratch),
        "files": ["cart.py", "tests/test_cart.py"], "editable": ["cart.py"], "excluded": {},
        "scratch_outputs": ["__pycache__", "tests/__pycache__"], "python": sys.executable,
        "trusted_project": True, "environment": {},
        "checks": [{"id": "public-tests", "argv": ["$PYTHON", "-I", "-m", "unittest", "discover", "-s", "tests"]}],
        "limits": {"max_files": 20, "max_source_bytes": 100000, "max_patch_bytes": 20000,
                   "wall_seconds": 30, "output_bytes_per_stream": 8192, "max_command_invocations": 8,
                   "max_direct_processes": 1, "address_space_bytes": None, "cpu_seconds": None}}
    policy_file = directory / "approved-policy.json"
    policy_file.write_bytes(canonical(policy))
    return CandidateSession.prepare(directory / "host-control", policy_file, directory / "candidate", policy_identity(policy_file))


def sandbox_policy(candidate: Path):
    return {"type": "workspaceWrite", "writableRoots": [str(candidate)], "networkAccess": False,
            "excludeTmpdirEnvVar": True, "excludeSlashTmp": True}


def sandbox_probe(host, session):
    """Try actual writes with the same sandbox used for the model turn, no model."""
    protected = [session.policy_file, session.control / "session.json",
                 Path(session.snapshot["project_root"]) / "cart.py"]
    # Also refuse creation next to the trusted adapter/verifier, not just policy.
    outside = ROOT / "integrations/python_guard_codex/p2-write-probe.tmp"
    before = {p: p.read_bytes() for p in protected}
    program = (
        "import errno,json,pathlib,sys; results=[]\n"
        "for i,name in enumerate(sys.argv[1:]):\n"
        " p=pathlib.Path(name)\n"
        " try:\n"
        "  with p.open('r+b' if i < 3 else 'xb') as f: pass\n"
        "  results.append(False)\n"
        " except OSError as exc:\n"
        "  if exc.errno not in (errno.EACCES, errno.EPERM, errno.EROFS): raise\n"
        "  results.append(True)\n"
        "print(json.dumps(results))\n"
    )
    result = host.request("command/exec", {"command": [sys.executable, "-I", "-c", program,
        *(str(p) for p in protected), str(outside)], "cwd": str(session.candidate),
        "sandboxPolicy": sandbox_policy(session.candidate), "timeoutMs": 30000})
    assert result["exitCode"] == 0, result
    denied = json.loads(result["stdout"].strip())
    assert denied == [True] * 4, ("sandbox did not protect source/policy/control/verifier; do not start model", denied)
    assert before == {p: p.read_bytes() for p in protected}
    assert not outside.exists()
    return {"source_write_denied": denied[2], "policy_write_denied": denied[0],
            "control_write_denied": denied[1], "verifier_directory_write_denied": denied[3]}


def run(directory, codex, model_demo=False, model=None):
    session = make_session(directory)
    original = {p.relative_to(Path(session.snapshot["project_root"])).as_posix(): p.read_bytes()
                for p in Path(session.snapshot["project_root"]).rglob("*") if p.is_file()}
    env = dict(os.environ)
    # Prevent inherited desktop workspace hints from adding another writable root.
    for key in ("CLAUDE_PROJECT_DIR", "CODEX_PERMISSION_PROFILE"):
        env.pop(key, None)
    if not model_demo:
        env["CODEX_HOME"] = str(directory / "isolated-codex-home")
        install = Path(env["CODEX_HOME"]) / "skills/python-guard"
        shutil.copytree(SKILL, install)
    version = subprocess.run([codex, "--version"], capture_output=True, text=True, timeout=15, check=True).stdout.strip()
    config = ["-c", 'sandbox_mode="workspace-write"', "-c", 'approval_policy="never"',
              "-c", "features.plugins=false"]
    if os.name == "nt":
        config += ["-c", 'windows.sandbox="unelevated"']
    host = AppServer(codex, env, session.candidate, extra_args=config)
    started = time.monotonic()
    result = {"mode": "MODEL_BEHAVIOR_DEMO" if model_demo else "ENGINEERING_HOST_CALLS",
              "codex": version, "model_turns_started": 0, "raw_transcripts_saved": False,
              "automatic_source_apply": False, "automatic_git_commit": False}
    try:
        host.request("initialize", {"clientInfo": {"name": "python-guard-consumer", "version": "1"},
            "capabilities": {"experimentalApi": True}})
        host.send({"method": "initialized", "params": {}})
        result["sandbox"] = sandbox_probe(host, session)
        skills = host.request("skills/list", {"cwds": [str(session.candidate)], "forceReload": True})
        discovered = [s for row in skills["data"] for s in row["skills"] if s["name"] == "python-guard" and s["enabled"]]
        if not model_demo:
            assert discovered, "isolated optional Skill not discovered by real Codex host"
            result["skill_discovered"] = True
            # Real host command mutates only the candidate; no toy FakeHost.
            changed = host.request("command/exec", {"command": [sys.executable, "-I", "-c",
                "from pathlib import Path; p=Path('cart.py'); p.write_bytes(p.read_bytes().replace(b'return sum(values)', b'return sum(values) + 0'))"],
                "cwd": str(session.candidate), "sandboxPolicy": sandbox_policy(session.candidate), "timeoutMs": 30000})
            assert changed["exitCode"] == 0, changed
            response = session.tool_call("guard_verify", {})
            assert response["success"], response
            report = json.loads(session.tool_call("guard_report", {})["contentItems"][0]["text"])
            assert report["checks_status"] == "FAIL" and report["applicability_status"] == "CURRENT", report
            assert report["candidate_matches_verified_patch"]
            result.update(engineering_result="PASS", expected_checks="FAIL", actual_checks=report["checks_status"],
                          applicability=report["applicability_status"], host_command_calls=2)
        else:
            params = {"cwd": str(session.candidate), "approvalPolicy": "never", "sandbox": "workspace-write",
                      "ephemeral": True, "dynamicTools": TOOLS,
                      "developerInstructions": "Use only this candidate workspace. The host owns policy, evidence and original source. Never apply or commit. Use the supplied python-guard Skill and host guard tools. Do not delegate."}
            if model:
                params["model"] = model
            thread = host.request("thread/start", params)
            thread_id = thread["thread"]["id"]
            result["resolved_model"] = thread.get("model")
            result["resolved_provider"] = thread.get("modelProvider")
            task = ("Use $python-guard to change cart.total(values): accept nonnegative integers (not bool), "
                    "raise TypeError for non-integers and ValueError for negative integers. Keep exact integer sums "
                    "and empty input = 0. Read the public tests. Edit cart.py only, then request guard_verify and "
                    "guard_report and report their checks/applicability. Do not change tests or original source. "
                    "Do not apply or commit. One bounded development demonstration, not an effectiveness experiment.")
            host.request("turn/start", {"threadId": thread_id, "input": [
                {"type": "skill", "name": "python-guard", "path": str(SKILL / "SKILL.md")},
                {"type": "text", "text": task}], "sandboxPolicy": sandbox_policy(session.candidate),
                "approvalPolicy": "never", "effort": "low"})
            result["model_turns_started"] = 1
            command_calls = guard_calls = 0
            seen = set()
            deadline = time.monotonic() + 240
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("240-second model demonstration deadline")
                try:
                    message = host.messages.get(timeout=min(5, deadline - time.monotonic()))
                except queue.Empty:
                    continue
                if message is None:
                    raise RuntimeError("Codex host exited before turn completion")
                if message.get("method") == "item/tool/call":
                    p = message["params"]
                    guard_calls += 1
                    if p["callId"] in seen or guard_calls > 4:
                        raise RuntimeError("duplicate dynamic call or four-call Guard limit")
                    seen.add(p["callId"])
                    host.send({"id": message["id"], "result": session.tool_call(p["tool"], p["arguments"])})
                elif "id" in message and "method" in message:
                    raise RuntimeError("unexpected host approval; no permission expansion")
                elif message.get("method") == "item/started":
                    item = message["params"]["item"]
                    if item["type"] in {"commandExecution", "fileChange"}:
                        command_calls += 1
                        if command_calls > 20:
                            raise RuntimeError("twenty local command/edit item limit")
                elif message.get("method") == "turn/completed":
                    result["turn_status"] = message["params"]["turn"]["status"]
                    break
            result.update(model_command_or_edit_items=command_calls, model_guard_calls=guard_calls)
            if (session.control / "last-verification.json").exists():
                report = session.report()
                result.update(checks_status=report["checks_status"], applicability_status=report["applicability_status"],
                              candidate_matches_verified_patch=report["candidate_matches_verified_patch"])
            else:
                result.update(checks_status="UNKNOWN", applicability_status="UNKNOWN", failure_reason="MODEL_DID_NOT_REQUEST_VERIFICATION")
    finally:
        host.close()
        after = {p.relative_to(Path(session.snapshot["project_root"])).as_posix(): p.read_bytes()
                 for p in Path(session.snapshot["project_root"]).rglob("*") if p.is_file()}
        assert original == after, "original source changed"
    result["source_unchanged"] = True
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--model-demo", action="store_true", help="explicitly authorize one real Codex model turn")
    parser.add_argument("--model", help="optional model override; default keeps the user's Codex model")
    parser.add_argument("--directory", type=Path, help="new local directory to retain source/candidate/evidence")
    args = parser.parse_args()
    assert args.codex, "Codex CLI required"
    if args.directory:
        result = run(args.directory.resolve(), args.codex, args.model_demo, args.model)
    else:
        # TemporaryDirectory creates a restrictive parent ACL on recent Windows
        # Python. Its restricted-token child cannot necessarily traverse it.
        # Create a normal, uniquely named host-owned directory instead.
        local = ROOT / ".local"
        local.mkdir(exist_ok=True)
        directory = local / ("guard-codex-demo-" + uuid.uuid4().hex)
        try:
            result = run(directory, args.codex, args.model_demo, args.model)
        finally:
            if directory.is_dir() and directory.parent.resolve() == local.resolve() and not directory.is_symlink():
                shutil.rmtree(directory)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
