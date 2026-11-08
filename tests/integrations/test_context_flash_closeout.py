import unittest
from benchmarks.context_flash_pilot.closeout import clarify


class CloseoutTests(unittest.TestCase):
    def test_uncertain_request_cost_never_becomes_zero_or_complete(self):
        report = {"rows": [{"id": "a", "reported_usage": {"totalTokens": 777}}]}
        batch = {"rows": [{"id": "a", "submitted_requests": 4, "requests": [{}, {}, {}], "infrastructure_hold": "transport unknown"}]}
        frozen = {"schedule": [{"id": "a"}, {"id": "b"}]}
        result = clarify(report, batch, frozen)
        self.assertIsNone(result["batch_total_token_cost"])
        self.assertEqual(result["rows"][0]["unknown_usage_attempts"], 1)
        self.assertFalse(result["rows"][0]["usage_complete_for_submitted_requests"])
        self.assertFalse(result["rows"][0]["model_performance_eligible"])
        self.assertEqual(result["not_started_slots"], [{"id": "b"}])
        self.assertEqual(result["rows"][0]["reported_usage"]["totalTokens"], 777)


if __name__ == "__main__": unittest.main()
