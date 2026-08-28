import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from luna_relay import MODEL, PROTOCOL
import smoke_luna


TOOLS = {
    "arm": "TEXT",
    "tools": [{"type": "function", "function": {
        "name": "read_file", "description": "read",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"],
            "additionalProperties": False}}},
    ],
}


class SmokeLunaTests(unittest.TestCase):
    def setUp(self):
        work_tmp = Path(r"C:\Users\85274\Documents\日常\tmp")
        work_tmp.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=str(work_tmp)))
        self.schema = self.root / "TOOLS-TEXT.json"
        self.schema.write_text(json.dumps(TOOLS), encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_smoke_passes_on_ok_reply(self):
        out = self.root / "smoke-01" / "result.json"

        def fake_post(self, body):
            return {
                "id": "resp_smoke",
                "model": MODEL,
                "status": "completed",
                "usage": {"input_tokens": 7, "output_tokens": 1},
                "output": [],
                "output_text": "OK",
            }

        with mock.patch("luna_relay.LunaRelay._post", fake_post):
            rc = smoke_luna.main_with_args(["--tool-schema", str(self.schema),
                                            "--out", str(out)])
        self.assertEqual(rc, 0)
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["fingerprint"]["response_model"], MODEL)
        self.assertEqual(result["fingerprint"]["protocol"], PROTOCOL)
