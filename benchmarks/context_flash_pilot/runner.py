"""Thin WSL transport around existing Host and DeepSeek API; no model retries.

Raw requests, responses (including provider private reasoning) and backend
receipts stay in an explicitly local output tree, never stdout or public Git.
"""
import argparse
import copy
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from benchmarks.compact_deepseek.api import API, ProviderFault, usage, totals
from benchmarks.compact_deepseek.runner import bounded_request
from benchmarks.bounded_context_audit.accounting import Exposure
from benchmarks.context_flash_pilot.freeze import ROOT, HERE, messages, runtime
from integrations.codex.maintenance_host import canonical, sha
from integrations.benchmark_runtime_v2.freeze import decode


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


class WSLSlot:
    def __init__(self, entry, frozen, sdk_paths):
        self.entry = entry
        mounted = "/mnt/" + str(ROOT.drive)[0].lower() + ROOT.as_posix()[2:]
        cmd = ["wsl", "-d", "Ubuntu-26.04", "--cd", mounted, "--", "python3", "-u", "-m", "benchmarks.context_flash_pilot.service",
               "--freeze", mounted + "/benchmarks/context_flash_pilot/FREEZE.json", "--task", entry["task"], "--arm", entry["arm"]]
        for key, value in sdk_paths.items(): cmd += ["--" + key, value]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.lines = queue.Queue()
        self.errors = bytearray()
        def read():
            while line := self.proc.stdout.readline(24 * 1024**2 + 1): self.lines.put(line)
            self.lines.put(None)
        def errors():
            while block := self.proc.stderr.read(4096):
                if len(self.errors) < 65536: self.errors.extend(block)
        self.reader = threading.Thread(target=read, daemon=True)
        self.err_reader = threading.Thread(target=errors, daemon=True)
        self.reader.start(); self.err_reader.start()
        try:
            ready = self.receive()
            schema = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}} for t in ready["tools"]]
            if schema != frozen["provider_tools"]: raise RuntimeError("RUNTIME_SCHEMA_DRIFT")
        except Exception:
            self.close()
            raise

    def receive(self):
        try: line = self.lines.get(timeout=150)
        except queue.Empty: raise RuntimeError("LOCAL_SERVICE_TIMEOUT_NO_REPLAY") from None
        if not line or len(line) > 24 * 1024**2: raise RuntimeError("LOCAL_SERVICE_CLOSED_OR_OVERSIZE")
        return json.loads(line)

    def request(self, req):
        self.proc.stdin.write(canonical(req) + b"\n"); self.proc.stdin.flush()
        return self.receive()

    def close(self):
        self.proc.stdin.close()
        try: code = self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired: raise RuntimeError("SERVICE_TERMINATION_UNCONFIRMED") from None
        self.reader.join(3); self.err_reader.join(3)
        if code or self.reader.is_alive() or self.err_reader.is_alive(): raise RuntimeError("SERVICE_CLEANUP_UNCONFIRMED")


def payload(frozen, msgs):
    return {"model": frozen["model"], "messages": msgs, "tools": frozen["provider_tools"], **frozen["api_parameters"]}


def exposed(meter, files, name, args, value):
    if name == "read_source" and value.get("status") == "SOURCE" and value.get("content"):
        source = files[value["path"]]
        start = sum(len(line) for line in source.splitlines(keepends=True)[:value["start"] - 1])
        meter.add(value["path"], source, start, value["content"].encode())
    if name == "search_source" and value.get("status") == "SEARCH":
        for hit in value["hits"]: meter.add(hit["path"], files[hit["path"]], hit["byte_start"], hit["content"].encode())


def conversation(api, slot, frozen, record, output):
    limits = frozen["limits"]
    task = frozen["tasks"][slot.entry["task"]]
    files = decode(task["bundle"], task["bundle"]["payload_sha256"])
    msgs = copy.deepcopy(frozen["initial_inputs"][slot.entry["task"]])
    record.update(requests=[], tool_events=[], usage_reports=[], calls=0, submitted_requests=0, first_accepted_change=None)
    meter, ids = Exposure(), set()
    allowed = {t["function"]["name"] for t in frozen["provider_tools"]}
    started = time.monotonic()
    try:
        for ordinal in range(1, limits["requests"] + 1):
            total = totals(record["usage_reports"])["totalTokens"]
            remaining = limits["active_seconds"] - (time.monotonic() - started)
            if remaining <= 0 or (total is not None and total >= limits["token_observation"]):
                record["stop_reason"] = "REQUEST_ADMISSION_LIMIT"; return
            request = payload(frozen, msgs)
            request_bytes = json.dumps(request).encode()  # Exact existing API transport serialization.
            if len(request_bytes) > limits["request_bytes"]:
                record["stop_reason"] = "REQUEST_BYTES_LIMIT"; return
            record["last_request_admission"] = {"ordinal": ordinal, "prior_reported_total": total,
                "request_bytes": len(request_bytes), "remaining_seconds": remaining,
                "output_cap": request["max_tokens"], "tools_dispatched": record["calls"]}
            if ordinal == 1 and sha(request_bytes) != frozen["initial_request_sha256"][slot.entry["task"]]: raise RuntimeError("FIRST_REQUEST_DRIFT")
            save(output / f"request-{ordinal:02}.json", request)
            (output / f"request-{ordinal:02}.wire").write_bytes(request_bytes)
            record["submitted_requests"] += 1
            record.setdefault("first_generation_utc", datetime.now(timezone.utc).isoformat())
            response = bounded_request(api, request, min(remaining, limits["request_timeout"]))
            save(output / f"response-{ordinal:02}.json", response)
            record["requests"].append({"ordinal": ordinal, "request_sha256": sha(request_bytes), "request_bytes": len(request_bytes),
                "response_sha256": sha(canonical(response)), "response_id": response.get("id"), "model": response.get("model"),
                "system_fingerprint": response.get("system_fingerprint")})
            if response.get("model") != frozen["model"]: raise ProviderFault("REPORTED_MODEL_MISMATCH")
            u = usage(response.get("usage") or {})
            record["usage_reports"].append(u)
            if any(type(u.get(k)) is not int for k in ("totalTokens", "inputTokens", "outputTokens")): raise ProviderFault("MISSING_USAGE")
            choice = response["choices"][0]
            reason = choice.get("finish_reason")
            if reason in ("length", "content_filter"):
                record["stop_reason"] = "INCOMPLETE_" + reason; return
            if reason not in ("stop", "tool_calls"): raise ProviderFault("UNKNOWN_OR_ERROR_FINISH")
            msg = choice["message"]
            msgs.append(msg)  # Preserve reasoning_content unchanged, privately.
            actions = msg.get("tool_calls") or []
            if not actions:
                record["stop_reason"] = "NORMAL_MODEL_STOP"; return
            for action_index, action in enumerate(actions):
                if record["calls"] >= limits["tools"] or time.monotonic() - started >= limits["active_seconds"]:
                    record["stop_reason"] = "ACTION_TOOL_OR_WALL_GATE"; return
                if action["id"] in ids:
                    record["stop_reason"] = "DUPLICATE_CALL_STOP"; return
                ids.add(action["id"])
                name = action["function"]["name"]
                try: args = json.loads(action["function"]["arguments"])
                except (ValueError, TypeError): args = None
                value = slot.request({"action": "tool", "name": name, "arguments": args}) if name in allowed else {"status": "REJECTED", "reason": "TOOL_NOT_EXPOSED"}
                record["calls"] += 1
                exposed(meter, files, name, args, value)
                event = {"request": ordinal, "name": name, "arguments": args, "response": value,
                         "raw_source_delivered": meter.delivered, "unique_raw_source": meter.unique,
                         "actual_cumulative_tokens": totals(record["usage_reports"])["totalTokens"]}
                record["tool_events"].append(event)
                if name == "prepare_change" and value.get("status") in ("PREPARED", "VALIDATION_FAILED") and record["first_accepted_change"] is None:
                    record["first_accepted_change"] = {"request": ordinal, "actual_tokens": event["actual_cumulative_tokens"],
                                                      "unique_raw_source": meter.unique, "raw_source_delivered": meter.delivered}
                msgs.append({"role": "tool", "tool_call_id": action["id"], "content": json.dumps(value, ensure_ascii=False)})
                if value.get("status") in ("BLOCKED", "PUBLISHED_UNVERIFIED", "UNVERIFIED_TEST_RECEIPT"):
                    raise RuntimeError("HOST_UNCERTAIN_OR_BLOCKED:" + value["status"])
                if name == "publish_change" and value.get("status") == "PUBLISHED":
                    record["stop_reason"] = "PUBLISHED"; return
                if any(marker in str(value.get("reason", "")).upper() for marker in ("CONFLICT", "STALE", "SOURCE_CHANGED", "VIEW_EXPIRED")):
                    for pending in actions[action_index + 1:]:
                        msgs.append({"role": "tool", "tool_call_id": pending["id"], "content": json.dumps({"status": "NOT_DISPATCHED", "reason": "CONFLICT_TAIL_STOP"})})
                    break  # Do not dispatch response tail referring to old state.
        record["stop_reason"] = "GENERATION_REQUEST_LIMIT"
    finally:
        record["active_seconds"] = time.monotonic() - started
        record["reported_usage"] = totals(record["usage_reports"])
        record["source_exposure"] = {"raw_delivered_bytes": meter.delivered, "unique_raw_bytes": meter.unique,
            "duplicate_raw_bytes": meter.delivered - meter.unique,
            "limitation": "Exact source tool bytes only; target body/context representations are separately retained, not treated as raw source"}


def run(args):
    frozen = json.loads((HERE / "FREEZE.json").read_bytes())
    if runtime() != frozen["runtime"]: raise RuntimeError("RUNTIME_DRIFT")
    if sha(Path(sys.executable).read_bytes()) != frozen["controller_python_sha256"]: raise RuntimeError("CONTROLLER_PYTHON_DRIFT")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT): raise RuntimeError("WORKTREE_DIRTY")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(["git", "rev-parse", "@{upstream}"], cwd=ROOT, text=True).strip()
    if head != remote: raise RuntimeError("FREEZE_NOT_PUSHED")
    args.output.mkdir(parents=True, exist_ok=False)
    # Exclusive global reservation prevents accidental second batches.
    reservation = ROOT / ".local" / ("context-flash-reserved-" + sha((HERE / "FREEZE.json").read_bytes()))
    reservation.parent.mkdir(exist_ok=True)
    reservation.open("x").close()
    api, rows = API(args.credentials), []
    for entry in frozen["schedule"]:
        record, slot = dict(entry), None
        print("START " + entry["id"], flush=True)
        try:
            if runtime() != frozen["runtime"]: raise RuntimeError("RUNTIME_DRIFT")
            slot = WSLSlot(entry, frozen, {k: getattr(args, k) for k in ("alva", "toolchain", "registry")})
            conversation(api, slot, frozen, record, args.output / entry["id"])
        except Exception as exc:
            record["infrastructure_hold"] = type(exc).__name__ + ":" + str(exc)[:180]
        finally:
            if slot:
                try:
                    final = slot.request({"action": "finish"})
                    save(args.output / entry["id"] / "backend.json", final)
                    record["outcome"] = {k: v for k, v in final.items() if k not in ("calls", "evaluations")}
                    slot.close()
                except Exception as exc: record["infrastructure_hold"] = "FINALIZATION:" + type(exc).__name__
            rows.append(record)
            save(args.output / entry["id"] / "record.json", record)
            save(args.output / "RESULTS.json", {"rows": rows, "freeze_commit": head, "provider_requests_submitted": api.submitted_chat_requests,
                "status": "HOLD" if record.get("infrastructure_hold") else "RUNNING"})
            print(json.dumps({"id": entry["id"], "stop": record.get("stop_reason"), "hold": record.get("infrastructure_hold"),
                              "correct": record.get("outcome", {}).get("correct"), "usage": record.get("reported_usage")}), flush=True)
        if record.get("infrastructure_hold"): break
    save(args.output / "RESULTS.json", {"rows": rows, "freeze_commit": head, "provider_requests_submitted": api.submitted_chat_requests,
        "status": "COMPLETED" if len(rows) == len(frozen["schedule"]) and not any(r.get("infrastructure_hold") for r in rows) else "HOLD"})


def canary(args):
    api = API(args.credentials)
    toy = [{"type": "function", "function": {"name": "echo", "description": "Echo the supplied text.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}}}]
    msgs = [{"role": "user", "content": "Non-scientific connectivity check. Call echo with text ready, then acknowledge the result briefly."}]
    replies = []
    for turn in range(2):
        req = {"model": "deepseek-flash", "messages": msgs, "tools": toy,
               "thinking": {"type": "enabled"}, "reasoning_effort": "low", "max_tokens": 2048, "stream": False}
        res = api.request("/chat/completions", req, timeout=90)
        replies.append({"request": copy.deepcopy(req), "response": res})
        if res.get("model") != "deepseek-flash" or type(usage(res.get("usage", {}))["totalTokens"]) is not int: raise RuntimeError("CANARY_IDENTITY_USAGE")
        choice = res["choices"][0]
        if choice["finish_reason"] not in ("stop", "tool_calls"): raise RuntimeError("CANARY_INCOMPLETE")
        message = choice["message"]
        msgs.append(message)
        if turn == 0:
            calls = message.get("tool_calls") or []
            if len(calls) != 1 or calls[0]["function"]["name"] != "echo" or json.loads(calls[0]["function"]["arguments"]) != {"text": "ready"}: raise RuntimeError("CANARY_TOOL_INTEGRITY")
            msgs.append({"role": "tool", "tool_call_id": calls[0]["id"], "content": "ready"})
        elif message.get("tool_calls"): raise RuntimeError("CANARY_CONTINUATION")
    save(args.output, replies)
    print(json.dumps({"canary": "PASS", "requests": api.submitted_chat_requests, "reported_model": replies[-1]["response"]["model"],
                      "usage": totals([usage(r["response"]["usage"]) for r in replies])}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--credentials", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--canary", action="store_true")
    for key in ("alva", "toolchain", "registry"): p.add_argument("--" + key)
    args = p.parse_args()
    if args.canary: canary(args)
    else:
        if not all(getattr(args, k) for k in ("alva", "toolchain", "registry")): p.error("Actual Linux SDK paths required")
        run(args)
