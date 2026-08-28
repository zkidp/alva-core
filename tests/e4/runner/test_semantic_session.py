import tempfile
import unittest
from pathlib import Path
from unittest import mock

from semantic_session import SemanticSession


class FakeAgent:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.closed = False

    def call(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"ok": True, "result": {"tool": tool}}

    def close(self):
        self.closed = True


class SemanticSessionTests(unittest.TestCase):
    def make(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        root = Path(temp.name)
        manifest = root / "alva.toml"
        manifest.write_text('[project]\nname="x"\n[modules]\nx="src/main.alva"\n',
                            encoding="utf-8")
        session = SemanticSession("alva", manifest)
        session._core.RecordingAgent = FakeAgent
        self.addCleanup(temp.cleanup)
        return session

    def test_begin_call_abort_close(self):
        session = self.make()
        self.assertTrue(session.start()["ok"])
        agent = session.agent
        self.assertEqual(agent.calls[0][0], "begin_transaction")
        self.assertTrue(session.call("inspect_project", {})["ok"])
        session.close(abort=True)
        self.assertEqual(agent.calls[-1][0], "abort_transaction")
        self.assertTrue(agent.closed)

    def test_commit_close_does_not_abort(self):
        session = self.make()
        session.start()
        agent = session.agent
        session.close(abort=False)
        self.assertEqual([name for name, _ in agent.calls],
                         ["begin_transaction"])

    def test_double_start_and_inactive_call_fail_closed(self):
        session = self.make()
        self.assertFalse(session.call("inspect_project", {})["ok"])
        self.assertTrue(session.start()["ok"])
        self.assertEqual(session.start()["error_code"], "E_SESSION_ACTIVE")
        session.close(abort=True)


if __name__ == "__main__":
    unittest.main()
