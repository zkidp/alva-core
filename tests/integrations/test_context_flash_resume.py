import json
import unittest
import urllib.error
from unittest.mock import patch

from benchmarks.context_flash_resume.transport import DiagnosticAPI, diagnostic
from benchmarks.context_flash_resume.register import remaining


class ResumeTests(unittest.TestCase):
    def test_exception_context_survives_suppression_and_is_redacted(self):
        try:
            try: raise urllib.error.URLError(OSError(11001, "getaddrinfo failed https://user:private@proxy.invalid/sk-private"))
            except Exception: raise RuntimeError("suppressed") from None
        except Exception as exc: result = diagnostic(exc)
        encoded = json.dumps(result)
        self.assertNotIn("private", encoded)
        self.assertNotIn("proxy.invalid", encoded)
        self.assertIn("DNS", encoded)
        self.assertIn("11001", encoded)

    def test_observer_does_not_retry_or_modify_payload(self):
        client = object.__new__(DiagnosticAPI)
        client.failures = []
        request = {"model": "deepseek-flash", "messages": []}
        with patch("benchmarks.compact_deepseek.api.API.request", side_effect=urllib.error.URLError(OSError(111, "connection refused"))) as original:
            with self.assertRaises(urllib.error.URLError): client.request("/chat/completions", request, timeout=90)
        original.assert_called_once_with("/chat/completions", request, timeout=90)
        self.assertEqual(client.failures[0]["exception_chain"][0]["class"], "URLError")

    def test_interrupted_slot_is_never_replaced(self):
        schedule = [{"id": "Q01-A"}, {"id": "Q01-B"}, {"id": "Q01-C"}]
        self.assertEqual(remaining({"schedule": schedule}, {"status": "HOLD", "rows": [{"id": "Q01-A"}]}), schedule[1:])
        with self.assertRaises(ValueError): remaining({"schedule": schedule}, {"status": "HOLD", "rows": [{"id": "Q01-A"}, {"id": "Q01-B"}]})


if __name__ == "__main__": unittest.main()
