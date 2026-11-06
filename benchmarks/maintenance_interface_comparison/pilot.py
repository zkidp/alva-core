"""MIC-01 Windows control / SSH Linux execution. Frozen 24-slot exploratory run."""
import argparse
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import pilot as old
from benchmarks.p36_mm02_native_model.remote import Remote
from benchmarks.maintenance_design import feasibility as prior
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha
from integrations.codex.native_commit_authorization import scoped_server, host_options, toml_value

HERE = Path(__file__).parent
NAMES = tuple(json.loads((ROOT / "benchmarks/p36_mm02_native_model/FREEZE.json").read_text())["native_tools"])
INSTRUCTIONS = """Perform the registered existing-code maintenance task using only study and, in N, the Native MCP tools.
The actual candidate is /work/project/alva.toml in a remote Linux namespace; your local cwd is only a documentation container.
No shell, apply_patch, web, other directories, sessions, delegation, host execution or reading past task material.
T edits ordinary .alva source via study edit (unique exact replacement) or write (complete file replacement), then Git diff/check/test/finish.
N mutates only through actual Native MCP tools and must commit AIR for a candidate to count; detached nodes or uncommitted staging do not count.
Both arms can read all original sources, language.md, and the complete official Skill and reference files with study doc.
In T the Skill is informational: ignore its Native-first and CLI-fallback instructions; Native and shell are unavailable. Use your source editor.
Only the authorized target body may change; preserve other bodies, all signatures/contracts/types/module metadata and the manifest.
Use the same study check/test for isolated compiler and finite behavioral evaluation. No test source or solution hints are available.
Native source projection can remain unchanged; final evaluation consumes authoritative AIR. Preview/check do not prove behavioral correctness.
One turn; 80 total model tools, 480 seconds active-turn observation, 600000 cumulative reported-token threshold, 20 seconds interrupt grace.
Use finish for final handoff. This does not auto-commit Native staging. Do not alter tests or specifications.
"""
TOOLS = [{"name": "study", "description": (
    "Remote isolated source/read/check workbench. arguments is a JSON-encoded object. "
    "revision:{} returns current revision and input file paths. "
    "read:{revision,path,start?:1,count?:120} reads up to 200 exact source lines with EOF/next_start. "
    "search:{revision,text}; diff:{revision} gives ordinary Git diff in T, authority summary in N. "
    "T edit:{revision,path,old,new} replaces one unique exact source span; "
    "T write:{revision,path,content} replaces the complete allowed source file. "
    "check:{}, test:{} run isolated checks and independent goal/regression tests with bounded combined feedback. "
    "doc:{path} reads language.md, SKILL.md, references/workflow.md, references/diagnostics.md or references/examples.md in BOTH arms. "
    "finish:{} hands off final authority, not uncommitted Native staging. No shell, evaluator access or arbitrary files."),
    "inputSchema": {"type": "object", "properties": {"action": {"type": "string", "enum": [
        "revision", "read", "search", "diff", "edit", "write", "check", "test", "doc", "finish"]},
        "arguments": {"type": "string"}}, "required": ["action", "arguments"], "additionalProperties": False}}]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, indent=2, ensure_ascii=True).encode() + b"\n")


def scoped_empty_options():
    # Same restrictions as P31, but no semantic server for source condition.
    example = scoped_server(sys.executable, ["unused"], enabled_tools=list(NAMES))
    opts = host_options(example)
    return opts[:-2] + ["-c", "mcp_servers={}"]


class Slot:
    def __init__(self, runtime, entry, frozen, args):
        self.path = runtime / entry["id"]
        self.path.mkdir(parents=True, exist_ok=False)
        self.entry, self.frozen = entry, frozen
        self.remote = Remote(args.connection)
        self.task = frozen["tasks"][entry["task"]]
        self.service = HERE / "service.py"
        self.ready, self.evidence = self.path / "ready.json", self.path / "linux.json"
        self.instance = uuid.uuid4().hex
        self.state = self.remote.path(self.path / ("owner-" + self.instance))
        self.ipc_path = "/tmp/alva-mic-" + self.instance + ".sock"
        self.process = None
        self.config = {"bundle": self.task["bundle"], "arm": entry["arm"], "task": self.task, "ipc_path": self.ipc_path,
            "vectors": [], "docs": frozen["docs"], "ready": self.remote.path(self.ready),
            "evidence": self.remote.path(self.evidence), **self.remote.cfg["sdk_paths"]}
        save(self.path / "config.json", self.config)
        self.remote.put(self.path / "config.json")
        try:
            owner = self.remote.root + "/benchmarks/maintenance_interface_comparison/owner.py"
            self.process = subprocess.Popen(self.remote.argv(["python3", owner, "serve", "--state", self.state,
                "--instance", self.instance, "--", "python3", self.remote.path(self.service), "--role", "server",
                "--config", self.remote.path(self.path / "config.json")]),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    _, err = self.process.communicate(timeout=2)
                    save(self.path / "startup-error.json", {"stderr": err.decode(errors="replace")})
                    raise RuntimeError("SERVICE_EXIT_BEFORE_READY:" + err.decode(errors="replace")[:800])
                if self.remote.run(["test", "-f", self.remote.path(self.ready)], timeout=3).returncode == 0:
                    return
                time.sleep(.1)
            raise RuntimeError("SERVICE_READY_TIMEOUT")
        except BaseException:
            self.cleanup()
            raise

    def control(self, action, args):
        result = self.remote.checked(["python3", self.remote.path(self.service), "--role", "control",
            "--config", self.remote.path(self.ready)], input=json.dumps({"action": action, "arguments": args}), timeout=180)
        return json.loads(result)

    def dispatch(self, action, detail):
        if action == "doc":
            return {"content": self.frozen["docs"][detail["path"]]} if detail.get("path") in self.frozen["docs"] else {"error": "DOC_PATH_NOT_ALLOWED"}
        if action in ("check", "test", "finish"):
            if detail:
                return {"error": "EXPECTED_EMPTY_ARGUMENTS"}
            return self.control(action, detail)
        if action not in ("revision", "read", "search", "diff", "edit", "write"):
            return {"error": "UNKNOWN_ACTION"}
        if self.entry["arm"] == "T":
            return self.control("edit" if action in ("edit", "write") else "read", dict(detail, _action=action))
        if action in ("edit", "write"):
            return {"error": "NATIVE_MUTATION_REQUIRED"}
        current = self.control("snapshot", {})["files"]
        source = {p: base64.b64decode(current[p]) for p in self.task["input_paths"]}
        revision = sha(canonical([(p, sha(source[p])) for p in self.task["input_paths"]]))
        if action == "revision":
            return {"revision": revision, "files": self.task["input_paths"], "authority": "AIR" if "alva-air/current" in current else "SOURCE"}
        if detail.get("revision") != revision:
            return {"error": "STALE_REVISION", "current_revision": revision}
        if action == "search":
            return {"revision": revision, "matches": [{"path": p, "line": i, "text": line} for p in source
                for i, line in enumerate(source[p].decode().splitlines(), 1) if detail["text"] in line]}
        if action == "diff":
            return {"revision": revision, "note": "Use preview_semantic_diff for staged Native changes; source projection is not AIR authority.",
                    "authority_sha256": {p: sha(base64.b64decode(b)) for p, b in current.items() if p.startswith("alva-air/")}}
        if detail.get("path") not in source:
            return {"error": "PATH_NOT_ALLOWED"}
        lines = source[detail["path"]].decode().splitlines(keepends=True)
        start, count = detail.get("start", 1), detail.get("count", 120)
        if type(start) is not int or type(count) is not int or not 1 <= start <= max(1, len(lines)) or not 1 <= count <= 200:
            return {"error": "INVALID_READ_RANGE"}
        end = min(len(lines), start + count - 1)
        return {"revision": revision, "content": "".join(lines[start - 1:end]), "eof": end == len(lines),
                "next_start": None if end == len(lines) else end + 1}

    def cleanup(self):
        ack = self.remote.cleanup_owned(self.state, self.instance)
        self.remote.checked(["python3", "-c", "import os,stat,sys;p=sys.argv[1];s=os.lstat(p) if os.path.lexists(p) else None;assert s is None or (stat.S_ISSOCK(s.st_mode) and s.st_uid==os.getuid());os.unlink(p) if s else None", self.ipc_path])
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.communicate(timeout=5)
        save(self.path / "cleanup.json", ack)
        return ack

    def close(self):
        try:
            self.control("stop", {})
            if self.process:
                self.process.communicate(timeout=30)
        finally:
            self.cleanup()
        self.remote.get(self.evidence)


def host(slot):
    slot.context = tempfile.TemporaryDirectory(prefix="alva-mic-auth-context-")
    home = Path(slot.context.name)
    auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if not auth.is_file():
        raise RuntimeError("AUTHENTICATED_CLI_UNAVAILABLE")
    os.link(auth, home / "auth.json")  # No credential reading/copying/hashing.
    workspace = home / "workspace"
    workspace.mkdir()
    for name, content in slot.frozen["docs"].items():
        if name == "language.md":
            target = workspace / name
        else:
            target = workspace / ".agents/skills/alva" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode())
    env = dict(os.environ, CODEX_HOME=str(home))
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CODEX_PERMISSION_PROFILE", None)
    if slot.entry["arm"] == "N":
        server = scoped_server(sys.executable, [str(HERE / "relay.py"), "--connection", str(slot.remote.connection),
            "--ready", slot.remote.path(slot.ready)], enabled_tools=list(NAMES))
        options = host_options(server)
    else:
        options = scoped_empty_options()
    h = old.transport.AppServer(shutil.which("codex"), env, workspace, extra_args=options)
    slot.host = h
    c = old.Controller(h)
    try:
        c.rpc("initialize", {"clientInfo": {"name": "alva-mic01", "version": "1"}, "capabilities": {"experimentalApi": True}})
        h.send({"method": "initialized", "params": {}})
        thread = c.rpc("thread/start", {"cwd": str(workspace), "approvalPolicy": "never", "sandbox": "read-only",
            "ephemeral": True, "model": slot.frozen["model"], "dynamicTools": TOOLS,
            "developerInstructions": INSTRUCTIONS + "\nCondition: " + slot.entry["arm"]})
        assert thread["model"] == slot.frozen["model"] and thread["modelProvider"] == slot.frozen["provider"]
        inventory = c.rpc("mcpServerStatus/list", {"threadId": thread["thread"]["id"]}, timeout=120)["data"]
        inventory = [s for s in inventory if s.get("tools")]
        if slot.entry["arm"] == "N":
            assert len(inventory) == 1 and set(inventory[0]["tools"]) == set(NAMES)
        else:
            assert not inventory
        parsed = c.rpc("config/read", {"includeLayers": False})["config"]
        assert parsed["approval_policy"] == "never" and thread["sandbox"]["type"] == "readOnly"
        save(slot.path / "host-validation.json", {"thread_id": thread["thread"]["id"], "model": thread["model"],
            "provider": thread["modelProvider"], "native_inventory": inventory, "approval": parsed["approval_policy"],
            "sandbox": thread["sandbox"], "model_generation_calls": 0})
        return h, c, thread
    except BaseException:
        h.close()
        raise


def score(task, evidence):
    a, b = evidence.get("initial_authority", {}), evidence.get("final_authority", {})
    final = evidence.get("final", {})
    if not a.get("functions") or not b.get("functions"):
        return {"correct": False, "scope": "UNKNOWN", "goal": final.get("goal", {}).get("status"),
                "regression": final.get("regression", {}).get("status"), "reason": "unreadable candidate structure"}
    from benchmarks.p38_authorized_effect_contract.mechanisms import structural
    footprint = structural(a, b, task["policy"]["authorized_functions"])
    changed = task["public_task"]["target"] in footprint["changed"]
    snapshot = {p: base64.b64decode(v) for p, v in evidence["final_files"].items()}
    digest = sha(canonical({p: sha(v) for p, v in snapshot.items()}))
    bound = digest == final.get("tested_snapshot_sha256")
    return {"correct": bool(final.get("status") == "PASS" and footprint["status"] == "ALLOW" and changed and bound),
        "scope": footprint["status"], "structural": footprint, "target_changed": changed,
        "goal": final.get("goal", {}).get("status"), "regression": final.get("regression", {}).get("status"),
        "tested_snapshot_sha256": digest, "exact_test_receipt_matches": bound,
        "fresh_project_revision": b.get("project_revision"), "air_published": "alva-air/current" in snapshot}


def check_runtime(frozen, remote):
    for name, digest in frozen["runtime_files"].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    remote_hashes = json.loads(remote.checked(["python3", "-c", "import sys,json,hashlib,pathlib;r=pathlib.Path(sys.argv[1]);print(json.dumps({p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in json.load(sys.stdin)}))",
        remote.root], input=json.dumps(list(frozen["runtime_files"]))))
    assert remote_hashes == frozen["runtime_files"]
    assert sha(Path(shutil.which("codex")).read_bytes()) == frozen["codex_binary_sha256"]


def run(args):
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    assert frozen["preflight_status"] == "PASS"
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
    remote = Remote(args.connection)
    check_runtime(frozen, remote)
    root = ROOT / ".local/mic01"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "GENERATION-STARTED.json").open("x") as stream:
        json.dump({"freeze_sha256": sha((HERE / "FREEZE.json").read_bytes()), "maximum_slots": 24}, stream)
    runtime = root / "wave01"
    runtime.mkdir(exist_ok=False)
    rows = []
    for entry in frozen["schedule"]:
        record = {"id": entry["id"], "task": entry["task"], "arm": entry["arm"], "repeat": entry["repeat"], "model_tasks_started": 0}
        slot = h = c = None
        print("START " + entry["id"], flush=True)
        try:
            slot = Slot(runtime, entry, frozen, args)
            h, c, thread = host(slot)
            task = slot.task["public_task"]
            prompt = json.dumps(task, ensure_ascii=False) + "\nProject: /work/project/alva.toml. Inspect original source; satisfy the task within its authorized body, check/test and finish. Documentation is available through study doc."
            request = {"threadId": thread["thread"]["id"], "input": [{"type": "text", "text": prompt}],
                "effort": frozen["effort"], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly"}}
            save(slot.path / "turn-start.json", request)
            record["model_tasks_started"] = 1
            turn = c.rpc("turn/start", request)
            c.bind(thread, turn)
            with patch.object(old, "CONFIG", frozen["limits"]):
                old.drive(c, slot, record)
        except Exception as exc:
            record["infrastructure_hold"] = type(exc).__name__ + ":" + str(exc)[:1800]
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
                try:
                    h.close()
                except Exception as exc:
                    record["infrastructure_hold"] = "HOST_CLEANUP:" + str(exc)
            if slot:
                try:
                    slot.close()
                except Exception as exc:
                    record["infrastructure_hold"] = "SERVICE_CLEANUP:" + str(exc)
                if hasattr(slot, "context"):
                    slot.context.cleanup()
        if slot and slot.evidence.exists():
            evidence = json.loads(slot.evidence.read_text())
            record["outcome"] = score(slot.task, evidence)
            if record.get("infrastructure_hold") or record.get("terminal_status") != "completed":
                record["outcome"]["correct"] = False
        save(runtime / entry["id"] / "record.json", record)
        row = {k: v for k, v in record.items() if k != "events"}
        rows.append(row)
        save(runtime / "RESULTS.json", {"status": "INFRASTRUCTURE_HOLD" if record.get("infrastructure_hold") else "RUNNING",
            "rows": rows, "scheduled": 24, "model_tasks_started": sum(r["model_tasks_started"] for r in rows)})
        print("SLOT_RESULT=" + json.dumps(row), flush=True)
        if record.get("infrastructure_hold"):
            break
    final = {"status": "COMPLETED" if len(rows) == 24 and not rows[-1].get("infrastructure_hold") else "INFRASTRUCTURE_HOLD",
        "rows": rows, "scheduled": 24, "model_tasks_started": sum(r["model_tasks_started"] for r in rows)}
    save(runtime / "RESULTS.json", final)
    print("BATCH_RESULT=" + json.dumps(final), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", required=True, type=Path)
    run(p.parse_args())
