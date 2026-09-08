"""Deterministic orchestration stop/failure tests; no native or model calls."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'integrations/skills/alva/scripts'))
from recovery_loop import MinimalIterativeRecovery, ReturnedTurn

STALE = {'ok': False, 'error_code': 'E_AEP_CONFLICT'}


def action(action_id, tool):
    return {'action_id': action_id, 'tool': tool, 'arguments': {}}


class PolicyTests(unittest.TestCase):
    def make(self, dispatch=None):
        calls = []
        def execute(tool, args):
            calls.append(tool)
            return dispatch(tool, args) if dispatch else {'ok': True, 'result': {}}
        return MinimalIterativeRecovery('original task', [{'user': 'original task'}], execute), calls

    def test_exhausted_budget_performs_no_restart(self):
        flow, calls = self.make()
        self.assertEqual(flow.run(STALE, 'project', lambda *_: [], lambda: False), 'UNKNOWN')
        self.assertEqual(calls, [])

    def test_ambiguous_transport_not_retried(self):
        flow, calls = self.make()
        with self.assertRaises(ValueError):
            flow.run({'ok': False, 'error_code': 'TIMEOUT'}, 'project', lambda *_: [], lambda: True)
        self.assertEqual(calls, [])

    def test_failed_begin_stops_before_inspection(self):
        flow, calls = self.make(lambda t, a: {'ok': t != 'begin_transaction', 'result': {}})
        self.assertEqual(flow.run(STALE, 'project', lambda *_: self.fail('asked model'), lambda: True), 'BLOCKED')
        self.assertEqual(calls, ['abort_transaction', 'begin_transaction'])

    def test_no_tool_completion_not_success(self):
        flow, _ = self.make()
        self.assertEqual(flow.run(STALE, 'project', lambda *_: [], lambda: True), 'UNKNOWN')
        self.assertFalse(flow.committed)

    def test_repeated_conflict_discards_stale_tail(self):
        commits = 0
        def dispatch(tool, args):
            nonlocal commits
            if tool == 'commit_transaction':
                commits += 1
                if commits == 1:
                    return STALE
            return {'ok': True, 'result': {}}
        flow, calls = self.make(dispatch)
        turns = iter([ReturnedTurn.completed([action('commit-1', 'commit_transaction'),
                                              action('tail', 'MUST_NOT_EXECUTE')]),
                      ReturnedTurn.completed([action('inspect', 'inspect_project')]),
                      ReturnedTurn.completed([action('commit-2', 'commit_transaction')])])
        self.assertEqual(flow.run(STALE, 'project', lambda *_: next(turns), lambda: True, lambda: 'PASSED'), 'PASSED')
        self.assertNotIn('MUST_NOT_EXECUTE', calls)
        self.assertEqual(calls.count('begin_transaction'), 2)
        starts = [e for e in flow.events if e['event'] == 'recovery_started']
        rejects = [e for e in flow.events if e['event'] == 'stale_rejected']
        self.assertEqual([e['rejected_event_id'] for e in starts], [e['event_id'] for e in rejects])

    def test_verifier_failure_not_success(self):
        flow, _ = self.make()
        self.assertEqual(flow.run(STALE, 'project', lambda *_: ReturnedTurn.completed(
            [action('commit', 'commit_transaction')]), lambda: True, lambda: 'FAILED'), 'FAILED')
        self.assertTrue(flow.committed)

    def test_untyped_verifier_result_is_unknown(self):
        for status in (True, {'ok': True}, None):
            flow, _ = self.make()
            self.assertEqual(flow.run(STALE, 'project', lambda *_: ReturnedTurn.completed(
                [action('commit', 'commit_transaction')]), lambda: True, lambda: status), 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
