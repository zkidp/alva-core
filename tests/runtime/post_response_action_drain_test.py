"""Deterministic canonical action-drain policy tests; model calls = 0."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'integrations/skills/alva/scripts'))
from recovery_loop import MinimalIterativeRecovery, ReturnedTurn

STALE = {'ok': False, 'error_code': 'E_AEP_CONFLICT'}


class DrainTests(unittest.TestCase):
    def make(self, dispatch=None):
        calls = []

        def execute(tool, arguments):
            calls.append((tool, arguments))
            if dispatch:
                return dispatch(tool, arguments)
            return {'ok': True, 'result': {}, 'execution': {}}

        return MinimalIterativeRecovery('task', [{'user': 'task'}], execute), calls

    @staticmethod
    def action(action_id, tool, **arguments):
        return {'action_id': action_id, 'tool': tool, 'arguments': arguments}

    def test_completed_actions_drain_after_request_budget_exhaustion(self):
        usage = {'total_tokens': 0}
        observed_usage = []

        def dispatch(_tool, _arguments):
            observed_usage.append(usage['total_tokens'])
            return {'ok': True, 'result': {}, 'execution': {}}

        flow, calls = self.make(dispatch)
        turns = 0

        def next_turn(*_):
            nonlocal turns
            turns += 1
            usage['total_tokens'] = 120  # Completed-response usage exhausted request admission.
            return ReturnedTurn.completed([
                self.action('a1', 'inspect_project'),
                self.action('a2', 'change_field', entity='x', field='value', value='y')])

        self.assertEqual(flow.run(STALE, 'p', next_turn,
                                  lambda: usage['total_tokens'] < 120), 'UNKNOWN')
        self.assertEqual(turns, 1)  # No request after exhaustion.
        self.assertEqual([x[0] for x in calls][-2:], ['inspect_project', 'change_field'])
        self.assertEqual(observed_usage[-2:], [120, 120])
        self.assertEqual(usage['total_tokens'], 120)  # Drain never clears the real ledger.

    def test_action_gate_remains_independent(self):
        for reason in ('TOOL_LIMIT', 'WALL_LIMIT', 'CANCELLED', 'SAFETY_DENIED'):
            with self.subTest(reason=reason):
                flow, calls = self.make()
                turn = ReturnedTurn.completed([
                    self.action('a1', 'inspect_project'), self.action('a2', 'change_field')])
                gate = lambda tool, _args: True if tool == 'inspect_project' else reason
                self.assertEqual(flow.run(STALE, 'p', lambda *_: turn, lambda: True,
                                          action_admission=gate), 'UNKNOWN')
                self.assertEqual([x[0] for x in calls][-1:], ['inspect_project'])
                self.assertEqual(flow.events[-1]['reason'], reason)

    def test_incomplete_and_unknown_turns_never_dispatch_actions(self):
        for turn in (ReturnedTurn.incomplete('r1'), ReturnedTurn('unknown'),
                     ReturnedTurn.completed([('change_field', {})]),
                     [('change_field', {})], object()):
            flow, calls = self.make()
            self.assertEqual(flow.run(STALE, 'p', lambda *_: turn, lambda: True), 'UNKNOWN')
            self.assertEqual([x[0] for x in calls],
                             ['abort_transaction', 'begin_transaction', 'inspect_project'])

    def test_conflict_stops_old_action_tail_and_respects_request_admission(self):
        def dispatch(tool, _args):
            return STALE if tool == 'change_field' else {'ok': True, 'result': {}}

        flow, calls = self.make(dispatch)
        may_request = {'value': True}

        def next_turn(*_):
            may_request['value'] = False
            return ReturnedTurn.completed([
                self.action('conflict', 'change_field'), self.action('tail', 'MUST_NOT_RUN')])

        self.assertEqual(flow.run(STALE, 'p', next_turn, lambda: may_request['value']), 'UNKNOWN')
        self.assertNotIn('MUST_NOT_RUN', [x[0] for x in calls])

    def test_successful_commit_stops_tail_and_verifier_is_independent(self):
        flow, calls = self.make()
        turn = ReturnedTurn.completed([
            self.action('commit', 'commit_transaction'), self.action('tail', 'MUST_NOT_RUN')])
        self.assertEqual(flow.run(STALE, 'p', lambda *_: turn, lambda: True), 'UNKNOWN')
        self.assertTrue(flow.committed)
        self.assertNotIn('MUST_NOT_RUN', [x[0] for x in calls])
        verified, _ = self.make()
        self.assertEqual(verified.run(STALE, 'p', lambda *_: turn, lambda: True,
                                      lambda: 'PASSED'), 'PASSED')

    def test_duplicate_action_id_is_not_executed_twice(self):
        flow, calls = self.make()
        turns = iter([
            ReturnedTurn.completed([self.action('same', 'inspect_project')]),
            ReturnedTurn.completed([self.action('same', 'inspect_project'),
                                    self.action('commit', 'commit_transaction')])])
        self.assertEqual(flow.run(STALE, 'p', lambda *_: next(turns), lambda: True), 'UNKNOWN')
        self.assertEqual([x[0] for x in calls].count('inspect_project'), 2)  # restart + action once
        self.assertTrue(any(e['event'] == 'action_duplicate_suppressed' for e in flow.events))

    def test_unknown_dispatch_outcome_is_not_blindly_retried(self):
        def dispatch(tool, _args):
            if tool == 'change_field':
                raise TimeoutError('unknown execution outcome')
            return {'ok': True, 'result': {}}

        flow, calls = self.make(dispatch)
        turns = 0

        def next_turn(*_):
            nonlocal turns
            turns += 1
            return ReturnedTurn.completed([self.action('uncertain', 'change_field')])

        self.assertEqual(flow.run(STALE, 'p', next_turn, lambda: True), 'UNKNOWN')
        self.assertEqual(turns, 1)
        self.assertEqual([x[0] for x in calls].count('change_field'), 1)
        self.assertEqual(flow.action_ledger['uncertain']['state'], 'UNKNOWN')

    def test_no_unrequested_commit_is_synthesized(self):
        flow, calls = self.make()
        allowed = iter([True, True, False])
        turn = ReturnedTurn.completed([self.action('inspect', 'inspect_project')])
        self.assertEqual(flow.run(STALE, 'p', lambda *_: turn, lambda: next(allowed)), 'UNKNOWN')
        self.assertNotIn('commit_transaction', [x[0] for x in calls])


if __name__ == '__main__':
    unittest.main()
