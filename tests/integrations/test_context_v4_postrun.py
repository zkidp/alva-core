import json,unittest
from pathlib import Path
from benchmarks.context_v4.safe_entry import refuse_consumed
HERE=Path(__file__).resolve().parents[2]/'benchmarks/context_v4'


class Postrun(unittest.TestCase):
    def test_consumed_freeze_cannot_replay(self):
        with self.assertRaisesRegex(RuntimeError,'CONSUMED_STUDY_NO_REPLAY'):refuse_consumed()
    def test_tail_regression_and_failed_text_screen_are_retained(self):
        d=json.loads((HERE/'RESULTS.json').read_bytes());f=json.loads((HERE/'FREEZE.json').read_bytes())
        self.assertEqual([r['id'] for r in d['rows']],[r['id'] for r in f['schedule']])
        self.assertTrue(all(r['valid'] and r['correct'] for r in d['rows']))
        self.assertEqual(d['comparisons']['T']['disposition'],'NO_EXPLORATORY_COST_ADVANTAGE')
        self.assertGreater(d['comparisons']['V3']['pairs'][0]['ratio'],1.8)
        self.assertIsNone(d['dollar_cost'])


if __name__=='__main__':unittest.main()
