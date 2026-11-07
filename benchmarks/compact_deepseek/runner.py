"""One fresh tool conversation per slot; no retries or operator recovery."""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

from benchmarks.compact_deepseek.api import API, ProviderFault, totals, usage
from benchmarks.compact_deepseek.runtime import Slot
from benchmarks.compact_maintenance.contract import study_tools, NATIVE_TOOLS
from benchmarks.maintenance_interface_comparison import pilot as prior
from benchmarks.p36_mm02_native_model.remote import Remote
from integrations.benchmark_runtime_v2.freeze import sha, canonical

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, indent=2, ensure_ascii=True).encode() + b"\n")


def model_result(value):
    if isinstance(value, dict) and "structuredContent" in value:
        # Preserve error status and all structured fields once. Raw MCP wire
        # receipts stay in the private backend log, without duplicating the
        # same result as text+structuredContent in model context.
        return {"isError": bool(value.get("isError")), "structuredContent": value["structuredContent"]}
    return value


def bounded_request(api, payload, seconds):
    result = queue.Queue()
    def invoke():
        try:
            result.put((True, api.request("/chat/completions", payload, timeout=min(90, seconds))))
        except BaseException as exc:
            result.put((False, exc))
    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    try:
        ok, value = result.get(timeout=seconds)
    except queue.Empty:
        # The API supplies no cancel/terminal acknowledgment for this HTTP
        # call. Never claim generation stopped or retry/launch another slot.
        raise ProviderFault("ACTIVE_DEADLINE_PROVIDER_TERMINATION_UNCONFIRMED") from None
    if not ok:
        raise value
    return value


def conversation(api, slot, frozen, record):
    tools = study_tools(slot.entry["arm"])
    if slot.native:
        tools += slot.native.schemas
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
               "parameters": t["inputSchema"]}} for t in tools]
    if tools != frozen["provider_tools"][slot.entry["arm"]]:
        raise RuntimeError("TOOL_SCHEMA_FREEZE_MISMATCH")
    allowed = {t["function"]["name"] for t in tools}
    messages = [{"role": "system", "content": frozen["developer_instructions"] + "\nCondition: " + slot.entry["arm"]},
                {"role": "user", "content": json.dumps(slot.task["public_task"], ensure_ascii=False)
                    + "\nProject: /work/project/alva.toml. Inspect source, satisfy the authorized task, check/test and finish."}]
    record["initial_messages"] = messages.copy()
    record["responses"], record["tool_events"], record["usage_reports"] = [], [], []
    record["observed_tool_calls"], record["dispatched_tool_calls"] = 0, 0
    record["submitted_chat_requests"] = 0
    start = time.monotonic()
    try:
        while True:
            remaining = frozen["limits"]["wall_observation_seconds"] - (time.monotonic() - start)
            total = totals(record["usage_reports"])["totalTokens"]
            if remaining <= 0 or (total is not None and total >= frozen["limits"]["token_observation_threshold"]):
                record["stop_reason"] = "OBSERVATION_LIMIT_BETWEEN_REQUESTS"
                break
            payload = {"model": frozen["model"], "messages": messages, "tools": tools, **frozen["api_parameters"]}
            request_hash = sha(json.dumps(payload, ensure_ascii=True).encode())
            record["submitted_chat_requests"] += 1
            response = bounded_request(api, payload, remaining)
            record["responses"].append({"request_sha256": request_hash, "message_count": len(messages), "response": response})
            if response.get("model") != frozen["model"]:
                raise ProviderFault("REPORTED_MODEL_MISMATCH")
            u = usage(response.get("usage") or {})
            record["usage_reports"].append(u)
            if type(u["totalTokens"]) is not int:
                raise ProviderFault("REPORTED_TOTAL_MISSING_CANNOT_ENFORCE_OBSERVATION")
            choice = response["choices"][0]
            message = choice["message"]
            reason = choice.get("finish_reason")
            if reason not in ("stop", "tool_calls", "length", "content_filter", "insufficient_system_resource"):
                raise ProviderFault("UNRECOGNIZED_FINISH_REASON")
            if reason == "insufficient_system_resource":
                raise ProviderFault("PROVIDER_INSUFFICIENT_SYSTEM_RESOURCE")
            if reason in ("length", "content_filter"):
                record["stop_reason"] = "MODEL_" + reason.upper()
                break
            if not message.get("tool_calls"):
                record["stop_reason"] = "NORMAL_STOP"
                record["terminal_confirmed"] = True
                break
            # Preserve reasoning_content exactly for subsequent tool requests;
            # it is private raw provider data, never a public report payload.
            messages.append(message)
            record["observed_tool_calls"] += len(message["tool_calls"])
            for tool in message["tool_calls"]:
                if record["dispatched_tool_calls"] >= frozen["limits"]["tool_callback_limit"]:
                    record["stop_reason"] = "TOOL_OBSERVATION_LIMIT"
                    return
                if time.monotonic() - start >= frozen["limits"]["wall_observation_seconds"]:
                    record["stop_reason"] = "ACTIVE_OBSERVATION_LIMIT_BETWEEN_TOOLS"
                    return
                function = tool["function"]
                name = function["name"]
                before = time.monotonic()
                try:
                    arguments = json.loads(function["arguments"])
                except (ValueError, TypeError):
                    arguments, value = None, {"error": "INVALID_TOOL_ARGUMENTS"}
                else:
                    value = slot.tool(name, arguments) if name in allowed else {"error": "TOOL_NOT_EXPOSED"}
                record["dispatched_tool_calls"] += 1
                normalized = model_result(value)
                record["tool_events"].append({"name": name, "arguments": arguments, "response": normalized,
                    "duration_seconds": time.monotonic() - before})
                messages.append({"role": "tool", "tool_call_id": tool["id"], "content": json.dumps(normalized, ensure_ascii=False)})
                if name == "study_finish" and normalized.get("finished") is True:
                    record["stop_reason"] = "STUDY_FINISH"
                    record["terminal_confirmed"] = True
                    return
    finally:
        record["active_seconds"] = time.monotonic() - start
        record["reported_usage"] = totals(record["usage_reports"])
        record["usage_complete"] = len(record["responses"]) == record["submitted_chat_requests"] and all(
            type(record["reported_usage"].get(k)) is int for k in ("totalTokens", "inputTokens", "cachedInputTokens", "outputTokens"))


def verify(frozen, remote):
    for path, expected in frozen["runtime_files"].items():
        if sha((ROOT / path).read_bytes()) != expected:
            raise RuntimeError("LOCAL_RUNTIME_IDENTITY_MISMATCH:" + path)
    code = "import json,pathlib,hashlib,sys;r=pathlib.Path(sys.argv[1]);print(json.dumps({p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in json.load(sys.stdin)}))"
    observed = json.loads(remote.checked(["python3", "-c", code, remote.root], input=json.dumps(list(frozen["runtime_files"]))))
    if observed != frozen["runtime_files"]:
        raise RuntimeError("REMOTE_RUNTIME_IDENTITY_MISMATCH")
    if sha(Path(__import__("sys").executable).read_bytes()) != frozen["controller_python_sha256"]:
        raise RuntimeError("CONTROLLER_EXECUTABLE_MISMATCH")
    sdk = remote.cfg["sdk_paths"]
    observed = json.loads(remote.checked(["python3", "-c",
        "import pathlib,hashlib,json,sys;print(json.dumps({k:hashlib.sha256(pathlib.Path(v).read_bytes()).hexdigest() for k,v in json.load(sys.stdin).items()}))"],
        input=json.dumps({"alva": sdk["alva"], "rustc": sdk["toolchain"] + "/bin/rustc"})))
    if observed != frozen["sdk_executables"]:
        raise RuntimeError("SDK_EXECUTABLE_MISMATCH")


def run(args):
    freeze_path = HERE / "FREEZE.json"
    frozen = json.loads(freeze_path.read_bytes())
    if frozen["status"] != "FROZEN_BEFORE_GENERATION":
        raise RuntimeError("UNQUALIFIED_RUNTIME")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise RuntimeError("DIRTY_WORKTREE_BEFORE_GENERATION")
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "GENERATION-STARTED.json", {"freeze_sha256": sha(freeze_path.read_bytes()), "max_slots": 16})
    api, remote = API(args.credentials), Remote(args.connection)
    rows = []
    for entry in frozen["schedule"]:
        record = {**entry, "correct": None, "valid": False, "terminal_confirmed": False,
                  "model_sessions_started": 0, "provider_generation_requests": None, "dollar_cost": None}
        slot = None
        before = time.monotonic()
        print("START " + entry["id"], flush=True)
        try:
            verify(frozen, remote)
            record["identity_before"] = True
            slot = Slot(args.output, entry, frozen, args)
            record["setup_seconds"] = time.monotonic() - before
            record["model_sessions_started"] = 1
            conversation(api, slot, frozen, record)
        except Exception as exc:
            record["infrastructure_hold"] = type(exc).__name__ + ":" + str(exc)[:180]
        finally:
            finish_start = time.monotonic()
            if slot:
                try:
                    slot.close()
                    record["cleanup_confirmed"] = True
                    evidence = json.loads(slot.evidence.read_bytes())
                    record["outcome"] = prior.score(slot.task, evidence)
                    record["evidence_sha256"] = sha(slot.evidence.read_bytes())
                    record["correct"] = bool(record["outcome"]["correct"] and record["terminal_confirmed"])
                    if entry["arm"] == "N":
                        commits = [e for e in evidence["calls"] if e.get("request", {}).get("method") == "tools/call"
                                   and e["request"]["params"]["name"] == "commit_transaction"
                                   and not e.get("response", {}).get("isError")]
                        record["successful_native_commits"] = len(commits)
                        record["correct"] &= bool(commits and record["outcome"]["air_published"] and
                            record["outcome"]["fresh_project_revision"] == commits[-1]["response"]["structuredContent"]["revision"])
                except Exception as exc:
                    record["infrastructure_hold"] = "FINALIZATION:" + type(exc).__name__ + ":" + str(exc)[:180]
            try:
                verify(frozen, remote)
                record["identity_after"] = True
            except Exception as exc:
                record["infrastructure_hold"] = "POST_SLOT_IDENTITY:" + type(exc).__name__
            record["finalization_seconds"] = time.monotonic() - finish_start
            record["valid"] = not record.get("infrastructure_hold") and record.get("cleanup_confirmed") is True
            rows.append(record)
            save(args.output / entry["id"] / "record.json", record)
            save(args.output / "RESULTS.json", {"status": "RUNNING" if record["valid"] else "INFRASTRUCTURE_HOLD",
                "rows": rows, "model_sessions_started": sum(r["model_sessions_started"] for r in rows),
                "submitted_chat_requests": api.submitted_chat_requests})
            print(json.dumps({"id": entry["id"], "valid": record["valid"], "correct": record["correct"],
                              "stop": record.get("stop_reason"), "hold": record.get("infrastructure_hold"),
                              "tool_calls": record.get("observed_tool_calls"), "usage": record.get("reported_usage")}), flush=True)
        if not record["valid"]:
            break
    result = {"status": "COMPLETED" if len(rows) == 16 and all(r["valid"] for r in rows) else "INFRASTRUCTURE_HOLD",
              "rows": rows, "model_sessions_started": sum(r["model_sessions_started"] for r in rows),
              "submitted_chat_requests": api.submitted_chat_requests, "provider_generation_requests": None, "dollar_cost": None}
    save(args.output / "RESULTS.json", result)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", type=Path, required=True)
    p.add_argument("--credentials", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    run(p.parse_args())
