"""Zero-model regression for the new connection, not historical study gates."""

import json
import queue
import unittest
from unittest.mock import patch

from benchmarks.native_prospective import pilot


class Host:
    def __init__(self, messages):
        self.messages = queue.Queue()
        for message in messages:
            self.messages.put(message)
        self.sent = []

    def send(self, message):
        self.sent.append(message)


class Slot:
    entry = {"arm": "N"}

    def __init__(self):
        self.actions = []

    def dispatch(self, action, args):
        self.actions.append((action, args))
        return {"ok": True}


class Tests(unittest.TestCase):
    def controller(self, messages):
        c = pilot.Controller(Host(messages))
        c.bind({"thread": {"id": "thread"}}, {"turn": {"id": "turn"}})
        return c

    def terminal(self):
        return {
            "method": "turn/completed",
            "params": {"turn": {"id": "turn", "status": "completed"}},
        }

    def test_p21_identity_interrupt_protocol(self):
        self.assertEqual(pilot.simulated_validation()["status"], "PASS")

    def test_native_not_misclassified_as_unauthorized(self):
        c = self.controller(
            [
                {
                    "method": "item/started",
                    "params": {"item": {"id": "m", "type": "mcpToolCall"}},
                },
                self.terminal(),
            ]
        )
        row = {}
        pilot.drive(c, Slot(), row)
        self.assertEqual(row["tool_calls"], 1)
        self.assertIsNone(row["usage"])
        self.assertFalse(row["usage_complete"])

    def test_native_forbidden_in_text(self):
        slot = Slot()
        slot.entry = {"arm": "T"}
        c = self.controller(
            [
                {
                    "method": "item/started",
                    "params": {"item": {"id": "m", "type": "mcpToolCall"}},
                }
            ]
        )
        with self.assertRaises(pilot.InfrastructureError):
            pilot.drive(c, slot, {})

    def test_no_host_command_execution(self):
        c = self.controller(
            [
                {
                    "method": "item/started",
                    "params": {"item": {"id": "x", "type": "commandExecution"}},
                }
            ]
        )
        with self.assertRaises(pilot.InfrastructureError):
            pilot.drive(c, Slot(), {})

    def test_duplicate_dynamic_call_never_reexecuted(self):
        message = {
            "id": 12,
            "method": "item/tool/call",
            "params": {
                "callId": "same",
                "tool": "study",
                "arguments": {
                    "action": "read",
                    "arguments": '{"path":"src/task.alva"}',
                },
            },
        }
        c = self.controller([message, dict(message, id=13), self.terminal()])
        slot = Slot()
        pilot.drive(c, slot, {})
        self.assertEqual(len(slot.actions), 1)
        self.assertIn(
            "DUPLICATE_CALL", c.host.sent[-1]["result"]["contentItems"][0]["text"]
        )

    def test_unknown_usage_fails_closed(self):
        c = self.controller(
            [
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {"tokenUsage": {"total": {}}},
                }
            ]
        )
        with self.assertRaises(pilot.InfrastructureError):
            pilot.drive(c, Slot(), {})

    def test_foreign_terminal_fails_closed(self):
        c = self.controller(
            [
                {
                    "method": "turn/completed",
                    "params": {"turn": {"id": "other", "status": "completed"}},
                }
            ]
        )
        with self.assertRaises(pilot.InfrastructureError):
            pilot.drive(c, Slot(), {})

    def test_fixed_schedule_and_prompt_no_hidden(self):
        frozen = pilot.setup(None)
        self.assertEqual(len(frozen["schedule"]), 12)
        self.assertEqual(frozen["schedule"], pilot.setup(None)["schedule"])
        for entry in frozen["schedule"]:
            text = pilot.prompt(entry, frozen)
            self.assertNotIn("vectors", text)
            self.assertNotIn("create_binary", text)  # no engineering witness recipe
            self.assertNotIn("coding_closure", text)
            if entry["arm"] != "N":
                self.assertNotIn("# ALVA semantic workflow", text)
            else:
                self.assertIn(frozen["docs"]["SKILL.md"], text)


if __name__ == "__main__":
    unittest.main()
