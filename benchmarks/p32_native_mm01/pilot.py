"""One prospective MM01-S slot; P30 controller/service plus P31 scoped policy.

No historical candidates/transcripts consumed. prepare uses no model; run
requires a pushed, clean freeze and an exclusive study-wide attempt ledger.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import time
import tomllib
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.mm01_pilot import pilot as mm
from integrations.codex.native_commit_authorization import scoped_server, host_options

old = mm.old
save, sha = mm.save, mm.sha
HERE = Path(__file__).resolve().parent
BASE = "c9aecd0bfbbc6b7444d50bf85ca1558ae969d3db"
BRANCH = "codex/p32-native-mm01-maintenance"
P30 = ROOT / "benchmarks/mm01_pilot/FREEZE.json"
CONFIG = mm.CONFIG


def authorization(slot):
    return scoped_server("wsl.exe", ["-d", "Ubuntu-26.04", "--exec", "python3",
        old.linux(slot.service), "--config", old.linux(slot.ready)],
        enabled_tools=list(slot.frozen["native_tools"]))


def host(slot):
    original = old.transport.AppServer
    expected = authorization(slot)
    options = host_options(expected)
    # Reuse P30's isolated auth context, Skill delivery, transport and thread.
    # Only replace its old process-level policy with the validated P31 policy.
    def launch(codex, env, cwd, extra_args=None):
        servers = [s for s in extra_args if s.startswith("mcp_servers=")]
        actual = tomllib.loads(servers[-1])["mcp_servers"]["alva"]
        assert all(actual[k] == expected[k] for k in ("command", "args", "required", "tool_timeout_sec"))
        save(slot.path / "host-options.json", options)
        return original(codex, env, cwd, extra_args=options)
    with patch.object(old.transport, "AppServer", launch):
        h, c, thread, inventory = mm.host(slot)
    try:
        parsed = c.rpc("config/read", {"includeLayers": False})["config"]
        assert set(parsed["mcp_servers"]) == {"alva"}
        parsed_server = parsed["mcp_servers"]["alva"]
        assert all(parsed_server[k] == v for k, v in expected.items())
        assert set(parsed_server) - set(expected) <= {"enabled", "environment_id"}
        assert parsed_server.get("enabled", True) and parsed_server.get("environment_id", "local") == "local"
        assert parsed["approval_policy"] == "never" and thread["approvalPolicy"] == "never"
        assert thread["sandbox"]["type"] == "readOnly"
        assert inventory[0]["tools"] == slot.frozen["native_tools"]
        assert inventory[0]["tools"]["commit_transaction"]["annotations"]["destructiveHint"] is True
        save(slot.path / "policy-validation.json", {"status": "PASS", "server": expected,
            "thread_approval": thread["approvalPolicy"], "thread_sandbox": thread["sandbox"],
            "native_schema_sha256": sha(mm.canonical(inventory[0]["tools"])),
            "destructive_annotation_preserved": True})
    except BaseException:
        h.close()
        raise
    return h, c, thread, inventory


def bind_runtime(frozen):
    # P30 already enumerates its transitive runtime, including evaluator,
    # observer, sandbox, transport, controller and exact-byte materializer.
    names = set(json.loads(P30.read_text())["files"])
    names.add("integrations/codex/native_commit_authorization.py")
    names.update(p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py"))
    frozen["files"] = {p: sha((ROOT / p).read_bytes()) for p in sorted(names)}
    frozen["runtime_bytes"] = {p: base64.b64encode((ROOT / p).read_bytes()).decode() for p in frozen["files"]}


def prepare(args, runtime):
    previous = json.loads(P30.read_text())
    frozen = copy.deepcopy({k: v for k, v in previous.items() if k not in ("files", "runtime_bytes", "validation", "status")})
    frozen.update(schema="alva-p32-native-mm01/v1", base=BASE, parent_input_freeze_sha256=sha(P30.read_bytes()))
    frozen["schedule"] = [dict(previous["schedule"][1], id="P32-MM01-S")]
    mm.check_identity(frozen, args)
    assert frozen["config"] == CONFIG and frozen["tools"] == mm.TOOLS
    mm.decode(frozen["task"]["bundle"], frozen["task"]["bundle"]["payload_sha256"])
    runtime.mkdir(parents=True, exist_ok=False)
    # Existing P31 local synthetic Responses fixture validates the real model
    # tool approval route, not merely direct mcpServer/tool/call. No auth used.
    probe = ROOT / "tests/integrations/native_commit_authorization_test.py"
    cmd = [sys.executable, str(probe), "--attempt", "p32-" + args.attempt]
    for k in ("alva", "toolchain", "registry"):
        cmd += ["--" + k, getattr(args, k)]
    subprocess.run(cmd, cwd=ROOT, check=True, timeout=300)
    summary_path = ROOT / ".local/p31-commit-authorization" / ("p32-" + args.attempt) / "summary.json"
    approval = json.loads(summary_path.read_text())
    assert approval["status"] == "PASS" and approval["model_generation_calls"] == 0
    frozen["approval_preflight"] = {"status": "PASS", "summary_sha256": sha(summary_path.read_bytes()),
        "model_approval_path": approval["model_approval_path"],
        "files": {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in
                  (probe, probe.with_name("p31_synthetic_provider.py"))}}
    slot = mm.Slot(runtime, dict(frozen["schedule"][0], id="preflight-native"), frozen, args)
    h = None
    try:
        h, c, thread, inventory = host(slot)
        call = lambda name, arguments: c.rpc("mcpServer/tool/call", {
            "threadId": thread["thread"]["id"], "server": "alva", "tool": name, "arguments": arguments})
        b = call("begin_transaction", {"project": "/work/project/alva.toml"})
        assert not b.get("isError"), b
        tx = b["structuredContent"]["transaction_id"]
        assert not call("inspect_body", {"transaction_id": tx, "function": frozen["task"]["target"]}).get("isError")
        assert not call("abort_transaction", {"transaction_id": tx}).get("isError")
        assert slot.dispatch("check", {})["status"] == "PASS"
        assert slot.dispatch("test", {})["status"] == "TEST_FAIL"
    finally:
        if h:
            h.close()
        slot.close()
    evidence = json.loads(slot.evidence.read_text())
    assert evidence["status"] == "CLOSED" and not evidence.get("error") and not evidence.get("worker_error")
    assert evidence["initial_authority"] == evidence["final_authority"]
    assert evidence["final"]["regression"]["exit"] == 0 and evidence["final"]["goal"]["exit"] != 0
    assert set(evidence["final_files"]) == set(mm.PATHS)
    frozen["host_policy"] = {"constructor": "integrations.codex.native_commit_authorization.host_options",
        "default": "auto", "only_explicit_grant": "alva.commit_transaction",
        "strict_config": True, "approval_policy": "never", "sandbox": "read-only",
        "transport": {"command": "wsl.exe", "distribution": "Ubuntu-26.04", "service": "benchmarks/mm01_pilot/service.py"},
        "actual_preflight_options_sha256": sha((slot.path / "host-options.json").read_bytes()),
        "candidate_transport_paths": "fresh attempt-specific service/ready path; no semantic configuration variability"}
    validation = {"status": "PASS", "generation_calls": 0, "controller": old.simulated_validation(),
        "model_tool_approval_path": frozen["approval_preflight"], "actual_p32_policy": "PASS",
        "native_tools": len(inventory[0]["tools"]), "schemas_identical_to_p30": True,
        "public_input_skill_evaluator_identical_to_p30": True, "authority_unchanged": True,
        "baseline_check_build_regression": "PASS", "baseline_goal_expected_fail": True,
        "linux_isolation": "P22/P23; unchanged", "historical_artifacts_modified": False}
    frozen["validation"] = validation
    frozen["status"] = "FROZEN_BEFORE_GENERATION"
    bind_runtime(frozen)
    save(HERE / "PREFLIGHT.json", validation)
    save(HERE / "FREEZE.json", frozen)
    print("P32 FREEZE PASS; generation calls=0. Commit/push before run.", flush=True)


def summarize(entry, record, evidence, observations):
    r = mm.summarize(entry, record, evidence, observations)
    completed = [e["params"]["item"] for e in record.get("events", [])
        if e.get("method") == "item/completed" and e.get("params", {}).get("item", {}).get("type") == "mcpToolCall"]
    native = [c for c in evidence.get("calls", []) if c.get("request", {}).get("method") == "tools/call"]
    commits = [c for c in native if c["request"]["params"]["name"] == "commit_transaction"]
    app_commits = [c for c in completed if c["tool"] == "commit_transaction"]
    check_rows = [c for c in native if c["request"]["params"]["name"] == "check_transaction"]
    r.update(appserver_commit_attempts=len(app_commits),
        appserver_commit_errors=[c.get("error") for c in app_commits if c.get("error")],
        commit_reached_native_mcp=bool(commits),
        commit_call_ids_match_native_dispatch={c["id"] for c in app_commits if not c.get("error")} ==
            {c["request"]["params"].get("_meta", {}).get("callId") for c in commits},
        transaction_checks=[{"isError": bool(c["response"].get("isError")),
            "structuredContent": c["response"].get("structuredContent")} for c in check_rows],
        appserver_native_errors=[{"tool": c["tool"], "error": c["error"]} for c in completed if c.get("error")],
        historical_T_pooling=False)
    return r


def run(args, runtime):
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    assert frozen["status"] == "FROZEN_BEFORE_GENERATION" and frozen["validation"]["status"] == "PASS"
    assert len(frozen["schedule"]) == 1 and frozen["schedule"][0]["arm"] == "N"
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == BRANCH
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/" + BRANCH], cwd=ROOT, text=True).split()[0] == head
    for p, digest in frozen["files"].items():
        assert sha((ROOT / p).read_bytes()) == digest, p
    mm.check_identity(frozen, args)
    # Study-wide exclusive ledger, independent of caller-selected attempt name.
    ledger = ROOT / ".local/p32-native-mm01/GENERATION-STARTED.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("x", encoding="utf-8") as out:
        json.dump({"freeze_commit": head, "maximum_model_tasks": 1, "attempt": args.attempt}, out)
    runtime.mkdir(parents=True, exist_ok=False)
    save(runtime / "STARTED.json", {"freeze_commit": head, "maximum_model_tasks": 1})
    entry = frozen["schedule"][0]
    record = {"model_tasks_started": 0, "freeze_commit": head}
    slot = h = c = None
    print("START " + entry["id"], flush=True)
    try:
        slot = mm.Slot(runtime, entry, frozen, args)
        h, c, thread, inventory = host(slot)
        request = {"threadId": thread["thread"]["id"], "input": [{"type": "text", "text": entry["prompt"]}],
            "effort": CONFIG["effort"], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly"}}
        save(slot.path / "turn-start.json", request)
        record["model_tasks_started"] = 1
        turn = c.rpc("turn/start", request)
        c.bind(thread, turn)
        c.record = record
        with patch.object(old, "CONFIG", CONFIG):
            old.drive(c, slot, record)
    except Exception as exc:
        record["infrastructure_hold"] = type(exc).__name__ + ": " + str(exc)
        if c and c.turn_id:
            try:
                c.interrupt()
                deadline = time.monotonic() + 20
                terminal = None
                while time.monotonic() < deadline:
                    try:
                        terminal = c.observe(c.next(.5)) or terminal
                    except queue.Empty:
                        continue
                    if terminal and c.interrupt_ack:
                        break
                record["termination_unconfirmed"] = not (terminal and c.interrupt_ack)
            except Exception:
                record["termination_unconfirmed"] = True
    finally:
        if h:
            h.close()
        if slot:
            try:
                slot.close()
            except Exception as exc:
                record["infrastructure_hold"] = "CLEANUP:" + str(exc)
    evidence = json.loads(slot.evidence.read_text()) if slot and slot.evidence.exists() else {}
    if evidence.get("error") or evidence.get("worker_error"):
        record["infrastructure_hold"] = "SERVICE:" + str(evidence.get("error") or evidence.get("worker_error"))
    op = slot.path / "observer.jsonl" if slot else None
    observations = [json.loads(line) for line in op.read_text().splitlines()] if op and op.exists() else []
    result = summarize(entry, record, evidence, observations)
    save(runtime / entry["id"] / "record.json", record)
    archive = runtime / "RAW.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(runtime.rglob("*")):
            if p.is_file() and p != archive and "model" not in p.relative_to(runtime).parts:
                z.write(p, p.relative_to(runtime).as_posix())
    with zipfile.ZipFile(archive) as z:
        entries = len(z.namelist())
    save(HERE / "ARCHIVE.json", {"sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size,
        "entries": entries, "controlled_local_only": True, "contains_credentials": False})
    save(HERE / "RESULTS.json", {"status": "COMMON_INFRASTRUCTURE_HOLD" if result.get("infrastructure_hold") else "CLOSED_COMPLETE",
        "freeze_commit": head, "scheduled": 1, "executed": record["model_tasks_started"], "slots": [result]})
    print("CLOSED " + result["disposition"] + "; STOP, no extra model tasks.", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "run"))
    p.add_argument("--attempt", required=True)
    for k in ("alva", "toolchain", "registry"):
        p.add_argument("--" + k, required=True)
    args = p.parse_args()
    (prepare if args.mode == "prepare" else run)(args, ROOT / ".local/p32-native-mm01" / args.attempt)
