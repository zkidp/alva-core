import copy
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.context_flash_pilot.freeze import INSTRUCTIONS, LIMITS, PARAMETERS, tools, messages
from benchmarks.context_flash_pilot.runner import conversation, payload, exposed
from benchmarks.bounded_context_audit.accounting import Exposure
from benchmarks.context_flash_pilot.tasks import tasks
from integrations.codex.maintenance_host import sha


def response(actions, reason="tool_calls"):
    return {"model": "deepseek-flash", "id": "synthetic", "choices": [{"finish_reason": reason,
        "message": {"role": "assistant", "content": None, "reasoning_content": "synthetic test marker", "tool_calls": actions}}],
        "usage": {"total_tokens": 120000, "prompt_tokens": 119990, "completion_tokens": 10}}


def action(ident, name, args):
    return {"id": ident, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Slot:
    entry = {"task": "Q01", "arm": "C"}
    def __init__(self, value): self.value, self.calls = value, []
    def request(self, req): self.calls.append(req); return copy.deepcopy(self.value)


class FakeAPI:
    def __init__(self, reply): self.reply, self.calls = reply, 0
    def request(self, *args, **kwargs): self.calls += 1; return self.reply


class PilotTests(unittest.TestCase):
    def test_empty_eof_does_not_invent_delivery_or_fail_host(self):
        meter = Exposure()
        exposed(meter, {"a.alva": b"x\n"}, "read_source", {}, {"status": "SOURCE", "path": "a.alva", "start": 20, "content": "", "eof": True})
        self.assertEqual(meter.delivered, 0)
    def run_conversation(self, reply, value):
        cfg = {"model": "deepseek-flash", "tasks": tasks(), "instructions": INSTRUCTIONS,
               "host_skill": "same shared generic skill", "limits": LIMITS, "api_parameters": PARAMETERS, "provider_tools": tools()}
        cfg["initial_inputs"] = {k: messages(cfg, task) for k, task in cfg["tasks"].items()}
        cfg["initial_request_sha256"] = {k: sha(json.dumps(payload(cfg, v)).encode()) for k, v in cfg["initial_inputs"].items()}
        slot, api, record = Slot(value), FakeAPI(reply), {}
        with tempfile.TemporaryDirectory() as td:
            conversation(api, slot, cfg, record, Path(td))
        return record, slot, api

    def test_response_action_drains_after_token_threshold(self):
        record, slot, api = self.run_conversation(response([action("one", "list_symbols", {})]), {"status": "SYMBOLS"})
        self.assertEqual(record["stop_reason"], "REQUEST_ADMISSION_LIMIT")
        self.assertEqual(len(slot.calls), 1)
        self.assertEqual(api.calls, 1)
        self.assertEqual(record["reported_usage"]["totalTokens"], 120000)
        self.assertIsNone(record["reported_usage"]["cachedInputTokens"])

    def test_incomplete_never_dispatches(self):
        record, slot, _ = self.run_conversation(response([action("one", "list_symbols", {})], "length"), {})
        self.assertEqual(slot.calls, [])
        self.assertEqual(record["stop_reason"], "INCOMPLETE_length")

    def test_duplicate_not_replayed(self):
        a = action("one", "list_symbols", {})
        record, slot, _ = self.run_conversation(response([a, a]), {"status": "SYMBOLS"})
        self.assertEqual(len(slot.calls), 1)
        self.assertEqual(record["stop_reason"], "DUPLICATE_CALL_STOP")

    def test_publish_stops_tail(self):
        record, slot, _ = self.run_conversation(response([action("one", "publish_change", {"proposal_id": "x"}),
            action("two", "prepare_change", {"view_id": "v", "body": "b"})]), {"status": "PUBLISHED"})
        self.assertEqual(len(slot.calls), 1)
        self.assertEqual(record["stop_reason"], "PUBLISHED")

    def test_tools_and_inputs_do_not_contain_evaluator(self):
        cfg = {"instructions": INSTRUCTIONS, "host_skill": "shared"}
        for task in tasks().values():
            text = json.dumps(messages(cfg, task))
            self.assertNotIn("maintenance_goal", text)
            self.assertNotIn("preserved_behavior", text)
            self.assertNotIn("assert_eq!", text)
        self.assertEqual(len(tools()), 7)


if __name__ == "__main__": unittest.main()
