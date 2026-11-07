"""Public result and replay-safety checks; no provider or private records."""
import json
from pathlib import Path
import unittest
from benchmarks.host_v3_acceptance.safe_entry import refuse_consumed

HERE=Path(__file__).resolve().parents[2]/'benchmarks/host_v3_acceptance'


class PostRun(unittest.TestCase):
    def test_consumed_study_refuses_before_credentials(self):
        with self.assertRaisesRegex(RuntimeError,'CONSUMED_STUDY_NO_REPLAY'):
            refuse_consumed()
    def test_all_registered_slots_and_conservative_dispositions_retained(self):
        result=json.loads((HERE/'RESULTS.json').read_bytes())
        frozen=json.loads((HERE/'FREEZE.json').read_bytes())
        self.assertEqual([r['id'] for r in result['rows']],[r['id'] for r in frozen['schedule']])
        self.assertEqual(result['model_sessions_started'],12)
        self.assertTrue(all(r['valid'] and r['correct'] for r in result['rows']))
        self.assertEqual(result['comparisons']['V2']['disposition'],'EXPLORATORY_COST_ACCEPTANCE_PASS')
        self.assertEqual(result['comparisons']['T']['disposition'],'NO_EXPLORATORY_COST_ADVANTAGE')
        self.assertIsNone(result['dollar_cost'])


if __name__=='__main__':unittest.main()
