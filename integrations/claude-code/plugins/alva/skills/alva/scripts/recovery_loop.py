"""Transport-neutral host orchestration; no model client or transaction semantics.

dispatch(tool, arguments) must return the AEP envelope {ok, result, execution}.
MCP adapters retain/inject transaction_id and normalize structuredContent.
next_turn receives the original assignment and accumulated host conversation;
the host translates records to its model protocol and enforces its own budget.
verify is an independent host callback, never an agent-provided success flag.
"""
from copy import deepcopy
from uuid import uuid4


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

    def run(self, rejected, project, next_turn, budget_available, verify=None):
        """Continue read/act feedback until commit+host verification or a stop.

        next_turn(assignment, conversation) returns [(tool, arguments), ...].
        An empty turn means the host/agent stopped, not that the task passed.
        budget_available is checked before every turn and operation. There is
        no one-response recovery cap and no compiler-PASS completion shortcut.
        """
        if not budget_available():
            return 'UNKNOWN'
        if not self.restart(rejected, project):
            return 'BLOCKED'
        while budget_available():
            actions = next_turn(self.assignment, deepcopy(self.conversation))
            if not actions:
                return 'UNKNOWN'
            for tool, arguments in actions:
                if not budget_available():
                    return 'UNKNOWN'
                response = self.call(tool, arguments)
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
        return 'UNKNOWN'
