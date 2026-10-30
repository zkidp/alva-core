"""One prospective MM02 turn. P32 controller, P31 approval, real P34 Guard.

SSH changes only trusted transport; no model hints, rescue or host execution.
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
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.mm01_pilot import pilot as mm
from benchmarks.p34_scope_guard.cases import case, TOOLS as NAMES
from benchmarks.maintenance_design import witnesses
from benchmarks.p36_mm02_native_model.remote import Remote
from integrations.benchmark_runtime_v2.freeze import pack_git, decode, canonical, sha
from integrations.codex.native_commit_authorization import scoped_server, host_options

old, save = mm.old, mm.save
HERE = Path(__file__).resolve().parent
BASE = "88cb64c9a9361c00f061bb1da2043d55315f8235"
BRANCH = "codex/p36-mm02-native-autonomous-maintenance"
CONFIG = dict(mm.CONFIG)
PATHS = ("alva.toml", "src/model.alva", "src/xml.alva")
INSTRUCTIONS = mm.INSTRUCTIONS.replace("src/app.alva and src/model.alva", "src/model.alva and src/xml.alva")
INSTRUCTIONS += " Only the body of store.xml.parse_prefix is authorized for mutation; preserve every other declaration."


class Slot(mm.Slot):
    READY_SECONDS = 45
    def __init__(self, runtime, entry, frozen, args):
        self.path = runtime / entry["id"]
        self.path.mkdir(parents=True, exist_ok=False)
        self.entry, self.frozen, self.calls = entry, frozen, 0
        self.remote = Remote(args.connection)
        self.ready, self.evidence = self.path / "ready.json", self.path / "linux.json"
        self.service = HERE / "service.py"
        self.config = {"bundle": frozen["task"]["bundle"], "policy": frozen["policy"], "arm": "N",
                       "vectors": [], "docs": frozen["docs"], "ready": self.remote.path(self.ready),
                       "evidence": self.remote.path(self.evidence),
                       "guard_evidence": self.remote.path(self.path / "guard.jsonl"),
                       "observer_evidence": self.remote.path(self.path / "observer.jsonl"),
                       "alva": args.alva, "toolchain": args.toolchain, "registry": args.registry}
        save(self.path / "config.json", self.config)
        self.remote.put(self.path / "config.json")
        self.process = None
        self.startup_instance = uuid.uuid4().hex
        self.owner_state = self.remote.path(self.path / ("startup-" + self.startup_instance))
        try:
            self.process = subprocess.Popen(self.remote.owned_service_argv(self.owner_state, self.startup_instance,
                self.remote.path(self.service), self.remote.path(self.path / "config.json")),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = time.monotonic() + self.READY_SECONDS
            while True:
                if self.process.poll() is not None:
                    _, stderr = self.process.communicate(timeout=2)
                    raise old.InfrastructureError("SERVICE_EXIT_BEFORE_READY:" + str(self.process.returncode) + ":" + stderr.decode(errors="replace")[-2000:])
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise old.InfrastructureError("SERVICE_READY_TIMEOUT")
                probe = self.remote.run(["test", "-f", self.remote.path(self.ready)], timeout=min(2, remaining))
                if probe.returncode == 0:
                    break
                if probe.returncode != 1:
                    raise old.InfrastructureError("SERVICE_READINESS_PROBE_FAILED:" + probe.stderr[-1000:])
                time.sleep(min(.1, max(0, deadline - time.monotonic())))
        except BaseException as original:
            # Slot(...) has not returned: this object must clean its own launch.
            try:
                cleanup = self._startup_cleanup()
            except BaseException as exc:
                cleanup = {"status": "STARTUP_CLEANUP_UNCONFIRMED", "errors": [repr(exc)]}
            try:
                save(self.path / "startup-failure.json", {"startup_error": type(original).__name__ + ":" + str(original),
                                                         "cleanup": cleanup})
            except BaseException as exc:
                cleanup["record_error"] = repr(exc)
            original.startup_cleanup = cleanup
            if hasattr(original, "add_note"):
                original.add_note(cleanup["status"] + ":" + json.dumps(cleanup))
            raise

    def _startup_cleanup(self):
        errors = []
        remote = None
        try:
            remote = self.remote.cleanup_owned(self.owner_state, self.startup_instance)
            if remote.get("instance") != self.startup_instance or remote.get("confirmed") is not True:
                raise RuntimeError("REMOTE_CLEANUP_IDENTITY_OR_CONFIRMATION_MISSING")
        except BaseException as exc:
            errors.append("remote:" + type(exc).__name__ + ":" + str(exc))
        reaped = self.process is None
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                try:
                    self.process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.communicate(timeout=2)
                reaped = True
            except BaseException as exc:
                errors.append("ssh:" + type(exc).__name__ + ":" + str(exc))
            finally:
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except BaseException as exc:
                            errors.append("pipe:" + repr(exc))
        return {"status": "STARTUP_CLEANUP_CONFIRMED" if not errors and reaped else "STARTUP_CLEANUP_UNCONFIRMED",
                "instance": self.startup_instance, "remote": remote, "local_ssh_reaped": reaped, "errors": errors}

    def dispatch(self, action, args):
        with patch.object(mm, "PATHS", PATHS), patch.object(old, "wsl", self.remote.run), \
             patch.object(old, "linux", self.remote.path):
            return super().dispatch(action, args)

    def close(self):
        try:
            super().close()
        finally:
            # Even a failed graceful stop must not leave the owned namespace.
            # Preserve an existing exception instead of hiding it with cleanup.
            original = sys.exc_info()[1]
            cleanup = self._startup_cleanup()
            try:
                save(self.path / "close-cleanup.json", cleanup)
            except BaseException:
                if original is None:
                    raise
            if cleanup["status"] != "STARTUP_CLEANUP_CONFIRMED":
                if original is None:
                    raise old.InfrastructureError("CLOSE_CLEANUP_UNCONFIRMED:" + json.dumps(cleanup))
                if hasattr(original, "add_note"):
                    original.add_note("CLOSE_CLEANUP_UNCONFIRMED:" + json.dumps(cleanup))
            if original is None:
                for name in ("linux.json", "guard.jsonl", "observer.jsonl"):
                    local = self.path / name
                    if not self.remote.run(["test", "-f", self.remote.path(local)]).returncode:
                        self.remote.get(local)


def authorization(slot):
    return scoped_server(sys.executable, [str(HERE / "remote.py"), "--connection", str(slot.remote.connection),
        "--ready", slot.remote.path(slot.ready)], enabled_tools=list(NAMES))


def host(slot):
    original = old.transport.AppServer
    expected = authorization(slot)
    options = host_options(expected)
    def launch(codex, env, cwd, extra_args=None):
        save(slot.path / "host-options.json", options)
        return original(codex, env, cwd, extra_args=options)
    with patch.object(old.transport, "AppServer", launch), patch.object(mm, "CONFIG", CONFIG), \
         patch.object(old, "linux", slot.remote.path):
        h, c, thread, inventory = mm.host(slot)
    try:
        parsed = c.rpc("config/read", {"includeLayers": False})["config"]
        assert set(parsed["mcp_servers"]) == {"alva"}
        server = parsed["mcp_servers"]["alva"]
        assert all(server[k] == v for k, v in expected.items())
        assert set(server) - set(expected) <= {"enabled", "environment_id"}
        assert parsed["approval_policy"] == thread["approvalPolicy"] == "never"
        assert thread["sandbox"]["type"] == "readOnly"
        assert set(inventory[0]["tools"]) == set(NAMES)
        assert inventory[0]["tools"]["commit_transaction"]["annotations"]["destructiveHint"] is True
        if frozen_tools := slot.frozen.get("native_tools"):
            assert inventory[0]["tools"] == frozen_tools
        save(slot.path / "policy-validation.json", {"status": "PASS", "server": expected,
            "thread_approval": thread["approvalPolicy"], "thread_sandbox": thread["sandbox"],
            "native_schema_sha256": sha(canonical(inventory[0]["tools"]))})
    except BaseException:
        h.close()
        raise
    return h, c, thread, inventory


def runtime_names():
    names = set(json.loads((ROOT / "benchmarks/p32_native_mm01/FREEZE.json").read_text())["files"])
    names = {p for p in names if not p.startswith("benchmarks/p32_native_mm01/")}
    names.update(["benchmarks/maintenance_design/feasibility.py", "benchmarks/maintenance_design/witnesses.py",
        "benchmarks/maintenance_design/TASK-CANDIDATES.json", "benchmarks/mm01_pilot/FREEZE.json",
        "benchmarks/p34_scope_guard/cases.py", "benchmarks/p33_shared_scope/reproduce.py",
        "integrations/codex/precommit_scope_guard.py"])
    names.update(p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py"))
    return sorted(names)


def identity(args):
    remote = Remote(args.connection)
    with patch.object(old, "wsl", remote.run):
        result = old.sdk_identity(args)
    result["platform"] = json.loads(remote.checked(["python3", "-c",
        "import platform,json;print(json.dumps({'system':platform.system(),'release':platform.release(),'machine':platform.machine()}))"]))
    result["alva_version"] = remote.checked([args.alva, "--version"]).strip()
    result["rustc_version"] = remote.checked([args.toolchain + "/bin/rustc", "--version"]).strip()
    return result


def prepare(args, runtime):
    fixed = case("MM02_SHARED")
    task = {k: fixed["task"][k] for k in ("id", "target", "requirement", "bundle", "functions", "public_inputs")}
    assert task["bundle"]["payload_sha256"] == "352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf"
    docs_bundle = pack_git(ROOT, BASE, ["integrations/skills/alva/" + n for n in
        ("SKILL.md", "references/workflow.md", "references/diagnostics.md", "references/examples.md")] + ["alva/README.md"])
    docs_data = decode(docs_bundle, docs_bundle["payload_sha256"])
    docs = {p.removeprefix("integrations/skills/alva/"): b.decode() for p, b in docs_data.items() if p.startswith("integrations/")}
    prompt = ("MM02 existing-code maintenance.\n" + task["requirement"] +
        "\nProject: /work/project/alva.toml. Initial source-only input paths: alva.toml, src/model.alva, src/xml.alva. "
        "Use the permitted tools to inspect and modify the existing project, then check/test and finish. "
        "Generic language documentation is available using study doc path language.md.\n")
    entry = {"id": "P36-MM02-S", "arm": "N", "condition": "S", "prompt": prompt +
        "\n$alva\nComplete official Skill and references follow verbatim:\n" +
        "".join("\n--- " + name + " ---\n" + body for name, body in docs.items())}
    frozen = {"schema": "alva-p36-mm02-native/v1", "base": BASE, "config": CONFIG, "tools": mm.TOOLS,
              "task": task, "docs": docs, "docs_bundle": docs_bundle,
              "language": docs_data["alva/README.md"].decode(), "policy": fixed["policy"],
              "public_task_input": prompt, "developer_instructions": INSTRUCTIONS, "schedule": [entry],
              "assertions": {"goal": witnesses.goals("MM02"), "regression": witnesses.regressions("MM02")},
              "terminal_rules": {"precedence": ["INFRASTRUCTURE_HOLD", "RESOURCE_CENSORED", "COMPLETED_CORRECT_MAINTENANCE",
                                "COMMITTED_INCORRECT_MAINTENANCE", "NO_COMMITTED_CANDIDATE"],
                  "correct": "changed target + actual guarded commit + AIR + matching fresh revision + original task/regression + scope + no unresolved infrastructure error",
                  "guard_denial": "ordinary model feedback, never infrastructure failure", "resource": "record authoritative candidate separately; no rerun"},
              "feedback": "unchanged P32 bounded compiler diagnostics/combined behavior only; hidden assertions never returned",
              "leakage_boundary": "Only public prompt/task/source, official docs/Skill, actual schemas and normal tools. No history, witnesses or study repository mounted.",
              "codex": subprocess.check_output([shutil.which("codex"), "--version"], text=True).strip(),
              "codex_binary_sha256": sha(Path(shutil.which("codex")).read_bytes()), "sdk_identity": identity(args)}
    original = json.loads((ROOT / "benchmarks/mm01_pilot/FREEZE.json").read_text())
    assert frozen["docs"] == original["docs"] and frozen["language"] == original["language"]
    remote = Remote(args.connection)
    for name in runtime_names():
        remote.put(ROOT / name)
    runtime.mkdir(parents=True, exist_ok=False)
    slot, h = None, None
    try:
        slot = Slot(runtime, dict(entry, id="preflight"), frozen, args)
        h, c, thread, inventory = host(slot)
        frozen["native_tools"] = inventory[0]["tools"]
        call = lambda name, arguments: c.rpc("mcpServer/tool/call", {"threadId": thread["thread"]["id"],
            "server": "alva", "tool": name, "arguments": arguments})
        begun = call("begin_transaction", {"project": "/work/project/alva.toml"})
        assert not begun.get("isError"), begun
        tx = begun["structuredContent"]["transaction_id"]
        assert not call("inspect_body", {"transaction_id": tx, "function": task["target"]}).get("isError")
        # No engineering candidate or P35 sequence during this preflight.
        assert not call("abort_transaction", {"transaction_id": tx}).get("isError")
        assert slot.dispatch("check", {})["status"] == "PASS"
        assert slot.dispatch("test", {})["status"] == "TEST_FAIL"
    finally:
        if h:
            h.close()
        if slot:
            slot.close()
    evidence = json.loads(slot.evidence.read_text())
    assert evidence["status"] == "CLOSED" and not evidence.get("error") and not evidence.get("worker_error")
    assert evidence["initial_authority"] == evidence["final_authority"]
    assert evidence["final"]["regression"]["status"] == "PASS"
    assert evidence["final"]["goal"]["status"] == "TEST_FAIL"
    assert set(evidence["final_files"]) == set(PATHS)
    guard = [json.loads(l) for l in (slot.path / "guard.jsonl").read_text().splitlines()]
    assert any(r["event"] == "trusted_baseline" and "error" not in r["snapshot"] for r in guard)
    frozen["host_policy"] = {"constructor": "integrations.codex.native_commit_authorization.host_options",
        "global_thread_approval": "never", "default_tool_approval": "auto", "only_explicit_approval": "alva.commit_transaction",
        "destructive_hint": True, "strict_config": True, "read_only": True,
        "single_server": "alva", "guard": "integrations.codex.precommit_scope_guard.GuardedNative",
        "transport": "SSH stdio; trusted service in outer unprivileged user namespace to isolate per-UID process accounting; unchanged inner P22/P23 limits; private endpoint/key excluded",
        "actual_options_sha256": sha((slot.path / "host-options.json").read_bytes()),
        "approval_evidence_reused": "P31/P34; actual P36 parsed strict configuration checked, no repeated historical solution"}
    frozen["files"] = {p: sha((ROOT / p).read_bytes()) for p in runtime_names()}
    frozen["runtime_bytes"] = {p: base64.b64encode((ROOT / p).read_bytes()).decode() for p in frozen["files"]}
    remote_hashes = json.loads(remote.checked(["python3", "-c",
        "import sys,json,hashlib,pathlib;root=pathlib.Path(sys.argv[1]);print(json.dumps({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in json.loads(sys.argv[2])}))",
        remote.root, json.dumps(list(frozen["files"]))]))
    assert remote_hashes == frozen["files"]
    frozen["status"] = "FROZEN_BEFORE_GENERATION"
    frozen["validation"] = {"status": "PASS", "model_generation_calls": 0, "baseline_regression": "PASS",
        "baseline_task": "EXPECTED_FAIL", "authority_unchanged": True, "actual_host_policy": "PASS",
        "real_guard_baseline": True, "runtime_bytes_match_remote": True, "native_tools": 20,
        "candidate_solution_preflight": "NOT_PERFORMED", "isolation": "unchanged P22/P23 Linux namespaces"}
    save(HERE / "FREEZE.json", frozen)
    save(HERE / "PREFLIGHT.json", frozen["validation"])
    print("P36 actual preflight PASS; model slots started=0. Commit/push freeze before run.", flush=True)


def run(args, runtime):
    from benchmarks.p36_mm02_native_model.analyze import analyze
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    assert frozen["status"] == "FROZEN_BEFORE_GENERATION" and frozen["validation"]["status"] == "PASS"
    assert len(frozen["schedule"]) == 1
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == BRANCH
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/" + BRANCH], cwd=ROOT, text=True).split()[0] == head
    for p, digest in frozen["files"].items():
        assert sha((ROOT / p).read_bytes()) == digest, p
    assert identity(args) == frozen["sdk_identity"]
    assert sha(Path(shutil.which("codex")).read_bytes()) == frozen["codex_binary_sha256"]
    remote = Remote(args.connection)
    hashes = json.loads(remote.checked(["python3", "-c",
        "import sys,json,hashlib,pathlib;root=pathlib.Path(sys.argv[1]);print(json.dumps({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in json.loads(sys.argv[2])}))",
        remote.root, json.dumps(list(frozen["files"]))]))
    assert hashes == frozen["files"]
    ledger = ROOT / ".local/p36-mm02-model/GENERATION-STARTED.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("x", encoding="utf-8") as out:
        json.dump({"freeze_commit": head, "maximum_model_tasks": 1, "attempt": args.attempt}, out)
    runtime.mkdir(parents=True, exist_ok=False)
    entry = frozen["schedule"][0]
    record = {"model_tasks_started": 0, "freeze_commit": head}
    slot = h = c = None
    try:
        slot = Slot(runtime, entry, frozen, args)
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
    save(runtime / "record.json", record)
    if slot:
        result = analyze(frozen, record, slot.path)
    else:
        result = {"disposition": "INFRASTRUCTURE_HOLD", "record": record}
    save(HERE / "RESULTS.json", result)
    archive = runtime / "RAW.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(runtime.rglob("*")):
            if p.is_file() and p != archive and "model" not in p.relative_to(runtime).parts:
                z.write(p, p.relative_to(runtime).as_posix())
    save(HERE / "ARCHIVE.json", {"sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size,
        "controlled_local_only": True, "credential_files_excluded": True})
    print("P36 CLOSED " + result["disposition"] + "; no retry or replacement.", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "run"))
    p.add_argument("--connection", type=Path, required=True)
    p.add_argument("--attempt", required=True)
    for key in ("alva", "toolchain", "registry"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    (prepare if a.mode == "prepare" else run)(a, ROOT / ".local/p36-mm02-model" / a.attempt)
