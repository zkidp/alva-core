"""Pinned OpenAI Responses API relay for the E4 evaluated model.

This module is inert until a frozen formal runner constructs it. It reads the
key only from OPENAI_API_KEY; credentials are never accepted in manifests.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


MODEL = "gpt-5.6-luna"
PROTOCOL = "openai-responses-function-loop-v1"


class LunaRelay:
    def __init__(self, tool_defs, telemetry_path, fingerprint_path,
                 *, reasoning_effort="high", max_output_tokens=16384):
        self.key = os.environ.get("OPENAI_API_KEY")
        if not self.key:
            raise RuntimeError("FAIL_CLOSED: OPENAI_API_KEY unset")
        self.base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.tools = [self._responses_tool(item) for item in tool_defs]
        self.telemetry_path = Path(telemetry_path)
        self.fingerprint_path = Path(fingerprint_path)
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens
        self.previous_response_id = None
        self.pending_call_id = None

    @staticmethod
    def _responses_tool(item):
        function = item.get("function", item)
        if item.get("type") not in (None, "function"):
            raise ValueError("only function tools are supported")
        return {
            "type": "function",
            "name": function["name"],
            "description": function.get("description", ""),
            "parameters": function.get("parameters", {
                "type": "object", "properties": {},
                "additionalProperties": False,
            }),
        }

    @staticmethod
    def _output_text(response):
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        chunks = []
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))
        return "".join(chunks)

    def _post(self, body):
        request = urllib.request.Request(
            self.base.rstrip("/") + "/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.key}"},
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            if exc.code == 429 or exc.code >= 500:
                raise RuntimeError(f"INFRA_FAILURE: HTTP {exc.code}: {detail}")
            raise RuntimeError(f"RUNNER_CRASH: HTTP {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"API_UNREACHABLE: {exc}")

    def _record(self, response):
        usage = response.get("usage") or {}
        rec = {
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "protocol": PROTOCOL,
            "response_id": response.get("id"),
            "response_model": response.get("model"),
            "status": response.get("status"),
            "usage": usage,
        }
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with self.telemetry_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(rec, sort_keys=True) + "\n")
        if self.fingerprint_path.exists():
            frozen = json.loads(self.fingerprint_path.read_text(encoding="utf-8"))
            if response.get("model") != frozen["response_model"]:
                raise RuntimeError("HOLD_MODEL_VERSION_DRIFT")
        else:
            if response.get("model") != MODEL:
                raise RuntimeError("HOLD_MODEL_VERSION_DRIFT")
            self.fingerprint_path.write_text(json.dumps({
                "requested_model": MODEL,
                "response_model": response.get("model"),
                "protocol": PROTOCOL,
                "recorded_at": rec["timestamp_utc"],
            }, indent=2) + "\n", encoding="utf-8")

    def _request(self, input_items, *, instructions=None):
        body = {
            "model": MODEL,
            "input": input_items,
            "tools": self.tools,
            "parallel_tool_calls": False,
            "reasoning": {"effort": self.reasoning_effort},
            "max_output_tokens": self.max_output_tokens,
        }
        if instructions is not None:
            body["instructions"] = instructions
        if self.previous_response_id is not None:
            body["previous_response_id"] = self.previous_response_id
        response = self._post(body)
        self._record(response)
        if response.get("status") != "completed":
            raise RuntimeError(f"RUNNER_CRASH: response status {response.get('status')}")
        self.previous_response_id = response.get("id")
        calls = [item for item in response.get("output", [])
                 if item.get("type") == "function_call"]
        if len(calls) > 1:
            raise RuntimeError("RUNNER_CRASH: parallel function calls returned")
        if calls:
            call = calls[0]
            try:
                arguments = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                raise RuntimeError("RUNNER_CRASH: invalid function arguments") from exc
            self.pending_call_id = call["call_id"]
            return {"type": "tool", "tool": call["name"],
                    "args": arguments, "tool_call_id": call["call_id"]}
        self.pending_call_id = None
        return {"type": "final", "text": self._output_text(response)}

    def start(self, task_statement, instructions):
        if self.previous_response_id is not None:
            raise RuntimeError("relay already started")
        return self._request(task_statement, instructions=instructions)

    def submit_tool_result(self, call_id, result):
        if call_id != self.pending_call_id:
            raise RuntimeError("RUNNER_CRASH: tool result call_id mismatch")
        return self._request([{
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(result, sort_keys=True),
        }])
