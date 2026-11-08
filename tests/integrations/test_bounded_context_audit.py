import unittest
from benchmarks.bounded_context_audit.accounting import Exposure, analyze, total


class AccountingTests(unittest.TestCase):
    def test_provider_total_not_cache_discounted_or_reasoning_added(self):
        row = {"usage_complete": True, "reported_usage": {"totalTokens": 110,
               "inputTokens": 100, "cachedInputTokens": 90, "outputTokens": 10, "reasoningOutputTokens": 5}}
        self.assertEqual(total(row), 110)
        row["usage_complete"] = False
        self.assertIsNone(total(row))
        self.assertIsNone(total({}))

    def test_exact_utf8_overlap_and_versions(self):
        meter = Exposure()
        source = "a中bc".encode()
        meter.add("a.alva", source, 0, source[:4])
        self.assertEqual(meter.add("a.alva", source, 1, source[1:]),
                         {"delivered": 9, "unique": 6, "duplicate": 3})
        changed = b"z" + source[1:]
        self.assertEqual(meter.add("a.alva", changed, 0, changed)["unique"], 12)
        with self.assertRaises(ValueError): meter.add("a.alva", source, 0, b"wrong")
        with self.assertRaises(UnicodeDecodeError): meter.add("a.alva", source, 1, source[1:2])

    def test_all_pairs_and_adverse_tails_retained(self):
        result = analyze()
        self.assertEqual(len(result["V4"]["pairs"]), 4)
        self.assertEqual(result["V4"]["aggregate_tokens"], {"T": 91109, "V3": 100277, "V4": 91896})
        self.assertGreater(result["V4"]["comparisons"]["T"]["aggregate_ratio"], 1)
        self.assertEqual(len(result["MIC01"]["eligible_pairs"]), 10)
        self.assertEqual(result["MIC01"]["both_success_pairs"], 8)
        self.assertEqual(result["MIC01"]["eligible_pair_correct"], {"T": 9, "N": 8})
        self.assertIsNone(result["actual_source_exposure"]["unique_bytes"])


if __name__ == "__main__": unittest.main()
