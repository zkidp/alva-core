"""Unit tests for the E4 formal Luna runner (no binary, no provider calls)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from formal_luna_runner import (
    ARMS,
    REPS,
    classify_failure,
    derive_metrics,
    load_statements,
    save_state,
    schedule_cells,
    sha256_bytes,
)

RUNNER_DIR = Path(__file__).resolve().parent


def _tempdir():
    # Runner dir is writable in all supported environments and tmp* is
    # gitignored; %TEMP% may be read-only under the local Windows sandbox.
    return tempfile.TemporaryDirectory(dir=RUNNER_DIR)


class ScheduleTests(unittest.TestCase):
    def test_96_cells_deterministic(self):
        with _tempdir() as tmp:
            root = Path(tmp)
            for task in ["A01", "A02", "A03", "A04", "A05", "A06",
                         "A07", "A08", "A09", "A10", "A11", "A12R"]:
                task_dir = root / task
                (task_dir / "fixture").mkdir(parents=True)
            cells = schedule_cells(root)
        self.assertEqual(len(cells), 96)
        self.assertEqual(
            [c[0] for c in cells][:12],
            ["A01", "A01", "A01", "A01", "A01", "A01", "A01", "A01",
             "A02", "A02", "A02", "A02"])
        self.assertEqual(cells[0], ("A01", "TEXT", 1))
        self.assertEqual(cells[1], ("A01", "TEXT", 2))
        self.assertEqual(cells[2], ("A01", "TEXT_VERIFY", 1))
        self.assertEqual(cells[6], ("A01", "FULL_ALVA", 1))
        self.assertEqual(cells[8], ("A02", "TEXT", 1))
        self.assertEqual(cells[95], ("A12R", "FULL_ALVA", 2))
        self.assertEqual(len(set(cells)), 96)
        for task, arm, rep in cells:
            self.assertIn(arm, ARMS)
            self.assertIn(rep, REPS)


class MetricTests(unittest.TestCase):
    def _telemetry(self, count, prompt=100, output=10):
        records = []
        for _ in range(count):
            records.append({
                "usage": {
                    "input_tokens": prompt,
                    "input_tokens_details": {
                        "cached_tokens": 5, "cache_write_tokens": 3},
                    "output_tokens": output,
                    "output_tokens_details": {"reasoning_tokens": 2},
                    "total_tokens": prompt + output,
                },
            })
        return records

    def test_basic_metrics(self):
        trajectory = [
            {"ordinal": 1, "tool": "read_file", "args": {"path": "src/main.alva"},
             "result": {"ok": True, "result": {}},
             "tool_call_id": "c1"},
            {"ordinal": 2, "tool": "write_file",
             "args": {"path": "src/main.alva", "content": "x = 2"},
             "result": {"ok": True, "result": {}},
             "tool_call_id": "c2"},
            {"ordinal": 3, "tool": "unknown_tool", "args": {},
             "result": {"ok": False, "error_code": "E_UNKNOWN_TOOL",
                        "message": "nope"},
             "tool_call_id": "c3"},
        ]
        telemetry = self._telemetry(4)
        verifier = {"ok": True, "reason": "PASS"}
        metrics = derive_metrics("TEXT", trajectory, telemetry, verifier, 12.5,
                                 b"tool-schema-bytes" * 10)
        self.assertTrue(metrics["correctness"])
        self.assertEqual(metrics["total_prompt_tokens"], 400)
        self.assertEqual(metrics["completion_tokens"], 40)
        self.assertEqual(metrics["api_turns"], 4)
        self.assertEqual(metrics["wall_seconds"], 12.5)
        self.assertEqual(metrics["raw_tool_call_count"], 3)
        self.assertEqual(metrics["tool_selection_failures"], 1)
        # first successful mutation is ordinal 2 -> prefix of 2 telemetry lines
        self.assertEqual(metrics["first_change_latency"], 2 * (100 + 10))
        self.assertEqual(metrics["semantic_adoption"], 0)
        self.assertEqual(metrics["edit_payload_bytes"], len("x = 2".encode()))
        self.assertGreater(metrics["static_tool_schema_bytes"], 0)

    def test_semantic_adoption_hybrid(self):
        trajectory = [
            {"ordinal": 1, "tool": "rename_entity", "args": {},
             "result": {"ok": True, "result": {}}, "tool_call_id": "c1"},
            {"ordinal": 2, "tool": "read_file", "args": {},
             "result": {"ok": True, "result": {}}, "tool_call_id": "c2"},
        ]
        metrics = derive_metrics("HYBRID", trajectory, self._telemetry(3),
                                 {"ok": True}, 1.0, b"x" * 100)
        self.assertEqual(metrics["semantic_adoption"], 1)

    def test_no_mutation_latency_none(self):
        trajectory = [
            {"ordinal": 1, "tool": "read_file", "args": {},
             "result": {"ok": True, "result": {}}, "tool_call_id": "c1"},
        ]
        metrics = derive_metrics("TEXT", trajectory, self._telemetry(1),
                                 {"ok": False}, 1.0, b"x" * 100)
        self.assertIsNone(metrics["first_change_latency"])
        self.assertFalse(metrics["correctness"])


class ClassificationTests(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(classify_failure("E_UNKNOWN_TOOL"),
                         "tool_selection_failure")
        self.assertEqual(classify_failure("E_INVALID_PROJECT"),
                         "argument_binding_failure")
        self.assertEqual(classify_failure("E_PATH_NOT_ALLOWED"),
                         "argument_binding_failure")
        self.assertEqual(classify_failure("E_PROJECT_CHECK"),
                         "other_failure")
        self.assertEqual(classify_failure(None), "other")


class StateTests(unittest.TestCase):
    def test_save_state(self):
        with _tempdir() as tmp:
            out = Path(tmp)
            schedule = [("A01", "TEXT", 1), ("A01", "TEXT", 2)]
            state = save_state(out, schedule, ["A01-TEXT-r1"], "2026-08-29T00:00:00Z")
            self.assertEqual(state["schedule_total"], 2)
            self.assertEqual(state["remaining"], ["A01-TEXT-r2"])
            on_disk = json.loads((out / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(on_disk["completed"], ["A01-TEXT-r1"])


class HashTests(unittest.TestCase):
    def test_sha256_bytes(self):
        self.assertEqual(
            sha256_bytes(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


class StatementTests(unittest.TestCase):
    def test_wrapped_and_flat_formats(self):
        with _tempdir() as tmp:
            root = Path(tmp)
            wrapped = root / "wrapped.json"
            wrapped.write_text(json.dumps({
                "schema_version": "e4-task-statements-v1",
                "statements": {"A01": "one", "A02": "two"},
            }), encoding="utf-8")
            flat = root / "flat.json"
            flat.write_text(json.dumps({"A01": "one", "A02": "two"}),
                            encoding="utf-8")
            self.assertEqual(load_statements(wrapped),
                             {"A01": "one", "A02": "two"})
            self.assertEqual(load_statements(flat),
                             {"A01": "one", "A02": "two"})


if __name__ == "__main__":
    unittest.main()
