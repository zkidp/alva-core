"""Twelve no-model routes. Deterministic witnesses never enter model inputs."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmarks.host_v3_acceptance.protocol import design
from benchmarks.host_v3_acceptance.service import Session
from benchmarks.compact_deepseek.preflight import replacement
from benchmarks.maintenance_interface_comparison.service import evaluate
from integrations.benchmark_runtime_v2.freeze import decode
from integrations.benchmark_runtime_v2.sandbox import SDK


def main(args):
    from benchmarks.maintenance_interface_comparison.linux_profile import install
    install()
    sdk=SDK(*(getattr(args,k).resolve() for k in ('alva','toolchain','registry')))
    d=design();rows=[]
    for entry in d['schedule']:
        task=d['tasks'][entry['task']]
        original=decode(task['bundle'],task['bundle']['payload_sha256'])
        baseline=evaluate(original,sdk,task)
        assert baseline['goal']['status']=='TEST_FAIL' and baseline['regression']['status']=='PASS'
        changed,body=replacement(task)
        session=Session(task,entry['arm'],sdk)
        try:
            view=session.tool('read_target',{'function':task['public_task']['target']})['structuredContent']
            assert view['status']=='READY',view
            if entry['arm']=='T':
                edits=[{'path':p,'old':b.decode(),'new':changed[p].decode()} for p,b in original.items() if changed[p]!=b]
                args_={'view_id':view['view_id'],'edits':edits}
            else:args_={'view_id':view['view_id'],'body':body}
            proposal=session.tool('prepare_change',args_)['structuredContent']
            assert proposal['status']=='PREPARED',proposal
            published=session.tool('publish_change',{'proposal_id':proposal['proposal_id']})['structuredContent']
            assert published['status']=='PUBLISHED',published
            result=session.finish()
            assert result['correct'] and result['cleanup_confirmed'] and result['original_sources_unchanged'],result
            row={**entry,'status':'PASS','task_test':result['task'],'regression':result['regression'],
                'scope':result['scope'],'fresh_authority_matches':result['fresh_authority_matches'],
                'cleanup_confirmed':result['cleanup_confirmed']}
            rows.append(row);print(json.dumps({'id':entry['id'],'status':'PASS'}),flush=True)
        finally:session.close()
    # A rejected source proposal cannot reuse an older passing authorization.
    task=d['tasks']['MM01'];session=Session(task,'T',sdk)
    try:
        original=session.original;changed,_=replacement(task)
        view=session.tool('read_target',{'function':task['public_task']['target']})['structuredContent']
        edits=[{'path':p,'old':b.decode(),'new':changed[p].decode()} for p,b in original.items() if changed[p]!=b]
        proposal=session.tool('prepare_change',{'view_id':view['view_id'],'edits':edits})['structuredContent']
        assert proposal['status']=='PREPARED'
        denied=session.tool('prepare_change',{'view_id':view['view_id'],
            'edits':[{'path':'src/app.alva','old':'(int 5)','new':'(int 4)'}]})['structuredContent']
        assert denied['status']=='SCOPE_VIOLATION' and not denied['source_edits_applied'],denied
        assert session.tool('publish_change',{'proposal_id':proposal['proposal_id']})['structuredContent']['status']=='REJECTED'
        assert not (session.root/'alva-air/current').exists()
    finally:session.close()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'status':'PASS','model_generation_calls':0,'rows':rows,
        'source_scope_denial_invalidates_passing_proposal':'PASS'},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('alva','toolchain','registry','output'):p.add_argument('--'+k,type=Path,required=True)
    main(p.parse_args())
