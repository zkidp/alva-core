import tempfile
import unittest
from pathlib import Path

from full_runtime import FullAlvaRuntime


class Agent:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.closed = False
    def call(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"ok": True, "result": {}}
    def close(self):
        self.closed = True


class FullRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        (self.root / "alva.toml").write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_project_path_is_host_mapped_and_commit_required(self):
        runtime = FullAlvaRuntime("alva", self.root, agent_factory=Agent)
        self.assertFalse(runtime.call("begin_transaction", project="C:/secret")['ok'])
        self.assertTrue(runtime.call("begin_transaction", project="alva.toml")['ok'])
        self.assertEqual(runtime.agent.calls[-1][1]["project"],
                         str(self.root / "alva.toml"))
        self.assertFalse(runtime.prepare_final_verifier()["ok"])
        runtime.call("commit_transaction")
        self.assertTrue(runtime.prepare_final_verifier()["ok"])
        runtime.close()

    def test_unknown_tool_fails_closed(self):
        runtime = FullAlvaRuntime("alva", self.root, agent_factory=Agent)
        result = runtime.call("read_file", path="src/main.alva")
        self.assertEqual(result["error_code"], "E_UNKNOWN_TOOL")
        runtime.close()


if __name__ == "__main__":
    unittest.main()
