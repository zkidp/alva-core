import copy
import json
from types import SimpleNamespace
import unittest

from benchmarks.compact_deepseek.api import usage, totals, ProviderFault
from benchmarks.compact_deepseek.preflight import design, replacement
from benchmarks.compact_deepseek.runner import conversation, model_result
from benchmarks.compact_maintenance.contract import study_tools


class FakeAPI:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
    def request(self, path, payload, timeout):
        self.requests.append(copy.deepcopy(payload))
        value = self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return value


def response(tool=None, arguments=None, reason="stop"):
    message = {"role": "assistant", "content": "", "reasoning_content": "PRIVATE_TEST_REASONING"}
    if tool:
        message["tool_calls"] = [{"id": "call-1", "type": "function", "function": {"name": tool, "arguments": json.dumps(arguments or {})}}]
        reason = "tool_calls"
    return {"model": "deepseek-flash", "choices": [{"message": message, "finish_reason": reason}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "prompt_cache_hit_tokens": 4}}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.frozen = design()
        self.frozen["provider_tools"] = {"T": [{"type": "function", "function": {
            "name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}} for t in study_tools("T")]}
        self.calls = []
        def tool(name, args):
            self.calls.append((name, args))
            return {"finished": True} if name == "study_finish" else {"status": "PASS"}
        self.slot = SimpleNamespace(entry={"arm": "T"}, native=None,
            task={"public_task": {"id": "MM01", "target": "demo.model.touch_size"}}, tool=tool)

    def test_reasoning_preserved_for_tool_continuations(self):
        api = FakeAPI([response("study_check"), response("study_finish")])
        record = {}
        conversation(api, self.slot, self.frozen, record)
        self.assertEqual(len(api.requests), 2)
        self.assertEqual(api.requests[1]["messages"][2]["reasoning_content"], "PRIVATE_TEST_REASONING")
        self.assertEqual(record["stop_reason"], "STUDY_FINISH")
        self.assertEqual(record["reported_usage"]["totalTokens"], 24)
        self.assertIsNone(record["reported_usage"]["reasoningOutputTokens"])

    def test_provider_failure_is_not_retried(self):
        api = FakeAPI([ProviderFault("HTTP_402"), response()])
        with self.assertRaises(ProviderFault): conversation(api, self.slot, self.frozen, {})
        self.assertEqual(len(api.requests), 1)

    def test_observation_limit_prevents_more_requests(self):
        self.frozen["limits"]["token_observation_threshold"] = 12
        api = FakeAPI([response("study_check"), response()])
        record = {}
        conversation(api, self.slot, self.frozen, record)
        self.assertEqual(len(api.requests), 1)
        self.assertEqual(record["stop_reason"], "OBSERVATION_LIMIT_BETWEEN_REQUESTS")

    def test_unexposed_tool_never_dispatched(self):
        api = FakeAPI([response("commit_transaction"), response()])
        record = {}
        conversation(api, self.slot, self.frozen, record)
        self.assertEqual(self.calls, [])
        self.assertEqual(record["tool_events"][0]["response"]["error"], "TOOL_NOT_EXPOSED")

    def test_tool_limit_and_model_identity(self):
        self.frozen["limits"]["tool_callback_limit"] = 0
        record = {}
        conversation(FakeAPI([response("study_check")]), self.slot, self.frozen, record)
        self.assertEqual(self.calls, [])
        self.assertEqual(record["stop_reason"], "TOOL_OBSERVATION_LIMIT")
        wrong = response(); wrong["model"] = "different"
        with self.assertRaises(ProviderFault): conversation(FakeAPI([wrong]), self.slot, self.frozen, {})

    def test_usage_missing_is_null_and_native_wire_is_not_duplicated(self):
        self.assertIsNone(usage({})["totalTokens"])
        self.assertIsNone(totals([])["totalTokens"])
        self.assertEqual(model_result({"isError": True, "structuredContent": {"error": "x"}, "content": [{"text": "duplicate"}]}),
                         {"isError": True, "structuredContent": {"error": "x"}})

    def test_all_four_deterministic_body_witnesses_extract_without_model_calls(self):
        for task in self.frozen["tasks"].values():
            source, fragment = replacement(task)
            self.assertTrue(fragment.startswith("(body"))
            self.assertLessEqual(len(fragment.encode()), 65536)


if __name__ == "__main__": unittest.main()
