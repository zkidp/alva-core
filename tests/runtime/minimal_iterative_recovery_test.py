"""Zero-model product integration tests on real CLI and MCP transactions."""
import argparse
import copy
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'integrations/skills/alva/scripts'))
from recovery_loop import MinimalIterativeRecovery
from intent_preserving_recovery_test import Agent


class Mcp:
    def __init__(self, binary, log):
        self.p = subprocess.Popen([str(binary), 'mcp', '--event-log', str(log)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding='utf-8')
        self.index = 0
        self.tx = None
        self.handles = []
        self.request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                    'clientInfo': {'name': 'recovery-test', 'version': '1'}})

    def request(self, method, params):
        self.index += 1
        self.p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.index,
                                      'method': method, 'params': params}) + '\n')
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def call(self, tool, **args):
        if tool != 'begin_transaction':
            args['transaction_id'] = self.tx
        envelope = self.request('tools/call', {'name': tool, 'arguments': args})['result']
        data = envelope['structuredContent']
        if envelope.get('isError'):
            # MCP currently carries native errors as structured message text.
            message = data.get('message', data.get('error', ''))
            if isinstance(message, dict):
                message = message.get('message', '')
            return {'ok': False, 'message': message,
                    'error_code': str(message).split(':')[0].split(' ')[0]}
        if tool == 'begin_transaction':
            self.tx = data['transaction_id']
            self.handles.append(self.tx)
        if tool in {'abort_transaction', 'commit_transaction'}:
            self.tx = None
        return {'ok': True, 'result': data, 'execution': data.get('execution', {})}

    def close(self):
        self.p.stdin.close()
        assert self.p.wait(timeout=10) == 0
        assert not self.p.stderr.read()


def scenario(binary, root, mode, use_mcp=False, verifier_available=True):
    project = root / ('mcp' if use_mcp else mode)
    shutil.copytree(ROOT / 'tests/project', project)
    manifest = str(project / 'alva.toml')
    original_source = (project / 'src/app.alva').read_bytes()
    log = root / (project.name + '-events.jsonl')
    writer = Mcp(binary, log) if use_mcp else Agent(binary, log if mode != 'off' else None, 'writer')
    winner = Agent(binary, None, 'winner')
    try:
        assert writer.call('begin_transaction', project=manifest)['ok']
        assert winner.call('begin_transaction', project=manifest)['ok']
        body = writer.call('inspect_body', function='demo.app.run')['result']['body']
        old_id = re.search(r'literal value=a rev=([0-9a-f]{64})', body).group(1)
        assert writer.call('change_field', entity=old_id, field='value', value='retained label')['ok']
        assert winner.call('rename_entity', entity='demo.app.run', new_name='run_current')['ok']
        committed = winner.call('commit_transaction')
        assert committed['ok'], committed
        before = {p.name: p.read_bytes() for p in (project / 'alva-air').glob('*') if p.is_file()}
        stale = writer.call('commit_transaction')
        assert not stale['ok'] and 'E_AEP_CONFLICT' in str(stale), stale
        # Adapter normalization must match a CONFIRMED code, not arbitrary text.
        assert MinimalIterativeRecovery.conflict(stale), stale
        assert before == {p.name: p.read_bytes() for p in (project / 'alva-air').glob('*') if p.is_file()}
        assignment = 'Set the app label to retained label; preserve the concurrent function rename.'
        history = [{'user': assignment}, {'prior_proposal': 'set app label'}]
        original_history = copy.deepcopy(history)
        received = []
        def sink(event):
            if mode == 'broken':
                raise OSError('unwritable sink')
            received.append(event)
        flow = MinimalIterativeRecovery(assignment, history,
                   lambda tool, args: writer.call(tool, **args), None if mode == 'off' else sink)
        turns = 0
        def next_turn(task, conversation):
            nonlocal turns
            assert task == assignment and conversation[:2] == original_history
            turns += 1
            if turns == 1:
                assert conversation[-1]['tool'] == 'inspect_project'
                assert flow.verification == 'UNKNOWN' and not flow.committed
                return [('inspect_body', {'function': 'demo.app.run_current'})]
            if turns == 2:
                assert conversation[-1]['tool'] == 'inspect_body'
                assert not flow.committed and flow.verification == 'UNKNOWN'
                body = conversation[-1]['response']['result']['body']
                entity = re.search(r'literal value=a rev=([0-9a-f]{64})', body).group(1)
                return [('change_field', {'entity': entity, 'field': 'value', 'value': 'retained label'})]
            if turns == 3:
                assert flow.verification == 'UNKNOWN'
                return [('check_transaction', {})]
            assert turns == 4
            assert conversation[-1]['response']['ok']
            assert not flow.committed and flow.verification == 'UNKNOWN'
            return [('commit_transaction', {})]
        def verify():
            observer = Agent(binary, None, 'verifier')
            try:
                assert observer.call('begin_transaction', project=manifest)['ok']
                body = observer.call('inspect_body', function='demo.app.run_current')
                old = observer.call('resolve_entity', name='demo.app.run', kind='function')
                checked = subprocess.run([str(binary), 'project', 'check', manifest, '--json'], capture_output=True)
                assert body['ok'] and 'literal value=retained label' in body['result']['body']
                assert not old['ok'] and checked.returncode == 0
                return 'PASSED'
            finally:
                observer.close()
        outcome = flow.run(stale, manifest, next_turn, lambda: True, verify if verifier_available else None)
        assert outcome == ('PASSED' if verifier_available else 'UNKNOWN')
        assert flow.committed and turns == 4
        assert history == original_history
        assert (project / 'src/app.alva').read_bytes() == original_source
        operations = [x.get('tool') for x in flow.conversation]
        assert not set(operations) & {'register_recovery_intent', 'inspect_recovery_context', 'begin_recovery'}
        kinds = [x['event'] for x in flow.events]
        assert all(k in kinds for k in ['stale_rejected', 'recovery_started', 'inspection', 'mutation', 'check', 'commit'])
        assert ('final_verification' in kinds) == verifier_available
        if use_mcp:
            assert len(writer.handles) == 2 and writer.handles[0] != writer.handles[1]
        if mode != 'off':
            native = [json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()]
            assert any(x['event'] == 'stale_write_rejected' for x in native)
            assert any(x['event'] == 'commit_succeeded' for x in native)
            assert not any(x['event'] == 'recovery_started' for x in native)
        return (project / 'alva-air/current').read_bytes()
    finally:
        writer.close()
        winner.close()


def commit_rechecks(binary, root):
    project = root / 'commit-recheck'
    shutil.copytree(ROOT / 'tests/project', project)
    agent = Agent(binary, None, 'commit-recheck')
    manifest = str(project / 'alva.toml')
    try:
        assert agent.call('begin_transaction', project=manifest)['ok']
        assert agent.call('commit_transaction')['ok']
        before = {p.name: p.read_bytes() for p in (project / 'alva-air').glob('*') if p.is_file()}
        assert agent.call('begin_transaction', project=manifest)['ok']
        assert agent.call('check_transaction')['ok']
        body = agent.call('inspect_body', function='demo.app.run')['result']['body']
        entity = re.search(r'call name=demo\.model\.size_of rev=([0-9a-f]{64})', body).group(1)
        assert agent.call('change_field', entity=entity, field='name', value='demo.model.missing')['ok']
        # Bypass another explicit check: commit itself must still reject.
        rejected = agent.call('commit_transaction')
        assert not rejected['ok'] and 'E_CALL_002' in str(rejected), rejected
        assert before == {p.name: p.read_bytes() for p in (project / 'alva-air').glob('*') if p.is_file()}
        assert agent.call('abort_transaction')['ok']
    finally:
        agent.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', type=Path, required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='alva-minimal-recovery-') as temp:
        root = Path(temp)
        on = scenario(args.binary, root, 'on')
        assert on == scenario(args.binary, root, 'off')
        assert on == scenario(args.binary, root, 'broken')
        assert on == scenario(args.binary, root, 'unknown', verifier_available=False)
        assert on == scenario(args.binary, root, 'mcp', use_mcp=True)
        commit_rechecks(args.binary, root)
    print('PASS: native CLI/MCP iterative restart, preserved task/history, winner protection, UNKNOWN verification and telemetry equivalence; model calls=0')


if __name__ == '__main__':
    main()
