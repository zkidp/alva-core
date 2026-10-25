"""Frozen sequential app-server batch. Codex owns the agent loop, not this driver.

One fresh turn per declared slot; exclusive started markers prevent replacement.
Only bounded public summaries go to Git; tool records remain in local storage.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/integrations"))
sys.path.insert(0, str(ROOT / "examples/python_guard_codex"))
from codex_native_test import AppServer
from demo import sandbox_policy
from integrations.python_guard.guard import canonical, digest
from integrations.python_guard_codex import CandidateSession, TOOLS
from prepare import RUNTIME, files_manifest, public_files
from tasks import TASKS


def save(path, value):
    path.write_bytes(canonical(value))


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args])


def validate_freeze():
    freeze = json.loads((HERE / "EXECUTION-FREEZE.json").read_bytes())
    assert public_files() == freeze["files"], "frozen public inputs changed"
    assert subprocess.check_output([shutil.which("codex"), "--version"]).decode().strip() == freeze["codex_version"]
    assert digest(Path(sys.executable).read_bytes()) == freeze["python_binary_sha256"]
    assert digest(Path(shutil.which("codex")).read_bytes()) == freeze["codex_binary_sha256"]
    assert all(digest((ROOT / name).read_bytes()) == sha for name, sha in freeze["reused_hashes"].items())
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT) == b"", "commit freeze before execution"
    assert git(ROOT, "rev-parse", "HEAD") == git(ROOT, "rev-parse", "@{upstream}"), "push freeze before execution"
    for row in freeze["schedule"]:
        local = RUNTIME / row["slot"]
        assert digest((local / "approved-policy.json").read_bytes()) == row["policy_sha256"]
        assert digest((local / "prompt.txt").read_bytes()) == row["prompt_sha256"]
        assert files_manifest(local / "source") == row["source_manifest"]
        assert files_manifest(local / "candidate") == row["candidate_manifest"]
        assert git(local / "candidate", "rev-parse", "HEAD").decode().strip() == row["initial_git_commit"]
        assert not (local / "STARTED.json").exists(), "no retries/replacements/resume of a started slot"
        assert files_manifest(local) == row["runtime_manifest"], "actual frozen runtime bytes changed"
    return freeze


def boundary_probe(host, root, candidate):
    protected = [root / "approved-policy.json", root / "source" / "TASK.json"]
    program = ("import errno,json,pathlib,sys; r=[]\n"
        "for s in sys.argv[1:]:\n"
        " try:\n"
        "  with pathlib.Path(s).open('r+b'): pass\n"
        "  r.append(False)\n"
        " except OSError as e:\n"
        "  if e.errno not in (errno.EACCES,errno.EPERM,errno.EROFS): raise\n"
        "  r.append(True)\n"
        "print(json.dumps(r))")
    result = host.request("command/exec", {"command": [sys.executable, "-I", "-c", program, *(str(p) for p in protected)],
        "cwd": str(candidate), "sandboxPolicy": sandbox_policy(candidate), "timeoutMs": 30000})
    assert result["exitCode"] == 0 and json.loads(result["stdout"]) == [True, True], "authority sandbox not enforced"


def evaluate(row, root):
    """Evaluate a new host copy with unchanged evaluator/descriptor, not agent claims."""
    candidate = root / "candidate"
    before = row["source_manifest"]
    # Walk actual tree, including undeclared files, but not declared transient/VCS outputs.
    current = files_manifest(candidate)
    changed = sorted(name for name in before.keys() | current.keys() if before.get(name) != current.get(name))
    task = next(task for task in TASKS if task["id"] == row["task"])
    violations = sorted(set(changed) - set(task["editable"]))
    tree = root / "terminal-evaluation"
    shutil.copytree(root / "source", tree)
    for name in task["editable"]:
        source = candidate / name
        target = tree / name
        if source.is_symlink():
            violations.append(name + ":symlink")
        elif source.exists():
            target.write_bytes(source.read_bytes())
        else:
            target.unlink(missing_ok=True)
    results = {}
    env = {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
           "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(root / "check-scratch"), "USERPROFILE": str(root / "check-scratch")}
    if "SystemRoot" in os.environ:
        env["SystemRoot"] = os.environ["SystemRoot"]
    for group in ("regression", "task"):
        try:
            process = subprocess.run([sys.executable, "-I", "test_pilot.py", group], cwd=tree, env=env,
                                     capture_output=True, timeout=30)
            results[group] = {"status": "PASS" if process.returncode == 0 else "FAIL", "returncode": process.returncode,
                              "stdout_sha256": digest(process.stdout), "stderr_sha256": digest(process.stderr)}
            (root / ("terminal-" + group + ".stdout")).write_bytes(process.stdout)
            (root / ("terminal-" + group + ".stderr")).write_bytes(process.stderr)
        except subprocess.TimeoutExpired:
            results[group] = {"status": "UNKNOWN", "reason": "TIMEOUT"}
    patch = git(candidate, "diff", "--binary")
    (root / "final.patch").write_bytes(patch)
    return {"independent_checks": results, "scope_violations": violations, "changed_paths": changed,
            "task_complete": results["task"]["status"] == "PASS" and results["regression"]["status"] == "PASS" and not violations,
            "regression_introduced": results["regression"]["status"] == "FAIL", "patch_sha256": digest(patch),
            "final_source_manifest": current,
            "original_source_unchanged": files_manifest(root / "source") == row["source_manifest"]}


def one_slot(freeze, row):
    root = RUNTIME / row["slot"]
    candidate = root / "candidate"
    session = CandidateSession(root / "control") if row["arm"] == "B" else None
    started = time.monotonic()
    result = {"slot": row["slot"], "task": row["task"], "arm": row["arm"], "model_turns_started": 0,
              "tool_items": 0, "guard_calls": [], "codex_token_usage": None, "dollar_cost": None,
              "dollar_cost_reason": "Codex subscription host exposes no attributable per-task invoice", "stop_reason": None}
    env = dict(os.environ)
    for key in ("CLAUDE_PROJECT_DIR", "CODEX_PERMISSION_PROFILE"):
        env.pop(key, None)
    config = ["-c", 'sandbox_mode="workspace-write"', "-c", 'approval_policy="never"', "-c", "features.plugins=false"]
    if os.name == "nt":
        config += ["-c", 'windows.sandbox="unelevated"']
    host = AppServer(shutil.which("codex"), env, candidate, extra_args=config)
    raw = (root / "tool-records.jsonl").open("xb")
    thread_id = None
    interrupted = False
    try:
        host.request("initialize", {"clientInfo": {"name": "guard-public-pilot", "version": "1"}, "capabilities": {"experimentalApi": True}})
        host.send({"method": "initialized", "params": {}})
        boundary_probe(host, root, candidate)
        params = json.loads((root / "thread-start-input.json").read_bytes())
        save(root / "thread-start.json", params)
        thread = host.request("thread/start", params)
        assert thread["model"] == freeze["model"], thread.get("model")
        result.update(resolved_model=thread["model"], resolved_provider=thread.get("modelProvider"))
        thread_id = thread["thread"]["id"]
        # Only the transport's fresh thread ID is added after freeze.
        turn = json.loads((root / "turn-start-input.json").read_bytes()) | {"threadId": thread_id}
        save(root / "turn-start.json", turn)
        # Mark immediately before the only generation-bearing call, using exclusive creation.
        with (root / "STARTED.json").open("xb") as marker:
            marker.write(canonical({"freeze_sha256": digest((HERE / "EXECUTION-FREEZE.json").read_bytes()), "slot": row["slot"]}))
        result["model_turns_started"] = 1
        host.request("turn/start", turn)
        deadline = time.monotonic() + freeze["budget"]["wall_seconds"]
        seen = set()
        while True:
            if not interrupted and time.monotonic() >= deadline:
                host.send({"id": 900001, "method": "turn/interrupt", "params": {"threadId": thread_id}})
                interrupted = True
                result["stop_reason"] = "WALL_OBSERVATION_LIMIT"
            if interrupted and time.monotonic() >= deadline + 30:
                break
            try:
                message = host.messages.get(timeout=2)
            except queue.Empty:
                continue
            if message is None:
                raise RuntimeError("common host exited before completed disposition")
            method = message.get("method")
            # Keep tool/evidence/usage data, not reasoning or raw agent transcripts.
            if method in {"item/started", "item/completed"}:
                item = message["params"]["item"]
                if item["type"] in {"commandExecution", "fileChange", "dynamicToolCall", "mcpToolCall"}:
                    raw.write(canonical(message) + b"\n")
                    if method == "item/started":
                        result["tool_items"] += 1
            if method == "thread/tokenUsage/updated":
                result["codex_token_usage"] = message["params"]["tokenUsage"]["total"]
                raw.write(canonical(message) + b"\n")
            elif method == "item/tool/call":
                p = message["params"]
                assert session is not None, "unexpected Guard tool in A"
                if p["callId"] in seen:
                    raise RuntimeError("duplicate Guard callback: no blind reexecution")
                seen.add(p["callId"])
                if len(result["guard_calls"]) >= freeze["budget"]["guard_calls"]:
                    output = {"success": False, "contentItems": [{"type": "inputText", "text": "GUARD_CALL_LIMIT"}]}
                else:
                    output = session.tool_call(p["tool"], p["arguments"])
                    content = json.loads(output["contentItems"][0]["text"]) if output["success"] else {}
                    result["guard_calls"].append({"tool": p["tool"], "success": output["success"],
                        "checks_status": content.get("checks_status"), "applicability_status": content.get("applicability_status"),
                        "candidate_matches_verified_patch": content.get("candidate_matches_verified_patch")})
                raw.write(canonical({"request": p, "response": output}) + b"\n")
                host.send({"id": message["id"], "result": output})
            elif method == "turn/completed":
                result["turn_status"] = message["params"]["turn"]["status"]
                result["stop_reason"] = result["stop_reason"] or result["turn_status"].upper()
                break
            elif "id" in message and method:
                raise RuntimeError("unexpected approval request; no authority expansion")
            usage = result["codex_token_usage"]
            over_tokens = usage and usage["totalTokens"] >= freeze["budget"]["observed_provider_tokens_interrupt_threshold"]
            if not interrupted and (result["tool_items"] >= freeze["budget"]["tool_item_observation_limit"] or over_tokens):
                host.send({"id": 900001, "method": "turn/interrupt", "params": {"threadId": thread_id}})
                interrupted = True
                deadline = time.monotonic()
                result["stop_reason"] = "TOKEN_OBSERVATION_LIMIT" if over_tokens else "TOOL_OBSERVATION_LIMIT"
    except Exception as exc:
        result["stop_reason"] = "COMMON_INFRASTRUCTURE_HOLD"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc).replace(str(ROOT), "<checkout>")[:1500]
    finally:
        raw.close()
        host.close()
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result.update(evaluate(row, root))
    if session and (root / "control/last-verification.json").exists():
        try:
            report = session.report()
            result["terminal_guard"] = {key: report[key] for key in (
                "checks_status", "applicability_status", "candidate_matches_verified_patch")}
        except Exception as exc:
            result["terminal_guard"] = {"checks_status": "UNKNOWN", "reason": type(exc).__name__}
    result["archive_manifest"] = files_manifest(root)
    # Public result manifests contain hashes, not tool-output text, source patches or machine paths.
    save(root / "result.json", result)
    return result


def main():
    freeze = validate_freeze()
    results = []
    (HERE / "results").mkdir(exist_ok=True)
    for row in freeze["schedule"]:
        print(json.dumps({"slot": row["slot"], "status": "STARTING"}), flush=True)
        result = one_slot(freeze, row)
        save(HERE / "results" / (row["slot"] + ".json"), result)
        results.append(result)
        save(HERE / "RESULTS.json", results)
        print(json.dumps({"slot": row["slot"], "status": "CLOSED", "stop_reason": result["stop_reason"]}), flush=True)
        if result["stop_reason"] == "COMMON_INFRASTRUCTURE_HOLD" or not result["original_source_unchanged"]:
            break
    print(json.dumps({"closed_slots": len(results), "scheduled": len(freeze["schedule"])}), flush=True)


if __name__ == "__main__":
    main()
