"""Two-slot P28 adapter. P26 control/drive, P23 isolation and transport reused.

No previous candidates or trajectories are read. Public inputs come only from
the normative P26 freeze and exact P27 design; all raw outputs stay in .local.
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
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import pilot as old
from benchmarks.p27_bottleneck.audit import extract_calls, usage_events, bracket, classify
from benchmarks.p28_optional_descriptor.observer import MUTATIONS
from integrations.benchmark_runtime_v2.freeze import canonical, sha

HERE = Path(__file__).resolve().parent
BASE = "8f2207a6533df87e3d2c707c8a04e3f0ce529345"
BRANCH = "codex/p28-optional-native-descriptor"
DESIGN_PATH = ROOT / "benchmarks/p27_bottleneck/NEXT-EXPERIMENT.json"
DESIGN = json.loads(DESIGN_PATH.read_text())
OVERRIDE = DESIGN["intervention_exact_developer_addendum"]
save = old.save


class Slot(old.Slot):
    """Only the service entry/config differ; dispatch/termination are inherited."""
    def __init__(self, runtime, entry, frozen, args):
        self.path = runtime / entry["id"]
        self.path.mkdir(parents=True, exist_ok=False)
        self.ready, self.evidence = self.path / "ready.json", self.path / "linux.json"
        self.entry, self.frozen, self.calls = entry, frozen, 0
        self.service = HERE / "service.py"
        self.config = {
            "bundle": frozen["tasks"]["HE41"]["bundle"], "arm": "N",
            "vectors": frozen["tasks"]["HE41"]["vectors"], "docs": frozen["docs"],
            "ready": old.linux(self.ready), "evidence": old.linux(self.evidence),
            "observer_evidence": old.linux(self.path / "observer.jsonl"),
            "alva": args.alva, "toolchain": args.toolchain, "registry": args.registry,
        }
        save(self.path / "config.json", self.config)
        self.process = subprocess.Popen([
            "wsl.exe", "-d", "Ubuntu-26.04", "--exec", "python3",
            old.linux(self.service), "--role", "server", "--config",
            old.linux(self.path / "config.json")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 30
        while not self.ready.exists():
            if self.process.poll() is not None:
                raise old.InfrastructureError("SERVICE_EXIT:" + self.process.communicate()[1].decode(errors="replace")[-2000:])
            if time.monotonic() > deadline:
                self.process.kill()
                self.process.communicate()
                raise old.InfrastructureError("SERVICE_READY_TIMEOUT")
            time.sleep(.05)


def host(slot):
    class ConditionController(old.Controller):
        def rpc(self, method, params, timeout=30):
            if method == "thread/start":
                params = copy.deepcopy(params)
                self.original_instructions = params["developerInstructions"]
                if slot.entry["condition"] == "C1":
                    params["developerInstructions"] += "\n\n" + OVERRIDE
                self.actual_instructions = params["developerInstructions"]
                expected = slot.entry.get("developer_instructions")
                if expected is not None and expected != self.actual_instructions:
                    raise old.InfrastructureError("DEVELOPER_INPUT_DRIFT")
                # Exact machine-local request is private, never a public config.
                save(slot.path / "thread-start.json", params)
            return super().rpc(method, params, timeout)

        def interrupt(self):
            if self.interrupt_id is None and hasattr(self, "record"):
                self.record["first_interrupt_event_boundary"] = len(self.record["events"])
            return super().interrupt()

    with patch.object(old, "Controller", ConditionController):
        return old.host(slot)


def inputs():
    prior = json.loads((ROOT / "benchmarks/native_prospective/FREEZE.json").read_text())
    assert prior["config"] == old.CONFIG and prior["tools"] == old.TOOLS
    task = prior["tasks"]["HE41"]
    prompt = next(s["prompt"] for s in prior["schedule"] if s["task"] == "HE41" and s["arm"] == "N")
    result = {"base": BASE, "config": old.CONFIG, "tools": old.TOOLS,
              "tasks": {"HE41": task}, "docs": prior["docs"],
              "native_tools": prior["native_tools"], "sdk_identity": prior["sdk_identity"],
              "binary_sha256": prior["binary_sha256"], "codex": prior["codex"],
              "codex_binary_sha256": prior["codex_binary_sha256"],
              "design_sha256": sha(DESIGN_PATH.read_bytes()),
              "p26_freeze_sha256": sha((ROOT / "benchmarks/native_prospective/FREEZE.json").read_bytes()),
              "schedule": [{"id": "P28-01-HE41-C1", "task": "HE41", "arm": "N", "condition": "C1", "prompt": prompt},
                           {"id": "P28-02-HE41-C0", "task": "HE41", "arm": "N", "condition": "C0", "prompt": prompt}],
              "override": OVERRIDE, "override_utf8_bytes": len(OVERRIDE.encode()),
              "model_input_boundary": "Only public requirement/original stub, exact full official docs and advertised schemas. Evaluator vectors are trusted host only.",
              "observer": {"target": "bench.solve", "read": "inspect_body", "same_live_transaction": True,
                           "feedback_added": False, "separate_call_accounting": True,
                           "primary_cutoff": "Only changed observations whose associated model tool completion event precedes first acknowledged-controller interrupt request. Completion-before-request ordering is conservative; no cross-clock inference.",
                           "no_credit": ["detached nodes", "ok:true alone", "observations after first interrupt", "missing tool-completion association"]},
              "no_retry_replacement_extra_slot": True, "generation_calls_before_freeze": 0}
    assert prompt == old.prompt(result["schedule"][0], result)
    return result


def check_identity(frozen, args):
    assert old.sdk_identity(args) == frozen["sdk_identity"], "SDK/runtime drift"
    assert old.wsl(["sha256sum", args.alva]).stdout.split()[0] == frozen["binary_sha256"]
    binary = Path(shutil.which("codex"))
    assert sha(binary.read_bytes()) == frozen["codex_binary_sha256"], "Codex SDK drift"
    assert subprocess.check_output([str(binary), "--version"], text=True).strip() == frozen["codex"]


def bind_runtime(frozen):
    paths = [p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py")] + [
        "benchmarks/native_prospective/pilot.py", "benchmarks/native_prospective/service.py",
        "benchmarks/native_prospective/inside.py", "benchmarks/p27_bottleneck/audit.py",
        "tests/integrations/codex_native_test.py", "benchmarks/cross_language/controller.py",
        "benchmarks/native_mcp_skill/proxy.py", "integrations/benchmark_runtime_v2/freeze.py",
        "integrations/benchmark_runtime_v2/persistent.py", "integrations/benchmark_runtime_v2/sandbox.py"]
    frozen["files"] = {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}
    frozen["runtime_bytes"] = {p: base64.b64encode((ROOT / p).read_bytes()).decode() for p in sorted(paths)}
    frozen["runtime_byte_policy"] = "Exact SHA256 UTF-8 bytes on both Windows and Linux; no EOL alternatives"


def prepare(args, runtime):
    runtime.mkdir(parents=True, exist_ok=False)
    frozen = inputs()
    check_identity(frozen, args)
    validations = {"controller": old.simulated_validation(), "generation_calls": 0}
    # A separate non-task literal fixture tests observer purity; no HE41 solution.
    command = ["python3", old.linux(HERE / "validate_linux.py"), "--alva", args.alva,
               "--toolchain", args.toolchain, "--registry", args.registry]
    p = old.wsl(command)
    if p.returncode:
        raise old.InfrastructureError("OBSERVER_ZERO_MODEL_FAIL:" + p.stdout[-3000:] + p.stderr[-3000:])
    save(runtime / "observer-preflight.json", json.loads(p.stdout))
    validations["linux_observer"] = json.loads(p.stdout)
    for entry in frozen["schedule"]:
        entry = dict(entry, id="preflight-" + entry["condition"])
        slot, h = Slot(runtime, entry, frozen, args), None
        try:
            h, c, thread, inventory = host(slot)
            assert inventory[0]["tools"] == frozen["native_tools"] and len(inventory[0]["tools"]) == 20
            target = next(s for s in frozen["schedule"] if s["condition"] == entry["condition"])
            target["developer_instructions"] = c.actual_instructions
            target["prompt_sha256"] = sha(target["prompt"].encode())
            target["developer_sha256"] = sha(c.actual_instructions.encode())
            tool = lambda name, arguments: c.rpc("mcpServer/tool/call", {
                "threadId": thread["thread"]["id"], "server": "alva", "tool": name, "arguments": arguments})
            begun = tool("begin_transaction", {"project": "/work/project/alva.toml"})
            assert not begun.get("isError"), begun
            aborted = tool("abort_transaction", {"transaction_id": begun["structuredContent"]["transaction_id"]})
            assert not aborted.get("isError"), aborted
        finally:
            if h:
                h.close()
            slot.close()
        evidence = json.loads(slot.evidence.read_text())
        assert evidence["status"] == "CLOSED" and not evidence.get("worker_error")
        assert evidence["final"]["check"]["exit"] == 0 and evidence["final"]["status"] == "TEST_FAIL"
        assert evidence["initial_authority"] == evidence["final_authority"]
        validations[entry["condition"]] = {"native_schema_skill": "PASS", "begin_abort": "PASS",
            "isolated_compile_behavior": "PASS (original stub expected behavioral FAIL)",
            "authority_unchanged": True, "model": thread["model"], "generation_calls": 0}
    c1, c0 = frozen["schedule"]
    assert c1["prompt"] == c0["prompt"]
    assert c1["developer_instructions"] == c0["developer_instructions"] + "\n\n" + OVERRIDE
    slot = Slot(runtime, {"id": "preflight-observed-relay", "arm": "N", "condition": "C0"}, frozen, args)
    try:
        p = old.wsl(["python3", old.linux(HERE / "validate_linux.py"), "--relay-ready", old.linux(slot.ready)])
        assert p.returncode == 0, p.stderr
        relay = json.loads(p.stdout)
    finally:
        slot.close()
    observations = [json.loads(line) for line in (slot.path / "observer.jsonl").read_text().splitlines()]
    assert len(observations) == 1 and observations[0]["call_id"] == "synthetic-begin"
    assert observations[0]["body_sha256"] == relay["body_sha256"]
    evidence = json.loads(slot.evidence.read_text())
    assert evidence["status"] == "CLOSED" and not evidence.get("worker_error")
    assert len([c for c in evidence["calls"] if c.get("request", {}).get("method") == "tools/call"]) == 3
    validations["real_service_observer_relay"] = {"status": "PASS", "observer_calls": 1,
        "model_envelopes": 3, "observer_not_counted_as_model": True, "feedback_unchanged": True}
    validations["input_identity_except_exact_override"] = "PASS"
    validations["status"] = "PASS"
    frozen["validation"] = validations
    bind_runtime(frozen)
    frozen["status"] = "FROZEN_BEFORE_GENERATION"
    save(HERE / "FREEZE.json", frozen)
    save(HERE / "PREFLIGHT.json", validations)
    print("P28 FREEZE PASS; commit and push before generation", flush=True)


def summarize(entry, record, evidence, observations):
    calls = extract_calls(record.get("events", []))
    usage = usage_events(record.get("events", []))
    cutoff = record.get("first_interrupt_event_boundary", len(record.get("events", [])))
    by_id = {c["item_id"]: c for c in calls}
    observed = []
    for obs in observations:
        call = by_id.get(obs["call_id"])
        before = call is not None and call["end"] is not None and call["end"] < cutoff
        observed.append({k: obs[k] for k in ("call_id", "after_operation", "baseline", "body_sha256",
            "baseline_body_sha256", "changed_from_transaction_start", "observer_calls")} | {
                "completion_before_first_interrupt": before,
                "model_tool_ordinal": calls.index(call) + 1 if call else None})
    operations = [c for c in evidence.get("calls", []) if c.get("request", {}).get("method") == "tools/call"]
    expected_observed = [c for c in operations if not c["response"].get("isError") and
        (c["request"]["params"]["name"] == "begin_transaction" or
         c["request"]["params"]["name"] in MUTATIONS)]
    observed_ids = {o["call_id"] for o in observations}
    observer_complete = all(c["request"]["params"].get("_meta", {}).get("callId") in observed_ids for c in expected_observed)
    if not observer_complete:
        record["infrastructure_hold"] = "OBSERVER_ASSOCIATION_INCOMPLETE"
    counts = {}
    for c in operations:
        name = c["request"]["params"]["name"]
        counts[name] = counts.get(name, 0) + 1
    initial, final = evidence.get("initial_authority", {}), evidence.get("final_authority", {})
    changed = bool(initial.get("body_sha256") and final.get("body_sha256") and initial["body_sha256"] != final["body_sha256"])
    first_construct = next((i for i, c in enumerate(calls, 1) if c["operation"] in
        ("create_reference", "create_literal", "create_binary", "create_call", "create_if", "construct_expression") and not c["failed"]), None)
    connected = [o for o in observed if o["changed_from_transaction_start"] and not o["baseline"] and o["completion_before_first_interrupt"]]
    published = any(p.startswith("alva-air/") for p in evidence.get("final_files", {}))
    row = {k: record.get(k) for k in ("model_tasks_started", "freeze_commit", "tool_calls", "usage", "usage_complete", "terminal_status", "stop_reason", "interrupt_ack", "elapsed_seconds", "infrastructure_hold", "first_interrupt_event_boundary")}
    row.update(id=entry["id"], condition=entry["condition"], task="HE41",
               staged_target_changed_before_interrupt=bool(connected), first_connected_tool_ordinal=connected[0]["model_tool_ordinal"] if connected else None,
               first_construction_tool_ordinal=first_construct, operation_counts=counts,
               describe_operation_calls=counts.get("describe_operation", 0),
               observer_calls=sum(o["observer_calls"] for o in observations), observer_observations=observed,
               observer_complete=observer_complete,
               observer_elapsed_seconds=sum(o.get("elapsed_ns", 0) for o in observations) / 1e9,
               observer_counted_as_agent_discovery=False, authority_published=published,
               fresh_authority_target_changed=changed, initial_authority=initial, final_authority=final,
               transaction_checks=sum(c["request"]["params"]["name"] == "check_transaction" and not c["response"].get("isError") for c in operations),
               successful_commits=sum(c["request"]["params"]["name"] == "commit_transaction" and not c["response"].get("isError") for c in operations),
               operation_errors=sum(bool(c["response"].get("isError")) for c in operations),
               stage_trace=[{"tool_ordinal": i, "operation": call["operation"], "action": call["action"],
                             "stage": classify(call["action"], call["operation"]),
                             "start_event_index": call["start"], "end_event_index": call["end"],
                             "failed": call["failed"], "usage_interval": bracket(usage, call["start"], call["end"] if call["end"] is not None else call["start"])}
                            for i, call in enumerate(calls, 1)],
               independent_final_status=evidence.get("final", {}).get("status"),
               provider_generation_requests=None, dollar_cost=None, hard_provider_token_cap=False,
               final_check_exit=evidence.get("final", {}).get("check", {}).get("exit"),
               disposition=evidence.get("final", {}).get("status", "UNKNOWN") if published else "NO_COMMITTED_CANDIDATE")
    return row


def run(args, runtime):
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    assert frozen["status"] == "FROZEN_BEFORE_GENERATION" and frozen["validation"]["status"] == "PASS"
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/" + BRANCH], cwd=ROOT, text=True).split()[0]
    assert head == remote, "Freeze must be committed/pushed before first turn"
    for name, digest in frozen["files"].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    check_identity(frozen, args)
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / "STARTED.json").open("x") as f:
        json.dump({"freeze_commit": head, "maximum_model_tasks": 2}, f)
    public = []
    for entry in frozen["schedule"]:
        row = {"model_tasks_started": 0, "freeze_commit": head}
        slot = h = c = None
        print("START " + entry["id"], flush=True)
        try:
            slot = Slot(runtime, entry, frozen, args)
            h, c, thread, inventory = host(slot)
            assert inventory[0]["tools"] == frozen["native_tools"]
            row["model_tasks_started"] = 1
            turn = c.rpc("turn/start", {"threadId": thread["thread"]["id"],
                "input": [{"type": "text", "text": entry["prompt"]}],
                "effort": old.CONFIG["effort"], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly"}})
            c.bind(thread, turn)
            c.record = row
            old.drive(c, slot, row)
        except Exception as exc:
            row["infrastructure_hold"] = type(exc).__name__ + ": " + str(exc)
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
                    if not terminal or not c.interrupt_ack:
                        row["termination_unconfirmed"] = True
                except Exception:
                    row["termination_unconfirmed"] = True
        finally:
            if h:
                h.close()
            if slot:
                try:
                    slot.close()
                except Exception as exc:
                    row["infrastructure_hold"] = "CLEANUP:" + str(exc)
        evidence = json.loads(slot.evidence.read_text()) if slot and slot.evidence.exists() else {}
        if evidence.get("worker_error") or evidence.get("error"):
            row["infrastructure_hold"] = "LINUX_SERVICE:" + str(evidence.get("worker_error") or evidence.get("error"))
        obs_path = slot.path / "observer.jsonl" if slot else None
        observations = [json.loads(line) for line in obs_path.read_text().splitlines()] if obs_path and obs_path.exists() else []
        result = summarize(entry, row, evidence, observations)
        save(runtime / entry["id"] / "result.json", row)
        public.append(result)
        save(runtime / "progress.json", [{k: r.get(k) for k in ("id", "model_tasks_started", "terminal_status", "infrastructure_hold")} for r in public])
        print("CLOSED " + entry["id"] + " " + result["disposition"], flush=True)
        if result.get("infrastructure_hold"):
            break
    archive = runtime / "RAW.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(runtime.rglob("*")):
            if p.is_file() and p != archive and "model" not in p.relative_to(runtime).parts:
                z.write(p, p.relative_to(runtime).as_posix())
    save(HERE / "ARCHIVE.json", {"sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size,
        "entries": len(zipfile.ZipFile(archive).namelist()), "controlled_local_only": True})
    status = "COMMON_INFRASTRUCTURE_HOLD" if any(r.get("infrastructure_hold") for r in public) else "CLOSED_COMPLETE"
    save(HERE / "RESULTS.json", {"status": status, "freeze_commit": head, "scheduled": 2,
         "executed": sum(r["model_tasks_started"] for r in public), "slots": public})
    print("STOP; no replacement or further model tasks", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "run"))
    p.add_argument("--attempt", required=True)
    for name in ("alva", "toolchain", "registry"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    runtime = ROOT / ".local/p28-optional-descriptor" / args.attempt
    (prepare if args.mode == "prepare" else run)(args, runtime)
