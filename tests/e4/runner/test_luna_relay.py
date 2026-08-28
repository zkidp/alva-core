import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from luna_relay import LunaRelay, MODEL, PROTOCOL


TOOLS = [{"type": "function", "function": {
    "name": "read_file", "description": "read",
    "parameters": {"type": "object", "properties": {
        "path": {"type": "string"}}, "required": ["path"],
        "additionalProperties": False}}}]


class LunaRelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        self.env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def relay(self):
        return LunaRelay(TOOLS, self.root / "telemetry.jsonl",
                         self.root / "fingerprint.json")

    def test_function_loop_uses_previous_response(self):
        relay = self.relay()
        responses = [{
            "id": "resp_1", "model": MODEL, "status": "completed",
            "usage": {"input_tokens": 10}, "output": [{
                "type": "function_call", "call_id": "call_1",
                "name": "read_file", "arguments": '{"path":"src/main.alva"}'
            }]
        }, {
            "id": "resp_2", "model": MODEL, "status": "completed",
            "usage": {"input_tokens": 5}, "output": [], "output_text": "done"
        }]
        bodies = []
        def fake(body):
            bodies.append(body)
            return responses.pop(0)
        relay._post = fake
        step = relay.start("task", "instructions")
        self.assertEqual(step["tool"], "read_file")
        final = relay.submit_tool_result("call_1", {"ok": True})
        self.assertEqual(final, {"type": "final", "text": "done"})
        self.assertEqual(bodies[0]["model"], MODEL)
        self.assertNotIn("strict", bodies[0]["tools"][0])
        self.assertNotIn("previous_response_id", bodies[0])
        self.assertEqual(bodies[1]["previous_response_id"], "resp_1")
        self.assertEqual(bodies[1]["input"][0]["type"],
                         "function_call_output")
        self.assertEqual(json.loads((self.root / "fingerprint.json")
                                    .read_text())["protocol"], PROTOCOL)

    def test_call_id_and_model_drift_fail_closed(self):
        relay = self.relay()
        relay._post = lambda body: {
            "id": "r", "model": MODEL, "status": "completed", "output": [{
                "type": "function_call", "call_id": "c", "name": "read_file",
                "arguments": "{}"}]}
        relay.start("task", "instructions")
        with self.assertRaisesRegex(RuntimeError, "call_id mismatch"):
            relay.submit_tool_result("wrong", {})
        relay2 = self.relay()
        relay2._post = lambda body: {
            "id": "x", "model": "different", "status": "completed", "output": []}
        with self.assertRaisesRegex(RuntimeError, "MODEL_VERSION_DRIFT"):
            relay2.start("task", "instructions")

    def test_extracts_raw_rest_message_output(self):
        relay = self.relay()
        relay._post = lambda body: {
            "id": "r", "model": MODEL, "status": "completed", "output": [{
                "type": "message", "content": [
                    {"type": "output_text", "text": "hello"},
                    {"type": "output_text", "text": " world"},
                ]}]}
        self.assertEqual(relay.start("task", "instructions")["text"],
                         "hello world")


if __name__ == "__main__":
    unittest.main()
