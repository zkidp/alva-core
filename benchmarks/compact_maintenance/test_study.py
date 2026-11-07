import copy
import json
from pathlib import Path
import unittest

from benchmarks.compact_maintenance.contract import decode_call, study_tools
from benchmarks.compact_maintenance.cost_profile import profile_record, text_content, failed
from benchmarks.compact_maintenance.register import registration, validate
from benchmarks.compact_maintenance.score import screen

HERE = Path(__file__).parent


class DiagnosisTests(unittest.TestCase):
    def test_dynamic_text_normalization_and_error_detection(self):
        item = {"type": "dynamicToolCall", "id": "call1", "tool": "study", "status": "completed",
                "arguments": {"action": "write"}, "success": True,
                "contentItems": [{"type": "inputText", "text": '{"error":"NATIVE_MUTATION_REQUIRED"}'}]}
        self.assertTrue(failed(item))
        event = {"method": "item/completed", "params": {"item": item}}
        result = profile_record({"tool_calls": 1, "events": [event, event]})
        self.assertEqual(result["completed_model_tool_items"], 1)
        self.assertEqual(result["duplicate_terminal_events_ignored"], 1)
        self.assertEqual(result["failed_model_tool_items"], 1)
        self.assertGreater(result["total_text_reply_utf8_bytes"], 0)

    def test_unicode_and_structured_content_are_not_double_counted(self):
        self.assertEqual(len(text_content([{"type": "text", "text": "中"}])), 3)
        self.assertEqual(text_content([{"type": "text", "text": "a"}, {"type": "inputText", "text": "b"}]), b"ab")
        item = {"type": "mcpToolCall", "id": "1", "tool": "inspect_body", "arguments": {},
                "result": {"content": [{"type": "text", "text": "abc"}], "structuredContent": {"body": "abc"}}}
        result = profile_record({"tool_calls": 1, "events": [{"method": "item/completed", "params": {"item": item}}]})
        self.assertEqual(result["total_text_reply_utf8_bytes"], 3)

    def test_missing_terminal_item_not_invented(self):
        result = profile_record({"tool_calls": 1, "events": []})
        self.assertEqual(result["unfinished_or_unrecorded_terminal_items"], 1)

    def test_committed_analysis_binds_old_records_and_pairs(self):
        r = json.loads((HERE / "COST-PROFILE.json").read_bytes())
        old = json.loads((HERE.parent / "maintenance_interface_comparison/RESULTS.json").read_bytes())
        self.assertEqual(len(r["rows"]), 24)
        self.assertEqual(len(r["both_success_pairs"]), 8)
        indexed = {e["id"]: e for e in old["rows"]}
        for row in r["rows"]:
            self.assertEqual(row["record_sha256"], indexed[row["id"]]["record_sha256"])
            self.assertEqual(row["linux_evidence_sha256"], indexed[row["id"]]["linux_evidence_sha256"])
            self.assertEqual(row["completed_model_tool_items"], sum(g["calls"] for g in row["by_category"].values()))
            self.assertGreaterEqual(row["unfinished_or_unrecorded_terminal_items"], 0)
        for arm in ("T", "N"):
            self.assertEqual(r["arms"][arm]["both_success_medians"]["reported_total_tokens"], old["both_success_median_reported_tokens"][arm])
        self.assertIsNone(r["per_category_tokens"])


class ContractTests(unittest.TestCase):
    def test_design_and_task_bytes_do_not_drift(self):
        value = json.loads((HERE / "REGISTRATION.json").read_bytes())
        self.assertFalse(validate(value)["runtime_ready"])
        self.assertEqual(value, registration())
        value["tasks"]["MM02"]["public_task"]["requirement"] = "different"
        with self.assertRaises(ValueError):
            validate(value)

    def test_typed_workbench_and_arm_exposure(self):
        for arm in ("T", "N"):
            for action in ("check", "test", "finish"):
                self.assertEqual(decode_call(arm, "study_" + action, {}), (action, {}))
                with self.assertRaises(ValueError):
                    decode_call(arm, "study_" + action, {"arguments": "{}"})
        with self.assertRaises(ValueError):
            decode_call("N", "study_write", {"revision": "r", "path": "a", "content": "x"})
        for value in (True, 0, 201, "20"):
            with self.assertRaises(ValueError):
                decode_call("T", "study_read", {"revision": "r", "path": "a", "count": value})
        self.assertEqual(len(study_tools("T")), 10)
        self.assertEqual(len(study_tools("N")), 8)


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.design = registration()
        self.rows = [dict(e, correct=True, valid=True, terminal_confirmed=True, identity_match=True,
                          cleanup_confirmed=True, evidence_bound=True, usage_complete=True,
                          reported_usage={"totalTokens": 100 if e["arm"] == "T" else 75,
                                          "inputTokens": 95 if e["arm"] == "T" else 70,
                                          "cachedInputTokens": 50, "outputTokens": 5, "reasoningOutputTokens": 1})
                     for e in self.design["schedule"]]

    def test_boundary_and_no_cached_subtraction(self):
        self.assertEqual(screen(self.design, self.rows)["disposition"], "EXPLORATORY_FAVORABLE_SIGNAL")
        for row in self.rows:
            if row["arm"] == "N":
                row["reported_usage"]["totalTokens"] = 76
        self.assertEqual(screen(self.design, self.rows)["disposition"], "NO_EXPLORATORY_FAVORABLE_SIGNAL")

    def test_infrastructure_and_incomplete_schedule_are_not_failures(self):
        self.assertEqual(screen(self.design, self.rows[:-1])["disposition"], "INCONCLUSIVE_INFRASTRUCTURE")
        self.rows[0]["provider_fault"] = True
        self.rows[0]["correct"] = None
        self.assertEqual(screen(self.design, self.rows)["disposition"], "INCONCLUSIVE_INFRASTRUCTURE")

    def test_success_selection_cannot_hide_lower_completion(self):
        native = next(r for r in self.rows if r["arm"] == "N")
        native["correct"] = False
        self.assertEqual(screen(self.design, self.rows)["disposition"], "NO_EXPLORATORY_FAVORABLE_SIGNAL")

    def test_missing_usage_is_not_zero(self):
        for row in self.rows:
            if row["arm"] == "N":
                row["reported_usage"] = None
        r = screen(self.design, self.rows)
        self.assertEqual(r["disposition"], "INCONCLUSIVE_INSUFFICIENT_PAIRED_SUCCESSES")
        self.assertIsNone(r["median_paired_token_ratio"])

    def test_duplicate_or_mismatched_slot_refused(self):
        with self.assertRaises(ValueError):
            screen(self.design, self.rows + [copy.deepcopy(self.rows[0])])
        self.rows[0]["task"] = "OTHER"
        with self.assertRaises(ValueError):
            screen(self.design, self.rows)


if __name__ == "__main__":
    unittest.main()
