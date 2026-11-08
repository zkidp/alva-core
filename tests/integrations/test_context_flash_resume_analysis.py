import unittest
from benchmarks.context_flash_resume.analyze import describe


def row(task, arm, tokens, hold=None):
    return {"id": task + "-" + arm, "task": task, "arm": arm, "submitted_requests": 1, "requests": [{}],
        "reported_usage": {"totalTokens": tokens}, "infrastructure_hold": hold,
        "source_exposure": {"unique_raw_bytes": 10, "raw_delivered_bytes": 10}, "outcome": {"correct": True}}


class AnalysisTests(unittest.TestCase):
    def test_censored_Q01_never_gets_A_ratio_or_full_screen(self):
        rows = [row("Q01", "C", 20)] + [row("Q02", a, t) for a, t in (("A", 10), ("B", 12), ("C", 18))]
        report = describe({"status": "COMPLETED_REMAINING_SLOTS", "rows": rows, "provider_requests_submitted": 4}, {"provider_requests_submitted": 4})
        self.assertFalse(report["full_original_screen_evaluable"])
        self.assertFalse(report["task_triples"][0]["eligible"])
        self.assertNotIn("C_over_A", report["task_triples"][0])
        self.assertEqual(report["eligible_AC_pairs"], 1)
        self.assertAlmostEqual(report["descriptive_median_C_over_A"], 1.8)
        self.assertIsNone(report["all_scientific_total_tokens"])

    def test_infrastructure_pair_is_excluded(self):
        rows = [row("Q02", a, 10, "transport" if a == "A" else None) for a in ("A", "B", "C")]
        result = describe({"status": "HOLD", "rows": rows, "provider_requests_submitted": 3}, {"provider_requests_submitted": 4})
        self.assertEqual(result["eligible_AC_pairs"], 0)
        self.assertIsNone(result["descriptive_median_C_over_A"])


if __name__ == "__main__": unittest.main()
