import unittest

from formal_runner import ScriptedRelay, drive


class Runtime:
    def __init__(self):
        self.calls = []
    def call(self, tool, **args):
        self.calls.append((tool, args))
        return {"ok": True, "result": {}}


class FormalRunnerTests(unittest.TestCase):
    def test_scripted_serial_loop_and_final(self):
        runtime = Runtime()
        relay = ScriptedRelay([
            {"tool": "list_files", "args": {"path": "src"}},
            {"tool": "read_file", "args": {"path": "src/main.alva"}},
            {"final": "done"},
        ])
        result = drive(runtime, relay, "task", "instructions", max_tool_steps=5)
        self.assertEqual(result["termination"], "MODEL_FINAL")
        self.assertEqual(len(result["trajectory"]), 2)

    def test_never_auto_commits_and_honors_cap(self):
        runtime = Runtime()
        relay = ScriptedRelay([{"tool": "read_file", "args": {"path": "x"}}] * 3)
        result = drive(runtime, relay, "task", "instructions", max_tool_steps=2)
        self.assertEqual(result["termination"], "MAX_TOOL_STEPS")
        self.assertNotIn("commit_patch", [name for name, _ in runtime.calls])


if __name__ == "__main__":
    unittest.main()
