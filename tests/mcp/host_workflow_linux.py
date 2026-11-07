#!/usr/bin/env python3
"""Deterministic Host V2 qualification on unchanged registered tasks; zero models.

Core inspection/publication runs as a trusted Host child. All generated code,
behavior tests and fresh draft reads run in the existing Linux namespaces.
Witness extraction is test-only; it is never supplied to a model.
"""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.compact_deepseek.preflight import replacement
from benchmarks.maintenance_interface_comparison.service import evaluate
from integrations.benchmark_runtime_v2.freeze import decode
from integrations.benchmark_runtime_v2.sandbox import SDK
from integrations.codex.maintenance_evaluator import LinuxProjectEvaluator
from integrations.codex.maintenance_host import AgentProcess, MaintenanceHost, project_source_loader, sha


class RecordingEvaluator(LinuxProjectEvaluator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.receipts = []
    def __call__(self, *args):
        result = super().__call__(*args)
        self.receipts.append(result)
        return result


def qualify(sdk):
    tasks = json.loads((ROOT / 'benchmarks/compact_maintenance/REGISTRATION.json').read_bytes())['tasks']
    rows = []
    for ident, task in tasks.items():
        original = decode(task['bundle'], task['bundle']['payload_sha256'])
        baseline = evaluate(original, sdk, task)
        assert baseline['goal']['status'] == 'TEST_FAIL', baseline
        assert baseline['regression']['status'] == 'PASS', baseline
        _, body = replacement(task)
        with tempfile.TemporaryDirectory(prefix='host-v2-qualification-') as directory:
            root = Path(directory)
            for name, data in original.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            # Both suites are unchanged trusted assertions, appended to the
            # generated crate only inside the disposable evaluator namespace.
            evaluator = RecordingEvaluator(sdk, task['crate'], assertions='\n'.join(task['assertions'].values()))
            host = MaintenanceHost(lambda:AgentProcess(sdk.alva), root / 'alva.toml', task['policy'],
                project_source_loader(root / 'alva.toml', task['input_paths']), evaluator)
            try:
                view = host.invoke('read_target', {'function':task['public_task']['target']})
                assert view['status'] == 'READY', view
                proposal = host.invoke('prepare_change', {'view_id':view['view_id'], 'body':body})
                assert proposal['status'] == 'PREPARED', proposal
                assert not (root / 'alva-air/current').exists(), 'staging published authority'
                assert all((root / p).read_bytes() == b for p,b in original.items())
                committed = host.invoke('publish_change', {'proposal_id':proposal['proposal_id']})
                assert committed['status'] == 'PUBLISHED', committed
                assert committed['fresh_authority_matches']
                scope = committed['commit']['host_scope']
                assert scope['status'] == 'SCOPE_ALLOWED', scope
                assert scope['changed_functions'] == [task['public_task']['target']], scope
                assert all((root / p).read_bytes() == b for p,b in original.items())
                published = {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
                final = evaluate(published, sdk, task)
                assert final['goal']['status'] == final['regression']['status'] == 'PASS', final
                assert host.work['agent_tool_calls'] == 3
                receipt = evaluator.receipts[0]
                row = {'task':ident, 'status':'PASS', 'bundle_sha256':task['bundle']['payload_sha256'],
                    'baseline':{'task':'FAIL', 'regression':'PASS'},
                    'draft':receipt['checks'], 'draft_work':receipt['work'],
                    'final':{'task':final['goal']['status'], 'regression':final['regression']['status']},
                    'scope':scope, 'commit_revision':committed['commit']['revision'],
                    'fresh_authority_matches':True, 'sources_unchanged':True,
                    'test_receipt_sha256':committed['test_receipt_sha256'], 'host_work':committed['host_work']}
                rows.append(row)
                print(json.dumps({'task':ident, 'status':'PASS', 'host_work':host.work}), flush=True)
            finally:
                host.close()
    return rows


def reject_wrong_behavior(sdk):
    # A well-typed but wrong candidate must fail actual pre-publication tests.
    from tests.mcp.host_workflow_test import fixture
    with tempfile.TemporaryDirectory(prefix='host-v2-wrong-behavior-') as directory:
        root = Path(directory); policy = fixture(root)
        evaluator = LinuxProjectEvaluator(sdk, 'host_demo', assertions='''
#[test] fn authorized_behavior() { assert_eq!(crate::m::a(), 2); }
#[test] fn preserved_behavior() { assert_eq!(crate::m::b(), 1); }
''')
        host = MaintenanceHost(lambda:AgentProcess(sdk.alva), root / 'alva.toml', policy,
            project_source_loader(root / 'alva.toml', ['alva.toml','m.alva']), evaluator)
        try:
            view = host.invoke('read_target', {'function':'m.a'})
            result = host.invoke('prepare_change', {'view_id':view['view_id'], 'body':'(body (int 3))'})
            assert result['status'] == 'VALIDATION_FAILED', result
            assert result['checks'] == {'check':'PASS','build':'PASS','test':'FAIL'}, result
            assert not (root / 'alva-air/current').exists()
            assert host.proposal is None
            return {'status':'PASS', 'candidate':result['checks'], 'publication_occurred':False}
        finally: host.close()


def cli_publication(sdk, shared_uid_profile):
    """Actual standalone MCP entry through all three actions and real tests."""
    from tests.mcp.host_workflow_test import fixture
    with tempfile.TemporaryDirectory(prefix='host-v2-cli-') as directory:
        root = Path(directory); policy = fixture(root)
        config = {'alva':str(sdk.alva), 'toolchain':str(sdk.rust_toolchain), 'registry':str(sdk.registry),
            'project':str(root/'alva.toml'), 'inputs':['alva.toml','m.alva'], 'crate':'host_demo', 'policy':policy,
            'assertions':'\n#[test] fn maintained() { assert_eq!(crate::m::a(), 2); assert_eq!(crate::m::b(), 1); }\n'}
        path = root/'trusted.json'; path.write_text(json.dumps(config))
        setup = ('from benchmarks.maintenance_interface_comparison.linux_profile import install;install();'
                 if shared_uid_profile else '')
        command = [sys.executable, '-c', setup +
            "import runpy;runpy.run_module('integrations.codex.maintenance_host',run_name='__main__')", '--config', str(path)]
        proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8')
        lines = queue.Queue()
        def reader():
            for line in proc.stdout: lines.put(line)
            lines.put(None)
        thread = threading.Thread(target=reader, daemon=True); thread.start()
        def call(name, arguments):
            proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':name,'method':'tools/call',
                'params':{'name':name,'arguments':arguments}})+'\n');proc.stdin.flush()
            line = lines.get(timeout=120)
            assert line, 'Host closed without response'
            response = json.loads(line)
            return response['result']['structuredContent']
        try:
            view = call('read_target', {'function':'m.a'})
            proposal = call('prepare_change', {'view_id':view['view_id'], 'body':'(body (int 2))'})
            assert proposal['status']=='PREPARED', proposal
            result = call('publish_change', {'proposal_id':proposal['proposal_id']})
            assert result['status']=='PUBLISHED', result
            assert result['fresh_authority_matches']
            assert (root/'alva-air/current').exists()
            proc.stdin.close();proc.wait(timeout=10);thread.join(timeout=5)
            assert proc.returncode==0, proc.stderr.read()
            return {'status':'PASS', 'agent_tool_calls':3, 'isolated_tests':'PASS', 'fresh_authority_matches':True}
        finally:
            if proc.poll() is None: proc.kill();proc.wait(timeout=10)
            thread.join(timeout=5)
            for stream in (proc.stdin,proc.stdout,proc.stderr): stream.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--alva', type=Path, required=True)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--shared-uid-profile', action='store_true')
    args = p.parse_args()
    if args.shared_uid_profile:
        from benchmarks.maintenance_interface_comparison.linux_profile import install
        install()
    sdk = SDK(*(getattr(args,k).resolve() for k in ('alva','toolchain','registry')))
    result = {'status':'PASS', 'model_generation_calls':0, 'input_token_api_calls':0,
        'alva_sha256':sha(sdk.alva.read_bytes()), 'shared_uid_profile':args.shared_uid_profile,
        'rows':qualify(sdk), 'wrong_behavior_control':reject_wrong_behavior(sdk),
        'standalone_mcp_publication':cli_publication(sdk, args.shared_uid_profile)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
