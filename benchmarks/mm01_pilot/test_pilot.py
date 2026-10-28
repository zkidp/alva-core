"""Zero-model adapter / provenance regression, no historical gates rerun."""
import base64
import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.mm01_pilot import pilot
from benchmarks.mm01_pilot import inside


class Tests(unittest.TestCase):
    def test_arguments(self):
        self.assertEqual(pilot.valid("edit", {})["error"], "MISSING_REQUIRED_ARGUMENT")
        self.assertEqual(pilot.valid("read", {"revision": 4, "path": "x"})["error"], "INVALID_ARGUMENT_TYPE")
        self.assertEqual(pilot.valid("check", {"x": 1})["error"], "UNKNOWN_ARGUMENT")
        self.assertIsNone(pilot.valid("edit", {"revision": "r", "path": "p", "old": "o", "new": "n"}))

    def test_exact_edit_and_pagination(self):
        # This test executes only trusted file-handling code, never candidates.
        import os
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            try:
                os.chdir(tmp)
                for p in inside.PATHS:
                    out = Path(p)
                    out.parent.mkdir(exist_ok=True, parents=True)
                    out.write_bytes(b"one\ntwo\n")
                r = inside.revision()
                a = inside.dispatch("read", {"revision": r, "path": "src/model.alva", "count": 1})
                self.assertEqual(a["content"], "one\n")
                self.assertFalse(a["eof"])
                self.assertEqual(a["next_start"], 2)
                self.assertEqual(inside.dispatch("read", {"revision": r, "path": "../outside"})["error"], "PATH_NOT_ALLOWED")
                self.assertEqual(inside.dispatch("read", {"revision": r, "path": "src/model.alva", "start": 0})["error"], "INVALID_READ_RANGE")
                a = inside.dispatch("edit", {"revision": r, "path": "src/model.alva", "old": "one", "new": "three"})
                self.assertTrue(a["accepted"])
                self.assertEqual(inside.dispatch("edit", {"revision": r, "path": "src/model.alva", "old": "one", "new": "four"})["error"], "STALE_REVISION")
                self.assertEqual(inside.dispatch("edit", {"revision": a["revision"], "path": "alva.toml", "old": "one", "new": "four"})["error"], "PROTECTED_PATH")
            finally:
                os.chdir(previous)

    def test_reused_controller_terminal_duplicate_and_usage(self):
        class Host:
            def __init__(self):
                self.messages, self.sent = queue.Queue(), []
            def send(self, row):
                self.sent.append(row)
        h = Host()
        c = pilot.old.Controller(h)
        c.bind({"thread": {"id": "t"}}, {"turn": {"id": "v"}})
        class Slot:
            entry = {"arm": "T"}
            def __init__(self): self.calls = []
            def dispatch(self, action, args):
                self.calls.append((action, args)); return {"finished": True}
        s = Slot()
        call = {"id": 1, "method": "item/tool/call", "params": {"callId": "same", "tool": "study", "arguments": {"action": "finish", "arguments": "{}"}}}
        h.messages.put(call); h.messages.put(call)
        h.messages.put({"method": "turn/completed", "params": {"turn": {"id": "v", "status": "completed"}}})
        row = {}
        with patch.object(pilot.old, "CONFIG", pilot.CONFIG):
            pilot.old.drive(c, s, row)
        self.assertEqual(len(s.calls), 1)
        self.assertEqual(row["terminal_status"], "completed")
        self.assertFalse(row["usage_complete"])
        self.assertEqual(pilot.old.simulated_validation()["status"], "PASS")

    def test_frozen_inputs(self):
        path = pilot.HERE / "FREEZE.json"
        if not path.exists():
            self.skipTest("prepare not yet run")
        f = json.loads(path.read_text())
        self.assertEqual(f["base"], pilot.BASE)
        self.assertEqual(f["config"], pilot.CONFIG)
        self.assertEqual(f["tools"], pilot.TOOLS)
        self.assertEqual(f["developer_instructions"], pilot.INSTRUCTIONS)
        self.assertEqual([r["condition"] for r in f["schedule"]], ["T", "S"])
        self.assertEqual(f["schedule"][0]["prompt"], f["public_task_input"])
        self.assertTrue(f["schedule"][1]["prompt"].startswith(f["public_task_input"] + "\n$alva\n"))
        for body in f["docs"].values():
            self.assertIn(body, f["schedule"][1]["prompt"])
        self.assertEqual(set(pilot.decode(f["task"]["bundle"], f["task"]["bundle"]["payload_sha256"])), set(pilot.PATHS))
        self.assertEqual(len(f["native_tools"]), 20)
        for name, digest in f["files"].items():
            self.assertEqual(pilot.sha(base64.b64decode(f["runtime_bytes"][name])), digest)
            self.assertEqual(pilot.sha((pilot.ROOT / name).read_bytes()), digest, name)
        self.assertEqual(f["validation"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
