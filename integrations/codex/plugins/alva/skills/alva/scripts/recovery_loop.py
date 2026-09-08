"""Transport-neutral host orchestration; no model client or transaction semantics.

dispatch(tool, arguments) must return the AEP envelope {ok, result, execution}.
MCP adapters retain/inject transaction_id and normalize structuredContent.
next_turn receives the original assignment and accumulated host conversation;
the host translates records to its model protocol and enforces its own budget.
verify is an independent host callback, never an agent-provided success flag.
"""
from copy import deepcopy
from uuid import uuid4


class ReturnedTurn:
    """Host-normalized provider turn; actions are usable only when completed."""

    def __init__(self, status, actions=(), response_id=None):
        if status not in {'completed', 'incomplete', 'unknown'}:
            raise ValueError('Unsupported provider turn status')
        self.status = status
        self.actions = list(actions)
        self.response_id = response_id

    @classmethod
    def completed(cls, actions, response_id=None):
        return cls('completed', actions, response_id)

    @classmethod
    def incomplete(cls, response_id=None):
        return cls('incomplete', (), response_id)


class MinimalIterativeRecovery:
    def __init__(self, assignment, conversation, dispatch, event_sink=None):
        self.assignment = assignment
        self.conversation = deepcopy(conversation)
        self.dispatch = dispatch
        self.event_sink = event_sink
        self.events = []
        self.committed = False
        self.verification = 'UNKNOWN'
        self.recovery_id = uuid4().hex
        self.action_ledger = {}

    def emit(self, kind, response=None, **fields):
        event = {'schema': 'alva.integration-recovery.v1', 'sequence': len(self.events) + 1,
                 'recovery_id': self.recovery_id,
                 'event_id': f'{self.recovery_id}:{len(self.events) + 1}',
                 'event': kind, 'core_event_id': (response or {}).get('execution', {}).get('event_id'),
                 **fields}
        self.events.append(event)
        if self.event_sink:
            try:
                self.event_sink(deepcopy(event))
            except Exception:
                pass  # Observational only, including sink failure.
        return event['event_id']

    def call(self, tool, arguments):
        response = self.dispatch(tool, arguments)
        self.conversation.append({'tool': tool, 'arguments': deepcopy(arguments),
                                  'response': deepcopy(response)})
        if tool.startswith('inspect') or tool == 'resolve_entity':
            self.emit('inspection', response, ok=response['ok'])
        elif tool == 'check_transaction':
            self.emit('check', response, ok=response['ok'])
        elif tool == 'commit_transaction':
            self.emit('commit', response, ok=response['ok'])
        elif response.get('execution', {}).get('state') == 'mutation_staged':
            self.emit('mutation', response, ok=response['ok'])
        return response

    def normalize_turn(self, returned):
        """Normalize a completed host response without interpreting its content.

        Adapters must pass ReturnedTurn after verifying provider completion.
        """
        if isinstance(returned, ReturnedTurn):
            turn = returned
        else:
            return ReturnedTurn('unknown')
        if turn.status != 'completed':
            return turn
        normalized = []
        for action in turn.actions:
            if not isinstance(action, dict):
                return ReturnedTurn('unknown', response_id=turn.response_id)
            action_id = action.get('action_id')
            tool = action.get('tool')
            arguments = action.get('arguments')
            if (not isinstance(action_id, str) or not action_id or
                    not isinstance(tool, str) or not isinstance(arguments, dict)):
                return ReturnedTurn('unknown', response_id=turn.response_id)
            normalized.append((action_id, tool, arguments))
        return ReturnedTurn.completed(normalized, turn.response_id)

    @staticmethod
    def action_gate(action_admission, tool, arguments):
        if action_admission is None:
            return None
        decision = action_admission(tool, deepcopy(arguments))
        if decision is True or decision is None:
            return None
        if decision is False:
            return 'HOST_ACTION_GATE'
        return str(decision)

    def deliver(self, action_id, tool, arguments):
        """Dispatch once; an ambiguous outcome is recorded and never retried."""
        prior = self.action_ledger.get(action_id)
        if prior is not None:
            self.emit('action_duplicate_suppressed', action_id=action_id,
                      prior_state=prior['state'])
            return prior.get('response'), True
        self.action_ledger[action_id] = {'state': 'DISPATCHING', 'tool': tool}
        self.emit('action_delivery_started', action_id=action_id, tool=tool)
        try:
            response = self.call(tool, arguments)
        except Exception as error:
            self.action_ledger[action_id] = {'state': 'UNKNOWN', 'tool': tool,
                                             'error_type': type(error).__name__}
            self.emit('action_outcome_unknown', action_id=action_id, tool=tool,
                      error_type=type(error).__name__)
            return None, False
        self.action_ledger[action_id] = {'state': 'COMPLETED', 'tool': tool,
                                         'response': deepcopy(response)}
        self.emit('action_delivered', response, action_id=action_id, tool=tool,
                  ok=response.get('ok'))
        return response, False

    @staticmethod
    def conflict(response):
        return not response['ok'] and response.get('error_code') == 'E_AEP_CONFLICT'

    def restart(self, rejected, project):
        if not self.conflict(rejected):
            raise ValueError('Only a confirmed stale/conflict rejection may restart')
        self.conversation.append({'stale_rejection': deepcopy(rejected)})
        rejected_id = self.emit('stale_rejected', rejected)
        # Abort drops only private staging, NOT conversation or assignment.
        aborted = self.call('abort_transaction', {})
        if not aborted['ok']:
            return False
        begun = self.call('begin_transaction', {'project': project})
        if not begun['ok']:
            return False
        self.emit('recovery_started', begun, rejected_event_id=rejected_id,
                  transaction_id=begun.get('result', {}).get('transaction_id'),
                  current_revision=begun.get('result', {}).get('project_revision'))
        # Return current authoritative facts into the SAME conversation.
        return self.call('inspect_project', {})['ok']

    def run(self, rejected, project, next_turn, budget_available, verify=None,
            action_admission=None):
        """Continue read/act feedback until commit+host verification or a stop.

        next_turn returns ReturnedTurn after validating the response envelope.
        A completed empty turn means the host/agent stopped, not task success.
        budget_available is request admission: it is checked before requesting
        each next turn, never used to discard actions from a completed turn.
        action_admission is the host's independent tool/wall/cancel/safety gate.
        There is no one-response recovery cap or compiler-PASS shortcut.
        """
        if not budget_available():
            return 'UNKNOWN'
        if not self.restart(rejected, project):
            return 'BLOCKED'
        while True:
            if not budget_available():
                return 'UNKNOWN'
            returned = self.normalize_turn(next_turn(
                self.assignment, deepcopy(self.conversation)))
            if returned.status != 'completed':
                self.emit('response_not_completed', status=returned.status,
                          response_id=returned.response_id)
                return 'UNKNOWN'
            if not returned.actions:
                return 'UNKNOWN'
            for action_id, tool, arguments in returned.actions:
                gate = self.action_gate(action_admission, tool, arguments)
                if gate:
                    self.emit('action_withheld', action_id=action_id, tool=tool,
                              reason=gate)
                    return 'UNKNOWN'
                response, duplicate = self.deliver(action_id, tool, arguments)
                if response is None:
                    return 'UNKNOWN'
                if duplicate:
                    continue
                if self.conflict(response):
                    if not self.restart(response, project):
                        return 'BLOCKED'
                    break  # Drop remaining stale actions; ask the same writer again.
                if tool == 'commit_transaction' and response['ok']:
                    self.committed = True
                    if verify is not None:
                        try:
                            status = verify()
                        except Exception:
                            status = 'UNKNOWN'
                        if not isinstance(status, str) or status not in {'PASSED', 'FAILED', 'UNKNOWN'}:
                            status = 'UNKNOWN'
                        self.verification = status
                        self.emit('final_verification', status=status)
                    return self.verification
