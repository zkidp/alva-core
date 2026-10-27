"""Synthetic accounting tests + bounded public derived-data consistency.

CI does not possess or pretend to reconstruct the private P26 archive.
"""

import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.p27_bottleneck import audit


class AccountingTests(unittest.TestCase):
    def test_archive_hash_fail_closed_before_read(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "wrong.zip"
            path.write_bytes(b"not the original trajectory")
            with self.assertRaisesRegex(ValueError, "ARCHIVE_SHA256_MISMATCH"):
                audit.verified_zip(path)

    def test_enclosing_usage_is_not_per_call_charge(self):
        usage = [
            {
                "ordinal": 1,
                "event_index": 3,
                "cumulative": {k: 100 for k in audit.FIELDS},
            },
            {
                "ordinal": 2,
                "event_index": 10,
                "cumulative": {k: 170 for k in audit.FIELDS},
            },
        ]
        one, two = audit.bracket(usage, 4, 7), audit.bracket(usage, 5, 8)
        self.assertEqual(one["enclosing_increment"], two["enclosing_increment"])
        self.assertIsNone(one["individual_call_token_charge"])
        self.assertEqual(one["before_usage_ordinal"], two["before_usage_ordinal"])

    def test_unreported_usage_before_call_not_imputed_zero(self):
        row = audit.bracket([], 2, 5)
        self.assertIsNone(row["cumulative_before"])
        self.assertIsNone(row["cumulative_after"])
        self.assertIsNone(row["enclosing_increment"])
        self.assertFalse(row["before_is_observed_usage"])

    def test_missing_usage_field_stays_unknown(self):
        row = audit.difference(
            audit.totals({"totalTokens": 10}), audit.totals({"totalTokens": 4})
        )
        self.assertEqual(row["totalTokens"], 6)
        self.assertIsNone(row["cachedInputTokens"])

    def test_cumulative_usage_monotonicity(self):
        def event(n):
            return {
                "method": "thread/tokenUsage/updated",
                "params": {"tokenUsage": {"total": {"totalTokens": n}, "last": {}}},
            }

        with self.assertRaisesRegex(ValueError, "Non-monotonic"):
            audit.usage_events([event(30), event(20)])

    def test_check_failure_not_tool_envelope_failure(self):
        answer, failed = audit.decode_answer(
            {
                "type": "dynamicToolCall",
                "success": True,
                "contentItems": [
                    {"type": "inputText", "text": '{"status":"COMPILE_FAIL"}'}
                ],
            }
        )
        self.assertFalse(failed)
        self.assertEqual(answer["status"], "COMPILE_FAIL")


class PublicConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = audit.load(audit.HERE / "STAGE-TRAJECTORIES.json")
        cls.slots = cls.data["slots"]

    def test_source_blob_identity(self):
        for name, digest in self.data["source"]["public_source_sha256"].items():
            self.assertEqual(audit.sha(audit.public_blob(name)), digest)

    def test_counts_and_usage_reconcile_without_private_zip(self):
        published = {s["id"]: s for s in audit.public_json("RESULTS.json")["slots"]}
        self.assertEqual(len(self.slots), 12)
        for slot in self.slots:
            original = published[slot["id"]]
            self.assertEqual(len(slot["calls"]), original["tool_calls"])
            self.assertEqual(
                slot["final_totals"], audit.totals(original["usage"]["total"])
            )
            self.assertEqual(slot["observed_disposition"], original["disposition"])
            total = slot["final_totals"]
            self.assertEqual(
                total["inputTokens"] + total["outputTokens"], total["totalTokens"]
            )
            self.assertLessEqual(total["cachedInputTokens"], total["inputTokens"])
            self.assertLessEqual(total["reasoningOutputTokens"], total["outputTokens"])
            self.assertLess(slot["thresholds"]["wall_elapsed_seconds"], 480)

    def test_reference_calls_are_one_content_addressed_revision(self):
        slot = next(s for s in self.slots if s["id"] == "P26-09-HE41-N")
        self.assertEqual(slot["construction_calls"], 2)
        self.assertEqual(slot["distinct_constructed_revisions"], 1)
        self.assertEqual(slot["calls"][9]["repeat_of_ordinal"], 9)
        self.assertFalse(slot["fresh_target_changed"])

    def test_baseline_pass_not_counted_as_post_edit_pass(self):
        by_task = {s["task"]: s for s in self.slots if s["arm"] == "T"}
        self.assertEqual(by_task["HE42"]["compiler_check_passes"], 1)
        self.assertEqual(by_task["HE42"]["post_edit_compiler_check_passes"], 0)
        self.assertEqual(by_task["HE3"]["post_edit_compiler_check_passes"], 3)
        self.assertTrue(
            all(s["same_source_state_repeats"] == 0 for s in by_task.values())
        )

    def test_under_specified_success_is_not_connected_commit(self):
        slot = next(s for s in self.slots if s["id"] == "P26-12-HE23-B")
        node = next(r for r in slot["calls"] if r["operation"] == "create_call")
        self.assertEqual(node["result"], "SUCCESS_ENVELOPE")
        self.assertEqual(
            node["missing_required_fields_vs_frozen_native_schema"], ["name"]
        )
        self.assertTrue(slot["authority_published"])
        self.assertFalse(slot["fresh_target_changed"])

    def test_tool_threshold_precedes_later_token_notification(self):
        slot = next(s for s in self.slots if s["id"] == "P26-07-HE3-T")
        limits = slot["thresholds"]
        self.assertEqual(limits["first_observed_trigger"], "TOOL")
        self.assertLess(
            limits["tool_cross_event_index"], limits["token_cross_event_index"]
        )

    def test_no_raw_transcript_or_private_metadata_export(self):
        text = json.dumps(self.data)
        for key in (
            "thread_id",
            "turn_id",
            "installationId",
            "serverName",
            "agentMessage",
            "contentItems",
            "reasoningText",
        ):
            self.assertNotIn('"' + key + '"', text)
        self.assertNotIn("C:\\\\Users", text)
        self.assertTrue(
            all(
                r["usage_bracket"]["individual_call_token_charge"] is None
                for s in self.slots
                for r in s["calls"]
            )
        )

    def test_next_design_has_only_two_unexecuted_fixed_task_slots(self):
        design = audit.load(audit.HERE / "NEXT-EXPERIMENT.json")
        self.assertEqual(design["status"], "DESIGN_ONLY_NOT_EXECUTED_NOT_AUTHORIZED")
        self.assertEqual(design["fixed_task"], "HE41")
        self.assertEqual(design["maximum_model_tasks"], 2)
        self.assertEqual(len(design["slots"]), 2)
        self.assertEqual(design["extra_repetitions"], 0)


if __name__ == "__main__":
    unittest.main()
