import unittest
from pathlib import Path
import subprocess
import sys
from benchmarks.maintenance_interface_comparison.provider_gate import provider_fault, guarded_drive


class ProviderGate(unittest.TestCase):
    def test_quota_failure_stops_before_next_launch(self):
        record = {"terminal_status": "failed", "events": [{"method": "turn/completed", "params": {
            "turn": {"status": "failed", "error": {"codexErrorInfo": "usageLimitExceeded"}}}}]}
        def original(controller, slot, output):
            output.update(record)
        output = {}
        guarded_drive(original)(None, None, output)
        self.assertEqual(provider_fault(output)["code"], "usageLimitExceeded")
        self.assertIn("infrastructure_hold", output)
        launches = 1
        if not output.get("infrastructure_hold"):
            launches += 1
        self.assertEqual(launches, 1)

    def test_wrong_candidate_or_observation_limit_is_not_provider_fault(self):
        for status in ("completed", "interrupted"):
            output = {"terminal_status": status, "outcome": {"correct": False}}
            guarded_drive(lambda c, s, r: None)(None, None, output)
            self.assertNotIn("infrastructure_hold", output)

    def test_unknown_terminal_failure_fails_closed(self):
        output = {"terminal_status": "failed"}
        guarded_drive(lambda c, s, r: None)(None, None, output)
        self.assertIn("UNKNOWN_TERMINAL_FAILURE", output["infrastructure_hold"])

    def test_safe_entry_refuses_old_freeze_without_starting_model(self):
        entry = Path(__file__).with_name("safe_run.py")
        result = subprocess.run([sys.executable, str(entry), "--connection", "not-read-by-refused-entry.json"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NO_GENERATION", result.stderr)


if __name__ == "__main__":
    unittest.main()
