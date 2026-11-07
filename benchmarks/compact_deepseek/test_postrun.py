"""Post-run artifact consistency and consumed-freeze protection; no models."""
import json
from pathlib import Path
import statistics
import tempfile
import unittest

from benchmarks.compact_deepseek.safe_entry import reserve

HERE = Path(__file__).parent


class PostrunTests(unittest.TestCase):
    def test_new_reservation_is_exclusive_and_consumed_freeze_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); freeze = root / "freeze.json"; freeze.write_text("{}")
            marker = reserve(freeze, root / "run")
            self.assertTrue(marker.exists())
            with self.assertRaises(FileExistsError): reserve(freeze, root / "run")
            import hashlib
            wave = root / "run/wave01"; wave.mkdir()
            (wave / "GENERATION-STARTED.json").write_text(json.dumps({"freeze_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest()}))
            with self.assertRaisesRegex(RuntimeError, "CONSUMED_FREEZE"):
                reserve(freeze, root / "run")

    def test_public_summary_recomputes_fixed_screen_and_schedule(self):
        result = json.loads((HERE / "RESULTS.json").read_bytes())
        freeze = json.loads((HERE / "FREEZE.json").read_bytes())
        self.assertEqual(len(result["rows"]), 16)
        self.assertEqual([{k:r[k] for k in ("id", "task", "repeat", "arm")} for r in result["rows"]], freeze["schedule"])
        self.assertTrue(all(r["valid"] and r["cleanup_confirmed"] and r["identity_before"] and r["identity_after"] for r in result["rows"]))
        ratios = [p["N_total"] / p["T_total"] for p in result["pairs"] if "ratio" in p]
        self.assertEqual(len(ratios), 6)
        self.assertEqual(statistics.median(ratios), result["median_paired_token_ratio"])
        for arm in ("T", "N"):
            rows = [r for r in result["rows"] if r["arm"] == arm]
            self.assertEqual(sum(r["correct"] for r in rows), result["arms"][arm]["correct"])
            self.assertEqual(sum(r["reported_usage"]["totalTokens"] for r in rows), result["arms"][arm]["observed_complete_usage_sum"]["totalTokens"])
        self.assertEqual(result["disposition"], "NO_EXPLORATORY_FAVORABLE_SIGNAL")
        self.assertIsNone(result["arms"]["N"]["dollar_cost"])

    def test_validation_retains_all_rows_and_preflight(self):
        validation = json.loads((HERE / "VALIDATION.json").read_bytes())
        preflight = json.loads((HERE / "PREFLIGHT.json").read_bytes())
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(validation["complete_schedule"])
        self.assertEqual(len(validation["rows"]), 16)
        self.assertEqual(len(preflight["rows"]), 8)
        self.assertEqual(preflight["model_generation_calls"], 0)


if __name__ == "__main__": unittest.main()
