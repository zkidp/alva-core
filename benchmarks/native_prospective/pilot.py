"""Prospective batch only. Existing AppServer/P21 controller/P22/P23 reused.

No old model outputs, engineering solutions or evaluation source are mounted
in the model working directory. All untrusted compilation stays in Linux.
"""

import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import queue
import random
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git, decode, canonical, sha
from benchmarks.cross_language.controller import (
    Controller,
    InfrastructureError,
    simulated_validation,
)

spec = importlib.util.spec_from_file_location(
    "transport", ROOT / "tests/integrations/codex_native_test.py"
)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)

BASE = "ba9d85a69e827a046d79bc3740ed8b2a3c26490d"
INPUT_BASE = "837226e69262d37c6e5fd5af5465790066bd7211"
CONFIG = {
    "model": "gpt-5.6-sol",
    "provider": "openai",
    "effort": "low",
    "wall_observation_seconds": 480,
    "tool_callback_limit": 80,
    "token_observation_threshold": 120000,
    "interrupt_grace_seconds": 20,
    "hard_provider_token_cap": False,
    "concurrency": 1,
    "model_turns_per_slot": 1,
    "provider_generation_requests": None,
}
TOOLS = [
    {
        "name": "study",
        "description": "Read/edit the candidate, run its check/test, or invoke public AEP. Arguments is a JSON-encoded object. read/edit: {path,content?}. aep: any native request with tool; project is host-bound. doc: {path} from supplied official references. finish: {}. No shell/network/reference access.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "edit", "check", "test", "aep", "doc", "finish"],
                },
                "arguments": {"type": "string"},
            },
            "required": ["action", "arguments"],
            "additionalProperties": False,
        },
    }
]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def linux(path):
    path = str(Path(path).resolve()).replace("\\", "/")
    if path[1:3] != ":/":
        raise ValueError("Explicit Windows to WSL path required")
    return "/mnt/" + path[0].lower() + path[2:]


def wsl(argv, **kwargs):
    return subprocess.run(
        ["wsl.exe", "-d", "Ubuntu-26.04", "--exec", *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        **kwargs,
    )


def sdk_identity(args):
    code = """import hashlib,json,pathlib,sys,subprocess
r={}
for label,root in zip(("binary","toolchain","registry"),sys.argv[1:]):
 p=pathlib.Path(root); rows=[]
 for f in sorted(p.rglob("*")) if p.is_dir() else [p]:
  if f.is_file(): rows.append((f.relative_to(p).as_posix() if p.is_dir() else "alva",hashlib.sha256(f.read_bytes()).hexdigest()))
 r[label]={"sha256":hashlib.sha256(json.dumps(rows,separators=(",",":")).encode()).hexdigest(),"files":len(rows)}
r["python"]=sys.version
r["bwrap"]=subprocess.check_output(["bwrap","--version"],text=True).strip()
print(json.dumps(r))"""
    p = wsl(["python3", "-I", "-c", code, args.alva, args.toolchain, args.registry])
    if p.returncode:
        raise InfrastructureError("Approved SDK identity failed: " + p.stderr[-1000:])
    return json.loads(p.stdout)


def bundle_case(case):
    original = pack_git(
        ROOT,
        INPUT_BASE,
        [
            f"benchmarks/native_mcp_skill/inputs/{case}/{p}"
            for p in ("alva.toml", "src/task.alva")
        ],
    )
    # Explicit transport relocation only; exact source bytes unchanged.
    for entry in original["payload"]["entries"]:
        entry["path"] = entry["path"].split(f"/{case}/", 1)[1]
    original["payload_sha256"] = sha(canonical(original["payload"]))
    return original


class Slot:
    def __init__(self, runtime, entry, frozen, args):
        self.path = runtime / entry["id"]
        self.path.mkdir(parents=True, exist_ok=False)
        self.ready = self.path / "ready.json"
        self.entry = entry
        self.frozen = frozen
        self.calls = 0
        self.evidence = self.path / "linux.json"
        self.service = ROOT / "benchmarks/native_prospective/service.py"
        self.config = {
            "bundle": frozen["tasks"][entry["task"]]["bundle"],
            "arm": entry["arm"],
            "vectors": frozen["tasks"][entry["task"]]["vectors"],
            "docs": frozen["docs"],
            "ready": linux(self.ready),
            "evidence": linux(self.evidence),
            "alva": args.alva,
            "toolchain": args.toolchain,
            "registry": args.registry,
        }
        save(self.path / "config.json", self.config)
        self.process = subprocess.Popen(
            [
                "wsl.exe",
                "-d",
                "Ubuntu-26.04",
                "--exec",
                "python3",
                linux(self.service),
                "--role",
                "server",
                "--config",
                linux(self.path / "config.json"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 30
        while not self.ready.exists():
            if self.process.poll() is not None:
                raise InfrastructureError(
                    "Linux service exited: "
                    + self.process.communicate()[1].decode(errors="replace")[-2000:]
                )
            if time.monotonic() > deadline:
                self.process.kill()
                raise InfrastructureError("Linux service startup timeout")
            time.sleep(0.05)

    def dispatch(self, action, arguments):
        p = wsl(
            [
                "python3",
                linux(self.service),
                "--role",
                "control",
                "--config",
                linux(self.ready),
            ],
            input=json.dumps({"action": action, "arguments": arguments}),
        )
        if p.returncode:
            raise InfrastructureError("Slot service RPC: " + p.stderr[-2000:])
        return json.loads(p.stdout)

    def close(self):
        if hasattr(self, "host") and self.host.process.poll() is None:
            self.host.close()
        if hasattr(self, "host_home"):
            self.host_home.cleanup()
        try:
            self.dispatch("stop", {})
            stdout, stderr = self.process.communicate(timeout=150)
            if self.process.returncode:
                raise InfrastructureError(
                    "Linux cleanup/evaluation failed: "
                    + stderr.decode(errors="replace")[-2000:]
                )
        except BaseException:
            self.process.kill()
            self.process.communicate(timeout=10)
            raise


def host(slot, generation=False):
    empty = slot.path / "model"
    empty.mkdir(exist_ok=True)
    env = dict(os.environ)
    # Isolate all configuration/catalogues, not merely tools/list metadata.
    # The authenticated CLI alone consumes its existing credential through a
    # temporary filesystem link. Never read/copy/hash/log/archive its bytes.
    slot.host_home = tempfile.TemporaryDirectory(prefix="alva-codex-auth-context-")
    auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if not auth.is_file():
        raise InfrastructureError(
            "Authenticated CLI credential file unavailable; no credential discovery"
        )
    os.link(auth, Path(slot.host_home.name) / "auth.json")
    env["CODEX_HOME"] = slot.host_home.name
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CODEX_PERMISSION_PROFILE", None)
    # Per-process config only: no user installation/configuration/credentials copied.
    opts = [
        "-c",
        "features.plugins=false",
        "-c",
        "features.apps=false",
        "-c",
        "features.shell_tool=false",
        "-c",
        'web_search="disabled"',
        "-c",
        "mcp_servers={}",
        "-c",
        'approval_policy="never"',
        "-c",
        'windows.sandbox="unelevated"',
    ]
    if slot.entry["arm"] == "N":
        skill = empty / ".agents/skills/alva"
        for path, text in slot.frozen["docs"].items():
            target = skill / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode())
        cfg = {
            "alva": {
                "command": "wsl.exe",
                "args": [
                    "-d",
                    "Ubuntu-26.04",
                    "--exec",
                    "python3",
                    linux(slot.service),
                    "--config",
                    linux(slot.ready),
                ],
                "required": True,
                "tool_timeout_sec": 120,
            }
        }
        # JSON is TOML-compatible only for scalars/arrays; inline table rendered explicitly.
        server = cfg["alva"]
        rendered = (
            '{alva={command="wsl.exe",args='
            + json.dumps(server["args"])
            + ",required=true,tool_timeout_sec=120}}"
        )
        opts += ["-c", "mcp_servers=" + rendered]
    h = transport.AppServer(shutil.which("codex"), env, empty, extra_args=opts)
    slot.host = h
    c = Controller(h)
    c.rpc(
        "initialize",
        {
            "clientInfo": {"name": "alva-native-prospective", "version": "1"},
            "capabilities": {"experimentalApi": True},
        },
    )
    h.send({"method": "initialized", "params": {}})
    instructions = (
        "Use only study and, in N, the ALVA native MCP tools. No shell, apply_patch, web, other directories, sessions or delegation. "
        "The candidate is /work/project/alva.toml inside Linux isolation; it is NOT your Windows working directory. "
        "Use study check/test for isolated compiler/build/independent evaluation. No host execution. "
        "T uses source editing only; B uses the aep action with persistent CLI Gateway requests; N uses native MCP only for mutations. "
        "Do not read any references except the official Skill/docs supplied in N. "
        "One task turn; at most 80 tool calls, 480 seconds, 120000 observed tokens (not a hard provider cap)."
    )
    thread = c.rpc(
        "thread/start",
        {
            "cwd": str(empty),
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
            "model": CONFIG["model"],
            "dynamicTools": TOOLS,
            "developerInstructions": instructions,
        },
    )
    if (
        thread["model"] != CONFIG["model"]
        or thread["modelProvider"] != CONFIG["provider"]
    ):
        h.close()
        raise InfrastructureError("Frozen model/provider mismatch")
    try:
        inventory = c.rpc(
            "mcpServerStatus/list", {"threadId": thread["thread"]["id"]}, timeout=120
        )["data"]
    except queue.Empty as exc:
        raise InfrastructureError(
            "MCP inventory timeout: " + str(h.errors[-5:])
        ) from exc
    inventory = [s for s in inventory if s.get("tools")]
    if slot.entry["arm"] == "N":
        if (
            len(inventory) != 1
            or inventory[0]["name"] != "alva"
            or inventory[0].get("toolsError")
        ):
            h.close()
            raise InfrastructureError(
                "Unapproved/missing native tool inventory: "
                + str(
                    [
                        {k: s.get(k) for k in ("name", "enabled", "toolsError")}
                        for s in inventory
                    ]
                )
            )
        skills = c.rpc("skills/list", {"cwds": [str(empty)], "forceReload": True})
        if not any(
            s["name"] == "alva" and s.get("enabled")
            for row in skills["data"]
            for s in row["skills"]
        ):
            h.close()
            raise InfrastructureError("Official Skill not discovered")
    elif inventory:
        h.close()
        raise InfrastructureError("Unexpected MCP inventory in T/B")
    return h, c, thread, inventory


def drive(c, slot, record):
    start = time.monotonic()
    interruption = None
    seen = set()
    native_items = set()
    record.update(
        tool_calls=0, usage=None, terminal_status=None, interrupt_ack=False, events=[]
    )
    while True:
        now = time.monotonic()
        if interruption is None and now - start >= CONFIG["wall_observation_seconds"]:
            interruption = now
            record["stop_reason"] = "WALL_OBSERVATION_LIMIT"
            c.interrupt()
        if interruption and now - interruption >= CONFIG["interrupt_grace_seconds"]:
            raise InfrastructureError("TERMINATION_UNCONFIRMED")
        try:
            msg = c.next(0.5)
        except queue.Empty:
            continue
        if msg is None:
            raise InfrastructureError("HOST_EXIT_WITHOUT_TERMINAL")
        method = msg.get("method")
        # Retain observable tools/usage/status, not hidden reasoning deltas.
        if method not in (
            "item/reasoning/textDelta",
            "item/reasoning/summaryTextDelta",
            "item/agentMessage/delta",
        ):
            if method and (
                "reasoning" in method.lower()
                or "reasoning"
                in str(msg.get("params", {}).get("item", {}).get("type", "")).lower()
            ):
                pass
            else:
                record["events"].append(msg)
        terminal = c.observe(msg)
        if terminal:
            record["terminal_status"] = terminal
            record.setdefault("stop_reason", "NATURAL_" + terminal.upper())
            break
        if method == "thread/tokenUsage/updated":
            record["usage"] = msg["params"]["tokenUsage"]
            total = record["usage"].get("total", {}).get("totalTokens")
            if type(total) is not int:
                raise InfrastructureError("UNKNOWN_USAGE_SCHEMA")
            if total >= CONFIG["token_observation_threshold"] and interruption is None:
                interruption = time.monotonic()
                record["stop_reason"] = "TOKEN_OBSERVATION_LIMIT"
                c.interrupt()
        elif method == "model/rerouted":
            raise InfrastructureError("FROZEN_MODEL_REROUTED")
        elif method == "item/started":
            item = msg["params"]["item"]
            kind = item["type"]
            if kind == "mcpToolCall" and slot.entry["arm"] == "N":
                native_items.add(item["id"])
                record["tool_calls"] += 1
            elif kind in (
                "commandExecution",
                "fileChange",
                "mcpToolCall",
                "collabToolCall",
                "webSearch",
            ):
                raise InfrastructureError("UNAUTHORIZED_HOST_TOOL:" + kind)
        elif method == "item/tool/call":
            p = msg["params"]
            record["tool_calls"] += 1
            if p["callId"] in seen:
                answer = {"error": "DUPLICATE_CALL_NOT_EXECUTED"}
            elif interruption or record["tool_calls"] > CONFIG["tool_callback_limit"]:
                answer = {"error": "LIMIT_NO_DISPATCH"}
            else:
                seen.add(p["callId"])
                try:
                    if p["tool"] != "study" or not isinstance(p["arguments"], dict):
                        raise ValueError("Unknown tool")
                    action = p["arguments"]["action"]
                    detail = json.loads(p["arguments"]["arguments"])
                    if not isinstance(detail, dict):
                        raise ValueError("Object required")
                except (KeyError, ValueError, TypeError) as exc:
                    answer = {"error": "INVALID_TOOL_ARGUMENTS", "message": str(exc)}
                else:
                    answer = slot.dispatch(action, detail)
            c.host.send(
                {
                    "id": msg["id"],
                    "result": {
                        "success": True,
                        "contentItems": [
                            {"type": "inputText", "text": json.dumps(answer)}
                        ],
                    },
                }
            )
        elif "id" in msg and "method" in msg:
            raise InfrastructureError("UNEXPECTED_SERVER_REQUEST:" + str(method))
        if (
            record["tool_calls"] >= CONFIG["tool_callback_limit"]
            and interruption is None
        ):
            interruption = time.monotonic()
            record["stop_reason"] = "TOOL_LIMIT"
            c.interrupt()
    record.update(
        elapsed_seconds=round(time.monotonic() - start, 3),
        thread_id=c.thread_id,
        turn_id=c.turn_id,
        interrupt_ack=c.interrupt_ack,
        usage_complete=record["usage"] is not None,
    )
    if c.interrupt_id and not c.interrupt_ack:
        # Terminal may precede the reply; wait for the actual interrupt ack.
        deadline = time.monotonic() + 10
        while not c.interrupt_ack and time.monotonic() < deadline:
            try:
                c.observe(c.next(0.5))
            except queue.Empty:
                pass
        record["interrupt_ack"] = c.interrupt_ack
        if not c.interrupt_ack:
            raise InfrastructureError("INTERRUPT_UNACKNOWLEDGED")


def setup(args):
    # No import of old reference implementations into any candidate.
    selection = json.loads(
        (ROOT / "benchmarks/native_mcp_skill/SELECTION.json").read_text()
    )
    task_module = {}
    exec(
        compile(
            subprocess.check_output(
                ["git", "show", INPUT_BASE + ":benchmarks/cross_language/tasks.py"],
                cwd=ROOT,
            ),
            "public-vectors",
            "exec",
        ),
        task_module,
    )
    tasks = {}
    for task in selection["tasks"]:
        vectors = next(
            t["vectors"]
            for t in task_module["TASKS"]
            if "HE" + str(t["id"]) == task["id"]
        )
        tasks[task["id"]] = {
            "public": task,
            "bundle": bundle_case(task["id"]),
            "vectors": vectors,
        }
    docs = {}
    for name in (
        "SKILL.md",
        "references/workflow.md",
        "references/diagnostics.md",
        "references/examples.md",
    ):
        docs[name] = subprocess.check_output(
            ["git", "show", BASE + ":integrations/skills/alva/" + name], cwd=ROOT
        ).decode()
    order = [(task, arm) for task in tasks for arm in ("T", "B", "N")]
    random.Random(250126).shuffle(order)
    schedule = [
        {"id": f"P26-{i:02d}-{task}-{arm}", "task": task, "arm": arm}
        for i, (task, arm) in enumerate(order, 1)
    ]
    return {
        "base": BASE,
        "input_base": INPUT_BASE,
        "config": CONFIG,
        "tools": TOOLS,
        "tasks": tasks,
        "docs": docs,
        "schedule": schedule,
        "controller": simulated_validation(),
        "source": selection["source"],
        "license": selection["license"],
    }


def prompt(slot, frozen):
    task = frozen["tasks"][slot["task"]]
    src = decode(task["bundle"], task["bundle"]["payload_sha256"])
    text = (
        "Implement bench.solve for this public adapted HumanEval task.\n"
        + task["public"]["requirement"]
        + "\nCandidate manifest: /work/project/alva.toml. Initial source:\n"
        + src["src/task.alva"].decode()
        + "\nCondition "
        + slot["arm"]
        + ". T: ordinary source edits. B: persistent public CLI Gateway through study aep; begin_transaction with project host-bound. N: native MCP operations and official ALVA Skill. "
        "Use study check/test for isolated checking and independent behavior feedback. Finish when done. "
        "Limits: 80 tools, 480 wall seconds, 120000 observed total tokens, no retry. No host shell, internet or other sessions."
    )
    if slot["arm"] == "N":
        text += "\n$alva\nComplete official Skill and references follow verbatim:\n"
        for name, body in frozen["docs"].items():
            text += "\n--- " + name + " ---\n" + body
    return text


def main(args):
    runtime = ROOT / ".local/native-prospective" / args.attempt
    if args.mode == "prepare":
        runtime.mkdir(parents=True, exist_ok=False)
        frozen = setup(args)
        save(runtime / "draft.json", frozen)
        # Capability/transport validation, not the four old solution witnesses.
        entry = {"id": "preflight-native", "task": "HE41", "arm": "N"}
        slot = Slot(runtime, entry, frozen, args)
        h = None
        try:
            h, c, thread, inventory = host(slot)
            server = inventory[0]
            frozen["native_tools"] = server["tools"]
            response = c.rpc(
                "mcpServer/tool/call",
                {
                    "threadId": thread["thread"]["id"],
                    "server": server["name"],
                    "tool": "begin_transaction",
                    "arguments": {"project": "/work/project/alva.toml"},
                },
            )
            tx = response["structuredContent"]["transaction_id"]
            aborted = c.rpc(
                "mcpServer/tool/call",
                {
                    "threadId": thread["thread"]["id"],
                    "server": server["name"],
                    "tool": "abort_transaction",
                    "arguments": {"transaction_id": tx},
                },
            )
            assert not aborted.get("isError"), aborted
            frozen["host_preflight"] = {
                "native_schema_discovery": "PASS",
                "begin_abort": "PASS",
                "model": thread["model"],
                "provider": thread["modelProvider"],
                "generation_calls": 0,
            }
        finally:
            if h:
                h.close()
            slot.close()
        for arm in ("T", "B"):
            slot = Slot(
                runtime,
                {"id": "preflight-" + arm, "task": "HE41", "arm": arm},
                frozen,
                args,
            )
            h = None
            try:
                h, _, _, inventory = host(slot)
                assert not inventory
                assert "content" in slot.dispatch("read", {"path": "src/task.alva"})
                if arm == "B":
                    assert slot.dispatch("aep", {"tool": "begin_transaction"})["ok"]
                    assert slot.dispatch("aep", {"tool": "abort_transaction"})["ok"]
            finally:
                if h:
                    h.close()
                slot.close()
        for entry in frozen["schedule"]:
            entry["prompt"] = prompt(entry, frozen)
            entry["prompt_sha256"] = sha(entry["prompt"].encode())
        check = wsl(["sha256sum", args.alva])
        assert check.returncode == 0, check.stderr
        frozen["binary_sha256"] = check.stdout.split()[0]
        frozen["codex"] = subprocess.check_output(
            [shutil.which("codex"), "--version"], text=True
        ).strip()
        frozen["python"] = sys.version
        frozen["sdk_identity"] = sdk_identity(args)
        frozen["codex_binary_sha256"] = sha(Path(shutil.which("codex")).read_bytes())
        bind_paths = [p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py")] + [
            "tests/integrations/codex_native_test.py",
            "benchmarks/cross_language/controller.py",
            "benchmarks/native_mcp_skill/proxy.py",
            "integrations/benchmark_runtime_v2/freeze.py",
            "integrations/benchmark_runtime_v2/persistent.py",
            "integrations/benchmark_runtime_v2/sandbox.py",
        ]
        frozen["files"] = {p: sha((ROOT / p).read_bytes()) for p in bind_paths}
        frozen["runtime_byte_policy"] = (
            "Exact frozen runtime UTF-8 bytes, SHA-bound on Windows and WSL mount; no EOL alternatives"
        )
        frozen["runtime_bytes"] = {
            p: base64.b64encode((ROOT / p).read_bytes()).decode() for p in bind_paths
        }
        frozen["status"] = "FROZEN_BEFORE_GENERATION"
        save(HERE / "FREEZE.json", frozen)
        print("FREEZE PASS; commit and push before run")
    else:
        frozen = json.loads((HERE / "FREEZE.json").read_text())
        assert (
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            )
            == ""
        )
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        remote = subprocess.check_output(
            [
                "git",
                "ls-remote",
                "origin",
                "refs/heads/codex/native-mcp-prospective-pilot",
            ],
            cwd=ROOT,
            text=True,
        ).split()[0]
        assert head == remote, "Freeze must be pushed"
        for path, digest in frozen["files"].items():
            assert sha((ROOT / path).read_bytes()) == digest, path
        assert (
            wsl(["sha256sum", args.alva]).stdout.split()[0] == frozen["binary_sha256"]
        )
        assert (
            sdk_identity(args) == frozen["sdk_identity"]
        ), "Approved SDK/runtime changed"
        assert (
            sha(Path(shutil.which("codex")).read_bytes())
            == frozen["codex_binary_sha256"]
        )
        runtime.mkdir(parents=True, exist_ok=True)
        with (runtime / "STARTED.json").open("x") as f:
            json.dump({"freeze_commit": head}, f)
        rows = []
        for entry in frozen["schedule"]:
            record = {
                "id": entry["id"],
                "task": entry["task"],
                "arm": entry["arm"],
                "freeze_commit": head,
                "model_tasks_started": 0,
                "provider_requests": None,
                "dollar_cost": None,
                "hard_token_cap": False,
            }
            slot = h = c = None
            print("START " + entry["id"], flush=True)
            try:
                slot = Slot(runtime, entry, frozen, args)
                h, c, thread, inventory = host(slot, True)
                if (
                    entry["arm"] == "N"
                    and inventory[0]["tools"] != frozen["native_tools"]
                ):
                    raise InfrastructureError("Native schema drift")
                record["model_tasks_started"] = 1
                turn = c.rpc(
                    "turn/start",
                    {
                        "threadId": thread["thread"]["id"],
                        "input": [{"type": "text", "text": entry["prompt"]}],
                        "effort": CONFIG["effort"],
                        "approvalPolicy": "never",
                        "sandboxPolicy": {"type": "readOnly"},
                    },
                )
                c.bind(thread, turn)
                drive(c, slot, record)
            except Exception as exc:
                record["infrastructure_hold"] = type(exc).__name__ + ": " + str(exc)
                if c and c.turn_id:
                    try:
                        c.interrupt()
                        end = time.monotonic() + 20
                        while time.monotonic() < end:
                            terminal = c.observe(c.next(1))
                            if terminal and c.interrupt_ack:
                                break
                    except Exception:
                        record["termination_unconfirmed"] = True
            finally:
                if h:
                    h.close()
                if slot:
                    try:
                        slot.close()
                    except Exception as exc:
                        record["infrastructure_hold"] = "CLEANUP: " + str(exc)
            if slot and slot.evidence.exists():
                evidence = json.loads(slot.evidence.read_text())
                record["final"] = evidence.get("final")
                record["authority_published"] = any(
                    p.startswith("alva-air/") for p in evidence.get("final_files", {})
                )
                record["initial_authority"] = evidence.get("initial_authority")
                record["final_authority"] = evidence.get("final_authority")
                record["target_body_changed"] = (
                    evidence.get("initial_authority", {}).get("body_sha256") is not None
                    and evidence.get("final_authority", {}).get("body_sha256")
                    is not None
                    and evidence["initial_authority"]["body_sha256"]
                    != evidence["final_authority"]["body_sha256"]
                )
                operations = []
                for call in evidence["calls"]:
                    if call.get("request", {}).get("method") == "tools/call":
                        operations.append(
                            (call["request"]["params"]["name"], call["response"])
                        )
                    elif call.get("action") == "aep":
                        operations.append(
                            (call["arguments"].get("tool"), call["response"])
                        )
                record["operation_counts"] = {
                    name: sum(op == name for op, _ in operations)
                    for name, _ in operations
                }
                record["operation_errors"] = sum(
                    bool(
                        answer.get("isError")
                        or answer.get("ok") is False
                        or answer.get("error")
                    )
                    for _, answer in operations
                )
                record["successful_commits"] = sum(
                    op == "commit_transaction"
                    and not answer.get("isError")
                    and answer.get("ok", True) is True
                    for op, answer in operations
                )
                record["authority_changed"] = (
                    record["authority_published"] and record["target_body_changed"]
                )
                if entry["arm"] != "T" and not record["authority_published"]:
                    record["disposition"] = "NO_COMMITTED_CANDIDATE"
                else:
                    record["disposition"] = (record["final"] or {}).get(
                        "status", "UNKNOWN"
                    )
            save(runtime / entry["id"] / "result.json", record)
            rows.append(record)
            save(
                runtime / "progress.json",
                [
                    {
                        k: r.get(k)
                        for k in (
                            "id",
                            "task",
                            "arm",
                            "model_tasks_started",
                            "disposition",
                            "infrastructure_hold",
                        )
                    }
                    for r in rows
                ],
            )
            print(
                "CLOSED " + entry["id"] + " " + record.get("disposition", "UNKNOWN"),
                flush=True,
            )
            if record.get("infrastructure_hold"):
                break
        archive = runtime / "RAW.zip"
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(runtime.rglob("*")):
                if (
                    p.is_file()
                    and p != archive
                    and "model" not in p.relative_to(runtime).parts
                ):
                    z.write(p, p.relative_to(runtime).as_posix())
        # Public summaries only; raw transcripts/candidates remain controlled local artifacts.
        public = [
            {
                k: r.get(k)
                for k in (
                    "id",
                    "task",
                    "arm",
                    "model_tasks_started",
                    "tool_calls",
                    "usage",
                    "usage_complete",
                    "terminal_status",
                    "stop_reason",
                    "elapsed_seconds",
                    "authority_changed",
                    "authority_published",
                    "target_body_changed",
                    "initial_authority",
                    "final_authority",
                    "operation_counts",
                    "operation_errors",
                    "successful_commits",
                    "disposition",
                    "infrastructure_hold",
                )
            }
            for r in rows
        ]
        save(
            HERE / "RESULTS.json",
            {
                "status": (
                    "COMMON_INFRASTRUCTURE_HOLD"
                    if any(r.get("infrastructure_hold") for r in rows)
                    else "CLOSED_COMPLETE"
                ),
                "freeze_commit": head,
                "slots": public,
                "scheduled": 12,
                "executed": sum(r["model_tasks_started"] for r in rows),
            },
        )
        save(
            HERE / "ARCHIVE.json",
            {
                "sha256": sha(archive.read_bytes()),
                "bytes": archive.stat().st_size,
                "entries": len(zipfile.ZipFile(archive).namelist()),
                "controlled_local_only": True,
            },
        )
        print("STOP; no additional slots or retry", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--attempt", default="wave-1")
    parser.add_argument("--alva", required=True)
    parser.add_argument("--toolchain", required=True)
    parser.add_argument("--registry", required=True)
    main(parser.parse_args())
