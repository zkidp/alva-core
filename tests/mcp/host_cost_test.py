#!/usr/bin/env python3
"""Paired deterministic cost qualification; real checks, no models or test cache."""
import argparse
import copy
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmarks.compact_deepseek.preflight import replacement
from benchmarks.maintenance_interface_comparison.service import evaluate
from integrations.benchmark_runtime_v2.freeze import decode
from integrations.benchmark_runtime_v2.sandbox import SDK
from integrations.codex.maintenance_host import AgentProcess, MaintenanceHost, canonical, project_source_loader, sha, tool_result
from tests.mcp.host_workflow_linux import RecordingEvaluator

PROTOCOL = ROOT/'docs/research/maintenance-cost-v3-protocol.json'


def run(sdk, task, mode):
    original=decode(task['bundle'],task['bundle']['payload_sha256'])
    _,body=replacement(task)
    with tempfile.TemporaryDirectory(prefix='host-cost-') as directory:
        root=Path(directory)
        for p,data in original.items():
            path=root/p;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        evaluator=RecordingEvaluator(sdk,task['crate'],assertions='\n'.join(task['assertions'].values()))
        host=MaintenanceHost(lambda:AgentProcess(sdk.alva),root/'alva.toml',task['policy'],
            project_source_loader(root/'alva.toml',task['input_paths']),evaluator,
            bulk_scope=mode=='candidate',digest_rechecks=mode=='candidate')
        outputs=[]
        start=time.monotonic()
        try:
            view=host.invoke('read_target',{'function':task['public_task']['target']});outputs.append(view)
            assert view['status']=='READY',view
            baseline=host.guard._baselines[host.tx]
            # Baseline snapshots and staged scope digests must be identical
            # across the paired runs, without adding reads to timed workloads.
            prepared=host.invoke('prepare_change',{'view_id':view['view_id'],'body':body});outputs.append(prepared)
            assert prepared['status']=='PREPARED',prepared
            assert not (root/'alva-air/current').exists()
            published=host.invoke('publish_change',{'proposal_id':prepared['proposal_id']});outputs.append(published)
            assert published['status']=='PUBLISHED',published
            wall=time.monotonic()-start
            assert host.work['agent_tool_calls']==3
            assert all((root/p).read_bytes()==data for p,data in original.items())
            files={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            final=evaluate(files,sdk,task)
            assert final['goal']['status']==final['regression']['status']=='PASS',final
            scope=published['commit']['host_scope']
            assert scope['changed_functions']==[task['public_task']['target']] and scope['status']=='SCOPE_ALLOWED'
            visible=[]
            for value in outputs:
                value=copy.deepcopy(value)
                if mode=='baseline' and 'host_work' in value:
                    # Measurement-only telemetry was absent from V2's MCP
                    # result. Do not inflate its model-facing baseline.
                    for k in ('native_seconds','native_wire_request_bytes','native_wire_reply_bytes'):
                        value['host_work'].pop(k,None)
                visible.append(len(json.dumps(tool_result(value,compact=mode=='candidate')).encode()))
            public=tool_result(view)['structuredContent']
            assert public['body']==view['body'] and public['declaration']==view['declaration']
            assert public['context']['available_builtins']=={
                b['name']:b['arity'] for b in view['context']['available_builtins']}
            assert tool_result(published)['structuredContent']['revision']==published['commit']['revision']
            return {'mode':mode,'wall_seconds':wall,'host_work':host.work,
                'model_facing_mcp_result_bytes':visible,'model_facing_total_bytes':sum(visible),
                'wire_bytes':host.work['native_wire_request_bytes']+host.work['native_wire_reply_bytes'],
                'baseline_snapshot_sha256':sha(canonical(baseline)), 'scope':scope,
                'draft_checks':evaluator.receipts[0]['checks'],'evaluation_work':evaluator.receipts[0]['work'],
                'final_task':'PASS','final_regression':'PASS','fresh_authority_matches':published['fresh_authority_matches']}
        finally:host.close()


def qualify(sdk):
    protocol=json.loads(PROTOCOL.read_bytes())
    tasks=json.loads((ROOT/'benchmarks/compact_maintenance/REGISTRATION.json').read_bytes())['tasks']
    rows=[]
    for ident in protocol['tasks']:
        trials=[]
        for repetition in range(protocol['repetitions']):
            order=('baseline','candidate') if repetition%2==0 else ('candidate','baseline')
            pair={mode:run(sdk,tasks[ident],mode) for mode in order}
            before,after=pair['baseline'],pair['candidate']
            assert before['scope']==after['scope'],pair
            assert before['baseline_snapshot_sha256']==after['baseline_snapshot_sha256'],pair
            reductions={
                'native_calls':1-after['host_work']['native_calls']/before['host_work']['native_calls'],
                'wire_bytes':1-after['wire_bytes']/before['wire_bytes'],
                'model_facing_bytes':1-after['model_facing_total_bytes']/before['model_facing_total_bytes'],
                'publication_bytes':1-after['model_facing_mcp_result_bytes'][-1]/before['model_facing_mcp_result_bytes'][-1]}
            acceptance=protocol['acceptance']
            for key,threshold in [('native_calls','native_call_reduction_each_task_minimum'),
                ('wire_bytes','native_wire_byte_reduction_each_task_minimum'),
                ('model_facing_bytes','model_facing_response_byte_reduction_each_task_minimum'),
                ('publication_bytes','publication_response_byte_reduction_minimum')]:
                assert reductions[key]>=acceptance[threshold],(ident,key,reductions,acceptance)
            trial={'repetition':repetition,'order':list(order),'runs':pair,'reductions':reductions,
                'wall_ratio':after['wall_seconds']/before['wall_seconds'],
                'native_time_ratio':after['host_work']['native_seconds']/before['host_work']['native_seconds']}
            trials.append(trial)
            print(json.dumps({'task':ident,'repetition':repetition,'reductions':reductions,
                'wall_ratio':trial['wall_ratio']}),flush=True)
        rows.append({'task':ident,'bundle_sha256':tasks[ident]['bundle']['payload_sha256'],'trials':trials,
            'median_wall_ratio':statistics.median(t['wall_ratio'] for t in trials),
            'median_native_time_ratio':statistics.median(t['native_time_ratio'] for t in trials)})
    return {'status':'PASS','protocol_sha256':sha(PROTOCOL.read_bytes()),'alva_sha256':sha(sdk.alva.read_bytes()),
        'model_generation_calls':0,'input_token_api_calls':0,'provider_usage':None,'dollars':None,'rows':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('alva','toolchain','registry','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--shared-uid-profile',action='store_true')
    a=p.parse_args()
    if a.shared_uid_profile:
        from benchmarks.maintenance_interface_comparison.linux_profile import install
        install()
    result=qualify(SDK(*(getattr(a,k).resolve() for k in ('alva','toolchain','registry'))))
    result['shared_uid_profile']=a.shared_uid_profile
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
