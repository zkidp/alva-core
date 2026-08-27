#!/usr/bin/env python3
"""DeepSeek ChatCompletions thinking tool-loop relay.

Frozen protocol: e3-deepseek-chatcompletions-thinking-toolloop-v1
  - model alias: deepseek-v4-pro (underlying V4-Pro-0813)
  - thinking mode: reasoning_effort=high; temperature/top_p NOT sent
  - assistant reasoning_content from prior turns MUST be carried back in
    the messages array (missing it yields HTTP 400)
  - tool results appended with the matching tool_call_id
  - per-response telemetry recorded: response.model, system_fingerprint,
    usage.* (incl. completion_tokens_details.reasoning_tokens)
  - model alias or system_fingerprint drift across the 96 runs -> HOLD

Error mapping (TERMINATION-TAXONOMY.md):
  network unreachable        -> ApiUnreachableError  (API_UNREACHABLE)
  HTTP 429 / 5xx / timeout   -> InfraFailureError    (INFRA_FAILURE)
  drift of model/fingerprint -> InfraFailureError    (HOLD_..._DRIFT)
  other 4xx / parse defect   -> RuntimeError         (RUNNER_CRASH)
"""

import json
import os
import time
import urllib.error
import urllib.request

from runner_core import ApiUnreachableError, InfraFailureError

MODEL_ALIAS = "deepseek-v4-pro"


class DeepSeekRelay:
    def __init__(self, tool_defs, fingerprint_path, telemetry_path):
        self.key = os.environ.get("DEEPSEEK_API_KEY")
        if not self.key:
            raise RuntimeError("FAIL_CLOSED: DEEPSEEK_API_KEY unset")
        self.base = os.environ.get("DEEPSEEK_BASE_URL",
                                   "https://api.deepseek.com")
        self.tool_defs = tool_defs
        self.fingerprint_path = fingerprint_path
        self.telemetry_path = telemetry_path
        os.makedirs(os.path.dirname(telemetry_path), exist_ok=True)

    def _post(self, body):
        req = urllib.request.Request(
            self.base.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
            },
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code == 429 or e.code >= 500:
                raise InfraFailureError(f"HTTP {e.code}: {detail}")
            raise RuntimeError(f"relay HTTP {e.code}: {detail}")
        except urllib.error.URLError as e:
            raise ApiUnreachableError(f"URLError: {e}")
        except TimeoutError as e:
            raise InfraFailureError(f"timeout: {e}")

    def _record_telemetry(self, resp):
        choice = resp.get("choices", [{}])[0]
        msg = choice.get("message", {})
        usage = resp.get("usage", {})
        rec = {
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                           time.gmtime()),
            "response_model": resp.get("model"),
            "system_fingerprint": resp.get("system_fingerprint"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "prompt_cache_hit_tokens":
                    usage.get("prompt_cache_hit_tokens"),
                "prompt_cache_miss_tokens":
                    usage.get("prompt_cache_miss_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reasoning_tokens": (usage.get(
                    "completion_tokens_details", {})
                    .get("reasoning_tokens")),
            },
            "finish_reason": choice.get("finish_reason"),
        }
        with open(self.telemetry_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        # drift gates (baseline set by the FIRST formal response)
        if os.path.exists(self.fingerprint_path):
            base = json.load(open(self.fingerprint_path, encoding="utf-8"))
            if resp.get("model") != base["model"]:
                raise InfraFailureError(
                    f"HOLD_MODEL_VERSION_DRIFT: {resp.get('model')} != "
                    f"{base['model']}")
            if resp.get("system_fingerprint") != base["fingerprint"]:
                raise InfraFailureError(
                    f"HOLD_MODEL_FINGERPRINT_DRIFT: "
                    f"{resp.get('system_fingerprint')} != "
                    f"{base['fingerprint']}")
        else:
            if resp.get("model") != MODEL_ALIAS:
                raise InfraFailureError(
                    f"HOLD_MODEL_VERSION_DRIFT: first response model "
                    f"{resp.get('model')} != {MODEL_ALIAS}")
            json.dump({"model": resp.get("model"),
                       "fingerprint": resp.get("system_fingerprint"),
                       "recorded_at": rec["timestamp_utc"]},
                      open(self.fingerprint_path, "w", encoding="utf-8"),
                      indent=2)
        return rec

    def step(self, messages):
        body = {
            "model": MODEL_ALIAS,
            "messages": messages,
            "tools": self.tool_defs,
            "reasoning_effort": "high",
            "parallel_tool_calls": False,
            "max_tokens": 16384,
        }
        resp = self._post(body)
        self._record_telemetry(resp)
        msg = resp["choices"][0]["message"]
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError as e:
                raise RuntimeError(f"relay tool-args parse defect: {e}")
            return {
                "type": "tool",
                "tool": tc["function"]["name"],
                "args": args,
                "assistant": msg,
                "tool_call_id": tc["id"],
            }
        return {"type": "final", "text": msg.get("content") or ""}
